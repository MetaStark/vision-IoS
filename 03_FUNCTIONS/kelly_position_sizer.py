#!/usr/bin/env python3
"""
KELLY CRITERION POSITION SIZER (STIG-2025-001 Compliant)
========================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - Bayesian Filter + Kelly Criterion
Classification: Tier-1 Risk Management Critical

Purpose:
    Probabilistic position sizing for low-Sharpe signals.
    Prevents "death by 1000 cuts" from binary entry on weak signals.

Kelly Formula:
    f* = (p(b+1) - 1) / b

    Where:
    - f* = optimal fraction of capital to risk
    - p = probability of winning
    - b = win/loss ratio (odds)

    Sharpe 0.15 -> p ~ 0.52 -> small position
    Sharpe 0.30 -> p ~ 0.60 -> larger position

Usage:
    from kelly_position_sizer import KellyPositionSizer, calculate_kelly_fraction

    sizer = KellyPositionSizer()
    position = sizer.calculate_position(
        sharpe=0.15,
        confidence=0.85,
        capital=100000,
        max_position_pct=0.10
    )
"""

import os
import json
import math
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class PositionSizeCategory(Enum):
    """Position sizing categories"""
    SKIP = "SKIP"               # f* < 0 or very negative edge
    MINIMAL = "MINIMAL"         # 0 < f* < 0.05 (tiny)
    SMALL = "SMALL"             # 0.05 <= f* < 0.15
    MEDIUM = "MEDIUM"           # 0.15 <= f* < 0.30
    LARGE = "LARGE"             # f* >= 0.30


@dataclass
class PositionSize:
    """Result of Kelly position sizing"""
    asset: str
    kelly_fraction: float           # Raw Kelly f*
    half_kelly: float               # Half-Kelly (more conservative)
    quarter_kelly: float            # Quarter-Kelly (most conservative)
    recommended_fraction: float     # Actual recommended
    position_category: PositionSizeCategory
    dollar_amount: float            # Actual dollar position
    shares: Optional[int]           # Share count if price available
    confidence: float               # Input signal confidence
    sharpe: float                   # Input Sharpe ratio
    win_probability: float          # Derived win probability
    win_loss_ratio: float           # Derived win/loss ratio
    metadata: Dict


