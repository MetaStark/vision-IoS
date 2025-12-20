# Alpha Graph v1.0

**Multi-layer relationship graph for market intelligence**

Alpha Graph is an institutional-grade module that represents and analyzes relationships between macro factors, on-chain metrics, derivatives, technical indicators, regimes, sentiment, strategies, and portfolio performance.

## Features

- **Multi-layer graph representation**: Nodes for various market factors and edges for relationships
- **Correlation analysis**: Rolling correlations across multiple time windows
- **Lead/lag detection**: Identify predictive relationships between factors
- **Regime-aware**: Compute regime-conditional relationships
- **Query API**: High-level queries like "what drives BTC-USD in BULL regime?"
- **Influence scoring**: Rank factors by their influence on target nodes
- **Pure Python**: No database dependencies, JSON-serializable artefacts
- **Deterministic**: Reproducible graph construction

## Installation

```bash
# From project root
pip install -e .
```

## Quick Start

### Building a Graph

```python
from datetime import datetime, timedelta
from alpha_graph import build_graph
from alpha_graph.models import TimeSeriesData, GraphBuildConfig

# Create time series data
ts_btc = TimeSeriesData(
    series_id="BTC-USD",
    timestamps=[datetime.utcnow() - timedelta(days=i) for i in range(100, 0, -1)],
    values=[...],  # Your price data
)

ts_dxy = TimeSeriesData(
    series_id="DXY",
    timestamps=[...],
    values=[...],
)

# Build graph
snapshot = build_graph(
    time_series_data={"BTC-USD": ts_btc, "DXY": ts_dxy},
    node_metadata={
        "BTC-USD": {"type": "TECH", "label": "Bitcoin Price"},
        "DXY": {"type": "MACRO", "label": "US Dollar Index"},
    },
    config=GraphBuildConfig(
        correlation_windows=[30, 90, 180],
        min_correlation_threshold=0.3,
        min_confidence_threshold=0.7,
    ),
)

print(f"Nodes: {snapshot.node_count}, Edges: {snapshot.edge_count}")
```

### Querying the Graph

```python
from alpha_graph import query_top_drivers

# Find top drivers of BTC-USD
result = query_top_drivers(
    snapshot=snapshot,
    target_node_id="BTC-USD",
    regime="BULL",
    top_n=10,
    min_confidence=0.7,
)

for score in result.results[:5]:
    print(f"{score.node_id}: influence={score.influence_score:.3f}")
```

### Incremental Updates

```python
from alpha_graph import update_graph

# Update graph with new data
new_snapshot, delta = update_graph(
    current_snapshot=snapshot,
    new_time_series_data=updated_ts_data,
    new_regime="BEAR",
)

print(f"Changes: {delta.edges_added} added, {delta.edges_updated} updated")
```

### Serialization

```python
from alpha_graph import save_snapshot, load_snapshot

# Save to JSON
save_snapshot(snapshot, "alpha_graph_snapshot.json")

# Load from JSON
loaded = load_snapshot("alpha_graph_snapshot.json")
```

## Architecture

```
alpha_graph/
├── __init__.py           # Package exports
├── models.py             # Pydantic schemas
├── builder.py            # Graph construction
├── updater.py            # Incremental updates
├── causality.py          # Lead/lag analysis
├── analytics.py          # Path finding, clustering
├── queries.py            # High-level query API
├── scoring.py            # Confidence & importance
├── utils.py              # Pure utility functions
├── serialization.py      # JSON I/O
├── exceptions.py         # Domain exceptions
└── tests/                # Unit & integration tests
```

## Core Models

### AlphaNode

Represents a single factor in the graph:
- `node_id`: Unique identifier
- `node_type`: MACRO, ONCHAIN, DERIV, TECH, REGIME, SENTIMENT, STRATEGY, PORTFOLIO
- `label`: Human-readable label
- `metadata`: Additional context

### AlphaEdge

Represents a relationship between nodes:
- `edge_id`: Unique identifier
- `from_node_id`, `to_node_id`: Connected nodes
- `relationship_type`: CORRELATION, CAUSALITY, LEAD_LAG, REGIME_CONDITIONAL
- `strength`: Effect size or correlation [-1, 1]
- `confidence`: Statistical confidence [0, 1]
- `regimes`: Applicable regimes
- `lag_days`: Lag for lead/lag relationships

### AlphaGraphSnapshot

Immutable snapshot of the entire graph:
- `snapshot_id`: Unique snapshot identifier
- `timestamp`: When snapshot was created
- `regime`: Current regime context
- `nodes`: List of AlphaNode objects
- `edges`: List of AlphaEdge objects

## Integration

### With Trade Engine

```python
from alpha_graph import query_top_drivers

# Enrich trade signal with graph context
signal = trade_engine.generate_signal(...)
drivers = query_top_drivers(snapshot, target_node_id=signal["symbol"])

enriched_signal = {
    **signal,
    "top_drivers": [d.node_id for d in drivers.results[:5]],
    "regime": snapshot.regime,
}
```

### With Model Governance

```python
# Reduce confidence on edges involving drifted models
drift_alert = model_governance.check_drift(...)

if drift_alert:
    # Graph automatically adjusts confidence scores
    new_snapshot, delta = update_graph(snapshot, ...)
```

## Testing

```bash
# Run tests
pytest alpha_graph/tests/ -v

# With coverage
pytest alpha_graph/tests/ --cov=alpha_graph --cov-report=html
```

## Performance

- **Build time**: ~1-2s for 50 nodes, 100 data points each
- **Update time**: ~100-500ms for incremental updates
- **Query time**: <10ms for top drivers query
- **Memory**: ~10-50MB for typical graph (50 nodes, 1000 edges)

## Artefacts

### alpha_graph_snapshot.json

```json
{
  "snapshot_id": "snapshot_2025-11-18T12:00:00Z",
  "timestamp": "2025-11-18T12:00:00Z",
  "regime": "BULL",
  "nodes": [...],
  "edges": [...],
  "metadata": {...}
}
```

### alpha_graph_delta.json

```json
{
  "delta_id": "delta_001_002",
  "from_snapshot_id": "snapshot_001",
  "to_snapshot_id": "snapshot_002",
  "edges_added": [...],
  "edges_updated": [...],
  "metadata": {...}
}
```

## License

Proprietary - FjordHQ Engineering Team

## Version

1.0.0 (2025-11-18)
