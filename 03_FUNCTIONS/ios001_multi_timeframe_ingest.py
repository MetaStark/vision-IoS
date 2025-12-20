#!/usr/bin/env python3
"""
IoS-001 MULTI-TIMEFRAME PRICE INGEST
====================================
CEO Directive: Multi-resolution alpha discovery per ADR-001

Supports canonical timeframes:
- 1m (minute) - Alpaca only
- 1h (hour) - Alpaca + yfinance
- 1d (daily) - All providers
- 1w (weekly) - Aggregated from daily

Data Sources:
- Alpaca (primary for intraday)
- Yahoo Finance (fallback for daily)

Authority: ADR-001 defines canonical timeframes: 1S, 1M, 1H, 6H, 12H, 1D, 1W, 1MONTH
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal
import hashlib

import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
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

# Alpaca API
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY", "") or os.getenv("ALPACA_SECRET", "")
ALPACA_BASE_URL = "https://data.alpaca.markets"

# Timeframe configurations per ADR-001
TIMEFRAMES = {
    '1m': {
        'alpaca_tf': '1Min',
        'lookback_days': 7,  # 7 days of minute data
        'batch_days': 1,
        'assets': ['crypto', 'equity']  # What asset classes support this
    },
    '1h': {
        'alpaca_tf': '1Hour',
        'lookback_days': 30,  # 30 days of hourly data
        'batch_days': 7,
        'assets': ['crypto', 'equity']
    },
    '1d': {
        'alpaca_tf': '1Day',
        'lookback_days': 365,  # 1 year of daily data
        'batch_days': 30,
        'assets': ['crypto', 'equity', 'fx']
    },
    '1w': {
        'alpaca_tf': None,  # Aggregated from daily
        'lookback_days': 365 * 3,  # 3 years of weekly
        'batch_days': 90,
        'assets': ['crypto', 'equity', 'fx']
    }
}

# Assets to ingest (core universe)
CRYPTO_SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD']
EQUITY_SYMBOLS = ['SPY', 'QQQ', 'NVDA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'TSLA']

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | IOS001-MTF | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"C:/fhq-market-system/vision-ios/logs/ios001_mtf_ingest_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# ALPACA CLIENT
# =============================================================================

class AlpacaDataClient:
    """Alpaca Market Data API client for multi-timeframe data."""

    def __init__(self):
        self.api_key = ALPACA_API_KEY
        self.secret_key = ALPACA_SECRET
        self.base_url = ALPACA_BASE_URL

        if not self.api_key or not self.secret_key:
            logger.warning("Alpaca API keys not configured")

    def _get_headers(self) -> Dict[str, str]:
        return {
            'APCA-API-KEY-ID': self.api_key,
            'APCA-API-SECRET-KEY': self.secret_key
        }

    def get_crypto_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> List[Dict]:
        """Fetch crypto bars from Alpaca."""
        import requests

        # Convert symbol format: BTC/USD -> BTCUSD
        alpaca_symbol = symbol.replace('/', '')

        url = f"{self.base_url}/v1beta3/crypto/us/bars"
        params = {
            'symbols': alpaca_symbol,
            'timeframe': timeframe,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'limit': 10000
        }

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                bars = data.get('bars', {}).get(alpaca_symbol, [])
                return [
                    {
                        'timestamp': bar['t'],
                        'open': float(bar['o']),
                        'high': float(bar['h']),
                        'low': float(bar['l']),
                        'close': float(bar['c']),
                        'volume': float(bar['v'])
                    }
                    for bar in bars
                ]
            else:
                logger.warning(f"Alpaca API error {response.status_code}: {response.text[:200]}")
                return []
        except Exception as e:
            logger.error(f"Alpaca crypto bars failed: {e}")
            return []

    def get_stock_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> List[Dict]:
        """Fetch stock bars from Alpaca."""
        import requests

        url = f"{self.base_url}/v2/stocks/{symbol}/bars"
        params = {
            'timeframe': timeframe,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'limit': 10000,
            'feed': 'iex'  # Use IEX feed (free)
        }

        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                bars = data.get('bars', [])
                return [
                    {
                        'timestamp': bar['t'],
                        'open': float(bar['o']),
                        'high': float(bar['h']),
                        'low': float(bar['l']),
                        'close': float(bar['c']),
                        'volume': float(bar['v'])
                    }
                    for bar in bars
                ]
            else:
                logger.warning(f"Alpaca stock API error {response.status_code}: {response.text[:200]}")
                return []
        except Exception as e:
            logger.error(f"Alpaca stock bars failed: {e}")
            return []

# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def get_connection():
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD
    )

def insert_price_data(conn, listing_id: str, resolution: str, bars: List[Dict], source: str = 'ALPACA'):
    """Insert price bars into fhq_data.price_series."""
    if not bars:
        return 0

    rows = []
    for bar in bars:
        # Parse timestamp
        if isinstance(bar['timestamp'], str):
            ts = datetime.fromisoformat(bar['timestamp'].replace('Z', '+00:00'))
        else:
            ts = bar['timestamp']

        rows.append((
            listing_id,
            ts.date() if resolution in ['1d', '1w'] else ts,
            bar['open'],
            bar['high'],
            bar['low'],
            bar['close'],
            bar['close'],  # adj_close
            bar['volume'],
            'SPOT',
            resolution,
            source,
            1  # adr_epoch
        ))

    with conn.cursor() as cur:
        # Use ON CONFLICT to handle duplicates
        execute_values(
            cur,
            """
            INSERT INTO fhq_data.price_series
                (listing_id, date, open, high, low, close, adj_close, volume, price_type, resolution, data_source, adr_epoch)
            VALUES %s
            ON CONFLICT (listing_id, date, resolution) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                adj_close = EXCLUDED.adj_close,
                volume = EXCLUDED.volume,
                data_source = EXCLUDED.data_source
            """,
            rows,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        conn.commit()

    return len(rows)

def ensure_resolution_column(conn):
    """Ensure resolution column exists in price_series."""
    with conn.cursor() as cur:
        # Check if unique constraint exists for (listing_id, date, resolution)
        cur.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname = 'price_series_listing_date_resolution_unique'
        """)
        if not cur.fetchone():
            try:
                cur.execute("""
                    ALTER TABLE fhq_data.price_series
                    ADD CONSTRAINT price_series_listing_date_resolution_unique
                    UNIQUE (listing_id, date, resolution)
                """)
                conn.commit()
                logger.info("Added unique constraint for multi-resolution support")
            except Exception as e:
                conn.rollback()
                logger.warning(f"Could not add constraint (may already exist): {e}")

