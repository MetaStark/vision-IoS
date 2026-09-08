#!/usr/bin/env python3
"""
ALPHA GRAPH SYNC SCHEDULER
==========================

Continuous sync daemon for alpha_graph_nodes.
Runs every 5 minutes via Windows Task Scheduler or cron.

Usage:
    python alpha_graph_sync_scheduler.py --once     # Single run
    python alpha_graph_sync_scheduler.py --daemon   # Continuous (5 min interval)

CEO-DIR-006 Compliance:
- Logs every run to job_runs
- Updates daemon heartbeat
- Tracks lag metrics
"""

import os
import sys
import time
import logging
import json
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[ALPHA-SYNC] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('03_FUNCTIONS/alpha_graph_sync_scheduler.log')
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

SYNC_INTERVAL_SECONDS = 300  # 5 minutes
LOOKBACK_HOURS = 2

DAEMON_NAME = 'alpha_graph_sync'


def heartbeat(conn, status: str, details: dict = None):
    """Write heartbeat to daemon_health table (Heartbeat Contract)."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (daemon_name)
                DO UPDATE SET status = EXCLUDED.status,
                              last_heartbeat = NOW(),
                              metadata = EXCLUDED.metadata,
                              updated_at = NOW()
            """, (DAEMON_NAME, status, json.dumps(details) if details else None))
            conn.commit()
            logger.debug(f"Heartbeat: {DAEMON_NAME} -> {status}")
    except Exception as e:
        logger.error(f"Heartbeat failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def write_critical_event(conn, event_type: str, message: str, severity: str = 'CRITICAL', metadata: dict = None):
    """Write CRITICAL event to system_event_log (Heartbeat Contract)."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.system_event_log
                (event_type, severity, source_system, event_message, event_timestamp, metadata)
                VALUES (%s, %s, %s, %s, NOW(), %s)
            """, (event_type, severity, DAEMON_NAME, message, json.dumps(metadata) if metadata else None))
            conn.commit()
            logger.critical(f"Event written: {event_type} - {message}")
    except Exception as e:
        logger.error(f"Failed to write CRITICAL event: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def run_sync():
    """Run a single sync cycle using CEO-DIR-007 validated function."""
    conn = get_connection()
    result = None
    prior_result = None

    try:
        # Heartbeat: Cycle start (Heartbeat Contract)
        heartbeat(conn, 'HEALTHY', {'status': 'cycle_start'})

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Run the VALIDATED sync function (CEO-DIR-007)
            # Uses 10-minute window for realtime sync
            cur.execute("SELECT * FROM fhq_learning.fn_sync_alpha_graph_validated(10)")
            result = cur.fetchone()
            conn.commit()

            status_msg = f"Sync complete: run_id={result['run_id']}, inserted={result['inserted_count']}, status={result['status']}"
            if result['error_message']:
                status_msg += f", error={result['error_message']}"
            logger.info(status_msg)

            # Run DAILY prior adjustment (CEO-DIR-007: only once per day)
            cur.execute("SELECT * FROM fhq_learning.fn_auto_adjust_priors_daily()")
            prior_result = cur.fetchone()
            conn.commit()

            prior_msg = f"Prior adjustment: run_id={prior_result['run_id']}, adjusted={prior_result['adjusted_count']}, status={prior_result['status']}"
            if prior_result['skipped_reason']:
                prior_msg += f" (skipped: {prior_result['skipped_reason']})"
            logger.info(prior_msg)

            # Heartbeat: Cycle complete (Heartbeat Contract)
            heartbeat(conn, 'HEALTHY', {
                'status': 'cycle_complete',
                'sync_run_id': result['run_id'],
                'inserted_count': result['inserted_count'],
                'prior_adjusted': prior_result['adjusted_count']
            })

            return {
                'sync': dict(result),
                'prior': dict(prior_result)
            }

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        write_critical_event(conn, 'ALPHA_GRAPH_SYNC_FAILURE', str(e), 'CRITICAL', {
            'error_type': type(e).__name__,
            'sync_run_id': result['run_id'] if result else None
        })
        # Heartbeat: Degraded on failure (Heartbeat Contract)
        try:
            heartbeat(conn, 'DEGRADED', {'status': 'failed', 'error': str(e)})
        except Exception:
            pass
        conn.rollback()
        raise
    finally:
        conn.close()


def run_once():
    """Run sync once and exit."""
    logger.info("Running single sync cycle")
    result = run_sync()
    print(f"Sync: {result['sync']['status']}, inserted={result['sync']['inserted_count']}")
    print(f"Prior: {result['prior']['status']}, adjusted={result['prior']['adjusted_count']}")
    return result


def run_daemon():
    """Run as continuous daemon."""
    logger.info(f"Starting daemon with {SYNC_INTERVAL_SECONDS}s interval")

    while True:
        try:
            run_sync()
        except Exception as e:
            logger.error(f"Cycle failed: {e}")

        logger.info(f"Sleeping {SYNC_INTERVAL_SECONDS}s until next cycle")
        time.sleep(SYNC_INTERVAL_SECONDS)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Alpha Graph Sync Scheduler')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--daemon', action='store_true', help='Run as continuous daemon')
    args = parser.parse_args()

    if args.daemon:
        run_daemon()
    else:
        run_once()


if __name__ == '__main__':
    main()
