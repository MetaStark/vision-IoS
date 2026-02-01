# Brier Calibration Implementation Proposal

**Dato:** 2026-01-23
**Direktiv:** CEO-DIR-2026-023 Order 6
**Status:** PROPOSAL
**Computed By:** STIG (EC-003)

---

## 1. CURRENT STATE

### 1.1 Brier Score Sources

| Source | Avg Brier | Records | Interpretation |
|--------|-----------|---------|----------------|
| forecast_skill_metrics | 0.3125 | 141 | Primary calibration metric |
| brier_decomposition | 0.5410 | 474 | Decomposition analysis |

**Critical Discrepancy:** The two data sources show significantly different Brier scores. This must be reconciled before any formula changes.

### 1.2 Current Skill Factor Formula

```python
skill_factor = max(0.1, 1.0 - (brier_score * 1.8))
```

| Property | Value |
|----------|-------|
| At current Brier (0.31) | 0.44 |
| Floor | 0.10 |
| Ceiling | 1.00 |
| Breakeven Brier | 0.50 |

---

## 2. RESEARCH-BACKED RECOMMENDATIONS

### 2.1 Murphy Decomposition Integration

**Recommendation:** ADOPT

```python
# Add Murphy decomposition to diagnostic pipeline
def murphy_decomposition(forecasts, outcomes, bins=10):
    """
    Compute Brier decomposition.

    Returns:
        reliability: Calibration error (lower is better)
        resolution: Forecast informativeness (higher is better)
        uncertainty: Dataset base rate variance (fixed)
    """
    # Bin forecasts
    bin_edges = np.linspace(0, 1, bins + 1)
    bin_indices = np.digitize(forecasts, bin_edges) - 1

    base_rate = np.mean(outcomes)
    uncertainty = base_rate * (1 - base_rate)

    reliability = 0
    resolution = 0

    for b in range(bins):
        mask = bin_indices == b
        if mask.sum() == 0:
            continue

        n_b = mask.sum()
        o_b = outcomes[mask].mean()  # Observed frequency in bin
        f_b = forecasts[mask].mean()  # Forecast frequency in bin

        reliability += (n_b / len(forecasts)) * (f_b - o_b) ** 2
        resolution += (n_b / len(forecasts)) * (o_b - base_rate) ** 2

    return {
        'reliability': reliability,
        'resolution': resolution,
        'uncertainty': uncertainty,
        'brier': reliability - resolution + uncertainty
    }
```

**Rationale:** Murphy decomposition provides diagnostic insight that raw Brier cannot. It distinguishes calibration errors from informativeness issues.

### 2.2 ECE as Secondary Metric

**Recommendation:** ADOPT WITH CAVEATS

```python
def expected_calibration_error(forecasts, outcomes, bins=10, min_bin_size=30):
    """
    Compute ECE with minimum bin size requirement.
    """
    bin_edges = np.linspace(0, 1, bins + 1)
    ece = 0
    total_samples = 0

    for i in range(bins):
        mask = (forecasts >= bin_edges[i]) & (forecasts < bin_edges[i+1])
        n_b = mask.sum()

        if n_b < min_bin_size:
            continue  # Skip sparse bins

        accuracy = outcomes[mask].mean()
        confidence = forecasts[mask].mean()

        ece += n_b * abs(accuracy - confidence)
        total_samples += n_b

    return ece / total_samples if total_samples > 0 else None
```

**Caveats:**
- Use minimum bin size (30) to avoid sparse bin issues
- Report alongside Brier, not as replacement
- Be aware of bin count sensitivity

### 2.3 Platt Scaling

**Recommendation:** DEFER

Current system lacks sufficient high-confidence forecasts for effective Platt scaling. Defer until:
- Forecast volume increases
- Confidence distribution broadens
- Held-out calibration set available

### 2.4 Temperature Scaling

**Recommendation:** CONSIDER FOR OVERCONFIDENCE

If overconfidence persists after discrepancy resolution:

```python
def temperature_scale(confidence, T=1.5):
    """
    Reduce overconfidence by scaling toward 0.5.
    T > 1 reduces confidence spread.
    """
    logit = np.log(confidence / (1 - confidence))
    scaled_logit = logit / T
    return 1 / (1 + np.exp(-scaled_logit))
```

---

## 3. PROPOSED CHANGES

### 3.1 Phase 1: Investigation (Immediate)

**No formula changes until discrepancy resolved.**

| Task | Priority | Owner |
|------|----------|-------|
| Reconcile FSM vs BD Brier scores | P0 | CDMO |
| Document data pipeline differences | P0 | STIG |
| Verify sample populations match | P0 | STIG |

### 3.2 Phase 2: Diagnostics (Post-Investigation)

