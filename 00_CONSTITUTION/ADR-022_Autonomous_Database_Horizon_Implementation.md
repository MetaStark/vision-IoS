# ADR-022: The Autonomous Database Horizon Implementation Charter

**ADR-ID:** ADR-022
**Title:** The Autonomous Database Horizon Implementation Charter
**Status:** DRAFT
**Date:** 2026-01-03
**Owner:** STIG (CTO)
**Tier:** 1 (Constitutional)
**Governing Reference:** `00_CONSTITUTION/The Autonomous Database Horizon.md`

---

## EXECUTIVE SUMMARY (CEO Quick Reference)

**Current State:** 78.5% alignment with Autonomous Database Horizon standard
**Target State:** 92% alignment by Q2 2026
**Status:** DRAFT - CEO CORRECTIONS APPLIED

### CEO Corrections Applied (Pillars 1-3)

| Correction | Original | Fixed |
|------------|----------|-------|
| **CoT Storage** | Full CoT in JSONB | Structured Reasoning Artifact + Hash |
| **Refinement Loop** | Best-effort retry | Hard-bound circuit (3 attempts, $0.02, 2.0s) |
| **AIQF** | Undefined | Canonical formula + benchmark registry |
| **Observability** | Q4 2026 | IMMEDIATE (Week 1-2) |
| **EU AI Act** | "Full compliance Aug 2025" | Scoped to DEPLOYER obligations |

### Immediate Priorities (Next 4-6 Weeks)

| Priority | Action | Why Urgent |
|----------|--------|------------|
| **1. Observability Core** | Pillar 1-3 instrumentation | Cannot measure refinement without it |
| **2. SQL Refinement** | Structured artifacts + circuit breaker | 86.6% accuracy with governance |
| **3. EU AI Act** | DEPLOYER inventory | Aug 2025 GPAI obligations active |
| **4. AIQF Benchmark** | 50-query test set | VEGA gate requires defined metric |

### Key Deliverables

- **7 SQL Migrations** (191, 191b, 192-196)
- **14 Python Functions** (STaR-SQL, Circuit Breaker, AIQF, HybridRAG, ABAC, Observability)
- **Complete Document Inventory:** 21 ADRs, 18 IoS, 18 ECs catalogued

### CEO Questions Answered (Section 13)

1. **AIQF Formula:** `(first×0.6) + (within3×0.25) + (semantic×0.1) + (no_escalation×0.05)` ≥ 0.95
2. **Phase 1 Scope:** FINN + STIG agents; `fhq_meta`, `fhq_research`, `fhq_canonical` schemas
3. **Hard Ceilings:** 3 attempts, 4000 tokens, 2.0s latency, $0.02/query, $25/day refinement budget

---

## 1. CONTEXT & DECISION

This ADR establishes the implementation roadmap for achieving full compliance with "The Autonomous Database Horizon" constitutional standard. It consolidates all existing governance documents and defines the path to Phase 3 Autonomous Governance (2026+).

**Decision:** FjordHQ shall implement the Autonomous Database Horizon architecture in three phases, achieving >90% compliance by Q2 2026.

---

## 2. COMPLETE GOVERNANCE DOCUMENT INVENTORY

### 2.1 Architecture Decision Records (ADR-001 to ADR-021)

