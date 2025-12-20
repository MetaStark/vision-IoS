#!/usr/bin/env python3
"""
Single Asset Backfill - For rate limiting situations
Usage: python backfill_single_asset.py NVDA
"""
import os
import sys
import uuid
import time
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env', override=True)

import yfinance as yf

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def backfill_asset(symbol: str):
    print(f"Backfilling {symbol}...")

    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=5 * 365 + 30)

    print(f"  Date range: {start_date} to {end_date}")
    print(f"  Fetching from Yahoo Finance...")

    # Use download function instead
    try:
        df = yf.download(symbol, start=str(start_date), end=str(end_date), progress=False)

        if df.empty:
            print(f"  [ERROR] No data returned")
            return

        print(f"  Fetched: {len(df)} bars")

        # Prepare data
        conn = get_connection()
        cur = conn.cursor()

        values = []
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            values.append((
                str(uuid.uuid4()),
                symbol,
                ts,
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']) if row['Volume'] > 0 else 0,
                'yfinance_backfill',
                datetime.now(timezone.utc),
                'STIG_BACKFILL'
            ))

        print(f"  Inserting {len(values)} records...")

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
        print(f"  [SUCCESS] Inserted {len(values)} records")

        # Verify
        cur.execute("""
            SELECT COUNT(*), MIN(timestamp)::date, MAX(timestamp)::date,
                   (MAX(timestamp)::date - MIN(timestamp)::date) as days
            FROM fhq_market.prices WHERE canonical_id = %s
        """, (symbol,))
        row = cur.fetchone()
        print(f"  Verification: {row[0]} records, {row[3]} days ({row[1]} to {row[2]})")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"  [ERROR] {e}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python backfill_single_asset.py SYMBOL")
        print("Example: python backfill_single_asset.py NVDA")
        sys.exit(1)

    symbol = sys.argv[1].upper()
    backfill_asset(symbol)
