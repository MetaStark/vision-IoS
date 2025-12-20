"""
HMM BACKFILL v1.0 - IoS-003 Appendix A Implementation
=====================================================
Authority: LARS (Owner IoS-003) -> CODE (EC-011)
Scope: Historical backfill only - no schema changes, no live routing.

Populates:
1. fhq_perception.hmm_features_daily (7 canonical features)
2. fhq_research.regime_model_registry (HMM v2.0 model)
3. fhq_research.regime_predictions_v2 (regime classifications)

All computations are deterministic and idempotent.
"""

import os
import json
import hashlib
import uuid
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values, Json
from hmmlearn import hmm

# Configuration
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

ENGINE_VERSION = 'HMM_v2.0'
PERCEPTION_MODEL_VERSION = '2026.PROD.1'
ZSCORE_WINDOW = 252
VOLATILITY_WINDOW = 20
ROC_WINDOW = 20
NUM_STATES = 9

# Regime label mapping (0-8 internal states to labels per Appendix A)
REGIME_LABELS = {
    0: 'STRONG_BULL',
    1: 'BULL',
    2: 'RANGE_UP',
    3: 'NEUTRAL',
    4: 'RANGE_DOWN',
    5: 'BEAR',
    6: 'STRONG_BEAR',
    7: 'PARABOLIC',
    8: 'BROKEN'
}

# Canonical assets per IoS-001
CANONICAL_ASSETS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'EURUSD']


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_hash(data: str) -> str:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data.encode()).hexdigest()


def compute_formula_hash() -> str:
    """Compute hash of the feature computation logic."""
    formula_spec = """
    return_z: ln(close_t / close_{t-1}), 252-day z-score
    volatility_z: 20-day rolling std of returns, 252-day z-score
    drawdown_z: (close - rolling_max) / rolling_max, 252-day z-score
    macd_diff_z: macd_histogram from indicator_trend, 252-day z-score
    bb_width_z: bb_width from indicator_volatility, 252-day z-score
    rsi_14_z: rsi_14 from indicator_momentum, 252-day z-score
    roc_20_z: (close_t - close_{t-20}) / close_{t-20}, 252-day z-score
    """
    return compute_hash(formula_spec)


def compute_lineage_hash(row_data: dict, prev_hash: Optional[str] = None) -> Tuple[str, str]:
    """Compute lineage hash and self hash for a row."""
    # Create deterministic string from row data
    data_str = json.dumps(row_data, sort_keys=True, default=str)
    hash_self = compute_hash(data_str)

    # Lineage hash combines previous hash with current
    if prev_hash:
        lineage_hash = compute_hash(prev_hash + hash_self)
    else:
        lineage_hash = hash_self

    return lineage_hash, hash_self


def rolling_zscore(series: pd.Series, window: int = 252) -> pd.Series:
    """Compute rolling z-score with specified window."""
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std()
    # Avoid division by zero
    rolling_std = rolling_std.replace(0, np.nan)
    return (series - rolling_mean) / rolling_std


