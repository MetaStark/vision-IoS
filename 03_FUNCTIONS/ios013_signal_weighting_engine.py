#!/usr/bin/env python3
"""
IoS-013 SIGNAL WEIGHTING ENGINE
================================
Directive: CEO-DIR-2026-120 P2.2
Classification: G4_SIGNAL_SYNTHESIS
Date: 2026-01-22

Implements 5-factor signal weighting methodology per IoS-013 spec:
1. Regime-samsvar (alignment) - 0.2 to 1.0
2. Forecast skill via Brier score - 0.1 to 1.0
3. Causal linkage strength - 0.3 to 1.2
4. Redundancy filter - -0.2 to -0.5
5. Event proximity penalty - -0.1 to -0.3

Populates fhq_signal_context.weighted_signal_plan daily.
Logs conflicts to signal_conflict_registry.

Authority: CEO, LARS (Strategy), STIG (Technical)
Employment Contract: EC-003
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

# Load environment
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[IoS-013-WEIGHT] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


@dataclass
class SignalWeightFactors:
    """Individual weighting factors for a signal."""
    regime_alignment: float = 1.0        # 0.2 - 1.0
    forecast_skill: float = 0.5          # 0.1 - 1.0 (Brier score based)
    causal_linkage: float = 0.5          # 0.3 - 1.2
    redundancy_penalty: float = 0.0      # -0.5 to 0
    event_proximity_penalty: float = 0.0  # -0.3 to 0

    @property
    def composite_weight(self) -> float:
        """Compute composite weight from all factors."""
        base_weight = self.regime_alignment * self.forecast_skill * self.causal_linkage
        penalties = self.redundancy_penalty + self.event_proximity_penalty
        return max(0.1, min(1.0, base_weight + penalties))  # Clamp to [0.1, 1.0]


@dataclass
class WeightedSignal:
    """A signal with computed weights."""
    signal_id: str
    asset_id: str
    signal_type: str
    direction: str
    raw_confidence: float
    weight_factors: SignalWeightFactors
    weighted_confidence: float
    regime_context: str
    explanation: str


@dataclass
class SignalConflict:
    """Detected conflict between signals."""
    conflict_id: str
    asset_id: str
    conflicting_signals: List[str]
    conflict_type: str  # DIRECTION, REGIME, REDUNDANCY
    resolution: str     # HIGHEST_WEIGHT, AVERAGE, SUPPRESSED
    resolved_direction: Optional[str]


class IoS013SignalWeightingEngine:
    """
    Signal Weighting Engine per IoS-013 specification.

    Transforms raw signals into weighted, conflict-resolved signal plans.
    """

    # Weight factor bounds
    REGIME_WEIGHT_MIN = 0.2
    REGIME_WEIGHT_MAX = 1.0
    FORECAST_WEIGHT_MIN = 0.1
    FORECAST_WEIGHT_MAX = 1.0
    CAUSAL_WEIGHT_MIN = 0.3
    CAUSAL_WEIGHT_MAX = 1.2
    REDUNDANCY_PENALTY_MAX = -0.5
    EVENT_PENALTY_MAX = -0.3

    # Regime alignment scores by signal type
    REGIME_ALIGNMENT_MATRIX = {
        # (signal_type, regime) -> alignment score
        ('MOMENTUM_UP', 'STRONG_BULL'): 1.0,
        ('MOMENTUM_UP', 'MODERATE_BULL'): 0.9,
        ('MOMENTUM_UP', 'NEUTRAL'): 0.7,
        ('MOMENTUM_UP', 'MODERATE_BEAR'): 0.4,
        ('MOMENTUM_UP', 'VOLATILE'): 0.5,
        ('MOMENTUM_UP', 'STRESS'): 0.2,

        ('MOMENTUM_DOWN', 'STRONG_BULL'): 0.3,
        ('MOMENTUM_DOWN', 'MODERATE_BULL'): 0.5,
        ('MOMENTUM_DOWN', 'NEUTRAL'): 0.7,
        ('MOMENTUM_DOWN', 'MODERATE_BEAR'): 0.9,
        ('MOMENTUM_DOWN', 'VOLATILE'): 0.6,
        ('MOMENTUM_DOWN', 'STRESS'): 0.8,

        ('MEAN_REVERSION', 'STRONG_BULL'): 0.4,
        ('MEAN_REVERSION', 'MODERATE_BULL'): 0.6,
        ('MEAN_REVERSION', 'NEUTRAL'): 1.0,
        ('MEAN_REVERSION', 'MODERATE_BEAR'): 0.6,
        ('MEAN_REVERSION', 'VOLATILE'): 0.3,
        ('MEAN_REVERSION', 'STRESS'): 0.2,

        ('VOLATILITY_BREAKOUT', 'STRONG_BULL'): 0.5,
        ('VOLATILITY_BREAKOUT', 'MODERATE_BULL'): 0.6,
        ('VOLATILITY_BREAKOUT', 'NEUTRAL'): 0.5,
        ('VOLATILITY_BREAKOUT', 'MODERATE_BEAR'): 0.7,
        ('VOLATILITY_BREAKOUT', 'VOLATILE'): 1.0,
        ('VOLATILITY_BREAKOUT', 'STRESS'): 0.8,

        ('MACRO_ALIGNED', 'STRONG_BULL'): 0.9,
        ('MACRO_ALIGNED', 'MODERATE_BULL'): 0.85,
        ('MACRO_ALIGNED', 'NEUTRAL'): 0.7,
        ('MACRO_ALIGNED', 'MODERATE_BEAR'): 0.6,
        ('MACRO_ALIGNED', 'VOLATILE'): 0.5,
        ('MACRO_ALIGNED', 'STRESS'): 0.4,

        # Golden Needle signal types (added for IoS-013 aggregation)
        ('GOLDEN_NEEDLE', 'STRONG_BULL'): 0.95,
        ('GOLDEN_NEEDLE', 'MODERATE_BULL'): 0.9,
        ('GOLDEN_NEEDLE', 'NEUTRAL'): 0.85,
        ('GOLDEN_NEEDLE', 'MODERATE_BEAR'): 0.7,
        ('GOLDEN_NEEDLE', 'VOLATILE'): 0.6,
        ('GOLDEN_NEEDLE', 'STRESS'): 0.5,
        ('GOLDEN_NEEDLE', 'BULLISH'): 0.9,
        ('GOLDEN_NEEDLE', 'BEARISH'): 0.7,
    }

    def __init__(self):
        self.conn = None
        self.conflicts: List[SignalConflict] = []
        self._version = "1.0.0"

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()

    def get_current_regime(self, asset_id: str) -> Tuple[str, float]:
        """Get current regime classification for asset."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # Try asset-specific regime first
                cur.execute("""
                    SELECT regime_label, confidence
                    FROM fhq_research.regime_predictions
                    WHERE listing_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (asset_id,))
                row = cur.fetchone()

                if row and row.get('regime_label'):
                    return row['regime_label'], float(row.get('confidence') or 0.5)

                # Fallback to global regime
                cur.execute("""
                    SELECT current_regime, 0.7 as confidence
                    FROM fhq_research.global_regime_state
                    ORDER BY updated_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()

                if row and row.get('current_regime'):
                    return row['current_regime'], float(row.get('confidence') or 0.7)

            except Exception as e:
                logger.warning(f"Could not get regime for {asset_id}: {e}")

            return 'NEUTRAL', 0.5

    def get_forecast_skill(self, signal_type: str, asset_id: str) -> float:
        """
        Get forecast skill for signal type (Brier score based).

        Lower Brier = higher skill. Map to 0.1-1.0 weight.
        Uses fhq_research.forecast_skill_metrics with MODEL scope.
        """
        # Map signal types to strategy models
        signal_to_model = {
            'MOMENTUM_UP': 'STRAT_DAY_V1',
            'MOMENTUM_DOWN': 'STRAT_DAY_V1',
            'MEAN_REVERSION': 'STRAT_HOUR_V1',
            'VOLATILITY_BREAKOUT': 'STRAT_SEC_V1',
            'MACRO_ALIGNED': 'STRAT_WEEK_V1',
            'GOLDEN_NEEDLE': 'STRAT_WEEK_V1',  # Golden Needles are weekly signals
            'REGIME_EDGE': 'STRAT_DAY_V1',
            'TIMING': 'STRAT_HOUR_V1',
            'VOLATILITY': 'STRAT_SEC_V1',
        }
        model = signal_to_model.get(signal_type, 'STRAT_DAY_V1')

        with self.conn.cursor() as cur:
            try:
                # Try MODEL scope first
                cur.execute("""
                    SELECT brier_score_mean, forecast_count
                    FROM fhq_research.forecast_skill_metrics
                    WHERE metric_scope = 'MODEL' AND scope_value = %s
                    ORDER BY computed_at DESC
                    LIMIT 1
                """, (model,))
                row = cur.fetchone()

                if row and row[0] is not None:
                    brier_score = float(row[0])
                    # Map Brier score (0=perfect, 0.25=random) to weight
                    # 0 -> 1.0, 0.25 -> 0.1
                    skill_weight = max(0.1, 1.0 - (brier_score * 3.6))
                    return round(skill_weight, 3)

                # Fallback to GLOBAL scope
                cur.execute("""
                    SELECT brier_score_mean
                    FROM fhq_research.forecast_skill_metrics
                    WHERE metric_scope = 'GLOBAL' AND scope_value = 'ALL_ASSETS'
                    ORDER BY computed_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()

                if row and row[0] is not None:
                    brier_score = float(row[0])
                    skill_weight = max(0.1, 1.0 - (brier_score * 3.6))
                    return round(skill_weight, 3)

            except Exception as e:
                logger.warning(f"Could not get forecast skill for {signal_type}: {e}")

        return 0.5  # Default neutral weight

    def get_causal_linkage(self, signal_type: str, asset_id: str) -> float:
        """
        Get causal linkage strength from ontology.

        Higher linkage = stronger theoretical backing.
        """
        with self.conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT path_weight
                    FROM fhq_research.ontology_path_weights
                    WHERE signal_type = %s
                    AND (asset_class = %s OR asset_class = 'EQUITY')
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (signal_type, asset_id[:3] if len(asset_id) > 3 else 'EQUITY'))
                row = cur.fetchone()

                if row and row[0] is not None:
                    # path_weight typically 0-1, map to 0.3-1.2
                    raw_weight = float(row[0])
                    causal_weight = 0.3 + (raw_weight * 0.9)
                    return round(min(1.2, causal_weight), 3)

            except Exception as e:
                logger.warning(f"Could not get causal linkage: {e}")

        return 0.5  # Default neutral

    def calculate_redundancy_penalty(
        self,
        signal_id: str,
        asset_id: str,
        all_signals: List[Dict]
    ) -> float:
        """
        Calculate redundancy penalty when multiple signals agree.

        Higher correlation between signals = higher penalty for redundancy.
        """
        if len(all_signals) <= 1:
            return 0.0

        # Count signals with same direction for this asset
        same_direction_count = sum(
            1 for s in all_signals
            if s.get('asset_id') == asset_id
            and s.get('signal_id') != signal_id
            and s.get('direction') == next(
                (x['direction'] for x in all_signals if x['signal_id'] == signal_id),
                None
            )
        )

        if same_direction_count == 0:
            return 0.0

        # Apply logarithmic penalty for redundancy
        # 1 redundant = -0.1, 2 = -0.15, 3+ = -0.2
        penalty = min(0.2, 0.1 + (same_direction_count * 0.05))
        return -penalty

    def calculate_event_proximity_penalty(self, asset_id: str) -> float:
        """
        Calculate penalty for signals near major events (FOMC, earnings, etc.).

        Signals close to events have higher uncertainty.
        """
        with self.conn.cursor() as cur:
            try:
                # Check for upcoming events in next 3 days
                cur.execute("""
                    SELECT event_type, event_date, impact_score
                    FROM fhq_calendar.market_events
                    WHERE (asset_id = %s OR asset_id = 'GLOBAL')
                    AND event_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '3 days'
                    ORDER BY impact_score DESC
                    LIMIT 1
                """, (asset_id,))
                row = cur.fetchone()

                if row and row[2] is not None:
                    impact = float(row[2])
                    # High impact events = larger penalty
                    if impact >= 0.8:
                        return -0.3
                    elif impact >= 0.5:
                        return -0.2
                    elif impact >= 0.3:
                        return -0.1

            except Exception as e:
                logger.warning(f"Could not check event proximity: {e}")

        return 0.0

    def compute_signal_weights(
        self,
        signal: Dict,
        all_signals: List[Dict]
    ) -> WeightedSignal:
        """Compute weighted signal from raw signal."""
        asset_id = signal['asset_id']
        signal_type = signal.get('signal_type', 'UNKNOWN')

        # Get current regime
        regime, regime_conf = self.get_current_regime(asset_id)

        # Factor 1: Regime alignment
        alignment_key = (signal_type, regime)
        regime_alignment = self.REGIME_ALIGNMENT_MATRIX.get(
            alignment_key,
            0.5  # Default if not in matrix
        )

        # Factor 2: Forecast skill
        forecast_skill = self.get_forecast_skill(signal_type, asset_id)

        # Factor 3: Causal linkage
        causal_linkage = self.get_causal_linkage(signal_type, asset_id)

        # Factor 4: Redundancy penalty
        redundancy_penalty = self.calculate_redundancy_penalty(
            signal['signal_id'], asset_id, all_signals
        )

        # Factor 5: Event proximity penalty
        event_penalty = self.calculate_event_proximity_penalty(asset_id)

        # Build weight factors
        factors = SignalWeightFactors(
            regime_alignment=regime_alignment,
            forecast_skill=forecast_skill,
            causal_linkage=causal_linkage,
            redundancy_penalty=redundancy_penalty,
            event_proximity_penalty=event_penalty
        )

        # Compute weighted confidence
        raw_confidence = float(signal.get('confidence', 0.5))
        weighted_confidence = raw_confidence * factors.composite_weight

        # Build explanation
        explanation = (
            f"Regime={regime}({regime_alignment:.2f}), "
            f"Skill={forecast_skill:.2f}, Causal={causal_linkage:.2f}, "
            f"Redundancy={redundancy_penalty:.2f}, Event={event_penalty:.2f} "
            f"=> Weight={factors.composite_weight:.3f}"
        )

        return WeightedSignal(
            signal_id=signal['signal_id'],
            asset_id=asset_id,
            signal_type=signal_type,
            direction=signal.get('direction', 'NEUTRAL'),
            raw_confidence=raw_confidence,
            weight_factors=factors,
            weighted_confidence=weighted_confidence,
            regime_context=regime,
            explanation=explanation
        )

    def detect_conflicts(
        self,
        weighted_signals: List[WeightedSignal]
    ) -> List[SignalConflict]:
        """Detect conflicts between signals for same asset."""
        conflicts = []
        asset_signals = {}

        # Group by asset
        for ws in weighted_signals:
            if ws.asset_id not in asset_signals:
                asset_signals[ws.asset_id] = []
            asset_signals[ws.asset_id].append(ws)

        # Check each asset for conflicts
        for asset_id, signals in asset_signals.items():
            if len(signals) <= 1:
                continue

            # Direction conflicts
            directions = set(s.direction for s in signals)
            if len(directions) > 1 and 'UP' in directions and 'DOWN' in directions:
                conflict = SignalConflict(
                    conflict_id=hashlib.md5(
                        f"{asset_id}_{datetime.now().isoformat()}".encode()
                    ).hexdigest()[:16],
                    asset_id=asset_id,
                    conflicting_signals=[s.signal_id for s in signals],
                    conflict_type='DIRECTION',
                    resolution='HIGHEST_WEIGHT',
                    resolved_direction=max(signals, key=lambda s: s.weighted_confidence).direction
                )
                conflicts.append(conflict)
                logger.warning(
                    f"CONFLICT: {asset_id} has conflicting directions "
                    f"{directions} - resolved to {conflict.resolved_direction}"
                )

        return conflicts

    def resolve_conflicts(
        self,
        weighted_signals: List[WeightedSignal],
        conflicts: List[SignalConflict]
    ) -> List[WeightedSignal]:
        """Apply conflict resolution to signals."""
        resolved = []
        suppressed_ids = set()

        # Mark suppressed signals from conflicts
        for conflict in conflicts:
            if conflict.resolution == 'HIGHEST_WEIGHT':
                # Keep only highest weight signal for conflicted asset
                asset_signals = [
                    ws for ws in weighted_signals
                    if ws.asset_id == conflict.asset_id
                ]
                if asset_signals:
                    winner = max(asset_signals, key=lambda s: s.weighted_confidence)
                    for s in asset_signals:
                        if s.signal_id != winner.signal_id:
                            suppressed_ids.add(s.signal_id)

        # Build resolved list
        for ws in weighted_signals:
            if ws.signal_id not in suppressed_ids:
                resolved.append(ws)

        return resolved

    def save_weighted_plan(
        self,
        weighted_signals: List[WeightedSignal],
        conflicts: List[SignalConflict]
    ) -> str:
        """Save weighted signal plan to database."""
        plan_date = datetime.now(timezone.utc).date()

        for ws in weighted_signals:
            try:
                with self.conn.cursor() as cur:
                    # Build input hashes for lineage
                    input_hashes = {
                        'signal_id': ws.signal_id,
                        'regime': ws.regime_context,
                        'weight_factors': asdict(ws.weight_factors)
                    }
                    lineage_hash = hashlib.sha256(
                        json.dumps(input_hashes, sort_keys=True).encode()
                    ).hexdigest()[:16]

                    cur.execute("""
                        INSERT INTO fhq_signal_context.weighted_signal_plan (
                            plan_id, asset_id, computation_date, regime_context,
                            regime_confidence, raw_signals, weighted_signals,
                            confidence_score, explainability_trace, semantic_conflicts,
                            input_hashes, lineage_hash, computed_by, ios_version, created_at
                        ) VALUES (
                            gen_random_uuid(), %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s, %s, NOW()
                        )
                        ON CONFLICT (asset_id, computation_date) DO UPDATE SET
                            regime_context = EXCLUDED.regime_context,
                            weighted_signals = EXCLUDED.weighted_signals,
                            confidence_score = EXCLUDED.confidence_score,
                            explainability_trace = EXCLUDED.explainability_trace,
                            lineage_hash = EXCLUDED.lineage_hash,
                            created_at = NOW()
                    """, (
                        ws.asset_id,
                        plan_date,
                        ws.regime_context,
                        ws.weight_factors.regime_alignment,
                        Json({'signal_id': ws.signal_id, 'raw_confidence': ws.raw_confidence}),
                        Json({
                            'weighted_confidence': ws.weighted_confidence,
                            'direction': ws.direction,
                            'factors': asdict(ws.weight_factors)
                        }),
                        ws.weighted_confidence,
                        ws.explanation,
                        [c.conflict_id for c in conflicts if ws.asset_id == c.asset_id],
                        Json(input_hashes),
                        lineage_hash,
                        'EC-003',
                        self._version
                    ))

                self.conn.commit()

            except Exception as e:
                logger.error(f"Failed to save weighted plan for {ws.asset_id}: {e}")
                self.conn.rollback()

        # Save conflicts to registry
        for conflict in conflicts:
            self._save_conflict(conflict)

        logger.info(f"Saved {len(weighted_signals)} weighted signals, {len(conflicts)} conflicts")
        return str(plan_date)

    def _save_conflict(self, conflict: SignalConflict):
        """Save conflict to registry."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_signal_context.signal_conflict_registry (
                        conflict_id, asset_id, conflicting_signals, conflict_type,
                        resolution, resolved_direction, detected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (conflict_id) DO NOTHING
                """, (
                    conflict.conflict_id,
                    conflict.asset_id,
                    conflict.conflicting_signals,
                    conflict.conflict_type,
                    conflict.resolution,
                    conflict.resolved_direction
                ))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to save conflict: {e}")
            self.conn.rollback()

    def run_daily_weighting(self) -> Dict[str, Any]:
        """
        Execute daily signal weighting pipeline.

        Returns summary of weighted signals and conflicts.
        """
        logger.info("=" * 60)
        logger.info("IoS-013 SIGNAL WEIGHTING ENGINE - DAILY RUN")
        logger.info("=" * 60)

        # Step 1: Get active signals
        signals = self._get_active_signals()
        logger.info(f"Retrieved {len(signals)} active signals")

        if not signals:
            logger.warning("No active signals to process")
            return {'status': 'NO_SIGNALS', 'weighted_count': 0, 'conflict_count': 0}

        # Step 2: Compute weights for each signal
        weighted_signals = []
        for signal in signals:
            try:
                ws = self.compute_signal_weights(signal, signals)
                weighted_signals.append(ws)
                logger.info(f"Weighted {ws.asset_id}: {ws.raw_confidence:.2f} -> {ws.weighted_confidence:.2f}")
            except Exception as e:
                logger.error(f"Failed to weight signal {signal.get('signal_id')}: {e}")

        # Step 3: Detect conflicts
        conflicts = self.detect_conflicts(weighted_signals)
        logger.info(f"Detected {len(conflicts)} conflicts")

        # Step 4: Resolve conflicts
        resolved_signals = self.resolve_conflicts(weighted_signals, conflicts)
        logger.info(f"Resolved to {len(resolved_signals)} signals")

        # Step 5: Save to database
        plan_date = self.save_weighted_plan(resolved_signals, conflicts)

        summary = {
            'status': 'COMPLETE',
            'date': plan_date,
            'input_signals': len(signals),
            'weighted_count': len(resolved_signals),
            'conflict_count': len(conflicts),
            'suppressed_count': len(weighted_signals) - len(resolved_signals)
        }

        logger.info("=" * 60)
        logger.info(f"WEIGHTING COMPLETE: {summary}")
        logger.info("=" * 60)

        return summary

    def _get_active_signals(self) -> List[Dict]:
        """
        Get active signals from aggregated sources.

        Priority 1: fhq_research.signals (populated by ios013_signal_aggregator)
        Fallback 1: Direct Golden Needle read
        Fallback 2: Direct G1 validated signals read
        """
        signals = []

        # Primary: Try aggregated signals table
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    signal_id::text as signal_id,
                    listing_id as asset_id,
                    signal_type,
                    CASE
                        WHEN signal_strength > 0.6 THEN 'UP'
                        WHEN signal_strength < 0.4 THEN 'DOWN'
                        ELSE 'NEUTRAL'
                    END as direction,
                    signal_strength as confidence,
                    created_at + INTERVAL '7 days' as valid_until,
                    market_regime
                FROM fhq_research.signals
                WHERE status = 'ACTIVE'
                ORDER BY signal_strength DESC
                LIMIT 100
            """)
            signals = [dict(row) for row in cur.fetchall()]

        logger.info(f"Primary source (fhq_research.signals): {len(signals)} signals")

        # Fallback 1: Direct Golden Needle read if primary is empty
        if not signals:
            logger.warning("No signals in fhq_research.signals - using Golden Needle fallback")
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        needle_id::text as signal_id,
                        target_asset as asset_id,
                        COALESCE(hypothesis_category, 'GOLDEN_NEEDLE') as signal_type,
                        CASE
                            WHEN regime_technical = 'BULLISH' THEN 'UP'
                            WHEN regime_technical = 'BEARISH' THEN 'DOWN'
                            ELSE 'NEUTRAL'
                        END as direction,
                        eqs_score as confidence,
                        created_at + INTERVAL '7 days' as valid_until,
                        regime_technical as market_regime
                    FROM fhq_canonical.golden_needles
                    WHERE is_current = true
                    ORDER BY eqs_score DESC
                    LIMIT 100
                """)
                signals = [dict(row) for row in cur.fetchall()]
                logger.info(f"Golden Needle fallback: {len(signals)} signals")

        # Fallback 2: G1 validated signals if still empty
        if not signals:
            logger.warning("No Golden Needles - using G1 validated signals fallback")
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        signal_id::text as signal_id,
                        'BTC-USD' as asset_id,
                        category as signal_type,
                        'NEUTRAL' as direction,
                        confidence_score as confidence,
                        validated_at + INTERVAL '30 days' as valid_until,
                        'NEUTRAL' as market_regime
                    FROM fhq_alpha.g1_validated_signals
                    WHERE status NOT IN ('REJECTED', 'EXPIRED')
                    ORDER BY confidence_score DESC
                    LIMIT 100
                """)
                signals = [dict(row) for row in cur.fetchall()]
                logger.info(f"G1 validated fallback: {len(signals)} signals")

        return signals


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='IoS-013 Signal Weighting Engine (CEO-DIR-2026-120 P2.2)'
    )
    parser.add_argument('--run', action='store_true', help='Run daily weighting')
    parser.add_argument('--test', action='store_true', help='Test with sample data')

    args = parser.parse_args()

    engine = IoS013SignalWeightingEngine()
    engine.connect()

    try:
        if args.run:
            summary = engine.run_daily_weighting()
            print(json.dumps(summary, indent=2, default=str))
        elif args.test:
            # Test with sample signal
            sample = {
                'signal_id': 'test-001',
                'asset_id': 'AAPL',
                'signal_type': 'MOMENTUM_UP',
                'direction': 'UP',
                'confidence': 0.75
            }
            ws = engine.compute_signal_weights(sample, [sample])
            print(f"Sample weighting: {ws.explanation}")
            print(f"Composite weight: {ws.weight_factors.composite_weight:.3f}")
            print(f"Weighted confidence: {ws.weighted_confidence:.3f}")
        else:
            parser.print_help()
    finally:
        engine.close()


if __name__ == '__main__':
    main()
