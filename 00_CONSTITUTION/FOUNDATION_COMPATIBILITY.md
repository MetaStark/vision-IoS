# FOUNDATION COMPATIBILITY MATRIX
## Vision-IoS <-> ADR-001–013 Compliance

**Generated:** 2025-11-23 01:32:31 UTC
**Foundation Repo:** github.com/MetaStark/fhq-market-system
**Foundation Branch:** claude/setup-db-mirroring-01LUuKugCnjjoWAPxAYwxt8s
**Foundation Commit:** c5fb701 - CANONICAL BASE SYNC

---

## 🏛️ CONSTITUTION REFERENCE

Vision-IoS is built **on top of** the ADR-001–013 foundation.
The foundation is **immutable and sovereign**.
Vision-IoS operates at the **application layer**, not the kernel layer.

```
┌─────────────────────────────────────┐
│ VISION-IOS (Application Layer)     │ ← We are here
│ • Builds on foundation              │
│ • Cannot override ADR-001–013       │
│ • Extends, never replaces           │
└─────────────────────────────────────┘
                ↓ builds on
┌─────────────────────────────────────┐
│ FHQ-MARKET-SYSTEM (Foundation)      │ ← Immutable
│ • ADR-001–013 (constitution)        │
│ • fhq_* schemas (canonical)         │
│ • VEGA/STIG/LARS/LINE/FINN agents   │
└─────────────────────────────────────┘
```

---

## ✅ ADR COMPLIANCE MATRIX

### Foundation ADRs (MUST COMPLY)

| ADR | Title | Vision-IoS Dependency | Compliance Level |
|-----|-------|----------------------|------------------|
| ADR-001 | System Charter | Uses same database, respects domain ownership | **CRITICAL** |
| ADR-002 | Audit Charter | All changes logged to fhq_meta.adr_audit_log | **CRITICAL** |
| ADR-003 | Institutional Standards | Follows schema naming (vision_*), not fhq_* | **REQUIRED** |
| ADR-004 | Change Gates | All DB changes go through G1-G4 gates | **REQUIRED** |
| ADR-005 | Mission & Vision | Aligned: "eliminate noise, generate signal" | INFORMATIONAL |
| ADR-006 | VEGA Charter | Autonomous functions report to VEGA | **CRITICAL** |
| ADR-007 | Orchestrator Architecture | Functions run under LARS/STIG/LINE/FINN | **CRITICAL** |
| ADR-008 | Crypto Keys | All operations signed via Ed25519 | **CRITICAL** |
| ADR-009 | Suspension Workflow | Vision functions can be suspended via VEGA | **REQUIRED** |
| ADR-010 | Reconciliation | Vision state syncs to fhq_meta reconciliation | **REQUIRED** |
| ADR-011 | Fortress | Vision operations produce hash chains | **REQUIRED** |
| ADR-012 | Economic Safety | NO autonomous execution until QG-F6 passes | **BLOCKER** |
| ADR-013 | Kernel Specification | Vision-IoS is application layer, not kernel | **CRITICAL** |

---

## 🚫 PROHIBITED ACTIONS

Vision-IoS **CANNOT** do the following (violations trigger VEGA Class A):

1. ❌ Create new `fhq_*` schemas (only `vision_*` allowed)
2. ❌ Write to foundation schemas (fhq_data, fhq_meta, fhq_monitoring, fhq_research)
3. ❌ Create new agent identities (must use existing LARS/STIG/LINE/FINN)
4. ❌ Generate new Ed25519 keys (must use ADR-008 key management)
5. ❌ Execute autonomous trades before ADR-012 QG-F6 passes
6. ❌ Bypass Change Gates (ADR-004 G0-G4)
7. ❌ Override ADR-001–013 decisions
8. ❌ Use separate database (must use same DB)
9. ❌ Skip audit logging (ADR-002)
10. ❌ Operate outside VEGA governance (ADR-006)

---

## ✅ PERMITTED ACTIONS

Vision-IoS **CAN** do the following:

1. ✅ Create new `vision_*` schemas
2. ✅ Read from foundation schemas (fhq_*)
3. ✅ Write to `vision_*` schemas
4. ✅ Run functions under existing agent identities
5. ✅ Generate signals (non-executable)
6. ✅ Perform meta-analysis
7. ✅ Filter noise
8. ✅ Create hash chains for verification
9. ✅ Log all operations to fhq_meta.adr_audit_log
10. ✅ Request VEGA approval for new capabilities

