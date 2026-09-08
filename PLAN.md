# CEO-DIR-2026-LEARNING-MEMORY-ADMISSION-041-060: Implementation Plan

**Prepared by:** STIG (CTO)
**Date:** 2026-02-11 (DAY 42)
**DEFCON:** YELLOW
**Scope:** 20 Runbooks (Day 41-60)
**Authority:** ADR-013, ADR-016, ADR-017, ADR-018, ADR-020, ADR-021 + EC-020/EC-021

---

## 1. EXISTING INFRASTRUCTURE AUDIT

### What Already Exists

| Component | Location | Status |
|-----------|----------|--------|
| `fhq_memory` schema | 10 tables (agent_memory, episodic_memory, perception_memory, state_snapshots, archival_store, conversations, conversation_messages, embedding_store, knowledge_fragments, retrieval_audit_log) | EXISTS but nearly empty (1 total row) |
| ASRP state log | `fhq_governance.asrp_state_log` (15 cols) | EXISTS, 1 row from 2025-12-10 (dormant) |
| ASRP violations | `fhq_governance.asrp_violations` (17 cols) | EXISTS, empty |
| ASRP code impl | `court_proof_enforcer_v2.py` (566 lines) | ACTIVE - canonical ASRP binding pattern |
| Alpha Graph nodes | `fhq_learning.alpha_graph_nodes` (18 cols) | 21,815 nodes |
| Causal edges | `fhq_alpha.causal_edges` (7 cols) | 64,523 edges |
| Alpha Graph ignition | `fhq_governance.alpha_graph_ignition_log` | EXISTS |
| Causal entropy audit | `fhq_governance.causal_entropy_audit` | EXISTS |
| Promotion gate | `promotion_gate_engine.py` (782 lines) | ACTIVE - DSR+PBO+FamilyInflation gate |
| Promotion gate audit | `fhq_learning.promotion_gate_audit` (8 cols) | EXISTS |
| Memory stack | `memory_stack.py` (631 lines) | ACTIVE - 3-tier CORE/RECALL/ARCHIVAL |
| BSS/Brier infra | `fhq_governance.brier_score_ledger`, `brier_decomposition` + 3 views | EXISTS |
| LVI canonical | `fhq_governance.lvi_canonical` | LVI = 0.0 (CRISIS), stale |
| Learning velocity | `fhq_learning.learning_velocity_metrics` (28 cols) | 1 row, last computed 2026-01-24 |
| Shared state snapshots | `fhq_governance.shared_state_snapshots` (24 cols, hash chain) | EXISTS |
| Epistemic system | 8 tables in `fhq_governance` | EXISTS |
| Hypothesis canon | `fhq_learning.hypothesis_canon` (75 cols) | 1,286 total (224 FALSIFIED, 1,062 TIMEOUT_PENDING) |
| Experiment registry | `fhq_learning.experiment_registry` (26 cols) | 123 completed, 0 active |
| Decision packs | `fhq_learning.decision_packs` (62 cols) | EXISTS |

### What Does NOT Exist (Must Be Created)

| Component | Notes |
|-----------|-------|
| STM/MTM/LPM tier separation | No tiered memory with promotion controls |
| Memory containment firewall | No side-channel prevention between memory and canonical pipeline |
| Learning Admission Gate | No ASRP-bound admission process for MTM -> LPM |
| Invariant Core registry | No frozen invariant driver set |
| Invariant expansion gate | No BSS-gated graph expansion |
| Memory contamination kill-switch | No fail-closed contamination detection |
| Titans/MIRAS integration layer | No non-canonical producer framework |
| Freeze scheduler | No 72h quarantine cycle |
| Stress harness | No reproducible crisis replay |

---

## 2. ARCHITECTURAL DECISIONS

### 2.1 Schema Strategy

**Extend `fhq_memory`** for MemoryOS tiers (STM, MTM, LPM). This schema already holds memory infrastructure and has the right semantic scope. Do NOT create a new schema.

