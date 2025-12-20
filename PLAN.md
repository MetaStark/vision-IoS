# CEIO Calibration & Alpha Graph Integration Plan

**Directive:** VISION-IOS CSO Memorandum 2025-12-08
**Executor:** STIG (CTO)
**Classification:** STRATEGIC IMPLEMENTATION
**Reference:** ADR-001–ADR-020 | IoS-007 Alpha Graph | NeurIPS 2025 / ICLR 2026 Protocols

---

## Executive Summary

Implement the CEIO (Causal-Entropy Information Optimization) architecture as the reward function for the FHQ autonomous research agent. This synthesizes:
- **IKEA Protocol** (Knowledge Boundary Awareness) - Huang et al., ICLR 2026
- **InForage Logic** (Information Scent Optimization) - Qian & Liu, NeurIPS 2025
- **Structural Causal Entropy ($H_{sc}$)** (Graph Stability Regulator) - FHQ Definition

**Master Equation:**
```
R_CEIO = β^max(0,T-2) · (r_signal + α·C_FHQ + γ·r_kb)
```

**Mission:** Maksimere brukerens FRIHET = Alpha Signal Presisjon / Tidsbruk → Maksimalt

---

## Implementation Steps

### Step 1: Database Schema Creation
Create `fhq_optimization` schema with CEIO tracking infrastructure.

**Migration:** `094_ceio_optimization_schema.sql`

**Tables:**
- `reward_traces` - Track all CEIO reward calculations with full audit trail
- `entropy_snapshots` - Store $H_{sc}$ calculations per reasoning session
- `ceio_hyperparameters` - Version-controlled hyperparameter registry for A/B testing

### Step 2: Structural Causal Entropy Engine
Create Python module for $H_{sc}$ calculation per Stig's redefinition.

**File:** `03_FUNCTIONS/ceio_entropy_engine.py`

**Functions:**
- `calculate_structural_causal_entropy(active_edges)` - Core entropy: $H_{sc}(G) = -\sum_{e \in E} P(e) \log P(e) \cdot w_{causal}(e)$
- `calculate_graph_coverage(focus_nodes, freshness_threshold)` - $C_{FHQ}$ metric with 2-hop expansion
- `calculate_knowledge_boundary_reward(api_calls, signal_score)` - IKEA $r_{kb}$ implementation
- `calculate_ceio_reward(...)` - Master equation aggregation

### Step 3: Alpha Graph Integration (IoS-007)
Connect CEIO engine to existing Alpha Graph infrastructure.

**Integration Points:**
- Read edge weights from `vision_signals.alpha_graph_edges`
- Calculate $H_{sc}$ for query-relevant subgraphs
- Dynamic `N_focus` expansion using 2-hop neighbor rule (fixes coverage denominator issue)
- Regime detection via entropy thresholds

### Step 4: Governance Registration
Register CEIO under ADR-020 (ACI Protocol) as implementation specification.

**Records:**
- IoS registry entry for CEIO engine
- G4 artifact hashes
- Hash chain integration

### Step 5: Validation & Calibration Harness
Deploy to sandbox with calibration test suite.

---

## Hyperparameter Calibration Table

| Parameter | Value | Paper Value | Source | Rationale |
|-----------|-------|-------------|--------|-----------|
| α (alpha) | 0.30 | 0.20 | FHQ | Higher penalty for missing macro-correlations |
| β (beta) | 0.90 | 0.95 | FHQ | Aggressive decay - markets move fast |
| γ (gamma) | 1.00 | N/A | FHQ | Full weight to internal knowledge reward |
| r_kb+ | 0.50 | 0.60 | IKEA | Baseline reward for parametric knowledge |
| API_max | 5 | 3 | FHQ | Hard limit per reasoning chain |
| T_max | 4 | N/A | FHQ | Maximum reasoning steps before timeout |
| T_min | 2 | 2 | InForage | Minimum steps (search + answer) |
| H_sc_threshold | 0.80 | N/A | FHQ | Entropy ceiling for regime cutoff |

