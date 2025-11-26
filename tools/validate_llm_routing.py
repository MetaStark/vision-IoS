#!/usr/bin/env python3
"""
LLM ROUTING VALIDATION TOOL
Agent: STIG
Purpose: Verify LLM tier routing policies per ADR-007
Compliance: ADR-007 Section 10.3, ADR-012

Usage:
    python tools/validate_llm_routing.py \
        --component FHQ_INTELLIGENCE_ORCHESTRATOR \
        --output logs/llm_routing_validation.json
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor


class Config:
    AGENT_ID = "STIG"

    # Expected tier assignments per ADR-007 Section 4.5
    EXPECTED_TIERS = {
        "LARS": {"tier": 1, "providers": ["Anthropic Claude"], "data_sharing": "PROHIBITED"},
        "VEGA": {"tier": 1, "providers": ["Anthropic Claude"], "data_sharing": "PROHIBITED"},
        "FINN": {"tier": 2, "providers": ["OpenAI"], "data_sharing": "PROHIBITED"},
        "STIG": {"tier": 3, "providers": ["DeepSeek", "OpenAI"], "data_sharing": "ALLOWED"},
        "LINE": {"tier": 3, "providers": ["DeepSeek", "OpenAI"], "data_sharing": "ALLOWED"},
    }

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def validate_routing_policies(conn) -> Dict[str, Any]:
    """Validate all LLM routing policies"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT agent_id, allowed_tier, allowed_providers, data_sharing_policy
            FROM fhq_governance.model_provider_policy
        """)
        policies = {row['agent_id']: dict(row) for row in cur.fetchall()}

    validations = []

    for agent_id, expected in Config.EXPECTED_TIERS.items():
        policy = policies.get(agent_id)

        if not policy:
            validations.append({
                "agent_id": agent_id,
                "status": "FAIL",
                "error": "No routing policy found"
            })
            continue

        checks = []

        # Check tier
        if policy['allowed_tier'] == expected['tier']:
            checks.append({"check": "tier_match", "status": "PASS",
                          "expected": expected['tier'], "actual": policy['allowed_tier']})
        else:
            checks.append({"check": "tier_match", "status": "FAIL",
                          "expected": expected['tier'], "actual": policy['allowed_tier']})

        # Check data sharing policy
        if policy['data_sharing_policy'] == expected['data_sharing']:
            checks.append({"check": "data_sharing_policy", "status": "PASS"})
        else:
            checks.append({"check": "data_sharing_policy", "status": "FAIL",
                          "expected": expected['data_sharing'], "actual": policy['data_sharing_policy']})

        all_passed = all(c["status"] == "PASS" for c in checks)

        validations.append({
            "agent_id": agent_id,
            "expected_tier": expected['tier'],
            "actual_tier": policy['allowed_tier'],
            "expected_data_sharing": expected['data_sharing'],
            "actual_data_sharing": policy['data_sharing_policy'],
            "checks": checks,
            "status": "PASS" if all_passed else "FAIL"
        })

    return validations


def check_routing_violations(conn, hours: int = 24) -> Dict[str, Any]:
    """Check for routing violations in recent logs"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT COUNT(*) as violation_count
            FROM fhq_governance.llm_routing_log
            WHERE violation_detected = TRUE
              AND request_timestamp > NOW() - INTERVAL '%s hours'
        """, (hours,))
        result = cur.fetchone()

        return {
            "period_hours": hours,
            "violations_found": result['violation_count'],
            "status": "PASS" if result['violation_count'] == 0 else "FAIL"
        }


def main():
    parser = argparse.ArgumentParser(description='LLM Routing Validation Tool')
    parser.add_argument('--component', required=True, help='Component name')
    parser.add_argument('--output', required=True, help='Output JSON file')
    args = parser.parse_args()

    print("[STIG] LLM Routing Validation")
    print("=" * 60)

    conn = psycopg2.connect(Config.get_db_connection_string())

    # Validate policies
    policy_validations = validate_routing_policies(conn)

    # Check for violations
    violation_check = check_routing_violations(conn)

    result = {
        "component": args.component,
        "verification_type": "LLM_ROUTING_VALIDATION",
        "agent": Config.AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "policy_validations": policy_validations,
        "violation_check": violation_check,
        "summary": {
            "total_agents": len(policy_validations),
            "passed": sum(1 for v in policy_validations if v["status"] == "PASS"),
            "failed": sum(1 for v in policy_validations if v["status"] == "FAIL"),
            "violations_24h": violation_check["violations_found"]
        }
    }

    print("\nTier Assignments:")
    for v in policy_validations:
        status = "[PASS]" if v["status"] == "PASS" else "[FAIL]"
        print(f"  {status} {v['agent_id']}: Tier-{v.get('actual_tier', '?')}")

    print(f"\nViolation Check (24h): {violation_check['status']}")

    result["status"] = "PASS" if (
        result["summary"]["failed"] == 0 and
        violation_check["status"] == "PASS"
    ) else "FAIL"

    # Write output
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"RESULT: {result['status']}")
    print(f"Policies: {result['summary']['passed']}/{result['summary']['total_agents']} PASS")
    print(f"Output: {args.output}")

    conn.close()
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == '__main__':
    main()
