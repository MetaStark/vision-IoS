#!/usr/bin/env python3
"""
RAG QUERY CACHE
===============
Directive: CEO-DIR-2026-120 P3.1
Classification: G4_EFFICIENCY_OPTIMIZATION
Date: 2026-01-22

Implements semantic caching for RAG queries with:
1. 15-minute TTL (configurable)
2. Cosine similarity for near-duplicate detection (threshold 0.95)
3. Cache hit metrics logging
4. Integration with QdrantGraphRAGClient

Token cost reduction target: ~50%
Cache hit rate target: >30%

Authority: CEO, STIG (Technical)
Employment Contract: EC-003
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv
import numpy as np

# Load environment
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[RAG-CACHE] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Cache configuration
DEFAULT_TTL_MINUTES = 15
SIMILARITY_THRESHOLD = 0.95  # Cosine similarity for near-duplicate detection


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    near_duplicate_hits: int = 0
    tokens_saved: int = 0
    estimated_cost_saved_usd: float = 0.0

    @property
    def hit_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return (self.cache_hits + self.near_duplicate_hits) / self.total_queries


@dataclass
class CacheEntry:
    """A cached query result."""
    cache_id: str
    query_hash: str
    query_text: str
    query_embedding: Optional[List[float]]
    result_data: Dict
    token_count: int
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0


class RAGQueryCache:
    """
    Semantic query cache for RAG operations.

    Implements:
    - Exact match caching via query hash
    - Near-duplicate detection via embedding similarity
    - DEFCON-aware TTL adjustment
    - Comprehensive metrics logging
    """

    # Cost per 1K tokens (approximate)
    COST_PER_1K_TOKENS = 0.003  # $0.003 per 1K tokens (Claude Haiku)

    def __init__(
        self,
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
        similarity_threshold: float = SIMILARITY_THRESHOLD
    ):
        self.conn = None
        self.ttl_minutes = ttl_minutes
        self.similarity_threshold = similarity_threshold
        self.metrics = CacheMetrics()
        self._embedding_cache: Dict[str, List[float]] = {}  # In-memory embedding cache

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()

    def _hash_query(self, query: str) -> str:
        """Generate hash for exact match lookup."""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _hash_embedding(self, embedding: List[float]) -> str:
        """Generate hash of embedding for logging."""
        if embedding is None:
            return "NO_EMBEDDING"
        # Hash first 10 values for quick comparison
        truncated = str(embedding[:10])
        return hashlib.md5(truncated.encode()).hexdigest()[:16]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        if a is None or b is None:
            return 0.0

        a_arr = np.array(a)
        b_arr = np.array(b)

        dot_product = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def get(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None
    ) -> Optional[Dict]:
        """
        Get cached result for query.

        Checks:
        1. Exact hash match (fastest)
        2. Near-duplicate via embedding similarity (if embedding provided)

        Returns cached result or None if miss.
        """
        self.metrics.total_queries += 1
        query_hash = self._hash_query(query)

        # Step 1: Try exact hash match
        exact_result = self._get_by_hash(query_hash)
        if exact_result is not None:
            self.metrics.cache_hits += 1
            self._log_query_event(query, query_hash, True, "EXACT_MATCH")
            logger.info(f"CACHE HIT (exact): {query[:50]}...")
            return exact_result

        # Step 2: Try near-duplicate via embedding similarity
        if query_embedding is not None:
            similar_result = self._find_similar(query_embedding)
            if similar_result is not None:
                self.metrics.near_duplicate_hits += 1
                self._log_query_event(query, query_hash, True, "NEAR_DUPLICATE")
                logger.info(f"CACHE HIT (similar): {query[:50]}...")
                return similar_result

        # Cache miss
        self.metrics.cache_misses += 1
        self._log_query_event(query, query_hash, False, "MISS")
        logger.debug(f"CACHE MISS: {query[:50]}...")
        return None

    def _get_by_hash(self, query_hash: str) -> Optional[Dict]:
        """Get cached result by exact hash match."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT result_data, token_count, cache_id
                    FROM fhq_optimization.rag_query_cache
                    WHERE query_hash = %s
                    AND expires_at > NOW()
                    LIMIT 1
                """, (query_hash,))
                row = cur.fetchone()

                if row:
                    # Update hit count
                    cur.execute("""
                        UPDATE fhq_optimization.rag_query_cache
                        SET cache_hit_count = cache_hit_count + 1,
                            last_accessed_at = NOW()
                        WHERE cache_id = %s
                    """, (row['cache_id'],))
                    self.conn.commit()

                    # Track tokens saved
                    self.metrics.tokens_saved += row['token_count']
                    self.metrics.estimated_cost_saved_usd += (
                        row['token_count'] / 1000 * self.COST_PER_1K_TOKENS
                    )

                    return row['result_data']

        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            self.conn.rollback()

        return None

    def _find_similar(self, query_embedding: List[float]) -> Optional[Dict]:
        """Find cached result with similar embedding."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get recent cache entries with embeddings
                cur.execute("""
                    SELECT cache_id, query_embedding_hash, result_data, token_count
                    FROM fhq_optimization.rag_query_cache
                    WHERE expires_at > NOW()
                    AND query_embedding_hash IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 50
                """)
                rows = cur.fetchall()

                # For each, compute similarity
                for row in rows:
                    # Check if we have embedding in memory cache
                    emb_hash = row['query_embedding_hash']
                    if emb_hash in self._embedding_cache:
                        cached_emb = self._embedding_cache[emb_hash]
                        similarity = self._cosine_similarity(query_embedding, cached_emb)

                        if similarity >= self.similarity_threshold:
                            # Found similar entry
                            cur.execute("""
                                UPDATE fhq_optimization.rag_query_cache
                                SET cache_hit_count = cache_hit_count + 1,
                                    last_accessed_at = NOW()
                                WHERE cache_id = %s
                            """, (row['cache_id'],))
                            self.conn.commit()

                            self.metrics.tokens_saved += row['token_count']
                            logger.info(f"Similar query found (similarity={similarity:.3f})")
                            return row['result_data']

        except Exception as e:
            logger.warning(f"Similar query lookup failed: {e}")
            self.conn.rollback()

        return None

    def put(
        self,
        query: str,
        result: Dict,
        token_count: int,
        query_embedding: Optional[List[float]] = None,
        ttl_minutes: Optional[int] = None
    ) -> str:
        """
        Store result in cache.

        Returns cache_id of stored entry.
        """
        query_hash = self._hash_query(query)
        embedding_hash = self._hash_embedding(query_embedding) if query_embedding else None
        ttl = ttl_minutes or self.ttl_minutes
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl)

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_optimization.rag_query_cache (
                        cache_id, query_hash, query_embedding_hash, query_text,
                        result_data, token_count, created_at, expires_at
                    ) VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, %s, NOW(), %s
                    )
                    ON CONFLICT (query_hash) DO UPDATE SET
                        result_data = EXCLUDED.result_data,
                        token_count = EXCLUDED.token_count,
                        expires_at = EXCLUDED.expires_at,
                        cache_hit_count = 0
                    RETURNING cache_id::text
                """, (
                    query_hash,
                    embedding_hash,
                    query[:500],  # Truncate for storage
                    Json(result),
                    token_count,
                    expires_at
                ))
                cache_id = cur.fetchone()[0]
                self.conn.commit()

                # Store embedding in memory for similarity lookups
                if query_embedding is not None and embedding_hash:
                    self._embedding_cache[embedding_hash] = query_embedding

                logger.debug(f"Cached result for: {query[:50]}... (TTL={ttl}min)")
                return cache_id

        except Exception as e:
            logger.error(f"Failed to cache result: {e}")
            self.conn.rollback()
            return ""

    def get_or_compute(
        self,
        query: str,
        compute_fn,
        query_embedding: Optional[List[float]] = None,
        ttl_minutes: Optional[int] = None
    ) -> Tuple[Dict, bool]:
        """
        Get cached result or compute and cache new result.

        Returns (result, was_cached).
        """
        # Try cache first
        cached = self.get(query, query_embedding)
        if cached is not None:
            return cached, True

        # Compute new result
        result, token_count = compute_fn()

        # Cache the result
        self.put(query, result, token_count, query_embedding, ttl_minutes)

        return result, False

    def _log_query_event(
        self,
        query: str,
        query_hash: str,
        cache_hit: bool,
        hit_type: str
    ):
        """Log query event for metrics analysis."""
        try:
            with self.conn.cursor() as cur:
                # Get current DEFCON level
                cur.execute("""
                    SELECT current_level FROM fhq_governance.defcon_state
                    ORDER BY state_timestamp DESC LIMIT 1
                """)
                defcon = cur.fetchone()
                defcon_level = defcon[0] if defcon else 'GREEN'

                cur.execute("""
                    INSERT INTO fhq_governance.inforage_query_log (
                        query_hash, query_text, cache_hit, result_tokens,
                        defcon_level, queried_at
                    ) VALUES (%s, %s, %s, %s, %s, NOW())
                """, (
                    query_hash,
                    query[:200],
                    cache_hit,
                    self.metrics.tokens_saved if cache_hit else 0,
                    defcon_level
                ))
                self.conn.commit()

        except Exception as e:
            logger.warning(f"Failed to log query event: {e}")
            try:
                self.conn.rollback()
            except:
                pass

    def cleanup_expired(self) -> int:
        """Remove expired cache entries."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM fhq_optimization.rag_query_cache
                    WHERE expires_at < NOW()
                    RETURNING cache_id
                """)
                deleted = cur.rowcount
                self.conn.commit()
                logger.info(f"Cleaned up {deleted} expired cache entries")
                return deleted
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            self.conn.rollback()
            return 0

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current cache metrics."""
        return {
            'total_queries': self.metrics.total_queries,
            'cache_hits': self.metrics.cache_hits,
            'near_duplicate_hits': self.metrics.near_duplicate_hits,
            'cache_misses': self.metrics.cache_misses,
            'hit_rate': round(self.metrics.hit_rate * 100, 2),
            'tokens_saved': self.metrics.tokens_saved,
            'estimated_cost_saved_usd': round(self.metrics.estimated_cost_saved_usd, 4),
            'target_hit_rate': 30.0,
            'meets_target': self.metrics.hit_rate >= 0.30
        }

    def adjust_ttl_for_defcon(self, base_ttl: int) -> int:
        """
        Adjust TTL based on current DEFCON level.

        Higher DEFCON = shorter TTL (fresher data needed).
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT current_level FROM fhq_governance.defcon_state
                    ORDER BY state_timestamp DESC LIMIT 1
                """)
                row = cur.fetchone()
                defcon = row[0] if row else 'GREEN'

                # DEFCON multipliers
                multipliers = {
                    'GREEN': 1.0,    # Normal TTL
                    'YELLOW': 0.8,   # 80% of normal
                    'ORANGE': 0.5,   # 50% of normal
                    'RED': 0.25,     # 25% of normal
                    'BLACK': 0.1     # 10% of normal (near-real-time)
                }

                multiplier = multipliers.get(defcon, 1.0)
                adjusted = max(1, int(base_ttl * multiplier))

                if adjusted != base_ttl:
                    logger.info(f"TTL adjusted for DEFCON {defcon}: {base_ttl} -> {adjusted} min")

                return adjusted

        except Exception as e:
            logger.warning(f"Could not check DEFCON for TTL: {e}")
            return base_ttl


