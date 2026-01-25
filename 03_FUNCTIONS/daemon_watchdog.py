#!/usr/bin/env python3
"""
FjordHQ Daemon Watchdog
=======================
CEO-DIR-2026-DAEMON-WATCHDOG

Monitors and restarts critical daemons if they crash.
Run this script to keep all daemons alive continuously.
"""

import os
import sys
import time
import subprocess
import psycopg2
import logging
from datetime import datetime, timezone

# Set working directory
os.chdir('C:/fhq-market-system/vision-ios')

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[WATCHDOG] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/daemon_watchdog.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Critical daemons to monitor
# has_heartbeat: True = check DB heartbeat, False = only check process alive
DAEMONS = {
    'finn_brain_scheduler': {
        'script': '03_FUNCTIONS/finn_brain_scheduler.py',
        'max_stale_minutes': 35,  # 30min cycle + 5min buffer
        'process': None,
        'has_heartbeat': True  # Has heartbeat code
    },
    'finn_crypto_scheduler': {
        'script': '03_FUNCTIONS/finn_crypto_scheduler.py',
        'max_stale_minutes': 35,
        'process': None,
        'has_heartbeat': True  # Has heartbeat code
    },
    'economic_outcome_daemon': {
        'script': '03_FUNCTIONS/economic_outcome_daemon.py',
        'max_stale_minutes': 10,
        'process': None,
        'has_heartbeat': False  # Uses agent_heartbeats (CEIO) - complex table, just check process
    },
    'g2c_continuous_forecast_engine': {
        'script': '03_FUNCTIONS/g2c_continuous_forecast_engine.py',
        'max_stale_minutes': 15,
        'process': None,
        'has_heartbeat': False  # NO heartbeat code - only check process
    },
    'ios003b_intraday_regime_delta': {
        'script': '03_FUNCTIONS/ios003b_intraday_regime_delta.py',
        'max_stale_minutes': 20,  # 15min cycle + buffer
        'process': None,
        'has_heartbeat': False  # NO heartbeat code - only check process
    }
}

CHECK_INTERVAL_SECONDS = 60  # Check every minute


def update_watchdog_heartbeat():
    """Update watchdog's own heartbeat."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
                VALUES ('daemon_watchdog', 'HEALTHY', NOW(), '{"managed_daemons": 5}'::jsonb)
                ON CONFLICT (daemon_name) DO UPDATE SET
                    status = 'HEALTHY',
                    last_heartbeat = NOW(),
                    metadata = '{"managed_daemons": 5}'::jsonb
            """)
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update watchdog heartbeat: {e}")


def check_daemon_heartbeat(daemon_name):
    """Check if daemon heartbeat is fresh."""
    config = DAEMONS[daemon_name]
    max_stale = config['max_stale_minutes']

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Check daemon_health table
            cur.execute("""
                SELECT EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60 as minutes_ago
                FROM fhq_monitoring.daemon_health
                WHERE daemon_name = %s
            """, (daemon_name,))
            row = cur.fetchone()

            if row and row[0] is not None:
                conn.close()
                return row[0] < max_stale

            # Also check agent_heartbeats for economic_outcome_daemon
            if config.get('heartbeat_table') == 'agent_heartbeats':
                cur.execute("""
                    SELECT EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60 as minutes_ago
                    FROM fhq_governance.agent_heartbeats
                    WHERE agent_id = %s
                """, (config.get('heartbeat_id'),))
                row = cur.fetchone()
                conn.close()
                if row and row[0] is not None:
                    return row[0] < max_stale

            conn.close()
        return False  # No heartbeat found
    except Exception as e:
        logger.error(f"Error checking heartbeat for {daemon_name}: {e}")
        return False


def start_daemon(daemon_name):
    """Start a daemon process."""
    config = DAEMONS[daemon_name]
    script = config['script']

    logger.info(f"Starting {daemon_name}...")

    try:
        # Start process with subprocess
        process = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd='C:/fhq-market-system/vision-ios',
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        config['process'] = process
        logger.info(f"  Started {daemon_name} (PID: {process.pid})")
        return True
    except Exception as e:
        logger.error(f"  Failed to start {daemon_name}: {e}")
        return False


def check_and_restart_daemons():
    """Check all daemons and restart if needed."""
    for daemon_name, config in DAEMONS.items():
        process = config.get('process')

        # Check if process is running
        process_alive = process is not None and process.poll() is None

        # Determine if we need to restart
        needs_restart = False
        reason = ""

        if not process_alive:
            needs_restart = True
            reason = "process dead"
        elif config.get('has_heartbeat', False):
            # Only check heartbeat for daemons that have heartbeat code
            heartbeat_fresh = check_daemon_heartbeat(daemon_name)
            if not heartbeat_fresh:
                needs_restart = True
                reason = "stale heartbeat"

        if needs_restart:
            logger.warning(f"{daemon_name}: {reason} - restarting...")

            # Kill existing process if any
            if process_alive:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    process.kill()

            # Start new process
            start_daemon(daemon_name)
        else:
            logger.debug(f"{daemon_name}: OK")


def main():
    logger.info("=" * 60)
    logger.info("FjordHQ Daemon Watchdog Starting - VERSION 2.0 (FIXED)")
    logger.info(f"Monitoring {len(DAEMONS)} daemons")
    logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")
    # Debug: log heartbeat settings
    for name, cfg in DAEMONS.items():
        logger.info(f"  {name}: has_heartbeat={cfg.get('has_heartbeat', 'NOT SET')}")
    logger.info("=" * 60)

    # Initial startup of all daemons
    for daemon_name in DAEMONS:
        start_daemon(daemon_name)

    # Main monitoring loop
    while True:
        try:
            update_watchdog_heartbeat()
            check_and_restart_daemons()
            time.sleep(CHECK_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Watchdog shutdown requested")
            break
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
            time.sleep(10)

    # Cleanup - terminate all managed processes
    logger.info("Shutting down managed daemons...")
    for daemon_name, config in DAEMONS.items():
        process = config.get('process')
        if process and process.poll() is None:
            process.terminate()
            logger.info(f"  Terminated {daemon_name}")

    logger.info("Watchdog shutdown complete")


if __name__ == '__main__':
    main()
