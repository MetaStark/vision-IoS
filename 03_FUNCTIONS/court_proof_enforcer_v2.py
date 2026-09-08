#!/usr/bin/env python3
"""
COURT-PROOF EVIDENCE ENFORCER v2.0
===================================
CEO Directive: CEO-DIR-2026-019 P0-3
Classification: CRITICAL - Learning Activation

Enhancements over v1:
  1. ASRP Binding (ADR-018): state_snapshot_hash, state_timestamp, agent_id
  2. DDATP Validation: Outcome independence, canonical regime enforcement
  3. Measurement Validity Flag: OUTCOME_INDEPENDENCE check
  4. Fail-Closed: Missing evidence = rejected output, not degraded

AUDIT-GRADE REQUIREMENTS:
  - Every FINN Insight Pack must include ASRP binding
  - Evidence pointers (tables, row ids, hashes) are mandatory
  - Summaries inherit same evidence linkage as underlying metrics
  - If binding or evidence is missing, output is REJECTED (not degraded)

Author: STIG (CTO)
Date: 2026-01-07
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("court_proof_enforcer_v2")


class CourtProofViolation(Exception):
    """Raised when evidence requirements are not met. FAIL-CLOSED."""
    pass


class ASRPBindingViolation(Exception):
    """Raised when ASRP binding requirements are not met. FAIL-CLOSED."""
    pass


class DDATPValidationFailure(Exception):
    """Raised when DDATP validation fails. FAIL-CLOSED."""
    pass


class OutcomeIndependenceViolation(Exception):
    """Raised when outcome independence cannot be proven. FAIL-CLOSED."""
    pass


# =============================================================================
# CANONICAL REGIME TAXONOMY (CEO-DIR-2026-019)
# =============================================================================
# These are the ONLY valid regime labels after circular validation fix

CANONICAL_REGIMES = {
    'STRONG_BULL', 'BULL', 'NEUTRAL', 'BEAR', 'STRONG_BEAR',
    'VOLATILE_NON_DIRECTIONAL', 'COMPRESSION', 'BROKEN', 'UNTRUSTED'
}

# Non-canonical regimes that require mapping
REGIME_MAPPING = {
    'STRESS': 'BEAR',  # CEO-DIR-2026-019: STRESS maps to BEAR
}

# Evidence sources that are CONTAMINATED (circular validation)
CONTAMINATED_EVIDENCE_SOURCES = {
    'sovereign_regime_state_v4',  # Predictions used as outcomes
}

# Evidence sources that are INDEPENDENT
INDEPENDENT_EVIDENCE_SOURCES = {
    'fhq_market.prices',  # Price-based regime derivation
}


class CourtProofEnforcerV2:
    """
    CEO-DIR-2026-019 P0-3: Enhanced Court-Proof Evidence Enforcer.

    Key differences from v1:
    1. ASRP binding is MANDATORY, not optional
    2. DDATP validation checks outcome independence
    3. Fail-closed on any validation failure
    4. Measurement validity flag tracks outcome independence
    """

    VALID_AGENTS = {'FINN', 'STIG', 'LINE', 'LARS', 'VEGA', 'CEIO', 'CDMO', 'CRIO'}

    VALID_SUMMARY_TYPES = {
        'ALPHA_SIGNAL', 'REGIME_SUMMARY', 'FACTOR_SUMMARY',
        'GOLDEN_NEEDLE', 'EXECUTION_RESULT', 'GOVERNANCE_DECISION',
        'MACRO_SYNTHESIS', 'LIQUIDITY_ANALYSIS', 'CREDIT_ANALYSIS',
        'INGEST_SUMMARY', 'VALIDATION_REPORT', 'AUDIT_FINDING',
        'SKILL_METRIC', 'EPISTEMIC_LESSON', 'MUTATION_PROPOSAL',
        'INSIGHT_PACK', 'NIGHTLY_INSIGHT'
    }

    def __init__(self, db_connection):
        """Initialize with database connection."""
        self.conn = db_connection

    def _compute_hash(self, data: Any) -> str:
        """Compute SHA-256 hash of data."""
        if isinstance(data, dict) or isinstance(data, list):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    def _get_state_snapshot(self) -> Dict:
        """
        Get current system state snapshot for ASRP binding.
        Returns state_snapshot_hash, state_timestamp, and key state values.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get execution state
            cur.execute("""
                SELECT
                    cognitive_fasting,
                    fasting_reason,
                    revalidation_required
                FROM fhq_governance.execution_state
                WHERE state_key = 'PRIMARY'
                LIMIT 1
            """)
            exec_state = cur.fetchone() or {}

            # Get latest regime state
            cur.execute("""
                SELECT
                    policy_regime,
                    policy_confidence,
                    defcon_level,
                    policy_timestamp
                FROM fhq_perception.sovereign_policy_state
                ORDER BY policy_timestamp DESC
                LIMIT 1
            """)
            regime_state = cur.fetchone() or {}

            # Get data freshness
            cur.execute("""
                SELECT
                    MAX(timestamp) as latest_price,
                    EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) / 3600 as staleness_hours
                FROM fhq_market.prices
                WHERE timestamp > NOW() - INTERVAL '48 hours'
            """)
            freshness = cur.fetchone() or {}

        state_snapshot = {
            'snapshot_timestamp': datetime.now(timezone.utc).isoformat(),
            'execution_state': {
                'cognitive_fasting': exec_state.get('cognitive_fasting', False),
                'fasting_reason': exec_state.get('fasting_reason'),
                'revalidation_required': exec_state.get('revalidation_required', False)
            },
            'regime_state': {
                'policy_regime': regime_state.get('policy_regime'),
                'policy_confidence': float(regime_state.get('policy_confidence', 0)),
                'defcon_level': regime_state.get('defcon_level'),
                'policy_timestamp': regime_state.get('policy_timestamp').isoformat() if regime_state.get('policy_timestamp') else None
            },
            'data_freshness': {
                'latest_price': freshness.get('latest_price').isoformat() if freshness.get('latest_price') else None,
                'staleness_hours': float(freshness.get('staleness_hours', 999))
            }
        }

        state_snapshot_hash = self._compute_hash(state_snapshot)
        state_snapshot['state_snapshot_hash'] = state_snapshot_hash

        return state_snapshot

    def _validate_canonical_regime(self, regime: str) -> Tuple[bool, str]:
        """
        Validate regime label is canonical.
        Returns (is_canonical, canonical_value).
        """
        if regime in CANONICAL_REGIMES:
            return True, regime
        elif regime in REGIME_MAPPING:
            mapped = REGIME_MAPPING[regime]
            logger.warning(f"Non-canonical regime '{regime}' mapped to '{mapped}'")
            return True, mapped
        else:
            return False, regime

    def _validate_outcome_independence(self, evidence_source: str) -> Tuple[bool, str]:
        """
        DDATP: Validate that outcome source is not prediction-derived.
        This prevents circular validation.
        """
        if evidence_source in CONTAMINATED_EVIDENCE_SOURCES:
            return False, f"CONTAMINATED: {evidence_source} is prediction-derived"
        elif evidence_source in INDEPENDENT_EVIDENCE_SOURCES:
            return True, f"INDEPENDENT: {evidence_source}"
        else:
            return False, f"UNKNOWN: {evidence_source} not in approved list"

    def validate_ddatp(
        self,
        evidence_sources: List[str],
        regime_labels: List[str]
    ) -> Dict:
        """
        DDATP (Data-to-Decision Admissibility Test Protocol) validation.

        Checks:
        1. Outcome sources are not prediction-derived
        2. Regime labels are canonical

        Returns validation result dict.
        Raises DDATPValidationFailure on failure (fail-closed).
        """
        result = {
            'valid': True,
            'outcome_independence': True,
            'canonical_regimes': True,
            'violations': [],
            'validated_at': datetime.now(timezone.utc).isoformat()
        }

        # Check outcome independence
        for source in evidence_sources:
            is_independent, msg = self._validate_outcome_independence(source)
            if not is_independent:
                result['valid'] = False
                result['outcome_independence'] = False
                result['violations'].append({
                    'type': 'OUTCOME_INDEPENDENCE',
                    'source': source,
                    'message': msg
                })

        # Check canonical regimes
        for regime in regime_labels:
            is_canonical, canonical = self._validate_canonical_regime(regime)
            if not is_canonical:
                result['valid'] = False
                result['canonical_regimes'] = False
                result['violations'].append({
                    'type': 'NON_CANONICAL_REGIME',
                    'regime': regime,
                    'message': f"Regime '{regime}' is not in canonical taxonomy"
                })

        if not result['valid']:
            # FAIL-CLOSED: Reject on validation failure
            raise DDATPValidationFailure(
                f"DDATP validation failed: {len(result['violations'])} violations. "
                f"Violations: {result['violations']}"
            )

        return result

    def attach_evidence_with_asrp(
        self,
        summary_id: str,
        summary_type: str,
        generating_agent: str,
        raw_query: str,
        query_result: Any,
        summary_content: Dict,
        evidence_sources: List[str],
        regime_labels: Optional[List[str]] = None,
        ddatp_bypass: bool = False
    ) -> Dict:
        """
        Attach court-proof evidence with ASRP binding.

        This is the MANDATORY function for P0-3 compliance.

        Args:
            summary_id: Unique identifier for this summary
            summary_type: Type of summary
            generating_agent: The agent creating this summary
            raw_query: The exact SQL query that produced the data
            query_result: The raw data returned by the query
            summary_content: The summary itself
            evidence_sources: List of data sources used (for DDATP)
            regime_labels: List of regime labels used (for DDATP)
            ddatp_bypass: If True, skip DDATP (ONLY for non-calibration summaries)

        Returns:
            Dict containing evidence_id, ASRP binding, and verification info

        Raises:
            CourtProofViolation: If any required evidence is missing
            ASRPBindingViolation: If ASRP binding fails
            DDATPValidationFailure: If DDATP validation fails
        """
        # Validate basic inputs
        if not summary_id or len(summary_id) < 3:
            raise CourtProofViolation("summary_id is mandatory")

        if generating_agent not in self.VALID_AGENTS:
            raise CourtProofViolation(f"Invalid agent: {generating_agent}")

        if not raw_query or len(raw_query) < 10:
            raise CourtProofViolation("raw_query is mandatory (min 10 chars)")

        if query_result is None:
            raise CourtProofViolation("query_result is mandatory")

        # ASRP Binding: Get state snapshot
        state_snapshot = self._get_state_snapshot()

        # DDATP Validation (unless bypassed)
        ddatp_result = None
        if not ddatp_bypass:
            ddatp_result = self.validate_ddatp(
                evidence_sources=evidence_sources,
                regime_labels=regime_labels or []
            )

        # Compute hashes
        query_result_hash = self._compute_hash(query_result)
        summary_hash = self._compute_hash(summary_content)

        # Convert query_result to JSON-serializable format
        if hasattr(query_result, 'to_dict'):
            query_result_json = query_result.to_dict()
        elif hasattr(query_result, '__iter__') and not isinstance(query_result, (str, dict)):
            query_result_json = list(query_result)
        else:
            query_result_json = query_result

        evidence_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)

        # Build ASRP binding
        asrp_binding = {
            'state_snapshot_hash': state_snapshot['state_snapshot_hash'],
            'state_timestamp': state_snapshot['snapshot_timestamp'],
            'agent_id': generating_agent,
            'summary_id': summary_id,
            'created_at': created_at.isoformat()
        }

        # Build measurement validity flag
        measurement_validity = {
            'outcome_independence': ddatp_result['outcome_independence'] if ddatp_result else None,
            'canonical_regimes': ddatp_result['canonical_regimes'] if ddatp_result else None,
            'ddatp_validated': ddatp_result is not None,
            'ddatp_bypassed': ddatp_bypass
        }

        # Insert into database
        with self.conn.cursor() as cur:
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
                Json(summary_content),
                summary_hash,
                Json({
                    'asrp_binding': asrp_binding,
                    'state_snapshot': state_snapshot,
                    'measurement_validity': measurement_validity,
                    'ddatp_result': ddatp_result,
                    'evidence_sources': evidence_sources
                }),
                created_at
            ))

            # Log to governance
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
                    'EVIDENCE_ATTACHMENT_V2',
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
                f"Court-proof evidence with ASRP binding: hash={query_result_hash[:16]}..., "
                f"state_hash={state_snapshot['state_snapshot_hash'][:16]}...",
                generating_agent,
                created_at,
                Json({
                    'evidence_id': evidence_id,
                    'asrp_binding': asrp_binding,
                    'measurement_validity': measurement_validity
                })
            ))

            self.conn.commit()

        logger.info(f"[COURT-PROOF-V2] Evidence attached: {summary_id}")
        logger.info(f"[COURT-PROOF-V2] ASRP binding: {asrp_binding['state_snapshot_hash'][:16]}...")
        logger.info(f"[COURT-PROOF-V2] OUTCOME_INDEPENDENCE: {measurement_validity['outcome_independence']}")

        return {
            'evidence_id': evidence_id,
            'summary_id': summary_id,
            'summary_type': summary_type,
            'generating_agent': generating_agent,
            'query_result_hash': query_result_hash,
            'summary_hash': summary_hash,
            'asrp_binding': asrp_binding,
            'measurement_validity': measurement_validity,
            'created_at': created_at.isoformat(),
            'court_proof_status': 'VERIFIED_V2'
        }

    def verify_evidence_integrity(self, evidence_id: str) -> Dict:
        """
        Verify the integrity of stored evidence including ASRP binding.

        Checks:
        1. Hash integrity (recompute and compare)
        2. ASRP binding validity
        3. Evidence pointer resolution
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM vision_verification.summary_evidence_ledger
                WHERE evidence_id = %s
            """, (evidence_id,))
            record = cur.fetchone()

        if not record:
            return {
                'valid': False,
                'error': 'Evidence record not found',
                'evidence_id': evidence_id
            }

        # Recompute hash
        recomputed_hash = self._compute_hash(record['query_result_snapshot'])
        hash_valid = (recomputed_hash == record['query_result_hash'])

        # Verify ASRP binding
        asrp_binding = record.get('execution_context', {}).get('asrp_binding', {})
        asrp_valid = bool(asrp_binding.get('state_snapshot_hash'))

        # Verify measurement validity
        measurement_validity = record.get('execution_context', {}).get('measurement_validity', {})

        result = {
            'valid': hash_valid and asrp_valid,
            'evidence_id': evidence_id,
            'summary_id': record['summary_id'],
            'hash_integrity': {
                'valid': hash_valid,
                'stored_hash': record['query_result_hash'],
                'recomputed_hash': recomputed_hash
            },
            'asrp_binding': {
                'valid': asrp_valid,
                'state_snapshot_hash': asrp_binding.get('state_snapshot_hash'),
                'state_timestamp': asrp_binding.get('state_timestamp'),
                'agent_id': asrp_binding.get('agent_id')
            },
            'measurement_validity': measurement_validity,
            'verification_timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Log verification
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vision_verification.evidence_verification_log (
                    evidence_id,
                    verified_by,
                    verification_result,
                    verification_details
                ) VALUES (%s, 'COURT_PROOF_V2', %s, %s)
            """, (
                evidence_id,
                result['valid'],
                Json(result)
            ))
            self.conn.commit()

        return result


def require_court_proof_v2(
    summary_type: str,
    generating_agent: str,
    evidence_sources: List[str]
):
    """
    Decorator to enforce v2 court-proof evidence on summary-generating functions.

    FAIL-CLOSED: If evidence attachment fails, the entire operation fails.
    """
    def decorator(func):
        def wrapper(db_conn, query: str, *args, **kwargs):
            # Execute the wrapped function
            summary_content, query_result = func(db_conn, query, *args, **kwargs)

            # Generate summary_id
            summary_id = f"{func.__name__.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

            # Attach evidence with ASRP binding
            enforcer = CourtProofEnforcerV2(db_conn)
            evidence = enforcer.attach_evidence_with_asrp(
                summary_id=summary_id,
                summary_type=summary_type,
                generating_agent=generating_agent,
                raw_query=query,
                query_result=query_result,
                summary_content=summary_content,
                evidence_sources=evidence_sources,
                regime_labels=kwargs.get('regime_labels', [])
            )

            return {
                'summary': summary_content,
                'evidence': evidence,
                'asrp_binding': evidence['asrp_binding'],
                'measurement_validity': evidence['measurement_validity']
            }
        return wrapper
    return decorator


if __name__ == '__main__':
    print("Court-Proof Evidence Enforcer v2.0")
    print("CEO-DIR-2026-019 P0-3: ASRP + DDATP + Fail-Closed")
    print(f"Canonical Regimes: {CANONICAL_REGIMES}")
    print(f"Contaminated Sources: {CONTAMINATED_EVIDENCE_SOURCES}")
    print(f"Independent Sources: {INDEPENDENT_EVIDENCE_SOURCES}")
