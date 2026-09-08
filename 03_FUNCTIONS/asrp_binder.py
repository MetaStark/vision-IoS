#!/usr/bin/env python3
"""
ASRP BINDER - Shared Utility for Agent State Reliability Protocol
=================================================================
CEO Directive: CEO-DIR-2026-LEARNING-MEMORY-ADMISSION-041-060
ADR: ADR-018 (Agent State Reliability Protocol)
Classification: CRITICAL - Constitutional Infrastructure

Extracted from court_proof_enforcer_v2.py to provide reusable ASRP
binding for all MemoryOS, Admission Gate, and Invariant Core modules.

Every artifact in the Memory/Learning/Admission system MUST embed:
  - state_snapshot_hash (SHA-256 of current system state)
  - state_timestamp (UTC ISO-8601)
  - agent_id (producing agent)

Artifacts lacking ASRP binding are INVALID and must fail closed.

Author: STIG (CTO)
Date: 2026-02-11
Contract: EC-003_2026_PRODUCTION
"""

import hashlib
import json
import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("asrp_binder")

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

VALID_AGENTS = {'FINN', 'STIG', 'LINE', 'LARS', 'VEGA', 'CEIO', 'CDMO', 'CRIO', 'CODE'}


class ASRPBindingError(Exception):
    """Raised when ASRP binding requirements are not met. FAIL-CLOSED."""
    pass


class AsrpBinder:
    """
    ADR-018: Agent State Reliability Protocol binder.

    Provides cryptographic binding of system state to artifacts,
    ensuring every memory/learning/admission artifact is traceable
    to a specific system state at creation time.
    """

    def __init__(self, conn=None):
        """Initialize with optional database connection."""
        self._conn = conn
        self._owns_conn = False

    @property
    def conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**DB_CONFIG)
            self._owns_conn = True
        return self._conn

    def close(self):
        if self._owns_conn and self._conn and not self._conn.closed:
            self._conn.close()

    def compute_hash(self, data: Any) -> str:
        """Compute SHA-256 hash of data. Deterministic serialization."""
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def get_state_snapshot(self) -> Dict:
        """
        Get current system state snapshot for ASRP binding.
        Queries execution_state, regime_state, data_freshness, and DEFCON.

        Returns dict with state_snapshot_hash and all state components.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Execution state
            cur.execute("""
                SELECT cognitive_fasting, fasting_reason, revalidation_required
                FROM fhq_governance.execution_state
                ORDER BY state_id DESC
                LIMIT 1
            """)
            exec_state = cur.fetchone() or {}

            # Regime state
            cur.execute("""
                SELECT policy_regime, policy_confidence, defcon_level, policy_timestamp
                FROM fhq_perception.sovereign_policy_state
                ORDER BY policy_timestamp DESC
                LIMIT 1
            """)
            regime_state = cur.fetchone() or {}

            # Data freshness
            cur.execute("""
                SELECT
                    MAX(timestamp) as latest_price,
                    EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) / 3600 as staleness_hours
                FROM fhq_market.prices
                WHERE timestamp > NOW() - INTERVAL '48 hours'
            """)
            freshness = cur.fetchone() or {}

            # DEFCON level
            cur.execute("""
                SELECT defcon_level, triggered_by, trigger_reason
                FROM fhq_governance.defcon_state
                WHERE is_current = true
                LIMIT 1
            """)
            defcon = cur.fetchone() or {}

        timestamp = datetime.now(timezone.utc)
        state_snapshot = {
            'snapshot_timestamp': timestamp.isoformat(),
            'execution_state': {
                'cognitive_fasting': exec_state.get('cognitive_fasting', False),
                'fasting_reason': exec_state.get('fasting_reason'),
                'revalidation_required': exec_state.get('revalidation_required', False)
            },
            'regime_state': {
                'policy_regime': regime_state.get('policy_regime'),
                'policy_confidence': float(regime_state.get('policy_confidence', 0)),
                'defcon_level': defcon.get('defcon_level'),
                'policy_timestamp': (
                    regime_state['policy_timestamp'].isoformat()
                    if regime_state.get('policy_timestamp') else None
                )
            },
            'data_freshness': {
                'latest_price': (
                    freshness['latest_price'].isoformat()
                    if freshness.get('latest_price') else None
                ),
                'staleness_hours': float(freshness.get('staleness_hours', 999))
            }
        }

        state_hash = self.compute_hash(state_snapshot)
        state_snapshot['state_snapshot_hash'] = state_hash

        return state_snapshot

    def bind_artifact(self, agent_id: str, artifact_data: Optional[Dict] = None) -> Dict:
        """
        Create an ASRP binding for an artifact.

        Returns dict with:
          - state_snapshot_hash: SHA-256 of current system state
          - state_timestamp: UTC ISO-8601 timestamp
          - agent_id: producing agent

        Raises ASRPBindingError if agent_id is invalid.
        """
        if agent_id not in VALID_AGENTS:
            raise ASRPBindingError(
                f"Invalid agent_id '{agent_id}'. Must be one of: {VALID_AGENTS}"
            )

        snapshot = self.get_state_snapshot()

        binding = {
            'state_snapshot_hash': snapshot['state_snapshot_hash'],
            'state_timestamp': snapshot['snapshot_timestamp'],
            'agent_id': agent_id,
        }

        if artifact_data:
            binding['artifact_hash'] = self.compute_hash(artifact_data)

        return binding

    def verify_binding(self, binding: Dict) -> Dict:
        """
        Verify an ASRP binding is structurally valid.

        Checks:
          1. Required fields present (state_snapshot_hash, state_timestamp, agent_id)
          2. Agent ID is valid
          3. Hash format is valid (64-char hex)

        Returns dict with 'valid' bool and 'errors' list.
        """
        errors = []

        required_fields = ['state_snapshot_hash', 'state_timestamp', 'agent_id']
        for field in required_fields:
            if field not in binding or not binding[field]:
                errors.append(f"Missing required ASRP field: {field}")

        if binding.get('agent_id') and binding['agent_id'] not in VALID_AGENTS:
            errors.append(f"Invalid agent_id: {binding['agent_id']}")

        hash_val = binding.get('state_snapshot_hash', '')
        if hash_val and (len(hash_val) != 64 or not all(c in '0123456789abcdef' for c in hash_val)):
            errors.append(f"Invalid hash format: expected 64-char hex, got {len(hash_val)} chars")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'checked_at': datetime.now(timezone.utc).isoformat()
        }

    def log_state(self, agent_id: str, operation_type: str, context: Optional[Dict] = None):
        """
        Log an ASRP state entry to fhq_governance.asrp_state_log.
        """
        snapshot = self.get_state_snapshot()
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.asrp_state_log
                    (log_id, agent_id, pre_state_hash, post_state_hash,
                     expected_state_hash, signature_verified, state_mismatch,
                     operation_type, operation_context, recorded_at, created_at)
                VALUES
                    (gen_random_uuid(), %s, %s, %s, %s, true, false, %s, %s, NOW(), NOW())
            """, (
                agent_id,
                snapshot['state_snapshot_hash'],
                snapshot['state_snapshot_hash'],
                snapshot['state_snapshot_hash'],
                operation_type,
                json.dumps(context or {}, default=str)
            ))
            self.conn.commit()
        logger.info(f"ASRP state logged: agent={agent_id}, op={operation_type}, hash={snapshot['state_snapshot_hash'][:16]}...")
        return snapshot


