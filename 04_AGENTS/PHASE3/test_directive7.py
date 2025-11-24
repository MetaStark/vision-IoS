"""
Unit Tests for LARS Directive 7 Implementation
Phase 3: Week 3 — Production Data Integration

Tests for:
1. Production Data Source Adapters (Binance, Alpaca, Yahoo, FRED)
2. STIG+ Persistence Tracker (C2 Signal Stability)
3. G4 Canonicalization Script

Authority: LARS G2 Approval (CDS Engine v1.0)
Canonical ADR Chain: ADR-001 → ADR-015
"""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

# Import modules under test
from production_data_adapters import (
    BinanceAdapter, AlpacaAdapter, YahooFinanceAdapter, FREDAdapter,
    DataSourceFactory, DataSourceConfig, RateLimiter, RateLimitConfig,
    DataSignature
)
from stig_persistence_tracker import (
    STIGPersistenceTracker, RegimeLabel, PersistenceRecord,
    RegimeTransition, compute_c2_for_cds
)
from g4_canonicalization import (
    G4EvidenceBundleGenerator, G4Signature, CanonicalSnapshot,
    TestResult, ComplianceCheck
)
from line_ohlcv_contracts import OHLCVInterval


# =============================================================================
# RATE LIMITER TESTS
# =============================================================================

class TestRateLimiter(unittest.TestCase):
    """Test rate limiting functionality (ADR-012)."""

    def setUp(self):
        """Set up rate limiter with test configuration."""
        self.config = RateLimitConfig(
            max_requests_per_minute=5,
            max_requests_per_hour=20,
            max_daily_budget_usd=10.0
        )
        self.limiter = RateLimiter(self.config)

    def test_initial_state_allows_requests(self):
        """Initial state should allow requests."""
        can_request, reason = self.limiter.can_make_request()
        self.assertTrue(can_request)
        self.assertEqual(reason, "OK")

    def test_per_minute_limit_enforced(self):
        """Per-minute limit should be enforced."""
        # Make requests up to limit
        for _ in range(5):
            can_request, _ = self.limiter.can_make_request()
            self.assertTrue(can_request)
            self.limiter.record_request()

        # Next request should be blocked
        can_request, reason = self.limiter.can_make_request()
        self.assertFalse(can_request)
        self.assertIn("Per-minute", reason)

    def test_daily_budget_enforced(self):
        """Daily budget should be enforced."""
        # Record costs up to limit
        self.limiter.record_request(cost=5.0)
        self.limiter.record_request(cost=4.9)

        # Next request with cost should be blocked
        can_request, reason = self.limiter.can_make_request(estimated_cost=0.2)
        self.assertFalse(can_request)
        self.assertIn("budget", reason.lower())

    def test_statistics_tracking(self):
        """Statistics should be tracked correctly."""
        self.limiter.record_request(cost=1.0)
        self.limiter.record_request(cost=2.0)

        stats = self.limiter.get_statistics()

        self.assertEqual(stats['requests_this_minute'], 2)
        self.assertEqual(stats['daily_cost_usd'], 3.0)
        self.assertEqual(stats['daily_budget_remaining_usd'], 7.0)


# =============================================================================
# BINANCE ADAPTER TESTS
# =============================================================================

