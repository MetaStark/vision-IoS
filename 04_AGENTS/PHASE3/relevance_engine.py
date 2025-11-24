"""
Relevance Engine: FINN+ Regime → Regime Weight Mapping
Phase 3: Week 2 — Canonical Relevance Scoring

Authority: LARS Phase 3 Directive 2 (Priority 2)
Reference: HC-LARS-PHASE3-CONTINUE-20251124
Canonical ADR Chain: ADR-001 → ADR-015

Purpose: Map FINN+ market regime classifications to Regime Weight values
Replaces: Legacy HHMM-based regime weighting system

New Canonical Regime Weights:
- BULL: 1.0 (baseline confidence, low uncertainty premium)
- NEUTRAL: 1.3 (moderate uncertainty premium)
- BEAR: 1.8 (high uncertainty premium, risk-off positioning)

Relevance Score Formula (unchanged from Phase 2):
    relevance_score = cds_score * regime_weight

Rationale:
- BULL markets: Lower volatility, higher confidence → lower weight (1.0)
- NEUTRAL markets: Moderate volatility, mixed signals → moderate weight (1.3)
- BEAR markets: High volatility, high uncertainty → higher weight (1.8)

The weight acts as an uncertainty premium multiplier on the CDS (Contextual
Discrepancy Score), amplifying signals in high-uncertainty regimes.

Integration:
- FINN+ classifies regime (BEAR/NEUTRAL/BULL)
- Relevance engine maps regime → weight
- Orchestrator computes relevance_score = cds_score * regime_weight
- STIG+ validates regime weight is canonical
"""

from typing import Tuple
from enum import Enum


class RegimeLabel(Enum):
    """FINN+ regime classifications."""
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"
    BULL = "BULL"


# Canonical Regime Weights (LARS Directive 2)
# These weights represent uncertainty premium multipliers
CANONICAL_REGIME_WEIGHTS = {
    RegimeLabel.BULL: 1.0,      # Low uncertainty, baseline confidence
    RegimeLabel.NEUTRAL: 1.3,   # Moderate uncertainty premium
    RegimeLabel.BEAR: 1.8       # High uncertainty premium (risk-off)
}


def get_regime_weight(regime_label: str) -> float:
    """
    Get canonical regime weight for FINN+ regime classification.

    This function maps FINN+ regime labels to their corresponding
    uncertainty premium weights used in relevance score calculation.

    Args:
        regime_label: FINN+ regime label ("BULL", "NEUTRAL", or "BEAR")

    Returns:
        Canonical regime weight (1.0, 1.3, or 1.8)

    Raises:
        ValueError: If regime_label is not a valid FINN+ regime

    Examples:
        >>> get_regime_weight("BULL")
        1.0
        >>> get_regime_weight("NEUTRAL")
        1.3
        >>> get_regime_weight("BEAR")
        1.8
    """
    # Normalize input (case-insensitive)
    regime_label_upper = regime_label.upper()

    # Validate and map to weight
    try:
        regime_enum = RegimeLabel[regime_label_upper]
        return CANONICAL_REGIME_WEIGHTS[regime_enum]
    except KeyError:
        raise ValueError(
            f"Invalid regime label: '{regime_label}'. "
            f"Must be one of: BULL, NEUTRAL, BEAR"
        )


