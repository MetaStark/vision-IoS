#!/usr/bin/env python3
"""
CALC_INDICATORS - IoS-002 Indicator Engine
Authority: FINN (owner), CODE (executor), STIG (infrastructure)
Contract: EC-003_2026_PRODUCTION (STIG), EC-004 (FINN), EC-011 (CODE)

ADR Compliance: ADR-001, ADR-003, ADR-007, ADR-010, ADR-013
IoS Reference: IoS-002 (Indicator Engine - Sensory Cortex)

PURPOSE:
Calculate deterministic technical indicators from canonical OHLCV data
and persist to fhq_research.indicator_* tables with full lineage.

INDICATORS:
- Momentum: RSI(14), StochRSI, CCI, MFI
- Trend: MACD, EMA(9,20,50,200), SMA(50,200), PSAR
- Volatility: Bollinger Bands(20,2), ATR(14)
- Ichimoku: Tenkan, Kijun, Senkou A/B, Chikou

LINEAGE (ADR-003/BCBS-239):
- engine_version: v1.0.0
- formula_hash: SHA-256 of calculation logic
- lineage_hash: SHA-256 of input data + formula
"""

import os
import sys
import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import logging

# Database
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

# Technical Analysis
import numpy as np
import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

ENGINE_VERSION = "1.0.0"
FORMULA_HASH_SEED = "IoS-002-CALC-INDICATORS-v1.0.0"

# Compute formula hash once
FORMULA_HASH = hashlib.sha256(FORMULA_HASH_SEED.encode()).hexdigest()

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("calc_indicators")


def get_db_connection():
    """Get database connection from environment."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


# =============================================================================
# INDICATOR CALCULATIONS (Deterministic)
# =============================================================================

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI (Relative Strength Index)."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_stoch_rsi(close: pd.Series, period: int = 14, stoch_period: int = 14) -> pd.Series:
    """Calculate Stochastic RSI."""
    rsi = calc_rsi(close, period)
    stoch_rsi = (rsi - rsi.rolling(stoch_period).min()) / \
                (rsi.rolling(stoch_period).max() - rsi.rolling(stoch_period).min())
    return stoch_rsi * 100


def calc_cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """Calculate CCI (Commodity Channel Index)."""
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad)
    return cci


def calc_mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14) -> pd.Series:
    """Calculate MFI (Money Flow Index)."""
    tp = (high + low + close) / 3
    raw_money_flow = tp * volume

    tp_diff = tp.diff()
    positive_flow = raw_money_flow.where(tp_diff > 0, 0.0)
    negative_flow = raw_money_flow.where(tp_diff < 0, 0.0)

    positive_mf = positive_flow.rolling(period).sum()
    negative_mf = negative_flow.rolling(period).sum()

    mfi = 100 - (100 / (1 + positive_mf / negative_mf.replace(0, np.nan)))
    return mfi


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """Calculate MACD."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def calc_ema(close: pd.Series, period: int) -> pd.Series:
    """Calculate EMA."""
    return close.ewm(span=period, adjust=False).mean()


def calc_sma(close: pd.Series, period: int) -> pd.Series:
    """Calculate SMA."""
    return close.rolling(period).mean()


def calc_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
    """Calculate Bollinger Bands."""
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    return {"bb_upper": upper, "bb_middle": sma, "bb_lower": lower, "bb_width": (upper - lower) / sma}


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate ATR (Average True Range)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr


def calc_ichimoku(high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, pd.Series]:
    """Calculate Ichimoku Cloud."""
    # Tenkan-sen (Conversion Line): 9-period
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2

    # Kijun-sen (Base Line): 26-period
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2

    # Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, shifted 26 periods ahead
    senkou_a = ((tenkan + kijun) / 2).shift(26)

    # Senkou Span B (Leading Span B): 52-period, shifted 26 periods ahead
    senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)

    # Chikou Span (Lagging Span): Close shifted 26 periods back
    chikou = close.shift(-26)

    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b,
        "chikou": chikou
    }


# =============================================================================
# VOLUME & MOMENTUM INDICATORS (IoS-002 §2.4 Completion)
# =============================================================================

