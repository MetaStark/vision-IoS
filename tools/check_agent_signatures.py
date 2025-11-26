#!/usr/bin/env python3
"""
AGENT SIGNATURE VALIDATION TOOL
Agent: STIG
Purpose: Verify Ed25519 key bindings for all agents
Compliance: ADR-007 Section 10.2, ADR-008

Usage:
    python tools/check_agent_signatures.py \
        --agents LARS STIG LINE FINN VEGA \
        --required-ed25519 \
        --output logs/agent_key_validation.json
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List

import psycopg2
from psycopg2.extras import RealDictCursor


class Config:
    AGENT_ID = "STIG"

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def validate_agent(conn, agent_id: str, require_ed25519: bool) -> Dict[str, Any]:
    """Validate a single agent's key binding"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT agent_id, agent_name, agent_role, authority_level,
                   public_key, signing_algorithm, llm_tier, llm_provider,
                   is_active, is_suspended
            FROM fhq_org.org_agents
            WHERE agent_id = %s
        """, (agent_id,))

        agent = cur.fetchone()

        if not agent:
            return {
                "agent_id": agent_id,
                "status": "FAIL",
                "error": "Agent not found in org_agents"
            }

        checks = []

        # Check public_key exists
        if agent['public_key']:
            checks.append({"check": "public_key_present", "status": "PASS"})
        else:
            checks.append({"check": "public_key_present", "status": "FAIL", "error": "Missing public_key"})

        # Check Ed25519 algorithm
        if require_ed25519:
            if agent['signing_algorithm'] == 'Ed25519':
                checks.append({"check": "ed25519_algorithm", "status": "PASS"})
            else:
                checks.append({"check": "ed25519_algorithm", "status": "FAIL",
                              "error": f"Expected Ed25519, got {agent['signing_algorithm']}"})

        # Check LLM tier assigned
        if agent['llm_tier']:
            checks.append({"check": "llm_tier_assigned", "status": "PASS", "tier": agent['llm_tier']})
        else:
            checks.append({"check": "llm_tier_assigned", "status": "FAIL", "error": "No LLM tier assigned"})

        # Check not suspended
        if not agent['is_suspended']:
            checks.append({"check": "not_suspended", "status": "PASS"})
        else:
            checks.append({"check": "not_suspended", "status": "FAIL", "error": "Agent is suspended"})

        all_passed = all(c["status"] == "PASS" for c in checks)

        return {
            "agent_id": agent_id,
            "agent_name": agent['agent_name'],
            "agent_role": agent['agent_role'],
            "authority_level": agent['authority_level'],
            "signing_algorithm": agent['signing_algorithm'],
            "llm_tier": agent['llm_tier'],
            "llm_provider": agent['llm_provider'],
            "public_key_prefix": agent['public_key'][:32] + "..." if agent['public_key'] else None,
            "checks": checks,
            "status": "PASS" if all_passed else "FAIL"
        }


def main():
    parser = argparse.ArgumentParser(description='Agent Signature Validation Tool')
    parser.add_argument('--agents', nargs='+', required=True, help='Agents to validate')
    parser.add_argument('--required-ed25519', action='store_true', help='Require Ed25519 algorithm')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    print("[STIG] Agent Signature Validation")
    print("=" * 60)

    conn = psycopg2.connect(Config.get_db_connection_string())

    result = {
        "verification_type": "AGENT_KEY_VALIDATION",
        "agent": Config.AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "require_ed25519": args.required_ed25519,
        "agents": [],
        "summary": {
            "total": len(args.agents),
            "passed": 0,
            "failed": 0
        }
    }

    for agent_id in args.agents:
        validation = validate_agent(conn, agent_id, args.required_ed25519)
        result["agents"].append(validation)

        if validation["status"] == "PASS":
            result["summary"]["passed"] += 1
            print(f"  [PASS] {agent_id}: Ed25519 bound, Tier-{validation.get('llm_tier', '?')}")
        else:
            result["summary"]["failed"] += 1
            print(f"  [FAIL] {agent_id}: {validation.get('error', 'Validation failed')}")

    result["status"] = "PASS" if result["summary"]["failed"] == 0 else "FAIL"

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"RESULT: {result['status']}")
    print(f"Agents: {result['summary']['passed']}/{result['summary']['total']} PASS")
    print(f"Output: {args.output}")

    conn.close()
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == '__main__':
    main()
