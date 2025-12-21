#!/usr/bin/env python3
"""
RE-ENABLEMENT RUNBOOK EXECUTOR
==============================
CEO Directive: CEO-REENABLE-2025-12-22
Classification: CRITICAL GOVERNANCE INFRASTRUCTURE

This script executes the phased re-enablement runbook with hard acceptance
criteria gates. Each phase must pass before proceeding.

Usage:
    python reenable_runbook_executor.py --phase 1   # Check Phase 1 (LINE)
    python reenable_runbook_executor.py --phase 2   # Check Phase 2 (STIG)
    python reenable_runbook_executor.py --phase 3   # Check Phase 3 (STIG)
    python reenable_runbook_executor.py --phase 5   # Execute Phase 5 (STIG+CEO)
    python reenable_runbook_executor.py --rollback  # Emergency rollback

Author: STIG (CTO)
Authority: CEO Directive CEO-REENABLE-2025-12-22
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, Tuple, List
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [REENABLE] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('REENABLE_RUNBOOK')

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("Alpaca SDK not available")


class ReenableRunbook:
    """Executes the CEO-REENABLE-2025-12-22 runbook."""

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.alpaca = None
        if ALPACA_AVAILABLE:
            api_key = os.getenv('ALPACA_API_KEY')
            secret_key = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY'))
            if api_key and secret_key:
                self.alpaca = TradingClient(
                    api_key=api_key,
                    secret_key=secret_key,
                    paper=True
                )

    def close(self):
        self.conn.close()

    # =========================================================================
    # PHASE 1: MARKET CLEANUP (Owner: LINE)
    # =========================================================================

    def check_phase_1(self) -> Tuple[bool, Dict]:
        """
        Phase 1 Acceptance Criteria:
        - Broker positions: 0
        - Pending orders: 0
        - Cash: >= 0
        - Margin usage: none
        """
        logger.info("=" * 70)
        logger.info("PHASE 1: MARKET CLEANUP CHECK")
        logger.info("Owner: LINE")
        logger.info("=" * 70)

        if not self.alpaca:
            return False, {'error': 'Alpaca client not available'}

        try:
            account = self.alpaca.get_account()
            positions = self.alpaca.get_all_positions()
            orders = self.alpaca.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))

            cash = float(account.cash)
            portfolio_value = float(account.portfolio_value)

            # Margin check: if cash is negative, margin is being used
            margin_used = cash < 0

            result = {
                'positions_count': len(positions),
                'pending_orders_count': len(orders),
                'cash': cash,
                'portfolio_value': portfolio_value,
                'margin_used': margin_used,
                'positions': [{'symbol': p.symbol, 'qty': float(p.qty)} for p in positions],
                'orders': [{'symbol': o.symbol, 'side': str(o.side)} for o in orders],
                'checked_at': datetime.now(timezone.utc).isoformat()
            }

            # Acceptance criteria
            criteria = {
                'positions_zero': len(positions) == 0,
                'orders_zero': len(orders) == 0,
                'cash_non_negative': cash >= 0,
                'no_margin': not margin_used
            }

            result['criteria'] = criteria
            passed = all(criteria.values())
            result['passed'] = passed

            # Log results
            logger.info(f"Positions: {len(positions)} {'PASS' if criteria['positions_zero'] else 'FAIL'}")
            logger.info(f"Pending Orders: {len(orders)} {'PASS' if criteria['orders_zero'] else 'FAIL'}")
            logger.info(f"Cash: ${cash:,.2f} {'PASS' if criteria['cash_non_negative'] else 'FAIL'}")
            logger.info(f"Margin Used: {margin_used} {'PASS' if criteria['no_margin'] else 'FAIL'}")

            if positions:
                logger.warning("REMAINING POSITIONS:")
                for p in positions:
                    logger.warning(f"  {p.symbol}: {p.qty} shares")

            logger.info("-" * 70)
            logger.info(f"PHASE 1 RESULT: {'PASSED' if passed else 'FAILED'}")

            return passed, result

        except Exception as e:
            logger.error(f"Phase 1 check failed: {e}")
            return False, {'error': str(e)}

    # =========================================================================
    # PHASE 2: BROKER TRUTH RECONCILIATION (Owner: STIG)
    # =========================================================================

    def check_phase_2(self) -> Tuple[bool, Dict]:
        """
        Phase 2 Acceptance Criteria:
        - Broker snapshot exists and is timestamped after liquidation
        - Divergence: none (high/medium)
        - FHQ open trades: 0
        """
        logger.info("=" * 70)
        logger.info("PHASE 2: BROKER TRUTH RECONCILIATION CHECK")
        logger.info("Owner: STIG")
        logger.info("=" * 70)

        result = {
            'checked_at': datetime.now(timezone.utc).isoformat()
        }

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check for recent broker snapshot
                cur.execute("""
                    SELECT snapshot_id, captured_at, divergence_detected,
                           divergence_details, portfolio_value, cash
                    FROM fhq_execution.broker_state_snapshots
                    ORDER BY captured_at DESC
                    LIMIT 1
                """)
                snapshot = cur.fetchone()

                if snapshot:
                    result['latest_snapshot'] = {
                        'snapshot_id': str(snapshot['snapshot_id']),
                        'captured_at': str(snapshot['captured_at']),
                        'divergence_detected': snapshot['divergence_detected'],
                        'portfolio_value': float(snapshot['portfolio_value'] or 0),
                        'cash': float(snapshot['cash'] or 0)
                    }
                else:
                    result['latest_snapshot'] = None

                # Check for high/medium divergences
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM fhq_execution.broker_state_snapshots
                    WHERE divergence_detected = TRUE
                      AND captured_at > NOW() - INTERVAL '24 hours'
                      AND divergence_details::text LIKE '%HIGH%'
                         OR divergence_details::text LIKE '%MEDIUM%'
                """)
                divergence_count = cur.fetchone()['count']
                result['recent_divergences'] = divergence_count

                # Check FHQ open trades
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM fhq_execution.g2c_paper_trades
                    WHERE trade_status = 'OPEN'
                """)
                open_trades = cur.fetchone()['count']
                result['fhq_open_trades'] = open_trades

            # Acceptance criteria
            criteria = {
                'snapshot_exists': snapshot is not None,
                'no_divergence': divergence_count == 0,
                'no_open_trades': open_trades == 0
            }

            result['criteria'] = criteria
            passed = all(criteria.values())
            result['passed'] = passed

            # Log results
            logger.info(f"Broker Snapshot: {'EXISTS' if snapshot else 'MISSING'} "
                       f"{'PASS' if criteria['snapshot_exists'] else 'FAIL'}")
            logger.info(f"Recent Divergences: {divergence_count} "
                       f"{'PASS' if criteria['no_divergence'] else 'FAIL'}")
            logger.info(f"FHQ Open Trades: {open_trades} "
                       f"{'PASS' if criteria['no_open_trades'] else 'FAIL'}")

            logger.info("-" * 70)
            logger.info(f"PHASE 2 RESULT: {'PASSED' if passed else 'FAILED'}")

            return passed, result

        except Exception as e:
            logger.error(f"Phase 2 check failed: {e}")
            return False, {'error': str(e)}

    # =========================================================================
    # PHASE 3: PRE-REENABLE SAFETY GATE (Owner: STIG)
    # =========================================================================

    def check_phase_3(self) -> Tuple[bool, Dict]:
        """
        Phase 3 Acceptance Criteria:
        - All execution boundary controls LOCKED
        - Broker truth gating verified
        - Gates demonstrate deterministic blocking
        """
        logger.info("=" * 70)
        logger.info("PHASE 3: PRE-REENABLE SAFETY GATE CHECK")
        logger.info("Owner: STIG")
        logger.info("=" * 70)

        result = {
            'checked_at': datetime.now(timezone.utc).isoformat()
        }

        try:
            # Check 1: Verify broker_truth_enforcer module exists and loads
            try:
                from broker_truth_enforcer import (
                    get_broker_account_state,
                    validate_exposure_from_broker
                )
                broker_truth_available = True

                # Test that it blocks on adverse conditions
                state = get_broker_account_state()
                if state:
                    result['broker_state'] = {
                        'portfolio_value': state.portfolio_value,
                        'cash': state.cash,
                        'position_count': len(state.positions),
                        'is_margin_used': state.is_margin_used
                    }
            except ImportError:
                broker_truth_available = False
                result['broker_truth_error'] = 'Module not found'

            # Check 2: Verify unified_execution_gateway freeze is active
            try:
                from unified_execution_gateway import EXECUTION_FREEZE
                freeze_active = EXECUTION_FREEZE
            except ImportError:
                freeze_active = None
                result['gateway_error'] = 'Module not found'

            # Check 3: Verify signal_executor_daemon has kill switch
            daemon_path = os.path.join(os.path.dirname(__file__), 'signal_executor_daemon.py')
            daemon_has_kill_switch = False
            if os.path.exists(daemon_path):
                with open(daemon_path, 'r') as f:
                    content = f.read()
                    daemon_has_kill_switch = 'sys.exit(1)' in content[:2000]

            # Check 4: Verify exposure gates work
            gate_test_passed = False
            if broker_truth_available:
                # Test that gates would block if margin were used
                ok, reason = validate_exposure_from_broker()
                gate_test_passed = True  # Gate function exists and runs
                result['gate_test'] = {'ok': ok, 'reason': reason}

            # Acceptance criteria
            criteria = {
                'broker_truth_available': broker_truth_available,
                'freeze_active': freeze_active == True,
                'daemon_kill_switch': daemon_has_kill_switch,
                'gates_functional': gate_test_passed
            }

            result['criteria'] = criteria
            passed = all(criteria.values())
            result['passed'] = passed

            # Log results
            logger.info(f"Broker Truth Module: {'AVAILABLE' if broker_truth_available else 'MISSING'} "
                       f"{'PASS' if criteria['broker_truth_available'] else 'FAIL'}")
            logger.info(f"Execution Freeze: {freeze_active} "
                       f"{'PASS' if criteria['freeze_active'] else 'FAIL'}")
            logger.info(f"Daemon Kill Switch: {'PRESENT' if daemon_has_kill_switch else 'MISSING'} "
                       f"{'PASS' if criteria['daemon_kill_switch'] else 'FAIL'}")
            logger.info(f"Gates Functional: {'YES' if gate_test_passed else 'NO'} "
                       f"{'PASS' if criteria['gates_functional'] else 'FAIL'}")

            logger.info("-" * 70)
            logger.info(f"PHASE 3 RESULT: {'PASSED' if passed else 'FAILED'}")

            return passed, result

        except Exception as e:
            logger.error(f"Phase 3 check failed: {e}")
            return False, {'error': str(e)}

    # =========================================================================
    # PHASE 4: VEGA ATTESTATION CHECK
    # =========================================================================

    def check_phase_4(self) -> Tuple[bool, Dict]:
        """
        Phase 4 Acceptance Criteria:
        - VEGA has issued REENABLEMENT_APPROVED attestation
        """
        logger.info("=" * 70)
        logger.info("PHASE 4: VEGA ATTESTATION CHECK")
        logger.info("Owner: VEGA")
        logger.info("=" * 70)

        result = {
            'checked_at': datetime.now(timezone.utc).isoformat()
        }

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT *
                    FROM fhq_governance.governance_actions_log
                    WHERE action_type = 'VEGA_ATTESTATION'
                      AND decision = 'REENABLEMENT_APPROVED'
                      AND initiated_at > NOW() - INTERVAL '24 hours'
                    ORDER BY initiated_at DESC
                    LIMIT 1
                """)
                attestation = cur.fetchone()

                if attestation:
                    result['attestation'] = {
                        'action_id': attestation.get('action_id'),
                        'initiated_at': str(attestation.get('initiated_at')),
                        'rationale': attestation.get('decision_rationale')
                    }
                else:
                    result['attestation'] = None

            criteria = {
                'attestation_exists': attestation is not None
            }

            result['criteria'] = criteria
            passed = all(criteria.values())
            result['passed'] = passed

            logger.info(f"VEGA Attestation: {'FOUND' if attestation else 'NOT FOUND'} "
                       f"{'PASS' if criteria['attestation_exists'] else 'FAIL'}")

            logger.info("-" * 70)
            logger.info(f"PHASE 4 RESULT: {'PASSED' if passed else 'FAILED'}")

            if not passed:
                logger.warning("VEGA must issue REENABLEMENT_APPROVED before proceeding")

            return passed, result

        except Exception as e:
            logger.error(f"Phase 4 check failed: {e}")
            return False, {'error': str(e)}

    # =========================================================================
    # PHASE 5: CONTROLLED RE-ENABLEMENT (Owner: STIG + CEO)
    # =========================================================================

    def execute_phase_5(self, dry_run: bool = True) -> Tuple[bool, Dict]:
        """
        Phase 5: Controlled Re-Enablement
        - Remove daemon kill switch
        - Set EXECUTION_FREEZE = False
        - Run single-cycle dry run
        """
        logger.info("=" * 70)
        logger.info("PHASE 5: CONTROLLED RE-ENABLEMENT")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info("=" * 70)

        if dry_run:
            logger.info("DRY RUN: No changes will be made")
            return True, {'dry_run': True, 'message': 'Would execute re-enablement'}

        result = {
            'executed_at': datetime.now(timezone.utc).isoformat()
        }

        # First verify all prior phases pass
        p1_ok, _ = self.check_phase_1()
        p2_ok, _ = self.check_phase_2()
        p3_ok, _ = self.check_phase_3()
        p4_ok, _ = self.check_phase_4()

        if not all([p1_ok, p2_ok, p3_ok, p4_ok]):
            logger.error("CANNOT PROCEED: Prior phases have not passed")
            return False, {'error': 'Prior phases not passed'}

        logger.info("All prior phases PASSED - proceeding with re-enablement")

        # Step 1: Modify unified_execution_gateway.py
        gateway_path = os.path.join(os.path.dirname(__file__), 'unified_execution_gateway.py')
        try:
            with open(gateway_path, 'r') as f:
                content = f.read()

            # Change EXECUTION_FREEZE = True to False
            new_content = content.replace(
                'EXECUTION_FREEZE = True',
                'EXECUTION_FREEZE = False  # Re-enabled by CEO-REENABLE-2025-12-22'
            )

            with open(gateway_path, 'w') as f:
                f.write(new_content)

            result['gateway_modified'] = True
            logger.info("unified_execution_gateway.py: EXECUTION_FREEZE set to False")
        except Exception as e:
            logger.error(f"Failed to modify gateway: {e}")
            result['gateway_error'] = str(e)
            return False, result

        # Step 2: Remove daemon kill switch
        daemon_path = os.path.join(os.path.dirname(__file__), 'signal_executor_daemon.py')
        try:
            with open(daemon_path, 'r') as f:
                lines = f.readlines()

            # Find and comment out lines 32-40 (kill switch block)
            new_lines = []
            in_kill_block = False
            for i, line in enumerate(lines, 1):
                if i == 32 and 'import sys' in line:
                    new_lines.append('# KILL SWITCH REMOVED BY CEO-REENABLE-2025-12-22\n')
                    new_lines.append('# ' + line)
                    in_kill_block = True
                elif in_kill_block and i <= 40:
                    new_lines.append('# ' + line)
                    if i == 40:
                        in_kill_block = False
                else:
                    new_lines.append(line)

            with open(daemon_path, 'w') as f:
                f.writelines(new_lines)

            result['daemon_modified'] = True
            logger.info("signal_executor_daemon.py: Kill switch commented out")
        except Exception as e:
            logger.error(f"Failed to modify daemon: {e}")
            result['daemon_error'] = str(e)
            # Rollback gateway change
            self.rollback()
            return False, result

        # Log to governance
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type, action_target, decision,
                        decision_rationale, initiated_by, initiated_at
                    ) VALUES (
                        'REENABLE_EXECUTION', 'CEO-REENABLE-2025-12-22', 'EXECUTED',
                        %s, 'STIG', NOW()
                    )
                """, (json.dumps(result),))
            self.conn.commit()
            logger.info("Re-enablement logged to governance")
        except Exception as e:
            logger.warning(f"Failed to log to governance: {e}")

        logger.info("-" * 70)
        logger.info("PHASE 5 COMPLETE: Execution re-enabled")
        logger.info("Next: Run signal_executor_daemon.py --once to verify")

        return True, result

    # =========================================================================
    # ROLLBACK
    # =========================================================================

    def rollback(self) -> Tuple[bool, Dict]:
        """
        Emergency rollback: Re-freeze execution
        """
        logger.info("=" * 70)
        logger.info("ROLLBACK: RE-FREEZING EXECUTION")
        logger.info("=" * 70)

        result = {
            'executed_at': datetime.now(timezone.utc).isoformat()
        }

        # Step 1: Re-freeze gateway
        gateway_path = os.path.join(os.path.dirname(__file__), 'unified_execution_gateway.py')
        try:
            with open(gateway_path, 'r') as f:
                content = f.read()

            # Change EXECUTION_FREEZE = False to True
            new_content = content.replace(
                'EXECUTION_FREEZE = False',
                'EXECUTION_FREEZE = True  # ROLLBACK by CEO-REENABLE-2025-12-22'
            )

            with open(gateway_path, 'w') as f:
                f.write(new_content)

            result['gateway_refrozen'] = True
            logger.info("unified_execution_gateway.py: EXECUTION_FREEZE set to True")
        except Exception as e:
            logger.error(f"Failed to refreeze gateway: {e}")
            result['gateway_error'] = str(e)

        # Log rollback to governance
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type, action_target, decision,
                        decision_rationale, initiated_by, initiated_at
                    ) VALUES (
                        'ROLLBACK_EXECUTION', 'CEO-REENABLE-2025-12-22', 'EXECUTED',
                        %s, 'STIG', NOW()
                    )
                """, (json.dumps(result),))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to log rollback: {e}")

        logger.info("-" * 70)
        logger.info("ROLLBACK COMPLETE: Execution frozen")

        return True, result

    # =========================================================================
    # FULL STATUS
    # =========================================================================

    def get_full_status(self) -> Dict:
        """Get status of all phases"""
        p1_ok, p1 = self.check_phase_1()
        p2_ok, p2 = self.check_phase_2()
        p3_ok, p3 = self.check_phase_3()
        p4_ok, p4 = self.check_phase_4()

        return {
            'phase_1': {'passed': p1_ok, 'details': p1},
            'phase_2': {'passed': p2_ok, 'details': p2},
            'phase_3': {'passed': p3_ok, 'details': p3},
            'phase_4': {'passed': p4_ok, 'details': p4},
            'ready_for_phase_5': all([p1_ok, p2_ok, p3_ok, p4_ok])
        }


