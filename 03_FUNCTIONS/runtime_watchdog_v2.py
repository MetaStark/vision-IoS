#!/usr/bin/env python3
"""
RUNTIME WATCHDOG DAEMON v2
========================
CEO-DIR-2026-RUNTIME-STABILIZATION-048 - ORDER 4

PURPOSE: Monitor critical daemon heartbeats and auto-restart on SLA breach.

SLA THRESHOLD: 75 minutes

Authority: STIG (EC-003)
Version: 2.0.0 - DEBUG
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor

DAEMON_NAME = 'runtime_watchdog'
SLA_THRESHOLD_MINUTES = 75
WATCH_INTERVAL_SECONDS = 300  # 5 minutes

# Critical daemons to monitor
CRITICAL_DAEMONS = [
    'outcome_settlement_daemon',
    'decision_pack_generator',
    'lvi_calculator',
    'alpha_graph_sync'
]

# Map daemon names to task names (exact match)
TASK_MAPPING = {
    'outcome_settlement_daemon': 'FjordHQ_OutcomeSettlement_Daemon',
    'decision_pack_generator': 'FjordHQ_DecisionPackGenerator',
    'lvi_calculator': 'FjordHQ_LVICalculator',
    'alpha_graph_sync': 'FjordHQ_AlphaGraphSync'
}

logging.basicConfig(
    level=logging.INFO,
    format='[WATCHDOG] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/runtime_watchdog_v2.log'),
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


def check_daemon_health(conn) -> Dict:
    """Check all critical daemon heartbeats."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT daemon_name, status, last_heartbeat,
               NOW() - last_heartbeat AS age_minutes,
               lifecycle_status
        FROM fhq_monitoring.daemon_health
        WHERE daemon_name = ANY(%s)
        ORDER BY daemon_name
    """, (CRITICAL_DAEMONS,))
    return {row['daemon_name']: row for row in cur.fetchall()}


def write_critical_event(conn, daemon_name: str, age_minutes: float):
    """Write CRITICAL event to system_event_log."""
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fhq_monitoring.system_event_log
            (event_type, severity, source_system, event_message, event_timestamp)
            VALUES ('DAEMON_HEARTBEAT_FAILURE', 'CRITICAL', %s,
                    %s::TEXT, NOW())
        """, (daemon_name, f"heartbeat gap {age_minutes:.1f} min exceeds SLA of {SLA_THRESHOLD_MINUTES} min"))
        conn.commit()
        logger.critical(f"Wrote CRITICAL event for {daemon_name}: {age_minutes:.1f} min > SLA")
    except Exception as e:
        logger.error(f"Failed to write CRITICAL event: {e}")


def restart_daemon(daemon_name: str):
    """Attempt to restart daemon via Task Scheduler."""
    task_name = TASK_MAPPING.get(daemon_name)
    logger.info(f"Looking up task for daemon: {daemon_name} -> {task_name}")

    if not task_name:
        logger.warning(f"No Task Scheduler task found for {daemon_name}")
        return False

    try:
        # Try to restart task
        result = os.system(f'schtasks /run /tn "{task_name}"')
        if result == 0:
            logger.info(f"Restarted task: {task_name}")
            return True
        else:
            logger.warning(f"Failed to restart task: {task_name}, exit code: {result}")
            return False
    except Exception as e:
        logger.error(f"Error restarting daemon {daemon_name}: {e}")
        return False


def watch_loop():
    """Main watch loop."""
    cycle_count = 0

    while True:
        try:
            conn = get_connection()
            health = check_daemon_health(conn)

            sla_breaches = []

            for daemon_name in CRITICAL_DAEMONS:
                if daemon_name not in health:
                    logger.warning(f"Daemon {daemon_name} not found in daemon_health")
                    continue

                daemon_status = health[daemon_name]
                age_minutes = daemon_status['age_minutes']

                # Calculate age in minutes
                if hasattr(age_minutes, 'days'):
                    age = age_minutes.days * 24 * 60 + age_minutes.seconds / 60
                else:
                    age = age_minutes.total_seconds() / 60

                if age > SLA_THRESHOLD_MINUTES:
                    logger.critical(f"SLA BREACH: {daemon_name} heartbeat age = {age:.1f} min")
                    write_critical_event(conn, daemon_name, age)

                    # Only attempt restart for daemons with Task Scheduler tasks
                    if daemon_name in TASK_MAPPING.keys():
                        restart_daemon(daemon_name)

                    sla_breaches.append(daemon_name)
                else:
                    logger.info(f"SLA OK: {daemon_name} heartbeat age = {age:.1f} min")

            cycle_count += 1

            if sla_breaches:
                logger.warning(f"Cycle {cycle_count}: {len(sla_breaches)} SLA breaches: {sla_breaches}")
            else:
                logger.info(f"Cycle {cycle_count}: All daemons within SLA")

            conn.close()

        except Exception as e:
            logger.error(f"Watchdog cycle failed: {e}")

        # Wait for next cycle
        logger.info(f"Next cycle in {WATCH_INTERVAL_SECONDS}s")
        time.sleep(WATCH_INTERVAL_SECONDS)


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point."""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    import argparse
    parser = argparse.ArgumentParser(description='Runtime Watch Daemon v2')
    parser.add_argument('--once', action='store_true', help='Run a single watch cycle then exit')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("RUNTIME WATCHDOG DAEMON v2")
    logger.info(f"CEO-DIR-2026-RUNTIME-STABILIZATION-048 - ORDER 4")
    logger.info(f"SLA Threshold: {SLA_THRESHOLD_MINUTES} minutes")
    logger.info(f"Mode: {'single cycle' if args.once else 'continuous daemon'}")
    logger.info(f"Watching: {', '.join(CRITICAL_DAEMONS)}")
    logger.info("=" * 60)

    # Debug: Print task mapping
    logger.info(f"Task mapping: {TASK_MAPPING}")

    if args.once:
        # Single cycle mode - for Task Scheduler
        try:
            conn = get_connection()
            health = check_daemon_health(conn)

            sla_breaches = []

            for daemon_name in CRITICAL_DAEMONS:
                if daemon_name not in health:
                    logger.warning(f"Daemon {daemon_name} not found in daemon_health")
                    continue

                daemon_status = health[daemon_name]
                age_minutes = daemon_status['age_minutes']

                # Calculate age in minutes
                if hasattr(age_minutes, 'days'):
                    age = age_minutes.days * 24 * 60 + age_minutes.seconds / 60
                else:
                    age = age_minutes.total_seconds() / 60

                if age > SLA_THRESHOLD_MINUTES:
                    logger.critical(f"SLA BREACH: {daemon_name} heartbeat age = {age:.1f} min")
                    write_critical_event(conn, daemon_name, age)

                    # Only attempt restart for daemons with Task Scheduler tasks
                    if daemon_name in TASK_MAPPING.keys():
                        restart_daemon(daemon_name)

                    sla_breaches.append(daemon_name)
                else:
                    logger.info(f"SLA OK: {daemon_name} heartbeat age = {age:.1f} min")

            if sla_breaches:
                logger.warning(f"SLA breaches: {len(sla_breaches)} - {sla_breaches}")
            else:
                logger.info(f"All daemons within SLA")

            conn.close()

        except Exception as e:
            logger.error(f"Watchdog cycle failed: {e}")
    else:
        # Continuous daemon mode
        watch_loop()


if __name__ == '__main__':
    main()
