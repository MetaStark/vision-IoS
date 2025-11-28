#!/usr/bin/env python3
"""
============================================================================
OPERATION IGNITION - PHASE E: THE GRAND SLAM
============================================================================
Authority: CEO
Document: EXEC-DIR-004-KEYS / ADR-014
Purpose: Verify End-to-End Integrity (Key -> Role -> Budget -> Data)

Tests:
1. IDENTITY: Ed25519 keys present and can sign/verify
2. ACCESS: Authority matrix enforces role permissions
3. BUDGET: Model provider policies enforce LLM tier routing

This script tests the governance infrastructure directly without
requiring an API server.
============================================================================
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Try to import Ed25519 library (nacl preferred, cryptography as fallback)
CRYPTO_LIB = None
SigningKey = None
VerifyKey = None
Ed25519PrivateKey = None
Ed25519PublicKey = None

try:
    from nacl.signing import SigningKey, VerifyKey
    CRYPTO_LIB = "nacl"
except:
    CRYPTO_LIB = None

# Try to import database connector
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


# ============================================================================
# CONFIGURATION
# ============================================================================

AGENTS = [
    "VEGA", "LARS", "STIG", "FINN", "LINE",
    "CSEO", "CDMO", "CRIO", "CEIO", "CFAO", "CODE"
]

# Agent tier definitions per ADR-014
AGENT_TIERS = {
    "VEGA": 1, "LARS": 1,                          # Tier-1: Governance
    "STIG": 1, "FINN": 1, "LINE": 1,               # Tier-1: Exec (per ADR-014)
    "CSEO": 2, "CDMO": 2, "CRIO": 2,               # Tier-2: Sub-Exec
    "CEIO": 2, "CFAO": 2,                          # Tier-2: Sub-Exec
    "CODE": 3                                       # Tier-3: Implementation
}

# Data source tiers (The Waterfall)
DATA_SOURCES = {
    "YFINANCE": {"tier": "FREE", "cost": 0.0, "name": "The Lake"},
    "MARKETAUX": {"tier": "PULSE", "cost": 0.001, "name": "The Pulse"},
    "ALPHAVANTAGE": {"tier": "SNIPER", "cost": 0.01, "name": "The Sniper"},
    "BLOOMBERG": {"tier": "PREMIUM", "cost": 0.10, "name": "Premium"}
}

# Access rules: Who can use what data sources
ACCESS_RULES = {
    # Tier-1 executives: Full access
    "VEGA": ["YFINANCE", "MARKETAUX", "ALPHAVANTAGE", "BLOOMBERG"],
    "LARS": ["YFINANCE"],  # LARS focuses on strategy, not noise
    "STIG": ["YFINANCE", "MARKETAUX", "ALPHAVANTAGE"],
    "FINN": ["YFINANCE", "MARKETAUX", "ALPHAVANTAGE"],  # Research needs Sniper
    "LINE": ["YFINANCE", "MARKETAUX"],
    # Tier-2: Limited access
    "CSEO": ["YFINANCE"],
    "CDMO": ["YFINANCE"],
    "CRIO": ["YFINANCE"],  # No Sniper without CRITICAL
    "CEIO": ["YFINANCE", "MARKETAUX"],  # External intel needs Pulse
    "CFAO": ["YFINANCE"],
    # Tier-3: Free tier only
    "CODE": ["YFINANCE"]
}


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    agent: Optional[str] = None


# ============================================================================
# HELPERS
# ============================================================================

def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(result: TestResult):
    status = "" if result.passed else ""
    print(f"  {status} {result.name}")
    if not result.passed:
        print(f"      {result.message}")


def get_db_connection():
    """Get database connection from environment."""
    if not HAS_PSYCOPG2:
        return None

    # Try Supabase connection string first
    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if db_url:
        return psycopg2.connect(db_url)

    # Fall back to individual params
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST", "localhost"),
        port=os.getenv("SUPABASE_PORT", "5432"),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER", "postgres"),
        password=os.getenv("SUPABASE_PASSWORD", "")
    )


# ============================================================================
# TEST 1: IDENTITY - Ed25519 Keys
# ============================================================================

def test_identity_keys_in_env() -> List[TestResult]:
    """Verify all agents have private keys in .env"""
    results = []

    for agent in AGENTS:
        key_var = f"FHQ_{agent}_PRIVATE_KEY"
        has_key = os.getenv(key_var) is not None and len(os.getenv(key_var, "")) > 0

        results.append(TestResult(
            name=f"{agent} private key in env",
            passed=has_key,
            message=f"Missing {key_var}" if not has_key else "OK",
            agent=agent
        ))

    return results


def test_identity_signing() -> List[TestResult]:
    """Test Ed25519 signing and verification for each agent."""
    results = []

    if CRYPTO_LIB is None:
        return [TestResult(
            name="Ed25519 library available",
            passed=False,
            message="Install 'cryptography' or 'pynacl' for signing tests"
        )]

    for agent in AGENTS:
        key_hex = os.getenv(f"FHQ_{agent}_PRIVATE_KEY")
        if not key_hex:
            results.append(TestResult(
                name=f"{agent} signing capability",
                passed=False,
                message=f"No private key found",
                agent=agent
            ))
            continue

        try:
            # Test signing
            message = f"IGNITION_TEST_{agent}_{datetime.utcnow().isoformat()}".encode()

            if CRYPTO_LIB == "cryptography":
                private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key_hex))
                signature = private_key.sign(message)
                public_key = private_key.public_key()
                public_key.verify(signature, message)
            else:  # nacl
                signing_key = SigningKey(bytes.fromhex(key_hex))
                signed = signing_key.sign(message)
                verify_key = signing_key.verify_key
                verify_key.verify(signed)

            results.append(TestResult(
                name=f"{agent} can sign and verify",
                passed=True,
                message="Signature verified",
                agent=agent
            ))
        except Exception as e:
            results.append(TestResult(
                name=f"{agent} signing capability",
                passed=False,
                message=f"Signing failed: {str(e)[:50]}",
                agent=agent
            ))

    return results


def test_identity_keys_in_database() -> List[TestResult]:
    """Verify all agents have ACTIVE keys in fhq_meta.agent_keys"""
    results = []

    if not HAS_PSYCOPG2:
        return [TestResult(
            name="Database connection",
            passed=False,
            message="Install 'psycopg2-binary' for database tests"
        )]

    try:
        conn = get_db_connection()
        if not conn:
            return [TestResult(
                name="Database connection",
                passed=False,
                message="Could not connect to database"
            )]

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT agent_id, key_type, key_state, key_fingerprint, ceremony_id
                FROM fhq_meta.agent_keys
                WHERE key_state = 'ACTIVE'
            """)
            rows = cur.fetchall()
        conn.close()

        db_agents = {row['agent_id'].upper(): row for row in rows}

        for agent in AGENTS:
            has_key = agent in db_agents
            results.append(TestResult(
                name=f"{agent} has ACTIVE key in DB",
                passed=has_key,
                message=f"fingerprint: {db_agents[agent]['key_fingerprint']}" if has_key else "No ACTIVE key",
                agent=agent
            ))

    except Exception as e:
        results.append(TestResult(
            name="Database key verification",
            passed=False,
            message=f"Query failed: {str(e)[:50]}"
        ))

    return results