| ADR | Title | Tier | Owner | Status | Domain |
|-----|-------|------|-------|--------|--------|
| **ADR-001** | System Charter | 1 | CEO | ACTIVE | Constitutional foundation, executive roles |
| **ADR-002** | Audit and Error Reconciliation Charter | 1 | VEGA | ACTIVE | All changes must be logged, audit trails |
| **ADR-003** | Institutional Standards and Compliance Framework | 2 | STIG | ACTIVE | Schema naming, MDLC, compliance |
| **ADR-004** | Change Gates Architecture (G0-G4) | 1 | VEGA | ACTIVE | Approval workflow, gate progression |
| **ADR-005** | Mission & Vision Charter | 1 | CEO | ACTIVE | Strategic direction, purpose |
| **ADR-006** | VEGA Autonomy and Governance Engine Charter | 1 | CEO | ACTIVE | VEGA powers, veto authority |
| **ADR-007** | Orchestrator Architecture | 1 | CEO | ACTIVE | LARS coordination, workflow |
| **ADR-008** | Cryptographic Key Management and Rotation | 1 | STIG | ACTIVE | Ed25519 signing, key ceremonies |
| **ADR-009** | Governance Approval Workflow for Agent Suspension | 2 | VEGA | ACTIVE | Suspension procedures |
| **ADR-010** | State Reconciliation Methodology and Discrepancy Scoring | 2 | STIG | ACTIVE | State consistency, drift detection |
| **ADR-011** | Fortress and VEGA Testsuite | 2 | STIG | ACTIVE | Hash chains, integrity testing |
| **ADR-012** | Economic Safety Architecture | 1 | CEO | ACTIVE | Cost ceilings, API waterfall, budgets |
| **ADR-013** | Canonical ADR Governance and One-True-Source | 2 | STIG | ACTIVE | Single source of truth |
| **ADR-014** | Executive Activation and Sub-Executive Governance | 1 | CEO | ACTIVE | Agent hierarchy, activation |
| **ADR-015** | Meta-Governance Framework for ADR Ingestion | 2 | VEGA | ACTIVE | Document ingestion rules |
| **ADR-016** | DEFCON Circuit Breaker Protocol | 1 | LINE | ACTIVE | Emergency halt, risk levels |
| **ADR-017** | MIT Quad Protocol for Alpha Sovereignty | 1 | CEO | ACTIVE | Alpha signal protection |
| **ADR-018** | Agent State Reliability Protocol (ASRP) | 2 | STIG | ACTIVE | State persistence, recovery |
| **ADR-019** | Human Interaction & Application Layer Charter | 1 | CEO | ACTIVE | Dashboard, user interface |
| **ADR-020** | Autonomous Cognitive Intelligence | 1 | CEO | ACTIVE | ACI framework, FINN-InForage-SitC-IKEA |
| **ADR-021** | Cognitive Engine Architecture Deep Research Protocol | 2 | FINN | ACTIVE | Research methodology |

**Total: 21 ADRs ACTIVE** (11 Tier-1 Constitutional, 10 Tier-2 Operational)

---

### 2.2 Instructions of Service (IoS-001 to IoS-015)

| IoS | Title | Tier | Owner | Status | Domain |
|-----|-------|------|-------|--------|--------|
| **IoS-001** | IoS-001_2026_PRODUCTION | 2 | STIG | ACTIVE | Data ingestion pipeline |
| **IoS-002** | IoS-002 | 2 | STIG | ACTIVE | Signal processing |
| **IoS-003** | IoS-003 | 2 | FINN | ACTIVE | Regime classification |
| **IOS-003-B** | Intraday Regime-Delta (Ephemeral Context Engine) | 2 | FINN | G0_SUBMITTED | Intraday context |
| **IoS-004** | IoS-004 | 2 | FINN | ACTIVE | Alpha generation |
| **IoS-005** | IoS-005 | 2 | FINN | ACTIVE | Signal validation |
| **IoS-006** | Global Macro & Factor Integration Engine | 2 | FINN | ACTIVE | Macro factors, G3 gates |
| **IoS-007** | IoS-007 | 2 | FINN | ACTIVE | Risk assessment |
| **IoS-008** | IoS-008 | 2 | LINE | ACTIVE | Execution protocols |
| **IoS-009** | IoS-009 | 2 | FINN | ACTIVE | Backtesting |
| **IoS-010** | IoS-010 | 2 | FINN | ACTIVE | Portfolio construction |
| **IoS-011** | IoS-011 | 2 | FINN | ACTIVE | Position sizing |
| **IoS-012** | IoS-012 | 2 | LINE | ACTIVE | Order management |
| **IoS-013** | IoS-013 | 3 | FINN | ACTIVE | Research operations |
| **IoS-014** | IoS-014 | 2 | STIG | ACTIVE | Infrastructure ops |
| **IoS-015** | IoS-015 | 2 | FINN | ACTIVE | Learning cycles |
| **G4.2** | Contextual Alpha Orchestration | 2 | - | ACTIVE | G4 gate operations |
| **G5** | Silent Sniper Paper Execution | 2 | - | ACTIVE | Paper trading |

