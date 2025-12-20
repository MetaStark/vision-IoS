"""
Experiment configuration schemas for Alpha Lab.

Defines the structure of experiments, parameter sweeps, and
backtesting configurations.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Dict, List, Optional, Any
from datetime import datetime


class BacktestConfig(BaseModel):
    """Configuration for a backtest run."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    start_date: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Start date in YYYY-MM-DD format"
    )
    end_date: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="End date in YYYY-MM-DD format"
    )
    initial_capital: float = Field(
        ...,
        gt=0,
        description="Starting capital for the backtest"
    )
    currency: str = Field(
        default="USDT",
        description="Base currency for the backtest"
    )
    commission_rate: float = Field(
        default=0.001,
        ge=0,
        le=1,
        description="Commission rate as decimal (e.g., 0.001 = 0.1%)"
    )
    slippage_bps: float = Field(
        default=5.0,
        ge=0,
        description="Slippage in basis points"
    )
    data_frequency: str = Field(
        default="1h",
        pattern=r'^(\d+[mhDWM]|tick)$',
        description="Frequency of price data (e.g., 1m, 1h, 1D)"
    )
    allow_fractional_shares: bool = Field(
        default=True,
        description="Whether to allow fractional position sizes"
    )

    @field_validator('end_date')
    @classmethod
    def validate_date_order(cls, v: str, info) -> str:
        """Ensure end_date is after start_date."""
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError("end_date must be after start_date")
        return v


class ExecutionConfig(BaseModel):
    """Configuration for experiment execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    parallel: bool = Field(
        default=False,
        description="Whether to run parameter combinations in parallel"
    )
    max_workers: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of parallel workers (None = CPU count)"
    )
    random_seed: int = Field(
        default=42,
        description="Random seed for reproducibility"
    )
    verbose: bool = Field(
        default=True,
        description="Whether to print progress information"
    )
    fail_fast: bool = Field(
        default=False,
        description="Whether to stop on first failure"
    )


class MetricsConfig(BaseModel):
    """Configuration for metrics calculation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    risk_free_rate: float = Field(
        default=0.02,
        ge=0,
        le=1,
        description="Annual risk-free rate for Sharpe calculation"
    )
    benchmark_symbol: Optional[str] = Field(
        default=None,
        description="Symbol to use as benchmark for comparison"
    )
    confidence_level: float = Field(
        default=0.95,
        gt=0,
        lt=1,
        description="Confidence level for statistical tests"
    )
    bootstrap_iterations: int = Field(
        default=10000,
        ge=100,
        description="Number of bootstrap iterations"
    )
    block_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Block size for block bootstrap (None = auto)"
    )


class ParameterGrid(BaseModel):
    """Defines parameter sweep space for experiments."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    parameters: Dict[str, List[Any]] = Field(
        ...,
        description="Dictionary mapping parameter names to lists of values"
    )

    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
        """Ensure all parameter lists have at least one value."""
        if not v:
            raise ValueError("Parameter grid must have at least one parameter")
        for param_name, param_values in v.items():
            if not param_values:
                raise ValueError(f"Parameter '{param_name}' must have at least one value")
            if not isinstance(param_values, list):
                raise ValueError(f"Parameter '{param_name}' values must be a list")
        return v

    def get_combinations_count(self) -> int:
        """Calculate total number of parameter combinations."""
        count = 1
        for values in self.parameters.values():
            count *= len(values)
        return count


class ExperimentConfig(BaseModel):
    """Complete configuration for a parameter sweep experiment."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    experiment_id: str = Field(
        ...,
        min_length=1,
        pattern=r'^[a-z0-9_]+$',
        description="Unique experiment identifier"
    )
    experiment_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable experiment name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed experiment description"
    )
    strategy_template: str = Field(
        ...,
        description="Strategy ID to use as template"
    )
    parameter_grid: Dict[str, List[Any]] = Field(
        ...,
        description="Parameter grid for sweep (param_name -> [values])"
    )
    backtest_config: BacktestConfig = Field(
        ...,
        description="Backtest configuration"
    )
    execution_config: ExecutionConfig = Field(
        default_factory=ExecutionConfig,
        description="Execution configuration"
    )
    metrics_config: MetricsConfig = Field(
        default_factory=MetricsConfig,
        description="Metrics configuration"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When experiment was created"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization"
    )

    @field_validator('parameter_grid')
    @classmethod
    def validate_parameter_grid(cls, v: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
        """Validate parameter grid structure."""
        if not v:
            raise ValueError("Parameter grid cannot be empty")
        for param_name, param_values in v.items():
            if not isinstance(param_values, list):
                raise ValueError(f"Values for '{param_name}' must be a list")
            if len(param_values) == 0:
                raise ValueError(f"Parameter '{param_name}' must have at least one value")
        return v


class PortfolioConfig(BaseModel):
    """Configuration for multi-strategy portfolio."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    portfolio_id: str = Field(
        ...,
        pattern=r'^[a-z0-9_]+$',
        description="Unique portfolio identifier"
    )
    portfolio_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable portfolio name"
    )
    description: Optional[str] = Field(
        default=None,
        description="Portfolio description"
    )
    strategies: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="List of {strategy_id, allocation, backtest_id}"
    )
    rebalance_frequency: Optional[str] = Field(
        default=None,
        description="Portfolio rebalance frequency (None = buy-and-hold)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When portfolio was created"
    )

    @field_validator('strategies')
    @classmethod
    def validate_strategies(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate strategy allocations sum to 1.0."""
        if not v:
            raise ValueError("Portfolio must have at least one strategy")

        total_allocation = sum(s.get('allocation', 0) for s in v)
        if not (0.99 <= total_allocation <= 1.01):  # Allow small floating point errors
            raise ValueError(f"Strategy allocations must sum to 1.0 (got {total_allocation})")

        for i, strategy in enumerate(v):
            if 'strategy_id' not in strategy:
                raise ValueError(f"Strategy {i} missing 'strategy_id'")
            if 'allocation' not in strategy:
                raise ValueError(f"Strategy {i} missing 'allocation'")
            if not (0 <= strategy['allocation'] <= 1):
                raise ValueError(f"Strategy {i} allocation must be between 0 and 1")

        return v
