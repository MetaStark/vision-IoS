#!/usr/bin/env python3
"""
AUTONOMY CLOCK TICK
===================
CEO-DIR-2026-007-D: Implements the daily tick mechanism for the autonomy clock.

Runs once daily at 23:55 CET. Evaluates whether all conditions for an
autonomous day were met, then increments or resets the streak.

Tick conditions (CEO-DIR-2026-097):
1. All scheduled autonomous daemons executed in the last 24h
2. All executions were unattended (no CEO_OVERRIDE)
3. discrepancy_score <= 0.10 for all executions

If YES to all: increment consecutive_days, insert TICK into history
If NO to any:  reset to 0, insert RESET with reason

Database operations:
  READS:  daemon_health, autonomy_clock_state, execution results
  WRITES: autonomy_clock_state, autonomy_clock_history

Author: STIG (CTO)
Date: 2026-02-04
Contract: EC-003_2026_PRODUCTION
Directive: CEO-DIR-2026-007-D
"""

import os
import sys
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[AUTONOMY_CLOCK] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/autonomy_clock_tick.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('autonomy_clock')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

CLOCK_ID = '7c09bbec-bc9a-4499-bb1f-19af8a4f590d'
DISCREPANCY_THRESHOLD = 0.10


def check_daemon_execution(conn) -> tuple:
    """Check if all ACTIVE daemons heartbeated in the last 24h.

    Returns (passed: bool, failures: list[str])
    """
    failures = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT daemon_name, last_heartbeat,
                   EXTRACT(epoch FROM (NOW() - last_heartbeat)) / 3600 AS hours_ago
            FROM fhq_monitoring.daemon_health
            WHERE lifecycle_status = 'ACTIVE'
        """)
        daemons = cur.fetchall()

        for d in daemons:
            if d['hours_ago'] and d['hours_ago'] > 24:
                failures.append(
                    f"{d['daemon_name']}: last heartbeat {d['hours_ago']:.1f}h ago"
                )

    passed = len(failures) == 0
    return passed, failures


def check_no_ceo_override(conn) -> tuple:
    """Check that no CEO_OVERRIDE occurred in the last 24h.

    Returns (passed: bool, overrides: list[str])
    """
    overrides = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check control_room_alerts for CEO overrides
        cur.execute("""
            SELECT alert_type, alert_message, created_at
            FROM fhq_ops.control_room_alerts
            WHERE alert_type = 'CEO_OVERRIDE'
              AND created_at > NOW() - INTERVAL '24 hours'
        """)
        rows = cur.fetchall()
        for r in rows:
            overrides.append(f"{r['alert_message']} at {r['created_at']}")

    passed = len(overrides) == 0
    return passed, overrides


def check_discrepancy_scores(conn) -> tuple:
    """Check that all discrepancy_scores in the last 24h are <= threshold.

    Returns (passed: bool, violations: list[str])
    """
    violations = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT event_id, discrepancy_score, discrepancy_type, created_at
            FROM fhq_governance.discrepancy_events
            WHERE created_at > NOW() - INTERVAL '24 hours'
              AND discrepancy_score > %s
            ORDER BY discrepancy_score DESC
            LIMIT 5
        """, (DISCREPANCY_THRESHOLD,))
        rows = cur.fetchall()
        for r in rows:
            violations.append(
                f"event {r['event_id']}: "
                f"discrepancy={r['discrepancy_score']} ({r['discrepancy_type']})"
            )

    passed = len(violations) == 0
    return passed, violations


