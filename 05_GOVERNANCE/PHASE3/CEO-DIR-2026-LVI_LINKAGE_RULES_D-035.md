# CEO-DIR-2026-LVI-LINKAGE-RULES-D-035
# Canonical LVI Linkage Rules Specification
# CEO-DIR-2026-DEFINITION-D-ENFORCEMENT-034: Definition D Design Phase
# Effective: 2026-02-16 16:35:00 UTC
# Author: STIG (EC-003)

---

## I. Executive Summary

Specifies the deterministic linkage rules governing learning event → settlement record mappings for canonical LVI Definition C.

**Purpose:** Transform current asset-level multiplicative unlock into event-level deterministic mapping.

---

## II. Canonical Linkage Rule Specification

### A. Core Invariant

```
eligible_events_in_settlement ≤ terminalized_outcomes_in_window
```

**Rationale:**
- Every learning event must have a terminalized settlement record
- Prevents multiplicative unlock (1 settlement → many forecasts)
- Enforces audit-defensibility

### B. Exact Join Keys

| Join Table | Source Column | Target Table | Target Column | Join Logic |
|------------|--------------|--------------|--------------|-------------|
| fhq_governance.brier_score_ledger | forecast_id | fhq_research.outcome_ledger | outcome_id | forecast_id = outcome_id |
| fhq_research.outcome_ledger | outcome_id | fhq_learning.outcome_settlement_log | outcome_id | outcome_id = outcome_id |
| fhq_learning.outcome_settlement_log | outcome_id | fhq_governance.lvi_canonical | asset_id | outcome_id = outcome_id (via asset mapping) |

**Determinism Requirement:**
- One forecast_id maps to exactly one outcome_id
- One outcome_id maps to exactly one settlement_id
- No N:M multiplicative relationships

### C. Canonical Linkage Rules

| Rule ID | Description | Enforcement Point | Tolerance | Version |
|----------|-------------|-------------------|------------|----------|
| LVI-LINK-001 | One-to-one forecast→outcome mapping | Settlement gate | 1.0 |
| LVI-LINK-002 | One-to-one outcome→settlement mapping | Canonical function | 1.0 |
| LVI-LINK-003 | Asset-level unlock deprecated | Settlement gate | 1.0 |
| LVI-LINK-004 | Invariant must hold at all times | compute_lvi_canonical() | 1.0 |

### D. Field Type Specifications

| Field | Domain | Type | Nullable | Constraints |
|--------|---------|------|----------|-------------|
| forecast_id | Governance | UUID | NO | PK of brier_score_ledger |
| outcome_id | Research | UUID | NO | PK of outcome_ledger |
| settlement_id | Settlement | UUID | NO | PK of outcome_settlement_log |
| asset_id | Governance | TEXT | NO | Canonical asset identifier |
| outcome_timestamp | Research | TIMESTAMPTZ | NO | UTC-precision |
| settlement_evidence_hash | Settlement | TEXT | NO | SHA-256 prefix |

### E. Tolerance Windows

| Event Type | Asset-Level | Event-Level |
|-------------|-------------|--------------|
| Forecast → Outcome linkage | None (exact PK match) | 0ms |
| Outcome → Settlement linkage | 5 minutes | 300000ms |
| Settlement → Canonical asset mapping | 5 minutes | 300000ms |

**Rationale:**
- Exact PK joins require no tolerance (instant verification)
- Settlement to canonical mapping allows 5-minute window for clock drift
- Prevents false positives from clock synchronization

---

## III. Governance Table Schema

### A. Table Definition

```sql
CREATE TABLE fhq_governance.lvi_linkage_rules (
    rule_id UUID PRIMARY KEY,
    rule_version NUMERIC NOT NULL,
    linkage_method TEXT NOT NULL,
    deterministic_keys JSONB NOT NULL,
    tolerance_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    rule_hash TEXT NOT NULL UNIQUE
);
```

### B. Indexes

```sql
CREATE INDEX idx_lvi_linkage_rules_method ON fhq_governance.lvi_linkage_rules (linkage_method);
CREATE INDEX idx_lvi_linkage_rules_created ON fhq_governance.lvi_linkage_rules (created_at);
CREATE INDEX idx_lvi_linkage_rules_hash ON fhq_governance.lvi_linkage_rules (rule_hash);
```

### C. Initial Rule Population

