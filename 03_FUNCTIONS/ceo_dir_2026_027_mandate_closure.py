#!/usr/bin/env python3
"""
CEO-DIR-2026-027: Contractual Mandate Closure & Revenue Activation
Executed by: STIG (CTO)

This script implements the mandate closures specified in CEO-DIR-2026-027:
- GAP-001: Forecast-Outcome Reconciliation ownership (FINN/STIG/VEGA)
- GAP-002: Epistemic Blindness Containment (VEGA)
- GAP-003: EC-007 Registry Reconciliation (CDMO canonical)
"""

import os
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from uuid import uuid4

DIRECTIVE_ID = "CEO-DIR-2026-027"

def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '54322'),
        database=os.environ.get('PGDATABASE', 'postgres'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', 'postgres')
    )

def register_inter_agent_contracts(conn):
    """Register inter-agent contracts for GAP-001 closure."""
    cursor = conn.cursor()

    contracts = [
        # GAP-001: Forecast-Outcome Reconciliation
        {
            'source_agent': 'FINN',
            'target_agent': 'STIG',
            'trigger_event': 'FORECAST_CREATED',
            'expected_action': 'REGISTER_FOR_RECONCILIATION',
            'sla_seconds': 3600,
            'metadata': {
                'directive': DIRECTIVE_ID,
                'gap_closure': 'GAP-001',
                'responsibility': 'Methodological Truth - defines match/hit logic'
            }
        },
        {
            'source_agent': 'STIG',
            'target_agent': 'VEGA',
            'trigger_event': 'RECONCILIATION_COMPLETE',
            'expected_action': 'VERIFY_LINEAGE_INTEGRITY',
            'sla_seconds': 1800,
            'metadata': {
                'directive': DIRECTIVE_ID,
                'gap_closure': 'GAP-001',
                'responsibility': 'Execution Infrastructure - SQL pipelines and schema'
            }
        },
        {
            'source_agent': 'VEGA',
            'target_agent': 'GOVERNANCE_LOG',
            'trigger_event': 'LINEAGE_VERIFIED',
            'expected_action': 'ATTEST_RECONCILIATION',
            'sla_seconds': 300,
            'metadata': {
                'directive': DIRECTIVE_ID,
                'gap_closure': 'GAP-001',
                'responsibility': 'Audit & Integrity - cryptographic lineage verification'
            }
        },
        # GAP-002: Epistemic Blindness Containment
        {
            'source_agent': 'VEGA',
            'target_agent': 'DEFCON_CONTROLLER',
            'trigger_event': 'BRIER_THRESHOLD_EXCEEDED',
            'expected_action': 'ESCALATE_DEFCON_IF_OVERCONFIDENT',
            'sla_seconds': 60,
            'metadata': {
                'directive': DIRECTIVE_ID,
                'gap_closure': 'GAP-002',
                'responsibility': 'Epistemic Blindness Detection',
                'threshold': 0.30,
                'condition': 'brier_score > 0.30 AND hit_rate < 0.40'
            }
        },
        {
            'source_agent': 'VEGA',
            'target_agent': 'LINE',
            'trigger_event': 'CALIBRATION_FAILURE_DETECTED',
            'expected_action': 'LOCK_EXECUTION',
            'sla_seconds': 10,
            'metadata': {
                'directive': DIRECTIVE_ID,
                'gap_closure': 'GAP-002',
                'responsibility': 'Execution Veto on Epistemic Risk',
                'veto_authority': 'ABSOLUTE'
            }
        }
    ]

    inserted = 0
    for contract in contracts:
        cursor.execute("""
            INSERT INTO fhq_governance.agent_contracts (
                contract_id, source_agent, target_agent, trigger_event,
                expected_action, sla_seconds, created_at, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
            ON CONFLICT DO NOTHING
        """, (
            str(uuid4()),
            contract['source_agent'],
            contract['target_agent'],
            contract['trigger_event'],
            contract['expected_action'],
            contract['sla_seconds'],
            json.dumps(contract['metadata'])
        ))
        inserted += cursor.rowcount

    conn.commit()
    cursor.close()
    return inserted

