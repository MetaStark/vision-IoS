# Brier Calibration Meta-Analysis

**Dato:** 2026-01-23
**Direktiv:** CEO-DIR-2026-023 Order 6
**Status:** COMPLETE
**Computed By:** STIG (EC-003)

---

## EXECUTIVE SUMMARY

This document provides a research-backed analysis of Brier score calibration practices and their application to FHQ's forecast evaluation system. The analysis covers:

1. Proper scoring rule theory
2. Murphy decomposition for diagnostics
3. Expected Calibration Error (ECE) critique
4. Recalibration methods
5. FHQ current state analysis
6. Recommendations

---

## 1. RESEARCH FOUNDATION

### 1.1 Proper Scoring Rules

**Source:** Gneiting & Raftery (2007) - "Strictly Proper Scoring Rules, Prediction, and Estimation"

A scoring rule S(p, y) is **proper** if the expected score is maximized when the forecaster reports their true belief. The Brier score is strictly proper:

```
Brier(p, y) = (p - y)²

Where:
- p = forecast probability (0-1)
- y = outcome (0 or 1)
```

**Key Insight:** Proper scoring rules incentivize honesty. Forecasters cannot game the system by reporting false probabilities.

### 1.2 Brier vs Log Loss

| Metric | Formula | Properties |
|--------|---------|------------|
| Brier | (p - y)² | Bounded [0,1], penalizes all errors equally |
| Log Loss | -y log(p) - (1-y) log(1-p) | Unbounded, harsh on confident errors |

**FHQ Recommendation:** Continue using Brier score. It is bounded, interpretable, and provides comparable results across assets.

### 1.3 Murphy Decomposition

**Source:** Murphy (1973) - "A New Vector Partition of the Probability Score"

The Brier score decomposes into three components:

```
Brier = Reliability - Resolution + Uncertainty

Where:
- Reliability: How well calibrated (lower is better)
- Resolution: How bold/informative (higher is better)
- Uncertainty: Base rate variance (fixed for dataset)
```

**Interpretation:**
- A well-calibrated forecaster has low Reliability
- A skilled forecaster has high Resolution
- Uncertainty is dataset-dependent

---

## 2. FHQ CURRENT STATE ANALYSIS

### 2.1 Forecast Skill Metrics Summary

```
Source: fhq_research.forecast_skill_metrics
Records: 141 samples

Metric          | Value
----------------|--------
Avg Brier       | 0.3125
Min Brier       | 0.0233
Max Brier       | 0.3233
Std Brier       | 0.0252
Avg Forecasts   | 16,457
Avg Hit Rate    | 51.65%
```

### 2.2 Murphy Decomposition Summary

```
Source: fhq_governance.brier_decomposition
Records: 474 decompositions

Component       | Value     | Interpretation
----------------|-----------|----------------
Avg Brier       | 0.5410    | Higher than skill metrics (different sample)
Avg Reliability | 0.4273    | HIGH - forecasts not well calibrated
Avg Resolution  | 0.0577    | LOW - forecasts not informative
Avg Uncertainty | 0.1704    | Base rate ~35%
Avg BSS         | -1.8706   | NEGATIVE - worse than climatology
Overconfident   | 465/474   | 98% overconfident
Well Calibrated | 0/474     | 0% well calibrated
Has Resolution  | 304/474   | 64% have meaningful resolution
```

### 2.3 Diagnosis

**Key Finding:** The decomposition reveals systematic overconfidence with low resolution.

1. **Reliability Issue:** Average reliability of 0.43 indicates forecasts systematically deviate from observed frequencies
2. **Resolution Issue:** Low resolution (0.06) means forecasts cluster around the base rate rather than providing bold, informative predictions
3. **Skill Issue:** Negative BSS indicates performance worse than always predicting the base rate

---

## 3. EXPECTED CALIBRATION ERROR (ECE) CRITIQUE

### 3.1 ECE Definition

**Source:** Naeini et al. (2015) - "Obtaining Well Calibrated Probabilities Using Bayesian Binning into Quantiles"

```
ECE = Σ (n_b / N) × |acc(b) - conf(b)|

Where:
- n_b = samples in bin b
- N = total samples
- acc(b) = accuracy in bin b
- conf(b) = average confidence in bin b
```

### 3.2 ECE Limitations

**Source:** Nixon et al. (2019), Gruber & Buettner (2022)

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Bin count sensitivity | Different bin counts give different ECE | Use adaptive binning |
| Sparse bins | Low sample bins dominate error | Minimum bin size requirement |
| Non-convexity | Cannot gradient descent on ECE | Use Brier as primary |

**FHQ Recommendation:** Use ECE as secondary diagnostic, not primary metric. Brier remains primary.

---

## 4. RECALIBRATION METHODS

### 4.1 Platt Scaling

**Source:** Platt (1999) - "Probabilistic Outputs for Support Vector Machines"

```
p_calibrated = σ(A × p_raw + B)

Where:
- σ = sigmoid function
- A, B = parameters fit on validation set
```

**Applicability to FHQ:** Limited. Requires sufficient high-confidence forecasts which current system lacks.

### 4.2 Isotonic Regression

