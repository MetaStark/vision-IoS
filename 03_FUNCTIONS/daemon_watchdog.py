#!/usr/bin/env python3
"""
FjordHQ Daemon Watchdog
=======================
CEO-DIR-2026-DAEMON-WATCHDOG
CEO-DIR-2026-DAEMON-HYGIENE-001 (Lifecycle Classification)

Monitors and restarts critical daemons if they crash.
Run this script to keep all daemons alive continuously.

Lifecycle Policy:
- ACTIVE: Managed by watchdog (start/restart/monitor)
- DEPRECATED: Ignored - replaced by newer daemon
- SUSPENDED_BY_DESIGN: Ignored - experiment paused or periodic task
- ORPHANED: ESCALATE - red flag requiring CEO attention
"""

import os
import sys
import time
import subprocess
import psycopg2
from psycopg2.extras import Json
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
    'finn_t_scheduler': {
        'script': '03_FUNCTIONS/finn_t_scheduler.py',
        'max_stale_minutes': 65,  # 60min cycle + 5min buffer
        'process': None,
        'has_heartbeat': True  # Has heartbeat code - CEO-DIR-2026-FINN-T-SCHEDULER-001
    },
    'finn_e_scheduler': {
        'script': '03_FUNCTIONS/finn_e_scheduler.py',
        'max_stale_minutes': 35,  # 30min cycle + 5min buffer
        'process': None,
        'has_heartbeat': True  # Has heartbeat code - CEO-DIR-2026-FINN-E-SCHEDULER-001
    },
    'hypothesis_death_daemon': {
        'script': '03_FUNCTIONS/hypothesis_death_daemon.py',
        'max_stale_minutes': 20,  # 15min cycle + 5min buffer
        'process': None,
        'has_heartbeat': True  # Has heartbeat code - CEO-DIR-2026-HYPOTHESIS-DEATH-001
    },
    'tier1_execution_daemon': {
        'script': '03_FUNCTIONS/tier1_execution_daemon.py',
        'max_stale_minutes': 35,  # 30min cycle + 5min buffer
        'process': None,
        'has_heartbeat': True  # Has heartbeat code - CEO-DIR-2026-TIER1-EXECUTION-001
    },
    'economic_outcome_daemon': {
        'script': '03_FUNCTIONS/economic_outcome_daemon.py',
        'max_stale_minutes': 10,
        'process': None,
        'has_heartbeat': False  # Uses agent_heartbeats (CEIO) - complex table, just check process
    },
    # SUSPENDED_BY_DESIGN: g2c_continuous_forecast_engine - Integrated into FINN schedulers
    # SUSPENDED_BY_DESIGN: ios003b_intraday_regime_delta - On-demand, not continuous
    'pre_tier_scoring_daemon': {
        'script': '03_FUNCTIONS/pre_tier_scoring_daemon.py',
        'max_stale_minutes': 10,  # 5min cycle + 5min buffer
        'process': None,
        'has_heartbeat': True  # Has heartbeat code - CEO-DIR-2026-PRE-TIER-SCORING-DAEMON-001
    }
    # SUSPENDED: wave15_autonomous_hunter - Reactivate after G1.5 (2026-02-07)
    # See control_room_alerts for reminder
}

CHECK_INTERVAL_SECONDS = 60  # Check every minute


def update_watchdog_heartbeat():
    """Update watchdog's own heartbeat."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata, lifecycle_status)
                VALUES ('daemon_watchdog', 'HEALTHY', NOW(), %s, 'ACTIVE')
                ON CONFLICT (daemon_name) DO UPDATE SET
                    status = 'HEALTHY',
                    last_heartbeat = NOW(),
                    metadata = %s,
                    lifecycle_status = 'ACTIVE'
            """, (Json({'managed_daemons': len(DAEMONS)}), Json({'managed_daemons': len(DAEMONS)})))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update watchdog heartbeat: {e}")


def check_orphaned_daemons():
    """
    CEO-DIR-2026-DAEMON-HYGIENE-001: Escalate ORPHANED daemons.
    These are red flags requiring CEO attention.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT daemon_name, lifecycle_reason, lifecycle_updated_at
                FROM fhq_monitoring.daemon_health
                WHERE lifecycle_status = 'ORPHANED'
            """)
            orphans = cur.fetchall()

            if orphans:
                logger.warning("=" * 60)
                logger.warning("🚨 ORPHANED DAEMONS DETECTED - CEO ATTENTION REQUIRED")
                for daemon_name, reason, updated_at in orphans:
                    logger.warning(f"  ⚠️  {daemon_name}")
                    logger.warning(f"      Reason: {reason}")
                    logger.warning(f"      Flagged: {updated_at}")
                logger.warning("=" * 60)

                # Log escalation to control_room_alerts
                cur.execute("""
                    INSERT INTO fhq_monitoring.control_room_alerts
                        (alert_type, severity, title, message, source_daemon, acknowledged)
                    VALUES ('DAEMON_ORPHAN', 'WARNING', 'Orphaned Daemon Detected',
                            %s, 'daemon_watchdog', false)
                    ON CONFLICT DO NOTHING
                """, (f"{len(orphans)} orphaned daemon(s) require CEO disposition: {', '.join([o[0] for o in orphans])}",))
                conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to check orphaned daemons: {e}")


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
    logger.info("FjordHQ Daemon Watchdog - VERSION 3.0 (LIFECYCLE-AWARE)")
    logger.info("CEO-DIR-2026-DAEMON-HYGIENE-001")
    logger.info(f"Monitoring {len(DAEMONS)} ACTIVE daemons")
    logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS} seconds")
    logger.info("-" * 60)
    logger.info("Lifecycle Policy:")
    logger.info("  ACTIVE: Managed | DEPRECATED/SUSPENDED: Ignored | ORPHANED: Escalate")
    logger.info("-" * 60)
    for name, cfg in DAEMONS.items():
        logger.info(f"  [ACTIVE] {name}")
    logger.info("=" * 60)

    # Check for orphaned daemons at startup
    check_orphaned_daemons()

    # Initial startup of all daemons
    for daemon_name in DAEMONS:
        start_daemon(daemon_name)

    # Main monitoring loop
    orphan_check_counter = 0
    while True:
        try:
            update_watchdog_heartbeat()
            check_and_restart_daemons()

            # Check for orphaned daemons every 10 cycles (10 minutes)
            orphan_check_counter += 1
            if orphan_check_counter >= 10:
                check_orphaned_daemons()
                orphan_check_counter = 0

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
