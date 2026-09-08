#!/usr/bin/env python3
"""
FAILED PACKS POST-MORTEM BACKFILL
===================================
CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024 - Directive 4, Order 4

PURPOSE: Backfill 20 FAILED packs with post_mortem records.
         Remediation (surgical) - do not touch original fail status.

CONTEXT:
- 20 FAILED packs exist from January batch
- post_mortem_settlement table is empty
- FAILED packs need post_mortem analysis records

BACKFILL LOGIC:
1. Query decision_packs with execution_status = 'FAILED'
2. Create post_mortem records for each
3. Use existing fail context if available (fail_reason_code, fail_reason_detail)
4. Do not modify original FAILED status

CONSTRAINTS:
- Only FAILED packs are processed
- Create post_mortem records with analysis_status = 'PENDING'
- No modifications to decision_packs.execution_status

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
from datetime import datetime, timezone
from typing import Optional, Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor

DAEMON_NAME = 'failed_packs_post_mortem_backfill'

logging.basicConfig(
    level=logging.INFO,
    format='[FAILED_BACKFILL] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/failed_packs_post_mortem_backfill.log'),
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


def get_failed_packs(conn) -> List[Dict]:
    """Get decision packs with FAILED status that lack post_mortem records."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            dp.pack_id,
            dp.asset,
            dp.direction,
            dp.hypothesis_uuid,
            dp.created_at,
            dp.snapshot_price,
            dp.evidence_hash as pack_evidence_hash,
            dp.execution_status,
            dp.fail_reason_code,
            dp.fail_reason_detail
        FROM fhq_learning.decision_packs dp
        WHERE dp.execution_status = 'FAILED'
          AND NOT EXISTS (
              SELECT 1 FROM fhq_learning.post_mortem_settlement pms
              WHERE pms.pack_id = dp.pack_id
          )
        ORDER BY dp.created_at ASC
    """)
    return cur.fetchall()


def create_post_mortem_record(conn, pack: Dict, fail_reason_code: str, fail_detail: str) -> Optional[str]:
    """Create post-mortem record for FAILED pack."""
    cur = conn.cursor()

    try:
        # Use existing fail context if available
        if pack.get('fail_reason_code'):
            fail_reason_code = pack['fail_reason_code']
        if pack.get('fail_reason_detail'):
            fail_detail = pack['fail_reason_detail']

        cur.execute("""
            INSERT INTO fhq_learning.post_mortem_settlement
                (pack_id, hypothesis_id, fail_reason_code, fail_reason_detail, analysis_status, original_fail_at, resolved_by)
            VALUES (%s, %s, %s, %s, 'PENDING', NOW(), 'FAILED_PACKS_BACKFILL')
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


def generate_backfill_evidence(backfills: List[Dict]) -> Dict:
    """Generate evidence bundle for backfill operations."""
    evidence = {
        'directive': 'CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024',
        'evidence_type': 'FAILED_PACKS_POST_MORTEM_BACKFILL',
        'computed_at': datetime.now(timezone.utc).isoformat(),
        'computed_by': 'STIG',
        'ec_contract': 'EC-003',
        'backfills': backfills,
        'summary': {
            'total_failed_packs': len(backfills),
            'post_mortem_created': sum(1 for b in backfills if b['pm_created']),
            'post_mortem_skipped': sum(1 for b in backfills if not b['pm_created'])
        }
    }

    evidence_str = json.dumps(evidence, sort_keys=True)
    evidence['evidence_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()[:16]

    return evidence


def run_backfill():
    """Run FAILED packs post-mortem backfill."""
    conn = get_connection()
    backfills = []

    try:
        # Get failed packs without post_mortem records
        failed_packs = get_failed_packs(conn)
        logger.info(f"Found {len(failed_packs)} FAILED packs without post_mortem records")

        for pack in failed_packs:
            # Use existing fail context if available (NULL allowed by constraint)
            fail_reason_code = pack.get('fail_reason_code') if pack.get('fail_reason_code') else 'UNKNOWN'
            fail_detail = pack.get('fail_reason_detail') if pack.get('fail_reason_detail') else f'FAILED pack from batch: {pack["asset"]} {pack["direction"]}'

            # Create post-mortem record
            pm_id = create_post_mortem_record(conn, pack, fail_reason_code, fail_detail)

            backfills.append({
                'pack_id': str(pack['pack_id']),
                'asset': pack['asset'],
                'direction': pack['direction'],
                'fail_reason_code': fail_reason_code,
                'fail_reason_detail': fail_detail,
                'pm_created': pm_id is not None,
                'pm_id': pm_id,
                'original_fail_date': pack.get('created_at').isoformat() if pack.get('created_at') else None
            })

        conn.commit()

        # Generate evidence
        if backfills:
            evidence = generate_backfill_evidence(backfills)

            # Save evidence file
            script_dir = os.path.dirname(os.path.abspath(__file__))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence_path = os.path.join(script_dir, 'evidence', f'FAILED_PACKS_POST_MORTEM_BACKFILL_{timestamp}.json')
            with open(evidence_path, 'w') as f:
                json.dump(evidence, f, indent=2)
            logger.info(f"Evidence: {evidence_path}")

        return {
            'failed_packs': len(failed_packs),
            'backfills': backfills
        }

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    """Main entry point for FAILED packs post-mortem backfill."""
    parser = argparse.ArgumentParser(description='FAILED Packs Post-Mortem Backfill')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("FAILED PACKS POST-MORTEM BACKFILL")
    logger.info("CEO-DIR-2026-LVI-SETTLEMENT-RELINK-024: Data Consistency Repair")
    logger.info("=" * 60)

    result = run_backfill()

    print(f"\nBackfill Summary:")
    print(f"  FAILED packs processed: {result['failed_packs']}")
    print(f"  Post-mortem records created: {sum(1 for b in result['backfills'] if b['pm_created'])}")
    print(f"  Post-mortem records skipped: {sum(1 for b in result['backfills'] if not b['pm_created'])}")


if __name__ == '__main__':
    main()
