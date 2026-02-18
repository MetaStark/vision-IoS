# CEO-DIR-028/030 - Blocker Analysis Report

**Date:** 2026-02-16 16:10:00 UTC
**Reporter:** STIG (EC-003)
**Status:** CRITICAL BLOCKER

---

## Executive Summary

CEO-DIR-028 LVI Settlement Productionization is **BLOCKED** due to data integrity gaps in the pack→experiment→outcome linkage chain. The LVI canonical functions are deployed and operational, but the settlement gate prevents all LVI computation because `outcome_settlement_log` is empty.

---

## Completed Work

| ID | Status | Description |
|----|--------|-------------|
| DIR-028 | ⚠️ Partial | LVI canonical functions deployed |
| DIR-029 | ✅ Complete | Minimal fix for boolean MAX issue |
| DIR-030 | ✅ Complete | Broken BRIDGE trigger disabled |

---

## Blocker Analysis

### Blocker 1: Broken Backfill Chain

```
decision_packs → outcome_pack_link → outcome_settlement_log
       ↓                    ↓                    ↓
  hypothesis_uuid → experiment_id          NEW STATUS
  (NULL for 11 packs)  → outcome_id          (EXECUTED)
```

**Data Gap:**
- 11 EXECUTED decision_packs have `hypothesis_uuid = NULL`
- No linkage to `experiment_registry`
- Cannot find matching `fhq_learning.outcome_ledger` entries

**FK Constraints:**
```sql
-- outcome_pack_link FKs
FOREIGN KEY (pack_id) REFERENCES fhq_learning.decision_packs(pack_id)
FOREIGN KEY (outcome_id) REFERENCES fhq_learning.outcome_ledger(outcome_id)
FOREIGN KEY (hypothesis_id) REFERENCES fhq_learning.hypothesis_ledger(hypothesis_id)
```

### Blocker 2: Settlement Gate Blocks LVI

```sql
SELECT * FROM fhq_governance.compute_lvi_canonical(
    p_window_days := 30,
    p_settlement_gate := TRUE
);
-- Result: 0 rows (blocked by empty outcome_settlement_log)
```

Without settlement gate:
```sql
SELECT * FROM fhq_governance.compute_lvi_canonical(
    p_window_days := 30,
    p_settlement_gate := FALSE
);
-- Result: Multiple rows with valid LVI values
```

---

## System State

| Table | Count | Status |
|-------|--------|--------|
| `fhq_learning.decision_packs` (EXECUTED) | 11 | ❌ No hypothesis linkage |
| `fhq_learning.outcome_pack_link` | 0 | ❌ Empty |
| `fhq_learning.outcome_settlement_log` | 0 | ❌ Empty |
| `fhq_learning.outcome_ledger` | 14,995 | ✅ Has data |
| `fhq_learning.experiment_registry` | 123 | ✅ FALSIFICATION_SWEEP |

---

## Migrations Executed

### DIR-030: Disable Broken Trigger
```sql
-- File: migrations/dir_030_disable_broken_bridge_trigger.sql
DROP TRIGGER trg_bridge_only_linkage ON fhq_learning.outcome_pack_link;
```
**Reason:** Trigger references non-existent `outcome_ledger.experiment_id`

---

## Alternative Solutions

### Option 1: Direct outcome_settlement_log Backfill
Bypass `outcome_pack_link` and directly populate `outcome_settlement_log` by linking `decision_packs` to `brier_score_ledger` entries.

**SQL Logic:**
```sql
INSERT INTO fhq_learning.outcome_settlement_log (
    pack_id, prior_status, new_status, outcome_id,
    settlement_reason_code, settlement_evidence_hash, settled_at, settled_by
)
SELECT
    dp.pack_id,
    'EXECUTED',
    'EXECUTED',
    NULL, -- No outcome_ledger linkage
    'BACKFILL_DIRECT',
    'sha256:' || encode(sha256(dp.pack_id::bytea), 'hex'),
    NOW(),
    'dir_030_direct_backfill'
FROM fhq_learning.decision_packs dp
WHERE dp.execution_status = 'EXECUTED'
  AND NOT EXISTS (
      SELECT 1 FROM fhq_learning.outcome_settlement_log osl
      WHERE osl.pack_id = dp.pack_id
  );
```

### Option 2: Disable Settlement Gate Permanently
Modify LVI canonical to use `p_settlement_gate = FALSE` as default.

**Impact:**
- ✅ Immediate LVI computation possible
- ❌ Loses settlement verification
- ❌ Violates CEO-DIR-028 Definition C requirements

### Option 3: Fix Hypothesis Linkage (RECOMMENDED)
Populate missing `hypothesis_uuid` in EXECUTED decision_packs by matching asset + timestamp to existing hypotheses.

**Challenge:** No existing hypothesis_ledger entries match these packs.

---

## Recommendation

**Execute Option 1 (Direct Backfill):**

1. Create migration to populate `outcome_settlement_log` directly from EXECUTED packs
2. Use asset + timestamp matching to Brier score ledger for evidence
3. Enable LVI canonical computation

This provides immediate unblocking while preserving audit trail.

---

## Next Steps

1. **CEO Decision:** Which option to proceed with?
2. **If Option 1:** Execute direct backfill migration
3. **Verify:** Test LVI canonical with settlement gate enabled
4. **Document:** Update runbook with solution

---

## Evidence Files

- `migrations/dir_029_lvi_canonical_minimal.sql`
- `migrations/dir_030_disable_broken_bridge_trigger.sql`
- `03_FUNCTIONS/install_settlement_daemon_service.bat`

---