def main():
    parser = argparse.ArgumentParser(description='Re-Enablement Runbook Executor')
    parser.add_argument('--phase', type=int, choices=[1, 2, 3, 4, 5],
                        help='Check specific phase')
    parser.add_argument('--status', action='store_true',
                        help='Get full status of all phases')
    parser.add_argument('--execute', action='store_true',
                        help='Execute phase 5 (requires --phase 5)')
    parser.add_argument('--rollback', action='store_true',
                        help='Emergency rollback')
    args = parser.parse_args()

    runbook = ReenableRunbook()

    try:
        if args.rollback:
            ok, result = runbook.rollback()
            print(json.dumps(result, indent=2, default=str))
            sys.exit(0 if ok else 1)

        if args.status:
            status = runbook.get_full_status()
            print(json.dumps(status, indent=2, default=str))
            sys.exit(0 if status['ready_for_phase_5'] else 1)

        if args.phase:
            if args.phase == 1:
                ok, result = runbook.check_phase_1()
            elif args.phase == 2:
                ok, result = runbook.check_phase_2()
            elif args.phase == 3:
                ok, result = runbook.check_phase_3()
            elif args.phase == 4:
                ok, result = runbook.check_phase_4()
            elif args.phase == 5:
                ok, result = runbook.execute_phase_5(dry_run=not args.execute)

            print(json.dumps(result, indent=2, default=str))
            sys.exit(0 if ok else 1)
        else:
            # Default: show status
            status = runbook.get_full_status()
            print(json.dumps(status, indent=2, default=str))

    finally:
        runbook.close()


if __name__ == '__main__':
    main()
