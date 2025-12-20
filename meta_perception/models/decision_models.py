"""Decision models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class MetaPerceptionDecision(BaseModel):
    """
    High-level decision output from meta-perception layer.

    This is what gets passed to Runtime Decision Engine.
    """

    decision_id: str = Field(..., description="Decision identifier")
    timestamp: datetime = Field(..., description="Decision timestamp")

    # Core decision
    should_act: bool = Field(..., description="Master override")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Decision confidence")

    # Recommended actions
    recommended_risk_mode: Optional[Literal["NORMAL", "CAUTIOUS", "DEFENSIVE"]] = Field(
        None,
        description="Recommended risk mode"
    )
    recommended_leverage_adjustment: Optional[float] = Field(
        None,
        description="Recommended leverage multiplier"
    )

    # Alerting
    alert_operator: bool = Field(..., description="Should alert operator?")
    alert_priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        ...,
        description="Alert priority"
    )
    alert_message: Optional[str] = Field(None, description="Alert message")

    # Rationale
    rationale: str = Field(..., description="Human-readable explanation")

    # Supporting data
    perception_snapshot_id: str = Field(..., description="Associated snapshot ID")
    key_factors: List[str] = Field(
        default_factory=list,
        description="Key factors driving decision"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


@frozen
class MetaPerceptionInput(BaseModel):
    """All inputs required for perception cycle."""

    timestamp: datetime = Field(..., description="Input timestamp")

    # Market data
    market_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Prices, volumes, etc."
    )

    # Alpha Graph
    alpha_graph_snapshot: Optional[Dict[str, Any]] = Field(
        None,
        description="AlphaGraphSnapshot as dict"
    )

    # Portfolio state
    portfolio_metrics: Optional[Dict[str, Any]] = Field(
        None,
        description="Portfolio metrics"
    )

    # Recent decisions
    recent_decisions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent decision history"
    )

    # Governance events
    governance_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Model governance events"
    )

    # Feature data
    features: Dict[str, float] = Field(
        default_factory=dict,
        description="Feature values"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


@frozen
class MetaPerceptionOutput(BaseModel):
    """Complete output from perception cycle."""

    snapshot: Any = Field(..., description="PerceptionSnapshot")
    delta: Optional[Any] = Field(None, description="Optional PerceptionDelta")
    decision: MetaPerceptionDecision = Field(..., description="Perception decision")

    # Artifacts
    artifacts: Dict[str, str] = Field(
        default_factory=dict,
        description="Paths to saved JSON artifacts"
    )

    computation_time_ms: float = Field(..., gt=0.0, description="Computation time (ms)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
