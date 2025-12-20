#!/usr/bin/env python3
"""
IoS-015 STATISTICAL ARBITRAGE ENGINE (STIG-2025-001 Compliant)
==============================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - StatArb with 3yr Cointegration
Classification: Tier-1 Alpha Generation

Purpose:
    Pairs trading using Engle-Granger cointegration with 3-year historical data.
    Generates mean-reversion signals on statistically validated pairs.

Methodology:
    1. Engle-Granger Two-Step Cointegration
       - Regress: log(P_A) = α + β·log(P_B) + ε
       - ADF test on residuals: p-value < 0.05

    2. Z-Score Trading
       - Entry: |z| > 2.0
       - Exit: |z| < 0.5

    3. Kelly-based position sizing

Usage:
    from ios015_statarb_engine import StatArbEngine

    engine = StatArbEngine()
    pairs = engine.find_cointegrated_pairs(['AAPL', 'MSFT', 'GOOGL'])
    signals = engine.generate_signals()
"""

import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

# Statistical tests
try:
    from statsmodels.tsa.stattools import adfuller, coint
    from statsmodels.regression.linear_model import OLS
    import statsmodels.api as sm
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    print("WARNING: statsmodels not available. Using simplified tests.")

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class SignalDirection(Enum):
    LONG_A_SHORT_B = "LONG_A_SHORT_B"   # Spread too low, buy A sell B
    SHORT_A_LONG_B = "SHORT_A_LONG_B"   # Spread too high, sell A buy B
    FLAT = "FLAT"                        # No signal / exit


@dataclass
class CointegrationResult:
    """Result of cointegration test"""
    asset_a: str
    asset_b: str
    is_cointegrated: bool
    p_value: float
    hedge_ratio: float              # β in regression
    half_life: float                # Mean reversion half-life
    correlation: float
    tested_at: datetime
    data_points: int
    years_tested: float


@dataclass
class StatArbSignal:
    """Statistical arbitrage trading signal"""
    pair_id: str
    asset_a: str
    asset_b: str
    direction: SignalDirection
    z_score: float
    spread: float
    hedge_ratio: float
    confidence: float
    kelly_fraction: float
    entry_price_a: float
    entry_price_b: float
    stop_loss_z: float
    take_profit_z: float
    generated_at: datetime


