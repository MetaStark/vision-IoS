#!/usr/bin/env python3
"""
CoinGecko CRYPTO Data Repair
============================

Authority: CEO-DIR-2025-DATA-001
Executor: STIG (EC-003)

Uses CoinGecko free API to repair CRYPTO price data when Yahoo is rate-limited.
CoinGecko provides proper USD market cap and volume data.

Rate Limits: 10-50 calls/min on free tier
"""

import os
import sys
import json
import uuid
import hashlib
import logging
import time
import requests
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
from typing import Dict, List, Optional

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
logger = logging.getLogger("COINGECKO_REPAIR")

# CoinGecko API
COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"

# Mapping from our canonical IDs to CoinGecko IDs
COINGECKO_ID_MAP = {
    'BTC-USD': 'bitcoin',
    'ETH-USD': 'ethereum',
    'SOL-USD': 'solana',
    'XRP-USD': 'ripple',
    'DOGE-USD': 'dogecoin',
    'ADA-USD': 'cardano',
    'AVAX-USD': 'avalanche-2',
    'DOT-USD': 'polkadot',
    'LINK-USD': 'chainlink',
    'LTC-USD': 'litecoin',
    'BCH-USD': 'bitcoin-cash',
    'UNI-USD': 'uniswap',
    'AAVE-USD': 'aave',
    'XTZ-USD': 'tezos',
    'SHIB-USD': 'shiba-inu',
    'GRT-USD': 'the-graph',
    'CRV-USD': 'curve-dao-token',
    'MATIC-USD': 'matic-network',
    'ATOM-USD': 'cosmos',
    'NEAR-USD': 'near',
}

# Volume threshold
CRYPTO_VOLUME_MIN_THRESHOLD = 1000


def get_connection():
    return psycopg2.connect(**DB_CONFIG, options='-c client_encoding=UTF8')


def get_missing_dates(conn, canonical_id: str, start_date: date, end_date: date) -> List[date]:
    """Find dates with missing or low-volume data."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT timestamp::date as date
            FROM fhq_market.prices
            WHERE canonical_id = %s
            AND timestamp::date >= %s
            AND timestamp::date <= %s
            AND volume >= %s
        """, (canonical_id, start_date, end_date, CRYPTO_VOLUME_MIN_THRESHOLD))
        existing_dates = {row[0] for row in cur.fetchall()}

    all_dates = []
    current = start_date
    while current <= end_date:
        all_dates.append(current)
        current += timedelta(days=1)

    missing = [d for d in all_dates if d not in existing_dates]
    return missing


def fetch_coingecko_history(coin_id: str, days: int = 30) -> Optional[pd.DataFrame]:
    """Fetch historical data from CoinGecko."""
    url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
    params = {
        'vs_currency': 'usd',
        'days': days,
        'interval': 'daily'
    }

    try:
        resp = requests.get(url, params=params, timeout=30)

        if resp.status_code == 429:
            logger.warning("  CoinGecko rate limited, waiting 60s...")
            time.sleep(60)
            resp = requests.get(url, params=params, timeout=30)

        if resp.status_code != 200:
            logger.warning(f"  CoinGecko returned {resp.status_code}")
            return None

        data = resp.json()

        # Parse prices, market_caps, total_volumes
        prices = data.get('prices', [])
        volumes = data.get('total_volumes', [])

        if not prices:
            return None

        # Build DataFrame
        rows = []
        for i, (ts, price) in enumerate(prices):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            volume = volumes[i][1] if i < len(volumes) else 0
            rows.append({
                'timestamp': dt.replace(tzinfo=None),
                'date': dt.date(),
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume,
                'adj_close': price
            })

        df = pd.DataFrame(rows)
        df.set_index('timestamp', inplace=True)
        return df

    except Exception as e:
        logger.error(f"  CoinGecko error: {e}")
        return None


