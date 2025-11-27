ADR-012_2026_PRODUCTION

Economic Safety Architecture

Status: PRODUCTION
Tier: Tier-3.5 (LIVE Protection Layer)
Authority: LARS – Chief Strategy & Alpha Officer
Owners: LINE (Operations), STIG (Architecture), VEGA (Governance)
Date: 2025-11-22

Constitutional Chain:
ADR-001 System Charter → ADR-002 Audit & Error Reconciliation → ADR-003 Institutional Standards → ADR-004 Change Gates → ADR-007 Orchestrator → ADR-008 Cryptographic Key Management → ADR-011 Production Fortress  → ADR-012 (this ADR)

1. Executive Summary

Activating LIVE LLM mode moves FjordHQ from a closed, deterministic test environment to a state where agents can:

Generate real API charges across multiple LLM providers

Escalate requests in parallel across agents and tasks

Trigger runaway LLM loops and pathological reasoning chains

Inherit and amplify upstream provider instability (latency, errors, throttling)

Degrade governance responsiveness and potentially trigger cascading suspensions

Without explicit economic controls, this violates the constitutional guarantees in ADR-001, the audit and error framework in ADR-002, the orchestrator invariants in ADR-007, and the Production Fortress guarantees in ADR-011.

ADR-012 defines the Economic Safety Architecture – a mandatory protection layer embedded in the Worker pipeline – that:

Enforces deterministic rate limits and cost ceilings

Prevents runaway costs and overuse before they occur

Automatically degrades the system to STUB mode on violation

Logs all violations as VEGA-visible governance events

Preserves ADR-011 Production Fortress guarantees even in LIVE mode

Ensures LLM operations remain predictable, bounded, and auditable across all providers

This ADR is the final prerequisite before any external LLM API keys can be activated in production.

2. Problem Statement

After Tier-3 activation of the WorkerEngine, agents gained the ability to call external LLM providers through the orchestrator. Without guardrails, LIVE mode introduces an unacceptable class of economic drift failure:

Runaway Operating Costs
Parallel agents can generate high-cost calls in minutes, easily breaching daily or monthly budgets.

Rate Limit Breaches
Unregulated bursts cause throttling and bans, collapsing pipelines and breaking deterministic behaviour.

Loss of Budgetary Control
CEO can no longer bound daily or per-strategy LLM spend with confidence.

Provider Instability Propagation
Latency spikes or outages propagate inward as:
– stalled pipelines
– governance timeouts
– false positive discrepancy scores and suspension flows

Governance Bypass via Resource Exhaustion
A single misbehaving or adversarial agent can:
– saturate the Worker pipeline
– delay or block VEGA and LARS
– degrade reconciliation and oversight in exactly the scenarios where governance is most needed

This directly undermines:

ADR-001 – Constitution of FjordHQ (system charter)

ADR-002 – Audit & Error Reconciliation Charter

ADR-007 – Orchestrator behaviour and anti-hallucination controls

ADR-011 – Production Fortress & VEGA Testsuite (proof-based integrity)

Conclusion:
LIVE mode must not be enabled until a deterministic, auditable, and VEGA-governed Economic Safety layer is in place.

3. Decision

FjordHQ adopts a three-layer Economic Safety Architecture, enforced inside the Worker pipeline prior to any external LLM call:

Rate Governance Layer – controls call frequency and volume.

Cost Governance Layer – enforces hard monetary ceilings per agent, task, and day.

Execution Governance Layer – bounds depth, latency, and token volume of reasoning.

All three layers are:

Deterministic – same inputs and state produce the same decision.

Cryptographically attestable under ADR-008 (Ed25519-signed events and hash-chained logs).

Unbypassable – embedded directly into Worker control flow, not in agent prompts.

Audited under ADR-002 – all violations are logged as governance events with full evidence.

Integrated with VEGA attestation – violations influence VEGA’s view of system integrity under ADR-011 and ADR-010.

Reversible only with LARS authority – returning from STUB mode to LIVE mode requires explicit governance action.

This architecture becomes mandatory for all agents and providers once API keys are activated.

4. Architecture Overview
4.1 Rate Governance Layer

Purpose: Prevent rate-driven failure modes (throttling, bans, pipeline storming).

Default limits (per production configuration):