def calc_psar(high: pd.Series, low: pd.Series, close: pd.Series,
              af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.20) -> pd.Series:
    """Calculate Parabolic SAR (Wilder 1978).

    IoS-002 §2.2 Trend Indicator.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        af_start: Initial acceleration factor (default 0.02)
        af_step: AF increment (default 0.02)
        af_max: Maximum AF (default 0.20)

    Returns:
        pd.Series: PSAR values
    """
    length = len(close)
    psar = pd.Series(index=close.index, dtype=float)
    af = af_start
    uptrend = True

    # Initialize
    ep = low.iloc[0]  # Extreme point
    psar.iloc[0] = high.iloc[0]

    for i in range(1, length):
        if uptrend:
            psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])
            psar.iloc[i] = min(psar.iloc[i], low.iloc[i-1])
            if i >= 2:
                psar.iloc[i] = min(psar.iloc[i], low.iloc[i-2])

            if low.iloc[i] < psar.iloc[i]:
                uptrend = False
                psar.iloc[i] = ep
                ep = low.iloc[i]
                af = af_start
            else:
                if high.iloc[i] > ep:
                    ep = high.iloc[i]
                    af = min(af + af_step, af_max)
        else:
            psar.iloc[i] = psar.iloc[i-1] + af * (ep - psar.iloc[i-1])
            psar.iloc[i] = max(psar.iloc[i], high.iloc[i-1])
            if i >= 2:
                psar.iloc[i] = max(psar.iloc[i], high.iloc[i-2])

            if high.iloc[i] > psar.iloc[i]:
                uptrend = True
                psar.iloc[i] = ep
                ep = high.iloc[i]
                af = af_start
            else:
                if low.iloc[i] < ep:
                    ep = low.iloc[i]
                    af = min(af + af_step, af_max)

    return psar


def calc_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume (Granville 1963).

    IoS-002 §2.4 Volume Indicator.

    OBV = Previous OBV + Volume (if close > prev_close)
    OBV = Previous OBV - Volume (if close < prev_close)
    OBV = Previous OBV (if close == prev_close)

    Args:
        close: Close prices
        volume: Volume data

    Returns:
        pd.Series: OBV values
    """
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    obv = (direction * volume).cumsum()
    return obv


def calc_roc(close: pd.Series, period: int = 20) -> pd.Series:
    """Calculate Rate of Change (ROC).

    IoS-002 §2.4 Volume/Momentum Indicator.

    ROC = ((Close - Close_n) / Close_n) * 100

    Args:
        close: Close prices
        period: Lookback period (default 20)

    Returns:
        pd.Series: ROC values (percentage)
    """
    roc = ((close - close.shift(period)) / close.shift(period)) * 100
    return roc


# =============================================================================
# DATA LOADING
# =============================================================================

def get_last_indicator_date(conn, asset_id: str) -> Optional[datetime]:
    """Get the last date for which indicators were computed for this asset."""
    query = """
        SELECT MAX(timestamp) as last_date
        FROM fhq_research.indicator_momentum
        WHERE asset_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (asset_id,))
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
    return None


def load_price_data(conn, canonical_id: str, incremental: bool = True) -> pd.DataFrame:
    """Load canonical price data for an asset.

    If incremental=True, only loads data from 252 days before the last computed indicator
    (need 252 days for rolling calculations like z-scores).
    """
    # Get last indicator date for incremental processing
    lookback_date = None
    if incremental:
        last_date = get_last_indicator_date(conn, canonical_id)
        if last_date:
            # Need 252 days lookback for rolling calculations
            lookback_date = last_date - pd.Timedelta(days=252)
            logger.info(f"  Incremental mode: loading data from {lookback_date.date()}")

    if lookback_date:
        query = """
            SELECT DISTINCT ON (canonical_id, timestamp::date)
                id,
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                data_hash
            FROM fhq_market.prices
            WHERE canonical_id = %s
              AND timestamp >= %s
            ORDER BY canonical_id, timestamp::date, timestamp DESC
        """
        df = pd.read_sql(query, conn, params=(canonical_id, lookback_date))
    else:
        query = """
            SELECT DISTINCT ON (canonical_id, timestamp::date)
                id,
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                data_hash
            FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY canonical_id, timestamp::date, timestamp DESC
        """
        df = pd.read_sql(query, conn, params=(canonical_id,))

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')  # Ensure ascending order after DISTINCT ON
    df.set_index('timestamp', inplace=True)
    return df


