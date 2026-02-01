#!/usr/bin/env python3
"""
IOS-010 SKILL METRICS AGGREGATOR
================================
CEO Directive: CEO-DIR-2026-007
Classification: STRATEGIC-FUNDAMENTAL (Class A+)
IoS Module: IoS-010 Prediction Ledger Engine

Purpose:
    Aggregates reconciliation results into rolling skill metrics.
    Outputs calibration, timing, regime, and suppression performance.
    CRITICALLY: Computes Suppression Regret Index per CEO-DIR-2026-007 Section 5.2.

Constitutional Alignment:
    - ADR-013: Skill metrics are canonical truth about forecasting quality
    - CEO-DIR-2026-006: Skill must show temporal structure (not noise)
    - CEO-DIR-2026-007 Section 5.2: "The cost of conservatism must be measurable"

Flow:
    1. Query forecast_outcome_pairs for period
    2. Compute aggregate Brier score, calibration, hit rate
    3. Compute Suppression Regret Index via database function
    4. Store metrics in forecast_skill_metrics
    5. Log evidence to governance

Schedule: Weekly on Sunday 01:00 UTC
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
logger = logging.getLogger("ios010_skill_metrics")

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

HASH_CHAIN_PREFIX = "IOS010-SKILL"
DEFAULT_LOOKBACK_DAYS = 7  # Weekly aggregation

# Phase 2: Drift Detection Configuration
DRIFT_THRESHOLD_PCT = 5.0  # Trigger recalibration if Brier degrades by >5%
CALIBRATION_ERROR_THRESHOLD = 0.15  # Alert if calibration error exceeds 15%
BASELINE_LOOKBACK_DAYS = 30  # Compare against 30-day baseline

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
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT blackout_id, trigger_reason, triggered_at
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
    """Enforce price reality gate - hard-fail if SLA violated."""
    gate_passed, reason = check_price_reality_gate()
    if not gate_passed:
        logger.critical(f"PRICE REALITY GATE FAILED: {reason}")
        logger.critical("CEO-DIR-2026-043: Learning task cannot proceed with stale data")
        raise SystemExit(1)
    logger.info(f"Price Reality Gate: {reason}")

# =============================================================================
# SKILL METRICS COMPUTATION
# =============================================================================

def compute_aggregate_metrics(conn, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
    """Compute aggregate skill metrics for a period"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS total_pairs,
                COUNT(*) FILTER (WHERE is_exact_match = TRUE) AS hit_count,
                AVG(brier_score) AS avg_brier,
                STDDEV(brier_score) AS std_brier,
                AVG(log_score) AS avg_log_score,
                STDDEV(log_score) AS std_log_score,
                AVG(CASE WHEN is_exact_match THEN 1.0 ELSE 0.0 END) AS hit_rate,
                COUNT(*) FILTER (WHERE outcome_within_horizon = TRUE) AS within_horizon_count
            FROM fhq_research.forecast_outcome_pairs
            WHERE reconciled_at BETWEEN %s AND %s
        """, (period_start, period_end))
        return dict(cur.fetchone())


def compute_calibration_curve(conn, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
    """
    Compute calibration curve - predicted probabilities vs observed frequencies.
    Buckets predictions by confidence level and compares to hit rate.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH bucketed AS (
                SELECT
                    CASE
                        WHEN f.forecast_probability < 0.3 THEN '0.0-0.3'
                        WHEN f.forecast_probability < 0.5 THEN '0.3-0.5'
                        WHEN f.forecast_probability < 0.7 THEN '0.5-0.7'
                        WHEN f.forecast_probability < 0.9 THEN '0.7-0.9'
                        ELSE '0.9-1.0'
                    END AS prob_bucket,
                    f.forecast_probability,
                    fop.is_exact_match
                FROM fhq_research.forecast_outcome_pairs fop
                JOIN fhq_research.forecast_ledger f ON f.forecast_id = fop.forecast_id
                WHERE fop.reconciled_at BETWEEN %s AND %s
            )
            SELECT
                prob_bucket,
                COUNT(*) AS count,
                AVG(forecast_probability) AS avg_predicted,
                AVG(CASE WHEN is_exact_match THEN 1.0 ELSE 0.0 END) AS observed_rate,
                ABS(AVG(forecast_probability) - AVG(CASE WHEN is_exact_match THEN 1.0 ELSE 0.0 END)) AS calibration_gap
            FROM bucketed
            GROUP BY prob_bucket
            ORDER BY prob_bucket
        """, (period_start, period_end))

        buckets = [dict(row) for row in cur.fetchall()]

        # Compute overall calibration error
        total_error = sum(float(b['calibration_gap'] or 0) * int(b['count']) for b in buckets)
        total_count = sum(int(b['count']) for b in buckets)
        avg_calibration_error = total_error / total_count if total_count > 0 else None

        return {
            'buckets': buckets,
            'avg_calibration_error': avg_calibration_error
        }


def compute_regime_breakdown(conn, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
    """Compute metrics broken down by regime"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                f.forecast_value AS regime,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE fop.is_exact_match) AS hits,
                AVG(fop.brier_score) AS avg_brier,
                AVG(CASE WHEN fop.is_exact_match THEN 1.0 ELSE 0.0 END) AS hit_rate
            FROM fhq_research.forecast_outcome_pairs fop
            JOIN fhq_research.forecast_ledger f ON f.forecast_id = fop.forecast_id
            WHERE fop.reconciled_at BETWEEN %s AND %s
            GROUP BY f.forecast_value
            ORDER BY total DESC
        """, (period_start, period_end))
        return {row['regime']: dict(row) for row in cur.fetchall()}


def compute_suppression_regret(conn, period_start: datetime, period_end: datetime) -> Optional[str]:
    """
    Compute Suppression Regret Index using database function.
    CEO-DIR-2026-007 Section 5.2: "The cost of conservatism must be measurable"
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fhq_governance.compute_suppression_regret(%s, %s)
        """, (period_start, period_end))
        result = cur.fetchone()
        return str(result[0]) if result and result[0] else None


def get_suppression_regret_details(conn, regret_id: str) -> Optional[Dict]:
    """Get details of a suppression regret computation"""
    if not regret_id:
        return None

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                total_suppressions,
                correct_suppressions,
                regrettable_suppressions,
                suppression_regret_rate,
                suppression_wisdom_rate,
                regret_by_regime,
                regret_by_asset
            FROM fhq_governance.suppression_regret_index
            WHERE regret_id = %s
        """, (regret_id,))
        result = cur.fetchone()
        return dict(result) if result else None


