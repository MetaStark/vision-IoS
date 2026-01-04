"""
star_sql_admission_controller.py

CEO Directive: CEO-DIR-2026-ADR022-STARSQL-CONCURRENCY-002-G0
ADR Reference: ADR-022 (The Autonomous Database Horizon)
Owner: STIG (EC-003)
Classification: Control-Plane Wrapper

Purpose:
    Single choke point for STAR SQL admission control.
    This module wraps the frozen STAR SQL engine (v1.0.1) and enforces:
    - Budget gate (daily spend from sql_refinement_log)
    - Circuit gate (event-derived state)
    - Dedup gate (query-based, no schema change)
    - Concurrency gate (process-level semaphore)

CONSTRAINTS (NON-NEGOTIABLE):
    - NO schema mutations
    - NO modifications to star_sql_reasoning_engine.py
    - Engine remains frozen at v1.0.1
    - Only writes to governance_actions_log

INTEGRATION MODEL:
    This is a WRAPPER, not advisory. All STAR SQL requests MUST go through:
        process_refinement_with_admission()

    Direct calls to star_sql_reasoning_engine.process_refinement_request()
    are considered out-of-policy outside of tests.

CEO-APPROVED QUERIES (from directive):
    - Budget: SUM(cost_usd) FROM sql_refinement_log WHERE date = today
    - Circuit: DISTINCT ON (breaker_name) FROM circuit_breaker_events ORDER BY created_at DESC
    - Dedup: EXISTS(original_query = X AND agent_id = Y AND date = today)
"""

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from enum import Enum


# =============================================================================
# CONSTANTS (CEO-APPROVED)
# =============================================================================

# Concurrency limits
MAX_CONCURRENT_REFINEMENTS = 3
SEMAPHORE_TIMEOUT_SECONDS = 5.0

# Query timeouts (seconds)
BUDGET_QUERY_TIMEOUT_SECONDS = 2.0
CIRCUIT_QUERY_TIMEOUT_SECONDS = 1.0
DEDUP_QUERY_TIMEOUT_SECONDS = 2.0

# Budget cap (from vega.llm_cost_limits global row)
# CEO Policy: Use $25/day until ADR-022 introduces dedicated SQL-refinement budget
DEFAULT_DAILY_BUDGET_CAP_USD = 25.00

# Per-agent soft partitions (CEO Policy Phase 1)
AGENT_BUDGET_PARTITIONS = {
    "FINN": 5.00,   # Existing vega.llm_cost_limits row
    "STIG": 10.00,  # Controller config per CEO directive
}

# Breaker names to check
SQL_REFINEMENT_BREAKERS = [
    "SQL_REFINEMENT_FAILURE",
    "SQL_REFINEMENT_LATENCY",
    "SQL_REFINEMENT_TOKENS",
    "SQL_REFINEMENT_COST",
]

# Controller version
CONTROLLER_VERSION = "1.0.0"
DIRECTIVE_ID = "CEO-DIR-2026-ADR022-STARSQL-CONCURRENCY-002-G0"


# =============================================================================
# REJECTION TAXONOMY (4 CODES)
# =============================================================================

class RejectionCode(str, Enum):
    BUDGET = "BUDGET"
    CIRCUIT = "CIRCUIT"
    DEDUP = "DEDUP"
    CONCURRENCY = "CONCURRENCY"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class AdmissionResult:
    """Result of admission check."""
    admitted: bool
    request_hash: str
    rejection_code: Optional[str] = None
    reason: str = ""
    risk_flag: Optional[str] = None  # For fail-open scenarios
    gates_checked: Dict[str, Any] = None

    def __post_init__(self):
        if self.gates_checked is None:
            self.gates_checked = {}


@dataclass
class RefinementResultWrapper:
    """Wrapper result that includes admission context."""
    success: bool
    request_hash: str
    admitted: bool
    rejection_code: Optional[str] = None
    error_message: Optional[str] = None
    refinement_result: Any = None  # The actual engine result if admitted
    risk_flag: Optional[str] = None


# =============================================================================
# PROCESS-LEVEL SEMAPHORE
# =============================================================================

