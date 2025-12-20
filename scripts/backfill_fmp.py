#!/usr/bin/env python3
"""
5-Year Equity Backfill via Financial Modeling Prep (FMP)
=========================================================
FMP has generous historical data access even on free tier.
Endpoint: /api/v3/historical-price-full/{symbol}
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

FMP_API_KEY = os.getenv('FMP_API_KEY')
EQUITY_UNIVERSE = ['NVDA', 'AAPL', 'MSFT', 'SPY', 'QQQ']

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_fmp_historical(symbol: str) -> list:
    """Fetch historical daily data from FMP."""
    # Calculate date range (5 years + buffer)
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=5*365+30)

    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}"
    params = {
        "from": str(start_date),
        "to": str(end_date),
        "apikey": FMP_API_KEY
    }

    print(f"  Fetching {symbol} from FMP...")
    print(f"    Date range: {start_date} to {end_date}")

    try:
        resp = requests.get(url, params=params, timeout=60)
        data = resp.json()

        if isinstance(data, dict) and "Error Message" in data:
            print(f"    [ERROR] {data['Error Message']}")
            return []

        if isinstance(data, dict) and "historical" in data:
            historical = data["historical"]
        else:
            print(f"    [ERROR] Unexpected response format")
            print(f"    Response: {str(data)[:200]}")
            return []

        bars = []
        for item in historical:
            try:
                ts = datetime.strptime(item['date'], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                bars.append({
                    'timestamp': ts,
                    'open': float(item['open']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'close': float(item['close']),
                    'volume': int(item.get('volume', 0))
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
            'fmp_backfill',
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

    bars = fetch_fmp_historical(symbol)

    if not bars:
        return {'asset': symbol, 'status': 'NO_DATA', 'inserted': 0}

    # Insert all bars
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
    print("CEO DIRECTIVE: 5-YEAR EQUITY BACKFILL - FMP")
    print("=" * 60)
    print(f"Assets: {', '.join(EQUITY_UNIVERSE)}")
    print(f"API Key: {FMP_API_KEY[:8]}...")

    results = []

    for i, asset in enumerate(EQUITY_UNIVERSE):
        if i > 0:
            print("\n  [RATE LIMIT] Waiting 2s...")
            time.sleep(2)

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
        # Single asset mode
        symbol = sys.argv[1].upper()
        result = backfill_asset(symbol)
        print(f"\nResult: {result}")
        verify_data()
    else:
        main()
