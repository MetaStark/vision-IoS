# Trade Engine

**Version:** 1.0.0
**Status:** Production-ready
**For:** FjordHQ Market System

## Overview

The Trade Engine is an institutional-grade, deterministic system for generating trades from signals. It provides pure, auditable functions for signal interpretation, risk-aware position sizing, and trade generation.

## Design Principles

1. **Pure Functions**: No side effects. All I/O via explicit parameters and return values.
2. **Deterministic**: Same inputs always produce same outputs.
3. **DB-Agnostic**: No SQL, no direct database access, no HTTP calls.
4. **Strong Typing**: Pydantic models with runtime validation.
5. **Fail-Fast**: Explicit exceptions for all error conditions.
6. **Auditable**: Every decision is traceable and explainable.

## Core Concepts

### Signal → Target → Trade Flow

```
SignalSnapshot + PortfolioState + RiskConfig
    ↓ (interpret_signal)
Desired Exposure [-1, 1]
    ↓ (derive_target_position)
TargetPosition
    ↓ (generate_proposed_trades)
ProposedTrade[]
```

### Risk Management

The engine enforces multiple layers of risk controls:

- **Kelly Criterion**: Position sizing based on signal strength with fractional cap (default 25%)
- **Single Asset Weight Limit**: Max % of equity per position (e.g. 50%)
- **Leverage Limit**: Max gross exposure / equity (e.g. 2.0x)
- **Notional Limit**: Max absolute position size

All limits are enforced at position sizing time, ensuring no trade violates risk constraints.

## Installation

```bash
# The package is part of the fhq-market-system monorepo
# No separate installation required

# Dependencies (ensure these are in requirements.txt):
pip install pydantic>=2.0.0
```

## Quick Start

```python
from datetime import datetime
from trade_engine import (
    run_trade_engine,
    SignalSnapshot,
    PortfolioState,
    RiskLimits,
    RiskConfig,
)

# 1. Define portfolio state
portfolio = PortfolioState(
    timestamp=datetime.utcnow(),
    cash_balance=100000.0,
    positions=[],
    constraints=RiskLimits(
        max_gross_exposure=2.0,
        max_single_asset_weight=0.5,
        max_leverage=2.0,
        max_position_size_notional=100000.0,
    ),
)

# 2. Create signals
signals = [
    SignalSnapshot(
        signal_id="signal_001",
        asset_id="BTC-USD",
        timestamp=datetime.utcnow(),
        signal_name="HMM_REGIME_MOMENTUM",
        signal_value=0.8,  # Strong long signal
        signal_confidence=0.9,  # High confidence
    )
]

# 3. Provide current prices
prices = {"BTC-USD": 50000.0}

# 4. Configure risk parameters
config = RiskConfig(
    base_bet_fraction=0.02,
    kelly_fraction_cap=0.25,
    min_trade_notional=100.0,
)

# 5. Run the engine
trades, risk_metrics, pnl_metrics = run_trade_engine(
    signals=signals,
    portfolio=portfolio,
    prices=prices,
    risk_limits=portfolio.constraints,
    config=config,
)

# 6. Process results
for trade in trades:
    print(f"{trade.side} {trade.quantity:.4f} {trade.asset_id} @ {trade.order_type}")
    print(f"Reason: {trade.reason}")

print(f"Portfolio Leverage: {risk_metrics.leverage:.2f}x")
print(f"Unrealized P&L: ${pnl_metrics.unrealized_pnl:,.2f}")
```

## API Reference

### Main Entry Point

#### `run_trade_engine()`

```python
def run_trade_engine(
    signals: List[SignalSnapshot],
    portfolio: PortfolioState,
    prices: Dict[str, float],
    risk_limits: RiskLimits,
    config: RiskConfig,
    logger: Optional[logging.Logger] = None,
) -> Tuple[List[ProposedTrade], RiskMetrics, PnLMetrics]:
```

**Parameters:**
- `signals`: List of signals to process (one per asset typically)
- `portfolio`: Current portfolio state
- `prices`: Current market prices (dict: asset_id → price)
- `risk_limits`: Risk constraint configuration
- `config`: Risk sizing configuration
- `logger`: Optional logger for diagnostics

**Returns:**
- `List[ProposedTrade]`: Trades to execute (may be empty)
- `RiskMetrics`: Current portfolio risk metrics
- `PnLMetrics`: Current portfolio P&L metrics

**Raises:**
- `MissingPriceError`: If price missing for required asset
- `InsufficientCapitalError`: If portfolio equity <= 0
- `ValidationError`: If input data fails validation

### Key Data Models

#### SignalSnapshot

```python
SignalSnapshot(
    signal_id: str,
    asset_id: str,
    timestamp: datetime,
    signal_name: str,
    signal_value: float,  # [-1.0, 1.0]
    signal_confidence: float,  # [0.0, 1.0]
    regime_label: Optional[str] = None,
    metadata: Dict[str, Any] = {},
)
```

#### PortfolioState

```python
PortfolioState(
    timestamp: datetime,
    cash_balance: float,
    positions: List[Position],
    base_currency: str = "USD",
    constraints: RiskLimits,
)
```

#### RiskLimits

