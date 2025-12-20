#!/usr/bin/env python3
"""
5-Year Equity Backfill via TwelveData
======================================
TwelveData time_series endpoint for historical OHLCV data.
Free tier: 800 API calls/day, 8 calls/minute
"""

import os
import sys
import uuid
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env', override=True)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

TWELVEDATA_API_KEY = os.getenv('TWELVEDATA_API_KEY')
EQUITY_UNIVERSE = ['NVDA', 'AAPL', 'MSFT', 'SPY', 'QQQ']

# Asset UUIDs from existing data
ASSET_IDS = {
    'NVDA': '11013883-7876-5b41-a4fb-6be9ac3a4939',
    'AAPL': '5e5024ad-e167-511b-b3a2-006e0c965ce8',
    'MSFT': '857b9211-0bd7-5571-97ea-270b8b023e60',
    'SPY': '8a368075-3fc6-5a35-acb8-1ddc32878238',
    'QQQ': '218f7bf7-f667-5421-8cea-e06c1a7d4287'
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_twelvedata_historical(symbol: str) -> list:
    """Fetch historical daily data from TwelveData."""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=5*365+30)

    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": "1day",
        "start_date": str(start_date),
        "end_date": str(end_date),
        "outputsize": 5000,  # Max allowed
        "apikey": TWELVEDATA_API_KEY
    }

    print(f"  Fetching {symbol} from TwelveData...")
    print(f"    Date range: {start_date} to {end_date}")

    try:
        resp = requests.get(url, params=params, timeout=60)
        data = resp.json()

        if data.get("status") == "error":
            print(f"    [ERROR] {data.get('message', 'Unknown error')}")
            return []

        if "code" in data and data["code"] != 200:
            print(f"    [ERROR] Code {data['code']}: {data.get('message', '')}")
            return []

        values = data.get("values", [])
        if not values:
            print(f"    [ERROR] No values in response")
            return []

        bars = []
        for item in values:
            try:
                ts = datetime.strptime(item['datetime'], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                bars.append({
                    'timestamp': ts,
                    'open': float(item['open']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'close': float(item['close']),
                    'volume': int(float(item.get('volume', 0)))
                })
            except (KeyError, ValueError) as e:
                continue

        # Sort by date ascending
        bars.sort(key=lambda x: x['timestamp'])
        print(f"    Fetched {len(bars)} daily bars")

        if bars:
            print(f"    Range: {bars[0]['timestamp'].date()} to {bars[-1]['timestamp'].date()}")

        return bars

    except Exception as e:
        print(f"    [ERROR] Request failed: {e}")
        return []


import hashlib

def compute_data_hash(bar: dict) -> str:
    """Compute SHA256 hash of OHLCV data."""
    data_str = f"{bar['open']}{bar['high']}{bar['low']}{bar['close']}{bar['volume']}"
    return hashlib.sha256(data_str.encode()).hexdigest()[:32]


def insert_bars(symbol: str, bars: list) -> int:
    """Insert OHLCV bars into fhq_market.prices."""
    if not bars:
        return 0

    asset_uuid = ASSET_IDS.get(symbol)
    if not asset_uuid:
        print(f"    [ERROR] No asset_id found for {symbol}")
        return 0

    conn = get_connection()
    cur = conn.cursor()

    # Generate batch_id for this backfill
    batch_id = str(uuid.uuid4())

    values = []
    for bar in bars:
        data_hash = compute_data_hash(bar)
        values.append((
            str(uuid.uuid4()),  # id
            asset_uuid,         # asset_id (UUID)
            symbol,             # canonical_id
            bar['timestamp'],   # timestamp
            float(bar['open']),
            float(bar['high']),
            float(bar['low']),
            float(bar['close']),
            float(bar['volume']),
            'twelvedata_backfill',  # source
            data_hash,          # data_hash
            batch_id,           # batch_id
            datetime.now(timezone.utc),  # canonicalized_at
            'STIG_BACKFILL'     # canonicalized_by
        ))

    try:
        execute_values(cur, """
            INSERT INTO fhq_market.prices
            (id, asset_id, canonical_id, timestamp, open, high, low, close, volume, source, data_hash, batch_id, canonicalized_at, canonicalized_by)
            VALUES %s
            ON CONFLICT (canonical_id, timestamp) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                source = EXCLUDED.source,
                data_hash = EXCLUDED.data_hash
        """, values)
        conn.commit()
        inserted = len(values)
        print(f"    [OK] Inserted {inserted} records")
    except Exception as e:
        print(f"    [ERROR] Insert failed: {e}")
        conn.rollback()
        inserted = 0
    finally:
        cur.close()
        conn.close()

    return inserted


def backfill_asset(symbol: str) -> dict:
    """Backfill historical data for a single asset."""
    print(f"\n[{symbol}] Starting 5-year backfill...")

    bars = fetch_twelvedata_historical(symbol)

    if not bars:
        return {'asset': symbol, 'status': 'NO_DATA', 'inserted': 0}

    inserted = insert_bars(symbol, bars)

    if bars:
        earliest = min(b['timestamp'] for b in bars).date()
        latest = max(b['timestamp'] for b in bars).date()
        days = (latest - earliest).days
    else:
        earliest = latest = None
        days = 0

    return {
        'asset': symbol,
        'status': 'SUCCESS' if inserted > 0 else 'FAILED',
        'inserted': inserted,
        'days': days,
        'earliest': str(earliest) if earliest else None,
        'latest': str(latest) if latest else None
    }


def verify_data():
    """Verify data after backfill."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    conn = get_connection()
    cur = conn.cursor()

    for asset in EQUITY_UNIVERSE:
        cur.execute("""
            SELECT
                COUNT(*) as records,
                MIN(timestamp)::date as earliest,
                MAX(timestamp)::date as latest,
                (MAX(timestamp)::date - MIN(timestamp)::date) as days
            FROM fhq_market.prices
            WHERE canonical_id = %s
        """, (asset,))
        row = cur.fetchone()
        meets_req = "OK" if row[3] and row[3] >= 1800 else "NEED MORE"
        print(f"  {asset}: {row[0]} records, {row[3]} days ({row[1]} to {row[2]}) [{meets_req}]")

    cur.close()
    conn.close()


def main():
    print("=" * 60)
    print("CEO DIRECTIVE: 5-YEAR EQUITY BACKFILL - TWELVEDATA")
    print("=" * 60)
    print(f"Assets: {', '.join(EQUITY_UNIVERSE)}")
    print(f"API Key: {TWELVEDATA_API_KEY[:8]}...")

    results = []

    for i, asset in enumerate(EQUITY_UNIVERSE):
        if i > 0:
            # Rate limit: 8 calls/minute
            print("\n  [RATE LIMIT] Waiting 10s...")
            time.sleep(10)

        result = backfill_asset(asset)
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)

    total_inserted = 0
    for r in results:
        status = "OK" if r['status'] == 'SUCCESS' else "FAIL"
        print(f"  [{status}] {r['asset']}: {r.get('days', 0)} days, {r.get('inserted', 0)} records")
        total_inserted += r.get('inserted', 0)

    print(f"\nTotal Inserted: {total_inserted}")

    verify_data()

    print("\n[COMPLETE] 5-year backfill finished.")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
        result = backfill_asset(symbol)
        print(f"\nResult: {result}")
        verify_data()
    else:
        main()
