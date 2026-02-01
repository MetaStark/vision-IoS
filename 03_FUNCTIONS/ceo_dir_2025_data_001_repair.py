#!/usr/bin/env python3
"""
CEO-DIR-2025-DATA-001 PRICE DATA REPAIR
=======================================

Authority: CEO
Executor: STIG (EC-003)
Date: 2025-12-30

This script repairs corrupted CRYPTO volume data caused by Alpaca
returning volumes in native token units instead of USD notional.

Actions:
1. Delete corrupted ALPACA CRYPTO records (volume < 1000)
2. Re-ingest from Yahoo Finance with correct USD notional volumes
3. Verify repair success

Root Cause: Alpaca API returns crypto volumes in native token units (BTC, ETH)
            while Yahoo Finance returns USD notional volume (billions).
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from dotenv import load_dotenv

# Load .env
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# Database config
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

# Evidence directory
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("CEO_DIR_REPAIR")

# Volume threshold - anything below this for CRYPTO is corrupted
# Normal BTC daily volume is ~30-80 billion USD
CRYPTO_VOLUME_MIN_THRESHOLD = 1000


def get_connection():
    return psycopg2.connect(**DB_CONFIG, options='-c client_encoding=UTF8')


def identify_corrupted_records(conn) -> List[Dict]:
    """Identify all corrupted CRYPTO records."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"""
            SELECT
                id,
                canonical_id,
                timestamp::date as date,
                volume,
                source
            FROM fhq_market.prices
            WHERE canonical_id LIKE '%-USD'
            AND volume < {CRYPTO_VOLUME_MIN_THRESHOLD}
            AND timestamp::date >= '2025-12-01'
            ORDER BY canonical_id, timestamp::date
        """)
        return cur.fetchall()


def delete_corrupted_records(conn, records: List[Dict]) -> int:
    """Delete corrupted records by ID."""
    if not records:
        return 0

    record_ids = [str(r['id']) for r in records]

    with conn.cursor() as cur:
        # Delete in batches of 100
        deleted = 0
        for i in range(0, len(record_ids), 100):
            batch = record_ids[i:i+100]
            cur.execute("""
                DELETE FROM fhq_market.prices
                WHERE id::text = ANY(%s)
            """, (batch,))
            deleted += cur.rowcount

        conn.commit()

    return deleted


def get_dates_to_reingest(records: List[Dict]) -> Dict[str, List[date]]:
    """Group corrupted records by asset and get dates to re-ingest."""
    asset_dates = {}
    for r in records:
        canonical_id = r['canonical_id']
        record_date = r['date']

        if canonical_id not in asset_dates:
            asset_dates[canonical_id] = []

        if record_date not in asset_dates[canonical_id]:
            asset_dates[canonical_id].append(record_date)

    return asset_dates


def reingest_from_yahoo(conn, asset_dates: Dict[str, List[date]], batch_id: str) -> Dict:
    """Re-ingest from Yahoo Finance for specified dates."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed")
        return {'status': 'FAILED', 'error': 'yfinance not installed'}

    results = {
        'assets_processed': 0,
        'rows_inserted': 0,
        'errors': [],
        'status': 'SUCCESS'
    }

    for canonical_id, dates in asset_dates.items():
        if not dates:
            continue

        # Find min/max dates with buffer
        min_date = min(dates) - timedelta(days=1)
        max_date = max(dates) + timedelta(days=1)

        logger.info(f"  Re-ingesting {canonical_id}: {len(dates)} dates from {min_date} to {max_date}")

        try:
            # Download from Yahoo
            df = yf.download(
                canonical_id,
                start=min_date.strftime('%Y-%m-%d'),
                end=(max_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1d',
                auto_adjust=False,
                progress=False,
                threads=False
            )

            if df.empty:
                logger.warning(f"    No data from Yahoo for {canonical_id}")
                results['errors'].append(f"{canonical_id}: No Yahoo data")
                continue

            # Normalize columns
            df.columns = df.columns.str.lower()
            if 'adj close' in df.columns:
                df.rename(columns={'adj close': 'adj_close'}, inplace=True)

            # Filter to only the dates we need
            df = df[df.index.date.isin([d if isinstance(d, date) else d.date() for d in dates])]

            if df.empty:
                logger.warning(f"    No matching dates for {canonical_id}")
                continue

            # Insert rows
            rows_inserted = insert_prices(conn, canonical_id, df, batch_id)
            results['rows_inserted'] += rows_inserted
            results['assets_processed'] += 1

            logger.info(f"    Inserted {rows_inserted} rows for {canonical_id}")

        except Exception as e:
            error_msg = str(e)[:200]
            logger.error(f"    Error for {canonical_id}: {error_msg}")
            results['errors'].append(f"{canonical_id}: {error_msg}")

    if results['errors']:
        results['status'] = 'PARTIAL' if results['rows_inserted'] > 0 else 'FAILED'

    return results


def insert_prices(conn, canonical_id: str, df: pd.DataFrame, batch_id: str) -> int:
    """Insert price data with volume sanity check."""
    if df is None or df.empty:
        return 0

    rows = []
    for idx, row in df.iterrows():
        try:
            timestamp = idx.tz_localize(None) if hasattr(idx, 'tz_localize') and idx.tzinfo else idx
        except:
            timestamp = idx

        try:
            open_val = float(row['open']) if pd.notna(row.get('open')) else None
            high_val = float(row['high']) if pd.notna(row.get('high')) else None
            low_val = float(row['low']) if pd.notna(row.get('low')) else None
            close_val = float(row['close']) if pd.notna(row.get('close')) else None
            volume_val = float(row.get('volume', 0)) if pd.notna(row.get('volume')) else 0
            adj_close_val = float(row.get('adj_close', close_val)) if pd.notna(row.get('adj_close', close_val)) else close_val
        except Exception as e:
            logger.debug(f"Row parse error: {e}")
            continue

        if close_val is None or close_val <= 0:
            continue

        # VOLUME SANITY CHECK - CEO-DIR-2025-DATA-001 Section B
        if canonical_id.endswith('-USD') and volume_val < CRYPTO_VOLUME_MIN_THRESHOLD:
            logger.warning(f"    SANITY REJECT: {canonical_id} {timestamp} volume={volume_val} < {CRYPTO_VOLUME_MIN_THRESHOLD}")
            continue

        # Fix OHLC
        if open_val is None:
            open_val = close_val
        if high_val is None:
            high_val = max(open_val, close_val)
        if low_val is None:
            low_val = min(open_val, close_val)
        high_val = max(high_val, open_val, close_val)
        low_val = min(low_val, open_val, close_val)

        # Data hash
        data_str = f"{canonical_id}|{timestamp}|{open_val}|{high_val}|{low_val}|{close_val}|{volume_val}"
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        rows.append((
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            canonical_id,
            timestamp,
            open_val,
            high_val,
            low_val,
            close_val,
            volume_val,
            'YAHOO_REPAIR',  # Mark as repair source
            None,
            data_hash,
            False,
            False,
            1.0,
            batch_id,
            'STIG',
            adj_close_val
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
                    volume = EXCLUDED.volume,
                    adj_close = EXCLUDED.adj_close,
                    data_hash = EXCLUDED.data_hash,
                    source = EXCLUDED.source
            """
            execute_values(cur, insert_sql, rows)
            conn.commit()
        return len(rows)
    except Exception as e:
        conn.rollback()
        logger.error(f"Insert error: {e}")
        return 0


def verify_repair(conn) -> Dict:
    """Verify no corrupted records remain."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"""
            SELECT
                COUNT(*) as remaining_corrupted,
                COUNT(DISTINCT canonical_id) as assets_affected
            FROM fhq_market.prices
            WHERE canonical_id LIKE '%-USD'
            AND volume < {CRYPTO_VOLUME_MIN_THRESHOLD}
            AND timestamp::date >= '2025-12-01'
        """)
        result = cur.fetchone()

        cur.execute("""
            SELECT
                canonical_id,
                COUNT(*) as record_count,
                MIN(timestamp::date) as min_date,
                MAX(timestamp::date) as max_date,
                AVG(volume) as avg_volume
            FROM fhq_market.prices
            WHERE canonical_id LIKE '%-USD'
            AND timestamp::date >= '2025-12-01'
            GROUP BY canonical_id
            ORDER BY canonical_id
        """)
        coverage = cur.fetchall()

    return {
        'remaining_corrupted': result['remaining_corrupted'],
        'assets_affected': result['assets_affected'],
        'verification_passed': result['remaining_corrupted'] == 0,
        'asset_coverage': coverage
    }


def log_governance_event(conn, event_type: str, details: Dict):
    """Log to governance table."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type, action_timestamp, action_by, details
                ) VALUES (%s, NOW(), 'STIG', %s)
            """, (f'CEO_DIR_2025_DATA_001_{event_type}', json.dumps(details, default=str)))
            conn.commit()
    except Exception as e:
        logger.warning(f"Governance logging failed: {e}")
        conn.rollback()


def run_repair():
    """Execute CEO-DIR-2025-DATA-001 Section A: Price Data Repair."""
    start_time = datetime.now(timezone.utc)
    batch_id = str(uuid.uuid4())

    logger.info("=" * 70)
    logger.info("CEO-DIR-2025-DATA-001 PRICE DATA REPAIR")
    logger.info("=" * 70)
    logger.info(f"Authority: CEO")
    logger.info(f"Executor: STIG (EC-003)")
    logger.info(f"Batch ID: {batch_id}")
    logger.info(f"Time: {start_time.isoformat()}")
    logger.info("=" * 70)

    conn = get_connection()

    results = {
        'batch_id': batch_id,
        'started_at': start_time.isoformat(),
        'directive': 'CEO-DIR-2025-DATA-001',
        'section': 'A. PRICE DATA REPAIR',
        'status': 'FAILED'
    }

    # Step 1: Identify corrupted records
    logger.info("\n[STEP 1] Identifying corrupted records...")
    corrupted = identify_corrupted_records(conn)
    results['corrupted_found'] = len(corrupted)
    results['assets_affected'] = len(set(r['canonical_id'] for r in corrupted))

    logger.info(f"  Found {len(corrupted)} corrupted records across {results['assets_affected']} assets")

    if not corrupted:
        logger.info("  No corrupted records found - repair not needed")
        results['status'] = 'NOT_NEEDED'
        conn.close()
        return results

    # Step 2: Get dates to re-ingest
    logger.info("\n[STEP 2] Planning re-ingest...")
    asset_dates = get_dates_to_reingest(corrupted)

    for asset, dates in asset_dates.items():
        logger.info(f"  {asset}: {len(dates)} dates")

    # Step 3: Delete corrupted records
    logger.info("\n[STEP 3] Deleting corrupted records...")
    deleted = delete_corrupted_records(conn, corrupted)
    results['records_deleted'] = deleted
    logger.info(f"  Deleted {deleted} corrupted records")

    # Step 4: Re-ingest from Yahoo
    logger.info("\n[STEP 4] Re-ingesting from Yahoo Finance...")
    reingest_results = reingest_from_yahoo(conn, asset_dates, batch_id)
    results['reingest'] = reingest_results
    logger.info(f"  Re-ingested {reingest_results['rows_inserted']} rows for {reingest_results['assets_processed']} assets")

    # Step 5: Verify repair
    logger.info("\n[STEP 5] Verifying repair...")
    verification = verify_repair(conn)
    results['verification'] = verification

    if verification['verification_passed']:
        logger.info("  VERIFICATION PASSED - No corrupted records remain")
        results['status'] = 'SUCCESS'
    else:
        logger.warning(f"  VERIFICATION FAILED - {verification['remaining_corrupted']} corrupted records remain")
        results['status'] = 'PARTIAL'

    # Log governance event
    log_governance_event(conn, 'REPAIR_COMPLETE', results)

    # Save evidence
    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    evidence_file = EVIDENCE_DIR / f"CEO_DIR_2025_DATA_001_REPAIR_{batch_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("REPAIR COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Status: {results['status']}")
    logger.info(f"Corrupted Found: {results['corrupted_found']}")
    logger.info(f"Records Deleted: {results['records_deleted']}")
    logger.info(f"Rows Re-ingested: {reingest_results['rows_inserted']}")
    logger.info(f"Verification: {'PASSED' if verification['verification_passed'] else 'FAILED'}")
    logger.info(f"Evidence: {evidence_file}")
    logger.info("=" * 70)

    conn.close()
    return results


if __name__ == "__main__":
    results = run_repair()
    sys.exit(0 if results['status'] in ['SUCCESS', 'NOT_NEEDED'] else 1)
