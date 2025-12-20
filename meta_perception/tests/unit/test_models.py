"""Test Pydantic models."""
import pytest
from datetime import datetime
from pydantic import ValidationError
from meta_perception.models.perception_state import PerceptionState

def test_perception_state_frozen():
    """Test that PerceptionState is immutable."""
    state = PerceptionState(
        state_id="test",
        timestamp=datetime.now(),
        market_entropy=2.0,
        noise_score=0.5,
        signal_quality=0.7,
        participant_intent={},
        market_pressure="NEUTRAL",
        reflexivity_coefficient=0.0,
        system_impact_score=0.0,
        regime_confidence=0.8,
        regime_stress=0.3,
        regime_pivot_probability=0.1,
        shock_intensity=0.0,
        total_uncertainty=0.5,
        should_act=True
    )
    
    with pytest.raises(ValidationError):
        state.market_entropy = 999.0

def test_perception_state_with_updates():
    """Test immutable update pattern."""
    state = PerceptionState(
        state_id="test",
        timestamp=datetime.now(),
        market_entropy=2.0,
        noise_score=0.5,
        signal_quality=0.7,
        participant_intent={},
        market_pressure="NEUTRAL",
        reflexivity_coefficient=0.0,
        system_impact_score=0.0,
        regime_confidence=0.8,
        regime_stress=0.3,
        regime_pivot_probability=0.1,
        shock_intensity=0.0,
        total_uncertainty=0.5,
        should_act=True
    )
    
    new_state = state.with_updates(market_entropy=3.0)
    assert new_state.market_entropy == 3.0
    assert state.market_entropy == 2.0  # Original unchanged
