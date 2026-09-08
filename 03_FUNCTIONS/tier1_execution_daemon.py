#!/usr/bin/env python3
"""
TIER-1 EXECUTION DAEMON
========================
CEO-DIR-2026-TIER1-EXECUTION-001

PURPOSE: Execute real Tier-1 hypothesis tests against actual market data.
         This daemon bridges hypothesis generation and evidence-based falsification.

AUTHORIZATION: CEO Directive - Immediate Activation of Tier-1 Execution Engine
DATE: 2026-01-26

SCOPE (EXPLICIT):
- Connect to real OHLCV data (fhq_data.price_series)
- Execute hypothesis tests against actual price movements
- Populate: sample_size, direction_accuracy, effect_size, p_value
- Ensure no hypothesis is killed with n=0

PROHIBITIONS (FREEZE INTEGRITY):
- NO changes to weights
- NO changes to thresholds
- NO changes to falsification criteria
- NO reinterpretation of p-value cutoffs
- NO new scoring logic
- NO bypass of Pre-Tier lineage

Author: STIG (EC-003)
Classification: G4_PRODUCTION_DAEMON
"""

import os
import sys
import json
import time
import signal
import logging
import hashlib
import math
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, List, Dict, Any
from decimal import Decimal
import uuid

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Daemon configuration
INTERVAL_MINUTES = 30  # Check every 30 minutes
DAEMON_NAME = 'tier1_execution_daemon'
MAX_TESTS_PER_CYCLE = 10  # Process up to 10 hypotheses per cycle
LOOKBACK_DAYS = 30  # Historical data for testing
MIN_SAMPLE_SIZE = 5  # Minimum samples required (less than 30 = INSUFFICIENT_DATA, not ANNIHILATED)

# FROZEN THRESHOLDS (from existing experiment_runner_daemon.py - DO NOT CHANGE)
DIRECTION_ACCURACY_STABLE = 0.5  # >= 0.5 = STABLE
DIRECTION_ACCURACY_WEAKENED = 0.4  # >= 0.4 = WEAKENED
# < 0.4 = FALSIFIED

# Setup logging
log_dir = 'C:/fhq-market-system/vision-ios/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[TIER1-EXEC] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/tier1_execution_daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    logger.info(f"Shutdown signal received ({signum})")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


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


def update_daemon_heartbeat(status: str = 'HEALTHY', metadata: dict = None):
    """Update daemon health heartbeat."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            meta_json = json.dumps(metadata or {})
            cur.execute("""
                INSERT INTO fhq_monitoring.daemon_health (daemon_name, status, last_heartbeat, metadata)
                VALUES (%s, %s, NOW(), %s::jsonb)
                ON CONFLICT (daemon_name) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_heartbeat = NOW(),
                    metadata = EXCLUDED.metadata
            """, (DAEMON_NAME, status, meta_json))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")


def get_untested_hypotheses() -> List[Dict[str, Any]]:
    """
    Get DRAFT hypotheses that have NOT been tested yet.
    Only hypotheses with valid asset_universe are eligible.
    """
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    h.canon_id,
                    h.hypothesis_code,
                    h.generator_id,
                    h.asset_universe,
                    h.expected_direction,
                    h.expected_timeframe_hours,
                    h.created_at,
                    h.pre_tier_score_at_birth,
                    h.current_confidence,
                    h.origin_error_id
                FROM fhq_learning.hypothesis_canon h
                WHERE h.status = 'DRAFT'
                  AND h.tier1_result IS NULL
                  AND h.asset_universe IS NOT NULL
                  AND array_length(h.asset_universe, 1) > 0
                  AND h.asset_universe[1] IS NOT NULL
                ORDER BY h.created_at ASC
                LIMIT %s
            """, (MAX_TESTS_PER_CYCLE,))
            results = cur.fetchall()
        conn.close()
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"Failed to get untested hypotheses: {e}")
        return []


