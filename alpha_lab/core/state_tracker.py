"""
Portfolio State Tracker for Alpha Lab.

Manages portfolio state during backtesting: cash, positions, equity, trades.
Provides pure, deterministic state management with full history tracking.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import copy

from alpha_lab.schemas import ExecutedTrade, TradeRecord, EquityPoint
from alpha_lab.utils import format_date


@dataclass
class Position:
    """Represents a position in a single symbol."""
    symbol: str
    quantity: float
    avg_entry_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class PortfolioState:
    """
    Complete state of the portfolio at a point in time.

    This is a pure data structure with no methods - all mutations
    happen through the PortfolioStateTracker.
    """
    timestamp: datetime
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    equity: float = 0.0
    peak_equity: float = 0.0
    drawdown: float = 0.0

    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value."""
        positions_value = sum(
            pos.quantity * current_prices.get(pos.symbol, pos.avg_entry_price)
            for pos in self.positions.values()
        )
        return self.cash + positions_value


class PortfolioStateTracker:
    """
    Tracks portfolio state through a backtest.

    Maintains:
    - Current cash and positions
    - Equity curve
    - Trade history
    - Drawdown tracking
    - Peak equity tracking
    """

    def __init__(
        self,
        initial_capital: float,
        start_date: datetime,
        currency: str = "USDT"
    ):
        """
        Initialize portfolio state tracker.

        Args:
            initial_capital: Starting cash
            start_date: Start date of backtest
            currency: Base currency
        """
        self.currency = currency
        self.initial_capital = initial_capital

        # Current state
        self.current_state = PortfolioState(
            timestamp=start_date,
            cash=initial_capital,
            positions={},
            equity=initial_capital,
            peak_equity=initial_capital,
            drawdown=0.0
        )

        # History
        self.equity_curve: List[EquityPoint] = []
        self.trade_history: List[TradeRecord] = []

        # Tracking
        self.total_commission_paid = 0.0
        self.total_slippage_paid = 0.0
        self.trade_counter = 0

        # For trade tracking (open trades)
        self.open_trades: Dict[str, List[Dict[str, Any]]] = {}

    def execute_trade(
        self,
        executed_trade: ExecutedTrade,
        current_prices: Dict[str, float]
    ) -> None:
        """
        Execute a trade and update portfolio state.

        Args:
            executed_trade: The executed trade
            current_prices: Current market prices for all symbols
        """
        symbol = executed_trade.symbol
        side = executed_trade.side
        quantity = executed_trade.quantity
        price = executed_trade.price

        # Update costs
        self.total_commission_paid += executed_trade.commission
        self.total_slippage_paid += executed_trade.slippage

        if side == "buy":
            # Deduct cash (price * quantity + commission)
            cost = price * quantity + executed_trade.commission
            self.current_state.cash -= cost

            # Update position
            if symbol in self.current_state.positions:
                pos = self.current_state.positions[symbol]
                # Update average entry price
                total_quantity = pos.quantity + quantity
                pos.avg_entry_price = (
                    (pos.avg_entry_price * pos.quantity + price * quantity) / total_quantity
                )
                pos.quantity = total_quantity
            else:
                # New position
                self.current_state.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    avg_entry_price=price
                )

            # Track open trade
            if symbol not in self.open_trades:
                self.open_trades[symbol] = []

            self.open_trades[symbol].append({
                'entry_date': executed_trade.timestamp,
                'entry_price': price,
                'quantity': quantity,
                'commission': executed_trade.commission,
            })

        elif side == "sell":
            # Add cash (price * quantity - commission)
            proceeds = price * quantity - executed_trade.commission
            self.current_state.cash += proceeds

            # Update position
            if symbol in self.current_state.positions:
                pos = self.current_state.positions[symbol]
                pos.quantity -= quantity

                # Close position if quantity is zero
                if abs(pos.quantity) < 1e-8:
                    del self.current_state.positions[symbol]

                # Record closed trade
                if symbol in self.open_trades and self.open_trades[symbol]:
                    # FIFO: close oldest trade first
                    remaining_qty = quantity
                    while remaining_qty > 0 and self.open_trades[symbol]:
                        open_trade = self.open_trades[symbol][0]
                        close_qty = min(remaining_qty, open_trade['quantity'])

                        # Calculate PnL
                        entry_price = open_trade['entry_price']
                        pnl = (price - entry_price) * close_qty
                        pnl_pct = (price - entry_price) / entry_price

                        # Create trade record
                        self.trade_counter += 1
                        trade_record = TradeRecord(
                            trade_id=f"trade_{self.trade_counter:06d}",
                            symbol=symbol,
                            side="long",
                            entry_date=format_date(open_trade['entry_date'], include_time=True),
                            entry_price=entry_price,
                            quantity=close_qty,
                            exit_date=format_date(executed_trade.timestamp, include_time=True),
                            exit_price=price,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            commission=open_trade['commission'] + (
                                executed_trade.commission * close_qty / quantity
                            ),
                            slippage=executed_trade.slippage * close_qty / quantity,
                            duration_hours=(
                                executed_trade.timestamp - open_trade['entry_date']
                            ).total_seconds() / 3600
                        )

                        self.trade_history.append(trade_record)

                        # Update open trade
                        open_trade['quantity'] -= close_qty
                        if open_trade['quantity'] < 1e-8:
                            self.open_trades[symbol].pop(0)

                        remaining_qty -= close_qty

        # Mark-to-market all positions
        self._mark_to_market(current_prices)

    def mark_to_market(
        self,
        current_prices: Dict[str, float],
        timestamp: datetime
    ) -> None:
        """
        Mark all positions to market and update equity.

        Args:
            current_prices: Current market prices
            timestamp: Current timestamp
        """
        self.current_state.timestamp = timestamp
        self._mark_to_market(current_prices)

    def _mark_to_market(self, current_prices: Dict[str, float]) -> None:
        """Internal mark-to-market implementation."""
        # Update position market values
        for symbol, pos in self.current_state.positions.items():
            current_price = current_prices.get(symbol, pos.avg_entry_price)
            pos.market_value = pos.quantity * current_price
            pos.unrealized_pnl = (current_price - pos.avg_entry_price) * pos.quantity

        # Calculate total equity
        positions_value = sum(pos.market_value for pos in self.current_state.positions.values())
        self.current_state.equity = self.current_state.cash + positions_value

        # Update peak and drawdown
        if self.current_state.equity > self.current_state.peak_equity:
            self.current_state.peak_equity = self.current_state.equity
            self.current_state.drawdown = 0.0
        else:
            self.current_state.drawdown = (
                self.current_state.equity - self.current_state.peak_equity
            ) / self.current_state.peak_equity

    def record_equity_point(self, daily_return: float = 0.0) -> None:
        """
        Record current equity as a point in the equity curve.

        Args:
            daily_return: Daily return (optional)
        """
        equity_point = EquityPoint(
            date=format_date(self.current_state.timestamp, include_time=True),
            equity=self.current_state.equity,
            drawdown=self.current_state.drawdown,
            daily_return=daily_return,
            cash=self.current_state.cash,
            positions_value=sum(
                pos.market_value for pos in self.current_state.positions.values()
            )
        )
        self.equity_curve.append(equity_point)

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for a symbol."""
        return self.current_state.positions.get(symbol)

    def get_position_quantity(self, symbol: str) -> float:
        """Get current position quantity for a symbol (0 if no position)."""
        pos = self.get_position(symbol)
        return pos.quantity if pos else 0.0

    def has_position(self, symbol: str) -> bool:
        """Check if we have a position in a symbol."""
        return symbol in self.current_state.positions

    def get_state_snapshot(self) -> PortfolioState:
        """Get a deep copy of current state."""
        return copy.deepcopy(self.current_state)

    def get_portfolio_dict(self) -> Dict[str, Any]:
        """
        Get portfolio state as dictionary (for passing to trade engine).

        Returns:
            Dictionary with cash, positions, equity, etc.
        """
        return {
            'cash': self.current_state.cash,
            'equity': self.current_state.equity,
            'positions': {
                symbol: pos.quantity
                for symbol, pos in self.current_state.positions.items()
            },
            'position_details': {
                symbol: {
                    'quantity': pos.quantity,
                    'avg_entry_price': pos.avg_entry_price,
                    'market_value': pos.market_value,
                    'unrealized_pnl': pos.unrealized_pnl,
                }
                for symbol, pos in self.current_state.positions.items()
            }
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of the portfolio."""
        return {
            'initial_capital': self.initial_capital,
            'final_equity': self.current_state.equity,
            'total_return': (self.current_state.equity - self.initial_capital) / self.initial_capital,
            'peak_equity': self.current_state.peak_equity,
            'max_drawdown': min(ep.drawdown for ep in self.equity_curve) if self.equity_curve else 0.0,
            'total_trades': len(self.trade_history),
            'total_commission': self.total_commission_paid,
            'total_slippage': self.total_slippage_paid,
            'open_positions': len(self.current_state.positions),
        }
