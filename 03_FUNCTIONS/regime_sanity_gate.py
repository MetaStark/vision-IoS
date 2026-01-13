#!/usr/bin/env python3
"""
CEO-DIR-2026-053: Regime Sanity Gate

PURPOSE: Stop decision-making based on anti-correlated intelligence.

MANDATE:
  - Real-time check of historical regime accuracy
  - If accuracy < 30%:
    - Force confidence ≤ 0.50
    - Flag explicitly as LOW_CONFIDENCE
  - This flag is BINDING for all downstream decision layers

SUCCESS CRITERION:
  - Regime accuracy > 30% over rolling 7 days measured in shadow execution

OWNER: FINN (implementation), STIG (integration), VEGA (validation)

CONTEXT:
  - Diagnosed root cause: ANTI_CORRELATED_REGIME_PREDICTIONS
  - High-confidence regime predictions (0.95-1.0) achieve only 19.6% accuracy
  - Expected random for 4-class: 25%
  - System is WORSE than random chance
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('regime_sanity_gate')

# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# CEO-DIR-2026-053 MANDATED THRESHOLDS
ACCURACY_THRESHOLD = 0.30  # 30% - below this, predictions are worse than random
FORCED_LOW_CONFIDENCE = 0.50  # Maximum confidence when accuracy is below threshold
ROLLING_WINDOW_DAYS = 7  # 7-day rolling accuracy window


@dataclass
class RegimeAccuracyMetrics:
    """Accuracy metrics for a specific regime type."""
    regime_type: str
    total_predictions: int
    correct_predictions: int
    accuracy: float
    last_updated: datetime
    is_reliable: bool  # True if accuracy >= ACCURACY_THRESHOLD


class RegimeSanityGate:
    """
    CEO-DIR-2026-053 MANDATED COMPONENT

    This class implements sanity checks for regime predictions.
    It PREVENTS decision-making based on anti-correlated intelligence.

    NO BYPASS ALLOWED.
    """

    DIRECTIVE = "CEO-DIR-2026-053"

    def __init__(self, db_conn=None):
        """Initialize with database connection."""
        self.conn = db_conn
        self._accuracy_cache: Dict[str, RegimeAccuracyMetrics] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # Refresh every 5 minutes

    def _get_connection(self):
        """Get database connection, creating if necessary."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn

    def _load_regime_accuracy(self) -> Dict[str, RegimeAccuracyMetrics]:
        """Load rolling regime accuracy from calibration gates."""
        conn = self._get_connection()

        # Query calibration gates for regime forecasts
        query = """
            SELECT
                regime,
                confidence_band_min,
                confidence_band_max,
                historical_accuracy,
                sample_size,
                created_at
            FROM fhq_governance.confidence_calibration_gates
            WHERE forecast_type = 'REGIME'
              AND (effective_until IS NULL OR effective_until > NOW())
            ORDER BY created_at DESC
        """

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        # Aggregate accuracy by regime
        accuracy_by_regime: Dict[str, RegimeAccuracyMetrics] = {}

        # Calculate overall regime accuracy
        total_predictions = 0
        weighted_accuracy = 0.0

        for row in rows:
            sample_size = row['sample_size'] or 0
            accuracy = float(row['historical_accuracy'] or 0)
            total_predictions += sample_size
            weighted_accuracy += accuracy * sample_size

        if total_predictions > 0:
            overall_accuracy = weighted_accuracy / total_predictions
        else:
            overall_accuracy = 0.0

        # Store overall metrics
        accuracy_by_regime['ALL'] = RegimeAccuracyMetrics(
            regime_type='ALL',
            total_predictions=total_predictions,
            correct_predictions=int(total_predictions * overall_accuracy),
            accuracy=overall_accuracy,
            last_updated=datetime.now(timezone.utc),
            is_reliable=overall_accuracy >= ACCURACY_THRESHOLD
        )

        # Also query Brier score ledger for regime-specific accuracy
        regime_query = """
            SELECT
                regime,
                COUNT(*) as total,
                SUM(CASE WHEN actual_outcome = true THEN 1 ELSE 0 END) as correct,
                AVG(CASE WHEN actual_outcome = true THEN 1.0 ELSE 0.0 END) as accuracy
            FROM fhq_governance.brier_score_ledger
            WHERE forecast_type = 'REGIME'
              AND forecast_timestamp >= NOW() - INTERVAL '%s days'
            GROUP BY regime
        """

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(regime_query, (ROLLING_WINDOW_DAYS,))
                regime_rows = cur.fetchall()

            for row in regime_rows:
                regime = row['regime'] or 'UNKNOWN'
                accuracy = float(row['accuracy'] or 0)
                accuracy_by_regime[regime] = RegimeAccuracyMetrics(
                    regime_type=regime,
                    total_predictions=int(row['total']),
                    correct_predictions=int(row['correct'] or 0),
                    accuracy=accuracy,
                    last_updated=datetime.now(timezone.utc),
                    is_reliable=accuracy >= ACCURACY_THRESHOLD
                )
        except Exception as e:
            logger.warning(f"Could not load regime-specific accuracy: {e}")

        return accuracy_by_regime

    def _get_accuracy(self, regime: str = "ALL") -> Optional[RegimeAccuracyMetrics]:
        """Get regime accuracy with caching."""
        now = datetime.now(timezone.utc)

        # Refresh cache if stale
        if (self._cache_timestamp is None or
            (now - self._cache_timestamp).total_seconds() > self._cache_ttl_seconds):
            self._accuracy_cache = self._load_regime_accuracy()
            self._cache_timestamp = now
            logger.info(f"Refreshed regime accuracy cache: {len(self._accuracy_cache)} regimes loaded")

        # Try specific regime first, fall back to ALL
        if regime in self._accuracy_cache:
            return self._accuracy_cache[regime]

        return self._accuracy_cache.get('ALL')

    def check_regime_sanity(
        self,
        predicted_regime: str,
        raw_confidence: float,
        asset_id: str = None
    ) -> Dict:
        """
        MANDATORY SANITY CHECK FOR ALL REGIME PREDICTIONS

        This function MUST be called before any regime prediction is:
        - Written to database
        - Used in decision making
        - Passed to execution layer

        Args:
            predicted_regime: The predicted regime (BULL, BEAR, NEUTRAL, STRESS, etc.)
            raw_confidence: Original model confidence (0.0-1.0)
            asset_id: Optional asset identifier

        Returns:
            Dict with:
                - adjusted_confidence: The sanity-checked confidence
                - is_reliable: Whether this regime prediction can be trusted
                - forced_low_confidence: Whether confidence was forcibly capped
                - regime_accuracy: Historical accuracy for this regime type
                - warning_flags: List of warning flags
        """
        # Get accuracy metrics
        metrics = self._get_accuracy(predicted_regime)

        if metrics is None:
            # SAFETY: No data - assume unreliable
            logger.warning(
                f"[{self.DIRECTIVE}] No accuracy data for regime '{predicted_regime}'. "
                f"Forcing LOW_CONFIDENCE."
            )
            return {
                'adjusted_confidence': min(raw_confidence, FORCED_LOW_CONFIDENCE),
                'is_reliable': False,
                'forced_low_confidence': True,
                'regime_accuracy': None,
                'raw_confidence': raw_confidence,
                'predicted_regime': predicted_regime,
                'warning_flags': ['NO_ACCURACY_DATA', 'FORCED_LOW_CONFIDENCE'],
                'directive': self.DIRECTIVE
            }

        # Check if regime predictions are reliable
        is_reliable = metrics.is_reliable
        warning_flags = []

        if not is_reliable:
            warning_flags.append('ACCURACY_BELOW_THRESHOLD')
            warning_flags.append('ANTI_CORRELATED_RISK')

            if metrics.accuracy < 0.25:  # Worse than random
                warning_flags.append('WORSE_THAN_RANDOM')

        # Apply sanity gate
        if is_reliable:
            adjusted_confidence = raw_confidence
            forced_low = False
        else:
            # FORCE LOW CONFIDENCE - THIS IS MANDATORY
            adjusted_confidence = min(raw_confidence, FORCED_LOW_CONFIDENCE)
            forced_low = adjusted_confidence < raw_confidence
            warning_flags.append('FORCED_LOW_CONFIDENCE')

            logger.warning(
                f"[{self.DIRECTIVE}] REGIME SANITY GATE TRIGGERED: "
                f"'{predicted_regime}' accuracy={metrics.accuracy:.2%} < {ACCURACY_THRESHOLD:.0%} threshold. "
                f"Confidence: {raw_confidence:.4f} → {adjusted_confidence:.4f}"
            )

        result = {
            'adjusted_confidence': round(adjusted_confidence, 4),
            'is_reliable': is_reliable,
            'forced_low_confidence': forced_low,
            'regime_accuracy': round(metrics.accuracy, 4),
            'accuracy_threshold': ACCURACY_THRESHOLD,
            'sample_size': metrics.total_predictions,
            'raw_confidence': raw_confidence,
            'predicted_regime': predicted_regime,
            'warning_flags': warning_flags,
            'directive': self.DIRECTIVE
        }

        return result

    def gate_regime_signal(
        self,
        signal: Dict,
        regime_field: str = 'regime',
        confidence_field: str = 'confidence'
    ) -> Dict:
        """
        Apply sanity gate to a regime signal dictionary.

        Args:
            signal: Signal dictionary containing regime and confidence
            regime_field: Key for regime value
            confidence_field: Key for confidence value

        Returns:
            Updated signal with sanity-checked confidence and metadata
        """
        regime = signal.get(regime_field, 'UNKNOWN')
        raw_conf = signal.get(confidence_field, 0.5)

        check = self.check_regime_sanity(regime, raw_conf)

        # Update signal
        updated = signal.copy()
        updated[confidence_field] = check['adjusted_confidence']
        updated['_regime_sanity_checked'] = True
        updated['_regime_is_reliable'] = check['is_reliable']
        updated['_regime_accuracy'] = check['regime_accuracy']
        updated['_confidence_flags'] = check['warning_flags']

        if check['forced_low_confidence']:
            # Explicit LOW_CONFIDENCE flag as mandated
            updated['confidence_level'] = 'LOW_CONFIDENCE'
            updated['_sanity_gate_triggered'] = True

        return updated

    def get_regime_reliability_report(self) -> Dict:
        """Generate a report of regime prediction reliability."""
        # Refresh cache
        self._accuracy_cache = self._load_regime_accuracy()
        self._cache_timestamp = datetime.now(timezone.utc)

        report = {
            'directive': self.DIRECTIVE,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'accuracy_threshold': ACCURACY_THRESHOLD,
            'rolling_window_days': ROLLING_WINDOW_DAYS,
            'regimes': {}
        }

        for regime, metrics in self._accuracy_cache.items():
            report['regimes'][regime] = {
                'accuracy': round(metrics.accuracy, 4),
                'is_reliable': metrics.is_reliable,
                'total_predictions': metrics.total_predictions,
                'correct_predictions': metrics.correct_predictions,
                'status': 'RELIABLE' if metrics.is_reliable else 'UNRELIABLE'
            }

        # Overall assessment
        all_metrics = self._accuracy_cache.get('ALL')
        if all_metrics:
            report['overall_status'] = 'RELIABLE' if all_metrics.is_reliable else 'ANTI_CORRELATED'
            report['overall_accuracy'] = round(all_metrics.accuracy, 4)
        else:
            report['overall_status'] = 'NO_DATA'
            report['overall_accuracy'] = None

        return report