---

## 📐 DATABASE STRATEGY

### Same Database, New Schemas

```sql
-- FOUNDATION SCHEMAS (READ-ONLY for Vision-IoS)
fhq_data         -- Price data, market data
fhq_meta         -- ADR registry, audit logs
fhq_monitoring   -- System events, health
fhq_research     -- Research results

-- VISION SCHEMAS (READ-WRITE for Vision-IoS)
vision_core         -- Core execution engine
vision_signals      -- Alpha signal storage
vision_autonomy     -- Self-governance state
vision_verification -- Cryptographic proofs
```

### Access Control

```sql
-- Vision-IoS has SELECT on foundation schemas
GRANT SELECT ON SCHEMA fhq_data TO vision_app;
GRANT SELECT ON SCHEMA fhq_meta TO vision_app;
GRANT SELECT ON SCHEMA fhq_monitoring TO vision_app;
GRANT SELECT ON SCHEMA fhq_research TO vision_app;

-- Vision-IoS has ALL on vision schemas
GRANT ALL ON SCHEMA vision_core TO vision_app;
GRANT ALL ON SCHEMA vision_signals TO vision_app;
GRANT ALL ON SCHEMA vision_autonomy TO vision_app;
GRANT ALL ON SCHEMA vision_verification TO vision_app;
```

---

## 🎯 FIRST 3 FUNCTIONS (ADR-Compliant)

### 1. Signal Inference Baseline
- **Schema:** `vision_signals.generate_baseline`
- **Purpose:** System understands state (non-actionable)
- **ADR Compliance:** ADR-010 (reconciliation), FINN discovery
- **Risk Level:** LOW (read-only analysis)

### 2. Noise Floor Estimator
- **Schema:** `vision_core.noise_profile`
- **Purpose:** Build reference level for noise vs signal
- **ADR Compliance:** Required to avoid false VEGA escalations
- **Risk Level:** LOW (profiling only)

### 3. Meta-State Sync
- **Schema:** `vision_autonomy.meta_sync`
- **Purpose:** Sync Vision-IoS state to fhq_meta
- **ADR Compliance:** ADR-002 (audit), ADR-010 (reconciliation)
- **Risk Level:** LOW (state sync only)

---

## 🔐 GOVERNANCE INTEGRATION

Vision-IoS functions run **under existing agent identities**:

- **LARS** - Orchestration commands
- **STIG** - Execution validation
- **LINE** - Data ingestion
- **FINN** - Discovery and analysis

Vision-IoS does **NOT** create new agents.
All governance flows through `fhq_governance` (ADR-007).
All actions signed via `fhq_meta.agent_keys` (ADR-008).

---

## 📊 COMPLIANCE VERIFICATION

To verify Vision-IoS remains compliant:

```bash
# Check schemas (should only have vision_*)
psql -c "\dn" | grep vision

# Verify no writes to foundation schemas
psql -c "SELECT * FROM fhq_meta.adr_audit_log WHERE schema_name LIKE 'fhq_%' AND created_by = 'vision_app';"

# Confirm all operations are signed
psql -c "SELECT * FROM vision_verification.operation_signatures ORDER BY created_at DESC LIMIT 10;"
```

---

## 🚨 ESCALATION POLICY

If Vision-IoS violates ADR-001–013:

1. **Class A Violation** (writes to fhq_*, new agents, skips audit)
   - Immediate suspension via ADR-009
   - VEGA emergency review
   - System rollback required

2. **Class B Violation** (misses audit log, wrong schema naming)
   - VEGA warning
   - 24h correction window
   - Escalates to Class A if not fixed

3. **Class C Violation** (documentation gaps, minor deviations)
   - Logged to fhq_meta.adr_audit_log
   - Correction in next sprint

---

## 📚 REFERENCES

- **Foundation Repo:** https://github.com/MetaStark/fhq-market-system
- **Baseline Commit:** c5fb701
- **ADR Registry:** See fhq_meta.adr_registry
- **Governance:** See fhq_governance schema

---

**Status:** ACTIVE
**Last Updated:** 2025-11-23
**Maintained By:** LARS (orchestrator)
