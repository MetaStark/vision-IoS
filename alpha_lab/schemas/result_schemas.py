"""
Result schemas for Alpha Lab.

Defines the structure of backtest results, performance metrics,
and experiment outcomes.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import datetime


class PerformanceMetrics(BaseModel):
    """Comprehensive performance metrics for a backtest."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Returns
    total_return: float = Field(..., description="Total return over period")
    cagr: float = Field(..., description="Compound annual growth rate")

    # Risk-adjusted returns
    sharpe_ratio: float = Field(..., description="Sharpe ratio (annualized)")
    sortino_ratio: float = Field(..., description="Sortino ratio (annualized)")
    calmar_ratio: float = Field(..., description="Calmar ratio (CAGR / |max_dd|)")

    # Risk metrics
    max_drawdown: float = Field(..., description="Maximum drawdown (negative)")
    max_drawdown_duration_days: int = Field(
        ...,
        description="Maximum drawdown duration in days"
    )
    volatility_annual: float = Field(..., description="Annualized volatility")
    downside_deviation: float = Field(
        ...,
        description="Downside deviation (annualized)"
    )

    # Trading statistics
    total_trades: int = Field(..., ge=0, description="Total number of trades")
    win_rate: float = Field(..., ge=0, le=1, description="Win rate (0-1)")
    profit_factor: float = Field(
        ...,
        ge=0,
        description="Gross profit / gross loss"
    )
    avg_trade_pnl: float = Field(..., description="Average PnL per trade")
    avg_trade_pnl_pct: float = Field(
        ...,
        description="Average PnL per trade as percentage"
    )
    avg_trade_duration_hours: float = Field(
        ...,
        ge=0,
        description="Average trade duration in hours"
    )

    # Turnover and costs
    turnover_annual: float = Field(..., ge=0, description="Annual turnover")
    total_commission: float = Field(..., ge=0, description="Total commission paid")
    total_slippage: float = Field(..., description="Total slippage cost")

    # Advanced metrics
    best_trade_pnl: float = Field(..., description="Best single trade PnL")
    worst_trade_pnl: float = Field(..., description="Worst single trade PnL")
    max_consecutive_wins: int = Field(..., ge=0, description="Max winning streak")
    max_consecutive_losses: int = Field(..., ge=0, description="Max losing streak")
    avg_winner_pnl: float = Field(..., description="Average winning trade PnL")
    avg_loser_pnl: float = Field(..., description="Average losing trade PnL")

    # Time-based metrics
    time_in_market_pct: float = Field(
        ...,
        ge=0,
        le=1,
        description="Percentage of time with open positions"
    )
    time_underwater_pct: float = Field(
        ...,
        ge=0,
        le=1,
        description="Percentage of time in drawdown"
    )


class EquityPoint(BaseModel):
    """Single point in the equity curve."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    equity: float = Field(..., gt=0, description="Total equity value")
    drawdown: float = Field(..., le=0, description="Drawdown (negative)")
    daily_return: float = Field(default=0.0, description="Daily return")
    cash: float = Field(default=0.0, description="Cash balance")
    positions_value: float = Field(default=0.0, description="Value of positions")


class TradeRecord(BaseModel):
    """Record of a single trade."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    trade_id: str = Field(..., description="Unique trade identifier")
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., pattern=r'^(buy|sell|long|short)$', description="Trade side")

    # Entry
    entry_date: str = Field(..., description="Entry date (YYYY-MM-DD HH:MM:SS)")
    entry_price: float = Field(..., gt=0, description="Entry price")
    quantity: float = Field(..., gt=0, description="Quantity traded")

    # Exit
    exit_date: str = Field(..., description="Exit date (YYYY-MM-DD HH:MM:SS)")
    exit_price: float = Field(..., gt=0, description="Exit price")

    # PnL
    pnl: float = Field(..., description="Profit/loss in currency")
    pnl_pct: float = Field(..., description="Profit/loss as percentage")

    # Costs
    commission: float = Field(..., ge=0, description="Commission paid")
    slippage: float = Field(..., description="Slippage cost")

    # Duration
    duration_hours: float = Field(..., ge=0, description="Trade duration in hours")

    # Metadata
    entry_reason: Optional[str] = Field(default=None, description="Entry signal reason")
    exit_reason: Optional[str] = Field(default=None, description="Exit signal reason")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional trade metadata"
    )


