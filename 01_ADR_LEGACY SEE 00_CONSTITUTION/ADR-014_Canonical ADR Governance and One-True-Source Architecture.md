ADR-014 – Canonical ADR Governance & One-True-Source Architecture

Status: Draft for CEO Approval
Author: LARS (CSO – Logic, Analytics & Research Strategy)
Authority Chain: ADR-001 → ADR-002 → ADR-004 → ADR-006 → ADR-010 → ADR-013 → ADR-014
Tier: Constitutional Governance (Tier-1.5)
Effective Scope: All agents (LARS, STIG, LINE, FINN, VEGA), Orchestrator, fhq_meta schema
Purpose: Establish FjordHQ’s single canonical ADR governance architecture for all future extensions (ADR-015+)

1. Executive Summary

ADR-014 establishes the One True ADR Source, enforces VEGA-mediated governance, activates the full ADR-004 change-gate sequence, and defines the only permissible automated ADR ingestion pipeline for the FjordHQ Market System.

This ADR is the integration layer between the constitutional foundation (ADR-001 → ADR-013) and all future evolution of Vision-IoS.
From this point forward, all governance, all content, and all future ADRs must extend this chain. Any reference to ADRs outside ADR-001→ADR-013→ADR-014→(ADR-015, ADR-016, …) is considered invalid and must be rejected by VEGA.

This ADR is mandatory for institutional integrity, non-repudiation, and deterministic governance of FjordHQ’s constitutional architecture.

2. Problem Statement

Despite the presence of ADR-002 (Audit) and ADR-006 (VEGA governance), the system has exhibited:

divergent ADR lookups

inconsistent registry states

incomplete or partially registered ADRs

STIG observing “missing ADRs” even when present

staging data leaking into canonical reasoning

non-deterministic integration of ADR drafts

missing lineage, missing hash-chains, inconsistent reconciliation outputs

This creates unacceptable governance risk and violates:

BCBS-239 (single source of truth)

ISO 8000-110 (data lineage)

ISO 42001 (AI governance & auditability)

GIPS 2020 (governance over performance-impacting logic)

ADR-014 resolves this permanently.

3. Decision Overview
3.1 One True ADR Source (Canonical Registry)

FjordHQ adopts fhq_meta.adr_registry as the single authoritative source for all ADR metadata, content hashes, lineage, and canonical versions.

Supporting tables (archive, staging, ingestion buffers) may exist, but:

STIG has read-only rights to the canonical registry

STIG is forbidden from reading staging or ingestion tables

VEGA is the only entity allowed to write to canonical ADR tables

All reconciliation logic must resolve exclusively against canonical ADR data (ADR-010)

This fulfills BCBS-239 requirement for one single source of truth.

3.2 VEGA as Mandatory Intermediary for All ADR Queries

STIG, LARS, FINN, LINE, or CODE cannot query ADR data directly.

All ADR-related requests must flow through VEGA using:

vega_verify_hashes() (integrity check)

vega_compare_registry() (lineage + drift check)

VEGA may reject, warn, or escalate according to ADR-002 error classes and ADR-010 discrepancy scoring.

This eliminates divergent lookups and ensures consistent governance behaviour across all agents.

3.3 Strict Activation of ADR-004 Change Gates

No ADR may enter canonical state unless all gates pass:

G1 – Technical Validation (STIG)
Schema, integrity, reproducibility.

G2 – Governance Validation (LARS + VEGA)
Compliance with ADR-001–013, regulatory standards, scope controls.

G3 – Audit Verification (VEGA)
Hash-chain creation, lineage, reconciliation consistency (ADR-002 + ADR-010).

G4 – CEO Canonicalization
Final authority; version increment; registry write.

This eliminates the historical condition where ADRs become “half-registered” or inconsistently visible across agents.

3.4 Automated ADR-Writing Pipeline (The Only Allowed Pipeline)

Automated ADR creation is permitted only when following this exact sequence:

LARS generates ADR-draft in structured JSON

STIG performs G1 validation

VEGA performs G2 governance validation

