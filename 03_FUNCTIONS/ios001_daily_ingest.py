#!/usr/bin/env python3
"""
IoS-001 DAILY PRICE INGEST - Full 466 Asset Universe
=====================================================

Authority:
- CEO Directive: CEO_DIRECTIVE_LINE_DAILY_INGEST_ACTIVATION_20251212
- ADR-013 Infrastructure Sovereignty
- ADR-007 Orchestrator Architecture
- IoS-001 Market Truth (G4_CONSTITUTIONAL)
- IoS-003 v4.0 Sovereign Perception (G4_CONSTITUTIONAL)

Executor: LINE (EC-004)
Schedule:
  - CRYPTO: Daily 01:00 UTC (7 days/week)
  - EQUITY: Weekdays 22:00 UTC (Mon-Fri)
  - FX: Sun-Thu 22:00 UTC

Asset Coverage: 466 VEGA-attesterte assets
  - CRYPTO: 47
  - EQUITY: 394
  - FX: 25

Usage:
    python ios001_daily_ingest.py                    # Run all asset classes
    python ios001_daily_ingest.py --asset-class CRYPTO
    python ios001_daily_ingest.py --asset-class EQUITY
    python ios001_daily_ingest.py --dry-run
    python ios001_daily_ingest.py --trigger-regime   # Also update HMM regimes
"""

import os
import sys
import json
import hashlib
import uuid
import logging
import time
import argparse
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import pandas as pd
import numpy as np
import yfinance as yf
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

# Rate limiting - conservative to avoid yfinance blocks
BATCH_SIZE = 25
BATCH_DELAY_SECONDS = 60
CALL_DELAY_SECONDS = 3

# Paths
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# Asset class schedules (for reference - actual scheduling via Windows Task Scheduler or cron)
SCHEDULES = {
    'CRYPTO': {'cron': '0 1 * * *', 'weekend': True, 'description': 'Daily 01:00 UTC'},
    'EQUITY': {'cron': '0 22 * * 1-5', 'weekend': False, 'description': 'Weekdays 22:00 UTC'},
    'FX': {'cron': '0 22 * * 0-4', 'weekend': False, 'description': 'Sun-Thu 22:00 UTC'}
}

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(EVIDENCE_DIR / f"ios001_daily_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("IOS001_DAILY_INGEST")


def get_connection():
    return psycopg2.connect(**DB_CONFIG, options='-c client_encoding=UTF8')


# =============================================================================
# ASSET UNIVERSE
# =============================================================================

def get_vega_attested_assets(conn, asset_class: Optional[str] = None) -> List[Dict]:
    """
    Get all VEGA-attested assets with HMM regime data.
    These are the canonical 466 assets.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = """
            SELECT DISTINCT
                a.canonical_id,
                a.ticker,
                a.asset_class,
                a.exchange_mic,
                a.data_quality_status
            FROM fhq_meta.assets a
            WHERE a.canonical_id IN (
                SELECT DISTINCT asset_id
                FROM fhq_perception.regime_daily
                WHERE hmm_version = 'v4.0'
            )
            AND a.active_flag = true
        """
        if asset_class:
            query += f" AND a.asset_class = '{asset_class}'"
        query += " ORDER BY a.asset_class, a.canonical_id"

        cur.execute(query)
        return cur.fetchall()


def get_yfinance_ticker(canonical_id: str, asset_class: str) -> str:
    """Map canonical_id to yfinance ticker format"""
    # FX pairs need =X suffix
    if asset_class == 'FX':
        if not canonical_id.endswith('=X'):
            return canonical_id + '=X'
    return canonical_id


def is_market_open_today(asset_class: str) -> bool:
    """Check if market is open today for asset class"""
    today = datetime.now(timezone.utc).weekday()  # 0=Monday, 6=Sunday

    if asset_class == 'CRYPTO':
        return True  # 24/7
    elif asset_class == 'EQUITY':
        return today < 5  # Mon-Fri
    elif asset_class == 'FX':
        # FX trades Sun evening to Fri evening
        return today < 5 or today == 6  # Sun-Fri
    return True


# =============================================================================
# DATA FETCHING
# =============================================================================

def fetch_daily_prices(
    canonical_id: str,
    yf_ticker: str,
    start_date: date,
    end_date: date
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from yfinance"""
    try:
        ticker = yf.Ticker(yf_ticker)
        df = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            interval='1d',
            auto_adjust=False  # Get both Close and Adj Close
        )

        if df.empty:
            return None

        return df

    except Exception as e:
        logger.warning(f"  [{canonical_id}] Fetch error: {str(e)[:100]}")
        return None


def get_last_price_date(conn, canonical_id: str) -> Optional[date]:
    """Get most recent price date for asset"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT MAX(timestamp::date)
            FROM fhq_market.prices
            WHERE canonical_id = %s
        """, (canonical_id,))
        result = cur.fetchone()[0]
        return result