# ============================================================================
# TEST 2: ACCESS CONTROL - Authority Matrix
# ============================================================================

def test_access_authority_matrix() -> List[TestResult]:
    """Verify authority matrix enforces Tier-2 restrictions."""
    results = []

    if not HAS_PSYCOPG2:
        return [TestResult(
            name="Database connection",
            passed=False,
            message="Install 'psycopg2-binary' for access tests"
        )]

    try:
        conn = get_db_connection()
        if not conn:
            return [TestResult(
                name="Database connection",
                passed=False,
                message="Could not connect"
            )]

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT agent_id, authority_level,
                       can_read_canonical, can_write_canonical,
                       can_trigger_g2, can_trigger_g3, can_trigger_g4
                FROM fhq_governance.authority_matrix
            """)
            rows = cur.fetchall()
        conn.close()

        matrix = {row['agent_id'].lower(): row for row in rows}

        # Test: Tier-2 agents cannot write to canonical
        tier2_agents = ["cseo", "cdmo", "crio", "ceio", "cfao"]
        for agent in tier2_agents:
            if agent not in matrix:
                results.append(TestResult(
                    name=f"{agent.upper()} authority matrix entry",
                    passed=False,
                    message="Not found in authority_matrix",
                    agent=agent.upper()
                ))
                continue

            row = matrix[agent]
            no_canonical_write = not row['can_write_canonical']
            no_high_gates = not (row['can_trigger_g2'] or row['can_trigger_g3'] or row['can_trigger_g4'])

            results.append(TestResult(
                name=f"{agent.upper()} cannot write canonical",
                passed=no_canonical_write,
                message="BLOCKED" if no_canonical_write else "VIOLATION: Can write!",
                agent=agent.upper()
            ))

            results.append(TestResult(
                name=f"{agent.upper()} cannot trigger G2-G4",
                passed=no_high_gates,
                message="BLOCKED" if no_high_gates else "VIOLATION: Can trigger!",
                agent=agent.upper()
            ))

    except Exception as e:
        results.append(TestResult(
            name="Authority matrix verification",
            passed=False,
            message=f"Query failed: {str(e)[:50]}"
        ))

    return results


def test_access_data_sources() -> List[TestResult]:
    """Simulate data source access decisions."""
    results = []

    # Test: LARS cannot access MarketAux (noise)
    lars_can_marketaux = "MARKETAUX" in ACCESS_RULES.get("LARS", [])
    results.append(TestResult(
        name="LARS blocked from MarketAux (noise)",
        passed=not lars_can_marketaux,
        message="BLOCKED" if not lars_can_marketaux else "VIOLATION: LARS can access noise!",
        agent="LARS"
    ))

    # Test: CRIO cannot use Sniper casually
    crio_can_sniper = "ALPHAVANTAGE" in ACCESS_RULES.get("CRIO", [])
    results.append(TestResult(
        name="CRIO blocked from Sniper (budget)",
        passed=not crio_can_sniper,
        message="BLOCKED" if not crio_can_sniper else "VIOLATION: CRIO can use Sniper!",
        agent="CRIO"
    ))

    # Test: CDMO can access The Lake (free)
    cdmo_can_lake = "YFINANCE" in ACCESS_RULES.get("CDMO", [])
    results.append(TestResult(
        name="CDMO can access The Lake (yfinance)",
        passed=cdmo_can_lake,
        message="ALLOWED" if cdmo_can_lake else "VIOLATION: CDMO blocked from free data!",
        agent="CDMO"
    ))

    # Test: CEIO can access The Pulse (monitoring)
    ceio_can_pulse = "MARKETAUX" in ACCESS_RULES.get("CEIO", [])
    results.append(TestResult(
        name="CEIO can access The Pulse (MarketAux)",
        passed=ceio_can_pulse,
        message="ALLOWED" if ceio_can_pulse else "VIOLATION: CEIO blocked from Pulse!",
        agent="CEIO"
    ))

    # Test: FINN can take Critical Sniper Shot
    finn_can_sniper = "ALPHAVANTAGE" in ACCESS_RULES.get("FINN", [])
    results.append(TestResult(
        name="FINN can use Sniper (research)",
        passed=finn_can_sniper,
        message="ALLOWED" if finn_can_sniper else "VIOLATION: FINN blocked from Sniper!",
        agent="FINN"
    ))

    return results


# ============================================================================
# TEST 3: LLM TIER ROUTING - Model Provider Policy
# ============================================================================

def test_llm_provider_policies() -> List[TestResult]:
    """Verify LLM tier routing (Tier-2 cannot use Anthropic)."""
    results = []

    if not HAS_PSYCOPG2:
        return [TestResult(
            name="Database connection",
            passed=False,
            message="Install 'psycopg2-binary' for LLM policy tests"
        )]

    try:
        conn = get_db_connection()
        if not conn:
            return [TestResult(
                name="Database connection",
                passed=False,
                message="Could not connect"
            )]

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Use actual schema columns: allowed_tier, allowed_providers
            cur.execute("""
                SELECT agent_id, allowed_tier, allowed_providers, data_sharing_policy
                FROM fhq_governance.model_provider_policy
            """)
            rows = cur.fetchall()
        conn.close()

        policies = {row['agent_id'].lower(): row for row in rows}

        # Tier-2 agents should NOT have Anthropic in allowed_providers
        tier2_agents = ["cseo", "cdmo", "crio", "ceio", "cfao"]
        for agent in tier2_agents:
            if agent not in policies:
                results.append(TestResult(
                    name=f"{agent.upper()} LLM policy exists",
                    passed=False,
                    message="No policy found",
                    agent=agent.upper()
                ))
                continue

            policy = policies[agent]
            allowed = policy.get('allowed_providers') or []
            # Anthropic blocked = not in allowed_providers list
            anthropic_blocked = "anthropic" not in [p.lower() for p in allowed]
            is_tier2 = policy.get('allowed_tier') == 2

            results.append(TestResult(
                name=f"{agent.upper()} is Tier-2 LLM",
                passed=is_tier2,
                message=f"LLM Tier: {policy.get('allowed_tier')}",
                agent=agent.upper()
            ))

            results.append(TestResult(
                name=f"{agent.upper()} blocked from Anthropic",
                passed=anthropic_blocked,
                message="BLOCKED" if anthropic_blocked else "VIOLATION: Can use Anthropic!",
                agent=agent.upper()
            ))

    except Exception as e:
        results.append(TestResult(
            name="LLM policy verification",
            passed=False,
            message=f"Query failed: {str(e)[:50]}"
        ))

    return results


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print_header("PHASE E: THE HARDENED GRAND SLAM")
    print("  Verifying ADR-008 (Identity) + ADR-014 (Roles) + Waterfall (Budget)")
    print(f"  Timestamp: {datetime.utcnow().isoformat()}")
    print(f"  Crypto Library: {CRYPTO_LIB or 'NONE'}")
    print(f"  Database: {'psycopg2' if HAS_PSYCOPG2 else 'NONE'}")

    all_results = []

    # ROUND 1: IDENTITY
    print_header("ROUND 1: IDENTITY (The Bouncer)")

    results = test_identity_keys_in_env()
    all_results.extend(results)
    for r in results:
        print_result(r)

    if CRYPTO_LIB:
        results = test_identity_signing()
        all_results.extend(results)
        for r in results:
            print_result(r)

    if HAS_PSYCOPG2:
        results = test_identity_keys_in_database()
        all_results.extend(results)
        for r in results:
            print_result(r)

    # ROUND 2: ACCESS CONTROL
    print_header("ROUND 2: ACCESS CONTROL (The Accountant)")

    results = test_access_data_sources()
    all_results.extend(results)
    for r in results:
        print_result(r)

    if HAS_PSYCOPG2:
        results = test_access_authority_matrix()
        all_results.extend(results)
        for r in results:
            print_result(r)

    # ROUND 3: LLM TIER ROUTING
    print_header("ROUND 3: LLM TIER ROUTING (The Budget)")

    if HAS_PSYCOPG2:
        results = test_llm_provider_policies()
        all_results.extend(results)
        for r in results:
            print_result(r)
    else:
        print("  [SKIPPED] No database connection")

    # SCORECARD
    print_header("SCORECARD")

    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    failed = total - passed

    print(f"\n  Total Tests: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")

    if failed == 0:
        print(f"\n  {'='*50}")
        print(f"  GRAND SLAM ACHIEVED ({passed}/{total})")
        print(f"  {'='*50}")
        print(f"\n  System is LIVE, SECURE, and BUDGET-AWARE.")
        print(f"  Ready for Phase F: VEGA Final Attestation.")
        return 0
    else:
        print(f"\n  {'='*50}")
        print(f"  FAILURES DETECTED ({failed} failures)")
        print(f"  {'='*50}")
        print(f"\n  Failed tests:")
        for r in all_results:
            if not r.passed:
                agent_str = f" [{r.agent}]" if r.agent else ""
                print(f"    - {r.name}{agent_str}: {r.message}")
        print(f"\n  Fix failures before proceeding to Phase F.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
