"""
Alpha Graph Updater

Incremental updates to Alpha Graph when new data arrives.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from alpha_graph.models import (
    AlphaNode,
    AlphaEdge,
    AlphaGraphSnapshot,
    AlphaGraphDelta,
    GraphUpdateConfig,
    TimeSeriesData,
    generate_delta_id,
    generate_snapshot_id,
)
from alpha_graph.builder import compute_pairwise_edges
from alpha_graph.exceptions import NodeNotFoundException


def identify_affected_nodes(
    current_snapshot: AlphaGraphSnapshot,
    new_data: Dict[str, TimeSeriesData],
) -> Set[str]:
    """
    Identify nodes that are affected by new data.

    Args:
        current_snapshot: Current graph snapshot
        new_data: New time series data

    Returns:
        Set of affected node IDs
    """
    affected = set()

    # Nodes with new data
    for node_id in new_data.keys():
        if current_snapshot.get_node(node_id):
            affected.add(node_id)

    return affected


def compute_delta(
    old_snapshot: AlphaGraphSnapshot,
    new_snapshot: AlphaGraphSnapshot,
) -> AlphaGraphDelta:
    """
    Compute delta between two snapshots.

    Args:
        old_snapshot: Previous snapshot
        new_snapshot: New snapshot

    Returns:
        AlphaGraphDelta
    """
    # Index nodes and edges
    old_nodes = {node.node_id: node for node in old_snapshot.nodes}
    new_nodes = {node.node_id: node for node in new_snapshot.nodes}
    old_edges = {edge.edge_id: edge for edge in old_snapshot.edges}
    new_edges = {edge.edge_id: edge for edge in new_snapshot.edges}

    # Find added/removed nodes
    nodes_added = [
        new_nodes[nid] for nid in new_nodes.keys() - old_nodes.keys()
    ]
    nodes_removed = list(old_nodes.keys() - new_nodes.keys())

    # Find added/removed/updated edges
    edges_added = [
        new_edges[eid] for eid in new_edges.keys() - old_edges.keys()
    ]
    edges_removed = list(old_edges.keys() - new_edges.keys())

    # Find updated edges (same ID but different properties)
    edges_updated = []
    for eid in old_edges.keys() & new_edges.keys():
        old_edge = old_edges[eid]
        new_edge = new_edges[eid]

        # Check if edge properties changed
        if (
            old_edge.strength != new_edge.strength
            or old_edge.confidence != new_edge.confidence
            or old_edge.p_value != new_edge.p_value
        ):
            edges_updated.append(new_edge)

    # Generate delta ID
    delta_id = generate_delta_id(old_snapshot.snapshot_id, new_snapshot.snapshot_id)

    return AlphaGraphDelta(
        delta_id=delta_id,
        from_snapshot_id=old_snapshot.snapshot_id,
        to_snapshot_id=new_snapshot.snapshot_id,
        nodes_added=nodes_added,
        nodes_removed=nodes_removed,
        edges_added=edges_added,
        edges_removed=edges_removed,
        edges_updated=edges_updated,
    )


def update_graph(
    current_snapshot: AlphaGraphSnapshot,
    new_time_series_data: Dict[str, TimeSeriesData],
    new_regime: Optional[str] = None,
    regime_labels: Optional[Dict[datetime, str]] = None,
    config: Optional[GraphUpdateConfig] = None,
) -> Tuple[AlphaGraphSnapshot, AlphaGraphDelta]:
    """
    Update graph with new data.

    Args:
        current_snapshot: Current graph snapshot
        new_time_series_data: New time series data (full series, not just new points)
        new_regime: Optional new regime label
        regime_labels: Optional updated regime labels
        config: Update configuration

    Returns:
        Tuple of (new_snapshot, delta)

    Example:
        >>> current = build_graph(...)
        >>> new_data = {...}  # Updated time series
        >>> new_snapshot, delta = update_graph(current, new_data, new_regime="BEAR")
    """
    if config is None:
        config = GraphUpdateConfig()

    # Determine which nodes are affected
    affected_nodes = identify_affected_nodes(current_snapshot, new_time_series_data)

    if config.recompute_all or not config.incremental:
        # Full recomputation - rebuild entire graph
        from alpha_graph.builder import build_graph, GraphBuildConfig

        # Convert update config to build config
        build_config = GraphBuildConfig(
            correlation_windows=config.correlation_windows,
            min_confidence_threshold=config.min_confidence_threshold,
        )

        # Extract node metadata from current snapshot
        node_metadata = {}
        for node in current_snapshot.nodes:
            node_metadata[node.node_id] = {
                "type": node.node_type,
                "label": node.label,
                "description": node.description,
                "metadata": node.metadata,
            }

        new_snapshot = build_graph(
            time_series_data=new_time_series_data,
            node_metadata=node_metadata,
            regime_labels=regime_labels,
            current_regime=new_regime or current_snapshot.regime,
            config=build_config,
        )

    else:
        # Incremental update - only recompute affected edges
        from alpha_graph.builder import GraphBuildConfig

        build_config = GraphBuildConfig(
            correlation_windows=config.correlation_windows,
            min_confidence_threshold=config.min_confidence_threshold,
        )

        # Start with current nodes and edges
        new_nodes = list(current_snapshot.nodes)
        old_edges_dict = {edge.edge_id: edge for edge in current_snapshot.edges}

        # Recompute edges involving affected nodes
        new_edges_for_affected = compute_pairwise_edges(
            new_time_series_data, build_config, regime_labels
        )

        # Filter to only edges involving affected nodes
        incremental_edges = [
            edge
            for edge in new_edges_for_affected
            if edge.from_node_id in affected_nodes or edge.to_node_id in affected_nodes
        ]

        # Remove old edges involving affected nodes
        edges_to_keep = [
            edge
            for edge in current_snapshot.edges
            if edge.from_node_id not in affected_nodes
            and edge.to_node_id not in affected_nodes
        ]

        # Combine
        new_edges = edges_to_keep + incremental_edges

        # Create new snapshot
        snapshot_id = generate_snapshot_id(datetime.utcnow())
        new_snapshot = AlphaGraphSnapshot(
            snapshot_id=snapshot_id,
            regime=new_regime or current_snapshot.regime,
            nodes=new_nodes,
            edges=new_edges,
            metadata={
                "config": config.model_dump(),
                "incremental_update": True,
                "affected_nodes": list(affected_nodes),
            },
        )

    # Compute delta
    delta = compute_delta(current_snapshot, new_snapshot)

    return new_snapshot, delta
