"""
IoS-021: Information Foraging Orchestrator
==========================================
STIG-2025-001 Phase 4 Component

Implements Information Foraging Theory for optimal research allocation.
Uses Marginal Value Theorem to determine when to switch "patches" (assets/strategies).

Authority: ADR-020 (ACI), EC-021 (InForage), IoS-021
"""

import os
import math
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

logging.basicConfig(level=logging.INFO, format='[IoS-021] %(message)s')
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


@dataclass
class Patch:
    """Research patch (asset or strategy domain)."""
    patch_id: str
    patch_type: str  # ASSET, STRATEGY, SECTOR
    name: str
    current_yield: float  # Alpha generated per unit time
    depletion_rate: float  # How fast yield drops
    travel_cost: float  # Cost to switch to this patch
    time_in_patch: float  # Hours spent in this patch
    total_alpha_harvested: float
    last_visit: datetime
    scent_strength: float  # Information scent (0-1)


@dataclass
class ForagingDecision:
    """Decision to stay or switch patches."""
    action: str  # STAY, SWITCH
    current_patch: str
    target_patch: Optional[str]
    expected_roi: float
    marginal_value: float
    rationale: str


class InformationForagingOrchestrator:
    """
    Implements Information Foraging Theory for FINN research allocation.

    Key Concepts:
    - Patches: Assets or strategy domains that yield alpha
    - Scent: Signals indicating patch quality (news, volatility, regime changes)
    - Marginal Value Theorem: Leave patch when marginal rate drops below average

    The forager (FINN) should leave a patch when:
        dE/dt < E_avg / (t_travel + t_patch)

    Where:
        dE/dt = current marginal energy gain rate
        E_avg = average gain across all patches
        t_travel = time to switch patches
        t_patch = time already in current patch
    """

    def __init__(self):
        self.conn = None
        self.patches: Dict[str, Patch] = {}
        self.average_yield = 0.0
        self.switch_cost_hours = 0.5  # Cost to context-switch

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def load_patches(self):
        """Load all research patches from database."""
        # Asset patches - simplified query without hypothesis join
        sql_assets = """
            SELECT
                a.canonical_id,
                a.sector,
                0 as hypothesis_count,
                0 as validated_count,
                a.updated_at as last_research
            FROM fhq_meta.assets a
            WHERE a.active_flag = true
              AND a.data_quality_status = 'FULL_HISTORY'
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql_assets)
            assets = cur.fetchall()

        for asset in assets:
            cid = asset['canonical_id']
            # Calculate yield based on validation rate
            total = max(asset['hypothesis_count'], 1)
            validated = asset['validated_count']
            yield_rate = validated / total if total > 0 else 0.1

            # Calculate scent based on recency
            days_since = (datetime.now(timezone.utc) - asset['last_research'].replace(tzinfo=timezone.utc)).days
            scent = max(0.1, 1.0 - (days_since / 30))

            self.patches[cid] = Patch(
                patch_id=cid,
                patch_type='ASSET',
                name=cid,
                current_yield=yield_rate,
                depletion_rate=0.1,  # 10% per hour
                travel_cost=self.switch_cost_hours,
                time_in_patch=0,
                total_alpha_harvested=validated * 0.1,  # Proxy for alpha
                last_visit=asset['last_research'],
                scent_strength=scent
            )

        # Strategy patches
        strategies = [
            ('STATARB', 'Statistical Arbitrage', 0.3),
            ('GRID', 'Grid Trading', 0.2),
            ('VBO', 'Volatility Breakout', 0.25),
            ('MEANREV', 'Mean Reversion', 0.2),
            ('CAUSAL', 'Causal Discovery', 0.35)
        ]
        for strat_id, name, base_yield in strategies:
            self.patches[f'STRAT_{strat_id}'] = Patch(
                patch_id=f'STRAT_{strat_id}',
                patch_type='STRATEGY',
                name=name,
                current_yield=base_yield,
                depletion_rate=0.05,
                travel_cost=self.switch_cost_hours * 2,  # Strategy switches cost more
                time_in_patch=0,
                total_alpha_harvested=0,
                last_visit=datetime.now(timezone.utc) - timedelta(hours=24),
                scent_strength=0.5
            )

        # Calculate average yield
        if self.patches:
            self.average_yield = np.mean([p.current_yield for p in self.patches.values()])

        logger.info(f"Loaded {len(self.patches)} patches, avg yield={self.average_yield:.3f}")

    def calculate_marginal_value(self, patch: Patch) -> float:
        """
        Calculate marginal value of staying in current patch.
        Uses exponential depletion model.
        """
        # Yield depletes exponentially with time in patch
        depleted_yield = patch.current_yield * math.exp(-patch.depletion_rate * patch.time_in_patch)
        return depleted_yield

    def calculate_switch_threshold(self, patch: Patch) -> float:
        """
        Calculate threshold below which we should switch patches.
        Based on Marginal Value Theorem.
        """
        if patch.time_in_patch == 0:
            return 0  # Just arrived, don't switch immediately

        # Threshold = average yield / (travel_time + time_in_patch)
        total_time = patch.travel_cost + patch.time_in_patch
        threshold = self.average_yield / total_time if total_time > 0 else self.average_yield

        return threshold

    def update_scent_trails(self):
        """Update scent strength based on market signals."""
        # Query for recent market events that indicate high-yield patches
        sql = """
            SELECT
                canonical_id,
                COUNT(*) as event_count
            FROM fhq_alpha.alpha_signals
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY canonical_id
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql)
                events = cur.fetchall()

            for event in events:
                cid = event['canonical_id']
                if cid in self.patches:
                    # Boost scent based on recent activity
                    self.patches[cid].scent_strength = min(1.0,
                        self.patches[cid].scent_strength + 0.1 * event['event_count'])
        except Exception as e:
            logger.warning(f"Could not update scent trails: {e}")

    def select_best_patch(self, exclude_current: str = None) -> Optional[Patch]:
        """
        Select best patch to switch to based on scent and expected yield.
        """
        candidates = []
        for patch_id, patch in self.patches.items():
            if patch_id == exclude_current:
                continue

            # Score = scent * yield / travel_cost
            if patch.travel_cost > 0:
                score = (patch.scent_strength * patch.current_yield) / patch.travel_cost
            else:
                score = patch.scent_strength * patch.current_yield

            candidates.append((patch, score))

        if not candidates:
            return None

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def decide(self, current_patch_id: str, time_in_patch: float) -> ForagingDecision:
        """
        Decide whether to stay in current patch or switch.

        Args:
            current_patch_id: ID of current research patch
            time_in_patch: Hours spent in current patch

        Returns:
            ForagingDecision with action and target
        """
        if current_patch_id not in self.patches:
            # Unknown patch - select best available
            best = self.select_best_patch()
            return ForagingDecision(
                action='SWITCH',
                current_patch=current_patch_id,
                target_patch=best.patch_id if best else None,
                expected_roi=best.current_yield if best else 0,
                marginal_value=0,
                rationale='Current patch unknown, switching to best available'
            )

        current = self.patches[current_patch_id]
        current.time_in_patch = time_in_patch

        # Calculate marginal value of staying
        marginal = self.calculate_marginal_value(current)
        threshold = self.calculate_switch_threshold(current)

        if marginal >= threshold:
            # Stay in current patch
            return ForagingDecision(
                action='STAY',
                current_patch=current_patch_id,
                target_patch=None,
                expected_roi=marginal,
                marginal_value=marginal,
                rationale=f'Marginal value ({marginal:.3f}) >= threshold ({threshold:.3f})'
            )
        else:
            # Switch to better patch
            best = self.select_best_patch(exclude_current=current_patch_id)
            if best and best.current_yield > marginal:
                return ForagingDecision(
                    action='SWITCH',
                    current_patch=current_patch_id,
                    target_patch=best.patch_id,
                    expected_roi=best.current_yield,
                    marginal_value=marginal,
                    rationale=f'Marginal depleted ({marginal:.3f} < {threshold:.3f}), '
                              f'switching to {best.name} (yield={best.current_yield:.3f})'
                )
            else:
                # No better option, stay but note depletion
                return ForagingDecision(
                    action='STAY',
                    current_patch=current_patch_id,
                    target_patch=None,
                    expected_roi=marginal,
                    marginal_value=marginal,
                    rationale='No better patches available despite depletion'
                )

    def get_research_queue(self, max_patches: int = 10) -> List[Tuple[str, float]]:
        """
        Get prioritized queue of patches to research.
        Returns list of (patch_id, priority_score) tuples.
        """
        scores = []
        for patch_id, patch in self.patches.items():
            # Priority = scent * yield * freshness_bonus
            days_since = (datetime.now(timezone.utc) - patch.last_visit.replace(tzinfo=timezone.utc)).days
            freshness_bonus = 1.0 + (days_since * 0.1)  # Bonus for unvisited patches

            score = patch.scent_strength * patch.current_yield * freshness_bonus
            scores.append((patch_id, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:max_patches]

    def log_foraging_decision(self, decision: ForagingDecision):
        """Log decision to database."""
        sql = """
            INSERT INTO fhq_alpha.foraging_decisions (
                decision_id, action, current_patch, target_patch,
                expected_roi, marginal_value, rationale, created_at
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, %s, %s, NOW()
            )
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    decision.action,
                    decision.current_patch,
                    decision.target_patch,
                    decision.expected_roi,
                    decision.marginal_value,
                    decision.rationale
                ))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Could not log foraging decision: {e}")


def get_foraging_orchestrator() -> InformationForagingOrchestrator:
    """Factory function to get configured orchestrator."""
    orchestrator = InformationForagingOrchestrator()
    orchestrator.connect()
    orchestrator.load_patches()
    orchestrator.update_scent_trails()
    return orchestrator


if __name__ == '__main__':
    orchestrator = get_foraging_orchestrator()

    # Get research queue
    queue = orchestrator.get_research_queue(10)
    logger.info("Research Priority Queue:")
    for patch_id, score in queue:
        logger.info(f"  {patch_id}: {score:.3f}")

    # Test decision
    if queue:
        decision = orchestrator.decide(queue[0][0], time_in_patch=2.0)
        logger.info(f"\nForaging Decision: {decision.action}")
        logger.info(f"  Rationale: {decision.rationale}")

    orchestrator.close()
