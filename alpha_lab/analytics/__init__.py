"""
Analytics modules for Alpha Lab - metrics and statistical validation.
"""

from alpha_lab.analytics.metrics import (
    calculate_performance_metrics,
    calculate_returns_from_equity,
)

from alpha_lab.analytics.statistics import (
    bootstrap_confidence_interval,
    bootstrap_sharpe_ratio,
    block_bootstrap_confidence_interval,
    test_excess_returns,
    permutation_test_sharpe,
    validate_strategy_statistical_significance,
)

__all__ = [
    # Metrics
    "calculate_performance_metrics",
    "calculate_returns_from_equity",
    # Statistics
    "bootstrap_confidence_interval",
    "bootstrap_sharpe_ratio",
    "block_bootstrap_confidence_interval",
    "test_excess_returns",
    "permutation_test_sharpe",
    "validate_strategy_statistical_significance",
]
