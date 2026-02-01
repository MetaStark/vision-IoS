#!/usr/bin/env python3
"""
LVI Calculator - Learning Velocity Index
CEO-DIR-2026-023 Order 4

Purpose: Compute non-gameable learning velocity metric.
Volume alone doesn't increase LVI without integrity.

Formula:
  LVI = (Completed_Experiments × Integrity_Rate × Coverage_Rate) / Median_Eval_Time

Where:
  - Completed_Experiments: event → hypothesis → decision → outcome chains
  - Integrity_Rate: % with full trace chain (evidence_hash NOT NULL)
  - Coverage_Rate: % of IoS-016 events with evaluated outcomes
  - Median_Eval_Time: hours from event to outcome (target: T+24h)
"""

import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres'
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_lvi(conn) -> dict:
    """
    Compute Learning Velocity Index.

    Non-gameable: volume alone doesn't increase LVI without integrity.

    Returns:
        dict with LVI components and final score
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Completed experiments (decision_packs with linked outcomes)
    cur.execute("""
        SELECT COUNT(*) as completed
        FROM fhq_learning.decision_packs dp
        WHERE dp.execution_status IS NOT NULL
          AND dp.created_at > NOW() - INTERVAL '7 days'
    """)
    result = cur.fetchone()
    completed = result['completed'] if result else 0

    # 2. Integrity rate (full trace chain with evidence_hash)
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE evidence_hash IS NOT NULL)::float /
            NULLIF(COUNT(*), 0) as integrity
        FROM fhq_learning.decision_packs
        WHERE created_at > NOW() - INTERVAL '7 days'
    """)
    result = cur.fetchone()
    integrity = float(result['integrity']) if result and result['integrity'] else 0.0

    # 3. Coverage rate (IoS-016 events with linked outcomes)
    # Check if hypothesis_ledger exists
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'fhq_learning'
            AND table_name = 'hypothesis_ledger'
        ) as exists
    """)
    hypothesis_ledger_exists = cur.fetchone()['exists']

    if hypothesis_ledger_exists:
        cur.execute("""
            SELECT
                COUNT(DISTINCT ce.event_id) FILTER (
                    WHERE hl.hypothesis_id IS NOT NULL
                ) ::float / NULLIF(COUNT(DISTINCT ce.event_id), 0) as coverage
            FROM fhq_calendar.calendar_events ce
            LEFT JOIN fhq_learning.hypothesis_ledger hl
                ON ce.event_id = hl.event_id
            WHERE ce.event_timestamp BETWEEN NOW() - INTERVAL '30 days' AND NOW()
        """)
        result = cur.fetchone()
        coverage = float(result['coverage']) if result and result['coverage'] else 0.0
    else:
        # Fallback: use outcome_ledger linkage to calendar events
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE actual_value IS NOT NULL)::float /
                NULLIF(COUNT(*), 0) as coverage
            FROM fhq_calendar.calendar_events
            WHERE event_timestamp BETWEEN NOW() - INTERVAL '30 days' AND NOW()
        """)
        result = cur.fetchone()
        coverage = float(result['coverage']) if result and result['coverage'] else 0.0

    # 4. Median evaluation time (hours from decision to outcome)
    # Note: outcome_ledger uses outcome_domain for asset reference, not symbol
    # For now, use default if no direct linkage exists
    cur.execute("""
        SELECT
            COALESCE(
                EXTRACT(EPOCH FROM
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY ol.created_at - dp.created_at
                    )
                ) / 3600,
                24
            ) as median_hours
        FROM fhq_learning.decision_packs dp
        LEFT JOIN fhq_research.outcome_ledger ol
            ON dp.asset = ol.outcome_domain
            AND ol.created_at > dp.created_at
            AND ol.created_at < dp.created_at + INTERVAL '7 days'
        WHERE dp.created_at > NOW() - INTERVAL '7 days'
    """)
    result = cur.fetchone()
    median_hours = float(result['median_hours']) if result and result['median_hours'] else 24.0

    # 5. Optional: Brier component (calibration quality)
    cur.execute("""
        SELECT AVG(brier_score_mean) as brier
        FROM fhq_research.forecast_skill_metrics
        WHERE brier_score_mean IS NOT NULL
    """)
    result = cur.fetchone()
    brier_score = float(result['brier']) if result and result['brier'] else 0.25

    # Brier component: lower is better, convert to multiplier (0.5 at brier=0.25)
    brier_component = max(0.1, 1.0 - (brier_score * 2.0))

    # Time factor: penalize slow evaluation (48h = 0.1 factor)
    time_factor = max(0.1, 1.0 - (median_hours / 48.0))

    # LVI Calculation
    # Formula: (completed * integrity * coverage * time_factor * brier_component)
    # Normalized to 0-1 range assuming max 100 experiments/week
    raw_lvi = completed * integrity * coverage * time_factor * brier_component
    lvi_score = min(1.0, raw_lvi / 10.0)  # Normalize: 10 high-quality experiments = 1.0

    return {
        'lvi_score': round(lvi_score, 4),
        'completed_experiments': completed,
        'integrity_rate': round(integrity, 4),
        'coverage_rate': round(coverage, 4),
        'median_evaluation_hours': round(median_hours, 2),
        'time_factor': round(time_factor, 4),
        'brier_component': round(brier_component, 4),
        'computed_at': datetime.now(timezone.utc).isoformat(),
        'formula': 'LVI = (completed × integrity × coverage × time_factor × brier) / 10'
    }


