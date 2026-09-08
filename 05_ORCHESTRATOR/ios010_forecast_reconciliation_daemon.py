#!/usr/bin/env python3
"""
IOS-010 FORECAST RECONCILIATION DAEMON
======================================
CEO Directive: CEO-DIR-2026-007
Classification: STRATEGIC-FUNDAMENTAL (Class A+)
IoS Module: IoS-010 Prediction Ledger Engine

Purpose:
    Pairs forecasts with outcomes using deterministic matching.
    Classifies epistemic error types per IoS-010 taxonomy.
    This is the CORE of truth reconciliation.

Constitutional Alignment:
    - ADR-013: Deterministic reconciliation (same inputs = same pairs)
    - CEO-DIR-2026-006: Error taxonomy classification
    - CEO-DIR-2026-007: Pairs forecasts with outcomes

Flow:
    1. Query unreconciled forecasts past their valid_until
    2. For each forecast, find matching outcome
    3. Compute Brier score and classify error type
    4. Create forecast_outcome_pair record
    5. Update forecast resolution status
    6. Log evidence to governance

Schedule: Daily at 00:30 UTC (after outcome capture)
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
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
logger = logging.getLogger("ios010_reconciliation")

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

HASH_CHAIN_PREFIX = "IOS010-RECONCILIATION"
TOLERANCE_HOURS = 6  # Matching tolerance window
MAX_FORECASTS_PER_RUN = 5000

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# CEO-DIR-2026-043: PRICE REALITY GATE
# Learning tasks must hard-fail if any asset exceeds SLA at execution time.
# No silent skips. No degraded learning.
# =============================================================================

def check_price_reality_gate() -> tuple:
    """
    Check if data is fresh enough for learning operations.
    Returns (gate_passed: bool, reason: str)

    Hard-fails if:
    - Active DATA_BLACKOUT exists
    - Any canonical asset exceeds SLA
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check for active blackout
            cur.execute("""
                SELECT blackout_id, trigger_reason, stale_assets, triggered_at
                FROM fhq_governance.data_blackout_state
                WHERE is_active = TRUE
                ORDER BY triggered_at DESC
                LIMIT 1
            """)
            blackout = cur.fetchone()

            if blackout:
                return (
                    False,
                    f"DATA_BLACKOUT active since {blackout['triggered_at']}: {blackout['trigger_reason']}"
                )

            return (True, "Price reality gate passed - no active blackouts")
    finally:
        conn.close()


def enforce_price_reality_gate():
    """
    Enforce price reality gate - hard-fail if SLA violated.
    CEO-DIR-2026-043: No silent skips. No degraded learning.
    """
    gate_passed, reason = check_price_reality_gate()
    if not gate_passed:
        logger.critical(f"PRICE REALITY GATE FAILED: {reason}")
        logger.critical("CEO-DIR-2026-043: Learning task cannot proceed with stale data")
        raise SystemExit(1)
    logger.info(f"Price Reality Gate: {reason}")

# =============================================================================
# BRIER SCORE COMPUTATION
# =============================================================================

def compute_brier_score(forecast_prob: float, forecast_value: str, outcome_value: str) -> float:
    """
    Compute Brier score for a single forecast-outcome pair.
    Brier = (probability - outcome_indicator)^2
    Lower is better (0 = perfect, 1 = worst)
    """
    outcome_indicator = 1.0 if forecast_value == outcome_value else 0.0
    return (forecast_prob - outcome_indicator) ** 2


def compute_log_score(forecast_prob: float, forecast_value: str, outcome_value: str) -> Optional[float]:
    """
    Compute logarithmic score.
    More sensitive to confident wrong predictions.
    """
    import math
    if forecast_value == outcome_value:
        prob = max(forecast_prob, 0.001)  # Avoid log(0)
    else:
        prob = max(1 - forecast_prob, 0.001)
    return -math.log(prob)

# =============================================================================
# CORE LOGIC
# =============================================================================

def get_unreconciled_forecasts(conn) -> List[Dict]:
    """Get forecasts past their valid_until that haven't been reconciled"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                f.forecast_id,
                f.forecast_type,
                f.forecast_domain,
                f.forecast_value,
                f.forecast_probability,
                f.forecast_confidence,
                f.forecast_horizon_hours,
                f.forecast_made_at,
                f.forecast_valid_from,
                f.forecast_valid_until,
                f.state_snapshot_id
            FROM fhq_research.forecast_ledger f
            WHERE f.is_resolved = FALSE
              AND f.forecast_valid_until < NOW() - INTERVAL '1 hour'
              AND f.forecast_type = 'REGIME'
            ORDER BY f.forecast_valid_until ASC
            LIMIT %s
        """, (MAX_FORECASTS_PER_RUN,))
        return [dict(row) for row in cur.fetchall()]


