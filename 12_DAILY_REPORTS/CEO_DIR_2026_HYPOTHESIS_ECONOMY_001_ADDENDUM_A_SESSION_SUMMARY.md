# CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Addendum A - Session Summary

**Date:** 2026-01-23/24
**Session:** Late Evening (23:45 - 00:15 CET)
**Author:** STIG (EC-003)

---

## ADDENDUM A: EPISTEMIC HARDENING

**Executive Intent:** Convert FjordHQ from "Hard and correct" to "Hard, self-aware, and self-correcting"

---

## FAILURE MODES ADDRESSED

1. **Over-hard Tier-1 falsification** (Type I error dominance)
2. **Narrative seduction** via unconstrained context vectors
3. **Antithesis leakage** destabilizing learning economics
4. **Reward hacking** ("Cobra Effect") in EC-022
5. **Context isolation** from Prediction Ledger (IoS-010)

---

## DIRECTIVE 1: TIER-1 SYMMETRY WATCH

### Shadow Tier Mechanism

| Parameter | Value |
|-----------|-------|
| Sample Rate | 5% of Tier-1 FALSIFIED |
| Executor | LARS (read-only) |
| Environment | NON_CANONICAL (isolated) |
| Purpose | Detect systematic over-hardening |

### New Metrics in v_tier1_calibration_status

| Metric | Description |
|--------|-------------|
| `false_negative_indicator` | TRUE if shadow survival > 30% |
| `shadow_survival_rate` | % of discarded hypotheses that survive in shadow |
| `hardening_bias_flag` | WARNING/ALERT if over-hardening detected |

### Fail-Closed Rule
- Shadow Tier must NEVER re-promote hypotheses
- Any cross-contamination → halt Phase III

---

## DIRECTIVE 2: CONTEXT VECTOR DOMINANCE HIERARCHY

### Hard Ordering (No Weighted Averaging)

```
1. Temporal Alignment (VETO)
   → If context timestamp > outcome timestamp: Confidence = 0
   → No further evaluation allowed

2. Statistical Lift
   → Only evaluated if temporal passes

3. Cross-Event Recurrence
   → Only evaluated if temporal + lift pass
```

### New Columns
- `temporal_veto`: TRUE if context came AFTER outcome
- `effective_confidence`: Respects dominance hierarchy

### Audit View
`v_context_rejection_audit` answers:
> "Why was this context ignored despite high narrative plausibility?"

---

## DIRECTIVE 3: CSEO ANTITHESIS BOUNDARY (ADR-014)

### Boundary Rule

```sql
antithesis_experiments.target_hypothesis_id
→ hypothesis.status IN ('WEAKENED', 'CANDIDATE')
```

### Explicit Prohibitions

| CSEO Cannot | Reason |
|-------------|--------|
| Attack INCUBATION hypotheses | Too early to stress-test |
| Attack Tier-1 FALSIFIED | Already dead, waste of resources |
| Spawn new hypotheses from antithesis | Antithesis is destructive only |

### Fail-Closed
- Boundary violation → raises exception
- Revokes CSEO antithesis execution until reviewed

---

## DIRECTIVE 4: EC-022 COBRA EFFECT PREVENTION

### Problem
System could optimize by generating weak ideas to kill quickly for reward.

### Solution: Complexity-Adjusted Incentives

**Complexity Formula:**
```
complexity = (causal_depth × 0.4) + (dof × 0.3) + (regime_count × 0.3)
```

**Reward Scaling:**
| Complexity | Reward Multiplier |
|------------|-------------------|
| < 1.5 (trivial) | 10% (90% reduction) |
| 1.5 - 2.5 (simple) | 50% |
| > 2.5 (complex) | scales with complexity |

### G1 Gate Extension
Now requires 4 tests (was 3):
1. Incentive Alignment Test
2. Asymmetry Test
3. Delayed Reward Test
4. **Cobra Effect Test** (NEW)

### Fail-Closed
If trivial-kill strategy yields positive reward → EC-022 remains disabled

---

## DIRECTIVE 5: IoS-010 STRUCTURAL INTEGRATION

### Schema Link

```sql
context_annotations.evaluation_id
→ fhq_research.evaluations.evaluation_id
```

### Enables
- Direct attribution of context impact on Brier Score deltas
- SQL query: "Which context reduced Brier Score most for this model?"

### Fail-Closed
- Evaluation-type context without evaluation_id → reject insert

---

## IMPLEMENTATION STATUS

| Directive | Component | Status |
|-----------|-----------|--------|
| 1 | Shadow Tier Registry | DEPLOYED |
| 1 | sample_for_shadow_tier() | DEPLOYED |
| 1 | v_tier1_calibration_status (extended) | DEPLOYED |
| 2 | temporal_veto column | DEPLOYED |
| 2 | effective_confidence column | DEPLOYED |
| 2 | trg_context_dominance | DEPLOYED |
| 2 | v_context_rejection_audit | DEPLOYED |
| 3 | trg_antithesis_boundary | DEPLOYED |
| 3 | v_antithesis_boundary_audit | DEPLOYED |
| 4 | complexity_score column | DEPLOYED |
| 4 | calculate_complexity_adjusted_reward() | DEPLOYED |
| 4 | validate_ec022_g1_gate_v2() | DEPLOYED |
| 5 | evaluation_id column | DEPLOYED |
| 5 | trg_context_evaluation_link | DEPLOYED |
| 5 | v_context_brier_impact | DEPLOYED |

---

## READINESS CHECKLIST (v_addendum_a_readiness)

| Item | Status | Requirement |
|------|--------|-------------|
| Tier-1 Death Rate | 50% | Target ≥70% (n=2, need n≥30) |
| Symmetry Watch | OPERATIONAL | 0 samples (awaiting falsifications) |
| Context Dominance | ENFORCED | Temporal veto active |
| CSEO Boundary | ENFORCED | Trigger active |
| EC-022 G1 | PENDING | Cobra test required |
| IoS-010 Bridge | READY | evaluation_id column active |

---

## PHASE STATUS (UNCHANGED)

| Phase | Status |
|-------|--------|
| Phase III | ACTIVE (calibrating) |
| Phase IV | ACTIVE (read-only) |
| Phase V | **FROZEN** |

---

## CEO ASSESSMENT QUOTE

> "At this point, the dominant risk is no longer overfitting, narrative bias, or reward hacking. But human impatience."

---

## FILES CREATED

### Migration
- `04_DATABASE/MIGRATIONS/338_addendum_a_epistemic_hardening.sql`

### Evidence
- `CEO_DIR_2026_HYPOTHESIS_ECONOMY_001_ADDENDUM_A_DEPLOYED.json`

---

**Signed:** STIG (EC-003)
**Timestamp:** 2026-01-24T00:15:00.000Z
