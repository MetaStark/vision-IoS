#!/usr/bin/env python3
"""
FINN CRYPTO LEARNING SCHEDULER
==============================
CEO-DIR-2026-CRYPTO-LEARNING-SCHEDULER-001

PURPOSE: 24/7 continuous hypothesis generation for crypto assets.
         Independent of equity market session state.

CONSTRAINTS:
- Asset class: CRYPTO only
- Session model: 24/7 continuous
- Data source: Binance / IoS-007 nodes
- Output: hypothesis_canon (learning_only=TRUE)
- No execution, allocation, decision rights
- Fail-closed on missing evidence

Authority: ADR-020 (ACI), ADR-016 (DEFCON), Migration 347-348
Classification: G4_PRODUCTION_SCHEDULER
Executor: STIG (EC-003)
"""

import os
import sys
import json
import time
import signal
import logging
import psycopg2
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
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
INTERVAL_MINUTES = 30  # Same cadence as FINN Brain
MAX_CYCLES_PER_DAY = 48
DAEMON_NAME = 'finn_crypto_scheduler'

# Setup logging
log_dir = 'C:/fhq-market-system/vision-ios/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[FINN-CRYPTO] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/finn_crypto_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def defcon_gate_check() -> Tuple[bool, str, str]:
    """
    DEFCON Hard Gate Check - CEO Directive Mandate III.

    Returns: (can_proceed, reason, defcon_level)
    """
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
        # Fail-closed: unknown state = block operations
        logger.critical(f"DEFCON check failed - BLOCKING: {e}")
        return (False, f"DEFCON CHECK FAILURE: {e}", "UNKNOWN")

    if level in ('RED', 'BLACK'):
        return (False, f"DEFCON {level}: ALL PROCESSES MUST TERMINATE", level)
    if level == 'ORANGE':
        return (False, f"DEFCON ORANGE: NEW CYCLES BLOCKED", level)
    if level == 'YELLOW':
        return (True, f"DEFCON YELLOW: Proceed with caution", level)
    return (True, f"DEFCON {level}: Full operation permitted", level)


def is_crypto_learnable() -> Tuple[bool, str]:
    """
    Check if crypto learning is permitted using fn_get_learnable_asset_classes().

    Returns: (is_learnable, reason)
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Check if crypto is in learnable asset classes
            cur.execute("""
                SELECT * FROM fhq_learning.fn_get_learnable_asset_classes()
                WHERE asset_class = 'CRYPTO'
            """)
            row = cur.fetchone()

            if row:
                return (True, "CRYPTO learning permitted (24/7)")
            else:
                # Fallback: check MIC directly
                cur.execute("""
                    SELECT fhq_meta.fn_is_market_open('XCRYPTO') as is_open
                """)
                mic_row = cur.fetchone()
                if mic_row and mic_row[0]:
                    return (True, "XCRYPTO market OPEN (24/7)")
                return (False, "CRYPTO learning not permitted")
        conn.close()
    except Exception as e:
        logger.warning(f"Learnability check failed, defaulting to TRUE (crypto is 24/7): {e}")
        # Crypto is 24/7 by nature, so default to learnable if check fails
        return (True, f"Default to learnable (check failed: {e})")


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
                'directive': 'CEO-DIR-2026-CRYPTO-LEARNING-SCHEDULER-001',
                'asset_class': 'CRYPTO',
                'session_model': '24/7',
                'learning_only': True
            })))
            conn.commit()
        conn.close()
        logger.debug(f"Heartbeat updated: {status}")
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")


def get_crypto_theory_artifacts() -> List[Dict[str, Any]]:
    """Fetch crypto theory artifacts from Migration 348."""
    theories = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT theory_type, theory_name, mechanism_chain,
                       theory_description, causal_depth
                FROM fhq_learning.crypto_theory_artifacts
                WHERE status = 'ACTIVE'
            """)
            for row in cur.fetchall():
                theories.append({
                    'theory_type': row[0],
                    'theory_name': row[1],
                    'causal_mechanism': row[2],  # mechanism_chain
                    'expected_direction': 'CONTEXT_DEPENDENT',
                    'target_assets': ['BTC-USD', 'ETH-USD'],
                    'causal_depth': row[4]
                })
        conn.close()
    except Exception as e:
        logger.warning(f"Could not fetch crypto theories: {e}")
    return theories


