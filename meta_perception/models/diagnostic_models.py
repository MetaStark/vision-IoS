"""Diagnostic models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, List
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class DiagnosticLog(BaseModel):
    """Detailed diagnostic for any perception computation."""

    log_id: str = Field(..., description="Log identifier")
    timestamp: datetime = Field(..., description="Log timestamp")
    module: str = Field(..., description="Module name (e.g., 'entropy', 'intent')")
    computation: str = Field(..., description="Function name")

    # Input summary
    inputs: Dict[str, Any] = Field(..., description="Input summary")

    # Output
    output_value: Any = Field(..., description="Output value")
    output_interpretation: str = Field(..., description="Human-readable interpretation")

    # Numerical breakdown
    computation_steps: List[Dict[str, Any]] = Field(
        ...,
        description="Step-by-step numerical trace"
    )

    # Thresholds & comparisons
    thresholds_used: Dict[str, float] = Field(
        default_factory=dict,
        description="Thresholds applied"
    )
    comparisons: List[str] = Field(
        default_factory=list,
        description="Human-readable comparisons"
    )

    # Attribution
    contributing_factors: Dict[str, float] = Field(
        default_factory=dict,
        description="Which inputs contributed how much"
    )

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
