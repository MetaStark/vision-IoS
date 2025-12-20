#!/usr/bin/env python3
"""
IoS-001 COLAB PRICE IMPORTER V2
===============================
Import CSV files downloaded from Google Colab backfill.
Handles yfinance batch download format with multi-level columns.

Usage:
    python import_colab_prices_v2.py --csv-dir <path-to-csvs>
"""

import os
import sys
import json
import hashlib
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import pandas as pd
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

# Iron Curtain thresholds
EQUITY_FX_QUARANTINE = 252
EQUITY_FX_FULL_HISTORY = 1260
CRYPTO_QUARANTINE = 365
CRYPTO_FULL_HISTORY = 1825

# Setup directories
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# =============================================================================
# LOGGING
# =============================================================================

log_file = EVIDENCE_DIR / f"colab_import_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

def get_asset_mapping(conn) -> Dict[str, Dict]:
    """Get mapping of ticker to asset info"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT canonical_id, ticker, asset_class, exchange_mic
            FROM fhq_meta.assets
            WHERE active_flag = true
        """)
        rows = cur.fetchall()

    mapping = {}
    for r in rows:
        canonical_id = r[0]
        ticker = r[1]
        asset_class = r[2]

        # Store by ticker as it appears in database
        mapping[ticker] = {
            "canonical_id": canonical_id,
            "ticker": ticker,
            "asset_class": asset_class,
            "exchange_mic": r[3]
        }

        # Also map by variants
        # For crypto: BTC-USD -> BTC-USD (direct match)
        # For FX: EURUSD=X -> EURUSD=X (direct match)
        # For equity with suffix: SAP.DE -> SAP.DE (direct match)

    return mapping

def insert_prices_batch(conn, canonical_id: str, df: pd.DataFrame) -> int:
    """Insert price data for a single asset"""
    if df is None or df.empty:
        return 0

    batch_id = str(uuid4())
    rows = []

    for idx, row in df.iterrows():
        try:
            # Handle different date formats
            if isinstance(idx, str):
                timestamp = pd.to_datetime(idx)
            else:
                timestamp = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
        except:
            continue

        try:
            open_val = float(row['Open']) if pd.notna(row.get('Open')) else None
            high_val = float(row['High']) if pd.notna(row.get('High')) else None
            low_val = float(row['Low']) if pd.notna(row.get('Low')) else None
            close_val = float(row['Close']) if pd.notna(row.get('Close')) else None
            volume_val = float(row['Volume']) if pd.notna(row.get('Volume')) else 0
        except (KeyError, TypeError, ValueError):
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
            'yfinance_colab',
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
    """Update asset data quality status based on row count"""
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
# CSV PROCESSING - YFINANCE BATCH FORMAT
# =============================================================================

