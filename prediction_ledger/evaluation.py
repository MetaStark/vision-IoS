"""
Forecast Evaluation Metrics

Compute Brier scores, calibration curves, hit rates, and other metrics.

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
"""

from datetime import datetime
from typing import List
import statistics

from prediction_ledger.models import (
    ForecastOutcomePair,
    EvaluationRecord,
    CalibrationBin,
    CalibrationCurve,
    EvaluationConfig,
)
from prediction_ledger.utils import (
    compute_brier_score_single,
    bin_probabilities,
    generate_evaluation_id,
)
from prediction_ledger.exceptions import EvaluationException, InsufficientDataException


def compute_brier_score(
    pairs: List[ForecastOutcomePair],
    evaluation_timestamp: datetime | None = None,
) -> EvaluationRecord:
    """
    Compute Brier score for probabilistic forecasts.

    Brier Score = mean((forecast_prob - realized_binary)^2)
    Lower is better, perfect score = 0.

    Args:
        pairs: List of forecast-outcome pairs
        evaluation_timestamp: When evaluation was performed

    Returns:
        EvaluationRecord with Brier score

    Raises:
        InsufficientDataException: If not enough pairs
        EvaluationException: If computation fails
    """
    if not pairs:
        raise InsufficientDataException("Need at least 1 pair for Brier score")

    if evaluation_timestamp is None:
        evaluation_timestamp = datetime.utcnow()

    # Validate that forecasts and outcomes are numeric
    try:
        scores = []
        for pair in pairs:
            forecast_prob = float(pair.forecast.forecast_value)
            realized_value = float(pair.outcome.realized_value)

            # Convert realized value to binary if not already
            if realized_value not in [0, 1]:
                realized_binary = 1 if realized_value > 0.5 else 0
            else:
                realized_binary = int(realized_value)

            score = compute_brier_score_single(forecast_prob, realized_binary)
            scores.append(score)

        mean_brier_score = statistics.mean(scores)

        # Get target info from first pair
        target_id = pairs[0].forecast.target_id
        target_type = pairs[0].forecast.target_type

        # Get time range
        forecast_times = [p.forecast.timestamp for p in pairs]
        period_start = min(forecast_times)
        period_end = max(forecast_times)

        return EvaluationRecord(
            evaluation_id=generate_evaluation_id(
                evaluation_timestamp, target_id, "brier_score"
            ),
            timestamp=evaluation_timestamp,
            target_id=target_id,
            target_type=target_type,
            metric_name="brier_score",
            metric_value=mean_brier_score,
            sample_size=len(pairs),
            period_start=period_start,
            period_end=period_end,
            metadata={"scores": scores[:10]},  # Sample of scores
        )

    except Exception as e:
        raise EvaluationException(f"Failed to compute Brier score: {e}") from e


def compute_calibration_curve(
    pairs: List[ForecastOutcomePair],
    config: EvaluationConfig | None = None,
) -> CalibrationCurve:
    """
    Compute calibration curve for probabilistic forecasts.

    Groups forecasts by probability bins and checks realized frequency.
    Well-calibrated forecasts have forecast_prob ≈ realized_freq for all bins.

    Args:
        pairs: List of forecast-outcome pairs
        config: Evaluation configuration

    Returns:
        CalibrationCurve

    Raises:
        InsufficientDataException: If not enough pairs
    """
    if not pairs:
        raise InsufficientDataException("Need at least 1 pair for calibration curve")

    if config is None:
        config = EvaluationConfig()

    # Extract probabilities and outcomes
    forecast_probs = [float(p.forecast.forecast_value) for p in pairs]
    realized_values = [float(p.outcome.realized_value) for p in pairs]

    # Convert realized values to binary
    realized_binary = [1 if v > 0.5 else 0 for v in realized_values]

    # Bin probabilities
    prob_bins = bin_probabilities(forecast_probs, config.n_calibration_bins)

    # Compute realized frequency for each bin
    calibration_bins: List[CalibrationBin] = []

    for bin_start, bin_end, indices in prob_bins:
        if not indices or len(indices) < config.min_samples_per_bin:
            continue  # Skip bins with too few samples

        # Realized frequency in this bin
        realized_in_bin = [realized_binary[i] for i in indices]
        realized_freq = statistics.mean(realized_in_bin)

        # Forecast probability center
        forecast_prob_center = (bin_start + bin_end) / 2

        calibration_bins.append(
            CalibrationBin(
                lower_bound=bin_start,
                upper_bound=bin_end,
                forecast_mean=forecast_prob_center,
                observed_frequency=realized_freq,
                count=len(indices),
            )
        )

    # Get metadata
    target_id = pairs[0].forecast.target_id
    target_type = pairs[0].forecast.target_type
    forecast_times = [p.forecast.timestamp for p in pairs]
    period_start = min(forecast_times)
    period_end = max(forecast_times)

    # Compute mean calibration error
    mce = sum(bin.calibration_error * bin.count for bin in calibration_bins) / len(pairs)

    return CalibrationCurve(
        curve_id=f"cal_{target_type}_{datetime.utcnow().strftime('%Y%m%d')}",
        target_type=target_type,
        horizon_bucket="mixed",  # Old function doesn't know horizon
        bins=calibration_bins,
        period_start=period_start,
        period_end=period_end,
        sample_size=len(pairs),
        mean_calibration_error=mce,
        created_at=datetime.utcnow(),
        metadata={"target_id": target_id},
    )