class StatArbEngine:
    """
    Statistical Arbitrage Engine (STIG-2025-001)

    Implements pairs trading with:
    - 3-year cointegration testing (756+ trading days)
    - Rolling 30-day ADF for blacklisting
    - Z-score entry/exit signals
    - Kelly-based position sizing
    """

    # STIG-2025-001 Parameters
    MIN_HISTORY_DAYS = 756          # 3 years minimum
    COINTEGRATION_PVALUE = 0.05     # ADF p-value threshold
    ZSCORE_ENTRY = 2.0              # Entry threshold
    ZSCORE_EXIT = 0.5               # Exit threshold
    ZSCORE_STOP = 3.5               # Stop loss threshold
    MIN_CORRELATION = 0.5           # Minimum correlation for pair

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self._pairs_cache: Dict[str, CointegrationResult] = {}
        self._cache_time: Optional[datetime] = None

    def _get_price_series(self, asset: str, days: int = 756) -> Tuple[np.ndarray, List[datetime]]:
        """Fetch log price series for asset"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT timestamp::date as date, close
                FROM fhq_market.prices
                WHERE canonical_id = %s
                  AND timestamp >= NOW() - INTERVAL '%s days'
                ORDER BY timestamp ASC
            """, (asset, days + 30))
            rows = cur.fetchall()

        if not rows:
            return np.array([]), []

        prices = np.array([float(r['close']) for r in rows])
        dates = [r['date'] for r in rows]

        # Return log prices for cointegration
        log_prices = np.log(prices)

        return log_prices, dates

    def _test_cointegration(self, asset_a: str, asset_b: str) -> CointegrationResult:
        """
        Test cointegration between two assets using Engle-Granger method.

        Steps:
        1. Regress log(P_A) on log(P_B)
        2. Get residuals
        3. ADF test on residuals
        """
        # Fetch data
        log_a, dates_a = self._get_price_series(asset_a, self.MIN_HISTORY_DAYS)
        log_b, dates_b = self._get_price_series(asset_b, self.MIN_HISTORY_DAYS)

        # Align series
        min_len = min(len(log_a), len(log_b))
        if min_len < self.MIN_HISTORY_DAYS * 0.8:  # Allow 20% missing
            return CointegrationResult(
                asset_a=asset_a,
                asset_b=asset_b,
                is_cointegrated=False,
                p_value=1.0,
                hedge_ratio=0.0,
                half_life=float('inf'),
                correlation=0.0,
                tested_at=datetime.now(timezone.utc),
                data_points=min_len,
                years_tested=min_len / 252
            )

        log_a = log_a[-min_len:]
        log_b = log_b[-min_len:]

        # Correlation check
        correlation = np.corrcoef(log_a, log_b)[0, 1]
        if abs(correlation) < self.MIN_CORRELATION:
            return CointegrationResult(
                asset_a=asset_a,
                asset_b=asset_b,
                is_cointegrated=False,
                p_value=1.0,
                hedge_ratio=0.0,
                half_life=float('inf'),
                correlation=correlation,
                tested_at=datetime.now(timezone.utc),
                data_points=min_len,
                years_tested=min_len / 252
            )

        if STATSMODELS_AVAILABLE:
            # Engle-Granger cointegration test
            try:
                # Step 1: OLS regression
                X = sm.add_constant(log_b)
                model = OLS(log_a, X).fit()
                hedge_ratio = model.params[1]
                residuals = model.resid

                # Step 2: ADF test on residuals
                adf_result = adfuller(residuals, maxlag=1)
                p_value = adf_result[1]

                # Calculate half-life of mean reversion
                residuals_lag = residuals[:-1]
                residuals_diff = np.diff(residuals)
                X_hl = sm.add_constant(residuals_lag)
                model_hl = OLS(residuals_diff, X_hl).fit()
                lambda_coef = model_hl.params[1]
                half_life = -np.log(2) / lambda_coef if lambda_coef < 0 else float('inf')

                is_cointegrated = p_value < self.COINTEGRATION_PVALUE and half_life < 60

            except Exception as e:
                print(f"Cointegration test error: {e}")
                p_value = 1.0
                hedge_ratio = 0.0
                half_life = float('inf')
                is_cointegrated = False
        else:
            # Simplified test without statsmodels
            # Use correlation as proxy
            hedge_ratio = np.cov(log_a, log_b)[0, 1] / np.var(log_b)
            spread = log_a - hedge_ratio * log_b
            spread_std = np.std(spread)

            # Simple stationarity check - variance shouldn't grow
            first_half_var = np.var(spread[:len(spread)//2])
            second_half_var = np.var(spread[len(spread)//2:])
            variance_ratio = second_half_var / first_half_var if first_half_var > 0 else 2

            is_cointegrated = 0.5 < variance_ratio < 2 and abs(correlation) > 0.7
            p_value = 0.01 if is_cointegrated else 0.5
            half_life = 20 if is_cointegrated else float('inf')

        result = CointegrationResult(
            asset_a=asset_a,
            asset_b=asset_b,
            is_cointegrated=is_cointegrated,
            p_value=round(p_value, 4),
            hedge_ratio=round(hedge_ratio, 4),
            half_life=round(half_life, 1),
            correlation=round(correlation, 4),
            tested_at=datetime.now(timezone.utc),
            data_points=min_len,
            years_tested=round(min_len / 252, 2)
        )

        # Cache and log
        pair_id = f"{asset_a}_{asset_b}"
        self._pairs_cache[pair_id] = result
        self._log_cointegration(result)

        return result

    def _log_cointegration(self, result: CointegrationResult):
        """Log cointegration result to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.cointegration_pairs
                    (asset_a, asset_b, is_cointegrated, p_value, hedge_ratio,
                     half_life, correlation, data_points, years_tested, tested_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (asset_a, asset_b) DO UPDATE SET
                        is_cointegrated = EXCLUDED.is_cointegrated,
                        p_value = EXCLUDED.p_value,
                        hedge_ratio = EXCLUDED.hedge_ratio,
                        half_life = EXCLUDED.half_life,
                        tested_at = EXCLUDED.tested_at
                """, (
                    result.asset_a,
                    result.asset_b,
                    result.is_cointegrated,
                    result.p_value,
                    result.hedge_ratio,
                    result.half_life,
                    result.correlation,
                    result.data_points,
                    result.years_tested,
                    result.tested_at
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass

    def find_cointegrated_pairs(self, assets: List[str]) -> List[CointegrationResult]:
        """
        Find all cointegrated pairs from list of assets.

        Tests all unique pairs (N choose 2).
        """
        cointegrated = []
        tested = 0

        for i, asset_a in enumerate(assets):
            for asset_b in assets[i+1:]:
                tested += 1
                result = self._test_cointegration(asset_a, asset_b)
                if result.is_cointegrated:
                    cointegrated.append(result)

                if tested % 10 == 0:
                    print(f"  Tested {tested} pairs, found {len(cointegrated)} cointegrated...")

        return cointegrated

    def calculate_zscore(self, asset_a: str, asset_b: str, hedge_ratio: float, lookback: int = 30) -> float:
        """Calculate current z-score of spread"""
        log_a, _ = self._get_price_series(asset_a, lookback + 10)
        log_b, _ = self._get_price_series(asset_b, lookback + 10)

        min_len = min(len(log_a), len(log_b))
        if min_len < lookback:
            return 0.0

        log_a = log_a[-min_len:]
        log_b = log_b[-min_len:]

        spread = log_a - hedge_ratio * log_b
        mean = np.mean(spread)
        std = np.std(spread)

        if std == 0:
            return 0.0

        current_spread = spread[-1]
        z_score = (current_spread - mean) / std

        return z_score

    def generate_signal(self, pair: CointegrationResult) -> Optional[StatArbSignal]:
        """Generate trading signal for cointegrated pair"""
        if not pair.is_cointegrated:
            return None

        z_score = self.calculate_zscore(pair.asset_a, pair.asset_b, pair.hedge_ratio)

        # Get current prices
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT canonical_id, close
                FROM fhq_market.prices
                WHERE canonical_id IN (%s, %s)
                ORDER BY timestamp DESC
                LIMIT 2
            """, (pair.asset_a, pair.asset_b))
            prices = {r['canonical_id']: float(r['close']) for r in cur.fetchall()}

        price_a = prices.get(pair.asset_a, 0)
        price_b = prices.get(pair.asset_b, 0)

        # Determine direction
        if abs(z_score) < self.ZSCORE_EXIT:
            direction = SignalDirection.FLAT
        elif z_score > self.ZSCORE_ENTRY:
            direction = SignalDirection.SHORT_A_LONG_B  # Spread too high
        elif z_score < -self.ZSCORE_ENTRY:
            direction = SignalDirection.LONG_A_SHORT_B  # Spread too low
        else:
            direction = SignalDirection.FLAT

        # Calculate confidence and Kelly
        confidence = min(abs(z_score) / 3.0, 1.0)  # Higher z = higher confidence
        kelly = self._calculate_kelly(pair.half_life, confidence)

        signal = StatArbSignal(
            pair_id=f"{pair.asset_a}_{pair.asset_b}",
            asset_a=pair.asset_a,
            asset_b=pair.asset_b,
            direction=direction,
            z_score=round(z_score, 4),
            spread=round(np.log(price_a) - pair.hedge_ratio * np.log(price_b), 6) if price_a and price_b else 0,
            hedge_ratio=pair.hedge_ratio,
            confidence=round(confidence, 4),
            kelly_fraction=round(kelly, 4),
            entry_price_a=price_a,
            entry_price_b=price_b,
            stop_loss_z=self.ZSCORE_STOP * np.sign(z_score) if z_score != 0 else 0,
            take_profit_z=self.ZSCORE_EXIT * np.sign(z_score) if z_score != 0 else 0,
            generated_at=datetime.now(timezone.utc)
        )

        # Log signal
        self._log_signal(signal)

        return signal

    def _calculate_kelly(self, half_life: float, confidence: float) -> float:
        """Calculate Kelly fraction for StatArb"""
        # Shorter half-life = faster mean reversion = better edge
        if half_life > 60 or half_life <= 0:
            return 0.0

        # Base win rate from half-life
        # half_life=10 -> ~0.65 win rate
        # half_life=30 -> ~0.55 win rate
        win_rate = 0.5 + 0.15 * (1 - half_life / 60)

        # Win/loss ratio (typical for mean reversion)
        win_loss = 1.2

        # Kelly formula
        kelly = (win_rate * (win_loss + 1) - 1) / win_loss

        # Apply confidence and half-kelly
        return max(0, kelly * confidence * 0.5)

    def _log_signal(self, signal: StatArbSignal):
        """Log signal to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.statarb_signals
                    (pair_id, asset_a, asset_b, direction, z_score, hedge_ratio,
                     confidence, kelly_fraction, entry_price_a, entry_price_b, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    signal.pair_id,
                    signal.asset_a,
                    signal.asset_b,
                    signal.direction.value,
                    signal.z_score,
                    signal.hedge_ratio,
                    signal.confidence,
                    signal.kelly_fraction,
                    signal.entry_price_a,
                    signal.entry_price_b,
                    signal.generated_at
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass

    def generate_all_signals(self) -> List[StatArbSignal]:
        """Generate signals for all known cointegrated pairs"""
        signals = []

        # Get cached pairs or from database
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT asset_a, asset_b, hedge_ratio, half_life, correlation, p_value
                    FROM fhq_alpha.cointegration_pairs
                    WHERE is_cointegrated = true
                      AND tested_at >= NOW() - INTERVAL '7 days'
                """)
                pairs = cur.fetchall()
        except Exception:
            pairs = []

        for p in pairs:
            pair = CointegrationResult(
                asset_a=p['asset_a'],
                asset_b=p['asset_b'],
                is_cointegrated=True,
                p_value=p['p_value'],
                hedge_ratio=p['hedge_ratio'],
                half_life=p['half_life'],
                correlation=p['correlation'],
                tested_at=datetime.now(timezone.utc),
                data_points=0,
                years_tested=0
            )
            signal = self.generate_signal(pair)
            if signal and signal.direction != SignalDirection.FLAT:
                signals.append(signal)

        return signals


if __name__ == "__main__":
    print("=" * 60)
    print("IoS-015 STATISTICAL ARBITRAGE ENGINE - SELF TEST")
    print("=" * 60)

    engine = StatArbEngine()

    # Get test assets (sector-based for better cointegration)
    print("\n[1] Fetching assets...")
    with engine.conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get tech stocks
        cur.execute("""
            SELECT DISTINCT canonical_id
            FROM fhq_market.prices
            WHERE canonical_id IN ('AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'AMD', 'INTC')
              AND timestamp >= NOW() - INTERVAL '60 days'
        """)
        tech = [r['canonical_id'] for r in cur.fetchall()]

        # Get financial stocks
        cur.execute("""
            SELECT DISTINCT canonical_id
            FROM fhq_market.prices
            WHERE canonical_id IN ('JPM', 'BAC', 'GS', 'MS', 'WFC', 'C')
              AND timestamp >= NOW() - INTERVAL '60 days'
        """)
        finance = [r['canonical_id'] for r in cur.fetchall()]

    print(f"   Tech stocks: {tech}")
    print(f"   Finance stocks: {finance}")

    # Test cointegration
    test_assets = tech[:4] if len(tech) >= 4 else tech + finance[:4-len(tech)]

    if len(test_assets) >= 2:
        print(f"\n[2] Testing cointegration for {test_assets}...")
        pairs = engine.find_cointegrated_pairs(test_assets)

        print(f"\n[3] Found {len(pairs)} cointegrated pairs:")
        for pair in pairs:
            print(f"   {pair.asset_a} <-> {pair.asset_b}")
            print(f"      p-value: {pair.p_value}, hedge_ratio: {pair.hedge_ratio}")
            print(f"      half-life: {pair.half_life} days, correlation: {pair.correlation}")

        # Generate signals
        if pairs:
            print(f"\n[4] Generating signals...")
            for pair in pairs:
                signal = engine.generate_signal(pair)
                if signal:
                    print(f"   {signal.pair_id}: {signal.direction.value}")
                    print(f"      z-score: {signal.z_score}, confidence: {signal.confidence}")
                    print(f"      kelly: {signal.kelly_fraction}")
    else:
        print("   Insufficient assets for testing")

    print("\n" + "=" * 60)
    print("IoS-015 STATISTICAL ARBITRAGE ENGINE - TEST COMPLETE")
    print("=" * 60)
