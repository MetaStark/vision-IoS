# Decorator Contract v1

**Document ID:** DC-v1
**Status:** DESIGN-ONLY (No Implementation Permitted)
**Authority:** CEO Directive - PHASE 2
**Compliance:** ADR-001, ADR-012, ADR-013, ADR-018, ADR-020, ADR-021
**Author:** STIG (CTO)
**Date:** 2025-12-10

---

## 1. Purpose

This document defines the Python-side contract for the `@metered_execution` decorator WITHOUT writing the actual decorator. The decorator is the agent-side entry point to the LLM Router.

---

## 2. Decorator Signature (Design)

```python
# DESIGN ONLY - NOT TO BE IMPLEMENTED IN PHASE 2

def metered_execution(
    task_name: str,
    task_type: TaskType,
    agent_id: str = None,           # Auto-detected if not provided
    provider: str = None,           # Auto-detected from function
    model: str = None,              # Auto-detected from function
    cognitive_modality: CognitiveModality = None,
    protocol_ref: UUID = None,      # SitC Chain-of-Query reference
    budget_override: Decimal = None,# Per-call budget limit
    stream_mode: bool = False,      # Enable streaming aggregation
    fail_silent: bool = False,      # If True, return None on error instead of raise
) -> Callable:
    """
    Decorator that wraps LLM calls with telemetry capture.

    DESIGN CONTRACT:
    - Extracts call context
    - Measures wall-clock latency
    - Counts tokens (in/out)
    - Captures errors
    - Writes telemetry envelope
    - Hash-chains via ADR-013

    Returns:
    - Wrapped function that emits telemetry on every call

    FAIL-CLOSED BEHAVIOR:
    - If telemetry write fails, raise TelemetryWriteFailure
    - LLM response is NOT returned without successful telemetry
    """
    pass  # DESIGN ONLY
```

---

## 3. Mandatory Requirements

### 3.1 Context Extraction

The decorator MUST extract:

| Field | Source | Method |
|-------|--------|--------|
| `agent_id` | Calling context | `get_current_agent()` or parameter |
| `task_name` | Decorator parameter | Required parameter |
| `task_type` | Decorator parameter | Required parameter |
| `provider` | LLM client inspection | Detect from wrapped function |
| `model` | LLM client inspection | Detect from wrapped function |
| `correlation_id` | Context propagation | `get_correlation_id()` or new UUID |
| `cognitive_parent_id` | Cognitive context | From `CognitiveContext.current()` |
| `protocol_ref` | SitC context | From `ResearchProtocol.current()` |

### 3.2 Latency Measurement

```python
# DESIGN ONLY
def measure_latency(wrapped_func):
    """
    Latency measurement contract:

    1. Record T0 (pre-validation start)
    2. Record T1 (HTTP request sent)
    3. Record T2 (first byte/token received) - streaming only
    4. Record T3 (last byte received)
    5. Record T4 (post-processing complete)

    Telemetry fields:
    - latency_ms = T3 - T1 (provider time)
    - total_latency_ms = T4 - T0 (full pipeline)
    - ttft_ms = T2 - T1 (time to first token) - streaming only
    """
    pass
```

### 3.3 Token Counting

```python
# DESIGN ONLY
def count_tokens(response):
    """
    Token counting contract:

    For standard responses:
    - tokens_in = response.usage.prompt_tokens
    - tokens_out = response.usage.completion_tokens

    For streaming responses:
    - Use StreamAggregator
    - Accumulate chunk.token_count across all chunks
    - Handle providers that don't include per-chunk counts

    For reasoning models (deepseek-reasoner):
    - reasoning_tokens = response.usage.reasoning_tokens (if present)
    - Total = prompt_tokens + completion_tokens + reasoning_tokens
    """
    pass
```

### 3.4 Error Capture

```python
# DESIGN ONLY
def capture_error(exception):
    """
    Error capture contract:

    Classify error into standard types:
    - TIMEOUT_ERROR
    - PROVIDER_ERROR
    - HALLUCINATION_BLOCK
    - IKEA_BOUNDARY_VIOLATION
    - DIMINISHING_RETURNS_TERMINATION
    - BUDGET_EXCEEDED
    - GOVERNANCE_BLOCK

    Capture in error_payload:
    - Original exception type
    - Exception message
    - Stack trace (truncated)
    - Provider-specific error codes
    - HTTP status if applicable

    Write to:
    - fhq_governance.telemetry_errors
    """
    pass
```

### 3.5 Telemetry Envelope Writing

