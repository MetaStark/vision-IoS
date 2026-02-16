#!/usr/bin/env python3
"""
OUTCOME PACK LINK BACKFILL
=========================
CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024: Data Consistency Repair

PURPOSE: Backfill outcome_pack_link entries for EXECUTED decision packs.
         Resolves data inconsistency from pre-DIR-024 settlement logic.

CONTEXT:
- Pre-DIR-024: outcome_settlement_daemon used direct outcome_ledger queries
- Post-DIR-024: outcome_settlement_daemon requires outcome_pack_link layer
- Current state: 11 packs marked EXECUTED, 0 outcome_pack_link entries

BACKFILL LOGIC:
1. Query decision_packs with execution_status = 'EXECUTED'
2. Match to outcome_ledger entries by asset and timestamp window (±7 days)
3. Create outcome_pack_link entries with link_method = 'POST_MORTEM'
4. Preserve audit trail with evidence_hash verification

CONSTRAINTS:
- Only EXECUTED packs are backfilled (FAILED and ORPHANED_OUTCOME_MISSING excluded)
- One link per pack (enforced by UNIQUE constraint on outcome_pack_link.pack_id)
- No modifications to existing EXECUTED status (state preservation)

Authority: CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024
Classification: G4_DATA_REPAIR
Executor: STIG (EC-003)
"""

import os
import sys
import json
import hashlib
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor

DAEMON_NAME = 'outcome_pack_link_backfill'

logging.basicConfig(
    level=logging.INFO,
    format='[LINK_BACKFILL] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/outcome_pack_link_backfill.log'),
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


def get_executed_packs(conn) -> List[Dict]:
    """Get decision packs with EXECUTED status that lack outcome_pack_link entries."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            dp.pack_id,
            dp.asset,
            dp.direction,
            dp.hypothesis_uuid,
            dp.created_at,
            dp.snapshot_price,
            dp.evidence_hash as pack_evidence_hash
        FROM fhq_learning.decision_packs dp
        WHERE dp.execution_status = 'EXECUTED'
          AND NOT EXISTS (
              SELECT 1 FROM fhq_learning.outcome_pack_link opl
              WHERE opl.pack_id = dp.pack_id
          )
        ORDER BY dp.created_at ASC
    """)
    return cur.fetchall()


def find_matching_outcome(conn, pack: Dict) -> Optional[Dict]:
    """Find outcome_ledger entry that matches this decision pack."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Match by asset (outcome_domain) and timestamp window (±7 days)
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
          AND outcome_timestamp >= %s - INTERVAL '7 days'
          AND outcome_timestamp <= %s + INTERVAL '7 days'
        ORDER BY ABS(EXTRACT(EPOCH FROM (outcome_timestamp - %s))) ASC
        LIMIT 1
    """, (pack['asset'], pack['created_at'], pack['created_at'], pack['created_at']))

    return cur.fetchone()


def create_outcome_pack_link(conn, pack: Dict, outcome: Dict) -> Optional[str]:
    """Create outcome_pack_link entry for EXECUTED pack."""
    cur = conn.cursor()

    try:
        # Check if outcome is already linked to another pack
        cur.execute("""
            SELECT pack_id FROM fhq_learning.outcome_pack_link
            WHERE outcome_id = %s
        """, (outcome['outcome_id'],))

        existing_link = cur.fetchone()
        if existing_link:
            logger.warning(f"Outcome already linked: pack={pack['pack_id'][:8]}... cannot link to outcome={outcome['outcome_id'][:8]}... (linked to {existing_link[0][:8]}...)")
            return None

        cur.execute("""
            INSERT INTO fhq_learning.outcome_pack_link
                (outcome_id, pack_id, hypothesis_id, link_method, link_confidence, linked_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (pack_id) DO NOTHING
            RETURNING link_id
        """, (
            outcome['outcome_id'],
            pack['pack_id'],
            pack.get('hypothesis_uuid'),
            'POST_MORTEM',  # Backfill, not SETTLEMENT
            0.8  # Medium confidence due to timestamp-based matching
        ))

        result = cur.fetchone()
        if result:
            link_id = result[0]
            logger.info(f"Created link: pack={pack['pack_id'][:8]}... asset={pack['asset']} -> outcome={outcome['outcome_id'][:8]}...")
            return str(link_id)
        return None

    except Exception as e:
        logger.error(f"Failed to create link for pack={pack['pack_id'][:8]}...: {e}")
        return None


