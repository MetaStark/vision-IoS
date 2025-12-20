# IoS-005 — G0 Technical Assessment

**Module:** IoS-005 Forecast Calibration & Skill Engine
**Canonical Version:** 2026.PROD.0
**Assessment Date:** 2025-11-29
**Reviewer:** STIG (EC-003, Chief Technology Officer)
**Gate:** G0 (Initial Technical Review)

---

## 1. Executive Summary

**RECOMMENDATION: G0 APPROVED — PROCEED TO G1 DEVELOPMENT**

The IoS-005 specification is technically sound and architecturally well-positioned. The module addresses a critical gap in the FjordHQ system: the absence of scientific validation for regime-driven allocation decisions.

### Key Findings

| Category | Status | Notes |
|----------|--------|-------|
| Specification Quality | ✓ PASS | Well-structured, clear acceptance criteria |
| Dependency Chain | ✓ PASS | IoS-002, IoS-003, IoS-004 all G4 ACTIVE |
| Schema Design | ✓ PASS | Tables created, indexes optimized |
| Task Registration | ✓ PASS | Registered in governance system |
| Data Availability | ⚠ GAP | Canonical price data requires ingestion |
| Alpha Lab Codebase | ⚠ GAP | Codebase does not exist, must be built |

---

## 2. Dependency Assessment

### 2.1 Upstream Dependencies (All Satisfied)

| Module | Status | Activation Date | Data Rows |
|--------|--------|-----------------|-----------|
| IoS-002 (Sensory Cortex) | G4 ACTIVE | 2025-11-29 | — |
| IoS-003 (HMM Perception) | G4 ACTIVE | 2025-11-29 | 10,103 |
| IoS-004 (Allocation Engine) | G4 ACTIVE | 2025-11-29 | 10,103 |

### 2.2 Data Sources Available

| Table | Schema | Rows | Date Range |
|-------|--------|------|------------|
| `regime_predictions_v2` | fhq_research | 10,103 | 2016-08-29 → 2025-11-28 |
| `target_exposure_daily` | fhq_positions | 10,103 | 2016-08-29 → 2025-11-28 |
| `indicator_momentum` | fhq_research | 11,135 | 2015-12-15 → 2025-11-28 |
| `indicator_trend` | fhq_research | 11,187 | 2015-12-02 → 2025-11-28 |

### 2.3 Data Gap: Canonical Price Series

**Issue:** The `fhq_data.price_series` table contains only 720 rows for 1 listing (1 month of data). IoS-005 requires 10+ years of daily close prices for 4 assets to compute returns.

**Resolution Required for G1:**
1. Ingest canonical OHLCV data for BTC-USD, ETH-USD, SOL-USD, EURUSD
2. Store in `fhq_research.backtest_price_cache` or populate `fhq_data.price_series`
3. Ensure price data aligns with `target_exposure_daily` timestamps

---

## 3. Infrastructure Created

### 3.1 Schema Migration

**File:** `04_DATABASE/MIGRATIONS/029_ios005_forecast_calibration_schema.sql`

**Tables Created:**

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `fhq_research.forecast_skill_registry` | Skill scorecards | FSS score, Sharpe, p-values, certification |
| `fhq_research.backtest_results` | Daily performance | Returns, exposures, drawdowns |
| `fhq_research.backtest_price_cache` | Price reproducibility | Canonical prices per backtest |

### 3.2 Hash Chain

| Property | Value |
|----------|-------|
| Chain ID | `HC-IOS-005-2026` |
| Chain Type | `IOS_MODULE` |
| Chain Scope | `IoS-005` |
| Genesis Hash | `379f8019aa36e776304b911e6f9a631177576e1488d03ead0d8eb3e3d82d1ae1` |

### 3.3 Task Registration

| Property | Value |
|----------|-------|
| Task Name | `FORECAST_CALIBRATION_ENGINE_V1` |
| Task Status | `REGISTERED` |
| Gate Level | `G0` |
| Owner | `LARS` |
| Executor | `CODE` |