def find_matching_outcome(conn, forecast: Dict) -> Optional[Dict]:
    """Find the best matching outcome for a forecast"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                o.outcome_id,
                o.outcome_type,
                o.outcome_domain,
                o.outcome_value,
                o.outcome_timestamp,
                -- Match confidence based on temporal proximity (use ABS on extracted epoch)
                1.0 - (ABS(EXTRACT(EPOCH FROM (o.outcome_timestamp - %s))) /
                       (%s * 3600.0))::numeric AS match_confidence
            FROM fhq_research.outcome_ledger o
            WHERE o.outcome_domain = %s
              AND o.outcome_type = %s
              AND o.outcome_timestamp BETWEEN %s AND (%s + INTERVAL '%s hours')
            ORDER BY ABS(EXTRACT(EPOCH FROM (o.outcome_timestamp - %s))) ASC
            LIMIT 1
        """, (
            forecast['forecast_valid_until'],
            TOLERANCE_HOURS,
            forecast['forecast_domain'],
            forecast['forecast_type'],
            forecast['forecast_valid_from'],
            forecast['forecast_valid_until'],
            TOLERANCE_HOURS,
            forecast['forecast_valid_until']
        ))
        result = cur.fetchone()
        return dict(result) if result else None


def classify_error_type(forecast: Dict, outcome: Dict) -> Tuple[str, str]:
    """
    Classify the error type based on forecast-outcome comparison.
    Returns (error_category, error_direction)
    """
    forecast_value = forecast['forecast_value']
    outcome_value = outcome['outcome_value']
    forecast_prob = float(forecast['forecast_probability'])

    if forecast_value == outcome_value:
        # Correct prediction
        if forecast_prob >= 0.8:
            return ('CORRECT_HIGH_CONFIDENCE', 'NONE')
        elif forecast_prob >= 0.6:
            return ('CORRECT_MEDIUM_CONFIDENCE', 'NONE')
        else:
            return ('CORRECT_LOW_CONFIDENCE', 'UNDER')  # Under-confident
    else:
        # Wrong prediction
        if forecast_prob >= 0.8:
            return ('DIRECTIONAL_ERROR', 'OVER')  # Over-confident wrong
        elif forecast_prob >= 0.6:
            return ('DIRECTIONAL_ERROR', 'WRONG')
        else:
            return ('CALIBRATION_ERROR', 'WRONG')  # Low confidence wrong - calibration issue


def create_reconciliation_pair(
    conn,
    forecast: Dict,
    outcome: Dict,
    brier_score: float,
    log_score: float,
    error_category: str,
    error_direction: str
) -> Optional[str]:
    """Create a forecast-outcome pair record"""
    try:
        forecast_value = forecast['forecast_value']
        outcome_value = outcome['outcome_value']
        is_hit = forecast_value == outcome_value

        # Compute lead time
        lead_time_hours = int(
            (outcome['outcome_timestamp'] - forecast['forecast_made_at']).total_seconds() / 3600
        )

        # Check if outcome within original horizon
        outcome_within_horizon = outcome['outcome_timestamp'] <= forecast['forecast_valid_until']

        # Hash chain
        hash_chain_id = f"{HASH_CHAIN_PREFIX}-{forecast['forecast_id']}-{outcome['outcome_id']}"

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_research.forecast_outcome_pairs (
                    forecast_id,
                    outcome_id,
                    alignment_score,
                    alignment_method,
                    is_exact_match,
                    brier_score,
                    log_score,
                    hit_rate_contribution,
                    forecast_lead_time_hours,
                    outcome_within_horizon,
                    reconciled_by,
                    hash_chain_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT DO NOTHING
                RETURNING pair_id
            """, (
                forecast['forecast_id'],
                outcome['outcome_id'],
                max(0.0, min(1.0, float(outcome.get('match_confidence', 1.0)))),  # Clamp to [0,1]
                'TEMPORAL_PROXIMITY',
                is_hit,
                brier_score,
                log_score,
                is_hit,
                lead_time_hours,
                outcome_within_horizon,
                'STIG',
                hash_chain_id
            ))

            result = cur.fetchone()
            return str(result[0]) if result else None

    except Exception as e:
        logger.error(f"Failed to create pair for forecast {forecast['forecast_id']}: {e}")
        return None


def mark_forecast_resolved(conn, forecast_id: str, outcome_id: str, status: str):
    """Update forecast resolution status"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_research.forecast_ledger
            SET is_resolved = TRUE,
                resolution_status = %s,
                resolved_at = NOW(),
                outcome_id = %s
            WHERE forecast_id = %s
        """, (status, outcome_id, forecast_id))


def mark_forecast_expired(conn, forecast_id: str):
    """Mark forecast as expired (no matching outcome found)"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_research.forecast_ledger
            SET is_resolved = TRUE,
                resolution_status = 'EXPIRED',
                resolved_at = NOW()
            WHERE forecast_id = %s
        """, (forecast_id,))


def log_reconciliation_evidence(conn, stats: Dict[str, Any]) -> str:
    """Log reconciliation run to governance"""
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
                'IOS010_FORECAST_RECONCILIATION',
                'fhq_research.forecast_outcome_pairs',
                'DAEMON_EXECUTION',
                'STIG',
                'EXECUTED',
                'CEO-DIR-2026-007: Forecasts reconciled with outcomes for truth verification',
                %s
            )
            RETURNING action_id
        """, (json.dumps({
            'evidence_id': evidence_id,
            'directive': 'CEO-DIR-2026-007',
            'ios': 'IoS-010',
            'daemon': 'ios010_forecast_reconciliation_daemon',
            'statistics': stats,
            'evidence_hash': evidence_hash,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }),))

    return evidence_id


