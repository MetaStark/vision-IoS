#!/usr/bin/env python3
"""
IoS-003 v4 Daily Regime Update - Modern HMM Pipeline
=====================================================
Authority: CEO Directive IoS-003 v4 Modernization
Date: 2025-12-11
Executor: STIG (CTO)

Pipeline Flow (per specification):
1. Data ingest - fetch latest prices from fhq_market.prices
2. Indicator calculation - compute technical indicators
3. Feature engineering - generate v4 features with macro covariates
4. Online EM update - continuous parameter adaptation
5. Changepoint analysis - BOCD for regime shift detection
6. IOHMM inference - compute state probabilities
7. Hysteresis filter - k=5 consecutive days for confirmation
8. CRIO modifier - apply sovereign override rules
9. Storage - persist to regime_daily and sovereign_regime_state_v4
10. Notify downstream - signal IoS-004 for allocation update

Key v4 Changes from v2:
- 3-4 states (BULL, NEUTRAL, BEAR, [STRESS]) vs 9 states
- Student-t emissions for fat tails
- IOHMM with macro covariate-driven transitions
- Online EM for continuous parameter updates
- BOCD for changepoint detection
- Asset-class specific models (CRYPTO, FX, EQUITIES)

Schedule: Daily at 00:20 UTC after indicators (task registry)
"""

import os
import sys
import json
import hashlib
import uuid
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from dotenv import load_dotenv

load_dotenv()

# Import v4 modules
from hmm_feature_engineering_v4 import (
    HMMFeatureEngineering,
    classify_asset_class,
    FeatureConfig
)
from hmm_iohmm_online import (
    IOHMM,
    IOHMMConfig,
    load_model_from_db,
    save_model_to_db,
    initialize_model
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("IOS003_V4")

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

ENGINE_VERSION = 'v4.0.0'
PERCEPTION_MODEL_VERSION = '2026.PROD.4'


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_hash(data: str) -> str:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data.encode()).hexdigest()


# =============================================================================
# CRIO MODIFIER (Sovereign Override Rules)
# =============================================================================

def apply_crio_modifier_v4(
    technical_regime: str,
    fragility_score: float,
    dominant_driver: Optional[str],
    state_probs: Dict[str, float]
) -> Tuple[str, bool, str]:
    """
    Apply CRIO Modifier Rules v4 for sovereign regime override.

    CEO Directive Rules (applied in order):
    1. fragility > 0.80 -> Override to STRESS/BEAR
    2. fragility > 0.60 + LIQUIDITY_CONTRACTION -> Cap at NEUTRAL
    3. fragility < 0.40 + LIQUIDITY_EXPANSION -> Allow BULL promotion
    4. VIX spike (dominant_driver='VIX_SPIKE') -> STRESS
    5. Else: Preserve technical

    Returns: (sovereign_regime, modifier_applied, reason)
    """
    # Rule 1: Extreme fragility override
    if fragility_score > 0.80:
        target = 'STRESS' if 'STRESS' in state_probs else 'BEAR'
        return (
            target,
            True,
            f'EXTREME_FRAGILITY: {fragility_score:.2f} > 0.80 -> {target}'
        )

    # Rule 2: VIX spike detection
    if dominant_driver == 'VIX_SPIKE' and fragility_score > 0.50:
        target = 'STRESS' if 'STRESS' in state_probs else 'BEAR'
        return (
            target,
            True,
            f'VIX_SPIKE: fragility {fragility_score:.2f} + VIX_SPIKE -> {target}'
        )

    # Rule 3: Liquidity contraction cap
    if fragility_score > 0.60 and dominant_driver == 'LIQUIDITY_CONTRACTION':
        if technical_regime == 'BULL':
            return (
                'NEUTRAL',
                True,
                f'LIQUIDITY_CONTRACTION_CAP: {fragility_score:.2f} -> max NEUTRAL'
            )

    # Rule 4: Liquidity expansion boost
    if fragility_score < 0.40 and dominant_driver == 'LIQUIDITY_EXPANSION':
        if technical_regime == 'NEUTRAL':
            # Only boost if BULL probability is reasonable
            if state_probs.get('BULL', 0) > 0.3:
                return (
                    'BULL',
                    True,
                    f'LIQUIDITY_EXPANSION_BOOST: {fragility_score:.2f} + good BULL prob -> BULL'
                )

    # Default: Preserve technical regime
    return (technical_regime, False, 'TECHNICAL_PRESERVED: No CRIO modifier triggered')


