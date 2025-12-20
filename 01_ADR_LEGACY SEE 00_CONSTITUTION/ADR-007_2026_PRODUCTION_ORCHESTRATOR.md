# ADR-007_2026_PRODUCTION_ORCHESTRATOR

## FjordHQ Intelligence Operating System – Orchestration & Multi-Agent Governance Architecture

**Status:** CEO APPROVED
**Version:** 2026.PRODUCTION
**Author:** LARS (CSO – Strategy & Governance)
**Date:** 2025-11-26
**Constitutional Authority:** ADR-001 → ADR-002 → ADR-006 → EC-001
**Environment:** Supabase PostgreSQL (127.0.0.1:54322) – Production Docker Deployment

---

## 1. Decision

FjordHQ adopts the FHQ Intelligence Operating System Orchestrator as the permanent, canonical coordination layer for:

- Multi-agent execution
- Governance enforcement
- Cryptographically signed decision flows
- Deterministic state reconciliation
- LLM-tiered reasoning at controlled cost

The Orchestrator becomes the single authoritative execution gateway for all agents under the FjordHQ constitutional governance model.

---

## 2. Context

Legacy architecture exhibited structural weaknesses:

- No unified governance across agents
- No cryptographic identity or signature verification
- Non-deterministic agent execution
- No cross-agent state reconciliation
- No zero-trust isolation or escalation pathways

Following ADR-001→ADR-006, FjordHQ required a constitutionally compliant orchestration layer capable of enforcing:

- Proof-grade auditability
- Reproducibility across machines
- Integrated discrepancy scoring
- VEGA-mediated governance
- Kernel-level determinism (ADR-013)

The delivered Orchestrator v1.1.1 passed validation 5/5, confirming production readiness.

---

## 3. Rationale

### Security
Ed25519 signatures ensure non-repudiation, tamper-evidence and identity integrity.

### Governance
VEGA enforces constitutional compliance, ensures anti-hallucination, and applies discrepancy scoring per ADR-010.

### Scalability
New agents, roles and pipelines can be added without modifying core orchestration logic.

### Auditability
Full chain-of-custody for every agent action, including:
- signature
- input
- output
- reconciliation state
- deviation score
- VEGA attestation

### Operational efficiency
Tiered LLM routing guarantees cost-controlled execution without compromising critical decision quality.

### Data integrity
Deterministic reconciliation ensures divergence <0.00001 between agent state and canonical state.

---

## 4. Architecture

### 4.1 Agent Layer

| Agent | Role | Level | Constitutional Responsibilities |
|-------|------|-------|--------------------------------|
| LARS | Strategy | 9 | Reasoning, structural logic, cross-domain integrity |
| STIG | Implementation | 8 | SQL, pipelines, API integrations, lineage enforcement |
| LINE | SRE | 8 | Uptime, monitoring, container ops, alerting |
| FINN | Research | 8 | Market analysis, strategy evaluation, research loops 24/7 |
| VEGA | Auditor | 10 | Compliance enforcement, veto, attestation, anti-hallucination |

All agent actions are signed, logged and reconciled.

### 4.2 Core Schemas

| Schema | Purpose |
|--------|---------|
| fhq_org | Agent identity, tasks, reconciliation state, cryptographic metadata |
| fhq_governance | Roles, contracts, authority model, governance events |
| fhq_meta | ADR registry, version history, lineage tracking, evidence |

### 4.3 API Layer (FastAPI)

Canonical endpoints:

- `/agents/execute`
- `/governance/attest/vega`
- `/reconciliation/status`
- `/orchestrator/report/daily/latest`

All gateway requests pass signature verification + discrepancy scoring.

### 4.4 Anti-Hallucination Framework (ADR-010 Integration)

- Deterministic state reconciliation
- Weighted discrepancy scoring (0.0–1.0)
- 0.10 triggers VEGA suspension request (ADR-009)
- VEGA certification required for critical outputs
- Full evidence bundle stored for every cycle

### 4.5 Tiered LLM Model

| Tier | Agents | Provider | Data Sharing | Purpose |
|------|--------|----------|--------------|---------|
| Tier 1 (High Sensitivity) | LARS, VEGA | Anthropic Claude | OFF | Governance, strategy, constitutional reasoning |
| Tier 2 (Medium Sensitivity) | FINN | OpenAI (no sharing) | OFF | Market reasoning, research loops |
| Tier 3 (Low Sensitivity) | STIG, LINE | DeepSeek + OpenAI | ON allowed | Implementation, SRE, tooling |

