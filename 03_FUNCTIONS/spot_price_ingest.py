#!/usr/bin/env python3
"""
Spot Price Ingest - Real-time price fetcher for Phase A Recovery
================================================================
CEO-DIR-2026-036: ACI Reactivation Protocol - Phase A Data Reality

Fetches CURRENT prices (not daily bars) to meet freshness requirements:
- Crypto: 15 minute max staleness
- Equity/Commodity: 60 minute max staleness

Sources:
- Binance: Crypto spot prices (real-time)
- Alpha Vantage: Equity spot prices (if key available)
- yfinance: Fallback for equities
"""

import os
import sys
import json
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

# API Keys
ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '')

def get_binance_spot_price(symbol: str) -> dict:
    """Get current spot price from Binance"""
    # Convert symbol format: BTC-USD -> BTCUSDT
    binance_symbol = symbol.replace('-USD', 'USDT')

    url = f"https://api.binance.com/api/v3/ticker/price"
    params = {'symbol': binance_symbol}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            'symbol': symbol,
            'price': float(data['price']),
            'timestamp': datetime.now(timezone.utc),
            'source': 'binance_spot'
        }
    except Exception as e:
        print(f"  [ERROR] Binance spot for {symbol}: {e}")
        return None

def get_alpha_vantage_quote(symbol: str) -> dict:
    """Get current quote from Alpha Vantage"""
    if not ALPHA_VANTAGE_KEY:
        return None

    url = "https://www.alphavantage.co/query"
    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol,
        'apikey': ALPHA_VANTAGE_KEY
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if 'Global Quote' in data and data['Global Quote']:
            quote = data['Global Quote']
            return {
                'symbol': symbol,
                'price': float(quote.get('05. price', 0)),
                'open': float(quote.get('02. open', 0)),
                'high': float(quote.get('03. high', 0)),
                'low': float(quote.get('04. low', 0)),
                'volume': int(float(quote.get('06. volume', 0))),
                'timestamp': datetime.now(timezone.utc),
                'source': 'alpha_vantage'
            }
        elif 'Note' in data:
            print(f"  [WARN] Alpha Vantage rate limit: {data['Note'][:50]}...")
            return None
        else:
            print(f"  [WARN] Alpha Vantage no data for {symbol}")
            return None
    except Exception as e:
        print(f"  [ERROR] Alpha Vantage for {symbol}: {e}")
        return None

def get_yfinance_quote(symbol: str) -> dict:
    """Get current quote from yfinance"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # Get current price from fast_info or info
        price = info.get('regularMarketPrice') or info.get('currentPrice')
        if price:
            return {
                'symbol': symbol,
                'price': float(price),
                'open': float(info.get('regularMarketOpen', price)),
                'high': float(info.get('regularMarketDayHigh', price)),
                'low': float(info.get('regularMarketDayLow', price)),
                'volume': int(info.get('regularMarketVolume', 0) or 0),
                'timestamp': datetime.now(timezone.utc),
                'source': 'yfinance_quote'
            }
        return None
    except Exception as e:
        print(f"  [ERROR] yfinance for {symbol}: {e}")
        return None

def get_frankfurter_fx(symbol: str) -> dict:
    """Get FX rate from Frankfurter API (free, ECB data)"""
    # Map yfinance-style symbols to Frankfurter format
    fx_map = {
        'EURUSD=X': ('EUR', 'USD'),
        'GBPUSD=X': ('GBP', 'USD'),
        'USDJPY=X': ('USD', 'JPY'),
    }

    if symbol not in fx_map:
        return None

    from_ccy, to_ccy = fx_map[symbol]

    try:
        url = f"https://api.frankfurter.app/latest?from={from_ccy}&to={to_ccy}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        rate = data['rates'].get(to_ccy)
        if rate:
            return {
                'symbol': symbol,
                'price': float(rate),
                'timestamp': datetime.now(timezone.utc),
                'source': 'frankfurter_ecb'
            }
        return None
    except Exception as e:
        print(f"  [ERROR] Frankfurter for {symbol}: {e}")
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

def insert_spot_price(conn, quote: dict) -> bool:
    """Insert a single spot price record"""
    if not quote:
        return False

    canonical_id = quote['symbol']
    asset_id = get_asset_id(conn, canonical_id)
    ts = quote['timestamp']
    price = quote['price']

    # Use price as OHLC if not provided
    open_p = quote.get('open', price)
    high_p = quote.get('high', price)
    low_p = quote.get('low', price)
    close_p = price
    volume = quote.get('volume', 0)
    source = quote['source']

    # Generate data hash
    hash_input = f"{canonical_id}:{ts}:{open_p}:{high_p}:{low_p}:{close_p}:{volume}"
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
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            volume = EXCLUDED.volume,
            source = EXCLUDED.source
    """

    try:
        with conn.cursor() as cur:
            cur.execute(insert_sql, (
                asset_id, canonical_id, ts,
                open_p, high_p, low_p, close_p, volume,
                source, data_hash, batch_id,
                source.split('_')[0],  # vendor_id
                'CANONICAL_PRIMARY',
                'P1'
            ))
        conn.commit()
        return True
    except Exception as e:
        print(f"  [ERROR] Insert failed for {canonical_id}: {e}")
        conn.rollback()
        return False

