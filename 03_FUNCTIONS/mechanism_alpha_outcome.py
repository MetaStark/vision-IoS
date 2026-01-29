#!/usr/bin/env python3
"""
Mechanism Alpha Outcome Daemon
===============================

Purpose: Evaluate open triggers past their deadline and write outcomes
         (MFE, MAE, PnL, result_bool) to fhq_learning.outcome_ledger.

Test-specific evaluation:
  TEST A (Vol Squeeze):    direction_correct AND magnitude > 2*ATR
  TEST B (Regime Align):   price_at_deadline > entry_price (LONG wins)
  TEST C (Mean Revert):    price touched bb_middle within timeframe
  TEST D (Breakout):       price_at_deadline > entry_price (continuation held)
  TEST E (Trend Pullback): price_at_deadline > entry_price (pullback recovered)
  TEST F (Panic Bottom):   max_price within timeframe > entry_price (bounce)

Authority: CEO Phase 2 Runtime Fabrication Directive
Contract: EC-003_2026_PRODUCTION

Usage:
    python mechanism_alpha_outcome.py              # Run daemon (60 min interval)
    python mechanism_alpha_outcome.py --once       # Single cycle then exit
    python mechanism_alpha_outcome.py --interval N # Override interval (seconds)

Author: STIG (EC-003)
Date: 2026-01-29
"""

import os
import sys
import json
import time
import signal
import hashlib
import logging
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[ALPHA_OUTCOME] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/mechanism_alpha_outcome.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AlphaOutcome')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DAEMON_NAME = 'mechanism_alpha_outcome'
DEFAULT_INTERVAL = 3600  # 60 minutes

BLOCKED_DEFCON = {'RED', 'BLACK', 'ORANGE'}

SHUTDOWN = False

def handle_signal(signum, frame):
    global SHUTDOWN
    logger.info(f"Received signal {signum}, shutting down...")
    SHUTDOWN = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return str(obj)
    raise TypeError(f"Not serializable: {type(obj)}")


def check_gate(cur):
    cur.execute("""
        SELECT status FROM fhq_meta.gate_status
        WHERE gate_id = 'PHASE2_HYPOTHESIS_SWARM_V1.1'
    """)
    row = cur.fetchone()
    return row and row['status'] == 'OPEN'


def check_defcon(cur):
    cur.execute("""
        SELECT defcon_level FROM fhq_governance.defcon_state
        WHERE is_current = true
    """)
    row = cur.fetchone()
    return row['defcon_level'] if row else 'UNKNOWN'


def heartbeat(cur, status='RUNNING', metadata=None):
    cur.execute("""
        INSERT INTO fhq_monitoring.daemon_health
            (daemon_name, status, last_heartbeat, metadata, expected_interval_minutes, is_critical)
        VALUES (%s, %s, NOW(), %s, %s, true)
        ON CONFLICT (daemon_name) DO UPDATE SET
            status = EXCLUDED.status,
            last_heartbeat = NOW(),
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """, (DAEMON_NAME, status, json.dumps(metadata or {}, default=decimal_default), 60))


def get_evaluable_triggers(cur):
    """Find triggers past their deadline with no outcome yet.
    Uses FOR UPDATE SKIP LOCKED for concurrency safety."""
    cur.execute("""
        SELECT
            te.trigger_event_id,
            te.experiment_id,
            te.asset_id,
            te.event_timestamp,
            te.trigger_indicators,
            te.entry_price,
            te.context_snapshot_hash,
            er.experiment_code,
            hc.hypothesis_code,
            hc.falsification_criteria,
            hc.expected_direction,
            hc.expected_timeframe_hours
        FROM fhq_learning.trigger_events te
        JOIN fhq_learning.experiment_registry er ON te.experiment_id = er.experiment_id
        JOIN fhq_learning.hypothesis_canon hc ON er.hypothesis_id = hc.canon_id
        LEFT JOIN fhq_learning.outcome_ledger ol ON te.trigger_event_id = ol.trigger_event_id
        WHERE ol.outcome_id IS NULL
          AND te.event_timestamp + make_interval(hours => hc.expected_timeframe_hours::int) < NOW()
        FOR UPDATE OF te SKIP LOCKED
    """)
    return cur.fetchall()


def get_price_series(cur, asset_id, start_date, end_date):
    """Get price series between two dates."""
    cur.execute("""
        SELECT date, close, high, low
        FROM fhq_data.price_series
        WHERE listing_id = %s AND date >= %s AND date <= %s
        ORDER BY date ASC
    """, (asset_id, start_date, end_date))
    return cur.fetchall()


