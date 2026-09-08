# IoS-016 - Economic Calendar and Temporal Governance

**Canonical Version:** 2026.G0.MBB++
**Owner:** LINE (EC-005) + CEIO (EC-009)
**Governance:** VEGA (Tier-1), CEO (Tier-0)
**Infrastructure:** STIG (EC-003)
**Data Steward:** CDMO (EC-007)
**Dependencies:** ADR-001..016, ADR-020, IoS-001, IoS-003, IoS-005, IoS-010
**CEO Approval:** Phase 1 Foundation APPROVED (2026-01-16)

---

## 1. Mission

IoS-016 is FjordHQ's canonical economic calendar and temporal governance system.

Its mission:

- Provide a single source of truth for market-moving events across all asset classes
- Enable event-aware learning by tagging forecasts with event proximity context
- Separate model error from event-driven volatility in Brier score analysis
- Detect information leakage through pre-event drift monitoring
- Support UMA's Learning Velocity Index (LVI) with clean learning windows
- Ensure all calendar data is auditable, signed, and court-proof

**IoS-016 does not generate trading signals.**
**It does not predict event outcomes.**
**It provides temporal context for learning systems.**

---

## 2. Strategic Rationale

### 2.1 The Learning Gap

Without calendar awareness, FjordHQ's learning system suffers from:

| Gap | Impact on Learning | Impact on ROI |
|-----|-------------------|---------------|
| **False-Negative Learning** | System punishes itself for event-driven volatility | Capital allocation miscalibration |
| **Model Drift vs Event Noise** | Cannot distinguish internal error from external shock | Incorrect model updates |
| **Brier Score Inflation** | Event-adjacent forecasts degrade aggregate Brier | Understated true model skill |
| **LVI Underestimation** | Learning velocity appears slower than reality | Resource misallocation |
| **Regime Misclassification** | Events cause regime transitions that look like errors | Strategy selection errors |

**Estimated Learning Efficiency Loss: 15-25% of validated signals misattributed**

### 2.2 The Solution

IoS-016 provides:

1. **Event Registry** - Canonical list of event types with impact rankings
2. **Calendar Events** - Timestamped instances with surprise scores
3. **Forecast Tagging** - EVENT_ADJACENT / EVENT_NEUTRAL / POST_EVENT classification
4. **Stratified Brier** - Separate analysis for event-affected vs clean windows
5. **Ghost Event Detection** - Flag unexplained volatility for calendar gaps
6. **LVI_adjusted** - CEO-visible learning metric excluding event noise

---

## 3. Scope

IoS-016 covers:

### 3.1 Event Categories

| Category | Examples | Impact Rank Range |
|----------|----------|-------------------|
| **MACRO** | FOMC, CPI, NFP, GDP, PMI | 3-5 |
| **EQUITY** | Earnings releases, dividends, splits | 2-4 |
| **CRYPTO** | Halvings, hard forks, regulatory announcements | 2-5 |
| **CROSS_ASSET** | Currency interventions, commodity shocks | 3-5 |

### 3.2 Coverage Scope (Phase 1 - 14 Day Firewall)

| Scope | Phase 1 | Phase 2+ |
|-------|---------|----------|
| US Macro (FOMC, CPI, NFP) | Full | Full |
| Global Central Banks | Major only | Full |
| Equity Earnings | Top 50 holdings | Full coverage |
| Crypto Events | BTC/ETH major events | Full |
| Corporate Actions | Partial | Full |

### 3.3 Out of Scope

- Event outcome prediction
- Trading signal generation
- Strategy recommendations
- Sentiment analysis of event text

---

## 4. Governance Alignment

### 4.1 ADR-001 - System Charter

IoS-016 extends the charter to include temporal governance:

| Agent | Calendar Authority |
|-------|-------------------|
| LINE | Temporal governance owner - system clock, event scheduling |
| CEIO | Calendar operator - external data ingestion |
| CDMO | Data steward - metadata definitions, quality standards |
| STIG | Infrastructure - schema enforcement, security |
| VEGA | Auditor - lineage verification, attestation |