**Extend `fhq_learning`** for Admission Gate and Invariant Core. These are learning governance constructs that belong alongside `promotion_gate_audit`, `alpha_graph_nodes`, and `hypothesis_canon`.

**Extend `fhq_governance`** for contamination events and gate state. Governance-level kill-switches belong here alongside DEFCON and ASRP.

### 2.2 ASRP Binding Strategy

Reuse the canonical pattern from `court_proof_enforcer_v2.py`:
1. `_get_state_snapshot()` builds state vector from execution_state + sovereign_policy_state + market prices
2. `_compute_hash()` -> SHA-256 of JSON-serialized state
3. Every artifact embeds: `state_snapshot_hash`, `state_timestamp`, `agent_id`

Create a shared `AsrpBinder` utility class extracted from `court_proof_enforcer_v2.py` to avoid code duplication across all new modules.

### 2.3 MIT Quad Pipeline Invariant

The pipeline order is: CEIO -> raw_staging -> CRIO -> research_signals -> IoS-006 -> canonical_features -> IoS-003 -> regime_state -> IoS-004 -> exposure

**MemoryOS operates OUTSIDE this pipeline.** Memory subsystems:
- READ from canonical pipeline outputs (observation)
- WRITE only to memory tables (fhq_memory)
- NEVER write to canonical_features, regime_state, or exposure tables
- The Admission Gate writes ONLY to `fhq_learning` (alpha_graph_nodes, hypothesis promotions)

This is enforced by: (a) database-level write permissions, (b) containment firewall audit, (c) DEFCON escalation on violation.

### 2.4 Existing Code Reuse

| Pattern | Source | Reuse |
|---------|--------|-------|
| Daemon heartbeat | `promotion_gate_engine.py` | All new daemons |
| ASRP binding | `court_proof_enforcer_v2.py` | Extract to shared utility |
| Evidence file writing | `promotion_gate_engine.py` | All new daemons |
| Gate evaluation pattern | `promotion_gate_engine.py` | Admission Gate |
| DB connection | `promotion_gate_engine.py` | All new daemons |
| Token-budgeted memory | `memory_stack.py` | STM/MTM/LPM tiers |

---

## 3. DATABASE MIGRATIONS (15 new tables)

### Phase 1 Tables (Runbooks 41-47)