**Total: 17 IoS ACTIVE, 1 G0_SUBMITTED**

---

### 2.3 Employment Contracts (EC-001 to EC-022)

| EC | Title | Tier | Owner | Status | Agent Role |
|----|-------|------|-------|--------|------------|
| **EC-001** | EC-001 | 1 | VEGA | ACTIVE | Chief Governance Officer |
| **EC-002** | EC-002 | 1 | LARS | ACTIVE | Chief Strategy Officer |
| **EC-003** | EC-003 | 2 | STIG | ACTIVE | Chief Technology Officer |
| **EC-004** | EC-004 | 2 | FINN | ACTIVE | Chief Research Officer |
| **EC-005** | EC-005 | 2 | LINE | ACTIVE | Chief Operations Officer |
| **EC-006** | EC-006 | 2 | CSEO | ACTIVE | Chief Security Officer |
| **EC-007** | EC-007 | 2 | CDMO | ACTIVE | Chief Data Management Officer |
| **EC-008** | EC-008 | 2 | FRAMEWORK | FRAMEWORK_CHARTER | Framework specification |
| **EC-009** | EC-009 | 2 | CEIO | ACTIVE | Chief External Intelligence Officer |
| **EC-010** | EC-010 | 2 | CFAO | ACTIVE | Chief Financial Analysis Officer |
| **EC-011** | EC-011 | 3 | CODE | ACTIVE | Development execution |
| **EC-012** | EC-012 | 3 | RESERVED | RESERVED | Future agent slot |
| **EC-013** | EC-013 | 2 | CRIO | ACTIVE | Chief Risk & Intelligence Officer |
| **EC-018** | EC-018 | 2 | CEIO | FROZEN | Meta-Alpha daemon |
| **EC-019** | EC-019 | 1 | CEO | ACTIVE | CEO directives |
| **EC-020** | EC-020_2026_PRODUCTION | 2 | FINN | FROZEN | SitC (Seeing is the Cause) |
| **EC-021** | EC-021_2026_PRODUCTION | 2 | FINN | FROZEN | InForage cost optimization |
| **EC-022** | EC-022_2026_PRODUCTION | 2 | FINN | ACTIVE | IKEA truth boundaries |

**Total: 13 ACTIVE, 3 FROZEN, 1 FRAMEWORK, 1 RESERVED**

**ACI Triangle (Autonomous Cognitive Intelligence):**
- EC-020 (SitC): Reasoning integrity, verification chains
- EC-021 (InForage): Cost optimization, API budget
- EC-022 (IKEA): Truth boundaries, anti-hallucination

---

## 3. DATABASE INFRASTRUCTURE STATUS

### 3.1 Schema Inventory (40 Schemas, 6,989 MB)

| Schema | Tables | Primary Function |
|--------|--------|------------------|
| `fhq_meta` | 140 | Registries, keys, attestations |
| `fhq_governance` | 125 | Governance actions, audit logs |
| `fhq_research` | 121 | Signal discovery, learning |
| `fhq_canonical` | 44 | Golden needles, G4/G5 gates |
| `fhq_alpha` | 34 | Alpha signals, backtesting |
| `fhq_execution` | 33 | Trading, paper orders |
| `fhq_finn` | 25 | FINN cognitive engine |
| `fhq_perception` | 15 | Market perception |
| `fhq_macro` | 15 | Macro indicators |
| `fhq_positions` | 13 | Position tracking |
| `fhq_graph` | 9 | Knowledge graph |
| `fhq_memory` | 7 | Agent memory, embeddings |
| `vision_*` | 40 | Signal verification |

### 3.2 Key Metrics

