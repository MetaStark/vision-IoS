"""Noise evaluation module."""

import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime

from meta_perception.models.noise_models import NoiseScore
from meta_perception.utils.id_generation import _generate_id


def evaluate_noise_level(
    market_data: Dict[str, List[float]],
    window_minutes: int = 60,
    noise_threshold: float = 0.7,
    diagnostic_logger: Optional[Any] = None
) -> NoiseScore:
    """
    Evaluate noise-to-signal ratio.

    Pure function: Same inputs → same output.

    Algorithm:
    1. Decompose price into trend + noise (simple method)
    2. Compute noise variance / signal variance
    3. Evaluate signal quality metrics
    4. Classify noise regime

    Args:
        market_data: Price time series
        window_minutes: Analysis window
        noise_threshold: Acceptable noise level

    Returns:
        NoiseScore with noise_level, signal_quality, is_acceptable
    """
    if diagnostic_logger:
        diagnostic_logger.log_step(
            1,
            "Start noise evaluation",
            {"n_features": len(market_data)},
            {},
            "Evaluating noise-to-signal ratio"
        )

    # Compute noise level for each feature
    noise_levels = []
    for feature, values in market_data.items():
        if len(values) < 10:
            continue

        arr = np.array(values)

        # Simple trend: moving average
        window = min(10, len(arr) // 2)
        if window < 2:
            continue

        trend = np.convolve(arr, np.ones(window) / window, mode='valid')

        # Noise: residual
        noise = arr[:len(trend)] - trend

        # Noise-to-signal ratio
        noise_var = np.var(noise)
        signal_var = np.var(trend)

        if signal_var > 0:
            ratio = noise_var / signal_var
            # Normalize to [0, 1]
            noise_level = min(ratio / (1 + ratio), 1.0)
            noise_levels.append(noise_level)

    # Aggregate noise level
    if noise_levels:
        overall_noise = np.mean(noise_levels)
    else:
        overall_noise = 0.5  # Unknown

    # Signal quality
    signal_quality = 1.0 - overall_noise

    # Noise-to-signal ratio
    if signal_quality > 0:
        noise_to_signal_ratio = overall_noise / signal_quality
    else:
        noise_to_signal_ratio = 999.0

    # Classify noise regime
    if overall_noise < 0.3:
        noise_regime = "CLEAN"
    elif overall_noise < 0.7:
        noise_regime = "NORMAL"
    elif overall_noise < 0.9:
        noise_regime = "NOISY"
    else:
        noise_regime = "EXTREME_NOISE"

    # Actionability
    is_acceptable = overall_noise < noise_threshold

    if diagnostic_logger:
        diagnostic_logger.log_threshold("noise_threshold", noise_threshold)
        diagnostic_logger.log_comparison(
            f"Noise level {overall_noise:.3f} {'<' if is_acceptable else '>='} threshold {noise_threshold}"
        )

    return NoiseScore(
        noise_id=_generate_id("noise", datetime.now().isoformat()),
        timestamp=datetime.now(),
        noise_level=overall_noise,
        signal_quality=signal_quality,
        noise_to_signal_ratio=noise_to_signal_ratio,
        noise_regime=noise_regime,
        is_acceptable=is_acceptable,
        threshold_used=noise_threshold,
        metadata={"window_minutes": window_minutes}
    )
