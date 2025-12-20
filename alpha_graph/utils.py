"""
Alpha Graph Utilities

Pure utility functions for correlation, statistics, and data manipulation.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import math
from alpha_graph.exceptions import InvalidCorrelationData, InsufficientDataException


def compute_mean(values: List[float]) -> float:
    """Compute mean of a list of values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_std(values: List[float], ddof: int = 1) -> float:
    """
    Compute standard deviation.

    Args:
        values: List of values
        ddof: Delta degrees of freedom (1 for sample, 0 for population)

    Returns:
        Standard deviation
    """
    if len(values) < 2:
        return 0.0

    mean = compute_mean(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - ddof)
    return math.sqrt(variance)


def compute_correlation(
    series_a: List[float],
    series_b: List[float],
    window: Optional[int] = None,
) -> Tuple[float, float]:
    """
    Compute Pearson correlation with significance (p-value approximation).

    Args:
        series_a: First series
        series_b: Second series
        window: Optional rolling window size (use last N points)

    Returns:
        Tuple of (correlation, p_value)

    Raises:
        InvalidCorrelationData: If series lengths don't match
        InsufficientDataException: If not enough data points
    """
    if len(series_a) != len(series_b):
        raise InvalidCorrelationData(
            f"Series length mismatch: {len(series_a)} vs {len(series_b)}"
        )

    if len(series_a) < 3:
        raise InsufficientDataException(required=3, actual=len(series_a))

    # Apply window if specified
    if window is not None and window < len(series_a):
        series_a = series_a[-window:]
        series_b = series_b[-window:]

    n = len(series_a)

    # Compute means
    mean_a = compute_mean(series_a)
    mean_b = compute_mean(series_b)

    # Compute covariance and standard deviations
    covariance = sum((series_a[i] - mean_a) * (series_b[i] - mean_b) for i in range(n))
    std_a = math.sqrt(sum((x - mean_a) ** 2 for x in series_a))
    std_b = math.sqrt(sum((x - mean_b) ** 2 for x in series_b))

    # Handle zero variance
    if std_a == 0.0 or std_b == 0.0:
        return 0.0, 1.0

    # Pearson correlation
    correlation = covariance / (std_a * std_b)

    # Clamp to [-1, 1] to handle floating point errors
    correlation = max(-1.0, min(1.0, correlation))

    # Approximate p-value using t-distribution
    # t = r * sqrt(n-2) / sqrt(1 - r^2)
    # For large n, approximate p-value
    if abs(correlation) >= 0.999:
        p_value = 0.0
    else:
        t_stat = abs(correlation) * math.sqrt(n - 2) / math.sqrt(1 - correlation**2)
        # Rough p-value approximation (simplified)
        p_value = max(0.0, 1.0 - min(1.0, t_stat / 10.0))

    return correlation, p_value


def compute_lagged_correlation(
    series_a: List[float],
    series_b: List[float],
    max_lag: int,
) -> Dict[int, Tuple[float, float]]:
    """
    Compute cross-correlation at various lags.

    Args:
        series_a: First series (leading)
        series_b: Second series (lagging)
        max_lag: Maximum lag to test (in data points)

    Returns:
        Dictionary mapping lag -> (correlation, p_value)
        Positive lag means series_a leads series_b
    """
    if len(series_a) != len(series_b):
        raise InvalidCorrelationData(
            f"Series length mismatch: {len(series_a)} vs {len(series_b)}"
        )

    if len(series_a) < max_lag + 3:
        raise InsufficientDataException(
            required=max_lag + 3, actual=len(series_a)
        )

    results = {}

    # Test lags from 0 to max_lag
    for lag in range(0, max_lag + 1):
        if lag == 0:
            # No lag - standard correlation
            corr, p_val = compute_correlation(series_a, series_b)
            results[0] = (corr, p_val)
        else:
            # Positive lag: series_a[t] vs series_b[t+lag]
            # (series_a leads series_b by lag periods)
            a_lagged = series_a[:-lag]
            b_shifted = series_b[lag:]

            if len(a_lagged) >= 3:
                corr, p_val = compute_correlation(a_lagged, b_shifted)
                results[lag] = (corr, p_val)

    return results


