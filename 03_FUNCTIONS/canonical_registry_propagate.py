"""
CEO-DIR-2025-INGEST-001: Registry Propagation
==============================================
One-way propagation: canonical_documents -> adr_registry, ios_registry

FORBEHOLD 2: This is ONE-WAY authority only.
Dataflow: Files -> canonical_documents -> registries
NO writeback from registries to canonical_documents.

Executor: STIG
"""

import psycopg2
from datetime import datetime

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres'
}

def propagate_adrs(conn):
    """Propagate ADRs from canonical_documents to adr_registry."""
    print("\n=== PROPAGATING ADRs to adr_registry ===")
    cursor = conn.cursor()

    # Get all ADRs from canonical_documents
    cursor.execute("""
        SELECT document_code, title, status, tier, owner, content_hash, source_path, version
        FROM fhq_meta.canonical_documents
        WHERE document_type = 'ADR'
        ORDER BY document_code
    """)
    adrs = cursor.fetchall()

    propagated = 0
    for adr_id, title, status, tier, owner, content_hash, source_path, version in adrs:
        adr_type = 'CONSTITUTIONAL' if tier == 1 else ('ARCHITECTURAL' if tier == 2 else 'OPERATIONAL')
        governance_tier = f'Tier-{tier}'

        try:
            cursor.execute("""
                INSERT INTO fhq_meta.adr_registry (
                    adr_id, adr_title, adr_status, adr_type, current_version,
                    status, created_by, governance_tier, owner, title, description,
                    sha256_hash, file_path, created_at, updated_at
                ) VALUES (
                    %s, %s, 'APPROVED', %s, %s,
                    %s, %s, %s, %s, %s, 'Propagated from canonical_documents per CEO-DIR-2025-INGEST-001',
                    %s, %s, NOW(), NOW()
                )
                ON CONFLICT (adr_id) DO UPDATE SET
                    adr_title = EXCLUDED.adr_title,
                    adr_status = EXCLUDED.adr_status,
                    adr_type = EXCLUDED.adr_type,
                    current_version = EXCLUDED.current_version,
                    status = EXCLUDED.status,
                    governance_tier = EXCLUDED.governance_tier,
                    owner = EXCLUDED.owner,
                    title = EXCLUDED.title,
                    sha256_hash = EXCLUDED.sha256_hash,
                    file_path = EXCLUDED.file_path,
                    updated_at = NOW()
            """, (
                adr_id, title, adr_type, version,
                status, owner, governance_tier, owner, title,
                content_hash, source_path
            ))
            conn.commit()
            propagated += 1
            print(f"  OK: {adr_id} -> adr_registry")
        except Exception as e:
            conn.rollback()
            print(f"  ERROR: {adr_id}: {e}")

    print(f"\n  TOTAL ADRs PROPAGATED: {propagated}")
    return propagated

def propagate_ioss(conn):
    """Propagate IoSs from canonical_documents to ios_registry."""
    print("\n=== PROPAGATING IoSs to ios_registry ===")
    cursor = conn.cursor()

    # Get all IoSs from canonical_documents
    cursor.execute("""
        SELECT document_code, title, status, tier, owner, content_hash, source_path, version, governing_adrs
        FROM fhq_meta.canonical_documents
        WHERE document_type = 'IoS'
        ORDER BY document_code
    """)
    ioss = cursor.fetchall()

    propagated = 0
    for ios_code, title, status, tier, owner, content_hash, source_path, version, governing_adrs in ioss:
        # Keep original format (IoS-001)
        ios_id = ios_code

        try:
            cursor.execute("""
                INSERT INTO fhq_meta.ios_registry (
                    ios_id, title, version, status, owner_role,
                    content_hash, governing_adrs, canonical, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, true, NOW(), NOW()
                )
                ON CONFLICT (ios_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    version = EXCLUDED.version,
                    status = EXCLUDED.status,
                    owner_role = EXCLUDED.owner_role,
                    content_hash = EXCLUDED.content_hash,
                    governing_adrs = EXCLUDED.governing_adrs,
                    canonical = true,
                    updated_at = NOW()
            """, (
                ios_id, title, version, status, owner,
                content_hash, governing_adrs
            ))
            conn.commit()
            propagated += 1
            print(f"  OK: {ios_id} -> ios_registry")
        except Exception as e:
            conn.rollback()
            print(f"  ERROR: {ios_id}: {e}")

    print(f"\n  TOTAL IoSs PROPAGATED: {propagated}")
    return propagated

def log_governance_action(conn):
    """Log the propagation as a governance action."""
    print("\n=== LOGGING GOVERNANCE ACTION ===")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_id,
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                initiated_at,
                decision,
                decision_rationale,
                metadata,
                vega_reviewed
            ) VALUES (
                gen_random_uuid(),
                'REGISTRY_PROPAGATION',
                'adr_registry,ios_registry',
                'CEO-DIR-2025-INGEST-001',
                'STIG',
                NOW(),
                'EXECUTED',
                'One-way propagation from canonical_documents to runtime registries per FORBEHOLD 2',
                jsonb_build_object(
                    'directive', 'CEO-DIR-2025-INGEST-001',
                    'propagation_type', 'ONE_WAY',
                    'source', 'fhq_meta.canonical_documents',
                    'targets', ARRAY['fhq_meta.adr_registry', 'fhq_meta.ios_registry'],
                    'forbehold_2', 'En-veis autoritet - Fil -> canonical -> registry'
                ),
                false
            )
        """)
        conn.commit()
        print("  OK: Governance action logged")
    except Exception as e:
        conn.rollback()
        print(f"  ERROR: {e}")

def verify_propagation(conn):
    """Verify propagation was successful."""
    print("\n=== VERIFICATION ===")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM fhq_meta.adr_registry")
    adr_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fhq_meta.ios_registry")
    ios_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fhq_meta.canonical_documents WHERE document_type = 'ADR'")
    canonical_adr = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fhq_meta.canonical_documents WHERE document_type = 'IoS'")
    canonical_ios = cursor.fetchone()[0]

    print(f"  canonical_documents ADRs: {canonical_adr}")
    print(f"  adr_registry count:       {adr_count}")
    print(f"  canonical_documents IoSs: {canonical_ios}")
    print(f"  ios_registry count:       {ios_count}")

    return adr_count, ios_count

def main():
    print("=" * 60)
    print("CEO-DIR-2025-INGEST-001: REGISTRY PROPAGATION")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Executor: STIG")
    print()
    print("FORBEHOLD 2: One-way authority only")
    print("Dataflow: canonical_documents -> adr_registry, ios_registry")
    print("=" * 60)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('WIN1252')  # Match database encoding
        print("\nDatabase connected.")

        adr_count = propagate_adrs(conn)
        ios_count = propagate_ioss(conn)
        log_governance_action(conn)
        verify_propagation(conn)

        print("\n" + "=" * 60)
        print("PROPAGATION COMPLETE")
        print("=" * 60)
        print(f"  ADRs propagated: {adr_count}")
        print(f"  IoSs propagated: {ios_count}")

        conn.close()

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        raise

if __name__ == '__main__':
    main()
