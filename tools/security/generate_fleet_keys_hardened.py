#!/usr/bin/env python3
"""
=============================================================================
FjordHQ Fleet Key Generation Script (SOP-008)
=============================================================================
Authority: EXEC-DIR-004-KEYS (Boardroom Directive: Phase D Identity Sovereignty)
Reference: ADR-008 (Cryptographic Key Management)
Executor: CODE (Clearance Level 3)
Auditor: VEGA (Constitutional Guardrail)

HIGH-SECURITY OPERATION:
- Location: Local Secure Terminal (No Cloud Shells)
- Output: Private keys to .env (memory), Public keys to SQL (ledger)
- Trace: None (No .key files on disk)

Zero Trust Rule: No agent operates without a verified Ed25519 identity keypair
anchored in fhq_meta.agent_keys and attested by VEGA.
=============================================================================
"""

import os
import sys
import datetime
import hashlib
import argparse
from typing import Tuple, Dict, List

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("ERROR: cryptography package not installed.")
    print("Install with: pip install cryptography>=43.0.0")
    sys.exit(1)

# =============================================================================
# CONSTITUTIONAL FLEET DEFINITION (11 SOVEREIGNS)
# =============================================================================

# Agent hierarchy per ADR-001, ADR-007, ADR-014
FLEET_AGENTS: List[Dict] = [
    # Tier-1 Executive (Constitutional Authority)
    {"id": "VEGA", "tier": 1, "role": "Auditor", "authority": 10, "parent": None},
    {"id": "LARS", "tier": 1, "role": "Strategy", "authority": 9, "parent": None},

    # Tier-2 Executive
    {"id": "STIG", "tier": 2, "role": "Implementation", "authority": 8, "parent": "LARS"},
    {"id": "FINN", "tier": 2, "role": "Research", "authority": 8, "parent": "LARS"},
    {"id": "LINE", "tier": 2, "role": "SRE", "authority": 8, "parent": "LARS"},

    # Tier-2 Sub-Executive (ADR-014)
    {"id": "CSEO", "tier": 2, "role": "Strategy & Experimentation", "authority": 2, "parent": "LARS"},
    {"id": "CDMO", "tier": 2, "role": "Data & Memory", "authority": 2, "parent": "STIG"},
    {"id": "CRIO", "tier": 2, "role": "Research & Insight", "authority": 2, "parent": "FINN"},
    {"id": "CEIO", "tier": 2, "role": "External Intelligence", "authority": 2, "parent": "STIG"},
    {"id": "CFAO", "tier": 2, "role": "Foresight & Autonomy", "authority": 2, "parent": "LARS"},

    # Tier-3 Engineering
    {"id": "CODE", "tier": 3, "role": "Engineering", "authority": 3, "parent": "STIG"},
]

# Extract just the agent IDs for backward compatibility
AGENTS: List[str] = [agent["id"] for agent in FLEET_AGENTS]


def generate_ed25519_keypair() -> Tuple[str, str]:
    """
    Generate a new Ed25519 keypair.

    Returns:
        Tuple of (private_key_hex, public_key_hex)

    Security Notes:
        - Keys are generated using cryptography library's secure random
        - Private key is 32 bytes (64 hex chars)
        - Public key is 32 bytes (64 hex chars)
        - Ed25519 provides 128-bit security level
    """
    # Generate private key using secure random
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Extract raw bytes
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    return private_bytes.hex(), public_bytes.hex()


def compute_key_fingerprint(public_key_hex: str) -> str:
    """
    Compute SHA-256 fingerprint of public key for identification.

    Args:
        public_key_hex: Hexadecimal public key

    Returns:
        First 16 characters of SHA-256 hash (short fingerprint)
    """
    return hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:16]


def generate_ceremony_id() -> str:
    """Generate unique ceremony identifier."""
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"CEREMONY_IGNITION_{timestamp}"


