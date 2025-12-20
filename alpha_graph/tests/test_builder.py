"""
Test Alpha Graph Builder

Tests for graph construction functionality.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

import pytest
from datetime import datetime, timedelta
from alpha_graph.models import TimeSeriesData, GraphBuildConfig
from alpha_graph.builder import build_graph, create_node, create_correlation_edge
from alpha_graph.exceptions import InsufficientDataException


def create_synthetic_timeseries(
    series_id: str,
    n_points: int = 100,
    trend: float = 0.0,
    volatility: float = 0.01,
) -> TimeSeriesData:
    """Create synthetic time series for testing."""
    import random

    timestamps = [datetime.utcnow() - timedelta(days=n_points - i) for i in range(n_points)]
    values = []
    value = 100.0

    for i in range(n_points):
        value += trend + random.gauss(0, volatility * value)
        values.append(value)

    return TimeSeriesData(
        series_id=series_id,
        timestamps=timestamps,
        values=values,
    )


def test_create_node():
    """Test node creation."""
    node = create_node(
        node_id="BTC-USD",
        node_type="TECH",
        label="Bitcoin Price",
        description="BTC/USD spot price",
    )

    assert node.node_id == "BTC-USD"
    assert node.node_type == "TECH"
    assert node.label == "Bitcoin Price"


def test_build_graph_basic():
    """Test basic graph construction."""
    # Create synthetic time series
    ts_btc = create_synthetic_timeseries("BTC-USD", n_points=100, trend=0.001)
    ts_eth = create_synthetic_timeseries("ETH-USD", n_points=100, trend=0.001)
    ts_dxy = create_synthetic_timeseries("DXY", n_points=100, trend=-0.0005)

    time_series_data = {
        "BTC-USD": ts_btc,
        "ETH-USD": ts_eth,
        "DXY": ts_dxy,
    }

    node_metadata = {
        "BTC-USD": {"type": "TECH", "label": "Bitcoin"},
        "ETH-USD": {"type": "TECH", "label": "Ethereum"},
        "DXY": {"type": "MACRO", "label": "Dollar Index"},
    }

    config = GraphBuildConfig(
        correlation_windows=[30],
        min_correlation_threshold=0.1,
        min_confidence_threshold=0.5,
    )

    snapshot = build_graph(
        time_series_data=time_series_data,
        node_metadata=node_metadata,
        config=config,
    )

    # Verify snapshot structure
    assert snapshot.node_count == 3
    assert snapshot.edge_count >= 0  # May have edges depending on correlation

    # Verify nodes
    btc_node = snapshot.get_node("BTC-USD")
    assert btc_node is not None
    assert btc_node.node_type == "TECH"


def test_build_graph_empty():
    """Test graph construction with no data."""
    snapshot = build_graph(
        time_series_data={},
        config=GraphBuildConfig(),
    )

    assert snapshot.node_count == 0
    assert snapshot.edge_count == 0


def test_correlation_edge_creation():
    """Test correlation edge creation."""
    edge = create_correlation_edge(
        from_node_id="BTC-USD",
        to_node_id="ETH-USD",
        correlation=0.75,
        p_value=0.01,
        sample_size=100,
        window_days=30,
    )

    assert edge is not None
    assert edge.from_node_id == "BTC-USD"
    assert edge.to_node_id == "ETH-USD"
    assert edge.strength == 0.75
    assert edge.relationship_type == "CORRELATION"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
