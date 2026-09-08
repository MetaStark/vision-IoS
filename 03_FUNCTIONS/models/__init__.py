"""
FHQ Learning Models Package
Phase 2 Hypothesis Swarm V1.1
"""

from .phase2_hypothesis_swarm import (
    # Context Models
    ContextSnapshotV11,
    TriggerIndicators,

    # Core Models
    TriggerEventEntry,
    OutcomeLedgerEntryV11,

    # Config Models
    AlphaSatelliteTriggerV11,
    AlphaSatelliteMeasurementV11,
    ATRLoggingConfig,
    AlphaSatelliteConfigV11,

    # Pre-configured Blueprints
    TEST_A_VOLATILITY_SQUEEZE_V11,
    TEST_B_REGIME_ALIGNMENT_V11,
    TEST_C_MEAN_REVERSION_V11,

    # Utility Functions
    get_all_test_blueprints,
    get_test_blueprint_by_code,
)

__all__ = [
    "ContextSnapshotV11",
    "TriggerIndicators",
    "TriggerEventEntry",
    "OutcomeLedgerEntryV11",
    "AlphaSatelliteTriggerV11",
    "AlphaSatelliteMeasurementV11",
    "ATRLoggingConfig",
    "AlphaSatelliteConfigV11",
    "TEST_A_VOLATILITY_SQUEEZE_V11",
    "TEST_B_REGIME_ALIGNMENT_V11",
    "TEST_C_MEAN_REVERSION_V11",
    "get_all_test_blueprints",
    "get_test_blueprint_by_code",
]
