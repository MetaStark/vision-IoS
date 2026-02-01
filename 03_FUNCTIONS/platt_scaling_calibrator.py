#!/usr/bin/env python3
"""
Platt Scaling Calibrator - CEO-DIR-2026-META-ANALYSIS Phase 2
STIG (CTO) - System for Technical Implementation & Governance

Implements probability calibration using:
1. Platt Scaling (logistic regression)
2. Isotonic Regression (non-parametric, recommended)

Purpose: Improve Brier score from 0.32 to <0.28 by calibrating confidence scores
to match empirical accuracy.

Reference: Platt (1999), Zadrozny & Elkan (2002)

Usage:
    python platt_scaling_calibrator.py --fit          # Fit calibration model from data
    python platt_scaling_calibrator.py --calibrate 0.75  # Calibrate a raw confidence
    python platt_scaling_calibrator.py --status       # Show calibration status
    python platt_scaling_calibrator.py --evaluate     # Evaluate calibration improvement
"""

import os
import sys
import json
import argparse
import hashlib
import pickle
import base64
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import numpy as np
from decimal import Decimal

# Try to import sklearn, provide fallback if not available
try:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[WARNING] sklearn not available - using fallback calibration")

DIRECTIVE_ID = "CEO-DIR-2026-META-ANALYSIS"
VERSION = "1.0.0"

# Database config
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', '54322')),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}


@dataclass
class CalibrationModel:
    """Represents a fitted calibration model."""
    model_id: str
    model_type: str  # 'ISOTONIC', 'PLATT', 'BINNED'
    forecast_type: str
    fitted_at: datetime
    training_samples: int
    pre_calibration_brier: float
    post_calibration_brier: float
    improvement_pct: float
    model_params: Dict
    model_blob: Optional[str] = None  # base64 encoded pickle


