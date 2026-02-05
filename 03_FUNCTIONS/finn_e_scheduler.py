#!/usr/bin/env python3
"""
FINN-E ERROR REPAIR SCHEDULER
==============================
CEO-DIR-2026-FINN-E-SCHEDULER-001

PURPOSE: Convert HIGH priority forecast errors into falsification sweep hypotheses.
         Error-driven learning for rapid sample size growth.

CONSTRAINTS:
- Input source: fhq_learning.error_classification_taxonomy (learning_priority='HIGH')
- Only convert errors where hypothesis_generated = FALSE
- Output: hypothesis_canon with generator_id='FINN-E'
- Cannot be sole generator (enforced via monitoring)

Authority: ADR-020 (ACI), ADR-016 (DEFCON), Migration 353
Classification: G4_PRODUCTION_SCHEDULER
Executor: STIG (EC-003)

CHANGE LOG:
- v2.0 (2026-01-27): CEO-DIR-2026-P0-INPUT-REPAIR - Added empty symbol gate
"""

FINN_E_VERSION = "2.0"

import os
import sys
import json
import time
import signal
import logging
import hashlib
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
INTERVAL_MINUTES = 30  # Check for new errors every 30 min
MAX_CYCLES_PER_DAY = 48
MAX_HYPOTHESES_PER_CYCLE = 3  # Limit to avoid flooding
DAEMON_NAME = 'finn_e_scheduler'
GENERATOR_ID = 'FINN-E'

# Setup logging
log_dir = 'C:/fhq-market-system/vision-ios/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[FINN-E] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/finn_e_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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
                'directive': 'CEO-DIR-2026-FINN-E-SCHEDULER-001',
                'generator_id': GENERATOR_ID,
                'input_source': 'error_classification_taxonomy',
                'max_per_cycle': MAX_HYPOTHESES_PER_CYCLE
            })))
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")


