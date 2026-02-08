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

import os
import sys
import json
import logging
import hashlib
import argparse
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[LVI_DAEMON] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/lvi_calculator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DAEMON_NAME = 'lvi_calculator'
CYCLE_INTERVAL_SECONDS = 86400  # 24h


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

    # 1. Completed experiments (decision_packs with EXECUTED status only)
    # CEO-DIR-2026-128: Only count EXECUTED, not PENDING/FAILED/EXPIRED
    cur.execute("""
        SELECT COUNT(*) as completed
        FROM fhq_learning.decision_packs dp
        WHERE dp.execution_status = 'EXECUTED'
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


def get_current_regime(conn) -> tuple:
    """Get current market regime and confidence from fhq_meta.regime_state."""
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT current_regime, regime_confidence
            FROM fhq_meta.regime_state
            ORDER BY last_updated_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return row['current_regime'], float(row['regime_confidence'])
    except Exception as e:
        logger.warning(f"Could not fetch regime: {e}")
    return 'NEUTRAL', 0.5


def store_lvi(conn, lvi_data: dict) -> Optional[str]:
    """
    Store LVI snapshot in both lvi_canonical (constitutional) and control_room_lvi (ops).

    Returns:
        lvi_id if stored successfully, None otherwise
    """
    try:
        cur = conn.cursor()

        # Get current regime for lvi_canonical
        regime, regime_weight = get_current_regime(conn)

        # Compute evidence hash
        evidence_str = json.dumps(lvi_data, sort_keys=True)
        evidence_hash = 'sha256:' + hashlib.sha256(evidence_str.encode()).hexdigest()

        window_end = datetime.now(timezone.utc).date()
        window_start = window_end - timedelta(days=7)

        # 1. Write to fhq_governance.lvi_canonical (constitutional source of truth)
        cur.execute("""
            INSERT INTO fhq_governance.lvi_canonical (
                asset_id, lvi_value, regime_at_computation, regime_weight,
                learning_events_counted, total_events_in_window,
                computation_method, window_start, window_end,
                evidence_hash, computed_by, model_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING lvi_id
        """, (
            'ALL',
            lvi_data['lvi_score'],
            regime,
            regime_weight,
            lvi_data['completed_experiments'],
            lvi_data['completed_experiments'] + int(lvi_data['coverage_rate'] * 30),
            'lvi_calculator_v1',
            window_start,
            window_end,
            evidence_hash,
            'STIG',
            'lvi_calculator_v1'
        ))
        lvi_id = cur.fetchone()[0]

        # 2. Write to fhq_ops.control_room_lvi (operational dashboard)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'fhq_ops'
                AND table_name = 'control_room_lvi'
            )
        """)
        if cur.fetchone()[0]:
            cur.execute("""
                INSERT INTO fhq_ops.control_room_lvi (
                    lvi_score, completed_experiments,
                    median_evaluation_time_hours, coverage_rate,
                    integrity_rate, time_factor, brier_component,
                    drivers, computation_method
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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

        conn.commit()
        logger.info(f"Stored LVI snapshot: {lvi_id} (lvi_canonical + control_room_lvi)")
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


def heartbeat(conn, status: str, details: dict = None):
    """Update daemon heartbeat in daemon_health."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (daemon_name)
                DO UPDATE SET status = EXCLUDED.status,
                              last_heartbeat = NOW(),
                              metadata = EXCLUDED.metadata,
                              updated_at = NOW()
            """, (DAEMON_NAME, status, json.dumps(details) if details else None))
            conn.commit()
    except Exception as e:
        logger.warning(f"Heartbeat failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


def run_cycle() -> dict:
    """Run one LVI computation cycle. Returns evidence dict."""
    conn = get_connection()
    try:
        # Compute LVI
        lvi_data = compute_lvi(conn)
        grade = get_lvi_grade(lvi_data['lvi_score'])
        bottleneck = identify_bottleneck(lvi_data)
        logger.info(f"LVI computed: {lvi_data['lvi_score']:.4f} ({grade})")
        logger.info(f"  Experiments: {lvi_data['completed_experiments']} | "
                     f"Integrity: {lvi_data['integrity_rate']:.2%} | "
                     f"Coverage: {lvi_data['coverage_rate']:.2%}")
        logger.info(f"  Median Eval: {lvi_data['median_evaluation_hours']:.1f}h | "
                     f"Brier: {lvi_data['brier_component']:.4f}")
        logger.info(f"  Bottleneck: {bottleneck}")

        # Store in database
        lvi_id = store_lvi(conn, lvi_data)

        # Generate evidence
        evidence = generate_evidence(lvi_data)

        # Save evidence file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(script_dir, 'evidence', f'LVI_COMPUTATION_{timestamp}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        logger.info(f"Evidence: {evidence_path}")

        # Heartbeat
        heartbeat(conn, 'HEALTHY', {
            'lvi_score': lvi_data['lvi_score'],
            'grade': grade,
            'bottleneck': bottleneck,
            'lvi_id': lvi_id,
        })

        return evidence

    except Exception as e:
        logger.error(f"LVI computation failed: {e}")
        try:
            heartbeat(conn, 'DEGRADED', {'error': str(e)})
        except Exception:
            pass
        raise
    finally:
        conn.close()


def main():
    """Main entry point for LVI daemon."""
    parser = argparse.ArgumentParser(description='LVI Calculator Daemon')
    parser.add_argument('--once', action='store_true',
                        help='Run a single computation then exit')
    parser.add_argument('--interval', type=int, default=CYCLE_INTERVAL_SECONDS,
                        help=f'Cycle interval in seconds (default: {CYCLE_INTERVAL_SECONDS})')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("LVI CALCULATOR DAEMON")
    logger.info(f"  mode={'once' if args.once else 'continuous'}")
    logger.info(f"  interval={args.interval}s")
    logger.info("=" * 60)

    if args.once:
        evidence = run_cycle()
        lvi = evidence['lvi_data']
        print(f"\nLVI: {lvi['lvi_score']:.4f} ({get_lvi_grade(lvi['lvi_score'])}) | "
              f"Bottleneck: {identify_bottleneck(lvi)}")
        return

    # Continuous daemon loop
    while True:
        try:
            run_cycle()
        except Exception as e:
            logger.error(f"Cycle failed: {e}")
        logger.info(f"Next cycle in {args.interval}s")
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
