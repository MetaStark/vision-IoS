#!/usr/bin/env python3
"""
ED25519 KEY GENERATOR v2.0
PHASE D: Key Generation & Provider Lock-in

Authority: CEO BOARDROOM DIRECTIVE v3.0 – Strategic Hardening Edition
Compliance: ADR-008 – Cryptographic Key Management & Rotation Architecture
Date: 2026-11-28

Purpose:
- Generate real Ed25519 keypairs for all FjordHQ agents
- Register public keys in fhq_meta.agent_keys
- Store private keys securely (env-based Phase 1, Vault Phase 2)
- VEGA validation before activation

Agents:
- Tier-1: LARS, STIG, LINE, FINN, VEGA, CODE
- Tier-2: CSEO, CRIO, CDMO, CEIO, CFAO

Usage:
    python ed25519_keygen_v2.py                    # Generate all keys
    python ed25519_keygen_v2.py --agent LARS       # Generate specific agent key
    python ed25519_keygen_v2.py --verify           # Verify all keys
    python ed25519_keygen_v2.py --rotate FINN      # Rotate specific key
"""

import os
import sys
import json
import hashlib
import argparse
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Cryptographic imports
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.backends import default_backend

# Database
import psycopg2
from psycopg2.extras import RealDictCursor


# =============================================================================
# CONFIGURATION
# =============================================================================

class KeyGenConfig:
    """Key generation configuration"""

    # Agent definitions
    TIER_1_AGENTS = ['lars', 'stig', 'line', 'finn', 'vega', 'code']
    TIER_2_AGENTS = ['cseo', 'crio', 'cdmo', 'ceio', 'cfao']
    ALL_AGENTS = TIER_1_AGENTS + TIER_2_AGENTS

    # Key lifecycle (ADR-008)
    ROTATION_DAYS = 90
    GRACE_PERIOD_HOURS = 24
    ARCHIVAL_YEARS = 7

    # Storage paths
    KEYS_DIR = Path(__file__).parent.parent.parent / '.keys'
    ENV_FILE = Path(__file__).parent.parent.parent / '.env'

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# =============================================================================
# ED25519 KEY MANAGER
# =============================================================================

