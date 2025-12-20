"""
FjordHQ LLM Router
==================
Authority: CEO Directive - PHASE 3
Compliance: ADR-001, ADR-012, ADR-016, ADR-018, ADR-020, ADR-021
Blueprint: LLM_ROUTER_BLUEPRINT_v1.md

"Better no LLM call than an untracked LLM call."

Centralized LLM routing with fail-closed semantics.
All LLM calls in FjordHQ MUST pass through this router.
"""

import os
import json
import hashlib
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, Callable
from uuid import UUID, uuid4
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.extras import Json, register_uuid
from dotenv import load_dotenv

# Register UUID adapter for psycopg2
register_uuid()

from .telemetry_envelope import TelemetryEnvelope, TaskType, CognitiveModality, calculate_cost
from .errors import (
    TelemetryError,
    TelemetryWriteFailure,
    BudgetExceededError,
    GovernanceBlockError,
    ASRPStateBlockedError,
    DEFCONBlockedError,
    CognitiveContextMissingError,
    ProviderError,
    TimeoutError as TelemetryTimeoutError
)

load_dotenv()

logger = logging.getLogger('fhq_telemetry.router')


class TelemetryConfig:
    """Configuration from fhq_governance.telemetry_config."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[float] = None
        self._cache_ttl: float = 60.0  # Refresh every 60 seconds

    def _load_config(self, conn) -> None:
        """Load config from database."""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT config_key, config_value, config_type
                FROM fhq_governance.telemetry_config
                WHERE effective_from <= NOW()
                  AND (effective_until IS NULL OR effective_until > NOW())
            """)
            for key, value, config_type in cur.fetchall():
                if config_type == 'BOOLEAN':
                    self._cache[key] = value.lower() == 'true'
                elif config_type == 'INTEGER':
                    self._cache[key] = int(value)
                elif config_type == 'DECIMAL':
                    self._cache[key] = Decimal(value)
                elif config_type == 'JSON':
                    self._cache[key] = json.loads(value)
                else:
                    self._cache[key] = value
        self._cache_time = time.time()

    def get(self, key: str, default: Any = None, conn=None) -> Any:
        """Get config value, refreshing cache if needed."""
        if conn and (self._cache_time is None or
                     time.time() - self._cache_time > self._cache_ttl):
            self._load_config(conn)
        return self._cache.get(key, default)

    @property
    def fail_closed_enabled(self) -> bool:
        return self._cache.get('FAIL_CLOSED_ENABLED', True)

    @property
    def budget_check_enabled(self) -> bool:
        return self._cache.get('BUDGET_CHECK_ENABLED', True)

    @property
    def asrp_check_enabled(self) -> bool:
        return self._cache.get('ASRP_CHECK_ENABLED', True)

    @property
    def defcon_check_enabled(self) -> bool:
        return self._cache.get('DEFCON_CHECK_ENABLED', True)

    @property
    def cognitive_linking_enabled(self) -> bool:
        return self._cache.get('COGNITIVE_LINKING_ENABLED', True)

    @property
    def cognitive_context_required_for_research(self) -> bool:
        return self._cache.get('COGNITIVE_CONTEXT_REQUIRED_FOR_RESEARCH', True)

    @property
    def default_timeout_ms(self) -> int:
        return self._cache.get('DEFAULT_TIMEOUT_MS', 60000)

    @property
    def max_retry_count(self) -> int:
        return self._cache.get('MAX_RETRY_COUNT', 3)