# =============================================================================
# MAIN INGEST LOGIC
# =============================================================================

def ingest_timeframe(conn, client: AlpacaDataClient, timeframe: str, symbols: List[str], asset_class: str):
    """Ingest data for a specific timeframe."""
    tf_config = TIMEFRAMES.get(timeframe)
    if not tf_config:
        logger.error(f"Unknown timeframe: {timeframe}")
        return

    if asset_class not in tf_config['assets']:
        logger.info(f"Timeframe {timeframe} not supported for {asset_class}")
        return

    alpaca_tf = tf_config['alpaca_tf']
    lookback = tf_config['lookback_days']

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback)

    logger.info(f"Ingesting {timeframe} data for {len(symbols)} {asset_class} assets")
    logger.info(f"  Range: {start.date()} to {end.date()}")

    total_rows = 0
    for symbol in symbols:
        # Map symbol to listing_id format
        if asset_class == 'crypto':
            listing_id = symbol.replace('/', '-')  # BTC/USD -> BTC-USD
            bars = client.get_crypto_bars(symbol, alpaca_tf, start, end)
        else:
            listing_id = symbol
            bars = client.get_stock_bars(symbol, alpaca_tf, start, end)

        if bars:
            rows = insert_price_data(conn, listing_id, timeframe, bars)
            total_rows += rows
            logger.info(f"  {symbol}: {rows} bars inserted")
        else:
            logger.warning(f"  {symbol}: No data received")

        time.sleep(0.5)  # Rate limiting

    logger.info(f"Completed {timeframe}: {total_rows} total rows")
    return total_rows

def run_ingest(timeframes: List[str] = None, asset_classes: List[str] = None):
    """Run multi-timeframe ingest."""
    if timeframes is None:
        timeframes = ['1h', '1d']  # Default to hourly and daily
    if asset_classes is None:
        asset_classes = ['crypto', 'equity']

    conn = get_connection()
    client = AlpacaDataClient()

    logger.info("=" * 60)
    logger.info("IoS-001 MULTI-TIMEFRAME INGEST")
    logger.info("=" * 60)
    logger.info(f"Timeframes: {timeframes}")
    logger.info(f"Asset Classes: {asset_classes}")

    # Ensure database supports multi-resolution
    ensure_resolution_column(conn)

    results = {}

    for tf in timeframes:
        for ac in asset_classes:
            if ac == 'crypto':
                symbols = CRYPTO_SYMBOLS
            elif ac == 'equity':
                symbols = EQUITY_SYMBOLS
            else:
                continue

            key = f"{tf}_{ac}"
            try:
                rows = ingest_timeframe(conn, client, tf, symbols, ac)
                results[key] = rows or 0
            except Exception as e:
                logger.error(f"Failed {key}: {e}")
                results[key] = 0

    conn.close()

    # Summary
    logger.info("=" * 60)
    logger.info("INGEST SUMMARY")
    logger.info("=" * 60)
    for key, rows in results.items():
        logger.info(f"  {key}: {rows} rows")
    logger.info("=" * 60)

    return results

# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='IoS-001 Multi-Timeframe Ingest')
    parser.add_argument('--timeframes', '-t', nargs='+', default=['1h', '1d'],
                        choices=['1m', '1h', '1d', '1w'],
                        help='Timeframes to ingest')
    parser.add_argument('--assets', '-a', nargs='+', default=['crypto', 'equity'],
                        choices=['crypto', 'equity', 'fx'],
                        help='Asset classes to ingest')
    args = parser.parse_args()

    os.makedirs('C:/fhq-market-system/vision-ios/logs', exist_ok=True)

    run_ingest(args.timeframes, args.assets)
