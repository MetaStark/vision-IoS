"""
UMA-SYNTH-002 CEO Approval
==========================
CEO Decision: APPROVED for Shadow Validation
Date: 2026-01-17

Signal: CRYPTO_BULL_CONDITIONAL_DISCOUNT
- Trigger: BULL@95%+ on CRYPTO assets
- Action: Elevated confidence discount
- Scope: CRYPTO only (equity unaffected)

Author: STIG (EC-003) executing CEO directive
"""

import os
import json
from datetime import datetime, timezone
from uuid import uuid4
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': os.environ.get('PGPORT', '54322'),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}


def record_ceo_approval():
    """Record CEO approval of UMA-SYNTH-002."""
    conn = psycopg2.connect(**DB_CONFIG)
    timestamp = datetime.now(timezone.utc)
    approval_id = str(uuid4())

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Record in governance_actions_log
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    decision,
                    decision_rationale,
                    metadata,
                    agent_id
                ) VALUES (
                    'CEO_SIGNAL_SYNTHESIS_APPROVAL',
                    'UMA-SYNTH-002',
                    'SIGNAL_SYNTHESIS',
                    'CEO',
                    'APPROVED_SHADOW',
                    'UMA-SYNTH-002 CRYPTO_BULL_CONDITIONAL_DISCOUNT approved for shadow validation. Signal correctly combines REGIME + ASSET_CLASS, is bounded to CRYPTO only, and non-contaminating.',
                    %s,
                    'CEO'
                )
                RETURNING action_id, initiated_at
            """, (json.dumps({
                'approval_id': approval_id,
                'signal_code': 'UMA-SYNTH-002',
                'signal_name': 'CRYPTO_BULL_CONDITIONAL_DISCOUNT',
                'signal_type': 'CONDITIONAL_CONFIDENCE_DISCOUNT',
                'approval_status': 'APPROVED_SHADOW',
                'trigger_conditions': {
                    'predicted_regime': 'BULL',
                    'forecast_confidence': '>= 95%',
                    'asset_class': 'CRYPTO'
                },
                'empirical_basis': {
                    'crypto_bear_reversal': '37.50%',
                    'equity_bear_reversal': '3.29%',
                    'differential': '11.4x higher risk'
                },
                'validation': {
                    'sitc_chain': '7 nodes verified',
                    'ikea_validation': 'APPROVED',
                    'hallucination_risk': 'ZERO',
                    'bounded_scope': 'CONFIRMED'
                },
                'directive_ref': 'CEO-DIR-2026-074',
                'evidence_file': 'UMA_SYNTH_002_CRYPTO_BULL_DISCOUNT_20260117.json',
                'approved_at': timestamp.isoformat()
            }),))

            result = cur.fetchone()
            action_id = result['action_id']
            action_time = result['initiated_at']

            # Record is complete in governance_actions_log

            conn.commit()

            print("=" * 60)
            print("CEO APPROVAL RECORDED - UMA-SYNTH-002")
            print("=" * 60)
            print(f"Action ID: {action_id}")
            print(f"Approval ID: {approval_id}")
            print(f"Timestamp: {action_time}")
            print(f"Status: APPROVED_SHADOW")
            print(f"Signal: CRYPTO_BULL_CONDITIONAL_DISCOUNT")
            print("=" * 60)

            return {
                'status': 'APPROVED_SHADOW',
                'action_id': str(action_id),
                'approval_id': approval_id,
                'timestamp': action_time.isoformat() if hasattr(action_time, 'isoformat') else str(action_time)
            }

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to record approval: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    result = record_ceo_approval()
    print(json.dumps(result, indent=2, default=str))
