# IoS-016 Operational Runbook

**Dato:** 2026-01-23
**Direktiv:** CEO-DIR-2026-023 Order 5
**Status:** DEFINED
**Computed By:** STIG (EC-003)

---

## OVERVIEW

IoS-016 is the Economic Calendar integration that enables systematic learning from market events. This runbook defines the operational procedures for the complete experiment lifecycle.

**Migration:** `04_DATABASE/MIGRATIONS/333_ios016_experiment_ledgers.sql`

---

## EXPERIMENT LIFECYCLE

```
T-4h: Event Approaches
  ↓
  → Hypothesis Pre-Commitment (MANDATORY)
  → Hypothesis becomes immutable at event_time
  ↓
T-0: Event Releases
  ↓
  → Hypothesis locked
  → Decision recorded (TRADE/NO_TRADE/WAIT)
  ↓
T+24h: Outcome Recording Deadline
  ↓
  → Actual vs Expected recorded
  → Learning verdict assigned
  → LVI updated
  ↓
T+24h+: Alert if Overdue
  ↓
  → CRITICAL alert generated
  → CEO notification via Control Room
```

---

## LEDGER TABLES

### 1. hypothesis_ledger
Pre-event hypothesis commitments.

| Column | Type | Purpose |
|--------|------|---------|
| hypothesis_id | UUID | Primary key |
| event_id | UUID | Link to calendar_events |
| hypothesis_text | TEXT | The hypothesis statement |
| expected_direction | TEXT | BULLISH/BEARISH/NEUTRAL |
| expected_magnitude | TEXT | HIGH/MEDIUM/LOW |
| confidence_pre_event | NUMERIC | 0-1 confidence |
| immutable_after | TIMESTAMPTZ | Event time (no edits after) |

**Immutability Constraint:** Trigger prevents updates after `immutable_after` timestamp.

### 2. decision_experiment_ledger
Links decisions to hypotheses.

| Column | Type | Purpose |
|--------|------|---------|
| experiment_id | UUID | Primary key |
| hypothesis_id | UUID | Link to hypothesis |
| decision_pack_id | UUID | Link to decision_packs |
| decision_type | TEXT | TRADE/NO_TRADE/WAIT |
| no_trade_reason | TEXT | Required if NO_TRADE |
| trade_direction | TEXT | LONG/SHORT if TRADE |

### 3. expectation_outcome_ledger
Records actual vs expected.

| Column | Type | Purpose |
|--------|------|---------|
| outcome_id | UUID | Primary key |
| hypothesis_id | UUID | Link to hypothesis |
| actual_direction | TEXT | BULLISH/BEARISH/NEUTRAL |
| actual_magnitude | TEXT | HIGH/MEDIUM/LOW |
| surprise_score | NUMERIC | Normalized surprise |
| learning_verdict | TEXT | VALIDATED/WEAKENED/FALSIFIED |
| recorded_within_24h | BOOLEAN | Met T+24h deadline |

---

## OPERATIONAL PROCEDURES

### Procedure 1: Pre-Event Hypothesis Creation

**Trigger:** Event within next 4 hours without hypothesis

**Steps:**
1. Query upcoming events:
   ```sql
   SELECT * FROM fhq_learning.v_events_without_hypotheses;
   ```

2. For each event, create hypothesis:
   ```sql
   INSERT INTO fhq_learning.hypothesis_ledger (
       event_id,
       hypothesis_text,
       expected_direction,
       expected_magnitude,
       confidence_pre_event,
       immutable_after
   ) VALUES (
       :event_id,
       'NFP release will be above consensus, supporting BULLISH USD',
       'BULLISH',
       'MEDIUM',
       0.65,
       :event_timestamp
   );
   ```

3. Verify immutability set:
   ```sql
   SELECT hypothesis_id, immutable_after, NOW() < immutable_after as is_mutable
   FROM fhq_learning.hypothesis_ledger
   WHERE event_id = :event_id;
   ```

### Procedure 2: Post-Event Decision Recording

**Trigger:** Event has passed, hypothesis is immutable

**Steps:**
1. Check hypothesis status:
   ```sql
   SELECT * FROM fhq_learning.v_experiment_summary
   WHERE experiment_status = 'PENDING';
   ```

2. Record decision:
   ```sql
   INSERT INTO fhq_learning.decision_experiment_ledger (
       hypothesis_id,
       decision_pack_id,  -- NULL if no trade
       decision_type,
       no_trade_reason,  -- Required if NO_TRADE
       trade_direction
   ) VALUES (
       :hypothesis_id,
       :pack_id,
       'TRADE',  -- or 'NO_TRADE', 'WAIT'
       NULL,
       'LONG'
   );
   ```