def compute_directional_accuracy(
    pairs: List[ForecastOutcomePair],
    evaluation_timestamp: datetime | None = None,
) -> EvaluationRecord:
    """
    Compute hit rate for directional forecasts (up/down).

    Hit rate = proportion of correct directional forecasts.

    Args:
        pairs: List of forecast-outcome pairs
        evaluation_timestamp: When evaluation was performed

    Returns:
        EvaluationRecord with hit rate

    Raises:
        InsufficientDataException: If not enough pairs
    """
    if not pairs:
        raise InsufficientDataException("Need at least 1 pair for directional accuracy")

    if evaluation_timestamp is None:
        evaluation_timestamp = datetime.utcnow()

    # Count correct forecasts
    correct = 0
    for pair in pairs:
        forecast_direction = 1 if float(pair.forecast.forecast_value) > 0.5 else 0
        realized_direction = 1 if float(pair.outcome.realized_value) > 0.5 else 0

        if forecast_direction == realized_direction:
            correct += 1

    hit_rate = correct / len(pairs)

    # Get metadata
    target_id = pairs[0].forecast.target_id
    target_type = pairs[0].forecast.target_type
    forecast_times = [p.forecast.timestamp for p in pairs]
    period_start = min(forecast_times)
    period_end = max(forecast_times)

    return EvaluationRecord(
        evaluation_id=generate_evaluation_id(
            evaluation_timestamp, target_id, "hit_rate"
        ),
        timestamp=evaluation_timestamp,
        target_id=target_id,
        target_type=target_type,
        metric_name="hit_rate",
        metric_value=hit_rate,
        sample_size=len(pairs),
        period_start=period_start,
        period_end=period_end,
        metadata={"correct": correct, "total": len(pairs)},
    )


def compute_mean_absolute_error(
    pairs: List[ForecastOutcomePair],
    evaluation_timestamp: datetime | None = None,
) -> EvaluationRecord:
    """
    Compute mean absolute error for continuous forecasts.

    MAE = mean(|forecast - realized|)

    Args:
        pairs: List of forecast-outcome pairs
        evaluation_timestamp: When evaluation was performed

    Returns:
        EvaluationRecord with MAE
    """
    if not pairs:
        raise InsufficientDataException("Need at least 1 pair for MAE")

    if evaluation_timestamp is None:
        evaluation_timestamp = datetime.utcnow()

    errors = []
    for pair in pairs:
        forecast_val = float(pair.forecast.forecast_value)
        realized_val = float(pair.outcome.realized_value)
        errors.append(abs(forecast_val - realized_val))

    mae = statistics.mean(errors)

    target_id = pairs[0].forecast.target_id
    target_type = pairs[0].forecast.target_type
    forecast_times = [p.forecast.timestamp for p in pairs]
    period_start = min(forecast_times)
    period_end = max(forecast_times)

    return EvaluationRecord(
        evaluation_id=generate_evaluation_id(evaluation_timestamp, target_id, "mae"),
        timestamp=evaluation_timestamp,
        target_id=target_id,
        target_type=target_type,
        metric_name="mean_absolute_error",
        metric_value=mae,
        sample_size=len(pairs),
        period_start=period_start,
        period_end=period_end,
    )


