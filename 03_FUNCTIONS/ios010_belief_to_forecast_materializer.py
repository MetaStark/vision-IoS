#!/usr/bin/env python3
"""
IOS-010 BELIEF TO FORECAST MATERIALIZER
========================================
CEO Directive: CEO-DIR-2026-007
Classification: STRATEGIC-FUNDAMENTAL (Class A+)
IoS Module: IoS-010 Prediction Ledger Engine

Purpose:
    Converts immutable model_belief_state records into time-horizon-specific
    forecasts in forecast_ledger. Beliefs ARE implicit forecasts - this daemon
    materializes that relationship.

Constitutional Alignment:
    - ADR-013: One-true-source (beliefs materialize to forecasts)
    - CEO-DIR-2026-006: Epistemic Memory (predictions must be recorded)
    - CEO-DIR-2026-007: No policy influence permitted

Flow:
    1. Query model_belief_state for unprocessed beliefs
    2. For each belief, create corresponding forecast_ledger entry
    3. Mark belief as materialized (via tracking table or metadata)
    4. Log evidence to governance

Schedule: Daily at 00:00 UTC (after nightly belief generation)
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ios010_belief_materializer")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

# Belief to forecast mapping
BELIEF_HORIZON_HOURS = 24  # Regime beliefs are T+1 day forecasts
HASH_CHAIN_PREFIX = "IOS010-BELIEF-FORECAST"

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# CORE LOGIC
# =============================================================================

def get_unmaterialized_beliefs(conn) -> List[Dict]:
    """
    Get beliefs that haven't been materialized to forecasts yet.
    Uses LEFT JOIN to find beliefs without corresponding forecasts.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                mbs.belief_id,
                mbs.asset_id,
                mbs.belief_timestamp,
                mbs.technical_regime,
                mbs.belief_distribution,
                mbs.belief_confidence,
                mbs.dominant_regime,
                mbs.model_version,
                mbs.inference_engine,
                mbs.feature_hash,
                mbs.entropy,
                mbs.lineage_hash
            FROM fhq_perception.model_belief_state mbs
            LEFT JOIN fhq_research.forecast_ledger fl
                ON fl.state_snapshot_id = mbs.belief_id
                AND fl.forecast_type = 'REGIME'
            WHERE fl.forecast_id IS NULL
            ORDER BY mbs.belief_timestamp ASC
            LIMIT 1000
        """)
        return [dict(row) for row in cur.fetchall()]


def compute_forecast_hash(
    forecast_type: str,
    forecast_domain: str,
    forecast_value: str,
    forecast_probability: float,
    forecast_made_at: datetime,
    state_hash: str
) -> str:
    """Compute deterministic content hash for forecast"""
    data = f"{forecast_type}|{forecast_domain}|{forecast_value}|{forecast_probability:.6f}|{forecast_made_at.isoformat()}|{state_hash}"
    return hashlib.sha256(data.encode()).hexdigest()


def materialize_belief_to_forecast(conn, belief: Dict) -> Optional[str]:
    """
    Convert a single belief to a forecast record.
    Returns forecast_id if successful, None if skipped.
    """
    try:
        forecast_made_at = belief['belief_timestamp']
        forecast_valid_from = forecast_made_at
        forecast_valid_until = forecast_made_at + timedelta(hours=BELIEF_HORIZON_HOURS)

        # Extract dominant regime probability from distribution
        distribution = belief['belief_distribution']
        if isinstance(distribution, str):
            distribution = json.loads(distribution)

        dominant_regime = belief['dominant_regime']
        forecast_probability = distribution.get(dominant_regime, belief['belief_confidence'])

        # Compute content hash
        content_hash = compute_forecast_hash(
            forecast_type='REGIME',
            forecast_domain=belief['asset_id'],
            forecast_value=dominant_regime,
            forecast_probability=float(forecast_probability),
            forecast_made_at=forecast_made_at,
            state_hash=belief.get('feature_hash', belief['lineage_hash'])
        )

        # Create hash chain ID
        hash_chain_id = f"{HASH_CHAIN_PREFIX}-{belief['belief_id']}"

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_research.forecast_ledger (
                    forecast_type,
                    forecast_source,
                    forecast_domain,
                    forecast_value,
                    forecast_probability,
                    forecast_confidence,
                    forecast_horizon_hours,
                    forecast_made_at,
                    forecast_valid_from,
                    forecast_valid_until,
                    state_vector_hash,
                    state_snapshot_id,
                    model_id,
                    model_version,
                    feature_set,
                    content_hash,
                    hash_chain_id,
                    created_by
                ) VALUES (
                    'REGIME',
                    'MODEL_BELIEF_STATE',
                    %(asset_id)s,
                    %(dominant_regime)s,
                    %(probability)s,
                    %(confidence)s,
                    %(horizon)s,
                    %(made_at)s,
                    %(valid_from)s,
                    %(valid_until)s,
                    %(state_hash)s,
                    %(belief_id)s,
                    %(inference_engine)s,
                    %(model_version)s,
                    %(distribution)s,
                    %(content_hash)s,
                    %(hash_chain_id)s,
                    'STIG'
                )
                RETURNING forecast_id
            """, {
                'asset_id': belief['asset_id'],
                'dominant_regime': dominant_regime,
                'probability': float(forecast_probability),
                'confidence': float(belief['belief_confidence']),
                'horizon': BELIEF_HORIZON_HOURS,
                'made_at': forecast_made_at,
                'valid_from': forecast_valid_from,
                'valid_until': forecast_valid_until,
                'state_hash': belief.get('feature_hash') or belief['lineage_hash'],
                'belief_id': belief['belief_id'],
                'inference_engine': belief['inference_engine'],
                'model_version': belief['model_version'],
                'distribution': json.dumps(distribution),
                'content_hash': content_hash,
                'hash_chain_id': hash_chain_id
            })

            result = cur.fetchone()
            return str(result[0]) if result else None

    except Exception as e:
        logger.error(f"Failed to materialize belief {belief['belief_id']}: {e}")
        return None