def perform_tick(conn):
    """Evaluate tick conditions and update clock state."""
    logger.info("=" * 60)
    logger.info("AUTONOMY CLOCK TICK — Evaluating conditions")
    logger.info("=" * 60)

    # Get current state
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM fhq_governance.autonomy_clock_state
            WHERE clock_id = %s
        """, (CLOCK_ID,))
        state = cur.fetchone()

    if not state:
        logger.error(f"Clock state not found for {CLOCK_ID}")
        return

    current_days = state['consecutive_days']
    logger.info(f"Current streak: {current_days} days")

    # Evaluate conditions
    daemon_ok, daemon_failures = check_daemon_execution(conn)
    logger.info(f"Condition 1 (daemon execution): {'PASS' if daemon_ok else 'FAIL'}")
    if daemon_failures:
        for f in daemon_failures:
            logger.info(f"  - {f}")

    override_ok, overrides = check_no_ceo_override(conn)
    logger.info(f"Condition 2 (no CEO override): {'PASS' if override_ok else 'FAIL'}")
    if overrides:
        for o in overrides:
            logger.info(f"  - {o}")

    discrepancy_ok, violations = check_discrepancy_scores(conn)
    logger.info(f"Condition 3 (discrepancy <= {DISCREPANCY_THRESHOLD}): "
                f"{'PASS' if discrepancy_ok else 'FAIL'}")
    if violations:
        for v in violations:
            logger.info(f"  - {v}")

    all_passed = daemon_ok and override_ok and discrepancy_ok

    if all_passed:
        new_days = current_days + 1
        event_type = 'TICK'
        reason = f"All conditions met. Day {new_days} autonomous."
        logger.info(f"ALL CONDITIONS MET — incrementing to {new_days}")
    else:
        new_days = 0
        event_type = 'RESET'
        fail_reasons = []
        if not daemon_ok:
            fail_reasons.append(f"daemon_failures={len(daemon_failures)}")
        if not override_ok:
            fail_reasons.append(f"ceo_overrides={len(overrides)}")
        if not discrepancy_ok:
            fail_reasons.append(f"discrepancy_violations={len(violations)}")
        reason = f"Conditions not met: {', '.join(fail_reasons)}"
        logger.info(f"CONDITIONS NOT MET — resetting to 0: {reason}")

    # Build evidence hash
    evidence = {
        'tick_timestamp': datetime.now(timezone.utc).isoformat(),
        'conditions': {
            'daemon_execution': daemon_ok,
            'no_ceo_override': override_ok,
            'discrepancy_threshold': discrepancy_ok,
        },
        'consecutive_days_before': current_days,
        'consecutive_days_after': new_days,
    }
    evidence_str = json.dumps(evidence, sort_keys=True)
    evidence_hash = 'sha256:' + hashlib.sha256(evidence_str.encode()).hexdigest()

    with conn.cursor() as cur:
        # Update clock state
        if all_passed:
            cur.execute("""
                UPDATE fhq_governance.autonomy_clock_state
                SET consecutive_days = %s,
                    last_tick_at = NOW(),
                    updated_at = NOW(),
                    total_autonomous_days = total_autonomous_days + 1,
                    longest_streak = GREATEST(longest_streak, %s),
                    evidence_hash = %s
                WHERE clock_id = %s
            """, (new_days, new_days, evidence_hash, CLOCK_ID))
        else:
            cur.execute("""
                UPDATE fhq_governance.autonomy_clock_state
                SET consecutive_days = 0,
                    last_tick_at = NOW(),
                    updated_at = NOW(),
                    current_streak_start = CURRENT_DATE + 1,
                    reset_reason = %s,
                    reset_by = 'AUTONOMY_CLOCK_TICK',
                    reset_at = NOW(),
                    total_resets = total_resets + 1,
                    evidence_hash = %s
                WHERE clock_id = %s
            """, (reason, evidence_hash, CLOCK_ID))

        # Insert history event
        cur.execute("""
            INSERT INTO fhq_governance.autonomy_clock_history (
                clock_id, event_type, event_timestamp,
                consecutive_days_before, consecutive_days_after,
                triggered_by, reason, evidence_hash
            ) VALUES (%s, %s, NOW(), %s, %s, 'AUTONOMY_CLOCK_TICK', %s, %s)
        """, (CLOCK_ID, event_type, current_days, new_days, reason, evidence_hash))

        conn.commit()

    logger.info(f"Clock updated: {current_days} -> {new_days} ({event_type})")
    logger.info(f"Evidence hash: {evidence_hash}")

    # Write evidence file
    evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
    os.makedirs(evidence_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    evidence_path = os.path.join(evidence_dir, f'AUTONOMY_CLOCK_TICK_{ts}.json')
    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)
    logger.info(f"Evidence: {evidence_path}")

    return evidence


def main():
    logger.info("Autonomy Clock Tick — CEO-DIR-2026-007-D")
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        perform_tick(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
