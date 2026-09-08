#!/usr/bin/env python3
"""
LEARNING VALIDATION MEASUREMENT
================================
CEO-DIR-2026-LEARNING-VALIDATION-WINDOW-005

Purpose: Measure and log learning system metrics every 6 hours during 48h validation window.

Metrics measured:
1. CLOSED trades total and new
2. hypothesis_trade_performance updates
3. guardrail_passed count
4. learning_allowed status
5. LVI value
6. Hypothesis status changes from trades

Author: STIG (EC-003)
Date: 2026-02-10
Classification: EXPERIMENTAL - No code changes during window
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[VALIDATION] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger('validation')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', '')
}

WINDOW_STATE_FILE = 'C:/fhq-market-system/vision-ios/03_FUNCTIONS/evidence/VALIDATION_WINDOW_STATE.json'


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def load_window_state():
    """Load validation window state."""
    if os.path.exists(WINDOW_STATE_FILE):
        with open(WINDOW_STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        'window_started': False,
        'start_time': None,
        'trigger_trade_id': None,
        'measurements': [],
        'baseline_closed_trades': None
    }


def save_window_state(state):
    """Save validation window state."""
    with open(WINDOW_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)


def get_closed_trades_count(conn):
    """Get total CLOSED trades with REALIZED pnl."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM fhq_execution.shadow_trades
            WHERE status = 'CLOSED' AND pnl_type = 'REALIZED'
        """)
        return cur.fetchone()[0]


def get_latest_closed_trade(conn):
    """Get the most recent CLOSED trade."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT trade_id, exit_time, asset_id, shadow_pnl
            FROM fhq_execution.shadow_trades
            WHERE status = 'CLOSED' AND pnl_type = 'REALIZED'
            ORDER BY exit_time DESC
            LIMIT 1
        """)
        return cur.fetchone()


def get_htp_stats(conn):
    """Get hypothesis_trade_performance statistics."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_records,
                SUM(CASE WHEN total_closed_trades > 0 THEN 1 ELSE 0 END) as with_trades,
                SUM(CASE WHEN guardrail_passed = TRUE THEN 1 ELSE 0 END) as guardrail_passed,
                SUM(CASE WHEN eval_status = 'FALSIFIED' THEN 1 ELSE 0 END) as falsified,
                SUM(CASE WHEN eval_status = 'PASSING' THEN 1 ELSE 0 END) as passing
            FROM fhq_learning.hypothesis_trade_performance
        """)
        return cur.fetchone()


def check_learning_allowed(conn):
    """Check if learning is allowed (exit coverage SLA met)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) as exits_48h
            FROM fhq_execution.shadow_trades
            WHERE status = 'CLOSED'
              AND pnl_type = 'REALIZED'
              AND exit_time >= NOW() - INTERVAL '48 hours'
        """)
        exits_48h = cur.fetchone()[0]
        return exits_48h >= 1, exits_48h


def get_lvi(conn):
    """Get current LVI value."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT lvi_value
            FROM fhq_monitoring.lvi_history
            ORDER BY computed_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        return float(row[0]) if row else 0.0


def get_hypothesis_status_changes(conn, since_time):
    """Get hypothesis status changes since a given time."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                hypothesis_code,
                status,
                annihilation_reason,
                last_updated_at,
                last_updated_by
            FROM fhq_learning.hypothesis_canon
            WHERE last_updated_at >= %s
              AND last_updated_by = 'trade_falsification_daemon'
            ORDER BY last_updated_at DESC
        """, (since_time,))
        return cur.fetchall()


def take_measurement(conn, state, hour_in_window):
    """Take a measurement and log it."""
    now = datetime.now(timezone.utc)

    # Get metrics
    closed_trades = get_closed_trades_count(conn)
    baseline = state.get('baseline_closed_trades', closed_trades)
    new_trades = closed_trades - baseline

    htp_stats = get_htp_stats(conn)
    learning_allowed, exits_48h = check_learning_allowed(conn)
    lvi = get_lvi(conn)

    # Get status changes since window start
    start_time = state.get('start_time')
    if start_time:
        status_changes = get_hypothesis_status_changes(conn, start_time)
    else:
        status_changes = []

    measurement = {
        'timestamp': now.isoformat(),
        'window_hour': hour_in_window,
        'closed_trades_total': closed_trades,
        'closed_trades_new': new_trades,
        'htp_records_with_trades': htp_stats['with_trades'],
        'guardrail_passed_count': htp_stats['guardrail_passed'],
        'falsified_count': htp_stats['falsified'],
        'passing_count': htp_stats['passing'],
        'exits_48h': exits_48h,
        'learning_allowed': learning_allowed,
        'lvi_value': lvi,
        'hypothesis_status_changes': len(status_changes),
        'status_change_details': [
            {
                'hypothesis': s['hypothesis_code'],
                'status': s['status'],
                'reason': s['annihilation_reason']
            }
            for s in status_changes
        ]
    }

    return measurement


