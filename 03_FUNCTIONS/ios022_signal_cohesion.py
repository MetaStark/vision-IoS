#!/usr/bin/env python3
"""
IoS-022 SIGNAL COHESION ENGINE (STIG-2025-001 Compliant)
========================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - Signal Cohesion Score
Classification: Tier-1 Risk Management Critical

Purpose:
    Prevent "Diworsification" - accumulating many correlated positions
    that provide false sense of diversification.

Implementation:
    Pre-trade correlation check rejects signals with correlation > 0.7
    to existing portfolio positions.

Usage:
    from ios022_signal_cohesion import SignalCohesionEngine, check_signal_cohesion

    engine = SignalCohesionEngine()
    result = engine.check_cohesion('AAPL', portfolio=['MSFT', 'GOOGL'])
    # Returns: APPROVED_DIVERSIFYING, APPROVED_WITH_SIZE_REDUCTION, or REJECTED_REDUNDANT
"""

import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class CohesionDecision(Enum):
    """Signal cohesion decisions per STIG-2025-001"""
    APPROVED_DIVERSIFYING = "APPROVED_DIVERSIFYING"         # Correlation < 0.5
    APPROVED_WITH_SIZE_REDUCTION = "APPROVED_SIZE_REDUCED"  # 0.5 <= Correlation < 0.7
    REJECTED_REDUNDANT = "REJECTED_REDUNDANT"               # Correlation >= 0.7


@dataclass
class CohesionResult:
    """Result of signal cohesion check"""
    asset: str
    decision: CohesionDecision
    avg_correlation: float
    max_correlation: float
    max_correlated_asset: Optional[str]
    size_multiplier: float  # 1.0 = full size, 0.5 = half size, 0.0 = rejected
    correlation_matrix: Dict[str, float]
    checked_at: datetime


class SignalCohesionEngine:
    """
    Signal Cohesion Engine (STIG-2025-001)

    Prevents portfolio "diworsification" by checking new signal correlation
    against existing portfolio positions.

    Thresholds:
    - correlation < 0.5: APPROVED_DIVERSIFYING (full size)
    - 0.5 <= correlation < 0.7: APPROVED_SIZE_REDUCED (50% size)
    - correlation >= 0.7: REJECTED_REDUNDANT (0% - blocked)
    """

    # STIG-2025-001 Mandatory Thresholds
    REJECT_THRESHOLD = 0.7      # Above this = REJECTED
    REDUCE_THRESHOLD = 0.5      # Above this = SIZE_REDUCED
    LOOKBACK_DAYS = 30          # Rolling correlation window

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self._correlation_cache: Dict[str, Dict[str, float]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=1)

    def _get_returns(self, assets: List[str], days: int = 30) -> Dict[str, np.ndarray]:
        """Fetch daily returns for assets"""
        returns = {}

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            for asset in assets:
                cur.execute("""
                    SELECT timestamp::date as date, close
                    FROM fhq_market.prices
                    WHERE canonical_id = %s
                      AND timestamp >= NOW() - INTERVAL '%s days'
                    ORDER BY timestamp
                """, (asset, days + 5))  # Extra days for return calc

                rows = cur.fetchall()
                if len(rows) >= 2:
                    closes = np.array([float(r['close']) for r in rows])
                    daily_returns = np.diff(np.log(closes))
                    returns[asset] = daily_returns

        return returns

    def _calculate_correlation(self, returns_a: np.ndarray, returns_b: np.ndarray) -> float:
        """Calculate Pearson correlation between two return series"""
        # Align lengths
        min_len = min(len(returns_a), len(returns_b))
        if min_len < 5:
            return 0.0  # Insufficient data

        a = returns_a[-min_len:]
        b = returns_b[-min_len:]

        # Handle edge cases
        if np.std(a) == 0 or np.std(b) == 0:
            return 0.0

        correlation = np.corrcoef(a, b)[0, 1]

        # Handle NaN
        if np.isnan(correlation):
            return 0.0

        return float(correlation)

    def _build_correlation_matrix(self, assets: List[str]) -> Dict[str, Dict[str, float]]:
        """Build correlation matrix for all assets"""
        returns = self._get_returns(assets, self.LOOKBACK_DAYS)

        matrix = {}
        for asset_a in assets:
            matrix[asset_a] = {}
            if asset_a not in returns:
                continue

            for asset_b in assets:
                if asset_b not in returns:
                    matrix[asset_a][asset_b] = 0.0
                elif asset_a == asset_b:
                    matrix[asset_a][asset_b] = 1.0
                else:
                    matrix[asset_a][asset_b] = self._calculate_correlation(
                        returns[asset_a], returns[asset_b]
                    )

        return matrix

    def check_cohesion(
        self,
        new_asset: str,
        portfolio: List[str],
        use_cache: bool = True
    ) -> CohesionResult:
        """
        Check if new asset signal is cohesive with existing portfolio.

        Args:
            new_asset: Asset to check (e.g., 'AAPL')
            portfolio: List of currently held assets
            use_cache: Whether to use cached correlation data

        Returns:
            CohesionResult with decision and metrics
        """
        # Empty portfolio = always approve
        if not portfolio:
            return CohesionResult(
                asset=new_asset,
                decision=CohesionDecision.APPROVED_DIVERSIFYING,
                avg_correlation=0.0,
                max_correlation=0.0,
                max_correlated_asset=None,
                size_multiplier=1.0,
                correlation_matrix={},
                checked_at=datetime.now(timezone.utc)
            )

        # Check cache
        if use_cache and self._cache_timestamp:
            cache_age = datetime.now(timezone.utc) - self._cache_timestamp
            if cache_age > self._cache_ttl:
                self._correlation_cache = {}

        # Build correlation matrix
        all_assets = list(set([new_asset] + portfolio))

        if not use_cache or new_asset not in self._correlation_cache:
            matrix = self._build_correlation_matrix(all_assets)
            for asset, correlations in matrix.items():
                self._correlation_cache[asset] = correlations
            self._cache_timestamp = datetime.now(timezone.utc)

        # Calculate correlations with portfolio
        correlations = {}
        for port_asset in portfolio:
            if port_asset == new_asset:
                continue
            if new_asset in self._correlation_cache:
                corr = self._correlation_cache[new_asset].get(port_asset, 0.0)
            else:
                corr = 0.0
            correlations[port_asset] = abs(corr)  # Use absolute correlation

        # Compute metrics
        if correlations:
            avg_corr = np.mean(list(correlations.values()))
            max_corr = max(correlations.values())
            max_asset = max(correlations, key=correlations.get)
        else:
            avg_corr = 0.0
            max_corr = 0.0
            max_asset = None

        # Make decision per STIG-2025-001
        if max_corr >= self.REJECT_THRESHOLD:
            decision = CohesionDecision.REJECTED_REDUNDANT
            size_mult = 0.0
        elif avg_corr >= self.REDUCE_THRESHOLD:
            decision = CohesionDecision.APPROVED_WITH_SIZE_REDUCTION
            size_mult = 0.5
        else:
            decision = CohesionDecision.APPROVED_DIVERSIFYING
            size_mult = 1.0

        result = CohesionResult(
            asset=new_asset,
            decision=decision,
            avg_correlation=round(avg_corr, 4),
            max_correlation=round(max_corr, 4),
            max_correlated_asset=max_asset,
            size_multiplier=size_mult,
            correlation_matrix=correlations,
            checked_at=datetime.now(timezone.utc)
        )

        # Log to database
        self._log_cohesion_check(result)

        return result

    def _log_cohesion_check(self, result: CohesionResult):
        """Log cohesion check to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.signal_cohesion_log
                    (asset_id, decision, avg_correlation, max_correlation,
                     max_correlated_asset, size_multiplier, correlation_matrix, checked_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    result.asset,
                    result.decision.value,
                    result.avg_correlation,
                    result.max_correlation,
                    result.max_correlated_asset,
                    result.size_multiplier,
                    json.dumps(result.correlation_matrix),
                    result.checked_at
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"[COHESION] Log error: {e}")

    def get_portfolio_correlation_matrix(self, portfolio: List[str]) -> Dict[str, Dict[str, float]]:
        """Get full correlation matrix for portfolio"""
        return self._build_correlation_matrix(portfolio)

    def find_diversifying_assets(
        self,
        portfolio: List[str],
        candidates: List[str],
        max_results: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Find candidate assets that would diversify the portfolio.

        Returns list of (asset, avg_correlation) sorted by lowest correlation.
        """
        results = []

        for candidate in candidates:
            if candidate in portfolio:
                continue

            check = self.check_cohesion(candidate, portfolio)
            if check.decision != CohesionDecision.REJECTED_REDUNDANT:
                results.append((candidate, check.avg_correlation))

        # Sort by lowest correlation
        results.sort(key=lambda x: x[1])

        return results[:max_results]


