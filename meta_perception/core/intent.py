"""Intent detection module."""

import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime

from meta_perception.models.intent_models import IntentScore
from meta_perception.models.config_models import PerceptionConfig
from meta_perception.utils.math_utils import softmax
from meta_perception.utils.id_generation import _generate_id


# Pre-calibrated weights (would be learned from historical data)
INTENT_WEIGHTS = {
    "long": np.array([2.5, 1.8, 3.2, 1.5, -2.0]),
    "short": np.array([-2.5, -1.8, -3.2, -1.5, 2.0]),
    "neutral": np.array([0.0, 0.0, 0.0, 0.0, 0.5])
}

FEATURE_ORDER = [
    "open_interest_change",
    "funding_rate",
    "whale_flow_net",
    "futures_basis",
    "put_call_ratio"
]


def infer_intent(
    features: Dict[str, float],
    prior_probabilities: Optional[Dict[str, float]] = None,
    config: Optional[PerceptionConfig] = None,
    diagnostic_logger: Optional[Any] = None
) -> IntentScore:
    """
    Infer participant intent using Bayesian inference.

    Pure function: Same features → same intent.

    Algorithm:
    1. P(intent | observations) ∝ P(observations | intent) × P(intent)
    2. Likelihood from logistic regression: σ(wᵀx)
    3. Normalize to get probabilities

    Args:
        features: Dict of feature_name → value
        prior_probabilities: Prior P(intent) (defaults to uniform)
        config: Optional configuration
        diagnostic_logger: Optional diagnostic logger

    Returns:
        IntentScore with probabilities, dominant intent, confidence
    """
    if diagnostic_logger:
        diagnostic_logger.log_step(
            1,
            "Normalize features",
            features,
            {},
            "Preparing feature vector"
        )

    # Extract and normalize features
    feature_vec = []
    for fname in FEATURE_ORDER:
        val = features.get(fname, 0.0)

        # Normalize specific features
        if fname == "funding_rate":
            val *= 10000  # Scale to similar range
        elif fname == "whale_flow_net":
            val /= 1e9  # Scale to billions
        elif fname == "futures_basis":
            val *= 1000  # Scale to bps

        feature_vec.append(val)

    X = np.array(feature_vec)

    # Compute logits
    logits = {}
    for intent, weights in INTENT_WEIGHTS.items():
        logits[intent] = np.dot(weights, X)

    if diagnostic_logger:
        diagnostic_logger.log_step(
            2,
            "Compute logits",
            {"weights": {k: v.tolist() for k, v in INTENT_WEIGHTS.items()}},
            logits,
            f"Logits computed: long={logits['long']:.2f}, short={logits['short']:.2f}"
        )

    # Softmax to probabilities
    logit_array = np.array([logits["long"], logits["short"], logits["neutral"]])
    probs_array = softmax(logit_array)

    intent_probabilities = {
        "long": float(probs_array[0]),
        "short": float(probs_array[1]),
        "neutral": float(probs_array[2])
    }

    # Dominant intent
    dominant = max(intent_probabilities, key=intent_probabilities.get)
    intent_strength = intent_probabilities[dominant]

    # Confidence: concentration of probability
    confidence = intent_strength

    # Map to literal
    if dominant == "long":
        dominant_literal = "LONG"
    elif dominant == "short":
        dominant_literal = "SHORT"
    elif dominant == "neutral":
        dominant_literal = "NEUTRAL"
    else:
        dominant_literal = "UNKNOWN"

    # Infer participant type (simple heuristic)
    whale_flow = features.get("whale_flow_net", 0)
    if abs(whale_flow) > 100_000_000:  # $100M
        participant_type = "WHALE"
    elif abs(whale_flow) > 10_000_000:  # $10M
        participant_type = "INSTITUTIONAL"
    else:
        participant_type = "UNKNOWN"

    if diagnostic_logger:
        diagnostic_logger.log_step(
            3,
            "Softmax to probabilities",
            {"logits": logits},
            {"probabilities": intent_probabilities},
            f"Intent: {dominant_literal} ({intent_strength:.2%})"
        )

    return IntentScore(
        intent_id=_generate_id("intent", datetime.now().isoformat()),
        timestamp=datetime.now(),
        intent_probabilities=intent_probabilities,
        confidence=confidence,
        evidence=features,
        dominant_intent=dominant_literal,
        intent_strength=intent_strength,
        participant_type=participant_type,
        metadata={}
    )
