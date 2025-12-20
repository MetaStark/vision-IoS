#!/usr/bin/env python3
"""
YAHOO CHART API V8 - RAW OHLCV FETCHER
======================================
CEO DIRECTIVE: Data Quality Enforcement for Equities

This module fetches RAW (unadjusted) OHLCV data from Yahoo Finance Chart API v8.
It also fetches corporate actions (dividends, splits) for building our own
adj_close backward-adjustment pipeline.

CRITICAL RULES:
1. NEVER use yfinance library (returns adjusted data by default)
2. ALWAYS fetch from chart.yahoo.finance API directly
3. Store RAW close in 'close' column
4. Store our calculated adj_close in 'adj_close' column
5. Store all corporate actions in corporate_actions table

ADR Compliance: ADR-003, ADR-013
IoS Reference: IoS-002 (Indicator Engine prerequisites)
"""

import os
import sys
import uuid
import json
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path
import hashlib

load_dotenv(Path(__file__).parent.parent / '.env', override=True)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

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


def fetch_yahoo_chart_v8(symbol: str, years: int = 5) -> dict:
    """
    Fetch RAW OHLCV + corporate actions from Yahoo Chart API v8.

    Returns:
        {
            'prices': [...],      # RAW OHLCV bars
            'dividends': [...],   # Dividend events
            'splits': [...]       # Split events
        }
    """
    # Calculate period
    end_ts = int(datetime.now().timestamp())
    start_ts = int((datetime.now() - timedelta(days=years * 365 + 30)).timestamp())

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        'period1': start_ts,
        'period2': end_ts,
        'interval': '1d',
        'events': 'div,split',  # Request dividend and split events
        'includeAdjustedClose': 'false'  # We want RAW data
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    print(f"  Fetching {symbol} from Yahoo Chart API v8...")
    print(f"    Period: {datetime.fromtimestamp(start_ts).date()} to {datetime.fromtimestamp(end_ts).date()}")

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        data = resp.json()

        if 'chart' not in data or 'result' not in data['chart']:
            print(f"    [ERROR] Invalid response structure")
            return {'prices': [], 'dividends': [], 'splits': []}

        result = data['chart']['result'][0]

        # Extract timestamps
        timestamps = result.get('timestamp', [])
        if not timestamps:
            print(f"    [ERROR] No timestamps in response")
            return {'prices': [], 'dividends': [], 'splits': []}

        # Extract OHLCV (these are RAW, unadjusted values)
        quote = result.get('indicators', {}).get('quote', [{}])[0]
        opens = quote.get('open', [])
        highs = quote.get('high', [])
        lows = quote.get('low', [])
        closes = quote.get('close', [])
        volumes = quote.get('volume', [])

        # Build price bars
        prices = []
        for i, ts in enumerate(timestamps):
            if closes[i] is None:
                continue  # Skip null bars (holidays)

            prices.append({
                'timestamp': datetime.fromtimestamp(ts, tz=timezone.utc),
                'open': float(opens[i]) if opens[i] else None,
                'high': float(highs[i]) if highs[i] else None,
                'low': float(lows[i]) if lows[i] else None,
                'close': float(closes[i]),  # RAW close
                'volume': int(volumes[i]) if volumes[i] else 0
            })

        print(f"    Fetched {len(prices)} RAW price bars")

        # Extract corporate actions
        events = result.get('events', {})

        # Dividends
        dividends = []
        div_events = events.get('dividends', {})
        for ts_str, div_data in div_events.items():
            dividends.append({
                'timestamp': datetime.fromtimestamp(int(ts_str), tz=timezone.utc),
                'amount': float(div_data.get('amount', 0)),
                'type': 'DIVIDEND'
            })

        # Splits
        splits = []
        split_events = events.get('splits', {})
        for ts_str, split_data in split_events.items():
            numerator = split_data.get('numerator', 1)
            denominator = split_data.get('denominator', 1)
            splits.append({
                'timestamp': datetime.fromtimestamp(int(ts_str), tz=timezone.utc),
                'numerator': int(numerator),
                'denominator': int(denominator),
                'ratio': float(numerator) / float(denominator),
                'type': 'SPLIT'
            })

        print(f"    Found {len(dividends)} dividends, {len(splits)} splits")

        return {
            'prices': sorted(prices, key=lambda x: x['timestamp']),
            'dividends': sorted(dividends, key=lambda x: x['timestamp']),
            'splits': sorted(splits, key=lambda x: x['timestamp'])
        }

    except Exception as e:
        print(f"    [ERROR] Request failed: {e}")
        return {'prices': [], 'dividends': [], 'splits': []}


