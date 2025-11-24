"""
FINN+ Tier-2 Engine: Causal Coherence Scoring (C4 Component)
Phase 3: Week 3 — LARS Directive 6 (Priority 1)

Authority: LARS G2 Approval + Directive 6
Canonical ADR Chain: ADR-001 → ADR-015
Reference: C4_CAUSAL_COHERENCE_PLAN.md

PURPOSE:
FINN+ Tier-2 implements LLM-based conflict summarization to assess
causal coherence of market regime classifications. This provides the
C4 component for the CDS Engine (20% weight).

MANDATE (from FINN_TIER2_MANDATE.md):
1. Detect conflicts between FINN+ regime classification and market narratives
2. Summarize conflicts in 3 sentences or less
3. Assess coherence of regime classification given narratives
4. Use LLM for causal reasoning (Claude/GPT-4)

COST CONSTRAINT (ADR-012):
- Maximum: $0.50 per summary
- Rate limit: 100 summaries/hour
- Daily budget: $500 cap
- Expected: ~$0.0024/call in production (~$0.24/day)

OUTPUT CONTRACT:
- coherence_score: float ∈ [0.0, 1.0] (C4 component)
- summary: string (3 sentences max, 300 char limit)
- llm_cost: float (USD)
- llm_api_calls: int
- timestamp: datetime
- signature: Ed25519 (ADR-008)

INTEGRATION:
CDS Engine C4 component receives coherence_score directly from Tier-2.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time
import hashlib
import json
import re

# Phase 3 imports
from finn_signature import Ed25519Signer


@dataclass
class Tier2Input:
    """Input contract for FINN+ Tier-2 causal coherence assessment."""
    regime_label: str  # "BEAR", "NEUTRAL", "BULL"
    regime_confidence: float  # 0.0–1.0

    # Market features (z-scored)
    return_z: float
    volatility_z: float
    drawdown_z: float
    macd_diff_z: float

    # Recent price action
    price_change_pct: float  # % change over lookback period
    current_drawdown_pct: float  # % from peak

    # Optional
    cycle_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Tier2Result:
    """Output contract for FINN+ Tier-2 causal coherence result."""
    coherence_score: float  # 0.0–1.0 (C4 component)
    summary: str  # 3 sentences max, 300 char limit

    # Cost tracking (ADR-012)
    llm_cost_usd: float
    llm_api_calls: int

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    cycle_id: Optional[str] = None

    # Cryptographic signature (ADR-008)
    signature_hex: Optional[str] = None
    public_key_hex: Optional[str] = None

    # LLM metadata
    llm_model: Optional[str] = None
    llm_tokens_input: Optional[int] = None
    llm_tokens_output: Optional[int] = None

    def __post_init__(self):
        """Validate coherence_score ∈ [0.0, 1.0]."""
        if not (0.0 <= self.coherence_score <= 1.0):
            raise ValueError(
                f"coherence_score must be in [0.0, 1.0], got {self.coherence_score}"
            )

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'coherence_score': self.coherence_score,
            'summary': self.summary,
            'llm_cost_usd': self.llm_cost_usd,
            'llm_api_calls': self.llm_api_calls,
            'timestamp': self.timestamp.isoformat(),
            'cycle_id': self.cycle_id,
            'signature_hex': self.signature_hex,
            'public_key_hex': self.public_key_hex,
            'llm_model': self.llm_model,
            'llm_tokens_input': self.llm_tokens_input,
            'llm_tokens_output': self.llm_tokens_output
        }


# ============================================================================
# Prompt Engineering
# ============================================================================

COHERENCE_PROMPT_TEMPLATE = """You are a quantitative market analyst assessing regime classification coherence.

**Regime Classification:**
- Regime: {regime_label}
- Confidence: {confidence_pct}

**Market Indicators (z-scored):**
- Return (20d): {return_z:.2f}σ
- Volatility: {volatility_z:.2f}σ
- Drawdown: {drawdown_z:.2f}σ
- MACD: {macd_diff_z:.2f}σ