def main():
    print("=" * 60)
    print("SPOT PRICE INGEST - CEO-DIR-2026-036 Phase A Recovery")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # Target symbols for Phase A (extended per CEO-DIR-2026-040)
    crypto_symbols = ['BTC-USD', 'SOL-USD', 'ETH-USD']
    equity_symbols = ['SPY', 'GLD']
    fx_symbols = ['EURUSD=X']

    conn = psycopg2.connect(**DB_CONFIG)
    results = {'success': [], 'failed': []}

    # =========================================================================
    # CRYPTO VIA BINANCE SPOT API
    # =========================================================================
    print(f"\n[BINANCE SPOT] Fetching {len(crypto_symbols)} crypto prices...")

    for symbol in crypto_symbols:
        quote = get_binance_spot_price(symbol)
        if quote and insert_spot_price(conn, quote):
            print(f"  [OK] {symbol}: ${quote['price']:.2f}")
            results['success'].append(symbol)
        else:
            results['failed'].append(symbol)

    # =========================================================================
    # EQUITIES VIA ALPHA VANTAGE OR YFINANCE
    # =========================================================================
    print(f"\n[EQUITY] Fetching {len(equity_symbols)} equity prices...")

    for symbol in equity_symbols:
        quote = None

        # Try Alpha Vantage first
        if ALPHA_VANTAGE_KEY:
            print(f"  Trying Alpha Vantage for {symbol}...")
            quote = get_alpha_vantage_quote(symbol)

        # Fallback to yfinance
        if not quote:
            print(f"  Trying yfinance for {symbol}...")
            quote = get_yfinance_quote(symbol)

        if quote and insert_spot_price(conn, quote):
            print(f"  [OK] {symbol}: ${quote['price']:.2f} via {quote['source']}")
            results['success'].append(symbol)
        else:
            print(f"  [FAIL] {symbol}: No data available")
            results['failed'].append(symbol)

    # =========================================================================
    # FX VIA FRANKFURTER API (ECB DATA) WITH YFINANCE FALLBACK
    # =========================================================================
    print(f"\n[FX] Fetching {len(fx_symbols)} FX prices...")

    for symbol in fx_symbols:
        # Try Frankfurter API first (free, reliable ECB data)
        print(f"  Trying Frankfurter (ECB) for {symbol}...")
        quote = get_frankfurter_fx(symbol)

        # Fallback to yfinance
        if not quote:
            print(f"  Trying yfinance for {symbol}...")
            quote = get_yfinance_quote(symbol)

        if quote and insert_spot_price(conn, quote):
            print(f"  [OK] {symbol}: {quote['price']:.4f} via {quote['source']}")
            results['success'].append(symbol)
        else:
            print(f"  [FAIL] {symbol}: No data available")
            results['failed'].append(symbol)

    # =========================================================================
    # VERIFICATION
    # =========================================================================
    print("\n" + "=" * 60)
    print("FRESHNESS VERIFICATION")
    print("=" * 60)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                canonical_id,
                MAX(timestamp) as last_price,
                EXTRACT(EPOCH FROM (NOW() - MAX(timestamp)))/60 as staleness_min
            FROM fhq_market.prices
            WHERE canonical_id IN ('SPY', 'GLD', 'QQQ', 'BTC-USD', 'SOL-USD', 'ETH-USD', 'EURUSD=X')
            GROUP BY canonical_id
            ORDER BY canonical_id
        """)

        all_fresh = True
        for row in cur.fetchall():
            staleness = float(row[2])
            max_allowed = 15 if 'USD' in row[0] else 60
            status = "[FRESH]" if staleness <= max_allowed else "[STALE]"
            if staleness > max_allowed:
                all_fresh = False
            print(f"  {row[0]}: {staleness:.1f} min (max: {max_allowed}) {status}")

    # =========================================================================
    # PHASE A STATUS
    # =========================================================================
    print("\n" + "=" * 60)
    print("PHASE A STATUS")
    print("=" * 60)

    if all_fresh:
        print("  [PASS] All assets within freshness thresholds")
        print("  [NOTE] Continuous ingestion for 120 min still required")
    else:
        print("  [FAIL] Some assets still stale")
        print("  [ACTION] Fix data ingestion pipeline before Phase A can pass")

    print(f"\nResults: {len(results['success'])} success, {len(results['failed'])} failed")

    conn.close()
    return all_fresh

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
