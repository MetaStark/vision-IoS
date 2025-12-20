"""
FjordHQ @metered_execution Decorator
====================================
Authority: CEO Directive - PHASE 3
Compliance: Decorator Contract v1, TCS-v1, ADR-012, ADR-021

The agent-side entry point to the LLM Router.
Every LLM call MUST be wrapped with this decorator.

"No Agent May Think Unobserved"
"""

import functools
import time
import logging
import traceback
from typing import Callable, Optional, Any, Union, Generator
from uuid import UUID
from decimal import Decimal

from .llm_router import get_router, LLMRouter
from .telemetry_envelope import (
    TelemetryEnvelope, TaskType, CognitiveModality, MeteredResponse, MeteredError
)
from .stream_aggregator import StreamAggregator, AggregatedResponse
from .errors import (
    TelemetryError,
    TelemetryWriteFailure,
    BudgetExceededError,
    GovernanceBlockError,
    CognitiveContextMissingError
)

logger = logging.getLogger('fhq_telemetry.decorator')


def metered_execution(
    task_name: str,
    task_type: Union[TaskType, str],
    agent_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    cognitive_modality: Optional[CognitiveModality] = None,
    protocol_ref: Optional[UUID] = None,
    correlation_id: Optional[UUID] = None,
    cognitive_parent_id: Optional[UUID] = None,
    budget_override: Optional[Decimal] = None,
    stream_mode: bool = False,
    fail_silent: bool = False
) -> Callable:
    """
    Decorator that wraps LLM calls with telemetry capture.

    Per Decorator Contract v1:
    - Extracts call context
    - Measures wall-clock latency
    - Counts tokens (in/out)
    - Captures errors
    - Writes telemetry envelope
    - Hash-chains via ADR-013

    Args:
        task_name: Human-readable task identifier (required)
        task_type: Category of task being performed (required)
        agent_id: Agent making the call (auto-detected if not provided)
        provider: LLM provider (DEEPSEEK, ANTHROPIC, OPENAI, GEMINI)
        model: Specific model used
        cognitive_modality: Cognitive classification per ADR-021
        protocol_ref: SitC Chain-of-Query reference
        correlation_id: Links related LLM calls
        cognitive_parent_id: Parent node in reasoning chain
        budget_override: Per-call budget limit
        stream_mode: Enable streaming aggregation
        fail_silent: If True, return None on error instead of raise

    Returns:
        Decorated function that emits telemetry on every call

    FAIL-CLOSED BEHAVIOR:
        If telemetry write fails, raise TelemetryWriteFailure.
        LLM response is NOT returned without successful telemetry.
    """
    # Normalize task_type
    if isinstance(task_type, str):
        task_type = TaskType(task_type.upper())

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            router = get_router()

            # Extract or use provided values
            _agent_id = agent_id or _detect_agent_id(func, args, kwargs)
            _provider = provider or _detect_provider(func, args, kwargs)
            _model = model or _detect_model(func, args, kwargs)

            # Create envelope
            envelope = router.create_envelope(
                agent_id=_agent_id,
                task_name=task_name,
                task_type=task_type,
                provider=_provider,
                model=_model,
                correlation_id=correlation_id,
                cognitive_parent_id=cognitive_parent_id,
                protocol_ref=protocol_ref,
                cognitive_modality=cognitive_modality
            )

            # =========================================================
            # PRE-CALL VALIDATION
            # =========================================================
            pre_call_error = router.validate_pre_call(envelope)
            if pre_call_error:
                logger.warning(f"Pre-call validation failed: {pre_call_error}")
                # Write error to telemetry
                router.write_error_only(envelope, pre_call_error)

                if fail_silent:
                    return MeteredError(
                        error_type=type(pre_call_error).__name__,
                        error_payload=pre_call_error.to_error_payload() if hasattr(pre_call_error, 'to_error_payload') else {},
                        telemetry_envelope_id=envelope.envelope_id,
                        recoverable=pre_call_error.recoverable,
                        retry_after_seconds=pre_call_error.retry_after_seconds
                    )
                raise pre_call_error

            # =========================================================
            # EXECUTE LLM CALL
            # =========================================================
            start_time = time.monotonic()
            tokens_in = 0
            tokens_out = 0
            result = None
            error = None
            aggregator = None

            try:
                if stream_mode:
                    # Handle streaming response
                    aggregator = StreamAggregator()
                    aggregator.on_stream_start()

                    # Call the function
                    stream_response = func(*args, **kwargs)

                    # Check if it's a generator
                    if hasattr(stream_response, '__iter__') and hasattr(stream_response, '__next__'):
                        # Aggregate the stream
                        collected_chunks = []
                        for chunk in stream_response:
                            aggregator.on_chunk(chunk)
                            collected_chunks.append(chunk)

                        agg_result = aggregator.on_stream_end()
                        tokens_out = agg_result.tokens_out
                        envelope.stream_chunks = agg_result.chunk_count
                        envelope.stream_first_token_ms = agg_result.ttft_ms
                        envelope.stream_token_accumulator = tokens_out

                        # Return content or collected chunks based on what caller expects
                        result = agg_result.content if agg_result.content else collected_chunks
                    else:
                        # Not actually a stream, treat as normal
                        result = stream_response
                else:
                    # Non-streaming call
                    result = func(*args, **kwargs)

                # Extract tokens from response
                tokens_in, tokens_out = _extract_tokens(result, tokens_in, tokens_out)

            except Exception as e:
                error = e
                logger.error(f"LLM call failed: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(traceback.format_exc())

            # =========================================================
            # RECORD TELEMETRY
            # =========================================================
            end_time = time.monotonic()
            latency_ms = int((end_time - start_time) * 1000)

            try:
                write_success = router.record_call(
                    envelope=envelope,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    stream_mode=stream_mode,
                    stream_chunks=envelope.stream_chunks,
                    stream_first_token_ms=envelope.stream_first_token_ms,
                    error=error
                )

                if not write_success:
                    raise TelemetryWriteFailure(
                        message="Telemetry write returned False",
                        envelope_id=envelope.envelope_id
                    )

            except TelemetryWriteFailure:
                if fail_silent:
                    return None
                raise

            # =========================================================
            # RETURN RESULT
            # =========================================================
            if error:
                if fail_silent:
                    return MeteredError(
                        error_type=type(error).__name__,
                        error_payload={"message": str(error)},
                        telemetry_envelope_id=envelope.envelope_id,
                        recoverable=getattr(error, 'recoverable', False)
                    )
                raise error

            return MeteredResponse(
                raw_llm_output=result,
                telemetry_envelope_id=envelope.envelope_id,
                cost_usd=envelope.cost_usd,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out
            )

        return wrapper
    return decorator


def _detect_agent_id(func: Callable, args: tuple, kwargs: dict) -> str:
    """Detect agent_id from function context."""
    # Check kwargs
    if 'agent_id' in kwargs:
        return kwargs['agent_id']

    # Check if first arg is self with agent_id attribute
    if args and hasattr(args[0], 'agent_id'):
        return args[0].agent_id

    # Check function module for hints
    module = getattr(func, '__module__', '')
    if 'finn' in module.lower():
        return 'FINN'
    elif 'crio' in module.lower():
        return 'CRIO'
    elif 'lars' in module.lower():
        return 'LARS'
    elif 'stig' in module.lower():
        return 'STIG'
    elif 'line' in module.lower():
        return 'LINE'
    elif 'vega' in module.lower():
        return 'VEGA'
    elif 'ceio' in module.lower():
        return 'CEIO'

    return 'UNKNOWN'


def _detect_provider(func: Callable, args: tuple, kwargs: dict) -> str:
    """Detect provider from function context."""
    # Check kwargs
    if 'provider' in kwargs:
        return kwargs['provider']

    # Check for client objects
    for arg in args:
        arg_type = type(arg).__name__.lower()
        if 'deepseek' in arg_type:
            return 'DEEPSEEK'
        elif 'anthropic' in arg_type:
            return 'ANTHROPIC'
        elif 'openai' in arg_type:
            return 'OPENAI'
        elif 'gemini' in arg_type or 'google' in arg_type:
            return 'GEMINI'

    # Check function name
    func_name = func.__name__.lower()
    if 'deepseek' in func_name:
        return 'DEEPSEEK'
    elif 'anthropic' in func_name or 'claude' in func_name:
        return 'ANTHROPIC'
    elif 'openai' in func_name or 'gpt' in func_name:
        return 'OPENAI'
    elif 'gemini' in func_name:
        return 'GEMINI'

    return 'DEEPSEEK'  # Default


def _detect_model(func: Callable, args: tuple, kwargs: dict) -> str:
    """Detect model from function context."""
    # Check kwargs
    if 'model' in kwargs:
        return kwargs['model']

    # Check for model in args
    for arg in args:
        if isinstance(arg, str) and any(m in arg.lower() for m in
            ['deepseek', 'claude', 'gpt', 'gemini']):
            return arg

    return 'deepseek-reasoner'  # Default


def _extract_tokens(response: Any, tokens_in: int, tokens_out: int) -> tuple[int, int]:
    """Extract token counts from response object."""
    if response is None:
        return tokens_in, tokens_out

    # OpenAI/DeepSeek format
    if hasattr(response, 'usage'):
        usage = response.usage
        if hasattr(usage, 'prompt_tokens'):
            tokens_in = usage.prompt_tokens or 0
        if hasattr(usage, 'completion_tokens'):
            tokens_out = usage.completion_tokens or 0
        if hasattr(usage, 'total_tokens') and tokens_in == 0 and tokens_out == 0:
            # Estimate split
            tokens_out = usage.total_tokens or 0

    # Dict format
    elif isinstance(response, dict):
        usage = response.get('usage', {})
        tokens_in = usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0) or tokens_in
        tokens_out = usage.get('completion_tokens', 0) or usage.get('output_tokens', 0) or tokens_out

    # MeteredResponse passthrough
    elif isinstance(response, MeteredResponse):
        tokens_in = response.tokens_in
        tokens_out = response.tokens_out

    # String response - estimate
    elif isinstance(response, str) and tokens_out == 0:
        tokens_out = len(response) // 4  # Rough estimate

    return tokens_in, tokens_out


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

