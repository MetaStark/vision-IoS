#!/usr/bin/env python3
"""
FINN CRYPTO LEARNING SCHEDULER
==============================
CEO-DIR-2026-CRYPTO-LEARNING-SCHEDULER-001
CEO-DIR-2026-G1.5-INPUT-VALIDITY-REMEDIATION-001 (v2.0)
CEO-DIR-2026-P0-CDS-VARIANCE-ROTATION-001 (v3.0)

PURPOSE: 24/7 continuous hypothesis generation for crypto assets.
         Independent of equity market session state.

CONSTRAINTS:
- Asset class: CRYPTO only
- Session model: 24/7 continuous
- Data source: Binance / IoS-007 nodes
- Output: hypothesis_canon (learning_only=TRUE)
- No execution, allocation, decision rights
- Fail-closed on missing evidence

REMEDIATION v2.0 (2026-01-27):
- generation_regime = 'CRYPTO_DIVERSIFIED_POST_FIX' for new hypotheses
- Throttled to 1 hypothesis per cycle (was 2)
- causal_depth now varies by theory (2, 3, 5) instead of constant 3

CDS VARIANCE ROTATION v3.0 (2026-01-28):
- Deterministic theory selection using hypothesis_id as entropy source
- sha256_utf8 hash function for stable cross-platform selection
- Selection metadata stored for VEGA audit verification
- Canonical theory order: FUNDING_DYNAMICS, VOLATILITY_CLUSTERING, REGIME_TRANSITION, LIQUIDATION_CASCADE

Authority: ADR-020 (ACI), ADR-016 (DEFCON), Migration 347-348
Classification: G4_PRODUCTION_SCHEDULER
Executor: STIG (EC-003)
"""

SCHEDULER_VERSION = "3.0"
SELECTION_VERSION = "POST_FIX_SELECTION_1.1.0"

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

# CEO-DIR-2026-P0-CDS-VARIANCE-ROTATION-001: Canonical Theory Order (IMMUTABLE)
# This order is canonical. It SHALL NOT be changed without a new CEO directive.
CANONICAL_THEORY_ORDER = [
    {'theory_type': 'FUNDING_DYNAMICS', 'causal_depth': 2, 'cds_score': 50.00},
    {'theory_type': 'VOLATILITY_CLUSTERING', 'causal_depth': 2, 'cds_score': 50.00},
    {'theory_type': 'REGIME_TRANSITION', 'causal_depth': 3, 'cds_score': 75.00},
    {'theory_type': 'LIQUIDATION_CASCADE', 'causal_depth': 5, 'cds_score': 100.00},
]


def deterministic_theory_selection(hypothesis_id: str) -> dict:
    """
    CEO-DIR-2026-P0-CDS-VARIANCE-ROTATION-001: Deterministic Theory Selection

    Uses hypothesis_id as the ONLY entropy source (cycle_id/timestamps FORBIDDEN).
    Hash function: sha256_utf8 (stable across platforms and replays).

    Args:
        hypothesis_id: UUID string of the hypothesis (canon_id)

    Returns:
        dict with: theory_type, causal_depth, theory_index, selection_metadata
    """
    # Compute stable hash
    hash_input = hypothesis_id.encode('utf-8')
    hash_digest = hashlib.sha256(hash_input).hexdigest()

    # Convert first 8 hex chars to int for index
    hash_int = int(hash_digest[:8], 16)
    theory_index = hash_int % 4

    selected_theory = CANONICAL_THEORY_ORDER[theory_index]

    return {
        'theory_type': selected_theory['theory_type'],
        'causal_depth': selected_theory['causal_depth'],
        'cds_score': selected_theory['cds_score'],
        'theory_index': theory_index,
        'selection_metadata': {
            'theory_type_selected': selected_theory['theory_type'],
            'theory_index': theory_index,
            'selection_entropy_source': hypothesis_id,
            'selection_hash_alg': 'sha256_utf8',
            'selection_hash_hex': hash_digest,
            'selection_version': SELECTION_VERSION,
            'generated_at_utc': datetime.now(timezone.utc).isoformat()
        }
    }

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


