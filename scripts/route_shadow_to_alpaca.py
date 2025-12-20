#!/usr/bin/env python3
"""
Route Shadow Trades to Alpaca Paper
CEO Directive: Make trades visible in Alpaca
"""
import os
import sys
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env', override=True)

import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError

# Config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

api = tradeapi.REST(
    key_id=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET'),
    base_url='https://paper-api.alpaca.markets',
    api_version='v2'
)

print('=' * 60)
print('SHADOW TRADE -> ALPACA PAPER ROUTING')
print('=' * 60)

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Get OPEN shadow trades
cur.execute('''
    SELECT trade_id, shadow_trade_ref, asset_id, direction, entry_price, entry_confidence
    FROM fhq_execution.shadow_trades
    WHERE status = 'OPEN'
    ORDER BY created_at
''')
shadow_trades = cur.fetchall()
print(f'Found {len(shadow_trades)} OPEN shadow trades')

# Asset symbol mapping for Alpaca
SYMBOL_MAP = {
    'BTC-USD': 'BTCUSD',
    'ETH-USD': 'ETHUSD',
    'SOL-USD': 'SOLUSD',
    'SPY': 'SPY',
    'QQQ': 'QQQ',
    'AAPL': 'AAPL',
    'MSFT': 'MSFT',
    'NVDA': 'NVDA'
}

# Trade sizing - use small notional for paper
NOTIONAL_SIZE = 100  # $100 per trade

routed = 0
for trade in shadow_trades:
    asset_id = trade['asset_id']
    symbol = SYMBOL_MAP.get(asset_id)

    if not symbol:
        print(f'  SKIP: {asset_id} - no symbol mapping')
        continue

    direction = trade['direction']
    side = 'buy' if direction == 'LONG' else 'sell'

    try:
        # Check if crypto or equity
        is_crypto = symbol in ['BTCUSD', 'ETHUSD', 'SOLUSD']

        if is_crypto:
            # Use notional for crypto
            order = api.submit_order(
                symbol=symbol,
                notional=NOTIONAL_SIZE,
                side=side,
                type='market',
                time_in_force='gtc'
            )
        else:
            # Use qty for equities (1 share each for paper testing)
            order = api.submit_order(
                symbol=symbol,
                qty=1,
                side=side,
                type='market',
                time_in_force='day'
            )

        print(f'  ROUTED: {side.upper()} {symbol} | Order: {order.id} | Status: {order.status}')

        # Update shadow trade with Alpaca order ID
        cur.execute('''
            UPDATE fhq_execution.shadow_trades
            SET status = 'ROUTED',
                updated_at = NOW()
            WHERE trade_id = %s
        ''', (trade['trade_id'],))
        conn.commit()
        routed += 1

        time.sleep(0.5)  # Rate limit

    except APIError as e:
        print(f'  FAIL: {symbol} - {e}')
    except Exception as e:
        print(f'  ERROR: {symbol} - {e}')

print(f'\nRouted {routed}/{len(shadow_trades)} trades to Alpaca Paper')

# Check positions now
time.sleep(2)
positions = api.list_positions()
print(f'\nAlpaca Paper Positions: {len(positions)}')
for p in positions:
    pnl = float(p.unrealized_pl)
    pnl_str = f'+${pnl:,.2f}' if pnl >= 0 else f'-${abs(pnl):,.2f}'
    print(f'  {p.symbol}: {p.qty} @ ${float(p.current_price):,.2f} = ${float(p.market_value):,.2f} ({pnl_str})')

cur.close()
conn.close()
