#!/usr/bin/env python3
"""
RESEARCH → LEARNING BRIDGE
============================
Creates fhq_learning.v_unified_outcome_summary VIEW that aggregates both
learning and research outcome data without copying between schemas.

Pipeline position: Cross-stream bridge (connects Stream 1 and Stream 2)

Stream 1: fhq_learning (Phase 2 experiments)
  hypothesis_canon → experiment → trigger → outcome

Stream 2: fhq_research (Historical Brier calibration)
  forecast_ledger → outcome_ledger → forecast_outcome_pairs → skill_metrics

This VIEW presents a unified summary for the morning report.

Database operations:
  CREATES: fhq_learning.v_unified_outcome_summary (VIEW)
  READS:   fhq_learning.outcome_ledger, fhq_research.forecast_skill_metrics,
           fhq_research.outcome_ledger

Usage:
    python research_learning_bridge.py              # Create/replace the VIEW
    python research_learning_bridge.py --check      # Show what would be created
    python research_learning_bridge.py --verify     # Verify VIEW returns data

Author: STIG (CTO)
Date: 2026-01-29
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[RESEARCH_BRIDGE] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/research_learning_bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('research_bridge')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

VIEW_SQL = """
CREATE OR REPLACE VIEW fhq_learning.v_unified_outcome_summary AS

-- Stream 1: fhq_learning experiment outcomes (Phase 2)
-- Aggregated per experiment with win/loss stats
WITH learning_outcomes AS (
    SELECT
        'EXPERIMENT' AS source_stream,
        er.experiment_code AS source_id,
        hc.asset_class,
        COUNT(ol.outcome_id) AS outcome_count,
        SUM(CASE WHEN ol.result_bool THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN NOT ol.result_bool THEN 1 ELSE 0 END) AS losses,
        CASE
            WHEN COUNT(ol.outcome_id) > 0
            THEN ROUND(
                SUM(CASE WHEN ol.result_bool THEN 1 ELSE 0 END)::numeric
                / COUNT(ol.outcome_id), 4
            )
            ELSE NULL
        END AS hit_rate,
        AVG(ol.return_pct) AS avg_return_pct,
        AVG(ol.pnl_gross_simulated) AS avg_pnl_simulated,
        NULL::numeric AS brier_score,
        NULL::numeric AS brier_skill_score,
        NULL::numeric AS calibration_error,
        MAX(ol.created_at) AS last_outcome_at
    FROM fhq_learning.outcome_ledger ol
    JOIN fhq_learning.experiment_registry er
        ON ol.experiment_id = er.experiment_id
    JOIN fhq_learning.hypothesis_canon hc
        ON er.hypothesis_id = hc.canon_id
    GROUP BY er.experiment_code, hc.asset_class
),

-- Stream 2: fhq_research forecast skill metrics (Historical Brier calibration)
-- Aggregated per asset class from resolved forecasts
research_metrics AS (
    SELECT
        'RESEARCH_BRIER' AS source_stream,
        fsm.scope_value AS source_id,
        CASE
            WHEN fsm.scope_value LIKE 'EQUITY_%' THEN 'US_EQUITY'
            WHEN fsm.scope_value LIKE 'CRYPTO_%' THEN 'CRYPTO'
            WHEN fsm.scope_value = 'ALL_ASSETS' THEN 'ALL'
            ELSE 'OTHER'
        END AS asset_class,
        fsm.resolved_count AS outcome_count,
        ROUND(fsm.resolved_count * COALESCE(fsm.hit_rate, 0))::integer AS wins,
        (fsm.resolved_count - ROUND(fsm.resolved_count * COALESCE(fsm.hit_rate, 0)))::integer AS losses,
        fsm.hit_rate,
        NULL::numeric AS avg_return_pct,
        NULL::numeric AS avg_pnl_simulated,
        fsm.brier_score_mean AS brier_score,
        fsm.brier_skill_score,
        fsm.calibration_error,
        fsm.computed_at AS last_outcome_at
    FROM fhq_research.forecast_skill_metrics fsm
    WHERE fsm.resolved_count > 0
    AND fsm.metric_scope = 'GLOBAL'
),

-- Stream 2b: fhq_research outcome_ledger aggregate (price direction outcomes)
research_outcomes AS (
    SELECT
        'RESEARCH_OUTCOME' AS source_stream,
        rol.outcome_domain AS source_id,
        CASE
            WHEN rol.outcome_domain LIKE 'EQUITY_%' THEN 'US_EQUITY'
            WHEN rol.outcome_domain LIKE 'CRYPTO_%' THEN 'CRYPTO'
            WHEN rol.outcome_domain IN ('PRICE_DIRECTION', 'REGIME') THEN 'ALL'
            ELSE 'OTHER'
        END AS asset_class,
        COUNT(*) AS outcome_count,
        SUM(CASE WHEN rol.outcome_value IN ('CORRECT', 'UP', 'TRUE', '1') THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN rol.outcome_value NOT IN ('CORRECT', 'UP', 'TRUE', '1') THEN 1 ELSE 0 END) AS losses,
        CASE
            WHEN COUNT(*) > 0
            THEN ROUND(
                SUM(CASE WHEN rol.outcome_value IN ('CORRECT', 'UP', 'TRUE', '1') THEN 1 ELSE 0 END)::numeric
                / COUNT(*), 4
            )
            ELSE NULL
        END AS hit_rate,
        NULL::numeric AS avg_return_pct,
        NULL::numeric AS avg_pnl_simulated,
        NULL::numeric AS brier_score,
        NULL::numeric AS brier_skill_score,
        NULL::numeric AS calibration_error,
        MAX(rol.outcome_timestamp) AS last_outcome_at
    FROM fhq_research.outcome_ledger rol
    GROUP BY rol.outcome_domain
)

