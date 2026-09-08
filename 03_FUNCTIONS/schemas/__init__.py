# FjordHQ Vision-IoS Schemas
# CEO-DIR-2026-COGNITIVE-ENGINES-001
"""
Pydantic schemas for FjordHQ cognitive engines.

This module provides type-safe data models for:
- Evidence bundles (IKEA compliance)
- Conversation memory
- Archival memory (MemGPT-style)
- Claim extraction (IKEA verification)
"""

from .cognitive_engines import (
    # Enums
    RetrievalMode,
    DEFCONLevel,
    MemoryTier,
    MemoryType,
    ClaimType,
    ConversationRole,
    # Result models
    DenseResult,
    SparseResult,
    FusedResult,
    # Core models
    EvidenceBundle,
    ConversationMessage,
    Conversation,
    ArchivalMemory,
    ExtractedClaim,
    # Query models
    InForageQueryLog,
    GoldenAlphaTestCase,
)

# CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001
# Note: DEFCONLevel imported from cognitive_engines, not signal_envelope (avoids duplication)
from .signal_envelope import (
    SignalEnvelope,
    NoSignal,
    Claim,
    GroundingResult,
    ValidationResult,
    SignalAction,
    ClaimType,  # Re-export for convenience
    CognitiveResult,
    IKEARefusal,
    validate_envelope_for_execution,
    validate_ikea_input,
)

__all__ = [
    # Existing cognitive engines
    'RetrievalMode',
    'DEFCONLevel',
    'MemoryTier',
    'MemoryType',
    'ClaimType',
    'ConversationRole',
    'DenseResult',
    'SparseResult',
    'FusedResult',
    'EvidenceBundle',
    'ConversationMessage',
    'Conversation',
    'ArchivalMemory',
    'ExtractedClaim',
    'InForageQueryLog',
    'GoldenAlphaTestCase',
    # Signal Envelope (CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001)
    'SignalEnvelope',
    'NoSignal',
    'Claim',
    'GroundingResult',
    'ValidationResult',
    'SignalAction',
    'CognitiveResult',
    'IKEARefusal',
    'validate_envelope_for_execution',
    'validate_ikea_input',
    # Note: ClaimType is exported from both cognitive_engines (original) and signal_envelope
    # DEFCONLevel only from cognitive_engines to avoid duplication
]
