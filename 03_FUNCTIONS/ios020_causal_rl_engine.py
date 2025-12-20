#!/usr/bin/env python3
"""
IoS-020 CAUSAL RL ENGINE (STIG-2025-001 Compliant)
==================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - Causal RL with Thompson Sampling
Classification: Tier-1 Cognitive Alpha

Purpose:
    Reinforcement Learning that uses ONLY causal parents as state inputs.
    Solves the "noisy state" problem in financial RL by drastically reducing
    state dimensionality through causal filtering.

Key Insight:
    RL agent for asset 'XOM' (Exxon) only sees:
    - Oil Futures (Causal Parent, discovered by PCMCI)
    - S&P 500 (Causal Parent)
    - Energy Cluster Centroid

    NOT all 500 prices!

Components:
    1. CausalStateBuilder - Constructs state from causal parents only
    2. CausalRLAgent - Per-asset RL agent with regime-aware action selection
    3. PortfolioRL - Orchestrates multiple CausalRLAgents
    4. RewardCalculator - Computes risk-adjusted rewards

Usage:
    from ios020_causal_rl_engine import CausalRLEngine

    engine = CausalRLEngine()
    actions = engine.get_portfolio_actions(['AAPL', 'XOM', 'GOOGL'])
"""

import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from dotenv import load_dotenv

# Import dependencies
try:
    from thompson_bandit import (
        ThompsonBandit,
        SizingAction,
        TimingAction,
        RegimeAwareBandit
    )
    THOMPSON_AVAILABLE = True
except ImportError:
    THOMPSON_AVAILABLE = False

try:
    from ios019_cluster_causal_engine import ClusterCausalEngine
    CAUSAL_AVAILABLE = True
except ImportError:
    CAUSAL_AVAILABLE = False

try:
    from ios003_advanced_regime import AdvancedRegimeClassifier
    REGIME_AVAILABLE = True
except ImportError:
    REGIME_AVAILABLE = False

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class RLAction(Enum):
    """Combined action for position sizing and timing"""
    # Sizing actions
    SIZE_SKIP = "SIZE_SKIP"           # Skip this signal
    SIZE_QUARTER = "SIZE_QUARTER"     # 0.25x Kelly
    SIZE_HALF = "SIZE_HALF"           # 0.5x Kelly
    SIZE_FULL = "SIZE_FULL"           # 1.0x Kelly
    SIZE_AGGRESSIVE = "SIZE_AGGRESSIVE"  # 1.5x Kelly (causal boost)

    # Timing actions
    ENTER_NOW = "ENTER_NOW"           # Execute immediately
    DELAY_1 = "DELAY_1"               # Wait 1 bar
    DELAY_2 = "DELAY_2"               # Wait 2 bars
    DELAY_3 = "DELAY_3"               # Wait 3 bars


@dataclass
class CausalState:
    """State representation using only causal parents"""
    asset: str
    parents: List[str]
    parent_returns: Dict[str, float]
    parent_volatilities: Dict[str, float]
    parent_regimes: Dict[str, str]
    cluster_centroid_return: float
    own_return: float
    own_volatility: float
    own_regime: str
    timestamp: datetime

    def to_vector(self) -> np.ndarray:
        """Convert state to numerical vector for RL"""
        features = []

        # Parent features (3 per parent: return, vol, regime_encoded)
        for parent in sorted(self.parents):
            features.append(self.parent_returns.get(parent, 0))
            features.append(self.parent_volatilities.get(parent, 0))
            regime = self.parent_regimes.get(parent, 'UNKNOWN')
            features.append(self._encode_regime(regime))

        # Own features
        features.append(self.own_return)
        features.append(self.own_volatility)
        features.append(self._encode_regime(self.own_regime))

        # Cluster centroid
        features.append(self.cluster_centroid_return)

        return np.array(features)

    @staticmethod
    def _encode_regime(regime: str) -> float:
        """Encode regime as numerical value"""
        encoding = {
            'STRONG_TREND': 1.0,
            'MODERATE_TREND': 0.66,
            'WEAK_TREND': 0.33,
            'RANGE_BOUND': 0.0,
            'UNKNOWN': 0.5
        }
        return encoding.get(regime, 0.5)


@dataclass
class RLDecision:
    """RL decision output"""
    asset: str
    sizing_action: str
    timing_action: str
    sizing_multiplier: float
    delay_bars: int
    confidence: float
    causal_parents: List[str]
    state_dim: int
    regime: str
    generated_at: datetime


@dataclass
class RewardSignal:
    """Reward signal for RL update"""
    asset: str
    action_taken: str
    pnl: float
    risk_adjusted_return: float
    holding_period: int
    regime_at_entry: str
    regime_at_exit: str
    causal_alignment: float  # Did causal parents predict correctly?


