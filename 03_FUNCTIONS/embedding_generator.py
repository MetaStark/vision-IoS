"""
Embedding Generator for FjordHQ Cognitive Engines
CEO-DIR-2026-COGNITIVE-ENGINES-001

Constitutional: ADR-017, ADR-020, ADR-021

This module provides embedding generation via OpenAI's API.
Used by:
- InForage hybrid retriever (query embeddings)
- Message embedding writer (conversation memory)
- Archival memory (semantic indexing)

Patches Applied:
- [P8] import math for NaN validation
- [P6] Generate query embeddings before Qdrant search (wiring support)
"""

import os
import math
import hashlib
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""
    pass


class EmbeddingValidationError(Exception):
    """Raised when embedding validation fails."""
    pass


class EmbeddingGenerator:
    """
    Generate embeddings using OpenAI's embedding API.

    Model: text-embedding-3-small (1536 dimensions)
    Cost: ~$0.00002 per 1K tokens

    Usage:
        generator = EmbeddingGenerator(api_key="sk-...")
        embedding = generator.generate_query_embedding("What is BTC price?")
    """

    # Default model configuration
    MODEL = "text-embedding-3-small"
    DIMENSION = 1536

    # Cost per 1K tokens (as of 2025)
    COST_PER_1K_TOKENS = 0.00002

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None
    ):
        """
        Initialize the embedding generator.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
            model: Embedding model name. Defaults to text-embedding-3-small.
            dimension: Expected embedding dimension. Defaults to 1536.
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key to constructor."
            )

        self.model = model or self.MODEL
        self.dimension = dimension or self.DIMENSION
        self.client = openai.OpenAI(api_key=self.api_key)

        # Track usage for cost monitoring
        self._total_tokens_used = 0
        self._total_requests = 0

    def generate(
        self,
        texts: List[str],
        validate: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of text strings to embed.
            validate: Whether to validate embeddings (dimension, NaN check).

        Returns:
            List of embedding vectors (each is List[float] of length self.dimension).

        Raises:
            EmbeddingError: If API call fails.
            EmbeddingValidationError: If validation fails.
        """
        if not texts:
            return []

        # Filter empty strings
        texts = [t for t in texts if t and t.strip()]
        if not texts:
            return []

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise EmbeddingError(f"Embedding generation failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in embedding generation: {e}")
            raise EmbeddingError(f"Embedding generation failed: {e}") from e

        # Extract embeddings
        embeddings = [e.embedding for e in response.data]

        # Track usage
        if hasattr(response, 'usage') and response.usage:
            self._total_tokens_used += response.usage.total_tokens
        self._total_requests += 1

        # Validate if requested
        if validate:
            self._validate_embeddings(embeddings)

        return embeddings

    def generate_single(
        self,
        text: str,
        validate: bool = True
    ) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed.
            validate: Whether to validate embedding.

        Returns:
            Embedding vector (List[float] of length self.dimension).
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        embeddings = self.generate([text], validate=validate)
        return embeddings[0]

    def generate_query_embedding(
        self,
        query: str,
        validate: bool = True
    ) -> List[float]:
        """
        [P6] Generate embedding for a search query.

        This is the critical entry point for InForage hybrid retrieval.
        Without this, queries would not be converted to vectors before Qdrant search.

        Args:
            query: Search query text.
            validate: Whether to validate embedding.

        Returns:
            Query embedding vector.
        """
        return self.generate_single(query, validate=validate)

    def _validate_embeddings(self, embeddings: List[List[float]]) -> None:
        """
        Validate embeddings for dimension and NaN values.

        [P8] Uses math.isnan() for NaN validation.

        Raises:
            EmbeddingValidationError: If any validation fails.
        """
        for i, emb in enumerate(embeddings):
            # Check dimension
            if len(emb) != self.dimension:
                raise EmbeddingValidationError(
                    f"Embedding {i} has invalid dimension: {len(emb)} "
                    f"(expected {self.dimension})"
                )

            # [P8] Check for NaN values
            if any(math.isnan(v) for v in emb):
                raise EmbeddingValidationError(
                    f"Embedding {i} contains NaN values"
                )

            # Check for infinity
            if any(math.isinf(v) for v in emb):
                raise EmbeddingValidationError(
                    f"Embedding {i} contains infinite values"
                )

    def estimate_cost(self, texts: List[str]) -> float:
        """
        Estimate cost for embedding generation.

        Uses rough estimate of 4 characters per token.

        Args:
            texts: List of texts to estimate cost for.

        Returns:
            Estimated cost in USD.
        """
        total_chars = sum(len(t) for t in texts)
        estimated_tokens = total_chars / 4  # Rough estimate
        return (estimated_tokens / 1000) * self.COST_PER_1K_TOKENS

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for this generator instance.

        Returns:
            Dict with tokens_used, requests, estimated_cost.
        """
        return {
            "tokens_used": self._total_tokens_used,
            "requests": self._total_requests,
            "estimated_cost_usd": (self._total_tokens_used / 1000) * self.COST_PER_1K_TOKENS,
            "model": self.model,
            "dimension": self.dimension
        }

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """
        Compute SHA-256 hash of content for deduplication.

        This matches the DB-side fhq_memory.sha256_hash() function.

        Args:
            content: Text content to hash.

        Returns:
            64-character hex string.
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


