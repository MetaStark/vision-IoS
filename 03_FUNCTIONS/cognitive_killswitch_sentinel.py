"""
Cognitive Engine Kill-Switch Sentinel
CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Phase D

Monitors for critical violations and triggers immediate shutdown:
- cost > $0.50 (any query)
- unsigned envelope
- IKEARefusal type mismatch
- staleness aborts > 20%

When triggered, sets COGNITIVE_ENGINE_MODE=OFF and logs evidence.

Author: STIG (CTO)
Date: 2026-01-05
"""

import os
import sys
import json
import time
import psycopg2
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# Load environment
from dotenv import load_dotenv
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(ENV_PATH, override=True)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION - Kill-Switch Triggers
# =============================================================================

# Cost cap violation (constitutional)
COST_HARD_CAP = 0.50

# Staleness abort threshold
STALENESS_ABORT_THRESHOLD = 0.20  # > 20% staleness aborts triggers kill

# Monitoring window
MONITORING_WINDOW_HOURS = 1

# Check interval (seconds)
CHECK_INTERVAL = 60


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class KillSwitchTrigger:
    trigger_type: str
    severity: str  # CRITICAL, HIGH
    timestamp: str
    details: str
    evidence: Dict


@dataclass
class SentinelStatus:
    timestamp: str
    mode: str
    healthy: bool
    triggers: List[KillSwitchTrigger]
    action_taken: Optional[str]


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=int(os.environ.get('PGPORT', '54322')),
        database=os.environ.get('PGDATABASE', 'postgres'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', 'postgres')
    )


# =============================================================================
# KILL-SWITCH CHECKS
# =============================================================================

def check_cost_violations(conn, window_hours: int = 1) -> Optional[KillSwitchTrigger]:
    """
    Check for any query exceeding $0.50 cost cap.
    This is a constitutional violation - immediate kill required.
    """
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT query_id, cost_usd, defcon_level, created_at
            FROM fhq_governance.inforage_query_log
            WHERE created_at > NOW() - INTERVAL '%s hours'
            AND cost_usd > %s
            ORDER BY created_at DESC
            LIMIT 1
        """, [window_hours, COST_HARD_CAP])

        row = cursor.fetchone()
        cursor.close()

        if row:
            query_id, cost, defcon, created_at = row
            return KillSwitchTrigger(
                trigger_type="COST_CAP_VIOLATION",
                severity="CRITICAL",
                timestamp=datetime.now(timezone.utc).isoformat(),
                details=f"Query {query_id} exceeded cost cap: ${cost:.4f} > ${COST_HARD_CAP}",
                evidence={
                    'query_id': str(query_id),
                    'cost_usd': float(cost),
                    'cap': COST_HARD_CAP,
                    'defcon_level': defcon,
                    'query_timestamp': str(created_at)
                }
            )
    except Exception as e:
        cursor.close()
        logger.warning(f"Cost check failed: {e}")

    return None


def check_unsigned_envelopes(conn, window_hours: int = 1) -> Optional[KillSwitchTrigger]:
    """
    Check for unsigned signal envelopes in evidence bundles.
    All envelopes must be cryptographically signed.
    """
    cursor = conn.cursor()

    try:
        # Check governance_actions_log for FINN actions without proper signing
        # Schema uses: initiated_at, initiated_by, timestamp
        cursor.execute("""
            SELECT action_id, action_type, initiated_by, initiated_at
            FROM fhq_governance.governance_actions_log
            WHERE initiated_at > NOW() - INTERVAL '%s hours'
            AND initiated_by = 'FINN'
            AND action_type LIKE '%%SIGNAL%%'
            AND (signature IS NULL OR signature = '')
            ORDER BY initiated_at DESC
            LIMIT 1
        """, [window_hours])

        row = cursor.fetchone()
        cursor.close()

        if row:
            action_id, action_type, initiated_by, initiated_at = row
            return KillSwitchTrigger(
                trigger_type="UNSIGNED_ENVELOPE",
                severity="CRITICAL",
                timestamp=datetime.now(timezone.utc).isoformat(),
                details=f"Unsigned signal envelope detected: {action_id}",
                evidence={
                    'action_id': str(action_id),
                    'action_type': action_type,
                    'agent_id': initiated_by,
                    'timestamp': str(initiated_at)
                }
            )
    except Exception as e:
        cursor.close()
        logger.warning(f"Unsigned envelope check failed: {e}")

    return None


def check_ikea_refusal_mismatch(conn, window_hours: int = 1) -> Optional[KillSwitchTrigger]:
    """
    Check for IKEARefusal due to type mismatch (non-SignalEnvelope input).
    This indicates a bypass attempt or integration bug.
    """
    cursor = conn.cursor()

    try:
        # Check inforage_query_log for IKEA type violations
        cursor.execute("""
            SELECT query_id, result_type, created_at
            FROM fhq_governance.inforage_query_log
            WHERE created_at > NOW() - INTERVAL '%s hours'
            AND result_type LIKE '%%IKEA%%TYPE%%MISMATCH%%'
            ORDER BY created_at DESC
            LIMIT 1
        """, [window_hours])

        row = cursor.fetchone()
        cursor.close()

        if row:
            query_id, result_type, created_at = row
            return KillSwitchTrigger(
                trigger_type="IKEA_TYPE_MISMATCH",
                severity="CRITICAL",
                timestamp=datetime.now(timezone.utc).isoformat(),
                details=f"IKEA refused non-SignalEnvelope input: {query_id}",
                evidence={
                    'query_id': str(query_id),
                    'result_type': result_type,
                    'timestamp': str(created_at)
                }
            )
    except Exception as e:
        cursor.close()
        logger.warning(f"IKEA mismatch check failed: {e}")

    return None


def check_staleness_abort_rate(conn, window_hours: int = 1) -> Optional[KillSwitchTrigger]:
    """
    Check if staleness aborts exceed 20% of queries.
    Indicates data freshness infrastructure failure.
    """
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE result_type LIKE '%%STALE%%') as stale_aborts
            FROM fhq_governance.inforage_query_log
            WHERE created_at > NOW() - INTERVAL '%s hours'
        """, [window_hours])

        row = cursor.fetchone()
        cursor.close()

        if row and row[0] > 0:
            total, stale_aborts = row
            abort_rate = stale_aborts / total if total > 0 else 0

            if abort_rate > STALENESS_ABORT_THRESHOLD:
                return KillSwitchTrigger(
                    trigger_type="HIGH_STALENESS_ABORT_RATE",
                    severity="HIGH",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details=f"Staleness abort rate {abort_rate:.1%} > {STALENESS_ABORT_THRESHOLD:.0%}",
                    evidence={
                        'total_queries': total,
                        'stale_aborts': stale_aborts,
                        'abort_rate': abort_rate,
                        'threshold': STALENESS_ABORT_THRESHOLD
                    }
                )
    except Exception as e:
        cursor.close()
        logger.warning(f"Staleness check failed: {e}")

    return None


