"""
Alpha Graph Scoring

Functions for computing confidence scores, importance metrics, and regime sensitivity.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from typing import Dict, List, Optional
from alpha_graph.models import AlphaNode, AlphaEdge, AlphaGraphSnapshot
from alpha_graph.utils import compute_confidence_score


def compute_edge_confidence(
    correlation: float,
    p_value: float,
    sample_size: int,
    config_min_sample: int = 30,
) -> float:
    """
    Compute confidence score for an edge.

    Args:
        correlation: Correlation coefficient
        p_value: Statistical p-value
        sample_size: Number of data points
        config_min_sample: Minimum sample size from config

    Returns:
        Confidence score [0-1]
    """
    return compute_confidence_score(
        correlation, p_value, sample_size, config_min_sample
    )


def compute_node_importance(
    node_id: str,
    snapshot: AlphaGraphSnapshot,
) -> float:
    """
    Compute importance score for a node based on its connectivity.

    Importance is based on:
    - Number of connected edges
    - Average edge strength
    - Edge confidence

    Args:
        node_id: Node to score
        snapshot: Graph snapshot

    Returns:
        Importance score [0-1]
    """
    edges = snapshot.get_connected_edges(node_id)

    if not edges:
        return 0.0

    # Count edges
    edge_count = len(edges)

    # Average edge strength (absolute value)
    avg_strength = sum(abs(edge.strength) for edge in edges) / edge_count

    # Average confidence
    avg_confidence = sum(edge.confidence for edge in edges) / edge_count

    # Normalize edge count (diminishing returns after 10 edges)
    normalized_count = min(edge_count / 10.0, 1.0)

    # Weighted combination
    importance = 0.4 * normalized_count + 0.3 * avg_strength + 0.3 * avg_confidence

    return min(1.0, importance)


def compute_regime_sensitivity(
    node_id: str,
    snapshot: AlphaGraphSnapshot,
) -> Dict[str, float]:
    """
    Compute regime sensitivity for a node.

    Returns how much the node's relationships vary across regimes.

    Args:
        node_id: Node to analyze
        snapshot: Graph snapshot

    Returns:
        Dictionary mapping regime -> sensitivity score
    """
    edges = snapshot.get_connected_edges(node_id)

    if not edges:
        return {}

    # Group edges by regime
    regime_edges: Dict[str, List[AlphaEdge]] = {}
    for edge in edges:
        for regime in edge.regimes:
            if regime not in regime_edges:
                regime_edges[regime] = []
            regime_edges[regime].append(edge)

    # Compute sensitivity for each regime
    sensitivity: Dict[str, float] = {}

    for regime, regime_edge_list in regime_edges.items():
        # Number of edges active in this regime
        edge_count = len(regime_edge_list)

        # Average strength in this regime
        avg_strength = sum(abs(e.strength) for e in regime_edge_list) / edge_count

        # Sensitivity is combination of edge count and strength
        normalized_count = min(edge_count / 10.0, 1.0)
        sensitivity[regime] = 0.5 * normalized_count + 0.5 * avg_strength

    return sensitivity


def rank_edges_by_strength(
    edges: List[AlphaEdge],
    min_confidence: float = 0.0,
) -> List[AlphaEdge]:
    """
    Rank edges by absolute strength, filtered by minimum confidence.

    Args:
        edges: List of edges
        min_confidence: Minimum confidence threshold

    Returns:
        Sorted list of edges (strongest first)
    """
    filtered = [e for e in edges if e.confidence >= min_confidence]
    return sorted(filtered, key=lambda e: abs(e.strength), reverse=True)


def rank_edges_by_confidence(
    edges: List[AlphaEdge],
    min_strength: float = 0.0,
) -> List[AlphaEdge]:
    """
    Rank edges by confidence, filtered by minimum strength.

    Args:
        edges: List of edges
        min_strength: Minimum absolute strength threshold

    Returns:
        Sorted list of edges (highest confidence first)
    """
    filtered = [e for e in edges if abs(e.strength) >= min_strength]
    return sorted(filtered, key=lambda e: e.confidence, reverse=True)


def compute_edge_score(edge: AlphaEdge) -> float:
    """
    Compute composite score for an edge.

    Combines strength and confidence into a single metric.

    Args:
        edge: Edge to score

    Returns:
        Composite score [0-1]
    """
    # Absolute strength weighted by confidence
    return abs(edge.strength) * edge.confidence


def rank_edges_by_score(
    edges: List[AlphaEdge],
    min_confidence: float = 0.0,
) -> List[AlphaEdge]:
    """
    Rank edges by composite score.

    Args:
        edges: List of edges
        min_confidence: Minimum confidence threshold

    Returns:
        Sorted list of edges (highest score first)
    """
    filtered = [e for e in edges if e.confidence >= min_confidence]
    return sorted(filtered, key=compute_edge_score, reverse=True)