def log_materialization_evidence(conn, stats: Dict[str, Any]) -> str:
    """Log materialization run to governance"""
    evidence_id = str(uuid.uuid4())
    evidence_hash = hashlib.sha256(json.dumps(stats, default=str).encode()).hexdigest()

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_type,
                action_target,
                action_target_type,
                initiated_by,
                decision,
                decision_rationale,
                metadata
            ) VALUES (
                'IOS010_BELIEF_MATERIALIZATION',
                'fhq_research.forecast_ledger',
                'DAEMON_EXECUTION',
                'STIG',
                'EXECUTED',
                'CEO-DIR-2026-007: Beliefs materialized to forecasts for epistemic reconciliation',
                %s
            )
            RETURNING action_id
        """, (json.dumps({
            'evidence_id': evidence_id,
            'directive': 'CEO-DIR-2026-007',
            'ios': 'IoS-010',
            'daemon': 'ios010_belief_to_forecast_materializer',
            'statistics': stats,
            'evidence_hash': evidence_hash,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }),))

    return evidence_id


def run_materialization() -> Dict[str, Any]:
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("IOS-010 BELIEF TO FORECAST MATERIALIZER")
    logger.info("Directive: CEO-DIR-2026-007")
    logger.info("=" * 60)

    stats = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'beliefs_found': 0,
        'forecasts_created': 0,
        'errors': 0,
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Get unmaterialized beliefs
        beliefs = get_unmaterialized_beliefs(conn)
        stats['beliefs_found'] = len(beliefs)
        logger.info(f"Found {len(beliefs)} unmaterialized beliefs")

        if not beliefs:
            logger.info("No beliefs to materialize")
            stats['completed_at'] = datetime.now(timezone.utc).isoformat()
            return stats

        # Materialize each belief
        for belief in beliefs:
            forecast_id = materialize_belief_to_forecast(conn, belief)
            if forecast_id:
                stats['forecasts_created'] += 1
                logger.debug(f"Materialized belief {belief['belief_id']} -> forecast {forecast_id}")
            else:
                stats['errors'] += 1

        conn.commit()

        # Log evidence
        evidence_id = log_materialization_evidence(conn, stats)
        stats['evidence_id'] = evidence_id
        conn.commit()

        logger.info(f"Materialization complete: {stats['forecasts_created']}/{stats['beliefs_found']} beliefs converted")

    except Exception as e:
        logger.error(f"Materialization failed: {e}")
        stats['status'] = 'FAILED'
        stats['error_message'] = str(e)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    stats['completed_at'] = datetime.now(timezone.utc).isoformat()
    return stats


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    result = run_materialization()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)