class TestBinanceAdapter(unittest.TestCase):
    """Test Binance data adapter."""

    def setUp(self):
        """Set up Binance adapter."""
        self.adapter = DataSourceFactory.create_adapter('binance')

    def test_adapter_initialization(self):
        """Adapter should initialize correctly."""
        self.assertEqual(self.adapter.config.source_name, 'binance')
        self.assertIsNotNone(self.adapter.rate_limiter)

    def test_symbol_normalization(self):
        """Symbols should be normalized correctly."""
        self.assertEqual(self.adapter._normalize_symbol('BTC/USD'), 'BTCUSDT')
        self.assertEqual(self.adapter._normalize_symbol('ETH/USDT'), 'ETHUSDT')

    def test_fetch_ohlcv_returns_bars(self):
        """fetch_ohlcv should return OHLCVBar objects."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

        bars = self.adapter.fetch_ohlcv(
            symbol='BTC/USD',
            interval=OHLCVInterval.DAY_1,
            start_date=start_date,
            end_date=end_date
        )

        self.assertGreater(len(bars), 0)
        self.assertEqual(bars[0].symbol, 'BTC/USD')
        self.assertEqual(bars[0].interval, OHLCVInterval.DAY_1)

    def test_bar_price_sanity(self):
        """Bar prices should be within sanity bounds."""
        bars = self.adapter.fetch_ohlcv(
            symbol='BTC/USD',
            interval=OHLCVInterval.DAY_1,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc)
        )

        for bar in bars:
            self.assertGreater(bar.open, 0)
            self.assertGreater(bar.close, 0)
            self.assertGreaterEqual(bar.high, bar.low)
            self.assertGreaterEqual(bar.high, bar.open)
            self.assertGreaterEqual(bar.high, bar.close)
            self.assertLessEqual(bar.low, bar.open)
            self.assertLessEqual(bar.low, bar.close)

    def test_statistics_updated(self):
        """Statistics should be updated after requests."""
        initial_count = self.adapter.request_count

        self.adapter.fetch_ohlcv(
            symbol='BTC/USD',
            interval=OHLCVInterval.DAY_1,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc)
        )

        self.assertGreater(self.adapter.request_count, initial_count)


# =============================================================================
# ALPACA ADAPTER TESTS
# =============================================================================

class TestAlpacaAdapter(unittest.TestCase):
    """Test Alpaca data adapter."""

    def setUp(self):
        """Set up Alpaca adapter."""
        self.adapter = DataSourceFactory.create_adapter('alpaca')

    def test_adapter_initialization(self):
        """Adapter should initialize correctly."""
        self.assertEqual(self.adapter.config.source_name, 'alpaca')

    def test_fetch_ohlcv_returns_bars(self):
        """fetch_ohlcv should return OHLCVBar objects."""
        bars = self.adapter.fetch_ohlcv(
            symbol='SPY',
            interval=OHLCVInterval.DAY_1,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc)
        )

        self.assertGreater(len(bars), 0)
        self.assertEqual(bars[0].symbol, 'SPY')


# =============================================================================
# YAHOO FINANCE ADAPTER TESTS
# =============================================================================

class TestYahooFinanceAdapter(unittest.TestCase):
    """Test Yahoo Finance data adapter."""

    def setUp(self):
        """Set up Yahoo Finance adapter."""
        self.adapter = DataSourceFactory.create_adapter('yahoo')

    def test_adapter_initialization(self):
        """Adapter should initialize correctly."""
        self.assertEqual(self.adapter.config.source_name, 'yahoo')

    def test_fetch_ohlcv_returns_bars(self):
        """fetch_ohlcv should return OHLCVBar objects."""
        bars = self.adapter.fetch_ohlcv(
            symbol='AAPL',
            interval=OHLCVInterval.DAY_1,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc)
        )

        self.assertGreater(len(bars), 0)
        self.assertEqual(bars[0].symbol, 'AAPL')


# =============================================================================
# FRED ADAPTER TESTS
# =============================================================================

class TestFREDAdapter(unittest.TestCase):
    """Test FRED (Federal Reserve) data adapter."""

    def setUp(self):
        """Set up FRED adapter."""
        self.adapter = DataSourceFactory.create_adapter('fred')

    def test_adapter_initialization(self):
        """Adapter should initialize correctly."""
        self.assertEqual(self.adapter.config.source_name, 'fred')

    def test_fetch_economic_indicators(self):
        """Should fetch economic indicator data."""
        indicators = self.adapter.fetch_economic_indicators(
            series_ids=['DFF', 'VIXCLS'],
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now()
        )

        self.assertIn('DFF', indicators)
        self.assertGreater(len(indicators['DFF']), 0)


# =============================================================================
# DATA SOURCE FACTORY TESTS
# =============================================================================

class TestDataSourceFactory(unittest.TestCase):
    """Test data source factory."""

    def test_create_binance_adapter(self):
        """Should create Binance adapter."""
        adapter = DataSourceFactory.create_adapter('binance')
        self.assertIsInstance(adapter, BinanceAdapter)

    def test_create_alpaca_adapter(self):
        """Should create Alpaca adapter."""
        adapter = DataSourceFactory.create_adapter('alpaca')
        self.assertIsInstance(adapter, AlpacaAdapter)

    def test_create_yahoo_adapter(self):
        """Should create Yahoo Finance adapter."""
        adapter = DataSourceFactory.create_adapter('yahoo')
        self.assertIsInstance(adapter, YahooFinanceAdapter)

    def test_create_fred_adapter(self):
        """Should create FRED adapter."""
        adapter = DataSourceFactory.create_adapter('fred')
        self.assertIsInstance(adapter, FREDAdapter)

    def test_invalid_source_raises_error(self):
        """Invalid source should raise ValueError."""
        with self.assertRaises(ValueError):
            DataSourceFactory.create_adapter('invalid_source')

    def test_get_available_sources(self):
        """Should return list of available sources."""
        sources = DataSourceFactory.get_available_sources()
        self.assertIn('binance', sources)
        self.assertIn('alpaca', sources)
        self.assertIn('yahoo', sources)
        self.assertIn('fred', sources)


# =============================================================================
# STIG+ PERSISTENCE TRACKER TESTS
# =============================================================================

class TestSTIGPersistenceTracker(unittest.TestCase):
    """Test STIG+ persistence tracking for C2 component."""

    def setUp(self):
        """Set up persistence tracker."""
        self.tracker = STIGPersistenceTracker(use_mock_storage=True)

    def test_tracker_initialization(self):
        """Tracker should initialize correctly."""
        self.assertEqual(self.tracker.total_updates, 0)
        self.assertEqual(self.tracker.total_transitions, 0)

    def test_initialize_regime(self):
        """Should initialize regime tracking."""
        record = self.tracker.initialize_regime(
            symbol='BTC/USD',
            interval='1d',
            regime=RegimeLabel.BULL,
            confidence=0.75
        )

        self.assertEqual(record.symbol, 'BTC/USD')
        self.assertEqual(record.current_regime, RegimeLabel.BULL)
        self.assertEqual(record.persistence_days, 0.0)
        self.assertEqual(record.c2_value, 0.0)

    def test_c2_calculation_formula(self):
        """C2 should follow formula: min(days/30, 1.0)."""
        self.tracker.initialize_regime('BTC/USD', '1d', RegimeLabel.BULL, 0.75)

        # Simulate 15 days of persistence
        base_time = datetime.now(timezone.utc)
        for day in range(15):
            self.tracker.update_regime(
                'BTC/USD', '1d', RegimeLabel.BULL, 0.75,
                timestamp=base_time + timedelta(days=day)
            )

        record = self.tracker.get_persistence('BTC/USD', '1d')

        # C2 should be approximately 15/30 = 0.5
        self.assertAlmostEqual(record.c2_value, 14.0 / 30.0, places=1)

    def test_c2_maxes_at_one(self):
        """C2 should max out at 1.0 after 30 days."""
        self.tracker.initialize_regime('BTC/USD', '1d', RegimeLabel.BULL, 0.75)

        # Simulate 45 days
        base_time = datetime.now(timezone.utc)
        for day in range(45):
            self.tracker.update_regime(
                'BTC/USD', '1d', RegimeLabel.BULL, 0.75,
                timestamp=base_time + timedelta(days=day)
            )

        record = self.tracker.get_persistence('BTC/USD', '1d')

        self.assertLessEqual(record.c2_value, 1.0)

    def test_regime_transition_detected(self):
        """Regime transitions should be detected."""
        self.tracker.initialize_regime('BTC/USD', '1d', RegimeLabel.BULL, 0.75)

        # Update with same regime - no transition
        record, transition = self.tracker.update_regime(
            'BTC/USD', '1d', RegimeLabel.BULL, 0.75
        )
        self.assertIsNone(transition)

        # Update with different regime - transition!
        record, transition = self.tracker.update_regime(
            'BTC/USD', '1d', RegimeLabel.BEAR, 0.80
        )

        self.assertIsNotNone(transition)
        self.assertEqual(transition.previous_regime, RegimeLabel.BULL)
        self.assertEqual(transition.new_regime, RegimeLabel.BEAR)

    def test_persistence_resets_on_transition(self):
        """Persistence should reset to 0 on regime transition."""
        self.tracker.initialize_regime('BTC/USD', '1d', RegimeLabel.BULL, 0.75)

        # Build up persistence
        base_time = datetime.now(timezone.utc)
        for day in range(10):
            self.tracker.update_regime(
                'BTC/USD', '1d', RegimeLabel.BULL, 0.75,
                timestamp=base_time + timedelta(days=day)
            )

        # Transition
        record, _ = self.tracker.update_regime(
            'BTC/USD', '1d', RegimeLabel.BEAR, 0.80,
            timestamp=base_time + timedelta(days=11)
        )

        self.assertEqual(record.persistence_days, 0.0)
        self.assertEqual(record.c2_value, 0.0)

    def test_transition_count_tracking(self):
        """Transition count should be tracked."""
        self.tracker.initialize_regime('BTC/USD', '1d', RegimeLabel.BULL, 0.75)

        # Make several transitions
        regimes = [RegimeLabel.BEAR, RegimeLabel.BULL, RegimeLabel.NEUTRAL, RegimeLabel.BEAR]

        for i, regime in enumerate(regimes):
            self.tracker.update_regime('BTC/USD', '1d', regime, 0.75)

        record = self.tracker.get_persistence('BTC/USD', '1d')
        self.assertEqual(record.transition_count_90d, len(regimes))

    def test_transition_limit_validation(self):
        """STIG+ Tier-4 transition limit should be validated."""
        is_valid, message = self.tracker.validate_transition_limit('BTC/USD', '1d')

        self.assertTrue(is_valid)
        self.assertIn('OK', message)

    def test_get_c2_value_for_cds(self):
        """get_c2_value should work for CDS integration."""
        self.tracker.initialize_regime('BTC/USD', '1d', RegimeLabel.BULL, 0.75)

        # Simulate 20 days
        base_time = datetime.now(timezone.utc)
        for day in range(20):
            self.tracker.update_regime(
                'BTC/USD', '1d', RegimeLabel.BULL, 0.75,
                timestamp=base_time + timedelta(days=day)
            )

        c2 = self.tracker.get_c2_value('BTC/USD', '1d')

        self.assertGreater(c2, 0.5)
        self.assertLess(c2, 1.0)

    def test_untracked_symbol_returns_placeholder(self):
        """Untracked symbol should return placeholder C2."""
        c2 = self.tracker.get_c2_value('UNKNOWN/USD', '1d')

        self.assertEqual(c2, 0.5)  # Placeholder value

    def test_compute_c2_for_cds_integration(self):
        """compute_c2_for_cds should work correctly."""
        result = compute_c2_for_cds(
            tracker=self.tracker,
            symbol='ETH/USD',
            interval='1d',
            regime_label='NEUTRAL',
            confidence=0.60
        )

        self.assertIn('c2_value', result)
        self.assertIn('persistence_days', result)
        self.assertIn('transition_limit_valid', result)

    def test_signature_on_records(self):
        """All records should have signature hashes."""
        record = self.tracker.initialize_regime('BTC/USD', '1d', RegimeLabel.BULL, 0.75)

        self.assertTrue(len(record.signature_hash) > 0)


# =============================================================================
# G4 CANONICALIZATION TESTS
# =============================================================================

class TestG4Signature(unittest.TestCase):
    """Test G4 signature utilities."""

    def test_hash_computation(self):
        """Hash should be deterministic."""
        data = {'key': 'value', 'number': 42}

        hash1 = G4Signature.compute_hash(data)
        hash2 = G4Signature.compute_hash(data)

        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA256 hex

    def test_different_data_different_hash(self):
        """Different data should produce different hashes."""
        data1 = {'key': 'value1'}
        data2 = {'key': 'value2'}

        hash1 = G4Signature.compute_hash(data1)
        hash2 = G4Signature.compute_hash(data2)

        self.assertNotEqual(hash1, hash2)

    def test_bundle_id_generation(self):
        """Bundle ID should be generated correctly."""
        bundle_id = G4Signature.generate_bundle_id()

        self.assertTrue(bundle_id.startswith('G4-BUNDLE-'))

    def test_snapshot_id_generation(self):
        """Snapshot ID should include component name."""
        snapshot_id = G4Signature.generate_snapshot_id('FINN')

        self.assertTrue(snapshot_id.startswith('SNAP-FINN-'))


class TestG4EvidenceBundleGenerator(unittest.TestCase):
    """Test G4 evidence bundle generation."""

    def setUp(self):
        """Set up bundle generator."""
        self.base_path = Path(__file__).parent
        self.generator = G4EvidenceBundleGenerator(self.base_path)

    def test_generator_initialization(self):
        """Generator should initialize correctly."""
        self.assertIsNotNone(self.generator.test_runner)
        self.assertIsNotNone(self.generator.compliance_checker)
        self.assertIsNotNone(self.generator.snapshot_generator)

    def test_generate_bundle_without_tests(self):
        """Should generate bundle without running tests."""
        bundle = self.generator.generate_bundle(
            run_tests=False,
            economic_cost=0.0,
            determinism_score=0.95
        )

        self.assertTrue(bundle.bundle_id.startswith('G4-BUNDLE-'))
        self.assertIsInstance(bundle.generated_at, datetime)
        self.assertIn(bundle.overall_status, ['READY', 'PENDING', 'BLOCKED'])

    def test_compliance_checks_generated(self):
        """Compliance checks should be generated."""
        bundle = self.generator.generate_bundle(run_tests=False)

        self.assertGreater(len(bundle.compliance_checks), 0)

        adr_ids = [c.adr_id for c in bundle.compliance_checks]
        self.assertIn('ADR-002', adr_ids)
        self.assertIn('ADR-008', adr_ids)
        self.assertIn('ADR-012', adr_ids)

    def test_snapshots_generated(self):
        """Canonical snapshots should be generated."""
        bundle = self.generator.generate_bundle(run_tests=False)

        self.assertGreater(len(bundle.snapshots), 0)

        components = [s.component for s in bundle.snapshots]
        self.assertIn('FINN_PLUS', components)
        self.assertIn('STIG_PLUS', components)
        self.assertIn('CDS_ENGINE', components)

    def test_bundle_hashes_computed(self):
        """Bundle and signature hashes should be computed."""
        bundle = self.generator.generate_bundle(run_tests=False)

        self.assertTrue(len(bundle.bundle_hash) > 0)
        self.assertTrue(len(bundle.signature_hash) > 0)

    def test_summary_report_generation(self):
        """Summary report should be generated."""
        bundle = self.generator.generate_bundle(run_tests=False)
        report = self.generator.generate_summary_report(bundle)

        self.assertIn('G4 PRODUCTION AUTHORIZATION', report)
        self.assertIn(bundle.bundle_id, report)
        self.assertIn(bundle.overall_status, report)

    def test_high_cost_creates_blocking_issue(self):
        """High economic cost should create blocking issue."""
        bundle = self.generator.generate_bundle(
            run_tests=False,
            economic_cost=1000.0  # Over $500 daily cap
        )

        self.assertIn('BLOCKED', bundle.overall_status + ''.join(bundle.blocking_issues))

    def test_low_determinism_creates_blocking_issue(self):
        """Low determinism should create blocking issue."""
        bundle = self.generator.generate_bundle(
            run_tests=False,
            determinism_score=0.80  # Below 95% threshold
        )

        blocking_text = ' '.join(bundle.blocking_issues)
        self.assertIn('Determinism', blocking_text)


# =============================================================================
# DATA SIGNATURE TESTS
# =============================================================================

class TestDataSignature(unittest.TestCase):
    """Test data signature utilities."""

    def test_hash_computation(self):
        """Hash should be computed correctly."""
        data = {'test': 'data'}
        hash_result = DataSignature.compute_hash(data)

        self.assertEqual(len(hash_result), 64)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestDirective7Integration(unittest.TestCase):
    """Integration tests for Directive 7 components."""

    def test_adapter_to_persistence_flow(self):
        """Data adapter → STIG+ persistence flow should work."""
        # Create adapter
        adapter = DataSourceFactory.create_adapter('binance')

        # Fetch data
        bars = adapter.fetch_ohlcv(
            symbol='BTC/USD',
            interval=OHLCVInterval.DAY_1,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc)
        )

        self.assertGreater(len(bars), 0)

        # Create persistence tracker
        tracker = STIGPersistenceTracker()

        # Initialize with regime from "FINN+" (mock)
        tracker.initialize_regime('BTC/USD', '1d', RegimeLabel.BULL, 0.75)

        # Get C2 for CDS
        c2 = tracker.get_c2_value('BTC/USD', '1d')

        self.assertGreaterEqual(c2, 0.0)
        self.assertLessEqual(c2, 1.0)

    def test_full_cds_c2_integration(self):
        """Full C2 computation for CDS should work."""
        tracker = STIGPersistenceTracker()

        # Simulate 10 days of BULL regime
        base_time = datetime.now(timezone.utc)
        for day in range(10):
            result = compute_c2_for_cds(
                tracker=tracker,
                symbol='BTC/USD',
                interval='1d',
                regime_label='BULL',
                confidence=0.75
            )

        # C2 should reflect ~10 days persistence
        self.assertGreater(result['c2_value'], 0.2)
        self.assertLess(result['c2_value'], 0.5)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("LARS DIRECTIVE 7 UNIT TESTS")
    print("Phase 3: Week 3 — Production Data Integration")
    print("=" * 70)

    # Run tests
    unittest.main(verbosity=2)
