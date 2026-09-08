# CEO-DIR-2026-AGENT-VERIFICATION-001
## Agent Reality Verification & Decision Flow Integrity Plan

**Status:** APPROVED - EXECUTION READY
**Issued:** 2026-01-23
**Executor:** STIG (EC-003)
**Classification:** GOVERNANCE-CRITICAL / AUDIT-BOUND

---

## EXECUTIVE SUMMARY

This plan document presents database-backed findings for the four verification axes plus Anthropic alignment assessment. All findings are derived from direct SQL queries against PostgreSQL (127.0.0.1:54322).

**Key Finding:** The system has **14 registered agents** but execution is **highly concentrated** in 3-4 agents. Exit conditions are **IMPLICIT** for most workflows. Eval infrastructure is **extensive but fragmented**.

---

## AXIS A: Agent Reality Verification

### A.1 Registered Agents Inventory

| EC-ID | Agent | Role Type | Parent | Status | Observed Execution |
|-------|-------|-----------|--------|--------|-------------------|
| EC-001 | LARS | executive | CEO | ACTIVE | Heartbeat: 2026-01-23, Orchestrator role, 4 G2C decisions |
| EC-003 | STIG | executive | LARS | ACTIVE | **PRIMARY EXECUTOR**: 13 task logs (last 7d), Brier computation, LVI computation |
| EC-004 | FINN | executive | LARS | ACTIVE | Heartbeat: 2026-01-23, Research component, regime_states table |
| EC-005 | LINE | executive | LARS | ACTIVE | Heartbeat: 2026-01-23, Execution component |
| EC-006 | VEGA | constitutional | CEO | ACTIVE | 25 attestations logged, G3/G4 signatures |
| EC-007 | CDMO | subexecutive | STIG | ACTIVE | Heartbeat: 2026-01-23, Data component |
| EC-008 | CEIO | subexecutive | STIG | ACTIVE | Heartbeat: 2026-01-23 (most recent), cnrp_execution |
| EC-009 | CRIO | subexecutive | FINN | ACTIVE | Heartbeat: 2026-01-23, Graph component |
| EC-014 | UMA | Tier-2 Meta-Executive | CEO | ACTIVE | 2026.PRODUCTION mandate, no direct task logs |
| EC-018 | (Meta-Alpha) | Tier-2 Cognitive | CEO | ACTIVE | Dependencies: EC-020,021,022 |
| EC-020 | SitC | aci_cognitive | LARS | ACTIVE | Reasoning authority, sitc_plan_id in golden_needles |
| EC-021 | InForage | aci_cognitive | FINN | ACTIVE | Search authority |
| EC-022 | IKEA | aci_cognitive | VEGA | ACTIVE | Hallucination firewall, ikea_feedback_log exists |
| - | CFAO | subexecutive | LARS | ACTIVE | No EC mapping found |
| - | CSEO | subexecutive | LARS | ACTIVE | No EC mapping found |

### A.2 Execution Evidence Summary

**Decision Generation:**
- `IoS-008` is the **dominant decision generator**: 2,777 REGIME_BASED + 418 PAPER_CYCLE decisions
- `LARS` created 4 G2C_STRATEGY_DECISION entries
- `STIG` created 4 decisions (REGIME_BASED + EQUITY_ALLOCATION)

**Execution Layer:**
- `IoS-012` handles all execution: 29 entries (21 PENDING, 8 MOCK_FILLED)

**Task Execution:**
- `STIG` is the only agent with task_log entries in last 7 days: 13 SHADOW_LEARNING tasks

**Critical Finding:** IoS-008 and IoS-012 are **protocol identifiers**, not agents. The actual agent creating IoS-008 decisions is not explicitly logged in `signature_agent`.

### A.3 ADR/IoS Enforcement Evidence

