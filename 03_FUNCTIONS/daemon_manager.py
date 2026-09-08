#!/usr/bin/env python3
"""
FjordHQ Daemon Manager
======================
CEO-DIR-2026-DAEMON-MANAGEMENT

Central management for all critical system daemons.
Provides start, stop, status, and restart functionality.
"""

import os
import sys
import subprocess
import psycopg2
from datetime import datetime, timezone
import argparse

# Set working directory
os.chdir('C:/fhq-market-system/vision-ios')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Critical daemons per runbook
CRITICAL_DAEMONS = {
    'finn_brain_scheduler': {
        'script': '03_FUNCTIONS/finn_brain_scheduler.py',
        'log': 'logs/finn_brain_daemon.log',
        'interval': '30 min',
        'description': 'FINN Cognitive Brain - hypothesis generation'
    },
    'finn_crypto_scheduler': {
        'script': '03_FUNCTIONS/finn_crypto_scheduler.py',
        'log': 'logs/finn_crypto_daemon.log',
        'interval': '30 min',
        'description': 'FINN Crypto Learning - 24/7 crypto hypothesis generation'
    },
    'economic_outcome_daemon': {
        'script': '03_FUNCTIONS/economic_outcome_daemon.py',
        'log': 'logs/economic_outcome_daemon.log',
        'interval': 'continuous',
        'description': 'Economic event outcome capture'
    },
    'g2c_continuous_forecast_engine': {
        'script': '03_FUNCTIONS/g2c_continuous_forecast_engine.py',
        'log': 'logs/g2c_forecast_daemon.log',
        'interval': 'continuous',
        'description': 'G2C macro forecast generation'
    },
    'ios003b_intraday_regime_delta': {
        'script': '03_FUNCTIONS/ios003b_intraday_regime_delta.py',
        'log': 'logs/ios003b_regime_daemon.log',
        'interval': '15 min',
        'description': 'Intraday regime detection'
    }
}


def get_daemon_status_from_db():
    """Get daemon heartbeat status from database (unified from both tables)."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        results = {}

        with conn.cursor() as cur:
            # Check fhq_monitoring.daemon_health
            cur.execute("""
                SELECT
                    daemon_name,
                    status,
                    last_heartbeat,
                    EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60 as minutes_ago
                FROM fhq_monitoring.daemon_health
                WHERE daemon_name IN %s
                ORDER BY daemon_name
            """, (tuple(CRITICAL_DAEMONS.keys()),))
            for row in cur.fetchall():
                results[row[0]] = {
                    'status': row[1],
                    'last_heartbeat': row[2],
                    'minutes_ago': float(row[3]) if row[3] else None,
                    'source': 'daemon_health'
                }

            # Also check fhq_governance.agent_heartbeats for daemons that write there
            # economic_outcome_daemon writes as 'CEIO'
            cur.execute("""
                SELECT
                    agent_id,
                    'HEALTHY' as status,
                    last_heartbeat,
                    EXTRACT(EPOCH FROM (NOW() - last_heartbeat))/60 as minutes_ago
                FROM fhq_governance.agent_heartbeats
                WHERE agent_id IN ('CEIO', 'G2C_FORECAST', 'IOS003B')
                ORDER BY last_heartbeat DESC
            """)
            agent_map = {'CEIO': 'economic_outcome_daemon', 'G2C_FORECAST': 'g2c_continuous_forecast_engine', 'IOS003B': 'ios003b_intraday_regime_delta'}
            for row in cur.fetchall():
                daemon_name = agent_map.get(row[0], row[0])
                if daemon_name in CRITICAL_DAEMONS:
                    # Use fresher heartbeat if available
                    existing = results.get(daemon_name)
                    new_minutes = float(row[3]) if row[3] else None
                    if not existing or (new_minutes and (existing.get('minutes_ago') is None or new_minutes < existing['minutes_ago'])):
                        results[daemon_name] = {
                            'status': row[1],
                            'last_heartbeat': row[2],
                            'minutes_ago': new_minutes,
                            'source': 'agent_heartbeats'
                        }

        conn.close()
        return results
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return {}


def get_health_assessment(minutes_ago):
    """Assess daemon health based on heartbeat age."""
    if minutes_ago is None:
        return 'UNKNOWN'
    if minutes_ago < 10:
        return 'FRESH'
    if minutes_ago < 60:
        return 'OK'
    if minutes_ago < 360:
        return 'STALE'
    return 'DEAD'


def print_status():
    """Print status of all critical daemons."""
    print("=" * 70)
    print("FjordHQ Critical Daemon Status")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    db_status = get_daemon_status_from_db()

    for daemon_name, config in CRITICAL_DAEMONS.items():
        db_info = db_status.get(daemon_name, {})
        minutes_ago = db_info.get('minutes_ago')
        health = get_health_assessment(minutes_ago)

        # Health indicator
        if health == 'FRESH':
            indicator = '[OK]'
        elif health == 'OK':
            indicator = '[OK]'
        elif health == 'STALE':
            indicator = '[!!]'
        else:
            indicator = '[XX]'

        minutes_str = f"{minutes_ago:.1f} min ago" if minutes_ago else "NO HEARTBEAT"

        print(f"\n{indicator} {daemon_name}")
        print(f"    Description: {config['description']}")
        print(f"    Interval: {config['interval']}")
        print(f"    Heartbeat: {minutes_str} ({health})")
        print(f"    Script: {config['script']}")

    print("\n" + "=" * 70)
    print("Legend: [OK]=Healthy, [!!]=Stale, [XX]=Dead/Unknown")
    print("=" * 70)


def start_daemon(daemon_name):
    """Start a specific daemon."""
    if daemon_name not in CRITICAL_DAEMONS:
        print(f"Unknown daemon: {daemon_name}")
        return False

    config = CRITICAL_DAEMONS[daemon_name]
    script_path = config['script']
    log_path = config['log']

    if not os.path.exists(script_path):
        print(f"Script not found: {script_path}")
        return False

    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    print(f"Starting {daemon_name}...")

    # Use subprocess with CREATE_NEW_CONSOLE on Windows
    if sys.platform == 'win32':
        subprocess.Popen(
            ['python', script_path],
            stdout=open(log_path, 'w'),
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NO_WINDOW
        )
    else:
        subprocess.Popen(
            ['python', script_path],
            stdout=open(log_path, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )

    print(f"  Started. Log: {log_path}")
    return True


def start_all():
    """Start all critical daemons."""
    print("Starting all critical daemons...")
    for daemon_name in CRITICAL_DAEMONS:
        start_daemon(daemon_name)
    print("\nAll daemons started. Use 'status' to check heartbeats.")


def main():
    parser = argparse.ArgumentParser(description='FjordHQ Daemon Manager')
    parser.add_argument('command', choices=['status', 'start', 'start-all'],
                       help='Command to execute')
    parser.add_argument('daemon', nargs='?', help='Daemon name (for start command)')

    args = parser.parse_args()

    if args.command == 'status':
        print_status()
    elif args.command == 'start-all':
        start_all()
    elif args.command == 'start':
        if not args.daemon:
            print("Please specify a daemon name. Available:")
            for name in CRITICAL_DAEMONS:
                print(f"  - {name}")
        else:
            start_daemon(args.daemon)


if __name__ == '__main__':
    main()
