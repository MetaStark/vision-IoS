"""
Forecast-Outcome Reconciliation

Logic to match forecasts to realized outcomes.

Author: FjordHQ Engineering Team
Date: 2025-11-18
ADR: ADR-061
"""

from typing import List

from prediction_ledger.models import (
    ForecastRecord,
    OutcomeRecord,
    ForecastOutcomePair,
    ReconciliationConfig,
)
from prediction_ledger.utils import is_within_time_window
from prediction_ledger.exceptions import ReconciliationException


def reconcile_forecasts_to_outcomes(
    forecasts: List[ForecastRecord],
    outcomes: List[OutcomeRecord],
    config: ReconciliationConfig | None = None,
) -> List[ForecastOutcomePair]:
    """
    Match forecasts to outcomes based on reconciliation rules.

    Matching logic:
    1. target_id must match
    2. forecast.timestamp + forecast.horizon must be within tolerance of outcome.timestamp

    Args:
        forecasts: List of forecast records
        outcomes: List of outcome records
        config: Reconciliation configuration

    Returns:
        List of matched forecast-outcome pairs

    Raises:
        ReconciliationException: If reconciliation fails
    """
    if config is None:
        config = ReconciliationConfig()

    pairs: List[ForecastOutcomePair] = []
    matched_outcomes = set()

    for forecast in forecasts:
        # Find matching outcome
        matching_outcome = _find_matching_outcome(
            forecast, outcomes, matched_outcomes, config
        )

        if matching_outcome:
            pair = ForecastOutcomePair(
                forecast=forecast, outcome=matching_outcome, match_confidence=1.0
            )
            pairs.append(pair)

            if not config.allow_multiple_matches:
                matched_outcomes.add(matching_outcome.outcome_id)

    return pairs


def _find_matching_outcome(
    forecast: ForecastRecord,
    outcomes: List[OutcomeRecord],
    matched_outcomes: set,
    config: ReconciliationConfig,
) -> OutcomeRecord | None:
    """
    Find matching outcome for a forecast.

    Args:
        forecast: Forecast record
        outcomes: List of outcome records
        matched_outcomes: Set of already matched outcome IDs
        config: Reconciliation config

    Returns:
        Matching outcome or None
    """
    # Expected outcome timestamp
    expected_outcome_time = forecast.timestamp + forecast.horizon

    for outcome in outcomes:
        # Skip if already matched (unless multiple matches allowed)
        if not config.allow_multiple_matches and outcome.outcome_id in matched_outcomes:
            continue

        # Check target match
        if config.require_exact_target_match and outcome.target_id != forecast.target_id:
            continue

        # Check time window
        if is_within_time_window(
            expected_outcome_time, outcome.timestamp, config.time_window_tolerance
        ):
            return outcome

    return None


def group_pairs_by_target(
    pairs: List[ForecastOutcomePair],
) -> dict[str, List[ForecastOutcomePair]]:
    """
    Group forecast-outcome pairs by target_id.

    Args:
        pairs: List of pairs

    Returns:
        Dict mapping target_id to list of pairs
    """
    grouped: dict[str, List[ForecastOutcomePair]] = {}

    for pair in pairs:
        target_id = pair.forecast.target_id
        if target_id not in grouped:
            grouped[target_id] = []
        grouped[target_id].append(pair)

    return grouped


def filter_pairs_by_time_range(
    pairs: List[ForecastOutcomePair],
    start_time: any,
    end_time: any,
) -> List[ForecastOutcomePair]:
    """
    Filter pairs by forecast timestamp range.

    Args:
        pairs: List of pairs
        start_time: Start of time range
        end_time: End of time range

    Returns:
        Filtered list of pairs
    """
    return [
        pair
        for pair in pairs
        if start_time <= pair.forecast.timestamp <= end_time
    ]


# ============================================================================
# GROUPING FUNCTIONS (Extended v1.1)
# ============================================================================

def group_matched_pairs_by_horizon(
    pairs: List[ForecastOutcomePair],
) -> dict[str, List[ForecastOutcomePair]]:
    """
    Group forecast-outcome pairs by horizon bucket.

    Args:
        pairs: List of matched pairs

    Returns:
        Dict mapping horizon bucket to list of pairs
    """
    from prediction_ledger.utils import derive_horizon_bucket

    grouped: dict[str, List[ForecastOutcomePair]] = {}

    for pair in pairs:
        bucket = derive_horizon_bucket(pair.forecast.horizon)
        if bucket not in grouped:
            grouped[bucket] = []
        grouped[bucket].append(pair)

    return grouped


def group_matched_pairs_by_target_type(
    pairs: List[ForecastOutcomePair],
) -> dict[str, List[ForecastOutcomePair]]:
    """
    Group forecast-outcome pairs by target type.

    Args:
        pairs: List of matched pairs

    Returns:
        Dict mapping target_type to list of pairs
    """
    grouped: dict[str, List[ForecastOutcomePair]] = {}

    for pair in pairs:
        target_type = pair.forecast.target_type
        if target_type not in grouped:
            grouped[target_type] = []
        grouped[target_type].append(pair)

    return grouped


def group_matched_pairs_by_both(
    pairs: List[ForecastOutcomePair],
) -> dict[tuple[str, str], List[ForecastOutcomePair]]:
    """
    Group forecast-outcome pairs by (target_type, horizon_bucket).

    Args:
        pairs: List of matched pairs

    Returns:
        Dict mapping (target_type, horizon_bucket) to list of pairs
    """
    from prediction_ledger.utils import derive_horizon_bucket

    grouped: dict[tuple[str, str], List[ForecastOutcomePair]] = {}

    for pair in pairs:
        target_type = pair.forecast.target_type
        bucket = derive_horizon_bucket(pair.forecast.horizon)
        key = (target_type, bucket)

        if key not in grouped:
            grouped[key] = []
        grouped[key].append(pair)

    return grouped