def get_price_at_date(cur, asset_id, target_date):
    """Get closest price at or before a target date."""
    cur.execute("""
        SELECT date, close
        FROM fhq_data.price_series
        WHERE listing_id = %s AND date <= %s
        ORDER BY date DESC
        LIMIT 1
    """, (asset_id, target_date))
    return cur.fetchone()


def get_latest_regime(cur, asset_id):
    """Get latest sovereign regime for context."""
    cur.execute("""
        SELECT sovereign_regime, engine_version, timestamp
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """, (asset_id,))
    return cur.fetchone()


def compute_mfe_mae(prices, entry_price, expected_direction):
    """Compute Maximum Favorable Excursion and Maximum Adverse Excursion using Decimal."""
    if not prices:
        return None, None

    entry = Decimal(str(entry_price))
    highs = [Decimal(str(p['high'])) for p in prices if p['high'] is not None]
    lows = [Decimal(str(p['low'])) for p in prices if p['low'] is not None]

    if not highs or not lows:
        return None, None

    max_price = max(highs)
    min_price = min(lows)
    zero = Decimal('0')

    if expected_direction in ('BULLISH', 'LONG', 'EITHER'):
        mfe = max_price - entry
        mae = entry - min_price
    elif expected_direction in ('BEARISH', 'SHORT'):
        mfe = entry - min_price
        mae = max_price - entry
    else:
        # Neutral: magnitude
        mfe = max(max_price - entry, entry - min_price)
        mae = min(max_price - entry, entry - min_price)

    return max(mfe, zero), max(mae, zero)


def evaluate_test_a(prices, entry_price, trigger_indicators):
    """TEST A (Vol Squeeze): direction_correct AND magnitude > 2*ATR."""
    if not prices:
        return False

    entry = float(entry_price)
    highs = [float(p['high']) for p in prices if p['high'] is not None]
    lows = [float(p['low']) for p in prices if p['low'] is not None]

    if not highs or not lows:
        return False

    max_price = max(highs)
    min_price = min(lows)

    # Direction correct: net upward movement dominates
    direction_correct = (max_price - entry) > (entry - min_price)

    # Magnitude significant: max excursion > 2 * ATR
    atr = trigger_indicators.get('atr_14')
    if atr is None or float(atr) == 0:
        return False

    max_excursion = max(abs(max_price - entry), abs(entry - min_price))
    magnitude_significant = max_excursion > 2 * float(atr)

    return direction_correct and magnitude_significant


def evaluate_test_b(cur, asset_id, trigger_time, entry_price, timeframe_hours):
    """TEST B (Regime Align): price_at_deadline > entry_price (LONG wins)."""
    deadline = trigger_time + timedelta(hours=int(timeframe_hours))
    deadline_price_row = get_price_at_date(cur, asset_id, deadline.date())

    if not deadline_price_row:
        return False

    return float(deadline_price_row['close']) > float(entry_price)


def evaluate_test_c(prices, trigger_indicators):
    """TEST C (Mean Revert): price touched bb_middle within timeframe."""
    bb_middle = trigger_indicators.get('bb_middle')
    if bb_middle is None or not prices:
        return False

    bb_mid = float(bb_middle)

    # Check if any low touched or went below bb_middle
    for p in prices:
        if p['low'] is not None and float(p['low']) <= bb_mid:
            return True
        if p['close'] is not None and float(p['close']) <= bb_mid:
            return True

    return False


def evaluate_test_d(cur, asset_id, trigger_time, entry_price, timeframe_h):
    """TEST D (Breakout): price_at_deadline > entry_price (continuation held)."""
    deadline = trigger_time + timedelta(hours=int(timeframe_h))
    deadline_price_row = get_price_at_date(cur, asset_id, deadline.date())
    if not deadline_price_row:
        return False
    return float(deadline_price_row['close']) > float(entry_price)


def evaluate_test_e(cur, asset_id, trigger_time, entry_price, timeframe_h):
    """TEST E (Trend Pullback): price_at_deadline > entry_price (pullback recovered)."""
    deadline = trigger_time + timedelta(hours=int(timeframe_h))
    deadline_price_row = get_price_at_date(cur, asset_id, deadline.date())
    if not deadline_price_row:
        return False
    return float(deadline_price_row['close']) > float(entry_price)


def evaluate_test_f(prices, entry_price):
    """TEST F (Panic Bottom): max price within timeframe > entry_price (bounce)."""
    if not prices:
        return False
    entry = float(entry_price)
    highs = [float(p['high']) for p in prices if p['high'] is not None]
    if not highs:
        return False
    return max(highs) > entry


