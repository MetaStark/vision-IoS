#!/usr/bin/env python3
"""
CEO-DIR-2026-053: Forecast Confidence Damper

PURPOSE: Eliminate systematic over-confidence by forcing predicted confidence
         to historically documented reality.

MANDATE:
  - Fetch confidence_ceiling from fhq_governance.confidence_calibration_gates
  - Hard-cap ALL raw model confidence at this ceiling
  - NO model, agent, or post-processor may bypass this layer

SUCCESS CRITERION:
  - 7-day rolling calibration gap < 0.15 for all confidence buckets

OWNER: FINN (implementation), STIG (integration), VEGA (validation)
"""

import os
import json
import logging
from datetime import datetime, timezone
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
logger = logging.getLogger('forecast_confidence_damper')

# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

@dataclass
class CalibrationGate:
    """Represents a confidence calibration gate from the database."""
    forecast_type: str
    regime: str
    band_min: float
    band_max: float
    historical_accuracy: float
    confidence_ceiling: float
    sample_size: int


class ForecastConfidenceDamper:
    """
    CEO-DIR-2026-053 MANDATED COMPONENT

    This class implements hard confidence caps based on historical calibration.
    It is UNENFORCEABLY MANDATORY for all forecast outputs.

    NO BYPASS ALLOWED.
    """

    DIRECTIVE = "CEO-DIR-2026-053"

    def __init__(self, db_conn=None):
        """Initialize with database connection."""
        self.conn = db_conn
        self._gates_cache: Dict[str, List[CalibrationGate]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # Refresh gates every 5 minutes

    def _get_connection(self):
        """Get database connection, creating if necessary."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
        return self.conn

    def _load_calibration_gates(self) -> Dict[str, List[CalibrationGate]]:
        """Load calibration gates from database."""
        conn = self._get_connection()

        query = """
            SELECT
                forecast_type,
                regime,
                confidence_band_min,
                confidence_band_max,
                historical_accuracy,
                confidence_ceiling,
                sample_size
            FROM fhq_governance.confidence_calibration_gates
            WHERE (effective_until IS NULL OR effective_until > NOW())
            ORDER BY forecast_type, confidence_band_min
        """

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        gates: Dict[str, List[CalibrationGate]] = {}
        for row in rows:
            gate = CalibrationGate(
                forecast_type=row['forecast_type'],
                regime=row['regime'],
                band_min=float(row['confidence_band_min']),
                band_max=float(row['confidence_band_max']),
                historical_accuracy=float(row['historical_accuracy']),
                confidence_ceiling=float(row['confidence_ceiling']),
                sample_size=row['sample_size']
            )

            key = f"{gate.forecast_type}:{gate.regime}"
            if key not in gates:
                gates[key] = []
            gates[key].append(gate)

        return gates

    def _get_gates(self, forecast_type: str, regime: str = "ALL") -> List[CalibrationGate]:
        """Get calibration gates with caching."""
        now = datetime.now(timezone.utc)

        # Refresh cache if stale
        if (self._cache_timestamp is None or
            (now - self._cache_timestamp).total_seconds() > self._cache_ttl_seconds):
            self._gates_cache = self._load_calibration_gates()
            self._cache_timestamp = now
            logger.info(f"Refreshed calibration gates cache: {len(self._gates_cache)} gate sets loaded")

        # Try specific regime first, fall back to ALL
        key = f"{forecast_type}:{regime}"
        if key in self._gates_cache:
            return self._gates_cache[key]

        key_all = f"{forecast_type}:ALL"
        if key_all in self._gates_cache:
            return self._gates_cache[key_all]

        logger.warning(f"No calibration gates found for {forecast_type}:{regime}")
        return []

    def _find_ceiling_for_confidence(
        self,
        raw_confidence: float,
        gates: List[CalibrationGate]
    ) -> Tuple[float, Optional[CalibrationGate]]:
        """Find the appropriate ceiling for a given raw confidence value."""
        for gate in gates:
            if gate.band_min <= raw_confidence < gate.band_max:
                return gate.confidence_ceiling, gate

        # If confidence is exactly 1.0, use the highest band
        if raw_confidence >= 1.0 and gates:
            highest_gate = max(gates, key=lambda g: g.band_max)
            return highest_gate.confidence_ceiling, highest_gate

        # No matching gate - return raw confidence with warning
        logger.warning(f"No calibration gate found for confidence {raw_confidence}")
        return raw_confidence, None

    def damp_confidence(
        self,
        raw_confidence: float,
        forecast_type: str = "PRICE_DIRECTION",
        regime: str = "ALL",
        log_dampening: bool = True
    ) -> Dict:
        """
        MANDATORY CONFIDENCE DAMPENING

        This function MUST be called for ALL forecast outputs.
        NO EXCEPTIONS. NO BYPASS.

        Args:
            raw_confidence: Original model confidence (0.0-1.0)
            forecast_type: Type of forecast (PRICE_DIRECTION, REGIME, etc.)
            regime: Current regime context (or ALL)
            log_dampening: Whether to log dampening events

        Returns:
            Dict with:
                - damped_confidence: The capped confidence value
                - was_damped: Boolean indicating if dampening occurred
                - dampening_delta: How much confidence was reduced
                - ceiling_applied: The ceiling that was applied
                - gate_info: Details about the calibration gate used
        """
        # Validate input
        raw_confidence = max(0.0, min(1.0, float(raw_confidence)))

        # Get applicable gates
        gates = self._get_gates(forecast_type, regime)

        if not gates:
            # SAFETY: If no gates found, apply conservative default ceiling
            default_ceiling = 0.50
            logger.warning(
                f"[{self.DIRECTIVE}] No calibration gates found for {forecast_type}:{regime}. "
                f"Applying conservative default ceiling of {default_ceiling}"
            )
            damped = min(raw_confidence, default_ceiling)
            return {
                'damped_confidence': damped,
                'was_damped': damped < raw_confidence,
                'dampening_delta': raw_confidence - damped,
                'ceiling_applied': default_ceiling,
                'gate_info': None,
                'directive': self.DIRECTIVE,
                'safety_mode': 'DEFAULT_CEILING'
            }

        # Find appropriate ceiling
        ceiling, gate = self._find_ceiling_for_confidence(raw_confidence, gates)

        # Apply hard cap - THIS IS UNENFORCEABLY MANDATORY
        damped_confidence = min(raw_confidence, ceiling)
        was_damped = damped_confidence < raw_confidence
        dampening_delta = raw_confidence - damped_confidence

        result = {
            'damped_confidence': round(damped_confidence, 4),
            'was_damped': was_damped,
            'dampening_delta': round(dampening_delta, 4),
            'ceiling_applied': ceiling,
            'raw_confidence': raw_confidence,
            'forecast_type': forecast_type,
            'regime': regime,
            'directive': self.DIRECTIVE,
            'gate_info': None
        }

        if gate:
            result['gate_info'] = {
                'band': f"{gate.band_min:.2f}-{gate.band_max:.2f}",
                'historical_accuracy': gate.historical_accuracy,
                'sample_size': gate.sample_size
            }

        # Log significant dampening events
        if log_dampening and was_damped and dampening_delta > 0.1:
            logger.info(
                f"[{self.DIRECTIVE}] CONFIDENCE DAMPED: {raw_confidence:.4f} → {damped_confidence:.4f} "
                f"(Δ={dampening_delta:.4f}) for {forecast_type}:{regime}"
            )

        return result

    def damp_forecast_batch(
        self,
        forecasts: List[Dict],
        confidence_field: str = 'confidence',
        forecast_type_field: str = 'forecast_type',
        regime_field: str = 'regime'
    ) -> List[Dict]:
        """
        Apply dampening to a batch of forecasts.

        Args:
            forecasts: List of forecast dictionaries
            confidence_field: Key containing raw confidence
            forecast_type_field: Key containing forecast type
            regime_field: Key containing regime

        Returns:
            List of forecasts with confidence dampened and metadata added
        """
        results = []
        damped_count = 0
        total_delta = 0.0

        for forecast in forecasts:
            raw_conf = forecast.get(confidence_field, 0.5)
            f_type = forecast.get(forecast_type_field, 'PRICE_DIRECTION')
            regime = forecast.get(regime_field, 'ALL')

            dampening = self.damp_confidence(raw_conf, f_type, regime, log_dampening=False)

            # Update forecast with damped confidence
            updated = forecast.copy()
            updated[confidence_field] = dampening['damped_confidence']
            updated['_dampening_applied'] = dampening['was_damped']
            updated['_raw_confidence'] = raw_conf
            updated['_dampening_delta'] = dampening['dampening_delta']
            updated['_directive'] = self.DIRECTIVE

            results.append(updated)

            if dampening['was_damped']:
                damped_count += 1
                total_delta += dampening['dampening_delta']

        if damped_count > 0:
            avg_delta = total_delta / damped_count
            logger.info(
                f"[{self.DIRECTIVE}] Batch dampening complete: {damped_count}/{len(forecasts)} "
                f"forecasts damped, avg Δ={avg_delta:.4f}"
            )

        return results

    def log_dampening_audit(
        self,
        raw_confidence: float,
        damped_confidence: float,
        forecast_type: str,
        forecast_id: str = None,
        asset_id: str = None
    ):
        """Log dampening event to calibration_audit_log for court-proof evidence."""
        conn = self._get_connection()

        query = """
            INSERT INTO fhq_governance.calibration_audit_log (
                audit_type,
                forecast_type,
                forecast_id,
                asset_id,
                raw_confidence,
                damped_confidence,
                dampening_delta,
                directive,
                created_at
            ) VALUES (
                'CONFIDENCE_DAMPENING',
                %s, %s, %s, %s, %s, %s, %s, NOW()
            )
        """

        try:
            with conn.cursor() as cur:
                cur.execute(query, (
                    forecast_type,
                    forecast_id,
                    asset_id,
                    raw_confidence,
                    damped_confidence,
                    raw_confidence - damped_confidence,
                    self.DIRECTIVE
                ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to log dampening audit: {e}")
            conn.rollback()


# Singleton instance for use across the system
_damper_instance: Optional[ForecastConfidenceDamper] = None

def get_damper() -> ForecastConfidenceDamper:
    """Get singleton damper instance."""
    global _damper_instance
    if _damper_instance is None:
        _damper_instance = ForecastConfidenceDamper()
    return _damper_instance


def damp_confidence(
    raw_confidence: float,
    forecast_type: str = "PRICE_DIRECTION",
    regime: str = "ALL"
) -> float:
    """
    MANDATORY ENTRY POINT FOR ALL CONFIDENCE VALUES

    This function MUST be called before any confidence value is:
    - Written to database
    - Used in decision making
    - Passed to execution layer

    NO EXCEPTIONS.
    """
    damper = get_damper()
    result = damper.damp_confidence(raw_confidence, forecast_type, regime)
    return result['damped_confidence']


if __name__ == "__main__":
    # Test the damper
    print(f"CEO-DIR-2026-053: Forecast Confidence Damper Test")
    print("=" * 60)

    damper = ForecastConfidenceDamper()

    # Test cases from diagnosed failure modes
    test_cases = [
        (0.967, "PRICE_DIRECTION", "ALL", "HIGH bucket - should be capped at ~0.40"),
        (0.811, "PRICE_DIRECTION", "ALL", "MEDIUM bucket - should be capped at ~0.52"),
        (0.953, "REGIME", "ALL", "REGIME high - should be capped at ~0.25"),
        (0.85, "PRICE_DIRECTION", "ALL", "Standard high confidence"),
        (0.50, "PRICE_DIRECTION", "ALL", "Medium confidence - minimal dampening"),
    ]

    print("\nTest Results:")
    print("-" * 60)

    for raw, f_type, regime, description in test_cases:
        result = damper.damp_confidence(raw, f_type, regime)
        print(f"\n{description}")
        print(f"  Raw: {raw:.4f} -> Damped: {result['damped_confidence']:.4f}")
        print(f"  Delta: {result['dampening_delta']:.4f}, Ceiling: {result['ceiling_applied']:.4f}")
        if result['gate_info']:
            print(f"  Gate: {result['gate_info']['band']}, Historical: {result['gate_info']['historical_accuracy']:.4f}")

    print("\n" + "=" * 60)
    print("Damper initialized and operational.")
