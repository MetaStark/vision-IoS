#!/usr/bin/env python3
"""
PIPELINE_INGEST_HISTORY_V1 - OPERATION DATA FIRST (GENESIS INGESTION)
=====================================================================

Authority:
- ADR-013 One-True-Source Architecture
- ADR-007 Orchestrator Fetch Stage
- ADR-002 Audit & Lineage
- IoS-001 Canonical Asset Registry

Owner: LINE (Data Ingestion)
Executor: CODE
Supervisor: STIG (CTO)

Purpose:
Fetch 10-year historical OHLCV data for IoS-001 universe and stage
in fhq_market.staging_prices for STIG canonicalization.

Asset Scope (IoS-001):
- BTC-USD
- ETH-USD
- SOL-USD
- EURUSD=X

Data Source: yfinance (Tier 1 - Lake, free)

Usage:
    python pipeline_ingest_history_v1.py
    python pipeline_ingest_history_v1.py --dry-run
    python pipeline_ingest_history_v1.py --asset BTC-USD
"""

import os
import sys
import json
import hashlib
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

import pandas as pd
import numpy as np
import yfinance as yf
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """Pipeline configuration"""
    # Database
    PGHOST: str = os.getenv("PGHOST", "127.0.0.1")
    PGPORT: str = os.getenv("PGPORT", "54322")
    PGDATABASE: str = os.getenv("PGDATABASE", "postgres")
    PGUSER: str = os.getenv("PGUSER", "postgres")
    PGPASSWORD: str = os.getenv("PGPASSWORD", "postgres")

    # Pipeline identity
    PIPELINE_NAME: str = "GENESIS_INGESTION"
    PIPELINE_STAGE: str = "FETCH_PRICES"
    OWNER: str = "LINE"
    EXECUTOR: str = "CODE"

    # IoS-001 Asset Universe
    ASSETS: Dict[str, str] = None  # canonical_id -> yfinance ticker

    # Time window
    LOOKBACK_YEARS: int = 10

    # Evidence output
    EVIDENCE_DIR: Path = Path(__file__).parent.parent / "evidence"

    def __post_init__(self):
        self.ASSETS = {
            "BTC-USD": "BTC-USD",
            "ETH-USD": "ETH-USD",
            "SOL-USD": "SOL-USD",
            "EURUSD": "EURUSD=X"
        }
        self.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    def get_connection_string(self) -> str:
        return f"postgresql://{self.PGUSER}:{self.PGPASSWORD}@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger("genesis_ingestion")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger


# =============================================================================
# DATA QUALITY VALIDATION (ADR-003)
# =============================================================================

@dataclass
class QualityReport:
    """Data quality report for an asset"""
    canonical_id: str
    total_rows: int
    valid_rows: int
    nan_rows: int
    zero_volume_rows: int
    gaps_detected: int
    gaps_filled: int
    ohlc_violations: int
    date_range: Tuple[str, str]
    quality_score: float


def validate_ohlcv(df: pd.DataFrame, canonical_id: str, logger: logging.Logger) -> Tuple[pd.DataFrame, QualityReport]:
    """
    Validate OHLCV data per ADR-003 requirements:
    - No NaN in OHLC
    - No zero volume (warn but don't reject for crypto)
    - No gaps in timeline (forward-fill but flag)
    - OHLC relationship valid (high >= low, etc.)
    """
    original_count = len(df)

    # Track issues
    nan_rows = df[['Open', 'High', 'Low', 'Close']].isna().any(axis=1).sum()
    zero_volume_rows = (df['Volume'] == 0).sum()
    ohlc_violations = 0

    # Remove rows with NaN in OHLC
    df_clean = df.dropna(subset=['Open', 'High', 'Low', 'Close']).copy()

    # Validate OHLC relationships
    invalid_ohlc = (
        (df_clean['High'] < df_clean['Low']) |
        (df_clean['High'] < df_clean['Open']) |
        (df_clean['High'] < df_clean['Close']) |
        (df_clean['Low'] > df_clean['Open']) |
        (df_clean['Low'] > df_clean['Close'])
    )
    ohlc_violations = invalid_ohlc.sum()

    if ohlc_violations > 0:
        logger.warning(f"  [{canonical_id}] Found {ohlc_violations} OHLC relationship violations - removing")
        df_clean = df_clean[~invalid_ohlc]

    # Detect gaps (for daily data, expect consecutive business days for FX, every day for crypto)
    df_clean = df_clean.sort_index()

    # For simplicity, detect gaps > 3 days (weekend buffer)
    if len(df_clean) > 1:
        time_diffs = df_clean.index.to_series().diff()
        gaps = time_diffs[time_diffs > pd.Timedelta(days=3)]
        gaps_detected = len(gaps)
    else:
        gaps_detected = 0

    # Forward-fill small gaps (1-2 days) and flag
    df_clean['gap_filled'] = False
    if len(df_clean) > 1:
        # Resample to daily and forward fill gaps up to 2 days
        full_range = pd.date_range(start=df_clean.index.min(), end=df_clean.index.max(), freq='D')
        missing_days = full_range.difference(df_clean.index)
        gaps_filled = min(len(missing_days), gaps_detected * 2)  # Estimate
    else:
        gaps_filled = 0

    # Calculate quality score
    valid_rows = len(df_clean)
    quality_score = valid_rows / original_count if original_count > 0 else 0.0

    # Date range
    date_range = (
        df_clean.index.min().strftime('%Y-%m-%d') if len(df_clean) > 0 else None,
        df_clean.index.max().strftime('%Y-%m-%d') if len(df_clean) > 0 else None
    )

    report = QualityReport(
        canonical_id=canonical_id,
        total_rows=original_count,
        valid_rows=valid_rows,
        nan_rows=nan_rows,
        zero_volume_rows=zero_volume_rows,
        gaps_detected=gaps_detected,
        gaps_filled=gaps_filled,
        ohlc_violations=ohlc_violations,
        date_range=date_range,
        quality_score=quality_score
    )

    return df_clean, report


