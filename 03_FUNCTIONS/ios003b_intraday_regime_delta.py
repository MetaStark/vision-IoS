#!/usr/bin/env python3
"""
IoS-003-B: Intraday Regime-Delta Engine
========================================
Constitutional Basis: LARS CEO Directive - Intraday Regime-Delta Implementation
ADR Compliance: ADR-013 (Canonical Integrity), ADR-014 (Sub-Executive Governance)

PURPOSE:
Implements the "fast weather" layer for intraday regime detection:
- Aggregates tick data into H1/H4 bars
- Detects volatility squeeze (Bollinger inside Keltner)
- Calculates momentum vector for directional bias
- Emits Flash-Context objects for Signal Executor consumption

SECURITY CONSTRAINTS:
1. Canonical regime (fhq_perception.regime_daily) is NEVER modified
2. All data is ephemeral with TTL
3. No circular feedback into canonical governance log
4. DEFCON always overrides intraday permits
"""

import os
import sys
import time
import logging
import argparse
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[IoS-003-B] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ios003b_intraday_regime_delta.log')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CEO-DIR-2026-0ZE-A v2: OBSERVABILITY-ONLY MODE
# ============================================================================
# When True: Detection engine runs, delta_log writes allowed, but
# flash_context emission is BLOCKED. Hypothetical contexts are logged instead.
# This mode is for Phase 1 evaluation - proving IOS-003-B value before execution.
# ============================================================================
OBSERVABILITY_ONLY_MODE = os.getenv('IOS003B_OBSERVABILITY_ONLY', 'true').lower() == 'true'

if OBSERVABILITY_ONLY_MODE:
    logger.info("=" * 60)
    logger.info("OBSERVABILITY-ONLY MODE ACTIVE (CEO-DIR-2026-0ZE-A v2)")
    logger.info("Flash-context emission DISABLED. Hypothetical logging ENABLED.")
    logger.info("=" * 60)


class DeltaType(Enum):
    """Intraday regime delta classifications"""
    VOLATILITY_SQUEEZE = "VOLATILITY_SQUEEZE"
    SQUEEZE_FIRE_BULL = "SQUEEZE_FIRE_BULL"
    SQUEEZE_FIRE_BEAR = "SQUEEZE_FIRE_BEAR"
    MOMENTUM_SHIFT_BULL = "MOMENTUM_SHIFT_BULL"
    MOMENTUM_SHIFT_BEAR = "MOMENTUM_SHIFT_BEAR"
    VOLUME_SURGE = "VOLUME_SURGE"
    TREND_ACCELERATION = "TREND_ACCELERATION"


class MomentumVector(Enum):
    """Momentum direction classification"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class SqueezeConfig:
    """Configuration for squeeze detection"""
    listing_id: str
    bb_period: int = 20
    bb_std_dev: float = 2.0
    kc_period: int = 20
    kc_atr_mult: float = 1.5
    momentum_period: int = 20
    momentum_smoothing: int = 5
    squeeze_threshold: float = 0.8
    intensity_min: float = 0.6
    volume_surge_mult: float = 1.5
    target_signal_classes: List[str] = None

    def __post_init__(self):
        if self.target_signal_classes is None:
            self.target_signal_classes = ['C']


@dataclass
class OHLCVBar:
    """Single OHLCV bar"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    tick_count: int = 0


@dataclass
class SqueezeResult:
    """Result of squeeze detection"""
    is_squeeze: bool
    squeeze_tightness: float
    bollinger_width: float
    keltner_width: float
    momentum_slope: float
    momentum_vector: MomentumVector
    volume_ratio: float
    intensity: float
    delta_type: Optional[DeltaType] = None


