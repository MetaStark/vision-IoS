"""
Alpha Graph Queries

High-level query API for the Alpha Graph.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from typing import List, Optional
from alpha_graph.models import (
    AlphaGraphSnapshot,
    QueryResult,
    InfluenceScore,
)
from alpha_graph.analytics import (
    compute_influence_scores,
    identify_regime_changes,
    find_clusters,
)
from alpha_graph.causality import (
    find_leading_indicators,
    rank_by_predictive_power,
)
from alpha_graph.scoring import rank_edges_by_score
from alpha_graph.exceptions import NodeNotFoundException


def query_top_drivers(
    snapshot: AlphaGraphSnapshot,
    target_node_id: str,
    regime: Optional[str] = None,
    top_n: int = 10,
    min_confidence: float = 0.7,
) -> QueryResult:
    """
    Find top N drivers of a target node.

    Args:
        snapshot: Graph snapshot
        target_node_id: Node to find drivers for
        regime: Optional regime filter
        top_n: Number of top drivers to return
        min_confidence: Minimum edge confidence

    Returns:
        QueryResult with top drivers

    Example:
        >>> result = query_top_drivers(snapshot, "BTC-USD", regime="BULL", top_n=10)
        >>> for score in result.results[:5]:
        ...     print(f"{score.node_id}: {score.influence_score:.3f}")
    """
    if not snapshot.get_node(target_node_id):
        raise NodeNotFoundException(target_node_id)

    # Filter snapshot by regime if specified
    if regime:
        filtered_edges = [
            edge
            for edge in snapshot.edges
            if not edge.regimes or regime in edge.regimes
        ]
        filtered_snapshot = AlphaGraphSnapshot(
            snapshot_id=snapshot.snapshot_id,
            timestamp=snapshot.timestamp,
            regime=regime,
            nodes=snapshot.nodes,
            edges=filtered_edges,
        )
    else:
        filtered_snapshot = snapshot

    # Compute influence scores
    influence_scores = compute_influence_scores(
        target_node_id, filtered_snapshot, min_confidence=min_confidence
    )

    # Take top N
    top_scores = influence_scores[:top_n]

    return QueryResult(
        query_type="TOP_DRIVERS",
        target_node_id=target_node_id,
        regime=regime,
        results=top_scores,
        metadata={
            "total_influencers": len(influence_scores),
            "min_confidence": min_confidence,
        },
    )


def query_regime_changes(
    old_snapshot: AlphaGraphSnapshot,
    new_snapshot: AlphaGraphSnapshot,
) -> QueryResult:
    """
    Identify what changed between regimes.

    Args:
        old_snapshot: Snapshot before regime change
        new_snapshot: Snapshot after regime change

    Returns:
        QueryResult with regime change analysis
    """
    changes = identify_regime_changes(old_snapshot, new_snapshot)

    # Convert to InfluenceScore format for consistency
    # (even though it's a bit of a stretch)
    results = [
        InfluenceScore(
            node_id="REGIME_CHANGE_SUMMARY",
            influence_score=float(len(changes["strengthened"]) + len(changes["weakened"])),
            direct_edges=len(changes["appeared"]) + len(changes["disappeared"]),
            indirect_paths=0,
            avg_path_strength=0.0,
            metadata=changes,
        )
    ]

    return QueryResult(
        query_type="REGIME_CHANGES",
        regime=new_snapshot.regime,
        results=results,
        metadata={
            "from_regime": old_snapshot.regime,
            "to_regime": new_snapshot.regime,
            "summary": changes,
        },
    )


def query_node_neighbors(
    snapshot: AlphaGraphSnapshot,
    node_id: str,
    min_strength: float = 0.3,
    min_confidence: float = 0.7,
) -> QueryResult:
    """
    Find neighboring nodes (directly connected).

    Args:
        snapshot: Graph snapshot
        node_id: Node to find neighbors for
        min_strength: Minimum edge strength
        min_confidence: Minimum edge confidence

    Returns:
        QueryResult with neighbor information
    """
    if not snapshot.get_node(node_id):
        raise NodeNotFoundException(node_id)

    # Get all connected edges
    connected_edges = snapshot.get_connected_edges(node_id)

    # Filter by thresholds
    filtered_edges = [
        edge
        for edge in connected_edges
        if abs(edge.strength) >= min_strength and edge.confidence >= min_confidence
    ]

    # Rank by score
    ranked_edges = rank_edges_by_score(filtered_edges, min_confidence=min_confidence)

    # Convert to InfluenceScore
    results = []
    for edge in ranked_edges:
        neighbor_id = (
            edge.to_node_id if edge.from_node_id == node_id else edge.from_node_id
        )

        results.append(
            InfluenceScore(
                node_id=neighbor_id,
                influence_score=abs(edge.strength) * edge.confidence,
                direct_edges=1,
                indirect_paths=0,
                avg_path_strength=abs(edge.strength),
                max_path_strength=abs(edge.strength),
                metadata={
                    "edge_id": edge.edge_id,
                    "relationship_type": edge.relationship_type,
                    "strength": edge.strength,
                    "confidence": edge.confidence,
                },
            )
        )

    return QueryResult(
        query_type="NODE_NEIGHBORS",
        target_node_id=node_id,
        results=results,
        metadata={
            "total_neighbors": len(results),
            "min_strength": min_strength,
            "min_confidence": min_confidence,
        },
    )


def query_leading_indicators(
    snapshot: AlphaGraphSnapshot,
    target_node_id: str,
    top_n: int = 10,
) -> QueryResult:
    """
    Find nodes that lead the target (predictive indicators).

    Args:
        snapshot: Graph snapshot
        target_node_id: Node to find leaders for
        top_n: Number of top leaders to return

    Returns:
        QueryResult with leading indicators
    """
    if not snapshot.get_node(target_node_id):
        raise NodeNotFoundException(target_node_id)

    # Rank by predictive power
    leaders = rank_by_predictive_power(target_node_id, snapshot)

    # Take top N
    top_leaders = leaders[:top_n]

    # Convert to InfluenceScore
    results = []
    for node_id, predictive_power in top_leaders:
        # Get the edge for metadata
        edges = find_leading_indicators(target_node_id, snapshot)
        edge = next((e for e in edges if e.from_node_id == node_id), None)

        results.append(
            InfluenceScore(
                node_id=node_id,
                influence_score=predictive_power,
                direct_edges=1,
                indirect_paths=0,
                avg_path_strength=abs(edge.strength) if edge else 0.0,
                metadata={
                    "lag_days": edge.lag_days if edge else None,
                    "correlation": edge.strength if edge else None,
                },
            )
        )

    return QueryResult(
        query_type="LEADING_INDICATORS",
        target_node_id=target_node_id,
        results=results,
        metadata={"total_leaders": len(leaders)},
    )


def query_clusters(
    snapshot: AlphaGraphSnapshot,
    min_correlation: float = 0.7,
) -> QueryResult:
    """
    Find clusters of highly correlated nodes.

    Args:
        snapshot: Graph snapshot
        min_correlation: Minimum correlation for clustering

    Returns:
        QueryResult with cluster information
    """
    clusters = find_clusters(snapshot, min_correlation=min_correlation)

    # Convert to InfluenceScore format
    results = []
    for i, cluster in enumerate(clusters):
        cluster_id = f"CLUSTER_{i+1}"
        results.append(
            InfluenceScore(
                node_id=cluster_id,
                influence_score=float(len(cluster)),
                direct_edges=0,
                indirect_paths=0,
                avg_path_strength=0.0,
                metadata={
                    "cluster_size": len(cluster),
                    "members": list(cluster),
                },
            )
        )

    # Sort by cluster size
    results.sort(key=lambda x: x.influence_score, reverse=True)

    return QueryResult(
        query_type="CLUSTERS",
        results=results,
        metadata={
            "total_clusters": len(clusters),
            "min_correlation": min_correlation,
        },
    )
