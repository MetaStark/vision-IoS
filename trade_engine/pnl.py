"""
P&L Computation
===============

Pure functions for computing portfolio P&L metrics.

Computes:
- Unrealized P&L for open positions
- Per-asset P&L breakdown
- Total P&L

V1 Limitation: Realized P&L requires trade history, which is not tracked yet.
V1 always returns realized_pnl = 0.0

Design (for ADR-051):
- Mark-to-market: P&L based on current prices vs entry prices
- Per-position calculation: Each position valued independently
- Short position support: Correct P&L sign for short positions
"""

from typing import Dict, Optional
from datetime import datetime
import logging

from trade_engine.models import PortfolioState, PnLMetrics
from trade_engine.exceptions import MissingPriceError


def compute_pnl(
    portfolio: PortfolioState,
    prices: Dict[str, float],
    timestamp: Optional[datetime] = None,
    logger: Optional[logging.Logger] = None,
) -> PnLMetrics:
    """Compute unrealized P&L for all positions.

    P&L calculation:
    - LONG position: (current_price - avg_entry_price) * quantity
    - SHORT position: (avg_entry_price - current_price) * quantity

    Args:
        portfolio: Current portfolio state
        prices: Current market prices for all assets
        timestamp: Optional timestamp for metrics (default: now)
        logger: Optional logger

    Returns:
        PnLMetrics with unrealized P&L breakdown

    Raises:
        MissingPriceError: If price missing for any position
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    unrealized_pnl = 0.0
    pnl_by_asset: Dict[str, float] = {}

    for position in portfolio.positions:
        asset_id = position.asset_id

        # Get current price
        if asset_id not in prices:
            raise MissingPriceError(
                f"Missing price for {asset_id} in P&L calculation"
            )
        current_price = prices[asset_id]

        # Compute P&L for this position
        if position.side == "LONG":
            pnl = (current_price - position.avg_entry_price) * position.quantity
        else:  # SHORT
            pnl = (position.avg_entry_price - current_price) * position.quantity

        unrealized_pnl += pnl
        pnl_by_asset[asset_id] = pnl

        if logger:
            logger.debug(
                f"P&L for {asset_id} ({position.side}): {pnl:.2f} "
                f"(qty={position.quantity:.4f}, entry={position.avg_entry_price:.2f}, "
                f"current={current_price:.2f})"
            )

    # V1: Realized P&L is always 0.0 (no trade history tracking yet)
    realized_pnl = 0.0
    total_pnl = realized_pnl + unrealized_pnl

    if logger:
        logger.info(
            f"P&L computed: unrealized={unrealized_pnl:.2f}, "
            f"realized={realized_pnl:.2f}, total={total_pnl:.2f}"
        )

    return PnLMetrics(
        timestamp=timestamp,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        pnl_by_asset=pnl_by_asset,
    )
