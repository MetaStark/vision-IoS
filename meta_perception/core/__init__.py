"""Core perception computation modules."""

from meta_perception.core.entropy import compute_market_entropy, compute_feature_entropy
from meta_perception.core.noise import evaluate_noise_level
from meta_perception.core.intent import infer_intent
from meta_perception.core.reflexivity import compute_reflexive_impact
from meta_perception.core.shocks import detect_shocks
from meta_perception.core.regime import detect_regime_pivot
from meta_perception.core.uncertainty import compute_total_uncertainty
from meta_perception.core.state import create_perception_state

__all__ = [
    "compute_market_entropy",
    "compute_feature_entropy",
    "evaluate_noise_level",
    "infer_intent",
    "compute_reflexive_impact",
    "detect_shocks",
    "detect_regime_pivot",
    "compute_total_uncertainty",
    "create_perception_state",
]
