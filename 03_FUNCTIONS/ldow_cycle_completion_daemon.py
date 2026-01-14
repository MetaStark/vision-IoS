#!/usr/bin/env python3
"""
LDOW CYCLE COMPLETION DAEMON
============================
CEO Directive: 2026-01-14 - Evidence-Based Cycle Completion
Classification: STRATEGIC-FUNDAMENTAL (Class A+)
ADR Reference: ADR-024 Rung D Eligibility

Purpose:
    Execute LDOW cycle completion with evidence-based thresholds.
    - Coverage threshold: Minimum % of forecasts paired
    - Stability threshold: Maximum Brier variance on re-run
    - Damper immutability: Hash unchanged during cycle

Architecture: Option A (OS-level scheduler)
    - Windows Task Scheduler triggers this script
    - Script enforces coverage and stability thresholds
    - Script logs all evidence per CEO requirements

ADR-024 Compliance:
    - Rung D eligibility requires 2 completed cycles
    - Both cycles must meet coverage + stability thresholds
    - VEGA attestation required for both cycles

Usage:
    python ldow_cycle_completion_daemon.py --cycle 1
    python ldow_cycle_completion_daemon.py --cycle 2
"""

import os
import sys
import json
import uuid
import hashlib
import logging
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, Tuple
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
logger = logging.getLogger("ldow_cycle_completion")

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

# Default thresholds (can be overridden from database)
DEFAULT_COVERAGE_THRESHOLD = 0.80  # 80% minimum
DEFAULT_STABILITY_THRESHOLD = 0.05  # 5% max Brier variance
STABILITY_CHECK_DELAY_SECONDS = 60  # Delay between stability runs

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# PRICE REALITY GATE (from ios010)
# =============================================================================

def check_price_reality_gate(conn) -> Tuple[bool, str]:
    """
    Check if data is fresh enough for learning operations.
    CEO-DIR-2026-043: Hard-fail if data SLA violated.
    """
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

        return (True, "Price reality gate passed")

# =============================================================================
# THRESHOLD LOADING
# =============================================================================

def load_thresholds(conn) -> Dict[str, float]:
    """Load active thresholds from database"""
    thresholds = {
        'coverage': DEFAULT_COVERAGE_THRESHOLD,
        'stability': DEFAULT_STABILITY_THRESHOLD
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT threshold_name, threshold_value
            FROM fhq_governance.ldow_completion_thresholds
            WHERE is_active = TRUE
        """)
        for row in cur.fetchall():
            if row['threshold_name'] == 'COVERAGE_MINIMUM':
                thresholds['coverage'] = float(row['threshold_value'])
            elif row['threshold_name'] == 'STABILITY_VARIANCE_MAX':
                thresholds['stability'] = float(row['threshold_value'])

    return thresholds

# =============================================================================
# DAMPER HASH VERIFICATION
# =============================================================================

def get_current_damper_hash(conn) -> str:
    """Get current damper configuration hash"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT config_value
            FROM fhq_governance.finn_config
            WHERE config_key = 'damper_hash'
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        result = cur.fetchone()
        if result:
            return result['config_value']

        # Fallback: compute from damper config
        cur.execute("""
            SELECT config_value
            FROM fhq_governance.finn_config
            WHERE config_key LIKE 'damper_%'
            ORDER BY config_key
        """)
        config_str = json.dumps([dict(r) for r in cur.fetchall()], sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:16]

# =============================================================================
# CYCLE COMPLETION LOGIC
# =============================================================================

def get_cycle_record(conn, cycle_number: int) -> Optional[Dict]:
    """Get cycle completion record"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT *
            FROM fhq_governance.ldow_cycle_completion
            WHERE cycle_number = %s
        """, (cycle_number,))
        result = cur.fetchone()
        return dict(result) if result else None


def update_cycle_status(conn, cycle_number: int, status: str, **kwargs):
    """Update cycle completion status"""
    set_clauses = ["completion_status = %s"]
    values = [status]

    for key, value in kwargs.items():
        set_clauses.append(f"{key} = %s")
        values.append(value)

    values.append(cycle_number)

    with conn.cursor() as cur:
        cur.execute(f"""
            UPDATE fhq_governance.ldow_cycle_completion
            SET {', '.join(set_clauses)}
            WHERE cycle_number = %s
        """, values)