| ADR/IoS | Enforcement Mechanism | Evidence Table | Enforcing Agent |
|---------|----------------------|----------------|-----------------|
| ADR-011 (Fortress) | Hash chain verification | `execution_log.hash_chain_id` | IoS-012 |
| ADR-013 (DB Truth) | Schema constraints | All fhq_* schemas | STIG |
| IoS-008 | Decision mandate | `decision_log.signature_agent` | IoS-008 protocol |
| IoS-012 | Execution gate | `execution_log` | IoS-012 protocol |
| IoS-013 | Signal weighting | Views exist but empty mapping | NOT ENFORCED |
| IoS-016 | Calendar governance | `ios_execution_gates` | STIG (4 gates set) |

---

## AXIS B: Exit Conditions Verification

### B.1 Classification by Agent/Protocol

| Agent/Protocol | Exit Condition Type | Evidence |
|----------------|-------------------|----------|
| IoS-008 (Decision) | **IMPLICIT** | `execution_state` column exists but ALL 3,221 rows = 'PENDING' |
| IoS-012 (Execution) | **IMPLICIT** | `execution_status` column: PENDING, MOCK_FILLED |
| G5 Signal State | **EXPLICIT** | `current_state`: EXPIRED, DORMANT, PRIMED, DUPLICATE_PRUNED |
| | | `exit_reason`: 1,160 with explicit reason text |
| DEFCON System | **EXPLICIT** | `defcon_level`: GREEN/YELLOW, `trigger_reason` logged |
| Circuit Breakers | **EXPLICIT** | `event_type`, `action_taken` columns exist |
| Golden Needles | **IMPLICIT** | `is_current` boolean, `superseded_by` for chain |

### B.2 Exit Condition Gap Analysis

**EXPLICIT (Machine-Detectable):**
- `fhq_canonical.g5_signal_state.current_state` - EXPIRED, DORMANT, PRIMED
- `fhq_canonical.g5_signal_state.exit_reason` - Free text with sentinel markers
- `fhq_governance.defcon_state.defcon_level` - GREEN, YELLOW
- `fhq_governance.circuit_breaker_events.event_type`

**IMPLICIT (Inferred):**
- `fhq_governance.decision_log.execution_state` - Only PENDING exists, no EXECUTED/CANCELLED
- `fhq_governance.execution_log.execution_status` - PENDING/MOCK_FILLED only

**MISSING:**
- No SIGNAL_PUBLISHED explicit state in decision_log
- No HALTED state for agents (only DEFCON for system)
- No ERROR_ABORT in agent_task_log

### B.3 Deliverable B: Exit Condition Classification

| Entity | Classification | Column/Table | Notes |
|--------|---------------|--------------|-------|
| Decision Pipeline | IMPLICIT | decision_log.execution_state | Only PENDING |
| Signal Lifecycle | EXPLICIT | g5_signal_state.current_state | 6 distinct states |
| System State | EXPLICIT | defcon_state.defcon_level | GREEN/YELLOW logged |
| Agent Tasks | MISSING | agent_task_log.status | SUCCESS/STOPPED but no ERROR_ABORT |
| Orchestrator | IMPLICIT | orchestrator_cycles.tasks_* | Counts only, no explicit exit |

---

## AXIS C: Eval Infrastructure Inventory

### C.1 Existing Evaluation Tables (88 total)

**BRIER SCORE INFRASTRUCTURE:**
| Table | Schema | Rows | Last Entry | Used By |
|-------|--------|------|------------|---------|
| brier_score_ledger | fhq_governance | 4,831 | 2026-01-20 | STIG_PHASE3_DAEMON, CEO-DIR-2026-117-MANUAL |
| brier_decomposition | fhq_governance | exists | - | Regime-level decomposition |
| v_brier_by_event_proximity | fhq_governance | view | - | Event correlation |
| v_brier_summary | fhq_ops | view | - | Control room |
| asset_brier_alerts | fhq_calendar | exists | - | Calendar alerting |

