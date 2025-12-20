#!/usr/bin/env python3
"""
CEO DIRECTIVE: 5-YEAR EQUITY BACKFILL
=====================================
Authority: CEO
Priority: P0 - IMMEDIATE EXECUTION
Date: 2025-12-09

Source: Yahoo Finance (yfinance) - Free, reliable, 5+ years available
Assets: NVDA, AAPL, MSFT, SPY, QQQ
"""

import os
import sys
import uuid
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env', override=True)

import yfinance as yf

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Assets to backfill (CEO directive)
EQUITY_UNIVERSE = ['NVDA', 'AAPL', 'MSFT', 'SPY', 'QQQ']

# 5 years of data
YEARS_OF_DATA = 5
END_DATE = datetime.now(timezone.utc).date()
START_DATE = END_DATE - timedelta(days=YEARS_OF_DATA * 365 + 30)  # Extra buffer

# =============================================================================
# DATABASE
# =============================================================================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_existing_dates(asset_id: str) -> set:
    """Get existing dates for an asset to avoid duplicates."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT timestamp::date
        FROM fhq_market.prices
        WHERE canonical_id = %s
    """, (asset_id,))
    dates = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return dates


def insert_bars(asset_id: str, bars: list) -> int:
    """Insert OHLCV bars into fhq_market.prices."""
    if not bars:
        return 0

    conn = get_connection()
    cur = conn.cursor()

    # Prepare data
    values = []
    for bar in bars:
        values.append((
            str(uuid.uuid4()),  # id
            asset_id,           # canonical_id
            bar['timestamp'],   # timestamp
            float(bar['open']),
            float(bar['high']),
            float(bar['low']),
            float(bar['close']),
            int(bar['volume']),
            'yfinance_backfill',  # source
            datetime.now(timezone.utc),  # canonicalized_at
            'STIG_BACKFILL'  # canonicalized_by
        ))

    # Bulk insert with ON CONFLICT
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


def log_backfill_event(asset_id: str, records: int, start: str, end: str):
    """Log backfill to governance."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO fhq_governance.system_events
            (event_type, event_category, source_agent, event_title, event_data, event_severity)
            VALUES ('EQUITY_BACKFILL', 'DATA', 'STIG', %s, %s, 'INFO')
        """, (
            f"5-year backfill: {asset_id}",
            f'{{"asset": "{asset_id}", "records": {records}, "start": "{start}", "end": "{end}"}}'
        ))
        conn.commit()
    except Exception as e:
        print(f"    [WARN] Log failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# =============================================================================
# YAHOO FINANCE DATA FETCH
# =============================================================================

def fetch_yfinance_bars(symbol: str, start_date, end_date, retries: int = 3) -> list:
    """Fetch historical bars from Yahoo Finance with retry logic."""
    import time
    import random

    bars = []
    for attempt in range(retries):
        try:
            # Add random delay to avoid rate limiting
            if attempt > 0:
                delay = 5 + random.randint(1, 5)
                print(f"    Retry {attempt+1}/{retries} after {delay}s delay...")
                time.sleep(delay)

            ticker = yf.Ticker(symbol)
            df = ticker.history(start=str(start_date), end=str(end_date), interval='1d')

            if df.empty:
                print(f"    [WARN] No data returned for {symbol}")
                continue

            for idx, row in df.iterrows():
                # Convert timezone-aware index to UTC
                ts = idx.to_pydatetime()
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                else:
                    ts = ts.astimezone(timezone.utc)

                bars.append({
                    'timestamp': ts,
                    'open': row['Open'],
                    'high': row['High'],
                    'low': row['Low'],
                    'close': row['Close'],
                    'volume': int(row['Volume']) if row['Volume'] > 0 else 0
                })

            # Success - break retry loop
            if bars:
                break

        except Exception as e:
            print(f"    [ERROR] yfinance fetch failed: {e}")
            if attempt < retries - 1:
                continue

    return bars


# =============================================================================
# MAIN BACKFILL
# =============================================================================

def backfill_asset(asset_id: str) -> dict:
    """Backfill 5 years of data for a single asset."""
    print(f"\n  [{asset_id}] Starting 5-year backfill...")
    print(f"    Range: {START_DATE} to {END_DATE}")

    # Check existing data
    existing = get_existing_dates(asset_id)
    print(f"    Existing dates: {len(existing)}")

    # Fetch from Yahoo Finance
    print(f"    Fetching from Yahoo Finance...")
    bars = fetch_yfinance_bars(asset_id, START_DATE, END_DATE)
    print(f"    Fetched: {len(bars)} bars")

    if not bars:
        return {'asset': asset_id, 'status': 'NO_DATA', 'inserted': 0, 'days_of_data': 0}

    # Filter out existing dates
    new_bars = [b for b in bars if b['timestamp'].date() not in existing]
    print(f"    New bars: {len(new_bars)}")

    # Insert
    if new_bars:
        inserted = insert_bars(asset_id, new_bars)
        print(f"    Inserted: {inserted} records")
    else:
        inserted = 0
        print(f"    No new data to insert")

    # Calculate stats
    earliest = min(b['timestamp'] for b in bars).date()
    latest = max(b['timestamp'] for b in bars).date()
    days = (latest - earliest).days

    # Log
    log_backfill_event(asset_id, inserted, str(earliest), str(latest))

    return {
        'asset': asset_id,
        'status': 'SUCCESS',
        'fetched': len(bars),
        'inserted': inserted,
        'earliest': str(earliest),
        'latest': str(latest),
        'days_of_data': days
    }


def main():
    """Execute 5-year backfill for all equities."""
    print("=" * 70)
    print("CEO DIRECTIVE: 5-YEAR EQUITY BACKFILL")
    print("=" * 70)
    print(f"Priority: P0 - IMMEDIATE EXECUTION")
    print(f"Assets: {', '.join(EQUITY_UNIVERSE)}")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print(f"Data Source: Yahoo Finance (yfinance)")

    import time as t
    results = []
    total_inserted = 0

    for i, asset in enumerate(EQUITY_UNIVERSE):
        if i > 0:
            print(f"\n  [RATE LIMIT] Waiting 10s before next asset...")
            t.sleep(10)
        result = backfill_asset(asset)
        results.append(result)
        total_inserted += result.get('inserted', 0)

    # Summary
    print("\n" + "=" * 70)
    print("BACKFILL SUMMARY")
    print("=" * 70)

    for r in results:
        status = "OK" if r['status'] == 'SUCCESS' else "FAIL"
        print(f"  [{status}] {r['asset']}: {r.get('days_of_data', 0)} days, {r.get('inserted', 0)} new records")

    print(f"\nTotal New Records: {total_inserted}")

    # Verify
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)

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

    print("\n[COMPLETE] 5-year backfill finished.")


if __name__ == '__main__':
    main()
