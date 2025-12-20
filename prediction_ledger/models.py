"""
Prediction Ledger Data Models

Pydantic v2 models for forecasts, outcomes, evaluations, and calibration.

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================================
# FORECAST RECORDS
# ============================================================================

class ForecastRecord(BaseModel):
    """
    A single forecast record.

    Captures:
    - What was predicted (target_id, forecast_value)
    - When it was predicted (timestamp, horizon)
    - Input state that led to this forecast (input_state_hash)
    - Link to scenario set if applicable
    """
    model_config = ConfigDict(frozen=True)

    forecast_id: str = Field(
        ...,
        description="Unique identifier for this forecast"
    )
    timestamp: datetime = Field(
        ...,
        description="When this forecast was made"
    )
    horizon: timedelta = Field(
        ...,
        description="Forecast horizon (e.g., 5 days, 10 days)"
    )
    target_id: str = Field(
        ...,
        description="ID of the forecast target (links to ForecastTargetDefinition)"
    )
    target_type: str = Field(
        ...,
        description="Type of forecast target"
    )
    forecast_value: Any = Field(
        ...,
        description="Predicted value (probability, direction, score, etc.)"
    )
    forecast_distribution: Dict[str, float] | None = Field(
        default=None,
        description="Optional probability distribution (e.g., for binned forecasts)"
    )
    scenario_set_id: str | None = Field(
        default=None,
        description="ID of scenario set this forecast came from (if applicable)"
    )
    input_state_hash: str = Field(
        ...,
        description="SHA256 hash of input state that generated this forecast"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @property
    def forecast_end_timestamp(self) -> datetime:
        """Timestamp when forecast is expected to be realized."""
        return self.timestamp + self.horizon


# ============================================================================
# OUTCOME RECORDS
# ============================================================================

class OutcomeRecord(BaseModel):
    """
    A realized outcome record.

    Captures what actually happened, to be matched against forecasts.
    """
    model_config = ConfigDict(frozen=True)

    outcome_id: str = Field(
        ...,
        description="Unique identifier for this outcome"
    )
    timestamp: datetime = Field(
        ...,
        description="When this outcome was realized"
    )
    target_id: str = Field(
        ...,
        description="ID of the forecast target"
    )
    target_type: str = Field(
        ...,
        description="Type of forecast target"
    )
    realized_value: Any = Field(
        ...,
        description="Actual realized value"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


# ============================================================================
# EVALUATION RECORDS
# ============================================================================

class EvaluationRecord(BaseModel):
    """
    Evaluation of forecast performance.

    Records metrics like Brier score, calibration error, hit rate, etc.
    """
    model_config = ConfigDict(frozen=True)

    evaluation_id: str = Field(
        ...,
        description="Unique identifier for this evaluation"
    )
    timestamp: datetime = Field(
        ...,
        description="When this evaluation was computed"
    )
    target_id: str = Field(
        ...,
        description="ID of the forecast target being evaluated"
    )
    target_type: str = Field(
        ...,
        description="Type of forecast target"
    )
    metric_name: str = Field(
        ...,
        description="Name of metric (brier_score, calibration_error, hit_rate, etc.)"
    )
    metric_value: float = Field(
        ...,
        description="Computed metric value"
    )
    sample_size: int = Field(
        ...,
        ge=1,
        description="Number of forecast-outcome pairs in this evaluation"
    )
    period_start: datetime = Field(
        ...,
        description="Start of evaluation period"
    )
    period_end: datetime = Field(
        ...,
        description="End of evaluation period"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (confidence intervals, etc.)"
    )


# ============================================================================
# CALIBRATION MODELS (Extended v1.1)
# ============================================================================

class CalibrationBin(BaseModel):
    """
    A single bin in a calibration curve.

    Represents forecasts grouped by predicted probability and their realized frequency.
    """
    model_config = ConfigDict(frozen=True)

    lower_bound: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Lower probability bound for this bin"
    )
    upper_bound: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Upper probability bound for this bin"
    )
    forecast_mean: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Mean forecast probability in this bin"
    )
    observed_frequency: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Actual realization rate in this bin"
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of forecasts in this bin"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @property
    def calibration_error(self) -> float:
        """Absolute calibration error for this bin."""
        return abs(self.forecast_mean - self.observed_frequency)

    # Backward compatibility
    @property
    def forecast_probability(self) -> float:
        """Alias for forecast_mean (backward compat)."""
        return self.forecast_mean

    @property
    def realized_frequency(self) -> float:
        """Alias for observed_frequency (backward compat)."""
        return self.observed_frequency

    @property
    def sample_size(self) -> int:
        """Alias for count (backward compat)."""
        return self.count


class CalibrationCurve(BaseModel):
    """
    Calibration curve for a forecast target.

    Shows how well-calibrated forecasts are across different probability levels.
    Well-calibrated forecasts have forecast_mean ≈ observed_frequency for all bins.
    """
    model_config = ConfigDict(frozen=True)

    curve_id: str = Field(
        ...,
        description="Unique identifier for this calibration curve"
    )
    target_type: str = Field(
        ...,
        description="Type of forecast target (e.g., REGIME_TRANSITION_PROB)"
    )
    horizon_bucket: str = Field(
        ...,
        description="Horizon bucket (e.g., '5d', '10d')"
    )
    bins: List[CalibrationBin] = Field(
        ...,
        description="Calibration bins (typically 10 bins)"
    )
    period_start: datetime = Field(
        ...,
        description="Start of calibration period"
    )
    period_end: datetime = Field(
        ...,
        description="End of calibration period"
    )
    sample_size: int = Field(
        ...,
        ge=0,
        description="Total number of forecast-outcome pairs"
    )
    mean_calibration_error: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Weighted mean calibration error across all bins"
    )
    created_at: datetime = Field(
        ...,
        description="When this curve was generated"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    # Backward compatibility
    @property
    def target_id(self) -> str:
        """Alias for backward compatibility."""
        return self.metadata.get("target_id", self.target_type)

    @property
    def total_samples(self) -> int:
        """Alias for sample_size (backward compat)."""
        return self.sample_size


# ============================================================================
# SKILL METRICS MODELS (New v1.1)
# ============================================================================

class SkillMetrics(BaseModel):
    """Collection of skill metrics for forecast evaluation."""
    model_config = ConfigDict(frozen=True)

    brier_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model Brier score (lower is better)"
    )
    brier_score_baseline: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Baseline Brier score for comparison"
    )
    brier_skill_score: float = Field(
        ...,
        description="BSS = 1 - (BS_model / BS_baseline), >0 means skill"
    )
    directional_accuracy: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Hit rate for directional forecasts (if applicable)"
    )
    mean_absolute_error: float | None = Field(
        None,
        ge=0.0,
        description="MAE for continuous forecasts (if applicable)"
    )
    log_score: float | None = Field(
        None,
        description="Logarithmic score (if applicable)"
    )


class SkillReport(BaseModel):
    """Comprehensive skill assessment report for a target type and horizon."""
    model_config = ConfigDict(frozen=True)

    report_id: str = Field(
        ...,
        description="Unique identifier for this report"
    )
    target_type: str = Field(
        ...,
        description="Type of forecast target"
    )
    horizon_bucket: str = Field(
        ...,
        description="Horizon bucket (e.g., '5d')"
    )
    model_id: str | None = Field(
        None,
        description="Strategy/model identifier (if applicable)"
    )
    period_start: datetime = Field(
        ...,
        description="Start of evaluation period"
    )
    period_end: datetime = Field(
        ...,
        description="End of evaluation period"
    )

    metrics: SkillMetrics = Field(
        ...,
        description="Computed skill metrics"
    )
    sample_size: int = Field(
        ...,
        ge=0,
        description="Number of forecast-outcome pairs evaluated"
    )
    baseline_description: str = Field(
        ...,
        description="Description of baseline used (e.g., 'historical_frequency')"
    )

    # Quality flags
    is_well_calibrated: bool = Field(
        ...,
        description="True if mean calibration error < 0.10"
    )
    has_positive_skill: bool = Field(
        ...,
        description="True if Brier skill score > 0.05"
    )
    sufficient_sample: bool = Field(
        ...,
        description="True if sample size >= 20"
    )

    created_at: datetime = Field(
        ...,
        description="When this report was generated"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


# ============================================================================
# RECONCILIATION MODELS
# ============================================================================

class ForecastOutcomePair(BaseModel):
    """
    A matched forecast-outcome pair.

    Used for evaluation and calibration computation.
    """
    model_config = ConfigDict(frozen=True)

    forecast: ForecastRecord = Field(
        ...,
        description="Forecast record"
    )
    outcome: OutcomeRecord = Field(
        ...,
        description="Outcome record"
    )
    match_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this match (1.0 = exact match)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @property
    def is_binary_match(self) -> bool:
        """Check if forecast and outcome are binary values (0 or 1)."""
        return (
            isinstance(self.forecast.forecast_value, (int, float))
            and isinstance(self.outcome.realized_value, (int, float))
            and self.forecast.forecast_value in [0, 1]
            and self.outcome.realized_value in [0, 1]
        )

    @property
    def squared_error(self) -> float:
        """Squared error for Brier score computation."""
        if isinstance(self.forecast.forecast_value, (int, float)) and isinstance(
            self.outcome.realized_value, (int, float)
        ):
            return (self.forecast.forecast_value - self.outcome.realized_value) ** 2
        raise ValueError("Cannot compute squared error for non-numeric values")


# ============================================================================
# CONFIGURATION
# ============================================================================

class ReconciliationConfig(BaseModel):
    """Configuration for forecast-outcome reconciliation."""
    model_config = ConfigDict(frozen=True)

    time_window_tolerance: timedelta = Field(
        default=timedelta(hours=6),
        description="Tolerance window for matching forecast end time to outcome time"
    )
    require_exact_target_match: bool = Field(
        default=True,
        description="Whether to require exact target_id match"
    )
    allow_multiple_matches: bool = Field(
        default=False,
        description="Whether to allow one forecast to match multiple outcomes"
    )


class EvaluationConfig(BaseModel):
    """Configuration for evaluation computation."""
    model_config = ConfigDict(frozen=True)

    n_calibration_bins: int = Field(
        default=10,
        ge=5,
        le=20,
        description="Number of bins for calibration curve"
    )
    min_samples_per_bin: int = Field(
        default=5,
        ge=1,
        description="Minimum samples required per calibration bin"
    )
    confidence_level: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Confidence level for confidence intervals"
    )
