IoS-016 — Economic Calendar & Temporal Governance

Institutional Operating Standard (IoS)
System: FjordHQ Market System / ACI
Classification: GOVERNANCE-CRITICAL (MBB++)
Status: G0 SUBMITTED — G1 IN PROGRESS
Owner: LINE (Temporal Governance)
Operator: CEIO (Ingestion & Coverage)
Auditor: VEGA
Version: 1.0

1. Purpose

IoS-016 defines the institutional standard for economic calendar awareness and temporal governance within FjordHQ ACI.

Its purpose is to ensure that the system:

Understands when the world is about to speak

Distinguishes model error from event-driven volatility

Learns only from signal, never from known noise

Remains audit-defensible, cost-safe, and execution-isolated

This IoS introduces calendar intelligence as context, not as a trading signal.

2. Scope

IoS-016 applies to all assets tracked by FjordHQ, including:

Macro indicators (rates, inflation, employment, GDP)

Equities and equity indices

Fixed income and rates instruments

Crypto assets and protocols

Cross-asset structural events

It governs:

Calendar ingestion

Event classification

Temporal normalization

Event-to-asset mapping

Learning annotation and attribution

It does not govern execution, forecasting logic, or capital allocation.

3. Constitutional Alignment

IoS-016 is explicitly aligned with the FjordHQ Constitution.

Key mappings:

ADR-012 (Economic Safety): Free-first ingestion, API waterfall, quota controls

ADR-013 (One-True-Source): Single canonical calendar with conflict resolution

ADR-011 (Fortress Testing): Deterministic behavior under audit

ADR-014 (Sub-Executive Authority): LINE owns time, CEIO operates ingestion

ADR-016 (DEFCON): Calendar respects circuit breakers

ADR-020 (ACI): Calendar accelerates learning, not action

Calendar data is explicitly non-canonical to price truth.

4. Design Principles
4.1 Context, Not Signal

Calendar data:

MAY annotate forecasts

MAY explain learning outcomes

MAY suppress false-negative learning

MUST NEVER trigger trades or forecasts

4.2 Temporal Rigor

All timestamps stored in UTC

Timezone reconciliation is mandatory

Daylight Savings errors are Class B violations

Precision must be explicitly encoded (time_precision)

4.3 Determinism Over Convenience

Conflicting data is resolved, never averaged

Every canonical event must be explainable post-hoc

4.4 Free-First Economics

Public, free sources prioritized

Paid sources optional, never required

No single vendor dependency

5. Event Taxonomy

All calendar events are classified via a canonical registry.

5.1 Event Categories

MACRO_POLICY

MACRO_DATA

EQUITY_CORPORATE

EQUITY_STRUCTURAL

CRYPTO_NATIVE

CROSS_ASSET

5.2 Impact Rank

Each event type is assigned an impact_rank from 1 to 5:

1 — Low relevance noise

3 — Medium market relevance

5 — High-impact, regime-moving events

Impact rank is used for learning attribution, not prediction.

6. Surprise & Information Shock

For applicable events, the calendar stores:

consensus_estimate

actual_value

surprise_score

Surprise scores MUST be normalized by historical variance of that event type.

Purpose:

Distinguish expected volatility from information shock

Prevent UMA from excusing poor performance on unsurprising events

7. Information Leakage Detection

Markets often move before official timestamps.

IoS-016 mandates:

Pre-event drift analysis windows (impact-rank dependent)

Detection of Brier degradation before EVENT_ADJACENT window

This enables:

Identification of information leakage

Improved confidence dampening

Early warning of missing data sources

8. Ghost Events

If market behavior changes without known events, the system must not hallucinate explanations.

IoS-016 introduces Ghost Event Detection.

Ghost events are classified as:

COVERAGE_GAP

TIMESTAMP_DEFECT

MAPPING_DEFECT

TRUE_GHOST

These flags create a feedback loop to CEIO for coverage expansion.

9. Database Architecture

All calendar data lives in the dedicated schema:

fhq_calendar

Key tables include:

event_type_registry

calendar_events

event_asset_mapping

calendar_provider_state

source_conflict_log

unexplained_volatility_flags

ingestion_batches

Calendar data flows:

Provider → staging_events → canonical calendar_events → learning annotation
10. UMA Integration

UMA is authorized to:

Explain Brier degradation

Compute event-adjusted learning metrics

Separate drift from noise

Surface repeated failures near event classes

UMA is explicitly not authorized to:

Suppress learning permanently

Override DEFCON

Justify persistent underperformance

Key metric introduced:

LVI_adjusted

Which weights learning in clean windows higher than event-adjacent periods.

11. Reporting Requirements

Daily and weekly reports must include:

Event-adjacent vs clean-window performance

Surprise-context annotations

Explicit unexplained volatility flags

Silence is acceptable. Unexplained error is not.

12. Governance Gates

IoS-016 follows full G0–G4 lifecycle.

G0: Architecture & ownership approval

G1: Technical validation

G2: Governance & audit review

G3: Operational stress test

G4: CEO activation

No gate may be skipped.

13. Audit & Defensibility

Every calendar event must be traceable to:

Source provider

Ingestion batch

Raw response hash

Canonical record hash

VEGA must be able to attest:

“This system knew what was scheduled, when it was scheduled, and why it mattered.”

14. Trading Calendar Integration (CEO-DIR-2026-091)

IoS-016 now includes mandatory trading calendar awareness as a first-class dependency.

### 14.1 Database Integration

IoS-016 consumes calendar truth via the `fhq_meta.ios016_calendar_truth` view:

| Field | Description |
|-------|-------------|
| market | Calendar identifier (US_EQUITY) |
| date | Calendar date |
| status | OPEN or CLOSED |
| reason | TRADING_DAY, WEEKEND, HOLIDAY, EARLY_CLOSE |
| provenance | LIBRARY (verified) or PROJECTED (extrapolated) |
| verified_at | Last verification timestamp |
| is_tentative | true if PROJECTED |

### 14.2 Daily Report Requirements

Every daily report MUST include:

```
Calendar Governance:
- Market open tomorrow? YES/NO (reason)
- Next 5 trading days: [dates]
- Projection window: N projected days in next 30 days
```

### 14.3 Provenance Rules

| Provenance | Trading Authority |
|------------|-------------------|
| LIBRARY | Full authority |
| PROJECTED | Display only - No trading decisions |

### 14.4 Crypto Epoch Boundary

Crypto uses 00:00:00 UTC as canonical daily boundary:

```sql
SELECT fhq_meta.crypto_epoch_boundary(timestamp);
```

Display as: `CRYPTO_EPOCH (00:00 UTC boundary)`

### 14.5 Forward Coverage Guarantee

- Minimum: 720 days (24 months) forward
- RED alert if within 30 days of threshold
- Monthly daemon extends coverage automatically

---

15. Failure Modes

IoS-016 explicitly guards against:

False-negative learning

Misclassified regime transitions

Inflated Brier degradation

Silent timezone drift

Vendor lock-in

Any violation is escalated per ADR severity rules.

15. Closing Principle

A system that learns without temporal context will always punish itself for reality.

IoS-016 ensures FjordHQ ACI learns with the world, not against it.

End of IoS-016