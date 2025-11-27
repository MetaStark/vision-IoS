# ADR-014 – Executive Activation & Sub-Executive Governance Charter

**Version:** 2026.PRODUCTION
**Status:** APPROVED
**Date:** 28 November 2026
**Owner:** CEO
**Authority Chain:** ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 → ADR-008 → ADR-009 → ADR-010 → ADR-013 → ADR-014
**Governing Agents:** VEGA (Compliance), LARS (Strategy)
**Affects:** fhq_governance, fhq_org, fhq_meta, All Tier-2 Agents
**Classification:** GOVERNANCE–CRITICAL

---

## 1. Decision

FjordHQ formally adopts and activates the Operational Sub-Executive C-Suite, consisting of five specialized Tier-2 AI officers:

| Role | Title |
|------|-------|
| CSEO | Chief Strategy & Experimentation Officer |
| CDMO | Chief Data & Memory Officer |
| CRIO | Chief Research & Insight Officer |
| CEIO | Chief External Intelligence Officer |
| CFAO | Chief Foresight & Autonomy Officer |

All five are registered in `fhq_governance.agent_contracts` as Tier-2 Sub-Executive Agents, with inherited authority from their respective Tier-1 Executives:

| Tier-2 Role | Parent Executive | Authority Type |
|-------------|------------------|----------------|
| CSEO | LARS | Operational Authority |
| CDMO | STIG | Dataset Authority |
| CRIO | FINN | Model Authority |
| CEIO | STIG + LINE | Operational Authority |
| CFAO | LARS | Operational Authority |

**Critical Restrictions:**
- None of these roles are granted System Authority
- None have write access to canonical domains (ADR-013)
- None can initiate G2–G4 gates (ADR-004)

This Charter establishes the Executive Control Framework (ECF) as the permanent governance and audit model for all Sub-Executives.

---

## 2. Context

- ADR-001 defines FjordHQ's constitutional executive layer: LARS, STIG, LINE, FINN, VEGA
- ADR-013 established Canonical Truth Architecture and One-Source-of-Truth
- ADR-007 established Orchestrator + LLM-tiers
- ADR-010 established discrepancy scoring and anti-hallucination

However, a high-frequency operational execution motor was missing—structured AI officers capable of:
- Fetching, cleaning, and enriching data
- Running reasoning chains and experiment simulations
- Producing research insights
- Generating scenario packages
- Filtering external information

...without touching constitutional layers or canonical truth.

ADR-014 fills this gap and makes FjordHQ operationally autonomous.

---

## 3. Scope

ADR-014 regulates:
- Registration of Sub-Executive Agents
- Authority model for Tier-2
- Audit, evidence, and signature requirements
- ECF (Executive Control Framework)
- Risk and suspension mechanisms
- LLM-tier bindings
- Parent-child authority inheritance
- Interaction with Orchestrator

This affects all future IoS modules and operational pipelines.

---

## 4. Sub-Executive Contracts (Canonical Role Definitions)

### 4.1 CSEO – Chief Strategy & Experimentation Officer

| Field | Value |
|-------|-------|
| Tier | 2 |
| Parent | LARS |
| Authority | Operational (no System Authority) |
| Mandate | Reasoning-based strategy exploration. Produces Strategy Drafts vX.Y |
| Allowed | o1/R1 reasoning, hypothesis testing, experiment design |
| Forbidden | Pipeline changes, canonical writes, final strategy |
| Oversight | VEGA discrepancy + governance logging |

### 4.2 CDMO – Chief Data & Memory Officer

| Field | Value |
|-------|-------|
| Tier | 2 |
| Parent | STIG |
| Authority | Dataset Authority |
| Mandate | Non-canonical data management, synthetic augmentation, quality & lineage |
| Allowed | Normalization, preprocessing, ingest flows |
| Forbidden | Canonical writes, schema changes, irreversible transformations |
| Oversight | VEGA lineage, STIG tech-validation |

### 4.3 CRIO – Chief Research & Insight Officer

