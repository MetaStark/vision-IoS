#!/usr/bin/env python3
"""Check Alpaca Paper Account Status"""
import os
from dotenv import load_dotenv
load_dotenv()

import alpaca_trade_api as tradeapi

api = tradeapi.REST(
    key_id=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET'),
    base_url='https://paper-api.alpaca.markets',
    api_version='v2'
)

print('=' * 60)
print('ALPACA PAPER ACCOUNT STATUS')
print('=' * 60)

account = api.get_account()
print(f'Account Status: {account.status}')
print(f'Buying Power: ${float(account.buying_power):,.2f}')
print(f'Portfolio Value: ${float(account.portfolio_value):,.2f}')
print(f'Cash: ${float(account.cash):,.2f}')

print(f'\n--- POSITIONS ---')
positions = api.list_positions()
total_value = 0
for p in positions:
    pnl = float(p.unrealized_pl)
    pnl_pct = float(p.unrealized_plpc) * 100
    mv = float(p.market_value)
    total_value += mv
    sign = '+' if pnl >= 0 else ''
    print(f'{p.symbol:10} | Qty: {float(p.qty):>12.6f} | Value: ${mv:>10,.2f} | P&L: {sign}${pnl:,.2f} ({sign}{pnl_pct:.2f}%)')

print(f'\nTotal Position Value: ${total_value:,.2f}')

print(f'\n--- RECENT ORDERS ---')
orders = api.list_orders(status='all', limit=10)
for o in orders:
    filled = o.filled_qty or 0
    print(f'{o.symbol:10} | {o.side:4} | Qty: {o.qty} | Filled: {filled} | Status: {o.status}')