# ============================================================================
# BASELINE STRATEGIES (New v1.1)
# ============================================================================

def compute_baseline_forecast(
    pairs: List[ForecastOutcomePair],
    baseline_type: str = "historical_frequency"
) -> float:
    """
    Compute baseline forecast probability.

    Baseline types:
    - "historical_frequency": P = mean(all realized outcomes)
    - "uniform": P = 0.5
    - "stratified": P = mean(outcomes per target type) - not implemented yet

    Args:
        pairs: List of forecast-outcome pairs
        baseline_type: Type of baseline

    Returns:
        Baseline forecast probability
    """
    if baseline_type == "uniform":
        return 0.5

    elif baseline_type == "historical_frequency":
        if not pairs:
            return 0.5

        # Compute mean of realized outcomes
        realized_values = [float(p.outcome.realized_value) for p in pairs]
        return sum(realized_values) / len(realized_values)

    else:
        raise ValueError(f"Unknown baseline_type: {baseline_type}")


def compute_baseline_brier_score(
    pairs: List[ForecastOutcomePair],
    baseline_type: str = "historical_frequency"
) -> float:
    """
    Compute Brier score for baseline forecast.

    Args:
        pairs: List of forecast-outcome pairs
        baseline_type: Type of baseline

    Returns:
        Baseline Brier score

    Raises:
        InsufficientDataException: If no pairs
    """
    if not pairs:
        raise InsufficientDataException("Need at least 1 pair for baseline Brier score")

    baseline_prob = compute_baseline_forecast(pairs, baseline_type)

    # Compute Brier score with constant baseline probability
    scores = []
    for pair in pairs:
        realized_value = float(pair.outcome.realized_value)
        realized_binary = 1 if realized_value > 0.5 else 0
        score = (baseline_prob - realized_binary) ** 2
        scores.append(score)

    return statistics.mean(scores)


# ============================================================================
# SKILL SCORES (New v1.1)
# ============================================================================

def compute_brier_skill_score(
    pairs: List[ForecastOutcomePair],
    baseline_type: str = "historical_frequency"
) -> float:
    """
    Compute Brier Skill Score.

    BSS = 1 - (BS_model / BS_baseline)

    Interpretation:
    - BSS > 0: Model better than baseline (has skill)
    - BSS = 0: Model equal to baseline
    - BSS < 0: Model worse than baseline

    Args:
        pairs: List of forecast-outcome pairs
        baseline_type: Type of baseline

    Returns:
        Brier Skill Score

    Raises:
        InsufficientDataException: If no pairs
    """
    if not pairs:
        raise InsufficientDataException("Need at least 1 pair for BSS")

    # Compute model Brier score
    model_brier = compute_brier_score(pairs).metric_value

    # Compute baseline Brier score
    baseline_brier = compute_baseline_brier_score(pairs, baseline_type)

    # Compute skill score
    if baseline_brier == 0:
        # Avoid division by zero
        return 0.0

    bss = 1 - (model_brier / baseline_brier)
    return bss


# ============================================================================
# ENHANCED CALIBRATION CURVE (Extended v1.1)
# ============================================================================

