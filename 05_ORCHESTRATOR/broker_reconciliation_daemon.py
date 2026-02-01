#!/usr/bin/env python3
"""
Broker Reconciliation Daemon
============================
CEO Directive 2025-12-21: Alpaca Broker is sole execution source of truth.

This daemon:
1. Periodically fetches Alpaca broker state
2. Compares with FHQ internal records
3. Flags divergences
4. Updates broker_state_snapshots
5. Alerts on mismatches

Usage:
    python broker_reconciliation_daemon.py [--once] [--interval SECONDS]
"""

import os
import sys
import json
import hashlib
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

# Alpaca imports
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class BrokerReconciliationDaemon:
    """
    Reconciles FHQ internal state with Alpaca broker state.
    Alpaca is the source of truth per CEO directive.
    """

    def __init__(self):
        # Database connection
        self.db_conn = psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'),
            port=os.getenv('PGPORT', '54322'),
            database=os.getenv('PGDATABASE', 'postgres'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', 'postgres')
        )

        # Alpaca client
        self.alpaca = TradingClient(
            api_key=os.getenv('ALPACA_API_KEY'),
            secret_key=os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY')),
            paper=True
        )

        logger.info("Broker Reconciliation Daemon initialized")

    def fetch_alpaca_state(self) -> Dict:
        """Fetch current state from Alpaca broker."""
        account = self.alpaca.get_account()
        positions = self.alpaca.get_all_positions()
        orders = self.alpaca.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))

        state = {
            'account': {
                'portfolio_value': float(account.portfolio_value),
                'cash': float(account.cash),
                'equity': float(account.equity),
                'buying_power': float(account.buying_power),
                'status': str(account.status)
            },
            'positions': [
                {
                    'symbol': p.symbol,
                    'qty': float(p.qty),
                    'side': str(p.side),
                    'market_value': float(p.market_value),
                    'avg_entry_price': float(p.avg_entry_price),
                    'unrealized_pl': float(p.unrealized_pl),
                    'asset_id': str(p.asset_id)
                }
                for p in positions
            ],
            'orders': [
                {
                    'order_id': str(o.id),
                    'symbol': o.symbol,
                    'side': str(o.side),
                    'qty': str(o.qty),
                    'status': str(o.status),
                    'type': str(o.type),
                    'created_at': str(o.created_at)
                }
                for o in orders
            ],
            'fetched_at': datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"Fetched Alpaca state: {len(state['positions'])} positions, {len(state['orders'])} orders")
        return state

    def fetch_fhq_state(self) -> Dict:
        """Fetch current state from FHQ internal records."""
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get open paper trades
            cur.execute("""
                SELECT
                    trade_id,
                    asset_symbol,
                    direction,
                    quantity,
                    ecu_size_usd,
                    entry_price,
                    broker_order_id,
                    trade_status
                FROM fhq_execution.g2c_paper_trades
                WHERE trade_status = 'OPEN'
            """)
            trades = cur.fetchall()

        state = {
            'open_trades': [dict(t) for t in trades],
            'fetched_at': datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"Fetched FHQ state: {len(state['open_trades'])} open trades")
        return state

    def detect_divergence(self, alpaca_state: Dict, fhq_state: Dict) -> Tuple[bool, Dict]:
        """
        Compare Alpaca and FHQ states.
        Returns (divergence_detected, details).
        """
        divergences = []

        # Get Alpaca position symbols
        alpaca_symbols = {p['symbol'] for p in alpaca_state['positions']}

        # Get FHQ open trade symbols
        fhq_symbols = {t['asset_symbol'] for t in fhq_state['open_trades']}

        # Check for FHQ trades without Alpaca positions
        orphan_fhq = fhq_symbols - alpaca_symbols
        if orphan_fhq:
            divergences.append({
                'type': 'FHQ_WITHOUT_BROKER',
                'symbols': list(orphan_fhq),
                'severity': 'HIGH',
                'message': f"FHQ has open trades for {orphan_fhq} but no Alpaca position exists"
            })

        # Check for FHQ trades without broker_order_id
        trades_without_broker_id = [
            t for t in fhq_state['open_trades']
            if t['trade_status'] == 'OPEN' and not t.get('broker_order_id')
        ]
        if trades_without_broker_id:
            divergences.append({
                'type': 'MISSING_BROKER_ORDER_ID',
                'count': len(trades_without_broker_id),
                'severity': 'MEDIUM',
                'message': f"{len(trades_without_broker_id)} OPEN trades without broker_order_id"
            })

        # Check for Alpaca positions without FHQ records (informational)
        orphan_alpaca = alpaca_symbols - fhq_symbols
        if orphan_alpaca:
            divergences.append({
                'type': 'BROKER_WITHOUT_FHQ',
                'symbols': list(orphan_alpaca),
                'severity': 'INFO',
                'message': f"Alpaca has positions for {orphan_alpaca} not tracked in FHQ g2c_paper_trades"
            })

        has_divergence = any(d['severity'] in ('HIGH', 'MEDIUM') for d in divergences)

        return has_divergence, {
            'divergences': divergences,
            'alpaca_position_count': len(alpaca_state['positions']),
            'fhq_open_trade_count': len(fhq_state['open_trades']),
            'checked_at': datetime.now(timezone.utc).isoformat()
        }

    def save_snapshot(self, alpaca_state: Dict, fhq_state: Dict,
                      divergence_detected: bool, divergence_details: Dict) -> str:
        """Save reconciliation snapshot to database."""
        snapshot_id = None

        with self.db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_execution.broker_state_snapshots (
                    broker, broker_environment, snapshot_type,
                    account_status, buying_power, cash, portfolio_value,
                    positions, open_orders, fhq_internal_state,
                    divergence_detected, divergence_details,
                    captured_at, created_by, hash_chain_id
                ) VALUES (
                    'ALPACA', 'PAPER', 'FULL',
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    NOW(), 'RECONCILIATION_DAEMON', %s
                )
                RETURNING snapshot_id
            """, (
                alpaca_state['account']['status'],
                alpaca_state['account']['buying_power'],
                alpaca_state['account']['cash'],
                alpaca_state['account']['portfolio_value'],
                Json(alpaca_state['positions']),
                Json(alpaca_state['orders']),
                Json(fhq_state),
                divergence_detected,
                Json(divergence_details),
                f"HC-RECON-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            ))
            snapshot_id = cur.fetchone()[0]
            self.db_conn.commit()

        logger.info(f"Saved snapshot: {snapshot_id}")
        return str(snapshot_id)

    def raise_alert(self, divergence_details: Dict):
        """Raise divergence alert in governance log."""
        with self.db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type, action_target, decision,
                    decision_rationale, initiated_by, initiated_at
                ) VALUES (
                    'DIVERGENCE_ALERT', 'BROKER_RECONCILIATION', 'ALERT',
                    %s, 'RECONCILIATION_DAEMON', NOW()
                )
            """, (
                json.dumps(divergence_details),
            ))
            self.db_conn.commit()

        logger.warning(f"DIVERGENCE ALERT raised: {divergence_details}")

    def run_once(self) -> Dict:
        """Run a single reconciliation cycle."""
        logger.info("Starting reconciliation cycle...")

        # Fetch states
        alpaca_state = self.fetch_alpaca_state()
        fhq_state = self.fetch_fhq_state()

        # Detect divergence
        divergence_detected, divergence_details = self.detect_divergence(
            alpaca_state, fhq_state
        )

        # Save snapshot
        snapshot_id = self.save_snapshot(
            alpaca_state, fhq_state,
            divergence_detected, divergence_details
        )

        # Raise alert if divergence detected
        if divergence_detected:
            self.raise_alert(divergence_details)

        result = {
            'snapshot_id': snapshot_id,
            'divergence_detected': divergence_detected,
            'divergence_details': divergence_details,
            'alpaca_positions': len(alpaca_state['positions']),
            'fhq_open_trades': len(fhq_state['open_trades'])
        }

        logger.info(f"Reconciliation complete: divergence={divergence_detected}")
        return result

    def run_daemon(self, interval_seconds: int = 300):
        """Run continuous reconciliation daemon."""
        import time

        logger.info(f"Starting daemon with {interval_seconds}s interval")

        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")

            time.sleep(interval_seconds)

    def close(self):
        """Clean up resources."""
        self.db_conn.close()
        logger.info("Daemon stopped")


def main():
    parser = argparse.ArgumentParser(description='Broker Reconciliation Daemon')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=300,
                        help='Interval in seconds (default: 300)')
    args = parser.parse_args()

    daemon = BrokerReconciliationDaemon()

    try:
        if args.once:
            result = daemon.run_once()
            print(json.dumps(result, indent=2, default=str))
        else:
            daemon.run_daemon(args.interval)
    finally:
        daemon.close()


if __name__ == '__main__':
    main()
