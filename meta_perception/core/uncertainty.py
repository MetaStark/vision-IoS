"""Uncertainty computation module."""

from meta_perception.models.entropy_models import EntropyMetrics
from meta_perception.models.noise_models import NoiseScore
from meta_perception.models.reflexivity_models import ReflexivityScore
from meta_perception.models.regime_models import RegimeAlert
from meta_perception.models.config_models import PerceptionConfig


def compute_total_uncertainty(
    entropy_metrics: EntropyMetrics,
    noise_score: NoiseScore,
    reflexivity_score: ReflexivityScore,
    regime_alert: RegimeAlert,
    config: PerceptionConfig
) -> float:
    """
    Compute total system uncertainty.

    Pure function.

    Formula:
    U = w_entropy × H + w_noise × N + w_reflex × |R| + w_stress × S

    Args:
        entropy_metrics: Entropy metrics
        noise_score: Noise score
        reflexivity_score: Reflexivity score
        regime_alert: Regime alert
        config: Configuration with weights

    Returns:
        Total uncertainty [0, ∞)
    """
    # Normalize components to [0, 1]
    max_entropy = 5.0  # Theoretical max
    H_norm = min(entropy_metrics.market_entropy / max_entropy, 1.0)
    N_norm = noise_score.noise_level
    R_norm = abs(reflexivity_score.reflexivity_coefficient)
    S_norm = min(regime_alert.regime_stress / 2.0, 1.0)

    # Get weights from config
    weights = config.uncertainty_weights

    # Compute weighted uncertainty
    total_uncertainty = (
        weights.get("entropy", 0.25) * H_norm +
        weights.get("noise", 0.35) * N_norm +
        weights.get("reflexivity", 0.15) * R_norm +
        weights.get("regime_stress", 0.25) * S_norm
    )

    return total_uncertainty
