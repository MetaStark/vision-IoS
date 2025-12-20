#!/usr/bin/env python3
"""
TRADE MANAGEMENT SYSTEM
=======================
Directive: CD-IOS015-ALPACA-PAPER-001 + ADR-020 ACI Protocol
Classification: G4_EXECUTION_MANAGEMENT

CRITICAL FUNCTIONALITY:
1. Exit Strategy Management (Stop-Loss, Take-Profit, Trailing, Time-Based)
2. Capital Awareness (Alpaca Account Integration)
3. Position Sizing (Kelly + Capital-Based)
4. Position Monitoring (Real-time P&L tracking)
5. Learning Integration (EC-020, EC-021, EC-022)

Authority: CEO, STIG, VEGA
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor, Json

# =============================================================================
# UNIFIED EXECUTION GATEWAY (CEO DIRECTIVE 2025-12-20)
# =============================================================================
try:
    from unified_execution_gateway import (
        validate_execution_permission,
        validate_position_size as gateway_validate_size,
        PAPER_MODE_ENABLED,
        PAPER_MODE_MAX_EXPOSURE_PCT
    )
    GATEWAY_AVAILABLE = True
except ImportError:
    GATEWAY_AVAILABLE = False
    PAPER_MODE_ENABLED = True
    PAPER_MODE_MAX_EXPOSURE_PCT = 0.10

logging.basicConfig(
    level=logging.INFO,
    format='[TRADE-MGMT] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
# Support both ALPACA_SECRET and ALPACA_SECRET_KEY (common naming variations)
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '') or os.getenv('ALPACA_SECRET', '')


class ExitReason(Enum):
    """Reasons for exiting a position."""
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_BASED = "TIME_BASED"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    DEFCON_EXIT = "DEFCON_EXIT"
    MANUAL = "MANUAL"
    REGIME_CHANGE = "REGIME_CHANGE"


@dataclass
class ExitStrategy:
    """Exit strategy configuration for a position."""
    # Stop-Loss
    stop_loss_pct: float = 0.02  # 2% default stop-loss
    stop_loss_price: Optional[float] = None

    # Take-Profit
    take_profit_pct: float = 0.05  # 5% default take-profit
    take_profit_price: Optional[float] = None

    # Trailing Stop
    trailing_stop_enabled: bool = True
    trailing_stop_pct: float = 0.015  # 1.5% trailing
    trailing_high_water_mark: Optional[float] = None

    # Time-Based Exit
    max_hold_hours: int = 168  # 7 days default

    # Dynamic adjustments based on regime
    regime_adjustments: Dict[str, float] = field(default_factory=dict)

    def calculate_stop_loss_price(self, entry_price: float, side: str) -> float:
        """Calculate stop-loss price based on entry."""
        if side == 'long':
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return entry_price * (1 + self.stop_loss_pct)

    def calculate_take_profit_price(self, entry_price: float, side: str) -> float:
        """Calculate take-profit price based on entry."""
        if side == 'long':
            return entry_price * (1 + self.take_profit_pct)
        else:
            return entry_price * (1 - self.take_profit_pct)


@dataclass
class CapitalState:
    """Current capital state from Alpaca."""
    total_equity: Decimal
    cash: Decimal
    buying_power: Decimal
    portfolio_value: Decimal
    positions_count: int
    timestamp: datetime

    # Risk parameters (based on ADR-012)
    max_position_pct: float = 0.05  # Max 5% per position
    max_total_exposure_pct: float = 0.75  # Max 75% total exposure
    min_cash_pct: float = 0.25  # Min 25% cash reserve
    max_daily_risk_pct: float = 0.02  # Max 2% daily risk


@dataclass
class PositionState:
    """Current state of a position."""
    position_id: str
    canonical_id: str
    strategy_source: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    max_favorable_pnl_pct: float  # For trailing stop
    entry_time: datetime
    exit_strategy: ExitStrategy
    regime_at_entry: str


class TradeManagementSystem:
    """
    Comprehensive trade management with exit strategies and capital awareness.

    Integrates with:
    - ADR-020: ACI Protocol (cognitive intelligence)
    - EC-020: SitC (dynamic planning for exits)
    - EC-021: InForage (information gathering for regime changes)
    - EC-022: IKEA (knowledge boundary for exit decisions)
    """

    def __init__(self):
        self.conn = None
        self.trading_client = None
        self.data_client = None
        self.capital_state: Optional[CapitalState] = None
        self.positions: Dict[str, PositionState] = {}

    def connect(self):
        """Connect to database and Alpaca."""
        self.conn = psycopg2.connect(**DB_CONFIG)

        # Both API key AND secret key must be present
        if ALPACA_AVAILABLE and ALPACA_API_KEY and ALPACA_SECRET_KEY:
            try:
                self.trading_client = TradingClient(
                    api_key=ALPACA_API_KEY,
                    secret_key=ALPACA_SECRET_KEY,
                    paper=True
                )
                self.data_client = StockHistoricalDataClient(
                    api_key=ALPACA_API_KEY,
                    secret_key=ALPACA_SECRET_KEY
                )
                logger.info("Connected to Alpaca Paper Trading")

                # Load initial capital state
                self.refresh_capital_state()
            except Exception as e:
                logger.warning(f"Alpaca connection failed: {e} - using simulated capital")
                self._set_simulated_capital()
        else:
            logger.warning("Alpaca credentials not configured - using simulated capital ($200k)")
            self._set_simulated_capital()

        logger.info("Trade Management System connected")

    def close(self):
        """Close connections."""
        if self.conn:
            self.conn.close()

    # =========================================================================
    # CAPITAL AWARENESS
    # =========================================================================

    def refresh_capital_state(self):
        """Refresh capital state from Alpaca."""
        if not self.trading_client:
            self._set_simulated_capital()
            return

        try:
            account = self.trading_client.get_account()
            positions = self.trading_client.get_all_positions()

            self.capital_state = CapitalState(
                total_equity=Decimal(str(account.equity)),
                cash=Decimal(str(account.cash)),
                buying_power=Decimal(str(account.buying_power)),
                portfolio_value=Decimal(str(account.portfolio_value)),
                positions_count=len(positions),
                timestamp=datetime.now(timezone.utc)
            )

            logger.info(f"Capital: ${self.capital_state.total_equity:,.2f} | "
                       f"Cash: ${self.capital_state.cash:,.2f} | "
                       f"Positions: {self.capital_state.positions_count}")

        except Exception as e:
            logger.error(f"Failed to refresh capital: {e}")
            self._set_simulated_capital()

    def _set_simulated_capital(self, total: Decimal = Decimal('200000')):
        """Set simulated capital state."""
        self.capital_state = CapitalState(
            total_equity=total,
            cash=total * Decimal('0.80'),
            buying_power=total * Decimal('0.75'),
            portfolio_value=total,
            positions_count=0,
            timestamp=datetime.now(timezone.utc)
        )
        logger.info(f"Simulated capital: ${self.capital_state.total_equity:,.2f}")

    def get_available_capital(self) -> Decimal:
        """Get available capital for new positions."""
        if not self.capital_state:
            self.refresh_capital_state()
        return self.capital_state.buying_power

    # =========================================================================
    # POSITION SIZING (Capital-Based + Kelly)
    # =========================================================================

    def calculate_position_size(
        self,
        canonical_id: str,
        signal_confidence: float,
        current_price: float,
        kelly_fraction: float = 0.5
    ) -> Tuple[float, float]:
        """
        Calculate position size based on capital and Kelly criterion.

        Returns:
            (quantity, notional_usd)
            Returns (0, 0) if execution is not permitted by gateway
        """
        # =====================================================================
        # GATEWAY CHECK - MUST BE FIRST (CEO Directive 2025-12-20)
        # No sizing calculation before execution permission is granted
        # =====================================================================
        if GATEWAY_AVAILABLE:
            decision = validate_execution_permission(
                symbol=canonical_id,
                target_state='ACTIVE'
            )
            if not decision.allowed:
                logger.warning(f"SIZING BLOCKED: {canonical_id} - {decision.reason}")
                return 0, 0
            logger.info(f"SIZING PERMITTED: {canonical_id} ({decision.execution_scope})")

        if not self.capital_state:
            self.refresh_capital_state()

        total_equity = float(self.capital_state.total_equity)

        # Step 1: Base position size (% of equity)
        # Higher confidence = larger position, but capped
        confidence_factor = min(signal_confidence, 0.95)
        base_pct = self.capital_state.max_position_pct * confidence_factor

        # Step 2: Apply Kelly fraction
        # Kelly tells us optimal bet size based on edge
        kelly_adjusted_pct = base_pct * kelly_fraction

        # Step 3: Cap at max position size
        final_pct = min(kelly_adjusted_pct, self.capital_state.max_position_pct)

        # Step 4: Calculate notional value
        notional_usd = total_equity * final_pct

        # =====================================================================
        # PAPER MODE HARD CAP (CEO Directive 2025-12-20)
        # 10% max exposure per trade regardless of Kelly/confidence/regime
        # =====================================================================
        if GATEWAY_AVAILABLE and PAPER_MODE_ENABLED:
            capped_amount, cap_reason = gateway_validate_size(
                symbol=canonical_id,
                requested_size=notional_usd,
                account_equity=total_equity
            )
            if capped_amount < notional_usd:
                logger.warning(f"PAPER CAP APPLIED: {canonical_id} ${notional_usd:.2f} -> ${capped_amount:.2f}")
                notional_usd = capped_amount
        elif PAPER_MODE_ENABLED:
            # Fallback cap if gateway not available
            max_allowed = total_equity * PAPER_MODE_MAX_EXPOSURE_PCT
            if notional_usd > max_allowed:
                logger.warning(f"PAPER CAP (fallback): {canonical_id} ${notional_usd:.2f} -> ${max_allowed:.2f}")
                notional_usd = max_allowed

        # Step 5: Calculate quantity
        quantity = notional_usd / current_price

        # Round to reasonable precision
        if current_price > 100:
            quantity = round(quantity, 2)
        else:
            quantity = round(quantity, 4)

        logger.info(f"Position size for {canonical_id}: "
                   f"${notional_usd:,.2f} ({final_pct*100:.1f}% of equity) = {quantity} units")

        return quantity, notional_usd

    # =========================================================================
    # EXIT STRATEGY MANAGEMENT
    # =========================================================================

    def create_exit_strategy(
        self,
        entry_price: float,
        side: str,
        regime: str,
        signal_confidence: float
    ) -> ExitStrategy:
        """
        Create exit strategy based on entry parameters and market regime.

        Regime adjustments per ADR-020 ACI Protocol:
        - HIGH_VOLATILITY: Wider stops, faster take-profit
        - LOW_VOLATILITY: Tighter stops, longer hold times
        - TRENDING: Trail more aggressively
        - RANGE_BOUND: Tighter take-profit
        """
        strategy = ExitStrategy()

        # Adjust based on regime
        if regime in ('HIGH_VOLATILITY', 'VOLATILE'):
            strategy.stop_loss_pct = 0.03  # 3% stop in volatile markets
            strategy.take_profit_pct = 0.04  # 4% take-profit (faster exit)
            strategy.trailing_stop_pct = 0.025  # 2.5% trail
            strategy.max_hold_hours = 72  # 3 days max

        elif regime in ('LOW_VOLATILITY', 'QUIET'):
            strategy.stop_loss_pct = 0.015  # 1.5% tight stop
            strategy.take_profit_pct = 0.03  # 3% take-profit
            strategy.trailing_stop_pct = 0.01  # 1% tight trail
            strategy.max_hold_hours = 336  # 14 days

        elif regime in ('STRONG_TREND', 'BULLISH_TRENDING', 'BEARISH_TRENDING'):
            strategy.stop_loss_pct = 0.025  # 2.5% stop
            strategy.take_profit_pct = 0.08  # 8% let profits run
            strategy.trailing_stop_pct = 0.02  # 2% trail
            strategy.max_hold_hours = 168  # 7 days

        elif regime in ('RANGE_BOUND', 'NEUTRAL'):
            strategy.stop_loss_pct = 0.015  # 1.5% tight stop
            strategy.take_profit_pct = 0.025  # 2.5% quick profit
            strategy.trailing_stop_pct = 0.01  # 1% tight trail
            strategy.max_hold_hours = 48  # 2 days

        # Adjust for confidence
        if signal_confidence > 0.8:
            strategy.take_profit_pct *= 1.2  # Let winners run longer
        elif signal_confidence < 0.5:
            strategy.stop_loss_pct *= 0.8  # Tighter stop for low confidence

        # Calculate actual price levels
        strategy.stop_loss_price = strategy.calculate_stop_loss_price(entry_price, side)
        strategy.take_profit_price = strategy.calculate_take_profit_price(entry_price, side)
        strategy.trailing_high_water_mark = entry_price

        logger.info(f"Exit strategy created: "
                   f"SL={strategy.stop_loss_price:.2f} ({strategy.stop_loss_pct*100:.1f}%) | "
                   f"TP={strategy.take_profit_price:.2f} ({strategy.take_profit_pct*100:.1f}%) | "
                   f"Trail={strategy.trailing_stop_pct*100:.1f}%")

        return strategy

    def check_exit_conditions(self, position: PositionState) -> Tuple[bool, Optional[ExitReason]]:
        """
        Check if position should be exited.

        Returns:
            (should_exit, reason)
        """
        current_price = position.current_price
        entry_price = position.entry_price
        strategy = position.exit_strategy
        side = position.side

        # Calculate current PnL
        if side == 'long':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price

        # Update max favorable for trailing stop
        if pnl_pct > position.max_favorable_pnl_pct:
            position.max_favorable_pnl_pct = pnl_pct
            if strategy.trailing_stop_enabled:
                # Update trailing high water mark
                if side == 'long':
                    strategy.trailing_high_water_mark = max(
                        strategy.trailing_high_water_mark or entry_price,
                        current_price
                    )
                else:
                    strategy.trailing_high_water_mark = min(
                        strategy.trailing_high_water_mark or entry_price,
                        current_price
                    )

        # Check 1: Stop-Loss
        if side == 'long' and current_price <= strategy.stop_loss_price:
            return True, ExitReason.STOP_LOSS
        if side == 'short' and current_price >= strategy.stop_loss_price:
            return True, ExitReason.STOP_LOSS

        # Check 2: Take-Profit
        if side == 'long' and current_price >= strategy.take_profit_price:
            return True, ExitReason.TAKE_PROFIT
        if side == 'short' and current_price <= strategy.take_profit_price:
            return True, ExitReason.TAKE_PROFIT

        # Check 3: Trailing Stop
        if strategy.trailing_stop_enabled and strategy.trailing_high_water_mark:
            if side == 'long':
                trailing_stop_price = strategy.trailing_high_water_mark * (1 - strategy.trailing_stop_pct)
                if current_price <= trailing_stop_price:
                    return True, ExitReason.TRAILING_STOP
            else:
                trailing_stop_price = strategy.trailing_high_water_mark * (1 + strategy.trailing_stop_pct)
                if current_price >= trailing_stop_price:
                    return True, ExitReason.TRAILING_STOP

        # Check 4: Time-Based Exit
        time_in_position = datetime.now(timezone.utc) - position.entry_time.replace(tzinfo=timezone.utc)
        if time_in_position.total_seconds() / 3600 >= strategy.max_hold_hours:
            return True, ExitReason.TIME_BASED

        return False, None

    # =========================================================================
    # POSITION MONITORING
    # =========================================================================

    def load_open_positions(self):
        """Load all open positions from database."""
        sql = """
            SELECT
                position_id::text,
                symbol as canonical_id,
                'IOS015' as strategy_source,
                CASE WHEN quantity > 0 THEN 'long' ELSE 'short' END as side,
                ABS(quantity) as quantity,
                avg_entry_price as entry_price,
                COALESCE(current_price, avg_entry_price) as current_price,
                COALESCE(unrealized_pnl_usd, 0) as unrealized_pnl,
                opened_at as entry_time
            FROM fhq_execution.paper_positions
            WHERE quantity != 0
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()

            for row in rows:
                entry_price = float(row['entry_price'])
                current_price = float(row['current_price'])

                # Calculate PnL %
                if row['side'] == 'long':
                    pnl_pct = (current_price - entry_price) / entry_price * 100
                else:
                    pnl_pct = (entry_price - current_price) / entry_price * 100

                # Create exit strategy (use defaults since we don't have regime info)
                exit_strategy = self.create_exit_strategy(
                    entry_price=entry_price,
                    side=row['side'],
                    regime='RANGE_BOUND',  # Conservative default
                    signal_confidence=0.5
                )

                self.positions[row['position_id']] = PositionState(
                    position_id=row['position_id'],
                    canonical_id=row['canonical_id'],
                    strategy_source=row['strategy_source'],
                    side=row['side'],
                    quantity=float(row['quantity']),
                    entry_price=entry_price,
                    current_price=current_price,
                    unrealized_pnl=float(row['unrealized_pnl']),
                    unrealized_pnl_pct=pnl_pct,
                    max_favorable_pnl_pct=max(pnl_pct, 0),
                    entry_time=row['entry_time'],
                    exit_strategy=exit_strategy,
                    regime_at_entry='UNKNOWN'
                )

            logger.info(f"Loaded {len(self.positions)} open positions")

        except Exception as e:
            logger.error(f"Failed to load positions: {e}")

    def update_position_prices(self):
        """Update current prices for all positions."""
        if not self.positions:
            return

        for pos_id, position in self.positions.items():
            try:
                # Try to get current price from Alpaca
                if self.data_client:
                    try:
                        request = StockLatestQuoteRequest(symbol_or_symbols=position.canonical_id)
                        quote = self.data_client.get_stock_latest_quote(request)
                        if position.canonical_id in quote:
                            position.current_price = float(quote[position.canonical_id].ask_price)
                    except:
                        pass

                # Fallback to database
                if position.current_price == position.entry_price:
                    with self.conn.cursor() as cur:
                        cur.execute("""
                            SELECT close FROM fhq_data.price_series
                            WHERE listing_id = %s
                            ORDER BY date DESC LIMIT 1
                        """, (position.canonical_id,))
                        row = cur.fetchone()
                        if row:
                            position.current_price = float(row[0])

                # Update P&L
                if position.side == 'long':
                    position.unrealized_pnl = (position.current_price - position.entry_price) * position.quantity
                    position.unrealized_pnl_pct = (position.current_price - position.entry_price) / position.entry_price * 100
                else:
                    position.unrealized_pnl = (position.entry_price - position.current_price) * position.quantity
                    position.unrealized_pnl_pct = (position.entry_price - position.current_price) / position.entry_price * 100

            except Exception as e:
                logger.warning(f"Failed to update price for {position.canonical_id}: {e}")

    def scan_for_exits(self) -> List[Dict]:
        """Scan all positions for exit conditions."""
        self.update_position_prices()

        exits_triggered = []

        for pos_id, position in self.positions.items():
            should_exit, reason = self.check_exit_conditions(position)

            if should_exit:
                exits_triggered.append({
                    'position_id': pos_id,
                    'canonical_id': position.canonical_id,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'exit_price': position.current_price,
                    'unrealized_pnl': position.unrealized_pnl,
                    'unrealized_pnl_pct': position.unrealized_pnl_pct,
                    'exit_reason': reason.value,
                    'strategy': position.strategy_source
                })

                logger.info(f"EXIT TRIGGERED: {position.canonical_id} | "
                           f"Reason: {reason.value} | "
                           f"PnL: ${position.unrealized_pnl:.2f} ({position.unrealized_pnl_pct:.2f}%)")

        return exits_triggered

    # =========================================================================
    # REPORTING
    # =========================================================================

    def get_portfolio_summary(self) -> Dict:
        """Get comprehensive portfolio summary."""
        if not self.capital_state:
            self.refresh_capital_state()

        self.load_open_positions()
        self.update_position_prices()

        total_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        total_exposure = sum(p.quantity * p.current_price for p in self.positions.values())

        return {
            'capital': {
                'total_equity': float(self.capital_state.total_equity),
                'cash': float(self.capital_state.cash),
                'buying_power': float(self.capital_state.buying_power),
                'positions_count': len(self.positions)
            },
            'positions': {
                pos_id: {
                    'symbol': p.canonical_id,
                    'side': p.side,
                    'quantity': p.quantity,
                    'entry_price': p.entry_price,
                    'current_price': p.current_price,
                    'unrealized_pnl': p.unrealized_pnl,
                    'unrealized_pnl_pct': p.unrealized_pnl_pct,
                    'stop_loss': p.exit_strategy.stop_loss_price,
                    'take_profit': p.exit_strategy.take_profit_price
                }
                for pos_id, p in self.positions.items()
            },
            'totals': {
                'total_unrealized_pnl': total_pnl,
                'total_exposure': total_exposure,
                'exposure_pct': total_exposure / float(self.capital_state.total_equity) * 100 if self.capital_state.total_equity else 0
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_trade_manager() -> TradeManagementSystem:
    """Factory function to get configured trade manager."""
    manager = TradeManagementSystem()
    manager.connect()
    return manager


# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Trade Management System')
    parser.add_argument('--summary', action='store_true', help='Show portfolio summary')
    parser.add_argument('--exits', action='store_true', help='Scan for exit conditions')
    parser.add_argument('--capital', action='store_true', help='Show capital state')
    args = parser.parse_args()

    manager = get_trade_manager()

    if args.summary:
        summary = manager.get_portfolio_summary()
        print(json.dumps(summary, indent=2, default=str))
    elif args.exits:
        manager.load_open_positions()
        exits = manager.scan_for_exits()
        print(f"Exits triggered: {len(exits)}")
        for e in exits:
            print(f"  {e['canonical_id']}: {e['exit_reason']} -> ${e['unrealized_pnl']:.2f}")
    elif args.capital:
        print(f"Total Equity: ${manager.capital_state.total_equity:,.2f}")
        print(f"Cash: ${manager.capital_state.cash:,.2f}")
        print(f"Buying Power: ${manager.capital_state.buying_power:,.2f}")
        print(f"Max Position Size: {manager.capital_state.max_position_pct*100}% = ${float(manager.capital_state.total_equity) * manager.capital_state.max_position_pct:,.2f}")
    else:
        print("Trade Management System")
        print(f"  Alpaca Available: {ALPACA_AVAILABLE}")
        print(f"  Capital: ${manager.capital_state.total_equity:,.2f}" if manager.capital_state else "  Capital: Not loaded")

    manager.close()
