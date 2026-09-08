"""
CEO-DIR-2026-025: Phase 3 Defensive Activation - Daily Calibration Daemon

Authority: CEO Directive 2026-025
Classification: DEFENSIVE MODE ONLY
Execution Time: 00:05 UTC daily

This daemon performs:
1. Learning classification updates
2. Brier score computation
3. Belief-outcome reconciliation
4. Audit record generation

EXPLICIT PROHIBITIONS (enforced):
- NO parameter updates
- NO confidence threshold adjustments
- NO decision logic modification
- NO adaptive learning
- NO execution influence
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [PHASE3-CALIBRATION] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/phase3_calibration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Governance constants
DIRECTIVE_ID = "CEO-DIR-2026-025"
DAEMON_VERSION = "1.0.0"
EXECUTION_MODE = "DEFENSIVE_ONLY"

# Calibration thresholds (READ-ONLY - not to be modified by this daemon)
BRIER_WARNING_THRESHOLD = 0.30
OVERCONFIDENCE_THRESHOLD = 0.90


def get_db_connection():
    """Get database connection from environment."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        database=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


def json_serializer(obj):
    """Custom JSON serializer for Decimal and datetime types."""
    from decimal import Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def generate_execution_hash(data: Dict[str, Any]) -> str:
    """Generate deterministic hash for audit trail."""
    content = json.dumps(data, sort_keys=True, default=json_serializer)
    return hashlib.sha256(content.encode()).hexdigest()


