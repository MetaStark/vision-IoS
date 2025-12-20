"""
Alpha Lab Schemas Package.

Comprehensive Pydantic schemas for all Alpha Lab data structures.
"""

from alpha_lab.schemas.strategy_schemas import (
    StrategyType,
    RebalanceFrequency,
    PositionSizingMethod,
    TradeEngineConfig,
    StrategyDefinition,
    ProposedTrade,
    ExecutedTrade,
)

from alpha_lab.schemas.experiment_schemas import (
    BacktestConfig,
    ExecutionConfig,
    MetricsConfig,
    ParameterGrid,
    ExperimentConfig,
    PortfolioConfig,
)

from alpha_lab.schemas.result_schemas import (
    PerformanceMetrics,
    EquityPoint,
    TradeRecord,
    ExecutionStats,
    BacktestResult,
    ExperimentRun,
    ExperimentResult,
    PortfolioResult,
)

from alpha_lab.schemas.report_schemas import (
    BootstrapResult,
    TTestResult,
    PermutationTestResult,
    StatisticalValidation,
    PassFailCriterion,
    AlphaReportSummary,
    PassFailThresholds,
    AlphaReport,
    ExperimentReport,
)

__all__ = [
    # Strategy schemas
    "StrategyType",
    "RebalanceFrequency",
    "PositionSizingMethod",
    "TradeEngineConfig",
    "StrategyDefinition",
    "ProposedTrade",
    "ExecutedTrade",
    # Experiment schemas
    "BacktestConfig",
    "ExecutionConfig",
    "MetricsConfig",
    "ParameterGrid",
    "ExperimentConfig",
    "PortfolioConfig",
    # Result schemas
    "PerformanceMetrics",
    "EquityPoint",
    "TradeRecord",
    "ExecutionStats",
    "BacktestResult",
    "ExperimentRun",
    "ExperimentResult",
    "PortfolioResult",
    # Report schemas
    "BootstrapResult",
    "TTestResult",
    "PermutationTestResult",
    "StatisticalValidation",
    "PassFailCriterion",
    "AlphaReportSummary",
    "PassFailThresholds",
    "AlphaReport",
    "ExperimentReport",
]
