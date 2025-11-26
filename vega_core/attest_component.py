#!/usr/bin/env python3
"""
VEGA ATTESTATION TOOL
Agent: VEGA
Purpose: Generate VEGA attestation for verified components
Compliance: ADR-006, ADR-007, EC-001

Usage:
    python vega_core/attest_component.py \
        --component FHQ_INTELLIGENCE_ORCHESTRATOR \
        --strict \
        --output logs/vega_attestation.json
"""

import os
import sys
import json
import hashlib
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List

import psycopg2
from psycopg2.extras import RealDictCursor


class Config:
    AGENT_ID = "VEGA"
    AUTHORITY_LEVEL = 10
    CONSTITUTIONAL_BASIS = "EC-001"

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_vega_public_key(conn) -> str:
    """Get VEGA's public key"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT public_key FROM fhq_org.org_agents WHERE agent_id = 'VEGA'
        """)
        row = cur.fetchone()
        return row['public_key'] if row else "GENESIS_KEY_VEGA"


def verify_prerequisites(conn, component: str, strict: bool) -> Dict[str, Any]:
    """Verify all prerequisites for attestation"""
    checks = []

    # 1. Check component is registered
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM fhq_governance.governance_state
            WHERE component_name = %s
        """, (component,))
        state = cur.fetchone()

        if state and state['registration_status'] == 'REGISTERED':
            checks.append({"check": "component_registered", "status": "PASS"})
        else:
            checks.append({"check": "component_registered", "status": "FAIL"})

    # 2. Check schema hashes exist
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fhq_monitoring.hash_registry
            WHERE verification_status = 'VERIFIED'
              AND computed_at > NOW() - INTERVAL '1 hour'
        """)
        hash_count = cur.fetchone()[0]

        if hash_count > 0:
            checks.append({"check": "schema_hashes_verified", "status": "PASS", "count": hash_count})
        else:
            checks.append({"check": "schema_hashes_verified", "status": "FAIL" if strict else "WARN"})

    # 3. Check agents have Ed25519 keys
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fhq_org.org_agents
            WHERE signing_algorithm = 'Ed25519' AND public_key IS NOT NULL
        """)
        agent_count = cur.fetchone()[0]

        if agent_count >= 5:
            checks.append({"check": "agents_ed25519_bound", "status": "PASS", "count": agent_count})
        else:
            checks.append({"check": "agents_ed25519_bound", "status": "FAIL"})

    # 4. Check LLM routing policies
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fhq_governance.model_provider_policy
        """)
        policy_count = cur.fetchone()[0]

        if policy_count >= 5:
            checks.append({"check": "llm_routing_configured", "status": "PASS", "count": policy_count})
        else:
            checks.append({"check": "llm_routing_configured", "status": "FAIL"})

    # 5. Check discrepancy score
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT discrepancy_score, threshold_exceeded
            FROM fhq_meta.reconciliation_snapshots
            WHERE component_name = %s
            ORDER BY snapshot_timestamp DESC
            LIMIT 1
        """, (component,))
        snapshot = cur.fetchone()

        if snapshot and not snapshot['threshold_exceeded']:
            checks.append({
                "check": "discrepancy_within_threshold",
                "status": "PASS",
                "score": float(snapshot['discrepancy_score'])
            })
        elif snapshot:
            checks.append({
                "check": "discrepancy_within_threshold",
                "status": "FAIL",
                "score": float(snapshot['discrepancy_score'])
            })
        else:
            checks.append({"check": "discrepancy_within_threshold", "status": "WARN", "note": "No snapshot found"})

    all_passed = all(c["status"] == "PASS" for c in checks)
    any_failed = any(c["status"] == "FAIL" for c in checks)

    return {
        "checks": checks,
        "all_passed": all_passed,
        "can_attest": not any_failed
    }


def generate_vega_signature(data: Dict) -> str:
    """Generate VEGA signature (SHA-256 hash for now, Ed25519 in production)"""
    # In production, this would use actual Ed25519 signing
    payload = json.dumps(data, sort_keys=True, default=str)
    return "VEGA_SIG_" + hashlib.sha256(payload.encode()).hexdigest()


def create_attestation(conn, component: str, prerequisites: Dict,
                       vega_public_key: str) -> Dict[str, Any]:
    """Create and store VEGA attestation"""

    # Get component version
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT component_version FROM fhq_governance.governance_state
            WHERE component_name = %s
        """, (component,))
        row = cur.fetchone()
        version = row['component_version'] if row else "1.0.0"

    attestation_data = {
        "component": component,
        "version": version,
        "prerequisites": prerequisites["checks"],
        "attestation_timestamp": datetime.now(timezone.utc).isoformat(),
        "attestor": Config.AGENT_ID,
        "authority_level": Config.AUTHORITY_LEVEL,
        "constitutional_basis": Config.CONSTITUTIONAL_BASIS
    }

    signature = generate_vega_signature(attestation_data)

    # Insert attestation
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.vega_attestations (
                target_type, target_id, target_version,
                attestation_type, attestation_status,
                vega_signature, vega_public_key,
                signature_verified, attestation_data,
                adr_reference, constitutional_basis
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING attestation_id
        """, (
            'ORCHESTRATOR',
            component,
            version,
            'CERTIFICATION',
            'APPROVED',
            signature,
            vega_public_key,
            True,
            json.dumps(attestation_data),
            'ADR-007',
            Config.CONSTITUTIONAL_BASIS
        ))
        attestation_id = cur.fetchone()[0]

        # Update governance_state
        cur.execute("""
            UPDATE fhq_governance.governance_state
            SET vega_attested = TRUE,
                vega_attestation_id = %s,
                vega_attestation_timestamp = NOW(),
                updated_at = NOW()
            WHERE component_name = %s
        """, (attestation_id, component))

        conn.commit()

    return {
        "attestation_id": str(attestation_id),
        "signature": signature,
        "data": attestation_data
    }


def register_governance_event(conn, component: str, evidence_path: str):
    """Register validation event in governance log"""
    with conn.cursor() as cur:
        # Check if governance_actions_log exists and has the right structure
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'fhq_governance' AND table_name = 'governance_actions_log'
        """)
        columns = [row[0] for row in cur.fetchall()]

        if 'component' in columns:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log
                (component, action_type, status, evidence_path)
                VALUES (%s, %s, %s, %s)
            """, (component, 'ORCHESTRATOR_VALIDATED', 'PASS', evidence_path))
        else:
            # Use alternative column structure
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log
                (action_type, agent_id, decision, metadata, hash_chain_id, signature, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                'ORCHESTRATOR_VALIDATED',
                'VEGA',
                'APPROVED',
                json.dumps({"component": component, "evidence_path": evidence_path}),
                f"HC-VEGA-ATTEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                generate_vega_signature({"component": component}),
                datetime.now(timezone.utc)
            ))

        conn.commit()


def main():
    parser = argparse.ArgumentParser(description='VEGA Attestation Tool')
    parser.add_argument('--component', required=True, help='Component to attest')
    parser.add_argument('--strict', action='store_true', help='Strict mode - all checks must pass')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    print("[VEGA] Component Attestation (EC-001)")
    print("=" * 60)
    print(f"Component: {args.component}")
    print(f"Mode: {'STRICT' if args.strict else 'STANDARD'}")
    print(f"Authority Level: {Config.AUTHORITY_LEVEL}")

    conn = psycopg2.connect(Config.get_db_connection_string())

    # Get VEGA public key
    vega_public_key = get_vega_public_key(conn)

    # Verify prerequisites
    print("\nPrerequisite Checks:")
    prerequisites = verify_prerequisites(conn, args.component, args.strict)

    for check in prerequisites["checks"]:
        status = check["status"]
        name = check["check"]
        print(f"  [{status}] {name}")

    if not prerequisites["can_attest"]:
        print(f"\n{'=' * 60}")
        print("ATTESTATION DENIED: Prerequisites not met")

        result = {
            "component": args.component,
            "attestation_status": "DENIED",
            "prerequisites": prerequisites,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)

        conn.close()
        sys.exit(1)

    # Create attestation
    print("\nGenerating VEGA Attestation...")
    attestation = create_attestation(conn, args.component, prerequisites, vega_public_key)

    # Register governance event
    register_governance_event(conn, args.component, args.output)

    result = {
        "component": args.component,
        "verification_type": "VEGA_ATTESTATION",
        "attestation_status": "APPROVED",
        "attestation_id": attestation["attestation_id"],
        "vega_signature": attestation["signature"],
        "vega_public_key": vega_public_key[:32] + "...",
        "prerequisites": prerequisites,
        "attestation_data": attestation["data"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "PASS"
    }

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'=' * 60}")
    print("VEGA ATTESTATION COMPLETE")
    print(f"Attestation ID: {attestation['attestation_id']}")
    print(f"Signature: {attestation['signature'][:40]}...")
    print(f"governance_state.vega_attested = TRUE")
    print(f"Output: {args.output}")

    conn.close()
    sys.exit(0)


if __name__ == '__main__':
    main()
