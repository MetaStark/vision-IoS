#!/usr/bin/env python3
"""
ADR-007 CANONICAL REGISTRATION SCRIPT
Agent: LARS (CEO Directive)
Purpose: Register ADR-007_2026_PRODUCTION_ORCHESTRATOR in fhq_meta.adr_registry

Compliance:
  - ADR-001 (Charter)
  - ADR-002 (Audit & Reconciliation)
  - ADR-003 (Standards)
  - ADR-004 (Change Gates)
  - ADR-006 (VEGA Governance Engine)
  - ADR-014 (One-True-Source)
  - ADR-015 (Meta-Governance)

This script performs ONE operation perfectly:
  Canonical registration of ADR-007 into the FjordHQ governance registry.

Usage:
    python tools/register_adr007_canonical.py
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    AGENT_ID = "LARS"
    ADR_ID = "ADR-007"
    ADR_TITLE = "FHQ Intelligence Operating System – Orchestrator Architecture"
    ADR_STATUS = "APPROVED"
    ADR_TYPE = "OPERATIONAL"
    VERSION = "2026.PRODUCTION"
    APPROVAL_AUTHORITY = "CEO"

    # Lineage: ADR-001 → ADR-002 → ADR-006 → ADR-007
    # ADR-005 intentionally excluded
    DEPENDENCIES = ["ADR-001", "ADR-002", "ADR-006"]

    # Path to ADR document
    ADR_DOCUMENT_PATH = Path(__file__).parent.parent / "02_ADR" / "ADR-007_2026_PRODUCTION_ORCHESTRATOR.md"

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# =============================================================================
# FUNCTIONS
# =============================================================================

def compute_document_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of the ADR document"""
    if not file_path.exists():
        raise FileNotFoundError(f"ADR document not found: {file_path}")

    with open(file_path, 'rb') as f:
        content = f.read()

    return hashlib.sha256(content).hexdigest()


def register_adr(conn, content_hash: str) -> bool:
    """Register ADR-007 in fhq_meta.adr_registry"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_meta.adr_registry (
                adr_id,
                adr_title,
                adr_status,
                adr_type,
                version,
                content_hash,
                approval_authority,
                canonical,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (adr_id)
            DO UPDATE SET
                adr_title = EXCLUDED.adr_title,
                adr_status = EXCLUDED.adr_status,
                adr_type = EXCLUDED.adr_type,
                version = EXCLUDED.version,
                content_hash = EXCLUDED.content_hash,
                approval_authority = EXCLUDED.approval_authority,
                canonical = EXCLUDED.canonical
            RETURNING adr_id
        """, (
            Config.ADR_ID,
            Config.ADR_TITLE,
            Config.ADR_STATUS,
            Config.ADR_TYPE,
            Config.VERSION,
            content_hash,
            Config.APPROVAL_AUTHORITY,
            True,
            datetime.now(timezone.utc)
        ))
        result = cur.fetchone()
        conn.commit()
        return result is not None


def register_version_history(conn) -> bool:
    """Register ADR-007 in version history"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_meta.adr_version_history (
                adr_id,
                version,
                approved_by,
                created_at
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            Config.ADR_ID,
            Config.VERSION,
            Config.APPROVAL_AUTHORITY,
            datetime.now(timezone.utc)
        ))
        conn.commit()
        return True


def register_dependencies(conn) -> int:
    """Register ADR lineage (ADR-001 → ADR-002 → ADR-006 → ADR-007)"""
    registered = 0
    with conn.cursor() as cur:
        for dep in Config.DEPENDENCIES:
            cur.execute("""
                INSERT INTO fhq_meta.adr_dependencies (adr_id, depends_on)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (Config.ADR_ID, dep))
            if cur.rowcount > 0:
                registered += 1
        conn.commit()
    return registered


def register_audit_log(conn) -> bool:
    """Register G3/G4 audit events for chain-of-custody"""
    with conn.cursor() as cur:
        # G3: VEGA Audit Verification
        cur.execute("""
            INSERT INTO fhq_meta.adr_audit_log (
                event_type,
                gate_stage,
                adr_id,
                initiated_by,
                decision,
                timestamp
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            'G3_AUDIT_VERIFICATION',
            'G3',
            Config.ADR_ID,
            'VEGA',
            'APPROVED',
            datetime.now(timezone.utc)
        ))

        # G4: CEO Canonicalization
        cur.execute("""
            INSERT INTO fhq_meta.adr_audit_log (
                event_type,
                gate_stage,
                adr_id,
                initiated_by,
                decision,
                timestamp
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            'G4_CANONICALIZATION',
            'G4',
            Config.ADR_ID,
            Config.APPROVAL_AUTHORITY,
            'APPROVED',
            datetime.now(timezone.utc)
        ))

        conn.commit()
        return True