# =============================================================================
# V4 REGIME MAPPING
# =============================================================================

V2_TO_V4_MAPPING = {
    'STRONG_BULL': 'BULL',
    'BULL': 'BULL',
    'RANGE_UP': 'BULL',
    'NEUTRAL': 'NEUTRAL',
    'RANGE_DOWN': 'BEAR',
    'BEAR': 'BEAR',
    'STRONG_BEAR': 'BEAR',
    'PARABOLIC': 'BULL',  # High vol bull
    'BROKEN': 'STRESS',
    'VOLATILE_NON_DIRECTIONAL': 'STRESS',
    'COMPRESSION': 'NEUTRAL',
    'UNTRUSTED': 'NEUTRAL'
}


def map_v2_to_v4(v2_regime: str) -> str:
    """Map v2 regime labels to v4 canonical states."""
    return V2_TO_V4_MAPPING.get(v2_regime, 'NEUTRAL')


# =============================================================================
# MAIN PIPELINE CLASS
# =============================================================================

class DailyRegimeUpdaterV4:
    """
    IoS-003 v4 Daily Regime Update Pipeline.

    Implements modernized HMM regime detection with:
    - IOHMM covariate-driven transitions
    - Student-t emissions
    - Online EM parameter updates
    - BOCD changepoint detection
    - Hysteresis filtering
    - CRIO sovereign modifiers
    """

    def __init__(self, dry_run: bool = False):
        self.conn = get_connection()
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.dry_run = dry_run
        self.feature_engine = HMMFeatureEngineering()

        # Results tracking
        self.results = {
            'pipeline': 'ios003_v4_regime_update',
            'version': ENGINE_VERSION,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executor': 'STIG',
            'dry_run': dry_run,
            'assets': {},
            'models': {}
        }

        # IOHMM models per asset class
        self.models: Dict[str, IOHMM] = {}

    def get_canonical_assets(self) -> List[Dict]:
        """Get all canonical assets from assets table."""
        self.cur.execute("""
            SELECT
                canonical_id,
                symbol,
                asset_type,
                exchange_mic,
                active_flag
            FROM fhq_meta.assets
            WHERE active_flag = TRUE
            ORDER BY asset_type, canonical_id
        """)
        return list(self.cur.fetchall())

    def get_v4_config(self, asset_class: str) -> Optional[Dict]:
        """Load v4 configuration for asset class."""
        self.cur.execute("""
            SELECT *
            FROM fhq_perception.hmm_v4_config
            WHERE asset_class = %s AND is_active = TRUE
        """, (asset_class,))
        row = self.cur.fetchone()
        return dict(row) if row else None

    def get_lids_verified_crio(self) -> Optional[Dict]:
        """Fetch latest LIDS-verified CRIO insight."""
        self.cur.execute("""
            SELECT
                insight_id::text,
                research_date,
                fragility_score,
                dominant_driver,
                quad_hash,
                lids_verified,
                confidence,
                regime_assessment
            FROM fhq_research.nightly_insights
            WHERE lids_verified = TRUE
            ORDER BY research_date DESC
            LIMIT 1
        """)
        row = self.cur.fetchone()
        if row:
            return {
                'insight_id': row['insight_id'],
                'research_date': row['research_date'],
                'fragility_score': float(row['fragility_score']) if row['fragility_score'] else 0.5,
                'dominant_driver': row['dominant_driver'] or 'NEUTRAL',
                'quad_hash': row['quad_hash'],
                'confidence': float(row['confidence']) if row['confidence'] else 0.5
            }
        return None

    def get_missing_dates(self, asset_id: str) -> List:
        """Get dates in prices table not yet in regime_daily for v4."""
        self.cur.execute("""
            SELECT DISTINCT p.timestamp::date as date
            FROM fhq_market.prices p
            WHERE p.canonical_id = %s
            AND p.timestamp::date > (
                SELECT COALESCE(MAX(timestamp), '2020-01-01'::date)
                FROM fhq_perception.regime_daily
                WHERE asset_id = %s AND hmm_version = 'v4.0'
            )
            ORDER BY date
        """, (asset_id, asset_id))
        return [row['date'] for row in self.cur.fetchall()]

    def get_prior_v4_state(self, asset_id: str) -> Tuple[str, int]:
        """Get prior v4 regime and consecutive confirms."""
        self.cur.execute("""
            SELECT technical_regime, consecutive_confirms
            FROM fhq_perception.regime_daily
            WHERE asset_id = %s AND hmm_version = 'v4.0'
            ORDER BY timestamp DESC
            LIMIT 1
        """, (asset_id,))
        row = self.cur.fetchone()
        if row:
            return (row['technical_regime'] or 'NEUTRAL', row['consecutive_confirms'] or 0)

        # Fallback: check v2 regime and map
        self.cur.execute("""
            SELECT regime_classification, consecutive_confirms
            FROM fhq_perception.regime_daily
            WHERE asset_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """, (asset_id,))
        row = self.cur.fetchone()
        if row:
            v2_regime = row['regime_classification']
            v4_regime = map_v2_to_v4(v2_regime)
            return (v4_regime, row['consecutive_confirms'] or 0)

        return ('NEUTRAL', 0)

    def load_or_initialize_model(self, asset_class: str) -> IOHMM:
        """Load existing model or initialize new one."""
        if asset_class in self.models:
            return self.models[asset_class]

        # Try loading from database
        model = load_model_from_db(self.conn, asset_class)

        if model is None:
            logger.info(f"Initializing new IOHMM model for {asset_class}")
            # Get config
            config = self.get_v4_config(asset_class)
            if config:
                iohmm_config = IOHMMConfig(
                    n_states=config['n_states'],
                    n_features=len(json.loads(config['technical_features'])),
                    n_covariates=len(json.loads(config['macro_covariates'])),
                    state_labels=json.loads(config['state_labels']),
                    learning_rate=float(config['learning_rate']),
                    hazard_rate=float(config['hazard_rate']),
                    changepoint_threshold=float(config['changepoint_threshold']),
                    hysteresis_days=config['hysteresis_days']
                )
            else:
                # Default config
                iohmm_config = IOHMMConfig(
                    n_states=3,
                    state_labels=['BULL', 'NEUTRAL', 'BEAR']
                )

            model = initialize_model(iohmm_config, asset_class)

        self.models[asset_class] = model
        return model

    def process_asset(
        self,
        asset_id: str,
        asset_class: str,
        crio_insight: Optional[Dict]
    ) -> Dict:
        """Process single asset through v4 pipeline."""
        result = {
            'asset_id': asset_id,
            'asset_class': asset_class,
            'status': 'PENDING',
            'updates': 0,
            'changepoints': 0,
            'modifiers_applied': 0
        }

        # Step 1: Get missing dates
        missing_dates = self.get_missing_dates(asset_id)
        if not missing_dates:
            result['status'] = 'CURRENT'
            return result

        result['missing_dates'] = len(missing_dates)

        # Step 2: Generate features
        features_df = self.feature_engine.compute_features_for_asset(
            self.conn, asset_id, asset_class
        )

        if features_df is None or len(features_df) < 50:
            result['status'] = 'INSUFFICIENT_DATA'
            result['rows'] = len(features_df) if features_df is not None else 0
            return result

        # Step 3: Load/initialize IOHMM model
        model = self.load_or_initialize_model(asset_class)

        # Step 4: Get prior state
        prior_regime, consecutive_confirms = self.get_prior_v4_state(asset_id)

        # Extract CRIO values
        crio_fragility = crio_insight['fragility_score'] if crio_insight else 0.5
        crio_driver = crio_insight['dominant_driver'] if crio_insight else 'NEUTRAL'
        crio_quad_hash = crio_insight['quad_hash'] if crio_insight else None
        crio_insight_id = crio_insight['insight_id'] if crio_insight else None

        # Get config for hysteresis
        config = self.get_v4_config(asset_class)
        hysteresis_days = config['hysteresis_days'] if config else 5

        # Step 5: Process each missing date
        updates = 0
        changepoints = 0
        modifiers = 0

        for date in missing_dates:
            if date not in features_df.index:
                continue

            row = features_df.loc[date]

            # Build feature and covariate vectors
            feature_cols = ['return_z', 'volatility_z', 'drawdown_z', 'macd_diff_z',
                           'bb_width_z', 'rsi_14_z', 'roc_20_z']
            covariate_cols = ['yield_spread_z', 'vix_z', 'liquidity_z']

            # Get available features (handle missing)
            feature_vec = []
            for col in feature_cols:
                if col in row and not pd.isna(row[col]):
                    feature_vec.append(float(row[col]))
                else:
                    feature_vec.append(0.0)

            covariate_vec = []
            for col in covariate_cols:
                if col in row and not pd.isna(row[col]):
                    covariate_vec.append(float(row[col]))
                else:
                    covariate_vec.append(0.0)

            feature_arr = np.array(feature_vec)
            covariate_arr = np.array(covariate_vec)

            # Step 6: IOHMM inference with Online EM and BOCD
            inference_result = model.process_observation(feature_arr, covariate_arr)

            technical_regime = inference_result['technical_regime']
            # Convert state_posteriors list to dict with labels
            posteriors = inference_result['state_posteriors']
            state_labels = model.config.state_labels
            state_probs = {
                state_labels[i]: float(posteriors[i])
                for i in range(len(state_labels))
            }
            is_changepoint = inference_result['is_changepoint']
            changepoint_prob = inference_result['changepoint_probability']
            run_length = inference_result['run_length']

            if is_changepoint:
                changepoints += 1

            # Step 7: Hysteresis filter
            if technical_regime == prior_regime:
                consecutive_confirms += 1
            else:
                consecutive_confirms = 1

            if consecutive_confirms >= hysteresis_days:
                hysteresis_regime = technical_regime
                stability_flag = True
            else:
                hysteresis_regime = prior_regime
                stability_flag = False

            # Step 8: Apply CRIO modifier
            sovereign_regime, modifier_applied, modifier_reason = apply_crio_modifier_v4(
                hysteresis_regime,
                crio_fragility,
                crio_driver,
                state_probs
            )

            if modifier_applied:
                modifiers += 1

            # Compute confidence
            max_prob = max(state_probs.values())
            confidence = min(max_prob + (consecutive_confirms * 0.05), 0.98)

            # Compute hashes
            data_str = f"{asset_id}|{date}|{sovereign_regime}|{technical_regime}|{confidence}|{crio_quad_hash}"
            hash_self = compute_hash(data_str)
            formula_hash = compute_hash(f"IOHMM_v4|{asset_class}|student_t|online_em|bocd")

            # Step 9: Store results
            if not self.dry_run:
                # Insert/update regime_daily
                self.cur.execute("""
                    INSERT INTO fhq_perception.regime_daily (
                        id, asset_id, timestamp,
                        regime_classification, technical_regime,
                        regime_stability_flag, regime_confidence,
                        consecutive_confirms, prior_regime,
                        changepoint_probability, run_length,
                        hmm_version, engine_version, perception_model_version,
                        formula_hash, lineage_hash, hash_self,
                        crio_fragility_score, crio_dominant_driver,
                        quad_hash, regime_modifier_applied, crio_insight_id,
                        anomaly_flag
                    )
                    VALUES (
                        gen_random_uuid(), %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        'v4.0', %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s
                    )
                    ON CONFLICT (asset_id, timestamp) DO UPDATE SET
                        regime_classification = EXCLUDED.regime_classification,
                        technical_regime = EXCLUDED.technical_regime,
                        regime_stability_flag = EXCLUDED.regime_stability_flag,
                        regime_confidence = EXCLUDED.regime_confidence,
                        consecutive_confirms = EXCLUDED.consecutive_confirms,
                        changepoint_probability = EXCLUDED.changepoint_probability,
                        run_length = EXCLUDED.run_length,
                        hmm_version = 'v4.0',
                        crio_fragility_score = EXCLUDED.crio_fragility_score,
                        crio_dominant_driver = EXCLUDED.crio_dominant_driver,
                        regime_modifier_applied = EXCLUDED.regime_modifier_applied
                """, (
                    asset_id, date,
                    sovereign_regime, technical_regime,
                    stability_flag, confidence,
                    consecutive_confirms, prior_regime,
                    changepoint_prob, run_length,
                    ENGINE_VERSION, PERCEPTION_MODEL_VERSION,
                    formula_hash, hash_self, hash_self,
                    crio_fragility, crio_driver,
                    crio_quad_hash, modifier_applied, crio_insight_id,
                    is_changepoint
                ))

                # Insert sovereign_regime_state_v4
                self.cur.execute("""
                    INSERT INTO fhq_perception.sovereign_regime_state_v4 (
                        id, asset_id, timestamp,
                        technical_regime, sovereign_regime,
                        state_probabilities,
                        crio_dominant_driver, crio_override_reason,
                        engine_version
                    )
                    VALUES (
                        gen_random_uuid(), %s, %s,
                        %s, %s,
                        %s,
                        %s, %s,
                        %s
                    )
                    ON CONFLICT (asset_id, timestamp) DO UPDATE SET
                        technical_regime = EXCLUDED.technical_regime,
                        sovereign_regime = EXCLUDED.sovereign_regime,
                        state_probabilities = EXCLUDED.state_probabilities,
                        crio_dominant_driver = EXCLUDED.crio_dominant_driver,
                        crio_override_reason = EXCLUDED.crio_override_reason
                """, (
                    asset_id, date,
                    technical_regime, sovereign_regime,
                    json.dumps(state_probs),
                    crio_driver, modifier_reason if modifier_applied else None,
                    ENGINE_VERSION
                ))

                # Log changepoint if detected
                if is_changepoint:
                    self.cur.execute("""
                        INSERT INTO fhq_perception.bocd_changepoint_log (
                            id, asset_id, asset_class, timestamp,
                            changepoint_probability, run_length,
                            is_changepoint, changepoint_threshold,
                            regime_before, regime_after
                        )
                        VALUES (
                            gen_random_uuid(), %s, %s, %s,
                            %s, %s,
                            TRUE, 0.5,
                            %s, %s
                        )
                        ON CONFLICT (asset_id, timestamp) DO NOTHING
                    """, (
                        asset_id, asset_class, date,
                        changepoint_prob, run_length,
                        prior_regime, technical_regime
                    ))

            prior_regime = sovereign_regime
            updates += 1

        if not self.dry_run:
            self.conn.commit()

        result['status'] = 'UPDATED'
        result['updates'] = updates
        result['changepoints'] = changepoints
        result['modifiers_applied'] = modifiers

        return result

    def save_models(self):
        """Save all models to database."""
        if self.dry_run:
            return

        for asset_class, model in self.models.items():
            logger.info(f"Saving model for {asset_class}")
            save_model_to_db(self.conn, model, asset_class)

    def run(self) -> Dict:
        """Run full v4 pipeline."""
        logger.info("=" * 60)
        logger.info("IoS-003 v4 MODERN HMM REGIME UPDATE")
        logger.info("=" * 60)

        # Step 1: Get CRIO insight
        crio_insight = self.get_lids_verified_crio()
        if crio_insight:
            logger.info(f"CRIO Insight: {crio_insight['insight_id'][:8]}...")
            logger.info(f"  Fragility: {crio_insight['fragility_score']:.2f}")
            logger.info(f"  Driver: {crio_insight['dominant_driver']}")
            self.results['crio_insight'] = crio_insight
        else:
            logger.warning("No LIDS-verified CRIO insight - using defaults")
            self.results['crio_insight'] = None

        # Step 2: Get canonical assets
        assets = self.get_canonical_assets()
        logger.info(f"Processing {len(assets)} canonical assets")

        # Step 3: Process each asset
        total_updates = 0
        total_changepoints = 0
        total_modifiers = 0

        for asset in assets:
            asset_id = asset['canonical_id']
            asset_class = classify_asset_class(asset_id)

            logger.info(f"  {asset_id} ({asset_class})...", )

            try:
                result = self.process_asset(asset_id, asset_class, crio_insight)
                self.results['assets'][asset_id] = result

                if result['status'] == 'UPDATED':
                    logger.info(f"    UPDATED: {result['updates']} records, "
                               f"{result['changepoints']} changepoints, "
                               f"{result['modifiers_applied']} modifiers")
                    total_updates += result['updates']
                    total_changepoints += result['changepoints']
                    total_modifiers += result['modifiers_applied']
                elif result['status'] == 'CURRENT':
                    logger.info(f"    CURRENT")
                else:
                    logger.info(f"    {result['status']}")

            except Exception as e:
                logger.error(f"    ERROR: {e}")
                self.results['assets'][asset_id] = {
                    'status': 'ERROR',
                    'error': str(e)
                }

        # Step 4: Save updated models
        self.save_models()

        # Step 5: Log audit event
        self.results['total_updates'] = total_updates
        self.results['total_changepoints'] = total_changepoints
        self.results['total_modifiers'] = total_modifiers
        self.results['status'] = 'COMPLETE'

        if not self.dry_run:
            evidence_hash = compute_hash(json.dumps(self.results, sort_keys=True, default=str))
            self.results['evidence_hash'] = evidence_hash

            self.cur.execute("""
                INSERT INTO fhq_meta.ios_audit_log (
                    audit_id, ios_id, event_type, event_timestamp,
                    actor, gate_level, event_data, evidence_hash
                )
                VALUES (
                    gen_random_uuid(), 'IoS-003', 'REGIME_UPDATE_V4', %s,
                    'STIG', 'G1', %s, %s
                )
            """, (
                datetime.now(timezone.utc),
                json.dumps(self.results, default=str),
                evidence_hash
            ))
            self.conn.commit()

        # Summary
        logger.info("=" * 60)
        logger.info(f"Total Updates: {total_updates}")
        logger.info(f"Total Changepoints: {total_changepoints}")
        logger.info(f"Total CRIO Modifiers: {total_modifiers}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("=" * 60)

        return self.results

    def close(self):
        """Close database connections."""
        self.cur.close()
        self.conn.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='IoS-003 v4 Daily Regime Update - Modern HMM Pipeline'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without writing to database'
    )
    parser.add_argument(
        '--asset',
        type=str,
        help='Process single asset (for testing)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    updater = DailyRegimeUpdaterV4(dry_run=args.dry_run)

    try:
        if args.asset:
            # Single asset mode
            asset_class = classify_asset_class(args.asset)
            crio = updater.get_lids_verified_crio()
            result = updater.process_asset(args.asset, asset_class, crio)
            print(json.dumps(result, indent=2, default=str))
            return result['status'] in ('UPDATED', 'CURRENT')
        else:
            # Full pipeline
            results = updater.run()
            return results['status'] == 'COMPLETE'
    finally:
        updater.close()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
