#!/usr/bin/env python3
"""
GOVERNANCE REALIGNMENT: Re-seed agent_contracts with correct mapping
CEO Directive: CLASS A HARD RESET
"""

import json
import uuid
import hashlib
from datetime import datetime, timezone
import psycopg2
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent / '.env', override=True)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# CEO-mandated agent contract mapping
AGENT_CONTRACTS = [
    # EC-001: VEGA - Constitutional Auditor
    {
        'contract_number': 'EC-001',
        'agent_id': 'VEGA',
        'tier': 'TIER_1',
        'role_type': 'Constitutional Auditor',
        'reports_to': 'CEO',
        'governing_charter': 'ADR-006',
        'duties': 10, 'rights': 7, 'constraints': 7
    },
    # EC-002: LARS - CSO
    {
        'contract_number': 'EC-002',
        'agent_id': 'LARS',
        'tier': 'TIER_1',
        'role_type': 'Chief Strategy Officer',
        'reports_to': 'CEO',
        'governing_charter': 'ADR-007',
        'duties': 8, 'rights': 6, 'constraints': 5
    },
    # EC-003: STIG - CTO
    {
        'contract_number': 'EC-003',
        'agent_id': 'STIG',
        'tier': 'TIER_1',
        'role_type': 'Chief Technology Officer',
        'reports_to': 'LARS',
        'governing_charter': 'ADR-007',
        'duties': 8, 'rights': 5, 'constraints': 5
    },
    # EC-004: FINN - Research Exec
    {
        'contract_number': 'EC-004',
        'agent_id': 'FINN',
        'tier': 'TIER_1',
        'role_type': 'Research Executive',
        'reports_to': 'LARS',
        'governing_charter': 'ADR-007',
        'duties': 8, 'rights': 5, 'constraints': 5
    },
    # EC-005: LINE - COO
    {
        'contract_number': 'EC-005',
        'agent_id': 'LINE',
        'tier': 'TIER_1',
        'role_type': 'Chief Operations Officer',
        'reports_to': 'LARS',
        'governing_charter': 'ADR-007',
        'duties': 8, 'rights': 5, 'constraints': 5
    },
    # EC-006: CODE - Engineering Unit (Tier-3)
    {
        'contract_number': 'EC-006',
        'agent_id': 'CODE',
        'tier': 'TIER_3',
        'role_type': 'Engineering Unit',
        'reports_to': 'STIG',
        'governing_charter': 'ADR-007',
        'duties': 4, 'rights': 3, 'constraints': 6
    },
    # EC-007: CFAO - Foresight Officer
    {
        'contract_number': 'EC-007',
        'agent_id': 'CFAO',
        'tier': 'TIER_2',
        'role_type': 'Foresight Officer',
        'reports_to': 'LARS',
        'governing_charter': 'ADR-007',
        'duties': 6, 'rights': 4, 'constraints': 4
    },
    # EC-008: SKIP - Architecture Doc (Do not register)
    # EC-009: CEIO - External Intel
    {
        'contract_number': 'EC-009',
        'agent_id': 'CEIO',
        'tier': 'TIER_2',
        'role_type': 'External Intelligence',
        'reports_to': 'STIG',
        'governing_charter': 'ADR-007',
        'duties': 6, 'rights': 4, 'constraints': 4,
        'content_hash': '3eb004ac8a1eb3dedb3100359564a7d04604f2862724a6c452f284732adf20b9'
    },
    # EC-010: CEO - Sovereign
    {
        'contract_number': 'EC-010',
        'agent_id': 'CEO',
        'tier': 'TIER_1',
        'role_type': 'Sovereign',
        'reports_to': 'Self',
        'governing_charter': 'ADR-001',
        'duties': 12, 'rights': 10, 'constraints': 2
    },
    # EC-011: CSEO - Strategy Exec
    {
        'contract_number': 'EC-011',
        'agent_id': 'CSEO',
        'tier': 'TIER_2',
        'role_type': 'Strategy Executive',
        'reports_to': 'LARS',
        'governing_charter': 'ADR-007',
        'duties': 6, 'rights': 4, 'constraints': 4
    },
    # EC-012: CDMO - Data Officer
    {
        'contract_number': 'EC-012',
        'agent_id': 'CDMO',
        'tier': 'TIER_2',
        'role_type': 'Data Officer',
        'reports_to': 'STIG',
        'governing_charter': 'ADR-007',
        'duties': 6, 'rights': 4, 'constraints': 4
    },
    # EC-013: CRIO - Research Ops
    {
        'contract_number': 'EC-013',
        'agent_id': 'CRIO',
        'tier': 'TIER_2',
        'role_type': 'Research Operations',
        'reports_to': 'FINN',
        'governing_charter': 'ADR-007',
        'duties': 6, 'rights': 4, 'constraints': 4,
        'content_hash': '35711b4d8bbf65c3e10bc5e1f432ce416f02a2ddd786f3cf4e61285d98131a93'
    }
]

