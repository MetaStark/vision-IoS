#!/usr/bin/env python3
"""
IoS-003 v4 Targeted Backfill - 4 Missing Assets
================================================
Authority: CEO Directive
Date: 2025-12-11
Executor: STIG (CTO)

Target assets with price data but missing HMM regimes:
- COMP-USD (CRYPTO)
- FTM-USD (CRYPTO)
- GRT-USD (CRYPTO)
- PGS.OL (EQUITY)
"""

import os
import sys
import json
from datetime import datetime, timezone
import logging

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from hmm_feature_engineering_v4 import HMMFeatureEngineering, classify_asset_class
from hmm_iohmm_online import (
    IOHMM, IOHMMConfig, load_model_from_db, save_model_to_db, initialize_model
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("IOS003_V4_TARGETED")

DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

TARGET_ASSETS = ['COMP-USD', 'FTM-USD', 'GRT-USD', 'PGS.OL']


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def process_single_asset(conn, asset_id: str, asset_class: str) -> dict:
    """Process HMM backfill for a single asset"""
    result = {
        'asset_id': asset_id,
        'asset_class': asset_class,
        'status': 'PENDING',
        'rows_created': 0,
        'error': None
    }

    try:
        # Initialize feature engineering
        fe = HMMFeatureEngineering()

        # Get price data
        features_df = fe.compute_features_for_asset(conn, asset_id, asset_class)

        if features_df is None or len(features_df) < 30:
            result['status'] = 'SKIPPED'
            result['error'] = f'Insufficient data: {len(features_df) if features_df is not None else 0} rows'
            return result

        logger.info(f"  [{asset_id}] Feature matrix: {len(features_df)} rows")

        # Load or initialize model for asset class
        model = load_model_from_db(conn, asset_class)
        if model is None:
            model = initialize_model(asset_class)
            logger.info(f"  [{asset_id}] Initialized new model for {asset_class}")

        # Get macro covariates
        macro_df = fe.get_macro_covariates(
            features_df.index.min(),
            features_df.index.max()
        )

        # Run IOHMM inference
        regime_results = []
        for i, (date, row) in enumerate(features_df.iterrows()):
            try:
                obs = row[['return_z', 'volatility_z', 'drawdown_z', 'macd_diff_z',
                          'bb_width_z', 'rsi_14_z', 'roc_20_z']].values

                macro_cov = None
                if macro_df is not None and date in macro_df.index:
                    macro_cov = macro_df.loc[date][['yield_spread_z', 'vix_z',
                                                    'inflation_z', 'liquidity_z']].values

                # Update model and get state
                state_probs = model.filter_step(obs, macro_cov)
                regime = model.get_regime_label(state_probs)
                confidence = float(state_probs.max())

                regime_results.append({
                    'timestamp': date,
                    'regime': regime,
                    'confidence': confidence,
                    'state_probs': state_probs.tolist()
                })

            except Exception as e:
                continue

        if not regime_results:
            result['status'] = 'FAILED'
            result['error'] = 'No regime results generated'
            return result

        # Write to database
        with conn.cursor() as cur:
            for r in regime_results:
                cur.execute("""
                    INSERT INTO fhq_perception.regime_daily (
                        asset_id, timestamp, regime_classification, regime_confidence,
                        regime_stability_flag, consecutive_confirms, hmm_version,
                        engine_version, perception_model_version
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (asset_id, timestamp) DO UPDATE SET
                        regime_classification = EXCLUDED.regime_classification,
                        regime_confidence = EXCLUDED.regime_confidence,
                        hmm_version = EXCLUDED.hmm_version
                """, (
                    asset_id,
                    r['timestamp'],
                    r['regime'],
                    r['confidence'],
                    r['confidence'] > 0.7,
                    1,
                    'v4.0',
                    'IOHMM-STUDENT-T',
                    '4.0.0'
                ))
            conn.commit()

        result['status'] = 'SUCCESS'
        result['rows_created'] = len(regime_results)
        logger.info(f"  [{asset_id}] Created {len(regime_results)} regime rows")

    except Exception as e:
        result['status'] = 'FAILED'
        result['error'] = str(e)
        logger.error(f"  [{asset_id}] Error: {e}")
        conn.rollback()

    return result


def main():
    logger.info("=" * 70)
    logger.info("IoS-003 v4 TARGETED BACKFILL - 4 Missing Assets")
    logger.info("=" * 70)

    conn = get_connection()

    # Get asset info
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT canonical_id, ticker, asset_class
            FROM fhq_meta.assets
            WHERE canonical_id = ANY(%s)
        """, (TARGET_ASSETS,))
        assets = cur.fetchall()

    logger.info(f"Processing {len(assets)} target assets")

    results = []
    for asset in assets:
        asset_id = asset['canonical_id']
        asset_class = asset['asset_class']

        logger.info(f"Processing: {asset_id} ({asset_class})")
        result = process_single_asset(conn, asset_id, asset_class)
        results.append(result)

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 70)

    success = sum(1 for r in results if r['status'] == 'SUCCESS')
    total_rows = sum(r['rows_created'] for r in results)

    logger.info(f"Assets processed: {len(results)}")
    logger.info(f"Successful: {success}")
    logger.info(f"Total regime rows created: {total_rows}")

    for r in results:
        status_icon = "OK" if r['status'] == 'SUCCESS' else "FAIL"
        logger.info(f"  [{status_icon}] {r['asset_id']}: {r['rows_created']} rows - {r['status']}")
        if r['error']:
            logger.info(f"       Error: {r['error']}")

    conn.close()

    # Save evidence
    evidence = {
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'target_assets': TARGET_ASSETS,
        'results': results,
        'summary': {
            'total': len(results),
            'success': success,
            'rows_created': total_rows
        }
    }

    evidence_file = f"evidence/TARGETED_BACKFILL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs('evidence', exist_ok=True)
    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    logger.info(f"Evidence saved: {evidence_file}")

    return results


if __name__ == "__main__":
    main()
