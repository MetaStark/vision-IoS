ADR-010 – State Reconciliation Methodology & Discrepancy Scoring

Status: Approved
Date: 2025-11-22
Owner: LARS – Chief Strategy & Alpha Officer
Governance Tier: Tier-2 (Validation, Integrity, Anti-Hallucination)
Affects: VEGA, Worker, Reconciliation Service, fhq_meta, fhq_governance
Supersedes: None
Review Cycle: 12 months

1. Context

Autonomous agents within FjordHQ-IoS produce state assessments, analyses, metrics, and recommendations.
These outputs must be continuously reconciled against the canonical system-of-record to detect:

hallucination

data drift

stale state

implementation errors

tampering or corruption

divergence from financial truth

Without a mathematically defined methodology, deviations would be ambiguous, unscaled, and inconsistently interpreted.

Tier-2 governance therefore requires a deterministic, reproducible, verifiable method for calculating discrepancy scores, producing evidence, and triggering VEGA oversight and LARS governance review.

This ADR defines that methodology in full.

2. Decision

FHQ-IoS adopts a unified, weighted, tolerance-aware discrepancy scoring system applied to every agent and every reconciliation cycle.

Key decisions:

Field-by-field comparison with binary match/mismatch

Criticality-weighted metric

Tolerance layer for timestamps, floats, and metadata

Three-tier discrepancy classification (Normal, Warning, Catastrophic)

Canonical evidence bundle stored for every reconciliation

Automatic VEGA attestation; no agent self-evaluation

Suspension workflow governed by ADR-009 (dual approval)

The discrepancy score becomes the authoritative signal for governance intervention.

3. Methodology
3.1 Core Formula

All reconciliations use the same normalized formula:

discrepancy_score = Σ(weight_i × δ_i) / Σ(weight_i)


Where:

δ_i = 0 if field_i matches within tolerance

δ_i = 1 if mismatch

weight_i ∈ [0.1, 1.0] (criticality factor)

weights depend on the agent and field class

all scores ∈ [0.0, 1.0]

This yields a stable, scalable measure that works across:

strategic reasoning (LARS)

technical analysis (STIG)

research (FINN)

infrastructure metrics (LINE)

governance evaluation (VEGA)

4. Field Classes & Criticality Weights
4.1 Critical (1.0)

Mismatch indicates severe hallucination or integrity failure.

Examples:

financial values (portfolio_value, exposure_usd)

risk metrics (var_95, sharpe_ratio)

boolean compliance states

agent identity, signatures, timestamps of execution events

4.2 High (0.8)

Mismatch affects operational accuracy.

Examples:

position counts

order statuses

infrastructure load metrics

4.3 Medium (0.5)

Derived metrics with informational use.

Examples:

indicators, rolling statistics, non-critical analytic features

4.4 Low (0.3)

Metadata with high tolerance.

Examples:

timestamps

API versions

source attribution

Weight definitions are stored and versioned in fhq_meta.reconciliation_field_weights.

5. Tolerance Rules

Reconciliation considers tolerances to prevent false positives.

5.1 Timestamps
match if |agent_ts − canonical_ts| ≤ 5 seconds

5.2 Floats
match if |agent − canonical| / max(|canonical|, ε) ≤ 0.001   # 0.1%


(ε prevents division by zero.)

5.3 Integers

Exact match required.

5.4 Strings

Case- and whitespace-insensitive match.

These tolerance rules are enforced uniformly across all agents.

6. Discrepancy Thresholds
6.1 Classification
Score Range	Status	Action
0.00 – 0.05	NORMAL	Proceed
0.05 – 0.10	WARNING	Log & monitor
> 0.10	CATASTROPHIC	Trigger VEGA suspension request

These thresholds are calibrated from empirical pilot data and Tier-2 risk tolerance.

6.2 Governance Behaviour

NORMAL: VEGA certifies.

WARNING: VEGA logs; no escalation.

CATASTROPHIC: VEGA creates suspension request (ADR-009 workflow).

VEGA never suspends; VEGA only recommends.

7. Canonical State Sources

The reconciler always compares against the system-of-record:

fhq_org.org_agents (agent identity & config)

fhq_org.org_tasks (task state)

fhq_market datasets (financial truth)

external validated data (market feeds, pricing)

last validated reconciliation snapshot

Canonical queries must be deterministic and timestamped.

8. Evidence Bundle Specification

Every reconciliation produces a structured evidence bundle including:

agent_id

reconciliation_type

agent_reported_state (full snapshot)

canonical_state (full snapshot)

field-by-field comparisons

weights applied

tolerances applied

discrepancy score

classification (NORMAL/WARNING/CATASTROPHIC)

cryptographic signatures

timestamp

Stored in:

fhq_meta.reconciliation_snapshots
fhq_meta.reconciliation_evidence


This bundle becomes the foundation for VEGA’s attestation.

9. VEGA Integration

After every reconciliation:

VEGA verifies field comparisons

VEGA validates discrepancy score

VEGA attaches governance signature

VEGA makes classification decision

If discrepancy_score > 0.10, VEGA:

creates suspension request

stores evidence

notifies LARS

returns status: "SUSPENSION_PENDING_APPROVAL"

All per ADR-009.

10. Orchestrator Worker Requirements

The worker must:

run reconciliation after each agent task

reject unsigned or unverifiable agent output

record evidence bundles

load weights from DB, not code

propagate VEGA decision to governance layer

respect suspension status (no execution for suspended agents)

This ensures end-to-end determinism and auditability.

11. Acceptance Criteria

Tier-2 Reconciliation is complete when:

 Discrepancy formula implemented uniformly across agents

 Field weights stored & versioned in DB

 Tolerance rules enforced

 Evidence bundles generated every cycle

 VEGA attestation integrated

 Suspensions flow through ADR-009 workflow

 Worker integrates discrepancy & governance logic

 Full audit trail is append-only and hash-chained

12. Consequences
Positive

Deterministic evaluation of agent truthfulness

Strong anti-hallucination enforcement

Institution-grade lineage

Clear escalation pathways

Forensic-grade reconstruction ability

Negative

Higher CPU & I/O load from evidence generation

Increased storage for reconciliation snapshots

Risks

Misconfigured weights could raise false alarms

Canonical data lag could affect timestamp tolerance

VEGA misconfiguration requires human review

13. Change History
Version	Date	Author	Change
1.0	2025-11-22	LARS	Initial governance specification

ADR-010 is now finalized, audit-ready, and implementation-ready.