### Procedure 3: Outcome Recording (T+24h)

**Trigger:** 24 hours after event

**Steps:**
1. Check overdue outcomes:
   ```sql
   SELECT * FROM fhq_learning.v_overdue_outcomes;
   ```

2. Record outcome:
   ```sql
   INSERT INTO fhq_learning.expectation_outcome_ledger (
       hypothesis_id,
       experiment_id,
       actual_direction,
       actual_magnitude,
       actual_value,
       consensus_value,
       surprise_pct,
       market_response,
       price_change_pct,
       learning_verdict,
       verdict_rationale,
       recorded_within_24h,
       evaluation_hours
   ) VALUES (
       :hypothesis_id,
       :experiment_id,
       'BULLISH',  -- Actual direction
       'HIGH',  -- Actual magnitude
       275000,  -- NFP actual
       220000,  -- Consensus
       25.0,  -- (275-220)/220 * 100
       'OVER',  -- Market reacted more than expected
       0.8,  -- 0.8% price change
       'VALIDATED',  -- Hypothesis was correct
       'NFP beat consensus significantly, USD strengthened as predicted',
       TRUE,
       18.5  -- Hours from event to recording
   );
   ```

### Procedure 4: Alert Resolution

**Trigger:** Alert in Control Room

**Steps:**
1. Check active alerts:
   ```bash
   python control_room_alerter.py
   ```

2. Resolve alert after action:
   ```python
   from control_room_alerter import resolve_alert, get_connection
   conn = get_connection()
   resolve_alert(conn, 'outcome_not_recorded_24h', 'STIG', 'Outcome recorded')
   ```

---

## MONITORING VIEWS

### v_experiment_summary
Unified experiment pipeline status.

```sql
SELECT * FROM fhq_learning.v_experiment_summary
ORDER BY event_time DESC;
```

### v_overdue_outcomes
Hypotheses past T+24h deadline.

```sql
SELECT * FROM fhq_learning.v_overdue_outcomes;
```

### v_events_without_hypotheses
Upcoming events needing hypothesis.

```sql
SELECT * FROM fhq_learning.v_events_without_hypotheses;
```

### v_learning_metrics
Aggregate learning statistics.

```sql
SELECT * FROM fhq_learning.v_learning_metrics;
```

---

## ALERT RULES

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| hypothesis_not_pre_committed | Event < 4h without hypothesis | WARNING | Create hypothesis immediately |
| outcome_not_recorded_24h | Hypothesis > 24h past event without outcome | CRITICAL | Record outcome ASAP |
| ios016_event_ingestion_missing | No events in next 7 days | WARNING | Check event calendar feed |

---

## LEARNING VERDICTS

| Verdict | Definition | Criteria |
|---------|------------|----------|
| VALIDATED | Hypothesis confirmed by outcome | Direction correct AND magnitude within range |
| WEAKENED | Hypothesis partially correct | Direction correct BUT magnitude wrong |
| FALSIFIED | Hypothesis incorrect | Direction wrong |

---

## SCHEDULED TASKS

| Task | Schedule | Script |
|------|----------|--------|
| Alert check | Every 15 min | `control_room_alerter.py` |
| LVI computation | Daily 00:00 | `lvi_calculator.py` |
| Hypothesis scan | Every hour | `ios016_hypothesis_scanner.py` |
| Outcome deadline check | Every 4 hours | `ios016_outcome_checker.py` |

---

## INTEGRATION POINTS

### Control Room
- Alerts → `fhq_ops.control_room_alerts`
- LVI updates → `fhq_ops.control_room_lvi`
- Dashboard metrics → `fhq_ops.v_control_room_dashboard`

### Telegram
- CRITICAL alerts → Immediate notification
- Daily summary → 08:00 CET with experiment stats

### Evidence Chain
- All hypotheses → evidence_hash
- All outcomes → evidence_hash
- Hash chain maintained for audit

---

## TROUBLESHOOTING

### "Hypothesis immutable" error
- Cause: Trying to edit hypothesis after event time
- Resolution: Create new hypothesis for future event

### "No calendar events found"
- Cause: Event ingestion pipeline blocked
- Resolution: Check `fhq_calendar.staging_events` and ingest daemon

### "LVI score zero"
- Cause: No completed experiments or missing ledger tables
- Resolution: Run migration 333, complete at least one full experiment

---

## APPROVAL

| Role | Status | Signature |
|------|--------|-----------|
| STIG | DELIVERED | EC-003 |
| CEO | PENDING | - |
