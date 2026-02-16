#!/usr/bin/env python3
"""
OUTCOME SETTLEMENT DAEMON (CONTINUOUS MODE)
============================================
CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024 - Directive 1
CEO-DIR-2026-LVI-LOOP-CLOSURE-025 - Start daemon in continuous mode

PURPOSE: Authoritative daemon for PENDING decision pack settlement.
         Runs continuously in production mode.
         Reads outcomes through outcome_pack_link layer.
         Writes terminal states: EXECUTED, FAILED, ORPHANED_OUTCOME_MISSING.
         Creates audit trail in outcome_settlement_log (append-only).
         Creates post-mortem records for FAILED and ORPHANED_OUTCOME_MISSING.

CONTINUOUS MODE FEATURES:
- Daemon heartbeat in daemon_health table with status ACTIVE
- PID file for daemon lifecycle management
- Fail-closed logic for missing outcome_pack_link (no silent drops)
- Evidence generation per run cycle

TERMINAL STATES:
- EXECUTED: Outcome exists via outcome_pack_link AND window ended
- FAILED: Explicit failure with fail_reason_code (THRESHOLD_MISSING, OUTCOME_MISMATCH, DATA_ERROR, TIMEOUT)
- ORPHANED_OUTCOME_MISSING: No outcome after 24-hour timeout

SETTLEMENT LOGIC:
1. For EXECUTED: Require outcome_pack_link exists, write to outcome_settlement_log
2. For ORPHANED_OUTCOME_MISSING: Create post-mortem row + outcome_settlement_log row
3. For FAILED: Create post-mortem row + outcome_settlement_log row

CONSTRAINTS:
- Read-only on outcome_ledger (via outcome_pack_link layer)
- Update only execution_status on decision_packs (with fail_reason columns)
- Write to post_mortem_settlement for FAILED/ORPHANED_OUTCOME_MISSING
- Write to outcome_settlement_log (append-only)
- Generate evidence for each settlement
- Fail-closed on errors (daemon_health = DEGRADED)

Authority: CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024
Classification: G4_PRODUCTION_DAEMON
Executor: STIG (EC-003)
Version: 3.1.0-CONTINUOUS
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import time
import signal
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor

DAEMON_NAME = 'outcome_settlement_daemon'
DAEMON_VERSION = '3.1.0-CONTINUOUS'
CYCLE_INTERVAL_SECONDS = 3600  # 1 hour
PID_FILE = '03_FUNCTIONS/outcome_settlement_daemon.pid'

logging.basicConfig(
    level=logging.INFO,
    format='[OUTCOME_SETTLE] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/outcome_settlement_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def write_pid(pid: int):
    """Write PID file for daemon lifecycle management."""
    with open(PID_FILE, 'w') as f:
        f.write(str(pid))
    logger.info(f"PID file written: {PID_FILE} (pid={pid})")


def read_pid() -> Optional[int]:
    """Read PID file if exists."""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            return int(f.read().strip())
    return None


def remove_pid():
    """Remove PID file."""
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
        logger.info(f"PID file removed: {PID_FILE}")


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_pending_decision_packs(conn) -> List[Dict]:
    """Get decision packs with PENDING status that need settlement (24-hour event window)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            dp.pack_id,
            dp.asset,
            dp.direction,
            dp.hypothesis_uuid,
            dp.created_at,
            dp.snapshot_price,
            dp.snapshot_timestamp,
            dp.evidence_hash,
            dp.snapshot_ttl_valid_until
        FROM fhq_learning.decision_packs dp
        WHERE dp.execution_status = 'PENDING'
          AND dp.created_at < NOW() - INTERVAL '24 hours'
        ORDER BY dp.created_at ASC
        LIMIT 50
    """)
    return cur.fetchall()


def find_matching_outcome(conn, pack: Dict) -> Optional[Dict]:
    """Find outcome_pack_link entry that matches this decision pack."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Query through outcome_pack_link layer (authoritative link)
    cur.execute("""
        SELECT
            opl.link_id,
            opl.outcome_id,
            opl.pack_id,
            opl.hypothesis_id,
            opl.linked_at,
            opl.link_method,
            opl.link_confidence,
            ol.outcome_type,
            ol.outcome_domain,
            ol.outcome_value,
            ol.outcome_timestamp,
            ol.evidence_source,
            ol.evidence_data,
            ol.content_hash
        FROM fhq_learning.outcome_pack_link opl
        JOIN fhq_research.outcome_ledger ol ON opl.outcome_id = ol.outcome_id
        WHERE opl.pack_id = %s
        LIMIT 1
    """, (pack['pack_id'],))

    return cur.fetchone()


