#!/usr/bin/env python3
"""
IoS-003 v4 HMM Regime Backfill Script
=====================================
Authority: CEO Directive - Rate-Limit Protection
Date: 2025-12-11
Executor: STIG (CTO)

Rate-Limit Protection Strategy:
- Batch size: 20 assets per batch
- Pause between batches: 60 seconds
- Asset-class priority: CRYPTO -> FX -> EQUITY
- Progress persistence: checkpoint after each batch
- Estimated runtime: ~30 minutes for 352 assets

Usage:
    python ios003_v4_backfill.py --batch-size 20 --delay 60
    python ios003_v4_backfill.py --resume  # Resume from last checkpoint
    python ios003_v4_backfill.py --dry-run --limit 5  # Test mode
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Import v4 modules
from hmm_feature_engineering_v4 import HMMFeatureEngineering, classify_asset_class
from hmm_iohmm_online import (
    IOHMM, IOHMMConfig, load_model_from_db, save_model_to_db, initialize_model
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ios003_v4_backfill.log')
    ]
)
logger = logging.getLogger("IOS003_V4_BACKFILL")

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

CHECKPOINT_FILE = 'ios003_v4_backfill_checkpoint.json'

# Rate-limit settings per CEO Directive
DEFAULT_BATCH_SIZE = 20
DEFAULT_DELAY_SECONDS = 60  # 1 minute between batches
ASSET_CLASS_PRIORITY = ['CRYPTO', 'FX', 'EQUITY']  # Process order


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# =============================================================================
# CHECKPOINT MANAGEMENT
# =============================================================================

def save_checkpoint(checkpoint: Dict):
    """Save progress checkpoint"""
    checkpoint['saved_at'] = datetime.now(timezone.utc).isoformat()
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint, f, indent=2, default=str)
    logger.info(f"Checkpoint saved: {checkpoint['processed']}/{checkpoint['total']} assets")


def load_checkpoint() -> Optional[Dict]:
    """Load checkpoint if exists"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            checkpoint = json.load(f)
        logger.info(f"Loaded checkpoint: {checkpoint['processed']}/{checkpoint['total']} assets")
        return checkpoint
    return None


def clear_checkpoint():
    """Remove checkpoint file"""
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        logger.info("Checkpoint cleared")


# =============================================================================
# BACKFILL LOGIC
# =============================================================================