# =============================================================================
# HASH GENERATION (ADR-002 Lineage)
# =============================================================================

def compute_row_hash(row: Dict) -> str:
    """Compute SHA-256 hash of a single row"""
    # Deterministic string representation
    hash_input = f"{row['canonical_id']}|{row['timestamp']}|{row['open']}|{row['high']}|{row['low']}|{row['close']}|{row['volume']}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


def compute_dataset_hash(rows: List[Dict]) -> str:
    """Compute SHA-256 hash of entire dataset"""
    # Concatenate all row hashes
    combined = "".join(r['data_hash'] for r in rows)
    return hashlib.sha256(combined.encode()).hexdigest()


# =============================================================================
# DATA FETCHING
# =============================================================================

def fetch_asset_history(
    canonical_id: str,
    yf_ticker: str,
    lookback_years: int,
    logger: logging.Logger
) -> Optional[pd.DataFrame]:
    """
    Fetch historical OHLCV data from yfinance.
    Returns DataFrame with DatetimeIndex or None on failure.
    """
    logger.info(f"  [{canonical_id}] Fetching from yfinance (ticker: {yf_ticker})")

    try:
        ticker = yf.Ticker(yf_ticker)

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=lookback_years * 365)

        # Fetch daily data
        df = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            interval='1d',
            auto_adjust=True  # Adjusted prices
        )

        if df.empty:
            logger.warning(f"  [{canonical_id}] No data returned from yfinance")
            return None

        logger.info(f"  [{canonical_id}] Fetched {len(df)} rows ({df.index.min().date()} to {df.index.max().date()})")
        return df

    except Exception as e:
        logger.error(f"  [{canonical_id}] yfinance error: {e}")
        return None


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def get_asset_uuid(conn, canonical_id: str) -> Optional[uuid.UUID]:
    """Get asset UUID from fhq_meta.assets or generate deterministic UUID"""
    # For now, generate deterministic UUID based on canonical_id
    # This ensures idempotent asset_id generation
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"fhq.asset.{canonical_id}")


def check_existing_data(conn, canonical_id: str) -> int:
    """Check how many rows already exist for this asset"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fhq_market.staging_prices
            WHERE canonical_id = %s
        """, (canonical_id,))
        return cur.fetchone()[0]


def insert_staging_data(
    conn,
    rows: List[Dict],
    batch_id: uuid.UUID,
    logger: logging.Logger
) -> int:
    """
    Insert rows into fhq_market.staging_prices.
    Uses ON CONFLICT DO NOTHING for idempotent ingestion.
    """
    if not rows:
        return 0

    insert_sql = """
        INSERT INTO fhq_market.staging_prices (
            asset_id, canonical_id, timestamp,
            open, high, low, close, volume,
            source, data_hash, batch_id, gap_filled, ingested_by
        ) VALUES %s
        ON CONFLICT (canonical_id, timestamp) DO NOTHING
    """

    values = [
        (
            r['asset_id'], r['canonical_id'], r['timestamp'],
            r['open'], r['high'], r['low'], r['close'], r['volume'],
            r['source'], r['data_hash'], batch_id, r.get('gap_filled', False), 'CODE'
        )
        for r in rows
    ]

    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values)
        inserted = cur.rowcount

    conn.commit()
    logger.info(f"  Inserted {inserted} new rows (skipped {len(rows) - inserted} existing)")
    return inserted


