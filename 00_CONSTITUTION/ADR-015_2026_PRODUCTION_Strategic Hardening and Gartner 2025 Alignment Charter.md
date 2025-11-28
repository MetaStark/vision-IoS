# ADR-015 – Strategic Hardening & Gartner 2025 Alignment Charter

**Version:** 2026.PRODUCTION
**Status:** APPROVED
**Date:** 28 November 2026
**Owner:** CEO
**Authority Chain:** ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 → ADR-008 → ADR-010 → ADR-013 → ADR-014 → ADR-015
**Governing Agents:** VEGA (Compliance), LARS (Strategy)
**Affects:** All Tier-1 Executives, All Tier-2 Sub-Executives, fhq_governance, fhq_meta, vega schema
**Classification:** CONSTITUTIONAL
**Tier:** Tier-1

---

## 1. Decision

FjordHQ formally adopts the **Strategic Hardening Framework** aligned with Gartner's 2025 Impact Radar. This ADR mandates constitutional extensions to executive contracts, establishes action-level governance controls, and activates the hardened boardroom launch sequence.

### 1.1 Gartner 2025 Impact Radar Alignment

| Agent | Mandate | Gartner Category |
|-------|---------|------------------|
| CSEO | Explicit Chain-of-Thought Logging + Inference-Time Scaling | Reasoning Models |
| CRIO | Market Knowledge Graph (MKG) + GraphRAG Primary Retrieval | Knowledge Graphs |
| CDMO | Synthetic Stress Scenario Generation | Synthetic Data |
| CFAO | Foresight Pack Simulation on Synthetic Data | Intelligent Simulation |
| VEGA | Action-Level Veto (LAM Governance) | Agentic AI / LAM |

### 1.2 Model Tier Enforcement

| Tier | Agents | Providers | Governance |
|------|--------|-----------|------------|
| Tier-1 | LARS, VEGA | Anthropic Claude | Constitutional reasoning |
| Tier-2 | STIG, LINE, FINN, CSEO, CRIO, CDMO, CEIO, CFAO | DeepSeek, OpenAI, Gemini | Operational execution |

---

## 2. Context

ADR-014 established the Tier-2 Sub-Executive C-Suite (CSEO, CDMO, CRIO, CEIO, CFAO) with operational authority under Tier-1 executives.

Gartner's 2025 Impact Radar identifies five transformative AI capabilities that directly apply to FjordHQ's architecture:

1. **Reasoning Models** – Require explicit chain-of-thought for accurate decisions in complex domains
2. **Knowledge Graphs / GraphRAG** – Model relationships and reduce hallucinations vs. linear RAG
3. **Synthetic Data** – Enable stress testing under non-historical regimes
4. **Intelligent Simulation** – Project risk and opportunity through scenario modeling
5. **Agentic AI / LAM** – Require hard guardrails for Large Action Models

ADR-015 integrates these capabilities into FjordHQ's constitutional framework.

---

## 3. Scope

ADR-015 governs:

- Executive contract hardening with Gartner-mandated extensions
- Action-level veto mechanism for all Tier-2 agents
- Model tier enforcement (Tier-1 → Claude, Tier-2 → DeepSeek/OpenAI/Gemini)
- Synthetic stress scenario pipeline (CDMO → CFAO)
- Chain-of-thought logging infrastructure
- Market Knowledge Graph architecture
- Ignition test framework for hardened launch
- VEGA attestation protocol for strategic hardening

---

## 4. Executive Contract Extensions

### 4.1 CSEO – Chain-of-Thought Logging Mandate

```
All strategic drafts produced by CSEO MUST include explicit chain-of-thought
reasoning logs, structured as inference breadcrumbs, suitable for VEGA audit
and discrepancy scoring under ADR-010.
```

**Required Components:**
- Reasoning chain ID
- Thought sequence (JSON)
- Inference steps count
- Confidence score
- Alternatives considered
- Final recommendation
- VEGA audit status

**Inference-Time Scaling:**
- Minimum reasoning depth: 3 steps
- Maximum reasoning depth: 10 steps
- Complexity threshold: 0.7
- Scaling policy: Adaptive

### 4.2 CRIO – GraphRAG Knowledge Graph Mandate

```
CRIO is hereby mandated to build and maintain an evolving, audit-compatible
Market Knowledge Graph and must use GraphRAG as primary retrieval method
for all research outputs.
```

**Market Knowledge Graph (MKG):**
- Node types: asset, sector, macro_indicator, event, sentiment, correlation, causation
- Edge types: influences, correlates_with, leads, lags, amplifies, dampens, triggers
- Update frequency: Realtime
- Versioning: Enabled

**Causal Chain Mapping:**
- commodities → shipping → currency
- rates → credit → liquidity
- geopolitics → risk_premium → volatility
- central_bank → rates → asset_prices

### 4.3 CDMO – Synthetic Stress Scenario Mandate

```
Responsible for continuous generation of synthetic macro-financial stress
scenarios for downstream foresight simulations.
```

**Scenario Categories:**
- Extreme rates: [-500bp, +500bp]
- Volatility spike: [VIX 40, VIX 80]
- Liquidity drought: Systemic severity
- Geopolitical shock: Black swan events
- Credit event: Sovereign or corporate
- Currency crisis: EM or G10

**Delivery Target:** CFAO
**Generation Frequency:** Weekly
**Historical Anchor:** FALSE (non-historical regimes)

### 4.4 CFAO – Foresight Simulation Mandate

```
Must run scenario simulations on synthetic datasets to project risk, fragility
and opportunity under non-historical regimes.
```

**Input Source:** CDMO Synthetic Stress Scenario Package
**Output:** Foresight Pack v1.0