class CausalStateBuilder:
    """
    Builds RL state from causal parents only.

    This is the key innovation - instead of feeding all 500 prices
    to a neural net, we only observe causal parents discovered by PCMCI.
    """

    LOOKBACK_DAYS = 20

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self._causal_cache = {}
        self._regime_cache = {}

    def get_causal_parents(self, asset: str) -> List[str]:
        """Get causal parents from PCMCI discovery"""
        if asset in self._causal_cache:
            return self._causal_cache[asset]

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check micro edges first (asset-level causality)
            cur.execute("""
                SELECT source_asset
                FROM fhq_alpha.micro_causal_edges
                WHERE target_asset = %s
                  AND edge_strength > 0.1
                ORDER BY edge_strength DESC
                LIMIT 5
            """, (asset,))

            parents = [r['source_asset'] for r in cur.fetchall()]

            # If no micro edges, check macro (cluster-level)
            if not parents:
                cur.execute("""
                    SELECT me.source_cluster_id
                    FROM fhq_alpha.macro_causal_edges me
                    JOIN fhq_alpha.asset_clusters ac ON ac.cluster_id = me.target_cluster_id
                    WHERE ac.asset_id = %s
                      AND me.edge_strength > 0.1
                    ORDER BY me.edge_strength DESC
                    LIMIT 3
                """, (asset,))

                # Get representative assets from parent clusters
                cluster_parents = [r['source_cluster_id'] for r in cur.fetchall()]
                for cluster_id in cluster_parents:
                    cur.execute("""
                        SELECT asset_id
                        FROM fhq_alpha.asset_clusters
                        WHERE cluster_id = %s
                        ORDER BY RANDOM()
                        LIMIT 1
                    """, (cluster_id,))
                    result = cur.fetchone()
                    if result:
                        parents.append(result['asset_id'])

        self._causal_cache[asset] = parents
        return parents

    def get_cluster_centroid_return(self, asset: str) -> float:
        """Get return of asset's cluster centroid"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT centroid_return
                FROM fhq_alpha.cluster_centroids cc
                JOIN fhq_alpha.asset_clusters ac ON ac.cluster_id = cc.cluster_id
                WHERE ac.asset_id = %s
                ORDER BY cc.calculated_at DESC
                LIMIT 1
            """, (asset,))

            result = cur.fetchone()
            return result['centroid_return'] if result else 0.0

    def _get_returns(self, asset: str, days: int = 1) -> float:
        """Get recent returns"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT close
                FROM fhq_market.prices
                WHERE canonical_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (asset, days + 1))

            rows = cur.fetchall()
            if len(rows) < 2:
                return 0.0

            return (float(rows[0]['close']) / float(rows[-1]['close'])) - 1

    def _get_volatility(self, asset: str, days: int = 20) -> float:
        """Get rolling volatility"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT close
                FROM fhq_market.prices
                WHERE canonical_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (asset, days + 1))

            rows = cur.fetchall()
            if len(rows) < 5:
                return 0.0

            closes = np.array([float(r['close']) for r in rows])
            returns = np.diff(np.log(closes))
            return float(np.std(returns) * np.sqrt(252))

    def _get_regime(self, asset: str) -> str:
        """Get current regime"""
        if asset in self._regime_cache:
            return self._regime_cache[asset]

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT trend_regime
                FROM fhq_perception.advanced_regime_log
                WHERE asset_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (asset,))

            result = cur.fetchone()
            regime = result['trend_regime'] if result else 'UNKNOWN'
            self._regime_cache[asset] = regime
            return regime

    def build_state(self, asset: str) -> CausalState:
        """Build causal state for asset"""
        parents = self.get_causal_parents(asset)

        # Get parent features
        parent_returns = {}
        parent_volatilities = {}
        parent_regimes = {}

        for parent in parents:
            parent_returns[parent] = self._get_returns(parent)
            parent_volatilities[parent] = self._get_volatility(parent)
            parent_regimes[parent] = self._get_regime(parent)

        # Get own features
        own_return = self._get_returns(asset)
        own_volatility = self._get_volatility(asset)
        own_regime = self._get_regime(asset)

        # Get cluster centroid
        cluster_return = self.get_cluster_centroid_return(asset)

        return CausalState(
            asset=asset,
            parents=parents,
            parent_returns=parent_returns,
            parent_volatilities=parent_volatilities,
            parent_regimes=parent_regimes,
            cluster_centroid_return=cluster_return,
            own_return=own_return,
            own_volatility=own_volatility,
            own_regime=own_regime,
            timestamp=datetime.now(timezone.utc)
        )


