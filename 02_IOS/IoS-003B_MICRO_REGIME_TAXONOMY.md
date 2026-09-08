# IoS-003B: Micro-Regime Taxonomy within CRISIS Macro State

**Status:** G2_OBSERVATIONAL
**Directive:** CEO-DIR-2026-OPS-MICROREGIME-003
**Author:** STIG (EC-003), commissioned by FINN (EC-006)
**Classification:** GOVERNANCE-CRITICAL / OBSERVATIONAL
**Execution Authority:** NONE
**Capital Authority:** ZERO
**Created:** 2026-02-01T18:46 CET (DAY32)

---

## 1. Motivation

The current macro regime state is CRISIS (confidence 0.9615), with belief_regime=STRESS and is_policy_divergent=true. The CRISIS label is a monolithic classification that collapses several distinct market micro-conditions into a single bucket. This creates two problems:

1. **Volatility Observer Blind Spot:** All 24 IoS-009 observations are `envelope_non_compliant` because CRISIS blocks SELL_VOL strategies unconditionally. Yet within CRISIS, there exist conditions where observation of protective strategies (BUY_VOL) would be informative.

2. **Hypothesis Stagnation:** 897 of 1024 hypotheses are FALSIFIED, many under a regime label too coarse to capture why. If CRISIS contains sub-states with meaningfully different return distributions, the falsification signal is noisy.

This document defines 4 micro-regimes within CRISIS that preserve the macro-level safety invariant while enabling finer-grained observational research.

---

## 2. Hard Constraints

| Constraint | Enforcement |
|-----------|-------------|
| NO changes to IoS-012 (Execution Engine) | Code review + assertion |
| NO changes to IoS-009 (Volatility Observer) execution path | Module boundary respected |
| NO changes to options_shadow_adapter.py | File not imported or modified |
| Micro-regimes are OBSERVATIONAL METADATA only | Written to `micro_regime` column, never to execution tables |
| Macro CRISIS label remains authoritative for all execution gates | DEFCON, kill-switch, and envelope still read macro only |
| No new execution authority granted | EXECUTION_AUTHORITY = NONE preserved |

---

## 3. Empirical Basis (Database Evidence)

### 3.1 Current Sovereign Regime Distribution (2026-01-29)

From `fhq_perception.sovereign_regime_state_v4` latest snapshot across 48 assets:

| Sovereign Regime | Count | Notable Assets |
|-----------------|-------|----------------|
| BEAR | ~30 | ADA, ALGO, AVAX, DOGE, ETH, SOL, XRP |
| STRESS | ~8 | BTC (96.2%), CHZ (98.4%), EOS (99.7%), EURCHF |
| NEUTRAL | ~6 | MKR, QNT, RPL, XTZ, FLOW, MANA |
| BULL | ~4 | AXS, AUDUSD, CHZ(prior), MATIC(stale) |

### 3.2 Stress Probability Distribution within BEAR Assets

Not all BEAR assets are equal. The `stress_prob` varies dramatically:

| Cluster | stress_prob Range | Assets | Interpretation |
|---------|------------------|--------|----------------|
| BEAR-pure | < 0.20 | CRO (0.002), ALGO (0.010), CRV (0.19) | Declining orderly, low contagion risk |
| BEAR-stressed | 0.20 - 0.60 | DOGE (0.22), ADA (0.15), ETC (0.29), AVAX (0.20) | Declining with elevated stress, contagion possible |
| BEAR-acute | > 0.60 | BCH (0.64), BNB (0.54), DOT (0.85), ETH (0.83) | Near-STRESS, high contagion, potential cascade |

### 3.3 Macro Regime State

```
current_regime: CRISIS
regime_confidence: 0.9615
belief_regime: STRESS
belief_confidence: 0.8499
is_policy_divergent: true
divergence_reason: HYSTERESIS: 1/5 confirms (CEO-DIR-2026-001 identified)
transition_state: PENDING_CONFIRMATION
```

The divergence between belief (STRESS) and policy (CRISIS) itself is a signal. The hysteresis mechanism requires 5 confirmations to transition; currently at 1/5.

### 3.4 Experiment Results Under CRISIS