| Metric | Value |
|--------|-------|
| Golden Needles | 1,765 |
| Evidence Nodes | 29 |
| Graph Nodes | 13 |
| Graph Edges | 18 |
| Embeddings | 5 |
| Financial Ontology | 31 entries |
| Agent Keys | 11 (all Ed25519) |
| VEGA Attestations | 39 |
| Governance Actions | 5,173 |
| API Budget Entries | 34 |
| LLM Routing Logs | 406 |
| DEFCON Status | GREEN |

---

## 4. AUTONOMOUS DATABASE HORIZON ALIGNMENT

### 4.1 Current Alignment Score: 78.5%

| Pillar | Weight | Score | Gap |
|--------|--------|-------|-----|
| AOP Middleware | 15% | 85% | Self-healing queries |
| Multi-Agent Orchestration | 15% | 90% | Differential privacy |
| System 2 Reasoning | 15% | 80% | Reasoning chain population |
| Model Context Protocol | 10% | 70% | MCP gateway, resource registry |
| GraphRAG/HybridRAG | 15% | 75% | Unified pipeline |
| Zero Trust Security | 20% | 85% | Semantic ABAC, firewall |
| Regulatory Governance | 10% | 50% | EU AI Act, FLOP tracking |

### 4.2 Target Alignment: 92% by Q2 2026

---

## 5. IMPLEMENTATION ROADMAP

**Research Foundation:** Based on "Optimalisering av plan.pdf" evaluation with academic references:
- STaR-SQL (ACL 2025): 86.6% execution accuracy via reasoning-driven SQL
- MAGIC (AAAI 2025): Multi-agent self-correction guidelines
- GraphRAG-Bench (2025): Schema-bound accuracy 16% → 90%
- EU AI Act: Effective dates Feb 2025 (prohibitions) and Aug 2025 (full compliance)

### 5.1 Immediate Actions (Next 4-6 Weeks)

#### 5.1.1 Establish Reasoning-Driven SQL Refinement (STaR-SQL + MAGIC)

**Objective:** Implement reasoning-driven, self-correcting SQL generation per Section 2.3, enhanced with STaR-SQL Chain-of-Thought and MAGIC-inspired auto-generated correction guidelines.

**Research Basis:**
- STaR-SQL (ACL 2025): Achieves **86.6% execution accuracy** - 31.6 percentage points above few-shot baseline
- MAGIC (AAAI 2025): Multi-agent system (manager, correction, feedback agents) that automatically generates self-correction guidelines
- Self-healing database platforms: Continuous monitoring with ML-based anomaly detection

**Database Changes (CEO-Corrected v2 - Pre-Implementation Fixes Applied):**

**CEO Pre-Implementation Review Corrections (2026-01-03):**
1. ✅ Latency ceiling: 30s → 2000ms (matches ADR-016 HIGH_LATENCY breaker exactly)
2. ✅ circuit_state default: OPEN → CLOSED (correct circuit breaker semantics)
3. ✅ Schema: fhq_meta → fhq_governance (ADR-016 anchor alignment)
4. ✅ FK constraints: Added for correction_guideline_id, escalation_bundle_id
5. ✅ Reasoning artifact only: No full CoT storage (forensic bundle exception)
6. ✅ No new circuit breaker tables: Reuse existing `fhq_governance.circuit_breakers`
7. ✅ Evidence bundle pattern: Reference `vision_verification.summary_evidence_ledger`

