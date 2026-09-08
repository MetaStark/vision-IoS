#!/usr/bin/env python3
"""
Record Operational Deployment for CEO-DIR-2026-021
"""

import os
import json
import psycopg2
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

def record_deployment():
    """Record operational deployment in database"""
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cur:
            # Record in governance_actions_log
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    decision,
                    decision_rationale,
                    metadata
                ) VALUES (
                    'OPERATIONAL_DEPLOYMENT',
                    'CEO-DIR-2026-021',
                    'LEARNING_PIPELINE',
                    'STIG',
                    'DEPLOYED',
                    'First live execution successful. Orchestrator integration operational. All CEO conditions met. VEGA attestation approved.',
                    %s
                )
                RETURNING action_id, initiated_at
            """, (json.dumps({
                'deployment_id': 'DEPLOY-CEO-DIR-2026-021-001',
                'directive_id': 'CEO-DIR-2026-021',
                'attestation_id': 'VEGA-ATT-2026-021-001',
                'first_live_execution': {
                    'run_id': 'd15468ec-5918-4627-9394-268ee5201710',
                    'iso_week': '2026-W2',
                    'execution_status': 'SUCCESS',
                    'execution_duration_ms': 508,
                    'lessons_detected': 1,
                    'evidence_id': '7a64e2f3-7816-4cfa-8346-9540e02db7b9'
                },
                'orchestrator_integration': {
                    'task_id': '1fc6c782-605d-47de-ab22-851da56abc4c',
                    'task_name': 'weekly_learning_orchestrator',
                    'enabled': True,
                    'orchestrator_position': '8/39'
                },
                'vega_grades': {
                    'governance_compliance': 'A',
                    'court_proof_evidence': 'A+',
                    'technical_implementation': 'A'
                },
                'key_metrics': {
                    'suppressions_classified': 193,
                    'regret_count': 31,
                    'wisdom_count': 161,
                    'match_rate_achieved': 0.995
                },
                'phase_5_status': 'LOCKED',
                'operational_readiness': 'READY',
                'next_review_due': '2026-04-08',
                'evidence_file': '03_FUNCTIONS/evidence/CEO_DIR_2026_021_OPERATIONAL_DEPLOYMENT_20260108.json',
                'stig_signature': 'STIG-DEPLOY-2026-021-OPERATIONAL',
                'deployed_at': datetime.now(timezone.utc).isoformat()
            }),))

            result = cur.fetchone()
            action_id, initiated_at = result

            conn.commit()

            print("[OK] Operational Deployment recorded")
            print(f"  Action ID: {action_id}")
            print(f"  Timestamp: {initiated_at}")
            print(f"  Status: OPERATIONAL")
            print(f"  First Live Execution: SUCCESS (run_id: d15468ec-5918-4627-9394-268ee5201710)")
            print(f"  Orchestrator Integration: COMPLETE (task_id: 1fc6c782-605d-47de-ab22-851da56abc4c)")
            print(f"  VEGA Grades: Governance A, Court-Proof A+, Technical A")

            return action_id

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Failed to record deployment: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    record_deployment()