# Singleton instance
_gate_instance: Optional[RegimeSanityGate] = None

def get_regime_gate() -> RegimeSanityGate:
    """Get singleton gate instance."""
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = RegimeSanityGate()
    return _gate_instance


def check_regime_sanity(
    predicted_regime: str,
    raw_confidence: float
) -> Tuple[float, bool]:
    """
    MANDATORY ENTRY POINT FOR ALL REGIME PREDICTIONS

    Returns:
        Tuple of (adjusted_confidence, is_reliable)
    """
    gate = get_regime_gate()
    result = gate.check_regime_sanity(predicted_regime, raw_confidence)
    return result['adjusted_confidence'], result['is_reliable']


if __name__ == "__main__":
    # Test the sanity gate
    print(f"CEO-DIR-2026-053: Regime Sanity Gate Test")
    print("=" * 60)

    gate = RegimeSanityGate()

    # Get reliability report
    report = gate.get_regime_reliability_report()
    print(f"\nOverall Status: {report['overall_status']}")
    print(f"Overall Accuracy: {report['overall_accuracy']}")
    print(f"Accuracy Threshold: {report['accuracy_threshold']}")

    print("\nRegime Reliability:")
    print("-" * 40)
    for regime, data in report['regimes'].items():
        status_icon = "[OK]" if data['is_reliable'] else "[X]"
        print(f"  {status_icon} {regime}: {data['accuracy']:.1%} ({data['status']})")

    # Test cases
    print("\n" + "=" * 60)
    print("Sanity Check Tests:")
    print("-" * 60)

    test_cases = [
        ("BULL", 0.95, "High confidence BULL - should be gated if unreliable"),
        ("BEAR", 0.85, "High confidence BEAR"),
        ("NEUTRAL", 0.90, "High confidence NEUTRAL"),
        ("STRESS", 0.80, "STRESS regime"),
    ]

    for regime, conf, description in test_cases:
        result = gate.check_regime_sanity(regime, conf)
        status = "PASSED" if result['is_reliable'] else "GATED"
        print(f"\n{description}")
        print(f"  Regime: {regime}, Raw: {conf:.2f} -> Adjusted: {result['adjusted_confidence']:.2f}")
        print(f"  Status: {status}, Accuracy: {result['regime_accuracy']}")
        if result['warning_flags']:
            print(f"  Warnings: {', '.join(result['warning_flags'])}")

    print("\n" + "=" * 60)
    print("Sanity gate initialized and operational.")