class CausalRLAgent:
    """
    Single-asset RL agent using Thompson Sampling.

    Uses regime-aware bandits for action selection with
    state constructed from causal parents only.
    """

    SIZING_MULTIPLIERS = {
        'SIZE_SKIP': 0.0,
        'SIZE_QUARTER': 0.25,
        'SIZE_HALF': 0.5,
        'SIZE_FULL': 1.0,
        'SIZE_AGGRESSIVE': 1.5
    }

    TIMING_DELAYS = {
        'DELAY_0': 0,
        'DELAY_1': 1,
        'DELAY_2': 2,
        'DELAY_3': 3
    }

    def __init__(self, asset: str):
        self.asset = asset
        self.state_builder = CausalStateBuilder()

        if THOMPSON_AVAILABLE:
            self.sizing_bandit = RegimeAwareBandit(
                actions=[SizingAction.QUARTER, SizingAction.HALF,
                        SizingAction.FULL, SizingAction.AGGRESSIVE],
                regimes=['STRONG_TREND', 'MODERATE_TREND', 'WEAK_TREND', 'RANGE_BOUND']
            )
            self.timing_bandit = RegimeAwareBandit(
                actions=[TimingAction.DELAY_0, TimingAction.DELAY_1,
                        TimingAction.DELAY_2, TimingAction.DELAY_3],
                regimes=['STRONG_TREND', 'MODERATE_TREND', 'WEAK_TREND', 'RANGE_BOUND']
            )
        else:
            self.sizing_bandit = None
            self.timing_bandit = None

        self._action_history = []

    def select_action(self) -> RLDecision:
        """Select action based on current causal state"""
        state = self.state_builder.build_state(self.asset)
        regime = state.own_regime

        # Select sizing and timing actions
        if self.sizing_bandit:
            sizing_action = self.sizing_bandit.select_action(regime)
            timing_action = self.timing_bandit.select_action(regime)
        else:
            # Default: half Kelly, enter now
            sizing_action = SizingAction.HALF
            timing_action = TimingAction.DELAY_0

        # Apply causal boost if parents aligned
        causal_alignment = self._calculate_causal_alignment(state)
        sizing_multiplier = self.SIZING_MULTIPLIERS.get(sizing_action.value, 0.5)

        if causal_alignment > 0.7:
            # Strong causal signal - boost size
            sizing_multiplier = min(sizing_multiplier * 1.3, 1.5)
        elif causal_alignment < 0.3:
            # Weak causal signal - reduce size
            sizing_multiplier *= 0.5

        delay_bars = self.TIMING_DELAYS.get(timing_action.value, 0)

        # Confidence based on causal alignment and bandit certainty
        confidence = causal_alignment * 0.6 + 0.4  # Base 40% + up to 60% from causal

        decision = RLDecision(
            asset=self.asset,
            sizing_action=sizing_action.value if hasattr(sizing_action, 'value') else str(sizing_action),
            timing_action=timing_action.value if hasattr(timing_action, 'value') else str(timing_action),
            sizing_multiplier=round(sizing_multiplier, 4),
            delay_bars=delay_bars,
            confidence=round(confidence, 4),
            causal_parents=state.parents,
            state_dim=len(state.to_vector()),
            regime=regime,
            generated_at=datetime.now(timezone.utc)
        )

        self._action_history.append(decision)
        return decision

    def _calculate_causal_alignment(self, state: CausalState) -> float:
        """
        Calculate how well causal parents align with own movement.

        High alignment = parents predict our direction
        Low alignment = parents don't explain our movement
        """
        if not state.parents:
            return 0.5  # Neutral if no parents

        own_direction = 1 if state.own_return > 0 else -1

        aligned_count = 0
        for parent in state.parents:
            parent_return = state.parent_returns.get(parent, 0)
            parent_direction = 1 if parent_return > 0 else -1
            if parent_direction == own_direction:
                aligned_count += 1

        return aligned_count / len(state.parents)

    def update(self, reward: RewardSignal):
        """Update bandits based on reward signal"""
        if not self.sizing_bandit:
            return

        regime = reward.regime_at_entry

        # Convert PnL to binary reward for Thompson Sampling
        sizing_reward = 1 if reward.pnl > 0 else 0
        timing_reward = 1 if reward.risk_adjusted_return > 0 else 0

        # Update sizing bandit
        sizing_action = SizingAction(reward.action_taken.split('_')[1]) if 'SIZE_' in reward.action_taken else SizingAction.HALF
        self.sizing_bandit.update(regime, sizing_action, sizing_reward)

        # Update timing bandit (timing is harder to attribute)
        timing_action = TimingAction.DELAY_0  # Default
        self.timing_bandit.update(regime, timing_action, timing_reward)