class IntradayRegimeDeltaEngine:
    """
    Main engine for intraday regime delta detection.

    Implements dual-layer "Climate vs Weather" architecture:
    - Climate: Daily canonical regime (unchanged)
    - Weather: Intraday regime delta (this engine)
    """

    def __init__(self, db_config: Dict[str, str] = None):
        """Initialize the engine with database connection."""
        self.db_config = db_config or {
            'host': os.getenv('PGHOST', '127.0.0.1'),
            'port': os.getenv('PGPORT', '54322'),
            'dbname': os.getenv('PGDATABASE', 'postgres'),
            'user': os.getenv('PGUSER', 'postgres'),
            'password': os.getenv('PGPASSWORD', 'postgres')
        }
        self.conn = None
        self.target_assets = ['BTC-USD', 'ETH-USD', 'SOL-USD']
        self.configs: Dict[str, SqueezeConfig] = {}
        self.ttl_hours = 4

    def connect(self):
        """Establish database connection."""
        self.conn = psycopg2.connect(**self.db_config)
        logger.info("Database connected")

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database disconnected")

    def load_configs(self):
        """Load squeeze detection configurations from database."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_operational.squeeze_config
                WHERE is_active = true
            """)
            rows = cur.fetchall()

            for row in rows:
                self.configs[row['listing_id']] = SqueezeConfig(
                    listing_id=row['listing_id'],
                    bb_period=row['bb_period'],
                    bb_std_dev=float(row['bb_std_dev']),
                    kc_period=row['kc_period'],
                    kc_atr_mult=float(row['kc_atr_mult']),
                    momentum_period=row['momentum_period'],
                    momentum_smoothing=row['momentum_smoothing'],
                    squeeze_threshold=float(row['squeeze_threshold']),
                    intensity_min=float(row['intensity_min']),
                    volume_surge_mult=float(row['volume_surge_mult']),
                    target_signal_classes=row['target_signal_classes']
                )

            logger.info(f"Loaded {len(self.configs)} squeeze configurations")

    def check_defcon_permit(self) -> bool:
        """Check if DEFCON level allows intraday operations."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT defcon_level
                FROM fhq_governance.defcon_state
                WHERE is_current = true
                LIMIT 1
            """)
            row = cur.fetchone()

            if not row:
                logger.warning("No DEFCON state found - defaulting to DENIED")
                return False

            # GREEN and YELLOW allow execution, RED and BLACK do not
            permitted_levels = ['GREEN', 'YELLOW']
            if row['defcon_level'] not in permitted_levels:
                logger.warning(f"DEFCON {row['defcon_level']} - Execution NOT permitted")
                return False

            logger.debug(f"DEFCON {row['defcon_level']} - Execution permitted")
            return True

    def get_canonical_regime(self, listing_id: str) -> Optional[str]:
        """Get the current canonical daily regime (READ-ONLY)."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT regime_classification
                FROM fhq_perception.regime_daily
                WHERE asset_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (listing_id,))
            row = cur.fetchone()
            return row['regime_classification'] if row else None

    def aggregate_h1_bars(self, listing_id: str, lookback_hours: int = 168) -> List[OHLCVBar]:
        """
        Aggregate tick data into H1 (1-hour) bars.

        Uses fhq_core.market_prices_live as the high-frequency data source.
        Rolling 7-day window (168 hours).
        """
        bars = []

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # First check if we have cached H1 bars
            cur.execute("""
                SELECT bar_timestamp, open_price, high_price, low_price,
                       close_price, volume, tick_count
                FROM fhq_operational.intraday_bars_h1
                WHERE listing_id = %s
                  AND bar_timestamp > NOW() - INTERVAL '%s hours'
                  AND expires_at > NOW()
                ORDER BY bar_timestamp ASC
            """, (listing_id, lookback_hours))

            cached_bars = cur.fetchall()
            last_cached_ts = None

            for row in cached_bars:
                bars.append(OHLCVBar(
                    timestamp=row['bar_timestamp'],
                    open=float(row['open_price']),
                    high=float(row['high_price']),
                    low=float(row['low_price']),
                    close=float(row['close_price']),
                    volume=float(row['volume']),
                    tick_count=row['tick_count']
                ))
                last_cached_ts = row['bar_timestamp']

            # Now aggregate any new ticks since last cached bar
            start_time = last_cached_ts if last_cached_ts else (
                datetime.utcnow() - timedelta(hours=lookback_hours)
            )

            cur.execute("""
                WITH hourly_agg AS (
                    SELECT
                        date_trunc('hour', event_time_utc) as bar_ts,
                        FIRST_VALUE(price) OVER (PARTITION BY date_trunc('hour', event_time_utc)
                                                  ORDER BY event_time_utc) as open_price,
                        MAX(price) as high_price,
                        MIN(price) as low_price,
                        LAST_VALUE(price) OVER (PARTITION BY date_trunc('hour', event_time_utc)
                                                 ORDER BY event_time_utc
                                                 ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as close_price,
                        SUM(COALESCE(volume, 0)) as total_volume,
                        COUNT(*) as tick_count
                    FROM fhq_core.market_prices_live
                    WHERE asset = %s
                      AND event_time_utc > %s
                      AND event_time_utc <= NOW()
                    GROUP BY date_trunc('hour', event_time_utc), event_time_utc, price
                )
                SELECT
                    bar_ts,
                    MIN(open_price) as open_price,
                    MAX(high_price) as high_price,
                    MIN(low_price) as low_price,
                    MAX(close_price) as close_price,
                    SUM(total_volume) as volume,
                    SUM(tick_count) as tick_count
                FROM hourly_agg
                GROUP BY bar_ts
                HAVING COUNT(*) > 0
                ORDER BY bar_ts ASC
            """, (listing_id, start_time))

            new_bars = cur.fetchall()

            for row in new_bars:
                # Skip incomplete current hour
                if row['bar_ts'].replace(tzinfo=None) >= datetime.utcnow().replace(minute=0, second=0, microsecond=0):
                    continue

                bar = OHLCVBar(
                    timestamp=row['bar_ts'],
                    open=float(row['open_price']),
                    high=float(row['high_price']),
                    low=float(row['low_price']),
                    close=float(row['close_price']),
                    volume=float(row['volume']) if row['volume'] else 0,
                    tick_count=int(row['tick_count'])
                )
                bars.append(bar)

                # Cache the new bar
                self._cache_h1_bar(listing_id, bar)

            logger.debug(f"{listing_id}: Aggregated {len(bars)} H1 bars")
            return bars

    def _cache_h1_bar(self, listing_id: str, bar: OHLCVBar):
        """Cache an H1 bar for future use."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_operational.intraday_bars_h1 (
                    listing_id, bar_timestamp, open_price, high_price,
                    low_price, close_price, volume, tick_count, expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW() + INTERVAL '7 days')
                ON CONFLICT (listing_id, bar_timestamp) DO UPDATE SET
                    close_price = EXCLUDED.close_price,
                    high_price = GREATEST(fhq_operational.intraday_bars_h1.high_price, EXCLUDED.high_price),
                    low_price = LEAST(fhq_operational.intraday_bars_h1.low_price, EXCLUDED.low_price),
                    volume = EXCLUDED.volume,
                    tick_count = EXCLUDED.tick_count
            """, (listing_id, bar.timestamp, bar.open, bar.high,
                  bar.low, bar.close, bar.volume, bar.tick_count))
            self.conn.commit()

    def calculate_bollinger_bands(self, closes: np.ndarray, period: int = 20,
                                   std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate Bollinger Bands.

        Returns: (upper_band, middle_band, lower_band)
        """
        if len(closes) < period:
            return np.array([]), np.array([]), np.array([])

        middle = np.convolve(closes, np.ones(period)/period, mode='valid')

        # Calculate rolling std dev
        stds = np.array([np.std(closes[i:i+period]) for i in range(len(closes) - period + 1)])

        upper = middle + (std_dev * stds)
        lower = middle - (std_dev * stds)

        return upper, middle, lower

    def calculate_keltner_channels(self, highs: np.ndarray, lows: np.ndarray,
                                    closes: np.ndarray, period: int = 20,
                                    atr_mult: float = 1.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate Keltner Channels.

        Uses EMA for middle band and ATR for channel width.
        Returns: (upper_channel, middle_channel, lower_channel)
        """
        if len(closes) < period:
            return np.array([]), np.array([]), np.array([])

        # EMA for middle
        alpha = 2 / (period + 1)
        ema = np.zeros(len(closes))
        ema[0] = closes[0]
        for i in range(1, len(closes)):
            ema[i] = alpha * closes[i] + (1 - alpha) * ema[i-1]

        # ATR calculation
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )
        tr = np.insert(tr, 0, highs[0] - lows[0])

        # ATR as EMA of TR
        atr = np.zeros(len(tr))
        atr[0] = tr[0]
        for i in range(1, len(tr)):
            atr[i] = alpha * tr[i] + (1 - alpha) * atr[i-1]

        # Trim to match Bollinger output length
        offset = period - 1
        middle = ema[offset:]
        atr_trimmed = atr[offset:]

        upper = middle + (atr_mult * atr_trimmed)
        lower = middle - (atr_mult * atr_trimmed)

        return upper, middle, lower

    def calculate_momentum(self, closes: np.ndarray, period: int = 20,
                           smoothing: int = 5) -> Tuple[float, MomentumVector]:
        """
        Calculate momentum slope and vector.

        Uses linear regression slope of price vs time, smoothed.
        Returns: (slope, vector)
        """
        if len(closes) < period:
            return 0.0, MomentumVector.NEUTRAL

        # Get last `period` closes
        recent = closes[-period:]

        # Linear regression
        x = np.arange(period)
        slope, _ = np.polyfit(x, recent, 1)

        # Normalize slope by price level
        avg_price = np.mean(recent)
        normalized_slope = (slope / avg_price) * 100  # Percentage per bar

        # Determine vector
        if normalized_slope > 0.1:
            vector = MomentumVector.BULLISH
        elif normalized_slope < -0.1:
            vector = MomentumVector.BEARISH
        else:
            vector = MomentumVector.NEUTRAL

        return normalized_slope, vector

    def detect_squeeze(self, listing_id: str, bars: List[OHLCVBar]) -> Optional[SqueezeResult]:
        """
        Detect volatility squeeze condition.

        A squeeze occurs when Bollinger Bands contract inside Keltner Channels,
        indicating low volatility that often precedes a significant move.
        """
        config = self.configs.get(listing_id)
        if not config:
            config = SqueezeConfig(listing_id=listing_id)

        if len(bars) < max(config.bb_period, config.kc_period) + 5:
            logger.debug(f"{listing_id}: Not enough bars for squeeze detection")
            return None

        # Extract OHLCV arrays
        opens = np.array([b.open for b in bars])
        highs = np.array([b.high for b in bars])
        lows = np.array([b.low for b in bars])
        closes = np.array([b.close for b in bars])
        volumes = np.array([b.volume for b in bars])

        # Calculate indicators
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(
            closes, config.bb_period, config.bb_std_dev
        )

        kc_upper, kc_middle, kc_lower = self.calculate_keltner_channels(
            highs, lows, closes, config.kc_period, config.kc_atr_mult
        )

        if len(bb_upper) == 0 or len(kc_upper) == 0:
            return None

        # Use most recent values
        bb_width = (bb_upper[-1] - bb_lower[-1]) / bb_middle[-1]
        kc_width = (kc_upper[-1] - kc_lower[-1]) / kc_middle[-1]

        # Squeeze tightness: ratio of BB width to KC width
        # < 1.0 means BB is inside KC (squeeze)
        squeeze_tightness = bb_width / kc_width if kc_width > 0 else 1.0

        # Momentum
        momentum_slope, momentum_vector = self.calculate_momentum(
            closes, config.momentum_period, config.momentum_smoothing
        )

        # Volume ratio (current vs 20-bar average)
        avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        current_volume = volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Determine if squeeze is active
        is_squeeze = squeeze_tightness < config.squeeze_threshold

        # Calculate intensity (0-1 scale)
        # Higher intensity = tighter squeeze + stronger momentum
        squeeze_intensity = max(0, 1 - squeeze_tightness) if is_squeeze else 0
        momentum_intensity = min(1, abs(momentum_slope) / 0.5)  # Normalize to 0.5% as max
        intensity = (squeeze_intensity * 0.6) + (momentum_intensity * 0.4)
        intensity = min(1.0, max(0.0, intensity))

        # Determine delta type
        delta_type = None
        if is_squeeze:
            if volume_ratio > config.volume_surge_mult:
                # Squeeze is firing (breaking out)
                if momentum_vector == MomentumVector.BULLISH:
                    delta_type = DeltaType.SQUEEZE_FIRE_BULL
                elif momentum_vector == MomentumVector.BEARISH:
                    delta_type = DeltaType.SQUEEZE_FIRE_BEAR
            else:
                # Still in compression
                delta_type = DeltaType.VOLATILITY_SQUEEZE
        elif momentum_intensity > 0.7:
            # Strong momentum shift without squeeze
            if momentum_vector == MomentumVector.BULLISH:
                delta_type = DeltaType.MOMENTUM_SHIFT_BULL
            elif momentum_vector == MomentumVector.BEARISH:
                delta_type = DeltaType.MOMENTUM_SHIFT_BEAR

        return SqueezeResult(
            is_squeeze=is_squeeze,
            squeeze_tightness=squeeze_tightness,
            bollinger_width=bb_width,
            keltner_width=kc_width,
            momentum_slope=momentum_slope,
            momentum_vector=momentum_vector,
            volume_ratio=volume_ratio,
            intensity=intensity,
            delta_type=delta_type
        )

    def persist_regime_delta(self, listing_id: str, result: SqueezeResult,
                             canonical_regime: Optional[str]) -> Optional[str]:
        """
        Persist a regime delta detection to the database.

        Returns the delta_id if persisted, None otherwise.
        """
        if result.delta_type is None:
            return None

        if result.intensity < self.configs.get(listing_id, SqueezeConfig(listing_id)).intensity_min:
            logger.debug(f"{listing_id}: Intensity {result.intensity:.4f} below threshold")
            return None

        delta_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=self.ttl_hours)

        # Check regime alignment
        regime_alignment = False
        if canonical_regime:
            if canonical_regime in ['BULL', 'BULLISH'] and result.momentum_vector == MomentumVector.BULLISH:
                regime_alignment = True
            elif canonical_regime in ['BEAR', 'BEARISH'] and result.momentum_vector == MomentumVector.BEARISH:
                regime_alignment = True

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_operational.regime_delta (
                    delta_id, listing_id, timeframe, delta_type, intensity,
                    momentum_vector, bollinger_width, keltner_width,
                    squeeze_tightness, momentum_slope, volume_ratio,
                    canonical_regime, regime_alignment, ttl_hours, expires_at,
                    issuing_agent
                ) VALUES (
                    %s, %s, 'H1', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'FINN'
                )
            """, (
                delta_id, listing_id, result.delta_type.value, result.intensity,
                result.momentum_vector.value, result.bollinger_width, result.keltner_width,
                result.squeeze_tightness, result.momentum_slope, result.volume_ratio,
                canonical_regime, regime_alignment, self.ttl_hours, expires_at
            ))

            # Log the event
            cur.execute("""
                INSERT INTO fhq_operational.delta_log (
                    event_type, delta_id, listing_id, details
                ) VALUES (
                    'DELTA_DETECTED', %s, %s, %s
                )
            """, (
                delta_id, listing_id,
                f'{{"delta_type": "{result.delta_type.value}", "intensity": {result.intensity:.4f}, '
                f'"momentum": "{result.momentum_vector.value}", "squeeze_tightness": {result.squeeze_tightness:.4f}}}'
            ))

            self.conn.commit()

        logger.info(f"{listing_id}: Regime delta persisted - {result.delta_type.value} "
                   f"(intensity={result.intensity:.4f}, momentum={result.momentum_vector.value})")

        return delta_id

    def emit_flash_context(self, delta_id: str, listing_id: str,
                           result: SqueezeResult) -> Optional[str]:
        """
        Emit a Flash-Context object for the Signal Executor.

        Flash-Context carries the intraday permit with TTL.

        CEO-DIR-2026-0ZE-A v2: In OBSERVABILITY_ONLY_MODE, flash_context writes
        are blocked. Instead, we log what WOULD have been emitted to delta_log
        for audit purposes (hypothetical context).
        """
        config = self.configs.get(listing_id, SqueezeConfig(listing_id))

        context_id = str(uuid.uuid4())
        ttl_minutes = 60  # Default 1 hour TTL for flash context

        # Adjust TTL based on delta type
        if result.delta_type in [DeltaType.SQUEEZE_FIRE_BULL, DeltaType.SQUEEZE_FIRE_BEAR]:
            ttl_minutes = 30  # Shorter TTL for breakouts (act fast or miss it)
        elif result.delta_type == DeltaType.VOLATILITY_SQUEEZE:
            ttl_minutes = 120  # Longer TTL for compression (waiting for fire)

        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

        # Determine applicable strategies
        applicable_strategies = []
        if result.delta_type in [DeltaType.SQUEEZE_FIRE_BULL, DeltaType.SQUEEZE_FIRE_BEAR]:
            applicable_strategies = ['VOLATILITY_COMPRESSION_BREAKOUT', 'MOMENTUM_BURST']
        elif result.delta_type == DeltaType.VOLATILITY_SQUEEZE:
            applicable_strategies = ['VOLATILITY_COMPRESSION_BREAKOUT']
        elif result.delta_type in [DeltaType.MOMENTUM_SHIFT_BULL, DeltaType.MOMENTUM_SHIFT_BEAR]:
            applicable_strategies = ['TREND_FOLLOWING', 'MOMENTUM_CONTINUATION']

        # CEO-DIR-2026-0ZE-A v2: OBSERVABILITY-ONLY MODE CHECK
        if OBSERVABILITY_ONLY_MODE:
            # Log hypothetical context instead of emitting
            return self._log_hypothetical_context(
                delta_id, listing_id, result, context_id,
                ttl_minutes, applicable_strategies
            )

        # Normal mode: emit flash_context
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_operational.flash_context (
                    context_id, delta_id, listing_id, delta_type, intensity,
                    momentum_vector, target_signal_class, applicable_strategies,
                    ttl_minutes, expires_at, issuing_agent
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'FINN'
                )
            """, (
                context_id, delta_id, listing_id, result.delta_type.value,
                result.intensity, result.momentum_vector.value,
                'C',  # Target Class C signals primarily
                applicable_strategies,
                ttl_minutes, expires_at
            ))

            # Log the emission
            cur.execute("""
                INSERT INTO fhq_operational.delta_log (
                    event_type, delta_id, context_id, listing_id, details
                ) VALUES (
                    'FLASH_CONTEXT_EMITTED', %s, %s, %s, %s
                )
            """, (
                delta_id, context_id, listing_id,
                f'{{"ttl_minutes": {ttl_minutes}, "strategies": {applicable_strategies}}}'
            ))

            self.conn.commit()

        logger.info(f"{listing_id}: Flash-Context emitted - {context_id[:8]}... "
                   f"(TTL={ttl_minutes}min, strategies={applicable_strategies})")

        return context_id

    def _log_hypothetical_context(self, delta_id: str, listing_id: str,
                                   result: SqueezeResult, context_id: str,
                                   ttl_minutes: int,
                                   applicable_strategies: List[str]) -> Optional[str]:
        """
        CEO-DIR-2026-0ZE-A v2: Log hypothetical flash_context for audit.

        In observability-only mode, we don't write to flash_context table
        but we DO log what WOULD have been emitted. This allows:
        1. Audit trail of IOS-003-B decision quality
        2. Counterfactual analysis (what if we had executed?)
        3. Phase 1 evaluation without execution risk
        """
        import json

        hypothetical_context = {
            'context_id': context_id,
            'delta_id': delta_id,
            'listing_id': listing_id,
            'delta_type': result.delta_type.value,
            'intensity': float(result.intensity),
            'momentum_vector': result.momentum_vector.value,
            'target_signal_class': 'C',
            'applicable_strategies': applicable_strategies,
            'ttl_minutes': ttl_minutes,
            'mode': 'OBSERVABILITY_ONLY',
            'directive': 'CEO-DIR-2026-0ZE-A-v2'
        }

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_operational.delta_log (
                    event_type, delta_id, context_id, listing_id, details
                ) VALUES (
                    'HYPOTHETICAL_FLASH_CONTEXT', %s, %s, %s, %s
                )
            """, (
                delta_id, context_id, listing_id,
                json.dumps(hypothetical_context)
            ))

            self.conn.commit()

        logger.info(f"{listing_id}: HYPOTHETICAL Flash-Context logged - {context_id[:8]}... "
                   f"(TTL={ttl_minutes}min, strategies={applicable_strategies}) [OBSERVABILITY-ONLY]")

        return context_id

    def expire_stale_data(self):
        """Run TTL expiration for stale intraday data."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM fhq_operational.expire_intraday_data()")
            result = cur.fetchone()

            if result:
                if any(result.values()):
                    logger.info(f"Expired: {result['expired_deltas']} deltas, "
                              f"{result['expired_contexts']} contexts, "
                              f"{result['expired_bars_h1']} H1 bars, "
                              f"{result['expired_bars_h4']} H4 bars")

            self.conn.commit()

    def run_detection_cycle(self) -> Dict[str, Any]:
        """
        Run a single detection cycle for all target assets.

        Returns summary of detections.
        """
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'assets_processed': 0,
            'deltas_detected': 0,
            'contexts_emitted': 0,
            'details': []
        }

        # Check DEFCON first
        if not self.check_defcon_permit():
            logger.warning("DEFCON does not permit intraday operations - cycle skipped")
            summary['skipped_reason'] = 'DEFCON_DENIED'
            return summary

        for listing_id in self.target_assets:
            try:
                # Get H1 bars
                bars = self.aggregate_h1_bars(listing_id)

                if len(bars) < 25:
                    logger.debug(f"{listing_id}: Insufficient bars ({len(bars)})")
                    continue

                # Get canonical regime (READ-ONLY)
                canonical_regime = self.get_canonical_regime(listing_id)

                # Detect squeeze
                result = self.detect_squeeze(listing_id, bars)

                if result and result.delta_type:
                    # Persist delta
                    delta_id = self.persist_regime_delta(listing_id, result, canonical_regime)

                    if delta_id:
                        summary['deltas_detected'] += 1

                        # Emit flash context
                        context_id = self.emit_flash_context(delta_id, listing_id, result)

                        if context_id:
                            summary['contexts_emitted'] += 1

                        summary['details'].append({
                            'listing_id': listing_id,
                            'delta_type': result.delta_type.value,
                            'intensity': result.intensity,
                            'momentum': result.momentum_vector.value,
                            'canonical_regime': canonical_regime,
                            'delta_id': delta_id,
                            'context_id': context_id
                        })

                summary['assets_processed'] += 1

            except Exception as e:
                logger.error(f"{listing_id}: Detection failed - {e}")
                summary['details'].append({
                    'listing_id': listing_id,
                    'error': str(e)
                })

        # Expire stale data
        self.expire_stale_data()

        return summary

    def run_continuous(self, interval_minutes: int = 15):
        """Run continuous detection loop."""
        logger.info("=" * 60)
        logger.info("IoS-003-B INTRADAY REGIME-DELTA ENGINE STARTING")
        logger.info("=" * 60)
        logger.info(f"Target Assets: {self.target_assets}")
        logger.info(f"Detection Interval: {interval_minutes} minutes")
        logger.info(f"TTL Hours: {self.ttl_hours}")
        logger.info("=" * 60)
        logger.info("CANONICAL REGIME IS READ-ONLY - NO MODIFICATIONS")
        logger.info("=" * 60)

        self.connect()
        self.load_configs()

        cycle_count = 0

        try:
            while True:
                cycle_count += 1
                logger.info(f"--- Detection Cycle #{cycle_count} ---")

                summary = self.run_detection_cycle()

                logger.info(f"Cycle complete: {summary['assets_processed']} assets, "
                           f"{summary['deltas_detected']} deltas, "
                           f"{summary['contexts_emitted']} contexts")

                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self.disconnect()

    def run_once(self):
        """Run a single detection cycle and exit."""
        logger.info("Running single detection cycle...")

        self.connect()
        self.load_configs()

        try:
            summary = self.run_detection_cycle()

            logger.info("=" * 60)
            logger.info("DETECTION CYCLE COMPLETE")
            logger.info(f"Assets Processed: {summary['assets_processed']}")
            logger.info(f"Deltas Detected: {summary['deltas_detected']}")
            logger.info(f"Contexts Emitted: {summary['contexts_emitted']}")

            for detail in summary['details']:
                if 'error' in detail:
                    logger.error(f"  {detail['listing_id']}: ERROR - {detail['error']}")
                else:
                    logger.info(f"  {detail['listing_id']}: {detail['delta_type']} "
                              f"(intensity={detail['intensity']:.4f})")

            logger.info("=" * 60)

            return summary

        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description='IoS-003-B Intraday Regime-Delta Engine'
    )
    parser.add_argument('--interval', type=int, default=15,
                        help='Detection interval in minutes (default: 15)')
    parser.add_argument('--once', action='store_true',
                        help='Run single cycle and exit')
    parser.add_argument('--ttl', type=int, default=4,
                        help='TTL hours for regime deltas (default: 4)')
    parser.add_argument('--assets', type=str, default='BTC-USD,ETH-USD,SOL-USD',
                        help='Comma-separated list of assets to monitor')

    args = parser.parse_args()

    engine = IntradayRegimeDeltaEngine()
    engine.ttl_hours = args.ttl
    engine.target_assets = [a.strip() for a in args.assets.split(',')]

    if args.once:
        engine.run_once()
    else:
        engine.run_continuous(args.interval)


if __name__ == '__main__':
    main()