```sql
-- T1: Memory Domain Registry
CREATE TABLE fhq_memory.memory_domains (
    domain_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_name VARCHAR(10) NOT NULL UNIQUE CHECK (domain_name IN ('STM', 'MTM', 'LPM')),
    description TEXT NOT NULL,
    is_canonical BOOLEAN NOT NULL DEFAULT false,
    write_protected BOOLEAN NOT NULL DEFAULT false,
    max_ttl_hours INTEGER,
    access_level VARCHAR(20) NOT NULL DEFAULT 'UNRESTRICTED',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT NOT NULL
);

-- T2: STM Store (Short-Term Memory)
CREATE TABLE fhq_memory.stm_store (
    stm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    session_id UUID,
    memory_key VARCHAR(255) NOT NULL,
    memory_value JSONB NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_id UUID,
    regime VARCHAR(50) NOT NULL,
    confidence NUMERIC,
    ttl_seconds INTEGER NOT NULL DEFAULT 3600,
    expires_at TIMESTAMPTZ NOT NULL,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    lineage_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    accessed_at TIMESTAMPTZ DEFAULT NOW()
);

-- T3: MTM Quarantine Store (Medium-Term Memory)
CREATE TABLE fhq_memory.mtm_quarantine (
    mtm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    observation_type VARCHAR(100) NOT NULL,
    observation_key VARCHAR(255) NOT NULL,
    observation_value JSONB NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    source_id UUID,
    source_agent VARCHAR(50),
    regime_at_observation VARCHAR(50) NOT NULL,
    confidence NUMERIC,
    experimental_tag BOOLEAN NOT NULL DEFAULT true,
    quarantine_status VARCHAR(20) NOT NULL DEFAULT 'QUARANTINED'
        CHECK (quarantine_status IN ('QUARANTINED', 'UNDER_REVIEW', 'PROMOTED', 'REJECTED', 'EXPIRED')),
    quarantine_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    quarantine_min_hours INTEGER NOT NULL DEFAULT 72,
    eligible_for_review_at TIMESTAMPTZ NOT NULL,
    review_started_at TIMESTAMPTZ,
    review_completed_at TIMESTAMPTZ,
    review_result TEXT,
    admission_gate_id UUID,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    lineage_hash TEXT,
    evidence_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- T4: LPM Canonical Store (Long-Term Permanent Memory)
CREATE TABLE fhq_memory.lpm_canonical (
    lpm_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_type VARCHAR(100) NOT NULL,
    knowledge_key VARCHAR(255) NOT NULL,
    knowledge_value JSONB NOT NULL,
    source_mtm_id UUID REFERENCES fhq_memory.mtm_quarantine(mtm_id),
    admission_gate_id UUID NOT NULL,
    promoted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    promoted_by TEXT NOT NULL,
    regime_tags TEXT[] NOT NULL,
    causal_node_id UUID,
    evidence_bundle_id UUID NOT NULL,
    bss_at_promotion NUMERIC NOT NULL,
    lvi_at_promotion NUMERIC NOT NULL,
    write_protected BOOLEAN NOT NULL DEFAULT true,
    invalidated BOOLEAN NOT NULL DEFAULT false,
    invalidated_at TIMESTAMPTZ,
    invalidated_by TEXT,
    invalidation_reason TEXT,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    lineage_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- T5: Containment Firewall Audit
CREATE TABLE fhq_memory.containment_firewall_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    source_domain VARCHAR(10) NOT NULL,
    target_domain VARCHAR(50) NOT NULL,
    blocked BOOLEAN NOT NULL,
    block_reason TEXT,
    agent_id VARCHAR(50) NOT NULL,
    operation_attempted TEXT NOT NULL,
    target_table TEXT,
    state_snapshot_hash TEXT NOT NULL,
    defcon_at_event TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Phase 2 Tables (Runbooks 48-54)

```sql
-- T6: Invariant Core Registry
CREATE TABLE fhq_learning.invariant_core_registry (
    invariant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invariant_name VARCHAR(100) NOT NULL UNIQUE,
    invariant_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    economic_rationale TEXT NOT NULL,
    falsifiability_statement TEXT NOT NULL,
    data_source TEXT NOT NULL,
    data_table TEXT NOT NULL,
    data_column TEXT,
    measurement_frequency VARCHAR(20) NOT NULL,
    is_frozen BOOLEAN NOT NULL DEFAULT false,
    frozen_at TIMESTAMPTZ,
    frozen_by TEXT,
    freeze_version INTEGER NOT NULL DEFAULT 0,
    alpha_graph_node_id UUID,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- T7: Invariant Expansion Gate
CREATE TABLE fhq_learning.invariant_expansion_gate (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposed_invariant_id UUID,
    proposed_name VARCHAR(100) NOT NULL,
    proposal_rationale TEXT NOT NULL,
    bss_before NUMERIC NOT NULL,
    bss_after NUMERIC,
    bss_improvement NUMERIC,
    complexity_before INTEGER NOT NULL,
    complexity_after INTEGER,
    gate_result VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (gate_result IN ('PENDING', 'APPROVED', 'REJECTED')),
    rejection_reason TEXT,
    evaluated_at TIMESTAMPTZ,
    evaluated_by TEXT,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    evidence_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- T8: BSS Baseline Registry
CREATE TABLE fhq_learning.bss_baseline_registry (
    baseline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    regime TEXT NOT NULL,
    brier_actual NUMERIC NOT NULL,
    brier_reference NUMERIC NOT NULL,
    bss_value NUMERIC NOT NULL,
    sample_size INTEGER NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    baseline_version INTEGER NOT NULL DEFAULT 1,
    is_current BOOLEAN NOT NULL DEFAULT true,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    evidence_hash TEXT NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computed_by TEXT NOT NULL
);

-- T9: Stress Harness Results
CREATE TABLE fhq_learning.stress_harness_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    harness_name VARCHAR(100) NOT NULL,
    crisis_period VARCHAR(50) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    invariant_set_version INTEGER NOT NULL,
    drift_detected BOOLEAN NOT NULL DEFAULT false,
    drift_magnitude NUMERIC,
    bss_during_crisis NUMERIC,
    replay_reproducible BOOLEAN NOT NULL,
    result_summary JSONB NOT NULL,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    evidence_hash TEXT NOT NULL,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    executed_by TEXT NOT NULL
);
```

### Phase 3 Tables (Runbooks 55-60)

```sql
-- T10: Admission Gate State
CREATE TABLE fhq_governance.admission_gate_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gate_status VARCHAR(20) NOT NULL DEFAULT 'LOCKED'
        CHECK (gate_status IN ('OPEN', 'LOCKED', 'REVIEW', 'PROMOTE', 'REJECT')),
    locked_reason TEXT,
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- T11: Admission Gate Candidates
CREATE TABLE fhq_learning.admission_gate_candidates (
    candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_mtm_id UUID REFERENCES fhq_memory.mtm_quarantine(mtm_id),
    candidate_type VARCHAR(50) NOT NULL,
    candidate_payload JSONB NOT NULL,
    proposed_target VARCHAR(50) NOT NULL
        CHECK (proposed_target IN ('LPM', 'ALPHA_GRAPH')),
    bss_check_passed BOOLEAN,
    bss_regimes_tested TEXT[],
    bss_values JSONB,
    lvi_check_passed BOOLEAN,
    lvi_baseline NUMERIC,
    lvi_candidate NUMERIC,
    evidence_chain_exists BOOLEAN,
    evidence_bundle_id UUID,
    falsifiability_check BOOLEAN,
    torture_test_passed BOOLEAN,
    torture_test_results JSONB,
    asrp_bound BOOLEAN NOT NULL DEFAULT false,
    overall_result VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (overall_result IN ('PENDING', 'PASS', 'FAIL', 'BLOCKED')),
    failure_reasons TEXT[],
    evaluated_at TIMESTAMPTZ,
    evaluated_by TEXT,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- T12: Admission Gate Audit Trail
CREATE TABLE fhq_learning.admission_gate_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID REFERENCES fhq_learning.admission_gate_candidates(candidate_id),
    gate_name VARCHAR(50) NOT NULL,
    gate_result VARCHAR(10) NOT NULL CHECK (gate_result IN ('PASS', 'FAIL', 'SKIP')),
    gate_details JSONB NOT NULL,
    failure_reason TEXT,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    evaluated_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_by TEXT NOT NULL
);

-- T13: Memory Contamination Events
CREATE TABLE fhq_governance.memory_contamination_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contamination_type VARCHAR(50) NOT NULL,
    trigger_description TEXT NOT NULL,
    source_agent VARCHAR(50),
    source_table TEXT,
    target_table TEXT,
    severity VARCHAR(20) NOT NULL DEFAULT 'CRITICAL',
    defcon_escalation_triggered BOOLEAN NOT NULL DEFAULT false,
    admission_gate_locked BOOLEAN NOT NULL DEFAULT false,
    mtm_promotions_frozen BOOLEAN NOT NULL DEFAULT false,
    resolution_status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
        CHECK (resolution_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'FALSE_POSITIVE')),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    evidence_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- T14: Consolidation Policy Registry
