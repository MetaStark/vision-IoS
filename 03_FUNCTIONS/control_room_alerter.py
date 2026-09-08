#!/usr/bin/env python3
"""
Control Room Alerter
CEO-DIR-2026-023 Order 5

Purpose: Monitor system health and generate alerts for Control Room.
Integrates with Telegram for critical notifications.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres'
}

# Alert Rules Configuration
ALERT_RULES = [
    {
        'name': 'pipeline_stall',
        'query': """
            SELECT COALESCE(
                EXTRACT(EPOCH FROM NOW() - MAX(created_at)) / 3600,
                999
            ) as hours_since
            FROM fhq_signal_context.weighted_signal_plan
        """,
        'threshold': 4,
        'operator': '>',
        'severity': 'CRITICAL',
        'message': 'Signal pipeline stalled > 4 hours',
        'category': 'PIPELINE'
    },
    {
        'name': 'ios016_event_ingestion_missing',
        'query': """
            SELECT COUNT(*) as count
            FROM fhq_calendar.calendar_events
            WHERE event_timestamp > NOW() AND event_timestamp < NOW() + INTERVAL '7 days'
        """,
        'threshold': 0,
        'operator': '<=',
        'severity': 'WARNING',
        'message': 'No upcoming IoS-016 events in next 7 days',
        'category': 'EVENT'
    },
    {
        'name': 'hypothesis_not_pre_committed',
        'query': """
            SELECT COUNT(*) as count
            FROM fhq_calendar.calendar_events ce
            LEFT JOIN fhq_learning.hypothesis_ledger hl ON ce.event_id = hl.event_id
            WHERE ce.event_timestamp BETWEEN NOW() AND NOW() + INTERVAL '4 hours'
            AND hl.hypothesis_id IS NULL
        """,
        'threshold': 0,
        'operator': '>',
        'severity': 'WARNING',
        'message': 'Event approaching without pre-committed hypothesis',
        'category': 'LEARNING',
        'requires_table': 'fhq_learning.hypothesis_ledger'
    },
    {
        'name': 'outcome_not_recorded_24h',
        'query': """
            SELECT COUNT(*) as count
            FROM fhq_learning.hypothesis_ledger hl
            LEFT JOIN fhq_learning.expectation_outcome_ledger eol
                ON hl.hypothesis_id = eol.hypothesis_id
            WHERE hl.immutable_after < NOW() - INTERVAL '24 hours'
            AND eol.outcome_id IS NULL
        """,
        'threshold': 0,
        'operator': '>',
        'severity': 'CRITICAL',
        'message': 'Outcome not recorded within T+24h deadline',
        'category': 'LEARNING',
        'requires_table': 'fhq_learning.expectation_outcome_ledger'
    },
    {
        'name': 'epistemic_proposals_empty',
        'query': """
            SELECT COUNT(*) as count FROM fhq_governance.epistemic_proposals
        """,
        'threshold': 0,
        'operator': '<=',
        'severity': 'WARNING',
        'message': 'No epistemic proposals - forward hypothesis generation blocked',
        'category': 'LEARNING'
    },
    {
        'name': 'daemon_heartbeat_stale',
        'query': """
            SELECT COUNT(*) as count
            FROM fhq_governance.agent_heartbeats
            WHERE EXTRACT(EPOCH FROM NOW() - last_heartbeat) / 3600 > 24
        """,
        'threshold': 0,
        'operator': '>',
        'severity': 'WARNING',
        'message': 'One or more daemon heartbeats stale > 24h',
        'category': 'DAEMON'
    },
    {
        'name': 'lvi_degradation',
        'query': """
            SELECT COALESCE(lvi_score, 0) as score
            FROM fhq_ops.control_room_lvi
            ORDER BY computed_at DESC
            LIMIT 1
        """,
        'threshold': 0.1,
        'operator': '<',
        'severity': 'CRITICAL',
        'message': 'LVI score below critical threshold (< 0.1)',
        'category': 'LVI',
        'requires_table': 'fhq_ops.control_room_lvi'
    },
    {
        'name': 'calibration_degradation',
        'query': """
            SELECT COALESCE(
                100.0 * COUNT(*) FILTER (WHERE calibration_status = 'CALIBRATED') /
                NULLIF(COUNT(*), 0),
                0
            ) as pct
            FROM fhq_signal_context.weighted_signal_plan
        """,
        'threshold': 50,
        'operator': '<',
        'severity': 'CRITICAL',
        'message': 'Calibration rate below 50%',
        'category': 'CALIBRATION'
    }
]


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def table_exists(cur, table_name: str) -> bool:
    """Check if a table exists."""
    schema, table = table_name.split('.') if '.' in table_name else ('public', table_name)
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        ) as exists
    """, (schema, table))
    result = cur.fetchone()
    return result['exists'] if isinstance(result, dict) else result[0]


