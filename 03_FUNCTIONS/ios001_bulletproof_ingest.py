#!/usr/bin/env python3
"""
IoS-001 BULLETPROOF DAILY PRICE INGEST
======================================

CEO Directive: CD-IOS-001-DAILY-INGEST-BULLETPROOF-001
Classification: CRITICAL INFRASTRUCTURE
Date: 2025-12-16

THIS SCRIPT WILL NOT FAIL SILENTLY.

Architecture:
  Layer 1: Multi-Provider Fallback (Alpaca -> Yahoo -> Alert)
  Layer 2: Verification After Every Run
  Layer 3: Multiple Trigger Points
  Layer 4: Alerting on ANY failure

Canonical Source: fhq_market.prices (ONLY)
  - This is the SINGLE source of truth
  - 1.23M rows, 497 assets
  - NEVER use fhq_data.price_series

Executor: STIG (EC-003)
"""

import os
import sys
import json
import hashlib
import uuid
import logging
import time
import argparse
import requests
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from dotenv import load_dotenv

# Load .env from project root (parent of 03_FUNCTIONS)
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / '.env')

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

# Alpaca API (Primary Provider - 200 req/min)
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '') or os.environ.get('ALPACA_SECRET', '')

# TwelveData API (Equity Backup - 800/day, 8/min on free tier)
TWELVEDATA_API_KEY = os.environ.get('TWELVEDATA_API_KEY', '')
# IoS-001 Compliance: 90% of free tier = 720/day, 7/min
TWELVEDATA_DAILY_LIMIT = 720  # 800 * 0.90
TWELVEDATA_RATE_PER_MIN = 7   # 8 * 0.90 rounded down
TWELVEDATA_CALL_DELAY = 60 / TWELVEDATA_RATE_PER_MIN  # ~8.6s between calls

# Alerting webhook (Slack/Discord)
ALERT_WEBHOOK_URL = os.environ.get('ALERT_WEBHOOK_URL', '')

# Rate limiting - Conservative
ALPACA_BATCH_SIZE = 50  # Alpaca is generous (200/min)
ALPACA_CALL_DELAY = 0.5  # 0.5s between calls = 120/min (safe margin)
YAHOO_BATCH_SIZE = 10   # Yahoo needs caution
YAHOO_CALL_DELAY = 5    # 5s between calls = 12/min
BATCH_COOLDOWN = 30     # Cooldown between batches

# Staleness threshold
STALE_THRESHOLD_DAYS = 2

# Paths
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# =============================================================================
# LOGGING
# =============================================================================

log_file = EVIDENCE_DIR / f"bulletproof_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("BULLETPROOF_INGEST")


class IngestProvider(Enum):
    ALPACA = "ALPACA"
    YAHOO = "YAHOO"
    MANUAL = "MANUAL"


