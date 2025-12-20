"""
Alpha Graph Serialization

JSON/YAML serialization for Alpha Graph artefacts.

Author: FjordHQ Engineering Team
Date: 2025-11-18
"""

import json
from pathlib import Path
from typing import Union
from alpha_graph.models import (
    AlphaGraphSnapshot,
    AlphaGraphDelta,
    QueryResult,
)
from alpha_graph.exceptions import SerializationError


def save_snapshot(
    snapshot: AlphaGraphSnapshot,
    file_path: Union[str, Path],
) -> None:
    """
    Save Alpha Graph snapshot to JSON file.

    Args:
        snapshot: Snapshot to save
        file_path: Output file path

    Raises:
        SerializationError: If save fails
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict with JSON-serializable types
        data = snapshot.model_dump(mode="json")

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    except Exception as e:
        raise SerializationError(f"Failed to save snapshot: {e}", e)


def load_snapshot(
    file_path: Union[str, Path],
) -> AlphaGraphSnapshot:
    """
    Load Alpha Graph snapshot from JSON file.

    Args:
        file_path: Input file path

    Returns:
        AlphaGraphSnapshot

    Raises:
        SerializationError: If load fails
    """
    try:
        file_path = Path(file_path)

        with open(file_path, "r") as f:
            data = json.load(f)

        return AlphaGraphSnapshot(**data)

    except Exception as e:
        raise SerializationError(f"Failed to load snapshot: {e}", e)


def save_delta(
    delta: AlphaGraphDelta,
    file_path: Union[str, Path],
) -> None:
    """
    Save Alpha Graph delta to JSON file.

    Args:
        delta: Delta to save
        file_path: Output file path

    Raises:
        SerializationError: If save fails
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict
        data = delta.model_dump(mode="json")

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    except Exception as e:
        raise SerializationError(f"Failed to save delta: {e}", e)


def load_delta(
    file_path: Union[str, Path],
) -> AlphaGraphDelta:
    """
    Load Alpha Graph delta from JSON file.

    Args:
        file_path: Input file path

    Returns:
        AlphaGraphDelta

    Raises:
        SerializationError: If load fails
    """
    try:
        file_path = Path(file_path)

        with open(file_path, "r") as f:
            data = json.load(f)

        return AlphaGraphDelta(**data)

    except Exception as e:
        raise SerializationError(f"Failed to load delta: {e}", e)


def save_query_result(
    result: QueryResult,
    file_path: Union[str, Path],
) -> None:
    """
    Save query result to JSON file.

    Args:
        result: Query result to save
        file_path: Output file path

    Raises:
        SerializationError: If save fails
    """
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = result.model_dump(mode="json")

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    except Exception as e:
        raise SerializationError(f"Failed to save query result: {e}", e)


def snapshot_to_json_string(snapshot: AlphaGraphSnapshot) -> str:
    """
    Convert snapshot to JSON string.

    Args:
        snapshot: Snapshot to serialize

    Returns:
        JSON string
    """
    try:
        data = snapshot.model_dump(mode="json")
        return json.dumps(data, indent=2, default=str)
    except Exception as e:
        raise SerializationError(f"Failed to serialize snapshot: {e}", e)


def snapshot_from_json_string(json_str: str) -> AlphaGraphSnapshot:
    """
    Parse snapshot from JSON string.

    Args:
        json_str: JSON string

    Returns:
        AlphaGraphSnapshot
    """
    try:
        data = json.loads(json_str)
        return AlphaGraphSnapshot(**data)
    except Exception as e:
        raise SerializationError(f"Failed to parse snapshot: {e}", e)
