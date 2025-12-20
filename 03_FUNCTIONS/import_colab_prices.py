#!/usr/bin/env python3
"""
IoS-001 COLAB PRICE IMPORTER
============================
Import CSV files downloaded from Google Colab backfill.

Usage:
    python import_colab_prices.py --csv-dir <path-to-csvs>
    python import_colab_prices.py --csv-file <single-csv>
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

log_file = EVIDENCE_DIR / f"colab_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
# TICKER MAPPING
# =============================================================================

def get_canonical_id_from_yf_ticker(yf_ticker: str) -> str:
    """Convert yfinance ticker back to canonical_id"""
    if yf_ticker.endswith("-USD"):
        # Crypto: BTC-USD -> BTC
        return yf_ticker.replace("-USD", "")
    elif yf_ticker.endswith("=X"):
        # FX: EURUSD=X -> EURUSD
        return yf_ticker.replace("=X", "")
    else:
        # Equity: ticker is canonical_id
        return yf_ticker

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
    """Get mapping of canonical_id to asset info"""
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

        # Build yfinance ticker
        if asset_class == "CRYPTO":
            yf_ticker = f"{ticker}-USD"
        elif asset_class == "FX":
            yf_ticker = f"{ticker}=X"
        else:
            yf_ticker = ticker

        mapping[yf_ticker] = {
            "canonical_id": canonical_id,
            "ticker": ticker,
            "asset_class": asset_class,
            "exchange_mic": r[3]
        }

        # Also map by canonical_id for direct lookup
        mapping[canonical_id] = mapping[yf_ticker]

    return mapping

def insert_prices_batch(conn, canonical_id: str, df: pd.DataFrame) -> int:
    """Insert price data for a single asset"""
    if df is None or df.empty:
        return 0

    batch_id = str(uuid4())
    rows = []

    for idx, row in df.iterrows():
        timestamp = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx

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
# CSV PROCESSING
# =============================================================================

def process_csv_file(conn, csv_path: Path, asset_mapping: Dict) -> Dict:
    """Process a single CSV file from Colab output"""
    logger.info(f"Processing: {csv_path.name}")

    results = {
        "file": str(csv_path),
        "tickers_found": 0,
        "tickers_imported": 0,
        "rows_inserted": 0,
        "errors": []
    }

    try:
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    except Exception as e:
        results["errors"].append(f"Failed to read CSV: {e}")
        return results

    # Check if multi-ticker format (multi-level columns)
    if isinstance(df.columns, pd.MultiIndex):
        # Multi-ticker batch file
        tickers = df.columns.get_level_values(0).unique().tolist()
        results["tickers_found"] = len(tickers)

        for ticker in tickers:
            try:
                ticker_df = df[ticker].dropna(subset=['Close'])

                if ticker_df.empty:
                    continue

                # Find canonical_id
                if ticker in asset_mapping:
                    asset = asset_mapping[ticker]
                    canonical_id = asset["canonical_id"]
                    asset_class = asset["asset_class"]
                else:
                    # Try converting
                    canonical_id = get_canonical_id_from_yf_ticker(ticker)
                    if canonical_id in asset_mapping:
                        asset = asset_mapping[canonical_id]
                        asset_class = asset["asset_class"]
                    else:
                        results["errors"].append(f"Unknown ticker: {ticker}")
                        continue

                # Insert prices
                rows = insert_prices_batch(conn, canonical_id, ticker_df)

                if rows > 0:
                    status = update_asset_status(conn, canonical_id, asset_class, rows)
                    logger.info(f"  [{ticker}] {rows} rows, status={status}")
                    results["tickers_imported"] += 1
                    results["rows_inserted"] += rows

            except Exception as e:
                results["errors"].append(f"Error processing {ticker}: {e}")

    else:
        # Single ticker file - try to determine ticker from filename
        filename = csv_path.stem  # e.g., "AAPL_prices" or just ticker
        ticker = filename.replace("_prices", "").upper()
        results["tickers_found"] = 1

        if ticker in asset_mapping:
            asset = asset_mapping[ticker]
            canonical_id = asset["canonical_id"]
            asset_class = asset["asset_class"]

            ticker_df = df.dropna(subset=['Close']) if 'Close' in df.columns else df

            rows = insert_prices_batch(conn, canonical_id, ticker_df)

            if rows > 0:
                status = update_asset_status(conn, canonical_id, asset_class, rows)
                logger.info(f"  [{ticker}] {rows} rows, status={status}")
                results["tickers_imported"] += 1
                results["rows_inserted"] += rows
        else:
            results["errors"].append(f"Unknown ticker from filename: {ticker}")

    return results

# =============================================================================
# MAIN
# =============================================================================

def import_colab_prices(csv_dir: str = None, csv_file: str = None):
    """Import price data from Colab CSV files"""
    logger.info("=" * 70)
    logger.info("IoS-001 COLAB PRICE IMPORTER")
    logger.info("=" * 70)

    conn = get_connection()
    asset_mapping = get_asset_mapping(conn)

    logger.info(f"Loaded {len(asset_mapping) // 2} asset mappings")

    # Find CSV files
    csv_files = []
    if csv_file:
        csv_files = [Path(csv_file)]
    elif csv_dir:
        csv_dir_path = Path(csv_dir)
        csv_files = list(csv_dir_path.glob("*.csv"))
    else:
        logger.error("Please specify --csv-dir or --csv-file")
        return

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

    for csv_path in csv_files:
        file_result = process_csv_file(conn, csv_path, asset_mapping)
        results["file_results"].append(file_result)
        results["total_tickers"] += file_result["tickers_found"]
        results["imported_tickers"] += file_result["tickers_imported"]
        results["total_rows"] += file_result["rows_inserted"]
        results["errors"].extend(file_result["errors"])

    results["completed_at"] = datetime.now().isoformat()

    # Save evidence
    evidence_file = EVIDENCE_DIR / f"COLAB_IMPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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
    parser = argparse.ArgumentParser(description="Import Colab price CSVs")
    parser.add_argument("--csv-dir", help="Directory containing CSV files")
    parser.add_argument("--csv-file", help="Single CSV file to import")
    args = parser.parse_args()

    import_colab_prices(csv_dir=args.csv_dir, csv_file=args.csv_file)
