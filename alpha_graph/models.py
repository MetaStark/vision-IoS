"""
Alpha Graph Models

Pydantic v2 models for Alpha Graph data contracts.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
import hashlib
import json


class AlphaNode(BaseModel):
    """Represents a single node in the Alpha Graph."""

    model_config = ConfigDict(frozen=True)

    node_id: str = Field(..., description="Unique node identifier")
    node_type: Literal[
        "MACRO",  # DXY, VIX, rates, CPI
        "ONCHAIN",  # Whale flow, NVT, miner activity
        "DERIV",  # Funding, OI, skew, basis
        "TECH",  # Technical indicators
        "REGIME",  # HMM states, vol regimes
        "SENTIMENT",  # Twitter, Reddit, news
        "STRATEGY",  # Alpha Lab strategy outputs
        "PORTFOLIO",  # Portfolio-level metrics
        "OTHER",
    ]
    label: str = Field(..., description="Human-readable label")
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def __hash__(self):
        """Make hashable for use in sets/dicts."""
        return hash(self.node_id)


class AlphaEdge(BaseModel):
    """Represents a relationship between two nodes."""

    model_config = ConfigDict(frozen=True)

    edge_id: str = Field(..., description="Unique edge identifier")
    from_node_id: str
    to_node_id: str
    relationship_type: Literal[
        "CORRELATION",  # Statistical correlation
        "CAUSALITY",  # Inferred causal relationship
        "LEAD_LAG",  # Time-lagged relationship
        "REGIME_CONDITIONAL",  # Only exists in certain regimes
    ]
    strength: float = Field(
        ..., ge=-1.0, le=1.0, description="Effect size or correlation"
    )
    direction: Literal["UNI", "BI"] = Field(default="BI")
    lag_days: Optional[int] = Field(
        default=None, description="Lag in days for lead/lag relationships"
    )
    regimes: List[str] = Field(
        default_factory=list, description="Applicable regime labels"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Statistical confidence [0-1]"
    )
    p_value: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    sample_size: Optional[int] = None
    window_days: Optional[int] = Field(
        default=None, description="Rolling window size"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __hash__(self):
        """Make hashable for use in sets/dicts."""
        return hash(self.edge_id)


class AlphaGraphSnapshot(BaseModel):
    """Immutable snapshot of the entire Alpha Graph."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str = Field(..., description="Unique snapshot identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    regime: Optional[str] = Field(default=None, description="Current regime context")
    nodes: List[AlphaNode]
    edges: List[AlphaEdge]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def node_count(self) -> int:
        """Number of nodes in the graph."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Number of edges in the graph."""
        return len(self.edges)

    def get_node(self, node_id: str) -> Optional[AlphaNode]:
        """Get node by ID."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_edge(self, edge_id: str) -> Optional[AlphaEdge]:
        """Get edge by ID."""
        for edge in self.edges:
            if edge.edge_id == edge_id:
                return edge
        return None

    def get_edges_from_node(self, node_id: str) -> List[AlphaEdge]:
        """Get all edges originating from a node."""
        return [edge for edge in self.edges if edge.from_node_id == node_id]

    def get_edges_to_node(self, node_id: str) -> List[AlphaEdge]:
        """Get all edges pointing to a node."""
        return [edge for edge in self.edges if edge.to_node_id == node_id]

    def get_connected_edges(self, node_id: str) -> List[AlphaEdge]:
        """Get all edges connected to a node (incoming or outgoing)."""
        return [
            edge
            for edge in self.edges
            if edge.from_node_id == node_id or edge.to_node_id == node_id
        ]


class AlphaGraphDelta(BaseModel):
    """Represents changes between two snapshots."""

    model_config = ConfigDict(frozen=True)

    delta_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    nodes_added: List[AlphaNode] = Field(default_factory=list)
    nodes_removed: List[str] = Field(default_factory=list)  # node_ids
    edges_added: List[AlphaEdge] = Field(default_factory=list)
    edges_removed: List[str] = Field(default_factory=list)  # edge_ids
    edges_updated: List[AlphaEdge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Check if delta contains any changes."""
        return bool(
            self.nodes_added
            or self.nodes_removed
            or self.edges_added
            or self.edges_removed
            or self.edges_updated
        )


class InfluenceScore(BaseModel):
    """Represents influence of one node on another."""

    node_id: str
    influence_score: float = Field(..., ge=0.0, description="Aggregate influence metric")
    direct_edges: int = Field(..., ge=0)
    indirect_paths: int = Field(..., ge=0)
    avg_path_strength: float
    max_path_strength: float = Field(default=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResult(BaseModel):
    """Result of a high-level graph query."""

    query_type: str
    target_node_id: Optional[str] = None
    regime: Optional[str] = None
    results: List[InfluenceScore]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GraphBuildConfig(BaseModel):
    """Configuration for building Alpha Graph."""

    correlation_windows: List[int] = Field(
        default_factory=lambda: [30, 90, 180],
        description="Rolling window sizes for correlation computation (days)",
    )
    min_correlation_threshold: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum correlation to create edge"
    )
    min_confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence for edges"
    )
    min_sample_size: int = Field(
        default=30, ge=1, description="Minimum data points for correlation"
    )
    max_lag_days: int = Field(
        default=30, ge=0, description="Maximum lag for lead/lag analysis"
    )
    include_regime_conditional: bool = Field(
        default=True, description="Compute regime-conditional relationships"
    )
    p_value_threshold: float = Field(
        default=0.05, ge=0.0, le=1.0, description="P-value threshold for significance"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphUpdateConfig(BaseModel):
    """Configuration for updating Alpha Graph."""

    incremental: bool = Field(
        default=True, description="Only update affected edges"
    )
    recompute_all: bool = Field(
        default=False, description="Force full recomputation"
    )
    correlation_windows: List[int] = Field(
        default_factory=lambda: [30, 90, 180],
        description="Rolling window sizes",
    )
    min_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimeSeriesData(BaseModel):
    """Container for time series data."""

    series_id: str
    timestamps: List[datetime]
    values: List[float]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamps", "values")
    def check_lengths_match(cls, v, info):
        """Ensure timestamps and values have same length."""
        if info.field_name == "values" and "timestamps" in info.data:
            if len(v) != len(info.data["timestamps"]):
                raise ValueError("timestamps and values must have same length")
        return v

    @property
    def length(self) -> int:
        """Number of data points."""
        return len(self.values)


def generate_edge_id(from_node_id: str, to_node_id: str, relationship_type: str) -> str:
    """Generate deterministic edge ID from components."""
    components = f"{from_node_id}_{to_node_id}_{relationship_type}"
    hash_digest = hashlib.md5(components.encode()).hexdigest()[:8]
    return f"edge_{hash_digest}_{relationship_type}"


def generate_snapshot_id(timestamp: datetime) -> str:
    """Generate snapshot ID from timestamp."""
    ts_str = timestamp.isoformat()
    return f"snapshot_{ts_str}"


def generate_delta_id(from_snapshot_id: str, to_snapshot_id: str) -> str:
    """Generate delta ID from snapshot IDs."""
    return f"delta_{from_snapshot_id}_to_{to_snapshot_id}"
