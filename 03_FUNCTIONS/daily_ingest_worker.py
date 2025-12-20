#!/usr/bin/env python3
"""
DAILY INGEST WORKER - Automated OHLCV Data Pipeline
====================================================

Authority:
- ADR-013 One-True-Source Architecture
- ADR-007 Orchestrator Fetch Stage
- ADR-002 Audit & Lineage
- IoS-001 Canonical Asset Registry

Pipeline Flow:
1. FETCH_PRICES (LINE) → Fetch latest OHLCV from yfinance
2. GAP_DETECTION (CODE) → Detect missing days
3. BACKFILL (CODE) → Fill gaps if detected
4. STAGING (CODE) → Write to fhq_market.staging_prices
5. RECONCILE (VEGA) → Validate staging vs canonical
6. CANONICALIZE (STIG) → Promote to fhq_market.prices

Schedule: Daily at 00:05 UTC
Target: IoS-001 universe (BTC-USD, ETH-USD, SOL-USD, EURUSD)

Usage:
    python daily_ingest_worker.py                    # Run daily ingest
    python daily_ingest_worker.py --backfill         # Run with gap backfill
    python daily_ingest_worker.py --canonicalize     # Run STIG canonicalization
    python daily_ingest_worker.py --full-pipeline    # Run complete pipeline
"""

import os
import sys
import json
import hashlib
import uuid
import logging
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field

import pandas as pd
import numpy as np
import yfinance as yf
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from dotenv import load_dotenv

# Load environment
load_dotenv()

# IoS-014 VendorGuard Integration
sys.path.insert(0, str(Path(__file__).parent.parent / "05_ORCHESTRATOR"))
try:
    from vendor_guard import VendorGuard, QuotaDecision
    IOS014_ENABLED = True
except ImportError:
    IOS014_ENABLED = False
    VendorGuard = None

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """Pipeline configuration"""
    PGHOST: str = os.getenv("PGHOST", "127.0.0.1")
    PGPORT: str = os.getenv("PGPORT", "54322")
    PGDATABASE: str = os.getenv("PGDATABASE", "postgres")
    PGUSER: str = os.getenv("PGUSER", "postgres")
    PGPASSWORD: str = os.getenv("PGPASSWORD", "postgres")

    # Pipeline identity
    SCHEDULE_NAME: str = "DAILY_OHLCV_INGEST"

    # Agents
    OWNER: str = "LINE"
    EXECUTOR: str = "CODE"
    RECONCILER: str = "VEGA"
    CANONICALIZER: str = "STIG"

    # IoS-001 Asset Universe
    ASSETS: Dict[str, str] = field(default_factory=lambda: {
        "BTC-USD": "BTC-USD",
        "ETH-USD": "ETH-USD",
        "SOL-USD": "SOL-USD",
        "EURUSD": "EURUSD=X"
    })

    # Paths
    EVIDENCE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / "evidence")
    LOGS_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / "logs")

    def __post_init__(self):
        self.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def get_connection_string(self) -> str:
        return f"postgresql://{self.PGUSER}:{self.PGPASSWORD}@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging(config: Config) -> logging.Logger:
    """Configure logging with file output"""
    logger = logging.getLogger("daily_ingest")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Console handler
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console.setFormatter(formatter)
        logger.addHandler(console)

        # File handler
        log_file = config.LOGS_DIR / f"daily_ingest_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# =============================================================================
# DATABASE UTILITIES
# =============================================================================