def evaluate_rule(cur, rule: Dict) -> Optional[Dict]:
    """
    Evaluate a single alert rule.

    Returns:
        Alert dict if triggered, None otherwise
    """
    # Check if required table exists
    if 'requires_table' in rule:
        if not table_exists(cur, rule['requires_table']):
            logger.debug(f"Skipping rule {rule['name']} - required table {rule['requires_table']} does not exist")
            return None

    try:
        cur.execute(rule['query'])
        result = cur.fetchone()

        if result is None:
            return None

        # Get the value (first column)
        value = list(result.values())[0] if isinstance(result, dict) else result[0]

        if value is None:
            value = 0

        # Evaluate condition
        triggered = False
        if rule['operator'] == '>':
            triggered = value > rule['threshold']
        elif rule['operator'] == '<':
            triggered = value < rule['threshold']
        elif rule['operator'] == '>=':
            triggered = value >= rule['threshold']
        elif rule['operator'] == '<=':
            triggered = value <= rule['threshold']
        elif rule['operator'] == '==':
            triggered = value == rule['threshold']

        if triggered:
            return {
                'alert_type': rule['name'],
                'alert_severity': rule['severity'],
                'alert_message': f"{rule['message']} (value={value}, threshold={rule['threshold']})",
                'alert_source': f"control_room_alerter.{rule['category']}",
                'value': value,
                'threshold': rule['threshold'],
                'category': rule['category']
            }

        return None

    except Exception as e:
        logger.error(f"Error evaluating rule {rule['name']}: {e}")
        return None


def check_all_rules(conn) -> List[Dict]:
    """
    Evaluate all alert rules and return triggered alerts.

    Returns:
        List of triggered alert dicts
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)
    alerts = []

    for rule in ALERT_RULES:
        alert = evaluate_rule(cur, rule)
        if alert:
            alerts.append(alert)
            logger.warning(f"ALERT: {alert['alert_type']} - {alert['alert_severity']}")

    return alerts


def store_alerts(conn, alerts: List[Dict]) -> List[str]:
    """
    Store alerts in control_room_alerts table.

    Returns:
        List of stored alert IDs
    """
    if not alerts:
        return []

    cur = conn.cursor()

    # Check if table exists
    if not table_exists(cur, 'fhq_ops.control_room_alerts'):
        logger.warning("fhq_ops.control_room_alerts does not exist - run migration 332 first")
        return []

    alert_ids = []
    for alert in alerts:
        # Check for existing unresolved alert of same type
        cur.execute("""
            SELECT alert_id FROM fhq_ops.control_room_alerts
            WHERE alert_type = %s AND is_resolved = FALSE
        """, (alert['alert_type'],))

        existing = cur.fetchone()
        if existing:
            # Update existing alert timestamp
            cur.execute("""
                UPDATE fhq_ops.control_room_alerts
                SET alert_message = %s, created_at = NOW()
                WHERE alert_id = %s
            """, (alert['alert_message'], existing[0]))
            alert_ids.append(str(existing[0]))
        else:
            # Create new alert
            cur.execute("""
                INSERT INTO fhq_ops.control_room_alerts
                (alert_type, alert_severity, alert_message, alert_source, auto_generated)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING alert_id
            """, (
                alert['alert_type'],
                alert['alert_severity'],
                alert['alert_message'],
                alert['alert_source']
            ))
            alert_ids.append(str(cur.fetchone()[0]))

    conn.commit()
    return alert_ids


def resolve_alert(conn, alert_type: str, resolved_by: str = 'STIG', notes: str = None):
    """Resolve an alert by type."""
    cur = conn.cursor()

    if not table_exists(cur, 'fhq_ops.control_room_alerts'):
        logger.warning("fhq_ops.control_room_alerts does not exist")
        return

    cur.execute("""
        UPDATE fhq_ops.control_room_alerts
        SET is_resolved = TRUE, resolved_at = NOW(), resolved_by = %s, resolution_notes = %s
        WHERE alert_type = %s AND is_resolved = FALSE
    """, (resolved_by, notes, alert_type))

    conn.commit()
    logger.info(f"Resolved alert: {alert_type}")


def get_active_alerts(conn) -> List[Dict]:
    """Get all active (unresolved) alerts."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if not table_exists(cur, 'fhq_ops.control_room_alerts'):
        return []

    cur.execute("""
        SELECT alert_id, alert_type, alert_severity, alert_message, created_at
        FROM fhq_ops.control_room_alerts
        WHERE is_resolved = FALSE
        ORDER BY
            CASE alert_severity
                WHEN 'CRITICAL' THEN 1
                WHEN 'WARNING' THEN 2
                ELSE 3
            END,
            created_at DESC
    """)

    return cur.fetchall()