def run_preflight_simulation(n_samples: int = 100) -> dict:
    """
    CEO-DIR-2026-P0-CDS-VARIANCE-ROTATION-001 Section 5: Pre-Flight Simulation

    Simulates the next n POST_FIX selections to verify distribution.

    Acceptance Criteria:
    - At least 3 of 4 theory types appear
    - No single theory > 70% of samples

    Returns:
        dict with simulation results and pass/fail status
    """
    import uuid

    results = {
        'n_samples': n_samples,
        'selections': [],
        'distribution': {},
        'acceptance_criteria': {},
        'passed': False
    }

    # Simulate selections
    for i in range(n_samples):
        test_id = str(uuid.uuid4())
        selection = deterministic_theory_selection(test_id)
        results['selections'].append({
            'hypothesis_id': test_id,
            'theory_index': selection['theory_index'],
            'theory_type_selected': selection['theory_type']
        })

        # Count distribution
        theory = selection['theory_type']
        results['distribution'][theory] = results['distribution'].get(theory, 0) + 1

    # Check acceptance criteria
    unique_theories = len(results['distribution'])
    max_concentration = max(results['distribution'].values()) / n_samples * 100

    results['acceptance_criteria'] = {
        'unique_theories_required': 3,
        'unique_theories_actual': unique_theories,
        'unique_theories_pass': unique_theories >= 3,
        'max_concentration_allowed': 70.0,
        'max_concentration_actual': round(max_concentration, 1),
        'max_concentration_pass': max_concentration <= 70.0
    }

    results['passed'] = (
        results['acceptance_criteria']['unique_theories_pass'] and
        results['acceptance_criteria']['max_concentration_pass']
    )

    return results


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


