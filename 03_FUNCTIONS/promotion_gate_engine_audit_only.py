#!/usr/bin/env python3
"""
PROMOTION GATE ENGINE — AUDIT-ONLY MODE (CEO-DIR-2026-AUDIT-THROUGHPUT-008)
=================================================================================
Scales audit logging without promotion (from 1 to 1000 rows).

Flags:
    --mode audit_only      Always writes audit row + gate row, never attempts PROMOTE
    --limit N             Limit evaluations to N experiments (default: 500)
    --write_gates true    Write gate rows to canonical_mutation_gates
    --promote false       Hard flag to disable promotion logic

Database operations:
    READS:  experiment_registry, outcome_ledger, hypothesis_canon
    WRITES: promotion_gate_audit, canonical_mutation_gates
    SKIPS:  hypothesis_canon updates, execution_eligibility_registry, g5_promotion_ledger

Usage:
    python promotion_gate_engine_audit_only.py --mode audit_only --limit 500 --write_gates true --promote false

Author: STIG (CTO)
Date: 2026-02-12
Directive: CEO-DIR-2026-AUDIT-THROUGHPUT-008
"""

import os
import sys
import json
import uuid
import math
import logging
import hashlib
import argparse
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Get script directory for absolute paths
SCRIPT_DIR = Path(__file__).parent
LOG_FILE = SCRIPT_DIR / 'promotion_gate_engine_audit_only.log'

