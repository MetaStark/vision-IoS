#!/usr/bin/env python3
"""
Phase 2 Experiment Registration - One-Shot Registration Script
==============================================================

Purpose: Register TEST A/B/C (Alpha Satellite) in experiment_registry.

Blueprints (from hypothesis_canon):
  TEST A: ALPHA_SAT_A_VOL_SQUEEZE_V1.1   (3969b7a9-e668-4e08-83f4-b5dd4021da9a)
  TEST B: ALPHA_SAT_B_REGIME_ALIGN_V1.1   (09030c4d-03c2-4776-9384-e68562ff8df8)
  TEST C: ALPHA_SAT_C_MEAN_REVERT_V1.1    (6d958167-b763-4f40-a399-184a87be4f4b)

Authority: CEO Phase 2 Runtime Fabrication Directive
Contract: EC-003_2026_PRODUCTION

Usage:
    python ops_phase2_registration.py

Author: STIG (EC-003)
Date: 2026-01-29
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[PHASE2_REG] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/ops_phase2_registration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Phase2Registration')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Fixed namespace for deterministic experiment IDs
NAMESPACE = uuid.UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')

# Sentinel error_id for non-error-origin experiments (CHECK constraint requires NOT NULL)
SENTINEL_ERROR_ID = uuid.uuid5(NAMESPACE, 'ALPHA_SAT_NON_ERROR_ORIGIN')

# Blueprint definitions
BLUEPRINTS = [
    {
        'canon_id': '3969b7a9-e668-4e08-83f4-b5dd4021da9a',
        'hypothesis_code': 'ALPHA_SAT_A_VOL_SQUEEZE_V1.1',
        'experiment_code': 'EXP_ALPHA_SAT_A_V1.1',
        'indicator_table': 'fhq_indicators.volatility',
    },
    {
        'canon_id': '09030c4d-03c2-4776-9384-e68562ff8df8',
        'hypothesis_code': 'ALPHA_SAT_B_REGIME_ALIGN_V1.1',
        'experiment_code': 'EXP_ALPHA_SAT_B_V1.1',
        'indicator_table': 'fhq_indicators.momentum',
    },
    {
        'canon_id': '6d958167-b763-4f40-a399-184a87be4f4b',
        'hypothesis_code': 'ALPHA_SAT_C_MEAN_REVERT_V1.1',
        'experiment_code': 'EXP_ALPHA_SAT_C_V1.1',
        'indicator_table': 'fhq_indicators.volatility',
    },
    # Wave 1 (D-F)
    {
        'canon_id': 'ba14214b-830f-4af7-9fbc-cf30226fc83a',
        'hypothesis_code': 'ALPHA_SAT_D_BREAKOUT_V1.0',
        'experiment_code': 'EXP_ALPHA_SAT_D_V1.0',
        'indicator_table': 'fhq_indicators.volatility',
    },
    {
        'canon_id': '3f28b5b2-c727-49cf-b0d0-71fd172151a7',
        'hypothesis_code': 'ALPHA_SAT_E_TREND_PULLBACK_V1.0',
        'experiment_code': 'EXP_ALPHA_SAT_E_V1.0',
        'indicator_table': 'fhq_indicators.momentum',
    },
    {
        'canon_id': '1d023cb7-9cfe-4e90-a2c9-5b367c640e90',
        'hypothesis_code': 'ALPHA_SAT_F_PANIC_BOTTOM_V1.0',
        'experiment_code': 'EXP_ALPHA_SAT_F_V1.0',
        'indicator_table': 'fhq_indicators.momentum',
    },
]


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def get_regime_snapshot(cur):
    """Get latest regime snapshot from sovereign_regime_state_v4 for crypto assets."""
    cur.execute("""
        SELECT DISTINCT ON (asset_id)
            asset_id, sovereign_regime, engine_version, timestamp
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id LIKE '%%-USD'
        ORDER BY asset_id, timestamp DESC
    """)
    rows = cur.fetchall()
    snapshot = {}
    for r in rows:
        snapshot[r['asset_id']] = {
            'sovereign_regime': r['sovereign_regime'],
            'engine_version': r['engine_version'],
            'timestamp': r['timestamp'].isoformat() if r['timestamp'] else None
        }
    return snapshot


def get_dataset_stats(cur, table_name):
    """Get dataset statistics for a given indicator table (crypto only)."""
    cur.execute(f"""
        SELECT COUNT(*) as row_count,
               MIN(signal_date) as min_date,
               MAX(signal_date) as max_date
        FROM {table_name}
        WHERE listing_id LIKE '%%-USD'
    """)
    return cur.fetchone()


def compute_dataset_signature(table_name, stats):
    """Compute SHA256 signature of dataset characteristics."""
    sig_input = json.dumps({
        'table': table_name,
        'row_count': stats['row_count'],
        'min_date': stats['min_date'].isoformat() if stats['min_date'] else 'NULL',
        'max_date': stats['max_date'].isoformat() if stats['max_date'] else 'NULL',
    }, sort_keys=True)
    return hashlib.sha256(sig_input.encode()).hexdigest()


def compute_system_state_hash(regime_snapshot):
    """Compute SHA256 of current system state."""
    canonical = json.dumps(regime_snapshot, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def get_falsification_criteria(cur, canon_id):
    """Fetch falsification_criteria JSONB from hypothesis_canon."""
    cur.execute("""
        SELECT falsification_criteria
        FROM fhq_learning.hypothesis_canon
        WHERE canon_id = %s
    """, (canon_id,))
    row = cur.fetchone()
    return row['falsification_criteria'] if row else {}


def count_parameters(falsification_criteria):
    """Count the number of parameters in falsification_criteria for tier1 check."""
    ms = falsification_criteria.get('measurement_schema', {})
    trigger = ms.get('trigger', {})
    # Parameters: indicator, condition, regime_filter (if present)
    count = 0
    if trigger.get('indicator'):
        count += 1
    if trigger.get('condition'):
        count += 1
    if trigger.get('regime_filter'):
        count += 1
    return count


def register_experiments():
    """Main registration logic."""
    conn = get_db_connection()
    conn.autocommit = False
    registered = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Gather regime snapshot (shared across all experiments)
            regime_snapshot = get_regime_snapshot(cur)
            system_state_hash = compute_system_state_hash(regime_snapshot)
            logger.info(f"Regime snapshot: {len(regime_snapshot)} assets, hash={system_state_hash[:16]}...")

            for bp in BLUEPRINTS:
                experiment_id = uuid.uuid5(NAMESPACE, bp['hypothesis_code'])
                logger.info(f"Processing {bp['experiment_code']} (id={experiment_id})")

                # Check if already registered (idempotent)
                cur.execute("""
                    SELECT experiment_id, status FROM fhq_learning.experiment_registry
                    WHERE experiment_id = %s
                """, (str(experiment_id),))
                existing = cur.fetchone()
                if existing:
                    logger.info(f"  Already exists (status={existing['status']}). Skipping.")
                    registered.append({
                        'experiment_code': bp['experiment_code'],
                        'experiment_id': str(experiment_id),
                        'action': 'ALREADY_EXISTS',
                        'status': existing['status']
                    })
                    continue

                # Get dataset stats
                stats = get_dataset_stats(cur, bp['indicator_table'])
                dataset_sig = compute_dataset_signature(bp['indicator_table'], stats)

                # Get falsification criteria
                fc = get_falsification_criteria(cur, bp['canon_id'])
                param_count = count_parameters(fc)

                # INSERT (tier_name, parameter_count are generated columns)
                cur.execute("""
                    INSERT INTO fhq_learning.experiment_registry (
                        experiment_id, experiment_code, hypothesis_id,
                        origin_error_id, experiment_tier,
                        error_id, system_state_hash, regime_snapshot,
                        dataset_signature, dataset_start_date, dataset_end_date,
                        dataset_row_count, parameters,
                        dof_count, execution_mode, status,
                        created_by, started_at
                    ) VALUES (
                        %s, %s, %s,
                        NULL, 1,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        1, 'EXPERIMENT', 'RUNNING',
                        'STIG', NOW()
                    )
                    ON CONFLICT (experiment_id) DO NOTHING
                """, (
                    str(experiment_id), bp['experiment_code'], bp['canon_id'],
                    str(SENTINEL_ERROR_ID), system_state_hash, json.dumps(regime_snapshot, default=str),
                    dataset_sig, stats['min_date'], stats['max_date'],
                    stats['row_count'], json.dumps(fc),
                ))
                logger.info(f"  Registered: {bp['experiment_code']}")
                registered.append({
                    'experiment_code': bp['experiment_code'],
                    'experiment_id': str(experiment_id),
                    'action': 'REGISTERED',
                    'dataset_rows': stats['row_count'],
                    'param_count': param_count,
                })

            # Activate hypothesis_canon entries (cast text[] to uuid[])
            canon_ids = [bp['canon_id'] for bp in BLUEPRINTS]
            cur.execute("""
                UPDATE fhq_learning.hypothesis_canon
                SET status = 'ACTIVE', activated_at = NOW(), last_updated_by = 'STIG', last_updated_at = NOW()
                WHERE canon_id = ANY(%s::uuid[]) AND status != 'ACTIVE'
            """, (canon_ids,))
            activated_count = cur.rowcount
            logger.info(f"Activated {activated_count} hypothesis_canon entries")

            conn.commit()
            logger.info("Transaction committed.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Registration failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()

    return registered, system_state_hash


def write_evidence(registered, system_state_hash):
    """Write evidence artifact."""
    evidence = {
        'evidence_type': 'PHASE2_EXPERIMENT_REGISTRATION',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'created_by': 'STIG',
        'directive': 'CEO_PHASE2_RUNTIME_FABRICATION',
        'system_state_hash': system_state_hash,
        'sentinel_error_id': str(SENTINEL_ERROR_ID),
        'experiments': registered,
        'verification': {
            'idempotent': True,
            'deterministic_ids': True,
            'namespace': str(NAMESPACE),
        }
    }
    evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    evidence['evidence_hash'] = evidence_hash

    path = '03_FUNCTIONS/evidence/PHASE2_EXPERIMENT_REGISTRATION.json'
    with open(path, 'w') as f:
        json.dump(evidence, f, indent=2)
    logger.info(f"Evidence written: {path} (hash={evidence_hash[:16]}...)")
    return evidence_hash


def verify_registration(conn_params):
    """Post-registration verification."""
    conn = psycopg2.connect(**conn_params)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT experiment_id, experiment_code, status
                FROM fhq_learning.experiment_registry
                WHERE experiment_code LIKE 'EXP_ALPHA_SAT_%%'
                ORDER BY experiment_code
            """)
            experiments = cur.fetchall()

            cur.execute("""
                SELECT canon_id, hypothesis_code, status
                FROM fhq_learning.hypothesis_canon
                WHERE canon_id IN (
                    '3969b7a9-e668-4e08-83f4-b5dd4021da9a',
                    '09030c4d-03c2-4776-9384-e68562ff8df8',
                    '6d958167-b763-4f40-a399-184a87be4f4b'
                )
                ORDER BY hypothesis_code
            """)
            hypotheses = cur.fetchall()

            return experiments, hypotheses
    finally:
        conn.close()


def main():
    logger.info("=" * 60)
    logger.info("PHASE 2 EXPERIMENT REGISTRATION - START")
    logger.info(f"Sentinel error_id: {SENTINEL_ERROR_ID}")
    logger.info(f"Namespace: {NAMESPACE}")
    logger.info("=" * 60)

    registered, state_hash = register_experiments()
    evidence_hash = write_evidence(registered, state_hash)

    # Verification
    experiments, hypotheses = verify_registration(DB_CONFIG)

    logger.info("=" * 60)
    logger.info("VERIFICATION RESULTS:")
    for exp in experiments:
        logger.info(f"  {exp['experiment_code']}: {exp['status']} (id={exp['experiment_id']})")
    for hyp in hypotheses:
        logger.info(f"  {hyp['hypothesis_code']}: {hyp['status']}")
    logger.info(f"Evidence hash: {evidence_hash[:16]}...")
    logger.info("PHASE 2 EXPERIMENT REGISTRATION - COMPLETE")
    logger.info("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
