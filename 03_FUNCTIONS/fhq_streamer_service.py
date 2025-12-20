#!/usr/bin/env python3
"""
FHQ MARKET STREAMER - WINDOWS SERVICE
======================================
CEO Directive: ARO-20251209/AUTONOMY_ENFORCEMENT_V2
Platform: Windows (win32)
Equivalent: systemd fhq-streamer.service

This module wraps market_streamer_v2.py as a Windows Service
with automatic restart, watchdog, and health monitoring.

Installation:
    python fhq_streamer_service.py install
    python fhq_streamer_service.py start

Or via NSSM:
    nssm install FHQ-Streamer python.exe C:\fhq-market-system\vision-ios\03_FUNCTIONS\market_streamer_v2.py
    nssm set FHQ-Streamer AppDirectory C:\fhq-market-system\vision-ios
    nssm set FHQ-Streamer AppRestartDelay 3000
    nssm start FHQ-Streamer
"""

import os
import sys
import time
import signal
import logging
import threading
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
LOG_DIR = Path("C:/fhq-market-system/vision-ios/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "fhq_streamer_service.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FHQ_STREAMER_SERVICE")

# Service configuration
SERVICE_NAME = "FHQ-Streamer"
SERVICE_DISPLAY = "FHQ Market Streamer (Canonical Ingestion)"
SERVICE_DESC = "Persistent market data ingestion service - CEO Directive ARO-20251209"

# Watchdog configuration
WATCHDOG_INTERVAL = 10  # seconds
MAX_HEARTBEAT_AGE = 60  # seconds before restart

# Environment sealing
REQUIRED_ENV = {
    'FHQ_ENV': 'PRODUCTION',
    'FHQ_LLM_PROVIDER': 'speciale',
    'FHQ_LLM_MODEL': 'deepseek-reasoner',
}


class StreamerWatchdog:
    """
    Watchdog supervisor for market_streamer_v2.py
    Monitors health and restarts on failure.
    """

    def __init__(self):
        self.process = None
        self.running = False
        self.restart_count = 0
        self.last_heartbeat = None
        self.streamer_path = Path(__file__).parent / "market_streamer_v2.py"

    def validate_environment(self) -> bool:
        """Validate required environment variables."""
        missing = []
        for key, expected in REQUIRED_ENV.items():
            actual = os.environ.get(key)
            if actual is None:
                logger.warning(f"ENV {key} not set (expected: {expected})")
                missing.append(key)
            elif actual != expected:
                logger.warning(f"ENV {key}={actual} (expected: {expected})")

        if missing:
            logger.warning(f"Missing environment variables: {missing}")
            # Don't abort - ingestion must continue even without LLM config
            return True  # Changed per CEO: "eyes must stay open even if brain blinks"

        return True

    def start_streamer(self):
        """Start the market streamer subprocess."""
        if self.process and self.process.poll() is None:
            logger.info("Streamer already running")
            return

        logger.info(f"Starting streamer: {self.streamer_path}")

        try:
            self.process = subprocess.Popen(
                [sys.executable, str(self.streamer_path)],
                cwd=str(self.streamer_path.parent.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            self.last_heartbeat = datetime.now(timezone.utc)
            logger.info(f"Streamer started with PID {self.process.pid}")

        except Exception as e:
            logger.error(f"Failed to start streamer: {e}")

    def check_health(self) -> bool:
        """Check streamer health via database heartbeat."""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=os.environ.get('PGHOST', '127.0.0.1'),
                port=int(os.environ.get('PGPORT', 54322)),
                database=os.environ.get('PGDATABASE', 'postgres'),
                user=os.environ.get('PGUSER', 'postgres'),
                password=os.environ.get('PGPASSWORD', 'postgres')
            )
            cur = conn.cursor()

            # Check latest heartbeat from system_events
            cur.execute("""
                SELECT MAX(created_at)
                FROM fhq_governance.system_events
                WHERE event_type = 'STREAMER_HEARTBEAT'
            """)
            row = cur.fetchone()

            if row and row[0]:
                heartbeat_age = (datetime.now(timezone.utc) - row[0].replace(tzinfo=timezone.utc)).total_seconds()
                if heartbeat_age < MAX_HEARTBEAT_AGE:
                    self.last_heartbeat = row[0]
                    return True
                else:
                    logger.warning(f"Heartbeat stale: {heartbeat_age:.0f}s old")
                    return False

            cur.close()
            conn.close()

        except Exception as e:
            logger.error(f"Health check failed: {e}")

        return False

    def restart_streamer(self):
        """Kill and restart the streamer."""
        self.restart_count += 1
        logger.warning(f"Restarting streamer (attempt #{self.restart_count})")

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()

        time.sleep(3)  # RestartSec=3 equivalent
        self.start_streamer()

    def run(self):
        """Main watchdog loop."""
        logger.info("=" * 60)
        logger.info("FHQ STREAMER WATCHDOG SERVICE STARTING")
        logger.info(f"Platform: {sys.platform}")
        logger.info(f"Watchdog Interval: {WATCHDOG_INTERVAL}s")
        logger.info(f"Max Heartbeat Age: {MAX_HEARTBEAT_AGE}s")
        logger.info("=" * 60)

        # Validate environment
        self.validate_environment()

        # Start streamer
        self.running = True
        self.start_streamer()

        # Watchdog loop
        while self.running:
            time.sleep(WATCHDOG_INTERVAL)

            # Check if process is alive
            if self.process is None or self.process.poll() is not None:
                logger.error("Streamer process died - restarting")
                self.restart_streamer()
                continue

            # Check health via heartbeat
            if not self.check_health():
                logger.warning("Health check failed - restarting")
                self.restart_streamer()

        logger.info("Watchdog stopping")
        if self.process:
            self.process.terminate()

    def stop(self):
        """Stop the watchdog and streamer."""
        self.running = False


def install_as_task():
    """Install as Windows Scheduled Task (alternative to service)."""
    import subprocess

    script_path = Path(__file__).resolve()
    python_path = sys.executable

    # Create scheduled task that runs at startup and restarts on failure
    cmd = f'''schtasks /create /tn "FHQ-Streamer" /tr "'{python_path}' '{script_path}' run" /sc onstart /ru SYSTEM /rl HIGHEST /f'''

    print(f"Installing scheduled task...")
    print(f"Command: {cmd}")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print("Task installed successfully")
    else:
        print(f"Failed: {result.stderr}")


def run_service():
    """Run the watchdog service."""
    watchdog = StreamerWatchdog()

    # Handle graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum} - stopping")
        watchdog.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    watchdog.run()


def main():
    if len(sys.argv) < 2:
        print("Usage: fhq_streamer_service.py [install|run|status]")
        print("  install - Install as Windows Scheduled Task")
        print("  run     - Run the watchdog service")
        print("  status  - Check service status")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'install':
        install_as_task()
    elif command == 'run':
        run_service()
    elif command == 'status':
        # Check status
        watchdog = StreamerWatchdog()
        healthy = watchdog.check_health()
        print(f"Streamer Health: {'HEALTHY' if healthy else 'UNHEALTHY'}")
        print(f"Last Heartbeat: {watchdog.last_heartbeat}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
