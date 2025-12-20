"""Deterministic ID generation for Meta-Perception Layer."""

import hashlib
from datetime import datetime
from typing import Any


def _generate_id(prefix: str, *components: Any) -> str:
    """
    Generate deterministic ID using MD5 hash.

    Args:
        prefix: ID prefix (e.g., "perception", "snapshot")
        *components: Components to hash together

    Returns:
        Deterministic ID string
    """
    # Combine components into string
    combined = "_".join(str(c) for c in components)

    # Generate MD5 hash
    hash_digest = hashlib.md5(combined.encode()).hexdigest()[:16]

    return f"{prefix}_{hash_digest}"


def generate_perception_id(timestamp: datetime, state_hash: str) -> str:
    """
    Generate deterministic perception state ID.

    Args:
        timestamp: State timestamp
        state_hash: Hash of state components

    Returns:
        Perception ID (e.g., "perception_a3f4b2c1d5e6f7g8")
    """
    return _generate_id("perception", timestamp.isoformat(), state_hash)


def generate_snapshot_id(timestamp: datetime) -> str:
    """
    Generate deterministic snapshot ID.

    Args:
        timestamp: Snapshot timestamp

    Returns:
        Snapshot ID (e.g., "snapshot_2025-11-19T14:30:00Z")
    """
    # Use full ISO timestamp for snapshots (more readable)
    return f"snapshot_{timestamp.isoformat()}"


def generate_decision_id(snapshot_id: str, timestamp: datetime) -> str:
    """
    Generate deterministic decision ID.

    Args:
        snapshot_id: Associated snapshot ID
        timestamp: Decision timestamp

    Returns:
        Decision ID
    """
    return _generate_id("decision", snapshot_id, timestamp.isoformat())


def generate_shock_id(shock_type: str, timestamp: datetime, feature: str = "") -> str:
    """
    Generate deterministic shock ID.

    Args:
        shock_type: Type of shock
        timestamp: Shock timestamp
        feature: Affected feature (optional)

    Returns:
        Shock ID
    """
    components = [shock_type.lower(), timestamp.isoformat()]
    if feature:
        components.append(feature)
    return _generate_id("shock", *components)


def generate_override_id(timestamp: datetime, trigger_reason: str) -> str:
    """
    Generate deterministic override ID.

    Args:
        timestamp: Override timestamp
        trigger_reason: Reason for override

    Returns:
        Override ID
    """
    return _generate_id("override", timestamp.isoformat(), trigger_reason)


def generate_diagnostic_id(module: str, computation: str, timestamp: datetime) -> str:
    """
    Generate deterministic diagnostic log ID.

    Args:
        module: Module name
        computation: Computation name
        timestamp: Log timestamp

    Returns:
        Diagnostic log ID
    """
    return _generate_id("diag", module, computation, timestamp.isoformat())


def generate_importance_id(snapshot_id: str) -> str:
    """Generate feature importance report ID."""
    return f"importance_{snapshot_id.replace('snapshot_', '')}"


def generate_scenario_id(scenario_name: str, timestamp: datetime) -> str:
    """Generate stress scenario result ID."""
    return _generate_id("scenario", scenario_name, timestamp.isoformat())
