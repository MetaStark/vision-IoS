# IoS-003C: Crypto Regime Engine

**Status:** P1_ACTIVATED
**Assigned To:** FINN (Financial Investments Neural Network)
**API Requirement:** DeepSeek Reasoning API
**Activated:** 2026-01-18
**Directive:** CEO-DIR-2026-076, **CEO-DIR-2026-089** (Discipline Upgrade)

---

## 1. Executive Summary

The Crypto Regime Engine (IoS-003C) is a dedicated research module to develop regime classification for cryptocurrency assets. This is explicitly **separate** from the equity regime engine (IoS-003) due to fundamental structural differences between asset classes.

**Core Doctrine:** Alpha speaks first. Measurement verifies. Instruments listen. Capital waits.

**Scope:** Crypto regime research only. No execution. No paper. No live. No cross-domain coupling.

---

## 2. HARD CONSTRAINTS (ABSOLUTE) — CEO-DIR-2026-089

### 2.1 Domain Separation (ENFORCED)

- Crypto regimes **MUST NOT** alter, recalibrate, or influence any EQUITY signal, inversion logic, confidence ceiling, OKR, or ledger.
- Any attempt to reuse equity regime definitions, thresholds, or labeling logic is **PROHIBITED** unless explicitly authorized in a later CEO directive.

### 2.2 No Execution Pressure

- Research outputs are descriptive and evaluative only.
- No PnL targets, no trade simulation objectives, no options logic embedded in IoS-003C research layer.

### 2.3 Definition Freeze

- Target definition, horizon definition, dataset inclusion rules, and regime ontology must be **FROZEN at Gate 1**.
- Any change after freeze requires VEGA logged exception + CEO approval.

---

## 3. Why Equity Regimes Fail for Crypto

| Equity Regime Driver | Crypto Reality |
|---------------------|----------------|
| M2 Money Supply | Stablecoin Velocity is the driver |
| Real Rates (10Y TIPS) | DeFi yields and funding rates dominate |
| VIX as stress proxy | Perp funding rates + liquidation cascades |
| Sector rotation | Protocol/narrative rotation |
| Market hours | 24/7 continuous trading |
| Regulatory clarity | Regulatory uncertainty is structural |

**Empirical Evidence:**
- STRESS@99%+ on crypto has **inconsistent** inversion characteristics
- Vol-squeezes are misinterpreted as STRESS by equity HMMs
- Funding rate dynamics have no equity analog

---

## 4. DISCIPLINE REQUIREMENTS (MANDATORY) — CEO-DIR-2026-089

### 4.1 HYSTERESIS (IoS-003 Section 3.1 Discipline)

**Purpose:** Prevent flip-flopping in volatile markets and make regimes operationally meaningful.

**Owner:** FINN
**Gate:** G1 (2026-01-25)

**Requirements:**
- Define deterministic transition thresholds using hysteresis buffers
- Buffers must be volatility-adjusted (explicit rule required)

**Deliverables:**
- [ ] Entry threshold per regime transition
- [ ] Exit threshold per regime transition
- [ ] Minimum dwell time rule (if used)
- [ ] Proof that hysteresis reduces regime churn without hiding true transitions

**STIG Verification:** Hysteresis parameters and transitions must be logged and reproducible.

---

### 4.2 CRIO ACTIVATION FOR LANE C (ADR-014)

**Purpose:** Causal mechanism clarity for microstructure stress.

**Owner:** CRIO
**Gate:** G3 (2026-02-15)

**Delegation:** Lane C (funding, OI, liquidations, basis, microstructure stress) is delegated to CRIO for causal mapping.

**CRIO Deliverables:**
- [ ] Causal mechanism map (what transmits to what, under which conditions)
- [ ] Mechanism hypotheses that are falsifiable
- [ ] Shortlist of "must-have" microstructure variables with rationale and expected directionality
- [ ] Funding Rate Arbitrage mapping (CEO recommendation)
- [ ] Short Squeeze Dynamics mapping (CEO recommendation)

**Scope:** GraphRAG/causal reasoning only — NOT model building.

---

### 4.3 STATISTICAL DISCIPLINE (IoS-005)

**Purpose:** Prove predictive skill is not luck.

**Owner:** FINN
**Gate:** G3 (2026-02-15)

**Requirements:**
- Gate 3 results must pass bootstrap significance
- Null hypothesis: performance equals random baseline for the chosen target
- Minimum: **p < 0.05** for primary KPI (Brier improvement or directional skill)

**Deliverables:**
- [ ] Bootstrap method described
- [ ] Number of resamples
- [ ] Confidence intervals for key metrics
- [ ] Sensitivity across subperiods (minimum: high-vol vs low-vol windows)

