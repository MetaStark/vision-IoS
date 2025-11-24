"""
FINN+ Regime Classifier - Stress Bundle V1.0 Validation

Tests regime classifier against canonical stress test dataset.

Authority: LARS Class B Governance Directive (20251124)
Purpose: Prove regime detection + stability under controlled conditions

Validation Targets:
- Transitions (90d): 1-4 (proves logic works)
- Persistence: ≥5 days (proves stability maintained)
"""

import pandas as pd
import numpy as np
from finn_regime_classifier import RegimeClassifier, RegimePersistence

def validate_against_stress_bundle(data_path: str = "TEST_DATA_V1.0.csv"):
    """
    Run FINN+ classifier against Stress Bundle V1.0.

    Args:
        data_path: Path to TEST_DATA_V1.0.csv

    Returns:
        Validation report with metrics
    """

    print("=" * 80)
    print("FINN+ REGIME CLASSIFIER — STRESS BUNDLE V1.0 VALIDATION")
    print("=" * 80)

    # Load stress bundle
    print(f"\n[1] Loading stress bundle: {data_path}")
    price_data = pd.read_csv(data_path)
    price_data['date'] = pd.to_datetime(price_data['date'])
    print(f"    Loaded: {len(price_data)} days")
    print(f"    Date range: {price_data['date'].min()} to {price_data['date'].max()}")

    # Initialize classifier
    print("\n[2] Computing features...")
    classifier = RegimeClassifier()
    features = classifier.compute_features(price_data)
    print(f"    Features computed: {len(features)} rows")
    print(f"    Feature completeness: {features.notna().sum(axis=1).mean():.1f}/7 avg")

    # Classify with persistence filtering
    print("\n[3] Running regime classification (hysteresis + persistence)...")
    regime_df = classifier.classify_timeseries_with_persistence(features, persistence_days=5)
    regime_series = regime_df['regime_label']

    # Focus on last 90 days (validation window) if dataset is longer
    if len(regime_series) > 90:
        print(f"    Full dataset: {len(regime_series)} days")
        print(f"    Validation window: Last 90 days")
        regime_series_90d = regime_series.tail(90)
        regime_df_90d = regime_df.tail(90)
    else:
        regime_series_90d = regime_series
        regime_df_90d = regime_df

    # Compute validation metrics (on 90-day window)
    print("\n[4] Computing validation metrics (90-day window)...")
    is_valid, avg_persistence = RegimePersistence.validate_persistence(regime_series_90d)
    transitions = RegimePersistence.count_transitions(regime_series_90d)

    print(f"    Average persistence: {avg_persistence:.1f} days (requirement: ≥5 days)")
    print(f"    Regime transitions (90d): {transitions} (requirement: ≤30)")
    print(f"    Persistence valid: {'✅ PASS' if is_valid else '❌ FAIL'}")
    print(f"    Transitions valid: {'✅ PASS' if transitions <= 30 else '❌ FAIL'}")

    # LARS specific requirement: 1-4 transitions
    transitions_in_range = 1 <= transitions <= 4
    print(f"    Transitions in LARS range [1-4]: {'✅ PASS' if transitions_in_range else '❌ FAIL'}")

    # Overall LARS validation
    lars_validation_pass = is_valid and transitions <= 30 and transitions_in_range
    print(f"\n    🎯 LARS VALIDATION: {'✅ PASS' if lars_validation_pass else '❌ FAIL'}")

    # Regime distribution
    print("\n[5] Regime distribution (90-day window)...")
    distribution = regime_series_90d.value_counts(normalize=True).sort_index()
    for regime in ['BEAR', 'NEUTRAL', 'BULL']:
        pct = distribution.get(regime, 0.0)
        print(f"    {regime}: {pct:.1%}")

    # Transition timeline
    print("\n[6] Regime transition timeline (90-day window)...")
    transition_mask = regime_df_90d['regime_label'] != regime_df_90d['regime_label'].shift()
    transition_points = regime_df_90d[transition_mask].iloc[1:]  # Skip first row (initial state)

    print(f"    Total transitions detected: {len(transition_points)}")
    if len(transition_points) > 0:
        print(f"\n    Transition Details:")
        prev_regime = regime_df_90d.iloc[0]['regime_label']
        first_idx = regime_df_90d.index[0]
        for idx in transition_points.index:
            row = regime_df_90d.loc[idx]
            day_num = list(regime_df_90d.index).index(idx)
            print(f"      Day {day_num:3d}: {prev_regime} → {row['regime_label']}")
            prev_regime = row['regime_label']

    # Regime stability analysis
    print("\n[7] Regime stability analysis (90-day window)...")
    for regime in ['BEAR', 'NEUTRAL', 'BULL']:
        regime_mask = regime_series_90d == regime
        if regime_mask.sum() > 0:
            # Count runs
            regime_changes = (regime_series_90d != regime_series_90d.shift()).cumsum()
            regime_runs = regime_series_90d[regime_mask].groupby(regime_changes[regime_mask]).size()

            print(f"    {regime}:")
            print(f"      Total days: {regime_mask.sum()}")
            print(f"      Number of runs: {len(regime_runs)}")
            print(f"      Avg run length: {regime_runs.mean():.1f} days")
            print(f"      Max run length: {regime_runs.max()} days")

    # Final summary
    print("\n" + "=" * 80)
    if lars_validation_pass:
        print("✅ STRESS BUNDLE VALIDATION PASS")
        print("\nConclusion:")
        print("  - Regime detection: FUNCTIONAL (transitions detected)")
        print("  - Stability rules: MAINTAINED (persistence ≥5 days)")
        print("  - LARS requirements: MET (1-4 transitions, stable persistence)")
        print("\nStatus: Ready for STIG+ integration (Week 2)")
    else:
        print("❌ STRESS BUNDLE VALIDATION FAIL")
        print("\nIssue:")
        if not transitions_in_range:
            print(f"  - Transitions out of range: {transitions} (need 1-4)")
        if not is_valid:
            print(f"  - Persistence too low: {avg_persistence:.1f} days (need ≥5)")
        if transitions > 30:
            print(f"  - Too many transitions: {transitions} (max 30)")
        print("\nStatus: Requires recalibration")
    print("=" * 80)

    return {
        'persistence': avg_persistence,
        'transitions': transitions,
        'lars_pass': lars_validation_pass,
        'distribution': distribution.to_dict()
    }

if __name__ == "__main__":
    results = validate_against_stress_bundle("TEST_DATA_V1.0.csv")
