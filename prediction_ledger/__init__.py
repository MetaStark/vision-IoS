"""
Prediction Ledger v1.0

Forecast recording, outcome tracking, and calibration metrics for FjordHQ Market System.

This package provides a complete audit trail for all forecasts, enabling
continuous calibration and evaluation of forecast accuracy.

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
Version: 1.0.0
"""

from prediction_ledger.models import (
    ForecastRecord,
    OutcomeRecord,
    EvaluationRecord,
    CalibrationBin,
    CalibrationCurve,
    ForecastOutcomePair,
    ReconciliationConfig,
    EvaluationConfig,
    SkillMetrics,
    SkillReport,
)

from prediction_ledger.ledger import (
    record_forecast,
    record_outcome,
    validate_forecast_batch,
    validate_outcome_batch,
)

from prediction_ledger.reconciliation import (
    reconcile_forecasts_to_outcomes,
    group_pairs_by_target,
    filter_pairs_by_time_range,
    group_matched_pairs_by_horizon,
    group_matched_pairs_by_target_type,
    group_matched_pairs_by_both,
)

from prediction_ledger.evaluation import (
    compute_brier_score,
    compute_calibration_curve,
    compute_directional_accuracy,
    compute_mean_absolute_error,
    compute_baseline_forecast,
    compute_baseline_brier_score,
    compute_brier_skill_score,
    build_calibration_curve_v2,
    build_skill_report,
)

from prediction_ledger.storage import (
    append_forecast_to_file,
    append_outcome_to_file,
    append_evaluation_to_file,
    load_forecasts,
    load_outcomes,
    load_evaluations,
)

from prediction_ledger.serialization import (
    save_calibration_curve_to_json,
    load_calibration_curve_from_json,
    calibration_curve_to_dict,
    evaluation_record_to_dict,
)

from prediction_ledger.utils import (
    generate_forecast_id,
    generate_outcome_id,
    generate_evaluation_id,
    derive_horizon_bucket,
    timedelta_to_days,
)

from prediction_ledger.exceptions import (
    PredictionLedgerException,
    InvalidForecastException,
    InvalidOutcomeException,
    ReconciliationException,
    EvaluationException,
    StorageException,
    SerializationException,
    InsufficientDataException,
)

__version__ = "1.0.0"

__all__ = [
    # Models
    "ForecastRecord",
    "OutcomeRecord",
    "EvaluationRecord",
    "CalibrationBin",
    "CalibrationCurve",
    "ForecastOutcomePair",
    "ReconciliationConfig",
    "EvaluationConfig",
    "SkillMetrics",
    "SkillReport",
    # Ledger
    "record_forecast",
    "record_outcome",
    "validate_forecast_batch",
    "validate_outcome_batch",
    # Reconciliation
    "reconcile_forecasts_to_outcomes",
    "group_pairs_by_target",
    "filter_pairs_by_time_range",
    "group_matched_pairs_by_horizon",
    "group_matched_pairs_by_target_type",
    "group_matched_pairs_by_both",
    # Evaluation
    "compute_brier_score",
    "compute_calibration_curve",
    "compute_directional_accuracy",
    "compute_mean_absolute_error",
    "compute_baseline_forecast",
    "compute_baseline_brier_score",
    "compute_brier_skill_score",
    "build_calibration_curve_v2",
    "build_skill_report",
    # Storage
    "append_forecast_to_file",
    "append_outcome_to_file",
    "append_evaluation_to_file",
    "load_forecasts",
    "load_outcomes",
    "load_evaluations",
    # Serialization
    "save_calibration_curve_to_json",
    "load_calibration_curve_from_json",
    "calibration_curve_to_dict",
    "evaluation_record_to_dict",
    # Utils
    "generate_forecast_id",
    "generate_outcome_id",
    "generate_evaluation_id",
    "derive_horizon_bucket",
    "timedelta_to_days",
    # Exceptions
    "PredictionLedgerException",
    "InvalidForecastException",
    "InvalidOutcomeException",
    "ReconciliationException",
    "EvaluationException",
    "StorageException",
    "SerializationException",
    "InsufficientDataException",
]
