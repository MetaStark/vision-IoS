#!/usr/bin/env python3
"""
THOMPSON SAMPLING BANDIT (STIG-2025-001 Compliant)
==================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - RL with Causal Parents
Classification: Tier-1 Cognitive Infrastructure

Purpose:
    Per-regime action selection using Thompson Sampling.
    No deep learning = low cost, interpretable decisions.

Key Insight:
    Instead of complex RL on all prices, use simple bandits
    that learn optimal actions per market regime.

Actions:
    - SIZE_HALF: 0.5x Kelly position
    - SIZE_FULL: 1.0x Kelly position
    - SIZE_AGGRESSIVE: 1.5x Kelly position
    - DELAY_0: Enter immediately
    - DELAY_1: Wait 1 bar
    - DELAY_2: Wait 2 bars

Usage:
    from thompson_bandit import ThompsonBandit, RegimeBanditSystem

    bandit = ThompsonBandit(['SIZE_HALF', 'SIZE_FULL', 'SIZE_AGGRESSIVE'])
    action = bandit.select_action()
    bandit.update(action, reward=0.02)  # 2% return
"""

import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
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


class SizingAction(Enum):
    """Position sizing actions"""
    SIZE_QUARTER = "SIZE_QUARTER"       # 0.25x Kelly
    SIZE_HALF = "SIZE_HALF"             # 0.5x Kelly
    SIZE_FULL = "SIZE_FULL"             # 1.0x Kelly
    SIZE_AGGRESSIVE = "SIZE_AGGRESSIVE" # 1.5x Kelly


class TimingAction(Enum):
    """Entry timing actions"""
    DELAY_0 = "DELAY_0"   # Enter immediately
    DELAY_1 = "DELAY_1"   # Wait 1 bar
    DELAY_2 = "DELAY_2"   # Wait 2 bars
    DELAY_3 = "DELAY_3"   # Wait 3 bars


