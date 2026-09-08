"""
Message Embedding Writer for FjordHQ Cognitive Engines
CEO-DIR-2026-COGNITIVE-ENGINES-001

Constitutional: ADR-017, ADR-020, ADR-021

[C4] Pipeline to populate embedding_id when messages are stored.
Ensures conversation_messages.embedding_id is populated for semantic search.
Without this, conversation memory becomes "stateless by accident".

Patches Applied:
- [P3] source_id = message_id ALWAYS (via source_reference column)
- [P4] App-level snippet_ids guard for SIGNAL messages
"""

import uuid
import logging
from typing import List, Optional, Any
from datetime import datetime

from embedding_generator import EmbeddingGenerator, EmbeddingError

logger = logging.getLogger(__name__)


class SnippetRequirementError(Exception):
    """
    [P4] Raised when assistant SIGNAL message lacks snippet_ids.

    This is an IKEA violation - ungrounded Alpha claims cannot be stored.
    The system must return NO_SIGNAL when this occurs.
    """
    pass


class MessageEmbeddingWriter:
    """
    Writes message embeddings to fhq_memory.embedding_store
    and links them to conversation_messages.

    [P4] App-level enforcement: When role='assistant' and content indicates
    a SIGNAL (Alpha output), snippet_ids MUST be non-empty, else raise error.

    Usage:
        writer = MessageEmbeddingWriter(db_conn, embedding_generator)
        message_id = writer.write_message_with_embedding(
            conversation_id=conv_id,
            role='assistant',
            content='Based on evidence, BUY BTC at $42,000',
            tokens_used=150,
            snippet_ids=[evidence_id_1, evidence_id_2],
            agent_id='FINN'
        )
    """

    # Signal indicators in assistant content
    SIGNAL_INDICATORS = [
        'BUY', 'SELL', 'HOLD', 'LONG', 'SHORT',
        'BULLISH', 'BEARISH', 'STRONG BUY', 'STRONG SELL',
        'ACCUMULATE', 'REDUCE', 'NO_SIGNAL'
    ]

    def __init__(
        self,
        db_conn: Any,
        embedding_generator: EmbeddingGenerator,
        agent_id: str = 'SYSTEM'
    ):
        """
        Initialize the message embedding writer.

        Args:
            db_conn: Database connection with execute() and commit() methods.
            embedding_generator: EmbeddingGenerator instance.
            agent_id: Default agent ID for embeddings.
        """
        self.db = db_conn
        self.embedder = embedding_generator
        self.agent_id = agent_id

    def _is_signal_message(self, content: str) -> bool:
        """
        Check if message contains Alpha signal output.

        Args:
            content: Message content text.

        Returns:
            True if content appears to contain trading signals.
        """
        content_upper = content.upper()
        return any(indicator in content_upper for indicator in self.SIGNAL_INDICATORS)

    def _enforce_snippet_requirement(
        self,
        role: str,
        content: str,
        snippet_ids: Optional[List[uuid.UUID]]
    ) -> None:
        """
        [P4] App-level guard for IKEA compliance.

        Assistant messages with signals MUST have snippet_ids.
        This prevents storing ungrounded Alpha claims.

        Args:
            role: Message role ('user', 'assistant', 'system').
            content: Message content.
            snippet_ids: List of evidence IDs (can be None or empty).

        Raises:
            SnippetRequirementError: If validation fails.
        """
        if role == 'assistant' and self._is_signal_message(content):
            if not snippet_ids or len(snippet_ids) == 0:
                raise SnippetRequirementError(
                    "[P4] IKEA Violation: Assistant SIGNAL message requires snippet_ids. "
                    "Cannot store ungrounded Alpha claims. System will return NO_SIGNAL."
                )

    def write_message_with_embedding(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        tokens_used: int,
        snippet_ids: Optional[List[uuid.UUID]] = None,
        agent_id: Optional[str] = None,
        parent_message_id: Optional[uuid.UUID] = None,
        regime: Optional[str] = None
    ) -> uuid.UUID:
        """
        Write a message and its embedding atomically.

        [P3] source_reference = message_id ALWAYS for consistency.
        [P4] Enforces snippet_ids requirement for assistant SIGNAL messages.

        Args:
            conversation_id: Parent conversation UUID.
            role: Message role ('user', 'assistant', 'system').
            content: Message content text.
            tokens_used: Token count for this message.
            snippet_ids: List of evidence_ids for IKEA grounding.
            agent_id: Agent creating this message (uses default if not provided).
            parent_message_id: For threaded conversations.
            regime: Current market regime for embedding context.

        Returns:
            UUID of the created message.

        Raises:
            SnippetRequirementError: If SIGNAL message lacks snippet_ids.
            EmbeddingError: If embedding generation fails.
        """
        # [P4] Enforce snippet requirement before any DB writes
        self._enforce_snippet_requirement(role, content, snippet_ids)

        # Resolve agent
        agent = agent_id or self.agent_id

        # 1. Generate message_id first (needed for source_reference consistency)
        message_id = uuid.uuid4()

        # 2. Generate embedding
        try:
            embedding = self.embedder.generate_query_embedding(content)
        except EmbeddingError as e:
            logger.error(f"Embedding generation failed for message {message_id}: {e}")
            raise

        # 3. Compute content hash for deduplication
        content_hash = self.embedder.compute_content_hash(content)

        # 4. Store embedding in embedding_store
        # [P3] source_reference = message_id (NOT conversation_id)
        # Maps to existing schema: content_type, source_agent, source_reference
        embedding_id = uuid.uuid4()
        cursor = self.db.cursor()

        cursor.execute("""
            INSERT INTO fhq_memory.embedding_store (
                embedding_id,
                content_hash,
                content_type,
                source_agent,
                source_reference,
                embedding,
                content_text,
                regime,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, [
            str(embedding_id),
            content_hash,
            'CONVERSATION_MESSAGE',  # content_type
            agent,                   # source_agent
            str(message_id),         # [P3] source_reference = message_id
            embedding,               # pgvector handles list->vector conversion
            content[:500] if content else None,  # content_text (truncated for summary)
            regime or 'UNKNOWN',
            datetime.utcnow()
        ])

        # 5. Store message with embedding_id link
        snippet_ids_array = [str(sid) for sid in snippet_ids] if snippet_ids else []

        cursor.execute("""
            INSERT INTO fhq_memory.conversation_messages (
                message_id,
                conversation_id,
                role,
                content,
                tokens_used,
                snippet_ids,
                embedding_id,
                parent_message_id,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, [
            str(message_id),
            str(conversation_id),
            role,
            content,
            tokens_used,
            snippet_ids_array,
            str(embedding_id),
            str(parent_message_id) if parent_message_id else None,
            datetime.utcnow()
        ])

        # 6. Update conversation last_activity
        cursor.execute("""
            UPDATE fhq_memory.conversations
            SET last_activity_at = %s,
                tokens_used = tokens_used + %s
            WHERE conversation_id = %s
        """, [datetime.utcnow(), tokens_used, str(conversation_id)])

        self.db.commit()
        cursor.close()

        logger.info(f"Created message {message_id} with embedding {embedding_id}")
        return message_id

    def create_conversation(
        self,
        agent_id: str,
        conversation_type: Optional[str] = None,
        regime: Optional[str] = None,
        token_budget: int = 8000,
        session_id: Optional[uuid.UUID] = None
    ) -> uuid.UUID:
        """
        Create a new conversation session.

        Args:
            agent_id: Agent owning this conversation.
            conversation_type: Type of conversation ('ALPHA_RESEARCH', etc.).
            regime: Current market regime.
            token_budget: Token budget for this conversation.
            session_id: Optional session identifier.

        Returns:
            UUID of the created conversation.
        """
        conversation_id = uuid.uuid4()
        cursor = self.db.cursor()

        cursor.execute("""
            INSERT INTO fhq_memory.conversations (
                conversation_id,
                agent_id,
                session_id,
                started_at,
                last_activity_at,
                regime,
                conversation_type,
                token_budget,
                tokens_used,
                archived
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 0, FALSE
            )
        """, [
            str(conversation_id),
            agent_id,
            str(session_id) if session_id else None,
            datetime.utcnow(),
            datetime.utcnow(),
            regime,
            conversation_type,
            token_budget
        ])

        self.db.commit()
        cursor.close()

        logger.info(f"Created conversation {conversation_id} for agent {agent_id}")
        return conversation_id

    def backfill_missing_embeddings(
        self,
        batch_size: int = 100,
        agent_id: Optional[str] = None
    ) -> int:
        """
        Backfill embeddings for messages that have NULL embedding_id.

        Run as a scheduled job to ensure all messages are searchable.

        Args:
            batch_size: Number of messages to process per batch.
            agent_id: Optional agent filter.

        Returns:
            Number of messages processed.
        """
        cursor = self.db.cursor()

        # Find messages without embeddings
        query = """
            SELECT m.message_id, m.content, m.conversation_id, c.regime, c.agent_id
            FROM fhq_memory.conversation_messages m
            JOIN fhq_memory.conversations c ON m.conversation_id = c.conversation_id
            WHERE m.embedding_id IS NULL
            LIMIT %s
        """
        cursor.execute(query, [batch_size])
        messages = cursor.fetchall()

        processed = 0
        for msg_id, content, conv_id, regime, agent in messages:
            try:
                # Generate embedding
                embedding = self.embedder.generate_query_embedding(content)
                content_hash = self.embedder.compute_content_hash(content)
                embedding_id = uuid.uuid4()

                # Store embedding
                # [P3] source_reference = message_id
                cursor.execute("""
                    INSERT INTO fhq_memory.embedding_store (
                        embedding_id,
                        content_hash,
                        content_type,
                        source_agent,
                        source_reference,
                        embedding,
                        content_text,
                        regime,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, [
                    str(embedding_id),
                    content_hash,
                    'CONVERSATION_MESSAGE',
                    agent,
                    str(msg_id),  # [P3] Always message_id
                    embedding,
                    content[:500] if content else None,
                    regime or 'UNKNOWN',
                    datetime.utcnow()
                ])

                # Link to message
                cursor.execute("""
                    UPDATE fhq_memory.conversation_messages
                    SET embedding_id = %s
                    WHERE message_id = %s
                """, [str(embedding_id), str(msg_id)])

                processed += 1

            except EmbeddingError as e:
                logger.error(f"Failed to backfill embedding for message {msg_id}: {e}")
                continue

        self.db.commit()
        cursor.close()

        logger.info(f"Backfilled {processed} message embeddings")
        return processed

    def archive_conversation(
        self,
        conversation_id: uuid.UUID
    ) -> bool:
        """
        Archive a conversation (marks as archived, does not delete).

        Args:
            conversation_id: Conversation to archive.

        Returns:
            True if successful.
        """
        cursor = self.db.cursor()

        cursor.execute("""
            UPDATE fhq_memory.conversations
            SET archived = TRUE,
                archived_at = %s
            WHERE conversation_id = %s
              AND archived = FALSE
        """, [datetime.utcnow(), str(conversation_id)])

        affected = cursor.rowcount
        self.db.commit()
        cursor.close()

        if affected > 0:
            logger.info(f"Archived conversation {conversation_id}")
            return True
        else:
            logger.warning(f"Conversation {conversation_id} not found or already archived")
            return False

    def get_conversation_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int = 50
    ) -> List[dict]:
        """
        Retrieve messages from a conversation.

        Args:
            conversation_id: Conversation to retrieve from.
            limit: Maximum messages to return.

        Returns:
            List of message dictionaries.
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT
                message_id,
                role,
                content,
                tokens_used,
                snippet_ids,
                embedding_id,
                created_at
            FROM fhq_memory.conversation_messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC
            LIMIT %s
        """, [str(conversation_id), limit])

        rows = cursor.fetchall()
        cursor.close()

        messages = []
        for row in rows:
            messages.append({
                'message_id': row[0],
                'role': row[1],
                'content': row[2],
                'tokens_used': row[3],
                'snippet_ids': row[4] or [],
                'embedding_id': row[5],
                'created_at': row[6]
            })

        return messages
