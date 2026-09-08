"""
LLM-as-Judge Evaluator for FjordHQ Cognitive Engines
CEO-DIR-2026-COGNITIVE-ENGINES-001

Constitutional: ADR-017, ADR-020, ADR-021
Reference: Zheng et al., 2023 - "Judging LLM-as-a-Judge"

This module provides evaluation metrics for:
1. Retrieval Quality (NDCG@K, MRR)
2. Faithfulness (grounding in evidence)
3. Answer Relevance (addresses the query)

G2 Gate Requirement: NDCG@10 >= 0.8 on Golden Alpha test set
"""

import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass

from schemas.cognitive_engines import (
    GoldenAlphaTestCase,
    EvidenceBundle,
    FusedResult,
    DEFCONLevel
)

logger = logging.getLogger(__name__)


# =============================================================================
# RETRIEVAL METRICS
# =============================================================================

def calculate_ndcg(
    retrieved_ids: List[UUID],
    relevant_ids: List[UUID],
    k: int = 10
) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain (NDCG@K).

    NDCG = DCG / IDCG
    DCG = sum(rel_i / log2(i + 1)) for i in 1..k
    IDCG = ideal DCG with perfect ranking

    Args:
        retrieved_ids: List of retrieved evidence IDs (in rank order).
        relevant_ids: List of relevant evidence IDs (ground truth).
        k: Cutoff for evaluation.

    Returns:
        NDCG score between 0 and 1.
    """
    if not relevant_ids:
        return 1.0 if not retrieved_ids else 0.0

    # Convert to sets for O(1) lookup
    relevant_set = set(relevant_ids)

    # Calculate DCG
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        if doc_id in relevant_set:
            # rel_i = 1 for binary relevance
            dcg += 1.0 / math.log2(i + 2)  # +2 because i is 0-indexed

    # Calculate IDCG (ideal DCG)
    idcg = 0.0
    num_relevant = min(len(relevant_ids), k)
    for i in range(num_relevant):
        idcg += 1.0 / math.log2(i + 2)

    if idcg == 0:
        return 0.0

    return dcg / idcg


def calculate_mrr(
    retrieved_ids: List[UUID],
    relevant_ids: List[UUID]
) -> float:
    """
    Calculate Mean Reciprocal Rank (MRR).

    MRR = 1 / rank of first relevant result

    Args:
        retrieved_ids: List of retrieved evidence IDs (in rank order).
        relevant_ids: List of relevant evidence IDs (ground truth).

    Returns:
        MRR score between 0 and 1.
    """
    relevant_set = set(relevant_ids)

    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_set:
            return 1.0 / (i + 1)

    return 0.0


def calculate_precision_at_k(
    retrieved_ids: List[UUID],
    relevant_ids: List[UUID],
    k: int = 10
) -> float:
    """
    Calculate Precision@K.

    P@K = |relevant in top-K| / K

    Args:
        retrieved_ids: List of retrieved evidence IDs (in rank order).
        relevant_ids: List of relevant evidence IDs (ground truth).
        k: Cutoff for evaluation.

    Returns:
        Precision score between 0 and 1.
    """
    relevant_set = set(relevant_ids)
    top_k = retrieved_ids[:k]

    relevant_in_top_k = sum(1 for doc_id in top_k if doc_id in relevant_set)

    return relevant_in_top_k / k if k > 0 else 0.0


def calculate_recall_at_k(
    retrieved_ids: List[UUID],
    relevant_ids: List[UUID],
    k: int = 10
) -> float:
    """
    Calculate Recall@K.

    R@K = |relevant in top-K| / |total relevant|

    Args:
        retrieved_ids: List of retrieved evidence IDs (in rank order).
        relevant_ids: List of relevant evidence IDs (ground truth).
        k: Cutoff for evaluation.

    Returns:
        Recall score between 0 and 1.
    """
    if not relevant_ids:
        return 1.0

    relevant_set = set(relevant_ids)
    top_k = retrieved_ids[:k]

    relevant_in_top_k = sum(1 for doc_id in top_k if doc_id in relevant_set)

    return relevant_in_top_k / len(relevant_ids)


# =============================================================================
# EVALUATION RESULT
# =============================================================================

@dataclass
class RetrievalEvaluationResult:
    """Result of retrieval evaluation on a single test case."""
    testcase_id: UUID
    query_text: str
    ndcg_at_10: float
    mrr: float
    precision_at_10: float
    recall_at_10: float
    retrieved_count: int
    relevant_count: int
    passed: bool  # NDCG@10 >= 0.8


@dataclass
class TestSetEvaluationResult:
    """Result of evaluation on entire test set."""
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    mean_ndcg_at_10: float
    mean_mrr: float
    mean_precision_at_10: float
    mean_recall_at_10: float
    meets_g2_requirement: bool  # mean NDCG@10 >= 0.8
    per_case_results: List[RetrievalEvaluationResult]
    evaluated_at: datetime


# =============================================================================
# LLM JUDGE EVALUATOR
# =============================================================================

class LLMJudgeEvaluator:
    """
    Evaluator for retrieval quality and LLM response faithfulness.

    G2 Gate Requirement: NDCG@10 >= 0.8 on Golden Alpha test set.

    Usage:
        evaluator = LLMJudgeEvaluator(db_conn, retriever)
        result = evaluator.evaluate_test_set()
        if result.meets_g2_requirement:
            print("G2 PASSED")
    """

    G2_NDCG_THRESHOLD = 0.8

    def __init__(
        self,
        db_conn: Any,
        retriever: Any = None
    ):
        """
        Initialize the evaluator.

        Args:
            db_conn: Database connection.
            retriever: InForageHybridRetriever instance (optional).
        """
        self.db = db_conn
        self.retriever = retriever

    def evaluate_retrieval(
        self,
        query_text: str,
        retrieved_ids: List[UUID],
        relevant_ids: List[UUID],
        testcase_id: UUID = None
    ) -> RetrievalEvaluationResult:
        """
        Evaluate retrieval quality for a single query.

        Args:
            query_text: The query text.
            retrieved_ids: List of retrieved evidence IDs.
            relevant_ids: List of relevant evidence IDs (ground truth).
            testcase_id: Optional test case ID.

        Returns:
            RetrievalEvaluationResult with all metrics.
        """
        ndcg = calculate_ndcg(retrieved_ids, relevant_ids, k=10)
        mrr = calculate_mrr(retrieved_ids, relevant_ids)
        precision = calculate_precision_at_k(retrieved_ids, relevant_ids, k=10)
        recall = calculate_recall_at_k(retrieved_ids, relevant_ids, k=10)

        return RetrievalEvaluationResult(
            testcase_id=testcase_id or UUID('00000000-0000-0000-0000-000000000000'),
            query_text=query_text,
            ndcg_at_10=ndcg,
            mrr=mrr,
            precision_at_10=precision,
            recall_at_10=recall,
            retrieved_count=len(retrieved_ids),
            relevant_count=len(relevant_ids),
            passed=ndcg >= self.G2_NDCG_THRESHOLD
        )

    def evaluate_test_set(
        self,
        test_cases: List[GoldenAlphaTestCase] = None,
        defcon_level: DEFCONLevel = DEFCONLevel.ORANGE
    ) -> TestSetEvaluationResult:
        """
        Evaluate retrieval on the Golden Alpha test set.

        If test_cases is not provided, loads from database.

        Args:
            test_cases: List of test cases (optional).
            defcon_level: DEFCON level for retrieval.

        Returns:
            TestSetEvaluationResult with aggregate metrics.
        """
        if test_cases is None:
            test_cases = self._load_test_set()

        if not test_cases:
            logger.warning("No test cases found for evaluation")
            return TestSetEvaluationResult(
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                pass_rate=0.0,
                mean_ndcg_at_10=0.0,
                mean_mrr=0.0,
                mean_precision_at_10=0.0,
                mean_recall_at_10=0.0,
                meets_g2_requirement=False,
                per_case_results=[],
                evaluated_at=datetime.utcnow()
            )

        results = []
        for case in test_cases:
            # Run retrieval if retriever is available
            if self.retriever:
                bundle = self.retriever.retrieve(
                    query_text=case.query_text,
                    defcon_level=defcon_level,
                    top_k=20,
                    rerank_cutoff=10
                )
                retrieved_ids = bundle.snippet_ids
            else:
                # No retriever, use empty results
                retrieved_ids = []

            result = self.evaluate_retrieval(
                query_text=case.query_text,
                retrieved_ids=retrieved_ids,
                relevant_ids=case.expected_snippet_ids,
                testcase_id=case.testcase_id
            )
            results.append(result)

            # Update test case in database
            self._update_test_case_result(case.testcase_id, result)

        # Calculate aggregates
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        mean_ndcg = sum(r.ndcg_at_10 for r in results) / total if total > 0 else 0.0
        mean_mrr = sum(r.mrr for r in results) / total if total > 0 else 0.0
        mean_precision = sum(r.precision_at_10 for r in results) / total if total > 0 else 0.0
        mean_recall = sum(r.recall_at_10 for r in results) / total if total > 0 else 0.0

        return TestSetEvaluationResult(
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            pass_rate=passed / total if total > 0 else 0.0,
            mean_ndcg_at_10=mean_ndcg,
            mean_mrr=mean_mrr,
            mean_precision_at_10=mean_precision,
            mean_recall_at_10=mean_recall,
            meets_g2_requirement=mean_ndcg >= self.G2_NDCG_THRESHOLD,
            per_case_results=results,
            evaluated_at=datetime.utcnow()
        )

    def _load_test_set(self) -> List[GoldenAlphaTestCase]:
        """
        Load Golden Alpha test set from database.

        Only loads VEGA-signed test cases.
        """
        cursor = self.db.cursor()

        try:
            cursor.execute("""
                SELECT
                    testcase_id,
                    query_text,
                    expected_snippet_ids,
                    expected_answer_constraints,
                    domain,
                    difficulty,
                    created_at,
                    created_by,
                    vega_signature,
                    signature_timestamp,
                    last_evaluated_at,
                    last_result,
                    last_ndcg_score
                FROM fhq_governance.golden_alpha_testset
                WHERE vega_signature IS NOT NULL  -- Only VEGA-signed cases
                ORDER BY difficulty, created_at
            """)

            rows = cursor.fetchall()
            cases = []

            for row in rows:
                expected_snippet_ids = []
                if row[2]:
                    expected_snippet_ids = [
                        UUID(sid) if isinstance(sid, str) else sid
                        for sid in row[2]
                    ]

                cases.append(GoldenAlphaTestCase(
                    testcase_id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
                    query_text=row[1],
                    expected_snippet_ids=expected_snippet_ids,
                    expected_answer_constraints=row[3],
                    domain=row[4],
                    difficulty=row[5] or 'MEDIUM',
                    created_at=row[6],
                    created_by=row[7] or 'SYSTEM',
                    vega_signature=row[8],
                    signature_timestamp=row[9],
                    last_evaluated_at=row[10],
                    last_result=row[11],
                    last_ndcg_score=row[12]
                ))

            return cases

        finally:
            cursor.close()

    def _update_test_case_result(
        self,
        testcase_id: UUID,
        result: RetrievalEvaluationResult
    ) -> None:
        """
        Update test case with evaluation result.
        """
        cursor = self.db.cursor()

        try:
            cursor.execute("""
                UPDATE fhq_governance.golden_alpha_testset
                SET last_evaluated_at = %s,
                    last_result = %s,
                    last_ndcg_score = %s
                WHERE testcase_id = %s
            """, [
                datetime.utcnow(),
                'PASS' if result.passed else 'FAIL',
                result.ndcg_at_10,
                str(testcase_id)
            ])

            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to update test case result: {e}")
            self.db.rollback()

        finally:
            cursor.close()

    def evaluate_faithfulness(
        self,
        response: str,
        evidence: List[str]
    ) -> float:
        """
        Evaluate faithfulness of response to evidence.

        Uses simple term overlap as baseline.
        TODO: Integrate LLM-based evaluation (DeepSeek-R1, GPT-4).

        Args:
            response: LLM response text.
            evidence: List of evidence texts.

        Returns:
            Faithfulness score between 0 and 1.
        """
        if not evidence:
            return 0.0

        # Combine all evidence
        all_evidence = ' '.join(evidence).lower()

        # Extract key terms from response
        import re
        response_terms = set(re.findall(r'\b\w{4,}\b', response.lower()))

        if not response_terms:
            return 1.0  # Empty response is trivially faithful

        # Count terms that appear in evidence
        grounded_terms = sum(1 for term in response_terms if term in all_evidence)

        return grounded_terms / len(response_terms)

    def evaluate_relevance(
        self,
        query: str,
        response: str
    ) -> float:
        """
        Evaluate whether response addresses the query.

        Uses simple term overlap as baseline.
        TODO: Integrate LLM-based evaluation.

        Args:
            query: Original query.
            response: LLM response text.

        Returns:
            Relevance score between 0 and 1.
        """
        import re

        # Extract key terms from query
        query_terms = set(re.findall(r'\b\w{4,}\b', query.lower()))

        if not query_terms:
            return 1.0

        # Check how many query terms appear in response
        response_lower = response.lower()
        matched_terms = sum(1 for term in query_terms if term in response_lower)

        return matched_terms / len(query_terms)

    def generate_evaluation_report(
        self,
        result: TestSetEvaluationResult
    ) -> str:
        """
        Generate a formatted evaluation report.

        Args:
            result: TestSetEvaluationResult to report.

        Returns:
            Formatted report string.
        """
        lines = [
            "=" * 70,
            "GOLDEN ALPHA TEST SET EVALUATION REPORT",
            f"CEO-DIR-2026-COGNITIVE-ENGINES-001",
            "=" * 70,
            f"Evaluated at: {result.evaluated_at.isoformat()}",
            "",
            "-" * 70,
            "SUMMARY",
            "-" * 70,
            f"Total test cases:    {result.total_cases}",
            f"Passed (NDCG>=0.8):  {result.passed_cases}",
            f"Failed:              {result.failed_cases}",
            f"Pass rate:           {result.pass_rate:.1%}",
            "",
            "-" * 70,
            "AGGREGATE METRICS",
            "-" * 70,
            f"Mean NDCG@10:        {result.mean_ndcg_at_10:.4f}",
            f"Mean MRR:            {result.mean_mrr:.4f}",
            f"Mean Precision@10:   {result.mean_precision_at_10:.4f}",
            f"Mean Recall@10:      {result.mean_recall_at_10:.4f}",
            "",
            "-" * 70,
            "G2 GATE STATUS",
            "-" * 70,
            f"Requirement:         NDCG@10 >= {self.G2_NDCG_THRESHOLD}",
            f"Achieved:            {result.mean_ndcg_at_10:.4f}",
            f"Status:              {'PASS' if result.meets_g2_requirement else 'FAIL'}",
            "",
        ]

        if result.failed_cases > 0:
            lines.extend([
                "-" * 70,
                "FAILED CASES",
                "-" * 70,
            ])
            for r in result.per_case_results:
                if not r.passed:
                    lines.append(f"  - {r.query_text[:50]}... (NDCG={r.ndcg_at_10:.4f})")

        lines.append("=" * 70)

        return "\n".join(lines)