def build_calibration_curve_v2(
    pairs: List[ForecastOutcomePair],
    target_type: str,
    horizon_bucket: str,
    num_bins: int = 10,
    min_samples_per_bin: int = 5
) -> "CalibrationCurve":
    """
    Build calibration curve with enhanced metadata.

    Args:
        pairs: List of forecast-outcome pairs
        target_type: Target type
        horizon_bucket: Horizon bucket
        num_bins: Number of probability bins
        min_samples_per_bin: Minimum samples required per bin

    Returns:
        CalibrationCurve object

    Raises:
        InsufficientDataException: If not enough pairs
    """
    from prediction_ledger.models import CalibrationCurve, CalibrationBin
    from prediction_ledger.utils import bin_probabilities

    if not pairs:
        raise InsufficientDataException("Need at least 1 pair for calibration curve")

    # Extract probabilities and outcomes
    forecast_probs = [float(p.forecast.forecast_value) for p in pairs]
    realized_values = [float(p.outcome.realized_value) for p in pairs]
    realized_binary = [1 if v > 0.5 else 0 for v in realized_values]

    # Bin probabilities
    prob_bins = bin_probabilities(forecast_probs, num_bins)

    # Compute calibration bins
    calibration_bins: List[CalibrationBin] = []

    for bin_start, bin_end, indices in prob_bins:
        if not indices or len(indices) < min_samples_per_bin:
            continue  # Skip bins with too few samples

        # Forecasts in this bin
        forecasts_in_bin = [forecast_probs[i] for i in indices]
        realized_in_bin = [realized_binary[i] for i in indices]

        # Compute statistics
        forecast_mean = statistics.mean(forecasts_in_bin)
        observed_freq = statistics.mean(realized_in_bin)

        calibration_bins.append(
            CalibrationBin(
                lower_bound=bin_start,
                upper_bound=bin_end,
                forecast_mean=forecast_mean,
                observed_frequency=observed_freq,
                count=len(indices),
            )
        )

    # Compute mean calibration error
    if calibration_bins:
        total_count = sum(b.count for b in calibration_bins)
        weighted_errors = sum(b.calibration_error * b.count for b in calibration_bins)
        mce = weighted_errors / total_count if total_count > 0 else 0.0
    else:
        mce = 0.0

    # Get time range
    forecast_times = [p.forecast.timestamp for p in pairs]
    period_start = min(forecast_times)
    period_end = max(forecast_times)

    # Generate curve ID
    curve_id = f"cal_{target_type}_{horizon_bucket}_{period_start.strftime('%Y%m')}"

    return CalibrationCurve(
        curve_id=curve_id,
        target_type=target_type,
        horizon_bucket=horizon_bucket,
        bins=calibration_bins,
        period_start=period_start,
        period_end=period_end,
        sample_size=len(pairs),
        mean_calibration_error=mce,
        created_at=datetime.utcnow(),
    )


# ============================================================================
# SKILL REPORT BUILDER (New v1.1)
# ============================================================================

def build_skill_report(
    target_type: str,
    horizon_bucket: str,
    pairs: List[ForecastOutcomePair],
    period_start: datetime,
    period_end: datetime,
    model_id: str | None = None,
    baseline_type: str = "historical_frequency"
) -> "SkillReport":
    """
    Build comprehensive skill report.

    Computes:
    - Brier score (model and baseline)
    - Brier skill score
    - Directional accuracy (if applicable)
    - Quality flags (well-calibrated, has skill, sufficient sample)

    Args:
        target_type: Target type
        horizon_bucket: Horizon bucket
        pairs: List of forecast-outcome pairs
        period_start: Start of evaluation period
        period_end: End of evaluation period
        model_id: Optional model identifier
        baseline_type: Type of baseline

    Returns:
        SkillReport object

    Raises:
        InsufficientDataException: If no pairs
    """
    from prediction_ledger.models import SkillReport, SkillMetrics

    if not pairs:
        raise InsufficientDataException("Need at least 1 pair for skill report")

    # Compute metrics
    model_brier = compute_brier_score(pairs).metric_value
    baseline_brier = compute_baseline_brier_score(pairs, baseline_type)
    bss = compute_brier_skill_score(pairs, baseline_type)

    # Directional accuracy (if applicable)
    try:
        dir_acc_record = compute_directional_accuracy(pairs)
        directional_accuracy = dir_acc_record.metric_value
    except:
        directional_accuracy = None

    # Build calibration curve to check calibration
    try:
        cal_curve = build_calibration_curve_v2(pairs, target_type, horizon_bucket)
        mce = cal_curve.mean_calibration_error
    except:
        mce = 1.0  # Assume poorly calibrated if can't compute

    # Quality flags
    is_well_calibrated = mce < 0.10
    has_positive_skill = bss > 0.05
    sufficient_sample = len(pairs) >= 20

    # Generate report ID
    report_id = f"skill_{target_type}_{horizon_bucket}_{period_start.strftime('%Y%m')}"

    metrics = SkillMetrics(
        brier_score=model_brier,
        brier_score_baseline=baseline_brier,
        brier_skill_score=bss,
        directional_accuracy=directional_accuracy,
    )

    return SkillReport(
        report_id=report_id,
        target_type=target_type,
        horizon_bucket=horizon_bucket,
        model_id=model_id,
        period_start=period_start,
        period_end=period_end,
        metrics=metrics,
        sample_size=len(pairs),
        baseline_description=baseline_type,
        is_well_calibrated=is_well_calibrated,
        has_positive_skill=has_positive_skill,
        sufficient_sample=sufficient_sample,
        created_at=datetime.utcnow(),
    )