# =============================================================================
# PHASE 2: DRIFT DETECTION AND RECALIBRATION TRIGGERS
# CEO-DIR-2026-META-ANALYSIS
# =============================================================================

def get_baseline_metrics(conn, lookback_days: int = BASELINE_LOOKBACK_DAYS) -> Optional[Dict]:
    """
    Get baseline metrics from the last N days for drift comparison.
    Returns the most recent stable baseline.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                AVG(brier_score_mean) as baseline_brier,
                AVG(calibration_error) as baseline_calibration_error,
                AVG(hit_rate) as baseline_hit_rate,
                COUNT(*) as sample_count,
                MIN(computed_at) as period_start,
                MAX(computed_at) as period_end
            FROM fhq_research.forecast_skill_metrics
            WHERE metric_scope = 'GLOBAL'
              AND computed_at >= NOW() - INTERVAL '%s days'
              AND brier_score_mean IS NOT NULL
        """, (lookback_days,))
        result = cur.fetchone()

        if result and result['sample_count'] > 0:
            return dict(result)
        return None


def detect_calibration_drift(
    conn,
    current_brier: float,
    current_calibration_error: float,
    baseline: Optional[Dict]
) -> Dict[str, Any]:
    """
    Detect if calibration has drifted significantly from baseline.

    Returns drift analysis including:
    - drift_detected: bool
    - drift_type: 'BRIER_DEGRADATION', 'CALIBRATION_DRIFT', 'NONE'
    - drift_magnitude: float (percentage change)
    - should_recalibrate: bool
    """
    drift_result = {
        'drift_detected': False,
        'drift_type': 'NONE',
        'drift_magnitude': 0.0,
        'drift_direction': None,
        'should_recalibrate': False,
        'alerts': []
    }

    if not baseline or baseline['baseline_brier'] is None:
        logger.info("No baseline available for drift detection")
        return drift_result

    baseline_brier = float(baseline['baseline_brier'])
    baseline_cal_error = float(baseline['baseline_calibration_error']) if baseline['baseline_calibration_error'] else 0.0

    # Check Brier score degradation
    if baseline_brier > 0:
        brier_change_pct = ((current_brier - baseline_brier) / baseline_brier) * 100

        if brier_change_pct > DRIFT_THRESHOLD_PCT:
            drift_result['drift_detected'] = True
            drift_result['drift_type'] = 'BRIER_DEGRADATION'
            drift_result['drift_magnitude'] = brier_change_pct
            drift_result['drift_direction'] = 'WORSE'
            drift_result['should_recalibrate'] = True
            drift_result['alerts'].append({
                'type': 'BRIER_DRIFT',
                'severity': 'WARNING',
                'message': f"Brier score degraded by {brier_change_pct:.1f}% (baseline: {baseline_brier:.4f}, current: {current_brier:.4f})"
            })
            logger.warning(f"DRIFT DETECTED: Brier degraded by {brier_change_pct:.1f}%")

        elif brier_change_pct < -DRIFT_THRESHOLD_PCT:
            # Improvement - good but note it
            drift_result['drift_direction'] = 'BETTER'
            drift_result['drift_magnitude'] = abs(brier_change_pct)
            logger.info(f"Brier improved by {abs(brier_change_pct):.1f}%")

    # Check calibration error threshold
    if current_calibration_error and current_calibration_error > CALIBRATION_ERROR_THRESHOLD:
        drift_result['drift_detected'] = True
        if drift_result['drift_type'] == 'NONE':
            drift_result['drift_type'] = 'CALIBRATION_DRIFT'
        drift_result['should_recalibrate'] = True
        drift_result['alerts'].append({
            'type': 'CALIBRATION_ERROR',
            'severity': 'WARNING',
            'message': f"Calibration error {current_calibration_error:.4f} exceeds threshold {CALIBRATION_ERROR_THRESHOLD}"
        })
        logger.warning(f"CALIBRATION ERROR: {current_calibration_error:.4f} exceeds {CALIBRATION_ERROR_THRESHOLD}")

    return drift_result


