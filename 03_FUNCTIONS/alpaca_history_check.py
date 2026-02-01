#!/usr/bin/env python3
"""Alpaca Paper Trading History Check - CEO Query"""

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

client = TradingClient(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY')),
    paper=True
)

# Get account for P&L calculation
account = client.get_account()
portfolio_value = float(account.portfolio_value)
starting_capital = 100000.00  # Alpaca paper starts with $100k

total_pnl = portfolio_value - starting_capital
total_pnl_pct = (total_pnl / starting_capital) * 100

print('='*80)
print('ALPACA PAPER TRADING - FREEDOM WAR STATUS')
print('='*80)
print()
print(f'Starting Capital:  $100,000.00')
print(f'Current Value:     ${portfolio_value:,.2f}')
print(f'Total P&L:         ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)')
print()

# Get all filled orders
request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100)
orders = client.get_orders(request)

filled_orders = [o for o in orders if str(o.status) == 'filled']
print(f'Total Filled Orders: {len(filled_orders)}')
print()

print('='*80)
print('FILLED ORDERS (Most Recent First)')
print('='*80)

total_buys = 0
total_sells = 0

for o in filled_orders[:20]:  # Last 20 orders
    side = str(o.side)
    filled_price = float(o.filled_avg_price) if o.filled_avg_price else 0
    filled_qty = float(o.filled_qty) if o.filled_qty else 0
    value = filled_price * filled_qty

    if side == 'buy':
        total_buys += value
    else:
        total_sells += value

    # Format timestamp
    ts = o.filled_at or o.submitted_at
    ts_str = str(ts)[:19] if ts else 'N/A'

    print(f'{o.symbol:8} | {side.upper():4} | Qty: {filled_qty:>12.6f} | @ ${filled_price:>10,.2f} | ${value:>10,.2f} | {ts_str}')

print()
print('-'*80)
print(f'Total Bought (last 20): ${total_buys:,.2f}')
print(f'Total Sold (last 20):   ${total_sells:,.2f}')
print()
print('='*80)
print('CURRENT POSITIONS')
print('='*80)

positions = client.get_all_positions()
if not positions:
    print('No open positions.')
else:
    for p in positions:
        qty = float(p.qty)
        market_value = float(p.market_value)
        unrealized_pl = float(p.unrealized_pl)
        unrealized_plpc = float(p.unrealized_plpc) * 100
        avg_entry = float(p.avg_entry_price)
        current = float(p.current_price)

        print(f'{p.symbol}:')
        print(f'  Qty: {qty}')
        print(f'  Avg Entry: ${avg_entry:,.2f}')
        print(f'  Current: ${current:,.2f}')
        print(f'  Market Value: ${market_value:,.2f}')
        print(f'  Unrealized P&L: ${unrealized_pl:,.2f} ({unrealized_plpc:+.2f}%)')

print()
print('='*80)
print('SIGNAL-TO-CAPITAL VALIDATION')
print('='*80)
print(f'Paper Trading P&L: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)')
print()
if total_pnl > 0:
    print('STATUS: PROFITABLE - Signals are generating alpha in real markets')
    print('RECOMMENDATION: Continue paper validation before live capital deployment')
else:
    print('STATUS: UNPROFITABLE - Signals need refinement')
    print('RECOMMENDATION: Do NOT deploy live capital until paper trading is profitable')
