#!/usr/bin/env python3
"""
EXIT DETECTION DAEMON - Ground Truth Outcome Capture
=====================================================
CEO Directive: CEO-G5-TRACE-2025-12-21 (Phase 2)
Classification: OUTCOME_CAPTURE
Mode: PAPER

Purpose:
    Detect closed positions and capture canonical outcomes.
    No learning. No thresholds. Just ground truth.

Flow:
    1. Query Alpaca for closed orders (broker truth)
    2. Match to open g5_paper_trades
    3. Call capture_trade_outcome() for each exit
    4. Log to canonical_outcomes

Runs independently of signal_executor_daemon.
Can run while execution is frozen.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus, OrderSide
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [EXIT-DETECT] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('EXIT_DETECTION')

# Configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))


class ExitDetectionDaemon:
    """Detect exits and capture canonical outcomes."""

    def __init__(self):
        self.conn = None
        self.trading_client = None

    def connect(self) -> bool:
        """Connect to database and Alpaca."""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Database connected")

            if ALPACA_AVAILABLE and ALPACA_API_KEY:
                self.trading_client = TradingClient(
                    api_key=ALPACA_API_KEY,
                    secret_key=ALPACA_SECRET,
                    paper=True
                )
                account = self.trading_client.get_account()
                logger.info(f"Alpaca connected - Portfolio: ${float(account.portfolio_value):,.2f}")
            else:
                logger.warning("Alpaca not available")

            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def close(self):
        """Close connections."""
        if self.conn:
            self.conn.close()

    def get_open_paper_trades(self) -> List[Dict]:
        """Get all open paper trades that need exit monitoring."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    trade_id,
                    needle_id,
                    symbol,
                    direction,
                    entry_price,
                    position_size,
                    entry_timestamp,
                    entry_regime,
                    entry_context
                FROM fhq_canonical.g5_paper_trades
                WHERE exit_timestamp IS NULL
                  AND needle_id IS NOT NULL
                ORDER BY entry_timestamp ASC
            """)
            return cur.fetchall()

    def get_alpaca_positions(self) -> Dict[str, Dict]:
        """Get current Alpaca positions."""
        if not self.trading_client:
            return {}

        try:
            positions = self.trading_client.get_all_positions()
            return {
                p.symbol: {
                    'qty': float(p.qty),
                    'market_value': float(p.market_value),
                    'current_price': float(p.current_price),
                    'unrealized_pnl': float(p.unrealized_pl),
                    'unrealized_pnl_pct': float(p.unrealized_plpc) * 100
                }
                for p in positions
            }
        except Exception as e:
            logger.error(f"Failed to get Alpaca positions: {e}")
            return {}

    def get_recent_closed_orders(self, since_hours: int = 24) -> List[Dict]:
        """Get recently closed/filled orders from Alpaca."""
        if not self.trading_client:
            return []

        try:
            # Get filled orders from last N hours
            orders = self.trading_client.get_orders(
                GetOrdersRequest(
                    status=QueryOrderStatus.CLOSED,
                    after=datetime.now(timezone.utc) - timedelta(hours=since_hours)
                )
            )

            return [
                {
                    'order_id': str(o.id),
                    'symbol': o.symbol,
                    'side': o.side.name,
                    'qty': float(o.filled_qty) if o.filled_qty else 0,
                    'filled_price': float(o.filled_avg_price) if o.filled_avg_price else 0,
                    'status': o.status.name if o.status else 'UNKNOWN',
                    'filled_at': o.filled_at
                }
                for o in orders
                if o.status and o.status.name == 'FILLED'
            ]
        except Exception as e:
            logger.error(f"Failed to get closed orders: {e}")
            return []

    def detect_exits(self) -> List[Dict]:
        """
        Detect exits by comparing open trades to Alpaca positions.

        A trade is exited if:
        1. Symbol no longer in Alpaca positions, OR
        2. We have a SELL order that closed the position
        """
        exits_detected = []

        # Get our open trades
        open_trades = self.get_open_paper_trades()
        if not open_trades:
            logger.debug("No open paper trades to monitor")
            return []

        # Get current Alpaca positions
        alpaca_positions = self.get_alpaca_positions()

        # Get recent closed orders
        closed_orders = self.get_recent_closed_orders()
        closed_sells = {
            o['symbol']: o
            for o in closed_orders
            if o['side'] == 'SELL'
        }

        for trade in open_trades:
            symbol = trade['symbol']

            # Check if position no longer exists
            if symbol not in alpaca_positions:
                # Position closed - check for sell order
                sell_order = closed_sells.get(symbol)

                if sell_order:
                    exit_price = sell_order['filled_price']
                    exit_reason = 'BROKER_CLOSED'  # Could be stop-loss, take-profit, or manual
                else:
                    # Position disappeared without our sell order (external close)
                    exit_price = float(trade['entry_price'])  # Fallback - not ideal
                    exit_reason = 'POSITION_DISAPPEARED'

                exits_detected.append({
                    'trade_id': trade['trade_id'],
                    'needle_id': trade['needle_id'],
                    'symbol': symbol,
                    'direction': trade['direction'],
                    'entry_price': float(trade['entry_price']),
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'position_size': float(trade['position_size']) if trade['position_size'] else 0
                })

                logger.info(f"EXIT DETECTED: {symbol} @ ${exit_price:.2f} ({exit_reason})")

        return exits_detected

    def capture_outcome(self, exit_data: Dict) -> Optional[str]:
        """
        Capture canonical outcome for an exit.
        Calls the SQL function capture_trade_outcome().
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT fhq_canonical.capture_trade_outcome(
                        p_trade_id := %s,
                        p_exit_price := %s,
                        p_exit_reason := %s,
                        p_exit_regime := NULL,
                        p_exit_defcon := NULL,
                        p_max_favorable := NULL,
                        p_max_adverse := NULL
                    )
                """, (
                    exit_data['trade_id'],
                    exit_data['exit_price'],
                    exit_data['exit_reason']
                ))

                outcome_id = cur.fetchone()[0]
                self.conn.commit()

                logger.info(f"OUTCOME CAPTURED: {outcome_id} for trade {exit_data['trade_id']}")
                return str(outcome_id)

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to capture outcome: {e}")
            return None

    def run_detection_cycle(self) -> Dict:
        """Run one detection cycle."""
        result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'open_trades_monitored': 0,
            'exits_detected': 0,
            'outcomes_captured': 0,
            'exits': []
        }

        # Get open trades count
        open_trades = self.get_open_paper_trades()
        result['open_trades_monitored'] = len(open_trades)

        if not open_trades:
            return result

        # Detect exits
        exits = self.detect_exits()
        result['exits_detected'] = len(exits)

        # Capture outcomes
        for exit_data in exits:
            outcome_id = self.capture_outcome(exit_data)
            if outcome_id:
                result['outcomes_captured'] += 1
                result['exits'].append({
                    'symbol': exit_data['symbol'],
                    'exit_reason': exit_data['exit_reason'],
                    'exit_price': exit_data['exit_price'],
                    'outcome_id': outcome_id
                })

        return result

    def check_current_status(self) -> Dict:
        """Check current status without making changes."""
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'open_paper_trades': 0,
            'canonical_outcomes': 0,
            'alpaca_positions': 0,
            'trades': []
        }

        # Get open trades
        open_trades = self.get_open_paper_trades()
        status['open_paper_trades'] = len(open_trades)

        for trade in open_trades:
            status['trades'].append({
                'trade_id': str(trade['trade_id'])[:8],
                'symbol': trade['symbol'],
                'direction': trade['direction'],
                'entry_price': float(trade['entry_price']),
                'entry_time': trade['entry_timestamp'].isoformat() if trade['entry_timestamp'] else None
            })

        # Get outcome count
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fhq_canonical.canonical_outcomes")
            status['canonical_outcomes'] = cur.fetchone()[0]

        # Get Alpaca positions
        alpaca_positions = self.get_alpaca_positions()
        status['alpaca_positions'] = len(alpaca_positions)
        status['alpaca_symbols'] = list(alpaca_positions.keys())

        return status


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Exit Detection Daemon - Ground Truth Capture')
    parser.add_argument('--status', action='store_true', help='Show current status')
    parser.add_argument('--detect', action='store_true', help='Run detection cycle')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=60, help='Cycle interval in seconds')
    args = parser.parse_args()

    daemon = ExitDetectionDaemon()

    if not daemon.connect():
        logger.error("Failed to connect")
        sys.exit(1)

    try:
        if args.status:
            status = daemon.check_current_status()
            print("\n" + "=" * 60)
            print("EXIT DETECTION STATUS")
            print("=" * 60)
            print(f"Open Paper Trades: {status['open_paper_trades']}")
            print(f"Canonical Outcomes: {status['canonical_outcomes']}")
            print(f"Alpaca Positions: {status['alpaca_positions']}")
            if status['alpaca_symbols']:
                print(f"  Symbols: {', '.join(status['alpaca_symbols'])}")
            print("-" * 60)
            for trade in status['trades']:
                print(f"  {trade['symbol']}: {trade['direction']} @ ${trade['entry_price']:.2f}")
            print("=" * 60)

        elif args.detect:
            result = daemon.run_detection_cycle()
            print("\n" + "=" * 60)
            print("DETECTION CYCLE RESULT")
            print("=" * 60)
            print(f"Open Trades Monitored: {result['open_trades_monitored']}")
            print(f"Exits Detected: {result['exits_detected']}")
            print(f"Outcomes Captured: {result['outcomes_captured']}")
            for exit in result['exits']:
                print(f"  {exit['symbol']}: {exit['exit_reason']} @ ${exit['exit_price']:.2f}")
            print("=" * 60)

        elif args.continuous:
            import time
            logger.info("=" * 60)
            logger.info("EXIT DETECTION DAEMON - Starting")
            logger.info(f"CEO Directive: CEO-G5-TRACE-2025-12-21")
            logger.info(f"Mode: GROUND_TRUTH_CAPTURE")
            logger.info(f"Interval: {args.interval}s")
            logger.info("=" * 60)

            while True:
                result = daemon.run_detection_cycle()
                if result['exits_detected'] > 0:
                    logger.info(f"Cycle: {result['exits_detected']} exits, {result['outcomes_captured']} captured")
                time.sleep(args.interval)

        else:
            # Default: show status
            status = daemon.check_current_status()
            print(f"Open trades: {status['open_paper_trades']}, Outcomes: {status['canonical_outcomes']}")
            print("Use --detect to run detection, --continuous for daemon mode")

    finally:
        daemon.close()


if __name__ == "__main__":
    main()