```sql
-- Migration: 191_reasoning_driven_sql_refinement.sql
-- CEO PRE-IMPLEMENTATION REVIEW: 8 corrections applied 2026-01-03 (DB-grounded)
-- SCHEMA: fhq_governance (not fhq_meta) per ADR-016 anchor requirement
-- CIRCUIT BREAKER: Reuse fhq_governance.circuit_breakers (no new tables)

-- First create the evidence_bundle table for FK reference
-- PATTERN: Follows vision_verification.summary_evidence_ledger structure (CEO Directive 2025-12-20)
-- Ensures court-proof evidence chain: raw_query → query_result_hash → query_result_snapshot
CREATE TABLE IF NOT EXISTS fhq_governance.refinement_evidence_bundle (
    bundle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    refinement_id UUID,  -- Back-reference (set after log insert)
    bundle_type VARCHAR(30) CHECK (bundle_type IN ('ESCALATION', 'FORENSIC', 'G4_INCIDENT')),
    raw_cot_preserved TEXT,  -- Only populated for G4 incidents
    preservation_reason TEXT NOT NULL,
    preserved_by VARCHAR(20) NOT NULL,
    -- Court-proof evidence fields (per vision_verification.summary_evidence_ledger pattern)
    raw_query TEXT,  -- The exact SQL that was attempted
    query_result_hash VARCHAR(64),  -- SHA-256 of results for verification
    query_result_snapshot JSONB,  -- Actual data at time of escalation
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE fhq_governance.sql_refinement_log (
    refinement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_query TEXT NOT NULL,

    -- CORRECTED: Structured Reasoning Artifact (not raw CoT)
    -- Full CoT is ephemeral unless G4 incident forces retention
    reasoning_artifact JSONB NOT NULL CHECK (
        reasoning_artifact ? 'intent' AND
        reasoning_artifact ? 'schema_elements' AND
        reasoning_artifact ? 'verification_steps'
    ),
    -- Required artifact structure:
    -- {
    --   "intent": "what the query aims to answer",
    --   "schema_elements": {"tables": [], "columns": []},
    --   "join_plan": "FK path or explicit join keys",
    --   "filters": [],
    --   "aggregation_grain": null|"day"|"ticker"|etc,
    --   "verification_steps": [],
    --   "risk_flags": ["wide_join", "unknown_column_resolved_by_guess", etc]
    -- }
    reasoning_hash VARCHAR(64) NOT NULL,  -- SHA-256 of artifact
    artifact_version INTEGER DEFAULT 1,

    generated_sql TEXT NOT NULL,

    -- Error handling
    error_message TEXT,
    error_type VARCHAR(50),
    error_taxonomy VARCHAR(50),  -- Structured error classification

    -- MAGIC-inspired self-correction (FK ADDED)
    correction_guideline_id UUID REFERENCES fhq_governance.sql_correction_guidelines(guideline_id),
    refined_query TEXT,

    -- CORRECTED: Hard-bound circuit breaker (ADR-012 + ADR-016)
    attempt_number INTEGER DEFAULT 1 CHECK (attempt_number <= 3),
    max_attempts INTEGER DEFAULT 3,
    tokens_consumed INTEGER DEFAULT 0,
    tokens_budget INTEGER DEFAULT 4000,  -- Per-query ceiling
    latency_ms INTEGER,
    latency_budget_ms INTEGER DEFAULT 2000,  -- CORRECTED: 2.0s (matches ADR-016 HIGH_LATENCY breaker)

    -- Circuit breaker status
    -- CORRECTED: Default CLOSED (traffic allowed), OPEN means blocked
    circuit_state VARCHAR(20) DEFAULT 'CLOSED' CHECK (circuit_state IN ('CLOSED', 'OPEN', 'HALF_OPEN')),
    escalated_to_human BOOLEAN DEFAULT FALSE,
    escalation_bundle_id UUID REFERENCES fhq_governance.refinement_evidence_bundle(bundle_id),  -- FK ADDED

    success BOOLEAN DEFAULT FALSE,
    agent_id VARCHAR(20) NOT NULL,

    -- Semantic verification results (not just syntactic)
    semantic_check_passed BOOLEAN,
    semantic_check_details JSONB,  -- FK path plausibility, rowcount bounds, null explosion risk

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Guidelines table (must exist before refinement_log for FK)
CREATE TABLE fhq_governance.sql_correction_guidelines (
    guideline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_pattern VARCHAR(100) NOT NULL,
    correction_template TEXT NOT NULL,

    -- Lifecycle controls (per CEO directive)
    guideline_version INTEGER DEFAULT 1,
    supersedes_guideline_id UUID REFERENCES fhq_governance.sql_correction_guidelines(guideline_id),
    validated_on_benchmark_run_id UUID REFERENCES fhq_governance.aiqf_benchmark_runs(run_id),  -- FK ADDED

    success_rate FLOAT DEFAULT 0.0,
    success_rate_confidence_lower FLOAT,  -- 95% CI lower bound
    usage_count INTEGER DEFAULT 0,

    created_by VARCHAR(20) NOT NULL,

    -- Governance controls
    is_active BOOLEAN DEFAULT TRUE,
    is_global_default BOOLEAN DEFAULT FALSE,  -- Requires VEGA signoff
    vega_signoff_attestation_id UUID REFERENCES fhq_governance.vega_attestations(attestation_id),  -- FK ADDED
    sunset_at TIMESTAMPTZ,  -- Deprecation date
    sunset_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- REUSE existing circuit_breakers table (CEO DIRECTIVE: No new breaker tables)
-- fhq_governance.circuit_breakers has UNIQUE(breaker_name) constraint
-- breaker_type must be one of: 'RATE','COST','EXECUTION','GOVERNANCE','MARKET','SYSTEM'

INSERT INTO fhq_governance.circuit_breakers (
    breaker_name,
    breaker_type,
    trigger_condition,
    defcon_threshold,
    action_on_trigger,
    is_active
) VALUES (
    'SQL_REFINEMENT_FAILURE',
    'GOVERNANCE',
    '{"condition": "refinement_failures_10min > 5", "description": "SQL refinement loop failure rate exceeded"}',
    'YELLOW',
    '{"actions": ["THROTTLE_REFINEMENT", "LOG_TO_GOVERNANCE"]}',
    true
)
ON CONFLICT (breaker_name) DO NOTHING;

-- Indexes on fhq_governance schema
CREATE INDEX idx_refinement_success ON fhq_governance.sql_refinement_log(success, created_at);
CREATE INDEX idx_refinement_agent ON fhq_governance.sql_refinement_log(agent_id, circuit_state);
CREATE INDEX idx_guidelines_pattern ON fhq_governance.sql_correction_guidelines(error_pattern, success_rate DESC);
CREATE INDEX idx_guidelines_active ON fhq_governance.sql_correction_guidelines(is_active, is_global_default);
-- NOTE: No index needed for circuit_breakers - existing table already indexed

-- Add back-reference to evidence bundle after refinement_log exists
ALTER TABLE fhq_governance.refinement_evidence_bundle
    ADD CONSTRAINT fk_evidence_refinement
    FOREIGN KEY (refinement_id) REFERENCES fhq_governance.sql_refinement_log(refinement_id);
```

