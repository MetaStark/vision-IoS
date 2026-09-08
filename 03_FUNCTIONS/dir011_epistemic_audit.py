#!/usr/bin/env python3
"""
CEO-DIR-2026-EPISTEMIC-LOCK-AND-PROOF-011
==========================================
Epistemic Proof Lock — Regime Perception Validation

Controlled epistemic audit comparing:
  - Pre-DIR-010 regime predictions (NULL-damped baseline)
  - Post-DIR-010 regime predictions (damped via calibration layer)

Deliverables:
  1. Before/After Regime Confusion Matrices
  2. Confidence Calibration Curves (raw vs damped)
  3. Brier Score Decomposition per regime
  4. False Suppression Regret Re-measurement

Lead: FINN | Support: STIG (EC-003) | Oversight: VEGA
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
    format='[DIR011_AUDIT] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger('dir011_audit')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Suppression threshold: predictions below this damped confidence are suppressed
SUPPRESSION_THRESHOLD = 0.30


def fetch_regime_pairs(conn):
    """Fetch all regime forecast-outcome pairs with full metadata."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                fop.pair_id,
                fop.forecast_id,
                fop.outcome_id,
                fop.brier_score,
                fop.hit_rate_contribution,
                fl.forecast_value as predicted_regime,
                fl.forecast_probability,
                fl.forecast_confidence,
                fl.forecast_type,
                fl.forecast_domain,
                ol.outcome_value as actual_regime
            FROM fhq_research.forecast_outcome_pairs fop
            JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
            JOIN fhq_research.outcome_ledger ol ON fop.outcome_id = ol.outcome_id
            WHERE fl.forecast_type = 'REGIME'
            ORDER BY fl.forecast_made_at
        """)
        return [dict(r) for r in cur.fetchall()]


def fetch_all_pairs(conn):
    """Fetch ALL forecast-outcome pairs for suppression regret analysis."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                fop.pair_id,
                fop.brier_score,
                fop.hit_rate_contribution,
                fl.forecast_value as predicted,
                fl.forecast_probability,
                fl.forecast_confidence,
                fl.forecast_type,
                ol.outcome_value as actual
            FROM fhq_research.forecast_outcome_pairs fop
            JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
            JOIN fhq_research.outcome_ledger ol ON fop.outcome_id = ol.outcome_id
            ORDER BY fl.forecast_made_at
        """)
        return [dict(r) for r in cur.fetchall()]


def apply_dampening(pairs, damper):
    """Apply dampening retroactively to all pairs using regime-specific gates."""
    for p in pairs:
        raw_conf = float(p['forecast_confidence'] or p['forecast_probability'] or 0.5)
        f_type = p.get('forecast_type', 'REGIME')
        # CEO-DIR-012: pass predicted regime for regime-specific ceilings
        predicted = p.get('predicted_regime', p.get('predicted', 'ALL'))
        result = damper.damp_confidence(raw_conf, f_type, predicted, log_dampening=False)
        p['raw_confidence'] = raw_conf
        p['damped_confidence'] = result['damped_confidence']
        p['dampening_delta'] = result['dampening_delta']
        p['ceiling_applied'] = result['ceiling_applied']
        p['was_damped'] = result['was_damped']
    return pairs


def compute_confusion_matrix(pairs):
    """Compute regime confusion matrix from pairs."""
    matrix = defaultdict(lambda: defaultdict(int))
    for p in pairs:
        pred = p['predicted_regime']
        actual = p['actual_regime']
        matrix[pred][actual] += 1
    return dict({k: dict(v) for k, v in matrix.items()})


def compute_calibration_curves(pairs, bins=None):
    """Compute calibration curves for raw and damped confidence."""
    if bins is None:
        bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]

    raw_curve = []
    damped_curve = []

    for lo, hi in bins:
        # Raw confidence bin
        raw_in_bin = [p for p in pairs if lo <= p['raw_confidence'] < hi]
        if raw_in_bin:
            avg_raw = sum(p['raw_confidence'] for p in raw_in_bin) / len(raw_in_bin)
            actual_hit = sum(1 for p in raw_in_bin if p['hit_rate_contribution']) / len(raw_in_bin)
            raw_curve.append({
                'bin': f'{lo:.1f}-{hi:.1f}',
                'n': len(raw_in_bin),
                'avg_stated_confidence': round(avg_raw, 4),
                'actual_accuracy': round(actual_hit, 4),
                'calibration_gap': round(avg_raw - actual_hit, 4),
                'direction': 'OVER' if avg_raw > actual_hit else 'UNDER'
            })

        # Damped confidence bin
        damped_in_bin = [p for p in pairs if lo <= p['damped_confidence'] < hi]
        if damped_in_bin:
            avg_damped = sum(p['damped_confidence'] for p in damped_in_bin) / len(damped_in_bin)
            actual_hit = sum(1 for p in damped_in_bin if p['hit_rate_contribution']) / len(damped_in_bin)
            damped_curve.append({
                'bin': f'{lo:.1f}-{hi:.1f}',
                'n': len(damped_in_bin),
                'avg_stated_confidence': round(avg_damped, 4),
                'actual_accuracy': round(actual_hit, 4),
                'calibration_gap': round(avg_damped - actual_hit, 4),
                'direction': 'OVER' if avg_damped > actual_hit else 'UNDER'
            })

    return raw_curve, damped_curve


def compute_brier_decomposition(pairs):
    """Compute Brier score decomposition per regime, pre and post dampening."""
    regimes = set(p['predicted_regime'] for p in pairs)
    decomposition = {}

    for regime in sorted(regimes):
        regime_pairs = [p for p in pairs if p['predicted_regime'] == regime]
        n = len(regime_pairs)
        if n == 0:
            continue

        # Pre-dampening: Brier using raw confidence as probability
        brier_raw_values = []
        brier_damped_values = []
        for p in regime_pairs:
            is_correct = 1.0 if p['hit_rate_contribution'] else 0.0
            raw_prob = p['raw_confidence']
            damped_prob = p['damped_confidence']

            brier_raw = (raw_prob - is_correct) ** 2
            brier_damped = (damped_prob - is_correct) ** 2

            brier_raw_values.append(brier_raw)
            brier_damped_values.append(brier_damped)

        avg_brier_raw = sum(brier_raw_values) / n
        avg_brier_damped = sum(brier_damped_values) / n
        delta = avg_brier_damped - avg_brier_raw
        hits = sum(1 for p in regime_pairs if p['hit_rate_contribution'])
        hit_rate = hits / n

        decomposition[regime] = {
            'n': n,
            'hits': hits,
            'hit_rate': round(hit_rate, 4),
            'avg_raw_confidence': round(sum(p['raw_confidence'] for p in regime_pairs) / n, 4),
            'avg_damped_confidence': round(sum(p['damped_confidence'] for p in regime_pairs) / n, 4),
            'brier_raw': round(avg_brier_raw, 6),
            'brier_damped': round(avg_brier_damped, 6),
            'brier_delta': round(delta, 6),
            'improvement': delta < 0,
            'improvement_pct': round(-delta / avg_brier_raw * 100, 2) if avg_brier_raw > 0 else 0.0
        }

    # Overall
    all_brier_raw = sum(d['brier_raw'] * d['n'] for d in decomposition.values()) / len(pairs)
    all_brier_damped = sum(d['brier_damped'] * d['n'] for d in decomposition.values()) / len(pairs)
    decomposition['OVERALL'] = {
        'n': len(pairs),
        'brier_raw': round(all_brier_raw, 6),
        'brier_damped': round(all_brier_damped, 6),
        'brier_delta': round(all_brier_damped - all_brier_raw, 6),
        'improvement': all_brier_damped < all_brier_raw,
        'improvement_pct': round(-(all_brier_damped - all_brier_raw) / all_brier_raw * 100, 2) if all_brier_raw > 0 else 0.0
    }

    return decomposition


def compute_suppression_regret(all_pairs, threshold=SUPPRESSION_THRESHOLD):
    """
    Re-measure suppression regret with dampened confidence.
    A prediction is 'suppressed' if damped_confidence < threshold.
    Regret = suppressed prediction that was actually correct.
    """
    suppressed = [p for p in all_pairs if p['damped_confidence'] < threshold]
    not_suppressed = [p for p in all_pairs if p['damped_confidence'] >= threshold]

    total_suppressed = len(suppressed)
    suppressed_correct = sum(1 for p in suppressed if p['hit_rate_contribution'])
    suppressed_wrong = total_suppressed - suppressed_correct

    total_not_suppressed = len(not_suppressed)
    not_suppressed_correct = sum(1 for p in not_suppressed if p['hit_rate_contribution'])

    regret_rate = suppressed_correct / total_suppressed if total_suppressed > 0 else 0.0
    wisdom_rate = suppressed_wrong / total_suppressed if total_suppressed > 0 else 0.0

    return {
        'threshold': threshold,
        'total_predictions': len(all_pairs),
        'suppressed': total_suppressed,
        'suppressed_pct': round(total_suppressed / len(all_pairs) * 100, 2),
        'suppressed_correct': suppressed_correct,
        'suppressed_wrong': suppressed_wrong,
        'not_suppressed': total_not_suppressed,
        'not_suppressed_correct': not_suppressed_correct,
        'regret_rate': round(regret_rate * 100, 2),
        'wisdom_rate': round(wisdom_rate * 100, 2),
        'baseline_regret': 41.5,
        'delta_from_baseline': round(regret_rate * 100 - 41.5, 2)
    }


def run_epistemic_audit():
    """Execute the full DIR-011 epistemic audit."""
    logger.info("=" * 70)
    logger.info("CEO-DIR-2026-EPISTEMIC-LOCK-AND-PROOF-011")
    logger.info("EPISTEMIC PROOF LOCK — Regime Perception Validation")
    logger.info("=" * 70)

    conn = psycopg2.connect(**DB_CONFIG)
    damper = ForecastConfidenceDamper(conn)

    try:
        # ========================================
        # 1. FETCH DATA
        # ========================================
        logger.info("\n[PHASE 1] Fetching regime forecast-outcome pairs...")
        regime_pairs = fetch_regime_pairs(conn)
        logger.info(f"  Regime pairs: {len(regime_pairs)}")

        logger.info("  Fetching all pairs for suppression analysis...")
        all_pairs = fetch_all_pairs(conn)
        logger.info(f"  All pairs: {len(all_pairs)}")

        # ========================================
        # 2. APPLY DAMPENING RETROACTIVELY
        # ========================================
        logger.info("\n[PHASE 2] Applying dampening retroactively...")
        regime_pairs = apply_dampening(regime_pairs, damper)
        all_pairs = apply_dampening(all_pairs, damper)

        damped_count = sum(1 for p in regime_pairs if p['was_damped'])
        logger.info(f"  Regime pairs damped: {damped_count}/{len(regime_pairs)}")
        avg_delta = sum(p['dampening_delta'] for p in regime_pairs) / len(regime_pairs) if regime_pairs else 0
        logger.info(f"  Average dampening delta: {avg_delta:.4f}")

        # ========================================
        # 3. CONFUSION MATRIX (Before/After)
        # ========================================
        logger.info("\n[PHASE 3] Computing regime confusion matrices...")
        confusion = compute_confusion_matrix(regime_pairs)

        # Compute accuracy per predicted regime
        regime_accuracy = {}
        for pred, actuals in confusion.items():
            total = sum(actuals.values())
            correct = actuals.get(pred, 0)
            error_rate = (total - correct) / total if total > 0 else 0
            regime_accuracy[pred] = {
                'total': total,
                'correct': correct,
                'error_rate': round(error_rate * 100, 2),
                'most_confused_with': max(
                    ((a, n) for a, n in actuals.items() if a != pred),
                    key=lambda x: x[1], default=('NONE', 0)
                )
            }

        for pred, acc in sorted(regime_accuracy.items()):
            confused = acc['most_confused_with']
            logger.info(f"  {pred}: {acc['error_rate']}% error "
                        f"({acc['correct']}/{acc['total']} correct, "
                        f"most confused with {confused[0]} x{confused[1]})")

        # ========================================
        # 4. CALIBRATION CURVES
        # ========================================
        logger.info("\n[PHASE 4] Building calibration curves...")
        raw_curve, damped_curve = compute_calibration_curves(regime_pairs)

        logger.info("  RAW confidence calibration:")
        total_raw_gap = 0
        for b in raw_curve:
            logger.info(f"    {b['bin']}: stated={b['avg_stated_confidence']:.4f} "
                        f"actual={b['actual_accuracy']:.4f} "
                        f"gap={b['calibration_gap']:+.4f} ({b['direction']})")
            total_raw_gap += abs(b['calibration_gap']) * b['n']

        logger.info("  DAMPED confidence calibration:")
        total_damped_gap = 0
        for b in damped_curve:
            logger.info(f"    {b['bin']}: stated={b['avg_stated_confidence']:.4f} "
                        f"actual={b['actual_accuracy']:.4f} "
                        f"gap={b['calibration_gap']:+.4f} ({b['direction']})")
            total_damped_gap += abs(b['calibration_gap']) * b['n']

        n_regime = len(regime_pairs) if regime_pairs else 1
        weighted_raw_gap = total_raw_gap / n_regime
        weighted_damped_gap = total_damped_gap / n_regime
        logger.info(f"  Weighted avg calibration gap: RAW={weighted_raw_gap:.4f} -> DAMPED={weighted_damped_gap:.4f}")

        # ========================================
        # 5. BRIER SCORE DECOMPOSITION
        # ========================================
        logger.info("\n[PHASE 5] Brier score decomposition per regime...")
        brier = compute_brier_decomposition(regime_pairs)

        for regime, data in sorted(brier.items()):
            if regime == 'OVERALL':
                continue
            direction = 'IMPROVED' if data['improvement'] else 'WORSENED'
            logger.info(f"  {regime}: raw={data['brier_raw']:.4f} -> damped={data['brier_damped']:.4f} "
                        f"({data['brier_delta']:+.4f}, {direction} {abs(data['improvement_pct']):.1f}%)")

        overall = brier['OVERALL']
        logger.info(f"  OVERALL: raw={overall['brier_raw']:.4f} -> damped={overall['brier_damped']:.4f} "
                    f"({overall['brier_delta']:+.4f}, "
                    f"{'IMPROVED' if overall['improvement'] else 'WORSENED'} {abs(overall['improvement_pct']):.1f}%)")

        # ========================================
        # 6. SUPPRESSION REGRET
        # ========================================
        logger.info("\n[PHASE 6] Suppression regret re-measurement...")
        regret = compute_suppression_regret(all_pairs)
        logger.info(f"  Threshold: {regret['threshold']}")
        logger.info(f"  Suppressed: {regret['suppressed']}/{regret['total_predictions']} ({regret['suppressed_pct']}%)")
        logger.info(f"  Suppression regret: {regret['regret_rate']}% (baseline: {regret['baseline_regret']}%)")
        logger.info(f"  Delta from baseline: {regret['delta_from_baseline']:+.2f}pp")
        logger.info(f"  Suppression wisdom: {regret['wisdom_rate']}%")

        # ========================================
        # 7. EPISTEMIC LESSONS DELTA
        # ========================================
        logger.info("\n[PHASE 7] Delta vs Jan-16 epistemic lessons...")
        jan16_baselines = {
            'HIGH_CONFIDENCE_gap': 0.708,
            'MEDIUM_CONFIDENCE_gap': 0.330,
            'BEAR_error_rate': 94.4,
            'BULL_error_rate': 77.9,
            'STRESS_error_rate': 100.0,
            'suppression_regret': 41.5,
        }

        current_metrics = {
            'BEAR_error_rate': regime_accuracy.get('BEAR', {}).get('error_rate', 0),
            'BULL_error_rate': regime_accuracy.get('BULL', {}).get('error_rate', 0),
            'STRESS_error_rate': regime_accuracy.get('STRESS', {}).get('error_rate', 0),
            'suppression_regret': regret['regret_rate'],
            'weighted_calibration_gap_raw': round(weighted_raw_gap, 4),
            'weighted_calibration_gap_damped': round(weighted_damped_gap, 4),
        }

        # ========================================
        # 8. VERDICT
        # ========================================
        logger.info("\n" + "=" * 70)
        logger.info("VERDICT")
        logger.info("=" * 70)

        # The question: "Did FjordHQ get smarter, or just quieter?"
        # Smarter = calibration improved (gap decreased)
        # Quieter = more suppression without accuracy improvement

        calibration_improved = weighted_damped_gap < weighted_raw_gap
        brier_improved = overall['improvement']
        regret_decreased = regret['regret_rate'] < regret['baseline_regret']

        if calibration_improved and brier_improved:
            verdict = 'PASS_CONDITIONAL'
            verdict_text = (
                'Calibration directionally improved. Brier score improved. '
                'System perception is MORE ACCURATE under dampening. '
                'However, regime CLASSIFICATION accuracy is unchanged — '
                'dampening corrects confidence, not prediction logic.'
            )
        elif calibration_improved:
            verdict = 'PASS_PARTIAL'
            verdict_text = (
                'Calibration improved but Brier score mixed. '
                'Dampening corrects overconfidence but regime accuracy unchanged.'
            )
        else:
            verdict = 'FAIL'
            verdict_text = 'No measurable improvement in calibration or Brier score.'

        logger.info(f"  Verdict: {verdict}")
        logger.info(f"  {verdict_text}")

        # ========================================
        # ASSEMBLE EVIDENCE
        # ========================================
        evidence = {
            'directive': 'CEO-DIR-2026-EPISTEMIC-LOCK-AND-PROOF-011',
            'classification': 'CONSTITUTIONAL / G2',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG',
            'ec': 'EC-003',
            'lead': 'FINN',
            'oversight': 'VEGA',
            'dataset': {
                'regime_pairs': len(regime_pairs),
                'all_pairs': len(all_pairs),
                'regime_pairs_damped': damped_count,
                'avg_dampening_delta': round(avg_delta, 4),
            },
            'confusion_matrix': confusion,
            'regime_accuracy': {
                k: {
                    'total': v['total'],
                    'correct': v['correct'],
                    'error_rate': v['error_rate'],
                    'most_confused_with': v['most_confused_with'][0],
                    'confusion_count': v['most_confused_with'][1]
                }
                for k, v in regime_accuracy.items()
            },
            'calibration_curves': {
                'raw': raw_curve,
                'damped': damped_curve,
                'weighted_avg_gap_raw': round(weighted_raw_gap, 4),
                'weighted_avg_gap_damped': round(weighted_damped_gap, 4),
                'calibration_improvement': calibration_improved,
                'gap_reduction_pct': round(
                    (weighted_raw_gap - weighted_damped_gap) / weighted_raw_gap * 100, 2
                ) if weighted_raw_gap > 0 else 0
            },
            'brier_decomposition': brier,
            'suppression_regret': regret,
            'jan16_delta': {
                'baselines': jan16_baselines,
                'current': current_metrics,
                'note': 'Confusion matrix unchanged by dampening (dampening corrects confidence, not predictions). '
                        'Calibration gap and Brier scores ARE affected.'
            },
            'verdict': {
                'code': verdict,
                'text': verdict_text,
                'calibration_improved': calibration_improved,
                'brier_improved': brier_improved,
                'regret_decreased': regret_decreased,
            },
            'constitutional_hold': {
                'ops_alpha_activation': 'BLOCKED',
                'shadow_hunting_escalation': 'BLOCKED',
                'micro_regime_overrides': 'BLOCKED',
                'live_experimentation': 'BLOCKED'
            }
        }

        evidence_json = json.dumps(evidence, indent=2, default=str)
        evidence_hash = hashlib.sha256(evidence_json.encode()).hexdigest()
        evidence['evidence_hash'] = evidence_hash

        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(evidence_dir, f'CEO_DIR_011_EPISTEMIC_AUDIT_{ts}.json')
        with open(path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)

        logger.info(f"\n  Evidence: {path}")
        logger.info(f"  Hash: {evidence_hash}")

        return evidence

    finally:
        conn.close()


if __name__ == '__main__':
    run_epistemic_audit()