def meter_llm_call(
    agent_id: str,
    task_name: str,
    task_type: TaskType,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    stream_mode: bool = False,
    stream_chunks: Optional[int] = None,
    stream_first_token_ms: Optional[int] = None,
    error: Optional[Exception] = None,
    cognitive_parent_id: Optional[UUID] = None,
    protocol_ref: Optional[UUID] = None,
    cognitive_modality: Optional[CognitiveModality] = None,
    correlation_id: Optional[UUID] = None
) -> UUID:
    """
    Directly record an LLM call without using the decorator.

    Use this when you can't use the decorator (e.g., complex async flows).

    Returns the envelope_id.
    """
    router = get_router()

    envelope = router.create_envelope(
        agent_id=agent_id,
        task_name=task_name,
        task_type=task_type,
        provider=provider,
        model=model,
        correlation_id=correlation_id,
        cognitive_parent_id=cognitive_parent_id,
        protocol_ref=protocol_ref,
        cognitive_modality=cognitive_modality
    )

    # Validate
    pre_call_error = router.validate_pre_call(envelope)
    if pre_call_error:
        router.write_error_only(envelope, pre_call_error)
        raise pre_call_error

    # Record
    router.record_call(
        envelope=envelope,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        stream_mode=stream_mode,
        stream_chunks=stream_chunks,
        stream_first_token_ms=stream_first_token_ms,
        error=error
    )

    return envelope.envelope_id


