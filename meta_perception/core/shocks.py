"""Shock detection module."""

import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from meta_perception.models.shock_models import ShockEvent
from meta_perception.models.config_models import PerceptionConfig
from meta_perception.utils.math_utils import detect_outliers
from meta_perception.utils.id_generation import generate_shock_id


def detect_shocks(
    time_series_data: Dict[str, List[float]],
    timestamps: Optional[List[datetime]] = None,
    threshold_std_devs: float = 3.0,
    config: Optional[PerceptionConfig] = None,
    diagnostic_logger: Optional[Any] = None
) -> List[ShockEvent]:
    """
    Detect information shocks BEFORE price reacts.

    Pure function.

    Algorithm:
    1. For each feature, compute rolling mean and std
    2. Detect outliers: |x - μ| > k×σ
    3. Compute shock intensity
    4. Classify shock type

    Args:
        time_series_data: {"feature": [values...]}
        timestamps: Corresponding timestamps
        threshold_std_devs: Detection threshold (default 3.0)
        config: Optional configuration
        diagnostic_logger: Optional diagnostic logger

    Returns:
        List of ShockEvent objects (sorted by intensity)
    """
    shocks = []

    if timestamps is None:
        timestamps = [datetime.now() - timedelta(minutes=i) for i in range(100)]

    for feature, values in time_series_data.items():
        if len(values) < 10:
            continue

        # Detect outliers
        outlier_indices = detect_outliers(values, threshold_std=threshold_std_devs)

        for idx in outlier_indices:
            if idx >= len(timestamps):
                continue

            # Compute shock statistics
            arr = np.array(values)
            mean = np.mean(arr)
            std = np.std(arr)

            if std == 0:
                continue

            shock_value = values[idx]
            z_score = abs((shock_value - mean) / std)

            # Shock intensity
            intensity = z_score / 3.0  # Normalize

            # Classify severity
            if intensity >= 5.0:
                severity = "CRITICAL"
            elif intensity >= 2.0:
                severity = "HIGH"
            elif intensity >= 1.0:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            # Classify shock type
            shock_type = _classify_shock_type(feature)

            # Expected direction
            if shock_value > mean:
                expected_direction = "UP"
            elif shock_value < mean:
                expected_direction = "DOWN"
            else:
                expected_direction = "NEUTRAL"

            shock = ShockEvent(
                shock_id=generate_shock_id(shock_type, timestamps[idx], feature),
                timestamp=timestamps[idx],
                detected_at=datetime.now(),
                shock_type=shock_type,
                intensity=intensity,
                severity=severity,
                affected_features=[feature],
                shock_size_std_devs=z_score,
                expected_direction=expected_direction,
                is_resolved=False,
                metadata={"threshold_used": threshold_std_devs}
            )

            shocks.append(shock)

    # Sort by intensity (highest first)
    shocks.sort(key=lambda s: s.intensity, reverse=True)

    if diagnostic_logger and shocks:
        diagnostic_logger.log_step(
            1,
            "Shocks detected",
            {"n_shocks": len(shocks)},
            {"max_intensity": shocks[0].intensity if shocks else 0},
            f"Detected {len(shocks)} shocks"
        )

    return shocks


def _classify_shock_type(feature: str) -> str:
    """Classify shock type from feature name."""
    feature_lower = feature.lower()

    if "funding" in feature_lower:
        return "FUNDING_SHOCK"
    elif "oi" in feature_lower or "open_interest" in feature_lower:
        return "OI_SURGE"
    elif "flow" in feature_lower or "whale" in feature_lower:
        return "FLOW_ANOMALY"
    elif "corr" in feature_lower:
        return "CORRELATION_BREAK"
    elif "entropy" in feature_lower:
        return "ENTROPY_SPIKE"
    else:
        return "UNKNOWN"
