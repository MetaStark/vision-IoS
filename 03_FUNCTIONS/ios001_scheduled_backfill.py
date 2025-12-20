#!/usr/bin/env python3
"""
IoS-001 SCHEDULED PRICE BACKFILL
================================
CEO DIRECTIVE: Ultra-conservative rate-limit protection.

Strategy:
- Single ticker fetch at a time
- 30-second delay between fetches
- 5-minute pause between batches of 10
- Skip already-backfilled assets

This script is designed to run safely without hitting yfinance rate limits.
"""

import os
import sys
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import pandas as pd
import yfinance as yf
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION - Ultra Conservative
# =============================================================================

PGHOST = os.getenv("PGHOST", "127.0.0.1")
PGPORT = os.getenv("PGPORT", "54322")
PGDATABASE = os.getenv("PGDATABASE", "postgres")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

DELAY_BETWEEN_ASSETS = 30  # 30 seconds between each ticker
BATCH_SIZE = 10  # 10 assets per batch
DELAY_BETWEEN_BATCHES = 300  # 5 minutes between batches
MAX_RETRIES = 3
RETRY_DELAY = 120  # 2 minute wait on failure

# History
MAX_HISTORY_YEARS = 10

# Iron Curtain thresholds
EQUITY_FX_QUARANTINE = 252
EQUITY_FX_FULL_HISTORY = 1260
CRYPTO_QUARANTINE = 365
CRYPTO_FULL_HISTORY = 1825

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "evidence" / f"scheduled_backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE
# =============================================================================

def get_connection():
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD
    )

def get_assets_without_prices(conn, limit: int = None) -> List[Dict]:
    """Get assets that don't have price data yet"""
    with conn.cursor() as cur:
        sql = """
            SELECT
                a.canonical_id,
                a.ticker,
                a.asset_class,
                a.exchange_mic,
                a.quarantine_threshold,
                a.full_history_threshold
            FROM fhq_meta.assets a
            LEFT JOIN (
                SELECT DISTINCT canonical_id FROM fhq_market.prices
            ) p ON a.canonical_id = p.canonical_id
            WHERE a.active_flag = true
              AND p.canonical_id IS NULL
            ORDER BY
                CASE a.asset_class
                    WHEN 'EQUITY' THEN 1  -- Prioritize equities
                    WHEN 'FX' THEN 2
                    WHEN 'CRYPTO' THEN 3
                END,
                a.canonical_id
        """
        if limit:
            sql += f" LIMIT {limit}"

        cur.execute(sql)
        rows = cur.fetchall()

        return [
            {
                "canonical_id": r[0],
                "ticker": r[1],
                "asset_class": r[2],
                "exchange_mic": r[3],
                "quarantine_threshold": r[4] or EQUITY_FX_QUARANTINE,
                "full_history_threshold": r[5] or EQUITY_FX_FULL_HISTORY
            }
            for r in rows
        ]

def get_yfinance_ticker(asset: Dict) -> str:
    """Convert asset to yfinance ticker format"""
    ticker = asset["ticker"]
    asset_class = asset["asset_class"]

    if asset_class == "CRYPTO":
        return f"{ticker}-USD"
    elif asset_class == "FX":
        return f"{ticker}=X"
    else:
        return ticker

def fetch_prices(ticker: str, start_date: date, end_date: date) -> Optional[pd.DataFrame]:
    """Fetch prices with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"Fetching {ticker} (attempt {attempt + 1})")

            df = yf.download(
                ticker,
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1d',
                auto_adjust=False,
                progress=False,
                threads=False
            )

            if df is None or df.empty:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Empty response for {ticker}, waiting {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                return None

            df = df.dropna(subset=['Close'])
            if df.empty:
                return None

            return df

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = any(x in error_str for x in ['rate', 'limit', '429', 'throttle', 'too many'])

            if is_rate_limit:
                wait_time = RETRY_DELAY * (attempt + 1)
                logger.warning(f"Rate limited for {ticker}, waiting {wait_time}s...")
                time.sleep(wait_time)
            elif attempt < MAX_RETRIES - 1:
                logger.warning(f"Error fetching {ticker}: {e}, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Failed to fetch {ticker} after {MAX_RETRIES} attempts: {e}")
                return None

    return None

def insert_prices(conn, asset: Dict, df: pd.DataFrame) -> int:
    """Insert price data into database"""
    batch_id = str(uuid4())
    canonical_id = asset["canonical_id"]

    rows = []
    for idx, row in df.iterrows():
        timestamp = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx

        data_str = f"{canonical_id}|{timestamp}|{row['Open']}|{row['High']}|{row['Low']}|{row['Close']}|{row['Volume']}"
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        rows.append((
            str(uuid4()),  # id
            str(uuid4()),  # asset_id (dummy UUID, using canonical_id for join)
            canonical_id,
            timestamp,
            float(row['Open']),
            float(row['High']),
            float(row['Low']),
            float(row['Close']),
            float(row['Volume']),
            'yfinance',
            None,  # staging_id
            data_hash,
            False,  # gap_filled
            False,  # interpolated
            1.0,    # quality_score
            batch_id,
            'STIG'
        ))

    with conn.cursor() as cur:
        insert_sql = """
            INSERT INTO fhq_market.prices (
                id, asset_id, canonical_id, timestamp, open, high, low, close, volume,
                source, staging_id, data_hash, gap_filled, interpolated, quality_score,
                batch_id, canonicalized_by
            ) VALUES %s
            ON CONFLICT (canonical_id, timestamp) DO NOTHING
        """
        execute_values(cur, insert_sql, rows)
        conn.commit()

    return len(rows)

def update_asset_status(conn, asset: Dict, row_count: int):
    """Update asset data quality status"""
    canonical_id = asset["canonical_id"]
    asset_class = asset["asset_class"]

    # Determine thresholds
    if asset_class == "CRYPTO":
        quarantine_threshold = CRYPTO_QUARANTINE
        full_threshold = CRYPTO_FULL_HISTORY
    else:
        quarantine_threshold = EQUITY_FX_QUARANTINE
        full_threshold = EQUITY_FX_FULL_HISTORY

    # Determine status
    if row_count < quarantine_threshold:
        status = 'QUARANTINED'
    elif row_count < full_threshold:
        status = 'SHORT_HISTORY'
    else:
        status = 'FULL_HISTORY'

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_meta.assets
            SET valid_row_count = %s,
                data_quality_status = %s::data_quality_status,
                updated_at = NOW()
            WHERE canonical_id = %s
        """, (row_count, status, canonical_id))
        conn.commit()

    return status