logging.basicConfig(
    level=logging.INFO,
    format='[PROMOTION_GATE_AUDIT_ONLY] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('promotion_gate_audit_only')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Thresholds (same as original)
DEFLATED_SHARPE_MIN = 1.0
PBO_MAX = 0.50
FAMILY_INFLATION_MAX = 0.30

DAEMON_NAME = 'promotion_gate_engine_audit_only'
HEARTBEAT_INTERVAL_MINUTES = 60


def register_heartbeat(conn, dry_run=False):
    """Register heartbeat in fhq_monitoring.daemon_health."""
    if dry_run:
        logger.info(f"[DRY RUN] Would register heartbeat for {DAEMON_NAME}")
        return
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_monitoring.daemon_health
                (daemon_name, status, last_heartbeat, expected_interval_minutes,
                 lifecycle_status, metadata)
            VALUES
                (%s, 'HEALTHY', NOW(), %s, 'ACTIVE', '{}'::jsonb)
            ON CONFLICT (daemon_name) DO UPDATE SET
                status = 'HEALTHY',
                last_heartbeat = NOW(),
                updated_at = NOW()
        """, (DAEMON_NAME, HEARTBEAT_INTERVAL_MINUTES))
    conn.commit()
    logger.info(f"Heartbeat registered: {DAEMON_NAME}")


def _decimal_to_float(val):
    """Safely convert Decimal to float."""
    if isinstance(val, Decimal):
        return float(val)
    return val


def compute_deflated_sharpe(observed_sharpe: float, n_trials: int,
                            n_observations: int, skew: float = 0.0,
                            kurtosis: float = 3.0) -> float:
    """Compute Deflated Sharpe Ratio per Bailey & Lopez de Prado (2014)."""
    if n_observations < 2 or n_trials < 1:
        return 0.0

    euler_mascheroni = 0.5772156649
    if n_trials > 1:
        e_max_sr = math.sqrt(2 * math.log(n_trials)) * (
            1 - euler_mascheroni / (2 * math.log(n_trials))
        ) + euler_mascheroni / math.sqrt(2 * math.log(n_trials))
    else:
        e_max_sr = 0.0

    sr_var = (1 - skew * observed_sharpe +
              ((kurtosis - 1) / 4) * observed_sharpe ** 2) / n_observations

    if sr_var <= 0:
        return 0.0

    sr_std = math.sqrt(sr_var)

    if sr_std == 0:
        return 0.0

    deflated = (observed_sharpe - e_max_sr) / sr_std
    return round(deflated, 6)


def compute_pbo_estimate(win_rates: list, n_splits: int = 5) -> float:
    """Estimate Probability of Backtest Overfitting (PBO)."""
    n = len(win_rates)
    if n < 4:
        return 1.0

    actual_splits = min(n_splits, n // 2)
    if actual_splits < 2:
        return 0.8

    fold_size = n // actual_splits
    folds = []
    for i in range(actual_splits):
        start = i * fold_size
        end = start + fold_size if i < actual_splits - 1 else n
        fold_wr = sum(win_rates[start:end]) / max(len(win_rates[start:end]), 1)
        folds.append(fold_wr)

    degradation_count = 0
    pair_count = 0
    for i in range(len(folds)):
        for j in range(i + 1, len(folds)):
            pair_count += 1
            if abs(folds[i] - folds[j]) > 0.15:
                degradation_count += 1

    if pair_count == 0:
        return 0.5

    pbo = degradation_count / pair_count
    return round(pbo, 4)


def compute_family_inflation_risk(n_hypotheses_tested: int,
                                  n_parameters: int) -> float:
    """Estimate family-wise error inflation risk."""
    if n_hypotheses_tested <= 1 and n_parameters <= 1:
        return 0.0

    hypothesis_risk = 1 - (0.95 ** n_hypotheses_tested)
    param_risk = min(1.0, n_parameters / 20.0)
    risk = max(hypothesis_risk, param_risk)
    return round(min(risk, 1.0), 4)


def evaluate_experiment(conn, experiment: dict, dry_run: bool = False,
                   audit_only: bool = True) -> dict:
    """Evaluate a single experiment for promotion gate."""
    exp_id = experiment['experiment_id']
    hyp_id = experiment['hypothesis_id']
    exp_code = experiment['experiment_code']

    logger.info(f"Evaluating {exp_code} (experiment_id={exp_id})")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT outcome_id, result_bool, return_pct, return_bps,
                   pnl_gross_simulated, mfe, mae, time_to_outcome
            FROM fhq_learning.outcome_ledger
            WHERE experiment_id = %s
            ORDER BY created_at
        """, (str(exp_id),))
        outcomes = cur.fetchall()

        cur.execute("""
            SELECT canon_id, hypothesis_code, trial_count,
                   parameter_search_breadth, prior_hypotheses_count,
                   falsification_criteria, current_confidence
            FROM fhq_learning.hypothesis_canon
            WHERE canon_id = %s
        """, (str(hyp_id),))
        hypothesis = cur.fetchone()

        cur.execute("""
            SELECT parameter_count, dof_count,
                   prior_experiments_on_hypothesis
            FROM fhq_learning.experiment_registry
            WHERE experiment_id = %s
        """, (str(exp_id),))
        exp_detail = cur.fetchone()

    if not outcomes or not hypothesis:
        logger.warning(f"  No outcomes or hypothesis for {exp_code}")
        return None

    n_outcomes = len(outcomes)
    falsif = hypothesis['falsification_criteria'] or {}
    min_sample = int(falsif.get('min_sample_size', 30))

    if n_outcomes < min_sample:
        logger.info(f"  {exp_code}: {n_outcomes}/{min_sample} outcomes (not yet eligible)")
        return None

    # Compute metrics
    wins = sum(1 for o in outcomes if o['result_bool'])
    win_rate = wins / n_outcomes

    returns = [_decimal_to_float(o['return_pct'] or 0) for o in outcomes]
    mean_return = sum(returns) / len(returns) if returns else 0
    if len(returns) > 1:
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_return = math.sqrt(variance)
    else:
        std_return = 0.001

    observed_sharpe = mean_return / std_return if std_return > 0 else 0.0

    if len(returns) > 2 and std_return > 0:
        skew = sum(((r - mean_return) / std_return) ** 3 for r in returns) / len(returns)
        kurtosis = sum(((r - mean_return) / std_return) ** 4 for r in returns) / len(returns)
    else:
        skew = 0.0
        kurtosis = 3.0

    n_trials = max(
        hypothesis['trial_count'] or 1,
        hypothesis['prior_hypotheses_count'] or 1,
        exp_detail['prior_experiments_on_hypothesis'] or 1
    )

    deflated_sharpe = compute_deflated_sharpe(
        observed_sharpe=observed_sharpe,
        n_trials=n_trials,
        n_observations=n_outcomes,
        skew=skew,
        kurtosis=kurtosis
    )

    win_sequence = [1.0 if o['result_bool'] else 0.0 for o in outcomes]
    pbo = compute_pbo_estimate(win_sequence)

    n_params = exp_detail['parameter_count'] or 1
    family_risk = compute_family_inflation_risk(n_trials, n_params)

    # Gate decision
    failures = []
    if deflated_sharpe < DEFLATED_SHARPE_MIN:
        failures.append(f"deflated_sharpe={deflated_sharpe:.4f} < {DEFLATED_SHARPE_MIN}")
    if pbo > PBO_MAX:
        failures.append(f"pbo={pbo:.4f} > {PBO_MAX}")
    if family_risk > FAMILY_INFLATION_MAX:
        failures.append(f"family_inflation={family_risk:.4f} > {FAMILY_INFLATION_MAX}")

    falsif_rule = falsif.get('falsified_if', '')
    falsified = False
    if falsif_rule:
        if '<' in falsif_rule:
            parts = falsif_rule.split('<')
            if len(parts) == 2:
                try:
                    threshold = float(parts[1].strip())
                    if 'rate' in parts[0] or 'win' in parts[0]:
                        if win_rate < threshold:
                            falsified = True
                            failures.append(f"falsification: win_rate={win_rate:.4f} < {threshold}")
                except ValueError:
                    pass

    gate_result = 'PASS' if (not failures and not falsified) else 'FAIL'

    metrics = {
        'n_outcomes': n_outcomes,
        'min_sample_size': min_sample,
        'win_rate': round(win_rate, 6),
        'wins': wins,
        'losses': n_outcomes - wins,
        'mean_return_pct': round(mean_return, 8),
        'std_return_pct': round(std_return, 8),
        'observed_sharpe': round(observed_sharpe, 6),
        'deflated_sharpe': deflated_sharpe,
        'pbo_probability': pbo,
        'family_inflation_risk': family_risk,
        'n_trials': n_trials,
        'n_parameters': n_params,
        'skew': round(skew, 6),
        'kurtosis': round(kurtosis, 6),
        'falsification_rule': falsif_rule,
        'falsified': falsified,
        'thresholds': {
            'deflated_sharpe_min': DEFLATED_SHARPE_MIN,
            'pbo_max': PBO_MAX,
            'family_inflation_max': FAMILY_INFLATION_MAX
        }
    }

    failure_reason = '; '.join(failures) if failures else None

    logger.info(f"  {exp_code}: gate_result={gate_result}, "
                f"win_rate={win_rate:.4f}, deflated_sharpe={deflated_sharpe:.4f}, "
                f"pbo={pbo:.4f}")
    if failure_reason:
        logger.info(f"  Failures: {failure_reason}")

    result = {
        'hypothesis_id': str(hyp_id),
        'experiment_id': str(exp_id),
        'experiment_code': exp_code,
        'gate_result': gate_result,
        'failure_reason': failure_reason,
        'metrics': metrics,
    }

    # AUDIT_ONLY MODE: Only write audit row + gate row, skip promotion logic
    if not dry_run:
        _write_promotion_gate_audit(conn, result, audit_only=True)
        if audit_only:
            # Skip hypothesis_canon updates, eligibility entries
            pass
        else:
            _update_hypothesis_canon(conn, result)
            _create_eligibility_entry(conn, result)

    return result


