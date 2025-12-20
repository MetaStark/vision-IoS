#!/usr/bin/env python3
"""
IoS-003 ADVANCED REGIME CLASSIFIER (STIG-2025-001 Compliant)
============================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - 4D Regime Classification
Classification: Tier-1 Perception Critical

Purpose:
    Multi-dimensional regime classification for strategy deployment safety.
    Replaces simple NEUTRAL filter with 4D vector analysis.

4D Regime Vector:
    Regime = f(Trend, Volatility, VolatilityShift, Volume)

    1. Trend (ADX): Trending vs Range-bound
    2. Volatility (ATR): High vs Low volatility
    3. VolatilityShift: Sudden vol expansion detection
    4. Volume: Liquidity confirmation

Usage:
    from ios003_advanced_regime import AdvancedRegimeClassifier, is_grid_safe

    classifier = AdvancedRegimeClassifier()
    regime = classifier.classify('AAPL')

    if classifier.is_grid_safe('AAPL'):
        # Deploy grid strategy
        pass
"""

import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class TrendRegime(Enum):
    """Trend classification based on ADX"""
    STRONG_TREND = "STRONG_TREND"       # ADX > 40
    MODERATE_TREND = "MODERATE_TREND"   # 25 < ADX <= 40
    WEAK_TREND = "WEAK_TREND"           # 20 < ADX <= 25
    RANGE_BOUND = "RANGE_BOUND"         # ADX <= 20


class VolatilityRegime(Enum):
    """Volatility classification based on ATR percentile"""
    EXTREME = "EXTREME"     # ATR > 90th percentile
    HIGH = "HIGH"           # ATR > 70th percentile
    NORMAL = "NORMAL"       # 30th <= ATR <= 70th percentile
    LOW = "LOW"             # ATR < 30th percentile


class VolumeRegime(Enum):
    """Volume classification relative to 20-day average"""
    SURGE = "SURGE"         # Volume > 200% of avg
    HIGH = "HIGH"           # Volume > 120% of avg
    NORMAL = "NORMAL"       # 70% <= Volume <= 120% of avg
    LOW = "LOW"             # Volume < 70% of avg


@dataclass
class RegimeVector:
    """4D Regime Vector per STIG-2025-001"""
    asset: str
    timestamp: datetime

    # Trend dimension
    adx: float
    trend_regime: TrendRegime
    plus_di: float
    minus_di: float
    trend_direction: str  # BULLISH, BEARISH, NEUTRAL

    # Volatility dimension
    atr: float
    atr_normalized: float  # ATR / Close
    atr_percentile: float
    volatility_regime: VolatilityRegime

    # Volatility Shift dimension
    volatility_shift: float  # Current ATR / 20-day ATR avg
    vol_expanding: bool

    # Volume dimension
    volume: float
    volume_ratio: float  # Current / 20-day avg
    volume_regime: VolumeRegime

    # Composite scores
    grid_safe: bool
    statarb_safe: bool
    breakout_favorable: bool
    meanrev_favorable: bool

    # Raw data for debugging
    metadata: Dict


