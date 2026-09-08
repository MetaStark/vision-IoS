# CEO-DIR-2026-DATABASE-VERIFICATION: EC-022 End-to-End Wiring Audit

**Date:** 2026-01-24 14:45 CET
**Requested by:** CEO
**Verified by:** STIG (EC-003)
**Database:** PostgreSQL 17.6 @ 127.0.0.1:54322

---

## EXECUTIVE SUMMARY

**VERDICT: NO — EC-022 is NOT fully wired end-to-end.**

The database schema and functions exist, but **no process executes them**. The test will not self-monitor, self-escalate, or self-resolve without manual intervention.

---

## 1. CANONICAL TEST REGISTRATION (Source of Truth)

### Status: VERIFIED

**Query:**
```sql
SELECT test_id, test_code, test_name, owning_agent, monitoring_agent_ec,
       beneficiary_system, status, start_ts, end_ts, required_days
FROM fhq_calendar.canonical_test_events
WHERE test_code LIKE '%EC022%';
```

**Result:**
| Field | Value |
|-------|-------|
| test_id | `fadbbc8d-c5c4-4da7-a379-4fbe890a8010` |
| test_code | `TEST-EC022-OBS-001` |
| test_name | EC-022 Reward Logic Observation Window |
| display_name | EC-022 — Reward Logic Freeze (Context Lift Validation) |
| owning_agent | EC-022 |
| monitoring_agent_ec | EC-022 |
| beneficiary_system | EC-022 (Reward Architect) |
| status | ACTIVE |
| start_ts | 2026-01-24 00:00:00+01 (IMMUTABLE) |
| end_ts | 2026-02-23 00:00:00+01 (IMMUTABLE) |
| required_days | 30 |

**Uniqueness Check:**
```sql
SELECT COUNT(*) as total, COUNT(DISTINCT test_id) as unique_ids
FROM fhq_calendar.canonical_test_events WHERE test_code LIKE '%EC022%';
-- Result: total=1, unique_ids=1
```

**Source of Truth Table:** `fhq_calendar.canonical_test_events`

**FK Linkage Verified:**
```sql
SELECT canonical_test_id FROM fhq_learning.observation_window
WHERE window_name LIKE '%EC-022%';
-- Result: fadbbc8d-c5c4-4da7-a379-4fbe890a8010 (linked)
```

---

## 2. MONITORING & ESCALATION WIRING

### Status: PARTIAL — CRITICAL GAP

**Database Functions Exist:**

| Function | Schema | Purpose |
|----------|--------|---------|
| `check_escalation_conditions(uuid)` | fhq_calendar | Evaluates sample deficit, Brier decline, overdue |
| `update_escalation_state()` | fhq_calendar | Updates escalation_state column |
| `compute_test_progress(uuid)` | fhq_calendar | Returns days_elapsed, days_remaining, is_overdue |

**Current Escalation State:**
```sql
SELECT escalation_state, ceo_action_required, recommended_actions
FROM fhq_calendar.canonical_test_events WHERE test_code = 'TEST-EC022-OBS-001';
```
| Field | Value |
|-------|-------|
| escalation_state | NONE |
| ceo_action_required | false |
| recommended_actions | [] |

### GAP: No Process Calls These Functions

**Evidence:**
```bash
# Grep all daemon files for canonical_test or escalation references
grep -r "canonical_test\|escalation_state\|ceo_action_required" 03_FUNCTIONS/*daemon*.py
# Result: 0 matches
```

**pg_cron Status:**
```sql
SELECT * FROM cron.job;
-- Error: relation "cron.job" does not exist
```
pg_cron is **NOT INSTALLED**.

**Impact:** Escalation logic is defined but will **never execute automatically**.

---

## 3. RUNBOOK & DAILY REPORT COUPLING

### Status: PARTIAL — GAP EXISTS