class QdrantRAGCacheIntegration:
    """
    Integration layer for QdrantGraphRAGClient with caching.

    Wraps graphrag_retrieve() calls with cache checks.
    """

    def __init__(self, qdrant_client, cache: RAGQueryCache):
        self.qdrant = qdrant_client
        self.cache = cache

    def cached_retrieve(
        self,
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> Tuple[List[Dict], bool]:
        """
        Retrieve with caching.

        Returns (results, was_cached).
        """
        # Generate cache key including params
        cache_key = f"{query}|top_k={top_k}"
        for k, v in sorted(kwargs.items()):
            cache_key += f"|{k}={v}"

        # Try cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached.get('results', []), True

        # Call actual retrieval
        results = self.qdrant.graphrag_retrieve(query, top_k=top_k, **kwargs)

        # Estimate token count (rough approximation)
        token_count = sum(
            len(str(r).split()) * 1.3  # ~1.3 tokens per word
            for r in results
        )

        # Cache results
        self.cache.put(
            cache_key,
            {'results': results, 'top_k': top_k},
            int(token_count)
        )

        return results, False


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='RAG Query Cache (CEO-DIR-2026-120 P3.1)'
    )
    parser.add_argument('--test', action='store_true', help='Run test queries')
    parser.add_argument('--cleanup', action='store_true', help='Clean expired entries')
    parser.add_argument('--metrics', action='store_true', help='Show cache metrics')

    args = parser.parse_args()

    cache = RAGQueryCache()
    cache.connect()

    try:
        if args.cleanup:
            deleted = cache.cleanup_expired()
            print(f"Cleaned up {deleted} expired entries")

        elif args.metrics:
            metrics = cache.get_metrics_summary()
            print(json.dumps(metrics, indent=2))

        elif args.test:
            # Test caching
            test_query = "What is the current market regime for AAPL?"

            # First query (should miss)
            result1 = cache.get(test_query)
            print(f"First query: {'HIT' if result1 else 'MISS'}")

            # Store result
            cache.put(
                test_query,
                {'answer': 'NEUTRAL regime', 'confidence': 0.75},
                token_count=150
            )

            # Second query (should hit)
            result2 = cache.get(test_query)
            print(f"Second query: {'HIT' if result2 else 'MISS'}")
            if result2:
                print(f"Cached result: {result2}")

            # Show metrics
            print("\nMetrics:")
            print(json.dumps(cache.get_metrics_summary(), indent=2))

        else:
            parser.print_help()

    finally:
        cache.close()


if __name__ == '__main__':
    main()
