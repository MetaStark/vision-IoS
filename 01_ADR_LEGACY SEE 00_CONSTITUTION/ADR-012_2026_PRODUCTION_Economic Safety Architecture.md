ADR-012_2026_PRODUCTION_Economic Safety Architecture

Status: PRODUCTION
Tier: Tier-3.5 (Pre-LIVE Protection Layer)
Authority: LARS – Chief Strategy & Alpha Officer
Owners: LINE (Operations), STIG (Architecture), VEGA (Governance)
Date: 2025-11-22

1. Executive Summary

The activation of LIVE LLM mode introduces a high-risk category of operational exposure:
economic drift failure.

Once external LLM calls are enabled, the system can:

generate real API charges

escalate costs in parallel across agents

trigger runaway LLM call loops

propagate provider instability (latency spikes, outages)

degrade governance response under load

cause unintended suspension cascades

ADR-012 establishes the Economic Safety Architecture, a mandatory protection layer that:

enforces deterministic API rate and cost ceilings

prevents runaway charges before they occur

automatically degrades to STUB mode on violation

logs all violations as governance events

preserves ADR-011 Production Fortress guarantees in LIVE mode

ensures predictable, controllable LLM operations across all providers

This is the final prerequisite before API keys may be activated.

2. Problem Statement

Following Tier-3 Activation, the WorkerEngine gained the ability to perform external LLM calls.
Without economic controls, LIVE mode creates unacceptable institutional risk:

2.1 Runaway Operating Costs

Parallel agents can generate expensive calls in minutes, exceeding daily budgets.

2.2 Rate Limit Breaches

Unregulated bursts → throttling → bans → pipeline collapse.

2.3 Loss of Budgetary Control

CEO cannot guarantee or bound daily system costs.

2.4 Propagation of Provider Instability

Provider downtime or latency spikes cause:

pipeline stalls

governance timeouts

false-positive suspension flows

2.5 Governance Bypass via Resource Exhaustion

A single overactive agent may:

saturate the Worker pipeline

block VEGA and LARS

cause governance delays or misclassification

This violates:

ADR-001 Constitution of FjordHQ

ADR-002 Change Control Architecture

ADR-007 Agent–LLM Binding

ADR-011 Production Fortress Integrity

Therefore, LIVE mode cannot be enabled without a deterministic, auditable economic safety layer.

3. Decision

FjordHQ adopts a three-layer Economic Safety Architecture, enforced within the Worker pipeline before any external LLM call:

Rate Governance Layer

Cost Governance Layer

Execution Governance Layer

All safety layers are:

deterministic

cryptographically attestable (ADR-008)

unbypassable (Worker pipeline enforcement)

audited under ADR-002

integrated with VEGA attestation logic

reversible only with LARS approval

This framework guarantees safe, predictable, bounded operation of LIVE LLM mode.

4. Architecture Overview
4.1 Rate Governance Layer

Controls LLM call frequency across multiple dimensions:

Metric	Default
max_calls_per_agent_per_minute	3
max_calls_per_pipeline_execution	5
global_daily_limit	100

On violation:

violation recorded in vega.llm_violation_events

VEGA issues WARN or SUSPEND recommendation

Worker switches to STUB_MODE immediately

hash-chain event appended (ADR-011)

4.2 Cost Governance Layer

Tracks estimated and actual cost per provider.

Estimated cost envelopes:

Provider	Estimated Range
Anthropic Claude	$0.004–$0.08 per call
OpenAI GPT	$0.002–$0.04 per call
DeepSeek	$0.001–$0.005 per call

Hard ceilings:

Metric	Default
max_daily_cost	$5.00
max_cost_per_task	$0.50
max_cost_per_agent_per_day	$1.00

On breach:

Worker aborts the call

System degrades to STUB_MODE

VEGA issues governance violation event

LIVE mode locked until LARS explicitly reactivates

4.3 Execution Governance Layer

Prevents runaway reasoning and compute overload:

Configuration	Default
max_llm_steps_per_task	3
max_total_latency_ms	3000ms
max_total_tokens_generated	provider-specific
abort_on_overrun	True

Protects against:

recursive LLM loops

excessive chain-of-thought expansion

degraded Worker performance

unbounded latency accumulation

5. Data Model (Database Specification)

New tables under the vega schema:

vega.llm_rate_limits

vega.llm_cost_limits

vega.llm_usage_log

vega.llm_violation_events

Key fields include:

agent_id

provider

tokens_in

tokens_out

cost_usd

timestamp

violation_type

governance_action (NONE, WARN, SUSPEND, SWITCH_TO_STUB)

All violation events are anchored into the hash-chain per ADR-011.

6. Quality Gates

ADR-012 introduces:

QG-F6: Economic Safety Gate
Gate	Description	Pass Requirement
QG-F6	Economic Safety	No rate, cost, or execution breaches in the last 24 hours

QG-F6 is mandatory before:

enabling LIVE mode

enabling FINN reasoning loops

running any production strategy

enabling DeepSeek live research

7. Implementation Plan
Phase 1 — Rate Governance

Rate limit enforcement and persistent logging.

Phase 2 — Cost Governance

Cost estimation, ceiling enforcement, daily aggregation.

Phase 3 — Execution Governance

Execution ceilings, latency control, abort logic.

Phase 4 — Governance Integration

VEGA attestation

LARS approval flows

hash-chain event creation

Phase 5 — Test Suite (10–15 tests)

Covers:

rate-limit violations

cost-breach behavior

pipeline abort logic

STUB fallback transitions

deterministic error envelopes

governance event creation

8. Consequences
Positive

Predictable, bounded operating cost

Safe activation of LIVE mode

Preservation of ADR-011 governance guarantees

Protection against runaway reasoning

Stable research environment for FINN

Negative

Strict ceilings may throttle workflows

Budgets may require manual tuning

Slightly increased Worker complexity

Risks Mitigated

runaway LLM API costs

governance bypass

external provider instability

unpredictable failure modes

unbounded token generation

9. Status

PRODUCTION
All future LIVE-mode operations must comply with ADR-012.
QG-F6 is required before API key activation.