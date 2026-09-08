"""
CEO-DIR-2026-FINN-019: Neural Bridge Attempt Logger

ADR-011 Fortress-compliant attempt logging with tamper-proof hash chain.

CEO Issues Addressed:
  #6: FK to g5_paper_trades
  #14: ADR-011 hash chain (hash_prev, hash_self)
  R6: chain_epoch_id for future rotation

Every trade attempt is logged with:
  - All gate outcomes (even if blocked early)
  - Hash chain linking to previous attempt
  - Evidence links (SitC, InForage, IKEA, causal)
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Genesis hash for chain start
GENESIS_HASH = "GENESIS"

# Default epoch for R6 chain rotation support
DEFAULT_EPOCH_ID = UUID("00000000-0000-0000-0000-000000000001")


@dataclass
class GateResult:
    """Result of a single gate check."""
    gate_name: str
    passed: bool
    reason: Optional[str] = None


@dataclass
class AttemptRecord:
    """
    Execution attempt record with ADR-011 Fortress hash chain.

    Every attempt is logged regardless of outcome:
    - EXECUTED: Trade completed successfully
    - BLOCKED: Gate blocked execution
    - ABORTED: Timeout or exception
    - EXPIRED: TTL expired
    - COST_ABORT: Cognition exceeded budget
    """
    attempt_id: UUID
    intent_draft_id: UUID
    needle_id: UUID
    decision_plan_id: Optional[UUID] = None

    # ADR-011 Fortress Hash Chain (CEO Issue #14)
    chain_epoch_id: UUID = field(default_factory=lambda: DEFAULT_EPOCH_ID)
    hash_prev: str = GENESIS_HASH
    hash_self: str = ""  # Computed at completion
    chain_sequence: int = 0

    # Gate progression (all gates logged even if blocked early)
    gate_exposure_passed: Optional[bool] = None
    gate_exposure_reason: Optional[str] = None
    gate_holiday_passed: Optional[bool] = None
    gate_holiday_reason: Optional[str] = None
    gate_btc_only_passed: Optional[bool] = None
    gate_btc_only_reason: Optional[str] = None
    gate_regime_stability_passed: Optional[bool] = None  # CEO Issue #16
    gate_regime_stability_reason: Optional[str] = None
    gate_sitc_passed: Optional[bool] = None
    gate_sitc_reason: Optional[str] = None
    gate_ikea_passed: Optional[bool] = None
    gate_ikea_reason: Optional[str] = None
    gate_inforage_passed: Optional[bool] = None
    gate_inforage_reason: Optional[str] = None
    gate_causal_passed: Optional[bool] = None
    gate_causal_reason: Optional[str] = None
    gate_fss_passed: Optional[bool] = None
    gate_fss_reason: Optional[str] = None
    gate_ttl_passed: Optional[bool] = None
    gate_ttl_reason: Optional[str] = None

    # Final outcome
    final_outcome: Optional[str] = None  # EXECUTED/BLOCKED/ABORTED/EXPIRED/COST_ABORT
    blocked_at_gate: Optional[str] = None
    block_reason: Optional[str] = None

    # Evidence links (mandatory for completed attempts)
    sitc_event_id: Optional[UUID] = None
    inforage_session_id: Optional[UUID] = None
    ikea_validation_id: Optional[UUID] = None
    causal_edge_refs: List[UUID] = field(default_factory=list)

    # Audit-only mode flag (R1)
    audit_only_mode: bool = False

    # Cognition metrics (CEO Issue #11)
    cognition_started_at: Optional[datetime] = None
    cognition_completed_at: Optional[datetime] = None
    cognition_duration_ms: Optional[int] = None

    # Timestamps
    attempt_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempt_completed_at: Optional[datetime] = None

    # Signature (matches DecisionPlan if sealed)
    signing_agent: Optional[str] = None
    signature: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for hashing and storage."""
        return {
            'attempt_id': str(self.attempt_id),
            'intent_draft_id': str(self.intent_draft_id),
            'needle_id': str(self.needle_id),
            'decision_plan_id': str(self.decision_plan_id) if self.decision_plan_id else None,
            'chain_epoch_id': str(self.chain_epoch_id),
            'hash_prev': self.hash_prev,
            'chain_sequence': self.chain_sequence,
            'gate_exposure_passed': self.gate_exposure_passed,
            'gate_exposure_reason': self.gate_exposure_reason,
            'gate_holiday_passed': self.gate_holiday_passed,
            'gate_holiday_reason': self.gate_holiday_reason,
            'gate_btc_only_passed': self.gate_btc_only_passed,
            'gate_btc_only_reason': self.gate_btc_only_reason,
            'gate_regime_stability_passed': self.gate_regime_stability_passed,
            'gate_regime_stability_reason': self.gate_regime_stability_reason,
            'gate_sitc_passed': self.gate_sitc_passed,
            'gate_sitc_reason': self.gate_sitc_reason,
            'gate_ikea_passed': self.gate_ikea_passed,
            'gate_ikea_reason': self.gate_ikea_reason,
            'gate_inforage_passed': self.gate_inforage_passed,
            'gate_inforage_reason': self.gate_inforage_reason,
            'gate_causal_passed': self.gate_causal_passed,
            'gate_causal_reason': self.gate_causal_reason,
            'gate_fss_passed': self.gate_fss_passed,
            'gate_fss_reason': self.gate_fss_reason,
            'gate_ttl_passed': self.gate_ttl_passed,
            'gate_ttl_reason': self.gate_ttl_reason,
            'final_outcome': self.final_outcome,
            'blocked_at_gate': self.blocked_at_gate,
            'block_reason': self.block_reason,
            'sitc_event_id': str(self.sitc_event_id) if self.sitc_event_id else None,
            'inforage_session_id': str(self.inforage_session_id) if self.inforage_session_id else None,
            'ikea_validation_id': str(self.ikea_validation_id) if self.ikea_validation_id else None,
            'causal_edge_refs': [str(ref) for ref in self.causal_edge_refs],
            'audit_only_mode': self.audit_only_mode,
            'cognition_started_at': self.cognition_started_at.isoformat() if self.cognition_started_at else None,
            'cognition_completed_at': self.cognition_completed_at.isoformat() if self.cognition_completed_at else None,
            'cognition_duration_ms': self.cognition_duration_ms,
            'attempt_started_at': self.attempt_started_at.isoformat(),
            'attempt_completed_at': self.attempt_completed_at.isoformat() if self.attempt_completed_at else None,
            'signing_agent': self.signing_agent,
            'signature': self.signature
        }


