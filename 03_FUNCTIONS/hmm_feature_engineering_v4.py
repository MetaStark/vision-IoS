#!/usr/bin/env python3
"""
IoS-003 v4 HMM Feature Engineering Module

Generates technical features and macro covariates for the modernized HMM regime detection.
Per CEO Directive IoS-003 v4 specification:
- 7 canonical technical features (z-scored)
- 4+ macro covariates for IOHMM transitions
- Asset-class specific features (crypto on-chain)

Authority: CEO Directive IoS-003 v4
Date: 2025-12-11
Executor: STIG (CTO)
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HMM_FEATURE_V4")

# Database config
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}


@dataclass
class FeatureConfig:
    """Configuration for feature engineering"""
    lookback_days: int = 252  # For z-score normalization
    volatility_window: int = 20
    roc_period: int = 20
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0


def get_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG)


def classify_asset_class(asset_id: str) -> str:
    """Classify asset into CRYPTO, FX, or EQUITIES"""
    crypto_suffixes = ['-USD', '-USDT', '-BTC', '-ETH']
    fx_patterns = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD', 'NOK', 'SEK']

    # Check crypto
    for suffix in crypto_suffixes:
        if asset_id.endswith(suffix):
            return 'CRYPTO'

    # Check FX (6 char pairs like EURUSD)
    if len(asset_id) == 6:
        base = asset_id[:3]
        quote = asset_id[3:]
        if base in fx_patterns and quote in fx_patterns:
            return 'FX'

    # Default to equities
    return 'EQUITIES'


def fetch_price_data(conn, asset_id: str, lookback_days: int = 365) -> pd.DataFrame:
    """Fetch OHLCV price data for asset"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            timestamp::date as date,
            open, high, low, close, volume
        FROM fhq_market.prices
        WHERE canonical_id = %s
        AND timestamp > NOW() - INTERVAL '%s days'
        ORDER BY timestamp
    """, (asset_id, lookback_days))

    rows = cur.fetchall()
    cur.close()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df[~df.index.duplicated(keep='last')]

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def fetch_macro_data(conn, lookback_days: int = 365) -> pd.DataFrame:
    """Fetch macro indicator data (VIX, yield spread, etc.)"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Try to get VIX data
    cur.execute("""
        SELECT
            timestamp::date as date,
            close as vix
        FROM fhq_market.prices
        WHERE canonical_id IN ('^VIX', 'VIX', 'VIXY')
        AND timestamp > NOW() - INTERVAL '%s days'
        ORDER BY timestamp
    """, (lookback_days,))

    vix_rows = cur.fetchall()

    # Try to get yield curve data from macro schema
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'fhq_macro'
            AND table_name = 'yield_curve'
        )
    """)
    has_yield = cur.fetchone()['exists']

    yield_rows = []
    if has_yield:
        cur.execute("""
            SELECT
                observation_date as date,
                value_10y - value_3m as yield_spread
            FROM fhq_macro.yield_curve
            WHERE observation_date > NOW() - INTERVAL '%s days'
            ORDER BY observation_date
        """, (lookback_days,))
        yield_rows = cur.fetchall()

    cur.close()

    # Combine into DataFrame
    macro_df = pd.DataFrame(index=pd.date_range(
        end=datetime.now(), periods=lookback_days, freq='D'
    ))

    if vix_rows:
        vix_df = pd.DataFrame(vix_rows)
        vix_df['date'] = pd.to_datetime(vix_df['date'])
        vix_df = vix_df.set_index('date')
        vix_df = vix_df[~vix_df.index.duplicated(keep='last')]
        macro_df = macro_df.join(vix_df, how='left')
    else:
        macro_df['vix'] = np.nan

    if yield_rows:
        yield_df = pd.DataFrame(yield_rows)
        yield_df['date'] = pd.to_datetime(yield_df['date'])
        yield_df = yield_df.set_index('date')
        yield_df = yield_df[~yield_df.index.duplicated(keep='last')]
        macro_df = macro_df.join(yield_df, how='left')
    else:
        macro_df['yield_spread'] = np.nan

    # Forward fill macro data (less frequent updates)
    macro_df = macro_df.ffill().bfill()

    return macro_df


def compute_rolling_zscore(series: pd.Series, window: int = 252) -> pd.Series:
    """Compute rolling z-score with given window"""
    rolling_mean = series.rolling(window=window, min_periods=20).mean()
    rolling_std = series.rolling(window=window, min_periods=20).std()

    # Avoid division by zero
    rolling_std = rolling_std.replace(0, np.nan)

    zscore = (series - rolling_mean) / rolling_std
    return zscore.clip(-5, 5)  # Clip extreme values


def compute_technical_features(df: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """
    Compute 7 canonical technical features per IoS-003 v4 spec.
    All features are z-scored using 252-day rolling windows.
    """
    features = pd.DataFrame(index=df.index)

    # 1. Return (log return)
    features['return'] = np.log(df['close'] / df['close'].shift(1))
    features['return_z'] = compute_rolling_zscore(features['return'], config.lookback_days)

    # 2. Volatility (20-day rolling std of returns)
    features['volatility'] = features['return'].rolling(window=config.volatility_window).std()
    features['volatility_z'] = compute_rolling_zscore(features['volatility'], config.lookback_days)

    # 3. Drawdown (close vs rolling max)
    rolling_max = df['close'].rolling(window=config.lookback_days, min_periods=1).max()
    features['drawdown'] = (df['close'] - rolling_max) / rolling_max
    features['drawdown_z'] = compute_rolling_zscore(features['drawdown'], config.lookback_days)

    # 4. MACD Histogram (momentum)
    ema_fast = df['close'].ewm(span=config.macd_fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=config.macd_slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=config.macd_signal, adjust=False).mean()
    features['macd_diff'] = macd_line - signal_line
    features['macd_diff_z'] = compute_rolling_zscore(features['macd_diff'], config.lookback_days)

    # 5. Bollinger Band Width
    sma = df['close'].rolling(window=config.bb_period).mean()
    std = df['close'].rolling(window=config.bb_period).std()
    features['bb_width'] = (config.bb_std * 2 * std) / sma
    features['bb_width_z'] = compute_rolling_zscore(features['bb_width'], config.lookback_days)

    # 6. RSI-14
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=config.rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=config.rsi_period).mean()
    rs = gain / loss.replace(0, np.nan)
    features['rsi_14'] = 100 - (100 / (1 + rs))
    features['rsi_14_z'] = compute_rolling_zscore(features['rsi_14'], config.lookback_days)

    # 7. Rate of Change (ROC-20)
    features['roc_20'] = (df['close'] - df['close'].shift(config.roc_period)) / df['close'].shift(config.roc_period)
    features['roc_20_z'] = compute_rolling_zscore(features['roc_20'], config.lookback_days)

    # Return only z-scored features
    return features[['return_z', 'volatility_z', 'drawdown_z', 'macd_diff_z',
                     'bb_width_z', 'rsi_14_z', 'roc_20_z']]


def compute_macro_covariates(macro_df: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """
    Compute macro covariates for IOHMM transition modeling.
    These drive the transition probabilities.
    """
    covariates = pd.DataFrame(index=macro_df.index)

    # VIX z-score
    if 'vix' in macro_df.columns:
        covariates['vix_z'] = compute_rolling_zscore(macro_df['vix'], config.lookback_days)
    else:
        covariates['vix_z'] = np.nan

    # Yield spread z-score
    if 'yield_spread' in macro_df.columns:
        covariates['yield_spread_z'] = compute_rolling_zscore(
            macro_df['yield_spread'], config.lookback_days
        )
    else:
        covariates['yield_spread_z'] = np.nan

    # Placeholder for inflation and liquidity (require additional data sources)
    covariates['inflation_z'] = np.nan
    covariates['liquidity_z'] = np.nan

    return covariates


def compute_crypto_features(asset_id: str, conn, config: FeatureConfig) -> pd.DataFrame:
    """
    Compute crypto-specific on-chain features.
    Currently placeholders - would require on-chain data integration.
    """
    # Placeholder implementation
    # Real implementation would fetch from fhq_crypto.onchain
    return pd.DataFrame()


def compute_all_features(
    asset_id: str,
    conn,
    config: Optional[FeatureConfig] = None
) -> Tuple[pd.DataFrame, str]:
    """
    Compute all features for an asset.

    Returns:
        Tuple of (features_df, asset_class)
    """
    if config is None:
        config = FeatureConfig()

    asset_class = classify_asset_class(asset_id)
    logger.info(f"Computing features for {asset_id} (class: {asset_class})")

    # Fetch price data
    price_df = fetch_price_data(conn, asset_id, config.lookback_days + 100)
    if price_df.empty:
        logger.warning(f"No price data for {asset_id}")
        return pd.DataFrame(), asset_class

    # Compute technical features
    technical = compute_technical_features(price_df, config)

    # Fetch and compute macro covariates
    macro_df = fetch_macro_data(conn, config.lookback_days + 100)
    covariates = compute_macro_covariates(macro_df, config)

    # Align indices
    features = technical.join(covariates, how='left')

    # Add crypto-specific features if applicable
    if asset_class == 'CRYPTO':
        crypto_features = compute_crypto_features(asset_id, conn, config)
        if not crypto_features.empty:
            features = features.join(crypto_features, how='left')
        else:
            features['onchain_hash_z'] = np.nan
            features['onchain_tx_z'] = np.nan

    # Build feature vector and covariate vector as JSON arrays
    tech_cols = ['return_z', 'volatility_z', 'drawdown_z', 'macd_diff_z',
                 'bb_width_z', 'rsi_14_z', 'roc_20_z']
    cov_cols = ['yield_spread_z', 'vix_z', 'liquidity_z']

    features['feature_vector'] = features[tech_cols].apply(
        lambda row: json.dumps([float(x) if pd.notna(x) else None for x in row]), axis=1
    )
    features['covariate_vector'] = features[cov_cols].apply(
        lambda row: json.dumps([float(x) if pd.notna(x) else None for x in row]), axis=1
    )

    features['asset_class'] = asset_class

    return features, asset_class


def save_features_to_db(
    conn,
    asset_id: str,
    features: pd.DataFrame,
    asset_class: str
) -> int:
    """Save computed features to hmm_features_v4 table"""
    if features.empty:
        return 0

    cur = conn.cursor()

    # Prepare data for insertion
    rows = []
    for date, row in features.iterrows():
        rows.append((
            asset_id,
            date.date() if isinstance(date, pd.Timestamp) else date,
            float(row['return_z']) if pd.notna(row.get('return_z')) else None,
            float(row['volatility_z']) if pd.notna(row.get('volatility_z')) else None,
            float(row['drawdown_z']) if pd.notna(row.get('drawdown_z')) else None,
            float(row['macd_diff_z']) if pd.notna(row.get('macd_diff_z')) else None,
            float(row['bb_width_z']) if pd.notna(row.get('bb_width_z')) else None,
            float(row['rsi_14_z']) if pd.notna(row.get('rsi_14_z')) else None,
            float(row['roc_20_z']) if pd.notna(row.get('roc_20_z')) else None,
            float(row['yield_spread_z']) if pd.notna(row.get('yield_spread_z')) else None,
            float(row['vix_z']) if pd.notna(row.get('vix_z')) else None,
            float(row['inflation_z']) if pd.notna(row.get('inflation_z')) else None,
            float(row['liquidity_z']) if pd.notna(row.get('liquidity_z')) else None,
            float(row.get('onchain_hash_z')) if pd.notna(row.get('onchain_hash_z')) else None,
            float(row.get('onchain_tx_z')) if pd.notna(row.get('onchain_tx_z')) else None,
            row.get('feature_vector'),
            row.get('covariate_vector'),
            asset_class
        ))

    # Upsert into table
    execute_values(
        cur,
        """
        INSERT INTO fhq_perception.hmm_features_v4 (
            asset_id, timestamp,
            return_z, volatility_z, drawdown_z, macd_diff_z, bb_width_z, rsi_14_z, roc_20_z,
            yield_spread_z, vix_z, inflation_z, liquidity_z,
            onchain_hash_z, onchain_tx_z,
            feature_vector, covariate_vector, asset_class
        ) VALUES %s
        ON CONFLICT (asset_id, timestamp) DO UPDATE SET
            return_z = EXCLUDED.return_z,
            volatility_z = EXCLUDED.volatility_z,
            drawdown_z = EXCLUDED.drawdown_z,
            macd_diff_z = EXCLUDED.macd_diff_z,
            bb_width_z = EXCLUDED.bb_width_z,
            rsi_14_z = EXCLUDED.rsi_14_z,
            roc_20_z = EXCLUDED.roc_20_z,
            yield_spread_z = EXCLUDED.yield_spread_z,
            vix_z = EXCLUDED.vix_z,
            inflation_z = EXCLUDED.inflation_z,
            liquidity_z = EXCLUDED.liquidity_z,
            onchain_hash_z = EXCLUDED.onchain_hash_z,
            onchain_tx_z = EXCLUDED.onchain_tx_z,
            feature_vector = EXCLUDED.feature_vector,
            covariate_vector = EXCLUDED.covariate_vector
        """,
        rows
    )

    conn.commit()
    cur.close()

    return len(rows)


class HMMFeatureEngineering:
    """
    HMM Feature Engineering class for IoS-003 v4.
    Provides a consistent interface for feature computation.
    """

    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()

    def compute_features_for_asset(
        self,
        conn,
        asset_id: str,
        asset_class: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Compute features for a single asset.

        Args:
            conn: Database connection
            asset_id: Asset identifier
            asset_class: Optional asset class override

        Returns:
            DataFrame with features indexed by date, or None if insufficient data
        """
        features, detected_class = compute_all_features(asset_id, conn, self.config)

        if features.empty:
            return None

        return features