def get_unconverted_high_errors() -> List[Dict]:
    """Get HIGH priority errors that haven't been converted to hypotheses."""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    error_id,
                    error_code,
                    error_type,
                    source_hypothesis_id,
                    predicted_direction,
                    actual_direction,
                    direction_error,
                    predicted_magnitude,
                    actual_magnitude,
                    magnitude_error_pct,
                    regime_at_prediction,
                    regime_at_outcome,
                    regime_mismatch,
                    causal_attribution,
                    confidence_at_prediction,
                    symbol,
                    asset_class,
                    error_detected_at
                FROM fhq_learning.error_classification_taxonomy
                WHERE learning_priority = 'HIGH'
                AND hypothesis_generated = FALSE
                ORDER BY error_detected_at DESC
                LIMIT %s
            """, (MAX_HYPOTHESES_PER_CYCLE * 2,))  # Fetch extra in case some fail
            errors = cur.fetchall()
        conn.close()
        return [dict(e) for e in errors]
    except Exception as e:
        logger.error(f"Failed to get errors: {e}")
        return []


def map_error_to_hypothesis_direction(error: Dict) -> str:
    """Determine hypothesis direction based on error analysis."""
    # If there was a direction error, the hypothesis should test the opposite
    if error.get('direction_error'):
        actual = error.get('actual_direction', '').upper()
        if actual in ['UP', 'BULLISH', 'POSITIVE']:
            return 'BULLISH'
        elif actual in ['DOWN', 'BEARISH', 'NEGATIVE']:
            return 'BEARISH'
    return 'NEUTRAL'


def build_error_hypothesis_rationale(error: Dict) -> Dict[str, str]:
    """Build hypothesis rationale from error analysis."""
    error_type = error.get('error_type', 'UNKNOWN')
    symbol = error.get('symbol', 'UNKNOWN')

    rationale = {
        'origin_rationale': f"Generated from forecast error {error.get('error_code', 'UNKNOWN')} on {symbol}",
        'economic_rationale': '',
        'causal_mechanism': '',
        'counterfactual': '',
        'behavioral_basis': ''
    }

    if error.get('direction_error'):
        rationale['economic_rationale'] = (
            f"Direction mismatch detected: predicted {error.get('predicted_direction', 'X')}, "
            f"actual {error.get('actual_direction', 'Y')}. "
            f"Hypothesis: market structure for {symbol} differs from model assumptions."
        )
        rationale['causal_mechanism'] = (
            f"Error signal detected -> Model recalibration required -> "
            f"Test opposite direction hypothesis to validate correction"
        )
        rationale['counterfactual'] = (
            f"If original prediction was correct, no direction error would occur. "
            f"Actual outcome suggests systematic bias in model."
        )
        rationale['behavioral_basis'] = "Error-driven learning: systematic errors indicate model blind spots"

    elif error.get('magnitude_error_pct') and abs(float(error.get('magnitude_error_pct', 0))) > 50:
        rationale['economic_rationale'] = (
            f"Magnitude error of {error.get('magnitude_error_pct', 0):.1f}% detected. "
            f"Model underestimated/overestimated move magnitude."
        )
        rationale['causal_mechanism'] = (
            f"Volatility regime different than expected -> "
            f"Magnitude calibration required -> Test revised magnitude hypothesis"
        )
        rationale['counterfactual'] = (
            f"If volatility regime was correctly identified, magnitude would be closer to prediction."
        )
        rationale['behavioral_basis'] = "Volatility clustering and regime-dependent magnitude expectations"

    elif error.get('regime_mismatch'):
        rationale['economic_rationale'] = (
            f"Regime mismatch: prediction made in {error.get('regime_at_prediction', 'X')} regime, "
            f"outcome in {error.get('regime_at_outcome', 'Y')} regime."
        )
        rationale['causal_mechanism'] = (
            f"Regime transition occurred -> Model assumptions invalidated -> "
            f"Test regime-conditional hypothesis"
        )
        rationale['counterfactual'] = (
            f"If regime remained stable, original prediction may have been valid."
        )
        rationale['behavioral_basis'] = "Regime-conditional behavior requires regime-aware predictions"

    else:
        rationale['economic_rationale'] = f"Error detected in {symbol} forecast, cause requires investigation"
        rationale['causal_mechanism'] = "Error signal -> Investigation required -> Generate test hypothesis"
        rationale['counterfactual'] = "Unknown error mechanism requires empirical testing"
        rationale['behavioral_basis'] = "Systematic error investigation via hypothesis testing"

    return rationale


def generate_hypothesis_from_error(error: Dict) -> Optional[str]:
    """Generate a hypothesis from a forecast error."""
    try:
        conn = get_db_connection()

        # Generate hypothesis code
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        error_code = error.get('error_code', 'UNK')[:8]
        hypothesis_code = f"FINNE-{error_code}-{timestamp}"

        # Build semantic hash
        semantic_content = f"{error.get('error_id')}:{error.get('error_type')}:{error.get('symbol')}"
        semantic_hash = hashlib.md5(semantic_content.encode()).hexdigest()

        # Build rationale
        rationale = build_error_hypothesis_rationale(error)
        direction = map_error_to_hypothesis_direction(error)

        # Determine asset universe (CEO-DIR-2026-P0-INPUT-REPAIR: handle empty symbols)
        symbol = error.get('symbol') or None
        asset_class = error.get('asset_class') or 'US_EQUITY'

        # HARD GATE: Reject errors without valid symbol
        if not symbol or symbol.strip() == '':
            logger.warning(f"Skipping error {error.get('error_code')} - no valid symbol")
            return None

        # Build regime validity from error context
        regime_validity = []
        if error.get('regime_at_prediction'):
            regime_validity.append(error['regime_at_prediction'])
        if error.get('regime_at_outcome') and error.get('regime_at_outcome') not in regime_validity:
            regime_validity.append(error['regime_at_outcome'])
        if not regime_validity:
            regime_validity = ['UNKNOWN']

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_learning.hypothesis_canon (
                    hypothesis_code,
                    origin_type,
                    origin_error_id,
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
                    causal_graph_depth,
                    semantic_hash,
                    created_at,
                    created_by,
                    asset_class
                ) VALUES (
                    %s, 'ERROR_DRIVEN', %s, %s, %s, %s, %s, %s, %s, %s, 'MEDIUM',
                    48, %s, %s, %s, 3, 0.55, 0.55, 'DRAFT', %s, 1, %s, NOW(), %s, %s
                )
                RETURNING hypothesis_code, canon_id
            """, (
                hypothesis_code,
                str(error.get('error_id')) if error.get('error_id') else None,
                rationale['origin_rationale'],
                rationale['economic_rationale'],
                rationale['causal_mechanism'],
                rationale['counterfactual'],
                rationale['behavioral_basis'],
                [symbol],
                direction,
                regime_validity,
                json.dumps({r: 0.55 for r in regime_validity}),
                json.dumps({
                    'source_error': str(error.get('error_code')),
                    'direction_test': f"Price does not move {direction} within 48h",
                    'confidence_threshold': 0.4
                }),
                GENERATOR_ID,
                semantic_hash,
                DAEMON_NAME,
                asset_class
            ))

            result = cur.fetchone()

            if result:
                # Mark error as converted
                cur.execute("""
                    UPDATE fhq_learning.error_classification_taxonomy
                    SET hypothesis_generated = TRUE,
                        generated_hypothesis_id = %s
                    WHERE error_id = %s
                """, (result[1], error.get('error_id')))

                conn.commit()
                logger.info(f"Generated {hypothesis_code} from error {error.get('error_code')}")
                return result[0]

        conn.close()
    except Exception as e:
        logger.error(f"Failed to generate hypothesis from error: {e}")
        import traceback
        traceback.print_exc()
    return None


