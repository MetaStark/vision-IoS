#!/usr/bin/env python3
"""
S-TIER EXIT MONITOR DAEMON
==========================
Authority: CEO-DIR-2025-EXE-001
Purpose: Monitor S-tier positions and execute exits based on:
  1. Stop Loss (2% below entry)
  2. Take Profit (3% above entry)
  3. Time Exit (4 hours from fill)

This daemon runs continuously and checks every 30 seconds.
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[EXIT-MONITOR] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('s_tier_exit_monitor.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CHECK_INTERVAL_SECONDS = 30
STOP_LOSS_PCT = 2.0
TAKE_PROFIT_PCT = 3.0
TIME_EXIT_HOURS = 4

# Database
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Alpaca
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.data.historical import CryptoHistoricalDataClient
    from alpaca.data.requests import CryptoLatestQuoteRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.error("Alpaca SDK not available")

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))


class STierExitMonitor:
    def __init__(self):
        self.trading_client = None
        self.data_client = None
        self.db_conn = None
        self.running = True

    def connect(self):
        """Connect to Alpaca and database."""
        if ALPACA_AVAILABLE and ALPACA_API_KEY:
            self.trading_client = TradingClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY,
                paper=True
            )
            self.data_client = CryptoHistoricalDataClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY
            )
            logger.info("Connected to Alpaca Paper Trading")

        self.db_conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

    def get_open_s_tier_executions(self):
        """Get open S-tier executions from database."""
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    execution_id,
                    needle_id,
                    target_asset,
                    entry_price,
                    position_size_qty,
                    stop_loss_pct,
                    take_profit_pct,
                    time_exit_hours,
                    filled_at,
                    execution_status
                FROM fhq_execution.s_tier_executions
                WHERE execution_status = 'OPEN'
            """)
            return cur.fetchall()

    def get_current_price(self, symbol: str) -> float:
        """Get current price from Alpaca."""
        if not self.data_client:
            return None

        # Convert symbol format
        alpaca_symbol = symbol.replace('-', '/')
        if '/' not in alpaca_symbol:
            alpaca_symbol = f"{alpaca_symbol}/USD"

        try:
            quote = self.data_client.get_crypto_latest_quote(
                CryptoLatestQuoteRequest(symbol_or_symbols=[alpaca_symbol])
            )
            return float(quote[alpaca_symbol].ask_price)
        except Exception as e:
            logger.error(f"Failed to get price for {alpaca_symbol}: {e}")
            return None

    def get_alpaca_position(self, symbol: str):
        """Get position from Alpaca."""
        if not self.trading_client:
            return None

        try:
            positions = self.trading_client.get_all_positions()
            for p in positions:
                if symbol.replace('-', '').replace('/', '') in p.symbol.replace('/', ''):
                    return p
            return None
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return None

    def close_position(self, execution: dict, exit_reason: str, exit_price: float):
        """Close position on Alpaca and update database."""
        symbol = execution['target_asset']
        qty = float(execution['position_size_qty'])
        entry_price = float(execution['entry_price'])

        logger.info(f"CLOSING POSITION: {symbol} - Reason: {exit_reason}")

        # Close on Alpaca
        if self.trading_client:
            try:
                alpaca_symbol = symbol.replace('-', '/')
                if '/' not in alpaca_symbol:
                    alpaca_symbol = f"{alpaca_symbol}/USD"

                # Get actual position quantity from Alpaca
                position = self.get_alpaca_position(symbol)
                if position:
                    actual_qty = float(position.qty)

                    order = MarketOrderRequest(
                        symbol=alpaca_symbol,
                        qty=actual_qty,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.GTC
                    )
                    result = self.trading_client.submit_order(order)
                    logger.info(f"Alpaca sell order submitted: {result.id}")

                    # Wait for fill
                    time.sleep(2)
                    filled_order = self.trading_client.get_order_by_id(result.id)
                    if filled_order.filled_avg_price:
                        exit_price = float(filled_order.filled_avg_price)
                        logger.info(f"Filled at ${exit_price:,.2f}")
                else:
                    logger.warning("No Alpaca position found to close")

            except Exception as e:
                logger.error(f"Failed to close on Alpaca: {e}")

        # Calculate P&L
        pnl_usd = (exit_price - entry_price) * qty
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100

        # Determine outcome
        if exit_reason == 'TAKE_PROFIT':
            outcome = 'WIN'
        elif exit_reason == 'STOP_LOSS':
            outcome = 'LOSS'
        else:
            outcome = 'WIN' if pnl_usd >= 0 else 'LOSS'

        # Update database
        with self.db_conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_execution.s_tier_executions
                SET
                    execution_status = 'CLOSED',
                    closed_at = NOW(),
                    exit_price = %s,
                    exit_reason = %s,
                    pnl_usd = %s,
                    pnl_pct = %s,
                    outcome = %s
                WHERE execution_id = %s
            """, (exit_price, exit_reason, pnl_usd, pnl_pct, outcome, execution['execution_id']))

            # Update signal state to COOLING
            cur.execute("""
                UPDATE fhq_canonical.golden_needles
                SET g5_signal_state = 'COOLING'
                WHERE needle_id = %s
            """, (execution['needle_id'],))

        self.db_conn.commit()

        logger.info(f"Position closed: {symbol}")
        logger.info(f"  Entry: ${entry_price:,.2f}")
        logger.info(f"  Exit:  ${exit_price:,.2f}")
        logger.info(f"  P&L:   ${pnl_usd:,.2f} ({pnl_pct:+.2f}%)")
        logger.info(f"  Outcome: {outcome}")
        logger.info(f"  Reason: {exit_reason}")

        return {
            'outcome': outcome,
            'pnl_usd': pnl_usd,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason
        }

    def check_exit_conditions(self, execution: dict) -> tuple:
        """
        Check if any exit condition is met.

        Returns: (should_exit: bool, exit_reason: str, current_price: float)
        """
        symbol = execution['target_asset']
        entry_price = float(execution['entry_price'])
        filled_at = execution['filled_at']

        # Get current price
        current_price = self.get_current_price(symbol)
        if not current_price:
            return False, None, None

        # Calculate levels
        stop_loss_price = entry_price * (1 - STOP_LOSS_PCT / 100)
        take_profit_price = entry_price * (1 + TAKE_PROFIT_PCT / 100)
        time_exit_at = filled_at + timedelta(hours=TIME_EXIT_HOURS)

        now = datetime.now(timezone.utc)
        if filled_at.tzinfo is None:
            filled_at = filled_at.replace(tzinfo=timezone.utc)

        # Check conditions
        if current_price <= stop_loss_price:
            return True, 'STOP_LOSS', current_price

        if current_price >= take_profit_price:
            return True, 'TAKE_PROFIT', current_price

        if now >= time_exit_at:
            return True, 'TIME_EXIT', current_price

        # Log status
        pct_from_entry = ((current_price - entry_price) / entry_price) * 100
        time_remaining = time_exit_at - now
        minutes_remaining = time_remaining.total_seconds() / 60

        logger.debug(f"{symbol}: ${current_price:,.2f} ({pct_from_entry:+.2f}%) - "
                    f"Time remaining: {minutes_remaining:.0f}m")

        return False, None, current_price

    def run(self):
        """Main monitoring loop."""
        logger.info("=" * 60)
        logger.info("S-TIER EXIT MONITOR STARTED")
        logger.info(f"Stop Loss: {STOP_LOSS_PCT}%")
        logger.info(f"Take Profit: {TAKE_PROFIT_PCT}%")
        logger.info(f"Time Exit: {TIME_EXIT_HOURS}h")
        logger.info(f"Check Interval: {CHECK_INTERVAL_SECONDS}s")
        logger.info("=" * 60)

        self.connect()

        while self.running:
            try:
                executions = self.get_open_s_tier_executions()

                if not executions:
                    logger.info("No open S-tier positions")
                else:
                    for execution in executions:
                        should_exit, exit_reason, current_price = self.check_exit_conditions(execution)

                        if should_exit:
                            self.close_position(execution, exit_reason, current_price)
                        else:
                            # Log status
                            entry = float(execution['entry_price'])
                            pct = ((current_price - entry) / entry) * 100 if current_price else 0
                            filled_at = execution['filled_at']
                            if filled_at.tzinfo is None:
                                filled_at = filled_at.replace(tzinfo=timezone.utc)
                            time_remaining = (filled_at + timedelta(hours=TIME_EXIT_HOURS) - datetime.now(timezone.utc))
                            mins = max(0, time_remaining.total_seconds() / 60)

                            logger.info(f"{execution['target_asset']}: ${current_price:,.2f} ({pct:+.2f}%) | "
                                       f"Time exit in {mins:.0f}m")

                time.sleep(CHECK_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                self.running = False
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Rollback any failed transaction
                if self.db_conn:
                    try:
                        self.db_conn.rollback()
                    except:
                        pass
                time.sleep(CHECK_INTERVAL_SECONDS)

        if self.db_conn:
            self.db_conn.close()


if __name__ == '__main__':
    monitor = STierExitMonitor()
    monitor.run()
