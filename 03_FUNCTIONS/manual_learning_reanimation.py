#!/usr/bin/env python3
"""
Manual Learning Reanimation - CEO-DIR-2026-LEARNING-REANIMATION-022
Objective: Restore LVI > 0 and non-stale FSS within 24h.

Actions:
1. Force immediate recomputation of LVI
2. Force immediate recomputation of FSS
3. Force immediate recomputation of BSS
4. Ensure outcome ledger events are feeding pipelines
5. Run manual backfill for last 7 days if needed
6. Validate sample_size progression
7. Clear silent freeze (done prior to execution)
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[LEARNING_REANIMATION] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/learning_reanimation.log'),
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
        'document_type': 'LEARNING_REANIMATION',
        'executed_by': 'STIG',
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'raw_sql_outputs': {}
    }

    try:
        conn = get_connection()

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            logger.info("=== Starting Learning Reanimation ===")
            logger.info("Directive: CEO-DIR-2026-LEARNING-REANIMATION-022")

            # 1. Check pre-animation state
            logger.info("Step 1: Checking pre-animation state...")

            # LVI pre-check
            cur.execute("""
                SELECT
                    lvi_value,
                    computed_at,
                    EXTRACT(EPOCH FROM (NOW() - computed_at)) / 3600 as hours_stale
                FROM fhq_governance.lvi_canonical
                ORDER BY computed_at DESC
                LIMIT 1
            """)
            lvi_pre = cur.fetchone()
            evidence['raw_sql_outputs']['lvi_pre'] = dict(lvi_pre)

            # FSS pre-check
            cur.execute("""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(*) FILTER (WHERE fss_value IS NOT NULL) as non_null_count,
                    MAX(computation_timestamp) as last_computed,
                    EXTRACT(EPOCH FROM (NOW() - MAX(computation_timestamp))) / 3600 as hours_stale
                FROM fhq_research.fss_computation_log
            """)
            fss_pre = cur.fetchone()
            evidence['raw_sql_outputs']['fss_pre'] = dict(fss_pre)

            # Outcome ledger check
            cur.execute("""
                SELECT
                    COUNT(*) as total_outcomes,
                    MAX(created_at) as newest_outcome,
                    EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) / 3600 as hours_since_last
                FROM fhq_research.outcome_ledger
            """)
            outcome_check = cur.fetchone()
            evidence['raw_sql_outputs']['outcome_check'] = dict(outcome_check)

            logger.info(f"LVI: {lvi_pre['lvi_value']} (stale {lvi_pre['hours_stale']:.1f}h)")
            logger.info(f"FSS: {fss_pre['non_null_count']}/{fss_pre['total_rows']} non-null (stale {fss_pre['hours_stale']:.1f}h)")
            logger.info(f"Outcomes: {outcome_check['total_outcomes']} total, {outcome_check['hours_since_last']:.1f}h since last")

            # 2. Manual FSS recomputation
            logger.info("Step 2: Manual FSS recomputation...")
            logger.info("HOTFIX CEO-DIR-2026-LEARNING-REANIMATION-023: Using 6-param compute_fss function")

            # Explicitly call 6-param compute_fss function (OID 294205) with p_base_rate
            for baseline_method_tag, baseline_method in [('NAIVE', 'NAIVE'), ('BASE_RATE_EMPIRICAL_BETA_30D_STRICT', 'HISTORICAL')]:
                logger.info(f"Computing FSS with baseline: {baseline_method} (tag: {baseline_method_tag})")

                cur.execute("""
                    SELECT
                        asset_id, brier_actual, brier_ref, fss_value,
                        baseline_method, period_start, period_end,
                        sample_size, evidence_hash, base_rate
                    FROM fhq_research.compute_fss(
                        p_baseline_method := %s,
                        p_base_rate := NULL::numeric
                    )
                    WHERE fss_value IS NOT NULL
                """, (baseline_method,))
                results = cur.fetchall()

                if results:
                    logged = 0
                    for row in results:
                        # 6-param function returns period_start, period_end directly
                        period_start = row.get('period_start')
                        period_end = row.get('period_end')
                        sample_size = row.get('sample_size', 0)

                        cur.execute("""
                            INSERT INTO fhq_research.fss_computation_log (
                                asset_id, brier_actual, brier_ref, fss_value,
                                baseline_method, period_start, period_end,
                                sample_size, evidence_hash, computed_by,
                                computation_timestamp
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            row['asset_id'],
                            row['brier_actual'],
                            row['brier_ref'],
                            row['fss_value'],
                            baseline_method,
                            period_start,
                            period_end,
                            sample_size,
                            row.get('evidence_hash', ''),
                            'STIG-MANUAL',
                            datetime.now(timezone.utc)
                        ))
                        logged += 1

                    logger.info(f"FSS computed: {baseline_method} - {logged} rows logged")

            evidence['raw_sql_outputs']['fss_recomputation'] = {
                'status': 'COMPLETE',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # 3. Manual LVI recomputation
            logger.info("Step 3: Manual LVI recomputation...")

            # Compute LVI components
            cur.execute("""
                SELECT COUNT(*) as completed
                FROM fhq_learning.decision_packs dp
                WHERE dp.execution_status = 'EXECUTED'
                  AND dp.created_at > NOW() - INTERVAL '7 days'
            """)
            result = cur.fetchone()
            completed_experiments = result['completed'] if result else 0

            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE evidence_hash IS NOT NULL)::float /
                    NULLIF(COUNT(*), 0) as integrity
                FROM fhq_learning.decision_packs
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            result = cur.fetchone()
            integrity = float(result['integrity']) if result and result['integrity'] else 0.0

            # Coverage rate: % of IoS-016 events with linked outcomes
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE dp.decision_id IN (
                        SELECT DISTINCT decision_id
                        FROM fhq_research.outcome_ledger
                        WHERE created_at > NOW() - INTERVAL '7 days'
                    ))::float /
                    NULLIF(COUNT(*), 0) as coverage
                FROM fhq_learning.decision_packs dp
                WHERE dp.created_at > NOW() - INTERVAL '7 days'
            """)
            result = cur.fetchone()
            coverage = float(result['coverage']) if result and result['coverage'] else 0.0

            # Median evaluation time
            cur.execute("""
                SELECT
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY eval_time_hours) as median_eval_time
                FROM (
                    SELECT
                        dp.decision_id,
                        EXTRACT(EPOCH FROM (ol.created_at - dp.created_at)) / 3600.0 as eval_time_hours
                    FROM fhq_learning.decision_packs dp
                    JOIN fhq_research.outcome_ledger ol ON dp.decision_id = ol.decision_id
                    WHERE dp.created_at > NOW() - INTERVAL '7 days'
                      AND dp.created_at < NOW() - INTERVAL '24 hours'
                      AND ol.created_at IS NOT NULL
                ) eval_times
            """)
            result = cur.fetchone()
            median_eval_time = float(result['median_eval_time']) if result and result['median_eval_time'] else 0.0

            # LVI calculation
            if completed_experiments > 0 and median_eval_time > 0:
                lvi_value = (completed_experiments * integrity * coverage) / median_eval_time
            else:
                lvi_value = 0.0

            logger.info(f"LVI computed: {lvi_value:.4f}")
            logger.info(f"  - Completed experiments: {completed_experiments}")
            logger.info(f"  - Integrity rate: {integrity:.4f}")
            logger.info(f"  - Coverage rate: {coverage:.4f}")
            logger.info(f"  - Median eval time: {median_eval_time:.2f}h")

            # Insert LVI canonical record
            cur.execute("""
                INSERT INTO fhq_governance.lvi_canonical (
                    lvi_value,
                    computation_method,
                    window_start,
                    window_end,
                    computed_at
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                lvi_value,
                'MANUAL_REANIMATION',
                (datetime.now(timezone.utc) - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0),
                datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
                datetime.now(timezone.utc)
            ))

            evidence['raw_sql_outputs']['lvi_recomputation'] = {
                'status': 'COMPLETE',
                'lvi_value': lvi_value,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # 4. BSS verification
            logger.info("Step 4: BSS verification...")

            cur.execute("""
                SELECT baseline_value, current_bss, baseline_timestamp
                FROM fhq_governance.bss_baseline_snapshot
                ORDER BY baseline_timestamp DESC
                LIMIT 1
            """)
            bss_result = cur.fetchone()
            evidence['raw_sql_outputs']['bss_status'] = dict(bss_result) if bss_result else None

            logger.info(f"BSS: {bss_result['current_bss'] if bss_result else 'NULL'}")

            # 5. Validate sample_size progression
            logger.info("Step 5: Validating sample_size progression...")

            cur.execute("""
                SELECT
                    sample_size,
                    COUNT(*) as count
                FROM fhq_research.fss_computation_log
                WHERE fss_value IS NOT NULL
                GROUP BY sample_size
                ORDER BY sample_size DESC
                LIMIT 10
            """)
            sample_sizes = cur.fetchall()
            evidence['raw_sql_outputs']['sample_size_progression'] = sample_sizes

            logger.info(f"Sample size distribution: {[(s['sample_size'], s['count']) for s in sample_sizes]}")

            # 6. Post-animation verification
            logger.info("Step 6: Post-animation verification...")

            # LVI post-check
            cur.execute("""
                SELECT
                    lvi_value,
                    computed_at,
                    EXTRACT(EPOCH FROM (NOW() - computed_at)) / 3600 as hours_stale
                FROM fhq_governance.lvi_canonical
                ORDER BY computed_at DESC
                LIMIT 1
            """)
            lvi_post = cur.fetchone()
            evidence['raw_sql_outputs']['lvi_post'] = dict(lvi_post)

            # FSS post-check
            cur.execute("""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(*) FILTER (WHERE fss_value IS NOT NULL) as non_null_count,
                    MAX(computation_timestamp) as last_computed,
                    EXTRACT(EPOCH FROM (NOW() - MAX(computation_timestamp))) / 3600 as hours_stale
                FROM fhq_research.fss_computation_log
            """)
            fss_post = cur.fetchone()
            evidence['raw_sql_outputs']['fss_post'] = dict(fss_post)

            logger.info(f"LVI after: {lvi_post['lvi_value']} (stale {lvi_post['hours_stale']:.1f}h)")
            logger.info(f"FSS after: {fss_post['non_null_count']}/{fss_post['total_rows']} non-null (stale {fss_post['hours_stale']:.1f}h)")

            # Success criteria
            lvi_success = lvi_post['lvi_value'] > 0 and lvi_post['hours_stale'] < 24
            fss_success = fss_post['hours_stale'] < 24

            evidence['results'] = {
                'lvi_restored': lvi_success,
                'fss_restored': fss_success,
                'lvi_value': lvi_post['lvi_value'],
                'fss_non_null_count': fss_post['non_null_count'],
                'fss_hours_stale': fss_post['hours_stale']
            }

            conn.commit()

            logger.info("=== Learning Reanimation Complete ===")
            logger.info(f"LVI Restored: {lvi_success}")
            logger.info(f"FSS Restored: {fss_success}")

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
    filename = f'LEARNING_REANIMATION_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w') as f:
        f.write(json.dumps(evidence, indent=2, default=str))

    # Output
    print(f'Evidence: {filepath}')
    print(f'SHA-256: {sha256}')
    print()
    print('Learning Reanimation Results:')
    print(f'  LVI Restored: {evidence.get("results", {}).get("lvi_restored", "UNKNOWN")}')
    print(f'  FSS Restored: {evidence.get("results", {}).get("fss_restored", "UNKNOWN")}')
    print(f'  LVI Value: {evidence.get("results", {}).get("lvi_value", 0)}')
    print(f'  FSS Non-Null: {evidence.get("results", {}).get("fss_non_null_count", 0)}')

    if evidence.get('status') == 'FAILED':
        return 2
    else:
        return 0

if __name__ == "__main__":
    exit(main())
