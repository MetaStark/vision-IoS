"""
Stress Bundle V1.0 Generator
Phase 3: LARS Validation Stress Test

Generates canonical test dataset with engineered regime shifts to validate:
1. Regime detection capability (1-4 transitions over 90 days)
2. Persistence stability (≥5 days average persistence)

Authority: LARS Class B Governance Directive (20251124)
Purpose: Prove FINN+ classifier detects regimes while maintaining stability
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_stress_bundle_v1(output_path: str = "TEST_DATA_V1.0.csv"):
    """
    Generate test dataset with clear regime transitions.

    Dataset Structure (343 days total):
    - Days 0-252: BASELINE (neutral, for z-score calibration, 252-day window)
    - Days 253-283: BEAR (strong negative returns, high drawdown, 30 days)
    - Days 284-303: NEUTRAL (recovery/transition, 20 days)
    - Days 304-343: BULL (strong positive returns, low drawdown, 40 days)

    Validation Window: Last 90 days (Days 254-343)
    Expected Transitions: 2 (BEAR→NEUTRAL, NEUTRAL→BULL)
    Expected Persistence: 20-40 days per regime
    """

    np.random.seed(2024)  # Deterministic for reproducibility

    # Start date (343 days before 2024-11-24)
    start_date = datetime(2023, 12, 17)
    dates = [start_date + timedelta(days=i) for i in range(343)]

    prices = []
    current_price = 100.0

    for i in range(343):
        # BASELINE PERIOD (Days 0-252) - For z-score calibration
        if i <= 252:
            drift = 0.0005  # Slight positive drift (0.05%)
            volatility = 0.018  # Moderate volatility (1.8%)

        # BEAR REGIME (Days 253-283)
        elif i <= 283:
            drift = -0.025  # -2.5% daily drift (very strong bear)
            volatility = 0.045  # 4.5% daily volatility (high stress)

        # NEUTRAL REGIME (Days 284-303)
        elif i <= 303:
            drift = 0.001  # Small positive drift (0.1%, recovery)
            volatility = 0.022  # 2.2% volatility (moderate)

        # BULL REGIME (Days 304-343)
        else:
            drift = 0.020  # +2.0% daily drift (strong bull)
            volatility = 0.012  # 1.2% volatility (low, stable growth)

        # Generate price change with regime characteristics
        change = drift + volatility * np.random.randn()
        current_price *= (1 + change)

        # Ensure price stays positive
        current_price = max(current_price, 1.0)

        prices.append(current_price)

    # Create OHLCV data
    df = pd.DataFrame({
        'date': dates,
        'open': [p * 0.995 for p in prices],  # Open slightly below close
        'high': [p * 1.015 for p in prices],  # High 1.5% above
        'low': [p * 0.985 for p in prices],   # Low 1.5% below
        'close': prices,
        'volume': np.random.randint(100000, 500000, 343)
    })

    # Save to CSV
    df.to_csv(output_path, index=False)

    # Compute key milestones
    baseline_end = df['close'].iloc[252]
    bear_end = df['close'].iloc[283]
    neutral_end = df['close'].iloc[303]
    bull_end = df['close'].iloc[-1]

    print("=" * 80)
    print("STRESS BUNDLE V1.0 GENERATED")
    print("=" * 80)
    print(f"\nOutput: {output_path}")
    print(f"Total Rows: {len(df)}")
    print(f"Date Range: {df['date'].min()} to {df['date'].max()}")
    print(f"\nPrice Trajectory:")
    print(f"  Day 0 (Start): ${df['close'].iloc[0]:.2f}")
    print(f"  Day 252 (Baseline End): ${baseline_end:.2f} (+{((baseline_end/df['close'].iloc[0]) - 1) * 100:.1f}%)")
    print(f"  Day 283 (BEAR End): ${bear_end:.2f} ({((bear_end/baseline_end) - 1) * 100:.1f}% from baseline)")
    print(f"  Day 303 (NEUTRAL End): ${neutral_end:.2f} ({((neutral_end/baseline_end) - 1) * 100:.1f}% from baseline)")
    print(f"  Day 343 (BULL End): ${bull_end:.2f} ({((bull_end/baseline_end) - 1) * 100:.1f}% from baseline)")
    print(f"\nRegime Design:")
    print(f"  Days 0-252: BASELINE (drift=+0.05%, vol=1.8%)")
    print(f"  Days 253-283: BEAR (drift=-2.5%, vol=4.5%)")
    print(f"  Days 284-303: NEUTRAL (drift=+0.1%, vol=2.2%)")
    print(f"  Days 304-343: BULL (drift=+2.0%, vol=1.2%)")
    print(f"\nValidation Window: Last 90 days (Days 254-343)")
    print(f"Expected Validation:")
    print(f"  Transitions: 2 (BEAR→NEUTRAL→BULL)")
    print(f"  Persistence: 20-40 days per regime")
    print(f"  LARS Target: 1-4 transitions, ≥5 days persistence")
    print("\n" + "=" * 80)

    return df

if __name__ == "__main__":
    df = generate_stress_bundle_v1("TEST_DATA_V1.0.csv")