class MeteredLLMContext:
    """
    Context manager for metering LLM calls.

    Usage:
        with MeteredLLMContext(agent_id="FINN", task_name="research", ...) as ctx:
            response = llm_client.chat(...)
            ctx.set_response(response)
    """

    def __init__(
        self,
        agent_id: str,
        task_name: str,
        task_type: TaskType,
        provider: str,
        model: str,
        stream_mode: bool = False,
        **kwargs
    ):
        self.router = get_router()
        self.envelope = self.router.create_envelope(
            agent_id=agent_id,
            task_name=task_name,
            task_type=task_type,
            provider=provider,
            model=model,
            **kwargs
        )
        self.stream_mode = stream_mode
        self.start_time: Optional[float] = None
        self.tokens_in = 0
        self.tokens_out = 0
        self.error: Optional[Exception] = None
        self.aggregator: Optional[StreamAggregator] = None

    def __enter__(self) -> 'MeteredLLMContext':
        # Validate pre-call
        pre_call_error = self.router.validate_pre_call(self.envelope)
        if pre_call_error:
            self.router.write_error_only(self.envelope, pre_call_error)
            raise pre_call_error

        self.start_time = time.monotonic()

        if self.stream_mode:
            self.aggregator = StreamAggregator()
            self.aggregator.on_stream_start()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency_ms = int((time.monotonic() - self.start_time) * 1000) if self.start_time else 0

        if exc_val:
            self.error = exc_val

        stream_chunks = None
        stream_first_token_ms = None

        if self.aggregator:
            result = self.aggregator.on_stream_end()
            self.tokens_out = result.tokens_out
            stream_chunks = result.chunk_count
            stream_first_token_ms = result.ttft_ms

        self.router.record_call(
            envelope=self.envelope,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            latency_ms=latency_ms,
            stream_mode=self.stream_mode,
            stream_chunks=stream_chunks,
            stream_first_token_ms=stream_first_token_ms,
            error=self.error
        )

        return False  # Don't suppress exceptions

    def set_response(self, response: Any) -> None:
        """Set response to extract tokens from."""
        self.tokens_in, self.tokens_out = _extract_tokens(response, self.tokens_in, self.tokens_out)

    def set_tokens(self, tokens_in: int, tokens_out: int) -> None:
        """Directly set token counts."""
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out

    def add_chunk(self, chunk: Any) -> None:
        """Add streaming chunk (if stream_mode=True)."""
        if self.aggregator:
            self.aggregator.on_chunk(chunk)

    @property
    def envelope_id(self) -> UUID:
        return self.envelope.envelope_id