class CausalRLEngine:
    """
    Portfolio-level RL engine coordinating multiple CausalRLAgents.

    Orchestrates:
    1. Causal discovery (via ClusterCausalEngine)
    2. Per-asset RL agents
    3. Portfolio-level risk constraints
    """

    MAX_AGENTS = 100
    MIN_CAUSAL_PARENTS = 1  # Minimum parents required for RL

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.agents: Dict[str, CausalRLAgent] = {}
        self.causal_engine = ClusterCausalEngine() if CAUSAL_AVAILABLE else None
        self.regime_classifier = AdvancedRegimeClassifier() if REGIME_AVAILABLE else None

    def _ensure_agent(self, asset: str) -> CausalRLAgent:
        """Get or create agent for asset"""
        if asset not in self.agents:
            if len(self.agents) >= self.MAX_AGENTS:
                # Remove least-used agent
                oldest = min(self.agents.keys(),
                           key=lambda a: len(self.agents[a]._action_history))
                del self.agents[oldest]

            self.agents[asset] = CausalRLAgent(asset)

        return self.agents[asset]

    def get_portfolio_actions(self, assets: List[str]) -> List[RLDecision]:
        """Get RL decisions for portfolio of assets"""
        decisions = []

        for asset in assets:
            agent = self._ensure_agent(asset)

            # Check if asset has causal parents
            state_builder = CausalStateBuilder()
            parents = state_builder.get_causal_parents(asset)

            if len(parents) < self.MIN_CAUSAL_PARENTS:
                # Not enough causal structure - skip or use default
                decision = RLDecision(
                    asset=asset,
                    sizing_action='SIZE_HALF',
                    timing_action='DELAY_0',
                    sizing_multiplier=0.5,
                    delay_bars=0,
                    confidence=0.3,  # Low confidence without causal structure
                    causal_parents=[],
                    state_dim=0,
                    regime='UNKNOWN',
                    generated_at=datetime.now(timezone.utc)
                )
            else:
                decision = agent.select_action()

            decisions.append(decision)

            # Log decision
            self._log_decision(decision)

        return decisions

    def _log_decision(self, decision: RLDecision):
        """Log RL decision to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.rl_decisions
                    (asset_id, sizing_action, timing_action, sizing_multiplier,
                     delay_bars, confidence, causal_parents, state_dim, regime,
                     generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    decision.asset,
                    decision.sizing_action,
                    decision.timing_action,
                    decision.sizing_multiplier,
                    decision.delay_bars,
                    decision.confidence,
                    json.dumps(decision.causal_parents),
                    decision.state_dim,
                    decision.regime,
                    decision.generated_at
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass

    def process_reward(self, asset: str, reward: RewardSignal):
        """Process reward signal for asset"""
        if asset in self.agents:
            self.agents[asset].update(reward)
            self._log_reward(reward)

    def _log_reward(self, reward: RewardSignal):
        """Log reward to database"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_alpha.rl_rewards
                    (asset_id, action_taken, pnl, risk_adjusted_return,
                     holding_period, regime_at_entry, regime_at_exit,
                     causal_alignment, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                """, (
                    reward.asset,
                    reward.action_taken,
                    reward.pnl,
                    reward.risk_adjusted_return,
                    reward.holding_period,
                    reward.regime_at_entry,
                    reward.regime_at_exit,
                    reward.causal_alignment
                ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass

    def get_agent_stats(self, asset: str) -> Dict:
        """Get statistics for asset's RL agent"""
        if asset not in self.agents:
            return {}

        agent = self.agents[asset]
        history = agent._action_history

        if not history:
            return {'asset': asset, 'decisions': 0}

        sizing_counts = {}
        timing_counts = {}

        for decision in history:
            sizing_counts[decision.sizing_action] = sizing_counts.get(decision.sizing_action, 0) + 1
            timing_counts[decision.timing_action] = timing_counts.get(decision.timing_action, 0) + 1

        return {
            'asset': asset,
            'decisions': len(history),
            'avg_confidence': np.mean([d.confidence for d in history]),
            'avg_state_dim': np.mean([d.state_dim for d in history]),
            'sizing_distribution': sizing_counts,
            'timing_distribution': timing_counts
        }

    def run_discovery_refresh(self, assets: List[str]) -> Dict:
        """Refresh causal discovery for assets"""
        if not self.causal_engine:
            return {'status': 'UNAVAILABLE', 'reason': 'ClusterCausalEngine not available'}

        # Run cluster causal discovery
        result = self.causal_engine.run_full_discovery(assets)

        # Clear causal cache in state builders
        for agent in self.agents.values():
            agent.state_builder._causal_cache.clear()

        return result


def calculate_reward(
    entry_price: float,
    exit_price: float,
    position_size: float,
    holding_period: int,
    regime_at_entry: str,
    regime_at_exit: str,
    causal_parents_returns: Dict[str, float]
) -> RewardSignal:
    """
    Calculate reward signal from trade outcome.

    Args:
        entry_price: Trade entry price
        exit_price: Trade exit price
        position_size: Dollar amount of position
        holding_period: Bars held
        regime_at_entry: Regime when entered
        regime_at_exit: Regime when exited
        causal_parents_returns: Returns of causal parents during period

    Returns:
        RewardSignal for RL update
    """
    # Calculate PnL
    pnl = position_size * ((exit_price / entry_price) - 1)

    # Risk-adjusted return (simplified Sharpe proxy)
    raw_return = (exit_price / entry_price) - 1
    risk_adjusted = raw_return / (holding_period ** 0.5) if holding_period > 0 else raw_return

    # Causal alignment: did parents predict our return direction?
    our_direction = 1 if exit_price > entry_price else -1
    aligned_parents = sum(
        1 for r in causal_parents_returns.values()
        if (r > 0 and our_direction > 0) or (r < 0 and our_direction < 0)
    )
    causal_alignment = aligned_parents / len(causal_parents_returns) if causal_parents_returns else 0.5

    return RewardSignal(
        asset="",  # Set by caller
        action_taken="",  # Set by caller
        pnl=round(pnl, 2),
        risk_adjusted_return=round(risk_adjusted, 6),
        holding_period=holding_period,
        regime_at_entry=regime_at_entry,
        regime_at_exit=regime_at_exit,
        causal_alignment=round(causal_alignment, 4)
    )


if __name__ == "__main__":
    print("=" * 60)
    print("IoS-020 CAUSAL RL ENGINE - SELF TEST")
    print("=" * 60)

    engine = CausalRLEngine()

    # Get test assets
    print("\n[1] Fetching assets with price data...")
    with engine.conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT canonical_id
            FROM fhq_market.prices
            WHERE timestamp >= NOW() - INTERVAL '60 days'
            ORDER BY canonical_id
            LIMIT 10
        """)
        assets = [r['canonical_id'] for r in cur.fetchall()]

    print(f"   Found {len(assets)} assets: {assets[:5]}...")

    # Build causal state for first asset
    print("\n[2] Building causal state...")
    if assets:
        state_builder = CausalStateBuilder()
        state = state_builder.build_state(assets[0])

        print(f"   Asset: {state.asset}")
        print(f"   Causal Parents: {state.parents}")
        print(f"   Own Return: {state.own_return:.4f}")
        print(f"   Own Volatility: {state.own_volatility:.4f}")
        print(f"   Own Regime: {state.own_regime}")
        print(f"   State Vector Dim: {len(state.to_vector())}")

    # Get RL decisions
    print("\n[3] Getting RL decisions...")
    decisions = engine.get_portfolio_actions(assets[:5])

    for decision in decisions:
        print(f"\n   {decision.asset}:")
        print(f"      Sizing: {decision.sizing_action} ({decision.sizing_multiplier:.2f}x)")
        print(f"      Timing: {decision.timing_action} (delay {decision.delay_bars} bars)")
        print(f"      Confidence: {decision.confidence:.2%}")
        print(f"      Causal Parents: {decision.causal_parents}")
        print(f"      State Dim: {decision.state_dim}")
        print(f"      Regime: {decision.regime}")

    # Test reward calculation
    print("\n[4] Testing reward calculation...")
    test_reward = calculate_reward(
        entry_price=100.0,
        exit_price=105.0,
        position_size=10000.0,
        holding_period=5,
        regime_at_entry='MODERATE_TREND',
        regime_at_exit='STRONG_TREND',
        causal_parents_returns={'SPY': 0.02, 'XLF': 0.01}
    )

    print(f"   PnL: ${test_reward.pnl:.2f}")
    print(f"   Risk-Adjusted Return: {test_reward.risk_adjusted_return:.4f}")
    print(f"   Causal Alignment: {test_reward.causal_alignment:.2%}")

    # Get agent stats
    print("\n[5] Agent statistics...")
    if assets:
        stats = engine.get_agent_stats(assets[0])
        print(f"   {stats}")

    print("\n" + "=" * 60)
    print("IoS-020 CAUSAL RL ENGINE - TEST COMPLETE")
    print("=" * 60)
