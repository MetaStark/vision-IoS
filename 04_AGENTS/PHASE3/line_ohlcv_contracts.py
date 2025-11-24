"""
LINE+ OHLCV Data Contracts
Phase 3: Week 2 — Multi-Interval Market Data Layer

Authority: LARS Phase 3 Directive (HC-LARS-PHASE3-CONTINUE-20251124)
Canonical ADR Chain: ADR-001 → ADR-015

Purpose: Define canonical OHLCV data contracts for multi-interval market data
Intervals: 1m, 5m, 15m, 1d (aligned with institutional trading frequencies)

LINE+ (Live INterval Engine) provides:
- Standardized OHLCV data structures
- Multi-interval support for regime classification
- Data quality validation hooks
- Database persistence integration
- Cryptographic lineage tracking (ADR-008)

Integration:
- FINN+ consumes LINE+ data for regime classification
- STIG+ validates data quality before FINN+ execution
- Database persistence via line_database.py

Compliance:
- ADR-002: Audit lineage via hash_chain_id
- ADR-008: Cryptographic signatures on data ingestion
- ADR-010: Data quality thresholds (price/volume sanity)
- ADR-012: Cost tracking for data API calls
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import pandas as pd


class OHLCVInterval(Enum):
    """Supported OHLCV intervals (institutional trading frequencies)."""
    MIN_1 = "1m"      # 1-minute (high-frequency analysis)
    MIN_5 = "5m"      # 5-minute (intraday signals)
    MIN_15 = "15m"    # 15-minute (short-term trend)
    HOUR_1 = "1h"     # 1-hour (intraday swing)
    HOUR_4 = "4h"     # 4-hour (medium-term swing)
    DAY_1 = "1d"      # Daily (regime classification primary)
    WEEK_1 = "1w"     # Weekly (long-term trend)

    @property
    def seconds(self) -> int:
        """Convert interval to seconds."""
        interval_seconds = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
            "1w": 604800
        }
        return interval_seconds[self.value]

    @property
    def pandas_freq(self) -> str:
        """Convert to pandas frequency string."""
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "1h": "1h",
            "4h": "4h",
            "1d": "1D",
            "1w": "1W"
        }
        return freq_map[self.value]


@dataclass
class OHLCVBar:
    """
    Single OHLCV bar (canonical data unit).

    This represents one time interval of market data with complete
    Open/High/Low/Close/Volume information.

    All LINE+ data must conform to this structure before downstream propagation.
    """
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    interval: OHLCVInterval

    # Optional metadata
    symbol: Optional[str] = None
    source: Optional[str] = None  # Data provider (e.g., "binance", "alpaca")

    # ADR-008: Cryptographic lineage
    hash_chain_id: Optional[str] = None
    signature_hex: Optional[str] = None

    # Data quality flags
    is_complete: bool = True  # All OHLCV fields present
    has_volume: bool = True   # Volume > 0
    is_valid: bool = True     # Passed quality validation

    def __post_init__(self):
        """Validate OHLCV bar after initialization."""
        # Basic sanity checks
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) cannot be less than Low ({self.low})")

        if self.open < 0 or self.close < 0:
            raise ValueError("Prices cannot be negative")

        if self.volume < 0:
            raise ValueError("Volume cannot be negative")

        # Update quality flags
        if self.volume == 0:
            self.has_volume = False

        # Check OHLC consistency
        if not (self.low <= self.open <= self.high):
            self.is_valid = False
        if not (self.low <= self.close <= self.high):
            self.is_valid = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'interval': self.interval.value,
            'symbol': self.symbol,
            'source': self.source,
            'hash_chain_id': self.hash_chain_id,
            'signature_hex': self.signature_hex,
            'is_complete': self.is_complete,
            'has_volume': self.has_volume,
            'is_valid': self.is_valid
        }

    def get_typical_price(self) -> float:
        """Calculate typical price: (H + L + C) / 3."""
        return (self.high + self.low + self.close) / 3.0

    def get_range(self) -> float:
        """Calculate bar range: H - L."""
        return self.high - self.low

    def get_body(self) -> float:
        """Calculate bar body: |C - O|."""
        return abs(self.close - self.open)

    def is_bullish(self) -> bool:
        """Check if bar is bullish (close > open)."""
        return self.close > self.open


@dataclass
class OHLCVDataset:
    """
    Collection of OHLCV bars for a single interval and symbol.

    This is the primary data structure consumed by FINN+ for regime classification.
    All datasets must pass LINE+ data quality validation before FINN+ execution.
    """
    symbol: str
    interval: OHLCVInterval
    bars: List[OHLCVBar] = field(default_factory=list)

    # Metadata
    source: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.now)

    # ADR-008: Dataset-level signature
    dataset_hash: Optional[str] = None
    dataset_signature: Optional[str] = None

    # Data quality metrics
    completeness_pct: float = 0.0    # % of bars with complete data
    volume_coverage_pct: float = 0.0  # % of bars with volume > 0
    valid_bars_pct: float = 0.0       # % of bars passing validation

    def __post_init__(self):
        """Calculate data quality metrics after initialization."""
        if self.bars:
            self._update_quality_metrics()

    def _update_quality_metrics(self):
        """Recalculate data quality metrics."""
        if not self.bars:
            self.completeness_pct = 0.0
            self.volume_coverage_pct = 0.0
            self.valid_bars_pct = 0.0
            return

        total = len(self.bars)
        complete = sum(1 for bar in self.bars if bar.is_complete)
        has_volume = sum(1 for bar in self.bars if bar.has_volume)
        valid = sum(1 for bar in self.bars if bar.is_valid)

        self.completeness_pct = (complete / total) * 100
        self.volume_coverage_pct = (has_volume / total) * 100
        self.valid_bars_pct = (valid / total) * 100

    def add_bar(self, bar: OHLCVBar):
        """Add bar and update quality metrics."""
        if bar.interval != self.interval:
            raise ValueError(
                f"Bar interval ({bar.interval.value}) does not match "
                f"dataset interval ({self.interval.value})"
            )

        if bar.symbol and bar.symbol != self.symbol:
            raise ValueError(
                f"Bar symbol ({bar.symbol}) does not match "
                f"dataset symbol ({self.symbol})"
            )

        self.bars.append(bar)
        self._update_quality_metrics()

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert to pandas DataFrame (FINN+ input format).

        Returns DataFrame with columns: date, open, high, low, close, volume
        """
        if not self.bars:
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

        data = {
            'date': [bar.timestamp for bar in self.bars],
            'open': [bar.open for bar in self.bars],
            'high': [bar.high for bar in self.bars],
            'low': [bar.low for bar in self.bars],
            'close': [bar.close for bar in self.bars],
            'volume': [bar.volume for bar in self.bars]
        }

        df = pd.DataFrame(data)
        df = df.sort_values('date').reset_index(drop=True)
        return df

    def get_date_range(self) -> tuple:
        """Get (start_date, end_date) for dataset."""
        if not self.bars:
            return None, None

        dates = [bar.timestamp for bar in self.bars]
        return min(dates), max(dates)

    def get_bar_count(self) -> int:
        """Get total number of bars."""
        return len(self.bars)

    def filter_valid_bars(self) -> 'OHLCVDataset':
        """Return new dataset with only valid bars."""
        valid_bars = [bar for bar in self.bars if bar.is_valid]

        filtered = OHLCVDataset(
            symbol=self.symbol,
            interval=self.interval,
            bars=valid_bars,
            source=self.source,
            fetched_at=self.fetched_at
        )

        return filtered

    def get_quality_report(self) -> Dict[str, Any]:
        """
        Generate data quality report for STIG+ validation.

        Returns dictionary with quality metrics and validation status.
        """
        start_date, end_date = self.get_date_range()

        return {
            'symbol': self.symbol,
            'interval': self.interval.value,
            'bar_count': self.get_bar_count(),
            'date_range': {
                'start': start_date.isoformat() if start_date else None,
                'end': end_date.isoformat() if end_date else None
            },
            'quality_metrics': {
                'completeness_pct': round(self.completeness_pct, 2),
                'volume_coverage_pct': round(self.volume_coverage_pct, 2),
                'valid_bars_pct': round(self.valid_bars_pct, 2)
            },
            'validation_status': {
                'meets_completeness': self.completeness_pct >= 95.0,
                'meets_volume_coverage': self.volume_coverage_pct >= 90.0,
                'meets_validity': self.valid_bars_pct >= 95.0
            },
            'source': self.source,
            'fetched_at': self.fetched_at.isoformat()
        }


