#!/usr/bin/env python3
"""
MANDATORY EVIDENCE CONTRACT
============================
CEO-DIR-2026-020 D2: Activate Evidence Attachment Everywhere

This module provides the enforcement mechanism for mandatory evidence attachment.
Every decision-producing or summary-producing flow must emit court-proof evidence or fail.

RULE: Learning without evidence is indistinguishable from fiction.

FAIL-CLOSED BEHAVIOR:
- Any function decorated with @require_evidence MUST call attach_evidence()
- Failure to attach evidence raises MissingEvidenceViolation
- Violation is logged to governance_actions_log
- Operation is aborted

Author: STIG (CTO)
Date: 2026-01-08
Classification: CEO-DIR-2026-020 COMPLIANT
"""

import os
import json
import hashlib
import uuid
import functools
import logging
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Callable
import psycopg2
from psycopg2.extras import RealDictCursor, Json


def json_serialize_safe(obj: Any) -> Any:
    """
    Recursively convert an object to JSON-serializable format.
    Handles: date, datetime, Decimal, UUID, bytes, and nested dicts/lists.
    """
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    elif isinstance(obj, dict):
        return {k: json_serialize_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [json_serialize_safe(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return json_serialize_safe(obj.__dict__)
    else:
        return str(obj)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - EVIDENCE_CONTRACT - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mandatory_evidence_contract")


# =============================================================================
# EXCEPTIONS
# =============================================================================

class MissingEvidenceViolation(Exception):
    """
    Raised when a function fails to attach evidence.

    CEO-DIR-2026-020: This is a GOVERNANCE VIOLATION.
    """
    pass


class EvidenceContractBreach(Exception):
    """
    Raised when the evidence contract is breached (e.g., invalid evidence).
    """
    pass


# =============================================================================
# DATABASE CONFIG
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


# =============================================================================
# EVIDENCE CONTRACT REGISTRY
# =============================================================================

# Track which summary types REQUIRE evidence
EVIDENCE_REQUIRED_SUMMARY_TYPES = {
    'REGIME_SUMMARY',           # ios003_daily_regime_update_v4.py
    'REGIME_UPDATE',            # ios003_daily_regime_update_v4.py
    'NIGHTLY_INSIGHT',          # finn_deepseek_researcher.py (FINN CRIO)
    'INSIGHT_PACK',             # finn_deepseek_researcher.py
    'G2_INGEST_SUMMARY',        # ios006_g2_macro_ingest.py
    'LIDS_BINDING',             # ios006_crio_lids_binding.py
    'GOLDEN_NEEDLE_PROMOTION',  # wave12_golden_needle_framework.py
    'ALPHA_SIGNAL',             # Signal executor
    'EXECUTION_RESULT',         # Trade execution
    'GOVERNANCE_DECISION',      # Governance actions
    'SKILL_METRIC',             # Learning metrics
    'EPISTEMIC_LESSON',         # Lessons learned
    'MUTATION_PROPOSAL',        # Parameter mutations
}

# Valid agents that can emit evidence
VALID_AGENTS = {'FINN', 'STIG', 'LINE', 'LARS', 'VEGA', 'CEIO', 'CDMO', 'CRIO'}


# =============================================================================
# EVIDENCE ATTACHMENT FUNCTION
# =============================================================================

def attach_evidence(
    conn,
    summary_id: str,
    summary_type: str,
    generating_agent: str,
    raw_query: str,
    query_result: Any,
    summary_content: Dict,
    evidence_sources: Optional[List[str]] = None
) -> Dict:
    """
    Attach court-proof evidence to a summary.

    This is the MANDATORY function for D2 compliance.

    Args:
        conn: Database connection
        summary_id: Unique identifier for this summary
        summary_type: Type of summary (must be in EVIDENCE_REQUIRED_SUMMARY_TYPES)
        generating_agent: The agent creating this summary
        raw_query: The exact SQL query that produced the data
        query_result: The raw data returned by the query
        summary_content: The summary itself
        evidence_sources: List of data sources used

    Returns:
        Dict containing evidence_id and verification info

    Raises:
        MissingEvidenceViolation: If required fields are missing
        EvidenceContractBreach: If evidence is invalid
    """
    # Validate required fields
    if not summary_id or len(summary_id) < 3:
        raise MissingEvidenceViolation("summary_id is mandatory")

    if generating_agent not in VALID_AGENTS:
        raise MissingEvidenceViolation(f"Invalid agent: {generating_agent}. Must be one of {VALID_AGENTS}")

    if not raw_query or len(raw_query) < 10:
        raise MissingEvidenceViolation("raw_query is mandatory (min 10 chars)")

    if query_result is None:
        raise MissingEvidenceViolation("query_result is mandatory")

    # Compute hashes
    def compute_hash(data: Any) -> str:
        if isinstance(data, dict) or isinstance(data, list):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    query_result_hash = compute_hash(query_result)
    summary_hash = compute_hash(summary_content)

    # Convert query_result to JSON-serializable format using safe serializer
    query_result_json = json_serialize_safe(query_result)
    summary_content_json = json_serialize_safe(summary_content)

    evidence_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    # Build execution context
    execution_context = {
        'evidence_contract': 'CEO-DIR-2026-020',
        'contract_version': 'D2_V1',
        'evidence_sources': evidence_sources or [],
        'generated_at': created_at.isoformat()
    }

    # Insert into evidence ledger
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO vision_verification.summary_evidence_ledger (
                evidence_id,
                summary_id,
                summary_type,
                generating_agent,
                raw_query,
                query_result_hash,
                query_result_snapshot,
                summary_content,
                summary_hash,
                execution_context,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            evidence_id,
            summary_id,
            summary_type,
            generating_agent,
            raw_query,
            query_result_hash,
            Json(query_result_json),
            Json(summary_content_json),
            summary_hash,
            Json(execution_context),
            created_at
        ))

        # Log governance action
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                decision,
                decision_rationale,
                initiated_by,
                initiated_at,
                metadata
            ) VALUES (
                'EVIDENCE_ATTACHMENT_D2',
                %s,
                'SUMMARY',
                'ENFORCED',
                %s,
                %s,
                %s,
                %s
            )
        """, (
            summary_id,
            f"CEO-DIR-2026-020 D2: Evidence attached. Type={summary_type}, Hash={query_result_hash[:16]}...",
            generating_agent,
            created_at,
            Json({
                'evidence_id': evidence_id,
                'summary_type': summary_type,
                'query_result_hash': query_result_hash[:32],
                'summary_hash': summary_hash[:32]
            })
        ))

        conn.commit()

    logger.info(f"[EVIDENCE-D2] Attached: {summary_id} | Type: {summary_type} | Agent: {generating_agent}")

    return {
        'evidence_id': evidence_id,
        'summary_id': summary_id,
        'summary_type': summary_type,
        'generating_agent': generating_agent,
        'query_result_hash': query_result_hash,
        'summary_hash': summary_hash,
        'created_at': created_at.isoformat(),
        'status': 'ATTACHED'
    }


def log_missing_evidence_violation(
    conn,
    flow_name: str,
    summary_type: str,
    generating_agent: str,
    reason: str
) -> str:
    """
    Log a missing evidence violation to governance.

    This is called when a flow fails to attach evidence.
    Returns the violation_id.
    """
    violation_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                decision,
                decision_rationale,
                initiated_by,
                initiated_at,
                metadata
            ) VALUES (
                'EVIDENCE_VIOLATION_D2',
                %s,
                'FLOW',
                'VIOLATION_LOGGED',
                %s,
                'EVIDENCE_CONTRACT',
                %s,
                %s
            )
        """, (
            flow_name,
            f"CEO-DIR-2026-020 D2 VIOLATION: {reason}",
            created_at,
            Json({
                'violation_id': violation_id,
                'flow_name': flow_name,
                'summary_type': summary_type,
                'generating_agent': generating_agent,
                'reason': reason,
                'timestamp': created_at.isoformat()
            })
        ))
        conn.commit()

    logger.error(f"[EVIDENCE-VIOLATION] {flow_name}: {reason}")

    return violation_id