class ExecutionStats(BaseModel):
    """Statistics about trade execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_slippage_cost: float = Field(..., description="Total slippage cost")
    total_commission: float = Field(..., ge=0, description="Total commission paid")
    avg_slippage_bps: float = Field(..., description="Average slippage in bps")
    fill_rate: float = Field(
        ...,
        ge=0,
        le=1,
        description="Average fill rate (1.0 = full fills)"
    )
    avg_fill_time_ms: float = Field(
        ...,
        ge=0,
        description="Average time to fill in milliseconds"
    )
    slippage_as_pct_of_pnl: Optional[float] = Field(
        default=None,
        description="Slippage cost as % of gross PnL"
    )
    commission_as_pct_of_pnl: Optional[float] = Field(
        default=None,
        description="Commission as % of gross PnL"
    )


class BacktestResult(BaseModel):
    """Complete result of a backtest run."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    backtest_id: str = Field(..., description="Unique backtest identifier")
    strategy_id: str = Field(..., description="Strategy that was backtested")
    parameters: Dict[str, Any] = Field(
        ...,
        description="Strategy parameters used"
    )

    # Configuration
    backtest_config: Dict[str, Any] = Field(
        ...,
        description="Backtest configuration used"
    )

    # Results
    results: PerformanceMetrics = Field(..., description="Performance metrics")
    equity_curve: List[EquityPoint] = Field(
        ...,
        description="Equity curve time series"
    )
    trades: List[TradeRecord] = Field(
        ...,
        description="List of all trades executed"
    )
    execution_stats: ExecutionStats = Field(
        ...,
        description="Execution statistics"
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this result was generated"
    )
    computation_time_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Time taken to run backtest"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if backtest failed"
    )


class ExperimentRun(BaseModel):
    """Single run within an experiment (one parameter combination)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str = Field(..., description="Unique run identifier")
    parameters: Dict[str, Any] = Field(..., description="Parameters for this run")
    backtest_result: Optional[BacktestResult] = Field(
        default=None,
        description="Backtest result (None if failed)"
    )
    success: bool = Field(..., description="Whether run succeeded")
    error: Optional[str] = Field(default=None, description="Error if failed")
    computation_time_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Computation time"
    )


class ExperimentResult(BaseModel):
    """Complete result of an experiment (parameter sweep)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    experiment_id: str = Field(..., description="Experiment identifier")
    experiment_name: str = Field(..., description="Experiment name")
    strategy_template: str = Field(..., description="Strategy template used")

    # Runs
    runs: List[ExperimentRun] = Field(..., description="All experiment runs")
    total_runs: int = Field(..., ge=0, description="Total number of runs")
    successful_runs: int = Field(..., ge=0, description="Number of successful runs")
    failed_runs: int = Field(..., ge=0, description="Number of failed runs")

    # Best/worst performers
    best_run_by_sharpe: Optional[str] = Field(
        default=None,
        description="Run ID with best Sharpe ratio"
    )
    worst_run_by_sharpe: Optional[str] = Field(
        default=None,
        description="Run ID with worst Sharpe ratio"
    )
    best_run_by_return: Optional[str] = Field(
        default=None,
        description="Run ID with best total return"
    )

    # Summary statistics
    avg_sharpe: Optional[float] = Field(
        default=None,
        description="Average Sharpe across runs"
    )
    median_sharpe: Optional[float] = Field(
        default=None,
        description="Median Sharpe across runs"
    )
    sharpe_std: Optional[float] = Field(
        default=None,
        description="Std dev of Sharpe across runs"
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When experiment completed"
    )
    total_computation_time_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Total computation time"
    )


class PortfolioResult(BaseModel):
    """Result of portfolio analysis (multi-strategy)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    portfolio_id: str = Field(..., description="Portfolio identifier")
    portfolio_name: str = Field(..., description="Portfolio name")

    # Strategy composition
    strategies: List[Dict[str, Any]] = Field(
        ...,
        description="Strategies and their allocations"
    )

    # Portfolio metrics
    portfolio_metrics: PerformanceMetrics = Field(
        ...,
        description="Portfolio-level performance metrics"
    )
    equity_curve: List[EquityPoint] = Field(
        ...,
        description="Portfolio equity curve"
    )

    # Cross-strategy analysis
    strategy_correlations: List[List[float]] = Field(
        ...,
        description="Correlation matrix of strategy returns"
    )
    diversification_ratio: float = Field(
        ...,
        gt=0,
        description="Portfolio diversification ratio"
    )
    risk_contributions: Dict[str, float] = Field(
        ...,
        description="Risk contribution by strategy"
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When portfolio was analyzed"
    )