**Failure Mode:** If p >= 0.05, IoS-003C does NOT advance to Gate 4.

---

### 4.4 CONTEXTUAL INTEGRITY AND CANONICAL IDS (IoS-001)

**Purpose:** Prevent identity drift across spot/derivatives and across providers.

**Owner:** STIG
**Gate:** G2 (2026-02-01)

**Requirements:**
STIG must verify — against database truth — that Lane A and Lane C inputs can be anchored to:
- `canonical_id` (asset identity)
- `exchange_mic` (venue identity, where applicable)
- `instrument_type` (spot, perp, option — classification only)

**AIRLOCK Protocol:**
If a provider cannot support canonical ID tagging, it must be placed behind an explicit "AIRLOCK" label with clear lineage, and excluded from any canonical conclusions until resolved.

---

### 4.5 EPOCH-BASED EVALUATION (Crypto 24/7 Primitive)

**Purpose:** Create a stable evaluation boundary equivalent to "trading day" for auditability.

**Owner:** STIG
**Gate:** G2 (2026-02-01)

**Canonical Evaluation Delimiter:**
- **00:00 UTC Snapshot** as the boundary for horizon evaluation and outcome capture

**Requirements:**
- Horizons must be defined relative to this epoch boundary
- NOT "calendar day add"
- NOT local exchange time

**Benefits:**
- Comparability across venues and timezones
- Prevents silent denominator shifts

**STIG Verification:** Outcome capture uses epoch convention consistently and is logged as part of the evidence bundle.

---

## 5. Research Lanes

### Lane A: Macro Liquidity
| Dimension | Data Source | Hypothesis |
|-----------|-------------|------------|
| **Net Stablecoin Liquidity** | On-chain (Glassnode, Dune) | Stablecoin inflows = risk-on, outflows = risk-off |
| **Global Liquidity Friction** | DXY + 10Y Real Rates | Macro squeeze compresses crypto first |

### Lane B: Volatility & Sentiment
| Dimension | Data Source | Hypothesis |
|-----------|-------------|------------|
| **Volatility Clustering** | GARCH/realized vol patterns | Regime persistence detection |
| **Narrative Momentum** | Social sentiment (LunarCrush, Santiment) | Reflexivity in crypto markets |

### Lane C: Microstructure Stress (CRIO Domain)
| Dimension | Data Source | Hypothesis |
|-----------|-------------|------------|
| **Perp Funding Rates** | Coinglass, Laevitas | Extreme funding = mean reversion signal |
| **Liquidation Cascades** | Coinglass | Stress transmission mechanism |
| **Open Interest** | Coinglass | Leverage buildup indicator |
| **Basis/Spread** | Kaiko | Arbitrage stress indicator |
| **Exchange Flow Ratio** | Glassnode | Selling pressure indicator |

---

## 6. GATE REQUIREMENTS (BINDING) — CEO-DIR-2026-089

### Gate 1 — 2026-01-25
**Owner:** FINN

| Requirement | Status |
|-------------|--------|
| Regime ontology frozen (3-6 states) | PENDING |
| Primary target frozen (what we predict) | PENDING |
| Hysteresis specification included (transition thresholds) | PENDING |

---

### Gate 2 — 2026-02-01
**Owner:** STIG (+ CDMO if applicable)

| Requirement | Status |
|-------------|--------|
| Data "AIRLOCK" validation completed for Lane A and Lane C | PENDING |
| Canonical ID tagging verified (or explicitly flagged as blocked) | PENDING |
| Epoch boundary (00:00 UTC) implemented for evaluation semantics | PENDING |

---

### Gate 3 — 2026-02-15
**Owner:** FINN + CRIO

| Requirement | Status |
|-------------|--------|
| Brier < 0.25 on primary target (as defined in Gate 1) | PENDING |
| Bootstrap significance p < 0.05 on primary KPI | PENDING |
| CRIO causal mechanism map delivered for Lane C | PENDING |

---

### Gate 4 — 2026-02-22
**Owner:** VEGA

| Requirement | Status |
|-------------|--------|
| Evidence Bundle signed | PENDING |

**Evidence Bundle Contents:**
- Definition freeze proof
- Dataset lineage and AIRLOCK status
- Canonical ID compliance report
- Hysteresis proof (reduced churn)
- Significance report (bootstrap)
- Calibration and stability summary

**NO G4 SIGNATURE = NO CEO DECISION GATE**

---

## 7. Success Criteria

