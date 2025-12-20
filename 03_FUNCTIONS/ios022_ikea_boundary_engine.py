#!/usr/bin/env python3
"""
iOS-022 IKEA BOUNDARY ENGINE
==============================
EC-022: Knowledge Boundary Officer (IKEA)
Employment Contract: EC-022_2026_PRODUCTION

"Do I know this, or do I need to look it up?"

This engine implements the hallucination firewall for the FjordHQ ACI system.
It classifies queries as PARAMETRIC (internal knowledge), EXTERNAL_REQUIRED
(must retrieve), or HYBRID (combination).

CEO DIRECTIVE COMPLIANCE (2025-12-17):
- Mandate I:  ASRP State-Binding - all classifications embed state_snapshot_hash
- Mandate V:  Fail-Safe Default - uncertain/failed -> EXTERNAL_REQUIRED
- Mandate VIII: Role Isolation - writes only to fhq_meta (Evidence, not Truth)

Authority: ADR-021 (Cognitive Engine Architecture), EC-022
Parent Executive: VEGA (Verification & Governance Authority)
Classification: Tier-2 Cognitive Engine

References:
- "SEAKR: Self-Aware Knowledge Retrieval" (NeurIPS 2024)
- EC-022 Employment Contract Section 6 (Volatility Flagging)
"""

import os
import re
import uuid
import hashlib
import logging
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor, Json

