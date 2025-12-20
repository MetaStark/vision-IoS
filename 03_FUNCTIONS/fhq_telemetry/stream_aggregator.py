"""
FjordHQ Stream Aggregator
=========================
Authority: CEO Directive - PHASE 3
Compliance: TCS-v1, Decorator Contract v1

Aggregates streaming LLM responses for accurate telemetry capture.
Critical for DeepSeek Reasoner and other streaming models.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Any, Generator
import logging

logger = logging.getLogger('fhq_telemetry.stream_aggregator')


@dataclass
class AggregatedResponse:
    """Final aggregated response from streaming."""
    content: str
    tokens_out: int
    chunk_count: int
    ttft_ms: int  # Time to first token
    total_latency_ms: int
    stream_mode: bool = True
    reasoning_content: Optional[str] = None


@dataclass
class StreamChunk:
    """Individual chunk from streaming response."""
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    token_count: int = 0
    finish_reason: Optional[str] = None
    raw_chunk: Any = None


class StreamAggregator:
    """
    Aggregates streaming LLM responses for telemetry.

    Per Decorator Contract v1:
    - Accumulates chunks
    - Sums token counts
    - Records TTFT (time to first token)
    - Handles providers that don't include per-chunk counts

    Usage:
        aggregator = StreamAggregator()
        aggregator.on_stream_start()

        for chunk in stream:
            aggregator.on_chunk(chunk)
            yield chunk  # Pass through to caller

        result = aggregator.on_stream_end()
    """

    def __init__(self, chars_per_token: int = 4):
        """
        Initialize stream aggregator.

        Args:
            chars_per_token: Characters per token for estimation when counts unavailable
        """
        self.chars_per_token = chars_per_token
        self.chunks: List[StreamChunk] = []
        self.content_buffer: List[str] = []
        self.reasoning_buffer: List[str] = []
        self.token_count: int = 0
        self.start_time: Optional[float] = None
        self.first_chunk_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self._finalized: bool = False

    def on_stream_start(self) -> None:
        """Initialize state at stream start."""
        self.chunks = []
        self.content_buffer = []
        self.reasoning_buffer = []
        self.token_count = 0
        self.start_time = time.monotonic()
        self.first_chunk_time = None
        self.end_time = None
        self._finalized = False
        logger.debug("Stream aggregation started")

    def on_chunk(self, chunk: Any) -> StreamChunk:
        """
        Process each chunk from the stream.

        Handles multiple response formats:
        - OpenAI/DeepSeek format: chunk.choices[0].delta.content
        - Anthropic format: chunk.delta.text
        - Raw dict format
        """
        if self.first_chunk_time is None:
            self.first_chunk_time = time.monotonic()

        parsed_chunk = self._parse_chunk(chunk)
        self.chunks.append(parsed_chunk)

        if parsed_chunk.content:
            self.content_buffer.append(parsed_chunk.content)

        if parsed_chunk.reasoning_content:
            self.reasoning_buffer.append(parsed_chunk.reasoning_content)

        # Accumulate token count if available
        if parsed_chunk.token_count > 0:
            self.token_count += parsed_chunk.token_count

        return parsed_chunk

    def _parse_chunk(self, chunk: Any) -> StreamChunk:
        """Parse different chunk formats into StreamChunk."""
        content = None
        reasoning_content = None
        token_count = 0
        finish_reason = None

        # OpenAI/DeepSeek format
        if hasattr(chunk, 'choices') and chunk.choices:
            choice = chunk.choices[0]
            if hasattr(choice, 'delta'):
                delta = choice.delta
                content = getattr(delta, 'content', None)
                reasoning_content = getattr(delta, 'reasoning_content', None)
            finish_reason = getattr(choice, 'finish_reason', None)

            # Get usage if available
            if hasattr(chunk, 'usage') and chunk.usage:
                token_count = getattr(chunk.usage, 'completion_tokens', 0) or 0

        # Anthropic format
        elif hasattr(chunk, 'delta'):
            content = getattr(chunk.delta, 'text', None)
            if hasattr(chunk, 'usage'):
                token_count = getattr(chunk.usage, 'output_tokens', 0) or 0

        # Dict format
        elif isinstance(chunk, dict):
            if 'choices' in chunk and chunk['choices']:
                choice = chunk['choices'][0]
                delta = choice.get('delta', {})
                content = delta.get('content')
                reasoning_content = delta.get('reasoning_content')
                finish_reason = choice.get('finish_reason')
            elif 'delta' in chunk:
                content = chunk['delta'].get('text')

            usage = chunk.get('usage', {})
            token_count = usage.get('completion_tokens', 0) or usage.get('output_tokens', 0) or 0

        return StreamChunk(
            content=content,
            reasoning_content=reasoning_content,
            token_count=token_count,
            finish_reason=finish_reason,
            raw_chunk=chunk
        )

    def on_stream_end(self) -> AggregatedResponse:
        """
        Finalize aggregation and return result.

        If no token counts were provided in chunks, estimate from content length.
        """
        self.end_time = time.monotonic()
        self._finalized = True

        full_content = ''.join(self.content_buffer)
        full_reasoning = ''.join(self.reasoning_buffer) if self.reasoning_buffer else None

        # Estimate tokens if not provided
        if self.token_count == 0 and full_content:
            self.token_count = len(full_content) // self.chars_per_token
            logger.debug(f"Estimated tokens from content: {self.token_count}")

        # Include reasoning tokens in estimate if present
        if self.token_count == 0 and full_reasoning:
            self.token_count += len(full_reasoning) // self.chars_per_token

        # Ensure minimum of 1 token if we have content
        if self.token_count == 0 and (full_content or full_reasoning):
            self.token_count = 1

        ttft_ms = 0
        if self.first_chunk_time and self.start_time:
            ttft_ms = int((self.first_chunk_time - self.start_time) * 1000)

        total_latency_ms = 0
        if self.end_time and self.start_time:
            total_latency_ms = int((self.end_time - self.start_time) * 1000)

        logger.debug(
            f"Stream aggregation complete: {len(self.chunks)} chunks, "
            f"{self.token_count} tokens, {ttft_ms}ms TTFT, {total_latency_ms}ms total"
        )

        return AggregatedResponse(
            content=full_content,
            tokens_out=self.token_count,
            chunk_count=len(self.chunks),
            ttft_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
            stream_mode=True,
            reasoning_content=full_reasoning
        )

    @property
    def current_content(self) -> str:
        """Get current accumulated content."""
        return ''.join(self.content_buffer)

    @property
    def current_token_count(self) -> int:
        """Get current token count."""
        return self.token_count

    @property
    def elapsed_ms(self) -> int:
        """Get elapsed time since start."""
        if self.start_time is None:
            return 0
        return int((time.monotonic() - self.start_time) * 1000)


def aggregate_stream(stream: Generator, chars_per_token: int = 4) -> tuple[str, AggregatedResponse]:
    """
    Convenience function to aggregate an entire stream.

    Args:
        stream: Generator/iterator yielding chunks
        chars_per_token: For token estimation

    Returns:
        Tuple of (full_content, AggregatedResponse)
    """
    aggregator = StreamAggregator(chars_per_token=chars_per_token)
    aggregator.on_stream_start()

    for chunk in stream:
        aggregator.on_chunk(chunk)

    result = aggregator.on_stream_end()
    return result.content, result