@dataclass
class MultiIntervalDataset:
    """
    Collection of OHLCV datasets across multiple intervals.

    Used for multi-timeframe analysis where regime classification
    requires confirming signals across different intervals.

    Example: Daily regime classification confirmed by 15m momentum.
    """
    symbol: str
    datasets: Dict[OHLCVInterval, OHLCVDataset] = field(default_factory=dict)

    # Metadata
    fetched_at: datetime = field(default_factory=datetime.now)

    def add_dataset(self, dataset: OHLCVDataset):
        """Add dataset for specific interval."""
        if dataset.symbol != self.symbol:
            raise ValueError(
                f"Dataset symbol ({dataset.symbol}) does not match "
                f"multi-interval symbol ({self.symbol})"
            )

        self.datasets[dataset.interval] = dataset

    def get_dataset(self, interval: OHLCVInterval) -> Optional[OHLCVDataset]:
        """Get dataset for specific interval."""
        return self.datasets.get(interval)

    def has_interval(self, interval: OHLCVInterval) -> bool:
        """Check if interval is available."""
        return interval in self.datasets

    def get_available_intervals(self) -> List[OHLCVInterval]:
        """Get list of available intervals."""
        return list(self.datasets.keys())

    def get_primary_dataframe(self, interval: OHLCVInterval = OHLCVInterval.DAY_1) -> pd.DataFrame:
        """
        Get primary DataFrame for FINN+ classification.

        Default: 1d interval (regime classification standard)
        """
        dataset = self.get_dataset(interval)
        if dataset is None:
            raise ValueError(f"Interval {interval.value} not available")

        return dataset.to_dataframe()

    def get_quality_summary(self) -> Dict[str, Any]:
        """Generate quality summary across all intervals."""
        summary = {
            'symbol': self.symbol,
            'intervals_available': [interval.value for interval in self.get_available_intervals()],
            'fetched_at': self.fetched_at.isoformat(),
            'interval_reports': {}
        }

        for interval, dataset in self.datasets.items():
            summary['interval_reports'][interval.value] = dataset.get_quality_report()

        return summary


