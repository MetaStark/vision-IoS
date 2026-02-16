#!/usr/bin/env python3
"""
Learning Reanimation Evidence - CEO-DIR-2026-LEARNING-REANIMATION-022 & 023
Evidence-grade reanimation after hotfix and hardening.
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
    format='[LEARNING_REANIMATION_EVIDENCE] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/learning_reanimation_evidence.log'),
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
        'directive_ref': 'CEO-DIR-2026-LEARNING-REANIMATION-023',
        'hotfix_applied': 'CEO-DIR-2026-LEARNING-REANIMATION-023-P0',
        'hardening_applied': 'CEO-DIR-2026-LEARNING-REANIMATION-023-P1',
        'document_type': 'LEARNING_REANIMATION_EVIDENCE',
        'executed_by': 'STIG',
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'raw_sql_outputs': {}
    }

    try:
        conn = get_connection()

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            logger.info("=== Learning Reanimation Evidence Collection ===")

            # 1. Verify hotfix: compute_fss function uniqueness
            logger.info("Step 1: Verifying hotfix...")
            cur.execute("""
                SELECT pg_proc.oid, proname, pg_get_function_arguments(pg_proc.oid) AS parameters
                FROM pg_proc
                JOIN pg_namespace n ON pg_proc.pronamespace = n.oid
                WHERE n.nspname = 'fhq_research' AND proname = 'compute_fss'
                ORDER BY pg_proc.oid
            """)
            functions = cur.fetchall()
            evidence['raw_sql_outputs']['compute_fss_functions'] = [dict(f) for f in functions]
            hotfix_success = len(functions) == 1 and functions[0]['parameters'].count('p_base_rate') > 0
            evidence['hotfix_verification'] = {
                'unique_function_exists': len(functions) == 1,
                'has_p_base_rate_param': functions[0]['parameters'].count('p_base_rate') > 0 if functions else False,
                'hotfix_success': hotfix_success
            }
            logger.info(f"Hotfix verified: {hotfix_success}")

            # 2. Test canonical call
            logger.info("Step 2: Testing canonical call...")
            cur.execute("""
                SELECT COUNT(*) as count
                FROM fhq_research.compute_fss(
                    p_baseline_method := 'NAIVE',
                    p_base_rate := NULL::numeric
                )
                WHERE fss_value IS NOT NULL
            """)
            test_result = cur.fetchone()
            evidence['canonical_call_test'] = {
                'called_successfully': True,
                'returned_rows': test_result['count'] if test_result else 0
            }
            logger.info(f"Canonical call test: {test_result['count']} rows")

            # 3. Verify FSS staleness (< 60 minutes)
            logger.info("Step 3: Verifying FSS staleness...")
            cur.execute("""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(*) FILTER (WHERE fss_value IS NOT NULL) as non_null_count,
                    MAX(computation_timestamp) as last_computed,
                    EXTRACT(EPOCH FROM (NOW() - MAX(computation_timestamp))) / 60 as minutes_stale
                FROM fhq_research.fss_computation_log
            """)
            fss_status = cur.fetchone()
            evidence['raw_sql_outputs']['fss_status'] = dict(fss_status)
            fss_acceptance = fss_status['minutes_stale'] < 60
            evidence['fss_acceptance'] = {
                'non_null_count': fss_status['non_null_count'],
                'minutes_stale': float(fss_status['minutes_stale']),
                'within_60min': fss_acceptance
            }
            logger.info(f"FSS stale: {fss_status['minutes_stale']:.1f}m (accept: {fss_acceptance})")

            # 4. Verify gate invariant: sample_size < 50 → fss_value IS NULL
            logger.info("Step 4: Verifying gate invariant...")
            cur.execute("""
                SELECT COUNT(*) as violation_count
                FROM fhq_research.fss_computation_log
                WHERE sample_size < 50 AND fss_value IS NOT NULL
            """)
            gate_check = cur.fetchone()
            gate_invariant_holds = gate_check['violation_count'] == 0
            evidence['gate_invariant'] = {
                'violation_count': gate_check['violation_count'],
                'invariant_holds': gate_invariant_holds,
                'rule': 'sample_size < 50 → fss_value IS NULL'
            }
            logger.info(f"Gate invariant: {gate_invariant_holds} (violations: {gate_check['violation_count']})")

            # 5. LVI bottleneck documentation
            logger.info("Step 5: Documenting LVI bottleneck...")
            cur.execute("""
                SELECT
                    lvi_value,
                    computed_at,
                    EXTRACT(EPOCH FROM (NOW() - computed_at)) / 3600 as hours_stale
                FROM fhq_governance.lvi_canonical
                ORDER BY computed_at DESC
                LIMIT 1
            """)
            lvi_status = cur.fetchone()
            evidence['raw_sql_outputs']['lvi_status'] = dict(lvi_status) if lvi_status else None

            # Check completed experiments
            cur.execute("""
                SELECT COUNT(*) as completed
                FROM fhq_learning.decision_packs
                WHERE execution_status = 'EXECUTED'
                  AND created_at > NOW() - INTERVAL '7 days'
            """)
            exp_result = cur.fetchone()
            evidence['lvi_bottleneck'] = {
                'lvi_value': lvi_status['lvi_value'] if lvi_status else 0.0,
                'hours_stale': float(lvi_status['hours_stale']) if lvi_status else None,
                'completed_experiments_7d': exp_result['completed'] if exp_result else 0,
                'bottleneck_identified': exp_result['completed'] == 0 if exp_result else False,
                'bottleneck_description': 'LVI = 0 without completed experiments'
            }
            logger.info(f"LVI bottleneck: {exp_result['completed'] if exp_result else 0} completed experiments")

            # Overall acceptance verdict
            evidence['overall_acceptance'] = {
                'hotfix_p0': hotfix_success,
                'canonical_call': True,
                'fss_within_60min': fss_acceptance,
                'gate_invariant': gate_invariant_holds,
                'all_acceptance_tests_passed': hotfix_success and fss_acceptance and gate_invariant_holds
            }

            conn.commit()
            logger.info("=== Evidence Collection Complete ===")

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
    filename = f'LEARNING_REANIMATION_EVIDENCE_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w') as f:
        f.write(json.dumps(evidence, indent=2, default=str))

    # Output
    print(f'Evidence: {filepath}')
    print(f'SHA-256: {sha256}')
    print()
    print('Acceptance Tests:')
    print(f'  Hotfix (P0): {evidence.get("overall_acceptance", {}).get("hotfix_p0", "UNKNOWN")}')
    print(f'  Canonical Call: {evidence.get("overall_acceptance", {}).get("canonical_call", "UNKNOWN")}')
    print(f'  FSS < 60min: {evidence.get("overall_acceptance", {}).get("fss_within_60min", "UNKNOWN")}')
    print(f'  Gate Invariant: {evidence.get("overall_acceptance", {}).get("gate_invariant", "UNKNOWN")}')
    print(f'  ALL PASSED: {evidence.get("overall_acceptance", {}).get("all_acceptance_tests_passed", "UNKNOWN")}')
    print()
    print('LVI Bottleneck:')
    print(f'  Completed experiments (7d): {evidence.get("lvi_bottleneck", {}).get("completed_experiments_7d", 0)}')
    print(f'  LVI Value: {evidence.get("lvi_bottleneck", {}).get("lvi_value", 0)}')
    print(f'  Bottleneck: {evidence.get("lvi_bottleneck", {}).get("bottleneck_identified", False)}')

    if evidence.get('status') == 'FAILED':
        return 2
    else:
        return 0

if __name__ == "__main__":
    exit(main())