| Field | Value |
|-------|-------|
| Tier | 2 |
| Parent | FINN |
| Authority | Model Authority |
| Mandate | Research, causal reasoning, insight production |
| Allowed | GraphRAG, embedding analysis, research packs |
| Forbidden | Model signing (VEGA only), pipeline activation (LARS/STIG) |
| Oversight | VEGA compliance, ADR-003 research regime |

### 4.4 CEIO – Chief External Intelligence Officer

| Field | Value |
|-------|-------|
| Tier | 2 |
| Parent | STIG + LINE |
| Authority | Operational |
| Mandate | Fetch and transform external data to governance-ready signal structure |
| Allowed | Sentiment models, macro ingest, event mapping |
| Forbidden | Canonical writes, strategy routing, Orchestrator bypass |
| Oversight | Orchestrator discrepancy scoring |

### 4.5 CFAO – Chief Foresight & Autonomy Officer

| Field | Value |
|-------|-------|
| Tier | 2 |
| Parent | LARS |
| Authority | Operational |
| Mandate | Scenario simulation, regime analysis, risk projection, autonomy testing |
| Allowed | Stress testing, volatility mapping, foresight packs |
| Forbidden | Strategy changes, canonical writes, model parameterization |
| Oversight | VEGA + LARS scenario compliance |

---

## 5. Executive Control Framework (ECF)

*Governing Model for Tier-2 Sub-Executives*

### ECF-1 – Authority Hierarchy

```
Tier-1 Executives (LARS/STIG/LINE/FINN/VEGA/CEO)
              ↓
Tier-2 Sub-Executives (CSEO/CDMO/CRIO/CEIO/CFAO)
              ↓
Tier-3 Sub-Agents (future activation)
```

**Tier-2 executes. Tier-1 decides.**

### ECF-2 – Change Gate Boundaries (ADR-004)

Tier-2 can only operate within:
- G0: Submission
- G1: Technical validation support

Tier-2 can **never** trigger:
- G2 (Governance Validation)
- G3 (Audit & VEGA Verification)
- G4 (CEO Activation)

### ECF-3 – Evidence Requirements (ADR-002 & ADR-010)

Each Tier-2 output must contain:
- Ed25519 agent signature (ADR-008)
- Evidence bundle (inputs, logic trace, outputs)
- Discrepancy score
- Governance event log entry

This provides full traceability, BCBS-239-compliant lineage, and zero-trust verification.

### ECF-4 – Canonical Protection (ADR-013)

All Tier-2 roles have:
- READ-ONLY against canonical domains
- WRITE-FORBIDDEN (Class A violation)
- Automatic VEGA escalation on attempt

This protects unified truth.

### ECF-5 – LLM-Tier Binding (ADR-007)

Tier-2 Sub-Execs are routed through:
- **Tier-2 Models:** OpenAI / DeepSeek / Gemini
- **Tier-1 Models:** Claude (only LARS, VEGA)

This prevents unauthorized governance reasoning.

### ECF-6 – Suspension Mechanism (ADR-009)

If `discrepancy_score > 0.10`:
1. VEGA issues "Suspension Recommendation"
2. CEO decides APPROVE/REJECT
3. Worker enforces suspension

This provides robust fallback and human control.

---

## 6. Technical Implementation Requirements (Mandatory)

### 6.1 Register Roles in fhq_governance.agent_contracts

Required fields per role:
- `role_id` (UUID)
- `role_name`
- `parent_agent_id`
- `authority_level` = 'TIER_2'
- `authority_type` (OPERATIONAL / DATASET / MODEL)
- `llm_tier` = 2
- `status` = 'ACTIVE'
- `created_by` = CEO
- `contract_sha256`

### 6.2 Update fhq_governance.authority_matrix

For each role:
- `can_read_canonical` = TRUE
- `can_write_canonical` = FALSE
- `can_trigger_g2` = FALSE
- `can_trigger_g3` = FALSE
- `can_trigger_g4` = FALSE
- `can_execute_operational_tasks` = TRUE
- `can_submit_g0` = TRUE

### 6.3 Update Model Provider Policy (ADR-007)

```
CSEO / CRIO / CDMO / CEIO / CFAO  → Tier-2 Provider Access
LARS / VEGA                       → Tier-1 Provider Access
```

### 6.4 Orchestrator Registration Requirement (fhq_org.org_agents)

