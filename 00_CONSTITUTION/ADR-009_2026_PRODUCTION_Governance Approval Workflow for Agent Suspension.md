ADR-009_2026_PRODUCTION

Governance Approval Workflow for Agent Suspension

Status: APPROVED
Version: 2026.PRODUCTION
Author / Owner: LARS – Chief Strategy & Alpha Officer
Date: 2025-11-22
Governance Tier: Tier-2 (Oversight, Risk Control, Non-Repudiation)
Supersedes: None
Affects: VEGA, LARS, CEO, fhq_governance, Orchestrator Worker
Review Cycle: 12 months
Constitutional Authority: ADR-001 → ADR-002 → ADR-006 → ADR-007 → ADR-008 → EC-001
Environment: Supabase PostgreSQL – Local Production (127.0.0.1:54322 / postgres)

1. Context

The FjordHQ Intelligence Operating System relies on autonomous agents (LARS, STIG, LINE, FINN, VEGA) to execute strategic, technical, operational and governance tasks. These agents must remain aligned with canonical system state and must not drift into hallucination, corruption or adversarial behaviour.

Under Tier-2 Governance, agent state deviations are measured via the discrepancy score as defined in ADR-010. Discrepancy scores above a catastrophic threshold introduce material risk and require intervention.

A previous design allowed automatic agent suspension, which introduced unacceptable governance risks:

single-entity authority (VEGA) without oversight

no human-in-the-loop

no formal evidence review

no structural separation between detection and enforcement

potential false positives during transient inconsistencies

vulnerability to cascading failure if VEGA misbehaves

To meet institutional governance expectations, FjordHQ requires a dual-approval, evidence-based suspension workflow with clear authority boundaries.

2. Decision

FjordHQ adopts a Two-Stage Governance Workflow for all agent suspensions.

2.1 Stage 1 – VEGA Recommendation (Automatic)

VEGA:

monitors discrepancy scores and reconciliation outputs

generates a suspension request when discrepancy_score > 0.10

packages evidence, including state snapshots, metrics, signatures and timestamps

records the request in the governance ledger

notifies LARS and CEO that review is required

does not suspend the agent

VEGA is limited to recommendation only. It has no authority to enforce suspension.

2.2 Stage 2 – CEO Approval

The CEO reviews the full evidence bundle and decides:

APPROVE

agent status is set to SUSPENDED

Orchestrator Worker halts all future tasks for the agent

suspension is written to immutable audit trail

reinstatement requires explicit manual action

REJECT

no suspension

VEGA records that an override occurred and logs rationale

agent continues operating under elevated monitoring

governance override is logged

This ensures checks and balances, transparent escalation and explicit human authority for high-impact actions.

3. Rationale
3.1 Separation of Duties

Detection (VEGA) and enforcement (CEO) must be decoupled in order to:

avoid unilateral decisions

prevent systemic shutdowns

protect against governance-layer hallucinations

align with institutional control frameworks

3.2 Regulatory Expectations

The workflow is consistent with:

BCBS 239 (Risk Aggregation and Reporting)

MiFID-grade governance principles

ISO 8000-110 (Data lineage and auditability)

Best-practice AI governance (human-in-loop for high-risk actions)

3.3 Integrity of Autonomous Agents

Suspending an agent is equivalent to suspending a business-critical system component. Such actions must be:

deliberate

traceable

evidence-based

reversible

3.4 Avoiding Cascading Failures

Automatic suspensions can:

halt critical operations

create feedback loops where agents suspend each other

destabilise the overall system

Dual approval eliminates these risks by inserting a human control point.

4. Consequences
4.1 Positive

Governance-grade oversight of autonomous agents

Clear authority boundaries between VEGA, LARS, CEO and Worker

Transparent, auditable escalation trail

Reduced false positive suspensions

Stronger institutional and regulatory credibility

4.2 Negative

Additional latency in catastrophic responses (seconds to minutes)

Requires CEO availability or delegated authority for timely decisions

4.3 Risks

If the CEO is unavailable and catastrophic conditions persist, the agent continues operating until reviewed.

Mitigation:

notification from FjordHQ Market System to CEO or delegate must be implemented alongside ADR-009

future Tier-3 configuration may allow controlled auto-rerouting to an approved backup authority

5. Workflow Specification
5.1 VEGA Decision Logic (Tier-2)
Discrepancy Score	VEGA Action	Workflow
0.00 – 0.05	CERTIFY	Normal operation
0.05 – 0.10	WARNING	Log and monitor
> 0.10	RECOMMEND SUSPENSION	Create request and notify LARS/CEO

VEGA never enforces suspension.

5.2 Suspension Request Record

Table: fhq_governance.agent_suspension_requests

Each request stores:

agent_id

discrepancy score at detection time

reconciliation snapshot IDs

evidence (JSONB)

VEGA signature

request_timestamp

status: PENDING → APPROVED / REJECTED

reviewed_by (CEO or delegate)

review_timestamp

rationale

All entries are immutable at business-logic level.

5.3 CEO Approval Logic

The CEO (or formally delegated authority):

reviews the evidence bundle and context

chooses APPROVE or REJECT

On APPROVE:

agent status set to SUSPENDED

Orchestrator Worker disables task scheduling for that agent

immutable audit entry with hash-linked evidence is written

VEGA and monitoring are notified

On REJECT:

override is recorded with rationale

no suspension is applied

monitoring continues under elevated scrutiny

6. Database Schema
6.1 fhq_governance.agent_suspension_requests

Canonical schema:

CREATE TABLE fhq_governance.agent_suspension_requests (
    request_id        UUID PRIMARY KEY,
    agent_id          UUID NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    requested_by      UUID NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    reason            TEXT NOT NULL,
    discrepancy_score NUMERIC(6,5) NOT NULL,
    evidence          JSONB NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED')),
    reviewed_by       UUID NULL REFERENCES fhq_org.org_agents(agent_id),
    reviewed_at       TIMESTAMP,
    created_at        TIMESTAMP DEFAULT NOW()
);


requested_by will normally be VEGA’s agent_id for automatic recommendations.

7. Orchestrator Integration Requirements

Worker must:

check agent status before starting any task

halt task execution for agents marked SUSPENDED

write full audit logs for each decision regarding suspension

attach cryptographic signatures to all relevant actions

VEGA must:

never directly enforce suspension

generate canonical evidence bundles for suspension requests

log all recommendations to fhq_governance.agent_suspension_requests

CEO must:

review requests and decide APPROVE/REJECT

ensure that decisions are recorded

maintain integrity of the authority chain defined in ADR-001, ADR-002 and ADR-006

8. Acceptance Criteria

Tier-2 Governance for agent suspension is complete when:

VEGA generates suspension requests automatically according to ADR-010 discrepancy scores

CEO is the sole authority for changing agent status to SUSPENDED

all suspension actions and decisions are logged with hash-linked evidence

Worker deterministically respects suspended status for all agents

evidence bundling is enforced for every request

no automatic enforcement of suspension exists anywhere in the system

9. Change History
Version	Date	Author	Change
1.0	2025-11-22	LARS	Initial governance specification

ADR-009 is hereby approved as the authoritative governance standard for agent suspension under Tier-2.