ADR-024 — AEL Phase Gate Protocol

Five-Rung Autonomy Ladder & Pre-Signable Intervention Categories

Status: APPROVED (G4 Activated 2026-01-14)
Tier: CONSTITUTIONAL – LEARNING GOVERNANCE
Owner: CEO
Governing Authorities: FINN (Methodology), STIG (Runtime), VEGA (Compliance)
Dependencies: ADR-001, ADR-003, ADR-010, ADR-012, ADR-016, ADR-017, ADR-018, ADR-020, ADR-021, ADR-022, ADR-023
Scope: Autonomous Epistemic Learning (AEL) only – not execution, not capital allocation

1. Purpose

This ADR formally defines what qualifies as autonomous learning inside FjordHQ and establishes a phase-gated path from observation to bounded autonomy.

The protocol exists to prevent three systemic failures:

Confusing local optimization with learning

Allowing silent drift under the guise of “improvement”

Granting write-access before epistemic competence is proven

Autonomy without proof is not intelligence. It is risk.

2. Audit-Grade Definition of Autonomous Learning

For FjordHQ, autonomous learning is not a metric improvement, a one-off delta, or a human-authorized tweak.

Autonomous learning exists if and only if all of the following conditions are met:

Intervention Proposal
AEL produces a concrete, bounded intervention candidate with:

explicit scope

stated hypothesis

expected direction of effect

Controlled Application
The intervention is applied only through a declared gate.

No silent parameter drift

No implicit overwrite

No retroactive mutation

Out-of-Sample Evaluation
The system evaluates impact using:

predefined holdout logic (or equivalent)

declared horizon(s)

declared asset coverage

Replicable Improvement
Improvement must be:

statistically meaningful

operationally relevant

observable again in subsequent independent cycles

Deterministic Rollback
The system can revert to the prior state with:

exact version recovery

no residual contamination

Full Attribution
Every step is:

hash-bound

time-bound

agent-attributable

evidence-backed

If any of these elements are missing, the activity is classified as:

Optimization Experiment – Not Autonomous Learning

This distinction is constitutional.

3. The Missing Transition: Effect vs Learning

FjordHQ currently demonstrates real effect, but not yet autonomous learning, because:

Coverage is partial (crypto + 1h horizon only)

Intervention authority is external (CEO / FINN / STIG)

Generalization across assets, regimes, and horizons is unproven

Repeatability across independent cycles is not established

This is correct and expected at this stage.

The objective of ADR-024 is not to accelerate autonomy, but to prevent premature autonomy.

4. The Five-Rung Autonomy Ladder (Non-Skippable)

Autonomy is earned sequentially. Skipping rungs destroys causality.

Rung A — Measurement Completeness

Learning cannot exist without complete outcomes.

Minimum requirements:

Continuous outcome matching across asset classes

crypto (24/7)

equities (exchange hours)

Multi-horizon support (e.g. 1h, 24h) with correct clocks

No sparse outcome domains

Failure mode if violated:

Subset learning

False confidence

Regime-conditional hallucination

Rung B — Canonical Evaluation Contract

All learning must be evaluated under a single invariant contract:

Fixed metric definitions

Fixed bucketing logic

Fixed sampling rules

Explicit leakage protections

If evaluation logic drifts, learning becomes undefined.

This rung establishes:

One definition of “better”, invariant over time.

Rung C — Intervention Registry & Causal Isolation

Every intervention must be:

Uniquely identified (hash + version)

Explicitly scoped (what it may touch)

Executed in isolation windows (e.g. LDOW)

Attribution must be unambiguous.

This prevents:

Cross-contamination

Post-hoc rationalization

Narrative overfitting

Rung D — Autonomous Proposal, Human-Authorized Execution

At this rung:

AEL may propose interventions

AEL may not execute them

Humans authorize execution under governance.

Success criteria:

Proposals are consistently coherent

Evidence is sufficient pre-execution

Rejections are rare and explainable

This is autonomy with a safety catch.

Rung E — Autonomous Execution Under Pre-Signed Policy

This is the first rung where operational autonomous learning exists.

Conditions:

Only pre-approved intervention classes

Strict parameter envelopes

Automatic rollback mandatory

VEGA attestation remains absolute

Execution autonomy is bounded, revocable, and supervised.

5. Pre-Signable Intervention Categories

Only the following categories may ever be pre-approved for autonomous execution:

Calibration tuning within fixed bounds

Threshold adjustments without topology change

Weight re-normalization under invariant schemas

Explicitly excluded:

Feature creation or removal

Regime logic changes

Objective function redefinition

Capital or execution logic

Each category requires:

Defined blast radius

Defined rollback path

Defined evaluation horizon

6. Learning Autonomy – Domain-Specific Meaning

FjordHQ operates supervised probabilistic forecasting, not reinforcement learning from execution.

Therefore, learning is defined as:

Improved calibration (probabilities match frequencies)

Improved skill / resolution (ΔFSS ≥ 0)

Improved generalization (holdout deltas persist across cycles)

All improvements must respect:

latency constraints

safety envelopes

DEFCON governance

Economic Safety (ADR-012)

7. The Prime Rule of Autonomy

Write-access is earned through repeated correct read-only judgments.

Therefore:

Multiple cycles are mandatory

Coverage must expand deliberately

Metric gaming is prohibited

Silent drift is a Class-A violation

Stillness is not weakness.
Stillness is discipline.

8. AEL Phase Gate Model (Canonical)
Phase	Capability	Authority
Phase 0	Observation only	Current state
Phase 1	Read-only evaluation + evidence packaging	Near-complete
Phase 2	Intervention proposal	Next gate
Phase 3	Execution of pre-approved classes	Conditional
Phase 4	Expanded bounded autonomy	Future

Progression requires explicit gate approval.
No implicit promotion exists.

9. Governance & Enforcement

ADR-024 is enforced via ADR-018 (State Reliability)

Violations escalate under ADR-016 (DEFCON)

Unauthorized execution is a Class-A breach (ADR-009)

This ADR does not accelerate autonomy.
It protects the right kind of autonomy.

10. Final Statement

FjordHQ does not chase autonomy.
It earns it.

Autonomous learning is not speed.
It is earned write-access after epistemic proof.

End of ADR-024