_REFINEMENT_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_REFINEMENTS)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def compute_request_hash(original_query: str, agent_id: str) -> str:
    """
    Compute deterministic idempotency key.
    Format: sha256(query|agent|utc_date)[:64]
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = f"{original_query}|{agent_id}|{today}"
    return hashlib.sha256(payload.encode()).hexdigest()[:64]


def get_daily_budget_cap(agent_id: str) -> float:
    """
    Get budget cap for agent.
    Uses per-agent partition if defined, else global cap.
    """
    return AGENT_BUDGET_PARTITIONS.get(agent_id, DEFAULT_DAILY_BUDGET_CAP_USD)


# =============================================================================
# GATE FUNCTIONS
# =============================================================================

def check_budget_gate(conn, agent_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Budget gate: Check daily spend against cap.

    CEO-APPROVED QUERY:
        SELECT COALESCE(SUM(cost_usd), 0) AS spent_today_usd
        FROM fhq_governance.sql_refinement_log
        WHERE agent_id = $1 AND created_at::date = CURRENT_DATE;

    Returns: (passed, gate_details)
    """
    cap_usd = get_daily_budget_cap(agent_id)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(cost_usd), 0) AS spent_today_usd
                FROM fhq_governance.sql_refinement_log
                WHERE agent_id = %s
                  AND created_at::date = CURRENT_DATE
            """, (agent_id,))
            row = cur.fetchone()
            spent_usd = float(row[0]) if row else 0.0

        remaining_usd = cap_usd - spent_usd
        passed = remaining_usd >= 0.02  # At least one request's worth

        return passed, {
            "passed": passed,
            "spent_usd": spent_usd,
            "cap_usd": cap_usd,
            "remaining_usd": remaining_usd,
            "timeout": False
        }

    except Exception as e:
        # CEO POLICY: Hybrid fail-open with containment
        # Admit with risk flag, semaphore still applies
        return True, {
            "passed": True,
            "spent_usd": "UNKNOWN",
            "cap_usd": cap_usd,
            "remaining_usd": "UNKNOWN",
            "timeout": True,
            "error": str(e)
        }


def check_circuit_gate(conn, breaker_names: list = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Circuit gate: Check if any SQL_REFINEMENT breaker is OPEN.

    CEO-APPROVED QUERY:
        SELECT DISTINCT ON (breaker_name) breaker_name, event_type
        FROM fhq_governance.circuit_breaker_events
        WHERE breaker_name = $1
        ORDER BY breaker_name, created_at DESC;

    Returns: (passed, gate_details)
    """
    if breaker_names is None:
        breaker_names = SQL_REFINEMENT_BREAKERS

    states = {}

    try:
        with conn.cursor() as cur:
            for breaker_name in breaker_names:
                cur.execute("""
                    SELECT event_type
                    FROM fhq_governance.circuit_breaker_events
                    WHERE breaker_name = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (breaker_name,))
                row = cur.fetchone()

                if row is None:
                    # No events = CLOSED (never triggered)
                    states[breaker_name] = "CLOSED"
                elif row[0] == "TRIGGERED":
                    states[breaker_name] = "OPEN"
                else:
                    # RESET or OVERRIDE = CLOSED
                    states[breaker_name] = "CLOSED"

        # Any OPEN breaker blocks admission
        any_open = any(s == "OPEN" for s in states.values())
        passed = not any_open

        return passed, {
            "passed": passed,
            "breakers_checked": breaker_names,
            "states": states,
            "timeout": False
        }

    except Exception as e:
        # CEO POLICY: Hybrid fail-open with containment
        return True, {
            "passed": True,
            "breakers_checked": breaker_names,
            "states": {"error": str(e)},
            "timeout": True,
            "error": str(e)
        }


def check_dedup_gate(conn, original_query: str, agent_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Dedup gate: Check if same query was already processed today.

    CEO-APPROVED QUERY:
        SELECT EXISTS (
            SELECT 1 FROM fhq_governance.sql_refinement_log
            WHERE agent_id = $1 AND created_at::date = CURRENT_DATE AND original_query = $2
        ) as already_processed;

    Returns: (passed, gate_details)
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT refinement_id
                FROM fhq_governance.sql_refinement_log
                WHERE agent_id = %s
                  AND created_at::date = CURRENT_DATE
                  AND original_query = %s
                LIMIT 1
            """, (agent_id, original_query))
            row = cur.fetchone()

        if row:
            # Already processed today
            return False, {
                "passed": False,
                "existing_refinement_id": str(row[0]),
                "timeout": False
            }
        else:
            return True, {
                "passed": True,
                "existing_refinement_id": None,
                "timeout": False
            }

    except Exception as e:
        # CEO POLICY: Hybrid fail-open with containment
        return True, {
            "passed": True,
            "existing_refinement_id": "UNKNOWN",
            "timeout": True,
            "error": str(e)
        }


