#!/usr/bin/env python3
"""
OUTCOME SETTLEMENT DAEMON
=========================
CEO-DIR-2026-128 DAY42: Learning Velocity Restoration

PURPOSE: Link outcome_ledger entries back to decision_packs.
         Updates execution_status from 'PENDING' to 'EXECUTED'.
         Enables LVI computation by completing the learning loop.

CONSTRAINTS:
- Read-only on outcome_ledger
- Update only execution_status on decision_packs
- Generate evidence for each settlement
- Fail-closed on errors

Authority: CEO-DIR-2026-128
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
    """Get decision packs with PENDING status that need settlement."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            dp.pack_id,
            dp.asset,
            dp.direction,
            dp.hypothesis_id,
            dp.created_at,
            dp.snapshot_price,
            dp.snapshot_timestamp,
            dp.evidence_hash
        FROM fhq_learning.decision_packs dp
        WHERE dp.execution_status = 'PENDING'
          AND dp.created_at < NOW() - INTERVAL '24 hours'
        ORDER BY dp.created_at ASC
        LIMIT 50
    """)
    return cur.fetchall()


def find_matching_outcome(conn, pack: Dict) -> Optional[Dict]:
    """Find outcome_ledger entry that matches this decision pack."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Match by asset (outcome_domain) and timestamp window
    # Outcomes should arrive within 7 days of decision pack creation
    cur.execute("""
        SELECT
            outcome_id,
            outcome_type,
            outcome_domain,
            outcome_value,
            outcome_timestamp,
            evidence_source,
            evidence_data,
            content_hash
        FROM fhq_research.outcome_ledger
        WHERE outcome_domain = %s
          AND outcome_timestamp > %s
          AND outcome_timestamp < %s + INTERVAL '7 days'
        ORDER BY outcome_timestamp ASC
        LIMIT 1
    """, (pack['asset'], pack['created_at'], pack['created_at']))

    return cur.fetchone()


def settle_decision_pack(conn, pack: Dict, outcome: Optional[Dict]) -> bool:
    """
    Settle a decision pack by linking to outcome.

    If outcome exists: mark as EXECUTED with evidence
    If no outcome after 7 days: mark as EXPIRED
    """
    cur = conn.cursor()

    pack_age_hours = (datetime.now(timezone.utc) - pack['created_at'].replace(tzinfo=timezone.utc)).total_seconds() / 3600

    if outcome:
        # We have an outcome - settle as EXECUTED
        settlement_evidence = json.dumps({
            'outcome_id': str(outcome['outcome_id']),
            'outcome_value': outcome['outcome_value'],
            'outcome_timestamp': outcome['outcome_timestamp'].isoformat() if outcome['outcome_timestamp'] else None,
            'outcome_hash': outcome['content_hash'],
            'settlement_timestamp': datetime.now(timezone.utc).isoformat(),
            'pack_age_hours': round(pack_age_hours, 2)
        })
        evidence_hash = 'sha256:' + hashlib.sha256(settlement_evidence.encode()).hexdigest()

        cur.execute("""
            UPDATE fhq_learning.decision_packs
            SET execution_status = 'EXECUTED',
                evidence_hash = %s,
                filled_at = %s
            WHERE pack_id = %s
        """, (evidence_hash, outcome['outcome_timestamp'], pack['pack_id']))

        logger.info(f"SETTLED: pack={pack['pack_id'][:8]}... asset={pack['asset']} -> EXECUTED (outcome={outcome['outcome_id'][:8]}...)")

    elif pack_age_hours > 168:  # 7 days old, no outcome
        # Expire the pack
        cur.execute("""
            UPDATE fhq_learning.decision_packs
            SET execution_status = 'EXPIRED'
            WHERE pack_id = %s
        """, (pack['pack_id'],))

        logger.info(f"EXPIRED: pack={pack['pack_id'][:8]}... asset={pack['asset']} (age={pack_age_hours:.1f}h, no outcome)")
    else:
        # Still waiting for outcome
        logger.debug(f"PENDING: pack={pack['pack_id'][:8]}... asset={pack['asset']} (age={pack_age_hours:.1f}h)")
        return False

    conn.commit()
    return True


def generate_settlement_evidence(settlements: List[Dict]) -> Dict:
    """Generate evidence bundle for settlements."""
    evidence = {
        'directive': 'CEO-DIR-2026-128',
        'evidence_type': 'OUTCOME_SETTLEMENT',
        'computed_at': datetime.now(timezone.utc).isoformat(),
        'computed_by': 'STIG',
        'ec_contract': 'EC-003',
        'settlements': settlements,
        'summary': {
            'total_settled': len(settlements),
            'executed_count': sum(1 for s in settlements if s['new_status'] == 'EXECUTED'),
            'expired_count': sum(1 for s in settlements if s['new_status'] == 'EXPIRED')
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
            settled = settle_decision_pack(conn, pack, outcome)

            if settled:
                settlements.append({
                    'pack_id': str(pack['pack_id']),
                    'asset': pack['asset'],
                    'new_status': 'EXECUTED' if outcome else 'EXPIRED',
                    'outcome_id': str(outcome['outcome_id']) if outcome else None
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
            'expired': sum(1 for s in settlements if s['new_status'] == 'EXPIRED')
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
    logger.info("CEO-DIR-2026-128: Learning Velocity Restoration")
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
