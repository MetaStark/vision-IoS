"""
Report schemas for Alpha Lab.

Defines the structure of alpha reports, statistical tests,
and pass/fail criteria for strategy validation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import datetime
from alpha_lab.schemas.result_schemas import PerformanceMetrics


class BootstrapResult(BaseModel):
    """Result of bootstrap analysis for a metric."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    metric_name: str = Field(..., description="Name of bootstrapped metric")
    point_estimate: float = Field(..., description="Point estimate of metric")
    confidence_interval_lower: float = Field(
        ...,
        description="Lower bound of confidence interval"
    )
    confidence_interval_upper: float = Field(
        ...,
        description="Upper bound of confidence interval"
    )
    confidence_level: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Confidence level (e.g., 0.95)"
    )
    bootstrap_iterations: int = Field(
        ...,
        ge=1,
        description="Number of bootstrap iterations"
    )
    standard_error: float = Field(
        ...,
        ge=0,
        description="Bootstrap standard error"
    )
    bias: float = Field(..., description="Bootstrap bias estimate")


class TTestResult(BaseModel):
    """Result of t-test for statistical significance."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    test_name: str = Field(..., description="Name of the test")
    t_statistic: float = Field(..., description="t-test statistic")
    p_value: float = Field(..., ge=0, le=1, description="p-value")
    degrees_of_freedom: int = Field(..., ge=1, description="Degrees of freedom")
    significance_level: float = Field(
        ...,
        gt=0,
        lt=1,
        description="Significance level (e.g., 0.05)"
    )
    is_significant: bool = Field(
        ...,
        description="Whether result is statistically significant"
    )
    conclusion: str = Field(..., description="Human-readable conclusion")
    null_hypothesis: str = Field(..., description="Null hypothesis tested")
    alternative_hypothesis: str = Field(
        ...,
        description="Alternative hypothesis"
    )


class PermutationTestResult(BaseModel):
    """Result of permutation test."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    test_name: str = Field(..., description="Name of the test")
    observed_statistic: float = Field(..., description="Observed test statistic")
    p_value: float = Field(..., ge=0, le=1, description="p-value")
    n_permutations: int = Field(..., ge=1, description="Number of permutations")
    significance_level: float = Field(..., description="Significance level")
    is_significant: bool = Field(..., description="Whether significant")
    conclusion: str = Field(..., description="Human-readable conclusion")


class StatisticalValidation(BaseModel):
    """Complete statistical validation of a strategy."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Bootstrap results
    sharpe_bootstrap: BootstrapResult = Field(
        ...,
        description="Bootstrap analysis of Sharpe ratio"
    )
    returns_bootstrap: Optional[BootstrapResult] = Field(
        default=None,
        description="Bootstrap analysis of returns"
    )

    # Hypothesis tests
    excess_returns_ttest: TTestResult = Field(
        ...,
        description="t-test for excess returns vs risk-free rate"
    )
    sharpe_permutation: Optional[PermutationTestResult] = Field(
        default=None,
        description="Permutation test for Sharpe ratio"
    )

    # Overall assessment
    overall_significance_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="Overall statistical significance score (0-1)"
    )
    is_statistically_significant: bool = Field(
        ...,
        description="Whether strategy shows significant alpha"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Statistical warnings (e.g., small sample, autocorrelation)"
    )


class PassFailCriterion(BaseModel):
    """Single pass/fail criterion for strategy validation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    criterion_name: str = Field(..., description="Name of the criterion")
    criterion_type: str = Field(
        ...,
        description="Type: 'performance', 'risk', 'statistical', 'trading'"
    )
    threshold: float = Field(..., description="Threshold value")
    actual: float = Field(..., description="Actual value achieved")
    comparison: str = Field(
        ...,
        pattern=r'^(>|>=|<|<=|==)$',
        description="Comparison operator"
    )
    passed: bool = Field(..., description="Whether criterion was met")
    weight: float = Field(
        default=1.0,
        ge=0,
        description="Weight of this criterion (for scoring)"
    )
    description: str = Field(..., description="Human-readable description")


