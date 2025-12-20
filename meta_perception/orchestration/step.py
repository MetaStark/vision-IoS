"""Main orchestration function - the perception cycle."""

import time
from typing import Tuple, Optional
from datetime import datetime

from meta_perception.models.perception_state import PerceptionState, PerceptionSnapshot, PerceptionDelta
from meta_perception.models.decision_models import MetaPerceptionInput, MetaPerceptionOutput, MetaPerceptionDecision
from meta_perception.models.config_models import PerceptionConfig
from meta_perception.core import (
    compute_market_entropy,
    evaluate_noise_level,
    infer_intent,
    compute_reflexive_impact,
    detect_shocks,
    detect_regime_pivot,
    compute_total_uncertainty,
    create_perception_state
)
from meta_perception.utils.id_generation import generate_snapshot_id, generate_decision_id
from meta_perception.utils.profiling import PerformanceProfiler


def step(
    state: PerceptionState,
    inputs: MetaPerceptionInput,
    config: PerceptionConfig,
    enable_diagnostics: bool = True,
    enable_importance: bool = True
) -> Tuple[PerceptionState, MetaPerceptionOutput]:
    """
    MAIN ORCHESTRATION FUNCTION.

    Single perception cycle: (state, inputs, config) → (new_state, output)

    This is the ONLY function with orchestration logic.
    All sub-computations are delegated to pure functions.

    Algorithm:
    1. Compute entropy metrics
    2. Evaluate noise level
    3. Infer participant intent
    4. Compute reflexivity
    5. Detect shocks
    6. Detect regime pivots
    7. Aggregate into new PerceptionState
    8. Compute PerceptionDelta (if previous state exists)
    9. Make MetaPerceptionDecision
    10. Generate PerceptionSnapshot
    11. Return (new_state, output)

    Args:
        state: Current perception state
        inputs: All inputs for this cycle
        config: Configuration parameters
        enable_diagnostics: Enable diagnostic logging
        enable_importance: Enable feature importance computation

    Returns:
        (new_state, output) tuple

    Performance: <150ms target
    """
    profiler = PerformanceProfiler(enabled=True)
    start_time = time.perf_counter()

    # 1. Entropy
    with profiler.profile("entropy"):
        entropy_metrics = compute_market_entropy(
            market_data=inputs.market_data,
            window_minutes=config.entropy_window_minutes,
            config=config
        )

    # 2. Noise
    with profiler.profile("noise"):
        noise_score = evaluate_noise_level(
            market_data=inputs.market_data,
            noise_threshold=config.noise_threshold
        )

    # 3. Intent
    with profiler.profile("intent"):
        intent_score = infer_intent(
            features=inputs.features,
            config=config
        )

    # 4. Reflexivity
    with profiler.profile("reflexivity"):
        reflexivity_score = compute_reflexive_impact(
            previous_decisions=inputs.recent_decisions,
            market_data=inputs.market_data,
            lookback_days=config.reflexivity_window_days
        )

    # 5. Shocks
    with profiler.profile("shocks"):
        shock_events = detect_shocks(
            time_series_data=inputs.market_data,
            threshold_std_devs=config.shock_intensity_threshold,
            config=config
        )

    # 6. Regime
    with profiler.profile("regime"):
        # Extract leading indicators from features
        leading_indicators = _extract_leading_indicators(inputs.features)

        regime_alert = detect_regime_pivot(
            perception_state=state,
            leading_indicators=leading_indicators,
            stress_threshold=config.regime_stress_threshold
        )

    # 7. Total uncertainty
    with profiler.profile("uncertainty"):
        total_uncertainty = compute_total_uncertainty(
            entropy_metrics=entropy_metrics,
            noise_score=noise_score,
            reflexivity_score=reflexivity_score,
            regime_alert=regime_alert,
            config=config
        )

    # 8. Create new state
    with profiler.profile("state_creation"):
        new_state = create_perception_state(
            entropy_metrics=entropy_metrics,
            noise_score=noise_score,
            intent_score=intent_score,
            reflexivity_score=reflexivity_score,
            shock_events=shock_events,
            regime_alert=regime_alert,
            total_uncertainty=total_uncertainty,
            config=config
        )

    # 9. Delta
    delta = None
    if state.state_id != "initial":
        delta = _compute_perception_delta(state, new_state, shock_events)

    # 10. Decision
    with profiler.profile("decision"):
        decision = _make_perception_decision(new_state, config, shock_events, regime_alert)

    # 11. Snapshot
    computation_time_ms = (time.perf_counter() - start_time) * 1000

    snapshot = PerceptionSnapshot(
        snapshot_id=generate_snapshot_id(new_state.timestamp),
        timestamp=new_state.timestamp,
        state=new_state,
        entropy_metrics=entropy_metrics,
        noise_score=noise_score,
        intent_score=intent_score,
        reflexivity_score=reflexivity_score,
        shock_events=shock_events,
        regime_alert=regime_alert,
        computation_time_ms=computation_time_ms,
        metadata={"profiler": profiler.get_summary()}
    )

    # 12. Output
    output = MetaPerceptionOutput(
        snapshot=snapshot,
        delta=delta,
        decision=decision,
        computation_time_ms=computation_time_ms,
        metadata={"performance_gate_passed": computation_time_ms < config.max_computation_time_ms}
    )

    return new_state, output


def _extract_leading_indicators(features: dict) -> dict:
    """Extract leading indicators from feature dict."""
    return {
        "volatility_acceleration": features.get("volatility_acceleration", 0.0),
        "correlation_instability": features.get("correlation_instability", 0.0),
        "liquidity_stress": features.get("liquidity_stress", 0.0),
        "flow_divergence": features.get("flow_divergence", 0.0),
        "entropy_spike": features.get("entropy_spike", 0.0)
    }