---

## 4. Alpha Lab v1.0 Requirements

The specification references "Alpha Lab v1.0" as the execution core. This codebase does not currently exist and must be developed.

### 4.1 Required Components

| Component | Module Path | Purpose |
|-----------|-------------|---------|
| Historical Simulator | `alpha_lab.core.historical_simulator` | Replay IoS-004 exposures with zero drift |
| Metric Suite | `alpha_lab.analytics.metrics` | 25+ institutional performance metrics |
| Statistics Engine | `alpha_lab.core.statistics` | Bootstrap, permutation tests |
| FSS Calculator | `alpha_lab.core.skill_score` | FjordHQ Skill Score computation |

### 4.2 Recommended Architecture

```
03_FUNCTIONS/alpha_lab/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── historical_simulator.py    # Deterministic backtest engine
│   ├── statistics.py              # Bootstrap & permutation tests
│   └── skill_score.py             # FSS calculation
├── analytics/
│   ├── __init__.py
│   └── metrics.py                 # 25+ performance metrics
└── config/
    └── default_config.yaml        # Hashable configuration
```

---

## 5. Technical Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Price data gap | HIGH | Prioritize canonical price ingestion in G1 |
| Bootstrap compute cost | MEDIUM | Use efficient numpy vectorization, consider parallel processing |
| Floating-point drift | LOW | Use `decimal.Decimal` for financial calculations |
| Hash chain integrity | LOW | Validate all inputs before storage |

---

## 6. G1 Development Scope

For G1 submission, the following must be completed:

### 6.1 Data Ingestion
- [ ] Ingest 10-year canonical price data for 4 assets
- [ ] Validate price-regime alignment (timestamps match)
- [ ] Populate `backtest_price_cache` with source hashes

### 6.2 Alpha Lab Core
- [ ] Implement `historical_simulator.py` — replay IoS-004 exposures
- [ ] Implement `metrics.py` — all 25+ metrics from specification
- [ ] Implement `statistics.py` — bootstrap and permutation tests
- [ ] Implement `skill_score.py` — FSS formula

### 6.3 Integration
- [ ] Connect to `target_exposure_daily` (IoS-004)
- [ ] Connect to `regime_predictions_v2` (IoS-003)
- [ ] Write results to `forecast_skill_registry`
- [ ] Write daily logs to `backtest_results`

### 6.4 Validation
- [ ] Zero-drift verification against IoS-004 production data
- [ ] Statistical test reproducibility (fixed random seeds)
- [ ] Hash chain integrity verification

---

## 7. Acceptance Criteria Mapping

| Criterion | Specification Requirement | G1 Implementation |
|-----------|---------------------------|-------------------|
| End-to-End Replay | Zero deviation from IoS-004 | `historical_simulator.py` |
| Metric Completeness | 25+ metrics, no nulls | `metrics.py` |
| Statistical Validation | Bootstrap + Permutation | `statistics.py` |
| Artefact Lineage | Full hash verification | ADR-011 compliance |
| FSS Generation | Computed and stored | `skill_score.py` |

---

## 8. Conclusion

**G0 Status: APPROVED**

IoS-005 is architecturally sound and strategically essential. The specification provides clear acceptance criteria, and the dependency chain is fully satisfied.

**Action Items for G1:**
1. **CODE (EC-011):** Build Alpha Lab v1.0 codebase per Section 4.2
2. **STIG (EC-003):** Supervise canonical price ingestion
3. **VEGA:** Prepare G1 review criteria based on specification Section 7

**Next Gate:** G1 (Implementation Review)

---

**Signed:**
STIG (EC-003)
Chief Technology Officer
2025-11-29T21:55:00Z

**Hash:** `a668d55fd36fd5455c6eba2ff38528cea6462153ea27fb45590c5fca7496371c`