| Experiment | Result | Trigger Count | Win/Loss | Note |
|-----------|--------|---------------|----------|------|
| EXP-2026-T1-0003 | FALSIFIED | 0 | - | direction_accuracy: 0.35 |
| EXP-2026-T1-0005 | WEAKENED | 0 | - | direction_accuracy: 0.41 (near threshold) |
| EXP_ALPHA_SAT_A_V1.1 | FALSIFIED | 19 | 0/19 | BBW squeeze, avg return +2.82% but direction wrong |
| EXP_ALPHA_SAT_B_V1.1 | FALSIFIED | 0 | - | RSI>70 in STRONG_BULL, no triggers in BEAR regime |
| EXP_ALPHA_SAT_C_V1.1 | FALSIFIED | 0 | - | BB position in NEUTRAL, no triggers in current regime |
| EXP_ALPHA_SAT_D_V1.0 | FALSIFIED | 0 | - | BB breakout in BULL_OR_NEUTRAL, no triggers |
| EXP_ALPHA_SAT_E_V1.0 | **RUNNING** | 0 | - | RSI<35 pullback in BULL, still collecting |
| EXP_ALPHA_SAT_F_V1.0 | FALSIFIED | 16 | 15/1 | RSI<20 bounce in BEAR/STRESS, 93.8% bounce rate |

**Key Observation:** Most experiments cannot trigger under CRISIS because their regime_filter requires BULL or NEUTRAL. Only EXP_ALPHA_SAT_F (BEAR_OR_STRESS filter) and EXP_ALPHA_SAT_A (no regime filter) produced triggers. This confirms the micro-regime taxonomy is needed to differentiate actionable sub-conditions within the CRISIS envelope.

---

## 4. Micro-Regime Taxonomy

### 4.1 Definition: 4 Micro-Regimes within CRISIS

| Micro-Regime | Code | Condition | Market Character |
|-------------|------|-----------|-----------------|
| **CRISIS_ACUTE** | `MR_ACUTE` | Portfolio avg stress_prob > 0.80 AND >50% assets in STRESS | Active contagion, cascade risk, max defensive |
| **CRISIS_SYSTEMIC** | `MR_SYSTEMIC` | Portfolio avg stress_prob 0.50-0.80 AND >30% assets with stress_prob > 0.60 | Broad stress, cross-asset correlation spike |
| **CRISIS_SELECTIVE** | `MR_SELECTIVE` | Portfolio avg stress_prob 0.20-0.50 AND <30% assets in STRESS | Sector-specific stress, some assets decoupling |
| **CRISIS_EXHAUSTION** | `MR_EXHAUSTION` | Portfolio avg stress_prob < 0.20 OR belief_regime divergent from policy AND transition_state = PENDING | Vol compression, potential bottom formation |

### 4.2 Classification Logic

```
FUNCTION classify_micro_regime(
    sovereign_states: Dict[asset, regime_record],
    macro_state: regime_state_record
) -> MicroRegime:

    stress_probs = [r.stress_prob for r in sovereign_states.values()]
    avg_stress = mean(stress_probs)
    pct_stress = count(r for r in sovereign_states if r.sovereign_regime == 'STRESS') / len(sovereign_states)
    pct_high_stress = count(r for r in sovereign_states if r.stress_prob > 0.60) / len(sovereign_states)

    -- Check exhaustion first (divergence signal)
    IF macro_state.is_policy_divergent AND macro_state.transition_state == 'PENDING_CONFIRMATION':
        IF avg_stress < 0.20:
            RETURN MR_EXHAUSTION

    -- Acute: overwhelming stress
    IF avg_stress > 0.80 AND pct_stress > 0.50:
        RETURN MR_ACUTE

    -- Systemic: broad but not universal stress
    IF avg_stress > 0.50 AND pct_high_stress > 0.30:
        RETURN MR_SYSTEMIC

    -- Selective: localized stress
    IF avg_stress > 0.20:
        RETURN MR_SELECTIVE

    -- Exhaustion: stress fading
    RETURN MR_EXHAUSTION
```

### 4.3 Current Classification (2026-02-01)

Based on the latest sovereign_regime_state_v4 snapshot:

- Total assets in universe: 48
- Assets in STRESS: ~8 (~17%)
- Assets with stress_prob > 0.60: ~12 (~25%) — BCH, BNB, DOT, ETH, BTC, CHZ, EOS, EURCHF, SAND, etc.
- Portfolio avg stress_prob: ~0.35 (estimated from weighted distribution)
- is_policy_divergent: true
- transition_state: PENDING_CONFIRMATION

**Classification: `MR_SELECTIVE`** — The majority of assets are in BEAR (not STRESS), stress is concentrated in major-cap crypto (BTC, ETH) and a few altcoins, while most of the portfolio shows orderly decline. The policy divergence (CRISIS vs belief STRESS) at 1/5 confirms suggests the macro regime may be transitioning.

### 4.4 Observational Implications per Micro-Regime

