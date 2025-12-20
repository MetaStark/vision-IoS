#!/usr/bin/env python3
"""
ALPACA PAPER ACCOUNT STATUS CHECK
CEO Query: Position status in paper mode
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv('C:/fhq-market-system/vision-ios/.env')

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

def main():
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')

    if not api_key or not secret_key:
        print('ERROR: Alpaca API keys not found in .env')
        sys.exit(1)

    client = TradingClient(api_key, secret_key, paper=True)

    # Get account info
    account = client.get_account()
    print('=' * 60)
    print('ALPACA PAPER ACCOUNT STATUS')
    print('=' * 60)
    print(f'Account ID: {account.id}')
    print(f'Status: {account.status}')
    print(f'Currency: {account.currency}')
    print()
    print('BALANCES:')
    print(f'  Cash: ${float(account.cash):,.2f}')
    print(f'  Portfolio Value: ${float(account.portfolio_value):,.2f}')
    print(f'  Equity: ${float(account.equity):,.2f}')
    print(f'  Buying Power: ${float(account.buying_power):,.2f}')
    print()
    print('P&L:')
    print(f'  Today P&L: ${float(account.equity) - float(account.last_equity):,.2f}')
    print()

    # Get positions
    positions = client.get_all_positions()
    print('=' * 60)
    print('OPEN POSITIONS')
    print('=' * 60)

    if not positions:
        print('No open positions.')
    else:
        total_market_value = 0
        total_unrealized_pl = 0
        for p in positions:
            qty = float(p.qty)
            market_value = float(p.market_value)
            unrealized_pl = float(p.unrealized_pl)
            unrealized_plpc = float(p.unrealized_plpc) * 100
            avg_entry = float(p.avg_entry_price)
            current = float(p.current_price)

            total_market_value += market_value
            total_unrealized_pl += unrealized_pl

            print(f'{p.symbol}:')
            print(f'  Qty: {qty}')
            print(f'  Avg Entry: ${avg_entry:,.2f}')
            print(f'  Current Price: ${current:,.2f}')
            print(f'  Market Value: ${market_value:,.2f}')
            print(f'  Unrealized P&L: ${unrealized_pl:,.2f} ({unrealized_plpc:+.2f}%)')
            print()

        print('-' * 60)
        print(f'TOTAL MARKET VALUE: ${total_market_value:,.2f}')
        print(f'TOTAL UNREALIZED P&L: ${total_unrealized_pl:,.2f}')

    # Get recent orders
    request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=10)
    orders = client.get_orders(request)

    print()
    print('=' * 60)
    print('RECENT ORDERS (Last 10)')
    print('=' * 60)

    if not orders:
        print('No recent orders.')
    else:
        for o in orders:
            filled_qty = o.filled_qty or 0
            filled_price = o.filled_avg_price or 0
            print(f'{o.symbol} | {o.side} | {o.qty} @ {o.type} | Status: {o.status}')
            if str(o.status) == 'filled':
                print(f'  Filled: {filled_qty} @ ${float(filled_price):,.2f}')
            print(f'  Submitted: {o.submitted_at}')
            print()


if __name__ == '__main__':
    main()
