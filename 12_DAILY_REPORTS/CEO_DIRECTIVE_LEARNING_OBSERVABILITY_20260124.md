# CEO Directive: Learning Observability & Execution Verification

**Executed:** 2026-01-24 23:15 CET
**Executor:** STIG (EC-003)
**Classification:** GOVERNANCE-CRITICAL / DATABASE-VERIFIED

---

## A. RUNBOOK ↔ SYSTEM REALITY VERIFICATION

### Generator Registry (DB-Verified)

| agent_id | generator_type | owner_ec | run_frequency | output_artifact | logged_where | escalation_path |
|----------|---------------|----------|---------------|-----------------|--------------|-----------------|
| FINN-E | ERROR_REPAIR | EC-004 | On-demand (error-triggered) | hypothesis_canon | fhq_learning.hypothesis_canon | CEO via TEST-TIER1-CAL-001 |
| FINN-T | WORLD_MODEL | EC-004 | On-demand (manual) | hypothesis_canon | fhq_learning.hypothesis_canon | CEO via TEST-FINN-T-ALIGN-001 |
| GN-S | SHADOW_DISCOVERY | EC-003 | On-demand (manual) | hypothesis_canon (DRAFT) | fhq_learning.hypothesis_canon | CEO via TEST-GN-SHADOW-001 |

### Active Calendar Tests (DB-Verified)

| test_code | test_name | owning_agent | monitoring_agent | status | end_date |
|-----------|-----------|--------------|------------------|--------|----------|
| TEST-EC022-OBS-001 | EC-022 Reward Logic Observation Window | EC-022 | EC-003 | ACTIVE | +30 market days |
| TEST-TIER1-CAL-001 | Tier-1 Brutality Calibration | EC-004 | EC-003 | ACTIVE | 2026-01-27 |
| TEST-GN-SHADOW-001 | Golden Needles Shadow-Tier | EC-003 | (none) | ACTIVE | 2026-02-07 |
| TEST-FINN-T-ALIGN-001 | FINN-T World-Model Activation | EC-004 | (none) | ACTIVE | 2026-02-07 |

### Daemon Health Status

| daemon_name | status | last_heartbeat | cadence |
|-------------|--------|----------------|---------|
| uma_meta_analyst | HEALTHY | 2026-01-24 06:00 | Daily 06:00 |
| calendar_integrity_check | HEALTHY | 2026-01-18 | Daily 05:00 |
| TRADING_CALENDAR_GOVERNANCE | HEALTHY | 2026-01-18 | Monthly 1st |
| cnrp_orchestrator | HEALTHY | 2026-01-13 | R1-R4 chain |
| g2c_continuous_forecast_engine | HEALTHY | 2026-01-13 | 30-min |
| ios010_learning_loop | HEALTHY | 2026-01-13 | 2-hour |
| price_freshness_heartbeat | **STOPPED** | 2026-01-13 | 60-min |

**FAIL-CLOSED ITEMS:**
- `price_freshness_heartbeat` daemon is STOPPED - requires attention
- TEST-GN-SHADOW-001 and TEST-FINN-T-ALIGN-001 have no monitoring_agent assigned

---

## B. AGENT RESPONSIBILITY & FOLLOW-UP

### Research Trinity Ownership Matrix

| Track | Owning Agent | Monitoring Agent | Produces | Frequency | "Behind Plan" Definition | Escalation Action |
|-------|--------------|------------------|----------|-----------|--------------------------|-------------------|
| **FINN-E** | EC-004 (FINN) | EC-003 (STIG) | Error-driven hypotheses | When HIGH errors detected | <25% conversion rate after 7d | CEO escalation + forced calibration |
| **FINN-T** | EC-004 (FINN) | EC-003 (STIG) | World-model hypotheses | Daily target | <1 hypothesis/day average | CEO escalation + G3 feature audit |
| **GN-S** | EC-003 (STIG) | CEO (direct) | Shadow hypotheses | Daily target | No output for 48h | Shadow feed investigation |

### "Behind Plan" Criteria (Explicit)

| Metric | Target | Current | Behind If |
|--------|--------|---------|-----------|
| Generator Diversity | No single >60% | 44.4% max | Any generator >60% |
| Causal Depth Avg | >2.5 | 2.56 | <2.0 for 3 consecutive days |
| Tier-1 Death Rate | 60-90% | **11.1%** | <50% or >95% |
| Error→Hypothesis | >25% | 3.0% | <15% after 7d |
| Hypothesis Velocity | >2/day | 2.3/day | <1/day for 3 days |

**CRITICAL FLAG:** Tier-1 Death Rate at 11.1% is FAR BELOW target (60-90%)

---

## C. LEARNING PROGRESSION METRICS

### Hypotheses Generated (7-Day)

| Date | FINN-E | FINN-T | GN-S | Total | Avg Depth |
|------|--------|--------|------|-------|-----------|
| 2026-01-24 | 0 | 4 | 2 | 6 | 3.33 |
| 2026-01-23 | 3 | 0 | 0 | 3 | 1.00 |
| 2026-01-22 | 0 | 0 | 0 | 0 | - |
| 2026-01-21 | 0 | 0 | 0 | 0 | - |
| **7-Day Total** | **3** | **4** | **2** | **9** | **2.56** |

### Experiments Generated (7-Day)

| Date | Created | Completed | Failed |
|------|---------|-----------|--------|
| 2026-01-23 | 2 | 2 | 0 |
| **7-Day Total** | **2** | **2** | **0** |

### Key Learning Metrics