CREATE TABLE fhq_learning.consolidation_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lpm_id UUID REFERENCES fhq_memory.lpm_canonical(lpm_id),
    regime_tag TEXT NOT NULL,
    causal_node_id UUID,
    evidence_bundle_id UUID NOT NULL,
    ewc_weight NUMERIC,
    consolidation_method VARCHAR(50) NOT NULL DEFAULT 'EWC',
    replay_validated BOOLEAN NOT NULL DEFAULT false,
    replay_validation_at TIMESTAMPTZ,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- T15: Promotion Ledger (canonical record of all promotions)
CREATE TABLE fhq_learning.promotion_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES fhq_learning.admission_gate_candidates(candidate_id),
    source_mtm_id UUID REFERENCES fhq_memory.mtm_quarantine(mtm_id),
    target_lpm_id UUID REFERENCES fhq_memory.lpm_canonical(lpm_id),
    target_alpha_node_id UUID,
    promotion_type VARCHAR(50) NOT NULL,
    bss_at_promotion NUMERIC NOT NULL,
    lvi_at_promotion NUMERIC NOT NULL,
    evidence_bundle_hash TEXT NOT NULL,
    admission_gate_hash TEXT NOT NULL,
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,
    promoted_at TIMESTAMPTZ DEFAULT NOW(),
    promoted_by TEXT NOT NULL,
    signature TEXT NOT NULL
);
```

---

## 4. PYTHON MODULES (7 new files)

### 4.1 `asrp_binder.py` (Shared Utility)
- Extract ASRP binding logic from `court_proof_enforcer_v2.py`
- Functions: `get_state_snapshot()`, `compute_hash()`, `bind_artifact()`, `verify_binding()`
- Used by ALL new modules

### 4.2 `memory_domain_manager.py` (MemoryOS Core)
- Register/manage STM, MTM, LPM domains
- STM lifecycle: create -> TTL expiry -> delete
- MTM quarantine: create -> tag experimental -> freeze timer -> eligible for review
- LPM: write-protected store, only writable via Admission Gate
- Containment firewall enforcement

### 4.3 `mtm_quarantine_daemon.py` (Scheduled Daemon)
- Runs on schedule (every 30 min via Windows Task Scheduler)
- Monitors MTM quarantine timers
- Marks entries eligible for review at 72h
- Expires stale MTM entries
- Heartbeat to `fhq_monitoring.daemon_health`

### 4.4 `containment_firewall_daemon.py` (Scheduled Daemon)
- Validates no MTM content has reached canonical tables
- Scans for side-channel violations
- Logs all checks to `containment_firewall_log`
- DEFCON escalation on violation

### 4.5 `invariant_core_manager.py` (Invariant Core)
- Define invariant candidates
- Map to Alpha Graph nodes
- Freeze/unfreeze (unfreeze requires G4)
- BSS-gated expansion gate

### 4.6 `admission_gate_engine.py` (Learning Admission Gate)
- Central gate daemon
- 5-check pipeline: BSS > 0 (2+ regimes) -> LVI improves -> Evidence chain -> Torture tests -> ASRP binding
- State machine: OPEN -> REVIEW -> PROMOTE/REJECT
- Kill-switch: auto-LOCK on contamination
- Writes to `admission_gate_candidates`, `admission_gate_audit`, `promotion_ledger`
- Writes to `fhq_memory.lpm_canonical` on successful promotion

### 4.7 `stress_harness_runner.py` (Stress Testing)
- Builds reproducible crisis replay datasets (GFC 2008, COVID 2020, etc.)
- Runs invariant set through crisis periods
- Measures drift and BSS stability
- Produces signed evidence bundles

---

## 5. RUNBOOK EXECUTION PLAN (Day 41-60)

### Phase 1: MemoryOS + Containment (Runbooks 41-47)

| Runbook | Day | Date | Deliverable | Tables | Code |
|---------|-----|------|-------------|--------|------|
| 41 | 41 | 2026-02-10 | Memory Domain Spec + access controls | `memory_domains` | `memory_domain_manager.py` (domain registration) |
| 42 | 42 | 2026-02-11 | STM lifecycle proof | `stm_store` | `memory_domain_manager.py` (STM methods) |
| 43 | 43 | 2026-02-12 | MTM quarantine proof + **read-side containment** | `mtm_quarantine` | `memory_domain_manager.py` (MTM methods + bilateral firewall) |
| 44 | 44 | 2026-02-13 | Side-channel test suite | `containment_firewall_log` | `containment_firewall_daemon.py` |
| 45 | 45 | 2026-02-14 | Titans/MIRAS as MTM-only writers | - | `memory_domain_manager.py` (non-canonical producer API) |
| 46 | 46 | 2026-02-15 | Freeze scheduler + eval cycle | - | `mtm_quarantine_daemon.py` |
| 47 | 47 | 2026-02-16 | First freeze audit | - | Audit script + signed report |

### Phase 2: Invariant Core + Causal Kernel (Runbooks 48-54)

| Runbook | Day | Date | Deliverable | Tables | Code |
|---------|-----|------|-------------|--------|------|
| 48 | 48 | 2026-02-17 | Invariant candidate list v1 | `invariant_core_registry` | `invariant_core_manager.py` (candidate definition) |
| 49 | 49 | 2026-02-18 | Alpha Graph node mapping | - | `invariant_core_manager.py` (graph mapping) |
| 50 | 50 | 2026-02-19 | Graph Freeze v1 + lock proof | - | `invariant_core_manager.py` (freeze logic) |
| 51 | 51 | 2026-02-20 | Stress dataset harness | `stress_harness_results` | `stress_harness_runner.py` |
| 52 | 52 | 2026-02-21 | BSS baseline report | `bss_baseline_registry` | BSS computation script |
| 53 | 53 | 2026-02-22 | LVI baseline + metric spec | - | LVI measurement definition |
| 54 | 54 | 2026-02-23 | GEX constraint integration | - | GEX as invariant test input |

### Phase 3: Admission Gate + Consolidation (Runbooks 55-60)

| Runbook | Day | Date | Deliverable | Tables | Code |
|---------|-----|------|-------------|--------|------|
| 55 | 55 | 2026-02-24 | Admission Gate arch + states | `admission_gate_state`, `admission_gate_candidates`, `admission_gate_audit` | `admission_gate_engine.py` (architecture) |
| 56 | 56 | 2026-02-25 | Torture test suite | - | `admission_gate_engine.py` (adversarial tests) |
| 57 | 57 | 2026-02-26 | ASRP binding enforcement | - | `asrp_binder.py` + negative test proofs |
| 58 | 58 | 2026-02-27 | Consolidation policy | `consolidation_policy`, `promotion_ledger` | EWC + regime tags + graph IDs |
| 59 | 59 | 2026-02-28 | Controlled promotion | `lpm_canonical` entries | Promotion execution |
| 60 | 60 | 2026-03-01 | Meta-review + readiness pack | - | Day 60 Readiness Pack |

---

## 6. INVARIANT CORE: INITIAL 7 CANDIDATES

Based on existing data infrastructure and economic first principles:

| # | Invariant | Type | Source Table | Rationale |
|---|-----------|------|-------------|-----------|
| 1 | GEX (Gamma Exposure) | Positioning | `fhq_macro.canonical_features` | Market maker hedging creates predictable price magnetism |
| 2 | VIX Term Structure | Volatility | `fhq_macro.canonical_features` | Contango/backwardation signals regime transitions |
| 3 | Fed Funds Rate Expectations | Macro/Rate | `fhq_macro.canonical_features` | Rate trajectory drives equity valuations |
| 4 | Credit Spreads (HY-IG) | Credit/Liquidity | `fhq_macro.canonical_features` | Credit stress precedes equity drawdowns |
| 5 | USD Liquidity (TGA + RRP) | Macro/Liquidity | `fhq_macro.canonical_features` | Aggregate liquidity drives risk appetite |
| 6 | BTC Realized Vol / Implied Vol | Crypto Volatility | `fhq_research.btc_trading_signals` | Regime signal for crypto universe |
| 7 | Put/Call Ratio (Equity) | Sentiment/Positioning | `fhq_macro.canonical_features` | Extreme readings signal crowded positioning |

These are falsifiable, economically grounded, and measurable. Each has a clear causal mechanism.

---

## 7. ADMISSION GATE: 5-CHECK PIPELINE

```
Candidate (from MTM, 72h quarantined)
  |
  v
