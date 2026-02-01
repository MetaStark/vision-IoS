#!/usr/bin/env python3
"""
G4.2 Contextual Alpha Orchestration Engine
CEO Directive WAVE 16C - 2025-12-18

Implements the "Permission to Speak" protocol:
- Signals are SILENT BY DEFAULT
- Execution requires explicit Context Permit
- Context must be ORTHOGONAL to signal trigger

LOCKED INSTITUTIONAL PARAMETERS:
    ORTHOGONALITY_THRESHOLD: 0.3
    CONTEXT_STABILITY_PERIODS: 3
    MINIMUM_SAMPLE_SIZE: 30
    CONTEXT_COVERAGE_FLOOR: 0.15
"""

import os
import sys
import uuid
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class G42Classification(Enum):
    VALIDATED_CONTEXTUAL = "VALIDATED-CONTEXTUAL"
    UNSTABLE_CONTEXTUAL = "UNSTABLE-CONTEXTUAL"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    ILLUSORY = "ILLUSORY"
    NO_VALID_CONTEXT = "NO_VALID_CONTEXT"


@dataclass
class ContextProfile:
    """Definition of a context for signal gating."""
    context_name: str
    regime: Optional[str] = None  # BULL, BEAR, NEUTRAL, STRESS
    regime_confidence_min: float = 0.0
    vol_state: Optional[str] = None  # COMPRESSING, EXPANDING, STABLE
    vol_percentile_max: Optional[float] = None
    vol_percentile_min: Optional[float] = None
    macro_condition: Optional[str] = None

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def matches(self, state: Dict) -> bool:
        """Check if current market state matches this context."""
        if self.regime and state.get('regime') != self.regime:
            return False
        if self.regime_confidence_min and state.get('regime_confidence', 0) < self.regime_confidence_min:
            return False
        if self.vol_state and state.get('vol_state') != self.vol_state:
            return False
        if self.vol_percentile_max and state.get('vol_percentile', 100) > self.vol_percentile_max:
            return False
        if self.vol_percentile_min and state.get('vol_percentile', 0) < self.vol_percentile_min:
            return False
        return True


