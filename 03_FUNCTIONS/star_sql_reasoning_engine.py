"""
star_sql_reasoning_engine.py

CEO Directive: CEO-DIR-2026-ADR022-STARSQL-001
ADR Reference: ADR-022 (The Autonomous Database Horizon)
Owner: STIG (EC-003)
Classification: DB-Bound Execution Component

Purpose:
    Deterministic logging and control component for SQL refinement.
    Produces Structured Reasoning Artifacts, enforces hard ceilings,
    and writes to governance tables per ADR-022.

CONSTRAINTS (NON-NEGOTIABLE):
    - NO new schemas, NO new tables, NO ALTER TABLE
    - Writes ONLY to existing migrated tables
    - Hard ceilings enforced in behavior, not prose

DB CONTRACT (LIVE EXTRACTION 2026-01-04):

    PRIMARY WRITE: fhq_governance.sql_refinement_log
    Required NOT NULL: original_query, reasoning_artifact, reasoning_hash,
                       generated_sql, agent_id

    ESCALATION WRITE: fhq_governance.refinement_evidence_bundle
    Required NOT NULL: bundle_type, preservation_reason, preserved_by, raw_query
    bundle_type ENUM: 'ESCALATION', 'FORENSIC', 'G4_INCIDENT'

    BREAKER EVENT WRITE: fhq_governance.circuit_breaker_events
    Required NOT NULL: breaker_name, event_type, triggered_by

    GUIDELINE LOOKUP: fhq_governance.sql_correction_guidelines (read + usage update)

HARD CEILINGS (ADR-012 + ADR-016):
    - latency_budget_ms = 2000 (ADR-016 HIGH_LATENCY)
    - tokens_budget = 4000
    - cost_budget_usd = 0.02
    - max_attempts = 3
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# CONSTANTS (DB-GROUNDED, NO DRIFT)
# =============================================================================

# Hard ceilings - these are the law
LATENCY_BUDGET_MS = 2000
TOKENS_BUDGET = 4000
COST_BUDGET_USD = 0.02
MAX_ATTEMPTS = 3

# Registered breaker names (from fhq_governance.circuit_breakers)
BREAKER_SQL_REFINEMENT_FAILURE = "SQL_REFINEMENT_FAILURE"
BREAKER_SQL_REFINEMENT_LATENCY = "SQL_REFINEMENT_LATENCY"
BREAKER_SQL_REFINEMENT_TOKENS = "SQL_REFINEMENT_TOKENS"
BREAKER_SQL_REFINEMENT_COST = "SQL_REFINEMENT_COST"

# Bundle types (enum from DB constraint)
class BundleType(str, Enum):
    ESCALATION = "ESCALATION"
    FORENSIC = "FORENSIC"
    G4_INCIDENT = "G4_INCIDENT"

# Error taxonomy (from DB constraint)
class ErrorTaxonomy(str, Enum):
    SYNTAX = "SYNTAX"
    SEMANTIC = "SEMANTIC"
    JOIN_PATH = "JOIN_PATH"
    AGGREGATION = "AGGREGATION"
    NULL_EXPLOSION = "NULL_EXPLOSION"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    PERMISSION = "PERMISSION"
    TIMEOUT = "TIMEOUT"
    RESULT_MISMATCH = "RESULT_MISMATCH"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"  # For malformed artifacts

# Circuit state (from DB constraint)
class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

# Required artifact fields (validation gate)
REQUIRED_ARTIFACT_FIELDS = {
    "intent",
    "schema_elements",
    "join_plan",
    "filters",
    "aggregation_grain",
    "verification_steps",
    "risk_flags"
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ReasoningArtifact:
    """Structured Reasoning Artifact - NOT full CoT."""
    intent: str
    schema_elements: Dict[str, Any]  # {"tables": [], "columns": []}
    join_plan: str
    filters: list
    aggregation_grain: Optional[str]
    verification_steps: list
    risk_flags: list

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "schema_elements": self.schema_elements,
            "join_plan": self.join_plan,
            "filters": self.filters,
            "aggregation_grain": self.aggregation_grain,
            "verification_steps": self.verification_steps,
            "risk_flags": self.risk_flags
        }


@dataclass
class RefinementResult:
    """Result of a refinement attempt."""
    refinement_id: uuid.UUID
    generated_sql: str
    reasoning_artifact: Dict[str, Any]
    reasoning_hash: str
    success: bool
    semantic_check_passed: Optional[bool] = None
    semantic_check_details: Optional[Dict[str, Any]] = None
    error_taxonomy: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    tokens_consumed: Optional[int] = None
    cost_usd: Optional[float] = None
    escalated_to_human: bool = False
    escalation_bundle_id: Optional[uuid.UUID] = None


@dataclass
class Budgets:
    """Budget configuration - uses defaults from DB contract."""
    max_attempts: int = MAX_ATTEMPTS
    tokens_budget: int = TOKENS_BUDGET
    latency_budget_ms: int = LATENCY_BUDGET_MS
    cost_budget_usd: float = COST_BUDGET_USD


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def validate_reasoning_artifact(artifact: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate that reasoning artifact contains all required fields.

    Returns:
        (is_valid, error_message)
    """
    missing = REQUIRED_ARTIFACT_FIELDS - set(artifact.keys())
    if missing:
        return False, f"Missing required artifact fields: {sorted(missing)}"

    # Validate schema_elements structure
    schema_elements = artifact.get("schema_elements", {})
    if not isinstance(schema_elements, dict):
        return False, "schema_elements must be a dict"
    if "tables" not in schema_elements or "columns" not in schema_elements:
        return False, "schema_elements must contain 'tables' and 'columns'"

    # Validate list fields
    for field in ["filters", "verification_steps", "risk_flags"]:
        if not isinstance(artifact.get(field), list):
            return False, f"{field} must be a list"

    return True, None


