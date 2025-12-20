"""Intent models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class IntentScore(BaseModel):
    """
    Inferred participant intent from market microstructure.

    Answers: What are other participants trying to do?
    """

    intent_id: str = Field(..., description="Intent score identifier")
    timestamp: datetime = Field(..., description="Timestamp")

    # Intent probabilities (Bayesian)
    intent_probabilities: Dict[str, float] = Field(
        ...,
        description="P(intent | observations). Must sum to 1.0"
    )
    # Example: {"long": 0.7, "short": 0.2, "neutral": 0.1}

    # Confidence in intent inference
    confidence: float = Field(..., ge=0.0, le=1.0, description="Inference confidence")

    # Evidence sources
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Evidence: open_interest, funding, flows, basis"
    )

    # Dominant intent
    dominant_intent: Literal["LONG", "SHORT", "NEUTRAL", "UNKNOWN"] = Field(
        ...,
        description="Dominant market intent"
    )
    intent_strength: float = Field(..., ge=0.0, le=1.0, description="Intent strength")

    # Participant type inference (optional)
    participant_type: Optional[Literal[
        "WHALE",
        "RETAIL",
        "INSTITUTIONAL",
        "MARKET_MAKER",
        "UNKNOWN"
    ]] = Field(default="UNKNOWN", description="Inferred participant type")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def is_directional(self) -> bool:
        """Strong directional intent?"""
        return self.intent_strength > 0.6


@frozen
class ParticipantIntent(BaseModel):
    """Single participant intent observation."""

    participant_id: str = Field(..., description="Participant identifier")
    intent: Literal["LONG", "SHORT", "NEUTRAL"] = Field(..., description="Intent direction")
    probability: float = Field(..., ge=0.0, le=1.0, description="Probability")
    size_estimate: Optional[float] = Field(None, description="Estimated position size")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
