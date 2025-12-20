# LLM Router Blueprint v1

**Document ID:** ARCH-LLM-ROUTER-v1
**Status:** DESIGN-ONLY (No Implementation Permitted)
**Authority:** CEO Directive - PHASE 2
**Compliance:** ADR-001, ADR-012, ADR-018, ADR-019, ADR-020, ADR-021
**Author:** STIG (CTO)
**Date:** 2025-12-10

---

## 1. Executive Summary

This blueprint defines the architecture for a centralized LLM Router that all FjordHQ LLM calls must pass through. The router enforces economic discipline, governance compliance, cognitive attribution, and fail-closed semantics.

**Core Principle:**
> "Better no LLM call than an untracked LLM call."

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AGENT CODE                                    │
│  (FINN, CRIO, LARS, LINE, STIG, VEGA, CEIO, CDMO, etc.)                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    @metered_execution DECORATOR                         │
│  - Extracts context                                                     │
│  - Initiates telemetry envelope                                         │
│  - Wraps LLM call                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LLM ROUTER CORE                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    PRE-CALL VALIDATION                          │   │
│  │  1. Budget Check (ADR-012)                                      │   │
│  │  2. ASRP State Check (ADR-018)                                  │   │
│  │  3. DEFCON Level Check (ADR-016)                                │   │
│  │  4. Governance Context Hydration (IoS-013)                      │   │
│  │  5. IKEA Boundary Check (EC-022)                                │   │
│  │  6. InForage Value Check (EC-021)                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│              ┌───────────────┴───────────────┐                          │
│              │         GATE DECISION         │                          │
│              │   PASS ──────────► PROCEED    │                          │
│              │   FAIL ──────────► BLOCK      │                          │
│              └───────────────────────────────┘                          │
│                              │                                          │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    PROVIDER DISPATCH                            │   │
│  │  - Select provider (DEEPSEEK, ANTHROPIC, OPENAI, GEMINI)       │   │
│  │  - Apply streaming/non-streaming                                │   │
│  │  - Start latency timer                                          │   │
│  │  - Execute HTTP call                                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    RESPONSE PROCESSOR                           │   │
│  │  - Stop latency timer                                           │   │
│  │  - Extract token counts                                         │   │
│  │  - Calculate cost                                               │   │
│  │  - Handle streaming aggregation                                 │   │
│  │  - Capture errors                                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    TELEMETRY WRITER                             │   │
│  │  - Complete envelope                                            │   │
│  │  - Write to all targets                                         │   │
│  │  - Hash-chain linkage                                           │   │
│  │  - FAIL-CLOSED on write error                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          [LLM Response to Agent]
```

---

## 3. Router Responsibilities

### 3.1 ADR-012 Economic Enforcement

```
RESPONSIBILITY: Enforce economic ceilings and budget discipline

CHECKS:
  - Daily budget per provider
  - Hourly rate limits
  - Per-task cost ceiling
  - Per-agent allocation
  - Global system ceiling

ACTIONS:
  - BLOCK if budget exceeded
  - WARN at 90% threshold
  - LOG all budget state changes
  - INCREMENT budget counters post-call

WRITE TARGET: fhq_governance.api_budget_log
```

### 3.2 ADR-018 State Reliability Enforcement

```
RESPONSIBILITY: Ensure ASRP state permits LLM operations

CHECKS:
  - Current ASRP state for calling agent
  - Propagation block status
  - State hash consistency

ACTIONS:
  - BLOCK if ASRP state = SUSPENDED
  - BLOCK if propagation blocked
  - LOG state at call time

WRITE TARGET: fhq_governance.asrp_state_log
```

### 3.3 ADR-019 Application Layer Isolation

```
RESPONSIBILITY: Enforce layer boundaries

CHECKS:
  - Calling agent's tier (Tier-1, Tier-2, Tier-3)
  - Provider authorization per tier
  - Cross-layer communication rules

ACTIONS:
  - BLOCK unauthorized provider access
  - ENFORCE tier-appropriate models
```

### 3.4 ADR-021 Cognitive Context Attachment

```
RESPONSIBILITY: Link LLM calls to cognitive reasoning chains

ATTACH:
  - cognitive_parent_id (if part of reasoning chain)
  - protocol_ref (if part of research protocol)
  - cognitive_modality (classification)

INTEGRATION:
  - SitC provides protocol_ref for Chain-of-Query
  - InForage provides value/cost assessment
  - IKEA provides boundary classification

WRITE TARGET: fhq_cognition.lineage_log
```

### 3.5 Token Accounting & Cost Calculation

```
RESPONSIBILITY: Accurate token and cost tracking

CAPTURE:
  - tokens_in (prompt tokens)
  - tokens_out (completion tokens)
  - reasoning_tokens (for deepseek-reasoner)

CALCULATE:
  cost_usd = (tokens_in / 1000 * input_rate)
           + (tokens_out / 1000 * output_rate)

STREAMING AGGREGATION:
  - Accumulate chunks
  - Sum token counts across chunks
  - Record TTFT (time to first token)

