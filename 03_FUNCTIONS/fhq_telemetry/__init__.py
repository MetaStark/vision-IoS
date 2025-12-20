"""
FjordHQ LLM Telemetry Module - PHASE 3
======================================
Authority: CEO Directive - PHASE 3 AUTHORIZATION
Compliance: ADR-001, ADR-012, ADR-013, ADR-018, ADR-020, ADR-021
Executor: STIG (CTO)

"No Agent May Think Unobserved"

This module provides:
- LLMRouter: Centralized LLM routing with fail-closed semantics
- @metered_execution: Decorator for telemetry capture
- StreamAggregator: Streaming response aggregation
- TelemetryEnvelope: Canonical telemetry data structure
"""

from .llm_router import LLMRouter
from .metered_execution import metered_execution
from .stream_aggregator import StreamAggregator
from .telemetry_envelope import TelemetryEnvelope
from .errors import (
    TelemetryError,
    TelemetryWriteFailure,
    BudgetExceededError,
    GovernanceBlockError,
    IKEABoundaryError,
    InForageTerminationError,
    CognitiveContextMissingError,
    ASRPStateBlockedError,
    DEFCONBlockedError
)

__version__ = "1.0.0"
__author__ = "STIG (CTO)"
__all__ = [
    'LLMRouter',
    'metered_execution',
    'StreamAggregator',
    'TelemetryEnvelope',
    'TelemetryError',
    'TelemetryWriteFailure',
    'BudgetExceededError',
    'GovernanceBlockError',
    'IKEABoundaryError',
    'InForageTerminationError',
    'CognitiveContextMissingError',
    'ASRPStateBlockedError',
    'DEFCONBlockedError'
]