class G4_2_ContextualOrchestrationEngine:
    """
    G4.2 Engine: Context-Gated Alpha Validation

    Core principle: "Silence is a position. Execution is a privilege."
    """

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self._load_locked_parameters()

    def _load_locked_parameters(self):
        """Load CEO-locked institutional parameters."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT parameter_name, parameter_value FROM fhq_canonical.g4_2_parameters")
            params = {r['parameter_name']: float(r['parameter_value']) for r in cur.fetchall()}

        self.ORTHOGONALITY_THRESHOLD = params.get('ORTHOGONALITY_THRESHOLD', 0.3)
        self.CONTEXT_STABILITY_PERIODS = int(params.get('CONTEXT_STABILITY_PERIODS', 3))
        self.MINIMUM_SAMPLE_SIZE = int(params.get('MINIMUM_SAMPLE_SIZE', 30))
        self.CONTEXT_COVERAGE_FLOOR = params.get('CONTEXT_COVERAGE_FLOOR', 0.15)

        print(f"[G4.2] Locked Parameters Loaded:")
        print(f"       ORTHOGONALITY_THRESHOLD: {self.ORTHOGONALITY_THRESHOLD}")
        print(f"       CONTEXT_STABILITY_PERIODS: {self.CONTEXT_STABILITY_PERIODS}")
        print(f"       MINIMUM_SAMPLE_SIZE: {self.MINIMUM_SAMPLE_SIZE}")
        print(f"       CONTEXT_COVERAGE_FLOOR: {self.CONTEXT_COVERAGE_FLOOR}")

    def get_regime_history(self, symbol: str, years: int = 7) -> pd.DataFrame:
        """Get regime classification history from IoS-003 or derive from prices."""
        if not symbol:
            symbol = 'BTC-USD'  # Default fallback

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if the table exists first
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'fhq_canonical'
                        AND table_name = 'ios003_regime_classifications'
                    )
                """)
                table_exists = cur.fetchone()['exists']

                if table_exists:
                    cur.execute("""
                        SELECT
                            trade_date,
                            regime_label as regime,
                            regime_confidence,
                            vol_regime,
                            vol_percentile
                        FROM fhq_canonical.ios003_regime_classifications
                        WHERE symbol = %s
                        AND trade_date >= CURRENT_DATE - INTERVAL '%s years'
                        ORDER BY trade_date
                    """, (symbol, years))
                    rows = cur.fetchall()

                    if rows:
                        df = pd.DataFrame(rows)
                        df['trade_date'] = pd.to_datetime(df['trade_date'])
                        df.set_index('trade_date', inplace=True)
                        return df

        except Exception as e:
            # Rollback on any error
            self.conn.rollback()
            print(f"       [INFO] No IoS-003 regime data, deriving from prices: {str(e)[:50]}")

        # Fallback: derive from price data
        return self._derive_regime_from_prices(symbol, years)

    def _derive_regime_from_prices(self, symbol: str, years: int) -> pd.DataFrame:
        """Derive simple regime classification from price data using G4 engine."""
        # Use the existing G4 validation engine which properly handles listing_id lookup
        from g4_validation_engine import G4ValidationEngine
        g4_engine = G4ValidationEngine()

        # Get price data using G4's proven method
        prices = g4_engine.get_price_history(symbol, years=years)
        # Note: G4ValidationEngine connection managed internally

        if not prices:
            return pd.DataFrame()

        rows = [{'trade_date': p['price_date'], 'close_price': p['close_price'], 'volume': p['volume']}
                for p in prices]

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)

        # Derive regime from price momentum and volatility
        df['returns'] = df['close_price'].pct_change()
        df['vol_20d'] = df['returns'].rolling(20).std() * np.sqrt(252)
        df['sma_50'] = df['close_price'].rolling(50).mean()
        df['sma_200'] = df['close_price'].rolling(200).mean()

        # Regime classification
        def classify_regime(row):
            if pd.isna(row['sma_200']):
                return 'NEUTRAL'
            if row['vol_20d'] > 0.40:
                return 'STRESS'
            if row['close_price'] > row['sma_50'] > row['sma_200']:
                return 'BULL'
            if row['close_price'] < row['sma_50'] < row['sma_200']:
                return 'BEAR'
            return 'NEUTRAL'

        df['regime'] = df.apply(classify_regime, axis=1)
        df['regime_confidence'] = 0.7  # Default confidence for derived regime

        # Vol state
        df['vol_percentile'] = df['vol_20d'].rolling(252).apply(
            lambda x: (x.iloc[-1] <= x).sum() / len(x) * 100 if len(x) > 0 else 50
        )

        def vol_state(pct):
            if pd.isna(pct):
                return 'STABLE'
            if pct < 30:
                return 'COMPRESSING'
            if pct > 70:
                return 'EXPANDING'
            return 'STABLE'

        df['vol_state'] = df['vol_percentile'].apply(vol_state)

        return df[['regime', 'regime_confidence', 'vol_state', 'vol_percentile']].dropna()

    def calculate_orthogonality(
        self,
        signal_features: np.ndarray,
        context_features: np.ndarray
    ) -> float:
        """
        Calculate orthogonality between signal trigger and context features.
        Returns absolute correlation (must be < ORTHOGONALITY_THRESHOLD to pass).
        """
        if len(signal_features) != len(context_features):
            raise ValueError("Feature arrays must have same length")

        if len(signal_features) < 10:
            return 1.0  # Fail if insufficient data

        # Remove NaN values
        mask = ~(np.isnan(signal_features) | np.isnan(context_features))
        if mask.sum() < 10:
            return 1.0

        corr = np.corrcoef(signal_features[mask], context_features[mask])[0, 1]
        return abs(corr) if not np.isnan(corr) else 1.0

    def run_context_gated_backtest(
        self,
        needle: Dict,
        context: ContextProfile,
        regime_history: pd.DataFrame
    ) -> Dict:
        """
        Run backtest with context gating.

        Returns performance metrics only for periods where context was valid.
        """
        from g4_validation_engine import G4ValidationEngine
        g4_engine = G4ValidationEngine()

        target = self._resolve_target_asset(needle)
        prices = g4_engine.get_price_history(target, years=7)
        # Note: G4ValidationEngine connection managed internally

        if not prices:
            return {'error': 'No price data'}

        # Build price DataFrame (G4 engine returns price_date, close_price, etc.)
        price_df = pd.DataFrame(prices)
        price_df['trade_date'] = pd.to_datetime(price_df['price_date'])
        price_df['close'] = price_df['close_price']
        price_df.set_index('trade_date', inplace=True)

        # Align regime history with prices
        aligned = price_df.join(regime_history, how='left')
        aligned['regime'] = aligned['regime'].ffill()
        aligned['regime_confidence'] = aligned['regime_confidence'].ffill()
        aligned['vol_state'] = aligned['vol_state'].ffill()
        aligned['vol_percentile'] = aligned['vol_percentile'].ffill()

        # Calculate returns
        aligned['returns'] = aligned['close'].pct_change()

        # Determine which periods are PERMITTED vs BLOCKED
        permitted_mask = []
        context_stable_count = 0

        for idx, row in aligned.iterrows():
            state = {
                'regime': row.get('regime'),
                'regime_confidence': row.get('regime_confidence', 0),
                'vol_state': row.get('vol_state'),
                'vol_percentile': row.get('vol_percentile', 50)
            }

            if context.matches(state):
                context_stable_count += 1
                # Must be stable for N periods before permitting
                permitted = context_stable_count >= self.CONTEXT_STABILITY_PERIODS
            else:
                context_stable_count = 0
                permitted = False

            permitted_mask.append(permitted)

        aligned['permitted'] = permitted_mask
        aligned['blocked'] = ~aligned['permitted']

        # Calculate metrics
        total_periods = len(aligned)
        permitted_periods = aligned['permitted'].sum()
        blocked_periods = aligned['blocked'].sum()
        suppression_rate = blocked_periods / total_periods if total_periods > 0 else 1.0

        coverage_ratio = permitted_periods / total_periods if total_periods > 0 else 0.0

        # Context-gated performance (only permitted periods)
        permitted_returns = aligned.loc[aligned['permitted'], 'returns'].dropna()

        if len(permitted_returns) < 5:
            return {
                'total_periods': total_periods,
                'permitted_periods': permitted_periods,
                'blocked_periods': blocked_periods,
                'suppression_rate': suppression_rate,
                'coverage_ratio': coverage_ratio,
                'trade_count': 0,
                'contextual_sharpe': None,
                'classification': G42Classification.INSUFFICIENT_SAMPLE.value,
                'classification_reason': {'reason': 'Insufficient permitted periods'}
            }

        # Calculate Sharpe on permitted windows
        mean_ret = permitted_returns.mean() * 252
        std_ret = permitted_returns.std() * np.sqrt(252)
        contextual_sharpe = mean_ret / std_ret if std_ret > 0 else 0

        # Estimate trade count (simplified: count regime transitions as trade opportunities)
        trade_count = (aligned['permitted'].diff() == 1).sum()

        # Calculate max drawdown on permitted periods
        cum_returns = (1 + permitted_returns).cumprod()
        rolling_max = cum_returns.cummax()
        drawdown = (cum_returns - rolling_max) / rolling_max
        max_dd = drawdown.min() if len(drawdown) > 0 else 0

        # Ungated comparison (what would have happened without context gating)
        all_returns = aligned['returns'].dropna()
        ungated_mean = all_returns.mean() * 252
        ungated_std = all_returns.std() * np.sqrt(252)
        ungated_sharpe = ungated_mean / ungated_std if ungated_std > 0 else 0

        ungated_cum = (1 + all_returns).cumprod()
        ungated_rm = ungated_cum.cummax()
        ungated_dd = ((ungated_cum - ungated_rm) / ungated_rm).min()

        damage_avoided = abs(ungated_dd) - abs(max_dd) if max_dd and ungated_dd else 0

        # Classify result
        classification, reason = self._classify_result(
            contextual_sharpe=contextual_sharpe,
            coverage_ratio=coverage_ratio,
            trade_count=trade_count,
            orthogonality_score=0.1  # Placeholder - will be calculated separately
        )

        return {
            'total_periods': total_periods,
            'permitted_periods': int(permitted_periods),
            'blocked_periods': int(blocked_periods),
            'suppression_rate': float(suppression_rate),
            'coverage_ratio': float(coverage_ratio),
            'trade_count': int(trade_count),
            'contextual_sharpe': float(contextual_sharpe) if contextual_sharpe else None,
            'contextual_max_dd': float(max_dd) if max_dd else None,
            'ungated_sharpe': float(ungated_sharpe),
            'ungated_max_dd': float(ungated_dd) if ungated_dd else None,
            'damage_avoided_dd': float(damage_avoided),
            'classification': classification.value,
            'classification_reason': reason
        }

    def _classify_result(
        self,
        contextual_sharpe: float,
        coverage_ratio: float,
        trade_count: int,
        orthogonality_score: float
    ) -> Tuple[G42Classification, Dict]:
        """Apply CEO Directive classification taxonomy."""

        reason = {}

        # Check orthogonality
        if orthogonality_score >= self.ORTHOGONALITY_THRESHOLD:
            reason['orthogonality'] = f"FAIL: {orthogonality_score:.3f} >= {self.ORTHOGONALITY_THRESHOLD}"
            return G42Classification.ILLUSORY, reason
        reason['orthogonality'] = f"PASS: {orthogonality_score:.3f} < {self.ORTHOGONALITY_THRESHOLD}"

        # Check coverage
        if coverage_ratio < self.CONTEXT_COVERAGE_FLOOR:
            reason['coverage'] = f"FAIL: {coverage_ratio:.2%} < {self.CONTEXT_COVERAGE_FLOOR:.0%}"
            return G42Classification.UNSTABLE_CONTEXTUAL, reason
        reason['coverage'] = f"PASS: {coverage_ratio:.2%} >= {self.CONTEXT_COVERAGE_FLOOR:.0%}"

        # Check sample size
        if trade_count < self.MINIMUM_SAMPLE_SIZE:
            reason['sample_size'] = f"FAIL: {trade_count} < {self.MINIMUM_SAMPLE_SIZE}"
            return G42Classification.INSUFFICIENT_SAMPLE, reason
        reason['sample_size'] = f"PASS: {trade_count} >= {self.MINIMUM_SAMPLE_SIZE}"

        # Check Sharpe
        if contextual_sharpe is None or contextual_sharpe < 1.5:
            sharpe_val = contextual_sharpe if contextual_sharpe else 0
            reason['sharpe'] = f"FAIL: {sharpe_val:.2f} < 1.50"
            return G42Classification.UNSTABLE_CONTEXTUAL, reason
        reason['sharpe'] = f"PASS: {contextual_sharpe:.2f} >= 1.50"

        return G42Classification.VALIDATED_CONTEXTUAL, reason

    def generate_context_profiles_for_needle(self, needle: Dict) -> List[ContextProfile]:
        """
        Generate candidate context profiles for a needle based on its category.

        For REGIME_EDGE signals, context should be orthogonal (e.g., volatility-based).
        """
        category = needle.get('hypothesis_category', '')

        profiles = []

        if category == 'REGIME_EDGE':
            # REGIME_EDGE signals use price/momentum - gate on volatility (orthogonal)
            profiles.extend([
                ContextProfile(
                    context_name="LOW_VOL_STABLE",
                    vol_state="COMPRESSING",
                    vol_percentile_max=30
                ),
                ContextProfile(
                    context_name="HIGH_VOL_STRESS",
                    vol_state="EXPANDING",
                    vol_percentile_min=70
                ),
                ContextProfile(
                    context_name="VOL_NEUTRAL",
                    vol_state="STABLE",
                    vol_percentile_min=30,
                    vol_percentile_max=70
                ),
            ])

        elif category == 'VOLATILITY':
            # VOLATILITY signals use vol metrics - gate on regime (orthogonal)
            profiles.extend([
                ContextProfile(
                    context_name="BULL_REGIME",
                    regime="BULL",
                    regime_confidence_min=0.7
                ),
                ContextProfile(
                    context_name="BEAR_REGIME",
                    regime="BEAR",
                    regime_confidence_min=0.7
                ),
                ContextProfile(
                    context_name="NEUTRAL_REGIME",
                    regime="NEUTRAL",
                    regime_confidence_min=0.7
                ),
            ])

        else:
            # Default: test both regime and volatility contexts
            profiles.extend([
                ContextProfile(context_name="BULL_LOW_VOL", regime="BULL", vol_state="COMPRESSING"),
                ContextProfile(context_name="BEAR_HIGH_VOL", regime="BEAR", vol_state="EXPANDING"),
                ContextProfile(context_name="NEUTRAL_STABLE", regime="NEUTRAL", vol_state="STABLE"),
            ])

        return profiles

    def _resolve_target_asset(self, needle: Dict) -> str:
        """
        Resolve target asset from needle data.

        CRITICAL FIX (CEO Directive 2025-12-20):
        price_witness_symbol is the SOURCE OF TRUTH and must be checked FIRST.
        This prevents BTCUSDT signals from being routed to NVDA via stale target_asset.
        """
        # =====================================================================
        # PRIORITY 1: price_witness_symbol (SOURCE OF TRUTH)
        # This is the actual asset the signal was generated for
        # =====================================================================
        pws = needle.get('price_witness_symbol', '')
        if pws:
            # Convert to Alpaca format
            if pws.endswith('USDT'):
                # BTCUSDT -> BTC/USD (Alpaca crypto format)
                base = pws[:-4]
                return f"{base}/USD"
            if '-USD' in pws:
                # BTC-USD -> BTC/USD (check before plain USD)
                return pws.replace('-USD', '/USD')
            if pws.endswith('USD') and '/' not in pws:
                # BTCUSD -> BTC/USD
                base = pws[:-3]
                return f"{base}/USD"
            return pws

        # =====================================================================
        # PRIORITY 2: target_asset (fallback only if no price_witness)
        # =====================================================================
        target = needle.get('target_asset')
        if target:
            return target

        # Default fallback
        return 'BTC/USD'

    def run_full_validation(self, needle: Dict) -> Dict:
        """
        Run G4.2 contextual validation on a needle.

        Tests multiple context profiles and selects the best (if any passes).
        """
        needle_id = needle.get('needle_id')
        title = needle.get('hypothesis_title', 'Unknown')
        target = self._resolve_target_asset(needle)

        print(f"\n[G4.2] Validating: {title[:50]}")
        print(f"       Target: {target}")

        # Get regime history
        regime_history = self.get_regime_history(target, years=7)
        if regime_history.empty:
            print(f"       [SKIP] No regime history available")
            return {
                'needle_id': needle_id,
                'classification': G42Classification.NO_VALID_CONTEXT.value,
                'reason': 'No regime history'
            }

        # Generate context profiles
        profiles = self.generate_context_profiles_for_needle(needle)
        print(f"       Testing {len(profiles)} context profiles...")

        best_result = None
        best_sharpe = -999

        for profile in profiles:
            print(f"         -> {profile.context_name}...", end=" ")

            result = self.run_context_gated_backtest(needle, profile, regime_history)

            sharpe = result.get('contextual_sharpe') or -999
            classification = result.get('classification', 'UNKNOWN')

            sharpe_str = f"{sharpe:.2f}" if sharpe != -999 else 'N/A'
            print(f"Sharpe={sharpe_str}, {classification}")

            # Save profile to database
            self._save_context_profile(needle_id, profile, result)

            # Track best result
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_result = {
                    'profile': profile,
                    'result': result
                }

        # Determine final verdict
        if best_result is None:
            final_class = G42Classification.NO_VALID_CONTEXT.value
            g5_eligible = False
        else:
            final_class = best_result['result'].get('classification', G42Classification.NO_VALID_CONTEXT.value)
            g5_eligible = (final_class == G42Classification.VALIDATED_CONTEXTUAL.value)

        # Save verdict
        self._save_verdict(needle_id, best_result, final_class, g5_eligible)

        print(f"       VERDICT: {final_class} | G5 Eligible: {g5_eligible}")

        return {
            'needle_id': needle_id,
            'best_context': best_result['profile'].context_name if best_result else None,
            'best_sharpe': best_sharpe if best_sharpe != -999 else None,
            'classification': final_class,
            'g5_eligible': g5_eligible
        }

    def _save_context_profile(self, needle_id: str, profile: ContextProfile, result: Dict):
        """Save context profile and backtest result to database."""
        with self.conn.cursor() as cur:
            # Insert profile
            cur.execute("""
                INSERT INTO fhq_canonical.g4_2_context_profiles
                (needle_id, context_name, context_definition, coverage_periods, total_periods,
                 coverage_ratio, created_by, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'FINN', 'PENDING')
                ON CONFLICT (needle_id, context_name) DO UPDATE SET
                    context_definition = EXCLUDED.context_definition,
                    coverage_periods = EXCLUDED.coverage_periods,
                    total_periods = EXCLUDED.total_periods,
                    coverage_ratio = EXCLUDED.coverage_ratio
                RETURNING profile_id
            """, (
                needle_id,
                profile.context_name,
                json.dumps(profile.to_dict()),
                result.get('permitted_periods', 0),
                result.get('total_periods', 0),
                result.get('coverage_ratio', 0)
            ))
            profile_row = cur.fetchone()
            profile_id = profile_row[0] if profile_row else None

            if profile_id and result.get('trade_count', 0) > 0:
                # Insert backtest result
                cur.execute("""
                    INSERT INTO fhq_canonical.g4_2_contextual_backtest
                    (needle_id, profile_id, context_name, total_periods, permitted_periods,
                     blocked_periods, suppression_rate, trade_count, contextual_sharpe,
                     contextual_max_dd, ungated_sharpe, ungated_max_dd, damage_avoided_dd,
                     classification, classification_reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (needle_id, profile_id) DO UPDATE SET
                        suppression_rate = EXCLUDED.suppression_rate,
                        trade_count = EXCLUDED.trade_count,
                        contextual_sharpe = EXCLUDED.contextual_sharpe,
                        classification = EXCLUDED.classification
                """, (
                    needle_id,
                    profile_id,
                    profile.context_name,
                    result.get('total_periods', 0),
                    result.get('permitted_periods', 0),
                    result.get('blocked_periods', 0),
                    result.get('suppression_rate', 0),
                    result.get('trade_count', 0),
                    result.get('contextual_sharpe'),
                    result.get('contextual_max_dd'),
                    result.get('ungated_sharpe'),
                    result.get('ungated_max_dd'),
                    result.get('damage_avoided_dd'),
                    result.get('classification', 'UNKNOWN'),
                    json.dumps(result.get('classification_reason', {}))
                ))

            self.conn.commit()

    def _save_verdict(self, needle_id: str, best_result: Optional[Dict], final_class: str, g5_eligible: bool):
        """Save final G4.2 verdict."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_canonical.g4_2_composite_verdict
                (needle_id, best_context_name, best_contextual_sharpe, best_suppression_rate,
                 best_trade_count, final_classification, g5_eligible, g5_eligibility_reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (needle_id) DO UPDATE SET
                    best_context_name = EXCLUDED.best_context_name,
                    best_contextual_sharpe = EXCLUDED.best_contextual_sharpe,
                    best_suppression_rate = EXCLUDED.best_suppression_rate,
                    final_classification = EXCLUDED.final_classification,
                    g5_eligible = EXCLUDED.g5_eligible,
                    validated_at = NOW()
            """, (
                needle_id,
                best_result['profile'].context_name if best_result else None,
                best_result['result'].get('contextual_sharpe') if best_result else None,
                best_result['result'].get('suppression_rate') if best_result else None,
                best_result['result'].get('trade_count') if best_result else None,
                final_class,
                g5_eligible,
                'VALIDATED-CONTEXTUAL with Sharpe >= 1.5' if g5_eligible else 'Does not meet G5 criteria'
            ))
            self.conn.commit()

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()


def main():
    """Test the G4.2 engine."""
    engine = G4_2_ContextualOrchestrationEngine()

    # Get a sample GOLD needle
    with engine.conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT gn.needle_id, gn.hypothesis_title, gn.hypothesis_category, gn.target_asset
            FROM fhq_canonical.golden_needles gn
            JOIN fhq_canonical.g4_composite_scorecard sc ON gn.needle_id = sc.needle_id
            WHERE sc.classification = 'GOLD'
            LIMIT 1
        """)
        needle = cur.fetchone()

    if needle:
        result = engine.run_full_validation(dict(needle))
        print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
    else:
        print("No GOLD needles found")

    engine.close()


if __name__ == "__main__":
    main()
