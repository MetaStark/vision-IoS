# LVI Definition - Learning Velocity Index

**Dato:** 2026-01-23
**Direktiv:** CEO-DIR-2026-023 Order 4
**Status:** DEFINED
**Computed By:** STIG (EC-003)

---

## OVERVIEW

The Learning Velocity Index (LVI) measures how quickly and reliably the system converts market events into validated learning. It is designed to be **non-gameable**: volume alone does not increase LVI without integrity.

---

## FORMULA

```
LVI = (Completed_Experiments × Integrity_Rate × Coverage_Rate × Time_Factor × Brier_Component) / 10
```

### Components

| Component | Definition | Range | Target |
|-----------|------------|-------|--------|
| Completed_Experiments | Decision packs with outcomes in last 7 days | 0-∞ | 10+/week |
| Integrity_Rate | % of decisions with evidence_hash | 0-1 | > 0.9 |
| Coverage_Rate | % of IoS-016 events with hypotheses | 0-1 | > 0.8 |
| Time_Factor | Evaluation speed penalty | 0.1-1 | > 0.5 |
| Brier_Component | Calibration quality multiplier | 0.1-1 | > 0.5 |

---

## TIME FACTOR CALCULATION

```
Time_Factor = max(0.1, 1.0 - (Median_Eval_Hours / 48))

Examples:
- 0 hours  → 1.0 (perfect)
- 12 hours → 0.75 (good)
- 24 hours → 0.5 (acceptable)
- 36 hours → 0.25 (slow)
- 48+ hours → 0.1 (penalty floor)
```

---

## BRIER COMPONENT CALCULATION

```
Brier_Component = max(0.1, 1.0 - (Brier_Score × 2.0))

Examples:
- Brier 0.10 → 0.80 (excellent)
- Brier 0.25 → 0.50 (average)
- Brier 0.35 → 0.30 (poor)
- Brier 0.45+ → 0.10 (penalty floor)
```

---

## GRADING SCALE

| LVI Score | Grade | Interpretation |
|-----------|-------|----------------|
| 0.8 - 1.0 | A | Excellent learning velocity |
| 0.6 - 0.8 | B | Good learning velocity |
| 0.4 - 0.6 | C | Acceptable learning velocity |
| 0.2 - 0.4 | D | Needs improvement |
| 0.0 - 0.2 | F | Learning loop blocked |

---

## NON-GAMEABILITY PROPERTIES

### 1. Volume Alone is Insufficient
- High experiment count with low integrity = low LVI
- Must have evidence hashes to count

### 2. Speed Alone is Insufficient
- Fast evaluation with poor coverage = low LVI
- Must cover IoS-016 events

### 3. Coverage Alone is Insufficient
- High coverage with slow evaluation = low LVI
- Must close loop within 24-48h

### 4. All Components Multiplicative
- Any zero component → LVI = 0
- Balanced excellence required

---

## BOTTLENECK IDENTIFICATION

The system identifies the primary limiting factor:

| Condition | Bottleneck Message |
|-----------|-------------------|
| completed = 0 | "No completed experiments - need to close learning loop" |
| integrity < 0.5 | "Low integrity rate - evidence hashes missing" |
| coverage < 0.5 | "Low coverage rate - events without hypotheses" |
| time_factor < 0.5 | "Slow evaluation - median time > 24h" |
| brier < 0.5 | "Poor calibration - Brier score too high" |

---

## DATABASE STORAGE

```sql
-- LVI snapshots stored in fhq_ops.control_room_lvi
SELECT
    lvi_score,
    completed_experiments,
    integrity_rate,
    coverage_rate,
    median_evaluation_time_hours,
    time_factor,
    brier_component,
    computed_at
FROM fhq_ops.control_room_lvi
ORDER BY computed_at DESC
LIMIT 7;  -- Last week
```

---

## COMPUTATION FREQUENCY

- **Daily:** Full LVI computation at 00:00 UTC
- **On-demand:** Via `python lvi_calculator.py`
- **Dashboard:** Real-time view from latest snapshot

---

## EVIDENCE GENERATION

Each LVI computation generates an evidence bundle:

```json
{
  "directive": "CEO-DIR-2026-023-ORDER-4",
  "evidence_type": "LVI_COMPUTATION",
  "computed_at": "2026-01-23T12:00:00Z",
  "computed_by": "STIG",
  "ec_contract": "EC-003",
  "lvi_data": {...},
  "evidence_hash": "abc123..."
}
```

---

## IMPROVEMENT STRATEGIES

### To Increase Completed Experiments
1. Ensure IoS-016 event pipeline active
2. Generate hypotheses before events
3. Record outcomes within 24h

### To Increase Integrity Rate
1. Always attach evidence_hash to decision_packs
2. Link decisions to hypothesis_ledger
3. Maintain hash chain

### To Increase Coverage Rate
1. Pre-commit hypotheses for all upcoming events
2. Expand IoS-016 event calendar
3. Automate hypothesis generation

### To Improve Time Factor
1. Set T+24h alerts for outcome recording
2. Automate outcome capture where possible
3. Prioritize high-impact events

### To Improve Brier Component
1. Apply recalibration to overconfident forecasts
2. Use Murphy decomposition diagnostics
3. Validate against out-of-sample data

---

## APPROVAL

| Role | Status | Signature |
|------|--------|-----------|
| STIG | DELIVERED | EC-003 |
| CEO | PENDING | - |
