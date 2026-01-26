#!/usr/bin/env python3
"""
FINN-T WORLD-MODEL SCHEDULER
=============================
CEO-DIR-2026-FINN-T-SCHEDULER-001
CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001 (Amendment)

PURPOSE: Continuous hypothesis generation from G3 Golden Features.
         Theory-driven learning with N-tier mechanism chains.

CONSTRAINTS:
- Input source: fhq_macro.golden_features (CANONICAL status)
- Min causal depth: 2
- Output: hypothesis_canon with generator_id='FINN-T'
- Rotation across LIQUIDITY, CREDIT, FACTOR, VOLATILITY clusters

G1.5 VARIANCE DIRECTIVE (2026-01-26):
- 20% of output targets causal_depth >= 4 (HIGH_CAUSAL_PRESSURE)
- Tagged with generation_regime='HIGH_CAUSAL_PRESSURE', causal_depth_target=4+
- G1.5 freeze on evaluative logic PRESERVED

Authority: ADR-020 (ACI), ADR-016 (DEFCON), Migration 353
Classification: G4_PRODUCTION_SCHEDULER
Executor: STIG (EC-003)
"""

import os
import sys
import json
import time
import signal
import logging
import hashlib
import random
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Tuple, Optional, List, Dict, Any

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Scheduler configuration
INTERVAL_MINUTES = 60  # Generate every hour (less frequent than crypto)
MAX_CYCLES_PER_DAY = 24
DAEMON_NAME = 'finn_t_scheduler'
GENERATOR_ID = 'FINN-T'
MIN_CAUSAL_DEPTH = 2

# G1.5 VARIANCE DIRECTIVE (CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001)
HIGH_CAUSAL_PRESSURE_RATIO = 0.20  # 20% of output targets depth >= 4
HIGH_CAUSAL_PRESSURE_MIN_DEPTH = 4
GENERATION_REGIME_STANDARD = 'STANDARD'
GENERATION_REGIME_HIGH_PRESSURE = 'HIGH_CAUSAL_PRESSURE'

# Setup logging
log_dir = 'C:/fhq-market-system/vision-ios/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[FINN-T] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/finn_t_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Mechanism chain templates for G3 clusters (STANDARD depth 2-3)
MECHANISM_CHAINS = {
    'LIQUIDITY': {
        'causal_chain': [
            'Fed policy changes liquidity conditions',
            'Liquidity flows into/out of risk assets',
            'Asset prices adjust to new liquidity equilibrium'
        ],
        'behavioral_basis': 'Institutional portfolio rebalancing follows liquidity signals',
        'regime_validity': ['RISK_ON', 'RISK_OFF', 'EXPANSION'],
        'assets': ['SPY', 'QQQ', 'TLT']
    },
    'CREDIT': {
        'causal_chain': [
            'Credit conditions tighten or loosen',
            'Corporate borrowing costs change',
            'Investment and earnings expectations adjust',
            'Equity valuations re-rate'
        ],
        'behavioral_basis': 'Credit cycles lead equity cycles by 3-6 months',
        'regime_validity': ['CONTRACTION', 'EXPANSION', 'TRANSITION'],
        'assets': ['SPY', 'XLF', 'HYG']
    },
    'FACTOR': {
        'causal_chain': [
            'Factor exposure concentrations build',
            'Regime shift triggers factor rotation',
            'Crowded positions unwind creating momentum'
        ],
        'behavioral_basis': 'Factor crowding creates mean-reversion pressure',
        'regime_validity': ['TRANSITION', 'RISK_OFF'],
        'assets': ['SPY', 'IWM', 'QQQ']
    },
    'VOLATILITY': {
        'causal_chain': [
            'Volatility regime shifts detected',
            'Options market reprices risk',
            'Delta hedging flows impact spot prices'
        ],
        'behavioral_basis': 'Volatility clustering and mean reversion',
        'regime_validity': ['HIGH_VOL', 'LOW_VOL', 'TRANSITION'],
        'assets': ['SPY', 'VXX', 'UVXY']
    }
}