def get_price_data(symbol: str, days: int = LOOKBACK_DAYS) -> List[Dict[str, Any]]:
    """
    Fetch OHLCV data from fhq_data.price_series.
    Returns list of {date, open, high, low, close, volume}
    """
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT date, open, high, low, close, volume
                FROM fhq_data.price_series
                WHERE listing_id = %s
                  AND date >= NOW() - INTERVAL '%s days'
                ORDER BY date ASC
            """, (symbol, days))
            results = cur.fetchall()
        conn.close()
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"Failed to get price data for {symbol}: {e}")
        return []


def calculate_direction_accuracy(prices: List[Dict], expected_direction: str) -> Dict[str, Any]:
    """
    Calculate direction accuracy by comparing expected vs actual price movements.

    For BULLISH: count days where close > previous close
    For BEARISH: count days where close < previous close
    For NEUTRAL: count days where |change| < 0.5%

    Returns metrics dict with sample_size, direction_accuracy, hits, misses
    """
    if len(prices) < 2:
        return {
            'sample_size': 0,
            'direction_accuracy': None,
            'hits': 0,
            'misses': 0,
            'error': 'INSUFFICIENT_DATA'
        }

    hits = 0
    misses = 0

    for i in range(1, len(prices)):
        prev_close = prices[i-1]['close']
        curr_close = prices[i]['close']

        if prev_close is None or curr_close is None or prev_close == 0:
            continue

        pct_change = (curr_close - prev_close) / prev_close

        if expected_direction == 'BULLISH':
            if pct_change > 0:
                hits += 1
            else:
                misses += 1
        elif expected_direction == 'BEARISH':
            if pct_change < 0:
                hits += 1
            else:
                misses += 1
        elif expected_direction == 'NEUTRAL':
            # Neutral = small moves (< 0.5%)
            if abs(pct_change) < 0.005:
                hits += 1
            else:
                misses += 1
        else:
            # Unknown direction - treat as neutral
            if abs(pct_change) < 0.005:
                hits += 1
            else:
                misses += 1

    sample_size = hits + misses
    direction_accuracy = hits / sample_size if sample_size > 0 else None

    return {
        'sample_size': sample_size,
        'direction_accuracy': direction_accuracy,
        'hits': hits,
        'misses': misses
    }


def calculate_effect_size(prices: List[Dict], expected_direction: str) -> Optional[float]:
    """
    Calculate Cohen's d effect size for the price movements.
    Measures how strong the directional signal is.
    """
    if len(prices) < 3:
        return None

    returns = []
    for i in range(1, len(prices)):
        prev_close = prices[i-1]['close']
        curr_close = prices[i]['close']
        if prev_close and curr_close and prev_close > 0:
            returns.append((curr_close - prev_close) / prev_close)

    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance) if variance > 0 else 0.0001

    # Cohen's d = mean / std_dev
    effect_size = abs(mean_return / std_dev)

    return round(effect_size, 4)


def calculate_p_value(sample_size: int, direction_accuracy: float) -> Optional[float]:
    """
    Calculate approximate p-value using binomial test.
    Tests if direction_accuracy is significantly different from 0.5 (random).

    Uses normal approximation for binomial: z = (p - 0.5) / sqrt(0.25/n)
    Then converts to p-value.
    """
    if sample_size < MIN_SAMPLE_SIZE or direction_accuracy is None:
        return None

    # Under null hypothesis, p = 0.5 (random guessing)
    null_p = 0.5
    observed_p = direction_accuracy

    # Standard error = sqrt(p*(1-p)/n)
    se = math.sqrt(null_p * (1 - null_p) / sample_size)

    if se == 0:
        return None

    # Z-score
    z = (observed_p - null_p) / se

    # Two-tailed p-value (approximate using standard normal)
    # P(|Z| > z) = 2 * (1 - Phi(|z|))
    # Using approximation: Phi(z) ≈ 1 - 0.5 * exp(-0.717*z - 0.416*z^2) for z > 0
    abs_z = abs(z)
    if abs_z > 6:
        p_value = 0.0001  # Very significant
    else:
        # Approximation of standard normal CDF
        phi = 1 / (1 + math.exp(-1.702 * abs_z))
        p_value = 2 * (1 - phi)

    return round(p_value, 6)


def determine_tier1_result(sample_size: int, direction_accuracy: float) -> str:
    """
    Determine Tier-1 result based on FROZEN thresholds.

    CRITICAL: These thresholds are from experiment_runner_daemon.py
    and MUST NOT be changed (CEO Prohibition).

    Database constraint allows: PENDING, ANNIHILATED, SURVIVED, WEAKENED
    Mapping:
    - STABLE (>=0.5) → SURVIVED
    - WEAKENED (>=0.4) → WEAKENED
    - FALSIFIED (<0.4) → ANNIHILATED
    - INSUFFICIENT_DATA → PENDING
    """
    if sample_size < MIN_SAMPLE_SIZE:
        return 'PENDING'  # Not enough data yet

    if direction_accuracy is None:
        return 'PENDING'

    # FROZEN THRESHOLDS (DO NOT CHANGE)
    if direction_accuracy >= DIRECTION_ACCURACY_STABLE:  # 0.5
        return 'SURVIVED'  # Was STABLE in experiment_runner
    elif direction_accuracy >= DIRECTION_ACCURACY_WEAKENED:  # 0.4
        return 'WEAKENED'
    else:
        return 'ANNIHILATED'  # Was FALSIFIED in experiment_runner


def execute_tier1_test(hypothesis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single Tier-1 test against real market data.

    Returns test result with all metrics populated.
    """
    logger.info(f"Testing: {hypothesis['hypothesis_code']} | assets={hypothesis['asset_universe']} | direction={hypothesis['expected_direction']}")

    result = {
        'hypothesis_code': hypothesis['hypothesis_code'],
        'canon_id': hypothesis['canon_id'],
        'tested_at': datetime.now(timezone.utc).isoformat(),
        'assets_tested': [],
        'aggregate_metrics': {},
        'tier1_result': 'INSUFFICIENT_DATA',
        'evidence': {}
    }

    # Aggregate metrics across all assets
    total_hits = 0
    total_misses = 0
    effect_sizes = []

    asset_universe = hypothesis['asset_universe']
    if not asset_universe:
        result['error'] = 'NO_ASSET_UNIVERSE'
        return result

    for symbol in asset_universe:
        if symbol is None:
            continue

        # Fetch price data
        prices = get_price_data(symbol, LOOKBACK_DAYS)

        if not prices:
            logger.warning(f"  No price data for {symbol}")
            result['assets_tested'].append({
                'symbol': symbol,
                'status': 'NO_DATA',
                'sample_size': 0
            })
            continue

        # Calculate direction accuracy
        metrics = calculate_direction_accuracy(prices, hypothesis['expected_direction'])

        # Calculate effect size
        effect_size = calculate_effect_size(prices, hypothesis['expected_direction'])

        asset_result = {
            'symbol': symbol,
            'status': 'TESTED',
            'sample_size': metrics['sample_size'],
            'direction_accuracy': metrics['direction_accuracy'],
            'hits': metrics['hits'],
            'misses': metrics['misses'],
            'effect_size': effect_size,
            'price_start': prices[0]['close'] if prices else None,
            'price_end': prices[-1]['close'] if prices else None,
            'date_start': str(prices[0]['date']) if prices else None,
            'date_end': str(prices[-1]['date']) if prices else None
        }

        result['assets_tested'].append(asset_result)

        total_hits += metrics['hits']
        total_misses += metrics['misses']
        if effect_size is not None:
            effect_sizes.append(effect_size)

    # Calculate aggregate metrics
    total_sample_size = total_hits + total_misses
    aggregate_direction_accuracy = total_hits / total_sample_size if total_sample_size > 0 else None
    aggregate_effect_size = sum(effect_sizes) / len(effect_sizes) if effect_sizes else None
    aggregate_p_value = calculate_p_value(total_sample_size, aggregate_direction_accuracy)

    result['aggregate_metrics'] = {
        'sample_size': total_sample_size,
        'direction_accuracy': round(aggregate_direction_accuracy, 4) if aggregate_direction_accuracy else None,
        'effect_size': round(aggregate_effect_size, 4) if aggregate_effect_size else None,
        'p_value': aggregate_p_value,
        'hits': total_hits,
        'misses': total_misses
    }

    # Determine Tier-1 result
    result['tier1_result'] = determine_tier1_result(total_sample_size, aggregate_direction_accuracy)

    # Build annihilation reason if ANNIHILATED
    if result['tier1_result'] == 'ANNIHILATED':
        result['annihilation_reason'] = (
            f"DIRECTION_ACCURACY: {aggregate_direction_accuracy:.2%} < {DIRECTION_ACCURACY_WEAKENED:.0%}; "
            f"SAMPLE_SIZE: n={total_sample_size}; "
            f"P_VALUE: p={aggregate_p_value}"
        )
    elif result['tier1_result'] == 'PENDING':
        result['annihilation_reason'] = f"PENDING: n={total_sample_size} < {MIN_SAMPLE_SIZE} (insufficient data)"

    logger.info(f"  Result: {result['tier1_result']} | n={total_sample_size} | accuracy={aggregate_direction_accuracy}")

    return result


