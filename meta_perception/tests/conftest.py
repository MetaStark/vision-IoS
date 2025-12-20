"""Pytest fixtures for Meta-Perception tests."""
import pytest
from datetime import datetime
from meta_perception.models.perception_state import PerceptionState
from meta_perception.models.decision_models import MetaPerceptionInput
from meta_perception.models.config_models import PerceptionConfig

@pytest.fixture
def default_config():
    """Default test configuration."""
    return PerceptionConfig(
        config_id="test_config",
        version="1.0.0"
    )

@pytest.fixture
def test_state():
    """Test perception state."""
    return PerceptionState(
        state_id="test_state",
        timestamp=datetime.now(),
        market_entropy=2.0,
        noise_score=0.5,
        signal_quality=0.7,
        participant_intent={"long": 0.5, "short": 0.5},
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

@pytest.fixture
def test_inputs():
    """Test inputs."""
    return MetaPerceptionInput(
        timestamp=datetime.now(),
        market_data={"BTC": [50000.0 + i for i in range(100)]},
        features={"open_interest_change": 0.1}
    )
