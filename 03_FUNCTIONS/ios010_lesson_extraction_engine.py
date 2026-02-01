#!/usr/bin/env python3
"""
IOS-010 LESSON EXTRACTION ENGINE
================================
CEO Directive: CEO-DIR-2026-007
Classification: STRATEGIC-FUNDAMENTAL (Class A+)
IoS Module: IoS-010 Prediction Ledger Engine

Purpose:
    Converts reconciled truth into structured lessons.
    Writes to fhq_governance.epistemic_lessons table.

    CRITICAL: No direct policy mutation allowed (Phase 5 LOCKED).
    Lessons are observation-only until 85% reconciliation rate x 30 days.

Constitutional Alignment:
    - ADR-013: Lessons are canonical truth about learning quality
    - CEO-DIR-2026-006: Extract lessons from reconciled truth
    - CEO-DIR-2026-007 Section 5.1: Adaptive Feedback Lock

Flow:
    1. Query recent reconciliation pairs and skill metrics
    2. Identify significant patterns (calibration drift, regime errors, etc.)
    3. Generate structured lessons per error taxonomy
    4. Store in epistemic_lessons (observation only)
    5. Update suppression ledger lesson_extracted field
    6. Log evidence to governance

Schedule: Weekly on Sunday 02:00 UTC (after skill metrics)
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
logger = logging.getLogger("ios010_lesson_extraction")

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

DEFAULT_LOOKBACK_DAYS = 7

# Severity thresholds per error taxonomy
CALIBRATION_ERROR_THRESHOLDS = {'LOW': 0.05, 'MEDIUM': 0.15, 'HIGH': 0.25}
DIRECTIONAL_ERROR_THRESHOLDS = {'LOW': 0.45, 'MEDIUM': 0.55, 'HIGH': 0.65}
SUPPRESSION_REGRET_THRESHOLDS = {'LOW': 0.30, 'MEDIUM': 0.50, 'HIGH': 0.70}

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
# LESSON DETECTION LOGIC
# =============================================================================

def detect_calibration_lessons(conn, period_start: datetime, period_end: datetime) -> List[Tuple[Dict, str, List[Dict]]]:
    """
    Detect calibration error patterns.
    Returns: List of (lesson_dict, raw_query, query_result) tuples for evidence binding.
    """
    lessons = []

    # Define query as constant for evidence binding
    CALIBRATION_QUERY = """
        WITH bucketed AS (
            SELECT
                CASE
                    WHEN f.forecast_probability < 0.5 THEN 'LOW_CONFIDENCE'
                    WHEN f.forecast_probability < 0.8 THEN 'MEDIUM_CONFIDENCE'
                    ELSE 'HIGH_CONFIDENCE'
                END AS confidence_bucket,
                f.forecast_probability,
                fop.is_exact_match,
                f.forecast_domain
            FROM fhq_research.forecast_outcome_pairs fop
            JOIN fhq_research.forecast_ledger f ON f.forecast_id = fop.forecast_id
            WHERE fop.reconciled_at BETWEEN %s AND %s
        )
        SELECT
            confidence_bucket,
            COUNT(*) AS total,
            AVG(forecast_probability) AS avg_predicted,
            AVG(CASE WHEN is_exact_match THEN 1.0 ELSE 0.0 END) AS observed_rate,
            ABS(AVG(forecast_probability) - AVG(CASE WHEN is_exact_match THEN 1.0 ELSE 0.0 END)) AS calibration_gap
        FROM bucketed
        GROUP BY confidence_bucket
        HAVING COUNT(*) >= 10
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(CALIBRATION_QUERY, (period_start, period_end))
        query_result = cur.fetchall()

        for row in query_result:
            gap = float(row['calibration_gap'])
            if gap >= CALIBRATION_ERROR_THRESHOLDS['LOW']:
                # Determine severity
                if gap >= CALIBRATION_ERROR_THRESHOLDS['HIGH']:
                    severity = 'HIGH'
                elif gap >= CALIBRATION_ERROR_THRESHOLDS['MEDIUM']:
                    severity = 'MEDIUM'
                else:
                    severity = 'LOW'

                # Determine direction
                predicted = float(row['avg_predicted'])
                observed = float(row['observed_rate'])
                direction = 'OVER' if predicted > observed else 'UNDER'

                lesson = {
                    'lesson_source': 'RECONCILIATION',
                    'lesson_category': 'CALIBRATION_ERROR',
                    'lesson_severity': severity,
                    'error_magnitude': gap,
                    'error_direction': direction,
                    'affected_regime': row['confidence_bucket'],
                    'lesson_description': (
                        f"Calibration gap of {gap:.3f} detected in {row['confidence_bucket']} predictions. "
                        f"Predicted avg: {predicted:.3f}, Observed: {observed:.3f}. "
                        f"System is {direction.lower()}-confident in this bucket."
                    ),
                    'recommended_action': (
                        f"Adjust confidence scaling for {row['confidence_bucket']} predictions. "
                        f"{'Reduce' if direction == 'OVER' else 'Increase'} output confidence."
                    )
                }
                # Append tuple: (lesson, raw_query, query_result)
                lessons.append((lesson, CALIBRATION_QUERY, [dict(r) for r in query_result]))

    return lessons