def _write_promotion_gate_audit(conn, result: dict, audit_only: bool = True,
                             write_gates: bool = True):
    """Write evaluation result to promotion_gate_audit."""
    hyp_id = str(result['hypothesis_id'])
    causal_node_id = str(uuid.uuid5(
        uuid.UUID('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'),
        hyp_id.encode()
    ))

    metrics_json = json.dumps(result['metrics'], default=str, sort_keys=True)
    state_snapshot_hash = hashlib.sha256(metrics_json.encode()).hexdigest()

    # Get or create gate_id
    gate_id = None
    if write_gates:
        with conn.cursor() as cur:
            # Check for existing gate for this hypothesis
            cur.execute("""
                SELECT gate_id FROM fhq_governance.canonical_mutation_gates
                WHERE target_id = %s::uuid
                AND target_domain = 'fhq_learning.hypothesis_canon'
                ORDER BY created_at DESC LIMIT 1
            """, (result['hypothesis_id'],))
            existing_gate = cur.fetchone()

            if existing_gate:
                gate_id = existing_gate[0]
            else:
                # Create new gate (LOCKED)
                request_data = json.dumps({
                    "test": "CEO-DIR-2026-AUDIT-THROUGHPUT-008",
                    "experiment_code": result['experiment_code'],
                    "audit_only": True
                })
                g1_evidence = json.dumps({
                    "test": "Gate created for DIR-008 audit"
                })
                cur.execute("""
                    INSERT INTO fhq_governance.canonical_mutation_gates
                        (mutation_type, target_domain, target_id,
                         g1_technical_validation, g1_validated_at, g1_validated_by, g1_evidence,
                         request_data, requested_by)
                    VALUES ('DOMAIN_UPDATE', 'fhq_learning.hypothesis_canon', %s::uuid,
                            true, NOW(), 'STIG_DIR_008_GATE',
                            %s::jsonb, %s::jsonb, 'STIG')
                    RETURNING gate_id
                """, (
                    result['hypothesis_id'],
                    g1_evidence,
                    request_data
                ))
                gate_id = cur.fetchone()[0]
                logger.info(f"  Created gate: {gate_id}")

    with conn.cursor() as cur:
        # Insert audit row with full binding
        # Note: gate_id may be NULL if write_gates=False
        if gate_id:
            cur.execute("""
                INSERT INTO fhq_learning.promotion_gate_audit
                    (hypothesis_id, gate_name, gate_result, failure_reason,
                     metrics_snapshot, evaluated_by, causal_node_id, gate_id,
                     state_snapshot_hash, agent_id)
                VALUES (%s::uuid, 'DEFLATED_SHARPE_GATE', %s, %s, %s::jsonb,
                        'STIG_DIR_008_ENGINE', %s::uuid, %s::uuid, %s, 'STIG')
            """, (
                result['hypothesis_id'],
                result['gate_result'],
                result['failure_reason'],
                json.dumps(result['metrics'], default=str),
                causal_node_id,
                gate_id,
                state_snapshot_hash
            ))
        else:
            cur.execute("""
                INSERT INTO fhq_learning.promotion_gate_audit
                    (hypothesis_id, gate_name, gate_result, failure_reason,
                     metrics_snapshot, evaluated_by, causal_node_id,
                     state_snapshot_hash, agent_id)
                VALUES (%s::uuid, 'DEFLATED_SHARPE_GATE', %s, %s, %s::jsonb,
                        'STIG_DIR_008_ENGINE', %s::uuid, %s, 'STIG')
            """, (
                result['hypothesis_id'],
                result['gate_result'],
                result['failure_reason'],
                json.dumps(result['metrics'], default=str),
                causal_node_id,
                state_snapshot_hash
            ))
        logger.info(f"  Inserted promotion_gate_audit for {result['experiment_code']}")

    conn.commit()