def trigger_recalibration(conn, drift_result: Dict[str, Any]) -> Optional[str]:
    """
    Trigger recalibration when drift is detected.
    Creates a recalibration request in the governance table.
    """
    if not drift_result['should_recalibrate']:
        return None

    request_id = str(uuid.uuid4())

    with conn.cursor() as cur:
        # Log recalibration trigger
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
                'RECALIBRATION_TRIGGER',
                'fhq_governance.probability_calibration_models',
                'DRIFT_DETECTION',
                'IOS010_SKILL_AGGREGATOR',
                'PENDING',
                'CEO-DIR-2026-META-ANALYSIS Phase 2: Automatic recalibration triggered due to drift detection',
                %s
            )
            RETURNING action_id
        """, (json.dumps({
            'request_id': request_id,
            'drift_result': drift_result,
            'triggered_at': datetime.now(timezone.utc).isoformat(),
            'threshold_config': {
                'drift_threshold_pct': DRIFT_THRESHOLD_PCT,
                'calibration_error_threshold': CALIBRATION_ERROR_THRESHOLD
            }
        }, default=str),))

        action_id = cur.fetchone()[0]

    logger.info(f"Recalibration triggered: request_id={request_id}, action_id={action_id}")
    return request_id


def create_drift_alerts(conn, drift_result: Dict[str, Any]) -> int:
    """Create control room alerts for detected drift."""
    alerts_created = 0

    for alert in drift_result.get('alerts', []):
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_ops.control_room_alerts (
                    alert_type,
                    alert_severity,
                    alert_message,
                    alert_source,
                    is_resolved,
                    auto_generated
                ) VALUES (
                    %s,
                    %s,
                    %s,
                    'IOS010_DRIFT_DETECTION',
                    false,
                    true
                )
            """, (
                alert['type'],
                alert['severity'],
                alert['message']
            ))
            alerts_created += 1

    return alerts_created


