"""
Trade Engine Data Models
=========================

Pydantic models for trade engine with comprehensive validation.

Design decisions (for ADR-051):
1. Pydantic over dataclasses: Runtime validation + JSON serialization
2. Immutability: Most models frozen to ensure audit trail integrity
3. Explicit validation: Business rules enforced at model level
4. No magic: All fields explicit, no computed properties in models
5. JSON-serializable: Ready for API/DB without custom encoders

All models are designed to be:
- Immutable (where appropriate)
- JSON-serializable
- Self-validating
- Documented
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, computed_field


class SignalSnapshot(BaseModel):
    """A trading signal at a point in time.

    Represents output from a signal generation system (e.g. HMM regime detector,
    momentum indicator, etc.). The signal_value indicates desired exposure direction
    and magnitude, while signal_confidence indicates reliability.

    Attributes:
        signal_id: Unique identifier for this signal instance
        asset_id: Asset identifier (e.g. "BTC-USD")
        timestamp: When the signal was generated
        signal_name: Signal generator name (e.g. "HMM_REGIME_MOMENTUM")
        signal_value: Desired exposure, normalized to [-1.0, 1.0]
                     -1.0 = strong short, 0.0 = neutral, +1.0 = strong long
        signal_confidence: Confidence in signal, [0.0, 1.0]
        regime_label: Optional market regime (e.g. "BULL", "BEAR", "SIDEWAYS")
        metadata: Additional signal-specific data (indicators, features, etc.)
    """

    signal_id: str
    asset_id: str
    timestamp: datetime
    signal_name: str
    signal_value: float
    signal_confidence: float
    regime_label: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("signal_value")
    @classmethod
    def validate_signal_value(cls, v: float) -> float:
        if not -1.0 <= v <= 1.0:
            raise ValueError(f"signal_value must be in [-1.0, 1.0], got {v}")
        return v

    @field_validator("signal_confidence")
    @classmethod
    def validate_signal_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"signal_confidence must be in [0.0, 1.0], got {v}")
        return v

    model_config = {"frozen": True}


class Position(BaseModel):
    """A position in a single asset.

    Represents a current holding in the portfolio. Quantity is always positive;
    the 'side' field indicates direction.

    Attributes:
        asset_id: Asset identifier
        quantity: Absolute quantity held (always > 0)
        avg_entry_price: Average entry price (> 0)
        side: Position direction (LONG or SHORT)
        unrealized_pnl: Optional cached unrealized PnL
        metadata: Additional position data (e.g. entry timestamp, strategy tag)
    """

    asset_id: str
    quantity: float
    avg_entry_price: float
    side: Literal["LONG", "SHORT"]
    unrealized_pnl: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"quantity must be > 0, got {v}")
        return v

    @field_validator("avg_entry_price")
    @classmethod
    def validate_avg_entry_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"avg_entry_price must be > 0, got {v}")
        return v

    model_config = {"frozen": True}


class RiskLimits(BaseModel):
    """Portfolio-level risk constraints.

    Hard limits that must not be violated. The engine will clamp position sizes
    to respect these limits.

    Attributes:
        max_gross_exposure: Maximum gross exposure as multiple of equity (e.g. 2.0 = 200%)
        max_single_asset_weight: Maximum single position as fraction of equity (e.g. 0.5 = 50%)
        max_leverage: Maximum leverage (gross / equity)
        max_position_size_notional: Maximum notional value for any single position
        max_daily_loss: Optional maximum daily loss (not enforced in V1)
        max_drawdown: Optional maximum drawdown (not enforced in V1)
    """

    max_gross_exposure: float = 2.0
    max_single_asset_weight: float = 0.5
    max_leverage: float = 2.0
    max_position_size_notional: float
    max_daily_loss: Optional[float] = None
    max_drawdown: Optional[float] = None

    @field_validator(
        "max_gross_exposure",
        "max_single_asset_weight",
        "max_leverage",
        "max_position_size_notional",
    )
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"Risk limit must be > 0, got {v}")
        return v

    model_config = {"frozen": True}


class RiskConfig(BaseModel):
    """Configuration for position sizing and risk management.

    Controls how aggressively the engine sizes positions given a signal.

    Attributes:
        base_bet_fraction: Base fraction of equity to risk per trade (e.g. 0.02 = 2%)
        volatility_scaling: Whether to scale position size by volatility (V1: placeholder)
        kelly_fraction_cap: Maximum Kelly fraction to apply (e.g. 0.25 = 25% of full Kelly)
        min_trade_notional: Minimum trade size (below this, don't trade)
        rounding_step: Optional rounding increment for quantity (e.g. 0.01 for 2 decimals)
    """

    base_bet_fraction: float = 0.02
    volatility_scaling: bool = True
    kelly_fraction_cap: float = 0.25
    min_trade_notional: float = 100.0
    rounding_step: Optional[float] = None

    @field_validator("base_bet_fraction", "kelly_fraction_cap")
    @classmethod
    def validate_fraction(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            raise ValueError(f"Fraction must be in (0, 1], got {v}")
        return v

    @field_validator("min_trade_notional")
    @classmethod
    def validate_min_trade_notional(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"min_trade_notional must be >= 0, got {v}")
        return v

    model_config = {"frozen": True}


class PortfolioState(BaseModel):
    """Complete portfolio state at a point in time.

    Represents all holdings and cash. Used as input to the trade engine.

    Attributes:
        timestamp: Portfolio snapshot time
        cash_balance: Available cash in base currency
        positions: List of current positions
        base_currency: Currency for cash and valuations (e.g. "USD")
        constraints: Risk limits for this portfolio
    """

    timestamp: datetime
    cash_balance: float
    positions: List[Position] = Field(default_factory=list)
    base_currency: str = "USD"
    constraints: RiskLimits

    def total_equity(self, prices: Dict[str, float]) -> float:
        """Compute total portfolio equity.

        Args:
            prices: Current prices for all assets

        Returns:
            Total equity (cash + position values)

        Raises:
            MissingPriceError: If price missing for any position
        """
        from trade_engine.exceptions import MissingPriceError

        equity = self.cash_balance

        for pos in self.positions:
            if pos.asset_id not in prices:
                raise MissingPriceError(
                    f"Missing price for {pos.asset_id} in equity calculation"
                )
            price = prices[pos.asset_id]
            notional = pos.quantity * price
            if pos.side == "LONG":
                equity += notional
            else:  # SHORT
                # For short: we have cash from sale, but owe the position
                # Simplified: equity impact is the P&L
                equity += pos.quantity * (pos.avg_entry_price - price)

        return equity

    def position_for_asset(self, asset_id: str) -> Optional[Position]:
        """Get position for a specific asset, if it exists."""
        for pos in self.positions:
            if pos.asset_id == asset_id:
                return pos
        return None

    model_config = {"frozen": False}  # Not frozen to allow modification


class ProposedTrade(BaseModel):
    """A proposed trade to execute.

    Generated by the trade engine to move from current to target position.

    Attributes:
        trade_id: Unique trade identifier (UUID)
        asset_id: Asset to trade
        side: Trade direction (BUY or SELL)
        quantity: Quantity to trade (always > 0)
        order_type: Order type (MARKET or LIMIT)
        limit_price: Limit price (required if order_type=LIMIT)
        time_in_force: Order duration (e.g. "GTC", "IOC", "FOK")
        reason: Human-readable explanation for this trade
        source_signal_id: ID of signal that generated this trade
        created_at: When the trade was proposed
        metadata: Additional trade data
    """

    trade_id: str = Field(default_factory=lambda: str(uuid4()))
    asset_id: str
    side: Literal["BUY", "SELL"]
    quantity: float
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    limit_price: Optional[float] = None
    time_in_force: Optional[str] = "GTC"
    reason: str
    source_signal_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"quantity must be > 0, got {v}")
        return v

    def model_post_init(self, __context):
        """Validate limit_price is set if order_type is LIMIT."""
        if self.order_type == "LIMIT" and self.limit_price is None:
            raise ValueError("limit_price must be set when order_type=LIMIT")

    model_config = {"frozen": True}


class TargetPosition(BaseModel):
    """Desired target position for an asset.

    Intermediate representation between signal and trades.

    Attributes:
        asset_id: Asset identifier
        target_quantity: Desired final quantity (can be 0 to close, negative not allowed)
        rationale: Explanation for this target
        metadata: Additional context
    """

    asset_id: str
    target_quantity: float  # Can be 0 (exit position)
    rationale: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("target_quantity")
    @classmethod
    def validate_target_quantity(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"target_quantity must be >= 0, got {v}")
        return v

    model_config = {"frozen": True}


class RiskMetrics(BaseModel):
    """Portfolio-level risk metrics.

    Computed by the trade engine after determining proposed trades.

    Attributes:
        gross_exposure: Sum of absolute notional values
        net_exposure: Signed sum of notional values
        largest_position_weight: Largest position as fraction of equity
        leverage: Gross exposure / equity
        value_at_risk: Optional VaR estimate (not computed in V1)
        notes: Optional explanatory notes
    """

    gross_exposure: float
    net_exposure: float
    largest_position_weight: float
    leverage: float
    value_at_risk: Optional[float] = None
    notes: Optional[str] = None

    model_config = {"frozen": True}


class PnLMetrics(BaseModel):
    """Portfolio-level P&L metrics.

    Attributes:
        timestamp: Metrics calculation time
        realized_pnl: Realized P&L from closed trades (V1: always 0.0)
        unrealized_pnl: Unrealized P&L from open positions
        total_pnl: realized + unrealized
        pnl_by_asset: Per-asset P&L breakdown
    """

    timestamp: datetime
    realized_pnl: float = 0.0  # V1: simplified, no trade history
    unrealized_pnl: float
    total_pnl: float
    pnl_by_asset: Dict[str, float] = Field(default_factory=dict)

    model_config = {"frozen": True}