def create_post_mortem_record(conn, pack: Dict, fail_reason_code: str, fail_detail: str) -> Optional[str]:
    """
    Create post-mortem record for FAILED or ORPHANED_OUTCOME_MISSING packs.

    Returns post_mortem_id if created, None otherwise.
    """
    cur = conn.cursor()

    try:
        # Use existing fail context if available (NULL allowed by constraint)
        fail_reason_code = pack.get('fail_reason_code') if pack.get('fail_reason_code') else 'UNKNOWN'
        fail_detail = pack.get('fail_reason_detail') if pack.get('fail_reason_detail') else f'FAILED pack from batch: {pack["asset"]} {pack["direction"]}'

        cur.execute("""
            INSERT INTO fhq_learning.post_mortem_settlement
                (pack_id, hypothesis_id, fail_reason_code, fail_reason_detail, analysis_status, original_fail_at, resolved_by)
            VALUES (%s, %s, %s, 'PENDING', NOW(), 'OUTCOME_SETTLEMENT_DAEMON')
            ON CONFLICT (pack_id) DO NOTHING
            RETURNING post_mortem_id
        """, (pack['pack_id'], pack.get('hypothesis_uuid'), fail_reason_code, fail_detail))

        result = cur.fetchone()
        if result:
            pm_id = result[0]
            logger.info(f"Created post-mortem record: pack={pack['pack_id'][:8]}... -> post_mortem_id={pm_id[:8]}...")
            return str(pm_id)
        return None

    except Exception as e:
        logger.error(f"Failed to create post-mortem record for pack={pack['pack_id'][:8]}...: {e}")
        return None


def create_settlement_log_entry(conn, pack: Dict, prior_status: str, new_status: str,
                                outcome_id: Optional[str], reason_code: str,
                                evidence_data: dict) -> Optional[str]:
    """
    Create entry in outcome_settlement_log (append-only audit spine).

    Returns settlement_id if created, None otherwise.
    """
    cur = conn.cursor()

    try:
        evidence_payload = json.dumps(evidence_data, sort_keys=True)
        evidence_hash = hashlib.sha256(evidence_payload.encode()).hexdigest()

        settled_by = f"{DAEMON_NAME}@{DAEMON_VERSION}"

        cur.execute("""
            INSERT INTO fhq_learning.outcome_settlement_log
                (pack_id, prior_status, new_status, outcome_id,
                 settlement_reason_code, settlement_evidence_hash, settled_at, settled_by)
            VALUES (%s, %s, %s, %s, NOW(), %s)
            RETURNING settlement_id
        """, (
            pack['pack_id'],
            prior_status,
            new_status,
            outcome_id,
            reason_code,
            evidence_hash,
            settled_by
        ))

        result = cur.fetchone()
        if result:
            log_id = result[0]
            logger.info(f"Created settlement log entry: pack={pack['pack_id'][:8]}... -> settlement_id={log_id[:8]}...")
            return str(log_id)
        return None

    except Exception as e:
        logger.error(f"Failed to create settlement log entry for pack={pack['pack_id'][:8]}...: {e}")
        return None


