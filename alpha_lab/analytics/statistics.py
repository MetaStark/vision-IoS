"""
Statistical Validation for Alpha Lab.

Provides statistical tests and validation for strategy performance:
- Bootstrap confidence intervals (standard and block)
- t-tests for excess returns
- Permutation tests
- Statistical significance scoring
"""

import numpy as np
from typing import Optional, Tuple
from scipy import stats

from alpha_lab.schemas import (
    BootstrapResult,
    TTestResult,
    PermutationTestResult,
    StatisticalValidation,
    EquityPoint,
)
from alpha_lab.analytics.metrics import calculate_returns_from_equity


def bootstrap_confidence_interval(
    data: np.ndarray,
    metric_func: callable,
    n_iterations: int = 10000,
    confidence_level: float = 0.95,
    random_seed: int = 42
) -> BootstrapResult:
    """
    Calculate bootstrap confidence interval for a metric.

    Args:
        data: Data array (e.g., returns)
        metric_func: Function that calculates metric from data
        n_iterations: Number of bootstrap iterations
        confidence_level: Confidence level (e.g., 0.95 for 95%)
        random_seed: Random seed for reproducibility

    Returns:
        Bootstrap result with confidence interval
    """
    np.random.seed(random_seed)

    # Calculate point estimate
    point_estimate = metric_func(data)

    # Bootstrap resampling
    n_samples = len(data)
    bootstrap_estimates = []

    for _ in range(n_iterations):
        # Resample with replacement
        resampled_data = np.random.choice(data, size=n_samples, replace=True)
        bootstrap_estimates.append(metric_func(resampled_data))

    bootstrap_estimates = np.array(bootstrap_estimates)

    # Calculate confidence interval
    alpha = 1 - confidence_level
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100

    ci_lower = np.percentile(bootstrap_estimates, lower_percentile)
    ci_upper = np.percentile(bootstrap_estimates, upper_percentile)

    # Calculate standard error and bias
    standard_error = np.std(bootstrap_estimates)
    bias = np.mean(bootstrap_estimates) - point_estimate

    return BootstrapResult(
        metric_name="custom_metric",
        point_estimate=float(point_estimate),
        confidence_interval_lower=float(ci_lower),
        confidence_interval_upper=float(ci_upper),
        confidence_level=confidence_level,
        bootstrap_iterations=n_iterations,
        standard_error=float(standard_error),
        bias=float(bias)
    )


def bootstrap_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.02,
    n_iterations: int = 10000,
    confidence_level: float = 0.95,
    annualization_factor: float = 252.0,
    random_seed: int = 42
) -> BootstrapResult:
    """
    Bootstrap confidence interval for Sharpe ratio.

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate
        n_iterations: Number of bootstrap iterations
        confidence_level: Confidence level
        annualization_factor: Factor to annualize returns
        random_seed: Random seed

    Returns:
        Bootstrap result for Sharpe ratio
    """
    def sharpe_func(r):
        if len(r) == 0 or np.std(r) == 0:
            return 0.0
        excess_returns = r - (risk_free_rate / annualization_factor)
        return (np.mean(excess_returns) / np.std(r)) * np.sqrt(annualization_factor)

    result = bootstrap_confidence_interval(
        data=returns,
        metric_func=sharpe_func,
        n_iterations=n_iterations,
        confidence_level=confidence_level,
        random_seed=random_seed
    )

    result.metric_name = "sharpe_ratio"
    return result