| Task | Priority | Owner |
|------|----------|-------|
| Add Murphy decomposition to Control Room | P1 | STIG |
| Display reliability/resolution separately | P1 | STIG |
| Alert on high reliability (> 0.3) | P1 | STIG |

### 3.3 Phase 3: Formula Enhancement (If Needed)

**Only if investigation reveals formula issue:**

**Option A: Add Reliability Penalty**
```python
# Penalize systematic miscalibration
skill_factor = max(0.1, (1.0 - brier * 1.8) * (1.0 - reliability * 0.5))
```

**Option B: Sample Size Adjustment**
```python
# Higher trust for larger samples
confidence_factor = 1 - 1 / np.sqrt(sample_size + 1)
skill_factor = max(0.1, (1.0 - brier * 1.8) * confidence_factor)
```

**Option C: Brier Skill Score Based**
```python
# Use BSS relative to climatology
bss = 1 - (brier / climatology_brier)
skill_factor = max(0.1, min(1.0, 0.5 + bss * 0.5))
```

---

## 4. VALIDATION PROTOCOL

### 4.1 Time-Aware Splits

```python
# Prevent future data leakage
train_end = datetime(2025, 12, 31)
test_start = datetime(2026, 1, 1)

train_data = forecasts[forecasts.timestamp < train_end]
test_data = forecasts[forecasts.timestamp >= test_start]
```

### 4.2 Out-of-Sample Evaluation

- Hold out 20% of data for validation
- Never tune on test set
- Report both train and test Brier

### 4.3 Bootstrap Confidence Intervals

```python
def bootstrap_brier(forecasts, outcomes, n_iterations=1000):
    """Compute 95% CI for Brier score."""
    scores = []
    for _ in range(n_iterations):
        idx = np.random.choice(len(forecasts), size=len(forecasts), replace=True)
        scores.append(brier_score(forecasts[idx], outcomes[idx]))
    return np.percentile(scores, [2.5, 97.5])
```

### 4.4 Regime Stratification

Test across all regime types:
- RISK_ON
- RISK_OFF
- NEUTRAL

Report regime-specific Brier scores.

---

## 5. ROLLBACK PLAN

### 5.1 Preserve Current Formula

```python
SKILL_FORMULA_V1 = lambda brier: max(0.1, 1.0 - (brier * 1.8))
```

### 5.2 Feature Flag

```python
SKILL_FORMULA_VERSION = os.environ.get('SKILL_FORMULA_VERSION', 'V1')

def compute_skill_factor(brier, reliability=None, sample_size=None):
    if SKILL_FORMULA_VERSION == 'V1':
        return max(0.1, 1.0 - (brier * 1.8))
    elif SKILL_FORMULA_VERSION == 'V2':
        # New formula with reliability
        return max(0.1, (1.0 - brier * 1.8) * (1.0 - reliability * 0.5))
    else:
        return SKILL_FORMULA_V1(brier)
```

### 5.3 Rollback Trigger

- If Brier increases > 10% after formula change
- If hit rate drops below 50%
- If signal quality complaints from CEO

---

## 6. ACCEPTANCE TESTS

| Test | Current | Target | Status |
|------|---------|--------|--------|
| Brier < 0.30 | 0.3125 | 0.30 | PENDING |
| Reliability < 0.20 | 0.4273 | 0.20 | FAILING |
| Resolution > 0.10 | 0.0577 | 0.10 | FAILING |
| Well-calibrated % > 50% | 0% | 50% | FAILING |
| No degradation in hit rate | 51.65% | 51.65% | BASELINE |

---

## 7. TIMELINE

| Phase | Start | End | Deliverable |
|-------|-------|-----|-------------|
| Investigation | 2026-01-23 | 2026-01-30 | Discrepancy report |
| Diagnostics | 2026-01-31 | 2026-02-07 | Murphy dashboard |
| Enhancement (if needed) | 2026-02-08 | 2026-02-21 | New formula |
| Validation | 2026-02-22 | 2026-02-28 | Test results |
| Rollout | 2026-03-01 | - | Production |

---

## 8. DECISION REQUIRED

### Current Formula Verdict: NO CHANGE

**Rationale:**
1. Data discrepancy must be resolved first
2. Current formula is working (signals being generated)
3. Changes risk destabilizing IoS-013 FULL integration

### Next Steps:
1. CEO approval of investigation phase
2. CDMO to reconcile data sources
3. STIG to implement Murphy dashboard
4. Reconvene after investigation complete

---

## APPROVAL

| Role | Status | Signature |
|------|--------|-----------|
| STIG | DELIVERED | EC-003 |
| CEO | PENDING | - |
| VEGA | PENDING | - |
| LARS | PENDING | - |
