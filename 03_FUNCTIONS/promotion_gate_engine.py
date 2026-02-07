#!/usr/bin/env python3
"""
PROMOTION GATE ENGINE
=====================
Evaluates experiments that reach min_sample_size and computes overfitting metrics.

Pipeline position: Step 4 (after outcome_ledger, before shadow_tier)

For each experiment with outcomes >= min_sample_size:
  1. Compute win_rate vs falsification_threshold
  2. Compute Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)
  3. Compute PBO estimate (Probability of Backtest Overfitting)
  4. Write result to promotion_gate_audit
  5. Update hypothesis_canon.tier1_result + deflated_sharpe_computed

Database operations:
  READS:  experiment_registry, outcome_ledger, hypothesis_canon
  WRITES: promotion_gate_audit, hypothesis_canon (updates only)

Usage:
    python promotion_gate_engine.py              # Evaluate all eligible
    python promotion_gate_engine.py --check      # Dry run, no writes
    python promotion_gate_engine.py --force EXP  # Force evaluate experiment

Author: STIG (CTO)
Date: 2026-01-29
Contract: EC-003_2026_PRODUCTION
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

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[PROMOTION_GATE] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/promotion_gate_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('promotion_gate')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Thresholds per Bailey & Lopez de Prado
DEFLATED_SHARPE_MIN = 1.0       # Minimum deflated Sharpe to pass
PBO_MAX = 0.50                  # Maximum PBO probability to pass
FAMILY_INFLATION_MAX = 0.30     # Maximum family-wise inflation risk

# CEO-DIR-2026-007-B: Forced Exploration Mode
# When active, top EXPLORATION_PERCENTILE hypotheses by pre_tier_score_at_birth
# qualify for SHADOW-only execution with DEFLATED_SHARPE_MIN = 0.0.
# Original 1.0 threshold preserved for any LIVE promotion path.
FORCED_EXPLORATION_MODE = True
EXPLORATION_PERCENTILE = 0.20   # Top 20% by pre_tier_score_at_birth

DAEMON_NAME = 'promotion_gate_engine'
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
                expected_interval_minutes = EXCLUDED.expected_interval_minutes,
                lifecycle_status = 'ACTIVE',
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
    """
    Compute Deflated Sharpe Ratio per Bailey & Lopez de Prado (2014).

    DSR adjusts the observed Sharpe ratio for:
    - Number of trials (multiple testing)
    - Non-normality of returns (skew, kurtosis)
    - Sample size

    Returns the deflated Sharpe estimate.
    """
    if n_observations < 2 or n_trials < 1:
        return 0.0

    # Expected maximum Sharpe under null (Euler-Mascheroni approximation)
    euler_mascheroni = 0.5772156649
    if n_trials > 1:
        e_max_sr = math.sqrt(2 * math.log(n_trials)) * (
            1 - euler_mascheroni / (2 * math.log(n_trials))
        ) + euler_mascheroni / math.sqrt(2 * math.log(n_trials))
    else:
        e_max_sr = 0.0

    # Variance of Sharpe ratio estimator (Lo, 2002)
    sr_var = (1 - skew * observed_sharpe +
              ((kurtosis - 1) / 4) * observed_sharpe ** 2) / n_observations

    if sr_var <= 0:
        return 0.0

    sr_std = math.sqrt(sr_var)

    # Deflated Sharpe = (observed - expected_max) / std
    if sr_std == 0:
        return 0.0

    deflated = (observed_sharpe - e_max_sr) / sr_std
    return round(deflated, 6)


def compute_pbo_estimate(win_rates: list, n_splits: int = 5) -> float:
    """
    Estimate Probability of Backtest Overfitting (PBO).

    Simplified approach: Use combinatorial split of outcomes to estimate
    how often in-sample best != out-of-sample best.

    For small samples, we use a conservative bootstrap estimate.
    Returns probability between 0 and 1.
    """
    n = len(win_rates)
    if n < 4:
        # Not enough data for meaningful PBO
        return 1.0  # Conservative: assume overfitted

    # Split into n_splits folds
    actual_splits = min(n_splits, n // 2)
    if actual_splits < 2:
        return 0.8  # Very conservative

    fold_size = n // actual_splits
    folds = []
    for i in range(actual_splits):
        start = i * fold_size
        end = start + fold_size if i < actual_splits - 1 else n
        fold_wr = sum(win_rates[start:end]) / max(len(win_rates[start:end]), 1)
        folds.append(fold_wr)

    # Count how many in-sample/out-of-sample pairs show degradation
    degradation_count = 0
    pair_count = 0
    for i in range(len(folds)):
        for j in range(i + 1, len(folds)):
            pair_count += 1
            # If performance drops significantly between folds
            if abs(folds[i] - folds[j]) > 0.15:
                degradation_count += 1

    if pair_count == 0:
        return 0.5

    pbo = degradation_count / pair_count
    return round(pbo, 4)


def compute_family_inflation_risk(n_hypotheses_tested: int,
                                  n_parameters: int) -> float:
    """
    Estimate family-wise error inflation risk.

    Based on the number of hypotheses tested on the same dataset
    and parameter count (degrees of freedom).
    """
    if n_hypotheses_tested <= 1 and n_parameters <= 1:
        return 0.0

    # Bonferroni-inspired risk estimate
    # More hypotheses tested = higher risk of spurious result
    hypothesis_risk = 1 - (0.95 ** n_hypotheses_tested)

    # Parameter overfitting risk
    param_risk = min(1.0, n_parameters / 20.0)  # Normalize: 20+ params = max risk

    # Combined risk (conservative: take max)
    risk = max(hypothesis_risk, param_risk)
    return round(min(risk, 1.0), 4)


def evaluate_experiment(conn, experiment: dict, dry_run: bool = False) -> dict:
    """
    Evaluate a single experiment for promotion gate.

    Returns dict with gate_result and metrics.
    """
    exp_id = experiment['experiment_id']
    hyp_id = experiment['hypothesis_id']
    exp_code = experiment['experiment_code']

    logger.info(f"Evaluating {exp_code} (experiment_id={exp_id})")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get outcomes
        cur.execute("""
            SELECT outcome_id, result_bool, return_pct, return_bps,
                   pnl_gross_simulated, mfe, mae, time_to_outcome
            FROM fhq_learning.outcome_ledger
            WHERE experiment_id = %s
            ORDER BY created_at
        """, (str(exp_id),))
        outcomes = cur.fetchall()

        # Get hypothesis details
        cur.execute("""
            SELECT canon_id, hypothesis_code, trial_count,
                   parameter_search_breadth, prior_hypotheses_count,
                   falsification_criteria, current_confidence
            FROM fhq_learning.hypothesis_canon
            WHERE canon_id = %s
        """, (str(hyp_id),))
        hypothesis = cur.fetchone()

        # Get experiment parameter count
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

    # --- Compute metrics ---

    # 1. Win rate
    wins = sum(1 for o in outcomes if o['result_bool'])
    win_rate = wins / n_outcomes

    # 2. Returns analysis
    returns = [_decimal_to_float(o['return_pct'] or 0) for o in outcomes]
    mean_return = sum(returns) / len(returns) if returns else 0
    if len(returns) > 1:
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_return = math.sqrt(variance)
    else:
        std_return = 0.001  # Avoid division by zero

    # Observed Sharpe (simplified: mean/std, no risk-free rate adjustment for short horizons)
    observed_sharpe = mean_return / std_return if std_return > 0 else 0.0

    # 3. Skew and kurtosis estimates
    if len(returns) > 2 and std_return > 0:
        skew = sum(((r - mean_return) / std_return) ** 3 for r in returns) / len(returns)
        kurtosis = sum(((r - mean_return) / std_return) ** 4 for r in returns) / len(returns)
    else:
        skew = 0.0
        kurtosis = 3.0

    # 4. Trial count for deflated Sharpe
    n_trials = max(
        hypothesis['trial_count'] or 1,
        hypothesis['prior_hypotheses_count'] or 1,
        exp_detail['prior_experiments_on_hypothesis'] or 1
    )

    # 5. Deflated Sharpe
    deflated_sharpe = compute_deflated_sharpe(
        observed_sharpe=observed_sharpe,
        n_trials=n_trials,
        n_observations=n_outcomes,
        skew=skew,
        kurtosis=kurtosis
    )

    # 6. PBO estimate
    win_sequence = [1.0 if o['result_bool'] else 0.0 for o in outcomes]
    pbo = compute_pbo_estimate(win_sequence)

    # 7. Family inflation risk
    n_params = exp_detail['parameter_count'] or 1
    family_risk = compute_family_inflation_risk(n_trials, n_params)

    # --- Gate decision ---
    failures = []
    if deflated_sharpe < DEFLATED_SHARPE_MIN:
        failures.append(f"deflated_sharpe={deflated_sharpe:.4f} < {DEFLATED_SHARPE_MIN}")
    if pbo > PBO_MAX:
        failures.append(f"pbo={pbo:.4f} > {PBO_MAX}")
    if family_risk > FAMILY_INFLATION_MAX:
        failures.append(f"family_inflation={family_risk:.4f} > {FAMILY_INFLATION_MAX}")

    # Check falsification criteria
    falsif_rule = falsif.get('falsified_if', '')
    falsified = False
    if falsif_rule:
        # Parse simple rules like "bounce_rate < 0.45"
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

    if not dry_run:
        _write_promotion_gate_audit(conn, result)
        _update_hypothesis_canon(conn, result)
        _create_eligibility_entry(conn, result)

    return result


def _write_promotion_gate_audit(conn, result: dict):
    """Write evaluation result to promotion_gate_audit."""
    with conn.cursor() as cur:
        # Check for existing audit for this hypothesis + gate
        cur.execute("""
            SELECT audit_id FROM fhq_learning.promotion_gate_audit
            WHERE hypothesis_id = %s::uuid
            AND gate_name = 'DEFLATED_SHARPE_GATE'
        """, (result['hypothesis_id'],))
        existing = cur.fetchone()

        metrics_json = json.dumps(result['metrics'], default=str)

        if existing:
            cur.execute("""
                UPDATE fhq_learning.promotion_gate_audit
                SET gate_result = %s,
                    failure_reason = %s,
                    metrics_snapshot = %s::jsonb,
                    evaluated_at = NOW(),
                    evaluated_by = 'STIG_PROMOTION_GATE_ENGINE'
                WHERE hypothesis_id = %s::uuid
                AND gate_name = 'DEFLATED_SHARPE_GATE'
            """, (
                result['gate_result'],
                result['failure_reason'],
                metrics_json,
                result['hypothesis_id']
            ))
            logger.info(f"  Updated promotion_gate_audit for {result['experiment_code']}")
        else:
            cur.execute("""
                INSERT INTO fhq_learning.promotion_gate_audit
                    (hypothesis_id, gate_name, gate_result, failure_reason,
                     metrics_snapshot, evaluated_by)
                VALUES (%s::uuid, 'DEFLATED_SHARPE_GATE', %s, %s, %s::jsonb,
                        'STIG_PROMOTION_GATE_ENGINE')
            """, (
                result['hypothesis_id'],
                result['gate_result'],
                result['failure_reason'],
                metrics_json
            ))
            logger.info(f"  Inserted promotion_gate_audit for {result['experiment_code']}")

    conn.commit()


def _update_hypothesis_canon(conn, result: dict):
    """Update hypothesis_canon with overfitting metrics."""
    metrics = result['metrics']
    tier1_result = 'PROMOTED' if result['gate_result'] == 'PASS' else 'BLOCKED'

    if metrics.get('falsified'):
        tier1_result = 'FALSIFIED'

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_learning.hypothesis_canon
            SET deflated_sharpe_computed = true,
                deflated_sharpe_estimate = %s,
                pbo_probability = %s,
                family_inflation_risk = %s,
                tier1_result = %s,
                tier1_evaluated_at = NOW(),
                sample_size = %s,
                effect_size = %s,
                last_updated_at = NOW(),
                last_updated_by = 'STIG_PROMOTION_GATE_ENGINE'
            WHERE canon_id = %s::uuid
        """, (
            metrics['deflated_sharpe'],
            metrics['pbo_probability'],
            metrics['family_inflation_risk'],
            tier1_result,
            metrics['n_outcomes'],
            metrics['mean_return_pct'],
            result['hypothesis_id']
        ))
    conn.commit()
    logger.info(f"  Updated hypothesis_canon: tier1_result={tier1_result}")


