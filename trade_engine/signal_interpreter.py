"""
Signal Interpretation
======================

Pure functions for converting raw signals into normalized exposure targets.

The signal interpreter applies confidence weighting and optional regime adjustments
to convert a SignalSnapshot into a scalar exposure target in [-1.0, 1.0].

Design (for ADR-051):
- Pure function: No side effects
- Confidence weighting: Lower confidence signals are scaled down
- Extensible: Regime adjustments can be added without breaking interface
"""

from typing import Optional
import logging

from trade_engine.models import SignalSnapshot, RiskConfig


def interpret_signal(
    signal: SignalSnapshot,
    config: RiskConfig,
    logger: Optional[logging.Logger] = None,
) -> float:
    """Convert signal to normalized desired exposure [-1.0, 1.0].

    Applies:
    1. Confidence weighting (signal_value * signal_confidence)
    2. Optional regime adjustments (V1: placeholder)

    Args:
        signal: Signal snapshot to interpret
        config: Risk configuration (for future extensions)
        logger: Optional logger for diagnostics

    Returns:
        Normalized exposure in [-1.0, 1.0]
        - Positive = long bias
        - Negative = short bias
        - Zero = no position

    Example:
        >>> signal = SignalSnapshot(
        ...     signal_id="s1",
        ...     asset_id="BTC-USD",
        ...     timestamp=datetime.utcnow(),
        ...     signal_name="MOMENTUM",
        ...     signal_value=0.8,
        ...     signal_confidence=0.5,
        ... )
        >>> interpret_signal(signal, config)
        0.4  # 0.8 * 0.5
    """
    # Apply confidence weighting
    # A signal_value of 0.8 with confidence 0.5 becomes 0.4
    exposure = signal.signal_value * signal.signal_confidence

    # Apply regime adjustments if regime_label is present
    # V1: Placeholder for future regime-based scaling
    if signal.regime_label:
        exposure = _apply_regime_adjustment(exposure, signal.regime_label)

    # Clamp to [-1, 1] as safety (should already be in range)
    exposure = max(-1.0, min(1.0, exposure))

    if logger:
        logger.info(
            f"Interpreted signal {signal.signal_id} for {signal.asset_id}: "
            f"value={signal.signal_value:.3f}, confidence={signal.signal_confidence:.3f}, "
            f"exposure={exposure:.3f}"
        )

    return exposure


def _apply_regime_adjustment(exposure: float, regime_label: str) -> float:
    """Apply regime-specific adjustments to exposure.

    V1 implementation: Identity function (no adjustment).
    V2 could implement regime-specific scaling, e.g.:
    - BEAR regime: reduce long exposure, enhance short exposure
    - SIDEWAYS regime: reduce all exposure

    Args:
        exposure: Base exposure from signal
        regime_label: Market regime (e.g. "BULL", "BEAR", "SIDEWAYS")

    Returns:
        Adjusted exposure
    """
    # V1: No adjustment
    # Future: Implement regime-specific logic here
    return exposure
