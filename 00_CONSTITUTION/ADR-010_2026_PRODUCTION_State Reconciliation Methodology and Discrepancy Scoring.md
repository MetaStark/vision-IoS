ADR-010 – State Reconciliation Methodology & Discrepancy Scoring

Version: 2026.PRODUCTION
Status: APPROVED
Date: 2025-11-22
Owner: LARS – Chief Strategy & Alpha Officer
Governance Tier: Tier-2 (Validation, Integrity, Anti-Hallucination)
Authority Chain: ADR-001 → ADR-002 → ADR-006 → ADR-007 → ADR-008 → ADR-009 → ADR-010 → EC-001
Affects: VEGA, Worker, Reconciliation Service, fhq_meta, fhq_governance
Supersedes: None
Review Cycle: 12 months

1. Purpose & Context

Autonomous agents in FjordHQ-IoS generate analytical state, decisions, metrics and strategic assessments.
These outputs must be validated against canonical system-of-record data to detect:

hallucination or fabricated reasoning

drift from validated market data

stale or cached state

implementation divergence

tampering or corruption

misalignment with governance truth

Before ADR-010, there was no deterministic or reproducible method to measure deviations.
This ADR establishes the only allowed mathematical methodology for reconciliation in FjordHQ.

2. Decision

FHQ-IoS adopts a single unified weighted discrepancy scoring model, applied after every agent task, with the following characteristics:

Field-level binary match / mismatch (δᵢ)

Criticality-weighted scoring

Tolerance layer for timestamps, floats, metadata

Three-tier discrepancy classification

Canonical evidence bundle generation

Automatic VEGA validation and signing

Suspension routed through ADR-009 dual-approval workflow

The discrepancy score becomes the authoritative governance signal.

3. Methodology
3.1 Canonical Formula
discrepancy_score = Σ(weight_i × δ_i) / Σ(weight_i)


Where:

δᵢ = 0 → match within tolerance

δᵢ = 1 → mismatch

weights ∈ [0.1, 1.0]

score ∈ [0.0, 1.0]

This method must be identical across:

LARS (strategy)

STIG (implementation)

LINE (infrastructure)

FINN (research)

VEGA (governance)

4. Field Classes & Weights

Critical (1.0)
financial values, risk metrics, agent identity, signatures, governance booleans.

High (0.8)
order states, infrastructure metrics, position counts.

Medium (0.5)
non-critical derived metrics, rolling analytics.

Low (0.3)
metadata, timestamps, API versions.

Stored in:
fhq_meta.reconciliation_field_weights

5. Tolerance Rules

Timestamps: match if |agent_ts − canonical_ts| ≤ 5s

Floats: relative deviation ≤ 0.1%

Integers: exact match

Strings: case/whitespace-insensitive

Tolerances must be uniformly enforced for all agents.

6. Thresholds & Governance Actions
Score	Status	Outcome
0.00–0.05	NORMAL	VEGA certifies
0.05–0.10	WARNING	Log & monitor
>0.10	CATASTROPHIC	VEGA submits suspension request (ADR-009)

VEGA never suspends. Only CEO approves.

7. Canonical State Sources

Comparisons must always reference deterministic, timestamped canonical data:

fhq_org.org_agents

fhq_org.org_tasks

validated market/pricing data

last reconciliation snapshot

8. Evidence Bundle Specification

Each reconciliation produces:

agent_id

reconciliation_type

agent_reported_state

canonical_state

field-by-field diffs

weights

tolerances

discrepancy score

classification

signatures

timestamp

Stored in:

fhq_meta.reconciliation_snapshots

fhq_meta.reconciliation_evidence

This evidence is mandatory for VEGA signing.

9. VEGA Integration

VEGA must:

verify discrepancy score

confirm all tolerances

apply governance signature

classify score

generate suspension requests if >0.10

notify LARS

register outcome in governance log

All per ADR-009.

10. Worker Requirements

Worker must:

execute reconciliation after each agent task

reject unsigned output

generate evidence bundle

load weights from DB (never from code)

honor suspension state (no execution when suspended)

propagate VEGA decisions to governance layer

11. Acceptance Criteria

Tier-2 reconciliation is considered complete when:

discrepancy formula implemented identically for all agents

field weights versioned in DB

all tolerance rules active

evidence bundle generated every cycle

VEGA signature applied

ADR-009 workflow triggered deterministically

worker enforces discrepancy logic and suspension boundaries

audit trail is immutable and hash-chained

12. Consequences
Positive

deterministic truth-validation

system-wide anti-hallucination

institutional‐grade auditability

complete forensic reconstruction

predictable governance escalation

Negative

CPU/I/O cost increase

storage overhead from snapshots

Risks

misconfigured weights

lagging canonical data

VEGA misalignment requiring human review

13. Change History
Version	Date	Author	Change
1.0	2025-11-22	LARS	Initial governance specification