**Source:** Zadrozny & Elkan (2001) - "Learning and Making Decisions When Costs and Probabilities are Both Unknown"

Non-parametric method that fits monotonic function to calibrate probabilities.

**Applicability to FHQ:** Possible for post-hoc correction. Requires held-out calibration set.

### 4.3 Temperature Scaling

**Source:** Guo et al. (2017) - "On Calibration of Modern Neural Networks"

```
p_calibrated = softmax(logits / T)

Where:
- T = temperature parameter (T > 1 reduces confidence)
```

**Applicability to FHQ:** Indirect. Can dampen overconfidence by scaling confidence scores.

---

## 5. FHQ SKILL FACTOR FORMULA ANALYSIS

### 5.1 Current Formula

```python
skill_factor = max(0.1, 1.0 - (brier_score * 1.8))

At Brier 0.3125:
skill_factor = max(0.1, 1.0 - (0.3125 * 1.8))
skill_factor = max(0.1, 1.0 - 0.5625)
skill_factor = 0.4375
```

### 5.2 Formula Properties

| Brier | Skill Factor | Interpretation |
|-------|--------------|----------------|
| 0.00 | 1.00 | Perfect forecaster |
| 0.10 | 0.82 | Excellent |
| 0.25 | 0.55 | Good |
| 0.30 | 0.46 | Average |
| 0.35 | 0.37 | Below average |
| 0.50 | 0.10 | Floor (penalty) |
| 0.55+ | 0.10 | Maximum penalty |

### 5.3 Formula Assessment

**Strengths:**
- Bounded output [0.1, 1.0] prevents extreme weights
- Floor at 0.1 ensures some signal still considered
- Multiplier 1.8 provides reasonable sensitivity

**Weaknesses:**
- Does not account for sample size (confidence)
- Does not distinguish reliability vs resolution issues
- Linear relationship may not match empirical skill curves

---

## 6. GOOD JUDGMENT PROJECT BENCHMARKS

**Source:** Tetlock & Gardner (2015) - "Superforecasting"

| Forecaster Type | Typical Brier |
|-----------------|---------------|
| Random guess | 0.250 |
| Typical forecaster | 0.220-0.240 |
| Good forecaster | 0.180-0.200 |
| Superforecaster | 0.140-0.160 |
| Perfect foresight | 0.000 |

**FHQ Assessment:** At Brier 0.31, FHQ forecasts are below typical forecaster performance. However, the forecast_skill_metrics sample shows Brier 0.31 while brier_decomposition shows 0.54 - this discrepancy needs investigation.

---

## 7. RECOMMENDATIONS

### 7.1 Immediate Actions

| Action | Priority | Rationale |
|--------|----------|-----------|
| Reconcile Brier discrepancy | HIGH | forecast_skill_metrics (0.31) vs brier_decomposition (0.54) |
| Add sample size weighting | MEDIUM | Higher confidence for larger samples |
| Implement Murphy decomposition dashboard | MEDIUM | Diagnose reliability vs resolution issues |

### 7.2 Formula Enhancement Options

**Option A: Keep Current Formula**
- Pros: Simple, working, understood
- Cons: Does not address overconfidence

**Option B: Add Reliability Penalty**
```python
skill_factor = max(0.1, 1.0 - (brier * 1.8) - (reliability * 0.5))
```
- Pros: Penalizes systematic miscalibration
- Cons: Requires Murphy decomposition data

**Option C: Sample Size Adjustment**
```python
confidence = 1 - 1/sqrt(sample_size)
skill_factor = max(0.1, (1.0 - brier * 1.8) * confidence)
```
- Pros: Higher trust for larger samples
- Cons: More complex

**Recommendation:** Option A (keep current) until decomposition discrepancy resolved.

### 7.3 Validation Protocol

1. **Time-aware splits:** No future data leakage
2. **Out-of-sample evaluation:** 20% holdout
3. **Bootstrap confidence intervals:** 1000 iterations
4. **Regime stratification:** Test across RISK_ON, RISK_OFF, NEUTRAL

---

## 8. APPENDIX: KEY REFERENCES

1. Gneiting, T., & Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *Journal of the American Statistical Association*, 102(477), 359-378.

2. Murphy, A. H. (1973). A new vector partition of the probability score. *Journal of Applied Meteorology*, 12(4), 595-600.

3. Nixon, J., Dusenberry, M. W., Zhang, L., Jerfel, G., & Tran, D. (2019). Measuring calibration in deep learning. *CVPR Workshops*.

4. Gruber, S., & Buettner, F. (2022). Better uncertainty calibration via proper scores for classification and beyond. *NeurIPS*.

5. Platt, J. C. (1999). Probabilistic outputs for support vector machines. *Advances in Large Margin Classifiers*, 61-74.

6. Zadrozny, B., & Elkan, C. (2001). Learning and making decisions when costs and probabilities are both unknown. *KDD*.

7. Tetlock, P. E., & Gardner, D. (2015). *Superforecasting: The Art and Science of Prediction*. Crown.

---

## APPROVAL

| Role | Status | Signature |
|------|--------|-----------|
| STIG | DELIVERED | EC-003 |
| CEO | PENDING | - |
| VEGA | PENDING | - |
| LARS | PENDING | - |
