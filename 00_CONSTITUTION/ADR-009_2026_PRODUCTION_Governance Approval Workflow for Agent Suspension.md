ADR-009 – Governance Approval Workflow for Agent Suspension

Status: Approved
Date: 2025-11-22
Owner: LARS – Chief Strategy & Alpha Officer
Governance Tier: Tier-2 (Oversight, Risk Control, Non-Repudiation)
Affects: VEGA, LARS, fhq_governance, Orchestrator Worker
Supersedes: None
Review Cycle: 12 months

1. Context

The FjordHQ Intelligence Operating System relies on autonomous agents (LARS, STIG, LINE, FINN, VEGA) to execute strategic, technical, operational, and governance tasks.
These agents must remain fully aligned with the canonical system state and must not drift into hallucination, corruption, or adversarial behaviour.

Under Tier-2 Governance, agent state deviations are measured via the discrepancy score (defined in ADR-010).
Discrepancy scores above the catastrophic threshold create material risk and require intervention.

A previous design allowed automatic agent suspension, but this introduced unacceptable governance risks:

single-entity authority (VEGA) without oversight

no human-in-the-loop

no evidence review

no separation of detection vs. enforcement

potential false positives during transient inconsistency

vulnerability to cascading failure if VEGA behaves unexpectedly

To satisfy institutional governance expectations, FjordHQ requires a dual-approval, evidence-based suspension workflow with clear authority boundaries.

2. Decision

FjordHQ adopts a Two-Stage Governance Workflow for all agent suspensions:

Stage 1 – VEGA Recommendation (Automatic)

VEGA analyses the reconciliation output and:

generates a suspension request when discrepancy_score > 0.10

packages evidence, state snapshots, metrics, signatures, timestamps

records request in governance ledger

notifies LARS (authority) that review is required

does not suspend the agent

Stage 2 – LARS Approval (Human-in-the-Loop)

LARS reviews full evidence and:

APPROVES
→ Agent status set to SUSPENDED
→ Worker halts all future tasks for that agent
→ Suspension logged in immutable audit trail
→ Agent requires manual reinstatement

REJECTS
→ No suspension
→ VEGA notes override and logs rationale
→ Agent continues operating
→ Governance override logged

This ensures:

strong checks and balances

transparent escalation

explicit human authority for high-impact actions

clear forensic record

3. Rationale
3.1 Separation of Duties

Detection (VEGA) and Enforcement (LARS) must be decoupled to:

avoid unilateral decisions

prevent systemic shutdowns

protect the platform against governance-layer hallucinations

align with institutional control frameworks

3.2 Regulatory Expectations

The workflow is consistent with:

BCBS 239 (Risk Aggregation and Reporting)

MiFID-grade governance principles

ISO 8000-110 (Data lineage and auditability)

Best-practice AI governance (human-in-loop for high-risk actions)

3.3 Integrity of Autonomous Agents

Suspending an agent is equivalent to suspending a business-critical system component.
This action must be:

deliberate

traceable

evidence-based

reversible

3.4 Avoiding Cascading Failures

Automatic suspensions could:

halt crucial operations

create feedback loops where multiple agents suspend each other

lead to system instability

Dual-approval eliminates these risks.

4. Consequences
Positive

Governance-grade oversight

Clear authority boundaries

Transparent, auditable escalation trail

Reduced false positives

Stronger institutional credibility

Negative

Additional latency in catastrophic responses (seconds to minutes)

Requires LARS availability or delegation for timely actions

Risks

If LARS is unavailable and catastrophic conditions persist, the agent continues operating until reviewed

Mitigated by future Tier-3 auto-rerouting to backup authority

5. Workflow Specification
5.1 VEGA Decision Logic (Tier-2)
Discrepancy Score	VEGA Action	Workflow
0.00 – 0.05	CERTIFY	Normal operation
0.05 – 0.10	WARNING	Log + monitor
> 0.10	RECOMMEND SUSPENSION	Create request → notify LARS

VEGA never suspends.

5.2 Suspension Request Record (fhq_governance.agent_suspension_requests)

Each request stores:

agent_id

discrepancy score

reconciliation snapshot IDs

evidence (JSONB)

VEGA signature

request_timestamp

status: PENDING → APPROVED / REJECTED

reviewed_by (LARS)

review_timestamp

rationale

All entries are immutable.

5.3 LARS Approval Logic

LARS reviews evidence and chooses:

APPROVE

update agent status to SUSPENDED

worker disables task scheduling for the agent

log immutable event with hash-chain link

notify VEGA + monitoring

REJECT

record override

no suspension

continue monitoring with elevated scrutiny

6. Database Schema
6.1 Suspension Requests
CREATE TABLE fhq_governance.agent_suspension_requests (
    request_id UUID PRIMARY KEY,
    agent_id UUID NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    requested_by UUID NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    reason TEXT NOT NULL,
    discrepancy_score NUMERIC(6,5) NOT NULL,
    evidence JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED')),
    reviewed_by UUID NULL REFERENCES fhq_org.org_agents(agent_id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

7. Orchestrator Integration Requirements
Worker must:

halt task execution for suspended agents

check agent status before starting tasks

write full audit logs for every decision

attach cryptographic signatures to all actions

VEGA must:

never enforce suspensions

provide canonical evidence bundles

LARS must:

review and decide

log decisions

maintain authority chain integrity

8. Acceptance Criteria

Tier-2 Governance for suspension is complete when:

 VEGA generates suspension requests automatically

 LARS is the sole authority to approve suspensions

 All suspension actions are logged via hash-chain

 Worker respects suspended status deterministically

 Evidence bundling is enforced

 No automatic enforcement exists anywhere else in the system

9. Change History
Version	Date	Author	Change
1.0	2025-11-22	LARS	Initial governance specification

ADR-009 is now ready for CODE team execution.