class V4RegimeBackfill:
    """Batched regime backfill with rate-limit protection"""

    def __init__(self, batch_size: int = 20, delay_seconds: int = 60, dry_run: bool = False):
        self.conn = get_connection()
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.batch_size = batch_size
        self.delay_seconds = delay_seconds
        self.dry_run = dry_run
        self.feature_engine = HMMFeatureEngineering()
        self.models: Dict[str, IOHMM] = {}

        # Statistics
        self.stats = {
            'total_assets': 0,
            'processed': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'total_records': 0,
            'start_time': None,
            'end_time': None
        }

    def get_all_assets(self) -> List[Dict]:
        """Get all active assets ordered by priority"""
        self.cur.execute("""
            SELECT
                canonical_id,
                ticker,
                asset_class,
                exchange_mic
            FROM fhq_meta.assets
            WHERE active_flag = TRUE
            ORDER BY
                CASE asset_class
                    WHEN 'CRYPTO' THEN 1
                    WHEN 'FX' THEN 2
                    ELSE 3
                END,
                canonical_id
        """)
        return list(self.cur.fetchall())

    def get_assets_needing_backfill(self) -> List[Dict]:
        """Get assets with price data that need v4 regime backfill"""
        # Get all assets with price data - we want to compute v4 for all
        self.cur.execute("""
            WITH asset_coverage AS (
                SELECT
                    a.canonical_id,
                    a.ticker,
                    a.asset_class,
                    a.exchange_mic,
                    COUNT(DISTINCT p.timestamp::date) as price_days,
                    COALESCE((
                        SELECT COUNT(DISTINCT timestamp)
                        FROM fhq_perception.regime_daily r
                        WHERE r.asset_id = a.canonical_id AND r.hmm_version = 'v4.0'
                    ), 0) as v4_regime_days
                FROM fhq_meta.assets a
                INNER JOIN fhq_market.prices p ON p.canonical_id = a.canonical_id
                WHERE a.active_flag = TRUE
                GROUP BY a.canonical_id, a.ticker, a.asset_class, a.exchange_mic
                HAVING COUNT(DISTINCT p.timestamp::date) >= 100  -- Need at least 100 days
            )
            SELECT
                canonical_id,
                ticker,
                asset_class,
                exchange_mic,
                price_days,
                v4_regime_days,
                price_days - v4_regime_days as missing_days
            FROM asset_coverage
            WHERE price_days > v4_regime_days  -- Any missing v4 data
            ORDER BY
                CASE asset_class
                    WHEN 'CRYPTO' THEN 1
                    WHEN 'FX' THEN 2
                    ELSE 3
                END,
                missing_days DESC
        """)
        return list(self.cur.fetchall())

    def load_model(self, asset_class: str) -> IOHMM:
        """Load or initialize model for asset class"""
        # Map EQUITY to EQUITIES for config lookup
        config_class = 'EQUITIES' if asset_class == 'EQUITY' else asset_class

        if config_class not in self.models:
            model = load_model_from_db(self.conn, config_class)
            if model is None:
                # Get config and initialize
                self.cur.execute("""
                    SELECT * FROM fhq_perception.hmm_v4_config
                    WHERE asset_class = %s AND is_active = TRUE
                """, (config_class,))
                config_row = self.cur.fetchone()

                if config_row:
                    config = IOHMMConfig(
                        n_states=config_row['n_states'],
                        state_labels=config_row['state_labels'],
                        learning_rate=float(config_row['learning_rate']),
                        hazard_rate=float(config_row['hazard_rate']),
                        changepoint_threshold=float(config_row['changepoint_threshold']),
                        hysteresis_days=config_row['hysteresis_days']
                    )
                else:
                    config = IOHMMConfig()

                model = initialize_model(config, config_class)

            self.models[config_class] = model

        return self.models[config_class]

    def process_single_asset(self, asset: Dict) -> Dict:
        """Process single asset through v4 pipeline"""
        asset_id = asset['canonical_id']
        asset_class = asset['asset_class']

        result = {
            'asset_id': asset_id,
            'status': 'PENDING',
            'records': 0,
            'error': None
        }

        try:
            # Load model
            model = self.load_model(asset_class)

            # Compute features
            features_df = self.feature_engine.compute_features_for_asset(
                self.conn, asset_id, asset_class
            )

            if features_df is None or len(features_df) < 50:
                result['status'] = 'INSUFFICIENT_DATA'
                return result

            # Get dates that need v4 processing
            # We process ALL dates that don't have v4 records yet
            self.cur.execute("""
                SELECT DISTINCT p.timestamp::date as date
                FROM fhq_market.prices p
                WHERE p.canonical_id = %s
                AND p.timestamp::date NOT IN (
                    SELECT timestamp FROM fhq_perception.regime_daily
                    WHERE asset_id = %s AND hmm_version = 'v4.0'
                )
                AND p.timestamp::date >= '2020-01-01'
                ORDER BY date
            """, (asset_id, asset_id))
            missing_dates = [row['date'] for row in self.cur.fetchall()]

            if not missing_dates:
                result['status'] = 'CURRENT'
                return result

            import pandas as pd

            # Normalize features_df index to date objects for comparison
            # features_df.index is pd.Timestamp, missing_dates are datetime.date
            features_dates = set(features_df.index.date if hasattr(features_df.index, 'date')
                                else [d.date() if hasattr(d, 'date') else d for d in features_df.index])

            # Process each date
            records = 0
            for date in missing_dates:
                # Convert to comparable format
                if date not in features_dates:
                    continue

                # Get the row using pd.Timestamp for indexing
                date_ts = pd.Timestamp(date)

                # Try to get row with timestamp index
                try:
                    if date_ts in features_df.index:
                        row = features_df.loc[date_ts]
                    else:
                        # Try normalized date index
                        row = features_df[features_df.index.date == date].iloc[0]
                except (KeyError, IndexError):
                    continue

                # Build feature vectors
                feature_cols = ['return_z', 'volatility_z', 'drawdown_z', 'macd_diff_z',
                               'bb_width_z', 'rsi_14_z', 'roc_20_z']
                covariate_cols = ['yield_spread_z', 'vix_z', 'liquidity_z']

                import numpy as np
                import pandas as pd

                feature_vec = np.array([
                    float(row[col]) if col in row and not pd.isna(row[col]) else 0.0
                    for col in feature_cols
                ])
                covariate_vec = np.array([
                    float(row[col]) if col in row and not pd.isna(row[col]) else 0.0
                    for col in covariate_cols
                ])

                # IOHMM inference
                inference = model.process_observation(feature_vec, covariate_vec)

                technical_regime = inference['technical_regime']
                posteriors = inference['state_posteriors']
                state_labels = model.config.state_labels
                state_probs = {state_labels[i]: posteriors[i] for i in range(len(state_labels))}

                # Store result (if not dry run)
                if not self.dry_run:
                    import hashlib
                    data_str = f"{asset_id}|{date}|{technical_regime}"
                    hash_self = hashlib.sha256(data_str.encode()).hexdigest()

                    self.cur.execute("""
                        INSERT INTO fhq_perception.regime_daily (
                            id, asset_id, timestamp,
                            regime_classification, technical_regime,
                            regime_stability_flag, regime_confidence,
                            consecutive_confirms, prior_regime,
                            changepoint_probability, run_length,
                            hmm_version, engine_version, perception_model_version,
                            formula_hash, lineage_hash, hash_self,
                            anomaly_flag
                        )
                        VALUES (
                            gen_random_uuid(), %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            'v4.0', 'v4.0.0', '2026.PROD.4',
                            %s, %s, %s,
                            %s
                        )
                        ON CONFLICT (asset_id, timestamp) DO UPDATE SET
                            regime_classification = EXCLUDED.regime_classification,
                            technical_regime = EXCLUDED.technical_regime,
                            hmm_version = 'v4.0'
                    """, (
                        asset_id, date,
                        technical_regime, technical_regime,
                        inference['is_confirmed'], inference['regime_confidence'],
                        inference['consecutive_days'], None,
                        inference['changepoint_probability'], inference['run_length'],
                        hash_self, hash_self, hash_self,
                        inference['is_changepoint']
                    ))

                    # Also store in sovereign_regime_state_v4
                    self.cur.execute("""
                        INSERT INTO fhq_perception.sovereign_regime_state_v4 (
                            id, asset_id, timestamp,
                            technical_regime, sovereign_regime,
                            state_probabilities,
                            engine_version
                        )
                        VALUES (
                            gen_random_uuid(), %s, %s,
                            %s, %s,
                            %s,
                            'v4.0.0'
                        )
                        ON CONFLICT (asset_id, timestamp) DO UPDATE SET
                            technical_regime = EXCLUDED.technical_regime,
                            sovereign_regime = EXCLUDED.sovereign_regime,
                            state_probabilities = EXCLUDED.state_probabilities
                    """, (
                        asset_id, date,
                        technical_regime, technical_regime,
                        json.dumps(state_probs)
                    ))

                records += 1

            if not self.dry_run:
                self.conn.commit()

            result['status'] = 'UPDATED'
            result['records'] = records

        except Exception as e:
            result['status'] = 'ERROR'
            result['error'] = str(e)
            logger.error(f"Error processing {asset_id}: {e}")
            self.conn.rollback()

        return result

    def process_batch(self, assets: List[Dict], batch_num: int) -> Dict:
        """Process a batch of assets"""
        batch_stats = {
            'batch': batch_num,
            'assets': len(assets),
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'records': 0
        }

        logger.info(f"=== BATCH {batch_num}: {len(assets)} assets ===")

        for asset in assets:
            asset_id = asset['canonical_id']
            asset_class = asset['asset_class']

            logger.info(f"  Processing {asset_id} ({asset_class})...")

            result = self.process_single_asset(asset)

            if result['status'] == 'UPDATED':
                batch_stats['updated'] += 1
                batch_stats['records'] += result['records']
                logger.info(f"    UPDATED: {result['records']} records")
            elif result['status'] == 'CURRENT':
                batch_stats['skipped'] += 1
                logger.info(f"    CURRENT (no backfill needed)")
            elif result['status'] == 'INSUFFICIENT_DATA':
                batch_stats['skipped'] += 1
                logger.info(f"    SKIPPED: insufficient data")
            else:
                batch_stats['errors'] += 1
                logger.error(f"    ERROR: {result.get('error', 'unknown')}")

        return batch_stats

    def run(self, resume: bool = False, limit: Optional[int] = None) -> Dict:
        """Run full backfill with batching"""
        self.stats['start_time'] = datetime.now(timezone.utc)

        logger.info("=" * 70)
        logger.info("IoS-003 v4 HMM REGIME BACKFILL")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Delay between batches: {self.delay_seconds}s")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 70)

        # Get assets needing backfill
        assets = self.get_assets_needing_backfill()

        if limit:
            assets = assets[:limit]

        self.stats['total_assets'] = len(assets)
        logger.info(f"Total assets needing backfill: {len(assets)}")

        # Handle resume
        start_idx = 0
        if resume:
            checkpoint = load_checkpoint()
            if checkpoint and checkpoint.get('processed_ids'):
                processed_ids = set(checkpoint['processed_ids'])
                assets = [a for a in assets if a['canonical_id'] not in processed_ids]
                start_idx = checkpoint.get('processed', 0)
                logger.info(f"Resuming from checkpoint: {start_idx} already processed")

        if not assets:
            logger.info("No assets need backfill!")
            return self.stats

        # Process in batches
        processed_ids = []
        total_batches = (len(assets) + self.batch_size - 1) // self.batch_size

        for batch_num, i in enumerate(range(0, len(assets), self.batch_size), 1):
            batch = assets[i:i + self.batch_size]

            # Process batch
            batch_stats = self.process_batch(batch, batch_num)

            # Update stats
            self.stats['processed'] += batch_stats['assets']
            self.stats['updated'] += batch_stats['updated']
            self.stats['skipped'] += batch_stats['skipped']
            self.stats['errors'] += batch_stats['errors']
            self.stats['total_records'] += batch_stats['records']

            # Track processed IDs
            for asset in batch:
                processed_ids.append(asset['canonical_id'])

            # Save checkpoint
            save_checkpoint({
                'processed': self.stats['processed'],
                'total': self.stats['total_assets'],
                'processed_ids': processed_ids,
                'stats': self.stats
            })

            # Progress report
            progress = (batch_num / total_batches) * 100
            logger.info(f"Progress: {progress:.1f}% ({batch_num}/{total_batches} batches)")

            # Rate-limit pause between batches
            if batch_num < total_batches and self.delay_seconds > 0:
                logger.info(f"Rate-limit pause: {self.delay_seconds}s...")
                time.sleep(self.delay_seconds)

        # Save models
        if not self.dry_run:
            for asset_class, model in self.models.items():
                logger.info(f"Saving model for {asset_class}...")
                save_model_to_db(self.conn, model, asset_class)

        # Clear checkpoint on success
        clear_checkpoint()

        self.stats['end_time'] = datetime.now(timezone.utc)
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()

        # Final report
        logger.info("=" * 70)
        logger.info("BACKFILL COMPLETE")
        logger.info(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
        logger.info(f"Total assets: {self.stats['total_assets']}")
        logger.info(f"Updated: {self.stats['updated']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Total records: {self.stats['total_records']}")
        logger.info("=" * 70)

        # Log governance event
        if not self.dry_run:
            self.cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id, action_type, action_target, action_target_type,
                    initiated_by, initiated_at, decision, decision_rationale,
                    hash_chain_id
                ) VALUES (
                    gen_random_uuid(), 'BACKFILL', 'IOS003_V4', 'MODULE',
                    'STIG', NOW(), 'COMPLETED',
                    %s,
                    encode(sha256(%s::bytea), 'hex')
                )
            """, (
                json.dumps(self.stats, default=str),
                f"IOS003_V4_BACKFILL_{datetime.now().isoformat()}"
            ))
            self.conn.commit()

        return self.stats

    def close(self):
        self.cur.close()
        self.conn.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='IoS-003 v4 HMM Regime Backfill with Rate-Limit Protection'
    )
    parser.add_argument(
        '--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
        help=f'Assets per batch (default: {DEFAULT_BATCH_SIZE})'
    )
    parser.add_argument(
        '--delay', type=int, default=DEFAULT_DELAY_SECONDS,
        help=f'Seconds between batches (default: {DEFAULT_DELAY_SECONDS})'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Run without writing to database'
    )
    parser.add_argument(
        '--resume', action='store_true',
        help='Resume from last checkpoint'
    )
    parser.add_argument(
        '--limit', type=int,
        help='Limit number of assets to process'
    )

    args = parser.parse_args()

    backfill = V4RegimeBackfill(
        batch_size=args.batch_size,
        delay_seconds=args.delay,
        dry_run=args.dry_run
    )

    try:
        stats = backfill.run(resume=args.resume, limit=args.limit)
        return stats['errors'] == 0
    finally:
        backfill.close()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
