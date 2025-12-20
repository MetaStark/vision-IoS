ADR-017 — THE MIT QUAD PROTOCOL FOR ALPHA SOVEREIGNTY

Canonical Version: 2026.PROD.1
Status: ACTIVE / CONSTITUTIONAL
Owner: CEO
Authority: MIT Quad (LIDS-ACL-DSL-RISL)
Dependencies: ADR-001, ADR-010, ADR-013, ADR-014, ADR-015, ADR-016, IoS-003, IoS-004, IoS-006, IoS-007

1. Executive Summary

ADR-017 establishes The MIT Quad Protocol as the constitutional intelligence architecture of FjordHQ.

The protocol fuses four MIT research disciplines into a unified, auditable operating system:

LIDS — Inference & Truth

ACL — Coordination & Synchronization

DSL — Optimization & Execution Logic

RISL — Immunity & Systemic Resilience

Together, these four pillars upgrade FjordHQ from an automated system to a fully autonomous one by enforcing a deterministic loop:

Sense → Understand → Decide → Defend.

The MIT Quad becomes the binding mechanism for:

epistemic certainty

coordination between agents

risk-adjusted allocation

immune response to drift, contamination, or hallucination

ADR-017 formally defines how truth is discovered, how tasks are allocated, how capital is deployed, and how the system protects itself from failure.

This document is constitutional and cannot be altered without full G4 CEO ratification.

2. Strategic Mandate

FjordHQ operates under the Freedom Equation:

𝐹
𝑟
𝑒
𝑒
𝑑
𝑜
𝑚
=
Alpha Signal Precision
Time to Autonomy
Freedom=
Time to Autonomy
Alpha Signal Precision
	​


The MIT Quad is the mathematical and governance backbone that maximizes both numerator and denominator:

Precision is enforced via LIDS + DSL.

Autonomy is enforced via ACL + RISL.

ADR-017 therefore becomes the operating law that connects:

perception (IoS-003)

research (CRIO / IoS-007)

execution (IoS-004)

protection (ADR-016 DEFCON)

canonical truth (ADR-013)

into a single, unified architecture.

3. The MIT Quad – Constitutional Definition

The MIT Quad is the only recognized intelligence model of FjordHQ.

MIT Pillar	MIT Domain	FjordHQ Role	Core Responsibility	Constitutional Constraint
LIDS	Inference & Decision Systems	Truth Engine	Ensures all decisions are grounded in statistical and causal truth	Cannot operate on unvalidated or non-canonical data
ACL	Control & Coordination	Coordination Layer	Synchronizes agents, resolves conflicts, enforces CBBA task allocation	Cannot override canonical truth or strategy signatures
DSL	Optimization & Operations Research	Allocation Engine	Translates truth into optimal risk-adjusted exposure	Cannot modify truth or perception inputs
RISL	Resilience & Immunity	Immune System	Detects drift, anomalies, hallucination, corruption	Can freeze system (DEFCON) but cannot change strategy

This quadrant is mutually interdependent, but strictly non-overlapping, satisfying ADR-014 (Role Separation) and ADR-015 (Meta-Governance).

4. Constitutional Architecture
4.1 Truth Domain (LIDS)

LIDS verifies the epistemic certainty of any signal before it enters exposure logic.

Mandatory constraint:

𝑃
(
𝑡
𝑟
𝑢
𝑡
ℎ
)
>
0.85
P(truth)>0.85

No allocation engine (DSL) may run without this certification.

LIDS is read-only toward canonical truth (ADR-013).

4.2 Coordination Domain (ACL)

ACL prevents conflicting agent behavior by enforcing a Consensus-Based Bundle Allocation (CBBA) mechanism for task assignment.

ACL ensures:

deterministic coordination

non-overlapping responsibilities

reproducible task routing

temporal ordering of multi-agent workflows

ACL is the constitutional governor of time, sequence, and synchronicity.

4.3 Optimization Domain (DSL)

DSL transforms validated truth into actionable allocation using:

stochastic optimization

tail-risk aware constraints (CVaR)

uncertainty-weighted bet sizing

deterministic replay capability

All DSL actions must be reproducible under historical replay without drift.

4.4 Immunity Domain (RISL)

RISL defends the system by:

detecting data drift

detecting hallucination patterns

detecting schema anomalies

detecting runtime inconsistencies

triggering ADR-016 DEFCON transitions

RISL operates a fail-safe architecture:
Prefer stopping the system over letting contaminated logic propagate.

RISL cannot alter strategy but can quarantine and halt execution.

5. Canonical Dataflow & Temporal Causality

ADR-017 requires strict temporal directionality to prevent self-referential inference.

5.1 State-Lag Rule

CRIO may only read:

IoS-007 Alpha Graph (Snapshot T-1)

This prevents race conditions, circular logic, and non-deterministic feedback loops.

5.2 Canonicalization Rule

CRIO may not write to canonical truth.

Only IoS-006 (Macro Validation Layer) may elevate research signals to:

fhq_macro.canonical_features

