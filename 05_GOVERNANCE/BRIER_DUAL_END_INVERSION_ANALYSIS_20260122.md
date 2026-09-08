# Dual-End Inversion Strategy: Meta-Analysis

**Date:** 2026-01-22
**Author:** STIG (EC-003)
**Classification:** GOVERNANCE-CRITICAL
**Database Source:** PostgreSQL 17.6 @ 127.0.0.1:54322

---

## Executive Summary

**Hypothesis:** High-confidence predictions at both ends of the probability scale exhibit systematic miscalibration that can be exploited through signal inversion.

**Conclusion:** CONFIRMED - Dual-end inversion reduces system Brier from **0.5662 to 0.4944** (12.68% improvement) using only ex-ante detectable signals.

---

## 1. Edge Cases: Best and Worst Predictions

### TOP 10 - Best Predictions (Brier = 0.000)

| Asset | Regime | Confidence | Outcome | Date |
|-------|--------|------------|---------|------|
| LGEN.L | BULL | 99.92% | TRUE | 2026-01-07 |
| ATOM-USD | BULL | 99.95% | TRUE | 2026-01-08 |
| GLEN.L | BULL | 99.89% | TRUE | 2026-01-13 |
| EOAN.DE | BULL | 99.78% | TRUE | 2026-01-06 |
| KOG.OL | BULL | 99.94% | TRUE | 2026-01-13 |
| DHER.DE | BULL | 99.47% | TRUE | 2026-01-13 |
| ML.PA | BULL | 99.37% | TRUE | 2026-01-13 |
| ASML | BULL | 99.92% | TRUE | 2026-01-13 |
| KLAC | BULL | 99.91% | TRUE | 2026-01-13 |
| SLB | BULL | 99.66% | TRUE | 2026-01-06 |

**Pattern:** All BULL regime, all correct, all >99% confidence.

### BOTTOM 10 - Worst Predictions (Brier ~ 1.0)

| Asset | Regime | Confidence | Outcome | Brier | Date |
|-------|--------|------------|---------|-------|------|
| PGR | STRESS | 99.99% | FALSE | 0.9998 | 2026-01-14 |
| BA.L | BULL | 99.99% | FALSE | 0.9998 | 2026-01-18 |
| PGR | STRESS | 99.99% | FALSE | 0.9998 | 2026-01-13 |
| AIG | STRESS | 99.98% | FALSE | 0.9996 | 2026-01-14 |
| XLB | BULL | 99.98% | FALSE | 0.9996 | 2026-01-14 |
| HAL | BULL | 99.98% | FALSE | 0.9996 | 2026-01-13 |
| ENGI.PA | BULL | 99.98% | FALSE | 0.9996 | 2026-01-14 |
| PHO.OL | BULL | 99.98% | FALSE | 0.9996 | 2026-01-14 |
| GIS | STRESS | 99.98% | FALSE | 0.9996 | 2026-01-11 |
| DE | BULL | 99.97% | FALSE | 0.9994 | 2026-01-14 |

**Pattern:** Mixed BULL/STRESS, all wrong, all >99.9% confidence. Clustering on 2026-01-13/14.

---

## 2. STRESS Regime: Complete Failure

### Hit Rate by Confidence Bucket

| Confidence | Total | Correct | Wrong | Hit Rate | Avg Brier |
|------------|-------|---------|-------|----------|-----------|
| 99.9%+ | 19 | 0 | 19 | **0.00%** | 0.9989 |
| 99.5-99.9% | 12 | 0 | 12 | **0.00%** | 0.9944 |
| 99.0-99.5% | 10 | 0 | 10 | **0.00%** | 0.9867 |
| 95-99% | 26 | 0 | 26 | **0.00%** | 0.9491 |
| 90-95% | 8 | 0 | 8 | **0.00%** | 0.8733 |
| <90% | 173 | 0 | 173 | **0.00%** | 0.3679 |
| **TOTAL** | **248** | **0** | **248** | **0.00%** | - |

**Critical Finding:** STRESS regime has **0% hit rate across ALL confidence levels**.

**Implication:** The STRESS detector is anti-correlated with reality. Every STRESS prediction should be inverted.

---

## 3. BULL Regime: Inverse Calibration at Extremes

### Hit Rate by Confidence Bucket

| Confidence | Total | Correct | Wrong | Hit Rate | Avg Brier |
|------------|-------|---------|-------|----------|-----------|
| 99.9%+ | 216 | 58 | 158 | 26.85% | 0.7305 |
| 99.5-99.9% | 398 | 100 | 298 | 25.13% | 0.7457 |
| 99.0-99.5% | 105 | 35 | 70 | 33.33% | 0.6572 |
| 95-99% | 264 | 113 | 151 | **42.80%** | 0.5452 |
| 90-95% | 326 | 39 | 287 | 11.96% | 0.7767 |
| <90% | 487 | 112 | 375 | 23.00% | 0.4364 |

