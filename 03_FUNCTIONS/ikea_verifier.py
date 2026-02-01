"""
IKEA Verifier: Truth Boundary Enforcement
CEO-DIR-2026-COGNITIVE-ENGINES-001

Constitutional: ADR-017, ADR-020, ADR-021
EC Compliance: EC-022 (IKEA anti-hallucination)

Every claim in LLM responses must cite a Snippet ID from evidence_bundles.
Ungrounded claims result in NO_SIGNAL - speculative output is forbidden.

[C8] Claim Definition (Minimum Standard):
A "claim" is a sentence that contains ANY of:
1. NUMERIC: Numbers, percentages, prices (e.g., "increased 15%", "$42,000")
2. TEMPORAL: Date/time references (e.g., "in Q4 2025", "yesterday")
3. ENTITY_PREDICATE: Entity + verb predicate (e.g., "BTC increased", "Tesla reported")
4. CAUSAL: Causal language (e.g., "because", "due to", "caused by")

Each extracted claim MUST have at least one snippet_id for grounding.
Ungrounded claims -> ABORT -> NO_SIGNAL

Patches Applied:
- [P5] Improved sentence splitting (handles tickers, abbreviations)
- [P5] Improved grounding logic (ALL numbers and entities must be in evidence)
"""

import re
import logging
from typing import List, Tuple, Dict, Set, Optional
from uuid import UUID
from dataclasses import dataclass

from schemas.cognitive_engines import (
    EvidenceBundle,
    ExtractedClaim,
    ClaimType,
    IKEAVerificationResult
)
from schemas.signal_envelope import (
    SignalEnvelope,
    Claim,
    GroundingResult,
    IKEARefusal,
    validate_ikea_input
)

logger = logging.getLogger(__name__)


class IKEAViolation(Exception):
    """
    Raised when IKEA verification fails.

    When this exception is raised, the system MUST return NO_SIGNAL.
    Speculative Alpha output is forbidden per EC-022.
    """
    pass


