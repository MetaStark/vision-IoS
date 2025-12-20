"""Entropy computation module."""

import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime

from meta_perception.models.entropy_models import EntropyMetrics
from meta_perception.models.config_models import PerceptionConfig
from meta_perception.utils.math_utils import compute_entropy
from meta_perception.utils.id_generation import _generate_id


def compute_market_entropy(
    market_data: Dict[str, List[float]],
    window_minutes: int = 60,
    n_bins: int = 50,
    config: Optional[PerceptionConfig] = None,
    diagnostic_logger: Optional[Any] = None
) -> EntropyMetrics:
    """
    Compute information entropy of market.

    Pure function: Same inputs → same output.

    Algorithm:
    1. Discretize price returns into bins
    2. Compute probability distribution p(x)
    3. H = -Σ p(x) log p(x)
    4. Compute entropy rate: dH/dt

    Args:
        market_data: {"BTC": [prices...], "ETH": [prices...]}
        window_minutes: Rolling window size
        n_bins: Number of bins for discretization
        config: Optional configuration
        diagnostic_logger: Optional diagnostic logger

    Returns:
        EntropyMetrics with market_entropy, feature_entropy, etc.
    """
    if diagnostic_logger:
        diagnostic_logger.log_step(
            1,
            "Start entropy computation",
            {"n_features": len(market_data), "window_minutes": window_minutes},
            {},
            "Computing market and feature entropy"
        )

    # Compute feature-level entropy
    feature_entropy = {}
    for feature, values in market_data.items():
        if len(values) > 1:
            # Compute returns
            arr = np.array(values)
            returns = np.diff(arr) / arr[:-1]

            # Compute entropy
            h = compute_entropy(returns.tolist(), n_bins=n_bins)
            feature_entropy[feature] = h

    # Market entropy: average of feature entropies
    if feature_entropy:
        market_entropy = np.mean(list(feature_entropy.values()))
    else:
        market_entropy = 0.0

    # Entropy rate: approximate as 0 for now (would need time series)
    market_entropy_rate = 0.0

    # Interpret entropy level
    if market_entropy < 1.5:
        interpretation = "LOW_ENTROPY"
    elif market_entropy < 3.0:
        interpretation = "MEDIUM_ENTROPY"
    elif market_entropy < 4.5:
        interpretation = "HIGH_ENTROPY"
    else:
        interpretation = "EXTREME_ENTROPY"

    if diagnostic_logger:
        diagnostic_logger.log_step(
            2,
            "Entropy computed",
            feature_entropy,
            {"market_entropy": market_entropy, "interpretation": interpretation},
            f"Market entropy: {market_entropy:.2f} bits ({interpretation})"
        )

    return EntropyMetrics(
        metric_id=_generate_id("entropy", datetime.now().isoformat()),
        timestamp=datetime.now(),
        market_entropy=market_entropy,
        market_entropy_rate=market_entropy_rate,
        feature_entropy=feature_entropy,
        interpretation=interpretation,
        metadata={"window_minutes": window_minutes, "n_bins": n_bins}
    )


def compute_feature_entropy(feature_values: List[float], n_bins: int = 50) -> float:
    """
    Compute entropy of single feature.

    Pure function.

    Args:
        feature_values: Feature values
        n_bins: Number of bins

    Returns:
        H(feature) in bits
    """
    return compute_entropy(feature_values, n_bins=n_bins)
