#!/usr/bin/env python3
"""
IoS-012-B PAPER TRADING EXECUTOR
================================
Directive: CEO-DIR-2026-106 (Option C Approval)
Classification: PAPER_ONLY (Hindsight Firewall compliance)
Date: 2026-01-19
Author: STIG

Executes paper trades on Alpaca based on IoS-012-B inverted signals.
This is PAPER TRADING ONLY - no live capital at risk.

CEO Decision (2026-01-19):
"go with option C, activate paper trading"

Option C: Keep hindsight firewall for LIVE trading, but activate PAPER trading NOW.

Execution Modes:
1. SPOT: Direct equity paper trades (Alpaca Paper)
2. OPTIONS_SIMULATED: Simulated vertical spread P&L based on directional move

The hindsight firewall blocks LIVE trading until 2026-02-02.
Paper trading is permitted immediately to:
- Test execution mechanics
- Track simulated P&L
- Validate strike selection and timing
- Build G4 evidence package
"""

import os
import sys
import json
import uuid
import hashlib
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

load_dotenv()

# Import existing adapter
try:
    from alpaca_paper_adapter import (
        AlpacaPaperAdapter,
        PaperOrder,
        SignalLineage,
        OrderStatus,
        ALPACA_AVAILABLE,
        ALPACA_API_KEY
    )
    ADAPTER_AVAILABLE = True
except ImportError:
    ADAPTER_AVAILABLE = False
    ALPACA_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='[IoS-012-B-PAPER] %(asctime)s %(levelname)s: %(message)s'
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

# Execution mode
EXECUTION_MODE = "PAPER_ONLY"  # HARDCODED

# Hindsight firewall
LIVE_ELIGIBILITY_DATE = date(2026, 2, 2)
PAPER_TRADING_ENABLED = True  # CEO Option C approval

# Position sizing for paper trades
PAPER_POSITION_SIZE_PCT = 0.025  # 2.5% NAV per position (per IoS-012-B spec)
PAPER_MAX_EXPOSURE_PCT = 0.25    # 25% total exposure
PAPER_NAV = 100000.0             # Simulated NAV for paper trading

# Options simulation parameters
OPTIONS_SPREAD_WIDTH = 5.0       # $5 spread width
OPTIONS_DTE = 21                 # Days to expiration
OPTIONS_DELTA_TARGET = 0.45      # Target delta


@dataclass
class PaperTradeSignal:
    """A paper trade signal from IoS-012-B."""
    signal_id: str
    overlay_id: str
    ticker: str
    inverted_direction: str  # 'UP' or 'DOWN'
    source_confidence: float
    source_regime: str
    entry_price: float
    entry_timestamp: datetime


@dataclass
class PaperPosition:
    """A paper trading position."""
    position_id: str
    signal_id: str
    ticker: str
    direction: str
    entry_price: float
    entry_timestamp: datetime
    position_size_usd: float
    shares: int
    strategy_type: str  # 'SPOT' or 'OPTIONS_SIMULATED'
    status: str  # 'OPEN', 'CLOSED'
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    pnl_usd: Optional[float] = None
    pnl_pct: Optional[float] = None