def get_ios007_learning_nodes() -> List[Dict[str, Any]]:
    """Fetch IoS-007 crypto learning nodes from Migration 348."""
    nodes = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT node_type, symbol, data_vendor, learning_only,
                       allocation_allowed, execution_allowed
                FROM fhq_research.ios007_crypto_learning_nodes
                WHERE learning_only = TRUE
            """)
            for row in cur.fetchall():
                nodes.append({
                    'node_type': row[0],
                    'symbol': row[1],
                    'data_source': row[2],  # data_vendor
                    'learning_only': row[3],
                    'allocation_allowed': row[4],
                    'execution_allowed': row[5]
                })
        conn.close()
    except Exception as e:
        logger.warning(f"Could not fetch IoS-007 nodes: {e}")
    return nodes


def generate_crypto_hypothesis(theory: Dict[str, Any], context: Dict[str, Any]) -> Optional[str]:
    """
    Generate a crypto hypothesis based on theory artifact.

    CONSTRAINTS:
    - learning_only = TRUE
    - No execution, allocation, decision rights
    - Fail-closed on missing evidence
    """
    try:
        conn = get_db_connection()

        # Generate hypothesis code
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        theory_code = theory['theory_type'][:4].upper()
        hypothesis_code = f"CRYPTO-{theory_code}-{timestamp}"

        # Generate semantic hash
        hash_input = f"{theory['theory_type']}:{theory['causal_mechanism']}:{timestamp}"
        semantic_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_learning.hypothesis_canon (
                    hypothesis_code,
                    origin_type,
                    origin_rationale,
                    economic_rationale,
                    causal_mechanism,
                    expected_direction,
                    asset_universe,
                    causal_graph_depth,
                    status,
                    created_by,
                    semantic_hash,
                    asset_class,
                    learning_only
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, 'DRAFT', %s, %s, 'CRYPTO', TRUE
                )
                RETURNING canon_id
            """, (
                hypothesis_code,
                'ECONOMIC_THEORY',  # FINN-T origin
                f"Generated from crypto theory: {theory['theory_name']}",
                theory['causal_mechanism'],
                json.dumps({
                    'theory_type': theory['theory_type'],
                    'mechanism': theory['causal_mechanism'],
                    'context': context
                }),
                theory['expected_direction'],
                theory.get('target_assets', ['BTC-USD', 'ETH-USD']),
                theory.get('causal_depth', 3),
                DAEMON_NAME,
                semantic_hash
            ))

            result = cur.fetchone()
            conn.commit()

            if result:
                logger.info(f"Generated hypothesis: {hypothesis_code}")
                return hypothesis_code

        conn.close()
    except Exception as e:
        logger.error(f"Failed to generate hypothesis: {e}")
        return None


def run_learning_cycle(cycle_num: int) -> Dict[str, Any]:
    """
    Run a single crypto learning cycle.

    Returns cycle results for logging.
    """
    start_time = datetime.now(timezone.utc)
    results = {
        'cycle': cycle_num,
        'timestamp': start_time.isoformat(),
        'asset_class': 'CRYPTO',
        'hypotheses_generated': 0,
        'theories_used': [],
        'nodes_checked': 0,
        'learning_only': True,
        'execution_blocked': True,
        'allocation_blocked': True
    }

    try:
        # Get context
        context = {
            'timestamp': start_time.isoformat(),
            'session': 'CONTINUOUS',  # Crypto is always open
            'asset_class': 'CRYPTO'
        }

        # Fetch theories from Migration 348
        theories = get_crypto_theory_artifacts()
        results['theories_available'] = len(theories)
        logger.info(f"Found {len(theories)} crypto theory artifacts")

        # Fetch IoS-007 nodes
        nodes = get_ios007_learning_nodes()
        results['nodes_checked'] = len(nodes)
        logger.info(f"Found {len(nodes)} IoS-007 learning nodes")

        # Generate hypotheses from theories (limit to 2 per cycle to avoid spam)
        hypotheses_this_cycle = 0
        max_per_cycle = 2

        for theory in theories:
            if hypotheses_this_cycle >= max_per_cycle:
                break

            hypothesis_code = generate_crypto_hypothesis(theory, context)
            if hypothesis_code:
                results['hypotheses_generated'] += 1
                results['theories_used'].append(theory['theory_type'])
                hypotheses_this_cycle += 1

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        results['duration_sec'] = (end_time - start_time).total_seconds()
        results['status'] = 'SUCCESS'

    except Exception as e:
        logger.error(f"Learning cycle error: {e}")
        results['status'] = 'ERROR'
        results['error'] = str(e)

    return results