class AdvancedRegimeClassifier:
    """
    Advanced 4D Regime Classifier (STIG-2025-001)

    Provides multi-dimensional market regime classification for
    strategy-specific deployment decisions.

    Key thresholds (per STIG-2025-001):
    - Grid Safe: ADX < 20, ATR_norm > 0.005, VolShift < 0.3, Vol > 70% avg
    - StatArb Safe: Low trend, normal volatility
    - Breakout: High ADX, expanding volatility
    - MeanRev: Low ADX, normal/high volatility
    """

    # STIG-2025-001 Thresholds
    ADX_STRONG = 40
    ADX_MODERATE = 25
    ADX_WEAK = 20

    ATR_HIGH_PERCENTILE = 70
    ATR_LOW_PERCENTILE = 30

    VOL_SHIFT_DANGER = 0.3  # 30% vol expansion = danger

    VOLUME_HIGH_RATIO = 1.2
    VOLUME_LOW_RATIO = 0.7

    def __init__(self, lookback_days: int = 20):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.lookback_days = lookback_days
        self._cache: Dict[str, RegimeVector] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=15)

    def _get_price_data(self, asset: str, days: int = 50) -> List[Dict]:
        """Fetch OHLCV data for calculations"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    timestamp::date as date,
                    open, high, low, close, volume
                FROM fhq_market.prices
                WHERE canonical_id = %s
                  AND timestamp >= NOW() - INTERVAL '%s days'
                ORDER BY timestamp DESC
                LIMIT %s
            """, (asset, days + 10, days + 5))
            return cur.fetchall()

    def _calculate_atr(self, data: List[Dict], period: int = 14) -> Tuple[float, List[float]]:
        """Calculate Average True Range"""
        if len(data) < period + 1:
            return 0.0, []

        true_ranges = []
        for i in range(1, len(data)):
            high = float(data[i]['high'])
            low = float(data[i]['low'])
            prev_close = float(data[i-1]['close'])

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        # Simple moving average for ATR
        if len(true_ranges) >= period:
            atr = np.mean(true_ranges[:period])
            return atr, true_ranges
        return 0.0, true_ranges

    def _calculate_adx(self, data: List[Dict], period: int = 14) -> Tuple[float, float, float]:
        """Calculate ADX, +DI, -DI"""
        if len(data) < period + 1:
            return 0.0, 0.0, 0.0

        plus_dm_list = []
        minus_dm_list = []
        tr_list = []

        for i in range(1, len(data)):
            high = float(data[i]['high'])
            low = float(data[i]['low'])
            prev_high = float(data[i-1]['high'])
            prev_low = float(data[i-1]['low'])
            prev_close = float(data[i-1]['close'])

            # True Range
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

            # Directional Movement
            plus_dm = max(high - prev_high, 0) if (high - prev_high) > (prev_low - low) else 0
            minus_dm = max(prev_low - low, 0) if (prev_low - low) > (high - prev_high) else 0

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)

        if len(tr_list) < period:
            return 0.0, 0.0, 0.0

        # Smoothed averages
        atr = np.mean(tr_list[:period])
        plus_dm_avg = np.mean(plus_dm_list[:period])
        minus_dm_avg = np.mean(minus_dm_list[:period])

        if atr == 0:
            return 0.0, 0.0, 0.0

        plus_di = 100 * plus_dm_avg / atr
        minus_di = 100 * minus_dm_avg / atr

        # DX and ADX
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 0.0, plus_di, minus_di

        dx = 100 * abs(plus_di - minus_di) / di_sum

        # For simplicity, use DX as ADX (proper ADX needs more smoothing)
        adx = dx

        return adx, plus_di, minus_di

    def _get_atr_percentile(self, current_atr: float, historical_atrs: List[float]) -> float:
        """Calculate percentile rank of current ATR"""
        if not historical_atrs or current_atr == 0:
            return 50.0

        count_below = sum(1 for atr in historical_atrs if atr < current_atr)
        return 100 * count_below / len(historical_atrs)

    def classify(self, asset: str, use_cache: bool = True) -> RegimeVector:
        """
        Classify asset into 4D regime vector.

        Args:
            asset: Asset identifier (e.g., 'AAPL')
            use_cache: Use cached result if fresh

        Returns:
            RegimeVector with full regime classification
        """
        # Check cache
        if use_cache and asset in self._cache:
            if self._cache_time and (datetime.now(timezone.utc) - self._cache_time) < self._cache_ttl:
                return self._cache[asset]

        # Fetch data
        data = self._get_price_data(asset, days=50)

        if len(data) < 20:
            # Insufficient data - return neutral regime
            return self._neutral_regime(asset)

        # Reverse to chronological order for calculations
        data = list(reversed(data))

        current_close = float(data[-1]['close'])
        current_volume = float(data[-1]['volume']) if data[-1]['volume'] else 0

        # Calculate indicators
        atr, atr_history = self._calculate_atr(data)
        adx, plus_di, minus_di = self._calculate_adx(data)

        # ATR normalized
        atr_normalized = atr / current_close if current_close > 0 else 0

        # ATR percentile
        atr_percentile = self._get_atr_percentile(atr, atr_history)

        # Volatility shift (current vs 20-day avg)
        if len(atr_history) >= 20:
            atr_20d_avg = np.mean(atr_history[-20:])
            volatility_shift = (atr / atr_20d_avg - 1) if atr_20d_avg > 0 else 0
        else:
            volatility_shift = 0

        # Volume ratio
        volumes = [float(d['volume']) if d['volume'] else 0 for d in data[-21:-1]]
        volume_20d_avg = np.mean(volumes) if volumes else current_volume
        volume_ratio = current_volume / volume_20d_avg if volume_20d_avg > 0 else 1.0

        # Classify dimensions
        trend_regime = self._classify_trend(adx)
        volatility_regime = self._classify_volatility(atr_percentile)
        volume_regime = self._classify_volume(volume_ratio)

        # Trend direction
        if plus_di > minus_di and adx > self.ADX_WEAK:
            trend_direction = "BULLISH"
        elif minus_di > plus_di and adx > self.ADX_WEAK:
            trend_direction = "BEARISH"
        else:
            trend_direction = "NEUTRAL"

        # Composite safety checks
        grid_safe = self._is_grid_safe(adx, atr_normalized, volatility_shift, volume_ratio)
        statarb_safe = self._is_statarb_safe(adx, volatility_regime)
        breakout_favorable = self._is_breakout_favorable(adx, volatility_shift, volume_ratio)
        meanrev_favorable = self._is_meanrev_favorable(adx, volatility_regime)

        regime = RegimeVector(
            asset=asset,
            timestamp=datetime.now(timezone.utc),
            adx=round(adx, 2),
            trend_regime=trend_regime,
            plus_di=round(plus_di, 2),
            minus_di=round(minus_di, 2),
            trend_direction=trend_direction,
            atr=round(atr, 4),
            atr_normalized=round(atr_normalized, 6),
            atr_percentile=round(atr_percentile, 1),
            volatility_regime=volatility_regime,
            volatility_shift=round(volatility_shift, 4),
            vol_expanding=volatility_shift > self.VOL_SHIFT_DANGER,
            volume=current_volume,
            volume_ratio=round(volume_ratio, 2),
            volume_regime=volume_regime,
            grid_safe=grid_safe,
            statarb_safe=statarb_safe,
            breakout_favorable=breakout_favorable,
            meanrev_favorable=meanrev_favorable,
            metadata={
                'data_points': len(data),
                'lookback_days': self.lookback_days,
                'current_close': current_close
            }
        )

        # Cache and log
        self._cache[asset] = regime
        self._cache_time = datetime.now(timezone.utc)
        self._log_regime(regime)

        return regime

    def _neutral_regime(self, asset: str) -> RegimeVector:
        """Return neutral regime for insufficient data"""
        return RegimeVector(
            asset=asset,
            timestamp=datetime.now(timezone.utc),
            adx=0,
            trend_regime=TrendRegime.RANGE_BOUND,
            plus_di=0,
            minus_di=0,
            trend_direction="NEUTRAL",
            atr=0,
            atr_normalized=0,
            atr_percentile=50,
            volatility_regime=VolatilityRegime.NORMAL,
            volatility_shift=0,
            vol_expanding=False,
            volume=0,
            volume_ratio=1.0,
            volume_regime=VolumeRegime.NORMAL,
            grid_safe=False,
            statarb_safe=False,
            breakout_favorable=False,
            meanrev_favorable=False,
            metadata={'error': 'insufficient_data'}
        )

    def _classify_trend(self, adx: float) -> TrendRegime:
        if adx > self.ADX_STRONG:
            return TrendRegime.STRONG_TREND
        elif adx > self.ADX_MODERATE:
            return TrendRegime.MODERATE_TREND
        elif adx > self.ADX_WEAK:
            return TrendRegime.WEAK_TREND
        else:
            return TrendRegime.RANGE_BOUND

    def _classify_volatility(self, percentile: float) -> VolatilityRegime:
        if percentile > 90:
            return VolatilityRegime.EXTREME
        elif percentile > self.ATR_HIGH_PERCENTILE:
            return VolatilityRegime.HIGH
        elif percentile < self.ATR_LOW_PERCENTILE:
            return VolatilityRegime.LOW
        else:
            return VolatilityRegime.NORMAL

    def _classify_volume(self, ratio: float) -> VolumeRegime:
        if ratio > 2.0:
            return VolumeRegime.SURGE
        elif ratio > self.VOLUME_HIGH_RATIO:
            return VolumeRegime.HIGH
        elif ratio < self.VOLUME_LOW_RATIO:
            return VolumeRegime.LOW
        else:
            return VolumeRegime.NORMAL

    def _is_grid_safe(self, adx: float, atr_norm: float, vol_shift: float, vol_ratio: float) -> bool:
        """
        Grid Safety Check per STIG-2025-001

        Grid only deploys if ALL conditions met:
        - ADX < 20 (non-trending)
        - ATR_normalized > 0.005 (some volatility)
        - VolatilityShift < 0.3 (no sudden expansion)
        - Volume > 70% of 20d avg (sufficient liquidity)
        """
        return (
            adx < self.ADX_WEAK and
            atr_norm > 0.005 and
            vol_shift < self.VOL_SHIFT_DANGER and
            vol_ratio > self.VOLUME_LOW_RATIO
        )

    def _is_statarb_safe(self, adx: float, vol_regime: VolatilityRegime) -> bool:
        """StatArb safety: low trend, non-extreme volatility"""
        return (
            adx < self.ADX_MODERATE and
            vol_regime != VolatilityRegime.EXTREME
        )

    def _is_breakout_favorable(self, adx: float, vol_shift: float, vol_ratio: float) -> bool:
        """Breakout favorable: trending + expanding vol + high volume"""
        return (
            adx > self.ADX_WEAK and
            vol_shift > 0.1 and
            vol_ratio > self.VOLUME_HIGH_RATIO
        )

    def _is_meanrev_favorable(self, adx: float, vol_regime: VolatilityRegime) -> bool:
        """Mean reversion favorable: low trend + normal/high volatility"""
        return (
            adx < self.ADX_MODERATE and
            vol_regime in [VolatilityRegime.NORMAL, VolatilityRegime.HIGH]
        )

    def _log_regime(self, regime: RegimeVector):
        """Log regime classification to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_perception.advanced_regime_log
                    (asset_id, adx, trend_regime, atr, atr_normalized, volatility_regime,
                     volatility_shift, volume_ratio, volume_regime, grid_safe, statarb_safe,
                     breakout_favorable, meanrev_favorable, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                """, (
                    regime.asset,
                    regime.adx,
                    regime.trend_regime.value,
                    regime.atr,
                    regime.atr_normalized,
                    regime.volatility_regime.value,
                    regime.volatility_shift,
                    regime.volume_ratio,
                    regime.volume_regime.value,
                    regime.grid_safe,
                    regime.statarb_safe,
                    regime.breakout_favorable,
                    regime.meanrev_favorable,
                    json.dumps(regime.metadata)
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            # Table may not exist
            pass

    def batch_classify(self, assets: List[str]) -> Dict[str, RegimeVector]:
        """Classify multiple assets"""
        results = {}
        for asset in assets:
            results[asset] = self.classify(asset)
        return results

    def get_safe_assets(self, assets: List[str], strategy: str) -> List[str]:
        """Get assets safe for specific strategy"""
        safe = []
        for asset in assets:
            regime = self.classify(asset)

            if strategy == 'grid' and regime.grid_safe:
                safe.append(asset)
            elif strategy == 'statarb' and regime.statarb_safe:
                safe.append(asset)
            elif strategy == 'breakout' and regime.breakout_favorable:
                safe.append(asset)
            elif strategy == 'meanrev' and regime.meanrev_favorable:
                safe.append(asset)

        return safe


# Convenience functions
def is_grid_safe(asset: str) -> bool:
    """Quick grid safety check"""
    classifier = AdvancedRegimeClassifier()
    return classifier.classify(asset).grid_safe


def get_regime(asset: str) -> RegimeVector:
    """Quick regime classification"""
    classifier = AdvancedRegimeClassifier()
    return classifier.classify(asset)


if __name__ == "__main__":
    print("=" * 60)
    print("IoS-003 ADVANCED REGIME CLASSIFIER - SELF TEST")
    print("=" * 60)

    classifier = AdvancedRegimeClassifier()

    # Get test assets
    with classifier.conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT canonical_id
            FROM fhq_market.prices
            WHERE timestamp >= NOW() - INTERVAL '60 days'
            ORDER BY canonical_id
            LIMIT 10
        """)
        assets = [r['canonical_id'] for r in cur.fetchall()]

    print(f"\n[1] Testing {len(assets)} assets...")

    for asset in assets[:5]:
        regime = classifier.classify(asset)

        print(f"\n{asset}:")
        print(f"  Trend:      ADX={regime.adx} -> {regime.trend_regime.value}")
        print(f"  Direction:  {regime.trend_direction} (+DI={regime.plus_di}, -DI={regime.minus_di})")
        print(f"  Volatility: ATR={regime.atr:.4f} ({regime.atr_percentile}%ile) -> {regime.volatility_regime.value}")
        print(f"  Vol Shift:  {regime.volatility_shift:.2%} {'EXPANDING!' if regime.vol_expanding else ''}")
        print(f"  Volume:     {regime.volume_ratio:.2f}x avg -> {regime.volume_regime.value}")
        print(f"  ---")
        print(f"  Grid Safe:      {regime.grid_safe}")
        print(f"  StatArb Safe:   {regime.statarb_safe}")
        print(f"  Breakout Fav:   {regime.breakout_favorable}")
        print(f"  MeanRev Fav:    {regime.meanrev_favorable}")

    print(f"\n[2] Strategy-specific asset selection...")
    for strategy in ['grid', 'statarb', 'breakout', 'meanrev']:
        safe = classifier.get_safe_assets(assets, strategy)
        print(f"  {strategy.upper()}: {len(safe)} assets safe - {safe[:3]}")

    print("\n" + "=" * 60)
    print("IoS-003 ADVANCED REGIME CLASSIFIER - TEST COMPLETE")
    print("=" * 60)
