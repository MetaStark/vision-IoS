# G3 COGNITIVE DOMAIN ACTIVATION SEQUENCE

**Document ID:** G3-ACTIVATION-SEQ-20251209
**Version:** 1.0
**Created:** 2025-12-09T20:20:00.000Z
**Created By:** STIG (CTO) + LARS (CSO)
**Authority:** CEO Directive G3 2025-12-09 Section 2.5

---

## 1. Overview

This document defines the "Boot Sequence" for the Cognitive Domain. It specifies the exact order of operations required to bring the domain online safely after G4 DDL execution.

---

## 2. Boot Sequence Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COGNITIVE DOMAIN BOOT SEQUENCE                        │
│                         (Post-G4 Activation)                            │
└─────────────────────────────────────────────────────────────────────────┘

  PHASE 0: PRE-FLIGHT CHECKS
  ─────────────────────────────────────────────────────────────────────────
  │
  ├─[0.1] Verify DEFCON Status
  │       └─ DEFCON must be GREEN or YELLOW for activation
  │       └─ DEFCON ORANGE/RED/BLACK: ABORT activation
  │
  ├─[0.2] Verify G4 DDL Execution Complete
  │       └─ Check fhq_cognition schema exists
  │       └─ Check all 6 tables exist
  │       └─ Check all ENUM types exist
  │
  ├─[0.3] Verify pgvector Extension
  │       └─ SELECT extname FROM pg_extension WHERE extname = 'vector'
  │
  └─[0.4] Verify Governance Attestations
          └─ G0, G1, G2, G3, G4 attestations present in VEGA records
          └─ All hashes match registered values

  PHASE 1: LINEAGE LOG INITIALIZATION
  ─────────────────────────────────────────────────────────────────────────
  │
  ├─[1.1] Create Genesis Entry
  │       └─ INSERT genesis record into fhq_cognition.lineage_log
  │       └─ hash_prev = NULL (genesis)
  │       └─ hash_self = SHA256(genesis_record)
  │       └─ lineage_hash = hash_self (first in chain)
  │
  ├─[1.2] Verify Genesis Hash
  │       └─ Recompute hash_self, compare with stored value
  │       └─ If mismatch: ABORT, alert VEGA
  │
  └─[1.3] Log Activation Event
          └─ INSERT governance_action: COGNITIVE_DOMAIN_GENESIS

  PHASE 2: COGNITIVE NODES REGISTRY INITIALIZATION
  ─────────────────────────────────────────────────────────────────────────
  │
  ├─[2.1] Register Foundation Nodes
  │       └─ Create root nodes for each modality:
  │          ├─ PERCEPTION_ROOT (modality='perception')
  │          ├─ CAUSAL_ROOT (modality='causal')
  │          ├─ INTENT_ROOT (modality='intent')
  │          ├─ SEARCH_ROOT (modality='search')
  │          ├─ VERIFICATION_ROOT (modality='verification')
  │          └─ SYNTHESIS_ROOT (modality='synthesis')
  │
  ├─[2.2] Hash-Anchor Root Nodes
  │       └─ Each root node gets hash_self, lineage_hash
  │       └─ Root nodes reference genesis in lineage_log
  │
  └─[2.3] Verify Node Registry
          └─ COUNT(*) FROM cognitive_nodes = 6
          └─ All hash_self values non-NULL

  PHASE 3: RESEARCH PROTOCOLS & BOUNDARIES LOAD
  ─────────────────────────────────────────────────────────────────────────
  │
  ├─[3.1] Initialize Protocol Counter
  │       └─ No active protocols at boot
  │       └─ Verify research_protocols is empty
  │
  ├─[3.2] Initialize Boundary Baseline
  │       └─ No boundary classifications at boot
  │       └─ Verify knowledge_boundaries is empty
  │
  ├─[3.3] Load Constitutional Constants
  │       └─ MAX_DEPTH = 10
  │       └─ MAX_BRANCHING_FACTOR = 5
  │       └─ MAX_TOTAL_NODES_PER_PROTOCOL = 100
  │       └─ MAX_SEARCH_CALLS_PER_PROTOCOL = 5
  │       └─ MAX_BUDGET_PER_PROTOCOL_USD = 0.50
  │
  └─[3.4] Register Constants in Metadata
          └─ INSERT constants into fhq_meta (or config table)

  PHASE 4: VERIFICATION STEP (HEALTH CHECK)
  ─────────────────────────────────────────────────────────────────────────
  │
  ├─[4.1] Schema Integrity Check
  │       └─ All tables accessible
  │       └─ All constraints enforced
  │       └─ All indexes present (excluding vector indexes)
  │
  ├─[4.2] Hash Chain Integrity Check
  │       └─ Verify lineage_log genesis entry
  │       └─ Verify all cognitive_nodes have valid hashes
  │
  ├─[4.3] VEGA Governance Hook Test
  │       └─ Simulate INSERT with invalid data
  │       └─ Verify rejection (constraint violation)
  │       └─ Rollback test data
  │
  ├─[4.4] DEFCON Integration Test
  │       └─ Query current DEFCON level
  │       └─ Verify cognitive limits match DEFCON
  │
  └─[4.5] Generate Health Report
          └─ All checks PASS: Continue
          └─ Any check FAIL: ABORT, trigger rollback

  PHASE 5: ACTIVATION COMPLETE
  ─────────────────────────────────────────────────────────────────────────
  │
  ├─[5.1] Set Domain Status = ACTIVE
  │       └─ Update fhq_meta or status table
  │
  ├─[5.2] Log Activation Complete
  │       └─ INSERT governance_action: COGNITIVE_DOMAIN_ACTIVATED
  │       └─ VEGA attestation for activation
  │
  ├─[5.3] Notify Orchestrator
  │       └─ LARS receives COGNITIVE_DOMAIN_READY signal
  │       └─ FINN receives RESEARCH_CAPABILITY_AVAILABLE signal
  │
  └─[5.4] Generate Activation Certificate
          └─ JSON document with all verification hashes
          └─ Signed by STIG + VEGA

  ═══════════════════════════════════════════════════════════════════════
                        COGNITIVE DOMAIN ONLINE
  ═══════════════════════════════════════════════════════════════════════