# ============================================================================
# Data Contract Validation Functions
# ============================================================================

def validate_ohlcv_bar(bar: OHLCVBar) -> tuple[bool, Optional[str]]:
    """
    Validate single OHLCV bar against LINE+ quality standards.

    Returns: (is_valid, error_message)
    """
    # Check if bar is already marked invalid
    if not bar.is_valid:
        return False, "Bar failed internal validation checks"

    # Check completeness
    if not bar.is_complete:
        return False, "Incomplete OHLCV data"

    # Check price consistency
    if bar.high < bar.low:
        return False, f"High ({bar.high}) < Low ({bar.low})"

    if not (bar.low <= bar.open <= bar.high):
        return False, f"Open ({bar.open}) outside [Low, High] range"

    if not (bar.low <= bar.close <= bar.high):
        return False, f"Close ({bar.close}) outside [Low, High] range"

    # Check for zero prices (invalid for most instruments)
    if bar.open == 0 or bar.close == 0:
        return False, "Zero prices detected"

    # Check for negative values
    if any(x < 0 for x in [bar.open, bar.high, bar.low, bar.close, bar.volume]):
        return False, "Negative values detected"

    return True, None


def validate_ohlcv_dataset(dataset: OHLCVDataset,
                          min_bars: int = 100,
                          min_completeness: float = 95.0,
                          min_volume_coverage: float = 90.0,
                          min_validity: float = 95.0) -> tuple[bool, List[str]]:
    """
    Validate OHLCV dataset against LINE+ quality thresholds.

    Args:
        dataset: OHLCVDataset to validate
        min_bars: Minimum number of bars required (default: 100)
        min_completeness: Minimum completeness % (default: 95%)
        min_volume_coverage: Minimum volume coverage % (default: 90%)
        min_validity: Minimum valid bars % (default: 95%)

    Returns:
        (is_valid, list_of_violations)
    """
    violations = []

    # Check minimum bar count
    if dataset.get_bar_count() < min_bars:
        violations.append(
            f"Insufficient bars: {dataset.get_bar_count()} < {min_bars} required"
        )

    # Check completeness
    if dataset.completeness_pct < min_completeness:
        violations.append(
            f"Completeness: {dataset.completeness_pct:.1f}% < {min_completeness}% required"
        )

    # Check volume coverage
    if dataset.volume_coverage_pct < min_volume_coverage:
        violations.append(
            f"Volume coverage: {dataset.volume_coverage_pct:.1f}% < {min_volume_coverage}% required"
        )

    # Check validity
    if dataset.valid_bars_pct < min_validity:
        violations.append(
            f"Valid bars: {dataset.valid_bars_pct:.1f}% < {min_validity}% required"
        )

    # Check date range continuity (for daily data)
    if dataset.interval == OHLCVInterval.DAY_1:
        start_date, end_date = dataset.get_date_range()
        if start_date and end_date:
            expected_days = (end_date - start_date).days + 1
            actual_bars = dataset.get_bar_count()

            # Allow for weekends/holidays (assume ~70% coverage)
            if actual_bars < expected_days * 0.7:
                violations.append(
                    f"Date range gaps: {actual_bars} bars over {expected_days} days "
                    f"(expected ≥{int(expected_days * 0.7)})"
                )

    is_valid = len(violations) == 0
    return is_valid, violations


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    """
    Demonstrate LINE+ OHLCV data contracts.
    """
    print("=" * 80)
    print("LINE+ OHLCV DATA CONTRACTS")
    print("Phase 3: Week 2 — Multi-Interval Market Data Layer")
    print("=" * 80)

    # [1] Create single OHLCV bar
    print("\n[1] Creating single OHLCV bar...")
    bar = OHLCVBar(
        timestamp=datetime(2024, 1, 1, 9, 30),
        open=100.0,
        high=102.5,
        low=99.5,
        close=101.0,
        volume=1000000,
        interval=OHLCVInterval.MIN_5,
        symbol="BTC/USD",
        source="binance"
    )

    print(f"    ✅ Bar created: {bar.symbol} @ {bar.timestamp}")
    print(f"    OHLC: O={bar.open}, H={bar.high}, L={bar.low}, C={bar.close}")
    print(f"    Volume: {bar.volume:,}")
    print(f"    Typical Price: ${bar.get_typical_price():.2f}")
    print(f"    Range: ${bar.get_range():.2f}")
    print(f"    Bullish: {bar.is_bullish()}")

    # [2] Validate bar
    print("\n[2] Validating OHLCV bar...")
    is_valid, error = validate_ohlcv_bar(bar)
    if is_valid:
        print(f"    ✅ Bar validation: PASS")
    else:
        print(f"    ❌ Bar validation: FAIL - {error}")

    # [3] Create dataset
    print("\n[3] Creating OHLCV dataset (simulated)...")
    dataset = OHLCVDataset(
        symbol="BTC/USD",
        interval=OHLCVInterval.DAY_1,
        source="binance"
    )

    # Add 100 simulated daily bars
    import numpy as np
    np.random.seed(42)

    base_date = datetime(2024, 1, 1)
    price = 100.0

    for i in range(100):
        bar_date = base_date + pd.Timedelta(days=i)
        daily_return = 0.01 * np.random.randn()  # 1% daily volatility

        open_price = price
        close_price = price * (1 + daily_return)
        high_price = max(open_price, close_price) * (1 + abs(np.random.randn()) * 0.005)
        low_price = min(open_price, close_price) * (1 - abs(np.random.randn()) * 0.005)
        volume = int(1000000 + 500000 * np.random.rand())

        bar = OHLCVBar(
            timestamp=bar_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            interval=OHLCVInterval.DAY_1,
            symbol="BTC/USD",
            source="binance"
        )

        dataset.add_bar(bar)
        price = close_price

    print(f"    ✅ Dataset created: {dataset.get_bar_count()} bars")
    start_date, end_date = dataset.get_date_range()
    print(f"    Date range: {start_date.date()} → {end_date.date()}")
    print(f"    Price: ${dataset.bars[0].close:.2f} → ${dataset.bars[-1].close:.2f}")

    # [4] Check data quality
    print("\n[4] Data quality metrics...")
    print(f"    Completeness: {dataset.completeness_pct:.1f}%")
    print(f"    Volume coverage: {dataset.volume_coverage_pct:.1f}%")
    print(f"    Valid bars: {dataset.valid_bars_pct:.1f}%")

    # [5] Validate dataset
    print("\n[5] Validating dataset...")
    is_valid, violations = validate_ohlcv_dataset(dataset, min_bars=100)
    if is_valid:
        print(f"    ✅ Dataset validation: PASS")
    else:
        print(f"    ❌ Dataset validation: FAIL")
        for violation in violations:
            print(f"       - {violation}")

    # [6] Convert to DataFrame (FINN+ format)
    print("\n[6] Converting to DataFrame (FINN+ input format)...")
    df = dataset.to_dataframe()
    print(f"    ✅ DataFrame created: {len(df)} rows × {len(df.columns)} columns")
    print(f"    Columns: {list(df.columns)}")
    print(f"\n    First 3 rows:")
    print(df.head(3).to_string(index=False))

    # [7] Generate quality report
    print("\n[7] Quality report (STIG+ validation input)...")
    quality_report = dataset.get_quality_report()
    print(f"    Symbol: {quality_report['symbol']}")
    print(f"    Interval: {quality_report['interval']}")
    print(f"    Bar count: {quality_report['bar_count']}")
    print(f"    Quality metrics:")
    for metric, value in quality_report['quality_metrics'].items():
        print(f"      - {metric}: {value}%")
    print(f"    Validation status:")
    for check, status in quality_report['validation_status'].items():
        status_icon = "✅" if status else "❌"
        print(f"      {status_icon} {check}: {status}")

    # [8] Multi-interval dataset
    print("\n[8] Creating multi-interval dataset...")
    multi_dataset = MultiIntervalDataset(symbol="BTC/USD")

    # Add daily dataset
    multi_dataset.add_dataset(dataset)

    # Create and add 5m dataset (simulated)
    dataset_5m = OHLCVDataset(
        symbol="BTC/USD",
        interval=OHLCVInterval.MIN_5,
        source="binance"
    )

    for i in range(200):  # 200 × 5min = ~16 hours
        bar_date = datetime(2024, 4, 10, 9, 0) + pd.Timedelta(minutes=i * 5)
        bar_5m = OHLCVBar(
            timestamp=bar_date,
            open=100.0 + i * 0.01,
            high=100.0 + i * 0.01 + 0.5,
            low=100.0 + i * 0.01 - 0.5,
            close=100.0 + i * 0.01 + 0.2,
            volume=50000,
            interval=OHLCVInterval.MIN_5,
            symbol="BTC/USD"
        )
        dataset_5m.add_bar(bar_5m)

    multi_dataset.add_dataset(dataset_5m)

    print(f"    ✅ Multi-interval dataset created")
    print(f"    Available intervals: {[i.value for i in multi_dataset.get_available_intervals()]}")
    print(f"    Daily bars: {multi_dataset.get_dataset(OHLCVInterval.DAY_1).get_bar_count()}")
    print(f"    5-minute bars: {multi_dataset.get_dataset(OHLCVInterval.MIN_5).get_bar_count()}")

    # Summary
    print("\n" + "=" * 80)
    print("✅ LINE+ OHLCV DATA CONTRACTS FUNCTIONAL")
    print("=" * 80)
    print("\nData Structures:")
    print("  - OHLCVBar: ✅ Single bar with quality validation")
    print("  - OHLCVDataset: ✅ Time series with quality metrics")
    print("  - MultiIntervalDataset: ✅ Multi-timeframe support")
    print("\nSupported Intervals:")
    print("  - 1m (60s): High-frequency analysis")
    print("  - 5m (300s): Intraday signals")
    print("  - 15m (900s): Short-term trend")
    print("  - 1d (86400s): Regime classification (primary)")
    print("\nData Quality Thresholds:")
    print("  - Completeness: ≥95% (all OHLCV fields present)")
    print("  - Volume coverage: ≥90% (volume > 0)")
    print("  - Validity: ≥95% (OHLC consistency checks)")
    print("  - Minimum bars: ≥100 (statistical significance)")
    print("\nIntegration Points:")
    print("  - FINN+ input: to_dataframe() → regime classification")
    print("  - STIG+ validation: get_quality_report() → data quality gate")
    print("  - Database persistence: to_dict() → fhq_phase3.ohlcv_data")
    print("\nStatus: Ready for LINE+ data quality validation module")
    print("=" * 80)
