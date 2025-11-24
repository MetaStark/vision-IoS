"""
FINN+ Regime Classification Module
Phase 3: System Expansion & Autonomy Development
Authority: LARS Phase 3 Directive (HC-LARS-PHASE3-CONFIRM-20251124)
Canonical ADR Chain: ADR-001 → ADR-015

This module implements market regime classification for FINN+ (v2.0).
Classifies market conditions into three regimes: BEAR, NEUTRAL, BULL.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class RegimeClassification:
    """Regime classification result."""
    regime_label: str  # "BEAR", "NEUTRAL", "BULL"
    regime_state: int  # 0, 1, 2
    confidence: float  # 0.0 to 1.0
    prob_bear: float
    prob_neutral: float
    prob_bull: float
    timestamp: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "regime_label": self.regime_label,
            "regime_state": self.regime_state,
            "confidence": round(self.confidence, 4),
            "prob_bear": round(self.prob_bear, 4),
            "prob_neutral": round(self.prob_neutral, 4),
            "prob_bull": round(self.prob_bull, 4),
            "timestamp": self.timestamp.isoformat()
        }


class RegimeClassifier:
    """
    Market regime classifier for FINN+.

    Uses 7 z-scored technical features to classify market state.
    Regime states: 0 (BEAR), 1 (NEUTRAL), 2 (BULL)
    """

    # Feature names (7 technical indicators)
    FEATURE_NAMES = [
        "return_z",       # Log returns (z-scored)
        "volatility_z",   # 20-day volatility (z-scored)
        "drawdown_z",     # Drawdown from peak (z-scored)
        "macd_diff_z",    # MACD histogram (z-scored)
        "bb_width_z",     # Bollinger Band width (z-scored)
        "rsi_14_z",       # RSI-14 (z-scored)
        "roc_20_z"        # Rate of change (z-scored)
    ]

    # Z-score window (252 trading days ≈ 1 year)
    ZSCORE_WINDOW = 252
    MIN_PERIODS = 30  # Minimum periods for z-score calculation

    # Regime labels
    REGIME_LABELS = {
        0: "BEAR",
        1: "NEUTRAL",
        2: "BULL"
    }

    def __init__(self):
        """Initialize regime classifier."""
        self.state_profiles = None
        self.is_fitted = False

    def compute_features(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute 7 z-scored features from price data.

        Args:
            price_data: DataFrame with columns [open, high, low, close, volume]

        Returns:
            DataFrame with z-scored features
        """
        df = price_data.copy()

        # 1. Log returns (use singular 'return' for consistency)
        df['return'] = np.log(df['close'] / df['close'].shift(1))

        # 2. Volatility (20-day rolling std of returns)
        df['volatility'] = df['return'].rolling(window=20).std()

        # 3. Drawdown from peak
        df['cummax'] = df['close'].cummax()
        df['drawdown'] = (df['close'] - df['cummax']) / df['cummax']

        # 4. MACD histogram (12, 26, 9)
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        df['macd_diff'] = macd_line - macd_signal

        # 5. Bollinger Band width (20-day, 2 std)
        bb_middle = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_width'] = (bb_std * 2) / bb_middle

        # 6. RSI-14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))

        # 7. Rate of change (20-day)
        df['roc_20'] = (df['close'] - df['close'].shift(20)) / df['close'].shift(20)

        # Z-score standardization (252-day rolling window)
        raw_features = ['return', 'volatility', 'drawdown', 'macd_diff',
                       'bb_width', 'rsi_14', 'roc_20']

        for feature in raw_features:
            mean = df[feature].rolling(window=self.ZSCORE_WINDOW, min_periods=self.MIN_PERIODS).mean()
            std = df[feature].rolling(window=self.ZSCORE_WINDOW, min_periods=self.MIN_PERIODS).std()
            df[f"{feature}_z"] = (df[feature] - mean) / std

        # Return only z-scored features
        return df[self.FEATURE_NAMES]

    def fit_state_profiles(self, features: pd.DataFrame,
                          state_assignments: np.ndarray) -> Dict:
        """
        Compute state profiles from features and state assignments.

        This would typically be done during model training.
        For Phase 3 Week 1, we use a simplified rule-based approach.

        Args:
            features: DataFrame with z-scored features
            state_assignments: Array of state labels (0, 1, 2)

        Returns:
            Dictionary of state profiles
        """
        profiles = {}

        for state in [0, 1, 2]:
            mask = state_assignments == state
            state_features = features[mask]

            profiles[state] = {
                "mean_return": state_features['return_z'].mean(),
                "mean_volatility": state_features['volatility_z'].mean(),
                "mean_drawdown": state_features['drawdown_z'].mean(),
                "count": mask.sum()
            }

        self.state_profiles = profiles
        self.is_fitted = True
        return profiles

    def classify_regime_rule_based(self, features: pd.Series) -> RegimeClassification:
        """
        Classify regime using rule-based logic (Week 1 prototype).

        Rules:
        - BEAR: negative returns, high volatility, high drawdown
        - BULL: positive returns, moderate volatility, low drawdown
        - NEUTRAL: near-zero returns, moderate volatility

        Args:
            features: Series with z-scored features

        Returns:
            RegimeClassification result
        """
        # Extract key features
        return_z = features.get('return_z', 0)
        vol_z = features.get('volatility_z', 0)
        drawdown_z = features.get('drawdown_z', 0)

        # Rule-based classification
        if return_z < -0.5 and drawdown_z < -0.3:
            # Strong negative signal → BEAR
            regime_state = 0
            regime_label = "BEAR"
            prob_bear = 0.70
            prob_neutral = 0.20
            prob_bull = 0.10
        elif return_z > 0.5 and drawdown_z > -0.3:
            # Strong positive signal → BULL
            regime_state = 2
            regime_label = "BULL"
            prob_bear = 0.10
            prob_neutral = 0.20
            prob_bull = 0.70
        else:
            # Mixed or weak signals → NEUTRAL
            regime_state = 1
            regime_label = "NEUTRAL"
            prob_bear = 0.25
            prob_neutral = 0.50
            prob_bull = 0.25

        # Confidence is max probability
        confidence = max(prob_bear, prob_neutral, prob_bull)

        return RegimeClassification(
            regime_label=regime_label,
            regime_state=regime_state,
            confidence=confidence,
            prob_bear=prob_bear,
            prob_neutral=prob_neutral,
            prob_bull=prob_bull,
            timestamp=datetime.utcnow()
        )

    def classify_regime(self, features: pd.Series) -> RegimeClassification:
        """
        Classify regime (unified interface).

        Week 1: Uses rule-based logic.
        Future: Will use trained statistical model (HMM or similar).

        Args:
            features: Series with z-scored features

        Returns:
            RegimeClassification result
        """
        # Week 1: Rule-based classification
        return self.classify_regime_rule_based(features)

    def validate_features(self, features: pd.Series) -> Tuple[bool, str]:
        """
        Validate that features meet quality requirements.

        Rule: At least 5 of 7 features must be non-null.

        Args:
            features: Series with z-scored features

        Returns:
            (is_valid, reason)
        """
        non_null_count = features[self.FEATURE_NAMES].notna().sum()

        if non_null_count < 5:
            return False, f"Insufficient features: {non_null_count}/7 (need ≥5)"

        return True, "Valid"


