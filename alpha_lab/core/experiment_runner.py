"""
Experiment Runner for Alpha Lab.

Runs parameter sweep experiments - testing strategies across
multiple parameter combinations to find optimal configurations.
"""

import time
import itertools
from typing import Callable, Dict, List, Any, Optional
from datetime import datetime
import pandas as pd

from alpha_lab.schemas import (
    StrategyDefinition,
    ExperimentConfig,
    BacktestConfig,
    ExperimentResult,
    ExperimentRun,
    BacktestResult,
)
from alpha_lab.core.historical_simulator import HistoricalSimulator


class ExperimentRunnerError(Exception):
    """Raised when experiment fails."""
    pass


class ExperimentRunner:
    """
    Runs parameter sweep experiments.

    Takes a strategy template and parameter grid, runs backtests
    for all parameter combinations, and aggregates results.
    """

    def __init__(
        self,
        trade_engine: Callable,
        execution_simulator: Callable,
        verbose: bool = False
    ):
        """
        Initialize experiment runner.

        Args:
            trade_engine: Trade engine callable
            execution_simulator: Execution simulator callable
            verbose: Whether to print progress
        """
        self.trade_engine = trade_engine
        self.execution_simulator = execution_simulator
        self.verbose = verbose

        # Create historical simulator
        self.simulator = HistoricalSimulator(
            trade_engine=trade_engine,
            execution_simulator=execution_simulator,
            verbose=False  # Individual backtests not verbose
        )

    def run_experiment(
        self,
        experiment_config: ExperimentConfig,
        strategy_template: StrategyDefinition,
        price_data: pd.DataFrame
    ) -> ExperimentResult:
        """
        Run a complete parameter sweep experiment.

        Args:
            experiment_config: Experiment configuration
            strategy_template: Strategy template (parameters will be varied)
            price_data: Price data for backtesting

        Returns:
            Complete experiment result
        """
        start_time = time.time()

        if self.verbose:
            print(f"Starting experiment: {experiment_config.experiment_name}")
            print(f"Strategy template: {strategy_template.strategy_id}")

        # Generate parameter combinations
        param_combinations = self._generate_parameter_combinations(
            experiment_config.parameter_grid
        )

        if self.verbose:
            print(f"Total parameter combinations: {len(param_combinations)}")

        # Run backtests for each combination
        runs = []
        successful_runs = 0
        failed_runs = 0

        for idx, params in enumerate(param_combinations):
            if self.verbose:
                pct = ((idx + 1) / len(param_combinations)) * 100
                print(f"Progress: {pct:.0f}% ({idx + 1}/{len(param_combinations)})")

            run = self._run_single_combination(
                strategy_template=strategy_template,
                parameters=params,
                backtest_config=experiment_config.backtest_config,
                price_data=price_data,
                run_number=idx + 1
            )

            runs.append(run)

            if run.success:
                successful_runs += 1
            else:
                failed_runs += 1

                if experiment_config.execution_config.fail_fast:
                    if self.verbose:
                        print(f"Fail-fast enabled, stopping experiment")
                    break

        # Aggregate results
        experiment_result = self._aggregate_results(
            experiment_id=experiment_config.experiment_id,
            experiment_name=experiment_config.experiment_name,
            strategy_template=strategy_template.strategy_id,
            runs=runs,
            successful_runs=successful_runs,
            failed_runs=failed_runs,
            total_time=time.time() - start_time
        )

        if self.verbose:
            print(f"\nExperiment completed in {experiment_result.total_computation_time_seconds:.2f}s")
            print(f"Successful runs: {successful_runs}/{len(param_combinations)}")

            if successful_runs > 0 and experiment_result.best_run_by_sharpe:
                print(f"Best Sharpe ratio: {experiment_result.avg_sharpe:.2f}")

        return experiment_result

    def _generate_parameter_combinations(
        self,
        parameter_grid: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate all parameter combinations from grid.

        Args:
            parameter_grid: Dictionary mapping param names to value lists

        Returns:
            List of parameter dictionaries
        """
        # Get parameter names and values
        param_names = list(parameter_grid.keys())
        param_values = [parameter_grid[name] for name in param_names]

        # Generate Cartesian product
        combinations = []
        for values in itertools.product(*param_values):
            param_dict = dict(zip(param_names, values))
            combinations.append(param_dict)

        return combinations

    def _run_single_combination(
        self,
        strategy_template: StrategyDefinition,
        parameters: Dict[str, Any],
        backtest_config: BacktestConfig,
        price_data: pd.DataFrame,
        run_number: int
    ) -> ExperimentRun:
        """
        Run backtest for a single parameter combination.

        Args:
            strategy_template: Strategy template
            parameters: Parameters for this run
            backtest_config: Backtest configuration
            price_data: Price data
            run_number: Run number

        Returns:
            Experiment run result
        """
        start_time = time.time()

        # Create strategy instance with these parameters
        strategy = StrategyDefinition(
            strategy_id=f"{strategy_template.strategy_id}_run_{run_number}",
            strategy_name=strategy_template.strategy_name,
            strategy_type=strategy_template.strategy_type,
            description=strategy_template.description,
            parameters=parameters,  # Use experiment parameters
            universe=strategy_template.universe,
            rebalance_frequency=strategy_template.rebalance_frequency,
            trade_engine_config=strategy_template.trade_engine_config,
            created_at=datetime.utcnow(),
            version=strategy_template.version
        )

        # Generate backtest ID
        backtest_id = f"bt_{strategy.strategy_id}_{int(time.time())}"

        try:
            # Run backtest
            backtest_result = self.simulator.run_backtest(
                strategy=strategy,
                price_data=price_data,
                backtest_config=backtest_config,
                backtest_id=backtest_id
            )

            # Check if backtest succeeded
            success = backtest_result.error is None

            return ExperimentRun(
                run_id=f"run_{run_number:04d}",
                parameters=parameters,
                backtest_result=backtest_result if success else None,
                success=success,
                error=backtest_result.error,
                computation_time_seconds=time.time() - start_time
            )

        except Exception as e:
            # Backtest failed
            return ExperimentRun(
                run_id=f"run_{run_number:04d}",
                parameters=parameters,
                backtest_result=None,
                success=False,
                error=str(e),
                computation_time_seconds=time.time() - start_time
            )

    def _aggregate_results(
        self,
        experiment_id: str,
        experiment_name: str,
        strategy_template: str,
        runs: List[ExperimentRun],
        successful_runs: int,
        failed_runs: int,
        total_time: float
    ) -> ExperimentResult:
        """
        Aggregate results from all runs.

        Args:
            experiment_id: Experiment ID
            experiment_name: Experiment name
            strategy_template: Strategy template ID
            runs: List of all runs
            successful_runs: Number of successful runs
            failed_runs: Number of failed runs
            total_time: Total computation time

        Returns:
            Aggregated experiment result
        """
        # Extract successful runs
        successful = [r for r in runs if r.success and r.backtest_result is not None]

        # Find best/worst performers
        best_sharpe_run = None
        worst_sharpe_run = None
        best_return_run = None

        avg_sharpe = None
        median_sharpe = None
        sharpe_std = None

        if successful:
            # Sort by Sharpe ratio
            sharpes = [(r.run_id, r.backtest_result.results.sharpe_ratio) for r in successful]
            sharpes_sorted = sorted(sharpes, key=lambda x: x[1], reverse=True)

            best_sharpe_run = sharpes_sorted[0][0]
            worst_sharpe_run = sharpes_sorted[-1][0]

            # Sort by total return
            returns = [(r.run_id, r.backtest_result.results.total_return) for r in successful]
            returns_sorted = sorted(returns, key=lambda x: x[1], reverse=True)

            best_return_run = returns_sorted[0][0]

            # Summary statistics
            sharpe_values = [s[1] for s in sharpes]
            avg_sharpe = float(sum(sharpe_values) / len(sharpe_values))
            median_sharpe = float(sorted(sharpe_values)[len(sharpe_values) // 2])

            if len(sharpe_values) > 1:
                import numpy as np
                sharpe_std = float(np.std(sharpe_values))
            else:
                sharpe_std = 0.0

        return ExperimentResult(
            experiment_id=experiment_id,
            experiment_name=experiment_name,
            strategy_template=strategy_template,
            runs=runs,
            total_runs=len(runs),
            successful_runs=successful_runs,
            failed_runs=failed_runs,
            best_run_by_sharpe=best_sharpe_run,
            worst_run_by_sharpe=worst_sharpe_run,
            best_run_by_return=best_return_run,
            avg_sharpe=avg_sharpe,
            median_sharpe=median_sharpe,
            sharpe_std=sharpe_std,
            generated_at=datetime.utcnow(),
            total_computation_time_seconds=total_time
        )