---

## Mathematical Definitions

### 1. Structural Causal Entropy ($H_{sc}$)
```
H_sc(G) = -Σ P(e) · log₂(P(e)) · w_causal(e)
```
Where:
- P(e) = normalized edge probability in subgraph
- w_causal(e) = ontology weight (LEADS=1.0, CORRELATES=0.5)

**Interpretation:**
- High $H_{sc}$ → Chaos/Noise (uniform causality)
- Low $H_{sc}$ → Clear Signal (peaked distribution)

### 2. Graph Coverage ($C_{FHQ}$)
```
C_FHQ = |{n ∈ N_focus : freshness(n) < 24h}| / |N_focus|
```
**Critical Fix:** Denominator is `N_focus` (2-hop subgraph), NOT entire graph.

### 3. Knowledge Boundary Reward ($r_{kb}$)
```
r_kb = 0.5 · (1 - API_calls/5) · 𝟙[r_signal > 0]
```
**Safety:** Only rewards efficiency if outcome is POSITIVE.

### 4. Master Equation ($R_{CEIO}$)
```
R_CEIO = β^max(0,T-2) · (r_signal + α·C_FHQ + γ·r_kb)
```

---

## Risk Mitigations

### 1. Frozen Agent Risk (High Entropy Regime)
**Problem:** Agent loops endlessly searching for causality in chaos.
**Solution:** If $H_{sc} > 0.80$, hard-switch to CASH/NEUTRAL. No Alpha in Chaos.

### 2. Lazy Analyst Risk (Reward Hacking)
**Problem:** Agent guesses "Neutral" to minimize API calls and claim r_kb.
**Solution:** `r_kb` only awarded if `r_signal > 0`. Never reward efficiency at losing.

### 3. Coverage Gaming
**Problem:** Agent might refresh irrelevant nodes to inflate C_FHQ.
**Solution:** C_FHQ denominator is N_focus (query-relevant subgraph), not full graph.

---

## Files to Create

| File | Purpose |
|------|---------|
| `04_DATABASE/MIGRATIONS/094_ceio_optimization_schema.sql` | Database infrastructure |
| `03_FUNCTIONS/ceio_entropy_engine.py` | Core calculation engine |
| `03_FUNCTIONS/ceio_alpha_graph_integration.py` | IoS-007 integration layer |
| `05_GOVERNANCE/PHASE3/CEIO_G0_SUBMISSION_20251208.json` | Governance evidence |

---

## Execution Order

1. Create database migration (094_ceio_optimization_schema.sql)
2. Execute migration via psql
3. Create Python CEIO engine (ceio_entropy_engine.py)
4. Create Alpha Graph integration layer
5. Register in governance tables
6. Generate G0 evidence bundle
7. Run unit tests on calculation functions
8. Deploy to sandbox for calibration

---

## Success Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `fhq_optimization.reward_traces` exists | Schema query |
| 2 | `fhq_optimization.entropy_snapshots` exists | Schema query |
| 3 | `fhq_optimization.ceio_hyperparameters` exists | Schema query |
| 4 | Python engine calculates H_sc correctly | Unit test |
| 5 | C_FHQ uses N_focus denominator | Unit test |
| 6 | r_kb respects signal positivity | Unit test |
| 7 | Master equation aggregates correctly | Integration test |
| 8 | Governance records created | DB query |

---

## Action Items (Per Directive)

| Agent | Action | Status |
|-------|--------|--------|
| LARS | Approve $H_{sc}$ redefinition | PENDING |
| STIG | Deploy Python calculation engine | IN_PROGRESS |
| VEGA | Run USD/NOK backtest for α calibration | PENDING |

---

**Plan Status:** READY FOR EXECUTION
**Approver:** CEO (LARS)
