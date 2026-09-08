"""
Pydantic Schemas for FjordHQ Cognitive Engines
CEO-DIR-2026-COGNITIVE-ENGINES-001

Constitutional: ADR-017, ADR-020, ADR-021

This module defines type-safe data models for:
- Evidence bundles and retrieval results
- Conversation memory
- Archival memory (MemGPT-style)
- Claim extraction for IKEA verification

CEO Conditions Implemented:
- [C7] EvidenceBundle Pydantic matches DB structure (rrf_fused_results as List)
- [C8] Explicit claim extraction definition (ClaimType enum)
- [P2] DB/API vector mapping documented
- [P9] snippet_id == evidence_id convention documented
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class RetrievalMode(str, Enum):
    """Retrieval mode for InForage hybrid search."""
    DENSE = "DENSE"      # Vector-only (Qdrant)
    SPARSE = "SPARSE"    # FTS-only (Postgres)
    HYBRID = "HYBRID"    # Dense + Sparse + RRF fusion


class DEFCONLevel(str, Enum):
    """
    DEFCON levels for budget gating (ADR-016).

    Budget allocation:
    - GREEN: Cached retrieval only ($0)
    - YELLOW: Dense only (cost <= $0.10)
    - ORANGE: Hybrid without reranking (cost <= $0.25)
    - RED/BLACK: Full hybrid + reranking (cost <= $0.50)
    """
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"
    BLACK = "BLACK"


class MemoryTier(str, Enum):
    """
    MemGPT-style memory hierarchy.

    - CORE: Read-only (Constitution, Risk Rules)
    - RECALL: Working memory (episodic_memory)
    - ARCHIVAL: Cold storage (archival_store)
    """
    CORE = "CORE"
    RECALL = "RECALL"
    ARCHIVAL = "ARCHIVAL"


class MemoryType(str, Enum):
    """
    Types of archival memory records.

    Per ADR-021, archival_store is append-only.
    Corrections must be stored as COUNTER_EVIDENCE, not updates.
    """
    DECISION = "DECISION"          # Agent decision record
    CORRECTION = "CORRECTION"      # Self-correction acknowledgment
    INSIGHT = "INSIGHT"            # Learned insight
    COUNTER_EVIDENCE = "COUNTER_EVIDENCE"  # Correction to previous record


class ClaimType(str, Enum):
    """
    [C8] Claim types for IKEA verification.

    Each type has specific extraction patterns:
    - NUMERIC: Numbers, percentages, prices
    - TEMPORAL: Date/time references
    - ENTITY_PREDICATE: Entity + verb predicate
    - CAUSAL: Cause-effect language
    """
    NUMERIC = "NUMERIC"
    TEMPORAL = "TEMPORAL"
    ENTITY_PREDICATE = "ENTITY_PREDICATE"
    CAUSAL = "CAUSAL"


class ConversationRole(str, Enum):
    """Message roles in conversations."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class VerificationStatus(str, Enum):
    """Evidence verification status."""
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    STALE = "STALE"
    FABRICATION = "FABRICATION"


# =============================================================================
# RETRIEVAL RESULT MODELS
# =============================================================================

class DenseResult(BaseModel):
    """
    Single result from dense (vector) search.

    Returned by Qdrant similarity search.
    """
    evidence_id: UUID
    score: float = Field(ge=0.0, le=1.0, description="Cosine similarity score")
    rank: int = Field(ge=1, description="1-indexed rank in results")


class SparseResult(BaseModel):
    """
    Single result from sparse (FTS) search.

    Returned by Postgres ts_rank_cd.
    """
    evidence_id: UUID
    score: float = Field(ge=0.0, description="FTS rank score")
    rank: int = Field(ge=1, description="1-indexed rank in results")