logging.basicConfig(
    level=logging.INFO,
    format='[IKEA] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# MANDATE VIII: Schema Boundary Enforcement
# =============================================================================

ALLOWED_WRITE_SCHEMAS = ['fhq_meta', 'fhq_optimization']


class MITQuadViolation(Exception):
    """Raised when cognitive engine attempts to write to canonical schemas."""
    pass


def validated_insert(schema: str, table: str):
    """Decorator to enforce MIT Quad schema boundaries."""
    if schema not in ALLOWED_WRITE_SCHEMAS:
        raise MITQuadViolation(
            f"IKEA cannot write to {schema}.{table} - only Evidence schemas allowed"
        )


# =============================================================================
# CLASSIFICATION TYPES
# =============================================================================

class Classification(Enum):
    """Knowledge boundary classification types."""
    PARAMETRIC = "PARAMETRIC"           # Can answer from internal knowledge
    EXTERNAL_REQUIRED = "EXTERNAL_REQUIRED"  # Must retrieve externally
    HYBRID = "HYBRID"                   # Combination of both


class VolatilityClass(Enum):
    """Data volatility classification (EC-022 Section 6)."""
    EXTREME = "EXTREME"   # Real-time (prices, order books)
    HIGH = "HIGH"         # Daily-Quarterly (earnings, GDP)
    MEDIUM = "MEDIUM"     # Monthly-Yearly (macro indicators)
    LOW = "LOW"           # Yearly+ (sector definitions)
    STATIC = "STATIC"     # Never changes (formulas, definitions)


# =============================================================================
# VOLATILITY RULES (per EC-022 Employment Contract)
# =============================================================================

VOLATILITY_RULES: Dict[str, VolatilityClass] = {
    # EXTREME - Real-time data (always EXTERNAL_REQUIRED)
    'price': VolatilityClass.EXTREME,
    'stock price': VolatilityClass.EXTREME,
    'current price': VolatilityClass.EXTREME,
    'market cap': VolatilityClass.EXTREME,
    'volume': VolatilityClass.EXTREME,
    'bid': VolatilityClass.EXTREME,
    'ask': VolatilityClass.EXTREME,
    'order book': VolatilityClass.EXTREME,
    'live': VolatilityClass.EXTREME,
    'now': VolatilityClass.EXTREME,
    'today': VolatilityClass.EXTREME,
    'current': VolatilityClass.EXTREME,

    # HIGH - Quarterly data
    'earnings': VolatilityClass.HIGH,
    'revenue': VolatilityClass.HIGH,
    'eps': VolatilityClass.HIGH,
    'quarterly': VolatilityClass.HIGH,
    'q1': VolatilityClass.HIGH,
    'q2': VolatilityClass.HIGH,
    'q3': VolatilityClass.HIGH,
    'q4': VolatilityClass.HIGH,
    'guidance': VolatilityClass.HIGH,
    'forecast': VolatilityClass.HIGH,

    # MEDIUM - Monthly/Annual
    'gdp': VolatilityClass.MEDIUM,
    'inflation': VolatilityClass.MEDIUM,
    'cpi': VolatilityClass.MEDIUM,
    'unemployment': VolatilityClass.MEDIUM,
    'fed': VolatilityClass.MEDIUM,
    'interest rate': VolatilityClass.MEDIUM,
    'annual': VolatilityClass.MEDIUM,

    # LOW - Stable but can change
    'sector': VolatilityClass.LOW,
    'industry': VolatilityClass.LOW,
    'classification': VolatilityClass.LOW,

    # STATIC - Never changes
    'formula': VolatilityClass.STATIC,
    'definition': VolatilityClass.STATIC,
    'what is': VolatilityClass.STATIC,
    'how to calculate': VolatilityClass.STATIC,
    'sharpe ratio': VolatilityClass.STATIC,
    'ebitda': VolatilityClass.STATIC,
    'p/e ratio': VolatilityClass.STATIC,
}

# Patterns that indicate entity-specific current data
ENTITY_PATTERNS = [
    r"(?:what is|what's)\s+\w+(?:'s)?\s+(?:current|latest|today)",
    r"\b(?:AAPL|MSFT|GOOGL|AMZN|NVDA|TSLA|META|BTC|ETH)\b.*(?:price|earnings|revenue)",
    r"(?:stock|share)\s+price\s+of",
    r"market\s+cap\s+of",
    r"\$\d+(?:\.\d+)?",  # Dollar amounts suggest current data
]


# =============================================================================
# PARAMETRIC KNOWLEDGE PATTERNS
# =============================================================================

PARAMETRIC_PATTERNS = [
    # Definitions and formulas
    r"^what\s+is\s+(?:a\s+)?(?:the\s+)?(?:definition\s+of\s+)?(?:sharpe|sortino|calmar|treynor)",
    r"^how\s+(?:to|do\s+you)\s+calculate",
    r"^(?:what|explain)\s+(?:is|are)\s+(?:the\s+)?(?:formula|equation)",
    r"^define\s+",

    # Financial concepts (stable)
    r"^what\s+(?:is|are)\s+(?:the\s+)?(?:major|main)\s+(?:sectors|industries|exchanges)",
    r"^(?:list|name)\s+(?:the\s+)?(?:central\s+banks|exchanges|indices)",

    # Mathematical/Statistical concepts
    r"^what\s+(?:is|are)\s+(?:standard\s+deviation|variance|correlation|covariance)",
    r"^how\s+(?:does|do)\s+(?:regression|GARCH|HMM|ARIMA)\s+work",
]


@dataclass
class ClassificationResult:
    """Result of IKEA knowledge boundary classification."""
    classification: Classification
    confidence: float
    volatility_class: Optional[VolatilityClass]
    query_hash: str
    state_snapshot_hash: str
    state_timestamp: datetime
    decision_rationale: str
    claims_extracted: List[str] = field(default_factory=list)
    evidence_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'classification': self.classification.value,
            'confidence': self.confidence,
            'volatility_class': self.volatility_class.value if self.volatility_class else None,
            'query_hash': self.query_hash,
            'state_snapshot_hash': self.state_snapshot_hash,
            'state_timestamp': self.state_timestamp.isoformat(),
            'decision_rationale': self.decision_rationale,
            'claims_extracted': self.claims_extracted,
            'evidence_required': self.evidence_required
        }