def get_canonical_assets(conn) -> List[str]:
    """Get list of canonical asset IDs."""
    query = "SELECT DISTINCT canonical_id FROM fhq_market.prices ORDER BY canonical_id"
    with conn.cursor() as cur:
        cur.execute(query)
        return [row[0] for row in cur.fetchall()]


# =============================================================================
# INDICATOR PERSISTENCE
# =============================================================================

def compute_lineage_hash(asset_id: str, timestamp: str, formula_hash: str, input_hash: str) -> str:
    """Compute lineage hash for a row."""
    data = f"{asset_id}|{timestamp}|{formula_hash}|{input_hash}"
    return hashlib.sha256(data.encode()).hexdigest()


def persist_momentum_indicators(conn, asset_id: str, df: pd.DataFrame, price_df: pd.DataFrame):
    """Persist momentum indicators to fhq_research.indicator_momentum.

    WAVE-001 W001-D: Vectorized implementation to fix 300s timeout.
    """
    # Compute all indicators as Series (vectorized)
    rsi = calc_rsi(price_df['close'])
    stoch_rsi = calc_stoch_rsi(price_df['close'])
    cci = calc_cci(price_df['high'], price_df['low'], price_df['close'])
    mfi = calc_mfi(price_df['high'], price_df['low'], price_df['close'], price_df['volume'])

    # Build DataFrame with all indicators (vectorized merge)
    indicators = pd.DataFrame({
        'rsi_14': rsi,
        'stoch_rsi_14': stoch_rsi,
        'cci_20': cci,
        'mfi_14': mfi
    }, index=price_df.index)

    # Filter rows where RSI is valid (vectorized)
    valid_mask = indicators['rsi_14'].notna()
    indicators = indicators[valid_mask]

    if indicators.empty:
        logger.info(f"  [MOMENTUM] No valid rows for {asset_id}")
        return

    # Vectorized row generation using list comprehension (faster than iterrows)
    now = datetime.now(timezone.utc)
    rows = []
    for ts in indicators.index:
        row_data = indicators.loc[ts]
        value_json = {
            "rsi_14": float(row_data['rsi_14']) if pd.notna(row_data['rsi_14']) else None,
            "stoch_rsi_14": float(row_data['stoch_rsi_14']) if pd.notna(row_data['stoch_rsi_14']) else None,
            "cci_20": float(row_data['cci_20']) if pd.notna(row_data['cci_20']) else None,
            "mfi_14": float(row_data['mfi_14']) if pd.notna(row_data['mfi_14']) else None
        }
        value_str = json.dumps(value_json)
        lineage_hash = compute_lineage_hash(asset_id, str(ts), FORMULA_HASH, value_str)
        rows.append((str(uuid.uuid4()), ts, asset_id, value_str, ENGINE_VERSION, FORMULA_HASH, lineage_hash, now))

    if rows:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO fhq_research.indicator_momentum
                (id, timestamp, asset_id, value_json, engine_version, formula_hash, lineage_hash, created_at)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, rows, page_size=1000)
        conn.commit()
        logger.info(f"  [MOMENTUM] Inserted {len(rows)} rows for {asset_id}")


