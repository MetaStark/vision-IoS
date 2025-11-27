"""
Economic Safety Engine
ADR-012: Economic Safety Architecture

Authority: LARS (ADR-012 Economic Safety Architecture)
Owners: LINE (Operations), STIG (Architecture), VEGA (Governance)
Canonical ADR Chain: ADR-001 → ADR-012

Purpose:
    Enforce deterministic rate limits, cost ceilings, and execution bounds
    for all LLM operations. This engine is the mandatory protection layer
    embedded in the Worker pipeline before any external LLM call.

Features:
    - Rate Governance Layer (Section 4.1): Controls call frequency and volume
    - Cost Governance Layer (Section 4.2): Enforces hard monetary ceilings
    - Execution Governance Layer (Section 4.3): Bounds depth, latency, tokens
    - Automatic STUB_MODE fallback on any violation
    - All violations logged as VEGA-visible governance events
    - Hash-chained violation events for Fortress integrity (ADR-011)

Database:
    All operations use vega schema tables on local Postgres (127.0.0.1:54322):
    - vega.llm_rate_limits
    - vega.llm_cost_limits
    - vega.llm_execution_limits
    - vega.llm_usage_log
    - vega.llm_violation_events

Compliance:
    - ADR-001: System Charter
    - ADR-002: Audit & Error Reconciliation
    - ADR-007: Orchestrator invariants
    - ADR-008: Cryptographic signatures (Ed25519)
    - ADR-010: Discrepancy scoring
    - ADR-011: Production Fortress
    - ADR-012: Economic Safety Architecture (this ADR)
"""

import os
import json
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("economic_safety_engine")


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class OperationMode(Enum):
    """LLM operation mode (ADR-012)."""
    LIVE = "LIVE"   # Real API calls
    STUB = "STUB"   # Mock/placeholder responses


class ViolationType(Enum):
    """Types of economic safety violations (ADR-012 Section 4)."""
    RATE = "RATE"          # Rate limit violation
    COST = "COST"          # Cost ceiling breach
    EXECUTION = "EXECUTION"  # Step/latency/token overrun


class GovernanceAction(Enum):
    """Actions taken on violation (ADR-012)."""
    NONE = "NONE"
    WARN = "WARN"
    SUSPEND_RECOMMENDATION = "SUSPEND_RECOMMENDATION"
    SWITCH_TO_STUB = "SWITCH_TO_STUB"


class Severity(Enum):
    """Violation severity classification (ADR-002)."""
    CLASS_A = "CLASS_A"  # Catastrophic
    CLASS_B = "CLASS_B"  # Significant
    CLASS_C = "CLASS_C"  # Minor


# ADR-012 Constitutional Defaults
DEFAULT_RATE_LIMITS = {
    'max_calls_per_minute': 3,
    'max_calls_per_pipeline_execution': 5,
    'global_daily_limit': 100
}

DEFAULT_COST_LIMITS = {
    'max_daily_cost': Decimal('5.00'),
    'max_cost_per_task': Decimal('0.50'),
    'max_cost_per_agent_per_day': Decimal('1.00')
}

