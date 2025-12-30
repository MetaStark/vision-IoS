#!/usr/bin/env python3
"""
Qdrant GraphRAG Client
CEO-DIR-2025-FINN-001 Phase 2

CRITICAL RULE: Qdrant is NOT a graph store.
It performs SIMILARITY SEARCH ONLY.
All authoritative relationships live in Postgres (fhq_graph.*).

GraphRAG Retrieval Contract:
  Step 1: Qdrant → candidate nodes (semantic proximity)
  Step 2: Postgres → relationship expansion (edges, hops, causality)
  Step 3: FINN → reasoning + synthesis

ADR Compliance: ADR-020 (ACI), ADR-016 (DEFCON), ADR-012 (Economic Safety)
EC Compliance: EC-020 (SitC), EC-021 (InForage), EC-022 (IKEA)

Author: STIG (CTO)
Date: 2025-12-30
"""

import os
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct, Filter,
        FieldCondition, MatchValue, SearchRequest
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logging.warning("[GraphRAG] qdrant-client not installed. Run: pip install qdrant-client")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GraphRAG")


@dataclass
class DEFCONConfig:
    """DEFCON behavior configuration for Qdrant operations (ADR-016)"""
    level: str = "GREEN"
    max_results: int = 20
    search_enabled: bool = True
    write_enabled: bool = True

    DEFCON_LIMITS = {
        "GREEN": {"max_results": 20, "search": True, "write": True},
        "YELLOW": {"max_results": 5, "search": True, "write": True},
        "ORANGE": {"max_results": 3, "search": True, "write": False},
        "RED": {"max_results": 0, "search": False, "write": False},
        "BLACK": {"max_results": 0, "search": False, "write": False},
    }

    def apply_level(self, level: str):
        """Apply DEFCON level constraints"""
        self.level = level.upper()
        config = self.DEFCON_LIMITS.get(self.level, self.DEFCON_LIMITS["RED"])
        self.max_results = config["max_results"]
        self.search_enabled = config["search"]
        self.write_enabled = config["write"]
        logger.info(f"[GraphRAG] DEFCON {self.level}: max_results={self.max_results}, search={self.search_enabled}, write={self.write_enabled}")


@dataclass
class EvidenceNode:
    """Structured evidence node for GraphRAG storage"""
    content: str
    content_type: str  # FACT, CLAIM, CITATION, METRIC, OBSERVATION
    source_type: str   # API, DATABASE, DOCUMENT, FINN_INFERENCE
    domain: str = "FINANCE"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    source_reference: Optional[str] = None
    data_timestamp: Optional[datetime] = None
    confidence_score: float = 1.0
    evidence_id: Optional[str] = None
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        """Convert to Qdrant payload format"""
        return {
            "evidence_id": self.evidence_id or str(uuid.uuid4()),
            "content": self.content,
            "content_type": self.content_type,
            "source_type": self.source_type,
            "domain": self.domain,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "source_reference": self.source_reference,
            "data_timestamp": self.data_timestamp.isoformat() if self.data_timestamp else None,
            "confidence_score": self.confidence_score,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **self.metadata
        }


@dataclass
class GraphRAGResult:
    """Result from GraphRAG retrieval (Step 1 + Step 2 combined)"""
    evidence_id: str
    content: str
    score: float  # Qdrant similarity score
    domain: str
    entity_type: Optional[str]
    confidence_score: float
    # Step 2: Postgres relationships
    related_evidence: List[Dict[str, Any]] = field(default_factory=list)
    causal_edges: List[Dict[str, Any]] = field(default_factory=list)