def _create_eligibility_entry(conn, result: dict):
    """Auto-create eligibility entry when promotion gate PASS.

    Fail-closed: all entries start with live_capital_blocked=true,
    leverage_blocked=true, execution_mode='SHADOW'. G4 approval required
    to unlock live capital.
    """
    if result['gate_result'] != 'PASS':
        return

    metrics = result['metrics']
    hyp_id = result['hypothesis_id']
    exp_code = result['experiment_code']
    eligibility_code = f"ELIG_{exp_code}"

    with conn.cursor() as cur:
        # Check if entry already exists
        cur.execute("""
            SELECT eligibility_id FROM fhq_learning.execution_eligibility_registry
            WHERE hypothesis_id = %s::uuid AND eligibility_code = %s
        """, (hyp_id, eligibility_code))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE fhq_learning.execution_eligibility_registry
                SET confidence_score = %s,
                    risk_adjusted_score = %s,
                    is_eligible = false,
                    eligibility_reason = %s,
                    execution_mode = 'SHADOW',
                    live_capital_blocked = true,
                    leverage_blocked = true,
                    ec022_dependency_blocked = true,
                    evaluated_at = NOW(),
                    expires_at = NOW() + INTERVAL '24 hours',
                    created_by = 'STIG_PROMOTION_GATE_ENGINE'
                WHERE hypothesis_id = %s::uuid AND eligibility_code = %s
            """, (
                metrics['deflated_sharpe'],
                metrics['observed_sharpe'],
                f"Promotion gate PASS. DSR={metrics['deflated_sharpe']:.4f}, "
                f"PBO={metrics['pbo_probability']:.4f}. Awaiting G4 for capital.",
                hyp_id,
                eligibility_code
            ))
            logger.info(f"  Updated eligibility entry: {eligibility_code}")
        else:
            cur.execute("""
                INSERT INTO fhq_learning.execution_eligibility_registry
                    (eligibility_code, hypothesis_id, tier_status,
                     confidence_score, risk_adjusted_score,
                     is_eligible, eligibility_reason,
                     execution_mode, live_capital_blocked, leverage_blocked,
                     ec022_dependency_blocked, created_by)
                VALUES (%s, %s::uuid, 'SHADOW_CANDIDATE',
                        %s, %s,
                        false, %s,
                        'SHADOW', true, true,
                        true, 'STIG_PROMOTION_GATE_ENGINE')
            """, (
                eligibility_code,
                hyp_id,
                metrics['deflated_sharpe'],
                metrics['observed_sharpe'],
                f"Promotion gate PASS. DSR={metrics['deflated_sharpe']:.4f}, "
                f"PBO={metrics['pbo_probability']:.4f}. Awaiting G4 for capital."
            ))
            logger.info(f"  Created eligibility entry: {eligibility_code} (G4-blocked)")

    conn.commit()


def find_eligible_experiments(conn) -> list:
    """Find experiments that have reached min_sample_size but not yet evaluated."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                e.experiment_id,
                e.experiment_code,
                e.hypothesis_id,
                e.parameters->>'min_sample_size' as min_sample_size,
                e.status,
                COUNT(o.outcome_id) as outcome_count,
                hc.deflated_sharpe_computed
            FROM fhq_learning.experiment_registry e
            JOIN fhq_learning.hypothesis_canon hc ON e.hypothesis_id = hc.canon_id
            LEFT JOIN fhq_learning.outcome_ledger o ON o.experiment_id = e.experiment_id
            WHERE e.status IN ('RUNNING', 'COMPLETED')
            GROUP BY e.experiment_id, e.experiment_code, e.hypothesis_id,
                     e.parameters, e.status, hc.deflated_sharpe_computed
            HAVING COUNT(o.outcome_id) >= COALESCE(
                (e.parameters->>'min_sample_size')::int, 30
            )
            ORDER BY e.experiment_code
        """)
        return cur.fetchall()


def run_exploration_pass(conn, dry_run: bool = False) -> int:
    """CEO-DIR-2026-007-B: Insert EXPLORATION_PASS for top percentile hypotheses.

    Selects hypotheses in top EXPLORATION_PERCENTILE by pre_tier_score_at_birth
    that do NOT already have a promotion_gate_audit entry, and inserts them
    with gate_result = 'EXPLORATION_PASS' for shadow-only execution.

    Returns count of inserted rows.
    """
    if not FORCED_EXPLORATION_MODE:
        return 0

    logger.info("=" * 60)
    logger.info("CEO-DIR-2026-007-B: FORCED EXPLORATION MODE")
    logger.info(f"  Percentile threshold: top {EXPLORATION_PERCENTILE*100:.0f}%")
    logger.info("=" * 60)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get the percentile cutoff
        cur.execute("""
            SELECT PERCENTILE_CONT(%s) WITHIN GROUP (ORDER BY pre_tier_score_at_birth)
            AS cutoff
            FROM fhq_learning.hypothesis_canon
            WHERE pre_tier_score_at_birth IS NOT NULL
        """, (1.0 - EXPLORATION_PERCENTILE,))
        row = cur.fetchone()
        cutoff = float(row['cutoff']) if row and row['cutoff'] else 999

        logger.info(f"  Score cutoff: >= {cutoff}")

        # Find eligible hypotheses (top percentile, no existing audit)
        cur.execute("""
            SELECT hc.canon_id, hc.hypothesis_code, hc.pre_tier_score_at_birth,
                   hc.current_confidence, hc.deflated_sharpe_estimate,
                   hc.pbo_probability, hc.family_inflation_risk
            FROM fhq_learning.hypothesis_canon hc
            LEFT JOIN fhq_learning.promotion_gate_audit pga
                ON pga.hypothesis_id = hc.canon_id
                AND pga.gate_name = 'FORCED_EXPLORATION_GATE'
            WHERE hc.pre_tier_score_at_birth >= %s
              AND hc.pre_tier_score_at_birth IS NOT NULL
              AND pga.audit_id IS NULL
            ORDER BY hc.pre_tier_score_at_birth DESC
        """, (cutoff,))
        candidates = cur.fetchall()

        logger.info(f"  Candidates: {len(candidates)}")

        if not candidates:
            logger.info("  No new candidates for exploration pass")
            return 0

        if dry_run:
            logger.info(f"  [DRY RUN] Would insert {len(candidates)} EXPLORATION_PASS entries")
            return 0

        inserted = 0
        for c in candidates:
            metrics = {
                'pre_tier_score_at_birth': float(c['pre_tier_score_at_birth'] or 0),
                'current_confidence': float(c['current_confidence'] or 0),
                'deflated_sharpe_estimate': float(c['deflated_sharpe_estimate'] or 0),
                'pbo_probability': float(c['pbo_probability'] or 0),
                'family_inflation_risk': float(c['family_inflation_risk'] or 0),
                'exploration_cutoff': cutoff,
                'exploration_percentile': EXPLORATION_PERCENTILE,
                'gate_reason': 'FORCED_EXPLORATION_CEO_DIR_2026_007',
            }

            cur.execute("""
                INSERT INTO fhq_learning.promotion_gate_audit
                    (hypothesis_id, gate_name, gate_result, failure_reason,
                     metrics_snapshot, evaluated_by)
                VALUES (%s, 'FORCED_EXPLORATION_GATE', 'EXPLORATION_PASS', NULL,
                        %s::jsonb, 'STIG_FORCED_EXPLORATION_CEO_DIR_2026_007')
            """, (
                str(c['canon_id']),
                json.dumps(metrics, default=str),
            ))
            inserted += 1

        conn.commit()
        logger.info(f"  Inserted {inserted} EXPLORATION_PASS entries")
        return inserted


def run_promotion_gate(dry_run: bool = False, force_experiment: str = None):
    """Main entry: evaluate all eligible experiments."""
    logger.info("=" * 60)
    logger.info("PROMOTION GATE ENGINE — Evaluating eligible experiments")
    logger.info(f"  dry_run={dry_run}, force={force_experiment}")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        if force_experiment:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT experiment_id, experiment_code, hypothesis_id,
                           parameters->>'min_sample_size' as min_sample_size, status
                    FROM fhq_learning.experiment_registry
                    WHERE experiment_code = %s
                """, (force_experiment,))
                experiments = cur.fetchall()
                if not experiments:
                    logger.error(f"Experiment {force_experiment} not found")
                    return
        else:
            experiments = find_eligible_experiments(conn)

        if not experiments:
            logger.info("No experiments eligible for promotion gate evaluation")
            logger.info("Criteria: outcomes >= min_sample_size")

            # Report current progress toward eligibility
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT e.experiment_code,
                           COALESCE((e.parameters->>'min_sample_size')::int, 30) as min_sample,
                           COUNT(o.outcome_id) as outcomes
                    FROM fhq_learning.experiment_registry e
                    LEFT JOIN fhq_learning.outcome_ledger o ON o.experiment_id = e.experiment_id
                    WHERE e.status = 'RUNNING'
                    GROUP BY e.experiment_code, e.parameters
                    ORDER BY e.experiment_code
                """)
                progress = cur.fetchall()
                for p in progress:
                    pct = round(100 * p['outcomes'] / p['min_sample'])
                    logger.info(f"  {p['experiment_code']}: "
                                f"{p['outcomes']}/{p['min_sample']} ({pct}%)")
            return

        results = []
        for exp in experiments:
            result = evaluate_experiment(conn, exp, dry_run=dry_run)
            if result:
                results.append(result)

        # Summary
        logger.info("=" * 60)
        logger.info(f"PROMOTION GATE SUMMARY: {len(results)} experiments evaluated")
        passed = [r for r in results if r['gate_result'] == 'PASS']
        failed = [r for r in results if r['gate_result'] == 'FAIL']
        logger.info(f"  PASS: {len(passed)}")
        logger.info(f"  FAIL: {len(failed)}")
        for r in results:
            logger.info(f"  {r['experiment_code']}: {r['gate_result']}")

        # CEO-DIR-2026-007-B: Run forced exploration pass
        exploration_count = run_exploration_pass(conn, dry_run=dry_run)

        # Write evidence
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_path = os.path.join(
            evidence_dir, f'PROMOTION_GATE_EVALUATION_{ts}.json'
        )
        evidence = {
            'evaluated_at': datetime.now(timezone.utc).isoformat(),
            'evaluated_by': 'STIG_PROMOTION_GATE_ENGINE',
            'dry_run': dry_run,
            'experiments_evaluated': len(results),
            'passed': len(passed),
            'failed': len(failed),
            'exploration_pass_inserted': exploration_count,
            'results': results,
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

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Promotion Gate Engine')
    parser.add_argument('--check', action='store_true', help='Dry run, no writes')
    parser.add_argument('--force', type=str, help='Force evaluate specific experiment code')
    args = parser.parse_args()

    run_promotion_gate(dry_run=args.check, force_experiment=args.force)


if __name__ == '__main__':
    main()
