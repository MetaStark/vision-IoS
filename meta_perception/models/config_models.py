"""Configuration models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from meta_perception.models.base import frozen


@frozen
class PerceptionConfig(BaseModel):
    """Configuration for meta-perception engine."""

    config_id: str = Field(..., description="Configuration identifier")
    version: str = Field(default="1.0.0", description="Configuration version")

    # Thresholds
    noise_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Noise level above which system should not act"
    )
    entropy_spike_threshold_std_devs: float = Field(
        default=3.0,
        gt=0.0,
        description="Standard deviations for entropy spike detection"
    )
    shock_intensity_threshold: float = Field(
        default=2.0,
        gt=0.0,
        description="Shock intensity threshold"
    )
    regime_stress_threshold: float = Field(
        default=1.0,
        gt=0.0,
        description="Regime stress threshold for pivot detection"
    )
    uncertainty_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Total uncertainty threshold"
    )

    # Time windows
    entropy_window_minutes: int = Field(
        default=60,
        gt=0,
        description="Rolling window for entropy computation (minutes)"
    )
    intent_lookback_hours: int = Field(
        default=24,
        gt=0,
        description="Lookback window for intent analysis (hours)"
    )
    reflexivity_window_days: int = Field(
        default=7,
        gt=0,
        description="Window for reflexivity analysis (days)"
    )

    # Feature weights (for uncertainty aggregation)
    feature_weights: Dict[str, float] = Field(
        default_factory=dict,
        description="Weights for feature importance"
    )

    # Uncertainty weights
    uncertainty_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "entropy": 0.25,
            "noise": 0.35,
            "reflexivity": 0.15,
            "regime_stress": 0.25
        },
        description="Weights for uncertainty aggregation"
    )

    # Regime configuration
    regime_levels: List[str] = Field(
        default_factory=lambda: ["BULL", "BEAR", "CRISIS", "NEUTRAL"],
        description="Supported regime levels"
    )

    # Diagnostic settings
    enable_diagnostics: bool = Field(
        default=True,
        description="Enable diagnostic logging"
    )
    enable_feature_importance: bool = Field(
        default=True,
        description="Enable feature importance computation"
    )

    # Performance settings
    max_computation_time_ms: float = Field(
        default=150.0,
        gt=0.0,
        description="Maximum allowed computation time (ms)"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