def log_governance_action(conn, action_type: str, details: Dict[str, Any]) -> str:
    """Log governance action with cryptographic signature."""
    execution_hash = generate_execution_hash(details)

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log (
                action_id, action_type, action_target, action_target_type,
                initiated_by, initiated_at, decision, decision_rationale,
                metadata, hash_chain_id, agent_id, timestamp
            ) VALUES (
                gen_random_uuid(), %s, 'fhq_governance.epistemic_suppression_ledger', 'CALIBRATION',
                'STIG_PHASE3_DAEMON', NOW(), 'EXECUTED', 'CEO-DIR-2026-025 Phase 3 Defensive Calibration',
                %s, %s, 'STIG', NOW()
            ) RETURNING action_id
        """, (action_type, json.dumps(details, default=json_serializer), 'PHASE3_' + execution_hash[:32]))

        result = cur.fetchone()
        conn.commit()
        return str(result[0]) if result else None


def update_learning_classifications(conn) -> Dict[str, int]:
    """
    Update regret/wisdom classifications for unclassified decisions.
    READ-ONLY toward decision parameters.
    """
    logger.info("Starting learning classification update...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Classify decisions that have price data available
        cur.execute("""
            WITH classifiable AS (
                SELECT
                    e.suppression_id,
                    e.asset_id,
                    e.chosen_regime,
                    p1.close as price_at_decision,
                    p2.close as price_after,
                    (p2.close - p1.close) / NULLIF(p1.close, 0) * 100 as return_pct
                FROM fhq_governance.epistemic_suppression_ledger e
                JOIN fhq_market.prices p1 ON p1.canonical_id = e.asset_id
                    AND DATE(p1.timestamp) = DATE(e.suppression_timestamp)
                JOIN fhq_market.prices p2 ON p2.canonical_id = e.asset_id
                    AND DATE(p2.timestamp) = DATE(e.suppression_timestamp) + INTERVAL '1 day'
                WHERE e.regret_classification IS NULL
            )
            UPDATE fhq_governance.epistemic_suppression_ledger e
            SET
                regret_classification = CASE
                    WHEN c.chosen_regime = 'BULL' AND c.return_pct > 0.5 THEN 'WISDOM'
                    WHEN c.chosen_regime = 'BEAR' AND c.return_pct < -0.5 THEN 'WISDOM'
                    WHEN c.chosen_regime = 'NEUTRAL' AND ABS(c.return_pct) < 1.5 THEN 'WISDOM'
                    WHEN c.chosen_regime = 'BULL' AND c.return_pct < -0.5 THEN 'REGRET'
                    WHEN c.chosen_regime = 'BEAR' AND c.return_pct > 0.5 THEN 'REGRET'
                    ELSE 'UNRESOLVED'
                END,
                regret_magnitude = ABS(c.return_pct) / 100.0,
                market_outcome = c.return_pct::text || '% ' ||
                    CASE WHEN c.return_pct > 0 THEN 'gain' ELSE 'loss' END,
                regret_computed_at = NOW(),
                reviewed_by = 'STIG_PHASE3_DAEMON'
            FROM classifiable c
            WHERE e.suppression_id = c.suppression_id
            RETURNING e.regret_classification
        """)

        results = cur.fetchall()
        conn.commit()

        # Count classifications
        counts = {'WISDOM': 0, 'REGRET': 0, 'UNRESOLVED': 0}
        for row in results:
            classification = row['regret_classification']
            if classification in counts:
                counts[classification] += 1

        logger.info(f"Classified {len(results)} decisions: {counts}")
        return counts


def update_brier_scores(conn) -> Dict[str, Any]:
    """
    Compute Brier scores for new beliefs with outcomes.
    READ-ONLY toward model parameters.
    """
    logger.info("Starting Brier score computation...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH belief_outcomes AS (
                SELECT
                    b.belief_id,
                    b.asset_id,
                    b.dominant_regime,
                    b.belief_confidence,
                    b.belief_timestamp,
                    p1.close as price_at_belief,
                    p2.close as price_after,
                    CASE
                        WHEN (p2.close - p1.close) / NULLIF(p1.close, 0) > 0.005 THEN 'BULL'
                        WHEN (p2.close - p1.close) / NULLIF(p1.close, 0) < -0.005 THEN 'BEAR'
                        ELSE 'NEUTRAL'
                    END as actual_regime
                FROM fhq_perception.model_belief_state b
                JOIN fhq_market.prices p1 ON p1.canonical_id = b.asset_id
                    AND DATE(p1.timestamp) = DATE(b.belief_timestamp)
                JOIN fhq_market.prices p2 ON p2.canonical_id = b.asset_id
                    AND DATE(p2.timestamp) = DATE(b.belief_timestamp) + INTERVAL '1 day'
                WHERE b.created_at >= NOW() - INTERVAL '2 days'
                  AND b.dominant_regime IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM fhq_governance.brier_score_ledger bsl
                      WHERE bsl.belief_id = b.belief_id
                  )
            )
            INSERT INTO fhq_governance.brier_score_ledger (
                score_id, belief_id, forecast_type, asset_id, regime, asset_class,
                forecast_probability, actual_outcome, squared_error,
                forecast_timestamp, outcome_timestamp, forecast_horizon_hours,
                generated_by, created_at
            )
            SELECT
                gen_random_uuid(),
                belief_id,
                'REGIME_CLASSIFICATION',
                asset_id,
                dominant_regime,
                CASE
                    WHEN asset_id LIKE '%-USD' THEN 'CRYPTO'
                    WHEN asset_id LIKE '%.OL' THEN 'EQUITY_OSLO'
                    ELSE 'EQUITY_US'
                END,
                belief_confidence,
                dominant_regime = actual_regime,
                POWER(belief_confidence - CASE WHEN dominant_regime = actual_regime THEN 1.0 ELSE 0.0 END, 2),
                belief_timestamp,
                belief_timestamp + INTERVAL '24 hours',
                24,
                'STIG_PHASE3_DAEMON',
                NOW()
            FROM belief_outcomes
            RETURNING score_id, squared_error, actual_outcome
        """)

        results = cur.fetchall()
        conn.commit()

        if results:
            avg_brier = sum(float(r['squared_error']) for r in results) / len(results)
            correct = sum(1 for r in results if r['actual_outcome'])
            accuracy = correct / len(results) * 100
        else:
            avg_brier = None
            accuracy = None

        stats = {
            'new_scores': len(results),
            'avg_brier': round(avg_brier, 4) if avg_brier else None,
            'accuracy_pct': round(accuracy, 1) if accuracy else None
        }

        logger.info(f"Computed {len(results)} new Brier scores: avg={avg_brier}, accuracy={accuracy}%")
        return stats