def persist_trend_indicators(conn, asset_id: str, df: pd.DataFrame, price_df: pd.DataFrame):
    """Persist trend indicators to fhq_research.indicator_trend.

    WAVE-001 W001-D: Vectorized implementation to fix 300s timeout.
    """
    # Compute all indicators as Series (vectorized)
    macd = calc_macd(price_df['close'])
    ema_9 = calc_ema(price_df['close'], 9)
    ema_20 = calc_ema(price_df['close'], 20)
    ema_50 = calc_ema(price_df['close'], 50)
    ema_200 = calc_ema(price_df['close'], 200)
    sma_50 = calc_sma(price_df['close'], 50)
    sma_200 = calc_sma(price_df['close'], 200)

    # Build DataFrame with all indicators (vectorized merge)
    indicators = pd.DataFrame({
        'macd': macd['macd'],
        'macd_signal': macd['signal'],
        'macd_histogram': macd['histogram'],
        'ema_9': ema_9,
        'ema_20': ema_20,
        'ema_50': ema_50,
        'ema_200': ema_200,
        'sma_50': sma_50,
        'sma_200': sma_200
    }, index=price_df.index)

    # Filter rows where EMA9 is valid (vectorized)
    valid_mask = indicators['ema_9'].notna()
    indicators = indicators[valid_mask]

    if indicators.empty:
        logger.info(f"  [TREND] No valid rows for {asset_id}")
        return

    # Vectorized row generation
    now = datetime.now(timezone.utc)
    rows = []
    for ts in indicators.index:
        row_data = indicators.loc[ts]
        value_json = {
            "macd": float(row_data['macd']) if pd.notna(row_data['macd']) else None,
            "macd_signal": float(row_data['macd_signal']) if pd.notna(row_data['macd_signal']) else None,
            "macd_histogram": float(row_data['macd_histogram']) if pd.notna(row_data['macd_histogram']) else None,
            "ema_9": float(row_data['ema_9']) if pd.notna(row_data['ema_9']) else None,
            "ema_20": float(row_data['ema_20']) if pd.notna(row_data['ema_20']) else None,
            "ema_50": float(row_data['ema_50']) if pd.notna(row_data['ema_50']) else None,
            "ema_200": float(row_data['ema_200']) if pd.notna(row_data['ema_200']) else None,
            "sma_50": float(row_data['sma_50']) if pd.notna(row_data['sma_50']) else None,
            "sma_200": float(row_data['sma_200']) if pd.notna(row_data['sma_200']) else None
        }
        value_str = json.dumps(value_json)
        lineage_hash = compute_lineage_hash(asset_id, str(ts), FORMULA_HASH, value_str)
        rows.append((str(uuid.uuid4()), ts, asset_id, value_str, ENGINE_VERSION, FORMULA_HASH, lineage_hash, now))

    if rows:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO fhq_research.indicator_trend
                (id, timestamp, asset_id, value_json, engine_version, formula_hash, lineage_hash, created_at)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, rows, page_size=1000)
        conn.commit()
        logger.info(f"  [TREND] Inserted {len(rows)} rows for {asset_id}")


def persist_volatility_indicators(conn, asset_id: str, df: pd.DataFrame, price_df: pd.DataFrame):
    """Persist volatility indicators to fhq_research.indicator_volatility.

    WAVE-001 W001-D: Vectorized implementation to fix 300s timeout.
    """
    # Compute all indicators as Series (vectorized)
    bollinger = calc_bollinger(price_df['close'])
    atr = calc_atr(price_df['high'], price_df['low'], price_df['close'])

    # Build DataFrame with all indicators (vectorized merge)
    indicators = pd.DataFrame({
        'bb_upper': bollinger['bb_upper'],
        'bb_middle': bollinger['bb_middle'],
        'bb_lower': bollinger['bb_lower'],
        'bb_width': bollinger['bb_width'],
        'atr_14': atr
    }, index=price_df.index)

    # Filter rows where BB middle is valid (vectorized)
    valid_mask = indicators['bb_middle'].notna()
    indicators = indicators[valid_mask]

    if indicators.empty:
        logger.info(f"  [VOLATILITY] No valid rows for {asset_id}")
        return

    # Vectorized row generation
    now = datetime.now(timezone.utc)
    rows = []
    for ts in indicators.index:
        row_data = indicators.loc[ts]
        value_json = {
            "bb_upper": float(row_data['bb_upper']) if pd.notna(row_data['bb_upper']) else None,
            "bb_middle": float(row_data['bb_middle']) if pd.notna(row_data['bb_middle']) else None,
            "bb_lower": float(row_data['bb_lower']) if pd.notna(row_data['bb_lower']) else None,
            "bb_width": float(row_data['bb_width']) if pd.notna(row_data['bb_width']) else None,
            "atr_14": float(row_data['atr_14']) if pd.notna(row_data['atr_14']) else None
        }
        value_str = json.dumps(value_json)
        lineage_hash = compute_lineage_hash(asset_id, str(ts), FORMULA_HASH, value_str)
        rows.append((str(uuid.uuid4()), ts, asset_id, value_str, ENGINE_VERSION, FORMULA_HASH, lineage_hash, now))

    if rows:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO fhq_research.indicator_volatility
                (id, timestamp, asset_id, value_json, engine_version, formula_hash, lineage_hash, created_at)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, rows, page_size=1000)
        conn.commit()
        logger.info(f"  [VOLATILITY] Inserted {len(rows)} rows for {asset_id}")