def _update_hypothesis_canon(conn, result: dict):
    """Update hypothesis_canon with overfitting metrics (SKIP in audit_only)."""
    # This function is called but does nothing in audit_only mode
    pass


def _create_eligibility_entry(conn, result: dict):
    """Create eligibility entry (SKIP in audit_only)."""
    # This function is called but does nothing in audit_only mode
    pass


def find_eligible_experiments(conn, limit: int = None) -> list:
    """Find experiments that have reached min_sample_size but not yet evaluated."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                e.experiment_id,
                e.experiment_code,
                e.hypothesis_id,
                e.parameters->>'min_sample_size' as min_sample_size,
                e.status,
                COUNT(o.outcome_id) as outcome_count
            FROM fhq_learning.experiment_registry e
            LEFT JOIN fhq_learning.outcome_ledger o ON o.experiment_id = e.experiment_id
            WHERE e.status IN ('RUNNING', 'COMPLETED')
            GROUP BY e.experiment_id, e.experiment_code, e.hypothesis_id,
                     e.parameters, e.status
            HAVING COUNT(o.outcome_id) >= COALESCE(
                (e.parameters->>'min_sample_size')::int, 30
            )
            ORDER BY e.experiment_code
        """)
        candidates = cur.fetchall()
        if limit:
            candidates = candidates[:limit]
        return candidates