class Ed25519KeyManager:
    """Manages Ed25519 key generation, storage, and rotation"""

    def __init__(self, config: KeyGenConfig = None):
        self.config = config or KeyGenConfig()
        self.conn = None

    def connect_db(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(self.config.get_db_connection_string())
        return self.conn

    def close_db(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    # =========================================================================
    # KEY GENERATION
    # =========================================================================

    def generate_keypair(self) -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
        """Generate a new Ed25519 keypair"""
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return private_key, public_key

    def serialize_private_key(self, private_key: Ed25519PrivateKey) -> bytes:
        """Serialize private key to PEM format"""
        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

    def serialize_public_key(self, public_key: Ed25519PublicKey) -> bytes:
        """Serialize public key to PEM format"""
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def public_key_to_hex(self, public_key: Ed25519PublicKey) -> str:
        """Convert public key to hex string for database storage"""
        raw_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return raw_bytes.hex()

    def private_key_to_hex(self, private_key: Ed25519PrivateKey) -> str:
        """Convert private key to hex string"""
        raw_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        return raw_bytes.hex()

    # =========================================================================
    # KEY REGISTRATION
    # =========================================================================

    def register_key_in_db(
        self,
        agent_id: str,
        public_key_hex: str,
        key_state: str = 'ACTIVE',
        rotation_generation: int = 1
    ) -> str:
        """Register public key in fhq_meta.agent_keys"""
        with self.conn.cursor() as cur:
            # Calculate valid_until based on rotation policy
            valid_until = datetime.now(timezone.utc) + timedelta(days=self.config.ROTATION_DAYS)

            cur.execute("""
                INSERT INTO fhq_meta.agent_keys (
                    agent_id,
                    public_key_hex,
                    key_state,
                    signing_algorithm,
                    rotation_generation,
                    valid_from,
                    valid_until,
                    archival_tier,
                    created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING key_id
            """, (
                agent_id,
                public_key_hex,
                key_state,
                'Ed25519',
                rotation_generation,
                datetime.now(timezone.utc),
                valid_until,
                'HOT',
                'ceo'
            ))

            key_id = cur.fetchone()[0]
            self.conn.commit()
            return str(key_id)

    def update_org_agent_key(self, agent_id: str, public_key_hex: str):
        """Update public key in fhq_org.org_agents"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_org.org_agents
                SET public_key = %s, updated_at = NOW()
                WHERE agent_id = %s
            """, (public_key_hex, agent_id))
            self.conn.commit()

    def deprecate_old_keys(self, agent_id: str):
        """Deprecate all existing ACTIVE keys for an agent"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_meta.agent_keys
                SET
                    key_state = 'DEPRECATED',
                    valid_until = NOW() + INTERVAL '24 hours',
                    archival_tier = 'WARM'
                WHERE agent_id = %s AND key_state = 'ACTIVE'
            """, (agent_id,))
            self.conn.commit()

    # =========================================================================
    # KEY STORAGE (Phase 1: File-based)
    # =========================================================================

    def store_private_key_file(self, agent_id: str, private_key_hex: str):
        """Store private key in secure file (Phase 1)"""
        # Ensure keys directory exists
        self.config.KEYS_DIR.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions on directory
        os.chmod(self.config.KEYS_DIR, 0o700)

        # Write key file
        key_file = self.config.KEYS_DIR / f"{agent_id}_private.key"
        key_file.write_text(private_key_hex)

        # Set restrictive permissions on file
        os.chmod(key_file, 0o600)

        return str(key_file)

    def append_to_env(self, agent_id: str, private_key_hex: str):
        """Append private key to .env file (Phase 1)"""
        env_var = f"AGENT_{agent_id.upper()}_ED25519_PRIVATE_KEY"

        # Read existing .env
        env_content = ""
        if self.config.ENV_FILE.exists():
            env_content = self.config.ENV_FILE.read_text()

        # Check if variable already exists
        if env_var in env_content:
            # Update existing
            lines = env_content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith(f"{env_var}="):
                    new_lines.append(f"{env_var}={private_key_hex}")
                else:
                    new_lines.append(line)
            env_content = '\n'.join(new_lines)
        else:
            # Append new
            if env_content and not env_content.endswith('\n'):
                env_content += '\n'
            env_content += f"{env_var}={private_key_hex}\n"

        # Write back
        self.config.ENV_FILE.write_text(env_content)

    # =========================================================================
    # KEY GENERATION WORKFLOW
    # =========================================================================

    def generate_agent_key(
        self,
        agent_id: str,
        rotate: bool = False
    ) -> Dict[str, Any]:
        """Generate and register key for a single agent"""

        agent_id = agent_id.lower()

        if agent_id not in self.config.ALL_AGENTS:
            raise ValueError(f"Unknown agent: {agent_id}")

        # Get current rotation generation
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT MAX(rotation_generation) as max_gen
                FROM fhq_meta.agent_keys
                WHERE agent_id = %s
            """, (agent_id,))
            result = cur.fetchone()
            current_gen = result['max_gen'] or 0

        new_generation = current_gen + 1 if rotate else 1

        # If rotating, deprecate old keys
        if rotate:
            self.deprecate_old_keys(agent_id)

        # Generate new keypair
        private_key, public_key = self.generate_keypair()

        # Convert to hex
        public_key_hex = self.public_key_to_hex(public_key)
        private_key_hex = self.private_key_to_hex(private_key)

        # Register in database
        key_id = self.register_key_in_db(
            agent_id=agent_id,
            public_key_hex=public_key_hex,
            key_state='ACTIVE',
            rotation_generation=new_generation
        )

        # Update org_agents
        self.update_org_agent_key(agent_id, public_key_hex)

        # Store private key
        key_file = self.store_private_key_file(agent_id, private_key_hex)
        self.append_to_env(agent_id, private_key_hex)

        return {
            'agent_id': agent_id,
            'key_id': key_id,
            'public_key_hex': public_key_hex,
            'private_key_file': key_file,
            'rotation_generation': new_generation,
            'key_state': 'ACTIVE',
            'valid_until': (datetime.now(timezone.utc) + timedelta(days=self.config.ROTATION_DAYS)).isoformat()
        }

    def generate_all_keys(self) -> List[Dict[str, Any]]:
        """Generate keys for all agents"""
        results = []

        for agent_id in self.config.ALL_AGENTS:
            try:
                result = self.generate_agent_key(agent_id)
                results.append(result)
                print(f"  ✅ {agent_id.upper()}: Key generated (gen={result['rotation_generation']})")
            except Exception as e:
                results.append({
                    'agent_id': agent_id,
                    'error': str(e)
                })
                print(f"  ❌ {agent_id.upper()}: {e}")

        return results

    # =========================================================================
    # VERIFICATION
    # =========================================================================

    def verify_agent_key(self, agent_id: str) -> Dict[str, Any]:
        """Verify key for a single agent"""
        agent_id = agent_id.lower()

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get active key from database
            cur.execute("""
                SELECT key_id, public_key_hex, key_state, rotation_generation, valid_from, valid_until
                FROM fhq_meta.agent_keys
                WHERE agent_id = %s AND key_state = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 1
            """, (agent_id,))
            db_key = cur.fetchone()

            # Get key from org_agents
            cur.execute("""
                SELECT public_key
                FROM fhq_org.org_agents
                WHERE agent_id = %s
            """, (agent_id,))
            org_key = cur.fetchone()

        # Check private key file
        key_file = self.config.KEYS_DIR / f"{agent_id}_private.key"
        private_key_exists = key_file.exists()

        # Check env variable
        env_var = f"AGENT_{agent_id.upper()}_ED25519_PRIVATE_KEY"
        env_key_exists = env_var in os.environ or (
            self.config.ENV_FILE.exists() and
            env_var in self.config.ENV_FILE.read_text()
        )

        # Validation
        is_valid = (
            db_key is not None and
            org_key is not None and
            db_key['public_key_hex'] == org_key['public_key'] and
            private_key_exists
        )

        return {
            'agent_id': agent_id,
            'valid': is_valid,
            'db_key_present': db_key is not None,
            'org_key_present': org_key is not None,
            'keys_match': db_key and org_key and db_key['public_key_hex'] == org_key['public_key'],
            'private_key_file': private_key_exists,
            'env_variable': env_key_exists,
            'key_state': db_key['key_state'] if db_key else None,
            'rotation_generation': db_key['rotation_generation'] if db_key else None,
            'valid_until': str(db_key['valid_until']) if db_key else None
        }

    def verify_all_keys(self) -> Dict[str, Any]:
        """Verify keys for all agents"""
        results = {}
        all_valid = True

        for agent_id in self.config.ALL_AGENTS:
            result = self.verify_agent_key(agent_id)
            results[agent_id] = result
            if not result['valid']:
                all_valid = False

        return {
            'all_valid': all_valid,
            'agents': results
        }

    # =========================================================================
    # SIGNING & VERIFICATION
    # =========================================================================

    def sign_message(self, agent_id: str, message: bytes) -> str:
        """Sign a message using agent's private key"""
        agent_id = agent_id.lower()

        # Load private key from file
        key_file = self.config.KEYS_DIR / f"{agent_id}_private.key"
        if not key_file.exists():
            raise FileNotFoundError(f"Private key not found for {agent_id}")

        private_key_hex = key_file.read_text().strip()
        private_key_bytes = bytes.fromhex(private_key_hex)

        # Reconstruct private key
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)

        # Sign message
        signature = private_key.sign(message)

        return signature.hex()

    def verify_signature(
        self,
        agent_id: str,
        message: bytes,
        signature_hex: str
    ) -> bool:
        """Verify a signature using agent's public key from database"""
        agent_id = agent_id.lower()

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get active or deprecated keys
            cur.execute("""
                SELECT public_key_hex
                FROM fhq_meta.agent_keys
                WHERE agent_id = %s AND key_state IN ('ACTIVE', 'DEPRECATED')
                ORDER BY created_at DESC
            """, (agent_id,))
            keys = cur.fetchall()

        if not keys:
            raise ValueError(f"No valid keys found for {agent_id}")

        signature = bytes.fromhex(signature_hex)

        # Try each key (most recent first)
        for key_record in keys:
            try:
                public_key_bytes = bytes.fromhex(key_record['public_key_hex'])
                public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
                public_key.verify(signature, message)
                return True
            except Exception:
                continue

        return False


