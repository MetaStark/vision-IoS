#!/usr/bin/env python3
"""
ALPACA HISTORY SYNC - Pull Paper Trading History into Capital Ledger
CEO Directive: CEO-DIR-2026-PLPS-001
Purpose: Sync Alpaca paper trades with Market Realism Filter applied

This script:
1. Pulls all trades from Alpaca paper account
2. Applies slippage/spread haircuts per asset
3. Computes conservative PnL
4. Stores in fhq_execution.alpaca_trade_sync
5. Generates Regime x Strategy matrix
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment
load_dotenv()

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

# Database connection
def get_db_conn():
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )

# Get realism config for asset
def get_realism_config(cursor, symbol):
    """Get slippage and spread haircuts for an asset."""
    # First try exact symbol match
    cursor.execute("""
        SELECT slippage_haircut_bps, spread_haircut_bps, liquidity_tier
        FROM fhq_execution.market_realism_config
        WHERE asset_symbol = %s AND is_active = TRUE
        LIMIT 1
    """, (symbol,))
    row = cursor.fetchone()

    if row:
        return row

    # Fall back to asset class default
    asset_class = 'CRYPTO' if 'USD' in symbol and symbol not in ['USDHKD=X'] else 'EQUITY'
    cursor.execute("""
        SELECT slippage_haircut_bps, spread_haircut_bps, liquidity_tier
        FROM fhq_execution.market_realism_config
        WHERE asset_class = %s AND asset_symbol IS NULL AND is_active = TRUE
        LIMIT 1
    """, (asset_class,))
    row = cursor.fetchone()

    return row or {'slippage_haircut_bps': 5.0, 'spread_haircut_bps': 10.0, 'liquidity_tier': 'MEDIUM'}

# Get current regime
def get_current_regime(cursor, symbol='BTC-USD'):
    """Get current sovereign regime for an asset."""
    cursor.execute("""
        SELECT sovereign_regime
        FROM fhq_perception.sovereign_regime_state_v4
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    return row['sovereign_regime'] if row else 'UNKNOWN'