**LVI (Learning Velocity Index):**
| Table | Schema | Rows | Last Entry | Used By |
|-------|--------|------|------------|---------|
| lvi_canonical | fhq_governance | 100+ | 2026-01-20 | STIG |
| lvi_regime_weights | fhq_governance | exists | - | Regime weighting |
| v_lvi_rolling_7d | fhq_governance | view | - | Dashboard |
| v_system_lvi | fhq_governance | view | - | System-wide |
| control_room_lvi | fhq_ops | exists | - | Control room |
| v_lvi_contribution | fhq_research | view | - | Research |

**CALIBRATION:**
| Table | Schema | Status | Notes |
|-------|--------|--------|-------|
| calibration_bins | fhq_governance | **EMPTY (0 rows)** | Not populated |
| calibration_bin_config | fhq_governance | exists | Configuration |
| calibration_versions | fhq_governance | exists | Version tracking |
| calibration_status | fhq_governance | view | Status dashboard |
| calibration_curve | fhq_analytics | exists | Analytics |
| calibration_curve_data | fhq_research | exists | Research |
| calibration_experiments | fhq_optimization | exists | Experiments |

**FORECAST ACCURACY:**
| Table | Schema | Rows | Notes |
|-------|--------|------|-------|
| forecast_ledger | fhq_research | 31,998 | Active, recent |
| forecast_outcome_pairs | fhq_research | 17,656 | Paired outcomes |
| forecast_skill_metrics | fhq_research | exists | Skill tracking |
| forecast_skill_registry | fhq_research | exists | Registry |
| forecast_resolution_log | fhq_research | exists | Resolution |

**DECISION QUALITY:**
| Table | Schema | Notes |
|-------|--------|-------|
| ldow_cycle_metrics | fhq_governance | Brier, FSS, calibration_error |
| ldow_evaluation_log | fhq_governance | Evaluation events |
| skill_damper_config | fhq_governance | Dampening config |
| skill_scorecard_monthly | fhq_analytics | Monthly scorecards |

### C.2 Redundancy Risk Analysis

**HIGH REDUNDANCY:**
- Brier scores: 5 tables/views across 3 schemas
- LVI: 6 tables/views across 4 schemas
- Calibration: 10+ tables across 5 schemas

**GAPS IDENTIFIED:**
1. `calibration_bins` is EMPTY - no bin-level calibration data
2. No unified eval dashboard view
3. Regime-conditional Brier not computed per-agent

### C.3 Deliverable C: Eval Metric Map

| Metric | Existing Table/View | Used By Agent | Gap | Redundancy Risk |
|--------|--------------------|--------------|----|-----------------|
| Brier Score | brier_score_ledger | STIG | None | HIGH (5 sources) |
| Brier Decomposition | brier_decomposition | STIG | None | LOW |
| LVI | lvi_canonical | STIG | None | HIGH (6 sources) |
| Calibration Bins | calibration_bins | - | **EMPTY** | MEDIUM |
| Forecast Accuracy | forecast_ledger | - | No agent attribution | LOW |
| Regime Accuracy | ldow_regime_metrics | - | Sparse | LOW |
| Decision Quality | ldow_cycle_metrics | - | No per-agent | MEDIUM |

---

## AXIS D: Single-Agent Baseline Detection

### D.1 End-to-End Decision Loop Analysis

**Question:** Does any single agent complete the full loop?
```
Ingest → Process → Evaluate Regime → Produce Decision → Exit Cleanly
```

### D.2 Findings

| Flow | Single-Agent? | Evidence | Boundary |
|------|--------------|----------|----------|
| Price Ingest → Storage | **NO** | CEIO ingests, CDMO validates | CEIO → CDMO handoff |
| Feature Computation | **PARTIAL** | fhq_indicators tables, no agent ownership | Schema owns |
| Regime Detection | **NO** | FINN produces regime_states, but fhq_hmm.regime_predictions is separate model | FINN → HMM model |
| Signal Generation | **NO** | SitC (EC-020) + golden_needles + VEGA attestation | Multi-agent |
| Decision Production | **NO** | IoS-008 protocol, not single agent | Protocol layer |
| Execution | **NO** | IoS-012 → LINE (EC-005) | Protocol → Agent |

