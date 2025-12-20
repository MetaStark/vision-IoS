#!/usr/bin/env python3
"""
5-Year Equity Backfill via Alpha Vantage
=========================================
Using Alpha Vantage TIME_SERIES_DAILY_ADJUSTED for reliable historical data.
Rate limit: 5 calls/minute (free tier), but we have a premium key.
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

ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API_KEY')
EQUITY_UNIVERSE = ['NVDA', 'AAPL', 'MSFT', 'SPY', 'QQQ']

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_alphavantage_daily(symbol: str) -> list:
    """Fetch full historical daily data from Alpha Vantage."""
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "full",  # Full history (20+ years)
        "apikey": ALPHAVANTAGE_API_KEY
    }

    print(f"  Fetching {symbol} from Alpha Vantage...")

    try:
        resp = requests.get(url, params=params, timeout=60)
        data = resp.json()

        if "Error Message" in data:
            print(f"    [ERROR] API Error: {data['Error Message']}")
            return []

        if "Note" in data:
            print(f"    [WARN] Rate limit: {data['Note']}")
            return []

        if "Information" in data:
            print(f"    [INFO] {data['Information']}")
            return []

        time_series = data.get("Time Series (Daily)", {})
        if not time_series:
            print(f"    [ERROR] No time series data returned")
            return []

        bars = []
        for date_str, values in time_series.items():
            try:
                ts = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                bars.append({
                    'timestamp': ts,
                    'open': float(values['1. open']),
                    'high': float(values['2. high']),
                    'low': float(values['3. low']),
                    'close': float(values['4. close']),
                    'volume': int(float(values['6. volume']))  # adjusted volume
                })
            except (KeyError, ValueError) as e:
                continue

        # Sort by date ascending
        bars.sort(key=lambda x: x['timestamp'])
        print(f"    Fetched {len(bars)} daily bars")
        return bars

    except Exception as e:
        print(f"    [ERROR] Request failed: {e}")
        return []


def insert_bars(asset_id: str, bars: list) -> int:
    """Insert OHLCV bars into fhq_market.prices."""
    if not bars:
        return 0

    conn = get_connection()
    cur = conn.cursor()

    values = []
    for bar in bars:
        values.append((
            str(uuid.uuid4()),
            asset_id,
            bar['timestamp'],
            float(bar['open']),
            float(bar['high']),
            float(bar['low']),
            float(bar['close']),
            int(bar['volume']),
            'alphavantage_backfill',
            datetime.now(timezone.utc),
            'STIG_BACKFILL'
        ))

    try:
        execute_values(cur, """
            INSERT INTO fhq_market.prices
            (id, canonical_id, timestamp, open, high, low, close, volume, source, canonicalized_at, canonicalized_by)
            VALUES %s
            ON CONFLICT (canonical_id, timestamp) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                source = EXCLUDED.source
        """, values)
        conn.commit()
        inserted = len(values)
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
    print(f"\n[{symbol}] Starting backfill...")

    bars = fetch_alphavantage_daily(symbol)

    if not bars:
        return {'asset': symbol, 'status': 'NO_DATA', 'inserted': 0}

    # Filter to last 5 years
    cutoff = datetime.now(timezone.utc) - timedelta(days=5*365+30)
    recent_bars = [b for b in bars if b['timestamp'] >= cutoff]
    print(f"    Bars in last 5 years: {len(recent_bars)}")

    # Insert
    inserted = insert_bars(symbol, recent_bars)
    print(f"    Inserted: {inserted} records")

    earliest = min(b['timestamp'] for b in recent_bars).date()
    latest = max(b['timestamp'] for b in recent_bars).date()
    days = (latest - earliest).days

    return {
        'asset': symbol,
        'status': 'SUCCESS',
        'inserted': inserted,
        'days': days,
        'earliest': str(earliest),
        'latest': str(latest)
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
    print("5-YEAR EQUITY BACKFILL - ALPHA VANTAGE")
    print("=" * 60)
    print(f"Assets: {', '.join(EQUITY_UNIVERSE)}")
    print(f"API Key: {ALPHAVANTAGE_API_KEY[:8]}...")

    results = []

    for i, asset in enumerate(EQUITY_UNIVERSE):
        if i > 0:
            print("\n  [RATE LIMIT] Waiting 15s...")
            time.sleep(15)

        result = backfill_asset(asset)
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_inserted = 0
    for r in results:
        status = "OK" if r['status'] == 'SUCCESS' else "FAIL"
        print(f"  [{status}] {r['asset']}: {r.get('days', 0)} days, {r.get('inserted', 0)} records")
        total_inserted += r.get('inserted', 0)

    print(f"\nTotal Inserted: {total_inserted}")

    verify_data()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Single asset mode
        symbol = sys.argv[1].upper()
        result = backfill_asset(symbol)
        print(f"\nResult: {result}")
        verify_data()
    else:
        main()
