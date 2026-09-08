# CEO-DIR-2026-023 Order 2: Re-Baseline Blueprint

**Dato:** 2026-01-23
**Direktiv:** CEO-DIR-2026-023
**Order:** 2 - RE-BASELINE BLUEPRINT
**Status:** COMPLETE
**Computed By:** STIG (EC-003)

---

## EXECUTIVE SUMMARY

Selective re-baseline after IoS-013 FULL integration. System is CHANGED, not BROKEN. This blueprint classifies all surfaces into three tiers with preservation/reset rules.

**Guiding Principle:** Preserve operational infrastructure (IoS-013 FULL), protect immutable evidence, build missing control plane.

---

## THREE-TIER CLASSIFICATION

### TIER 0 - IMMUTABLE EVIDENCE (NEVER DELETE)

These artifacts form the audit trail and governance foundation. Deletion is prohibited.

| Schema | Object | Records | Protection |
|--------|--------|---------|------------|
| fhq_governance | ec_registry | 5 | FK + Trigger |
| fhq_governance | canonical_evidence | 0 | FK + Trigger |
| fhq_governance | learning_hypothesis_registry | 1 | FK + Trigger |
| fhq_governance | task_execution_evidence | * | FK + Trigger |
| fhq_governance | epistemic_lesson_evidence | * | FK + Trigger |
| fhq_research | outcome_ledger | 30,685 | FK + Trigger |
| fhq_research | forecast_skill_metrics | 141 | Immutable |
| fhq_canonical | evidence_nodes | * | FK + Trigger |
| fhq_canonical | evidence_relationships | * | FK + Trigger |
| fhq_canonical | hash_chains | * | Immutable |
| filesystem | 03_FUNCTIONS/evidence/*.json | * | Git-tracked |
| filesystem | 05_GOVERNANCE/*.md | * | Git-tracked |

**Enforcement:**
```sql
-- Trigger to prevent deletion of Tier 0 records
CREATE OR REPLACE FUNCTION prevent_tier0_delete()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'TIER0_VIOLATION: Cannot delete immutable evidence (%)' , TG_TABLE_NAME;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Apply to Tier 0 tables
CREATE TRIGGER tier0_protect_outcome_ledger
  BEFORE DELETE ON fhq_research.outcome_ledger
  FOR EACH ROW EXECUTE FUNCTION prevent_tier0_delete();
```

---

### TIER 1 - SIGNAL INFRASTRUCTURE (PRESERVE)

Active IoS-013 FULL integration components. Preserve current state.

| Schema | Object | Records | Action |
|--------|--------|---------|--------|
| fhq_signal_context | weighted_signal_plan | 23 | PRESERVE |
| fhq_signal_context | signal_scope_registry | * | PRESERVE |
| fhq_finn | regime_states | * | PRESERVE |
| fhq_finn | regime_daily | * | PRESERVE |
| fhq_research | fama_french_factors | 15,709 | PRESERVE |
| fhq_calendar | calendar_events | 51 | PRESERVE |
| fhq_learning | decision_packs | 20 | PRESERVE |
| fhq_governance | agent_heartbeats | 8 | PRESERVE |

**Files to Preserve:**
```
03_FUNCTIONS/ios013_options_universe_signal_generator.py
03_FUNCTIONS/ios006_g2_macro_ingest.py
03_FUNCTIONS/ios014_g2_vega_validation.py
03_FUNCTIONS/unified_execution_gateway.py
03_FUNCTIONS/forecast_confidence_damper.py
```

**Enforcement:**
- Migration scripts include allowlist check
- Any operation on Tier 1 requires explicit CEO approval
- Backup created before any modification

---

### TIER 2 - LEARNING & CONTROL PLANE (BUILD/RESET)

New infrastructure required for learning loop closure and operational visibility.

| Schema | Object | Current State | Action |
|--------|--------|---------------|--------|
| fhq_ops | (entire schema) | DOES NOT EXIST | CREATE |
| fhq_ops | control_room_metrics | N/A | CREATE |
| fhq_ops | control_room_alerts | N/A | CREATE |
| fhq_ops | control_room_lvi | N/A | CREATE |
| fhq_ops | v_signal_production | N/A | CREATE VIEW |
| fhq_ops | v_calibration_distribution | N/A | CREATE VIEW |
| fhq_ops | v_event_coverage | N/A | CREATE VIEW |
| fhq_learning | hypothesis_ledger | DOES NOT EXIST | CREATE |
| fhq_learning | decision_experiment_ledger | DOES NOT EXIST | CREATE |
| fhq_learning | expectation_outcome_ledger | DOES NOT EXIST | CREATE |
| fhq_governance | epistemic_proposals | 0 records | ACTIVATE |

**Files to Create:**
```
03_FUNCTIONS/lvi_calculator.py
03_FUNCTIONS/control_room_alerter.py
04_DATABASE/MIGRATIONS/310_fhq_ops_control_room.sql
04_DATABASE/MIGRATIONS/311_ios016_experiment_ledgers.sql
```

---

## PRESERVATION MATRIX

| Component | Tier | Records | Action | Rationale |
|-----------|------|---------|--------|-----------|
| weighted_signal_plan | 1 | 23 | PRESERVE | IoS-013 FULL active |
| outcome_ledger | 0 | 30,685 | IMMUTABLE | Historical truth |
| decision_packs | 1 | 20 | PRESERVE | Active decisions |
| calendar_events | 1 | 51 | PRESERVE | Event calendar |
| fama_french_factors | 1 | 15,709 | PRESERVE | Macro foundation |
| forecast_skill_metrics | 0 | 141 | IMMUTABLE | Calibration history |
| epistemic_proposals | 2 | 0 | ACTIVATE | Start generating |
| fhq_ops.* | 2 | N/A | CREATE | Control Room |
| hypothesis_ledger | 2 | N/A | CREATE | IoS-016 loop |

---

## RESET RULES

### What Gets Reset
1. **Stale daemon heartbeats** - Update to current timestamp after verification
2. **Empty alpha surfaces** - Leave empty (will populate organically)
3. **Staging tables** - Clear for fresh ingestion

### What Does NOT Get Reset
1. **ANY Tier 0 record** - Never
2. **IoS-013 signal plans** - Active integration
3. **Brier calibration metrics** - Historical truth
4. **Outcome ledger** - Learning history

---

## MIGRATION SAFETY PROTOCOL

### Pre-Migration
```bash
# 1. Create backup
pg_dump -h 127.0.0.1 -p 54322 -U postgres postgres > backup_pre_023_$(date +%Y%m%d).sql

# 2. Verify Tier 0 counts
psql -c "SELECT 'outcome_ledger', COUNT(*) FROM fhq_research.outcome_ledger"
psql -c "SELECT 'forecast_skill_metrics', COUNT(*) FROM fhq_research.forecast_skill_metrics"
```

### Post-Migration
```bash
# 3. Verify Tier 0 unchanged
psql -c "SELECT 'outcome_ledger', COUNT(*) FROM fhq_research.outcome_ledger"
# Must equal pre-migration count

# 4. Verify Tier 2 created
psql -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'fhq_ops'"
# Must return 'fhq_ops'
```

---

## ENFORCEMENT MECHANISMS

### 1. Tier 0 Delete Triggers
```sql
-- Applied to all Tier 0 tables
CREATE TRIGGER tier0_protect_{table}
  BEFORE DELETE ON {schema}.{table}
  FOR EACH ROW EXECUTE FUNCTION prevent_tier0_delete();
```

### 2. Migration Allowlist
```python
TIER1_ALLOWLIST = [
    'fhq_signal_context.weighted_signal_plan',
    'fhq_finn.regime_states',
    'fhq_research.fama_french_factors',
    'fhq_calendar.calendar_events',
    'fhq_learning.decision_packs'
]

def validate_migration(target_table):
    if target_table in TIER1_ALLOWLIST:
        raise MigrationBlockedError(f"Tier 1 table {target_table} requires CEO approval")
```

### 3. Git Protection
```
# .gitattributes
03_FUNCTIONS/evidence/*.json merge=ours
05_GOVERNANCE/*.md merge=ours
```

---

## TIER CHANGE REQUEST PROCESS

### To Reclassify a Surface
1. Submit CEO-DIR with justification
2. VEGA attestation required for Tier 0→1 or Tier 1→2
3. Evidence bundle documenting downstream impact
4. Minimum 24h review period
5. Rollback plan documented

---

## DOWNSTREAM DEPENDENCIES

### IoS-013 FULL Depends On
- fhq_signal_context.weighted_signal_plan (Tier 1)
- fhq_finn.regime_states (Tier 1)
- fhq_research.fama_french_factors (Tier 1)
- fhq_research.forecast_skill_metrics (Tier 0)

### Control Room Depends On
- fhq_ops.* (Tier 2 - to be created)
- fhq_signal_context.weighted_signal_plan (Tier 1)
- fhq_calendar.calendar_events (Tier 1)

### LVI Depends On
- fhq_learning.hypothesis_ledger (Tier 2 - to be created)
- fhq_learning.decision_experiment_ledger (Tier 2 - to be created)
- fhq_learning.expectation_outcome_ledger (Tier 2 - to be created)
- fhq_learning.decision_packs (Tier 1)
- fhq_research.outcome_ledger (Tier 0)

---

## APPROVAL

**Order 2 Complete.** Awaiting CEO + VEGA checkpoint.

| Role | Status | Signature |
|------|--------|-----------|
| STIG | DELIVERED | EC-003 |
| CEO | PENDING | - |
| VEGA | PENDING | - |

---

## APPENDIX: TIER SUMMARY

```
TIER 0 (IMMUTABLE)     TIER 1 (PRESERVE)      TIER 2 (BUILD)
==================     =================      ==============
outcome_ledger         weighted_signal_plan   fhq_ops.*
forecast_skill_metrics regime_states          hypothesis_ledger
ec_registry           fama_french_factors     decision_experiment_ledger
canonical_evidence    calendar_events         expectation_outcome_ledger
hash_chains           decision_packs          control_room_*
evidence/*.json       agent_heartbeats        lvi_calculator.py
```
