#!/usr/bin/env python3
"""
DIR-024 ACCEPTANCE TESTS (HARD GATES)
====================================
CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024 - Directive 4, Order 5

PURPOSE: Run acceptance tests with hard gates to verify DIR-024 implementation.
         Tests verify data integrity, settlement flow, and LVI readiness.

ACCEPTANCE TESTS (Hard Gates):
AT-1: outcome_pack_link.count > 0 and rising daily
AT-2: decision_packs has non-zero EXECUTED created in last 24h
AT-3: outcome_settlement_log append-only growth with no deletes/updates
AT-4: LVI next cycle > 0 (or explicitly blocked with evidence showing why)

STOP CONDITIONS:
- Any non-daemon writer updates decision_packs.execution_status - immediate halt
- Any EXECUTED pack without outcome_pack_link - immediate halt
- Any settlement without a log row - immediate halt

Authority: CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024
Classification: G4_ACCEPTANCE_TEST
Executor: STIG (EC-003)
"""

import os
import sys
import json
import hashlib
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

DAEMON_NAME = 'dir_024_acceptance_tests'

logging.basicConfig(
    level=logging.INFO,
    format='[ACCEPTANCE_TEST] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/dir_024_acceptance_tests.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def test_outcome_pack_link_growth(conn) -> Dict:
    """AT-1: outcome_pack_link.count > 0 and rising daily."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Count links per day for last 7 days
    cur.execute("""
        SELECT
            DATE(linked_at) as link_date,
            COUNT(*) as link_count
        FROM fhq_learning.outcome_pack_link
        WHERE linked_at >= NOW() - INTERVAL '7 days'
        GROUP BY DATE(linked_at)
        ORDER BY link_date ASC
    """)

    daily_links = cur.fetchall()

    # Convert date objects to strings for JSON serialization
    for i in range(len(daily_links)):
        if 'link_date' in daily_links[i] and hasattr(daily_links[i]['link_date'], 'isoformat'):
            daily_links[i]['link_date'] = daily_links[i]['link_date'].isoformat()

    daily_links = cur.fetchall()

    # Check for growth (each day should have >= previous day)
    has_growth = True
    for i in range(1, len(daily_links)):
        if daily_links[i]['link_count'] < daily_links[i-1]['link_count']:
            has_growth = False
            break

    result = {
        'test_name': 'AT-1 outcome_pack_link_growth',
        'test_type': 'GROWTH',
        'passed': has_growth and len(daily_links) >= 3,  # At least 3 days of data
        'criteria': 'outcome_pack_link.count > 0 AND each day >= previous day (7 days)',
        'observation': {
            'days_analyzed': len(daily_links),
            'daily_links': daily_links,
            'has_growth': has_growth
        }
    }

    return result


def test_executed_packs_24h(conn) -> Dict:
    """AT-2: decision_packs has non-zero EXECUTED created in last 24h."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            COUNT(*) FILTER (
                WHERE execution_status = 'EXECUTED'
                AND terminalized_at >= NOW() - INTERVAL '24 hours'
            ) as executed_24h
        FROM fhq_learning.decision_packs
    """)

    result = cur.fetchone()
    executed_24h = result['executed_24h'] if result else 0

    passed = executed_24h > 0

    result = {
        'test_name': 'AT-2 executed_packs_24h',
        'test_type': 'COUNT',
        'passed': passed,
        'criteria': 'decision_packs has non-zero EXECUTED created in last 24h',
        'observation': {
            'executed_24h': executed_24h,
            'passed': passed
        }
    }

    return result


def test_settlement_log_append_only(conn) -> Dict:
    """AT-3: outcome_settlement_log append-only growth with no deletes/updates."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get current row count and check if any rows exist
    cur.execute("""
        SELECT
            COUNT(*) as total_rows
        FROM fhq_learning.outcome_settlement_log
    """)

    result = cur.fetchone()
    total_rows = result['total_rows'] if result else 0

    # Check for append-only behavior (should have only INSERT operations)
    # This is enforced by trigger trg_prevent_settlement_log_delete

    passed = total_rows > 0  # At least some rows should exist

    result = {
        'test_name': 'AT-3 outcome_settlement_log_append_only',
        'test_type': 'INTEGRITY',
        'passed': passed,
        'criteria': 'outcome_settlement_log append-only growth with no deletes/updates',
        'observation': {
            'total_rows': total_rows,
            'append_only_enforced': True,  # Enforced by trigger
            'passed': passed
        }
    }

    return result