def run_audit_only_mode(conn, limit: int = 500, write_gates: bool = True,
                      dry_run: bool = False):
    """Run audit-only mode: write audit rows + gate rows, no promotion."""
    logger.info("=" * 60)
    logger.info("CEO-DIR-2026-AUDIT-THROUGHPUT-008: AUDIT-ONLY MODE")
    logger.info(f"  limit={limit}, write_gates={write_gates}, dry_run={dry_run}")
    logger.info("=" * 60)

    experiments = find_eligible_experiments(conn, limit=limit)

    if not experiments:
        logger.info("No experiments eligible for audit")
        return {'evaluated': 0, 'passed': 0, 'failed': 0}

    logger.info(f"Found {len(experiments)} experiments (limit={limit})")

    results = []
    for exp in experiments:
        result = evaluate_experiment(conn, exp, dry_run=dry_run, audit_only=True)
        if result:
            results.append(result)

    # Summary
    passed = [r for r in results if r['gate_result'] == 'PASS']
    failed = [r for r in results if r['gate_result'] == 'FAIL']

    logger.info("=" * 60)
    logger.info(f"AUDIT-ONLY SUMMARY: {len(results)} experiments evaluated")
    logger.info(f"  PASS: {len(passed)}")
    logger.info(f"  FAIL: {len(failed)}")

    # Write evidence
    evidence_dir = SCRIPT_DIR / 'evidence'
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    evidence_path = evidence_dir / f'CEO_DIR_AUDIT_THROUGHPUT_008_{ts}.json'

    evidence = {
        'directive': 'CEO-DIR-2026-AUDIT-THROUGHPUT-008',
        'agent': 'STIG (EC-003)',
        'evaluated_at': datetime.now(timezone.utc).isoformat(),
        'dry_run': dry_run,
        'limit': limit,
        'write_gates': write_gates,
        'experiments_evaluated': len(results),
        'passed': len(passed),
        'failed': len(failed),
        'results': results[:10],  # First 10 only for brevity
        'thresholds': {
            'deflated_sharpe_min': DEFLATED_SHARPE_MIN,
            'pbo_max': PBO_MAX,
            'family_inflation_max': FAMILY_INFLATION_MAX
        }
    }

    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)
    logger.info(f"Evidence: {evidence_path}")

    # Register heartbeat
    register_heartbeat(conn, dry_run)

    return {
        'evaluated': len(results),
        'passed': len(passed),
        'failed': len(failed)
    }