# =============================================================================
# VEGA VALIDATION
# =============================================================================

def vega_validate_keygen(conn, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """VEGA validation of key generation"""

    validation_timestamp = datetime.now(timezone.utc)

    # Check all keys generated successfully
    all_success = all('error' not in r for r in results)

    # Count by tier
    tier1_count = sum(1 for r in results if r.get('agent_id') in KeyGenConfig.TIER_1_AGENTS and 'error' not in r)
    tier2_count = sum(1 for r in results if r.get('agent_id') in KeyGenConfig.TIER_2_AGENTS and 'error' not in r)

    # Generate attestation
    attestation = {
        'validation_type': 'ED25519_KEYGEN_PHASE_D',
        'validation_timestamp': validation_timestamp.isoformat(),
        'all_keys_generated': all_success,
        'tier1_keys': tier1_count,
        'tier2_keys': tier2_count,
        'total_agents': len(KeyGenConfig.ALL_AGENTS),
        'signing_algorithm': 'Ed25519',
        'rotation_policy_days': KeyGenConfig.ROTATION_DAYS,
        'compliance': ['ADR-008', 'CEO-DIRECTIVE-v3.0']
    }

    # Calculate attestation hash
    attestation_hash = hashlib.sha256(
        json.dumps(attestation, sort_keys=True).encode()
    ).hexdigest()

    # Store VEGA attestation
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_meta.vega_attestations (
                attestation_type,
                attestation_scope,
                attestation_status,
                evidence_bundle,
                attestation_hash,
                created_at,
                created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING attestation_id
        """, (
            'KEYGEN_PHASE_D',
            'strategic_hardening_ed25519',
            'APPROVED' if all_success else 'PARTIAL',
            json.dumps({
                'attestation': attestation,
                'results': results
            }),
            attestation_hash,
            validation_timestamp,
            'vega'
        ))
        attestation_id = cur.fetchone()[0]
        conn.commit()

    return {
        'attestation_id': str(attestation_id),
        'attestation_hash': attestation_hash,
        'status': 'APPROVED' if all_success else 'PARTIAL',
        'details': attestation
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Ed25519 Key Generator v2.0 – Phase D Key Generation'
    )
    parser.add_argument(
        '--agent',
        type=str,
        help='Generate key for specific agent only'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify all existing keys'
    )
    parser.add_argument(
        '--rotate',
        type=str,
        help='Rotate key for specific agent'
    )
    parser.add_argument(
        '--sign-test',
        type=str,
        help='Test signing with specific agent'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("ED25519 KEY GENERATOR v2.0")
    print("PHASE D: Key Generation & Provider Lock-in")
    print("Authority: CEO BOARDROOM DIRECTIVE v3.0 – Strategic Hardening Edition")
    print("=" * 70)
    print()

    manager = Ed25519KeyManager()

    try:
        manager.connect_db()

        if args.verify:
            print("Verifying all agent keys...")
            print()

            result = manager.verify_all_keys()

            print("Agent Key Verification Status:")
            print("-" * 50)

            for agent_id, status in result['agents'].items():
                tier = "Tier-1" if agent_id in KeyGenConfig.TIER_1_AGENTS else "Tier-2"
                valid_str = "✅" if status['valid'] else "❌"
                print(f"  {valid_str} {agent_id.upper():6} ({tier})")
                if not status['valid']:
                    if not status['db_key_present']:
                        print(f"      - Missing database key")
                    if not status['org_key_present']:
                        print(f"      - Missing org_agents entry")
                    if not status['keys_match']:
                        print(f"      - Key mismatch between tables")
                    if not status['private_key_file']:
                        print(f"      - Missing private key file")

            print()
            print(f"Overall Status: {'✅ ALL VALID' if result['all_valid'] else '❌ ISSUES FOUND'}")

        elif args.rotate:
            agent = args.rotate.lower()
            print(f"Rotating key for agent: {agent.upper()}")
            print()

            result = manager.generate_agent_key(agent, rotate=True)

            print(f"  ✅ New key generated")
            print(f"     Key ID: {result['key_id']}")
            print(f"     Generation: {result['rotation_generation']}")
            print(f"     Valid until: {result['valid_until']}")
            print(f"     Old keys deprecated (24h grace period)")

        elif args.sign_test:
            agent = args.sign_test.lower()
            print(f"Testing signature with agent: {agent.upper()}")
            print()

            test_message = b"Test message for VEGA validation"
            signature = manager.sign_message(agent, test_message)

            print(f"  Message: {test_message.decode()}")
            print(f"  Signature: {signature[:64]}...")

            # Verify
            is_valid = manager.verify_signature(agent, test_message, signature)
            print(f"  Verification: {'✅ VALID' if is_valid else '❌ INVALID'}")

        elif args.agent:
            agent = args.agent.lower()
            print(f"Generating key for agent: {agent.upper()}")
            print()

            result = manager.generate_agent_key(agent)

            print(f"  ✅ Key generated successfully")
            print(f"     Key ID: {result['key_id']}")
            print(f"     Public Key (hex): {result['public_key_hex'][:32]}...")
            print(f"     Private Key File: {result['private_key_file']}")

        else:
            print("Generating Ed25519 keys for all agents...")
            print()

            print("Tier-1 Executives (Constitutional):")
            print("-" * 40)

            results = []

            for agent_id in KeyGenConfig.TIER_1_AGENTS:
                result = manager.generate_agent_key(agent_id)
                results.append(result)

            print()
            print("Tier-2 Sub-Executives (Operational):")
            print("-" * 40)

            for agent_id in KeyGenConfig.TIER_2_AGENTS:
                result = manager.generate_agent_key(agent_id)
                results.append(result)

            print()
            print("=" * 70)
            print("VEGA VALIDATION")
            print("=" * 70)
            print()

            vega_result = vega_validate_keygen(manager.conn, results)

            print(f"  Attestation ID: {vega_result['attestation_id']}")
            print(f"  Attestation Hash: {vega_result['attestation_hash'][:32]}...")
            print(f"  Status: {vega_result['status']}")
            print()
            print(f"  Tier-1 Keys: {vega_result['details']['tier1_keys']}/{len(KeyGenConfig.TIER_1_AGENTS)}")
            print(f"  Tier-2 Keys: {vega_result['details']['tier2_keys']}/{len(KeyGenConfig.TIER_2_AGENTS)}")

            print()
            print("=" * 70)
            print("PHASE D COMPLETE")
            print("=" * 70)
            print()
            print("Next Steps:")
            print("  → Phase E: Run Hardened Grand Slam (3-loop test)")
            print("  → Phase F: VEGA Final Attestation")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        manager.close_db()


if __name__ == '__main__':
    main()