def insert_prices(conn, canonical_id: str, df: pd.DataFrame, batch_id: str) -> int:
    """Insert price data."""
    if df is None or df.empty:
        return 0

    rows = []
    for idx, row in df.iterrows():
        timestamp = idx

        close_val = float(row['close'])
        volume_val = float(row.get('volume', 0))

        if close_val <= 0:
            continue

        # Volume sanity check
        if volume_val < CRYPTO_VOLUME_MIN_THRESHOLD:
            logger.debug(f"    Skipping {timestamp} - volume {volume_val} too low")
            continue

        open_val = float(row.get('open', close_val))
        high_val = float(row.get('high', close_val))
        low_val = float(row.get('low', close_val))
        adj_close_val = float(row.get('adj_close', close_val))

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
            'COINGECKO_REPAIR',
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
                WHERE fhq_market.prices.volume < %s
            """
            # Need to handle the WHERE clause differently
            # Use a simpler approach
            for row in rows:
                cur.execute("""
                    INSERT INTO fhq_market.prices (
                        id, asset_id, canonical_id, timestamp, open, high, low, close, volume,
                        source, staging_id, data_hash, gap_filled, interpolated, quality_score,
                        batch_id, canonicalized_by, adj_close
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (canonical_id, timestamp) DO UPDATE SET
                        volume = EXCLUDED.volume,
                        adj_close = EXCLUDED.adj_close,
                        data_hash = EXCLUDED.data_hash,
                        source = EXCLUDED.source
                    WHERE fhq_market.prices.volume < 1000
                """, row)
            conn.commit()
        return len(rows)
    except Exception as e:
        conn.rollback()
        logger.error(f"Insert error: {e}")
        return 0


def run_coingecko_repair():
    """Run CoinGecko-based CRYPTO repair."""
    start_time = datetime.now(timezone.utc)
    batch_id = str(uuid.uuid4())

    logger.info("=" * 70)
    logger.info("COINGECKO CRYPTO DATA REPAIR")
    logger.info("=" * 70)
    logger.info(f"Authority: CEO-DIR-2025-DATA-001")
    logger.info(f"Executor: STIG (EC-003)")
    logger.info(f"Batch ID: {batch_id}")
    logger.info("=" * 70)

    conn = get_connection()

    results = {
        'batch_id': batch_id,
        'started_at': start_time.isoformat(),
        'assets_processed': 0,
        'rows_inserted': 0,
        'errors': []
    }

    # Process each crypto asset
    end_date = date.today()
    start_date = date(2025, 12, 1)

    for canonical_id, coin_id in COINGECKO_ID_MAP.items():
        logger.info(f"\nProcessing {canonical_id} ({coin_id})...")

        # Check missing dates
        missing = get_missing_dates(conn, canonical_id, start_date, end_date)
        if not missing:
            logger.info(f"  No missing dates for {canonical_id}")
            continue

        logger.info(f"  Missing/low-volume dates: {len(missing)}")

        # Fetch from CoinGecko
        df = fetch_coingecko_history(coin_id, days=35)
        if df is None or df.empty:
            logger.warning(f"  No data from CoinGecko for {canonical_id}")
            results['errors'].append(f"{canonical_id}: No CoinGecko data")
            continue

        # Filter to missing dates only
        df['date_only'] = df.index.date
        df_filtered = df[df['date_only'].isin(missing)]

        if df_filtered.empty:
            logger.info(f"  No matching dates in CoinGecko data")
            continue

        # Insert
        rows = insert_prices(conn, canonical_id, df_filtered, batch_id)
        if rows > 0:
            results['assets_processed'] += 1
            results['rows_inserted'] += rows
            logger.info(f"  Inserted {rows} rows for {canonical_id}")

        # Rate limiting - be nice to CoinGecko
        time.sleep(3)

    # Summary
    results['completed_at'] = datetime.now(timezone.utc).isoformat()

    logger.info("\n" + "=" * 70)
    logger.info("COINGECKO REPAIR COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Assets Processed: {results['assets_processed']}")
    logger.info(f"Rows Inserted: {results['rows_inserted']}")
    logger.info(f"Errors: {len(results['errors'])}")
    logger.info("=" * 70)

    # Save evidence
    evidence_file = EVIDENCE_DIR / f"COINGECKO_REPAIR_{batch_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Evidence: {evidence_file}")

    conn.close()
    return results


if __name__ == "__main__":
    results = run_coingecko_repair()
    sys.exit(0 if results['rows_inserted'] > 0 else 1)
