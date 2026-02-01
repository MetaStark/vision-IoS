"""
CEO Gateway Daemon - Telegram Polling Service
CEO-DIR-2026-01-03: Cognitive Digital Intuition Platform
CEO-DIR-2026-01-03-PHASE-B-ACTIVATE: Controlled Activation

This daemon polls the Telegram API for incoming CEO commands
and routes them through the CEOTelegramGateway.

GUARDRAIL A - KILL-SWITCH:
  Set CEO_GATEWAY_ENABLED=0 to immediately disable polling.
  Location: Environment variable (no redeploy required)
  VEGA: This is the kill-switch location.

COGNITIVE FIREWALL (Guardrail B):
  This daemon is OUTSIDE:
    - ACI execution paths
    - Signal generation loops
    - Learning/feedback ingestion
  READ-ONLY OBSERVABILITY ONLY.

Run with: python ceo_gateway_daemon.py
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment from .env file
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ceo_telegram_gateway import CEOTelegramGateway

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("CEO_DAEMON")

# =============================================================================
# GUARDRAIL A: KILL-SWITCH (CEO-DIR-2026-01-03-PHASE-B-ACTIVATE)
# =============================================================================
# Set CEO_GATEWAY_ENABLED=0 to immediately disable all polling.
# No redeploy required. Takes effect on next poll cycle.
# VEGA: This is the documented kill-switch location.

def is_gateway_enabled() -> bool:
    """
    Check if gateway is enabled via environment variable.

    Kill-Switch: Set CEO_GATEWAY_ENABLED=0 to disable.
    Default: Enabled (1) if not set.
    """
    return os.getenv('CEO_GATEWAY_ENABLED', '1') != '0'

# Polling configuration
POLL_INTERVAL = 2  # seconds between polls
TELEGRAM_TIMEOUT = 30  # long polling timeout


class CEOGatewayDaemon:
    """
    Persistent daemon for CEO Telegram gateway.

    Polls Telegram API for updates and handles CEO commands.
    """

    def __init__(self):
        """Initialize daemon with gateway."""
        self.gateway = CEOTelegramGateway()
        self.last_update_id = 0
        self.running = False

        # Verify bot token
        if not self.gateway.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    def run(self):
        """Run the daemon loop."""
        # Check kill-switch before starting
        if not is_gateway_enabled():
            logger.warning("=" * 60)
            logger.warning("CEO GATEWAY DISABLED (CEO_GATEWAY_ENABLED=0)")
            logger.warning("Kill-switch is active. Set CEO_GATEWAY_ENABLED=1 to enable.")
            logger.warning("=" * 60)
            return

        self.running = True
        logger.info("=" * 60)
        logger.info("CEO GATEWAY DAEMON STARTING")
        logger.info("CEO-DIR-2026-01-03-PHASE-B-ACTIVATE: Controlled Activation")
        logger.info("=" * 60)
        logger.info(f"Mode: POLLING (interval: {POLL_INTERVAL}s)")
        logger.info(f"Commands: {len(self.gateway.VALID_COMMANDS)} total")
        logger.info(f"  Phase A: 9 current state commands")
        logger.info(f"  Phase B: 5 temporal context commands")
        logger.info("Kill-Switch: CEO_GATEWAY_ENABLED=0 to disable")
        logger.info("Press Ctrl+C to stop")
        logger.info("-" * 60)

        try:
            while self.running:
                # Check kill-switch on each cycle (Guardrail A)
                if not is_gateway_enabled():
                    logger.warning("Kill-switch activated (CEO_GATEWAY_ENABLED=0)")
                    logger.warning("Daemon stopping gracefully...")
                    break

                self._poll_once()
                time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.running = False
            logger.info("CEO Gateway Daemon stopped")

    def _poll_once(self):
        """Poll Telegram once for updates."""
        try:
            updates = self.gateway.get_updates(offset=self.last_update_id + 1)

            for update in updates:
                update_id = update.get('update_id', 0)

                # Handle message
                if 'message' in update:
                    self._handle_update(update)

                # Track last update ID
                if update_id > self.last_update_id:
                    self.last_update_id = update_id

        except Exception as e:
            logger.error(f"Poll error: {e}")

    def _handle_update(self, update: dict):
        """Handle a single Telegram update."""
        message = update.get('message', {})
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '')
        from_user = message.get('from', {})
        username = from_user.get('username', 'unknown')

        if not text:
            return

        # Parse command
        command, args = self.gateway.parse_command(text)
        if not command:
            return

        logger.info(f"Received {command} from @{username} (chat_id: {chat_id})")

        # Process through gateway
        self.gateway.handle_message(update)

        logger.info(f"Processed {command}")


def main():
    """Run the CEO Gateway Daemon."""
    try:
        daemon = CEOGatewayDaemon()
        daemon.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Set TELEGRAM_BOT_TOKEN environment variable to enable Telegram polling")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Daemon error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