### 4.2 ADR-002 - Audit Charter

All calendar operations must:

- Log to `fhq_calendar.ingestion_batches` with hash chains
- Maintain TOS/license evidence in `provider_tos_archive`
- Support court-proof verification per CEO Directive 2025-12-20

### 4.3 ADR-004 - Change Gates

Calendar changes follow the standard G0-G4 cycle:

| Gate | Calendar Requirement |
|------|---------------------|
| G0 | IoS-016 document (this), schema proposal |
| G1 | Schema DDL validated, timezone logic tested |
| G2 | VEGA lineage review, TOS compliance verified |
| G3 | QG-F1..F5 passed, VEGA attestation |
| G3.5 | 48h Shadow Mode (CEO S2 refinement) |
| G4 | CEO activation, production deployment |

### 4.4 ADR-008 - Key Management

| Component | ADR-008 Status |
|-----------|---------------|
| Calendar records | OPEN - Must be signed by CEIO key |
| Event ingestion batches | OPEN - Signature chain required |
| Schema migrations | Standard - STIG signature |

### 4.5 ADR-012 - Economic Safety

Calendar providers follow API waterfall:

| Tier | Calendar Sources |
|------|-----------------|
| Tier 1 (Lake) | FRED, yfinance (free) |
| Tier 2 (Pulse) | Economic calendars via CEIO |
| Tier 3 (Sniper) | Premium calendar APIs (rate-limited) |

### 4.6 ADR-013 - One-True-Source

`fhq_calendar.calendar_events` is the canonical source for all event data:

- Multi-vendor reconciliation via `source_conflict_log`
- Highest domain-specific reliability wins
- All consumers read from canonical table only

### 4.7 ADR-016 - DEFCON

Calendar respects circuit breaker states:

| DEFCON | Calendar Behavior |
|--------|-------------------|
| GREEN | Full operation, all event categories |
| YELLOW | Full operation, enhanced monitoring |
| ORANGE | Ingestion continues, tagging paused |
| RED | Read-only mode, no new ingestion |
| BLACK | Complete halt |

---

## 5. Functional Architecture

### 5.1 Component Overview

```
External Providers → CEIO Ingestion → Staging → Reconciliation → Canonical Events
                                                      ↓
                                              Source Conflict Log
                                                      ↓
Forecast Engine → Event Tagger → Tagged Forecasts → Brier Analysis
                                        ↓
                                  Ghost Detector → UMA Investigation
                                        ↓
                                  LVI Calculator → CEO Dashboard
```

### 5.2 Event Type Registry

Defines canonical event types with metadata:

| Field | Description |
|-------|-------------|
| event_type_code | Primary key (e.g., 'US_FOMC', 'US_CPI') |
| event_category | MACRO, EQUITY, CRYPTO, CROSS_ASSET |
| impact_rank | 1-5 (5 = highest impact) |
| consensus_available | Whether consensus typically exists |
| actual_available | Whether actual value typically exists |
| surprise_normalization_unit | BPS for rates, PCT for CPI, etc. |
| historical_std_lookup_table | Reference for normalization |

### 5.3 Calendar Events

Stores event instances:

| Field | Description |
|-------|-------------|
| event_id | Primary key |
| event_type_code | FK to registry |
| event_timestamp | UTC enforced (TIMESTAMPTZ) |
| time_semantics | RELEASE_TIME, EMBARGO_LIFT, etc. |
| time_precision | DATE_ONLY, MINUTE, SECOND |
| consensus_estimate | Optional per event-type rules |
| actual_value | Optional per event-type rules |
| surprise_score | Normalized by historical_std |
| ceio_signature | Ed25519 signature |

### 5.4 Event Tagging

The `tag_event_proximity()` function classifies forecasts:

| Tag | Definition |
|-----|------------|
| EVENT_ADJACENT | Forecast falls within pre-event window |
| EVENT_NEUTRAL | No significant events within window |
| POST_EVENT | Forecast falls within post-event window |

