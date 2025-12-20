"""Base models and utilities for Meta-Perception Layer."""

from pydantic import BaseModel, ConfigDict
from typing import TypeVar

# Frozen model decorator
def frozen(cls):
    """Decorator to make Pydantic models frozen (immutable)."""
    cls.model_config = ConfigDict(frozen=True)
    return cls


# Generic type for model classes
T = TypeVar('T', bound=BaseModel)