def check_concurrency_gate() -> Tuple[bool, Dict[str, Any]]:
    """
    Concurrency gate: Attempt to acquire semaphore.

    Returns: (passed, gate_details)

    NOTE: If passed=True, the semaphore is ACQUIRED and caller MUST release it.
    """
    import time
    start = time.time()

    acquired = _REFINEMENT_SEMAPHORE.acquire(timeout=SEMAPHORE_TIMEOUT_SECONDS)
    elapsed_ms = int((time.time() - start) * 1000)

    if acquired:
        return True, {
            "passed": True,
            "acquired_at_ms": elapsed_ms,
            "timeout": False
        }
    else:
        return False, {
            "passed": False,
            "acquired_at_ms": None,
            "timeout": True,
            "waited_ms": elapsed_ms
        }


def release_concurrency_gate():
    """Release the semaphore after refinement completes."""
    _REFINEMENT_SEMAPHORE.release()


# =============================================================================
# GOVERNANCE LOGGING
# =============================================================================

def log_admission_decision(
    conn,
    admitted: bool,
    agent_id: str,
    request_hash: str,
    rejection_code: Optional[str],
    gates_checked: Dict[str, Any],
    risk_flag: Optional[str] = None,
    original_query_preview: str = ""
):
    """
    Log admission decision to governance_actions_log.

    CEO-APPROVED SCHEMA:
        action_type: STARSQL_ADMISSION_REJECTED | STARSQL_ADMISSION_GRANTED
        decision: REJECTED | ADMITTED
        metadata: {request_hash, rejection_code, gates_checked, ...}
    """
    action_type = "STARSQL_ADMISSION_GRANTED" if admitted else "STARSQL_ADMISSION_REJECTED"
    decision = "ADMITTED" if admitted else "REJECTED"

    # Build deterministic metadata payload
    metadata = {
        "request_hash": request_hash,
        "rejection_code": rejection_code,
        "gates_checked": gates_checked,
        "original_query_preview": original_query_preview[:100] if original_query_preview else "",
        "controller_version": CONTROLLER_VERSION,
        "directive_id": DIRECTIVE_ID
    }

    if risk_flag:
        metadata["risk_flag"] = risk_flag

    rationale = f"Rejection: {rejection_code}" if rejection_code else "All gates passed"
    if risk_flag:
        rationale += f" (RISK: {risk_flag})"

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log
                (action_id, action_type, action_target, action_target_type,
                 initiated_by, initiated_at, decision, decision_rationale,
                 metadata, agent_id, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                action_type,
                "sql_refinement_request",
                "REFINEMENT",
                "star_sql_admission_controller",
                datetime.now(timezone.utc),
                decision,
                rationale,
                json.dumps(metadata),
                agent_id,
                datetime.now(timezone.utc)
            ))
        conn.commit()
    except Exception as e:
        # Log failure should not block admission
        import logging
        logging.getLogger("STARSQL_ADMISSION").error(f"Failed to log admission: {e}")


# =============================================================================
# MAIN ADMISSION FUNCTION
# =============================================================================