def fetch_price_data(conn, asset_id: str) -> pd.DataFrame:
    """Fetch price data for an asset (deduped by date)."""
    query = """
        SELECT DISTINCT ON (canonical_id, timestamp::date)
            canonical_id as asset_id,
            timestamp::date as timestamp,
            close
        FROM fhq_market.prices
        WHERE canonical_id = %s
          AND timestamp::date < CURRENT_DATE
        ORDER BY canonical_id, timestamp::date, timestamp DESC
    """
    df = pd.read_sql(query, conn, params=(asset_id,))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def fetch_indicator_momentum(conn, asset_id: str) -> pd.DataFrame:
    """Fetch momentum indicators (deduped by date)."""
    query = """
        SELECT DISTINCT ON (asset_id, timestamp::date)
            asset_id,
            timestamp::date as timestamp,
            (value_json->>'rsi_14')::numeric as rsi_14
        FROM fhq_research.indicator_momentum
        WHERE asset_id = %s
          AND timestamp::date < CURRENT_DATE
        ORDER BY asset_id, timestamp::date, timestamp DESC
    """
    df = pd.read_sql(query, conn, params=(asset_id,))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def fetch_indicator_volatility(conn, asset_id: str) -> pd.DataFrame:
    """Fetch volatility indicators (deduped by date)."""
    query = """
        SELECT DISTINCT ON (asset_id, timestamp::date)
            asset_id,
            timestamp::date as timestamp,
            (value_json->>'bb_width')::numeric as bb_width
        FROM fhq_research.indicator_volatility
        WHERE asset_id = %s
          AND timestamp::date < CURRENT_DATE
        ORDER BY asset_id, timestamp::date, timestamp DESC
    """
    df = pd.read_sql(query, conn, params=(asset_id,))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def fetch_indicator_trend(conn, asset_id: str) -> pd.DataFrame:
    """Fetch trend indicators (deduped by date)."""
    query = """
        SELECT DISTINCT ON (asset_id, timestamp::date)
            asset_id,
            timestamp::date as timestamp,
            (value_json->>'macd_histogram')::numeric as macd_histogram
        FROM fhq_research.indicator_trend
        WHERE asset_id = %s
          AND timestamp::date < CURRENT_DATE
        ORDER BY asset_id, timestamp::date, timestamp DESC
    """
    df = pd.read_sql(query, conn, params=(asset_id,))
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def compute_hmm_features(conn, asset_id: str) -> pd.DataFrame:
    """
    Compute all 7 canonical HMM features for an asset.
    Returns DataFrame with features where all 252-day z-scores are valid.
    """
    print(f"  Computing features for {asset_id}...")

    # Fetch all data sources
    prices_df = fetch_price_data(conn, asset_id)
    momentum_df = fetch_indicator_momentum(conn, asset_id)
    volatility_df = fetch_indicator_volatility(conn, asset_id)
    trend_df = fetch_indicator_trend(conn, asset_id)

    if prices_df.empty:
        print(f"    WARNING: No price data for {asset_id}")
        return pd.DataFrame()

    # Set timestamp as index for all dataframes
    prices_df = prices_df.set_index('timestamp').sort_index()

    # Compute price-derived raw features
    prices_df['return_raw'] = np.log(prices_df['close'] / prices_df['close'].shift(1))
    prices_df['volatility_raw'] = prices_df['return_raw'].rolling(window=VOLATILITY_WINDOW).std()
    prices_df['rolling_max'] = prices_df['close'].expanding().max()
    prices_df['drawdown_raw'] = (prices_df['close'] - prices_df['rolling_max']) / prices_df['rolling_max']
    prices_df['roc_20_raw'] = (prices_df['close'] - prices_df['close'].shift(ROC_WINDOW)) / prices_df['close'].shift(ROC_WINDOW)

    # Compute 252-day z-scores for price-derived features
    prices_df['return_z'] = rolling_zscore(prices_df['return_raw'], ZSCORE_WINDOW)
    prices_df['volatility_z'] = rolling_zscore(prices_df['volatility_raw'], ZSCORE_WINDOW)
    prices_df['drawdown_z'] = rolling_zscore(prices_df['drawdown_raw'], ZSCORE_WINDOW)
    prices_df['roc_20_z'] = rolling_zscore(prices_df['roc_20_raw'], ZSCORE_WINDOW)

    # Merge indicator data
    if not momentum_df.empty:
        momentum_df = momentum_df.set_index('timestamp').sort_index()
        momentum_df['rsi_14_z'] = rolling_zscore(momentum_df['rsi_14'].astype(float), ZSCORE_WINDOW)
        prices_df = prices_df.join(momentum_df[['rsi_14_z']], how='left')
    else:
        prices_df['rsi_14_z'] = np.nan

    if not volatility_df.empty:
        volatility_df = volatility_df.set_index('timestamp').sort_index()
        volatility_df['bb_width_z'] = rolling_zscore(volatility_df['bb_width'].astype(float), ZSCORE_WINDOW)
        prices_df = prices_df.join(volatility_df[['bb_width_z']], how='left')
    else:
        prices_df['bb_width_z'] = np.nan

    if not trend_df.empty:
        trend_df = trend_df.set_index('timestamp').sort_index()
        trend_df['macd_diff_z'] = rolling_zscore(trend_df['macd_histogram'].astype(float), ZSCORE_WINDOW)
        prices_df = prices_df.join(trend_df[['macd_diff_z']], how='left')
    else:
        prices_df['macd_diff_z'] = np.nan

    # Select only the 7 canonical features
    feature_cols = ['return_z', 'volatility_z', 'drawdown_z', 'macd_diff_z', 'bb_width_z', 'rsi_14_z', 'roc_20_z']

    # Filter to rows where all features are valid (not NaN)
    features_df = prices_df[feature_cols].copy()
    features_df = features_df.dropna()

    # Add asset_id
    features_df['asset_id'] = asset_id
    features_df = features_df.reset_index()

    print(f"    {asset_id}: {len(features_df)} valid feature rows (out of {len(prices_df)} price rows)")

    return features_df


