#!/usr/bin/env python3
"""
Quick Price Ingest - Per CD-IOS-001-PRICE-ARCH-001
===================================================
Uses canonical vendors:
- Alpaca for equities (CANONICAL_PRIMARY)
- Binance for crypto (CANONICAL_PRIMARY)
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

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

# Core symbols to ingest
EQUITY_SYMBOLS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMD', 'META', 'SPY', 'QQQ']
CRYPTO_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD']

def get_alpaca_bars(symbols: list, days: int = 5) -> dict:
    """Fetch daily bars from Alpaca using SDK"""
    if not ALPACA_API_KEY:
        print("ERROR: ALPACA_API_KEY not set")
        return {}

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET)

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=start,
            end=end
        )

        bars = client.get_stock_bars(request)

        # Convert to dict format
        result = {}
        for symbol in symbols:
            if symbol in bars.data:
                result[symbol] = [
                    {
                        't': bar.timestamp.isoformat(),
                        'o': float(bar.open),
                        'h': float(bar.high),
                        'l': float(bar.low),
                        'c': float(bar.close),
                        'v': int(bar.volume)
                    }
                    for bar in bars.data[symbol]
                ]

        return result

    except ImportError:
        print("Alpaca SDK not available, trying REST API...")
        # Fallback to REST API
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        url = "https://data.alpaca.markets/v2/stocks/bars"
        headers = {
            'APCA-API-KEY-ID': ALPACA_API_KEY,
            'APCA-API-SECRET-KEY': ALPACA_SECRET
        }
        params = {
            'symbols': ','.join(symbols),
            'timeframe': '1Day',
            'start': start.strftime('%Y-%m-%dT00:00:00Z'),
            'end': end.strftime('%Y-%m-%dT23:59:59Z'),
            'adjustment': 'split'
        }

        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get('bars', {})
        except Exception as e:
            print(f"Alpaca REST error: {e}")
            return {}
    except Exception as e:
        print(f"Alpaca error: {e}")
        return {}

def get_binance_klines(symbol: str, days: int = 5) -> list:
    """Fetch daily klines from Binance"""
    # Convert symbol format: BTC-USD -> BTCUSDT
    binance_symbol = symbol.replace('-USD', 'USDT')

    url = "https://api.binance.com/api/v3/klines"
    params = {
        'symbol': binance_symbol,
        'interval': '1d',
        'limit': days
    }

    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Binance error for {symbol}: {e}")
        return []

def get_asset_id(conn, canonical_id: str) -> str:
    """Get or create asset_id for a symbol"""
    with conn.cursor() as cur:
        # Try to get existing asset_id
        cur.execute("""
            SELECT DISTINCT asset_id FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY asset_id
            LIMIT 1
        """, (canonical_id,))
        row = cur.fetchone()
        if row:
            return row[0]
        # Generate new one
        import uuid
        return str(uuid.uuid4())

def insert_prices(conn, prices: list):
    """Insert prices into canonical table"""
    if not prices:
        return 0

    import hashlib
    import uuid
    batch_id = str(uuid.uuid4())

    # Get asset_ids for each symbol
    asset_ids = {}
    symbols = set(p[0] for p in prices)
    for sym in symbols:
        asset_ids[sym] = get_asset_id(conn, sym)

    # Build full records with all required columns
    full_records = []
    for p in prices:
        canonical_id = p[0]
        ts = p[1]
        o, h, l, c, v = p[2], p[3], p[4], p[5], p[6]
        source = p[7]
        vendor_id = p[8]
        vendor_role = p[9]
        price_class = p[10]

        # Generate data hash
        hash_input = f"{canonical_id}:{ts}:{o}:{h}:{l}:{c}:{v}"
        data_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]

        full_records.append((
            asset_ids[canonical_id],  # asset_id
            canonical_id,
            ts,
            o, h, l, c, v,
            source,
            data_hash,
            batch_id,
            vendor_id,
            vendor_role,
            price_class
        ))

    insert_sql = """
        INSERT INTO fhq_market.prices (
            asset_id, canonical_id, timestamp, open, high, low, close, volume,
            source, data_hash, batch_id, vendor_id, vendor_role, price_class
        ) VALUES %s
        ON CONFLICT (canonical_id, timestamp) DO UPDATE SET
            close = EXCLUDED.close,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            volume = EXCLUDED.volume,
            source = EXCLUDED.source,
            vendor_id = EXCLUDED.vendor_id,
            vendor_role = EXCLUDED.vendor_role
    """

    with conn.cursor() as cur:
        execute_values(cur, insert_sql, full_records)
    conn.commit()
    return len(full_records)

def get_yfinance_prices(symbols: list, days: int = 5) -> dict:
    """Fetch prices via yfinance (BACKUP vendor)"""
    try:
        import yfinance as yf
        result = {}
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=f"{days}d")
                if not hist.empty:
                    result[symbol] = [
                        {
                            't': idx.isoformat(),
                            'o': float(row['Open']),
                            'h': float(row['High']),
                            'l': float(row['Low']),
                            'c': float(row['Close']),
                            'v': int(row['Volume'])
                        }
                        for idx, row in hist.iterrows()
                    ]
            except Exception as e:
                print(f"  yfinance error for {symbol}: {e}")
        return result
    except ImportError:
        print("yfinance not available")
        return {}

def main():
    print("=" * 60)
    print("QUICK PRICE INGEST - CD-IOS-001-PRICE-ARCH-001")
    print("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    total_inserted = 0

    # =========================================================================
    # EQUITIES VIA ALPACA (CANONICAL_PRIMARY) - Try first
    # =========================================================================
    print(f"\n[ALPACA] Fetching {len(EQUITY_SYMBOLS)} equity symbols...")
    bars = get_alpaca_bars(EQUITY_SYMBOLS)

    equity_prices = []
    for symbol, symbol_bars in bars.items():
        for bar in symbol_bars:
            ts = datetime.fromisoformat(bar['t'].replace('Z', '+00:00'))
            equity_prices.append((
                symbol,
                ts,
                bar['o'],
                bar['h'],
                bar['l'],
                bar['c'],
                bar['v'],
                'alpaca',
                'alpaca',
                'CANONICAL_PRIMARY',
                'P1'
            ))

    if equity_prices:
        count = insert_prices(conn, equity_prices)
        print(f"[ALPACA] Inserted {count} equity price records")
        total_inserted += count
    else:
        print("[ALPACA] No equity data - falling back to yfinance (BACKUP)")
        # Fallback to yfinance
        yf_bars = get_yfinance_prices(EQUITY_SYMBOLS)
        for symbol, symbol_bars in yf_bars.items():
            for bar in symbol_bars:
                ts = datetime.fromisoformat(bar['t'])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                equity_prices.append((
                    symbol,
                    ts,
                    bar['o'],
                    bar['h'],
                    bar['l'],
                    bar['c'],
                    bar['v'],
                    'yfinance',
                    'yahoo_finance',
                    'BACKUP_ONLY',
                    'P1'
                ))
        if equity_prices:
            count = insert_prices(conn, equity_prices)
            print(f"[YFINANCE] Inserted {count} equity price records")
            total_inserted += count

    # =========================================================================
    # CRYPTO VIA BINANCE (CANONICAL_PRIMARY)
    # =========================================================================
    print(f"\n[BINANCE] Fetching {len(CRYPTO_SYMBOLS)} crypto symbols...")
    crypto_prices = []

    for symbol in CRYPTO_SYMBOLS:
        klines = get_binance_klines(symbol)
        for kline in klines:
            # Binance kline format: [open_time, open, high, low, close, volume, ...]
            ts = datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc)
            crypto_prices.append((
                symbol,
                ts,
                float(kline[1]),  # open
                float(kline[2]),  # high
                float(kline[3]),  # low
                float(kline[4]),  # close
                float(kline[5]),  # volume
                'binance',
                'binance',
                'CANONICAL_PRIMARY',
                'P1'
            ))

    if crypto_prices:
        count = insert_prices(conn, crypto_prices)
        print(f"[BINANCE] Inserted {count} crypto price records")
        total_inserted += count
    else:
        print("[BINANCE] No crypto data received")

    # =========================================================================
    # VERIFY
    # =========================================================================
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT canonical_id, MAX(timestamp::date) as latest, COUNT(*) as total
            FROM fhq_market.prices
            WHERE canonical_id IN ('NVDA', 'SPY', 'BTC-USD', 'ETH-USD')
            GROUP BY canonical_id
            ORDER BY canonical_id
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}: latest={row[1]}, total={row[2]}")

    print(f"\nTotal inserted: {total_inserted} records")

    conn.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
