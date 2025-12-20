"""
FjordHQ Trade Engine
====================

An institutional-grade, deterministic trade engine for generating trades from signals.

This package provides pure, auditable functions for:
- Interpreting trading signals
- Computing risk-aware target positions
- Generating proposed trades
- Computing PnL and risk metrics

Design Principles (for ADR-051):
- Pure functions: No side effects, explicit inputs/outputs
- DB-agnostic: All I/O via in-memory data structures
- Strong typing: Pydantic models with runtime validation
- Deterministic: Same inputs always produce same outputs
- Fail-fast: Explicit exceptions for all error conditions

Entry Point:
    run_trade_engine() - Main orchestration function

Key Modules:
    models - Pydantic data models
    signal_interpreter - Signal → exposure mapping
    position_sizing - Risk-aware position sizing
    trade_generator - Target → proposed trades
    pnl - PnL computation
    risk - Risk metrics computation
    exceptions - Domain-specific exceptions
"""

from trade_engine.models import (
    SignalSnapshot,
    Position,
    PortfolioState,
    RiskLimits,
    RiskConfig,
    ProposedTrade,
    TargetPosition,
    RiskMetrics,
    PnLMetrics,
)
from trade_engine.engine import run_trade_engine
from trade_engine.exceptions import (
    TradeEngineError,
    ValidationError,
    RiskLimitViolation,
    MissingPriceError,
    InsufficientCapitalError,
    ConfigurationError,
)

__version__ = "1.0.0"
__all__ = [
    # Main entry point
    "run_trade_engine",
    # Models
    "SignalSnapshot",
    "Position",
    "PortfolioState",
    "RiskLimits",
    "RiskConfig",
    "ProposedTrade",
    "TargetPosition",
    "RiskMetrics",
    "PnLMetrics",
    # Exceptions
    "TradeEngineError",
    "ValidationError",
    "RiskLimitViolation",
    "MissingPriceError",
    "InsufficientCapitalError",
    "ConfigurationError",
]