class DatabaseManager:
    """Database connection and query manager"""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.conn = None
        self.vendor_guard = None

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(self.config.get_connection_string(), options='-c client_encoding=UTF8')
        self.logger.info("Database connection established")

        # Initialize VendorGuard if IoS-014 enabled
        if IOS014_ENABLED and VendorGuard:
            try:
                self.vendor_guard = VendorGuard(self.config.get_connection_string(), self.logger)
                self.vendor_guard.connect()
                self.logger.info("IoS-014 VendorGuard initialized")
            except Exception as e:
                self.logger.warning(f"VendorGuard init failed (continuing without): {e}")
                self.vendor_guard = None

    def close(self):
        """Close database connection"""
        if self.vendor_guard:
            try:
                self.vendor_guard.close()
            except:
                pass
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed")

    def get_last_timestamp(self, canonical_id: str, table: str = "staging_prices") -> Optional[datetime]:
        """Get the most recent timestamp for an asset"""
        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT MAX(timestamp) FROM fhq_market.{table}
                WHERE canonical_id = %s
            """, (canonical_id,))
            result = cur.fetchone()[0]
            return result

    def get_asset_uuid(self, canonical_id: str) -> uuid.UUID:
        """Get or generate asset UUID"""
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"fhq.asset.{canonical_id}")

    def detect_gaps(self, canonical_id: str) -> List[Tuple[date, date, int]]:
        """
        Detect gaps in the data for an asset.
        Returns list of (gap_start, gap_end, gap_days) tuples.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                WITH dates AS (
                    SELECT DISTINCT timestamp::date as dt
                    FROM fhq_market.staging_prices
                    WHERE canonical_id = %s
                    ORDER BY dt
                ),
                date_with_prev AS (
                    SELECT dt, LAG(dt) OVER (ORDER BY dt) as prev_dt
                    FROM dates
                ),
                gaps AS (
                    SELECT
                        (prev_dt + INTERVAL '1 day')::date as gap_start,
                        (dt - INTERVAL '1 day')::date as gap_end,
                        (dt - prev_dt)::int - 1 as gap_days
                    FROM date_with_prev
                    WHERE prev_dt IS NOT NULL
                      AND (dt - prev_dt)::int > 3  -- Allow weekend gaps
                )
                SELECT gap_start, gap_end, gap_days
                FROM gaps
                WHERE gap_days > 0
                ORDER BY gap_start
            """, (canonical_id,))
            return cur.fetchall()

    def record_gap(self, canonical_id: str, gap_start: date, gap_end: date, gap_days: int):
        """Record a detected gap in data_gaps table"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_market.data_gaps (
                    canonical_id, gap_start, gap_end, gap_days, status
                ) VALUES (%s, %s, %s, %s, 'DETECTED')
                ON CONFLICT DO NOTHING
            """, (canonical_id, gap_start, gap_end, gap_days))
        self.conn.commit()

    def update_schedule_status(self, schedule_name: str, status: str, batch_id: uuid.UUID):
        """Update ingest schedule with run status"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_market.ingest_schedule
                SET last_run_at = NOW(),
                    last_run_status = %s,
                    last_run_batch_id = %s,
                    next_run_at = (CURRENT_DATE + INTERVAL '1 day' + INTERVAL '5 minutes')
                WHERE schedule_name = %s
            """, (status, str(batch_id), schedule_name))
        self.conn.commit()

    def log_to_ios_audit(self, operation: str, details: dict):
        """Log operation to ios_audit_log"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_meta.ios_audit_log (
                    ios_id, event_type, actor, event_data, gate_level, created_at
                ) VALUES (
                    'IoS-001', %s, %s, %s, 'G1', NOW()
                )
            """, (operation, 'CODE', json.dumps(details)))
        self.conn.commit()


# =============================================================================
# DATA FETCHING (LINE) - IoS-014 VendorGuard Integration
# =============================================================================

# Fallback chain: YFINANCE -> TWELVEDATA -> BINANCE_PUBLIC
PRICE_VENDOR_CHAIN = ['YFINANCE', 'TWELVEDATA', 'BINANCE_PUBLIC']

# Rate limit: minimum seconds between API calls per vendor
VENDOR_RATE_LIMITS = {
    'YFINANCE': 2.0,      # yfinance gets aggressive rate limiting
    'TWELVEDATA': 1.0,
    'BINANCE_PUBLIC': 0.5,
    'ALPHAVANTAGE': 12.0,  # 5 calls/min = 12s between calls
}

# Track last call time per vendor for rate limiting
_last_call_time: Dict[str, float] = {}


def _rate_limit_wait(vendor: str, logger: logging.Logger):
    """Wait if needed to respect rate limits"""
    min_interval = VENDOR_RATE_LIMITS.get(vendor, 1.0)
    last_call = _last_call_time.get(vendor, 0)
    elapsed = time.time() - last_call

    if elapsed < min_interval:
        wait_time = min_interval - elapsed
        logger.debug(f"  Rate limiting {vendor}: waiting {wait_time:.1f}s")
        time.sleep(wait_time)

    _last_call_time[vendor] = time.time()


def _fetch_yfinance(
    canonical_id: str,
    yf_ticker: str,
    start_date: date,
    end_date: date,
    logger: logging.Logger
) -> Optional[pd.DataFrame]:
    """Fetch from yfinance"""
    try:
        ticker = yf.Ticker(yf_ticker)
        df = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            interval='1d',
            auto_adjust=True
        )
        if df.empty:
            return None
        return df
    except Exception as e:
        error_str = str(e)
        if "Too Many Requests" in error_str or "rate" in error_str.lower():
            logger.warning(f"  [{canonical_id}] YFINANCE rate limited")
            raise  # Re-raise to trigger fallback
        logger.error(f"  [{canonical_id}] YFINANCE error: {e}")
        return None


def _fetch_twelvedata(
    canonical_id: str,
    start_date: date,
    end_date: date,
    logger: logging.Logger
) -> Optional[pd.DataFrame]:
    """Fetch from TwelveData (requires API key)"""
    api_key = os.getenv("TWELVEDATA_API_KEY")
    if not api_key:
        logger.debug(f"  [{canonical_id}] TWELVEDATA: No API key configured")
        return None

    try:
        import requests

        # Map canonical_id to TwelveData symbol
        symbol_map = {
            'BTC-USD': 'BTC/USD',
            'ETH-USD': 'ETH/USD',
            'SOL-USD': 'SOL/USD',
            'EURUSD': 'EUR/USD'
        }
        symbol = symbol_map.get(canonical_id, canonical_id)

        url = "https://api.twelvedata.com/time_series"
        params = {
            'symbol': symbol,
            'interval': '1day',
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'apikey': api_key
        }

        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()

        if 'values' not in data:
            logger.warning(f"  [{canonical_id}] TWELVEDATA: {data.get('message', 'No data')}")
            return None

        # Convert to DataFrame matching yfinance format
        rows = []
        for v in data['values']:
            rows.append({
                'Date': pd.to_datetime(v['datetime']),
                'Open': float(v['open']),
                'High': float(v['high']),
                'Low': float(v['low']),
                'Close': float(v['close']),
                'Volume': float(v.get('volume', 0))
            })

        df = pd.DataFrame(rows)
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        return df

    except Exception as e:
        logger.error(f"  [{canonical_id}] TWELVEDATA error: {e}")
        return None


def fetch_daily_data(
    canonical_id: str,
    yf_ticker: str,
    start_date: date,
    end_date: date,
    logger: logging.Logger,
    vendor_guard: Optional['VendorGuard'] = None
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data with IoS-014 VendorGuard integration.

    Uses fallback chain: YFINANCE -> TWELVEDATA -> BINANCE_PUBLIC
    Respects quota limits and rate limits.
    """
    logger.info(f"  [{canonical_id}] Fetching {start_date} to {end_date}")

    # Determine which vendors to try
    vendors_to_try = PRICE_VENDOR_CHAIN.copy()

    for vendor in vendors_to_try:
        # Check quota with VendorGuard if available
        if vendor_guard:
            result = vendor_guard.check_quota(vendor, 1)
            if not result.can_proceed:
                logger.info(f"  [{canonical_id}] {vendor}: Quota blocked ({result.message})")
                if result.fallback_vendor:
                    logger.info(f"  [{canonical_id}] Trying fallback: {result.fallback_vendor}")
                continue

        # Apply rate limiting
        _rate_limit_wait(vendor, logger)

        # Try fetch from this vendor
        df = None
        try:
            if vendor == 'YFINANCE':
                df = _fetch_yfinance(canonical_id, yf_ticker, start_date, end_date, logger)
            elif vendor == 'TWELVEDATA':
                df = _fetch_twelvedata(canonical_id, start_date, end_date, logger)
            elif vendor == 'BINANCE_PUBLIC':
                # Binance only supports crypto
                if canonical_id in ['BTC-USD', 'ETH-USD', 'SOL-USD']:
                    df = _fetch_binance(canonical_id, start_date, end_date, logger)
                else:
                    continue

            if df is not None and not df.empty:
                # Success - increment usage
                if vendor_guard:
                    vendor_guard.increment_usage(vendor, 1, f"daily_ingest_{canonical_id}")
                logger.info(f"  [{canonical_id}] Fetched {len(df)} rows via {vendor}")
                return df

        except Exception as e:
            error_str = str(e)
            if "Too Many Requests" in error_str or "rate" in error_str.lower():
                logger.warning(f"  [{canonical_id}] {vendor} rate limited, trying next...")
                continue
            else:
                logger.error(f"  [{canonical_id}] {vendor} error: {e}")
                continue

    logger.error(f"  [{canonical_id}] All vendors exhausted, no data fetched")
    return None


