#!/usr/bin/env python3
"""
IoS-003 SOVEREIGN PERCEPTION ENGINE
====================================
Authority: CEO Directive - SOVEREIGN PERCEPTION UPGRADE
Classification: Automated G1 Path
Reference: ADR-017 (MIT Quad Protocol), ADR-013 (Truth Architecture)

Pipeline Flow:
1. Detect new dates in fhq_market.prices vs regime_daily
2. Fetch LIDS-verified CRIO insight (fragility_score, dominant_driver)
3. Compute HMM features for new dates
4. Run regime inference with hysteresis
5. Apply CRIO Modifier Rules (Sovereign Regime Algorithm)
6. Update regime_predictions_v2 and regime_daily with quad_hash lineage
7. Log audit event

Sovereign Regime Algorithm (CRIO Modifier Rules):
- fragility > 0.80 -> Override all states to STRONG_BEAR
- fragility > 0.60 + LIQUIDITY_CONTRACTION -> Cap at NEUTRAL
- fragility < 0.40 + LIQUIDITY_EXPANSION -> Allow STRONG_BULL
- Else: Preserve technical classification

Schedule: Daily after price ingest, before IoS-004 allocation
Guarantees: Sovereign perception freshness before allocation run
"""

import os
import json
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

# HMM Configuration (IoS-003 Appendix A)
ENGINE_VERSION = 'HMM_v2.0'
PERCEPTION_MODEL_VERSION = '2026.PROD.1'
ZSCORE_WINDOW = 252
VOLATILITY_WINDOW = 20
NUM_STATES = 9
HYSTERESIS_DAYS = 5

REGIME_LABELS = {
    0: 'STRONG_BULL', 1: 'BULL', 2: 'RANGE_UP', 3: 'NEUTRAL',
    4: 'RANGE_DOWN', 5: 'BEAR', 6: 'STRONG_BEAR', 7: 'PARABOLIC', 8: 'BROKEN'
}

# Canonical assets per IoS-001
CANONICAL_ASSETS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'EURUSD']

# NOTE: ASSET_TO_LISTING mapping removed per CEO Directive - Canonical Consolidation
# fhq_market.prices uses canonical_id directly (e.g., 'BTC-USD')


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_hash(data: str) -> str:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data.encode()).hexdigest()


