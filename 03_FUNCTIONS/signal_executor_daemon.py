#!/usr/bin/env python3
"""
SIGNAL EXECUTOR DAEMON (Paper Mode)
====================================
CEO Directive: CD-IOS-001-PRICE-ARCH-001
Classification: G5_PAPER_EXECUTION
Orchestrator: FHQ-IoS001-Bulletproof-EQUITY

===============================================================================
CEO DIRECTIVE 2025-12-22: EXECUTION RE-ENABLED
===============================================================================
Status: OPERATIONAL - Monday liquidation complete ($104,924 cash)
Previous Incident: 3x over-limit execution (MSTR 1088 shares, 2x leverage)

Fixes Confirmed by STIG:
- Fix A: Exposure gate BLOCKS (not just logs) - IMPLEMENTED
- Fix B: Position counts query BROKER via broker_truth_enforcer - IMPLEMENTED
- Fix C: Trade logging atomic with execution - IMPLEMENTED
- Fix D: Single-symbol accumulation guard - IMPLEMENTED
- Fix E: Incremental exposure check - IMPLEMENTED

EXECUTION_FREEZE lifted in unified_execution_gateway.py
Kill switch removed by CEO authorization 2025-12-22.
===============================================================================
"""

# ============================================================================
# EXECUTION RE-ENABLED - CEO DIRECTIVE 2025-12-22
# ============================================================================

"""
Purpose:
    Monitors Golden Needles across ALL asset classes and CCO state.
    Executes trades via Alpaca Paper when CCO permits.
    Stays silent when CCO is SUPPRESSED (expected behavior).

    === IoS-003-B INTEGRATION (Intraday Regime-Delta) ===
    Consumes Flash-Context from fhq_operational for EPHEMERAL_PRIMED transitions.
    When canonical regime doesn't match but Flash-Context indicates favorable
    intraday conditions, signals can be promoted with reduced position sizing (50%).

Multi-Asset Support (per CD-IOS-001-PRICE-ARCH-001):
    - Equities: Direct execution via Alpaca
    - ETFs: Direct execution via Alpaca
    - Crypto: Proxy execution via crypto-adjacent equities (MSTR, COIN, MARA)
    - All golden needles are tradeable regardless of asset class

Flow:
    1. Check CCO state every cycle
    2. Monitor existing positions for stop-loss/take-profit exits
    3. If SUPPRESSED → wait silently (exits still monitored)
    4. If PERMITTED → scan for executable signals across all asset classes
    5. Check Flash-Context for EPHEMERAL_PRIMED opportunities (IoS-003-B)
    6. Execute via Alpaca with Kelly sizing (50% for ephemeral)
    7. Log all transitions and trades

Hard Constraints:
    - Paper mode ONLY
    - Respects VOL_NEUTRAL threshold (does NOT override)
    - Maximum 3 concurrent positions
    - Kelly-based position sizing
    - Freshness decoupling per FDR-002 (execution independent of canonical completeness)
    - Ephemeral trades use 50% position sizing (conservative due to intraday context)
"""

import os
import sys
import time
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Holiday Execution Gate (CEO Directive 2025-12-19)
try:
    from holiday_execution_gate import (
        check_holiday_execution_gate,
        can_execute as holiday_can_execute,
        get_holiday_status,
        HOLIDAY_MODE_ENABLED
    )
    HOLIDAY_GATE_AVAILABLE = True
except ImportError:
    HOLIDAY_GATE_AVAILABLE = False
    HOLIDAY_MODE_ENABLED = False

# Unified Execution Gateway (CEO Directive 2025-12-20)
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

# ============================================================================
# BROKER TRUTH ENFORCER (CEO Directive 2025-12-21)
# Position/exposure queries MUST use broker, NOT database
# ============================================================================
try:
    from broker_truth_enforcer import (
        get_broker_account_state,
        get_open_position_count as broker_get_open_position_count,
        get_open_symbols as broker_get_open_symbols,
        has_position_for_symbol,
        get_exposure_metrics,
        validate_exposure_from_broker,
        get_pending_orders
    )
    BROKER_TRUTH_AVAILABLE = True
except ImportError:
    BROKER_TRUTH_AVAILABLE = False
    logger.warning("BROKER TRUTH ENFORCER NOT AVAILABLE - EXECUTION BLOCKED")

# Alpaca SDK
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SIGNAL-EXEC] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SIGNAL_EXECUTOR')

# Configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY', ''))

# Daemon Config
DAEMON_CONFIG = {
    'cycle_interval_seconds': 60,       # Check every 60 seconds
    'max_concurrent_positions': 3,       # Max open positions
    'min_eqs_score': 0.80,              # Minimum EQS to consider
    'kelly_multiplier': 0.75,           # 3/4 Kelly (aggressive)
    'max_position_pct': 0.15,           # 15% NAV max per position
    'min_position_dollars': 500,        # Minimum $500 per trade
    'default_target_pct': 0.05,         # 5% target
    'default_stop_loss_pct': 0.03,      # 3% stop loss
}

# =============================================================================
# HARD EXPOSURE GATES (CEO DIRECTIVE: CRITICAL RISK CONTROL)
# =============================================================================
# These are ABSOLUTE LIMITS that cannot be overridden.
# They protect against position sizing bugs, external trades, and margin abuse.
# Violation of these gates BLOCKS all new execution.

HARD_LIMITS = {
    'max_single_position_pct': 0.25,    # ABSOLUTE MAX 25% NAV per position
    'max_total_exposure_pct': 1.00,     # ABSOLUTE MAX 100% NAV total (no margin)
    'max_single_position_usd': 50000,   # ABSOLUTE MAX $50,000 per position
    'min_cash_reserve_pct': 0.10,       # Maintain 10% cash minimum
    'block_on_margin': True,            # Block execution if using margin (negative cash)
}

# Multi-Asset Symbol Configuration
# Per CEO Directive CD-IOS-001-PRICE-ARCH-001: Multi-tier execution across asset classes

# Direct tradeable symbols (equities via Alpaca)
DIRECT_EQUITY_SYMBOLS = [
    'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMD', 'META', 'AMZN',
    'SPY', 'QQQ', 'IWM', 'DIA',  # ETFs
    'MSTR', 'COIN', 'MARA', 'RIOT',  # Crypto-adjacent equities
    'JPM', 'GS', 'MS', 'BAC',  # Financials
    'XOM', 'CVX', 'COP',  # Energy
    'UNH', 'JNJ', 'PFE',  # Healthcare
]

# Crypto symbols tradeable via Alpaca Crypto
CRYPTO_SYMBOLS = [
    'BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD', 'DOGE/USD',
    'LTC/USD', 'BCH/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD'
]

# Mapping from price witness symbols to tradeable symbols
SYMBOL_MAPPING = {
    # Crypto to Alpaca crypto format
    'BTCUSDT': 'BTC/USD',
    'BTC-USD': 'BTC/USD',
    'ETHUSDT': 'ETH/USD',
    'ETH-USD': 'ETH/USD',
    'SOLUSDT': 'SOL/USD',
    'SOL-USD': 'SOL/USD',
    # Direct equity pass-through
    'NVDA': 'NVDA',
    'AAPL': 'AAPL',
    'MSFT': 'MSFT',
    'GOOGL': 'GOOGL',
    'TSLA': 'TSLA',
    'AMD': 'AMD',
    'META': 'META',
    'SPY': 'SPY',
    'QQQ': 'QQQ',
}

# Proxy mapping for symbols not directly tradeable
PROXY_SYMBOLS = {
    'BTCUSDT': ['MSTR', 'COIN', 'MARA'],
    'BTC-USD': ['MSTR', 'COIN', 'MARA'],
    'ETHUSDT': ['COIN', 'MSTR'],
    'ETH-USD': ['COIN', 'MSTR'],
    'default': ['SPY', 'QQQ', 'NVDA']
}