def compute_pnl(entry_price, exit_price, expected_direction):
    """Compute PnL gross and net using Decimal for full precision."""
    entry = Decimal(str(entry_price))
    exit_p = Decimal(str(exit_price))

    if expected_direction in ('BULLISH', 'LONG'):
        pnl_gross = exit_p - entry
    elif expected_direction in ('BEARISH', 'SHORT'):
        pnl_gross = entry - exit_p
    else:
        # NEUTRAL / EITHER: magnitude only
        pnl_gross = abs(exit_p - entry)

    # 0.1% spread estimate
    spread = entry * Decimal('0.001')
    pnl_net = pnl_gross - spread
    return pnl_gross, pnl_net


def compute_returns(pnl_gross, entry_price):
    """Compute return_bps and return_pct from PnL and entry price."""
    entry = Decimal(str(entry_price))
    gross = Decimal(str(pnl_gross))
    if entry == 0:
        return None, None
    return_pct = (gross / entry) * Decimal('100')
    return_bps = return_pct * Decimal('100')  # 1% = 100 bps
    return return_bps, return_pct


def build_outcome_context(regime_row, defcon):
    """Build context snapshot for outcome evaluation."""
    context = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "regime_at_evaluation": regime_row['sovereign_regime'] if regime_row else "UNKNOWN",
        "regime_model_version": regime_row['engine_version'] if regime_row else "UNKNOWN",
        "defcon_level": defcon,
    }
    return context