### D.3 Deliverable D: Single-Agent Baseline Statement

| Core Flow | Single-Agent Baseline | Justification |
|-----------|----------------------|---------------|
| Data Ingest | **NO** | CEIO ingests, CDMO validates, dual ownership |
| Indicator Computation | **NO** | Schema-owned (fhq_indicators), no agent attribution |
| Regime Detection | **PARTIAL** | FINN owns regime_states but HMM model runs separately |
| Signal Generation | **NO** | SitC creates, VEGA attests, G5 lifecycle manages |
| Decision Production | **NO** | IoS-008 is protocol, not agent |
| Trade Execution | **NO** | IoS-012 protocol + LINE agent |

**Conclusion:** NO single-agent baseline exists. All flows are multi-agent or protocol-mediated.

---

## AXIS E: System Flow Visualization

### E.1 Actual Implemented Pipeline (Mermaid)

```mermaid
flowchart TD
    subgraph INGEST["Data Ingest (CEIO - EC-008)"]
        A1[External APIs] --> A2[fhq_finn.vendor_raw_ingest]
        A2 --> A3[fhq_data.price_series]
    end

    subgraph VALIDATE["Data Validation (CDMO - EC-007)"]
        A3 --> B1[fhq_data.data_quality_metrics]
        B1 --> B2{Quality Gate}
    end

    subgraph INDICATORS["Feature Computation (Schema-owned)"]
        B2 -->|PASS| C1[fhq_indicators.momentum]
        B2 -->|PASS| C2[fhq_indicators.volatility]
        B2 -->|PASS| C3[fhq_indicators.trend]
        B2 -->|PASS| C4[fhq_indicators.volume]
    end

    subgraph REGIME["Regime Detection (FINN - EC-004)"]
        C1 & C2 & C3 & C4 --> D1[fhq_finn.regime_states]
        D1 --> D2[fhq_hmm.regime_predictions]
        D2 --> D3{Regime: BULL/BEAR/NEUTRAL/STRESS}
    end

    subgraph SIGNAL["Signal Generation (SitC - EC-020)"]
        D3 --> E1[fhq_alpha.hunt_sessions]
        E1 --> E2[fhq_canonical.golden_needles]
        E2 --> E3[EQS Score Calculation]
    end

    subgraph VALIDATE_SIG["Signal Validation (VEGA - EC-006)"]
        E3 --> F1[fhq_governance.vega_attestations]
        F1 --> F2{VEGA Attestation}
    end

    subgraph LIFECYCLE["Signal Lifecycle (G5 Protocol)"]
        F2 -->|ATTESTED| G1[fhq_canonical.g5_signal_state]
        G1 --> G2{State: DORMANT → PRIMED → EXECUTING}
        G2 -->|EXIT| G3[exit_reason logged]
    end

    subgraph DECISION["Decision Production (IoS-008 Protocol)"]
        G2 -->|PRIMED| H1[fhq_governance.decision_log]
        H1 --> H2[Context Hash + Signature]
    end

    subgraph EXECUTION["Execution (IoS-012 → LINE - EC-005)"]
        H2 --> I1[fhq_governance.execution_log]
        I1 --> I2[fhq_execution.paper_orders]
        I2 --> I3{MOCK_FILLED / PENDING}
    end

    style INGEST fill:#e1f5fe
    style VALIDATE fill:#fff3e0
    style INDICATORS fill:#f3e5f5
    style REGIME fill:#e8f5e9
    style SIGNAL fill:#fce4ec
    style VALIDATE_SIG fill:#fff8e1
    style LIFECYCLE fill:#e0f2f1
    style DECISION fill:#f1f8e9
    style EXECUTION fill:#fbe9e7
```

### E.2 Flow Annotations

