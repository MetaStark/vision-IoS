#!/usr/bin/env python3
"""
IOS-010 OUTCOME CAPTURE DAEMON
==============================
CEO Directive: CEO-DIR-2026-007
Classification: STRATEGIC-FUNDAMENTAL (Class A+)
IoS Module: IoS-010 Prediction Ledger Engine

Purpose:
    Captures realized market outcomes at defined T+n horizons.
    Outcomes are immutable and timestamp-bound, independent of predictions.

Constitutional Alignment:
    - ADR-013: One-true-source (outcomes are canonical truth)
    - CEO-DIR-2026-006: Outcomes must be independent of predictions
    - CEO-DIR-2026-007: No circular contamination

Flow:
    1. Query regime_daily for realized regime classifications
    2. For each observation, create outcome_ledger entry
    3. Ensure no duplicate outcomes for same asset/timestamp
    4. Log evidence to governance

Schedule: Every 4 hours (0 */4 * * *)
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
logger = logging.getLogger("ios010_outcome_capture")

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

HASH_CHAIN_PREFIX = "IOS010-OUTCOME"
LOOKBACK_HOURS = 48  # How far back to look for unprocessed observations

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# CORE LOGIC
# =============================================================================

def get_uncaptured_regime_observations(conn) -> List[Dict]:
    """
    Get regime observations that haven't been captured as outcomes yet.
    Uses sovereign_regime_state_v4 as the canonical v4 regime source.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # First check if we have data in sovereign_regime_state_v4
        cur.execute("""
            SELECT
                srs.asset_id,
                srs.timestamp::timestamptz AS timestamp,
                srs.sovereign_regime AS realized_regime,
                NULL::numeric AS confidence,
                srs.state_probabilities AS regime_probabilities,
                srs.created_at AS updated_at
            FROM fhq_perception.sovereign_regime_state_v4 srs
            LEFT JOIN fhq_research.outcome_ledger ol
                ON ol.outcome_domain = srs.asset_id
                AND ol.outcome_type = 'REGIME'
                AND DATE_TRUNC('hour', ol.outcome_timestamp) = DATE_TRUNC('hour', srs.timestamp)
            WHERE srs.timestamp > NOW() - INTERVAL '%s hours'
              AND ol.outcome_id IS NULL
            ORDER BY srs.timestamp ASC
            LIMIT 1000
        """ % LOOKBACK_HOURS)
        return [dict(row) for row in cur.fetchall()]


def compute_outcome_hash(
    outcome_type: str,
    outcome_domain: str,
    outcome_value: str,
    outcome_timestamp: datetime
) -> str:
    """Compute deterministic content hash for outcome"""
    data = f"{outcome_type}|{outcome_domain}|{outcome_value}|{outcome_timestamp.isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()


def capture_regime_outcome(conn, observation: Dict) -> Optional[str]:
    """
    Convert a regime observation to an outcome record.
    Returns outcome_id if successful, None if skipped.
    """
    try:
        outcome_timestamp = observation['timestamp']
        realized_regime = observation['realized_regime']

        # Prepare evidence data
        evidence_data = {
            'confidence': float(observation['confidence']) if observation['confidence'] else None,
            'regime_probabilities': observation['regime_probabilities'],
            'source_updated_at': observation['updated_at'].isoformat() if observation['updated_at'] else None
        }

        # Compute content hash
        content_hash = compute_outcome_hash(
            outcome_type='REGIME',
            outcome_domain=observation['asset_id'],
            outcome_value=realized_regime,
            outcome_timestamp=outcome_timestamp
        )

        # Create hash chain ID
        hash_chain_id = f"{HASH_CHAIN_PREFIX}-{observation['asset_id']}-{outcome_timestamp.strftime('%Y%m%d%H')}"

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_research.outcome_ledger (
                    outcome_type,
                    outcome_domain,
                    outcome_value,
                    outcome_timestamp,
                    evidence_source,
                    evidence_data,
                    content_hash,
                    hash_chain_id,
                    created_by
                ) VALUES (
                    'REGIME',
                    %(asset_id)s,
                    %(realized_regime)s,
                    %(timestamp)s,
                    'sovereign_regime_state_v4',
                    %(evidence_data)s,
                    %(content_hash)s,
                    %(hash_chain_id)s,
                    'STIG'
                )
                ON CONFLICT DO NOTHING
                RETURNING outcome_id
            """, {
                'asset_id': observation['asset_id'],
                'realized_regime': realized_regime,
                'timestamp': outcome_timestamp,
                'evidence_data': json.dumps(evidence_data),
                'content_hash': content_hash,
                'hash_chain_id': hash_chain_id
            })

            result = cur.fetchone()
            return str(result[0]) if result else None

    except Exception as e:
        logger.error(f"Failed to capture outcome for {observation['asset_id']}: {e}")
        return None


def log_capture_evidence(conn, stats: Dict[str, Any]) -> str:
    """Log outcome capture run to governance"""
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
                'IOS010_OUTCOME_CAPTURE',
                'fhq_research.outcome_ledger',
                'DAEMON_EXECUTION',
                'STIG',
                'EXECUTED',
                'CEO-DIR-2026-007: Market outcomes captured for epistemic reconciliation',
                %s
            )
            RETURNING action_id
        """, (json.dumps({
            'evidence_id': evidence_id,
            'directive': 'CEO-DIR-2026-007',
            'ios': 'IoS-010',
            'daemon': 'ios010_outcome_capture_daemon',
            'statistics': stats,
            'evidence_hash': evidence_hash,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }),))

    return evidence_id


def run_outcome_capture() -> Dict[str, Any]:
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("IOS-010 OUTCOME CAPTURE DAEMON")
    logger.info("Directive: CEO-DIR-2026-007")
    logger.info("=" * 60)

    stats = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'observations_found': 0,
        'outcomes_captured': 0,
        'duplicates_skipped': 0,
        'errors': 0,
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Get uncaptured observations
        observations = get_uncaptured_regime_observations(conn)
        stats['observations_found'] = len(observations)
        logger.info(f"Found {len(observations)} uncaptured regime observations")

        if not observations:
            logger.info("No observations to capture")
            stats['completed_at'] = datetime.now(timezone.utc).isoformat()
            return stats

        # Capture each observation
        for obs in observations:
            outcome_id = capture_regime_outcome(conn, obs)
            if outcome_id:
                stats['outcomes_captured'] += 1
                logger.debug(f"Captured outcome for {obs['asset_id']} at {obs['timestamp']}")
            else:
                # Could be duplicate or error
                stats['duplicates_skipped'] += 1

        conn.commit()

        # Log evidence
        evidence_id = log_capture_evidence(conn, stats)
        stats['evidence_id'] = evidence_id
        conn.commit()

        logger.info(f"Outcome capture complete: {stats['outcomes_captured']}/{stats['observations_found']} captured")

    except Exception as e:
        logger.error(f"Outcome capture failed: {e}")
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
    result = run_outcome_capture()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)