**Python Implementation:**
- Create `03_FUNCTIONS/star_sql_reasoning_engine.py` (STaR-SQL CoT integration)
- Create `03_FUNCTIONS/magic_correction_agent.py` (Auto-guideline generation)
- Implement multi-agent pipeline: Manager → SQL Generator → Verifier → Corrector
- Track error → reasoning → correction → success chains

**Success Metric:** >86% queries correct on first attempt (matching STaR-SQL benchmark), >98% within 3 attempts.

---

## 13. CEO QUESTIONS - AUTHORITATIVE ANSWERS

### Q1: AIQF Definition - What is the exact formula and test set?

**Formula (Canonical):**
```
AIQF = (correct_first_attempt × 0.60) +
       (correct_within_3 × 0.25) +
       (semantic_correct × 0.10) +
       (no_escalation × 0.05)
```

**Test Set Specification:**
- **Location:** `fhq_governance.aiqf_benchmark_registry` (Migration 191b)
- **Size:** 50 queries of varying complexity
- **Query Classes:**
  - Simple lookups (10 queries)
  - Multi-table joins (15 queries)
  - Aggregations with filters (15 queries)
  - Complex nested/window queries (10 queries)
- **Evidence:** `dataset_hash`, `expected_results_fingerprint` stored per benchmark version
- **Certification:** VEGA signs `vega_certification_attestation_id` upon validation

---

### Q2: Query Classes in Scope - Which agents and schemas?

**Phase 1 Agents (Refinement Loop Authorized):**
| Agent | Authorized | Reason |
|-------|------------|--------|
| **FINN** | YES | Primary research queries |
| **STIG** | YES | Infrastructure/audit queries |
| **LARS** | NO (Phase 1) | Orchestrator - delegates to FINN/STIG |
| **LINE** | NO | Execution agent - no SQL generation |
| **VEGA** | NO | Governance - read-only |