This satisfies ADR-013 (Truth), ADR-014 (Role Boundaries), and ADR-015 (Governance).

6. Interaction Map & Role Isolation Contract (Canonical Definition)

The following section is binding and constitutional.
Violation constitutes Class A or Class B governance breach.

6.1 Purpose

To guarantee:

clean separation of fetch, reasoning, perception, and decision

elimination of hallucinatory pathways

deterministic auditability of perception

preservation of canonical truth

MIT Quad compliance

This section establishes the only valid dataflow architecture of FjordHQ.

6.2 Role Archetypes
CEIO — “The Hunter” (Search–Fetch Subsystem)

Tier: 2
Authority: Fetch → Clean → Stage
Writes: fhq_macro.raw_staging

CEIO is FjordHQ’s only outward-facing sensory organ.

Forbidden:

analysis

scoring

model inference

access to IoS-003 or IoS-004

writing to any canonical domain

CRIO — “The Researcher” (Causality Engine)

Tier: 2
Authority: Interpret → Validate → Convert → Feature
Reads: raw_staging, IoS-002, IoS-007 (T-1 Snapshot)
Writes: fhq_research.signals

CRIO decides whether the external world has meaning.

Forbidden:

writing to canonical truth

performing perception

altering regime logic

self-referential inference

IoS-006 — Macro Validation Layer (Port of Admittance)

Only IoS-006 may elevate signals into canonical truth.

Writes: fhq_macro.canonical_features
Reads: CRIO signals, structural indicators
Controls: statistical validation, lineage enforcement

IoS-006 is the constitutional gate into ADR-013 truth.

IoS-003 — “The Overview” (Meta-Perception Engine)

Tier: 1
Authority: Perceive → Classify → Summarize → Determine Regime
Reads: canonical_features (IoS-006), IoS-002 technical indicators
Writes: regime_state

IoS-003 never fetches, never researches, never reads external raw text.

Forbidden:

Internet access

Serper

consuming unvalidated data

modifying canonical truth

6.3 Mandatory Processing Order (Pipeline Invariant)

This invariant is constitutional:

[1] CEIO → raw_staging
      ↓
[2] CRIO → research_signals
      ↓
[3] IoS-006 → canonical_features
      ↓
[4] IoS-003 → regime_state
      ↓
[5] IoS-004 → target_exposure


If lineage for all steps [1]→[4] is not complete:

IoS-003 must ignore the signal and log a discrepancy_event (ADR-010).

6.4 Interaction Map (Audit-Ready)
Layer	Reads	Writes	Forbidden	ADR Alignment
CEIO	Internet, APIs	raw_staging	IoS-003, IoS-004	ADR-014
CRIO	raw_staging, IoS-007 (T-1)	research_signals	canonical truth	EC-004, ADR-010
IoS-006	research_signals	canonical_features	raw external data	ADR-013, ADR-015
IoS-003	canonical_features, IoS-002	regime_state	external APIs, raw text	IoS-003 Spec
IoS-004	regime_state	exposure tables	non-canonical data	IoS-004 Spec
6.5 MIT Quad Enforcement Rules
MIT Layer	Domain	Bound Actor(s)	Enforcement Rule
LIDS	Truth	IoS-003	Must reject any feature not elevated by IoS-006
ACL	Coordination	CRIO, IoS-006	Must wait for CEIO batch completion before processing
DSL	Optimization	IoS-004	Must use validated regime_state; stochastic optimization must be deterministic under replay
RISL	Immunity	ALL	If CEIO fetches poisoned data → isolate pipeline & trigger DEFCON (ADR-016)
6.6 Constitutional Status

The interaction model above is:

Canonical under ADR-013

Role-bound under ADR-014

Meta-governed under ADR-015

Runtime-protected under ADR-016

Class A Violation:
Any attempt by IoS-003 to access the internet.

Class B Violation:
Missing lineage hash between CRIO → IoS-006.

Mandatory Action:
Violations must trigger RISL, DEFCON reassessment, and automatic isolation.

7. Activation & Governance

ADR-017 becomes effective immediately upon CEO signature.

All modules interacting with perception, research, external fetch, allocation, or immune response must comply.

Modifications require G4 CEO approval and VEGA co-signing.

All trades must include Quad-Hash:
{LIDS}_{ACL}_{DSL}_{RISL}.

8. Acceptance Criteria (G1 → G4)
G1 — Technical Validation (STIG)

Role isolation verified

T-1 snapshot enforcement verified

IoS-006 ingest gate validated

Pipeline determinism confirmed

G2 — Governance Validation (VEGA)

Lineage compliance

Discrepancy event routing

DEFCON integration

G3 — Integration

Runtime orchestration alignment

Multi-agent synchronization

G4 — Constitutional Activation

Final CEO ratification

Immutable storage under ADR-013

9. Signatures

CEO — FjordHQ
LARS — Chief Strategy Officer
STIG — Chief Technology Officer
VEGA — Chief Compliance & Governance Officer
CFAO — Chief Foresight & Autonomy Officer