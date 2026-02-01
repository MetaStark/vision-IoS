"""
CEO-DIR-2026-077 Execution
==========================
OPERATIONAL ALPHA TRANSITION – INVERSION-FIRST STRATEGY

Authority: CEO
Effective: 2026-01-18 (immediately)

Author: STIG (EC-003)
Date: 2026-01-18
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


def insert_governance_action(cur, action_type, action_target, target_type,
                             initiated_by, decision, rationale, metadata_dict, agent_id):
    """Helper to insert governance action."""
    cur.execute("""
        INSERT INTO fhq_governance.governance_actions_log (
            action_type, action_target, action_target_type,
            initiated_by, decision, decision_rationale, metadata, agent_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        RETURNING action_id
    """, (action_type, action_target, target_type, initiated_by,
          decision, rationale, json.dumps(metadata_dict), agent_id))
    return cur.fetchone()['action_id']


def execute_directive():
    """Execute CEO-DIR-2026-077."""
    conn = psycopg2.connect(**DB_CONFIG)
    timestamp = datetime.now(timezone.utc)
    results = {}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Register CEO directive
            action_id = insert_governance_action(
                cur,
                'CEO_DIRECTIVE_EXECUTION',
                'CEO-DIR-2026-077',
                'DIRECTIVE',
                'CEO',
                'EXECUTING',
                'OPERATIONAL ALPHA TRANSITION - INVERSION-FIRST STRATEGY. Supersedes planning discussion. Sets single coherent path from discovery to ROI.',
                {
                    'directive_id': 'CEO-DIR-2026-077',
                    'title': 'Operational Alpha Transition - Inversion-First Strategy',
                    'supersedes': 'Planning discussion',
                    'priority_0': ['T48H_RECONCILIATION', 'CANONICALIZATION_READINESS'],
                    'priority_1': ['CRYPTO_REGIME_RESEARCH'],
                    'authority': 'CEO',
                    'effective': 'IMMEDIATELY',
                    'timestamp': timestamp.isoformat()
                },
                'CEO'
            )
            results['directive_action_id'] = str(action_id)
            print(f"[OK] CEO-DIR-2026-077 registered: {action_id}")

            # 2. Register System State Acknowledgment (NON-NEGOTIABLE CANONICAL FACTS)
            action_id = insert_governance_action(
                cur,
                'CANONICAL_FACTS_LOCKED',
                'SYSTEM_STATE_2026-01-18',
                'CANONICAL_KNOWLEDGE',
                'CEO',
                'LOCKED',
                'Non-negotiable canonical facts established. No further debate permitted unless new contradictory evidence emerges.',
                {
                    'directive_ref': 'CEO-DIR-2026-077',
                    'canonical_facts': [
                        'STRESS@99%+ in EQUITY is structural contrarian signal',
                        'Original Brier 0.996 is deterministic inversion, not failure',
                        'Inverted Brier 0.003 is economically extraordinary',
                        'Equity and Crypto are epistemically non-transferable domains',
                        'Reference Epoch 001 is valid and locked'
                    ],
                    'debate_status': 'PROHIBITED',
                    'override_condition': 'New contradictory evidence only',
                    'timestamp': timestamp.isoformat()
                },
                'CEO'
            )
            results['canonical_facts_id'] = str(action_id)
            print(f"[OK] Canonical facts locked: {action_id}")

            # 3. Register T+24h G4 Checkpoint
            action_id = insert_governance_action(
                cur,
                'G4_CHECKPOINT_CAPTURED',
                'T_PLUS_24H',
                'OKR_CHECKPOINT',
                'STIG',
                'CAPTURED',
                'T+24h G4 checkpoint captured. Brier improved from 0.5358 to 0.3233 (39.66% improvement). Hit rate improved from 32.65% to 41.01%.',
                {
                    'directive_ref': 'CEO-DIR-2026-068',
                    'checkpoint': 'T+24h',
                    'captured_at': timestamp.isoformat(),
                    'baseline': {
                        'brier': 0.5358,
                        'hit_rate': 0.3265,
                        'stop_loss': 0.5658
                    },
                    'current': {
                        'brier': 0.3233,
                        'hit_rate': 0.4101,
                        'total_pairs': 17656
                    },
                    'analysis': {
                        'brier_improvement': '39.66%',
                        'hit_rate_improvement': '+8.36pp',
                        'headroom_to_stop_loss': 0.2425,
                        'status': 'GREEN'
                    },
                    'stress_inversion': {
                        'total': 10,
                        'correct': 0,
                        'brier': 0.9968,
                        'inverted_brier': 0.0032,
                        'status': 'STABLE'
                    },
                    'timestamp': timestamp.isoformat()
                },
                'STIG'
            )
            results['checkpoint_id'] = str(action_id)
            print(f"[OK] T+24h G4 checkpoint captured: {action_id}")

            # 4. Register Inversion-First Strategic Mandate
            action_id = insert_governance_action(
                cur,
                'STRATEGIC_MANDATE_REGISTERED',
                'INVERSION_FIRST_STRATEGY',
                'STRATEGIC_CORRECTION',
                'CEO',
                'ACTIVE',
                'Inversion-First Strategy clarified. Suppression=defensive, Calibration=corrective, Inversion=exploitative. All future synthesis must first test invertibility.',
                {
                    'directive_ref': 'CEO-DIR-2026-077',
                    'strategy_hierarchy': {
                        'suppression': 'DEFENSIVE',
                        'calibration': 'CORRECTIVE',
                        'inversion': 'EXPLOITATIVE'
                    },
                    'mandate_changes': [
                        'No further confidence-suppression-only signals prioritized',
                        'All future synthesis must first test: Is this wrong in consistent, invertible way?',
                        'UMA retains synthesis authority under clarified mandate'
                    ],
                    'effective': 'IMMEDIATELY',
                    'timestamp': timestamp.isoformat()
                },
                'CEO'
            )
            results['strategic_mandate_id'] = str(action_id)
            print(f"[OK] Inversion-First Strategy registered: {action_id}")

            # 5. Register Authority Boundaries (ABSOLUTE)
            action_id = insert_governance_action(
                cur,
                'AUTHORITY_BOUNDARIES_LOCKED',
                'CEO-DIR-2026-077',
                'GOVERNANCE_CONSTRAINT',
                'CEO',
                'LOCKED',
                'Absolute authority boundaries locked. No paper trading, no capital allocation, no BULL inversion, no cross-domain generalization, no crypto ROI optimization.',
                {
                    'directive_ref': 'CEO-DIR-2026-077',
                    'prohibited_until_new_directive': [
                        'Paper trading',
                        'Capital allocation',
                        'BULL inversion',
                        'Cross-domain generalization',
                        'Optimization against ROI metrics that include crypto'
                    ],
                    'principle': 'Equity inversion stands alone and must prove itself cleanly',
                    'override_authority': 'CEO_ONLY',
                    'effective': 'IMMEDIATELY',
                    'timestamp': timestamp.isoformat()
                },
                'CEO'
            )
            results['authority_boundaries_id'] = str(action_id)
            print(f"[OK] Authority boundaries locked: {action_id}")

            # 6. Register IoS-003C Constraints
            action_id = insert_governance_action(
                cur,
                'IOS_MODULE_CONSTRAINTS_REGISTERED',
                'IoS-003C',
                'RESEARCH_CONSTRAINTS',
                'CEO',
                'CONSTRAINED',
                'IoS-003C Crypto Regime Engine constraints registered. FINN authorized under strict constraints. Equity regimes, macro proxies, confidence logic explicitly disallowed.',
                {
                    'directive_ref': 'CEO-DIR-2026-077',
                    'module': 'IoS-003C',
                    'assigned_to': 'FINN',
                    'objective': 'Native crypto regime classification with target Brier < 0.25',
                    'explicitly_disallowed': [
                        'Equity regimes',
                        'Macro proxies',
                        'Confidence logic from equity'
                    ],
                    'required_research_priorities': [
                        'On-chain net flows',
                        'Exchange inflow/outflow asymmetry',
                        'Funding-rate dynamics',
                        'Volatility-of-volatility'
                    ],
                    'api_mandatory': 'DeepSeek Reasoning API',
                    'deliverable': 'Crypto Regime Dimensions v0 (descriptive, not executable)',
                    'crypto_forecast_status': 'BLOCKED until approved',
                    'timestamp': timestamp.isoformat()
                },
                'FINN'
            )
            results['ios_003c_constraints_id'] = str(action_id)
            print(f"[OK] IoS-003C constraints registered: {action_id}")

            # 7. Register T+48h Decision Gate Requirements
            action_id = insert_governance_action(
                cur,
                'DECISION_GATE_SCHEDULED',
                'T_PLUS_48H_RECONCILIATION',
                'CEO_DECISION_GATE',
                'CEO',
                'SCHEDULED',
                'T+48h decision gate scheduled for 2026-01-19. Required: STRESS inversion results (VEGA attested), BULL extension recommendation, crypto research status.',
                {
                    'directive_ref': 'CEO-DIR-2026-077',
                    'scheduled': '2026-01-19',
                    'presentations_required': [
                        'Verified STRESS inversion results (database + VEGA attested)',
                        'Recommendation: Canonicalize STRESS inversion (G4) or abort',
                        'Readiness assessment for extending inversion logic to BULL@99%+',
                        'Status of Crypto regime research (directional only)'
                    ],
                    'gate_purpose': 'Move from Discovery to Operational Alpha',
                    'vega_attestation_required': True,
                    'timestamp': timestamp.isoformat()
                },
                'CEO'
            )
            results['decision_gate_id'] = str(action_id)
            print(f"[OK] T+48h decision gate scheduled: {action_id}")

            # 8. Register Canonicalization Readiness Pack Preparation Order
            action_id = insert_governance_action(
                cur,
                'PREPARATION_ORDER_ISSUED',
                'G4_CANONICALIZATION_PACK',
                'PREPARATION_ORDER',
                'CEO',
                'ORDERED',
                'G4 Canonicalization Readiness Pack preparation ordered. Must include: Reference Epoch 001 evidence, exact trigger conditions, non-applicability conditions, governance constraints.',
                {
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
                },
                'STIG'
            )
            results['canonicalization_pack_id'] = str(action_id)
            print(f"[OK] Canonicalization pack preparation ordered: {action_id}")

            conn.commit()

            print("\n" + "=" * 60)
            print("CEO-DIR-2026-077 EXECUTION COMPLETE")
            print("=" * 60)
            print("\nFINAL NOTE: We do not need more intelligence.")
            print("We need correct sequencing of authority.")
            print("\nA system that is predictably wrong is a weapon if handled precisely.")
            print("A system that rushes is dead.")

            return results

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Execution failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    result = execute_directive()
    print("\nGovernance Action IDs:")
    print(json.dumps(result, indent=2))
