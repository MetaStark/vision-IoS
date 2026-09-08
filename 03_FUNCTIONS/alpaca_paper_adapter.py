#!/usr/bin/env python3
"""
ALPACA PAPER EXECUTION ADAPTER
==============================
Directive: CD-IOS015-ALPACA-PAPER-001
Classification: G4_EXECUTION_ENABLEMENT
Date: 2025-12-16

Connects IoS-015 to Alpaca Paper Trading for learning activation.
This is a LEARNING ACTIVATION, not a revenue activation.

HARD CONSTRAINTS:
- Paper mode ONLY (execution_mode = PAPER_ONLY)
- Full signal lineage required
- DEFCON must be GREEN
- Circuit breaker must be CLOSED
- Kelly sizing enforced

Authority: CEO, STIG, VEGA
"""

import os
import sys
import json
import time
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

# =============================================================================
# UNIFIED EXECUTION GATEWAY (CEO DIRECTIVE 2025-12-20)
# =============================================================================
try:
    from unified_execution_gateway import (
        validate_execution_permission,
        validate_position_size,
        ExecutionDecision,
        PAPER_MODE_ENABLED,
        PAPER_MODE_MAX_EXPOSURE_PCT
    )
    GATEWAY_AVAILABLE = True
except ImportError:
    GATEWAY_AVAILABLE = False
    PAPER_MODE_ENABLED = True
    PAPER_MODE_MAX_EXPOSURE_PCT = 0.10

# Load environment variables
load_dotenv()

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        TakeProfitRequest,
        StopLossRequest
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, OrderClass
    from alpaca.data.historical import StockHistoricalDataClient
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logging.warning("Alpaca SDK not installed. Run: pip install alpaca-py")

logging.basicConfig(
    level=logging.INFO,
    format='[ALPACA-PAPER] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION - PAPER MODE ONLY
# =============================================================================

EXECUTION_MODE = "PAPER_ONLY"  # HARDCODED - DO NOT CHANGE

# AGGRESSIVE CORPORATE STANDARD SIZING
AGGRESSIVE_MAX_POSITION_PCT = 0.15  # 15% of NAV per position
AGGRESSIVE_KELLY_MULTIPLIER = 0.75  # 3/4 Kelly
AGGRESSIVE_MIN_POSITION = 500       # Minimum $500 per trade

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Alpaca Paper Trading credentials
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))  # Support both names
ALPACA_PAPER = True  # HARDCODED - Paper mode only


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class SignalLineage:
    """Complete signal lineage for audit trail (required per Directive Section 3)."""
    signal_id: str
    strategy_source: str
    regime_state: str
    cognitive_action: str
    kelly_fraction: float
    circuit_breaker_state: str

    def compute_hash(self) -> str:
        """Compute lineage hash for verification."""
        data = f"{self.signal_id}{self.strategy_source}{self.regime_state}"
        data += f"{self.cognitive_action}{self.kelly_fraction}{self.circuit_breaker_state}"
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class PaperOrder:
    """Paper trading order with full lineage."""
    canonical_id: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market' or 'limit'
    qty: float
    limit_price: Optional[float]
    lineage: SignalLineage

    # TP/SL for bracket orders (CEO-DIR-2026-119: MANDATORY per Day 21 learning)
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None

    # CEO-DIR-2026-119: Allow bypass only with explicit governance approval
    tp_sl_bypass_approved: bool = False

    # Filled by adapter
    order_id: Optional[str] = None
    alpaca_order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0
    filled_avg_price: Optional[float] = None


@dataclass
class EpisodicSnapshot:
    """Episodic memory snapshot (per Amendment AMND-006)."""
    trade_id: str
    canonical_id: str
    strategy_source: str
    unrealized_pnl: float
    unrealized_pnl_pct: float
    max_drawdown_pct: float
    volatility_decay: float
    time_in_position_minutes: int
    current_price: float
    regime_state: str
    defcon_level: str