class IngestStatus(Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


# =============================================================================
# ALERTING
# =============================================================================

def send_alert(message: str, severity: str = 'ERROR'):
    """
    Send alert to configured webhook.
    THIS WILL ALWAYS LOG LOCALLY even if webhook fails.
    """
    timestamp = datetime.utcnow().isoformat()

    # Always log locally first
    if severity == 'CRITICAL':
        logger.critical(f"ALERT [{severity}]: {message}")
    elif severity == 'ERROR':
        logger.error(f"ALERT [{severity}]: {message}")
    else:
        logger.warning(f"ALERT [{severity}]: {message}")

    # Try webhook
    if ALERT_WEBHOOK_URL:
        try:
            requests.post(ALERT_WEBHOOK_URL, json={
                'text': f"[{severity}] IoS-001 Bulletproof Ingest: {message}",
                'timestamp': timestamp,
                'component': 'ios001_bulletproof_ingest'
            }, timeout=10)
        except Exception as e:
            logger.warning(f"Webhook alert failed: {e}")


# =============================================================================
# DATABASE
# =============================================================================

def get_connection():
    return psycopg2.connect(**DB_CONFIG, options='-c client_encoding=UTF8')


def get_canonical_assets(conn, asset_class: Optional[str] = None) -> List[Dict]:
    """
    Get all canonical assets that need price data.
    Returns assets from fhq_meta.assets.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = """
            SELECT
                canonical_id,
                ticker,
                asset_class,
                exchange_mic
            FROM fhq_meta.assets
            WHERE active_flag = true
        """
        if asset_class:
            query += f" AND asset_class = '{asset_class}'"
        query += " ORDER BY asset_class, canonical_id"

        cur.execute(query)
        return cur.fetchall()


def get_last_price_date(conn, canonical_id: str) -> Optional[date]:
    """Get most recent price date for asset from CANONICAL source."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT MAX(timestamp::date)
            FROM fhq_market.prices
            WHERE canonical_id = %s
        """, (canonical_id,))
        result = cur.fetchone()[0]
        return result


def insert_prices_canonical(
    conn,
    canonical_id: str,
    df: pd.DataFrame,
    batch_id: str,
    source: str
) -> int:
    """
    Insert price data to CANONICAL source: fhq_market.prices

    THIS IS THE ONLY PLACE PRICE DATA SHOULD BE WRITTEN.
    """
    if df is None or df.empty:
        return 0

    rows = []
    for idx, row in df.iterrows():
        # Handle timezone
        try:
            timestamp = idx.tz_localize(None) if idx.tzinfo else idx
        except:
            timestamp = idx

        # Extract values
        try:
            open_val = float(row['open']) if pd.notna(row.get('open')) else None
            high_val = float(row['high']) if pd.notna(row.get('high')) else None
            low_val = float(row['low']) if pd.notna(row.get('low')) else None
            close_val = float(row['close']) if pd.notna(row.get('close')) else None
            volume_val = float(row.get('volume', 0)) if pd.notna(row.get('volume')) else 0
            adj_close_val = float(row.get('adj_close', close_val)) if pd.notna(row.get('adj_close', close_val)) else close_val
        except Exception as e:
            logger.debug(f"Row parse error for {canonical_id}: {e}")
            continue

        if close_val is None or close_val <= 0:
            continue

        # OHLC validation - ensure constraints are met
        if open_val is None:
            open_val = close_val
        if high_val is None:
            high_val = max(open_val, close_val)
        if low_val is None:
            low_val = min(open_val, close_val)

        # Fix OHLC violations
        high_val = max(high_val, open_val, close_val)
        low_val = min(low_val, open_val, close_val)

        # Data hash for deduplication
        data_str = f"{canonical_id}|{timestamp}|{open_val}|{high_val}|{low_val}|{close_val}|{volume_val}"
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        rows.append((
            str(uuid.uuid4()),      # id
            str(uuid.uuid4()),      # asset_id
            canonical_id,           # canonical_id
            timestamp,              # timestamp
            open_val,               # open
            high_val,               # high
            low_val,                # low
            close_val,              # close
            volume_val,             # volume
            source,                 # source (ALPACA or YAHOO)
            None,                   # staging_id
            data_hash,              # data_hash
            False,                  # gap_filled
            False,                  # interpolated
            1.0,                    # quality_score
            batch_id,               # batch_id
            'STIG',                 # canonicalized_by
            adj_close_val           # adj_close (IoS-002 compliant)
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
                    data_hash = EXCLUDED.data_hash,
                    source = EXCLUDED.source
                WHERE fhq_market.prices.adj_close IS NULL
                   OR fhq_market.prices.source = 'MIGRATION_FROM_PRICE_SERIES'
            """
            execute_values(cur, insert_sql, rows)
            conn.commit()
        return len(rows)
    except Exception as e:
        conn.rollback()
        logger.error(f"Insert error for {canonical_id}: {e}")
        return 0


# =============================================================================
# PROVIDER: ALPACA (PRIMARY)
# =============================================================================

def try_alpaca_ingest(
    conn,
    assets: List[Dict],
    batch_id: str
) -> Tuple[Dict, List[str]]:
    """
    Attempt data ingest via Alpaca API.

    Alpaca provides:
    - US equities (all NYSE, NASDAQ, etc.)
    - Crypto (major pairs)
    - Rate limit: 200 req/min (very generous)

    Returns: (results dict, list of failed asset IDs)
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        logger.warning("Alpaca API keys not configured")
        return {'status': 'NOT_CONFIGURED', 'updated': 0, 'rows': 0}, [a['canonical_id'] for a in assets]

    try:
        from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
        from alpaca.data.timeframe import TimeFrame
    except ImportError:
        logger.warning("alpaca-py not installed")
        return {'status': 'NOT_INSTALLED', 'updated': 0, 'rows': 0}, [a['canonical_id'] for a in assets]

    logger.info("=" * 60)
    logger.info("ATTEMPTING ALPACA INGEST (Primary Provider)")
    logger.info(f"Assets: {len(assets)}, Rate limit: 200/min")
    logger.info("=" * 60)

    stock_client = StockHistoricalDataClient(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_SECRET_KEY
    )
    crypto_client = CryptoHistoricalDataClient(
        api_key=ALPACA_API_KEY,
        secret_key=ALPACA_SECRET_KEY
    )

    results = {'status': 'SUCCESS', 'updated': 0, 'rows': 0, 'errors': 0}
    failed_assets = []
    consecutive_sip_errors = 0  # Track SIP subscription errors for early termination
    MAX_SIP_ERRORS = 5  # If 5 consecutive SIP errors, skip remaining

    for i, asset in enumerate(assets):
        canonical_id = asset['canonical_id']
        asset_class = asset['asset_class']

        # Get last price date
        last_date = get_last_price_date(conn, canonical_id)
        if last_date:
            start_date = last_date + timedelta(days=1)
        else:
            start_date = date.today() - timedelta(days=30)

        end_date = date.today()

        if start_date > end_date:
            logger.debug(f"  [{canonical_id}] Up to date")
            continue

        try:
            if asset_class == 'CRYPTO':
                # Alpaca crypto symbols don't have -USD suffix
                symbol = canonical_id.replace('-USD', '/USD')
                request = CryptoBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Day,
                    start=datetime.combine(start_date, datetime.min.time()),
                    end=datetime.combine(end_date, datetime.max.time())
                )
                bars = crypto_client.get_crypto_bars(request)
            elif asset_class == 'EQUITY':
                # Skip non-US equities (Alpaca only has US)
                if '.OL' in canonical_id or '.DE' in canonical_id or '.PA' in canonical_id:
                    failed_assets.append(canonical_id)
                    continue

                request = StockBarsRequest(
                    symbol_or_symbols=canonical_id,
                    timeframe=TimeFrame.Day,
                    start=datetime.combine(start_date, datetime.min.time()),
                    end=datetime.combine(end_date, datetime.max.time())
                )
                bars = stock_client.get_stock_bars(request)
            else:
                # FX - Alpaca doesn't provide FX
                failed_assets.append(canonical_id)
                continue

            # Convert to DataFrame
            if asset_class == 'CRYPTO':
                symbol_key = symbol
            else:
                symbol_key = canonical_id

            if symbol_key in bars.data and len(bars.data[symbol_key]) > 0:
                bar_list = bars.data[symbol_key]
                df = pd.DataFrame([{
                    'timestamp': bar.timestamp,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume
                } for bar in bar_list])
                df.set_index('timestamp', inplace=True)
                df['adj_close'] = df['close']  # Alpaca doesn't have adj_close

                rows = insert_prices_canonical(conn, canonical_id, df, batch_id, 'ALPACA')
                if rows > 0:
                    results['updated'] += 1
                    results['rows'] += rows
                    logger.info(f"  [{canonical_id}] +{rows} rows via ALPACA")
                    consecutive_sip_errors = 0  # Reset on success
            else:
                logger.debug(f"  [{canonical_id}] No data from Alpaca")
                failed_assets.append(canonical_id)

        except Exception as e:
            error_msg = str(e)[:200]
            if '429' in error_msg or 'rate' in error_msg.lower():
                logger.warning(f"  [{canonical_id}] Rate limited, waiting 60s...")
                time.sleep(60)
            elif 'subscription does not permit' in error_msg:
                consecutive_sip_errors += 1
                if consecutive_sip_errors >= MAX_SIP_ERRORS:
                    logger.warning(f"  [{canonical_id}] SIP subscription error ({consecutive_sip_errors} consecutive)")
                    logger.warning(f"  EARLY TERMINATION: Alpaca SIP subscription not available")
                    logger.warning(f"  Skipping remaining {len(assets) - i - 1} Alpaca assets - will use fallback provider")
                    # Add all remaining assets to failed list
                    remaining_assets = [a['canonical_id'] for a in assets[i:]]
                    failed_assets.extend(remaining_assets)
                    results['status'] = 'SIP_NOT_AVAILABLE'
                    break
                else:
                    logger.warning(f"  [{canonical_id}] Alpaca error: {error_msg[:100]}")
            else:
                logger.warning(f"  [{canonical_id}] Alpaca error: {error_msg[:100]}")
                consecutive_sip_errors = 0  # Reset on non-SIP errors
            failed_assets.append(canonical_id)
            results['errors'] += 1

        # Rate limiting
        time.sleep(ALPACA_CALL_DELAY)

        # Progress update every 50 assets
        if (i + 1) % 50 == 0:
            logger.info(f"  Progress: {i+1}/{len(assets)} assets processed")

    if results['errors'] > len(assets) * 0.5:
        results['status'] = 'PARTIAL'

    return results, failed_assets


# =============================================================================
# PROVIDER: YAHOO FINANCE (FALLBACK) - FIXED VERSION
# =============================================================================

# Rate limit configuration for Yahoo
YAHOO_MAX_RETRIES = 3
YAHOO_BASE_BACKOFF = 60  # Start with 60s backoff
YAHOO_BATCH_DOWNLOAD_SIZE = 50  # Download up to 50 symbols at once


def _check_yahoo_rate_limit() -> bool:
    """
    Pre-flight check to detect if Yahoo Finance is rate-limiting us.
    Returns True if rate-limited, False if OK.
    """
    import yfinance as yf
    try:
        # Use a single well-known ticker for testing
        test = yf.download('AAPL', period='1d', progress=False, threads=False)
        return test.empty  # Empty result often means rate limited
    except Exception as e:
        if 'RateLimit' in type(e).__name__ or '429' in str(e) or 'Too Many' in str(e):
            return True
        return False


def _map_to_yf_ticker(canonical_id: str, asset_class: str) -> str:
    """Map canonical ID to yfinance ticker format."""
    if asset_class == 'FX' and not canonical_id.endswith('=X'):
        return canonical_id + '=X'
    return canonical_id


def _batch_download_with_retry(
    symbols: List[str],
    start_date: date,
    end_date: date,
    max_retries: int = YAHOO_MAX_RETRIES
) -> pd.DataFrame:
    """
    Download data for multiple symbols using yf.download() with retry logic.

    This is MUCH more efficient than individual ticker.history() calls:
    - 1 API call for 50 symbols vs 50 API calls
    - Automatic rate limit handling by yfinance
    """
    import yfinance as yf

    for attempt in range(max_retries):
        try:
            # Use yf.download for batch operations - CRITICAL for rate limiting
            df = yf.download(
                symbols,
                start=start_date.strftime('%Y-%m-%d'),
                end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                interval='1d',
                auto_adjust=False,
                progress=False,
                threads=False,  # Single thread to avoid rate limit issues
                group_by='ticker'  # Group by ticker for easier processing
            )
            return df

        except Exception as e:
            error_msg = str(e)
            is_rate_limited = (
                'YFRateLimitError' in type(e).__name__ or
                '429' in error_msg or
                'Too Many Requests' in error_msg or
                'Rate limit' in error_msg.lower()
            )

            if is_rate_limited and attempt < max_retries - 1:
                backoff = YAHOO_BASE_BACKOFF * (2 ** attempt)  # Exponential backoff
                logger.warning(f"  Rate limited (attempt {attempt + 1}/{max_retries}), waiting {backoff}s...")
                time.sleep(backoff)
            else:
                raise

    return pd.DataFrame()


def try_yahoo_ingest(
    conn,
    assets: List[Dict],
    batch_id: str
) -> Tuple[Dict, List[str]]:
    """
    Attempt data ingest via Yahoo Finance (fallback).

    FIXED VERSION: Uses batch download (yf.download) instead of individual
    ticker.history() calls. This dramatically reduces API calls and rate limiting.

    Yahoo provides:
    - Global equities (US, EU, Asia)
    - Crypto
    - FX
    - Rate limit: 2000 requests/hour (but aggressive 429s when exceeded)

    Returns: (results dict, list of failed asset IDs)
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed")
        return {'status': 'NOT_INSTALLED', 'updated': 0, 'rows': 0}, [a['canonical_id'] for a in assets]

    logger.info("=" * 60)
    logger.info("ATTEMPTING YAHOO FINANCE INGEST (Fallback Provider)")
    logger.info(f"Assets: {len(assets)}, Using BATCH DOWNLOAD (efficient)")
    logger.info("=" * 60)

    results = {'status': 'SUCCESS', 'updated': 0, 'rows': 0, 'errors': 0}
    failed_assets = []

    # Pre-flight rate limit check
    logger.info("  Checking Yahoo Finance rate limit status...")
    if _check_yahoo_rate_limit():
        logger.warning("  RATE LIMITED - Yahoo Finance is currently blocking requests")
        logger.warning("  Skipping Yahoo and marking all assets as failed")
        return {'status': 'RATE_LIMITED', 'updated': 0, 'rows': 0, 'errors': 0}, [a['canonical_id'] for a in assets]
    logger.info("  Rate limit check passed - proceeding with download")

    # Group assets by start date needed (optimization)
    # For simplicity, use the earliest start date across all assets
    earliest_start = date.today() - timedelta(days=30)
    for asset in assets:
        last_date = get_last_price_date(conn, asset['canonical_id'])
        if last_date:
            asset_start = last_date + timedelta(days=1)
            if asset_start < earliest_start:
                earliest_start = asset_start

    end_date = date.today()

    if earliest_start > end_date:
        logger.info("  All assets are up to date")
        return results, []

    # Build symbol mapping: yf_ticker -> canonical_id
    symbol_map = {}
    for asset in assets:
        canonical_id = asset['canonical_id']
        asset_class = asset['asset_class']
        yf_ticker = _map_to_yf_ticker(canonical_id, asset_class)
        symbol_map[yf_ticker] = canonical_id

    symbols = list(symbol_map.keys())
    logger.info(f"  Downloading {len(symbols)} symbols from {earliest_start} to {end_date}")

    # Process in batches for very large symbol lists
    for i in range(0, len(symbols), YAHOO_BATCH_DOWNLOAD_SIZE):
        batch_symbols = symbols[i:i + YAHOO_BATCH_DOWNLOAD_SIZE]
        batch_num = (i // YAHOO_BATCH_DOWNLOAD_SIZE) + 1
        total_batches = (len(symbols) + YAHOO_BATCH_DOWNLOAD_SIZE - 1) // YAHOO_BATCH_DOWNLOAD_SIZE

        logger.info(f"  Batch {batch_num}/{total_batches}: {len(batch_symbols)} symbols")

        try:
            df = _batch_download_with_retry(batch_symbols, earliest_start, end_date)

            if df is None or df.empty:
                logger.warning(f"  Batch {batch_num} returned no data")
                for sym in batch_symbols:
                    failed_assets.append(symbol_map[sym])
                continue

            # Process each symbol from the batch result
            for yf_ticker in batch_symbols:
                canonical_id = symbol_map[yf_ticker]

                try:
                    # Extract single ticker data from MultiIndex DataFrame
                    if len(batch_symbols) == 1:
                        ticker_df = df.copy()
                    else:
                        if yf_ticker in df.columns.get_level_values(0):
                            ticker_df = df[yf_ticker].copy()
                        else:
                            logger.debug(f"  [{canonical_id}] No data in batch result")
                            failed_assets.append(canonical_id)
                            continue

                    # Check if we have valid data
                    if ticker_df is None or ticker_df.empty or ticker_df['Close'].isna().all():
                        failed_assets.append(canonical_id)
                        continue

                    # Rename columns to lowercase
                    ticker_df.columns = ticker_df.columns.str.lower()
                    ticker_df.rename(columns={'adj close': 'adj_close'}, inplace=True)

                    # Filter to only dates after last known price
                    last_date = get_last_price_date(conn, canonical_id)
                    if last_date:
                        ticker_df = ticker_df[ticker_df.index.date > last_date]

                    if ticker_df.empty:
                        continue  # Up to date, not a failure

                    rows = insert_prices_canonical(conn, canonical_id, ticker_df, batch_id, 'YAHOO')
                    if rows > 0:
                        results['updated'] += 1
                        results['rows'] += rows
                        logger.info(f"  [{canonical_id}] +{rows} rows via YAHOO")

                except Exception as e:
                    logger.debug(f"  [{canonical_id}] Processing error: {e}")
                    failed_assets.append(canonical_id)
                    results['errors'] += 1

        except Exception as e:
            error_msg = str(e)[:200]
            logger.error(f"  Batch {batch_num} failed: {error_msg}")
            results['errors'] += len(batch_symbols)
            for sym in batch_symbols:
                failed_assets.append(symbol_map[sym])

        # Cooldown between batches
        if i + YAHOO_BATCH_DOWNLOAD_SIZE < len(symbols):
            logger.info(f"  Batch complete, cooling down {BATCH_COOLDOWN}s...")
            time.sleep(BATCH_COOLDOWN)

    if results['errors'] > len(assets) * 0.5:
        results['status'] = 'PARTIAL'

    logger.info(f"  Yahoo ingest complete: {results['updated']} updated, {len(failed_assets)} failed")
    return results, failed_assets


# =============================================================================
# PROVIDER: ECB (European Central Bank) - FX BACKUP
# =============================================================================

# ECB FX pair mapping (canonical_id -> ECB currency code)
ECB_FX_MAP = {
    'EURUSD=X': ('USD', 'EUR'),  # ECB provides EUR-based rates
    'EURGBP=X': ('GBP', 'EUR'),
    'EURJPY=X': ('JPY', 'EUR'),
    'EURCHF=X': ('CHF', 'EUR'),
    'EURNOK=X': ('NOK', 'EUR'),
    'EURSEK=X': ('SEK', 'EUR'),
    'EURAUD=X': ('AUD', 'EUR'),
}


def try_ecb_fx_ingest(
    conn,
    assets: List[Dict],
    batch_id: str
) -> Tuple[Dict, List[str]]:
    """
    Attempt FX data ingest via ECB (European Central Bank) API.

    ECB provides:
    - EUR-based FX rates only
    - NO rate limiting (free public API)
    - Daily data, updated around 16:00 CET

    This is a BACKUP provider for when Yahoo is rate-limited.
    Only supports EUR-based pairs.

    Returns: (results dict, list of failed asset IDs)
    """
    logger.info("=" * 60)
    logger.info("ATTEMPTING ECB FX INGEST (Backup Provider)")
    logger.info(f"Assets: {len(assets)}, Rate limit: NONE (free API)")
    logger.info("=" * 60)

    results = {'status': 'SUCCESS', 'updated': 0, 'rows': 0, 'errors': 0}
    failed_assets = []

    # Filter to only ECB-supported FX pairs
    ecb_assets = [a for a in assets if a['canonical_id'] in ECB_FX_MAP]
    non_ecb_assets = [a for a in assets if a['canonical_id'] not in ECB_FX_MAP]

    logger.info(f"  ECB-supported: {len(ecb_assets)}, Not supported: {len(non_ecb_assets)}")

    # Mark non-ECB assets as failed immediately
    for asset in non_ecb_assets:
        failed_assets.append(asset['canonical_id'])

    if not ecb_assets:
        logger.info("  No ECB-supported FX pairs to fetch")
        return results, failed_assets

    for asset in ecb_assets:
        canonical_id = asset['canonical_id']
        currency, base = ECB_FX_MAP[canonical_id]

        # Get last price date
        last_date = get_last_price_date(conn, canonical_id)
        if last_date:
            start_date = last_date + timedelta(days=1)
        else:
            start_date = date.today() - timedelta(days=30)

        if start_date > date.today():
            logger.debug(f"  [{canonical_id}] Up to date")
            continue

        try:
            # ECB SDMX API
            days_needed = (date.today() - start_date).days + 5  # Extra buffer
            url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A?format=jsondata&lastNObservations={days_needed}"

            resp = requests.get(url, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"  [{canonical_id}] ECB returned {resp.status_code}")
                failed_assets.append(canonical_id)
                results['errors'] += 1
                continue

            data = resp.json()

            # Parse ECB response
            observations = data.get('dataSets', [{}])[0].get('series', {}).get('0:0:0:0:0', {}).get('observations', {})
            time_periods = data.get('structure', {}).get('dimensions', {}).get('observation', [{}])[0].get('values', [])

            if not observations or not time_periods:
                logger.warning(f"  [{canonical_id}] No data from ECB")
                failed_assets.append(canonical_id)
                continue

            # Build DataFrame
            rows = []
            for idx, period in enumerate(time_periods):
                date_str = period.get('id', '')
                if str(idx) in observations:
                    rate = observations[str(idx)][0]
                    try:
                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                        if dt.date() > last_date if last_date else True:
                            rows.append({
                                'timestamp': dt,
                                'open': rate,
                                'high': rate,
                                'low': rate,
                                'close': rate,
                                'volume': 0,
                                'adj_close': rate
                            })
                    except:
                        pass

            if rows:
                df = pd.DataFrame(rows)
                df.set_index('timestamp', inplace=True)
                inserted = insert_prices_canonical(conn, canonical_id, df, batch_id, 'ECB')
                if inserted > 0:
                    results['updated'] += 1
                    results['rows'] += inserted
                    logger.info(f"  [{canonical_id}] +{inserted} rows via ECB")
            else:
                failed_assets.append(canonical_id)

        except Exception as e:
            logger.warning(f"  [{canonical_id}] ECB error: {str(e)[:100]}")
            failed_assets.append(canonical_id)
            results['errors'] += 1

        time.sleep(0.5)  # Be nice to ECB

    logger.info(f"  ECB ingest complete: {results['updated']} updated, {len(failed_assets)} failed")
    return results, failed_assets


# =============================================================================
# PROVIDER: TWELVEDATA FX (NON-EUR BACKUP)
# =============================================================================

def try_twelvedata_fx_ingest(
    conn,
    assets: List[Dict],
    batch_id: str
) -> Tuple[Dict, List[str]]:
    """
    Attempt FX data ingest via TwelveData API for non-EUR pairs.

    TwelveData provides:
    - Global forex pairs (not just EUR-based)
    - Historical OHLCV data
    - Free tier: 800 calls/day, 8/min (SHARED with equity)

    IoS-001 Compliance: Use 90% of free tier = 720/day, 7/min

    This is a BACKUP provider for non-EUR FX pairs when Yahoo is rate-limited.

    Returns: (results dict, list of failed asset IDs)
    """
    if not TWELVEDATA_API_KEY:
        logger.warning("TwelveData API key not configured")
        return {'status': 'NOT_CONFIGURED', 'updated': 0, 'rows': 0}, [a['canonical_id'] for a in assets]

    logger.info("=" * 60)
    logger.info("ATTEMPTING TWELVEDATA FX INGEST (Non-EUR Backup)")
    logger.info(f"Assets: {len(assets)}, Rate limit: {TWELVEDATA_RATE_PER_MIN}/min (90% of free tier)")
    logger.info("=" * 60)

    results = {'status': 'SUCCESS', 'updated': 0, 'rows': 0, 'errors': 0, 'api_calls': 0}
    failed_assets = []

    # Filter to only FX assets
    fx_assets = [a for a in assets if a.get('asset_class') == 'FX']
    non_fx_assets = [a for a in assets if a.get('asset_class') != 'FX']

    logger.info(f"  FX assets: {len(fx_assets)}, Non-FX: {len(non_fx_assets)}")

    # Mark non-FX assets as failed immediately
    for asset in non_fx_assets:
        failed_assets.append(asset['canonical_id'])

    if not fx_assets:
        logger.info("  No FX assets to fetch")
        return results, failed_assets

    for i, asset in enumerate(fx_assets):
        # Rate limiting at START - IoS-001 compliant (ensures ALL code paths respect rate limit)
        if i > 0:  # Skip delay on first iteration
            time.sleep(TWELVEDATA_CALL_DELAY)

        canonical_id = asset['canonical_id']

        # Get last price date
        last_date = get_last_price_date(conn, canonical_id)
        if last_date:
            start_date = last_date + timedelta(days=1)
        else:
            start_date = date.today() - timedelta(days=30)

        if start_date > date.today():
            logger.debug(f"  [{canonical_id}] Up to date")
            continue

        # Map Yahoo FX format to TwelveData format
        # USDJPY=X -> USD/JPY, EURUSD=X -> EUR/USD, etc.
        td_symbol = canonical_id.replace('=X', '')
        if len(td_symbol) == 6:
            td_symbol = f"{td_symbol[:3]}/{td_symbol[3:]}"
        else:
            logger.warning(f"  [{canonical_id}] Invalid FX format, skipping")
            failed_assets.append(canonical_id)
            continue

        try:
            url = 'https://api.twelvedata.com/time_series'
            params = {
                'symbol': td_symbol,
                'interval': '1day',
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': date.today().strftime('%Y-%m-%d'),
                'apikey': TWELVEDATA_API_KEY
            }

            resp = requests.get(url, params=params, timeout=30)
            results['api_calls'] += 1

            if resp.status_code == 429:
                logger.warning(f"  [{canonical_id}] TwelveData rate limited, stopping")
                for remaining_asset in fx_assets[i:]:
                    failed_assets.append(remaining_asset['canonical_id'])
                results['status'] = 'RATE_LIMITED'
                break

            if resp.status_code != 200:
                logger.warning(f"  [{canonical_id}] TwelveData returned {resp.status_code}")
                failed_assets.append(canonical_id)
                results['errors'] += 1
                continue

            data = resp.json()

            if 'values' not in data:
                error_msg = data.get('message', 'Unknown error')
                if 'not found' in error_msg.lower() or 'invalid' in error_msg.lower():
                    logger.debug(f"  [{canonical_id}] Symbol not found on TwelveData")
                else:
                    logger.warning(f"  [{canonical_id}] TwelveData error: {error_msg}")
                failed_assets.append(canonical_id)
                results['errors'] += 1
                continue

            # Build DataFrame from response
            rows = []
            for v in data['values']:
                try:
                    dt = datetime.strptime(v['datetime'], '%Y-%m-%d')
                    rows.append({
                        'timestamp': dt,
                        'open': float(v['open']),
                        'high': float(v['high']),
                        'low': float(v['low']),
                        'close': float(v['close']),
                        'volume': 0.0,  # FX doesn't have volume in TwelveData
                        'adj_close': float(v['close'])
                    })
                except Exception as e:
                    logger.debug(f"  [{canonical_id}] Parse error: {e}")
                    continue

            if rows:
                df = pd.DataFrame(rows)
                df.set_index('timestamp', inplace=True)
                inserted = insert_prices_canonical(conn, canonical_id, df, batch_id, 'TWELVEDATA_FX')
                if inserted > 0:
                    results['updated'] += 1
                    results['rows'] += inserted
                    logger.info(f"  [{canonical_id}] +{inserted} rows via TWELVEDATA_FX")
            else:
                failed_assets.append(canonical_id)

        except Exception as e:
            logger.warning(f"  [{canonical_id}] TwelveData FX error: {str(e)[:100]}")
            failed_assets.append(canonical_id)
            results['errors'] += 1

        # Progress update every 10 assets
        if (i + 1) % 10 == 0:
            logger.info(f"  Progress: {i+1}/{len(fx_assets)} FX assets, {results['api_calls']} API calls")

    if results['errors'] > len(fx_assets) * 0.5:
        results['status'] = 'PARTIAL'

    logger.info(f"  TwelveData FX ingest complete: {results['updated']} updated, {len(failed_assets)} failed, {results['api_calls']} API calls")
    return results, failed_assets


# =============================================================================
# PROVIDER: TWELVEDATA (EQUITY BACKUP)
# =============================================================================

def try_twelvedata_equity_ingest(
    conn,
    assets: List[Dict],
    batch_id: str
) -> Tuple[Dict, List[str]]:
    """
    Attempt equity data ingest via TwelveData API.

    TwelveData provides:
    - Global equities (US, EU, etc.)
    - Historical OHLCV data
    - Free tier: 800 calls/day, 8/min

    IoS-001 Compliance: Use 90% of free tier = 720/day, 7/min

    This is a BACKUP provider for when Yahoo is rate-limited.

    Returns: (results dict, list of failed asset IDs)
    """
    if not TWELVEDATA_API_KEY:
        logger.warning("TwelveData API key not configured")
        return {'status': 'NOT_CONFIGURED', 'updated': 0, 'rows': 0}, [a['canonical_id'] for a in assets]

    logger.info("=" * 60)
    logger.info("ATTEMPTING TWELVEDATA EQUITY INGEST (Backup Provider)")
    logger.info(f"Assets: {len(assets)}, Rate limit: {TWELVEDATA_RATE_PER_MIN}/min (90% of free tier)")
    logger.info(f"Daily limit: {TWELVEDATA_DAILY_LIMIT} calls (90% of 800)")
    logger.info("=" * 60)

    results = {'status': 'SUCCESS', 'updated': 0, 'rows': 0, 'errors': 0, 'api_calls': 0}
    failed_assets = []

    # Filter to only EQUITY assets
    equity_assets = [a for a in assets if a.get('asset_class') == 'EQUITY']
    non_equity_assets = [a for a in assets if a.get('asset_class') != 'EQUITY']

    logger.info(f"  Equity assets: {len(equity_assets)}, Non-equity: {len(non_equity_assets)}")

    # Mark non-equity assets as failed immediately
    for asset in non_equity_assets:
        failed_assets.append(asset['canonical_id'])

    if not equity_assets:
        logger.info("  No equity assets to fetch")
        return results, failed_assets

    # Check daily limit
    if len(equity_assets) > TWELVEDATA_DAILY_LIMIT:
        logger.warning(f"  Too many assets ({len(equity_assets)}) for daily limit ({TWELVEDATA_DAILY_LIMIT})")
        logger.warning(f"  Will process first {TWELVEDATA_DAILY_LIMIT} assets only")
        overflow_assets = equity_assets[TWELVEDATA_DAILY_LIMIT:]
        equity_assets = equity_assets[:TWELVEDATA_DAILY_LIMIT]
        for asset in overflow_assets:
            failed_assets.append(asset['canonical_id'])

    for i, asset in enumerate(equity_assets):
        # Rate limiting at START - IoS-001 compliant (ensures ALL code paths respect rate limit)
        if i > 0:  # Skip delay on first iteration
            time.sleep(TWELVEDATA_CALL_DELAY)

        canonical_id = asset['canonical_id']

        # Get last price date
        last_date = get_last_price_date(conn, canonical_id)
        if last_date:
            start_date = last_date + timedelta(days=1)
        else:
            start_date = date.today() - timedelta(days=30)

        if start_date > date.today():
            logger.debug(f"  [{canonical_id}] Up to date")
            continue

        # Map canonical_id to TwelveData symbol
        # Remove exchange suffixes for US stocks
        td_symbol = canonical_id
        if '.OL' in canonical_id:
            td_symbol = canonical_id.replace('.OL', ':OSL')  # Oslo Børs
        elif '.DE' in canonical_id:
            td_symbol = canonical_id.replace('.DE', ':XETR')  # German
        elif '.PA' in canonical_id:
            td_symbol = canonical_id.replace('.PA', ':XPAR')  # Paris

        try:
            url = 'https://api.twelvedata.com/time_series'
            params = {
                'symbol': td_symbol,
                'interval': '1day',
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': date.today().strftime('%Y-%m-%d'),
                'apikey': TWELVEDATA_API_KEY
            }

            resp = requests.get(url, params=params, timeout=30)
            results['api_calls'] += 1

            if resp.status_code == 429:
                logger.warning(f"  [{canonical_id}] TwelveData rate limited, stopping")
                # Stop processing to avoid burning more quota
                for remaining_asset in equity_assets[i:]:
                    failed_assets.append(remaining_asset['canonical_id'])
                results['status'] = 'RATE_LIMITED'
                break

            if resp.status_code != 200:
                logger.warning(f"  [{canonical_id}] TwelveData returned {resp.status_code}")
                failed_assets.append(canonical_id)
                results['errors'] += 1
                continue

            data = resp.json()

            if 'values' not in data:
                error_msg = data.get('message', 'Unknown error')
                if 'not found' in error_msg.lower() or 'invalid' in error_msg.lower():
                    logger.debug(f"  [{canonical_id}] Symbol not found on TwelveData")
                else:
                    logger.warning(f"  [{canonical_id}] TwelveData error: {error_msg}")
                failed_assets.append(canonical_id)
                results['errors'] += 1
                continue

            # Build DataFrame from response
            rows = []
            for v in data['values']:
                try:
                    dt = datetime.strptime(v['datetime'], '%Y-%m-%d')
                    rows.append({
                        'timestamp': dt,
                        'open': float(v['open']),
                        'high': float(v['high']),
                        'low': float(v['low']),
                        'close': float(v['close']),
                        'volume': float(v.get('volume', 0)),
                        'adj_close': float(v['close'])  # TwelveData doesn't provide adj_close
                    })
                except Exception as e:
                    logger.debug(f"  [{canonical_id}] Parse error: {e}")
                    continue

            if rows:
                df = pd.DataFrame(rows)
                df.set_index('timestamp', inplace=True)
                inserted = insert_prices_canonical(conn, canonical_id, df, batch_id, 'TWELVEDATA')
                if inserted > 0:
                    results['updated'] += 1
                    results['rows'] += inserted
                    logger.info(f"  [{canonical_id}] +{inserted} rows via TWELVEDATA")
            else:
                failed_assets.append(canonical_id)

        except Exception as e:
            logger.warning(f"  [{canonical_id}] TwelveData error: {str(e)[:100]}")
            failed_assets.append(canonical_id)
            results['errors'] += 1

        # Progress update every 50 assets
        if (i + 1) % 50 == 0:
            logger.info(f"  Progress: {i+1}/{len(equity_assets)} assets, {results['api_calls']} API calls")

    if results['errors'] > len(equity_assets) * 0.5:
        results['status'] = 'PARTIAL'

    logger.info(f"  TwelveData ingest complete: {results['updated']} updated, {len(failed_assets)} failed, {results['api_calls']} API calls")
    return results, failed_assets


# =============================================================================
# VERIFICATION LAYER
# =============================================================================

def verify_data_freshness(conn) -> Tuple[bool, int, List[str]]:
    """
    CRITICAL: Verify data is actually fresh after ingestion.

    This runs AFTER every ingest attempt.
    Returns: (is_fresh, stale_count, stale_asset_ids)
    """
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION: Checking Data Freshness")
    logger.info("=" * 60)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"""
            WITH asset_freshness AS (
                SELECT
                    p.canonical_id,
                    MAX(p.timestamp::date) as last_date,
                    CURRENT_DATE - MAX(p.timestamp::date) as days_stale
                FROM fhq_market.prices p
                JOIN fhq_meta.assets a ON p.canonical_id = a.canonical_id
                WHERE a.active_flag = TRUE  -- Only check ACTIVE assets
                GROUP BY p.canonical_id
            )
            SELECT
                canonical_id,
                last_date,
                days_stale
            FROM asset_freshness
            WHERE days_stale > {STALE_THRESHOLD_DAYS}
            ORDER BY days_stale DESC
        """)
        stale_assets = cur.fetchall()

    stale_count = len(stale_assets)
    stale_ids = [a['canonical_id'] for a in stale_assets]
    is_fresh = stale_count == 0

    if is_fresh:
        logger.info("VERIFICATION PASSED: All assets are fresh")
    else:
        logger.warning(f"VERIFICATION FAILED: {stale_count} assets are stale")
        for asset in stale_assets[:10]:  # Show first 10
            logger.warning(f"  - {asset['canonical_id']}: {asset['days_stale']} days stale (last: {asset['last_date']})")
        if stale_count > 10:
            logger.warning(f"  ... and {stale_count - 10} more")

    return is_fresh, stale_count, stale_ids


def get_freshness_summary(conn) -> Dict[str, Any]:
    """Get summary of data freshness by asset class."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"""
            WITH asset_freshness AS (
                SELECT
                    p.canonical_id,
                    a.asset_class,
                    MAX(p.timestamp::date) as last_date,
                    CURRENT_DATE - MAX(p.timestamp::date) as days_stale
                FROM fhq_market.prices p
                JOIN fhq_meta.assets a ON p.canonical_id = a.canonical_id
                GROUP BY p.canonical_id, a.asset_class
            )
            SELECT
                asset_class,
                COUNT(*) as total_assets,
                SUM(CASE WHEN days_stale <= {STALE_THRESHOLD_DAYS} THEN 1 ELSE 0 END) as fresh_assets,
                SUM(CASE WHEN days_stale > {STALE_THRESHOLD_DAYS} THEN 1 ELSE 0 END) as stale_assets,
                ROUND(100.0 * SUM(CASE WHEN days_stale <= {STALE_THRESHOLD_DAYS} THEN 1 ELSE 0 END) / COUNT(*), 1) as fresh_pct
            FROM asset_freshness
            GROUP BY asset_class
            ORDER BY asset_class
        """)
        return {row['asset_class']: dict(row) for row in cur.fetchall()}


# =============================================================================
# GOVERNANCE LOGGING
# =============================================================================

def log_governance_event(conn, event_type: str, details: Dict):
    """Log ingest event to governance table."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type, action_timestamp, action_by, details
                ) VALUES (%s, NOW(), 'STIG', %s)
            """, (f'IOS001_INGEST_{event_type}', json.dumps(details, default=str)))
            conn.commit()
    except Exception as e:
        logger.warning(f"Governance logging failed: {e}")
        conn.rollback()


def record_heartbeat(conn, status: str, details: Dict):
    """Record system heartbeat for monitoring."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.system_heartbeats (
                    component_name, status, details, recorded_at
                ) VALUES ('IOS001_BULLETPROOF_INGEST', %s, %s, NOW())
                ON CONFLICT (component_name) DO UPDATE SET
                    status = EXCLUDED.status,
                    details = EXCLUDED.details,
                    recorded_at = NOW()
            """, (status, json.dumps(details, default=str)))
            conn.commit()
    except Exception as e:
        logger.warning(f"Heartbeat recording failed: {e}")


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_bulletproof_ingest(
    asset_class: Optional[str] = None,
    dry_run: bool = False,
    skip_alpaca: bool = False,
    skip_yahoo: bool = False
) -> Dict:
    """
    Execute bulletproof daily price ingest.

    This function implements the 4-layer architecture:
    1. Multi-Provider Fallback (Alpaca -> Yahoo -> Alert)
    2. Verification After Every Run
    3. Alerting on ANY failure
    4. Governance logging
    """
    start_time = datetime.now(timezone.utc)

    logger.info("=" * 70)
    logger.info("IoS-001 BULLETPROOF DAILY PRICE INGEST")
    logger.info("=" * 70)
    logger.info(f"CEO Directive: CD-IOS-001-DAILY-INGEST-BULLETPROOF-001")
    logger.info(f"Executor: STIG (EC-003)")
    logger.info(f"Time: {start_time.isoformat()}")
    logger.info(f"Asset Class Filter: {asset_class or 'ALL'}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info(f"Canonical Source: fhq_market.prices (ONLY)")
    logger.info("=" * 70)

    conn = get_connection()
    batch_id = str(uuid.uuid4())

    results = {
        'batch_id': batch_id,
        'started_at': start_time.isoformat(),
        'asset_class_filter': asset_class or 'ALL',
        'dry_run': dry_run,
        'canonical_source': 'fhq_market.prices',
        'providers_attempted': [],
        'provider_results': {},
        'total_updated': 0,
        'total_rows': 0,
        'verification': {},
        'status': IngestStatus.FAILED.value
    }

    # Get canonical assets
    assets = get_canonical_assets(conn, asset_class)
    results['total_assets'] = len(assets)
    logger.info(f"Found {len(assets)} canonical assets")

    if dry_run:
        logger.info("DRY RUN - No data will be fetched or inserted")
        results['status'] = 'DRY_RUN'
        conn.close()
        return results

    # Track which assets still need data
    pending_assets = assets.copy()

    # Layer 1: Try Alpaca (Primary)
    if not skip_alpaca and ALPACA_API_KEY:
        results['providers_attempted'].append('ALPACA')
        alpaca_results, alpaca_failed = try_alpaca_ingest(conn, pending_assets, batch_id)
        results['provider_results']['ALPACA'] = alpaca_results
        results['total_updated'] += alpaca_results.get('updated', 0)
        results['total_rows'] += alpaca_results.get('rows', 0)

        # Update pending assets to only include failed ones
        pending_assets = [a for a in pending_assets if a['canonical_id'] in alpaca_failed]
        logger.info(f"Alpaca: Updated {alpaca_results.get('updated', 0)} assets, {len(pending_assets)} remaining")

    # Layer 1b: Try Yahoo for remaining assets
    if not skip_yahoo and pending_assets:
        results['providers_attempted'].append('YAHOO')
        yahoo_results, yahoo_failed = try_yahoo_ingest(conn, pending_assets, batch_id)
        results['provider_results']['YAHOO'] = yahoo_results
        results['total_updated'] += yahoo_results.get('updated', 0)
        results['total_rows'] += yahoo_results.get('rows', 0)

        pending_assets = [a for a in pending_assets if a['canonical_id'] in yahoo_failed]
        logger.info(f"Yahoo: Updated {yahoo_results.get('updated', 0)} assets, {len(pending_assets)} remaining")

    # Layer 1c: Try ECB for remaining FX assets (when Yahoo is rate-limited)
    fx_pending = [a for a in pending_assets if a.get('asset_class') == 'FX']
    if fx_pending:
        results['providers_attempted'].append('ECB')
        ecb_results, ecb_failed = try_ecb_fx_ingest(conn, fx_pending, batch_id)
        results['provider_results']['ECB'] = ecb_results
        results['total_updated'] += ecb_results.get('updated', 0)
        results['total_rows'] += ecb_results.get('rows', 0)

        # Update pending: remove FX that ECB handled, keep non-FX failures
        non_fx_pending = [a for a in pending_assets if a.get('asset_class') != 'FX']
        fx_still_failed = [a for a in fx_pending if a['canonical_id'] in ecb_failed]
        pending_assets = non_fx_pending + fx_still_failed
        logger.info(f"ECB: Updated {ecb_results.get('updated', 0)} FX assets, {len(pending_assets)} total remaining")

    # Layer 1d: Try TwelveData for remaining FX assets (non-EUR pairs)
    fx_still_pending = [a for a in pending_assets if a.get('asset_class') == 'FX']
    if fx_still_pending and TWELVEDATA_API_KEY:
        results['providers_attempted'].append('TWELVEDATA_FX')
        td_fx_results, td_fx_failed = try_twelvedata_fx_ingest(conn, fx_still_pending, batch_id)
        results['provider_results']['TWELVEDATA_FX'] = td_fx_results
        results['total_updated'] += td_fx_results.get('updated', 0)
        results['total_rows'] += td_fx_results.get('rows', 0)

        # Update pending: remove FX that TwelveData handled
        non_fx_pending = [a for a in pending_assets if a.get('asset_class') != 'FX']
        fx_still_failed = [a for a in fx_still_pending if a['canonical_id'] in td_fx_failed]
        pending_assets = non_fx_pending + fx_still_failed
        logger.info(f"TwelveData FX: Updated {td_fx_results.get('updated', 0)} FX assets, {len(pending_assets)} total remaining")

    # Layer 1e: Try TwelveData for remaining EQUITY assets (when Yahoo is rate-limited)
    equity_pending = [a for a in pending_assets if a.get('asset_class') == 'EQUITY']
    if equity_pending and TWELVEDATA_API_KEY:
        results['providers_attempted'].append('TWELVEDATA')
        td_results, td_failed = try_twelvedata_equity_ingest(conn, equity_pending, batch_id)
        results['provider_results']['TWELVEDATA'] = td_results
        results['total_updated'] += td_results.get('updated', 0)
        results['total_rows'] += td_results.get('rows', 0)

        # Update pending: remove equity that TwelveData handled
        non_equity_pending = [a for a in pending_assets if a.get('asset_class') != 'EQUITY']
        equity_still_failed = [a for a in equity_pending if a['canonical_id'] in td_failed]
        pending_assets = non_equity_pending + equity_still_failed
        logger.info(f"TwelveData: Updated {td_results.get('updated', 0)} equity assets, {len(pending_assets)} total remaining")

    # Layer 2: Verification
    is_fresh, stale_count, stale_ids = verify_data_freshness(conn)
    freshness_summary = get_freshness_summary(conn)

    results['verification'] = {
        'is_fresh': is_fresh,
        'stale_count': stale_count,
        'stale_assets': stale_ids[:20],  # First 20 for logging
        'freshness_by_class': freshness_summary
    }

    # Layer 3: Alerting
    if not is_fresh:
        send_alert(
            f"DATA VERIFICATION FAILED: {stale_count} assets still stale after ingest! "
            f"Updated: {results['total_updated']}, Rows: {results['total_rows']}",
            'CRITICAL'
        )
        log_governance_event(conn, 'VERIFICATION_FAILED', {
            'stale_count': stale_count,
            'batch_id': batch_id,
            'providers_attempted': results['providers_attempted']
        })

    if results['total_updated'] == 0 and len(assets) > 0:
        send_alert(
            "ALL INGEST METHODS FAILED - No assets were updated! Manual intervention required.",
            'CRITICAL'
        )
        results['status'] = IngestStatus.FAILED.value
    elif len(pending_assets) > 0:
        send_alert(
            f"PARTIAL INGEST: {len(pending_assets)} assets could not be updated via any provider",
            'WARNING'
        )
        results['status'] = IngestStatus.PARTIAL.value
    else:
        results['status'] = IngestStatus.SUCCESS.value

    # Layer 4: Governance logging
    results['completed_at'] = datetime.now(timezone.utc).isoformat()
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    results['elapsed_seconds'] = elapsed

    record_heartbeat(conn, results['status'], {
        'batch_id': batch_id,
        'updated': results['total_updated'],
        'rows': results['total_rows'],
        'verification_passed': is_fresh
    })

    log_governance_event(conn, results['status'], {
        'batch_id': batch_id,
        'total_updated': results['total_updated'],
        'total_rows': results['total_rows'],
        'providers': results['providers_attempted'],
        'verification_passed': is_fresh,
        'elapsed_seconds': elapsed
    })

    # Save evidence file
    evidence_file = EVIDENCE_DIR / f"BULLETPROOF_INGEST_{batch_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("BULLETPROOF INGEST COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Status: {results['status']}")
    logger.info(f"Assets Updated: {results['total_updated']}")
    logger.info(f"Rows Inserted: {results['total_rows']}")
    logger.info(f"Providers Used: {', '.join(results['providers_attempted'])}")
    logger.info(f"Verification: {'PASSED' if is_fresh else f'FAILED ({stale_count} stale)'}")
    logger.info(f"Elapsed: {elapsed:.1f}s")

    logger.info("\nFreshness by Asset Class:")
    for cls, data in freshness_summary.items():
        logger.info(f"  {cls}: {data['fresh_assets']}/{data['total_assets']} fresh ({data['fresh_pct']}%)")

    logger.info(f"\nEvidence: {evidence_file}")
    logger.info("=" * 70)

    conn.close()
    return results


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="IoS-001 Bulletproof Daily Price Ingest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python ios001_bulletproof_ingest.py                      # Full ingest
    python ios001_bulletproof_ingest.py --asset-class CRYPTO # Crypto only
    python ios001_bulletproof_ingest.py --dry-run            # Dry run
    python ios001_bulletproof_ingest.py --skip-alpaca        # Yahoo only
        """
    )
    parser.add_argument(
        "--asset-class",
        choices=['CRYPTO', 'EQUITY', 'FX'],
        help="Filter by asset class"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without executing"
    )
    parser.add_argument(
        "--skip-alpaca",
        action="store_true",
        help="Skip Alpaca and use Yahoo only"
    )
    parser.add_argument(
        "--skip-yahoo",
        action="store_true",
        help="Skip Yahoo and use Alpaca only"
    )

    args = parser.parse_args()

    results = run_bulletproof_ingest(
        asset_class=args.asset_class,
        dry_run=args.dry_run,
        skip_alpaca=args.skip_alpaca,
        skip_yahoo=args.skip_yahoo
    )

    # Exit with appropriate code
    if results['status'] == IngestStatus.SUCCESS.value:
        sys.exit(0)
    elif results['status'] == IngestStatus.PARTIAL.value:
        sys.exit(0)  # Partial is acceptable
    else:
        sys.exit(1)