def process_yfinance_batch_csv(conn, csv_path: Path, asset_mapping: Dict) -> Dict:
    """
    Process yfinance batch download CSV format.

    Format:
    Row 0: Ticker names repeated for each column (Ticker, NEE, NEE, NEE, ... TXN, TXN, ...)
    Row 1: Price types (Price, Open, High, Low, Close, Adj Close, Volume, Open, High, ...)
    Row 2: Date (empty header)
    Row 3+: Date, values...
    """
    logger.info(f"Processing: {csv_path.name}")

    results = {
        "file": str(csv_path),
        "tickers_found": 0,
        "tickers_imported": 0,
        "rows_inserted": 0,
        "errors": []
    }

    try:
        # Read the raw CSV to understand structure
        raw_df = pd.read_csv(csv_path, header=None, nrows=3)

        # Row 0 has tickers, row 1 has price types
        ticker_row = raw_df.iloc[0].tolist()
        price_type_row = raw_df.iloc[1].tolist()

        # Find unique tickers (skip first column which is "Ticker" or "Date")
        tickers = []
        ticker_cols = {}  # ticker -> {Open: col_idx, High: col_idx, ...}

        current_ticker = None
        for i, (ticker, price_type) in enumerate(zip(ticker_row, price_type_row)):
            if i == 0:
                continue  # Skip first column
            if pd.notna(ticker) and ticker != current_ticker:
                current_ticker = ticker
                if current_ticker not in ticker_cols:
                    ticker_cols[current_ticker] = {}
                    tickers.append(current_ticker)
            if pd.notna(price_type) and current_ticker:
                ticker_cols[current_ticker][price_type] = i

        results["tickers_found"] = len(tickers)
        logger.info(f"  Found {len(tickers)} tickers in file")

        # Now read the data portion (skip first 2 header rows)
        data_df = pd.read_csv(csv_path, skiprows=2, header=None)

        # Process each ticker
        for ticker in tickers:
            cols = ticker_cols.get(ticker, {})
            if 'Close' not in cols:
                results["errors"].append(f"No Close column for {ticker}")
                continue

            # Build ticker dataframe
            ticker_data = []
            for _, row in data_df.iterrows():
                date_val = row[0]
                if pd.isna(date_val) or date_val == 'Date':
                    continue

                try:
                    record = {
                        'Date': pd.to_datetime(date_val),
                        'Open': float(row[cols['Open']]) if 'Open' in cols and pd.notna(row[cols['Open']]) else None,
                        'High': float(row[cols['High']]) if 'High' in cols and pd.notna(row[cols['High']]) else None,
                        'Low': float(row[cols['Low']]) if 'Low' in cols and pd.notna(row[cols['Low']]) else None,
                        'Close': float(row[cols['Close']]) if pd.notna(row[cols['Close']]) else None,
                        'Volume': float(row[cols['Volume']]) if 'Volume' in cols and pd.notna(row[cols['Volume']]) else 0
                    }
                    if record['Close'] and record['Close'] > 0:
                        ticker_data.append(record)
                except (ValueError, TypeError):
                    continue

            if not ticker_data:
                results["errors"].append(f"No valid data for {ticker}")
                continue

            ticker_df = pd.DataFrame(ticker_data)
            ticker_df.set_index('Date', inplace=True)

            # Find canonical_id
            if ticker in asset_mapping:
                asset = asset_mapping[ticker]
                canonical_id = asset["canonical_id"]
                asset_class = asset["asset_class"]
            else:
                results["errors"].append(f"Unknown ticker: {ticker}")
                continue

            # Insert prices
            rows = insert_prices_batch(conn, canonical_id, ticker_df)

            if rows > 0:
                status = update_asset_status(conn, canonical_id, asset_class, rows)
                logger.info(f"    [{ticker}] {rows} rows -> {status}")
                results["tickers_imported"] += 1
                results["rows_inserted"] += rows
            else:
                results["errors"].append(f"No rows inserted for {ticker}")

    except Exception as e:
        results["errors"].append(f"Error processing file: {e}")
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

    return results

# =============================================================================
# MAIN
# =============================================================================

def import_colab_prices(csv_dir: str):
    """Import price data from Colab CSV files"""
    logger.info("=" * 70)
    logger.info("IoS-001 COLAB PRICE IMPORTER V2")
    logger.info("=" * 70)

    conn = get_connection()
    asset_mapping = get_asset_mapping(conn)

    logger.info(f"Loaded {len(asset_mapping)} asset mappings")

    # Find CSV files
    csv_dir_path = Path(csv_dir)
    csv_files = list(csv_dir_path.glob("*.csv"))

    logger.info(f"Found {len(csv_files)} CSV files to process")

    results = {
        "started_at": datetime.now().isoformat(),
        "csv_files": len(csv_files),
        "total_tickers": 0,
        "imported_tickers": 0,
        "total_rows": 0,
        "file_results": [],
        "errors": []
    }

    for csv_path in sorted(csv_files):
        file_result = process_yfinance_batch_csv(conn, csv_path, asset_mapping)
        results["file_results"].append(file_result)
        results["total_tickers"] += file_result["tickers_found"]
        results["imported_tickers"] += file_result["tickers_imported"]
        results["total_rows"] += file_result["rows_inserted"]
        results["errors"].extend(file_result["errors"])

    results["completed_at"] = datetime.now().isoformat()

    # Save evidence
    evidence_file = EVIDENCE_DIR / f"COLAB_IMPORT_V2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("IMPORT COMPLETE")
    logger.info("=" * 70)
    logger.info(f"CSV files processed: {len(csv_files)}")
    logger.info(f"Tickers found: {results['total_tickers']}")
    logger.info(f"Tickers imported: {results['imported_tickers']}")
    logger.info(f"Total rows inserted: {results['total_rows']}")
    logger.info(f"Errors: {len(results['errors'])}")
    logger.info(f"Evidence: {evidence_file}")
    logger.info("=" * 70)

    conn.close()
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Colab price CSVs V2")
    parser.add_argument("--csv-dir", required=True, help="Directory containing CSV files")
    args = parser.parse_args()

    import_colab_prices(csv_dir=args.csv_dir)