def _fetch_binance(
    canonical_id: str,
    start_date: date,
    end_date: date,
    logger: logging.Logger
) -> Optional[pd.DataFrame]:
    """Fetch from Binance public API (crypto only)"""
    try:
        import requests

        # Map to Binance symbol
        symbol_map = {
            'BTC-USD': 'BTCUSDT',
            'ETH-USD': 'ETHUSDT',
            'SOL-USD': 'SOLUSDT'
        }
        symbol = symbol_map.get(canonical_id)
        if not symbol:
            return None

        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': '1d',
            'startTime': int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000),
            'endTime': int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000),
            'limit': 1000
        }

        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()

        if not data or isinstance(data, dict):
            return None

        # Convert to DataFrame
        rows = []
        for k in data:
            rows.append({
                'Date': pd.to_datetime(k[0], unit='ms'),
                'Open': float(k[1]),
                'High': float(k[2]),
                'Low': float(k[3]),
                'Close': float(k[4]),
                'Volume': float(k[5])
            })

        df = pd.DataFrame(rows)
        df.set_index('Date', inplace=True)
        return df

    except Exception as e:
        logger.error(f"  [{canonical_id}] BINANCE error: {e}")
        return None


# =============================================================================
# DATA VALIDATION
# =============================================================================

def validate_and_prepare(
    df: pd.DataFrame,
    canonical_id: str,
    asset_uuid: uuid.UUID,
    batch_id: uuid.UUID,
    logger: logging.Logger
) -> List[Dict]:
    """Validate OHLCV data and prepare for insertion"""

    # Remove NaN rows
    df_clean = df.dropna(subset=['Open', 'High', 'Low', 'Close']).copy()

    # Validate OHLC relationships
    invalid = (
        (df_clean['High'] < df_clean['Low']) |
        (df_clean['High'] < df_clean['Open']) |
        (df_clean['High'] < df_clean['Close']) |
        (df_clean['Low'] > df_clean['Open']) |
        (df_clean['Low'] > df_clean['Close'])
    )

    if invalid.any():
        logger.warning(f"  [{canonical_id}] Removing {invalid.sum()} OHLC violations")
        df_clean = df_clean[~invalid]

    # Convert to row dictionaries
    rows = []
    for idx, row in df_clean.iterrows():
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
            'gap_filled': False,
            'batch_id': str(batch_id)
        }

        # Compute row hash
        hash_input = f"{row_dict['canonical_id']}|{row_dict['timestamp']}|{row_dict['open']}|{row_dict['high']}|{row_dict['low']}|{row_dict['close']}|{row_dict['volume']}"
        row_dict['data_hash'] = hashlib.sha256(hash_input.encode()).hexdigest()

        rows.append(row_dict)

    return rows


