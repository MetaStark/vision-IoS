#!/usr/bin/env python3
"""
HYPOTHESIS DEATH DAEMON
========================
CEO-DIR-2026-HYPOTHESIS-DEATH-001
CEO-DIR-2026-HYPOTHESIS-DEATH-002 (ACTIVE processing)

PURPOSE: Process expired hypotheses and mark them as FALSIFIED.
         This enables the G1.5 calibration experiment to accumulate
         deaths with pre_tier_score_at_birth for Spearman analysis.

CONSTRAINTS:
- Process hypotheses where status = 'DRAFT' OR 'ACTIVE'
- Kill hypotheses past their expected_timeframe_hours
- Set death_timestamp, time_to_falsification_hours
- Count towards G1.5 experiment (30 deaths target)

FIX (2026-01-27): Added ACTIVE hypothesis processing.
- ACTIVE hypotheses that exceeded timeframe were not being falsified
- Tier-1 promoted DRAFT → ACTIVE before time-based expiration
- Now both DRAFT and ACTIVE expired hypotheses are processed

Authority: ADR-020 (ACI), ADR-016 (DEFCON), G1.5 Experiment
Classification: G4_PRODUCTION_DAEMON
Executor: STIG (EC-003)
"""

import os
import sys
import json
import time
import signal
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Tuple, Optional, List, Dict, Any

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Daemon configuration
INTERVAL_MINUTES = 15  # Check every 15 minutes
DAEMON_NAME = 'hypothesis_death_daemon'
MAX_DEATHS_PER_CYCLE = 50  # Increased from 10 to clear ACTIVE backlog (CEO-DIR-2026-HYPOTHESIS-DEATH-002)

# Setup logging
log_dir = 'C:/fhq-market-system/vision-ios/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[DEATH-DAEMON] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/hypothesis_death_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    logger.info(f"Shutdown signal received ({signum})")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def defcon_gate_check() -> Tuple[bool, str, str]:
    """DEFCON Hard Gate Check."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT defcon_level FROM fhq_governance.defcon_state
                WHERE is_current = true
                ORDER BY triggered_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            level = row[0] if row else 'GREEN'
        conn.close()
    except Exception as e:
        logger.critical(f"DEFCON check failed - BLOCKING: {e}")
        return (False, f"DEFCON CHECK FAILURE: {e}", "UNKNOWN")

    if level in ('RED', 'BLACK'):
        return (False, f"DEFCON {level}: ALL PROCESSES MUST TERMINATE", level)
    if level == 'ORANGE':
        return (False, f"DEFCON ORANGE: NEW CYCLES BLOCKED", level)
    if level == 'YELLOW':
        return (True, f"DEFCON YELLOW: Proceed with caution", level)
    return (True, f"DEFCON {level}: Full operation permitted", level)


def update_daemon_heartbeat(status: str = 'HEALTHY', metadata: dict = None):
    """Update daemon health heartbeat."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            meta_json = json.dumps(metadata or {})
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
                VALUES (%s, %s, NOW(), %s::jsonb)
                ON CONFLICT (daemon_name) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_heartbeat = NOW(),
                    metadata = EXCLUDED.metadata
            """, (DAEMON_NAME, status, meta_json))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")


def get_expired_hypotheses() -> List[Dict[str, Any]]:
    """
    Find DRAFT and ACTIVE hypotheses that have exceeded their expected_timeframe_hours.

    CEO-DIR-2026-HYPOTHESIS-DEATH-002: Now includes ACTIVE status.
    ACTIVE hypotheses were being promoted by Tier-1 but never falsified on expiration.
    """
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    canon_id,
                    hypothesis_code,
                    generator_id,
                    status,
                    tier1_result,
                    created_at,
                    expected_timeframe_hours,
                    pre_tier_score_at_birth,
                    created_at + (expected_timeframe_hours || ' hours')::interval as death_time,
                    EXTRACT(EPOCH FROM (NOW() - created_at))/3600 as hours_since_creation
                FROM fhq_learning.hypothesis_canon
                WHERE status IN ('DRAFT', 'ACTIVE')
                  AND expected_timeframe_hours IS NOT NULL
                  AND NOW() > created_at + (expected_timeframe_hours || ' hours')::interval
                ORDER BY created_at ASC
                LIMIT %s
            """, (MAX_DEATHS_PER_CYCLE,))
            results = cur.fetchall()
        conn.close()
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"Failed to get expired hypotheses: {e}")
        return []