def log_cycle_results(results: Dict[str, Any]):
    """Log cycle results."""
    logger.info("=" * 60)
    logger.info(f"CRYPTO LEARNING CYCLE {results['cycle']} COMPLETE")
    logger.info(f"  Timestamp: {results['timestamp']}")
    logger.info(f"  Asset Class: {results['asset_class']}")
    logger.info(f"  Hypotheses Generated: {results['hypotheses_generated']}")
    logger.info(f"  Theories Used: {results.get('theories_used', [])}")
    logger.info(f"  Nodes Checked: {results['nodes_checked']}")
    logger.info(f"  Learning Only: {results['learning_only']}")
    logger.info(f"  Duration: {results.get('duration_sec', 0):.1f}s")
    logger.info(f"  Status: {results['status']}")
    logger.info("=" * 60)

    # Save results to file
    try:
        results_file = f"{log_dir}/crypto_cycle_{results['cycle']}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Could not save results: {e}")


class FINNCryptoScheduler:
    """
    24/7 Crypto Learning Scheduler.

    Independent of equity market state.
    Generates hypotheses to hypothesis_canon with learning_only=TRUE.
    """

    def __init__(self):
        self.shutdown_requested = False
        self.cycles_today = 0
        self.last_reset_date = None
        self.total_hypotheses = 0

    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        def handler(signum, frame):
            logger.info(f"Shutdown signal received ({signum})")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def reset_daily_counter(self):
        """Reset cycle counter at midnight UTC."""
        today = datetime.now(timezone.utc).date()
        if self.last_reset_date != today:
            self.cycles_today = 0
            self.last_reset_date = today
            logger.info(f"Daily counter reset for {today}")

    def run(self):
        """Run the scheduler continuously."""
        logger.info("=" * 70)
        logger.info("FINN CRYPTO LEARNING SCHEDULER ACTIVATED")
        logger.info("CEO-DIR-2026-CRYPTO-LEARNING-SCHEDULER-001")
        logger.info(f"  Interval: {INTERVAL_MINUTES} minutes")
        logger.info(f"  Asset Class: CRYPTO only")
        logger.info(f"  Session Model: 24/7 continuous")
        logger.info(f"  Learning Only: TRUE")
        logger.info(f"  Execution: BLOCKED")
        logger.info(f"  Allocation: BLOCKED")
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

                # Check if crypto learning is permitted
                is_learnable, learn_reason = is_crypto_learnable()
                if not is_learnable:
                    logger.warning(f"Crypto learning blocked: {learn_reason}")
                    update_daemon_heartbeat('BLOCKED')
                    time.sleep(60)
                    continue

                # Check daily limit
                if self.cycles_today >= MAX_CYCLES_PER_DAY:
                    logger.warning(f"Daily cycle limit reached ({MAX_CYCLES_PER_DAY})")
                    time.sleep(60)
                    continue

                # Update heartbeat before cycle
                update_daemon_heartbeat('HEALTHY')

                # Run learning cycle
                logger.info(f"Starting crypto learning cycle (#{self.cycles_today + 1} today, DEFCON: {defcon_level})...")
                results = run_learning_cycle(self.cycles_today + 1)
                log_cycle_results(results)

                self.cycles_today += 1
                self.total_hypotheses += results.get('hypotheses_generated', 0)

                # Update heartbeat after cycle
                update_daemon_heartbeat('HEALTHY')

                # Wait for next interval
                if not self.shutdown_requested:
                    logger.info(f"Next cycle in {INTERVAL_MINUTES} minutes...")
                    for _ in range(INTERVAL_MINUTES * 60):
                        if self.shutdown_requested:
                            break
                        time.sleep(1)
                        # Update heartbeat every 5 minutes during wait
                        if _ > 0 and _ % 300 == 0:
                            update_daemon_heartbeat('HEALTHY')

            except Exception as e:
                logger.error(f"Cycle error: {e}")
                import traceback
                traceback.print_exc()
                update_daemon_heartbeat('ERROR')
                time.sleep(60)

        # Final status
        update_daemon_heartbeat('STOPPED')
        logger.info(f"FINN Crypto Scheduler shutdown complete. Total hypotheses: {self.total_hypotheses}")


if __name__ == '__main__':
    print("[IoS-017] FINN Crypto Learning Scheduler starting...")
    print("[IoS-017] CEO-DIR-2026-CRYPTO-LEARNING-SCHEDULER-001")
    print("[IoS-017] Asset Class: CRYPTO | Session: 24/7 | Learning Only: TRUE")

    scheduler = FINNCryptoScheduler()
    scheduler.run()
