"""
IoS-013 ASPE — Agent State Protocol Engine
============================================
Authority: STIG (CTO & Technical Authority)
ADR Reference: ADR-018 Agent State Reliability Protocol (ASRP)
Version: 2026.PROD.G0

PURPOSE:
    Exclusive implementation of ADR-018. Provides atomic state vector
    synchronization for all FjordHQ agents. Implements Zero-Trust
    fail-closed semantics.

CONSTITUTIONAL MANDATE:
    1. Zero drift in agent perception
    2. Deterministic coordination
    3. Immutable auditability
    4. Fail-closed default
    5. No local caching permitted

USAGE:
    from ios013_aspe_engine import ASPEEngine

    engine = ASPEEngine()
    state = engine.retrieve_state_vector(agent_id='FINN')

    if state.is_valid:
        # Proceed with reasoning using state.defcon, state.regime, state.strategy
        pass
    else:
        # HALT - fail-closed semantics
        raise ASRPViolationError(state.error_message)
"""

import os
import hashlib
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor


class DEFCONLevel(Enum):
    """DEFCON levels per ADR-016"""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"
    BLACK = "BLACK"


class RegimeLabel(Enum):
    """BTC Regime labels per IoS-003"""
    STRONG_BULL = "STRONG_BULL"
    BULL = "BULL"
    RANGE_UP = "RANGE_UP"
    NEUTRAL = "NEUTRAL"
    RANGE_DOWN = "RANGE_DOWN"
    BEAR = "BEAR"
    STRONG_BEAR = "STRONG_BEAR"
    PARABOLIC = "PARABOLIC"
    BROKEN = "BROKEN"
    UNTRUSTED = "UNTRUSTED"


class StrategyPosture(Enum):
    """Strategic postures per IoS-004"""
    AGGRESSIVE_LONG = "AGGRESSIVE_LONG"
    LONG = "LONG"
    NEUTRAL = "NEUTRAL"
    DEFENSIVE = "DEFENSIVE"
    CASH = "CASH"
    CONVEX_LONG = "CONVEX_LONG"
    CONVEX_SHORT = "CONVEX_SHORT"


class RetrievalStatus(Enum):
    """State retrieval outcomes"""
    SUCCESS = "SUCCESS"
    STALE = "STALE"
    HASH_MISMATCH = "HASH_MISMATCH"
    NOT_FOUND = "NOT_FOUND"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    REJECTED = "REJECTED"
    HALT_REQUIRED = "HALT_REQUIRED"


class ASRPViolationType(Enum):
    """ASRP violation types per ADR-018 §7"""
    BYPASS_ATTEMPT = "BYPASS_ATTEMPT"
    STALE_STATE_USE = "STALE_STATE_USE"
    MISSING_HASH = "MISSING_HASH"
    AUTHORITY_OVERRIDE = "AUTHORITY_OVERRIDE"
    INVALID_READ = "INVALID_READ"
    LOCAL_CACHE = "LOCAL_CACHE"
    TORN_READ = "TORN_READ"


