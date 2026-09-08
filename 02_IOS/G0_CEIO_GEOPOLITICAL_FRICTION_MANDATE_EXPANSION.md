# G0 CHANGE PROPOSAL: CEIO Geopolitical Friction Mandate Expansion

**Proposal ID:** G0-2026-019
**Submitted By:** STIG (EC-003)
**Submission Date:** 2026-01-19
**Classification:** MANDATE_EXPANSION
**Priority:** P1
**Target Agent:** CEIO (Chief External Intelligence Officer)

---

## 1. EXECUTIVE SUMMARY

This proposal expands CEIO's mandate from traditional macro-economic intelligence to include **geopolitical friction monitoring**, enabling FjordHQ to detect and respond to structural shifts in global liquidity architecture.

**Strategic Context:** The activation of BRICS Bridge (mBridge), Brazil's Drex CBDC interoperability, and Trump-era tariff escalation (30-245%) represent a "Financial Fission" - the fragmentation of dollar hegemony as the single source of global liquidity truth.

**Core Thesis:** FjordHQ must evolve from linear trend perception to **causal regime understanding** by treating geopolitical friction as a first-class macro factor.

---

## 2. CONSTITUTIONAL ALIGNMENT

### 2.1 ADR-014 Compliance (Sub-Executive Governance)

CEIO's current mandate per ADR-014:
> "Chief External Intelligence Officer: Hente og transformere eksterne data (nyheter, makro, sentiment) til en styringsklar signalstruktur"

**Expansion Justification:** Geopolitical friction (tariffs, sanctions, alternative settlement systems) is a macro input that directly affects regime classification and asset allocation. This expansion is a natural extension of CEIO's "eksterne data" mandate, not a new authority.

### 2.2 IoS Integration Matrix

| IoS | Integration Point | Change Type |
|-----|------------------|-------------|
| IoS-001 | New canonical asset: Geopolitical Friction Index | EXTENDS |
| IoS-003 | New regime: `BIFURCATED_LIQUIDITY` | EXTENDS |
| IoS-006 | New feature cluster: `GEOPOLITICAL_FRICTION` | EXTENDS |
| IoS-007 | New causal edges: BRICS → De-dollarization → Crypto | EXTENDS |
| IoS-008 | TTL reduction during geopolitical volatility | CONFIGURES |

### 2.3 ADR-013 Compliance (One-Source-of-Truth)

All geopolitical data flows through `fhq_macro.macro_nodes` as the canonical layer. No parallel truth structures created.

---

## 3. SCOPE DEFINITION

### 3.1 In Scope

1. **Data Source Expansion**
   - USTR (US Trade Representative) - Tariff schedules
   - BIS (Bank for International Settlements) - Cross-border payment flows
   - IMF COFER - Currency composition of foreign exchange reserves
   - Alternative settlement monitoring (mBridge, CIPS, SPFS)

2. **Macro Node Creation**
   - `MACRO_GEOPOLITICAL_FRICTION` - Composite de-dollarization pressure index
   - `MACRO_TARIFF_EFFECTIVE_RATE` - Trade-weighted average tariff rate
   - `MACRO_BRICS_SETTLEMENT_SHARE` - Non-USD international settlement percentage
   - `MACRO_SANCTIONS_INTENSITY` - Active sanctions count and scope

3. **Causal Edge Modeling**
   - `TARIFF_RATE → DXY` (AMPLIFIES)
   - `BRICS_SETTLEMENT → DXY` (INHIBITS)
   - `GEOPOLITICAL_FRICTION → BTC-USD` (LEADS)
   - `SANCTIONS_INTENSITY → CRYPTO_ADOPTION` (AMPLIFIES)

4. **Regime Extension**
   - New regime: `BIFURCATED_LIQUIDITY`
   - Trigger conditions and hysteresis rules

### 3.2 Out of Scope

- Direct trading signals from geopolitical events (remains FINN/LINE domain)
- Political sentiment analysis (not quantifiable per ADR-003)
- Predictive modeling of government actions (outside epistemic boundary)
- Real-time news feed processing (latency concerns)

---

## 4. TECHNICAL SPECIFICATION

### 4.1 New Data Sources (fhq_governance.approved_data_sources)

| Source Code | Source Name | Type | Verification Method |
|-------------|-------------|------|---------------------|
| USTR | US Trade Representative | GOVERNMENT_AGENCY | Official publication cross-check |
| BIS | Bank for International Settlements | INTERNATIONAL_ORG | API with hash verification |
| IMF_COFER | IMF Currency Composition | INTERNATIONAL_ORG | Quarterly publication |
| SWIFT_GPI | SWIFT gpi Tracker | FINANCIAL_INFRA | Licensed data feed |

### 4.2 New Macro Nodes (fhq_macro.macro_nodes)

