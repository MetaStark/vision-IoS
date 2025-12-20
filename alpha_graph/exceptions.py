"""
Alpha Graph Exceptions

Domain-specific exceptions for the Alpha Graph module.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""


class AlphaGraphException(Exception):
    """Base exception for Alpha Graph module."""
    pass


class NodeNotFoundException(AlphaGraphException):
    """Raised when a node_id is not found in the graph."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        super().__init__(f"Node not found: {node_id}")


class EdgeNotFoundException(AlphaGraphException):
    """Raised when an edge_id is not found."""

    def __init__(self, edge_id: str):
        self.edge_id = edge_id
        super().__init__(f"Edge not found: {edge_id}")


class InvalidCorrelationData(AlphaGraphException):
    """Raised when correlation computation fails (e.g., mismatched series lengths)."""

    def __init__(self, message: str):
        super().__init__(f"Invalid correlation data: {message}")


class InsufficientDataException(AlphaGraphException):
    """Raised when not enough data to compute statistics."""

    def __init__(self, required: int, actual: int):
        self.required = required
        self.actual = actual
        super().__init__(
            f"Insufficient data: required {required} points, got {actual}"
        )


class GraphValidationError(AlphaGraphException):
    """Raised when graph structure is invalid (orphaned nodes, etc.)."""

    def __init__(self, message: str):
        super().__init__(f"Graph validation error: {message}")


class SerializationError(AlphaGraphException):
    """Raised when JSON/YAML serialization fails."""

    def __init__(self, message: str, original_error: Exception = None):
        self.original_error = original_error
        super().__init__(f"Serialization error: {message}")