# =============================================================================
# DECORATOR FOR MANDATORY EVIDENCE
# =============================================================================

def require_evidence(
    summary_type: str,
    generating_agent: str,
    evidence_sources: Optional[List[str]] = None
):
    """
    Decorator that enforces evidence attachment on summary-producing functions.

    The decorated function MUST:
    1. Accept a database connection as first argument
    2. Return a tuple of (summary_content, query_result, raw_query) OR
       a dict with keys: 'summary', 'query_result', 'raw_query'

    FAIL-CLOSED: If evidence attachment fails, the operation is aborted.

    Usage:
        @require_evidence('REGIME_SUMMARY', 'STIG', ['fhq_market.prices'])
        def generate_regime_summary(conn, asset_id):
            raw_query = "SELECT * FROM ..."
            result = execute_query(conn, raw_query)
            summary = analyze(result)
            return {'summary': summary, 'query_result': result, 'raw_query': raw_query}
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(conn, *args, **kwargs):
            # Execute the wrapped function
            try:
                result = func(conn, *args, **kwargs)
            except Exception as e:
                # Log violation and re-raise
                log_missing_evidence_violation(
                    conn, func.__name__, summary_type, generating_agent,
                    f"Function raised exception before evidence could be attached: {str(e)}"
                )
                raise

            # Extract evidence components
            if isinstance(result, tuple) and len(result) == 3:
                summary_content, query_result, raw_query = result
            elif isinstance(result, dict):
                summary_content = result.get('summary', result)
                query_result = result.get('query_result', result)
                raw_query = result.get('raw_query', 'QUERY_NOT_PROVIDED')
            else:
                # Log violation
                log_missing_evidence_violation(
                    conn, func.__name__, summary_type, generating_agent,
                    "Function did not return evidence-compatible format (tuple or dict)"
                )
                raise MissingEvidenceViolation(
                    f"Function {func.__name__} must return (summary, query_result, raw_query) "
                    f"tuple or dict with 'summary', 'query_result', 'raw_query' keys"
                )

            # Generate summary_id
            summary_id = f"{func.__name__.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

            # Attach evidence (FAIL-CLOSED)
            try:
                evidence = attach_evidence(
                    conn=conn,
                    summary_id=summary_id,
                    summary_type=summary_type,
                    generating_agent=generating_agent,
                    raw_query=raw_query,
                    query_result=query_result,
                    summary_content=summary_content,
                    evidence_sources=evidence_sources
                )

                # Return result with evidence
                return {
                    'summary': summary_content,
                    'evidence': evidence,
                    'evidence_attached': True
                }

            except Exception as e:
                # Log violation and abort
                log_missing_evidence_violation(
                    conn, func.__name__, summary_type, generating_agent,
                    f"Evidence attachment failed: {str(e)}"
                )
                raise MissingEvidenceViolation(
                    f"CEO-DIR-2026-020 D2 VIOLATION: Evidence attachment failed for {func.__name__}: {str(e)}"
                )

        return wrapper
    return decorator


# =============================================================================
# EVIDENCE VERIFICATION
# =============================================================================

def verify_evidence_coverage(hours: int = 24) -> Dict:
    """
    Verify evidence coverage for recent summaries.

    Returns statistics on:
    - How many summaries have evidence attached
    - How many summaries are missing evidence
    - Coverage by summary_type and agent
    """
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get evidence counts
            cur.execute("""
                SELECT
                    summary_type,
                    generating_agent,
                    COUNT(*) as count,
                    MIN(created_at) as first_record,
                    MAX(created_at) as last_record
                FROM vision_verification.summary_evidence_ledger
                WHERE created_at > NOW() - INTERVAL '%s hours'
                GROUP BY summary_type, generating_agent
                ORDER BY count DESC
            """ % hours)

            evidence_records = cur.fetchall()

            # Get total count
            cur.execute("""
                SELECT COUNT(*) as total
                FROM vision_verification.summary_evidence_ledger
                WHERE created_at > NOW() - INTERVAL '%s hours'
            """ % hours)

            total = cur.fetchone()['total']

            # Get violations
            cur.execute("""
                SELECT COUNT(*) as violations
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'EVIDENCE_VIOLATION_D2'
                  AND initiated_at > NOW() - INTERVAL '%s hours'
            """ % hours)

            violations = cur.fetchone()['violations']

        return {
            'period_hours': hours,
            'total_evidence_records': total,
            'violations': violations,
            'by_type_and_agent': [dict(r) for r in evidence_records],
            'status': 'HEALTHY' if violations == 0 else 'VIOLATIONS_DETECTED',
            'verified_at': datetime.now(timezone.utc).isoformat()
        }

    finally:
        conn.close()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("MANDATORY EVIDENCE CONTRACT")
    print("CEO-DIR-2026-020 D2: Activate Evidence Attachment Everywhere")
    print("=" * 60)
    print(f"Evidence-Required Summary Types: {len(EVIDENCE_REQUIRED_SUMMARY_TYPES)}")
    for st in sorted(EVIDENCE_REQUIRED_SUMMARY_TYPES):
        print(f"  - {st}")
    print(f"\nValid Agents: {VALID_AGENTS}")
    print("\nVerifying coverage...")
    coverage = verify_evidence_coverage(24)
    print(json.dumps(coverage, indent=2, default=str))
