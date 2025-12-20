"""
Alpha Graph Analytics

Graph analytics, pathfinding, and influence analysis.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from typing import Dict, List, Optional, Set, Tuple
from alpha_graph.models import (
    AlphaNode,
    AlphaEdge,
    AlphaGraphSnapshot,
    InfluenceScore,
)
from alpha_graph.scoring import compute_node_importance, compute_regime_sensitivity
from alpha_graph.exceptions import NodeNotFoundException


def find_paths(
    snapshot: AlphaGraphSnapshot,
    from_node_id: str,
    to_node_id: str,
    max_depth: int = 3,
    min_edge_confidence: float = 0.5,
) -> List[List[str]]:
    """
    Find paths between two nodes.

    Args:
        snapshot: Graph snapshot
        from_node_id: Starting node
        to_node_id: Target node
        max_depth: Maximum path length
        min_edge_confidence: Minimum edge confidence to traverse

    Returns:
        List of paths, where each path is a list of node IDs

    Raises:
        NodeNotFoundException: If either node doesn't exist
    """
    if not snapshot.get_node(from_node_id):
        raise NodeNotFoundException(from_node_id)
    if not snapshot.get_node(to_node_id):
        raise NodeNotFoundException(to_node_id)

    paths = []

    def dfs(current: str, target: str, path: List[str], depth: int):
        """Depth-first search for paths."""
        if depth > max_depth:
            return

        if current == target:
            paths.append(path.copy())
            return

        # Get outgoing edges from current node
        outgoing = snapshot.get_edges_from_node(current)

        for edge in outgoing:
            if edge.confidence < min_edge_confidence:
                continue

            next_node = edge.to_node_id

            # Avoid cycles
            if next_node not in path:
                path.append(next_node)
                dfs(next_node, target, path, depth + 1)
                path.pop()

    # Start DFS
    dfs(from_node_id, to_node_id, [from_node_id], 0)

    return paths


def compute_path_strength(
    path: List[str],
    snapshot: AlphaGraphSnapshot,
) -> float:
    """
    Compute strength of a path (product of edge strengths).

    Args:
        path: List of node IDs forming a path
        snapshot: Graph snapshot

    Returns:
        Path strength (product of absolute edge strengths)
    """
    if len(path) < 2:
        return 0.0

    strength = 1.0

    for i in range(len(path) - 1):
        from_node = path[i]
        to_node = path[i + 1]

        # Find edge
        edge = None
        for e in snapshot.edges:
            if e.from_node_id == from_node and e.to_node_id == to_node:
                edge = e
                break

        if edge is None:
            return 0.0  # Path is broken

        strength *= abs(edge.strength)

    return strength


def compute_influence_scores(
    target_node_id: str,
    snapshot: AlphaGraphSnapshot,
    max_depth: int = 2,
    min_confidence: float = 0.5,
) -> List[InfluenceScore]:
    """
    Compute influence scores for all nodes affecting the target.

    Args:
        target_node_id: Node to analyze
        snapshot: Graph snapshot
        max_depth: Maximum path depth to consider
        min_confidence: Minimum edge confidence

    Returns:
        List of InfluenceScore objects, sorted by influence descending
    """
    if not snapshot.get_node(target_node_id):
        raise NodeNotFoundException(target_node_id)

    influence_map: Dict[str, InfluenceScore] = {}

    # Get all nodes
    all_node_ids = [node.node_id for node in snapshot.nodes]

    for source_node_id in all_node_ids:
        if source_node_id == target_node_id:
            continue

        # Find paths from source to target
        paths = find_paths(
            snapshot,
            source_node_id,
            target_node_id,
            max_depth=max_depth,
            min_edge_confidence=min_confidence,
        )

        if not paths:
            continue

        # Count direct vs indirect
        direct_edges = 0
        indirect_paths = 0
        path_strengths = []

        for path in paths:
            if len(path) == 2:
                direct_edges += 1
            else:
                indirect_paths += 1

            # Compute path strength
            strength = compute_path_strength(path, snapshot)
            path_strengths.append(strength)

        # Aggregate influence
        avg_path_strength = sum(path_strengths) / len(path_strengths)
        max_path_strength = max(path_strengths)

        # Overall influence score (weighted by direct edges)
        influence_score = avg_path_strength * (1.0 + 0.5 * direct_edges)

        influence_map[source_node_id] = InfluenceScore(
            node_id=source_node_id,
            influence_score=influence_score,
            direct_edges=direct_edges,
            indirect_paths=indirect_paths,
            avg_path_strength=avg_path_strength,
            max_path_strength=max_path_strength,
        )

    # Sort by influence
    influence_list = list(influence_map.values())
    influence_list.sort(key=lambda x: x.influence_score, reverse=True)

    return influence_list


def analyze_regime_sensitivity(
    node_id: str,
    snapshot: AlphaGraphSnapshot,
) -> Dict[str, float]:
    """
    Analyze regime sensitivity for a node.

    Args:
        node_id: Node to analyze
        snapshot: Graph snapshot

    Returns:
        Dictionary mapping regime -> sensitivity score
    """
    if not snapshot.get_node(node_id):
        raise NodeNotFoundException(node_id)

    return compute_regime_sensitivity(node_id, snapshot)


def identify_regime_changes(
    old_snapshot: AlphaGraphSnapshot,
    new_snapshot: AlphaGraphSnapshot,
) -> Dict[str, List[str]]:
    """
    Identify which edges changed due to regime transition.

    Args:
        old_snapshot: Snapshot before regime change
        new_snapshot: Snapshot after regime change

    Returns:
        Dictionary with:
        - "strengthened": List of edge IDs that got stronger
        - "weakened": List of edge IDs that got weaker
        - "appeared": List of edge IDs that appeared
        - "disappeared": List of edge IDs that disappeared
    """
    old_edges = {edge.edge_id: edge for edge in old_snapshot.edges}
    new_edges = {edge.edge_id: edge for edge in new_snapshot.edges}

    strengthened = []
    weakened = []
    appeared = list(new_edges.keys() - old_edges.keys())
    disappeared = list(old_edges.keys() - new_edges.keys())

    # Check for strength changes
    for edge_id in old_edges.keys() & new_edges.keys():
        old_strength = abs(old_edges[edge_id].strength)
        new_strength = abs(new_edges[edge_id].strength)

        if new_strength > old_strength * 1.2:  # 20% threshold
            strengthened.append(edge_id)
        elif new_strength < old_strength * 0.8:
            weakened.append(edge_id)

    return {
        "strengthened": strengthened,
        "weakened": weakened,
        "appeared": appeared,
        "disappeared": disappeared,
    }


def find_clusters(
    snapshot: AlphaGraphSnapshot,
    min_correlation: float = 0.7,
) -> List[Set[str]]:
    """
    Find clusters of highly correlated nodes.

    Simple clustering based on correlation strength.

    Args:
        snapshot: Graph snapshot
        min_correlation: Minimum correlation for cluster membership

    Returns:
        List of node ID sets (clusters)
    """
    # Build adjacency list of strong correlations
    adjacency: Dict[str, Set[str]] = {}

    for edge in snapshot.edges:
        if edge.relationship_type != "CORRELATION":
            continue

        if abs(edge.strength) >= min_correlation:
            if edge.from_node_id not in adjacency:
                adjacency[edge.from_node_id] = set()
            if edge.to_node_id not in adjacency:
                adjacency[edge.to_node_id] = set()

            adjacency[edge.from_node_id].add(edge.to_node_id)
            adjacency[edge.to_node_id].add(edge.from_node_id)

    # Find connected components
    visited = set()
    clusters = []

    def dfs(node: str, cluster: Set[str]):
        """Depth-first search for clustering."""
        visited.add(node)
        cluster.add(node)

        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, cluster)

    for node_id in adjacency.keys():
        if node_id not in visited:
            cluster = set()
            dfs(node_id, cluster)
            if len(cluster) > 1:  # Only include multi-node clusters
                clusters.append(cluster)

    return clusters


def compute_centrality(
    snapshot: AlphaGraphSnapshot,
) -> Dict[str, float]:
    """
    Compute degree centrality for all nodes.

    Centrality = number of connected edges / total possible edges.

    Args:
        snapshot: Graph snapshot

    Returns:
        Dictionary mapping node_id -> centrality score
    """
    node_ids = [node.node_id for node in snapshot.nodes]
    n = len(node_ids)

    if n <= 1:
        return {node_id: 0.0 for node_id in node_ids}

    centrality = {}

    for node_id in node_ids:
        degree = len(snapshot.get_connected_edges(node_id))
        # Normalize by maximum possible degree
        centrality[node_id] = degree / (n - 1)

    return centrality
