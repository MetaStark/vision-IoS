#!/usr/bin/env python3
"""
AUTONOMOUS PIPELINE EXECUTOR
============================
CEO-DIR-2026-AUTONOMY-PIPELINE-ACTIVATION-001

This daemon:
1. Reads EXECUTING entries from autonomous_execution_queue
2. Submits orders to Alpaca Paper Trading
3. Updates execution_logs with results
4. Completes the autonomous execution chain

Authority: CEO, STIG, VEGA, LINE
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        TakeProfitRequest,
        StopLossRequest
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("WARNING: Alpaca SDK not installed. Run: pip install alpaca-py")

logging.basicConfig(
    level=logging.INFO,
    format='[AUTONOMOUS-EXECUTOR] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Alpaca config
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))

# Symbol mapping for Alpaca
SYMBOL_MAP = {
    'BTC-USD': 'BTC/USD',
    'ETH-USD': 'ETH/USD',
    'SOL-USD': 'SOL/USD',
    'CRO-USD': 'CRO/USD',
    'EOS-USD': 'EOS/USD',
    'FIL-USD': 'FIL/USD',
    'ICP-USD': 'ICP/USD',
    'NEAR-USD': 'NEAR/USD',
    'SPY': 'SPY',
    'QQQ': 'QQQ',
    'XLF': 'XLF',
}


class AutonomousPipelineExecutor:
    """
    Executor daemon for the autonomous pipeline.

    Reads entries in EXECUTING status and submits to Alpaca.
    """

    def __init__(self):
        self.conn = None
        self.trading_client = None

    def connect(self):
        """Connect to database and Alpaca."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

        if ALPACA_AVAILABLE and ALPACA_API_KEY:
            self.trading_client = TradingClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY,
                paper=True  # ALWAYS paper mode
            )
            logger.info("Connected to Alpaca Paper Trading")
        else:
            logger.warning("Alpaca not configured - will simulate executions")

    def close(self):
        """Close connections."""
        if self.conn:
            self.conn.close()

    def get_executing_entries(self):
        """Get all entries in EXECUTING status."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_execution.autonomous_execution_queue
                WHERE queue_status = 'EXECUTING'
                ORDER BY queued_at
            """)
            return cur.fetchall()

    def execute_order(self, entry: Dict) -> Dict:
        """Execute a single order via Alpaca with MANDATORY TP/SL bracket."""
        asset = entry['asset']
        direction = entry['direction']
        size_usd = float(entry['position_size_usd'])
        entry_price = float(entry['entry_price'])

        # CRITICAL: Extract TP/SL from queue entry (CEO-DIR-2026-AUTONOMY fix)
        stop_loss_price = float(entry['stop_loss_price']) if entry.get('stop_loss_price') else None
        take_profit_price = float(entry['take_profit_price']) if entry.get('take_profit_price') else None

        # Map symbol
        symbol = SYMBOL_MAP.get(asset, asset)
        side = OrderSide.BUY if direction == 'LONG' else OrderSide.SELL

        result = {
            'queue_id': str(entry['queue_id']),
            'asset': asset,
            'symbol': symbol,
            'direction': direction,
            'size_usd': size_usd,
            'stop_loss_price': stop_loss_price,
            'take_profit_price': take_profit_price,
            'alpaca_order_id': None,
            'status': 'PENDING',
            'error': None
        }

        if not self.trading_client:
            # Simulation mode
            result['status'] = 'SIMULATED'
            result['alpaca_order_id'] = f'SIM-{entry["queue_id"]}'
            logger.info(f"SIMULATED: {direction} {symbol} ${size_usd:.2f} TP={take_profit_price} SL={stop_loss_price}")
            return result

        # MANDATORY: Reject orders without TP/SL
        if stop_loss_price is None or take_profit_price is None:
            result['status'] = 'REJECTED'
            result['error'] = 'MANDATORY TP/SL missing - order rejected per CEO directive'
            logger.error(f"REJECTED: {direction} {symbol} - Missing TP/SL (TP={take_profit_price}, SL={stop_loss_price})")
            return result

        try:
            # Calculate quantity
            qty = size_usd / entry_price
            is_crypto = '/' in symbol or '-USD' in asset

            # Build bracket order with TP/SL
            if is_crypto:
                # Crypto - use notional with bracket
                request = MarketOrderRequest(
                    symbol=symbol,
                    notional=round(size_usd, 2),
                    side=side,
                    time_in_force=TimeInForce.GTC,
                    order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=round(take_profit_price, 2)),
                    stop_loss=StopLossRequest(stop_price=round(stop_loss_price, 2))
                )
            else:
                # Equity - use qty with bracket
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=int(qty),
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=round(take_profit_price, 2)),
                    stop_loss=StopLossRequest(stop_price=round(stop_loss_price, 2))
                )

            order = self.trading_client.submit_order(request)

            result['alpaca_order_id'] = str(order.id)
            result['status'] = str(order.status)
            result['order_class'] = 'BRACKET'
            logger.info(f"SUBMITTED BRACKET: {direction} {symbol} ${size_usd:.2f} TP=${take_profit_price} SL=${stop_loss_price} -> {order.id}")

        except Exception as e:
            result['status'] = 'FAILED'
            result['error'] = str(e)
            logger.error(f"FAILED: {direction} {symbol} - {e}")

        return result

    def update_queue_entry(self, queue_id: str, result: Dict):
        """Update queue entry with execution result."""
        # Handle various Alpaca status formats (OrderStatus.FILLED, 'filled', etc.)
        status_str = str(result['status']).lower()
        success_statuses = ('filled', 'simulated', 'new', 'accepted', 'pending_new', 'orderstatus.filled', 'orderstatus.new', 'orderstatus.pending_new', 'orderstatus.accepted')
        status = 'COMPLETED' if any(s in status_str for s in success_statuses) else 'FAILED'

        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_execution.autonomous_execution_queue
                SET queue_status = %s,
                    executed_at = NOW(),
                    execution_result = %s
                WHERE queue_id = %s::uuid
            """, (status, json.dumps(result), queue_id))

        self.conn.commit()

    def update_execution_log(self, entry: Dict, result: Dict):
        """Update execution_logs with Alpaca result."""
        # Handle various Alpaca status formats
        status_str = str(result['status']).lower()
        success_statuses = ('filled', 'simulated', 'new', 'accepted', 'pending_new', 'orderstatus.filled', 'orderstatus.new', 'orderstatus.pending_new', 'orderstatus.accepted')
        action_type = 'ORDER_FILLED' if any(s in status_str for s in success_statuses) else 'ORDER_FAILED'

        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_execution.execution_logs
                SET alpaca_order_id = %s,
                    execution_result = %s,
                    action_type = %s
                WHERE decision_pack_id = %s::uuid
                AND action_type = 'ORDER_SUBMITTED'
            """, (
                result.get('alpaca_order_id'),
                json.dumps(result),
                action_type,
                str(entry['decision_pack_id'])
            ))

        self.conn.commit()

    def run_once(self):
        """Execute all pending entries once."""
        entries = self.get_executing_entries()

        if not entries:
            logger.info("No entries in EXECUTING status")
            return 0

        logger.info(f"Processing {len(entries)} EXECUTING entries")

        executed = 0
        for entry in entries:
            result = self.execute_order(entry)
            self.update_queue_entry(str(entry['queue_id']), result)
            self.update_execution_log(entry, result)
            executed += 1
            time.sleep(0.5)  # Rate limit

        return executed

    def run_daemon(self, interval_seconds: int = 60):
        """Run as daemon, checking for new entries periodically."""
        logger.info(f"Starting daemon with {interval_seconds}s interval")

        while True:
            try:
                executed = self.run_once()
                if executed > 0:
                    logger.info(f"Executed {executed} orders")
            except Exception as e:
                logger.error(f"Daemon error: {e}")
                # Reconnect on error
                try:
                    self.close()
                    self.connect()
                except:
                    pass

            time.sleep(interval_seconds)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Autonomous Pipeline Executor')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--interval', type=int, default=60, help='Daemon interval in seconds')
    args = parser.parse_args()

    executor = AutonomousPipelineExecutor()
    executor.connect()

    try:
        if args.daemon:
            executor.run_daemon(args.interval)
        else:
            executed = executor.run_once()
            print(f"Executed {executed} orders")
    finally:
        executor.close()


if __name__ == '__main__':
    main()
