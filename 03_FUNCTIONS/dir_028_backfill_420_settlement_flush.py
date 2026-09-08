#!/usr/bin/env python3
"""
420 Settlement Flush - Backfill Execution
CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028 Directive 3

Purpose: Execute controlled backfill to terminalize 420 linked BRIDGE outcomes
         into outcome_settlement_log.

Success criteria: outcome_settlement_log increases from 0 to ≥ 400
                  within first 2 daemon cycles.

Authority: CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028
Classification: G4_PRODUCTION_DAEMON
Executor: STIG (EC-003)
Version: 1.0.0
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[SETTLEMENT_BACKFILL] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/dir_028_backfill.log'),
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


def get_outcome_pack_links(conn) -> List[Dict]:
    """Get outcome_pack_link entries for BRIDGE experiments."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT
            opl.link_id,
            opl.outcome_id,
            opl.pack_id,
            opl.hypothesis_id,
            opl.link_method,
            opl.link_confidence,
            ol.outcome_domain,
            ol.outcome_value,
            ol.outcome_timestamp,
            dp.execution_status as pack_status,
            dp.created_at as pack_created_at
        FROM fhq_learning.outcome_pack_link opl
        JOIN fhq_learning.decision_packs dp ON opl.pack_id = dp.pack_id
        JOIN fhq_research.outcome_ledger ol ON opl.outcome_id = ol.outcome_id
        WHERE opl.link_method = 'POST_MORTEM'
          AND dp.execution_status = 'EXECUTED'
        ORDER BY dp.created_at DESC
        LIMIT 500
    """)
    return cur.fetchall()


def check_settlement_exists(conn, pack_id: str) -> bool:
    """Check if settlement already exists for this pack."""
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) as count
        FROM fhq_learning.outcome_settlement_log
        WHERE pack_id = %s
    """, (pack_id,))
    return cur.fetchone()[0] > 0


def create_settlement_backfill(conn, link: Dict) -> Optional[str]:
    """Create settlement log entry for backfilled outcome."""
    cur = conn.cursor()

    try:
        # Create settlement log entry
        evidence_data = {
            'backfill': True,
            'backfill_timestamp': datetime.now(timezone.utc).isoformat(),
            'backfill_directive': 'CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028',
            'original_outcome_timestamp': link['outcome_timestamp'].isoformat() if link['outcome_timestamp'] else None,
            'link_method': link['link_method'],
            'link_confidence': float(link['link_confidence'])
        }

        evidence_payload = json.dumps(evidence_data, sort_keys=True)
        evidence_hash = 'sha256:' + hashlib.sha256(evidence_payload.encode()).hexdigest()

        cur.execute("""
            INSERT INTO fhq_learning.outcome_settlement_log (
                pack_id, prior_status, new_status, outcome_id,
                settlement_reason_code, settlement_evidence_hash, settled_at, settled_by
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
            RETURNING settlement_id
        """, (
            link['pack_id'],
            link['pack_status'] if link['pack_status'] else 'UNKNOWN',
            'EXECUTED',
            link['outcome_id'],
            'BACKFILL_POST_MORTEM',
            evidence_hash,
            'dir_028_backfill_420_flush'
        ))

        result = cur.fetchone()
        if result:
            log_id = result[0]
            logger.info(f"Backfilled: pack={link['pack_id'][:8]}... -> settlement_id={log_id[:8]}... (outcome={link['outcome_id'][:8]}...)")
            return str(log_id)
        return None

    except Exception as e:
        logger.error(f"Failed to backfill pack={link['pack_id'][:8]}...: {e}")
        return None


def execute_backfill() -> Dict:
    """Execute the 420 Settlement Flush."""
    conn = get_connection()
    settlements = []
    skipped = 0

    try:
        # Get outcome_pack_link entries
        links = get_outcome_pack_links(conn)
        logger.info(f"Found {len(links)} outcome_pack_link entries for backfill")

        for link in links:
            # Check if settlement already exists
            if check_settlement_exists(conn, link['pack_id']):
                skipped += 1
                logger.debug(f"Skipping: pack={link['pack_id'][:8]}... (already settled)")
                continue

            # Create settlement log entry
            log_id = create_settlement_backfill(conn, link)

            if log_id:
                settlements.append({
                    'pack_id': str(link['pack_id']),
                    'outcome_id': str(link['outcome_id']),
                    'settlement_log_id': log_id,
                    'outcome_domain': link['outcome_domain'],
                    'link_method': link['link_method']
                })

        conn.commit()

        # Generate evidence
        evidence = {
            'directive': 'CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028',
            'directive_subsection': '3-Backfill-Execution',
            'evidence_type': 'SETTLEMENT_BACKFILL_420_FLUSH',
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG',
            'ec_contract': 'EC-003',
            'backfill_summary': {
                'total_links_found': len(links),
                'settlements_created': len(settlements),
                'skipped': skipped,
                'target': 400,
                'success': len(settlements) >= 400
            },
            'settlements': settlements
        }

        # Save evidence file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(script_dir, 'evidence', f'SETTLEMENT_BACKFILL_420_{timestamp}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        logger.info(f"Evidence: {evidence_path}")

        # Log summary
        logger.info("=" * 60)
        logger.info("BACKFILL SUMMARY")
        logger.info(f"Total links found: {len(links)}")
        logger.info(f"Settlements created: {len(settlements)}")
        logger.info(f"Skipped (already settled): {skipped}")
        logger.info(f"Success (≥ 400): {len(settlements) >= 400}")
        logger.info("=" * 60)

        if len(settlements) < 400:
            logger.warning(f"BACKFILL TARGET NOT MET: {len(settlements)} / 400")
            evidence['target_met'] = False
        else:
            logger.info("BACKFILL TARGET MET")
            evidence['target_met'] = True

        return evidence

    except Exception as e:
        logger.error(f"Backfill execution failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("420 SETTLEMENT FLUSH - BACKFILL EXECUTION")
    logger.info("CEO-DIR-2026-SYSTEM-PRODUCTIONALIZATION-028")
    logger.info("=" * 60)

    try:
        evidence = execute_backfill()

        # Exit with appropriate code
        if evidence['backfill_summary']['success']:
            print(f"\nSUCCESS: {evidence['backfill_summary']['settlements_created']} settlements created")
            sys.exit(0)
        else:
            print(f"\nWARNING: Target not met - {evidence['backfill_summary']['settlements_created']} / 400")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
