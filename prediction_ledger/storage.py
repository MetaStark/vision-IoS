"""
Prediction Ledger File Storage

File-based storage using JSON lines format (append-only).

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from prediction_ledger.models import ForecastRecord, OutcomeRecord, EvaluationRecord
from prediction_ledger.exceptions import StorageException


def append_forecast_to_file(file_path: str | Path, forecast: ForecastRecord) -> None:
    """
    Append forecast to JSON lines file.

    Uses append-only semantics for auditability.

    Args:
        file_path: Path to JSON lines file
        forecast: Forecast record to append

    Raises:
        StorageException: If write fails
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "a") as f:
            json.dump(forecast.model_dump(mode="json"), f, default=str)
            f.write("\n")

    except Exception as e:
        raise StorageException(f"Failed to append forecast to {file_path}: {e}") from e


def append_outcome_to_file(file_path: str | Path, outcome: OutcomeRecord) -> None:
    """
    Append outcome to JSON lines file.

    Args:
        file_path: Path to JSON lines file
        outcome: Outcome record to append

    Raises:
        StorageException: If write fails
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "a") as f:
            json.dump(outcome.model_dump(mode="json"), f, default=str)
            f.write("\n")

    except Exception as e:
        raise StorageException(f"Failed to append outcome to {file_path}: {e}") from e


def append_evaluation_to_file(
    file_path: str | Path, evaluation: EvaluationRecord
) -> None:
    """
    Append evaluation to JSON lines file.

    Args:
        file_path: Path to JSON lines file
        evaluation: Evaluation record to append

    Raises:
        StorageException: If write fails
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "a") as f:
            json.dump(evaluation.model_dump(mode="json"), f, default=str)
            f.write("\n")

    except Exception as e:
        raise StorageException(
            f"Failed to append evaluation to {file_path}: {e}"
        ) from e


def load_forecasts(
    file_path: str | Path,
    filters: Dict[str, Any] | None = None,
) -> List[ForecastRecord]:
    """
    Load forecasts from JSON lines file with optional filtering.

    Args:
        file_path: Path to JSON lines file
        filters: Optional filters (e.g., {"target_id": "xyz"})

    Returns:
        List of ForecastRecord objects

    Raises:
        StorageException: If read fails
    """
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            return []

        forecasts = []

        with open(file_path, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    forecast = ForecastRecord.model_validate(data)

                    # Apply filters
                    if filters and not _matches_filters(forecast, filters):
                        continue

                    forecasts.append(forecast)

        return forecasts

    except Exception as e:
        raise StorageException(f"Failed to load forecasts from {file_path}: {e}") from e


def load_outcomes(
    file_path: str | Path,
    filters: Dict[str, Any] | None = None,
) -> List[OutcomeRecord]:
    """
    Load outcomes from JSON lines file with optional filtering.

    Args:
        file_path: Path to JSON lines file
        filters: Optional filters

    Returns:
        List of OutcomeRecord objects

    Raises:
        StorageException: If read fails
    """
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            return []

        outcomes = []

        with open(file_path, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    outcome = OutcomeRecord.model_validate(data)

                    # Apply filters
                    if filters and not _matches_filters(outcome, filters):
                        continue

                    outcomes.append(outcome)

        return outcomes

    except Exception as e:
        raise StorageException(f"Failed to load outcomes from {file_path}: {e}") from e


def load_evaluations(
    file_path: str | Path,
    filters: Dict[str, Any] | None = None,
) -> List[EvaluationRecord]:
    """
    Load evaluations from JSON lines file.

    Args:
        file_path: Path to JSON lines file
        filters: Optional filters

    Returns:
        List of EvaluationRecord objects
    """
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            return []

        evaluations = []

        with open(file_path, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    evaluation = EvaluationRecord.model_validate(data)

                    if filters and not _matches_filters(evaluation, filters):
                        continue

                    evaluations.append(evaluation)

        return evaluations

    except Exception as e:
        raise StorageException(
            f"Failed to load evaluations from {file_path}: {e}"
        ) from e


def _matches_filters(obj: Any, filters: Dict[str, Any]) -> bool:
    """
    Check if object matches all filters.

    Args:
        obj: Object to check
        filters: Dict of field -> value filters

    Returns:
        True if matches all filters
    """
    for field, value in filters.items():
        if not hasattr(obj, field) or getattr(obj, field) != value:
            return False
    return True