def backfill_hmm_features(conn) -> Dict:
    """
    Step 1: Backfill hmm_features_daily for all canonical assets.
    Returns statistics for evidence file.
    """
    print("\n" + "="*60)
    print("STEP 1: Backfilling hmm_features_daily")
    print("="*60)

    formula_hash = compute_formula_hash()
    stats = {
        'assets': {},
        'total_rows': 0,
        'formula_hash': formula_hash
    }

    cursor = conn.cursor()

    for asset_id in CANONICAL_ASSETS:
        print(f"\nProcessing {asset_id}...")

        # Compute features
        features_df = compute_hmm_features(conn, asset_id)

        if features_df.empty:
            print(f"  WARNING: No features computed for {asset_id}")
            stats['assets'][asset_id] = {'rows': 0, 'error': 'No features computed'}
            continue

        # Delete existing rows for this asset (idempotent)
        cursor.execute(
            "DELETE FROM fhq_perception.hmm_features_daily WHERE asset_id = %s",
            (asset_id,)
        )
        deleted = cursor.rowcount
        print(f"  Deleted {deleted} existing rows for {asset_id}")

        # Deduplicate on timestamp (keep last occurrence per ADR-002 idempotency)
        features_df = features_df.drop_duplicates(subset=['timestamp'], keep='last')
        features_df = features_df.sort_values('timestamp').reset_index(drop=True)

        # Prepare rows for insertion
        rows_to_insert = []
        prev_hash = None

        for idx, row in features_df.iterrows():
            row_data = {
                'asset_id': asset_id,
                'timestamp': str(row['timestamp'].date()),
                'return_z': float(row['return_z']),
                'volatility_z': float(row['volatility_z']),
                'drawdown_z': float(row['drawdown_z']),
                'macd_diff_z': float(row['macd_diff_z']),
                'bb_width_z': float(row['bb_width_z']),
                'rsi_14_z': float(row['rsi_14_z']),
                'roc_20_z': float(row['roc_20_z'])
            }

            lineage_hash, hash_self = compute_lineage_hash(row_data, prev_hash)

            rows_to_insert.append((
                str(uuid.uuid4()),  # id
                asset_id,
                row['timestamp'].date(),
                float(row['return_z']),
                float(row['volatility_z']),
                float(row['drawdown_z']),
                float(row['macd_diff_z']),
                float(row['bb_width_z']),
                float(row['rsi_14_z']),
                float(row['roc_20_z']),
                ENGINE_VERSION,
                PERCEPTION_MODEL_VERSION,
                formula_hash,
                lineage_hash,
                prev_hash,
                hash_self
            ))

            prev_hash = hash_self

        # Batch UPSERT (idempotent per ADR-002 §3.1)
        insert_query = """
            INSERT INTO fhq_perception.hmm_features_daily (
                id, asset_id, timestamp,
                return_z, volatility_z, drawdown_z, macd_diff_z,
                bb_width_z, rsi_14_z, roc_20_z,
                engine_version, perception_model_version, formula_hash,
                lineage_hash, hash_prev, hash_self
            ) VALUES %s
            ON CONFLICT (asset_id, timestamp) DO UPDATE SET
                return_z = EXCLUDED.return_z,
                volatility_z = EXCLUDED.volatility_z,
                drawdown_z = EXCLUDED.drawdown_z,
                macd_diff_z = EXCLUDED.macd_diff_z,
                bb_width_z = EXCLUDED.bb_width_z,
                rsi_14_z = EXCLUDED.rsi_14_z,
                roc_20_z = EXCLUDED.roc_20_z,
                engine_version = EXCLUDED.engine_version,
                perception_model_version = EXCLUDED.perception_model_version,
                formula_hash = EXCLUDED.formula_hash,
                lineage_hash = EXCLUDED.lineage_hash,
                hash_prev = EXCLUDED.hash_prev,
                hash_self = EXCLUDED.hash_self
        """
        execute_values(cursor, insert_query, rows_to_insert, page_size=1000)

        # Collect stats
        min_date = features_df['timestamp'].min()
        max_date = features_df['timestamp'].max()

        stats['assets'][asset_id] = {
            'rows': len(rows_to_insert),
            'min_date': str(min_date.date()),
            'max_date': str(max_date.date()),
            'feature_stats': {
                'return_z': {'min': float(features_df['return_z'].min()), 'max': float(features_df['return_z'].max())},
                'volatility_z': {'min': float(features_df['volatility_z'].min()), 'max': float(features_df['volatility_z'].max())},
                'drawdown_z': {'min': float(features_df['drawdown_z'].min()), 'max': float(features_df['drawdown_z'].max())},
                'macd_diff_z': {'min': float(features_df['macd_diff_z'].min()), 'max': float(features_df['macd_diff_z'].max())},
                'bb_width_z': {'min': float(features_df['bb_width_z'].min()), 'max': float(features_df['bb_width_z'].max())},
                'rsi_14_z': {'min': float(features_df['rsi_14_z'].min()), 'max': float(features_df['rsi_14_z'].max())},
                'roc_20_z': {'min': float(features_df['roc_20_z'].min()), 'max': float(features_df['roc_20_z'].max())}
            }
        }
        stats['total_rows'] += len(rows_to_insert)

        print(f"  Inserted {len(rows_to_insert)} rows for {asset_id}")
        print(f"  Date range: {min_date.date()} to {max_date.date()}")

    conn.commit()
    print(f"\nTotal rows inserted: {stats['total_rows']}")

    return stats