def reconcile_forecast_outcomes(conn) -> Dict[str, Any]:
    """
    Link forecasts to market outcomes.
    READ-ONLY toward forecast parameters.
    """
    logger.info("Starting forecast-outcome reconciliation...")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Create outcomes from price data
        cur.execute("""
            WITH price_outcomes AS (
                SELECT
                    p1.canonical_id as asset_id,
                    DATE(p1.timestamp) as outcome_date,
                    p1.close as price_start,
                    p2.close as price_end,
                    CASE
                        WHEN p2.close > p1.close * 1.005 THEN 'BULL'
                        WHEN p2.close < p1.close * 0.995 THEN 'BEAR'
                        ELSE 'NEUTRAL'
                    END as regime_outcome,
                    p2.timestamp as outcome_timestamp
                FROM fhq_market.prices p1
                JOIN fhq_market.prices p2 ON p2.canonical_id = p1.canonical_id
                    AND DATE(p2.timestamp) = DATE(p1.timestamp) + INTERVAL '1 day'
                WHERE p1.timestamp >= NOW() - INTERVAL '2 days'
            )
            INSERT INTO fhq_research.outcome_ledger (
                outcome_id, outcome_type, outcome_domain, outcome_value, outcome_timestamp,
                evidence_source, evidence_data, content_hash, hash_chain_id, created_by, created_at
            )
            SELECT
                gen_random_uuid(), 'REGIME', asset_id, regime_outcome, outcome_timestamp,
                'fhq_market.prices',
                jsonb_build_object('price_start', price_start, 'price_end', price_end),
                md5(asset_id || outcome_date::text || regime_outcome || NOW()::text),
                'PHASE3_DAEMON_' || md5(asset_id || outcome_date::text),
                'STIG_PHASE3_DAEMON', NOW()
            FROM price_outcomes po
            WHERE NOT EXISTS (
                SELECT 1 FROM fhq_research.outcome_ledger ol
                WHERE ol.outcome_domain = po.asset_id
                  AND DATE(ol.outcome_timestamp) = DATE(po.outcome_timestamp)
                  AND ol.outcome_type = 'REGIME'
            )
            ON CONFLICT (content_hash) DO NOTHING
            RETURNING outcome_id
        """)
        outcomes_created = len(cur.fetchall())

        # Link forecasts to outcomes
        cur.execute("""
            WITH matchable AS (
                SELECT
                    f.forecast_id, f.forecast_value, f.forecast_confidence,
                    f.forecast_horizon_hours, f.hash_chain_id as forecast_hash,
                    o.outcome_id, o.outcome_value, o.hash_chain_id as outcome_hash
                FROM fhq_research.forecast_ledger f
                JOIN fhq_research.outcome_ledger o
                    ON o.outcome_domain = f.forecast_domain
                    AND DATE(o.outcome_timestamp) = DATE(f.forecast_made_at) + INTERVAL '1 day'
                    AND o.outcome_type = 'REGIME'
                WHERE f.forecast_made_at >= NOW() - INTERVAL '2 days'
                  AND f.is_resolved = false
                LIMIT 200
            )
            INSERT INTO fhq_research.forecast_outcome_pairs (
                pair_id, forecast_id, outcome_id, alignment_score, alignment_method,
                is_exact_match, brier_score, hit_rate_contribution, forecast_lead_time_hours,
                outcome_within_horizon, reconciled_at, reconciled_by, hash_chain_id
            )
            SELECT
                gen_random_uuid(), forecast_id, outcome_id,
                CASE WHEN forecast_value = outcome_value THEN 1.0
                     WHEN forecast_value = 'NEUTRAL' OR outcome_value = 'NEUTRAL' THEN 0.5
                     ELSE 0.0 END,
                'PRICE_REGIME_MATCH', forecast_value = outcome_value,
                POWER(COALESCE(forecast_confidence, 0.5) -
                      CASE WHEN forecast_value = outcome_value THEN 1.0 ELSE 0.0 END, 2),
                forecast_value = outcome_value,
                COALESCE(forecast_horizon_hours, 24), true, NOW(),
                'STIG_PHASE3_DAEMON',
                'PAIR_' || LEFT(forecast_hash, 20) || '_' || LEFT(outcome_hash, 20)
            FROM matchable m
            WHERE NOT EXISTS (
                SELECT 1 FROM fhq_research.forecast_outcome_pairs fop
                WHERE fop.forecast_id = m.forecast_id
            )
            RETURNING pair_id
        """)
        pairs_created = len(cur.fetchall())

        # Mark forecasts resolved
        cur.execute("""
            UPDATE fhq_research.forecast_ledger f
            SET is_resolved = true,
                resolution_status = CASE WHEN fop.is_exact_match THEN 'CORRECT' ELSE 'INCORRECT' END,
                resolved_at = NOW(), outcome_id = fop.outcome_id
            FROM fhq_research.forecast_outcome_pairs fop
            WHERE f.forecast_id = fop.forecast_id AND f.is_resolved = false
        """)

        conn.commit()

        stats = {
            'outcomes_created': outcomes_created,
            'pairs_created': pairs_created
        }

        logger.info(f"Reconciliation complete: {outcomes_created} outcomes, {pairs_created} pairs")
        return stats