def process_hypothesis_death(hypothesis: Dict[str, Any]) -> bool:
    """
    Mark a hypothesis as FALSIFIED (dead).

    For G1.5 experiment, we need:
    - status = 'FALSIFIED'
    - death_timestamp = NOW()
    - time_to_falsification_hours = hours from creation to death
    - falsified_at = NOW()

    CEO-DIR-2026-HYPOTHESIS-DEATH-002: Now handles both DRAFT and ACTIVE status.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Calculate time to death
            hours_lived = hypothesis['hours_since_creation']
            prev_status = hypothesis.get('status', 'UNKNOWN')
            tier1_result = hypothesis.get('tier1_result', 'NONE')

            # Build annihilation reason based on previous status
            if prev_status == 'ACTIVE':
                reason = f'HORIZON_EXPIRED_ACTIVE: Was {tier1_result}, exceeded {hypothesis["expected_timeframe_hours"]}h without market validation'
            else:
                reason = 'HORIZON_EXPIRED: Exceeded expected_timeframe_hours without validation'

            # Update the hypothesis - now accepts both DRAFT and ACTIVE
            cur.execute("""
                UPDATE fhq_learning.hypothesis_canon
                SET
                    status = 'FALSIFIED',
                    falsified_at = NOW(),
                    death_timestamp = NOW(),
                    time_to_falsification_hours = %s,
                    last_updated_at = NOW(),
                    last_updated_by = 'hypothesis_death_daemon',
                    annihilation_reason = %s
                WHERE canon_id = %s
                  AND status IN ('DRAFT', 'ACTIVE')
                RETURNING hypothesis_code
            """, (hours_lived, reason, hypothesis['canon_id']))

            result = cur.fetchone()
            if result:
                conn.commit()

                # Log the death with status transition
                has_score = hypothesis.get('pre_tier_score_at_birth') is not None
                score_str = f"score={hypothesis['pre_tier_score_at_birth']:.2f}" if has_score else "NO_SCORE"

                logger.info(
                    f"DEATH: {hypothesis['hypothesis_code']} | "
                    f"{prev_status}->FALSIFIED | "
                    f"tier1={tier1_result} | "
                    f"generator={hypothesis['generator_id']} | "
                    f"lived={hours_lived:.1f}h | "
                    f"horizon={hypothesis['expected_timeframe_hours']}h | "
                    f"{score_str} | "
                    f"G1.5_ELIGIBLE={'YES' if has_score else 'NO'}"
                )

                conn.close()
                return True
            else:
                conn.rollback()
                conn.close()
                logger.warning(f"Hypothesis {hypothesis['hypothesis_code']} already processed or not in DRAFT/ACTIVE status")
                return False

    except Exception as e:
        logger.error(f"Failed to process death for {hypothesis['hypothesis_code']}: {e}")
        return False


def get_g15_death_count() -> Tuple[int, int]:
    """Get G1.5 experiment death count (with scores) and total deaths."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Deaths with pre_tier_score_at_birth (count for G1.5)
            cur.execute("""
                SELECT COUNT(*)
                FROM fhq_learning.hypothesis_canon
                WHERE status = 'FALSIFIED'
                  AND pre_tier_score_at_birth IS NOT NULL
            """)
            g15_deaths = cur.fetchone()[0]

            # Total deaths
            cur.execute("""
                SELECT COUNT(*)
                FROM fhq_learning.hypothesis_canon
                WHERE status = 'FALSIFIED'
            """)
            total_deaths = cur.fetchone()[0]

        conn.close()
        return (g15_deaths, total_deaths)
    except Exception as e:
        logger.error(f"Failed to get death count: {e}")
        return (0, 0)


def run_death_cycle() -> Dict[str, Any]:
    """Run one death processing cycle."""
    cycle_start = datetime.now(timezone.utc)
    result = {
        'timestamp': cycle_start.isoformat(),
        'deaths_processed': 0,
        'g15_eligible_deaths': 0,
        'errors': []
    }

    # Get expired hypotheses
    expired = get_expired_hypotheses()
    logger.info(f"Found {len(expired)} expired hypotheses to process")

    if not expired:
        result['message'] = 'No expired hypotheses found'
        return result

    # Process each death
    for hyp in expired:
        success = process_hypothesis_death(hyp)
        if success:
            result['deaths_processed'] += 1
            if hyp.get('pre_tier_score_at_birth') is not None:
                result['g15_eligible_deaths'] += 1

    # Get updated G1.5 count
    g15_deaths, total_deaths = get_g15_death_count()
    result['g15_death_count'] = g15_deaths
    result['total_death_count'] = total_deaths
    result['g15_target'] = 30
    result['g15_progress_pct'] = round(g15_deaths / 30 * 100, 1)

    logger.info(
        f"Cycle complete: processed={result['deaths_processed']} | "
        f"G1.5_eligible={result['g15_eligible_deaths']} | "
        f"G1.5_progress={g15_deaths}/30 ({result['g15_progress_pct']}%)"
    )

    return result


def main():
    """Main daemon loop."""
    logger.info("=" * 60)
    logger.info("HYPOTHESIS DEATH DAEMON STARTING - VERSION 2.0")
    logger.info("CEO-DIR-2026-HYPOTHESIS-DEATH-002: Now processes DRAFT + ACTIVE")
    logger.info(f"Interval: {INTERVAL_MINUTES} minutes")
    logger.info(f"Max deaths per cycle: {MAX_DEATHS_PER_CYCLE}")
    logger.info("Purpose: Process expired hypotheses for G1.5 calibration")
    logger.info("=" * 60)

    cycle_count = 0

    while not shutdown_requested:
        cycle_count += 1
        logger.info(f"--- Cycle {cycle_count} starting ---")

        # DEFCON gate check
        can_proceed, msg, level = defcon_gate_check()
        if not can_proceed:
            logger.warning(f"DEFCON BLOCKED: {msg}")
            update_daemon_heartbeat('BLOCKED_DEFCON', {'defcon': level})
            time.sleep(60)
            continue

        # Run death processing cycle
        try:
            result = run_death_cycle()

            # Update heartbeat with cycle results
            update_daemon_heartbeat('HEALTHY', {
                'cycle': cycle_count,
                'last_result': result,
                'defcon': level
            })

        except Exception as e:
            logger.error(f"Cycle {cycle_count} failed: {e}")
            update_daemon_heartbeat('ERROR', {'error': str(e)})

        # Wait for next cycle
        logger.info(f"Sleeping {INTERVAL_MINUTES} minutes until next cycle...")
        for _ in range(INTERVAL_MINUTES * 60):
            if shutdown_requested:
                break
            time.sleep(1)

    logger.info("Hypothesis Death Daemon shutting down gracefully")
    update_daemon_heartbeat('STOPPED', {'shutdown': 'graceful'})


if __name__ == '__main__':
    main()
