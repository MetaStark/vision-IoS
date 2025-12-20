"""Regime models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class RegimeAlert(BaseModel):
    """
    Nonlinear regime pivot detection BEFORE it manifests.

    Answers: Is the regime about to change?
    """

    alert_id: str = Field(..., description="Alert identifier")
    timestamp: datetime = Field(..., description="Alert timestamp")

    # Current regime
    current_regime: str = Field(..., description="Current market regime")
    current_regime_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in current regime"
    )

    # Regime stress (leading indicator)
    regime_stress: float = Field(
        ...,
        ge=0.0,
        description="Stress on current regime (0=stable, >1=breaking)"
    )

    # Pivot detection
    pivot_detected: bool = Field(..., description="Is pivot detected?")
    pivot_probability: float = Field(..., ge=0.0, le=1.0, description="Pivot probability")
    expected_new_regime: Optional[str] = Field(None, description="Expected new regime")

    # Timing
    estimated_pivot_window_hours: Optional[float] = Field(
        None,
        ge=0.0,
        description="How soon will pivot occur?"
    )

    # Leading indicators
    leading_indicators: Dict[str, float] = Field(
        default_factory=dict,
        description="Indicator values contributing to alert"
    )

    # Alert level
    alert_level: Literal["INFO", "WATCH", "WARNING", "CRITICAL"] = Field(
        ...,
        description="Alert severity level"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def requires_action(self) -> bool:
        """Should downstream systems prepare for regime change?"""
        return self.alert_level in ["WARNING", "CRITICAL"]


@frozen
class RegimeSentinelState(BaseModel):
    """Internal state of regime sentinel."""

    regime_history: List[str] = Field(default_factory=list, description="Historical regimes")
    stress_history: List[float] = Field(default_factory=list, description="Historical stress levels")
    last_pivot: Optional[datetime] = Field(None, description="Last pivot timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
