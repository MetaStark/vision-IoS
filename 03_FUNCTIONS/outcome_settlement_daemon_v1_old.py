#!/usr/bin/env python3
"""
OUTCOME SETTLEMENT DAEMON
=========================
CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024: Learning Velocity Restoration

PURPOSE: Authoritative daemon for PENDING decision pack settlement.
         Reads outcomes through outcome_pack_link layer.
         Writes terminal states: EXECUTED, FAILED, ORPHANED_OUTCOME_MISSING.

TERMINAL STATES:
- EXECUTED: Outcome exists via outcome_pack_link AND event window ended
- FAILED: Explicit failure with fail_reason_code (THRESHOLD_MISSING, OUTCOME_MISMATCH, DATA_ERROR, TIMEOUT)
- ORPHANED_OUTCOME_MISSING: No outcome after 24-hour timeout

SETTLEMENT RULES:
- Only settlements through this daemon are authoritative
- Post-mortem records created for FAILED packs in post_mortem_settlement table
- Original FAIL state preserved (no retrospective overrides)

CONSTRAINTS:
- Read-only on outcome_ledger (via outcome_pack_link layer)
- Update only execution_status on decision_packs
- Write to post_mortem_settlement for FAILED packs
- Generate evidence for each settlement
- Fail-closed on errors

Authority: CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024
Classification: G4_PRODUCTION_DAEMON
Executor: STIG (EC-003)
"""

import os
import sys
import json
import hashlib
import logging
import argparse
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor

DAEMON_NAME = 'outcome_settlement_daemon'
CYCLE_INTERVAL_SECONDS = 3600  # 1 hour

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

    Returns the post_mortem_id if created, None otherwise.
    """
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO fhq_learning.post_mortem_settlement
                (pack_id, hypothesis_id, fail_reason_code, fail_reason_detail, analysis_status, original_fail_at, resolved_by)
            VALUES (%s, %s, %s, %s, 'PENDING', NOW(), 'OUTCOME_SETTLEMENT_DAEMON')
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


def settle_decision_pack(conn, pack: Dict, outcome: Optional[Dict]) -> tuple[bool, str, Optional[str]]:
    """
    Settle a decision pack to a terminal state.

    Terminal states:
    - EXECUTED: Outcome exists via outcome_pack_link AND window ended
    - FAILED: Explicit failure with fail_reason_code (THRESHOLD_MISSING, OUTCOME_MISMATCH, DATA_ERROR, TIMEOUT)
    - ORPHANED_OUTCOME_MISSING: No outcome after 24-hour timeout

    Only settlements through this daemon are authoritative.
    """
    cur = conn.cursor()

    pack_age_hours = (datetime.now(timezone.utc) - pack['created_at'].replace(tzinfo=timezone.utc)).total_seconds() / 3600
    new_status = None
    outcome_id = None

    if outcome:
        # EXECUTED: Outcome exists via outcome_pack_link
        new_status = 'EXECUTED'
        outcome_id = outcome['outcome_id']

        settlement_evidence = json.dumps({
            'outcome_id': str(outcome['outcome_id']),
            'outcome_value': outcome['outcome_value'],
            'outcome_timestamp': outcome['outcome_timestamp'].isoformat() if outcome['outcome_timestamp'] else None,
            'outcome_hash': outcome['content_hash'],
            'link_method': outcome['link_method'],
            'link_confidence': float(outcome['link_confidence']),
            'settlement_timestamp': datetime.now(timezone.utc).isoformat(),
            'pack_age_hours': round(pack_age_hours, 2)
        })
        evidence_hash = 'sha256:' + hashlib.sha256(settlement_evidence.encode()).hexdigest()

        cur.execute("""
            UPDATE fhq_learning.decision_packs
            SET execution_status = %s,
                evidence_hash = %s,
                filled_at = %s
            WHERE pack_id = %s
        """, ('EXECUTED', evidence_hash, outcome['outcome_timestamp'], pack['pack_id']))

        logger.info(f"EXECUTED: pack={pack['pack_id'][:8]}... asset={pack['asset']} -> EXECUTED (outcome={outcome['outcome_id'][:8]}...)")

    elif pack_age_hours >= 24:  # 24-hour timeout - no outcome
        # ORPHANED_OUTCOME_MISSING: No outcome after timeout
        new_status = 'ORPHANED_OUTCOME_MISSING'

        # Create post-mortem record for orphaned pack
        post_mortem_data = json.dumps({
            'fail_reason_code': 'TIMEOUT',
            'fail_reason_detail': f'No outcome found within 24-hour window (age={pack_age_hours:.1f}h)',
            'analysis_status': 'PENDING',
            'original_fail_at': datetime.now(timezone.utc).isoformat(),
            'pack_context': {
                'asset': pack['asset'],
                'direction': pack['direction'],
                'snapshot_price': float(pack['snapshot_price']),
                'pack_age_hours': round(pack_age_hours, 2)
            }
        })

        # Update decision_packs status
        cur.execute("""
            UPDATE fhq_learning.decision_packs
            SET execution_status = %s
            WHERE pack_id = %s
        """, ('ORPHANED_OUTCOME_MISSING', pack['pack_id']))

        logger.info(f"ORPHANED: pack={pack['pack_id'][:8]}... asset={pack['asset']} -> ORPHANED_OUTCOME_MISSING (age={pack_age_hours:.1f}h)")

    else:
        # Still waiting - do not settle yet
        logger.debug(f"WAITING: pack={pack['pack_id'][:8]}... asset={pack['asset']} (age={pack_age_hours:.1f}h)")
        return False, None, None

    conn.commit()
    return True, new_status, outcome_id


def generate_settlement_evidence(settlements: List[Dict]) -> Dict:
    """Generate evidence bundle for settlements."""
    evidence = {
        'directive': 'CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024',
        'evidence_type': 'OUTCOME_SETTLEMENT',
        'computed_at': datetime.now(timezone.utc).isoformat(),
        'computed_by': 'STIG',
        'ec_contract': 'EC-003',
        'settlements': settlements,
        'summary': {
            'total_settled': len(settlements),
            'executed_count': sum(1 for s in settlements if s['new_status'] == 'EXECUTED'),
            'failed_count': sum(1 for s in settlements if s['new_status'] == 'FAILED'),
            'orphaned_count': sum(1 for s in settlements if s['new_status'] == 'ORPHANED_OUTCOME_MISSING'),
            'post_mortem_records': sum(1 for s in settlements if s.get('post_mortem_id'))
        }
    }

    evidence_str = json.dumps(evidence, sort_keys=True)
    evidence['evidence_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()[:16]

    return evidence


def heartbeat(conn, status: str, details: dict = None):
    """Update daemon heartbeat in daemon_health."""
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
            """, (DAEMON_NAME, status, json.dumps(details) if details else None))
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
            # Find matching outcome
            outcome = find_matching_outcome(conn, pack)

            # Settle the pack
            settled, new_status, outcome_id = settle_decision_pack(conn, pack, outcome)

            if settled:
                # Create post-mortem record for ORPHANED_OUTCOME_MISSING
                post_mortem_id = None
                if new_status == 'ORPHANED_OUTCOME_MISSING':
                    pack_age_hours = (datetime.now(timezone.utc) - pack['created_at'].replace(tzinfo=timezone.utc)).total_seconds() / 3600
                    fail_detail = f'No outcome found within 24-hour window (age={pack_age_hours:.1f}h)'
                    post_mortem_id = create_post_mortem_record(conn, pack, 'TIMEOUT', fail_detail)

                settlements.append({
                    'pack_id': str(pack['pack_id']),
                    'asset': pack['asset'],
                    'new_status': new_status,
                    'outcome_id': str(outcome_id) if outcome_id else None,
                    'post_mortem_id': post_mortem_id
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
        heartbeat(conn, 'HEALTHY', {
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
        try:
            heartbeat(conn, 'DEGRADED', {'error': str(e)})
        except Exception:
            pass
        raise
    finally:
        conn.close()


def main():
    """Main entry point for outcome settlement daemon."""
    parser = argparse.ArgumentParser(description='Outcome Settlement Daemon')
    parser.add_argument('--once', action='store_true',
                        help='Run a single cycle then exit')
    parser.add_argument('--interval', type=int, default=CYCLE_INTERVAL_SECONDS,
                        help=f'Cycle interval in seconds (default: {CYCLE_INTERVAL_SECONDS})')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("OUTCOME SETTLEMENT DAEMON")
    logger.info(f"  mode={'once' if args.once else 'continuous'}")
    logger.info(f"  interval={args.interval}s")
    logger.info("CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024: Learning Velocity Restoration")
    logger.info("=" * 60)

    if args.once:
        result = run_cycle()
        print(f"\nSettled: {len(result['settlements'])} decision packs")
        return

    # Continuous daemon loop
    while True:
        try:
            run_cycle()
        except Exception as e:
            logger.error(f"Cycle failed: {e}")
        logger.info(f"Next cycle in {args.interval}s")
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
