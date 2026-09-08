"""
Memory Stack: MemGPT-Inspired Memory Hierarchy
CEO-DIR-2026-COGNITIVE-ENGINES-001

Constitutional: ADR-017, ADR-020, ADR-021

Three-tier memory hierarchy per ADR-021:
- CORE (Read-Only): Constitution, System Prompt, Risk Rules
- RECALL (Working): fhq_memory.episodic_memory
- ARCHIVAL (Cold): fhq_memory.archival_store

Patches Applied:
- [P7] Uses DB-side hashing (fhq_memory.sha256_hash) for audit consistency
"""

import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from embedding_generator import EmbeddingGenerator
from schemas.cognitive_engines import (
    MemoryTier,
    MemoryType,
    DEFCONLevel,
    ArchivalMemory
)

logger = logging.getLogger(__name__)


# =============================================================================
# MEMORY TYPES
# =============================================================================

@dataclass
class CoreMemory:
    """
    Read-only core memory: Constitution, System Prompt, Risk Rules.
    Loaded once and never modified during a session.
    """
    constitution: str
    system_prompt: str
    risk_rules: List[str]
    token_count: int


@dataclass
class RecallMemory:
    """
    Working memory from episodic_memory table.
    Subject to decay based on age and relevance.
    """
    episode_id: uuid.UUID
    episode_type: str
    description: str
    outcome: Optional[str]
    importance_score: float
    effective_relevance: float
    regime: str
    created_at: datetime
    token_count: int


@dataclass
class ArchivalMemoryItem:
    """
    Cold storage memory from archival_store table.
    Append-only, immutable after creation.
    """
    archive_id: uuid.UUID
    content: str
    memory_type: MemoryType
    source_conversation_id: Optional[uuid.UUID]
    regime_at_archival: Optional[str]
    created_at: datetime
    token_count: int
    similarity_score: float = 0.0


@dataclass
class PagedMemoryResult:
    """
    Result of memory paging operation.
    Contains memories from all tiers within token budget.
    """
    core: CoreMemory
    recall_memories: List[RecallMemory] = field(default_factory=list)
    archival_memories: List[ArchivalMemoryItem] = field(default_factory=list)
    total_tokens_used: int = 0
    token_budget: int = 8000
    archival_accessed: bool = False


# =============================================================================
# MEMORY STACK
# =============================================================================