class IKEAVerifier:
    """
    IKEA: Truth boundary enforcement.
    Every claim must cite a Snippet ID from evidence_bundles.

    Usage:
        verifier = IKEAVerifier()
        try:
            claims = verifier.enforce(response, evidence_bundle, evidence_texts)
            # Response is grounded, safe to output
        except IKEAViolation as e:
            # Return NO_SIGNAL
            return NO_SIGNAL

    The verify_grounding() method can be used for softer checking without exception.
    """

    # [C8] Regex patterns for claim extraction
    PATTERNS = {
        ClaimType.NUMERIC: [
            r'\d+\.?\d*\s*%',                # Percentages: "15%", "2.5%"
            r'\$\d+[\d,]*\.?\d*',             # USD prices: "$42,000", "$1.5"
            r'\d+[\d,]*\.?\d*\s*(USD|EUR|BTC|ETH|SOL)',  # Currency amounts
            r'(increased|decreased|rose|fell|gained|lost)\s+\d+',  # Change amounts
            r'\d+\.?\d*x',                   # Multiples: "2.5x", "10x"
            r'\d+\.?\d*\s*(billion|million|trillion)',  # Large numbers
            r'(strength|confidence|correlation|probability|score|ratio|factor|weight|alpha|beta|sharpe|volatility)\s*(of|is|was|:)?\s*-?\d+\.?\d*',  # Financial metrics with decimals
            r'-?\d+\.\d{2,}',                # Raw decimals with 2+ decimal places (0.229, 0.95000)
            r'(is|was|equals?|at|of)\s+-?\d+\.\d+',  # Decimals after verbs: "is 0.95", "at 0.15"
        ],
        ClaimType.TEMPORAL: [
            r'(in|during|since|until)\s+(Q[1-4]\s+)?\d{4}',  # "in Q4 2025"
            r'(yesterday|today|last\s+week|this\s+month|last\s+month)',  # Relative time
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # Date formats
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}',
            r'(YTD|year-to-date|month-over-month|MoM|YoY|year-over-year)',
        ],
        ClaimType.ENTITY_PREDICATE: [
            r'[A-Z][a-z]+\s+(increased|decreased|reported|announced|released|fell|rose|gained|lost|jumped|plunged)',
            r'(BTC|ETH|SOL|AAPL|TSLA|SPY|QQQ|NVDA|MSFT)\s+(is|was|has|had|will|would|could)',
            r'(Bitcoin|Ethereum|Tesla|Apple|Microsoft|Nvidia|Solana)\s+\w+ed',
            r'(The\s+)?[A-Z][a-z]+\s+(Fed|ECB|SEC|CFTC|Treasury)',
        ],
        ClaimType.CAUSAL: [
            r'(because|due\s+to|caused\s+by|as\s+a\s+result\s+of|owing\s+to)',
            r'(led\s+to|resulted\s+in|driven\s+by|attributed\s+to)',
            r'(if|when|then|therefore|thus|hence|consequently)',
            r'(correlation|causation|relationship\s+between)',
        ],
    }

    # Common abbreviations and patterns that should NOT be sentence breaks
    ABBREVIATIONS = {
        'Inc', 'Corp', 'Ltd', 'Co', 'Mr', 'Mrs', 'Ms', 'Dr', 'Prof',
        'vs', 'etc', 'approx', 'avg', 'est', 'max', 'min',
        'Jan', 'Feb', 'Mar', 'Apr', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
        'e.g', 'i.e', 'cf', 'viz'
    }

    # Common non-entity words to filter out
    COMMON_WORDS = {
        'The', 'This', 'That', 'These', 'Those', 'And', 'But', 'For', 'With',
        'From', 'Into', 'Through', 'During', 'Before', 'After', 'Above', 'Below',
        'Between', 'Under', 'Again', 'Further', 'Then', 'Once', 'Here', 'There',
        'When', 'Where', 'Why', 'How', 'All', 'Each', 'Few', 'More', 'Most',
        'Other', 'Some', 'Such', 'Only', 'Same', 'Than', 'Very', 'Just', 'Also'
    }

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the IKEA verifier.

        Args:
            strict_mode: If True, raise IKEAViolation on ungrounded claims.
                        If False, return result without exception.
        """
        self.strict_mode = strict_mode

    def extract_claims(self, response: str) -> List[ExtractedClaim]:
        """
        [C8] Extract claim units from LLM response.

        Uses regex + heuristics as baseline. Each sentence is checked
        for claim indicators (NUMERIC, TEMPORAL, ENTITY_PREDICATE, CAUSAL).

        Args:
            response: LLM response text.

        Returns:
            List of ExtractedClaim objects (ungrounded, snippet_ids empty).
        """
        sentences = self._split_sentences(response)
        claims = []

        for idx, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue

            claim_types = self._detect_claim_types(sentence)
            if claim_types:
                # This sentence contains a claim
                for claim_type in claim_types:
                    claims.append(ExtractedClaim(
                        claim_text=sentence,
                        claim_type=claim_type,
                        snippet_ids=[],  # Will be populated by grounding check
                        confidence=0.0,
                        grounded=False,
                        source_sentence_index=idx
                    ))

        return claims

    def _split_sentences(self, text: str) -> List[str]:
        """
        [P5] Improved sentence splitting.

        Simple `. ` split fails on tickers (AAPL.) and abbreviations (Inc.).
        Use multiple delimiters: `.\n`, `\n-`, `\n\n`, and sentence-final `.`
        with negative lookbehind for common patterns.

        Args:
            text: Text to split into sentences.

        Returns:
            List of sentence strings.
        """
        # First split on clear boundaries
        chunks = re.split(r'\.\n|\n-|\n\n|\n\*|\n\d+\.', text)

        # Build negative lookbehind pattern for abbreviations
        abbrev_pattern = '|'.join(re.escape(a) for a in self.ABBREVIATIONS)
        # Also don't split after tickers (2-5 uppercase letters)
        split_pattern = rf'(?<!{abbrev_pattern})(?<![A-Z]{{2,5}})\.\s+'

        sentences = []
        for chunk in chunks:
            if not chunk.strip():
                continue

            # Split on sentence-ending punctuation
            # But not after abbreviations or tickers
            try:
                parts = re.split(split_pattern, chunk)
            except re.error:
                # Fallback to simple split if regex fails
                parts = chunk.split('. ')

            for part in parts:
                part = part.strip()
                if part:
                    sentences.append(part)

        return sentences

    def _detect_claim_types(self, sentence: str) -> List[ClaimType]:
        """
        Detect which claim types are present in a sentence.

        Args:
            sentence: Sentence to analyze.

        Returns:
            List of ClaimType enums found in sentence.
        """
        detected = []
        for claim_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                try:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        detected.append(claim_type)
                        break  # One match per type is enough
                except re.error:
                    continue
        return detected

    def verify_grounding(
        self,
        response: str,
        evidence_bundle: EvidenceBundle,
        evidence_texts: Dict[str, str]
    ) -> IKEAVerificationResult:
        """
        Verify that all claims in response are grounded in evidence.

        Args:
            response: LLM response text.
            evidence_bundle: EvidenceBundle with snippet_ids.
            evidence_texts: Dict mapping snippet_id (str) to evidence text.

        Returns:
            IKEAVerificationResult with is_valid, claims, and statistics.
        """
        claims = self.extract_claims(response)

        if not claims:
            # No claims detected - response is pure commentary, OK
            return IKEAVerificationResult(
                is_valid=True,
                claims=[],
                grounded_claims_count=0,
                ungrounded_claims_count=0,
                grounding_ratio=1.0,
                violation_message=None
            )

        # Check each claim against evidence
        for claim in claims:
            grounding_snippets = []
            for snippet_id in evidence_bundle.snippet_ids:
                snippet_text = evidence_texts.get(str(snippet_id), "")
                if self._claim_matches_evidence(claim.claim_text, snippet_text):
                    grounding_snippets.append(snippet_id)

            if grounding_snippets:
                claim.snippet_ids = grounding_snippets
                claim.grounded = True
                claim.confidence = min(1.0, len(grounding_snippets) * 0.5)
            else:
                claim.grounded = False
                claim.confidence = 0.0

        # Calculate statistics
        grounded_count = sum(1 for c in claims if c.grounded)
        ungrounded_count = len(claims) - grounded_count
        grounding_ratio = grounded_count / len(claims) if claims else 1.0

        is_valid = ungrounded_count == 0

        # Build violation message if needed
        violation_message = None
        if not is_valid:
            ungrounded_texts = [c.claim_text[:50] for c in claims if not c.grounded]
            violation_message = (
                f"Hallucination detected. {ungrounded_count} ungrounded claim(s): "
                f"{ungrounded_texts}. System must return NO_SIGNAL."
            )

        return IKEAVerificationResult(
            is_valid=is_valid,
            claims=claims,
            grounded_claims_count=grounded_count,
            ungrounded_claims_count=ungrounded_count,
            grounding_ratio=grounding_ratio,
            violation_message=violation_message
        )

    def _claim_matches_evidence(self, claim: str, evidence: str) -> bool:
        """
        [P5] Improved grounding check.

        Old approach: 50% term overlap (too strict for short claims, too loose for long).
        New approach: All NUMERIC values and ENTITY names must appear in evidence.

        This gives fewer false aborts without letting hallucinations through.

        Args:
            claim: Claim text to verify.
            evidence: Evidence text to check against.

        Returns:
            True if claim is grounded in evidence.
        """
        if not evidence:
            return False

        evidence_lower = evidence.lower()
        evidence_text = evidence  # Keep original case for ticker matching

        # Extract NUMERIC values (numbers, percentages, prices)
        claim_numbers = set(re.findall(
            r'\d+\.?\d*%?|\$[\d,]+\.?\d*|\d+\.?\d*x',
            claim
        ))

        # Extract ENTITY names (tickers, proper nouns)
        claim_entities = set(re.findall(
            r'\b[A-Z]{2,5}\b|\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',
            claim
        ))
        # Filter out common words that aren't entities
        claim_entities = claim_entities - self.COMMON_WORDS

        # [P5] Grounding rule: ALL numbers and entities must be in evidence
        # Not percentage overlap, but presence check

        # Check numbers (must ALL be present)
        for num in claim_numbers:
            # Normalize number format for comparison
            num_clean = num.replace(',', '').replace('$', '').replace('%', '')
            # Check if number appears in evidence (with some flexibility)
            if (num_clean not in evidence and
                num not in evidence and
                num_clean not in evidence_lower):
                logger.debug(f"Number '{num}' not found in evidence")
                return False  # Number not grounded

        # Check entities (must ALL be present)
        for entity in claim_entities:
            # Check both exact match and case-insensitive
            if entity not in evidence_text and entity.lower() not in evidence_lower:
                logger.debug(f"Entity '{entity}' not found in evidence")
                return False  # Entity not grounded

        # If we get here, all critical terms are grounded
        # Return True if there were any terms to check, False if claim was empty
        return bool(claim_numbers or claim_entities)

    def enforce(
        self,
        response: str,
        evidence_bundle: EvidenceBundle,
        evidence_texts: Dict[str, str]
    ) -> List[ExtractedClaim]:
        """
        Enforce IKEA boundaries.

        If verification fails and strict_mode is True:
            raise IKEAViolation -> return NO_SIGNAL

        Args:
            response: LLM response text.
            evidence_bundle: EvidenceBundle with snippet_ids.
            evidence_texts: Dict mapping snippet_id (str) to evidence text.

        Returns:
            List of grounded ExtractedClaim objects.

        Raises:
            IKEAViolation: If verification fails in strict mode.
        """
        result = self.verify_grounding(response, evidence_bundle, evidence_texts)

        if not result.is_valid:
            if self.strict_mode:
                raise IKEAViolation(result.violation_message)
            else:
                logger.warning(f"IKEA violation (non-strict): {result.violation_message}")

        return result.claims

    def enforce_envelope(
        self,
        envelope: SignalEnvelope,
        evidence_texts: Dict[str, str]
    ) -> GroundingResult:
        """
        CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001: MANDATORY SignalEnvelope Enforcement

        IKEA must verify ONLY SignalEnvelope.draft_claims - no other text blob is permitted.
        This makes bypass IMPOSSIBLE BY CONSTRUCTION - not by policy, not by hope, but by code.

        Args:
            envelope: SignalEnvelope with draft_claims to verify
            evidence_texts: Dict mapping snippet_id (str) to evidence text

        Returns:
            GroundingResult with verification statistics

        Raises:
            IKEARefusal: If input is not a SignalEnvelope or missing draft_claims
        """
        # MANDATORY TYPE CHECK - bypassing impossible by construction
        validate_ikea_input(envelope)

        # Build pseudo EvidenceBundle for verification
        from schemas.cognitive_engines import EvidenceBundle
        pseudo_bundle = EvidenceBundle(
            bundle_id=envelope.bundle_id,
            query_text="",  # Not needed for verification
            query_embedding=[],  # Not needed
            snippet_ids=envelope.snippet_ids,
            rrf_fused_results=[],
            retrieval_mode="",
            defcon_level="",
            query_cost_usd=envelope.query_cost_usd,
            created_at=envelope.timestamp
        )

        # Verify each draft claim against evidence
        verified_claims = []
        ungrounded_claim_ids = []

        for claim in envelope.draft_claims:
            # Check if claim is grounded in evidence
            is_grounded = False
            grounding_snippets = []

            for snippet_id in envelope.snippet_ids:
                snippet_text = evidence_texts.get(str(snippet_id), "")
                if self._claim_matches_evidence(claim.claim_text, snippet_text):
                    grounding_snippets.append(snippet_id)
                    is_grounded = True

            if is_grounded:
                # Create verified claim with grounding info
                verified_claims.append(Claim.create(
                    claim_text=claim.claim_text,
                    claim_type=claim.claim_type,
                    snippet_ids=grounding_snippets,
                    grounded=True
                ))
            else:
                ungrounded_claim_ids.append(claim.claim_id)

        # Calculate grounding statistics
        total_claims = len(envelope.draft_claims)
        grounded_count = len(verified_claims)
        ungrounded_count = total_claims - grounded_count
        gcr = grounded_count / total_claims if total_claims > 0 else 1.0

        result = GroundingResult(
            total_claims=total_claims,
            grounded_count=grounded_count,
            ungrounded_count=ungrounded_count,
            gcr=gcr,
            ungrounded_claims=ungrounded_claim_ids
        )

        # In strict mode, raise violation if not fully grounded
        if self.strict_mode and not result.is_fully_grounded:
            raise IKEAViolation(
                f"Hallucination detected. {ungrounded_count} ungrounded claim(s). "
                f"GCR={gcr:.2%}. System must return NO_SIGNAL."
            )

        return result

    def get_grounding_report(
        self,
        response: str,
        evidence_bundle: EvidenceBundle,
        evidence_texts: Dict[str, str]
    ) -> str:
        """
        Generate a detailed grounding report for debugging.

        Args:
            response: LLM response text.
            evidence_bundle: EvidenceBundle with snippet_ids.
            evidence_texts: Dict mapping snippet_id (str) to evidence text.

        Returns:
            Formatted report string.
        """
        result = self.verify_grounding(response, evidence_bundle, evidence_texts)

        lines = [
            "=" * 60,
            "IKEA GROUNDING REPORT",
            "=" * 60,
            f"Status: {'PASS' if result.is_valid else 'FAIL'}",
            f"Claims extracted: {len(result.claims)}",
            f"Grounded: {result.grounded_claims_count}",
            f"Ungrounded: {result.ungrounded_claims_count}",
            f"Grounding ratio: {result.grounding_ratio:.2%}",
            "",
            "-" * 60,
            "CLAIMS DETAIL:",
            "-" * 60,
        ]

        for i, claim in enumerate(result.claims, 1):
            status = "[GROUNDED]" if claim.grounded else "[UNGROUNDED]"
            lines.append(f"\n{i}. {status} ({claim.claim_type.value})")
            lines.append(f"   Text: {claim.claim_text[:80]}...")
            if claim.snippet_ids:
                lines.append(f"   Citations: {len(claim.snippet_ids)} snippet(s)")

        if result.violation_message:
            lines.extend([
                "",
                "-" * 60,
                "VIOLATION:",
                result.violation_message,
            ])

        lines.append("=" * 60)

        return "\n".join(lines)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def check_ikea_compliance(
    response: str,
    evidence_bundle: EvidenceBundle,
    evidence_texts: Dict[str, str]
) -> bool:
    """
    Convenience function to check IKEA compliance.

    Args:
        response: LLM response text.
        evidence_bundle: EvidenceBundle with snippet_ids.
        evidence_texts: Dict mapping snippet_id (str) to evidence text.

    Returns:
        True if response is IKEA-compliant, False otherwise.
    """
    verifier = IKEAVerifier(strict_mode=False)
    result = verifier.verify_grounding(response, evidence_bundle, evidence_texts)
    return result.is_valid


def extract_and_ground_claims(
    response: str,
    evidence_bundle: EvidenceBundle,
    evidence_texts: Dict[str, str]
) -> Tuple[List[ExtractedClaim], bool]:
    """
    Convenience function to extract claims and check grounding.

    Args:
        response: LLM response text.
        evidence_bundle: EvidenceBundle with snippet_ids.
        evidence_texts: Dict mapping snippet_id (str) to evidence text.

    Returns:
        Tuple of (claims, all_grounded).
    """
    verifier = IKEAVerifier(strict_mode=False)
    result = verifier.verify_grounding(response, evidence_bundle, evidence_texts)
    return result.claims, result.is_valid