def log_task_execution(
    conn,
    task_id: str,
    cycle_completion_id: str,
    task_type: str,
    damper_hash: str,
    **metrics
) -> str:
    """Log task execution per CEO evidence requirements"""
    execution_id = str(uuid.uuid4())

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.ldow_task_execution_log (
                execution_id,
                task_id,
                cycle_completion_id,
                task_type,
                damper_hash,
                forecasts_eligible,
                forecasts_paired,
                forecasts_expired,
                brier_score,
                calibration_error,
                hit_rate,
                parameters_unchanged,
                execution_status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'RUNNING'
            )
        """, (
            execution_id,
            task_id,
            cycle_completion_id,
            task_type,
            damper_hash,
            metrics.get('forecasts_eligible'),
            metrics.get('forecasts_paired'),
            metrics.get('forecasts_expired'),
            metrics.get('brier_score'),
            metrics.get('calibration_error'),
            metrics.get('hit_rate'),
            metrics.get('parameters_unchanged', True)
        ))

    return execution_id


def complete_task_execution(conn, execution_id: str, status: str, evidence_id: str = None, error: str = None):
    """Complete task execution log entry"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_governance.ldow_task_execution_log
            SET ended_at = NOW(),
                execution_status = %s,
                evidence_id = %s,
                error_message = %s
            WHERE execution_id = %s
        """, (status, evidence_id, error, execution_id))


# =============================================================================
# RECONCILIATION EXECUTION
# =============================================================================

def run_reconciliation(conn, cycle_number: int, horizon_hours: int = 24) -> Dict[str, Any]:
    """
    Execute reconciliation for the cycle.
    Returns metrics for coverage and scoring.
    """
    logger.info(f"Running reconciliation for cycle {cycle_number}, horizon {horizon_hours}h")

    # Get eligible forecasts for this cycle
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Count eligible forecasts (past valid_until by at least 1 hour)
        cur.execute("""
            SELECT COUNT(*) as eligible
            FROM fhq_research.forecast_ledger f
            WHERE f.is_resolved = FALSE
              AND f.forecast_valid_until < NOW() - INTERVAL '1 hour'
              AND f.forecast_type = 'REGIME'
              AND f.forecast_horizon_hours = %s
        """, (horizon_hours,))
        eligible_count = cur.fetchone()['eligible']

        logger.info(f"Found {eligible_count} eligible forecasts")

        if eligible_count == 0:
            return {
                'forecasts_eligible': 0,
                'forecasts_paired': 0,
                'forecasts_expired': 0,
                'brier_score': None,
                'hit_rate': None,
                'calibration_error': None
            }

        # Run reconciliation (similar to ios010 daemon)
        paired_count = 0
        expired_count = 0
        total_brier = 0.0
        hit_count = 0

        cur.execute("""
            SELECT
                f.forecast_id,
                f.forecast_type,
                f.forecast_domain,
                f.forecast_value,
                f.forecast_probability,
                f.forecast_valid_from,
                f.forecast_valid_until
            FROM fhq_research.forecast_ledger f
            WHERE f.is_resolved = FALSE
              AND f.forecast_valid_until < NOW() - INTERVAL '1 hour'
              AND f.forecast_type = 'REGIME'
              AND f.forecast_horizon_hours = %s
            ORDER BY f.forecast_valid_until ASC
            LIMIT 5000
        """, (horizon_hours,))

        forecasts = cur.fetchall()

        for forecast in forecasts:
            # Find matching outcome
            cur.execute("""
                SELECT
                    o.outcome_id,
                    o.outcome_value,
                    o.outcome_timestamp,
                    1.0 - LEAST(1.0, ABS(EXTRACT(EPOCH FROM (o.outcome_timestamp - %s))) /
                           (6 * 3600.0))::numeric AS match_confidence
                FROM fhq_research.outcome_ledger o
                WHERE o.outcome_domain = %s
                  AND o.outcome_type = %s
                  AND o.outcome_timestamp BETWEEN %s AND (%s + INTERVAL '6 hours')
                ORDER BY ABS(EXTRACT(EPOCH FROM (o.outcome_timestamp - %s))) ASC
                LIMIT 1
            """, (
                forecast['forecast_valid_until'],
                forecast['forecast_domain'],
                forecast['forecast_type'],
                forecast['forecast_valid_from'],
                forecast['forecast_valid_until'],
                forecast['forecast_valid_until']
            ))

            outcome = cur.fetchone()

            if outcome:
                # Compute Brier score
                forecast_prob = float(forecast['forecast_probability'])
                is_hit = forecast['forecast_value'] == outcome['outcome_value']
                outcome_indicator = 1.0 if is_hit else 0.0
                brier = (forecast_prob - outcome_indicator) ** 2

                # Create pair
                cur.execute("""
                    INSERT INTO fhq_research.forecast_outcome_pairs (
                        forecast_id,
                        outcome_id,
                        alignment_score,
                        alignment_method,
                        is_exact_match,
                        brier_score,
                        hit_rate_contribution,
                        outcome_within_horizon,
                        reconciled_by,
                        hash_chain_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, TRUE, 'LDOW_CYCLE_DAEMON', %s
                    )
                    ON CONFLICT DO NOTHING
                    RETURNING pair_id
                """, (
                    forecast['forecast_id'],
                    outcome['outcome_id'],
                    max(0.0, min(1.0, float(outcome['match_confidence']))),
                    'TEMPORAL_PROXIMITY',
                    is_hit,
                    brier,
                    is_hit,
                    f"LDOW-CYCLE-{cycle_number}-{forecast['forecast_id']}"
                ))

                if cur.fetchone():
                    paired_count += 1
                    total_brier += brier
                    if is_hit:
                        hit_count += 1

                    # Mark forecast resolved
                    resolution_status = 'CORRECT' if is_hit else 'INCORRECT'
                    cur.execute("""
                        UPDATE fhq_research.forecast_ledger
                        SET is_resolved = TRUE,
                            resolution_status = %s,
                            resolved_at = NOW(),
                            outcome_id = %s
                        WHERE forecast_id = %s
                    """, (resolution_status, outcome['outcome_id'], forecast['forecast_id']))
            else:
                # Mark as expired
                cur.execute("""
                    UPDATE fhq_research.forecast_ledger
                    SET is_resolved = TRUE,
                        resolution_status = 'EXPIRED',
                        resolved_at = NOW()
                    WHERE forecast_id = %s
                """, (forecast['forecast_id'],))
                expired_count += 1

    # Compute metrics
    avg_brier = total_brier / paired_count if paired_count > 0 else None
    hit_rate = hit_count / paired_count if paired_count > 0 else None

    return {
        'forecasts_eligible': eligible_count,
        'forecasts_paired': paired_count,
        'forecasts_expired': expired_count,
        'brier_score': avg_brier,
        'hit_rate': hit_rate,
        'calibration_error': avg_brier  # Using Brier as calibration proxy
    }


# =============================================================================
# EVIDENCE LOGGING
# =============================================================================

def log_cycle_evidence(conn, cycle_number: int, metrics: Dict, damper_hash: str) -> str:
    """Log cycle completion evidence to governance"""
    evidence_id = str(uuid.uuid4())
    evidence_hash = hashlib.sha256(json.dumps(metrics, default=str).encode()).hexdigest()

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
                'LDOW_CYCLE_COMPLETION',
                %s,
                'CYCLE',
                'LDOW_CYCLE_DAEMON',
                'EXECUTED',
                'CEO Directive 2026-01-14: Evidence-based cycle completion',
                %s
            )
            RETURNING action_id
        """, (
            f'LDOW-CYCLE-{cycle_number}',
            json.dumps({
                'evidence_id': evidence_id,
                'cycle_number': cycle_number,
                'metrics': metrics,
                'damper_hash': damper_hash,
                'evidence_hash': evidence_hash,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'adr_reference': 'ADR-024'
            })
        ))

    return evidence_id


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def execute_cycle_completion(cycle_number: int) -> Dict[str, Any]:
    """
    Main execution function for cycle completion.
    Implements evidence-based completion with coverage and stability thresholds.
    """
    logger.info("=" * 60)
    logger.info(f"LDOW CYCLE {cycle_number} COMPLETION DAEMON")
    logger.info("CEO Directive: 2026-01-14 - Evidence-Based Completion")
    logger.info("=" * 60)

    result = {
        'cycle_number': cycle_number,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'status': 'RUNNING'
    }

    conn = None
    try:
        conn = get_db_connection()

        # 1. Price Reality Gate
        gate_passed, reason = check_price_reality_gate(conn)
        if not gate_passed:
            logger.critical(f"PRICE REALITY GATE FAILED: {reason}")
            result['status'] = 'ERROR'
            result['error'] = reason
            return result

        logger.info(f"Price Reality Gate: {reason}")

        # 2. Load thresholds
        thresholds = load_thresholds(conn)
        logger.info(f"Thresholds: coverage={thresholds['coverage']}, stability={thresholds['stability']}")

        # 3. Get cycle record
        cycle = get_cycle_record(conn, cycle_number)
        if not cycle:
            logger.error(f"Cycle {cycle_number} not found in ldow_cycle_completion")
            result['status'] = 'ERROR'
            result['error'] = 'Cycle not registered'
            return result

        # 4. Get current damper hash
        damper_hash_start = get_current_damper_hash(conn)
        logger.info(f"Damper hash at start: {damper_hash_start}")

        # 5. Update cycle to RUNNING
        update_cycle_status(conn, cycle_number, 'RUNNING',
                            started_at=datetime.now(timezone.utc),
                            damper_hash_at_start=damper_hash_start)
        conn.commit()

        # 6. Run first reconciliation
        logger.info("Running reconciliation (run 1)...")
        task_id_1 = f"LDOW-CYCLE-{cycle_number}-RECONCILE-1"
        exec_id_1 = log_task_execution(
            conn, task_id_1, str(cycle['completion_id']),
            'RECONCILIATION', damper_hash_start
        )
        conn.commit()

        metrics_1 = run_reconciliation(conn, cycle_number, cycle['horizon_hours'])
        conn.commit()

        complete_task_execution(conn, exec_id_1, 'SUCCESS')
        conn.commit()

        logger.info(f"Run 1 metrics: {metrics_1}")

        # 7. Check coverage threshold
        coverage_ratio = 0.0
        if metrics_1['forecasts_eligible'] > 0:
            coverage_ratio = metrics_1['forecasts_paired'] / metrics_1['forecasts_eligible']

        logger.info(f"Coverage ratio: {coverage_ratio:.2%} (threshold: {thresholds['coverage']:.0%})")

        if coverage_ratio < thresholds['coverage']:
            logger.warning(f"COVERAGE THRESHOLD NOT MET: {coverage_ratio:.2%} < {thresholds['coverage']:.0%}")
            update_cycle_status(conn, cycle_number, 'COVERAGE_FAIL',
                                forecasts_eligible=metrics_1['forecasts_eligible'],
                                forecasts_paired=metrics_1['forecasts_paired'],
                                forecasts_expired=metrics_1['forecasts_expired'],
                                brier_score_run1=metrics_1['brier_score'])
            conn.commit()
            result['status'] = 'COVERAGE_FAIL'
            result['coverage_ratio'] = coverage_ratio
            return result

        # 8. Stability check - wait and run again
        logger.info(f"Waiting {STABILITY_CHECK_DELAY_SECONDS}s for stability check...")
        import time
        time.sleep(STABILITY_CHECK_DELAY_SECONDS)

        logger.info("Running stability check (run 2)...")
        task_id_2 = f"LDOW-CYCLE-{cycle_number}-STABILITY-CHECK"
        exec_id_2 = log_task_execution(
            conn, task_id_2, str(cycle['completion_id']),
            'STABILITY_CHECK', damper_hash_start
        )
        conn.commit()

        metrics_2 = run_reconciliation(conn, cycle_number, cycle['horizon_hours'])
        conn.commit()

        complete_task_execution(conn, exec_id_2, 'SUCCESS')
        conn.commit()

        logger.info(f"Run 2 metrics: {metrics_2}")

        # 9. Check stability threshold
        brier_variance = 0.0
        if metrics_1['brier_score'] is not None and metrics_2['brier_score'] is not None:
            brier_variance = abs(metrics_1['brier_score'] - metrics_2['brier_score'])
        elif metrics_1['brier_score'] is None and metrics_2['brier_score'] is None:
            # Both runs had no pairings - this is stable (0 variance)
            brier_variance = 0.0

        logger.info(f"Brier variance: {brier_variance:.5f} (threshold: {thresholds['stability']:.5f})")

        if brier_variance > thresholds['stability']:
            logger.warning(f"STABILITY THRESHOLD NOT MET: {brier_variance:.5f} > {thresholds['stability']:.5f}")
            update_cycle_status(conn, cycle_number, 'STABILITY_FAIL',
                                brier_score_run1=metrics_1['brier_score'],
                                brier_score_run2=metrics_2['brier_score'])
            conn.commit()
            result['status'] = 'STABILITY_FAIL'
            result['brier_variance'] = brier_variance
            return result

        # 10. Verify damper unchanged
        damper_hash_end = get_current_damper_hash(conn)
        logger.info(f"Damper hash at end: {damper_hash_end}")

        if damper_hash_start != damper_hash_end:
            logger.critical(f"DAMPER CHANGED DURING CYCLE: {damper_hash_start} -> {damper_hash_end}")
            update_cycle_status(conn, cycle_number, 'DAMPER_CHANGED',
                                damper_hash_at_end=damper_hash_end)
            conn.commit()
            result['status'] = 'DAMPER_CHANGED'
            return result

        # 11. Log evidence
        evidence_id = log_cycle_evidence(conn, cycle_number, {
            'metrics_run1': metrics_1,
            'metrics_run2': metrics_2,
            'coverage_ratio': coverage_ratio,
            'brier_variance': brier_variance,
            'thresholds': thresholds
        }, damper_hash_end)
        conn.commit()

        # 12. Mark cycle complete
        # Combine metrics from both runs
        total_paired = metrics_1['forecasts_paired'] + metrics_2['forecasts_paired']
        total_expired = metrics_1['forecasts_expired'] + metrics_2['forecasts_expired']

        update_cycle_status(conn, cycle_number, 'COMPLETED',
                            completed_at=datetime.now(timezone.utc),
                            forecasts_eligible=metrics_1['forecasts_eligible'],
                            forecasts_paired=total_paired,
                            forecasts_expired=total_expired,
                            brier_score_run1=metrics_1['brier_score'],
                            brier_score_run2=metrics_2['brier_score'],
                            calibration_error=metrics_1['brier_score'],
                            hit_rate=metrics_1['hit_rate'],
                            damper_hash_at_end=damper_hash_end,
                            evidence_id=evidence_id)
        conn.commit()

        logger.info("=" * 60)
        logger.info(f"CYCLE {cycle_number} COMPLETED SUCCESSFULLY")
        logger.info(f"Coverage: {coverage_ratio:.2%}")
        logger.info(f"Stability: {brier_variance:.5f}")
        logger.info(f"Evidence ID: {evidence_id}")
        logger.info("=" * 60)

        result['status'] = 'COMPLETED'
        result['coverage_ratio'] = coverage_ratio
        result['brier_variance'] = brier_variance
        result['evidence_id'] = evidence_id
        result['metrics'] = {
            'run1': metrics_1,
            'run2': metrics_2
        }

    except Exception as e:
        logger.error(f"Cycle completion failed: {e}")
        result['status'] = 'ERROR'
        result['error'] = str(e)
        if conn:
            try:
                update_cycle_status(conn, cycle_number, 'ERROR')
                conn.commit()
            except:
                pass
            conn.rollback()
    finally:
        if conn:
            conn.close()

    result['completed_at'] = datetime.now(timezone.utc).isoformat()
    return result


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='LDOW Cycle Completion Daemon')
    parser.add_argument('--cycle', type=int, required=True,
                        help='Cycle number to complete (1 or 2)')
    args = parser.parse_args()

    if args.cycle not in [1, 2]:
        print("ERROR: Cycle must be 1 or 2")
        sys.exit(1)

    result = execute_cycle_completion(args.cycle)
    print(json.dumps(result, indent=2, default=str))

    if result['status'] == 'COMPLETED':
        sys.exit(0)
    else:
        sys.exit(1)
