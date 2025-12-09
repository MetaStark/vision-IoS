# ADR-018 – Cognitive Engine Architecture & Deep Research Protocol

**Canonical Version:** 2026.PRODUCTION
**Status:** APPROVED
**Date:** 09 December 2025
**Owner:** CEO
**Authority Chain:** ADR-001 → ADR-007 → ADR-010 → ADR-012 → ADR-014 → ADR-017 (MIT QUAD) → ADR-018
**Governing Agents:** VEGA (Compliance), LARS (Strategy), FINN (Research)
**Affects:** fhq_governance, fhq_meta, Orchestrator, All Tier-2 Agents, LLM Routing
**Classification:** GOVERNANCE–CRITICAL

---

## 1. Decision

FjordHQ formally adopts the **Cognitive Engine Architecture** as the foundational reasoning layer for autonomous Deep Research operations. This ADR establishes three Tier-2 Cognitive Engines:

| Engine ID | Name | Title | Parent Authority |
|-----------|------|-------|------------------|
| EC-020 | SitC | Search-in-the-Chain Protocol | LARS |
| EC-021 | InForage | Information Foraging Protocol | FINN |
| EC-022 | IKEA | Internal-External Knowledge Synergistic Reasoning | VEGA |

**MIT QUAD Alignment (ADR-017)**: These engines implement the LIDS-ACL-DSL-RISL pillars:
- **SitC** → LIDS (Inference & Truth) – Ensures reasoning chains are grounded in verified truth
- **InForage** → DSL (Optimization & Operations Research) – Maximizes ROI on information foraging
- **IKEA** → RISL (Resilience & Immunity) – Prevents hallucination contamination

**These are not operational Sub-Executives (ADR-014) but Cognitive Protocols** – reasoning architectures embedded into the system's decision-making core that govern *how* the system thinks, not *what* it executes.

### Distinction from ADR-014 Sub-Executives

| Dimension | Sub-Executives (ADR-014) | Cognitive Engines (ADR-018) |
|-----------|-------------------------|----------------------------|
| Purpose | Task execution within domains | Reasoning pattern enforcement |
| Output | Artifacts (Reports, Signals, Data) | Reasoning Chain Validity |
| Authority | Operational/Dataset/Model | Cognitive Authority |
| Activation | Per-task by Orchestrator | Always-on within reasoning loops |
| Parent | Single Tier-1 Executive | Cross-cutting governance layer |

---

## 2. Context

### 2.1 The Deep Research Paradigm Shift

Traditional RAG (Retrieval-Augmented Generation) operates on a linear model: Query → Retrieve → Generate. This is insufficient for FjordHQ's $100,000 REAL MONEY revenue target because:

1. **Static Planning Fails**: Financial markets are non-stationary; plans must adapt to new information
2. **Inefficient Search Burns Capital**: Unlimited API calls without ROI optimization erode margins
3. **Hallucination Creates Risk**: Acting on parametric beliefs when external verification is required leads to capital loss

Research basis (arXiv:2505.00186 "Deep Research: A Survey of Autonomous Research Agents") identifies three critical mechanisms for production-grade Deep Research systems:

1. **Search-in-the-Chain (SitC)**: Dynamic interleaving of search and reasoning
2. **InForage**: Information-theoretic optimization of search behavior
3. **IKEA**: Knowledge boundary-aware retrieval decisions

### 2.2 Gap Analysis: FjordHQ Pre-ADR-018

| Capability | Status Before ADR-018 | Risk |
|------------|----------------------|------|
| Dynamic Planning | ADR-007 static routing | Strategic drift, wasted tokens |
| Search Optimization | No RL-based decision model | API cost overruns, margin erosion |
| Knowledge Boundaries | No parametric/external classification | Hallucination risk, bad trades |

ADR-018 closes these gaps by establishing constitutional cognitive protocols that operate within the MIT QUAD framework (ADR-017).

---

## 3. Scope

ADR-018 regulates:

