"""
FjordHQ Telemetry Error Hierarchy
=================================
Authority: CEO Directive - PHASE 3
Compliance: ADR-012, ADR-018, ADR-020, ADR-021

Error classification per TCS-v1 specification.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from decimal import Decimal
from uuid import UUID


class TelemetryError(Exception):
    """Base class for telemetry errors."""

    def __init__(self, message: str, envelope_id: Optional[UUID] = None):
        super().__init__(message)
        self.envelope_id = envelope_id
        self.recoverable = False
        self.retry_after_seconds: Optional[int] = None


class TelemetryWriteFailure(TelemetryError):
    """
    Failed to write telemetry - BLOCKS LLM response.

    This is the critical fail-closed error. When telemetry cannot be written,
    the LLM response MUST be discarded per CEO Directive.
    """

    def __init__(self, message: str, envelope_id: Optional[UUID] = None,
                 partial_write: bool = False):
        super().__init__(message, envelope_id)
        self.partial_write = partial_write
        self.recoverable = False


class BudgetExceededError(TelemetryError):
    """
    ADR-012 budget exceeded.

    Raised when an LLM call would exceed configured budget limits.
    """

    def __init__(
        self,
        message: str,
        envelope_id: Optional[UUID] = None,
        budget_type: str = "DAILY",  # DAILY, HOURLY, PER_TASK, PER_AGENT
        budget_limit: Decimal = Decimal("0"),
        current_usage: Decimal = Decimal("0"),
        requested_estimate: Decimal = Decimal("0"),
        provider: str = "",
        reset_time: Optional[str] = None
    ):
        super().__init__(message, envelope_id)
        self.budget_type = budget_type
        self.budget_limit = budget_limit
        self.current_usage = current_usage
        self.requested_estimate = requested_estimate
        self.provider = provider
        self.reset_time = reset_time
        self.recoverable = True
        self.retry_after_seconds = 3600 if budget_type == "HOURLY" else 86400

    def to_error_payload(self) -> Dict[str, Any]:
        return {
            "budget_type": self.budget_type,
            "budget_limit": str(self.budget_limit),
            "current_usage": str(self.current_usage),
            "requested_estimate": str(self.requested_estimate),
            "provider": self.provider,
            "reset_time": self.reset_time
        }


class GovernanceBlockError(TelemetryError):
    """
    ADR-018 ASRP or general governance block.

    Raised when governance systems block an LLM call.
    """

    def __init__(
        self,
        message: str,
        envelope_id: Optional[UUID] = None,
        block_source: str = "GOVERNANCE",  # ASRP, VEGA, DEFCON, TRUTH_GATEWAY
        block_reason: str = "",
        asrp_state: Optional[str] = None,
        defcon_level: Optional[int] = None,
        truth_vector_drift: Optional[Decimal] = None,
        remediation_required: bool = False
    ):
        super().__init__(message, envelope_id)
        self.block_source = block_source
        self.block_reason = block_reason
        self.asrp_state = asrp_state
        self.defcon_level = defcon_level
        self.truth_vector_drift = truth_vector_drift
        self.remediation_required = remediation_required
        self.recoverable = not remediation_required

    def to_error_payload(self) -> Dict[str, Any]:
        return {
            "block_source": self.block_source,
            "block_reason": self.block_reason,
            "asrp_state": self.asrp_state,
            "defcon_level": self.defcon_level,
            "truth_vector_drift": str(self.truth_vector_drift) if self.truth_vector_drift else None,
            "remediation_required": self.remediation_required
        }


class ASRPStateBlockedError(GovernanceBlockError):
    """ADR-018 ASRP state specifically blocked."""

    def __init__(self, message: str, envelope_id: Optional[UUID] = None,
                 asrp_state: str = "SUSPENDED"):
        super().__init__(
            message=message,
            envelope_id=envelope_id,
            block_source="ASRP",
            block_reason=f"Agent ASRP state is {asrp_state}",
            asrp_state=asrp_state,
            remediation_required=True
        )


class DEFCONBlockedError(GovernanceBlockError):
    """ADR-016 DEFCON level blocks LLM calls."""

    def __init__(self, message: str, envelope_id: Optional[UUID] = None,
                 defcon_level: int = 1):
        super().__init__(
            message=message,
            envelope_id=envelope_id,
            block_source="DEFCON",
            block_reason=f"DEFCON level {defcon_level} blocks LLM operations",
            defcon_level=defcon_level,
            remediation_required=True
        )


class IKEABoundaryError(TelemetryError):
    """
    EC-022 IKEA knowledge boundary violation.

    Raised when IKEA detects a knowledge boundary violation.
    """

    def __init__(
        self,
        message: str,
        envelope_id: Optional[UUID] = None,
        violation_type: str = "GUESSED_WHEN_SHOULD_SEARCH",
        boundary_id: Optional[UUID] = None,
        parametric_confidence: Decimal = Decimal("0"),
        external_required: bool = True,
        cost_of_violation: Decimal = Decimal("0"),
        ikea_recommendation: str = ""
    ):
        super().__init__(message, envelope_id)
        self.violation_type = violation_type
        self.boundary_id = boundary_id
        self.parametric_confidence = parametric_confidence
        self.external_required = external_required
        self.cost_of_violation = cost_of_violation
        self.ikea_recommendation = ikea_recommendation
        self.recoverable = True

    def to_error_payload(self) -> Dict[str, Any]:
        return {
            "violation_type": self.violation_type,
            "boundary_id": str(self.boundary_id) if self.boundary_id else None,
            "parametric_confidence": str(self.parametric_confidence),
            "external_required": self.external_required,
            "cost_of_violation": str(self.cost_of_violation),
            "ikea_recommendation": self.ikea_recommendation
        }


class InForageTerminationError(TelemetryError):
    """
    EC-021 InForage diminishing returns termination.

    Raised when InForage determines further LLM calls have diminishing returns.
    """

    def __init__(
        self,
        message: str,
        envelope_id: Optional[UUID] = None,
        termination_reason: str = "DIMINISHING_RETURNS",
        scent_score: Decimal = Decimal("0"),
        cost_so_far: Decimal = Decimal("0"),
        expected_value_remaining: Decimal = Decimal("0"),
        paths_explored: int = 0,
        paths_abandoned: int = 0,
        foraging_efficiency: Decimal = Decimal("0")
    ):
        super().__init__(message, envelope_id)
        self.termination_reason = termination_reason
        self.scent_score = scent_score
        self.cost_so_far = cost_so_far
        self.expected_value_remaining = expected_value_remaining
        self.paths_explored = paths_explored
        self.paths_abandoned = paths_abandoned
        self.foraging_efficiency = foraging_efficiency
        self.recoverable = False

    def to_error_payload(self) -> Dict[str, Any]:
        return {
            "termination_reason": self.termination_reason,
            "scent_score": str(self.scent_score),
            "cost_so_far": str(self.cost_so_far),
            "expected_value_remaining": str(self.expected_value_remaining),
            "paths_explored": self.paths_explored,
            "paths_abandoned": self.paths_abandoned,
            "foraging_efficiency": str(self.foraging_efficiency)
        }


class CognitiveContextMissingError(TelemetryError):
    """
    ADR-021 cognitive context missing for multi-hop reasoning.

    Raised when cognitive_parent_id is required but not provided.
    """

    def __init__(
        self,
        message: str,
        envelope_id: Optional[UUID] = None,
        task_type: str = "",
        required_field: str = "cognitive_parent_id"
    ):
        super().__init__(message, envelope_id)
        self.task_type = task_type
        self.required_field = required_field
        self.recoverable = True

    def to_error_payload(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type,
            "required_field": self.required_field,
            "message": "Cognitive context required for multi-hop reasoning per ADR-021"
        }


class ProviderError(TelemetryError):
    """LLM provider returned an error."""

    def __init__(
        self,
        message: str,
        envelope_id: Optional[UUID] = None,
        http_status: Optional[int] = None,
        error_code: Optional[str] = None,
        rate_limited: bool = False,
        quota_remaining: Optional[int] = None
    ):
        super().__init__(message, envelope_id)
        self.http_status = http_status
        self.error_code = error_code
        self.rate_limited = rate_limited
        self.quota_remaining = quota_remaining
        self.recoverable = rate_limited or (http_status and http_status >= 500)
        if rate_limited:
            self.retry_after_seconds = 60

    def to_error_payload(self) -> Dict[str, Any]:
        return {
            "http_status": self.http_status,
            "error_code": self.error_code,
            "rate_limited": self.rate_limited,
            "quota_remaining": self.quota_remaining
        }


class TimeoutError(TelemetryError):
    """LLM call timed out."""

    def __init__(
        self,
        message: str,
        envelope_id: Optional[UUID] = None,
        timeout_ms: int = 60000,
        elapsed_ms: int = 0,
        provider: str = "",
        model: str = "",
        partial_response: Optional[str] = None
    ):
        super().__init__(message, envelope_id)
        self.timeout_ms = timeout_ms
        self.elapsed_ms = elapsed_ms
        self.provider = provider
        self.model = model
        self.partial_response = partial_response
        self.recoverable = True
        self.retry_after_seconds = 5

    def to_error_payload(self) -> Dict[str, Any]:
        return {
            "timeout_ms": self.timeout_ms,
            "elapsed_ms": self.elapsed_ms,
            "provider": self.provider,
            "model": self.model,
            "partial_response": self.partial_response[:500] if self.partial_response else None
        }