def compute_zscore(series: pd.Series, window: int = 252) -> pd.Series:
    """Compute rolling z-score."""
    mean = series.rolling(window=window, min_periods=50).mean()
    std = series.rolling(window=window, min_periods=50).std()
    return (series - mean) / std.replace(0, np.nan)


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute HMM features from OHLCV data."""
    df = df.copy()
    df['returns'] = np.log(df['close'] / df['close'].shift(1))
    df['volatility'] = df['returns'].rolling(window=VOLATILITY_WINDOW).std()
    df['rolling_max'] = df['close'].rolling(window=ZSCORE_WINDOW, min_periods=20).max()
    df['drawdown'] = (df['close'] - df['rolling_max']) / df['rolling_max']
    df['roc_20'] = (df['close'] - df['close'].shift(20)) / df['close'].shift(20)

    # Z-scores
    df['return_z'] = compute_zscore(df['returns'])
    df['volatility_z'] = compute_zscore(df['volatility'])
    df['drawdown_z'] = compute_zscore(df['drawdown'])
    df['roc_20_z'] = compute_zscore(df['roc_20'])

    return df


def classify_regime(return_z: float, vol_z: float, dd_z: float) -> str:
    """Classify regime based on z-score features (Technical Classification)."""
    if pd.isna(return_z) or pd.isna(vol_z):
        return 'NEUTRAL'

    if return_z > 1.5 and vol_z > 1.5:
        return 'PARABOLIC'
    elif return_z > 1.0:
        return 'STRONG_BULL'
    elif return_z > 0.3:
        return 'BULL'
    elif return_z > -0.3:
        if vol_z > 0.5:
            return 'RANGE_UP' if return_z > 0 else 'RANGE_DOWN'
        return 'NEUTRAL'
    elif return_z > -1.0:
        return 'BEAR'
    elif dd_z < -2.0 if not pd.isna(dd_z) else False:
        return 'BROKEN'
    else:
        return 'STRONG_BEAR'


def apply_crio_modifier(
    technical_regime: str,
    fragility_score: float,
    dominant_driver: str
) -> Tuple[str, bool, str]:
    """
    Apply CRIO Modifier Rules to convert Technical -> Sovereign Regime.

    CEO Directive Rules (applied in order):
    1. fragility > 0.80 -> Override to STRONG_BEAR
    2. fragility > 0.60 + LIQUIDITY_CONTRACTION -> Cap at NEUTRAL
    3. fragility < 0.40 + LIQUIDITY_EXPANSION -> Allow STRONG_BULL
    4. Else: Preserve technical

    Returns: (sovereign_regime, modifier_applied, reason)
    """
    # Rule 1: High fragility override
    if fragility_score > 0.80:
        return (
            'STRONG_BEAR',
            True,
            f'HIGH_FRAGILITY_OVERRIDE: fragility {fragility_score:.2f} > 0.80'
        )

    # Rule 2: Liquidity contraction cap
    if fragility_score > 0.60 and dominant_driver == 'LIQUIDITY_CONTRACTION':
        bullish_regimes = ['STRONG_BULL', 'BULL', 'RANGE_UP', 'PARABOLIC']
        if technical_regime in bullish_regimes:
            return (
                'NEUTRAL',
                True,
                f'LIQUIDITY_CONTRACTION_CAP: fragility {fragility_score:.2f} + {dominant_driver} -> max NEUTRAL'
            )

    # Rule 3: Liquidity expansion boost
    if fragility_score < 0.40 and dominant_driver == 'LIQUIDITY_EXPANSION':
        boostable_regimes = ['BULL', 'RANGE_UP']
        if technical_regime in boostable_regimes:
            return (
                'STRONG_BULL',
                True,
                f'LIQUIDITY_EXPANSION_BOOST: fragility {fragility_score:.2f} + {dominant_driver} -> STRONG_BULL'
            )

    # Default: Preserve technical
    return (technical_regime, False, 'TECHNICAL_PRESERVED: No CRIO modifier triggered')


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class DailyRegimeUpdater:
    """Sovereign Perception Engine - Daily regime update pipeline."""

    def __init__(self):
        self.conn = get_connection()
        self.cur = self.conn.cursor()
        self.crio_insight = None  # LIDS-verified CRIO insight
        self.results = {
            'pipeline': 'ios003_sovereign_perception',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executor': 'STIG',
            'crio_insight': None,
            'assets': {}
        }

    def get_lids_verified_crio(self) -> Optional[Dict[str, Any]]:
        """Fetch latest LIDS-verified CRIO insight from nightly_insights."""
        self.cur.execute("""
            SELECT insight_id, research_date, fragility_score, dominant_driver,
                   quad_hash, lids_verified, confidence, regime_assessment
            FROM fhq_research.nightly_insights
            WHERE lids_verified = TRUE
            ORDER BY research_date DESC
            LIMIT 1
        """)
        row = self.cur.fetchone()
        if row:
            return {
                'insight_id': str(row[0]),
                'research_date': row[1],
                'fragility_score': float(row[2]) if row[2] else 0.5,
                'dominant_driver': row[3] or 'NEUTRAL',
                'quad_hash': row[4],
                'lids_verified': row[5],
                'confidence': float(row[6]) if row[6] else 0.5,
                'regime_assessment': row[7]
            }
        return None

    def get_model_id(self) -> Optional[uuid.UUID]:
        """Get active HMM model ID."""
        self.cur.execute("""
            SELECT model_id FROM fhq_research.regime_model_registry
            WHERE engine_version = %s AND is_active = true
            ORDER BY created_at DESC LIMIT 1
        """, (ENGINE_VERSION,))
        row = self.cur.fetchone()
        return row[0] if row else None

    def get_missing_dates(self, asset_id: str) -> List:
        """Detect dates in fhq_market.prices not in regime_daily (ADR-013 Canonical)."""
        self.cur.execute("""
            SELECT DISTINCT p.timestamp::date
            FROM fhq_market.prices p
            WHERE p.canonical_id = %s
            AND p.timestamp::date > (
                SELECT COALESCE(MAX(timestamp), '2016-01-01'::date)
                FROM fhq_perception.regime_daily
                WHERE asset_id = %s
            )
            ORDER BY p.timestamp::date
        """, (asset_id, asset_id))
        return [row[0] for row in self.cur.fetchall()]

    def get_price_data(self, canonical_id: str) -> pd.DataFrame:
        """Fetch price data for feature computation (ADR-013 Canonical)."""
        self.cur.execute("""
            SELECT timestamp::date as date, open, high, low, close, volume
            FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY timestamp
        """, (canonical_id,))
        rows = self.cur.fetchall()
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df = df.set_index('date')

        # Convert Decimal to float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df

    def get_prior_regime(self, asset_id: str) -> Tuple[str, int]:
        """Get prior regime and consecutive confirms."""
        self.cur.execute("""
            SELECT regime_classification, consecutive_confirms
            FROM fhq_perception.regime_daily
            WHERE asset_id = %s
            ORDER BY timestamp DESC LIMIT 1
        """, (asset_id,))
        row = self.cur.fetchone()
        return (row[0], row[1]) if row else ('NEUTRAL', 0)

    def update_asset(self, asset_id: str, model_id: uuid.UUID, crio_insight: Optional[Dict] = None) -> Dict:
        """Update regime for single asset with Sovereign Perception (ADR-013 Canonical)."""
        # Get missing dates - uses canonical_id directly (no mapping needed)
        missing_dates = self.get_missing_dates(asset_id)
        if not missing_dates:
            return {'status': 'CURRENT', 'new_dates': 0}

        # Get price data from fhq_market.prices (ADR-013 One-True-Source)
        df = self.get_price_data(asset_id)
        if len(df) < 300:
            return {'status': 'INSUFFICIENT_DATA', 'rows': len(df)}

        # Compute features
        df = compute_features(df)

        # Get prior state
        prior_regime, consecutive_confirms = self.get_prior_regime(asset_id)

        # Formula hash - now includes CRIO modifier
        formula_spec = "return_z|volatility_z|drawdown_z|roc_20_z->technical->crio_modifier->sovereign_regime"
        formula_hash = compute_hash(formula_spec)

        # Extract CRIO values (with defaults)
        crio_fragility = crio_insight['fragility_score'] if crio_insight else 0.5
        crio_driver = crio_insight['dominant_driver'] if crio_insight else 'NEUTRAL'
        crio_quad_hash = crio_insight['quad_hash'] if crio_insight else None
        crio_insight_id = crio_insight['insight_id'] if crio_insight else None

        updates = 0
        modifiers_applied = 0

        # Verify return_z column exists after feature computation
        if 'return_z' not in df.columns:
            return {'status': 'FEATURE_ERROR', 'error': 'return_z column missing after compute_features'}

        for date in missing_dates:
            if date not in df.index:
                continue

            row = df.loc[date]

            # Handle duplicate dates (row would be DataFrame instead of Series)
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]

            # Safe access to return_z with proper NaN check
            return_z_val = row.get('return_z') if hasattr(row, 'get') else row['return_z']
            if return_z_val is None or pd.isna(return_z_val):
                continue

            # Step 1: Technical Classification (HMM-based)
            # Extract features - skip date if required features are missing (ADR-013 Canonical Truth)
            vol_z_val = row['volatility_z']
            dd_z_val = row['drawdown_z']
            if pd.isna(vol_z_val):
                continue  # Skip - no regime from partial data
            technical_regime = classify_regime(
                return_z_val,
                vol_z_val,
                dd_z_val if not pd.isna(dd_z_val) else 0  # drawdown_z optional (early rows)
            )

            # Step 2: Apply hysteresis to technical regime
            if technical_regime == prior_regime:
                consecutive_confirms += 1
            else:
                consecutive_confirms = 1

            if consecutive_confirms >= HYSTERESIS_DAYS:
                hysteresis_regime = technical_regime
                stability_flag = True
            else:
                hysteresis_regime = prior_regime
                stability_flag = False

            # Step 3: Apply CRIO Modifier Rules (Sovereign Regime Algorithm)
            sovereign_regime, modifier_applied, modifier_reason = apply_crio_modifier(
                hysteresis_regime, crio_fragility, crio_driver
            )

            if modifier_applied:
                modifiers_applied += 1

            # Final regime is the sovereign regime
            final_regime = sovereign_regime
            confidence = min(0.5 + (consecutive_confirms * 0.1), 0.95)

            # Compute hashes with CRIO lineage
            data_str = f"{asset_id}|{date}|{final_regime}|{confidence}|{crio_quad_hash}"
            hash_self = compute_hash(data_str)

            # Insert regime_predictions_v2
            pred_id = str(uuid.uuid4())
            self.cur.execute("""
                INSERT INTO fhq_research.regime_predictions_v2
                (prediction_id, asset_id, timestamp, model_id, perception_model_version,
                 regime_raw, regime_label, confidence_score, lineage_hash, hash_self)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (asset_id, timestamp) DO UPDATE SET
                    regime_label = EXCLUDED.regime_label,
                    confidence_score = EXCLUDED.confidence_score
            """, (pred_id, asset_id, date, str(model_id), PERCEPTION_MODEL_VERSION,
                  list(REGIME_LABELS.values()).index(final_regime) if final_regime in REGIME_LABELS.values() else 3,
                  final_regime, confidence, hash_self, hash_self))

            # Insert regime_daily with CRIO audit fields
            self.cur.execute("""
                INSERT INTO fhq_perception.regime_daily
                (id, asset_id, timestamp, regime_classification, regime_stability_flag,
                 regime_confidence, consecutive_confirms, prior_regime, anomaly_flag,
                 engine_version, perception_model_version, formula_hash, lineage_hash, hash_self,
                 crio_fragility_score, crio_dominant_driver, quad_hash, regime_modifier_applied, crio_insight_id)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (asset_id, timestamp) DO UPDATE SET
                    regime_classification = EXCLUDED.regime_classification,
                    regime_stability_flag = EXCLUDED.regime_stability_flag,
                    regime_confidence = EXCLUDED.regime_confidence,
                    consecutive_confirms = EXCLUDED.consecutive_confirms,
                    crio_fragility_score = EXCLUDED.crio_fragility_score,
                    crio_dominant_driver = EXCLUDED.crio_dominant_driver,
                    quad_hash = EXCLUDED.quad_hash,
                    regime_modifier_applied = EXCLUDED.regime_modifier_applied,
                    crio_insight_id = EXCLUDED.crio_insight_id
            """, (asset_id, date, final_regime, stability_flag, confidence,
                  consecutive_confirms, prior_regime, False, ENGINE_VERSION,
                  PERCEPTION_MODEL_VERSION, formula_hash, hash_self, hash_self,
                  crio_fragility, crio_driver, crio_quad_hash, modifier_applied, crio_insight_id))

            prior_regime = final_regime
            updates += 1

        self.conn.commit()
        return {
            'status': 'UPDATED',
            'new_dates': len(missing_dates),
            'updates': updates,
            'modifiers_applied': modifiers_applied,
            'crio_fragility': crio_fragility,
            'crio_driver': crio_driver
        }

    def run(self) -> Dict:
        """Run full Sovereign Perception pipeline."""
        print("=" * 60)
        print("IoS-003 SOVEREIGN PERCEPTION ENGINE")
        print("=" * 60)

        # Step 1: Fetch LIDS-verified CRIO insight
        self.crio_insight = self.get_lids_verified_crio()
        if self.crio_insight:
            print(f"CRIO Insight: {self.crio_insight['insight_id'][:8]}...")
            print(f"  Fragility: {self.crio_insight['fragility_score']:.2f}")
            print(f"  Driver: {self.crio_insight['dominant_driver']}")
            print(f"  Quad Hash: {self.crio_insight['quad_hash']}")
            self.results['crio_insight'] = {
                'insight_id': self.crio_insight['insight_id'],
                'fragility_score': self.crio_insight['fragility_score'],
                'dominant_driver': self.crio_insight['dominant_driver'],
                'quad_hash': self.crio_insight['quad_hash']
            }
        else:
            print("[WARNING] No LIDS-verified CRIO insight - using defaults")
            self.results['crio_insight'] = None

        # Step 2: Get HMM model
        model_id = self.get_model_id()
        if not model_id:
            self.results['status'] = 'ERROR'
            self.results['error'] = 'No active HMM model'
            print("[ERROR] No active HMM model found")
            return self.results

        print(f"HMM Model: {str(model_id)[:8]}...")

        # Step 3: Update each asset with Sovereign Perception
        total_updates = 0
        total_modifiers = 0
        for asset_id in CANONICAL_ASSETS:
            print(f"\n  {asset_id}...", end=" ")
            result = self.update_asset(asset_id, model_id, self.crio_insight)
            self.results['assets'][asset_id] = result

            if result['status'] == 'UPDATED':
                mods = result.get('modifiers_applied', 0)
                print(f"UPDATED ({result['updates']} records, {mods} modifiers)")
                total_updates += result['updates']
                total_modifiers += mods
            elif result['status'] == 'CURRENT':
                print("CURRENT")
            else:
                print(f"{result['status']}")

        self.results['total_updates'] = total_updates
        self.results['total_modifiers'] = total_modifiers
        self.results['status'] = 'COMPLETE'

        # Log audit event
        evidence_hash = compute_hash(json.dumps(self.results, sort_keys=True, default=str))
        self.results['evidence_hash'] = evidence_hash

        self.cur.execute("""
            INSERT INTO fhq_meta.ios_audit_log
            (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
        """, ('IoS-003', 'SOVEREIGN_PERCEPTION_UPDATE', datetime.now(timezone.utc), 'STIG', 'G1',
              json.dumps(self.results, default=str), evidence_hash))
        self.conn.commit()

        print(f"\n{'=' * 60}")
        print(f"Total Updates: {total_updates}")
        print(f"CRIO Modifiers Applied: {total_modifiers}")
        if self.crio_insight:
            print(f"Quad Hash: {self.crio_insight['quad_hash']}")
        print(f"Evidence Hash: {evidence_hash[:32]}...")
        print("=" * 60)

        return self.results

    def close(self):
        """Close connections."""
        self.cur.close()
        self.conn.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run daily regime update."""
    updater = DailyRegimeUpdater()
    try:
        results = updater.run()
        return results['status'] == 'COMPLETE'
    finally:
        updater.close()


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