Per agent:
- `public_key` (Ed25519)
- `signing_algorithm` = 'Ed25519'
- `llm_tier` = 2
- `authority_level` = 2

---

## 7. Consequences

### Positive
- Full autonomy in operational layer
- 80/20 liberation of CEO/LARS time
- Harmonious distribution between reasoning, research, data, and risk
- Zero-trust controls intact via ADR-010 + ADR-013
- Operational speed increases without weakening governance

### Negative
- Increased volume of evidence bundles
- Higher frequency of Orchestrator calls
- Requires strict adherence to G0–G1

---

## 8. Acceptance Criteria

ADR-014 is considered implemented when:
- All five Sub-Executives are registered in governance tables
- Authority matrix is updated
- Orchestrator recognizes the roles
- VEGA approves activation
- Discrepancy scoring functions for all Tier-2 roles
- Canonical protections function deterministically

---

## 9. Status

**APPROVED**
VEGA Attestation Required
Ready for Immediate Production Deployment

---

## 10. Appendix A – Juridical Contracts

### Contract Template (all follow this structure)

- Role
- Reporting
- Authority boundary
- Operating Tier
- Canonical obligations
- Forbidden actions
- Signing scope
- VEGA oversight
- Breach conditions (Class A/B/C ref. ADR-002)
- Reconciliation & Evidence Requirements (ADR-010)
- Suspension workflow (ADR-009)
- Interaction with Change Gates (ADR-004)

---

### CONTRACT: CSEO – Chief Strategy & Experimentation Officer

**Role Type:** Sub-Executive Officer
**Reports To:** LARS (Executive – Strategy)
**Authority Level:** Operational Authority (Tier-2)
**Domain:** Strategy formulation, experimentation, reasoning chains

**1. Mandate**
CSEO performs strategy experimentation based on reasoning models and problem formulation principles. CSEO produces proposals—never decisions.

**2. Authority Boundaries**

*Allowed:*
- Run reasoning models
- Generate Strategy Drafts vX.Y
- Build experiment designs
- Evaluate strategic hypotheses
- Use Tier-2 resources

*Not Allowed (Hard boundary):*
- Change system parameters (System Authority)
- Write to canonical domain stores (ref. ADR-013)
- Produce final strategy (only LARS)
- Change pipeline logic, code, or governance

**3. Tier:** Tier-2 Operational (fast loop, high frequency, high debias)

**4. Governance & Compliance**
CSEO is subject to: ADR-001, ADR-003, ADR-004, ADR-007, ADR-010, ADR-013

**5. VEGA Oversight**
All strategic drafts evaluated through governance event log, discrepancy check, VEGA monitoring.

**6. Breach Conditions**
- Class A: Write attempt to canonical tables
- Class B: Incomplete documentation
- Class C: Missing metadata

Consequences: Reconciliation → VEGA review → CEO decision (ADR-009)

---

### CONTRACT: CDMO – Chief Data & Memory Officer

**Role Type:** Sub-Executive Officer
**Reports To:** STIG (Technical Governance)
**Authority Type:** Dataset Authority (Tier-2)
**Domain:** Data quality, lineage, synthetic augmentation

**Mandate:** CDMO maintains all non-canonical datasets, including preparation of data for later STIG + VEGA approval for canonical use.

*Allowed:* Ingest pipeline execution, dataset normalization, synthetic augmentation, memory-lag management, anomaly detection

*Forbidden:* Ingest to fhq_meta.canonical_domain_registry (only STIG), schema or datatype changes, irreversible transformations

**Tier:** Tier-2 Operational (high speed, tight control)

**VEGA Oversight:** Automatic discrepancy scoring + lineage review

---

### CONTRACT: CRIO – Chief Research & Insight Officer

**Role Type:** Sub-Executive Officer
**Reports To:** FINN
**Authority:** Model Authority (Tier-2)
**Domain:** Research, causal reasoning, feature generation

**Mandate:** CRIO builds insight, models, and problem formulations. Produces Insight Packs, never final conclusions.

*Allowed:* DeepSeek-based reasoning models, research packs, graph analysis (GraphRAG), feature engineering

