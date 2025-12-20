"""
Trade Engine Exceptions
========================

Domain-specific exceptions for explicit error handling.

All exceptions inherit from TradeEngineError for easy catching.
Each exception type represents a specific failure mode that calling
code may want to handle differently.
"""


class TradeEngineError(Exception):
    """Base exception for all trade engine errors."""
    pass


class ValidationError(TradeEngineError):
    """Raised when input data fails validation.

    Examples:
    - Signal value outside [-1.0, 1.0] range
    - Negative price
    - Invalid position side
    """
    pass


class RiskLimitViolation(TradeEngineError):
    """Raised when an operation would violate configured risk limits.

    Examples:
    - Position would exceed max_single_asset_weight
    - Leverage would exceed max_leverage
    - Notional would exceed max_position_size_notional

    Note: In normal operation, the engine clamps positions to limits
    rather than raising. This exception indicates a configuration error
    or pre-condition violation.
    """
    pass


class MissingPriceError(TradeEngineError):
    """Raised when required price data is not available.

    Examples:
    - Computing PnL but no price for held asset
    - Sizing position but no current price

    This indicates a data pipeline issue that must be resolved
    before the engine can proceed.
    """
    pass


class InsufficientCapitalError(TradeEngineError):
    """Raised when portfolio lacks sufficient capital for an operation.

    Examples:
    - Negative equity
    - Cash balance insufficient for margin requirements

    Note: V1 simplified - no explicit margin calculation yet.
    """
    pass


class ConfigurationError(TradeEngineError):
    """Raised when configuration is invalid or inconsistent.

    Examples:
    - base_bet_fraction <= 0 or > 1
    - max_leverage <= 0
    - Conflicting risk limit settings
    """
    pass


# ============================================================
# CONSTITUTIONAL GUARD EXCEPTIONS (ADR-008, ADR-012, ADR-013, ADR-016)
# ============================================================
# Added per CEO Remediation Order — CV-001, CV-002, HV-001, HV-002
# ============================================================


class ConstitutionalError(TradeEngineError):
    """Raised when a constitutional violation is detected.

    This is the base class for all constitutional violations.
    ADR Reference: ADR-013 (One-Source-Truth)

    Examples:
    - Signal from non-canonical source
    - Mandate without proper authorization
    """
    pass


class InvalidSignatureError(ConstitutionalError):
    """Raised when Ed25519 signature validation fails.

    ADR Reference: ADR-008 (Cryptographic Key Management)

    Examples:
    - Signature does not match payload
    - Signature uses wrong key
    - Corrupted signature data
    """
    pass


class MissingSignatureError(ConstitutionalError):
    """Raised when required Ed25519 signature is missing.

    ADR Reference: ADR-008 (Cryptographic Key Management)

    Examples:
    - Mandate envelope lacks signature field
    - Empty signature provided
    """
    pass


class ExecutionDeniedError(ConstitutionalError):
    """Raised when ExecutionGuard denies execution.

    ADR Reference: ADR-012 (Economic Safety)

    Examples:
    - No execution authority
    - Failed mandate source validation
    - DEFCON level too high
    - Invalid lineage hash
    """

    def __init__(self, reason: str, guard_step: str = None):
        self.reason = reason
        self.guard_step = guard_step
        super().__init__(f"Execution denied: {reason}" + (f" (at {guard_step})" if guard_step else ""))


class DefconBlockError(ConstitutionalError):
    """Raised when DEFCON level blocks execution.

    ADR Reference: ADR-016 (DEFCON & Circuit Breaker Protocol)

    Execution is blocked when defcon_level > 3.

    DEFCON Levels:
    - DEFCON-5: Normal operations
    - DEFCON-4: Elevated caution
    - DEFCON-3: High alert (last level allowing execution)
    - DEFCON-2: Severe — EXECUTION BLOCKED
    - DEFCON-1: Critical — ALL OPERATIONS HALTED
    """

    def __init__(self, defcon_level: int, reason: str = None):
        self.defcon_level = defcon_level
        self.reason = reason or f"DEFCON-{defcon_level} blocks execution"
        super().__init__(f"ADR-016 Safety Lock: {self.reason}")


class MandateSourceError(ConstitutionalError):
    """Raised when signal/mandate source is not IoS-008.

    ADR Reference: ADR-013 (One-Source-Truth)

    Hard rule: Only IoS-008 Runtime Decision Engine may issue
    execution mandates. All other sources are rejected.
    """

    def __init__(self, source_module: str):
        self.source_module = source_module
        super().__init__(f"Only IoS-008 mandates accepted. Received from: {source_module}")
