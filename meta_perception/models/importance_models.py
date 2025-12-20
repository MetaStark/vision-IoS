"""Feature importance models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Tuple
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class FeatureImportance(BaseModel):
    """Track feature importance for each perception computation."""

    report_id: str = Field(..., description="Report identifier")
    timestamp: datetime = Field(..., description="Report timestamp")
    perception_snapshot_id: str = Field(..., description="Associated snapshot ID")

    # Global feature importance
    global_importance: Dict[str, float] = Field(
        ...,
        description="Feature → importance score [0, 1]"
    )

    # Per-module feature importance
    entropy_drivers: Dict[str, float] = Field(
        default_factory=dict,
        description="Features driving entropy computation"
    )
    intent_drivers: Dict[str, float] = Field(
        default_factory=dict,
        description="Features driving intent inference"
    )
    reflexivity_drivers: Dict[str, float] = Field(
        default_factory=dict,
        description="Features driving reflexivity computation"
    )
    shock_drivers: Dict[str, float] = Field(
        default_factory=dict,
        description="Features driving shock detection"
    )

    # Top features
    top_5_features: List[Tuple[str, float]] = Field(
        ...,
        description="[(feature, importance), ...] sorted by importance"
    )

    # Change tracking
    importance_delta: Dict[str, float] = Field(
        default_factory=dict,
        description="Change in importance vs previous cycle"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
