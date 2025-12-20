"""Reflexivity computation module."""

import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime

from meta_perception.models.reflexivity_models import ReflexivityScore
from meta_perception.utils.math_utils import compute_correlation
from meta_perception.utils.id_generation import _generate_id


def compute_reflexive_impact(
    previous_decisions: List[Dict[str, Any]],
    market_data: Dict[str, List[float]],
    lookback_days: int = 7,
    diagnostic_logger: Optional[Any] = None
) -> ReflexivityScore:
    """
    Measure reflexivity: correlation between our decisions and market state.

    Pure function.

    Algorithm:
    1. Extract decision timestamps and actions
    2. Measure market state change after each decision
    3. Compute correlation: corr(decision → next_state)
    4. Estimate market impact in bps

    Args:
        previous_decisions: List of decision dicts with timestamps, actions
        market_data: Market prices after decisions
        lookback_days: How far back to analyze

    Returns:
        ReflexivityScore with coefficient, impact estimate, feedback strength
    """
    if diagnostic_logger:
        diagnostic_logger.log_step(
            1,
            "Analyze decision history",
            {"n_decisions": len(previous_decisions)},
            {},
            "Computing reflexivity from decision-market correlation"
        )

    if len(previous_decisions) < 2:
        # Not enough data
        return ReflexivityScore(
            reflexivity_id=_generate_id("reflex", datetime.now().isoformat()),
            timestamp=datetime.now(),
            reflexivity_coefficient=0.0,
            market_impact_estimate=0.0,
            feedback_strength="NONE",
            self_fulfilling_probability=0.0,
            market_learning_rate=0.0,
            metadata={"insufficient_data": True}
        )

    # Convert decisions to vector
    decision_vector = []
    for dec in previous_decisions:
        actions = dec.get("actions", [])
        # Encode: +1 for buy, -1 for sell, 0 for neutral
        if any("BUY" in str(a) for a in actions):
            decision_vector.append(1.0)
        elif any("SELL" in str(a) for a in actions):
            decision_vector.append(-1.0)
        else:
            decision_vector.append(0.0)

    # Get market movements (use first available feature)
    market_movements = []
    for feature, values in market_data.items():
        if len(values) >= len(decision_vector):
            # Compute returns
            arr = np.array(values[:len(decision_vector)])
            if len(arr) > 1:
                returns = (arr[1:] - arr[:-1]) / arr[:-1]
                # Pad to match decision length
                market_movements = np.pad(returns, (0, max(0, len(decision_vector) - len(returns))), mode='edge').tolist()
                break

    if not market_movements or len(market_movements) != len(decision_vector):
        market_movements = [0.0] * len(decision_vector)

    # Compute reflexivity coefficient
    reflexivity_coef = compute_correlation(decision_vector, market_movements)

    # Estimate market impact (simple model)
    # Assume impact scales with correlation strength
    market_impact_bps = abs(reflexivity_coef) * 5.0  # 0-5 bps range

    # Classify feedback strength
    abs_coef = abs(reflexivity_coef)
    if abs_coef < 0.1:
        feedback_strength = "NONE"
    elif abs_coef < 0.3:
        feedback_strength = "WEAK"
    elif abs_coef < 0.6:
        feedback_strength = "MODERATE"
    else:
        feedback_strength = "STRONG"

    # Self-fulfilling probability (higher correlation = higher self-fulfilling)
    self_fulfilling_prob = min(abs_coef, 1.0)

    # Market learning rate (assume 5% for now)
    market_learning_rate = 0.05

    if diagnostic_logger:
        diagnostic_logger.log_step(
            2,
            "Compute correlation",
            {"decision_vector": decision_vector[:5]},  # First 5
            {"reflexivity_coefficient": reflexivity_coef},
            f"Reflexivity: {reflexivity_coef:.3f} ({feedback_strength})"
        )

    return ReflexivityScore(
        reflexivity_id=_generate_id("reflex", datetime.now().isoformat()),
        timestamp=datetime.now(),
        reflexivity_coefficient=reflexivity_coef,
        market_impact_estimate=market_impact_bps,
        feedback_strength=feedback_strength,
        self_fulfilling_probability=self_fulfilling_prob,
        market_learning_rate=market_learning_rate,
        impact_half_life_hours=6.0,
        metadata={"lookback_days": lookback_days}
    )