def store_skill_metrics(
    conn,
    period_start: datetime,
    period_end: datetime,
    metrics: Dict[str, Any],
    calibration: Dict[str, Any],
    regime_breakdown: Dict[str, Any],
    suppression_regret: Optional[Dict]
) -> str:
    """Store computed skill metrics"""
    hash_chain_id = f"{HASH_CHAIN_PREFIX}-{period_start.strftime('%Y%m%d')}-{period_end.strftime('%Y%m%d')}"

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_research.forecast_skill_metrics (
                metric_scope,
                scope_value,
                period_start,
                period_end,
                forecast_count,
                resolved_count,
                brier_score_mean,
                brier_score_std,
                brier_skill_score,
                log_score_mean,
                log_score_std,
                hit_rate,
                hit_rate_confidence_low,
                hit_rate_confidence_high,
                calibration_error,
                overconfidence_ratio,
                reliability_diagram,
                drift_detected,
                drift_magnitude,
                drift_direction,
                computed_by,
                hash_chain_id
            ) VALUES (
                'GLOBAL',
                'ALL_ASSETS',
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s,
                FALSE, NULL, NULL,
                'STIG',
                %s
            )
            RETURNING metric_id
        """, (
            period_start, period_end,
            metrics.get('total_pairs', 0),
            metrics.get('total_pairs', 0),
            metrics.get('avg_brier'),
            metrics.get('std_brier'),
            None,  # brier_skill_score - computed separately
            metrics.get('avg_log_score'),
            metrics.get('std_log_score'),
            metrics.get('hit_rate'),
            None, None,  # confidence intervals
            calibration.get('avg_calibration_error'),
            None,  # overconfidence_ratio
            # CEO-DIR-2026-042: Use default=str to handle Decimal serialization
            json.dumps({
                'calibration_buckets': calibration.get('buckets', []),
                'regime_breakdown': regime_breakdown,
                'suppression_regret': suppression_regret
            }, default=str),
            hash_chain_id
        ))

        result = cur.fetchone()
        return str(result[0]) if result else None


def log_skill_evidence(conn, stats: Dict[str, Any]) -> str:
    """Log skill metrics computation to governance"""
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
                'IOS010_SKILL_METRICS_AGGREGATION',
                'fhq_research.forecast_skill_metrics',
                'DAEMON_EXECUTION',
                'STIG',
                'EXECUTED',
                'CEO-DIR-2026-007: Skill metrics aggregated including Suppression Regret Index',
                %s
            )
            RETURNING action_id
        """,
        # CEO-DIR-2026-042: Use default=str to handle Decimal serialization
        (json.dumps({
            'evidence_id': evidence_id,
            'directive': 'CEO-DIR-2026-007',
            'ios': 'IoS-010',
            'daemon': 'ios010_skill_metrics_aggregator',
            'statistics': stats,
            'evidence_hash': evidence_hash,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, default=str),))

    return evidence_id