WRITE TARGET: fhq_governance.telemetry_cost_ledger
```

### 3.6 Latency Tracking

```
RESPONSIBILITY: Measure end-to-end call latency

TIMING POINTS:
  - T0: Pre-validation start
  - T1: HTTP request sent
  - T2: First byte received (streaming TTFT)
  - T3: Last byte received
  - T4: Post-processing complete

METRICS:
  - latency_ms = T3 - T1 (provider time)
  - total_latency_ms = T4 - T0 (full pipeline)
  - ttft_ms = T2 - T1 (time to first token)

WRITE TARGET: fhq_governance.llm_routing_log
```

---

## 4. Routing Logic (Pseudocode)

```python
class LLMRouter:
    """
    DESIGN ONLY - NOT IMPLEMENTED
    Centralized LLM routing with fail-closed semantics
    """

    def route(self, request: LLMRequest) -> LLMResponse:
        # ═══════════════════════════════════════════════════════════
        # PHASE 1: PRE-CALL VALIDATION
        # ═══════════════════════════════════════════════════════════

        envelope = TelemetryEnvelope.create(request)

        # 1. Budget Check (ADR-012)
        budget_status = self.check_budget(
            provider=request.provider,
            agent_id=request.agent_id,
            estimated_cost=request.estimated_cost
        )
        if budget_status.exceeded:
            return self.block_with_error(
                envelope,
                BudgetExceededError(budget_status)
            )

        # 2. ASRP State Check (ADR-018)
        asrp_state = self.get_asrp_state(request.agent_id)
        if asrp_state.blocked:
            return self.block_with_error(
                envelope,
                GovernanceBlockError(asrp_state)
            )

        # 3. DEFCON Check (ADR-016)
        defcon = self.get_defcon_level()
        if defcon.blocks_llm_calls:
            return self.block_with_error(
                envelope,
                GovernanceBlockError(defcon)
            )

        # 4. Governance Context Hydration (IoS-013)
        gov_context = self.hydrate_governance_context(request)
        if gov_context.hydration_failed:
            # FAIL-CLOSED: Cannot proceed without governance context
            return self.block_with_error(
                envelope,
                GovernanceHydrationError(gov_context)
            )
        envelope.governance_context_hash = gov_context.hash

        # 5. IKEA Boundary Check (EC-022)
        ikea_verdict = self.check_knowledge_boundary(request)
        if ikea_verdict.should_block:
            return self.block_with_error(
                envelope,
                IKEABoundaryViolation(ikea_verdict)
            )

        # 6. InForage Value Check (EC-021)
        inforage_verdict = self.check_information_value(request)
        if inforage_verdict.expected_value < inforage_verdict.cost:
            return self.block_with_error(
                envelope,
                DiminishingReturnsTermination(inforage_verdict)
            )

        # ═══════════════════════════════════════════════════════════
        # PHASE 2: PROVIDER DISPATCH
        # ═══════════════════════════════════════════════════════════

        start_time = time.monotonic()

        try:
            if request.stream_mode:
                response = self.dispatch_streaming(request)
                envelope.stream_mode = True
                envelope.stream_chunks = response.chunk_count
                envelope.stream_token_accumulator = response.total_tokens
            else:
                response = self.dispatch_standard(request)

        except TimeoutError as e:
            return self.handle_error(envelope, TimeoutError(e))
        except ProviderError as e:
            return self.handle_error(envelope, ProviderError(e))

        # ═══════════════════════════════════════════════════════════
        # PHASE 3: RESPONSE PROCESSING
        # ═══════════════════════════════════════════════════════════

        end_time = time.monotonic()

        envelope.latency_ms = int((end_time - start_time) * 1000)
        envelope.tokens_in = response.usage.prompt_tokens
        envelope.tokens_out = response.usage.completion_tokens
        envelope.cost_usd = self.calculate_cost(
            provider=request.provider,
            model=request.model,
            tokens_in=envelope.tokens_in,
            tokens_out=envelope.tokens_out
        )

        # ═══════════════════════════════════════════════════════════
        # PHASE 4: TELEMETRY WRITE (FAIL-CLOSED)
        # ═══════════════════════════════════════════════════════════

        write_success = self.write_telemetry(envelope)

        if not write_success:
            # FAIL-CLOSED: If we can't track it, we can't return it
            # This is the critical fail-closed semantic
            raise TelemetryWriteFailure(
                "LLM response received but telemetry write failed. "
                "Response discarded per FAIL-CLOSED policy."
            )

        # ═══════════════════════════════════════════════════════════
        # PHASE 5: RETURN
        # ═══════════════════════════════════════════════════════════

        return LLMResponse(
            content=response.content,
            envelope_id=envelope.envelope_id,
            telemetry_written=True
        )
```

---

## 5. Write Targets (Design Only)

### 5.1 Primary Write Targets

| Target Table | Purpose | Write Condition |
|--------------|---------|-----------------|
| `fhq_governance.llm_routing_log` | All LLM call metadata | Every call |
| `fhq_governance.telemetry_cost_ledger` | Cost tracking | Every call |
| `fhq_governance.api_budget_log` | Budget increment | Every call |
| `fhq_governance.agent_task_log` | Task enrichment | If task_id provided |
| `fhq_governance.asrp_state_log` | State at call time | If state changed |
| `fhq_governance.telemetry_errors` | Error capture | On error |
| `fhq_cognition.lineage_log` | Cognitive linkage | If cognitive context |

### 5.2 Write Order (Transactional)

```sql
-- DESIGN ONLY: Transactional write sequence
BEGIN;

