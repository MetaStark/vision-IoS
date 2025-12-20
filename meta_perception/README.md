# FjordHQ Meta-Perception Layer v1.0

**The Perception Brain** — Higher-order inference engine that determines WHAT information matters, WHEN it matters, WHY it changes, and HOW this affects alpha generation capability.

## Overview

The Meta-Perception Layer is a deterministic, pure-Python system that sits above all FjordHQ components and acts as the perception and decision guardrail. It is NOT a predictor or strategy — it is a higher-order system that:

- Interprets the market's informational structure
- Detects intent and pressure from other market participants
- Identifies information shocks before price reacts
- Quantifies uncertainty, entropy, and noise
- Evaluates when all signals should be ignored
- Detects nonlinear regime pivots BEFORE they manifest
- Acts as a guardrail for all downstream modules

## Architecture

```
Meta-Perception Layer
├── Core Perception Modules (pure functions)
│   ├── Entropy Computation
│   ├── Noise Evaluation
│   ├── Intent Detection
│   ├── Reflexivity Measurement
│   ├── Shock Detection
│   └── Regime Sentinel
│
├── Orchestration Layer
│   └── step() — Main perception cycle
│
├── Advanced Features
│   ├── Diagnostic Engine
│   ├── Feature Importance
│   ├── Uncertainty Override Logger
│   └── Stress Scenario Simulator
│
└── Integration Layer
    ├── Artifact Manager
    └── STIG Adapter API
```

## Key Features

### ✅ Pure & Deterministic
- All core modules are pure functions (same inputs → same outputs)
- Zero external dependencies
- No database or network calls
- Fully reproducible

### ✅ Pydantic v2 (Frozen Models)
- All data models are immutable
- Full type validation
- JSON serialization built-in

### ✅ Performance Optimized
- Target: <150ms per perception cycle
- Built-in profiling
- Performance gates enforced

### ✅ Comprehensive Diagnostics
- Step-by-step numerical traces
- Feature importance tracking
- Uncertainty override logging

### ✅ Stress-Tested
- 6 built-in stress scenarios
- Flash crash, funding explosions, liquidity crises
- ≥80% pass rate required

## Quick Start

```python
from meta_perception import step, PerceptionState, MetaPerceptionInput, PerceptionConfig
from datetime import datetime

# Configuration
config = PerceptionConfig(config_id="prod", version="1.0.0")

# Initial state
state = PerceptionState(
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

# Inputs
inputs = MetaPerceptionInput(
    timestamp=datetime.now(),
    market_data={"BTC": [50000.0, 50100.0, 50200.0]},
    features={"open_interest_change": 0.1}
)

# Run perception cycle
new_state, output = step(state, inputs, config)

# Check decision
print(f"Should act: {output.decision.should_act}")
print(f"Confidence: {output.decision.confidence}")
print(f"Rationale: {output.decision.rationale}")
```

## STIG Integration

```python
from meta_perception.adapters import STIGAdapterAPI

# Get latest perception
snapshot = STIGAdapterAPI.get_latest_perception_snapshot()

if snapshot:
    print(f"Should act: {snapshot.state.should_act}")
    print(f"Noise level: {snapshot.noise_score.noise_level}")
    print(f"Total uncertainty: {snapshot.state.total_uncertainty}")

# Get system health
health = STIGAdapterAPI.get_system_health()
print(f"Status: {health['status']}")
```

## Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest meta_perception/tests/ -v

# Run with coverage
pytest meta_perception/tests/ --cov=meta_perception --cov-report=html

# Run stress scenarios
pytest meta_perception/tests/scenarios/ -v
```

## Artifacts Generated

The system generates the following artifacts:

1. **perception_snapshot.json** — Complete perception state
2. **perception_delta.json** — State changes
3. **intent_report.json** — Intent analysis
4. **shock_report.json** — Shock tracking
5. **entropy_report.json** — Entropy analysis
6. **feature_importance_report.json** — Feature importance
7. **uncertainty_override_log.jsonl** — Override logs

All artifacts are stored in `artifacts_output/` directory.

## Performance Metrics

- **Computation time**: <150ms (enforced)
- **Test coverage**: ≥85%
- **Stress scenario pass rate**: ≥80%
- **Memory usage**: <50MB typical

## Version

**v1.0.0** — Production ready

## License

Proprietary — FjordHQ Team

## Support

For issues or questions, contact the FjordHQ development team.
