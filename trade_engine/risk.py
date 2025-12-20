"""
Risk Metrics Computation
=========================

Pure functions for computing portfolio-level risk metrics.

Computes:
- Gross exposure (sum of absolute notional values)
- Net exposure (signed sum of notional values)
- Leverage (gross exposure / equity)
- Largest single position weight

V1 does not compute VaR (value at risk) - placeholder for V2.

Design (for ADR-051):
- Simple metrics: Focus on position-based risk (no volatility modeling in V1)
- Portfolio-level aggregation: Sum across all positions
- Equity-relative: All metrics scaled by total equity
"""

from typing import Dict, Optional
import logging

from trade_engine.models import PortfolioState, RiskMetrics
from trade_engine.exceptions import MissingPriceError, InsufficientCapitalError


def compute_risk_metrics(
    portfolio: PortfolioState,
    prices: Dict[str, float],
    logger: Optional[logging.Logger] = None,
) -> RiskMetrics:
    """Compute aggregate portfolio risk metrics.

    Metrics:
    - Gross exposure: Sum of |notional| for all positions
    - Net exposure: Sum of signed notional for all positions
      (LONG = positive, SHORT = negative)
    - Leverage: gross_exposure / equity
    - Largest position weight: max(|notional|) / equity

    Args:
        portfolio: Current portfolio state
        prices: Current market prices for all assets
        logger: Optional logger

    Returns:
        RiskMetrics with computed values

    Raises:
        MissingPriceError: If price missing for any position
        InsufficientCapitalError: If equity <= 0
    """
    # Compute equity
    equity = portfolio.total_equity(prices)
    if equity <= 0:
        raise InsufficientCapitalError(
            f"Portfolio equity is {equity:.2f}, cannot compute risk metrics"
        )

    gross_exposure = 0.0
    net_exposure = 0.0
    largest_position_notional = 0.0

    for position in portfolio.positions:
        asset_id = position.asset_id

        # Get current price
        if asset_id not in prices:
            raise MissingPriceError(
                f"Missing price for {asset_id} in risk metrics calculation"
            )
        current_price = prices[asset_id]

        # Compute notional
        notional = position.quantity * current_price

        # Update metrics
        gross_exposure += abs(notional)

        if position.side == "LONG":
            net_exposure += notional
        else:  # SHORT
            net_exposure -= notional

        largest_position_notional = max(largest_position_notional, abs(notional))

    # Compute derived metrics
    leverage = gross_exposure / equity if equity > 0 else 0.0
    largest_position_weight = largest_position_notional / equity if equity > 0 else 0.0

    # Notes for any observations
    notes = []
    if leverage > 1.5:
        notes.append(f"Leverage {leverage:.2f}x is elevated")
    if largest_position_weight > 0.3:
        notes.append(
            f"Largest position weight {largest_position_weight:.1%} is concentrated"
        )

    notes_str = "; ".join(notes) if notes else None

    if logger:
        logger.info(
            f"Risk metrics: gross={gross_exposure:.2f}, net={net_exposure:.2f}, "
            f"leverage={leverage:.2f}x, largest_weight={largest_position_weight:.1%}"
        )

    return RiskMetrics(
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        largest_position_weight=largest_position_weight,
        leverage=leverage,
        value_at_risk=None,  # V1: Not implemented
        notes=notes_str,
    )