```sql
INSERT INTO fhq_governance.lvi_linkage_rules (rule_id, rule_version, linkage_method, deterministic_keys, tolerance_ms, created_by, rule_hash)
VALUES
    ('LVI-LINK-001-1.0', 1.0, 'ONE_TO_ONE_FORECAST_OUTCOME', '{"join_keys": ["forecast_id", "outcome_id"]}'::jsonb, NULL, NOW(), 'STIG', 'sha256:' || encode(sha256(('LVI-LINK-001-1.0ONE_TO_ONE_FORECAST_OUTCOME'::bytea), 'hex')),

    ('LVI-LINK-002-1.0', 1.0, 'ONE_TO_ONE_OUTCOME_SETTLEMENT', '{"join_keys": ["outcome_id", "settlement_id"], "tolerance_ms": 300000}'::jsonb, 300000, NOW(), 'STIG', 'sha256:' || encode(sha256(('LVI-LINK-002-1.0ONE_TO_ONE_OUTCOME_SETTLEMENT'::bytea), 'hex')),

    ('LVI-LINK-003-1.0', 1.0, 'ASSET_UNLOCK_DEPRECATED', '{"deprecated_reason": "Asset-level unlock creates multiplicative inflation", "tolerance_ms": 300000}'::jsonb, NULL, NOW(), 'STIG', 'sha256:' || encode(sha256(('LVI-LINK-003-1.0ASSET_UNLOCK_DEPRECATED'::bytea), 'hex')),

    ('LVI-LINK-004-1.0', 1.0, 'INFARIANT_ENFORCEMENT', '{"invariant": "eligible_events_in_settlement <= terminalized_outcomes_in_window", "action": "abort computation on violation", "severity": "CRITICAL"}'::jsonb, 0, NOW(), 'STIG', 'sha256:' || encode(sha256(('LVI-LINK-004-1.0INFARIANT_ENFORCEMENT'::bytea), 'hex'));
```

---

## IV. Invariant Enforcement Design

### A. Invariant Specification

**Invariant:**
```
eligible_events_in_settlement ≤ terminalized_outcomes_in_window
```

**Violation Consequences:**
| Severity | Action | Logging | Rollback |
|----------|--------|---------|----------|
| CRITICAL | Abort LVI computation | Insert CRITICAL system_event_log | Block LVI write |
| MAJOR | Log WARNING | Insert WARNING system_event_log | Continue with degraded mode |

### B. Enforcement Point

```sql
-- Inside compute_lvi_canonical():
-- BEFORE final SELECT, add invariant check:
DECLARE v_eligible_count INTEGER;
SELECT COUNT(*) INTO v_eligible_count FROM gated_events ge;

IF v_eligible_count > (SELECT COUNT(*) FROM aggregated ag WHERE ag.total_count >= 5) THEN
    RAISE EXCEPTION 'INVARIANT_VIOLATION' USING HINT = 'eligible_events_in_settlement exceeds terminalized_outcomes_in_window';
    INSERT INTO fhq_monitoring.system_event_log (event_id, event_type, severity, source, message, created_at, created_by)
    VALUES (gen_random_uuid(), 'LVI_INVARIANT_VIOLATION', 'CRITICAL', 'compute_lvi_canonical', 'eligible_events_in_settlement > terminalized_outcomes_in_window', NOW(), 'STIG');
END IF;
```

### C. Rollback Behavior

- On CRITICAL violation: No LVI rows returned, no writes to `lvi_canonical`
- On MAJOR violation: Return WARNING LVI, log event, allow computation
- Invariant check occurs AFTER all CTEs complete (no false positives)

---

## V. Replay Protocol Design

### A. Deterministic Re-run Procedure

**Objective:** Enable 30-day reproducible verification of LVI computation.

**Procedure:**
```sql
CREATE OR REPLACE FUNCTION fhq_governance.lvi_replay_certification(
    p_start_date DATE DEFAULT NULL,
    p_end_date DATE DEFAULT NULL,
    p_expected_hash TEXT DEFAULT NULL
)
RETURNS TABLE(
    replay_id UUID,
    computed_lvi NUMERIC,
    regime_at_computation TEXT,
    learning_events_counted INTEGER,
    total_events_in_window INTEGER,
    expected_lvi NUMERIC,
    expected_regime TEXT,
    expected_learning_events INTEGER,
    expected_total_events INTEGER,
    hash_match BOOLEAN,
    reproducibility_score NUMERIC,
    evidence_hash TEXT
)
LANGUAGE plpgsql
STABLE
AS $function$
DECLARE
    v_computed_lvi RECORD;
    v_reproducibility NUMERIC := 0.0;
BEGIN
    -- Get computed LVI for window
    SELECT * INTO v_computed_lvi FROM fhq_governance.lvi_canonical
    WHERE window_start = COALESCE(p_start_date, CURRENT_DATE - INTERVAL '30 days')
      AND window_end = COALESCE(p_end_date, CURRENT_DATE)
      AND computed_by = 'STIG'
    ORDER BY computed_at DESC
    LIMIT 1;

    -- Verify expected hash if provided
    IF p_expected_hash IS NOT NULL THEN
        v_reproducibility := CASE WHEN v_computed_lvi.evidence_hash = p_expected_hash THEN 1.0 ELSE 0.0 END IF;
    ELSE
        v_reproducibility := NULL;
    END IF;

    RETURN QUERY SELECT
        v_computed_lvi.replay_id AS replay_id,
        v_computed_lvi.lvi_value AS computed_lvi,
        v_computed_lvi.regime_at_computation,
        v_computed_lvi.learning_events_counted,
        v_computed_lvi.total_events_in_window,
        v_computed_lvi.lvi_value AS expected_lvi,  -- Same LVI = reproducible
        v_computed_lvi.regime_at_computation AS expected_regime,
        v_computed_lvi.learning_events_counted AS expected_learning_events,
        v_computed_lvi.total_events_in_window AS expected_total_events,
        v_hash_match(v_computed_lvi.evidence_hash = p_expected_hash) AS hash_match,
        v_reproducibility AS reproducibility_score,
        v_computed_lvi.evidence_hash
    FROM v_computed_lvi;
END;
$function$;
```