**Critical Finding:** Higher confidence correlates with LOWER hit rate at extreme levels (99%+).

**Paradox:** The model is most confident when it's most wrong.

---

## 4. BULL@99%+ Breakdown by Asset Class

| Asset Class | Signals | Correct | Wrong | Wrong % | Original Brier | Inverted Brier | Improvement |
|-------------|---------|---------|-------|---------|----------------|----------------|-------------|
| **CRYPTO** | 327 | 40 | 287 | **87.77%** | 0.8742 | 0.1218 | 0.7524 |
| EQUITY | 386 | 153 | 233 | 60.36% | 0.6003 | 0.3942 | 0.2061 |
| FX | 6 | 0 | 6 | **100.00%** | 0.9949 | 0.0000 | 0.9949 |

**Critical Finding:** CRYPTO assets have **87.77% failure rate** at BULL@99%+ confidence.

**Top CRYPTO Offenders:**
- SHIB-USD: 214 failures
- XRP-USD: 32 failures
- ATOM-USD: 9 failures
- DOT-USD: 8 failures

---

## 5. Dual-End Inversion Strategies Compared

| Strategy | Description | Brier | Improvement |
|----------|-------------|-------|-------------|
| CURRENT | No inversion | 0.5662 | - |
| INVERT_STRESS_ONLY | Current IoS-012-B | 0.5454 | 3.69% |
| **INVERT_STRESS_AND_BULL_CRYPTO** | Recommended | **0.4944** | **12.68%** |
| INVERT_ALL_HIGH_CONF_WRONG | Oracle (hindsight) | 0.4055 | 28.39% |

**Recommended Strategy:** INVERT_STRESS_AND_BULL_CRYPTO

- Detectable ex-ante (no hindsight required)
- Achieves 12.68% Brier improvement
- Compliant with hindsight firewall

---

## 6. Key Findings

### Finding 1: STRESS is Systematically Inverted
- 248 signals, 0 correct (0% hit rate)
- The model's STRESS detector is anti-correlated with reality
- **Action:** MANDATORY inversion for all STRESS signals

### Finding 2: BULL@99%+ CRYPTO is Nearly as Broken
- 87.77% failure rate for CRYPTO at BULL@99%+
- Nearly matches STRESS failure profile
- **Action:** Extend inversion to BULL@99%+ CRYPTO signals

### Finding 3: Confidence Inversely Correlates with Accuracy at Extremes
- BULL@99.9%+ has 26.85% hit rate
- BULL@95-99% has 42.80% hit rate
- Model becomes LESS reliable as it becomes MORE confident
- **Action:** Implement confidence damping at extreme levels

### Finding 4: SHIB-USD Dominates Failures
- 214 failures at BULL@99%+ confidence (single asset)
- Possible model breakdown for high-volatility assets
- **Action:** Consider mandatory inversion for SHIB-USD

### Finding 5: 12.68% Brier Improvement Available
- From 0.5662 to 0.4944 using ex-ante rules only
- No hindsight contamination required
- **Action:** Implement INVERT_STRESS_AND_BULL_CRYPTO strategy

---

## 7. Governance Recommendations

### Immediate Actions (P0-P1)

1. **P0:** Extend IoS-012-B to include BULL@99%+ CRYPTO inversion
   - Expected impact: Brier from 0.5454 to 0.4944

2. **P1:** Add SHIB-USD to explicit inversion universe
   - Expected impact: Eliminates 214 catastrophic failures

3. **P1:** Implement confidence ceiling at 99% for BULL regime
   - Expected impact: Prevents overconfidence penalty

### Research Actions (P2)

4. Investigate 2026-01-13/14 event clustering
5. Evaluate EQUITY inversion at BULL@99.5%+ threshold

---

## 8. Hindsight Firewall Compliance

| Signal Type | Detection Method | Compliance |
|-------------|------------------|------------|
| STRESS_ALL | Ex-ante (regime detection) | COMPLIANT |
| BULL_99PCT_CRYPTO | Ex-ante (confidence + asset class) | COMPLIANT |
| ALL_HIGH_CONF_WRONG | Requires outcome (hindsight) | NOT COMPLIANT |

**Recommended strategy is COMPLIANT** - uses only ex-ante detectable rules.

---

## Evidence File

`03_FUNCTIONS/evidence/BRIER_DUAL_END_INVERSION_META_ANALYSIS_20260122.json`

---

**Status:** META_ANALYSIS_COMPLETE
**Next Action:** CEO review for IoS-012-B amendment