class FusedResult(BaseModel):
    """
    [C7] Single result from RRF fusion.

    Mirrors rrf_fused_results JSONB structure in DB.
    RRF formula: score(d) = sum(1 / (k + rank(d))) where k=60
    """
    evidence_id: UUID
    rrf_score: float = Field(ge=0.0, description="RRF fusion score")
    dense_rank: Optional[int] = Field(None, ge=1, description="Rank in dense results")
    sparse_rank: Optional[int] = Field(None, ge=1, description="Rank in sparse results")


# =============================================================================
# EVIDENCE BUNDLE
# =============================================================================

class EvidenceBundle(BaseModel):
    """
    [C7] Evidence bundle with proper structure matching DB schema.

    rrf_fused_results is a list of FusedResult, not a single score.

    [P9] CONVENTION: In FjordHQ, `snippet_id` references `evidence_nodes.evidence_id`.
    We use "snippet" terminology for IKEA grounding but the underlying ID is evidence_id.
    This is intentional - snippets are evidence nodes that ground LLM claims.
    """
    bundle_id: UUID
    query_text: str

    # [P9] snippet_ids == evidence_ids from fhq_canonical.evidence_nodes
    snippet_ids: List[UUID] = Field(default_factory=list)

    # Search results
    dense_results: Optional[List[DenseResult]] = None
    sparse_results: Optional[List[SparseResult]] = None

    # [C7] RRF fusion results - List of FusedResult, not dict
    rrf_fused_results: Optional[List[FusedResult]] = None

    # [C7] Top score for quick access
    rrf_top_score: Optional[float] = None

    # Context
    defcon_level: DEFCONLevel
    regime: Optional[str] = None

    # Cost tracking (EC-021)
    query_cost_usd: float = Field(default=0.0, le=0.50, description="Hard cap per query")

    # Hash for court-proof verification
    bundle_hash: Optional[str] = None

    @field_validator('rrf_top_score', mode='before')
    @classmethod
    def compute_top_score(cls, v, info):
        """Auto-compute top score from fused results if not provided."""
        if v is not None:
            return v
        fused = info.data.get('rrf_fused_results') if info.data else None
        if fused and len(fused) > 0:
            return max(r.rrf_score for r in fused if isinstance(r, FusedResult))
        return None


# =============================================================================
# CONVERSATION MODELS
# =============================================================================

class ConversationMessage(BaseModel):
    """
    Single message in a conversation.

    [P4] Assistant SIGNAL messages MUST have snippet_ids (enforced in app layer).
    """
    message_id: UUID
    conversation_id: UUID
    role: ConversationRole
    content: str
    tokens_used: Optional[int] = None

    # IKEA citations (required for assistant SIGNAL messages)
    snippet_ids: List[UUID] = Field(default_factory=list)

    # [C4] Link to embedding_store
    embedding_id: Optional[UUID] = None

    # Parent for threading
    parent_message_id: Optional[UUID] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    """
    Conversation session for multi-turn dialogues.
    """
    conversation_id: UUID
    agent_id: str
    session_id: Optional[UUID] = None

    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)

    regime: Optional[str] = None
    conversation_type: Optional[str] = None

    # Token management (MemGPT-style)
    token_budget: int = 8000
    tokens_used: int = 0

    archived: bool = False
    archived_at: Optional[datetime] = None

    # Messages (loaded separately for performance)
    messages: Optional[List[ConversationMessage]] = None


# =============================================================================
# ARCHIVAL MEMORY
# =============================================================================

class ArchivalMemory(BaseModel):
    """
    Archival memory record.
    Immutable after creation - corrections stored as COUNTER_EVIDENCE.

    [P2] DB/API Vector Mapping:
    - DB: pgvector `vector(1536)` type
    - API: `List[float]` for JSON serialization
    - Conversion: psycopg2 adapter handles vector<->list automatically
    """
    archive_id: UUID
    agent_id: str
    content: str
    content_hash: str  # SHA-256 hex (pgcrypto digest)
    memory_type: MemoryType
    source_conversation_id: Optional[UUID] = None
    source_message_id: Optional[UUID] = None
    regime_at_archival: Optional[str] = None

    # [P2] API=List[float], DB=vector(1536)
    embedding: Optional[List[float]] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# CLAIM EXTRACTION (IKEA)