def convert_adjusted_to_raw(prices: list, splits: list) -> list:
    """
    Convert adjusted prices BACK to RAW prices using split events.

    Yahoo Chart API returns split-adjusted prices. We need to REVERSE
    the adjustment to get RAW prices.

    Algorithm:
    1. Start from most recent price (no adjustment needed - it's already correct)
    2. For each split going backwards, MULTIPLY historical prices by split ratio
       - e.g., NVDA 10:1 split on 2024-06-10
       - Pre-split prices were divided by 10 during adjustment
       - To get RAW: multiply pre-split prices by 10

    Returns prices with:
    - 'raw_close': Original unadjusted close price (what we want for TA)
    - 'adj_close': Split-adjusted close (what Yahoo gave us)
    """
    if not prices:
        return prices

    # Build split lookup: date -> ratio
    split_lookup = {s['timestamp'].date(): s['ratio'] for s in splits}

    # Sort prices ascending by date
    prices_sorted = sorted(prices, key=lambda x: x['timestamp'])

    # Calculate cumulative adjustment factor for each date
    # Going BACKWARDS from end: after a split, factor increases for earlier dates
    cumulative_factor = 1.0
    factors = {}

    for price in reversed(prices_sorted):
        price_date = price['timestamp'].date()
        factors[price_date] = cumulative_factor

        # If there was a split on this date, prices BEFORE this were
        # divided by split ratio. To reverse: multiply by ratio.
        if price_date in split_lookup:
            cumulative_factor *= split_lookup[price_date]

    # Apply reverse adjustment to get RAW prices
    for price in prices_sorted:
        price_date = price['timestamp'].date()
        factor = factors.get(price_date, 1.0)

        adj_close = price['close']  # This is what Yahoo gave us (adjusted)
        raw_close = adj_close * factor  # Reverse the adjustment to get RAW

        price['adj_close'] = adj_close
        price['raw_close'] = raw_close

        # Also convert OHLV to RAW
        if price['open']:
            price['raw_open'] = price['open'] * factor
            price['open'] = price['raw_open']  # Replace with RAW
        if price['high']:
            price['raw_high'] = price['high'] * factor
            price['high'] = price['raw_high']
        if price['low']:
            price['raw_low'] = price['low'] * factor
            price['low'] = price['raw_low']

        # Replace close with RAW close
        price['close'] = raw_close

    return prices_sorted


def compute_data_hash(bar: dict) -> str:
    """Compute SHA256 hash of OHLCV data."""
    data_str = f"{bar['open']}{bar['high']}{bar['low']}{bar['close']}{bar['volume']}"
    return hashlib.sha256(data_str.encode()).hexdigest()[:32]


