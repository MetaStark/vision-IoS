"""
Prediction Ledger Exceptions

Custom exceptions for prediction_ledger package.

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
"""


class PredictionLedgerException(Exception):
    """Base exception for prediction_ledger package."""
    pass


class InvalidForecastException(PredictionLedgerException):
    """Raised when forecast record is invalid."""
    pass


class InvalidOutcomeException(PredictionLedgerException):
    """Raised when outcome record is invalid."""
    pass


class ReconciliationException(PredictionLedgerException):
    """Raised when forecast-outcome reconciliation fails."""
    pass


class EvaluationException(PredictionLedgerException):
    """Raised when evaluation computation fails."""
    pass


class StorageException(PredictionLedgerException):
    """Raised when file storage operation fails."""
    pass


class SerializationException(PredictionLedgerException):
    """Raised when JSON serialization/deserialization fails."""
    pass


class InsufficientDataException(PredictionLedgerException):
    """Raised when insufficient data for evaluation."""
    pass
