"""
Performance Metrics Calculator for Alpha Lab.

Calculates comprehensive performance metrics for backtests:
- Returns metrics (total return, CAGR)
- Risk-adjusted metrics (Sharpe, Sortino, Calmar)
- Risk metrics (volatility, drawdown)
- Trading metrics (win rate, profit factor, turnover)
"""

import numpy as np
import pandas as pd
from typing import List, Optional

from alpha_lab.schemas import (
    PerformanceMetrics,
    EquityPoint,
    TradeRecord,
)
from alpha_lab.utils import annualization_factor, get_years_between


def calculate_performance_metrics(
    equity_curve: List[EquityPoint],
    trades: List[TradeRecord],
    risk_free_rate: float = 0.02,
    initial_capital: Optional[float] = None,
    data_frequency: str = "1h"
) -> PerformanceMetrics:
    """
    Calculate comprehensive performance metrics.

    Args:
        equity_curve: List of equity points
        trades: List of trade records
        risk_free_rate: Annual risk-free rate
        initial_capital: Initial capital (if None, inferred from first equity point)
        data_frequency: Data frequency for annualization

    Returns:
        Complete performance metrics
    """
    if len(equity_curve) == 0:
        return _get_zero_metrics()

    # Extract data
    equities = np.array([ep.equity for ep in equity_curve])
    drawdowns = np.array([ep.drawdown for ep in equity_curve])

    # Infer initial capital
    if initial_capital is None:
        initial_capital = equities[0]

    # Calculate returns
    returns = np.diff(equities) / equities[:-1]
    returns = returns[np.isfinite(returns)]  # Remove inf/nan

    if len(returns) == 0:
        returns = np.array([0.0])

    # Basic return metrics
    final_equity = equities[-1]
    total_return = (final_equity - initial_capital) / initial_capital

    # Calculate time period
    if len(equity_curve) >= 2:
        start_date = equity_curve[0].date.split()[0]  # Extract date part
        end_date = equity_curve[-1].date.split()[0]
        years = get_years_between(start_date, end_date)
        years = max(years, 1/365)  # Minimum 1 day
    else:
        years = 1.0

    # CAGR
    if years > 0:
        cagr = (final_equity / initial_capital) ** (1 / years) - 1
    else:
        cagr = 0.0

    # Volatility metrics
    ann_factor = annualization_factor(data_frequency)
    volatility_annual = np.std(returns) * np.sqrt(ann_factor) if len(returns) > 1 else 0.0

    # Sharpe ratio
    if volatility_annual > 0:
        excess_return = np.mean(returns) * ann_factor - risk_free_rate
        sharpe_ratio = excess_return / volatility_annual
    else:
        sharpe_ratio = 0.0

    # Sortino ratio (using downside deviation)
    negative_returns = returns[returns < 0]
    if len(negative_returns) > 0:
        downside_deviation = np.std(negative_returns) * np.sqrt(ann_factor)
        if downside_deviation > 0:
            sortino_ratio = (np.mean(returns) * ann_factor - risk_free_rate) / downside_deviation
        else:
            sortino_ratio = 0.0
    else:
        downside_deviation = 0.0
        sortino_ratio = sharpe_ratio  # No downside, use Sharpe

    # Drawdown metrics
    max_drawdown = min(drawdowns) if len(drawdowns) > 0 else 0.0

    # Max drawdown duration
    max_dd_duration_days = _calculate_max_drawdown_duration(equity_curve)

    # Calmar ratio
    if max_drawdown < 0:
        calmar_ratio = cagr / abs(max_drawdown)
    else:
        calmar_ratio = 0.0

    # Trading metrics
    if len(trades) > 0:
        trade_metrics = _calculate_trade_metrics(trades)
    else:
        trade_metrics = _get_zero_trade_metrics()

    # Turnover
    if len(trades) > 0:
        total_trade_value = sum(abs(t.entry_price * t.quantity) for t in trades)
        avg_equity = np.mean(equities)
        turnover_annual = (total_trade_value / avg_equity) / years if years > 0 else 0.0
    else:
        turnover_annual = 0.0

    # Costs
    total_commission = sum(t.commission for t in trades)
    total_slippage = sum(t.slippage for t in trades)

    # Time-based metrics
    time_in_market_pct = _calculate_time_in_market(trades, equity_curve)
    time_underwater_pct = _calculate_time_underwater(drawdowns)

    return PerformanceMetrics(
        # Returns
        total_return=total_return,
        cagr=cagr,
        # Risk-adjusted
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        # Risk
        max_drawdown=max_drawdown,
        max_drawdown_duration_days=max_dd_duration_days,
        volatility_annual=volatility_annual,
        downside_deviation=downside_deviation,
        # Trading
        total_trades=trade_metrics['total_trades'],
        win_rate=trade_metrics['win_rate'],
        profit_factor=trade_metrics['profit_factor'],
        avg_trade_pnl=trade_metrics['avg_trade_pnl'],
        avg_trade_pnl_pct=trade_metrics['avg_trade_pnl_pct'],
        avg_trade_duration_hours=trade_metrics['avg_trade_duration_hours'],
        # Turnover and costs
        turnover_annual=turnover_annual,
        total_commission=total_commission,
        total_slippage=total_slippage,
        # Advanced
        best_trade_pnl=trade_metrics['best_trade_pnl'],
        worst_trade_pnl=trade_metrics['worst_trade_pnl'],
        max_consecutive_wins=trade_metrics['max_consecutive_wins'],
        max_consecutive_losses=trade_metrics['max_consecutive_losses'],
        avg_winner_pnl=trade_metrics['avg_winner_pnl'],
        avg_loser_pnl=trade_metrics['avg_loser_pnl'],
        # Time-based
        time_in_market_pct=time_in_market_pct,
        time_underwater_pct=time_underwater_pct,
    )