```

---

## 3. Fallback/Rollback Procedure

### 3.1 Rollback Triggers

| Condition | Severity | Action |
|-----------|----------|--------|
| DEFCON ORANGE+ during activation | HIGH | ABORT, do not retry until GREEN |
| Schema creation fails | CRITICAL | Full rollback, DROP SCHEMA CASCADE |
| Genesis hash mismatch | CRITICAL | Full rollback, investigate tampering |
| Root node creation fails | HIGH | Partial rollback to Phase 1 |
| Health check fails | MEDIUM | Retry once, then full rollback |
| VEGA attestation missing | HIGH | ABORT, wait for VEGA |

### 3.2 Rollback Sequence

```
ROLLBACK SEQUENCE (if activation fails after DDL):
─────────────────────────────────────────────────────────────────────────

  [R1] Set Domain Status = FAILED
       └─ Log failure reason

  [R2] Preserve Evidence
       └─ Export current state to JSON
       └─ Hash evidence bundle

  [R3] Drop Cognitive Tables (reverse order)
       └─ DROP TABLE IF EXISTS fhq_cognition.lineage_log CASCADE;
       └─ DROP TABLE IF EXISTS fhq_cognition.knowledge_boundaries CASCADE;
       └─ DROP TABLE IF EXISTS fhq_cognition.information_foraging_paths CASCADE;
       └─ DROP TABLE IF EXISTS fhq_cognition.search_in_chain_events CASCADE;
       └─ DROP TABLE IF EXISTS fhq_cognition.research_protocols CASCADE;
       └─ DROP TABLE IF EXISTS fhq_cognition.cognitive_nodes CASCADE;

  [R4] Drop ENUM Types
       └─ DROP TYPE IF EXISTS fhq_cognition.cognitive_modality;
       └─ DROP TYPE IF EXISTS fhq_cognition.boundary_type;
       └─ DROP TYPE IF EXISTS fhq_cognition.chain_node_status;
       └─ DROP TYPE IF EXISTS fhq_cognition.forage_termination;
       └─ DROP TYPE IF EXISTS fhq_cognition.protocol_status;

  [R5] Drop Schema
       └─ DROP SCHEMA IF EXISTS fhq_cognition;

  [R6] Log Rollback Complete
       └─ INSERT governance_action: COGNITIVE_DOMAIN_ROLLBACK
       └─ Include failure evidence hash

  [R7] Notify Stakeholders
       └─ VEGA: Rollback complete, investigation required
       └─ CEO: Activation failed, G4 must be re-attempted