**Output Components:**
- Risk projection (probability distribution)
- Fragility score (0-1 scalar)
- Opportunity zones (ranked list)
- Regime probabilities (state vector)
- Action recommendations (prioritized list)

### 4.5 VEGA – Action-Level Veto Mandate

```
VEGA must approve, block, or reclassify all large-action decisions before
execution, serving as constitutional guardrail for all agentic behaviors.
```

**Veto Decisions:**
- APPROVED: Action within acceptable risk threshold
- BLOCKED: Action violates authority or constitutional rules
- RECLASSIFIED: High-risk action requires elevated approval
- PENDING: Awaiting evaluation

**Pre-flight Evaluation:**
- All Tier-2 action requests evaluated before execution
- Risk threshold: 0.7 (configurable)
- Canonical write attempts: Always BLOCKED for Tier-2
- Gate triggers (G2/G3/G4): Always BLOCKED for Tier-2

---

## 5. Technical Implementation

### 5.1 Database Tables Created

| Schema | Table | Purpose |
|--------|-------|---------|
| fhq_meta | baseline_locks | Governance state locking |
| fhq_meta | cot_reasoning_logs | CSEO CoT storage |
| fhq_governance | model_tier_enforcement | LLM tier binding |
| fhq_research | synthetic_stress_scenarios | CDMO output |
| fhq_research | foresight_packs | CFAO output |
| fhq_research | mkg_nodes | CRIO Knowledge Graph |
| fhq_research | mkg_edges | CRIO Knowledge Graph |
| vega | action_level_veto | VEGA LAM decisions |

### 5.2 Database Functions Created

| Schema | Function | Purpose |
|--------|----------|---------|
| vega | integrity_rehash() | Hash verification across governance tables |
| vega | lock_baseline() | Lock governance state with attestation |
| vega | evaluate_action_request() | Pre-flight action evaluation |

### 5.3 Implementation Files

| File | Phase | Purpose |
|------|-------|---------|
| 020_strategic_hardening_gartner.sql | A+B | Migration with all tables/functions |
| ed25519_keygen_v2.py | D | Real Ed25519 key generation |
| ignition_test_crio_graphrag.py | E | GraphRAG test |
| ignition_test_cseo_cot.py | E | CoT test |
| ignition_test_cfao_foresight.py | E | Foresight test |
| vega_ignition_attestation.py | F | Final attestation |

---

## 6. Operation Ignition – Hardened Boardroom Launch

### Phase A: Core Fuel & Governance Extension
- Load API keys via KeyStore (ADR-008)
- Run VEGA integrity rehash
- Lock new baselines
- Bind model tiers

### Phase B: Executive Contract Hardening
- Apply Gartner-mandated extensions to all Sub-Executive contracts
- Idempotent insertion (no deletion of governance history)

### Phase C: Sub-Executive Activation (ADR-014)
- Verify all 5 Sub-Executives registered
- Confirm `can_write_canonical = FALSE`
- Confirm `can_trigger_g2/g3/g4 = FALSE`
- Confirm `llm_tier = 2`

### Phase D: Key Generation & Provider Lock-in
- Generate Ed25519 keypairs for all 11 agents
- Register in fhq_meta.agent_keys
- Update fhq_org.org_agents
- Enforce model provider policy

### Phase E: Hardened Grand Slam (3-Loop Test)
- CRIO GraphRAG causal inference test
- CSEO CoT reasoning test
- CFAO synthetic foresight simulation test

**Pass Criteria (all tests):**
- Ed25519 signature verification ✓
- Discrepancy score < 0.05 ✓
- VEGA guardrail approval ✓
- Canonical READ-ONLY enforcement ✓

### Phase F: VEGA Final Attestation
- Pre-flight governance checks
- Action-level veto validation
- LLM tier-routing verification
- Lineage hash-chain checks
- Audit event classification

**Approval Token:** `ATT-VEGA-IGNITION-HARDENED-{timestamp}`

---

## 7. Consequences

### Positive
- Full Gartner 2025 Impact Radar alignment
- Constitutional-grade action control via VEGA LAM veto
- Explicit reasoning trails for all strategic outputs
- Knowledge graph architecture for causal inference
- Non-historical stress testing capability
- Hardened model tier separation

### Negative
- Increased complexity in contract management
- Higher computational cost for CoT logging
- Additional latency from pre-flight veto checks

### Risks
- GraphRAG performance under high query load → mitigated by caching
- Synthetic scenario generation quality → mitigated by VEGA validation
- CoT log storage growth → mitigated by retention policy (365 days)

---

## 8. Acceptance Criteria

ADR-015 is considered implemented when:

1. All executive contracts updated with Gartner mandates
2. VEGA action-level veto function operational
3. Model tier enforcement active for all 11 agents
4. CoT logging table accepting CSEO output
5. MKG tables ready for CRIO population
6. Synthetic stress pipeline (CDMO → CFAO) functional
7. All Phase E ignition tests passing
8. VEGA attestation token issued

---

## 9. Signatures

**Prepared by:** LARS – Chief Strategy & Alpha Officer
**Reviewed by:** STIG – CTO (Technical Validation)
**Attested by:** VEGA – Governance Authority (Constitutional Compliance)
**Approved by:** CEO – Final Constitutional Authority

---

## 10. Authority Chain Extension

```
ADR-001 (System Charter)
    ↓
ADR-014 (Sub-Executive Governance)
    ↓
ADR-015 (Strategic Hardening & Gartner 2025 Alignment) ← THIS DOCUMENT
```

**ADR-015 hereby extends the constitutional framework with Gartner 2025 Impact Radar alignment and hardened governance controls.**