def _calculate_trade_metrics(trades: List[TradeRecord]) -> dict:
    """Calculate trading-specific metrics."""
    total_trades = len(trades)
    pnls = np.array([t.pnl for t in trades])
    pnl_pcts = np.array([t.pnl_pct for t in trades])

    # Win/loss metrics
    winners = pnls > 0
    losers = pnls < 0
    num_winners = np.sum(winners)
    num_losers = np.sum(losers)

    win_rate = num_winners / total_trades if total_trades > 0 else 0.0

    # Profit factor
    gross_profit = np.sum(pnls[winners]) if num_winners > 0 else 0.0
    gross_loss = abs(np.sum(pnls[losers])) if num_losers > 0 else 0.0

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = 0.0 if gross_profit == 0 else float('inf')

    # Average metrics
    avg_trade_pnl = np.mean(pnls) if len(pnls) > 0 else 0.0
    avg_trade_pnl_pct = np.mean(pnl_pcts) if len(pnl_pcts) > 0 else 0.0

    avg_winner_pnl = np.mean(pnls[winners]) if num_winners > 0 else 0.0
    avg_loser_pnl = np.mean(pnls[losers]) if num_losers > 0 else 0.0

    # Best/worst
    best_trade_pnl = np.max(pnls) if len(pnls) > 0 else 0.0
    worst_trade_pnl = np.min(pnls) if len(pnls) > 0 else 0.0

    # Duration
    durations = np.array([t.duration_hours for t in trades])
    avg_trade_duration_hours = np.mean(durations) if len(durations) > 0 else 0.0

    # Consecutive wins/losses
    max_consecutive_wins = _calculate_max_consecutive(winners)
    max_consecutive_losses = _calculate_max_consecutive(losers)

    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'avg_trade_pnl': avg_trade_pnl,
        'avg_trade_pnl_pct': avg_trade_pnl_pct,
        'avg_trade_duration_hours': avg_trade_duration_hours,
        'best_trade_pnl': best_trade_pnl,
        'worst_trade_pnl': worst_trade_pnl,
        'max_consecutive_wins': max_consecutive_wins,
        'max_consecutive_losses': max_consecutive_losses,
        'avg_winner_pnl': avg_winner_pnl,
        'avg_loser_pnl': avg_loser_pnl,
    }