def process_all_assets(conn, limit: Optional[int] = None) -> Dict[str, Any]:
    """Process features for all active assets"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get list of assets with price data
    cur.execute("""
        SELECT DISTINCT canonical_id
        FROM fhq_market.prices
        WHERE timestamp > NOW() - INTERVAL '30 days'
        ORDER BY canonical_id
    """)

    assets = [row['canonical_id'] for row in cur.fetchall()]
    cur.close()

    if limit:
        assets = assets[:limit]

    results = {
        'processed': 0,
        'failed': 0,
        'by_class': {'CRYPTO': 0, 'FX': 0, 'EQUITIES': 0},
        'errors': []
    }

    for asset_id in assets:
        try:
            features, asset_class = compute_all_features(asset_id, conn)
            if not features.empty:
                count = save_features_to_db(conn, asset_id, features, asset_class)
                results['processed'] += 1
                results['by_class'][asset_class] += 1
                logger.info(f"Saved {count} feature rows for {asset_id}")
            else:
                results['failed'] += 1
        except Exception as e:
            logger.error(f"Error processing {asset_id}: {e}")
            results['failed'] += 1
            results['errors'].append({'asset': asset_id, 'error': str(e)})

    return results


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("IoS-003 v4 HMM Feature Engineering")
    logger.info("=" * 60)

    conn = get_connection()

    try:
        results = process_all_assets(conn, limit=None)

        logger.info(f"\nResults:")
        logger.info(f"  Processed: {results['processed']}")
        logger.info(f"  Failed: {results['failed']}")
        logger.info(f"  By class: {results['by_class']}")

        if results['errors']:
            logger.warning(f"  Errors: {len(results['errors'])}")

        return results

    finally:
        conn.close()


if __name__ == '__main__':
    main()