def run_skill_aggregation(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> Dict[str, Any]:
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("IOS-010 SKILL METRICS AGGREGATOR")
    logger.info("Directive: CEO-DIR-2026-007")
    logger.info("=" * 60)

    # CEO-DIR-2026-043: Price Reality Gate - hard-fail if data SLA violated
    enforce_price_reality_gate()

    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=lookback_days)

    stats = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        # Compute aggregate metrics
        logger.info(f"Computing metrics for period {period_start} to {period_end}")
        metrics = compute_aggregate_metrics(conn, period_start, period_end)
        stats['aggregate_metrics'] = metrics
        logger.info(f"Aggregate: {metrics['total_pairs']} pairs, "
                    f"hit rate: {metrics['hit_rate']:.3f}" if metrics['hit_rate'] else "No pairs")

        if not metrics['total_pairs']:
            logger.warning("No reconciliation pairs found for period")
            stats['status'] = 'NO_DATA'
            return stats

        # Compute calibration
        logger.info("Computing calibration curve")
        calibration = compute_calibration_curve(conn, period_start, period_end)
        stats['calibration'] = calibration

        # Compute regime breakdown
        logger.info("Computing regime breakdown")
        regime_breakdown = compute_regime_breakdown(conn, period_start, period_end)
        stats['regime_breakdown'] = regime_breakdown

        # Compute Suppression Regret Index
        logger.info("Computing Suppression Regret Index (CEO-DIR-2026-007 Section 5.2)")
        regret_id = compute_suppression_regret(conn, period_start, period_end)
        suppression_regret = get_suppression_regret_details(conn, regret_id) if regret_id else None
        stats['suppression_regret_id'] = regret_id
        stats['suppression_regret'] = suppression_regret

        if suppression_regret:
            logger.info(f"Suppression Regret Index: {suppression_regret['suppression_regret_rate']:.3f} "
                        f"(Wisdom: {suppression_regret['suppression_wisdom_rate']:.3f})")

        # Phase 2: Drift Detection
        logger.info("Running drift detection (CEO-DIR-2026-META-ANALYSIS Phase 2)")
        baseline = get_baseline_metrics(conn, BASELINE_LOOKBACK_DAYS)
        current_brier = float(metrics['avg_brier']) if metrics.get('avg_brier') else 0.0
        current_cal_error = float(calibration.get('avg_calibration_error', 0)) if calibration.get('avg_calibration_error') else 0.0

        drift_result = detect_calibration_drift(conn, current_brier, current_cal_error, baseline)
        stats['drift_detection'] = drift_result

        if drift_result['drift_detected']:
            # Create alerts
            alerts_created = create_drift_alerts(conn, drift_result)
            stats['drift_alerts_created'] = alerts_created

            # Trigger recalibration if needed
            if drift_result['should_recalibrate']:
                recal_request_id = trigger_recalibration(conn, drift_result)
                stats['recalibration_request_id'] = recal_request_id
                logger.info(f"Recalibration request created: {recal_request_id}")
        else:
            logger.info("No drift detected - calibration stable")

        # Store metrics
        logger.info("Storing skill metrics")
        metric_id = store_skill_metrics(
            conn, period_start, period_end,
            metrics, calibration, regime_breakdown, suppression_regret
        )
        stats['metric_id'] = metric_id
        conn.commit()

        # Log evidence
        evidence_id = log_skill_evidence(conn, stats)
        stats['evidence_id'] = evidence_id
        conn.commit()

        logger.info(f"Skill aggregation complete: metric_id={metric_id}")

    except Exception as e:
        logger.error(f"Skill aggregation failed: {e}")
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
    import argparse

    parser = argparse.ArgumentParser(description="IoS-010 Skill Metrics Aggregator")
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help="Number of days to look back")
    args = parser.parse_args()

    result = run_skill_aggregation(lookback_days=args.days)
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result['status'] in ('SUCCESS', 'NO_DATA') else 1)
