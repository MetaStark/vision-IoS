# Prediction Ledger v1.0

**Forecast recording, outcome tracking, and calibration metrics for FjordHQ Market System**

IoS-010 | Status: ✅ Complete | Version: 1.0.0

---

## Overview

The Prediction Ledger provides a complete audit trail for all forecasts, enabling continuous calibration and evaluation of forecast accuracy.

**Key Features:**
- ✅ Log every forecast with input-state hash
- ✅ Track realized outcomes
- ✅ Reconcile forecasts to outcomes (time-based matching)
- ✅ Compute Brier scores and calibration curves
- ✅ File-based storage (append-only JSON lines)
- ✅ Pure Python, DB-agnostic

---

## Quick Start

```python
from prediction_ledger import (
    ForecastRecord,
    OutcomeRecord,
    record_forecast,
    record_outcome,
    reconcile_forecasts_to_outcomes,
    compute_brier_score,
    compute_calibration_curve,
    append_forecast_to_file,
    load_forecasts,
)
from datetime import datetime, timedelta

# Create forecast
forecast = ForecastRecord(
    forecast_id="f_001",
    timestamp=datetime(2025, 11, 1),
    horizon=timedelta(days=5),
    target_id="regime_bull_to_crisis_5d",
    target_type="REGIME_TRANSITION_PROB",
    forecast_value=0.25,  # 25% probability
    input_state_hash="abc123",
)

# Validate and log
validated = record_forecast(forecast)
append_forecast_to_file("forecasts.jsonl", validated)

# Create outcome (after 5 days)
outcome = OutcomeRecord(
    outcome_id="o_001",
    timestamp=datetime(2025, 11, 6),
    target_id="regime_bull_to_crisis_5d",
    target_type="REGIME_TRANSITION_PROB",
    realized_value=0,  # Did not occur
)

record_outcome(outcome)

# Reconcile and evaluate
forecasts = load_forecasts("forecasts.jsonl")
outcomes = load_outcomes("outcomes.jsonl")

pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)
brier_score = compute_brier_score(pairs)
calibration = compute_calibration_curve(pairs)

print(f"Brier Score: {brier_score.metric_value:.3f}")
print(f"Calibration Error: {calibration.mean_calibration_error:.3f}")
```

---

## Evaluation Metrics

### Brier Score

Measures accuracy of probabilistic forecasts.

- **Formula**: mean((forecast_prob - realized_binary)²)
- **Range**: [0, 1]
- **Perfect**: 0.0
- **Good**: < 0.20

### Calibration Curve

Shows how well-calibrated forecasts are.

- **Well-calibrated**: forecast_prob ≈ realized_frequency
- **Example**: 70% forecasts should realize 70% of the time

### Directional Accuracy (Hit Rate)

Proportion of correct directional forecasts.

- **Range**: [0, 1]
- **Good**: > 0.60

---

## Integration with Scenario Engine

```python
from scenario_engine import generate_scenarios, build_default_target_stack
from scenario_engine.integration import scenario_set_to_forecast_records
from prediction_ledger import ForecastRecord

# Generate scenarios
scenario_set = generate_scenarios(input_state, targets, config)

# Convert to forecast records
forecast_dicts = scenario_set_to_forecast_records(scenario_set)
forecasts = [ForecastRecord.model_validate(d) for d in forecast_dicts]

# Log all forecasts
for forecast in forecasts:
    append_forecast_to_file("forecasts.jsonl", forecast)
```

---

## File Storage Format

### Forecasts (JSON Lines)

```jsonl
{"forecast_id": "f_001", "timestamp": "2025-11-01T12:00:00Z", "target_id": "...", ...}
{"forecast_id": "f_002", "timestamp": "2025-11-02T12:00:00Z", "target_id": "...", ...}
```

### Outcomes (JSON Lines)

```jsonl
{"outcome_id": "o_001", "timestamp": "2025-11-06T12:00:00Z", "target_id": "...", ...}
```

---

## Testing

```bash
pytest prediction_ledger/tests/ -v
```

---

## Architecture

```
prediction_ledger/
├── models.py           # Pydantic schemas
├── ledger.py           # Forecast/outcome validation
├── reconciliation.py   # Matching logic
├── evaluation.py       # Brier, calibration, hit rate
├── storage.py          # File I/O (JSON lines)
├── serialization.py    # JSON helpers
├── utils.py            # Pure functions
└── exceptions.py       # Domain exceptions
```