# =============================================================================

class ExtractedClaim(BaseModel):
    """
    [C8] A claim unit extracted from LLM response.
    Must have at least one snippet_id for grounding.

    Claim types (C8 definition):
    - NUMERIC: Contains number/percent/price
    - TEMPORAL: Contains date/time reference
    - ENTITY_PREDICATE: "X increased", "Y is"
    - CAUSAL: "because", "due to", "caused by"
    """
    claim_text: str
    claim_type: ClaimType
    snippet_ids: List[UUID] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    grounded: bool = False

    # Source tracking
    source_sentence_index: Optional[int] = None


class IKEAVerificationResult(BaseModel):
    """Result of IKEA verification on an LLM response."""
    is_valid: bool
    claims: List[ExtractedClaim]
    grounded_claims_count: int
    ungrounded_claims_count: int
    grounding_ratio: float = Field(ge=0.0, le=1.0)

    # If verification failed
    violation_message: Optional[str] = None


# =============================================================================
# INFORAGE QUERY LOG
# =============================================================================

class InForageQueryLog(BaseModel):
    """
    Log entry for InForage hybrid retrieval operations.
    Used for cost tracking and audit (EC-021).
    """
    query_id: UUID
    query_text: str
    retrieval_mode: RetrievalMode

    # RRF parameters
    rrf_k: int = 60
    dense_weight: float = 0.5
    sparse_weight: float = 0.5

    # Search parameters
    top_k: int = 20
    rerank_cutoff: int = 5

    # Performance metrics
    latency_ms: Optional[int] = None
    results_count: Optional[int] = None

    # Cost tracking (EC-021)
    embedding_cost_usd: float = 0.0
    search_cost_usd: float = 0.0
    rerank_cost_usd: float = 0.0
    cost_usd: float = 0.0  # Total

    # Context
    defcon_level: DEFCONLevel
    budget_remaining_pct: Optional[float] = None
    querying_agent: Optional[str] = None

    # Link to evidence bundle
    bundle_id: Optional[UUID] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# GOLDEN ALPHA TEST SET
# =============================================================================

class ExpectedAnswerConstraints(BaseModel):
    """Constraints for expected answers in golden test set."""
    must_contain: List[str] = Field(default_factory=list)
    must_not_contain: List[str] = Field(default_factory=list)
    min_confidence: Optional[float] = None
    max_latency_ms: Optional[int] = None


class GoldenAlphaTestCase(BaseModel):
    """
    [C9] Golden Alpha test case for G2 gate validation.
    VEGA must sign before G2 approval.
    """
    testcase_id: UUID
    query_text: str
    expected_snippet_ids: List[UUID] = Field(default_factory=list)
    expected_answer_constraints: Optional[ExpectedAnswerConstraints] = None

    domain: Optional[str] = None
    difficulty: str = Field(default="MEDIUM", pattern="^(EASY|MEDIUM|HARD)$")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "SYSTEM"

    # [C9] VEGA governance
    vega_signature: Optional[str] = None
    signature_timestamp: Optional[datetime] = None

    # Test results
    last_evaluated_at: Optional[datetime] = None
    last_result: Optional[str] = None
    last_ndcg_score: Optional[float] = None


# =============================================================================
# MEMORY PAGE REQUEST (for MemoryStack)
# =============================================================================

class MemoryPageRequest(BaseModel):
    """Request for paging memory from MemoryStack."""
    query: str
    agent_id: str
    defcon_level: DEFCONLevel
    regime: str
    token_budget: int = 8000
    min_relevance: float = 0.1


class PagedMemory(BaseModel):
    """Result of memory paging operation."""
    core_tokens: int
    recall_memories: List[Dict[str, Any]]
    archival_memories: List[Dict[str, Any]]
    total_tokens_used: int
    archival_accessed: bool