class RegimePersistence:
    """Utilities for regime prediction persistence."""

    @staticmethod
    def validate_persistence(regime_history: pd.Series,
                            min_consecutive_days: int = 5) -> Tuple[bool, float]:
        """
        Validate regime persistence (average consecutive days).

        Args:
            regime_history: Series of regime labels over time
            min_consecutive_days: Minimum acceptable persistence

        Returns:
            (is_valid, avg_consecutive_days)
        """
        if len(regime_history) == 0:
            return False, 0.0

        # Count consecutive regime runs
        regime_changes = (regime_history != regime_history.shift()).cumsum()
        run_lengths = regime_history.groupby(regime_changes).size()
        avg_persistence = run_lengths.mean()

        is_valid = avg_persistence >= min_consecutive_days
        return is_valid, avg_persistence

    @staticmethod
    def count_transitions(regime_history: pd.Series, window_days: int = 90) -> int:
        """
        Count regime transitions in recent window.

        Args:
            regime_history: Series of regime labels over time
            window_days: Window for transition counting

        Returns:
            Number of transitions
        """
        recent_history = regime_history.tail(window_days)
        transitions = (recent_history != recent_history.shift()).sum() - 1  # -1 for first row
        return max(0, transitions)


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of RegimeClassifier.

    This demonstrates Week 1 prototype functionality.
    """
    print("=" * 80)
    print("FINN+ REGIME CLASSIFIER - WEEK 1 PROTOTYPE")
    print("=" * 80)

    # Create sample price data
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", end="2024-11-24", freq="D")
    n = len(dates)

    # Simulate price series with regimes
    prices = []
    current_price = 100.0

    for i in range(n):
        # Simulate different regimes over time
        if i < n // 3:
            # BEAR regime: negative drift, high volatility
            drift = -0.001
            vol = 0.03
        elif i < 2 * n // 3:
            # NEUTRAL regime: zero drift, moderate volatility
            drift = 0.0
            vol = 0.02
        else:
            # BULL regime: positive drift, low volatility
            drift = 0.002
            vol = 0.015

        change = drift + vol * np.random.randn()
        current_price *= (1 + change)
        prices.append(current_price)

    price_data = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': np.random.randint(1000, 10000, n)
    })

    # Initialize classifier
    classifier = RegimeClassifier()

    # Compute features
    print("\n[1] Computing features...")
    features = classifier.compute_features(price_data)
    print(f"    Features computed: {len(features)} rows")
    print(f"    Feature completeness: {features.notna().sum(axis=1).mean():.1f}/7 avg")

    # Classify most recent regime
    print("\n[2] Classifying current regime...")
    latest_features = features.iloc[-1]

    is_valid, reason = classifier.validate_features(latest_features)
    if is_valid:
        result = classifier.classify_regime(latest_features)
        print(f"    Current regime: {result.regime_label}")
        print(f"    Confidence: {result.confidence:.2%}")
        print(f"    Probabilities: BEAR={result.prob_bear:.2%}, "
              f"NEUTRAL={result.prob_neutral:.2%}, BULL={result.prob_bull:.2%}")
        print(f"    Result: {json.dumps(result.to_dict(), indent=2)}")
    else:
        print(f"    ❌ Validation failed: {reason}")

    # Analyze persistence
    print("\n[3] Analyzing regime persistence...")
    recent_features = features.tail(90).dropna()
    regime_labels = []

    for idx in recent_features.index:
        result = classifier.classify_regime(recent_features.loc[idx])
        regime_labels.append(result.regime_label)

    regime_series = pd.Series(regime_labels)
    is_valid, avg_persistence = RegimePersistence.validate_persistence(regime_series)
    transitions = RegimePersistence.count_transitions(regime_series)

    print(f"    Average persistence: {avg_persistence:.1f} days (min: 5 days)")
    print(f"    Regime transitions (90d): {transitions}")
    print(f"    Persistence valid: {'✅' if is_valid else '❌'}")

    # Regime distribution
    print("\n[4] Regime distribution (last 90 days)...")
    distribution = regime_series.value_counts(normalize=True)
    for regime, pct in distribution.items():
        print(f"    {regime}: {pct:.1%}")

    print("\n" + "=" * 80)
    print("✅ WEEK 1 PROTOTYPE COMPLETE")
    print("=" * 80)
