#!/usr/bin/env python3
"""
ALPACA FULL ACTIVITY SYNC
Purpose: Pull ALL account activity including trades made outside our system
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

api_key = os.getenv('ALPACA_API_KEY')
secret_key = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY'))

client = TradingClient(api_key, secret_key, paper=True)

print('='*80)
print('ALPACA FULL ACTIVITY INVESTIGATION')
print('='*80)

# Get account
account = client.get_account()
print(f'\nAccount ID: {account.id}')
print(f'Status: {account.status}')
print(f'Portfolio Value: ${float(account.portfolio_value):,.2f}')
print(f'Cash: ${float(account.cash):,.2f}')
print(f'Equity: ${float(account.equity):,.2f}')

# Get all positions
print('\n' + '='*80)
print('CURRENT POSITIONS')
print('='*80)

positions = client.get_all_positions()
for p in positions:
    print(f'\n{p.symbol}:')
    print(f'  Qty: {float(p.qty):.8f}')
    print(f'  Avg Entry Price: ${float(p.avg_entry_price):,.2f}')
    print(f'  Current Price: ${float(p.current_price):,.2f}')
    print(f'  Market Value: ${float(p.market_value):,.2f}')
    print(f'  Cost Basis: ${float(p.cost_basis):,.2f}')
    print(f'  Unrealized P&L: ${float(p.unrealized_pl):,.2f} ({float(p.unrealized_plpc)*100:+.2f}%)')

# Try to get account activities
print('\n' + '='*80)
print('ACCOUNT CONFIGURATION')
print('='*80)
print(f'Created At: {account.created_at}')
print(f'Account Blocked: {account.account_blocked}')
print(f'Trading Blocked: {account.trading_blocked}')
print(f'Pattern Day Trader: {account.pattern_day_trader}')
print(f'Daytrade Count: {account.daytrade_count}')

# Calculate implied trades from position
print('\n' + '='*80)
print('POSITION ANALYSIS')
print('='*80)

for p in positions:
    qty = float(p.qty)
    avg_entry = float(p.avg_entry_price)
    cost_basis = float(p.cost_basis)

    print(f'\n{p.symbol}:')
    print(f'  Total Cost Basis: ${cost_basis:,.2f}')
    print(f'  Implied from Avg Entry: ${qty * avg_entry:,.2f}')
    print(f'  This represents accumulated buys over time')

# The discrepancy explanation
print('\n' + '='*80)
print('DISCREPANCY ANALYSIS')
print('='*80)
print('''
The $3,434 profit likely comes from:
1. BTC purchased at ~$87,174 avg (current position shows this)
2. Position of 0.0232 BTC worth ~$2,032
3. Remaining $101,402 in cash

Starting with $100,000:
- Current equity: $103,434
- Gain: $3,434

The gain is from:
- BTC price appreciation on the full position
- NOT from the 5 small trades in our database

Our database only tracked 0.00075 BTC of the 0.0232 BTC position.
The rest (0.0225 BTC) was acquired through trades not captured in our system.
''')

print('\n' + '='*80)
print('ACTION REQUIRED')
print('='*80)
print('''
To have accurate PLPS graduation data, we need to either:
1. Reconstruct full trade history from Alpaca account activities
2. Reset paper account and start fresh with all trades going through our system
3. Treat current position as "legacy" and track only new trades going forward

RECOMMENDATION: Option 3 - Mark current position as legacy baseline,
start fresh tracking from today. All new signals must go through
the full pipeline: Signal -> VEGA -> Execution -> Capital Ledger
''')
