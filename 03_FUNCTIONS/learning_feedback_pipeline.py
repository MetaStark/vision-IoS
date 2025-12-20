#!/usr/bin/env python3
"""
LEARNING FEEDBACK PIPELINE
==========================
Directive: CD-IOS015-ALPACA-PAPER-001, Amendment AMND-006
Classification: G4_LEARNING_ACTIVATION
Date: 2025-12-16

Connects paper trade outcomes to learning systems:
- Thompson Bandit posterior updates
- Causal RL reward / penalty propagation
- Strategy performance statistics

Per Amendment Section 7 (Authorized Learning Sinks):
Only the systems above may consume feedback from the canonical outcome.
The episodic buffer (fhq_sandbox) is wiped on trade close; only the
finalized return flows to canonical learning tables.

Authority: CEO, STIG, VEGA
"""

import os
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor, Json

logging.basicConfig(
    level=logging.INFO,
    format='[LEARNING] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Import learning systems
try:
    from thompson_bandit import RegimeBanditSystem
    BANDIT_AVAILABLE = True
except ImportError:
    BANDIT_AVAILABLE = False
    logger.warning("Thompson Bandit not available")

try:
    from ios020_causal_rl_engine import CausalRLEngine, RewardSignal
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    logger.warning("Causal RL Engine not available")


@dataclass
class TradeOutcome:
    """Trade outcome from paper execution."""
    outcome_id: str
    position_id: str
    canonical_id: str
    strategy_source: str
    side: str
    entry_price: float
    exit_price: float
    realized_pnl: float
    realized_pnl_pct: float
    max_drawdown_pct: float
    hold_duration_minutes: int
    regime_at_entry: str = 'UNKNOWN'
    regime_at_exit: str = 'UNKNOWN'
    sizing_action: str = 'SIZE_HALF'
    timing_action: str = 'DELAY_0'


@dataclass
class LearningUpdate:
    """Record of learning update for audit trail."""
    update_id: str
    outcome_id: str
    learning_system: str
    action: str
    reward: float
    prior_state: Dict
    posterior_state: Dict
    created_at: datetime


class LearningFeedbackPipeline:
    """
    Pipeline that propagates paper trade outcomes to learning systems.

    Flow (per Amendment Section 7):
    1. Trade closes → paper_trade_outcomes table
    2. Pipeline reads outcome
    3. Computes reward signal
    4. Updates Thompson Bandit (sizing/timing priors)
    5. Updates Causal RL (per-asset agent)
    6. Updates Strategy Statistics
    7. Logs all updates to learning_updates table
    """

    # Reward scaling parameters
    PNL_SCALE = 10.0  # Scale factor for converting PnL% to reward
    WIN_THRESHOLD = 0.0  # PnL threshold for binary win/loss

    def __init__(self):
        self.conn = None
        self.bandit_systems: Dict[str, RegimeBanditSystem] = {}
        self.rl_engine = None

    def connect(self):
        """Connect to database and initialize learning systems."""
        self.conn = psycopg2.connect(**DB_CONFIG)

        # Initialize Causal RL if available
        if RL_AVAILABLE:
            self.rl_engine = CausalRLEngine()
            logger.info("Causal RL Engine initialized")

        logger.info("Learning Feedback Pipeline connected")

    def close(self):
        """Close connections."""
        if self.conn:
            self.conn.close()

    def _get_bandit_system(self, strategy: str) -> Optional[RegimeBanditSystem]:
        """Get or create bandit system for strategy."""
        if not BANDIT_AVAILABLE:
            return None

        if strategy not in self.bandit_systems:
            self.bandit_systems[strategy] = RegimeBanditSystem(strategy=strategy)

        return self.bandit_systems[strategy]

    # =========================================================================
    # OUTCOME PROCESSING
    # =========================================================================

    def get_pending_outcomes(self) -> List[TradeOutcome]:
        """Get trade outcomes that haven't been processed for learning."""
        sql = """
            SELECT
                pto.outcome_id::text,
                pto.position_id::text,
                pto.canonical_id,
                pto.strategy_source,
                pto.side,
                pto.entry_price,
                pto.exit_price,
                pto.realized_pnl,
                pto.realized_pnl_pct,
                pto.max_drawdown_pct,
                pto.hold_duration_minutes,
                COALESCE(pto.regime_at_entry, 'UNKNOWN') as regime_at_entry,
                COALESCE(pto.regime_at_exit, 'UNKNOWN') as regime_at_exit
            FROM fhq_execution.paper_trade_outcomes pto
            WHERE pto.learning_applied = false
            ORDER BY pto.created_at ASC
            LIMIT 100
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()

            return [TradeOutcome(**row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching pending outcomes: {e}")
            return []

    def process_outcome(self, outcome: TradeOutcome) -> List[LearningUpdate]:
        """
        Process single trade outcome through all learning systems.

        Per CEO Directive Mandate IV (2025-12-17):
        - Thompson Bandit, Causal RL, Strategy Stats: Direct updates (allowed)
        - Cognitive Engines (IKEA, InForage, SitC): Proposals to staging only

        Returns list of learning updates applied.
        """
        updates = []

        # 1. Thompson Bandit Update (Direct - allowed per Amendment Section 7)
        bandit_update = self._update_thompson_bandit(outcome)
        if bandit_update:
            updates.append(bandit_update)

        # 2. Causal RL Update (Direct - allowed per Amendment Section 7)
        rl_update = self._update_causal_rl(outcome)
        if rl_update:
            updates.append(rl_update)

        # 3. Strategy Statistics Update (Direct - allowed)
        stats_update = self._update_strategy_stats(outcome)
        if stats_update:
            updates.append(stats_update)

        # 4. MANDATE IV: Cognitive Engine Learning Proposals (Staging Only)
        # These DO NOT directly update production - they go to learning_proposals
        # table and require G1/VEGA approval before activation.
        try:
            proposals = self.submit_cognitive_learning_proposals(outcome)
            if proposals:
                # Log that proposals were submitted (not applied)
                proposal_update = LearningUpdate(
                    update_id='',
                    outcome_id=outcome.outcome_id,
                    learning_system='COGNITIVE_PROPOSALS',
                    action='STAGED_FOR_REVIEW',
                    reward=0.0,
                    prior_state={},
                    posterior_state={'proposals': proposals},
                    created_at=datetime.now(timezone.utc)
                )
                updates.append(proposal_update)
        except Exception as e:
            logger.warning(f"Cognitive proposal submission failed: {e}")

        # Mark outcome as processed
        self._mark_outcome_processed(outcome.outcome_id, updates)

        return updates

    # =========================================================================
    # THOMPSON BANDIT UPDATES
    # =========================================================================

    def _update_thompson_bandit(self, outcome: TradeOutcome) -> Optional[LearningUpdate]:
        """
        Update Thompson Bandit with trade outcome.

        Updates both sizing and timing bandits based on PnL.
        """
        bandit_system = self._get_bandit_system(outcome.strategy_source)
        if not bandit_system:
            return None

        # Get prior state
        prior_state = {
            'sizing_means': {},
            'timing_means': {}
        }

        regime = self._map_regime(outcome.regime_at_entry)
        if regime in bandit_system.sizing_bandits:
            prior_state['sizing_means'] = bandit_system.sizing_bandits[regime].get_estimated_means()
        if regime in bandit_system.timing_bandits:
            prior_state['timing_means'] = bandit_system.timing_bandits[regime].get_estimated_means()

        # Convert PnL to reward
        # Positive PnL = success, negative = failure
        reward = outcome.realized_pnl_pct / 100.0  # Convert to decimal

        # Get actions (if not stored, use defaults based on outcome)
        sizing_action = outcome.sizing_action
        timing_action = outcome.timing_action

        # Update bandits
        try:
            bandit_system.update(
                regime=regime,
                sizing_action=sizing_action,
                timing_action=timing_action,
                reward=reward
            )
        except Exception as e:
            logger.error(f"Bandit update failed: {e}")
            return None

        # Get posterior state
        posterior_state = {
            'sizing_means': {},
            'timing_means': {}
        }
        if regime in bandit_system.sizing_bandits:
            posterior_state['sizing_means'] = bandit_system.sizing_bandits[regime].get_estimated_means()
        if regime in bandit_system.timing_bandits:
            posterior_state['timing_means'] = bandit_system.timing_bandits[regime].get_estimated_means()

        update = LearningUpdate(
            update_id='',  # Set by database
            outcome_id=outcome.outcome_id,
            learning_system='THOMPSON_BANDIT',
            action=f"{sizing_action}|{timing_action}",
            reward=reward,
            prior_state=prior_state,
            posterior_state=posterior_state,
            created_at=datetime.now(timezone.utc)
        )

        logger.info(f"Thompson Bandit updated: {outcome.canonical_id} "
                   f"regime={regime} reward={reward:.4f}")

        return update

    def _map_regime(self, regime: str) -> str:
        """Map regime names to bandit system regimes."""
        mapping = {
            'STRONG_TREND': 'BULLISH_TRENDING',
            'MODERATE_TREND': 'BULLISH_TRENDING',
            'WEAK_TREND': 'RANGE_BOUND',
            'RANGE_BOUND': 'RANGE_BOUND',
            'HIGH_VOLATILITY': 'HIGH_VOLATILITY',
            'LOW_VOLATILITY': 'LOW_VOLATILITY',
            'BULLISH_TRENDING': 'BULLISH_TRENDING',
            'BEARISH_TRENDING': 'BEARISH_TRENDING',
            'UNKNOWN': 'RANGE_BOUND'
        }
        return mapping.get(regime, 'RANGE_BOUND')

    # =========================================================================
    # CAUSAL RL UPDATES
    # =========================================================================

    def _update_causal_rl(self, outcome: TradeOutcome) -> Optional[LearningUpdate]:
        """
        Update Causal RL agent with trade outcome.

        Propagates reward to per-asset agent based on causal alignment.
        """
        if not self.rl_engine:
            return None

        # Build reward signal
        reward_signal = RewardSignal(
            asset=outcome.canonical_id,
            action_taken=outcome.sizing_action,
            pnl=outcome.realized_pnl,
            risk_adjusted_return=outcome.realized_pnl_pct / 100.0 /
                                 max(outcome.hold_duration_minutes / 60 / 24, 1) ** 0.5,
            holding_period=outcome.hold_duration_minutes // 60,  # Convert to bars (hourly)
            regime_at_entry=outcome.regime_at_entry,
            regime_at_exit=outcome.regime_at_exit,
            causal_alignment=self._get_causal_alignment(outcome)
        )

        # Get prior state
        prior_stats = self.rl_engine.get_agent_stats(outcome.canonical_id)

        # Process reward
        try:
            self.rl_engine.process_reward(outcome.canonical_id, reward_signal)
        except Exception as e:
            logger.error(f"Causal RL update failed: {e}")
            return None

        # Get posterior state
        posterior_stats = self.rl_engine.get_agent_stats(outcome.canonical_id)

        update = LearningUpdate(
            update_id='',
            outcome_id=outcome.outcome_id,
            learning_system='CAUSAL_RL',
            action=outcome.sizing_action,
            reward=reward_signal.risk_adjusted_return,
            prior_state={'agent_stats': prior_stats},
            posterior_state={'agent_stats': posterior_stats},
            created_at=datetime.now(timezone.utc)
        )

        logger.info(f"Causal RL updated: {outcome.canonical_id} "
                   f"reward={reward_signal.risk_adjusted_return:.4f} "
                   f"alignment={reward_signal.causal_alignment:.2f}")

        return update

    def _get_causal_alignment(self, outcome: TradeOutcome) -> float:
        """Calculate causal alignment for trade outcome."""
        # Query causal parents
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT source_id, edge_weight
                    FROM fhq_alpha.causal_edges
                    WHERE target_id = %s
                      AND is_active = true
                    LIMIT 5
                """, (outcome.canonical_id,))
                parents = cur.fetchall()
        except:
            return 0.5  # Default neutral alignment

        if not parents:
            return 0.5

        # Check if parents moved in same direction
        our_direction = 1 if outcome.realized_pnl > 0 else -1
        aligned = 0

        for parent in parents:
            # Get parent return during trade period (simplified)
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            (SELECT close FROM fhq_data.price_series
                             WHERE listing_id = %s ORDER BY date DESC LIMIT 1) /
                            NULLIF((SELECT close FROM fhq_data.price_series
                             WHERE listing_id = %s ORDER BY date DESC OFFSET 1 LIMIT 1), 0) - 1
                            as parent_return
                    """, (parent['source_id'], parent['source_id']))
                    result = cur.fetchone()
                    if result and result[0]:
                        parent_direction = 1 if result[0] > 0 else -1
                        if parent_direction == our_direction:
                            aligned += 1
            except:
                pass

        return aligned / len(parents) if parents else 0.5

    # =========================================================================
    # STRATEGY STATISTICS
    # =========================================================================

    def _update_strategy_stats(self, outcome: TradeOutcome) -> Optional[LearningUpdate]:
        """
        Update strategy performance statistics.

        Maintains running statistics per strategy for monitoring.
        """
        # Upsert into strategy stats table
        sql = """
            INSERT INTO fhq_execution.strategy_performance_stats (
                strategy_source,
                total_trades,
                winning_trades,
                total_pnl,
                total_pnl_pct,
                max_drawdown_pct,
                avg_hold_minutes,
                updated_at
            ) VALUES (
                %s, 1,
                CASE WHEN %s > 0 THEN 1 ELSE 0 END,
                %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (strategy_source) DO UPDATE SET
                total_trades = fhq_execution.strategy_performance_stats.total_trades + 1,
                winning_trades = fhq_execution.strategy_performance_stats.winning_trades +
                                 CASE WHEN %s > 0 THEN 1 ELSE 0 END,
                total_pnl = fhq_execution.strategy_performance_stats.total_pnl + %s,
                total_pnl_pct = fhq_execution.strategy_performance_stats.total_pnl_pct + %s,
                max_drawdown_pct = GREATEST(
                    fhq_execution.strategy_performance_stats.max_drawdown_pct, %s
                ),
                avg_hold_minutes = (
                    fhq_execution.strategy_performance_stats.avg_hold_minutes *
                    fhq_execution.strategy_performance_stats.total_trades + %s
                ) / (fhq_execution.strategy_performance_stats.total_trades + 1),
                updated_at = NOW()
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    outcome.strategy_source,
                    outcome.realized_pnl,
                    outcome.realized_pnl,
                    outcome.realized_pnl_pct,
                    outcome.max_drawdown_pct,
                    outcome.hold_duration_minutes,
                    outcome.realized_pnl,
                    outcome.realized_pnl,
                    outcome.realized_pnl_pct,
                    outcome.max_drawdown_pct,
                    outcome.hold_duration_minutes
                ))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Strategy stats update failed (table may not exist): {e}")
            self.conn.rollback()
            # Create table if it doesn't exist
            self._ensure_stats_table()
            return None

        update = LearningUpdate(
            update_id='',
            outcome_id=outcome.outcome_id,
            learning_system='STRATEGY_STATS',
            action='UPDATE_STATS',
            reward=outcome.realized_pnl_pct,
            prior_state={},
            posterior_state={'strategy': outcome.strategy_source},
            created_at=datetime.now(timezone.utc)
        )

        logger.info(f"Strategy stats updated: {outcome.strategy_source}")

        return update

    def _ensure_stats_table(self):
        """Create strategy stats table if it doesn't exist."""
        sql = """
            CREATE TABLE IF NOT EXISTS fhq_execution.strategy_performance_stats (
                strategy_source TEXT PRIMARY KEY,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                total_pnl NUMERIC(12,4) DEFAULT 0,
                total_pnl_pct NUMERIC(8,4) DEFAULT 0,
                max_drawdown_pct NUMERIC(8,4) DEFAULT 0,
                avg_hold_minutes INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
            self.conn.commit()
        except:
            self.conn.rollback()

    # =========================================================================
    # CEO DIRECTIVE MANDATE IV: Cognitive Engine Learning Proposals
    # =========================================================================
    # "NO automated updates to IKEA classifier. All updates go to staging
    #  + G1/VEGA approval."
    #
    # These methods PROPOSE learning updates, they do NOT directly modify
    # production cognitive engine parameters. All proposals go to:
    #   fhq_governance.learning_proposals (staging table)
    #
    # Production updates require:
    #   1. G1 technical validation
    #   2. VEGA attestation (vega_attestation_id)
    #   3. Human approval via fn_approve_learning_proposal()
    # =========================================================================

    def _propose_ikea_update(self, outcome: TradeOutcome) -> Optional[str]:
        """
        Propose an update to IKEA boundary classifier based on trade outcome.

        If a hypothesis used hallucinated data and the trade failed,
        IKEA should learn to classify that data type as EXTERNAL_REQUIRED.

        Returns: proposal_id if submitted, None otherwise.
        """
        # Only propose updates for significant losses
        if outcome.realized_pnl >= 0:
            return None

        evidence_bundle = {
            'outcome_id': outcome.outcome_id,
            'position_id': outcome.position_id,
            'canonical_id': outcome.canonical_id,
            'realized_pnl': outcome.realized_pnl,
            'realized_pnl_pct': outcome.realized_pnl_pct,
            'regime_at_entry': outcome.regime_at_entry,
            'regime_at_exit': outcome.regime_at_exit,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Propose increasing strictness for this data category
        current_value = {'boundary_strictness': 0.7}  # Placeholder - would query actual
        proposed_value = {'boundary_strictness': 0.85}  # More conservative

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT fhq_governance.fn_submit_learning_proposal(
                        'IKEA'::varchar(10),
                        'BOUNDARY_WEIGHT'::varchar(50),
                        %s::jsonb,
                        %s::jsonb,
                        %s::jsonb,
                        'LEARNING_PIPELINE'::varchar(50)
                    )
                """, (
                    Json(current_value),
                    Json(proposed_value),
                    Json([evidence_bundle])
                ))
                result = cur.fetchone()
                proposal_id = str(result[0]) if result else None
            self.conn.commit()

            if proposal_id:
                logger.info(f"IKEA learning proposal submitted: {proposal_id}")
            return proposal_id

        except Exception as e:
            logger.warning(f"IKEA proposal submission failed: {e}")
            self.conn.rollback()
            return None

    def _propose_inforage_update(self, outcome: TradeOutcome) -> Optional[str]:
        """
        Propose an update to InForage scent model based on trade outcome.

        Compare predicted information gain to actual ROI to calibrate
        the scent scoring model.

        Returns: proposal_id if submitted, None otherwise.
        """
        evidence_bundle = {
            'outcome_id': outcome.outcome_id,
            'canonical_id': outcome.canonical_id,
            'realized_pnl_pct': outcome.realized_pnl_pct,
            'strategy_source': outcome.strategy_source,
            'hold_duration_minutes': outcome.hold_duration_minutes,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Calculate actual gain for scent calibration
        actual_gain = max(0, min(1, (outcome.realized_pnl_pct + 5) / 10))  # Normalize to 0-1

        current_value = {'scent_decay_factor': 0.85}
        proposed_value = {'scent_decay_factor': 0.80 if actual_gain < 0.3 else 0.90}

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT fhq_governance.fn_submit_learning_proposal(
                        'INFORAGE'::varchar(10),
                        'SCENT_MODEL'::varchar(50),
                        %s::jsonb,
                        %s::jsonb,
                        %s::jsonb,
                        'LEARNING_PIPELINE'::varchar(50)
                    )
                """, (
                    Json(current_value),
                    Json(proposed_value),
                    Json([evidence_bundle])
                ))
                result = cur.fetchone()
                proposal_id = str(result[0]) if result else None
            self.conn.commit()

            if proposal_id:
                logger.info(f"InForage learning proposal submitted: {proposal_id}")
            return proposal_id

        except Exception as e:
            logger.warning(f"InForage proposal submission failed: {e}")
            self.conn.rollback()
            return None

    def _propose_sitc_update(self, outcome: TradeOutcome) -> Optional[str]:
        """
        Propose an update to SitC plan priors based on trade outcome.

        Track which plan structures lead to successful trades.

        Returns: proposal_id if submitted, None otherwise.
        """
        evidence_bundle = {
            'outcome_id': outcome.outcome_id,
            'strategy_source': outcome.strategy_source,
            'realized_pnl': outcome.realized_pnl,
            'realized_pnl_pct': outcome.realized_pnl_pct,
            'regime_at_entry': outcome.regime_at_entry,
            'success': outcome.realized_pnl > 0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Propose plan structure adjustments
        current_value = {'max_chain_depth': 5}
        proposed_value = {
            'max_chain_depth': 4 if outcome.realized_pnl < 0 else 6
        }

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT fhq_governance.fn_submit_learning_proposal(
                        'SITC'::varchar(10),
                        'PLAN_PRIOR'::varchar(50),
                        %s::jsonb,
                        %s::jsonb,
                        %s::jsonb,
                        'LEARNING_PIPELINE'::varchar(50)
                    )
                """, (
                    Json(current_value),
                    Json(proposed_value),
                    Json([evidence_bundle])
                ))
                result = cur.fetchone()
                proposal_id = str(result[0]) if result else None
            self.conn.commit()

            if proposal_id:
                logger.info(f"SitC learning proposal submitted: {proposal_id}")
            return proposal_id

        except Exception as e:
            logger.warning(f"SitC proposal submission failed: {e}")
            self.conn.rollback()
            return None

    def submit_cognitive_learning_proposals(self, outcome: TradeOutcome) -> Dict[str, Optional[str]]:
        """
        Submit all cognitive engine learning proposals for a trade outcome.

        Per Mandate IV: All proposals go to staging, NOT directly to production.

        Returns: Dict of engine -> proposal_id
        """
        proposals = {}

        # IKEA: Only propose on significant losses (hallucination detection)
        if outcome.realized_pnl_pct < -2.0:  # >2% loss
            proposals['IKEA'] = self._propose_ikea_update(outcome)

        # InForage: Always propose for scent calibration
        proposals['INFORAGE'] = self._propose_inforage_update(outcome)

        # SitC: Propose for all trades to calibrate plan structures
        proposals['SITC'] = self._propose_sitc_update(outcome)

        submitted = {k: v for k, v in proposals.items() if v}
        if submitted:
            logger.info(f"Submitted {len(submitted)} cognitive learning proposals")

        return proposals

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def _mark_outcome_processed(self, outcome_id: str, updates: List[LearningUpdate]):
        """Mark outcome as processed and log updates."""
        # Mark as processed
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_execution.paper_trade_outcomes
                SET learning_applied = true
                WHERE outcome_id = %s::uuid
            """, (outcome_id,))

        # Log each update
        for update in updates:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_execution.learning_updates (
                        outcome_id, learning_system, action, reward,
                        prior_state, posterior_state
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s
                    )
                """, (
                    update.outcome_id,
                    update.learning_system,
                    update.action,
                    update.reward,
                    Json(update.prior_state),
                    Json(update.posterior_state)
                ))

        self.conn.commit()

    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================

    def process_all_pending(self) -> Dict:
        """Process all pending trade outcomes."""
        outcomes = self.get_pending_outcomes()

        if not outcomes:
            logger.info("No pending outcomes to process")
            return {'processed': 0, 'updates': 0}

        total_updates = 0
        for outcome in outcomes:
            updates = self.process_outcome(outcome)
            total_updates += len(updates)

        logger.info(f"Processed {len(outcomes)} outcomes, {total_updates} learning updates")

        return {
            'processed': len(outcomes),
            'updates': total_updates,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def get_learning_summary(self) -> Dict:
        """Get summary of learning system state."""
        summary = {
            'bandit_systems': {},
            'rl_agents': 0,
            'strategy_stats': {}
        }

        # Bandit system stats
        for strategy, system in self.bandit_systems.items():
            recommendations = system.get_recommended_actions()
            summary['bandit_systems'][strategy] = recommendations

        # RL agent count
        if self.rl_engine:
            summary['rl_agents'] = len(self.rl_engine.agents)

        # Strategy performance
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        strategy_source,
                        total_trades,
                        winning_trades,
                        total_pnl,
                        CASE WHEN total_trades > 0
                             THEN winning_trades::float / total_trades
                             ELSE 0 END as win_rate
                    FROM fhq_execution.strategy_performance_stats
                """)
                for row in cur.fetchall():
                    summary['strategy_stats'][row['strategy_source']] = {
                        'trades': row['total_trades'],
                        'wins': row['winning_trades'],
                        'pnl': float(row['total_pnl']),
                        'win_rate': round(row['win_rate'], 4)
                    }
        except:
            pass

        return summary


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_learning_pipeline() -> LearningFeedbackPipeline:
    """Factory function to get configured learning pipeline."""
    pipeline = LearningFeedbackPipeline()
    pipeline.connect()
    return pipeline


# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Learning Feedback Pipeline')
    parser.add_argument('--process', action='store_true', help='Process pending outcomes')
    parser.add_argument('--summary', action='store_true', help='Show learning summary')
    args = parser.parse_args()

    pipeline = get_learning_pipeline()

    if args.process:
        result = pipeline.process_all_pending()
        print(f"Processed: {result}")
    elif args.summary:
        summary = pipeline.get_learning_summary()
        print(json.dumps(summary, indent=2, default=str))
    else:
        print("Learning Feedback Pipeline")
        print(f"  Thompson Bandit Available: {BANDIT_AVAILABLE}")
        print(f"  Causal RL Available: {RL_AVAILABLE}")

        pending = pipeline.get_pending_outcomes()
        print(f"  Pending Outcomes: {len(pending)}")

    pipeline.close()