```python
# DESIGN ONLY
def write_telemetry(envelope: TelemetryEnvelope) -> str:
    """
    Telemetry write contract:

    1. Validate envelope completeness
    2. Calculate cost_usd from tokens and pricing
    3. Generate governance_context_hash via IoS-013
    4. Begin transaction
    5. Write to llm_routing_log
    6. Write to telemetry_cost_ledger
    7. Update api_budget_log
    8. Update agent_task_log (if task_id)
    9. Write to lineage_log (if cognitive context)
    10. Commit transaction

    FAIL-CLOSED:
    - If ANY write fails, ROLLBACK
    - Raise TelemetryWriteFailure
    - DO NOT return LLM response

    Returns:
    - envelope_id (UUID) on success
    """
    pass
```

### 3.6 Hash-Chain via ADR-013

```python
# DESIGN ONLY
def compute_hash_chain(envelope: TelemetryEnvelope) -> str:
    """
    Hash-chain contract per ADR-013:

    1. Get previous hash from lineage_log for this agent
    2. Compute hash_self:
       hash_self = SHA256(
           envelope_id +
           agent_id +
           timestamp_utc +
           tokens_in +
           tokens_out +
           cost_usd +
           governance_context_hash
       )
    3. Compute lineage_hash:
       lineage_hash = SHA256(hash_prev + hash_self)
    4. Store in envelope

    This creates an immutable audit chain for all LLM operations.
    """
    pass
```

---

## 4. Streaming Aggregation Strategy

### 4.1 Problem

DeepSeek Reasoner and other models use streaming. Without aggregation:
- `tokens_out = 0` (incomplete)
- Cost cannot be calculated
- Latency is per-chunk not total

### 4.2 Solution Design

```python
# DESIGN ONLY
class StreamAggregator:
    """
    Contract for streaming response aggregation.

    Lifecycle:
    1. on_stream_start() - Initialize accumulator
    2. on_chunk(chunk) - Accumulate each chunk
    3. on_stream_end() - Finalize and return aggregated response

    Accumulation rules:
    - content: Concatenate chunk.delta.content
    - tokens: Sum chunk.usage.completion_tokens (if present)
    - If no per-chunk tokens, estimate from content length

    Final output:
    - stream_mode = True
    - stream_chunks = number of chunks received
    - stream_token_accumulator = total tokens
    - tokens_out = stream_token_accumulator
    - ttft_ms = time from start to first chunk
    """

    def on_stream_start(self):
        """Initialize state"""
        self.chunks = []
        self.content_buffer = []
        self.token_count = 0
        self.start_time = time.monotonic()
        self.first_chunk_time = None

    def on_chunk(self, chunk):
        """Process each chunk"""
        if self.first_chunk_time is None:
            self.first_chunk_time = time.monotonic()

        self.chunks.append(chunk)

        if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'content'):
            self.content_buffer.append(chunk.delta.content or '')

        # Token counting varies by provider
        if hasattr(chunk, 'usage') and chunk.usage:
            self.token_count += chunk.usage.completion_tokens or 0

    def on_stream_end(self) -> AggregatedResponse:
        """Finalize aggregation"""
        end_time = time.monotonic()

        # If no token counts in chunks, estimate
        if self.token_count == 0:
            full_content = ''.join(self.content_buffer)
            # Rough estimate: 4 chars per token
            self.token_count = len(full_content) // 4

        return AggregatedResponse(
            content=''.join(self.content_buffer),
            tokens_out=self.token_count,
            chunk_count=len(self.chunks),
            ttft_ms=int((self.first_chunk_time - self.start_time) * 1000),
            total_latency_ms=int((end_time - self.start_time) * 1000),
            stream_mode=True
        )
```

---

## 5. Return Contract

### 5.1 Successful Call Return

```python
# DESIGN ONLY
@dataclass
class MeteredResponse:
    """
    Return type for @metered_execution decorated functions.

    Contract:
    - raw_llm_output: The original LLM response (unchanged)
    - telemetry_envelope_id: UUID of written envelope
    - governance_signature: Future Ed25519 signature (optional)
    - cost_usd: Cost of this call
    - latency_ms: Provider latency
    """
    raw_llm_output: Any          # Original response
    telemetry_envelope_id: UUID  # Reference to telemetry record
    governance_signature: str    # Future: Ed25519 signature
    cost_usd: Decimal            # Cost in USD
    latency_ms: int              # Latency in milliseconds
    tokens_in: int               # Input tokens
    tokens_out: int              # Output tokens
```

### 5.2 Error Return

```python
# DESIGN ONLY
@dataclass
class MeteredError:
    """
    Return type when LLM call fails.

    Contract:
    - error_type: Standardized error classification
    - error_payload: Structured error details
    - telemetry_envelope_id: Envelope even for errors
    - recoverable: Whether retry is appropriate
    """
    error_type: str
    error_payload: dict
    telemetry_envelope_id: UUID
    recoverable: bool
    retry_after_seconds: int = None
```