def compute_relevance_score(cds_score: float, regime_label: str) -> Tuple[float, float]:
    """
    Compute relevance score from CDS score and FINN+ regime.

    This function implements the Phase 2 relevance scoring formula
    but uses Phase 3 FINN+ regime classifications instead of legacy
    HHMM-based regime weights.

    Formula: relevance_score = cds_score * regime_weight

    Args:
        cds_score: Contextual Discrepancy Score [0.0, 1.0]
        regime_label: FINN+ regime label ("BULL", "NEUTRAL", or "BEAR")

    Returns:
        Tuple of (relevance_score, regime_weight)

    Raises:
        ValueError: If cds_score out of range or regime_label invalid

    Examples:
        >>> compute_relevance_score(0.723, "BEAR")
        (1.3014, 1.8)  # High CDS + BEAR regime = very high relevance

        >>> compute_relevance_score(0.450, "NEUTRAL")
        (0.585, 1.3)   # Moderate CDS + NEUTRAL regime = moderate relevance

        >>> compute_relevance_score(0.300, "BULL")
        (0.300, 1.0)   # Low CDS + BULL regime = low relevance
    """
    # Validate CDS score range
    if not (0.0 <= cds_score <= 1.0):
        raise ValueError(
            f"CDS score must be in range [0.0, 1.0], got {cds_score}"
        )

    # Get regime weight
    regime_weight = get_regime_weight(regime_label)

    # Compute relevance score
    relevance_score = cds_score * regime_weight

    return relevance_score, regime_weight


def get_canonical_weights() -> dict:
    """
    Get all canonical regime weights.

    Returns:
        Dictionary mapping regime labels to weights

    Example:
        >>> get_canonical_weights()
        {'BULL': 1.0, 'NEUTRAL': 1.3, 'BEAR': 1.8}
    """
    return {
        regime.value: weight
        for regime, weight in CANONICAL_REGIME_WEIGHTS.items()
    }


def validate_regime_weight(weight: float) -> bool:
    """
    Validate that a weight is one of the canonical regime weights.

    Used by STIG+ to verify regime weight correctness.

    Args:
        weight: Regime weight to validate

    Returns:
        True if weight is canonical, False otherwise

    Example:
        >>> validate_regime_weight(1.8)
        True
        >>> validate_regime_weight(0.85)  # Legacy HHMM weight
        False
    """
    canonical_values = set(CANONICAL_REGIME_WEIGHTS.values())
    return weight in canonical_values


def get_relevance_tier(relevance_score: float) -> str:
    """
    Classify relevance score into tier (ADR-010 compliance).

    Tiers:
    - "high": relevance_score > 0.70 (action required)
    - "medium": 0.40 < relevance_score <= 0.70 (monitor)
    - "low": relevance_score <= 0.40 (informational)

    Args:
        relevance_score: Computed relevance score

    Returns:
        Tier label ("high", "medium", or "low")

    Example:
        >>> get_relevance_tier(0.850)
        'high'
        >>> get_relevance_tier(0.550)
        'medium'
        >>> get_relevance_tier(0.300)
        'low'
    """
    if relevance_score > 0.70:
        return "high"
    elif relevance_score > 0.40:
        return "medium"
    else:
        return "low"


# ============================================================================
# Legacy HHMM Weights (Deprecated - for reference only)
# ============================================================================

# Phase 2 HHMM-based weights (DEPRECATED - DO NOT USE)
LEGACY_HHMM_WEIGHTS = [0.25, 0.50, 0.75, 0.85, 1.0]

"""
LEGACY SYSTEM NOTES (Phase 2):

The Phase 2 system used Hidden Markov Model (HHMM) to classify market regimes
into 5 states with corresponding weights: [0.25, 0.50, 0.75, 0.85, 1.0]

Issues with Legacy System:
1. HHMM regime states were opaque (no clear BEAR/NEUTRAL/BULL mapping)
2. 5-state granularity was excessive for relevance scoring
3. Weights ranged from 0.25-1.0 (unduly compressed uncertainty premium)

Phase 3 Improvements (FINN+):
1. Explicit 3-regime classification (BEAR/NEUTRAL/BULL)
2. Clear semantic meaning for each regime
3. Expanded weight range (1.0-1.8) to capture uncertainty premium
4. Direct integration with validated regime classifier (STIG+)
5. Cryptographic signature on regime predictions (ADR-008)

Migration Path:
- Phase 2 systems continue using HHMM until Phase 3 activation
- Phase 3 systems use FINN+ regime → weight mapping
- No backward compatibility required (Phase 3 isolated schema)
"""


# ============================================================================
# Example Usage and Testing
# ============================================================================