**Phase 1 Schema Domains:**
| Schema | In Scope | Reason |
|--------|----------|--------|
| `fhq_meta` | YES | Core registries, minimal risk |
| `fhq_research` | YES | Signal discovery, primary use case |
| `fhq_canonical` | YES | Golden needles, critical data |
| `fhq_governance` | READ-ONLY | No refinement writes allowed |
| `fhq_execution` | NO (Phase 1) | Trading data - too sensitive |
| `fhq_alpha` | Phase 2 | After AIQF > 0.95 proven on Phase 1 |
| `vision_*` | Phase 2 | After circuit breaker stability proven |

**Authority Boundary:**
Refinement loop is **subordinate to** ADR-012 (Economic Safety) and ADR-016 (DEFCON). The loop cannot retry autonomously - it must respect circuit breaker state.

---

### Q3: Economic Constraints - Hard ceilings for refinement

**Per-Query Hard Ceilings:**
| Constraint | Ceiling | ADR Reference |
|------------|---------|---------------|
| Max Attempts | 3 | ADR-012 §4.2 |
| Max Tokens | 4,000 | ADR-012 §3.1 |
| Max Latency | 2,000 ms | ADR-016 §2.1 (matches HIGH_LATENCY breaker) |
| Max Cost | $0.02/query | ADR-012 §3.3 |

**Budget Attachment:**
| Agent | Budget Pool | Daily Ceiling |
|-------|-------------|---------------|
| FINN | `finn_research_daily` | $50/day |
| STIG | `stig_infra_daily` | $20/day |
| Refinement Total | `refinement_overhead` | $25/day |

**Escalation Path (when ceilings hit):**
1. Query marked `escalated_to_human = TRUE`
2. Evidence bundle created (`escalation_bundle_id`)
3. No further retries until human review
4. If 5 escalations in 10 minutes → DEFCON YELLOW trigger

---

## 14. OBSERVABILITY TIMELINE - CORRECTED (Improvement D)

**CEO Directive:** Observability 2.0 Core must be **IMMEDIATE**, not Q4 2026.

**Immediate (Week 1-2):**
- Refinement success rate instrumentation
- Error taxonomy logging
- Guideline effectiveness (success_rate with confidence bounds)
- Cost per successful query

**Phase 1 (Week 3-4):**
- Circuit breaker state monitoring
- DEFCON integration alerts
- AIQF drift detection

**Phase 2 (Month 2-3):**
- Cognitive Performance Dashboard (UI polish)
- Historical trend analysis
- Predictive anomaly detection

**What is NOT deferred:**
- All Pillar 1-3 instrumentation is **immediate**
- Dashboard polish can wait, but metrics capture cannot

---

## 15. MIGRATION EXECUTION ORDER (CEO-DIRECTED)

**CEO Directive:** Run observability FIRST, then refinement migrations.

**Rationale:** Without instrumentation, you cannot measure the effect of the refinement loop. This prevents "governance-correct but unobservable" deployments.

### Execution Sequence

| Order | Migration | Purpose | Prerequisite |
|-------|-----------|---------|--------------|
| **1** | `196_observability_2_immediate.sql` | Pillar 1-3 instrumentation | None |
| **2** | `191b_aiqf_benchmark_registry.sql` | AIQF canonical metric | 196 (for drift detection) |
| **3** | `191_reasoning_driven_sql_refinement.sql` | SQL refinement + circuit breaker | 191b (for FK to benchmark_runs) |
| **4** | `192_hybridrag_graphrag_infrastructure.sql` | Knowledge graph extensions | 191 |
| **5** | `193_mcp_gateway_infrastructure.sql` | MCP tool registry | 192 |
| **6** | `194_eu_ai_act_compliance_scoped.sql` | AI inventory (DEPLOYER scope) | None (parallel) |
| **7** | `195_semantic_abac_privacy_preserving.sql` | ABAC with differential privacy | 193 |

### Pre-Flight Checklist

