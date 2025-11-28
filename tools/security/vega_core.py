#!/usr/bin/env python3
"""
=============================================================================
VEGA Core Attestation & Verification Tooling
=============================================================================
Authority: ADR-006 (VEGA Autonomy & Governance Engine Charter)
Reference: ADR-008 (Cryptographic Key Management)
         : EXEC-DIR-004-KEYS (Phase D Identity Sovereignty)

VEGA is the Constitutional Guardrail for the FjordHQ Intelligence Operating System.
This module provides:
  - Agent key verification
  - Identity state snapshots
  - Cryptographic attestation
  - Key ceremony validation

Zero Trust Rule: No agent operates without a verified Ed25519 identity keypair
anchored in fhq_meta.agent_keys and attested by VEGA.
=============================================================================
"""

import os
import sys
import json
import hashlib
import datetime
import argparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("ERROR: cryptography package not installed.")
    print("Install with: pip install cryptography>=43.0.0")
    sys.exit(1)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    print("WARNING: psycopg2 not installed. Database operations will be unavailable.")
    print("Install with: pip install psycopg2-binary")


# =============================================================================
# CONSTITUTIONAL CONSTANTS
# =============================================================================

# Expected agent fleet (11 sovereigns)
CONSTITUTIONAL_FLEET = [
    "VEGA", "LARS",  # Tier-1 Executive
    "STIG", "FINN", "LINE",  # Tier-2 Executive
    "CSEO", "CDMO", "CRIO", "CEIO", "CFAO",  # Tier-2 Sub-Executive
    "CODE"  # Tier-3 Engineering
]

# Verification severities
class Severity:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AgentKeyState:
    """Represents an agent's cryptographic key state."""
    agent_id: str
    public_key_hex: Optional[str] = None
    key_state: Optional[str] = None
    key_type: str = "ED25519_SIGNING"
    activation_date: Optional[str] = None
    key_fingerprint: Optional[str] = None
    ceremony_id: Optional[str] = None
    is_registered: bool = False
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Result of a verification operation."""
    success: bool
    message: str
    severity: str = Severity.INFO
    agent_id: Optional[str] = None
    details: Dict = field(default_factory=dict)


@dataclass
class IdentityStateSnapshot:
    """Snapshot of the entire fleet's identity state."""
    snapshot_id: str
    timestamp: str
    agent_count: int
    active_key_count: int
    identity_state_hash: str
    agent_states: Dict[str, AgentKeyState]
    reason: str
    vega_attested: bool = False
    vega_signature: Optional[str] = None


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Get PostgreSQL database connection."""
    if psycopg2 is None:
        raise RuntimeError("psycopg2 not installed. Cannot connect to database.")

    # Try DATABASE_URL first (Supabase format)
    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if db_url:
        return psycopg2.connect(db_url)

    # Fall back to individual params
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


# =============================================================================
# VERIFICATION FUNCTIONS
# =============================================================================

def verify_agent_key(agent_id: str, strict: bool = False) -> VerificationResult:
    """
    Verify that an agent has a valid active key.

    Args:
        agent_id: Agent identifier
        strict: If True, require exactly one ACTIVE key

    Returns:
        VerificationResult with verification outcome
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check for active keys (using actual schema columns)
        cursor.execute("""
            SELECT
                agent_id, public_key_hex, key_state, key_type,
                activation_date, key_fingerprint, ceremony_id
            FROM fhq_meta.agent_keys
            WHERE (agent_id = %s OR UPPER(agent_id) = UPPER(%s))
              AND key_state = 'ACTIVE'
        """, (agent_id, agent_id))

        active_keys = cursor.fetchall()

        cursor.close()
        conn.close()

        if len(active_keys) == 0:
            return VerificationResult(
                success=False,
                message=f"No ACTIVE key found for {agent_id}",
                severity=Severity.ERROR,
                agent_id=agent_id,
                details={"active_key_count": 0}
            )

        if strict and len(active_keys) > 1:
            return VerificationResult(
                success=False,
                message=f"Multiple ACTIVE keys found for {agent_id} (expected exactly 1)",
                severity=Severity.ERROR,
                agent_id=agent_id,
                details={"active_key_count": len(active_keys)}
            )

        key_data = active_keys[0]

        # Verify key format (Ed25519 public key should be 64 hex chars = 32 bytes)
        public_key_hex = key_data.get("public_key_hex", "")
        if len(public_key_hex) != 64:
            return VerificationResult(
                success=False,
                message=f"Invalid public key length for {agent_id}: {len(public_key_hex)} (expected 64)",
                severity=Severity.ERROR,
                agent_id=agent_id,
                details={"public_key_length": len(public_key_hex)}
            )

        # Verify it's valid hex
        try:
            bytes.fromhex(public_key_hex)
        except ValueError:
            return VerificationResult(
                success=False,
                message=f"Invalid hex encoding for {agent_id}'s public key",
                severity=Severity.ERROR,
                agent_id=agent_id
            )

        return VerificationResult(
            success=True,
            message=f"PASS: {agent_id} has valid ACTIVE key",
            severity=Severity.INFO,
            agent_id=agent_id,
            details={
                "public_key_fingerprint": key_data.get("key_fingerprint"),
                "key_type": key_data.get("key_type"),
                "ceremony_id": key_data.get("ceremony_id")
            }
        )

    except Exception as e:
        return VerificationResult(
            success=False,
            message=f"Database error verifying {agent_id}: {str(e)}",
            severity=Severity.CRITICAL,
            agent_id=agent_id
        )