def admit_refinement_request(
    conn,
    original_query: str,
    agent_id: str
) -> AdmissionResult:
    """
    Pre-admission gate. Must be called BEFORE any LLM invocation.

    Gate order (CEO-approved):
        1. Budget (cheapest check)
        2. Circuit (event-derived)
        3. Dedup (requires text comparison)
        4. Concurrency (blocking)

    Returns: AdmissionResult with admitted status and details.
    """
    request_hash = compute_request_hash(original_query, agent_id)
    gates_checked = {}
    risk_flag = None

    # Gate 1: Budget
    budget_passed, budget_details = check_budget_gate(conn, agent_id)
    gates_checked["budget"] = budget_details

    if budget_details.get("timeout"):
        risk_flag = "DB_TIMEOUT_FAIL_OPEN"

    if not budget_passed:
        result = AdmissionResult(
            admitted=False,
            request_hash=request_hash,
            rejection_code=RejectionCode.BUDGET.value,
            reason=f"Daily budget exhausted: ${budget_details.get('spent_usd', 0):.4f} spent of ${budget_details.get('cap_usd', 0):.2f} cap",
            gates_checked=gates_checked
        )
        log_admission_decision(conn, False, agent_id, request_hash,
                               RejectionCode.BUDGET.value, gates_checked,
                               original_query_preview=original_query)
        return result

    # Gate 2: Circuit
    circuit_passed, circuit_details = check_circuit_gate(conn)
    gates_checked["circuit"] = circuit_details

    if circuit_details.get("timeout"):
        risk_flag = "DB_TIMEOUT_FAIL_OPEN"

    if not circuit_passed:
        open_breakers = [k for k, v in circuit_details.get("states", {}).items() if v == "OPEN"]
        result = AdmissionResult(
            admitted=False,
            request_hash=request_hash,
            rejection_code=RejectionCode.CIRCUIT.value,
            reason=f"Circuit breaker(s) OPEN: {', '.join(open_breakers)}",
            gates_checked=gates_checked
        )
        log_admission_decision(conn, False, agent_id, request_hash,
                               RejectionCode.CIRCUIT.value, gates_checked,
                               original_query_preview=original_query)
        return result

    # Gate 3: Dedup
    dedup_passed, dedup_details = check_dedup_gate(conn, original_query, agent_id)
    gates_checked["dedup"] = dedup_details

    if dedup_details.get("timeout"):
        risk_flag = "DB_TIMEOUT_FAIL_OPEN"

    if not dedup_passed:
        result = AdmissionResult(
            admitted=False,
            request_hash=request_hash,
            rejection_code=RejectionCode.DEDUP.value,
            reason=f"Duplicate request: already processed as {dedup_details.get('existing_refinement_id')}",
            gates_checked=gates_checked
        )
        log_admission_decision(conn, False, agent_id, request_hash,
                               RejectionCode.DEDUP.value, gates_checked,
                               original_query_preview=original_query)
        return result

    # Gate 4: Concurrency
    concurrency_passed, concurrency_details = check_concurrency_gate()
    gates_checked["concurrency"] = concurrency_details

    if not concurrency_passed:
        result = AdmissionResult(
            admitted=False,
            request_hash=request_hash,
            rejection_code=RejectionCode.CONCURRENCY.value,
            reason=f"Concurrency limit reached: waited {concurrency_details.get('waited_ms', 0)}ms",
            gates_checked=gates_checked
        )
        log_admission_decision(conn, False, agent_id, request_hash,
                               RejectionCode.CONCURRENCY.value, gates_checked,
                               original_query_preview=original_query)
        return result

    # All gates passed - ADMITTED
    # NOTE: Semaphore is acquired and must be released after refinement
    result = AdmissionResult(
        admitted=True,
        request_hash=request_hash,
        rejection_code=None,
        reason="All gates passed",
        risk_flag=risk_flag,
        gates_checked=gates_checked
    )

    log_admission_decision(conn, True, agent_id, request_hash,
                           None, gates_checked, risk_flag=risk_flag,
                           original_query_preview=original_query)

    return result


# =============================================================================
# WRAPPER FUNCTION (SINGLE ENTRY POINT)
# =============================================================================

