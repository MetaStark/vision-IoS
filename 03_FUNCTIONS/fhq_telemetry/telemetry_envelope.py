"""
FjordHQ Telemetry Envelope
==========================
Authority: CEO Directive - PHASE 3
Compliance: TCS-v1 Specification

The canonical envelope that every LLM call must emit.
"""

import os
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from enum import Enum


class TaskType(str, Enum):
    """Task type classification per TCS-v1."""
    RESEARCH = "RESEARCH"
    SYNTHESIS = "SYNTHESIS"
    ANALYSIS = "ANALYSIS"
    ORCHESTRATION = "ORCHESTRATION"
    VERIFICATION = "VERIFICATION"
    CLASSIFICATION = "CLASSIFICATION"
    SYSTEM_MAINTENANCE = "SYSTEM_MAINTENANCE"
    HEALTH_CHECK = "HEALTH_CHECK"


class CognitiveModality(str, Enum):
    """Cognitive modality classification per ADR-021."""
    SEARCH = "search"
    SYNTHESIS = "synthesis"
    CAUSAL = "causal"
    VERIFICATION = "verification"
    PERCEPTION = "perception"
    INTENT = "intent"


# Pricing table per TCS-v1 (Updated 2025-12-14 with official DeepSeek pricing)
PRICING_TABLE = {
    "DEEPSEEK": {
        # DeepSeek unified pricing (2025-12-14): Input $0.28/M, Output $0.42/M, Cache $0.028/M
        "deepseek-chat": {"input_per_1k": Decimal("0.00028"), "output_per_1k": Decimal("0.00042")},
        "deepseek-reasoner": {"input_per_1k": Decimal("0.00028"), "output_per_1k": Decimal("0.00042")},
    },
    "ANTHROPIC": {
        "claude-3-opus": {"input_per_1k": Decimal("0.015"), "output_per_1k": Decimal("0.075")},
        "claude-3-sonnet": {"input_per_1k": Decimal("0.003"), "output_per_1k": Decimal("0.015")},
        "claude-3-haiku": {"input_per_1k": Decimal("0.00025"), "output_per_1k": Decimal("0.00125")},
        "claude-opus-4-5-20251101": {"input_per_1k": Decimal("0.015"), "output_per_1k": Decimal("0.075")},
    },
    "OPENAI": {
        "gpt-4-turbo": {"input_per_1k": Decimal("0.01"), "output_per_1k": Decimal("0.03")},
        "gpt-4o": {"input_per_1k": Decimal("0.005"), "output_per_1k": Decimal("0.015")},
    },
    "GEMINI": {
        "gemini-1.5-pro": {"input_per_1k": Decimal("0.00125"), "output_per_1k": Decimal("0.005")},
    }
}


def calculate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> Decimal:
    """Calculate cost in USD based on TCS-v1 pricing table."""
    provider_upper = provider.upper()
    if provider_upper not in PRICING_TABLE:
        # Default to DeepSeek pricing (2025-12-14): Input $0.28/M, Output $0.42/M
        return (Decimal(tokens_in) / 1000 * Decimal("0.00028") +
                Decimal(tokens_out) / 1000 * Decimal("0.00042"))

    provider_models = PRICING_TABLE[provider_upper]
    model_lower = model.lower()

    # Try exact match first
    if model_lower in provider_models:
        rates = provider_models[model_lower]
    else:
        # Try partial match
        for model_key, rates in provider_models.items():
            if model_key in model_lower or model_lower in model_key:
                break
        else:
            # Default to first model in provider
            rates = list(provider_models.values())[0]

    return (Decimal(tokens_in) / 1000 * rates["input_per_1k"] +
            Decimal(tokens_out) / 1000 * rates["output_per_1k"])