def _calculate_max_consecutive(boolean_array: np.ndarray) -> int:
    """Calculate maximum consecutive True values."""
    if len(boolean_array) == 0:
        return 0

    max_count = 0
    current_count = 0

    for value in boolean_array:
        if value:
            current_count += 1
            max_count = max(max_count, current_count)
        else:
            current_count = 0

    return max_count


def _calculate_max_drawdown_duration(equity_curve: List[EquityPoint]) -> int:
    """Calculate maximum drawdown duration in days."""
    if len(equity_curve) < 2:
        return 0

    max_duration = 0
    current_duration = 0
    in_drawdown = False

    for ep in equity_curve:
        if ep.drawdown < 0:
            if not in_drawdown:
                in_drawdown = True
                current_duration = 1
            else:
                current_duration += 1
        else:
            if in_drawdown:
                max_duration = max(max_duration, current_duration)
                in_drawdown = False
                current_duration = 0

    # Check if still in drawdown at end
    if in_drawdown:
        max_duration = max(max_duration, current_duration)

    return max_duration


def _calculate_time_in_market(
    trades: List[TradeRecord],
    equity_curve: List[EquityPoint]
) -> float:
    """Calculate percentage of time with open positions."""
    # Simplified: assume always in market if we have trades
    # In reality, we'd track actual position timestamps
    if len(trades) > 0 and len(equity_curve) > 0:
        total_trade_hours = sum(t.duration_hours for t in trades)
        total_hours = len(equity_curve)  # Approximate
        return min(1.0, total_trade_hours / total_hours) if total_hours > 0 else 0.0
    return 0.0


def _calculate_time_underwater(drawdowns: np.ndarray) -> float:
    """Calculate percentage of time in drawdown."""
    if len(drawdowns) == 0:
        return 0.0

    underwater_count = np.sum(drawdowns < 0)
    return underwater_count / len(drawdowns)


def _get_zero_metrics() -> PerformanceMetrics:
    """Get metrics with all zeros (for empty results)."""
    return PerformanceMetrics(
        total_return=0.0,
        cagr=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        calmar_ratio=0.0,
        max_drawdown=0.0,
        max_drawdown_duration_days=0,
        volatility_annual=0.0,
        downside_deviation=0.0,
        total_trades=0,
        win_rate=0.0,
        profit_factor=0.0,
        avg_trade_pnl=0.0,
        avg_trade_pnl_pct=0.0,
        avg_trade_duration_hours=0.0,
        turnover_annual=0.0,
        total_commission=0.0,
        total_slippage=0.0,
        best_trade_pnl=0.0,
        worst_trade_pnl=0.0,
        max_consecutive_wins=0,
        max_consecutive_losses=0,
        avg_winner_pnl=0.0,
        avg_loser_pnl=0.0,
        time_in_market_pct=0.0,
        time_underwater_pct=0.0,
    )


def _get_zero_trade_metrics() -> dict:
    """Get trade metrics with all zeros."""
    return {
        'total_trades': 0,
        'win_rate': 0.0,
        'profit_factor': 0.0,
        'avg_trade_pnl': 0.0,
        'avg_trade_pnl_pct': 0.0,
        'avg_trade_duration_hours': 0.0,
        'best_trade_pnl': 0.0,
        'worst_trade_pnl': 0.0,
        'max_consecutive_wins': 0,
        'max_consecutive_losses': 0,
        'avg_winner_pnl': 0.0,
        'avg_loser_pnl': 0.0,
    }


def calculate_returns_from_equity(equity_curve: List[EquityPoint]) -> np.ndarray:
    """
    Extract returns array from equity curve.

    Args:
        equity_curve: List of equity points

    Returns:
        Array of returns
    """
    if len(equity_curve) < 2:
        return np.array([0.0])

    equities = np.array([ep.equity for ep in equity_curve])
    returns = np.diff(equities) / equities[:-1]
    returns = returns[np.isfinite(returns)]

    return returns if len(returns) > 0 else np.array([0.0])
