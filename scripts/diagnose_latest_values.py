#!/usr/bin/env python3
"""
DIAGNOSTIC SPOT CHECK - READ ONLY
=================================

Purpose: Clarify discrepancy between IoS-002 output (StochRSI=1.0)
and external source (TradingView RSI~40).

This script is READ-ONLY - no database modifications.
"""

import os
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )

def main():
    print("=" * 80)
    print("DIAGNOSTIC SPOT CHECK - BTC-USD")
    print("=" * 80)
    print(f"Run Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Purpose: Verify timestamp alignment between canonical prices and indicators")
    print("=" * 80)

    conn = get_connection()

    # ========================================================================
    # SECTION 1: Canonical Prices (fhq_market.prices)
    # ========================================================================
    print("\n" + "=" * 80)
    print("SECTION 1: CANONICAL PRICES (fhq_market.prices)")
    print("=" * 80)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                source,
                data_hash
            FROM fhq_market.prices
            WHERE canonical_id = 'BTC-USD'
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        prices = cur.fetchall()

    if prices:
        print(f"\nLast 5 rows from canonical prices:")
        print("-" * 80)
        print(f"{'Timestamp':<25} {'Close':>15} {'Volume':>20} {'Source':<10}")
        print("-" * 80)
        for row in prices:
            ts = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')
            close = f"{row['close']:,.2f}"
            vol = f"{row['volume']:,.0f}"
            print(f"{ts:<25} {close:>15} {vol:>20} {row['source']:<10}")

        print(f"\n  LATEST PRICE DETAILS:")
        latest = prices[0]
        print(f"    Timestamp: {latest['timestamp']}")
        print(f"    Open:      ${latest['open']:,.2f}")
        print(f"    High:      ${latest['high']:,.2f}")
        print(f"    Low:       ${latest['low']:,.2f}")
        print(f"    Close:     ${latest['close']:,.2f}")
        print(f"    Volume:    {latest['volume']:,.0f}")
        print(f"    Hash:      {latest['data_hash'][:16]}...")
    else:
        print("  NO DATA FOUND in fhq_market.prices for BTC-USD")

    # ========================================================================
    # SECTION 2: Indicator Momentum (fhq_research.indicator_momentum)
    # ========================================================================
    print("\n" + "=" * 80)
    print("SECTION 2: INDICATOR MOMENTUM (fhq_research.indicator_momentum)")
    print("=" * 80)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                timestamp,
                asset_id,
                value_json,
                engine_version,
                formula_hash,
                created_at
            FROM fhq_research.indicator_momentum
            WHERE asset_id = 'BTC-USD'
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        momentum = cur.fetchall()

    if momentum:
        print(f"\nLast 5 rows from indicator_momentum:")
        print("-" * 80)
        for row in momentum:
            ts = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC') if row['timestamp'] else 'NULL'
            print(f"  Timestamp: {ts}")
            print(f"  Values: {row['value_json']}")
            print(f"  Engine: {row['engine_version']}, Hash: {row['formula_hash']}")
            print("-" * 40)
    else:
        print("  NO DATA FOUND in fhq_research.indicator_momentum for BTC-USD")
        print("  (Tables are empty - indicators not yet populated)")

    # Check table row count
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_research.indicator_momentum")
        cnt = cur.fetchone()['cnt']
        print(f"\n  Total rows in indicator_momentum: {cnt}")

    # ========================================================================
    # SECTION 3: Indicator Trend (fhq_research.indicator_trend)
    # ========================================================================
    print("\n" + "=" * 80)
    print("SECTION 3: INDICATOR TREND (fhq_research.indicator_trend)")
    print("=" * 80)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                timestamp,
                asset_id,
                value_json,
                engine_version,
                formula_hash,
                created_at
            FROM fhq_research.indicator_trend
            WHERE asset_id = 'BTC-USD'
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        trend = cur.fetchall()

    if trend:
        print(f"\nLast 5 rows from indicator_trend:")
        print("-" * 80)
        for row in trend:
            ts = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC') if row['timestamp'] else 'NULL'
            print(f"  Timestamp: {ts}")
            print(f"  Values: {row['value_json']}")
            print(f"  Engine: {row['engine_version']}, Hash: {row['formula_hash']}")
            print("-" * 40)
    else:
        print("  NO DATA FOUND in fhq_research.indicator_trend for BTC-USD")
        print("  (Tables are empty - indicators not yet populated)")

    # Check table row count
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM fhq_research.indicator_trend")
        cnt = cur.fetchone()['cnt']
        print(f"\n  Total rows in indicator_trend: {cnt}")

    # ========================================================================
    # SECTION 4: Live Calculation from Canonical Prices
    # ========================================================================
    print("\n" + "=" * 80)
    print("SECTION 4: LIVE CALCULATION FROM CANONICAL PRICES")
    print("=" * 80)
    print("(Computing RSI and StochRSI from the last 100 days of canonical prices)")

    import pandas as pd
    import numpy as np

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT timestamp, close
            FROM fhq_market.prices
            WHERE canonical_id = 'BTC-USD'
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        rows = cur.fetchall()

    if rows:
        df = pd.DataFrame(rows)
        df = df.sort_values('timestamp').reset_index(drop=True)
        df['close'] = df['close'].astype(float)

        # Calculate RSI-14
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Calculate StochRSI
        rsi_min = rsi.rolling(window=14).min()
        rsi_max = rsi.rolling(window=14).max()
        stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min)

        # Get latest values
        latest_idx = len(df) - 1
        latest_ts = df['timestamp'].iloc[latest_idx]
        latest_close = df['close'].iloc[latest_idx]
        latest_rsi = rsi.iloc[latest_idx]
        latest_stoch = stoch_rsi.iloc[latest_idx]

        print(f"\n  COMPUTED VALUES (from canonical prices):")
        print(f"    Latest Timestamp: {latest_ts}")
        print(f"    Latest Close:     ${latest_close:,.2f}")
        print(f"    RSI-14:           {latest_rsi:.2f}")
        print(f"    StochRSI:         {latest_stoch:.4f}")

        # Show last 5 RSI values
        print(f"\n  Last 5 RSI values:")
        print(f"  {'Timestamp':<25} {'Close':>12} {'RSI-14':>10} {'StochRSI':>10}")
        print("-" * 60)
        for i in range(max(0, len(df)-5), len(df)):
            ts = df['timestamp'].iloc[i].strftime('%Y-%m-%d')
            close = df['close'].iloc[i]
            r = rsi.iloc[i]
            s = stoch_rsi.iloc[i]
            print(f"  {ts:<25} {close:>12,.2f} {r:>10.2f} {s:>10.4f}")

    # ========================================================================
    # SECTION 5: Data Freshness Analysis
    # ========================================================================
    print("\n" + "=" * 80)
    print("SECTION 5: DATA FRESHNESS ANALYSIS")
    print("=" * 80)

    now = datetime.now(timezone.utc)
    if prices:
        latest_price_ts = prices[0]['timestamp']
        if latest_price_ts.tzinfo is None:
            from datetime import timezone as tz
            latest_price_ts = latest_price_ts.replace(tzinfo=tz.utc)
        age = now - latest_price_ts

        print(f"\n  Current UTC Time:     {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Latest Price Time:    {latest_price_ts.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Data Age:             {age.days} days, {age.seconds // 3600} hours")

        if age.days >= 1:
            print(f"\n  WARNING: Price data is {age.days} day(s) old!")
            print(f"  This explains why RSI may differ from live TradingView.")
            print(f"  TradingView shows CURRENT price, our data shows YESTERDAY's close.")

    # ========================================================================
    # SECTION 6: StochRSI = 1.0 Explanation
    # ========================================================================
    print("\n" + "=" * 80)
    print("SECTION 6: WHY StochRSI = 1.0?")
    print("=" * 80)

    if rows:
        print(f"\n  StochRSI formula: (RSI - RSI_min) / (RSI_max - RSI_min)")
        print(f"  Over the last 14 periods:")

        rsi_window = rsi.iloc[-14:]
        print(f"    RSI range: {rsi_window.min():.2f} to {rsi_window.max():.2f}")
        print(f"    Current RSI: {latest_rsi:.2f}")

        if latest_rsi >= rsi_window.max() - 0.01:
            print(f"\n  EXPLANATION: Current RSI ({latest_rsi:.2f}) is at or near the")
            print(f"  14-period HIGH ({rsi_window.max():.2f}), so StochRSI = 1.0")
            print(f"  This means RSI is at its highest level in the last 14 days.")

        print(f"\n  NOTE: StochRSI measures RSI position within its recent range,")
        print(f"  NOT the absolute RSI value. StochRSI=1.0 with RSI=42 is valid")
        print(f"  if RSI=42 is the highest RSI in the last 14 periods.")

    conn.close()

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