class QdrantGraphRAGClient:
    """
    GraphRAG client bridging Qdrant (similarity) and Postgres (relationships).

    CRITICAL: This client enforces the boundary separation:
    - Qdrant = ANN similarity search only
    - Postgres = authoritative relationships and causality

    Usage:
        client = QdrantGraphRAGClient()
        results = client.graphrag_retrieve(query_embedding, top_k=10, expand_hops=2)
    """

    # Collection names (must match docker-compose setup)
    COLLECTION_FINN_EMBEDDINGS = "finn_embeddings"
    COLLECTION_EVIDENCE_NODES = "evidence_nodes"
    COLLECTION_CAUSAL_CLAIMS = "causal_claims"

    # Default embedding dimension (OpenAI text-embedding-3-small)
    EMBEDDING_DIM = 1536

    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        pg_host: str = None,
        pg_port: int = None,
        pg_database: str = None,
        pg_user: str = None,
        pg_password: str = None,
        defcon_level: str = "GREEN"
    ):
        """Initialize GraphRAG client with Qdrant and Postgres connections"""

        # DEFCON configuration
        self.defcon = DEFCONConfig()
        self.defcon.apply_level(defcon_level)

        # Qdrant connection
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.qdrant: Optional[QdrantClient] = None

        if QDRANT_AVAILABLE:
            try:
                self.qdrant = QdrantClient(
                    host=qdrant_host,
                    port=qdrant_port,
                    check_compatibility=False  # Skip version check
                )
                logger.info(f"[GraphRAG] Connected to Qdrant at {qdrant_host}:{qdrant_port}")
            except Exception as e:
                logger.error(f"[GraphRAG] Failed to connect to Qdrant: {e}")

        # Postgres connection parameters
        self.pg_config = {
            "host": pg_host or os.getenv("PGHOST", "127.0.0.1"),
            "port": pg_port or int(os.getenv("PGPORT", "54322")),
            "database": pg_database or os.getenv("PGDATABASE", "postgres"),
            "user": pg_user or os.getenv("PGUSER", "postgres"),
            "password": pg_password or os.getenv("PGPASSWORD", "postgres"),
        }

    def _get_pg_connection(self):
        """Get Postgres connection"""
        return psycopg2.connect(**self.pg_config)

    # =========================================================================
    # DEFCON Control
    # =========================================================================

    def set_defcon(self, level: str):
        """Update DEFCON level (affects all operations)"""
        self.defcon.apply_level(level)

    def check_defcon_search(self) -> bool:
        """Check if search is allowed at current DEFCON"""
        if not self.defcon.search_enabled:
            logger.warning(f"[GraphRAG] Search blocked at DEFCON {self.defcon.level}")
            return False
        return True

    def check_defcon_write(self) -> bool:
        """Check if write is allowed at current DEFCON"""
        if not self.defcon.write_enabled:
            logger.warning(f"[GraphRAG] Write blocked at DEFCON {self.defcon.level}")
            return False
        return True

    # =========================================================================
    # Step 1: Qdrant Similarity Search
    # =========================================================================

    def search_similar(
        self,
        embedding: List[float],
        collection: str = None,
        top_k: int = 10,
        domain_filter: Optional[str] = None,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Step 1 of GraphRAG: Semantic similarity search via Qdrant.

        This returns candidate nodes based on vector similarity.
        Relationships are NOT queried here - that's Step 2 via Postgres.

        Args:
            embedding: Query embedding vector (1536 dim)
            collection: Qdrant collection name
            top_k: Number of results (capped by DEFCON)
            domain_filter: Filter by domain (FINANCE, CRYPTO, MACRO)
            score_threshold: Minimum similarity score

        Returns:
            List of candidate evidence nodes with similarity scores
        """
        if not self.check_defcon_search():
            return []

        if not self.qdrant:
            logger.error("[GraphRAG] Qdrant client not available")
            return []

        collection = collection or self.COLLECTION_EVIDENCE_NODES

        # Apply DEFCON limit
        effective_top_k = min(top_k, self.defcon.max_results)
        if effective_top_k == 0:
            return []

        # Build filter
        query_filter = None
        if domain_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="domain",
                        match=MatchValue(value=domain_filter)
                    )
                ]
            )

        try:
            # Use query() for newer qdrant-client versions
            results = self.qdrant.query_points(
                collection_name=collection,
                query=embedding,
                limit=effective_top_k,
                query_filter=query_filter,
                score_threshold=score_threshold
            ).points

            candidates = []
            for hit in results:
                candidates.append({
                    "qdrant_point_id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload or {}
                })

            logger.info(f"[GraphRAG] Step 1: Found {len(candidates)} candidates (DEFCON {self.defcon.level})")
            return candidates

        except Exception as e:
            logger.error(f"[GraphRAG] Qdrant search failed: {e}")
            return []

    # =========================================================================
    # Step 2: Postgres Relationship Expansion
    # =========================================================================

    def expand_relationships(
        self,
        evidence_ids: List[str],
        max_hops: int = 2,
        include_causal: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Step 2 of GraphRAG: Relationship expansion via Postgres.

        This queries fhq_canonical.evidence_relationships and fhq_graph.edges
        to expand the candidate set with related nodes and causal edges.

        Args:
            evidence_ids: List of evidence_id from Step 1
            max_hops: Maximum relationship hops (default 2)
            include_causal: Include fhq_graph.edges for causality

        Returns:
            Dict mapping evidence_id to its relationships
        """
        if not evidence_ids:
            return {}

        expansion = {eid: {"related": [], "causal": []} for eid in evidence_ids}

        conn = self._get_pg_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get evidence relationships (1-hop)
                cur.execute("""
                    SELECT
                        from_evidence_id::TEXT,
                        to_evidence_id::TEXT,
                        relationship_type,
                        strength
                    FROM fhq_canonical.evidence_relationships
                    WHERE from_evidence_id::TEXT = ANY(%s)
                       OR to_evidence_id::TEXT = ANY(%s)
                """, (evidence_ids, evidence_ids))

                for row in cur.fetchall():
                    from_id = row["from_evidence_id"]
                    to_id = row["to_evidence_id"]

                    if from_id in expansion:
                        expansion[from_id]["related"].append({
                            "evidence_id": to_id,
                            "relationship_type": row["relationship_type"],
                            "direction": "outgoing",
                            "strength": float(row["strength"]) if row["strength"] else 1.0
                        })
                    if to_id in expansion:
                        expansion[to_id]["related"].append({
                            "evidence_id": from_id,
                            "relationship_type": row["relationship_type"],
                            "direction": "incoming",
                            "strength": float(row["strength"]) if row["strength"] else 1.0
                        })

                # Get causal edges from fhq_graph if requested
                if include_causal:
                    # Find matching entity_ids in evidence_nodes
                    cur.execute("""
                        SELECT DISTINCT entity_id
                        FROM fhq_canonical.evidence_nodes
                        WHERE evidence_id::TEXT = ANY(%s)
                          AND entity_id IS NOT NULL
                    """, (evidence_ids,))

                    entity_ids = [row["entity_id"] for row in cur.fetchall()]

                    if entity_ids:
                        # Get causal edges involving these entities
                        cur.execute("""
                            SELECT
                                edge_id,
                                from_node_id,
                                to_node_id,
                                relationship_type::TEXT,
                                strength,
                                confidence,
                                hypothesis,
                                transmission_mechanism
                            FROM fhq_graph.edges
                            WHERE (from_node_id = ANY(%s) OR to_node_id = ANY(%s))
                              AND status = 'active'
                            LIMIT 50
                        """, (entity_ids, entity_ids))

                        causal_edges = [dict(row) for row in cur.fetchall()]

                        # Attach causal edges to relevant evidence nodes
                        for eid, entity_id in zip(evidence_ids, entity_ids):
                            for edge in causal_edges:
                                if edge["from_node_id"] == entity_id or edge["to_node_id"] == entity_id:
                                    if eid in expansion:
                                        expansion[eid]["causal"].append(edge)

            logger.info(f"[GraphRAG] Step 2: Expanded {len(evidence_ids)} nodes with relationships")
            return expansion

        except Exception as e:
            logger.error(f"[GraphRAG] Postgres expansion failed: {e}")
            return expansion
        finally:
            conn.close()

    # =========================================================================
    # Combined GraphRAG Retrieval
    # =========================================================================

    def graphrag_retrieve(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        domain_filter: Optional[str] = None,
        expand_hops: int = 2,
        include_causal: bool = True,
        score_threshold: float = 0.5
    ) -> List[GraphRAGResult]:
        """
        Full GraphRAG retrieval (Step 1 + Step 2).

        This is the main entry point for FINN Truth Engine retrieval.

        Contract:
          Step 1: Qdrant → candidate nodes (semantic proximity)
          Step 2: Postgres → relationship expansion (edges, hops, causality)
          Step 3: FINN → reasoning + synthesis (handled by caller)

        Args:
            query_embedding: Query embedding vector
            top_k: Number of candidates from Step 1
            domain_filter: Filter by domain
            expand_hops: Max relationship hops in Step 2
            include_causal: Include causal edges from fhq_graph
            score_threshold: Minimum similarity score

        Returns:
            List of GraphRAGResult with combined Step 1 + Step 2 data
        """
        # Step 1: Qdrant similarity search
        candidates = self.search_similar(
            embedding=query_embedding,
            top_k=top_k,
            domain_filter=domain_filter,
            score_threshold=score_threshold
        )

        if not candidates:
            return []

        # Extract evidence IDs
        evidence_ids = [
            c["payload"].get("evidence_id")
            for c in candidates
            if c["payload"].get("evidence_id")
        ]

        # Step 2: Postgres relationship expansion
        expansions = self.expand_relationships(
            evidence_ids=evidence_ids,
            max_hops=expand_hops,
            include_causal=include_causal
        )

        # Combine results
        results = []
        for candidate in candidates:
            payload = candidate["payload"]
            eid = payload.get("evidence_id")

            expansion = expansions.get(eid, {"related": [], "causal": []})

            results.append(GraphRAGResult(
                evidence_id=eid or candidate["qdrant_point_id"],
                content=payload.get("content", ""),
                score=candidate["score"],
                domain=payload.get("domain", "FINANCE"),
                entity_type=payload.get("entity_type"),
                confidence_score=payload.get("confidence_score", 1.0),
                related_evidence=expansion["related"],
                causal_edges=expansion["causal"]
            ))

        logger.info(f"[GraphRAG] Retrieved {len(results)} results with {sum(len(r.related_evidence) for r in results)} related + {sum(len(r.causal_edges) for r in results)} causal")
        return results

    # =========================================================================
    # Evidence Storage (with Postgres sync)
    # =========================================================================

    def upsert_evidence(
        self,
        evidence: EvidenceNode,
        embedding: List[float],
        collection: str = None
    ) -> Optional[str]:
        """
        Store evidence in both Qdrant and Postgres.

        CRITICAL: Postgres is authoritative. Qdrant mirrors for search.

        Args:
            evidence: EvidenceNode to store
            embedding: Embedding vector
            collection: Qdrant collection name

        Returns:
            evidence_id if successful, None otherwise
        """
        if not self.check_defcon_write():
            return None

        if not self.qdrant:
            logger.error("[GraphRAG] Qdrant client not available")
            return None

        collection = collection or self.COLLECTION_EVIDENCE_NODES
        evidence_id = evidence.evidence_id or str(uuid.uuid4())
        qdrant_point_id = str(uuid.uuid4())

        # Step 1: Insert into Postgres (authoritative)
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_canonical.evidence_nodes (
                        evidence_id, content, content_type, source_type,
                        domain, entity_type, entity_id, source_reference,
                        data_timestamp, confidence_score,
                        qdrant_collection, qdrant_point_id, embedding_model
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (evidence_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        confidence_score = EXCLUDED.confidence_score,
                        qdrant_point_id = EXCLUDED.qdrant_point_id,
                        updated_at = NOW()
                    RETURNING evidence_id::TEXT
                """, (
                    evidence_id,
                    evidence.content,
                    evidence.content_type,
                    evidence.source_type,
                    evidence.domain,
                    evidence.entity_type,
                    evidence.entity_id,
                    evidence.source_reference,
                    evidence.data_timestamp,
                    evidence.confidence_score,
                    collection,
                    qdrant_point_id,
                    "text-embedding-3-small"
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"[GraphRAG] Postgres insert failed: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

        # Step 2: Insert into Qdrant (mirror for search)
        try:
            payload = evidence.to_payload()
            payload["evidence_id"] = evidence_id

            point = PointStruct(
                id=qdrant_point_id,
                vector=embedding,
                payload=payload
            )

            self.qdrant.upsert(
                collection_name=collection,
                points=[point]
            )

            # Log sync
            self._log_qdrant_sync(
                collection=collection,
                operation="INSERT",
                source_id=evidence_id,
                qdrant_point_id=qdrant_point_id,
                status="SUCCESS"
            )

            logger.info(f"[GraphRAG] Stored evidence {evidence_id} in Postgres + Qdrant")
            return evidence_id

        except Exception as e:
            logger.error(f"[GraphRAG] Qdrant upsert failed: {e}")
            self._log_qdrant_sync(
                collection=collection,
                operation="INSERT",
                source_id=evidence_id,
                qdrant_point_id=qdrant_point_id,
                status="FAILED",
                error=str(e)
            )
            return evidence_id  # Postgres insert succeeded

    def _log_qdrant_sync(
        self,
        collection: str,
        operation: str,
        source_id: str,
        qdrant_point_id: str,
        status: str,
        error: str = None
    ):
        """Log Qdrant sync operation to Postgres"""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_operational.qdrant_sync_log (
                        collection_name, operation, source_table, source_id,
                        qdrant_point_id, status, error_message, completed_at
                    ) VALUES (
                        %s, %s, 'fhq_canonical.evidence_nodes', %s, %s, %s, %s,
                        CASE WHEN %s IN ('SUCCESS', 'FAILED') THEN NOW() ELSE NULL END
                    )
                """, (collection, operation, source_id, qdrant_point_id, status, error, status))
                conn.commit()
        except Exception as e:
            logger.warning(f"[GraphRAG] Failed to log sync: {e}")
        finally:
            conn.close()

    # =========================================================================
    # Health Check
    # =========================================================================

    def health_check(self) -> Dict[str, Any]:
        """Check health of Qdrant and Postgres connections"""
        health = {
            "qdrant": {"status": "unknown", "collections": []},
            "postgres": {"status": "unknown"},
            "defcon": self.defcon.level
        }

        # Check Qdrant
        if self.qdrant:
            try:
                collections = self.qdrant.get_collections()
                health["qdrant"]["status"] = "healthy"
                health["qdrant"]["collections"] = [c.name for c in collections.collections]
            except Exception as e:
                health["qdrant"]["status"] = f"error: {e}"
        else:
            health["qdrant"]["status"] = "not_available"

        # Check Postgres
        try:
            conn = self._get_pg_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            health["postgres"]["status"] = "healthy"
            conn.close()
        except Exception as e:
            health["postgres"]["status"] = f"error: {e}"

        return health


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GraphRAG Client CLI")
    parser.add_argument("--health", action="store_true", help="Run health check")
    parser.add_argument("--defcon", default="GREEN", help="DEFCON level")
    args = parser.parse_args()

    client = QdrantGraphRAGClient(defcon_level=args.defcon)

    if args.health:
        health = client.health_check()
        print(json.dumps(health, indent=2))