class MemoryStack:
    """
    Three-tier memory hierarchy per ADR-021.

    CORE (Read-Only): Constitution, System Prompt, Risk Rules
      - Loaded once, never modified
      - Always included in context

    RECALL (Working): fhq_memory.episodic_memory
      - Subject to temporal decay
      - Prioritized by importance and recency

    ARCHIVAL (Cold): fhq_memory.archival_store
      - Only accessed on RED/BLACK DEFCON
      - Semantic search via embeddings
      - APPEND-ONLY (immutable)

    Usage:
        stack = MemoryStack(db_conn, embedder, agent_id='FINN')
        paged = stack.page_in(
            query="What was BTC's behavior during last crisis?",
            defcon_level=DEFCONLevel.RED,
            regime='CRISIS',
            token_budget=8000
        )
    """

    # Estimated tokens per character (rough)
    TOKENS_PER_CHAR = 0.25

    # Default token allocations
    CORE_TOKEN_BUDGET = 2000
    RECALL_TOKEN_BUDGET = 4000
    ARCHIVAL_TOKEN_BUDGET = 2000

    def __init__(
        self,
        db_conn: Any,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        agent_id: str = 'SYSTEM'
    ):
        """
        Initialize the memory stack.

        Args:
            db_conn: Database connection.
            embedding_generator: Optional embedder for archival search.
            agent_id: Agent ID for memory operations.
        """
        self.db = db_conn
        self.embedder = embedding_generator
        self.agent_id = agent_id
        self._core_memory: Optional[CoreMemory] = None

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return int(len(text) * self.TOKENS_PER_CHAR)

    def _load_core(self) -> CoreMemory:
        """
        Load core memory (constitution, system prompt, risk rules).
        Cached after first load.
        """
        if self._core_memory is not None:
            return self._core_memory

        # Load from database or config
        cursor = self.db.cursor()

        try:
            # Load system prompt from agent_memory
            cursor.execute("""
                SELECT memory_value
                FROM fhq_memory.agent_memory
                WHERE agent_id = %s
                  AND memory_type = 'context'
                  AND memory_key = 'system_prompt'
                ORDER BY created_at DESC
                LIMIT 1
            """, [self.agent_id])

            row = cursor.fetchone()
            system_prompt = row[0] if row else self._default_system_prompt()

            # Load risk rules from agent_memory
            cursor.execute("""
                SELECT memory_value
                FROM fhq_memory.agent_memory
                WHERE agent_id = %s
                  AND memory_type = 'context'
                  AND memory_key = 'risk_rules'
                ORDER BY created_at DESC
                LIMIT 1
            """, [self.agent_id])

            row = cursor.fetchone()
            if row and isinstance(row[0], dict) and 'rules' in row[0]:
                risk_rules = row[0]['rules']
            else:
                risk_rules = self._default_risk_rules()

            # Load constitution summary
            constitution = self._load_constitution_summary()

            # Calculate token count
            all_text = constitution + system_prompt + ' '.join(risk_rules)
            token_count = self._estimate_tokens(all_text)

            self._core_memory = CoreMemory(
                constitution=constitution,
                system_prompt=system_prompt,
                risk_rules=risk_rules,
                token_count=token_count
            )

            return self._core_memory

        finally:
            cursor.close()

    def _load_constitution_summary(self) -> str:
        """Load constitution summary from ADR registry."""
        cursor = self.db.cursor()

        try:
            cursor.execute("""
                SELECT adr_title, description
                FROM fhq_meta.adr_registry
                WHERE adr_status IN ('ACTIVE', 'APPROVED')
                  AND adr_type = 'CONSTITUTIONAL'
                ORDER BY adr_id
                LIMIT 10
            """)

            rows = cursor.fetchall()
            if not rows:
                return "FjordHQ Vision-IoS Constitution"

            lines = ["FjordHQ Constitution (Active ADRs):"]
            for title, desc in rows:
                lines.append(f"- {title}: {desc[:100]}")

            return "\n".join(lines)

        finally:
            cursor.close()

    def _default_system_prompt(self) -> str:
        """Default system prompt if not found in database."""
        return (
            "You are FINN, FjordHQ's Financial Investments Neural Network. "
            "Your role is to analyze market data, identify Alpha signals, and provide "
            "evidence-based investment insights. All claims must be grounded in retrieved evidence. "
            "If you cannot ground a claim, return NO_SIGNAL."
        )

    def _default_risk_rules(self) -> List[str]:
        """Default risk rules if not found in database."""
        return [
            "RULE 1: Never execute trades without G4 approval",
            "RULE 2: Maximum position size limited by ADR-012",
            "RULE 3: Circuit breaker triggers halt all operations",
            "RULE 4: All signals require IKEA grounding verification",
            "RULE 5: Cost must not exceed budget per DEFCON level"
        ]

    def page_in(
        self,
        query: str,
        defcon_level: DEFCONLevel,
        regime: str,
        token_budget: int = 8000,
        min_relevance: float = 0.1
    ) -> PagedMemoryResult:
        """
        Deterministic paging based on:
        1. Token budget
        2. Relevance decay
        3. DEFCON level

        Args:
            query: Query for semantic relevance.
            defcon_level: Current DEFCON level.
            regime: Current market regime.
            token_budget: Total token budget.
            min_relevance: Minimum relevance score.

        Returns:
            PagedMemoryResult with memories from all tiers.
        """
        # 1. Always include core memory
        core = self._load_core()
        tokens_used = core.token_count

        result = PagedMemoryResult(
            core=core,
            total_tokens_used=tokens_used,
            token_budget=token_budget
        )

        # Allocate remaining budget
        remaining_tokens = token_budget - tokens_used

        # 2. Page in recall memory (working)
        recall_budget = min(self.RECALL_TOKEN_BUDGET, remaining_tokens * 0.7)
        recall_memories = self._query_recall(
            regime=regime,
            min_relevance=min_relevance,
            token_budget=int(recall_budget)
        )
        result.recall_memories = recall_memories
        recall_tokens = sum(m.token_count for m in recall_memories)
        tokens_used += recall_tokens
        remaining_tokens -= recall_tokens

        # 3. If DEFCON allows, page in archival
        if defcon_level in [DEFCONLevel.RED, DEFCONLevel.BLACK]:
            if remaining_tokens > 500 and self.embedder:
                archival_memories = self._query_archival(
                    query=query,
                    regime=regime,
                    token_budget=int(remaining_tokens)
                )
                result.archival_memories = archival_memories
                archival_tokens = sum(m.token_count for m in archival_memories)
                tokens_used += archival_tokens
                result.archival_accessed = True

        result.total_tokens_used = tokens_used
        return result

    def _query_recall(
        self,
        regime: str,
        min_relevance: float,
        token_budget: int,
        limit: int = 20
    ) -> List[RecallMemory]:
        """
        Query recall memory (episodic_memory) with decay applied.
        Uses exponential decay: relevance = importance * exp(-decay_rate * age_hours)
        """
        cursor = self.db.cursor()

        try:
            # Inline exponential decay calculation (decay_rate = 0.01 per hour)
            # effective_relevance = importance_score * exp(-0.01 * age_hours)
            cursor.execute("""
                SELECT
                    episode_id,
                    episode_type,
                    episode_description,
                    outcome_type,
                    importance_score,
                    COALESCE(importance_score, 0.5) *
                        EXP(-0.01 * EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0)
                        as effective_relevance,
                    regime_at_start,
                    created_at
                FROM fhq_memory.episodic_memory
                WHERE (regime_at_start = %s OR regime_at_start IS NULL)
                  AND COALESCE(importance_score, 0.5) *
                      EXP(-0.01 * EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0) >= %s
                ORDER BY
                    effective_relevance DESC,
                    created_at DESC
                LIMIT %s
            """, [regime, min_relevance, limit])

            rows = cursor.fetchall()
            memories = []
            tokens_used = 0

            for row in rows:
                description = row[2] or ''
                token_count = self._estimate_tokens(description)

                if tokens_used + token_count > token_budget:
                    break

                memories.append(RecallMemory(
                    episode_id=row[0],
                    episode_type=row[1] or 'unknown',
                    description=description,
                    outcome=row[3],
                    importance_score=float(row[4] or 0.5),
                    effective_relevance=float(row[5] or 0.5),
                    regime=row[6] or regime,
                    created_at=row[7],
                    token_count=token_count
                ))
                tokens_used += token_count

            return memories

        finally:
            cursor.close()

    def _query_archival(
        self,
        query: str,
        regime: str,
        token_budget: int,
        limit: int = 10
    ) -> List[ArchivalMemoryItem]:
        """
        Query archival memory with semantic search.
        """
        if not self.embedder:
            return []

        cursor = self.db.cursor()

        try:
            # Generate query embedding
            query_embedding = self.embedder.generate_query_embedding(query)

            # Semantic search on archival_store
            cursor.execute("""
                SELECT
                    archive_id,
                    content,
                    memory_type,
                    source_conversation_id,
                    regime_at_archival,
                    created_at,
                    1 - (embedding <=> %s::vector) as similarity
                FROM fhq_memory.archival_store
                WHERE agent_id = %s
                  AND (regime_at_archival = %s OR regime_at_archival IS NULL)
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, [query_embedding, self.agent_id, regime, query_embedding, limit])

            rows = cursor.fetchall()
            memories = []
            tokens_used = 0

            for row in rows:
                content = row[1] or ''
                token_count = self._estimate_tokens(content)

                if tokens_used + token_count > token_budget:
                    break

                memories.append(ArchivalMemoryItem(
                    archive_id=row[0],
                    content=content,
                    memory_type=MemoryType(row[2]) if row[2] else MemoryType.INSIGHT,
                    source_conversation_id=row[3],
                    regime_at_archival=row[4],
                    created_at=row[5],
                    token_count=token_count,
                    similarity_score=float(row[6] or 0.0)
                ))
                tokens_used += token_count

            return memories

        except Exception as e:
            logger.error(f"Archival query failed: {e}")
            return []

        finally:
            cursor.close()

    def archive(
        self,
        content: str,
        memory_type: MemoryType,
        source_conversation_id: Optional[uuid.UUID] = None,
        source_message_id: Optional[uuid.UUID] = None,
        regime: Optional[str] = None
    ) -> uuid.UUID:
        """
        Append to archival memory.
        IMMUTABLE: No updates or deletes allowed (enforced by DB trigger).

        [P7] Uses DB canonical hashing function for audit-friendly, deterministic hash.

        Args:
            content: Content to archive.
            memory_type: Type of memory (DECISION, CORRECTION, INSIGHT, COUNTER_EVIDENCE).
            source_conversation_id: Optional source conversation.
            source_message_id: Optional source message.
            regime: Market regime at time of archival.

        Returns:
            UUID of the archived memory.
        """
        cursor = self.db.cursor()
        archive_id = uuid.uuid4()

        try:
            # Generate embedding if available
            embedding = None
            if self.embedder:
                try:
                    embedding = self.embedder.generate_query_embedding(content)
                except Exception as e:
                    logger.warning(f"Failed to generate archival embedding: {e}")

            # [P7] Use DB-side hashing for consistency and audit trail
            # This ensures the same hash function is used everywhere
            cursor.execute("""
                INSERT INTO fhq_memory.archival_store (
                    archive_id,
                    agent_id,
                    content,
                    content_hash,
                    embedding,
                    memory_type,
                    source_conversation_id,
                    source_message_id,
                    regime_at_archival,
                    created_at
                ) VALUES (
                    %s, %s, %s, fhq_memory.sha256_hash(%s), %s, %s, %s, %s, %s, %s
                )
            """, [
                str(archive_id),
                self.agent_id,
                content,
                content,  # [P7] Content passed to sha256_hash function
                embedding,
                memory_type.value,
                str(source_conversation_id) if source_conversation_id else None,
                str(source_message_id) if source_message_id else None,
                regime,
                datetime.utcnow()
            ])

            self.db.commit()
            logger.info(f"Archived memory {archive_id} of type {memory_type.value}")
            return archive_id

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to archive memory: {e}")
            raise

        finally:
            cursor.close()

    def archive_correction(
        self,
        original_archive_id: uuid.UUID,
        correction_content: str,
        source_conversation_id: Optional[uuid.UUID] = None
    ) -> uuid.UUID:
        """
        Archive a correction to a previous memory.

        Since archival_store is append-only, corrections are stored as
        new COUNTER_EVIDENCE records that reference the original.

        Args:
            original_archive_id: ID of the original memory being corrected.
            correction_content: The correction content.
            source_conversation_id: Optional source conversation.

        Returns:
            UUID of the correction record.
        """
        # Include reference to original in the content
        correction_with_ref = (
            f"[CORRECTION to archive_id={original_archive_id}]\n"
            f"{correction_content}"
        )

        return self.archive(
            content=correction_with_ref,
            memory_type=MemoryType.COUNTER_EVIDENCE,
            source_conversation_id=source_conversation_id
        )

    def get_context_for_llm(
        self,
        query: str,
        defcon_level: DEFCONLevel,
        regime: str,
        token_budget: int = 8000
    ) -> str:
        """
        Get formatted context string for LLM prompt.

        Args:
            query: Query for semantic relevance.
            defcon_level: Current DEFCON level.
            regime: Current market regime.
            token_budget: Total token budget.

        Returns:
            Formatted context string for LLM prompt.
        """
        paged = self.page_in(query, defcon_level, regime, token_budget)

        lines = []

        # Core memory
        lines.append("=== CORE MEMORY (IMMUTABLE) ===")
        lines.append(paged.core.constitution)
        lines.append("")
        lines.append("--- System Prompt ---")
        lines.append(paged.core.system_prompt)
        lines.append("")
        lines.append("--- Risk Rules ---")
        for rule in paged.core.risk_rules:
            lines.append(f"  {rule}")
        lines.append("")

        # Recall memory
        if paged.recall_memories:
            lines.append("=== RECALL MEMORY (RECENT EPISODES) ===")
            for mem in paged.recall_memories:
                lines.append(f"[{mem.episode_type}] {mem.description[:200]}")
                if mem.outcome:
                    lines.append(f"  Outcome: {mem.outcome}")
            lines.append("")

        # Archival memory
        if paged.archival_memories:
            lines.append("=== ARCHIVAL MEMORY (LONG-TERM) ===")
            for mem in paged.archival_memories:
                lines.append(f"[{mem.memory_type.value}] (similarity={mem.similarity_score:.2f})")
                lines.append(f"  {mem.content[:300]}")
            lines.append("")

        lines.append(f"[Token usage: {paged.total_tokens_used}/{paged.token_budget}]")

        return "\n".join(lines)