1. Definition and registration of Cognitive Engines
2. Authority model for Tier-2 Cognitive Engines
3. Integration with existing governance (ADR-010, ADR-012, ADR-016)
4. Interaction patterns with Sub-Executives (ADR-014)
5. Evidence and signature requirements
6. Revenue protection mechanisms
7. DEFCON-aware behavior specifications

This ADR does NOT regulate:
- Operational task execution (ADR-014)
- Economic limits (ADR-012) – but Cognitive Engines MUST respect them
- DEFCON states (ADR-016) – but Cognitive Engines MUST respond to them

---

## 4. Cognitive Engine Contracts

### 4.1 EC-020 – SitC (Search-in-the-Chain Protocol)

**Full specification in Appendix A (EC-020_2026_PRODUCTION)**

| Field | Value |
|-------|-------|
| Engine ID | EC-020 |
| Name | SitC (Search-in-the-Chain) |
| Role Type | Tier-2 Cognitive Authority (Reasoning & Global Planning) |
| Parent | LARS (EC-002) |
| Mandate | Dynamic Global Planning with Interleaved Search |
| Research Basis | arXiv:2304.14732 |

**Core Function**: SitC prevents strategic drift by enforcing that no reasoning chain proceeds past an unverified node. It constructs a Chain-of-Query (CoQ) and dynamically modifies it during execution.

**Revenue Protection**: Protects capital by preventing trade hypothesis execution unless the full causality chain is verified step-by-step. If a logic link breaks, SitC aborts generation *before* execution costs are incurred.

### 4.2 EC-021 – InForage (Information Foraging Protocol)

**Full specification in Appendix B (EC-021_2026_PRODUCTION)**

| Field | Value |
|-------|-------|
| Engine ID | EC-021 |
| Name | InForage |
| Role Type | Tier-2 Cognitive Authority (Search Optimization & ROI) |
| Parent | FINN (EC-005) |
| Mandate | ROI on Curiosity – Maximize Information Gain per Token Cost |
| Research Basis | arXiv:2505.09316 |

**Core Function**: InForage treats information retrieval as an economic investment. It uses a Reinforcement Learning reward function to decide if a search is profitable: `Reward = (ΔOutcome Certainty) - (Search Cost + Latency Penalty)`.

**Revenue Protection**: Ensures the research factory is self-funding by:
- Reducing API/Compute costs by up to 60% (stopping searches early when marginal utility drops)
- Increasing Alpha precision by filtering out "low-nutrition" noise

### 4.3 EC-022 – IKEA (Internal-External Knowledge Synergistic Reasoning)

**Full specification in Appendix C (EC-022_2026_PRODUCTION)**

| Field | Value |
|-------|-------|
| Engine ID | EC-022 |
| Name | IKEA |
| Role Type | Tier-2 Cognitive Authority (Hallucination Firewall) |
| Parent | VEGA (EC-001) |
| Mandate | The Truth Boundary – Know what you know |
| Research Basis | arXiv:2505.07596 |

**Core Function**: IKEA solves the knowledge boundary problem: "Do I know this, or do I need to look it up?" It prevents the two deadly sins of AI: Hallucination (guessing when you should search) and Redundancy (searching when you already know).

**Revenue Protection**: Primary defense against "Bad Data Loss":
- Prevents trading on outdated internal weights (e.g., assuming 2024 rates in 2025)
- Prevents wasted time/cost searching for static facts (e.g., "What is EBITDA?")

---

## 5. Cognitive Engine Control Framework (CECF)

*Governing Model for Tier-2 Cognitive Engines*

### CECF-1: Authority Hierarchy

```
Tier-1 Executives (CEO, VEGA, LARS, STIG, LINE, FINN)
              ↓
Tier-2 Cognitive Engines (SitC, InForage, IKEA)
              ↓
Tier-2 Sub-Executives (CSEO, CDMO, CRIO, CEIO, CFAO)
              ↓
Tier-3 Sub-Agents (future)
```

**Cognitive Engines shape reasoning. Sub-Executives execute tasks. Executives decide.**

