"""
Alpha Graph v1.0

Multi-layer relationship graph for market intelligence.
Represents relationships between macro factors, on-chain metrics, derivatives,
technical indicators, regimes, sentiment, strategies, and portfolio performance.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from alpha_graph.models import (
    AlphaNode,
    AlphaEdge,
    AlphaGraphSnapshot,
    AlphaGraphDelta,
    InfluenceScore,
    QueryResult,
    GraphBuildConfig,
    GraphUpdateConfig,
)
from alpha_graph.builder import build_graph
from alpha_graph.updater import update_graph
from alpha_graph.queries import (
    query_top_drivers,
    query_regime_changes,
    query_node_neighbors,
)
from alpha_graph.analytics import (
    compute_influence_scores,
    find_paths,
    analyze_regime_sensitivity,
)
from alpha_graph.serialization import (
    save_snapshot,
    load_snapshot,
    save_delta,
    load_delta,
)
from alpha_graph.exceptions import (
    AlphaGraphException,
    NodeNotFoundException,
    EdgeNotFoundException,
    InvalidCorrelationData,
    InsufficientDataException,
    GraphValidationError,
    SerializationError,
)

__version__ = "1.0.0"
__all__ = [
    # Models
    "AlphaNode",
    "AlphaEdge",
    "AlphaGraphSnapshot",
    "AlphaGraphDelta",
    "InfluenceScore",
    "QueryResult",
    "GraphBuildConfig",
    "GraphUpdateConfig",
    # Core functions
    "build_graph",
    "update_graph",
    # Queries
    "query_top_drivers",
    "query_regime_changes",
    "query_node_neighbors",
    # Analytics
    "compute_influence_scores",
    "find_paths",
    "analyze_regime_sensitivity",
    # Serialization
    "save_snapshot",
    "load_snapshot",
    "save_delta",
    "load_delta",
    # Exceptions
    "AlphaGraphException",
    "NodeNotFoundException",
    "EdgeNotFoundException",
    "InvalidCorrelationData",
    "InsufficientDataException",
    "GraphValidationError",
    "SerializationError",
]