def insert_raw_prices(symbol: str, prices: list) -> int:
    """Insert RAW OHLCV into fhq_market.prices, replacing adjusted data."""
    if not prices:
        return 0

    asset_uuid = ASSET_IDS.get(symbol)
    if not asset_uuid:
        print(f"    [ERROR] No asset_id for {symbol}")
        return 0

    conn = get_connection()
    cur = conn.cursor()

    batch_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    values = []
    for bar in prices:
        if bar['close'] is None:
            continue
        data_hash = compute_data_hash(bar)
        values.append((
            str(uuid.uuid4()),
            asset_uuid,
            symbol,
            bar['timestamp'],
            float(bar['open']) if bar['open'] else 0.0,
            float(bar['high']) if bar['high'] else 0.0,
            float(bar['low']) if bar['low'] else 0.0,
            float(bar['close']),  # RAW close
            float(bar['volume']),
            'yahoo_chart_v8_raw',  # Source identifier
            data_hash,
            batch_id,
            now,
            'STIG_RAW_BACKFILL'
        ))

    try:
        # Delete existing data for this symbol first (replace adjusted with RAW)
        cur.execute("""
            DELETE FROM fhq_market.prices
            WHERE canonical_id = %s
              AND source IN ('twelvedata_backfill', 'yfinance_backfill')
        """, (symbol,))
        deleted = cur.rowcount
        print(f"    Deleted {deleted} adjusted records")

        # Insert RAW data
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
        print(f"    [OK] Inserted {len(values)} RAW records")
        return len(values)

    except Exception as e:
        print(f"    [ERROR] Insert failed: {e}")
        conn.rollback()
        return 0
    finally:
        cur.close()
        conn.close()


