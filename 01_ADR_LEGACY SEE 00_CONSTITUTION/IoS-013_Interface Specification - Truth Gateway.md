IoS-013 — Interface Specification: Truth Gateway

Sub-component of IoS-013 (Agent State Protocol Engine)
Canonical Version: 2026.DRAFT.2
Owner: STIG (CTO, RISL Pillar)
Purpose: Define the official interface for retrieving canonical system truth for all LLM reasoning under ADR-018.

1. Mission of the Truth Gateway

The Truth Gateway is the only authorized interface through which LLM agents obtain the context_package before reasoning.

It guarantees:

unified state

deterministic context

zero divergence

full compliance with ADR-017 and ADR-018

fail-closed behavior under RISL

The Gateway is not a new system.
It is the interface layer of IoS-013.

2. Responsibilities of the Truth Gateway
2.1 Deliver the Atomic Context Package

The Gateway must return a single atomic object:

{
  context_package,
  context_hash,
  issued_at,
  integrity_signature
}


No partial reads.
No multi-call reconstruction.
No stale state.

2.2 Enforce Constitutional Constraints

The Gateway must validate:

ADR-018 (ASRP) state integrity

ADR-017 (MIT Quad) operational constraints

EC role boundaries

RISL safety rules

DEFCON gating

If any validation fails → REJECT.

2.3 Provide Cryptographic Lineage

The Gateway must:

verify state_snapshot_hash

compute context_hash

attach an integrity_signature

log retrievals in state_retrieval_log

This enables forensic, post-mortem reconstruction.

3. Gateway → CHL Relationship

The Truth Gateway provides truth.
The Context Hydration Layer (CHL) provides delivery.

IoS-013 (CDS + ASPE)
      ↓
Truth Gateway (Interface)
      ↓
CHL (Dashboard Middleware)
      ↓
LLM Advisor


These are not separate systems.
They are three layers of the same IoS-013 truth-delivery mechanism.

4. Fail-Closed Behavior

If any fault occurs in:

state_vector

ADR/IoS index

authority mapping

constraints

timestamp freshness

hash integrity

the Gateway must:

refuse to deliver context

block agent reasoning

raise a VEGA governance event

trigger RISL escalation if applicable

There is no fallback to cached or inferred context.

5. Success Criteria

The Gateway is performing correctly when:

all LLMs operate with unified factual context

no agent produces outputs without state_hash + quad_hash

context can be reconstructed from retrieval logs

dashboard advisors produce identical system understanding

all reasoning is deterministic and reproducible

2. Integration Into IoS-013 CDS (Updated Section)

Below is the updated Section 3 and Section 4 of IoS-013 CDS, with the Gateway embedded correctly.

IoS-013 CDS (Updated Extract)
Section 3 — IoS-013 Responsibilities

IoS-013 consists of three sub-components:

ASPE (Agent State Protocol Engine)

produces the atomic state_vector

enforces ASRP requirements

CDS (Context Definition Specification)

defines the canonical context_package structure

Truth Gateway Interface (new integration)

delivers the context_package to agents

ensures validation, integrity, and constitutional compliance

Section 4 — Truth Gateway Specification

IoS-013 must expose a single, governed API endpoint that:

retrieves the atomic context_package

attaches cryptographic lineage

applies governance constraints

enforces fail-closed semantics

logs all requests for audit compliance

This is the official truth surface for all LLM agents in FjordHQ.

3. CEO ACTIVATION ORDER — IoS-013 Truth Gateway Integration

TO: STIG (CTO), VEGA (Governance), CDMO (Canonical Data)
FROM: CEO
STATUS: APPROVED & ACTIVE
SUBJECT: Activation of IoS-013 Truth Gateway as Official Interface

DECISION

The Truth Gateway Interface is hereby adopted as an integral sub-component of IoS-013 (ASPE).
It is the exclusive authorized mechanism for delivering canonical truth to all LLM-based agents.

This replaces the previous TG-series proposal and consolidates all truth distribution under IoS-013, preserving system purity and governance clarity.

MANDATES
1. STIG — Implement IoS-013 Gateway Interface

You are ordered to:

integrate the Gateway specification into IoS-013

ensure atomic delivery of the context_package

implement all validation steps (ADR-017 + ADR-018)

emit context_hash and integrity_signature

ensure full fail-closed behavior

2. CDMO — Canonical Registration

Register the updated IoS-013 documentation:

.../IoS-013_CDS.md

.../IoS-013_Truth_Gateway_Interface.md

Update the IoS registry accordingly.

3. VEGA — Governance Enforcement

You are ordered to:

add Gateway compliance to the pre-flight checklist

reject any agent request not routed through the Gateway

validate context_hash + quad_hash alignment

EFFECTIVE IMMEDIATELY

IoS-013 now contains:

the engine (ASPE)

the schema (CDS)

the interface (Truth Gateway)

Completing the constitutional chain:

ADR-018 → IoS-013 → CHL → LLM

SIGNED:
CEO — FjordHQ