Before running ANY migration:
- [ ] VEGA attestation of migration SQL (signed)
- [ ] DEFCON status = GREEN
- [ ] Backup of `fhq_governance` schema complete
- [ ] Observability dashboards configured (after 196)

### Post-Migration Validation

After 196 + 191b + 191:
1. Run AIQF baseline benchmark (50 queries)
2. Record `aiqf_score` in `fhq_governance.aiqf_benchmark_runs`
3. VEGA signs attestation if AIQF ≥ 0.95
4. If AIQF < 0.95: HALT further migrations, enter remediation

---

## 16. CEO PRE-IMPLEMENTATION REVIEW SIGN-OFF

**Review Date:** 2026-01-03
**Reviewer:** CEO

### Corrections Applied (DB-Grounded 2026-01-03)

| # | Issue | Fix Applied | Status |
|---|-------|-------------|--------|
| 1 | Latency 30s vs ADR-016 2000ms trigger | Reduced to 2000ms (matches HIGH_LATENCY breaker) | ✅ |
| 2 | circuit_state DEFAULT 'OPEN' wrong | Changed to 'CLOSED' | ✅ |
| 3 | Tables in fhq_meta not fhq_governance | Moved to fhq_governance | ✅ |
| 4 | Section 5.3.1 said "reasoning_chain" | Corrected to "reasoning_artifact" | ✅ |
| 5 | Missing FK constraints | Added all FKs | ✅ |
| 6 | Migration order undefined | 196 → 191b → 191 sequence | ✅ |
| 7 | New circuit breaker table proposed | Reuse `fhq_governance.circuit_breakers` with INSERT | ✅ |
| 8 | Evidence bundle pattern unclear | Reference `vision_verification.summary_evidence_ledger` | ✅ |

### CEO Hard Commitments (DB-Grounded)

1. **No new schemas in ADR-022 Phase 1** - All tables in existing fhq_governance
2. **Latency ceiling is 2000ms** - Matches ADR-016 HIGH_LATENCY breaker exactly
3. **Reuse existing circuit_breakers table** - INSERT with `ON CONFLICT (breaker_name) DO NOTHING`

### Authorization

This ADR-022 DRAFT is now **IMPLEMENTATION-READY** pending:
- [ ] VEGA Technical Review
- [ ] LARS Strategic Approval
- [ ] CEO Final Authorization

---

## 17. CONCLUSION

Med denne planen vil FjordHQ kunne levere på ADR-022's løfter på en **kontrollert, forskningsforankret og effektiv måte**.

Hvert steg er knyttet til:
- **Målbare milepæler** med forskningsvaliderte benchmarks
- **Best practice** (MBB-klasse struktur)
- **Konkrete referanser** til systemets konstitusjon og aktuell AI-forskning

Slik balanseres **innovasjon med ansvarlighet** – et absolutt krav for suksess når man befinner seg på frontlinjen av autonom AI-utvikling.

---

**ADR-022 Attestation:**
- **Evidence Method:** Direct database interrogation via MCP (`postgres_local` server)
- **Query Count:** 35+ SQL queries executed
- **Document Sources:** 21 ADRs, 18 IoS, 18 ECs verified in database
- **Constitutional Reference:** `00_CONSTITUTION/The Autonomous Database Horizon.md`
- **Research Reference:** `00_CONSTITUTION/Optimalisering av plan.pdf`
- **Schema Inventory:** 48 schemas, ~7GB, 621+ tables
- **Current Alignment Score:** 78.5% (target: 92% by Q2 2026)

**DB-Grounded Corrections Applied:**
- Latency: 2000ms (verified against ADR-016 HIGH_LATENCY breaker)
- Circuit breakers: Reuse `fhq_governance.circuit_breakers` with `UNIQUE(breaker_name)`
- Evidence bundles: Follow `vision_verification.summary_evidence_ledger` pattern
- No new schemas: All tables in existing `fhq_governance`

*Prepared by STIG (EC-003) under CEO Directive authority.*
*Date: 2026-01-03*
*DB-Grounded Review: 2026-01-03*