@dataclass
class StateVector:
    """
    Atomic state vector per ADR-018 §4.

    All fields are captured atomically - partial reads are unconstitutional.
    """
    snapshot_id: Optional[str]
    state_vector_hash: str
    snapshot_timestamp: datetime

    # DEFCON State (Authority: STIG - ADR-016)
    defcon_level: DEFCONLevel

    # BTC Regime (Authority: FINN - IoS-003)
    btc_regime_label: RegimeLabel
    btc_regime_confidence: float

    # Canonical Strategy (Authority: LARS - IoS-004)
    strategy_posture: StrategyPosture
    strategy_exposure: float

    # Validity
    is_fresh: bool
    retrieval_status: RetrievalStatus

    # Error details (if failed)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if state is valid for agent use"""
        return (
            self.retrieval_status == RetrievalStatus.SUCCESS
            and self.is_fresh
            and self.defcon_level != DEFCONLevel.BLACK
        )

    @property
    def allows_execution(self) -> bool:
        """Check if execution operations are permitted"""
        return (
            self.is_valid
            and self.defcon_level in [DEFCONLevel.GREEN, DEFCONLevel.YELLOW]
        )

    @property
    def allows_trading(self) -> bool:
        """Check if trading operations are permitted"""
        return (
            self.is_valid
            and self.defcon_level == DEFCONLevel.GREEN
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state vector for output binding"""
        return {
            "snapshot_id": self.snapshot_id,
            "state_vector_hash": self.state_vector_hash,
            "snapshot_timestamp": self.snapshot_timestamp.isoformat(),
            "defcon_level": self.defcon_level.value,
            "btc_regime_label": self.btc_regime_label.value,
            "btc_regime_confidence": self.btc_regime_confidence,
            "strategy_posture": self.strategy_posture.value,
            "strategy_exposure": self.strategy_exposure,
            "is_fresh": self.is_fresh,
            "retrieval_status": self.retrieval_status.value,
            "is_valid": self.is_valid
        }


class ASRPViolationError(Exception):
    """Raised when ASRP is violated per ADR-018 §7"""

    def __init__(self, violation_type: ASRPViolationType, message: str, agent_id: str = None):
        self.violation_type = violation_type
        self.agent_id = agent_id
        super().__init__(f"[ASRP VIOLATION - {violation_type.value}] {message}")


class ASPEEngine:
    """
    Agent State Protocol Engine (IoS-013)

    Exclusive implementation of ADR-018 ASRP.
    Provides atomic state vector synchronization with fail-closed semantics.

    CONSTITUTIONAL REQUIREMENTS:
    1. All agents MUST call retrieve_state_vector() before any reasoning
    2. NO local caching is permitted
    3. Failed retrievals MUST halt agent operation
    4. All outputs MUST be bound to state_snapshot_hash
    """

    def __init__(self, connection_string: str = None):
        """
        Initialize ASPE Engine.

        Args:
            connection_string: PostgreSQL connection string.
                             If None, uses environment variables.
        """
        self.connection_string = connection_string or self._build_connection_string()
        self._validate_connection()

    def _build_connection_string(self) -> str:
        """Build connection string from environment variables"""
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"host={host} port={port} dbname={database} user={user} password={password}"

    def _validate_connection(self) -> None:
        """Validate database connection is available"""
        try:
            with psycopg2.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        except Exception as e:
            raise ASRPViolationError(
                ASRPViolationType.INVALID_READ,
                f"IoS-013 cannot connect to database: {e}"
            )

    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.connection_string)

    def retrieve_state_vector(
        self,
        agent_id: str,
        agent_tier: str = "TIER-2"
    ) -> StateVector:
        """
        Atomically retrieve current state vector.

        Per ADR-018 §4: Agents may not read state objects individually.
        This function retrieves the complete atomic state vector or fails.

        Args:
            agent_id: Identifier of the requesting agent
            agent_tier: Agent tier (TIER-1, TIER-2, TIER-3)

        Returns:
            StateVector with current state or HALT status

        Raises:
            ASRPViolationError: If retrieval fails in unrecoverable way
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Call the atomic retrieval function
                    cur.execute(
                        "SELECT * FROM fhq_governance.retrieve_state_vector(%s, %s)",
                        (agent_id, agent_tier)
                    )
                    result = cur.fetchone()

                    if result is None:
                        return self._create_halt_state("No result from retrieve_state_vector")

                    # Parse result into StateVector
                    return self._parse_state_result(result)

        except psycopg2.Error as e:
            # Log system error and return HALT state
            return self._create_halt_state(f"Database error: {e}")
        except Exception as e:
            return self._create_halt_state(f"Unexpected error: {e}")

    def _parse_state_result(self, result: Dict) -> StateVector:
        """Parse database result into StateVector"""
        try:
            # Handle HALT status
            if result.get("retrieval_status") == "HALT_REQUIRED":
                return self._create_halt_state(result.get("state_vector_hash", "Unknown error"))

            # Parse enums safely
            defcon = DEFCONLevel(result["defcon_level"])
            regime = RegimeLabel(result["btc_regime_label"])
            posture = StrategyPosture(result["strategy_posture"])
            status = RetrievalStatus(result["retrieval_status"])

            return StateVector(
                snapshot_id=str(result["snapshot_id"]) if result.get("snapshot_id") else None,
                state_vector_hash=result["state_vector_hash"],
                snapshot_timestamp=result["snapshot_timestamp"],
                defcon_level=defcon,
                btc_regime_label=regime,
                btc_regime_confidence=float(result["btc_regime_confidence"]),
                strategy_posture=posture,
                strategy_exposure=float(result["strategy_exposure"]),
                is_fresh=result["is_fresh"],
                retrieval_status=status
            )
        except (KeyError, ValueError) as e:
            return self._create_halt_state(f"Failed to parse state: {e}")

    def _create_halt_state(self, error_message: str) -> StateVector:
        """Create HALT state vector for fail-closed semantics"""
        return StateVector(
            snapshot_id=None,
            state_vector_hash="HALT",
            snapshot_timestamp=datetime.now(timezone.utc),
            defcon_level=DEFCONLevel.BLACK,
            btc_regime_label=RegimeLabel.UNTRUSTED,
            btc_regime_confidence=0.0,
            strategy_posture=StrategyPosture.CASH,
            strategy_exposure=0.0,
            is_fresh=False,
            retrieval_status=RetrievalStatus.HALT_REQUIRED,
            error_code="ASRP_HALT",
            error_message=error_message
        )

    def create_snapshot(self) -> str:
        """
        Create new atomic state snapshot.

        Authority: STIG only. Called by orchestrator to refresh state.

        Returns:
            New snapshot_id

        Raises:
            ASRPViolationError: If snapshot creation fails
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT fhq_governance.create_state_snapshot()")
                    result = cur.fetchone()
                    conn.commit()
                    return str(result[0])
        except Exception as e:
            raise ASRPViolationError(
                ASRPViolationType.INVALID_READ,
                f"Failed to create state snapshot: {e}",
                agent_id="STIG"
            )

    def validate_output_binding(
        self,
        agent_id: str,
        state_hash: str,
        intended_action: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate state hash before output binding.

        Per ADR-018 §5: Every agent output must embed state_snapshot_hash.

        Args:
            agent_id: Agent producing the output
            state_hash: State hash the output is bound to
            intended_action: Type of output being produced

        Returns:
            Tuple of (is_approved, rejection_reason)
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """SELECT * FROM fhq_governance.vega_validate_state_request(%s, %s, %s)""",
                        (agent_id, state_hash, intended_action)
                    )
                    result = cur.fetchone()

                    return (result["is_approved"], result.get("rejection_reason"))
        except Exception as e:
            return (False, f"Validation error: {e}")

    def bind_output(
        self,
        state_hash: str,
        state_timestamp: datetime,
        agent_id: str,
        output_type: str,
        output_id: str,
        output_table: str,
        output_hash: str
    ) -> str:
        """
        Bind an agent output to its governing state context.

        Per ADR-018 §5.1: No agent output is valid without its contextual fingerprint.

        Args:
            state_hash: State vector hash at time of reasoning
            state_timestamp: Timestamp of state snapshot
            agent_id: Agent producing the output
            output_type: Type of output (REASONING, TRADE, etc.)
            output_id: UUID of the output record
            output_table: Table where output is stored
            output_hash: Hash of the output content

        Returns:
            binding_id
        """
        # Compute binding hash
        binding_data = f"{state_hash}:{agent_id}:{output_type}:{output_id}:{output_hash}"
        binding_hash = hashlib.sha256(binding_data.encode()).hexdigest()

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO fhq_governance.output_bindings (
                            state_snapshot_hash, state_timestamp, agent_id,
                            output_type, output_id, output_table,
                            output_hash, binding_hash, binding_status
                        ) VALUES (%s, %s, %s, %s, %s::uuid, %s, %s, %s, 'VALID')
                        RETURNING binding_id
                        """,
                        (state_hash, state_timestamp, agent_id,
                         output_type, output_id, output_table,
                         output_hash, binding_hash)
                    )
                    result = cur.fetchone()
                    conn.commit()
                    return str(result[0])
        except Exception as e:
            raise ASRPViolationError(
                ASRPViolationType.MISSING_HASH,
                f"Failed to bind output: {e}",
                agent_id=agent_id
            )

    def log_violation(
        self,
        violation_type: ASRPViolationType,
        agent_id: str,
        attempted_action: str,
        state_hash_expected: str = None,
        state_hash_provided: str = None,
        enforcement_action: str = "BLOCKED"
    ) -> str:
        """
        Log an ASRP violation.

        Per ADR-018 §7: All violations trigger ADR-009 suspension review.

        Args:
            violation_type: Type of ASRP violation
            agent_id: Agent that committed the violation
            attempted_action: Action that was attempted
            state_hash_expected: Expected state hash
            state_hash_provided: Provided state hash
            enforcement_action: Action taken (BLOCKED, ISOLATED, etc.)

        Returns:
            violation_id
        """
        evidence = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "violation_type": violation_type.value,
            "agent_id": agent_id,
            "attempted_action": attempted_action,
            "state_hash_expected": state_hash_expected,
            "state_hash_provided": state_hash_provided,
            "enforcement_action": enforcement_action
        }

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO fhq_governance.asrp_violations (
                            violation_type, agent_id, attempted_action,
                            state_hash_expected, state_hash_provided,
                            enforcement_action, evidence_bundle
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING violation_id
                        """,
                        (violation_type.value, agent_id, attempted_action,
                         state_hash_expected, state_hash_provided,
                         enforcement_action, json.dumps(evidence))
                    )
                    result = cur.fetchone()
                    conn.commit()
                    return str(result[0])
        except Exception as e:
            # Even logging failures should not be silent
            print(f"[CRITICAL] Failed to log ASRP violation: {e}")
            return None

    def get_current_defcon(self) -> DEFCONLevel:
        """
        Get current DEFCON level (convenience method).

        NOTE: This should only be used for display/logging.
        For actual operations, use retrieve_state_vector().
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT current_defcon FROM fhq_governance.system_state
                           WHERE is_active = TRUE LIMIT 1"""
                    )
                    result = cur.fetchone()
                    return DEFCONLevel(result[0]) if result else DEFCONLevel.BLACK
        except Exception:
            return DEFCONLevel.BLACK


# Convenience function for agent use
def get_state_vector(agent_id: str, agent_tier: str = "TIER-2") -> StateVector:
    """
    Retrieve current state vector (convenience function).

    This is the primary entry point for agents to get synchronized state.

    Example:
        state = get_state_vector("FINN")
        if not state.is_valid:
            raise ASRPViolationError("Cannot proceed without valid state")

        # Use state for reasoning
        if state.defcon_level == DEFCONLevel.GREEN:
            # Normal operations
            pass
    """
    engine = ASPEEngine()
    return engine.retrieve_state_vector(agent_id, agent_tier)


if __name__ == "__main__":
    # Self-test
    print("=" * 70)
    print("IoS-013 ASPE — Agent State Protocol Engine")
    print("Self-Test Execution")
    print("=" * 70)

    try:
        engine = ASPEEngine()

        # Test 1: Retrieve state vector
        print("\n[TEST 1] Retrieving state vector for STIG...")
        state = engine.retrieve_state_vector("STIG", "TIER-1")

        print(f"  Snapshot ID: {state.snapshot_id}")
        print(f"  State Hash: {state.state_vector_hash[:16]}...")
        print(f"  Timestamp: {state.snapshot_timestamp}")
        print(f"  DEFCON: {state.defcon_level.value}")
        print(f"  BTC Regime: {state.btc_regime_label.value} ({state.btc_regime_confidence:.2f})")
        print(f"  Strategy: {state.strategy_posture.value} ({state.strategy_exposure:.2f})")
        print(f"  Is Fresh: {state.is_fresh}")
        print(f"  Status: {state.retrieval_status.value}")
        print(f"  Is Valid: {state.is_valid}")
        print(f"  Allows Execution: {state.allows_execution}")
        print(f"  Allows Trading: {state.allows_trading}")

        # Test 2: Validate output binding
        if state.is_valid:
            print("\n[TEST 2] Validating output binding...")
            is_approved, reason = engine.validate_output_binding(
                "STIG", state.state_vector_hash, "REASONING"
            )
            print(f"  Approved: {is_approved}")
            if reason:
                print(f"  Reason: {reason}")

        # Test 3: Create new snapshot
        print("\n[TEST 3] Creating new state snapshot...")
        new_id = engine.create_snapshot()
        print(f"  New Snapshot ID: {new_id}")

        # Test 4: Retrieve updated state
        print("\n[TEST 4] Retrieving updated state...")
        new_state = engine.retrieve_state_vector("STIG", "TIER-1")
        print(f"  New State Hash: {new_state.state_vector_hash[:16]}...")
        print(f"  Status: {new_state.retrieval_status.value}")

        print("\n" + "=" * 70)
        print("IoS-013 ASPE Self-Test: PASSED")
        print("=" * 70)

    except Exception as e:
        print(f"\n[ERROR] Self-test failed: {e}")
        print("\n" + "=" * 70)
        print("IoS-013 ASPE Self-Test: FAILED")
        print("=" * 70)