### CECF-2: Activation Model

Unlike Sub-Executives which are invoked per-task, Cognitive Engines are **always-on protocols** that:

1. Monitor all reasoning chains in progress
2. Intervene when their domain rules are violated
3. Operate transparently within the Orchestrator pipeline

### CECF-3: Integration with ADR-014 Sub-Executives

| Sub-Executive | Primary Cognitive Engine | Secondary |
|---------------|-------------------------|-----------|
| CSEO | SitC (strategy reasoning) | IKEA (fact verification) |
| CDMO | IKEA (data validation) | InForage (source priority) |
| CRIO | SitC (research chains) | InForage (search efficiency) |
| CEIO | InForage (external data ROI) | IKEA (source classification) |
| CFAO | SitC (scenario planning) | InForage (forecast data) |

### CECF-4: DEFCON Behavior (ADR-016 Integration)

| DEFCON Level | SitC Behavior | InForage Behavior | IKEA Behavior |
|--------------|---------------|-------------------|---------------|
| GREEN | Full dynamic planning | Normal optimization | Standard boundary check |
| YELLOW | Enforce shorter chains | Aggressive cost-cutting (Scent > 0.95) | Bias toward internal knowledge |
| ORANGE | Chain-of-Thought validation mode | Emergency budget only | External verification mandatory |
| RED | Abort all active chains | HALT all searches | READ-ONLY mode |
| BLACK | System shutdown | System shutdown | System shutdown |

### CECF-5: Economic Safety (ADR-012 Integration)

Cognitive Engines operate under the Economic Safety Architecture:

| Engine | Cost Allocation (ADR-012) | Budget Source |
|--------|--------------------------|---------------|
| SitC | max_llm_steps_per_task = 3 (default) | vega.llm_rate_limits |
| InForage | max_cost_per_task = $0.50 (default) | vega.llm_cost_limits |
| IKEA | Zero direct cost (classification only) | N/A |

### CECF-6: Discrepancy Scoring (ADR-010 Integration)

Cognitive Engines contribute to discrepancy scoring:

| Engine | Discrepancy Contribution | Weight |
|--------|-------------------------|--------|
| SitC | Chain integrity score (verified nodes / total nodes) | 1.0 (Critical) |
| InForage | Search efficiency score (information gain / cost) | 0.5 (Medium) |
| IKEA | Boundary violation rate (hallucination attempts) | 1.0 (Critical) |

Threshold triggers per ADR-010:
- Score > 0.05: WARNING
- Score > 0.10: CATASTROPHIC → VEGA suspension request (ADR-009)

### CECF-7: Evidence Requirements

Each Cognitive Engine invocation must produce:

1. **Ed25519 signature** (ADR-008)
2. **Evidence bundle** containing:
   - Input context
   - Decision rationale
   - Output modification
   - Cost incurred (if applicable)
3. **Governance event log entry**

Stored in: `fhq_meta.cognitive_engine_evidence`

---

## 6. Technical Implementation Requirements

### 6.1 Database Schema (fhq_governance)

