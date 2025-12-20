"""
Alpha Graph Causality Analysis

Lead/lag detection and simple causality analysis.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from alpha_graph.models import (
    AlphaEdge,
    AlphaGraphSnapshot,
    TimeSeriesData,
    generate_edge_id,
)
from alpha_graph.utils import (
    compute_lagged_correlation,
    find_best_lag,
    align_time_series,
)
from alpha_graph.scoring import compute_edge_confidence
from alpha_graph.exceptions import InsufficientDataException


def detect_lead_lag_relationship(
    ts_a: TimeSeriesData,
    ts_b: TimeSeriesData,
    max_lag: int = 30,
    min_correlation: float = 0.3,
    min_confidence: float = 0.7,
) -> Optional[Tuple[int, float, float]]:
    """
    Detect lead/lag relationship between two time series.

    Args:
        ts_a: First time series (potential leader)
        ts_b: Second time series (potential lagger)
        max_lag: Maximum lag to test (in data points)
        min_correlation: Minimum correlation threshold
        min_confidence: Minimum confidence threshold

    Returns:
        Tuple of (lag, correlation, confidence) if relationship found, None otherwise
    """
    # Align time series
    aligned_a, aligned_b, common_ts = align_time_series(
        ts_a.values, ts_a.timestamps, ts_b.values, ts_b.timestamps
    )

    if len(aligned_a) < max_lag + 10:
        raise InsufficientDataException(required=max_lag + 10, actual=len(aligned_a))

    # Compute lagged correlations
    lagged_corrs = compute_lagged_correlation(aligned_a, aligned_b, max_lag)

    # Find best lag
    best_lag, best_corr, best_p = find_best_lag(lagged_corrs)

    # Check thresholds
    if abs(best_corr) < min_correlation:
        return None

    # Compute confidence
    sample_size = len(aligned_a) - best_lag
    confidence = compute_edge_confidence(best_corr, best_p, sample_size)

    if confidence < min_confidence:
        return None

    return best_lag, best_corr, confidence


def find_leading_indicators(
    target_node_id: str,
    snapshot: AlphaGraphSnapshot,
    min_lag: int = 1,
) -> List[AlphaEdge]:
    """
    Find nodes that lead the target node.

    Args:
        target_node_id: Node to find leaders for
        snapshot: Graph snapshot
        min_lag: Minimum lag to consider (default 1 = exclude contemporaneous)

    Returns:
        List of LEAD_LAG edges where target is the lagging node
    """
    # Find all edges pointing to target
    incoming_edges = snapshot.get_edges_to_node(target_node_id)

    # Filter for LEAD_LAG relationships with sufficient lag
    leading_edges = [
        edge
        for edge in incoming_edges
        if edge.relationship_type == "LEAD_LAG"
        and edge.lag_days is not None
        and edge.lag_days >= min_lag
    ]

    # Sort by lag (shortest lag first)
    leading_edges.sort(key=lambda e: e.lag_days or 0)

    return leading_edges


def find_lagging_indicators(
    source_node_id: str,
    snapshot: AlphaGraphSnapshot,
    min_lag: int = 1,
) -> List[AlphaEdge]:
    """
    Find nodes that lag the source node.

    Args:
        source_node_id: Node to find laggers for
        snapshot: Graph snapshot
        min_lag: Minimum lag to consider

    Returns:
        List of LEAD_LAG edges where source is the leading node
    """
    # Find all edges from source
    outgoing_edges = snapshot.get_edges_from_node(source_node_id)

    # Filter for LEAD_LAG relationships
    lagging_edges = [
        edge
        for edge in outgoing_edges
        if edge.relationship_type == "LEAD_LAG"
        and edge.lag_days is not None
        and edge.lag_days >= min_lag
    ]

    # Sort by lag
    lagging_edges.sort(key=lambda e: e.lag_days or 0)

    return lagging_edges


def compute_granger_causality_stub(
    ts_a: TimeSeriesData,
    ts_b: TimeSeriesData,
    max_lag: int = 5,
) -> Dict[str, float]:
    """
    Stub for Granger causality test.

    This is a simplified placeholder. A full implementation would use
    vector autoregression (VAR) and F-tests.

    Args:
        ts_a: First time series
        ts_b: Second time series
        max_lag: Maximum lag to test

    Returns:
        Dictionary with causality metrics
    """
    # Simplified: use lagged correlation as proxy
    aligned_a, aligned_b, _ = align_time_series(
        ts_a.values, ts_a.timestamps, ts_b.values, ts_b.timestamps
    )

    if len(aligned_a) < max_lag + 10:
        return {"causality_score": 0.0, "confidence": 0.0}

    # Test if A Granger-causes B
    lagged_corrs = compute_lagged_correlation(aligned_a, aligned_b, max_lag)
    best_lag, best_corr, best_p = find_best_lag(lagged_corrs)

    # Simple heuristic: strong lagged correlation suggests causality
    causality_score = abs(best_corr) if best_lag > 0 else 0.0
    confidence = 1.0 - best_p if best_lag > 0 else 0.0

    return {
        "causality_score": causality_score,
        "confidence": confidence,
        "best_lag": best_lag,
        "correlation": best_corr,
    }


def rank_by_predictive_power(
    target_node_id: str,
    snapshot: AlphaGraphSnapshot,
) -> List[Tuple[str, float]]:
    """
    Rank nodes by their predictive power for the target.

    Predictive power is based on lead/lag strength and confidence.

    Args:
        target_node_id: Node to find predictors for
        snapshot: Graph snapshot

    Returns:
        List of (node_id, predictive_power_score) sorted by score descending
    """
    leading_edges = find_leading_indicators(target_node_id, snapshot, min_lag=1)

    # Score each leading indicator
    scores = []
    for edge in leading_edges:
        # Predictive power = strength * confidence / sqrt(lag)
        # Penalize longer lags slightly
        lag_penalty = 1.0 / (1.0 + 0.1 * (edge.lag_days or 1))
        predictive_power = abs(edge.strength) * edge.confidence * lag_penalty
        scores.append((edge.from_node_id, predictive_power))

    # Sort by score descending
    scores.sort(key=lambda x: x[1], reverse=True)

    return scores