def update_ec_registry(conn):
    """Update EC registry for GAP-003 closure (EC-007 = CDMO canonical)."""
    cursor = conn.cursor()

    # Check if EC-007 exists and update if needed
    cursor.execute("""
        SELECT contract_id, employee, status
        FROM fhq_meta.vega_employment_contract
        WHERE contract_number = 'EC-007'
    """)

    result = cursor.fetchone()

    if result:
        # Update existing EC-007 to CDMO
        cursor.execute("""
            UPDATE fhq_meta.vega_employment_contract
            SET employee = 'CDMO',
                updated_at = NOW()
            WHERE contract_number = 'EC-007'
        """)
        action = 'UPDATED'
    else:
        # Insert new EC-007 for CDMO
        cursor.execute("""
            INSERT INTO fhq_meta.vega_employment_contract (
                contract_number, contract_version, employer, employee,
                effective_date, status, governing_charter,
                constitutional_foundation, total_duties, total_constraints, total_rights,
                override_authority, reports_to, vega_signature, content_hash,
                created_at, updated_at
            ) VALUES (
                'EC-007', '2026.PRODUCTION', 'FjordHQ AS', 'CDMO',
                NOW(), 'ACTIVE', 'ADR-007',
                ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-007', 'ADR-013', 'ADR-014'],
                6, 4, 4,
                ARRAY['CEO', 'VEGA', 'LARS'],
                'STIG',
                md5('CDMO-EC-007-' || NOW()::text),
                md5('CDMO-CONTENT-' || NOW()::text),
                NOW(), NOW()
            )
        """)
        action = 'INSERTED'

    conn.commit()
    cursor.close()
    return action

def register_mandate_amendments(conn):
    """Register mandate amendments in agent_mandates table."""
    cursor = conn.cursor()

    amendments = [
        {
            'agent_name': 'FINN',
            'mandate_type': 'executive',
            'authority_type': 'METHODOLOGICAL',
            'parent_agent': 'LARS',
            'mandate_document': {
                'domain': 'Research & Insight',
                'ceo_dir_2026_027_amendment': {
                    'gap_closure': 'GAP-001',
                    'added_responsibility': 'Forecast-Outcome Reconciliation - Methodological Truth',
                    'authority': 'Owns the logic of what constitutes a match and a hit',
                    'effective_date': '2026-01-09'
                }
            }
        },
        {
            'agent_name': 'STIG',
            'mandate_type': 'executive',
            'authority_type': 'INFRASTRUCTURE',
            'parent_agent': 'LARS',
            'mandate_document': {
                'domain': 'Technology & Infrastructure',
                'ceo_dir_2026_027_amendment': {
                    'gap_closure': 'GAP-001',
                    'added_responsibility': 'Forecast-Outcome Reconciliation - Execution Infrastructure',
                    'authority': 'Owns SQL pipelines and schema stability of forecast_outcome_pairs',
                    'effective_date': '2026-01-09'
                }
            }
        },
        {
            'agent_name': 'VEGA',
            'mandate_type': 'constitutional',
            'authority_type': 'GOVERNANCE',
            'parent_agent': 'CEO',
            'mandate_document': {
                'domain': 'Constitutional Audit & Governance',
                'ceo_dir_2026_027_amendments': [
                    {
                        'gap_closure': 'GAP-001',
                        'added_responsibility': 'Forecast-Outcome Reconciliation - Audit & Integrity',
                        'authority': 'Verifies cryptographic lineage of every matched pair'
                    },
                    {
                        'gap_closure': 'GAP-002',
                        'added_responsibility': 'Epistemic Blindness Containment',
                        'authority': 'Primary mandate owner - detect and suppress Overconfidence Regimes',
                        'enforcement': 'Authorized to escalate DEFCON and lock execution if Brier > 0.30 while confidence remains high',
                        'veto_power': 'ABSOLUTE'
                    }
                ],
                'effective_date': '2026-01-09'
            }
        },
        {
            'agent_name': 'CDMO',
            'mandate_type': 'subexecutive',
            'authority_type': 'DATASET',
            'parent_agent': 'STIG',
            'mandate_document': {
                'domain': 'Data & Memory',
                'ceo_dir_2026_027_clarification': {
                    'gap_closure': 'GAP-003',
                    'canonical_ec': 'EC-007',
                    'status': 'Database entry is canonical truth',
                    'effective_date': '2026-01-09'
                }
            }
        }
    ]

    updated = 0
    for amendment in amendments:
        # Update existing mandate or insert new one
        cursor.execute("""
            UPDATE fhq_governance.agent_mandates
            SET mandate_document = mandate_document || %s::jsonb,
                mandate_version = 'v2.0-CEO-DIR-2026-027'
            WHERE agent_name = %s
        """, (
            json.dumps(amendment['mandate_document']),
            amendment['agent_name']
        ))

        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO fhq_governance.agent_mandates (
                    mandate_id, agent_name, mandate_version, mandate_type,
                    authority_type, parent_agent, mandate_document, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                str(uuid4()),
                amendment['agent_name'],
                'v2.0-CEO-DIR-2026-027',
                amendment['mandate_type'],
                amendment['authority_type'],
                amendment['parent_agent'],
                json.dumps(amendment['mandate_document'])
            ))

        updated += 1

    conn.commit()
    cursor.close()
    return updated

