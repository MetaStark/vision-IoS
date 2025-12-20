"""
Prediction Ledger Serialization

JSON serialization helpers for prediction ledger artifacts.

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
"""

import json
from pathlib import Path
from typing import Any, Dict

from prediction_ledger.models import CalibrationCurve, EvaluationRecord
from prediction_ledger.exceptions import SerializationException


def save_calibration_curve_to_json(
    calibration_curve: CalibrationCurve, file_path: str | Path
) -> None:
    """
    Save calibration curve to JSON file.

    Args:
        calibration_curve: Calibration curve to save
        file_path: Path to JSON file

    Raises:
        SerializationException: If serialization fails
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = calibration_curve.model_dump(mode="json")

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    except Exception as e:
        raise SerializationException(
            f"Failed to save calibration curve to {file_path}: {e}"
        ) from e


def load_calibration_curve_from_json(file_path: str | Path) -> CalibrationCurve:
    """
    Load calibration curve from JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        CalibrationCurve object

    Raises:
        SerializationException: If deserialization fails
    """
    try:
        file_path = Path(file_path)

        with open(file_path, "r") as f:
            data = json.load(f)

        return CalibrationCurve.model_validate(data)

    except Exception as e:
        raise SerializationException(
            f"Failed to load calibration curve from {file_path}: {e}"
        ) from e


def calibration_curve_to_dict(calibration_curve: CalibrationCurve) -> Dict[str, Any]:
    """
    Convert calibration curve to plain dict.

    Args:
        calibration_curve: Calibration curve

    Returns:
        Plain dict
    """
    return calibration_curve.model_dump(mode="json")


def evaluation_record_to_dict(evaluation: EvaluationRecord) -> Dict[str, Any]:
    """
    Convert evaluation record to plain dict.

    Args:
        evaluation: Evaluation record

    Returns:
        Plain dict
    """
    return evaluation.model_dump(mode="json")
