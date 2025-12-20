"""
Prediction Ledger Utility Functions

Pure utility functions for forecast evaluation and reconciliation.

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
"""

from datetime import datetime, timedelta
from typing import List
import math


def generate_forecast_id(timestamp: datetime, target_id: str) -> str:
    """
    Generate forecast ID.

    Args:
        timestamp: Forecast timestamp
        target_id: Target ID

    Returns:
        Forecast ID string
    """
    ts_str = timestamp.isoformat()
    return f"forecast_{ts_str}_{target_id}"


def generate_outcome_id(timestamp: datetime, target_id: str) -> str:
    """
    Generate outcome ID.

    Args:
        timestamp: Outcome timestamp
        target_id: Target ID

    Returns:
        Outcome ID string
    """
    ts_str = timestamp.isoformat()
    return f"outcome_{ts_str}_{target_id}"


def generate_evaluation_id(timestamp: datetime, target_id: str, metric_name: str) -> str:
    """
    Generate evaluation ID.

    Args:
        timestamp: Evaluation timestamp
        target_id: Target ID
        metric_name: Metric name

    Returns:
        Evaluation ID string
    """
    ts_str = timestamp.isoformat()
    return f"eval_{ts_str}_{target_id}_{metric_name}"


def is_within_time_window(
    target_time: datetime, actual_time: datetime, tolerance: timedelta
) -> bool:
    """
    Check if actual_time is within tolerance of target_time.

    Args:
        target_time: Target timestamp
        actual_time: Actual timestamp
        tolerance: Tolerance window

    Returns:
        True if within window
    """
    return abs((actual_time - target_time).total_seconds()) <= tolerance.total_seconds()


def compute_brier_score_single(forecast_prob: float, realized_binary: int) -> float:
    """
    Compute Brier score for a single forecast-outcome pair.

    Brier Score = (forecast_prob - realized_binary)^2

    Args:
        forecast_prob: Forecast probability (0-1)
        realized_binary: Realized outcome (0 or 1)

    Returns:
        Brier score (0 = perfect, 1 = worst)
    """
    return (forecast_prob - realized_binary) ** 2


def compute_log_score_single(forecast_prob: float, realized_binary: int) -> float:
    """
    Compute logarithmic score for a single forecast-outcome pair.

    Log Score = -log(P(outcome))

    Args:
        forecast_prob: Forecast probability (0-1)
        realized_binary: Realized outcome (0 or 1)

    Returns:
        Log score (lower is better)
    """
    if realized_binary == 1:
        prob = max(forecast_prob, 1e-15)  # Avoid log(0)
    else:
        prob = max(1 - forecast_prob, 1e-15)

    return -math.log(prob)


def bin_probabilities(
    probabilities: List[float], n_bins: int = 10
) -> List[tuple[float, float, List[int]]]:
    """
    Bin probabilities into n_bins for calibration curve.

    Args:
        probabilities: List of probabilities
        n_bins: Number of bins

    Returns:
        List of (bin_start, bin_end, indices) tuples
    """
    bins: List[tuple[float, float, List[int]]] = []

    bin_width = 1.0 / n_bins

    for i in range(n_bins):
        bin_start = i * bin_width
        bin_end = (i + 1) * bin_width

        # Find indices of probabilities in this bin
        indices = [
            idx
            for idx, p in enumerate(probabilities)
            if bin_start <= p < bin_end or (i == n_bins - 1 and p == 1.0)
        ]

        bins.append((bin_start, bin_end, indices))

    return bins


def derive_horizon_bucket(horizon: timedelta) -> str:
    """
    Convert horizon timedelta to bucket label.

    Buckets:
    - "1d": 0-2 days
    - "5d": 3-7 days
    - "10d": 8-14 days
    - "20d": 15-30 days
    - "30d+": >30 days

    Args:
        horizon: Forecast horizon

    Returns:
        Bucket label (e.g., "5d")
    """
    days = horizon.total_seconds() / 86400

    if days <= 2:
        return "1d"
    elif days <= 7:
        return "5d"
    elif days <= 14:
        return "10d"
    elif days <= 30:
        return "20d"
    else:
        return "30d+"


def timedelta_to_days(td: timedelta) -> float:
    """
    Convert timedelta to days (fractional).

    Args:
        td: Timedelta

    Returns:
        Days as float
    """
    return td.total_seconds() / 86400