def generate_backfill_evidence(backfills: List[Dict]) -> Dict:
    """Generate evidence bundle for backfill operations."""
    evidence = {
        'directive': 'CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024',
        'evidence_type': 'OUTCOME_PACK_LINK_BACKFILL',
        'computed_at': datetime.now(timezone.utc).isoformat(),
        'computed_by': 'STIG',
        'ec_contract': 'EC-003',
        'backfills': backfills,
        'summary': {
            'total_executed_packs': len(backfills),
            'links_created': sum(1 for b in backfills if b['link_created']),
            'links_skipped': sum(1 for b in backfills if not b['link_created'])
        }
    }

    evidence_str = json.dumps(evidence, sort_keys=True)
    evidence['evidence_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()[:16]

    return evidence


def run_backfill():
    """Run outcome_pack_link backfill."""
    conn = get_connection()
    backfills = []

    try:
        # Get executed packs without links
        executed_packs = get_executed_packs(conn)
        logger.info(f"Found {len(executed_packs)} EXECUTED packs without outcome_pack_link entries")

        for pack in executed_packs:
            # Find matching outcome
            outcome = find_matching_outcome(conn, pack)

            if outcome:
                # Create outcome_pack_link entry
                try:
                    link_id = create_outcome_pack_link(conn, pack, outcome)

                    backfills.append({
                        'pack_id': str(pack['pack_id']),
                        'asset': pack['asset'],
                        'outcome_id': str(outcome['outcome_id']),
                        'outcome_timestamp': outcome['outcome_timestamp'].isoformat() if outcome['outcome_timestamp'] else None,
                        'link_created': link_id is not None,
                        'link_id': link_id,
                        'link_method': 'POST_MORTEM' if link_id else None
                    })
                except Exception as e:
                    # Log error but continue processing other packs
                    logger.error(f"Failed to process pack={pack['pack_id'][:8]}...: {e}")
                    backfills.append({
                        'pack_id': str(pack['pack_id']),
                        'asset': pack['asset'],
                        'outcome_id': str(outcome['outcome_id']) if outcome else None,
                        'outcome_timestamp': outcome['outcome_timestamp'].isoformat() if outcome and outcome['outcome_timestamp'] else None,
                        'link_created': False,
                        'link_id': None,
                        'link_method': None,
                        'error': str(e)
                    })
            else:
                backfills.append({
                    'pack_id': str(pack['pack_id']),
                    'asset': pack['asset'],
                    'outcome_id': None,
                    'outcome_timestamp': None,
                    'link_created': False,
                    'link_id': None,
                    'link_method': None,
                    'reason': 'No matching outcome found within ±7 day window'
                })

        conn.commit()

        # Generate evidence
        if backfills:
            evidence = generate_backfill_evidence(backfills)

            # Save evidence file
            script_dir = os.path.dirname(os.path.abspath(__file__))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence_path = os.path.join(script_dir, 'evidence', f'OUTCOME_PACK_LINK_BACKFILL_{timestamp}.json')
            with open(evidence_path, 'w') as f:
                json.dump(evidence, f, indent=2)
            logger.info(f"Evidence: {evidence_path}")

        return {
            'executed_packs': len(executed_packs),
            'backfills': backfills
        }

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    """Main entry point for outcome_pack_link backfill."""
    parser = argparse.ArgumentParser(description='Outcome Pack Link Backfill')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("OUTCOME PACK LINK BACKFILL")
    logger.info("CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024: Data Consistency Repair")
    logger.info("=" * 60)

    result = run_backfill()

    print(f"\nBackfill Summary:")
    print(f"  EXECUTED packs processed: {result['executed_packs']}")
    print(f"  Links created: {sum(1 for b in result['backfills'] if b['link_created'])}")
    print(f"  Links skipped: {sum(1 for b in result['backfills'] if not b['link_created'])}")


if __name__ == '__main__':
    main()