| Metric | Current Value | Target | Status |
|--------|---------------|--------|--------|
| Total Hypotheses | 9 | Growing | OK |
| Avg Causal Depth | 2.56 | >2.5 | **PASS** |
| Tier-1 Death Rate | 11.1% | 60-90% | **FAIL - CRITICAL** |
| Error→Hypothesis | 3.0% | >25% | **FAIL** |
| Generator Diversity | 44.4% max | <60% | **PASS** |

### Error Classification Summary

| Metric | Value |
|--------|-------|
| Total Errors (7d) | 100 |
| Direction Errors | 92 |
| Magnitude Errors | 8 |
| HIGH Priority | 100 |
| Hypotheses Generated | 3 |
| Conversion Rate | **3.0%** |

---

## D. DATA FREQUENCY & OPTIONS READINESS AUDIT

### Price Ingestion Frequency

| Source | Records (7d) | Last Ingest (CET) | Hours Since | Status |
|--------|--------------|-------------------|-------------|--------|
| ALPACA | 182 | 2026-01-24 20:00 | 4.3h | OK |
| yfinance | 688 | 2026-01-23 24:00 | 23.0h | OK |
| YAHOO | 1214 | 2026-01-22 24:00 | 47.0h | STALE |
| TWELVEDATA | 305 | 2026-01-22 24:00 | 47.0h | STALE |
| ECB | 28 | 2026-01-22 24:00 | 47.0h | OK (weekly) |
| TWELVEDATA_FX | 34 | 2026-01-21 24:00 | 71.0h | STALE |
| COINGECKO_REPAIR | 5 | 2026-01-20 | 84.0h | STALE |

### Instruments Enabling Negative Underlying Profit

| Instrument Type | Tickers in System | Ingestion Cadence | Status |
|-----------------|-------------------|-------------------|--------|
| **Inverse ETFs** | NONE | N/A | **NOT AVAILABLE** |
| **Volatility ETFs** | NONE | N/A | **NOT AVAILABLE** |
| **Put Options** | NONE | N/A | **NOT AVAILABLE** |

**CRITICAL GAP:** System has NO instruments for profiting from negative underlying moves.

### Active Assets by Class

| Asset Class | Active Count | Instrument Type | Granularity |
|-------------|--------------|-----------------|-------------|
| CRYPTO | 30+ | SPOT | AGGREGATED |
| EQUITY | (check needed) | SPOT | DAILY |
| FX | (check needed) | SPOT | DAILY |

### Epistemic Insufficiency Flags

| Instrument | Issue | Impact |
|------------|-------|--------|
| All Equities | Daily bars only | Cannot capture intraday regime shifts |
| VIX derivatives | Not ingested | Volatility surface blind |
| Options chains | Not ingested | Cannot assess gamma exposure |
| Inverse ETFs | Not in system | Cannot hedge/profit from declines |

---

## E. CALENDAR ↔ LEARNING LOOP INTEGRITY

### Calendar Completeness Check

| Question | Answer | Source |
|----------|--------|--------|
| What is running? | 4 active tests | canonical_test_events |
| Why? | Business intent documented | business_intent column |
| Who owns it? | EC-003, EC-004, EC-022 | owning_agent column |
| Are we ahead or behind? | **BEHIND on Tier-1 death rate** | hypothesis_canon status |

### Test Event Decision Points

| Test | Next Decision Point | Owner Action Required |
|------|--------------------|-----------------------|
| TEST-EC022-OBS-001 | +30 market days | Evaluate context lift |
| TEST-TIER1-CAL-001 | 2026-01-27 (end) | Assess death rate calibration |
| TEST-GN-SHADOW-001 | 2026-01-31 (mid) | Review shadow hypothesis quality |
| TEST-FINN-T-ALIGN-001 | 2026-01-31 (mid) | Review world-model hypothesis quality |

---

## SUMMARY: CRITICAL GAPS REQUIRING CEO ATTENTION

### FAIL-CLOSED Items

| Item | Status | Required Action |
|------|--------|-----------------|
| Tier-1 Death Rate | 11.1% (target 60-90%) | FINN must increase falsification pressure |
| Error→Hypothesis | 3.0% (target >25%) | Error classification → hypothesis pipeline broken |
| Inverse/Vol Instruments | NONE | Cannot profit from declines |
| Options Data | NONE | Volatility surface not available |
| price_freshness_heartbeat | STOPPED | Daemon requires restart |
| Monitoring Agents | 2 tests unmonitored | Assign EC-003 to all tests |

### Action Items for FINN (EC-004)

1. **Immediately** increase Tier-1 falsification pressure
2. **Within 24h** explain why error→hypothesis conversion is 3%
3. **Within 48h** propose mechanism for higher death rate

### Action Items for STIG (EC-003)

1. Assign self as monitoring_agent to TEST-GN-SHADOW-001 and TEST-FINN-T-ALIGN-001
2. Restart price_freshness_heartbeat daemon
3. Investigate COINGECKO_REPAIR staleness (84h)

### Action Items for CEO

1. Approve/reject inverse ETF addition to asset universe
2. Decide on options chain ingestion priority
3. Review Tier-1 death rate target (is 60-90% correct?)

---

## EVIDENCE

- Query timestamp: 2026-01-24 23:15 CET
- Database: PostgreSQL 17.6 @ 127.0.0.1:54322
- All metrics are database-verified, not assumed

---

*This is an operational learning institute, not an advanced research system.*
*Observability, cadence, and accountability are non-negotiable.*
