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


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def run_sync():
    """Run a single sync cycle using CEO-DIR-007 validated function."""
    conn = get_connection()
    try:
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

            return {
                'sync': dict(result),
                'prior': dict(prior_result)
            }

    except Exception as e:
        logger.error(f"Sync failed: {e}")
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