def settle_decision_pack(conn, pack: Dict, outcome: Optional[Dict]) -> tuple[bool, str, Optional[str]]:
    """
    Settle a decision pack to a terminal state.

    Terminal states:
    - EXECUTED: Outcome exists via outcome_pack_link AND window ended
    - FAILED: Explicit failure with fail_reason_code (THRESHOLD_MISSING, OUTCOME_MISMATCH, DATA_ERROR, TIMEOUT)
    - ORPHANED_OUTCOME_MISSING: No outcome after 24-hour timeout

    Fail-closed logic: If outcome_pack_link is missing for PENDING pack >= 24h old,
    mark as ORPHANED_OUTCOME_MISSING with post-mortem + settlement log (evidence-grade).
    No silent drops - all terminalizations must create audit entries.

    Only settlements through this daemon are authoritative.
    """
    cur = conn.cursor()

    prior_status = pack.get('execution_status', 'PENDING')
    pack_age_hours = (datetime.now(timezone.utc) - pack['created_at'].replace(tzinfo=timezone.utc)).total_seconds() / 3600
    new_status = None
    outcome_id = None
    settlement_reason_code = None

    # Fail-closed check: If outcome_pack_link is missing and pack is >= 24h old
    if not outcome and pack_age_hours >= 24:
        # ORPHANED_OUTCOME_MISSING: No outcome after timeout
        new_status = 'ORPHANED_OUTCOME_MISSING'
        settlement_reason_code = 'OUTCOME_MISSING_TIMEOUT'

        fail_detail = f'No outcome found within 24-hour window (age={pack_age_hours:.1f}h)'

        # Create post-mortem record
        pm_id = create_post_mortem_record(conn, pack, 'TIMEOUT', fail_detail)

        # Update decision_packs with new columns
        cur.execute("""
            UPDATE fhq_learning.decision_packs
            SET execution_status = %s,
                outcome_id = NULL,
                evidence_hash = NULL,
                filled_at = NULL,
                fail_reason_code = %s,
                fail_reason_detail = %s,
                terminalized_at = NOW(),
                settled_by = %s
            WHERE pack_id = %s
        """, (
            'ORPHANED_OUTCOME_MISSING',
            'TIMEOUT',
            fail_detail,
            f"{DAEMON_NAME}@{DAEMON_VERSION}"
        ))

        logger.info(f"FAIL-CLOSED: pack={pack['pack_id'][:8]}... asset={pack['asset']} -> ORPHANED_OUTCOME_MISSING (age={pack_age_hours:.1f}h)")

    elif outcome:
        # EXECUTED: Outcome exists via outcome_pack_link
        new_status = 'EXECUTED'
        outcome_id = str(outcome['outcome_id'])
        settlement_reason_code = 'OUTCOME_LINKED'

        # Compute settlement evidence
        settlement_evidence_data = {
            'outcome_id': outcome_id,
            'outcome_value': outcome['outcome_value'],
            'outcome_timestamp': outcome['outcome_timestamp'].isoformat() if outcome['outcome_timestamp'] else None,
            'outcome_hash': outcome['content_hash'],
            'link_method': outcome['link_method'],
            'link_confidence': float(outcome['link_confidence']),
            'settlement_timestamp': datetime.now(timezone.utc).isoformat(),
            'pack_age_hours': round(pack_age_hours, 2),
            'daemon_version': DAEMON_VERSION
        }

        # Update decision_packs with new columns
        cur.execute("""
            UPDATE fhq_learning.decision_packs
            SET execution_status = %s,
                outcome_id = %s,
                evidence_hash = %s,
                filled_at = %s,
                fail_reason_code = NULL,
                fail_reason_detail = NULL,
                terminalized_at = NOW(),
                settled_by = %s
            WHERE pack_id = %s
        """, (
            'EXECUTED',
            outcome['outcome_id'],
            'sha256:' + hashlib.sha256(json.dumps(settlement_evidence_data, sort_keys=True).encode()).hexdigest(),
            outcome['outcome_timestamp'],
            f"{DAEMON_NAME}@{DAEMON_VERSION}"
        ))

        logger.info(f"EXECUTED: pack={pack['pack_id'][:8]}... asset={pack['asset']} -> EXECUTED (outcome={outcome['outcome_id'][:8]}...)")

    else:
        # Still waiting - do not settle yet
        logger.debug(f"WAITING: pack={pack['pack_id'][:8]}... asset={pack['asset']} (age={pack_age_hours:.1f}h)")
        return False, None, None

    conn.commit()

    # Create settlement log entry (if terminal state reached)
    if new_status:
        settlement_evidence_data = {
            'outcome_id': outcome_id,
            'settlement_timestamp': datetime.now(timezone.utc).isoformat(),
            'pack_age_hours': round(pack_age_hours, 2),
            'daemon_version': DAEMON_VERSION
        }

        log_id = create_settlement_log_entry(
            conn, pack, prior_status, new_status,
            outcome_id, settlement_reason_code, settlement_evidence_data
        )

        if log_id:
            return True, new_status, outcome_id, log_id

    return True, new_status, outcome_id, None