class AttemptLogger:
    """
    ADR-011 Fortress-compliant attempt logger with hash chain.

    Ensures tamper-proof audit trail for all execution attempts.
    """

    def __init__(self, db_conn):
        self.conn = db_conn
        self._current_sequence = None
        self._last_hash = None

    def start_attempt(
        self,
        needle_id: UUID,
        intent_draft_id: UUID,
        audit_only: bool = False
    ) -> AttemptRecord:
        """
        Create attempt record BEFORE any gate.

        ADR-011: Links to previous attempt via hash_prev.
        R1: Set audit_only_mode for hard-blocked attempts.
        """
        # Get previous hash and next sequence
        prev_hash = self._get_last_hash()
        sequence = self._get_next_sequence()

        attempt = AttemptRecord(
            attempt_id=uuid4(),
            intent_draft_id=intent_draft_id,
            needle_id=needle_id,
            chain_epoch_id=DEFAULT_EPOCH_ID,
            hash_prev=prev_hash,
            chain_sequence=sequence,
            audit_only_mode=audit_only,
            attempt_started_at=datetime.now(timezone.utc)
        )

        logger.info(f"Attempt started: {attempt.attempt_id} (seq={sequence})")
        return attempt

    def log_gate_result(
        self,
        attempt: AttemptRecord,
        gate: str,
        passed: bool,
        reason: Optional[str] = None
    ):
        """
        Log gate result to attempt (even if blocked).

        All gates are logged for complete audit trail.
        """
        gate_lower = gate.lower().replace('-', '_')

        # Map gate names to attributes
        gate_map = {
            'exposure': ('gate_exposure_passed', 'gate_exposure_reason'),
            'holiday': ('gate_holiday_passed', 'gate_holiday_reason'),
            'btc_only': ('gate_btc_only_passed', 'gate_btc_only_reason'),
            'regime_stability': ('gate_regime_stability_passed', 'gate_regime_stability_reason'),
            'sitc': ('gate_sitc_passed', 'gate_sitc_reason'),
            'ikea': ('gate_ikea_passed', 'gate_ikea_reason'),
            'inforage': ('gate_inforage_passed', 'gate_inforage_reason'),
            'causal': ('gate_causal_passed', 'gate_causal_reason'),
            'fss': ('gate_fss_passed', 'gate_fss_reason'),
            'ttl': ('gate_ttl_passed', 'gate_ttl_reason'),
        }

        if gate_lower in gate_map:
            passed_attr, reason_attr = gate_map[gate_lower]
            setattr(attempt, passed_attr, passed)
            setattr(attempt, reason_attr, reason)

        log_level = logging.INFO if passed else logging.WARNING
        logger.log(log_level, f"Gate {gate}: {'PASSED' if passed else 'BLOCKED'} - {reason or 'OK'}")

    def log_cognition_start(self, attempt: AttemptRecord):
        """Mark cognition stack start time."""
        attempt.cognition_started_at = datetime.now(timezone.utc)

    def log_cognition_complete(self, attempt: AttemptRecord):
        """Mark cognition stack completion with duration."""
        attempt.cognition_completed_at = datetime.now(timezone.utc)
        if attempt.cognition_started_at:
            delta = attempt.cognition_completed_at - attempt.cognition_started_at
            attempt.cognition_duration_ms = int(delta.total_seconds() * 1000)

    def set_evidence_links(
        self,
        attempt: AttemptRecord,
        sitc_event_id: Optional[UUID] = None,
        inforage_session_id: Optional[UUID] = None,
        ikea_validation_id: Optional[UUID] = None,
        causal_edge_refs: Optional[List[UUID]] = None
    ):
        """Set evidence links for audit trail."""
        if sitc_event_id:
            attempt.sitc_event_id = sitc_event_id
        if inforage_session_id:
            attempt.inforage_session_id = inforage_session_id
        if ikea_validation_id:
            attempt.ikea_validation_id = ikea_validation_id
        if causal_edge_refs:
            attempt.causal_edge_refs = causal_edge_refs

    def complete_attempt(
        self,
        attempt: AttemptRecord,
        outcome: str,
        blocked_at_gate: Optional[str] = None,
        block_reason: Optional[str] = None,
        decision_plan_id: Optional[UUID] = None
    ) -> str:
        """
        Seal attempt with hash and persist.

        Returns: hash_self for chain verification
        """
        attempt.final_outcome = outcome
        attempt.blocked_at_gate = blocked_at_gate
        attempt.block_reason = block_reason
        attempt.decision_plan_id = decision_plan_id
        attempt.attempt_completed_at = datetime.now(timezone.utc)

        # Compute hash_self for Fortress chain (CEO Issue #14)
        attempt.hash_self = self._compute_hash(attempt)

        # Persist to database
        self._persist(attempt)

        # Update cache
        self._last_hash = attempt.hash_self
        self._current_sequence = attempt.chain_sequence

        logger.info(f"Attempt completed: {attempt.attempt_id} -> {outcome}")
        return attempt.hash_self

    def verify_chain_integrity(self) -> bool:
        """
        Verify entire hash chain (for VEGA audit).

        Re-computes all hashes and verifies chain links.
        """
        if self.conn is None:
            return True

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT chain_status, COUNT(*) as count
                FROM fhq_governance.attempt_chain_audit
                GROUP BY chain_status
            ''')

            results = cursor.fetchall()
            for row in results:
                if row[0] == 'CHAIN_BROKEN':
                    logger.error(f"Hash chain integrity FAILED: {row[1]} broken links")
                    return False

            logger.info("Hash chain integrity: VALID")
            return True

        except Exception as e:
            logger.error(f"Chain verification error: {e}")
            return False

    def get_attempt_stats(self) -> Dict[str, int]:
        """Get attempt outcome statistics."""
        if self.conn is None:
            return {}

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT final_outcome, COUNT(*) as count
                FROM fhq_governance.execution_attempts
                GROUP BY final_outcome
            ''')

            return {row[0]: row[1] for row in cursor.fetchall()}

        except Exception as e:
            logger.error(f"Stats query error: {e}")
            return {}

    def _get_last_hash(self) -> str:
        """Get hash_self from most recent attempt in current epoch."""
        if self._last_hash:
            return self._last_hash

        if self.conn is None:
            return GENESIS_HASH

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT hash_self
                FROM fhq_governance.execution_attempts
                WHERE chain_epoch_id = %s
                ORDER BY chain_sequence DESC
                LIMIT 1
            ''', (str(DEFAULT_EPOCH_ID),))

            row = cursor.fetchone()
            if row:
                self._last_hash = row[0]
                return row[0]

        except Exception as e:
            logger.warning(f"Could not get last hash: {e}")

        return GENESIS_HASH

    def _get_next_sequence(self) -> int:
        """Get next monotonic sequence number."""
        if self._current_sequence is not None:
            self._current_sequence += 1
            return self._current_sequence

        if self.conn is None:
            return 1

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT COALESCE(MAX(chain_sequence), 0) + 1
                FROM fhq_governance.execution_attempts
                WHERE chain_epoch_id = %s
            ''', (str(DEFAULT_EPOCH_ID),))

            row = cursor.fetchone()
            self._current_sequence = row[0] if row else 1
            return self._current_sequence

        except Exception as e:
            logger.warning(f"Could not get sequence: {e}")
            return 1

    def _compute_hash(self, attempt: AttemptRecord) -> str:
        """Compute SHA-256 hash for Fortress chain."""
        content = attempt.to_dict()
        # Remove hash_self from content before hashing
        content.pop('hash_self', None)

        canonical = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _persist(self, attempt: AttemptRecord):
        """Persist attempt to database."""
        if self.conn is None:
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO fhq_governance.execution_attempts (
                    attempt_id, intent_draft_id, needle_id, decision_plan_id,
                    chain_epoch_id, hash_prev, hash_self, chain_sequence,
                    gate_exposure_passed, gate_exposure_reason,
                    gate_holiday_passed, gate_holiday_reason,
                    gate_btc_only_passed, gate_btc_only_reason,
                    gate_regime_stability_passed, gate_regime_stability_reason,
                    gate_sitc_passed, gate_sitc_reason,
                    gate_ikea_passed, gate_ikea_reason,
                    gate_inforage_passed, gate_inforage_reason,
                    gate_causal_passed, gate_causal_reason,
                    gate_fss_passed, gate_fss_reason,
                    gate_ttl_passed, gate_ttl_reason,
                    final_outcome, blocked_at_gate, block_reason,
                    sitc_event_id, inforage_session_id, ikea_validation_id,
                    causal_edge_refs, audit_only_mode,
                    cognition_started_at, cognition_completed_at, cognition_duration_ms,
                    attempt_started_at, attempt_completed_at,
                    signing_agent, signature
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
            ''', (
                str(attempt.attempt_id),
                str(attempt.intent_draft_id),
                str(attempt.needle_id),
                str(attempt.decision_plan_id) if attempt.decision_plan_id else None,
                str(attempt.chain_epoch_id),
                attempt.hash_prev,
                attempt.hash_self,
                attempt.chain_sequence,
                attempt.gate_exposure_passed,
                attempt.gate_exposure_reason,
                attempt.gate_holiday_passed,
                attempt.gate_holiday_reason,
                attempt.gate_btc_only_passed,
                attempt.gate_btc_only_reason,
                attempt.gate_regime_stability_passed,
                attempt.gate_regime_stability_reason,
                attempt.gate_sitc_passed,
                attempt.gate_sitc_reason,
                attempt.gate_ikea_passed,
                attempt.gate_ikea_reason,
                attempt.gate_inforage_passed,
                attempt.gate_inforage_reason,
                attempt.gate_causal_passed,
                attempt.gate_causal_reason,
                attempt.gate_fss_passed,
                attempt.gate_fss_reason,
                attempt.gate_ttl_passed,
                attempt.gate_ttl_reason,
                attempt.final_outcome,
                attempt.blocked_at_gate,
                attempt.block_reason,
                str(attempt.sitc_event_id) if attempt.sitc_event_id else None,
                str(attempt.inforage_session_id) if attempt.inforage_session_id else None,
                str(attempt.ikea_validation_id) if attempt.ikea_validation_id else None,
                [str(ref) for ref in attempt.causal_edge_refs],
                attempt.audit_only_mode,
                attempt.cognition_started_at,
                attempt.cognition_completed_at,
                attempt.cognition_duration_ms,
                attempt.attempt_started_at,
                attempt.attempt_completed_at,
                attempt.signing_agent,
                attempt.signature
            ))
            self.conn.commit()

        except Exception as e:
            logger.error(f"Failed to persist attempt: {e}")
            self.conn.rollback()
            raise


if __name__ == "__main__":
    # Quick test
    from uuid import uuid4

    # Create attempt without DB
    logger_instance = AttemptLogger(None)
    attempt = logger_instance.start_attempt(
        needle_id=uuid4(),
        intent_draft_id=uuid4()
    )

    # Log gates
    logger_instance.log_gate_result(attempt, 'exposure', True, 'Below limit')
    logger_instance.log_gate_result(attempt, 'holiday', True, 'Market open')
    logger_instance.log_gate_result(attempt, 'sitc', True, 'HIGH confidence')

    # Complete
    hash_self = logger_instance.complete_attempt(
        attempt,
        outcome='EXECUTED',
        decision_plan_id=uuid4()
    )

    print(f"Attempt: {attempt.attempt_id}")
    print(f"  Sequence: {attempt.chain_sequence}")
    print(f"  Hash prev: {attempt.hash_prev}")
    print(f"  Hash self: {hash_self[:16]}...")
    print(f"  Outcome: {attempt.final_outcome}")
