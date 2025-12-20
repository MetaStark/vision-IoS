# IoS-006 — G0 TECHNICAL ASSESSMENT

**Version:** 2026.PROD.G0
**Owner:** FINN (Tier-1 Research)
**Technical Authority:** STIG (CTO)
**Validator:** IoS-005 (Constitutional Audit Engine)
**Governance:** VEGA
**Date:** 2025-11-30

---

## 1. EXECUTIVE SUMMARY

IoS-006 Global Macro & Factor Integration Engine has passed G0 Technical Assessment.

**Strategic Hypothesis:** *"Price is the shadow, Macro is the object."*

IoS-006 is not a data pipe — it is a **Feature Filtration System** designed to reject 95% of macro candidates. Only features that survive IoS-005's constitutional significance testing may enter future HMM v3.0 (IoS-003B).

---

## 2. DEPENDENCY VERIFICATION

| Dependency | Status | Version | Notes |
|------------|--------|---------|-------|
| IoS-002 | ACTIVE | 2026.PROD.1 | Indicator Engine — provides price features |
| IoS-005 | ACTIVE | 2026.PROD.G4 | **CONSTITUTIONAL** — validates all features |
| ADR-013 | ACTIVE | — | One-True-Source — enforces lineage |

**Verdict:** All dependencies satisfied.

---

## 3. SCHEMA ARCHITECTURE

### 3.1 Schema Created: `fhq_macro`

| Table | Purpose | Rows |
|-------|---------|------|
| `feature_registry` | Macro Feature Registry (MFR) — canonical truth source | 0 |
| `raw_staging` | Ingestion staging area | 0 |
| `canonical_series` | Immutable historical series (ADR-013) | 0 |
| `stationarity_tests` | ADF test audit trail | 0 |
| `feature_significance` | IoS-005 significance results | 0 |

### 3.2 Key Constraints Implemented

| Constraint | Table | Purpose |
|------------|-------|---------|
| `frequency` CHECK | feature_registry | Valid frequencies only |
| `stationarity_method` CHECK | feature_registry | Valid transforms only |
| `cluster` CHECK | feature_registry | Valid Alpha Cubes only |
| `status` CHECK | feature_registry | Valid lifecycle states only |
| `unique_feature_source` | feature_registry | Prevent duplicate registrations |
| `unique_canonical_point` | canonical_series | One value per feature/timestamp |

---

## 4. FEATURE CLUSTERS (Alpha Cubes)

| Cluster | Code | Hypothesis | Example Features |
|---------|------|------------|------------------|
| **A: Liquidity** | LIQUIDITY | Crypto beta = f(fiat debasement) | M2 YoY, Net Liquidity, TGA |
| **B: Credit** | CREDIT | Credit stress precedes liquidity withdrawal | HY Spreads, Yield Curve, MOVE |
| **C: Volatility** | VOLATILITY | Vol regimes dictate leverage capacity | VIX Term Structure, IV/RV |
| **D: Factors** | FACTOR | Macro-gravity on crypto prices | DXY, Real Rates, Tech Beta |
| **E: On-Chain** | ONCHAIN | Blockchain-native signals | (Future) |
| **F: Sentiment** | SENTIMENT | Positioning and surveys | (Future) |

---

## 5. DATA PIPELINE ARCHITECTURE

```
External Sources (FRED, Bloomberg, Yahoo)
           ↓
    [CEIO Ingestion]
           ↓
    fhq_macro.raw_staging
           ↓
    [Canonicalization (ADR-013)]
           ↓
    fhq_macro.canonical_series
           ↓
    [STATIONARITY GATE]  ←── fhq_macro.stationarity_tests
           ↓
    ADF Test: p < 0.05?
       │
       ├── YES → Proceed
       │
       └── NO → Apply Transform → Re-test → If still non-stationary: REJECT
           ↓
    [LAG ALIGNMENT]
           ↓
    [IoS-005 SIGNIFICANCE TEST]  ←── fhq_macro.feature_significance
           ↓
    p < 0.05 (Bonferroni)?
       │
       ├── YES → SIGNIFICANT
       │         ↓
       │    [OOS VALIDATION]
       │         ↓
       │    OOS p < 0.05?
       │       │
       │       ├── YES → GOLDEN (→ HMM v3.0)
       │       └── NO → SIGNIFICANT_IS only
       │
       └── NO → REJECTED (95% expected)
```

---

## 6. STATIONARITY GATE

**Critical Filter:** Non-stationary data is NEVER passed to IoS-005.

