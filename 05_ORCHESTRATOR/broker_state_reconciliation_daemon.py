#!/usr/bin/env python3
"""
BROKER STATE RECONCILIATION DAEMON
===================================
Directive: CEO-DIR-2026-DBV-003 / P0 ACTION
Classification: GOVERNANCE-CRITICAL / ANTI-HALLUCINATION

Purpose:
- Continuously sync database state with Alpaca broker state
- Detect divergence within 60 seconds
- ALERT if database claims something that Alpaca contradicts
- NEVER trust database alone - Alpaca = VIRKELIGHET (reality)

Authority: LINE (EC-005) via IoS-012
Author: STIG (EC-003_2026_PRODUCTION)

CRITICAL RULE:
    Alpaca API response = TRUTH
    Database status = internal tracking ONLY
    If they diverge → ALERT + STOP
"""

import os
import sys
import json
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import pathlib

# Load environment
# Path: 03_FUNCTIONS -> vision-ios -> .env
env_path = pathlib.Path(__file__).parent.parent / '.env'
from dotenv import load_dotenv
load_dotenv(env_path)

import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import OrderStatus, QueryOrderStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("WARNING: Alpaca SDK not installed. Run: pip install alpaca-py")

# Configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Use paper trading credentials (check multiple env var names for compatibility)
ALPACA_API_KEY = os.getenv('ALPACA_PAPER_API_KEY', os.getenv('ALPACA_API_KEY', ''))
ALPACA_SECRET_KEY = os.getenv('ALPACA_PAPER_SECRET_KEY',
                              os.getenv('ALPACA_SECRET_KEY',
                              os.getenv('ALPACA_SECRET', '')))

# Reconciliation settings
RECONCILIATION_INTERVAL_SECONDS = 60
DIVERGENCE_ALERT_THRESHOLD = 0  # Any divergence triggers alert
MAX_DIVERGENCE_BEFORE_HALT = 3  # Halt after 3 consecutive divergences


