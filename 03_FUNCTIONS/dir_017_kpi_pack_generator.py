#!/usr/bin/env python3
"""
CEO-DIR-2026-OUTCOME-THROUGHPUT-ACTIVATION-017
KPI Pack Generator (Directive 5) - Operational Only
--
Purpose: Generate simple KPI pack every 6 hours.
No new metrics. Just progress tracking.
"""

import os
import sys
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres'
}

DAEMON_NAME = 'dir_017_kpi_pack_generator'
INTERVAL_HOURS = 6

LOG_FILE = r'C:\fhq-market-system\vision-ios\03_FUNCTIONS\dir_017_kpi_pack_generator.log'

logging.basicConfig(
    level=logging.INFO,
    format=f'[{DAEMON_NAME}] %(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def generate_kpi_pack(conn):
    """Generate KPI pack with simple progress metrics."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Active hypotheses
        cur.execute("""
            SELECT COUNT(*) as active_hypotheses
            FROM fhq_learning.hypothesis_canon
            WHERE status IN ('ACTIVE', 'PRE_TIER', 'TIMEOUT_PENDING');
        """)
        active_hypotheses = cur.fetchone()['active_hypotheses']

        # Outcomes last 24h
        cur.execute("""
            SELECT COUNT(*) as outcomes_24h
            FROM fhq_learning.expectation_outcome_ledger
            WHERE recorded_at >= NOW() - INTERVAL '24 hours';
        """)
        outcomes_24h = cur.fetchone()['outcomes_24h']

        # Avg time-to-outcome
        cur.execute("""
            SELECT AVG(evaluation_hours) as avg_time_to_outcome
            FROM fhq_learning.expectation_outcome_ledger
            WHERE evaluation_hours IS NOT NULL
              AND recorded_at >= NOW() - INTERVAL '7 days';
        """)
        avg_time_to_outcome = cur.fetchone()['avg_time_to_outcome']

        # Hypotheses with >=10 outcomes
        cur.execute("""
            SELECT COUNT(*) as hypotheses_ge_10
            FROM (
                SELECT hypothesis_id, COUNT(*) as outcome_count
                FROM fhq_learning.expectation_outcome_ledger
                WHERE recorded_at >= NOW() - INTERVAL '30 days'
                GROUP BY hypothesis_id
                HAVING COUNT(*) >= 10
            ) t;
        """)
        hypotheses_ge_10 = cur.fetchone()['hypotheses_ge_10']

        # Hypotheses with >=30 outcomes
        cur.execute("""
            SELECT COUNT(*) as hypotheses_ge_30
            FROM (
                SELECT hypothesis_id, COUNT(*) as outcome_count
                FROM fhq_learning.expectation_outcome_ledger
                WHERE recorded_at >= NOW() - INTERVAL '30 days'
                GROUP BY hypothesis_id
                HAVING COUNT(*) >= 30
            ) t;
        """)
        hypotheses_ge_30 = cur.fetchone()['hypotheses_ge_30']

        # Top1_share (from semantic diversity blocks)
        cur.execute("""
            SELECT MAX(current_pct) as top1_share
            FROM fhq_learning.semantic_diversity_blocks
            WHERE blocked_at >= NOW() - INTERVAL '24 hours';
        """)
        result = cur.fetchone()
        top1_share = result['top1_share'] if result['top1_share'] else 0

        kpi_pack = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "daemon": DAEMON_NAME,
            "interval_hours": INTERVAL_HOURS,
            "active_hypotheses": active_hypotheses,
            "outcomes_last_24h": outcomes_24h,
            "avg_time_to_outcome_hours": round(avg_time_to_outcome, 2) if avg_time_to_outcome else None,
            "hypotheses_with_ge_10_outcomes": hypotheses_ge_10,
            "hypotheses_with_ge_30_outcomes": hypotheses_ge_30,
            "top1_share_pct": round(top1_share, 2) if top1_share else 0
        }

        return kpi_pack


def save_kpi_pack(kpi_pack):
    """Save KPI pack to evidence directory."""
    evidence_dir = r'C:\fhq-market-system\vision-ios\03_FUNCTIONS\evidence'
    os.makedirs(evidence_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"DIR_017_KPI_PACK_{timestamp}.json"
    filepath = os.path.join(evidence_dir, filename)

    with open(filepath, 'w') as f:
        json.dump(kpi_pack, f, indent=2)

    logger.info(f"KPI Pack saved to {filepath}")
    return filepath


def main():
    logger.info("DIR-017 KPI Pack Generator starting")

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        kpi_pack = generate_kpi_pack(conn)
        logger.info(f"KPI Pack generated:")
        logger.info(f"  Active hypotheses: {kpi_pack['active_hypotheses']}")
        logger.info(f"  Outcomes last 24h: {kpi_pack['outcomes_last_24h']}")
        logger.info(f"  Avg time-to-outcome: {kpi_pack['avg_time_to_outcome_hours']}h")
        logger.info(f"  Hypotheses with ≥10 outcomes: {kpi_pack['hypotheses_with_ge_10_outcomes']}")
        logger.info(f"  Hypotheses with ≥30 outcomes: {kpi_pack['hypotheses_with_ge_30_outcomes']}")
        logger.info(f"  Top1 share: {kpi_pack['top1_share_pct']}%")

        save_kpi_pack(kpi_pack)

        conn.commit()
        logger.info("DIR-017 KPI Pack Complete ===")

    except Exception as e:
        logger.error(f"DIR-017 KPI Pack Failed: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