def process_refinement_with_admission(
    conn,
    original_query: str,
    agent_id: str,
    **engine_kwargs
) -> RefinementResultWrapper:
    """
    MANDATORY WRAPPER for STAR SQL execution.

    This is the ONLY supported entry point for STAR SQL in normal operation.
    Direct calls to star_sql_reasoning_engine.execute_refinement_attempt()
    are out-of-policy outside of tests.

    ARCHITECTURE (CEO-confirmed):
        Caller -> Admission Controller -> LLM Call -> Engine (log+enforce)

        The engine is LOG+ENFORCE only, not a generator.
        This wrapper gates the LLM caller, then invokes the engine with results.

    Args:
        conn: Database connection
        original_query: The natural language query to process
        agent_id: The calling agent ID (e.g., 'FINN', 'STIG')
        **engine_kwargs: Additional arguments:
            - use_mock (bool): If True, use mock LLM values (for G2 canary)
            - reasoning_artifact (dict): Pre-built artifact (production)
            - generated_sql (str): Pre-generated SQL (production)
            - latency_ms, tokens_consumed, cost_usd: Measured metrics (production)

    Returns:
        RefinementResultWrapper with admission context and engine result
    """
    # Step 1: Check admission
    admission = admit_refinement_request(conn, original_query, agent_id)

    if not admission.admitted:
        return RefinementResultWrapper(
            success=False,
            request_hash=admission.request_hash,
            admitted=False,
            rejection_code=admission.rejection_code,
            error_message=admission.reason,
            risk_flag=admission.risk_flag
        )

    # Step 2: Admitted - perform LLM call (or mock for testing) then log via engine
    # NOTE: Semaphore was acquired in admission check
    try:
        # Import here to avoid circular dependency and emphasize separation
        from star_sql_reasoning_engine import execute_refinement_attempt

        # CEO-APPROVED G2 CANARY: Use mock values for controlled testing
        # In production, this would be replaced with actual LLM call
        # Architecture: Admission gates LLM caller, engine logs+enforces

        # Check if mock mode requested (for G2 canary)
        use_mock = engine_kwargs.pop('use_mock', False)

        if use_mock:
            # G2 CANARY: Deterministic mock values per CEO directive
            mock_reasoning_artifact = {
                "intent": f"Mock query analysis for: {original_query[:50]}",
                "schema_elements": {"tables": ["mock_table"], "columns": ["mock_col"]},
                "join_plan": "No joins required (mock)",
                "filters": [],
                "aggregation_grain": None,
                "verification_steps": ["Mock verification"],
                "risk_flags": []
            }
            mock_generated_sql = f"-- MOCK SQL for canary test\nSELECT 1 AS canary_result;"
            mock_latency_ms = 10
            mock_tokens_consumed = 100
            mock_cost_usd = 0.001
            mock_success = True

            engine_result = execute_refinement_attempt(
                conn=conn,
                original_query=original_query,
                reasoning_artifact=mock_reasoning_artifact,
                generated_sql=mock_generated_sql,
                agent_id=agent_id,
                attempt_number=1,
                latency_ms=mock_latency_ms,
                tokens_consumed=mock_tokens_consumed,
                cost_usd=mock_cost_usd,
                success=mock_success,
                model_used="mock-canary-v1",
                prompt_template_version="canary-1.0"
            )
        else:
            # PRODUCTION PATH: Caller must provide LLM results via engine_kwargs
            # Required: reasoning_artifact, generated_sql, latency_ms, tokens_consumed, cost_usd
            engine_result = execute_refinement_attempt(
                conn=conn,
                original_query=original_query,
                agent_id=agent_id,
                **engine_kwargs
            )

        return RefinementResultWrapper(
            success=engine_result.success if hasattr(engine_result, 'success') else True,
            request_hash=admission.request_hash,
            admitted=True,
            refinement_result=engine_result,
            risk_flag=admission.risk_flag
        )

    except Exception as e:
        return RefinementResultWrapper(
            success=False,
            request_hash=admission.request_hash,
            admitted=True,
            error_message=f"Engine error: {str(e)}",
            risk_flag=admission.risk_flag
        )

    finally:
        # CRITICAL: Always release semaphore
        release_concurrency_gate()


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("STAR SQL ADMISSION CONTROLLER - Self Test")
    print(f"Version: {CONTROLLER_VERSION}")
    print(f"Directive: {DIRECTIVE_ID}")
    print("=" * 60)

    print("\n1. Constants:")
    print(f"   MAX_CONCURRENT_REFINEMENTS: {MAX_CONCURRENT_REFINEMENTS}")
    print(f"   SEMAPHORE_TIMEOUT_SECONDS: {SEMAPHORE_TIMEOUT_SECONDS}")
    print(f"   DEFAULT_DAILY_BUDGET_CAP_USD: ${DEFAULT_DAILY_BUDGET_CAP_USD}")
    print(f"   AGENT_BUDGET_PARTITIONS: {AGENT_BUDGET_PARTITIONS}")

    print("\n2. Request Hash Test:")
    test_hash = compute_request_hash("SELECT * FROM test", "STIG")
    print(f"   Hash: {test_hash}")

    print("\n3. Rejection Codes:")
    for code in RejectionCode:
        print(f"   {code.name}: {code.value}")

    print("\n4. Breakers to check:")
    for breaker in SQL_REFINEMENT_BREAKERS:
        print(f"   - {breaker}")

    print("\n" + "=" * 60)
    print("Self-test complete (no DB connection)")
    print("=" * 60)