if __name__ == "__main__":
    """
    Demonstrate relevance engine functionality.
    """
    print("=" * 80)
    print("RELEVANCE ENGINE — FINN+ REGIME → WEIGHT MAPPING")
    print("Phase 3: Week 2 — Canonical Relevance Scoring")
    print("=" * 80)

    # [1] Display canonical weights
    print("\n[1] Canonical Regime Weights (LARS Directive 2)")
    print("-" * 60)
    for regime, weight in get_canonical_weights().items():
        print(f"    {regime:8s}: {weight:.1f}")

    # [2] Test regime weight lookup
    print("\n[2] Regime Weight Lookup Examples")
    print("-" * 60)
    for regime in ["BULL", "NEUTRAL", "BEAR"]:
        weight = get_regime_weight(regime)
        print(f"    get_regime_weight('{regime}'):  {weight:.1f}")

    # [3] Test relevance score computation
    print("\n[3] Relevance Score Computation Examples")
    print("-" * 60)

    test_cases = [
        (0.723, "BEAR", "High CDS + BEAR regime"),
        (0.450, "NEUTRAL", "Moderate CDS + NEUTRAL regime"),
        (0.300, "BULL", "Low CDS + BULL regime"),
        (0.850, "BEAR", "Very high CDS + BEAR regime"),
    ]

    for cds, regime, description in test_cases:
        relevance, weight = compute_relevance_score(cds, regime)
        tier = get_relevance_tier(relevance)
        print(f"    CDS={cds:.3f}, Regime={regime:7s} → "
              f"Relevance={relevance:.3f} (tier: {tier}) "
              f"[{description}]")

    # [4] Test validation
    print("\n[4] Regime Weight Validation")
    print("-" * 60)

    test_weights = [1.0, 1.3, 1.8, 0.85, 2.0]
    for weight in test_weights:
        is_valid = validate_regime_weight(weight)
        status = "✅ CANONICAL" if is_valid else "❌ INVALID"
        note = "" if is_valid else " (legacy HHMM)" if weight in LEGACY_HHMM_WEIGHTS else " (unknown)"
        print(f"    validate_regime_weight({weight:.2f}): {status}{note}")

    # [5] Test tier classification
    print("\n[5] Relevance Tier Classification (ADR-010)")
    print("-" * 60)

    tier_test_scores = [0.900, 0.700, 0.550, 0.400, 0.200]
    for score in tier_test_scores:
        tier = get_relevance_tier(score)
        print(f"    Relevance={score:.3f} → Tier: {tier.upper()}")

    # [6] Error handling
    print("\n[6] Error Handling")
    print("-" * 60)

    try:
        get_regime_weight("INVALID")
    except ValueError as e:
        print(f"    ✅ Invalid regime rejected: {e}")

    try:
        compute_relevance_score(1.5, "BULL")  # CDS out of range
    except ValueError as e:
        print(f"    ✅ Invalid CDS rejected: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("✅ RELEVANCE ENGINE FUNCTIONAL")
    print("=" * 80)
    print("\nLARS Directive 2 (Priority 2): COMPLETE")
    print("\nCanonical Regime Weights:")
    print("  - BULL: 1.0 (baseline confidence)")
    print("  - NEUTRAL: 1.3 (moderate uncertainty premium)")
    print("  - BEAR: 1.8 (high uncertainty premium)")
    print("\nLegacy HHMM System: DEPRECATED")
    print("  - Phase 2 weights: [0.25, 0.50, 0.75, 0.85, 1.0]")
    print("  - Replaced by: FINN+ 3-regime classification")
    print("\nIntegration Status:")
    print("  - get_regime_weight(): ✅ FUNCTIONAL")
    print("  - compute_relevance_score(): ✅ FUNCTIONAL")
    print("  - validate_regime_weight(): ✅ FUNCTIONAL (STIG+)")
    print("  - get_relevance_tier(): ✅ FUNCTIONAL (ADR-010)")
    print("\nReady for Phase 3 orchestrator integration")
    print("=" * 80)