| Metric | Target | Rationale |
|--------|--------|-----------|
| Brier Score | < 0.25 | Must beat random by structural correctness |
| Bootstrap p-value | < 0.05 | Prove predictive skill is not luck |
| Hit Rate | > 55% | Directional edge required |
| Regime Persistence | > 3 days mean | Regimes must be tradeable |
| Hysteresis Churn Reduction | Demonstrable | Operational meaningfulness |

---

## 8. Research Sources

### Academic Literature
- "Cryptocurrency Market Microstructure" (Makarov & Schoar, 2020)
- "Bitcoin Trading and Volatility" (Baur & Dimpfl, 2021)
- "Stablecoin Runs" (Lyons & Viswanath-Natraj, 2023)

### On-Chain Analytics Providers
- Glassnode (chain metrics, exchange flows)
- Dune Analytics (DeFi flows)
- DefiLlama (TVL dynamics)

### Market Microstructure Data
- Coinglass (funding rates, liquidations, OI)
- Laevitas (options flow)
- Kaiko (order book depth, basis)

### Sentiment/Narrative
- LunarCrush (social metrics)
- Santiment (developer activity)

---

## 9. Governance

### 9.1 Isolation Requirements

```
CRYPTO REGIME ENGINE (IoS-003C)
├── Separate schema: vision_crypto (proposed)
├── Separate forecast table: crypto_regime_forecasts
├── Separate outcome table: crypto_regime_outcomes
├── NO cross-reference to equity tables
├── NO shared calibration parameters
├── AIRLOCK for non-canonical data sources
└── Epoch boundary: 00:00 UTC
```

### 9.2 Authority Boundaries

| Agent | Role | Gate |
|-------|------|------|
| FINN | Research, model development, hysteresis design | G1, G3 |
| CRIO | Lane C causal mechanism mapping | G3 |
| STIG | Data pipeline, canonical ID verification, epoch implementation | G2 |
| VEGA | Audit, evidence bundle attestation | G4 |
| CEO | Final approval for production activation | Post-G4 |

### 9.3 Change Gates (ADR-004)

All transitions between Gate 1-4 must be logged in `fhq_meta.adr_audit_log` with specific event_type in compliance with ADR-004.

### 9.4 Canonical Truth Protection (ADR-013)

No sub-executives (CRIO, CDMO) have write access to canonical domains. Any attempt to write crypto regimes to `fhq_meta.canonical_domain_registry` before G4 is a **Class A violation**.

### 9.5 Crypto Forecast Status

**CURRENT: BLOCKED**

No crypto forecasts may be generated until IoS-003C passes G4 audit.

---

## 10. Risk Register

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R1 | Data Lineage Contamination | HIGH | AIRLOCK protocol for non-canonical sources |
| R2 | Target Ambiguity | HIGH | Definition freeze at G1 |
| R3 | Identity Drift (spot vs perp) | HIGH | Canonical ID tagging verification at G2 |
| R4 | Sample Size Insufficient | MEDIUM | Minimum 100 forecasts before G3 |
| R5 | Regime Non-Stationarity | MEDIUM | Hysteresis buffers + high/low vol subperiod testing |

---

## 11. Timeline

| Milestone | Target Date | Owner | Status |
|-----------|-------------|-------|--------|
| Research Kickoff | 2026-01-18 | FINN | **ACTIVATED** |
| **Gate 1: Definition Freeze** | 2026-01-25 | FINN | PENDING |
| **Gate 2: Data Infrastructure** | 2026-02-01 | STIG | PENDING |
| **Gate 3: Model Validation** | 2026-02-15 | FINN+CRIO | PENDING |
| **Gate 4: VEGA Attestation** | 2026-02-22 | VEGA | PENDING |
| CEO Decision Gate | 2026-02-28 | CEO | PENDING |

---

## 12. CEO Guidance

> "Crypto regimes will not be 'good enough' by being clever. They will be accepted only if they are: deterministic in definitions, statistically defensible, identity-clean, causally coherent, comparable over time. Do this once. Do it right. Then we move."
>
> — CEO-DIR-2026-089

> "This is not caution. This is correctness. Crypto and equity are epistemically non-transferable domains. Build from first principles."
>
> — CEO-DIR-2026-076

---

## References

- **CEO-DIR-2026-089**: IoS-003C Discipline Upgrade (Research Only)
- **CEO-DIR-2026-076**: STRESS Inversion Validation + Crypto Regime Separation
- **ADR-003**: Institutional Standards (MDLC)
- **ADR-004**: Change Gates (G0-G4)
- **ADR-013**: Kernel Specification (Infrastructure Sovereignty)
- **ADR-014**: Sub-Executive Governance
- **IoS-001**: Contextual Integrity
- **IoS-003**: Regime Classification Engine (EQUITY)
- **IoS-005**: Statistical Discipline