Windows are governed by `leakage_detection_config`:

| Impact Rank | Pre-Event Window | Post-Event Window |
|-------------|-----------------|-------------------|
| 5 (Critical) | 4 hours | 24 hours |
| 4 (High) | 3 hours | 12 hours |
| 3 (Medium) | 2 hours | 6 hours |
| 2 (Low) | 1 hour | 3 hours |
| 1 (Minimal) | 30 minutes | 1 hour |

### 5.5 Ghost Event Detection

Flags unexplained volatility for investigation:

| Field | Description |
|-------|-------------|
| flag_id | Primary key |
| asset_id | Affected asset |
| detection_timestamp | When flagged |
| suspected_cause | COVERAGE_GAP, TIMESTAMP_DEFECT, MAPPING_DEFECT, TRUE_GHOST |
| triage_notes | Investigation notes |
| resolution_event_id | Linked event if found |

### 5.6 Asset-Specific Brier Alerts (CEO Strong Signal)

Monitors persistent asset-level Brier degradation:

| Alert Level | Condition | Action |
|-------------|-----------|--------|
| AMBER | Asset Brier > Portfolio Brier + 0.10 for 3+ cycles | Flag for UMA review |
| RED | Asset Brier > 0.60 for 5+ cycles | CEO alert + model quarantine |
| CRITICAL | Degradation correlates with EVENT_NEUTRAL windows | STRONG SIGNAL - investigate model edge |

---

## 6. LVI Formula

The Learning Velocity Index adjusted for events:

```
LVI_adjusted = SUM(Forecast_success * (1 - Event_proximity * Impact_rank)) / T_total
```

Where:
- `Forecast_success` = 1 if forecast within confidence interval, 0 otherwise
- `Event_proximity` = 0 (EVENT_NEUTRAL), 0.5 (POST_EVENT), 1.0 (EVENT_ADJACENT)
- `Impact_rank` = 0.2 to 1.0 (normalized from 1-5)
- `T_total` = Total time period

**Purpose:** Give CEO a realistic view of learning velocity without noise from scheduled events.

---

## 7. Provider Management

### 7.1 Provider State

Each provider has domain-specific reliability scores:

| Field | Description |
|-------|-------------|
| reliability_macro | 0-1 score for macro events |
| reliability_equity | 0-1 score for equity events |
| reliability_crypto | 0-1 score for crypto events |
| reliability_cross_asset | 0-1 score for cross-asset events |

### 7.2 TOS Compliance (CEO Refinement #3)

All providers must have documented TOS compliance:

| Field | Description |
|-------|-------------|
| tos_snapshot_hash | SHA-256 of TOS document |
| tos_snapshot_date | When TOS was captured |
| tos_permitted_use | Scope of permitted use |
| tos_redistribution_allowed | Boolean |
| tos_evidence_uri | Link to archived TOS |

### 7.3 Conflict Resolution

When providers disagree:

1. Domain-specific reliability score determines winner
2. Conflict logged to `source_conflict_log`
3. VEGA can flag for manual review if delta significant

---

## 8. Integration Points

### 8.1 IoS-001 (Canonical Asset Registry)

Calendar extends asset registry with event metadata:
- Event types linked to asset classes
- Asset-event mapping table

### 8.2 IoS-003 (Regime Engine)

Regime engine consumes event context:
- STRESS regime considers event proximity
- Regime transitions tagged with causal events

### 8.3 IoS-005 (Forecast Calibration)

Brier scores stratified by event proximity:
- EVENT_ADJACENT Brier separated from EVENT_NEUTRAL
- Clean windows identified for model skill assessment

### 8.4 IoS-010 (Prediction Ledger)

Forecasts tagged with event context:
- `event_proximity_tag` column
- `adjacent_event_id` reference
- `impact_rank` inheritance

### 8.5 UMA (EC-014)

UMA consumes:
- LVI_adjusted for learning velocity
- Brier stratification for drift detection
- Ghost event flags for calendar gap analysis

