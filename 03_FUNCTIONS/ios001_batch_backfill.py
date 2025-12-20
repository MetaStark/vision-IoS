#!/usr/bin/env python3
"""
IoS-001 BATCH PRICE BACKFILL
============================
CEO DIRECTIVE: Smart yfinance usage per best practices.

Key Insights from research:
1. ONE BIG REQUEST is less likely to trigger rate limit than many small ones
2. Use requests_cache for caching
3. Use custom session with proper headers
4. Batch multiple tickers in single yf.download() call

Strategy:
- Download ALL tickers in one yf.download() call (or batches of 50)
- Use requests_cache to avoid re-fetching
- Process results after download completes

Sources:
- https://github.com/ranaroussi/yfinance/issues/2422
- https://blog.ni18.in/how-to-fix-the-yfinance-429-client-error-too-many-requests/
"""

import os
import sys
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import pandas as pd
import yfinance as yf
import requests
import requests_cache
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

PGHOST = os.getenv("PGHOST", "127.0.0.1")
PGPORT = os.getenv("PGPORT", "54322")
PGDATABASE = os.getenv("PGDATABASE", "postgres")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

# Batch settings - ONE big request is better than many small ones
BATCH_SIZE = 50  # Yahoo can handle ~50 tickers in one request
DELAY_BETWEEN_BATCHES = 60  # 1 minute between batches
MAX_HISTORY_YEARS = 10

# Iron Curtain thresholds
EQUITY_FX_QUARANTINE = 252
EQUITY_FX_FULL_HISTORY = 1260
CRYPTO_QUARANTINE = 365
CRYPTO_FULL_HISTORY = 1825

# Setup cache directory
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# =============================================================================
# LOGGING
# =============================================================================

log_file = EVIDENCE_DIR / f"batch_backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# CACHED SESSION SETUP
# =============================================================================

def get_cached_session():
    """Create a cached session with proper headers"""
    # Install cache - expires after 24 hours
    cache_file = str(CACHE_DIR / "yfinance_cache")
    session = requests_cache.CachedSession(
        cache_file,
        backend='sqlite',
        expire_after=timedelta(hours=24),
        allowable_codes=[200],
        allowable_methods=['GET']
    )

    # Add proper headers to look like browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    })

    return session

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
                    WHEN 'EQUITY' THEN 1
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

def insert_prices_batch(conn, canonical_id: str, df: pd.DataFrame) -> int:
    """Insert price data for a single asset"""
    if df is None or df.empty:
        return 0

    batch_id = str(uuid4())
    rows = []

    for idx, row in df.iterrows():
        timestamp = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx

        # Handle multi-level columns from batch download
        try:
            open_val = float(row['Open']) if not pd.isna(row['Open']) else None
            high_val = float(row['High']) if not pd.isna(row['High']) else None
            low_val = float(row['Low']) if not pd.isna(row['Low']) else None
            close_val = float(row['Close']) if not pd.isna(row['Close']) else None
            volume_val = float(row['Volume']) if not pd.isna(row['Volume']) else 0
        except (KeyError, TypeError):
            continue

        if close_val is None or close_val <= 0:
            continue
        if open_val is None or open_val <= 0:
            open_val = close_val
        if high_val is None or high_val <= 0:
            high_val = max(open_val, close_val)
        if low_val is None or low_val <= 0:
            low_val = min(open_val, close_val)

        data_str = f"{canonical_id}|{timestamp}|{open_val}|{high_val}|{low_val}|{close_val}|{volume_val}"
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        rows.append((
            str(uuid4()),
            str(uuid4()),
            canonical_id,
            timestamp,
            open_val,
            high_val,
            low_val,
            close_val,
            volume_val,
            'yfinance',
            None,
            data_hash,
            False,
            False,
            1.0,
            batch_id,
            'STIG'
        ))

    if not rows:
        return 0

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

def update_asset_status(conn, canonical_id: str, asset_class: str, row_count: int) -> str:
    """Update asset data quality status"""
    if asset_class == "CRYPTO":
        quarantine_threshold = CRYPTO_QUARANTINE
        full_threshold = CRYPTO_FULL_HISTORY
    else:
        quarantine_threshold = EQUITY_FX_QUARANTINE
        full_threshold = EQUITY_FX_FULL_HISTORY

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

# =============================================================================
# BATCH DOWNLOAD
# =============================================================================

def download_batch(tickers: List[str], session, start_date: date, end_date: date) -> Optional[pd.DataFrame]:
    """
    Download multiple tickers in ONE request.
    This is the key insight - batch downloads are less likely to trigger rate limits!
    """
    ticker_string = " ".join(tickers)
    logger.info(f"Downloading {len(tickers)} tickers in single batch...")

    try:
        df = yf.download(
            ticker_string,
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            interval='1d',
            auto_adjust=False,
            group_by='ticker',
            progress=True,
            threads=False,  # Single thread to avoid rate limits
            session=session
        )

        if df is None or df.empty:
            logger.warning("Empty response from batch download")
            return None

        return df

    except Exception as e:
        logger.error(f"Batch download failed: {e}")
        return None