def generate_fleet_keys(
    agents: List[str] = AGENTS,
    ceremony_id: str = None,
    dry_run: bool = False
) -> Dict:
    """
    Generate Ed25519 keypairs for the entire fleet.

    Args:
        agents: List of agent IDs to generate keys for
        ceremony_id: Unique ceremony identifier
        dry_run: If True, don't output sensitive data

    Returns:
        Dictionary containing ceremony results
    """
    if ceremony_id is None:
        ceremony_id = generate_ceremony_id()

    utc_now = datetime.datetime.utcnow()
    print(f"{'='*72}")
    print(f"FjordHQ KEY CEREMONY - SOP-008")
    print(f"{'='*72}")
    print(f"Ceremony ID: {ceremony_id}")
    print(f"Timestamp:   {utc_now.isoformat()}Z")
    print(f"Executor:    CODE (Clearance Level 3)")
    print(f"Auditor:     VEGA (Constitutional Guardrail)")
    print(f"Agents:      {len(agents)}")
    print(f"{'='*72}")
    print()

    # Generate keys for each agent
    results = {
        "ceremony_id": ceremony_id,
        "timestamp": utc_now.isoformat(),
        "agents": {},
        "sql_statements": [],
        "env_lines": []
    }

    for agent_id in agents:
        private_hex, public_hex = generate_ed25519_keypair()
        fingerprint = compute_key_fingerprint(public_hex)

        results["agents"][agent_id] = {
            "public_key": public_hex,
            "private_key": private_hex if not dry_run else "[REDACTED]",
            "fingerprint": fingerprint
        }

        # Generate SQL statement (with idempotent check)
        # Note: Uses actual schema columns from fhq_meta.agent_keys
        # key_type must be 'ED25519_SIGNING' or 'ED25519_VERIFICATION' (CHECK constraint)
        # key_state must be 'PENDING', 'ACTIVE', 'DEPRECATED', 'ARCHIVED' (CHECK constraint)
        # key_storage_tier must be 'TIER1_HOT', 'TIER2_WARM', 'TIER3_COLD' (CHECK constraint)
        sql = f"""
INSERT INTO fhq_meta.agent_keys (
    key_id, agent_id, key_type, key_state, public_key_hex,
    key_storage_tier, activation_date, key_fingerprint, ceremony_id
)
SELECT
    gen_random_uuid(),
    '{agent_id}',
    'ED25519_SIGNING',
    'ACTIVE',
    '{public_hex}',
    'TIER1_HOT',
    NOW(),
    '{fingerprint}',
    '{ceremony_id}'
WHERE NOT EXISTS (
    SELECT 1 FROM fhq_meta.agent_keys
    WHERE agent_id = '{agent_id}' AND key_state = 'ACTIVE'
);"""
        results["sql_statements"].append(sql.strip())

        # Generate update for org_agents.public_key
        update_sql = f"""
UPDATE fhq_org.org_agents
SET public_key = '{public_hex}',
    key_registered_at = NOW(),
    updated_at = NOW()
WHERE agent_id = '{agent_id}' OR UPPER(agent_id) = '{agent_id}';"""
        results["sql_statements"].append(update_sql.strip())

        # Generate .env line
        env_line = f"FHQ_{agent_id}_PRIVATE_KEY={private_hex}"
        results["env_lines"].append(env_line if not dry_run else f"FHQ_{agent_id}_PRIVATE_KEY=[REDACTED]")

    # Compute ceremony hash
    ceremony_data = f"{ceremony_id}:{utc_now.isoformat()}:{','.join(agents)}"
    ceremony_hash = hashlib.sha256(ceremony_data.encode()).hexdigest()
    results["ceremony_hash"] = ceremony_hash

    return results


def print_sql_output(results: Dict) -> None:
    """Print SQL statements for database injection."""
    print()
    print("=" * 72)
    print("[STEP 1: PUBLIC REGISTRY INJECTION]")
    print("Execute this SQL in Supabase/PostgreSQL immediately:")
    print("=" * 72)
    print()
    print("BEGIN;")
    print()

    # Record ceremony in key_ceremonies table
    ceremony_sql = f"""
-- Record Key Ceremony
INSERT INTO fhq_meta.key_ceremonies (
    ceremony_id, ceremony_type, ceremony_name, ceremony_timestamp,
    agents_included, keys_generated, keys_registered,
    executed_by, execution_environment,
    ceremony_status, ceremony_hash, ceremony_notes
) VALUES (
    gen_random_uuid(),
    'IGNITION',
    '{results["ceremony_id"]}',
    '{results["timestamp"]}',
    ARRAY{list(results["agents"].keys())},
    {len(results["agents"])},
    {len(results["agents"])},
    'CODE',
    'LOCAL_SECURE_TERMINAL',
    'IN_PROGRESS',
    '{results["ceremony_hash"]}',
    'Phase D Identity Sovereignty - EXEC-DIR-004-KEYS'
);
"""
    print(ceremony_sql)

    for sql in results["sql_statements"]:
        print(sql)
        print()

    # Mark ceremony complete
    print(f"""
-- Mark ceremony complete
UPDATE fhq_meta.key_ceremonies
SET ceremony_status = 'COMPLETED',
    keys_registered = {len(results["agents"])},
    completed_at = NOW()
WHERE ceremony_name = '{results["ceremony_id"]}';
""")

    print("COMMIT;")
    print()


