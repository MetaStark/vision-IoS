"""
Historical Simulator for Alpha Lab.

Bar-by-bar backtesting engine that runs strategies through historical data.
Integrates with Trade Engine and Execution Simulator as black boxes.
"""

import time
from typing import Callable, Dict, List, Any, Optional
from datetime import datetime
import pandas as pd

from alpha_lab.schemas import (
    StrategyDefinition,
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
    ExecutionStats,
    ProposedTrade,
    ExecutedTrade,
)
from alpha_lab.core.state_tracker import PortfolioStateTracker
from alpha_lab.utils import parse_date, format_date, validate_price_data


class HistoricalSimulatorError(Exception):
    """Raised when simulation fails."""
    pass


class HistoricalSimulator:
    """
    Bar-by-bar historical backtesting engine.

    This is the core backtest engine that:
    1. Iterates through historical price data bar-by-bar
    2. Calls the trade engine (black box) to get proposed trades
    3. Calls the execution simulator (black box) to simulate fills
    4. Updates portfolio state
    5. Generates equity curve and trade records
    6. Returns complete backtest results
    """

    def __init__(
        self,
        trade_engine: Callable,
        execution_simulator: Callable,
        verbose: bool = False
    ):
        """
        Initialize historical simulator.

        Args:
            trade_engine: Callable that takes (market_data, portfolio_state, params)
                         and returns List[ProposedTrade]
            execution_simulator: Callable that takes (proposed_trades, market_data)
                                and returns List[ExecutedTrade]
            verbose: Whether to print progress
        """
        self.trade_engine = trade_engine
        self.execution_simulator = execution_simulator
        self.verbose = verbose

    def run_backtest(
        self,
        strategy: StrategyDefinition,
        price_data: pd.DataFrame,
        backtest_config: BacktestConfig,
        backtest_id: Optional[str] = None
    ) -> BacktestResult:
        """
        Run a complete backtest.

        Args:
            strategy: Strategy definition
            price_data: DataFrame with columns: date, open, high, low, close, volume
            backtest_config: Backtest configuration
            backtest_id: Optional backtest ID (auto-generated if None)

        Returns:
            Complete backtest result

        Raises:
            HistoricalSimulatorError: If backtest fails
        """
        start_time = time.time()

        try:
            # Validate inputs
            self._validate_inputs(price_data, backtest_config)

            # Generate backtest ID if not provided
            if backtest_id is None:
                backtest_id = f"bt_{strategy.strategy_id}_{int(time.time())}"

            # Initialize portfolio state tracker
            start_date = parse_date(backtest_config.start_date)
            state_tracker = PortfolioStateTracker(
                initial_capital=backtest_config.initial_capital,
                start_date=start_date,
                currency=backtest_config.currency
            )

            # Filter price data to backtest date range
            price_data = self._filter_date_range(price_data, backtest_config)

            if len(price_data) == 0:
                raise HistoricalSimulatorError("No price data in specified date range")

            # Run bar-by-bar simulation
            self._simulate_bars(
                strategy=strategy,
                price_data=price_data,
                backtest_config=backtest_config,
                state_tracker=state_tracker
            )

            # Calculate performance metrics
            from alpha_lab.analytics.metrics import calculate_performance_metrics

            metrics = calculate_performance_metrics(
                equity_curve=state_tracker.equity_curve,
                trades=state_tracker.trade_history,
                risk_free_rate=0.02,  # Default, should come from config
                initial_capital=backtest_config.initial_capital
            )

            # Calculate execution stats
            execution_stats = self._calculate_execution_stats(state_tracker)

            # Create backtest result
            computation_time = time.time() - start_time

            result = BacktestResult(
                backtest_id=backtest_id,
                strategy_id=strategy.strategy_id,
                parameters=strategy.parameters,
                backtest_config=backtest_config.model_dump(),
                results=metrics,
                equity_curve=state_tracker.equity_curve,
                trades=state_tracker.trade_history,
                execution_stats=execution_stats,
                generated_at=datetime.utcnow(),
                computation_time_seconds=computation_time,
                error=None
            )

            if self.verbose:
                print(f"Backtest completed in {computation_time:.2f}s")
                print(f"Total Return: {metrics.total_return:.2%}")
                print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
                print(f"Max Drawdown: {metrics.max_drawdown:.2%}")
                print(f"Total Trades: {metrics.total_trades}")

            return result

        except Exception as e:
            # Return failed result
            computation_time = time.time() - start_time

            if backtest_id is None:
                backtest_id = f"bt_failed_{int(time.time())}"

            return BacktestResult(
                backtest_id=backtest_id,
                strategy_id=strategy.strategy_id,
                parameters=strategy.parameters,
                backtest_config=backtest_config.model_dump(),
                results=self._get_empty_metrics(),
                equity_curve=[],
                trades=[],
                execution_stats=self._get_empty_execution_stats(),
                generated_at=datetime.utcnow(),
                computation_time_seconds=computation_time,
                error=str(e)
            )

    def _simulate_bars(
        self,
        strategy: StrategyDefinition,
        price_data: pd.DataFrame,
        backtest_config: BacktestConfig,
        state_tracker: PortfolioStateTracker
    ) -> None:
        """
        Run bar-by-bar simulation loop.

        Args:
            strategy: Strategy definition
            price_data: Price data
            backtest_config: Backtest config
            state_tracker: Portfolio state tracker
        """
        total_bars = len(price_data)

        for idx, row in price_data.iterrows():
            # Extract bar data
            bar_data = self._extract_bar_data(row, idx, strategy)

            # Get current prices (for mark-to-market)
            current_prices = {
                symbol: row['close']
                for symbol in strategy.universe
            }

            # Call trade engine (BLACK BOX)
            portfolio_dict = state_tracker.get_portfolio_dict()

            try:
                proposed_trades = self.trade_engine(
                    market_data=bar_data,
                    portfolio_state=portfolio_dict,
                    strategy_params=strategy.parameters
                )
            except Exception as e:
                # Trade engine failed - skip this bar
                if self.verbose:
                    print(f"Trade engine error at bar {idx}: {e}")
                proposed_trades = []

            # If we have proposed trades, simulate execution
            if proposed_trades:
                try:
                    executed_trades = self.execution_simulator(
                        proposed_trades=proposed_trades,
                        market_data=bar_data,
                        slippage_config={
                            'slippage_bps': backtest_config.slippage_bps,
                            'commission_rate': backtest_config.commission_rate,
                        }
                    )

                    # Execute trades in portfolio
                    for executed_trade in executed_trades:
                        state_tracker.execute_trade(executed_trade, current_prices)

                except Exception as e:
                    # Execution simulator failed - skip trades
                    if self.verbose:
                        print(f"Execution simulator error at bar {idx}: {e}")

            # Mark-to-market at bar close
            timestamp = row.get('date', datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = parse_date(timestamp)

            state_tracker.mark_to_market(current_prices, timestamp)

            # Record equity point
            if len(state_tracker.equity_curve) > 0:
                prev_equity = state_tracker.equity_curve[-1].equity
                daily_return = (state_tracker.current_state.equity - prev_equity) / prev_equity
            else:
                daily_return = 0.0

            state_tracker.record_equity_point(daily_return)

            # Progress reporting
            if self.verbose and idx % max(1, total_bars // 10) == 0:
                pct = (idx / total_bars) * 100
                print(f"Progress: {pct:.0f}% ({idx}/{total_bars} bars)")

    def _extract_bar_data(
        self,
        row: pd.Series,
        bar_number: int,
        strategy: StrategyDefinition
    ) -> Dict[str, Any]:
        """Extract bar data into format for trade engine."""
        timestamp = row.get('date', datetime.utcnow())
        if isinstance(timestamp, str):
            timestamp = parse_date(timestamp)

        # For single-asset strategies, use first symbol
        symbol = strategy.universe[0] if strategy.universe else "UNKNOWN"

        return {
            'symbol': symbol,
            'timestamp': timestamp,
            'open': row.get('open', 0.0),
            'high': row.get('high', 0.0),
            'low': row.get('low', 0.0),
            'close': row.get('close', 0.0),
            'volume': row.get('volume', 0.0),
            'bar_number': bar_number,
        }

    def _validate_inputs(
        self,
        price_data: pd.DataFrame,
        backtest_config: BacktestConfig
    ) -> None:
        """Validate backtest inputs."""
        # Validate price data
        validate_price_data(price_data)

        # Validate config
        if backtest_config.initial_capital <= 0:
            raise HistoricalSimulatorError("Initial capital must be positive")

        if backtest_config.commission_rate < 0 or backtest_config.commission_rate > 1:
            raise HistoricalSimulatorError("Commission rate must be between 0 and 1")

        if backtest_config.slippage_bps < 0:
            raise HistoricalSimulatorError("Slippage must be non-negative")

    def _filter_date_range(
        self,
        price_data: pd.DataFrame,
        backtest_config: BacktestConfig
    ) -> pd.DataFrame:
        """Filter price data to backtest date range."""
        df = price_data.copy()

        # Ensure date column is datetime
        if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])

        # Filter by date range
        start_date = pd.to_datetime(backtest_config.start_date)
        end_date = pd.to_datetime(backtest_config.end_date)

        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

        return df.reset_index(drop=True)

    def _calculate_execution_stats(
        self,
        state_tracker: PortfolioStateTracker
    ) -> ExecutionStats:
        """Calculate execution statistics."""
        total_slippage = state_tracker.total_slippage_paid
        total_commission = state_tracker.total_commission_paid

        if len(state_tracker.trade_history) > 0:
            avg_slippage_bps = (
                sum(abs(t.slippage) / (t.exit_price * t.quantity) for t in state_tracker.trade_history if t.exit_price * t.quantity > 0)
                / len(state_tracker.trade_history)
            ) * 10000
            avg_fill_time = sum(
                getattr(t, 'fill_time_ms', 0) for t in state_tracker.trade_history
            ) / len(state_tracker.trade_history) if state_tracker.trade_history else 0

            # Calculate as % of PnL
            gross_pnl = sum(abs(t.pnl) for t in state_tracker.trade_history)
            if gross_pnl > 0:
                slippage_pct = (total_slippage / gross_pnl) * 100
                commission_pct = (total_commission / gross_pnl) * 100
            else:
                slippage_pct = None
                commission_pct = None
        else:
            avg_slippage_bps = 0.0
            avg_fill_time = 0.0
            slippage_pct = None
            commission_pct = None

        return ExecutionStats(
            total_slippage_cost=total_slippage,
            total_commission=total_commission,
            avg_slippage_bps=avg_slippage_bps,
            fill_rate=1.0,  # Assume full fills for now
            avg_fill_time_ms=avg_fill_time,
            slippage_as_pct_of_pnl=slippage_pct,
            commission_as_pct_of_pnl=commission_pct
        )

    def _get_empty_metrics(self) -> PerformanceMetrics:
        """Get empty metrics for failed backtest."""
        return PerformanceMetrics(
            total_return=0.0,
            cagr=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_duration_days=0,
            volatility_annual=0.0,
            downside_deviation=0.0,
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_trade_pnl=0.0,
            avg_trade_pnl_pct=0.0,
            avg_trade_duration_hours=0.0,
            turnover_annual=0.0,
            total_commission=0.0,
            total_slippage=0.0,
            best_trade_pnl=0.0,
            worst_trade_pnl=0.0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            avg_winner_pnl=0.0,
            avg_loser_pnl=0.0,
            time_in_market_pct=0.0,
            time_underwater_pct=0.0
        )

    def _get_empty_execution_stats(self) -> ExecutionStats:
        """Get empty execution stats for failed backtest."""
        return ExecutionStats(
            total_slippage_cost=0.0,
            total_commission=0.0,
            avg_slippage_bps=0.0,
            fill_rate=0.0,
            avg_fill_time_ms=0.0
        )
