"""
Position Sizing
===============

Pure functions for computing risk-aware target positions.

Implements position sizing with:
- Kelly criterion (with fractional cap)
- Risk limits enforcement
- Single-asset weight limits
- Leverage limits
- Notional limits

Design (for ADR-051):
- Conservative default: 25% of Kelly (industry standard for risk management)
- Multi-layer risk checks: Each limit applied independently
- Fail-safe: Always returns valid quantity (clamped to limits)
"""

from typing import Optional, Dict
import logging

from trade_engine.models import (
    SignalSnapshot,
    PortfolioState,
    RiskLimits,
    RiskConfig,
    TargetPosition,
)
from trade_engine.exceptions import MissingPriceError, InsufficientCapitalError


def derive_target_position(
    signal: SignalSnapshot,
    portfolio: PortfolioState,
    prices: Dict[str, float],
    risk_limits: RiskLimits,
    config: RiskConfig,
    logger: Optional[logging.Logger] = None,
) -> TargetPosition:
    """Compute target quantity for asset respecting risk constraints.

    Process:
    1. Interpret signal to get desired exposure [-1, 1]
    2. Compute base position size using Kelly-like sizing
    3. Apply risk limits (single asset weight, leverage, notional)
    4. Round if configured

    Args:
        signal: Signal for this asset
        portfolio: Current portfolio state
        prices: Current prices for all assets
        risk_limits: Risk limit constraints
        config: Risk configuration
        logger: Optional logger

    Returns:
        TargetPosition with computed quantity and rationale

    Raises:
        MissingPriceError: If price not available for asset
        InsufficientCapitalError: If portfolio equity <= 0
    """
    from trade_engine.signal_interpreter import interpret_signal

    asset_id = signal.asset_id

    # Get current price
    if asset_id not in prices:
        raise MissingPriceError(f"Missing price for {asset_id}")
    current_price = prices[asset_id]

    # Get portfolio equity
    equity = portfolio.total_equity(prices)
    if equity <= 0:
        raise InsufficientCapitalError(
            f"Portfolio equity is {equity:.2f}, cannot size positions"
        )

    # Interpret signal to exposure
    exposure = interpret_signal(signal, config, logger=logger)

    # If exposure is zero or near-zero, target is zero (exit)
    if abs(exposure) < 1e-6:
        return TargetPosition(
            asset_id=asset_id,
            target_quantity=0.0,
            rationale=f"Signal exposure {exposure:.4f} below threshold, exiting position",
        )

    # Compute base position size
    # Use Kelly-like sizing: exposure * kelly_fraction_cap * equity
    # Then convert to quantity
    base_notional = abs(exposure) * config.kelly_fraction_cap * equity
    base_quantity = base_notional / current_price

    # Apply risk limits
    limited_quantity = apply_risk_limits(
        target_quantity=base_quantity,
        asset_id=asset_id,
        portfolio=portfolio,
        prices=prices,
        risk_limits=risk_limits,
        current_price=current_price,
        logger=logger,
    )

    # Apply rounding if configured
    if config.rounding_step and config.rounding_step > 0:
        limited_quantity = _round_quantity(limited_quantity, config.rounding_step)

    # Build rationale
    rationale_parts = [
        f"Signal: {signal.signal_name}",
        f"Value: {signal.signal_value:.3f}",
        f"Confidence: {signal.signal_confidence:.3f}",
        f"Exposure: {exposure:.3f}",
        f"Base quantity: {base_quantity:.4f}",
        f"After limits: {limited_quantity:.4f}",
    ]
    rationale = ", ".join(rationale_parts)

    if logger:
        logger.info(f"Target position for {asset_id}: {limited_quantity:.4f} | {rationale}")

    return TargetPosition(
        asset_id=asset_id,
        target_quantity=limited_quantity,
        rationale=rationale,
        metadata={
            "signal_id": signal.signal_id,
            "signal_name": signal.signal_name,
            "exposure": exposure,
            "base_quantity": base_quantity,
            "equity": equity,
            "price": current_price,
        },
    )


