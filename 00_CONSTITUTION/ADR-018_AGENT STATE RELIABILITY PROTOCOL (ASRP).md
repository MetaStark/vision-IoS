ADR-018 — AGENT STATE RELIABILITY PROTOCOL (ASRP)

Canonical Version: 2026.PROD.2
Status: CONSTITUTIONAL — ACTIVE
Owner: CEO
Dependencies: ADR-001, ADR-013, ADR-016, ADR-017
Implements: Mandatory Synchronized State for All Agents

1. Purpose & Strategic Mandate

ADR-018 establishes the Agent State Reliability Protocol (ASRP): FjordHQ’s constitutional guarantee that all agents operate from one unified, verified, cryptographically-pinned state before producing any reasoning, strategy, execution, or governance artifact.

ASRP ensures:

Zero drift in agent perception

Deterministic coordination across LIDS–ACL–DSL–RISL (ADR-017)

Immutable auditability of all decisions

Protection against hallucination, divergence, and stale reasoning

Full compliance with ADR-013 (One-True-Source) and ADR-016 (DEFCON)

ASRP is a non-bypassable precondition for intelligence and autonomy.

2. The Synchrony Requirement (Non-Negotiable)

No agent may initiate reasoning, forecasting, or action unless a fresh, verified Shared State has been atomically retrieved from IoS-013.

This applies universally to:

Tier-1 Executives (LARS, STIG, FINN, VEGA)

Tier-2 Sub-Executives (CFAO, CSEO, CEIO, CDMO, LINE)

Tier-3 Units (CODE, pipelines, orchestrators)

The Shared State is not optional.
It is the constitutional starting point of every cognitive act.

3. Scope of Shared State (v1 Canonical Set)

ASRP recognizes exactly three state objects in v1:

3.1 current_defcon

Authority: STIG — ADR-016
Defines operational safety posture.

3.2 btc_regime

Authority: FINN — IoS-003 Canonical Regime
Defines market condition truth (LIDS pillar).

3.3 canonical_strategy

Authority: LARS — IoS-004 Allocation Doctrine
Defines the system’s active strategic posture.

No additional state objects may be introduced without G4 approval.

4. Atomic Synchronization Principle (New Constitutional Principle)

ASRP treats Shared State as a single atomic vector.

4.1 Atomicity Guarantee

Agents may not read state objects individually.
They must retrieve:

state_vector = {defcon, regime, strategy, hash, timestamp}


Where all fields:

are generated in the same system tick

share the same composite hash

reflect the same authoritative snapshot

4.2 Torn-Read Prohibition

If any component fails validation (freshness, hash mismatch, ownership),
the entire retrieval is invalid.

Partial reads are unconstitutional.

5. Output Binding Requirement (Chain of Custody) — NEW

Every agent-produced artifact must embed the state_snapshot_hash that governed the decision.

This applies to:

reasoning outputs

strategy proposals

execution plans

code artifacts

governance decisions

trades and allocations

Insight Packs, Skill Reports, Foresight Packs

5.1 Immutable Link

Every output must include:

state_snapshot_hash
state_timestamp
agent_id


This establishes a cryptographically provable link between context and action, enabling deterministic post-mortem reconstruction under ADR-002/ADR-011 lineage requirements.

No agent output is valid without its contextual fingerprint.

6. Fail-Closed Default (Zero-Trust Runtime) — NEW

ASRP is governed by a Zero-Trust safety model.

6.1 Halt-On-Silence Rule

If IoS-013 is:

unreachable

delayed beyond the latency threshold

returns corrupted state

returns a hash mismatch

exhibits inconsistent authority

then the system must immediately HALT.

6.2 No Local Caching

No agent may:

reuse previous state

fall back to cached local state

generate synthetic substitutes

guess missing state

Local caching is classified as an ADR-018 breach and a Class-A governance violation.

6.3 DEFCON Escalation

Any ASRP failure automatically triggers:

minimum DEFCON YELLOW (execution freeze)

VEGA review

STIG infrastructure audit

This is enforced under ADR-016.

7. Enforcement & Violations
7.1 Class A Governance Violation

Any attempt to:

bypass ASRP

use stale or uncoupled state

produce output without state_hash

override ownership boundaries

operate after an invalid read

constitutes a Class-A violation and triggers ADR-009 suspension.

7.2 Isolation & Containment

Under RISL (ADR-017), agents exhibiting drift or mismatch must be:

isolated immediately

quarantined from the orchestration bus

prevented from further reasoning

Reintegration requires VEGA approval.

8. Governance Integration
8.1 ADR-013 — Truth Architecture

ASRP stores summaries and pointers only.
Truth itself remains in canonical schemas.

8.2 ADR-016 — Safety

current_defcon gating must be evaluated as part of the atomic vector.

8.3 ADR-017 — MIT Quad

ASRP delivers the coordination substrate required by:

LIDS: truth depends on regime

ACL: coordination depends on shared strategy

DSL: allocation depends on DEFCON and strategy

RISL: immunity depends on state integrity

ASRP is the synchronization backbone of MIT Quad.

8.4 IoS-013 — Implementation

IoS-013 is the exclusive technical executor of ADR-018.
No alternative implementations are allowed.

9. Lifecycle & Evolution
9.1 Amendments

Any change to:

atomicity semantics

state object definitions

authority mapping

fail-closed logic

requires G4 CEO approval.

9.2 Expansion

New Shared State fields require:

FINN causal-truth approval

STIG schema & integrity approval

VEGA governance paper

CEO G4 ratification

9.3 Deprecation

State deprecation follows ADR-015 lifecycle governance.

10. Signatures

CEO — FjordHQ
STIG — Technical Authority
LARS — Strategic Authority
FINN — Research Authority
LINE — Execution Authority
VEGA — Governance & Compliance