Dashboard LLM Interface — Context Hydration Layer (CHL) Workflow Specification

Canonical Version: 2026.DRAFT.1
Owner: Dashboard Team (Interface), STIG (Technical Authority), VEGA (Governance Oversight)
Purpose: Define exactly how canonical system context and user prompts are combined and delivered to any LLM advisor, without drift, override or ambiguity.
Scope: All LLM calls originating from FjordHQ dashboards.

1. Mission of CHL

The Context Hydration Layer (CHL) ensures that every LLM request from the dashboard is fully saturated with canonical system truth before any user input is considered.

CHL guarantees:

System truth is always applied first

User prompt is always applied second

LLM can never override or ignore the context_package

All calls are consistent, auditable and role-aligned

It is the delivery glue between IoS-013 Truth Gateway and the LLM.

2. Position in the Architecture

Runtime chain:

IoS-013 (ASPE + CDS)
      ↓
Truth Gateway (Interface)
      ↓
CHL (Dashboard Middleware)
      ↓
LLM Advisor (via LLM API)
      ↓
Response → Dashboard UI


IoS-013: produces and validates context

Truth Gateway: returns atomic, signed truth_payload

CHL: merges truth_payload + user prompt into one governed LLM request

3. CHL Workflow – Exact Sequence

For every LLM call from the dashboard, CHL must follow this sequence:

Receive user_intent from UI (raw text + selected advisor role).

Call IoS-013 Truth Gateway to obtain truth_payload:

context_package

context_hash

issued_at

integrity_signature

Validate that truth_payload is present and marked valid.

Construct LLM SYSTEM CONTEXT from context_package + role + constraints:

state_vector

adr_index

ios_index

authority_map

operational_constraints

llm_role

constitutional prohibitions

Attach user prompt as separate, lower-priority content.

Send full request to LLM API.

Bind returned output to:

state_snapshot_hash

context_hash

quad_hash (if applicable)
and log that binding.

No step may be skipped.
No parallel path is allowed.

4. Separation of System Context vs User Prompt

CHL must enforce a hard separation between:

SYSTEM_CONTEXT (immutable, from IoS-013)

USER_PROMPT (mutable, from dashboard user)

Rules:

SYSTEM_CONTEXT is injected at system-level / high priority.

USER_PROMPT is injected at dialogue-level / normal priority.

USER_PROMPT can never override or negate SYSTEM_CONTEXT.

CHL must not modify or filter the context_package.

CHL is a conduit, not an editor, for system truth.

5. Governance Constraints Enforced by CHL

CHL must ensure the following before sending any LLM request:

A valid truth_payload has been obtained from IoS-013.

state_snapshot_hash is present and non-stale (ADR-018).

llm_role is defined and consistent with authority_map.

Operational constraints (LIDS threshold, DEFCON, RISL) are embedded.

No user-supplied text is placed before system context.

If any of these fail → the call is not sent.

6. Fail-Closed Behavior

If CHL detects:

missing or invalid truth_payload

failed validations from Truth Gateway

inconsistent role vs authority_map

internal errors assembling SYSTEM_CONTEXT

Then CHL must:

Abort the LLM call.

Return an error to the dashboard (e.g. “System context unavailable – reasoning blocked”).

Raise a governance event for VEGA (for monitoring/triage).

No fallback to:

cached context

partial context

hardcoded defaults

“best effort” prompts

If context fails, the safest answer is no answer.

7. Logging & Audit

CHL must log, for each LLM call:

agent_id / advisor_id

llm_role

reference to truth_payload (hash / id)

timestamp

whether call was SENT or BLOCKED

state_snapshot_hash + context_hash + (if relevant) quad_hash

LLM output must be stored with a pointer back to:

the exact state that governed it

the exact context_hash that hydrated it

This completes the Context → Reasoning → Output chain.

8. Responsibilities

Dashboard Team

Implement CHL workflow exactly as specified.

Ensure all LLM calls pass through CHL – no bypass.

STIG

Guarantee IoS-013 Truth Gateway contract is stable and documented.

Provide schema and test fixtures for CHL implementers.

VEGA

Monitor CHL logs.

Flag any LLM request that did not pass through CHL.

Treat any bypass as a governance violation under ADR-018.

9. Success Criteria

CHL is successful when:

Every advisor-LLM sees the same system reality.

No LLM request leaves the dashboard without valid system context.

No reasoning occurs if IoS-013 is unavailable or fails validation.

All outputs can be tied back to a specific state and context_hash.

You can switch between advisors in dashboardet og få identisk fakta om systemet – uansett tidligere samtaler.