---

## 9. ROI Validation Plan (CEO Refinement #1)

### 9.1 Hypotheses to Validate

| Hypothesis | Validation Metric | Success Threshold | Deadline |
|------------|-------------------|-------------------|----------|
| False-negative reduction | EVENT_ADJACENT vs EVENT_NEUTRAL Brier delta | >= 0.05 | Day 28 |
| Brier improvement | Aggregate Brier Day 23 vs Day 9 | <= 0.42 | Day 28 |
| LVI_adjusted utility | CEO reports as actionable | Qualitative | Day 28 |
| Drift detection speed | Time from drift to alert | <= 4 hours | Day 28 |
| Leakage flagging | True positive rate on synthetic injection | >= 80% | Day 28 |

### 9.2 Stop-Loss Rules

| Condition | Action |
|-----------|--------|
| Brier degradation Day 23 > Day 9 + 0.03 | HALT Phase 2, investigate |
| LVI_adjusted computation errors > 5% | HALT UMA integration, fix formula |
| Ghost event false-positive rate > 30% | Disable ghost detection, recalibrate |
| Shadow Mode fails determinism test | DO NOT promote to production |
| Any stop-loss triggered | CEO review required before resumption |

---

## 10. Shadow Mode Protocol (CEO S2)

Before production activation:

1. CFAO activates 48h Shadow Mode
2. `tag_event_proximity()` runs in parallel, writes to shadow table
3. Determinism verified: same inputs → same outputs
4. No drift in tagging logic over 48h window
5. CEO briefed on shadow results before G4 promotion

---

## 11. Activation Path (G0 - G4)

| Gate | Timeline | Deliverables | Status |
|------|----------|--------------|--------|
| G0 | Day 1 | IoS-016 document, schema proposal, evidence | SUBMITTING |
| G1 | Days 2-5 | DDL validated, timezone tested, reconciliation reviewed | PENDING |
| G2 | Days 6-8 | VEGA lineage review, ADR compliance, TOS archive | PENDING |
| G3 | Days 9-12 | QG-F1..F5, VEGA attestation, evidence bundle | PENDING |
| G3.5 | Days 12-14 | 48h Shadow Mode, determinism verified | PENDING |
| G4 | Day 14 | CEO approval, production activation | PENDING |

---

## 12. Closing Principle

> A system that learns without knowing what mattered, how much it mattered, and whether it surprised the world will never converge to edge.

IoS-016 ensures FjordHQ learns only from signal, never from noise.

---

## Appendix A: Database Schema

### A.1 Tables (in `fhq_calendar` schema)

1. **event_type_registry** - Canonical event types
2. **calendar_events** - Event instances
3. **event_asset_mapping** - Event-to-asset relationships
4. **staging_events** - Raw provider data
5. **calendar_provider_state** - Provider reliability + licensing
6. **source_conflict_log** - ADR-013 conflict resolution
7. **unexplained_volatility_flags** - Ghost event detection
8. **ingestion_batches** - ADR-002 audit trail
9. **provider_tos_archive** - TOS/License evidence
10. **leakage_detection_config** - Governed leakage windows
11. **asset_brier_alerts** - Asset-specific Brier alerts

### A.2 Functions

1. **tag_event_proximity()** - Automatic forecast tagging
2. **compute_lvi_adjusted()** - CEO-visible learning metric
3. **classify_brier_degradation()** - UMA learning classification
4. **detect_pre_event_drift()** - Information leakage detection
5. **resolve_source_conflict()** - ADR-013 highest-reliability-wins
6. **normalize_surprise_score()** - Per data-type normalization
7. **triage_ghost_event()** - Classify unexplained volatility cause
8. **verify_provider_tos()** - Check TOS compliance before ingestion
9. **monitor_asset_brier_persistence()** - Daily asset-specific Brier monitoring

---

*Document Hash: IoS-016-G0-2026-01-16-MBB++*
*Constitutional Compliance: VERIFIED*
*CEO Approval: Phase 1 Foundation APPROVED*