class BrokerStateReconciliationDaemon:
    """
    Continuous reconciliation between database and Alpaca broker.

    CRITICAL: This daemon treats Alpaca API as the ONLY source of truth.
    Database is merely a tracking system that MUST match Alpaca.
    """

    def __init__(self):
        self.consecutive_divergences = 0
        self.last_reconciliation = None
        self.alpaca_client = None
        self.db_conn = None

    def initialize(self) -> bool:
        """Initialize connections to Alpaca and database."""
        # Check Alpaca credentials
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            self._log_error(
                "FATAL: Alpaca credentials not configured",
                "Set ALPACA_PAPER_API_KEY and ALPACA_PAPER_SECRET_KEY in .env"
            )
            return False

        if not ALPACA_AVAILABLE:
            self._log_error("FATAL: Alpaca SDK not installed")
            return False

        try:
            self.alpaca_client = TradingClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY,
                paper=True
            )
            # Test connection
            account = self.alpaca_client.get_account()
            print(f"[INIT] Connected to Alpaca Paper: {account.status}")
        except Exception as e:
            self._log_error(f"FATAL: Cannot connect to Alpaca: {e}")
            return False

        try:
            self.db_conn = psycopg2.connect(**DB_CONFIG)
            print(f"[INIT] Connected to PostgreSQL")
        except Exception as e:
            self._log_error(f"FATAL: Cannot connect to database: {e}")
            return False

        return True

    def get_alpaca_state(self) -> Dict[str, Any]:
        """
        Get TRUTH from Alpaca API.
        This is the ONLY authoritative source.
        """
        try:
            # Get account info
            account = self.alpaca_client.get_account()

            # Get all positions
            positions = self.alpaca_client.get_all_positions()

            # Get open orders
            open_orders = self.alpaca_client.get_orders(
                filter=GetOrdersRequest(status=QueryOrderStatus.OPEN)
            )

            return {
                "source": "ALPACA_API",
                "is_truth": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "account": {
                    "status": str(account.status),
                    "cash": float(account.cash),
                    "portfolio_value": float(account.portfolio_value),
                    "buying_power": float(account.buying_power)
                },
                "positions": [
                    {
                        "symbol": p.symbol,
                        "qty": float(p.qty),
                        "side": str(p.side),
                        "avg_entry_price": float(p.avg_entry_price),
                        "current_price": float(p.current_price),
                        "unrealized_pl": float(p.unrealized_pl)
                    }
                    for p in positions
                ],
                "open_orders": [
                    {
                        "order_id": str(o.id),
                        "symbol": o.symbol,
                        "side": str(o.side),
                        "qty": str(o.qty),
                        "status": str(o.status),
                        "created_at": o.created_at.isoformat() if o.created_at else None
                    }
                    for o in open_orders
                ],
                "position_count": len(positions),
                "open_order_count": len(open_orders)
            }
        except Exception as e:
            return {"source": "ALPACA_API", "error": str(e), "is_truth": False}

    def get_database_state(self) -> Dict[str, Any]:
        """
        Get internal tracking state from database.
        This is NOT truth - just what we THINK the state is.
        """
        try:
            with self.db_conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get latest broker snapshot
                cur.execute("""
                    SELECT
                        snapshot_id,
                        positions,
                        portfolio_value,
                        cash,
                        captured_at
                    FROM fhq_execution.broker_state_snapshots
                    ORDER BY captured_at DESC
                    LIMIT 1
                """)
                snapshot = cur.fetchone()

                # Get paper orders status
                cur.execute("""
                    SELECT
                        order_id,
                        canonical_id as symbol,
                        side,
                        qty,
                        status,
                        alpaca_order_id
                    FROM fhq_execution.paper_orders
                    WHERE status NOT IN ('filled', 'cancelled', 'expired', 'rejected')
                    ORDER BY created_at DESC
                """)
                pending_orders = cur.fetchall()

                # Get IOS012B positions
                cur.execute("""
                    SELECT ticker, shares, direction, status
                    FROM fhq_alpha.ios012b_paper_positions
                    WHERE status = 'OPEN'
                """)
                ios012b_positions = cur.fetchall()

            return {
                "source": "DATABASE",
                "is_truth": False,  # CRITICAL: Database is NOT truth
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latest_snapshot": {
                    "snapshot_id": str(snapshot['snapshot_id']) if snapshot else None,
                    "positions": snapshot['positions'] if snapshot else [],
                    "portfolio_value": float(snapshot['portfolio_value']) if snapshot else 0,
                    "captured_at": snapshot['captured_at'].isoformat() if snapshot and snapshot['captured_at'] else None
                } if snapshot else None,
                "pending_orders": [dict(o) for o in pending_orders],
                "ios012b_positions": [dict(p) for p in ios012b_positions],
                "pending_order_count": len(pending_orders),
                "ios012b_position_count": len(ios012b_positions)
            }
        except Exception as e:
            return {"source": "DATABASE", "error": str(e), "is_truth": False}

    def reconcile(self) -> Dict[str, Any]:
        """
        Compare Alpaca state (TRUTH) with database state (tracking).
        Flag any divergence.
        """
        alpaca_state = self.get_alpaca_state()
        db_state = self.get_database_state()

        if "error" in alpaca_state:
            return {
                "status": "ERROR",
                "error": f"Cannot get Alpaca state: {alpaca_state['error']}",
                "action": "CANNOT_RECONCILE"
            }

        divergences = []

        # Check 1: Position count
        alpaca_positions = {p['symbol']: p for p in alpaca_state['positions']}

        # Check 2: Compare with database snapshot
        if db_state.get('latest_snapshot') and db_state['latest_snapshot'].get('positions'):
            db_positions = {p['symbol']: p for p in db_state['latest_snapshot']['positions']}

            # Find positions in Alpaca but not in DB snapshot
            for symbol in alpaca_positions:
                if symbol not in db_positions:
                    divergences.append({
                        "type": "POSITION_NOT_IN_DB",
                        "symbol": symbol,
                        "alpaca_qty": alpaca_positions[symbol]['qty'],
                        "db_qty": 0,
                        "severity": "HIGH"
                    })
                elif alpaca_positions[symbol]['qty'] != db_positions[symbol].get('qty', 0):
                    divergences.append({
                        "type": "POSITION_QTY_MISMATCH",
                        "symbol": symbol,
                        "alpaca_qty": alpaca_positions[symbol]['qty'],
                        "db_qty": db_positions[symbol].get('qty', 0),
                        "severity": "HIGH"
                    })

            # Find positions in DB but not in Alpaca
            for symbol in db_positions:
                if symbol not in alpaca_positions:
                    divergences.append({
                        "type": "PHANTOM_POSITION_IN_DB",
                        "symbol": symbol,
                        "alpaca_qty": 0,
                        "db_qty": db_positions[symbol].get('qty', 0),
                        "severity": "CRITICAL",
                        "meaning": "DB thinks position exists but Alpaca says NO"
                    })

        # Check 3: Orders claimed cancelled but still open at Alpaca
        alpaca_order_ids = {o['order_id'] for o in alpaca_state['open_orders']}
        for order in db_state.get('pending_orders', []):
            if order.get('status') == 'cancelled' and order.get('alpaca_order_id') in alpaca_order_ids:
                divergences.append({
                    "type": "ORDER_HALLUCINATION",
                    "order_id": str(order['order_id']),
                    "alpaca_order_id": order.get('alpaca_order_id'),
                    "db_status": order.get('status'),
                    "alpaca_status": "OPEN",
                    "severity": "CRITICAL",
                    "meaning": "DB claims order cancelled but Alpaca shows OPEN"
                })

        # Build result
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alpaca_state": alpaca_state,
            "db_state": db_state,
            "divergences": divergences,
            "divergence_count": len(divergences),
            "status": "DIVERGED" if divergences else "SYNCHRONIZED"
        }

        # Handle divergence
        if divergences:
            self.consecutive_divergences += 1
            result["consecutive_divergences"] = self.consecutive_divergences
            result["action"] = self._determine_action(divergences)
            self._log_divergence(result)
        else:
            self.consecutive_divergences = 0
            result["action"] = "NONE"

        self.last_reconciliation = result
        return result

    def _determine_action(self, divergences: List[Dict]) -> str:
        """Determine what action to take based on divergences."""
        critical_count = sum(1 for d in divergences if d.get('severity') == 'CRITICAL')

        if critical_count > 0:
            return "HALT_AND_ALERT"
        elif self.consecutive_divergences >= MAX_DIVERGENCE_BEFORE_HALT:
            return "HALT_AFTER_MAX_DIVERGENCES"
        else:
            return "ALERT_ONLY"

    def _log_divergence(self, result: Dict):
        """Log divergence to database for audit trail."""
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_execution.broker_reconciliation_events (
                        event_type,
                        divergence_count,
                        divergences,
                        action_taken,
                        alpaca_state_hash,
                        created_by
                    ) VALUES (
                        'RECONCILIATION_DIVERGENCE',
                        %s,
                        %s,
                        %s,
                        %s,
                        'broker_state_reconciliation_daemon'
                    )
                """, (
                    result['divergence_count'],
                    Json(result['divergences']),
                    result['action'],
                    hashlib.md5(json.dumps(result['alpaca_state'], default=str).encode()).hexdigest()
                ))
            self.db_conn.commit()
        except Exception as e:
            print(f"[ERROR] Failed to log divergence: {e}")

    def _log_error(self, message: str, detail: str = None):
        """Log error to console and optionally database."""
        print(f"[ERROR] {message}")
        if detail:
            print(f"        {detail}")

    def save_snapshot(self, alpaca_state: Dict):
        """Save current Alpaca state to broker_state_snapshots."""
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_execution.broker_state_snapshots (
                        broker,
                        broker_environment,
                        snapshot_type,
                        account_status,
                        buying_power,
                        cash,
                        portfolio_value,
                        positions,
                        open_orders,
                        captured_at,
                        created_by
                    ) VALUES (
                        'ALPACA',
                        'PAPER',
                        'RECONCILIATION_DAEMON',
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        NOW(),
                        'broker_state_reconciliation_daemon'
                    )
                """, (
                    alpaca_state['account']['status'],
                    alpaca_state['account']['buying_power'],
                    alpaca_state['account']['cash'],
                    alpaca_state['account']['portfolio_value'],
                    Json(alpaca_state['positions']),
                    Json(alpaca_state['open_orders'])
                ))
            self.db_conn.commit()
            print(f"[SNAPSHOT] Saved Alpaca state: {alpaca_state['position_count']} positions, {alpaca_state['open_order_count']} orders")
        except Exception as e:
            print(f"[ERROR] Failed to save snapshot: {e}")

    def run_once(self) -> Dict[str, Any]:
        """Run one reconciliation cycle."""
        print(f"\n{'='*60}")
        print(f"RECONCILIATION CYCLE: {datetime.now(timezone.utc).isoformat()}")
        print(f"{'='*60}")

        result = self.reconcile()

        if result['status'] == 'SYNCHRONIZED':
            print(f"[OK] Synchronized: {result['alpaca_state']['position_count']} positions")
            # Save snapshot on successful sync
            self.save_snapshot(result['alpaca_state'])
        else:
            print(f"[DIVERGENCE] Found {result['divergence_count']} divergences!")
            for d in result['divergences']:
                print(f"  - {d['type']}: {d.get('symbol', d.get('order_id', 'N/A'))} "
                      f"(Alpaca: {d.get('alpaca_qty', d.get('alpaca_status', 'N/A'))}, "
                      f"DB: {d.get('db_qty', d.get('db_status', 'N/A'))})")
            print(f"[ACTION] {result['action']}")

            if result['action'] in ('HALT_AND_ALERT', 'HALT_AFTER_MAX_DIVERGENCES'):
                print("\n" + "!"*60)
                print("CRITICAL: HALTING - Manual intervention required!")
                print("!"*60)

        return result

    def run_continuous(self):
        """Run continuous reconciliation loop."""
        print("\n" + "="*60)
        print("BROKER STATE RECONCILIATION DAEMON")
        print("="*60)
        print(f"Interval: {RECONCILIATION_INTERVAL_SECONDS}s")
        print(f"Divergence threshold: {DIVERGENCE_ALERT_THRESHOLD}")
        print(f"Max divergences before halt: {MAX_DIVERGENCE_BEFORE_HALT}")
        print("="*60)

        if not self.initialize():
            print("FATAL: Initialization failed. Exiting.")
            sys.exit(1)

        while True:
            try:
                result = self.run_once()

                if result.get('action') in ('HALT_AND_ALERT', 'HALT_AFTER_MAX_DIVERGENCES'):
                    print("\nDaemon halted due to critical divergence. Manual review required.")
                    break

                time.sleep(RECONCILIATION_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                print("\nDaemon stopped by user.")
                break
            except Exception as e:
                print(f"[ERROR] Unexpected error: {e}")
                time.sleep(RECONCILIATION_INTERVAL_SECONDS)


def main():
    """Entry point for the daemon."""
    daemon = BrokerStateReconciliationDaemon()

    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Run once for testing
        if daemon.initialize():
            daemon.run_once()
    else:
        # Run continuously
        daemon.run_continuous()


if __name__ == "__main__":
    main()
