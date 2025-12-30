#!/usr/bin/env python3
"""
FINN Truth Engine
CEO-DIR-2025-FINN-001 Phase 2

The FINN Truth Engine is the cognitive core of FjordHQ's Autonomous Cognitive
Intelligence (ACI) system. It generates court-proof hypotheses and golden
needle candidates via GraphRAG retrieval.

CRITICAL: FINN has Zero Execution Authority (ZEA).
It is the brain, NOT the hands. All outputs are G0 Draft Proposals.

ACI Triangle Integration:
  EC-018 (Meta-Alpha) → First receiver of CEO intent
  EC-020 (SitC)       → Chain-of-Query construction
  EC-021 (InForage)   → Budget gates for retrieval
  EC-022 (IKEA)       → Hallucination firewall

GraphRAG Contract:
  Step 1: Qdrant → candidate nodes (semantic proximity)
  Step 2: Postgres → relationship expansion (edges, hops, causality)
  Step 3: FINN → reasoning + synthesis (THIS FILE)

ADR Compliance: ADR-020 (ACI), ADR-004 (G0), ADR-013 (Canonical Truth)
EC Compliance: EC-018, EC-020, EC-021, EC-022

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

# Local imports
try:
    from qdrant_graphrag_client import QdrantGraphRAGClient, EvidenceNode, GraphRAGResult
except ImportError:
    # Allow running from different directories
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from qdrant_graphrag_client import QdrantGraphRAGClient, EvidenceNode, GraphRAGResult

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FINNTruthEngine")


@dataclass
class G0DraftProposal:
    """
    G0 Draft Proposal structure per EC-018 Section 5 and ADR-004.

    Any FINN output that proposes a new initiative, indicator, IoS module,
    or material system change MUST be structured as a G0 Draft Proposal.
    """
    proposal_id: str
    proposal_type: str  # HYPOTHESIS, GOLDEN_NEEDLE_CANDIDATE, INITIATIVE, INDICATOR
    title: str
    summary: str

    # Hypothesis-specific fields
    hypothesis_statement: Optional[str] = None
    confidence_score: float = 0.0
    critical_dependencies: List[str] = field(default_factory=list)

    # Evidence chain (court-proof)
    evidence_ids: List[str] = field(default_factory=list)
    evidence_summary: str = ""
    graphrag_retrieval_count: int = 0

    # ACI Triangle attestations
    sitc_plan_id: Optional[str] = None
    sitc_node_count: int = 0
    inforage_cost_usd: float = 0.0
    ikea_classification: str = "UNVERIFIED"  # PARAMETRIC, EXTERNAL_REQUIRED, HYBRID
    ikea_confidence: float = 0.0

    # Governance
    generated_by: str = "FINN"
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    requires_vega_approval: bool = True

    # Hash chain
    content_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "proposal_id": self.proposal_id,
            "proposal_type": self.proposal_type,
            "title": self.title,
            "summary": self.summary,
            "hypothesis_statement": self.hypothesis_statement,
            "confidence_score": self.confidence_score,
            "critical_dependencies": self.critical_dependencies,
            "evidence": {
                "evidence_ids": self.evidence_ids,
                "evidence_summary": self.evidence_summary,
                "graphrag_retrieval_count": self.graphrag_retrieval_count
            },
            "aci_triangle": {
                "sitc_plan_id": self.sitc_plan_id,
                "sitc_node_count": self.sitc_node_count,
                "inforage_cost_usd": self.inforage_cost_usd,
                "ikea_classification": self.ikea_classification,
                "ikea_confidence": self.ikea_confidence
            },
            "governance": {
                "generated_by": self.generated_by,
                "generated_at": self.generated_at,
                "requires_vega_approval": self.requires_vega_approval,
                "content_hash": self.content_hash
            }
        }

    def compute_hash(self):
        """Compute content hash for audit trail"""
        content = json.dumps({
            "title": self.title,
            "hypothesis_statement": self.hypothesis_statement,
            "evidence_ids": sorted(self.evidence_ids),
            "confidence_score": self.confidence_score
        }, sort_keys=True)
        self.content_hash = hashlib.sha256(content.encode()).hexdigest()


@dataclass
class TruthEngineQuery:
    """Query structure for FINN Truth Engine"""
    query_text: str
    domain: str = "FINANCE"  # FINANCE, CRYPTO, MACRO, REGULATORY
    intent: str = "HYPOTHESIS"  # HYPOTHESIS, FACT_CHECK, CAUSAL_ANALYSIS
    source: str = "EC-018"  # Originating component
    session_id: Optional[str] = None
    budget_limit_usd: float = 5.0  # EC-018 daily budget


class FINNTruthEngine:
    """
    FINN Truth Engine - GraphRAG-powered hypothesis generation.

    This engine implements Step 3 of the GraphRAG contract:
      Step 1: Qdrant → candidate nodes (via QdrantGraphRAGClient)
      Step 2: Postgres → relationship expansion (via QdrantGraphRAGClient)
      Step 3: FINN → reasoning + synthesis (THIS CLASS)

    CRITICAL: Zero Execution Authority (ZEA).
    All outputs are G0 Draft Proposals requiring VEGA approval.

    Usage:
        engine = FINNTruthEngine()
        proposal = engine.generate_hypothesis(
            TruthEngineQuery(query_text="What drives BTC price?")
        )
    """

    def __init__(
        self,
        graphrag_client: Optional[QdrantGraphRAGClient] = None,
        defcon_level: str = "GREEN",
        embedding_model: str = "text-embedding-3-small"
    ):
        """
        Initialize FINN Truth Engine.

        Args:
            graphrag_client: Pre-configured GraphRAG client (optional)
            defcon_level: Initial DEFCON level
            embedding_model: Model for generating embeddings
        """
        self.graphrag = graphrag_client or QdrantGraphRAGClient(defcon_level=defcon_level)
        self.embedding_model = embedding_model
        self.defcon_level = defcon_level

        # Cost tracking (EC-021 InForage)
        self.session_cost_usd = 0.0
        self.api_call_count = 0

        # Postgres connection
        self.pg_config = {
            "host": os.getenv("PGHOST", "127.0.0.1"),
            "port": int(os.getenv("PGPORT", "54322")),
            "database": os.getenv("PGDATABASE", "postgres"),
            "user": os.getenv("PGUSER", "postgres"),
            "password": os.getenv("PGPASSWORD", "postgres"),
        }

        logger.info(f"[FINN] Truth Engine initialized at DEFCON {defcon_level}")

    def _get_pg_connection(self):
        """Get Postgres connection"""
        return psycopg2.connect(**self.pg_config)

    # =========================================================================
    # EC-021 InForage: Budget Control
    # =========================================================================

    def _check_budget(self, query: TruthEngineQuery, estimated_cost: float) -> bool:
        """
        Check if operation is within budget (EC-021).

        Args:
            query: The query with budget_limit_usd
            estimated_cost: Estimated cost of operation

        Returns:
            True if within budget, False otherwise
        """
        if self.session_cost_usd + estimated_cost > query.budget_limit_usd:
            logger.warning(
                f"[FINN] Budget exceeded: session={self.session_cost_usd:.4f}, "
                f"estimated={estimated_cost:.4f}, limit={query.budget_limit_usd}"
            )
            return False
        return True

    def _record_cost(self, cost_usd: float, operation: str):
        """Record API cost for InForage tracking"""
        self.session_cost_usd += cost_usd
        self.api_call_count += 1
        logger.info(f"[FINN] InForage: {operation} cost=${cost_usd:.4f}, session_total=${self.session_cost_usd:.4f}")

    # =========================================================================
    # EC-022 IKEA: Hallucination Firewall
    # =========================================================================

    def _classify_knowledge_boundary(
        self,
        query: TruthEngineQuery,
        graphrag_results: List[GraphRAGResult]
    ) -> Tuple[str, float]:
        """
        Classify query per EC-022 IKEA knowledge boundary rules.

        Classifications:
        - PARAMETRIC: Stable, internal knowledge (answer directly)
        - EXTERNAL_REQUIRED: Time-sensitive, volatile (mandatory retrieval)
        - HYBRID: Combined stable + current

        Args:
            query: The query to classify
            graphrag_results: Results from GraphRAG retrieval

        Returns:
            Tuple of (classification, confidence)
        """
        # Get IKEA thresholds from calibration
        ikea_external_threshold = self._get_calibration("IKEA_EXTERNAL_REQUIRED", 0.70)

        # Check if we have fresh evidence
        has_fresh_evidence = len(graphrag_results) > 0
        avg_confidence = (
            sum(r.confidence_score for r in graphrag_results) / len(graphrag_results)
            if graphrag_results else 0.0
        )

        # Domain-based classification
        volatile_domains = ["CRYPTO", "PRICE", "EXECUTION"]
        is_volatile = query.domain in volatile_domains or any(
            kw in query.query_text.lower()
            for kw in ["price", "current", "now", "today", "latest"]
        )

        if is_volatile:
            if has_fresh_evidence and avg_confidence >= ikea_external_threshold:
                return "EXTERNAL_REQUIRED", avg_confidence
            else:
                return "EXTERNAL_REQUIRED", 0.0  # Needs retrieval
        elif has_fresh_evidence:
            return "HYBRID", avg_confidence
        else:
            return "PARAMETRIC", 0.95  # High confidence for stable knowledge

    def _get_calibration(self, param_name: str, default: float) -> float:
        """Get calibration value from fhq_governance.calibration_versions"""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT value FROM fhq_governance.calibration_versions
                    WHERE parameter_name = %s AND is_active = TRUE
                    LIMIT 1
                """, (param_name,))
                row = cur.fetchone()
                return float(row[0]) if row else default
        except Exception as e:
            logger.warning(f"[FINN] Failed to get calibration {param_name}: {e}")
            return default
        finally:
            conn.close()

    # =========================================================================
    # Core Hypothesis Generation
    # =========================================================================

    def generate_hypothesis(
        self,
        query: TruthEngineQuery,
        top_k: int = 10,
        expand_hops: int = 2
    ) -> G0DraftProposal:
        """
        Generate a hypothesis as a G0 Draft Proposal.

        This is the main entry point for FINN Truth Engine.
        All outputs are G0 bound per EC-018 Section 5.

        Args:
            query: TruthEngineQuery with query text and constraints
            top_k: Number of GraphRAG candidates
            expand_hops: Relationship expansion depth

        Returns:
            G0DraftProposal ready for VEGA review
        """
        proposal_id = f"G0-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        session_id = query.session_id or str(uuid.uuid4())

        logger.info(f"[FINN] Generating hypothesis for: {query.query_text[:50]}...")

        # Step 1+2: GraphRAG retrieval (via client)
        # Note: In production, this would use embedding generation
        # For now, we'll use a placeholder embedding (all zeros)
        # TODO: Integrate with actual embedding model
        query_embedding = [0.0] * 1536  # Placeholder

        graphrag_results = self.graphrag.graphrag_retrieve(
            query_embedding=query_embedding,
            top_k=top_k,
            domain_filter=query.domain if query.domain != "FINANCE" else None,
            expand_hops=expand_hops,
            score_threshold=0.3
        )

        # EC-022: IKEA classification
        ikea_classification, ikea_confidence = self._classify_knowledge_boundary(
            query, graphrag_results
        )

        # Extract evidence IDs
        evidence_ids = [r.evidence_id for r in graphrag_results]

        # Build evidence summary
        evidence_summary = self._build_evidence_summary(graphrag_results)

        # Identify critical dependencies
        critical_deps = self._extract_critical_dependencies(graphrag_results)

        # Calculate confidence score
        confidence_score = self._calculate_confidence(
            graphrag_results, ikea_classification, ikea_confidence
        )

        # Build hypothesis statement
        hypothesis_statement = self._synthesize_hypothesis(
            query, graphrag_results, ikea_classification
        )

        # Create G0 Draft Proposal
        proposal = G0DraftProposal(
            proposal_id=proposal_id,
            proposal_type="HYPOTHESIS",
            title=f"Hypothesis: {query.query_text[:50]}...",
            summary=f"GraphRAG-generated hypothesis based on {len(graphrag_results)} evidence nodes.",
            hypothesis_statement=hypothesis_statement,
            confidence_score=confidence_score,
            critical_dependencies=critical_deps,
            evidence_ids=evidence_ids,
            evidence_summary=evidence_summary,
            graphrag_retrieval_count=len(graphrag_results),
            sitc_plan_id=None,  # TODO: Integrate with SitC
            sitc_node_count=0,
            inforage_cost_usd=self.session_cost_usd,
            ikea_classification=ikea_classification,
            ikea_confidence=ikea_confidence,
            generated_by="FINN",
            requires_vega_approval=True
        )

        # Compute content hash for audit
        proposal.compute_hash()

        # Persist to database
        self._persist_proposal(proposal, session_id)

        logger.info(
            f"[FINN] Generated {proposal.proposal_id}: "
            f"confidence={confidence_score:.2f}, "
            f"evidence={len(evidence_ids)}, "
            f"ikea={ikea_classification}"
        )

        return proposal

    def _build_evidence_summary(self, results: List[GraphRAGResult]) -> str:
        """Build human-readable evidence summary"""
        if not results:
            return "No evidence retrieved from GraphRAG."

        summary_parts = []
        for i, r in enumerate(results[:5]):  # Top 5
            summary_parts.append(
                f"[{i+1}] {r.content[:100]}... "
                f"(score={r.score:.2f}, confidence={r.confidence_score:.2f})"
            )

        return "\n".join(summary_parts)

    def _extract_critical_dependencies(self, results: List[GraphRAGResult]) -> List[str]:
        """Extract critical dependencies from causal edges"""
        deps = set()
        for r in results:
            for edge in r.causal_edges:
                if edge.get("hypothesis"):
                    deps.add(edge["hypothesis"])
                if edge.get("transmission_mechanism"):
                    deps.add(f"Mechanism: {edge['transmission_mechanism']}")
        return list(deps)[:5]  # Top 5 dependencies

    def _calculate_confidence(
        self,
        results: List[GraphRAGResult],
        ikea_classification: str,
        ikea_confidence: float
    ) -> float:
        """
        Calculate overall confidence score.

        Factors:
        - GraphRAG retrieval scores
        - IKEA classification confidence
        - Evidence count
        - Causal edge strength
        """
        if not results:
            return 0.0

        # Base: average GraphRAG score
        avg_score = sum(r.score for r in results) / len(results)

        # Boost for high evidence count
        evidence_boost = min(0.1, len(results) * 0.01)

        # IKEA confidence factor
        ikea_factor = ikea_confidence * 0.3

        # Causal edge boost
        total_causal = sum(len(r.causal_edges) for r in results)
        causal_boost = min(0.1, total_causal * 0.02)

        # Combine (capped at 0.95 - cannot be certain)
        confidence = min(0.95, avg_score * 0.5 + evidence_boost + ikea_factor + causal_boost)

        return round(confidence, 4)

    def _synthesize_hypothesis(
        self,
        query: TruthEngineQuery,
        results: List[GraphRAGResult],
        ikea_classification: str
    ) -> str:
        """
        Synthesize hypothesis statement from evidence.

        In production, this would use the LLM for synthesis.
        For now, we build a structured statement from evidence.
        """
        if not results:
            return f"Insufficient evidence to generate hypothesis for: {query.query_text}"

        # Aggregate domains and entities
        domains = set(r.domain for r in results)
        entities = set(r.entity_type for r in results if r.entity_type)

        # Count causal relationships
        causal_count = sum(len(r.causal_edges) for r in results)

        statement = (
            f"Based on {len(results)} evidence nodes spanning domains {domains}, "
            f"with {causal_count} causal relationships identified, "
            f"the following hypothesis emerges:\n\n"
            f"Query: {query.query_text}\n\n"
            f"Key entities involved: {entities if entities else 'Various'}\n"
            f"Knowledge classification: {ikea_classification}\n\n"
            f"Evidence summary: {self._build_evidence_summary(results[:3])}"
        )

        return statement

    def _persist_proposal(self, proposal: G0DraftProposal, session_id: str):
        """Persist G0 proposal to database for VEGA review using existing schema"""
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                # Use existing g0_draft_proposals schema
                # Map our proposal fields to existing columns
                cur.execute("""
                    INSERT INTO fhq_alpha.g0_draft_proposals (
                        proposal_id,
                        hunt_session_id,
                        hypothesis_id,
                        hypothesis_title,
                        hypothesis_category,
                        hypothesis_statement,
                        confidence_score,
                        executive_summary,
                        falsification_criteria,
                        proposal_status,
                        sitc_plan_id,
                        sitc_confidence,
                        sitc_envelope
                    ) VALUES (
                        gen_random_uuid(),
                        %s::uuid,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s::jsonb,
                        'G0_PENDING',
                        %s,
                        %s,
                        %s::jsonb
                    )
                    RETURNING proposal_id::TEXT
                """, (
                    session_id if session_id and len(session_id) == 36 else None,
                    proposal.proposal_id,  # Use as hypothesis_id
                    proposal.title,  # hypothesis_title
                    proposal.proposal_type,  # hypothesis_category
                    proposal.hypothesis_statement,
                    proposal.confidence_score,
                    proposal.summary,  # executive_summary
                    json.dumps({
                        "evidence_ids": proposal.evidence_ids,
                        "graphrag_count": proposal.graphrag_retrieval_count,
                        "ikea_classification": proposal.ikea_classification,
                        "ikea_confidence": proposal.ikea_confidence,
                        "content_hash": proposal.content_hash
                    }),
                    proposal.sitc_plan_id,
                    proposal.ikea_classification,  # Use IKEA as SitC confidence proxy
                    json.dumps({
                        "inforage_cost_usd": proposal.inforage_cost_usd,
                        "sitc_node_count": proposal.sitc_node_count,
                        "evidence_summary": proposal.evidence_summary[:500] if proposal.evidence_summary else None
                    })
                ))
                result = cur.fetchone()
                conn.commit()

                logger.info(f"[FINN] Persisted G0 proposal {result[0] if result else proposal.proposal_id}")

        except Exception as e:
            logger.error(f"[FINN] Failed to persist proposal: {e}")
            conn.rollback()
        finally:
            conn.close()

    # =========================================================================
    # Health & Status
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get engine status including GraphRAG health"""
        graphrag_health = self.graphrag.health_check()

        return {
            "engine": "FINN Truth Engine",
            "version": "1.0.0",
            "directive": "CEO-DIR-2025-FINN-001",
            "defcon_level": self.defcon_level,
            "session_cost_usd": self.session_cost_usd,
            "api_call_count": self.api_call_count,
            "graphrag": graphrag_health,
            "aci_integration": {
                "ec_018": "Meta-Alpha query receiver",
                "ec_020": "SitC Chain-of-Query (pending)",
                "ec_021": "InForage budget tracking",
                "ec_022": "IKEA classification"
            },
            "zea_enforced": True,  # Zero Execution Authority
            "g0_output_only": True
        }


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FINN Truth Engine CLI")
    parser.add_argument("--status", action="store_true", help="Show engine status")
    parser.add_argument("--query", type=str, help="Generate hypothesis for query")
    parser.add_argument("--domain", default="CRYPTO", help="Query domain")
    parser.add_argument("--defcon", default="GREEN", help="DEFCON level")
    args = parser.parse_args()

    engine = FINNTruthEngine(defcon_level=args.defcon)

    if args.status:
        status = engine.get_status()
        print(json.dumps(status, indent=2))

    elif args.query:
        query = TruthEngineQuery(
            query_text=args.query,
            domain=args.domain,
            intent="HYPOTHESIS"
        )
        proposal = engine.generate_hypothesis(query)
        print(json.dumps(proposal.to_dict(), indent=2))

    else:
        print("Usage: python finn_truth_engine.py --status")
        print("       python finn_truth_engine.py --query 'What drives BTC price?'")