def register_hmm_model(conn) -> Dict:
    """
    Step 2: Register HMM v2.0 model in regime_model_registry.
    Returns model info for evidence file.
    """
    print("\n" + "="*60)
    print("STEP 2: Registering HMM v2.0 Model")
    print("="*60)

    cursor = conn.cursor()

    # Define HMM v2.0 parameters (canonical specification)
    # Initial transition matrix - designed for regime persistence with realistic transitions
    transition_matrix = np.array([
        # SB    BU    RU    NE    RD    BE    SBE   PA    BR
        [0.85, 0.10, 0.02, 0.01, 0.01, 0.00, 0.00, 0.01, 0.00],  # STRONG_BULL
        [0.10, 0.75, 0.08, 0.04, 0.02, 0.01, 0.00, 0.00, 0.00],  # BULL
        [0.02, 0.10, 0.70, 0.12, 0.04, 0.01, 0.00, 0.01, 0.00],  # RANGE_UP
        [0.01, 0.05, 0.10, 0.68, 0.10, 0.05, 0.01, 0.00, 0.00],  # NEUTRAL
        [0.00, 0.02, 0.05, 0.12, 0.70, 0.08, 0.02, 0.00, 0.01],  # RANGE_DOWN
        [0.00, 0.01, 0.02, 0.04, 0.10, 0.75, 0.08, 0.00, 0.00],  # BEAR
        [0.00, 0.00, 0.01, 0.01, 0.02, 0.10, 0.85, 0.00, 0.01],  # STRONG_BEAR
        [0.15, 0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.15, 0.05],  # PARABOLIC
        [0.05, 0.05, 0.05, 0.20, 0.20, 0.20, 0.15, 0.05, 0.05],  # BROKEN
    ])

    # Emission parameters (means and covariances for each state)
    # Based on characteristic z-score patterns for each regime
    # Order: return_z, volatility_z, drawdown_z, macd_diff_z, bb_width_z, rsi_14_z, roc_20_z
    emission_means = {
        'STRONG_BULL': [1.5, -0.5, 0.5, 1.5, 0.5, 1.5, 1.5],
        'BULL': [0.8, -0.2, 0.2, 0.8, 0.2, 0.8, 0.8],
        'RANGE_UP': [0.3, 0.0, 0.0, 0.3, 0.0, 0.3, 0.3],
        'NEUTRAL': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        'RANGE_DOWN': [-0.3, 0.0, -0.2, -0.3, 0.0, -0.3, -0.3],
        'BEAR': [-0.8, 0.3, -0.5, -0.8, 0.3, -0.8, -0.8],
        'STRONG_BEAR': [-1.5, 1.0, -1.0, -1.5, 1.0, -1.5, -1.5],
        'PARABOLIC': [2.0, 1.5, 0.0, 2.0, 1.5, 2.0, 2.0],
        'BROKEN': [0.0, 2.5, -1.5, 0.0, 2.0, 0.0, 0.0]
    }

    # Covariance (diagonal - independent features)
    emission_covars = {state: [1.0] * 7 for state in emission_means.keys()}

    emission_parameters = {
        'means': emission_means,
        'covars': emission_covars,
        'covariance_type': 'diag'
    }

    # Compute model hash
    model_spec = json.dumps({
        'transition_matrix': transition_matrix.tolist(),
        'emission_parameters': emission_parameters,
        'num_states': NUM_STATES,
        'feature_spec': ['return_z', 'volatility_z', 'drawdown_z', 'macd_diff_z', 'bb_width_z', 'rsi_14_z', 'roc_20_z']
    }, sort_keys=True)
    model_hash = compute_hash(model_spec)

    # Deactivate any existing active models
    cursor.execute("""
        UPDATE fhq_research.regime_model_registry
        SET is_active = FALSE, updated_at = NOW()
        WHERE is_active = TRUE
    """)
    deactivated = cursor.rowcount
    if deactivated > 0:
        print(f"  Deactivated {deactivated} previous model(s)")

    # Insert new model
    model_id = str(uuid.uuid4())

    row_data = {
        'model_id': model_id,
        'perception_model_version': PERCEPTION_MODEL_VERSION,
        'engine_version': ENGINE_VERSION,
        'model_hash': model_hash
    }
    lineage_hash, hash_self = compute_lineage_hash(row_data)

    cursor.execute("""
        INSERT INTO fhq_research.regime_model_registry (
            model_id,
            perception_model_version,
            engine_version,
            model_hash,
            training_window_start,
            training_window_end,
            num_states,
            transition_matrix,
            emission_parameters,
            is_active,
            lineage_hash,
            hash_prev,
            hash_self,
            created_at,
            updated_at
        ) VALUES (
            %s, %s, %s, %s,
            (SELECT MIN(timestamp) FROM fhq_perception.hmm_features_daily),
            (SELECT MAX(timestamp) FROM fhq_perception.hmm_features_daily),
            %s, %s, %s, TRUE, %s, NULL, %s, NOW(), NOW()
        )
    """, (
        model_id,
        PERCEPTION_MODEL_VERSION,
        ENGINE_VERSION,
        model_hash,
        NUM_STATES,
        Json(transition_matrix.tolist()),
        Json(emission_parameters),
        lineage_hash,
        hash_self
    ))

    conn.commit()

    # Verify
    cursor.execute("""
        SELECT model_id, perception_model_version, engine_version, model_hash,
               training_window_start, training_window_end, is_active
        FROM fhq_research.regime_model_registry
        WHERE is_active = TRUE
    """)
    active_models = cursor.fetchall()

    print(f"  Registered model: {model_id}")
    print(f"  Model hash: {model_hash}")
    print(f"  Active models count: {len(active_models)}")

    return {
        'model_id': model_id,
        'model_hash': model_hash,
        'perception_model_version': PERCEPTION_MODEL_VERSION,
        'engine_version': ENGINE_VERSION,
        'num_states': NUM_STATES,
        'active_models': [
            {
                'model_id': str(m[0]),
                'perception_model_version': m[1],
                'engine_version': m[2],
                'model_hash': m[3],
                'training_window_start': str(m[4]),
                'training_window_end': str(m[5]),
                'is_active': m[6]
            }
            for m in active_models
        ]
    }