def print_measurement(m):
    """Print measurement in readable format."""
    logger.info("=" * 70)
    logger.info(f"VALIDATION MEASUREMENT - Hour {m['window_hour']} of 48")
    logger.info("=" * 70)
    logger.info(f"Timestamp:              {m['timestamp']}")
    logger.info(f"CLOSED trades total:    {m['closed_trades_total']}")
    logger.info(f"CLOSED trades new:      {m['closed_trades_new']}")
    logger.info(f"HTP with trades:        {m['htp_records_with_trades']}")
    logger.info(f"Guardrail passed:       {m['guardrail_passed_count']}")
    logger.info(f"Exits (48h):            {m['exits_48h']}")
    logger.info(f"Learning allowed:       {m['learning_allowed']}")
    logger.info(f"LVI:                    {m['lvi_value']}")
    logger.info(f"Status changes:         {m['hypothesis_status_changes']}")
    if m['status_change_details']:
        for sc in m['status_change_details']:
            logger.info(f"  -> {sc['hypothesis']}: {sc['status']}")
    logger.info("=" * 70)


def main():
    logger.info("CEO-DIR-2026-LEARNING-VALIDATION-WINDOW-005")
    logger.info("48h Learning Validation Measurement")
    logger.info("")

    state = load_window_state()
    conn = get_db_connection()

    try:
        # Check if window has started
        if not state['window_started']:
            # Check for new closed trades since baseline
            latest = get_latest_closed_trade(conn)
            baseline_count = state.get('baseline_closed_trades')

            if baseline_count is None:
                # Set baseline
                baseline_count = get_closed_trades_count(conn)
                state['baseline_closed_trades'] = baseline_count
                logger.info(f"Baseline set: {baseline_count} CLOSED trades")
                save_window_state(state)

            current_count = get_closed_trades_count(conn)
            if current_count > baseline_count:
                # Window starts!
                state['window_started'] = True
                state['start_time'] = datetime.now(timezone.utc).isoformat()
                state['trigger_trade_id'] = str(latest['trade_id']) if latest else None
                logger.info("=" * 70)
                logger.info("VALIDATION WINDOW STARTED!")
                logger.info(f"Trigger: {current_count - baseline_count} new CLOSED trades")
                logger.info(f"Start time: {state['start_time']}")
                logger.info("48h countdown begins NOW")
                logger.info("=" * 70)
                save_window_state(state)
            else:
                logger.info(f"Awaiting trigger: {current_count} CLOSED (baseline: {baseline_count})")
                logger.info("Window will start when first new realized exit is registered")
                return

        # Calculate hour in window
        start_time = datetime.fromisoformat(state['start_time'].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        hours_elapsed = (now - start_time).total_seconds() / 3600

        if hours_elapsed >= 48:
            logger.info("=" * 70)
            logger.info("VALIDATION WINDOW COMPLETE (48h elapsed)")
            logger.info("Ready for VEGA attestation review")
            logger.info("=" * 70)
            # Take final measurement
            measurement = take_measurement(conn, state, 48)
            state['measurements'].append(measurement)
            state['window_complete'] = True
            save_window_state(state)
            print_measurement(measurement)
            return

        # Take measurement
        hour_in_window = int(hours_elapsed)
        measurement = take_measurement(conn, state, hour_in_window)
        state['measurements'].append(measurement)
        save_window_state(state)

        print_measurement(measurement)

        # Check success criterion
        if measurement['hypothesis_status_changes'] > 0:
            logger.info("")
            logger.info("*** SUCCESS CRITERION MET ***")
            logger.info("At least one hypothesis changed status based on trade-performance!")
            logger.info("FjordHQ is epistemically corrected.")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
