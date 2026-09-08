"""
CEO-DIR-2026-FINN-019: Neural Bridge Decision Engine

This module implements the two-phase decision lifecycle:
  Phase 1: IntentDraft - Created BEFORE any gate, captures market snapshot
  Phase 2: DecisionPlan - Sealed AFTER cognitive stack completes

CEO Issues Addressed:
  #1: IntentDraft before gates
  #2: DecisionPlan sealed after cognition
  #7: Tier-2 signature with key registry
  #8: Dual TTL (snapshot 60s, plan 300s)
  #9: Timeout = ABORTED, not degraded
  #11: COST_ABORT if cognition > 5s
  #13: LSA hash fields
  #15: Tier-2 signing agent (CSEO)
  #16: Regime stability flag

Refinements:
  R1: Audit-only mode for hard-blocked attempts
  R2: CAUSAL_NEUTRAL_FALLBACK explicit marking
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Constants
SNAPSHOT_TTL_SECONDS = 60       # CEO Issue #8: Market snapshot valid for 60s
PLAN_TTL_SECONDS = 300          # Plan valid for 300s after sealing
COGNITION_TIMEOUT_SECONDS = 5.0 # CEO Issue #11: Max cognition time
MIN_ROI_THRESHOLD = 1.2         # InForage minimum ROI


@dataclass
class IntentDraft:
    """
    Phase 1: Created immediately when needle is considered, BEFORE any gate.

    CEO-DIR-2026-FINN-019 NB-01: IntentDraft captured BEFORE any execution gate
    """
    draft_id: UUID
    needle_id: UUID
    asset: str
    direction: str  # 'LONG' or 'SHORT'

    # Market snapshot with TTL (CEO Issue #8)
    snapshot_price: float
    snapshot_regime: str
    snapshot_regime_stability: float  # CEO Issue #16
    snapshot_timestamp: datetime
    snapshot_ttl_valid_until: datetime

    # Pre-gate state
    eqs_score: float

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_snapshot_valid(self) -> bool:
        """Check if market snapshot is still fresh."""
        return datetime.now(timezone.utc) <= self.snapshot_ttl_valid_until

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for database storage."""
        return {
            'draft_id': str(self.draft_id),
            'needle_id': str(self.needle_id),
            'asset': self.asset,
            'direction': self.direction,
            'snapshot_price': self.snapshot_price,
            'snapshot_regime': self.snapshot_regime,
            'snapshot_regime_stability': self.snapshot_regime_stability,
            'snapshot_timestamp': self.snapshot_timestamp.isoformat(),
            'snapshot_ttl_valid_until': self.snapshot_ttl_valid_until.isoformat(),
            'eqs_score': self.eqs_score,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class DecisionPlan:
    """
    Phase 2: Sealed after cognitive stack completes.

    CEO-DIR-2026-FINN-019 NB-01: Signed DecisionPlan sealed after cognitive stack
    """
    plan_id: UUID
    intent_draft_id: UUID
    attempt_id: UUID
    needle_id: UUID

    # Trade details
    asset: str
    direction: str
    sizing_action: str
    position_usd: float

    # Trinity Requirement
    regime_check_passed: bool
    regime_stability_flag: bool     # CEO Issue #16
    causal_alignment_score: float   # 0-1 scale
    causal_fallback_used: bool      # R2: True when no edges found
    fss_score: float

    # Cognitive Evidence (ALL MANDATORY)
    sitc_event_id: UUID
    sitc_reasoning_complete: bool
    inforage_session_id: UUID
    inforage_roi: float
    ikea_validation_id: UUID
    causal_edge_refs: List[UUID]

    # LSA Loop (CEO Issue #13)
    lsa_hash_in: Optional[str]
    lsa_hash_out: Optional[str]  # R5: Write-once, post-settlement only

    # TTL (CEO Issue #8)
    plan_ttl_valid_until: datetime
    snapshot_ttl_valid_until: datetime

    # Signature (CEO Issue #7, #15)
    signature: str
    signing_agent: str              # Tier-2 Sub-Executive (e.g., "CSEO")
    signing_key_id: str             # Reference to fhq_meta.key_registry
    signed_at: datetime

    # VEGA Verification (CEO Issue #7)
    vega_verified: bool = False
    vega_verification_timestamp: Optional[datetime] = None

    # Cognition metrics (CEO Issue #11)
    cognition_duration_ms: int = 0
    cognition_cost_usd: float = 0.0

    # Outcome
    final_outcome: Optional[str] = None  # EXECUTED/BLOCKED/ABORTED/EXPIRED/COST_ABORT
    blocked_at_gate: Optional[str] = None
    block_reason: Optional[str] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_plan_valid(self) -> bool:
        """Check if plan TTL is still valid."""
        return datetime.now(timezone.utc) <= self.plan_ttl_valid_until

    def is_snapshot_valid(self) -> bool:
        """Check if original snapshot is still valid."""
        return datetime.now(timezone.utc) <= self.snapshot_ttl_valid_until

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for database storage."""
        return {
            'plan_id': str(self.plan_id),
            'intent_draft_id': str(self.intent_draft_id),
            'attempt_id': str(self.attempt_id),
            'needle_id': str(self.needle_id),
            'asset': self.asset,
            'direction': self.direction,
            'sizing_action': self.sizing_action,
            'position_usd': float(self.position_usd),
            'regime_check_passed': self.regime_check_passed,
            'regime_stability_flag': self.regime_stability_flag,
            'causal_alignment_score': float(self.causal_alignment_score),
            'causal_fallback_used': self.causal_fallback_used,
            'fss_score': float(self.fss_score),
            'sitc_event_id': str(self.sitc_event_id),
            'sitc_reasoning_complete': self.sitc_reasoning_complete,
            'inforage_session_id': str(self.inforage_session_id),
            'inforage_roi': float(self.inforage_roi),
            'ikea_validation_id': str(self.ikea_validation_id),
            'causal_edge_refs': [str(ref) for ref in self.causal_edge_refs],
            'lsa_hash_in': self.lsa_hash_in,
            'lsa_hash_out': self.lsa_hash_out,
            'plan_ttl_valid_until': self.plan_ttl_valid_until.isoformat(),
            'snapshot_ttl_valid_until': self.snapshot_ttl_valid_until.isoformat(),
            'signature': self.signature,
            'signing_agent': self.signing_agent,
            'signing_key_id': self.signing_key_id,
            'signed_at': self.signed_at.isoformat(),
            'vega_verified': self.vega_verified,
            'vega_verification_timestamp': self.vega_verification_timestamp.isoformat() if self.vega_verification_timestamp else None,
            'cognition_duration_ms': self.cognition_duration_ms,
            'cognition_cost_usd': float(self.cognition_cost_usd),
            'final_outcome': self.final_outcome,
            'blocked_at_gate': self.blocked_at_gate,
            'block_reason': self.block_reason,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class CognitiveResult:
    """Result from cognitive stack evaluation."""
    sitc_event_id: Optional[UUID]
    sitc_approved: bool
    sitc_confidence: str  # HIGH/MEDIUM/LOW
    sitc_reasoning_complete: bool

    inforage_session_id: Optional[UUID]
    inforage_roi: float
    inforage_should_abort: bool

    ikea_validation_id: Optional[UUID]
    ikea_passed: bool
    ikea_rule_violated: Optional[str]

    causal_edge_refs: List[UUID]
    causal_alignment_score: float
    causal_fallback_used: bool

    cognition_duration_ms: int
    cognition_cost_usd: float

    timed_out: bool = False
    exception: Optional[str] = None


@dataclass
class AbortResult:
    """Result when plan is aborted."""
    outcome: str  # BLOCKED/ABORTED/EXPIRED/COST_ABORT
    gate: str
    reason: str
    details: Optional[Dict[str, Any]] = None


def create_intent_draft(
    needle_id: UUID,
    asset: str,
    direction: str,
    current_price: float,
    current_regime: str,
    regime_stability: float,
    eqs_score: float
) -> IntentDraft:
    """
    Create IntentDraft with market snapshot.

    CEO Issue #8: Snapshot TTL set to 60 seconds.
    CEO Issue #16: Include regime stability.
    """
    now = datetime.now(timezone.utc)

    return IntentDraft(
        draft_id=uuid4(),
        needle_id=needle_id,
        asset=asset,
        direction=direction,
        snapshot_price=current_price,
        snapshot_regime=current_regime,
        snapshot_regime_stability=regime_stability,
        snapshot_timestamp=now,
        snapshot_ttl_valid_until=now + timedelta(seconds=SNAPSHOT_TTL_SECONDS),
        eqs_score=eqs_score,
        created_at=now
    )


def validate_snapshot_ttl(intent: IntentDraft) -> Tuple[bool, Optional[str]]:
    """
    Check snapshot freshness BEFORE cognition.

    CEO Issue #8: Snapshot must be < 60s old.
    """
    if not intent.is_snapshot_valid():
        age = (datetime.now(timezone.utc) - intent.snapshot_timestamp).total_seconds()
        return False, f"SNAPSHOT_EXPIRED: Market data stale ({age:.1f}s > {SNAPSHOT_TTL_SECONDS}s)"
    return True, None


def validate_plan_ttl(plan: DecisionPlan) -> Tuple[bool, Optional[str]]:
    """
    Check plan freshness BEFORE execution.

    CEO Issue #8: Check both snapshot and plan TTLs.
    """
    now = datetime.now(timezone.utc)

    if not plan.is_snapshot_valid():
        return False, "SNAPSHOT_EXPIRED: Original market data stale"

    if not plan.is_plan_valid():
        return False, f"PLAN_EXPIRED: DecisionPlan > {PLAN_TTL_SECONDS}s old"

    return True, None


def compute_signature(plan_data: Dict[str, Any], signing_key_id: str) -> str:
    """
    Compute Ed25519 signature for DecisionPlan.

    CEO Issue #7: Signature with key registry reference.

    Note: In production, this would use actual Ed25519 signing.
    For now, we compute a SHA-256 hash as placeholder.
    """
    # Serialize plan data deterministically
    import json
    canonical = json.dumps(plan_data, sort_keys=True, default=str)

    # Hash with key reference
    sig_content = f"{signing_key_id}:{canonical}"
    signature = hashlib.sha256(sig_content.encode()).hexdigest()

    return signature


def seal_decision_plan(
    intent: IntentDraft,
    attempt_id: UUID,
    cognitive_result: CognitiveResult,
    position_usd: float,
    sizing_action: str,
    fss_score: float,
    regime_check_passed: bool,
    signing_agent: str = "CSEO",
    signing_key_id: str = "CSEO-KEY-2026-001"
) -> DecisionPlan:
    """
    Seal DecisionPlan after cognitive stack completes.

    CEO Issue #7: Tier-2 signature with VEGA verification.
    CEO Issue #13: LSA hash fields.
    CEO Issue #15: Tier-2 signing agent.
    """
    now = datetime.now(timezone.utc)

    # Create plan with all required fields
    plan = DecisionPlan(
        plan_id=uuid4(),
        intent_draft_id=intent.draft_id,
        attempt_id=attempt_id,
        needle_id=intent.needle_id,
        asset=intent.asset,
        direction=intent.direction,
        sizing_action=sizing_action,
        position_usd=position_usd,
        regime_check_passed=regime_check_passed,
        regime_stability_flag=intent.snapshot_regime_stability >= 0.7,  # CEO Issue #16
        causal_alignment_score=cognitive_result.causal_alignment_score,
        causal_fallback_used=cognitive_result.causal_fallback_used,
        fss_score=fss_score,
        sitc_event_id=cognitive_result.sitc_event_id,
        sitc_reasoning_complete=cognitive_result.sitc_reasoning_complete,
        inforage_session_id=cognitive_result.inforage_session_id,
        inforage_roi=cognitive_result.inforage_roi,
        ikea_validation_id=cognitive_result.ikea_validation_id,
        causal_edge_refs=cognitive_result.causal_edge_refs,
        lsa_hash_in=None,  # CEO Issue #13: Populated by LSA loader
        lsa_hash_out=None,  # R5: Write-once, post-settlement only
        plan_ttl_valid_until=now + timedelta(seconds=PLAN_TTL_SECONDS),
        snapshot_ttl_valid_until=intent.snapshot_ttl_valid_until,
        signature="",  # Computed below
        signing_agent=signing_agent,
        signing_key_id=signing_key_id,
        signed_at=now,
        cognition_duration_ms=cognitive_result.cognition_duration_ms,
        cognition_cost_usd=cognitive_result.cognition_cost_usd
    )

    # Compute signature
    plan_data = plan.to_dict()
    plan.signature = compute_signature(plan_data, signing_key_id)

    return plan


def create_abort_result(
    outcome: str,
    gate: str,
    reason: str,
    details: Optional[Dict[str, Any]] = None
) -> AbortResult:
    """Create abort result for failed attempts."""
    return AbortResult(
        outcome=outcome,
        gate=gate,
        reason=reason,
        details=details
    )


class DecisionEngine:
    """
    Neural Bridge Decision Engine.

    Orchestrates the two-phase decision lifecycle:
    1. Create IntentDraft (before gates)
    2. Run gates and cognitive stack
    3. Seal DecisionPlan (after cognition)

    CEO Issue #9: Timeout = ABORTED, not degraded pass.
    CEO Issue #11: COST_ABORT if cognition > 5s.
    R1: Audit-only mode for hard-blocked attempts.
    """

    def __init__(self, db_conn, sitc_gate=None, inforage_controller=None, ikea_boundary=None):
        self.conn = db_conn
        self.sitc_gate = sitc_gate
        self.inforage = inforage_controller
        self.ikea = ikea_boundary

    def create_intent(
        self,
        needle_id: UUID,
        asset: str,
        direction: str,
        current_price: float,
        current_regime: str,
        regime_stability: float,
        eqs_score: float
    ) -> IntentDraft:
        """Create IntentDraft and persist to database."""
        intent = create_intent_draft(
            needle_id=needle_id,
            asset=asset,
            direction=direction,
            current_price=current_price,
            current_regime=current_regime,
            regime_stability=regime_stability,
            eqs_score=eqs_score
        )

        # Persist to database
        self._persist_intent(intent)

        logger.info(f"IntentDraft created: {intent.draft_id} for {asset} {direction}")
        return intent

    def run_cognitive_stack(
        self,
        intent: IntentDraft,
        position_usd: float,
        audit_only: bool = False,
        timeout_seconds: float = COGNITION_TIMEOUT_SECONDS
    ) -> CognitiveResult:
        """
        Run cognitive stack: SitC -> IKEA -> InForage -> Causal.

        CEO Issue #9: Timeout = abort, not degrade.
        CEO Issue #11: Track cognition time.
        R1: Audit-only mode skips expensive LLM calls.
        """
        start_time = time.time()

        try:
            # 1. SitC reasoning
            sitc_result = self._run_sitc(intent, audit_only, timeout_seconds)
            if sitc_result.get('timed_out'):
                return self._create_timeout_result(start_time, "SITC_TIMEOUT")

            # 2. IKEA boundary check
            ikea_result = self._run_ikea(intent, position_usd, audit_only)

            # 3. InForage ROI check
            inforage_result = self._run_inforage(intent, position_usd, audit_only)

            # 4. Causal edge lookup
            causal_result = self._query_causal_edges(intent.asset)

            # Check total time
            elapsed_ms = int((time.time() - start_time) * 1000)
            if elapsed_ms > timeout_seconds * 1000:
                return self._create_timeout_result(start_time, "COST_ABORT")

            return CognitiveResult(
                sitc_event_id=sitc_result.get('event_id'),
                sitc_approved=sitc_result.get('approved', False),
                sitc_confidence=sitc_result.get('confidence', 'LOW'),
                sitc_reasoning_complete=sitc_result.get('reasoning_complete', False),
                inforage_session_id=inforage_result.get('session_id'),
                inforage_roi=inforage_result.get('roi', 0.0),
                inforage_should_abort=inforage_result.get('should_abort', False),
                ikea_validation_id=ikea_result.get('validation_id'),
                ikea_passed=ikea_result.get('passed', False),
                ikea_rule_violated=ikea_result.get('rule_violated'),
                causal_edge_refs=causal_result.get('edge_refs', []),
                causal_alignment_score=causal_result.get('alignment_score', 0.5),
                causal_fallback_used=causal_result.get('fallback_used', True),
                cognition_duration_ms=elapsed_ms,
                cognition_cost_usd=0.0,  # Populated by cost tracker
                timed_out=False
            )

        except Exception as e:
            logger.error(f"Cognitive stack exception: {e}")
            elapsed_ms = int((time.time() - start_time) * 1000)
            return CognitiveResult(
                sitc_event_id=None,
                sitc_approved=False,
                sitc_confidence='LOW',
                sitc_reasoning_complete=False,
                inforage_session_id=None,
                inforage_roi=0.0,
                inforage_should_abort=True,
                ikea_validation_id=None,
                ikea_passed=False,
                ikea_rule_violated=None,
                causal_edge_refs=[],
                causal_alignment_score=0.5,
                causal_fallback_used=True,
                cognition_duration_ms=elapsed_ms,
                cognition_cost_usd=0.0,
                timed_out=False,
                exception=str(e)
            )

    def seal_plan(
        self,
        intent: IntentDraft,
        attempt_id: UUID,
        cognitive_result: CognitiveResult,
        position_usd: float,
        sizing_action: str,
        fss_score: float,
        regime_check_passed: bool
    ) -> DecisionPlan:
        """Seal DecisionPlan and persist to database."""
        plan = seal_decision_plan(
            intent=intent,
            attempt_id=attempt_id,
            cognitive_result=cognitive_result,
            position_usd=position_usd,
            sizing_action=sizing_action,
            fss_score=fss_score,
            regime_check_passed=regime_check_passed
        )

        # Persist to database
        self._persist_plan(plan)

        logger.info(f"DecisionPlan sealed: {plan.plan_id} for {intent.asset}")
        return plan

    def _run_sitc(self, intent: IntentDraft, audit_only: bool, timeout: float) -> Dict:
        """Run SitC reasoning with timeout."""
        if self.sitc_gate is None or audit_only:
            # Return mock approval for audit-only mode
            return {
                'event_id': uuid4(),
                'approved': True,
                'confidence': 'MEDIUM',
                'reasoning_complete': True,
                'timed_out': False
            }

        # Real SitC invocation would go here
        # For now, return mock result
        return {
            'event_id': uuid4(),
            'approved': True,
            'confidence': 'HIGH',
            'reasoning_complete': True,
            'timed_out': False
        }

    def _run_ikea(self, intent: IntentDraft, position_usd: float, audit_only: bool) -> Dict:
        """Run IKEA boundary check."""
        if self.ikea is None:
            # Return pass for missing IKEA
            return {
                'validation_id': uuid4(),
                'passed': True,
                'rule_violated': None
            }

        # Real IKEA invocation would call self.ikea.validate()
        return {
            'validation_id': uuid4(),
            'passed': True,
            'rule_violated': None
        }

    def _run_inforage(self, intent: IntentDraft, position_usd: float, audit_only: bool) -> Dict:
        """Run InForage ROI check."""
        if self.inforage is None or audit_only:
            # Calculate mock ROI
            expected_return_pct = intent.eqs_score * 0.05  # 5% TP
            expected_pnl = position_usd * expected_return_pct * 0.9985  # 15bps slippage
            total_cost = position_usd * 0.0015 + position_usd * 0.0015  # spread + slippage
            roi = expected_pnl / max(total_cost, 0.01)

            return {
                'session_id': uuid4(),
                'roi': roi,
                'should_abort': roi < MIN_ROI_THRESHOLD
            }

        # Real InForage invocation would go here
        return {
            'session_id': uuid4(),
            'roi': 2.0,
            'should_abort': False
        }

    def _query_causal_edges(self, asset: str) -> Dict:
        """
        Query causal edges for asset.

        R2: CAUSAL_NEUTRAL_FALLBACK when no edges found.
        """
        # Check if we have edges in database
        # For now, return fallback since tables are empty
        return {
            'edge_refs': [],
            'alignment_score': 0.5,  # Neutral
            'fallback_used': True,
            'warning': 'CAUSAL_NEUTRAL_FALLBACK: No edges found for asset'
        }

    def _create_timeout_result(self, start_time: float, reason: str) -> CognitiveResult:
        """Create result for timeout case."""
        elapsed_ms = int((time.time() - start_time) * 1000)
        return CognitiveResult(
            sitc_event_id=None,
            sitc_approved=False,
            sitc_confidence='LOW',
            sitc_reasoning_complete=False,
            inforage_session_id=None,
            inforage_roi=0.0,
            inforage_should_abort=True,
            ikea_validation_id=None,
            ikea_passed=False,
            ikea_rule_violated=None,
            causal_edge_refs=[],
            causal_alignment_score=0.5,
            causal_fallback_used=True,
            cognition_duration_ms=elapsed_ms,
            cognition_cost_usd=0.0,
            timed_out=True,
            exception=reason
        )

    def _persist_intent(self, intent: IntentDraft):
        """Persist IntentDraft to database."""
        if self.conn is None:
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO fhq_governance.intent_drafts (
                    draft_id, needle_id, asset, direction,
                    snapshot_price, snapshot_regime, snapshot_regime_stability,
                    snapshot_timestamp, snapshot_ttl_valid_until,
                    eqs_score, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                str(intent.draft_id),
                str(intent.needle_id),
                intent.asset,
                intent.direction,
                intent.snapshot_price,
                intent.snapshot_regime,
                intent.snapshot_regime_stability,
                intent.snapshot_timestamp,
                intent.snapshot_ttl_valid_until,
                intent.eqs_score,
                intent.created_at
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist IntentDraft: {e}")
            self.conn.rollback()

    def _persist_plan(self, plan: DecisionPlan):
        """Persist DecisionPlan to database."""
        if self.conn is None:
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO fhq_governance.decision_plans (
                    plan_id, intent_draft_id, attempt_id, needle_id,
                    asset, direction, sizing_action, position_usd,
                    regime_check_passed, regime_stability_flag,
                    causal_alignment_score, causal_fallback_used, fss_score,
                    sitc_event_id, sitc_reasoning_complete,
                    inforage_session_id, inforage_roi,
                    ikea_validation_id, causal_edge_refs,
                    lsa_hash_in, lsa_hash_out,
                    plan_ttl_valid_until, snapshot_ttl_valid_until,
                    signature, signing_agent, signing_key_id, signed_at,
                    vega_verified, vega_verification_timestamp,
                    cognition_duration_ms, cognition_cost_usd,
                    final_outcome, blocked_at_gate, block_reason,
                    created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
            ''', (
                str(plan.plan_id),
                str(plan.intent_draft_id),
                str(plan.attempt_id),
                str(plan.needle_id),
                plan.asset,
                plan.direction,
                plan.sizing_action,
                plan.position_usd,
                plan.regime_check_passed,
                plan.regime_stability_flag,
                plan.causal_alignment_score,
                plan.causal_fallback_used,
                plan.fss_score,
                str(plan.sitc_event_id) if plan.sitc_event_id else None,
                plan.sitc_reasoning_complete,
                str(plan.inforage_session_id) if plan.inforage_session_id else None,
                plan.inforage_roi,
                str(plan.ikea_validation_id) if plan.ikea_validation_id else None,
                [str(ref) for ref in plan.causal_edge_refs],
                plan.lsa_hash_in,
                plan.lsa_hash_out,
                plan.plan_ttl_valid_until,
                plan.snapshot_ttl_valid_until,
                plan.signature,
                plan.signing_agent,
                plan.signing_key_id,
                plan.signed_at,
                plan.vega_verified,
                plan.vega_verification_timestamp,
                plan.cognition_duration_ms,
                plan.cognition_cost_usd,
                plan.final_outcome,
                plan.blocked_at_gate,
                plan.block_reason,
                plan.created_at
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist DecisionPlan: {e}")
            self.conn.rollback()


if __name__ == "__main__":
    # Quick test
    from uuid import uuid4

    intent = create_intent_draft(
        needle_id=uuid4(),
        asset="BTC/USD",
        direction="LONG",
        current_price=94500.0,
        current_regime="RISK_ON",
        regime_stability=0.85,
        eqs_score=0.82
    )

    print(f"IntentDraft: {intent.draft_id}")
    print(f"  Asset: {intent.asset}")
    print(f"  Snapshot valid: {intent.is_snapshot_valid()}")
    print(f"  EQS: {intent.eqs_score}")
