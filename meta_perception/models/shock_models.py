"""Shock models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class ShockEvent(BaseModel):
    """
    Information shock detected BEFORE price reacts.

    Answers: Is something unusual happening?
    """

    shock_id: str = Field(..., description="Shock event identifier")
    timestamp: datetime = Field(..., description="Shock timestamp")
    detected_at: datetime = Field(..., description="Detection timestamp")

    # Shock type
    shock_type: Literal[
        "ENTROPY_SPIKE",       # Sudden entropy jump
        "FLOW_ANOMALY",        # Unusual whale flow
        "OI_SURGE",            # Open interest surge
        "FUNDING_SHOCK",       # Funding rate shock
        "CORRELATION_BREAK",   # Correlation breakdown
        "MICROSTRUCTURE_ANOMALY",  # Order book anomaly
        "REGIME_TRANSITION",   # Regime change
        "UNKNOWN"
    ] = Field(..., description="Type of shock")

    # Intensity [0.0, ∞)
    intensity: float = Field(..., ge=0.0, description="Shock intensity")

    # Interpretation
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        ...,
        description="Shock severity"
    )

    # Affected features
    affected_features: List[str] = Field(
        default_factory=list,
        description="Features affected by shock"
    )

    # Shock metrics
    shock_size_std_devs: float = Field(
        ...,
        description="Size in standard deviations"
    )

    # Directional impact
    expected_direction: Optional[Literal["UP", "DOWN", "NEUTRAL"]] = Field(
        None,
        description="Expected price direction"
    )

    # Resolution
    is_resolved: bool = Field(default=False, description="Is shock resolved?")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def is_critical(self) -> bool:
        """Is this a critical shock?"""
        return self.severity == "CRITICAL"


@frozen
class ShockIntensity(BaseModel):
    """Aggregate shock intensity across all active shocks."""

    total_intensity: float = Field(..., ge=0.0, description="Total shock intensity")
    max_intensity: float = Field(..., ge=0.0, description="Maximum individual shock intensity")
    active_shock_count: int = Field(..., ge=0, description="Number of active shocks")
    critical_shock_count: int = Field(..., ge=0, description="Number of critical shocks")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