### Test Protocol

| Test | Method | Threshold | Action if Failed |
|------|--------|-----------|------------------|
| Level | ADF | p < 0.05 | Apply DIFF |
| After DIFF | ADF | p < 0.05 | Apply LOG_DIFF |
| After LOG_DIFF | ADF | p < 0.05 | Apply SECOND_DIFF |
| After SECOND_DIFF | ADF | p < 0.05 | REJECT feature |

### Transformation Methods

| Method | Formula | Use Case |
|--------|---------|----------|
| DIFF | x(t) - x(t-1) | Unit root removal |
| LOG_DIFF | log(x(t)) - log(x(t-1)) | Percentage changes |
| Z_SCORE | (x - μ) / σ | Standardization |
| SEASONAL_DIFF | x(t) - x(t-period) | Seasonal patterns |

---

## 7. NULL RESULT REGIME

IoS-006 operates under the **Expected Null Result Regime** inherited from IoS-005:

### 7.1 Core Assumptions

- Most macro features will NOT be significant
- Finding no correlation is a valid, expected result
- 95% rejection rate is the baseline expectation

### 7.2 Bonferroni Firewall

When testing N features:
- Adjusted threshold: α = 0.05 / N
- Example: 20 features → α = 0.0025

### 7.3 Anti-P-Hacking Discipline

- All features MUST be registered in MFR before testing
- No ad-hoc feature creation allowed
- Hypothesis must be documented before testing

---

## 8. IoS-005 INTEGRATION

IoS-006 is **subordinate** to IoS-005 (Constitutional Audit Engine):

| Rule | Description |
|------|-------------|
| **MFR Requirement** | IoS-005 may only test features registered in fhq_macro.feature_registry |
| **Stationarity Requirement** | IoS-005 receives only stationary series |
| **Lag Alignment** | All data is lag-adjusted before testing |
| **Evidence Chain** | All tests produce evidence files linked to fhq_analytics |

---

## 9. GOVERNANCE REGISTRATION

### ios_registry Entry

| Field | Value |
|-------|-------|
| ios_id | IoS-006 |
| title | Global Macro & Factor Integration Engine |
| version | 2026.PROD.G0 |
| status | DRAFT |
| owner_role | FINN |
| dependencies | IoS-002, IoS-005 |

### task_registry Entry

| Field | Value |
|-------|-------|
| task_name | MACRO_FACTOR_ENGINE_V1 |
| task_type | FEATURE_PIPELINE |
| gate_level | G0 |
| gate_approved | FALSE |

### hash_chains Entry

| Field | Value |
|-------|-------|
| chain_id | HC-IOS-006-2026 |
| chain_type | IOS_MODULE |
| schema_frozen | FALSE |

---

## 10. ACCEPTANCE CRITERIA FOR G1

IoS-006 is ready for G1 Technical Validation when:

- [ ] MFR schema tested with sample features
- [ ] Stationarity pipeline (ADF) implemented and tested
- [ ] At least one feature cluster populated with 5+ candidates
- [ ] Lag alignment logic verified
- [ ] IoS-005 integration pathway tested
- [ ] Evidence file generation confirmed

---

## 11. STIG TECHNICAL ASSESSMENT

### 11.1 Architecture Review

| Criterion | Status | Notes |
|-----------|--------|-------|
| Schema design | PASS | 5 tables with proper constraints |
| ADR-013 compliance | PASS | Lineage columns present |
| ADR-011 compliance | PASS | Hash chain created |
| Constraint coverage | PASS | All enums constrained |
| Index strategy | PASS | Appropriate indexes created |

### 11.2 Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Look-ahead bias | HIGH | Lag alignment mandatory |
| P-hacking | HIGH | MFR registration required |
| Non-stationarity | MEDIUM | ADF gate enforced |
| Overfitting | MEDIUM | OOS validation required |

### 11.3 Verdict

**G0 TECHNICAL ASSESSMENT: PASS**

IoS-006 foundation schema is correctly structured and governance-compliant.
Ready to proceed to Phase 2 (Ingest & Canonicalize).

---

## SIGNATURES

| Role | Agent | Decision | Date |
|------|-------|----------|------|
| Technical Authority | STIG | APPROVED | 2025-11-30 |
| Owner | FINN | Pending G1 | — |
| Governance | VEGA | Pending G1 | — |

---

**Hash Chain:** HC-IOS-006-2026
**Migration:** 035_ios006_macro_factor_foundation.sql