def compute_context_hash(context):
    canonical = json.dumps(context, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def run_cycle():
    """Execute one outcome evaluation cycle."""
    conn = get_db_connection()
    conn.autocommit = False
    outcomes_evaluated = 0
    outcomes_positive = 0

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Gate check
            if not check_gate(cur):
                logger.warning("GATE CLOSED. Skipping cycle.")
                heartbeat(cur, status='DEGRADED', metadata={'reason': 'GATE_CLOSED'})
                conn.commit()
                return 0, 0

            # DEFCON check
            defcon = check_defcon(cur)
            if defcon in BLOCKED_DEFCON:
                logger.warning(f"DEFCON {defcon}: Blocked. Skipping cycle.")
                heartbeat(cur, status='DEGRADED', metadata={'reason': f'DEFCON_{defcon}'})
                conn.commit()
                return 0, 0

            # Find evaluable triggers
            triggers = get_evaluable_triggers(cur)
            if not triggers:
                logger.info("No evaluable triggers found.")
                heartbeat(cur, status='HEALTHY', metadata={'outcomes_evaluated': 0})
                conn.commit()
                return 0, 0

            logger.info(f"Found {len(triggers)} evaluable triggers")

            for trig in triggers:
                test_code = trig['falsification_criteria'].get('measurement_schema', {}).get('test_code', '')
                timeframe_h = int(trig['expected_timeframe_hours'])
                trigger_time = trig['event_timestamp']
                deadline = trigger_time + timedelta(hours=timeframe_h)
                entry_price = trig['entry_price']
                asset_id = trig['asset_id']
                trigger_indicators = trig['trigger_indicators'] or {}

                logger.info(f"Evaluating: {asset_id} test={test_code} "
                            f"trigger={trigger_time} deadline={deadline}")

                # Get price series for evaluation window
                prices = get_price_series(cur, asset_id, trigger_time, deadline)
                if not prices:
                    logger.warning(f"  No price data for evaluation window. Skipping.")
                    continue

                # Get exit price (at deadline)
                exit_price_row = get_price_at_date(cur, asset_id, deadline.date())
                exit_price = exit_price_row['close'] if exit_price_row else prices[-1]['close']

                # Compute MFE/MAE
                mfe, mae = compute_mfe_mae(prices, entry_price, trig['expected_direction'])

                # ATR multiples
                atr = trigger_indicators.get('atr_14')
                mfe_atr = None
                mae_atr = None
                if atr and float(atr) > 0:
                    atr_f = float(atr)
                    mfe_atr = float(mfe) / atr_f if mfe is not None else None
                    mae_atr = float(mae) / atr_f if mae is not None else None

                # Test-specific result
                result_bool = False
                if test_code == 'ALPHA_SAT_A':
                    result_bool = evaluate_test_a(prices, entry_price, trigger_indicators)
                elif test_code == 'ALPHA_SAT_B':
                    result_bool = evaluate_test_b(cur, asset_id, trigger_time, entry_price, timeframe_h)
                elif test_code == 'ALPHA_SAT_C':
                    result_bool = evaluate_test_c(prices, trigger_indicators)
                elif test_code == 'ALPHA_SAT_D':
                    result_bool = evaluate_test_d(cur, asset_id, trigger_time, entry_price, timeframe_h)
                elif test_code == 'ALPHA_SAT_E':
                    result_bool = evaluate_test_e(cur, asset_id, trigger_time, entry_price, timeframe_h)
                elif test_code == 'ALPHA_SAT_F':
                    result_bool = evaluate_test_f(prices, entry_price)

                # PnL (Decimal precision)
                pnl_gross, pnl_net = compute_pnl(entry_price, exit_price, trig['expected_direction'])

                # Returns
                return_bps, return_pct = compute_returns(pnl_gross, entry_price)

                # Time to outcome
                time_to_outcome = deadline - trigger_time

                # Context: entry_context_hash from trigger, exit_context from current state
                entry_context_hash = trig['context_snapshot_hash']
                regime_row = get_latest_regime(cur, asset_id)
                exit_context = build_outcome_context(regime_row, defcon)
                exit_context_hash = compute_context_hash(exit_context)

                # INSERT outcome (new schema: entry/exit context split, return columns)
                cur.execute("""
                    INSERT INTO fhq_learning.outcome_ledger (
                        experiment_id, trigger_event_id,
                        result_bool, pnl_gross_simulated, pnl_net_est,
                        entry_context_hash, exit_context_hash, exit_context_details,
                        mfe, mae, mfe_atr_multiple, mae_atr_multiple,
                        return_bps, return_pct,
                        time_to_outcome, created_by
                    ) VALUES (
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, 'STIG'
                    )
                    ON CONFLICT (experiment_id, trigger_event_id) DO NOTHING
                    RETURNING outcome_id
                """, (
                    str(trig['experiment_id']), str(trig['trigger_event_id']),
                    result_bool, str(pnl_gross), str(pnl_net),
                    entry_context_hash, exit_context_hash, json.dumps(exit_context, default=decimal_default),
                    mfe, mae, mfe_atr, mae_atr,
                    str(return_bps) if return_bps is not None else None,
                    str(return_pct) if return_pct is not None else None,
                    time_to_outcome,
                ))
                result = cur.fetchone()
                if result:
                    outcomes_evaluated += 1
                    if result_bool:
                        outcomes_positive += 1
                    logger.info(f"  OUTCOME: result={result_bool} pnl_gross={pnl_gross} "
                                f"return_bps={return_bps} mfe={mfe} mae={mae} id={result['outcome_id']}")
                else:
                    logger.info(f"  OUTCOME DEDUPED (already exists): {trig['trigger_event_id']}")

            # Heartbeat
            win_rate = outcomes_positive / outcomes_evaluated if outcomes_evaluated > 0 else 0.0
            heartbeat(cur, status='HEALTHY', metadata={
                'cycle_time': datetime.now(timezone.utc).isoformat(),
                'outcomes_evaluated': outcomes_evaluated,
                'outcomes_positive': outcomes_positive,
                'win_rate': round(win_rate, 4),
                'defcon': defcon,
            })

            conn.commit()
            logger.info(f"Cycle complete: evaluated={outcomes_evaluated} "
                        f"positive={outcomes_positive} win_rate={win_rate:.2%}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Cycle failed: {e}", exc_info=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                heartbeat(cur, status='UNHEALTHY', metadata={'error': str(e)})
                conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    return outcomes_evaluated, outcomes_positive


def run_daemon(interval):
    """Run continuous daemon loop."""
    logger.info(f"Starting daemon (interval={interval}s)")
    cycle = 0

    while not SHUTDOWN:
        cycle += 1
        logger.info(f"=== Cycle {cycle} ===")
        try:
            evaluated, positive = run_cycle()
            logger.info(f"Cycle {cycle} complete: evaluated={evaluated} positive={positive}")
        except Exception as e:
            logger.error(f"Cycle {cycle} failed: {e}")

        for _ in range(interval):
            if SHUTDOWN:
                break
            time.sleep(1)

    logger.info("Daemon shutdown complete.")


def main():
    parser = argparse.ArgumentParser(description='Alpha Satellite Outcome Daemon')
    parser.add_argument('--once', action='store_true', help='Single cycle then exit')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL, help='Cycle interval in seconds')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("MECHANISM ALPHA OUTCOME DAEMON")
    logger.info(f"Interval: {args.interval}s")
    logger.info(f"Once: {args.once}")
    logger.info("=" * 60)

    if args.once:
        evaluated, positive = run_cycle()
        logger.info(f"Single cycle complete: evaluated={evaluated} positive={positive}")
        return 0

    run_daemon(args.interval)
    return 0


if __name__ == '__main__':
    sys.exit(main())
