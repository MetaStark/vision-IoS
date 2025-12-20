"""Stress scenario models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, List
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class StressScenarioResult(BaseModel):
    """Result from running a single stress scenario."""

    result_id: str = Field(..., description="Result identifier")
    scenario_name: str = Field(..., description="Scenario name")
    timestamp: datetime = Field(..., description="Execution timestamp")

    # Test result
    passed: bool = Field(..., description="Did scenario pass?")

    # Perception snapshot from scenario
    perception_snapshot: Any = Field(..., description="PerceptionSnapshot from scenario")

    # Expected vs actual
    expected_behavior: Dict[str, Any] = Field(
        ...,
        description="Expected behavior from scenario definition"
    )
    actual_behavior: Dict[str, Any] = Field(
        ...,
        description="Actual observed behavior"
    )

    # Deviations
    deviations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Deviations from expected behavior"
    )

    # Execution metrics
    execution_time_ms: float = Field(..., gt=0.0, description="Execution time (ms)")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


@frozen
class StressScenarioSummary(BaseModel):
    """Summary of all stress scenario runs."""

    summary_id: str = Field(..., description="Summary identifier")
    timestamp: datetime = Field(..., description="Summary timestamp")

    total_scenarios: int = Field(..., ge=0, description="Total scenarios run")
    passed: int = Field(..., ge=0, description="Scenarios passed")
    failed: int = Field(..., ge=0, description="Scenarios failed")

    pass_rate: float = Field(..., ge=0.0, le=1.0, description="Pass rate (passed/total)")

    results: List[StressScenarioResult] = Field(
        ...,
        description="Individual scenario results"
    )

    # Aggregate metrics
    avg_execution_time_ms: float = Field(..., gt=0.0, description="Average execution time")
    max_execution_time_ms: float = Field(..., gt=0.0, description="Maximum execution time")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