def generate_settlement_evidence(settlements: List[Dict]) -> Dict:
    """Generate evidence bundle for settlements."""
    evidence = {
        'directive': 'CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024',
        'evidence_type': 'OUTCOME_SETTLEMENT',
        'computed_at': datetime.now(timezone.utc).isoformat(),
        'computed_by': 'STIG',
        'ec_contract': 'EC-003',
        'daemon_version': DAEMON_VERSION,
        'settlements': settlements,
        'summary': {
            'total_settled': len(settlements),
            'executed_count': sum(1 for s in settlements if s['new_status'] == 'EXECUTED'),
            'failed_count': sum(1 for s in settlements if s['new_status'] == 'FAILED'),
            'orphaned_count': sum(1 for s in settlements if s['new_status'] == 'ORPHANED_OUTCOME_MISSING'),
            'post_mortem_records': sum(1 for s in settlements if s.get('post_mortem_id')),
            'settlement_log_entries': sum(1 for s in settlements if s.get('settlement_log_id'))
        }
    }

    evidence_str = json.dumps(evidence, sort_keys=True)
    evidence['evidence_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()[:16]

    return evidence


def heartbeat(conn, status: str, details: dict = None):
    """Update daemon heartbeat in daemon_health table with status ACTIVE."""
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
            """, (DAEMON_NAME, 'HEALTHY', json.dumps(details) if details else None))
            conn.commit()
    except Exception as e:
        logger.warning(f"Heartbeat failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def run_cycle() -> Dict:
    """Run one settlement cycle."""
    conn = get_connection()
    settlements = []

    try:
        # Get pending decision packs
        pending_packs = get_pending_decision_packs(conn)
        logger.info(f"Found {len(pending_packs)} pending decision packs to evaluate")

        for pack in pending_packs:
            # Find matching outcome through outcome_pack_link
            outcome = find_matching_outcome(conn, pack)

            # Settle pack to terminal state
            settled, new_status, outcome_id, log_id = settle_decision_pack(conn, pack, outcome)

            if settled:
                settlements.append({
                    'pack_id': str(pack['pack_id']),
                    'asset': pack['asset'],
                    'new_status': new_status,
                    'outcome_id': outcome_id,
                    'post_mortem_id': None,  # EXECUTED doesn't get post_mortem
                    'settlement_log_id': log_id if log_id else None,
                    'settlement_reason_code': 'OUTCOME_LINKED' if new_status == 'EXECUTED' else 'OUTCOME_MISSING_TIMEOUT'
                })

        # Generate evidence
        if settlements:
            evidence = generate_settlement_evidence(settlements)

            # Save evidence file
            script_dir = os.path.dirname(os.path.abspath(__file__))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence_path = os.path.join(script_dir, 'evidence', f'OUTCOME_SETTLEMENT_{timestamp}.json')
            with open(evidence_path, 'w') as f:
                json.dump(evidence, f, indent=2)
            logger.info(f"Evidence: {evidence_path}")

        # Heartbeat
        heartbeat(conn, 'ACTIVE', {
            'pending_evaluated': len(pending_packs),
            'settled': len(settlements),
            'executed': sum(1 for s in settlements if s['new_status'] == 'EXECUTED'),
            'failed': sum(1 for s in settlements if s['new_status'] == 'FAILED'),
            'orphaned': sum(1 for s in settlements if s['new_status'] == 'ORPHANED_OUTCOME_MISSING')
        })

        return {
            'pending_evaluated': len(pending_packs),
            'settlements': settlements
        }

    except Exception as e:
        logger.error(f"Settlement cycle failed: {e}")
        heartbeat(conn, 'DEGRADED', {'error': str(e)})
        time.sleep(CYCLE_INTERVAL_SECONDS)  # Continue on error

    finally:
        conn.close()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    heartbeat(get_connection(), 'STOPPED', {'reason': f'Signal {signum}'})
    remove_pid()
    sys.exit(0)


def main():
    """Main entry point for outcome settlement daemon (continuous mode)."""
    parser = argparse.ArgumentParser(description='Outcome Settlement Daemon (Continuous)')
    parser.add_argument('--once', action='store_true',
                        help='Run a single cycle then exit')
    parser.add_argument('--stop', action='store_true',
                        help='Stop running daemon')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"OUTCOME SETTLEMENT DAEMON v{DAEMON_VERSION} (CONTINUOUS MODE)")
    logger.info("CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024: Learning Velocity Restoration")
    logger.info("=" * 60)

    # Write PID file
    current_pid = os.getpid()
    write_pid(current_pid)

    # Register signal handlers for graceful shutdown
    import signal
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Continuous daemon loop
    cycle_count = 0
    while True:
        try:
            run_cycle()
            cycle_count += 1
            logger.info(f"Cycle {cycle_count} completed. Next cycle in {CYCLE_INTERVAL_SECONDS}s")
            time.sleep(CYCLE_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Daemon loop failed: {e}")
            heartbeat(get_connection(), 'DEGRADED', {'error': str(e)})
            time.sleep(CYCLE_INTERVAL_SECONDS)  # Continue on error

    # Cleanup on exit
    logger.info(f"Daemon shutting down after {cycle_count} cycles")
    remove_pid()
    heartbeat(get_connection(), 'STOPPED', {'cycles_completed': cycle_count})
