#!/usr/bin/env python3
"""
RECONCILIATION SELF-TEST TOOL
Agent: STIG
Purpose: Verify discrepancy scoring engine functionality
Compliance: ADR-007 Section 10.4, ADR-010

Usage:
    python tools/run_reconciliation_selftest.py \
        --component FHQ_INTELLIGENCE_ORCHESTRATOR \
        --output logs/reconciliation_selftest.json
"""

import os
import sys
import json
import hashlib
import argparse
from datetime import datetime, timezone
from typing import Dict, Any
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor


class Config:
    AGENT_ID = "STIG"
    MAX_DISCREPANCY = 0.05  # Orchestrator must not exceed 0.05

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_canonical_state(conn, component: str) -> Dict[str, Any]:
    """Get canonical state from governance_state"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT component_type, component_name, component_version,
                   registration_status, authority_chain, adr_compliance,
                   vega_attested, is_active, configuration
            FROM fhq_governance.governance_state
            WHERE component_name = %s
        """, (component,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return {}


def get_agent_state(conn, component: str) -> Dict[str, Any]:
    """Get current agent state (simulated for orchestrator)"""
    # For orchestrator, agent state should match canonical state
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get agent configurations
        cur.execute("""
            SELECT agent_id, llm_tier, signing_algorithm, is_active
            FROM fhq_org.org_agents
            ORDER BY agent_id
        """)
        agents = {row['agent_id']: dict(row) for row in cur.fetchall()}

        # Get routing policies
        cur.execute("""
            SELECT agent_id, allowed_tier, data_sharing_policy
            FROM fhq_governance.model_provider_policy
        """)
        policies = {row['agent_id']: dict(row) for row in cur.fetchall()}

        return {
            "agents": agents,
            "policies": policies,
            "component": component
        }


def compute_discrepancy_score(canonical: Dict, agent: Dict) -> float:
    """Compute weighted discrepancy score per ADR-010"""
    # Field weights per ADR-010
    weights = {
        "component_exists": 1.0,
        "registration_status": 0.8,
        "agent_count": 0.7,
        "policy_count": 0.7,
        "vega_attestation": 0.5,
    }

    discrepancies = []

    # Check component exists
    if canonical:
        discrepancies.append(("component_exists", 0.0))
    else:
        discrepancies.append(("component_exists", 1.0))
        return 1.0  # Critical failure

    # Check registration status
    if canonical.get('registration_status') == 'REGISTERED':
        discrepancies.append(("registration_status", 0.0))
    else:
        discrepancies.append(("registration_status", 1.0))

    # Check agent count (expect 5)
    agent_count = len(agent.get('agents', {}))
    if agent_count == 5:
        discrepancies.append(("agent_count", 0.0))
    else:
        discrepancies.append(("agent_count", abs(5 - agent_count) / 5))

    # Check policy count (expect 5)
    policy_count = len(agent.get('policies', {}))
    if policy_count == 5:
        discrepancies.append(("policy_count", 0.0))
    else:
        discrepancies.append(("policy_count", abs(5 - policy_count) / 5))

    # Compute weighted score
    total_weight = sum(weights.get(field, 0.5) for field, _ in discrepancies)
    weighted_score = sum(
        weights.get(field, 0.5) * score
        for field, score in discrepancies
    ) / total_weight

    return round(weighted_score, 6)


def store_reconciliation_snapshot(conn, component: str, canonical: Dict,
                                   agent: Dict, score: float) -> str:
    """Store reconciliation snapshot"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_meta.reconciliation_snapshots (
                component_name, snapshot_type,
                agent_state, canonical_state,
                discrepancy_score, discrepancy_threshold,
                threshold_exceeded, reconciliation_status,
                created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING snapshot_id
        """, (
            component,
            'SELF_TEST',
            json.dumps(agent, default=str),
            json.dumps(canonical, default=str),
            score,
            Config.MAX_DISCREPANCY,
            score > Config.MAX_DISCREPANCY,
            'RECONCILED' if score <= Config.MAX_DISCREPANCY else 'DIVERGENT',
            Config.AGENT_ID
        ))
        snapshot_id = cur.fetchone()[0]
        conn.commit()
        return str(snapshot_id)


def main():
    parser = argparse.ArgumentParser(description='Reconciliation Self-Test Tool')
    parser.add_argument('--component', required=True, help='Component name')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    print("[STIG] Reconciliation Self-Test (ADR-010)")
    print("=" * 60)

    conn = psycopg2.connect(Config.get_db_connection_string())

    # Get states
    canonical_state = get_canonical_state(conn, args.component)
    agent_state = get_agent_state(conn, args.component)

    # Compute discrepancy
    discrepancy_score = compute_discrepancy_score(canonical_state, agent_state)

    print(f"\nComponent: {args.component}")
    print(f"Discrepancy Score: {discrepancy_score:.6f}")
    print(f"Threshold: {Config.MAX_DISCREPANCY}")
    print(f"Status: {'PASS' if discrepancy_score <= Config.MAX_DISCREPANCY else 'FAIL'}")

    # Store snapshot
    snapshot_id = store_reconciliation_snapshot(
        conn, args.component, canonical_state, agent_state, discrepancy_score
    )
    print(f"Snapshot ID: {snapshot_id}")

    result = {
        "component": args.component,
        "verification_type": "RECONCILIATION_SELFTEST",
        "agent": Config.AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "discrepancy_score": discrepancy_score,
        "threshold": Config.MAX_DISCREPANCY,
        "threshold_exceeded": discrepancy_score > Config.MAX_DISCREPANCY,
        "snapshot_id": snapshot_id,
        "canonical_state_summary": {
            "component_name": canonical_state.get('component_name'),
            "version": canonical_state.get('component_version'),
            "registration_status": canonical_state.get('registration_status'),
            "vega_attested": canonical_state.get('vega_attested')
        },
        "agent_state_summary": {
            "agent_count": len(agent_state.get('agents', {})),
            "policy_count": len(agent_state.get('policies', {}))
        },
        "status": "PASS" if discrepancy_score <= Config.MAX_DISCREPANCY else "FAIL"
    }

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"RESULT: {result['status']}")
    print(f"Output: {args.output}")

    conn.close()
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == '__main__':
    main()