-- 1. Primary routing log
INSERT INTO fhq_governance.llm_routing_log (...);

-- 2. Cost ledger
INSERT INTO fhq_governance.telemetry_cost_ledger (...);

-- 3. Budget increment
UPDATE fhq_governance.api_budget_log
SET requests_made = requests_made + 1,
    ...
WHERE provider_name = :provider AND usage_date = CURRENT_DATE;

-- 4. Task enrichment (if applicable)
UPDATE fhq_governance.agent_task_log
SET provider = :provider, cost_usd = :cost, latency_ms = :latency
WHERE task_id = :task_id;

-- 5. Cognitive lineage (if applicable)
INSERT INTO fhq_cognition.lineage_log (...);

COMMIT;
-- If ANY write fails, ROLLBACK and BLOCK response
```

---

## 6. Fail-Closed Architecture

### 6.1 Failure Modes and Responses

| Failure | Action | Rationale |
|---------|--------|-----------|
| Telemetry write fails | BLOCK LLM response | Better no data than untracked data |
| Governance hydration fails | BLOCK LLM call | Cannot verify compliance |
| Budget exceeded | BLOCK LLM call | Economic discipline |
| ASRP blocked | BLOCK LLM call | State reliability |
| Provider timeout | RETRY then BLOCK | Bounded retry policy |
| Provider error | LOG and BLOCK | Preserve error context |

### 6.2 Fail-Closed Implementation Pattern

```python
# DESIGN ONLY
def fail_closed_write(envelope: TelemetryEnvelope) -> bool:
    """
    Fail-closed telemetry write.
    Returns True only if ALL writes succeed.
    """
    try:
        with db.transaction() as tx:
            tx.insert('llm_routing_log', envelope.to_routing())
            tx.insert('telemetry_cost_ledger', envelope.to_cost())
            tx.update('api_budget_log', envelope.to_budget_increment())

            if envelope.task_id:
                tx.update('agent_task_log', envelope.to_task_enrichment())

            if envelope.cognitive_parent_id:
                tx.insert('lineage_log', envelope.to_lineage())

            tx.commit()
            return True

    except Exception as e:
        # Log the failure but DO NOT return the LLM response
        logger.critical(f"Telemetry write failed: {e}")
        return False
```

---

## 7. Streaming Aggregation Strategy

### 7.1 Problem Statement

DeepSeek Reasoner uses streaming responses. Without aggregation:
- `tokens_out = 0` (each chunk has partial count)
- Cost calculation fails
- Latency is per-chunk not total

### 7.2 Aggregation Design

```python
# DESIGN ONLY
class StreamAggregator:
    """Aggregates streaming LLM responses for telemetry"""

    def __init__(self):
        self.chunks = []
        self.total_tokens = 0
        self.first_token_time = None
        self.last_token_time = None

    def on_chunk(self, chunk: StreamChunk):
        if self.first_token_time is None:
            self.first_token_time = time.monotonic()

        self.chunks.append(chunk)
        self.total_tokens += chunk.token_count
        self.last_token_time = time.monotonic()

    def finalize(self) -> AggregatedResponse:
        return AggregatedResponse(
            content=self.merge_content(),
            total_tokens=self.total_tokens,
            chunk_count=len(self.chunks),
            ttft_ms=self.calculate_ttft(),
            total_latency_ms=self.calculate_total_latency()
        )
```

---

## 8. Integration Points

### 8.1 SitC Integration (Chain-of-Query)

```
TRIGGER: research_protocols.status = 'EXECUTING'
CONTEXT: protocol_id, current_step, query_chain
ROUTER ACTION: Attach protocol_ref to envelope
```

### 8.2 InForage Integration (Information Economics)

```
TRIGGER: Before each search/retrieval call
CONTEXT: current_scent, cost_so_far, expected_value
ROUTER ACTION: Block if diminishing returns detected
```

### 8.3 IKEA Integration (Knowledge Boundary)

```
TRIGGER: Before each LLM call
CONTEXT: query, parametric_confidence, boundary_type
ROUTER ACTION: Block hallucination attempts, redirect to search
```

---

## 9. Design Constraints

- **NO IMPLEMENTATION** in PHASE 2
- **NO CODE CHANGES** to existing agents
- **NO SCHEMA CHANGES** to database
- **NO DECORATOR ATTACHMENT** to functions
- This document describes FUTURE architecture only

---

## 10. PHASE 3 Prerequisites

Before PHASE 3 implementation:
1. CEO authorization
2. VEGA attestation of design compliance
3. Migration scripts approved
4. Test environment prepared
5. Rollback plan documented

---

**END OF BLUEPRINT**

*DESIGN ONLY - ZERO IMPLEMENTATION PERMITTED*