Metric	Default
max_calls_per_agent_per_minute	3
max_calls_per_pipeline_execution	5
global_daily_limit	100

Defaults are constitutional baselines and can be tightened by VEGA or raised by CEO decision via ADR-004 change gates.

Research agents that use lower-cost providers (e.g. DeepSeek) may be granted higher call quotas, but only through canonical configuration updates (no prompt-level overrides).

On violation:

A violation event is written to vega.llm_violation_events.

VEGA issues a WARN or SUSPEND-RECOMMENDATION governance classification (aligned with ADR-010 thresholds).

Worker immediately switches to STUB_MODE for that agent, task, or (if necessary) globally.

A hash-chained governance event is appended under ADR-011’s Production Fortress rules.

4.2 Cost Governance Layer

Purpose: Make LLM spend predictable, capped and provable.

The system tracks estimated and actual cost per provider and call. Per-provider reference envelopes (to be kept in canonical config, not hard-coded):

Provider	Estimated Range (USD per call)
Anthropic Claude	[configured from official pricing – no hard-coding]
OpenAI GPT	[configured from official pricing – no hard-coding]
DeepSeek	$0.001 – $0.005
Gemini	[configured from official pricing – no hard-coding]

Hard ceilings (defaults):

Metric	Default
max_daily_cost	$5.00
max_cost_per_task	$0.50
max_cost_per_agent_per_day	$1.00

On breach:

Worker aborts the call before sending it to the provider.

Worker immediately degrades to STUB_MODE for the relevant scope (task/agent/global).

VEGA emits a governance violation event (Class B or Class A depending on impact) under ADR-002.

LIVE mode remains locked until LARS (or delegated SMF under ADR-003) explicitly reauthorizes via a gated configuration change.

4.3 Execution Governance Layer

Purpose: Bound reasoning depth, latency and token growth, preventing “infinite thought spirals”.

Default execution ceilings:

Configuration	Default
max_llm_steps_per_task	3
max_total_latency_ms	3000 ms
max_total_tokens_generated	provider-specific (canonical config)
abort_on_overrun	True

This layer protects against:

Recursive or cyclic LLM loops

Excessive chain-of-thought expansion that does not change state

Worker performance degradation and queue starvation

Unbounded latency that can distort VEGA’s timing assumptions during reconciliation

Any overrun:

Triggers a controlled abort with deterministic error envelope (per ADR-011 quality gates).

Produces a violation event visible to VEGA and LINE (SRE).

Can be used as input to discrepancy scoring if it leads to output divergence.

5. Data Model (Database Specification)

All Economic Safety tables live under the vega schema, enforcing that governance, not agents, owns economic controls.

New canonical tables:

vega.llm_rate_limits

Per-agent and global rate ceilings.

Key fields: agent_id, provider, max_per_minute, max_per_execution, global_daily_limit, source_adr, created_at.

vega.llm_cost_limits

Per-agent, per-task and global monetary ceilings.

Key fields: agent_id, provider, max_daily_cost, max_cost_per_task, max_cost_per_agent_per_day, currency, source_adr, created_at.

vega.llm_usage_log

Canonical usage ledger for all LLM calls.

Key fields: usage_id, agent_id, task_id, provider, tokens_in, tokens_out, cost_usd, latency_ms, timestamp, mode (LIVE/STUB), signature.

vega.llm_violation_events

Governance log for rate, cost, and execution violations; hash-chained under ADR-011.

Key fields:

violation_id

agent_id

provider

violation_type (RATE, COST, EXECUTION)

governance_action (NONE, WARN, SUSPEND_RECOMMENDATION, SWITCH_TO_STUB)

details (JSONB – full evidence bundle)

discrepancy_score (if relevant; see ADR-010)

hash_prev, hash_self (for hash-chain)

timestamp

All violation events are anchored into the hash-chain and become part of the Production Fortress evidence base.

6. Quality Gates

ADR-012 introduces QG-F6: Economic Safety Gate, extending the Fortress quality gate suite defined in ADR-011.

Gate	Description	Pass Requirement
QG-F6	Economic Safety	No rate, cost, or execution breaches in last 24 hours and all safety tables consistent with configuration hashes

QG-F6 is mandatory before:

Enabling LIVE mode for any provider or agent