# HIGH_CAUSAL_PRESSURE mechanism chains (depth 4+) - G1.5 VARIANCE DIRECTIVE
HIGH_PRESSURE_MECHANISM_CHAINS = {
    'LIQUIDITY': {
        'causal_chain': [
            'Fed policy changes liquidity conditions',
            'Interbank lending rates adjust',
            'Liquidity flows into/out of risk assets',
            'Market makers widen spreads in response',
            'Asset prices adjust to new liquidity equilibrium'
        ],
        'behavioral_basis': 'Multi-tier liquidity transmission mechanism',
        'regime_validity': ['RISK_ON', 'RISK_OFF', 'EXPANSION', 'TRANSITION'],
        'assets': ['SPY', 'QQQ', 'TLT', 'LQD']
    },
    'CREDIT': {
        'causal_chain': [
            'Credit conditions tighten or loosen',
            'Corporate borrowing costs change',
            'Capital expenditure plans adjust',
            'Earnings guidance revisions follow',
            'Equity valuations re-rate'
        ],
        'behavioral_basis': 'Full credit-to-equity transmission chain',
        'regime_validity': ['CONTRACTION', 'EXPANSION', 'TRANSITION'],
        'assets': ['SPY', 'XLF', 'HYG', 'LQD']
    },
    'FACTOR': {
        'causal_chain': [
            'Factor exposure concentrations build',
            'Risk parity funds begin rebalancing',
            'Regime shift triggers factor rotation',
            'Crowded positions unwind creating momentum',
            'Cross-asset correlations spike'
        ],
        'behavioral_basis': 'Factor crowding cascade with cross-asset contagion',
        'regime_validity': ['TRANSITION', 'RISK_OFF', 'HIGH_VOL'],
        'assets': ['SPY', 'IWM', 'QQQ', 'EFA']
    },
    'VOLATILITY': {
        'causal_chain': [
            'Volatility regime shifts detected',
            'Options market reprices risk',
            'Vol-targeting funds reduce exposure',
            'Delta hedging flows impact spot prices',
            'Realized vol validates implied shift'
        ],
        'behavioral_basis': 'Vol regime feedback loop with hedging amplification',
        'regime_validity': ['HIGH_VOL', 'LOW_VOL', 'TRANSITION'],
        'assets': ['SPY', 'VXX', 'UVXY', 'VIXY']
    }
}


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def defcon_gate_check() -> Tuple[bool, str, str]:
    """DEFCON Hard Gate Check."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT defcon_level FROM fhq_governance.defcon_state
                WHERE is_current = true
                ORDER BY triggered_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            level = row[0] if row else 'GREEN'
        conn.close()
    except Exception as e:
        logger.critical(f"DEFCON check failed - BLOCKING: {e}")
        return (False, f"DEFCON CHECK FAILURE: {e}", "UNKNOWN")

    if level in ('RED', 'BLACK'):
        return (False, f"DEFCON {level}: ALL PROCESSES MUST TERMINATE", level)
    if level == 'ORANGE':
        return (False, f"DEFCON ORANGE: NEW CYCLES BLOCKED", level)
    if level == 'YELLOW':
        return (True, f"DEFCON YELLOW: Proceed with caution", level)
    return (True, f"DEFCON {level}: Full operation permitted", level)


def update_daemon_heartbeat(status: str = 'HEALTHY'):
    """Update daemon health heartbeat."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (daemon_name) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_heartbeat = NOW(),
                    metadata = EXCLUDED.metadata
            """, (DAEMON_NAME, status, json.dumps({
                'directive': 'CEO-DIR-2026-FINN-T-SCHEDULER-001',
                'generator_id': GENERATOR_ID,
                'input_source': 'g3_golden_features',
                'min_causal_depth': MIN_CAUSAL_DEPTH
            })))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")


def get_g3_golden_features() -> List[Dict]:
    """Get G3 Golden Features for hypothesis generation."""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT feature_id, cluster, hypothesis, expected_direction, status
                FROM fhq_macro.golden_features
                WHERE status = 'CANONICAL'
                ORDER BY cluster, feature_id
            """)
            features = cur.fetchall()
        conn.close()
        return [dict(f) for f in features]
    except Exception as e:
        logger.error(f"Failed to get G3 features: {e}")
        return []