@dataclass
class TelemetryEnvelope:
    """
    Canonical telemetry envelope per TCS-v1.

    Every LLM call MUST emit one envelope. This is the central data structure
    for LLM observability in FjordHQ.
    """

    # Identity
    envelope_id: UUID = field(default_factory=uuid4)
    agent_id: str = ""
    task_name: str = ""
    task_type: TaskType = TaskType.RESEARCH

    # Provider info
    provider: str = ""
    model: str = ""

    # Token metrics
    tokens_in: int = 0
    tokens_out: int = 0

    # Performance metrics
    latency_ms: int = 0
    cost_usd: Decimal = Decimal("0")

    # Timestamps
    timestamp_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Correlation
    correlation_id: Optional[UUID] = None

    # Governance
    governance_context_hash: Optional[str] = None

    # Retry/fallback
    retry_count: int = 0
    fallback_used: bool = False

    # Error info
    error_type: Optional[str] = None
    error_payload: Optional[Dict[str, Any]] = None

    # Cognitive links (ADR-021)
    cognitive_parent_id: Optional[UUID] = None
    protocol_ref: Optional[UUID] = None
    cognitive_modality: Optional[CognitiveModality] = None

    # Streaming fields
    stream_mode: bool = False
    stream_chunks: Optional[int] = None
    stream_token_accumulator: Optional[int] = None
    stream_first_token_ms: Optional[int] = None

    # Hash chain (ADR-013)
    hash_chain_id: Optional[str] = None
    hash_self: Optional[str] = None
    hash_prev: Optional[str] = None
    lineage_hash: Optional[str] = None

    # Backfill marker
    backfill: bool = False

    def calculate_cost_from_tokens(self) -> Decimal:
        """Calculate cost_usd from tokens using TCS-v1 pricing."""
        self.cost_usd = calculate_cost(
            self.provider, self.model, self.tokens_in, self.tokens_out
        )
        return self.cost_usd

    def compute_hash_self(self) -> str:
        """Compute hash_self per ADR-013."""
        hash_input = (
            f"{self.envelope_id}"
            f"{self.agent_id}"
            f"{self.timestamp_utc.isoformat()}"
            f"{self.tokens_in}"
            f"{self.tokens_out}"
            f"{self.cost_usd}"
            f"{self.governance_context_hash or ''}"
        )
        self.hash_self = hashlib.sha256(hash_input.encode()).hexdigest()
        return self.hash_self

    def compute_lineage_hash(self, hash_prev: Optional[str] = None) -> str:
        """Compute lineage_hash per ADR-013."""
        if hash_prev:
            self.hash_prev = hash_prev
        if not self.hash_self:
            self.compute_hash_self()
        lineage_input = f"{self.hash_prev or ''}{self.hash_self}"
        self.lineage_hash = hashlib.sha256(lineage_input.encode()).hexdigest()
        return self.lineage_hash

    def validate(self) -> tuple[bool, list[str]]:
        """Validate envelope completeness per TCS-v1."""
        errors = []

        if not self.agent_id:
            errors.append("agent_id is required")
        if not self.task_name:
            errors.append("task_name is required")
        if not self.provider:
            errors.append("provider is required")
        if not self.model:
            errors.append("model is required")

        # Cognitive context validation (ADR-021)
        # cognitive_parent_id required for multi-hop reasoning unless exempt task types
        exempt_types = {TaskType.SYSTEM_MAINTENANCE, TaskType.HEALTH_CHECK}
        if (self.task_type not in exempt_types and
            self.cognitive_modality in {CognitiveModality.CAUSAL, CognitiveModality.SYNTHESIS} and
            self.cognitive_parent_id is None):
            errors.append("cognitive_parent_id required for multi-hop reasoning (ADR-021)")

        return len(errors) == 0, errors

    def to_routing_log_dict(self) -> Dict[str, Any]:
        """Convert to dict for llm_routing_log insert."""
        return {
            "envelope_id": self.envelope_id,
            "agent_id": self.agent_id,
            "task_name": self.task_name,
            "task_type": self.task_type.value if isinstance(self.task_type, TaskType) else self.task_type,
            "routed_provider": self.provider,
            "requested_provider": self.provider,
            "requested_tier": 2,
            "routed_tier": 2,
            "model": self.model,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_ms": self.latency_ms,
            "cost_usd": float(self.cost_usd),
            "timestamp_utc": self.timestamp_utc,
            "correlation_id": self.correlation_id,
            "governance_context_hash": self.governance_context_hash,
            "cognitive_parent_id": self.cognitive_parent_id,
            "protocol_ref": self.protocol_ref,
            "cognitive_modality": self.cognitive_modality.value if self.cognitive_modality else None,
            "stream_mode": self.stream_mode,
            "stream_chunks": self.stream_chunks,
            "stream_token_accumulator": self.stream_token_accumulator,
            "stream_first_token_ms": self.stream_first_token_ms,
            "error_type": self.error_type,
            "error_payload": self.error_payload,
            "hash_chain_id": self.hash_chain_id,
            "hash_self": self.hash_self,
            "hash_prev": self.hash_prev,
            "lineage_hash": self.lineage_hash,
            "backfill": self.backfill,
            "policy_satisfied": True,
            "violation_detected": False
        }

    def to_error_log_dict(self) -> Dict[str, Any]:
        """Convert to dict for telemetry_errors insert."""
        return {
            "envelope_id": self.envelope_id,
            "agent_id": self.agent_id,
            "task_name": self.task_name,
            "task_type": self.task_type.value if isinstance(self.task_type, TaskType) else self.task_type,
            "error_type": self.error_type,
            "error_payload": self.error_payload,
            "provider": self.provider,
            "model": self.model
        }


@dataclass
class MeteredResponse:
    """
    Return type for @metered_execution decorated functions.

    Contract per Decorator Contract v1.
    """
    raw_llm_output: Any
    telemetry_envelope_id: UUID
    governance_signature: Optional[str] = None
    cost_usd: Decimal = Decimal("0")
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class MeteredError:
    """
    Return type when LLM call fails.

    Contract per Decorator Contract v1.
    """
    error_type: str
    error_payload: Dict[str, Any]
    telemetry_envelope_id: UUID
    recoverable: bool = False
    retry_after_seconds: Optional[int] = None