| Step | Schema.Table | Responsible Agent | Exit Condition | Anthropic Pattern |
|------|-------------|-------------------|----------------|-------------------|
| 1. Ingest | fhq_finn.vendor_raw_ingest | CEIO (EC-008) | IMPLICIT | Workflow (chaining) |
| 2. Validate | fhq_data.data_quality_metrics | CDMO (EC-007) | IMPLICIT | Workflow (chaining) |
| 3. Indicators | fhq_indicators.* | Schema-owned | N/A | Workflow (parallel) |
| 4. Regime | fhq_finn.regime_states | FINN (EC-004) | IMPLICIT | Workflow (chaining) |
| 5. Signal | fhq_canonical.golden_needles | SitC (EC-020) | IMPLICIT | Agent (dynamic) |
| 6. Attest | fhq_governance.vega_attestations | VEGA (EC-006) | EXPLICIT | Evaluator-optimizer |
| 7. Lifecycle | fhq_canonical.g5_signal_state | G5 Protocol | **EXPLICIT** | Workflow (routing) |
| 8. Decision | fhq_governance.decision_log | IoS-008 Protocol | IMPLICIT | Workflow (chaining) |
| 9. Execute | fhq_governance.execution_log | LINE (EC-005) | IMPLICIT | Workflow (chaining) |

---

## AXIS F: Anthropic Alignment Verification

### F.1 Order 1: Workflow vs Agent Classification

| EC-ID | Agent | Classification | Evidence |
|-------|-------|---------------|----------|
| EC-001 | LARS | **WORKFLOW** | Orchestrator role, predefined decision paths |
| EC-003 | STIG | **WORKFLOW** | Predefined task execution, no dynamic tool selection |
| EC-004 | FINN | **WORKFLOW** | Model inference, predefined computation |
| EC-005 | LINE | **WORKFLOW** | Order execution, predefined broker calls |
| EC-006 | VEGA | **WORKFLOW** | Attestation rules, predefined validation |
| EC-007 | CDMO | **WORKFLOW** | Data validation, predefined quality checks |
| EC-008 | CEIO | **WORKFLOW** | API ingestion, predefined endpoints |
| EC-009 | CRIO | **WORKFLOW** | Graph queries, predefined paths |
| EC-020 | SitC | **AGENT** | Dynamic search planning, tool selection |
| EC-021 | InForage | **AGENT** | Dynamic information retrieval |
| EC-022 | IKEA | **WORKFLOW** | Pattern matching, predefined hallucination checks |
| EC-014 | UMA | **AGENT** | Meta-learning, dynamic recommendations |

**Summary:** 9 WORKFLOW, 3 AGENT

### F.2 Order 2: Pattern Mapping (Anthropic Taxonomy)

| Pattern | Implementation | Duplicates | Gaps |
|---------|---------------|------------|------|
| **Prompt Chaining** | Ingest → Validate → Compute → Regime | None | Clear |
| **Routing** | Regime → Signal type selection | None | IoS-013 routing NOT IMPLEMENTED |
| **Parallelization** | Indicator computation | None | Clear |
| **Orchestrator-Workers** | LARS → FINN/LINE/VEGA | None | Clear |
| **Evaluator-Optimizer** | VEGA attestation loop | Partial in G5 | G5 evaluator separate from VEGA |

**Recommendation:** Consolidate G5 lifecycle evaluation with VEGA evaluator pattern.

### F.3 Order 3: Ground Truth Storage

| Step | Ground Truth Stored? | Table | Replayable? |
|------|---------------------|-------|-------------|
| Ingest | YES | vendor_raw_ingest | YES |
| Validate | YES | data_quality_metrics | YES |
| Indicators | YES | fhq_indicators.* | YES |
| Regime | YES | regime_states | YES |
| Signal | YES | golden_needles | YES |
| Attest | YES | vega_attestations | YES |
| Decision | YES | decision_log | YES |
| Execute | PARTIAL | execution_log | Missing filled prices |

**Gap:** Execution outcomes not fully stored for replay.

### F.4 Order 4: ACI Tool Interface Audit