# =============================================================================
# DATA INSERTION
# =============================================================================

def insert_prices(conn, canonical_id: str, df: pd.DataFrame, batch_id: str) -> int:
    """Insert price data with IoS-002 dual price ontology (close + adj_close)"""
    if df is None or df.empty:
        return 0

    rows = []
    for idx, row in df.iterrows():
        try:
            timestamp = idx.tz_localize(None) if idx.tzinfo else idx
        except:
            timestamp = idx

        try:
            open_val = float(row['Open']) if pd.notna(row.get('Open')) else None
            high_val = float(row['High']) if pd.notna(row.get('High')) else None
            low_val = float(row['Low']) if pd.notna(row.get('Low')) else None
            close_val = float(row['Close']) if pd.notna(row.get('Close')) else None
            adj_close_val = float(row['Adj Close']) if pd.notna(row.get('Adj Close')) else close_val
            volume_val = float(row['Volume']) if pd.notna(row.get('Volume')) else 0
        except:
            continue

        if close_val is None or close_val <= 0:
            continue

        # OHLC validation
        if open_val is None: open_val = close_val
        if high_val is None: high_val = max(open_val, close_val)
        if low_val is None: low_val = min(open_val, close_val)

        # Ensure OHLC constraints
        high_val = max(high_val, open_val, close_val)
        low_val = min(low_val, open_val, close_val)

        # Data hash
        data_str = f"{canonical_id}|{timestamp}|{open_val}|{high_val}|{low_val}|{close_val}|{adj_close_val}|{volume_val}"
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        rows.append((
            str(uuid.uuid4()),  # id
            str(uuid.uuid4()),  # asset_id
            canonical_id,
            timestamp,
            open_val,
            high_val,
            low_val,
            close_val,
            volume_val,
            'yfinance',         # source
            None,               # staging_id
            data_hash,
            False,              # gap_filled
            False,              # interpolated
            1.0,                # quality_score
            batch_id,
            'LINE',             # canonicalized_by
            adj_close_val       # IoS-002 compliant
        ))

    if not rows:
        return 0

    try:
        with conn.cursor() as cur:
            insert_sql = """
                INSERT INTO fhq_market.prices (
                    id, asset_id, canonical_id, timestamp, open, high, low, close, volume,
                    source, staging_id, data_hash, gap_filled, interpolated, quality_score,
                    batch_id, canonicalized_by, adj_close
                ) VALUES %s
                ON CONFLICT (canonical_id, timestamp) DO UPDATE SET
                    adj_close = EXCLUDED.adj_close,
                    data_hash = EXCLUDED.data_hash
                WHERE fhq_market.prices.adj_close IS NULL
            """
            execute_values(cur, insert_sql, rows)
            conn.commit()
        return len(rows)
    except Exception as e:
        conn.rollback()
        logger.error(f"  [{canonical_id}] Insert error: {e}")
        return 0


def update_asset_row_count(conn, canonical_id: str):
    """Update asset valid_row_count after ingest"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_meta.assets
            SET valid_row_count = (
                SELECT COUNT(*) FROM fhq_market.prices WHERE canonical_id = %s
            ),
            updated_at = NOW()
            WHERE canonical_id = %s
        """, (canonical_id, canonical_id))
        conn.commit()


# =============================================================================
# HEARTBEAT & MONITORING
# =============================================================================