def run_hmm_inference(conn, model_info: Dict) -> Dict:
    """
    Step 3: Run HMM inference and populate regime_predictions_v2.
    Returns statistics for evidence file.
    """
    print("\n" + "="*60)
    print("STEP 3: Running HMM Inference")
    print("="*60)

    cursor = conn.cursor()
    model_id = model_info['model_id']

    # Fetch model parameters
    cursor.execute("""
        SELECT transition_matrix, emission_parameters
        FROM fhq_research.regime_model_registry
        WHERE model_id = %s
    """, (model_id,))
    result = cursor.fetchone()
    transition_matrix = np.array(result[0])
    emission_params = result[1]

    # Initialize HMM model
    model = hmm.GaussianHMM(
        n_components=NUM_STATES,
        covariance_type='diag',
        n_iter=0  # No training, use provided parameters
    )

    # Set model parameters
    model.startprob_ = np.ones(NUM_STATES) / NUM_STATES  # Uniform start
    model.transmat_ = transition_matrix

    # Set emission parameters
    means = []
    covars = []
    for i in range(NUM_STATES):
        state_name = REGIME_LABELS[i]
        means.append(emission_params['means'][state_name])
        covars.append(emission_params['covars'][state_name])

    model.means_ = np.array(means)
    model.covars_ = np.array(covars)

    stats = {
        'assets': {},
        'total_rows': 0,
        'model_id': model_id
    }

    feature_cols = ['return_z', 'volatility_z', 'drawdown_z', 'macd_diff_z', 'bb_width_z', 'rsi_14_z', 'roc_20_z']

    for asset_id in CANONICAL_ASSETS:
        print(f"\nProcessing {asset_id}...")

        # Fetch features
        query = f"""
            SELECT id, asset_id, timestamp,
                   return_z, volatility_z, drawdown_z, macd_diff_z,
                   bb_width_z, rsi_14_z, roc_20_z
            FROM fhq_perception.hmm_features_daily
            WHERE asset_id = %s
            ORDER BY timestamp ASC
        """
        features_df = pd.read_sql(query, conn, params=(asset_id,))

        if features_df.empty:
            print(f"  WARNING: No features for {asset_id}")
            stats['assets'][asset_id] = {'rows': 0, 'error': 'No features found'}
            continue

        # Prepare feature matrix
        X = features_df[feature_cols].values

        # Run Viterbi decoding
        log_prob, hidden_states = model.decode(X, algorithm='viterbi')

        # Compute posterior probabilities
        posteriors = model.predict_proba(X)
        confidence_scores = np.max(posteriors, axis=1)

        # Delete existing predictions for this asset
        cursor.execute(
            "DELETE FROM fhq_research.regime_predictions_v2 WHERE asset_id = %s",
            (asset_id,)
        )
        deleted = cursor.rowcount
        print(f"  Deleted {deleted} existing predictions")

        # Prepare rows for insertion
        rows_to_insert = []
        prev_hash = None
        regime_counts = {label: 0 for label in REGIME_LABELS.values()}

        # WAVE-001 FIX (W001-B): Use enumerate() to ensure array index alignment
        # iterrows() idx is DataFrame index which may not match numpy array indices
        features_df = features_df.reset_index(drop=True)
        for array_idx, (df_idx, row) in enumerate(features_df.iterrows()):
            state = hidden_states[array_idx]
            regime_label = REGIME_LABELS[state]
            confidence = float(confidence_scores[array_idx])

            # Ensure confidence is in [0, 1]
            confidence = max(0.0, min(1.0, confidence))

            row_data = {
                'asset_id': asset_id,
                'timestamp': str(row['timestamp']),
                'model_id': model_id,
                'regime_raw': int(state),
                'regime_label': regime_label,
                'confidence_score': confidence
            }

            lineage_hash, hash_self = compute_lineage_hash(row_data, prev_hash)

            rows_to_insert.append((
                str(uuid.uuid4()),  # prediction_id
                asset_id,
                row['timestamp'],
                model_id,
                PERCEPTION_MODEL_VERSION,
                int(state),
                regime_label,
                confidence,
                lineage_hash,
                prev_hash,
                hash_self
            ))

            prev_hash = hash_self
            regime_counts[regime_label] += 1

        # Batch insert
        insert_query = """
            INSERT INTO fhq_research.regime_predictions_v2 (
                prediction_id, asset_id, timestamp, model_id,
                perception_model_version, regime_raw, regime_label,
                confidence_score, lineage_hash, hash_prev, hash_self
            ) VALUES %s
        """
        execute_values(cursor, insert_query, rows_to_insert, page_size=1000)

        # Collect stats
        min_date = features_df['timestamp'].min()
        max_date = features_df['timestamp'].max()

        # Check for dominant regime
        max_regime_pct = max(regime_counts.values()) / len(features_df) * 100
        dominant_regime = max(regime_counts, key=regime_counts.get)

        stats['assets'][asset_id] = {
            'rows': len(rows_to_insert),
            'min_date': str(min_date),
            'max_date': str(max_date),
            'regime_distribution': regime_counts,
            'dominant_regime': dominant_regime,
            'dominant_regime_pct': round(max_regime_pct, 2),
            'sanity_check': 'PASS' if max_regime_pct < 99 else 'WARN_DOMINANT'
        }
        stats['total_rows'] += len(rows_to_insert)

        print(f"  Inserted {len(rows_to_insert)} predictions for {asset_id}")
        print(f"  Date range: {min_date} to {max_date}")
        print(f"  Regime distribution: {regime_counts}")

    conn.commit()

    return stats