---

## Future: STIG Integration

STIG will migrate from file storage to Supabase:
- `forecasts` table
- `outcomes` table
- `evaluations` table

All logic remains pure Python, only storage layer changes.

---

## License

Proprietary - FjordHQ Engineering Team

---

## Calibration & Skill Metrics v1.1

**Extension**: Forecast quality assessment with calibration curves and skill scores.

### What We Measure

| Metric | Question Answered | Good Value |
|--------|------------------|------------|
| **Brier Score** | How accurate are our probabilities? | < 0.20 |
| **Brier Skill Score (BSS)** | Do we beat naive baselines? | > 0.05 |
| **Mean Calibration Error (MCE)** | Are our probabilities honest? | < 0.10 |
| **Directional Accuracy** | Do we get the sign right? | > 0.60 |

### Quick Start

```python
from prediction_ledger import (
    build_skill_report,
    build_calibration_curve_v2,
    group_matched_pairs_by_horizon,
    derive_horizon_bucket,
)
from datetime import datetime

# Match forecasts to outcomes
pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)

# Group by horizon bucket
by_horizon = group_matched_pairs_by_horizon(pairs)

# Build skill report for 5-day horizon
pairs_5d = by_horizon["5d"]
report = build_skill_report(
    target_type="REGIME_TRANSITION_PROB",
    horizon_bucket="5d",
    pairs=pairs_5d,
    period_start=datetime(2025, 9, 1),
    period_end=datetime(2025, 11, 18),
    baseline_type="historical_frequency"
)

# Check quality
print(f"BSS: {report.metrics.brier_skill_score:.3f}")
print(f"Well-calibrated: {report.is_well_calibrated}")
print(f"Positive skill: {report.has_positive_skill}")

# Build calibration curve
curve = build_calibration_curve_v2(pairs_5d, "REGIME_TRANSITION_PROB", "5d")
print(f"Mean Calibration Error: {curve.mean_calibration_error:.3f}")
```

### Interpretation

**Brier Skill Score (BSS)**:
- BSS > 0.2: Strong skill (excellent)
- BSS > 0.05: Positive skill (good)
- BSS = 0: No skill (equal to baseline)
- BSS < 0: Negative skill (worse than baseline)

**Mean Calibration Error (MCE)**:
- MCE < 0.05: Excellent calibration
- MCE < 0.10: Good calibration (well-calibrated flag)
- MCE > 0.20: Poor calibration

**Quality Flags**:
- `is_well_calibrated`: MCE < 0.10
- `has_positive_skill`: BSS > 0.05
- `sufficient_sample`: sample_size >= 20

### Example Output

**Skill Report**:
```json
{
  "report_id": "skill_REGIME_TRANSITION_PROB_5d_202509",
  "metrics": {
    "brier_score": 0.16,
    "brier_score_baseline": 0.24,
    "brier_skill_score": 0.33,
    "directional_accuracy": 0.72
  },
  "is_well_calibrated": true,
  "has_positive_skill": true,
  "sufficient_sample": true
}
```

**Interpretation**: 
- 33% improvement over baseline ✅
- Well-calibrated probabilities ✅
- 72% directional accuracy ✅
- **Verdict**: Auto-approve for autonomous operation

---

## Horizon Buckets

Forecasts are grouped into standard horizon buckets:
- `"1d"`: 0-2 days
- `"5d"`: 3-7 days
- `"10d"`: 8-14 days
- `"20d"`: 15-30 days
- `"30d+"`: >30 days

```python
from prediction_ledger import derive_horizon_bucket
from datetime import timedelta

bucket = derive_horizon_bucket(timedelta(days=5))
print(bucket)  # "5d"
```

---

## Grouping & Analysis

```python
# Group by target type and horizon
by_both = group_matched_pairs_by_both(pairs)

for (target_type, horizon_bucket), group_pairs in by_both.items():
    if len(group_pairs) < 20:
        continue  # Skip insufficient samples
    
    report = build_skill_report(
        target_type=target_type,
        horizon_bucket=horizon_bucket,
        pairs=group_pairs,
        period_start=period_start,
        period_end=period_end
    )
    
    print(f"{target_type} {horizon_bucket}: BSS={report.metrics.brier_skill_score:.2f}")
```

---

## Version

Prediction Ledger v1.1 (Calibration & Skill Extension)  
Date: 2025-11-19