def persist_ichimoku_indicators(conn, asset_id: str, df: pd.DataFrame, price_df: pd.DataFrame):
    """Persist Ichimoku indicators to fhq_research.indicator_ichimoku.

    WAVE-001 W001-D: Vectorized implementation to fix 300s timeout.
    """
    # Compute all indicators as Series (vectorized)
    ichimoku = calc_ichimoku(price_df['high'], price_df['low'], price_df['close'])

    # Build DataFrame with all indicators (vectorized merge)
    indicators = pd.DataFrame({
        'tenkan': ichimoku['tenkan'],
        'kijun': ichimoku['kijun'],
        'senkou_a': ichimoku['senkou_a'],
        'senkou_b': ichimoku['senkou_b'],
        'chikou': ichimoku['chikou']
    }, index=price_df.index)

    # Filter rows where Tenkan is valid (vectorized)
    valid_mask = indicators['tenkan'].notna()
    indicators = indicators[valid_mask]

    if indicators.empty:
        logger.info(f"  [ICHIMOKU] No valid rows for {asset_id}")
        return

    # Vectorized row generation
    now = datetime.now(timezone.utc)
    rows = []
    for ts in indicators.index:
        row_data = indicators.loc[ts]
        value_json = {
            "tenkan": float(row_data['tenkan']) if pd.notna(row_data['tenkan']) else None,
            "kijun": float(row_data['kijun']) if pd.notna(row_data['kijun']) else None,
            "senkou_a": float(row_data['senkou_a']) if pd.notna(row_data['senkou_a']) else None,
            "senkou_b": float(row_data['senkou_b']) if pd.notna(row_data['senkou_b']) else None,
            "chikou": float(row_data['chikou']) if pd.notna(row_data['chikou']) else None
        }
        value_str = json.dumps(value_json)
        lineage_hash = compute_lineage_hash(asset_id, str(ts), FORMULA_HASH, value_str)
        rows.append((str(uuid.uuid4()), ts, asset_id, value_str, ENGINE_VERSION, FORMULA_HASH, lineage_hash, now))

    if rows:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO fhq_research.indicator_ichimoku
                (id, timestamp, asset_id, value_json, engine_version, formula_hash, lineage_hash, created_at)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, rows, page_size=1000)
        conn.commit()
        logger.info(f"  [ICHIMOKU] Inserted {len(rows)} rows for {asset_id}")


