# STIG TECHNICAL CONTEXT: REGIME CLASSIFIER DIAGNOSIS
## Prepared for CEIO/CDMO per CEO-DIR-2025-RC-001

**Date:** 2025-12-26
**Prepared By:** STIG (CTO)
**Status:** TECHNICAL CONTEXT ONLY (not diagnosis)

---

## CRITICAL FINDING: CLASSIFIER STOPPED ON 2025-12-11

The regime classifier was functioning correctly until **December 10, 2025**, then experienced a catastrophic failure starting **December 11, 2025**.

### Evidence: Daily Classification Distribution

| Date | BULL | BEAR | NEUTRAL | STRESS | Total Assets |
|------|------|------|---------|--------|--------------|
| Dec 8 | 135 | 99 | 202 | 27 | **463** |
| Dec 9 | 147 | 104 | 184 | 28 | **463** |
| Dec 10 | 171 | 97 | 164 | 26 | **458** |
| **Dec 11** | 0 | 0 | 4 | 0 | **4** |
| Dec 12-25 | 0 | 0 | 3 | 0 | **3** |

### Two Simultaneous Failures

1. **Diversity Collapse:** 100% NEUTRAL after Dec 10
2. **Asset Count Collapse:** 458 assets → 3-4 assets (BTC, ETH, SOL only)

---

## LAST KNOWN GOOD STATE (Dec 10, 2025)

Sample of diverse classifications on last working day:

| Asset | Classification | Confidence |
|-------|---------------|------------|
| MKR-USD | BULL | 0.77 |
| FIL-USD | BEAR | 0.95 |
| VET-USD | BEAR | 0.84 |
| QNT-USD | STRESS | 0.72 |
| SNX-USD | BEAR | 0.79 |

The classifier was producing high-confidence diverse classifications.

---

## CURRENT STATE (Dec 11-25, 2025)

| Asset | Classification | Confidence | CRIO Driver |
|-------|---------------|------------|-------------|
| BTC-USD | NEUTRAL | 0.60-0.80 | **UNKNOWN** |
| ETH-USD | NEUTRAL | 0.60-0.70 | **UNKNOWN** |
| SOL-USD | NEUTRAL | 0.60-0.90 | **UNKNOWN** |

**Note:** `crio_dominant_driver = UNKNOWN` suggests upstream data issue.

---

## HYPOTHESIS FOR CEIO/CDMO

Based on technical evidence, likely failure modes:

### H1: Asset Coverage Collapse (HIGH PROBABILITY)
- Only 3 assets (BTC, ETH, SOL) are being processed
- 450+ other assets stopped receiving classifications
- Possible cause: Data pipeline filter change, asset list configuration

### H2: Upstream Data Starvation (HIGH PROBABILITY)
- `crio_dominant_driver = UNKNOWN` on all recent entries
- `technical_regime = NULL` on all recent entries
- Suggests CRIO (macro context) data not flowing

### H3: Threshold Saturation (MEDIUM PROBABILITY)
- Classifier defaulting to NEUTRAL when uncertain
- May be related to confidence threshold change

### H4: Manual Override / Safety Lock (LOW PROBABILITY)
- Could be intentional governance lock
- Would explain sudden, complete change

---

## TABLES TO INVESTIGATE

| Table | Rows | Purpose |
|-------|------|---------|
| `fhq_perception.regime_daily` | 39 recent | Daily classifications |
| `fhq_research.regime_predictions_v2` | 39 | Model predictions |
| `fhq_canonical.g4_1_regime_rotation_results` | 49 | Rotation decisions |

**Empty tables (potential issue):**
- `fhq_finn.regime_states` (0 rows)
- `fhq_finn.regime_tracker` (0 rows)
- `fhq_hmm.regime_predictions` (0 rows)
- `vision_signals.regime_engine_state` (0 rows)

---

## CRITICAL: V4 MIGRATION ON DEC 11

**The file `ios003_daily_regime_update_v4.py` was created on 2025-12-11** - the exact date the failure started.

### V4 File Header Evidence
```
Date: 2025-12-11
Schedule: Daily at 00:20 UTC
Key v4 Changes from v2:
- 3-4 states (BULL, NEUTRAL, BEAR, [STRESS]) vs 9 states
- Asset-class specific models (CRYPTO, FX, EQUITIES)
```

### Task Registry (Created Dec 15)
```
task_name: ios003_daily_regime_update_v4
function_path: 03_FUNCTIONS/ios003_daily_regime_update_v4.py
enabled: true
```

### Probable Root Cause

The v4 migration on Dec 11 appears to have:
1. Replaced the working v2 regime classifier
2. Reduced asset coverage from 458 → 3 (possibly only CRYPTO class)
3. Changed regime semantics (9 states → 3-4 states)
4. Not been properly initialized or calibrated

---

## QUESTIONS FOR CEIO/CDMO

1. **Was the v4 migration intentional?**
   - Was v2 → v4 transition approved?
   - Was there a cutover plan?

2. **Why only 3 assets in v4?**
   - Is v4 only processing CRYPTO asset class?
   - Are FX and EQUITIES asset classes disabled?

3. **Why is v4 producing only NEUTRAL?**
   - Are model parameters initialized?
   - Is the IOHMM model trained?
   - Are thresholds calibrated?

4. **Why is CRIO driver UNKNOWN?**
   - Is macro context data flowing to v4?
   - Did v4 break CRIO integration?

---

## STIG CONSTRAINTS

Per CEO-DIR-2025-RC-001, STIG will:

- Provide technical context only
- Not implement any fixes
- Not modify classifier code
- Await CEO approval of CEIO/CDMO diagnosis

---

**Prepared by:** STIG
**Timestamp:** 2025-12-26T18:30:00Z
**Classification:** DIAGNOSTIC CONTEXT - NOT A FIX
