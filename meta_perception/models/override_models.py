"""Uncertainty override models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class UncertaintyOverride(BaseModel):
    """Log entry when system overrides itself."""

    override_id: str = Field(..., description="Override identifier")
    timestamp: datetime = Field(..., description="Override timestamp")
    perception_snapshot_id: str = Field(..., description="Associated snapshot ID")

    # Override trigger
    trigger_reason: Literal[
        "HIGH_NOISE",
        "LOW_CONFIDENCE",
        "REGIME_PIVOT",
        "CRITICAL_SHOCK",
        "HIGH_UNCERTAINTY",
        "REFLEXIVITY_LOOP",
        "DATA_QUALITY"
    ] = Field(..., description="Reason for override")

    # Metrics at override
    noise_level: float = Field(..., ge=0.0, le=1.0, description="Noise level at override")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence at override")
    total_uncertainty: float = Field(..., ge=0.0, description="Total uncertainty")
    regime_stress: float = Field(..., ge=0.0, description="Regime stress")

    # What was prevented
    prevented_actions: List[str] = Field(
        ...,
        description="Actions that would have been taken"
    )

    # Numerical justification
    override_justification: Dict[str, Any] = Field(
        ...,
        description="Detailed numerical breakdown of why"
    )

    # Impact
    estimated_prevented_trades: int = Field(..., ge=0, description="Estimated trades prevented")
    estimated_prevented_capital_usd: float = Field(
        ...,
        ge=0.0,
        description="Estimated capital saved"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