def detect_regime_lessons(conn, period_start: datetime, period_end: datetime) -> List[Tuple[Dict, str, List[Dict]]]:
    """
    Detect regime-specific error patterns.
    Returns: List of (lesson_dict, raw_query, query_result) tuples for evidence binding.
    """
    lessons = []

    REGIME_QUERY = """
        SELECT
            f.forecast_value AS predicted_regime,
            o.outcome_value AS actual_regime,
            COUNT(*) AS confusion_count,
            SUM(CASE WHEN f.forecast_value = o.outcome_value THEN 1 ELSE 0 END) AS correct_count
        FROM fhq_research.forecast_outcome_pairs fop
        JOIN fhq_research.forecast_ledger f ON f.forecast_id = fop.forecast_id
        JOIN fhq_research.outcome_ledger o ON o.outcome_id = fop.outcome_id
        WHERE fop.reconciled_at BETWEEN %s AND %s
        GROUP BY f.forecast_value, o.outcome_value
        HAVING COUNT(*) >= 5
        ORDER BY COUNT(*) DESC
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(REGIME_QUERY, (period_start, period_end))
        query_result = cur.fetchall()

        # Build confusion matrix
        confusion = {}
        for row in query_result:
            pred = row['predicted_regime']
            actual = row['actual_regime']
            if pred not in confusion:
                confusion[pred] = {'total': 0, 'correct': 0, 'misclassified_to': {}}
            confusion[pred]['total'] += row['confusion_count']
            if pred == actual:
                confusion[pred]['correct'] += row['correct_count']
            else:
                confusion[pred]['misclassified_to'][actual] = row['confusion_count']

        # Generate lessons for significant misclassifications
        for regime, data in confusion.items():
            if data['total'] >= 10:
                error_rate = 1 - (data['correct'] / data['total'])
                if error_rate >= DIRECTIONAL_ERROR_THRESHOLDS['LOW']:
                    # Find most common misclassification
                    if data['misclassified_to']:
                        worst_confusion = max(data['misclassified_to'].items(), key=lambda x: x[1])

                        severity = 'HIGH' if error_rate >= DIRECTIONAL_ERROR_THRESHOLDS['HIGH'] else \
                                   'MEDIUM' if error_rate >= DIRECTIONAL_ERROR_THRESHOLDS['MEDIUM'] else 'LOW'

                        lesson = {
                            'lesson_source': 'RECONCILIATION',
                            'lesson_category': 'REGIME_MISCLASSIFICATION',
                            'lesson_severity': severity,
                            'error_magnitude': error_rate,
                            'error_direction': 'WRONG',
                            'affected_regime': regime,
                            'lesson_description': (
                                f"Regime {regime} predictions have {error_rate:.1%} error rate. "
                                f"Most often confused with {worst_confusion[0]} ({worst_confusion[1]} times)."
                            ),
                            'recommended_action': (
                                f"Review feature weights for {regime} vs {worst_confusion[0]} classification. "
                                f"Consider adding discriminative features."
                            )
                        }
                        # Append tuple: (lesson, raw_query, query_result)
                        lessons.append((lesson, REGIME_QUERY, [dict(r) for r in query_result]))

    return lessons


def detect_suppression_lessons(conn, period_start: datetime, period_end: datetime) -> List[Tuple[Dict, str, List[Dict]]]:
    """
    Detect lessons from suppression regret analysis.
    Returns: List of (lesson_dict, raw_query, query_result) tuples for evidence binding.
    """
    lessons = []

    SUPPRESSION_QUERY = """
        SELECT
            regret_id,
            total_suppressions,
            correct_suppressions,
            regrettable_suppressions,
            suppression_regret_rate,
            suppression_wisdom_rate,
            regret_by_regime,
            regret_by_asset
        FROM fhq_governance.suppression_regret_index
        WHERE period_start < %s AND period_end > %s
        ORDER BY computation_timestamp DESC
        LIMIT 1
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(SUPPRESSION_QUERY, (period_end, period_start))
        query_result = cur.fetchall()
        result = query_result[0] if query_result else None
        if result and result['total_suppressions'] and result['total_suppressions'] > 0:
            regret_rate = float(result['suppression_regret_rate'])
            wisdom_rate = float(result['suppression_wisdom_rate'])

            # Generate regret lesson
            if regret_rate >= SUPPRESSION_REGRET_THRESHOLDS['LOW']:
                severity = 'HIGH' if regret_rate >= SUPPRESSION_REGRET_THRESHOLDS['HIGH'] else \
                           'MEDIUM' if regret_rate >= SUPPRESSION_REGRET_THRESHOLDS['MEDIUM'] else 'LOW'

                lesson = {
                    'lesson_source': 'SUPPRESSION',
                    'lesson_category': 'SUPPRESSION_REGRET',
                    'lesson_severity': severity,
                    'error_magnitude': regret_rate,
                    'error_direction': 'OVER',  # Over-conservative
                    'lesson_description': (
                        f"Suppression Regret Index: {regret_rate:.1%}. "
                        f"Of {result['total_suppressions']} suppressions, {result['regrettable_suppressions']} "
                        f"were correct beliefs that policy incorrectly suppressed."
                    ),
                    'recommended_action': (
                        "Consider reducing hysteresis confirmation window or "
                        "increasing confidence threshold for policy override. "
                        f"Top regret assets: {json.dumps(result['regret_by_asset']) if result['regret_by_asset'] else 'N/A'}"
                    )
                }
                # Append tuple: (lesson, raw_query, query_result)
                lessons.append((lesson, SUPPRESSION_QUERY, [dict(r) for r in query_result]))

            # Generate wisdom lesson (policy adds value)
            if wisdom_rate >= 0.7:
                lesson = {
                    'lesson_source': 'SUPPRESSION',
                    'lesson_category': 'SUPPRESSION_WISDOM',
                    'lesson_severity': 'LOW',
                    'error_magnitude': wisdom_rate,
                    'error_direction': 'UNDER',  # Policy was wisely conservative (under-confident)
                    'lesson_description': (
                        f"Suppression Wisdom: {wisdom_rate:.1%}. "
                        f"Policy correctly suppressed {result['correct_suppressions']} beliefs that would have been wrong."
                    ),
                    'recommended_action': (
                        "Policy layer is adding value. Maintain current hysteresis parameters."
                    )
                }
                # Append tuple: (lesson, raw_query, query_result)
                lessons.append((lesson, SUPPRESSION_QUERY, [dict(r) for r in query_result]))

    return lessons