def process_asset(conn, asset: Dict) -> Dict:
    """Process a single asset"""
    canonical_id = asset["canonical_id"]
    ticker = asset["ticker"]
    yf_ticker = get_yfinance_ticker(asset)

    result = {
        "canonical_id": canonical_id,
        "ticker": ticker,
        "yf_ticker": yf_ticker,
        "success": False,
        "rows": 0,
        "status": None,
        "error": None
    }

    try:
        # Fetch data
        end_date = date.today()
        start_date = end_date - timedelta(days=365 * MAX_HISTORY_YEARS)

        df = fetch_prices(yf_ticker, start_date, end_date)

        if df is None or df.empty:
            result["error"] = "No data returned"
            logger.warning(f"[{ticker}] No data returned from yfinance")
            return result

        # Insert data
        rows_inserted = insert_prices(conn, asset, df)

        # Update status
        status = update_asset_status(conn, asset, rows_inserted)

        result["success"] = True
        result["rows"] = rows_inserted
        result["status"] = status

        logger.info(f"[{ticker}] SUCCESS: {rows_inserted} rows, status={status}")

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[{ticker}] FAILED: {e}")

    return result

# =============================================================================
# MAIN
# =============================================================================

def run_scheduled_backfill(limit: int = None):
    """Run the scheduled backfill"""
    logger.info("=" * 70)
    logger.info("IoS-001 SCHEDULED PRICE BACKFILL - ULTRA CONSERVATIVE")
    logger.info("=" * 70)
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Rate limiting: {DELAY_BETWEEN_ASSETS}s between assets, {DELAY_BETWEEN_BATCHES}s between batches of {BATCH_SIZE}")
    logger.info("=" * 70)

    conn = get_connection()

    # Get assets without prices
    assets = get_assets_without_prices(conn, limit)
    total_assets = len(assets)

    logger.info(f"Assets to process: {total_assets}")

    if total_assets == 0:
        logger.info("All assets have price data!")
        return

    results = {
        "started_at": datetime.now().isoformat(),
        "total": total_assets,
        "success": 0,
        "failed": 0,
        "rows_inserted": 0,
        "details": []
    }

    # Process in batches
    for batch_num, i in enumerate(range(0, total_assets, BATCH_SIZE), 1):
        batch = assets[i:i + BATCH_SIZE]
        batch_count = len(batch)

        logger.info(f"\n{'=' * 50}")
        logger.info(f"BATCH {batch_num}/{(total_assets + BATCH_SIZE - 1) // BATCH_SIZE} ({batch_count} assets)")
        logger.info(f"{'=' * 50}")

        for j, asset in enumerate(batch, 1):
            logger.info(f"\n[{j}/{batch_count}] Processing {asset['ticker']} ({asset['asset_class']})")

            result = process_asset(conn, asset)
            results["details"].append(result)

            if result["success"]:
                results["success"] += 1
                results["rows_inserted"] += result["rows"]
            else:
                results["failed"] += 1

            # Delay between assets
            if j < batch_count:
                logger.info(f"Waiting {DELAY_BETWEEN_ASSETS}s before next asset...")
                time.sleep(DELAY_BETWEEN_ASSETS)

        # Delay between batches
        if i + BATCH_SIZE < total_assets:
            logger.info(f"\nBatch complete. Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
            time.sleep(DELAY_BETWEEN_BATCHES)

    results["completed_at"] = datetime.now().isoformat()

    # Save evidence
    evidence_dir = Path(__file__).parent / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    evidence_file = evidence_dir / f"SCHEDULED_BACKFILL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total processed: {total_assets}")
    logger.info(f"Success: {results['success']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Rows inserted: {results['rows_inserted']}")
    logger.info(f"Evidence: {evidence_file}")
    logger.info("=" * 70)

    conn.close()
    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IoS-001 Scheduled Price Backfill")
    parser.add_argument("--limit", type=int, help="Limit number of assets")
    args = parser.parse_args()

    run_scheduled_backfill(limit=args.limit)
