"""Entropy models for Meta-Perception Layer."""

from pydantic import BaseModel, Field
from typing import Dict, Any, Literal
from datetime import datetime
from meta_perception.models.base import frozen


@frozen
class EntropyMetrics(BaseModel):
    """
    Information entropy across different dimensions.

    Measures: How much information is in the market?
    """

    metric_id: str = Field(..., description="Metric identifier")
    timestamp: datetime = Field(..., description="Metric timestamp")

    # Market-level entropy
    market_entropy: float = Field(..., ge=0.0, description="H(market) in bits")
    market_entropy_rate: float = Field(..., description="dH/dt (bits per minute)")

    # Feature-level entropy
    feature_entropy: Dict[str, float] = Field(
        default_factory=dict,
        description="H(feature) for each feature"
    )

    # Prediction entropy (uncertainty in predictions)
    prediction_entropy: Optional[float] = Field(None, ge=0.0, description="Prediction uncertainty")

    # Cross-entropy (model vs reality)
    cross_entropy: Optional[float] = Field(None, ge=0.0, description="Cross-entropy")

    # Regime-conditional entropy
    entropy_by_regime: Dict[str, float] = Field(
        default_factory=dict,
        description="Entropy by regime"
    )

    # Interpretation
    interpretation: Literal[
        "LOW_ENTROPY",      # Highly ordered, predictable
        "MEDIUM_ENTROPY",   # Normal market conditions
        "HIGH_ENTROPY",     # Chaotic, unpredictable
        "EXTREME_ENTROPY"   # Market breakdown
    ] = Field(..., description="Entropy interpretation")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def is_stable(self) -> bool:
        """Is entropy rate low?"""
        return abs(self.market_entropy_rate) < 0.1


@frozen
class SignalEntropy(BaseModel):
    """Entropy of specific signals/features."""

    signal_name: str = Field(..., description="Signal/feature name")
    entropy: float = Field(..., ge=0.0, description="Entropy in bits")
    entropy_rate: float = Field(..., description="Rate of change")
    is_informative: bool = Field(
        ...,
        description="Is entropy in optimal range?"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# Import Optional after class definitions to avoid circular imports
from typing import Optional