**Table Exists:**
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'test_runbook_entries';
```
- entry_id, canonical_test_id, entry_date, runbook_file_path, daily_report_file_path, entry_content, db_verified, created_at

**Current Entries for EC-022:**
```sql
SELECT COUNT(*) FROM fhq_calendar.test_runbook_entries
WHERE canonical_test_id = 'fadbbc8d-c5c4-4da7-a379-4fbe890a8010';
-- Result: 0 rows
```

### GAP: No Day 0 Entry, No Daily Generation Process

The `resolve_test_window()` function writes a runbook entry at test END, but **nothing writes during the ACTIVE period**.

**Expected:** Daily machine-readable entry for each day the test is ACTIVE.
**Actual:** 0 entries exist.

---

## 4. METRIC INGESTION & EVALUATION READINESS

### Status: PARTIAL — GAPS IN DATA SOURCES

**Baseline Definition (Stored):**
```json
{
  "lvi": 0.0389,
  "brier_score": "baseline from Day 23",
  "context_lift": 0,
  "tier1_death_rate": 0.5
}
```

**Target Metrics (Stored):**
```json
{
  "macro_regimes_tested": 2,
  "drawdown_phases_tested": 1,
  "context_lift_vs_baseline": 0.05,
  "ios010_bridge_operational": true
}
```

**Success Criteria (Stored):**
```json
{
  "macro_regimes_passed": 2,
  "drawdown_phase_passed": 1,
  "no_negative_brier_drift_7d": true,
  "context_confidence_shows_lift": true
}
```

**Failure Criteria (Stored):**
```json
{
  "ios010_bridge_failed": true,
  "brier_drift_sustained": true,
  "context_lift_negative": true
}
```

### Signal Source Status

| Signal | Table | Row Count |
|--------|-------|-----------|
| LVI | `fhq_learning.learning_velocity_metrics` | **0 (EMPTY)** |
| Brier Score | `fhq_learning.ldow_cycle_metrics` | Available |
| Context Lift | `fhq_learning.v_context_brier_impact` | **0 (EMPTY)** |
| IoS-010 Bridge | `fhq_learning.v_addendum_a_readiness` | Available |

### GAP: No Wiring to Compare Current vs Baseline

Even if data existed, **no process reads these tables and compares against the test's success/failure criteria**.

---

## 5. END-OF-WINDOW RESOLUTION

### Status: PARTIAL — NO AUTOMATIC TRIGGER

**Function Exists:**
```sql
fhq_calendar.resolve_test_window(
    p_test_id uuid,
    p_verdict text,  -- 'SUCCESS', 'FAILURE', 'INCONCLUSIVE'
    p_measured_vs_expected jsonb,
    p_trigger_promotion boolean DEFAULT false
)
```

**Function Will:**
1. Set `status = 'COMPLETED'`
2. Set `verdict = p_verdict`
3. Set `escalation_state = 'RESOLVED'`
4. Insert entry to `test_runbook_entries`
5. Set `promotion_sop_triggered = true` if SUCCESS

### GAP: No Scheduled Trigger at end_ts

- pg_cron: NOT INSTALLED
- No time-based trigger on table
- No daemon checks for `NOW() > end_ts AND verdict = 'PENDING'`

**Impact:** At end_ts + ε, **nothing happens**. Manual intervention required.

---

## 6. EXPLICIT CONFIRMATION

# NO — THE FOLLOWING GAPS REMAIN

| Gap ID | Component | Description | Impact |
|--------|-----------|-------------|--------|
| **G1** | Monitoring Daemon | No process calls `check_escalation_conditions()` | Escalation never triggers |
| **G2** | Progress Update | No process calls `compute_test_progress()` | `days_elapsed` never updates |
| **G3** | Daily Runbook | No daily entry generation for ACTIVE tests | CEO has no daily state capture |
| **G4** | LVI Data | `learning_velocity_metrics` is EMPTY | Cannot compare LVI vs baseline |
| **G5** | Context Lift | `v_context_brier_impact` is EMPTY | Cannot measure context lift |
| **G6** | Auto-Resolution | No trigger for `resolve_test_window()` at end_ts | Test will not auto-resolve |
| **G7** | Scheduling | pg_cron NOT INSTALLED | No in-database scheduling |

---

## REQUIRED ACTIONS TO ACHIEVE FULL WIRING

### Option A: Create New Daemon (Recommended)

Create `canonical_test_monitor_daemon.py`:

```
Schedule: Daily at 06:00 CET (before market open)

For each ACTIVE test in canonical_test_events:
  1. Call compute_test_progress() → update days_elapsed, days_remaining
  2. Call check_escalation_conditions() → if breach, update escalation_state
  3. Insert daily entry to test_runbook_entries
  4. If NOW() > end_ts AND verdict = 'PENDING':
     - Compute measured vs expected from signal tables
     - Call resolve_test_window() with computed verdict
  5. If ceo_action_required = true:
     - Insert alert to ceo_calendar_alerts
```

### Option B: Extend Existing Daemon

Add canonical test monitoring to `calendar_integrity_daemon.py` (already runs daily at 05:00).

### Option C: Install pg_cron

```sql
CREATE EXTENSION pg_cron;
SELECT cron.schedule('canonical-test-monitor', '0 6 * * *',
  $$SELECT fhq_calendar.run_daily_test_monitoring()$$);
```

Requires PostgreSQL restart and `shared_preload_libraries` config.

---

## CEO DECISION REQUIRED

| Decision | Options |
|----------|---------|
| **D1: Monitoring Approach** | A) New daemon / B) Extend calendar_integrity / C) pg_cron |
| **D2: LVI Data Gap** | Wire existing LVI calculator to `learning_velocity_metrics`? |
| **D3: Context Lift Gap** | Defer until IoS-010 Bridge operational? |
| **D4: Timeline** | Implement before Day 1 of test? (Currently Day 0) |

---

## EVIDENCE HASHES

| Query | Result Hash (SHA256) |
|-------|---------------------|
| Canonical test exists | `fadbbc8d-c5c4-4da7-a379-4fbe890a8010` |
| Uniqueness check | `1 entry, 1 unique` |
| Runbook entries | `0 rows` |
| LVI metrics | `0 rows` |
| Context lift | `0 rows` |

---

**Report Generated:** 2026-01-24 14:45 CET
**Classification:** GOVERNANCE-CRITICAL
**Next Action:** CEO decision on Options A/B/C

*— STIG (EC-003)*
