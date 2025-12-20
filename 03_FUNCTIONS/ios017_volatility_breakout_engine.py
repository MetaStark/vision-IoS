"""
IoS-017: Volatility Breakout Engine
===================================
STIG-2025-001 Phase 2 Component

Detects Bollinger Band squeezes inside Keltner Channels
and generates breakout signals with causal driver amplification.

Authority: ADR-020 (ACI), IoS-017
"""

import os
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO, format='[IoS-017] %(message)s')
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


@dataclass
class SqueezeSignal:
    """Volatility squeeze breakout signal."""
    canonical_id: str
    signal_type: str  # SQUEEZE_LONG, SQUEEZE_SHORT
    squeeze_intensity: float  # 0-1, how tight the squeeze
    breakout_direction: str  # UP, DOWN
    bb_width: float
    kc_width: float
    momentum: float
    causal_bonus: float  # Amplification from causal parent breakout
    confidence: float
    timestamp: datetime


class VolatilityBreakoutEngine:
    """
    Detects BB squeezes inside KC and generates breakout signals.

    Squeeze Detection:
    - Bollinger Bands (20, 2.0) inside Keltner Channels (20, 1.5 ATR)
    - Squeeze intensity = 1 - (BB_width / KC_width)

    Breakout Signal:
    - Momentum > 0 after squeeze → LONG
    - Momentum < 0 after squeeze → SHORT

    Causal Amplification:
    - If causal parent already broke out, amplify signal confidence
    """

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0,
                 kc_period: int = 20, kc_atr_mult: float = 1.5):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.kc_period = kc_period
        self.kc_atr_mult = kc_atr_mult
        self.conn = None

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def get_price_data(self, canonical_id: str, lookback: int = 100) -> Optional[pd.DataFrame]:
        """Fetch price data for asset."""
        sql = """
            SELECT date, open, high, low, close, volume
            FROM fhq_data.price_series
            WHERE listing_id = %s AND resolution = '1d'
            ORDER BY date DESC
            LIMIT %s
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (canonical_id, lookback))
            rows = cur.fetchall()

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df = df.sort_values('date').reset_index(drop=True)
        return df

    def calculate_bollinger_bands(self, close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands."""
        sma = close.rolling(self.bb_period).mean()
        std = close.rolling(self.bb_period).std()
        upper = sma + (self.bb_std * std)
        lower = sma - (self.bb_std * std)
        return upper, sma, lower

    def calculate_keltner_channels(self, high: pd.Series, low: pd.Series,
                                    close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Keltner Channels using ATR."""
        # EMA for middle
        ema = close.ewm(span=self.kc_period, adjust=False).mean()

        # ATR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(self.kc_period).mean()

        upper = ema + (self.kc_atr_mult * atr)
        lower = ema - (self.kc_atr_mult * atr)
        return upper, ema, lower

    def calculate_momentum(self, close: pd.Series, period: int = 12) -> pd.Series:
        """Calculate momentum oscillator."""
        return close - close.shift(period)

    def detect_squeeze(self, df: pd.DataFrame) -> Dict:
        """
        Detect if asset is in squeeze and breakout direction.

        Returns dict with squeeze state and metrics.
        """
        bb_upper, bb_mid, bb_lower = self.calculate_bollinger_bands(df['close'])
        kc_upper, kc_mid, kc_lower = self.calculate_keltner_channels(
            df['high'], df['low'], df['close']
        )
        momentum = self.calculate_momentum(df['close'])

        # BB width and KC width
        bb_width = (bb_upper - bb_lower) / bb_mid
        kc_width = (kc_upper - kc_lower) / kc_mid

        # Squeeze: BB inside KC
        squeeze_on = (bb_lower.iloc[-1] > kc_lower.iloc[-1]) and \
                     (bb_upper.iloc[-1] < kc_upper.iloc[-1])

        # Was in squeeze before?
        squeeze_prev = (bb_lower.iloc[-2] > kc_lower.iloc[-2]) and \
                       (bb_upper.iloc[-2] < kc_upper.iloc[-2]) if len(df) > 1 else False

        # Squeeze intensity
        if kc_width.iloc[-1] > 0:
            intensity = max(0, 1 - (bb_width.iloc[-1] / kc_width.iloc[-1]))
        else:
            intensity = 0

        # Breakout detection: was in squeeze, now exiting
        breakout = squeeze_prev and not squeeze_on

        return {
            'squeeze_on': squeeze_on,
            'squeeze_prev': squeeze_prev,
            'breakout': breakout,
            'intensity': intensity,
            'bb_width': bb_width.iloc[-1],
            'kc_width': kc_width.iloc[-1],
            'momentum': momentum.iloc[-1],
            'momentum_direction': 'UP' if momentum.iloc[-1] > 0 else 'DOWN'
        }

    def get_causal_bonus(self, canonical_id: str) -> float:
        """
        Check if causal parents have already broken out.
        Returns amplification factor (1.0 = no bonus, up to 1.5).
        """
        # Query causal graph for parents
        sql = """
            SELECT source_id, edge_weight
            FROM fhq_alpha.causal_edges
            WHERE target_id = %s
              AND edge_type = 'CAUSAL_PARENT'
              AND is_active = true
            ORDER BY edge_weight DESC
            LIMIT 3
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (canonical_id,))
                parents = cur.fetchall()
        except:
            return 1.0

        if not parents:
            return 1.0

        # Check if any parent broke out recently
        bonus = 1.0
        for parent in parents:
            parent_df = self.get_price_data(parent['source_id'], 20)
            if parent_df is not None and len(parent_df) >= 20:
                parent_squeeze = self.detect_squeeze(parent_df)
                if parent_squeeze['breakout']:
                    # Parent broke out - amplify
                    bonus += 0.15 * parent['edge_weight']

        return min(bonus, 1.5)  # Cap at 50% bonus

    def scan_asset(self, canonical_id: str) -> Optional[SqueezeSignal]:
        """Scan single asset for squeeze breakout."""
        df = self.get_price_data(canonical_id)
        if df is None or len(df) < self.bb_period + 5:
            return None

        squeeze = self.detect_squeeze(df)

        # Only generate signal on breakout
        if not squeeze['breakout']:
            return None

        # Get causal amplification
        causal_bonus = self.get_causal_bonus(canonical_id)

        # Signal type based on momentum direction
        signal_type = f"SQUEEZE_{squeeze['momentum_direction']}"

        # Confidence based on intensity and causal bonus
        base_confidence = 0.5 + (squeeze['intensity'] * 0.3)
        confidence = min(base_confidence * causal_bonus, 0.95)

        return SqueezeSignal(
            canonical_id=canonical_id,
            signal_type=signal_type,
            squeeze_intensity=squeeze['intensity'],
            breakout_direction=squeeze['momentum_direction'],
            bb_width=squeeze['bb_width'],
            kc_width=squeeze['kc_width'],
            momentum=squeeze['momentum'],
            causal_bonus=causal_bonus,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc)
        )

    def scan_universe(self) -> List[SqueezeSignal]:
        """Scan all active assets for squeeze breakouts."""
        sql = """
            SELECT canonical_id FROM fhq_meta.assets
            WHERE active_flag = true
              AND data_quality_status IN ('FULL_HISTORY', 'SHORT_HISTORY')
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            assets = [r[0] for r in cur.fetchall()]

        signals = []
        for asset in assets:
            try:
                signal = self.scan_asset(asset)
                if signal:
                    signals.append(signal)
                    logger.info(f"SQUEEZE BREAKOUT: {asset} {signal.signal_type} "
                               f"conf={signal.confidence:.2f} causal_bonus={signal.causal_bonus:.2f}")
            except Exception as e:
                logger.error(f"Error scanning {asset}: {e}")
                try:
                    self.conn.rollback()  # Rollback to clear transaction error state
                except:
                    pass

        return signals

    def store_signals(self, signals: List[SqueezeSignal]):
        """Store signals in database."""
        if not signals:
            return

        sql = """
            INSERT INTO fhq_alpha.alpha_signals (
                signal_id, canonical_id, signal_type, strategy_source,
                confidence, signal_metadata, created_at
            ) VALUES (
                gen_random_uuid(), %s, %s, 'IOS017_VBO',
                %s, %s, NOW()
            )
        """
        with self.conn.cursor() as cur:
            for sig in signals:
                metadata = {
                    'squeeze_intensity': sig.squeeze_intensity,
                    'breakout_direction': sig.breakout_direction,
                    'bb_width': sig.bb_width,
                    'kc_width': sig.kc_width,
                    'momentum': sig.momentum,
                    'causal_bonus': sig.causal_bonus
                }
                cur.execute(sql, (
                    sig.canonical_id,
                    sig.signal_type,
                    sig.confidence,
                    psycopg2.extras.Json(metadata)
                ))
        self.conn.commit()


def run_vbo_scan():
    """Run volatility breakout scan."""
    engine = VolatilityBreakoutEngine()
    engine.connect()

    try:
        signals = engine.scan_universe()
        logger.info(f"Found {len(signals)} squeeze breakout signals")

        if signals:
            engine.store_signals(signals)
            logger.info("Signals stored to fhq_alpha.alpha_signals")

        return signals
    finally:
        engine.close()


if __name__ == '__main__':
    run_vbo_scan()
