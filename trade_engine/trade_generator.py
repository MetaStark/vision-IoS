"""
Trade Generation
=================

Pure functions for generating ProposedTrades from target positions.

Given a target position and current portfolio state, generates the minimal
set of trades needed to reach the target.

Design (for ADR-051):
- Incremental trades: Only trade the delta between current and target
- Min trade filter: Skip trades below min_trade_notional
- Explicit reasoning: Each trade includes human-readable rationale
"""

from typing import List, Literal, Optional
from datetime import datetime
import logging

from trade_engine.models import (
    ProposedTrade,
    TargetPosition,
    PortfolioState,
    RiskConfig,
)


def generate_proposed_trades(
    target: TargetPosition,
    portfolio: PortfolioState,
    current_price: float,
    config: RiskConfig,
    logger: Optional[logging.Logger] = None,
) -> List[ProposedTrade]:
    """Generate trades to move from current to target position.

    Logic:
    1. Determine current quantity for asset (from portfolio)
    2. Compute delta = target - current
    3. If abs(delta * price) < min_trade_notional, return []
    4. Otherwise, create trade for the delta

    Args:
        target: Target position to achieve
        portfolio: Current portfolio state
        current_price: Current price for the asset
        config: Risk configuration (for min_trade_notional)
        logger: Optional logger

    Returns:
        List of ProposedTrade (empty if no trade needed, 1 trade otherwise)

    Example:
        Current: 0 BTC
        Target: 0.5 BTC
        → [BUY 0.5 BTC]

        Current: 1.0 BTC
        Target: 0.5 BTC
        → [SELL 0.5 BTC]

        Current: 0.5 BTC
        Target: 0.5 BTC
        → [] (no change)
    """
    asset_id = target.asset_id

    # Get current position
    current_position = portfolio.position_for_asset(asset_id)
    current_quantity = 0.0
    if current_position:
        # Current quantity is signed: positive for LONG, negative for SHORT
        if current_position.side == "LONG":
            current_quantity = current_position.quantity
        else:  # SHORT
            current_quantity = -current_position.quantity

    # Compute delta
    # Note: target_quantity is always positive (unsigned)
    # We need to infer intent from signal/context
    # For V1: we only handle LONG positions (no shorts)
    # So target_quantity is the absolute quantity we want to hold long
    delta = target.target_quantity - abs(current_quantity)

    # Check if delta is significant
    notional_delta = abs(delta * current_price)
    if notional_delta < config.min_trade_notional:
        if logger:
            logger.info(
                f"No trade for {asset_id}: delta notional {notional_delta:.2f} "
                f"< min {config.min_trade_notional:.2f}"
            )
        return []

    # Determine trade side and quantity
    if delta > 0:
        side = "BUY"
        quantity = delta
        reason = (
            f"Increase position to {target.target_quantity:.4f} from "
            f"{abs(current_quantity):.4f} (delta: {delta:.4f}). {target.rationale}"
        )
    else:  # delta < 0
        side = "SELL"
        quantity = abs(delta)
        reason = (
            f"Decrease position to {target.target_quantity:.4f} from "
            f"{abs(current_quantity):.4f} (delta: {delta:.4f}). {target.rationale}"
        )

    # Create trade
    trade = create_trade(
        asset_id=asset_id,
        side=side,
        quantity=quantity,
        reason=reason,
        source_signal_id=target.metadata.get("signal_id", "unknown"),
        order_type="MARKET",
        logger=logger,
    )

    return [trade]


def create_trade(
    asset_id: str,
    side: Literal["BUY", "SELL"],
    quantity: float,
    reason: str,
    source_signal_id: str,
    order_type: Literal["MARKET", "LIMIT"] = "MARKET",
    limit_price: Optional[float] = None,
    logger: Optional[logging.Logger] = None,
) -> ProposedTrade:
    """Factory function for creating ProposedTrade instances.

    Args:
        asset_id: Asset to trade
        side: BUY or SELL
        quantity: Quantity to trade (must be > 0)
        reason: Human-readable explanation
        source_signal_id: Signal that originated this trade
        order_type: MARKET or LIMIT
        limit_price: Required if order_type=LIMIT
        logger: Optional logger

    Returns:
        ProposedTrade instance

    Raises:
        ValueError: If quantity <= 0 or invalid parameters
    """
    if quantity <= 0:
        raise ValueError(f"Trade quantity must be > 0, got {quantity}")

    if order_type == "LIMIT" and limit_price is None:
        raise ValueError("limit_price required when order_type=LIMIT")

    trade = ProposedTrade(
        asset_id=asset_id,
        side=side,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
        time_in_force="GTC",
        reason=reason,
        source_signal_id=source_signal_id,
        created_at=datetime.utcnow(),
    )

    if logger:
        logger.info(
            f"Created trade: {side} {quantity:.4f} {asset_id} @ {order_type} "
            f"(ID: {trade.trade_id})"
        )

    return trade