def build_reasoning_artifact(
    intent: str,
    tables: list,
    columns: list,
    join_plan: str,
    filters: list,
    aggregation_grain: Optional[str],
    verification_steps: list,
    risk_flags: list
) -> Dict[str, Any]:
    """
    Build a Structured Reasoning Artifact.

    This is the canonical structure - no free-form narrative allowed.
    """
    artifact = ReasoningArtifact(
        intent=intent,
        schema_elements={"tables": tables, "columns": columns},
        join_plan=join_plan,
        filters=filters,
        aggregation_grain=aggregation_grain,
        verification_steps=verification_steps,
        risk_flags=risk_flags
    )
    return artifact.to_dict()


def hash_reasoning_artifact(artifact: Dict[str, Any]) -> str:
    """
    Compute SHA-256 hash of reasoning artifact.

    Uses canonical JSON serialization (sorted keys, no whitespace ambiguity).
    """
    canonical_json = json.dumps(artifact, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


def check_ceiling_breach(
    latency_ms: Optional[int],
    tokens_consumed: Optional[int],
    cost_usd: Optional[float],
    budgets: Budgets
) -> Dict[str, bool]:
    """
    Check if any hard ceiling has been breached.

    Returns dict of breach flags.
    """
    return {
        "latency_exceeded": latency_ms is not None and latency_ms > budgets.latency_budget_ms,
        "tokens_exceeded": tokens_consumed is not None and tokens_consumed > budgets.tokens_budget,
        "cost_exceeded": cost_usd is not None and cost_usd > budgets.cost_budget_usd
    }


def should_escalate(
    attempt_number: int,
    success: bool,
    artifact_valid: bool,
    breaches: Dict[str, bool],
    budgets: Budgets
) -> Tuple[bool, Optional[str]]:
    """
    Determine if escalation to human is required.

    Returns:
        (should_escalate, reason)
    """
    # Attempt ceiling breach
    if attempt_number >= budgets.max_attempts and not success:
        return True, f"Max attempts ({budgets.max_attempts}) exhausted without success"

    # Artifact corruption on first attempt
    if attempt_number == 1 and not artifact_valid:
        return True, "Artifact validation failed on first attempt - upstream corruption suspected"

    # Any budget breach
    if breaches.get("latency_exceeded"):
        return True, f"Latency ceiling breached ({budgets.latency_budget_ms}ms)"
    if breaches.get("tokens_exceeded"):
        return True, f"Token ceiling breached ({budgets.tokens_budget})"
    if breaches.get("cost_exceeded"):
        return True, f"Cost ceiling breached (${budgets.cost_budget_usd})"

    return False, None


# =============================================================================
# DATABASE WRITERS
# =============================================================================

def log_refinement_attempt(
    conn,
    original_query: str,
    reasoning_artifact: Dict[str, Any],
    reasoning_hash: str,
    generated_sql: str,
    agent_id: str,
    attempt_number: int = 1,
    query_intent: Optional[str] = None,
    generated_sql_hash: Optional[str] = None,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
    error_taxonomy: Optional[str] = None,
    correction_guideline_id: Optional[uuid.UUID] = None,
    refined_query: Optional[str] = None,
    tokens_consumed: Optional[int] = None,
    latency_ms: Optional[int] = None,
    cost_usd: Optional[float] = None,
    circuit_state: str = CircuitState.CLOSED.value,
    escalated_to_human: bool = False,
    escalation_bundle_id: Optional[uuid.UUID] = None,
    escalation_reason: Optional[str] = None,
    success: bool = False,
    execution_result_hash: Optional[str] = None,
    semantic_check_passed: Optional[bool] = None,
    semantic_check_details: Optional[Dict[str, Any]] = None,
    model_used: Optional[str] = None,
    prompt_template_version: Optional[str] = None,
    benchmark_run_id: Optional[uuid.UUID] = None
) -> uuid.UUID:
    """
    Write one row to fhq_governance.sql_refinement_log.

    This is the primary write operation - one row per attempt.

    Returns:
        refinement_id (UUID)
    """
    refinement_id = uuid.uuid4()

    sql = """
    INSERT INTO fhq_governance.sql_refinement_log (
        refinement_id,
        original_query,
        query_intent,
        reasoning_artifact,
        reasoning_hash,
        artifact_version,
        generated_sql,
        generated_sql_hash,
        error_message,
        error_type,
        error_taxonomy,
        correction_guideline_id,
        refined_query,
        attempt_number,
        tokens_consumed,
        latency_ms,
        cost_usd,
        circuit_state,
        escalated_to_human,
        escalation_bundle_id,
        escalation_reason,
        success,
        execution_result_hash,
        semantic_check_passed,
        semantic_check_details,
        agent_id,
        model_used,
        prompt_template_version,
        benchmark_run_id
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """

    cursor = conn.cursor()
    cursor.execute(sql, (
        str(refinement_id),
        original_query,
        query_intent,
        json.dumps(reasoning_artifact),
        reasoning_hash,
        1,  # artifact_version
        generated_sql,
        generated_sql_hash,
        error_message,
        error_type,
        error_taxonomy,
        str(correction_guideline_id) if correction_guideline_id else None,
        refined_query,
        attempt_number,
        tokens_consumed,
        latency_ms,
        cost_usd,
        circuit_state,
        escalated_to_human,
        str(escalation_bundle_id) if escalation_bundle_id else None,
        escalation_reason,
        success,
        execution_result_hash,
        semantic_check_passed,
        json.dumps(semantic_check_details) if semantic_check_details else None,
        agent_id,
        model_used,
        prompt_template_version,
        str(benchmark_run_id) if benchmark_run_id else None
    ))
    conn.commit()

    return refinement_id


def emit_breaker_event(
    conn,
    breaker_name: str,
    event_type: str,
    triggered_by: str,
    breaker_id: Optional[uuid.UUID] = None,
    defcon_before: Optional[str] = None,
    defcon_after: Optional[str] = None,
    trigger_data: Optional[Dict[str, Any]] = None,
    action_taken: Optional[Dict[str, Any]] = None
) -> uuid.UUID:
    """
    Write a circuit breaker event to fhq_governance.circuit_breaker_events.

    Use only registered breaker names:
        - SQL_REFINEMENT_FAILURE
        - SQL_REFINEMENT_LATENCY

    Returns:
        event_id (UUID)
    """
    event_id = uuid.uuid4()

    sql = """
    INSERT INTO fhq_governance.circuit_breaker_events (
        event_id,
        breaker_id,
        breaker_name,
        event_type,
        defcon_before,
        defcon_after,
        trigger_data,
        action_taken,
        triggered_by,
        event_timestamp
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """

    cursor = conn.cursor()
    cursor.execute(sql, (
        str(event_id),
        str(breaker_id) if breaker_id else None,
        breaker_name,
        event_type,
        defcon_before,
        defcon_after,
        json.dumps(trigger_data) if trigger_data else None,
        json.dumps(action_taken) if action_taken else None,
        triggered_by,
        datetime.now(timezone.utc)
    ))
    conn.commit()

    return event_id


def create_evidence_bundle(
    conn,
    bundle_type: str,
    preservation_reason: str,
    preserved_by: str,
    raw_query: str,
    refinement_id: Optional[uuid.UUID] = None,
    raw_cot_preserved: Optional[str] = None,
    query_result_hash: Optional[str] = None,
    query_result_snapshot: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    error_stack_trace: Optional[str] = None,
    governance_action_id: Optional[uuid.UUID] = None,
    defcon_level_at_creation: Optional[str] = None
) -> uuid.UUID:
    """
    Create an evidence bundle in fhq_governance.refinement_evidence_bundle.

    ONLY call this when escalated_to_human = true.

    bundle_type must be one of: 'ESCALATION', 'FORENSIC', 'G4_INCIDENT'

    Returns:
        bundle_id (UUID)
    """
    # Validate bundle_type
    valid_types = {BundleType.ESCALATION.value, BundleType.FORENSIC.value, BundleType.G4_INCIDENT.value}
    if bundle_type not in valid_types:
        raise ValueError(f"Invalid bundle_type: {bundle_type}. Must be one of {valid_types}")

    bundle_id = uuid.uuid4()

    sql = """
    INSERT INTO fhq_governance.refinement_evidence_bundle (
        bundle_id,
        bundle_type,
        preservation_reason,
        preserved_by,
        raw_cot_preserved,
        raw_query,
        query_result_hash,
        query_result_snapshot,
        error_message,
        error_stack_trace,
        refinement_id,
        governance_action_id,
        defcon_level_at_creation
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """

    cursor = conn.cursor()
    cursor.execute(sql, (
        str(bundle_id),
        bundle_type,
        preservation_reason,
        preserved_by,
        raw_cot_preserved,
        raw_query,
        query_result_hash,
        json.dumps(query_result_snapshot) if query_result_snapshot else None,
        error_message,
        error_stack_trace,
        str(refinement_id) if refinement_id else None,
        str(governance_action_id) if governance_action_id else None,
        defcon_level_at_creation
    ))
    conn.commit()

    return bundle_id


def lookup_correction_guideline(
    conn,
    error_pattern: str,
    error_taxonomy: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Look up a correction guideline by error pattern.

    Returns guideline dict or None if not found.
    """
    sql = """
    SELECT
        guideline_id,
        error_pattern,
        error_taxonomy,
        correction_template,
        correction_example,
        success_rate
    FROM fhq_governance.sql_correction_guidelines
    WHERE error_pattern = %s
    AND is_active = true
    """
    params = [error_pattern]

    if error_taxonomy:
        sql += " AND error_taxonomy = %s"
        params.append(error_taxonomy)

    sql += " ORDER BY success_rate DESC LIMIT 1"

    cursor = conn.cursor()
    cursor.execute(sql, params)
    row = cursor.fetchone()

    if row:
        return {
            "guideline_id": row[0],
            "error_pattern": row[1],
            "error_taxonomy": row[2],
            "correction_template": row[3],
            "correction_example": row[4],
            "success_rate": row[5]
        }
    return None


def update_guideline_usage(
    conn,
    guideline_id: uuid.UUID,
    was_successful: bool
) -> None:
    """
    Update usage statistics for a correction guideline.

    Increments usage_count, updates last_used_at, and adjusts success_rate.
    """
    sql = """
    UPDATE fhq_governance.sql_correction_guidelines
    SET
        usage_count = usage_count + 1,
        last_used_at = NOW(),
        success_rate = (
            (success_rate * usage_count + %s) / (usage_count + 1)
        ),
        updated_at = NOW()
    WHERE guideline_id = %s
    """

    cursor = conn.cursor()
    cursor.execute(sql, (1.0 if was_successful else 0.0, str(guideline_id)))
    conn.commit()


def get_breaker_id(conn, breaker_name: str) -> Optional[uuid.UUID]:
    """
    Look up breaker_id from fhq_governance.circuit_breakers.

    No local constants pretending to be IDs - always read from DB.
    """
    sql = """
    SELECT breaker_id FROM fhq_governance.circuit_breakers
    WHERE breaker_name = %s
    """
    cursor = conn.cursor()
    cursor.execute(sql, (breaker_name,))
    row = cursor.fetchone()
    return uuid.UUID(row[0]) if row else None


# =============================================================================
# ORCHESTRATION (SINGLE ATTEMPT)
# =============================================================================

def execute_refinement_attempt(
    conn,
    original_query: str,
    reasoning_artifact: Dict[str, Any],
    generated_sql: str,
    agent_id: str,
    attempt_number: int = 1,
    latency_ms: Optional[int] = None,
    tokens_consumed: Optional[int] = None,
    cost_usd: Optional[float] = None,
    success: bool = False,
    error_message: Optional[str] = None,
    error_taxonomy: Optional[str] = None,
    semantic_check_passed: Optional[bool] = None,
    semantic_check_details: Optional[Dict[str, Any]] = None,
    model_used: Optional[str] = None,
    prompt_template_version: Optional[str] = None,
    budgets: Optional[Budgets] = None
) -> RefinementResult:
    """
    Execute a single refinement attempt with full ceiling enforcement.

    This is the main entry point. It:
    1. Validates the reasoning artifact
    2. Checks for ceiling breaches
    3. Logs the attempt
    4. Emits breaker events if needed
    5. Creates evidence bundle if escalation required

    Returns:
        RefinementResult with all outcomes
    """
    if budgets is None:
        budgets = Budgets()

    # Step 1: Validate reasoning artifact
    artifact_valid, artifact_error = validate_reasoning_artifact(reasoning_artifact)
    if not artifact_valid:
        error_taxonomy = ErrorTaxonomy.ARTIFACT_INVALID.value
        error_message = artifact_error
        success = False

    # Step 2: Compute artifact hash
    reasoning_hash = hash_reasoning_artifact(reasoning_artifact)

    # Step 3: Check ceiling breaches
    breaches = check_ceiling_breach(latency_ms, tokens_consumed, cost_usd, budgets)

    # Step 4: Determine if escalation needed
    escalate, escalation_reason = should_escalate(
        attempt_number, success, artifact_valid, breaches, budgets
    )

    # Step 5: Determine circuit state
    circuit_state = CircuitState.CLOSED.value
    if breaches.get("latency_exceeded") or breaches.get("tokens_exceeded") or breaches.get("cost_exceeded"):
        circuit_state = CircuitState.OPEN.value

    # Step 6: Create evidence bundle if escalating
    escalation_bundle_id = None
    if escalate:
        escalation_bundle_id = create_evidence_bundle(
            conn=conn,
            bundle_type=BundleType.ESCALATION.value,
            preservation_reason=escalation_reason,
            preserved_by=agent_id,
            raw_query=original_query,
            error_message=error_message
        )

    # Step 7: Log the refinement attempt
    refinement_id = log_refinement_attempt(
        conn=conn,
        original_query=original_query,
        reasoning_artifact=reasoning_artifact,
        reasoning_hash=reasoning_hash,
        generated_sql=generated_sql,
        agent_id=agent_id,
        attempt_number=attempt_number,
        error_message=error_message,
        error_taxonomy=error_taxonomy,
        tokens_consumed=tokens_consumed,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        circuit_state=circuit_state,
        escalated_to_human=escalate,
        escalation_bundle_id=escalation_bundle_id,
        escalation_reason=escalation_reason,
        success=success,
        semantic_check_passed=semantic_check_passed,
        semantic_check_details=semantic_check_details,
        model_used=model_used,
        prompt_template_version=prompt_template_version
    )

    # Step 8: Emit breaker events for breaches
    # Rule: 1 breach -> 1 event. Multiple breaches in one attempt emit multiple events.
    if breaches.get("latency_exceeded"):
        breaker_id = get_breaker_id(conn, BREAKER_SQL_REFINEMENT_LATENCY)
        emit_breaker_event(
            conn=conn,
            breaker_name=BREAKER_SQL_REFINEMENT_LATENCY,
            event_type="TRIGGERED",  # DB constraint: TRIGGERED|RESET|OVERRIDE|ESCALATED
            triggered_by=agent_id,
            breaker_id=breaker_id,
            trigger_data={
                "ceiling": "LATENCY",
                "latency_ms": latency_ms,
                "latency_budget_ms": budgets.latency_budget_ms,
                "refinement_id": str(refinement_id)
            },
            action_taken={"circuit_state": circuit_state, "escalated": escalate}
        )

    if breaches.get("tokens_exceeded"):
        breaker_id = get_breaker_id(conn, BREAKER_SQL_REFINEMENT_TOKENS)
        emit_breaker_event(
            conn=conn,
            breaker_name=BREAKER_SQL_REFINEMENT_TOKENS,
            event_type="TRIGGERED",  # DB constraint: TRIGGERED|RESET|OVERRIDE|ESCALATED
            triggered_by=agent_id,
            breaker_id=breaker_id,
            trigger_data={
                "ceiling": "TOKENS",
                "tokens_consumed": tokens_consumed,
                "tokens_budget": budgets.tokens_budget,
                "refinement_id": str(refinement_id)
            },
            action_taken={"circuit_state": circuit_state, "escalated": escalate}
        )

    if breaches.get("cost_exceeded"):
        breaker_id = get_breaker_id(conn, BREAKER_SQL_REFINEMENT_COST)
        emit_breaker_event(
            conn=conn,
            breaker_name=BREAKER_SQL_REFINEMENT_COST,
            event_type="TRIGGERED",  # DB constraint: TRIGGERED|RESET|OVERRIDE|ESCALATED
            triggered_by=agent_id,
            breaker_id=breaker_id,
            trigger_data={
                "ceiling": "COST",
                "cost_usd": cost_usd,
                "cost_budget_usd": budgets.cost_budget_usd,
                "refinement_id": str(refinement_id)
            },
            action_taken={"circuit_state": circuit_state, "escalated": escalate}
        )

    if not success and attempt_number >= budgets.max_attempts:
        breaker_id = get_breaker_id(conn, BREAKER_SQL_REFINEMENT_FAILURE)
        emit_breaker_event(
            conn=conn,
            breaker_name=BREAKER_SQL_REFINEMENT_FAILURE,
            event_type="TRIGGERED",  # DB constraint: TRIGGERED|RESET|OVERRIDE|ESCALATED
            triggered_by=agent_id,
            breaker_id=breaker_id,
            trigger_data={
                "attempt_number": attempt_number,
                "max_attempts": budgets.max_attempts,
                "refinement_id": str(refinement_id)
            },
            action_taken={"circuit_state": circuit_state, "escalated": escalate}
        )

    # Return result
    return RefinementResult(
        refinement_id=refinement_id,
        generated_sql=generated_sql,
        reasoning_artifact=reasoning_artifact,
        reasoning_hash=reasoning_hash,
        success=success,
        semantic_check_passed=semantic_check_passed,
        semantic_check_details=semantic_check_details,
        error_taxonomy=error_taxonomy,
        error_message=error_message,
        latency_ms=latency_ms,
        tokens_consumed=tokens_consumed,
        cost_usd=cost_usd,
        escalated_to_human=escalate,
        escalation_bundle_id=escalation_bundle_id
    )