@dataclass
class BanditState:
    """State of a Thompson Sampling bandit"""
    name: str
    actions: List[str]
    alpha: Dict[str, float]    # Beta prior successes
    beta: Dict[str, float]     # Beta prior failures
    total_pulls: Dict[str, int]
    total_reward: Dict[str, float]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ThompsonBandit:
    """
    Thompson Sampling Multi-Armed Bandit

    Uses Beta distribution for probability estimation.
    Balances exploration vs exploitation automatically.

    Prior: Beta(alpha=1, beta=1) = Uniform[0,1]
    Update:
        - Success: alpha += 1
        - Failure: beta += 1
    """

    def __init__(self, actions: List[str], name: str = "default"):
        self.name = name
        self.actions = actions

        # Initialize uniform priors
        self.alpha = {a: 1.0 for a in actions}
        self.beta = {a: 1.0 for a in actions}

        # Statistics
        self.total_pulls = {a: 0 for a in actions}
        self.total_reward = {a: 0.0 for a in actions}

    def select_action(self) -> str:
        """
        Select action using Thompson Sampling.

        For each arm, sample from Beta(alpha, beta).
        Select arm with highest sample.
        """
        samples = {}
        for action in self.actions:
            # Sample from posterior Beta distribution
            sample = np.random.beta(self.alpha[action], self.beta[action])
            samples[action] = sample

        # Return action with highest sample
        return max(samples, key=samples.get)

    def update(self, action: str, reward: float, threshold: float = 0.0):
        """
        Update bandit with observed reward.

        Args:
            action: The action that was taken
            reward: Observed reward (e.g., trade return)
            threshold: Reward threshold for success (default 0)
        """
        if action not in self.actions:
            return

        self.total_pulls[action] += 1
        self.total_reward[action] += reward

        # Binary success/failure based on threshold
        if reward > threshold:
            self.alpha[action] += 1
        else:
            self.beta[action] += 1

    def update_continuous(self, action: str, reward: float, scale: float = 10.0):
        """
        Update with continuous reward (proportional to magnitude).

        For rewards in [-1, 1] range, scale appropriately.
        """
        if action not in self.actions:
            return

        self.total_pulls[action] += 1
        self.total_reward[action] += reward

        # Convert to success probability
        # reward of 0.05 (5%) -> mostly success
        # reward of -0.02 (-2%) -> mostly failure
        success_prob = 1 / (1 + np.exp(-reward * scale))

        # Fractional update
        self.alpha[action] += success_prob
        self.beta[action] += (1 - success_prob)

    def get_estimated_means(self) -> Dict[str, float]:
        """Get estimated mean reward for each action"""
        return {
            a: self.alpha[a] / (self.alpha[a] + self.beta[a])
            for a in self.actions
        }

    def get_confidence_intervals(self, confidence: float = 0.95) -> Dict[str, Tuple[float, float]]:
        """Get confidence intervals for each action"""
        from scipy.stats import beta as beta_dist

        intervals = {}
        alpha_ci = (1 - confidence) / 2

        for action in self.actions:
            lower = beta_dist.ppf(alpha_ci, self.alpha[action], self.beta[action])
            upper = beta_dist.ppf(1 - alpha_ci, self.alpha[action], self.beta[action])
            intervals[action] = (round(lower, 4), round(upper, 4))

        return intervals

    def get_state(self) -> BanditState:
        """Get current bandit state"""
        return BanditState(
            name=self.name,
            actions=self.actions,
            alpha=self.alpha.copy(),
            beta=self.beta.copy(),
            total_pulls=self.total_pulls.copy(),
            total_reward=self.total_reward.copy(),
            updated_at=datetime.now(timezone.utc)
        )

    def load_state(self, state: BanditState):
        """Load bandit state"""
        self.name = state.name
        self.actions = state.actions
        self.alpha = state.alpha.copy()
        self.beta = state.beta.copy()
        self.total_pulls = state.total_pulls.copy()
        self.total_reward = state.total_reward.copy()

    def reset(self):
        """Reset to uniform priors"""
        self.alpha = {a: 1.0 for a in self.actions}
        self.beta = {a: 1.0 for a in self.actions}
        self.total_pulls = {a: 0 for a in self.actions}
        self.total_reward = {a: 0.0 for a in self.actions}