def find_best_lag(
    lagged_correlations: Dict[int, Tuple[float, float]]
) -> Tuple[int, float, float]:
    """
    Find lag with highest absolute correlation.

    Args:
        lagged_correlations: Dictionary from compute_lagged_correlation

    Returns:
        Tuple of (best_lag, correlation, p_value)
    """
    if not lagged_correlations:
        return 0, 0.0, 1.0

    best_lag = 0
    best_corr = 0.0
    best_p_value = 1.0

    for lag, (corr, p_val) in lagged_correlations.items():
        if abs(corr) > abs(best_corr):
            best_lag = lag
            best_corr = corr
            best_p_value = p_val

    return best_lag, best_corr, best_p_value


def filter_by_regime(
    values: List[float],
    timestamps: List[datetime],
    regime_labels: Dict[datetime, str],
    target_regime: str,
) -> Tuple[List[float], List[datetime]]:
    """
    Filter time series to only include points in a specific regime.

    Args:
        values: Time series values
        timestamps: Corresponding timestamps
        regime_labels: Mapping of timestamp -> regime label
        target_regime: Regime to filter for

    Returns:
        Tuple of (filtered_values, filtered_timestamps)
    """
    if len(values) != len(timestamps):
        raise InvalidCorrelationData(
            f"Length mismatch: {len(values)} values vs {len(timestamps)} timestamps"
        )

    filtered_values = []
    filtered_timestamps = []

    for i, ts in enumerate(timestamps):
        # Find regime for this timestamp (use closest match)
        regime = regime_labels.get(ts)
        if regime == target_regime:
            filtered_values.append(values[i])
            filtered_timestamps.append(ts)

    return filtered_values, filtered_timestamps


def compute_confidence_score(
    correlation: float,
    p_value: float,
    sample_size: int,
    min_sample_size: int = 30,
) -> float:
    """
    Compute confidence score [0-1] from statistical metrics.

    Confidence combines:
    - Statistical significance (p-value)
    - Sample size adequacy
    - Correlation strength

    Args:
        correlation: Correlation coefficient
        p_value: Statistical p-value
        sample_size: Number of data points
        min_sample_size: Minimum acceptable sample size

    Returns:
        Confidence score [0-1]
    """
    # Component 1: Significance (inverse of p-value)
    sig_score = max(0.0, 1.0 - p_value)

    # Component 2: Sample size adequacy
    if sample_size >= min_sample_size:
        sample_score = 1.0
    else:
        sample_score = sample_size / min_sample_size

    # Component 3: Correlation strength (absolute value)
    corr_score = abs(correlation)

    # Weighted average (significance most important)
    confidence = 0.5 * sig_score + 0.3 * sample_score + 0.2 * corr_score

    return max(0.0, min(1.0, confidence))


def align_time_series(
    series_a: List[float],
    timestamps_a: List[datetime],
    series_b: List[float],
    timestamps_b: List[datetime],
) -> Tuple[List[float], List[float], List[datetime]]:
    """
    Align two time series to common timestamps.

    Args:
        series_a: First series values
        timestamps_a: First series timestamps
        series_b: Second series values
        timestamps_b: Second series timestamps

    Returns:
        Tuple of (aligned_series_a, aligned_series_b, aligned_timestamps)
    """
    # Create dictionaries for lookup
    dict_a = {ts: val for ts, val in zip(timestamps_a, series_a)}
    dict_b = {ts: val for ts, val in zip(timestamps_b, series_b)}

    # Find common timestamps
    common_timestamps = sorted(set(timestamps_a) & set(timestamps_b))

    # Build aligned series
    aligned_a = [dict_a[ts] for ts in common_timestamps]
    aligned_b = [dict_b[ts] for ts in common_timestamps]

    return aligned_a, aligned_b, common_timestamps


def validate_time_series(
    values: List[float],
    timestamps: List[datetime],
    allow_nan: bool = False,
) -> bool:
    """
    Validate time series data.

    Args:
        values: Series values
        timestamps: Corresponding timestamps
        allow_nan: Whether to allow NaN values

    Returns:
        True if valid

    Raises:
        InvalidCorrelationData: If validation fails
    """
    if len(values) != len(timestamps):
        raise InvalidCorrelationData(
            f"Length mismatch: {len(values)} values vs {len(timestamps)} timestamps"
        )

    if not allow_nan:
        for i, val in enumerate(values):
            if math.isnan(val) or math.isinf(val):
                raise InvalidCorrelationData(
                    f"Invalid value at index {i}: {val}"
                )

    # Check timestamps are sorted
    for i in range(1, len(timestamps)):
        if timestamps[i] <= timestamps[i - 1]:
            raise InvalidCorrelationData(
                f"Timestamps not sorted at index {i}: {timestamps[i-1]} >= {timestamps[i]}"
            )

    return True
