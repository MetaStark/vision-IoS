ADR-007_2026_PRODUCTION_ORCHESTRATOR

Status: ACCEPTED
Author: LARS (CSO – Strategy & Governance)
Date: 2026-01-01
Constitutional Authority: ADR-001 → ADR-002 → ADR-006 → EC-001
Production Environment: Supabase Docker (127.0.0.1:54322)

1. Decision

FjordHQ adopts FHQ Intelligence Operating System v1.1.1 as the permanent production architecture for multi-agent orchestration, governance, and intelligence.

This system is now the single authoritative coordination layer for all agents and automated decision processes across FjordHQ.

2. Context

The legacy architecture lacked:
– Centralized agent governance
– Cryptographic auditability
– Deterministic task execution
– Cross-agent state reconciliation
– Zero-trust controls

To resolve these gaps, FHQ-ORCHESTRATOR v1.1.1 introduces a unified intelligence layer with verified deployment as of 2025-11-21 (5/5 PASS).

3. Rationale

Security – Ed25519 signing prevents impersonation and tampering.

Governance – VEGA enforces constitutional compliance and anti-hallucination.

Scalability – New agents can be added without modifying core logic.

Auditability – Full chain-of-custody logging.

Operational Efficiency – Tiered LLM usage optimizes cost without degrading quality.

Data Integrity – Reconciliation ensures <0.00001 divergence between agent state and canonical state.

4. Architecture
4.1 Agents
Agent	Role	Level	Responsibility
LARS	Strategy	9	Logic, audit, structural reasoning
STIG	Implementation	8	SQL, pipelines, external APIs
LINE	SRE	8	Stability, uptime, monitoring
FINN	Research	8	Market analysis and insights
VEGA	Auditor	10	Oversight, veto, anti-hallucination

All actions are cryptographically signed and logged in org_activity_log.

4.2 Core Schemas

fhq_org – agents, tasks, memory, reconciliation

fhq_governance – roles, contracts, authority model

fhq_meta – ADR logs, data lineage, certification registry

4.3 API Layer (FastAPI)

Includes:
– /agents/execute
– /governance/attest/vega
– /reconciliation/status
– /orchestrator/report/daily/latest

4.4 Anti-Hallucination Framework

Deterministic state reconciliation

Discrepancy scoring (0.0–1.0)

Automatic suspension at >0.1 deviation

VEGA certification required for all critical outputs

4.5 LLM Tier Model

Tier 1 – High sensitivity: LARS, VEGA → Anthropic Claude (no data sharing)
Tier 2 – Medium sensitivity: FINN → OpenAI (no sharing)
Tier 3 – Low sensitivity: STIG, LINE → DeepSeek + OpenAI (sharing ON allowed)

5. Consequences
Positive

– Institutional-grade governance
– Zero-trust architecture
– Complete audit trail
– Controlled autonomy
– Reduced operational cost
– Predictable agent behaviour
– Full reproducibility

Requirements

– Real Ed25519 keypairs
– .env configuration with LLM keys
– Agent → LLM routing rules
– Completion of end-to-end tests

Risks

– Incorrect LLM routing may expose sensitive data
– Missing keys will disable signing
– Dashboard must interface through orchestrator to maintain governance integrity

6. Decision Drivers

Governance over convenience

Cost discipline over model maximalism

Zero-trust as default

Deterministic behaviour

Production readiness as acceptance threshold

7. Status & Next Steps

Orchestrator v1.1.1: Fully deployed, verified 5/5, production-ready.

Remaining to go live:

Generate Ed25519 production keypairs

Configure .env with proper API keys

Implement LLM tier routing

Connect dashboard to orchestrator API

Execute full operational rehearsal (Task → Agent → VEGA → DB)

8. Appendices

– ADR-001 Constitutional Charter
– ADR-002 Authority Model
– ADR-006 Cryptographic Framework
– EC-001 VEGA Identity Specification
– Migration 008 Deployment Log