# =============================================================================
# KILL-SWITCH ACTION
# =============================================================================

def disable_cognitive_engine() -> bool:
    """
    Emergency shutdown: Set COGNITIVE_ENGINE_MODE=OFF in .env file.
    Returns True if successful.
    """
    try:
        # Read current .env
        with open(ENV_PATH, 'r') as f:
            lines = f.readlines()

        # Find and replace COGNITIVE_ENGINE_MODE
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith('COGNITIVE_ENGINE_MODE='):
                new_lines.append('COGNITIVE_ENGINE_MODE=OFF\n')
                updated = True
                logger.critical("KILL-SWITCH ACTIVATED: Set COGNITIVE_ENGINE_MODE=OFF")
            else:
                new_lines.append(line)

        # If not found, add it
        if not updated:
            new_lines.append('\nCOGNITIVE_ENGINE_MODE=OFF\n')
            logger.critical("KILL-SWITCH ACTIVATED: Added COGNITIVE_ENGINE_MODE=OFF")

        # Write back
        with open(ENV_PATH, 'w') as f:
            f.writelines(new_lines)

        # Update environment variable for current process
        os.environ['COGNITIVE_ENGINE_MODE'] = 'OFF'

        return True

    except Exception as e:
        logger.error(f"Failed to disable cognitive engine: {e}")
        return False


def log_kill_switch_event(conn, trigger: KillSwitchTrigger, action: str) -> None:
    """Log kill-switch event to governance_actions_log."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type, agent_id, details, created_at
            ) VALUES (
                'COGNITIVE_KILLSWITCH', 'STIG',
                %s, NOW()
            )
        """, [json.dumps({
            'trigger': asdict(trigger),
            'action': action,
            'directive': 'CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001'
        })])
        conn.commit()
        cursor.close()
    except Exception as e:
        logger.warning(f"Failed to log kill-switch event: {e}")


# =============================================================================
# SENTINEL LOOP
# =============================================================================

