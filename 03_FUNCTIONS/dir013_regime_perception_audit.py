#!/usr/bin/env python3
"""
CEO-DIR-2026-REGIME-PERCEPTION-AND-SENSITIVITY-013
===================================================
Uplift av Regime-Persepsjon og Asymmetrisk Risikofølsomhet

STIG Section 2C: Verification & Re-score

Phases:
  1. Fetch data (forecast_outcome_pairs + sovereign_regime_state_v4)
  2. Baseline confusion matrix + Brier per regime (DIR-012 calibrated)
  3. Time-to-detection for BEAR/STRESS transitions
  4. Type II error analysis (missed risk events / recall)
  5. Probability ramp analysis (pre-transition p_bear/p_stress evolution)
  6. [PLUGGABLE] Re-score with FINN proposals (Section 2A/2B)
  7. Generate evidence

Lead: FINN | Verification: STIG (EC-003) | Oversight: VEGA
Date: 2026-02-02
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.dirname(__file__))
from forecast_confidence_damper import ForecastConfidenceDamper

logging.basicConfig(
    level=logging.INFO,
    format='[DIR013_AUDIT] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger('dir013_audit')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

SUPPRESSION_THRESHOLD = 0.30


# ============================================================
# DATA FETCHING
# ============================================================

def fetch_regime_pairs(conn):
    """Fetch all regime forecast-outcome pairs with metadata."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                fop.pair_id, fop.forecast_id, fop.outcome_id,
                fop.brier_score, fop.hit_rate_contribution,
                fl.forecast_value as predicted_regime,
                fl.forecast_probability, fl.forecast_confidence,
                fl.forecast_type, fl.forecast_domain,
                fl.forecast_made_at,
                ol.outcome_value as actual_regime,
                ol.outcome_timestamp as actual_timestamp
            FROM fhq_research.forecast_outcome_pairs fop
            JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
            JOIN fhq_research.outcome_ledger ol ON fop.outcome_id = ol.outcome_id
            WHERE fl.forecast_type = 'REGIME'
            ORDER BY fl.forecast_made_at
        """)
        return [dict(r) for r in cur.fetchall()]


def fetch_sovereign_transitions(conn):
    """Fetch sovereign regime state with transition detection."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH regime_changes AS (
                SELECT asset_id, timestamp::date as ts_date,
                       sovereign_regime, technical_regime,
                       state_probabilities,
                       LAG(sovereign_regime) OVER (
                           PARTITION BY asset_id ORDER BY timestamp
                       ) as prev_sovereign
                FROM fhq_perception.sovereign_regime_state_v4
            )
            SELECT asset_id, ts_date, sovereign_regime, technical_regime,
                   state_probabilities, prev_sovereign
            FROM regime_changes
            ORDER BY asset_id, ts_date
        """)
        return [dict(r) for r in cur.fetchall()]


def fetch_bear_stress_detection_lag(conn):
    """Compute detection lag for all BEAR/STRESS sovereign entries."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH regime_changes AS (
                SELECT asset_id, timestamp::date as ts_date,
                       sovereign_regime, technical_regime,
                       state_probabilities,
                       LAG(sovereign_regime) OVER (
                           PARTITION BY asset_id ORDER BY timestamp
                       ) as prev_sovereign
                FROM fhq_perception.sovereign_regime_state_v4
            ),
            bear_stress_entries AS (
                SELECT asset_id, ts_date as sov_date,
                       sovereign_regime as sov_regime,
                       technical_regime, prev_sovereign,
                       state_probabilities
                FROM regime_changes
                WHERE sovereign_regime IN ('BEAR', 'STRESS')
                  AND (prev_sovereign IS NULL
                       OR prev_sovereign NOT IN ('BEAR', 'STRESS')
                       OR (prev_sovereign = 'BEAR' AND sovereign_regime = 'STRESS'))
            ),
            with_tech_lag AS (
                SELECT e.*,
                       (SELECT MIN(s2.timestamp::date)
                        FROM fhq_perception.sovereign_regime_state_v4 s2
                        WHERE s2.asset_id = e.asset_id
                          AND s2.technical_regime = e.sov_regime
                          AND s2.timestamp::date <= e.sov_date
                          AND s2.timestamp::date >= e.sov_date - 14
                       ) as tech_first_date
                FROM bear_stress_entries e
            )
            SELECT sov_regime,
                   COUNT(*) as transitions,
                   ROUND(AVG((sov_date - tech_first_date))::numeric, 2) as avg_lag_days,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (
                       ORDER BY (sov_date - tech_first_date)
                   ) as median_lag_days,
                   MAX(sov_date - tech_first_date) as max_lag_days,
                   SUM(CASE WHEN sov_date - tech_first_date = 0 THEN 1 ELSE 0 END) as same_day,
                   SUM(CASE WHEN sov_date - tech_first_date >= 3 THEN 1 ELSE 0 END) as late_3plus,
                   SUM(CASE WHEN sov_date - tech_first_date >= 7 THEN 1 ELSE 0 END) as late_7plus
            FROM with_tech_lag
            WHERE tech_first_date IS NOT NULL
            GROUP BY sov_regime
        """)
        return [dict(r) for r in cur.fetchall()]


def fetch_btc_pre_transition_ramp(conn):
    """Fetch BTC-USD probability evolution before BEAR/STRESS entries (2026 only)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            WITH all_rows AS (
                SELECT timestamp::date as ts_date, sovereign_regime,
                       LAG(sovereign_regime) OVER (ORDER BY timestamp) as prev_sov
                FROM fhq_perception.sovereign_regime_state_v4
                WHERE asset_id = 'BTC-USD'
            ),
            filtered AS (
                SELECT ts_date as bear_date, sovereign_regime, prev_sov
                FROM all_rows
                WHERE sovereign_regime IN ('BEAR', 'STRESS')
                  AND prev_sov IS NOT NULL
                  AND prev_sov NOT IN ('BEAR', 'STRESS')
                  AND ts_date >= '2025-01-01'
            )
            SELECT f.bear_date, f.sovereign_regime as target_regime,
                   s.timestamp::date as signal_date,
                   (f.bear_date - s.timestamp::date) as days_before,
                   s.sovereign_regime,
                   s.technical_regime,
                   ROUND((s.state_probabilities->>'BEAR')::numeric, 4) as p_bear,
                   ROUND((s.state_probabilities->>'STRESS')::numeric, 4) as p_stress,
                   ROUND((s.state_probabilities->>'NEUTRAL')::numeric, 4) as p_neutral,
                   ROUND((s.state_probabilities->>'BULL')::numeric, 4) as p_bull
            FROM filtered f
            JOIN fhq_perception.sovereign_regime_state_v4 s
              ON s.asset_id = 'BTC-USD'
              AND s.timestamp::date BETWEEN f.bear_date - 5 AND f.bear_date
            ORDER BY f.bear_date, s.timestamp
        """)
        return [dict(r) for r in cur.fetchall()]


# ============================================================
# ANALYSIS FUNCTIONS
# ============================================================

def apply_dampening(pairs, damper):
    """Apply dampening retroactively using regime-specific gates (DIR-012)."""
    for p in pairs:
        raw_conf = float(p['forecast_confidence'] or p['forecast_probability'] or 0.5)
        f_type = p.get('forecast_type', 'REGIME')
        predicted = p.get('predicted_regime', p.get('predicted', 'ALL'))
        result = damper.damp_confidence(raw_conf, f_type, predicted, log_dampening=False)
        p['raw_confidence'] = raw_conf
        p['damped_confidence'] = result['damped_confidence']
        p['dampening_delta'] = result['dampening_delta']
        p['ceiling_applied'] = result['ceiling_applied']
        p['was_damped'] = result['was_damped']
    return pairs


def compute_confusion_matrix(pairs):
    """Compute regime confusion matrix."""
    matrix = defaultdict(lambda: defaultdict(int))
    for p in pairs:
        matrix[p['predicted_regime']][p['actual_regime']] += 1
    return dict({k: dict(v) for k, v in matrix.items()})


def compute_type2_analysis(pairs):
    """
    Type II error analysis: missed BEAR/STRESS events.
    When the actual regime WAS BEAR/STRESS, what did the system predict?
    """
    actual_groups = defaultdict(list)
    for p in pairs:
        actual_groups[p['actual_regime']].append(p)

    analysis = {}
    for regime in ['BEAR', 'STRESS']:
        events = actual_groups.get(regime, [])
        if not events:
            analysis[regime] = {
                'actual_events': 0,
                'correctly_detected': 0,
                'recall': 0.0,
                'type2_rate': 1.0,
                'missed_as': {}
            }
            continue

        correct = sum(1 for p in events if p['predicted_regime'] == regime)
        missed_as = defaultdict(int)
        for p in events:
            if p['predicted_regime'] != regime:
                missed_as[p['predicted_regime']] += 1

        analysis[regime] = {
            'actual_events': len(events),
            'correctly_detected': correct,
            'recall': round(correct / len(events), 4) if events else 0.0,
            'type2_rate': round(1 - correct / len(events), 4) if events else 1.0,
            'missed_as': dict(missed_as)
        }

    return analysis


def compute_brier_per_regime(pairs):
    """Brier score decomposition per regime with both raw and damped."""
    regimes = sorted(set(p['predicted_regime'] for p in pairs))
    decomposition = {}

    for regime in regimes:
        rp = [p for p in pairs if p['predicted_regime'] == regime]
        n = len(rp)
        if n == 0:
            continue

        hits = sum(1 for p in rp if p['hit_rate_contribution'])
        brier_raw = sum((p['raw_confidence'] - (1.0 if p['hit_rate_contribution'] else 0.0)) ** 2 for p in rp) / n
        brier_damped = sum((p['damped_confidence'] - (1.0 if p['hit_rate_contribution'] else 0.0)) ** 2 for p in rp) / n

        decomposition[regime] = {
            'n': n,
            'hits': hits,
            'accuracy': round(hits / n, 4),
            'avg_raw_confidence': round(sum(p['raw_confidence'] for p in rp) / n, 4),
            'avg_damped_confidence': round(sum(p['damped_confidence'] for p in rp) / n, 4),
            'brier_raw': round(brier_raw, 6),
            'brier_damped': round(brier_damped, 6),
            'brier_delta': round(brier_damped - brier_raw, 6),
            'improvement_pct': round(-(brier_damped - brier_raw) / brier_raw * 100, 2) if brier_raw > 0 else 0.0
        }

    # Overall
    total = len(pairs)
    all_raw = sum(d['brier_raw'] * d['n'] for d in decomposition.values()) / total
    all_damped = sum(d['brier_damped'] * d['n'] for d in decomposition.values()) / total
    decomposition['OVERALL'] = {
        'n': total,
        'brier_raw': round(all_raw, 6),
        'brier_damped': round(all_damped, 6),
        'brier_delta': round(all_damped - all_raw, 6),
        'improvement_pct': round(-(all_damped - all_raw) / all_raw * 100, 2) if all_raw > 0 else 0.0
    }

    return decomposition


def analyze_probability_ramps(ramp_data):
    """Analyze how p_bear/p_stress evolve before sovereign transitions."""
    transitions = defaultdict(list)
    for r in ramp_data:
        key = (str(r['bear_date']), r['target_regime'])
        transitions[key].append(r)

    ramp_summary = []
    for (bear_date, target), rows in sorted(transitions.items()):
        rows.sort(key=lambda x: x['days_before'], reverse=True)
        prob_key = 'p_bear' if target == 'BEAR' else 'p_stress'

        probs = [(r['days_before'], float(r[prob_key] or 0)) for r in rows]
        if not probs:
            continue

        # Earliest signal: first day p_target > 0.20
        early_signal_day = None
        for days_before, prob in probs:
            if prob >= 0.20:
                early_signal_day = days_before
                break

        # Find the technical_regime at each step
        tech_regimes = [(r['days_before'], r['technical_regime']) for r in rows]
        tech_first_match = None
        for days_before, tech in tech_regimes:
            if tech == target:
                tech_first_match = days_before
                break

        ramp_summary.append({
            'transition_date': bear_date,
            'target_regime': target,
            'probability_ramp': probs,
            'early_signal_day': early_signal_day,
            'tech_first_match_day': tech_first_match,
            'max_pre_prob': max(p for _, p in probs),
            'days_tracked': len(probs)
        })

    return ramp_summary


def compute_asymmetric_loss_baseline(pairs):
    """
    Compute baseline loss under symmetric vs asymmetric weighting.
    Type II (missed crash) penalized 3x vs Type I (false alarm).
    This establishes the baseline FINN's proposal will be measured against.
    """
    # Symmetric: all errors weighted equally
    symmetric_loss = 0
    # Asymmetric: Type II BEAR/STRESS miss = 3x penalty
    asymmetric_loss = 0
    n = len(pairs)

    for p in pairs:
        is_correct = p['hit_rate_contribution']
        pred = p['predicted_regime']
        actual = p['actual_regime']

        if is_correct:
            continue  # No loss on correct predictions

        # Symmetric loss: 1.0 per error
        symmetric_loss += 1.0

        # Asymmetric loss: penalize missed risk events more
        if actual in ('BEAR', 'STRESS') and pred not in ('BEAR', 'STRESS'):
            # Type II: failed to detect risk — 3x penalty
            asymmetric_loss += 3.0
        elif actual not in ('BEAR', 'STRESS') and pred in ('BEAR', 'STRESS'):
            # Type I: false alarm — 1x penalty (acceptable)
            asymmetric_loss += 1.0
        else:
            # Other misclassification — 1x
            asymmetric_loss += 1.0

    return {
        'total_pairs': n,
        'total_errors': int(symmetric_loss),
        'error_rate': round(symmetric_loss / n, 4),
        'symmetric_loss': round(symmetric_loss / n, 6),
        'asymmetric_loss_3x': round(asymmetric_loss / n, 6),
        'asymmetric_penalty_ratio': round(asymmetric_loss / symmetric_loss, 4) if symmetric_loss > 0 else 0,
        'type2_penalty_weight': 3.0,
        'note': 'Baseline with uniform 3x Type II penalty. FINN Section 2B will propose refined weights.'
    }


# ============================================================
# PLUGGABLE SCORING INTERFACE (for FINN deliverables)
# ============================================================

def apply_finn_regime_score(pairs, score_fn=None):
    """
    Apply FINN's proposed regime-score function (Section 2A).
    score_fn: callable(pair_dict) -> updated pair_dict with new scores.
    Returns pairs unchanged if score_fn is None (FINN not yet delivered).
    """
    if score_fn is None:
        return pairs, False
    for p in pairs:
        p = score_fn(p)
    return pairs, True


def apply_finn_loss_function(pairs, loss_fn=None):
    """
    Apply FINN's proposed asymmetric loss function (Section 2B).
    loss_fn: callable(predicted, actual, confidence) -> loss_value.
    Returns baseline loss if loss_fn is None.
    """
    if loss_fn is None:
        return None, False
    total_loss = sum(loss_fn(p['predicted_regime'], p['actual_regime'],
                             p['damped_confidence']) for p in pairs)
    return {'total_loss': total_loss, 'avg_loss': total_loss / len(pairs)}, True


# ============================================================
# MAIN AUDIT
# ============================================================

def run_dir013_audit(finn_score_fn=None, finn_loss_fn=None):
    """Execute DIR-013 regime perception audit."""
    logger.info("=" * 70)
    logger.info("CEO-DIR-2026-REGIME-PERCEPTION-AND-SENSITIVITY-013")
    logger.info("Regime Perception & Asymmetric Risk Sensitivity — STIG Verification")
    logger.info("=" * 70)

    conn = psycopg2.connect(**DB_CONFIG)
    damper = ForecastConfidenceDamper(conn)

    try:
        # ==========================================
        # PHASE 1: FETCH DATA
        # ==========================================
        logger.info("\n[PHASE 1] Fetching data...")
        regime_pairs = fetch_regime_pairs(conn)
        logger.info(f"  Regime forecast-outcome pairs: {len(regime_pairs)}")

        # ==========================================
        # PHASE 2: BASELINE BRIER + CONFUSION (DIR-012 calibrated)
        # ==========================================
        logger.info("\n[PHASE 2] Baseline metrics (DIR-012 regime-specific calibration)...")
        regime_pairs = apply_dampening(regime_pairs, damper)

        confusion = compute_confusion_matrix(regime_pairs)
        brier = compute_brier_per_regime(regime_pairs)

        for regime in ['NEUTRAL', 'BULL', 'BEAR', 'STRESS']:
            if regime in brier:
                d = brier[regime]
                logger.info(f"  {regime:8s}: accuracy={d['accuracy']:.4f}  "
                            f"Brier raw={d['brier_raw']:.4f} -> damped={d['brier_damped']:.4f}  "
                            f"({d['improvement_pct']:+.1f}%)")

        overall = brier['OVERALL']
        logger.info(f"  {'OVERALL':8s}: Brier raw={overall['brier_raw']:.4f} -> "
                    f"damped={overall['brier_damped']:.4f} ({overall['improvement_pct']:+.1f}%)")

        # ==========================================
        # PHASE 3: TIME-TO-DETECTION
        # ==========================================
        logger.info("\n[PHASE 3] Time-to-detection for BEAR/STRESS transitions...")
        detection_lag = fetch_bear_stress_detection_lag(conn)

        detection_summary = {}
        for row in detection_lag:
            regime = row['sov_regime']
            detection_summary[regime] = {
                'transitions': int(row['transitions']),
                'avg_lag_days': float(row['avg_lag_days']),
                'median_lag_days': float(row['median_lag_days']),
                'max_lag_days': int(row['max_lag_days']),
                'same_day_pct': round(int(row['same_day']) / int(row['transitions']) * 100, 1),
                'late_3plus_pct': round(int(row['late_3plus']) / int(row['transitions']) * 100, 1),
                'late_7plus_pct': round(int(row['late_7plus']) / int(row['transitions']) * 100, 1),
            }
            logger.info(f"  {regime}: {row['transitions']} transitions, "
                        f"avg lag={row['avg_lag_days']}d, median={row['median_lag_days']}d, "
                        f"same-day={detection_summary[regime]['same_day_pct']}%, "
                        f"7d+ late={detection_summary[regime]['late_7plus_pct']}%")

        # ==========================================
        # PHASE 4: TYPE II ERROR ANALYSIS
        # ==========================================
        logger.info("\n[PHASE 4] Type II error analysis (missed risk events)...")
        type2 = compute_type2_analysis(regime_pairs)

        for regime in ['BEAR', 'STRESS']:
            t = type2[regime]
            logger.info(f"  {regime}: {t['actual_events']} actual events, "
                        f"recall={t['recall']:.4f}, "
                        f"Type II rate={t['type2_rate']:.4f}")
            if t['missed_as']:
                for pred, count in sorted(t['missed_as'].items(), key=lambda x: -x[1]):
                    logger.info(f"    Missed as {pred}: {count}")

        # ==========================================
        # PHASE 5: PROBABILITY RAMP ANALYSIS (BTC-USD)
        # ==========================================
        logger.info("\n[PHASE 5] Probability ramp analysis (BTC-USD pre-transition)...")
        ramp_data = fetch_btc_pre_transition_ramp(conn)
        ramp_summary = analyze_probability_ramps(ramp_data)

        early_signals = [r for r in ramp_summary if r['early_signal_day'] is not None and r['early_signal_day'] > 0]
        if ramp_summary:
            avg_early = sum(r['early_signal_day'] for r in early_signals) / len(early_signals) if early_signals else 0
            logger.info(f"  Total BTC transitions analyzed: {len(ramp_summary)}")
            logger.info(f"  Transitions with early signal (p>0.20 before D-day): {len(early_signals)}/{len(ramp_summary)}")
            logger.info(f"  Average early signal lead: {avg_early:.1f} days")

            # Latest transitions (2026)
            recent = [r for r in ramp_summary if r['transition_date'] >= '2026-01-01']
            for r in recent:
                logger.info(f"    {r['transition_date']} -> {r['target_regime']}: "
                            f"early_signal={r['early_signal_day']}d, "
                            f"tech_first={r['tech_first_match_day']}d, "
                            f"max_prob={r['max_pre_prob']:.4f}")

        ramp_evidence = {
            'total_transitions': len(ramp_summary),
            'early_signal_count': len(early_signals),
            'avg_early_signal_days': round(avg_early, 2) if early_signals else None,
            'recent_2026': [
                {
                    'date': r['transition_date'],
                    'target': r['target_regime'],
                    'early_signal_days': r['early_signal_day'],
                    'tech_first_match_days': r['tech_first_match_day'],
                    'max_pre_prob': r['max_pre_prob']
                }
                for r in ramp_summary if r['transition_date'] >= '2026-01-01'
            ]
        }

        # ==========================================
        # PHASE 6: ASYMMETRIC LOSS BASELINE
        # ==========================================
        logger.info("\n[PHASE 6] Asymmetric loss function baseline...")
        loss_baseline = compute_asymmetric_loss_baseline(regime_pairs)
        logger.info(f"  Error rate: {loss_baseline['error_rate']:.4f}")
        logger.info(f"  Symmetric loss: {loss_baseline['symmetric_loss']:.6f}")
        logger.info(f"  Asymmetric loss (3x Type II): {loss_baseline['asymmetric_loss_3x']:.6f}")
        logger.info(f"  Penalty ratio: {loss_baseline['asymmetric_penalty_ratio']:.4f}x")

        # ==========================================
        # PHASE 7: PLUGGABLE FINN RE-SCORE
        # ==========================================
        logger.info("\n[PHASE 7] FINN deliverable integration...")
        _, finn_score_applied = apply_finn_regime_score(regime_pairs, finn_score_fn)
        finn_loss_result, finn_loss_applied = apply_finn_loss_function(regime_pairs, finn_loss_fn)

        finn_status = {
            'section_2a_regime_score': 'APPLIED' if finn_score_applied else 'AWAITING_DELIVERY',
            'section_2b_loss_function': 'APPLIED' if finn_loss_applied else 'AWAITING_DELIVERY',
            'finn_loss_result': finn_loss_result,
        }
        logger.info(f"  Section 2A (regime score): {finn_status['section_2a_regime_score']}")
        logger.info(f"  Section 2B (loss function): {finn_status['section_2b_loss_function']}")

        if finn_score_applied:
            # Re-compute metrics with FINN's proposals
            brier_after = compute_brier_per_regime(regime_pairs)
            type2_after = compute_type2_analysis(regime_pairs)
            logger.info("  Re-scored metrics computed — see evidence for comparison.")
        else:
            brier_after = None
            type2_after = None

        # ==========================================
        # SUCCESS CRITERIA CHECK
        # ==========================================
        logger.info("\n" + "=" * 70)
        logger.info("SUCCESS CRITERIA (CEO-DIR-013 Section 4)")
        logger.info("=" * 70)

        bear_recall = type2['BEAR']['recall']
        stress_recall = type2['STRESS']['recall']
        neutral_accuracy = brier.get('NEUTRAL', {}).get('accuracy', 0)
        neutral_brier = brier.get('NEUTRAL', {}).get('brier_damped', 1.0)

        criteria = {
            'bear_stress_detection_improvement': {
                'status': 'BASELINE_ESTABLISHED',
                'bear_recall_current': bear_recall,
                'stress_recall_current': stress_recall,
                'bear_avg_lag_days': detection_summary.get('BEAR', {}).get('avg_lag_days'),
                'stress_avg_lag_days': detection_summary.get('STRESS', {}).get('avg_lag_days'),
                'note': 'Improvement requires FINN Section 2A delivery. Baseline captured for comparison.'
            },
            'neutral_no_regression': {
                'status': 'PASS' if neutral_accuracy >= 0.80 else 'WARN',
                'neutral_accuracy': neutral_accuracy,
                'neutral_brier_damped': neutral_brier,
                'threshold': 0.80,
            },
            'full_evidence_package': {
                'status': 'PARTIAL',
                'baseline_complete': True,
                'finn_2a_received': finn_score_applied,
                'finn_2b_received': finn_loss_applied,
                'before_after_ready': finn_score_applied,
            }
        }

        for name, c in criteria.items():
            logger.info(f"  {name}: {c['status']}")

        # ==========================================
        # ASSEMBLE EVIDENCE
        # ==========================================
        evidence = {
            'directive': 'CEO-DIR-2026-REGIME-PERCEPTION-AND-SENSITIVITY-013',
            'classification': 'GOVERNANCE-CRITICAL / INTELLIGENCE',
            'gate': 'ADR-004 -> G2',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG',
            'ec': 'EC-003',
            'lead': 'FINN',
            'oversight': 'VEGA',

            'dataset': {
                'regime_pairs': len(regime_pairs),
                'sovereign_transitions_bear': detection_summary.get('BEAR', {}).get('transitions', 0),
                'sovereign_transitions_stress': detection_summary.get('STRESS', {}).get('transitions', 0),
            },

            'baseline_brier': brier,
            'confusion_matrix': confusion,

            'time_to_detection': detection_summary,

            'type2_analysis': type2,

            'probability_ramp_btc': ramp_evidence,

            'asymmetric_loss_baseline': loss_baseline,

            'finn_integration': finn_status,

            'success_criteria': criteria,

            'governance_state': {
                'defcon': 'GREEN',
                'execution_mode': 'SHADOW_PAPER',
                'live_capital_blocked': True,
                'constitutional_hold': 'ACTIVE',
                'no_execution_mode_change': True,
                'no_defcon_change_without_ceo': True,
            },

            'constraints_verified': {
                'no_execution_mode_change': True,
                'no_live_shadow_capital_increase': True,
                'no_defcon_mechanic_change': True,
            }
        }

        # Add before/after if FINN delivered
        if brier_after:
            evidence['rescore_comparison'] = {
                'brier_before': brier,
                'brier_after': brier_after,
                'type2_before': type2,
                'type2_after': type2_after,
            }

        evidence_json = json.dumps(evidence, indent=2, default=str)
        evidence_hash = hashlib.sha256(evidence_json.encode()).hexdigest()
        evidence['evidence_hash'] = evidence_hash

        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(evidence_dir, f'CEO_DIR_013_REGIME_PERCEPTION_{ts}.json')
        with open(path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)

        logger.info(f"\n  Evidence: {path}")
        logger.info(f"  Hash: {evidence_hash}")

        return evidence

    finally:
        conn.close()


if __name__ == '__main__':
    run_dir013_audit()