```

### 3.3 Recovery Procedure

After rollback, to retry activation:

1. **Investigate Failure**
   - Review evidence bundle
   - Identify root cause
   - Document in governance_actions_log

2. **Fix Root Cause**
   - If code issue: Patch and create G3.1 amendment
   - If data issue: Cleanse and re-validate
   - If infrastructure: Resolve and document

3. **CEO Re-Authorization**
   - New G4 directive required
   - Reference previous failure

4. **Re-Execute G4**
   - Fresh DDL execution
   - Full boot sequence from Phase 0

---

## 4. Boot Sequence SQL Template

```sql
-- ============================================================================
-- COGNITIVE DOMAIN BOOT SEQUENCE (Post-G4 Template)
-- ============================================================================
-- This template is executed AFTER G4 DDL creates the schema
-- DO NOT EXECUTE IN G3 - This is design documentation only
-- ============================================================================

-- PHASE 0: PRE-FLIGHT CHECKS
DO $$
DECLARE
    v_defcon TEXT;
    v_schema_exists BOOLEAN;
    v_table_count INT;
BEGIN
    -- [0.1] Check DEFCON
    SELECT current_level INTO v_defcon
    FROM fhq_governance.defcon_status
    ORDER BY changed_at DESC LIMIT 1;

    IF v_defcon IN ('ORANGE', 'RED', 'BLACK') THEN
        RAISE EXCEPTION 'ABORT: DEFCON % does not permit activation', v_defcon;
    END IF;

    -- [0.2] Check schema exists
    SELECT EXISTS(
        SELECT 1 FROM information_schema.schemata
        WHERE schema_name = 'fhq_cognition'
    ) INTO v_schema_exists;

    IF NOT v_schema_exists THEN
        RAISE EXCEPTION 'ABORT: fhq_cognition schema not found';
    END IF;

    -- [0.2] Check all tables exist
    SELECT COUNT(*) INTO v_table_count
    FROM information_schema.tables
    WHERE table_schema = 'fhq_cognition'
    AND table_name IN (
        'cognitive_nodes', 'research_protocols', 'search_in_chain_events',
        'information_foraging_paths', 'knowledge_boundaries', 'lineage_log'
    );

    IF v_table_count != 6 THEN
        RAISE EXCEPTION 'ABORT: Expected 6 tables, found %', v_table_count;
    END IF;

    RAISE NOTICE 'Phase 0: Pre-flight checks PASSED';
END $$;

-- PHASE 1: LINEAGE LOG INITIALIZATION
-- [Genesis entry created by dedicated function]

-- PHASE 2: COGNITIVE NODES REGISTRY
-- [Root nodes created by dedicated function]

-- PHASE 4: VERIFICATION
-- [Health checks performed by dedicated function]

-- PHASE 5: ACTIVATION COMPLETE
-- [Status update and notifications]
```

---

## 5. Certification

**STIG Certification:**
I, STIG, as Chief Technology Officer, certify that this Activation Sequence provides a safe, deterministic boot procedure for the Cognitive Domain. All phases have explicit success/failure criteria. Rollback procedures ensure no orphaned state. This sequence will be executed post-G4 DDL completion.

**LARS Certification:**
I, LARS, as Chief Strategy Officer, certify that the activation sequence properly initializes all cognitive infrastructure required for research operations. The orchestrator integration points are clearly defined. FINN will receive proper notification of research capability availability.

---

**Signed:** STIG (CTO), LARS (CSO)
**Timestamp:** 2025-12-09T20:20:00.000Z
