"""
Artefact Manager for Alpha Lab.

Handles saving and loading of all Alpha Lab artefacts (strategies,
backtests, experiments, portfolios, reports) to/from JSON files.
"""

import json
from pathlib import Path
from typing import Optional, List, Type, TypeVar, Union
from datetime import datetime

from alpha_lab.schemas import (
    StrategyDefinition,
    BacktestResult,
    ExperimentResult,
    PortfolioResult,
    AlphaReport,
    ExperimentReport,
    ExperimentConfig,
    PortfolioConfig,
)

T = TypeVar('T')


class ArtefactManagerError(Exception):
    """Base exception for artefact manager errors."""
    pass


class ArtefactNotFoundError(ArtefactManagerError):
    """Raised when artefact file is not found."""
    pass


class ArtefactValidationError(ArtefactManagerError):
    """Raised when artefact fails validation."""
    pass


class ArtefactManager:
    """
    Manages saving and loading of Alpha Lab artefacts.

    All artefacts are stored as JSON files in a structured directory tree.
    Provides type-safe save/load operations using Pydantic schemas.
    """

    def __init__(self, base_dir: Union[str, Path] = "artefacts/alpha_lab"):
        """
        Initialize artefact manager.

        Args:
            base_dir: Base directory for all Alpha Lab artefacts
        """
        self.base_dir = Path(base_dir)
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure all required subdirectories exist."""
        subdirs = [
            "strategies",
            "backtests",
            "experiments",
            "portfolios",
            "reports",
            "reports/plots",
        ]
        for subdir in subdirs:
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, artefact_type: str, artefact_id: str, extension: str = "json") -> Path:
        """Get file path for an artefact."""
        return self.base_dir / artefact_type / f"{artefact_id}.{extension}"

    def _save_json(self, data: dict, file_path: Path) -> Path:
        """Save dictionary as pretty-printed JSON."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return file_path

    def _load_json(self, file_path: Path) -> dict:
        """Load JSON file as dictionary."""
        if not file_path.exists():
            raise ArtefactNotFoundError(f"Artefact not found: {file_path}")

        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ArtefactValidationError(f"Invalid JSON in {file_path}: {e}")

    # Strategy methods
    def save_strategy(self, strategy: StrategyDefinition) -> Path:
        """
        Save a strategy definition.

        Args:
            strategy: Strategy definition to save

        Returns:
            Path to saved file
        """
        file_path = self._get_file_path("strategies", strategy.strategy_id)
        return self._save_json(strategy.model_dump(mode='json'), file_path)

    def load_strategy(self, strategy_id: str) -> StrategyDefinition:
        """
        Load a strategy definition.

        Args:
            strategy_id: ID of strategy to load

        Returns:
            Loaded strategy definition

        Raises:
            ArtefactNotFoundError: If strategy not found
            ArtefactValidationError: If strategy fails validation
        """
        file_path = self._get_file_path("strategies", strategy_id)
        data = self._load_json(file_path)
        try:
            return StrategyDefinition(**data)
        except Exception as e:
            raise ArtefactValidationError(f"Strategy validation failed: {e}")

    # Backtest methods
    def save_backtest(self, result: BacktestResult) -> Path:
        """
        Save a backtest result.

        Args:
            result: Backtest result to save

        Returns:
            Path to saved file
        """
        file_path = self._get_file_path("backtests", result.backtest_id)
        return self._save_json(result.model_dump(mode='json'), file_path)

    def load_backtest(self, backtest_id: str) -> BacktestResult:
        """
        Load a backtest result.

        Args:
            backtest_id: ID of backtest to load

        Returns:
            Loaded backtest result

        Raises:
            ArtefactNotFoundError: If backtest not found
            ArtefactValidationError: If backtest fails validation
        """
        file_path = self._get_file_path("backtests", backtest_id)
        data = self._load_json(file_path)
        try:
            return BacktestResult(**data)
        except Exception as e:
            raise ArtefactValidationError(f"Backtest validation failed: {e}")

    # Experiment methods
    def save_experiment_config(self, config: ExperimentConfig) -> Path:
        """Save an experiment configuration."""
        file_path = self._get_file_path("experiments", f"{config.experiment_id}_config")
        return self._save_json(config.model_dump(mode='json'), file_path)

    def load_experiment_config(self, experiment_id: str) -> ExperimentConfig:
        """Load an experiment configuration."""
        file_path = self._get_file_path("experiments", f"{experiment_id}_config")
        data = self._load_json(file_path)
        try:
            return ExperimentConfig(**data)
        except Exception as e:
            raise ArtefactValidationError(f"Experiment config validation failed: {e}")

    def save_experiment_result(self, result: ExperimentResult) -> Path:
        """
        Save experiment results.

        Args:
            result: Experiment result to save

        Returns:
            Path to saved file
        """
        file_path = self._get_file_path("experiments", f"{result.experiment_id}_result")
        return self._save_json(result.model_dump(mode='json'), file_path)

    def load_experiment_result(self, experiment_id: str) -> ExperimentResult:
        """
        Load experiment results.

        Args:
            experiment_id: ID of experiment to load

        Returns:
            Loaded experiment result

        Raises:
            ArtefactNotFoundError: If experiment not found
            ArtefactValidationError: If experiment fails validation
        """
        file_path = self._get_file_path("experiments", f"{experiment_id}_result")
        data = self._load_json(file_path)
        try:
            return ExperimentResult(**data)
        except Exception as e:
            raise ArtefactValidationError(f"Experiment result validation failed: {e}")

    # Portfolio methods
    def save_portfolio_config(self, config: PortfolioConfig) -> Path:
        """Save a portfolio configuration."""
        file_path = self._get_file_path("portfolios", f"{config.portfolio_id}_config")
        return self._save_json(config.model_dump(mode='json'), file_path)

    def load_portfolio_config(self, portfolio_id: str) -> PortfolioConfig:
        """Load a portfolio configuration."""
        file_path = self._get_file_path("portfolios", f"{portfolio_id}_config")
        data = self._load_json(file_path)
        try:
            return PortfolioConfig(**data)
        except Exception as e:
            raise ArtefactValidationError(f"Portfolio config validation failed: {e}")

    def save_portfolio_result(self, result: PortfolioResult) -> Path:
        """
        Save portfolio results.

        Args:
            result: Portfolio result to save

        Returns:
            Path to saved file
        """
        file_path = self._get_file_path("portfolios", f"{result.portfolio_id}_result")
        return self._save_json(result.model_dump(mode='json'), file_path)

    def load_portfolio_result(self, portfolio_id: str) -> PortfolioResult:
        """
        Load portfolio results.

        Args:
            portfolio_id: ID of portfolio to load

        Returns:
            Loaded portfolio result

        Raises:
            ArtefactNotFoundError: If portfolio not found
            ArtefactValidationError: If portfolio fails validation
        """
        file_path = self._get_file_path("portfolios", f"{portfolio_id}_result")
        data = self._load_json(file_path)
        try:
            return PortfolioResult(**data)
        except Exception as e:
            raise ArtefactValidationError(f"Portfolio result validation failed: {e}")

    # Report methods
    def save_alpha_report(self, report: AlphaReport) -> Path:
        """
        Save an alpha report (JSON only).

        Args:
            report: Alpha report to save

        Returns:
            Path to saved JSON file
        """
        file_path = self._get_file_path("reports", report.report_id)
        return self._save_json(report.model_dump(mode='json'), file_path)

    def save_alpha_report_markdown(self, report_id: str, markdown_content: str) -> Path:
        """
        Save markdown version of alpha report.

        Args:
            report_id: Report ID
            markdown_content: Markdown content

        Returns:
            Path to saved markdown file
        """
        file_path = self._get_file_path("reports", report_id, extension="md")
        file_path.write_text(markdown_content)
        return file_path

    def load_alpha_report(self, report_id: str) -> AlphaReport:
        """
        Load an alpha report.

        Args:
            report_id: ID of report to load

        Returns:
            Loaded alpha report

        Raises:
            ArtefactNotFoundError: If report not found
            ArtefactValidationError: If report fails validation
        """
        file_path = self._get_file_path("reports", report_id)
        data = self._load_json(file_path)
        try:
            return AlphaReport(**data)
        except Exception as e:
            raise ArtefactValidationError(f"Alpha report validation failed: {e}")

    def save_experiment_report(self, report: ExperimentReport) -> Path:
        """Save an experiment report."""
        file_path = self._get_file_path("reports", f"{report.experiment_id}_experiment_report")
        return self._save_json(report.model_dump(mode='json'), file_path)

    def load_experiment_report(self, experiment_id: str) -> ExperimentReport:
        """Load an experiment report."""
        file_path = self._get_file_path("reports", f"{experiment_id}_experiment_report")
        data = self._load_json(file_path)
        try:
            return ExperimentReport(**data)
        except Exception as e:
            raise ArtefactValidationError(f"Experiment report validation failed: {e}")

    # Plot methods
    def get_plot_path(self, report_id: str, plot_name: str) -> Path:
        """
        Get path for a plot file.

        Args:
            report_id: Report ID
            plot_name: Plot name (e.g., 'equity_curve', 'drawdown')

        Returns:
            Path to plot file
        """
        return self.base_dir / "reports" / "plots" / f"{report_id}_{plot_name}.png"

    # List methods
    def list_strategies(self) -> List[str]:
        """List all strategy IDs."""
        strategy_dir = self.base_dir / "strategies"
        if not strategy_dir.exists():
            return []
        return [f.stem for f in strategy_dir.glob("*.json")]

    def list_backtests(self) -> List[str]:
        """List all backtest IDs."""
        backtest_dir = self.base_dir / "backtests"
        if not backtest_dir.exists():
            return []
        return [f.stem for f in backtest_dir.glob("*.json")]

    def list_experiments(self) -> List[str]:
        """List all experiment IDs."""
        experiment_dir = self.base_dir / "experiments"
        if not experiment_dir.exists():
            return []
        # Extract unique experiment IDs (remove _config/_result suffix)
        experiment_ids = set()
        for f in experiment_dir.glob("*.json"):
            exp_id = f.stem.replace("_config", "").replace("_result", "")
            experiment_ids.add(exp_id)
        return sorted(list(experiment_ids))

    def list_portfolios(self) -> List[str]:
        """List all portfolio IDs."""
        portfolio_dir = self.base_dir / "portfolios"
        if not portfolio_dir.exists():
            return []
        # Extract unique portfolio IDs
        portfolio_ids = set()
        for f in portfolio_dir.glob("*.json"):
            port_id = f.stem.replace("_config", "").replace("_result", "")
            portfolio_ids.add(port_id)
        return sorted(list(portfolio_ids))

    def list_reports(self) -> List[str]:
        """List all report IDs."""
        report_dir = self.base_dir / "reports"
        if not report_dir.exists():
            return []
        return [f.stem for f in report_dir.glob("*.json") if not f.stem.endswith("_experiment_report")]

    # Utility methods
    def delete_artefact(self, artefact_type: str, artefact_id: str) -> bool:
        """
        Delete an artefact.

        Args:
            artefact_type: Type of artefact (strategies, backtests, etc.)
            artefact_id: ID of artefact to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self._get_file_path(artefact_type, artefact_id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def artefact_exists(self, artefact_type: str, artefact_id: str) -> bool:
        """
        Check if an artefact exists.

        Args:
            artefact_type: Type of artefact
            artefact_id: ID of artefact

        Returns:
            True if artefact exists
        """
        file_path = self._get_file_path(artefact_type, artefact_id)
        return file_path.exists()

    def get_artefact_path(self, artefact_type: str, artefact_id: str) -> Path:
        """Get full path to an artefact file."""
        return self._get_file_path(artefact_type, artefact_id)