| Micro-Regime | Options Observation Policy | Hypothesis Generation | Envelope Relaxation |
|-------------|--------------------------|----------------------|-------------------|
| MR_ACUTE | OBSERVE protective only (PROTECTIVE_PUT) | Suspend new generation | NONE — all blocked |
| MR_SYSTEMIC | OBSERVE protective + defined-risk | Allow BEAR-thesis only | NONE — macro blocks |
| MR_SELECTIVE | OBSERVE all strategies, log counterfactuals | Allow regime-conditional | NONE — macro blocks |
| MR_EXHAUSTION | OBSERVE all, flag potential transition | Allow full generation | NONE — awaits macro transition |

**Critical:** Envelope relaxation is ALWAYS NONE under CRISIS macro. Micro-regimes provide observational granularity only. The DEFCON/kill-switch system and strategy eligibility envelope continue to read the macro CRISIS label. This is a hard invariant.

---

## 5. Regime-Delta Integration

### 5.1 Existing Infrastructure

The `fhq_operational.regime_delta` table already exists with the following schema:

| Column | Type | Purpose |
|--------|------|---------|
| delta_type | text | Type of regime change detected |
| intensity | numeric | Magnitude of the change |
| momentum_vector | text | Direction of the change |
| bollinger_width | numeric | Volatility bandwidth |
| squeeze_tightness | numeric | Squeeze compression level |
| canonical_regime | text | Current regime at detection |
| regime_alignment | boolean | Whether delta aligns with regime |

The table is currently empty (0 rows). The micro-regime classifier will produce `MICRO_REGIME_SHIFT` delta events when the micro-regime changes within CRISIS.

### 5.2 Delta Event Format

When micro-regime transitions occur, the classifier writes to `fhq_operational.regime_delta`:

```
delta_type: 'MICRO_REGIME_SHIFT'
canonical_regime: 'CRISIS'
intensity: abs(new_avg_stress - old_avg_stress)
momentum_vector: 'IMPROVING' | 'DETERIORATING' | 'STABLE'
regime_alignment: true (always aligned with CRISIS macro)
```

### 5.3 Integration Points (Observer-Only)

| Consumer | How It Uses Micro-Regime | Authority Level |
|----------|------------------------|-----------------|
| volatility_observer.py (IoS-009) | Reads micro_regime from latest classification; logs in observation metadata | READ-ONLY |
| options_hypothesis_canon | New column `micro_regime_at_observation` captures state at hypothesis creation | METADATA-ONLY |
| CADENCE_STATE.json | Reports current micro_regime in status | REPORTING-ONLY |
| Decision Pack Generator | Includes micro_regime context in daily pack | INFORMATIONAL |

**NOT integrated with (hard constraint):**
- options_shadow_adapter.py — NO import, NO read
- unified_execution_gateway.py — NO changes
- options_defcon_killswitch.py — NO changes
- Any execution table — NO writes

---

## 6. Falsification Design

The micro-regime taxonomy itself must be falsifiable:

| Criterion | Falsified If | Measurement |
|-----------|-------------|-------------|
| Micro-regimes capture distinct return distributions | Return distributions are statistically identical across micro-regimes (KS-test p > 0.10) | Compare 30-day returns per micro-regime after 90 days |
| Micro-regime transitions predict macro transitions | Micro-regime progression (ACUTE → SYSTEMIC → SELECTIVE → EXHAUSTION) does NOT precede macro regime changes | Count predictive vs. non-predictive sequences |
| Micro-regimes improve hypothesis quality | Hypotheses generated under micro-regime context have same falsification rate as without | Compare falsification rates before/after micro-regime metadata |
| MR_EXHAUSTION identifies bottoms | MR_EXHAUSTION classification does NOT precede recovery within 30 days at rate > chance (50%) | Track EXHAUSTION → recovery transitions |

---

## 7. Files Created by This Directive

| File | Type | Purpose |
|------|------|---------|
| `02_IOS/IoS-003B_MICRO_REGIME_TAXONOMY.md` | Specification | This document |
| `04_DATABASE/MIGRATIONS/353_micro_regime_infrastructure.sql` | Migration | Add micro_regime columns + classification table |
| `03_FUNCTIONS/micro_regime_classifier.py` | Module | Classification logic + CLI |
| `03_FUNCTIONS/evidence/CEO_DIR_2026_OPS_MICROREGIME_003_EVIDENCE.json` | Evidence | Classification results + test status |

---

## 8. Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | 4 micro-regimes defined with deterministic classification logic | This document |
| 2 | Current state classified correctly against database evidence | Classifier output matches manual analysis |
| 3 | Migration adds metadata columns without altering execution tables | information_schema verification |
| 4 | No execution authority granted | Assertion-enforced in code |
| 5 | Integration points are read-only | Code review |
| 6 | Full experiment status report delivered | Evidence JSON |