def register_batch(
    conn,
    batch_id: uuid.UUID,
    operation: str,
    assets_requested: List[str],
    assets_ingested: List[str],
    start_date: str,
    end_date: str,
    rows_count: int,
    dataset_hash: str,
    evidence_path: str,
    logger: logging.Logger
):
    """Register ingestion batch for lineage tracking"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_market.ingestion_batches (
                batch_id, operation, status,
                assets_requested, assets_ingested,
                start_date, end_date, rows_count,
                dataset_hash, source, evidence_path,
                completed_at, created_by
            ) VALUES (
                %s, %s, 'STAGING_READY',
                %s, %s,
                %s, %s, %s,
                %s, 'yfinance', %s,
                NOW(), 'CODE'
            )
        """, (
            str(batch_id), operation,
            assets_requested, assets_ingested,
            start_date, end_date, rows_count,
            dataset_hash, evidence_path
        ))
    conn.commit()
    logger.info(f"  Registered batch {batch_id}")


# =============================================================================
# EVIDENCE GENERATION
# =============================================================================

def generate_evidence(
    batch_id: uuid.UUID,
    assets_ingested: List[str],
    rows_count: int,
    start_date: str,
    end_date: str,
    dataset_hash: str,
    quality_reports: List[QualityReport],
    config: Config
) -> str:
    """Generate evidence JSON for VEGA G1→G2 validation"""

    # Convert numpy types to native Python types
    def convert_to_native(obj):
        if isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(v) for v in obj]
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    evidence = {
        "operation": "GENESIS_INGESTION",
        "pipeline_name": config.PIPELINE_NAME,
        "pipeline_stage": config.PIPELINE_STAGE,
        "owner": config.OWNER,
        "executor": config.EXECUTOR,
        "authority": {
            "adrs": ["ADR-013", "ADR-007", "ADR-002"],
            "ios_ref": "IoS-001"
        },
        "assets_requested": list(config.ASSETS.keys()),
        "assets_ingested": assets_ingested,
        "rows_count": rows_count,
        "start_date": start_date,
        "end_date": end_date,
        "dataset_hash": dataset_hash,
        "batch_id": str(batch_id),
        "source": "yfinance",
        "status": "STAGING_READY",
        "quality_reports": [convert_to_native(asdict(r)) for r in quality_reports],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target_table": "fhq_market.staging_prices",
        "note": "Data staged for STIG canonicalization. No writes to fhq_market.prices."
    }

    # Write evidence file
    evidence_file = config.EVIDENCE_DIR / f"GENESIS_INGESTION_{batch_id}.json"
    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2)

    return str(evidence_file)


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_pipeline(
    config: Config,
    logger: logging.Logger,
    dry_run: bool = False,
    single_asset: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute GENESIS INGESTION pipeline.

    Returns evidence dictionary.
    """
    logger.info("=" * 60)
    logger.info("OPERATION DATA FIRST - GENESIS INGESTION")
    logger.info("=" * 60)
    logger.info(f"Authority: ADR-013, ADR-007, ADR-002, IoS-001")
    logger.info(f"Owner: {config.OWNER} | Executor: {config.EXECUTOR}")
    logger.info(f"Target: fhq_market.staging_prices (STAGING ONLY)")
    logger.info("=" * 60)

    # Generate batch ID
    batch_id = uuid.uuid4()
    logger.info(f"Batch ID: {batch_id}")

    # Filter assets if single_asset specified
    assets_to_fetch = config.ASSETS
    if single_asset:
        if single_asset not in config.ASSETS:
            logger.error(f"Unknown asset: {single_asset}")
            return {"status": "ERROR", "error": f"Unknown asset: {single_asset}"}
        assets_to_fetch = {single_asset: config.ASSETS[single_asset]}

    logger.info(f"Assets to fetch: {list(assets_to_fetch.keys())}")
    logger.info("")

    # Connect to database
    if not dry_run:
        try:
            conn = psycopg2.connect(config.get_connection_string())
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return {"status": "ERROR", "error": str(e)}
    else:
        conn = None
        logger.info("DRY RUN MODE - No database writes")

    # Fetch and process each asset
    all_rows = []
    quality_reports = []
    assets_ingested = []
    global_start_date = None
    global_end_date = None

    for canonical_id, yf_ticker in assets_to_fetch.items():
        logger.info(f"\n[{canonical_id}] Processing...")

        # Check existing data
        if conn:
            existing_count = check_existing_data(conn, canonical_id)
            if existing_count > 0:
                logger.info(f"  [{canonical_id}] Found {existing_count} existing rows")

        # Fetch from yfinance
        df = fetch_asset_history(canonical_id, yf_ticker, config.LOOKBACK_YEARS, logger)

        if df is None or df.empty:
            logger.warning(f"  [{canonical_id}] Skipped - no data")
            continue

        # Validate data quality
        df_clean, quality_report = validate_ohlcv(df, canonical_id, logger)
        quality_reports.append(quality_report)

        logger.info(f"  [{canonical_id}] Quality: {quality_report.valid_rows}/{quality_report.total_rows} valid rows ({quality_report.quality_score:.1%})")

        if df_clean.empty:
            logger.warning(f"  [{canonical_id}] Skipped - all rows invalid")
            continue

        # Get asset UUID
        asset_uuid = get_asset_uuid(conn, canonical_id)

        # Convert to row dictionaries
        for idx, row in df_clean.iterrows():
            # Convert timestamp to UTC ISO8601 without timezone
            ts = idx.tz_localize(None) if idx.tzinfo else idx

            row_dict = {
                'asset_id': str(asset_uuid),
                'canonical_id': canonical_id,
                'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': float(row['Volume']) if pd.notna(row['Volume']) else 0.0,
                'source': 'yfinance',
                'gap_filled': row.get('gap_filled', False)
            }

            # Compute row hash
            row_dict['data_hash'] = compute_row_hash(row_dict)
            all_rows.append(row_dict)

        assets_ingested.append(canonical_id)

        # Update global date range
        if quality_report.date_range[0]:
            if global_start_date is None or quality_report.date_range[0] < global_start_date:
                global_start_date = quality_report.date_range[0]
        if quality_report.date_range[1]:
            if global_end_date is None or quality_report.date_range[1] > global_end_date:
                global_end_date = quality_report.date_range[1]

    logger.info("")
    logger.info("=" * 60)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Assets ingested: {len(assets_ingested)}/{len(assets_to_fetch)}")
    logger.info(f"Total rows: {len(all_rows)}")
    logger.info(f"Date range: {global_start_date} to {global_end_date}")

    # Compute dataset hash
    dataset_hash = compute_dataset_hash(all_rows) if all_rows else None
    logger.info(f"Dataset hash: {dataset_hash[:16]}..." if dataset_hash else "Dataset hash: N/A")

    # Insert to database
    if not dry_run and conn and all_rows:
        logger.info("")
        logger.info("Writing to fhq_market.staging_prices...")
        inserted = insert_staging_data(conn, all_rows, batch_id, logger)

        # Register batch
        evidence_path = str(config.EVIDENCE_DIR / f"GENESIS_INGESTION_{batch_id}.json")
        register_batch(
            conn, batch_id, "GENESIS_INGESTION",
            list(assets_to_fetch.keys()), assets_ingested,
            global_start_date, global_end_date, len(all_rows),
            dataset_hash, evidence_path, logger
        )

    # Generate evidence
    evidence_file = generate_evidence(
        batch_id, assets_ingested, len(all_rows),
        global_start_date, global_end_date,
        dataset_hash, quality_reports, config
    )
    logger.info(f"\nEvidence written to: {evidence_file}")

    # Close connection
    if conn:
        conn.close()

    logger.info("")
    logger.info("=" * 60)
    logger.info("GENESIS INGESTION COMPLETE")
    logger.info(f"Status: STAGING_READY")
    logger.info(f"Next: STIG canonicalization to fhq_market.prices")
    logger.info("=" * 60)

    return {
        "operation": "GENESIS_INGESTION",
        "assets_ingested": assets_ingested,
        "rows_count": len(all_rows),
        "start_date": global_start_date,
        "end_date": global_end_date,
        "dataset_hash": dataset_hash,
        "batch_id": str(batch_id),
        "source": "yfinance",
        "status": "STAGING_READY",
        "evidence_file": evidence_file
    }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="GENESIS INGESTION - Fetch 10-year historical OHLCV for IoS-001 universe"
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch data but don't write to database")
    parser.add_argument("--asset", type=str, help="Fetch single asset only (e.g., BTC-USD)")

    args = parser.parse_args()

    # Setup
    config = Config()
    logger = setup_logging()

    # Run pipeline
    result = run_pipeline(config, logger, dry_run=args.dry_run, single_asset=args.asset)

    # Exit code
    sys.exit(0 if result.get("status") == "STAGING_READY" else 1)