# Get current LSA hash
def get_current_lsa_hash(cursor):
    """Get current canonical LSA hash."""
    cursor.execute("""
        SELECT content_hash
        FROM fhq_meta.learning_state_artifacts
        WHERE is_canonical = TRUE
        ORDER BY created_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    return row['content_hash'] if row else None

def sync_alpaca_trades():
    """Main sync function."""
    print('='*80)
    print('ALPACA PAPER TRADING HISTORY SYNC')
    print('CEO-DIR-2026-PLPS-001: Market Realism Filter Applied')
    print('='*80)
    print()

    # Initialize Alpaca client
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY'))

    if not api_key or not secret_key:
        print('ERROR: Alpaca API keys not found in .env')
        sys.exit(1)

    client = TradingClient(api_key, secret_key, paper=True)

    # Get account info
    account = client.get_account()
    portfolio_value = float(account.portfolio_value)
    starting_capital = 100000.00
    total_pnl = portfolio_value - starting_capital

    print(f'Account Status: {account.status}')
    print(f'Portfolio Value: ${portfolio_value:,.2f}')
    print(f'Starting Capital: ${starting_capital:,.2f}')
    print(f'Gross P&L: ${total_pnl:,.2f} ({(total_pnl/starting_capital)*100:.2f}%)')
    print()

    # Get all orders
    request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500)
    orders = client.get_orders(request)

    filled_orders = [o for o in orders if str(o.status) == 'filled']
    print(f'Total Filled Orders from Alpaca API: {len(filled_orders)}')

    # Get current positions for unrealized P&L
    positions = {p.symbol: p for p in client.get_all_positions()}

    # Connect to database
    conn = get_db_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get current regime and LSA
    current_regime = get_current_regime(cursor)
    lsa_hash = get_current_lsa_hash(cursor)

    print(f'Current Regime: {current_regime}')
    print(f'LSA Hash: {lsa_hash[:16]}...' if lsa_hash else 'LSA Hash: None')
    print()

    # Sync each order
    synced_count = 0
    skipped_count = 0
    total_haircut = 0

    print('='*80)
    print('SYNCING TRADES WITH MARKET REALISM HAIRCUTS')
    print('='*80)

    for order in filled_orders:
        # Check if already synced
        cursor.execute("""
            SELECT sync_id FROM fhq_execution.alpaca_trade_sync
            WHERE alpaca_order_id = %s
        """, (str(order.id),))

        if cursor.fetchone():
            skipped_count += 1
            continue

        # Get realism config
        symbol = order.symbol
        realism = get_realism_config(cursor, symbol)
        slippage_bps = float(realism['slippage_haircut_bps']) if isinstance(realism, dict) else float(realism[0])
        spread_bps = float(realism['spread_haircut_bps']) if isinstance(realism, dict) else float(realism[1])

        # Calculate trade value and haircut
        filled_qty = float(order.filled_qty) if order.filled_qty else 0
        avg_price = float(order.filled_avg_price) if order.filled_avg_price else 0
        trade_value = filled_qty * avg_price

        # Haircut = (slippage + spread) * trade_value / 10000
        haircut_bps_total = slippage_bps + spread_bps
        haircut_usd = (haircut_bps_total / 10000) * trade_value
        total_haircut += haircut_usd

        # Get realized P&L from position if available
        realized_pnl = 0
        unrealized_pnl = 0
        if symbol in positions:
            pos = positions[symbol]
            unrealized_pnl = float(pos.unrealized_pl)

        # Insert into sync table
        cursor.execute("""
            INSERT INTO fhq_execution.alpaca_trade_sync (
                alpaca_order_id,
                symbol,
                side,
                qty,
                filled_qty,
                avg_fill_price,
                submitted_at,
                filled_at,
                slippage_est_bps,
                spread_est_bps,
                realized_pnl_usd,
                unrealized_pnl_usd,
                regime_at_entry,
                lsa_hash,
                sync_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            str(order.id),
            symbol,
            str(order.side),
            float(order.qty),
            filled_qty,
            avg_price,
            order.submitted_at,
            order.filled_at,
            slippage_bps,
            spread_bps,
            realized_pnl,
            unrealized_pnl,
            current_regime,
            lsa_hash,
            'ALPACA_API'
        ))

        synced_count += 1
        print(f'{symbol:8} | {str(order.side):4} | Qty: {filled_qty:>12.6f} | @ ${avg_price:>10,.2f} | Haircut: ${haircut_usd:>6.2f}')

    conn.commit()

    print()
    print('='*80)
    print('SYNC SUMMARY')
    print('='*80)
    print(f'Orders Synced: {synced_count}')
    print(f'Orders Skipped (already synced): {skipped_count}')
    print(f'Total Haircut Applied: ${total_haircut:,.2f}')
    print()

    # Compute conservative P&L
    gross_pnl = total_pnl
    conservative_pnl = gross_pnl - total_haircut

    print('='*80)
    print('CONSERVATIVE P&L (after Market Realism Haircut)')
    print('='*80)
    print(f'Gross P&L:        ${gross_pnl:,.2f}')
    print(f'Haircut Applied:  ${total_haircut:,.2f}')
    print(f'Conservative P&L: ${conservative_pnl:,.2f}')
    print()

    if conservative_pnl > 0:
        print('STATUS: CONSERVATIVE P&L POSITIVE - Edge survives realism filter')
    else:
        print('STATUS: CONSERVATIVE P&L NEGATIVE - Edge does NOT survive realism filter')

    # Generate Regime x Strategy Matrix
    print()
    print('='*80)
    print('REGIME x STRATEGY MATRIX')
    print('='*80)

    cursor.execute("""
        SELECT * FROM fhq_execution.v_regime_strategy_matrix
    """)
    matrix = cursor.fetchall()

    if matrix:
        print(f'{"Regime":<12} | {"Symbol":<10} | {"Trades":>6} | {"Wins":>5} | {"Losses":>6} | {"Avg P&L":>10} | {"Total P&L":>12} | {"PF":>6} | {"Win%":>6}')
        print('-'*90)
        for row in matrix:
            print(f'{row["regime"] or "N/A":<12} | {row["symbol"]:<10} | {row["trade_count"]:>6} | {row["wins"]:>5} | {row["losses"]:>6} | ${row["avg_pnl"] or 0:>9,.2f} | ${row["total_pnl"] or 0:>11,.2f} | {row["profit_factor"] or 0:>5.2f} | {row["win_rate_pct"] or 0:>5.1f}%')
    else:
        print('No trade data in matrix yet.')

    # Check PLPS graduation criteria
    print()
    print('='*80)
    print('PLPS GRADUATION CHECK')
    print('='*80)

    cursor.execute("SELECT * FROM fhq_governance.plps_gate_config WHERE is_active = TRUE LIMIT 1")
    plps = cursor.fetchone()

    if plps:
        # Count all trades
        cursor.execute("SELECT COUNT(*) as count FROM fhq_execution.alpaca_trade_sync")
        trade_count = cursor.fetchone()['count']

        # Calculate profit factor from matrix
        cursor.execute("""
            SELECT
                SUM(CASE WHEN realized_pnl_usd > 0 THEN realized_pnl_usd ELSE 0 END) as gross_profit,
                ABS(SUM(CASE WHEN realized_pnl_usd < 0 THEN realized_pnl_usd ELSE 0 END)) as gross_loss
            FROM fhq_execution.alpaca_trade_sync
        """)
        pf_data = cursor.fetchone()
        gross_profit = float(pf_data['gross_profit'] or 0)
        gross_loss = float(pf_data['gross_loss'] or 0.001)  # Avoid division by zero
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Count unique regimes
        cursor.execute("""
            SELECT COUNT(DISTINCT regime_at_entry) as regime_count
            FROM fhq_execution.alpaca_trade_sync
            WHERE regime_at_entry IS NOT NULL
        """)
        regime_count = cursor.fetchone()['regime_count']

        # Gate checks
        gate_trades = trade_count >= plps['minimum_trades']
        gate_pf = profit_factor >= float(plps['profit_factor_floor'])
        gate_regimes = regime_count >= plps['regime_coverage_min']
        gate_conservative = conservative_pnl > 0

        print(f'Minimum Trades:     {trade_count:>5} / {plps["minimum_trades"]} {"PASS" if gate_trades else "FAIL"}')
        print(f'Profit Factor:      {profit_factor:>5.2f} / {plps["profit_factor_floor"]} {"PASS" if gate_pf else "FAIL"}')
        print(f'Regime Coverage:    {regime_count:>5} / {plps["regime_coverage_min"]} {"PASS" if gate_regimes else "FAIL"}')
        print(f'Conservative P&L:   ${conservative_pnl:>10,.2f} {"PASS" if gate_conservative else "FAIL"}')
        print()

        all_passed = gate_trades and gate_pf and gate_regimes and gate_conservative

        if all_passed:
            print('GRADUATION STATUS: ALL GATES PASSED - Ready for VEGA attestation')
        else:
            print('GRADUATION STATUS: NOT YET - Continue paper trading')

    cursor.close()
    conn.close()

    print()
    print('='*80)
    print('SYNC COMPLETE')
    print('='*80)

    return {
        'synced': synced_count,
        'skipped': skipped_count,
        'gross_pnl': gross_pnl,
        'haircut': total_haircut,
        'conservative_pnl': conservative_pnl
    }


if __name__ == '__main__':
    result = sync_alpaca_trades()