DEFAULT_EXECUTION_LIMITS = {
    'max_llm_steps_per_task': 3,
    'max_total_latency_ms': 3000,
    'max_total_tokens_generated': 4000,  # Reasonable default
    'abort_on_overrun': True
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RateLimits:
    """Rate limit configuration (ADR-012 Section 4.1)."""
    max_calls_per_minute: int = 3
    max_calls_per_pipeline_execution: int = 5
    global_daily_limit: int = 100
    agent_id: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class CostLimits:
    """Cost limit configuration (ADR-012 Section 4.2)."""
    max_daily_cost: Decimal = Decimal('5.00')
    max_cost_per_task: Decimal = Decimal('0.50')
    max_cost_per_agent_per_day: Decimal = Decimal('1.00')
    currency: str = 'USD'
    agent_id: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class ExecutionLimits:
    """Execution limit configuration (ADR-012 Section 4.3)."""
    max_llm_steps_per_task: int = 3
    max_total_latency_ms: int = 3000
    max_total_tokens_generated: Optional[int] = None
    abort_on_overrun: bool = True
    agent_id: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class UsageRecord:
    """Record of a single LLM usage event."""
    agent_id: str
    provider: str
    mode: OperationMode
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: Decimal = Decimal('0.0')
    latency_ms: int = 0
    task_id: Optional[str] = None
    cycle_id: Optional[str] = None
    model: Optional[str] = None
    request_hash: Optional[str] = None
    response_hash: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ViolationEvent:
    """Record of an economic safety violation."""
    agent_id: str
    violation_type: ViolationType
    governance_action: GovernanceAction
    severity: Severity = Severity.CLASS_B
    violation_subtype: Optional[str] = None
    task_id: Optional[str] = None
    cycle_id: Optional[str] = None
    provider: Optional[str] = None
    limit_value: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None
    discrepancy_score: Optional[Decimal] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SafetyCheckResult:
    """Result of a safety check before LLM call."""
    allowed: bool
    reason: str
    mode: OperationMode
    violation: Optional[ViolationEvent] = None


@dataclass
class QGF6Result:
    """Result of QG-F6 Economic Safety Gate check."""
    gate_passed: bool
    rate_violations: int
    cost_violations: int
    execution_violations: int
    last_violation_at: Optional[datetime]
    check_timestamp: datetime


# =============================================================================
# ECONOMIC SAFETY ENGINE
# =============================================================================

class EconomicSafetyEngine:
    """
    Economic Safety Engine (ADR-012).

    Enforces rate, cost, and execution governance for all LLM operations.
    This engine is embedded in the Worker pipeline and is unbypassable.

    All limits are read from the vega schema tables on local Postgres.
    All violations are logged as governance events with hash-chain integrity.
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize the Economic Safety Engine.

        Args:
            connection_string: PostgreSQL connection string.
                Defaults to environment variables (PGHOST, PGPORT, etc.)
        """
        self.connection_string = connection_string or self._get_connection_string()
        self.conn = None

        # In-memory caches (for performance, refreshed periodically)
        self._rate_limits_cache: Dict[Tuple[str, str], RateLimits] = {}
        self._cost_limits_cache: Dict[Tuple[str, str], CostLimits] = {}
        self._execution_limits_cache: Dict[Tuple[str, str], ExecutionLimits] = {}
        self._cache_ttl_seconds = 60
        self._cache_refreshed_at: Optional[datetime] = None

        # Current mode
        self._global_mode: OperationMode = OperationMode.STUB

        # Last hash for chain
        self._last_violation_hash: Optional[str] = None

    @staticmethod
    def _get_connection_string() -> str:
        """Get PostgreSQL connection string from environment variables."""
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    def connect(self):
        """Establish database connection."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(self.connection_string)

    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # =========================================================================
    # LIMIT RETRIEVAL (from vega schema)
    # =========================================================================

    def get_rate_limits(
        self,
        agent_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> RateLimits:
        """
        Get rate limits for agent/provider from vega.llm_rate_limits.

        Falls back to global defaults if no specific limits found.
        """
        self.connect()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try specific agent+provider first
                cur.execute("""
                    SELECT max_calls_per_minute, max_calls_per_pipeline_execution,
                           global_daily_limit, agent_id, provider
                    FROM vega.llm_rate_limits
                    WHERE (agent_id = %s OR agent_id IS NULL)
                      AND (provider = %s OR provider IS NULL)
                      AND is_active = TRUE
                    ORDER BY
                        CASE WHEN agent_id IS NOT NULL AND provider IS NOT NULL THEN 1
                             WHEN agent_id IS NOT NULL THEN 2
                             WHEN provider IS NOT NULL THEN 3
                             ELSE 4 END
                    LIMIT 1
                """, (agent_id, provider))

                row = cur.fetchone()
                if row:
                    return RateLimits(
                        max_calls_per_minute=row['max_calls_per_minute'],
                        max_calls_per_pipeline_execution=row['max_calls_per_pipeline_execution'],
                        global_daily_limit=row['global_daily_limit'],
                        agent_id=row['agent_id'],
                        provider=row['provider']
                    )
        except psycopg2.Error as e:
            logger.warning(f"Failed to get rate limits from DB: {e}. Using defaults.")

        return RateLimits(**DEFAULT_RATE_LIMITS)

    def get_cost_limits(
        self,
        agent_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> CostLimits:
        """
        Get cost limits for agent/provider from vega.llm_cost_limits.

        Falls back to global defaults if no specific limits found.
        """
        self.connect()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT max_daily_cost, max_cost_per_task, max_cost_per_agent_per_day,
                           currency, agent_id, provider
                    FROM vega.llm_cost_limits
                    WHERE (agent_id = %s OR agent_id IS NULL)
                      AND (provider = %s OR provider IS NULL)
                      AND is_active = TRUE
                    ORDER BY
                        CASE WHEN agent_id IS NOT NULL AND provider IS NOT NULL THEN 1
                             WHEN agent_id IS NOT NULL THEN 2
                             WHEN provider IS NOT NULL THEN 3
                             ELSE 4 END
                    LIMIT 1
                """, (agent_id, provider))

                row = cur.fetchone()
                if row:
                    return CostLimits(
                        max_daily_cost=Decimal(str(row['max_daily_cost'])),
                        max_cost_per_task=Decimal(str(row['max_cost_per_task'])),
                        max_cost_per_agent_per_day=Decimal(str(row['max_cost_per_agent_per_day'])),
                        currency=row['currency'],
                        agent_id=row['agent_id'],
                        provider=row['provider']
                    )
        except psycopg2.Error as e:
            logger.warning(f"Failed to get cost limits from DB: {e}. Using defaults.")

        return CostLimits(**DEFAULT_COST_LIMITS)

    def get_execution_limits(
        self,
        agent_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> ExecutionLimits:
        """
        Get execution limits for agent/provider from vega.llm_execution_limits.

        Falls back to global defaults if no specific limits found.
        """
        self.connect()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT max_llm_steps_per_task, max_total_latency_ms,
                           max_total_tokens_generated, abort_on_overrun,
                           agent_id, provider
                    FROM vega.llm_execution_limits
                    WHERE (agent_id = %s OR agent_id IS NULL)
                      AND (provider = %s OR provider IS NULL)
                      AND is_active = TRUE
                    ORDER BY
                        CASE WHEN agent_id IS NOT NULL AND provider IS NOT NULL THEN 1
                             WHEN agent_id IS NOT NULL THEN 2
                             WHEN provider IS NOT NULL THEN 3
                             ELSE 4 END
                    LIMIT 1
                """, (agent_id, provider))

                row = cur.fetchone()
                if row:
                    return ExecutionLimits(
                        max_llm_steps_per_task=row['max_llm_steps_per_task'],
                        max_total_latency_ms=row['max_total_latency_ms'],
                        max_total_tokens_generated=row['max_total_tokens_generated'],
                        abort_on_overrun=row['abort_on_overrun'],
                        agent_id=row['agent_id'],
                        provider=row['provider']
                    )
        except psycopg2.Error as e:
            logger.warning(f"Failed to get execution limits from DB: {e}. Using defaults.")

        return ExecutionLimits(**DEFAULT_EXECUTION_LIMITS)

    # =========================================================================
    # USAGE TRACKING
    # =========================================================================

    def get_agent_usage_today(self, agent_id: str) -> Dict[str, Any]:
        """
        Get today's usage statistics for an agent.

        Returns:
            Dict with call_count, total_cost_usd, total_tokens
        """
        self.connect()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS call_count,
                        COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                        COALESCE(SUM(tokens_in + tokens_out), 0) AS total_tokens
                    FROM vega.llm_usage_log
                    WHERE agent_id = %s
                      AND DATE(timestamp) = CURRENT_DATE
                """, (agent_id,))

                row = cur.fetchone()
                if row:
                    return {
                        'call_count': row['call_count'] or 0,
                        'total_cost_usd': Decimal(str(row['total_cost_usd'])),
                        'total_tokens': row['total_tokens'] or 0
                    }
        except psycopg2.Error as e:
            logger.warning(f"Failed to get agent usage: {e}")

        return {'call_count': 0, 'total_cost_usd': Decimal('0'), 'total_tokens': 0}

    def get_task_usage(self, task_id: str) -> Dict[str, Any]:
        """Get usage statistics for a specific task."""
        self.connect()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS call_count,
                        COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                        COALESCE(SUM(tokens_in + tokens_out), 0) AS total_tokens,
                        COALESCE(SUM(latency_ms), 0) AS total_latency_ms
                    FROM vega.llm_usage_log
                    WHERE task_id = %s
                """, (task_id,))

                row = cur.fetchone()
                if row:
                    return {
                        'call_count': row['call_count'] or 0,
                        'total_cost_usd': Decimal(str(row['total_cost_usd'])),
                        'total_tokens': row['total_tokens'] or 0,
                        'total_latency_ms': row['total_latency_ms'] or 0
                    }
        except psycopg2.Error as e:
            logger.warning(f"Failed to get task usage: {e}")

        return {
            'call_count': 0,
            'total_cost_usd': Decimal('0'),
            'total_tokens': 0,
            'total_latency_ms': 0
        }

    def get_global_usage_today(self) -> Dict[str, Any]:
        """Get today's global usage statistics."""
        self.connect()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) AS call_count,
                        COALESCE(SUM(cost_usd), 0) AS total_cost_usd
                    FROM vega.llm_usage_log
                    WHERE DATE(timestamp) = CURRENT_DATE
                """)

                row = cur.fetchone()
                if row:
                    return {
                        'call_count': row['call_count'] or 0,
                        'total_cost_usd': Decimal(str(row['total_cost_usd']))
                    }
        except psycopg2.Error as e:
            logger.warning(f"Failed to get global usage: {e}")

        return {'call_count': 0, 'total_cost_usd': Decimal('0')}

    def get_agent_calls_last_minute(self, agent_id: str) -> int:
        """Get number of calls by agent in the last minute."""
        self.connect()
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM vega.llm_usage_log
                    WHERE agent_id = %s
                      AND timestamp > NOW() - INTERVAL '1 minute'
                """, (agent_id,))
                return cur.fetchone()[0] or 0
        except psycopg2.Error as e:
            logger.warning(f"Failed to get agent calls last minute: {e}")
            return 0

    # =========================================================================
    # SAFETY CHECKS (The Core Enforcement Logic)
    # =========================================================================

    def check_rate_limits(
        self,
        agent_id: str,
        provider: Optional[str] = None,
        pipeline_call_count: int = 0
    ) -> SafetyCheckResult:
        """
        Check rate limits before an LLM call (ADR-012 Section 4.1).

        Args:
            agent_id: Agent making the call
            provider: LLM provider (optional)
            pipeline_call_count: Calls made in current pipeline execution

        Returns:
            SafetyCheckResult indicating if call is allowed
        """
        limits = self.get_rate_limits(agent_id, provider)

        # Check per-minute limit
        calls_last_minute = self.get_agent_calls_last_minute(agent_id)
        if calls_last_minute >= limits.max_calls_per_minute:
            violation = ViolationEvent(
                agent_id=agent_id,
                violation_type=ViolationType.RATE,
                violation_subtype='PER_MINUTE',
                governance_action=GovernanceAction.SWITCH_TO_STUB,
                severity=Severity.CLASS_B,
                provider=provider,
                limit_value=Decimal(limits.max_calls_per_minute),
                actual_value=Decimal(calls_last_minute),
                details={
                    'limit_type': 'max_calls_per_minute',
                    'window': '1 minute'
                }
            )
            self._record_violation(violation)
            return SafetyCheckResult(
                allowed=False,
                reason=f"Rate limit exceeded: {calls_last_minute}/{limits.max_calls_per_minute} calls/minute",
                mode=OperationMode.STUB,
                violation=violation
            )

        # Check per-pipeline limit
        if pipeline_call_count >= limits.max_calls_per_pipeline_execution:
            violation = ViolationEvent(
                agent_id=agent_id,
                violation_type=ViolationType.RATE,
                violation_subtype='PER_PIPELINE',
                governance_action=GovernanceAction.SWITCH_TO_STUB,
                severity=Severity.CLASS_B,
                provider=provider,
                limit_value=Decimal(limits.max_calls_per_pipeline_execution),
                actual_value=Decimal(pipeline_call_count),
                details={
                    'limit_type': 'max_calls_per_pipeline_execution'
                }
            )
            self._record_violation(violation)
            return SafetyCheckResult(
                allowed=False,
                reason=f"Pipeline limit exceeded: {pipeline_call_count}/{limits.max_calls_per_pipeline_execution} calls",
                mode=OperationMode.STUB,
                violation=violation
            )

        # Check global daily limit
        global_usage = self.get_global_usage_today()
        if global_usage['call_count'] >= limits.global_daily_limit:
            violation = ViolationEvent(
                agent_id=agent_id,
                violation_type=ViolationType.RATE,
                violation_subtype='GLOBAL_DAILY',
                governance_action=GovernanceAction.SWITCH_TO_STUB,
                severity=Severity.CLASS_A,  # Global violations are more severe
                provider=provider,
                limit_value=Decimal(limits.global_daily_limit),
                actual_value=Decimal(global_usage['call_count']),
                details={
                    'limit_type': 'global_daily_limit'
                }
            )
            self._record_violation(violation)
            return SafetyCheckResult(
                allowed=False,
                reason=f"Global daily limit exceeded: {global_usage['call_count']}/{limits.global_daily_limit}",
                mode=OperationMode.STUB,
                violation=violation
            )

        return SafetyCheckResult(
            allowed=True,
            reason="Rate limits OK",
            mode=OperationMode.LIVE
        )

    def check_cost_limits(
        self,
        agent_id: str,
        estimated_cost: Decimal,
        task_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> SafetyCheckResult:
        """
        Check cost limits before an LLM call (ADR-012 Section 4.2).

        Args:
            agent_id: Agent making the call
            estimated_cost: Estimated cost of the call in USD
            task_id: Task identifier (optional)
            provider: LLM provider (optional)

        Returns:
            SafetyCheckResult indicating if call is allowed
        """
        limits = self.get_cost_limits(agent_id, provider)
        agent_usage = self.get_agent_usage_today(agent_id)
        global_usage = self.get_global_usage_today()

        # Check global daily cost
        if global_usage['total_cost_usd'] + estimated_cost > limits.max_daily_cost:
            violation = ViolationEvent(
                agent_id=agent_id,
                violation_type=ViolationType.COST,
                violation_subtype='GLOBAL_DAILY',
                governance_action=GovernanceAction.SWITCH_TO_STUB,
                severity=Severity.CLASS_A,
                task_id=task_id,
                provider=provider,
                limit_value=limits.max_daily_cost,
                actual_value=global_usage['total_cost_usd'] + estimated_cost,
                details={
                    'limit_type': 'max_daily_cost',
                    'current_cost': float(global_usage['total_cost_usd']),
                    'estimated_cost': float(estimated_cost)
                }
            )
            self._record_violation(violation)
            return SafetyCheckResult(
                allowed=False,
                reason=f"Global daily cost exceeded: ${global_usage['total_cost_usd']:.2f} + ${estimated_cost:.2f} > ${limits.max_daily_cost:.2f}",
                mode=OperationMode.STUB,
                violation=violation
            )

        # Check agent daily cost
        if agent_usage['total_cost_usd'] + estimated_cost > limits.max_cost_per_agent_per_day:
            violation = ViolationEvent(
                agent_id=agent_id,
                violation_type=ViolationType.COST,
                violation_subtype='AGENT_DAILY',
                governance_action=GovernanceAction.SWITCH_TO_STUB,
                severity=Severity.CLASS_B,
                task_id=task_id,
                provider=provider,
                limit_value=limits.max_cost_per_agent_per_day,
                actual_value=agent_usage['total_cost_usd'] + estimated_cost,
                details={
                    'limit_type': 'max_cost_per_agent_per_day',
                    'current_cost': float(agent_usage['total_cost_usd']),
                    'estimated_cost': float(estimated_cost)
                }
            )
            self._record_violation(violation)
            return SafetyCheckResult(
                allowed=False,
                reason=f"Agent daily cost exceeded: ${agent_usage['total_cost_usd']:.2f} + ${estimated_cost:.2f} > ${limits.max_cost_per_agent_per_day:.2f}",
                mode=OperationMode.STUB,
                violation=violation
            )

        # Check task cost
        if task_id:
            task_usage = self.get_task_usage(task_id)
            if task_usage['total_cost_usd'] + estimated_cost > limits.max_cost_per_task:
                violation = ViolationEvent(
                    agent_id=agent_id,
                    violation_type=ViolationType.COST,
                    violation_subtype='TASK',
                    governance_action=GovernanceAction.SWITCH_TO_STUB,
                    severity=Severity.CLASS_B,
                    task_id=task_id,
                    provider=provider,
                    limit_value=limits.max_cost_per_task,
                    actual_value=task_usage['total_cost_usd'] + estimated_cost,
                    details={
                        'limit_type': 'max_cost_per_task',
                        'current_cost': float(task_usage['total_cost_usd']),
                        'estimated_cost': float(estimated_cost)
                    }
                )
                self._record_violation(violation)
                return SafetyCheckResult(
                    allowed=False,
                    reason=f"Task cost exceeded: ${task_usage['total_cost_usd']:.2f} + ${estimated_cost:.2f} > ${limits.max_cost_per_task:.2f}",
                    mode=OperationMode.STUB,
                    violation=violation
                )

        return SafetyCheckResult(
            allowed=True,
            reason="Cost limits OK",
            mode=OperationMode.LIVE
        )

    def check_execution_limits(
        self,
        agent_id: str,
        task_id: Optional[str] = None,
        provider: Optional[str] = None,
        current_steps: int = 0,
        current_latency_ms: int = 0,
        current_tokens: int = 0
    ) -> SafetyCheckResult:
        """
        Check execution limits for a task (ADR-012 Section 4.3).

        Args:
            agent_id: Agent executing the task
            task_id: Task identifier (optional)
            provider: LLM provider (optional)
            current_steps: Steps taken so far
            current_latency_ms: Cumulative latency so far
            current_tokens: Tokens generated so far

        Returns:
            SafetyCheckResult indicating if execution can continue
        """
        limits = self.get_execution_limits(agent_id, provider)

        # Check step limit
        if current_steps >= limits.max_llm_steps_per_task:
            violation = ViolationEvent(
                agent_id=agent_id,
                violation_type=ViolationType.EXECUTION,
                violation_subtype='STEPS_EXCEEDED',
                governance_action=GovernanceAction.SWITCH_TO_STUB,
                severity=Severity.CLASS_B,
                task_id=task_id,
                provider=provider,
                limit_value=Decimal(limits.max_llm_steps_per_task),
                actual_value=Decimal(current_steps),
                details={
                    'limit_type': 'max_llm_steps_per_task'
                }
            )
            self._record_violation(violation)
            return SafetyCheckResult(
                allowed=False,
                reason=f"Step limit exceeded: {current_steps}/{limits.max_llm_steps_per_task} steps",
                mode=OperationMode.STUB,
                violation=violation
            )

        # Check latency limit
        if current_latency_ms >= limits.max_total_latency_ms:
            violation = ViolationEvent(
                agent_id=agent_id,
                violation_type=ViolationType.EXECUTION,
                violation_subtype='LATENCY_EXCEEDED',
                governance_action=GovernanceAction.SWITCH_TO_STUB,
                severity=Severity.CLASS_B,
                task_id=task_id,
                provider=provider,
                limit_value=Decimal(limits.max_total_latency_ms),
                actual_value=Decimal(current_latency_ms),
                details={
                    'limit_type': 'max_total_latency_ms'
                }
            )
            self._record_violation(violation)
            return SafetyCheckResult(
                allowed=False,
                reason=f"Latency limit exceeded: {current_latency_ms}/{limits.max_total_latency_ms} ms",
                mode=OperationMode.STUB,
                violation=violation
            )

        # Check token limit (if configured)
        if limits.max_total_tokens_generated and current_tokens >= limits.max_total_tokens_generated:
            violation = ViolationEvent(
                agent_id=agent_id,
                violation_type=ViolationType.EXECUTION,
                violation_subtype='TOKENS_EXCEEDED',
                governance_action=GovernanceAction.SWITCH_TO_STUB,
                severity=Severity.CLASS_B,
                task_id=task_id,
                provider=provider,
                limit_value=Decimal(limits.max_total_tokens_generated),
                actual_value=Decimal(current_tokens),
                details={
                    'limit_type': 'max_total_tokens_generated'
                }
            )
            self._record_violation(violation)
            return SafetyCheckResult(
                allowed=False,
                reason=f"Token limit exceeded: {current_tokens}/{limits.max_total_tokens_generated}",
                mode=OperationMode.STUB,
                violation=violation
            )

        return SafetyCheckResult(
            allowed=True,
            reason="Execution limits OK",
            mode=OperationMode.LIVE
        )

    def check_all_limits(
        self,
        agent_id: str,
        estimated_cost: Decimal = Decimal('0.01'),
        provider: Optional[str] = None,
        task_id: Optional[str] = None,
        pipeline_call_count: int = 0,
        current_steps: int = 0,
        current_latency_ms: int = 0,
        current_tokens: int = 0
    ) -> SafetyCheckResult:
        """
        Comprehensive safety check before LLM call.

        Checks all three governance layers:
        1. Rate limits
        2. Cost limits
        3. Execution limits

        Returns first violation found, or success if all pass.
        """
        # Check rate limits first (cheapest check)
        rate_result = self.check_rate_limits(agent_id, provider, pipeline_call_count)
        if not rate_result.allowed:
            return rate_result

        # Check cost limits
        cost_result = self.check_cost_limits(agent_id, estimated_cost, task_id, provider)
        if not cost_result.allowed:
            return cost_result

        # Check execution limits
        exec_result = self.check_execution_limits(
            agent_id, task_id, provider,
            current_steps, current_latency_ms, current_tokens
        )
        if not exec_result.allowed:
            return exec_result

        return SafetyCheckResult(
            allowed=True,
            reason="All safety checks passed",
            mode=OperationMode.LIVE
        )

    # =========================================================================
    # USAGE LOGGING
    # =========================================================================

    def log_usage(self, record: UsageRecord) -> int:
        """
        Log LLM usage to vega.llm_usage_log.

        Returns:
            usage_id from database
        """
        self.connect()
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO vega.llm_usage_log (
                        agent_id, task_id, cycle_id, provider, model,
                        tokens_in, tokens_out, cost_usd, latency_ms,
                        mode, request_hash, response_hash, timestamp
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    RETURNING usage_id
                """, (
                    record.agent_id,
                    record.task_id,
                    record.cycle_id,
                    record.provider,
                    record.model,
                    record.tokens_in,
                    record.tokens_out,
                    float(record.cost_usd),
                    record.latency_ms,
                    record.mode.value,
                    record.request_hash,
                    record.response_hash,
                    record.timestamp
                ))

                usage_id = cur.fetchone()[0]
                self.conn.commit()

                logger.info(f"Logged LLM usage: agent={record.agent_id}, "
                           f"cost=${record.cost_usd:.4f}, mode={record.mode.value}")

                return usage_id
        except psycopg2.Error as e:
            self.conn.rollback()
            logger.error(f"Failed to log usage: {e}")
            raise

    # =========================================================================
    # VIOLATION RECORDING
    # =========================================================================

    def _compute_violation_hash(self, violation: ViolationEvent) -> str:
        """Compute SHA-256 hash for violation event chain (ADR-011)."""
        payload = json.dumps({
            'agent_id': violation.agent_id,
            'violation_type': violation.violation_type.value,
            'governance_action': violation.governance_action.value,
            'timestamp': violation.timestamp.isoformat(),
            'details': violation.details,
            'hash_prev': self._last_violation_hash or 'GENESIS'
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _record_violation(self, violation: ViolationEvent) -> int:
        """
        Record violation event to vega.llm_violation_events.

        Returns:
            violation_id from database
        """
        self.connect()

        # Compute hash for chain
        hash_self = self._compute_violation_hash(violation)

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO vega.llm_violation_events (
                        agent_id, task_id, cycle_id, provider,
                        violation_type, violation_subtype, governance_action,
                        severity, discrepancy_score, details,
                        limit_value, actual_value,
                        hash_prev, hash_self, timestamp
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s
                    )
                    RETURNING violation_id
                """, (
                    violation.agent_id,
                    violation.task_id,
                    violation.cycle_id,
                    violation.provider,
                    violation.violation_type.value,
                    violation.violation_subtype,
                    violation.governance_action.value,
                    violation.severity.value,
                    float(violation.discrepancy_score) if violation.discrepancy_score else None,
                    json.dumps(violation.details),
                    float(violation.limit_value) if violation.limit_value else None,
                    float(violation.actual_value) if violation.actual_value else None,
                    self._last_violation_hash,
                    hash_self,
                    violation.timestamp
                ))

                violation_id = cur.fetchone()[0]
                self.conn.commit()

                # Update chain
                self._last_violation_hash = hash_self

                logger.warning(
                    f"VIOLATION RECORDED: {violation.violation_type.value} - "
                    f"agent={violation.agent_id}, action={violation.governance_action.value}"
                )

                return violation_id
        except psycopg2.Error as e:
            self.conn.rollback()
            logger.error(f"Failed to record violation: {e}")
            raise

    # =========================================================================
    # QG-F6 QUALITY GATE (ADR-012 Section 6)
    # =========================================================================

    def check_qg_f6(self) -> QGF6Result:
        """
        Check QG-F6 Economic Safety Gate (ADR-012 Section 6).

        Gate passes if no rate, cost, or execution breaches in last 24 hours.

        Returns:
            QGF6Result with gate status and violation counts
        """
        self.connect()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM vega.check_qg_f6()")
                row = cur.fetchone()

                if row:
                    return QGF6Result(
                        gate_passed=row['gate_passed'],
                        rate_violations=row['rate_violations'],
                        cost_violations=row['cost_violations'],
                        execution_violations=row['execution_violations'],
                        last_violation_at=row['last_violation_at'],
                        check_timestamp=row['check_timestamp']
                    )
        except psycopg2.Error as e:
            logger.error(f"Failed to check QG-F6: {e}")

        # Default to failed if check fails
        return QGF6Result(
            gate_passed=False,
            rate_violations=-1,
            cost_violations=-1,
            execution_violations=-1,
            last_violation_at=None,
            check_timestamp=datetime.now(timezone.utc)
        )

    def can_enable_live_mode(self) -> Tuple[bool, str]:
        """
        Check if LIVE mode can be enabled (QG-F6 must pass).

        Returns:
            Tuple of (allowed, reason)
        """
        result = self.check_qg_f6()

        if not result.gate_passed:
            reasons = []
            if result.rate_violations > 0:
                reasons.append(f"{result.rate_violations} rate violation(s)")
            if result.cost_violations > 0:
                reasons.append(f"{result.cost_violations} cost violation(s)")
            if result.execution_violations > 0:
                reasons.append(f"{result.execution_violations} execution violation(s)")

            return False, f"QG-F6 FAILED: {', '.join(reasons) or 'Check failed'}"

        return True, "QG-F6 PASSED: No violations in last 24 hours"

    # =========================================================================
    # MODE CONTROL
    # =========================================================================

    def get_current_mode(self) -> OperationMode:
        """Get current global operation mode."""
        return self._global_mode

    def enable_live_mode(self, force: bool = False) -> Tuple[bool, str]:
        """
        Enable LIVE mode (requires QG-F6 pass).

        Args:
            force: If True, skip QG-F6 check (requires LARS authority)

        Returns:
            Tuple of (success, reason)
        """
        if not force:
            can_enable, reason = self.can_enable_live_mode()
            if not can_enable:
                return False, reason

        self._global_mode = OperationMode.LIVE
        logger.info("LIVE MODE ENABLED")
        return True, "LIVE mode enabled"

    def switch_to_stub_mode(self, reason: str = "Manual switch"):
        """Switch to STUB mode (always allowed)."""
        self._global_mode = OperationMode.STUB
        logger.warning(f"STUB MODE ACTIVATED: {reason}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_economic_safety_engine() -> EconomicSafetyEngine:
    """Factory function to create EconomicSafetyEngine with default config."""
    return EconomicSafetyEngine()


def estimate_llm_cost(
    provider: str,
    tokens_in: int,
    tokens_out: int
) -> Decimal:
    """
    Estimate LLM call cost based on provider pricing.

    Note: These are estimates. Actual costs should be tracked after calls.
    """
    # Approximate pricing per 1K tokens (as of 2025)
    PRICING = {
        'anthropic': {'input': 0.003, 'output': 0.015},   # Claude 3
        'openai': {'input': 0.01, 'output': 0.03},        # GPT-4
        'deepseek': {'input': 0.0001, 'output': 0.0005},  # DeepSeek
        'gemini': {'input': 0.00025, 'output': 0.0005},   # Gemini Pro
    }

    provider_key = provider.lower() if provider else 'anthropic'
    pricing = PRICING.get(provider_key, PRICING['anthropic'])

    input_cost = (tokens_in / 1000) * pricing['input']
    output_cost = (tokens_out / 1000) * pricing['output']

    return Decimal(str(round(input_cost + output_cost, 6)))


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == "__main__":
    print("Economic Safety Engine - ADR-012")
    print("=" * 50)

    # Test instantiation
    engine = EconomicSafetyEngine()
    print(f"Connection string: {engine.connection_string}")

    # Test QG-F6 check
    try:
        with engine:
            result = engine.check_qg_f6()
            print(f"\nQG-F6 Check:")
            print(f"  Gate passed: {result.gate_passed}")
            print(f"  Rate violations: {result.rate_violations}")
            print(f"  Cost violations: {result.cost_violations}")
            print(f"  Execution violations: {result.execution_violations}")

            # Test safety check
            print("\nSafety Check (FINN agent):")
            check = engine.check_all_limits(
                agent_id='FINN',
                estimated_cost=Decimal('0.01'),
                provider='anthropic'
            )
            print(f"  Allowed: {check.allowed}")
            print(f"  Mode: {check.mode.value}")
            print(f"  Reason: {check.reason}")
    except Exception as e:
        print(f"Error: {e}")
        print("(This is expected if database schema not yet applied)")
