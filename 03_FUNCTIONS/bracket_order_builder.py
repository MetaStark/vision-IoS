"""
Bracket Order Builder - Alpaca-native OTOCO Orders
CEO-DIR-2026-01-22: Use BRACKET primitive, NOT three loose orders

Builds Alpaca-native bracket orders from Decision Packs.
- Entry: LIMIT order
- Take Profit: LIMIT order (OCO)
- Stop Loss: STOP or STOP_LIMIT order (OCO)

Author: STIG (CTO)
Contract: EC-003_2026_PRODUCTION
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class BracketOrderSpec:
    """Alpaca-native BRACKET order specification."""
    symbol: str
    side: str                     # 'buy' or 'sell'
    qty: float
    entry_type: str               # 'limit'
    entry_limit_price: float
    take_profit_price: float
    stop_loss_price: float
    stop_loss_type: str           # 'stop' or 'stop_limit'
    stop_limit_price: Optional[float]
    time_in_force: str            # 'gtc' or 'day'
    order_class: str = 'bracket'  # Alpaca OrderClass.BRACKET
    client_order_id: Optional[str] = None


# =============================================================================
# ORDER BUILDER
# =============================================================================

def build_bracket_order_from_pack(decision_pack) -> BracketOrderSpec:
    """
    Build Alpaca-native BRACKET order from Decision Pack.

    CEO Requirements:
    - Use BRACKET/OTOCO primitive (NOT three loose orders)
    - Stop type decision: stop-market for tail risk, stop-limit for price control

    Args:
        decision_pack: Complete DecisionPack object

    Returns:
        BracketOrderSpec ready for Alpaca submission
    """
    # Determine side from direction
    side = 'buy' if decision_pack.direction == 'LONG' else 'sell'

    # Use stop type from Decision Pack (determined by EWRE based on regime)
    stop_type = 'stop_limit' if decision_pack.stop_type == 'STOP_LIMIT' else 'stop'

    # Generate client order ID for tracking
    client_order_id = f"EWRE-{str(decision_pack.pack_id)[:8]}"

    spec = BracketOrderSpec(
        symbol=_normalize_symbol(decision_pack.asset),
        side=side,
        qty=decision_pack.position_qty,
        entry_type='limit',
        entry_limit_price=decision_pack.entry_limit_price,
        take_profit_price=decision_pack.take_profit_price,
        stop_loss_price=decision_pack.stop_loss_price,
        stop_loss_type=stop_type,
        stop_limit_price=decision_pack.stop_limit_price,
        time_in_force='gtc',
        order_class='bracket',
        client_order_id=client_order_id
    )

    logger.info(f"[BracketBuilder] Built order: {spec.symbol} {spec.side.upper()} "
                f"{spec.qty} @ ${spec.entry_limit_price:,.2f}, "
                f"TP=${spec.take_profit_price:,.2f}, SL=${spec.stop_loss_price:,.2f}")

    return spec


def _normalize_symbol(asset: str) -> str:
    """
    Normalize asset symbol for Alpaca API.

    Examples:
        BTC/USD -> BTC/USD (crypto)
        BTC-USD -> BTC/USD (crypto)
        SPY -> SPY (equity)
    """
    # Crypto symbols need slash format
    if '-' in asset:
        asset = asset.replace('-', '/')

    return asset


# =============================================================================
# ALPACA SUBMISSION
# =============================================================================

def submit_bracket_to_alpaca(
    trading_client,
    order_spec: BracketOrderSpec
) -> Dict[str, Any]:
    """
    Submit bracket order to Alpaca.

    Args:
        trading_client: Alpaca TradingClient instance
        order_spec: BracketOrderSpec to submit

    Returns:
        Dict with order_id, status, and other Alpaca response fields
    """
    from alpaca.trading.requests import LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

    try:
        side = OrderSide.BUY if order_spec.side == 'buy' else OrderSide.SELL
        tif = TimeInForce.GTC if order_spec.time_in_force == 'gtc' else TimeInForce.DAY

        # Build bracket order request
        if order_spec.stop_loss_type == 'stop_limit' and order_spec.stop_limit_price:
            # Stop-limit for price control
            from alpaca.trading.requests import TakeProfitRequest, StopLossRequest

            request = LimitOrderRequest(
                symbol=order_spec.symbol,
                qty=order_spec.qty,
                side=side,
                time_in_force=tif,
                limit_price=order_spec.entry_limit_price,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(
                    limit_price=order_spec.take_profit_price
                ),
                stop_loss=StopLossRequest(
                    stop_price=order_spec.stop_loss_price,
                    limit_price=order_spec.stop_limit_price
                ),
                client_order_id=order_spec.client_order_id
            )
        else:
            # Stop-market for guaranteed exit
            from alpaca.trading.requests import TakeProfitRequest, StopLossRequest

            request = LimitOrderRequest(
                symbol=order_spec.symbol,
                qty=order_spec.qty,
                side=side,
                time_in_force=tif,
                limit_price=order_spec.entry_limit_price,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(
                    limit_price=order_spec.take_profit_price
                ),
                stop_loss=StopLossRequest(
                    stop_price=order_spec.stop_loss_price
                ),
                client_order_id=order_spec.client_order_id
            )

        # Submit order
        logger.info(f"[BracketBuilder] Submitting to Alpaca: {order_spec.symbol}")
        order = trading_client.submit_order(request)

        result = {
            'order_id': str(order.id),
            'client_order_id': order.client_order_id,
            'status': order.status.value,
            'symbol': order.symbol,
            'qty': float(order.qty),
            'side': order.side.value,
            'order_class': order.order_class.value if order.order_class else None,
            'submitted_at': order.submitted_at.isoformat() if order.submitted_at else None,
            'legs': []
        }

        # Capture leg information
        if hasattr(order, 'legs') and order.legs:
            for leg in order.legs:
                result['legs'].append({
                    'leg_id': str(leg.id),
                    'leg_type': leg.order_type.value if leg.order_type else None,
                    'limit_price': float(leg.limit_price) if leg.limit_price else None,
                    'stop_price': float(leg.stop_price) if leg.stop_price else None
                })

        logger.info(f"[BracketBuilder] Order submitted: {result['order_id']}, "
                    f"status={result['status']}")

        return result

    except Exception as e:
        logger.error(f"[BracketBuilder] Alpaca submission failed: {e}")
        return {
            'error': str(e),
            'order_id': None,
            'status': 'FAILED'
        }


def validate_bracket_spec(order_spec: BracketOrderSpec) -> tuple[bool, str]:
    """
    Validate bracket order specification before submission.

    Checks:
    - All required fields present
    - Price relationships valid for direction
    - Quantity positive

    Returns:
        Tuple of (valid, reason)
    """
    # Check required fields
    if not order_spec.symbol:
        return False, "SYMBOL_MISSING"

    if not order_spec.qty or order_spec.qty <= 0:
        return False, "INVALID_QUANTITY"

    if not order_spec.entry_limit_price or order_spec.entry_limit_price <= 0:
        return False, "INVALID_ENTRY_PRICE"

    if not order_spec.take_profit_price or order_spec.take_profit_price <= 0:
        return False, "INVALID_TP_PRICE"

    if not order_spec.stop_loss_price or order_spec.stop_loss_price <= 0:
        return False, "INVALID_SL_PRICE"

    # Validate price relationships
    if order_spec.side == 'buy':
        # LONG: TP > Entry > SL
        if order_spec.take_profit_price <= order_spec.entry_limit_price:
            return False, "TP_MUST_BE_ABOVE_ENTRY_FOR_LONG"
        if order_spec.stop_loss_price >= order_spec.entry_limit_price:
            return False, "SL_MUST_BE_BELOW_ENTRY_FOR_LONG"
    else:
        # SHORT: TP < Entry < SL
        if order_spec.take_profit_price >= order_spec.entry_limit_price:
            return False, "TP_MUST_BE_BELOW_ENTRY_FOR_SHORT"
        if order_spec.stop_loss_price <= order_spec.entry_limit_price:
            return False, "SL_MUST_BE_ABOVE_ENTRY_FOR_SHORT"

    # Validate stop-limit price if present
    if order_spec.stop_loss_type == 'stop_limit':
        if not order_spec.stop_limit_price:
            return False, "STOP_LIMIT_PRICE_MISSING"

        if order_spec.side == 'buy':
            # For LONG, stop limit should be below stop price
            if order_spec.stop_limit_price > order_spec.stop_loss_price:
                return False, "STOP_LIMIT_SHOULD_BE_BELOW_STOP_FOR_LONG"
        else:
            # For SHORT, stop limit should be above stop price
            if order_spec.stop_limit_price < order_spec.stop_loss_price:
                return False, "STOP_LIMIT_SHOULD_BE_ABOVE_STOP_FOR_SHORT"

    return True, "VALID"


# =============================================================================
# PAPER MODE WRAPPER
# =============================================================================

def submit_bracket_paper_mode(order_spec: BracketOrderSpec) -> Dict[str, Any]:
    """
    Submit bracket order in paper trading mode.

    Uses Alpaca paper trading environment.
    """
    from dotenv import load_dotenv
    # Load from project root .env
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), override=True)

    # Get paper trading credentials (support both ALPACA_SECRET and ALPACA_SECRET_KEY)
    api_key = os.getenv('ALPACA_API_KEY_PAPER', os.getenv('ALPACA_API_KEY'))
    secret_key = os.getenv('ALPACA_SECRET_KEY_PAPER',
                          os.getenv('ALPACA_SECRET_KEY', os.getenv('ALPACA_SECRET')))

    if not api_key or not secret_key:
        logger.error("[BracketBuilder] Alpaca credentials not found")
        return {'error': 'CREDENTIALS_MISSING', 'order_id': None, 'status': 'FAILED'}

    try:
        from alpaca.trading.client import TradingClient

        # Use paper=True for paper trading
        trading_client = TradingClient(api_key, secret_key, paper=True)

        return submit_bracket_to_alpaca(trading_client, order_spec)

    except Exception as e:
        logger.error(f"[BracketBuilder] Paper mode submission failed: {e}")
        return {'error': str(e), 'order_id': None, 'status': 'FAILED'}


# =============================================================================
# TESTING
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Bracket Order Builder Test")
    print("=" * 60)

    # Test validation
    test_specs = [
        BracketOrderSpec(
            symbol="BTC/USD",
            side="buy",
            qty=0.05,
            entry_type="limit",
            entry_limit_price=103450.0,
            take_profit_price=111726.0,
            stop_loss_price=98278.0,
            stop_loss_type="stop_limit",
            stop_limit_price=97786.0,
            time_in_force="gtc",
            client_order_id="TEST-001"
        ),
        BracketOrderSpec(
            symbol="SPY",
            side="sell",
            qty=10,
            entry_type="limit",
            entry_limit_price=580.0,
            take_profit_price=560.0,  # Short: TP below entry
            stop_loss_price=595.0,    # Short: SL above entry
            stop_loss_type="stop",
            stop_limit_price=None,
            time_in_force="day",
            client_order_id="TEST-002"
        )
    ]

    for i, spec in enumerate(test_specs, 1):
        print(f"\nTest {i}: {spec.symbol} {spec.side.upper()}")
        print("-" * 40)

        valid, reason = validate_bracket_spec(spec)
        print(f"Valid: {valid} ({reason})")

        if valid:
            print(f"  Entry: ${spec.entry_limit_price:,.2f}")
            print(f"  TP: ${spec.take_profit_price:,.2f}")
            print(f"  SL: ${spec.stop_loss_price:,.2f} ({spec.stop_loss_type})")
            if spec.stop_limit_price:
                print(f"  SL Limit: ${spec.stop_limit_price:,.2f}")

    print("\n" + "=" * 60)
    print("Bracket Order Builder Test Complete")
    print("=" * 60)
