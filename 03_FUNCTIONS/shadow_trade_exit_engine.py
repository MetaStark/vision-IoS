#!/usr/bin/env python3
"""
SHADOW TRADE EXIT ENGINE
=========================
Evaluates OPEN shadow trades and closes them when exit conditions are met.

Pipeline position: Step 5.1 (after shadow_trade_creator, before capital_simulation)

Exit conditions (evaluated in order):
  1. TIME_EXPIRY: entry_time + hypothesis.expected_timeframe_hours has elapsed
     AND a price bar exists at or after the expiry time.
  2. STOP_LOSS: intraday low breached stop-loss threshold (entry_price * (1 - SL_PCT))
     for LONG trades (high for SHORT).
  3. TAKE_PROFIT: intraday high breached take-profit threshold (entry_price * (1 + TP_PCT))
     for LONG trades (low for SHORT).

On exit:
  - exit_price = close price of the exit bar
  - exit_time = timestamp of the exit bar
  - shadow_pnl = (exit_price - entry_price) * shadow_size for LONG
  - shadow_return_pct = (exit_price / entry_price - 1) * 100
  - max_favorable_excursion = best intraday move in trade direction
  - max_adverse_excursion = worst intraday move against trade direction
  - exit_reason = TIME_EXPIRY | STOP_LOSS | TAKE_PROFIT
  - exit_regime = current regime at exit time
  - status = CLOSED

Price source: fhq_data.price_series (daily OHLC)

Safety:
  - No broker calls
  - Deterministic, idempotent (only updates OPEN trades)
  - Full lineage preserved

Database operations:
  READS:  shadow_trades, hypothesis_canon, price_series, regime_state
  WRITES: shadow_trades (UPDATE only: exit fields + status)

Usage:
    python shadow_trade_exit_engine.py           # Evaluate and close
    python shadow_trade_exit_engine.py --check   # Dry run

Author: STIG (CTO)
Date: 2026-01-30
Contract: EC-003_2026_PRODUCTION
Directive: CEO-DIR-20260130-PIPELINE-COMPLETION-002 D1
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from governance_preflight import run_governance_preflight, GovernancePreflightError

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[EXIT_ENGINE] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/shadow_trade_exit_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('exit_engine')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Default risk parameters (used when EWRE is not available)
DEFAULT_STOP_LOSS_PCT = 0.05    # 5% stop loss
DEFAULT_TAKE_PROFIT_PCT = 0.10  # 10% take profit
DEFAULT_TIMEFRAME_HOURS = 24    # 24h default expiry

REGIME_MAP = {
    'BULL': 'BULL',
    'BEAR': 'BEAR',
    'SIDEWAYS': 'SIDEWAYS',
    'CRISIS': 'CRISIS',
    'STRESS': 'CRISIS',
    'UNKNOWN': 'UNKNOWN',
}


def get_current_regime(conn) -> str:
    """Get current regime mapped for shadow_trades constraint."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT current_regime
            FROM fhq_meta.regime_state
            ORDER BY last_updated_at DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return 'UNKNOWN'
        return REGIME_MAP.get(row['current_regime'], 'UNKNOWN')


def find_open_shadow_trades(conn) -> list:
    """Find all OPEN shadow trades with their hypothesis context."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                st.trade_id,
                st.shadow_trade_ref,
                st.asset_id,
                st.direction,
                st.entry_price,
                st.entry_time,
                st.entry_confidence,
                st.entry_regime,
                st.shadow_size,
                st.source_hypothesis_id,
                st.trigger_event_id,
                st.lineage_hash,
                hc.expected_timeframe_hours,
                hc.hypothesis_code
            FROM fhq_execution.shadow_trades st
            LEFT JOIN fhq_learning.hypothesis_canon hc
                ON st.source_hypothesis_id = hc.canon_id::text
            WHERE st.status = 'OPEN'
            ORDER BY st.entry_time
        """)
        return cur.fetchall()


def get_price_bars_after(conn, asset_id: str, after_time) -> list:
    """Get daily price bars for an asset after a given time."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT date, open, high, low, close, volume
            FROM fhq_data.price_series
            WHERE listing_id = %s
            AND date > (%s)::date
            ORDER BY date
        """, (asset_id, after_time))
        return cur.fetchall()