def get_calibration_status(conn) -> Dict[str, Any]:
    """Get current calibration metrics for warning evaluation."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_scores,
                ROUND(AVG(squared_error)::numeric, 4) as avg_brier,
                COUNT(*) FILTER (WHERE actual_outcome = true) as correct,
                COUNT(*) FILTER (WHERE squared_error > 0.5 AND forecast_probability > 0.9) as overconfident_wrong
            FROM fhq_governance.brier_score_ledger
            WHERE created_at >= NOW() - INTERVAL '30 days'
        """)

        result = cur.fetchone()
        return dict(result) if result else {}


def refresh_materialized_views(conn):
    """Refresh dashboard materialized views."""
    logger.info("Refreshing materialized views...")

    with conn.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW fhq_governance.weekly_learning_metrics")
        conn.commit()

    logger.info("Materialized views refreshed")


def run_daily_calibration():
    """
    Main execution function for daily calibration.
    Runs at 00:05 UTC.
    """
    start_time = datetime.now(timezone.utc)
    logger.info(f"=" * 60)
    logger.info(f"PHASE 3 CALIBRATION DAEMON - {DIRECTIVE_ID}")
    logger.info(f"Mode: {EXECUTION_MODE}")
    logger.info(f"Started: {start_time.isoformat()}")
    logger.info(f"=" * 60)

    execution_details = {
        'directive': DIRECTIVE_ID,
        'daemon_version': DAEMON_VERSION,
        'execution_mode': EXECUTION_MODE,
        'start_time': start_time.isoformat(),
        'results': {}
    }

    try:
        conn = get_db_connection()

        # Step 1: Learning classifications
        classification_results = update_learning_classifications(conn)
        execution_details['results']['classifications'] = classification_results

        # Step 2: Brier scores
        brier_results = update_brier_scores(conn)
        execution_details['results']['brier_scores'] = brier_results

        # Step 3: Forecast-outcome reconciliation
        reconciliation_results = reconcile_forecast_outcomes(conn)
        execution_details['results']['reconciliation'] = reconciliation_results

        # Step 4: Get calibration status
        calibration_status = get_calibration_status(conn)
        execution_details['results']['calibration_status'] = calibration_status

        # Step 5: Refresh views
        refresh_materialized_views(conn)

        # Step 6: Log governance action (audit hardening)
        end_time = datetime.now(timezone.utc)
        execution_details['end_time'] = end_time.isoformat()
        execution_details['duration_seconds'] = (end_time - start_time).total_seconds()
        execution_details['status'] = 'SUCCESS'

        action_id = log_governance_action(
            conn,
            'PHASE3_DAILY_CALIBRATION',
            execution_details
        )

        logger.info(f"Governance action logged: {action_id}")
        logger.info(f"Calibration status: Brier={calibration_status.get('avg_brier')}")

        # Check for calibration warning condition (VEGA mandate)
        avg_brier = calibration_status.get('avg_brier')
        if avg_brier and float(avg_brier) > BRIER_WARNING_THRESHOLD:
            logger.warning(
                f"CALIBRATION WARNING: Brier score {avg_brier} > {BRIER_WARNING_THRESHOLD}. "
                f"High-confidence decisions should be flagged."
            )

        conn.close()

        logger.info(f"=" * 60)
        logger.info(f"PHASE 3 CALIBRATION COMPLETE")
        logger.info(f"Duration: {execution_details['duration_seconds']:.2f}s")
        logger.info(f"=" * 60)

        return execution_details

    except Exception as e:
        logger.error(f"PHASE 3 CALIBRATION FAILED: {e}")
        execution_details['status'] = 'FAILED'
        execution_details['error'] = str(e)

        # Still try to log the failure
        try:
            conn = get_db_connection()
            log_governance_action(conn, 'PHASE3_CALIBRATION_FAILURE', execution_details)
            conn.close()
        except:
            pass

        raise


if __name__ == "__main__":
    result = run_daily_calibration()
    print(json.dumps(result, indent=2, default=str))