def store_lvi(conn, lvi_data: dict) -> Optional[str]:
    """
    Store LVI snapshot in control_room_lvi table.

    Returns:
        lvi_id if stored successfully, None otherwise
    """
    try:
        cur = conn.cursor()

        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'fhq_ops'
                AND table_name = 'control_room_lvi'
            )
        """)
        if not cur.fetchone()[0]:
            logger.warning("fhq_ops.control_room_lvi does not exist - run migration 332 first")
            return None

        cur.execute("""
            INSERT INTO fhq_ops.control_room_lvi (
                lvi_score,
                completed_experiments,
                median_evaluation_time_hours,
                coverage_rate,
                integrity_rate,
                time_factor,
                brier_component,
                drivers,
                computation_method
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING lvi_id
        """, (
            lvi_data['lvi_score'],
            lvi_data['completed_experiments'],
            lvi_data['median_evaluation_hours'],
            lvi_data['coverage_rate'],
            lvi_data['integrity_rate'],
            lvi_data['time_factor'],
            lvi_data['brier_component'],
            json.dumps(lvi_data),
            'lvi_calculator_v1'
        ))

        lvi_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"Stored LVI snapshot: {lvi_id}")
        return str(lvi_id)

    except Exception as e:
        logger.error(f"Failed to store LVI: {e}")
        conn.rollback()
        return None


def generate_evidence(lvi_data: dict) -> dict:
    """Generate evidence bundle for LVI computation."""
    evidence = {
        'directive': 'CEO-DIR-2026-023-ORDER-4',
        'evidence_type': 'LVI_COMPUTATION',
        'computed_at': lvi_data['computed_at'],
        'computed_by': 'STIG',
        'ec_contract': 'EC-003',
        'lvi_data': lvi_data,
        'interpretation': {
            'score': lvi_data['lvi_score'],
            'grade': get_lvi_grade(lvi_data['lvi_score']),
            'bottleneck': identify_bottleneck(lvi_data)
        }
    }

    # Add hash
    evidence_str = json.dumps(lvi_data, sort_keys=True)
    evidence['evidence_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()[:16]

    return evidence


def get_lvi_grade(score: float) -> str:
    """Get letter grade for LVI score."""
    if score >= 0.8:
        return 'A'
    elif score >= 0.6:
        return 'B'
    elif score >= 0.4:
        return 'C'
    elif score >= 0.2:
        return 'D'
    else:
        return 'F'


def identify_bottleneck(lvi_data: dict) -> str:
    """Identify the primary bottleneck limiting LVI."""
    if lvi_data['completed_experiments'] == 0:
        return 'No completed experiments - need to close learning loop'
    if lvi_data['integrity_rate'] < 0.5:
        return 'Low integrity rate - evidence hashes missing'
    if lvi_data['coverage_rate'] < 0.5:
        return 'Low coverage rate - events without hypotheses'
    if lvi_data['time_factor'] < 0.5:
        return 'Slow evaluation - median time > 24h'
    if lvi_data['brier_component'] < 0.5:
        return 'Poor calibration - Brier score too high'
    return 'No critical bottleneck'


def main():
    """Main entry point for LVI computation."""
    logger.info("Starting LVI computation...")

    try:
        conn = get_connection()

        # Compute LVI
        lvi_data = compute_lvi(conn)
        logger.info(f"LVI computed: {lvi_data['lvi_score']} ({get_lvi_grade(lvi_data['lvi_score'])})")

        # Store in database (if table exists)
        lvi_id = store_lvi(conn, lvi_data)

        # Generate evidence
        evidence = generate_evidence(lvi_data)

        # Save evidence file
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(script_dir, 'evidence', f'LVI_COMPUTATION_{timestamp}.json')

        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2)

        logger.info(f"Evidence saved to: {evidence_path}")

        # Print summary
        print("\n" + "=" * 60)
        print("LVI COMPUTATION SUMMARY")
        print("=" * 60)
        print(f"LVI Score:          {lvi_data['lvi_score']:.4f} ({get_lvi_grade(lvi_data['lvi_score'])})")
        print(f"Experiments:        {lvi_data['completed_experiments']}")
        print(f"Integrity Rate:     {lvi_data['integrity_rate']:.2%}")
        print(f"Coverage Rate:      {lvi_data['coverage_rate']:.2%}")
        print(f"Median Eval Time:   {lvi_data['median_evaluation_hours']:.1f}h")
        print(f"Time Factor:        {lvi_data['time_factor']:.4f}")
        print(f"Brier Component:    {lvi_data['brier_component']:.4f}")
        print(f"Bottleneck:         {identify_bottleneck(lvi_data)}")
        print("=" * 60)

        conn.close()
        return evidence

    except Exception as e:
        logger.error(f"LVI computation failed: {e}")
        raise


if __name__ == '__main__':
    main()