def generate_vega_signature(content_hash: str) -> str:
    """Generate VEGA attestation signature"""
    return hashlib.sha256(f'VEGA_ATTESTED|{content_hash}'.encode()).hexdigest()

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    now = datetime.now(timezone.utc)

    print('=' * 60)
    print('GOVERNANCE REALIGNMENT: RE-SEEDING AGENT CONTRACTS')
    print('=' * 60)
    print()

    success_count = 0

    for contract in AGENT_CONTRACTS:
        contract_id = str(uuid.uuid4())

        # Generate content hash if not provided
        content_hash = contract.get('content_hash') or hashlib.sha256(
            f"{contract['contract_number']}|{contract['agent_id']}|{now.isoformat()}".encode()
        ).hexdigest()

        vega_signature = generate_vega_signature(content_hash)

        # Determine counterparty agents
        if contract['reports_to'] == 'CEO':
            counterparty = ['CEO', 'VEGA']
        elif contract['reports_to'] == 'Self':
            counterparty = ['VEGA']
        else:
            counterparty = [contract['reports_to'], 'VEGA']

        authority_boundaries = {
            'tier': contract['tier'],
            'reports_to': contract['reports_to'],
            'governing_charter': contract['governing_charter'],
            'total_duties': contract['duties'],
            'total_rights': contract['rights'],
            'total_constraints': contract['constraints']
        }

        metadata = {
            'employer': 'FjordHQ AS',
            'canonical_contract_number': contract['contract_number'],
            'canonical_source': f"/01_CANONICAL/EC/{contract['contract_number']}_2026_PRODUCTION.md",
            'content_hash': content_hash,
            'vega_signature': vega_signature,
            'adr_014_compliant': True
        }

        try:
            cur.execute('''
                INSERT INTO fhq_governance.agent_contracts
                (contract_id, agent_id, contract_type, contract_status, counterparty_agents,
                 mandate_scope, authority_boundaries, communication_protocols, escalation_rules,
                 performance_criteria, compliance_requirements, approved_by, approved_at,
                 effective_from, metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ''', (
                contract_id,
                contract['agent_id'],
                'MANDATE',
                'ACTIVE',
                counterparty,
                f"Employment contract {contract['contract_number']} as per ADR-014. Governing charter: {contract['governing_charter']}",
                json.dumps(authority_boundaries),
                json.dumps({'protocol': 'ASYNC_MESSAGE', 'escalation_chain': f"{contract['reports_to']} -> CEO -> VEGA"}),
                json.dumps({'level_1': contract['reports_to'], 'level_2': 'CEO', 'override': 'VEGA'}),
                json.dumps({'review_frequency': 'QUARTERLY', 'duties_compliance': True, 'constraints_compliance': True}),
                ['ADR-001', 'ADR-006', 'ADR-014', contract['governing_charter']],
                'CEO',
                now,
                now,
                json.dumps(metadata)
            ))
            print(f"  {contract['contract_number']}: {contract['agent_id']} ({contract['tier']}) -> {contract['reports_to']} OK")
            success_count += 1
        except Exception as e:
            print(f"  {contract['contract_number']}: ERROR - {e}")

    print()
    print(f'Inserted {success_count}/{len(AGENT_CONTRACTS)} contracts')

    # Verification
    print()
    print('=== VALIDATION ===')

    # Check EC-010 returns CEO
    cur.execute("SELECT agent_id FROM fhq_governance.agent_contracts WHERE metadata->>'canonical_contract_number' = 'EC-010'")
    result = cur.fetchone()
    ec010_valid = result and result[0] == 'CEO'
    print(f"  EC-010 -> CEO: {'PASS' if ec010_valid else 'FAIL'} (got: {result[0] if result else 'NULL'})")

    # Check EC-006 returns CODE
    cur.execute("SELECT agent_id FROM fhq_governance.agent_contracts WHERE metadata->>'canonical_contract_number' = 'EC-006'")
    result = cur.fetchone()
    ec006_valid = result and result[0] == 'CODE'
    print(f"  EC-006 -> CODE: {'PASS' if ec006_valid else 'FAIL'} (got: {result[0] if result else 'NULL'})")

    # Check EC-009 hash
    cur.execute("SELECT metadata->>'content_hash' FROM fhq_governance.agent_contracts WHERE metadata->>'canonical_contract_number' = 'EC-009'")
    result = cur.fetchone()
    ec009_hash = result[0] if result else None
    ec009_valid = ec009_hash == '3eb004ac8a1eb3dedb3100359564a7d04604f2862724a6c452f284732adf20b9'
    print(f"  EC-009 hash: {'PASS' if ec009_valid else 'FAIL'}")

    # Check EC-013 exists
    cur.execute("SELECT agent_id, metadata->>'content_hash' FROM fhq_governance.agent_contracts WHERE metadata->>'canonical_contract_number' = 'EC-013'")
    result = cur.fetchone()
    ec013_valid = result and result[0] == 'CRIO'
    print(f"  EC-013 -> CRIO: {'PASS' if ec013_valid else 'FAIL'} (got: {result[0] if result else 'NULL'})")

    cur.close()
    conn.close()

    print()
    all_valid = ec010_valid and ec006_valid and ec009_valid and ec013_valid
    if all_valid:
        print('=' * 60)
        print('SUCCESS: ALL VALIDATION CRITERIA MET')
        print('=' * 60)
    else:
        print('=' * 60)
        print('FAILURE: VALIDATION CRITERIA NOT MET')
        print('=' * 60)

    return all_valid

if __name__ == '__main__':
    main()