def store_lesson_with_evidence(
    conn,
    lesson: Dict,
    raw_query: str,
    query_result: List[Dict]
) -> Optional[Tuple[str, str]]:
    """
    Store a single lesson with atomic evidence binding.
    CEO-DIR-2026-021 Audit Correction #4: Transactional evidence binding.

    Returns: (lesson_id, evidence_id) or None on failure
    """
    try:
        lesson_hash = hashlib.sha256(
            json.dumps(lesson, sort_keys=True, default=str).encode()
        ).hexdigest()

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Call court-proof atomic function
            cur.execute("""
                SELECT * FROM fhq_governance.store_lesson_with_evidence(
                    p_lesson_source := %s,
                    p_lesson_category := %s,
                    p_lesson_severity := %s,
                    p_lesson_description := %s,
                    p_lesson_hash := %s,
                    p_raw_query := %s,
                    p_query_result := %s,
                    p_error_magnitude := %s,
                    p_error_direction := %s,
                    p_affected_regime := %s,
                    p_recommended_action := %s,
                    p_created_by := 'STIG'
                )
            """, (
                lesson['lesson_source'],
                lesson['lesson_category'],
                lesson['lesson_severity'],
                lesson['lesson_description'],
                lesson_hash,
                raw_query,
                # CEO-DIR-2026-042: Use default=str to handle Decimal serialization
                json.dumps(query_result, default=str),  # Convert to JSONB
                lesson.get('error_magnitude'),
                lesson.get('error_direction'),
                lesson.get('affected_regime'),
                lesson.get('recommended_action')
            ))

            result = cur.fetchone()
            if result:
                return (str(result['lesson_id']), str(result['evidence_id']))
            return None

    except Exception as e:
        logger.error(f"Failed to store lesson with evidence: {e}")
        return None


def store_lesson(conn, lesson: Dict) -> Optional[str]:
    """
    Legacy function - redirects to store_lesson_with_evidence.
    Provided for backward compatibility but logs warning.
    """
    logger.warning(
        "store_lesson() called without evidence binding. "
        "This violates CEO-DIR-2026-021 Audit Correction #4. "
        "Caller should use store_lesson_with_evidence() instead."
    )

    # Fallback: store with placeholder evidence
    placeholder_query = "-- NO QUERY PROVIDED (LEGACY CALL)"
    placeholder_result = [{"warning": "Evidence not provided"}]

    result = store_lesson_with_evidence(conn, lesson, placeholder_query, placeholder_result)
    return result[0] if result else None


