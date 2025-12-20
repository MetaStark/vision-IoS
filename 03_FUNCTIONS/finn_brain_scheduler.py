#!/usr/bin/env python3
"""
FINN COGNITIVE BRAIN SCHEDULER
==============================
CEO Directive: Activate FINN Brain every 30 minutes for learning.
CEO Directive (2025-12-17) Mandate III: DEFCON Deterministic Gating.

Authority: ADR-020 (ACI), ADR-016 (DEFCON), CD-IOS015-ALPACA-PAPER-001
Classification: G4_PRODUCTION_SCHEDULER
"""

import os
import sys
import json
import time
import signal
import logging
import psycopg2
from datetime import datetime, timezone
from decimal import Decimal
from typing import Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finn_cognitive_brain import FINNCognitiveBrain


# =============================================================================
# CEO DIRECTIVE MANDATE III: DEFCON Deterministic Gating (ADR-016)
# =============================================================================
# "Daemon Scheduler must have explicit Hard Gates linked to DEFCON state."
#
# DEFCON Behavior Matrix (Proscriptive, not Descriptive):
# | DEFCON | Research Cycles | Running Processes | Learning Updates |
# |--------|-----------------|-------------------|------------------|
# | GREEN  | ALLOWED         | ALLOWED           | STAGING ONLY     |
# | YELLOW | ALLOWED (reduced)| ALLOWED          | STAGING ONLY     |
# | ORANGE | **BLOCKED**     | ALLOWED (no new)  | **BLOCKED**      |
# | RED    | **BLOCKED**     | **KILLED**        | **BLOCKED**      |
# | BLACK  | **BLOCKED**     | **KILLED**        | **BLOCKED**      |
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def defcon_gate_check() -> Tuple[bool, str, str]:
    """
    DEFCON Hard Gate Check - MUST be called BEFORE any cycle starts.

    Per CEO Directive Mandate III (2025-12-17):
    - RED/BLACK: Kill running processes, block all cycles
    - ORANGE: Block new cycles (allow existing to complete)
    - YELLOW: Allow with reduced frequency
    - GREEN: Full operation

    CRITICAL: This gate is ABOVE agent will. No agent code path can bypass it.
    The check happens at the scheduler level, before FINNCognitiveBrain is invoked.

    Returns: (can_proceed, reason, defcon_level)
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Query the actual defcon_state table with correct schema
            cur.execute("""
                SELECT defcon_level FROM fhq_governance.defcon_state
                WHERE is_current = true
                ORDER BY triggered_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            level = row[0] if row else 'GREEN'
        conn.close()
    except Exception as e:
        # MANDATE III FAIL-SAFE: If we can't check DEFCON, block operations
        # This is the conservative choice - unknown state = assume danger
        logging.critical(f"DEFCON check failed - BLOCKING ALL OPERATIONS: {e}")
        return (False, f"DEFCON CHECK FAILURE: {e} - Operations blocked for safety", "UNKNOWN")

    if level in ('RED', 'BLACK'):
        return (False, f"DEFCON {level}: ALL PROCESSES MUST TERMINATE", level)

    if level == 'ORANGE':
        return (False, f"DEFCON ORANGE: NEW CYCLES BLOCKED", level)

    if level == 'YELLOW':
        return (True, f"DEFCON YELLOW: Proceed with caution", level)

    return (True, f"DEFCON {level}: Full operation permitted", level)

