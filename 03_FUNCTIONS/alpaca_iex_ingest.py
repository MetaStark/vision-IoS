#!/usr/bin/env python3
"""
Alpaca IEX Price Ingest - Free tier equity data
================================================
CEO-DIR-2026-036: Phase A Data Reality

Uses Alpaca's IEX feed (free tier, 15-min delayed) for equity prices.
"""

import os
import sys
import requests
from datetime import datetime, timezone
import psycopg2
from dotenv import load_dotenv
import hashlib
import uuid as uuid_module

load_dotenv()

# Database
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Alpaca
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))

def get_alpaca_iex_quote(symbol: str) -> dict:
    """Get latest quote from Alpaca IEX feed (free tier)"""
    if not ALPACA_API_KEY:
        print("  [ERROR] ALPACA_API_KEY not set")
        return None

    # Use latest quote endpoint with IEX feed
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
    headers = {
        'APCA-API-KEY-ID': ALPACA_API_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET
    }
    params = {
        'feed': 'iex'  # Use IEX feed (free tier)
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if 'quote' in data:
            quote = data['quote']
            # Use midpoint as price
            bid = float(quote.get('bp', 0))
            ask = float(quote.get('ap', 0))
            price = (bid + ask) / 2 if bid and ask else bid or ask

            return {
                'symbol': symbol,
                'price': price,
                'bid': bid,
                'ask': ask,
                'timestamp': datetime.now(timezone.utc),
                'source': 'alpaca_iex'
            }
        return None
    except Exception as e:
        print(f"  [ERROR] Alpaca IEX quote for {symbol}: {e}")
        return None

def get_alpaca_iex_trade(symbol: str) -> dict:
    """Get latest trade from Alpaca IEX feed"""
    if not ALPACA_API_KEY:
        return None

    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest"
    headers = {
        'APCA-API-KEY-ID': ALPACA_API_KEY,
        'APCA-API-SECRET-KEY': ALPACA_SECRET
    }
    params = {
        'feed': 'iex'
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if 'trade' in data:
            trade = data['trade']
            return {
                'symbol': symbol,
                'price': float(trade.get('p', 0)),
                'size': int(trade.get('s', 0)),
                'timestamp': datetime.now(timezone.utc),
                'source': 'alpaca_iex_trade'
            }
        return None
    except Exception as e:
        print(f"  [ERROR] Alpaca IEX trade for {symbol}: {e}")
        return None

def get_asset_id(conn, canonical_id: str) -> str:
    """Get existing asset_id or generate new one"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT asset_id FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY asset_id
            LIMIT 1
        """, (canonical_id,))
        row = cur.fetchone()
        if row:
            return row[0]
        return str(uuid_module.uuid4())

def insert_price(conn, quote: dict) -> bool:
    """Insert price record"""
    if not quote or not quote.get('price'):
        return False

    canonical_id = quote['symbol']
    asset_id = get_asset_id(conn, canonical_id)
    ts = quote['timestamp']
    price = quote['price']

    hash_input = f"{canonical_id}:{ts}:{price}"
    data_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]
    batch_id = str(uuid_module.uuid4())

    insert_sql = """
        INSERT INTO fhq_market.prices (
            asset_id, canonical_id, timestamp, open, high, low, close, volume,
            source, data_hash, batch_id, vendor_id, vendor_role, price_class
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (canonical_id, timestamp) DO UPDATE SET
            close = EXCLUDED.close,
            source = EXCLUDED.source
    """

    try:
        with conn.cursor() as cur:
            cur.execute(insert_sql, (
                asset_id, canonical_id, ts,
                price, price, price, price, 0,
                quote['source'], data_hash, batch_id,
                'alpaca', 'CANONICAL_PRIMARY', 'P1'
            ))
        conn.commit()
        return True
    except Exception as e:
        print(f"  [ERROR] Insert failed for {canonical_id}: {e}")
        conn.rollback()
        return False

def main():
    print("=" * 60)
    print("ALPACA IEX INGEST - Free Tier Equity Data")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    symbols = ['SPY', 'GLD', 'QQQ']
    conn = psycopg2.connect(**DB_CONFIG)
    results = {'success': [], 'failed': []}

    for symbol in symbols:
        print(f"\n[{symbol}] Fetching...")

        # Try trade first (actual price), then quote (bid/ask midpoint)
        quote = get_alpaca_iex_trade(symbol)
        if not quote:
            quote = get_alpaca_iex_quote(symbol)

        if quote and insert_price(conn, quote):
            print(f"  [OK] ${quote['price']:.2f} via {quote['source']}")
            results['success'].append(symbol)
        else:
            print(f"  [FAIL] No data available")
            results['failed'].append(symbol)

    # Verify
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                canonical_id,
                MAX(timestamp) as last_price,
                close as price,
                EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60 as staleness_min
            FROM fhq_market.prices
            WHERE canonical_id IN ('SPY', 'GLD', 'QQQ')
            GROUP BY canonical_id, close
            ORDER BY canonical_id, last_price DESC
        """)
        for row in cur.fetchall():
            staleness = float(row[3])
            status = "[FRESH]" if staleness <= 60 else "[STALE]"
            print(f"  {row[0]}: ${row[2]:.2f} ({staleness:.1f} min) {status}")

    print(f"\nResults: {len(results['success'])} success, {len(results['failed'])} failed")
    conn.close()

    return len(results['failed']) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
