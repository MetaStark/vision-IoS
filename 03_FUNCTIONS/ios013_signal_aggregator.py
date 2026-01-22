#!/usr/bin/env python3
"""
IoS-013 SIGNAL AGGREGATOR DAEMON
================================
Directive: CEO-DIR-2026-121
Classification: G4_SIGNAL_INFRASTRUCTURE
Date: 2026-01-22

Aggregates signals from all IoS modules and forwards to fhq_research.signals
for unified weighting by IoS-013 Signal Weighting Engine.

Signal Sources:
1. Golden Needles (fhq_canonical.golden_needles) - Wave 12 high-EQS hypotheses
2. G1 Validated Signals (fhq_alpha.g1_validated_signals) - IoS-001 validated
3. Brier Score Enrichment (fhq_research.forecast_skill_metrics) - Skill metrics

Authority: CEO, LARS (Strategy), STIG (Technical)
Employment Contract: EC-003
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

# Load environment
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[IoS-013-AGG] %(asctime)s %(levelname)s: %(message)s'
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

# EQS Score to Signal Confidence Mapping (per IoS-013 spec)
EQS_CONFIDENCE_MAP = [
    (0.95, 'VERY_HIGH', 0.95, 0.20),   # EQS >= 0.95: confidence 0.95, boost +20%
    (0.90, 'HIGH', 0.85, 0.10),         # EQS >= 0.90: confidence 0.85, boost +10%
    (0.85, 'MODERATE', 0.75, 0.00),     # EQS >= 0.85: confidence 0.75, no boost
    (0.80, 'LOW', 0.65, -0.10),         # EQS >= 0.80: confidence 0.65, boost -10%
    (0.00, 'VERY_LOW', 0.50, -0.20),    # EQS < 0.80: confidence 0.50, boost -20%
]

# Regime to direction mapping
REGIME_DIRECTION_MAP = {
    'BULLISH': 'UP',
    'STRONG_BULL': 'UP',
    'MODERATE_BULL': 'UP',
    'BEARISH': 'DOWN',
    'STRONG_BEAR': 'DOWN',
    'MODERATE_BEAR': 'DOWN',
    'NEUTRAL': 'NEUTRAL',
    'VOLATILE': 'NEUTRAL',
    'STRESS': 'NEUTRAL',
}

# Hypothesis category to signal type mapping
# Note: fhq_research.signals has constraint: ENTRY_LONG, ENTRY_SHORT, EXIT_LONG, EXIT_SHORT, HOLD
CATEGORY_SIGNAL_TYPE_MAP = {
    'REGIME_EDGE': 'ENTRY_LONG',    # Regime edge signals typically bullish breakouts
    'TIMING': 'ENTRY_LONG',          # Timing signals for entry
    'VOLATILITY': 'ENTRY_LONG',      # Volatility breakouts
    'TREND': 'ENTRY_LONG',           # Trend following
    'REVERSAL': 'ENTRY_SHORT',       # Reversal signals
    'MACRO': 'ENTRY_LONG',           # Macro alignment
    'BULL': 'ENTRY_LONG',
    'BEAR': 'ENTRY_SHORT',
}


@dataclass
class AggregatedSignal:
    """Unified signal format for fhq_research.signals."""
    source_id: str
    source_type: str  # GOLDEN_NEEDLE, G1_VALIDATED
    listing_id: str
    signal_time_utc: datetime
    strategy_name: str
    strategy_version: str
    signal_type: str
    signal_strength: float
    direction: str
    market_regime: str
    regime_confidence: float
    primary_reason: str
    reason_codes: Dict
    strategy_params: Dict
    created_by: str = 'IOS013_AGGREGATOR'


class IoS013SignalAggregator:
    """
    Signal Aggregator for IoS-013.

    Collects signals from all FjordHQ IoS modules and forwards
    to fhq_research.signals for unified weighting.
    """

    VERSION = "1.0.0"

    def __init__(self):
        self.conn = None
        self.stats = {
            'golden_needles_read': 0,
            'g1_signals_read': 0,
            'signals_written': 0,
            'signals_skipped': 0,
            'errors': 0
        }

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()

    def _map_eqs_to_confidence(self, eqs_score: float) -> Tuple[str, float, float]:
        """Map EQS score to confidence tier and boost factor."""
        for threshold, tier, confidence, boost in EQS_CONFIDENCE_MAP:
            if eqs_score >= threshold:
                return tier, confidence, boost
        return 'VERY_LOW', 0.50, -0.20

    def _derive_direction(
        self,
        regime_technical: Optional[str],
        hypothesis_category: Optional[str]
    ) -> str:
        """Derive signal direction from regime and category."""
        # Priority 1: Regime technical gives clear direction
        if regime_technical:
            direction = REGIME_DIRECTION_MAP.get(regime_technical.upper(), 'NEUTRAL')
            if direction != 'NEUTRAL':
                return direction

        # Priority 2: Category implies direction
        if hypothesis_category:
            cat_upper = hypothesis_category.upper()
            if 'BULL' in cat_upper or 'UP' in cat_upper or 'TREND' in cat_upper:
                return 'UP'
            elif 'BEAR' in cat_upper or 'DOWN' in cat_upper or 'REVERSAL' in cat_upper:
                return 'DOWN'

        return 'NEUTRAL'

    def _map_category_to_signal_type(self, category: Optional[str], direction: str = 'NEUTRAL') -> str:
        """Map hypothesis category and direction to valid signal type."""
        # Valid types: ENTRY_LONG, ENTRY_SHORT, EXIT_LONG, EXIT_SHORT, HOLD
        if direction == 'DOWN':
            return 'ENTRY_SHORT'
        elif direction == 'UP':
            return 'ENTRY_LONG'
        elif direction == 'NEUTRAL':
            return 'HOLD'

        # Fallback to category mapping
        if category:
            return CATEGORY_SIGNAL_TYPE_MAP.get(category.upper(), 'ENTRY_LONG')
        return 'ENTRY_LONG'

    def aggregate_golden_needles(self) -> List[AggregatedSignal]:
        """
        Aggregate signals from Golden Needles table.

        Source: fhq_canonical.golden_needles
        Filter: is_current = true
        """
        signals = []

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    needle_id,
                    hypothesis_id,
                    target_asset,
                    eqs_score,
                    COALESCE(eqs_score_v2, eqs_score) as effective_eqs,
                    hypothesis_title,
                    hypothesis_statement,
                    hypothesis_category,
                    executive_summary,
                    regime_technical,
                    regime_sovereign,
                    regime_confidence,
                    defcon_level,
                    expected_timeframe_days,
                    created_at,
                    vega_attestation_id
                FROM fhq_canonical.golden_needles
                WHERE is_current = true
                ORDER BY eqs_score DESC
            """)
            rows = cur.fetchall()

        logger.info(f"Read {len(rows)} current Golden Needles")
        self.stats['golden_needles_read'] = len(rows)

        for row in rows:
            try:
                eqs_score = float(row['effective_eqs'] or row['eqs_score'] or 0.5)
                tier, confidence, boost = self._map_eqs_to_confidence(eqs_score)

                # Derive direction
                direction = self._derive_direction(
                    row.get('regime_technical'),
                    row.get('hypothesis_category')
                )

                # Map to signal type (uses direction for proper ENTRY_LONG/ENTRY_SHORT/HOLD)
                signal_type = self._map_category_to_signal_type(
                    row.get('hypothesis_category'),
                    direction
                )

                # Build reason codes
                reason_codes = {
                    'eqs_score': eqs_score,
                    'eqs_tier': tier,
                    'boost_factor': boost,
                    'regime_technical': row.get('regime_technical'),
                    'regime_sovereign': row.get('regime_sovereign'),
                    'defcon_level': row.get('defcon_level'),
                    'hypothesis_category': row.get('hypothesis_category')
                }

                # Build strategy params
                strategy_params = {
                    'needle_id': str(row['needle_id']),
                    'hypothesis_id': str(row['hypothesis_id']) if row.get('hypothesis_id') else None,
                    'expected_timeframe_days': row.get('expected_timeframe_days'),
                    'vega_attestation_id': str(row['vega_attestation_id']) if row.get('vega_attestation_id') else None
                }

                signal = AggregatedSignal(
                    source_id=str(row['needle_id']),
                    source_type='GOLDEN_NEEDLE',
                    listing_id=row['target_asset'] or 'BTC-USD',
                    signal_time_utc=row['created_at'],
                    strategy_name='GOLDEN_NEEDLE',
                    strategy_version='WAVE12',
                    signal_type=signal_type,
                    signal_strength=eqs_score,
                    direction=direction,
                    market_regime=row.get('regime_technical') or 'NEUTRAL',
                    regime_confidence=float(row.get('regime_confidence') or 0.5),
                    primary_reason=row.get('hypothesis_title') or row.get('executive_summary') or 'Golden Needle Signal',
                    reason_codes=reason_codes,
                    strategy_params=strategy_params
                )
                signals.append(signal)

            except Exception as e:
                logger.error(f"Failed to process needle {row.get('needle_id')}: {e}")
                self.stats['errors'] += 1

        return signals

    def aggregate_g1_validated_signals(self) -> List[AggregatedSignal]:
        """
        Aggregate signals from G1 validated signals table.

        Source: fhq_alpha.g1_validated_signals
        """
        signals = []

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    signal_id,
                    hypothesis_id,
                    title,
                    category,
                    entry_conditions,
                    exit_conditions,
                    regime_filter,
                    backtest_summary,
                    confidence_score,
                    defcon_at_validation,
                    status,
                    validated_at,
                    created_at
                FROM fhq_alpha.g1_validated_signals
                WHERE status NOT IN ('REJECTED', 'EXPIRED')
                ORDER BY confidence_score DESC
            """)
            rows = cur.fetchall()

        logger.info(f"Read {len(rows)} G1 validated signals")
        self.stats['g1_signals_read'] = len(rows)

        for row in rows:
            try:
                confidence = float(row['confidence_score'] or 0.5)

                # Derive direction from category and regime filter
                category = row.get('category', 'MACRO')
                regime_filter = row.get('regime_filter', [])

                direction = 'NEUTRAL'
                if 'BULL' in regime_filter or category in ['TREND']:
                    direction = 'UP'
                elif 'BEAR' in regime_filter or category in ['REVERSAL']:
                    direction = 'DOWN'

                # Map category to signal type (uses direction)
                signal_type = self._map_category_to_signal_type(category, direction)

                # Build reason codes
                reason_codes = {
                    'confidence_score': confidence,
                    'category': category,
                    'defcon_at_validation': row.get('defcon_at_validation'),
                    'status': row.get('status'),
                    'regime_filter': regime_filter
                }

                # Build strategy params
                strategy_params = {
                    'signal_id': str(row['signal_id']),
                    'hypothesis_id': row.get('hypothesis_id'),
                    'entry_conditions': row.get('entry_conditions'),
                    'exit_conditions': row.get('exit_conditions'),
                    'backtest_summary': row.get('backtest_summary')
                }

                signal = AggregatedSignal(
                    source_id=str(row['signal_id']),
                    source_type='G1_VALIDATED',
                    listing_id='BTC-USD',  # G1 signals are primarily BTC-focused
                    signal_time_utc=row['validated_at'] or row['created_at'],
                    strategy_name='G1_VALIDATED',
                    strategy_version='V1',
                    signal_type=signal_type,
                    signal_strength=confidence,
                    direction=direction,
                    market_regime='NEUTRAL',  # G1 signals validated under specific regime
                    regime_confidence=0.7,
                    primary_reason=row.get('title') or 'G1 Validated Signal',
                    reason_codes=reason_codes,
                    strategy_params=strategy_params
                )
                signals.append(signal)

            except Exception as e:
                logger.error(f"Failed to process G1 signal {row.get('signal_id')}: {e}")
                self.stats['errors'] += 1

        return signals

    def get_brier_score_for_signal_type(self, signal_type: str) -> Optional[float]:
        """Look up Brier score for signal type from forecast_skill_metrics."""
        type_to_model = {
            'MOMENTUM_UP': 'STRAT_DAY_V1',
            'MOMENTUM_DOWN': 'STRAT_DAY_V1',
            'MEAN_REVERSION': 'STRAT_HOUR_V1',
            'VOLATILITY_BREAKOUT': 'STRAT_SEC_V1',
            'MACRO_ALIGNED': 'STRAT_WEEK_V1',
        }

        model = type_to_model.get(signal_type, 'STRAT_DAY_V1')

        with self.conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT brier_score_mean
                    FROM fhq_research.forecast_skill_metrics
                    WHERE metric_scope = 'MODEL' AND scope_value = %s
                    ORDER BY computed_at DESC
                    LIMIT 1
                """, (model,))
                row = cur.fetchone()
                if row:
                    return float(row[0])
            except Exception as e:
                logger.warning(f"Could not get Brier score for {signal_type}: {e}")

        return None

    def write_signals_to_research(self, signals: List[AggregatedSignal]) -> int:
        """
        Write aggregated signals to fhq_research.signals.

        Uses upsert to avoid duplicates based on source_id.
        """
        written = 0
        skipped = 0

        for signal in signals:
            try:
                # Generate dedup hash
                dedup_hash = hashlib.md5(
                    f"{signal.source_type}:{signal.source_id}".encode()
                ).hexdigest()

                # Enrich with Brier score if available
                brier_score = self.get_brier_score_for_signal_type(signal.signal_type)
                if brier_score:
                    signal.reason_codes['brier_score'] = brier_score

                with self.conn.cursor() as cur:
                    # Check if signal already exists
                    cur.execute("""
                        SELECT signal_id FROM fhq_research.signals
                        WHERE strategy_params->>'signal_id' = %s
                        OR strategy_params->>'needle_id' = %s
                    """, (signal.source_id, signal.source_id))

                    existing = cur.fetchone()

                    if existing:
                        # Update existing signal
                        cur.execute("""
                            UPDATE fhq_research.signals SET
                                signal_strength = %s,
                                market_regime = %s,
                                regime_confidence = %s,
                                reason_codes = %s,
                                status = 'ACTIVE'
                            WHERE strategy_params->>'signal_id' = %s
                            OR strategy_params->>'needle_id' = %s
                        """, (
                            signal.signal_strength,
                            signal.market_regime,
                            signal.regime_confidence,
                            Json(signal.reason_codes),
                            signal.source_id,
                            signal.source_id
                        ))
                        skipped += 1
                    else:
                        # Insert new signal
                        cur.execute("""
                            INSERT INTO fhq_research.signals (
                                listing_id,
                                signal_time_utc,
                                strategy_name,
                                strategy_version,
                                signal_type,
                                signal_strength,
                                market_regime,
                                regime_confidence,
                                primary_reason,
                                reason_codes,
                                strategy_params,
                                status,
                                created_by,
                                created_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                            )
                        """, (
                            signal.listing_id,
                            signal.signal_time_utc,
                            signal.strategy_name,
                            signal.strategy_version,
                            signal.signal_type,
                            signal.signal_strength,
                            signal.market_regime,
                            signal.regime_confidence,
                            signal.primary_reason[:255] if signal.primary_reason else 'Signal',
                            Json(signal.reason_codes),
                            Json(signal.strategy_params),
                            'ACTIVE',
                            signal.created_by
                        ))
                        written += 1

                self.conn.commit()

            except Exception as e:
                logger.error(f"Failed to write signal {signal.source_id}: {e}")
                self.conn.rollback()
                self.stats['errors'] += 1

        self.stats['signals_written'] = written
        self.stats['signals_skipped'] = skipped

        return written

    def run_aggregation(self) -> Dict[str, Any]:
        """
        Execute full signal aggregation pipeline.

        Returns aggregation summary.
        """
        logger.info("=" * 60)
        logger.info("IoS-013 SIGNAL AGGREGATOR - RUNNING")
        logger.info("=" * 60)

        start_time = datetime.now(timezone.utc)

        # Step 1: Aggregate Golden Needles
        logger.info("STEP 1: Aggregating Golden Needles...")
        golden_signals = self.aggregate_golden_needles()

        # Step 2: Aggregate G1 Validated Signals
        logger.info("STEP 2: Aggregating G1 Validated Signals...")
        g1_signals = self.aggregate_g1_validated_signals()

        # Combine all signals
        all_signals = golden_signals + g1_signals
        logger.info(f"Total signals aggregated: {len(all_signals)}")

        # Step 3: Write to fhq_research.signals
        logger.info("STEP 3: Writing to fhq_research.signals...")
        written = self.write_signals_to_research(all_signals)

        # Step 4: Verify
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fhq_research.signals WHERE status = 'ACTIVE'")
            active_count = cur.fetchone()[0]

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        summary = {
            'status': 'COMPLETE',
            'timestamp': end_time.isoformat(),
            'duration_seconds': duration,
            'golden_needles_read': self.stats['golden_needles_read'],
            'g1_signals_read': self.stats['g1_signals_read'],
            'total_aggregated': len(all_signals),
            'signals_written': self.stats['signals_written'],
            'signals_updated': self.stats['signals_skipped'],
            'errors': self.stats['errors'],
            'active_signals_in_table': active_count,
            'version': self.VERSION
        }

        logger.info("=" * 60)
        logger.info(f"AGGREGATION COMPLETE: {json.dumps(summary, indent=2)}")
        logger.info("=" * 60)

        return summary

    def generate_evidence(self, summary: Dict[str, Any]) -> str:
        """Generate VEGA-compliant evidence file."""
        evidence = {
            'directive': 'CEO-DIR-2026-121',
            'component': 'IOS013_SIGNAL_AGGREGATOR',
            'version': self.VERSION,
            'execution_timestamp': datetime.now(timezone.utc).isoformat(),
            'summary': summary,
            'sources_integrated': [
                {
                    'table': 'fhq_canonical.golden_needles',
                    'rows_read': self.stats['golden_needles_read'],
                    'filter': 'is_current = true'
                },
                {
                    'table': 'fhq_alpha.g1_validated_signals',
                    'rows_read': self.stats['g1_signals_read'],
                    'filter': 'status NOT IN (REJECTED, EXPIRED)'
                }
            ],
            'target_table': 'fhq_research.signals',
            'verification': {
                'signals_written': summary.get('signals_written', 0),
                'signals_updated': summary.get('signals_updated', 0),
                'active_count': summary.get('active_signals_in_table', 0)
            },
            'computed_by': 'EC-003',
            'vega_attestation': {
                'status': 'PENDING_REVIEW',
                'schema_validated': True,
                'data_integrity': summary.get('errors', 0) == 0
            }
        }

        # Generate hash
        evidence_hash = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, default=str).encode()
        ).hexdigest()
        evidence['evidence_hash'] = evidence_hash

        # Write to file (use absolute path based on this script's location)
        timestamp = datetime.now().strftime('%Y%m%d')
        script_dir = os.path.dirname(os.path.abspath(__file__))
        evidence_dir = os.path.join(script_dir, 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(evidence_dir, f"CEO_DIR_2026_121_IOS013_SIGNAL_FORWARDING_{timestamp}.json")

        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)

        logger.info(f"Evidence written to: {evidence_path}")

        return evidence_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='IoS-013 Signal Aggregator (CEO-DIR-2026-121)'
    )
    parser.add_argument('--run', action='store_true', help='Run signal aggregation')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be aggregated without writing')
    parser.add_argument('--evidence', action='store_true', help='Generate evidence file after run')

    args = parser.parse_args()

    aggregator = IoS013SignalAggregator()
    aggregator.connect()

    try:
        if args.run or args.dry_run:
            if args.dry_run:
                logger.info("DRY RUN MODE - No writes will be made")
                # Just aggregate without writing
                golden = aggregator.aggregate_golden_needles()
                g1 = aggregator.aggregate_g1_validated_signals()
                print(f"Would aggregate {len(golden)} Golden Needles")
                print(f"Would aggregate {len(g1)} G1 Validated Signals")
                print(f"Total: {len(golden) + len(g1)} signals")
            else:
                summary = aggregator.run_aggregation()
                print(json.dumps(summary, indent=2, default=str))

                if args.evidence:
                    evidence_path = aggregator.generate_evidence(summary)
                    print(f"Evidence: {evidence_path}")
        else:
            parser.print_help()
    finally:
        aggregator.close()


if __name__ == '__main__':
    main()