def get_price_bars_range(conn, asset_id: str, start_time, end_time) -> list:
    """Get daily price bars for an asset in a time range (inclusive)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT date, open, high, low, close, volume
            FROM fhq_data.price_series
            WHERE listing_id = %s
            AND date > (%s)::date
            AND date <= (%s)::date
            ORDER BY date
        """, (asset_id, start_time, end_time))
        return cur.fetchall()


def evaluate_exit(trade: dict, bars_after_entry: list, regime: str) -> dict:
    """
    Evaluate whether a shadow trade should be closed.

    Returns dict with exit info or None if trade should remain open.
    """
    if not bars_after_entry:
        return None

    entry_price = float(trade['entry_price'])
    direction = trade['direction']
    timeframe_hours = float(trade['expected_timeframe_hours'] or DEFAULT_TIMEFRAME_HOURS)
    entry_time = trade['entry_time']

    # Compute expiry time — normalize to date for comparison with daily bars
    expiry_time = entry_time + timedelta(hours=timeframe_hours)
    expiry_date = expiry_time.date() if hasattr(expiry_time, 'date') else expiry_time

    # Compute stop/take-profit thresholds
    if direction == 'LONG':
        stop_price = entry_price * (1 - DEFAULT_STOP_LOSS_PCT)
        tp_price = entry_price * (1 + DEFAULT_TAKE_PROFIT_PCT)
    elif direction == 'SHORT':
        stop_price = entry_price * (1 + DEFAULT_STOP_LOSS_PCT)
        tp_price = entry_price * (1 - DEFAULT_TAKE_PROFIT_PCT)
    else:
        # NEUTRAL — close at first available bar
        bar = bars_after_entry[0]
        return {
            'exit_price': bar['close'],
            'exit_time': bar['date'],
            'exit_reason': 'NEUTRAL_CLOSE',
            'exit_regime': regime,
            'bars_evaluated': 1,
        }

    # Track MFE/MAE across all bars
    max_favorable = 0.0
    max_adverse = 0.0

    for i, bar in enumerate(bars_after_entry):
        bar_high = float(bar['high'])
        bar_low = float(bar['low'])
        bar_close = float(bar['close'])
        bar_time = bar['date']
        # Normalize bar_time to date for comparison with expiry_date
        bar_date = bar_time.date() if hasattr(bar_time, 'date') and callable(bar_time.date) else bar_time

        # Update MFE/MAE
        if direction == 'LONG':
            favorable = bar_high - entry_price
            adverse = entry_price - bar_low
        else:  # SHORT
            favorable = entry_price - bar_low
            adverse = bar_high - entry_price

        max_favorable = max(max_favorable, favorable)
        max_adverse = max(max_adverse, adverse)

        # Check stop-loss (Priority 1)
        if direction == 'LONG' and bar_low <= stop_price:
            return {
                'exit_price': stop_price,  # Assume stopped at stop level
                'exit_time': bar_time,
                'exit_reason': 'STOP_LOSS',
                'exit_regime': regime,
                'max_favorable': max_favorable,
                'max_adverse': max_adverse,
                'bars_evaluated': i + 1,
            }
        elif direction == 'SHORT' and bar_high >= stop_price:
            return {
                'exit_price': stop_price,
                'exit_time': bar_time,
                'exit_reason': 'STOP_LOSS',
                'exit_regime': regime,
                'max_favorable': max_favorable,
                'max_adverse': max_adverse,
                'bars_evaluated': i + 1,
            }

        # Check take-profit (Priority 2)
        if direction == 'LONG' and bar_high >= tp_price:
            return {
                'exit_price': tp_price,  # Assume filled at TP level
                'exit_time': bar_time,
                'exit_reason': 'TAKE_PROFIT',
                'exit_regime': regime,
                'max_favorable': max_favorable,
                'max_adverse': max_adverse,
                'bars_evaluated': i + 1,
            }
        elif direction == 'SHORT' and bar_low <= tp_price:
            return {
                'exit_price': tp_price,
                'exit_time': bar_time,
                'exit_reason': 'TAKE_PROFIT',
                'exit_regime': regime,
                'max_favorable': max_favorable,
                'max_adverse': max_adverse,
                'bars_evaluated': i + 1,
            }

        # Check time expiry (Priority 3)
        if bar_date >= expiry_date:
            return {
                'exit_price': bar_close,  # Exit at close of expiry bar
                'exit_time': bar_time,
                'exit_reason': 'TIME_EXPIRY',
                'exit_regime': regime,
                'max_favorable': max_favorable,
                'max_adverse': max_adverse,
                'bars_evaluated': i + 1,
            }

    # No exit condition met yet — trade remains open
    return None