def apply_risk_limits(
    target_quantity: float,
    asset_id: str,
    portfolio: PortfolioState,
    prices: Dict[str, float],
    risk_limits: RiskLimits,
    current_price: float,
    logger: Optional[logging.Logger] = None,
) -> float:
    """Clamp target quantity to satisfy all risk limits.

    Applies limits in order:
    1. Max single asset weight
    2. Max position size notional
    3. Max leverage (portfolio-level)

    Args:
        target_quantity: Desired quantity before limits
        asset_id: Asset identifier
        portfolio: Current portfolio state
        prices: Current prices
        risk_limits: Risk limits to enforce
        current_price: Current price for this asset
        logger: Optional logger

    Returns:
        Clamped quantity that satisfies all limits
    """
    equity = portfolio.total_equity(prices)
    limited_quantity = target_quantity

    # 1. Max single asset weight
    max_notional_by_weight = equity * risk_limits.max_single_asset_weight
    max_quantity_by_weight = max_notional_by_weight / current_price
    if limited_quantity > max_quantity_by_weight:
        if logger:
            logger.warning(
                f"{asset_id}: Quantity {limited_quantity:.4f} exceeds max single asset weight, "
                f"clamping to {max_quantity_by_weight:.4f}"
            )
        limited_quantity = max_quantity_by_weight

    # 2. Max position size notional
    max_quantity_by_notional = risk_limits.max_position_size_notional / current_price
    if limited_quantity > max_quantity_by_notional:
        if logger:
            logger.warning(
                f"{asset_id}: Quantity {limited_quantity:.4f} exceeds max notional, "
                f"clamping to {max_quantity_by_notional:.4f}"
            )
        limited_quantity = max_quantity_by_notional

    # 3. Max leverage (portfolio-level check)
    # Compute what gross exposure would be with this new position
    projected_gross = _compute_projected_gross_exposure(
        portfolio, prices, asset_id, limited_quantity, current_price
    )
    projected_leverage = projected_gross / equity

    if projected_leverage > risk_limits.max_leverage:
        # Scale down the quantity proportionally
        scale_factor = risk_limits.max_leverage / projected_leverage
        scaled_quantity = limited_quantity * scale_factor
        if logger:
            logger.warning(
                f"{asset_id}: Projected leverage {projected_leverage:.2f}x exceeds max "
                f"{risk_limits.max_leverage:.2f}x, scaling quantity from {limited_quantity:.4f} "
                f"to {scaled_quantity:.4f}"
            )
        limited_quantity = scaled_quantity

    return limited_quantity


def _compute_projected_gross_exposure(
    portfolio: PortfolioState,
    prices: Dict[str, float],
    new_asset_id: str,
    new_quantity: float,
    new_price: float,
) -> float:
    """Compute gross exposure if we added/updated a position.

    Args:
        portfolio: Current portfolio
        prices: Current prices
        new_asset_id: Asset we're sizing
        new_quantity: Proposed quantity for that asset
        new_price: Current price for that asset

    Returns:
        Projected gross exposure (sum of abs notional values)
    """
    gross = 0.0

    # Add existing positions (excluding the one we're updating)
    for pos in portfolio.positions:
        if pos.asset_id == new_asset_id:
            continue  # Skip, we'll add the new quantity
        if pos.asset_id not in prices:
            continue  # Skip positions without prices (shouldn't happen)
        gross += abs(pos.quantity * prices[pos.asset_id])

    # Add the new/updated position
    gross += abs(new_quantity * new_price)

    return gross


def _round_quantity(quantity: float, step: float) -> float:
    """Round quantity to nearest step.

    Args:
        quantity: Quantity to round
        step: Rounding increment (e.g. 0.01 for 2 decimals)

    Returns:
        Rounded quantity
    """
    return round(quantity / step) * step
