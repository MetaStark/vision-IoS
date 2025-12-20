"""Regime pivot detection module."""

import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime

from meta_perception.models.regime_models import RegimeAlert
from meta_perception.models.perception_state import PerceptionState
from meta_perception.utils.math_utils import sigmoid
from meta_perception.utils.id_generation import _generate_id


INDICATOR_WEIGHTS = {
    "volatility_acceleration": 0.30,
    "correlation_instability": 0.25,
    "liquidity_stress": 0.20,
    "flow_divergence": 0.15,
    "entropy_spike": 0.10
}


def detect_regime_pivot(
    perception_state: PerceptionState,
    leading_indicators: Dict[str, float],
    stress_threshold: float = 1.0,
    diagnostic_logger: Optional[Any] = None
) -> RegimeAlert:
    """
    Detect nonlinear regime pivots BEFORE they manifest.

    Pure function.

    Algorithm:
    1. Compute regime stress from leading indicators
    2. Detect stress > threshold → pivot imminent
    3. Estimate new regime from indicator values

    Args:
        perception_state: Current perception state
        leading_indicators: Dict of indicator → value
        stress_threshold: Pivot detection threshold
        diagnostic_logger: Optional diagnostic logger

    Returns:
        RegimeAlert with stress, pivot_detected, expected_new_regime
    """
    # Compute regime stress
    regime_stress = 0.0
    for indicator, value in leading_indicators.items():
        weight = INDICATOR_WEIGHTS.get(indicator, 0.0)
        regime_stress += weight * value

    # Pivot detection
    pivot_detected = regime_stress >= stress_threshold

    # Pivot probability (sigmoid around threshold)
    pivot_probability = sigmoid((regime_stress - stress_threshold) * 5)

    # Estimate new regime
    expected_new_regime = None
    if pivot_detected:
        expected_new_regime = _estimate_new_regime(leading_indicators)

    # Alert level
    if regime_stress >= 2.0:
        alert_level = "CRITICAL"
    elif regime_stress >= stress_threshold:
        alert_level = "WARNING"
    elif regime_stress >= 0.7:
        alert_level = "WATCH"
    else:
        alert_level = "INFO"

    if diagnostic_logger:
        diagnostic_logger.log_step(
            1,
            "Compute regime stress",
            leading_indicators,
            {"regime_stress": regime_stress},
            f"Regime stress: {regime_stress:.3f} (threshold: {stress_threshold})"
        )
        diagnostic_logger.log_threshold("regime_stress_threshold", stress_threshold)

    return RegimeAlert(
        alert_id=_generate_id("regime", datetime.now().isoformat()),
        timestamp=datetime.now(),
        current_regime=perception_state.current_regime or "UNKNOWN",
        current_regime_confidence=perception_state.regime_confidence,
        regime_stress=regime_stress,
        pivot_detected=pivot_detected,
        pivot_probability=pivot_probability,
        expected_new_regime=expected_new_regime,
        estimated_pivot_window_hours=24.0 if pivot_detected else None,
        leading_indicators=leading_indicators,
        alert_level=alert_level,
        metadata={"stress_threshold": stress_threshold}
    )


def _estimate_new_regime(indicators: Dict[str, float]) -> str:
    """
    Predict next regime from indicator values.

    Heuristics:
    - High volatility + negative flow → CRISIS
    - Low volatility + positive flow → BULL
    - Neutral indicators → NEUTRAL
    """
    vol_accel = indicators.get("volatility_acceleration", 0)
    flow_div = indicators.get("flow_divergence", 0)

    if vol_accel > 0.01 and flow_div < -0.1:
        return "CRISIS"
    elif vol_accel < 0.001 and flow_div > 0.1:
        return "BULL"
    elif vol_accel > 0.005:
        return "BEAR"
    else:
        return "NEUTRAL"
