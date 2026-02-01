#!/usr/bin/env python3
"""
IoS-012-B EXIT SENTINEL DAEMON
==============================
Directive: CEO-DIR-2026-107
Classification: GOVERNANCE ENFORCEMENT LAYER
Author: STIG
Date: 2026-01-19

Per CEO-DIR-2026-107 UPGRADE 3:
Sentinel is classified as GOVERNANCE enforcement layer, NOT performance logic.
It operates deterministically without access to signal generation.

Purpose:
- Monitor all open paper positions against canonical exit levels
- Enforce SPOT-canonical exit rules:
  - STOP_LOSS_ATR_2X: 2.0x ATR(14) from entry
  - TAKE_PROFIT_1_25R: 1.25R where R = |entry - SL|
  - REGIME_EXIT: Exit if regime != STRESS
- Log all enforcement actions for audit trail

Phase 1 Restriction (CEO-DIR-2026-107 Section 3.3):
- NO adaptive TP/SL
- NO trailing stops
- Fixed rules only to verify positive expectancy first
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[IoS-012-B-SENTINEL] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Sentinel governance parameters (FIXED - no optimization in Phase 1)
ATR_MULTIPLIER = 2.0      # Per CEO-DIR-2026-107 Section 3.1
R_MULTIPLIER = 1.25       # Per CEO-DIR-2026-107 Section 3.2
ATR_PERIOD = 14           # Per UPGRADE 1: ATR(14)

# Phase 1 restrictions
ADAPTIVE_TP_SL_ENABLED = False  # FORBIDDEN in Phase 1
TRAILING_STOP_ENABLED = False   # FORBIDDEN in Phase 1


@dataclass
class SentinelCheck:
    """Result of a sentinel governance check."""
    position_id: str
    ticker: str
    direction: str
    entry_price: float
    current_price: float
    canonical_stop_loss: float
    canonical_take_profit: float
    sl_distance_pct: float
    tp_distance_pct: float
    sl_hit: bool
    tp_hit: bool
    regime_exit: bool
    exit_action: str
    check_timestamp: str


class ExitSentinelDaemon:
    """
    Governance enforcement layer for IoS-012-B exit rules.

    Per CEO-DIR-2026-107 UPGRADE 3:
    This is NOT performance logic. It operates deterministically
    without access to signal generation.
    """

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Exit Sentinel Daemon initialized")
        logger.info(f"Parameters: ATR_MULT={ATR_MULTIPLIER}, R_MULT={R_MULTIPLIER}, ATR_PERIOD={ATR_PERIOD}")
        logger.info(f"Phase 1 Restrictions: Adaptive={ADAPTIVE_TP_SL_ENABLED}, Trailing={TRAILING_STOP_ENABLED}")

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions under sentinel monitoring."""
        query = """
            SELECT
                position_id, ticker, direction, entry_price, shares,
                canonical_stop_loss, canonical_take_profit, atr_at_entry, r_value,
                entry_timestamp, position_size_usd
            FROM fhq_alpha.ios012b_paper_positions
            WHERE status = 'OPEN' AND sentinel_monitored = TRUE
            ORDER BY entry_timestamp
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for ticker."""
        query = """
            SELECT close FROM fhq_market.prices
            WHERE canonical_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (ticker,))
                row = cur.fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            logger.warning(f"Could not get price for {ticker}: {e}")
            self.conn.rollback()
            return None

    def get_current_regime(self, ticker: str) -> Optional[str]:
        """Get current regime for ticker."""
        query = """
            SELECT regime FROM fhq_research.regime_states
            WHERE asset_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (ticker,))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.warning(f"Could not get regime for {ticker}: {e}")
            self.conn.rollback()
            return None

    def check_position(self, position: Dict) -> SentinelCheck:
        """
        Check a single position against exit rules.

        This is DETERMINISTIC governance enforcement, not signal logic.
        """
        ticker = position['ticker']
        direction = position['direction']
        entry_price = float(position['entry_price'])
        canonical_sl = float(position['canonical_stop_loss']) if position['canonical_stop_loss'] else None
        canonical_tp = float(position['canonical_take_profit']) if position['canonical_take_profit'] else None

        # Get current price
        current_price = self.get_current_price(ticker)
        if current_price is None:
            logger.warning(f"No current price for {ticker}, skipping check")
            return None

        # If canonical levels not set, calculate them now
        if canonical_sl is None or canonical_tp is None:
            levels = self.calculate_exit_levels(ticker, entry_price, direction)
            if levels:
                canonical_sl = levels['canonical_stop_loss']
                canonical_tp = levels['canonical_take_profit']
                # Update position with canonical levels
                self._update_position_levels(position['position_id'], levels)
            else:
                logger.warning(f"Could not calculate exit levels for {ticker}")
                return None

        # Check Stop Loss
        if direction == 'UP':  # LONG
            sl_hit = current_price <= canonical_sl
            tp_hit = current_price >= canonical_tp
        else:  # SHORT
            sl_hit = current_price >= canonical_sl
            tp_hit = current_price <= canonical_tp

        # Check Regime Exit
        current_regime = self.get_current_regime(ticker)
        regime_exit = current_regime is not None and current_regime != 'STRESS'

        # Calculate distances
        sl_distance_pct = ((current_price - canonical_sl) / entry_price) * 100
        tp_distance_pct = ((canonical_tp - current_price) / entry_price) * 100

        # Determine exit action (priority order per rules)
        if sl_hit:
            exit_action = 'EXIT_STOP_LOSS_ATR_2X'
        elif tp_hit:
            exit_action = 'EXIT_TAKE_PROFIT_1_25R'
        elif regime_exit:
            exit_action = 'EXIT_REGIME_CHANGE'
        else:
            exit_action = 'HOLD'

        return SentinelCheck(
            position_id=str(position['position_id']),
            ticker=ticker,
            direction=direction,
            entry_price=entry_price,
            current_price=current_price,
            canonical_stop_loss=canonical_sl,
            canonical_take_profit=canonical_tp,
            sl_distance_pct=sl_distance_pct,
            tp_distance_pct=tp_distance_pct,
            sl_hit=sl_hit,
            tp_hit=tp_hit,
            regime_exit=regime_exit,
            exit_action=exit_action,
            check_timestamp=datetime.now(timezone.utc).isoformat()
        )

    def calculate_exit_levels(self, ticker: str, entry_price: float, direction: str) -> Optional[Dict]:
        """Calculate canonical exit levels using database function."""
        query = """
            SELECT * FROM fhq_alpha.calculate_canonical_exit_levels(%s, %s, %s)
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (ticker, entry_price, direction))
                row = cur.fetchone()
                if row:
                    return {
                        'canonical_stop_loss': float(row['canonical_stop_loss']),
                        'canonical_take_profit': float(row['canonical_take_profit']),
                        'atr_at_entry': float(row['atr_at_entry']),
                        'r_value': float(row['r_value'])
                    }
        except Exception as e:
            logger.error(f"Error calculating exit levels for {ticker}: {e}")
            self.conn.rollback()
        return None

    def _update_position_levels(self, position_id: str, levels: Dict):
        """Update position with canonical exit levels."""
        query = """
            UPDATE fhq_alpha.ios012b_paper_positions
            SET canonical_stop_loss = %s,
                canonical_take_profit = %s,
                atr_at_entry = %s,
                r_value = %s,
                updated_at = NOW()
            WHERE position_id = %s::uuid
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (
                    levels['canonical_stop_loss'],
                    levels['canonical_take_profit'],
                    levels['atr_at_entry'],
                    levels['r_value'],
                    position_id
                ))
            self.conn.commit()
            logger.info(f"Updated exit levels for position {position_id}")
        except Exception as e:
            logger.error(f"Error updating position levels: {e}")
            self.conn.rollback()

    def log_sentinel_check(self, check: SentinelCheck):
        """Log sentinel check to governance table."""
        query = """
            INSERT INTO fhq_alpha.exit_sentinel_log (
                position_id, check_timestamp, current_price,
                canonical_stop_loss, canonical_take_profit,
                sl_distance_pct, tp_distance_pct,
                exit_triggered, exit_rule, sentinel_action, evidence_hash
            ) VALUES (
                %s::uuid, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        exit_triggered = check.sl_hit or check.tp_hit or check.regime_exit
        exit_rule = None
        if check.sl_hit:
            exit_rule = 'STOP_LOSS_ATR_2X'
        elif check.tp_hit:
            exit_rule = 'TAKE_PROFIT_1_25R'
        elif check.regime_exit:
            exit_rule = 'REGIME_EXIT'

        # Create evidence hash
        evidence_data = json.dumps(asdict(check), sort_keys=True)
        evidence_hash = f"sha256:{hashlib.sha256(evidence_data.encode()).hexdigest()[:32]}"

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (
                    check.position_id,
                    check.current_price,
                    check.canonical_stop_loss,
                    check.canonical_take_profit,
                    check.sl_distance_pct,
                    check.tp_distance_pct,
                    exit_triggered,
                    exit_rule,
                    check.exit_action,
                    evidence_hash
                ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error logging sentinel check: {e}")
            self.conn.rollback()

    def execute_exit(self, check: SentinelCheck) -> bool:
        """Execute exit for a position that triggered an exit rule."""
        logger.info(f"EXECUTING EXIT: {check.ticker} - {check.exit_action}")

        query = """
            UPDATE fhq_alpha.ios012b_paper_positions
            SET status = 'CLOSED',
                exit_price = %s,
                exit_timestamp = NOW(),
                exit_reason = %s,
                exit_rule_triggered = %s,
                realized_pnl = %s,
                realized_pnl_pct = %s,
                updated_at = NOW()
            WHERE position_id = %s::uuid
        """

        # Calculate P&L
        direction_mult = 1 if check.direction == 'UP' else -1
        pnl_pct = ((check.current_price / check.entry_price) - 1) * 100 * direction_mult

        # Get shares for USD P&L
        with self.conn.cursor() as cur:
            cur.execute("SELECT shares FROM fhq_alpha.ios012b_paper_positions WHERE position_id = %s::uuid",
                       (check.position_id,))
            shares = cur.fetchone()[0]

        pnl_usd = (check.current_price - check.entry_price) * shares * direction_mult

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (
                    check.current_price,
                    f"CEO-DIR-2026-107 Sentinel: {check.exit_action}",
                    check.exit_action.replace('EXIT_', ''),
                    pnl_usd,
                    pnl_pct,
                    check.position_id
                ))
            self.conn.commit()
            logger.info(f"EXIT EXECUTED: {check.ticker} P&L=${pnl_usd:.2f} ({pnl_pct:.2f}%)")
            return True
        except Exception as e:
            logger.error(f"Error executing exit: {e}")
            self.conn.rollback()
            return False

    def run_sentinel_cycle(self, execute_exits: bool = False) -> Dict[str, Any]:
        """
        Run a complete sentinel governance cycle.

        Args:
            execute_exits: If True, automatically execute exits. If False, only log.
        """
        logger.info("=" * 60)
        logger.info("SENTINEL GOVERNANCE CYCLE START")
        logger.info("=" * 60)

        positions = self.get_open_positions()
        logger.info(f"Monitoring {len(positions)} open positions")

        results = {
            'cycle_timestamp': datetime.now(timezone.utc).isoformat(),
            'positions_checked': len(positions),
            'exits_triggered': 0,
            'exits_executed': 0,
            'checks': []
        }

        for pos in positions:
            check = self.check_position(pos)
            if check is None:
                continue

            # Log the check
            self.log_sentinel_check(check)
            results['checks'].append(asdict(check))

            # Report status
            if check.exit_action == 'HOLD':
                logger.info(f"  {check.ticker}: HOLD (SL:{check.sl_distance_pct:.2f}%, TP:{check.tp_distance_pct:.2f}%)")
            else:
                logger.warning(f"  {check.ticker}: {check.exit_action} TRIGGERED")
                results['exits_triggered'] += 1

                if execute_exits:
                    if self.execute_exit(check):
                        results['exits_executed'] += 1

        logger.info("=" * 60)
        logger.info(f"CYCLE COMPLETE: {results['exits_triggered']} exits triggered, {results['exits_executed']} executed")
        logger.info("=" * 60)

        return results

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Main entry point for Sentinel daemon."""
    import argparse

    parser = argparse.ArgumentParser(description='IoS-012-B Exit Sentinel Daemon')
    parser.add_argument('--execute', action='store_true',
                       help='Execute exits (default: monitor only)')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously (check every 5 minutes)')
    parser.add_argument('--interval', type=int, default=300,
                       help='Check interval in seconds (default: 300)')
    args = parser.parse_args()

    sentinel = ExitSentinelDaemon()

    try:
        if args.continuous:
            import time
            logger.info(f"Running in continuous mode (interval: {args.interval}s)")
            while True:
                results = sentinel.run_sentinel_cycle(execute_exits=args.execute)

                # Save results to evidence file
                evidence_path = f"03_FUNCTIONS/evidence/SENTINEL_CYCLE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(evidence_path, 'w') as f:
                    json.dump(results, f, indent=2)

                time.sleep(args.interval)
        else:
            results = sentinel.run_sentinel_cycle(execute_exits=args.execute)
            print(json.dumps(results, indent=2))
    finally:
        sentinel.close()


if __name__ == '__main__':
    main()