def record_heartbeat(conn, component: str, status: str, details: dict):
    """Record system heartbeat for monitoring"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.system_heartbeats (
                    component_name, status, details, recorded_at
                ) VALUES (%s, %s, %s, NOW())
                ON CONFLICT (component_name) DO UPDATE SET
                    status = EXCLUDED.status,
                    details = EXCLUDED.details,
                    recorded_at = NOW()
            """, (component, status, json.dumps(details)))
            conn.commit()
    except Exception as e:
        logger.warning(f"Heartbeat recording failed: {e}")


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_daily_ingest(
    asset_class: Optional[str] = None,
    dry_run: bool = False,
    trigger_regime: bool = False
) -> Dict:
    """
    Execute daily price ingest for VEGA-attested assets.
    """
    logger.info("=" * 70)
    logger.info("IoS-001 DAILY PRICE INGEST")
    logger.info(f"Executor: LINE (EC-004)")
    logger.info(f"Authority: CEO_DIRECTIVE_LINE_DAILY_INGEST_ACTIVATION_20251212")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Asset Class Filter: {asset_class or 'ALL'}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("=" * 70)

    conn = get_connection()
    batch_id = str(uuid.uuid4())

    results = {
        'batch_id': batch_id,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'asset_class': asset_class or 'ALL',
        'assets_processed': 0,
        'assets_updated': 0,
        'rows_inserted': 0,
        'errors': [],
        'by_class': {}
    }

    # Get VEGA-attested assets
    assets = get_vega_attested_assets(conn, asset_class)
    logger.info(f"Found {len(assets)} VEGA-attested assets")

    # Group by asset class
    by_class = {}
    for asset in assets:
        cls = asset['asset_class']
        if cls not in by_class:
            by_class[cls] = []
        by_class[cls].append(asset)

    # Process each asset class
    for cls, class_assets in by_class.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {cls}: {len(class_assets)} assets")
        logger.info(f"Schedule: {SCHEDULES.get(cls, {}).get('description', 'N/A')}")
        logger.info(f"{'='*60}")

        if not is_market_open_today(cls):
            logger.info(f"  Market closed for {cls} today, skipping")
            results['by_class'][cls] = {'skipped': True, 'reason': 'market_closed'}
            continue

        class_results = {
            'total': len(class_assets),
            'updated': 0,
            'rows': 0,
            'errors': 0
        }

        # Process in batches
        for i in range(0, len(class_assets), BATCH_SIZE):
            batch = class_assets[i:i+BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(class_assets) + BATCH_SIZE - 1) // BATCH_SIZE

            logger.info(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} assets)")

            for asset in batch:
                canonical_id = asset['canonical_id']
                ticker = asset['ticker']

                results['assets_processed'] += 1

                # Get last price date
                last_date = get_last_price_date(conn, canonical_id)

                if last_date:
                    start_date = last_date + timedelta(days=1)
                else:
                    start_date = date.today() - timedelta(days=30)

                end_date = date.today()

                if start_date > end_date:
                    logger.debug(f"    [{canonical_id}] Up to date")
                    continue

                # Get yfinance ticker
                yf_ticker = get_yfinance_ticker(canonical_id, cls)

                if dry_run:
                    logger.info(f"    [{canonical_id}] Would fetch {start_date} to {end_date}")
                    continue

                # Fetch data
                df = fetch_daily_prices(canonical_id, yf_ticker, start_date, end_date)

                if df is not None and not df.empty:
                    rows = insert_prices(conn, canonical_id, df, batch_id)
                    if rows > 0:
                        update_asset_row_count(conn, canonical_id)
                        results['assets_updated'] += 1
                        results['rows_inserted'] += rows
                        class_results['updated'] += 1
                        class_results['rows'] += rows
                        logger.info(f"    [{canonical_id}] +{rows} rows")
                else:
                    class_results['errors'] += 1

                # Rate limit
                time.sleep(CALL_DELAY_SECONDS)

            # Batch delay
            if i + BATCH_SIZE < len(class_assets):
                logger.info(f"  Batch complete, waiting {BATCH_DELAY_SECONDS}s...")
                time.sleep(BATCH_DELAY_SECONDS)

        results['by_class'][cls] = class_results

    # Record heartbeat
    if not dry_run:
        record_heartbeat(conn, 'IOS001_DAILY_INGEST', 'SUCCESS', {
            'batch_id': batch_id,
            'assets_updated': results['assets_updated'],
            'rows_inserted': results['rows_inserted']
        })

    # Trigger regime update if requested
    if trigger_regime and not dry_run and results['assets_updated'] > 0:
        logger.info("\n" + "=" * 70)
        logger.info("Triggering IoS-003 Regime Update...")
        try:
            import subprocess
            regime_script = Path(__file__).parent / "ios003_daily_regime_update.py"
            if regime_script.exists():
                subprocess.run([sys.executable, str(regime_script)], check=True)
                results['regime_update'] = 'TRIGGERED'
            else:
                results['regime_update'] = 'SCRIPT_NOT_FOUND'
        except Exception as e:
            results['regime_update'] = f'FAILED: {e}'
            logger.error(f"Regime update failed: {e}")

    results['completed_at'] = datetime.now(timezone.utc).isoformat()

    # Save evidence
    evidence_file = EVIDENCE_DIR / f"IOS001_DAILY_INGEST_{batch_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("DAILY INGEST COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Assets Processed: {results['assets_processed']}")
    logger.info(f"Assets Updated:   {results['assets_updated']}")
    logger.info(f"Rows Inserted:    {results['rows_inserted']}")
    for cls, cls_results in results['by_class'].items():
        if isinstance(cls_results, dict) and not cls_results.get('skipped'):
            logger.info(f"  {cls}: {cls_results.get('updated', 0)} assets, {cls_results.get('rows', 0)} rows")
    logger.info(f"Evidence: {evidence_file}")
    logger.info("=" * 70)

    conn.close()
    return results


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IoS-001 Daily Price Ingest")
    parser.add_argument("--asset-class", choices=['CRYPTO', 'EQUITY', 'FX'],
                        help="Filter by asset class")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be fetched without executing")
    parser.add_argument("--trigger-regime", action="store_true",
                        help="Trigger IoS-003 regime update after ingest")

    args = parser.parse_args()

    results = run_daily_ingest(
        asset_class=args.asset_class,
        dry_run=args.dry_run,
        trigger_regime=args.trigger_regime
    )

    sys.exit(0 if results['assets_updated'] >= 0 else 1)