# Convenience function
def check_signal_cohesion(
    asset: str,
    portfolio: List[str]
) -> CohesionResult:
    """Quick cohesion check without engine initialization"""
    engine = SignalCohesionEngine()
    return engine.check_cohesion(asset, portfolio)


if __name__ == "__main__":
    print("=" * 60)
    print("IoS-022 SIGNAL COHESION ENGINE - SELF TEST")
    print("=" * 60)

    engine = SignalCohesionEngine()

    # Test with real data
    print("\n[1] Checking asset universe...")

    with engine.conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT canonical_id
            FROM fhq_market.prices
            WHERE timestamp >= NOW() - INTERVAL '60 days'
            ORDER BY canonical_id
            LIMIT 10
        """)
        assets = [r['canonical_id'] for r in cur.fetchall()]

    print(f"    Found {len(assets)} active assets: {assets[:5]}...")

    if len(assets) >= 3:
        portfolio = assets[:3]
        candidate = assets[4] if len(assets) > 4 else assets[0]

        print(f"\n[2] Testing cohesion check...")
        print(f"    Portfolio: {portfolio}")
        print(f"    Candidate: {candidate}")

        result = engine.check_cohesion(candidate, portfolio)

        print(f"\n[3] Result:")
        print(f"    Decision: {result.decision.value}")
        print(f"    Avg Correlation: {result.avg_correlation:.4f}")
        print(f"    Max Correlation: {result.max_correlation:.4f}")
        print(f"    Max Correlated: {result.max_correlated_asset}")
        print(f"    Size Multiplier: {result.size_multiplier}")

        print(f"\n[4] Correlation Matrix:")
        for asset, corr in result.correlation_matrix.items():
            print(f"    {candidate} <-> {asset}: {corr:.4f}")

        print(f"\n[5] Finding diversifying assets...")
        diversifiers = engine.find_diversifying_assets(portfolio, assets)
        for asset, corr in diversifiers[:5]:
            print(f"    {asset}: avg_corr={corr:.4f}")

    else:
        print("    Insufficient assets for test")

    print("\n" + "=" * 60)
    print("IoS-022 SIGNAL COHESION ENGINE - TEST COMPLETE")
    print("=" * 60)