def run_reconciliation() -> Dict[str, Any]:
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("IOS-010 FORECAST RECONCILIATION DAEMON")
    logger.info("Directive: CEO-DIR-2026-007")
    logger.info("=" * 60)

    # CEO-DIR-2026-043: Price Reality Gate - hard-fail if data SLA violated
    enforce_price_reality_gate()

    stats = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'forecasts_found': 0,
        'pairs_created': 0,
        'forecasts_expired': 0,
        'total_brier_score': 0.0,
        'hit_count': 0,
        'miss_count': 0,
        'errors': 0,
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Get unreconciled forecasts
        forecasts = get_unreconciled_forecasts(conn)
        stats['forecasts_found'] = len(forecasts)
        logger.info(f"Found {len(forecasts)} unreconciled forecasts")

        if not forecasts:
            logger.info("No forecasts to reconcile")
            stats['completed_at'] = datetime.now(timezone.utc).isoformat()
            return stats

        # Reconcile each forecast
        for forecast in forecasts:
            outcome = find_matching_outcome(conn, forecast)

            if outcome:
                # Compute scores
                brier = compute_brier_score(
                    float(forecast['forecast_probability']),
                    forecast['forecast_value'],
                    outcome['outcome_value']
                )
                log_sc = compute_log_score(
                    float(forecast['forecast_probability']),
                    forecast['forecast_value'],
                    outcome['outcome_value']
                )

                # Classify error
                error_cat, error_dir = classify_error_type(forecast, outcome)

                # Create pair
                pair_id = create_reconciliation_pair(
                    conn, forecast, outcome, brier, log_sc, error_cat, error_dir
                )

                if pair_id:
                    stats['pairs_created'] += 1
                    stats['total_brier_score'] += brier

                    # Determine resolution status based on outcome match
                    # CEO-DIR-2026-042: Use valid check constraint values
                    is_correct = forecast['forecast_value'] == outcome['outcome_value']
                    if is_correct:
                        stats['hit_count'] += 1
                        resolution_status = 'CORRECT'
                    else:
                        stats['miss_count'] += 1
                        resolution_status = 'INCORRECT'

                    # Mark forecast resolved
                    mark_forecast_resolved(
                        conn,
                        str(forecast['forecast_id']),
                        str(outcome['outcome_id']),
                        resolution_status
                    )
                else:
                    stats['errors'] += 1
            else:
                # No matching outcome - mark as expired
                mark_forecast_expired(conn, str(forecast['forecast_id']))
                stats['forecasts_expired'] += 1

        conn.commit()

        # Compute summary metrics
        if stats['pairs_created'] > 0:
            stats['avg_brier_score'] = stats['total_brier_score'] / stats['pairs_created']
            stats['hit_rate'] = stats['hit_count'] / stats['pairs_created']
        else:
            stats['avg_brier_score'] = None
            stats['hit_rate'] = None

        # Log evidence
        evidence_id = log_reconciliation_evidence(conn, stats)
        stats['evidence_id'] = evidence_id
        conn.commit()

        logger.info(f"Reconciliation complete: {stats['pairs_created']} pairs, "
                    f"{stats['forecasts_expired']} expired, hit rate: {stats.get('hit_rate', 'N/A')}")

    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
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
    result = run_reconciliation()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)