def compute_pnl(entry_price: float, exit_price: float, direction: str,
                shadow_size: float) -> tuple:
    """Compute shadow_pnl and shadow_return_pct."""
    if direction == 'LONG':
        pnl = (exit_price - entry_price) * shadow_size
        return_pct = ((exit_price / entry_price) - 1) * 100 if entry_price > 0 else 0
    elif direction == 'SHORT':
        pnl = (entry_price - exit_price) * shadow_size
        return_pct = ((entry_price / exit_price) - 1) * 100 if exit_price > 0 else 0
    else:
        pnl = 0
        return_pct = 0
    return round(pnl, 8), round(return_pct, 6)


def close_shadow_trade(conn, trade: dict, exit_info: dict, dry_run: bool = False) -> dict:
    """Write exit data to shadow_trades and set status = CLOSED."""
    entry_price = float(trade['entry_price'])
    exit_price = float(exit_info['exit_price'])
    direction = trade['direction']
    shadow_size = float(trade['shadow_size'] or 1.0)

    pnl, return_pct = compute_pnl(entry_price, exit_price, direction, shadow_size)

    result = {
        'trade_id': str(trade['trade_id']),
        'shadow_trade_ref': trade['shadow_trade_ref'],
        'asset_id': trade['asset_id'],
        'direction': direction,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'exit_time': str(exit_info['exit_time']),
        'exit_reason': exit_info['exit_reason'],
        'exit_regime': exit_info['exit_regime'],
        'shadow_pnl': pnl,
        'shadow_return_pct': return_pct,
        'max_favorable_excursion': exit_info.get('max_favorable'),
        'max_adverse_excursion': exit_info.get('max_adverse'),
    }

    if dry_run:
        logger.info(f"  [DRY RUN] Would close: {trade['shadow_trade_ref']} | "
                    f"{trade['asset_id']} {direction} | "
                    f"entry={entry_price} exit={exit_price} | "
                    f"pnl={pnl:+.8f} ({return_pct:+.4f}%) | "
                    f"reason={exit_info['exit_reason']}")
    else:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_execution.shadow_trades
                SET exit_price = %s,
                    exit_time = %s,
                    exit_reason = %s,
                    exit_regime = %s,
                    shadow_pnl = %s,
                    shadow_return_pct = %s,
                    max_favorable_excursion = %s,
                    max_adverse_excursion = %s,
                    status = 'CLOSED',
                    updated_at = NOW()
                WHERE trade_id = %s
                AND status = 'OPEN'
            """, (
                exit_price,
                exit_info['exit_time'],
                exit_info['exit_reason'],
                exit_info['exit_regime'],
                pnl,
                return_pct,
                exit_info.get('max_favorable'),
                exit_info.get('max_adverse'),
                trade['trade_id'],
            ))
        logger.info(f"  CLOSED: {trade['shadow_trade_ref']} | "
                    f"{trade['asset_id']} {direction} | "
                    f"entry={entry_price} exit={exit_price} | "
                    f"pnl={pnl:+.8f} ({return_pct:+.4f}%) | "
                    f"reason={exit_info['exit_reason']}")

    return result


def run_exit_engine(dry_run: bool = False):
    """Main entry: evaluate all OPEN shadow trades for exit conditions."""
    logger.info("=" * 60)
    logger.info("SHADOW TRADE EXIT ENGINE — Evaluating exit conditions")
    logger.info(f"  dry_run={dry_run}")
    logger.info(f"  directive=CEO-DIR-20260130-PIPELINE-COMPLETION-002 D1")
    logger.info(f"  stop_loss={DEFAULT_STOP_LOSS_PCT*100}%  take_profit={DEFAULT_TAKE_PROFIT_PCT*100}%")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        # GOVERNANCE PREFLIGHT — fail-closed (CEO-DIR-010 Workstream B)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                preflight = run_governance_preflight(cur, 'SHADOW_TRADE_EXIT_ENGINE')
            except GovernancePreflightError as e:
                logger.error(f"GOVERNANCE PREFLIGHT BLOCKED: {e}")
                return

        # Get current regime
        regime = get_current_regime(conn)
        logger.info(f"Current regime: {regime}")

        # Find open trades
        open_trades = find_open_shadow_trades(conn)
        logger.info(f"Open shadow trades: {len(open_trades)}")

        if not open_trades:
            logger.info("No open trades to evaluate.")
            return

        closed = []
        still_open = []
        no_data = []

        for trade in open_trades:
            ref = trade['shadow_trade_ref']
            asset = trade['asset_id']
            entry_time = trade['entry_time']

            # Get price bars after entry
            bars = get_price_bars_after(conn, asset, entry_time)

            if not bars:
                no_data.append(ref)
                logger.info(f"  {ref} | {asset} | No price data after entry ({entry_time}) — skipping")
                continue

            # Evaluate exit
            exit_info = evaluate_exit(trade, bars, regime)

            if exit_info is None:
                still_open.append(ref)
                logger.info(f"  {ref} | {asset} | No exit condition met ({len(bars)} bars evaluated)")
                continue

            # Close the trade
            result = close_shadow_trade(conn, trade, exit_info, dry_run)
            closed.append(result)

        if not dry_run and closed:
            conn.commit()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("EXIT ENGINE SUMMARY")
        logger.info(f"  Total open trades evaluated: {len(open_trades)}")
        logger.info(f"  Closed: {len(closed)}")
        logger.info(f"  Still open (no exit condition): {len(still_open)}")
        logger.info(f"  No price data: {len(no_data)}")
        if closed:
            total_pnl = sum(r['shadow_pnl'] for r in closed)
            winners = sum(1 for r in closed if r['shadow_pnl'] > 0)
            losers = sum(1 for r in closed if r['shadow_pnl'] < 0)
            logger.info(f"  Total shadow P&L: {total_pnl:+.8f}")
            logger.info(f"  Winners: {winners}  Losers: {losers}")
            by_reason = {}
            for r in closed:
                reason = r['exit_reason']
                by_reason[reason] = by_reason.get(reason, 0) + 1
            for reason, cnt in sorted(by_reason.items()):
                logger.info(f"  {reason}: {cnt}")
        logger.info("=" * 60)

        # Evidence
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'directive': 'CEO-DIR-20260130-PIPELINE-COMPLETION-002',
            'deliverable': 'D1',
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'executed_by': 'STIG_EXIT_ENGINE',
            'dry_run': dry_run,
            'regime_at_evaluation': regime,
            'trades_evaluated': len(open_trades),
            'trades_closed': len(closed),
            'trades_still_open': len(still_open),
            'trades_no_data': len(no_data),
            'risk_parameters': {
                'stop_loss_pct': DEFAULT_STOP_LOSS_PCT,
                'take_profit_pct': DEFAULT_TAKE_PROFIT_PCT,
                'default_timeframe_hours': DEFAULT_TIMEFRAME_HOURS,
            },
            'closed_trades': closed,
        }
        evidence_path = os.path.join(evidence_dir, f'SHADOW_EXIT_ENGINE_{ts}.json')
        with open(evidence_path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)
        logger.info(f"Evidence: {evidence_path}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Shadow Trade Exit Engine')
    parser.add_argument('--check', '--dry-run', action='store_true',
                        help='Dry run: evaluate without writing')
    args = parser.parse_args()
    run_exit_engine(dry_run=args.check)


if __name__ == '__main__':
    main()
