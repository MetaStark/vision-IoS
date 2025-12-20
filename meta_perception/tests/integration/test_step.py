"""Test orchestration step function."""
import pytest
from meta_perception.orchestration.step import step

def test_step_basic(test_state, test_inputs, default_config):
    """Test basic step execution."""
    new_state, output = step(test_state, test_inputs, default_config)
    
    assert new_state is not None
    assert output is not None
    assert output.snapshot is not None
    assert output.decision is not None
    assert output.computation_time_ms > 0

def test_step_performance(test_state, test_inputs, default_config):
    """Test that step meets performance requirements."""
    new_state, output = step(test_state, test_inputs, default_config)
    
    assert output.computation_time_ms < 150  # Performance gate