```sql
-- Geopolitical Friction Index (Composite)
{
  node_id: 'MACRO_GEOPOLITICAL_FRICTION',
  node_type: 'MACRO_FACTOR',
  subtype: 'GEOPOLITICAL',
  description: 'Composite de-dollarization pressure index',
  source_tier: 'DERIVED',
  frequency: 'WEEKLY',
  stress_threshold: 0.70,
  extreme_threshold: 0.85
}

-- Effective Tariff Rate
{
  node_id: 'MACRO_TARIFF_EFFECTIVE_RATE',
  node_type: 'MACRO_FACTOR',
  subtype: 'TRADE',
  description: 'Trade-weighted average US tariff rate',
  source_tier: 'LAKE',
  source_provider: 'USTR',
  frequency: 'MONTHLY',
  stress_threshold: 15.0,  -- percent
  extreme_threshold: 25.0
}

-- BRICS Settlement Share
{
  node_id: 'MACRO_BRICS_SETTLEMENT_SHARE',
  node_type: 'MACRO_FACTOR',
  subtype: 'LIQUIDITY',
  description: 'Non-USD international settlement percentage',
  source_tier: 'PULSE',
  source_provider: 'BIS',
  frequency: 'QUARTERLY',
  stress_threshold: 20.0,  -- percent
  extreme_threshold: 30.0
}

-- Sanctions Intensity
{
  node_id: 'MACRO_SANCTIONS_INTENSITY',
  node_type: 'MACRO_FACTOR',
  subtype: 'GEOPOLITICAL',
  description: 'Active US/EU sanctions programs count and scope',
  source_tier: 'LAKE',
  source_provider: 'OFAC',
  frequency: 'WEEKLY'
}
```

### 4.3 New Causal Edges (fhq_macro.macro_edges)

| Source | Target | Edge Type | Hypothesis |
|--------|--------|-----------|------------|
| MACRO_TARIFF_EFFECTIVE_RATE | MACRO_DXY | AMPLIFIES | Higher tariffs strengthen USD short-term |
| MACRO_BRICS_SETTLEMENT_SHARE | MACRO_DXY | INHIBITS | Alternative settlement weakens USD demand |
| MACRO_GEOPOLITICAL_FRICTION | BTC-USD | LEADS | Friction drives neutral reserve adoption |
| MACRO_SANCTIONS_INTENSITY | MACRO_BRICS_SETTLEMENT_SHARE | AMPLIFIES | Sanctions accelerate BRICS adoption |
| MACRO_GEOPOLITICAL_FRICTION | MACRO_VIX | AMPLIFIES | Friction increases market uncertainty |

### 4.4 New Regime Definition (IoS-003)

```yaml
regime: BIFURCATED_LIQUIDITY
description: "Global liquidity split between USD and alternative settlement systems"
trigger_conditions:
  - MACRO_BRICS_SETTLEMENT_SHARE > 15%
  - MACRO_TARIFF_EFFECTIVE_RATE > 20%
  - MACRO_GEOPOLITICAL_FRICTION > 0.60
hysteresis:
  entry_confirmation_days: 5
  exit_confirmation_days: 10
implications:
  - Reduce confidence in USD-correlated forecasts
  - Increase weight on crypto as neutral reserve
  - Shorten TTL on all macro-driven decisions
```

---

## 5. CEIO MANDATE EXPANSION

### 5.1 Current Mandate (Per ADR-014)

```
CEIO shall:
- Ingest external macro data from approved sources
- Transform raw data into signal-ready structures
- Maintain data freshness per IoS-001 standards
- Report to STIG for infrastructure, FINN for research integration
```

### 5.2 Expanded Mandate (Post-Approval)

```
CEIO shall additionally:
- Monitor geopolitical friction indicators from approved sources
- Compute and maintain MACRO_GEOPOLITICAL_FRICTION composite index
- Alert LARS when friction exceeds stress_threshold
- Provide weekly briefing to CEO on de-dollarization metrics
- Trigger DEFCON escalation if extreme_threshold breached
- Coordinate with CRIO for causal hypothesis validation
```

### 5.3 New CEIO Contracts

| Trigger Event | Expected Action | SLA |
|---------------|-----------------|-----|
| GEOPOLITICAL_DATA_REFRESH | Update friction nodes | 6 hours |
| FRICTION_STRESS_THRESHOLD | Alert LARS + CEO | 30 minutes |
| FRICTION_EXTREME_THRESHOLD | Trigger DEFCON-3 | 10 minutes |
| TARIFF_ANNOUNCEMENT | Capture and quantify | 4 hours |

---

## 6. IMPLEMENTATION PLAN

### Phase 1: Infrastructure (Days 1-3)
- [ ] Migration 311: Create geopolitical friction tables and nodes
- [ ] Approve new data sources in governance registry
- [ ] Register CEIO expanded contracts

### Phase 2: Data Ingestion (Days 4-7)
- [ ] Implement USTR tariff scraper
- [ ] Implement BIS cross-border flow parser
- [ ] Implement BRICS settlement estimator
- [ ] Backfill historical data (2020-present)

