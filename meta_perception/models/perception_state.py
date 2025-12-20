"""Perception state models."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class PerceptionState(BaseModel):
    """
    Immutable perception state at a point in time.

    This is the PRIMARY state object that flows through the meta-brain.
    """

    state_id: str = Field(..., description="Deterministic state ID")
    timestamp: datetime = Field(..., description="State timestamp")

    # Current assessments
    market_entropy: float = Field(..., ge=0.0, description="H(market) in bits")
    feature_entropy: Dict[str, float] = Field(
        default_factory=dict,
        description="Entropy per feature"
    )
    noise_score: float = Field(..., ge=0.0, le=1.0, description="Noise level")
    signal_quality: float = Field(..., ge=0.0, le=1.0, description="Signal quality")

    # Intent & behavior
    participant_intent: Dict[str, float] = Field(
        default_factory=dict,
        description="Intent probabilities: {long: 0.7, short: 0.3}"
    )
    market_pressure: Literal["LONG", "SHORT", "NEUTRAL", "UNKNOWN"] = Field(
        default="UNKNOWN",
        description="Dominant market pressure"
    )

    # Reflexivity
    reflexivity_coefficient: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Correlation between decisions and market moves"
    )
    system_impact_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated system impact on market"
    )

    # Regime perception
    current_regime: Optional[str] = Field(None, description="Current market regime")
    regime_confidence: float = Field(..., ge=0.0, le=1.0, description="Regime confidence")
    regime_stress: float = Field(..., ge=0.0, description="Regime stress indicator")
    regime_pivot_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability of regime pivot"
    )

    # Shocks
    active_shocks: List[str] = Field(
        default_factory=list,
        description="List of shock_ids currently active"
    )
    shock_intensity: float = Field(..., ge=0.0, description="Aggregate shock intensity")

    # System uncertainty
    total_uncertainty: float = Field(..., ge=0.0, description="Total system uncertainty")
    should_act: bool = Field(..., description="Master override: can system act?")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def with_updates(self, **kwargs) -> "PerceptionState":
        """Create new state with updates (immutable pattern)."""
        current_data = self.model_dump()
        current_data.update(kwargs)
        return PerceptionState(**current_data)


@frozen
class PerceptionSnapshot(BaseModel):
    """
    Complete snapshot of perception state + all sub-analyses.

    This is the ARTIFACT that gets serialized to JSON.
    """

    snapshot_id: str = Field(..., description="Snapshot identifier")
    timestamp: datetime = Field(..., description="Snapshot timestamp")
    state: PerceptionState = Field(..., description="Perception state")

    # Sub-module outputs (forward references resolved at runtime)
    entropy_metrics: Any = Field(..., description="EntropyMetrics")
    noise_score: Any = Field(..., description="NoiseScore")
    intent_score: Any = Field(..., description="IntentScore")
    reflexivity_score: Any = Field(..., description="ReflexivityScore")
    shock_events: List[Any] = Field(default_factory=list, description="List[ShockEvent]")
    regime_alert: Optional[Any] = Field(None, description="Optional[RegimeAlert]")

    # Metadata
    computation_time_ms: float = Field(..., gt=0.0, description="Computation time in ms")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def has_active_shocks(self) -> bool:
        """Check if there are active shocks."""
        return len(self.shock_events) > 0

    @property
    def is_actionable(self) -> bool:
        """Can downstream systems act on this perception?"""
        return self.state.should_act and self.noise_score.is_acceptable


@frozen
class PerceptionDelta(BaseModel):
    """
    Changes between two perception states.

    Used for incremental updates and alerting.
    """

    delta_id: str = Field(..., description="Delta identifier")
    from_snapshot_id: str = Field(..., description="Source snapshot ID")
    to_snapshot_id: str = Field(..., description="Target snapshot ID")
    timestamp: datetime = Field(..., description="Delta timestamp")

    # Changes
    entropy_delta: float = Field(..., description="Change in entropy")
    noise_delta: float = Field(..., description="Change in noise level")
    intent_shift: Dict[str, float] = Field(
        default_factory=dict,
        description="Intent probability shifts"
    )
    reflexivity_delta: float = Field(..., description="Change in reflexivity")
    regime_changed: bool = Field(..., description="Did regime change?")
    new_regime: Optional[str] = Field(None, description="New regime if changed")

    # New shocks detected
    shocks_added: List[Any] = Field(
        default_factory=list,
        description="New shock events"
    )
    shocks_resolved: List[str] = Field(
        default_factory=list,
        description="Resolved shock IDs"
    )

    # Alerts
    requires_attention: bool = Field(
        ...,
        description="Should operator be alerted?"
    )
    alert_priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        ...,
        description="Alert priority level"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