def run_sentinel_check() -> SentinelStatus:
    """Run single sentinel check cycle."""
    current_mode = os.environ.get('COGNITIVE_ENGINE_MODE', 'OFF')

    triggers = []
    action_taken = None

    # Only monitor if cognitive engine is active
    if current_mode in ['SHADOW', 'LIVE']:
        # Check all kill-switch conditions
        # Each check gets its own connection to prevent transaction cascade failures
        checks = [
            check_cost_violations,
            check_unsigned_envelopes,
            check_ikea_refusal_mismatch,
            check_staleness_abort_rate
        ]

        for check_fn in checks:
            try:
                conn = get_db_connection()
                trigger = check_fn(conn, MONITORING_WINDOW_HOURS)
                conn.close()
                if trigger:
                    triggers.append(trigger)
            except Exception as e:
                logger.warning(f"Check {check_fn.__name__} failed: {e}")

        # If any CRITICAL trigger, activate kill-switch
        critical_triggers = [t for t in triggers if t.severity == 'CRITICAL']
        if critical_triggers:
            logger.critical(f"KILL-SWITCH TRIGGERED: {len(critical_triggers)} critical violations")
            for t in critical_triggers:
                logger.critical(f"  - {t.trigger_type}: {t.details}")

            # Disable cognitive engine
            if disable_cognitive_engine():
                action_taken = "COGNITIVE_ENGINE_DISABLED"
                # Log events with fresh connection
                try:
                    log_conn = get_db_connection()
                    for t in triggers:
                        log_kill_switch_event(log_conn, t, action_taken)
                    log_conn.close()
                except Exception as e:
                    logger.warning(f"Failed to log kill-switch events: {e}")
            else:
                action_taken = "DISABLE_FAILED"
                logger.error("CRITICAL: Failed to disable cognitive engine!")

    return SentinelStatus(
        timestamp=datetime.now(timezone.utc).isoformat(),
        mode=current_mode,
        healthy=len(triggers) == 0,
        triggers=triggers,
        action_taken=action_taken
    )


def run_sentinel_loop(interval_seconds: int = 60, max_iterations: int = None):
    """
    Run continuous sentinel monitoring loop.

    Args:
        interval_seconds: Check interval
        max_iterations: Maximum iterations (None = infinite)
    """
    logger.info("=" * 70)
    logger.info("COGNITIVE KILL-SWITCH SENTINEL STARTED")
    logger.info("CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Phase D")
    logger.info("=" * 70)
    logger.info(f"Check interval: {interval_seconds}s")
    logger.info(f"Monitoring window: {MONITORING_WINDOW_HOURS}h")
    logger.info(f"Kill triggers: cost>${COST_HARD_CAP}, unsigned, IKEA mismatch, staleness>{STALENESS_ABORT_THRESHOLD:.0%}")
    logger.info("=" * 70)

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1

        try:
            status = run_sentinel_check()

            if status.healthy:
                logger.info(f"[{iteration}] SENTINEL OK - Mode: {status.mode}")
            else:
                logger.warning(f"[{iteration}] SENTINEL ALERT - {len(status.triggers)} triggers")
                for t in status.triggers:
                    logger.warning(f"    {t.severity}: {t.trigger_type}")

            if status.action_taken:
                logger.critical(f"[{iteration}] ACTION: {status.action_taken}")
                # Store evidence
                save_sentinel_evidence(status)

        except Exception as e:
            logger.error(f"[{iteration}] Sentinel check failed: {e}")

        if max_iterations is None or iteration < max_iterations:
            time.sleep(interval_seconds)

    logger.info("Sentinel loop completed")


def save_sentinel_evidence(status: SentinelStatus):
    """Save sentinel event evidence."""
    evidence = {
        'directive': 'CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001',
        'event': 'KILLSWITCH_ACTIVATION',
        'timestamp': status.timestamp,
        'mode_before': status.mode,
        'action_taken': status.action_taken,
        'triggers': [asdict(t) for t in status.triggers]
    }

    evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
    os.makedirs(evidence_dir, exist_ok=True)

    evidence_path = os.path.join(
        evidence_dir,
        f'KILLSWITCH_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.json'
    )

    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2)

    logger.info(f"Evidence stored: {evidence_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run sentinel once (for testing) or start continuous loop."""
    import argparse

    parser = argparse.ArgumentParser(description='Cognitive Kill-Switch Sentinel')
    parser.add_argument('--once', action='store_true', help='Run single check')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    args = parser.parse_args()

    if args.once:
        status = run_sentinel_check()
        print(f"Mode: {status.mode}")
        print(f"Healthy: {status.healthy}")
        print(f"Triggers: {len(status.triggers)}")
        for t in status.triggers:
            print(f"  - {t.severity}: {t.trigger_type}")
        if status.action_taken:
            print(f"Action: {status.action_taken}")
    else:
        run_sentinel_loop(interval_seconds=args.interval)


if __name__ == '__main__':
    main()