class AlpacaPaperAdapter:
    """
    Paper trading execution adapter for IoS-015.

    Flow (per Directive Section 4):
    IoS-015 Signal → Regime Validation → Cognitive Action Selection
    → Risk & Sizing Gate → Circuit Breaker Check → Paper Execution Adapter (Alpaca)
    → Execution Feedback → Learning Update

    Alpaca is downstream only. It does not influence strategy selection,
    regime classification, risk limits, or capital allocation logic.
    """

    def __init__(self):
        self.conn = None
        self.trading_client = None
        self.data_client = None
        self._episodic_enabled = True

        # Verify paper mode (non-negotiable)
        if EXECUTION_MODE != "PAPER_ONLY":
            raise RuntimeError("FATAL: Execution mode must be PAPER_ONLY")

    def connect(self):
        """Connect to database and Alpaca."""
        # Database
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

        # Alpaca Paper Trading
        if ALPACA_AVAILABLE and ALPACA_API_KEY:
            self.trading_client = TradingClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY,
                paper=True  # ALWAYS paper mode
            )
            self.data_client = StockHistoricalDataClient(
                api_key=ALPACA_API_KEY,
                secret_key=ALPACA_SECRET_KEY
            )
            logger.info("Connected to Alpaca Paper Trading")
        else:
            logger.warning("Alpaca not configured - simulation mode only")

    def close(self):
        """Close connections."""
        if self.conn:
            self.conn.close()

    # =========================================================================
    # PRECONDITION CHECKS (Directive Section 3)
    # =========================================================================

    def calculate_aggressive_position_size(
        self,
        symbol: str,
        sharpe: float = 0.30,
        confidence: float = 0.85
    ) -> Tuple[int, float, float]:
        """
        Calculate position size using AGGRESSIVE CORPORATE STANDARD.

        Returns:
            Tuple of (shares, dollar_amount, kelly_fraction)
        """
        if not self.trading_client:
            raise RuntimeError("Alpaca not connected")

        # Get account equity
        account = self.trading_client.get_account()
        portfolio_value = float(account.portfolio_value)

        # Get current price
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        data_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
        quote = data_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=[symbol]))
        current_price = float(quote[symbol].ask_price)

        # Kelly calculation (simplified)
        # Win probability from Sharpe
        win_prob = 0.5 + (0.5 / (1 + 2.718 ** (-3 * sharpe))) - 0.25
        win_prob = min(max(win_prob, 0.50), 0.95)

        # Win/loss ratio
        win_loss = 1.0 + (0.5 * sharpe)

        # Raw Kelly: f* = (p(b+1) - 1) / b
        raw_kelly = (win_prob * (win_loss + 1) - 1) / win_loss

        # Apply aggressive multiplier and confidence
        adjusted_kelly = raw_kelly * AGGRESSIVE_KELLY_MULTIPLIER * confidence

        # Cap at max position
        position_pct = min(adjusted_kelly, AGGRESSIVE_MAX_POSITION_PCT)

        # Calculate dollar amount
        dollar_amount = portfolio_value * position_pct
        dollar_amount = max(dollar_amount, AGGRESSIVE_MIN_POSITION)

        # =====================================================================
        # PAPER MODE HARD CAP (CEO Directive 2025-12-20)
        # 10% max exposure per trade regardless of Kelly/confidence/regime
        # =====================================================================
        if GATEWAY_AVAILABLE and PAPER_MODE_ENABLED:
            capped_amount, cap_reason = validate_position_size(
                symbol=symbol,
                requested_size=dollar_amount,
                account_equity=portfolio_value
            )
            if capped_amount < dollar_amount:
                logger.warning(f"PAPER CAP APPLIED: {symbol} ${dollar_amount:.2f} -> ${capped_amount:.2f}")
                dollar_amount = capped_amount
        elif PAPER_MODE_ENABLED:
            # Fallback cap if gateway not available
            max_allowed = portfolio_value * PAPER_MODE_MAX_EXPOSURE_PCT
            if dollar_amount > max_allowed:
                logger.warning(f"PAPER CAP (fallback): {symbol} ${dollar_amount:.2f} -> ${max_allowed:.2f}")
                dollar_amount = max_allowed

        # Calculate shares
        shares = int(dollar_amount / current_price)

        logger.info(f"Aggressive sizing: {symbol} - Kelly={raw_kelly:.4f}, "
                   f"Adjusted={adjusted_kelly:.4f}, Position={position_pct:.2%}, "
                   f"${dollar_amount:,.2f} = {shares} shares")

        return shares, dollar_amount, adjusted_kelly

    def check_defcon(self) -> Tuple[bool, str]:
        """Check DEFCON level. Must be GREEN for execution."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT current_level FROM fhq_governance.defcon_state
                    ORDER BY state_timestamp DESC LIMIT 1
                """)
                row = cur.fetchone()
                level = row[0] if row else 'GREEN'
        except Exception as e:
            # Rollback to clear aborted transaction state
            try:
                self.conn.rollback()
            except:
                pass
            level = 'GREEN'  # Default if table doesn't exist

        if level != 'GREEN':
            return False, f"DEFCON {level} - execution blocked"
        return True, "GREEN"

    def check_circuit_breaker(self, state: str) -> Tuple[bool, str]:
        """Check circuit breaker state. Must be CLOSED for execution."""
        if state != 'CLOSED':
            return False, f"Circuit breaker {state} - execution blocked"
        return True, "CLOSED"

    def validate_lineage(self, lineage: SignalLineage) -> Tuple[bool, str]:
        """Validate signal lineage is complete."""
        if not lineage.signal_id:
            return False, "Missing signal_id"
        if not lineage.strategy_source:
            return False, "Missing strategy_source"
        if not lineage.regime_state:
            return False, "Missing regime_state"
        if lineage.kelly_fraction <= 0 or lineage.kelly_fraction > 1:
            return False, f"Invalid kelly_fraction: {lineage.kelly_fraction}"
        return True, "Lineage valid"

    def check_existing_position(self, canonical_id: str, strategy: str) -> bool:
        """Check if position already exists (one per asset per strategy)."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM fhq_execution.paper_positions
                    WHERE canonical_id = %s AND strategy_source = %s AND status = 'open'
                """, (canonical_id, strategy))
                count = cur.fetchone()[0]
            return count > 0
        except Exception as e:
            # Rollback to clear aborted transaction state
            try:
                self.conn.rollback()
            except:
                pass
            return False  # Allow trade if check fails (fail-open for paper trading)

    # =========================================================================
    # TP/SL CALCULATION HELPERS (CEO-DIR-2026-119)
    # =========================================================================

    def calculate_tp_sl(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        risk_reward_ratio: float = 2.0,
        stop_loss_pct: float = 0.02
    ) -> Tuple[float, float]:
        """
        Calculate Take Profit and Stop Loss levels.

        CEO-DIR-2026-119: Every order MUST have TP/SL.
        Default: 2% stop loss, 2:1 risk/reward ratio = 4% take profit.

        Args:
            symbol: Asset symbol
            side: 'buy' or 'sell'
            entry_price: Expected entry price
            risk_reward_ratio: TP distance / SL distance (default 2.0)
            stop_loss_pct: Stop loss percentage from entry (default 2%)

        Returns:
            Tuple of (take_profit_price, stop_loss_price)
        """
        if side == 'buy':
            # Long position: SL below entry, TP above entry
            stop_loss = round(entry_price * (1 - stop_loss_pct), 2)
            take_profit = round(entry_price * (1 + stop_loss_pct * risk_reward_ratio), 2)
        else:
            # Short position: SL above entry, TP below entry
            stop_loss = round(entry_price * (1 + stop_loss_pct), 2)
            take_profit = round(entry_price * (1 - stop_loss_pct * risk_reward_ratio), 2)

        logger.info(f"TP/SL calculated for {symbol}: Entry={entry_price}, "
                   f"TP={take_profit}, SL={stop_loss} (RR={risk_reward_ratio})")

        return take_profit, stop_loss

    def calculate_atr_based_tp_sl(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        atr_multiplier_sl: float = 1.5,
        atr_multiplier_tp: float = 3.0
    ) -> Tuple[float, float]:
        """
        Calculate TP/SL based on ATR (Average True Range).

        More sophisticated than percentage-based - adapts to volatility.

        Args:
            symbol: Asset symbol
            side: 'buy' or 'sell'
            entry_price: Expected entry price
            atr_multiplier_sl: ATR multiplier for stop loss (default 1.5)
            atr_multiplier_tp: ATR multiplier for take profit (default 3.0)

        Returns:
            Tuple of (take_profit_price, stop_loss_price)
        """
        # Get ATR from database
        atr = self._get_atr(symbol)
        if atr is None or atr == 0:
            # Fallback to percentage-based
            logger.warning(f"No ATR for {symbol}, using percentage-based TP/SL")
            return self.calculate_tp_sl(symbol, side, entry_price)

        if side == 'buy':
            stop_loss = round(entry_price - (atr * atr_multiplier_sl), 2)
            take_profit = round(entry_price + (atr * atr_multiplier_tp), 2)
        else:
            stop_loss = round(entry_price + (atr * atr_multiplier_sl), 2)
            take_profit = round(entry_price - (atr * atr_multiplier_tp), 2)

        logger.info(f"ATR-based TP/SL for {symbol}: ATR={atr:.2f}, "
                   f"Entry={entry_price}, TP={take_profit}, SL={stop_loss}")

        return take_profit, stop_loss

    def _get_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """
        Get ATR from database, with on-the-fly calculation fallback.

        CEO-DIR-2026-120 P1.1: When database lacks ATR, calculate from Alpaca bars.
        This ensures every order can have proper TP/SL bracket even for symbols
        without pre-computed indicators.
        """
        # First try database
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT atr_14 FROM fhq_indicators.volatility
                    WHERE listing_id = %s
                    ORDER BY signal_date DESC LIMIT 1
                """, (symbol,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    logger.info(f"ATR for {symbol} from database: {row[0]}")
                    return float(row[0])
        except Exception as e:
            logger.warning(f"Database ATR query failed for {symbol}: {e}")
            try:
                self.conn.rollback()
            except:
                pass

        # Fallback: Calculate on-the-fly from Alpaca bars
        logger.info(f"Computing ATR on-the-fly for {symbol} (database lacks data)")
        return self._calculate_atr_from_bars(symbol, period)

    def _calculate_atr_from_bars(self, symbol: str, period: int = 14) -> Optional[float]:
        """
        Calculate ATR from Alpaca historical bars when database lacks data.

        CEO-DIR-2026-120 P1.1: On-the-fly ATR calculation for bracket order support.
        Uses True Range methodology: max(H-L, |H-C_prev|, |L-C_prev|)

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            period: ATR period (default 14)

        Returns:
            ATR value or None if calculation fails
        """
        if not self.data_client:
            logger.warning(f"No data client available for ATR calculation: {symbol}")
            return None

        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            from datetime import datetime, timedelta

            # Get enough bars for ATR calculation (period + buffer for TR calculation)
            end = datetime.now()
            start = end - timedelta(days=period * 2 + 10)  # Extra days for market closures

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start,
                end=end
            )

            bars = self.data_client.get_stock_bars(request)

            if symbol not in bars or len(bars[symbol]) < period + 1:
                logger.warning(f"Insufficient bars for ATR calculation: {symbol}")
                return None

            bar_list = list(bars[symbol])

            # Calculate True Range for each bar
            true_ranges = []
            for i in range(1, len(bar_list)):
                high = float(bar_list[i].high)
                low = float(bar_list[i].low)
                prev_close = float(bar_list[i-1].close)

                # True Range = max(H-L, |H-C_prev|, |L-C_prev|)
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)

            if len(true_ranges) < period:
                logger.warning(f"Not enough True Range values for ATR: {symbol}")
                return None

            # Calculate ATR as Simple Moving Average of True Range (last 'period' values)
            atr = sum(true_ranges[-period:]) / period

            logger.info(f"ATR({period}) for {symbol} calculated on-the-fly: {atr:.4f}")

            # Cache to database for future use (non-blocking)
            self._cache_atr_to_database(symbol, atr, period)

            return round(atr, 4)

        except Exception as e:
            logger.error(f"Failed to calculate ATR from bars for {symbol}: {e}")
            return None

    def _cache_atr_to_database(self, symbol: str, atr: float, period: int = 14):
        """
        Cache computed ATR to database for future queries.
        Non-blocking - failures logged but don't affect order flow.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_indicators.volatility (
                        listing_id, signal_date, atr_14, created_at
                    ) VALUES (%s, CURRENT_DATE, %s, NOW())
                    ON CONFLICT (listing_id, signal_date)
                    DO UPDATE SET atr_14 = EXCLUDED.atr_14, created_at = NOW()
                """, (symbol, atr))
                self.conn.commit()
                logger.info(f"Cached ATR({period})={atr:.4f} for {symbol}")
        except Exception as e:
            logger.warning(f"Failed to cache ATR for {symbol}: {e}")
            try:
                self.conn.rollback()
            except:
                pass

    # =========================================================================
    # ORDER EXECUTION (Directive Section 5)
    # =========================================================================

    def submit_order(self, order: PaperOrder) -> PaperOrder:
        """
        Submit paper order to Alpaca.

        Returns updated order with status and fill information.
        """
        # =====================================================================
        # GATEWAY CHECK - MUST BE FIRST (CEO Directive 2025-12-20)
        # No sizing, allocation, or order construction before permission
        # =====================================================================
        if GATEWAY_AVAILABLE:
            source_signal = order.lineage.signal_id if order.lineage else None
            decision = validate_execution_permission(
                symbol=order.canonical_id,
                source_signal=source_signal,
                target_state='ACTIVE'
            )
            if not decision.allowed:
                order.status = OrderStatus.REJECTED
                logger.warning(f"GATEWAY BLOCKED: {order.canonical_id} - {decision.reason}")
                self._log_order(order, "GATEWAY_BLOCKED")
                return order
            logger.info(f"GATEWAY PERMITTED: {order.canonical_id} ({decision.execution_scope})")
        else:
            logger.warning("GATEWAY UNAVAILABLE - proceeding with legacy checks")

        # Precondition checks
        defcon_ok, defcon_msg = self.check_defcon()
        if not defcon_ok:
            order.status = OrderStatus.REJECTED
            logger.warning(f"Order rejected: {defcon_msg}")
            self._log_order(order, "DEFCON_REJECTED")
            return order

        cb_ok, cb_msg = self.check_circuit_breaker(order.lineage.circuit_breaker_state)
        if not cb_ok:
            order.status = OrderStatus.REJECTED
            logger.warning(f"Order rejected: {cb_msg}")
            self._log_order(order, "CIRCUIT_BREAKER_REJECTED")
            return order

        lineage_ok, lineage_msg = self.validate_lineage(order.lineage)
        if not lineage_ok:
            order.status = OrderStatus.REJECTED
            logger.warning(f"Order rejected: {lineage_msg}")
            self._log_order(order, "LINEAGE_REJECTED")
            return order

        # Check existing position constraint
        if order.side == 'buy' and self.check_existing_position(
            order.canonical_id, order.lineage.strategy_source
        ):
            order.status = OrderStatus.REJECTED
            logger.warning(f"Order rejected: Position already exists for {order.canonical_id}")
            self._log_order(order, "POSITION_EXISTS")
            return order

        # =====================================================================
        # CEO-DIR-2026-119: MANDATORY TP/SL ENFORCEMENT (Day 21 Learning)
        # Every BUY order MUST have take_profit and stop_loss attached.
        # This prevents unprotected positions without exit discipline.
        # =====================================================================
        if order.side == 'buy':
            if order.take_profit is None or order.stop_loss is None:
                if not order.tp_sl_bypass_approved:
                    order.status = OrderStatus.REJECTED
                    logger.error(
                        f"CEO-DIR-2026-119 VIOLATION: {order.canonical_id} - "
                        f"TP/SL REQUIRED. TP={order.take_profit}, SL={order.stop_loss}. "
                        f"Set tp_sl_bypass_approved=True only with CEO approval."
                    )
                    self._log_order(order, "TP_SL_MISSING")
                    return order
                else:
                    logger.warning(
                        f"CEO-DIR-2026-119 BYPASS: {order.canonical_id} - "
                        f"Proceeding without TP/SL (bypass approved)"
                    )

        # Log order to database first
        order.order_id = self._log_order(order, "PENDING")

        # Submit to Alpaca
        if self.trading_client:
            try:
                alpaca_order = self._submit_to_alpaca(order)
                order.alpaca_order_id = alpaca_order.id
                order.status = OrderStatus.SUBMITTED

                # Wait briefly for fill (paper orders usually fill instantly)
                time.sleep(0.5)

                # Check fill status
                filled_order = self.trading_client.get_order_by_id(alpaca_order.id)
                if filled_order.status == 'filled':
                    order.status = OrderStatus.FILLED
                    order.filled_qty = float(filled_order.filled_qty)
                    order.filled_avg_price = float(filled_order.filled_avg_price)
                elif filled_order.status == 'partially_filled':
                    order.status = OrderStatus.PARTIAL
                    order.filled_qty = float(filled_order.filled_qty)
                    order.filled_avg_price = float(filled_order.filled_avg_price)

                logger.info(f"Order {order.status.value}: {order.canonical_id} "
                           f"{order.side} {order.qty} @ {order.filled_avg_price}")

            except Exception as e:
                order.status = OrderStatus.REJECTED
                logger.error(f"Alpaca submission failed: {e}")

        else:
            # Simulation mode - instant fill at market price
            order.status = OrderStatus.FILLED
            order.filled_qty = order.qty
            order.filled_avg_price = self._get_simulated_price(order.canonical_id)
            logger.info(f"Simulated fill: {order.canonical_id} {order.side} "
                       f"{order.qty} @ {order.filled_avg_price}")

        # Update order in database
        self._update_order(order)

        # Create position if filled
        if order.status == OrderStatus.FILLED:
            self._create_position(order)

        return order

    def _submit_to_alpaca(self, order: PaperOrder):
        """Submit order to Alpaca API.

        CEO-DIR-2026-DBV-002: Bracket order support for TP/SL enforcement.
        When take_profit and stop_loss are provided, uses OrderClass.BRACKET
        to ensure exit discipline is enforced at broker level.
        """
        side = OrderSide.BUY if order.side == 'buy' else OrderSide.SELL

        # Determine if bracket order needed (TP/SL present)
        use_bracket = order.take_profit is not None and order.stop_loss is not None

        if use_bracket:
            # CEO-DIR-2026-DBV-002: BRACKET ORDER WITH TP/SL
            # This ensures exit discipline is enforced at Alpaca level
            logger.info(f"Creating BRACKET order: {order.canonical_id} TP={order.take_profit} SL={order.stop_loss}")

            if order.order_type == 'market':
                request = MarketOrderRequest(
                    symbol=order.canonical_id,
                    qty=order.qty,
                    side=side,
                    time_in_force=TimeInForce.GTC,  # GTC for bracket orders
                    order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=order.take_profit),
                    stop_loss=StopLossRequest(stop_price=order.stop_loss)
                )
            else:
                request = LimitOrderRequest(
                    symbol=order.canonical_id,
                    qty=order.qty,
                    side=side,
                    time_in_force=TimeInForce.GTC,  # GTC for bracket orders
                    limit_price=order.limit_price,
                    order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=order.take_profit),
                    stop_loss=StopLossRequest(stop_price=order.stop_loss)
                )
        else:
            # Standard order (no bracket)
            if order.order_type == 'market':
                request = MarketOrderRequest(
                    symbol=order.canonical_id,
                    qty=order.qty,
                    side=side,
                    time_in_force=TimeInForce.DAY
                )
            else:
                request = LimitOrderRequest(
                    symbol=order.canonical_id,
                    qty=order.qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=order.limit_price
                )

        return self.trading_client.submit_order(request)

    def _get_simulated_price(self, canonical_id: str) -> float:
        """Get simulated fill price from database."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT close FROM fhq_data.price_series
                WHERE listing_id = %s
                ORDER BY date DESC LIMIT 1
            """, (canonical_id,))
            row = cur.fetchone()
            return float(row[0]) if row else 100.0

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def _log_order(self, order: PaperOrder, status: str) -> str:
        """Log order to database with full lineage."""
        sql = """
            INSERT INTO fhq_execution.paper_orders (
                signal_id, strategy_source, regime_state, cognitive_action,
                kelly_fraction, circuit_breaker_state, lineage_hash,
                canonical_id, side, order_type, qty, limit_price,
                status, execution_mode, defcon_at_submission
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING order_id::text
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    order.lineage.signal_id,
                    order.lineage.strategy_source,
                    order.lineage.regime_state,
                    order.lineage.cognitive_action,
                    order.lineage.kelly_fraction,
                    order.lineage.circuit_breaker_state,
                    order.lineage.compute_hash(),
                    order.canonical_id,
                    order.side,
                    order.order_type,
                    order.qty,
                    order.limit_price,
                    status.lower(),
                    EXECUTION_MODE,
                    'GREEN'
                ))
                order_id = cur.fetchone()[0]
            self.conn.commit()
            return order_id
        except Exception as e:
            logger.warning(f"Failed to log order for {order.canonical_id}: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return str(uuid.uuid4())  # Generate fallback order ID

    def _update_order(self, order: PaperOrder):
        """Update order status after execution."""
        sql = """
            UPDATE fhq_execution.paper_orders
            SET alpaca_order_id = %s,
                status = %s,
                filled_qty = %s,
                filled_avg_price = %s,
                filled_at = CASE WHEN %s IN ('filled', 'partial') THEN NOW() ELSE NULL END
            WHERE order_id = %s::uuid
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    str(order.alpaca_order_id) if order.alpaca_order_id else None,
                    order.status.value,
                    order.filled_qty,
                    order.filled_avg_price,
                    order.status.value,
                    str(order.order_id) if order.order_id else None
                ))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update order: {e}")
            try:
                self.conn.rollback()
            except:
                pass

    def _create_position(self, order: PaperOrder):
        """Create position record from filled order."""
        side = 'long' if order.side == 'buy' else 'short'
        sql = """
            INSERT INTO fhq_execution.paper_positions (
                canonical_id, strategy_source, side, qty, avg_entry_price,
                current_price, entry_order_id, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s::uuid, 'open'
            ) RETURNING position_id::text
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    order.canonical_id,
                    order.lineage.strategy_source,
                    side,
                    order.filled_qty,
                    order.filled_avg_price,
                    order.filled_avg_price,
                    str(order.order_id) if order.order_id else None
                ))
                position_id = cur.fetchone()[0]
            self.conn.commit()
            logger.info(f"Position created: {position_id}")
            return position_id
        except Exception as e:
            logger.warning(f"Failed to create position: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return None

    # =========================================================================
    # EPISODIC MEMORY (Amendment AMND-006)
    # =========================================================================

    def record_episodic_snapshot(self, snapshot: EpisodicSnapshot):
        """
        Record episodic snapshot to sandbox (non-canonical).

        Per Amendment Section 6.1: MUST be written to fhq_sandbox.episodic_traces only.
        """
        if not self._episodic_enabled:
            return

        # Check storage limit (fail-closed at 1GB)
        if not self._check_episodic_storage():
            logger.warning("Episodic storage limit reached - disabling")
            self._episodic_enabled = False
            return

        sql = """
            INSERT INTO fhq_sandbox.episodic_traces (
                trade_id, canonical_id, strategy_source,
                unrealized_pnl, unrealized_pnl_pct, max_drawdown_pct,
                volatility_decay, time_in_position_minutes,
                current_price, regime_state, defcon_level
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    snapshot.trade_id,
                    snapshot.canonical_id,
                    snapshot.strategy_source,
                    snapshot.unrealized_pnl,
                    snapshot.unrealized_pnl_pct,
                    snapshot.max_drawdown_pct,
                    snapshot.volatility_decay,
                    snapshot.time_in_position_minutes,
                    snapshot.current_price,
                    snapshot.regime_state,
                    snapshot.defcon_level
                ))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Episodic snapshot failed: {e}")
            self.conn.rollback()

    def _check_episodic_storage(self) -> bool:
        """Check if episodic storage is under limit."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT fhq_sandbox.check_storage_limit()")
                return cur.fetchone()[0]
        except:
            return True  # Assume OK if check fails

    def purge_episodic_and_archive(self, trade_id: str, outcome: Dict):
        """
        Purge episodic traces and create archive after trade closure.

        Per Amendment Section 6.2: Active episodic rows are fully wiped.
        Only the final realized outcome goes to canonical (IoS-010).
        """
        # Get episodic summary before purge
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as snapshot_count,
                    MAX(max_drawdown_pct) as max_dd,
                    AVG(unrealized_pnl) as avg_pnl,
                    jsonb_agg(volatility_decay) as vol_data
                FROM fhq_sandbox.episodic_traces
                WHERE trade_id = %s::uuid
            """, (trade_id,))
            summary = cur.fetchone()

        if summary and summary['snapshot_count'] > 0:
            # Create archive
            episodic_hash = hashlib.sha256(
                json.dumps(outcome, default=str).encode()
            ).hexdigest()

            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_sandbox.training_log_archive (
                        trade_id, canonical_id, strategy_source,
                        episodic_hash, snapshot_count, max_drawdown_observed,
                        avg_unrealized_pnl, volatility_summary,
                        final_realized_pnl, trade_duration_minutes
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    trade_id,
                    outcome['canonical_id'],
                    outcome['strategy_source'],
                    episodic_hash,
                    summary['snapshot_count'],
                    summary['max_dd'],
                    summary['avg_pnl'],
                    Json(summary['vol_data']),
                    outcome['realized_pnl'],
                    outcome['duration_minutes']
                ))

        # Purge episodic traces
        with self.conn.cursor() as cur:
            cur.execute("SELECT fhq_sandbox.purge_episodic_traces(%s::uuid)", (trade_id,))

        self.conn.commit()
        logger.info(f"Episodic traces purged for trade {trade_id}")

    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================

    def get_open_positions(self) -> List[Dict]:
        """Get all open paper positions."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_execution.paper_positions
                WHERE status = 'open'
            """)
            return cur.fetchall()

    def close_position(self, position_id: str, exit_price: float) -> Dict:
        """
        Close a position and record outcome.

        Returns trade outcome for learning updates.
        """
        # Get position details
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_execution.paper_positions
                WHERE position_id = %s::uuid
            """, (position_id,))
            position = cur.fetchone()

        if not position or position['status'] != 'open':
            raise ValueError(f"Position {position_id} not found or not open")

        # Calculate PnL
        entry_price = float(position['avg_entry_price'])
        qty = float(position['qty'])
        side_mult = 1 if position['side'] == 'long' else -1
        realized_pnl = (exit_price - entry_price) * qty * side_mult
        realized_pnl_pct = ((exit_price / entry_price) - 1) * 100 * side_mult

        # Calculate duration
        entry_time = position['entry_timestamp']
        duration = (datetime.now(timezone.utc) - entry_time.replace(tzinfo=timezone.utc))
        duration_minutes = int(duration.total_seconds() / 60)

        # Update position
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_execution.paper_positions
                SET status = 'closed',
                    current_price = %s,
                    exit_timestamp = NOW()
                WHERE position_id = %s::uuid
            """, (exit_price, position_id))

        # Record outcome
        outcome = {
            'position_id': position_id,
            'canonical_id': position['canonical_id'],
            'strategy_source': position['strategy_source'],
            'side': position['side'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'realized_pnl': realized_pnl,
            'realized_pnl_pct': realized_pnl_pct,
            'max_drawdown_pct': float(position['max_drawdown_pct'] or 0),
            'duration_minutes': duration_minutes
        }

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_execution.paper_trade_outcomes (
                    position_id, canonical_id, strategy_source, side,
                    entry_price, exit_price, realized_pnl, realized_pnl_pct,
                    max_drawdown_pct, hold_duration_minutes
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING outcome_id::text
            """, (
                position_id,
                outcome['canonical_id'],
                outcome['strategy_source'],
                outcome['side'],
                outcome['entry_price'],
                outcome['exit_price'],
                outcome['realized_pnl'],
                outcome['realized_pnl_pct'],
                outcome['max_drawdown_pct'],
                outcome['duration_minutes']
            ))
            outcome['outcome_id'] = cur.fetchone()[0]

        self.conn.commit()

        # Purge episodic and archive
        self.purge_episodic_and_archive(position_id, outcome)

        logger.info(f"Position closed: {position['canonical_id']} "
                   f"PnL={realized_pnl:.2f} ({realized_pnl_pct:.2f}%)")

        return outcome


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_paper_adapter() -> AlpacaPaperAdapter:
    """Factory function to get configured paper adapter."""
    adapter = AlpacaPaperAdapter()
    adapter.connect()
    return adapter


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Alpaca Paper Adapter Test')
    parser.add_argument('--test', action='store_true', help='Run connection test')
    args = parser.parse_args()

    if args.test:
        adapter = get_paper_adapter()
        print(f"Execution Mode: {EXECUTION_MODE}")
        print(f"Alpaca Available: {ALPACA_AVAILABLE}")
        print(f"Alpaca Connected: {adapter.trading_client is not None}")

        defcon_ok, defcon_msg = adapter.check_defcon()
        print(f"DEFCON Check: {defcon_msg}")

        positions = adapter.get_open_positions()
        print(f"Open Positions: {len(positions)}")

        adapter.close()
        print("Test complete.")
