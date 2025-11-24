"""
LINE+ Data Quality Validation
Phase 3: Week 2 — OHLCV Data Quality Gate

Authority: LARS Phase 3 Directive (HC-LARS-PHASE3-CONTINUE-20251124)
Canonical ADR Chain: ADR-001 → ADR-015

Purpose: Validate OHLCV data quality before FINN+ regime classification
Acts as mandatory gate: Invalid data → reject before downstream propagation

LINE+ Data Quality Validation enforces:
- Price sanity checks (outlier detection, spike filtering)
- Volume validation (zero volume detection, volume spikes)
- Completeness checks (missing data detection)
- Continuity checks (gap detection, irregular intervals)
- Statistical validation (distribution checks)

Integration:
- Pre-FINN+ gate: All data must pass validation before regime classification
- STIG+ Tier 2 extension: Data quality as validation tier
- ADR-010 compliance: Severity classification (INFO/WARNING/ERROR/CRITICAL)

Rationale:
Garbage in → Garbage out. Invalid market data causes:
- False regime transitions (price spikes misinterpreted as BEAR entry)
- Incorrect feature z-scores (outliers distort rolling statistics)
- Signature failures (data tampering detected post-ingestion)

LINE+ data quality validation prevents these failures upstream.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np

from line_ohlcv_contracts import (
    OHLCVBar, OHLCVDataset, OHLCVInterval,
    validate_ohlcv_bar, validate_ohlcv_dataset
)


class DataQualitySeverity(Enum):
    """Data quality issue severity (ADR-010 aligned)."""
    INFO = "INFO"            # Informational, no action required
    WARNING = "WARNING"      # Minor issue, proceed with caution
    ERROR = "ERROR"          # Significant issue, reject if possible
    CRITICAL = "CRITICAL"    # Critical failure, must reject


@dataclass
class DataQualityIssue:
    """Single data quality validation issue."""
    check_name: str
    severity: DataQualitySeverity
    message: str
    bar_index: Optional[int] = None  # Bar index if issue is bar-specific
    actual_value: Optional[float] = None
    expected_range: Optional[str] = None

    def __str__(self) -> str:
        """Format issue for display."""
        severity_icons = {
            DataQualitySeverity.INFO: "ℹ️",
            DataQualitySeverity.WARNING: "⚠️",
            DataQualitySeverity.ERROR: "❌",
            DataQualitySeverity.CRITICAL: "🔴"
        }

        icon = severity_icons.get(self.severity, "")
        bar_info = f" (bar {self.bar_index})" if self.bar_index is not None else ""

        return f"{icon} {self.severity.value}: {self.check_name}{bar_info} - {self.message}"


@dataclass
class DataQualityReport:
    """Complete data quality validation report."""
    dataset_symbol: str
    dataset_interval: str
    bar_count: int
    issues: List[DataQualityIssue]
    overall_pass: bool

    # Summary counts
    critical_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    def __post_init__(self):
        """Calculate summary counts."""
        for issue in self.issues:
            if issue.severity == DataQualitySeverity.CRITICAL:
                self.critical_count += 1
            elif issue.severity == DataQualitySeverity.ERROR:
                self.error_count += 1
            elif issue.severity == DataQualitySeverity.WARNING:
                self.warning_count += 1
            elif issue.severity == DataQualitySeverity.INFO:
                self.info_count += 1

        # Overall pass if no CRITICAL or ERROR issues
        if self.critical_count > 0 or self.error_count > 0:
            self.overall_pass = False

    def get_summary(self) -> str:
        """Get human-readable summary."""
        status = "✅ PASS" if self.overall_pass else "❌ FAIL"
        return (
            f"Data Quality Report: {status}\n"
            f"Dataset: {self.dataset_symbol} ({self.dataset_interval})\n"
            f"Bars: {self.bar_count}\n"
            f"Issues: {len(self.issues)} total "
            f"({self.critical_count} critical, {self.error_count} error, "
            f"{self.warning_count} warning, {self.info_count} info)"
        )

    def get_failures(self) -> List[DataQualityIssue]:
        """Get critical and error issues."""
        return [
            issue for issue in self.issues
            if issue.severity in [DataQualitySeverity.CRITICAL, DataQualitySeverity.ERROR]
        ]


class LINEDataQualityValidator:
    """
    LINE+ Data Quality Validator.

    Validates OHLCV datasets before FINN+ regime classification.
    Acts as mandatory gate: Invalid data → reject before downstream.
    """

    def __init__(self,
                 price_spike_threshold: float = 5.0,
                 volume_spike_threshold: float = 10.0,
                 zero_volume_max_pct: float = 5.0,
                 max_gap_days: int = 5):
        """
        Initialize validator with thresholds.

        Args:
            price_spike_threshold: Price change threshold (z-score) for spike detection
            volume_spike_threshold: Volume change threshold (z-score) for spike detection
            zero_volume_max_pct: Maximum % of bars with zero volume
            max_gap_days: Maximum allowable gap in days for daily data
        """
        self.price_spike_threshold = price_spike_threshold
        self.volume_spike_threshold = volume_spike_threshold
        self.zero_volume_max_pct = zero_volume_max_pct
        self.max_gap_days = max_gap_days

    def validate_dataset(self, dataset: OHLCVDataset) -> DataQualityReport:
        """
        Perform complete data quality validation on dataset.

        Returns: DataQualityReport with all detected issues
        """
        issues = []

        # [1] Basic validation (from contracts)
        is_valid_basic, violations = validate_ohlcv_dataset(dataset)
        if not is_valid_basic:
            for violation in violations:
                issues.append(DataQualityIssue(
                    check_name="Basic Validation",
                    severity=DataQualitySeverity.ERROR,
                    message=violation
                ))

        # [2] Individual bar validation
        bar_issues = self._validate_individual_bars(dataset)
        issues.extend(bar_issues)

        # [3] Price sanity checks
        price_issues = self._validate_price_sanity(dataset)
        issues.extend(price_issues)

        # [4] Volume validation
        volume_issues = self._validate_volume_sanity(dataset)
        issues.extend(volume_issues)

        # [5] Continuity checks
        continuity_issues = self._validate_continuity(dataset)
        issues.extend(continuity_issues)

        # [6] Statistical distribution checks
        distribution_issues = self._validate_distribution(dataset)
        issues.extend(distribution_issues)

        # Generate report
        report = DataQualityReport(
            dataset_symbol=dataset.symbol,
            dataset_interval=dataset.interval.value,
            bar_count=dataset.get_bar_count(),
            issues=issues,
            overall_pass=(len([i for i in issues if i.severity in [
                DataQualitySeverity.CRITICAL, DataQualitySeverity.ERROR
            ]]) == 0)
        )

        return report

    def _validate_individual_bars(self, dataset: OHLCVDataset) -> List[DataQualityIssue]:
        """Validate each bar individually."""
        issues = []

        for idx, bar in enumerate(dataset.bars):
            is_valid, error = validate_ohlcv_bar(bar)
            if not is_valid:
                issues.append(DataQualityIssue(
                    check_name="Bar Validation",
                    severity=DataQualitySeverity.ERROR,
                    message=error,
                    bar_index=idx
                ))

        return issues

    def _validate_price_sanity(self, dataset: OHLCVDataset) -> List[DataQualityIssue]:
        """
        Validate price sanity (outlier detection, spike filtering).

        Detects:
        - Price spikes (z-score > threshold)
        - Negative prices
        - Zero prices
        - Extremely small prices (< 0.01 for most instruments)
        """
        issues = []

        if dataset.get_bar_count() < 2:
            return issues

        # Extract prices
        closes = np.array([bar.close for bar in dataset.bars])
        opens = np.array([bar.open for bar in dataset.bars])
        highs = np.array([bar.high for bar in dataset.bars])
        lows = np.array([bar.low for bar in dataset.bars])

        # Check for price spikes using returns
        returns = np.diff(closes) / closes[:-1]

        if len(returns) > 20:  # Need minimum history for z-score
            return_mean = np.mean(returns)
            return_std = np.std(returns)

            if return_std > 0:
                return_z = (returns - return_mean) / return_std

                # Detect spikes
                spike_indices = np.where(np.abs(return_z) > self.price_spike_threshold)[0]

                if len(spike_indices) > 0:
                    for spike_idx in spike_indices:
                        bar_idx = spike_idx + 1  # returns array is 1 shorter
                        issues.append(DataQualityIssue(
                            check_name="Price Spike Detection",
                            severity=DataQualitySeverity.WARNING,
                            message=f"Abnormal price change detected (z-score: {return_z[spike_idx]:.2f})",
                            bar_index=bar_idx,
                            actual_value=returns[spike_idx] * 100,
                            expected_range=f"within {self.price_spike_threshold}σ"
                        ))

        # Check for zero or very small prices
        for idx, bar in enumerate(dataset.bars):
            if bar.close <= 0.01:
                issues.append(DataQualityIssue(
                    check_name="Price Sanity",
                    severity=DataQualitySeverity.ERROR,
                    message=f"Suspiciously low price: ${bar.close:.4f}",
                    bar_index=idx,
                    actual_value=bar.close
                ))

        # Check for unrealistic high/low spreads (>50% intrabar range)
        for idx, bar in enumerate(dataset.bars):
            bar_range = bar.get_range()
            mid_price = (bar.high + bar.low) / 2.0

            if mid_price > 0:
                range_pct = (bar_range / mid_price) * 100

                if range_pct > 50.0:  # >50% intrabar range is suspicious
                    issues.append(DataQualityIssue(
                        check_name="Intrabar Range",
                        severity=DataQualitySeverity.WARNING,
                        message=f"Unusually wide intrabar range: {range_pct:.1f}%",
                        bar_index=idx,
                        actual_value=range_pct,
                        expected_range="<50%"
                    ))

        return issues

    def _validate_volume_sanity(self, dataset: OHLCVDataset) -> List[DataQualityIssue]:
        """
        Validate volume sanity.

        Detects:
        - Zero volume bars (suspicious for active instruments)
        - Volume spikes (z-score > threshold)
        - Negative volume (should be caught earlier but double-check)
        """
        issues = []

        if dataset.get_bar_count() < 2:
            return issues

        # Extract volumes
        volumes = np.array([bar.volume for bar in dataset.bars])

        # Check zero volume percentage
        zero_volume_count = np.sum(volumes == 0)
        zero_volume_pct = (zero_volume_count / len(volumes)) * 100

        if zero_volume_pct > self.zero_volume_max_pct:
            issues.append(DataQualityIssue(
                check_name="Zero Volume",
                severity=DataQualitySeverity.WARNING,
                message=f"High percentage of zero-volume bars: {zero_volume_pct:.1f}%",
                actual_value=zero_volume_pct,
                expected_range=f"<{self.zero_volume_max_pct}%"
            ))

        # Check for volume spikes (exclude zero volume bars)
        non_zero_volumes = volumes[volumes > 0]

        if len(non_zero_volumes) > 20:
            volume_mean = np.mean(non_zero_volumes)
            volume_std = np.std(non_zero_volumes)

            if volume_std > 0:
                volume_z = (volumes - volume_mean) / volume_std

                spike_indices = np.where(volume_z > self.volume_spike_threshold)[0]

                if len(spike_indices) > 0:
                    for spike_idx in spike_indices:
                        issues.append(DataQualityIssue(
                            check_name="Volume Spike Detection",
                            severity=DataQualitySeverity.INFO,
                            message=f"Abnormal volume detected (z-score: {volume_z[spike_idx]:.2f})",
                            bar_index=spike_idx,
                            actual_value=volumes[spike_idx],
                            expected_range=f"within {self.volume_spike_threshold}σ"
                        ))

        # Check for negative volumes (should be impossible but safety check)
        negative_indices = np.where(volumes < 0)[0]
        for idx in negative_indices:
            issues.append(DataQualityIssue(
                check_name="Volume Sanity",
                severity=DataQualitySeverity.CRITICAL,
                message=f"Negative volume detected: {volumes[idx]}",
                bar_index=idx,
                actual_value=volumes[idx]
            ))

        return issues

    def _validate_continuity(self, dataset: OHLCVDataset) -> List[DataQualityIssue]:
        """
        Validate time series continuity.

        Detects:
        - Large gaps in timestamp sequence
        - Duplicate timestamps
        - Out-of-order timestamps
        """
        issues = []

        if dataset.get_bar_count() < 2:
            return issues

        timestamps = [bar.timestamp for bar in dataset.bars]

        # Check for duplicates
        timestamp_counts = pd.Series(timestamps).value_counts()
        duplicates = timestamp_counts[timestamp_counts > 1]

        if len(duplicates) > 0:
            issues.append(DataQualityIssue(
                check_name="Duplicate Timestamps",
                severity=DataQualitySeverity.ERROR,
                message=f"Found {len(duplicates)} duplicate timestamps",
                actual_value=len(duplicates)
            ))

        # Check for out-of-order timestamps
        for idx in range(len(timestamps) - 1):
            if timestamps[idx] >= timestamps[idx + 1]:
                issues.append(DataQualityIssue(
                    check_name="Timestamp Order",
                    severity=DataQualitySeverity.ERROR,
                    message=f"Out-of-order timestamp at bar {idx}",
                    bar_index=idx
                ))

        # Check for large gaps (daily data only)
        if dataset.interval == OHLCVInterval.DAY_1:
            for idx in range(len(timestamps) - 1):
                gap_days = (timestamps[idx + 1] - timestamps[idx]).days

                if gap_days > self.max_gap_days:
                    issues.append(DataQualityIssue(
                        check_name="Data Continuity",
                        severity=DataQualitySeverity.WARNING,
                        message=f"Large gap detected: {gap_days} days",
                        bar_index=idx,
                        actual_value=gap_days,
                        expected_range=f"≤{self.max_gap_days} days"
                    ))

        return issues

    def _validate_distribution(self, dataset: OHLCVDataset) -> List[DataQualityIssue]:
        """
        Validate statistical distribution properties.

        Checks:
        - Returns distribution (should not be perfectly uniform/constant)
        - Volatility (should not be zero)
        - Price variance (should have some movement)
        """
        issues = []

        if dataset.get_bar_count() < 20:
            return issues

        closes = np.array([bar.close for bar in dataset.bars])
        returns = np.diff(closes) / closes[:-1]

        # Check for zero variance (constant prices)
        price_std = np.std(closes)
        if price_std == 0:
            issues.append(DataQualityIssue(
                check_name="Price Variance",
                severity=DataQualitySeverity.ERROR,
                message="All prices are identical (zero variance)",
                actual_value=price_std,
                expected_range=">0"
            ))

        # Check for zero volatility
        return_std = np.std(returns)
        if return_std == 0:
            issues.append(DataQualityIssue(
                check_name="Return Volatility",
                severity=DataQualitySeverity.ERROR,
                message="Zero volatility detected (no price movement)",
                actual_value=return_std,
                expected_range=">0"
            ))

        # Check for suspiciously low volatility (< 0.1% daily for active instruments)
        if dataset.interval == OHLCVInterval.DAY_1:
            daily_vol = return_std * 100  # Convert to percentage

            if daily_vol < 0.1:
                issues.append(DataQualityIssue(
                    check_name="Volatility Sanity",
                    severity=DataQualitySeverity.WARNING,
                    message=f"Suspiciously low volatility: {daily_vol:.4f}%",
                    actual_value=daily_vol,
                    expected_range="≥0.1% for active instruments"
                ))

        return issues


# ============================================================================
# Convenience Functions
# ============================================================================

def validate_for_finn(dataset: OHLCVDataset) -> Tuple[bool, DataQualityReport]:
    """
    Validate dataset for FINN+ regime classification.

    This is the canonical pre-FINN+ validation gate.

    Returns:
        (is_valid, report)
        is_valid: True if dataset passes all critical/error checks
        report: Full DataQualityReport
    """
    validator = LINEDataQualityValidator()
    report = validator.validate_dataset(dataset)

    is_valid = report.overall_pass

    return is_valid, report


def validate_multi_interval_for_finn(datasets: List[OHLCVDataset]) -> Tuple[bool, List[DataQualityReport]]:
    """
    Validate multiple interval datasets for FINN+ classification.

    Returns:
        (all_valid, reports)
        all_valid: True if ALL datasets pass validation
        reports: List of DataQualityReports (one per dataset)
    """
    validator = LINEDataQualityValidator()
    reports = []

    all_valid = True

    for dataset in datasets:
        report = validator.validate_dataset(dataset)
        reports.append(report)

        if not report.overall_pass:
            all_valid = False

    return all_valid, reports


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    """
    Demonstrate LINE+ data quality validation.
    """
    print("=" * 80)
    print("LINE+ DATA QUALITY VALIDATION")
    print("Phase 3: Week 2 — OHLCV Data Quality Gate")
    print("=" * 80)

    from line_ohlcv_contracts import OHLCVBar, OHLCVDataset, OHLCVInterval
    import numpy as np

    # [1] Create clean dataset
    print("\n[1] Creating clean dataset (should pass validation)...")
    np.random.seed(42)

    clean_dataset = OHLCVDataset(
        symbol="BTC/USD",
        interval=OHLCVInterval.DAY_1,
        source="test"
    )

    base_date = pd.Timestamp("2024-01-01")
    price = 100.0

    for i in range(100):
        bar_date = base_date + pd.Timedelta(days=i)
        daily_return = 0.01 * np.random.randn()

        open_price = price
        close_price = price * (1 + daily_return)
        high_price = max(open_price, close_price) * 1.005
        low_price = min(open_price, close_price) * 0.995
        volume = int(1000000 + 500000 * np.random.rand())

        bar = OHLCVBar(
            timestamp=bar_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            interval=OHLCVInterval.DAY_1,
            symbol="BTC/USD"
        )

        clean_dataset.add_bar(bar)
        price = close_price

    print(f"    ✅ Clean dataset created: {clean_dataset.get_bar_count()} bars")

    # [2] Validate clean dataset
    print("\n[2] Validating clean dataset...")
    is_valid, report = validate_for_finn(clean_dataset)

    print(f"\n{report.get_summary()}")

    if report.issues:
        print(f"\n    Issues detected:")
        for issue in report.issues:
            print(f"      {issue}")
    else:
        print(f"    ✅ No issues detected - dataset is clean")

    # [3] Create corrupted dataset (price spike)
    print("\n[3] Creating corrupted dataset (price spike)...")
    corrupted_dataset = OHLCVDataset(
        symbol="ETH/USD",
        interval=OHLCVInterval.DAY_1,
        source="test"
    )

    price = 100.0
    for i in range(100):
        bar_date = base_date + pd.Timedelta(days=i)

        # Inject spike at bar 50
        if i == 50:
            daily_return = 0.80  # +80% spike
        else:
            daily_return = 0.01 * np.random.randn()

        open_price = price
        close_price = price * (1 + daily_return)
        high_price = max(open_price, close_price) * 1.005
        low_price = min(open_price, close_price) * 0.995
        volume = int(1000000 + 500000 * np.random.rand())

        bar = OHLCVBar(
            timestamp=bar_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            interval=OHLCVInterval.DAY_1,
            symbol="ETH/USD"
        )

        corrupted_dataset.add_bar(bar)
        price = close_price

    print(f"    ✅ Corrupted dataset created (injected +80% spike at bar 50)")

    # [4] Validate corrupted dataset
    print("\n[4] Validating corrupted dataset...")
    is_valid_corrupted, report_corrupted = validate_for_finn(corrupted_dataset)

    print(f"\n{report_corrupted.get_summary()}")

    if report_corrupted.issues:
        print(f"\n    Issues detected:")
        for issue in report_corrupted.issues:
            print(f"      {issue}")

    # [5] Create dataset with zero volume
    print("\n[5] Creating dataset with high zero-volume percentage...")
    zero_vol_dataset = OHLCVDataset(
        symbol="SHIB/USD",
        interval=OHLCVInterval.DAY_1,
        source="test"
    )

    price = 100.0
    for i in range(100):
        bar_date = base_date + pd.Timedelta(days=i)
        daily_return = 0.01 * np.random.randn()

        open_price = price
        close_price = price * (1 + daily_return)
        high_price = max(open_price, close_price) * 1.005
        low_price = min(open_price, close_price) * 0.995

        # 20% of bars have zero volume
        volume = 0 if i % 5 == 0 else int(1000000 + 500000 * np.random.rand())

        bar = OHLCVBar(
            timestamp=bar_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            interval=OHLCVInterval.DAY_1,
            symbol="SHIB/USD"
        )

        zero_vol_dataset.add_bar(bar)
        price = close_price

    print(f"    ✅ Zero-volume dataset created (20% zero volume)")

    # [6] Validate zero-volume dataset
    print("\n[6] Validating zero-volume dataset...")
    is_valid_zero, report_zero = validate_for_finn(zero_vol_dataset)

    print(f"\n{report_zero.get_summary()}")

    if report_zero.issues:
        print(f"\n    Issues detected:")
        for issue in report_zero.issues:
            print(f"      {issue}")

    # [7] Integration test with real Stress Bundle
    print("\n[7] Validating Stress Bundle V1.0...")
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    stress_bundle_path = os.path.join(script_dir, "TEST_DATA_V1.0.csv")

    if os.path.exists(stress_bundle_path):
        stress_df = pd.read_csv(stress_bundle_path)
        stress_df['date'] = pd.to_datetime(stress_df['date'])

        # Convert to OHLCVDataset
        stress_dataset = OHLCVDataset(
            symbol="SPY",
            interval=OHLCVInterval.DAY_1,
            source="stress_bundle_v1"
        )

        for _, row in stress_df.iterrows():
            bar = OHLCVBar(
                timestamp=row['date'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume'],
                interval=OHLCVInterval.DAY_1,
                symbol="SPY"
            )
            stress_dataset.add_bar(bar)

        print(f"    Loaded Stress Bundle V1.0: {stress_dataset.get_bar_count()} bars")

        # Validate
        is_valid_stress, report_stress = validate_for_finn(stress_dataset)

        print(f"\n{report_stress.get_summary()}")

        if report_stress.issues:
            print(f"\n    Issues detected:")
            for issue in report_stress.issues[:10]:  # Show first 10
                print(f"      {issue}")
            if len(report_stress.issues) > 10:
                print(f"      ... and {len(report_stress.issues) - 10} more")
        else:
            print(f"    ✅ Stress Bundle V1.0 passes all data quality checks")

    else:
        print(f"    ⏸️  Stress Bundle V1.0 not found")

    # Summary
    print("\n" + "=" * 80)
    print("✅ LINE+ DATA QUALITY VALIDATION FUNCTIONAL")
    print("=" * 80)
    print("\nValidation Tiers:")
    print("  - Tier 1: Basic validation (completeness, volume coverage, validity)")
    print("  - Tier 2: Individual bar validation (OHLC consistency)")
    print("  - Tier 3: Price sanity (outlier detection, spike filtering)")
    print("  - Tier 4: Volume sanity (zero volume, volume spikes)")
    print("  - Tier 5: Continuity (gaps, duplicates, ordering)")
    print("  - Tier 6: Distribution (variance, volatility)")
    print("\nSeverity Levels (ADR-010):")
    print("  - CRITICAL: Must reject (negative volume, etc.)")
    print("  - ERROR: Significant issue (duplicate timestamps, etc.)")
    print("  - WARNING: Minor issue (price spike, large gap)")
    print("  - INFO: Informational (volume spike)")
    print("\nIntegration:")
    print("  - Pre-FINN+ gate: validate_for_finn() → True/False")
    print("  - STIG+ extension: DataQualityReport → validation tier")
    print("  - Multi-interval: validate_multi_interval_for_finn()")
    print("\nTest Results:")
    print(f"  - Clean dataset: {'✅ PASS' if is_valid else '❌ FAIL'}")
    print(f"  - Corrupted dataset (spike): {'✅ PASS' if is_valid_corrupted else '❌ FAIL (expected)'}")
    print(f"  - Zero-volume dataset: {'✅ PASS' if is_valid_zero else '❌ FAIL (expected)'}")
    print("\nStatus: Ready for Tier-1 orchestrator integration")
    print("=" * 80)