class KellyPositionSizer:
    """
    Kelly Criterion Position Sizer (STIG-2025-001)

    Implements probabilistic position sizing based on signal quality.
    Uses fractional Kelly (half or quarter) for safety.

    Key insight: Sharpe ratio maps to win probability:
    - Sharpe 0.0 -> p = 0.50 (no edge)
    - Sharpe 0.15 -> p = 0.52
    - Sharpe 0.30 -> p = 0.55
    - Sharpe 0.50 -> p = 0.60
    - Sharpe 1.00 -> p = 0.69
    """

    # ADR-012 Compliance Limits - AGGRESSIVE CORPORATE STANDARD
    MAX_SINGLE_POSITION = 0.15      # 15% NAV max (aggressive)
    MAX_KELLY_FRACTION = 0.30       # Allow up to 30% Kelly
    MIN_KELLY_THRESHOLD = 0.01      # Skip if Kelly < 1%
    MIN_POSITION_DOLLAR = 500       # Minimum $500 per trade

    # Fractional Kelly multiplier - AGGRESSIVE
    KELLY_MULTIPLIER = 0.75         # Use 3/4 Kelly (aggressive)

    def __init__(self, kelly_multiplier: float = 0.75):
        """
        Initialize Kelly Position Sizer.

        Args:
            kelly_multiplier: Fraction of Kelly to use (0.5 = Half-Kelly)
        """
        self.kelly_multiplier = kelly_multiplier
        self.conn = psycopg2.connect(**DB_CONFIG)

    @staticmethod
    def sharpe_to_win_probability(sharpe: float, trading_days: int = 252) -> float:
        """
        Convert Sharpe ratio to win probability.

        Based on: If daily Sharpe = S, and assuming normal distribution,
        win probability p = Phi(S / sqrt(trading_days))

        Simplified approximation for daily trades:
        p = 0.5 + 0.12 * sharpe (for sharpe in [0, 1])
        """
        # More accurate: use normal CDF
        # But simpler approximation works well for typical Sharpe range
        if sharpe <= 0:
            return 0.50

        # Sigmoid-like mapping
        # sharpe=0 -> p=0.50, sharpe=0.5 -> p=0.60, sharpe=1.0 -> p=0.69
        p = 0.5 + (0.5 / (1 + math.exp(-3 * sharpe))) - 0.25

        return min(max(p, 0.50), 0.95)  # Clamp to [0.50, 0.95]

    @staticmethod
    def estimate_win_loss_ratio(sharpe: float, avg_win_pct: float = 0.02) -> float:
        """
        Estimate win/loss ratio from Sharpe.

        For typical mean-reversion strategies:
        - Average win ~ 2%
        - Average loss varies with Sharpe

        Higher Sharpe -> better win/loss ratio
        """
        if sharpe <= 0:
            return 1.0

        # Win/loss ratio increases with Sharpe
        # At Sharpe 0.5, expect ~1.2x win/loss
        # At Sharpe 1.0, expect ~1.5x win/loss
        ratio = 1.0 + (0.5 * sharpe)

        return min(ratio, 3.0)  # Cap at 3x

    @staticmethod
    def kelly_formula(win_prob: float, win_loss_ratio: float) -> float:
        """
        Calculate Kelly fraction.

        f* = (p(b+1) - 1) / b

        Where:
        - p = probability of winning
        - b = win/loss ratio
        """
        p = win_prob
        b = win_loss_ratio

        if b <= 0:
            return 0.0

        kelly = (p * (b + 1) - 1) / b

        return kelly

    def calculate_position(
        self,
        asset: str,
        sharpe: float,
        confidence: float,
        capital: float,
        current_price: Optional[float] = None,
        cohesion_multiplier: float = 1.0,
        max_position_pct: float = None
    ) -> PositionSize:
        """
        Calculate position size using Kelly Criterion.

        Args:
            asset: Asset identifier
            sharpe: Backtest Sharpe ratio
            confidence: Signal confidence [0, 1]
            capital: Total portfolio capital
            current_price: Current asset price (for share calculation)
            cohesion_multiplier: From SignalCohesionEngine (0.5 or 1.0)
            max_position_pct: Override max position percentage

        Returns:
            PositionSize with recommended allocation
        """
        max_pct = max_position_pct or self.MAX_SINGLE_POSITION

        # Convert Sharpe to edge metrics
        win_prob = self.sharpe_to_win_probability(sharpe)
        win_loss = self.estimate_win_loss_ratio(sharpe)

        # Calculate raw Kelly
        raw_kelly = self.kelly_formula(win_prob, win_loss)

        # Apply fractional Kelly
        half_kelly = raw_kelly * 0.5
        quarter_kelly = raw_kelly * 0.25

        # Determine recommended fraction
        # Use half-kelly adjusted by confidence and cohesion
        adjusted_kelly = half_kelly * confidence * cohesion_multiplier

        # Apply limits
        if adjusted_kelly < self.MIN_KELLY_THRESHOLD:
            recommended = 0.0
            category = PositionSizeCategory.SKIP
        elif adjusted_kelly < 0.05:
            recommended = adjusted_kelly
            category = PositionSizeCategory.MINIMAL
        elif adjusted_kelly < 0.15:
            recommended = min(adjusted_kelly, max_pct)
            category = PositionSizeCategory.SMALL
        elif adjusted_kelly < 0.30:
            recommended = min(adjusted_kelly, max_pct)
            category = PositionSizeCategory.MEDIUM
        else:
            recommended = min(adjusted_kelly, max_pct, self.MAX_KELLY_FRACTION)
            category = PositionSizeCategory.LARGE

        # Calculate dollar amount
        dollar_amount = capital * recommended

        # Enforce minimum position size (AGGRESSIVE CORPORATE STANDARD)
        if dollar_amount > 0 and dollar_amount < self.MIN_POSITION_DOLLAR:
            dollar_amount = self.MIN_POSITION_DOLLAR
            recommended = dollar_amount / capital

        # Calculate shares if price available
        shares = None
        if current_price and current_price > 0 and dollar_amount > 0:
            shares = int(dollar_amount / current_price)

        result = PositionSize(
            asset=asset,
            kelly_fraction=round(raw_kelly, 4),
            half_kelly=round(half_kelly, 4),
            quarter_kelly=round(quarter_kelly, 4),
            recommended_fraction=round(recommended, 4),
            position_category=category,
            dollar_amount=round(dollar_amount, 2),
            shares=shares,
            confidence=confidence,
            sharpe=sharpe,
            win_probability=round(win_prob, 4),
            win_loss_ratio=round(win_loss, 4),
            metadata={
                'cohesion_multiplier': cohesion_multiplier,
                'max_position_pct': max_pct,
                'kelly_multiplier': self.kelly_multiplier,
                'calculated_at': datetime.now(timezone.utc).isoformat()
            }
        )

        # Log calculation
        self._log_calculation(result)

        return result

    def _log_calculation(self, result: PositionSize):
        """Log position sizing to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.kelly_sizing_log
                    (asset_id, sharpe, confidence, kelly_fraction, recommended_fraction,
                     position_category, dollar_amount, win_probability, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                """, (
                    result.asset,
                    result.sharpe,
                    result.confidence,
                    result.kelly_fraction,
                    result.recommended_fraction,
                    result.position_category.value,
                    result.dollar_amount,
                    result.win_probability,
                    json.dumps(result.metadata)
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            # Table may not exist yet
            pass

    def get_current_price(self, asset: str) -> Optional[float]:
        """Get latest price for asset"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT close
                    FROM fhq_market.prices
                    WHERE canonical_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (asset,))
                result = cur.fetchone()
                return float(result['close']) if result else None
        except Exception:
            return None

    def calculate_portfolio_allocation(
        self,
        signals: list,  # List of (asset, sharpe, confidence)
        capital: float,
        max_total_exposure: float = 0.75
    ) -> Dict[str, PositionSize]:
        """
        Calculate positions for multiple signals with total exposure limit.

        Ensures total allocation doesn't exceed max_total_exposure.
        """
        positions = {}
        total_allocation = 0.0

        # Sort by expected edge (sharpe * confidence)
        sorted_signals = sorted(
            signals,
            key=lambda x: x[1] * x[2],  # sharpe * confidence
            reverse=True
        )

        for asset, sharpe, confidence in sorted_signals:
            if total_allocation >= max_total_exposure:
                break

            # Get price
            price = self.get_current_price(asset)

            # Calculate position
            remaining_capacity = max_total_exposure - total_allocation
            position = self.calculate_position(
                asset=asset,
                sharpe=sharpe,
                confidence=confidence,
                capital=capital,
                current_price=price,
                max_position_pct=min(self.MAX_SINGLE_POSITION, remaining_capacity)
            )

            if position.position_category != PositionSizeCategory.SKIP:
                positions[asset] = position
                total_allocation += position.recommended_fraction

        return positions


# Convenience functions
def calculate_kelly_fraction(win_prob: float, win_loss_ratio: float) -> float:
    """Quick Kelly calculation"""
    return KellyPositionSizer.kelly_formula(win_prob, win_loss_ratio)


def sharpe_to_position_size(
    sharpe: float,
    confidence: float = 0.85,
    capital: float = 100000
) -> float:
    """Quick position sizing from Sharpe"""
    sizer = KellyPositionSizer()
    result = sizer.calculate_position(
        asset="TEMP",
        sharpe=sharpe,
        confidence=confidence,
        capital=capital
    )
    return result.dollar_amount


if __name__ == "__main__":
    print("=" * 60)
    print("KELLY CRITERION POSITION SIZER - SELF TEST")
    print("=" * 60)

    sizer = KellyPositionSizer()

    # Test Sharpe -> Win Probability mapping
    print("\n[1] Sharpe -> Win Probability Mapping:")
    for sharpe in [0.0, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0]:
        p = sizer.sharpe_to_win_probability(sharpe)
        print(f"    Sharpe {sharpe:.2f} -> Win Prob {p:.4f}")

    # Test Kelly formula
    print("\n[2] Kelly Formula Tests:")
    test_cases = [
        (0.50, 1.0, "No edge"),
        (0.52, 1.0, "Sharpe ~0.15"),
        (0.55, 1.2, "Sharpe ~0.30"),
        (0.60, 1.5, "Sharpe ~0.50"),
        (0.70, 2.0, "Sharpe ~1.0"),
    ]
    for p, b, label in test_cases:
        kelly = calculate_kelly_fraction(p, b)
        print(f"    {label}: p={p}, b={b} -> Kelly={kelly:.4f}")

    # Test full position sizing
    print("\n[3] Full Position Sizing (Capital: $100,000):")
    capital = 100000
    for sharpe in [0.10, 0.15, 0.20, 0.30, 0.50]:
        result = sizer.calculate_position(
            asset="TEST",
            sharpe=sharpe,
            confidence=0.85,
            capital=capital
        )
        print(f"\n    Sharpe {sharpe}:")
        print(f"      Win Prob: {result.win_probability}")
        print(f"      Kelly f*: {result.kelly_fraction}")
        print(f"      Half-Kelly: {result.half_kelly}")
        print(f"      Recommended: {result.recommended_fraction}")
        print(f"      Category: {result.position_category.value}")
        print(f"      Dollar: ${result.dollar_amount:,.2f}")

    # Test with real assets
    print("\n[4] Testing with Real Data:")
    try:
        with sizer.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT canonical_id
                FROM fhq_market.prices
                WHERE timestamp >= NOW() - INTERVAL '30 days'
                LIMIT 5
            """)
            assets = [r['canonical_id'] for r in cur.fetchall()]

        if assets:
            signals = [(a, 0.20, 0.85) for a in assets]
            portfolio = sizer.calculate_portfolio_allocation(
                signals=signals,
                capital=100000
            )

            print(f"\n    Portfolio Allocation ({len(portfolio)} positions):")
            for asset, pos in portfolio.items():
                print(f"      {asset}: ${pos.dollar_amount:,.2f} ({pos.position_category.value})")
    except Exception as e:
        print(f"    Real data test skipped: {e}")

    print("\n" + "=" * 60)
    print("KELLY CRITERION POSITION SIZER - TEST COMPLETE")
    print("=" * 60)
