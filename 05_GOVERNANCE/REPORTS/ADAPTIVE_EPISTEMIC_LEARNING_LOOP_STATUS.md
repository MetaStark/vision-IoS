# Adaptive Epistemic Learning Loop — Database Status Report

**Report ID:** AELL-2026-002
**Date:** 2026-01-06
**Author:** STIG (CTO)
**Classification:** Technical Assessment
**Status:** ACTIVATED per CEO-DIR-2026-META-LEARNING-001

---

## Executive Summary

The Vision-IoS database implements **~70% of an Adaptive Epistemic Learning Loop**, with strong foundations in outcome capture, knowledge persistence, and governance-controlled calibration.

**UPDATE 2026-01-06:** CEO-DIR-2026-META-LEARNING-001 has **ACTIVATED** automatic meta-learning. The Epistemic Proposal Engine now generates improvement proposals autonomously.

**Key Principle:** System PROPOSES, humans APPROVE. Meta-learning observes and suggests, but VEGA approval gates remain in place for all calibration changes.

---

## 1. What is an Adaptive Epistemic Learning Loop?

```
┌─────────────────────────────────────────────────────────────┐
│                   ADAPTIVE EPISTEMIC LOOP                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│    OBSERVE          HYPOTHESIZE        ACT         EVALUATE  │
│       │                  │              │              │      │
│       ▼                  ▼              ▼              ▼      │
│   ┌───────┐         ┌───────┐      ┌───────┐     ┌───────┐  │
│   │Market │   →     │FINN   │  →   │Execute│  →  │Outcome│  │
│   │Data   │         │Needle │      │Trade  │     │Capture│  │
│   └───────┘         └───────┘      └───────┘     └───────┘  │
│       ↑                                              │       │
│       │              META-LEARNING                   │       │
│       │         (Adjust HOW we learn)                │       │
│       │                  │                           │       │
│       │                  ▼                           │       │
│       │          ┌─────────────┐                     │       │
│       └──────────│ Calibration │◄────────────────────┘       │
│                  │   Engine    │                             │
│                  └─────────────┘                             │
│                         │                                    │
│                         ▼                                    │
│              ┌───────────────────┐                           │
│              │ EPISTEMIC UPDATE  │                           │
│              │ - Trust weights   │                           │
│              │ - Confidence cal. │                           │
│              │ - Source validity │                           │
│              └───────────────────┘                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. IMPLEMENTED Components ✅

### 2.1 Ground Truth Outcome Capture
**Migration:** `165_canonical_outcome_capture.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
fhq_canonical.canonical_outcomes
├── needle_id → Links to golden_needles (CEO Directive traceability)
├── pnl_absolute, pnl_percent → Ground truth metrics
├── entry_regime, exit_regime → Regime context
├── max_favorable_excursion, max_adverse_excursion → Risk capture
└── needle_eqs_score, needle_sitc_confidence → Snapshot at entry
```

**Function:** `capture_trade_outcome()` — Captures ground truth when trades exit.

> *"You cannot learn from what you cannot attribute."* — Migration 165 comment

---

### 2.2 Knowledge Fragment Memory
**Migration:** `100_ceio_phase2_feedback_loop.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
fhq_memory.knowledge_fragments
├── fragment_type → 'WINNING_PATTERN', 'LOSS_PATTERN', 'CAUSAL_INSIGHT'
├── validity_score → 0.0-1.0, updated by learning
├── reinforcement_count → Times pattern succeeded
├── decay_rate → How fast validity decays
├── reasoning_chain → Full reasoning that led to outcome
└── regime_context, entropy_at_signal → Market state snapshot
```

**Trigger:** `trg_shadow_trade_feedback` — Automatically creates knowledge fragments when trades close.

---

### 2.3 Feedback Loop Trigger
**Migration:** `100_ceio_phase2_feedback_loop.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
fn_shadow_trade_feedback() TRIGGER
├── STEP 1: Create Episodic Memory Entry
├── STEP 2: Create Knowledge Fragment
├── STEP 3: Update reward_trace with outcome
└── STEP 4: Log feedback event to governance
```

**Logic:** When shadow trade status → 'CLOSED':
- Calculates validity score based on outcome
- Winners: `validity = LEAST(0.95, 0.70 + return_pct * 2)`
- Losers: `validity = GREATEST(0.10, 0.30 + return_pct * 2)`

---

### 2.4 Calibration Governance Infrastructure
**Migration:** `174_finn_truth_engine_calibration_governance.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
fhq_governance.calibration_versions
├── parameter_name, version → Versioned parameters
├── proposed_at, frozen_at → Lifecycle tracking
├── vega_approval_ref → REQUIRED (G3-YYYY-NNN format)
├── is_active → Only one active per parameter
└── previous_version → Rollback chain
```

**Functions:**
| Function | Purpose |
|----------|---------|
| `propose_calibration()` | Submit new calibration (PENDING state) |
| `freeze_calibration()` | Lock with VEGA G3 approval |
| `activate_calibration()` | Promote to production |
| `rollback_calibration()` | Emergency revert |
| `get_active_calibration()` | Retrieve current value |

**Constitutional Rule:** `frozen_at IS NULL OR vega_approval_ref IS NOT NULL`
(Cannot freeze without VEGA approval)

---

### 2.5 Learning Proposals Governance
**Migration:** `151_aci_learning_proposals_governance.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
fhq_governance.learning_proposals
├── engine_id → 'IKEA', 'INFORAGE', 'SITC'
├── current_value, proposed_value → Change tracking
├── evidence_bundle, evidence_win_rate → Justification
├── status → 'PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'EXPIRED'
├── vega_attestation_id → Required for approval
└── expires_at → 7-day auto-expiry
```

**CEO Directive Compliance:**
> *"NO automated updates to IKEA classifier. All updates go to staging + G1/VEGA approval."*

---

### 2.6 FjordHQ Skill Score (FSS)
**Migration:** `029_ios005_forecast_calibration_schema.sql`, `045_ios005_recalibration_pathway.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
calculate_fss(risk_adj_return, stability, significance, consistency)
├── 40% Risk-Adjusted Return (Sharpe/Sortino normalized)
├── 30% Stability (1 - drawdown severity)
├── 20% Significance (1 - p_value)
└── 10% Consistency (hit rate)
```

**Skill Registry:** `fhq_research.forecast_skill_registry`
- Bootstrap resampling p-values
- Permutation test p-values
- 95% confidence intervals
- Certification: `is_certified = (p < 0.05 AND Sharpe > 1.0)`

---

### 2.7 Recalibration Pathway
**Migration:** `045_ios005_recalibration_pathway.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
fhq_research.recalibration_requests
├── target_edge_id → Edge to modify
├── current_strength, proposed_strength → Change
├── evidence_p_value → Must be < 0.05
├── status → PENDING → UNDER_REVIEW → APPROVED → EXECUTED
└── execution_signature_id → Cryptographic audit
```

**The ONLY Pathway:** IoS-007 edge weights are locked. This is the sole authorized modification route.

---

### 2.8 Memory Decay System
**Migration:** `096_pgvector_memory_foundation.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
calculate_effective_relevance(base_relevance, decay_factor, created_at)
├── Formula: effective = base × exp(-λ × age_days)
├── Floor: Never below 0.01
└── Bypass: is_eternal_truth = TRUE
```

**Memory Types with Decay:**
- `fhq_memory.embedding_store` — Vector embeddings
- `fhq_memory.semantic_memory` — Factual knowledge
- `fhq_memory.causal_memory` — Causal relationships

---

### 2.9 InForage Economic Stops
**Migration:** `100_ceio_phase2_feedback_loop.sql`
**Status:** ✅ FULLY IMPLEMENTED

```sql
fn_inforage_cost_check(session_id, step_type, predicted_gain)
├── Tracks cumulative cost per session
├── Decision: 'CONTINUE', 'ABORT_LOW_ROI', 'ABORT_BUDGET'
├── ROI threshold: 1.2× minimum
└── Gain decay: 15% per step
```

**Budget Config:** `fhq_optimization.inforage_budget_config`
- Session max: $0.50
- Daily max: $50.00
- API step cost: $0.05
- LLM step cost: $0.02

---

## 3. GAP Analysis ❌

### Gap 1: NO Automatic Meta-Learning
**Severity:** 🔴 HIGH (Architectural limitation)

**Current State:**
- All calibration changes require G1/VEGA approval
- Knowledge fragments capture outcomes but don't auto-adjust parameters
- Validity scores update but don't propagate to production

**Missing:**
```sql
-- DOES NOT EXIST:
fn_auto_recalibrate_from_outcomes()
├── Analyze recent canonical_outcomes
├── Compute optimal parameter adjustments
├── Apply changes without human approval ← FORBIDDEN BY CEO DIRECTIVE
```

**Root Cause:** CEO Directive 2025-12-17 explicitly prohibits automated IKEA updates.

---

### Gap 2: NO Confidence Calibration Tracking
**Severity:** 🟠 MEDIUM

**Current State:**
- `confidence_metrics_v` tracks confidence variance
- Signals have `confidence` fields
- No Brier score computation

**Missing:**
```sql
-- DOES NOT EXIST:
fhq_research.confidence_calibration_log
├── predicted_confidence → What FINN said
├── actual_outcome → What happened
├── brier_score → (predicted - actual)²
├── calibration_bucket → 0.1 intervals
└── calibration_curve → Reliability diagram data
```

**Impact:** Cannot answer "Is FINN overconfident at 80% confidence predictions?"

---

### Gap 3: NO Source Trust Scoring
**Severity:** 🟠 MEDIUM

**Current State:**
- Sources tracked in `fhq_data.price_series` (source column)
- InForage tracks cost per source tier
- No accuracy-based trust adjustment

**Missing:**
```sql
-- DOES NOT EXIST:
fhq_research.source_trust_registry
├── source_id → 'alpaca', 'fred', 'marketaux'
├── trust_score → 0.0-1.0, starts at 0.5
├── accuracy_history → Rolling accuracy over N predictions
├── last_updated → Auto-updates on outcome capture
└── trust_decay_rate → How fast trust regresses to prior
```

**Impact:** FINN treats all sources equally regardless of historical accuracy.

---

### Gap 4: NO Hypothesis Quality Scoring
**Severity:** 🟡 LOW-MEDIUM

**Current State:**
- `golden_needles` contain hypotheses
- `canonical_outcomes` link to needles
- No aggregated hypothesis quality metrics

**Missing:**
```sql
-- DOES NOT EXIST:
fhq_research.hypothesis_performance_log
├── hypothesis_category → 'MOMENTUM', 'REVERSAL', 'MACRO', etc.
├── win_rate → % of trades that were profitable
├── avg_return → Mean return per trade
├── sharpe_by_category → Risk-adjusted by type
└── regime_performance → Performance breakdown by regime
```

**Impact:** Cannot answer "Should FINN generate more MOMENTUM hypotheses in BULL regimes?"

---

### Gap 5: NO Adaptive Decay Rates
**Severity:** 🟡 LOW

**Current State:**
- Decay rates are static at creation (`decay_rate NUMERIC DEFAULT 0.01`)
- No mechanism to adjust based on pattern validity

**Missing:**
```sql
-- DOES NOT EXIST:
fn_adapt_decay_rate(fragment_id)
├── High validity + reinforcement → Slower decay
├── Low validity + failures → Faster decay
└── Update: decay_rate = base_decay × (1 - validity_score)
```

---

### Gap 6: NO Cross-Regime Learning Transfer
**Severity:** 🟡 LOW

**Current State:**
- Regime-gated memory prevents cross-contamination
- Patterns in BULL regime can't inform BEAR regime

**Missing:**
```sql
-- DOES NOT EXIST:
fhq_research.regime_similarity_matrix
├── regime_a, regime_b → e.g., 'BULL', 'NEUTRAL'
├── similarity_score → 0.0-1.0
├── transfer_weight → How much to weight cross-regime patterns
└── transferable_pattern_types → Which patterns transfer
```

---

### Gap 7: NO Epistemic Uncertainty Quantification
**Severity:** 🟡 LOW

**Current State:**
- No explicit "known unknowns" tracking
- No decomposition: aleatoric vs epistemic uncertainty

**Missing:**
```sql
-- DOES NOT EXIST:
fhq_research.epistemic_uncertainty_log
├── domain → 'crypto', 'equities', 'macro'
├── uncertainty_type → 'ALEATORIC' (market noise), 'EPISTEMIC' (model ignorance)
├── uncertainty_score → Quantified uncertainty
├── data_coverage → % of domain with sufficient data
└── model_disagreement → Ensemble disagreement metric
```

---

## 4. Implementation Completeness Matrix

| Component | Schema/Table | Migration | Status | Completeness |
|-----------|-------------|-----------|--------|--------------|
| Outcome Capture | `canonical_outcomes` | 165 | ✅ | 100% |
| Knowledge Fragments | `knowledge_fragments` | 100 | ✅ | 100% |
| Feedback Trigger | `trg_shadow_trade_feedback` | 100 | ✅ | 100% |
| Calibration Governance | `calibration_versions` | 174 | ✅ | 100% |
| Learning Proposals | `learning_proposals` | 151 | ✅ | 100% |
| FSS Skill Scoring | `forecast_skill_registry` | 029, 045 | ✅ | 100% |
| Recalibration Pathway | `recalibration_requests` | 045 | ✅ | 100% |
| Memory Decay | `calculate_effective_relevance` | 096 | ✅ | 100% |
| InForage Cost Tracking | `inforage_cost_log` | 100 | ✅ | 100% |
| **Auto Meta-Learning** | — | — | ❌ | 0% |
| **Confidence Calibration** | — | — | ❌ | 0% |
| **Source Trust Scoring** | — | — | ❌ | 0% |
| **Hypothesis Quality** | — | — | ❌ | 20% |
| **Adaptive Decay** | — | — | ❌ | 0% |
| **Cross-Regime Transfer** | — | — | ❌ | 0% |
| **Epistemic Uncertainty** | — | — | ❌ | 0% |

**Overall Completeness:** ~70%

---

## 5. Architectural Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
                    │              ADAPTIVE EPISTEMIC LEARNING LOOP            │
                    │                    Vision-IoS Implementation             │
                    └─────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   OBSERVE    │     │  HYPOTHESIZE │     │     ACT      │     │   EVALUATE   │
│              │     │              │     │              │     │              │
│ price_series │────▶│golden_needles│────▶│g5_paper_trade│────▶│  canonical   │
│ regime_state │     │  (FINN)      │     │  s (LINE)    │     │  _outcomes   │
│              │     │              │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                      │
                                                                      │ OUTCOME
                                                                      │ CAPTURE
                                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KNOWLEDGE PERSISTENCE                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │knowledge_       │  │episodic_memory  │  │embedding_store  │              │
│  │fragments        │  │                 │  │ (pgvector)      │              │
│  │✅ validity_score│  │✅ outcome_type  │  │✅ decay_factor  │              │
│  │✅ decay_rate    │  │✅ importance    │  │✅ relevance     │              │
│  │✅ reinforcement │  │✅ is_landmark   │  │✅ regime_tag    │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└───────────────────────────────────────────────────────────────┬─────────────┘
                                                                │
                                                                │ LEARNING
                                                                │ SIGNAL
                                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CALIBRATION GOVERNANCE                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                     learning_proposals                           │        │
│  │  PENDING ──▶ UNDER_REVIEW ──▶ APPROVED ──▶ learning_versions    │        │
│  │                   │                              │               │        │
│  │                   ▼                              ▼               │        │
│  │           VEGA G3 APPROVAL              calibration_versions    │        │
│  │              REQUIRED                    (ACTIVE = TRUE)        │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ⚠️  CEO DIRECTIVE: NO AUTOMATED UPDATES — ALL REQUIRE HUMAN APPROVAL       │
└─────────────────────────────────────────────────────────────────────────────┘
                                                                │
                                                                │ BLOCKED
                                                                │ (GOVERNANCE)
                                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          META-LEARNING (GAPS)                                │
│                                                                              │
│  ❌ Auto-Calibration          ❌ Confidence Brier Scores                     │
│  ❌ Source Trust Adjustment   ❌ Hypothesis Quality Scoring                  │
│  ❌ Adaptive Decay Rates      ❌ Cross-Regime Transfer                       │
│  ❌ Epistemic Uncertainty     ❌ Model Disagreement Tracking                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Recommendations

### 6.1 Quick Wins (No Governance Change Required)

| Priority | Recommendation | Migration Est. |
|----------|---------------|----------------|
| 1 | Add Brier score computation to `canonical_outcomes` | 1 migration |
| 2 | Create `hypothesis_performance_log` materialized view | 1 migration |
| 3 | Add `source_accuracy_7d` to price_series metadata | 1 migration |

### 6.2 Medium-Term (Requires CEO Directive Amendment)

| Priority | Recommendation | Governance Required |
|----------|---------------|---------------------|
| 4 | Allow auto-decay rate adjustment (non-parameter) | G2 Review |
| 5 | Implement confidence calibration curves | G2 Review |
| 6 | Create source trust registry with manual updates | G3 Approval |

### 6.3 Long-Term (Architectural Decision)

| Priority | Recommendation | Risk |
|----------|---------------|------|
| 7 | Allow bounded auto-calibration with VEGA oversight | HIGH — Requires CEO approval |
| 8 | Cross-regime transfer learning framework | MEDIUM — New ADR required |
| 9 | Epistemic uncertainty decomposition | LOW — Research phase |

---

## 7. Conclusion

Vision-IoS has a **robust foundation** for an Adaptive Epistemic Learning Loop:
- ✅ Ground truth capture is complete and traceable
- ✅ Knowledge persistence with decay is implemented
- ✅ Governance-controlled calibration prevents rogue updates
- ✅ Feedback trigger closes the loop on every trade

However, the **meta-learning layer is intentionally constrained**:
- ❌ All parameter updates require human/VEGA approval
- ❌ No automatic confidence recalibration
- ❌ No source trust scoring

This is a **design choice, not a bug**. The CEO Directive prioritizes legal defensibility and auditability over autonomous adaptation.

**If full Adaptive Epistemic Learning is desired, a CEO Directive amendment is required to authorize bounded auto-calibration within VEGA oversight constraints.**

---

*Report generated by STIG | Classification: Internal Technical Assessment*