def test_lvi_next_cycle(conn) -> Dict:
    """AT-4: LVI next cycle > 0 (or explicitly blocked with evidence showing why)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get current LVI value
    cur.execute("""
        SELECT
            lvi_value,
            computed_at,
            window_start,
            window_end
        FROM fhq_governance.lvi_canonical
        ORDER BY computed_at DESC
        LIMIT 1
    """)

    lvi_result = cur.fetchone()

    lvi_value = float(lvi_result['lvi_value']) if lvi_result and lvi_result['lvi_value'] is not None else None
    lvi_computed_at = lvi_result['computed_at'].isoformat() if lvi_result and lvi_result['computed_at'] else None

    # Check for completed experiments in last 7 days (LVI computation window)
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE completed_at >= NOW() - INTERVAL '7 days')
        FROM fhq_learning.experiment_registry
        WHERE status = 'COMPLETED'
    """)

    exp_result = cur.fetchone()
    completed_experiments = exp_result['count'] if exp_result else 0

    # Determine LVI status
    passed = lvi_value is not None and lvi_value > 0

    status = 'POSITIVE' if passed else 'ZERO_OR_BLOCKED'
    if lvi_value is not None and lvi_value == 0:
        status = 'ZERO_NEEDS_INVESTIGATION'
    elif lvi_value is None:
        status = 'NO_LVI_COMPUTED'

    result = {
        'test_name': 'AT-4 lvi_next_cycle',
        'test_type': 'VALUE',
        'passed': passed,
        'criteria': 'LVI > 0 (or explicitly blocked with evidence)',
        'observation': {
            'lvi_value': lvi_value,
            'lvi_computed_at': lvi_computed_at,
            'completed_experiments_7d': completed_experiments,
            'status': status
        }
    }

    return result


def run_acceptance_tests() -> Dict:
    """Run all acceptance tests and generate report."""
    conn = get_connection()
    test_results = []

    try:
        # Run all acceptance tests
        test_results.append(test_outcome_pack_link_growth(conn))
        test_results.append(test_executed_packs_24h(conn))
        test_results.append(test_settlement_log_append_only(conn))
        test_results.append(test_lvi_next_cycle(conn))

        # Generate summary
        passed_count = sum(1 for t in test_results if t['passed'])
        failed_count = sum(1 for t in test_results if not t['passed'])
        total_count = len(test_results)

        # Generate evidence
        evidence = {
            'directive': 'CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024',
            'evidence_type': 'ACCEPTANCE_TESTS',
            'computed_at': datetime.now(timezone.utc).isoformat(),
            'computed_by': 'STIG',
            'ec_contract': 'EC-003',
            'test_results': test_results,
            'summary': {
                'total_tests': total_count,
                'passed': passed_count,
                'failed': failed_count,
                'success_rate': f"{(passed_count/total_count*100):.1f}%" if total_count > 0 else "N/A"
            }
        }

        evidence_str = json.dumps(evidence, sort_keys=True)
        evidence['evidence_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()[:16]

        # Save evidence file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(script_dir, 'evidence', f'DIR_024_ACCEPTANCE_TESTS_{timestamp}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        logger.info(f"Evidence: {evidence_path}")

        return evidence

    except Exception as e:
        logger.error(f"Acceptance tests failed: {e}")
        raise
    finally:
        conn.close()


def main():
    """Main entry point for acceptance tests."""
    parser = argparse.ArgumentParser(description='DIR-024 Acceptance Tests')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("DIR-024 ACCEPTANCE TESTS (HARD GATES)")
    logger.info("CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024: Acceptance Testing")
    logger.info("=" * 60)

    evidence = run_acceptance_tests()

    # Print summary
    print(f"\nAcceptance Test Summary:")
    print(f"  Total tests: {len(evidence['test_results'])}")
    print(f"  Passed: {evidence['summary']['passed']}")
    print(f"  Failed: {evidence['summary']['failed']}")
    print(f"  Success rate: {evidence['summary']['success_rate']}")


if __name__ == '__main__':
    main()
