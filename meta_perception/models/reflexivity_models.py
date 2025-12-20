"""Reflexivity models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class ReflexivityScore(BaseModel):
    """
    Measures how FjordHQ's decisions influence future market state.

    Answers: Are we moving the market? Is the market reacting to us?
    """

    reflexivity_id: str = Field(..., description="Reflexivity score identifier")
    timestamp: datetime = Field(..., description="Timestamp")

    # Reflexivity coefficient: corr(our_decision → next_state)
    reflexivity_coefficient: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Correlation between decisions and market moves"
    )

    # Impact metrics
    market_impact_estimate: float = Field(
        ...,
        ge=0.0,
        description="Estimated price impact of our trades (bps)"
    )

    # Feedback loop strength
    feedback_strength: Literal["NONE", "WEAK", "MODERATE", "STRONG"] = Field(
        ...,
        description="Feedback loop classification"
    )

    # Self-fulfilling probability
    self_fulfilling_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="P(our prediction causes outcome)"
    )

    # Adaptive market hypothesis
    market_learning_rate: float = Field(
        ...,
        ge=0.0,
        description="How fast market adapts to our strategy"
    )

    # Impact decay
    impact_half_life_hours: Optional[float] = Field(
        None,
        ge=0.0,
        description="Time for impact to decay 50%"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def is_significant(self) -> bool:
        """Significant reflexivity detected?"""
        return abs(self.reflexivity_coefficient) > 0.3


@frozen
class ImpactMetrics(BaseModel):
    """Detailed impact breakdown."""

    permanent_impact_bps: float = Field(..., description="Permanent price impact (bps)")
    temporary_impact_bps: float = Field(..., description="Temporary price impact (bps)")
    total_impact_bps: float = Field(..., description="Total price impact (bps)")
    impact_confidence: float = Field(..., ge=0.0, le=1.0, description="Impact estimate confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