---

## 6. Usage Pattern (Design Only)

### 6.1 Basic Usage

```python
# DESIGN ONLY - Example of how decorator would be used

@metered_execution(
    task_name="CRIO_GAP_ANALYSIS",
    task_type=TaskType.RESEARCH,
    agent_id="CRIO"
)
def analyze_gap(query: str) -> dict:
    """This function would be wrapped by the decorator"""
    response = deepseek_client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[{"role": "user", "content": query}],
        stream=True
    )
    return response
```

### 6.2 With Cognitive Context

```python
# DESIGN ONLY - Example with ADR-021 cognitive linking

@metered_execution(
    task_name="SITC_CHAIN_STEP",
    task_type=TaskType.SYNTHESIS,
    cognitive_modality=CognitiveModality.CAUSAL,
    protocol_ref=current_protocol.id
)
def execute_chain_step(context: dict) -> dict:
    """This function is part of a SitC Chain-of-Query"""
    pass
```

### 6.3 With Streaming

```python
# DESIGN ONLY - Example with streaming aggregation

@metered_execution(
    task_name="DEEP_REASONING",
    task_type=TaskType.ANALYSIS,
    stream_mode=True
)
def deep_reason(prompt: str) -> str:
    """Streaming response with automatic aggregation"""
    pass
```

---

## 7. Integration with Existing Code

### 7.1 Files Requiring Decoration

Based on PHASE 1 findings, these files make LLM calls:

| File | Function | Decoration Required |
|------|----------|---------------------|
| `06_AGENTS/FINN/finn_deepseek_researcher.py:227` | `DeepSeekClient.analyze()` | Yes |
| `scripts/research_daemon.py:245` | `synthesize_with_deepseek()` | Yes |
| `scripts/research_daemon.py:504` | `analyze_for_trade_impact()` | Yes |
| `scripts/crio_night_watch.py:451` | `synthesize_research()` | Yes |
| `scripts/crio_night_watch.py:587` | `deep_analysis()` | Yes |
| `scripts/force_batch_reasoning.py:142` | `generate_reasoning()` | Yes |
| `05_ORCHESTRATOR/orchestrator_daemon.py:703` | `llm_synthesis()` | Yes |

### 7.2 Migration Strategy (Design Only)

```
PHASE 3 Migration Order:
1. Implement decorator in fhq_telemetry.py
2. Import decorator in each file
3. Apply to each function
4. Test with dry-run mode
5. Enable telemetry writes
6. Verify via dashboard/AOL
```

---

## 8. Error Handling Contract

### 8.1 Exception Hierarchy (Design)

```python
# DESIGN ONLY
class TelemetryError(Exception):
    """Base class for telemetry errors"""
    pass

class TelemetryWriteFailure(TelemetryError):
    """Failed to write telemetry - BLOCKS LLM response"""
    pass

class BudgetExceededError(TelemetryError):
    """ADR-012 budget exceeded"""
    pass

class GovernanceBlockError(TelemetryError):
    """ADR-018 governance blocked"""
    pass

class IKEABoundaryError(TelemetryError):
    """EC-022 knowledge boundary violation"""
    pass

class InForageTerminationError(TelemetryError):
    """EC-021 diminishing returns"""
    pass
```

### 8.2 Error Logging

All errors written to `fhq_governance.telemetry_errors` with:
- envelope_id (links to routing log)
- error_type
- error_payload (JSONB)
- stack_trace (TEXT, truncated)
- created_at

---

## 9. Design Constraints

- **NO IMPLEMENTATION** in PHASE 2
- **NO CODE CHANGES** to existing agents
- **NO DECORATOR ATTACHMENT** to functions
- **NO NEW PYTHON FILES** created
- This document describes FUTURE implementation only

---

## 10. PHASE 3 Implementation Checklist

When CEO authorizes PHASE 3:

- [ ] Create `lib/fhq_telemetry/decorator.py`
- [ ] Implement `@metered_execution` per this contract
- [ ] Implement `StreamAggregator` class
- [ ] Implement `TelemetryEnvelope` dataclass
- [ ] Implement error hierarchy
- [ ] Unit tests for decorator
- [ ] Integration tests with mock LLM
- [ ] Apply to first file (finn_deepseek_researcher.py)
- [ ] Verify telemetry writes
- [ ] Roll out to remaining files

---

**END OF DECORATOR CONTRACT**

*DESIGN ONLY - ZERO IMPLEMENTATION PERMITTED*
