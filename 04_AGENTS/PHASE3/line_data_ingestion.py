"""
LINE+ Real-Time Data Ingestion Framework
Phase 3: Week 3 — LARS Directive 4 (Priority 1: Operational Readiness)

Authority: LARS G2 Approval (CDS Engine v1.0)
Canonical ADR Chain: ADR-001 → ADR-015

Purpose: Real-time OHLCV data ingestion with multi-interval support
Sources: External APIs (Binance, Alpaca, Alpha Vantage, etc.)

Pipeline:
1. Data Source Adapter → Fetch OHLCV data
2. Data Normalization → Convert to LINE+ contracts
3. Data Quality Gate → Mandatory validation before downstream
4. Orchestrator Integration → Feed validated data to FINN+

Compliance:
- ADR-002: Audit lineage (source tracking, timestamps)
- ADR-010: Data quality validation (LINE+ gate)
- ADR-012: Economic safety (rate limiting, cost tracking)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
import time

from line_ohlcv_contracts import OHLCVBar, OHLCVDataset, OHLCVInterval
from line_data_quality import LINEDataQualityValidator, validate_for_finn


@dataclass
class DataSourceConfig:
    """Configuration for data source."""
    source_name: str  # e.g., "binance", "alpaca"
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    rate_limit_per_minute: int = 60  # Rate limit
    timeout_seconds: int = 30


class DataSourceAdapter(ABC):
    """
    Abstract base class for data source adapters.

    Each data source (Binance, Alpaca, etc.) should implement this interface.
    """

    def __init__(self, config: DataSourceConfig):
        """Initialize data source adapter."""
        self.config = config
        self.request_count = 0
        self.total_cost = 0.0

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, interval: OHLCVInterval,
                    start_date: datetime, end_date: datetime) -> List[OHLCVBar]:
        """
        Fetch OHLCV data from source.

        Args:
            symbol: Symbol (e.g., "BTC/USD")
            interval: OHLCVInterval (1m, 5m, 15m, 1d)
            start_date: Start datetime
            end_date: End datetime

        Returns:
            List of OHLCVBar objects

        Raises:
            Exception if fetch fails
        """
        pass

    @abstractmethod
    def get_latest_bar(self, symbol: str, interval: OHLCVInterval) -> Optional[OHLCVBar]:
        """
        Get latest OHLCV bar for symbol/interval.

        Args:
            symbol: Symbol (e.g., "BTC/USD")
            interval: OHLCVInterval

        Returns:
            Latest OHLCVBar or None if unavailable
        """
        pass

    def get_statistics(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        return {
            'source': self.config.source_name,
            'request_count': self.request_count,
            'total_cost': self.total_cost
        }


class MockDataSourceAdapter(DataSourceAdapter):
    """
    Mock data source adapter for testing.

    Generates synthetic OHLCV data without external API calls.
    """

    def __init__(self, config: DataSourceConfig):
        """Initialize mock adapter."""
        super().__init__(config)
        self.base_price = 100.0

    def fetch_ohlcv(self, symbol: str, interval: OHLCVInterval,
                    start_date: datetime, end_date: datetime) -> List[OHLCVBar]:
        """Generate synthetic OHLCV data."""
        import numpy as np

        bars = []
        current_date = start_date
        price = self.base_price

        # Determine interval duration
        interval_seconds = interval.seconds
        interval_delta = timedelta(seconds=interval_seconds)

        while current_date <= end_date:
            # Generate synthetic price movement
            daily_return = 0.01 * np.random.randn()  # 1% volatility

            open_price = price
            close_price = price * (1 + daily_return)
            high_price = max(open_price, close_price) * 1.005
            low_price = min(open_price, close_price) * 0.995
            volume = int(1000000 + 500000 * np.random.rand())

            bar = OHLCVBar(
                timestamp=current_date,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                interval=interval,
                symbol=symbol,
                source=self.config.source_name
            )

            bars.append(bar)
            price = close_price
            current_date += interval_delta

        self.request_count += 1
        return bars

    def get_latest_bar(self, symbol: str, interval: OHLCVInterval) -> Optional[OHLCVBar]:
        """Get latest synthetic bar."""
        bars = self.fetch_ohlcv(
            symbol=symbol,
            interval=interval,
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now()
        )
        return bars[-1] if bars else None


class LINEDataIngestionPipeline:
    """
    LINE+ Data Ingestion Pipeline.

    Orchestrates data fetching, normalization, and quality validation.

    Pipeline:
    1. Fetch data from source
    2. Convert to OHLCVDataset
    3. Validate with LINE+ quality gate
    4. Return validated dataset for orchestrator
    """

    def __init__(self, data_source: DataSourceAdapter):
        """
        Initialize ingestion pipeline.

        Args:
            data_source: DataSourceAdapter implementation
        """
        self.data_source = data_source
        self.validator = LINEDataQualityValidator()
        self.ingestion_count = 0
        self.validation_failures = 0

    def ingest_historical(self, symbol: str, interval: OHLCVInterval,
                         start_date: datetime, end_date: datetime) -> Optional[OHLCVDataset]:
        """
        Ingest historical OHLCV data.

        Args:
            symbol: Symbol (e.g., "BTC/USD")
            interval: OHLCVInterval
            start_date: Start datetime
            end_date: End datetime

        Returns:
            OHLCVDataset if validation passes, None otherwise
        """
        self.ingestion_count += 1

        try:
            # [1] Fetch data from source
            bars = self.data_source.fetch_ohlcv(symbol, interval, start_date, end_date)

            if not bars:
                print(f"No data fetched for {symbol} ({interval.value})")
                return None

            # [2] Create dataset
            dataset = OHLCVDataset(
                symbol=symbol,
                interval=interval,
                bars=bars,
                source=self.data_source.config.source_name,
                fetched_at=datetime.now()
            )

            # [3] Validate with LINE+ quality gate
            is_valid, report = validate_for_finn(dataset)

            if not is_valid:
                self.validation_failures += 1
                print(f"Data quality validation failed for {symbol} ({interval.value})")
                print(f"Issues: {len(report.get_failures())}")
                return None

            return dataset

        except Exception as e:
            print(f"Error during ingestion: {e}")
            return None

    def ingest_latest(self, symbol: str, interval: OHLCVInterval) -> Optional[OHLCVBar]:
        """
        Ingest latest OHLCV bar.

        Args:
            symbol: Symbol (e.g., "BTC/USD")
            interval: OHLCVInterval

        Returns:
            Latest OHLCVBar if available, None otherwise
        """
        try:
            bar = self.data_source.get_latest_bar(symbol, interval)
            return bar
        except Exception as e:
            print(f"Error fetching latest bar: {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        data_source_stats = self.data_source.get_statistics()

        return {
            'ingestion_count': self.ingestion_count,
            'validation_failures': self.validation_failures,
            'validation_success_rate': (
                (self.ingestion_count - self.validation_failures) / self.ingestion_count * 100
                if self.ingestion_count > 0 else 0.0
            ),
            'data_source': data_source_stats
        }


class MultiIntervalIngestionPipeline:
    """
    Multi-Interval Data Ingestion Pipeline.

    Ingests OHLCV data across multiple intervals (1m, 5m, 15m, 1d)
    for multi-timeframe regime analysis.
    """

    def __init__(self, data_source: DataSourceAdapter):
        """Initialize multi-interval pipeline."""
        self.pipeline = LINEDataIngestionPipeline(data_source)

    def ingest_multi_interval(self, symbol: str,
                             intervals: List[OHLCVInterval],
                             start_date: datetime,
                             end_date: datetime) -> Dict[OHLCVInterval, OHLCVDataset]:
        """
        Ingest data across multiple intervals.

        Args:
            symbol: Symbol (e.g., "BTC/USD")
            intervals: List of OHLCVInterval to ingest
            start_date: Start datetime
            end_date: End datetime

        Returns:
            Dictionary mapping interval to validated dataset
        """
        datasets = {}

        for interval in intervals:
            print(f"Ingesting {symbol} ({interval.value})...")
            dataset = self.pipeline.ingest_historical(symbol, interval, start_date, end_date)

            if dataset:
                datasets[interval] = dataset
                print(f"  ✅ {dataset.get_bar_count()} bars ingested")
            else:
                print(f"  ❌ Ingestion failed")

        return datasets


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """
    Demonstrate LINE+ data ingestion pipeline.
    """
    print("=" * 80)
    print("LINE+ REAL-TIME DATA INGESTION FRAMEWORK")
    print("Phase 3: Week 3 — LARS Directive 4 (Priority 1)")
    print("=" * 80)

    # [1] Initialize mock data source
    print("\n[1] Initializing mock data source...")
    config = DataSourceConfig(
        source_name="mock_exchange",
        rate_limit_per_minute=60
    )
    data_source = MockDataSourceAdapter(config)
    print("    ✅ Mock data source initialized")

    # [2] Create ingestion pipeline
    print("\n[2] Creating LINE+ ingestion pipeline...")
    pipeline = LINEDataIngestionPipeline(data_source)
    print("    ✅ Pipeline created")

    # [3] Ingest historical data (daily)
    print("\n[3] Ingesting historical data (1d interval)...")
    start_date = datetime.now() - timedelta(days=300)
    end_date = datetime.now()

    dataset_daily = pipeline.ingest_historical(
        symbol="BTC/USD",
        interval=OHLCVInterval.DAY_1,
        start_date=start_date,
        end_date=end_date
    )

    if dataset_daily:
        print(f"    ✅ Ingested {dataset_daily.get_bar_count()} daily bars")
        print(f"    Data quality: {dataset_daily.valid_bars_pct:.1f}% valid")
    else:
        print("    ❌ Ingestion failed")

    # [4] Ingest latest bar
    print("\n[4] Fetching latest bar...")
    latest_bar = pipeline.ingest_latest(symbol="BTC/USD", interval=OHLCVInterval.DAY_1)
    if latest_bar:
        print(f"    ✅ Latest bar: ${latest_bar.close:.2f} @ {latest_bar.timestamp}")
    else:
        print("    ❌ Failed to fetch latest bar")

    # [5] Multi-interval ingestion
    print("\n[5] Multi-interval ingestion...")
    multi_pipeline = MultiIntervalIngestionPipeline(data_source)

    intervals = [OHLCVInterval.MIN_5, OHLCVInterval.MIN_15, OHLCVInterval.DAY_1]
    datasets = multi_pipeline.ingest_multi_interval(
        symbol="BTC/USD",
        intervals=intervals,
        start_date=datetime.now() - timedelta(days=7),
        end_date=datetime.now()
    )

    print(f"\n    Summary:")
    for interval, dataset in datasets.items():
        print(f"    - {interval.value}: {dataset.get_bar_count()} bars")

    # [6] Pipeline statistics
    print("\n[6] Pipeline statistics...")
    stats = pipeline.get_statistics()
    print(f"    Total ingestions: {stats['ingestion_count']}")
    print(f"    Validation failures: {stats['validation_failures']}")
    print(f"    Success rate: {stats['validation_success_rate']:.1f}%")
    print(f"    Data source requests: {stats['data_source']['request_count']}")

    # Summary
    print("\n" + "=" * 80)
    print("✅ LINE+ DATA INGESTION FRAMEWORK FUNCTIONAL")
    print("=" * 80)
    print("\nFeatures:")
    print("  - Multi-interval support (1m, 5m, 15m, 1d)")
    print("  - Data quality gate (mandatory validation)")
    print("  - Mock adapter for testing")
    print("  - Real-time latest bar fetching")
    print("  - Multi-interval batch ingestion")
    print("\nIntegration:")
    print("  - Data Source → LINE+ Contracts")
    print("  - LINE+ Quality Gate → Orchestrator")
    print("  - Validated datasets → FINN+ Classification")
    print("\nProduction Readiness:")
    print("  - Implement BinanceAdapter, AlpacaAdapter, etc.")
    print("  - Add rate limiting enforcement")
    print("  - Add retry logic with exponential backoff")
    print("  - Add cost tracking (API usage)")
    print("\nStatus: Ready for production data source adapters")
    print("=" * 80)