def block_bootstrap_confidence_interval(
    data: np.ndarray,
    metric_func: callable,
    block_size: Optional[int] = None,
    n_iterations: int = 10000,
    confidence_level: float = 0.95,
    random_seed: int = 42
) -> BootstrapResult:
    """
    Block bootstrap confidence interval (preserves autocorrelation).

    Args:
        data: Data array
        metric_func: Function that calculates metric
        block_size: Block size (if None, uses sqrt(n))
        n_iterations: Number of iterations
        confidence_level: Confidence level
        random_seed: Random seed

    Returns:
        Bootstrap result
    """
    np.random.seed(random_seed)

    n_samples = len(data)

    # Auto-select block size if not provided
    if block_size is None:
        block_size = int(np.sqrt(n_samples))

    # Calculate point estimate
    point_estimate = metric_func(data)

    # Block bootstrap
    bootstrap_estimates = []

    for _ in range(n_iterations):
        # Number of blocks needed
        n_blocks = int(np.ceil(n_samples / block_size))

        # Randomly select blocks with replacement
        resampled_data = []
        for _ in range(n_blocks):
            # Random starting position
            start_idx = np.random.randint(0, n_samples - block_size + 1)
            block = data[start_idx:start_idx + block_size]
            resampled_data.extend(block)

        # Trim to original length
        resampled_data = np.array(resampled_data[:n_samples])

        bootstrap_estimates.append(metric_func(resampled_data))

    bootstrap_estimates = np.array(bootstrap_estimates)

    # Calculate confidence interval
    alpha = 1 - confidence_level
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100

    ci_lower = np.percentile(bootstrap_estimates, lower_percentile)
    ci_upper = np.percentile(bootstrap_estimates, upper_percentile)

    standard_error = np.std(bootstrap_estimates)
    bias = np.mean(bootstrap_estimates) - point_estimate

    return BootstrapResult(
        metric_name="block_bootstrap",
        point_estimate=float(point_estimate),
        confidence_interval_lower=float(ci_lower),
        confidence_interval_upper=float(ci_upper),
        confidence_level=confidence_level,
        bootstrap_iterations=n_iterations,
        standard_error=float(standard_error),
        bias=float(bias)
    )


def test_excess_returns(
    returns: np.ndarray,
    risk_free_rate: float = 0.02,
    annualization_factor: float = 252.0,
    significance_level: float = 0.05
) -> TTestResult:
    """
    t-test for whether returns exceed risk-free rate.

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate
        annualization_factor: Factor to annualize returns
        significance_level: Significance level (e.g., 0.05)

    Returns:
        t-test result
    """
    # Calculate excess returns
    rf_per_period = risk_free_rate / annualization_factor
    excess_returns = returns - rf_per_period

    # One-sample t-test (test if mean > 0)
    t_statistic, p_value = stats.ttest_1samp(excess_returns, 0)

    # One-tailed p-value (testing if returns > risk-free rate)
    p_value_one_tailed = p_value / 2 if t_statistic > 0 else 1 - (p_value / 2)

    is_significant = p_value_one_tailed < significance_level

    if is_significant:
        conclusion = f"Strategy returns significantly exceed risk-free rate (p={p_value_one_tailed:.4f})"
    else:
        conclusion = f"Strategy returns do not significantly exceed risk-free rate (p={p_value_one_tailed:.4f})"

    return TTestResult(
        test_name="excess_returns_t_test",
        t_statistic=float(t_statistic),
        p_value=float(p_value_one_tailed),
        degrees_of_freedom=len(returns) - 1,
        significance_level=significance_level,
        is_significant=is_significant,
        conclusion=conclusion,
        null_hypothesis="Mean excess return = 0 (returns = risk-free rate)",
        alternative_hypothesis="Mean excess return > 0 (returns > risk-free rate)"
    )