class RegimeBanditSystem:
    """
    Per-Regime Bandit System

    Maintains separate bandits for each market regime,
    allowing regime-specific action learning.

    Regimes:
    - BULLISH_TRENDING
    - BEARISH_TRENDING
    - RANGE_BOUND
    - HIGH_VOLATILITY
    - LOW_VOLATILITY
    """

    REGIMES = [
        'BULLISH_TRENDING',
        'BEARISH_TRENDING',
        'RANGE_BOUND',
        'HIGH_VOLATILITY',
        'LOW_VOLATILITY'
    ]

    def __init__(self, strategy: str = "default"):
        self.strategy = strategy
        self.conn = psycopg2.connect(**DB_CONFIG)

        # Sizing bandits per regime
        sizing_actions = [a.value for a in SizingAction]
        self.sizing_bandits = {
            regime: ThompsonBandit(sizing_actions, f"{strategy}_{regime}_sizing")
            for regime in self.REGIMES
        }

        # Timing bandits per regime
        timing_actions = [a.value for a in TimingAction]
        self.timing_bandits = {
            regime: ThompsonBandit(timing_actions, f"{strategy}_{regime}_timing")
            for regime in self.REGIMES
        }

        # Load saved states
        self._load_states()

    def select_actions(self, regime: str) -> Tuple[str, str]:
        """
        Select sizing and timing actions for given regime.

        Returns:
            (sizing_action, timing_action)
        """
        if regime not in self.REGIMES:
            regime = 'RANGE_BOUND'  # Default

        sizing = self.sizing_bandits[regime].select_action()
        timing = self.timing_bandits[regime].select_action()

        return sizing, timing

    def update(self, regime: str, sizing_action: str, timing_action: str, reward: float):
        """Update both bandits with observed reward"""
        if regime not in self.REGIMES:
            regime = 'RANGE_BOUND'

        self.sizing_bandits[regime].update_continuous(sizing_action, reward)
        self.timing_bandits[regime].update_continuous(timing_action, reward)

        # Save states periodically
        total_pulls = sum(
            sum(b.total_pulls.values())
            for b in list(self.sizing_bandits.values()) + list(self.timing_bandits.values())
        )
        if total_pulls % 10 == 0:
            self._save_states()

    def get_recommended_actions(self) -> Dict[str, Dict[str, str]]:
        """Get best actions for each regime based on current estimates"""
        recommendations = {}

        for regime in self.REGIMES:
            sizing_means = self.sizing_bandits[regime].get_estimated_means()
            timing_means = self.timing_bandits[regime].get_estimated_means()

            best_sizing = max(sizing_means, key=sizing_means.get)
            best_timing = max(timing_means, key=timing_means.get)

            recommendations[regime] = {
                'sizing': best_sizing,
                'timing': best_timing,
                'sizing_confidence': round(sizing_means[best_sizing], 4),
                'timing_confidence': round(timing_means[best_timing], 4)
            }

        return recommendations

    def get_statistics(self) -> Dict:
        """Get overall system statistics"""
        stats = {
            'strategy': self.strategy,
            'regimes': {}
        }

        for regime in self.REGIMES:
            sizing_bandit = self.sizing_bandits[regime]
            timing_bandit = self.timing_bandits[regime]

            stats['regimes'][regime] = {
                'sizing': {
                    'total_pulls': sum(sizing_bandit.total_pulls.values()),
                    'means': sizing_bandit.get_estimated_means(),
                    'best': max(sizing_bandit.get_estimated_means(), key=sizing_bandit.get_estimated_means().get)
                },
                'timing': {
                    'total_pulls': sum(timing_bandit.total_pulls.values()),
                    'means': timing_bandit.get_estimated_means(),
                    'best': max(timing_bandit.get_estimated_means(), key=timing_bandit.get_estimated_means().get)
                }
            }

        return stats

    def _save_states(self):
        """Save bandit states to database"""
        try:
            with self.conn.cursor() as cur:
                for regime in self.REGIMES:
                    # Save sizing bandit
                    sizing_state = self.sizing_bandits[regime].get_state()
                    cur.execute("""
                        INSERT INTO fhq_cognition.bandit_states
                        (bandit_name, strategy, regime, bandit_type, alpha, beta,
                         total_pulls, total_reward, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (bandit_name) DO UPDATE SET
                            alpha = EXCLUDED.alpha,
                            beta = EXCLUDED.beta,
                            total_pulls = EXCLUDED.total_pulls,
                            total_reward = EXCLUDED.total_reward,
                            updated_at = NOW()
                    """, (
                        sizing_state.name,
                        self.strategy,
                        regime,
                        'sizing',
                        json.dumps(sizing_state.alpha),
                        json.dumps(sizing_state.beta),
                        json.dumps(sizing_state.total_pulls),
                        json.dumps(sizing_state.total_reward)
                    ))

                    # Save timing bandit
                    timing_state = self.timing_bandits[regime].get_state()
                    cur.execute("""
                        INSERT INTO fhq_cognition.bandit_states
                        (bandit_name, strategy, regime, bandit_type, alpha, beta,
                         total_pulls, total_reward, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (bandit_name) DO UPDATE SET
                            alpha = EXCLUDED.alpha,
                            beta = EXCLUDED.beta,
                            total_pulls = EXCLUDED.total_pulls,
                            total_reward = EXCLUDED.total_reward,
                            updated_at = NOW()
                    """, (
                        timing_state.name,
                        self.strategy,
                        regime,
                        'timing',
                        json.dumps(timing_state.alpha),
                        json.dumps(timing_state.beta),
                        json.dumps(timing_state.total_pulls),
                        json.dumps(timing_state.total_reward)
                    ))

                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass

    def _load_states(self):
        """Load bandit states from database"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT bandit_name, regime, bandit_type, alpha, beta,
                           total_pulls, total_reward
                    FROM fhq_cognition.bandit_states
                    WHERE strategy = %s
                """, (self.strategy,))
                rows = cur.fetchall()

            for row in rows:
                regime = row['regime']
                bandit_type = row['bandit_type']

                alpha = json.loads(row['alpha']) if isinstance(row['alpha'], str) else row['alpha']
                beta = json.loads(row['beta']) if isinstance(row['beta'], str) else row['beta']
                pulls = json.loads(row['total_pulls']) if isinstance(row['total_pulls'], str) else row['total_pulls']
                reward = json.loads(row['total_reward']) if isinstance(row['total_reward'], str) else row['total_reward']

                if bandit_type == 'sizing' and regime in self.sizing_bandits:
                    bandit = self.sizing_bandits[regime]
                    bandit.alpha = alpha
                    bandit.beta = beta
                    bandit.total_pulls = pulls
                    bandit.total_reward = reward

                elif bandit_type == 'timing' and regime in self.timing_bandits:
                    bandit = self.timing_bandits[regime]
                    bandit.alpha = alpha
                    bandit.beta = beta
                    bandit.total_pulls = pulls
                    bandit.total_reward = reward

        except Exception:
            pass