def _compute_perception_delta(
    from_state: PerceptionState,
    to_state: PerceptionState,
    shock_events: list
) -> PerceptionDelta:
    """Compute delta between states."""
    # Intent shift
    intent_shift = {}
    for intent_type in ["long", "short", "neutral"]:
        old_prob = from_state.participant_intent.get(intent_type, 0.0)
        new_prob = to_state.participant_intent.get(intent_type, 0.0)
        intent_shift[intent_type] = new_prob - old_prob

    # Regime change
    regime_changed = from_state.current_regime != to_state.current_regime

    # New shocks
    new_shock_ids = set(to_state.active_shocks) - set(from_state.active_shocks)
    shocks_added = [s for s in shock_events if s.shock_id in new_shock_ids]

    # Resolved shocks
    shocks_resolved = list(set(from_state.active_shocks) - set(to_state.active_shocks))

    # Alert priority
    if any(s.severity == "CRITICAL" for s in shocks_added):
        alert_priority = "CRITICAL"
    elif regime_changed:
        alert_priority = "HIGH"
    elif shocks_added:
        alert_priority = "MEDIUM"
    else:
        alert_priority = "LOW"

    requires_attention = alert_priority in ["HIGH", "CRITICAL"]

    from meta_perception.utils.id_generation import _generate_id

    return PerceptionDelta(
        delta_id=_generate_id("delta", from_state.state_id, to_state.state_id),
        from_snapshot_id=f"snapshot_{from_state.timestamp.isoformat()}",
        to_snapshot_id=f"snapshot_{to_state.timestamp.isoformat()}",
        timestamp=to_state.timestamp,
        entropy_delta=to_state.market_entropy - from_state.market_entropy,
        noise_delta=to_state.noise_score - from_state.noise_score,
        intent_shift=intent_shift,
        reflexivity_delta=to_state.reflexivity_coefficient - from_state.reflexivity_coefficient,
        regime_changed=regime_changed,
        new_regime=to_state.current_regime if regime_changed else None,
        shocks_added=shocks_added,
        shocks_resolved=shocks_resolved,
        requires_attention=requires_attention,
        alert_priority=alert_priority,
        metadata={}
    )


def _make_perception_decision(
    state: PerceptionState,
    config: PerceptionConfig,
    shock_events: list,
    regime_alert
) -> MetaPerceptionDecision:
    """Make perception decision from state."""
    # Determine should_act
    should_act = state.should_act

    # Confidence
    confidence = state.signal_quality

    # Recommended risk mode
    if state.regime_stress > 1.5 or any(s.severity == "CRITICAL" for s in shock_events):
        recommended_risk_mode = "DEFENSIVE"
    elif state.noise_score > 0.6 or state.regime_stress > 0.8:
        recommended_risk_mode = "CAUTIOUS"
    else:
        recommended_risk_mode = "NORMAL"

    # Recommended leverage adjustment
    leverage_adjustment = None
    if not should_act:
        leverage_adjustment = 0.5  # Reduce leverage
    elif state.total_uncertainty > 0.7:
        leverage_adjustment = 0.7

    # Alerting
    alert_operator = (
        not should_act or
        any(s.severity == "CRITICAL" for s in shock_events) or
        regime_alert.alert_level == "CRITICAL"
    )

    if alert_operator and not should_act:
        alert_priority = "CRITICAL"
    elif alert_operator:
        alert_priority = "HIGH"
    else:
        alert_priority = "LOW"

    # Rationale
    rationale = _generate_rationale(state, shock_events, regime_alert)

    # Key factors
    key_factors = []
    if state.noise_score > 0.7:
        key_factors.append(f"High noise ({state.noise_score:.2%})")
    if state.total_uncertainty > 0.6:
        key_factors.append(f"High uncertainty ({state.total_uncertainty:.2%})")
    if shock_events:
        key_factors.append(f"{len(shock_events)} active shocks")
    if regime_alert.pivot_detected:
        key_factors.append("Regime pivot detected")

    snapshot_id = generate_snapshot_id(state.timestamp)

    return MetaPerceptionDecision(
        decision_id=generate_decision_id(snapshot_id, state.timestamp),
        timestamp=state.timestamp,
        should_act=should_act,
        confidence=confidence,
        recommended_risk_mode=recommended_risk_mode,
        recommended_leverage_adjustment=leverage_adjustment,
        alert_operator=alert_operator,
        alert_priority=alert_priority,
        rationale=rationale,
        perception_snapshot_id=snapshot_id,
        key_factors=key_factors,
        metadata={}
    )


def _generate_rationale(state, shock_events, regime_alert) -> str:
    """Generate human-readable rationale."""
    parts = []

    if not state.should_act:
        if state.noise_score > 0.7:
            parts.append(f"High noise level ({state.noise_score:.2%}) exceeds threshold.")
        if state.total_uncertainty > 0.6:
            parts.append(f"High system uncertainty ({state.total_uncertainty:.2%}).")
        if any(s.severity == "CRITICAL" for s in shock_events):
            parts.append("Critical shocks detected.")
        if regime_alert.pivot_detected:
            parts.append("Regime pivot imminent.")

        return "System override: " + " ".join(parts)
    else:
        return f"Normal operation. Noise: {state.noise_score:.2%}, Uncertainty: {state.total_uncertainty:.2%}, Confidence: {state.signal_quality:.2%}"