def run_learning_cycle(cycle_num: int) -> Dict[str, Any]:
    """Run a single FINN-E learning cycle."""
    start_time = datetime.now(timezone.utc)
    results = {
        'cycle': cycle_num,
        'timestamp': start_time.isoformat(),
        'generator_id': GENERATOR_ID,
        'hypotheses_generated': 0,
        'errors_available': 0,
        'errors_processed': []
    }

    try:
        # Get unconverted HIGH priority errors
        errors = get_unconverted_high_errors()
        results['errors_available'] = len(errors)
        logger.info(f"Found {len(errors)} unconverted HIGH priority errors")

        if not errors:
            logger.info("No unconverted errors to process")
            results['status'] = 'NO_DATA'
            return results

        # Process errors (limit per cycle)
        for error in errors[:MAX_HYPOTHESES_PER_CYCLE]:
            hypothesis_code = generate_hypothesis_from_error(error)
            if hypothesis_code:
                results['hypotheses_generated'] += 1
                results['errors_processed'].append(error.get('error_code'))

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
    logger.info(f"FINN-E ERROR REPAIR CYCLE {results['cycle']} COMPLETE")
    logger.info(f"  Generator: {results['generator_id']}")
    logger.info(f"  Errors Available: {results['errors_available']}")
    logger.info(f"  Hypotheses Generated: {results['hypotheses_generated']}")
    logger.info(f"  Errors Processed: {results.get('errors_processed', [])}")
    logger.info(f"  Duration: {results.get('duration_sec', 0):.1f}s")
    logger.info(f"  Status: {results['status']}")
    logger.info("=" * 60)


class FINNEScheduler:
    """FINN-E Error Repair Scheduler."""

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
        logger.info("FINN-E ERROR REPAIR SCHEDULER ACTIVATED")
        logger.info("CEO-DIR-2026-FINN-E-SCHEDULER-001")
        logger.info(f"  Interval: {INTERVAL_MINUTES} minutes")
        logger.info(f"  Generator: {GENERATOR_ID}")
        logger.info(f"  Input: HIGH priority forecast errors")
        logger.info(f"  Max per cycle: {MAX_HYPOTHESES_PER_CYCLE}")
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

                logger.info(f"Starting FINN-E cycle (#{self.cycles_today + 1} today, DEFCON: {defcon_level})...")
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
        logger.info(f"FINN-E Scheduler shutdown. Total hypotheses: {self.total_hypotheses}")


if __name__ == '__main__':
    from daemon_lock import acquire_lock, release_lock
    if not acquire_lock('finn_e_scheduler'):
        sys.exit(0)
    try:
        print("[FINN-E] Error Repair Scheduler starting...")
        print("[FINN-E] CEO-DIR-2026-FINN-E-SCHEDULER-001")
        print("[FINN-E] Input: HIGH priority forecast errors")

        scheduler = FINNEScheduler()
        scheduler.run()
    finally:
        release_lock('finn_e_scheduler')
