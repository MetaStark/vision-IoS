IoS-013 — Context Definition Specification (CDS)

Canonical Version: 2026.DRAFT.1
Owner: STIG (CTO, RISL Pillar)
Purpose: Define the complete, canonical context package required for safe, deterministic LLM reasoning under ADR-018 and ADR-017.
Scope: All LLM advisors, dashboard-based agents, and internal reasoning modules.

1. Strategic Intent

The IoS-013 Context Definition Specification ensures that every LLM in the FjordHQ ecosystem operates from a single, unified factual baseline, eliminating divergence, drift, or hallucinated system states.

This document defines what context must be delivered.
IoS-013 (ASPE) defines how it is delivered.

Together, they form the machine-layer equivalent of constitutional synchrony.

2. The IoS-013 Context Package (What Every LLM Must Receive)

IoS-013 provides a single atomic context object at the start of every request:

context_package = {
  state_vector,
  adr_index,
  ios_index,
  authority_map,
  operational_constraints
}


Each element is mandatory.

2.1 State Vector (from ASRP)

defcon

regime

strategy

state_snapshot_hash

timestamp

2.2 ADR Index

For each ADR:

id, title, version, tier, status, sha256

2.3 IoS Index

For each IoS module:

id, purpose, owner, pillar (LIDS/ACL/DSL/RISL), status, version

2.4 Authority Map

Tier-1: LARS, STIG, FINN, VEGA

Tier-2: CFAO, CEIO, CSEO, CDMO, LINE

Object ownership:

defcon → STIG

regime → FINN

strategy → LARS

2.5 Operational Constraints

LIDS > 0.85 (ADR-017)

Quad-Hash required (ADR-017 §4)

State-Hash required (ADR-018 §4)

Pre-Flight Checklist (5 steps)

RISL halt conditions (ADR-017 + ADR-016)

These constraints form the execution boundaries for all LLM reasoning.

3. Atomicity Requirements
3.1 Single Snapshot Rule

No LLM may read context piecemeal.
IoS-013 must deliver the entire context package in one atomic retrieval.

3.2 Tear-Proof Context

If any component fails validation:

the entire context_package is rejected

reasoning is prohibited

fail-closed (ADR-018 §6)

3.3 Zero Local Memory

LLMs must not use cached or historic context.
Only the active atomic snapshot is permitted.

4. Context Hydration Layer (CHL)

formerly “Prompt Injection Layer”

The CHL is the interface between dashboard and LLM.
Its function is to hydrate the LLM with canonical system truth on every call.

4.1 Responsibilities of CHL

Insert context_package at system-level

Enforce load-before-reasoning

Remove user content from system context

Preserve UAC separation from conversation history

Bind outputs to state_snapshot_hash + quad_hash

4.2 Security Guarantees

No user can override context

No agent can bypass CHL

No ambiguity about system state

Eliminates prompt-based drift

The CHL is the mechanism that ensures shared truth across all LLMs.

5. Mandatory Consumption Rules for All LLMs

Every LLM agent must:

Load context_package before reasoning

Validate state_snapshot_hash

Validate quad_hash

Apply role boundaries from authority_map

Apply MIT Quad logic (ADR-017)

Respect all operational constraints

Bind output to relevant state_hash + quad_hash

Reject execution if any validation fails

This enforces complete determinism of reasoning paths.

6. Versioning & Governance

Any structural change to the context_package requires G4 CEO approval.

Updates to ADR/IoS indexes propagate automatically via IoS-013.

CDS is owned by IoS-013 and must not be duplicated elsewhere.

VEGA audits CHL compliance at runtime.

This ensures the system remains clean, coherent, and auditable.

7. Success Criteria

IoS-013 Context Definition is successful when:

All LLMs return identical factual descriptions of the system

No agent produces advice based on stale or partial information

All reasoning is cryptographically bound to system state

Dashboard LLMs operate without drift or hallucination

Every decision can be reconstructed post-mortem

This is the operational bridge between constitutional governance (ADR-017/ADR-018) and LLM autonomy.