def update_suppression_ledger_lessons(conn, period_start: datetime, period_end: datetime) -> int:
    """
    Update epistemic_suppression_ledger with extracted lessons.
    This closes the loop: suppression -> outcome -> lesson.
    """
    # NOTE: Phase 5 LOCKED - we only mark lesson_extracted, we don't modify policy
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_governance.epistemic_suppression_ledger
            SET lesson_extracted = (
                SELECT lesson_id::text
                FROM fhq_governance.epistemic_lessons
                WHERE lesson_source = 'SUPPRESSION'
                  AND created_at >= %s
                ORDER BY created_at DESC
                LIMIT 1
            )
            WHERE suppression_timestamp BETWEEN %s AND %s
              AND lesson_extracted IS NULL
        """, (period_start, period_start, period_end))

        return cur.rowcount


def log_extraction_evidence(conn, stats: Dict[str, Any]) -> str:
    """Log lesson extraction to governance"""
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
                'IOS010_LESSON_EXTRACTION',
                'fhq_governance.epistemic_lessons',
                'DAEMON_EXECUTION',
                'STIG',
                'EXECUTED',
                'CEO-DIR-2026-007: Lessons extracted from reconciled truth. Phase 5 LOCKED - observation only.',
                %s
            )
            RETURNING action_id
        """, (json.dumps({
            'evidence_id': evidence_id,
            'directive': 'CEO-DIR-2026-007',
            'ios': 'IoS-010',
            'daemon': 'ios010_lesson_extraction_engine',
            'phase_5_status': 'LOCKED - no policy mutation',
            'statistics': stats,
            'evidence_hash': evidence_hash,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }),))

    return evidence_id


def run_lesson_extraction(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> Dict[str, Any]:
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("IOS-010 LESSON EXTRACTION ENGINE")
    logger.info("Directive: CEO-DIR-2026-007")
    logger.info("Phase 5 Status: LOCKED (observation only)")
    logger.info("=" * 60)

    # CEO-DIR-2026-043: Price Reality Gate - hard-fail if data SLA violated
    enforce_price_reality_gate()

    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=lookback_days)

    stats = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
        'lessons_detected': 0,
        'lessons_stored': 0,
        'suppression_ledger_updated': 0,
        'phase_5_status': 'LOCKED',
        'status': 'SUCCESS'
    }

    conn = None
    try:
        conn = get_db_connection()

        all_lessons = []

        # Detect calibration lessons
        logger.info("Detecting calibration lessons")
        calibration_lessons = detect_calibration_lessons(conn, period_start, period_end)
        all_lessons.extend(calibration_lessons)
        stats['calibration_lessons'] = len(calibration_lessons)

        # Detect regime lessons
        logger.info("Detecting regime misclassification lessons")
        regime_lessons = detect_regime_lessons(conn, period_start, period_end)
        all_lessons.extend(regime_lessons)
        stats['regime_lessons'] = len(regime_lessons)

        # Detect suppression lessons
        logger.info("Detecting suppression lessons")
        suppression_lessons = detect_suppression_lessons(conn, period_start, period_end)
        all_lessons.extend(suppression_lessons)
        stats['suppression_lessons'] = len(suppression_lessons)

        stats['lessons_detected'] = len(all_lessons)
        logger.info(f"Detected {len(all_lessons)} lessons total")

        # Store lessons with evidence binding (CEO-DIR-2026-021 Audit Correction #4)
        for lesson_tuple in all_lessons:
            # Unpack tuple: (lesson_dict, raw_query, query_result)
            lesson, raw_query, query_result = lesson_tuple

            result = store_lesson_with_evidence(conn, lesson, raw_query, query_result)
            if result:
                lesson_id, evidence_id = result
                stats['lessons_stored'] += 1
                logger.debug(f"Stored lesson: {lesson['lesson_category']} ({lesson['lesson_severity']}) "
                            f"with evidence {evidence_id}")

        # Update suppression ledger
        updated = update_suppression_ledger_lessons(conn, period_start, period_end)
        stats['suppression_ledger_updated'] = updated

        conn.commit()

        # Log evidence
        evidence_id = log_extraction_evidence(conn, stats)
        stats['evidence_id'] = evidence_id
        conn.commit()

        logger.info(f"Lesson extraction complete: {stats['lessons_stored']} lessons stored, "
                    f"{stats['suppression_ledger_updated']} suppression records linked")

    except Exception as e:
        logger.error(f"Lesson extraction failed: {e}")
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

    parser = argparse.ArgumentParser(description="IoS-010 Lesson Extraction Engine")
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help="Number of days to look back")
    args = parser.parse_args()

    result = run_lesson_extraction(lookback_days=args.days)
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)
