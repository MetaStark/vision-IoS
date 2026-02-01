"""
CEO-DIR-2026-077 Final Action - Canonicalization Pack Order
"""

import os
import json
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': os.environ.get('PGPORT', '54322'),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

conn = psycopg2.connect(**DB_CONFIG)
timestamp = datetime.now(timezone.utc)

try:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        metadata = {
            'directive_ref': 'CEO-DIR-2026-077',
            'pack_contents_required': [
                'Reference Epoch 001 evidence',
                'Exact trigger conditions (STRESS, 99%+, EQUITY only)',
                'Explicit non-applicability conditions',
                'Governance constraints (shadow to paper to micro only, staged)'
            ],
            'authorization_note': 'This does NOT authorize execution. Prepares board decision.',
            'vega_g3_audit_required': True,
            'timestamp': timestamp.isoformat()
        }

        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type, action_target, action_target_type,
                initiated_by, decision, decision_rationale, metadata, agent_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING action_id
        """, (
            'PREPARATION_ORDER_ISSUED',
            'G4_CANONICALIZATION_PACK',
            'PREPARATION_ORDER',
            'CEO',
            'ORDERED',
            'G4 Canonicalization Readiness Pack preparation ordered. Must include: Reference Epoch 001 evidence, exact trigger conditions, non-applicability conditions, governance constraints.',
            json.dumps(metadata),
            'STIG'
        ))
        action_id = cur.fetchone()['action_id']
        print(f"[OK] Canonicalization pack preparation ordered: {action_id}")

        conn.commit()
except Exception as e:
    conn.rollback()
    print(f"[ERROR] {e}")
finally:
    conn.close()
