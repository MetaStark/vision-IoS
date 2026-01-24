# Canonical Test Orchestrator v1 — Design Document

**Date:** 2026-01-24
**Author:** STIG (EC-003)
**Directive:** CEO Authorization — Canonical Test Orchestrator
**Classification:** GOVERNANCE-CRITICAL

---

## 1. PROCESS IDENTITY

| Attribute | Value |
|-----------|-------|
| **Process Name** | `canonical_test_orchestrator_daemon.py` |
| **Location** | `C:\fhq-market-system\vision-ios\03_FUNCTIONS\` |
| **Schedule** | Daily at 06:00 CET (before market open) |
| **Ownership** | EC-003 (STIG) — Technical Execution |
| **Monitoring** | VEGA — Governance Oversight |

---

## 2. ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│              CANONICAL TEST ORCHESTRATOR                     │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   PHASE 1    │───▶│   PHASE 2    │───▶│   PHASE 3    │  │
│  │   DISCOVER   │    │   EVALUATE   │    │   EXECUTE    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │           │
│         ▼                   ▼                   ▼           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Load ACTIVE  │    │ Check Each:  │    │ For Each:    │  │
│  │ tests from   │    │ - Progress   │    │ - Escalate   │  │
│  │ canonical_   │    │ - Metrics    │    │ - Resolve    │  │
│  │ test_events  │    │ - Criteria   │    │ - Log        │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    FAIL-CLOSED GATE                   │   │
│  │  If any test has incomplete definition → HALT + ALERT │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │         OUTPUTS               │
              │  • test_runbook_entries       │
              │  • ceo_calendar_alerts        │
              │  • escalation_state updates   │
              │  • verdict + promotion SOP    │
              │  • RUNBOOK file append        │
              │  • Daily Report append        │
              └───────────────────────────────┘
```

---

## 3. EXECUTION FLOW

### Phase 1: Discovery (Test-Agnostic)

```sql
SELECT * FROM fhq_calendar.canonical_test_events
WHERE status = 'ACTIVE'
ORDER BY start_ts ASC;
```

No hardcoded test codes. All ACTIVE tests processed.

### Phase 2: Evaluation (Per Test)

For each test:

1. **Progress Computation**
   ```sql
   SELECT * FROM fhq_calendar.compute_test_progress(test_id);
   ```
   Updates: `days_elapsed`, `days_remaining`, `is_overdue`

2. **Metric Collection**
   - Read `baseline_definition` from test
   - Query current values from signal tables
   - Compare against `target_metrics`

3. **Escalation Check**
   ```sql
   SELECT * FROM fhq_calendar.check_escalation_conditions(test_id);
   ```
   Returns: `should_escalate`, `escalation_reason`, `recommended_actions`

4. **End-of-Window Detection**
   ```sql
   IF NOW() > end_ts AND verdict = 'PENDING' THEN
       -- Trigger resolution
   END IF;
   ```

### Phase 3: Execution (Actions)

| Condition | Action |
|-----------|--------|
| Progress changed | UPDATE `days_elapsed`, `days_remaining` |
| Escalation triggered | SET `escalation_state`, `ceo_action_required = true` |
| Escalation triggered | INSERT to `ceo_calendar_alerts` |
| Test overdue | Call `resolve_test_window()` with computed verdict |
| Any state change | INSERT to `test_runbook_entries` |
| Any state change | Append to RUNBOOK file |
| Any state change | Append to Daily Report file |

---

## 4. FAIL-CLOSED GUARDRAILS

The orchestrator **HALTS and ALERTS** if:

| Condition | Response |
|-----------|----------|
| Test missing `start_ts` or `end_ts` | HALT — "Incomplete test definition" |
| Test missing `success_criteria` | HALT — "No success criteria defined" |
| Test missing `failure_criteria` | HALT — "No failure criteria defined" |
| Metrics unavailable for comparison | WARN — "Metrics pending, evaluation deferred" |
| Escalation path undefined | HALT — "No escalation path" |
| Database connection failure | HALT — "Database unreachable" |

All HALT conditions:
1. Set `escalation_state = 'SYSTEM_ERROR'`
2. Set `ceo_action_required = true`
3. Insert CRITICAL alert to `ceo_calendar_alerts`
4. Log to evidence file
5. Exit with non-zero status

---

## 5. GAP CLOSURE MAPPING

| Gap ID | Gap Description | Closure Method |
|--------|-----------------|----------------|
| **G1** | No process calls `check_escalation_conditions()` | Orchestrator Phase 2 calls it for every ACTIVE test |
| **G2** | No process calls `compute_test_progress()` | Orchestrator Phase 2 calls it for every ACTIVE test |
| **G3** | No daily RUNBOOK entry generation | Orchestrator Phase 3 writes to `test_runbook_entries` AND appends to file |
| **G4** | `learning_velocity_metrics` is EMPTY | Orchestrator logs WARNING, evaluation deferred until data exists |
| **G5** | `v_context_brier_impact` is EMPTY | Orchestrator logs WARNING, evaluation deferred until data exists |
| **G6** | No trigger for `resolve_test_window()` at end_ts | Orchestrator Phase 2 detects `NOW() > end_ts`, Phase 3 calls resolution |
| **G7** | pg_cron NOT INSTALLED | Orchestrator runs as Python daemon, scheduled via Windows Task Scheduler |

