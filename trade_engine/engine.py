"""
Trade Engine Orchestration
===========================

Main entry point for the trade engine.

The run_trade_engine() function orchestrates the complete pipeline:
1. Interpret signals
2. Derive target positions
3. Generate proposed trades
4. Compute risk and P&L metrics

This is the primary function that external systems (e.g. FINN scheduler,
API endpoints) should call.

Design (for ADR-051):
- Single entry point: One function for complete pipeline
- Deterministic: Same inputs always produce same outputs
- Side-effect free: All I/O is via parameters and return values
- Comprehensive output: Returns trades + metrics for auditability
"""

from typing import List, Tuple, Dict, Optional
import logging

from trade_engine.models import (
    SignalSnapshot,
    PortfolioState,
    RiskLimits,
    RiskConfig,
    ProposedTrade,
    RiskMetrics,
    PnLMetrics,
    TargetPosition,
)
from trade_engine.position_sizing import derive_target_position
from trade_engine.trade_generator import generate_proposed_trades
from trade_engine.risk import compute_risk_metrics
from trade_engine.pnl import compute_pnl


def run_trade_engine(
    signals: List[SignalSnapshot],
    portfolio: PortfolioState,
    prices: Dict[str, float],
    risk_limits: RiskLimits,
    config: RiskConfig,
    logger: Optional[logging.Logger] = None,
) -> Tuple[List[ProposedTrade], RiskMetrics, PnLMetrics]:
    """Main entry point for trade engine.

    Complete pipeline:
    1. For each signal, derive target position (respecting risk limits)
    2. Generate trades to reach target positions
    3. Compute risk metrics for current portfolio
    4. Compute P&L metrics for current portfolio

    Args:
        signals: List of signals to process (one per asset typically)
        portfolio: Current portfolio state
        prices: Current market prices for all assets
        risk_limits: Risk limit constraints
        config: Risk configuration
        logger: Optional logger for diagnostics

    Returns:
        Tuple of:
        - List of proposed trades (may be empty)
        - RiskMetrics for current portfolio
        - PnLMetrics for current portfolio

    Raises:
        MissingPriceError: If price missing for any required asset
        InsufficientCapitalError: If portfolio equity <= 0
        Other TradeEngineError subclasses: For validation failures

    Example:
        >>> signals = [SignalSnapshot(...), ...]
        >>> portfolio = PortfolioState(...)
        >>> prices = {"BTC-USD": 50000.0, "ETH-USD": 3000.0}
        >>> trades, risk, pnl = run_trade_engine(
        ...     signals, portfolio, prices, risk_limits, config
        ... )
        >>> for trade in trades:
        ...     print(f"{trade.side} {trade.quantity} {trade.asset_id}")
    """
    if logger:
        logger.info(
            f"Trade engine starting: {len(signals)} signals, "
            f"{len(portfolio.positions)} existing positions"
        )

    all_trades: List[ProposedTrade] = []

    # Process each signal
    for signal in signals:
        if logger:
            logger.debug(f"Processing signal {signal.signal_id} for {signal.asset_id}")

        # Derive target position
        try:
            target = derive_target_position(
                signal=signal,
                portfolio=portfolio,
                prices=prices,
                risk_limits=risk_limits,
                config=config,
                logger=logger,
            )

            # Generate trades to reach target
            if signal.asset_id not in prices:
                if logger:
                    logger.warning(
                        f"Skipping {signal.asset_id}: price not available"
                    )
                continue

            trades = generate_proposed_trades(
                target=target,
                portfolio=portfolio,
                current_price=prices[signal.asset_id],
                config=config,
                logger=logger,
            )

            all_trades.extend(trades)

            if logger:
                logger.debug(
                    f"Signal {signal.signal_id}: generated {len(trades)} trade(s)"
                )

        except Exception as e:
            if logger:
                logger.error(
                    f"Error processing signal {signal.signal_id} for {signal.asset_id}: {e}"
                )
            # Re-raise to fail fast (don't silently skip errors)
            raise

    # Compute risk metrics for current portfolio
    risk_metrics = compute_risk_metrics(
        portfolio=portfolio,
        prices=prices,
        logger=logger,
    )

    # Compute P&L metrics for current portfolio
    pnl_metrics = compute_pnl(
        portfolio=portfolio,
        prices=prices,
        logger=logger,
    )

    if logger:
        logger.info(
            f"Trade engine complete: {len(all_trades)} trade(s) proposed, "
            f"leverage={risk_metrics.leverage:.2f}x, "
            f"total_pnl={pnl_metrics.total_pnl:.2f}"
        )

    return all_trades, risk_metrics, pnl_metrics