class CachedEmbeddingGenerator(EmbeddingGenerator):
    """
    Embedding generator with in-memory caching.

    Useful for repeated queries within a session.
    Cache is content-hash based for deduplication.
    """

    def __init__(self, *args, max_cache_size: int = 1000, **kwargs):
        """
        Initialize cached embedding generator.

        Args:
            max_cache_size: Maximum number of embeddings to cache.
            *args, **kwargs: Passed to EmbeddingGenerator.
        """
        super().__init__(*args, **kwargs)
        self._cache: Dict[str, List[float]] = {}
        self._max_cache_size = max_cache_size
        self._cache_hits = 0
        self._cache_misses = 0

    def generate_single(
        self,
        text: str,
        validate: bool = True
    ) -> List[float]:
        """
        Generate embedding with caching.

        Args:
            text: Text to embed.
            validate: Whether to validate embedding.

        Returns:
            Embedding vector (possibly from cache).
        """
        # Compute cache key
        cache_key = self.compute_content_hash(text)

        # Check cache
        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]

        # Generate new embedding
        self._cache_misses += 1
        embedding = super().generate_single(text, validate=validate)

        # Add to cache (with eviction if needed)
        if len(self._cache) >= self._max_cache_size:
            # Simple FIFO eviction - remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[cache_key] = embedding
        return embedding

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, hit_rate, size.
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache),
            "max_cache_size": self._max_cache_size
        }

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0


# =============================================================================
# MOCK GENERATOR FOR TESTING
# =============================================================================

class MockEmbeddingGenerator(EmbeddingGenerator):
    """
    Mock embedding generator for testing.

    Generates deterministic embeddings based on content hash.
    Does not require OpenAI API key.
    """

    def __init__(self, dimension: int = 1536):
        """
        Initialize mock generator.

        Args:
            dimension: Embedding dimension to generate.
        """
        # Skip parent __init__ to avoid API key requirement
        self.model = "mock-embedding-model"
        self.dimension = dimension
        self._total_tokens_used = 0
        self._total_requests = 0

    def generate(
        self,
        texts: List[str],
        validate: bool = True
    ) -> List[List[float]]:
        """
        Generate mock embeddings based on content hash.

        Args:
            texts: List of texts to embed.
            validate: Whether to validate embeddings.

        Returns:
            List of deterministic embedding vectors.
        """
        embeddings = []
        for text in texts:
            embedding = self._generate_deterministic_embedding(text)
            embeddings.append(embedding)

        # Track usage
        self._total_tokens_used += sum(len(t) // 4 for t in texts)
        self._total_requests += 1

        if validate:
            self._validate_embeddings(embeddings)

        return embeddings

    def _generate_deterministic_embedding(self, text: str) -> List[float]:
        """
        Generate deterministic embedding from text hash.

        Uses SHA-256 hash to seed a deterministic vector.
        """
        import random

        # Use content hash as seed for reproducibility
        content_hash = self.compute_content_hash(text)
        seed = int(content_hash[:16], 16)  # Use first 64 bits as seed
        rng = random.Random(seed)

        # Generate normalized vector
        embedding = [rng.gauss(0, 1) for _ in range(self.dimension)]

        # Normalize to unit length (like real embeddings)
        magnitude = math.sqrt(sum(v * v for v in embedding))
        if magnitude > 0:
            embedding = [v / magnitude for v in embedding]

        return embedding