---

## 6. METRIC SIGNAL WIRING

### EC-022 Specific (But Configured in Test Definition)

| Metric | Source Table | Column |
|--------|--------------|--------|
| LVI | `fhq_learning.learning_velocity_metrics` | `death_rate_pct` |
| Brier Score | `fhq_learning.ldow_cycle_metrics` | `brier_score` |
| Context Lift | `fhq_learning.v_context_brier_impact` | `brier_delta` |
| IoS-010 Bridge | `fhq_learning.v_addendum_a_readiness` | `ios010_bridge_ready` |
| Tier-1 Death Rate | `fhq_learning.v_tier1_calibration_status` | `death_rate` |

### Generic Signal Resolution

Each test's `baseline_definition` and `target_metrics` contain metric keys.
Orchestrator uses a **signal registry** to map keys to tables:

```sql
-- Signal registry (to be created)
CREATE TABLE fhq_calendar.test_signal_registry (
    signal_key TEXT PRIMARY KEY,
    source_schema TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_column TEXT NOT NULL,
    aggregation TEXT DEFAULT 'LATEST'  -- LATEST, AVG_7D, SUM, etc.
);
```

---

## 7. OUTPUT ARTIFACTS

### 7.1 Database Tables

| Table | Purpose |
|-------|---------|
| `fhq_calendar.canonical_test_events` | Progress + escalation state updates |
| `fhq_calendar.test_runbook_entries` | Machine-readable daily entries |
| `fhq_calendar.ceo_calendar_alerts` | CEO escalation alerts |

### 7.2 File Outputs

| File | Path Pattern |
|------|--------------|
| RUNBOOK | `C:\fhq-market-system\vision-ios\12_DAILY_REPORTS\DAY{N}_RUNBOOK_{YYYYMMDD}.md` |
| Daily Report | Same as RUNBOOK (appended section) |
| Evidence | `C:\fhq-market-system\vision-ios\03_FUNCTIONS\evidence\ORCHESTRATOR_{test_code}_{YYYYMMDD}.json` |

### 7.3 RUNBOOK Entry Format

```markdown
## CANONICAL TEST: {test_name}

| Field | Value |
|-------|-------|
| Test Code | {test_code} |
| Day | {days_elapsed} of {required_days} |
| Status | {status} |
| Escalation | {escalation_state} |
| CEO Action Required | {ceo_action_required} |

### Metrics Snapshot
- LVI: {current_lvi} (baseline: {baseline_lvi})
- Brier: {current_brier} (baseline: {baseline_brier})
- Context Lift: {current_lift} (target: {target_lift})

### Verdict
{verdict if resolved, else "PENDING"}
```

---

## 8. SCHEDULE & TRIGGERS

### Primary Schedule

| Trigger | Time | Action |
|---------|------|--------|
| Daily Run | 06:00 CET | Full evaluation of all ACTIVE tests |

### Future Enhancement (Checkpoint Triggers)

| Trigger | Condition | Action |
|---------|-----------|--------|
| Mid-test checkpoint | `NOW() = mid_test_checkpoint` | Force evaluation + CEO alert |
| End-of-window | `NOW() > end_ts` | Force resolution |
| Metric breach | Real-time (future) | Immediate escalation |

For v1: Daily run only. Checkpoint triggers in v2.

---

## 9. IMPLEMENTATION PLAN

| Step | Action | Status |
|------|--------|--------|
| 1 | Create `test_signal_registry` table | PENDING |
| 2 | Populate signal mappings for EC-022 metrics | PENDING |
| 3 | Create `canonical_test_orchestrator_daemon.py` | PENDING |
| 4 | Test with EC-022 (Day 1 run) | PENDING |
| 5 | Schedule via Windows Task Scheduler | PENDING |
| 6 | Verify RUNBOOK + Daily Report output | PENDING |

---

## 10. CONFIRMATION

### Process Identity
- **Name:** `canonical_test_orchestrator_daemon.py`
- **Schedule:** Daily at 06:00 CET
- **Owner:** EC-003 (STIG)

### Gap Closure
All 7 gaps (G1-G7) have defined closure methods in Section 5.

### Test-Agnostic Design
- No hardcoded test codes
- All ACTIVE tests processed equally
- EC-022 is first test, not special case

---

**Awaiting CEO approval to proceed with implementation.**

*— STIG (EC-003)*