VEGA executes G3 hashing, lineage, canonical snapshot

CEO approves via G4

STIG registers ADR automatically into canonical registry

VEGA signs and certifies the ADR as canonical

If any step fails, the pipeline aborts with a Class B/C governance event or a Class A critical event (ADR-002).

This pipeline is aligned with BCBS-239 traceability and ISO 42001 explainability.

3.5 Discrepancy Scoring Integration (ADR-010)

If STIG or any agent reports ADR data inconsistent with canonical state:

discrepancy_score > 0.10 → VEGA creates suspension request (ADR-009)

LARS reviews evidence and approves/rejects

The agent may be suspended until correctness is restored

This ensures autonomous detection of “ADR drift” or hallucination.

3.6 Kernel-Level Integration (ADR-013)

ADR governance becomes part of the FHQ-IoS Kernel:

ADR logic

registry schema

hash-chain verifier

comparison functions

governance gates

discrepancy scoring

attestation logic

VEGA certificate flow

Kernel snapshots must include ADR governance logic and exclude all non-canonical files, in accordance with ADR-013.

This ensures zero-drift deployment across machines and long-term reproducibility.

4. Scope

ADR-014 governs:

ADR ingestion

ADR lineage

ADR registry access

agent-to-ADR interactions

canonical state verification

governance mediation (VEGA)

automated ADR generation

change-gate enforcement

kernel snapshot inclusion of governance logic

Applies to all agents and all future ADRs.

5. Mandatory Governance Rules

All ADR references must fall within ADR-001 → ADR-014 (then ADR-015, ADR-016, etc.).
Any ADR outside this chain is invalid and must be rejected by VEGA.

VEGA must attest each new ADR before it becomes operational.

All ADR ingestion, validation, hashing, lineage, and certification must follow the pipeline defined in this ADR.

STIG is prohibited from reading any ADR source except the canonical registry.

Reconciliation logic (ADR-010) must treat any ADR discrepancy as governance-critical.

6. Institutional Rationale

This architecture satisfies:

BCBS-239: Single source of truth, lineage, accuracy, reconciliation

ISO 8000-110: Deterministic metadata governance

ISO 42001: AI governance, explainability, traceability

GIPS 2020: Performance governance, integrity of rules forming the investment process

It also aligns with established best practice in:

audit-driven change control

separation of duties

deterministic evidence pipelines

cryptographic attestability

ADR-014 is required to move Vision-IoS from “governed system” to “fully deterministic institutional platform”.

7. Consequences
Positive

Eliminates ADR drift forever

Guarantees deterministic ADR ingestion

Removes STIG lookup inconsistencies

Creates forensic audit traceability

Ensures long-term institutional reproducibility

Enables future fully automated governance loops

Integrates ADRs into Kernel snapshots for immutable deployment

Negative

Slows down ad-hoc ADR creation (by design)

Requires strict discipline and VEGA mediation

Risks

Incorrect VEGA configuration → mitigated via ADR-011 Fortress tests

Improper gating configuration → mitigated via ADR-004 enforcement

Bad JSON ADR drafts → rejected at G1

8. Next Steps

VEGA validates ADR-014 alignment with ADR-001 → ADR-013

CEO approves ADR-014 via G4

STIG registers ADR-014 into fhq_meta.adr_registry

VEGA certifies ADR-014 as canonical

LARS convenes MBB-level research council to design ADR-015 (meta-analysis of ADR ingestion framework)

9. Meta-Directive for Future ADRs

All new governance, architecture, or system features must extend the canonical chain:

ADR-001 → ADR-002 → … → ADR-013 → ADR-014 → ADR-015 → ADR-016 → …

Any ADR not in this lineage is invalid and constitutes a Class A governance event.

10. Signatures

Prepared by:
LARS – Chief Strategy & Alpha Officer

Reviewed by:
STIG – CTO (Technical Validation)
VEGA – Governance Authority (Compliance & Hash Verification)

To be approved by:
CEO – Final Canonical Authority

To be certified by:
VEGA – Attestation of Canonical Integration