"""Stress scenario runner."""
import time
from datetime import datetime
from meta_perception.models.scenario_models import StressScenarioResult, StressScenarioSummary
from meta_perception.models.config_models import PerceptionConfig
from meta_perception.models.perception_state import PerceptionState
from meta_perception.models.decision_models import MetaPerceptionInput
from meta_perception.orchestration.step import step
from meta_perception.simulation.scenarios import STRESS_SCENARIOS, generate_flash_crash_data, generate_funding_explosion_data
from meta_perception.utils.id_generation import generate_scenario_id

def run_stress_scenario(scenario_name: str, config: PerceptionConfig) -> StressScenarioResult:
    """Run single stress scenario."""
    start_time = time.perf_counter()
    
    scenario = STRESS_SCENARIOS[scenario_name]
    
    # Generate data
    if scenario_name == "flash_crash":
        market_data = generate_flash_crash_data()
    elif scenario_name == "funding_explosion":
        market_data = generate_funding_explosion_data()
    else:
        market_data = {"BTC": [50000.0] * 100}
    
    # Create initial state
    initial_state = PerceptionState(
        state_id="initial",
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
    
    # Run perception
    inputs = MetaPerceptionInput(
        timestamp=datetime.now(),
        market_data=market_data,
        features={"volatility_acceleration": 0.01}
    )
    
    new_state, output = step(initial_state, inputs, config)
    
    # Check expectations
    expected = scenario["expected_behavior"]
    actual = {
        "should_act": output.decision.should_act,
        "alert_operator": output.decision.alert_operator,
        "recommended_risk_mode": output.decision.recommended_risk_mode
    }
    
    passed = True
    deviations = []
    
    for key, expected_val in expected.items():
        actual_val = actual.get(key)
        if actual_val != expected_val:
            passed = False
            deviations.append({
                "metric": key,
                "expected": expected_val,
                "actual": actual_val
            })
    
    execution_time = (time.perf_counter() - start_time) * 1000
    
    return StressScenarioResult(
        result_id=generate_scenario_id(scenario_name, datetime.now()),
        scenario_name=scenario_name,
        timestamp=datetime.now(),
        passed=passed,
        perception_snapshot=output.snapshot,
        expected_behavior=expected,
        actual_behavior=actual,
        deviations=deviations,
        execution_time_ms=execution_time
    )

def run_all_stress_scenarios(config: PerceptionConfig) -> StressScenarioSummary:
    """Run all stress scenarios."""
    results = []
    for scenario_name in STRESS_SCENARIOS:
        result = run_stress_scenario(scenario_name, config)
        results.append(result)
    
    passed = sum(r.passed for r in results)
    total = len(results)
    
    return StressScenarioSummary(
        summary_id=f"summary_{datetime.now().isoformat()}",
        timestamp=datetime.now(),
        total_scenarios=total,
        passed=passed,
        failed=total - passed,
        pass_rate=passed / total if total > 0 else 0.0,
        results=results,
        avg_execution_time_ms=sum(r.execution_time_ms for r in results) / total if total > 0 else 0.0,
        max_execution_time_ms=max(r.execution_time_ms for r in results) if results else 0.0
    )