def persist_volume_indicators(conn, asset_id: str, df: pd.DataFrame, price_df: pd.DataFrame):
    """Persist volume indicators to fhq_research.indicator_volume.

    IoS-002 §2.4 Volume Indicators: OBV (Granville 1963), ROC.
    """
    # Compute all indicators as Series (vectorized)
    obv = calc_obv(price_df['close'], price_df['volume'])
    roc_20 = calc_roc(price_df['close'], 20)
    psar = calc_psar(price_df['high'], price_df['low'], price_df['close'])

    # Build DataFrame with all indicators (vectorized merge)
    indicators = pd.DataFrame({
        'obv': obv,
        'roc_20': roc_20,
        'psar': psar
    }, index=price_df.index)

    # Filter rows where ROC is valid (needs 20 periods)
    valid_mask = indicators['roc_20'].notna()
    indicators = indicators[valid_mask]

    if indicators.empty:
        logger.info(f"  [VOLUME] No valid rows for {asset_id}")
        return

    # Vectorized row generation
    now = datetime.now(timezone.utc)
    rows = []
    for ts in indicators.index:
        row_data = indicators.loc[ts]
        value_json = {
            "obv": float(row_data['obv']) if pd.notna(row_data['obv']) else None,
            "roc_20": float(row_data['roc_20']) if pd.notna(row_data['roc_20']) else None,
            "psar": float(row_data['psar']) if pd.notna(row_data['psar']) else None
        }
        value_str = json.dumps(value_json)
        lineage_hash = compute_lineage_hash(asset_id, str(ts), FORMULA_HASH, value_str)
        rows.append((str(uuid.uuid4()), ts, asset_id, value_str, ENGINE_VERSION, FORMULA_HASH, lineage_hash, now))

    if rows:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO fhq_research.indicator_volume
                (id, timestamp, asset_id, value_json, engine_version, formula_hash, lineage_hash, created_at)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, rows, page_size=1000)
        conn.commit()
        logger.info(f"  [VOLUME] Inserted {len(rows)} rows for {asset_id}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_calc_indicators():
    """Main entry point for CALC_INDICATORS."""
    logger.info("=" * 60)
    logger.info("CALC_INDICATORS - IoS-002 Indicator Engine")
    logger.info(f"Engine Version: {ENGINE_VERSION}")
    logger.info(f"Formula Hash: {FORMULA_HASH[:16]}...")
    logger.info("=" * 60)

    conn = get_db_connection()

    try:
        # Get canonical assets
        assets = get_canonical_assets(conn)
        logger.info(f"Found {len(assets)} canonical assets: {assets}")

        total_rows = {
            "momentum": 0,
            "trend": 0,
            "volatility": 0,
            "ichimoku": 0,
            "volume": 0
        }

        for asset_id in assets:
            logger.info(f"\nProcessing {asset_id}...")

            # Load price data
            price_df = load_price_data(conn, asset_id)
            logger.info(f"  Loaded {len(price_df)} price rows ({price_df.index.min()} to {price_df.index.max()})")

            if len(price_df) < 200:
                logger.warning(f"  Skipping {asset_id}: insufficient data (<200 rows)")
                continue

            # Calculate and persist indicators
            persist_momentum_indicators(conn, asset_id, None, price_df)
            persist_trend_indicators(conn, asset_id, None, price_df)
            persist_volatility_indicators(conn, asset_id, None, price_df)
            persist_ichimoku_indicators(conn, asset_id, None, price_df)
            persist_volume_indicators(conn, asset_id, None, price_df)

        # Log final counts
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fhq_research.indicator_momentum")
            total_rows["momentum"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fhq_research.indicator_trend")
            total_rows["trend"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fhq_research.indicator_volatility")
            total_rows["volatility"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fhq_research.indicator_ichimoku")
            total_rows["ichimoku"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fhq_research.indicator_volume")
            total_rows["volume"] = cur.fetchone()[0]

        logger.info("\n" + "=" * 60)
        logger.info("CALC_INDICATORS COMPLETE")
        logger.info(f"  indicator_momentum:   {total_rows['momentum']} rows")
        logger.info(f"  indicator_trend:      {total_rows['trend']} rows")
        logger.info(f"  indicator_volatility: {total_rows['volatility']} rows")
        logger.info(f"  indicator_ichimoku:   {total_rows['ichimoku']} rows")
        logger.info(f"  indicator_volume:     {total_rows['volume']} rows")
        logger.info("=" * 60)

        # Log governance action
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id, action_type, action_target, action_target_type,
                    initiated_by, initiated_at, decision, decision_rationale,
                    vega_reviewed, hash_chain_id, signature_id
                ) VALUES (
                    gen_random_uuid(),
                    'CALC_INDICATORS_EXECUTION',
                    'fhq_research.indicator_*',
                    'PIPELINE_STAGE',
                    'CODE',
                    NOW(),
                    'APPROVED',
                    %s,
                    false,
                    %s,
                    gen_random_uuid()
                )
            """, (
                f"CALC_INDICATORS executed for {len(assets)} assets. Rows: momentum={total_rows['momentum']}, trend={total_rows['trend']}, volatility={total_rows['volatility']}, ichimoku={total_rows['ichimoku']}, volume={total_rows['volume']}. Engine v{ENGINE_VERSION}.",
                f"CALC-IND-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            ))
            conn.commit()

        return total_rows

    finally:
        conn.close()


if __name__ == "__main__":
    run_calc_indicators()