def permutation_test_sharpe(
    returns: np.ndarray,
    risk_free_rate: float = 0.02,
    n_permutations: int = 10000,
    annualization_factor: float = 252.0,
    significance_level: float = 0.05,
    random_seed: int = 42
) -> PermutationTestResult:
    """
    Permutation test for Sharpe ratio significance.

    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate
        n_permutations: Number of permutations
        annualization_factor: Factor to annualize
        significance_level: Significance level
        random_seed: Random seed

    Returns:
        Permutation test result
    """
    np.random.seed(random_seed)

    # Calculate observed Sharpe ratio
    rf_per_period = risk_free_rate / annualization_factor
    excess_returns = returns - rf_per_period

    if np.std(excess_returns) == 0:
        observed_sharpe = 0.0
    else:
        observed_sharpe = (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(annualization_factor)

    # Generate null distribution by random shuffling
    null_sharpes = []

    for _ in range(n_permutations):
        # Shuffle returns
        shuffled = np.random.permutation(returns)
        shuffled_excess = shuffled - rf_per_period

        if np.std(shuffled_excess) == 0:
            sharpe = 0.0
        else:
            sharpe = (np.mean(shuffled_excess) / np.std(shuffled_excess)) * np.sqrt(annualization_factor)

        null_sharpes.append(sharpe)

    null_sharpes = np.array(null_sharpes)

    # Calculate p-value (one-tailed: observed > null)
    p_value = np.sum(null_sharpes >= observed_sharpe) / n_permutations

    is_significant = p_value < significance_level

    if is_significant:
        conclusion = f"Sharpe ratio is statistically significant (p={p_value:.4f})"
    else:
        conclusion = f"Sharpe ratio is not statistically significant (p={p_value:.4f})"

    return PermutationTestResult(
        test_name="sharpe_permutation_test",
        observed_statistic=float(observed_sharpe),
        p_value=float(p_value),
        n_permutations=n_permutations,
        significance_level=significance_level,
        is_significant=is_significant,
        conclusion=conclusion
    )


def validate_strategy_statistical_significance(
    equity_curve: list,
    risk_free_rate: float = 0.02,
    confidence_level: float = 0.95,
    significance_level: float = 0.05,
    n_bootstrap: int = 10000,
    random_seed: int = 42
) -> StatisticalValidation:
    """
    Complete statistical validation of a strategy.

    Args:
        equity_curve: List of EquityPoint objects
        risk_free_rate: Annual risk-free rate
        confidence_level: Confidence level for CIs
        significance_level: Significance level for tests
        n_bootstrap: Number of bootstrap iterations
        random_seed: Random seed

    Returns:
        Complete statistical validation
    """
    # Extract returns
    returns = calculate_returns_from_equity(equity_curve)

    # Bootstrap Sharpe ratio
    sharpe_bootstrap = bootstrap_sharpe_ratio(
        returns=returns,
        risk_free_rate=risk_free_rate,
        n_iterations=n_bootstrap,
        confidence_level=confidence_level,
        random_seed=random_seed
    )

    # t-test for excess returns
    excess_returns_test = test_excess_returns(
        returns=returns,
        risk_free_rate=risk_free_rate,
        significance_level=significance_level
    )

    # Permutation test for Sharpe
    sharpe_perm_test = permutation_test_sharpe(
        returns=returns,
        risk_free_rate=risk_free_rate,
        n_permutations=n_bootstrap,
        significance_level=significance_level,
        random_seed=random_seed
    )

    # Overall significance score
    # Average of individual test results
    significance_scores = []

    if excess_returns_test.is_significant:
        significance_scores.append(1.0)
    else:
        # Partial credit based on p-value
        significance_scores.append(max(0, 1 - (excess_returns_test.p_value / significance_level)))

    if sharpe_perm_test.is_significant:
        significance_scores.append(1.0)
    else:
        significance_scores.append(max(0, 1 - (sharpe_perm_test.p_value / significance_level)))

    overall_significance_score = np.mean(significance_scores)
    is_statistically_significant = overall_significance_score > 0.5

    # Warnings
    warnings = []

    if len(returns) < 100:
        warnings.append("Small sample size (< 100 observations) - results may be unreliable")

    if sharpe_bootstrap.standard_error > abs(sharpe_bootstrap.point_estimate) * 0.5:
        warnings.append("Large standard error in Sharpe ratio - estimate is imprecise")

    # Check for autocorrelation (simplified)
    if len(returns) > 1:
        autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        if abs(autocorr) > 0.3:
            warnings.append(f"Significant autocorrelation detected ({autocorr:.2f}) - consider block bootstrap")

    return StatisticalValidation(
        sharpe_bootstrap=sharpe_bootstrap,
        returns_bootstrap=None,  # Optional
        excess_returns_ttest=excess_returns_test,
        sharpe_permutation=sharpe_perm_test,
        overall_significance_score=float(overall_significance_score),
        is_statistically_significant=is_statistically_significant,
        warnings=warnings
    )