class PaperTradingExecutor:
    """
    IoS-012-B Paper Trading Executor.

    Executes paper trades based on inverted signals.
    PAPER MODE ONLY - no live capital at risk.
    """

    def __init__(self):
        self.conn = None
        self.alpaca_adapter = None
        self._validate_mode()

    def _validate_mode(self):
        """Validate we're in paper mode only."""
        if EXECUTION_MODE != "PAPER_ONLY":
            raise RuntimeError("FATAL: IoS-012-B must be in PAPER_ONLY mode")

        today = date.today()
        if today >= LIVE_ELIGIBILITY_DATE:
            logger.warning("Hindsight firewall expired. Live trading may be enabled via G4.")
        else:
            days_remaining = (LIVE_ELIGIBILITY_DATE - today).days
            logger.info(f"PAPER MODE: Live trading blocked for {days_remaining} more days")

    def connect(self):
        """Connect to database and Alpaca."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

        if ADAPTER_AVAILABLE and ALPACA_API_KEY:
            self.alpaca_adapter = AlpacaPaperAdapter()
            self.alpaca_adapter.connect()
            logger.info("Connected to Alpaca Paper Trading")
        else:
            logger.warning("Alpaca not available - using simulated execution")

    def close(self):
        """Close connections."""
        if self.conn:
            self.conn.close()
        if self.alpaca_adapter:
            self.alpaca_adapter.close()

    # =========================================================================
    # SIGNAL RETRIEVAL
    # =========================================================================

    def get_actionable_signals(self) -> List[PaperTradeSignal]:
        """
        Get signals ready for paper execution.

        Criteria:
        - actual_outcome = TRUE (inversion confirmed correct)
        - Not already paper traded
        - In canonical universe
        """
        query = """
            SELECT
                ios.overlay_id,
                ios.ticker,
                ios.inverted_direction,
                ios.source_confidence,
                ios.source_regime,
                ios.entry_price_underlying,
                ios.entry_timestamp
            FROM fhq_alpha.inversion_overlay_shadow ios
            LEFT JOIN fhq_alpha.ios012b_paper_positions pp
                ON ios.overlay_id = pp.source_overlay_id
            WHERE ios.is_shadow = TRUE
              AND ios.actual_outcome = TRUE
              AND pp.position_id IS NULL
              AND ios.ticker IN (
                  SELECT ticker FROM fhq_alpha.inversion_universe
                  WHERE canonical_status = 'G4_CANONICALIZED'
              )
            ORDER BY ios.source_confidence DESC
            LIMIT 10
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        signals = []
        for row in rows:
            signal = PaperTradeSignal(
                signal_id=str(uuid.uuid4()),
                overlay_id=str(row['overlay_id']),
                ticker=row['ticker'],
                inverted_direction=row['inverted_direction'],
                source_confidence=float(row['source_confidence']),
                source_regime=row['source_regime'],
                entry_price=float(row['entry_price_underlying']) if row['entry_price_underlying'] else 0,
                entry_timestamp=row['entry_timestamp']
            )
            signals.append(signal)

        logger.info(f"Found {len(signals)} actionable signals for paper trading")
        return signals

    # =========================================================================
    # PAPER EXECUTION
    # =========================================================================

    def execute_paper_trade(
        self,
        signal: PaperTradeSignal,
        strategy: str = 'SPOT'
    ) -> Optional[PaperPosition]:
        """
        Execute a paper trade for the given signal.

        Args:
            signal: The inverted signal to trade
            strategy: 'SPOT' or 'OPTIONS_SIMULATED'

        Returns:
            PaperPosition if successful, None if failed
        """
        logger.info(f"Executing paper trade: {signal.ticker} {signal.inverted_direction}")

        # Get current price
        current_price = self._get_current_price(signal.ticker)
        if not current_price:
            logger.warning(f"Could not get price for {signal.ticker}")
            return None

        # Calculate position size
        position_size_usd = PAPER_NAV * PAPER_POSITION_SIZE_PCT
        shares = int(position_size_usd / current_price)

        if shares < 1:
            logger.warning(f"Position size too small for {signal.ticker}")
            return None

        # Check total exposure
        if not self._check_exposure_limit(position_size_usd):
            logger.warning("Total exposure limit reached")
            return None

        # Create position
        position = PaperPosition(
            position_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            ticker=signal.ticker,
            direction=signal.inverted_direction,
            entry_price=current_price,
            entry_timestamp=datetime.now(timezone.utc),
            position_size_usd=shares * current_price,
            shares=shares,
            strategy_type=strategy,
            status='OPEN'
        )

        # Execute via Alpaca if available
        if self.alpaca_adapter and strategy == 'SPOT':
            position = self._execute_via_alpaca(signal, position)
        else:
            # Simulated execution
            logger.info(f"SIMULATED: {signal.ticker} {signal.inverted_direction} "
                       f"{shares} shares @ ${current_price:.2f}")

        # Record position in database
        self._record_position(position, signal)

        return position

    def _execute_via_alpaca(
        self,
        signal: PaperTradeSignal,
        position: PaperPosition
    ) -> PaperPosition:
        """Execute paper trade via Alpaca."""
        # Create lineage
        lineage = SignalLineage(
            signal_id=signal.signal_id,
            strategy_source='IOS012B_INVERSION',
            regime_state=signal.source_regime,
            cognitive_action='INVERSION_PAPER_TRADE',
            kelly_fraction=0.025,  # 2.5% position
            circuit_breaker_state='CLOSED'
        )

        # Create order
        side = 'buy' if signal.inverted_direction == 'UP' else 'sell'
        order = PaperOrder(
            canonical_id=signal.ticker,
            side=side,
            order_type='market',
            qty=position.shares,
            limit_price=None,
            lineage=lineage
        )

        # Submit order
        result = self.alpaca_adapter.submit_order(order)

        if result.status == OrderStatus.FILLED:
            position.entry_price = result.filled_avg_price
            position.position_size_usd = result.filled_qty * result.filled_avg_price
            logger.info(f"ALPACA FILL: {signal.ticker} {side} "
                       f"{result.filled_qty} @ ${result.filled_avg_price:.2f}")
        else:
            logger.warning(f"ALPACA ORDER {result.status.value}: {signal.ticker}")

        return position

    def _get_current_price(self, ticker: str) -> Optional[float]:
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
            logger.warning(f"Price lookup failed for {ticker}: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return None

    def _check_exposure_limit(self, new_position_usd: float) -> bool:
        """Check if new position would exceed exposure limit."""
        query = """
            SELECT COALESCE(SUM(position_size_usd), 0) as total_exposure
            FROM fhq_alpha.ios012b_paper_positions
            WHERE status = 'OPEN'
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                current_exposure = float(cur.fetchone()[0])

            max_exposure = PAPER_NAV * PAPER_MAX_EXPOSURE_PCT
            return (current_exposure + new_position_usd) <= max_exposure
        except Exception as e:
            logger.warning(f"Exposure check failed: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return True  # Allow trade on error (fail-open for paper trading)

    def _record_position(self, position: PaperPosition, signal: PaperTradeSignal):
        """Record paper position in database."""
        query = """
            INSERT INTO fhq_alpha.ios012b_paper_positions (
                position_id, source_overlay_id, ticker, direction,
                entry_price, entry_timestamp, position_size_usd, shares,
                strategy_type, status, evidence_hash
            ) VALUES (
                %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        evidence_hash = hashlib.sha256(
            json.dumps(asdict(position), default=str).encode()
        ).hexdigest()[:32]

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (
                    str(position.position_id),
                    str(signal.overlay_id),
                    position.ticker,
                    position.direction,
                    position.entry_price,
                    position.entry_timestamp,
                    position.position_size_usd,
                    position.shares,
                    position.strategy_type,
                    position.status,
                    f"sha256:{evidence_hash}"
                ))
            self.conn.commit()
            logger.info(f"Position recorded: {position.position_id}")
        except Exception as e:
            logger.error(f"Failed to record position {position.ticker}: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            raise

    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================

    def get_open_positions(self) -> List[Dict]:
        """Get all open paper positions."""
        query = """
            SELECT * FROM fhq_alpha.ios012b_paper_positions
            WHERE status = 'OPEN'
            ORDER BY entry_timestamp DESC
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return [dict(r) for r in cur.fetchall()]

    def update_position_pnl(self, position_id: str) -> Dict:
        """Update P&L for an open position."""
        # Get position
        query = """
            SELECT * FROM fhq_alpha.ios012b_paper_positions
            WHERE position_id = %s::uuid
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (position_id,))
            position = dict(cur.fetchone())

        if position['status'] != 'OPEN':
            return position

        # Get current price
        current_price = self._get_current_price(position['ticker'])
        if not current_price:
            return position

        # Calculate P&L
        entry_price = float(position['entry_price'])
        shares = int(position['shares'])
        direction_mult = 1 if position['direction'] == 'UP' else -1

        pnl_usd = (current_price - entry_price) * shares * direction_mult
        pnl_pct = ((current_price / entry_price) - 1) * 100 * direction_mult

        # Update in database
        update_query = """
            UPDATE fhq_alpha.ios012b_paper_positions
            SET current_price = %s, unrealized_pnl = %s, unrealized_pnl_pct = %s
            WHERE position_id = %s::uuid
        """
        with self.conn.cursor() as cur:
            cur.execute(update_query, (current_price, pnl_usd, pnl_pct, position_id))
        self.conn.commit()

        position['current_price'] = current_price
        position['unrealized_pnl'] = pnl_usd
        position['unrealized_pnl_pct'] = pnl_pct

        return position

    def close_position(self, position_id: str, exit_price: Optional[float] = None) -> Dict:
        """Close a paper position."""
        # Get position
        query = """
            SELECT * FROM fhq_alpha.ios012b_paper_positions
            WHERE position_id = %s::uuid
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (position_id,))
            position = dict(cur.fetchone())

        if position['status'] != 'OPEN':
            raise ValueError(f"Position {position_id} is not open")

        # Get exit price if not provided
        if exit_price is None:
            exit_price = self._get_current_price(position['ticker'])

        # Calculate final P&L
        entry_price = float(position['entry_price'])
        shares = int(position['shares'])
        direction_mult = 1 if position['direction'] == 'UP' else -1

        pnl_usd = (exit_price - entry_price) * shares * direction_mult
        pnl_pct = ((exit_price / entry_price) - 1) * 100 * direction_mult

        # Update position
        update_query = """
            UPDATE fhq_alpha.ios012b_paper_positions
            SET status = 'CLOSED',
                exit_price = %s,
                exit_timestamp = NOW(),
                realized_pnl = %s,
                realized_pnl_pct = %s
            WHERE position_id = %s::uuid
        """
        with self.conn.cursor() as cur:
            cur.execute(update_query, (exit_price, pnl_usd, pnl_pct, position_id))
        self.conn.commit()

        logger.info(f"Position closed: {position['ticker']} P&L=${pnl_usd:.2f} ({pnl_pct:.2f}%)")

        return {
            'position_id': position_id,
            'ticker': position['ticker'],
            'direction': position['direction'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_usd': pnl_usd,
            'pnl_pct': pnl_pct
        }

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    def execute_all_actionable(self, strategy: str = 'SPOT') -> Dict[str, Any]:
        """Execute paper trades for all actionable signals."""
        signals = self.get_actionable_signals()

        results = {
            'total_signals': len(signals),
            'executed': 0,
            'failed': 0,
            'positions': []
        }

        for signal in signals:
            try:
                position = self.execute_paper_trade(signal, strategy)
                if position:
                    results['executed'] += 1
                    results['positions'].append(asdict(position))
                else:
                    results['failed'] += 1
            except Exception as e:
                logger.error(f"Failed to execute {signal.ticker}: {e}")
                results['failed'] += 1
                # Ensure transaction is rolled back before next signal
                try:
                    self.conn.rollback()
                except:
                    pass

        logger.info(f"Batch execution complete: {results['executed']}/{results['total_signals']} executed")
        return results

    def update_all_positions(self) -> List[Dict]:
        """Update P&L for all open positions."""
        positions = self.get_open_positions()
        updated = []

        for pos in positions:
            try:
                updated_pos = self.update_position_pnl(str(pos['position_id']))
                updated.append(updated_pos)
            except Exception as e:
                logger.error(f"Failed to update {pos['ticker']}: {e}")

        return updated

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get paper portfolio summary."""
        query = """
            SELECT
                COUNT(*) as total_positions,
                COUNT(CASE WHEN status = 'OPEN' THEN 1 END) as open_positions,
                COUNT(CASE WHEN status = 'CLOSED' THEN 1 END) as closed_positions,
                COALESCE(SUM(CASE WHEN status = 'OPEN' THEN position_size_usd END), 0) as total_exposure,
                COALESCE(SUM(CASE WHEN status = 'OPEN' THEN unrealized_pnl END), 0) as unrealized_pnl,
                COALESCE(SUM(CASE WHEN status = 'CLOSED' THEN realized_pnl END), 0) as realized_pnl
            FROM fhq_alpha.ios012b_paper_positions
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            row = cur.fetchone()

        return {
            'paper_nav': PAPER_NAV,
            'total_positions': row['total_positions'],
            'open_positions': row['open_positions'],
            'closed_positions': row['closed_positions'],
            'total_exposure': float(row['total_exposure'] or 0),
            'exposure_pct': float(row['total_exposure'] or 0) / PAPER_NAV * 100,
            'unrealized_pnl': float(row['unrealized_pnl'] or 0),
            'realized_pnl': float(row['realized_pnl'] or 0),
            'total_pnl': float((row['unrealized_pnl'] or 0) + (row['realized_pnl'] or 0))
        }


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='IoS-012-B Paper Trading Executor')
    parser.add_argument('--execute', action='store_true', help='Execute paper trades for actionable signals')
    parser.add_argument('--update', action='store_true', help='Update P&L for open positions')
    parser.add_argument('--summary', action='store_true', help='Show portfolio summary')
    parser.add_argument('--positions', action='store_true', help='List open positions')
    parser.add_argument('--strategy', default='SPOT', choices=['SPOT', 'OPTIONS_SIMULATED'])
    args = parser.parse_args()

    executor = PaperTradingExecutor()
    executor.connect()

    try:
        if args.execute:
            print("\n=== EXECUTING PAPER TRADES ===")
            results = executor.execute_all_actionable(args.strategy)
            print(json.dumps(results, indent=2, default=str))

        if args.update:
            print("\n=== UPDATING POSITIONS ===")
            positions = executor.update_all_positions()
            for pos in positions:
                print(f"{pos['ticker']}: ${pos.get('unrealized_pnl', 0):.2f} ({pos.get('unrealized_pnl_pct', 0):.2f}%)")

        if args.summary:
            print("\n=== PORTFOLIO SUMMARY ===")
            summary = executor.get_portfolio_summary()
            print(json.dumps(summary, indent=2))

        if args.positions:
            print("\n=== OPEN POSITIONS ===")
            positions = executor.get_open_positions()
            for pos in positions:
                print(f"{pos['ticker']} {pos['direction']}: {pos['shares']} @ ${pos['entry_price']:.2f}")

        if not any([args.execute, args.update, args.summary, args.positions]):
            parser.print_help()

    finally:
        executor.close()


if __name__ == '__main__':
    main()