```python
RiskLimits(
    max_gross_exposure: float = 2.0,
    max_single_asset_weight: float = 0.5,
    max_leverage: float = 2.0,
    max_position_size_notional: float,
)
```

#### RiskConfig

```python
RiskConfig(
    base_bet_fraction: float = 0.02,
    kelly_fraction_cap: float = 0.25,
    min_trade_notional: float = 100.0,
    rounding_step: Optional[float] = None,
)
```

## Architecture

### Module Structure

```
trade_engine/
├── __init__.py           # Public API
├── models.py             # Pydantic data models
├── exceptions.py         # Domain-specific exceptions
├── signal_interpreter.py # Signal → exposure
├── position_sizing.py    # Risk-aware sizing
├── trade_generator.py    # Target → trades
├── pnl.py               # P&L computation
├── risk.py              # Risk metrics
└── engine.py            # Main orchestration
```

### Data Flow

```
┌─────────────────┐
│ SignalSnapshot  │ ←── Input from signal generation system
└────────┬────────┘
         ↓
┌─────────────────┐
│ interpret_signal│ ←── Applies confidence weighting
└────────┬────────┘
         ↓
┌──────────────────────┐
│ derive_target_position│ ←── Kelly sizing + risk limits
└────────┬─────────────┘
         ↓
┌──────────────────────┐
│generate_proposed_trades│ ←── Delta vs current position
└────────┬─────────────┘
         ↓
┌─────────────────┐
│ ProposedTrade[] │ ←── Output for execution
└─────────────────┘
```

## Testing

Run tests with pytest:

```bash
# All trade engine tests
pytest tests/test_trade_engine/ -v

# Specific test modules
pytest tests/test_trade_engine/test_models.py -v
pytest tests/test_trade_engine/test_position_sizing.py -v

# Integration test
pytest tests/test_trade_engine/test_engine_integration.py -v

# With coverage
pytest tests/test_trade_engine/ --cov=trade_engine --cov-report=html
```

## Error Handling

The engine uses explicit exception types for different failure modes:

- **`ValidationError`**: Invalid input data (e.g. signal_value > 1.0)
- **`MissingPriceError`**: Required price data not available
- **`InsufficientCapitalError`**: Portfolio equity <= 0
- **`RiskLimitViolation`**: Operation would violate risk limits
- **`ConfigurationError`**: Invalid configuration

All exceptions inherit from `TradeEngineError` for easy catching.

## V1 Limitations

1. **Realized P&L**: Always returns 0.0 (requires trade history tracking)
2. **Short Positions**: Limited support (V1 focuses on long-only)
3. **Regime Adjustments**: Placeholder only (no regime-specific scaling)
4. **VaR**: Not computed (placeholder in RiskMetrics)
5. **Volatility Scaling**: Not implemented (flag exists for V2)

## For STIG (Integration)

### Database Wiring

```python
# Pseudocode for STIG to wire this to DB:

def scheduled_trade_generation():
    # 1. Fetch latest signals from DB
    signals = fetch_signals_from_db()

    # 2. Load current portfolio state
    portfolio = load_portfolio_from_db()

    # 3. Get current prices (from market data gateway)
    prices = fetch_latest_prices()

    # 4. Load risk configuration
    risk_limits = load_risk_limits_from_db()
    config = load_risk_config_from_db()

    # 5. Run engine (pure function, no side effects!)
    trades, risk_metrics, pnl_metrics = run_trade_engine(
        signals, portfolio, prices, risk_limits, config
    )

    # 6. Persist results
    save_proposed_trades_to_db(trades)
    save_risk_metrics_to_db(risk_metrics)
    save_pnl_metrics_to_db(pnl_metrics)

    # 7. Log event
    log_system_event("TRADE_GENERATION_COMPLETE", {
        "num_trades": len(trades),
        "leverage": risk_metrics.leverage,
    })
```

### API Exposure

```python
# For API endpoints:

@app.post("/api/v1/simulate-trades")
def simulate_trades(request: TradeSimulationRequest):
    """Simulate trades without persisting."""
    trades, risk_metrics, pnl_metrics = run_trade_engine(
        signals=request.signals,
        portfolio=request.portfolio,
        prices=request.prices,
        risk_limits=request.risk_limits,
        config=request.config,
    )
    return {
        "trades": [t.model_dump() for t in trades],
        "risk_metrics": risk_metrics.model_dump(),
        "pnl_metrics": pnl_metrics.model_dump(),
    }
```

## ADR-051 Notes

Key architectural decisions for documentation:

1. **Pydantic v2**: Chosen for runtime validation, JSON serialization, and IDE support
2. **Pure Functions**: Testability and audit trail integrity
3. **Explicit Price Passing**: Ensures DB-agnostic design
4. **Conservative Kelly**: 25% fractional cap to prevent over-leveraging
5. **Immutable Models**: Most models frozen to prevent accidental mutation
6. **No Smart Defaults**: Risk limits must be explicit

## Support

For questions or issues:
- Internal: Contact core code team
- Docs: See main project README
- Issues: GitHub issue tracker

---

**Built for:** FjordHQ Market System
**Standards:** BCBS 239, ISO 8000, GIPS/SEC best practices
**Last Updated:** 2025-11-18
