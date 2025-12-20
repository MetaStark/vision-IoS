"""Override detection."""
from typing import Optional
from datetime import datetime
from meta_perception.models.override_models import UncertaintyOverride
from meta_perception.models.decision_models import MetaPerceptionDecision
from meta_perception.models.perception_state import PerceptionSnapshot
from meta_perception.models.config_models import PerceptionConfig
from meta_perception.utils.id_generation import generate_override_id

def detect_override(
    decision: MetaPerceptionDecision,
    snapshot: PerceptionSnapshot,
    config: PerceptionConfig
) -> Optional[UncertaintyOverride]:
    """Detect if uncertainty override occurred."""
    if decision.should_act:
        return None
    
    # Determine trigger reason
    if snapshot.noise_score.noise_level > config.noise_threshold:
        trigger_reason = "HIGH_NOISE"
    elif snapshot.state.total_uncertainty > config.uncertainty_threshold:
        trigger_reason = "HIGH_UNCERTAINTY"
    elif snapshot.regime_alert and snapshot.regime_alert.pivot_detected:
        trigger_reason = "REGIME_PIVOT"
    elif any(s.severity == "CRITICAL" for s in snapshot.shock_events):
        trigger_reason = "CRITICAL_SHOCK"
    else:
        trigger_reason = "LOW_CONFIDENCE"
    
    justification = {
        "reason": trigger_reason,
        "noise_level": snapshot.noise_score.noise_level,
        "noise_threshold": config.noise_threshold,
        "uncertainty": snapshot.state.total_uncertainty,
        "uncertainty_threshold": config.uncertainty_threshold,
        "explanation": decision.rationale
    }
    
    return UncertaintyOverride(
        override_id=generate_override_id(datetime.now(), trigger_reason),
        timestamp=datetime.now(),
        perception_snapshot_id=snapshot.snapshot_id,
        trigger_reason=trigger_reason,
        noise_level=snapshot.noise_score.noise_level,
        confidence=decision.confidence,
        total_uncertainty=snapshot.state.total_uncertainty,
        regime_stress=snapshot.regime_alert.regime_stress if snapshot.regime_alert else 0.0,
        prevented_actions=["RUN_TRADE_ENGINE"],
        override_justification=justification,
        estimated_prevented_trades=1,
        estimated_prevented_capital_usd=100000.0,
        metadata={}
    )