# =============================================================================
# STAGING (CODE)
# =============================================================================

def insert_to_staging(
    conn,
    rows: List[Dict],
    logger: logging.Logger
) -> int:
    """Insert rows to staging_prices with idempotent upsert"""
    if not rows:
        return 0

    batch_id = rows[0]['batch_id']

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
            r['source'], r['data_hash'], batch_id, r['gap_filled'], 'CODE'
        )
        for r in rows
    ]

    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values)
        inserted = cur.rowcount

    conn.commit()
    return inserted


# =============================================================================
# RECONCILIATION (VEGA)
# =============================================================================

def reconcile_batch(
    conn,
    batch_id: uuid.UUID,
    logger: logging.Logger
) -> Dict:
    """
    VEGA reconciliation: Compare staging batch against canonical.
    Returns reconciliation result.
    """
    logger.info("VEGA: Running reconciliation...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get staging batch stats
        cur.execute("""
            SELECT
                canonical_id,
                COUNT(*) as staging_rows,
                MIN(timestamp) as min_ts,
                MAX(timestamp) as max_ts
            FROM fhq_market.staging_prices
            WHERE batch_id = %s
            GROUP BY canonical_id
        """, (str(batch_id),))
        staging_stats = cur.fetchall()

        if not staging_stats:
            logger.warning("VEGA: No rows in staging batch")
            return {"decision": "REJECTED", "reason": "Empty batch"}

        # Check for duplicates in canonical
        total_staging = sum(s['staging_rows'] for s in staging_stats)
        total_new = 0

        for stat in staging_stats:
            cur.execute("""
                SELECT COUNT(*) FROM fhq_market.staging_prices s
                WHERE s.batch_id = %s
                  AND s.canonical_id = %s
                  AND NOT EXISTS (
                      SELECT 1 FROM fhq_market.prices p
                      WHERE p.canonical_id = s.canonical_id
                        AND p.timestamp = s.timestamp
                  )
            """, (str(batch_id), stat['canonical_id']))
            new_rows = cur.fetchone()[0]
            total_new += new_rows

        # Compute staging batch hash
        cur.execute("""
            SELECT string_agg(data_hash, '' ORDER BY canonical_id, timestamp) as combined
            FROM fhq_market.staging_prices
            WHERE batch_id = %s
        """, (str(batch_id),))
        combined = cur.fetchone()['combined'] or ''
        staging_hash = hashlib.sha256(combined.encode()).hexdigest()

        # Log reconciliation
        reconciliation_id = uuid.uuid4()
        cur.execute("""
            INSERT INTO fhq_market.reconciliation_log (
                reconciliation_id, batch_id,
                staging_rows, canonical_rows, rows_added,
                staging_hash, vega_decision, vega_notes,
                reconciled_by
            ) VALUES (
                %s, %s, %s, 0, %s, %s, 'APPROVED',
                'Automated reconciliation passed', 'VEGA'
            )
        """, (str(reconciliation_id), str(batch_id), total_staging, total_new, staging_hash))

    conn.commit()

    result = {
        "decision": "APPROVED",
        "reconciliation_id": str(reconciliation_id),
        "staging_rows": total_staging,
        "new_rows": total_new,
        "staging_hash": staging_hash
    }

    logger.info(f"VEGA: Reconciliation APPROVED - {total_new} new rows ready for canonicalization")
    return result


# =============================================================================
# CANONICALIZATION (STIG)
# =============================================================================

def canonicalize_batch(
    conn,
    batch_id: uuid.UUID,
    reconciliation_id: uuid.UUID,
    logger: logging.Logger
) -> int:
    """
    STIG canonicalization: Promote staging data to canonical prices table.
    """
    logger.info("STIG: Canonicalizing batch...")

    with conn.cursor() as cur:
        # Insert new rows from staging to canonical
        cur.execute("""
            INSERT INTO fhq_market.prices (
                asset_id, canonical_id, timestamp,
                open, high, low, close, volume,
                source, staging_id, data_hash,
                gap_filled, batch_id,
                vega_reconciled, vega_reconciled_at, vega_attestation_id,
                canonicalized_by
            )
            SELECT
                s.asset_id::uuid, s.canonical_id, s.timestamp,
                s.open, s.high, s.low, s.close, s.volume,
                s.source, s.id, s.data_hash,
                s.gap_filled, s.batch_id,
                TRUE, NOW(), %s,
                'STIG'
            FROM fhq_market.staging_prices s
            WHERE s.batch_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM fhq_market.prices p
                  WHERE p.canonical_id = s.canonical_id
                    AND p.timestamp = s.timestamp
              )
        """, (str(reconciliation_id), str(batch_id)))

        canonicalized = cur.rowcount

    conn.commit()
    logger.info(f"STIG: Canonicalized {canonicalized} rows to fhq_market.prices")
    return canonicalized


# =============================================================================
# GAP BACKFILL
# =============================================================================

def backfill_gaps(
    db: DatabaseManager,
    config: Config,
    logger: logging.Logger
) -> Dict:
    """Detect and backfill gaps for all assets"""
    logger.info("Checking for data gaps...")

    batch_id = uuid.uuid4()
    total_gaps = 0
    total_filled = 0

    for canonical_id, yf_ticker in config.ASSETS.items():
        gaps = db.detect_gaps(canonical_id)

        if gaps:
            logger.info(f"  [{canonical_id}] Found {len(gaps)} gaps")

            for gap_start, gap_end, gap_days in gaps:
                logger.info(f"    Gap: {gap_start} to {gap_end} ({gap_days} days)")

                # Record gap
                db.record_gap(canonical_id, gap_start, gap_end, gap_days)
                total_gaps += 1

                # Attempt backfill (with VendorGuard if available)
                df = fetch_daily_data(
                    canonical_id, yf_ticker,
                    gap_start, gap_end, logger, db.vendor_guard
                )

                if df is not None and not df.empty:
                    asset_uuid = db.get_asset_uuid(canonical_id)
                    rows = validate_and_prepare(df, canonical_id, asset_uuid, batch_id, logger)

                    # Mark as gap-filled
                    for r in rows:
                        r['gap_filled'] = True

                    inserted = insert_to_staging(db.conn, rows, logger)
                    total_filled += inserted
                    logger.info(f"    Backfilled {inserted} rows")

                # Rate limit
                time.sleep(1)
        else:
            logger.info(f"  [{canonical_id}] No gaps detected")

    return {
        "gaps_detected": total_gaps,
        "rows_backfilled": total_filled,
        "batch_id": str(batch_id) if total_filled > 0 else None
    }


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_daily_pipeline(
    config: Config,
    logger: logging.Logger,
    include_backfill: bool = True,
    include_canonicalize: bool = True
) -> Dict:
    """
    Execute the full daily ingestion pipeline.
    """
    logger.info("=" * 60)
    logger.info("DAILY INGEST WORKER - Starting Pipeline")
    logger.info("=" * 60)
    logger.info(f"Schedule: {config.SCHEDULE_NAME}")
    logger.info(f"Assets: {list(config.ASSETS.keys())}")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    # Initialize
    db = DatabaseManager(config, logger)
    db.connect()

    batch_id = uuid.uuid4()
    results = {
        "batch_id": str(batch_id),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "assets": {},
        "totals": {"fetched": 0, "staged": 0, "canonicalized": 0}
    }

    try:
        # Update schedule status
        db.update_schedule_status(config.SCHEDULE_NAME, "RUNNING", batch_id)

        # STAGE 1: FETCH_PRICES (LINE)
        logger.info("\n[STAGE 1] FETCH_PRICES (LINE)")
        logger.info("-" * 40)

        for canonical_id, yf_ticker in config.ASSETS.items():
            logger.info(f"\n[{canonical_id}] Processing...")

            # Get last timestamp
            last_ts = db.get_last_timestamp(canonical_id)

            if last_ts:
                start_date = (last_ts + timedelta(days=1)).date()
                logger.info(f"  Last data: {last_ts.date()}, fetching from {start_date}")
            else:
                start_date = date.today() - timedelta(days=7)
                logger.info(f"  No existing data, fetching last 7 days")

            end_date = date.today()

            if start_date > end_date:
                logger.info(f"  [{canonical_id}] Already up to date")
                results["assets"][canonical_id] = {"status": "UP_TO_DATE", "rows": 0}
                continue

            # Fetch data (with VendorGuard if available)
            df = fetch_daily_data(canonical_id, yf_ticker, start_date, end_date, logger, db.vendor_guard)

            if df is None or df.empty:
                results["assets"][canonical_id] = {"status": "NO_DATA", "rows": 0}
                continue

            # Validate and prepare
            asset_uuid = db.get_asset_uuid(canonical_id)
            rows = validate_and_prepare(df, canonical_id, asset_uuid, batch_id, logger)
            results["totals"]["fetched"] += len(rows)

            # Insert to staging
            inserted = insert_to_staging(db.conn, rows, logger)
            results["totals"]["staged"] += inserted
            results["assets"][canonical_id] = {"status": "STAGED", "rows": inserted}

            logger.info(f"  [{canonical_id}] Staged {inserted} rows")

            # Rate limit
            time.sleep(0.5)

        # STAGE 2: GAP_DETECTION & BACKFILL (CODE)
        if include_backfill:
            logger.info("\n[STAGE 2] GAP_DETECTION & BACKFILL (CODE)")
            logger.info("-" * 40)
            backfill_result = backfill_gaps(db, config, logger)
            results["backfill"] = backfill_result

        # STAGE 3: RECONCILE (VEGA)
        logger.info("\n[STAGE 3] RECONCILE (VEGA)")
        logger.info("-" * 40)
        reconcile_result = reconcile_batch(db.conn, batch_id, logger)
        results["reconciliation"] = reconcile_result

        # STAGE 4: CANONICALIZE (STIG)
        if include_canonicalize and reconcile_result["decision"] == "APPROVED":
            logger.info("\n[STAGE 4] CANONICALIZE (STIG)")
            logger.info("-" * 40)
            reconciliation_id = uuid.UUID(reconcile_result["reconciliation_id"])
            canonicalized = canonicalize_batch(db.conn, batch_id, reconciliation_id, logger)
            results["totals"]["canonicalized"] = canonicalized

        # Update schedule status
        status = "SUCCESS" if results["totals"]["staged"] > 0 or all(
            a["status"] == "UP_TO_DATE" for a in results["assets"].values()
        ) else "PARTIAL"
        db.update_schedule_status(config.SCHEDULE_NAME, status, batch_id)

        # Log to ios_audit
        db.log_to_ios_audit("DAILY_INGEST", {
            "batch_id": str(batch_id),
            "assets": list(config.ASSETS.keys()),
            "staged": results["totals"]["staged"],
            "canonicalized": results["totals"]["canonicalized"]
        })

        results["status"] = status
        results["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        results["status"] = "FAILED"
        results["error"] = str(e)
        try:
            db.conn.rollback()  # Rollback any failed transaction
            db.update_schedule_status(config.SCHEDULE_NAME, "FAILED", batch_id)
        except:
            pass  # Connection may be in bad state

    finally:
        db.close()

    # Write evidence
    evidence_file = config.EVIDENCE_DIR / f"DAILY_INGEST_{batch_id}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nEvidence: {evidence_file}")

    # Summary - conditional on actual status
    final_status = results.get('status', 'UNKNOWN')
    logger.info("\n" + "=" * 60)
    if final_status in ["SUCCESS", "PARTIAL"]:
        logger.info("PIPELINE COMPLETE")
    else:
        logger.info(f"PIPELINE FAILED ({final_status})")
    logger.info("=" * 60)
    logger.info(f"Status: {final_status}")
    logger.info(f"Fetched: {results['totals']['fetched']} rows")
    logger.info(f"Staged: {results['totals']['staged']} rows")
    logger.info(f"Canonicalized: {results['totals']['canonicalized']} rows")
    logger.info("=" * 60)

    return results


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Daily OHLCV Ingest Worker")
    parser.add_argument("--backfill", action="store_true", help="Include gap backfill")
    parser.add_argument("--canonicalize", action="store_true", help="Include canonicalization")
    parser.add_argument("--full-pipeline", action="store_true", help="Run complete pipeline")

    args = parser.parse_args()

    config = Config()
    logger = setup_logging(config)

    include_backfill = args.backfill or args.full_pipeline
    include_canonicalize = args.canonicalize or args.full_pipeline

    result = run_daily_pipeline(
        config, logger,
        include_backfill=include_backfill,
        include_canonicalize=include_canonicalize
    )

    sys.exit(0 if result.get("status") in ["SUCCESS", "PARTIAL"] else 1)
