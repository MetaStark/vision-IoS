"""
Strategy definition schemas for Alpha Lab.

Defines the structure of trading strategies that can be backtested
and experimented with in the Alpha Lab framework.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class StrategyType(str, Enum):
    """Classification of strategy types."""
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    ARBITRAGE = "arbitrage"
    STATISTICAL = "statistical"
    CUSTOM = "custom"


class RebalanceFrequency(str, Enum):
    """Supported rebalance frequencies."""
    TICK = "tick"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1D"
    WEEK_1 = "1W"
    MONTH_1 = "1M"


class PositionSizingMethod(str, Enum):
    """Position sizing methodologies."""
    FIXED_PCT = "fixed_pct"
    FIXED_UNITS = "fixed_units"
    KELLY = "kelly"
    VOLATILITY_TARGET = "volatility_target"
    RISK_PARITY = "risk_parity"


class TradeEngineConfig(BaseModel):
    """Configuration for the trade engine (black box)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    regime_enabled: bool = Field(
        default=False,
        description="Whether regime detection is enabled"
    )
    max_positions: int = Field(
        default=10,
        ge=1,
        description="Maximum number of concurrent positions"
    )
    position_sizing_method: PositionSizingMethod = Field(
        default=PositionSizingMethod.FIXED_PCT,
        description="Method for sizing positions"
    )
    risk_limit_pct: float = Field(
        default=0.02,
        ge=0,
        le=1,
        description="Risk limit as percentage of equity per trade"
    )
    additional_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional trade engine specific parameters"
    )


class StrategyDefinition(BaseModel):
    """Complete definition of a trading strategy.

    This schema defines all parameters needed to run a strategy
    through the Alpha Lab backtesting and experimentation framework.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    strategy_id: str = Field(
        ...,
        min_length=1,
        pattern=r'^[a-z0-9_]+$',
        description="Unique identifier for the strategy (lowercase, underscores)"
    )
    strategy_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable strategy name"
    )
    strategy_type: StrategyType = Field(
        ...,
        description="Classification of strategy type"
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Detailed description of strategy logic"
    )
    parameters: Dict[str, Any] = Field(
        ...,
        description="Strategy-specific parameters (e.g., MA periods, thresholds)"
    )
    universe: List[str] = Field(
        ...,
        min_length=1,
        description="List of symbols/instruments to trade"
    )
    rebalance_frequency: RebalanceFrequency = Field(
        ...,
        description="How often the strategy evaluates signals"
    )
    trade_engine_config: TradeEngineConfig = Field(
        ...,
        description="Configuration for the trade execution engine"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this strategy definition was created"
    )
    version: str = Field(
        default="1.0.0",
        pattern=r'^\d+\.\d+\.\d+$',
        description="Semantic version of strategy"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization and search"
    )
    author: Optional[str] = Field(
        default=None,
        description="Strategy author/creator"
    )

    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure parameters dict is not empty."""
        if not v:
            raise ValueError("Strategy must have at least one parameter")
        return v


class ProposedTrade(BaseModel):
    """A trade proposed by the trade engine.

    This represents the black-box output from the trade engine
    before execution simulation.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., pattern=r'^(buy|sell)$', description="Trade side")
    quantity: float = Field(..., gt=0, description="Quantity to trade")
    order_type: str = Field(
        default="market",
        description="Order type (market, limit, etc.)"
    )
    limit_price: Optional[float] = Field(
        default=None,
        description="Limit price if order_type is limit"
    )
    stop_loss: Optional[float] = Field(
        default=None,
        description="Stop loss price"
    )
    take_profit: Optional[float] = Field(
        default=None,
        description="Take profit price"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When trade was proposed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional trade metadata"
    )


class ExecutedTrade(BaseModel):
    """A trade that has been executed (after simulation).

    This represents the black-box output from the execution simulator.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    trade_id: str = Field(..., description="Unique trade identifier")
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., pattern=r'^(buy|sell)$', description="Trade side")
    quantity: float = Field(..., gt=0, description="Executed quantity")
    price: float = Field(..., gt=0, description="Execution price")
    commission: float = Field(..., ge=0, description="Commission paid")
    slippage: float = Field(..., description="Slippage cost (can be negative)")
    timestamp: datetime = Field(..., description="Execution timestamp")
    fill_rate: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Fraction of order filled"
    )
    fill_time_ms: float = Field(
        default=0.0,
        ge=0,
        description="Time to fill in milliseconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata"
    )
