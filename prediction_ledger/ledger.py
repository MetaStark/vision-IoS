"""
Prediction Ledger Core

In-memory ledger interface for recording forecasts and outcomes.

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
"""

from typing import List

from prediction_ledger.models import ForecastRecord, OutcomeRecord
from prediction_ledger.exceptions import InvalidForecastException, InvalidOutcomeException


def record_forecast(forecast: ForecastRecord) -> ForecastRecord:
    """
    Validate and return forecast record (pure function).

    In actual use, this would be called before appending to storage.

    Args:
        forecast: Forecast record to validate

    Returns:
        Validated forecast record

    Raises:
        InvalidForecastException: If forecast is invalid
    """
    # Validate forecast
    if not forecast.forecast_id:
        raise InvalidForecastException("Forecast must have forecast_id")

    if not forecast.target_id:
        raise InvalidForecastException("Forecast must have target_id")

    if not forecast.input_state_hash:
        raise InvalidForecastException("Forecast must have input_state_hash")

    # Additional validation for probabilistic forecasts
    if isinstance(forecast.forecast_value, (int, float)):
        if not (0 <= forecast.forecast_value <= 1):
            # Allow values outside [0, 1] for non-probability targets
            pass

    return forecast


def record_outcome(outcome: OutcomeRecord) -> OutcomeRecord:
    """
    Validate and return outcome record (pure function).

    Args:
        outcome: Outcome record to validate

    Returns:
        Validated outcome record

    Raises:
        InvalidOutcomeException: If outcome is invalid
    """
    if not outcome.outcome_id:
        raise InvalidOutcomeException("Outcome must have outcome_id")

    if not outcome.target_id:
        raise InvalidOutcomeException("Outcome must have target_id")

    return outcome


def validate_forecast_batch(forecasts: List[ForecastRecord]) -> List[ForecastRecord]:
    """
    Validate batch of forecasts.

    Args:
        forecasts: List of forecast records

    Returns:
        List of validated forecasts

    Raises:
        InvalidForecastException: If any forecast is invalid
    """
    return [record_forecast(f) for f in forecasts]


def validate_outcome_batch(outcomes: List[OutcomeRecord]) -> List[OutcomeRecord]:
    """
    Validate batch of outcomes.

    Args:
        outcomes: List of outcome records

    Returns:
        List of validated outcomes

    Raises:
        InvalidOutcomeException: If any outcome is invalid
    """
    return [record_outcome(o) for o in outcomes]
