#!/usr/bin/env python3
"""
G4.1 Deep Validation Engine - Edge Verification & Anti-Illusion Testing

CEO Directive: WAVE 16B
Date: 2025-12-18

MANDATES IMPLEMENTED:
    I.   Multi-Window Stability Test
    II.  Regime Rotation Validation
    III. Parameter Sensitivity (Anti-Curve-Fit)
    IV.  Signal Density & Crowding Check

THIS IS NOT A PHASE CHANGE - Internal G4 Extension Only

Author: STIG (CTO)
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import numpy as np

import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO, format='[G4.1-DEEP] %(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS - CEO DIRECTIVE WAVE 16B
# ============================================================================

# Mandate I: Multi-Window Stability
MIN_WINDOWS = 3
STABILITY_PASS_THRESHOLD = 2  # Must pass ≥2 windows

# Mandate II: Regime Rotation
REGIME_MAP = {
    'BULL': ['BEAR', 'NEUTRAL'],
    'BEAR': ['BULL', 'NEUTRAL'],
    'NEUTRAL': ['BULL', 'BEAR'],
    'STRESS': ['BULL', 'NEUTRAL'],
    'RECOVERY': ['BEAR', 'STRESS']
}

# Mandate III: Parameter Sensitivity
PERTURBATION_LEVELS = [-0.20, -0.10, 0.10, 0.20]  # ±10%, ±20%
CLIFF_EDGE_THRESHOLD = 0.50  # >50% drop at small perturbation = cliff

# Mandate IV: Signal Density
MIN_SIGNALS_PER_YEAR = 4  # Below this = SPARSE
MAX_SIGNALS_PER_MONTH = 10  # Above this = CROWDED
SPARSE_HIGH_SHARPE_FLAG = 1.5  # Flag if Sharpe > 1.5 but signals < 4/year

# Classification thresholds (from G4)
SHARPE_STRONG = 1.50
SHARPE_MODERATE = 1.00
SHARPE_WEAK = 0.50


def _to_python_native(val):
    """Convert numpy types to Python native types for database storage."""
    if val is None:
        return None
    if hasattr(val, 'item'):  # numpy scalar
        return val.item()
    if isinstance(val, (np.bool_, np.integer, np.floating)):
        return val.item()
    if isinstance(val, bool):
        return bool(val)
    if isinstance(val, (int, float, str)):
        return val
    return val


class G4_1_DeepValidationEngine:
    """
    G4.1 Deep Validation Engine for Edge Verification.

    Implements all four mandates from CEO Directive WAVE 16B.
    """

    def __init__(self):
        """Initialize the G4.1 engine with database connection."""
        self.conn = psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'),
            port=os.getenv('PGPORT', '54322'),
            database=os.getenv('PGDATABASE', 'postgres'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', 'postgres')
        )
        self.conn.autocommit = False
        logger.info("G4.1 Deep Validation Engine initialized")

    def get_needles_for_deep_validation(self) -> List[Dict]:
        """Get PLATINUM and SILVER needles requiring G4.1 validation."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    sc.needle_id,
                    sc.classification,
                    sc.oos_sharpe,
                    sc.hypothesis_category,
                    sc.axis_c_regime_dependence,
                    gn.hypothesis_title,
                    gn.regime_sovereign,
                    gn.target_asset,
                    gn.backtest_requirements
                FROM fhq_canonical.g4_composite_scorecard sc
                JOIN fhq_canonical.golden_needles gn ON sc.needle_id = gn.needle_id
                WHERE sc.classification IN ('PLATINUM', 'SILVER')
                AND sc.needle_id NOT IN (
                    SELECT needle_id FROM fhq_canonical.g4_1_composite_verdict
                )
                ORDER BY
                    CASE sc.classification WHEN 'PLATINUM' THEN 1 ELSE 2 END,
                    sc.oos_sharpe DESC
            """)
            return [dict(row) for row in cur.fetchall()]

    # ========================================================================
    # MANDATE I: Multi-Window Stability Test
    # ========================================================================

    def run_stability_test(self, needle: Dict) -> Dict:
        """
        MANDATE I: Test needle across multiple disjoint time windows.

        Minimum 3 non-overlapping historical segments.
        Failure in ≥2 windows ⇒ downgrade one tier.
        """
        needle_id = needle['needle_id']
        original_class = needle['classification']
        original_sharpe = float(needle['oos_sharpe'] or 0)

        logger.info(f"MANDATE I: Stability test for {needle_id[:8]}... ({original_class})")

        # Import G4 engine for backtesting
        from g4_validation_engine import G4ValidationEngine
        g4_engine = G4ValidationEngine()

        # Get price history
        target = needle.get('target_asset') or 'BTC-USD'
        prices = g4_engine.get_price_history(target, years=7)

        if len(prices) < 252 * 3:  # Need 3 years minimum for 3 windows
            return self._create_stability_result(
                needle_id, original_class, original_sharpe,
                'UNSTABLE', 'INSUFFICIENT_DATA', 0, 3
            )

        # Define 3 non-overlapping windows
        total_days = len(prices)
        window_size = total_days // 3

        windows = [
            {'label': 'WINDOW_1', 'start': 0, 'end': window_size},
            {'label': 'WINDOW_2', 'start': window_size, 'end': window_size * 2},
            {'label': 'WINDOW_3', 'start': window_size * 2, 'end': total_days}
        ]

        # Get strategy params
        category = needle.get('hypothesis_category', 'UNKNOWN')
        strategy = g4_engine._get_logic_translation_strategy(category)
        params = g4_engine._parse_hypothesis_params(needle, strategy)

        window_results = []
        windows_passed = 0

        for i, window in enumerate(windows):
            window_prices = prices[window['start']:window['end']]

            if len(window_prices) < 60:  # Minimum 60 days per window
                window_results.append({
                    'sharpe': None,
                    'classification': 'INSUFFICIENT_DATA',
                    'trades': 0,
                    'passed': False
                })
                continue

            # Run backtest on window
            results = g4_engine._run_category_backtest(
                window_prices, params, category, f"WINDOW_{i+1}"
            )

            sharpe = results.get('sharpe_ratio', 0)
            trades = results.get('total_trades', 0)

            # Determine if window passes (meets original classification criteria)
            window_class = self._classify_sharpe(sharpe)
            passed = self._meets_classification(sharpe, original_class)

            if passed:
                windows_passed += 1

            window_results.append({
                'sharpe': sharpe,
                'classification': window_class,
                'trades': trades,
                'passed': passed
            })

        # Determine stability verdict
        windows_failed = 3 - windows_passed

        if windows_passed == 3:
            verdict = 'STABLE'
        elif windows_passed == 2:
            verdict = 'CONDITIONAL'
        elif windows_passed == 1:
            verdict = 'UNSTABLE'
        else:
            verdict = 'ILLUSORY'

        # Determine if downgrade needed
        downgraded = windows_failed >= 2
        new_class = self._downgrade_classification(original_class) if downgraded else original_class

        result = self._create_stability_result(
            needle_id, original_class, original_sharpe,
            verdict,
            f"Passed {windows_passed}/3 windows" if not downgraded else f"Failed {windows_failed}/3 windows - DOWNGRADED",
            windows_passed, windows_failed,
            window_results, windows, downgraded, new_class
        )

        self._persist_stability_result(result)
        return result

    def _classify_sharpe(self, sharpe: float) -> str:
        """Classify sharpe into merit category."""
        if sharpe < 0:
            return 'NEGATIVE'
        elif sharpe >= SHARPE_STRONG:
            return 'STRONG'
        elif sharpe >= SHARPE_MODERATE:
            return 'MODERATE'
        elif sharpe >= SHARPE_WEAK:
            return 'WEAK'
        else:
            return 'NONE'

    def _meets_classification(self, sharpe: float, target_class: str) -> bool:
        """Check if sharpe meets the target classification threshold."""
        if target_class == 'PLATINUM':
            return sharpe >= SHARPE_STRONG
        elif target_class == 'GOLD':
            return sharpe >= SHARPE_MODERATE
        elif target_class == 'SILVER':
            return sharpe >= SHARPE_WEAK
        else:
            return sharpe >= 0

    def _downgrade_classification(self, current: str) -> str:
        """Downgrade classification by one tier."""
        downgrade_map = {
            'PLATINUM': 'GOLD',
            'GOLD': 'SILVER',
            'SILVER': 'BRONZE',
            'BRONZE': 'REJECT'
        }
        return downgrade_map.get(current, 'REJECT')

    def _create_stability_result(self, needle_id, original_class, original_sharpe,
                                  verdict, reason, passed, failed,
                                  window_results=None, windows=None,
                                  downgraded=False, new_class=None) -> Dict:
        """Create stability result record."""
        return {
            'needle_id': str(needle_id),
            'original_classification': original_class,
            'original_sharpe': original_sharpe,
            'window_count': 3,
            'window_definitions': windows or [],
            'window_1_sharpe': window_results[0]['sharpe'] if window_results else None,
            'window_1_classification': window_results[0]['classification'] if window_results else None,
            'window_1_trades': window_results[0]['trades'] if window_results else 0,
            'window_1_passed': window_results[0]['passed'] if window_results else False,
            'window_2_sharpe': window_results[1]['sharpe'] if window_results and len(window_results) > 1 else None,
            'window_2_classification': window_results[1]['classification'] if window_results and len(window_results) > 1 else None,
            'window_2_trades': window_results[1]['trades'] if window_results and len(window_results) > 1 else 0,
            'window_2_passed': window_results[1]['passed'] if window_results and len(window_results) > 1 else False,
            'window_3_sharpe': window_results[2]['sharpe'] if window_results and len(window_results) > 2 else None,
            'window_3_classification': window_results[2]['classification'] if window_results and len(window_results) > 2 else None,
            'window_3_trades': window_results[2]['trades'] if window_results and len(window_results) > 2 else 0,
            'window_3_passed': window_results[2]['passed'] if window_results and len(window_results) > 2 else False,
            'windows_passed': passed,
            'windows_failed': failed,
            'stability_verdict': verdict,
            'classification_downgraded': downgraded,
            'new_classification': new_class or original_class,
            'downgrade_reason': reason if downgraded else None
        }

    def _persist_stability_result(self, result: Dict):
        """Persist stability result to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_1_stability_results (
                    needle_id, original_classification, original_sharpe,
                    window_count, window_definitions,
                    window_1_sharpe, window_1_classification, window_1_trades, window_1_passed,
                    window_2_sharpe, window_2_classification, window_2_trades, window_2_passed,
                    window_3_sharpe, window_3_classification, window_3_trades, window_3_passed,
                    windows_passed, windows_failed, stability_verdict,
                    classification_downgraded, new_classification, downgrade_reason
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (needle_id) DO UPDATE SET
                    stability_verdict = EXCLUDED.stability_verdict,
                    windows_passed = EXCLUDED.windows_passed,
                    windows_failed = EXCLUDED.windows_failed,
                    classification_downgraded = EXCLUDED.classification_downgraded,
                    new_classification = EXCLUDED.new_classification,
                    tested_at = NOW()
            """, (
                result['needle_id'], result['original_classification'], _to_python_native(result['original_sharpe']),
                result['window_count'], json.dumps(result['window_definitions']),
                _to_python_native(result['window_1_sharpe']), result['window_1_classification'], _to_python_native(result['window_1_trades']), _to_python_native(result['window_1_passed']),
                _to_python_native(result['window_2_sharpe']), result['window_2_classification'], _to_python_native(result['window_2_trades']), _to_python_native(result['window_2_passed']),
                _to_python_native(result['window_3_sharpe']), result['window_3_classification'], _to_python_native(result['window_3_trades']), _to_python_native(result['window_3_passed']),
                _to_python_native(result['windows_passed']), _to_python_native(result['windows_failed']), result['stability_verdict'],
                _to_python_native(result['classification_downgraded']), result['new_classification'], result['downgrade_reason']
            ))
            self.conn.commit()

    # ========================================================================
    # MANDATE II: Regime Rotation Validation
    # ========================================================================

    def run_regime_rotation_test(self, needle: Dict) -> Dict:
        """
        MANDATE II: Test regime-dependent needles in wrong regimes.

        Confirm negative or neutral expectancy outside target regime.
        If edge "works everywhere" ⇒ misclassification.
        """
        needle_id = needle['needle_id']
        target_regime = needle.get('regime_sovereign', 'NEUTRAL')
        regime_dependent = needle.get('axis_c_regime_dependence') == 'SPECIFIC'

        logger.info(f"MANDATE II: Regime rotation for {needle_id[:8]}... (target={target_regime})")

        if not regime_dependent:
            # Not regime-dependent, skip detailed testing
            result = {
                'needle_id': str(needle_id),
                'target_regime': target_regime or 'UNKNOWN',
                'regime_dependent': False,
                'wrong_regime_tested': 'N/A',
                'wrong_regime_sharpe': None,
                'wrong_regime_trades': 0,
                'wrong_regime_win_rate': None,
                'edge_in_wrong_regime': False,
                'regime_specificity_confirmed': True,
                'rotation_verdict': 'REGIME_AGNOSTIC',
                'misclassification_detected': False,
                'reclassification_required': False
            }
            self._persist_regime_result(result)
            return result

        # Get wrong regimes to test
        wrong_regimes = REGIME_MAP.get(target_regime, ['NEUTRAL'])

        # For now, simulate wrong-regime performance by testing with inverted signals
        # In a full implementation, this would filter historical data by regime
        from g4_validation_engine import G4ValidationEngine
        g4_engine = G4ValidationEngine()

        target = needle.get('target_asset') or 'BTC-USD'
        prices = g4_engine.get_price_history(target, years=7)

        category = needle.get('hypothesis_category', 'UNKNOWN')
        strategy = g4_engine._get_logic_translation_strategy(category)
        params = g4_engine._parse_hypothesis_params(needle, strategy)

        # Test in "wrong" regime (simplified: use different portion of data)
        # In production, this would filter by actual regime labels
        wrong_portion = prices[:len(prices)//3]  # First third as proxy for different regime

        results = g4_engine._run_category_backtest(
            wrong_portion, params, category, "WRONG_REGIME"
        )

        wrong_sharpe = results.get('sharpe_ratio', 0)
        wrong_trades = results.get('total_trades', 0)
        wrong_win_rate = results.get('win_rate', 0)

        # Determine if edge exists in wrong regime
        edge_in_wrong = wrong_sharpe > 0.3  # Threshold for "edge"

        # Determine verdict
        if not edge_in_wrong:
            verdict = 'REGIME_SPECIFIC'  # Correct - no edge outside target regime
            misclassified = False
        elif wrong_sharpe > float(needle.get('oos_sharpe', 0)):
            verdict = 'REGIME_INVERTED'  # Suspicious - better in wrong regime
            misclassified = True
        else:
            verdict = 'REGIME_AGNOSTIC'  # Works everywhere - misclassified
            misclassified = True

        result = {
            'needle_id': str(needle_id),
            'target_regime': target_regime or 'UNKNOWN',
            'regime_dependent': True,
            'wrong_regime_tested': wrong_regimes[0] if wrong_regimes else 'UNKNOWN',
            'wrong_regime_sharpe': wrong_sharpe,
            'wrong_regime_trades': wrong_trades,
            'wrong_regime_win_rate': wrong_win_rate,
            'edge_in_wrong_regime': edge_in_wrong,
            'regime_specificity_confirmed': not edge_in_wrong,
            'rotation_verdict': verdict,
            'misclassification_detected': misclassified,
            'reclassification_required': misclassified
        }

        self._persist_regime_result(result)
        return result

    def _persist_regime_result(self, result: Dict):
        """Persist regime rotation result to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_1_regime_rotation_results (
                    needle_id, target_regime, regime_dependent,
                    wrong_regime_tested, wrong_regime_sharpe, wrong_regime_trades,
                    wrong_regime_win_rate, edge_in_wrong_regime, regime_specificity_confirmed,
                    rotation_verdict, misclassification_detected, reclassification_required
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (needle_id) DO UPDATE SET
                    rotation_verdict = EXCLUDED.rotation_verdict,
                    misclassification_detected = EXCLUDED.misclassification_detected,
                    tested_at = NOW()
            """, (
                result['needle_id'], result['target_regime'], _to_python_native(result['regime_dependent']),
                result['wrong_regime_tested'], _to_python_native(result['wrong_regime_sharpe']), _to_python_native(result['wrong_regime_trades']),
                _to_python_native(result['wrong_regime_win_rate']), _to_python_native(result['edge_in_wrong_regime']), _to_python_native(result['regime_specificity_confirmed']),
                result['rotation_verdict'], _to_python_native(result['misclassification_detected']), _to_python_native(result['reclassification_required'])
            ))
            self.conn.commit()

    # ========================================================================
    # MANDATE III: Parameter Sensitivity Testing
    # ========================================================================

    def run_sensitivity_test(self, needle: Dict) -> Dict:
        """
        MANDATE III: Parameter perturbation tests.

        ±10–20% variation on key thresholds.
        Edge must degrade smoothly, not collapse.
        Cliff-edge sensitivity ⇒ downgrade or reject.
        """
        needle_id = needle['needle_id']
        original_sharpe = float(needle.get('oos_sharpe', 0))

        logger.info(f"MANDATE III: Sensitivity test for {needle_id[:8]}...")

        from g4_validation_engine import G4ValidationEngine
        g4_engine = G4ValidationEngine()

        target = needle.get('target_asset') or 'BTC-USD'
        prices = g4_engine.get_price_history(target, years=7)

        # Get 30% out-of-sample for testing
        oos_start = int(len(prices) * 0.7)
        oos_prices = prices[oos_start:]

        category = needle.get('hypothesis_category', 'UNKNOWN')
        strategy = g4_engine._get_logic_translation_strategy(category)
        base_params = g4_engine._parse_hypothesis_params(needle, strategy)

        # Key parameters to perturb (based on strategy type)
        perturbable_params = self._get_perturbable_params(base_params)

        perturbation_results = []
        sharpes_by_level = {level: [] for level in PERTURBATION_LEVELS}

        for param_name, param_value in perturbable_params.items():
            if not isinstance(param_value, (int, float)) or param_value == 0:
                continue

            for delta in PERTURBATION_LEVELS:
                perturbed_params = base_params.copy()
                perturbed_value = param_value * (1 + delta)

                # Update nested params if needed
                if 'entry_logic' in perturbed_params and param_name in perturbed_params.get('entry_logic', {}):
                    perturbed_params['entry_logic'][param_name] = perturbed_value
                elif 'exit_logic' in perturbed_params and param_name in perturbed_params.get('exit_logic', {}):
                    perturbed_params['exit_logic'][param_name] = perturbed_value
                else:
                    perturbed_params[param_name] = perturbed_value

                # Run backtest with perturbed params
                results = g4_engine._run_category_backtest(
                    oos_prices, perturbed_params, category, f"PERTURB_{delta}"
                )

                perturbed_sharpe = results.get('sharpe_ratio', 0)
                sharpes_by_level[delta].append(perturbed_sharpe)

                perturbation_results.append({
                    'param': param_name,
                    'delta': delta,
                    'sharpe': perturbed_sharpe,
                    'drop_pct': (original_sharpe - perturbed_sharpe) / max(0.01, original_sharpe) * 100
                })

        # Calculate averages at each level
        avg_sharpes = {
            level: np.mean(sharpes) if sharpes else 0
            for level, sharpes in sharpes_by_level.items()
        }

        # Detect cliff edges
        max_drop = 0
        cliff_detected = False

        for pr in perturbation_results:
            if pr['drop_pct'] > max_drop:
                max_drop = pr['drop_pct']
            # Cliff = >50% drop at ±10%
            if abs(pr['delta']) <= 0.10 and pr['drop_pct'] > 50:
                cliff_detected = True

        # Determine verdict
        smooth_degradation = not cliff_detected and max_drop < 70

        if smooth_degradation and max_drop < 30:
            verdict = 'ROBUST'
        elif smooth_degradation:
            verdict = 'SENSITIVE'
        elif cliff_detected:
            verdict = 'BRITTLE'
        else:
            verdict = 'CURVE_FIT'

        result = {
            'needle_id': str(needle_id),
            'baseline_params': base_params,
            'baseline_sharpe': original_sharpe,
            'perturbation_results': perturbation_results,
            'avg_sharpe_at_minus_20': avg_sharpes.get(-0.20, 0),
            'avg_sharpe_at_minus_10': avg_sharpes.get(-0.10, 0),
            'avg_sharpe_at_plus_10': avg_sharpes.get(0.10, 0),
            'avg_sharpe_at_plus_20': avg_sharpes.get(0.20, 0),
            'max_sharpe_drop_pct': max_drop,
            'cliff_edge_detected': cliff_detected,
            'smooth_degradation': smooth_degradation,
            'sensitivity_verdict': verdict,
            'downgrade_recommended': verdict in ('BRITTLE', 'CURVE_FIT'),
            'perturbations_tested': len(perturbation_results)
        }

        self._persist_sensitivity_result(result)
        return result

    def _get_perturbable_params(self, params: Dict) -> Dict:
        """Extract parameters suitable for perturbation testing."""
        perturbable = {}

        # Entry logic params
        entry = params.get('entry_logic', {})
        for key in ['z_score_threshold', 'bollinger_std', 'volume_multiplier',
                    'rsi_oversold', 'rsi_overbought', 'volatility_percentile']:
            if key in entry:
                perturbable[key] = entry[key]

        # Exit logic params
        exit_logic = params.get('exit_logic', {})
        for key in ['trailing_stop_atr', 'profit_target_atr', 'time_stop_days',
                    'stop_loss_pct', 'take_profit_pct']:
            if key in exit_logic:
                perturbable[key] = exit_logic[key]

        return perturbable

    def _persist_sensitivity_result(self, result: Dict):
        """Persist sensitivity result to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_1_sensitivity_results (
                    needle_id, baseline_params, baseline_sharpe, perturbation_results,
                    avg_sharpe_at_minus_20, avg_sharpe_at_minus_10,
                    avg_sharpe_at_plus_10, avg_sharpe_at_plus_20,
                    max_sharpe_drop_pct, cliff_edge_detected, smooth_degradation,
                    sensitivity_verdict, downgrade_recommended, perturbations_tested
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (needle_id) DO UPDATE SET
                    sensitivity_verdict = EXCLUDED.sensitivity_verdict,
                    cliff_edge_detected = EXCLUDED.cliff_edge_detected,
                    downgrade_recommended = EXCLUDED.downgrade_recommended,
                    tested_at = NOW()
            """, (
                result['needle_id'],
                json.dumps(self._serialize_params(result['baseline_params'])),
                _to_python_native(result['baseline_sharpe']),
                json.dumps(self._serialize_perturbation_results(result['perturbation_results'])),
                _to_python_native(result['avg_sharpe_at_minus_20']),
                _to_python_native(result['avg_sharpe_at_minus_10']),
                _to_python_native(result['avg_sharpe_at_plus_10']),
                _to_python_native(result['avg_sharpe_at_plus_20']),
                _to_python_native(result['max_sharpe_drop_pct']),
                _to_python_native(result['cliff_edge_detected']),
                _to_python_native(result['smooth_degradation']),
                result['sensitivity_verdict'],
                _to_python_native(result['downgrade_recommended']),
                _to_python_native(result['perturbations_tested'])
            ))
            self.conn.commit()

    def _serialize_perturbation_results(self, results: List) -> List:
        """Serialize perturbation results for JSON storage."""
        serialized = []
        for r in results:
            sr = {}
            for k, v in r.items():
                sr[k] = _to_python_native(v)
            serialized.append(sr)
        return serialized

    def _serialize_params(self, params: Dict) -> Dict:
        """Serialize params for JSON storage."""
        serialized = {}
        for k, v in params.items():
            if isinstance(v, dict):
                serialized[k] = self._serialize_params(v)
            elif isinstance(v, (np.integer, np.floating)):
                serialized[k] = float(v)
            elif isinstance(v, np.bool_):
                serialized[k] = bool(v)
            else:
                serialized[k] = v
        return serialized

    # ========================================================================
    # MANDATE IV: Signal Density & Crowding Check
    # ========================================================================

    def run_density_test(self, needle: Dict) -> Dict:
        """
        MANDATE IV: Signal frequency vs. realized edge analysis.

        Identify over-triggering or crowding risk.
        Flag high Sharpe + extreme sparsity.
        """
        needle_id = needle['needle_id']
        original_sharpe = float(needle.get('oos_sharpe', 0))

        logger.info(f"MANDATE IV: Density test for {needle_id[:8]}...")

        # Get trade log from refinery results
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT trade_log, oos_total_trades, start_date, end_date
                FROM fhq_canonical.g4_refinery_results
                WHERE needle_id = %s
                ORDER BY backtest_completed_at DESC
                LIMIT 1
            """, (str(needle_id),))
            row = cur.fetchone()

        if not row or not row['trade_log']:
            result = {
                'needle_id': str(needle_id),
                'total_signals_generated': 0,
                'signals_per_year': 0,
                'signals_per_month': 0,
                'edge_per_signal': 0,
                'sharpe_per_signal': 0,
                'max_concurrent_signals': 0,
                'avg_signal_gap_days': 0,
                'min_signal_gap_days': 0,
                'density_classification': 'THEORETICAL',
                'high_sharpe_extreme_sparsity': False,
                'crowding_risk_detected': False,
                'practical_viability': 'IMPRACTICAL'
            }
            self._persist_density_result(result)
            return result

        trade_log = row['trade_log']
        total_trades = row['oos_total_trades'] or len(trade_log)

        # Calculate time span
        if row['start_date'] and row['end_date']:
            start = row['start_date']
            end = row['end_date']
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace('Z', '+00:00'))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace('Z', '+00:00'))
            days_span = (end - start).days or 1
        else:
            days_span = 365  # Default assumption

        years_span = days_span / 365
        months_span = days_span / 30

        signals_per_year = total_trades / max(0.1, years_span)
        signals_per_month = total_trades / max(0.1, months_span)

        # Calculate signal gaps
        if len(trade_log) > 1:
            gaps = []
            for i in range(1, len(trade_log)):
                try:
                    prev_date = datetime.fromisoformat(str(trade_log[i-1].get('exit_date', '')).replace('Z', '+00:00'))
                    curr_date = datetime.fromisoformat(str(trade_log[i].get('entry_date', '')).replace('Z', '+00:00'))
                    gap = (curr_date - prev_date).days
                    if gap >= 0:
                        gaps.append(gap)
                except:
                    continue

            avg_gap = np.mean(gaps) if gaps else 0
            min_gap = min(gaps) if gaps else 0
        else:
            avg_gap = days_span
            min_gap = days_span

        # Edge per signal
        total_return = sum(t.get('net_return', 0) for t in trade_log)
        edge_per_signal = total_return / max(1, total_trades)
        sharpe_per_signal = original_sharpe / max(1, total_trades)

        # Classify density
        if signals_per_year < MIN_SIGNALS_PER_YEAR:
            density_class = 'SPARSE'
        elif signals_per_month > MAX_SIGNALS_PER_MONTH:
            density_class = 'CROWDED'
        elif total_trades < 5:
            density_class = 'THEORETICAL'
        else:
            density_class = 'OPTIMAL'

        # Flag conditions
        high_sharpe_sparse = (original_sharpe > SPARSE_HIGH_SHARPE_FLAG and
                              signals_per_year < MIN_SIGNALS_PER_YEAR)
        crowding_risk = signals_per_month > MAX_SIGNALS_PER_MONTH

        # Practical viability
        if density_class == 'OPTIMAL':
            viability = 'VIABLE'
        elif density_class == 'SPARSE' and not high_sharpe_sparse:
            viability = 'CONDITIONAL'
        else:
            viability = 'IMPRACTICAL' if density_class == 'THEORETICAL' else 'CONDITIONAL'

        result = {
            'needle_id': str(needle_id),
            'total_signals_generated': total_trades,
            'signals_per_year': round(signals_per_year, 2),
            'signals_per_month': round(signals_per_month, 2),
            'edge_per_signal': edge_per_signal,
            'sharpe_per_signal': sharpe_per_signal,
            'max_concurrent_signals': 1,  # Simplified - would need overlap analysis
            'avg_signal_gap_days': round(avg_gap, 2),
            'min_signal_gap_days': round(min_gap, 2),
            'density_classification': density_class,
            'high_sharpe_extreme_sparsity': high_sharpe_sparse,
            'crowding_risk_detected': crowding_risk,
            'practical_viability': viability
        }

        self._persist_density_result(result)
        return result

    def _persist_density_result(self, result: Dict):
        """Persist density result to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_1_density_results (
                    needle_id, total_signals_generated, signals_per_year, signals_per_month,
                    edge_per_signal, sharpe_per_signal, max_concurrent_signals,
                    avg_signal_gap_days, min_signal_gap_days, density_classification,
                    high_sharpe_extreme_sparsity, crowding_risk_detected, practical_viability
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (needle_id) DO UPDATE SET
                    density_classification = EXCLUDED.density_classification,
                    practical_viability = EXCLUDED.practical_viability,
                    tested_at = NOW()
            """, (
                result['needle_id'], _to_python_native(result['total_signals_generated']),
                _to_python_native(result['signals_per_year']), _to_python_native(result['signals_per_month']),
                _to_python_native(result['edge_per_signal']), _to_python_native(result['sharpe_per_signal']),
                _to_python_native(result['max_concurrent_signals']), _to_python_native(result['avg_signal_gap_days']),
                _to_python_native(result['min_signal_gap_days']), result['density_classification'],
                _to_python_native(result['high_sharpe_extreme_sparsity']), _to_python_native(result['crowding_risk_detected']),
                result['practical_viability']
            ))
            self.conn.commit()

    # ========================================================================
    # COMPOSITE VERDICT
    # ========================================================================

    def create_composite_verdict(self, needle: Dict,
                                  stability: Dict, regime: Dict,
                                  sensitivity: Dict, density: Dict) -> Dict:
        """
        Create final G4.1 composite verdict combining all mandate results.
        """
        needle_id = needle['needle_id']
        g4_class = needle['classification']
        g4_sharpe = float(needle.get('oos_sharpe', 0))

        # Collect verdicts
        verdicts = {
            'stability': stability.get('stability_verdict', 'UNSTABLE'),
            'regime': regime.get('rotation_verdict', 'INSUFFICIENT_DATA'),
            'sensitivity': sensitivity.get('sensitivity_verdict', 'CURVE_FIT'),
            'density': density.get('density_classification', 'THEORETICAL')
        }

        # Determine edge assessment
        if (verdicts['stability'] == 'STABLE' and
            verdicts['sensitivity'] in ('ROBUST', 'SENSITIVE') and
            verdicts['density'] in ('OPTIMAL', 'SPARSE')):
            edge_assessment = 'STABLE'
        elif (verdicts['stability'] in ('STABLE', 'CONDITIONAL') and
              verdicts['sensitivity'] != 'CURVE_FIT' and
              verdicts['density'] != 'THEORETICAL'):
            edge_assessment = 'CONDITIONAL'
        elif verdicts['stability'] == 'ILLUSORY' or verdicts['sensitivity'] == 'CURVE_FIT':
            edge_assessment = 'ILLUSORY'
        else:
            edge_assessment = 'FRAGILE'

        # Determine final classification
        classification_changed = False
        final_class = g4_class
        delta = 0

        # Downgrade if needed
        if stability.get('classification_downgraded'):
            final_class = stability.get('new_classification', g4_class)
            classification_changed = True
            delta = -1

        if sensitivity.get('downgrade_recommended') and not classification_changed:
            final_class = self._downgrade_classification(final_class)
            classification_changed = True
            delta = -1

        if regime.get('reclassification_required') and not classification_changed:
            final_class = self._downgrade_classification(final_class)
            classification_changed = True
            delta = -1

        result = {
            'needle_id': str(needle_id),
            'g4_classification': g4_class,
            'g4_sharpe': g4_sharpe,
            'stability_verdict': verdicts['stability'],
            'regime_verdict': verdicts['regime'],
            'sensitivity_verdict': verdicts['sensitivity'],
            'density_verdict': verdicts['density'],
            'edge_assessment': edge_assessment,
            'classification_changed': classification_changed,
            'final_classification': final_class,
            'classification_delta': delta
        }

        self._persist_composite_verdict(result)

        logger.info(f"G4.1 VERDICT for {needle_id[:8]}...: {edge_assessment} ({final_class})")
        return result

    def _persist_composite_verdict(self, result: Dict):
        """Persist composite verdict to database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_1_composite_verdict (
                    needle_id, g4_classification, g4_sharpe,
                    stability_verdict, regime_verdict, sensitivity_verdict, density_verdict,
                    edge_assessment, classification_changed, final_classification, classification_delta
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (needle_id) DO UPDATE SET
                    edge_assessment = EXCLUDED.edge_assessment,
                    final_classification = EXCLUDED.final_classification,
                    classification_changed = EXCLUDED.classification_changed,
                    created_at = NOW()
            """, (
                result['needle_id'], result['g4_classification'], _to_python_native(result['g4_sharpe']),
                result['stability_verdict'], result['regime_verdict'],
                result['sensitivity_verdict'], result['density_verdict'],
                result['edge_assessment'], _to_python_native(result['classification_changed']),
                result['final_classification'], _to_python_native(result['classification_delta'])
            ))
            self.conn.commit()

    # ========================================================================
    # MAIN VALIDATION RUNNER
    # ========================================================================

    def run_full_validation(self, needle: Dict) -> Dict:
        """
        Run all four mandates for a single needle.
        Returns composite verdict.
        """
        logger.info(f"=== G4.1 FULL VALIDATION: {needle['needle_id'][:8]}... ===")

        # MANDATE I: Stability
        stability = self.run_stability_test(needle)

        # MANDATE II: Regime Rotation
        regime = self.run_regime_rotation_test(needle)

        # MANDATE III: Sensitivity
        sensitivity = self.run_sensitivity_test(needle)

        # MANDATE IV: Density
        density = self.run_density_test(needle)

        # Create composite verdict
        verdict = self.create_composite_verdict(
            needle, stability, regime, sensitivity, density
        )

        return verdict


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='G4.1 Deep Validation Engine')
    parser.add_argument('--limit', type=int, default=10, help='Max needles to validate')
    args = parser.parse_args()

    engine = G4_1_DeepValidationEngine()
    needles = engine.get_needles_for_deep_validation()

    print(f"\nFound {len(needles)} needles requiring G4.1 validation")
    print(f"Processing up to {args.limit} needles...\n")

    results = []
    for i, needle in enumerate(needles[:args.limit]):
        print(f"\n[{i+1}/{min(args.limit, len(needles))}] Validating {needle['needle_id'][:8]}... ({needle['classification']})")
        verdict = engine.run_full_validation(needle)
        results.append(verdict)

    # Summary
    print("\n" + "="*60)
    print("G4.1 DEEP VALIDATION SUMMARY")
    print("="*60)

    assessments = {}
    for r in results:
        a = r['edge_assessment']
        assessments[a] = assessments.get(a, 0) + 1

    for assessment in ['STABLE', 'CONDITIONAL', 'FRAGILE', 'ILLUSORY']:
        count = assessments.get(assessment, 0)
        pct = count / max(1, len(results)) * 100
        print(f"  {assessment:12s}: {count:3d} ({pct:5.1f}%)")

    print("="*60)
