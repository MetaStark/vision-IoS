#!/usr/bin/env python3
"""
Record VEGA Attestation for CEO-DIR-2026-021
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

def record_attestation():
    """Record VEGA attestation in database"""
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
                    'VEGA_ATTESTATION',
                    'CEO-DIR-2026-021',
                    'LEARNING_PIPELINE',
                    'VEGA',
                    'APPROVED',
                    'Full compliance verified. All 4 audit corrections operational. All CEO conditions met. Approved for operational deployment.',
                    %s
                )
                RETURNING action_id, initiated_at
            """, (json.dumps({
                'attestation_id': 'VEGA-ATT-2026-021-001',
                'attestation_type': 'G3_GOVERNANCE_AUDIT',
                'directive_id': 'CEO-DIR-2026-021',
                'verdict': 'APPROVED FOR OPERATIONAL DEPLOYMENT',
                'compliance_level': 'FULL COMPLIANCE',
                'governance_grade': 'A',
                'court_proof_grade': 'A+',
                'technical_implementation_grade': 'A',
                'audit_scope': {
                    'audit_corrections': 4,
                    'execution_steps': 4,
                    'migrations_verified': 4,
                    'artifacts_reviewed': 13
                },
                'key_metrics': {
                    'suppressions_classified': 193,
                    'regret_count': 31,
                    'wisdom_count': 161,
                    'match_rate_achieved': 0.995,
                    'match_rate_threshold': 0.70,
                    'margin_above_threshold': 0.295
                },
                'phase_5_status': 'CORRECTLY_LOCKED',
                'next_review_due': '2026-04-08',
                'attestation_file': '05_GOVERNANCE/PHASE3/VEGA_ATTESTATION_CEO_DIR_2026_021_20260108.json',
                'vega_signature': 'VEGA-ATT-2026-021-001-APPROVED',
                'attested_at': datetime.now(timezone.utc).isoformat()
            }),))

            result = cur.fetchone()
            action_id, initiated_at = result

            conn.commit()

            print("[OK] VEGA Attestation recorded")
            print(f"  Action ID: {action_id}")
            print(f"  Timestamp: {initiated_at}")
            print(f"  Verdict: APPROVED FOR OPERATIONAL DEPLOYMENT")
            print(f"  Compliance: FULL COMPLIANCE")
            print(f"  Grades: Governance A, Court-Proof A+, Technical A")

            return action_id

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Failed to record attestation: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    record_attestation()
