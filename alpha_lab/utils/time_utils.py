"""
Time utilities for Alpha Lab.

Helpers for date/time handling, business days, and frequency conversion.
"""

from datetime import datetime, timedelta
from typing import List
import pandas as pd


def parse_date(date_str: str) -> datetime:
    """
    Parse date string to datetime.

    Args:
        date_str: Date in YYYY-MM-DD or YYYY-MM-DD HH:MM:SS format

    Returns:
        Parsed datetime object
    """
    try:
        if ' ' in date_str:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        else:
            return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD or YYYY-MM-DD HH:MM:SS") from e


def format_date(dt: datetime, include_time: bool = False) -> str:
    """
    Format datetime to string.

    Args:
        dt: Datetime object
        include_time: Whether to include time component

    Returns:
        Formatted date string
    """
    if include_time:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        return dt.strftime("%Y-%m-%d")


def get_trading_days(start_date: str, end_date: str) -> int:
    """
    Calculate number of trading days between two dates.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Number of calendar days (simplified - doesn't account for holidays)
    """
    start = parse_date(start_date)
    end = parse_date(end_date)
    return (end - start).days


def annualization_factor(frequency: str) -> float:
    """
    Get annualization factor for a given data frequency.

    Args:
        frequency: Data frequency (e.g., '1m', '1h', '1D')

    Returns:
        Number of periods per year
    """
    freq_map = {
        '1m': 525600,      # Minutes per year
        '5m': 105120,
        '15m': 35040,
        '1h': 8760,        # Hours per year
        '4h': 2190,
        '1D': 365,         # Days per year
        '1W': 52,          # Weeks per year
        '1M': 12,          # Months per year
        'tick': 1,         # Not annualized
    }

    if frequency in freq_map:
        return freq_map[frequency]

    # Try to parse custom frequency
    import re
    match = re.match(r'(\d+)([mhDWM])', frequency)
    if match:
        num, unit = int(match.group(1)), match.group(2)
        base_factors = {'m': 525600, 'h': 8760, 'D': 365, 'W': 52, 'M': 12}
        if unit in base_factors:
            return base_factors[unit] / num

    # Default to daily
    return 365


def generate_date_range(
    start_date: str,
    end_date: str,
    frequency: str = '1D'
) -> List[datetime]:
    """
    Generate list of dates between start and end at given frequency.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        frequency: Frequency (pandas-compatible)

    Returns:
        List of datetime objects
    """
    start = parse_date(start_date)
    end = parse_date(end_date)

    # Convert our frequency format to pandas format
    freq_map = {
        '1m': 'T',
        '5m': '5T',
        '15m': '15T',
        '1h': 'H',
        '4h': '4H',
        '1D': 'D',
        '1W': 'W',
        '1M': 'M',
    }

    pd_freq = freq_map.get(frequency, 'D')

    dates = pd.date_range(start=start, end=end, freq=pd_freq)
    return dates.to_pydatetime().tolist()


def calculate_duration_hours(start: str, end: str) -> float:
    """
    Calculate duration in hours between two timestamps.

    Args:
        start: Start timestamp (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)
        end: End timestamp (YYYY-MM-DD HH:MM:SS or YYYY-MM-DD)

    Returns:
        Duration in hours
    """
    start_dt = parse_date(start)
    end_dt = parse_date(end)
    duration = end_dt - start_dt
    return duration.total_seconds() / 3600


def get_years_between(start_date: str, end_date: str) -> float:
    """
    Calculate fractional years between two dates.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Number of years (fractional)
    """
    days = get_trading_days(start_date, end_date)
    return days / 365.0
