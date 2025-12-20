"""Perception state creation module."""

from datetime import datetime
from typing import Dict, List

from meta_perception.models.perception_state import PerceptionState
from meta_perception.models.entropy_models import EntropyMetrics
from meta_perception.models.noise_models import NoiseScore
from meta_perception.models.intent_models import IntentScore
from meta_perception.models.reflexivity_models import ReflexivityScore
from meta_perception.models.shock_models import ShockEvent
from meta_perception.models.regime_models import RegimeAlert
from meta_perception.models.config_models import PerceptionConfig
from meta_perception.utils.id_generation import generate_perception_id


def create_perception_state(
    entropy_metrics: EntropyMetrics,
    noise_score: NoiseScore,
    intent_score: IntentScore,
    reflexivity_score: ReflexivityScore,
    shock_events: List[ShockEvent],
    regime_alert: RegimeAlert,
    total_uncertainty: float,
    config: PerceptionConfig
) -> PerceptionState:
    """
    Create new perception state from components.

    Pure function.

    Args:
        entropy_metrics: Entropy metrics
        noise_score: Noise assessment
        intent_score: Intent inference
        reflexivity_score: Reflexivity measurement
        shock_events: Detected shocks
        regime_alert: Regime assessment
        total_uncertainty: Total uncertainty metric
        config: Configuration

    Returns:
        New PerceptionState
    """
    # Aggregate shock intensity
    shock_intensity = 0.0
    active_shock_ids = []
    for shock in shock_events:
        if not shock.is_resolved:
            shock_intensity += shock.intensity
            active_shock_ids.append(shock.shock_id)

    # Determine if system should act
    should_act = (
        noise_score.is_acceptable and
        total_uncertainty < config.uncertainty_threshold and
        not regime_alert.pivot_detected and
        len([s for s in shock_events if s.severity == "CRITICAL"]) == 0
    )

    # Generate state ID
    state_hash = f"{entropy_metrics.market_entropy:.3f}_{noise_score.noise_level:.3f}"
    state_id = generate_perception_id(datetime.now(), state_hash)

    return PerceptionState(
        state_id=state_id,
        timestamp=datetime.now(),
        market_entropy=entropy_metrics.market_entropy,
        feature_entropy=entropy_metrics.feature_entropy,
        noise_score=noise_score.noise_level,
        signal_quality=noise_score.signal_quality,
        participant_intent=intent_score.intent_probabilities,
        market_pressure=intent_score.dominant_intent,
        reflexivity_coefficient=reflexivity_score.reflexivity_coefficient,
        system_impact_score=min(reflexivity_score.market_impact_estimate / 10.0, 1.0),
        current_regime=regime_alert.current_regime,
        regime_confidence=regime_alert.current_regime_confidence,
        regime_stress=regime_alert.regime_stress,
        regime_pivot_probability=regime_alert.pivot_probability,
        active_shocks=active_shock_ids,
        shock_intensity=shock_intensity,
        total_uncertainty=total_uncertainty,
        should_act=should_act,
        metadata={}
    )