*Forbidden:* Sign models (only VEGA), activate models in pipeline (only LARS/STIG), write to canonical model registries

**Tier:** Tier-2

**VEGA Oversight:** Research validated against ADR-003 + discrepancy score

---

### CONTRACT: CEIO – Chief External Intelligence & Signal Officer

**Role Type:** Sub-Executive Officer
**Reports To:** STIG + LINE
**Authority:** Operational Authority
**Domain:** Fetch, filter, and structure external information

**Mandate:** CEIO transforms raw external data (news, macro, sentiment, flows) into signals compatible with the governance system.

*Allowed:* Ingest signals, enrich data, run sentiment and NLP models, generate Signal Package vX.Y

*Forbidden:* Write directly to canonical truth domains, re-wrap signals as strategy, bypass Orchestrator

**Tier:** Tier-2

---

### CONTRACT: CFAO – Chief Foresight & Autonomy Officer

**Role Type:** Sub-Executive
**Reports To:** LARS
**Authority:** Operational Authority
**Domain:** Future scenarios, risk, allocation, autonomy simulation

**Mandate:** CFAO builds scenario packages based on CSEO/CRIO output. CFAO evaluates risk, regime, future paths. No final decision authority.

*Allowed:* Scenario simulation, risk analysis, foresight pipelines, economic stress testing

*Forbidden:* Change strategies, modify canonical outputs, change model parameters

**Tier:** Tier-2

---

## 11. Appendix B – Executive Control Framework (ECF) Full Specification

### ECF-1: Authority Hierarchy (Aligned with ADR-001)

**Tier-1 (Constitutional Executives):** LARS – STIG – LINE – FINN – VEGA – CEO

**Tier-2 (Operational Sub-Executives):** CSEO – CDMO – CRIO – CEIO – CFAO

**Tier-3 (Sub-agents, future):** e.g., PIA (FINN), AUD (VEGA), NODDE (LINE)

### ECF-2: Governance Path (ADR-004 Compliance)

All sub-executives operate as follows:
- G0: Can submit proposals
- G1: STIG evaluates technical aspects
- G2: LARS/FINN evaluate logic
- G3: VEGA validates
- G4: CEO approves

Sub-executives can **never** initiate G2–G4.

### ECF-3: Evidence Structure (ADR-002 + ADR-010)

All sub-executive outputs must be produced with:
- Agent signature (Ed25519 via ADR-008)
- Evidence bundle
- Discrepancy scoring before ingest
- Governance event log

This makes everything audit-compatible.

### ECF-4: Canonical Protection (ADR-013)

Sub-executives have zero access to canonical domain stores.
Attempt → Class A → VEGA → CEO

### ECF-5: Orchestrator Routing (ADR-007)

- All requests go via `/agents/execute`
- LLM-tier: All five are Tier-2
- They receive mid-level provider access (OpenAI, DeepSeek, Gemini)
- None are allowed to communicate directly with Tier-1 models (Claude)

### ECF-6: Compliance & Regulatory Alignment (ADR-003)

All sub-executive activities are evaluated against:
- ISO 8000 (data quality)
- BCBS-239 (lineage & traceability)
- DORA (resilience)
- GIPS 2020 (performance integrity)

### ECF-7: Suspension Logic (ADR-009)

If `discrepancy_score > 0.10` for any sub-executive:
1. VEGA → Recommendation
2. CEO → APPROVE/REJECT
3. Orchestrator Worker → Enforce

### ECF-8: Operating Rhythm

**Daily:**
- Discrepancy scoring
- Integrity checks

**Weekly:**
- Governance review
- Dataset validation

**Monthly:**
- Scenario refresh (CFAO)
- Research alignment (CRIO)

---

## 12. Governance Chain

This framework is 100% anchored in:
- ADR-001 (Constitution)
- ADR-002 (Audit)
- ADR-003 (Standards)
- ADR-004 (Change Gates)
- ADR-006 (VEGA Charter)
- ADR-007 (Orchestrator)
- ADR-008 (Keys & Identity)
- ADR-010 (Reconciliation)
- ADR-013 (Canonical Truth)

---

**END OF ADR-014_2026_PRODUCTION**
