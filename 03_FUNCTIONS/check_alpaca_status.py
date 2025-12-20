#!/usr/bin/env python3
"""Quick Alpaca status check."""
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
import os
from dotenv import load_dotenv

load_dotenv()

client = TradingClient(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY')),
    paper=True
)

print('='*70)
print('ALPACA ACCOUNT STATUS')
print('='*70)

account = client.get_account()
print(f'Portfolio Value: ${float(account.portfolio_value):,.2f}')
print(f'Cash:            ${float(account.cash):,.2f}')
print(f'Buying Power:    ${float(account.buying_power):,.2f}')
print(f'Equity:          ${float(account.equity):,.2f}')
print(f'Margin Used:     ${float(account.initial_margin):,.2f}')

print()
print('='*70)
print('OPEN POSITIONS')
print('='*70)

positions = client.get_all_positions()
total_value = 0
for pos in positions:
    mv = float(pos.market_value)
    total_value += mv
    up = float(pos.unrealized_pl)
    upp = float(pos.unrealized_plpc) * 100
    print(f'{pos.symbol:8} | Qty: {pos.qty:>6} | Value: ${mv:>12,.2f} | P/L: ${up:>10,.2f} ({upp:>6.2f}%)')

print(f'\nTotal Position Value: ${total_value:,.2f}')

print()
print('='*70)
print('OPEN/PENDING ORDERS')
print('='*70)

orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
if orders:
    for order in orders:
        print(f'{order.symbol:8} | {order.side} {order.qty} | Status: {order.status} | Type: {order.type} | ID: {order.id}')
else:
    print('No pending orders')
