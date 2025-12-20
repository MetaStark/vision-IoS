"""Noise models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class NoiseScore(BaseModel):
    """
    Evaluates noise-to-signal ratio.

    Answers: Should we act, or is the market too noisy?
    """

    noise_id: str = Field(..., description="Noise score identifier")
    timestamp: datetime = Field(..., description="Timestamp")

    # Noise level [0.0, 1.0]
    noise_level: float = Field(..., ge=0.0, le=1.0, description="Noise level")

    # Signal quality [0.0, 1.0]
    signal_quality: float = Field(..., ge=0.0, le=1.0, description="Signal quality")

    # Noise-to-signal ratio
    noise_to_signal_ratio: float = Field(..., ge=0.0, description="Noise/signal ratio")

    # Regime classification
    noise_regime: Literal[
        "CLEAN",          # Low noise, high signal
        "NORMAL",         # Moderate noise
        "NOISY",          # High noise
        "EXTREME_NOISE"   # Market breakdown
    ] = Field(..., description="Noise regime classification")

    # Actionability
    is_acceptable: bool = Field(
        ...,
        description="Is noise low enough to act?"
    )
    threshold_used: float = Field(..., ge=0.0, le=1.0, description="Threshold applied")

    # Noise sources
    noise_sources: List[str] = Field(
        default_factory=list,
        description="Identified noise contributors"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def should_pause(self) -> bool:
        """Should trading be paused due to noise?"""
        return self.noise_regime == "EXTREME_NOISE" or not self.is_acceptable
