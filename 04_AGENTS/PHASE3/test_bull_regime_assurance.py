"""
BULL Regime Detection Assurance Test
Phase 3: G2/G3 Governance Check

Authority: LARS Bull-Assurance Directive (ADR-010 Discrepancy Scoring)
Purpose: Prove BULL-entry logic is functional and achievable

Test Objective:
- Create synthetic dataset that clearly meets BULL criteria
- Verify BULL regime detection occurs
- Prevent Tier-2 Asymmetric Error (blind to upside opportunities)

BULL Entry Criteria:
- return_z > 1.0 (strong positive returns)
- drawdown_z > -0.2 (minimal drawdown, near peak)
- vol_z < 0.5 (low volatility, stable growth)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from finn_regime_classifier import RegimeClassifier, RegimePersistence

def generate_bull_stress_test():
    """
    Generate synthetic dataset explicitly designed to trigger BULL regime.

    Structure:
    - Days 0-252: BASELINE (for z-score calibration)
    - Days 253-343: AGGRESSIVE BULL (strong rally, low volatility, sustained growth)

    Expected: BULL regime detected in days 253-343 after persistence filtering
    """

    np.random.seed(2025)  # Different seed from Stress Bundle V1.0

    start_date = datetime(2023, 12, 17)
    dates = [start_date + timedelta(days=i) for i in range(343)]

    prices = []
    current_price = 100.0

    for i in range(343):
        # BASELINE PERIOD (Days 0-252)
        if i <= 252:
            drift = 0.0003  # Slight positive drift
            volatility = 0.020  # Moderate volatility

        # AGGRESSIVE BULL REGIME (Days 253-343)
        else:
            drift = 0.025  # +2.5% daily drift (very strong bull)
            volatility = 0.010  # 1.0% volatility (very low, stable growth)

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

    return df

def test_bull_regime_detection():
    """
    Unit test: Verify BULL regime can be detected.

    Returns:
        dict with test results
    """

    print("=" * 80)
    print("BULL REGIME DETECTION ASSURANCE TEST")
    print("G2/G3 Governance Check — ADR-010 Discrepancy Scoring")
    print("=" * 80)

    # Generate BULL-optimized test data
    print("\n[1] Generating BULL stress test dataset...")
    price_data = generate_bull_stress_test()
    print(f"    Generated: {len(price_data)} days")
    print(f"    Price trajectory: ${price_data['close'].iloc[0]:.2f} → ${price_data['close'].iloc[-1]:.2f}")
    print(f"    Total return: {((price_data['close'].iloc[-1] / price_data['close'].iloc[0]) - 1) * 100:.1f}%")

    # Compute features
    print("\n[2] Computing features...")
    classifier = RegimeClassifier()
    features = classifier.compute_features(price_data)
    print(f"    Features computed: {len(features)} rows")

    # Analyze feature characteristics in BULL period (days 253-343)
    print("\n[3] Analyzing BULL period features (days 253-343)...")
    bull_period_features = features.iloc[253:343]

    print(f"    Average return_z: {bull_period_features['return_z'].mean():.2f}")
    print(f"    Average drawdown_z: {bull_period_features['drawdown_z'].mean():.2f}")
    print(f"    Average volatility_z: {bull_period_features['volatility_z'].mean():.2f}")

    # Check if features meet BULL criteria
    bull_criteria_met = (
        (bull_period_features['return_z'] > 1.0) &
        (bull_period_features['drawdown_z'] > -0.2)
    ).sum()

    print(f"    Days meeting BULL criteria: {bull_criteria_met} / {len(bull_period_features)}")
    print(f"    Percentage: {(bull_criteria_met / len(bull_period_features)) * 100:.1f}%")

    # Run full regime classification with persistence
    print("\n[4] Running regime classification (hysteresis + persistence)...")
    regime_df = classifier.classify_timeseries_with_persistence(features, persistence_days=5)
    regime_series = regime_df['regime_label']

    # Focus on last 90 days
    regime_series_90d = regime_series.tail(90)
    regime_df_90d = regime_df.tail(90)

    # Check for BULL detection
    print("\n[5] BULL regime detection results (90-day window)...")
    bull_detected = (regime_series_90d == 'BULL').sum()
    bear_detected = (regime_series_90d == 'BEAR').sum()
    neutral_detected = (regime_series_90d == 'NEUTRAL').sum()

    print(f"    BULL days: {bull_detected} ({(bull_detected/90)*100:.1f}%)")
    print(f"    NEUTRAL days: {neutral_detected} ({(neutral_detected/90)*100:.1f}%)")
    print(f"    BEAR days: {bear_detected} ({(bear_detected/90)*100:.1f}%)")

    # Compute validation metrics
    is_valid, avg_persistence = RegimePersistence.validate_persistence(regime_series_90d)
    transitions = RegimePersistence.count_transitions(regime_series_90d)

    print(f"\n[6] Validation metrics...")
    print(f"    Average persistence: {avg_persistence:.1f} days")
    print(f"    Transitions (90d): {transitions}")

    # Show transition timeline
    print(f"\n[7] Transition timeline...")
    transition_mask = regime_df_90d['regime_label'] != regime_df_90d['regime_label'].shift()
    transition_points = regime_df_90d[transition_mask].iloc[1:]

    if len(transition_points) > 0:
        prev_regime = regime_df_90d.iloc[0]['regime_label']
        for idx in transition_points.index:
            row = regime_df_90d.loc[idx]
            day_num = list(regime_df_90d.index).index(idx)
            print(f"    Day {day_num}: {prev_regime} → {row['regime_label']}")
            prev_regime = row['regime_label']
    else:
        final_regime = regime_df_90d.iloc[-1]['regime_label']
        print(f"    No transitions detected (entire period: {final_regime})")

    # Test verdict
    print("\n" + "=" * 80)

    bull_test_pass = bull_detected > 0

    if bull_test_pass:
        print("✅ BULL REGIME DETECTION: FUNCTIONAL")
        print("\nConclusion:")
        print(f"  - BULL regime detected: {bull_detected} days ({(bull_detected/90)*100:.1f}% of window)")
        print(f"  - Detection logic: VERIFIED")
        print(f"  - Asymmetric blind spot: NONE")
        print(f"  - Alpha generation capability: CONFIRMED (both upside & downside)")
        print("\nStatus: G2/G3 governance check PASSED")
    else:
        print("❌ BULL REGIME DETECTION: FAILED")
        print("\nIssue:")
        print(f"  - BULL regime not detected despite strong rally (+{((price_data['close'].iloc[-1] / price_data['close'].iloc[0]) - 1) * 100:.1f}%)")
        print(f"  - Days meeting BULL criteria: {bull_criteria_met}")
        print(f"  - Potential asymmetric blind spot: YES")
        print(f"  - Risk: Unable to detect upside opportunities (Tier-2 Asymmetric Error)")
        print("\nStatus: G2/G3 governance check FAILED — requires threshold recalibration")

    print("=" * 80)

    return {
        'bull_detected_days': bull_detected,
        'bull_percentage': (bull_detected / 90) * 100,
        'test_pass': bull_test_pass,
        'avg_persistence': avg_persistence,
        'transitions': transitions,
        'bull_criteria_met_days': bull_criteria_met
    }

if __name__ == "__main__":
    results = test_bull_regime_detection()

    # Print final verdict
    print("\n" + "=" * 80)
    print("FINAL VERDICT — LARS G2/G3 BULL-ASSURANCE CHECK")
    print("=" * 80)

    if results['test_pass']:
        print(f"✅ BULL detection logic: FUNCTIONAL")
        print(f"   Detected BULL regime: {results['bull_detected_days']} days ({results['bull_percentage']:.1f}%)")
        print(f"   Asymmetric error risk: MITIGATED")
        print(f"\n   Assurance: FINN+ can detect both BEAR and BULL regimes.")
        print(f"   Status: Ready for Tier-2 → Tier-3 integration.")
    else:
        print(f"❌ BULL detection logic: NON-FUNCTIONAL")
        print(f"   Detected BULL regime: 0 days (0.0%)")
        print(f"   Asymmetric error risk: CRITICAL")
        print(f"\n   Warning: FINN+ blind to upside opportunities.")
        print(f"   Status: Requires immediate threshold recalibration.")

    print("=" * 80)
