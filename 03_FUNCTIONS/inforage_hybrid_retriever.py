"""
InForage Hybrid Retriever for FjordHQ Cognitive Engines
CEO-DIR-2026-COGNITIVE-ENGINES-001

Constitutional: ADR-017, ADR-020, ADR-021
EC Compliance: EC-021 (InForage cost management)

This module implements hybrid retrieval combining:
1. Dense (vector) search via Qdrant
2. Sparse (FTS) search via Postgres postgres_fts_search()
3. Reciprocal Rank Fusion (RRF) to combine results

[P6] Explicit query embedding generation before Qdrant search.
Without this, queries would not be converted to vectors.

Budget Gating (EC-021):
- DEFCON GREEN: Cached retrieval only (cost = $0)
- DEFCON YELLOW: Dense only (cost <= $0.10)
- DEFCON ORANGE: Hybrid without reranking (cost <= $0.25)
- DEFCON RED/BLACK: Full hybrid + reranking (cost <= $0.50)
"""

import uuid
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from embedding_generator import EmbeddingGenerator, EmbeddingError
from schemas.cognitive_engines import (
    EvidenceBundle,
    DenseResult,
    SparseResult,
    FusedResult,
    DEFCONLevel,
    RetrievalMode,
    InForageQueryLog
)

logger = logging.getLogger(__name__)


# =============================================================================
# RRF FUSION
# =============================================================================

def reciprocal_rank_fusion(
    dense_results: List[DenseResult],
    sparse_results: List[SparseResult],
    k: int = 60,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5
) -> List[FusedResult]:
    """
    Reciprocal Rank Fusion algorithm.

    RRF(d) = sum(weight / (k + rank(d)))

    Reference: Cormack et al., SIGIR 2009
    "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods"

    Args:
        dense_results: Results from vector search.
        sparse_results: Results from FTS search.
        k: RRF constant (default 60, per original paper).
        dense_weight: Weight for dense results.
        sparse_weight: Weight for sparse results.

    Returns:
        Fused results sorted by RRF score.
    """
    scores: Dict[uuid.UUID, Dict[str, Any]] = {}

    # Add dense results
    for result in dense_results:
        evidence_id = result.evidence_id
        if evidence_id not in scores:
            scores[evidence_id] = {
                'rrf_score': 0.0,
                'dense_rank': None,
                'sparse_rank': None
            }
        scores[evidence_id]['rrf_score'] += dense_weight / (k + result.rank)
        scores[evidence_id]['dense_rank'] = result.rank

    # Add sparse results
    for result in sparse_results:
        evidence_id = result.evidence_id
        if evidence_id not in scores:
            scores[evidence_id] = {
                'rrf_score': 0.0,
                'dense_rank': None,
                'sparse_rank': None
            }
        scores[evidence_id]['rrf_score'] += sparse_weight / (k + result.rank)
        scores[evidence_id]['sparse_rank'] = result.rank

    # Convert to FusedResult and sort
    fused = []
    for evidence_id, data in scores.items():
        fused.append(FusedResult(
            evidence_id=evidence_id,
            rrf_score=data['rrf_score'],
            dense_rank=data['dense_rank'],
            sparse_rank=data['sparse_rank']
        ))

    # Sort by RRF score descending
    fused.sort(key=lambda x: x.rrf_score, reverse=True)

    return fused


# =============================================================================
# BUDGET GATING
# =============================================================================

@dataclass
class BudgetGate:
    """Budget limits per DEFCON level."""
    allow_dense: bool
    allow_sparse: bool
    allow_hybrid: bool
    allow_rerank: bool
    max_cost_usd: float