[Gate 1: BSS Check]
  - BSS > 0 across >= 2 distinct regimes
  - Uses fhq_governance.brier_score_ledger + fhq_research.fss_computation_log
  |
  v
[Gate 2: LVI Improvement]
  - LVI with candidate > LVI baseline
  - Uses fhq_governance.lvi_canonical
  |
  v
[Gate 3: Evidence Chain (ADR-020)]
  - Economic logic documented
  - Falsifiability statement exists
  - Evidence bundle signed
  |
  v
[Gate 4: Adversarial Torture Tests]
  - Overfit detection (deflated Sharpe, PBO)
  - Leakage test (no future data contamination)
  - Regime inversion test (survives regime changes)
  - Spurious causality test (Granger/PCMCI validation)
  - Stop-loss criteria not breached
  |
  v
[Gate 5: ASRP Binding]
  - state_snapshot_hash present and valid
  - state_timestamp current
  - agent_id matches authorized agent
  - Hash verification passes
  |
  v
PROMOTE (write to LPM + promotion_ledger)
  or
REJECT (with full audit trail)
```

---

## 8. SAFETY: CONTAMINATION KILL-SWITCH

### Trigger Conditions (any one -> fail-closed)

1. Promotion attempt without Admission Gate record
2. Missing ASRP binding fields on any admission artifact
3. Hash mismatch / torn read of ASRP state vector
4. Evidence chain missing or unsigned
5. Drift threshold breach for memory subsystem outputs
6. Direct write to LPM bypassing Admission Gate
7. MTM content detected in canonical_features, regime_state, or exposure tables

### Kill-Switch Actions (atomic)

1. Set `admission_gate_state.gate_status = 'LOCKED'`
2. Freeze all MTM -> LPM promotions
3. Log to `fhq_governance.memory_contamination_events`
4. DEFCON escalation per ADR-016
5. Alert to daemon_health with `status = 'BREACH'`

### Recovery

Requires G4-level CEO directive to:
1. Investigate contamination source
2. Remediate affected data
3. Unlock Admission Gate

---

## 9. EVIDENCE BUNDLE STANDARD (Per Runbook)

Each runbook produces:
```json
{
  "runbook_id": "RB-{N}",
  "objective": "...",
  "changes_made": ["..."],
  "tests_executed": ["..."],
  "result": "PASS|FAIL",
  "evidence_bundle_ref": "evidence/{FILENAME}.json",
  "asrp_snapshot": {
    "state_snapshot_hash": "sha256:...",
    "state_timestamp": "...",
    "agent_id": "STIG"
  },
  "defcon_at_execution": "YELLOW",
  "signed_at": "...",
  "signed_by": "STIG"
}
```

Stored in: `03_FUNCTIONS/evidence/MEMORY_ADMISSION_RB{N}_{YYYYMMDD}.json`

---

## 9B. RB-43 READ-SIDE CONTAINMENT PLAN

### Problem
The CEO checklist requires bilateral containment:
- STM cannot be queried by canonical services (IoS-003, IoS-004)
- MTM readable only by research layer
- MTM not accessible by IoS-003 (regime) or IoS-004 (exposure)

Current containment only blocks WRITES from memory -> canonical. It does not block READS from canonical services -> memory.

### Implementation (RB-43 Scope)

**Layer 1: Database Role Isolation**
```sql
-- Create restricted role for canonical pipeline services
CREATE ROLE fhq_canonical_pipeline NOLOGIN;
REVOKE ALL ON ALL TABLES IN SCHEMA fhq_memory FROM fhq_canonical_pipeline;
-- canonical services use this role; memory services use fhq_memory_writer role
```

**Layer 2: Service-Layer Access Control Table**
```sql
CREATE TABLE fhq_memory.access_control_registry (
    acl_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_name VARCHAR(10) NOT NULL REFERENCES fhq_memory.memory_domains(domain_name),
    allowed_reader VARCHAR(50) NOT NULL,
    reader_type VARCHAR(20) NOT NULL CHECK (reader_type IN ('AGENT', 'DAEMON', 'LAYER')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- Seed: MTM readable by FINN, CEIO, research daemons only
-- STM readable by owning agent session only
-- LPM readable by all (it's canonical)
```

**Layer 3: Containment Firewall Extension**
Extend `check_containment()` to also validate READ operations:
```python
# In memory_domain_manager.py
FORBIDDEN_READERS = {
    'STM': {'ios003_regime', 'ios004_exposure', 'ios006_features'},
    'MTM': {'ios003_regime', 'ios004_exposure', 'ios006_features'},
    'LPM': set()  # LPM is canonical, readable by all
}
```

**Layer 4: Audit Trail**
Every read from STM/MTM by a non-authorized service is logged to `containment_firewall_log` with `event_type='UNAUTHORIZED_READ_ATTEMPT'` and triggers DEFCON escalation.

### Tests (RB-43 Fail Criteria)
1. Simulate IoS-003 reading MTM -> must be BLOCKED
2. Simulate IoS-004 reading STM -> must be BLOCKED
3. Research layer reading MTM -> must be ALLOWED
4. Any agent reading LPM -> must be ALLOWED

### Deferred Fixes (Post RB-47 Batch)
- Avvik #1: Evidence bundle field name normalization
- Avvik #2: STM session-end auto-delete
- Avvik #5: evidence_bundle_id as UUID

---

## 10. RISK ASSESSMENT

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Stale ASRP state (last entry 2025-12-10) | HIGH | MEDIUM | First runbook reactivates ASRP logging |
| BSS impossible with current FSS (-1.295) | HIGH | HIGH | BSS baseline computed from existing data; no promotions until FSS improves |
| LVI = 0.0 means Gate 2 cannot pass | HIGH | HIGH | LVI baseline measurement first; improvement is relative to baseline |
| No active hypotheses to promote | HIGH | MEDIUM | Admission Gate exists but is dormant until learning pipeline restarts |
| 1,341 tables - schema complexity risk | MEDIUM | LOW | All new tables in established schemas with FK constraints |
| MIT Quad side-channel creation | LOW | CRITICAL | Containment firewall + database-level write controls |

---

## 11. IMPLEMENTATION ORDER (Today: Day 42)

Today I will implement Runbooks 41+42 (Memory Domain Registration + STM Implementation):

1. Create `asrp_binder.py` (shared utility)
2. Run Phase 1 table migrations (T1: memory_domains, T2: stm_store)
3. Create `memory_domain_manager.py` with domain registration + STM lifecycle
4. Register CEO directive in database
5. Write evidence bundles for RB41 + RB42
6. Create DAY42_RUNBOOK_20260211.md

Subsequent days follow the runbook schedule above.

---

## 12. ACCEPTANCE CRITERIA (Day 60 Checklist)

- [ ] MemoryOS exists with STM/MTM/LPM separation and write controls
- [ ] MTM quarantine works; LPM is write-protected
- [ ] Admission Gate exists and is the only promotion path
- [ ] Promotions are ASRP-bound and fail closed on any mismatch
- [ ] Invariant core frozen and graph expansion gated by BSS improvement
- [ ] SitC and InForage logs exist for all deep-research work
- [ ] DEFCON behavior enforced on breach conditions
- [ ] No canonical side-channel exists (pipeline invariant preserved)
- [ ] All 20 evidence bundles signed and stored
- [ ] Promotion ledger operational
- [ ] Kill-switch tested and verified

---

**Plan prepared by STIG. Awaiting G4 approval to begin implementation.**