class AlphaReportSummary(BaseModel):
    """Executive summary of alpha report."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    conclusion: str = Field(
        ...,
        pattern=r'^(PASS|FAIL|CONDITIONAL)$',
        description="Overall conclusion: PASS, FAIL, or CONDITIONAL"
    )
    confidence_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in strategy viability (0-1)"
    )
    overall_grade: str = Field(
        ...,
        pattern=r'^[A-F][+-]?$',
        description="Letter grade (A+ to F)"
    )
    key_findings: List[str] = Field(
        ...,
        min_length=1,
        description="Key findings and highlights"
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Strategy strengths"
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="Strategy weaknesses"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings and concerns"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improvement"
    )


class PassFailThresholds(BaseModel):
    """Configurable thresholds for pass/fail criteria."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    min_sharpe_ratio: float = Field(default=1.0, description="Minimum Sharpe ratio")
    max_drawdown: float = Field(
        default=-0.25,
        le=0,
        description="Maximum acceptable drawdown (negative)"
    )
    min_total_return: float = Field(
        default=0.0,
        description="Minimum total return"
    )
    min_trade_count: int = Field(
        default=20,
        ge=0,
        description="Minimum number of trades"
    )
    max_correlation_to_benchmark: Optional[float] = Field(
        default=None,
        ge=-1,
        le=1,
        description="Maximum correlation to benchmark"
    )
    min_win_rate: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Minimum win rate"
    )
    max_time_underwater_pct: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Maximum time in drawdown"
    )
    min_profit_factor: Optional[float] = Field(
        default=None,
        ge=0,
        description="Minimum profit factor"
    )
    statistical_significance_level: float = Field(
        default=0.05,
        gt=0,
        lt=1,
        description="Required significance level"
    )


class AlphaReport(BaseModel):
    """Complete institutional-grade alpha report."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    report_id: str = Field(..., description="Unique report identifier")
    report_type: str = Field(
        ...,
        pattern=r'^(strategy_evaluation|experiment_summary|portfolio_analysis)$',
        description="Type of report"
    )
    report_version: str = Field(
        default="1.0.0",
        description="Report schema version"
    )

    # Subject
    strategy_id: str = Field(..., description="Strategy being evaluated")
    backtest_id: str = Field(..., description="Backtest ID")
    experiment_id: Optional[str] = Field(
        default=None,
        description="Experiment ID if applicable"
    )

    # Summary
    summary: AlphaReportSummary = Field(..., description="Executive summary")

    # Performance
    performance_metrics: PerformanceMetrics = Field(
        ...,
        description="Detailed performance metrics"
    )

    # Statistical validation
    statistical_validation: StatisticalValidation = Field(
        ...,
        description="Statistical test results"
    )

    # Pass/fail analysis
    pass_fail_criteria: List[PassFailCriterion] = Field(
        ...,
        description="All pass/fail criteria evaluated"
    )
    criteria_passed_count: int = Field(
        ...,
        ge=0,
        description="Number of criteria passed"
    )
    criteria_total_count: int = Field(
        ...,
        ge=0,
        description="Total number of criteria"
    )
    criteria_pass_rate: float = Field(
        ...,
        ge=0,
        le=1,
        description="Pass rate (passed / total)"
    )

    # Artefacts
    artefacts: Dict[str, str] = Field(
        ...,
        description="Paths to generated artefacts (plots, data files)"
    )

    # Metadata
    thresholds_used: PassFailThresholds = Field(
        ...,
        description="Thresholds used for evaluation"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When report was generated"
    )
    generated_by: str = Field(
        default="Alpha Lab v1.0",
        description="System that generated report"
    )


class ExperimentReport(BaseModel):
    """Report summarizing an entire experiment (parameter sweep)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    report_id: str = Field(..., description="Report identifier")
    experiment_id: str = Field(..., description="Experiment identifier")
    experiment_name: str = Field(..., description="Experiment name")

    # Summary
    total_runs: int = Field(..., ge=0, description="Total parameter combinations")
    successful_runs: int = Field(..., ge=0, description="Successful runs")
    failed_runs: int = Field(..., ge=0, description="Failed runs")

    # Best performers
    top_performers: List[Dict[str, Any]] = Field(
        ...,
        description="Top performing parameter combinations"
    )

    # Parameter sensitivity
    parameter_sensitivity: Dict[str, Any] = Field(
        ...,
        description="Analysis of parameter impact on performance"
    )

    # Robustness analysis
    sharpe_distribution: Dict[str, float] = Field(
        ...,
        description="Distribution statistics of Sharpe ratios"
    )
    return_distribution: Dict[str, float] = Field(
        ...,
        description="Distribution statistics of returns"
    )

    # Recommendations
    recommended_parameters: Dict[str, Any] = Field(
        ...,
        description="Recommended parameter values"
    )
    parameter_stability_score: float = Field(
        ...,
        ge=0,
        le=1,
        description="How stable performance is across parameters"
    )

    # Artefacts
    artefacts: Dict[str, str] = Field(
        default_factory=dict,
        description="Generated plots and files"
    )

    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When report was generated"
    )