def extract_ticker_data(batch_df: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
    """Extract single ticker data from batch download result"""
    try:
        if batch_df is None:
            return None

        # Check if multi-ticker result (has multi-level columns)
        if isinstance(batch_df.columns, pd.MultiIndex):
            if ticker in batch_df.columns.get_level_values(0):
                ticker_df = batch_df[ticker].copy()
                return ticker_df.dropna(subset=['Close'])
            return None
        else:
            # Single ticker result
            return batch_df.dropna(subset=['Close'])

    except Exception as e:
        logger.debug(f"Error extracting {ticker}: {e}")
        return None

# =============================================================================
# MAIN
# =============================================================================

def run_batch_backfill(limit: int = None, batch_size: int = BATCH_SIZE):
    """Run the batch backfill"""
    logger.info("=" * 70)
    logger.info("IoS-001 BATCH PRICE BACKFILL")
    logger.info("=" * 70)
    logger.info(f"Strategy: Download {batch_size} tickers per yf.download() call")
    logger.info(f"Cache: SQLite at {CACHE_DIR}")
    logger.info("=" * 70)

    conn = get_connection()
    session = get_cached_session()

    # Get assets without prices
    assets = get_assets_without_prices(conn, limit)
    total_assets = len(assets)

    logger.info(f"Assets to process: {total_assets}")

    if total_assets == 0:
        logger.info("All assets have price data!")
        return

    # Build ticker mapping
    ticker_to_asset = {}
    for asset in assets:
        yf_ticker = get_yfinance_ticker(asset)
        ticker_to_asset[yf_ticker] = asset

    all_tickers = list(ticker_to_asset.keys())

    results = {
        "started_at": datetime.now().isoformat(),
        "total": total_assets,
        "success": 0,
        "failed": 0,
        "rows_inserted": 0,
        "details": []
    }

    # Date range
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * MAX_HISTORY_YEARS)

    # Process in batches
    num_batches = (len(all_tickers) + batch_size - 1) // batch_size

    for batch_num, i in enumerate(range(0, len(all_tickers), batch_size), 1):
        batch_tickers = all_tickers[i:i + batch_size]

        logger.info(f"\n{'=' * 50}")
        logger.info(f"BATCH {batch_num}/{num_batches} ({len(batch_tickers)} tickers)")
        logger.info(f"Tickers: {', '.join(batch_tickers[:5])}{'...' if len(batch_tickers) > 5 else ''}")
        logger.info(f"{'=' * 50}")

        # Download batch
        batch_df = download_batch(batch_tickers, session, start_date, end_date)

        if batch_df is None:
            logger.error("Batch download failed completely")
            for yf_ticker in batch_tickers:
                results["failed"] += 1
                results["details"].append({
                    "ticker": yf_ticker,
                    "success": False,
                    "error": "Batch download failed"
                })
            continue

        # Process each ticker from the batch
        for yf_ticker in batch_tickers:
            asset = ticker_to_asset[yf_ticker]
            canonical_id = asset["canonical_id"]

            # Extract this ticker's data
            ticker_df = extract_ticker_data(batch_df, yf_ticker)

            if ticker_df is None or ticker_df.empty:
                logger.warning(f"  [{asset['ticker']}] No data")
                results["failed"] += 1
                results["details"].append({
                    "canonical_id": canonical_id,
                    "ticker": asset["ticker"],
                    "yf_ticker": yf_ticker,
                    "success": False,
                    "error": "No data returned"
                })
                continue

            # Insert data
            rows_inserted = insert_prices_batch(conn, canonical_id, ticker_df)

            if rows_inserted > 0:
                # Update status
                status = update_asset_status(conn, canonical_id, asset["asset_class"], rows_inserted)

                logger.info(f"  [{asset['ticker']}] {rows_inserted} rows, status={status}")
                results["success"] += 1
                results["rows_inserted"] += rows_inserted
                results["details"].append({
                    "canonical_id": canonical_id,
                    "ticker": asset["ticker"],
                    "yf_ticker": yf_ticker,
                    "success": True,
                    "rows": rows_inserted,
                    "status": status
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "canonical_id": canonical_id,
                    "ticker": asset["ticker"],
                    "yf_ticker": yf_ticker,
                    "success": False,
                    "error": "No valid rows"
                })

        # Delay between batches
        if i + batch_size < len(all_tickers):
            logger.info(f"\nBatch complete. Waiting {DELAY_BETWEEN_BATCHES}s...")
            time.sleep(DELAY_BETWEEN_BATCHES)

    results["completed_at"] = datetime.now().isoformat()

    # Save evidence
    evidence_file = EVIDENCE_DIR / f"BATCH_BACKFILL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total: {total_assets}")
    logger.info(f"Success: {results['success']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Rows inserted: {results['rows_inserted']}")
    logger.info(f"Evidence: {evidence_file}")
    logger.info("=" * 70)

    conn.close()
    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IoS-001 Batch Price Backfill")
    parser.add_argument("--limit", type=int, help="Limit number of assets")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Tickers per batch")
    args = parser.parse_args()

    run_batch_backfill(limit=args.limit, batch_size=args.batch_size)
