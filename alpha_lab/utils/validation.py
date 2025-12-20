"""
Validation utilities for Alpha Lab.

Input validation helpers and data quality checks.
"""

from typing import Any, Dict, List
import pandas as pd
import numpy as np


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_price_data(df: pd.DataFrame, required_columns: List[str] = None) -> None:
    """
    Validate OHLCV price data.

    Args:
        df: DataFrame with price data
        required_columns: List of required column names

    Raises:
        ValidationError: If validation fails
    """
    if required_columns is None:
        required_columns = ['open', 'high', 'low', 'close', 'volume']

    # Check for required columns
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValidationError(f"Missing required columns: {missing}")

    # Check for NaN values
    if df[required_columns].isnull().any().any():
        raise ValidationError("Price data contains NaN values")

    # Check for positive prices
    price_cols = [c for c in ['open', 'high', 'low', 'close'] if c in df.columns]
    if (df[price_cols] <= 0).any().any():
        raise ValidationError("Price data contains non-positive values")

    # Check OHLC consistency (high >= low, etc.)
    if 'high' in df.columns and 'low' in df.columns:
        if (df['high'] < df['low']).any():
            raise ValidationError("Invalid OHLC data: high < low")

    if all(c in df.columns for c in ['open', 'high', 'low', 'close']):
        if (df['high'] < df['open']).any() or (df['high'] < df['close']).any():
            raise ValidationError("Invalid OHLC data: high < open/close")
        if (df['low'] > df['open']).any() or (df['low'] > df['close']).any():
            raise ValidationError("Invalid OHLC data: low > open/close")


def validate_date_range(start_date: str, end_date: str) -> None:
    """
    Validate date range.

    Args:
        start_date: Start date
        end_date: End date

    Raises:
        ValidationError: If dates are invalid
    """
    from alpha_lab.utils.time_utils import parse_date

    start = parse_date(start_date)
    end = parse_date(end_date)

    if end <= start:
        raise ValidationError(f"end_date ({end_date}) must be after start_date ({start_date})")


def validate_parameter_ranges(params: Dict[str, Any], ranges: Dict[str, tuple]) -> None:
    """
    Validate parameters are within acceptable ranges.

    Args:
        params: Dictionary of parameters
        ranges: Dictionary mapping parameter names to (min, max) tuples

    Raises:
        ValidationError: If parameters are out of range
    """
    for param_name, (min_val, max_val) in ranges.items():
        if param_name in params:
            value = params[param_name]
            if not (min_val <= value <= max_val):
                raise ValidationError(
                    f"Parameter '{param_name}' value {value} "
                    f"outside acceptable range [{min_val}, {max_val}]"
                )


def validate_returns(returns: np.ndarray) -> None:
    """
    Validate returns array.

    Args:
        returns: Array of returns

    Raises:
        ValidationError: If returns are invalid
    """
    if len(returns) == 0:
        raise ValidationError("Returns array is empty")

    if np.isnan(returns).any():
        raise ValidationError("Returns contain NaN values")

    if np.isinf(returns).any():
        raise ValidationError("Returns contain infinite values")


def validate_equity_curve(equity: pd.Series) -> None:
    """
    Validate equity curve.

    Args:
        equity: Series of equity values

    Raises:
        ValidationError: If equity curve is invalid
    """
    if len(equity) == 0:
        raise ValidationError("Equity curve is empty")

    if equity.isnull().any():
        raise ValidationError("Equity curve contains NaN values")

    if (equity <= 0).any():
        raise ValidationError("Equity curve contains non-positive values")


def check_for_lookahead_bias(
    signal_dates: List[str],
    price_dates: List[str],
    tolerance_seconds: int = 0
) -> bool:
    """
    Check for potential lookahead bias in signals.

    Args:
        signal_dates: List of signal generation timestamps
        price_dates: List of corresponding price timestamps
        tolerance_seconds: Allowed time difference

    Returns:
        True if lookahead bias detected
    """
    from alpha_lab.utils.time_utils import parse_date

    for sig_date, price_date in zip(signal_dates, price_dates):
        sig_dt = parse_date(sig_date)
        price_dt = parse_date(price_date)

        # Signal should not be generated after the price timestamp
        if (sig_dt - price_dt).total_seconds() > tolerance_seconds:
            return True

    return False


def validate_allocations(allocations: Dict[str, float], tolerance: float = 0.01) -> None:
    """
    Validate allocations sum to 1.0.

    Args:
        allocations: Dictionary mapping strategy/asset to allocation
        tolerance: Allowed deviation from 1.0

    Raises:
        ValidationError: If allocations don't sum to 1.0
    """
    total = sum(allocations.values())
    if not (1.0 - tolerance <= total <= 1.0 + tolerance):
        raise ValidationError(
            f"Allocations sum to {total:.4f}, expected 1.0 (±{tolerance})"
        )

    for key, value in allocations.items():
        if not (0 <= value <= 1):
            raise ValidationError(
                f"Allocation for '{key}' is {value}, must be between 0 and 1"
            )