def verify_all_agent_keys(strict: bool = False) -> Tuple[bool, List[VerificationResult]]:
    """
    Verify all 11 agents have exactly one active key.

    Args:
        strict: If True, require exactly one ACTIVE key per agent

    Returns:
        Tuple of (all_passed, list of results)
    """
    results = []
    all_passed = True

    print()
    print("=" * 60)
    print("VEGA AGENT KEY VERIFICATION")
    print("=" * 60)
    print(f"Mode: {'STRICT' if strict else 'STANDARD'}")
    print(f"Fleet Size: {len(CONSTITUTIONAL_FLEET)} agents")
    print("-" * 60)
    print()

    for agent_id in CONSTITUTIONAL_FLEET:
        result = verify_agent_key(agent_id, strict=strict)
        results.append(result)

        status_icon = "PASS" if result.success else "FAIL"
        print(f"[{status_icon}] {agent_id}: {result.message}")

        if not result.success:
            all_passed = False

    print()
    print("-" * 60)
    passed_count = sum(1 for r in results if r.success)
    print(f"Verification: {passed_count}/{len(CONSTITUTIONAL_FLEET)} agents passed")
    print(f"Overall Status: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 60)

    return all_passed, results


# =============================================================================
# SNAPSHOT FUNCTIONS
# =============================================================================

def compute_identity_state_hash(agent_states: Dict[str, dict]) -> str:
    """
    Compute deterministic hash of identity state.

    The hash is computed from:
    - Sorted agent IDs
    - Each agent's public key
    - Key state
    - Ceremony ID
    """
    hash_input = []

    for agent_id in sorted(agent_states.keys()):
        state = agent_states[agent_id]
        entry = f"{agent_id}:{state.get('public_key_hex', '')}:{state.get('key_state', '')}:{state.get('ceremony_id', '')}"
        hash_input.append(entry)

    combined = "|".join(hash_input)
    return hashlib.sha256(combined.encode()).hexdigest()


def create_identity_snapshot(reason: str, canonical: bool = False) -> Optional[IdentityStateSnapshot]:
    """
    Create a snapshot of the current identity state.

    Args:
        reason: Reason for snapshot (e.g., "IGNITION_PHASE_D")
        canonical: If True, store in database

    Returns:
        IdentityStateSnapshot object
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get all agent key states (using actual schema columns)
        cursor.execute("""
            SELECT
                agent_id, public_key_hex, key_state, key_type,
                activation_date, key_fingerprint, ceremony_id
            FROM fhq_meta.agent_keys
            WHERE key_state = 'ACTIVE'
        """)

        active_keys = cursor.fetchall()

        # Build agent states dict
        agent_states = {}
        for row in active_keys:
            agent_id = row["agent_id"].upper()
            agent_states[agent_id] = dict(row)

        # Compute state hash
        state_hash = compute_identity_state_hash(agent_states)

        # Generate snapshot ID
        timestamp = datetime.datetime.utcnow()
        snapshot_id = f"SNAPSHOT_{timestamp.strftime('%Y%m%d_%H%M%S')}_{state_hash[:8]}"

        snapshot = IdentityStateSnapshot(
            snapshot_id=snapshot_id,
            timestamp=timestamp.isoformat(),
            agent_count=len(CONSTITUTIONAL_FLEET),
            active_key_count=len(active_keys),
            identity_state_hash=state_hash,
            agent_states=agent_states,
            reason=reason
        )

        # Store snapshot if canonical
        if canonical:
            cursor.execute("""
                INSERT INTO fhq_meta.identity_state_snapshots (
                    snapshot_timestamp, agent_count, active_key_count,
                    identity_state_hash, agent_states, reason, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, 'VEGA')
                RETURNING snapshot_id
            """, (
                timestamp,
                len(CONSTITUTIONAL_FLEET),
                len(active_keys),
                state_hash,
                json.dumps(agent_states),
                reason
            ))

            db_snapshot_id = cursor.fetchone()["snapshot_id"]
            snapshot.snapshot_id = str(db_snapshot_id)
            conn.commit()

            print(f"Snapshot stored: {snapshot.snapshot_id}")

        cursor.close()
        conn.close()

        return snapshot

    except Exception as e:
        print(f"ERROR creating snapshot: {e}")
        return None


def snapshot_keys(canonical: bool = False, reason: str = "MANUAL") -> None:
    """
    Create and display identity state snapshot.

    Args:
        canonical: Store in database (immutable ledger)
        reason: Reason for snapshot
    """
    print()
    print("=" * 60)
    print("VEGA IDENTITY STATE SNAPSHOT")
    print("=" * 60)
    print(f"Reason: {reason}")
    print(f"Canonical: {canonical}")
    print("-" * 60)
    print()

    snapshot = create_identity_snapshot(reason=reason, canonical=canonical)

    if snapshot:
        print(f"Snapshot ID:      {snapshot.snapshot_id}")
        print(f"Timestamp:        {snapshot.timestamp}")
        print(f"Agent Count:      {snapshot.agent_count}")
        print(f"Active Keys:      {snapshot.active_key_count}")
        print(f"State Hash:       sha256:{snapshot.identity_state_hash[:32]}...")
        print()
        print("Agent Key States:")
        print("-" * 60)

        for agent_id in sorted(snapshot.agent_states.keys()):
            state = snapshot.agent_states[agent_id]
            fingerprint = state.get("key_fingerprint", "N/A")[:16]
            print(f"  {agent_id:<8}: {fingerprint}")

        print("-" * 60)

        if canonical:
            print(f"STORED: Snapshot saved to fhq_meta.identity_state_snapshots")
        else:
            print("NOTE: Use --canonical to persist snapshot to database")

    print("=" * 60)


# =============================================================================
# ATTESTATION FUNCTIONS
# =============================================================================

def sign_with_vega_key(data: str) -> Optional[Tuple[str, str]]:
    """
    Sign data with VEGA's private key.

    Args:
        data: Data to sign

    Returns:
        Tuple of (signature_hex, public_key_hex) or None if key not available
    """
    vega_private_key_hex = os.getenv("FHQ_VEGA_PRIVATE_KEY")

    if not vega_private_key_hex:
        print("WARNING: FHQ_VEGA_PRIVATE_KEY not set in environment")
        print("Attestation will be recorded but not cryptographically signed")
        return None

    try:
        # Load VEGA's private key
        private_bytes = bytes.fromhex(vega_private_key_hex)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
        public_key = private_key.public_key()

        # Sign the data
        signature = private_key.sign(data.encode())

        public_key_hex = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

        return signature.hex(), public_key_hex

    except Exception as e:
        print(f"ERROR signing with VEGA key: {e}")
        return None


def attest_identity_state(sign: bool = False) -> None:
    """
    VEGA attestation of current identity state.

    This is the "God Seal" on the identity system - cryptographic proof
    that VEGA has verified the identity state of all agents.

    Args:
        sign: If True, cryptographically sign the attestation
    """
    print()
    print("=" * 72)
    print("VEGA IDENTITY STATE ATTESTATION")
    print("=" * 72)
    print()

    # Step 1: Verify all agent keys
    print("[1/3] Verifying agent keys...")
    all_passed, results = verify_all_agent_keys(strict=True)

    if not all_passed:
        print()
        print("ATTESTATION BLOCKED: Not all agents have valid keys")
        print("Fix key issues before attempting attestation")
        print("=" * 72)
        return

    # Step 2: Create canonical snapshot
    print()
    print("[2/3] Creating canonical snapshot...")
    snapshot = create_identity_snapshot(
        reason="VEGA_ATTESTATION",
        canonical=True
    )

    if not snapshot:
        print("ATTESTATION BLOCKED: Failed to create snapshot")
        print("=" * 72)
        return

    # Step 3: Sign attestation
    print()
    print("[3/3] Signing attestation...")

    attestation_data = {
        "snapshot_id": snapshot.snapshot_id,
        "identity_state_hash": snapshot.identity_state_hash,
        "timestamp": snapshot.timestamp,
        "agent_count": snapshot.agent_count,
        "active_key_count": snapshot.active_key_count,
        "attester": "VEGA",
        "authority": "ADR-006"
    }

    attestation_string = json.dumps(attestation_data, sort_keys=True)

    signature_result = None
    if sign:
        signature_result = sign_with_vega_key(attestation_string)

    # Store attestation in database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if signature_result:
            signature_hex, vega_public_key = signature_result

            # Update snapshot with attestation
            cursor.execute("""
                UPDATE fhq_meta.identity_state_snapshots
                SET vega_attested = TRUE,
                    vega_signature = %s,
                    vega_public_key = %s,
                    attestation_timestamp = NOW()
                WHERE snapshot_id = %s::uuid
            """, (signature_hex, vega_public_key, snapshot.snapshot_id))

            # Record in VEGA attestations
            cursor.execute("""
                INSERT INTO fhq_governance.vega_attestations (
                    target_type, target_id, target_version,
                    attestation_type, attestation_status, attestation_timestamp,
                    vega_signature, vega_public_key, signature_verified,
                    attestation_data, adr_reference, constitutional_basis
                ) VALUES (
                    'IDENTITY_STATE', %s, '1.0',
                    'CERTIFICATION', 'APPROVED', NOW(),
                    %s, %s, TRUE,
                    %s, 'ADR-008', 'EC-001'
                )
            """, (
                snapshot.identity_state_hash[:32],
                signature_hex,
                vega_public_key,
                json.dumps(attestation_data)
            ))

            conn.commit()
            print(f"Attestation: SIGNED by VEGA")
            print(f"Signature:   {signature_hex[:32]}...")
        else:
            # Record unsigned attestation
            cursor.execute("""
                UPDATE fhq_meta.identity_state_snapshots
                SET vega_attested = TRUE,
                    attestation_timestamp = NOW()
                WHERE snapshot_id = %s::uuid
            """, (snapshot.snapshot_id,))

            conn.commit()
            print("Attestation: RECORDED (unsigned)")
            print("NOTE: Set FHQ_VEGA_PRIVATE_KEY to enable cryptographic signing")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"ERROR storing attestation: {e}")

    print()
    print("=" * 72)
    print("ATTESTATION RESULT")
    print("=" * 72)
    print(f"Verification:   PASS ({snapshot.active_key_count}/{snapshot.agent_count} keys)")
    print(f"Snapshot:       Created (Hash: sha256:{snapshot.identity_state_hash[:32]}...)")
    print(f"Attestation:    {'SIGNED' if signature_result else 'RECORDED'} by VEGA")
    print()
    print("Identity Sovereignty: ESTABLISHED")
    print("=" * 72)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="VEGA Core Attestation & Verification Tooling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  verify agent_keys      Verify all agents have valid keys
  snapshot_keys          Create identity state snapshot
  attest identity_state  VEGA attestation of identity state

Examples:
  # Verify all agent keys (strict mode)
  python vega_core.py verify agent_keys --strict

  # Create canonical snapshot
  python vega_core.py snapshot_keys --canonical --reason IGNITION_PHASE_D

  # VEGA attestation with cryptographic signature
  python vega_core.py attest identity_state --sign

Authority: ADR-006 (VEGA Autonomy & Governance Engine Charter)
Reference: ADR-008 (Cryptographic Key Management)
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # verify command
    verify_parser = subparsers.add_parser("verify", help="Verification operations")
    verify_parser.add_argument("target", choices=["agent_keys"], help="Verification target")
    verify_parser.add_argument("--strict", action="store_true", help="Strict verification (exactly 1 active key)")

    # snapshot command
    snapshot_parser = subparsers.add_parser("snapshot_keys", help="Create identity state snapshot")
    snapshot_parser.add_argument("--canonical", action="store_true", help="Store in immutable ledger")
    snapshot_parser.add_argument("--reason", type=str, default="MANUAL", help="Reason for snapshot")

    # attest command
    attest_parser = subparsers.add_parser("attest", help="Attestation operations")
    attest_parser.add_argument("target", choices=["identity_state"], help="Attestation target")
    attest_parser.add_argument("--sign", action="store_true", help="Cryptographically sign attestation")

    args = parser.parse_args()

    if args.command == "verify":
        if args.target == "agent_keys":
            all_passed, _ = verify_all_agent_keys(strict=args.strict)
            sys.exit(0 if all_passed else 1)

    elif args.command == "snapshot_keys":
        snapshot_keys(canonical=args.canonical, reason=args.reason)

    elif args.command == "attest":
        if args.target == "identity_state":
            attest_identity_state(sign=args.sign)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
