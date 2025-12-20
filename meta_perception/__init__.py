"""
FjordHQ Meta-Perception Layer v1.0

The perception brain of FjordHQ - determines WHAT information matters, WHEN it matters,
WHY it changes, and HOW this affects alpha generation capability.

This is a higher-order inference engine that:
- Interprets the market's informational structure
- Detects intent and pressure from other market participants
- Identifies information shocks before price reacts
- Quantifies uncertainty, entropy, and noise
- Evaluates when all signals should be ignored
- Detects nonlinear regime pivots BEFORE they manifest
- Acts as a guardrail for all downstream modules

Author: FjordHQ Team
Version: 1.0.0
License: Proprietary
"""

__version__ = "1.0.0"
__author__ = "FjordHQ Team"

# Core exports
from meta_perception.orchestration.step import step
from meta_perception.models.perception_state import PerceptionState, PerceptionSnapshot
from meta_perception.models.decision_models import MetaPerceptionDecision
from meta_perception.models.config_models import PerceptionConfig

# Adapter exports
from meta_perception.adapters.stig_api import STIGAdapterAPI

__all__ = [
    "__version__",
    "__author__",
    "step",
    "PerceptionState",
    "PerceptionSnapshot",
    "MetaPerceptionDecision",
    "PerceptionConfig",
    "STIGAdapterAPI",
]