Enabling FINN’s autonomous reasoning loops in production

Running any production trading or strategy pipeline that depends on LLM outputs

Enabling DeepSeek live research in FINN or research agents

Failure of QG-F6 automatically:

Locks the system into STUB_MODE for all LLM calls

Flags a Class B or Class A governance event under ADR-002, depending on the severity and impact.

7. Implementation Plan (CODE / STIG / LINE)

This section defines what must be done – not how to write the code – so CODE can implement against the existing architecture on the local Supabase/Postgres instance (127.0.0.1:54322/postgres) as already defined in .env.

Phase 1 – Rate Governance

Owner: STIG (design), CODE (implementation), VEGA (validation)

Retrieve existing rate-limit logic from the current FHQ-IoS / WorkerEngine codebase (Economic Safety / LLM guard modules).

Refactor configuration so that all limits are read from vega.llm_rate_limits instead of hard-coded values.

Ensure Worker pipeline uses the canonical DSN (Supabase instance at 127.0.0.1:54322) for all reads/writes.

Add persistent logging into vega.llm_usage_log for every LLM call – regardless of success or violation.

On violation, insert into vega.llm_violation_events and switch the relevant scope to STUB_MODE.

Phase 2 – Cost Governance

Owner: STIG, CODE, VEGA

Extend WorkerEngine’s LLM binding layer (per ADR-007) to compute estimated cost for every planned call using provider-specific config.

Before dispatch, compare projected cost against vega.llm_cost_limits for:

this task

this agent (today)

global daily cost.

Abort non-compliant calls deterministically and emit violation events with full evidence (usage, limits, config hash).

Ensure all cost data is written into vega.llm_usage_log and can be aggregated for daily/weekly reporting.

Phase 3 – Execution Governance

Owner: CODE, LINE

Implement step-count, latency and token ceilings inside the Worker pipeline.

Ensure abort conditions are deterministic and produce standard error envelopes suitable for Fortress tests.

Log all overruns as EXECUTION violations in vega.llm_violation_events.

Phase 4 – Governance Integration (VEGA / LARS)

Owner: VEGA, LARS

Integrate violation events into VEGA’s reconciliation and discrepancy scoring logic per ADR-010 (e.g. high frequency of violations impacts integrity classification).

Ensure VEGA can classify violations as NORMAL / WARNING / CATASTROPHIC and, for catastrophic cases, issue SUSPEND_RECOMMENDATION to LARS under ADR-009 (dual-approval suspension).

Require explicit LARS approval to re-enable LIVE mode after a lock, recorded as a governance event with hash-chain evidence.

Phase 5 – Test Suite (10–15 Fortress-Grade Tests)

Owner: CODE, VEGA (attestation)

Minimum coverage:

Rate-limit violations at agent level, pipeline level, and global level

Cost breaches per task, per agent, and global

Execution overrun scenarios (steps, latency, tokens)

STUB_MODE fallback and recovery flows

Deterministic error envelopes suitable for ADR-011 Fortress checks

Correct creation, hashing, and linkage of vega.llm_violation_events rows

A successful full run must produce a VEGA-signed attestation under ADR-011 and be stored as Fortress proof.

8. Consequences
Positive

Predictable, bounded operating cost for all LLM usage.

Safe activation of LIVE mode without compromising constitutional guarantees.

Preservation of ADR-011 Production Fortress integrity in real-world operation.

Strong protection against runaway reasoning, loops, and resource exhaustion.

Stable and controlled environment for FINN’s research and strategy evaluation.

Negative

Strict ceilings may throttle some workflows until limits are tuned with empirical data.

Budgets and limits require ongoing governance rather than one-off configuration.

Worker complexity increases due to safety checks and additional logging.

Risks Mitigated

Runaway LLM API costs and unexpected billing events.

Governance bypass via resource exhaustion or starvation.

External provider instability translating into systemic instability.

Unpredictable failure modes from unbounded loops or token usage.

Hidden drift between perceived and actual economic exposure.

9. Status

PRODUCTION

ADR-012 is binding for all future LIVE-mode operations.

QG-F6 Economic Safety Gate is required before any API key activation or production strategy using LLM output.

Any attempt to bypass this architecture constitutes a Class A governance event under ADR-002 and must be escalated immediately to VEGA and CEO.