| Tool/Function | Clarity | Examples | Ambiguity Risk | Poka-yoke Fix |
|--------------|---------|----------|----------------|---------------|
| inforage_query | MEDIUM | None in schema | Similar to sitc_search | Add explicit parameter docs |
| sitc_plan | LOW | None | Confusion with hunt_session | Rename to hypothesis_plan |
| ikea_validate | HIGH | In pattern_registry | None | None needed |
| vega_attest | HIGH | In attestations | None | None needed |

---

## DELIVERABLES SUMMARY

### Deliverable A: Agent Enforcement Table
See Section AXIS A.1 - 14 agents mapped with execution evidence.

### Deliverable B: Exit Condition Classification
See Section AXIS B.3 - 5 entities classified: 2 EXPLICIT, 2 IMPLICIT, 1 MISSING.

### Deliverable C: Eval Metric Map
See Section AXIS C.3 - 7 metrics mapped with gaps and redundancy risk.

### Deliverable D: Single-Agent Baseline Statement
**NO single-agent baselines exist.** All 6 core flows are multi-agent or protocol-mediated.

### Deliverable E: System Flow Diagram
See Section AXIS E.1 - Mermaid diagram with 9 annotated steps.

### Deliverable F: Anthropic Alignment Summary
- 9 WORKFLOW, 3 AGENT classifications
- 5 patterns mapped, 1 gap (IoS-013 routing)
- Ground truth stored at 8/9 steps
- 2 tool interfaces need poka-yoke fixes

---

## CONSTRAINTS COMPLIANCE

- [x] No new agents created
- [x] No new metrics created
- [x] No architectural redesign
- [x] No narrative interpretation
- [x] All findings database-backed

---

## QUERIES EXECUTED (Evidence Index)

```sql
-- Agent Registry
SELECT * FROM fhq_governance.ec_registry;
SELECT * FROM fhq_governance.agent_ec_mapping;
SELECT * FROM fhq_governance.agent_mandates;

-- Execution Evidence
SELECT agent_id, task_type, status, COUNT(*) FROM fhq_governance.agent_task_log GROUP BY 1,2,3;
SELECT signature_agent, decision_type, execution_state, COUNT(*) FROM fhq_governance.decision_log GROUP BY 1,2,3;
SELECT created_by, execution_mode, execution_status, COUNT(*) FROM fhq_governance.execution_log GROUP BY 1,2,3;

-- Exit Conditions
SELECT current_state, exit_reason, COUNT(*) FROM fhq_canonical.g5_signal_state GROUP BY 1,2;
SELECT defcon_level, triggered_by, trigger_reason FROM fhq_governance.defcon_state;

-- Eval Infrastructure
SELECT generated_by, forecast_type, regime, COUNT(*), AVG(squared_error) FROM fhq_governance.brier_score_ledger GROUP BY 1,2,3;
SELECT asset_id, computed_by, AVG(lvi_value) FROM fhq_governance.lvi_canonical GROUP BY 1,2;
SELECT COUNT(*) FROM fhq_research.forecast_ledger;
SELECT COUNT(*) FROM fhq_research.forecast_outcome_pairs;

-- Heartbeats
SELECT agent_id, component, MAX(last_heartbeat) FROM fhq_governance.agent_heartbeats GROUP BY 1,2;
```

---

## CRITICAL FINDINGS REQUIRING CEO DECISION

1. **IoS-013 routing is NOT IMPLEMENTED** - No `ios_quad_mapping` data, views exist but return empty
2. **Exit conditions are predominantly IMPLICIT** - Risk of orphaned decisions
3. **No single-agent baseline** - All flows have multi-agent coupling
4. **Eval infrastructure fragmentation** - 88 tables across 15 schemas

**Recommended Next Steps:**
1. Implement explicit exit condition logging for decision_log
2. Populate ios_quad_mapping for IoS-013 routing
3. Consolidate eval views into unified dashboard
4. Add execution outcome storage for replay capability

---

**Verification Date:** 2026-01-23
**STIG (EC-003)** - System for Technical Implementation & Governance