BUDGET_GATES: Dict[DEFCONLevel, BudgetGate] = {
    DEFCONLevel.GREEN: BudgetGate(
        allow_dense=False,  # Cache only
        allow_sparse=False,
        allow_hybrid=False,
        allow_rerank=False,
        max_cost_usd=0.0
    ),
    DEFCONLevel.YELLOW: BudgetGate(
        allow_dense=True,
        allow_sparse=False,
        allow_hybrid=False,
        allow_rerank=False,
        max_cost_usd=0.10
    ),
    DEFCONLevel.ORANGE: BudgetGate(
        allow_dense=True,
        allow_sparse=True,
        allow_hybrid=True,
        allow_rerank=False,
        max_cost_usd=0.25
    ),
    DEFCONLevel.RED: BudgetGate(
        allow_dense=True,
        allow_sparse=True,
        allow_hybrid=True,
        allow_rerank=True,
        max_cost_usd=0.50
    ),
    DEFCONLevel.BLACK: BudgetGate(
        allow_dense=True,
        allow_sparse=True,
        allow_hybrid=True,
        allow_rerank=True,
        max_cost_usd=0.50
    )
}


# =============================================================================
# INFORAGE HYBRID RETRIEVER
# =============================================================================

class InForageHybridRetriever:
    """
    [P6] Hybrid retrieval with explicit query embedding generation.

    Combines:
    1. Dense search (Qdrant) - semantic similarity
    2. Sparse search (Postgres FTS) - keyword matching
    3. RRF fusion - combines rankings

    Budget-gated per DEFCON level (EC-021).

    Usage:
        retriever = InForageHybridRetriever(qdrant_client, db_conn, embedder)
        bundle = retriever.retrieve(
            query_text="What is BTC price forecast?",
            defcon_level=DEFCONLevel.ORANGE,
            top_k=20,
            rerank_cutoff=5
        )
    """

    # Cost constants (as of 2025)
    EMBEDDING_COST_PER_QUERY = 0.0001  # ~$0.0001 per embedding
    SEARCH_COST_BASE = 0.001  # Base compute cost
    RERANK_COST_PER_DOC = 0.0002  # ~$0.0002 per document reranked

    def __init__(
        self,
        qdrant_client: Any,
        db_conn: Any,
        embedding_generator: EmbeddingGenerator,
        rrf_k: int = 60,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5
    ):
        """
        Initialize the hybrid retriever.

        Args:
            qdrant_client: QdrantGraphRAGClient instance.
            db_conn: Database connection.
            embedding_generator: EmbeddingGenerator instance.
            rrf_k: RRF constant (default 60).
            dense_weight: Weight for dense results in RRF.
            sparse_weight: Weight for sparse results in RRF.
        """
        self.qdrant = qdrant_client
        self.db = db_conn
        self.embedder = embedding_generator
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

    def retrieve(
        self,
        query_text: str,
        defcon_level: DEFCONLevel,
        top_k: int = 20,
        rerank_cutoff: int = 5,
        domain_filter: Optional[str] = None,
        regime_filter: Optional[str] = None,
        score_threshold: float = 0.0
    ) -> EvidenceBundle:
        """
        [P6] Full hybrid retrieval with explicit query embedding.

        Args:
            query_text: Search query.
            defcon_level: DEFCON level for budget gating.
            top_k: Number of results per search method.
            rerank_cutoff: Number of top results to rerank.
            domain_filter: Optional domain filter (FINANCE, MACRO, CRYPTO, REGULATORY).
            regime_filter: Optional regime filter.
            score_threshold: Minimum score threshold.

        Returns:
            EvidenceBundle with fused results.
        """
        start_time = time.time()
        bundle_id = uuid.uuid4()

        # Get budget gate
        gate = BUDGET_GATES[defcon_level]

        # Track costs
        embedding_cost = 0.0
        search_cost = 0.0
        rerank_cost = 0.0

        # Initialize results
        dense_results: List[DenseResult] = []
        sparse_results: List[SparseResult] = []
        fused_results: List[FusedResult] = []

        # Determine retrieval mode based on DEFCON
        if not gate.allow_dense and not gate.allow_sparse:
            # DEFCON GREEN: No retrieval, return empty bundle
            retrieval_mode = RetrievalMode.DENSE  # Nominal
        elif gate.allow_hybrid:
            retrieval_mode = RetrievalMode.HYBRID
        elif gate.allow_dense:
            retrieval_mode = RetrievalMode.DENSE
        else:
            retrieval_mode = RetrievalMode.SPARSE

        # [P6] STEP 1: Generate query embedding (THIS WAS MISSING)
        query_embedding = None
        if gate.allow_dense:
            try:
                query_embedding = self.embedder.generate_query_embedding(query_text)
                embedding_cost = self.EMBEDDING_COST_PER_QUERY
            except EmbeddingError as e:
                logger.error(f"Query embedding generation failed: {e}")
                # Fall back to sparse-only
                retrieval_mode = RetrievalMode.SPARSE
                query_embedding = None

        # STEP 2: Dense search via Qdrant
        if query_embedding and gate.allow_dense:
            try:
                raw_dense = self.qdrant.search_similar(
                    embedding=query_embedding,
                    collection='evidence_nodes',
                    top_k=top_k,
                    domain_filter=domain_filter,
                    score_threshold=score_threshold
                )
                # [FIX] Qdrant payload has entity_id, not evidence_id
                # Use qdrant_point_id to look up evidence_id in Postgres
                dense_results = []

                # Collect qdrant_point_ids for batch lookup
                qdrant_point_ids = [r.get('qdrant_point_id') for r in raw_dense if r.get('qdrant_point_id')]

                if qdrant_point_ids:
                    # Batch lookup evidence_ids via qdrant_point_id
                    cursor = self.db.cursor()
                    try:
                        placeholders = ','.join(['%s'] * len(qdrant_point_ids))
                        cursor.execute(f'''
                            SELECT evidence_id, qdrant_point_id
                            FROM fhq_canonical.evidence_nodes
                            WHERE qdrant_point_id IN ({placeholders})
                        ''', qdrant_point_ids)
                        point_to_evidence = {str(row[1]): row[0] for row in cursor.fetchall()}
                    finally:
                        cursor.close()

                    for i, r in enumerate(raw_dense):
                        point_id = r.get('qdrant_point_id')
                        if point_id and point_id in point_to_evidence:
                            dense_results.append(DenseResult(
                                evidence_id=point_to_evidence[point_id],
                                score=r.get('score', 0.0),
                                rank=i + 1
                            ))

                search_cost += self.SEARCH_COST_BASE
                logger.info(f"Dense search returned {len(raw_dense)} Qdrant results, {len(dense_results)} mapped to evidence")
            except Exception as e:
                logger.error(f"Dense search failed: {e}")
                dense_results = []

        # STEP 3: Sparse search via Postgres FTS
        if gate.allow_sparse:
            try:
                sparse_results = self._sparse_search(
                    query_text=query_text,
                    top_k=top_k,
                    domain_filter=domain_filter
                )
                search_cost += self.SEARCH_COST_BASE * 0.5  # FTS is cheaper
            except Exception as e:
                logger.error(f"Sparse search failed: {e}")
                sparse_results = []

        # STEP 4: RRF Fusion
        if dense_results or sparse_results:
            fused_results = reciprocal_rank_fusion(
                dense_results=dense_results,
                sparse_results=sparse_results,
                k=self.rrf_k,
                dense_weight=self.dense_weight,
                sparse_weight=self.sparse_weight
            )

        # STEP 5: Rerank top-K (if DEFCON allows)
        if gate.allow_rerank and fused_results:
            fused_results, rerank_cost = self._rerank(
                fused_results[:rerank_cutoff],
                query_text
            )

        # Calculate total cost
        total_cost = embedding_cost + search_cost + rerank_cost

        # Check budget
        if total_cost > gate.max_cost_usd:
            logger.warning(
                f"Query cost {total_cost:.4f} exceeds budget {gate.max_cost_usd:.4f} "
                f"for DEFCON {defcon_level.value}"
            )

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Get top snippet IDs
        snippet_ids = [r.evidence_id for r in fused_results[:rerank_cutoff]]

        # Calculate top score
        rrf_top_score = fused_results[0].rrf_score if fused_results else None

        # Build evidence bundle FIRST (before logging)
        bundle = EvidenceBundle(
            bundle_id=bundle_id,
            query_text=query_text,
            snippet_ids=snippet_ids,
            dense_results=dense_results if dense_results else None,
            sparse_results=sparse_results if sparse_results else None,
            rrf_fused_results=fused_results if fused_results else None,
            rrf_top_score=rrf_top_score,
            defcon_level=defcon_level,
            regime=regime_filter,
            query_cost_usd=total_cost
        )

        # Store bundle to evidence_bundles table (required for FK constraint)
        try:
            self.store_evidence_bundle(bundle)
        except Exception as e:
            logger.warning(f"Failed to store evidence bundle: {e}")

        # Log query (now bundle_id exists in evidence_bundles)
        self._log_query(
            query_text=query_text,
            retrieval_mode=retrieval_mode,
            latency_ms=latency_ms,
            results_count=len(fused_results),
            embedding_cost=embedding_cost,
            search_cost=search_cost,
            rerank_cost=rerank_cost,
            total_cost=total_cost,
            defcon_level=defcon_level,
            bundle_id=bundle_id
        )

        return bundle

    def _sparse_search(
        self,
        query_text: str,
        top_k: int = 20,
        domain_filter: Optional[str] = None
    ) -> List[SparseResult]:
        """
        Execute sparse (FTS) search via Postgres.

        Uses fhq_canonical.postgres_fts_search() function.
        """
        cursor = self.db.cursor()

        try:
            # Call postgres_fts_search function
            cursor.execute("""
                SELECT evidence_id, fts_rank
                FROM fhq_canonical.postgres_fts_search(%s, %s, 'simple')
            """, [query_text, top_k])

            rows = cursor.fetchall()

            results = []
            for i, row in enumerate(rows):
                # Apply domain filter if specified
                if domain_filter:
                    cursor.execute("""
                        SELECT domain FROM fhq_canonical.evidence_nodes
                        WHERE evidence_id = %s
                    """, [str(row[0])])
                    domain_row = cursor.fetchone()
                    if domain_row and domain_row[0] != domain_filter:
                        continue

                results.append(SparseResult(
                    evidence_id=row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0])),
                    score=float(row[1]),
                    rank=len(results) + 1
                ))

            return results

        finally:
            cursor.close()

    def _rerank(
        self,
        results: List[FusedResult],
        query_text: str
    ) -> Tuple[List[FusedResult], float]:
        """
        Rerank results using cross-encoder or LLM.

        Currently a placeholder - returns results as-is.
        TODO: Integrate BGE reranker or Cohere Rerank.

        Args:
            results: Fused results to rerank.
            query_text: Original query.

        Returns:
            Tuple of (reranked results, cost).
        """
        # Placeholder: no actual reranking yet
        # Cost would be RERANK_COST_PER_DOC * len(results)
        rerank_cost = 0.0

        # TODO: Implement actual reranking
        # Options:
        # 1. BGE reranker (local, free)
        # 2. Cohere Rerank API ($0.001/search)
        # 3. LLM-based reranking (expensive)

        return results, rerank_cost

    def _log_query(
        self,
        query_text: str,
        retrieval_mode: RetrievalMode,
        latency_ms: int,
        results_count: int,
        embedding_cost: float,
        search_cost: float,
        rerank_cost: float,
        total_cost: float,
        defcon_level: DEFCONLevel,
        bundle_id: uuid.UUID
    ) -> None:
        """
        Log query to fhq_governance.inforage_query_log.
        """
        cursor = self.db.cursor()

        try:
            cursor.execute("""
                INSERT INTO fhq_governance.inforage_query_log (
                    query_id,
                    query_text,
                    retrieval_mode,
                    rrf_k,
                    dense_weight,
                    sparse_weight,
                    top_k,
                    rerank_cutoff,
                    latency_ms,
                    results_count,
                    embedding_cost_usd,
                    search_cost_usd,
                    rerank_cost_usd,
                    cost_usd,
                    defcon_level,
                    bundle_id,
                    created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, [
                str(uuid.uuid4()),
                query_text,
                retrieval_mode.value,
                self.rrf_k,
                self.dense_weight,
                self.sparse_weight,
                20,  # default top_k
                5,   # default rerank_cutoff
                latency_ms,
                results_count,
                embedding_cost,
                search_cost,
                rerank_cost,
                total_cost,
                defcon_level.value if hasattr(defcon_level, 'value') else str(defcon_level),
                str(bundle_id),
                datetime.utcnow()
            ])

            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to log query: {e}")
            self.db.rollback()

        finally:
            cursor.close()

    def get_evidence_texts(
        self,
        evidence_ids: List[uuid.UUID]
    ) -> Dict[str, str]:
        """
        Retrieve evidence texts for IKEA verification.

        Args:
            evidence_ids: List of evidence node IDs.

        Returns:
            Dict mapping evidence_id (str) to content text.
        """
        if not evidence_ids:
            return {}

        cursor = self.db.cursor()

        try:
            placeholders = ','.join(['%s'] * len(evidence_ids))
            cursor.execute(f"""
                SELECT evidence_id, content
                FROM fhq_canonical.evidence_nodes
                WHERE evidence_id IN ({placeholders})
            """, [str(eid) for eid in evidence_ids])

            rows = cursor.fetchall()
            return {str(row[0]): row[1] for row in rows}

        finally:
            cursor.close()

    def store_evidence_bundle(
        self,
        bundle: EvidenceBundle
    ) -> uuid.UUID:
        """
        Store evidence bundle to database.

        Args:
            bundle: EvidenceBundle to store.

        Returns:
            bundle_id of stored bundle.
        """
        cursor = self.db.cursor()

        try:
            # Convert results to JSON-serializable format
            dense_json = None
            sparse_json = None
            fused_json = None

            if bundle.dense_results:
                dense_json = [
                    {'evidence_id': str(r.evidence_id), 'score': r.score, 'rank': r.rank}
                    for r in bundle.dense_results
                ]

            if bundle.sparse_results:
                sparse_json = [
                    {'evidence_id': str(r.evidence_id), 'score': r.score, 'rank': r.rank}
                    for r in bundle.sparse_results
                ]

            if bundle.rrf_fused_results:
                fused_json = [
                    {
                        'evidence_id': str(r.evidence_id),
                        'rrf_score': r.rrf_score,
                        'dense_rank': r.dense_rank,
                        'sparse_rank': r.sparse_rank
                    }
                    for r in bundle.rrf_fused_results
                ]

            import json

            # Convert snippet_ids to proper format for uuid[] column
            snippet_ids_str = [str(sid) for sid in bundle.snippet_ids] if bundle.snippet_ids else []

            # Handle DEFCONLevel enum or string
            defcon_str = bundle.defcon_level.value if hasattr(bundle.defcon_level, 'value') else str(bundle.defcon_level)

            cursor.execute("""
                INSERT INTO fhq_canonical.evidence_bundles (
                    bundle_id,
                    query_text,
                    dense_results,
                    sparse_results,
                    rrf_fused_results,
                    rrf_top_score,
                    snippet_ids,
                    defcon_level,
                    regime,
                    query_cost_usd,
                    created_at
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s
                )
            """, [
                str(bundle.bundle_id),
                bundle.query_text,
                json.dumps(dense_json) if dense_json else None,
                json.dumps(sparse_json) if sparse_json else None,
                json.dumps(fused_json) if fused_json else None,
                bundle.rrf_top_score,
                snippet_ids_str,
                defcon_str,
                bundle.regime,
                bundle.query_cost_usd,
                datetime.utcnow()
            ])

            self.db.commit()
            return bundle.bundle_id

        finally:
            cursor.close()
