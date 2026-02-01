"""
Signal Envelope Schema
CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001

Explicit schema definition for Cognitive Engine output.
LINE MUST reject any envelope missing required fields.

Author: STIG (CTO)
Date: 2026-01-04
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Any
from enum import Enum
import uuid
import hashlib
import json

# Import DEFCONLevel from cognitive_engines to avoid duplication
from .cognitive_engines import DEFCONLevel


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_SIGNAL = "NO_SIGNAL"


class ClaimType(str, Enum):
    NUMERIC = "NUMERIC"
    TEMPORAL = "TEMPORAL"
    ENTITY_PREDICATE = "ENTITY_PREDICATE"
    CAUSAL = "CAUSAL"


@dataclass(frozen=True)
class Claim:
    """Single claim extracted from FINN output."""
    claim_id: str
    claim_text: str
    claim_type: ClaimType
    snippet_ids: List[str]
    grounded: bool

    @classmethod
    def create(cls, claim_text: str, claim_type: ClaimType, snippet_ids: List[str], grounded: bool = False) -> 'Claim':
        """Factory method to create a new Claim with generated ID."""
        return cls(
            claim_id=str(uuid.uuid4()),
            claim_text=claim_text,
            claim_type=claim_type,
            snippet_ids=snippet_ids,
            grounded=grounded
        )


@dataclass(frozen=True)
class GroundingResult:
    """Result of IKEA grounding verification."""
    total_claims: int
    grounded_count: int
    ungrounded_count: int
    gcr: float  # Grounded Claim Rate (0.0 - 1.0)
    ungrounded_claims: List[str]  # claim_ids of ungrounded claims

    @property
    def is_fully_grounded(self) -> bool:
        return self.gcr == 1.0 and self.ungrounded_count == 0


@dataclass(frozen=True)
class SignalEnvelope:
    """
    Immutable output from Cognitive Engine.
    LINE MUST reject any envelope missing required fields.
    """
    # Identity
    signal_id: str
    timestamp: datetime

    # Asset context
    asset: str
    regime: str
    defcon_level: DEFCONLevel

    # Action (REQUIRED)
    action: SignalAction
    confidence: float

    # Evidence Chain (REQUIRED - LINE REFUSAL without these)
    bundle_id: str
    snippet_ids: List[str]
    draft_claims: List[Claim]
    verified_claims: List[Claim]

    # Grounding Proof
    grounding_result: GroundingResult
    ikea_verified: bool

    # Cryptographic
    signed_by: str
    signature: str

    # Cost tracking
    query_cost_usd: float

    @classmethod
    def create(
        cls,
        asset: str,
        regime: str,
        defcon_level: DEFCONLevel,
        action: SignalAction,
        confidence: float,
        bundle_id: str,
        snippet_ids: List[str],
        draft_claims: List[Claim],
        verified_claims: List[Claim],
        grounding_result: GroundingResult,
        signed_by: str,
        query_cost_usd: float,
        signature: str = ""
    ) -> 'SignalEnvelope':
        """Factory method to create a new SignalEnvelope with generated ID and timestamp."""
        return cls(
            signal_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            asset=asset,
            regime=regime,
            defcon_level=defcon_level,
            action=action,
            confidence=confidence,
            bundle_id=bundle_id,
            snippet_ids=snippet_ids,
            draft_claims=draft_claims,
            verified_claims=verified_claims,
            grounding_result=grounding_result,
            ikea_verified=grounding_result.is_fully_grounded,
            signed_by=signed_by,
            signature=signature,
            query_cost_usd=query_cost_usd
        )

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of envelope for signing."""
        content = {
            'signal_id': self.signal_id,
            'timestamp': self.timestamp.isoformat(),
            'asset': self.asset,
            'regime': self.regime,
            'defcon_level': self.defcon_level.value,
            'action': self.action.value,
            'confidence': self.confidence,
            'bundle_id': self.bundle_id,
            'snippet_ids': self.snippet_ids,
            'ikea_verified': self.ikea_verified,
            'query_cost_usd': self.query_cost_usd
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class NoSignal:
    """Returned when cognitive engine cannot produce a valid signal."""
    signal_id: str
    timestamp: datetime
    reason: str
    defcon_level: DEFCONLevel
    shadow_envelope: Optional[SignalEnvelope] = None

    @classmethod
    def create(
        cls,
        reason: str,
        defcon_level: DEFCONLevel,
        shadow_envelope: Optional[SignalEnvelope] = None
    ) -> 'NoSignal':
        """Factory method to create a NoSignal with generated ID and timestamp."""
        return cls(
            signal_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            reason=reason,
            defcon_level=defcon_level,
            shadow_envelope=shadow_envelope
        )


@dataclass
class ValidationResult:
    """Result of envelope validation for LINE execution."""
    valid: bool
    errors: List[str]
    rejection_reason: Optional[str]


def validate_envelope_for_execution(envelope: SignalEnvelope) -> ValidationResult:
    """
    LINE calls this before any execution consideration.

    LINE MUST REJECT any SignalEnvelope that:
    - bundle_id is None: "Missing evidence bundle"
    - len(snippet_ids) == 0: "No evidence cited"
    - ikea_verified != True: "Claims not grounded"
    - signature is None: "Unsigned envelope"
    - query_cost_usd > 0.50: "Cost cap exceeded"
    - action == NO_SIGNAL: "No actionable signal"
    """
    errors = []

    if not envelope.bundle_id:
        errors.append("Missing evidence bundle - cannot trace decision")
    if not envelope.snippet_ids:
        errors.append("No evidence cited - ungrounded signal")
    if not envelope.ikea_verified:
        errors.append("Claims not IKEA-verified - potential hallucination")
    if not envelope.signature:
        errors.append("Unsigned envelope - cannot verify origin")
    if envelope.query_cost_usd > 0.50:
        errors.append(f"Cost cap exceeded: ${envelope.query_cost_usd}")
    if envelope.action == SignalAction.NO_SIGNAL:
        errors.append("No actionable signal")

    if errors:
        return ValidationResult(valid=False, errors=errors, rejection_reason="; ".join(errors))

    return ValidationResult(valid=True, errors=[], rejection_reason=None)


# Type alias for return type from cognitive gateway
CognitiveResult = SignalEnvelope | NoSignal


class IKEARefusal(Exception):
    """Raised when IKEA refuses to verify a non-SignalEnvelope input."""
    pass


def validate_ikea_input(artifact: Any) -> None:
    """
    IKEA must verify ONLY SignalEnvelope.draft_claims.
    No other text blob is permitted.

    Raises:
        IKEARefusal: If artifact is not a SignalEnvelope or has no draft_claims
    """
    if not isinstance(artifact, SignalEnvelope):
        raise IKEARefusal("IKEA only verifies SignalEnvelope.draft_claims")

    if not hasattr(artifact, 'draft_claims') or not artifact.draft_claims:
        raise IKEARefusal("SignalEnvelope missing draft_claims field")
