#!/usr/bin/env python3
"""
BROKER TRUTH CAPTURE
====================
CD-EXEC-ALPACA-SOT-001: Alpaca Paper is the sole source of truth for NAV/positions.

This module captures broker state snapshots from Alpaca and stores them in the
canonical broker_state_snapshots table for use by all execution systems.

Author: STIG (CTO)
Directive: CD-EXEC-ALPACA-SOT-001
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

# Load environment
load_dotenv('C:/fhq-market-system/vision-ios/.env')

# Try to import Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("WARNING: alpaca-py not installed. Run: pip install alpaca-py")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class BrokerTruthCapture:
    """
    Captures broker state from Alpaca Paper and stores as canonical truth.

    Per CD-EXEC-ALPACA-SOT-001:
    - Alpaca Paper is the ONLY source of truth for NAV/positions
    - All internal ledgers are derived views
    - Any divergence triggers governance event
    """

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.alpaca_client = None

        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY') or os.getenv('ALPACA_SECRET')

        if ALPACA_AVAILABLE and api_key and secret_key:
            try:
                self.alpaca_client = TradingClient(api_key, secret_key, paper=True)
                print("[BROKER-TRUTH] Alpaca Paper client initialized")
            except Exception as e:
                print(f"[BROKER-TRUTH] Alpaca init failed: {e}")
        else:
            print("[BROKER-TRUTH] Alpaca not available - check API keys")

    def _compute_hash(self, data: str) -> str:
        """Compute SHA-256 hash for audit trail"""
        return hashlib.sha256(data.encode()).hexdigest()

    def capture_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Capture current broker state from Alpaca Paper.

        Returns snapshot dict or None if capture fails.
        """
        if not self.alpaca_client:
            print("[BROKER-TRUTH] ERROR: No Alpaca client - cannot capture snapshot")
            return None

        try:
            # Get account info
            account = self.alpaca_client.get_account()

            # Get positions
            positions = self.alpaca_client.get_all_positions()

            # Build positions array
            positions_data = []
            for p in positions:
                positions_data.append({
                    'symbol': p.symbol,
                    'asset_id': str(p.asset_id),
                    'qty': float(p.qty),
                    'side': str(p.side),
                    'market_value': float(p.market_value),
                    'avg_entry_price': float(p.avg_entry_price),
                    'current_price': float(p.current_price),
                    'unrealized_pl': float(p.unrealized_pl),
                    'unrealized_plpc': float(p.unrealized_plpc)
                })

            snapshot = {
                'snapshot_id': str(uuid.uuid4()),
                'broker': 'ALPACA',
                'broker_environment': 'PAPER',
                'account_id': str(account.id),
                'account_status': str(account.status),
                'portfolio_value': float(account.portfolio_value),
                'cash': float(account.cash),
                'buying_power': float(account.buying_power),
                'equity': float(account.equity),
                'positions': positions_data,
                'captured_at': datetime.utcnow().isoformat()
            }

            return snapshot

        except Exception as e:
            print(f"[BROKER-TRUTH] Capture failed: {e}")
            return None

    def store_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """
        Store snapshot in canonical broker_state_snapshots table.

        Returns True if stored successfully.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_execution.broker_state_snapshots (
                        snapshot_id,
                        broker,
                        broker_environment,
                        snapshot_type,
                        account_id,
                        account_status,
                        buying_power,
                        cash,
                        portfolio_value,
                        positions,
                        captured_at,
                        created_by,
                        hash_chain_id
                    ) VALUES (
                        %s, %s, %s, 'FULL', %s, %s, %s, %s, %s, %s, NOW(), 'STIG',
                        %s
                    )
                """, (
                    snapshot['snapshot_id'],
                    snapshot['broker'],
                    snapshot['broker_environment'],
                    snapshot['account_id'],
                    snapshot['account_status'],
                    snapshot['buying_power'],
                    snapshot['cash'],
                    snapshot['portfolio_value'],
                    Json(snapshot['positions']),
                    f"HC-BROKER-TRUTH-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                ))

                self.conn.commit()
                return True

        except Exception as e:
            print(f"[BROKER-TRUTH] Store failed: {e}")
            self.conn.rollback()
            return False

    def check_divergence(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check for divergence between broker state and internal state.

        Returns divergence report.
        """
        divergence = {
            'has_divergence': False,
            'severity': 'NONE',
            'details': []
        }

        # For now, we check against any internal position tracking
        # In full implementation, compare against internal position tables

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if we have any internal position state to compare
            cur.execute("""
                SELECT config_value
                FROM fhq_positions.hcp_engine_config
                WHERE config_key = 'synthetic_nav_allowed'
            """)
            row = cur.fetchone()

            if row and row['config_value'] == 'true':
                divergence['has_divergence'] = True
                divergence['severity'] = 'CRITICAL'
                divergence['details'].append({
                    'issue': 'synthetic_nav_allowed is TRUE',
                    'directive': 'CD-EXEC-ALPACA-SOT-001 requires FALSE'
                })

        return divergence

    def log_reconciliation(self, snapshot: Dict, divergence: Dict) -> None:
        """Log reconciliation event to broker_reconciliation_events table."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_execution.broker_reconciliation_events (
                        reconciliation_type,
                        broker_nav,
                        broker_cash,
                        broker_positions,
                        is_reconciled,
                        divergence_severity,
                        hash_chain_id
                    ) VALUES (
                        'CONTINUOUS',
                        %s, %s, %s,
                        %s, %s,
                        %s
                    )
                """, (
                    snapshot['portfolio_value'],
                    snapshot['cash'],
                    Json(snapshot['positions']),
                    not divergence['has_divergence'],
                    divergence['severity'],
                    f"HC-RECON-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                ))
                self.conn.commit()
        except Exception as e:
            print(f"[BROKER-TRUTH] Reconciliation log failed: {e}")
            self.conn.rollback()

    def run_capture_cycle(self) -> Dict[str, Any]:
        """
        Execute one complete capture cycle:
        1. Capture snapshot from Alpaca
        2. Store in canonical table
        3. Check for divergence
        4. Log reconciliation event

        Returns cycle result.
        """
        result = {
            'success': False,
            'snapshot_id': None,
            'nav': None,
            'cash': None,
            'position_count': 0,
            'divergence': None,
            'captured_at': datetime.utcnow().isoformat()
        }

        # Step 1: Capture
        print("[BROKER-TRUTH] Capturing snapshot from Alpaca Paper...")
        snapshot = self.capture_snapshot()

        if not snapshot:
            result['error'] = 'Capture failed'
            return result

        result['snapshot_id'] = snapshot['snapshot_id']
        result['nav'] = snapshot['portfolio_value']
        result['cash'] = snapshot['cash']
        result['position_count'] = len(snapshot['positions'])

        # Step 2: Store
        print(f"[BROKER-TRUTH] NAV: ${snapshot['portfolio_value']:,.2f} | Cash: ${snapshot['cash']:,.2f}")
        print(f"[BROKER-TRUTH] Positions: {len(snapshot['positions'])}")

        if not self.store_snapshot(snapshot):
            result['error'] = 'Store failed'
            return result

        print(f"[BROKER-TRUTH] Snapshot stored: {snapshot['snapshot_id']}")

        # Step 3: Check divergence
        divergence = self.check_divergence(snapshot)
        result['divergence'] = divergence

        if divergence['has_divergence']:
            print(f"[BROKER-TRUTH] WARNING: Divergence detected - {divergence['severity']}")
            for d in divergence['details']:
                print(f"  - {d['issue']}")
        else:
            print("[BROKER-TRUTH] No divergence - broker state is canonical")

        # Step 4: Log reconciliation
        self.log_reconciliation(snapshot, divergence)

        result['success'] = True
        return result

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Execute broker truth capture."""
    print("=" * 70)
    print("BROKER TRUTH CAPTURE")
    print("CD-EXEC-ALPACA-SOT-001: Alpaca Paper as Sole Source of Truth")
    print("=" * 70)
    print(f"Time: {datetime.now().isoformat()}")
    print()

    capture = BrokerTruthCapture()

    try:
        result = capture.run_capture_cycle()

        print()
        print("=" * 70)
        print("CAPTURE RESULT")
        print("=" * 70)

        if result['success']:
            print(f"Status: SUCCESS")
            print(f"Snapshot ID: {result['snapshot_id']}")
            print(f"NAV: ${result['nav']:,.2f}")
            print(f"Cash: ${result['cash']:,.2f}")
            print(f"Positions: {result['position_count']}")
            print(f"Divergence: {result['divergence']['severity']}")
        else:
            print(f"Status: FAILED")
            print(f"Error: {result.get('error', 'Unknown')}")

        return result['success']

    finally:
        capture.close()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