### Phase 3: Causal Modeling (Days 8-14)
- [ ] CRIO validates edge hypotheses with historical data
- [ ] Bootstrap significance testing on LEADS relationships
- [ ] VEGA attestation of causal graph integrity

### Phase 4: Regime Integration (Days 15-21)
- [ ] IoS-003 regime engine update for BIFURCATED_LIQUIDITY
- [ ] IoS-008 TTL adjustment rules
- [ ] Shadow mode testing (7 days)

### Phase 5: Activation (Day 22)
- [ ] CEO review and G4 approval
- [ ] Production activation
- [ ] First weekly geopolitical briefing

---

## 7. RISK ASSESSMENT

### 7.1 Data Quality Risks

| Risk | Mitigation |
|------|------------|
| BRICS data opacity | Use multiple proxies (BIS, SWIFT alternatives, trade flow analysis) |
| Tariff schedule complexity | Focus on effective rate, not line-item |
| Political event unpredictability | We model friction, not predict events |

### 7.2 Model Risks

| Risk | Mitigation |
|------|------------|
| Spurious correlation | CRIO Lane C validation required |
| Regime flip-flopping | Hysteresis rules with 5-day confirmation |
| Overconfidence in geopolitical signals | Confidence ceiling at 0.60 for friction-derived forecasts |

### 7.3 Operational Risks

| Risk | Mitigation |
|------|------------|
| CEIO scope creep | Hard boundary: no political prediction |
| Information overload | Weekly digest, not real-time alerts (except thresholds) |
| API cost escalation | BIS and IMF are free; SWIFT requires budget review |

---

## 8. SUCCESS CRITERIA

### 8.1 Quantitative

- MACRO_GEOPOLITICAL_FRICTION node populated with 5+ years historical data
- At least 3 LEADS edges validated with p < 0.05
- Regime detection latency < 5 days from structural shift
- Zero CEIO scope violations (no political prediction)

### 8.2 Qualitative

- CEO receives actionable weekly geopolitical briefing
- FINN can reference friction factors in forecast rationale
- System detects "Financial Fission" events before mainstream narrative

---

## 9. GOVERNANCE GATE REQUIREMENTS

### G1 (Technical Validation)
- [ ] STIG validates Migration 311 schema
- [ ] Data source connectivity verified
- [ ] Historical backfill complete

### G2 (Research Validation)
- [ ] CRIO validates causal hypotheses
- [ ] FINN confirms integration with forecast engine
- [ ] CDMO confirms canonical data storage

### G3 (Audit Verification)
- [ ] VEGA attests causal graph integrity
- [ ] Ed25519 signatures on all new contracts
- [ ] Evidence bundle complete

### G4 (CEO Activation)
- [ ] CEO reviews evidence bundle
- [ ] Shadow mode results satisfactory
- [ ] Final approval signed

---

## 10. ATTESTATION

**Submitted By:** STIG
**Contract:** EC-003_2026_PRODUCTION
**Timestamp:** 2026-01-19T10:00:00Z

**Constitutional Compliance:**
- ADR-014: CEIO mandate expansion within "External Intelligence" scope
- ADR-013: All data flows through canonical fhq_macro schema
- ADR-004: Full G0-G4 gate process followed
- IoS-006: Feature cluster extension, not replacement

**Strategic Alignment:**
This expansion enables FjordHQ to detect structural shifts in global liquidity architecture before they manifest as price movements. By treating geopolitical friction as a macro factor rather than news noise, we maintain epistemic discipline while gaining first-mover advantage.

---

## APPENDIX A: Geopolitical Friction Index Formula

```
GFI = w1 * TARIFF_NORMALIZED +
      w2 * BRICS_SETTLEMENT_DELTA +
      w3 * SANCTIONS_INTENSITY_NORMALIZED +
      w4 * USD_RESERVE_SHARE_DELTA

Where:
- w1 = 0.30 (tariff impact weight)
- w2 = 0.35 (settlement shift weight - highest)
- w3 = 0.20 (sanctions weight)
- w4 = 0.15 (reserve composition weight)

Normalization: Each component scaled 0-1 based on historical percentiles
Update frequency: Weekly
```

## APPENDIX B: BIFURCATED_LIQUIDITY Regime Characteristics

```yaml
regime_characteristics:
  volatility_expectation: ELEVATED
  correlation_stability: LOW
  usd_correlation_reliability: DEGRADED
  crypto_neutral_reserve_thesis: STRENGTHENED
  forecast_confidence_ceiling: 0.60
  ttl_multiplier: 0.5  # Half normal TTL

portfolio_implications:
  - Reduce USD-denominated position confidence
  - Increase crypto allocation ceiling (subject to Brier validation)
  - Diversify macro factor exposure
  - Monitor mBridge volume as leading indicator
```

---

**END OF G0 PROPOSAL**

*Awaiting CEO review for G1 gate opening.*