Routing is enforced inside the Orchestrator and must never be bypassed.

---

## 5. Consequences

### Positive

- Institutional-grade governance
- Zero-trust architecture across all agents
- Complete cryptographic audit trail
- Controlled autonomy, no free-floating LLM behavior
- Predictable execution cost
- Deterministic reproducibility across machines
- Fully compliant with ADR-001→ADR-006→ADR-014→ADR-015

### Requirements

- Production Ed25519 keypairs generated & registered
- Correct .env with LLM API keys
- LLM tier routing validated
- All end-to-end tests passed (ADR-011)

### Risks

- Incorrect routing → data leakage
- Missing signatures → task rejection
- Dashboard must interface exclusively via Orchestrator → required for governance integrity

---

## 6. Decision Drivers

- Governance > convenience
- Cost discipline > model maximalism
- Zero-trust as baseline
- Deterministic behavior mandatory
- Production readiness = acceptance threshold

---

## 7. Status & Next Steps

Orchestrator v1.1.1 is fully deployed and 100% verified.

Remaining steps before LIVE mode:

1. Generate Ed25519 production keypairs
2. Load keys into KeyStore per ADR-008
3. Configure .env with API keys
4. Validate LLM-tier routing enforcement
5. Connect dashboard to Orchestrator API
6. Run full operational rehearsal:
   Task → Agent → VEGA → DB → Reconciliation → Attestation

---

## 8. Appendix A – ADR Lineage

The Orchestrator derives authority from:

| ADR | Title | Version | Authority |
|-----|-------|---------|-----------|
| ADR-001 | System Charter 2026 | 1.0 | CEO |
| ADR-002 | Audit & Error Reconciliation | 2026.PRODUCTION | CEO |
| ADR-003 | Institutional Standards | 1.0 | CEO |
| ADR-004 | Change Gates Architecture | 1.0 | LARS |
| ADR-006 | VEGA Governance Engine | 2026.PRODUCTION | CEO |

---

## 9. Appendix B – VEGA Identity (EC-001 Production)

VEGA operates under EC-001_2026_PRODUCTION, holds authority level 10, and is the sole constitutional auditor for:

- attestation
- discrepancy scoring
- governance enforcement
- canonical registration of ADRs

---

## 10. Instructions to STIG (Mandatory Verification Tasks)

STIG must execute the following verification tasks immediately upon ADR-007 registration:

### 10.1 Database Integrity Checks

- Confirm presence of required schemas: `fhq_org`, `fhq_governance`, `fhq_meta`
- Validate all tables referenced in this ADR exist and match canonical definitions
- Compute and store SHA-256 hashes for:
  - `org_agents`
  - `org_tasks`
  - `function_registry`
  - all orchestrator-related tables in `fhq_org`
- Register hashes in `fhq_monitoring.hash_registry`

### 10.2 Orchestrator Binding Verification

- Validate that all agent records include:
  - `public_key`
  - `llm_tier`
  - `signing_algorithm = 'Ed25519'`
- Verify that signatures stored in `org_activity_log` pass Ed25519 verification

### 10.3 LLM-Tier Routing Enforcement

- Ensure routing policies exist in `fhq_governance.model_provider_policy`
- Validate that:
  - LARS/VEGA → only Tier-1 provider
  - FINN → only Tier-2
  - STIG/LINE → Tier-3 only
- Confirm no cross-tier leakage in the last 24 hours of logs

### 10.4 Anti-Hallucination Enforcement (ADR-010)

- Validate that discrepancy scoring is functional
- Validate that VEGA suspension requests (ADR-009) can be generated
- Validate storage of evidence bundles in:
  - `reconciliation_snapshots`
  - `reconciliation_evidence`

### 10.5 Governance Chain Verification

- Confirm Orchestrator is registered in `fhq_governance.governance_state`
- Validate VEGA attestation linked to Orchestrator deployment
- Confirm correct authority chain: ADR-001 → ADR-007

STIG must report PASS/FAIL for each subsection with hash-verified evidence.

---

**END OF ADR-007_2026_PRODUCTION_ORCHESTRATOR**