def generate_summary(alerts: List[Dict]) -> str:
    """Generate a summary of current alerts."""
    if not alerts:
        return "CONTROL ROOM: All systems GREEN"

    critical_count = sum(1 for a in alerts if a.get('alert_severity') == 'CRITICAL')
    warning_count = sum(1 for a in alerts if a.get('alert_severity') == 'WARNING')

    summary = f"CONTROL ROOM: {critical_count} CRITICAL, {warning_count} WARNING\n"
    for alert in alerts:
        severity_icon = "🔴" if alert.get('alert_severity') == 'CRITICAL' else "🟡"
        summary += f"{severity_icon} {alert.get('alert_type', 'unknown')}: {alert.get('alert_message', '')}\n"

    return summary


def main():
    """Main entry point for alerter."""
    logger.info("Starting Control Room Alerter check...")

    try:
        conn = get_connection()

        # Check all rules
        alerts = check_all_rules(conn)

        # Store alerts
        alert_ids = store_alerts(conn, alerts)

        # Get all active alerts
        active_alerts = get_active_alerts(conn)

        # Generate summary
        summary = generate_summary(alerts)

        # Print results
        print("\n" + "=" * 60)
        print("CONTROL ROOM ALERT CHECK")
        print("=" * 60)
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print(f"Rules evaluated: {len(ALERT_RULES)}")
        print(f"Alerts triggered: {len(alerts)}")
        print(f"Active alerts: {len(active_alerts)}")
        print("-" * 60)

        if alerts:
            print("\nNEW ALERTS:")
            for alert in alerts:
                severity_icon = "[!!!]" if alert['alert_severity'] == 'CRITICAL' else "[!]"
                print(f"  {severity_icon} [{alert['alert_severity']}] {alert['alert_type']}")
                print(f"     {alert['alert_message']}")
        else:
            print("\n[OK] No new alerts triggered")

        if active_alerts:
            print("\nALL ACTIVE ALERTS:")
            for alert in active_alerts:
                severity_icon = "[!!!]" if alert['alert_severity'] == 'CRITICAL' else "[!]"
                print(f"  {severity_icon} [{alert['alert_severity']}] {alert['alert_type']}")
                print(f"     {alert['alert_message']}")

        print("=" * 60)

        conn.close()

        return {
            'alerts_triggered': len(alerts),
            'active_alerts': len(active_alerts),
            'summary': summary,
            'alerts': alerts
        }

    except Exception as e:
        logger.error(f"Alerter check failed: {e}")
        raise


if __name__ == '__main__':
    main()