def get_rotation_cluster() -> str:
    """Get next cluster to process based on rotation."""
    clusters = ['LIQUIDITY', 'CREDIT', 'FACTOR', 'VOLATILITY']
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Find which cluster was used least recently
            cur.execute("""
                SELECT
                    c.cluster,
                    COALESCE(MAX(h.created_at), '1970-01-01'::timestamptz) as last_used
                FROM (VALUES ('LIQUIDITY'), ('CREDIT'), ('FACTOR'), ('VOLATILITY')) AS c(cluster)
                LEFT JOIN fhq_learning.hypothesis_canon h
                    ON h.generator_id = 'FINN-T'
                    AND h.causal_mechanism LIKE '%' || c.cluster || '%'
                GROUP BY c.cluster
                ORDER BY last_used ASC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                return row[0]
        conn.close()
    except Exception as e:
        logger.warning(f"Rotation check failed, using LIQUIDITY: {e}")
    return clusters[0]


def map_direction(direction: str) -> str:
    """Map feature direction to valid hypothesis_canon values."""
    mapping = {
        'POSITIVE': 'BULLISH',
        'NEGATIVE': 'BEARISH',
        'NEUTRAL': 'NEUTRAL',
        'BULLISH': 'BULLISH',
        'BEARISH': 'BEARISH',
    }
    return mapping.get(direction.upper() if direction else 'NEUTRAL', 'NEUTRAL')


def should_apply_high_causal_pressure() -> bool:
    """
    Determine if this hypothesis should use HIGH_CAUSAL_PRESSURE regime.
    CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001: 20% of output targets depth >= 4
    """
    return random.random() < HIGH_CAUSAL_PRESSURE_RATIO


def generate_hypothesis(feature: Dict, cluster: str) -> Optional[str]:
    """Generate a hypothesis from a G3 Golden Feature."""
    try:
        conn = get_db_connection()

        # G1.5 VARIANCE DIRECTIVE: 20% chance of HIGH_CAUSAL_PRESSURE
        use_high_pressure = should_apply_high_causal_pressure()

        if use_high_pressure:
            chain_template = HIGH_PRESSURE_MECHANISM_CHAINS.get(cluster, HIGH_PRESSURE_MECHANISM_CHAINS['LIQUIDITY'])
            generation_regime = GENERATION_REGIME_HIGH_PRESSURE
            causal_depth_target = HIGH_CAUSAL_PRESSURE_MIN_DEPTH
            logger.info(f"HIGH_CAUSAL_PRESSURE activated for {cluster} (depth={len(chain_template['causal_chain'])})")
        else:
            chain_template = MECHANISM_CHAINS.get(cluster, MECHANISM_CHAINS['LIQUIDITY'])
            generation_regime = GENERATION_REGIME_STANDARD
            causal_depth_target = None

        # Generate hypothesis code
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        hypothesis_code = f"FINNT-{cluster[:3]}-{timestamp}"

        # Build semantic hash for duplicate detection
        semantic_content = f"{feature['feature_id']}:{feature.get('hypothesis', '')}:{cluster}:{datetime.now(timezone.utc).date()}"
        semantic_hash = hashlib.md5(semantic_content.encode()).hexdigest()

        # Check for recent duplicate (same day)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT hypothesis_code FROM fhq_learning.hypothesis_canon
                WHERE generator_id = %s
                AND semantic_hash = %s
                AND created_at > NOW() - INTERVAL '24 hours'
            """, (GENERATOR_ID, semantic_hash))

            if cur.fetchone():
                logger.debug(f"Recent duplicate for {feature['feature_id']}, skipping")
                conn.close()
                return None

        # Build mechanism graph
        mechanism_graph = {
            'nodes': [
                {'tier': i+1, 'mechanism': step, 'evidence_required': True}
                for i, step in enumerate(chain_template['causal_chain'])
            ],
            'root_driver': feature['feature_id'],
            'terminal_outcome': f"Asset price movement in {feature.get('expected_direction', 'expected')} direction",
            'depth': len(chain_template['causal_chain'])
        }

        causal_mechanism = ' -> '.join(chain_template['causal_chain'])
        mapped_direction = map_direction(feature.get('expected_direction', 'NEUTRAL'))

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_learning.hypothesis_canon (
                    hypothesis_code,
                    origin_type,
                    origin_rationale,
                    economic_rationale,
                    causal_mechanism,
                    counterfactual_scenario,
                    behavioral_basis,
                    asset_universe,
                    expected_direction,
                    expected_magnitude,
                    expected_timeframe_hours,
                    regime_validity,
                    regime_conditional_confidence,
                    falsification_criteria,
                    max_falsifications,
                    initial_confidence,
                    current_confidence,
                    status,
                    generator_id,
                    mechanism_graph,
                    causal_graph_depth,
                    semantic_hash,
                    created_at,
                    created_by,
                    asset_class,
                    generation_regime,
                    causal_depth_target
                ) VALUES (
                    %s, 'ECONOMIC_THEORY', %s, %s, %s, %s, %s, %s, %s, 'MEDIUM',
                    72, %s, %s, %s, 3, 0.60, 0.60, 'DRAFT', %s, %s, %s, %s, NOW(), %s, 'EQUITY',
                    %s, %s
                )
                RETURNING hypothesis_code
            """, (
                hypothesis_code,
                f"Generated from G3 Golden Feature: {feature['feature_id']} ({cluster})",
                feature.get('hypothesis', f'{cluster} signal detected'),
                causal_mechanism,
                f"If {feature['feature_id']} signal fails, expect no directional move within 72h",
                chain_template['behavioral_basis'],
                chain_template['assets'],
                mapped_direction,
                chain_template['regime_validity'],
                json.dumps({regime: 0.65 for regime in chain_template['regime_validity']}),
                json.dumps({
                    'direction_violation': f"Price moves opposite to {feature.get('expected_direction', 'expected')}",
                    'magnitude_threshold': '2 standard deviations',
                    'time_window_hours': 72
                }),
                GENERATOR_ID,
                json.dumps(mechanism_graph),
                mechanism_graph['depth'],
                semantic_hash,
                DAEMON_NAME,
                generation_regime,
                causal_depth_target
            ))

            result = cur.fetchone()
            conn.commit()

            if result:
                regime_tag = f" [{generation_regime}]" if generation_regime != GENERATION_REGIME_STANDARD else ""
                logger.info(f"Generated {hypothesis_code} from {feature['feature_id']} (depth={mechanism_graph['depth']}){regime_tag}")
                return result[0]

        conn.close()
    except Exception as e:
        logger.error(f"Failed to generate hypothesis: {e}")
    return None


def run_learning_cycle(cycle_num: int) -> Dict[str, Any]:
    """Run a single FINN-T learning cycle."""
    start_time = datetime.now(timezone.utc)
    results = {
        'cycle': cycle_num,
        'timestamp': start_time.isoformat(),
        'generator_id': GENERATOR_ID,
        'hypotheses_generated': 0,
        'cluster_used': None,
        'features_available': 0
    }

    try:
        # Get G3 Golden Features
        features = get_g3_golden_features()
        results['features_available'] = len(features)
        logger.info(f"Found {len(features)} G3 Golden Features")

        if not features:
            logger.warning("No G3 Golden Features found")
            results['status'] = 'NO_DATA'
            return results

        # Get rotation cluster
        cluster = get_rotation_cluster()
        results['cluster_used'] = cluster
        logger.info(f"Rotation selected cluster: {cluster}")

        # Filter features for this cluster
        cluster_features = [f for f in features if f.get('cluster') == cluster]

        if not cluster_features:
            # Fallback to any available feature
            cluster_features = features[:1]
            cluster = cluster_features[0].get('cluster', 'LIQUIDITY')
            results['cluster_used'] = cluster

        # Generate hypothesis from first available feature in cluster
        for feature in cluster_features[:1]:  # Limit to 1 per cycle
            hypothesis_code = generate_hypothesis(feature, cluster)
            if hypothesis_code:
                results['hypotheses_generated'] += 1

        results['duration_sec'] = (datetime.now(timezone.utc) - start_time).total_seconds()
        results['status'] = 'SUCCESS'

    except Exception as e:
        logger.error(f"Learning cycle error: {e}")
        results['status'] = 'ERROR'
        results['error'] = str(e)

    return results


def log_cycle_results(results: Dict[str, Any]):
    """Log cycle results."""
    logger.info("=" * 60)
    logger.info(f"FINN-T LEARNING CYCLE {results['cycle']} COMPLETE")
    logger.info(f"  Generator: {results['generator_id']}")
    logger.info(f"  Cluster: {results.get('cluster_used', 'N/A')}")
    logger.info(f"  Features Available: {results['features_available']}")
    logger.info(f"  Hypotheses Generated: {results['hypotheses_generated']}")
    logger.info(f"  Duration: {results.get('duration_sec', 0):.1f}s")
    logger.info(f"  Status: {results['status']}")
    logger.info("=" * 60)


class FINNTScheduler:
    """FINN-T World-Model Scheduler."""

    def __init__(self):
        self.shutdown_requested = False
        self.cycles_today = 0
        self.last_reset_date = None
        self.total_hypotheses = 0

    def setup_signal_handlers(self):
        def handler(signum, frame):
            logger.info(f"Shutdown signal received ({signum})")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def reset_daily_counter(self):
        today = datetime.now(timezone.utc).date()
        if self.last_reset_date != today:
            self.cycles_today = 0
            self.last_reset_date = today
            logger.info(f"Daily counter reset for {today}")

    def run(self):
        logger.info("=" * 70)
        logger.info("FINN-T WORLD-MODEL SCHEDULER ACTIVATED")
        logger.info("CEO-DIR-2026-FINN-T-SCHEDULER-001")
        logger.info("CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001 (ACTIVE)")
        logger.info(f"  Interval: {INTERVAL_MINUTES} minutes")
        logger.info(f"  Generator: {GENERATOR_ID}")
        logger.info(f"  Input: G3 Golden Features")
        logger.info(f"  Min Causal Depth: {MIN_CAUSAL_DEPTH}")
        logger.info(f"  HIGH_CAUSAL_PRESSURE: {HIGH_CAUSAL_PRESSURE_RATIO*100:.0f}% @ depth {HIGH_CAUSAL_PRESSURE_MIN_DEPTH}+")
        logger.info("=" * 70)

        self.setup_signal_handlers()
        update_daemon_heartbeat('HEALTHY')

        while not self.shutdown_requested:
            try:
                self.reset_daily_counter()

                # DEFCON Hard Gate
                can_proceed, reason, defcon_level = defcon_gate_check()

                if defcon_level in ('RED', 'BLACK'):
                    logger.critical(f"DEFCON {defcon_level} - IMMEDIATE TERMINATION")
                    update_daemon_heartbeat('TERMINATED')
                    self.shutdown_requested = True
                    break

                if not can_proceed:
                    logger.warning(reason)
                    update_daemon_heartbeat('BLOCKED')
                    time.sleep(60)
                    continue

                if self.cycles_today >= MAX_CYCLES_PER_DAY:
                    logger.warning(f"Daily cycle limit reached ({MAX_CYCLES_PER_DAY})")
                    time.sleep(60)
                    continue

                update_daemon_heartbeat('HEALTHY')

                logger.info(f"Starting FINN-T cycle (#{self.cycles_today + 1} today, DEFCON: {defcon_level})...")
                results = run_learning_cycle(self.cycles_today + 1)
                log_cycle_results(results)

                self.cycles_today += 1
                self.total_hypotheses += results.get('hypotheses_generated', 0)

                update_daemon_heartbeat('HEALTHY')

                if not self.shutdown_requested:
                    logger.info(f"Next cycle in {INTERVAL_MINUTES} minutes...")
                    for i in range(INTERVAL_MINUTES * 60):
                        if self.shutdown_requested:
                            break
                        time.sleep(1)
                        if i > 0 and i % 300 == 0:
                            update_daemon_heartbeat('HEALTHY')

            except Exception as e:
                logger.error(f"Cycle error: {e}")
                import traceback
                traceback.print_exc()
                update_daemon_heartbeat('ERROR')
                time.sleep(60)

        update_daemon_heartbeat('STOPPED')
        logger.info(f"FINN-T Scheduler shutdown. Total hypotheses: {self.total_hypotheses}")


if __name__ == '__main__':
    print("[FINN-T] World-Model Scheduler starting...")
    print("[FINN-T] CEO-DIR-2026-FINN-T-SCHEDULER-001")
    print("[FINN-T] Input: G3 Golden Features | Min Depth: 2")

    scheduler = FINNTScheduler()
    scheduler.run()
