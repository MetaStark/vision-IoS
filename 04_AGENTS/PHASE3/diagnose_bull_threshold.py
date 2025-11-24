"""
BULL Threshold Diagnostic Tool

Analyzes why BULL regime is not detected and identifies threshold issues.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from finn_regime_classifier import RegimeClassifier

def diagnose_bull_threshold():
    """
    Detailed diagnostic of BULL detection failure.
    """

    print("=" * 80)
    print("BULL THRESHOLD DIAGNOSTIC")
    print("=" * 80)

    # Generate aggressive BULL test data
    np.random.seed(2025)
    start_date = datetime(2023, 12, 17)
    dates = [start_date + timedelta(days=i) for i in range(343)]

    prices = []
    current_price = 100.0

    for i in range(343):
        if i <= 252:
            drift = 0.0003
            volatility = 0.020
        else:
            drift = 0.025  # +2.5% daily
            volatility = 0.010  # Low vol

        change = drift + volatility * np.random.randn()
        current_price *= (1 + change)
        current_price = max(current_price, 1.0)
        prices.append(current_price)

    df = pd.DataFrame({
        'date': dates,
        'open': [p * 0.998 for p in prices],
        'high': [p * 1.012 for p in prices],
        'low': [p * 0.988 for p in prices],
        'close': prices,
        'volume': np.random.randint(100000, 500000, 343)
    })

    # Compute features
    classifier = RegimeClassifier()
    features = classifier.compute_features(df)

    # Analyze BULL period (days 253-343, last 90 days)
    bull_period = features.iloc[253:343]

    print("\n[1] BULL Period Feature Statistics (Days 253-343)")
    print("-" * 80)
    print(f"{'Feature':<20} {'Mean':<12} {'Min':<12} {'Max':<12} {'BULL Threshold'}")
    print("-" * 80)

    stats = {
        'return_z': (bull_period['return_z'].mean(), bull_period['return_z'].min(),
                     bull_period['return_z'].max(), '> 1.0'),
        'drawdown_z': (bull_period['drawdown_z'].mean(), bull_period['drawdown_z'].min(),
                      bull_period['drawdown_z'].max(), '> -0.2'),
        'volatility_z': (bull_period['volatility_z'].mean(), bull_period['volatility_z'].min(),
                        bull_period['volatility_z'].max(), '< 0.5'),
    }

    for feature, (mean, min_val, max_val, threshold) in stats.items():
        print(f"{feature:<20} {mean:>11.2f} {min_val:>11.2f} {max_val:>11.2f}  {threshold}")

    print("\n[2] BULL Criteria Analysis")
    print("-" * 80)

    # Count days meeting each criterion individually
    return_z_pass = (bull_period['return_z'] > 1.0).sum()
    drawdown_z_pass = (bull_period['drawdown_z'] > -0.2).sum()
    vol_z_pass = (bull_period['volatility_z'] < 0.5).sum()

    print(f"Days with return_z > 1.0:       {return_z_pass}/90 ({return_z_pass/90*100:.1f}%)")
    print(f"Days with drawdown_z > -0.2:    {drawdown_z_pass}/90 ({drawdown_z_pass/90*100:.1f}%)")
    print(f"Days with volatility_z < 0.5:   {vol_z_pass}/90 ({vol_z_pass/90*100:.1f}%)")

    # Count days meeting ALL criteria
    all_criteria = (
        (bull_period['return_z'] > 1.0) &
        (bull_period['drawdown_z'] > -0.2) &
        (bull_period['volatility_z'] < 0.5)
    )
    all_pass = all_criteria.sum()

    print(f"\nDays meeting ALL criteria:      {all_pass}/90 ({all_pass/90*100:.1f}%)")

    # Find longest consecutive streak meeting ALL criteria
    streak = 0
    max_streak = 0
    for val in all_criteria:
        if val:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    print(f"Longest consecutive streak:     {max_streak} days")
    print(f"Persistence requirement:        5 days")

    if max_streak >= 5:
        print(f"\n✅ Persistence threshold MET ({max_streak} ≥ 5 days)")
        print("   → Issue likely in hysteresis or classification logic")
    else:
        print(f"\n❌ Persistence threshold NOT MET ({max_streak} < 5 days)")
        print("   → Thresholds too strict OR volatility in returns")

    # Analyze return_z specifically (likely bottleneck)
    print("\n[3] Return_z Detailed Analysis (Likely Bottleneck)")
    print("-" * 80)

    return_z = bull_period['return_z'].dropna()
    print(f"Percentiles:")
    print(f"  10th: {return_z.quantile(0.10):.2f}")
    print(f"  25th: {return_z.quantile(0.25):.2f}")
    print(f"  50th: {return_z.quantile(0.50):.2f}")
    print(f"  75th: {return_z.quantile(0.75):.2f}")
    print(f"  90th: {return_z.quantile(0.90):.2f}")
    print(f"\nCurrent threshold: > 1.0")
    print(f"Days above threshold: {(return_z > 1.0).sum()}/90 ({(return_z > 1.0).sum()/90*100:.1f}%)")

    # Test alternative thresholds
    print("\n[4] Alternative Threshold Analysis")
    print("-" * 80)

    for threshold in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        alt_criteria = (
            (bull_period['return_z'] > threshold) &
            (bull_period['drawdown_z'] > -0.2) &
            (bull_period['volatility_z'] < 0.5)
        )
        alt_pass = alt_criteria.sum()

        # Find longest streak
        streak = 0
        max_streak = 0
        for val in alt_criteria:
            if val:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        status = "✅ PASS (≥5 days)" if max_streak >= 5 else f"❌ FAIL ({max_streak} days)"

        print(f"  return_z > {threshold:.1f}: {alt_pass}/90 days ({alt_pass/90*100:5.1f}%), "
              f"max streak = {max_streak:2d} days  {status}")

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

    return {
        'return_z_pass': return_z_pass,
        'all_criteria_pass': all_pass,
        'max_consecutive_streak': max_streak,
        'persistence_met': max_streak >= 5
    }

if __name__ == "__main__":
    results = diagnose_bull_threshold()