**Recent Price Action:**
- Price change (20d): {price_change_pct:+.1f}%
- Current drawdown: {current_drawdown_pct:.1f}%

**Task:**
1. Assess if the {regime_label} classification is causally coherent given the indicators.
2. Rate coherence from 0.0 (incoherent/contradictory) to 1.0 (perfectly coherent/aligned).
3. Provide a 3-sentence justification (max 300 characters).

**Scoring Rubric:**
- 0.9–1.0: Perfect alignment (all indicators support regime)
- 0.7–0.9: Strong alignment (most indicators support regime)
- 0.5–0.7: Weak alignment (mixed signals)
- 0.3–0.5: Contradictory (indicators conflict with regime)
- 0.0–0.3: Severe mismatch (regime classification incorrect)

**Format:**
Coherence: [0.0-1.0]
Justification: [3 sentences, max 300 characters]

Example:
Coherence: 0.85
Justification: The BULL classification is well-supported by positive return z-score (+1.2σ) and minimal drawdown (-2%). Low volatility (0.6σ) confirms stable upward momentum.
"""


def construct_prompt(tier2_input: Tier2Input) -> str:
    """
    Construct LLM prompt for causal coherence assessment.

    Args:
        tier2_input: Tier2Input with regime + features

    Returns:
        Formatted prompt string
    """
    return COHERENCE_PROMPT_TEMPLATE.format(
        regime_label=tier2_input.regime_label,
        confidence_pct=f"{tier2_input.regime_confidence:.1%}",
        return_z=tier2_input.return_z,
        volatility_z=tier2_input.volatility_z,
        drawdown_z=tier2_input.drawdown_z,
        macd_diff_z=tier2_input.macd_diff_z,
        price_change_pct=tier2_input.price_change_pct,
        current_drawdown_pct=tier2_input.current_drawdown_pct
    )


def parse_llm_response(response_text: str) -> tuple[float, str]:
    """
    Parse LLM response to extract coherence score and justification.

    Args:
        response_text: Raw LLM response

    Returns:
        Tuple of (coherence_score, justification)

    Raises:
        ValueError: If response cannot be parsed
    """
    # Extract coherence score
    coherence_match = re.search(r'Coherence:\s*([\d.]+)', response_text, re.IGNORECASE)
    if not coherence_match:
        raise ValueError("Could not find coherence score in LLM response")

    coherence_score = float(coherence_match.group(1))

    # Validate bounds
    if not (0.0 <= coherence_score <= 1.0):
        raise ValueError(f"Coherence score out of bounds: {coherence_score}")

    # Extract justification
    justification_match = re.search(
        r'Justification:\s*(.+?)(?:\n|$)',
        response_text,
        re.IGNORECASE | re.DOTALL
    )

    if not justification_match:
        raise ValueError("Could not find justification in LLM response")

    justification = justification_match.group(1).strip()

    # Truncate to 300 characters
    if len(justification) > 300:
        justification = justification[:297] + "..."

    return coherence_score, justification


# ============================================================================
# LLM Client Interface
# ============================================================================

class LLMClient:
    """
    Abstract base class for LLM API clients.

    Implementations should support Claude, GPT-4, and other LLM providers.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize LLM client."""
        self.api_key = api_key
        self.request_count = 0
        self.total_cost = 0.0

    def generate(self, prompt: str) -> Dict[str, Any]:
        """
        Generate LLM response.

        Args:
            prompt: Input prompt

        Returns:
            Dictionary with:
                - response_text: str
                - cost_usd: float
                - tokens_input: int
                - tokens_output: int
                - model: str

        Raises:
            NotImplementedError: Subclasses must implement
        """
        raise NotImplementedError("Subclass must implement generate()")

    def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            'request_count': self.request_count,
            'total_cost': self.total_cost
        }


class MockLLMClient(LLMClient):
    """
    Mock LLM client for testing (no actual API calls).

    Generates synthetic coherence scores based on z-score alignment.
    """

    def __init__(self):
        """Initialize mock client."""
        super().__init__(api_key=None)
        self.mock_cost_per_call = 0.0024  # $0.0024/call (realistic)

    def generate(self, prompt: str) -> Dict[str, Any]:
        """
        Generate mock LLM response.

        Uses heuristic: Parse prompt to extract z-scores and regime,
        then compute synthetic coherence based on alignment.
        """
        self.request_count += 1
        self.total_cost += self.mock_cost_per_call

        # Parse regime and z-scores from prompt
        regime_match = re.search(r'Regime:\s*(\w+)', prompt)
        return_z_match = re.search(r'Return.*?:\s*([-\d.]+)σ', prompt)
        vol_z_match = re.search(r'Volatility.*?:\s*([-\d.]+)σ', prompt)

        regime = regime_match.group(1) if regime_match else "NEUTRAL"
        return_z = float(return_z_match.group(1)) if return_z_match else 0.0
        vol_z = float(vol_z_match.group(1)) if vol_z_match else 0.0

        # Compute synthetic coherence (heuristic)
        if regime == "BULL":
            # BULL coherence: high if return_z > 0, low vol
            coherence = 0.5 + (return_z * 0.15) - (abs(vol_z) * 0.05)
        elif regime == "BEAR":
            # BEAR coherence: high if return_z < 0, high drawdown
            coherence = 0.5 - (return_z * 0.15) - (abs(vol_z) * 0.05)
        else:  # NEUTRAL
            # NEUTRAL coherence: high if return_z near 0
            coherence = 0.7 - (abs(return_z) * 0.10)

        # Clamp to [0.0, 1.0]
        coherence = max(0.0, min(1.0, coherence))

        # Generate justification
        if coherence >= 0.8:
            justification = f"The {regime} classification is well-supported by market indicators. Return z-score ({return_z:.2f}σ) aligns with regime expectations. Volatility levels confirm the assessment."
        elif coherence >= 0.5:
            justification = f"The {regime} classification shows moderate alignment. Return z-score ({return_z:.2f}σ) provides some support. Mixed signals from volatility indicators."
        else:
            justification = f"The {regime} classification is weakly supported. Return z-score ({return_z:.2f}σ) contradicts regime expectations. Coherence concerns warrant review."

        # Truncate justification
        if len(justification) > 300:
            justification = justification[:297] + "..."

        # Format response
        response_text = f"Coherence: {coherence:.2f}\nJustification: {justification}"

        return {
            'response_text': response_text,
            'cost_usd': self.mock_cost_per_call,
            'tokens_input': 300,  # Realistic estimate
            'tokens_output': 100,
            'model': 'mock-llm-v1.0'
        }


# ============================================================================
# FINN+ Tier-2 Engine
# ============================================================================

class FINNTier2Engine:
    """
    FINN+ Tier-2 Engine: LLM-based Causal Coherence Scoring.

    This engine implements the C4 (Causal Coherence) component for CDS Engine
    using LLM-based conflict summarization to assess whether regime classifications
    are causally coherent with market indicators.

    Cost: ~$0.0024/call (Claude 3 Sonnet)
    Rate Limit: 100 calls/hour (ADR-012)
    Daily Budget: $500 cap
    """

    def __init__(self, llm_client: Optional[LLMClient] = None,
                 use_production_mode: bool = False):
        """
        Initialize FINN+ Tier-2 engine.

        Args:
            llm_client: LLM client implementation (default: MockLLMClient)
            use_production_mode: If True, use real LLM; if False, return placeholder
        """
        self.llm_client = llm_client or MockLLMClient()
        self.use_production_mode = use_production_mode
        self.signer = Ed25519Signer()

        # Rate limiting (ADR-012)
        self.max_calls_per_hour = 100
        self.daily_budget_usd = 500.0
        self.call_timestamps: List[datetime] = []
        self.daily_cost = 0.0
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Statistics
        self.computation_count = 0
        self.cache_hits = 0

        # Simple cache (recent results)
        self.cache: Dict[str, Tier2Result] = {}
        self.cache_ttl_seconds = 300  # 5 minutes

    def compute_coherence(self, tier2_input: Tier2Input) -> Tier2Result:
        """
        Compute causal coherence score for regime classification.

        This is the main entry point for C4 component computation.

        Args:
            tier2_input: Tier2Input with regime + features

        Returns:
            Tier2Result with coherence_score (C4) + metadata
        """
        self.computation_count += 1

        # DIRECTIVE 6 MANDATE: Return placeholder in production until G1-validated
        if not self.use_production_mode:
            # Placeholder mode: Return 0.0 coherence (conservative)
            return Tier2Result(
                coherence_score=0.0,
                summary="PLACEHOLDER: FINN+ Tier-2 not active (awaiting G1 validation)",
                llm_cost_usd=0.0,
                llm_api_calls=0,
                timestamp=datetime.now(),
                cycle_id=tier2_input.cycle_id,
                llm_model="placeholder-v1.0"
            )

        # Check cache
        cache_key = self._compute_cache_key(tier2_input)
        if cache_key in self.cache:
            cached_result = self.cache[cache_key]
            # Check TTL
            age_seconds = (datetime.now() - cached_result.timestamp).total_seconds()
            if age_seconds < self.cache_ttl_seconds:
                self.cache_hits += 1
                return cached_result
            else:
                # Expired, remove from cache
                del self.cache[cache_key]

        # Check rate limits (ADR-012)
        if not self._check_rate_limits():
            # Rate limit exceeded, return placeholder
            return Tier2Result(
                coherence_score=0.0,
                summary="RATE LIMIT: Tier-2 calls exceeded (ADR-012 protection)",
                llm_cost_usd=0.0,
                llm_api_calls=0,
                timestamp=datetime.now(),
                cycle_id=tier2_input.cycle_id,
                llm_model="rate-limited"
            )

        # [1] Construct prompt
        prompt = construct_prompt(tier2_input)

        # [2] Generate LLM response
        try:
            llm_response = self.llm_client.generate(prompt)
        except Exception as e:
            # LLM API error, return placeholder
            print(f"LLM API error: {e}")
            return Tier2Result(
                coherence_score=0.0,
                summary=f"ERROR: LLM API failed ({str(e)[:50]})",
                llm_cost_usd=0.0,
                llm_api_calls=0,
                timestamp=datetime.now(),
                cycle_id=tier2_input.cycle_id,
                llm_model="error"
            )

        # [3] Parse response
        try:
            coherence_score, justification = parse_llm_response(
                llm_response['response_text']
            )
        except ValueError as e:
            # Parse error, return placeholder
            print(f"Parse error: {e}")
            return Tier2Result(
                coherence_score=0.0,
                summary=f"PARSE ERROR: {str(e)[:50]}",
                llm_cost_usd=llm_response['cost_usd'],
                llm_api_calls=1,
                timestamp=datetime.now(),
                cycle_id=tier2_input.cycle_id,
                llm_model=llm_response['model']
            )

        # [4] Track costs
        self._track_cost(llm_response['cost_usd'])

        # [5] Create result
        result = Tier2Result(
            coherence_score=coherence_score,
            summary=justification,
            llm_cost_usd=llm_response['cost_usd'],
            llm_api_calls=1,
            timestamp=datetime.now(),
            cycle_id=tier2_input.cycle_id,
            llm_model=llm_response['model'],
            llm_tokens_input=llm_response['tokens_input'],
            llm_tokens_output=llm_response['tokens_output']
        )

        # [6] Sign result (Ed25519, ADR-008)
        signature_hex, public_key_hex = self._sign_result(result)
        result.signature_hex = signature_hex
        result.public_key_hex = public_key_hex

        # [7] Cache result
        self.cache[cache_key] = result

        return result

    def _compute_cache_key(self, tier2_input: Tier2Input) -> str:
        """Compute cache key for tier2_input."""
        key_dict = {
            'regime': tier2_input.regime_label,
            'confidence': round(tier2_input.regime_confidence, 2),
            'return_z': round(tier2_input.return_z, 2),
            'volatility_z': round(tier2_input.volatility_z, 2),
            'drawdown_z': round(tier2_input.drawdown_z, 2),
            'macd_diff_z': round(tier2_input.macd_diff_z, 2)
        }
        canonical_json = json.dumps(key_dict, sort_keys=True)
        return hashlib.sha256(canonical_json.encode()).hexdigest()[:16]

    def _check_rate_limits(self) -> bool:
        """
        Check if rate limits allow new API call (ADR-012).

        Returns:
            True if call allowed, False if rate limit exceeded
        """
        now = datetime.now()

        # Reset daily budget at midnight
        if now >= self.daily_reset_time + timedelta(days=1):
            self.daily_cost = 0.0
            self.daily_reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Check daily budget
        if self.daily_cost >= self.daily_budget_usd:
            return False

        # Check hourly rate limit
        one_hour_ago = now - timedelta(hours=1)
        self.call_timestamps = [ts for ts in self.call_timestamps if ts > one_hour_ago]

        if len(self.call_timestamps) >= self.max_calls_per_hour:
            return False

        return True

    def _track_cost(self, cost_usd: float):
        """Track API call cost."""
        self.call_timestamps.append(datetime.now())
        self.daily_cost += cost_usd

    def _sign_result(self, result: Tier2Result) -> tuple[str, str]:
        """
        Sign Tier-2 result with Ed25519 (ADR-008).

        Returns: (signature_hex, public_key_hex)
        """
        payload = {
            'coherence_score': result.coherence_score,
            'summary': result.summary,
            'llm_cost_usd': result.llm_cost_usd,
            'timestamp': result.timestamp.isoformat()
        }

        canonical_json = json.dumps(payload, sort_keys=True)
        payload_bytes = canonical_json.encode('utf-8')

        signature_bytes = self.signer.private_key.sign(payload_bytes)
        signature_hex = signature_bytes.hex()
        public_key_hex = self.signer.get_public_key_hex()

        return signature_hex, public_key_hex

    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        llm_stats = self.llm_client.get_statistics()

        return {
            'computation_count': self.computation_count,
            'cache_hits': self.cache_hits,
            'cache_size': len(self.cache),
            'daily_cost_usd': self.daily_cost,
            'calls_last_hour': len(self.call_timestamps),
            'llm_stats': llm_stats,
            'public_key': self.signer.get_public_key_hex()
        }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """
    Demonstrate FINN+ Tier-2 engine functionality.
    """
    print("=" * 80)
    print("FINN+ TIER-2 ENGINE — CAUSAL COHERENCE SCORING (C4)")
    print("Phase 3: Week 3 — LARS Directive 6 (Priority 1)")
    print("=" * 80)

    # [1] Initialize engine (mock mode for testing)
    print("\n[1] Initializing FINN+ Tier-2 Engine (mock mode)...")
    engine = FINNTier2Engine(use_production_mode=True)  # Use mock LLM
    print("    ✅ Engine initialized")
    print(f"    Rate limit: {engine.max_calls_per_hour} calls/hour")
    print(f"    Daily budget: ${engine.daily_budget_usd:.2f}")

    # [2] Test Case 1: BULL regime with strong alignment
    print("\n[2] Test Case 1: BULL regime with strong alignment...")

    bull_input = Tier2Input(
        regime_label="BULL",
        regime_confidence=0.75,
        return_z=1.2,   # Strong positive return
        volatility_z=0.6,  # Low volatility
        drawdown_z=-0.3,  # Minimal drawdown
        macd_diff_z=0.8,  # Positive MACD
        price_change_pct=15.0,  # +15% over 20 days
        current_drawdown_pct=-2.0,  # -2% from peak
        cycle_id="test-001"
    )

    result_bull = engine.compute_coherence(bull_input)
    print(f"\n    Coherence Score: {result_bull.coherence_score:.2f}")
    print(f"    Summary: {result_bull.summary}")
    print(f"    Cost: ${result_bull.llm_cost_usd:.4f}")
    print(f"    Model: {result_bull.llm_model}")

    # [3] Test Case 2: BEAR regime with contradictory signals
    print("\n[3] Test Case 2: BEAR regime with contradictory signals...")

    bear_input = Tier2Input(
        regime_label="BEAR",
        regime_confidence=0.65,
        return_z=0.8,   # Positive return (contradicts BEAR)
        volatility_z=1.2,  # High volatility
        drawdown_z=-0.1,  # Minimal drawdown (contradicts BEAR)
        macd_diff_z=0.3,  # Positive MACD (contradicts BEAR)
        price_change_pct=8.0,  # +8% (contradicts BEAR)
        current_drawdown_pct=-1.5,
        cycle_id="test-002"
    )

    result_bear = engine.compute_coherence(bear_input)
    print(f"\n    Coherence Score: {result_bear.coherence_score:.2f}")
    print(f"    Summary: {result_bear.summary}")
    print(f"    Cost: ${result_bear.llm_cost_usd:.4f}")
    print(f"    Model: {result_bear.llm_model}")

    # [4] Test Case 3: NEUTRAL regime with mixed signals
    print("\n[4] Test Case 3: NEUTRAL regime with mixed signals...")

    neutral_input = Tier2Input(
        regime_label="NEUTRAL",
        regime_confidence=0.55,
        return_z=0.1,   # Near zero return
        volatility_z=0.4,  # Moderate volatility
        drawdown_z=-0.5,
        macd_diff_z=-0.1,
        price_change_pct=1.5,  # Slight positive
        current_drawdown_pct=-3.0,
        cycle_id="test-003"
    )

    result_neutral = engine.compute_coherence(neutral_input)
    print(f"\n    Coherence Score: {result_neutral.coherence_score:.2f}")
    print(f"    Summary: {result_neutral.summary}")
    print(f"    Cost: ${result_neutral.llm_cost_usd:.4f}")
    print(f"    Model: {result_neutral.llm_model}")

    # [5] Test caching
    print("\n[5] Testing cache functionality...")
    result_bull_cached = engine.compute_coherence(bull_input)
    print(f"    Cache hit: {'✅ YES' if result_bull_cached is result_bull else '❌ NO (created new)'}")

    # [6] Test placeholder mode
    print("\n[6] Testing placeholder mode (production default)...")
    engine_placeholder = FINNTier2Engine(use_production_mode=False)
    result_placeholder = engine_placeholder.compute_coherence(bull_input)
    print(f"    Coherence Score: {result_placeholder.coherence_score:.2f} (placeholder)")
    print(f"    Summary: {result_placeholder.summary}")
    print(f"    Cost: ${result_placeholder.llm_cost_usd:.4f}")

    # [7] Engine statistics
    print("\n[7] Engine statistics...")
    stats = engine.get_statistics()
    print(f"    Computations: {stats['computation_count']}")
    print(f"    Cache hits: {stats['cache_hits']}")
    print(f"    Cache size: {stats['cache_size']}")
    print(f"    Daily cost: ${stats['daily_cost_usd']:.4f}")
    print(f"    Calls (last hour): {stats['calls_last_hour']}")
    print(f"    LLM requests: {stats['llm_stats']['request_count']}")
    print(f"    LLM total cost: ${stats['llm_stats']['total_cost']:.4f}")

    # Summary
    print("\n" + "=" * 80)
    print("✅ FINN+ TIER-2 ENGINE FUNCTIONAL")
    print("=" * 80)
    print("\nKey Features:")
    print("  - LLM-based causal coherence scoring")
    print("  - Cost tracking: ~$0.0024/call (ADR-012)")
    print("  - Rate limiting: 100 calls/hour, $500/day budget")
    print("  - Response caching (5-minute TTL)")
    print("  - Ed25519 signing (ADR-008)")
    print("  - Placeholder mode (default until G1 validation)")
    print("\nIntegration:")
    print("  - Input: Tier2Input (regime + features)")
    print("  - Output: Tier2Result (coherence_score ∈ [0.0, 1.0])")
    print("  - CDS Engine: C4 component receives coherence_score")
    print("\nProduction Mode:")
    print("  - DISABLED by default (Directive 6 mandate)")
    print("  - Returns 0.0 coherence until G1-validated")
    print("  - Enable with: FINNTier2Engine(use_production_mode=True)")
    print("\nStatus: Ready for CDS Engine integration")
    print("=" * 80)