def get_db_connection():
    """Get a database connection using standard config."""
    return psycopg2.connect(**DB_CONFIG)


def register_heartbeat(conn, daemon_name: str, interval_minutes: int = 60,
                       is_critical: bool = False, ceo_directive_ref: str = None):
    """Register daemon heartbeat in fhq_monitoring.daemon_health."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_monitoring.daemon_health
                (daemon_name, status, last_heartbeat, expected_interval_minutes,
                 lifecycle_status, is_critical, ceo_directive_ref, metadata)
            VALUES
                (%s, 'HEALTHY', NOW(), %s, 'ACTIVE', %s, %s, '{}'::jsonb)
            ON CONFLICT (daemon_name) DO UPDATE SET
                status = 'HEALTHY',
                last_heartbeat = NOW(),
                expected_interval_minutes = EXCLUDED.expected_interval_minutes,
                lifecycle_status = 'ACTIVE',
                is_critical = EXCLUDED.is_critical,
                ceo_directive_ref = EXCLUDED.ceo_directive_ref,
                updated_at = NOW()
        """, (daemon_name, interval_minutes, is_critical, ceo_directive_ref))
        conn.commit()


def write_evidence_file(evidence: Dict, filename: str):
    """Write evidence bundle to 03_FUNCTIONS/evidence/ directory."""
    evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
    os.makedirs(evidence_dir, exist_ok=True)
    filepath = os.path.join(evidence_dir, filename)
    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)
    logger.info(f"Evidence written: {filepath}")
    return filepath