class IKEABoundaryEngine:
    """
    IKEA Knowledge Boundary Engine - The Hallucination Firewall.

    Core Principle (Mandate V): Fail-Safe Default
    - If uncertain -> EXTERNAL_REQUIRED
    - If error -> EXTERNAL_REQUIRED
    - Burden of proof: Must PROVE it's parametric, not assume it

    Constitutional Constraint: "Facts without sources are illegal"
    """

    # Confidence thresholds (Mandate V: Burden of Proof Inversion)
    PARAMETRIC_CONFIDENCE_THRESHOLD = 0.85  # High bar to prove internal knowledge
    HYBRID_CONFIDENCE_THRESHOLD = 0.70      # Medium bar for hybrid
    FAIL_SAFE_THRESHOLD = 0.70              # Below this -> EXTERNAL_REQUIRED

    def __init__(self):
        self.conn = None
        self._classification_count = 0
        self._external_required_count = 0

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'),
            port=int(os.getenv('PGPORT', '54322')),
            database=os.getenv('PGDATABASE', 'postgres'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', 'postgres')
        )
        logger.info("IKEA Boundary Engine connected to database")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("IKEA Boundary Engine connection closed")

    # =========================================================================
    # MANDATE I: ASRP State-Binding
    # =========================================================================

    def _get_current_asrp_state(self) -> Tuple[str, datetime]:
        """
        Retrieve current atomic state snapshot hash and timestamp.
        Per ADR-018: Every artifact must be bound to market state.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT state_snapshot_hash, vector_timestamp
                    FROM fhq_meta.aci_state_snapshot_log
                    WHERE is_atomic = true
                    ORDER BY created_at DESC LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    return (row[0], row[1])
        except Exception as e:
            logger.warning(f"Could not retrieve ASRP state: {e}")

        # Fallback: generate emergency state hash
        emergency_hash = hashlib.sha256(
            f"EMERGENCY_STATE_{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:32]
        return (emergency_hash, datetime.now(timezone.utc))

    # =========================================================================
    # CORE CLASSIFICATION LOGIC
    # =========================================================================

    def classify_query(self, query: str) -> ClassificationResult:
        """
        Classify a query's knowledge boundary.

        MANDATE V: Fail-Safe Default
        - Any error -> EXTERNAL_REQUIRED
        - Low confidence -> EXTERNAL_REQUIRED
        - Burden of proof lies on proving PARAMETRIC

        Args:
            query: The query to classify

        Returns:
            ClassificationResult with classification, confidence, and state binding
        """
        self._classification_count += 1
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:32]
        state_hash, state_timestamp = self._get_current_asrp_state()

        try:
            # Internal classification logic
            classification, confidence, volatility, rationale = self._internal_classify(query)

            # MANDATE V: Fail-Safe Default
            if confidence < self.FAIL_SAFE_THRESHOLD:
                logger.warning(
                    f"IKEA: Low confidence ({confidence:.2f}), "
                    f"defaulting to EXTERNAL_REQUIRED"
                )
                classification = Classification.EXTERNAL_REQUIRED
                rationale = f"Confidence {confidence:.2f} below threshold {self.FAIL_SAFE_THRESHOLD}. Fail-safe activated."
                self._external_required_count += 1

            # MANDATE V: Burden of Proof Inversion
            if classification == Classification.PARAMETRIC and confidence < self.PARAMETRIC_CONFIDENCE_THRESHOLD:
                logger.info(
                    f"IKEA: PARAMETRIC confidence ({confidence:.2f}) below "
                    f"threshold ({self.PARAMETRIC_CONFIDENCE_THRESHOLD}), "
                    f"upgrading to EXTERNAL_REQUIRED"
                )
                classification = Classification.EXTERNAL_REQUIRED
                rationale = f"Burden of proof not met. Need {self.PARAMETRIC_CONFIDENCE_THRESHOLD} confidence for PARAMETRIC."
                self._external_required_count += 1

            result = ClassificationResult(
                classification=classification,
                confidence=confidence,
                volatility_class=volatility,
                query_hash=query_hash,
                state_snapshot_hash=state_hash,
                state_timestamp=state_timestamp,
                decision_rationale=rationale,
                claims_extracted=self._extract_factual_claims(query),
                evidence_required=(classification != Classification.PARAMETRIC)
            )

            # Log classification (MANDATE VIII: only to fhq_meta)
            self._log_classification(result, query)

            return result

        except Exception as e:
            # MANDATE V: Any failure defaults to maximum safety
            logger.error(f"IKEA classification failed: {e}")
            self._external_required_count += 1

            return ClassificationResult(
                classification=Classification.EXTERNAL_REQUIRED,
                confidence=0.0,
                volatility_class=VolatilityClass.EXTREME,
                query_hash=query_hash,
                state_snapshot_hash=state_hash,
                state_timestamp=state_timestamp,
                decision_rationale=f"Classification error: {e}. Fail-safe activated.",
                claims_extracted=[query],  # Treat entire query as claim needing verification
                evidence_required=True
            )

    def _internal_classify(
        self, query: str
    ) -> Tuple[Classification, float, Optional[VolatilityClass], str]:
        """
        Internal classification logic.

        Returns:
            Tuple of (Classification, confidence, volatility_class, rationale)
        """
        query_lower = query.lower().strip()

        # Step 1: Check volatility indicators (most restrictive first)
        volatility = self._detect_volatility(query_lower)

        if volatility in (VolatilityClass.EXTREME, VolatilityClass.HIGH):
            return (
                Classification.EXTERNAL_REQUIRED,
                0.95,
                volatility,
                f"Volatility class {volatility.value} requires external retrieval"
            )

        # Step 2: Check for entity-specific patterns
        for pattern in ENTITY_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return (
                    Classification.EXTERNAL_REQUIRED,
                    0.90,
                    VolatilityClass.HIGH,
                    f"Entity-specific pattern detected: requires current data"
                )

        # Step 3: Check for pure parametric patterns
        for pattern in PARAMETRIC_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return (
                    Classification.PARAMETRIC,
                    0.90,
                    VolatilityClass.STATIC,
                    f"Matches parametric pattern: stable conceptual knowledge"
                )

        # Step 4: Analyze content for hybrid indicators
        if volatility == VolatilityClass.MEDIUM:
            return (
                Classification.HYBRID,
                0.75,
                volatility,
                f"Medium volatility: combine internal concepts with external validation"
            )

        if volatility == VolatilityClass.LOW:
            return (
                Classification.HYBRID,
                0.80,
                volatility,
                f"Low volatility: mostly internal, verify currency"
            )

        if volatility == VolatilityClass.STATIC:
            return (
                Classification.PARAMETRIC,
                0.85,
                volatility,
                f"Static content: pure conceptual/definitional"
            )

        # Step 5: Default case - uncertain, lean toward safety
        return (
            Classification.EXTERNAL_REQUIRED,
            0.60,  # Low confidence triggers fail-safe
            None,
            "Unable to determine classification with confidence. Defaulting to EXTERNAL_REQUIRED."
        )

    def _detect_volatility(self, query_lower: str) -> VolatilityClass:
        """Detect data volatility class from query content."""
        for keyword, volatility in VOLATILITY_RULES.items():
            if keyword in query_lower:
                return volatility
        return VolatilityClass.MEDIUM  # Default to medium if unclear

    def _extract_factual_claims(self, text: str) -> List[str]:
        """
        Extract factual claims from text that need verification.

        MANDATE V: If extraction fails, treat entire text as claim.
        """
        try:
            claims = []

            # Split into sentences
            sentences = re.split(r'[.!?]', text)

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                # Look for factual claim patterns
                if any(indicator in sentence.lower() for indicator in [
                    'is', 'was', 'are', 'were', 'has', 'have', 'had',
                    'will be', 'should be', 'equals', 'amounts to'
                ]):
                    claims.append(sentence)

            # If no claims extracted, treat entire text as claim
            if not claims:
                claims = [text]

            return claims

        except Exception as e:
            logger.warning(f"Claim extraction failed: {e}")
            # Fail-safe: entire text needs verification
            return [text]

    # =========================================================================
    # MANDATE VIII: Logging to fhq_meta only
    # =========================================================================

    def _log_classification(self, result: ClassificationResult, original_query: str):
        """
        Log classification to fhq_meta.knowledge_boundary_log.

        MANDATE VIII: Cognitive engine outputs are Evidence, not Truth.
        Only writes to fhq_meta schema.
        """
        # Validate schema boundary
        validated_insert('fhq_meta', 'knowledge_boundary_log')

        sql = """
            INSERT INTO fhq_meta.knowledge_boundary_log (
                boundary_id,
                query_hash,
                classification,
                confidence_score,
                volatility_class,
                state_snapshot_hash,
                state_timestamp,
                decision_rationale,
                claims_extracted,
                evidence_required,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    str(uuid.uuid4()),
                    result.query_hash,
                    result.classification.value,
                    result.confidence,
                    result.volatility_class.value if result.volatility_class else None,
                    result.state_snapshot_hash,
                    result.state_timestamp,
                    result.decision_rationale,
                    Json(result.claims_extracted),
                    result.evidence_required
                ))
            self.conn.commit()
            logger.debug(f"Classification logged: {result.classification.value}")
        except Exception as e:
            logger.warning(f"Failed to log classification: {e}")
            # Don't raise - logging failure shouldn't block classification

    # =========================================================================
    # PUBLIC API FOR INTEGRATION
    # =========================================================================

    def check_query(self, query: str) -> Tuple[str, float]:
        """
        Simplified API for cognitive loop integration.

        Returns:
            Tuple of (classification_string, confidence)
        """
        result = self.classify_query(query)
        return (result.classification.value, result.confidence)

    def must_retrieve(self, query: str) -> bool:
        """
        Check if query requires external retrieval.

        Returns True if classification is EXTERNAL_REQUIRED or HYBRID.
        """
        result = self.classify_query(query)
        return result.classification in (
            Classification.EXTERNAL_REQUIRED,
            Classification.HYBRID
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get classification statistics."""
        return {
            'total_classifications': self._classification_count,
            'external_required_count': self._external_required_count,
            'external_required_rate': (
                self._external_required_count / max(self._classification_count, 1)
            ),
            'fail_safe_threshold': self.FAIL_SAFE_THRESHOLD,
            'parametric_threshold': self.PARAMETRIC_CONFIDENCE_THRESHOLD
        }

    def check_volatility_class(self, data_type: str) -> str:
        """
        Check volatility class for a data type.

        Returns volatility class string.
        """
        volatility = self._detect_volatility(data_type.lower())
        return volatility.value


# =============================================================================
# TESTING
# =============================================================================

def test_ikea_engine():
    """Test the IKEA boundary engine."""
    logger.info("=" * 60)
    logger.info("IKEA BOUNDARY ENGINE TEST")
    logger.info("=" * 60)

    engine = IKEABoundaryEngine()
    engine.connect()

    test_queries = [
        # Should be EXTERNAL_REQUIRED (prices, current data)
        ("What is Apple's current stock price?", Classification.EXTERNAL_REQUIRED),
        ("What is the market cap of NVDA?", Classification.EXTERNAL_REQUIRED),
        ("What were Tesla's Q3 2025 earnings?", Classification.EXTERNAL_REQUIRED),

        # Should be PARAMETRIC (stable knowledge)
        ("What is the Sharpe ratio?", Classification.PARAMETRIC),
        ("How do you calculate EBITDA?", Classification.PARAMETRIC),
        ("Define standard deviation", Classification.PARAMETRIC),

        # Should be HYBRID (mixed)
        ("Is the current VIX above historical average?", Classification.HYBRID),
        ("What is the Fed's current interest rate policy?", Classification.HYBRID),
    ]

    for query, expected in test_queries:
        result = engine.classify_query(query)
        status = "PASS" if result.classification == expected else "FAIL"
        logger.info(f"\n[{status}] Query: {query[:50]}...")
        logger.info(f"  Expected: {expected.value}")
        logger.info(f"  Got: {result.classification.value} (confidence: {result.confidence:.2f})")
        logger.info(f"  Rationale: {result.decision_rationale}")

    stats = engine.get_statistics()
    logger.info(f"\nStatistics: {stats}")

    engine.close()


if __name__ == "__main__":
    test_ikea_engine()