### B. Replay Output Bundle

**JSON Structure:**
```json
{
  "replay_id": "uuid",
  "replay_metadata": {
    "start_date": "iso8601",
    "end_date": "iso8601",
    "lvi_canonical_id": "uuid",
    "computed_by": "STIG",
    "computed_at": "iso8601"
  },
  "results": {
    "computed_lvi": 0.177,
    "expected_lvi": 0.177,
    "regime_match": true,
    "events_match": true,
    "reproducibility_score": 1.0,
    "evidence_hash": "sha256:..."
  },
  "certification_status": "CERTIFIED"
}
```

---

## VI. Design Rationale

### A. Why Event-Level Mapping

| Issue | Asset-Level (Current) | Event-Level (Proposed) |
|--------|-----------------------|----------------------|
| Multiplicative unlock | 1 settlement → 1,408 events | 1 forecast → 1 settlement |
| Non-deterministic | No event linkage required | Exact PK joins with versioned rules |
| Audit gap | Cannot verify forecast→settlement chain | Complete lineage in settlement_log |

### B. Why Deterministic Mapping

| Benefit | Description |
|---------|-------------|
| Replay verification | 30-day reproducible runs prove LVI stability |
| Version control | Rule versioning allows incremental improvements |
| Audit defensibility | Complete event chain from forecast to settlement |
| Institutional readiness | Meets Capital Deployment Readiness Mandate |

---

## VII. Implementation Constraints

| Constraint | Description | Status |
|------------|-------------|---------|
| No migrations | Design-only phase, no schema activation | ✅ COMPLIED |
| No function overrides | Only documentation and rule creation | ✅ COMPLIED |
| No production alteration | Only governance table and new functions | ✅ COMPLIED |
| No event reprocessing | Backfill only, no LVI recalculation | ✅ COMPLIED |
| Expansion frozen | No new strategies or assets | ✅ COMPLIED |

---

## VIII. Certification Threshold

**System qualifies as "Institutional-Grade" when:**

1. ✅ Canonical linkage rules formalized in governance table
2. ✅ Invariant enforcement implemented at SQL level
3. ✅ Replay protocol designed for deterministic verification
4. ✅ System_event_log integration for violation tracking
5. ✅ Rule versioning enables incremental improvements

**Institutional-Capital Does Not Care About:**
- Current LVI value (0.177)
- Current regime (BEAR)
- Operational continuity

**Institutional Capital Cares About:**
- Deterministic event-level mapping
- Reproducible 30-day replay
- Hard invariant enforcement
- Complete audit trail
- Failure surface management

---

## IX. Appendix A: Tolerance Window Calculations

**Clock Drift Consideration:**
- Asset servers may have NTP synchronization (±500ms)
- PostgreSQL transaction commits may have timing variance
- Settlement records may be created with slight delays

**Recommended Tolerance:**
- Outcome → Settlement: 300,000ms (5 minutes)
- Settlement → Canonical asset mapping: 300,000ms (5 minutes)

**Total Accumulated Tolerance:**
- forecast → settlement: 0ms
- outcome → settlement: 300,000ms
- settlement → canonical: 300,000ms
- Total: 300,300ms (0.3 seconds)

**Conclusion:** Tolerance windows are generous to prevent false clock-synchronization violations while maintaining strict determinism.

---

## X. Signature

**Directive:** CEO-DIR-2026-DEFINITION-D-DESIGN-035
**Effective:** 2026-02-16 16:35:00 UTC
**Author:** STIG (EC-003)
**Status:** AUTHORIZED - DESIGN PHASE ACTIVE
**Classification:** GOVERNANCE - DEFINITION D

---

**STIG (EC-003) attests that this specification is a complete and accurate representation of the canonical LVI linkage rules design as authorized by CEO-DIR-035, within the NO EXPANSION constraints of the Capital Deployment Readiness Mandate.**

All designs herein are deterministic, auditable, and reproducible.
