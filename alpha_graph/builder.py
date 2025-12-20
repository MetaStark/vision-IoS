"""
Alpha Graph Builder

Functions for constructing Alpha Graph from time series data and metrics.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from datetime import datetime
from typing import Dict, List, Optional, Set
from alpha_graph.models import (
    AlphaNode,
    AlphaEdge,
    AlphaGraphSnapshot,
    GraphBuildConfig,
    TimeSeriesData,
    generate_edge_id,
    generate_snapshot_id,
)
from alpha_graph.utils import (
    compute_correlation,
    compute_lagged_correlation,
    find_best_lag,
    filter_by_regime,
    align_time_series,
    validate_time_series,
)
from alpha_graph.scoring import compute_edge_confidence
from alpha_graph.exceptions import InsufficientDataException, InvalidCorrelationData


def create_node(
    node_id: str,
    node_type: str,
    label: str,
    description: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> AlphaNode:
    """
    Create an AlphaNode.

    Args:
        node_id: Unique identifier
        node_type: Node type (MACRO, ONCHAIN, etc.)
        label: Human-readable label
        description: Optional description
        metadata: Optional metadata

    Returns:
        AlphaNode instance
    """
    return AlphaNode(
        node_id=node_id,
        node_type=node_type,
        label=label,
        description=description,
        metadata=metadata or {},
    )


def create_correlation_edge(
    from_node_id: str,
    to_node_id: str,
    correlation: float,
    p_value: float,
    sample_size: int,
    window_days: Optional[int] = None,
    regimes: Optional[List[str]] = None,
    config: Optional[GraphBuildConfig] = None,
) -> Optional[AlphaEdge]:
    """
    Create a correlation edge between two nodes.

    Args:
        from_node_id: Source node
        to_node_id: Target node
        correlation: Correlation coefficient
        p_value: Statistical p-value
        sample_size: Number of data points
        window_days: Rolling window size
        regimes: Applicable regimes
        config: Build configuration

    Returns:
        AlphaEdge if correlation meets thresholds, None otherwise
    """
    if config is None:
        config = GraphBuildConfig()

    # Check if correlation meets minimum threshold
    if abs(correlation) < config.min_correlation_threshold:
        return None

    # Compute confidence
    confidence = compute_edge_confidence(
        correlation, p_value, sample_size, config.min_sample_size
    )

    # Check if confidence meets minimum threshold
    if confidence < config.min_confidence_threshold:
        return None

    # Generate edge ID
    edge_id = generate_edge_id(from_node_id, to_node_id, "CORRELATION")

    return AlphaEdge(
        edge_id=edge_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        relationship_type="CORRELATION",
        strength=correlation,
        direction="BI",  # Correlation is bidirectional
        lag_days=None,
        regimes=regimes or [],
        confidence=confidence,
        p_value=p_value,
        sample_size=sample_size,
        window_days=window_days,
    )


def create_lead_lag_edge(
    from_node_id: str,
    to_node_id: str,
    lag_days: int,
    correlation: float,
    p_value: float,
    sample_size: int,
    regimes: Optional[List[str]] = None,
    config: Optional[GraphBuildConfig] = None,
) -> Optional[AlphaEdge]:
    """
    Create a lead/lag edge between two nodes.

    Args:
        from_node_id: Leading node
        to_node_id: Lagging node
        lag_days: Lag in days
        correlation: Lagged correlation
        p_value: Statistical p-value
        sample_size: Number of data points
        regimes: Applicable regimes
        config: Build configuration

    Returns:
        AlphaEdge if correlation meets thresholds, None otherwise
    """
    if config is None:
        config = GraphBuildConfig()

    # Check if correlation meets minimum threshold
    if abs(correlation) < config.min_correlation_threshold:
        return None

    # Compute confidence
    confidence = compute_edge_confidence(
        correlation, p_value, sample_size, config.min_sample_size
    )

    # Check if confidence meets minimum threshold
    if confidence < config.min_confidence_threshold:
        return None

    # Generate edge ID
    edge_id = generate_edge_id(from_node_id, to_node_id, "LEAD_LAG")

    return AlphaEdge(
        edge_id=edge_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        relationship_type="LEAD_LAG",
        strength=correlation,
        direction="UNI",  # Lead/lag is unidirectional
        lag_days=lag_days,
        regimes=regimes or [],
        confidence=confidence,
        p_value=p_value,
        sample_size=sample_size,
    )


def compute_pairwise_edges(
    ts_data_dict: Dict[str, TimeSeriesData],
    config: GraphBuildConfig,
    regime_labels: Optional[Dict[datetime, str]] = None,
) -> List[AlphaEdge]:
    """
    Compute pairwise correlation edges for all time series.

    Args:
        ts_data_dict: Dictionary mapping node_id -> TimeSeriesData
        config: Build configuration
        regime_labels: Optional regime labels for regime-conditional analysis

    Returns:
        List of AlphaEdge objects
    """
    edges = []
    node_ids = list(ts_data_dict.keys())

    # Compute pairwise correlations
    for i, node_a in enumerate(node_ids):
        for node_b in node_ids[i + 1 :]:  # Avoid duplicates
            ts_a = ts_data_dict[node_a]
            ts_b = ts_data_dict[node_b]

            try:
                # Align time series
                aligned_a, aligned_b, common_ts = align_time_series(
                    ts_a.values, ts_a.timestamps, ts_b.values, ts_b.timestamps
                )

                if len(aligned_a) < config.min_sample_size:
                    continue

                # Compute correlation for each window size
                for window in config.correlation_windows:
                    if len(aligned_a) >= window:
                        corr, p_val = compute_correlation(
                            aligned_a, aligned_b, window=window
                        )

                        # Create edge
                        edge = create_correlation_edge(
                            from_node_id=node_a,
                            to_node_id=node_b,
                            correlation=corr,
                            p_value=p_val,
                            sample_size=min(window, len(aligned_a)),
                            window_days=window,
                            config=config,
                        )

                        if edge:
                            edges.append(edge)

                # Compute lead/lag relationships if configured
                if config.max_lag_days > 0:
                    lagged_corrs = compute_lagged_correlation(
                        aligned_a, aligned_b, max_lag=min(config.max_lag_days, len(aligned_a) // 3)
                    )

                    best_lag, best_corr, best_p = find_best_lag(lagged_corrs)

                    if best_lag > 0:  # Only create edge if there's actual lag
                        edge = create_lead_lag_edge(
                            from_node_id=node_a,
                            to_node_id=node_b,
                            lag_days=best_lag,
                            correlation=best_corr,
                            p_value=best_p,
                            sample_size=len(aligned_a) - best_lag,
                            config=config,
                        )

                        if edge:
                            edges.append(edge)

                # Compute regime-conditional correlations if configured
                if config.include_regime_conditional and regime_labels:
                    # Get unique regimes
                    regimes = set(regime_labels.values())

                    for regime in regimes:
                        filtered_a, filtered_ts_a = filter_by_regime(
                            ts_a.values, ts_a.timestamps, regime_labels, regime
                        )
                        filtered_b, filtered_ts_b = filter_by_regime(
                            ts_b.values, ts_b.timestamps, regime_labels, regime
                        )

                        # Align filtered series
                        aligned_regime_a, aligned_regime_b, _ = align_time_series(
                            filtered_a, filtered_ts_a, filtered_b, filtered_ts_b
                        )

                        if len(aligned_regime_a) >= config.min_sample_size:
                            corr, p_val = compute_correlation(
                                aligned_regime_a, aligned_regime_b
                            )

                            edge = create_correlation_edge(
                                from_node_id=node_a,
                                to_node_id=node_b,
                                correlation=corr,
                                p_value=p_val,
                                sample_size=len(aligned_regime_a),
                                regimes=[regime],
                                config=config,
                            )

                            if edge:
                                # Mark as regime-conditional
                                edge = AlphaEdge(
                                    **{**edge.model_dump(), "relationship_type": "REGIME_CONDITIONAL"}
                                )
                                edges.append(edge)

            except (InvalidCorrelationData, InsufficientDataException):
                # Skip pairs that can't be computed
                continue

    return edges


def build_graph(
    time_series_data: Dict[str, TimeSeriesData],
    node_metadata: Dict[str, Dict] = None,
    regime_labels: Optional[Dict[datetime, str]] = None,
    current_regime: Optional[str] = None,
    config: Optional[GraphBuildConfig] = None,
) -> AlphaGraphSnapshot:
    """
    Build Alpha Graph from time series data.

    Args:
        time_series_data: Dictionary mapping node_id -> TimeSeriesData
        node_metadata: Optional metadata for each node (node_id -> {type, label, description})
        regime_labels: Optional regime labels for regime-conditional analysis
        current_regime: Current regime label
        config: Build configuration

    Returns:
        AlphaGraphSnapshot

    Example:
        >>> ts_data = {
        ...     "BTC-USD": TimeSeriesData(
        ...         series_id="BTC-USD",
        ...         timestamps=[...],
        ...         values=[...],
        ...     ),
        ...     "DXY": TimeSeriesData(
        ...         series_id="DXY",
        ...         timestamps=[...],
        ...         values=[...],
        ...     ),
        ... }
        >>> metadata = {
        ...     "BTC-USD": {"type": "TECH", "label": "Bitcoin Price"},
        ...     "DXY": {"type": "MACRO", "label": "US Dollar Index"},
        ... }
        >>> snapshot = build_graph(ts_data, metadata)
    """
    if config is None:
        config = GraphBuildConfig()

    if node_metadata is None:
        node_metadata = {}

    # Create nodes
    nodes = []
    for node_id, ts_data in time_series_data.items():
        meta = node_metadata.get(node_id, {})
        node = create_node(
            node_id=node_id,
            node_type=meta.get("type", "OTHER"),
            label=meta.get("label", node_id),
            description=meta.get("description"),
            metadata=meta.get("metadata", {}),
        )
        nodes.append(node)

    # Compute edges
    edges = compute_pairwise_edges(time_series_data, config, regime_labels)

    # Generate snapshot ID
    snapshot_id = generate_snapshot_id(datetime.utcnow())

    # Create snapshot
    snapshot = AlphaGraphSnapshot(
        snapshot_id=snapshot_id,
        regime=current_regime,
        nodes=nodes,
        edges=edges,
        metadata={
            "config": config.model_dump(),
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    )

    return snapshot