def update_hypothesis_with_result(hypothesis: Dict, test_result: Dict) -> bool:
    """
    Update hypothesis_canon with Tier-1 test results.

    Populates: sample_size, p_value, effect_size, tier1_result, tier1_evaluated_at
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            metrics = test_result['aggregate_metrics']

            # CEO-DIR-2026-LEARNING-ARCHITECTURE-CORRECTION-003 (2026-02-10)
            # DEACTIVATED: OHLCV-based falsification
            # REASON: Direction accuracy from price_series does NOT reflect actual trade performance
            # NEW: Falsification now handled by trade_falsification_daemon based on shadow_trades
            #
            # ORIGINAL LOGIC (PRESERVED FOR AUDIT):
            # if test_result['tier1_result'] == 'ANNIHILATED':
            #     new_status = 'FALSIFIED'
            # elif test_result['tier1_result'] in ('SURVIVED', 'WEAKENED'):
            #     new_status = 'ACTIVE'
            #
            # NEW LOGIC: Only record OHLCV metrics, do NOT change status based on direction_accuracy
            new_status = hypothesis.get('status', 'DRAFT')
            # Status changes are now ONLY permitted by trade_falsification_daemon
            # tier1_result is recorded for historical reference but does not trigger falsification

            cur.execute("""
                UPDATE fhq_learning.hypothesis_canon
                SET
                    sample_size = %s,
                    p_value = %s,
                    effect_size = %s,
                    tier1_result = %s,
                    tier1_evaluated_at = NOW(),
                    annihilation_reason = %s,
                    status = %s,
                    last_updated_at = NOW(),
                    last_updated_by = 'tier1_execution_daemon'
                WHERE canon_id = %s
                RETURNING hypothesis_code
            """, (
                metrics.get('sample_size'),
                metrics.get('p_value'),
                metrics.get('effect_size'),
                test_result['tier1_result'],
                test_result.get('annihilation_reason'),
                new_status,
                hypothesis['canon_id']
            ))

            result = cur.fetchone()
            conn.commit()

            if result:
                logger.info(f"  Updated {result[0]}: status={new_status}, tier1={test_result['tier1_result']}")
                return True
            else:
                logger.warning(f"  No rows updated for {hypothesis['hypothesis_code']}")
                return False

    except Exception as e:
        logger.error(f"Failed to update hypothesis {hypothesis['hypothesis_code']}: {e}")
        return False
    finally:
        conn.close()


def write_evidence_file(cycle_results: Dict) -> str:
    """Write evidence file for this execution cycle."""
    evidence_dir = 'C:/fhq-market-system/vision-ios/03_FUNCTIONS/evidence'
    os.makedirs(evidence_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"TIER1_EXECUTION_{timestamp}.json"
    filepath = os.path.join(evidence_dir, filename)

    # Convert any non-serializable types
    def serialize(obj):
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return str(obj)

    with open(filepath, 'w') as f:
        json.dump(cycle_results, f, indent=2, default=serialize)

    return filepath


def run_execution_cycle() -> Dict[str, Any]:
    """Run one Tier-1 execution cycle."""
    cycle_start = datetime.now(timezone.utc)
    cycle_id = str(uuid.uuid4())[:8]

    result = {
        'cycle_id': cycle_id,
        'timestamp': cycle_start.isoformat(),
        'hypotheses_tested': 0,
        'results': {
            'SURVIVED': 0,
            'WEAKENED': 0,
            'ANNIHILATED': 0,
            'PENDING': 0
        },
        'tests': []
    }

    # Get untested hypotheses
    hypotheses = get_untested_hypotheses()
    logger.info(f"Found {len(hypotheses)} untested hypotheses")

    if not hypotheses:
        result['message'] = 'No untested hypotheses found'
        return result

    # Execute tests
    for hyp in hypotheses:
        test_result = execute_tier1_test(hyp)

        # Update hypothesis in database
        updated = update_hypothesis_with_result(hyp, test_result)

        if updated:
            result['hypotheses_tested'] += 1
            tier1_outcome = test_result['tier1_result']
            result['results'][tier1_outcome] = result['results'].get(tier1_outcome, 0) + 1
            result['tests'].append({
                'hypothesis_code': hyp['hypothesis_code'],
                'tier1_result': tier1_outcome,
                'sample_size': test_result['aggregate_metrics'].get('sample_size'),
                'direction_accuracy': test_result['aggregate_metrics'].get('direction_accuracy'),
                'p_value': test_result['aggregate_metrics'].get('p_value')
            })

    # Write evidence
    evidence_path = write_evidence_file(result)
    result['evidence_file'] = evidence_path

    logger.info(
        f"Cycle {cycle_id} complete: tested={result['hypotheses_tested']} | "
        f"SURVIVED={result['results']['SURVIVED']} | "
        f"WEAKENED={result['results']['WEAKENED']} | "
        f"ANNIHILATED={result['results']['ANNIHILATED']} | "
        f"PENDING={result['results']['PENDING']}"
    )

    return result


def main():
    """Main daemon loop."""
    logger.info("=" * 60)
    logger.info("TIER-1 EXECUTION DAEMON STARTING")
    logger.info("CEO-DIR-2026-TIER1-EXECUTION-001")
    logger.info(f"Interval: {INTERVAL_MINUTES} minutes")
    logger.info(f"Max tests per cycle: {MAX_TESTS_PER_CYCLE}")
    logger.info(f"Lookback: {LOOKBACK_DAYS} days")
    logger.info("FROZEN THRESHOLDS:")
    logger.info(f"  STABLE >= {DIRECTION_ACCURACY_STABLE}")
    logger.info(f"  WEAKENED >= {DIRECTION_ACCURACY_WEAKENED}")
    logger.info("=" * 60)

    cycle_count = 0

    while not shutdown_requested:
        cycle_count += 1
        logger.info(f"--- Cycle {cycle_count} starting ---")

        # DEFCON gate check
        can_proceed, msg, level = defcon_gate_check()
        if not can_proceed:
            logger.warning(f"DEFCON BLOCKED: {msg}")
            update_daemon_heartbeat('BLOCKED_DEFCON', {'defcon': level})
            time.sleep(60)
            continue

        # Run execution cycle
        try:
            result = run_execution_cycle()

            # Update heartbeat with cycle results
            update_daemon_heartbeat('HEALTHY', {
                'cycle': cycle_count,
                'last_result': {
                    'tested': result['hypotheses_tested'],
                    'results': result['results']
                },
                'defcon': level
            })

        except Exception as e:
            logger.error(f"Cycle {cycle_count} failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            update_daemon_heartbeat('ERROR', {'error': str(e)})

        # Wait for next cycle
        logger.info(f"Sleeping {INTERVAL_MINUTES} minutes until next cycle...")
        for _ in range(INTERVAL_MINUTES * 60):
            if shutdown_requested:
                break
            time.sleep(1)

    logger.info("Tier-1 Execution Daemon shutting down gracefully")
    update_daemon_heartbeat('STOPPED', {'shutdown': 'graceful'})


if __name__ == '__main__':
    main()
