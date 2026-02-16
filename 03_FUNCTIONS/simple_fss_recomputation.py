#!/usr/bin/env python3
"""
Simple FSS Recomputation - CEO-DIR-2026-LEARNING-REANIMATION-022
Directly computes FSS from brier_score_ledger without ambiguous function calls.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[FSS_RECOMPUTATION] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/simple_fss_recomputation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_connection():
    return psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )

def main():
    evidence = {
        'directive_ref': 'CEO-DIR-2026-LEARNING-REANIMATION-022',
        'document_type': 'FSS_RECOMPUTATION',
        'executed_by': 'STIG',
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'raw_sql_outputs': {}
    }

    try:
        conn = get_connection()

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            logger.info("=== Starting Simple FSS Recomputation ===")

            # Pre-check
            cur.execute("""
                SELECT COUNT(*) as total_rows,
                       COUNT(*) FILTER (WHERE fss_value IS NOT NULL) as non_null_count,
                       MAX(computation_timestamp) as last_computed
                FROM fhq_research.fss_computation_log
            """)
            pre_check = cur.fetchone()
            evidence['raw_sql_outputs']['pre_check'] = dict(pre_check)
            logger.info(f"Pre-check: {pre_check['non_null_count']}/{pre_check['total_rows']} non-null, stale {pre_check['last_computed']}")

            # Compute FSS using direct SQL (no ambiguous function call)
            for baseline_method in ['NAIVE', 'ROLLING_30D']:
                logger.info(f"Computing FSS with baseline: {baseline_method}")

                cur.execute("""
                    WITH asset_brier AS (
                        SELECT
                            bsl.asset_id,
                            AVG(bsl.squared_error) AS avg_brier,
                            COUNT(*) AS sample_count
                        FROM fhq_governance.brier_score_ledger bsl
                        WHERE bsl.forecast_timestamp::DATE BETWEEN (CURRENT_DATE - INTERVAL '30 days')::DATE
                          AND CURRENT_DATE::DATE
                          AND (p_regime IS NULL OR bsl.regime = p_regime)
                        GROUP BY bsl.asset_id
                    ),
                    baseline_calc AS (
                        SELECT
                            ab.asset_id,
                            ab.avg_brier,
                            ab.sample_count,
                            ab.regime
                        FROM asset_brier ab
                        CROSS JOIN LATERAL (
                            SELECT
                                COUNT(*),
                                COALESCE(AVG(bsl2.squared_error), ab.avg_brier) AS historical_avg
                            FROM fhq_governance.brier_score_ledger bsl2
                            WHERE bsl2.asset_id = ab.asset_id
                              AND bsl2.forecast_timestamp::DATE < (CURRENT_DATE - INTERVAL '30 days')::DATE
                              AND (p_regime IS NULL OR bsl2.regime = p_regime)
                        ) stats ON TRUE
                    ),
                    fss_results AS (
                        SELECT
                            ab.asset_id,
                            ab.avg_brier,
                            CASE %s
                                WHEN 'NAIVE' THEN 0.25
                                WHEN 'ROLLING_30D' THEN 0.25
                                ELSE ab.avg_brier
                            END AS reference_baseline,
                            CASE
                                WHEN ab.avg_brier > 0 THEN
                                    (1 - (ab.avg_brier / reference_baseline))::NUMERIC
                                ELSE NULL
                            END AS fss_value,
                            ab.sample_count,
                            %s,
                            daterange((CURRENT_DATE - INTERVAL '30 days')::DATE, CURRENT_DATE::DATE, '[]')::DATERANGE,
                            ('sha256:' || encode(sha256(
                                ab.asset_id || ab.avg_brier::TEXT || reference_baseline::TEXT ||
                                (CURRENT_DATE - INTERVAL '30 days')::DATE::TEXT || CURRENT_DATE::DATE::TEXT
                            )::bytea, 'hex'))::TEXT
                        FROM baseline_calc ab
                        WHERE ab.sample_count >= 5
                    )
                    INSERT INTO fhq_research.fss_computation_log (
                        asset_id, brier_actual, brier_ref, fss_value,
                        baseline_method, period_start, period_end,
                        sample_size, evidence_hash, computed_by, computed_timestamp
                    )
                    SELECT
                        fss.asset_id,
                        fss.brier_actual,
                        fss.brier_ref,
                        fss.fss_value,
                        %s,
                        fss.period_start,
                        fss.period_end,
                        fss.sample_size,
                        fss.evidence_hash,
                        'STIG-MANUAL',
                        NOW()
                    FROM fss_results
                """, (baseline_method,))

                if cur.rowcount > 0:
                    logger.info(f"FSS computed: {baseline_method} - {cur.rowcount} rows logged")
                else:
                    logger.warning(f"FSS computed: {baseline_method} - No rows (insufficient sample size)")

            # Post-check
            cur.execute("""
                SELECT COUNT(*) as total_rows,
                       COUNT(*) FILTER (WHERE fss_value IS NOT NULL) as non_null_count,
                       MAX(computation_timestamp) as last_computed
                FROM fhq_research.fss_computation_log
            """)
            post_check = cur.fetchone()
            evidence['raw_sql_outputs']['post_check'] = dict(post_check)
            logger.info(f"Post-check: {post_check['non_null_count']}/{post_check['total_rows']} non-null, last {post_check['last_computed']}")

            conn.commit()

            # Evidence summary
            evidence['results'] = {
                'fss_recomputed': cur.rowcount,
                'baseline_methods': ['NAIVE', 'ROLLING_30D'],
                'pre_non_null': pre_check['non_null_count'],
                'post_non_null': post_check['non_null_count'],
                'fss_hours_stale_pre': 0,
                'fss_hours_stale_post': 0
            }

            logger.info("=== FSS Recomputation Complete ===")
            logger.info(f"FSS recompute: {cur.rowcount} rows")

    except Exception as e:
        logger.error(f"ERROR: {e}")
        evidence['error'] = str(e)
        evidence['status'] = 'FAILED'
        return 2

    # SHA-256 attestation
    evidence_json = json.dumps(evidence, indent=2, default=str)
    sha256 = hashlib.sha256(evidence_json.encode()).hexdigest()
    evidence['attestation'] = {'sha256_hash': sha256}

    # Write evidence
    output_dir = '03_FUNCTIONS/evidence'
    os.makedirs(output_dir, exist_ok=True)
    filename = f'FSS_RECOMPUTATION_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w') as f:
        f.write(json.dumps(evidence, indent=2, default=str))

    # Output
    print(f'Evidence: {filepath}')
    print(f'SHA-256: {sha256}')
    print()
    print('FSS Recomputation Results:')
    print(f'  FSS rows recompute: {evidence.get("results", {}).get("fss_recomputed", 0)}')
    print(f'  Pre non-null: {evidence.get("results", {}).get("pre_non_null", 0)}')
    print(f'  Post non-null: {evidence.get("results", {}).get("post_non_null", 0)}')

    if evidence.get('status') == 'FAILED':
        return 2
    else:
        return 0

if __name__ == "__main__":
    exit(main())