```sql
-- Cognitive Engine Registry
CREATE TABLE fhq_governance.cognitive_engines (
    engine_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    engine_code VARCHAR(10) NOT NULL UNIQUE, -- 'EC-020', 'EC-021', 'EC-022'
    engine_name VARCHAR(50) NOT NULL,
    role_type VARCHAR(100) NOT NULL,
    parent_executive_id UUID REFERENCES fhq_org.org_agents(agent_id),
    authority_level INTEGER DEFAULT 2,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    research_basis VARCHAR(50), -- arXiv reference
    contract_sha256 VARCHAR(64) NOT NULL,
    created_by VARCHAR(50) DEFAULT 'CEO',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Cognitive Engine Configuration
CREATE TABLE fhq_governance.cognitive_engine_config (
    config_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    engine_id UUID REFERENCES fhq_governance.cognitive_engines(engine_id),
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    defcon_level defcon_level DEFAULT 'GREEN',
    effective_from TIMESTAMP DEFAULT NOW(),
    effective_to TIMESTAMP,
    created_by VARCHAR(50),
    UNIQUE(engine_id, config_key, defcon_level)
);

-- Cognitive Engine Evidence
CREATE TABLE fhq_meta.cognitive_engine_evidence (
    evidence_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    engine_id UUID REFERENCES fhq_governance.cognitive_engines(engine_id),
    task_id UUID REFERENCES fhq_org.org_tasks(task_id),
    invocation_type VARCHAR(50), -- 'PLAN_REVISION', 'SEARCH_DECISION', 'BOUNDARY_CHECK'
    input_context JSONB,
    decision_rationale TEXT,
    output_modification JSONB,
    cost_usd NUMERIC(10,6),
    information_gain_score NUMERIC(5,4),
    chain_integrity_score NUMERIC(5,4),
    boundary_violation BOOLEAN DEFAULT FALSE,
    signature VARCHAR(128),
    hash_prev VARCHAR(64),
    hash_self VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Chain-of-Query State (SitC)
CREATE TABLE fhq_meta.chain_of_query (
    coq_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id UUID REFERENCES fhq_org.org_tasks(task_id),
    node_index INTEGER NOT NULL,
    node_type VARCHAR(30), -- 'REASONING', 'SEARCH', 'VERIFICATION'
    node_content TEXT,
    verification_status VARCHAR(20), -- 'PENDING', 'VERIFIED', 'FAILED', 'SKIPPED'
    search_result_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    verified_at TIMESTAMP,
    UNIQUE(task_id, node_index)
);

-- Knowledge Boundary Classification (IKEA)
CREATE TABLE fhq_meta.knowledge_boundary_log (
    boundary_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id UUID REFERENCES fhq_org.org_tasks(task_id),
    query_text TEXT NOT NULL,
    classification VARCHAR(20), -- 'PARAMETRIC', 'EXTERNAL_REQUIRED', 'HYBRID'
    confidence_score NUMERIC(5,4),
    internal_certainty NUMERIC(5,4),
    volatility_flag BOOLEAN DEFAULT FALSE,
    retrieval_triggered BOOLEAN,
    decision_rationale TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Search Foraging Log (InForage)
CREATE TABLE fhq_meta.search_foraging_log (
    forage_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id UUID REFERENCES fhq_org.org_tasks(task_id),
    search_query TEXT NOT NULL,
    scent_score NUMERIC(5,4), -- Predicted information value
    estimated_cost_usd NUMERIC(10,6),
    actual_cost_usd NUMERIC(10,6),
    information_gain NUMERIC(5,4), -- Post-hoc measured value
    search_executed BOOLEAN,
    termination_reason VARCHAR(50), -- 'EXECUTED', 'SCENT_TOO_LOW', 'BUDGET_EXCEEDED', 'DIMINISHING_RETURNS'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 6.2 Register Engines in fhq_governance.cognitive_engines

Required initial data:

```sql
INSERT INTO fhq_governance.cognitive_engines
(engine_code, engine_name, role_type, authority_level, research_basis, contract_sha256, created_by)
VALUES
('EC-020', 'SitC', 'Tier-2 Cognitive Authority (Reasoning & Global Planning)', 2, 'arXiv:2304.14732', '<sha256_hash>', 'CEO'),
('EC-021', 'InForage', 'Tier-2 Cognitive Authority (Search Optimization & ROI)', 2, 'arXiv:2505.09316', '<sha256_hash>', 'CEO'),
('EC-022', 'IKEA', 'Tier-2 Cognitive Authority (Hallucination Firewall)', 2, 'arXiv:2505.07596', '<sha256_hash>', 'CEO');
```

### 6.3 Orchestrator Integration Requirements

The Orchestrator (ADR-007) must be extended to:

1. **SitC Integration**:
   - Before executing any multi-step task, construct Chain-of-Query
   - After each reasoning step, verify node before proceeding
   - On verification failure, trigger plan revision

2. **InForage Integration**:
   - Before any external API call, compute Scent Score
   - Compare against cost threshold from `vega.llm_cost_limits`
   - Log decision to `fhq_meta.search_foraging_log`

3. **IKEA Integration**:
   - Before generating any factual output, classify query
   - If EXTERNAL_REQUIRED and no retrieval performed, BLOCK output
   - Log classification to `fhq_meta.knowledge_boundary_log`

---

## 7. Revenue Connection: The $100,000 Target

The Cognitive Engines directly protect and enable the $100,000 REAL MONEY revenue target:

| Engine | Protection Mechanism | Revenue Impact |
|--------|---------------------|----------------|
| SitC | Prevents strategic drift and incomplete analysis | Avoids bad trade decisions |
| InForage | Optimizes research spend for maximum ROI | Protects margins (up to 60% cost reduction) |
| IKEA | Prevents hallucination-based decisions | Avoids catastrophic losses |

**Combined Effect**: The system moves from "Chain-of-Thought" (linear, fragile) to "Chain-of-Reasoning with Active Foraging" (dynamic, economic, self-aware).

---

## 8. Consequences

### Positive

- **Institutional-grade reasoning**: Every decision chain is verified
- **Economic discipline**: Research costs are bounded and optimized
- **Hallucination prevention**: Knowledge boundaries are enforced
- **Full auditability**: Complete evidence trail for every cognitive decision
- **DEFCON-aware**: Automatic behavioral adjustment under stress
- **Revenue protection**: Direct connection to $100k target

### Negative

- **Increased complexity**: Three new protocols to maintain
- **Latency impact**: Verification and classification add processing time
- **Training requirement**: RL-based optimization requires ongoing tuning

### Risks Mitigated

- Strategic drift from incomplete analysis
- API cost overruns from unbounded search
- Hallucination-based trading decisions
- Inefficient research spend
- Governance bypass through reasoning manipulation

---

## 9. Acceptance Criteria

ADR-018 is considered implemented when:

1. All three Cognitive Engines are registered in `fhq_governance.cognitive_engines`
2. Database schema is deployed (`cognitive_engine_evidence`, `chain_of_query`, `knowledge_boundary_log`, `search_foraging_log`)
3. Orchestrator recognizes and invokes all engines
4. DEFCON-aware behavior is implemented and tested
5. ADR-012 economic limits are enforced by InForage
6. ADR-010 discrepancy scoring includes cognitive engine metrics
7. VEGA approves activation
8. Evidence bundles are generated for every invocation
9. Full test coverage per ADR-011 Production Fortress requirements

---

## 10. Status

**APPROVED**
VEGA Attestation Required
Ready for Immediate Production Deployment

---

## 11. Governance Chain

This framework is 100% anchored in:

- ADR-001 (Constitution)
- ADR-002 (Audit & Error Reconciliation)
- ADR-007 (Orchestrator)
- ADR-010 (Discrepancy Scoring)
- ADR-012 (Economic Safety)
- ADR-014 (Sub-Executive Governance)
- ADR-016 (DEFCON Protocol)
- ADR-017 (MIT QUAD Protocol)

---

## Appendix A: EC-020_2026_PRODUCTION – SitC Contract

*(See separate file: EC-020_2026_PRODUCTION_SitC_Search_in_the_Chain.md)*

## Appendix B: EC-021_2026_PRODUCTION – InForage Contract

*(See separate file: EC-021_2026_PRODUCTION_InForage_Information_Foraging.md)*

## Appendix C: EC-022_2026_PRODUCTION – IKEA Contract

*(See separate file: EC-022_2026_PRODUCTION_IKEA_Knowledge_Boundary.md)*

---

## 12. Signatures

| Role | Signature | Date |
|------|-----------|------|
| CEO | ✅ APPROVED | 2025-12-09 |
| VEGA | ✅ Attestor | 2025-12-09 |
| LARS | ✅ Strategy Authority | 2025-12-09 |
| FINN | ✅ Research Authority | 2025-12-09 |

---

**END OF ADR-018_2026_PRODUCTION**