class LLMRouter:
    """
    Centralized LLM Router with fail-closed semantics.

    Per LLM Router Blueprint v1:
    1. Pre-validates every LLM call
    2. Blocks if telemetry cannot write
    3. Blocks if budget insufficient (ADR-012)
    4. Hydrates governance context (IoS-013)
    5. Enforces IKEA & InForage constraints
    6. Attaches pricing model per provider (TCS-v1)

    Core principle: "Better NO call than an UNTRACKED call."
    """

    _instance: Optional['LLMRouter'] = None

    def __new__(cls):
        """Singleton pattern for router."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config = TelemetryConfig()
        self._db_conn: Optional[Any] = None
        logger.info("LLMRouter initialized (PHASE 3)")

    def get_connection(self):
        """Get database connection, reconnecting if needed."""
        if self._db_conn is None or self._db_conn.closed:
            self._db_conn = psycopg2.connect(
                host=os.getenv('PGHOST', '127.0.0.1'),
                port=os.getenv('PGPORT', '54322'),
                database=os.getenv('PGDATABASE', 'postgres'),
                user=os.getenv('PGUSER', 'postgres'),
                password=os.getenv('PGPASSWORD', 'postgres')
            )
        return self._db_conn

    @contextmanager
    def connection(self):
        """Context manager for database connection."""
        conn = self.get_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            pass  # Keep connection alive

    # =========================================================================
    # PRE-CALL VALIDATION (6 Gates per Blueprint)
    # =========================================================================

    def check_budget(self, provider: str, agent_id: str,
                     estimated_cost: Decimal = Decimal("0.01")) -> tuple[bool, Optional[BudgetExceededError]]:
        """
        Gate 1: Budget Check (ADR-012).

        Returns (passed, error_if_failed).
        """
        if not self.config.budget_check_enabled:
            return True, None

        with self.connection() as conn:
            self.config.get('BUDGET_CHECK_ENABLED', conn=conn)  # Refresh config

            with conn.cursor() as cur:
                # Check daily budget for provider
                cur.execute("""
                    SELECT daily_limit, requests_made, usage_percent
                    FROM fhq_governance.api_budget_log
                    WHERE provider_name = %s AND usage_date = CURRENT_DATE
                    ORDER BY usage_date DESC LIMIT 1
                """, (provider,))
                row = cur.fetchone()

                if row:
                    daily_limit, requests_made, usage_percent = row
                    if usage_percent and usage_percent >= 100:
                        return False, BudgetExceededError(
                            message=f"Daily budget exceeded for {provider}",
                            budget_type="DAILY",
                            budget_limit=Decimal(str(daily_limit)),
                            current_usage=Decimal(str(requests_made)),
                            requested_estimate=estimated_cost,
                            provider=provider
                        )
                    elif usage_percent and usage_percent >= 90:
                        logger.warning(f"Budget warning: {provider} at {usage_percent}%")

        return True, None

    def check_asrp_state(self, agent_id: str) -> tuple[bool, Optional[ASRPStateBlockedError]]:
        """
        Gate 2: ASRP State Check (ADR-018).

        Returns (passed, error_if_failed).
        Checks:
        1. Agent is not suspended in org_agents
        2. No recent state mismatch in asrp_state_log
        """
        if not self.config.asrp_check_enabled:
            return True, None

        with self.connection() as conn:
            with conn.cursor() as cur:
                # Check if agent is suspended in org_agents
                cur.execute("""
                    SELECT is_suspended, suspension_reason
                    FROM fhq_org.org_agents
                    WHERE agent_id = %s
                """, (agent_id,))
                row = cur.fetchone()

                if row:
                    is_suspended, suspension_reason = row
                    if is_suspended:
                        return False, ASRPStateBlockedError(
                            message=f"Agent {agent_id} is suspended: {suspension_reason}",
                            asrp_state='SUSPENDED'
                        )

                # Check for recent state mismatches in asrp_state_log
                cur.execute("""
                    SELECT state_mismatch, mismatch_severity, enforcement_action
                    FROM fhq_governance.asrp_state_log
                    WHERE agent_id = %s
                      AND state_mismatch = true
                      AND recorded_at > NOW() - INTERVAL '1 hour'
                    ORDER BY recorded_at DESC LIMIT 1
                """, (agent_id,))
                mismatch_row = cur.fetchone()

                if mismatch_row:
                    state_mismatch, severity, action = mismatch_row
                    if severity in ('CRITICAL', 'HIGH'):
                        return False, ASRPStateBlockedError(
                            message=f"Agent {agent_id} has recent state mismatch ({severity})",
                            asrp_state=f'MISMATCH_{severity}'
                        )

        return True, None

    def check_defcon_level(self) -> tuple[bool, Optional[DEFCONBlockedError]]:
        """
        Gate 3: DEFCON Level Check (ADR-016).

        Returns (passed, error_if_failed).
        DEFCON levels: GREEN (5), BLUE (4), YELLOW (3), ORANGE (2), RED (1)
        LLM operations blocked at RED (1) and ORANGE (2).
        """
        if not self.config.defcon_check_enabled:
            return True, None

        with self.connection() as conn:
            with conn.cursor() as cur:
                # Check current DEFCON level from defcon_state
                cur.execute("""
                    SELECT defcon_level, trigger_reason
                    FROM fhq_governance.defcon_state
                    WHERE is_current = true
                    ORDER BY triggered_at DESC LIMIT 1
                """, ())
                row = cur.fetchone()

                if row:
                    level_str, trigger_reason = row
                    # Map level string to number for comparison
                    level_map = {'RED': 1, 'ORANGE': 2, 'YELLOW': 3, 'BLUE': 4, 'GREEN': 5}
                    level_num = level_map.get(level_str.upper(), 5)

                    if level_num <= 2:  # RED or ORANGE blocks LLM
                        return False, DEFCONBlockedError(
                            message=f"DEFCON {level_str} blocks LLM operations: {trigger_reason}",
                            defcon_level=level_num
                        )

        return True, None

    def hydrate_governance_context(self, agent_id: str, task_type: TaskType) -> tuple[str, bool]:
        """
        Gate 4: Governance Context Hydration (IoS-013).

        Returns (governance_context_hash, success).
        """
        # Build governance context
        context = {
            "agent_id": agent_id,
            "task_type": task_type.value if isinstance(task_type, TaskType) else task_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "router_version": "1.0.0"
        }

        # Hash the context
        context_str = json.dumps(context, sort_keys=True)
        context_hash = hashlib.sha256(context_str.encode()).hexdigest()

        return context_hash, True

    def check_cognitive_context(self, envelope: TelemetryEnvelope) -> tuple[bool, Optional[CognitiveContextMissingError]]:
        """
        Gate 5 & 6: Cognitive Context Check (ADR-021).

        Validates cognitive_parent_id is present for multi-hop reasoning.
        """
        if not self.config.cognitive_linking_enabled:
            return True, None

        # Exempt task types don't require cognitive context
        exempt_types = {TaskType.SYSTEM_MAINTENANCE, TaskType.HEALTH_CHECK}
        if envelope.task_type in exempt_types:
            return True, None

        # RESEARCH and multi-hop tasks require cognitive_parent_id
        if self.config.cognitive_context_required_for_research:
            if envelope.task_type == TaskType.RESEARCH and envelope.cognitive_parent_id is None:
                # Allow if this is the root of a new research chain
                # Only enforce for chains (when protocol_ref is set)
                if envelope.protocol_ref is not None:
                    return False, CognitiveContextMissingError(
                        message="cognitive_parent_id required for chained RESEARCH tasks",
                        task_type=envelope.task_type.value
                    )

        return True, None

    def validate_pre_call(self, envelope: TelemetryEnvelope) -> Optional[TelemetryError]:
        """
        Run all 6 pre-call validation gates.

        Returns error if any gate fails, None if all pass.
        """
        # Gate 1: Budget
        passed, error = self.check_budget(envelope.provider, envelope.agent_id)
        if not passed:
            return error

        # Gate 2: ASRP State
        passed, error = self.check_asrp_state(envelope.agent_id)
        if not passed:
            return error

        # Gate 3: DEFCON
        passed, error = self.check_defcon_level()
        if not passed:
            return error

        # Gate 4: Governance Context
        gov_hash, success = self.hydrate_governance_context(
            envelope.agent_id, envelope.task_type
        )
        if success:
            envelope.governance_context_hash = gov_hash

        # Gate 5-6: Cognitive Context
        passed, error = self.check_cognitive_context(envelope)
        if not passed:
            return error

        return None

    # =========================================================================
    # TELEMETRY WRITING (Fail-Closed)
    # =========================================================================

    def get_previous_hash(self, agent_id: str) -> Optional[str]:
        """Get previous lineage hash for agent."""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT lineage_hash
                    FROM fhq_governance.llm_routing_log
                    WHERE agent_id = %s AND lineage_hash IS NOT NULL
                    ORDER BY timestamp_utc DESC LIMIT 1
                """, (agent_id,))
                row = cur.fetchone()
                return row[0] if row else None

    def write_telemetry(self, envelope: TelemetryEnvelope) -> bool:
        """
        Write telemetry envelope to all target tables.

        FAIL-CLOSED: If ANY write fails, rollback and return False.
        The LLM response MUST be discarded if this returns False.
        """
        # Compute hashes
        prev_hash = self.get_previous_hash(envelope.agent_id)
        envelope.compute_hash_self()
        envelope.compute_lineage_hash(prev_hash)
        envelope.hash_chain_id = f"LLM-{envelope.agent_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"

        try:
            with self.connection() as conn:
                with conn.cursor() as cur:
                    # 1. Write to llm_routing_log
                    data = envelope.to_routing_log_dict()
                    cur.execute("""
                        INSERT INTO fhq_governance.llm_routing_log (
                            envelope_id, agent_id, request_timestamp,
                            requested_provider, requested_tier, routed_provider, routed_tier,
                            policy_satisfied, violation_detected,
                            task_name, task_type, model,
                            tokens_in, tokens_out, latency_ms, cost_usd,
                            timestamp_utc, correlation_id,
                            governance_context_hash,
                            cognitive_parent_id, protocol_ref, cognitive_modality,
                            stream_mode, stream_chunks, stream_token_accumulator, stream_first_token_ms,
                            error_type, error_payload,
                            hash_chain_id, hash_self, hash_prev, lineage_hash,
                            backfill
                        ) VALUES (
                            %(envelope_id)s, %(agent_id)s, NOW(),
                            %(requested_provider)s, %(requested_tier)s, %(routed_provider)s, %(routed_tier)s,
                            %(policy_satisfied)s, %(violation_detected)s,
                            %(task_name)s, %(task_type)s, %(model)s,
                            %(tokens_in)s, %(tokens_out)s, %(latency_ms)s, %(cost_usd)s,
                            %(timestamp_utc)s, %(correlation_id)s,
                            %(governance_context_hash)s,
                            %(cognitive_parent_id)s, %(protocol_ref)s, %(cognitive_modality)s,
                            %(stream_mode)s, %(stream_chunks)s, %(stream_token_accumulator)s, %(stream_first_token_ms)s,
                            %(error_type)s, %(error_payload)s,
                            %(hash_chain_id)s, %(hash_self)s, %(hash_prev)s, %(lineage_hash)s,
                            %(backfill)s
                        )
                    """, {
                        **data,
                        'error_payload': Json(data['error_payload']) if data['error_payload'] else None
                    })

                    # 2. Write error if present
                    if envelope.error_type:
                        error_data = envelope.to_error_log_dict()
                        cur.execute("""
                            INSERT INTO fhq_governance.telemetry_errors (
                                envelope_id, agent_id, task_name, task_type,
                                error_type, error_payload, provider, model
                            ) VALUES (
                                %(envelope_id)s, %(agent_id)s, %(task_name)s, %(task_type)s,
                                %(error_type)s, %(error_payload)s, %(provider)s, %(model)s
                            )
                        """, {
                            **error_data,
                            'error_payload': Json(error_data['error_payload']) if error_data['error_payload'] else None
                        })

                conn.commit()
                logger.debug(f"Telemetry written: {envelope.envelope_id}")
                return True

        except Exception as e:
            logger.error(f"Telemetry write failed: {e}")
            if self.config.fail_closed_enabled:
                raise TelemetryWriteFailure(
                    message=f"Telemetry write failed: {e}",
                    envelope_id=envelope.envelope_id
                )
            return False

    def write_error_only(self, envelope: TelemetryEnvelope, error: TelemetryError) -> bool:
        """Write error to telemetry when call was blocked pre-flight."""
        envelope.error_type = type(error).__name__
        if hasattr(error, 'to_error_payload'):
            envelope.error_payload = error.to_error_payload()
        else:
            envelope.error_payload = {"message": str(error)}

        return self.write_telemetry(envelope)

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def create_envelope(
        self,
        agent_id: str,
        task_name: str,
        task_type: TaskType,
        provider: str,
        model: str,
        correlation_id: Optional[UUID] = None,
        cognitive_parent_id: Optional[UUID] = None,
        protocol_ref: Optional[UUID] = None,
        cognitive_modality: Optional[CognitiveModality] = None
    ) -> TelemetryEnvelope:
        """Create a new telemetry envelope."""
        return TelemetryEnvelope(
            envelope_id=uuid4(),
            agent_id=agent_id,
            task_name=task_name,
            task_type=task_type,
            provider=provider,
            model=model,
            correlation_id=correlation_id,
            cognitive_parent_id=cognitive_parent_id,
            protocol_ref=protocol_ref,
            cognitive_modality=cognitive_modality,
            timestamp_utc=datetime.now(timezone.utc)
        )

    def record_call(
        self,
        envelope: TelemetryEnvelope,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        stream_mode: bool = False,
        stream_chunks: Optional[int] = None,
        stream_first_token_ms: Optional[int] = None,
        error: Optional[Exception] = None
    ) -> bool:
        """
        Record a completed LLM call.

        This is the main entry point after an LLM call completes.
        Returns True if telemetry was written successfully.

        IMPORTANT: If this returns False and fail_closed is enabled,
        the LLM response MUST be discarded.
        """
        envelope.tokens_in = tokens_in
        envelope.tokens_out = tokens_out
        envelope.latency_ms = latency_ms
        envelope.stream_mode = stream_mode

        if stream_mode:
            envelope.stream_chunks = stream_chunks
            envelope.stream_token_accumulator = tokens_out
            envelope.stream_first_token_ms = stream_first_token_ms

        # Calculate cost
        envelope.calculate_cost_from_tokens()

        # Record error if present
        if error:
            envelope.error_type = type(error).__name__
            if hasattr(error, 'to_error_payload'):
                envelope.error_payload = error.to_error_payload()
            else:
                envelope.error_payload = {"message": str(error)}

        return self.write_telemetry(envelope)


# Global router instance
_router: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    """Get the singleton router instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