def print_env_output(results: Dict) -> None:
    """Print environment variable lines for .env file."""
    print()
    print("=" * 72)
    print("[STEP 2: PRIVATE VAULT STORAGE]")
    print("Append these lines to your local .env file.")
    print("!!! DO NOT COMMIT TO GIT !!!")
    print("=" * 72)
    print()

    print("# " + "=" * 68)
    print(f"# FjordHQ Fleet Private Keys - Generated {results['timestamp']}")
    print(f"# Ceremony ID: {results['ceremony_id']}")
    print("# " + "=" * 68)
    print()

    for env_line in results["env_lines"]:
        print(env_line)

    print()
    print("# " + "=" * 68)
    print("# END FLEET KEYS")
    print("# " + "=" * 68)
    print()


def print_summary(results: Dict) -> None:
    """Print ceremony summary with fingerprints."""
    print()
    print("=" * 72)
    print("[CEREMONY SUMMARY]")
    print("=" * 72)
    print()
    print(f"{'Agent':<8} {'Tier':<6} {'Fingerprint':<18} {'Status'}")
    print("-" * 50)

    for agent in FLEET_AGENTS:
        agent_id = agent["id"]
        if agent_id in results["agents"]:
            fingerprint = results["agents"][agent_id]["fingerprint"]
            print(f"{agent_id:<8} Tier-{agent['tier']:<4} {fingerprint:<18} GENERATED")

    print("-" * 50)
    print(f"Total Keys Generated: {len(results['agents'])}")
    print(f"Ceremony Hash: {results['ceremony_hash'][:32]}...")
    print()
    print("=" * 72)
    print("[NEXT STEPS]")
    print("=" * 72)
    print("1. Execute SQL in Supabase (public keys -> fhq_meta.agent_keys)")
    print("2. Update .env file (private keys -> local vault)")
    print("3. Run VEGA attestation:")
    print("   python tools/security/vega_core.py verify agent_keys --strict")
    print("   python tools/security/vega_core.py snapshot_keys --canonical --reason IGNITION_PHASE_D")
    print("   python tools/security/vega_core.py attest identity_state --sign")
    print("=" * 72)


def main():
    """Main entry point for key ceremony."""
    parser = argparse.ArgumentParser(
        description="FjordHQ Fleet Key Generation (SOP-008)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate keys for all 11 agents
  python generate_fleet_keys_hardened.py

  # Dry run (no sensitive output)
  python generate_fleet_keys_hardened.py --dry-run

  # Generate for specific agents only
  python generate_fleet_keys_hardened.py --agents VEGA LARS CODE

  # Output SQL only (for piping to file)
  python generate_fleet_keys_hardened.py --sql-only > keys.sql

Security Notes:
  - Run only on LOCAL SECURE TERMINAL
  - Never run in cloud shells or CI/CD pipelines
  - Private keys are printed to stdout ONCE and never stored
  - After ceremony, immediately secure .env file
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate keys but redact private keys from output"
    )
    parser.add_argument(
        "--agents",
        nargs="+",
        default=AGENTS,
        help="Specific agents to generate keys for (default: all 11)"
    )
    parser.add_argument(
        "--sql-only",
        action="store_true",
        help="Output only SQL statements (for piping)"
    )
    parser.add_argument(
        "--env-only",
        action="store_true",
        help="Output only .env lines (for piping)"
    )
    parser.add_argument(
        "--ceremony-id",
        type=str,
        default=None,
        help="Custom ceremony ID (default: auto-generated)"
    )

    args = parser.parse_args()

    # Security warning
    if not args.dry_run and not args.sql_only and not args.env_only:
        print()
        print("!" * 72)
        print("!!! HIGH-SECURITY OPERATION !!!")
        print("!" * 72)
        print()
        print("This script will generate REAL Ed25519 private keys.")
        print("Private keys will be printed to stdout ONCE and never stored.")
        print()
        print("REQUIREMENTS:")
        print("  1. Local Secure Terminal (no cloud shells)")
        print("  2. No screen recording or logging enabled")
        print("  3. Immediate secure storage of .env after ceremony")
        print()

        confirm = input("Type 'IGNITION' to proceed: ")
        if confirm != "IGNITION":
            print("Ceremony aborted.")
            sys.exit(1)

    # Generate keys
    results = generate_fleet_keys(
        agents=args.agents,
        ceremony_id=args.ceremony_id,
        dry_run=args.dry_run
    )

    # Output based on flags
    if args.sql_only:
        print("BEGIN;")
        for sql in results["sql_statements"]:
            print(sql)
        print("COMMIT;")
    elif args.env_only:
        for env_line in results["env_lines"]:
            print(env_line)
    else:
        print_sql_output(results)
        print_env_output(results)
        print_summary(results)


if __name__ == "__main__":
    main()