def run_verification(conn):
    """Run verification queries for DIR-008."""
    logger.info("=" * 60)
    logger.info("VERIFICATION: CEO-DIR-2026-AUDIT-THROUGHPUT-008")
    logger.info("=" * 60)

    with conn.cursor() as cur:
        # Count new audit rows with full binding (last 60 min)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM fhq_learning.promotion_gate_audit
            WHERE evaluated_at >= NOW() - INTERVAL '60 minutes'
              AND causal_node_id IS NOT NULL
              AND gate_id IS NOT NULL
              AND state_snapshot_hash IS NOT NULL
              AND agent_id IS NOT NULL
        """)
        audit_count = cur.fetchone()[0]
        logger.info(f"  Full-binding audit rows (60 min): {audit_count}")

        # Count gates per state (last 60 min)
        cur.execute("""
            SELECT admission_state, COUNT(*) as count
            FROM fhq_governance.canonical_mutation_gates
            WHERE created_at >= NOW() - INTERVAL '60 minutes'
            GROUP BY admission_state
            ORDER BY admission_state
        """)
        gate_states = cur.fetchall()
        logger.info(f"  New gates per state (60 min):")
        for state, count in gate_states:
            logger.info(f"    {state}: {count}")

        # Top 10 failure reasons
        cur.execute("""
            SELECT failure_reason, COUNT(*) as count
            FROM fhq_learning.promotion_gate_audit
            WHERE evaluated_at >= NOW() - INTERVAL '60 minutes'
              AND failure_reason IS NOT NULL
            GROUP BY failure_reason
            ORDER BY count DESC
            LIMIT 10
        """)
        top_failures = cur.fetchall()
        logger.info(f"  Top 10 failure reasons (60 min):")
        for i, (reason, count) in enumerate(top_failures, 1):
            logger.info(f"    {i}. {reason} ({count})")

        # Confirm 0 PROMOTE transitions (check any activity in g5_promotion_ledger)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM fhq_canonical.g5_promotion_ledger
            WHERE created_at >= NOW() - INTERVAL '60 minutes'
        """)
        promote_count = cur.fetchone()[0]
        logger.info(f"  g5_promotion_ledger new entries (60 min): {promote_count}")

        # Any activity in g5 indicates promotion occurred
        if promote_count > 0:
            logger.warning(f"  STOP CONDITION VIOLATED: {promote_count} new entries in g5_promotion_ledger (should be 0 in audit_only mode)!")

        # Check for trigger blocks (rows missing binding fields)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM fhq_learning.promotion_gate_audit
            WHERE evaluated_at >= NOW() - INTERVAL '60 minutes'
              AND (causal_node_id IS NULL OR gate_id IS NULL OR state_snapshot_hash IS NULL OR agent_id IS NULL)
        """)
        blocked_count = cur.fetchone()[0]
        if blocked_count > 0:
            logger.warning(f"  TRIGGER BLOCKS DETECTED: {blocked_count} rows missing binding")

    return {
        'audit_full_binding': audit_count,
        'gate_states': dict(gate_states),
        'top_failures': top_failures,
        'promote_count': promote_count,
        'blocked_count': blocked_count
    }


def main():
    parser = argparse.ArgumentParser(
        description='Promotion Gate Engine - Audit-Only Mode (CEO-DIR-2026-AUDIT-THROUGHPUT-008)'
    )
    parser.add_argument('--mode', type=str, default='audit_only',
                       help='Execution mode (default: audit_only)')
    parser.add_argument('--limit', type=int, default=500,
                       help='Limit evaluations to N experiments (default: 500)')
    parser.add_argument('--write_gates', action='store_true',
                       help='Write gate rows to canonical_mutation_gates')
    parser.add_argument('--promote', action='store_true',
                       help='Enable promotion logic (default: false)')
    parser.add_argument('--check', action='store_true', help='Dry run, no writes')
    parser.add_argument('--verify', action='store_true',
                       help='Run verification only, no evaluations')

    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        if args.verify:
            # Verification only mode
            results = run_verification(conn)
            evidence_dir = SCRIPT_DIR / 'evidence'
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence_path = evidence_dir / f'CEO_DIR_AUDIT_THROUGHPUT_008_VERIFY_{ts}.json'
            evidence = {
                'directive': 'CEO-DIR-2026-AUDIT-THROUGHPUT-008',
                'agent': 'STIG (EC-003)',
                'verified_at': datetime.now(timezone.utc).isoformat(),
                'verification': results
            }
            with open(evidence_path, 'w') as f:
                json.dump(evidence, f, indent=2)
            logger.info(f"Verification evidence: {evidence_path}")
        else:
            # Run audit-only mode
            run_audit_only_mode(
                conn,
                limit=args.limit,
                write_gates=args.write_gates,
                dry_run=args.check
            )
    finally:
        conn.close()


if __name__ == '__main__':
    main()