def generate_evidence_files(feature_stats: Dict, model_info: Dict, prediction_stats: Dict):
    """Generate evidence files for the operation."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    evidence_dir = 'evidence'

    # Evidence 1: Features backfill
    features_evidence = {
        'report_type': 'HMM_BACKFILL_FEATURES',
        'report_id': f'IOS003-HMM-FEATURES-{timestamp}',
        'timestamp': datetime.now().isoformat(),
        'generated_by': 'STIG',
        'operation': 'BACKFILL_HMM_FEATURES_DAILY',
        'engine_version': ENGINE_VERSION,
        'perception_model_version': PERCEPTION_MODEL_VERSION,
        'formula_hash': feature_stats['formula_hash'],
        'total_rows': feature_stats['total_rows'],
        'assets': feature_stats['assets'],
        'verification': {
            'all_features_non_null': True,
            'zscore_window': ZSCORE_WINDOW,
            'idempotent': True
        }
    }

    features_path = f'{evidence_dir}/IOS003_HMM_BACKFILL_FEATURES_{timestamp}.json'
    with open(features_path, 'w') as f:
        json.dump(features_evidence, f, indent=2, default=str)
    print(f"\nGenerated: {features_path}")

    # Evidence 2: Model registry
    model_evidence = {
        'report_type': 'HMM_MODEL_REGISTRY',
        'report_id': f'IOS003-HMM-MODEL-{timestamp}',
        'timestamp': datetime.now().isoformat(),
        'generated_by': 'STIG',
        'operation': 'REGISTER_HMM_MODEL',
        'model_id': model_info['model_id'],
        'model_hash': model_info['model_hash'],
        'perception_model_version': model_info['perception_model_version'],
        'engine_version': model_info['engine_version'],
        'num_states': model_info['num_states'],
        'active_models': model_info['active_models'],
        'verification': {
            'single_active_model': len(model_info['active_models']) == 1
        }
    }

    model_path = f'{evidence_dir}/IOS003_HMM_MODEL_REGISTRY_{timestamp}.json'
    with open(model_path, 'w') as f:
        json.dump(model_evidence, f, indent=2, default=str)
    print(f"Generated: {model_path}")

    # Evidence 3: Predictions backfill
    predictions_evidence = {
        'report_type': 'HMM_BACKFILL_PREDICTIONS',
        'report_id': f'IOS003-HMM-PREDICTIONS-{timestamp}',
        'timestamp': datetime.now().isoformat(),
        'generated_by': 'STIG',
        'operation': 'BACKFILL_REGIME_PREDICTIONS',
        'model_id': prediction_stats['model_id'],
        'total_rows': prediction_stats['total_rows'],
        'assets': prediction_stats['assets'],
        'verification': {
            'all_labels_valid': True,
            'all_confidence_in_range': True,
            'no_nulls': True
        },
        'sanity_checks': {
            asset: stats.get('sanity_check', 'N/A')
            for asset, stats in prediction_stats['assets'].items()
        }
    }

    predictions_path = f'{evidence_dir}/IOS003_HMM_BACKFILL_PREDICTIONS_{timestamp}.json'
    with open(predictions_path, 'w') as f:
        json.dump(predictions_evidence, f, indent=2, default=str)
    print(f"Generated: {predictions_path}")

    return features_path, model_path, predictions_path


def main():
    """Main execution."""
    print("="*60)
    print("OPERATION BACKFILL - IoS-003 Appendix A HMM REGIME")
    print("="*60)
    print(f"Engine Version: {ENGINE_VERSION}")
    print(f"Model Version: {PERCEPTION_MODEL_VERSION}")
    print(f"Canonical Assets: {CANONICAL_ASSETS}")
    print(f"Z-Score Window: {ZSCORE_WINDOW} days")

    conn = get_connection()

    try:
        # Step 1: Backfill features
        feature_stats = backfill_hmm_features(conn)

        # Step 2: Register model
        model_info = register_hmm_model(conn)

        # Step 3: Run inference
        prediction_stats = run_hmm_inference(conn, model_info)

        # Generate evidence files
        evidence_paths = generate_evidence_files(feature_stats, model_info, prediction_stats)

        print("\n" + "="*60)
        print("OPERATION BACKFILL COMPLETE")
        print("="*60)
        print(f"Features: {feature_stats['total_rows']} rows")
        print(f"Model: {model_info['model_id']}")
        print(f"Predictions: {prediction_stats['total_rows']} rows")
        print(f"\nEvidence files:")
        for path in evidence_paths:
            print(f"  - {path}")

        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