class SignalExecutorDaemon:
    """Autonomous Signal Executor for Paper Trading"""

    def __init__(self):
        self.conn = None
        self.trading_client = None
        self.data_client = None
        self.running = False
        self.cycle_count = 0
        self.last_permit_status = None
        self.suppressed_cycles = 0

    def connect(self) -> bool:
        """Connect to database and Alpaca"""
        try:
            # Database
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Database connected")

            # Alpaca
            if ALPACA_AVAILABLE and ALPACA_API_KEY:
                self.trading_client = TradingClient(
                    api_key=ALPACA_API_KEY,
                    secret_key=ALPACA_SECRET,
                    paper=True  # ALWAYS paper mode
                )
                self.data_client = StockHistoricalDataClient(
                    ALPACA_API_KEY, ALPACA_SECRET
                )
                account = self.trading_client.get_account()
                logger.info(f"Alpaca connected - Portfolio: ${float(account.portfolio_value):,.2f}")
            else:
                logger.warning("Alpaca not available - simulation mode")

            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def close(self):
        """Close connections"""
        if self.conn:
            self.conn.close()

    # =========================================================================
    # HARD EXPOSURE GATE (CEO DIRECTIVE: CRITICAL RISK CONTROL)
    # =========================================================================
    # This gate MUST be checked before ANY trade execution.
    # It validates ACTUAL Alpaca positions, not just our records.
    # This protects against external trades, bugs, and margin abuse.

    def validate_exposure_gate(
        self,
        proposed_trade_usd: float = 0,
        proposed_symbol: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validate HARD exposure limits before allowing any new trade.

        CEO Directive 2025-12-21: This checks ACTUAL Alpaca positions.
        Database state is NEVER trusted for exposure decisions.

        Args:
            proposed_trade_usd: Size of proposed trade in USD (Fix E)
            proposed_symbol: Symbol for proposed trade (Fix D - same-symbol guard)

        Returns:
            (is_allowed, reason_if_blocked)
        """
        if not self.trading_client:
            return False, "No Alpaca connection"

        # =====================================================================
        # CEO DIRECTIVE 2025-12-21: Use broker_truth_enforcer if available
        # This centralizes all broker queries in one module
        # =====================================================================
        if BROKER_TRUTH_AVAILABLE:
            return validate_exposure_from_broker(
                proposed_trade_usd=proposed_trade_usd,
                proposed_symbol=proposed_symbol
            )

        # Fallback to direct Alpaca queries if broker_truth_enforcer not available
        try:
            # Get ACTUAL account state from Alpaca
            account = self.trading_client.get_account()
            portfolio_value = float(account.portfolio_value)
            cash = float(account.cash)

            # Get ACTUAL positions from Alpaca
            positions = self.trading_client.get_all_positions()

            # Build list of open symbols for same-symbol check
            open_symbols = [p.symbol for p in positions]

            # Calculate total exposure
            total_exposure = sum(float(p.market_value) for p in positions)
            total_exposure_pct = total_exposure / portfolio_value if portfolio_value > 0 else 0

            # Check for largest single position
            largest_position = 0
            largest_symbol = None
            for p in positions:
                pos_value = float(p.market_value)
                if pos_value > largest_position:
                    largest_position = pos_value
                    largest_symbol = p.symbol

            largest_position_pct = largest_position / portfolio_value if portfolio_value > 0 else 0

            # GATE 1: Check if using margin (negative cash)
            if HARD_LIMITS['block_on_margin'] and cash < 0:
                logger.critical(f"HARD GATE BLOCKED: Using margin! Cash=${cash:,.2f}")
                return False, f"MARGIN VIOLATION: Cash is negative (${cash:,.2f})"

            # GATE 2: Check total exposure
            if total_exposure_pct > HARD_LIMITS['max_total_exposure_pct']:
                logger.critical(f"HARD GATE BLOCKED: Total exposure {total_exposure_pct:.1%} > {HARD_LIMITS['max_total_exposure_pct']:.0%}")
                return False, f"TOTAL EXPOSURE VIOLATION: {total_exposure_pct:.1%} exceeds {HARD_LIMITS['max_total_exposure_pct']:.0%} limit"

            # GATE 3: Check largest single position
            if largest_position_pct > HARD_LIMITS['max_single_position_pct']:
                logger.critical(f"HARD GATE BLOCKED: Position {largest_symbol} at {largest_position_pct:.1%} > {HARD_LIMITS['max_single_position_pct']:.0%}")
                return False, f"SINGLE POSITION VIOLATION: {largest_symbol} at {largest_position_pct:.1%} exceeds {HARD_LIMITS['max_single_position_pct']:.0%} limit"

            # GATE 4: Check if largest position exceeds absolute USD limit
            if largest_position > HARD_LIMITS['max_single_position_usd']:
                logger.critical(f"HARD GATE BLOCKED: Position {largest_symbol} at ${largest_position:,.0f} > ${HARD_LIMITS['max_single_position_usd']:,.0f}")
                return False, f"ABSOLUTE USD VIOLATION: {largest_symbol} at ${largest_position:,.0f} exceeds ${HARD_LIMITS['max_single_position_usd']:,.0f} limit"

            # =====================================================================
            # GATE 5: SAME-SYMBOL ACCUMULATION GUARD (Fix D - CEO Directive 2025-12-21)
            # Prevents multiple positions in the same symbol
            # This was the ROOT CAUSE of 3x MSTR accumulation
            # =====================================================================
            if proposed_symbol and proposed_symbol in open_symbols:
                logger.critical(f"SAME-SYMBOL BLOCKED: Already have position in {proposed_symbol}")
                return False, f"SAME-SYMBOL VIOLATION: Already have position in {proposed_symbol}"

            # =====================================================================
            # GATE 6: INCREMENTAL EXPOSURE CHECK (Fix E - CEO Directive 2025-12-21)
            # Validates that proposed trade won't push us over limits
            # =====================================================================
            if proposed_trade_usd > 0:
                new_exposure_pct = (total_exposure + proposed_trade_usd) / portfolio_value
                if new_exposure_pct > HARD_LIMITS['max_total_exposure_pct']:
                    logger.warning(f"Proposed trade blocked: Would increase exposure to {new_exposure_pct:.1%}")
                    return False, f"PROPOSED TRADE BLOCKED: Would increase exposure to {new_exposure_pct:.1%}"

                if proposed_trade_usd > HARD_LIMITS['max_single_position_usd']:
                    logger.warning(f"Proposed trade blocked: ${proposed_trade_usd:,.0f} exceeds ${HARD_LIMITS['max_single_position_usd']:,.0f}")
                    return False, f"PROPOSED TRADE BLOCKED: ${proposed_trade_usd:,.0f} exceeds single position limit"

            # GATE 7: Check minimum cash reserve
            cash_pct = cash / portfolio_value if portfolio_value > 0 else 0
            if cash_pct < HARD_LIMITS['min_cash_reserve_pct'] and proposed_trade_usd > 0:
                logger.warning(f"Cash reserve low: {cash_pct:.1%} < {HARD_LIMITS['min_cash_reserve_pct']:.0%}")
                return False, f"CASH RESERVE LOW: {cash_pct:.1%} below {HARD_LIMITS['min_cash_reserve_pct']:.0%} minimum"

            # GATE 8: Check for pending orders on same symbol
            if proposed_symbol:
                try:
                    pending = self.trading_client.get_orders(
                        GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[proposed_symbol])
                    )
                    if pending:
                        logger.warning(f"Pending order exists for {proposed_symbol}")
                        return False, f"PENDING ORDER EXISTS: {len(pending)} pending order(s) for {proposed_symbol}"
                except Exception as e:
                    logger.warning(f"Could not check pending orders: {e}")

            # All gates passed
            logger.info(f"Exposure gate PASSED: {len(positions)} positions, {total_exposure_pct:.1%} exposure, ${cash:,.0f} cash")
            return True, "OK"

        except Exception as e:
            logger.error(f"Exposure gate check failed: {e}")
            return False, f"GATE CHECK ERROR: {e}"

    def log_exposure_violation(self, violation_type: str, details: Dict):
        """Log exposure violation to governance table"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type,
                        action_target,
                        action_target_type,
                        initiated_by,
                        decision,
                        decision_rationale,
                        agent_id,
                        metadata
                    ) VALUES (
                        'EXPOSURE_GATE_VIOLATION',
                        'SIGNAL_EXECUTOR',
                        'HARD_LIMIT_BREACH',
                        'SIGNAL_EXECUTOR_DAEMON',
                        'BLOCKED',
                        %s,
                        'STIG',
                        %s::jsonb
                    )
                """, (violation_type, json.dumps(details)))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log exposure violation: {e}")

    def log_holiday_gate_block(self, symbol: str, asset_class: str, reason: str, needle: Dict):
        """Log holiday gate block to governance table (for observability)"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type,
                        action_target,
                        action_target_type,
                        initiated_by,
                        decision,
                        decision_rationale,
                        agent_id,
                        metadata
                    ) VALUES (
                        'HOLIDAY_EXECUTION_GATE',
                        %s,
                        %s,
                        'SIGNAL_EXECUTOR_DAEMON',
                        'BLOCKED',
                        %s,
                        'STIG',
                        %s::jsonb
                    )
                """, (
                    symbol,
                    asset_class,
                    reason,
                    json.dumps({
                        'needle_id': str(needle.get('needle_id', 'unknown')),
                        'price_witness_symbol': needle.get('price_witness_symbol'),
                        'eqs_score': float(needle.get('eqs_score', 0)),
                        'signal_state': needle.get('current_state'),
                        'holiday_mode': 'CRYPTO_FIRST',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log holiday gate block: {e}")

    # =========================================================================
    # CCO STATE MONITORING
    # =========================================================================

    def get_cco_state(self) -> Optional[Dict]:
        """Get current CCO state"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    cco_status,
                    global_permit,
                    permit_reason,
                    current_regime,
                    current_vol_percentile,
                    defcon_level,
                    context_timestamp
                FROM fhq_canonical.g5_cco_state
                WHERE is_active = TRUE
            """)
            return cur.fetchone()

    def is_execution_permitted(self) -> Tuple[bool, str]:
        """Check if execution is permitted by CCO"""
        state = self.get_cco_state()
        if not state:
            return False, "No CCO state available"

        if state['cco_status'] != 'OPERATIONAL':
            return False, f"CCO not operational: {state['cco_status']}"

        if state['global_permit'] != 'PERMITTED':
            return False, state['permit_reason'] or "Global permit not granted"

        if state['defcon_level'] and state['defcon_level'] <= 2:
            return False, f"DEFCON {state['defcon_level']} - execution blocked"

        return True, "Execution permitted"

    # =========================================================================
    # POSITION MANAGEMENT
    # CEO DIRECTIVE 2025-12-21: BROKER IS SOURCE OF TRUTH
    # All position/exposure queries for DECISION-MAKING must use BROKER
    # Database queries permitted ONLY for internal bookkeeping (needle_id tracking)
    # =========================================================================

    def get_open_positions_count(self) -> int:
        """
        Get count of open positions FROM BROKER (not database).

        CEO Directive 2025-12-21 FIX B:
        This function MUST query Alpaca directly.
        Database counts may be used only for reporting, never for decision-making.
        """
        if BROKER_TRUTH_AVAILABLE:
            return broker_get_open_position_count()
        else:
            # Broker unavailable = execution blocked = return max to prevent new trades
            logger.critical("BROKER UNAVAILABLE - Returning MAX to block execution")
            return DAEMON_CONFIG['max_concurrent_positions']

    def get_traded_needles(self) -> List[str]:
        """
        Get list of needle IDs that have been traded.

        NOTE: This is internal bookkeeping only (broker doesn't track needle IDs).
        This does NOT affect position/exposure decisions.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT needle_id::text FROM fhq_canonical.g5_paper_trades
            """)
            return [row[0] for row in cur.fetchall()]

    def get_open_symbols(self) -> List[str]:
        """
        Get symbols with open positions FROM BROKER (not database).

        CEO Directive 2025-12-21 FIX B:
        This function MUST query Alpaca directly.
        Database symbols may be used only for reporting, never for decision-making.
        """
        if BROKER_TRUTH_AVAILABLE:
            return broker_get_open_symbols()
        else:
            # Broker unavailable = execution blocked
            logger.critical("BROKER UNAVAILABLE - Cannot get open symbols")
            return []

    def get_open_positions(self) -> List[Dict]:
        """
        Get all open positions with entry details.

        WARNING: This is for internal bookkeeping ONLY (exit monitoring).
        The database records provide needle_id, entry_price, entry_context
        which the broker doesn't track.

        For position/exposure DECISIONS, use broker_truth_enforcer functions.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    trade_id,
                    needle_id,
                    symbol,
                    direction,
                    entry_price,
                    position_size,
                    entry_context,
                    entry_timestamp
                FROM fhq_canonical.g5_paper_trades
                WHERE exit_timestamp IS NULL
                ORDER BY entry_timestamp ASC
            """)
            return cur.fetchall()

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        if not self.data_client:
            return None
        try:
            quote = self.data_client.get_stock_latest_quote(
                StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            )
            # Use mid price for more accurate valuation
            bid = float(quote[symbol].bid_price)
            ask = float(quote[symbol].ask_price)
            return (bid + ask) / 2 if bid > 0 and ask > 0 else float(quote[symbol].ask_price)
        except Exception as e:
            logger.warning(f"Could not get price for {symbol}: {e}")
            return None

    # =========================================================================
    # STOP LOSS / TAKE PROFIT EXIT LOGIC
    # =========================================================================

    def check_exit_conditions(self, position: Dict) -> Tuple[bool, str, float]:
        """
        Check if position should be exited based on stop loss or take profit.
        Returns: (should_exit, reason, current_price)
        """
        symbol = position['symbol']
        entry_price = float(position['entry_price'])
        direction = position['direction']

        # Parse target/stop from entry_context
        entry_context = position.get('entry_context', {})
        if isinstance(entry_context, str):
            try:
                entry_context = json.loads(entry_context)
            except:
                entry_context = {}

        target_pct = entry_context.get('target_pct', DAEMON_CONFIG['default_target_pct'])
        stop_loss_pct = entry_context.get('stop_loss_pct', DAEMON_CONFIG['default_stop_loss_pct'])

        # Get current price
        current_price = self.get_current_price(symbol)
        if current_price is None or current_price <= 0:
            return False, "Price unavailable or market closed", 0

        # Calculate P/L percentage
        if direction == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price
            target_price = entry_price * (1 + target_pct)
            stop_price = entry_price * (1 - stop_loss_pct)

            # Check take profit
            if current_price >= target_price:
                return True, f"TAKE_PROFIT (+{pnl_pct*100:.2f}%)", current_price

            # Check stop loss
            if current_price <= stop_price:
                return True, f"STOP_LOSS ({pnl_pct*100:.2f}%)", current_price
        else:
            # SHORT position
            pnl_pct = (entry_price - current_price) / entry_price
            target_price = entry_price * (1 - target_pct)
            stop_price = entry_price * (1 + stop_loss_pct)

            if current_price <= target_price:
                return True, f"TAKE_PROFIT (+{pnl_pct*100:.2f}%)", current_price

            if current_price >= stop_price:
                return True, f"STOP_LOSS ({pnl_pct*100:.2f}%)", current_price

        return False, f"HOLDING ({pnl_pct*100:+.2f}%)", current_price

    def execute_exit(self, position: Dict, reason: str, exit_price: float) -> Optional[Dict]:
        """Execute an exit order for a position"""
        if not self.trading_client:
            logger.warning("Alpaca not available - cannot exit")
            return None

        symbol = position['symbol']
        direction = position['direction']

        # Get current Alpaca position to know exact shares
        try:
            alpaca_positions = self.trading_client.get_all_positions()
            alpaca_pos = next((p for p in alpaca_positions if p.symbol == symbol), None)

            if not alpaca_pos:
                logger.warning(f"No Alpaca position found for {symbol} - marking as closed")
                self._log_exit(position, exit_price, 0, reason, "POSITION_NOT_FOUND")
                return {'symbol': symbol, 'reason': reason, 'status': 'POSITION_NOT_FOUND'}

            shares = abs(float(alpaca_pos.qty))

        except Exception as e:
            logger.error(f"Could not get Alpaca position for {symbol}: {e}")
            return None

        # Determine exit side (opposite of entry)
        exit_side = OrderSide.SELL if direction == 'LONG' else OrderSide.BUY

        logger.info(f"Exiting: {exit_side.name} {int(shares)} {symbol} @ ~${exit_price:.2f} ({reason})")

        try:
            order = self.trading_client.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=exit_side,
                    time_in_force=TimeInForce.DAY
                )
            )

            # Wait for fill
            time.sleep(1)
            filled_order = self.trading_client.get_order_by_id(order.id)

            if filled_order.status in ['filled', 'partially_filled']:
                filled_price = float(filled_order.filled_avg_price)
                filled_qty = float(filled_order.filled_qty)

                # Calculate realized P/L
                entry_price = float(position['entry_price'])
                if direction == 'LONG':
                    realized_pnl = (filled_price - entry_price) * filled_qty
                else:
                    realized_pnl = (entry_price - filled_price) * filled_qty

                logger.info(f"EXIT FILLED: {symbol} @ ${filled_price:.2f} | P/L: ${realized_pnl:+,.2f}")

                # Log to database
                self._log_exit(position, filled_price, realized_pnl, reason, str(order.id))

                return {
                    'symbol': symbol,
                    'exit_price': filled_price,
                    'realized_pnl': realized_pnl,
                    'reason': reason,
                    'order_id': str(order.id)
                }
            else:
                logger.warning(f"Exit order not filled: {filled_order.status}")
                return None

        except Exception as e:
            logger.error(f"Exit execution failed for {symbol}: {e}")
            return None

    def _log_exit(self, position: Dict, exit_price: float, realized_pnl: float,
                  reason: str, order_id: str):
        """Log exit to database"""
        cco_state = self.get_cco_state()

        exit_context = json.dumps({
            'exit_reason': reason,
            'exit_price': exit_price,
            'realized_pnl': realized_pnl,
            'alpaca_order_id': order_id,
            'cco_status': cco_state['cco_status'] if cco_state else 'UNKNOWN',
            'vol_percentile': float(cco_state['current_vol_percentile']) if cco_state else 0,
            'exited_by': 'SIGNAL_EXECUTOR_DAEMON',
            'exit_timestamp': datetime.now(timezone.utc).isoformat()
        })

        with self.conn.cursor() as cur:
            # Update trade record
            cur.execute("""
                UPDATE fhq_canonical.g5_paper_trades
                SET
                    exit_price = %s,
                    exit_timestamp = NOW(),
                    realized_pnl = %s,
                    exit_reason = %s,
                    exit_context = %s
                WHERE trade_id = %s
            """, (exit_price, realized_pnl, reason, exit_context, position['trade_id']))

            # Update signal state to EXECUTED
            cur.execute("""
                UPDATE fhq_canonical.g5_signal_state
                SET
                    current_state = 'EXECUTED',
                    executed_at = NOW(),
                    position_exit_price = %s,
                    realized_pnl = %s,
                    last_transition = 'PRIMED_TO_EXECUTED',
                    last_transition_at = NOW(),
                    transition_count = transition_count + 1,
                    updated_at = NOW()
                WHERE needle_id = %s
            """, (exit_price, realized_pnl, position['needle_id']))

            # Log transition
            cur.execute("""
                INSERT INTO fhq_canonical.g5_state_transitions (
                    needle_id, from_state, to_state, transition_trigger,
                    context_snapshot, cco_status, transition_valid, transitioned_at
                ) VALUES (
                    %s, 'PRIMED', 'EXECUTED', %s,
                    %s, %s, TRUE, NOW()
                )
            """, (
                position['needle_id'],
                reason,
                exit_context,
                cco_state['cco_status'] if cco_state else 'UNKNOWN'
            ))

        self.conn.commit()

    def monitor_positions(self) -> Dict:
        """Monitor all open positions for exit conditions"""
        result = {
            'positions_checked': 0,
            'exits_triggered': 0,
            'exits': []
        }

        positions = self.get_open_positions()
        result['positions_checked'] = len(positions)

        for position in positions:
            should_exit, reason, current_price = self.check_exit_conditions(position)

            if should_exit:
                exit_result = self.execute_exit(position, reason, current_price)
                if exit_result:
                    result['exits_triggered'] += 1
                    result['exits'].append(exit_result)

        return result

    # =========================================================================
    # GOLDEN NEEDLE SELECTION
    # =========================================================================

    def get_executable_needles(self, limit: int = 5) -> List[Dict]:
        """Get Golden Needles eligible for execution"""
        traded_needles = self.get_traded_needles()
        traded_clause = ""
        if traded_needles:
            traded_clause = f"AND needle_id NOT IN ({','.join(['%s'] * len(traded_needles))})"

        query = f"""
            SELECT
                needle_id,
                hypothesis_title,
                hypothesis_category,
                eqs_score,
                confluence_factor_count,
                sitc_confidence_level,
                price_witness_symbol,
                regime_technical,
                expected_timeframe_days,
                created_at
            FROM fhq_canonical.golden_needles
            WHERE is_current = TRUE
              AND eqs_score >= %s
              {traded_clause}
            ORDER BY eqs_score DESC, created_at DESC
            LIMIT %s
        """

        params = [DAEMON_CONFIG['min_eqs_score']]
        if traded_needles:
            params.extend(traded_needles)
        params.append(limit)

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def select_symbol_for_needle(self, needle: Dict) -> Optional[str]:
        """
        Select tradeable symbol based on needle's price witness.
        Per CD-IOS-001-PRICE-ARCH-001: Multi-asset execution support.

        Priority:
        1. Direct mapping if symbol is directly tradeable
        2. Crypto via Alpaca if crypto symbol
        3. Proxy equity if no direct mapping
        """
        witness = needle.get('price_witness_symbol', '')
        open_symbols = self.get_open_symbols()

        # 1. Check direct mapping
        if witness in SYMBOL_MAPPING:
            mapped = SYMBOL_MAPPING[witness]
            if mapped not in open_symbols:
                # Check if it's a crypto symbol (contains /)
                if '/' in mapped:
                    # For crypto, use proxy equities for now (Alpaca crypto needs different client)
                    candidates = PROXY_SYMBOLS.get(witness, PROXY_SYMBOLS['default'])
                    available = [s for s in candidates if s not in open_symbols]
                    if available:
                        return available[0]
                else:
                    return mapped

        # 2. Check if witness is a direct equity symbol
        if witness in DIRECT_EQUITY_SYMBOLS:
            if witness not in open_symbols:
                return witness

        # 3. Fall back to proxy symbols
        candidates = PROXY_SYMBOLS.get(witness, PROXY_SYMBOLS['default'])
        available = [s for s in candidates if s not in open_symbols]

        if not available:
            return None

        return available[0]

    # =========================================================================
    # POSITION SIZING (KELLY)
    # =========================================================================

    def calculate_position_size(
        self,
        symbol: str,
        eqs_score: float,
        confidence: str
    ) -> Tuple[int, float, float]:
        """Calculate position size using Kelly criterion"""
        if not self.trading_client:
            return 0, 0, 0

        # Get account value
        account = self.trading_client.get_account()
        portfolio_value = float(account.portfolio_value)

        # Get current price
        try:
            quote = self.data_client.get_stock_latest_quote(
                StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            )
            current_price = float(quote[symbol].ask_price)
        except Exception as e:
            logger.warning(f"Could not get price for {symbol}: {e}")
            return 0, 0, 0

        # Map EQS to Sharpe estimate (EQS 1.0 ~ Sharpe 0.5)
        sharpe_estimate = eqs_score * 0.5

        # Confidence multiplier
        conf_mult = {'HIGH': 1.0, 'MEDIUM': 0.8, 'LOW': 0.6}.get(confidence, 0.7)

        # Kelly calculation
        win_prob = 0.5 + (0.5 / (1 + 2.718 ** (-3 * sharpe_estimate))) - 0.25
        win_prob = min(max(win_prob, 0.50), 0.95)
        win_loss = 1.0 + (0.5 * sharpe_estimate)
        raw_kelly = (win_prob * (win_loss + 1) - 1) / win_loss

        # Apply multipliers
        adjusted_kelly = raw_kelly * DAEMON_CONFIG['kelly_multiplier'] * conf_mult

        # Cap at max position
        position_pct = min(adjusted_kelly, DAEMON_CONFIG['max_position_pct'])

        # Calculate dollar amount
        dollar_amount = portfolio_value * position_pct
        dollar_amount = max(dollar_amount, DAEMON_CONFIG['min_position_dollars'])

        # Calculate shares
        shares = int(dollar_amount / current_price)

        return shares, dollar_amount, current_price

    # =========================================================================
    # TRADE EXECUTION
    # =========================================================================

    def execute_trade(self, needle: Dict, symbol: str) -> Optional[Dict]:
        """Execute a paper trade for a Golden Needle"""
        if not self.trading_client:
            logger.warning("Alpaca not available - skipping execution")
            return None

        # =====================================================================
        # HARD EXPOSURE GATE - MANDATORY PRE-EXECUTION CHECK
        # CEO Directive 2025-12-21: Validates ACTUAL Alpaca state before any trade.
        # Fix D: Same-symbol accumulation guard via proposed_symbol
        # =====================================================================
        gate_ok, gate_reason = self.validate_exposure_gate(proposed_symbol=symbol)
        if not gate_ok:
            logger.critical(f"EXECUTION BLOCKED by HARD EXPOSURE GATE: {gate_reason}")
            self.log_exposure_violation(gate_reason, {
                'symbol': symbol,
                'needle_id': str(needle.get('needle_id', 'unknown')),
                'attempted_action': 'TRADE_EXECUTION',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            return None

        # =====================================================================
        # HOLIDAY EXECUTION GATE (CEO Directive 2025-12-19)
        # Crypto-First Execution: Equities/FX suspended, Crypto (BTC,ETH,SOL) active
        # =====================================================================
        if HOLIDAY_GATE_AVAILABLE and HOLIDAY_MODE_ENABLED:
            # Get source signal for proxy resolution
            source_symbol = needle.get('price_witness_symbol', symbol)
            holiday_ok, holiday_reason, asset_class = check_holiday_execution_gate(
                symbol=symbol,
                target_state='ACTIVE',
                source_signal=source_symbol
            )
            if not holiday_ok:
                logger.warning(f"HOLIDAY GATE BLOCKED: {symbol} ({asset_class}) - {holiday_reason}")
                # Log for observability (signal lifecycle continues, execution blocked)
                self.log_holiday_gate_block(symbol, asset_class, holiday_reason, needle)
                return None
            else:
                logger.info(f"HOLIDAY GATE PASSED: {symbol} ({asset_class}) - {holiday_reason}")

        # WAVE 17D.1 FIX: Check for existing pending orders to prevent duplicates
        try:
            open_orders = self.trading_client.get_orders(
                GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
            )
            if open_orders:
                logger.info(f"Pending order exists for {symbol} - skipping duplicate")
                return None
        except Exception as e:
            logger.warning(f"Could not check pending orders: {e}")

        # Calculate position size
        shares, dollar_amount, entry_price = self.calculate_position_size(
            symbol,
            float(needle['eqs_score']),
            needle['sitc_confidence_level']
        )

        # =====================================================================
        # SECONDARY GATE: Validate proposed trade against limits
        # CEO Directive 2025-12-21: Fix D (same-symbol) + Fix E (incremental exposure)
        # =====================================================================
        gate_ok, gate_reason = self.validate_exposure_gate(
            proposed_trade_usd=dollar_amount,
            proposed_symbol=symbol
        )
        if not gate_ok:
            logger.warning(f"Proposed trade blocked: {gate_reason}")
            return None

        if shares < 1:
            logger.warning(f"Position too small for {symbol} - skipping")
            return None

        logger.info(f"Executing: BUY {shares} {symbol} @ ${entry_price:.2f} (~${dollar_amount:,.2f})")

        try:
            # Submit market order
            order = self.trading_client.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
            )

            # Wait for fill
            time.sleep(1)
            filled_order = self.trading_client.get_order_by_id(order.id)

            if filled_order.status in ['filled', 'partially_filled']:
                filled_qty = float(filled_order.filled_qty)
                filled_price = float(filled_order.filled_avg_price)
                position_value = filled_qty * filled_price

                logger.info(f"FILLED: {int(filled_qty)} {symbol} @ ${filled_price:.2f} = ${position_value:,.2f}")

                # Log to database
                trade_id = self._log_trade(needle, symbol, filled_qty, filled_price, position_value, order.id)

                return {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'qty': filled_qty,
                    'price': filled_price,
                    'value': position_value,
                    'order_id': str(order.id)
                }
            else:
                logger.warning(f"Order not filled: {filled_order.status}")
                return None

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return None

    def _log_trade(
        self,
        needle: Dict,
        symbol: str,
        qty: float,
        price: float,
        value: float,
        order_id: str
    ) -> str:
        """
        Log trade to database.

        CEO Directive 2025-12-21 FIX C: Trade logging must be atomic with execution.
        If primary logging fails, we MUST log to recovery table because the broker
        trade has already executed.

        The trade cannot be rolled back at broker level, so we ensure logging
        succeeds or falls back to a simpler recovery log.
        """
        trade_id = str(uuid.uuid4())
        execution_time = datetime.now(timezone.utc)
        cco_state = self.get_cco_state()

        entry_context = json.dumps({
            'cco_status': cco_state['cco_status'] if cco_state else 'UNKNOWN',
            'global_permit': cco_state['global_permit'] if cco_state else 'UNKNOWN',
            'regime': cco_state['current_regime'] if cco_state else 'UNKNOWN',
            'vol_percentile': float(cco_state['current_vol_percentile']) if cco_state else 0,
            'needle_title': needle.get('hypothesis_title', 'UNKNOWN'),
            'needle_category': needle.get('hypothesis_category', 'UNKNOWN'),
            'eqs_score': float(needle.get('eqs_score', 0)),
            'alpaca_order_id': str(order_id),
            'kelly_multiplier': DAEMON_CONFIG['kelly_multiplier'],
            'target_pct': DAEMON_CONFIG['default_target_pct'],
            'stop_loss_pct': DAEMON_CONFIG['default_stop_loss_pct'],
            'executed_by': 'SIGNAL_EXECUTOR_DAEMON',
            'execution_timestamp': execution_time.isoformat()
        })

        try:
            # =====================================================================
            # PRIMARY LOGGING - Normal trade record
            # =====================================================================
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_canonical.g5_paper_trades (
                        trade_id, needle_id, symbol, direction, entry_price,
                        position_size, entry_context, entry_cco_status,
                        entry_vol_percentile, entry_regime, entry_timestamp
                    ) VALUES (
                        %s, %s, %s, 'LONG', %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    trade_id,
                    needle['needle_id'],
                    symbol,
                    price,
                    value,
                    entry_context,
                    cco_state['cco_status'] if cco_state else 'UNKNOWN',
                    float(cco_state['current_vol_percentile']) if cco_state else 0,
                    cco_state['current_regime'] if cco_state else 'UNKNOWN',
                    execution_time
                ))

                # Update signal state
                cur.execute("""
                    UPDATE fhq_canonical.g5_signal_state
                    SET
                        current_state = 'PRIMED',
                        primed_at = %s,
                        position_direction = 'LONG',
                        position_entry_price = %s,
                        position_size = %s,
                        last_transition = 'DORMANT_TO_PRIMED',
                        last_transition_at = %s,
                        transition_count = transition_count + 1,
                        updated_at = %s
                    WHERE needle_id = %s
                """, (execution_time, price, value, execution_time, execution_time, needle['needle_id']))

                # Log transition
                cur.execute("""
                    INSERT INTO fhq_canonical.g5_state_transitions (
                        needle_id, from_state, to_state, transition_trigger,
                        context_snapshot, cco_status, transition_valid, transitioned_at
                    ) VALUES (
                        %s, 'DORMANT', 'PRIMED', 'SIGNAL_EXECUTOR_DAEMON',
                        %s, %s, TRUE, %s
                    )
                """, (needle['needle_id'], entry_context, cco_state['cco_status'] if cco_state else 'UNKNOWN', execution_time))

            self.conn.commit()
            logger.info(f"Trade logged successfully: {trade_id} ({symbol})")
            return trade_id

        except Exception as primary_error:
            # =====================================================================
            # FIX C: ATOMIC FALLBACK - If primary fails, log to governance
            # The trade HAS executed at broker. We MUST record it somewhere.
            # =====================================================================
            logger.critical(f"PRIMARY TRADE LOGGING FAILED: {primary_error}")

            try:
                self.conn.rollback()  # Clean up failed transaction

                # Log to governance actions as CRITICAL - this will be visible
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO fhq_governance.governance_actions_log (
                            action_type,
                            action_target,
                            action_target_type,
                            initiated_by,
                            decision,
                            decision_rationale,
                            agent_id,
                            metadata
                        ) VALUES (
                            'TRADE_LOGGING_FAILURE',
                            %s,
                            'CRITICAL_RECOVERY',
                            'SIGNAL_EXECUTOR_DAEMON',
                            'FAILED',
                            %s,
                            'STIG',
                            %s::jsonb
                        )
                    """, (
                        symbol,
                        f"CRITICAL: Trade executed at broker but logging failed. Order ID: {order_id}. Error: {primary_error}",
                        json.dumps({
                            'trade_id': trade_id,
                            'needle_id': str(needle.get('needle_id')),
                            'symbol': symbol,
                            'qty': qty,
                            'price': price,
                            'value': value,
                            'order_id': order_id,
                            'execution_time': execution_time.isoformat(),
                            'primary_error': str(primary_error),
                            'entry_context': entry_context
                        })
                    ))
                self.conn.commit()
                logger.critical(f"RECOVERY LOG CREATED for failed trade: {trade_id}")

            except Exception as recovery_error:
                logger.critical(f"RECOVERY LOGGING ALSO FAILED: {recovery_error}")
                logger.critical(f"MANUAL INTERVENTION REQUIRED: Order {order_id} for {symbol}")

            # Return trade_id even on failure - the trade DID execute
            return trade_id

    # =========================================================================
    # IoS-003-B: FLASH-CONTEXT CONSUMPTION (Intraday Regime-Delta)
    # =========================================================================

    def get_available_flash_contexts(self) -> List[Dict]:
        """
        Get available Flash-Context objects from IoS-003-B.
        These represent intraday regime opportunities with TTL.
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        fc.context_id,
                        fc.delta_id,
                        fc.listing_id,
                        fc.delta_type,
                        fc.intensity,
                        fc.momentum_vector,
                        fc.target_signal_class,
                        fc.applicable_strategies,
                        fc.ttl_minutes,
                        fc.expires_at,
                        rd.canonical_regime,
                        rd.regime_alignment
                    FROM fhq_operational.flash_context fc
                    JOIN fhq_operational.regime_delta rd ON fc.delta_id = rd.delta_id
                    WHERE fc.is_consumed = FALSE
                      AND fc.expires_at > NOW()
                      AND rd.is_active = TRUE
                    ORDER BY fc.intensity DESC, fc.expires_at ASC
                    LIMIT 10
                """)
                return cur.fetchall()
        except Exception as e:
            logger.debug(f"Flash-Context query failed (table may not exist): {e}")
            return []

    def find_matching_dormant_signals(self, flash_context: Dict) -> List[Dict]:
        """
        Find DORMANT signals that could benefit from this Flash-Context.
        Matches based on listing_id (or mapped symbol) and applicable strategies.
        """
        listing_id = flash_context['listing_id']
        strategies = flash_context.get('applicable_strategies', [])
        momentum = flash_context['momentum_vector']

        # Map listing_id to tradeable symbol
        tradeable_symbol = SYMBOL_MAPPING.get(listing_id, listing_id)

        # Get already traded needles to exclude
        traded_needles = self.get_traded_needles()
        traded_clause = ""
        params = [listing_id]

        if traded_needles:
            traded_clause = f"AND gn.needle_id NOT IN ({','.join(['%s'] * len(traded_needles))})"
            params.extend(traded_needles)

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Find signals in DORMANT state that match the Flash-Context asset
            query = f"""
                SELECT
                    ss.state_id,
                    ss.needle_id,
                    ss.current_state,
                    gn.hypothesis_title,
                    gn.hypothesis_category,
                    gn.eqs_score,
                    gn.price_witness_symbol,
                    gn.sitc_confidence_level,
                    gn.regime_technical
                FROM fhq_canonical.g5_signal_state ss
                JOIN fhq_canonical.golden_needles gn ON ss.needle_id = gn.needle_id
                WHERE ss.current_state = 'DORMANT'
                  AND gn.is_current = TRUE
                  AND gn.eqs_score >= %s
                  AND (gn.price_witness_symbol = %s OR gn.price_witness_symbol LIKE %s)
                  {traded_clause}
                ORDER BY gn.eqs_score DESC
                LIMIT 3
            """

            params_full = [DAEMON_CONFIG['min_eqs_score'], listing_id, f"{listing_id.split('-')[0]}%"]
            params_full.extend(traded_needles if traded_needles else [])

            cur.execute(query, params_full)
            return cur.fetchall()

    def consume_flash_context(self, context_id: str, signal_id: str) -> bool:
        """
        Mark a Flash-Context as consumed by a specific signal.
        Logs the consumption for audit trail.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_operational.flash_context
                    SET is_consumed = TRUE,
                        consumed_by_signal_id = %s,
                        consumed_at = NOW()
                    WHERE context_id = %s
                      AND is_consumed = FALSE
                """, (signal_id, context_id))

                if cur.rowcount == 0:
                    logger.warning(f"Flash-Context {context_id[:8]}... already consumed or expired")
                    return False

                # Log the consumption
                cur.execute("""
                    INSERT INTO fhq_operational.delta_log (
                        event_type, context_id, signal_id, details
                    ) VALUES (
                        'CONTEXT_CONSUMED', %s, %s,
                        '{"consumed_by": "SIGNAL_EXECUTOR_DAEMON"}'
                    )
                """, (context_id, signal_id))

                self.conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to consume Flash-Context: {e}")
            self.conn.rollback()
            return False

    def execute_ephemeral_trade(self, needle: Dict, symbol: str,
                                 flash_context: Dict) -> Optional[Dict]:
        """
        Execute an EPHEMERAL_PRIMED trade with reduced position sizing (50%).
        This is for trades triggered by Flash-Context (IoS-003-B).
        """
        if not self.trading_client:
            logger.warning("Alpaca not available - skipping ephemeral execution")
            return None

        # =====================================================================
        # UNIFIED GATEWAY CHECK - MUST BE FIRST (CEO Directive 2025-12-20)
        # No sizing, allocation, or order construction before permission
        # =====================================================================
        if GATEWAY_AVAILABLE:
            source_signal = needle.get('price_witness_symbol', symbol)
            decision = validate_execution_permission(
                symbol=symbol,
                source_signal=source_signal,
                target_state='ACTIVE'
            )
            if not decision.allowed:
                logger.warning(f"EPHEMERAL GATEWAY BLOCKED: {symbol} - {decision.reason}")
                return None
            logger.info(f"EPHEMERAL GATEWAY PERMITTED: {symbol} ({decision.execution_scope})")
        elif HOLIDAY_GATE_AVAILABLE and HOLIDAY_MODE_ENABLED:
            # Fallback to direct holiday gate check
            source_symbol = needle.get('price_witness_symbol', symbol)
            holiday_ok, holiday_reason, asset_class = check_holiday_execution_gate(
                symbol=symbol,
                target_state='ACTIVE',
                source_signal=source_symbol
            )
            if not holiday_ok:
                logger.warning(f"EPHEMERAL HOLIDAY BLOCKED: {symbol} - {holiday_reason}")
                return None

        # =====================================================================
        # HARD EXPOSURE GATE - MANDATORY PRE-EXECUTION CHECK
        # CEO Directive 2025-12-21: Validates ACTUAL Alpaca state before any trade.
        # Fix D: Same-symbol accumulation guard via proposed_symbol
        # =====================================================================
        gate_ok, gate_reason = self.validate_exposure_gate(proposed_symbol=symbol)
        if not gate_ok:
            logger.critical(f"EPHEMERAL EXECUTION BLOCKED by HARD EXPOSURE GATE: {gate_reason}")
            self.log_exposure_violation(gate_reason, {
                'symbol': symbol,
                'needle_id': str(needle.get('needle_id', 'unknown')),
                'flash_context_id': flash_context.get('context_id', 'unknown'),
                'attempted_action': 'EPHEMERAL_TRADE_EXECUTION',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            return None

        # WAVE 17D.1 FIX: Check for existing pending orders
        try:
            open_orders = self.trading_client.get_orders(
                GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
            )
            if open_orders:
                logger.info(f"Pending order exists for {symbol} - skipping ephemeral")
                return None
        except Exception as e:
            logger.warning(f"Could not check pending orders: {e}")

        # Calculate position size with EPHEMERAL SCALAR (50%)
        shares, dollar_amount, entry_price = self.calculate_position_size(
            symbol,
            float(needle['eqs_score']),
            needle['sitc_confidence_level']
        )

        # Apply 50% reduction for ephemeral trades (conservative due to intraday context)
        ephemeral_scalar = 0.5
        shares = int(shares * ephemeral_scalar)
        dollar_amount = dollar_amount * ephemeral_scalar

        if shares < 1:
            logger.warning(f"Ephemeral position too small for {symbol} - skipping")
            return None

        logger.info(f"EPHEMERAL TRADE: BUY {shares} {symbol} @ ${entry_price:.2f} (~${dollar_amount:,.2f})")
        logger.info(f"  Flash-Context: {flash_context['delta_type']} | Intensity: {flash_context['intensity']:.4f}")

        try:
            order = self.trading_client.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
            )

            time.sleep(1)
            filled_order = self.trading_client.get_order_by_id(order.id)

            if filled_order.status in ['filled', 'partially_filled']:
                filled_qty = float(filled_order.filled_qty)
                filled_price = float(filled_order.filled_avg_price)
                position_value = filled_qty * filled_price

                logger.info(f"EPHEMERAL FILLED: {int(filled_qty)} {symbol} @ ${filled_price:.2f}")

                # Log to database with ephemeral context
                trade_id = self._log_ephemeral_trade(
                    needle, symbol, filled_qty, filled_price, position_value,
                    order.id, flash_context
                )

                # Consume the Flash-Context
                self.consume_flash_context(
                    flash_context['context_id'],
                    str(needle['needle_id'])
                )

                return {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'qty': filled_qty,
                    'price': filled_price,
                    'value': position_value,
                    'order_id': str(order.id),
                    'ephemeral': True,
                    'flash_context_id': flash_context['context_id']
                }
            else:
                logger.warning(f"Ephemeral order not filled: {filled_order.status}")
                return None

        except Exception as e:
            logger.error(f"Ephemeral trade execution failed: {e}")
            return None

    def _log_ephemeral_trade(
        self,
        needle: Dict,
        symbol: str,
        qty: float,
        price: float,
        value: float,
        order_id: str,
        flash_context: Dict
    ) -> str:
        """Log ephemeral trade to database with IoS-003-B context"""
        trade_id = str(uuid.uuid4())
        cco_state = self.get_cco_state()

        entry_context = json.dumps({
            'cco_status': cco_state['cco_status'] if cco_state else 'UNKNOWN',
            'global_permit': cco_state['global_permit'] if cco_state else 'UNKNOWN',
            'regime': cco_state['current_regime'] if cco_state else 'UNKNOWN',
            'vol_percentile': float(cco_state['current_vol_percentile']) if cco_state else 0,
            'needle_title': needle['hypothesis_title'],
            'needle_category': needle['hypothesis_category'],
            'eqs_score': float(needle['eqs_score']),
            'alpaca_order_id': order_id,
            'kelly_multiplier': DAEMON_CONFIG['kelly_multiplier'],
            'ephemeral_scalar': 0.5,  # 50% position sizing
            'target_pct': DAEMON_CONFIG['default_target_pct'],
            'stop_loss_pct': DAEMON_CONFIG['default_stop_loss_pct'],
            'executed_by': 'SIGNAL_EXECUTOR_DAEMON',
            'execution_type': 'EPHEMERAL_PRIMED',
            'flash_context_id': flash_context['context_id'],
            'flash_delta_type': flash_context['delta_type'],
            'flash_intensity': float(flash_context['intensity']),
            'flash_momentum': flash_context['momentum_vector'],
            'flash_expires_at': flash_context['expires_at'].isoformat() if hasattr(flash_context['expires_at'], 'isoformat') else str(flash_context['expires_at']),
            'execution_timestamp': datetime.now(timezone.utc).isoformat()
        })

        with self.conn.cursor() as cur:
            # Log paper trade
            cur.execute("""
                INSERT INTO fhq_canonical.g5_paper_trades (
                    trade_id, needle_id, symbol, direction, entry_price,
                    position_size, entry_context, entry_cco_status,
                    entry_vol_percentile, entry_regime, entry_timestamp
                ) VALUES (
                    %s, %s, %s, 'LONG', %s, %s, %s, %s, %s, %s, NOW()
                )
            """, (
                trade_id,
                needle['needle_id'],
                symbol,
                price,
                value,
                entry_context,
                cco_state['cco_status'] if cco_state else 'UNKNOWN',
                float(cco_state['current_vol_percentile']) if cco_state else 0,
                cco_state['current_regime'] if cco_state else 'UNKNOWN'
            ))

            # Update signal state to PRIMED with ephemeral flag
            cur.execute("""
                UPDATE fhq_canonical.g5_signal_state
                SET
                    current_state = 'PRIMED',
                    primed_at = NOW(),
                    position_direction = 'LONG',
                    position_entry_price = %s,
                    position_size = %s,
                    is_ephemeral_promotion = TRUE,
                    ephemeral_context_id = %s,
                    ephemeral_primed_at = NOW(),
                    ephemeral_expires_at = %s,
                    ephemeral_position_scalar = 0.5,
                    last_transition = 'DORMANT_TO_EPHEMERAL_PRIMED',
                    last_transition_at = NOW(),
                    transition_count = transition_count + 1,
                    updated_at = NOW()
                WHERE needle_id = %s
            """, (price, value, flash_context['context_id'],
                  flash_context['expires_at'], needle['needle_id']))

            # Log transition
            cur.execute("""
                INSERT INTO fhq_canonical.g5_state_transitions (
                    needle_id, from_state, to_state, transition_trigger,
                    context_snapshot, cco_status, transition_valid, transitioned_at
                ) VALUES (
                    %s, 'DORMANT', 'PRIMED', 'EPHEMERAL_FLASH_CONTEXT',
                    %s, %s, TRUE, NOW()
                )
            """, (needle['needle_id'], entry_context,
                  cco_state['cco_status'] if cco_state else 'UNKNOWN'))

            # Log to delta_log
            cur.execute("""
                INSERT INTO fhq_operational.delta_log (
                    event_type, context_id, signal_id, listing_id, details
                ) VALUES (
                    'EPHEMERAL_PRIMED', %s, %s, %s, %s
                )
            """, (
                flash_context['context_id'],
                str(needle['needle_id']),
                flash_context['listing_id'],
                json.dumps({
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'position_value': value,
                    'ephemeral_scalar': 0.5
                })
            ))

        self.conn.commit()
        return trade_id

    def process_flash_contexts(self) -> Dict:
        """
        Process available Flash-Contexts from IoS-003-B.
        Attempts to match and execute EPHEMERAL_PRIMED trades.
        """
        result = {
            'contexts_available': 0,
            'contexts_matched': 0,
            'ephemeral_trades': 0,
            'details': []
        }

        flash_contexts = self.get_available_flash_contexts()
        result['contexts_available'] = len(flash_contexts)

        if not flash_contexts:
            return result

        open_count = self.get_open_positions_count()
        if open_count >= DAEMON_CONFIG['max_concurrent_positions']:
            logger.debug("Max positions reached - skipping Flash-Context processing")
            return result

        for fc in flash_contexts:
            # Find matching dormant signals
            matching_signals = self.find_matching_dormant_signals(fc)

            if not matching_signals:
                continue

            result['contexts_matched'] += 1

            # Execute for best matching signal
            for signal in matching_signals:
                # Map to tradeable symbol
                witness = signal.get('price_witness_symbol', '')
                symbol = SYMBOL_MAPPING.get(witness)

                if not symbol or '/' in symbol:
                    # Use proxy for crypto
                    candidates = PROXY_SYMBOLS.get(witness, PROXY_SYMBOLS['default'])
                    open_symbols = self.get_open_symbols()
                    available = [s for s in candidates if s not in open_symbols]
                    symbol = available[0] if available else None

                if not symbol:
                    continue

                # Execute ephemeral trade
                trade = self.execute_ephemeral_trade(signal, symbol, fc)

                if trade:
                    result['ephemeral_trades'] += 1
                    result['details'].append({
                        'context_id': fc['context_id'][:8],
                        'delta_type': fc['delta_type'],
                        'symbol': symbol,
                        'trade_id': trade['trade_id'][:8]
                    })
                    break  # One trade per Flash-Context

                # Check position limit after each trade
                if self.get_open_positions_count() >= DAEMON_CONFIG['max_concurrent_positions']:
                    return result

        return result

    # =========================================================================
    # MAIN EXECUTION LOOP
    # =========================================================================

    def run_cycle(self) -> Dict:
        """Run one execution cycle"""
        self.cycle_count += 1
        result = {
            'cycle': self.cycle_count,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'permitted': False,
            'trades_executed': 0,
            'ephemeral_trades': 0,  # IoS-003-B Flash-Context trades
            'exits_triggered': 0,
            'exposure_gate_status': 'UNKNOWN',
            'reason': ''
        }

        # =====================================================================
        # PHASE 0: HARD EXPOSURE GATE CHECK (CEO Directive: Critical Risk Control)
        # This runs EVERY cycle to detect and log exposure violations.
        # =====================================================================
        gate_ok, gate_reason = self.validate_exposure_gate()
        result['exposure_gate_status'] = 'PASSED' if gate_ok else 'BLOCKED'

        if not gate_ok:
            logger.critical(f"=" * 60)
            logger.critical(f"HARD EXPOSURE GATE VIOLATION DETECTED")
            logger.critical(f"Reason: {gate_reason}")
            logger.critical(f"ALL NEW TRADES ARE BLOCKED")
            logger.critical(f"=" * 60)
            # Log to governance (once per minute to avoid spam)
            if self.cycle_count % 1 == 0:  # Every cycle for now during active violation
                self.log_exposure_violation(gate_reason, {
                    'cycle': self.cycle_count,
                    'detection_type': 'CYCLE_START_CHECK',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

            # =====================================================================
            # FIX A (CEO Directive 2025-12-21): EXPOSURE GATE MUST BLOCK
            # If gate fails, we ONLY allow position monitoring (exits).
            # NO new trades are permitted. Logging without blocking is forbidden.
            # =====================================================================
            # Phase 1: Monitor existing positions (exits only)
            monitor_result = self.monitor_positions()
            result['exits_triggered'] = monitor_result['exits_triggered']
            result['reason'] = f"EXPOSURE GATE BLOCKED: {gate_reason}"

            if monitor_result['exits_triggered'] > 0:
                for exit in monitor_result['exits']:
                    pnl = exit.get('realized_pnl', 0)
                    pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                    logger.info(f"EXIT: {exit['symbol']} | {exit['reason']} | P/L: {pnl_str}")

            # CRITICAL: Return early - NO new trades when gate fails
            return result

        # =====================================================================
        # PHASE 1: MONITOR EXISTING POSITIONS (Always runs, even when suppressed)
        # =====================================================================
        monitor_result = self.monitor_positions()
        result['exits_triggered'] = monitor_result['exits_triggered']

        if monitor_result['exits_triggered'] > 0:
            for exit in monitor_result['exits']:
                pnl = exit.get('realized_pnl', 0)
                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                logger.info(f"EXIT: {exit['symbol']} | {exit['reason']} | P/L: {pnl_str}")

        # =====================================================================
        # PHASE 2: CHECK CCO PERMIT FOR NEW ENTRIES
        # =====================================================================
        permitted, reason = self.is_execution_permitted()
        result['permitted'] = permitted
        result['reason'] = reason

        # Track state changes
        if permitted != self.last_permit_status:
            if permitted:
                logger.info(f"CCO PERMITTED - Execution enabled")
                self.suppressed_cycles = 0
            else:
                if self.last_permit_status is not None:
                    logger.info(f"CCO SUPPRESSED - {reason}")
            self.last_permit_status = permitted

        if not permitted:
            self.suppressed_cycles += 1
            # Log every 10 cycles when suppressed
            if self.suppressed_cycles % 10 == 0:
                logger.debug(f"Waiting... ({self.suppressed_cycles} cycles suppressed)")
            return result

        # =====================================================================
        # PHASE 2.5: IoS-003-B FLASH-CONTEXT PROCESSING (Ephemeral Opportunities)
        # =====================================================================
        flash_result = self.process_flash_contexts()
        result['ephemeral_trades'] = flash_result.get('ephemeral_trades', 0)

        if flash_result['ephemeral_trades'] > 0:
            for detail in flash_result['details']:
                logger.info(f"EPHEMERAL: {detail['symbol']} via {detail['delta_type']} context")

        # =====================================================================
        # PHASE 3: EXECUTE NEW ENTRIES (Only when permitted)
        # =====================================================================
        open_count = self.get_open_positions_count()
        if open_count >= DAEMON_CONFIG['max_concurrent_positions']:
            result['reason'] = f"Max positions reached ({open_count}/{DAEMON_CONFIG['max_concurrent_positions']})"
            logger.debug(result['reason'])
            return result

        # Get executable needles
        slots_available = DAEMON_CONFIG['max_concurrent_positions'] - open_count
        needles = self.get_executable_needles(limit=slots_available)

        if not needles:
            result['reason'] = "No executable needles found"
            return result

        # Execute trades
        for needle in needles:
            symbol = self.select_symbol_for_needle(needle)
            if not symbol:
                logger.debug(f"No symbol available for needle {needle['needle_id']}")
                continue

            trade = self.execute_trade(needle, symbol)
            if trade:
                result['trades_executed'] += 1
                logger.info(f"Trade logged: {trade['trade_id'][:8]}... {trade['symbol']}")

                # Check if we've hit max positions
                if self.get_open_positions_count() >= DAEMON_CONFIG['max_concurrent_positions']:
                    break

        return result

    def run(self, max_cycles: int = None):
        """Run the daemon continuously"""
        logger.info("=" * 60)
        logger.info("SIGNAL EXECUTOR DAEMON - Starting")
        logger.info(f"CEO Directive: CD-IOS-001-PRICE-ARCH-001")
        logger.info(f"Orchestrator: FHQ-IoS001-Bulletproof-EQUITY")
        logger.info("=" * 60)
        logger.info(f"Mode: PAPER ONLY")
        logger.info(f"Cycle Interval: {DAEMON_CONFIG['cycle_interval_seconds']}s")
        logger.info(f"Max Positions: {DAEMON_CONFIG['max_concurrent_positions']}")
        logger.info(f"Min EQS: {DAEMON_CONFIG['min_eqs_score']}")
        logger.info(f"Take Profit: +{DAEMON_CONFIG['default_target_pct']*100:.1f}%")
        logger.info(f"Stop Loss: -{DAEMON_CONFIG['default_stop_loss_pct']*100:.1f}%")
        logger.info("-" * 60)
        logger.info(f"Direct Equities: {len(DIRECT_EQUITY_SYMBOLS)} symbols")
        logger.info(f"Symbol Mappings: {len(SYMBOL_MAPPING)} configured")
        logger.info(f"Multi-Asset: Crypto → Proxy Equities (MSTR, COIN, MARA)")
        logger.info("=" * 60)

        self.running = True

        try:
            while self.running:
                result = self.run_cycle()

                if result['trades_executed'] > 0:
                    logger.info(f"Cycle {result['cycle']}: {result['trades_executed']} trade(s) executed")

                if max_cycles and self.cycle_count >= max_cycles:
                    logger.info(f"Reached max cycles ({max_cycles})")
                    break

                time.sleep(DAEMON_CONFIG['cycle_interval_seconds'])

        except KeyboardInterrupt:
            logger.info("\nShutdown requested...")
        finally:
            self.running = False
            logger.info("Signal Executor Daemon stopped")

    def stop(self):
        """Stop the daemon"""
        self.running = False


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Signal Executor Daemon (Paper Mode)')
    parser.add_argument('--once', action='store_true', help='Run single cycle and exit')
    parser.add_argument('--max-cycles', type=int, help='Maximum cycles to run')
    parser.add_argument('--interval', type=int, default=60, help='Cycle interval in seconds')
    args = parser.parse_args()

    if args.interval:
        DAEMON_CONFIG['cycle_interval_seconds'] = args.interval

    daemon = SignalExecutorDaemon()

    if not daemon.connect():
        logger.error("Failed to connect")
        sys.exit(1)

    try:
        if args.once:
            result = daemon.run_cycle()
            print(f"\nCycle Result:")
            print(f"  Permitted: {result['permitted']}")
            print(f"  Reason: {result['reason']}")
            print(f"  Trades: {result['trades_executed']}")
        else:
            daemon.run(max_cycles=args.max_cycles)
    finally:
        daemon.close()


if __name__ == "__main__":
    main()
