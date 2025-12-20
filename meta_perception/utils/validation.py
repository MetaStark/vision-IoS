"""Validation utilities for Meta-Perception Layer."""

import math
from typing import Dict, List, Tuple, Any
from datetime import datetime, timedelta


def validate_market_data(data: Dict[str, List[float]]) -> Tuple[Dict[str, List[float]], float]:
    """
    Validate and clean market data.

    Args:
        data: Market data dictionary

    Returns:
        (clean_data, quality_score) tuple
    """
    clean_data = {}
    quality_score = 1.0

    for feature, values in data.items():
        if not values:
            quality_score *= 0.5
            continue

        # Remove NaN values
        clean_values = [v for v in values if not math.isnan(v) and math.isfinite(v)]

        # Quality degradation if too many removed
        removal_rate = 1.0 - (len(clean_values) / len(values))
        if removal_rate > 0.1:  # >10% removed
            quality_score *= (1.0 - removal_rate)

        # Cap extreme outliers (>10 std devs)
        if len(clean_values) > 2:
            import numpy as np
            mean = np.mean(clean_values)
            std = np.std(clean_values)

            if std > 0:
                capped_values = []
                for v in clean_values:
                    z_score = abs((v - mean) / std)
                    if z_score > 10:
                        # Cap at 10 std devs
                        capped_v = mean + (10 * std if v > mean else -10 * std)
                        capped_values.append(capped_v)
                    else:
                        capped_values.append(v)

                clean_values = capped_values

        if clean_values:
            clean_data[feature] = clean_values
        else:
            quality_score *= 0.5

    return clean_data, quality_score


def validate_features(features: Dict[str, float]) -> Tuple[Dict[str, float], float]:
    """
    Validate feature dictionary.

    Args:
        features: Feature dictionary

    Returns:
        (clean_features, quality_score) tuple
    """
    clean_features = {}
    quality_score = 1.0

    for name, value in features.items():
        # Check for NaN or Inf
        if math.isnan(value) or math.isinf(value):
            quality_score *= 0.9
            continue

        clean_features[name] = value

    return clean_features, quality_score


def validate_timestamps(timestamps: List[datetime]) -> bool:
    """
    Validate that timestamps are sequential and recent.

    Args:
        timestamps: List of timestamps

    Returns:
        True if valid, False otherwise
    """
    if not timestamps:
        return False

    # Check sequential
    for i in range(1, len(timestamps)):
        if timestamps[i] < timestamps[i-1]:
            return False

    # Check recency (not older than 30 days)
    oldest = min(timestamps)
    if datetime.now() - oldest > timedelta(days=30):
        return False

    return True


def validate_probabilities(probs: Dict[str, float], tolerance: float = 1e-6) -> bool:
    """
    Validate that probabilities sum to 1.0.

    Args:
        probs: Probability dictionary
        tolerance: Allowed deviation from 1.0

    Returns:
        True if valid, False otherwise
    """
    if not probs:
        return False

    total = sum(probs.values())

    return abs(total - 1.0) < tolerance


def clip_value(value: float, min_val: float, max_val: float) -> float:
    """Clip value to range [min_val, max_val]."""
    return max(min_val, min(max_val, value))
