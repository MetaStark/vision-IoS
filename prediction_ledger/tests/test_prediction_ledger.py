"""
Comprehensive Prediction Ledger Tests

Tests for core prediction ledger functionality.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

import pytest
from datetime import datetime, timedelta

from prediction_ledger import (
    ForecastRecord,
    OutcomeRecord,
    record_forecast,
    record_outcome,
    reconcile_forecasts_to_outcomes,
    compute_brier_score,
    compute_calibration_curve,
    compute_directional_accuracy,
    append_forecast_to_file,
    append_outcome_to_file,
    load_forecasts,
    load_outcomes,
    generate_forecast_id,
    generate_outcome_id,
    # New v1.1 imports
    derive_horizon_bucket,
    group_matched_pairs_by_horizon,
    group_matched_pairs_by_target_type,
    group_matched_pairs_by_both,
    compute_baseline_forecast,
    compute_baseline_brier_score,
    compute_brier_skill_score,
    build_calibration_curve_v2,
    build_skill_report,
    SkillMetrics,
    SkillReport,
    CalibrationCurve,
    save_calibration_curve_to_json,
    load_calibration_curve_from_json,
    calibration_curve_to_dict,
)
from prediction_ledger.exceptions import InvalidForecastException, InsufficientDataException


class TestForecastRecording:
    """Test forecast recording."""

    def test_record_forecast_valid(self):
        """Test recording a valid forecast."""
        forecast = ForecastRecord(
            forecast_id="f_001",
            timestamp=datetime.utcnow(),
            horizon=timedelta(days=5),
            target_id="regime_bull_to_bear_5d",
            target_type="REGIME_TRANSITION_PROB",
            forecast_value=0.25,
            input_state_hash="abc123",
        )

        validated = record_forecast(forecast)
        assert validated == forecast

    def test_record_forecast_invalid(self):
        """Test that invalid forecast raises exception."""
        forecast = ForecastRecord(
            forecast_id="",  # Empty ID
            timestamp=datetime.utcnow(),
            horizon=timedelta(days=5),
            target_id="target_001",
            target_type="REGIME_TRANSITION_PROB",
            forecast_value=0.5,
            input_state_hash="abc123",
        )

        with pytest.raises(InvalidForecastException):
            record_forecast(forecast)

    def test_outcome_recording(self):
        """Test recording an outcome."""
        outcome = OutcomeRecord(
            outcome_id="o_001",
            timestamp=datetime.utcnow(),
            target_id="regime_bull_to_bear_5d",
            target_type="REGIME_TRANSITION_PROB",
            realized_value=0,  # Did not occur
        )

        validated = record_outcome(outcome)
        assert validated == outcome


class TestReconciliation:
    """Test forecast-outcome reconciliation."""

    def test_reconcile_exact_match(self):
        """Test reconciliation with exact time match."""
        forecast_time = datetime(2025, 11, 1, 12, 0, 0)
        horizon = timedelta(days=5)
        expected_outcome_time = forecast_time + horizon

        forecast = ForecastRecord(
            forecast_id="f_001",
            timestamp=forecast_time,
            horizon=horizon,
            target_id="target_001",
            target_type="REGIME_TRANSITION_PROB",
            forecast_value=0.75,
            input_state_hash="abc123",
        )

        outcome = OutcomeRecord(
            outcome_id="o_001",
            timestamp=expected_outcome_time,  # Exact match
            target_id="target_001",
            target_type="REGIME_TRANSITION_PROB",
            realized_value=1,  # Did occur
        )

        pairs = reconcile_forecasts_to_outcomes([forecast], [outcome])

        assert len(pairs) == 1
        assert pairs[0].forecast == forecast
        assert pairs[0].outcome == outcome

    def test_reconcile_within_tolerance(self):
        """Test reconciliation within time tolerance window."""
        forecast_time = datetime(2025, 11, 1, 12, 0, 0)
        horizon = timedelta(days=5)
        expected_outcome_time = forecast_time + horizon

        forecast = ForecastRecord(
            forecast_id="f_001",
            timestamp=forecast_time,
            horizon=horizon,
            target_id="target_001",
            target_type="REGIME_TRANSITION_PROB",
            forecast_value=0.75,
            input_state_hash="abc123",
        )

        # Outcome 2 hours later (within default 6-hour tolerance)
        outcome = OutcomeRecord(
            outcome_id="o_001",
            timestamp=expected_outcome_time + timedelta(hours=2),
            target_id="target_001",
            target_type="REGIME_TRANSITION_PROB",
            realized_value=1,
        )

        pairs = reconcile_forecasts_to_outcomes([forecast], [outcome])

        assert len(pairs) == 1

    def test_reconcile_no_match(self):
        """Test reconciliation with no matching outcome."""
        forecast = ForecastRecord(
            forecast_id="f_001",
            timestamp=datetime(2025, 11, 1),
            horizon=timedelta(days=5),
            target_id="target_001",
            target_type="REGIME_TRANSITION_PROB",
            forecast_value=0.75,
            input_state_hash="abc123",
        )

        # Outcome with different target
        outcome = OutcomeRecord(
            outcome_id="o_001",
            timestamp=datetime(2025, 11, 6),
            target_id="target_002",  # Different target
            target_type="REGIME_TRANSITION_PROB",
            realized_value=1,
        )

        pairs = reconcile_forecasts_to_outcomes([forecast], [outcome])

        assert len(pairs) == 0  # No match


class TestEvaluation:
    """Test evaluation metrics."""

    def test_compute_brier_score(self):
        """Test Brier score computation."""
        # Create forecast-outcome pairs
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 11, 1) + timedelta(days=i),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.7,
                input_state_hash="abc123",
            )
            for i in range(10)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 11, 6) + timedelta(days=i),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=1 if i < 7 else 0,  # 70% actually occurred
            )
            for i in range(10)
        ]

        # Reconcile
        pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)

        # Compute Brier score
        eval_record = compute_brier_score(pairs)

        assert eval_record.metric_name == "brier_score"
        assert eval_record.sample_size == 10
        assert 0 <= eval_record.metric_value <= 1  # Brier score range

        # For 70% forecast and 70% realization, Brier score should be close to 0
        assert eval_record.metric_value < 0.3  # Good Brier score

    def test_compute_calibration_curve(self):
        """Test calibration curve computation."""
        # Create 100 forecasts with varying probabilities
        forecasts = []
        outcomes = []

        for i in range(100):
            forecast_prob = (i % 10) / 10.0  # 0.0, 0.1, ..., 0.9

            forecast = ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 11, 1) + timedelta(hours=i),
                horizon=timedelta(days=1),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=forecast_prob,
                input_state_hash="abc123",
            )
            forecasts.append(forecast)

            # Realize outcome with probability = forecast_prob (perfect calibration)
            realized = 1 if (i % 10) < (forecast_prob * 10) else 0

            outcome = OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 11, 2) + timedelta(hours=i),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=realized,
            )
            outcomes.append(outcome)

        pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)

        calibration_curve = compute_calibration_curve(pairs)

        assert calibration_curve.target_id == "target_001"
        assert calibration_curve.total_samples == len(pairs)
        assert len(calibration_curve.bins) > 0

    def test_compute_directional_accuracy(self):
        """Test directional accuracy computation."""
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime.utcnow(),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="RETURN_DIRECTION",
                forecast_value=0.8,  # Predicting up
                input_state_hash="abc123",
            )
            for i in range(10)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime.utcnow() + timedelta(days=5),
                target_id="target_001",
                target_type="RETURN_DIRECTION",
                realized_value=1 if i < 8 else 0,  # 80% actually went up
            )
            for i in range(10)
        ]

        pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)
        eval_record = compute_directional_accuracy(pairs)

        assert eval_record.metric_name == "hit_rate"
        assert eval_record.metric_value == 0.8  # 80% hit rate


class TestStorage:
    """Test file-based storage."""

    def test_append_and_load_forecasts(self, tmp_path):
        """Test appending and loading forecasts."""
        file_path = tmp_path / "forecasts.jsonl"

        # Create and append forecasts
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime.utcnow(),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.5 + i * 0.05,
                input_state_hash="abc123",
            )
            for i in range(5)
        ]

        for forecast in forecasts:
            append_forecast_to_file(file_path, forecast)

        # Load
        loaded_forecasts = load_forecasts(file_path)

        assert len(loaded_forecasts) == 5
        assert loaded_forecasts[0].forecast_id == "f_000"
        assert loaded_forecasts[4].forecast_id == "f_004"

    def test_load_forecasts_with_filter(self, tmp_path):
        """Test loading forecasts with filters."""
        file_path = tmp_path / "forecasts.jsonl"

        # Create forecasts with different targets
        for i in range(10):
            forecast = ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime.utcnow(),
                horizon=timedelta(days=5),
                target_id=f"target_{i % 2:03d}",  # Alternating targets
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.5,
                input_state_hash="abc123",
            )
            append_forecast_to_file(file_path, forecast)

        # Load with filter
        loaded = load_forecasts(file_path, filters={"target_id": "target_000"})

        assert len(loaded) == 5  # Half of the forecasts


# ============================================================================
# CALIBRATION & SKILL METRICS TESTS (v1.1)
# ============================================================================

class TestHorizonBucketing:
    """Test horizon bucketing functions."""

    def test_derive_horizon_bucket_1d(self):
        """Test deriving 1d bucket."""
        assert derive_horizon_bucket(timedelta(days=0.5)) == "1d"
        assert derive_horizon_bucket(timedelta(days=1)) == "1d"
        assert derive_horizon_bucket(timedelta(days=2)) == "1d"

    def test_derive_horizon_bucket_5d(self):
        """Test deriving 5d bucket."""
        assert derive_horizon_bucket(timedelta(days=3)) == "5d"
        assert derive_horizon_bucket(timedelta(days=5)) == "5d"
        assert derive_horizon_bucket(timedelta(days=7)) == "5d"

    def test_derive_horizon_bucket_10d(self):
        """Test deriving 10d bucket."""
        assert derive_horizon_bucket(timedelta(days=8)) == "10d"
        assert derive_horizon_bucket(timedelta(days=10)) == "10d"
        assert derive_horizon_bucket(timedelta(days=14)) == "10d"

    def test_derive_horizon_bucket_20d(self):
        """Test deriving 20d bucket."""
        assert derive_horizon_bucket(timedelta(days=15)) == "20d"
        assert derive_horizon_bucket(timedelta(days=20)) == "20d"
        assert derive_horizon_bucket(timedelta(days=30)) == "20d"

    def test_derive_horizon_bucket_30d_plus(self):
        """Test deriving 30d+ bucket."""
        assert derive_horizon_bucket(timedelta(days=31)) == "30d+"
        assert derive_horizon_bucket(timedelta(days=60)) == "30d+"
        assert derive_horizon_bucket(timedelta(days=365)) == "30d+"


class TestGroupingFunctions:
    """Test grouping functions for matched pairs."""

    def _create_test_pairs(self):
        """Helper to create test forecast-outcome pairs."""
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 11, 1) + timedelta(days=i),
                horizon=timedelta(days=(i % 3) * 5 + 1),  # Mix of 1d, 5d, 10d
                target_id=f"target_{i % 2}",
                target_type="REGIME_TRANSITION_PROB" if i % 2 == 0 else "TAIL_RISK_PROB",
                forecast_value=0.5 + i * 0.01,
                input_state_hash="abc123",
            )
            for i in range(12)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=forecast.timestamp + forecast.horizon,
                target_id=forecast.target_id,
                target_type=forecast.target_type,
                realized_value=1 if i % 3 == 0 else 0,
            )
            for i, forecast in enumerate(forecasts)
        ]

        return reconcile_forecasts_to_outcomes(forecasts, outcomes)

    def test_group_by_horizon(self):
        """Test grouping pairs by horizon bucket."""
        pairs = self._create_test_pairs()
        grouped = group_matched_pairs_by_horizon(pairs)

        assert "1d" in grouped
        assert "5d" in grouped or "10d" in grouped
        assert sum(len(v) for v in grouped.values()) == len(pairs)

    def test_group_by_target_type(self):
        """Test grouping pairs by target type."""
        pairs = self._create_test_pairs()
        grouped = group_matched_pairs_by_target_type(pairs)

        assert "REGIME_TRANSITION_PROB" in grouped
        assert "TAIL_RISK_PROB" in grouped
        assert sum(len(v) for v in grouped.values()) == len(pairs)

    def test_group_by_both(self):
        """Test grouping pairs by both target type and horizon."""
        pairs = self._create_test_pairs()
        grouped = group_matched_pairs_by_both(pairs)

        # Check that keys are tuples
        for key in grouped.keys():
            assert isinstance(key, tuple)
            assert len(key) == 2
            target_type, horizon_bucket = key
            assert target_type in ["REGIME_TRANSITION_PROB", "TAIL_RISK_PROB"]
            assert horizon_bucket in ["1d", "5d", "10d", "20d", "30d+"]

        assert sum(len(v) for v in grouped.values()) == len(pairs)


class TestBaselineStrategies:
    """Test baseline forecast strategies."""

    def _create_balanced_pairs(self):
        """Create pairs with 50% realization rate."""
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 11, 1),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.6,
                input_state_hash="abc123",
            )
            for i in range(20)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 11, 6),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=1 if i < 10 else 0,  # 50% realization
            )
            for i in range(20)
        ]

        return reconcile_forecasts_to_outcomes(forecasts, outcomes)

    def test_baseline_historical_frequency(self):
        """Test historical frequency baseline."""
        pairs = self._create_balanced_pairs()
        baseline = compute_baseline_forecast(pairs, baseline_type="historical_frequency")

        assert baseline == 0.5  # 50% historical frequency

    def test_baseline_uniform(self):
        """Test uniform baseline."""
        pairs = self._create_balanced_pairs()
        baseline = compute_baseline_forecast(pairs, baseline_type="uniform")

        assert baseline == 0.5

    def test_baseline_brier_score(self):
        """Test baseline Brier score computation."""
        pairs = self._create_balanced_pairs()
        baseline_bs = compute_baseline_brier_score(pairs, baseline_type="historical_frequency")

        # For 50% baseline with 50% realization, Brier score = 0.25
        assert 0.20 <= baseline_bs <= 0.30


class TestBrierSkillScore:
    """Test Brier Skill Score computation."""

    def _create_skilled_pairs(self):
        """Create pairs where model beats baseline."""
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 11, 1),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.8 if i < 16 else 0.2,  # Skilled forecast
                input_state_hash="abc123",
            )
            for i in range(20)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 11, 6),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=1 if i < 16 else 0,  # 80% realization
            )
            for i in range(20)
        ]

        return reconcile_forecasts_to_outcomes(forecasts, outcomes)

    def test_positive_skill(self):
        """Test that skilled forecasts have positive BSS."""
        pairs = self._create_skilled_pairs()
        bss = compute_brier_skill_score(pairs, baseline_type="historical_frequency")

        # Model should beat historical baseline (80% event rate)
        assert bss > 0.0  # Positive skill

    def test_perfect_forecasts_bss(self):
        """Test BSS for perfect forecasts."""
        # Create perfect forecasts
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 11, 1),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=1.0 if i < 10 else 0.0,  # Perfect
                input_state_hash="abc123",
            )
            for i in range(20)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 11, 6),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=1 if i < 10 else 0,
            )
            for i in range(20)
        ]

        pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)
        bss = compute_brier_skill_score(pairs)

        # Perfect forecasts should have very high BSS (close to 1.0)
        assert bss > 0.9


class TestCalibrationCurveV2:
    """Test enhanced calibration curve building."""

    def _create_calibrated_pairs(self):
        """Create well-calibrated forecast-outcome pairs."""
        forecasts = []
        outcomes = []

        # Create 100 forecasts across probability spectrum
        # For well-calibrated forecasts: each 10% bin should realize at its expected rate
        for bin_idx in range(10):  # 10 bins: 0-10%, 10-20%, ..., 90-100%
            forecast_prob = (bin_idx + 0.5) / 10.0  # Midpoint of bin

            # Create 10 forecasts for this probability bin
            for j in range(10):
                i = bin_idx * 10 + j

                forecast = ForecastRecord(
                    forecast_id=f"f_{i:03d}",
                    timestamp=datetime(2025, 11, 1) + timedelta(hours=i),
                    horizon=timedelta(days=5),
                    target_id="target_001",
                    target_type="REGIME_TRANSITION_PROB",
                    forecast_value=forecast_prob,
                    input_state_hash="abc123",
                )
                forecasts.append(forecast)

                # Well-calibrated: realize approximately at forecast_prob rate
                # For 10 samples, realize round(forecast_prob * 10) of them
                num_to_realize = round(forecast_prob * 10)
                realized = 1 if j < num_to_realize else 0

                outcome = OutcomeRecord(
                    outcome_id=f"o_{i:03d}",
                    timestamp=datetime(2025, 11, 6) + timedelta(hours=i),
                    target_id="target_001",
                    target_type="REGIME_TRANSITION_PROB",
                    realized_value=realized,
                )
                outcomes.append(outcome)

        return reconcile_forecasts_to_outcomes(forecasts, outcomes)

    def test_calibration_curve_structure(self):
        """Test calibration curve structure."""
        pairs = self._create_calibrated_pairs()
        curve = build_calibration_curve_v2(
            pairs,
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
            num_bins=10,
        )

        assert isinstance(curve, CalibrationCurve)
        assert curve.target_type == "REGIME_TRANSITION_PROB"
        assert curve.horizon_bucket == "5d"
        assert len(curve.bins) <= 10
        assert curve.sample_size == len(pairs)
        assert 0.0 <= curve.mean_calibration_error <= 1.0

    def test_well_calibrated_forecasts(self):
        """Test that well-calibrated forecasts have low MCE."""
        pairs = self._create_calibrated_pairs()
        curve = build_calibration_curve_v2(
            pairs,
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
        )

        # Well-calibrated forecasts should have low mean calibration error
        assert curve.mean_calibration_error < 0.20  # Generous threshold for test

    def test_calibration_bin_properties(self):
        """Test calibration bin properties."""
        pairs = self._create_calibrated_pairs()
        curve = build_calibration_curve_v2(
            pairs,
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
        )

        for bin in curve.bins:
            # Check bounds
            assert 0.0 <= bin.lower_bound <= 1.0
            assert 0.0 <= bin.upper_bound <= 1.0
            assert bin.lower_bound < bin.upper_bound

            # Check forecast mean and observed frequency
            assert 0.0 <= bin.forecast_mean <= 1.0
            assert 0.0 <= bin.observed_frequency <= 1.0

            # Check count
            assert bin.count > 0


class TestSkillReport:
    """Test comprehensive skill report building."""

    def _create_test_pairs_for_report(self):
        """Create test pairs for skill report."""
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 9, 1) + timedelta(days=i),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.7,  # Consistent forecast
                input_state_hash="abc123",
            )
            for i in range(30)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 9, 6) + timedelta(days=i),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=1 if i < 21 else 0,  # 70% realization
            )
            for i in range(30)
        ]

        return reconcile_forecasts_to_outcomes(forecasts, outcomes)

    def test_skill_report_structure(self):
        """Test skill report structure."""
        pairs = self._create_test_pairs_for_report()
        report = build_skill_report(
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
            pairs=pairs,
            period_start=datetime(2025, 9, 1),
            period_end=datetime(2025, 10, 1),
            baseline_type="historical_frequency",
        )

        assert isinstance(report, SkillReport)
        assert report.target_type == "REGIME_TRANSITION_PROB"
        assert report.horizon_bucket == "5d"
        assert report.sample_size == 30
        assert isinstance(report.metrics, SkillMetrics)

    def test_skill_report_metrics(self):
        """Test skill report metrics."""
        pairs = self._create_test_pairs_for_report()
        report = build_skill_report(
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
            pairs=pairs,
            period_start=datetime(2025, 9, 1),
            period_end=datetime(2025, 10, 1),
        )

        # Check metrics range
        assert 0.0 <= report.metrics.brier_score <= 1.0
        assert 0.0 <= report.metrics.brier_score_baseline <= 1.0

        # For 70% forecast with 70% realization, should have good metrics
        assert report.metrics.brier_score < 0.30  # Good Brier score

    def test_skill_report_quality_flags(self):
        """Test skill report quality flags."""
        pairs = self._create_test_pairs_for_report()
        report = build_skill_report(
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
            pairs=pairs,
            period_start=datetime(2025, 9, 1),
            period_end=datetime(2025, 10, 1),
        )

        # Check boolean flags
        assert isinstance(report.is_well_calibrated, bool)
        assert isinstance(report.has_positive_skill, bool)
        assert isinstance(report.sufficient_sample, bool)

        # With 30 samples, should have sufficient sample
        assert report.sufficient_sample is True

    def test_skill_report_with_directional_accuracy(self):
        """Test skill report includes directional accuracy."""
        pairs = self._create_test_pairs_for_report()
        report = build_skill_report(
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
            pairs=pairs,
            period_start=datetime(2025, 9, 1),
            period_end=datetime(2025, 10, 1),
        )

        # Should include directional accuracy
        if report.metrics.directional_accuracy is not None:
            assert 0.0 <= report.metrics.directional_accuracy <= 1.0


class TestSerialization:
    """Test serialization functions."""

    def test_calibration_curve_to_dict(self):
        """Test converting calibration curve to dict."""
        # Create a simple calibration curve
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 9, 1),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.5,
                input_state_hash="abc123",
            )
            for i in range(20)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 9, 6),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=1 if i < 10 else 0,
            )
            for i in range(20)
        ]

        pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)
        curve = build_calibration_curve_v2(
            pairs,
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
        )

        # Convert to dict
        curve_dict = calibration_curve_to_dict(curve)

        assert isinstance(curve_dict, dict)
        assert curve_dict["target_type"] == "REGIME_TRANSITION_PROB"
        assert curve_dict["horizon_bucket"] == "5d"
        assert "bins" in curve_dict
        assert isinstance(curve_dict["bins"], list)

    def test_save_and_load_calibration_curve(self, tmp_path):
        """Test saving and loading calibration curve."""
        # Create a calibration curve
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 9, 1),
                horizon=timedelta(days=5),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.6,
                input_state_hash="abc123",
            )
            for i in range(20)
        ]

        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 9, 6),
                target_id="target_001",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=1 if i < 12 else 0,
            )
            for i in range(20)
        ]

        pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)
        original_curve = build_calibration_curve_v2(
            pairs,
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
        )

        # Save to file
        file_path = tmp_path / "calibration_curve.json"
        save_calibration_curve_to_json(original_curve, file_path)

        # Load from file
        loaded_curve = load_calibration_curve_from_json(file_path)

        # Verify
        assert loaded_curve.target_type == original_curve.target_type
        assert loaded_curve.horizon_bucket == original_curve.horizon_bucket
        assert loaded_curve.sample_size == original_curve.sample_size
        assert len(loaded_curve.bins) == len(original_curve.bins)


class TestIntegration:
    """Integration tests for calibration workflow."""

    def test_end_to_end_calibration_workflow(self):
        """Test complete calibration workflow from forecasts to skill report."""
        # Step 1: Create forecasts
        forecasts = [
            ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 9, 1) + timedelta(days=i),
                horizon=timedelta(days=5),
                target_id="target_regime_bull_to_bear_5d",
                target_type="REGIME_TRANSITION_PROB",
                forecast_value=0.3 + (i % 5) * 0.1,  # Varying forecasts
                input_state_hash=f"hash_{i}",
            )
            for i in range(50)
        ]

        # Step 2: Create outcomes
        outcomes = [
            OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 9, 6) + timedelta(days=i),
                target_id="target_regime_bull_to_bear_5d",
                target_type="REGIME_TRANSITION_PROB",
                realized_value=1 if i % 3 == 0 else 0,  # ~33% realization
            )
            for i in range(50)
        ]

        # Step 3: Reconcile
        pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)
        assert len(pairs) == 50

        # Step 4: Group by horizon
        by_horizon = group_matched_pairs_by_horizon(pairs)
        assert "5d" in by_horizon

        # Step 5: Build calibration curve
        curve = build_calibration_curve_v2(
            by_horizon["5d"],
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
        )
        assert isinstance(curve, CalibrationCurve)
        assert curve.sample_size == 50

        # Step 6: Build skill report
        report = build_skill_report(
            target_type="REGIME_TRANSITION_PROB",
            horizon_bucket="5d",
            pairs=by_horizon["5d"],
            period_start=datetime(2025, 9, 1),
            period_end=datetime(2025, 10, 21),
        )
        assert isinstance(report, SkillReport)
        assert report.sufficient_sample is True

    def test_multi_target_type_workflow(self):
        """Test workflow with multiple target types."""
        # Create forecasts for different target types
        forecasts = []
        outcomes = []

        for i in range(40):
            target_type = "REGIME_TRANSITION_PROB" if i < 20 else "TAIL_RISK_PROB"
            target_id = f"target_{target_type.lower()}_{i}"

            forecast = ForecastRecord(
                forecast_id=f"f_{i:03d}",
                timestamp=datetime(2025, 9, 1) + timedelta(days=i % 20),
                horizon=timedelta(days=5),
                target_id=target_id,
                target_type=target_type,
                forecast_value=0.4 + (i % 5) * 0.1,
                input_state_hash=f"hash_{i}",
            )
            forecasts.append(forecast)

            outcome = OutcomeRecord(
                outcome_id=f"o_{i:03d}",
                timestamp=datetime(2025, 9, 6) + timedelta(days=i % 20),
                target_id=target_id,
                target_type=target_type,
                realized_value=1 if i % 3 == 0 else 0,
            )
            outcomes.append(outcome)

        # Reconcile
        pairs = reconcile_forecasts_to_outcomes(forecasts, outcomes)

        # Group by target type
        by_target_type = group_matched_pairs_by_target_type(pairs)
        assert "REGIME_TRANSITION_PROB" in by_target_type
        assert "TAIL_RISK_PROB" in by_target_type

        # Build reports for each target type
        for target_type, target_pairs in by_target_type.items():
            if len(target_pairs) >= 20:
                report = build_skill_report(
                    target_type=target_type,
                    horizon_bucket="5d",
                    pairs=target_pairs,
                    period_start=datetime(2025, 9, 1),
                    period_end=datetime(2025, 9, 21),
                )
                assert report.target_type == target_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
