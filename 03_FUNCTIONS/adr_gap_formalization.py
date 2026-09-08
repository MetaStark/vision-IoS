#!/usr/bin/env python3
"""
ADR Gap Formalization - CEO-DIR-2026-GOV-021
Formalizes undocumented architectural exposure into bounded constitutional objects.

No implementation, retro edits, or inference - only formalization.
"""

import os
import json
import hashlib
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return 2

    conn = psycopg2.connect(database_url)
    conn.autocommit = False

    evidence = {
        'directive_ref': 'CEO-DIR-2026-GOV-021',
        'document_type': 'ADR_GAP_FORMALIZATION',
        'executed_by': 'STIG',
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'raw_sql_outputs': {}
    }

    # ADR formalization data
    # Note: adr_status must use allowed values (DRAFT, PROPOSED, APPROVED, DEPRECATED, SUPERSEDED)
    # Gap status is documented in metadata field
    adr_formalizations = {
        'ADR-022': {
            'adr_title': 'The Autonomous Database Horizon Implementation Charter',
            'adr_status': 'APPROVED',  # Keep approved status, gap in metadata
            'governance_tier': 'Tier-1',
            'adr_type': 'CONSTITUTIONAL',
            'current_sha256': '2c11bc86b5b185460a902696897dba121f23083aef2ec0f4a9d626c109602b21',
            'sha256_hash': None,  # Gap: Not attested despite hash presence
            'vega_attested': False,
            'risk_classification': {
                'capital_impact': 'NONE',
                'learning_impact': 'NONE',
                'gate_impact': 'NONE',
                'evidence_integrity_impact': 'NONE'
            },
            'dependency_mapping': {
                'affected_ios_modules': [],
                'affected_daemons': [],
                'affected_tables': [
                    'fhq_governance.*',  # Governance layer tables
                    'fhq_monitoring.*'  # Monitoring tables
                ],
                'upstream_adr_dependencies': [],
                'downstream_adr_dependencies': []
            }
        },
        'ADR-023': {
            'adr_title': 'MBB Corporate Standards Integration',
            'adr_status': 'APPROVED',  # Keep approved status, gap in metadata
            'governance_tier': 'G1',
            'adr_type': 'OPERATIONAL',
            'current_sha256': 'f638a1d1117b43bdfe4ae0a1ba07669ab7430349b0a24f95f92ef18a0642baa6',
            'sha256_hash': None,  # Gap: Not attested despite hash presence
            'vega_attested': False,
            'risk_classification': {
                'capital_impact': 'NONE',
                'learning_impact': 'NONE',
                'gate_impact': 'NONE',
                'evidence_integrity_impact': 'MODERATE'  # Corporate standards affect evidence
            },
            'dependency_mapping': {
                'affected_ios_modules': [],
                'affected_daemons': [],
                'affected_tables': [
                    'fhq_meta.adr_registry',
                    'fhq_meta.ios_registry'
                ],
                'upstream_adr_dependencies': [],
                'downstream_adr_dependencies': []
            }
        },
        'ADR-013A': {
            'adr_title': 'Time Authority Doctrine',
            'adr_status': 'APPROVED',  # Keep approved status, gap in metadata
            'governance_tier': 'Tier-2',
            'adr_type': 'ARCHITECTURAL',
            'current_sha256': None,  # Gap: No hash present
            'sha256_hash': None,
            'vega_attested': False,
            'risk_classification': {
                'capital_impact': 'NONE',
                'learning_impact': 'NONE',
                'gate_impact': 'NONE',
                'evidence_integrity_impact': 'CORE'  # Time authority affects all temporal integrity
            },
            'dependency_mapping': {
                'affected_ios_modules': [],  # Unknown - no data
                'affected_daemons': [],  # Unknown - no data
                'affected_tables': [
                    'fhq_governance.autonomy_clock_state',
                    'fhq_governance.defcon_state',
                    'fhq_governance.execution_mode',
                    'fhq_calendar.canonical_test_events'
                ],
                'upstream_adr_dependencies': [],
                'downstream_adr_dependencies': []
            }
        }
    }

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Capture pre-update state
            cur.execute('''
                SELECT adr_id, adr_title, adr_status, sha256_hash, vega_attested, governance_tier
                FROM fhq_meta.adr_registry
                WHERE adr_id IN ('ADR-022', 'ADR-023', 'ADR-013A')
                ORDER BY adr_id
            ''')
            pre_update_state = [dict(r) for r in cur.fetchall()]
            evidence['raw_sql_outputs']['pre_update_state'] = pre_update_state

            # Update each ADR with gap formalization
            for adr_id, formalization in adr_formalizations.items():
                print(f'Formalizing {adr_id}...')

                # Build metadata with formalization data
                updated_metadata = {
                    'gap_formalization': {
                        'directive': 'CEO-DIR-2026-GOV-021',
                        'formalized_at': datetime.now(timezone.utc).isoformat(),
                        'formalized_by': 'STIG',
                        'risk_classification': formalization['risk_classification'],
                        'dependency_mapping': formalization['dependency_mapping'],
                        'attestation_status': 'NOT_SIGNED',
                        'implementation_status': 'UNBOUND'
                    }
                }

                # Preserve existing metadata if present
                existing_metadata_query = '''
                    SELECT metadata FROM fhq_meta.adr_registry WHERE adr_id = %s
                '''
                cur.execute(existing_metadata_query, (adr_id,))
                result = cur.fetchone()
                if result and result['metadata']:
                    updated_metadata['existing_metadata'] = result['metadata']

                # Update ADR with formalization
                cur.execute('''
                    UPDATE fhq_meta.adr_registry
                    SET adr_status = %s,
                        sha256_hash = %s,
                        vega_attested = %s,
                        metadata = %s,
                        updated_at = %s
                    WHERE adr_id = %s
                ''', (
                    formalization['adr_status'],
                    formalization['sha256_hash'],
                    formalization['vega_attested'],
                    json.dumps(updated_metadata),
                    datetime.now(timezone.utc),
                    adr_id
                ))
                print(f'  {adr_id} formalized')

            conn.commit()

            # Capture post-update state
            cur.execute('''
                SELECT adr_id, adr_title, adr_status, sha256_hash, vega_attested, governance_tier, metadata
                FROM fhq_meta.adr_registry
                WHERE adr_id IN ('ADR-022', 'ADR-023', 'ADR-013A')
                ORDER BY adr_id
            ''')
            post_update_state = [dict(r) for r in cur.fetchall()]
            evidence['raw_sql_outputs']['post_update_state'] = post_update_state

            # Governance Classification Verdict
            evidence['governance_classification'] = {
                'rule': 'If ALL true (no capital allocation, no gate mutation, no learning score dependency) → WARN → GREEN',
                'analysis': {}
            }

            for adr_id, formalization in adr_formalizations.items():
                risks = formalization['risk_classification']
                touches_critical_layers = any([
                    risks['capital_impact'] in ('DIRECT', 'INDIRECT'),
                    risks['gate_impact'] in ('CORE', 'MODERATE'),
                    risks['learning_impact'] in ('CORE', 'MODERATE')
                ])
                verdict = 'CONDITIONAL' if touches_critical_layers else 'GREEN'
                evidence['governance_classification']['analysis'][adr_id] = {
                    'touches_critical_layers': touches_critical_layers,
                    'verdict': verdict,
                    'risk_summary': risks
                }

            # Overall verdict
            any_conditional = any(
                v['verdict'] == 'CONDITIONAL'
                for v in evidence['governance_classification']['analysis'].values()
            )
            evidence['governance_classification']['overall_verdict'] = 'CONDITIONAL' if any_conditional else 'GREEN'
            evidence['governance_classification']['system_status'] = 'WARN' if any_conditional else 'PASS'

    except Exception as e:
        conn.rollback()
        evidence['error'] = str(e)
        evidence['status'] = 'FAILED'
        print(f'ERROR: {e}')

    finally:
        conn.close()

    # SHA-256 attestation
    evidence_json = json.dumps(evidence, indent=2, default=str)
    sha256 = hashlib.sha256(evidence_json.encode()).hexdigest()
    evidence['attestation'] = {'sha256_hash': sha256}

    # Write evidence
    output_dir = '03_FUNCTIONS/evidence'
    os.makedirs(output_dir, exist_ok=True)
    filename = f'GOV_021_ADR_GAP_FORMALIZATION_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w') as f:
        f.write(json.dumps(evidence, indent=2, default=str))

    # Output
    print(f'Evidence: {filepath}')
    print(f'SHA-256: {sha256}')
    print()
    print('Governance Classification Verdict:')
    for adr_id, analysis in evidence.get('governance_classification', {}).get('analysis', {}).items():
        print(f'  {adr_id}: {analysis["verdict"]}')
    print()
    print(f'Overall System Status: {evidence.get("governance_classification", {}).get("system_status", "UNKNOWN")}')

    if evidence.get('status') == 'FAILED':
        return 2
    else:
        return 0

if __name__ == "__main__":
    exit(main())