def log_revenue_activation(conn):
    """Log revenue activation authorization in governance ledger."""
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, initiated_at, decision, decision_rationale,
            metadata, agent_id, timestamp
        ) VALUES (
            gen_random_uuid(),
            'REVENUE_ACTIVATION',
            'FjordHQ Market System',
            'SYSTEM',
            'CEO',
            NOW(),
            'APPROVED',
            %s,
            %s,
            'STIG',
            NOW()
        )
    """, (
        'CEO-DIR-2026-027: FjordHQ authorized to operate as Revenue-Seeking System of Record',
        json.dumps({
            'directive': DIRECTIVE_ID,
            'activation_type': 'REVENUE_SEEKING_SYSTEM_OF_RECORD',
            'constraints': {
                'boundary_enforcement': 'Execution within EC-defined authority',
                'veto_power': 'VEGA absolute veto on calibration failure',
                'auditability': 'Every action generates evidence bundle'
            },
            'standing_order': 'Hurry Slowly',
            'principles': [
                'Failure is allowed',
                'Losses are allowed (within risk limits)',
                'Learning is mandatory',
                'Operating without a mandate is FORBIDDEN'
            ],
            'activated_at': datetime.now().isoformat()
        })
    ))

    conn.commit()
    cursor.close()

def main():
    """Execute mandate closure."""
    print("=" * 60)
    print("CEO-DIR-2026-027: Contractual Mandate Closure")
    print(f"Executor: STIG | Started: {datetime.now().isoformat()}")
    print("=" * 60)

    conn = get_db_connection()

    # GAP-001 & GAP-002: Register inter-agent contracts
    print("\n--- GAP-001 & GAP-002: Registering Inter-Agent Contracts ---")
    contracts_inserted = register_inter_agent_contracts(conn)
    print(f"  Inter-agent contracts registered: {contracts_inserted}")

    # GAP-003: Update EC registry
    print("\n--- GAP-003: EC-007 Registry Reconciliation ---")
    ec_action = update_ec_registry(conn)
    print(f"  EC-007 (CDMO): {ec_action}")

    # Register mandate amendments
    print("\n--- Registering Mandate Amendments ---")
    mandates_updated = register_mandate_amendments(conn)
    print(f"  Mandate amendments registered: {mandates_updated}")

    # Log revenue activation
    print("\n--- Revenue Activation Authorization ---")
    log_revenue_activation(conn)
    print("  Revenue activation logged to governance_actions_log")

    conn.close()

    print("\n" + "=" * 60)
    print("MANDATE CLOSURE COMPLETE")
    print("=" * 60)
    print("\nGAP-001: Forecast-Outcome Reconciliation -> FINN/STIG/VEGA")
    print("GAP-002: Epistemic Blindness Containment -> VEGA (Primary)")
    print("GAP-003: EC-007 -> CDMO (Canonical)")
    print("\nREVENUE ACTIVATION: AUTHORIZED")
    print("Operating without a mandate is FORBIDDEN.")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