-- Unified output
SELECT * FROM learning_outcomes
UNION ALL
SELECT * FROM research_metrics
UNION ALL
SELECT * FROM research_outcomes
ORDER BY source_stream, asset_class, source_id;
"""


def create_view(conn, dry_run: bool = False):
    """Create or replace the unified outcome summary VIEW."""
    if dry_run:
        logger.info("DRY RUN — VIEW SQL:")
        logger.info(VIEW_SQL)
        return True

    with conn.cursor() as cur:
        cur.execute(VIEW_SQL)
    conn.commit()
    logger.info("Created/replaced fhq_learning.v_unified_outcome_summary")
    return True


def verify_view(conn) -> dict:
    """Verify the VIEW returns data from both streams."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if view exists
        cur.execute("""
            SELECT COUNT(*) as cnt
            FROM information_schema.views
            WHERE table_schema = 'fhq_learning'
            AND table_name = 'v_unified_outcome_summary'
        """)
        exists = cur.fetchone()['cnt'] > 0

        if not exists:
            logger.error("VIEW does not exist")
            return {'exists': False}

        # Query the view
        cur.execute("""
            SELECT source_stream, COUNT(*) as rows,
                   SUM(outcome_count) as total_outcomes,
                   AVG(hit_rate) as avg_hit_rate
            FROM fhq_learning.v_unified_outcome_summary
            GROUP BY source_stream
            ORDER BY source_stream
        """)
        streams = cur.fetchall()

        # Sample data
        cur.execute("""
            SELECT *
            FROM fhq_learning.v_unified_outcome_summary
            LIMIT 10
        """)
        sample = cur.fetchall()

    result = {
        'exists': True,
        'streams': [],
        'sample_rows': len(sample)
    }

    for s in streams:
        stream_info = {
            'source_stream': s['source_stream'],
            'row_count': s['rows'],
            'total_outcomes': int(s['total_outcomes'] or 0),
            'avg_hit_rate': float(s['avg_hit_rate']) if s['avg_hit_rate'] else None
        }
        result['streams'].append(stream_info)
        logger.info(f"  {s['source_stream']}: {s['rows']} rows, "
                     f"{int(s['total_outcomes'] or 0)} outcomes, "
                     f"avg hit_rate={s['avg_hit_rate']}")

    return result


def run_bridge(dry_run: bool = False, verify_only: bool = False):
    """Main entry."""
    logger.info("=" * 60)
    logger.info("RESEARCH → LEARNING BRIDGE")
    logger.info(f"  dry_run={dry_run}, verify_only={verify_only}")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        if verify_only:
            result = verify_view(conn)
            if result['exists']:
                print("\n=== VIEW VERIFICATION ===\n")
                for s in result['streams']:
                    print(f"  {s['source_stream']}: "
                          f"{s['row_count']} rows, "
                          f"{s['total_outcomes']} outcomes, "
                          f"hit_rate={s['avg_hit_rate']}")
                print(f"\n  VIEW is operational with {result['sample_rows']} sample rows")
            else:
                print("\n  VIEW does not exist. Run without --verify to create.")
            return

        # Create the VIEW
        success = create_view(conn, dry_run=dry_run)

        if success and not dry_run:
            # Verify
            logger.info("Verifying VIEW...")
            result = verify_view(conn)

            # Evidence
            evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
            os.makedirs(evidence_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence = {
                'executed_at': datetime.now(timezone.utc).isoformat(),
                'executed_by': 'STIG_RESEARCH_BRIDGE',
                'action': 'CREATE_VIEW',
                'view_name': 'fhq_learning.v_unified_outcome_summary',
                'verification': result
            }
            evidence_path = os.path.join(evidence_dir,
                                         f'RESEARCH_LEARNING_BRIDGE_{ts}.json')
            with open(evidence_path, 'w') as f:
                json.dump(evidence, f, indent=2, default=str)
            logger.info(f"Evidence: {evidence_path}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Research → Learning Bridge')
    parser.add_argument('--check', action='store_true', help='Dry run')
    parser.add_argument('--verify', action='store_true', help='Verify VIEW')
    args = parser.parse_args()

    run_bridge(dry_run=args.check, verify_only=args.verify)


if __name__ == '__main__':
    main()