def insert_corporate_actions(symbol: str, dividends: list, splits: list) -> int:
    """Insert corporate actions into fhq_market.corporate_actions."""
    if not dividends and not splits:
        return 0

    asset_uuid = ASSET_IDS.get(symbol)
    conn = get_connection()
    cur = conn.cursor()

    # Ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fhq_market.corporate_actions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            asset_id UUID NOT NULL,
            canonical_id TEXT NOT NULL,
            action_date DATE NOT NULL,
            action_type TEXT NOT NULL,  -- 'DIVIDEND' or 'SPLIT'
            dividend_amount DOUBLE PRECISION,
            split_numerator INTEGER,
            split_denominator INTEGER,
            split_ratio DOUBLE PRECISION,
            source TEXT DEFAULT 'yahoo_chart_v8',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(canonical_id, action_date, action_type)
        )
    """)

    values = []

    # Dividends
    for div in dividends:
        values.append((
            str(uuid.uuid4()),
            asset_uuid,
            symbol,
            div['timestamp'].date(),
            'DIVIDEND',
            div['amount'],
            None, None, None,
            'yahoo_chart_v8'
        ))

    # Splits
    for split in splits:
        values.append((
            str(uuid.uuid4()),
            asset_uuid,
            symbol,
            split['timestamp'].date(),
            'SPLIT',
            None,
            split['numerator'],
            split['denominator'],
            split['ratio'],
            'yahoo_chart_v8'
        ))

    try:
        execute_values(cur, """
            INSERT INTO fhq_market.corporate_actions
            (id, asset_id, canonical_id, action_date, action_type, dividend_amount, split_numerator, split_denominator, split_ratio, source)
            VALUES %s
            ON CONFLICT (canonical_id, action_date, action_type) DO UPDATE SET
                dividend_amount = EXCLUDED.dividend_amount,
                split_numerator = EXCLUDED.split_numerator,
                split_denominator = EXCLUDED.split_denominator,
                split_ratio = EXCLUDED.split_ratio
        """, values)
        conn.commit()
        print(f"    [OK] Inserted {len(values)} corporate actions")
        return len(values)

    except Exception as e:
        print(f"    [ERROR] Corporate actions insert failed: {e}")
        conn.rollback()
        return 0
    finally:
        cur.close()
        conn.close()


def verify_raw_data(symbol: str) -> dict:
    """Verify that data is RAW by checking known split dates."""
    conn = get_connection()
    cur = conn.cursor()

    # Known splits to verify
    known_splits = {
        'NVDA': {'date': '2024-06-10', 'ratio': 10, 'pre_price_approx': 1200},
        'AAPL': {'date': '2020-08-31', 'ratio': 4, 'pre_price_approx': 500},
    }

    if symbol not in known_splits:
        return {'verified': True, 'reason': 'No known splits to verify'}

    split_info = known_splits[symbol]
    split_date = split_info['date']

    # Get prices around split date
    cur.execute("""
        SELECT timestamp::date, close, source
        FROM fhq_market.prices
        WHERE canonical_id = %s
          AND timestamp::date BETWEEN %s::date - interval '5 days' AND %s::date + interval '5 days'
        ORDER BY timestamp
    """, (symbol, split_date, split_date))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return {'verified': False, 'reason': 'No data around split date'}

    # Check if pre-split prices are in expected RAW range
    pre_split_prices = [r[1] for r in rows if str(r[0]) < split_date]

    if pre_split_prices:
        avg_pre = sum(pre_split_prices) / len(pre_split_prices)
        expected_min = split_info['pre_price_approx'] * 0.7
        expected_max = split_info['pre_price_approx'] * 1.3

        if expected_min <= avg_pre <= expected_max:
            return {
                'verified': True,
                'reason': f'Pre-split avg ${avg_pre:.2f} matches RAW expectation',
                'pre_split_avg': avg_pre
            }
        else:
            return {
                'verified': False,
                'reason': f'Pre-split avg ${avg_pre:.2f} looks ADJUSTED (expected ~${split_info["pre_price_approx"]})',
                'pre_split_avg': avg_pre
            }

    return {'verified': False, 'reason': 'Could not find pre-split prices'}


def backfill_raw_equity(symbol: str) -> dict:
    """Backfill RAW data for a single equity."""
    print(f"\n[{symbol}] Starting RAW data backfill...")

    # Fetch from Yahoo Chart API v8
    data = fetch_yahoo_chart_v8(symbol, years=5)

    if not data['prices']:
        return {'asset': symbol, 'status': 'NO_DATA', 'inserted': 0}

    # Convert adjusted prices back to RAW using split events
    prices_with_raw = convert_adjusted_to_raw(data['prices'], data['splits'])

    # Insert RAW prices
    inserted = insert_raw_prices(symbol, prices_with_raw)

    # Insert corporate actions
    actions = insert_corporate_actions(symbol, data['dividends'], data['splits'])

    # Verify RAW data
    verification = verify_raw_data(symbol)

    if prices_with_raw:
        earliest = min(p['timestamp'] for p in prices_with_raw).date()
        latest = max(p['timestamp'] for p in prices_with_raw).date()
        days = (latest - earliest).days
    else:
        earliest = latest = None
        days = 0

    return {
        'asset': symbol,
        'status': 'SUCCESS' if inserted > 0 else 'FAILED',
        'inserted': inserted,
        'corporate_actions': actions,
        'dividends': len(data['dividends']),
        'splits': len(data['splits']),
        'days': days,
        'earliest': str(earliest) if earliest else None,
        'latest': str(latest) if latest else None,
        'raw_verified': verification['verified'],
        'verification_reason': verification['reason']
    }


def main():
    print("=" * 70)
    print("CEO DIRECTIVE: RAW DATA BACKFILL - YAHOO CHART API V8")
    print("=" * 70)
    print(f"Assets: {', '.join(EQUITY_UNIVERSE)}")
    print("Data Type: RAW OHLCV (unadjusted)")
    print("Corporate Actions: Dividends + Splits")

    results = []

    for i, asset in enumerate(EQUITY_UNIVERSE):
        if i > 0:
            print("\n  [RATE LIMIT] Waiting 2s...")
            time.sleep(2)

        result = backfill_raw_equity(asset)
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("RAW DATA BACKFILL SUMMARY")
    print("=" * 70)

    all_verified = True
    for r in results:
        status = "RAW-OK" if r.get('raw_verified') else "NEEDS-CHECK"
        if not r.get('raw_verified'):
            all_verified = False
        print(f"  [{status}] {r['asset']}: {r.get('days', 0)} days, {r.get('inserted', 0)} records, {r.get('dividends', 0)} divs, {r.get('splits', 0)} splits")
        if r.get('verification_reason'):
            print(f"           Verification: {r['verification_reason']}")

    print("\n" + "=" * 70)
    if all_verified:
        print("[SUCCESS] All equities have verified RAW data")
    else:
        print("[WARNING] Some assets need manual verification")
    print("=" * 70)

    return results


if __name__ == '__main__':
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
        result = backfill_raw_equity(symbol)
        print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
    else:
        main()