logging.basicConfig(
    level=logging.INFO,
    format='[FINN-SCHEDULER] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('C:/fhq-market-system/vision-ios/logs/finn_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
INTERVAL_MINUTES = 30
DAILY_BUDGET_USD = Decimal('10.00')
MAX_CYCLES_PER_DAY = 48  # 30 min intervals = 48 per day

class FINNScheduler:
    """
    Scheduler for FINN Cognitive Brain.
    Runs cognitive cycles every 30 minutes.
    """

    def __init__(self):
        self.brain = None
        self.shutdown_requested = False
        self.cycles_today = 0
        self.last_reset_date = None

    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        def handler(signum, frame):
            logger.info(f"Shutdown signal received ({signum})")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def reset_daily_counter(self):
        """Reset cycle counter at midnight."""
        today = datetime.now(timezone.utc).date()
        if self.last_reset_date != today:
            self.cycles_today = 0
            self.last_reset_date = today
            logger.info(f"Daily counter reset for {today}")

    def run_cycle(self) -> dict:
        """Run a single cognitive cycle."""
        if self.brain is None:
            self.brain = FINNCognitiveBrain(daily_budget_usd=DAILY_BUDGET_USD)
            self.brain.connect()
            logger.info("FINN Brain initialized")

        results = self.brain.run_cognitive_cycle()
        self.cycles_today += 1

        return results

    def log_results(self, results: dict):
        """Log cycle results."""
        logger.info("=" * 60)
        logger.info(f"CYCLE {results['cycle']} COMPLETE")
        logger.info(f"  Timestamp: {results['timestamp']}")
        logger.info(f"  Strategy: {results['strategy_used']}")
        logger.info(f"  Signals: {len(results['signals'])}")
        logger.info(f"  Validated: {len(results['validated'])}")
        logger.info(f"  Executed: {len(results['executed'])}")
        logger.info(f"  Exits: {len(results['exits_triggered'])}")
        logger.info(f"  Learning Updates: {results['learning_updates']}")

        if results.get('capital'):
            logger.info(f"  Capital: ${results['capital']:,.2f}")

        if results.get('context'):
            ctx = results['context']
            logger.info(f"  Context: regime={ctx.get('regime')}, session={ctx.get('session')}")

        logger.info(f"  Duration: {results['duration_sec']:.1f}s")
        logger.info("=" * 60)

        # Save results to file
        results_file = f"C:/fhq-market-system/vision-ios/logs/finn_cycle_{results['cycle']}.json"
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Could not save results: {e}")

    def run(self):
        """Run the scheduler continuously."""
        logger.info("=" * 70)
        logger.info("FINN COGNITIVE BRAIN SCHEDULER ACTIVATED")
        logger.info(f"  Interval: {INTERVAL_MINUTES} minutes")
        logger.info(f"  Daily Budget: ${DAILY_BUDGET_USD}")
        logger.info(f"  Max Cycles/Day: {MAX_CYCLES_PER_DAY}")
        logger.info("=" * 70)

        self.setup_signal_handlers()

        while not self.shutdown_requested:
            try:
                self.reset_daily_counter()

                # =========================================================
                # MANDATE III: DEFCON Hard Gate - CHECKED BEFORE EVERY CYCLE
                # =========================================================
                can_proceed, reason, defcon_level = defcon_gate_check()

                if defcon_level in ('RED', 'BLACK'):
                    # CRITICAL: Terminate immediately
                    logger.critical(f"DEFCON {defcon_level} - IMMEDIATE TERMINATION REQUIRED")
                    logger.critical(reason)
                    self.shutdown_requested = True
                    break

                if not can_proceed:
                    # ORANGE: Block new cycles but don't terminate
                    logger.warning(reason)
                    time.sleep(60)  # Check again in 1 minute
                    continue

                if defcon_level == 'YELLOW':
                    logger.warning(f"DEFCON YELLOW: Operating with increased caution")

                # Check daily limit
                if self.cycles_today >= MAX_CYCLES_PER_DAY:
                    logger.warning(f"Daily cycle limit reached ({MAX_CYCLES_PER_DAY})")
                    time.sleep(60)  # Check again in 1 minute
                    continue

                # Run cognitive cycle
                logger.info(f"Starting cycle (#{self.cycles_today + 1} today, DEFCON: {defcon_level})...")
                results = self.run_cycle()
                self.log_results(results)

                # Wait for next interval
                if not self.shutdown_requested:
                    logger.info(f"Next cycle in {INTERVAL_MINUTES} minutes...")
                    for _ in range(INTERVAL_MINUTES * 60):
                        if self.shutdown_requested:
                            break
                        time.sleep(1)

            except Exception as e:
                logger.error(f"Cycle error: {e}")
                import traceback
                traceback.print_exc()
                # Wait before retry
                time.sleep(60)

        # Cleanup
        if self.brain:
            self.brain.close()
        logger.info("FINN Scheduler shutdown complete")


def run_single_test():
    """Run a single test cycle."""
    logger.info("Running single test cycle...")
    scheduler = FINNScheduler()
    results = scheduler.run_cycle()
    scheduler.log_results(results)
    if scheduler.brain:
        scheduler.brain.close()
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='FINN Brain Scheduler')
    parser.add_argument('--test', action='store_true', help='Run single test cycle')
    parser.add_argument('--interval', type=int, default=30, help='Interval in minutes')
    args = parser.parse_args()

    if args.test:
        run_single_test()
    else:
        INTERVAL_MINUTES = args.interval
        scheduler = FINNScheduler()
        scheduler.run()