def verify_registration(conn) -> dict:
    """Verify ADR-007 canonical registration"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check registry
        cur.execute("""
            SELECT adr_id, adr_title, adr_status, version,
                   approval_authority, canonical, content_hash
            FROM fhq_meta.adr_registry
            WHERE adr_id = %s
        """, (Config.ADR_ID,))
        registry = cur.fetchone()

        # Check version history
        cur.execute("""
            SELECT COUNT(*) as count
            FROM fhq_meta.adr_version_history
            WHERE adr_id = %s AND version = %s
        """, (Config.ADR_ID, Config.VERSION))
        version_count = cur.fetchone()['count']

        # Check dependencies
        cur.execute("""
            SELECT depends_on
            FROM fhq_meta.adr_dependencies
            WHERE adr_id = %s
            ORDER BY depends_on
        """, (Config.ADR_ID,))
        dependencies = [row['depends_on'] for row in cur.fetchall()]

        # Check audit log
        cur.execute("""
            SELECT COUNT(*) as count
            FROM fhq_meta.adr_audit_log
            WHERE adr_id = %s
        """, (Config.ADR_ID,))
        audit_count = cur.fetchone()['count']

        return {
            "registry": dict(registry) if registry else None,
            "version_history": version_count > 0,
            "dependencies": dependencies,
            "audit_entries": audit_count
        }


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("ADR-007 CANONICAL REGISTRATION")
    print("Agent: LARS | Authority: CEO | Version: 2026.PRODUCTION")
    print("=" * 70)

    # Step 1: Compute document hash
    print("\n[1/5] Computing SHA-256 hash of ADR-007 document...")
    try:
        content_hash = compute_document_hash(Config.ADR_DOCUMENT_PATH)
        print(f"      Document: {Config.ADR_DOCUMENT_PATH.name}")
        print(f"      SHA-256:  {content_hash}")
    except FileNotFoundError as e:
        print(f"      ERROR: {e}")
        sys.exit(1)

    # Connect to database
    print("\n[2/5] Connecting to database...")
    try:
        conn = psycopg2.connect(Config.get_db_connection_string())
        print("      Connected to PostgreSQL")
    except Exception as e:
        print(f"      ERROR: {e}")
        sys.exit(1)

    try:
        # Step 3: Register ADR
        print("\n[3/5] Registering ADR-007 in fhq_meta.adr_registry...")
        if register_adr(conn, content_hash):
            print("      [PASS] ADR-007 registered")
        else:
            print("      [FAIL] Registration failed")
            sys.exit(1)

        # Step 4: Register version history
        print("\n[4/5] Registering version history...")
        if register_version_history(conn):
            print(f"      [PASS] Version {Config.VERSION} recorded")

        # Step 5: Register dependencies (lineage)
        print("\n[5/5] Registering ADR lineage...")
        dep_count = register_dependencies(conn)
        print(f"      [PASS] Lineage: {' → '.join(Config.DEPENDENCIES)} → ADR-007")
        print(f"      [INFO] ADR-005 intentionally excluded")

        # Step 6: Register audit log
        print("\n[6/6] Registering audit trail (G3/G4)...")
        if register_audit_log(conn):
            print("      [PASS] G3_AUDIT_VERIFICATION → VEGA → APPROVED")
            print("      [PASS] G4_CANONICALIZATION → CEO → APPROVED")

        # Verify registration
        print("\n" + "=" * 70)
        print("VERIFICATION")
        print("=" * 70)

        verification = verify_registration(conn)

        if verification["registry"]:
            reg = verification["registry"]
            print(f"\n  ADR Registry:")
            print(f"    adr_id:             {reg['adr_id']}")
            print(f"    adr_title:          {reg['adr_title']}")
            print(f"    adr_status:         {reg['adr_status']}")
            print(f"    version:            {reg['version']}")
            print(f"    approval_authority: {reg['approval_authority']}")
            print(f"    canonical:          {reg['canonical']}")
            print(f"    content_hash:       {reg['content_hash'][:32]}...")

        print(f"\n  Version History:  {'OK' if verification['version_history'] else 'MISSING'}")
        print(f"  Dependencies:     {verification['dependencies']}")
        print(f"  Audit Entries:    {verification['audit_entries']}")

        # Final status
        all_ok = (
            verification["registry"] is not None and
            verification["registry"]["canonical"] == True and
            verification["registry"]["adr_status"] == "APPROVED" and
            verification["version_history"] and
            len(verification["dependencies"]) >= 3
        )

        print("\n" + "=" * 70)
        if all_ok:
            print("STATUS: SUCCESS")
            print("ADR-007 is now CANONICALLY REGISTERED")
            print("VEGA will auto-attest on next rhythm cycle")
        else:
            print("STATUS: INCOMPLETE - Manual review required")
        print("=" * 70)

        conn.close()
        sys.exit(0 if all_ok else 1)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        sys.exit(1)


if __name__ == '__main__':
    main()