if __name__ == "__main__":
    print("=" * 60)
    print("THOMPSON SAMPLING BANDIT - SELF TEST")
    print("=" * 60)

    # Test single bandit
    print("\n[1] Single Bandit Test...")
    actions = ['A', 'B', 'C']
    bandit = ThompsonBandit(actions, "test")

    # Simulate: A has 60% win rate, B has 40%, C has 50%
    true_probs = {'A': 0.6, 'B': 0.4, 'C': 0.5}

    for i in range(100):
        action = bandit.select_action()
        reward = 1 if np.random.random() < true_probs[action] else 0
        bandit.update(action, reward, threshold=0.5)

    print(f"   True probs: {true_probs}")
    print(f"   Estimated:  {bandit.get_estimated_means()}")
    print(f"   Pulls:      {bandit.total_pulls}")

    # Test regime system
    print("\n[2] Regime Bandit System Test...")
    system = RegimeBanditSystem(strategy="test_strategy")

    # Simulate trading in different regimes
    regime_rewards = {
        'BULLISH_TRENDING': 0.02,    # 2% avg return
        'BEARISH_TRENDING': -0.01,   # -1% avg return
        'RANGE_BOUND': 0.005,        # 0.5% avg return
        'HIGH_VOLATILITY': 0.03,     # 3% avg return (with risk)
        'LOW_VOLATILITY': 0.002      # 0.2% avg return
    }

    for _ in range(50):
        for regime in system.REGIMES:
            sizing, timing = system.select_actions(regime)
            # Simulated reward with noise
            base_reward = regime_rewards[regime]
            noise = np.random.normal(0, 0.01)
            reward = base_reward + noise

            system.update(regime, sizing, timing, reward)

    print("\n[3] Recommended Actions per Regime:")
    recommendations = system.get_recommended_actions()
    for regime, rec in recommendations.items():
        print(f"   {regime}:")
        print(f"      Sizing: {rec['sizing']} (conf={rec['sizing_confidence']:.3f})")
        print(f"      Timing: {rec['timing']} (conf={rec['timing_confidence']:.3f})")

    print("\n[4] System Statistics:")
    stats = system.get_statistics()
    for regime, data in stats['regimes'].items():
        pulls = data['sizing']['total_pulls'] + data['timing']['total_pulls']
        print(f"   {regime}: {pulls} total pulls")

    print("\n" + "=" * 60)
    print("THOMPSON SAMPLING BANDIT - TEST COMPLETE")
    print("=" * 60)
