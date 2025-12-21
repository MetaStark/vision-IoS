#!/usr/bin/env python3
"""
BROKER TRUTH ENFORCER
=====================
CEO Directive 2025-12-21, Section 2: Source-of-Truth Reassertion

This module enforces the non-negotiable principle:

    ALPACA IS THE SOLE AND EXCLUSIVE SOURCE OF TRUTH FOR:
    - Positions
    - Exposure
    - Leverage
    - Cash balance
    - Portfolio value

DATABASE STATE IS DERIVATIVE, NEVER AUTHORITATIVE.

Any logic that queries the database for position/exposure information
for decision-making is INVALID BY DEFINITION.

This module provides the ONLY approved methods for querying execution state.
All execution logic MUST use these methods instead of database queries.

Author: STIG (CTO)
Classification: CRITICAL SECURITY INFRASTRUCTURE
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('BROKER_TRUTH')

# =============================================================================
# BROKER CLIENT INITIALIZATION
# =============================================================================

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("Alpaca SDK not available")

# Initialize broker client
_broker_client: Optional[TradingClient] = None

def get_broker_client() -> Optional[TradingClient]:
    """Get or create the broker client singleton."""
    global _broker_client
    if _broker_client is None and ALPACA_AVAILABLE:
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET', os.getenv('ALPACA_SECRET_KEY'))
        if api_key and secret_key:
            _broker_client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=True
            )
    return _broker_client


# =============================================================================
# BROKER TRUTH DATA CLASSES
# =============================================================================

@dataclass
class BrokerPosition:
    """Position data from broker (source of truth)."""
    symbol: str
    qty: float
    side: str
    market_value: float
    avg_entry_price: float
    unrealized_pl: float
    asset_id: str


@dataclass
class BrokerAccountState:
    """Account state from broker (source of truth)."""
    portfolio_value: float
    cash: float
    equity: float
    buying_power: float
    positions: List[BrokerPosition]
    is_margin_used: bool  # True if cash < 0
    total_exposure: float
    largest_position_value: float
    largest_position_symbol: Optional[str]
    timestamp: str


# =============================================================================
# BROKER TRUTH FUNCTIONS (MANDATORY FOR ALL EXECUTION LOGIC)
# =============================================================================

def get_broker_account_state() -> Optional[BrokerAccountState]:
    """
    Get current account state from BROKER (not database).

    This is the ONLY approved method for getting execution state.
    DO NOT query database for this information.

    Returns:
        BrokerAccountState or None if broker unavailable
    """
    client = get_broker_client()
    if not client:
        logger.error("BROKER UNAVAILABLE - Cannot get account state")
        return None

    try:
        account = client.get_account()
        positions = client.get_all_positions()

        broker_positions = []
        total_exposure = 0.0
        largest_value = 0.0
        largest_symbol = None

        for p in positions:
            mv = float(p.market_value)
            total_exposure += abs(mv)

            if mv > largest_value:
                largest_value = mv
                largest_symbol = p.symbol

            broker_positions.append(BrokerPosition(
                symbol=p.symbol,
                qty=float(p.qty),
                side=str(p.side),
                market_value=mv,
                avg_entry_price=float(p.avg_entry_price),
                unrealized_pl=float(p.unrealized_pl),
                asset_id=str(p.asset_id)
            ))

        cash = float(account.cash)

        return BrokerAccountState(
            portfolio_value=float(account.portfolio_value),
            cash=cash,
            equity=float(account.equity),
            buying_power=float(account.buying_power),
            positions=broker_positions,
            is_margin_used=cash < 0,
            total_exposure=total_exposure,
            largest_position_value=largest_value,
            largest_position_symbol=largest_symbol,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to get broker account state: {e}")
        return None


def get_open_position_count() -> int:
    """
    Get count of open positions from BROKER (not database).

    REPLACES: get_open_positions_count() database query
    """
    state = get_broker_account_state()
    return len(state.positions) if state else 0


def get_open_symbols() -> List[str]:
    """
    Get list of symbols with open positions from BROKER (not database).

    REPLACES: get_open_symbols() database query
    """
    state = get_broker_account_state()
    return [p.symbol for p in state.positions] if state else []


def has_position_for_symbol(symbol: str) -> bool:
    """
    Check if a position exists for a symbol from BROKER (not database).

    Use this to prevent same-symbol accumulation.
    """
    open_symbols = get_open_symbols()
    return symbol in open_symbols


def get_exposure_metrics() -> Optional[Dict]:
    """
    Get exposure metrics from BROKER (not database).

    Returns dict with:
        - total_exposure_pct
        - largest_position_pct
        - largest_position_usd
        - cash_reserve_pct
        - is_using_margin
    """
    state = get_broker_account_state()
    if not state:
        return None

    pv = state.portfolio_value
    if pv <= 0:
        return None

    return {
        'total_exposure_pct': state.total_exposure / pv,
        'largest_position_pct': state.largest_position_value / pv,
        'largest_position_usd': state.largest_position_value,
        'largest_position_symbol': state.largest_position_symbol,
        'cash_reserve_pct': state.cash / pv,
        'is_using_margin': state.is_margin_used,
        'position_count': len(state.positions),
        'timestamp': state.timestamp
    }


def get_pending_orders(symbol: Optional[str] = None) -> List[Dict]:
    """
    Get pending orders from BROKER (not database).

    Args:
        symbol: Optional filter by symbol
    """
    client = get_broker_client()
    if not client:
        return []

    try:
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        if symbol:
            request = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])

        orders = client.get_orders(request)
        return [
            {
                'order_id': str(o.id),
                'symbol': o.symbol,
                'side': str(o.side),
                'qty': str(o.qty),
                'status': str(o.status),
                'type': str(o.type),
                'created_at': str(o.created_at)
            }
            for o in orders
        ]
    except Exception as e:
        logger.error(f"Failed to get pending orders: {e}")
        return []


# =============================================================================
# EXPOSURE GATE (BROKER-BASED)
# =============================================================================

def validate_exposure_from_broker(
    proposed_trade_usd: float = 0,
    proposed_symbol: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Validate exposure limits using BROKER state (not database).

    This is the MANDATORY replacement for database-based exposure checks.

    Args:
        proposed_trade_usd: Size of proposed trade in USD
        proposed_symbol: Symbol for proposed trade (for same-symbol check)

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    metrics = get_exposure_metrics()

    if metrics is None:
        return False, "BROKER UNAVAILABLE - Cannot validate exposure"

    # HARD LIMITS (CEO Directive)
    MAX_SINGLE_POSITION_PCT = 0.25
    MAX_TOTAL_EXPOSURE_PCT = 1.00
    MAX_SINGLE_POSITION_USD = 50000
    MIN_CASH_RESERVE_PCT = 0.10

    # GATE 1: Check if using margin (negative cash)
    if metrics['is_using_margin']:
        return False, f"MARGIN VIOLATION: Cash is negative"

    # GATE 2: Check total exposure
    if metrics['total_exposure_pct'] > MAX_TOTAL_EXPOSURE_PCT:
        return False, f"TOTAL EXPOSURE VIOLATION: {metrics['total_exposure_pct']:.1%} exceeds {MAX_TOTAL_EXPOSURE_PCT:.0%}"

    # GATE 3: Check largest single position percentage
    if metrics['largest_position_pct'] > MAX_SINGLE_POSITION_PCT:
        return False, f"SINGLE POSITION VIOLATION: {metrics['largest_position_symbol']} at {metrics['largest_position_pct']:.1%} exceeds {MAX_SINGLE_POSITION_PCT:.0%}"

    # GATE 4: Check largest position absolute USD
    if metrics['largest_position_usd'] > MAX_SINGLE_POSITION_USD:
        return False, f"ABSOLUTE USD VIOLATION: {metrics['largest_position_symbol']} at ${metrics['largest_position_usd']:,.0f} exceeds ${MAX_SINGLE_POSITION_USD:,.0f}"

    # GATE 5: Same-symbol accumulation guard
    if proposed_symbol and has_position_for_symbol(proposed_symbol):
        return False, f"SAME-SYMBOL VIOLATION: Already have position in {proposed_symbol}"

    # GATE 6: Check if proposed trade would exceed limits
    if proposed_trade_usd > 0:
        state = get_broker_account_state()
        if state:
            projected_exposure = (metrics['total_exposure_pct'] * state.portfolio_value + proposed_trade_usd) / state.portfolio_value
            if projected_exposure > MAX_TOTAL_EXPOSURE_PCT:
                return False, f"PROJECTED EXPOSURE VIOLATION: Would reach {projected_exposure:.1%}"

            if proposed_trade_usd > MAX_SINGLE_POSITION_USD:
                return False, f"PROPOSED TRADE VIOLATION: ${proposed_trade_usd:,.0f} exceeds ${MAX_SINGLE_POSITION_USD:,.0f}"

    # GATE 7: Check minimum cash reserve
    if metrics['cash_reserve_pct'] < MIN_CASH_RESERVE_PCT and proposed_trade_usd > 0:
        return False, f"CASH RESERVE VIOLATION: {metrics['cash_reserve_pct']:.1%} below {MIN_CASH_RESERVE_PCT:.0%}"

    # GATE 8: Check for pending orders on same symbol
    if proposed_symbol:
        pending = get_pending_orders(proposed_symbol)
        if pending:
            return False, f"PENDING ORDER EXISTS: {len(pending)} pending order(s) for {proposed_symbol}"

    return True, "OK"


# =============================================================================
# VERIFICATION
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("BROKER TRUTH ENFORCER")
    print("CEO Directive 2025-12-21: Alpaca is sole source of truth")
    print("=" * 70)

    state = get_broker_account_state()
    if state:
        print(f"\nPortfolio Value: ${state.portfolio_value:,.2f}")
        print(f"Cash: ${state.cash:,.2f}")
        print(f"Margin Used: {state.is_margin_used}")
        print(f"Total Exposure: ${state.total_exposure:,.2f}")
        print(f"Positions: {len(state.positions)}")

        if state.positions:
            print("\nOpen Positions (BROKER TRUTH):")
            for p in state.positions:
                print(f"  {p.symbol}: {p.qty} shares @ ${p.avg_entry_price:.2f} = ${p.market_value:,.2f}")

        print("\nExposure Gate Check:")
        ok, reason = validate_exposure_from_broker()
        print(f"  Status: {'PASSED' if ok else 'BLOCKED'}")
        print(f"  Reason: {reason}")
    else:
        print("BROKER UNAVAILABLE")