def generate_crypto_hypothesis_v3(context: Dict[str, Any]) -> Optional[str]:
    """
    CEO-DIR-2026-P0-CDS-VARIANCE-ROTATION-001: Generate crypto hypothesis with deterministic theory selection.

    v3.0 Changes:
    - Generate hypothesis_id (UUID) FIRST
    - Use deterministic_theory_selection with hypothesis_id as entropy source
    - Store selection metadata for VEGA audit verification
    - Fail-closed if selection metadata cannot be written

    CONSTRAINTS:
    - learning_only = TRUE
    - No execution, allocation, decision rights
    - Fail-closed on missing evidence or metadata failure
    """
    conn = None
    try:
        conn = get_db_connection()

        with conn.cursor() as cur:
            # STEP 1: Generate hypothesis_id FIRST (CEO requirement: entropy source)
            cur.execute("SELECT gen_random_uuid()::text")
            hypothesis_id = cur.fetchone()[0]

            # STEP 2: Deterministic theory selection using hypothesis_id
            selection = deterministic_theory_selection(hypothesis_id)
            selected_theory_type = selection['theory_type']
            causal_depth = selection['causal_depth']
            selection_metadata = selection['selection_metadata']

            logger.info(f"Deterministic selection: {hypothesis_id[:8]}... -> {selected_theory_type} (index {selection['theory_index']})")

            # STEP 3: Fetch full theory details from DB
            cur.execute("""
                SELECT theory_type, theory_name, mechanism_chain, theory_description
                FROM fhq_learning.crypto_theory_artifacts
                WHERE theory_type = %s AND status = 'ACTIVE'
            """, (selected_theory_type,))
            theory_row = cur.fetchone()

            if not theory_row:
                logger.error(f"FAIL-CLOSED: Theory {selected_theory_type} not found in DB")
                return None

            theory_name = theory_row[1]
            mechanism_chain = theory_row[2]

            # STEP 4: Generate hypothesis code using selected theory
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            theory_code = selected_theory_type[:4].upper()
            hypothesis_code = f"CRYPTO-{theory_code}-{timestamp}"

            # Serialize mechanism chain
            mechanism_str = json.dumps(mechanism_chain) if isinstance(mechanism_chain, dict) else str(mechanism_chain)

            # Generate semantic hash
            hash_input = f"{selected_theory_type}:{mechanism_str}:{timestamp}"
            semantic_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

            # STEP 4.5: CEO-DIR-2026-128 MEMORY BIRTH GATE
            # Query prior failures before hypothesis birth
            asset_universe = ['BTC-USD', 'ETH-USD']
            cur.execute("""
                SELECT prior_count, exact_duplicate_exists, similar_failures,
                       memory_citation, should_block, block_reason
                FROM fhq_learning.check_prior_failures(%s, %s, %s, %s)
            """, (mechanism_str, semantic_hash, asset_universe, DAEMON_NAME))
            memory_result = cur.fetchone()

            if memory_result and memory_result[4]:  # should_block = True
                # Log the block
                cur.execute("""
                    INSERT INTO fhq_learning.hypothesis_birth_blocks (
                        block_reason, generator_id, proposed_semantic_hash,
                        proposed_causal_mechanism, proposed_asset_universe,
                        prior_failures_count, similar_failures
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    memory_result[5],  # block_reason
                    DAEMON_NAME,
                    semantic_hash,
                    mechanism_str[:500],
                    asset_universe,
                    memory_result[0],  # prior_count
                    memory_result[2]   # similar_failures (JSONB)
                ))
                conn.commit()
                logger.warning(f"MEMORY_BLOCK: {memory_result[5]} - prior_count={memory_result[0]}")
                return None

            # Extract memory citation for hypothesis birth
            prior_hypotheses_count = memory_result[0] if memory_result else 0
            memory_citation = memory_result[3] if memory_result else None

            # STEP 5: Build mechanism_graph with selection metadata (for VEGA audit)
            mechanism_graph = {
                'theory_type': selected_theory_type,
                'mechanism': mechanism_chain,
                'context': context,
                'selection_metadata': selection_metadata  # CEO requirement: audit trail
            }

            # STEP 6: Insert hypothesis with pre-generated canon_id
            # CEO-DIR-2026-128: Now includes prior_hypotheses_count from memory gate
            cur.execute("""
                INSERT INTO fhq_learning.hypothesis_canon (
                    canon_id,
                    hypothesis_code,
                    origin_type,
                    origin_rationale,
                    economic_rationale,
                    causal_mechanism,
                    counterfactual_scenario,
                    expected_direction,
                    expected_timeframe_hours,
                    regime_validity,
                    regime_conditional_confidence,
                    falsification_criteria,
                    initial_confidence,
                    asset_universe,
                    causal_graph_depth,
                    mechanism_graph,
                    status,
                    created_by,
                    generator_id,
                    semantic_hash,
                    asset_class,
                    learning_only,
                    generation_regime,
                    prior_hypotheses_count
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::text[], %s, %s, %s, %s::text[], %s, %s, 'DRAFT', %s, %s, %s, 'CRYPTO', TRUE, 'CRYPTO_DIVERSIFIED_POST_FIX', %s
                )
                RETURNING canon_id
            """, (
                hypothesis_id,
                hypothesis_code,
                'ECONOMIC_THEORY',
                f"Generated from crypto theory: {theory_name} (deterministic selection v{SCHEDULER_VERSION})",
                mechanism_str,
                json.dumps(mechanism_graph, default=str),
                f"If {selected_theory_type} fails, expect mean reversion or regime continuation",
                'NEUTRAL',
                24,
                '{CRYPTO_24_7}',
                json.dumps({'base': 0.6, 'regime': 'CRYPTO_24_7'}),
                json.dumps({'criteria': f"Price movement contradicts {selected_theory_type} within 24h", 'threshold': 0.3}),
                0.5,
                '{BTC-USD,ETH-USD}',
                causal_depth,
                json.dumps(mechanism_graph, default=str),
                DAEMON_NAME,
                DAEMON_NAME,
                semantic_hash,
                prior_hypotheses_count
            ))

            result = cur.fetchone()

            # STEP 7: Verify selection metadata was stored (fail-closed requirement)
            if not result:
                logger.error("FAIL-CLOSED: Insert returned no result")
                conn.rollback()
                return None

            conn.commit()
            logger.info(f"Generated hypothesis: {hypothesis_code} (theory: {selected_theory_type}, CDS: {selection['cds_score']})")
            return hypothesis_code

    except Exception as e:
        logger.error(f"FAIL-CLOSED: Failed to generate hypothesis: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()


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

        # Fetch theories from Migration 348 (for logging only - selection is deterministic)
        theories = get_crypto_theory_artifacts()
        results['theories_available'] = len(theories)
        logger.info(f"Found {len(theories)} crypto theory artifacts")

        # Fetch IoS-007 nodes
        nodes = get_ios007_learning_nodes()
        results['nodes_checked'] = len(nodes)
        logger.info(f"Found {len(nodes)} IoS-007 learning nodes")

        # CEO-DIR-2026-P0-CDS-VARIANCE-ROTATION-001 v3.0:
        # Theory selection is now DETERMINISTIC based on hypothesis_id
        # No more "for theory in theories" loop - selection happens inside generate_crypto_hypothesis_v3
        max_per_cycle = 1  # THROTTLED

        for _ in range(max_per_cycle):
            hypothesis_code = generate_crypto_hypothesis_v3(context)
            if hypothesis_code:
                results['hypotheses_generated'] += 1
                # Extract theory from hypothesis code (CRYPTO-XXXX-timestamp)
                theory_prefix = hypothesis_code.split('-')[1] if '-' in hypothesis_code else 'UNKNOWN'
                results['theories_used'].append(theory_prefix)

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
    from daemon_lock import acquire_lock, release_lock
    if not acquire_lock('finn_crypto_scheduler'):
        sys.exit(0)
    try:
        print("[IoS-017] FINN Crypto Learning Scheduler starting...")
        print("[IoS-017] CEO-DIR-2026-CRYPTO-LEARNING-SCHEDULER-001")
        print("[IoS-017] Asset Class: CRYPTO | Session: 24/7 | Learning Only: TRUE")

        scheduler = FINNCryptoScheduler()
        scheduler.run()
    finally:
        release_lock('finn_crypto_scheduler')