class PlattScalingCalibrator:
    """
    Probability calibration using Platt scaling and isotonic regression.

    Addresses the overconfidence problem where raw model confidence
    doesn't match empirical accuracy.
    """

    def __init__(self):
        self.conn = None
        self.models: Dict[str, Any] = {}  # forecast_type -> fitted model
        self.calibration_maps: Dict[str, List[Tuple[float, float]]] = {}

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        print(f"[OK] Connected to database")

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()

    def get_training_data(self, forecast_type: str = 'PRICE_DIRECTION',
                          window_days: int = 90) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get training data from forecast_outcome_pairs.

        Returns:
            X: Raw confidence scores
            y: Binary outcomes (1 = correct, 0 = incorrect)
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    fop.forecast_confidence,
                    CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END as outcome
                FROM fhq_research.forecast_outcome_pairs fop
                JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
                WHERE fl.forecast_type = %s
                  AND fop.reconciled_at >= NOW() - INTERVAL '%s days'
                  AND fop.forecast_confidence IS NOT NULL
                ORDER BY fop.reconciled_at
            """, (forecast_type, window_days))

            rows = cur.fetchall()

        if not rows:
            print(f"[WARNING] No training data for {forecast_type}")
            return np.array([]), np.array([])

        X = np.array([float(r['forecast_confidence']) for r in rows])
        y = np.array([r['outcome'] for r in rows])

        print(f"[OK] Loaded {len(X)} training samples for {forecast_type}")
        print(f"     Accuracy: {y.mean()*100:.1f}%")
        print(f"     Confidence range: [{X.min():.2f}, {X.max():.2f}]")

        return X, y

    def compute_brier_score(self, y_true: np.ndarray, y_prob: np.ndarray) -> float:
        """Compute Brier score."""
        return np.mean((y_prob - y_true) ** 2)

    def fit_isotonic(self, X: np.ndarray, y: np.ndarray) -> Any:
        """
        Fit isotonic regression calibrator.

        Isotonic regression finds a monotonic function that minimizes
        mean squared error, perfect for probability calibration.
        """
        if not SKLEARN_AVAILABLE:
            return self._fit_binned_fallback(X, y)

        # Isotonic regression
        ir = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds='clip')
        ir.fit(X.reshape(-1, 1), y)

        return ir

    def fit_platt(self, X: np.ndarray, y: np.ndarray) -> Any:
        """
        Fit Platt scaling (logistic regression) calibrator.

        Maps raw scores through sigmoid: P(y=1|f) = 1 / (1 + exp(A*f + B))
        """
        if not SKLEARN_AVAILABLE:
            return self._fit_binned_fallback(X, y)

        # Logistic regression on raw confidence
        lr = LogisticRegression(solver='lbfgs', max_iter=1000)
        lr.fit(X.reshape(-1, 1), y)

        return lr

    def _fit_binned_fallback(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """
        Fallback binned calibration when sklearn not available.

        Creates a lookup table mapping confidence bins to empirical accuracy.
        """
        # Create 10 equal-width bins
        bins = np.linspace(0, 1, 11)
        bin_indices = np.digitize(X, bins) - 1
        bin_indices = np.clip(bin_indices, 0, 9)

        calibration_map = {}
        for i in range(10):
            mask = bin_indices == i
            if mask.sum() > 0:
                bin_center = (bins[i] + bins[i+1]) / 2
                empirical_prob = y[mask].mean()
                calibration_map[i] = {
                    'bin_center': float(bin_center),
                    'empirical_prob': float(empirical_prob),
                    'sample_count': int(mask.sum())
                }

        return {'type': 'BINNED', 'bins': bins.tolist(), 'calibration_map': calibration_map}

    def calibrate_confidence(self, raw_confidence: float, model: Any) -> float:
        """Apply calibration model to raw confidence."""
        if isinstance(model, dict) and model.get('type') == 'BINNED':
            # Binned fallback
            bins = np.array(model['bins'])
            bin_idx = np.digitize([raw_confidence], bins)[0] - 1
            bin_idx = max(0, min(9, bin_idx))

            if bin_idx in model['calibration_map']:
                return model['calibration_map'][bin_idx]['empirical_prob']
            return raw_confidence

        elif SKLEARN_AVAILABLE:
            # sklearn model
            if hasattr(model, 'predict'):
                # Isotonic regression
                return float(model.predict([[raw_confidence]])[0])
            elif hasattr(model, 'predict_proba'):
                # Logistic regression
                return float(model.predict_proba([[raw_confidence]])[0, 1])

        return raw_confidence

    def fit_and_evaluate(self, forecast_type: str = 'PRICE_DIRECTION',
                         method: str = 'ISOTONIC') -> CalibrationModel:
        """
        Fit calibration model and evaluate improvement.

        Args:
            forecast_type: Type of forecast to calibrate
            method: 'ISOTONIC', 'PLATT', or 'BINNED'

        Returns:
            CalibrationModel with fit results
        """
        print(f"\n{'='*60}")
        print(f"FITTING {method} CALIBRATION")
        print(f"Forecast Type: {forecast_type}")
        print(f"{'='*60}")

        # Get training data
        X, y = self.get_training_data(forecast_type)

        if len(X) < 100:
            print(f"[ERROR] Insufficient data: {len(X)} samples (need 100+)")
            return None

        # Split for evaluation (80/20)
        n_train = int(len(X) * 0.8)
        X_train, X_test = X[:n_train], X[n_train:]
        y_train, y_test = y[:n_train], y[n_train:]

        # Pre-calibration Brier
        pre_brier = self.compute_brier_score(y_test, X_test)
        print(f"\n[BASELINE] Pre-calibration Brier: {pre_brier:.4f}")

        # Fit model
        if method == 'ISOTONIC':
            model = self.fit_isotonic(X_train, y_train)
        elif method == 'PLATT':
            model = self.fit_platt(X_train, y_train)
        else:
            model = self._fit_binned_fallback(X_train, y_train)

        # Calibrate test set
        calibrated_probs = np.array([self.calibrate_confidence(x, model) for x in X_test])

        # Post-calibration Brier
        post_brier = self.compute_brier_score(y_test, calibrated_probs)
        improvement = (pre_brier - post_brier) / pre_brier * 100

        print(f"[CALIBRATED] Post-calibration Brier: {post_brier:.4f}")
        print(f"[IMPROVEMENT] {improvement:.1f}% reduction in Brier score")

        # Show calibration examples
        print(f"\nCalibration Examples:")
        for raw in [0.95, 0.80, 0.65, 0.50, 0.35]:
            cal = self.calibrate_confidence(raw, model)
            print(f"  {raw:.2f} -> {cal:.2f}")

        # Serialize model
        model_blob = None
        if SKLEARN_AVAILABLE and not isinstance(model, dict):
            model_blob = base64.b64encode(pickle.dumps(model)).decode('utf-8')

        # Generate model ID
        model_id = hashlib.md5(
            f"{forecast_type}:{method}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        result = CalibrationModel(
            model_id=model_id,
            model_type=method,
            forecast_type=forecast_type,
            fitted_at=datetime.now(timezone.utc),
            training_samples=len(X_train),
            pre_calibration_brier=float(pre_brier),
            post_calibration_brier=float(post_brier),
            improvement_pct=float(improvement),
            model_params=model if isinstance(model, dict) else {},
            model_blob=model_blob
        )

        # Store in memory
        self.models[forecast_type] = model

        return result

    def save_calibration_model(self, cal_model: CalibrationModel) -> str:
        """Save calibration model to database."""
        with self.conn.cursor() as cur:
            # Check if table exists, create if not
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fhq_governance.probability_calibration_models (
                    model_id TEXT PRIMARY KEY,
                    model_type TEXT NOT NULL,
                    forecast_type TEXT NOT NULL,
                    fitted_at TIMESTAMPTZ NOT NULL,
                    training_samples INTEGER,
                    pre_calibration_brier NUMERIC,
                    post_calibration_brier NUMERIC,
                    improvement_pct NUMERIC,
                    model_params JSONB,
                    model_blob TEXT,
                    is_active BOOLEAN DEFAULT true,
                    approved_by TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Deactivate previous models for this forecast type
            cur.execute("""
                UPDATE fhq_governance.probability_calibration_models
                SET is_active = false
                WHERE forecast_type = %s AND is_active = true
            """, (cal_model.forecast_type,))

            # Insert new model
            cur.execute("""
                INSERT INTO fhq_governance.probability_calibration_models
                (model_id, model_type, forecast_type, fitted_at, training_samples,
                 pre_calibration_brier, post_calibration_brier, improvement_pct,
                 model_params, model_blob, is_active, approved_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, 'STIG')
            """, (
                cal_model.model_id,
                cal_model.model_type,
                cal_model.forecast_type,
                cal_model.fitted_at,
                cal_model.training_samples,
                cal_model.pre_calibration_brier,
                cal_model.post_calibration_brier,
                cal_model.improvement_pct,
                Json(cal_model.model_params),
                cal_model.model_blob
            ))

            self.conn.commit()

        print(f"[OK] Model saved: {cal_model.model_id}")
        return cal_model.model_id

    def load_active_model(self, forecast_type: str) -> Optional[Any]:
        """Load active calibration model from database."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT model_id, model_type, model_params, model_blob
                FROM fhq_governance.probability_calibration_models
                WHERE forecast_type = %s AND is_active = true
                ORDER BY fitted_at DESC
                LIMIT 1
            """, (forecast_type,))

            row = cur.fetchone()

        if not row:
            return None

        # Deserialize
        if row['model_blob'] and SKLEARN_AVAILABLE:
            model = pickle.loads(base64.b64decode(row['model_blob']))
            self.models[forecast_type] = model
            return model
        elif row['model_params']:
            self.models[forecast_type] = row['model_params']
            return row['model_params']

        return None

    def get_status(self) -> Dict[str, Any]:
        """Get current calibration status."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'fhq_governance'
                    AND table_name = 'probability_calibration_models'
                )
            """)
            table_exists = cur.fetchone()['exists']

            if not table_exists:
                return {'status': 'NOT_INITIALIZED', 'models': []}

            cur.execute("""
                SELECT model_id, model_type, forecast_type, fitted_at,
                       training_samples, pre_calibration_brier, post_calibration_brier,
                       improvement_pct, is_active
                FROM fhq_governance.probability_calibration_models
                WHERE is_active = true
                ORDER BY forecast_type
            """)

            models = [dict(row) for row in cur.fetchall()]

        return {
            'status': 'ACTIVE' if models else 'NO_MODELS',
            'models': models,
            'sklearn_available': SKLEARN_AVAILABLE
        }

    def generate_evidence(self, cal_model: CalibrationModel) -> str:
        """Generate VEGA-compliant evidence file."""
        evidence = {
            'directive': DIRECTIVE_ID,
            'phase': 'Phase 2 - Calibration Enhancement',
            'component': 'PLATT_SCALING_CALIBRATOR',
            'version': VERSION,
            'execution_timestamp': datetime.now(timezone.utc).isoformat(),
            'model': asdict(cal_model),
            'verification': {
                'pre_brier': cal_model.pre_calibration_brier,
                'post_brier': cal_model.post_calibration_brier,
                'improvement_pct': cal_model.improvement_pct,
                'target_met': cal_model.post_calibration_brier < 0.28
            },
            'computed_by': 'EC-003',
            'sklearn_used': SKLEARN_AVAILABLE
        }

        # Generate hash
        evidence_hash = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, default=str).encode()
        ).hexdigest()
        evidence['evidence_hash'] = evidence_hash

        # Write to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(
            evidence_dir,
            f"CEO_DIR_2026_META_ANALYSIS_PLATT_CALIBRATION_{timestamp}.json"
        )

        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)

        print(f"[OK] Evidence: {os.path.basename(evidence_path)}")
        return evidence_path


def main():
    parser = argparse.ArgumentParser(
        description='Platt Scaling Calibrator - CEO-DIR-2026-META-ANALYSIS Phase 2'
    )
    parser.add_argument('--fit', action='store_true',
                        help='Fit calibration model from historical data')
    parser.add_argument('--method', choices=['ISOTONIC', 'PLATT', 'BINNED'],
                        default='ISOTONIC', help='Calibration method')
    parser.add_argument('--forecast-type', default='PRICE_DIRECTION',
                        help='Forecast type to calibrate')
    parser.add_argument('--calibrate', type=float,
                        help='Calibrate a raw confidence value')
    parser.add_argument('--status', action='store_true',
                        help='Show calibration status')
    parser.add_argument('--evaluate', action='store_true',
                        help='Evaluate current calibration improvement')
    parser.add_argument('--all-types', action='store_true',
                        help='Fit models for all forecast types')

    args = parser.parse_args()

    print("=" * 60)
    print("PLATT SCALING CALIBRATOR")
    print(f"Directive: {DIRECTIVE_ID} Phase 2")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"sklearn available: {SKLEARN_AVAILABLE}")
    print("=" * 60)

    calibrator = PlattScalingCalibrator()
    calibrator.connect()

    try:
        if args.fit:
            if args.all_types:
                # Fit for multiple forecast types
                forecast_types = ['PRICE_DIRECTION', 'VOLATILITY', 'REGIME_CHANGE']
                for ft in forecast_types:
                    print(f"\n--- Fitting {ft} ---")
                    result = calibrator.fit_and_evaluate(ft, args.method)
                    if result:
                        calibrator.save_calibration_model(result)
                        calibrator.generate_evidence(result)
            else:
                result = calibrator.fit_and_evaluate(args.forecast_type, args.method)
                if result:
                    calibrator.save_calibration_model(result)
                    calibrator.generate_evidence(result)

        elif args.calibrate is not None:
            # Load model and calibrate
            model = calibrator.load_active_model(args.forecast_type)
            if model:
                calibrated = calibrator.calibrate_confidence(args.calibrate, model)
                print(f"\nRaw confidence: {args.calibrate:.4f}")
                print(f"Calibrated:     {calibrated:.4f}")
            else:
                print(f"[ERROR] No active model for {args.forecast_type}")
                print("        Run --fit first to create a model")

        elif args.status:
            status = calibrator.get_status()
            print(f"\nCalibration Status: {status['status']}")
            print(f"sklearn available: {status['sklearn_available']}")

            if status['models']:
                print("\nActive Models:")
                for m in status['models']:
                    print(f"\n  [{m['forecast_type']}]")
                    print(f"    Model: {m['model_type']} ({m['model_id']})")
                    print(f"    Fitted: {m['fitted_at']}")
                    print(f"    Samples: {m['training_samples']}")
                    print(f"    Pre-Brier: {float(m['pre_calibration_brier']):.4f}")
                    print(f"    Post-Brier: {float(m['post_calibration_brier']):.4f}")
                    print(f"    Improvement: {float(m['improvement_pct']):.1f}%")
            else:
                print("\n  No active models. Run --fit to create.")

        elif args.evaluate:
            # Quick evaluation without saving
            result = calibrator.fit_and_evaluate(args.forecast_type, args.method)
            if result:
                print(f"\n[RESULT] Would achieve {result.improvement_pct:.1f}% improvement")
                print(f"         Brier: {result.pre_calibration_brier:.4f} -> {result.post_calibration_brier:.4f}")

                if result.post_calibration_brier < 0.28:
                    print(f"\n         [SUCCESS] Target Brier < 0.28 ACHIEVED!")
                else:
                    gap = result.post_calibration_brier - 0.28
                    print(f"\n         [PROGRESS] Still {gap:.4f} above target")

        else:
            parser.print_help()

    finally:
        calibrator.close()

    print("\n" + "=" * 60)
    print("CALIBRATOR COMPLETE")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
