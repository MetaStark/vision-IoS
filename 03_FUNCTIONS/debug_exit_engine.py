#!/usr/bin/env python3
"""Debug script to understand exit engine date comparison issue."""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get one OPEN trade
    cur.execute("""
        SELECT trade_id, asset_id, entry_time, entry_price, direction
        FROM fhq_execution.shadow_trades
        WHERE status = 'OPEN' AND asset_id = 'SPY'
        LIMIT 1
    """)
    trade = cur.fetchone()
    print(f"Trade: {trade['trade_id'][:8]}...")
    print(f"  asset_id: {trade['asset_id']}")
    print(f"  entry_time: {trade['entry_time']} (type: {type(trade['entry_time']).__name__})")
    print(f"  entry_price: {trade['entry_price']}")
    print(f"  direction: {trade['direction']}")

    # Compute expiry
    entry_time = trade['entry_time']
    timeframe_hours = 24
    expiry_time = entry_time + timedelta(hours=timeframe_hours)
    expiry_date = expiry_time.date() if hasattr(expiry_time, 'date') else expiry_time

    print(f"\n  expiry_time: {expiry_time} (type: {type(expiry_time).__name__})")
    print(f"  expiry_date: {expiry_date} (type: {type(expiry_date).__name__})")

    # Get price bars after entry
    cur.execute("""
        SELECT date, open, high, low, close
        FROM fhq_data.price_series
        WHERE listing_id = %s
        AND date > (%s)::date
        ORDER BY date
    """, (trade['asset_id'], entry_time))
    bars = cur.fetchall()

    print(f"\nBars after entry ({len(bars)} found):")
    for bar in bars:
        bar_time = bar['date']
        bar_date = bar_time.date() if hasattr(bar_time, 'date') and callable(bar_time.date) else bar_time

        print(f"  Bar: {bar_time} (type: {type(bar_time).__name__})")
        print(f"    bar_date: {bar_date} (type: {type(bar_date).__name__})")
        print(f"    OHLC: {bar['open']}, {bar['high']}, {bar['low']}, {bar['close']}")

        # Check TIME_EXPIRY condition
        comparison = bar_date >= expiry_date
        print(f"    TIME_EXPIRY check: {bar_date} >= {expiry_date} = {comparison}")

        # Check STOP_LOSS for SHORT
        entry_price = float(trade['entry_price'])
        stop_price = entry_price * 1.05
        bar_high = float(bar['high'])
        print(f"    STOP_LOSS check: {bar_high} >= {stop_price} = {bar_high >= stop_price}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
