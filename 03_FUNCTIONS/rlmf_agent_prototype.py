#!/usr/bin/env python3
"""
RLMF AGENT PROTOTYPE - OBSERVATION MODE ONLY
============================================
Directive: CEO-DIR-2026-120 P4.1
Classification: G4_RESEARCH_SANDBOX
Date: 2026-01-22

Reinforcement Learning from Market Feedback (RLMF) agent skeleton.

STRICT CONSTRAINTS (Phase 1):
1. OBSERVATION ONLY - No production weight updates
2. All suggestions logged to fhq_sandbox.rlmf_observation_log
3. production_write_blocked = True at all times
4. No connection to live weighting system

Purpose:
- Log signal/regime/outcome observations for offline analysis
- Generate weight adjustment suggestions (not applied)
- Build training data for future RL implementation

Authority: CEO, STIG (Technical)
Employment Contract: EC-003
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

# Load environment
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[RLMF-PROTO] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# STRICT: Phase 1 observation mode
OBSERVATION_ONLY_MODE = True
PRODUCTION_WRITE_BLOCKED = True  # NEVER SET TO FALSE IN PHASE 1


@dataclass
class Observation:
    """An observation of signal, regime, and outcome."""
    observation_id: str
    signal_id: str
    signal_type: str
    regime_at_signal: str
    direction: str
    confidence: float
    actual_outcome: Optional[str]  # 'WIN', 'LOSS', 'PENDING'
    realized_pnl: Optional[float]
    holding_period_hours: Optional[int]
    timestamp: datetime


@dataclass
class WeightSuggestion:
    """A suggested weight adjustment (not applied in Phase 1)."""
    signal_type: str
    regime: str
    current_weight: float
    suggested_weight: float
    adjustment_reason: str
    confidence_in_suggestion: float


class RLMFAgentPrototype:
    """
    RLMF Agent Prototype - Observation Only.

    STRICT: This agent OBSERVES and SUGGESTS but NEVER WRITES to production tables.
    All observations go to fhq_sandbox.rlmf_observation_log only.
    """

    def __init__(self):
        self.conn = None
        self._observation_count = 0
        self._suggestion_count = 0

        # STRICT: Verify observation mode
        if not OBSERVATION_ONLY_MODE:
            raise RuntimeError("FATAL: RLMF must be in OBSERVATION_ONLY_MODE in Phase 1")

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("RLMF Agent connected (OBSERVATION MODE ONLY)")

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()

    def observe(
        self,
        signal_id: str,
        signal_type: str,
        regime: str,
        direction: str,
        confidence: float,
        outcome: Optional[str] = None,
        realized_pnl: Optional[float] = None
    ) -> Observation:
        """
        Record an observation for offline learning.

        This is the primary method for collecting training data.
        """
        obs_id = hashlib.md5(
            f"{signal_id}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        observation = Observation(
            observation_id=obs_id,
            signal_id=signal_id,
            signal_type=signal_type,
            regime_at_signal=regime,
            direction=direction,
            confidence=confidence,
            actual_outcome=outcome,
            realized_pnl=realized_pnl,
            holding_period_hours=None,
            timestamp=datetime.now(timezone.utc)
        )

        # Log to sandbox (NEVER to production)
        self._log_observation(observation)
        self._observation_count += 1

        logger.info(
            f"OBSERVATION #{self._observation_count}: "
            f"{signal_type}@{regime} -> {outcome or 'PENDING'}"
        )

        return observation

    def suggest_weight_adjustment(
        self,
        signal_type: str,
        regime: str
    ) -> Optional[WeightSuggestion]:
        """
        Generate a weight adjustment suggestion based on historical observations.

        STRICT: Suggestions are logged but NEVER applied to production in Phase 1.
        """
        # Get historical performance for this signal/regime combination
        stats = self._get_historical_stats(signal_type, regime)

        if stats['observation_count'] < 10:
            logger.debug(f"Insufficient data for suggestion: {signal_type}@{regime}")
            return None

        # Simple heuristic: adjust weight based on win rate
        win_rate = stats['win_count'] / stats['observation_count']
        avg_pnl = stats['avg_pnl']

        # Current weight (default 1.0)
        current_weight = self._get_current_weight(signal_type, regime)

        # Suggested adjustment (conservative)
        if win_rate > 0.6 and avg_pnl > 0:
            # Increase weight (max 10% increase)
            suggested = min(current_weight * 1.10, 1.2)
            reason = f"High win rate ({win_rate:.2%}) and positive avg PnL (${avg_pnl:.2f})"
        elif win_rate < 0.4 or avg_pnl < 0:
            # Decrease weight (max 10% decrease)
            suggested = max(current_weight * 0.90, 0.3)
            reason = f"Low win rate ({win_rate:.2%}) or negative avg PnL (${avg_pnl:.2f})"
        else:
            # No change
            suggested = current_weight
            reason = "Performance within acceptable range"

        suggestion = WeightSuggestion(
            signal_type=signal_type,
            regime=regime,
            current_weight=current_weight,
            suggested_weight=round(suggested, 4),
            adjustment_reason=reason,
            confidence_in_suggestion=min(0.9, stats['observation_count'] / 100)
        )

        # Log suggestion (NEVER apply)
        self._log_suggestion(suggestion)
        self._suggestion_count += 1

        logger.info(
            f"SUGGESTION #{self._suggestion_count} (NOT APPLIED): "
            f"{signal_type}@{regime}: {current_weight:.3f} -> {suggested:.3f}"
        )

        return suggestion

    def _get_historical_stats(
        self,
        signal_type: str,
        regime: str
    ) -> Dict[str, Any]:
        """Get historical performance statistics from observations."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as observation_count,
                        COUNT(*) FILTER (WHERE actual_outcome = 'WIN') as win_count,
                        COUNT(*) FILTER (WHERE actual_outcome = 'LOSS') as loss_count,
                        AVG(realized_pnl) as avg_pnl,
                        STDDEV(realized_pnl) as pnl_stddev
                    FROM fhq_sandbox.rlmf_observation_log
                    WHERE signal_type = %s
                    AND regime_at_signal = %s
                    AND actual_outcome IS NOT NULL
                """, (signal_type, regime))
                row = cur.fetchone()

                return {
                    'observation_count': row['observation_count'] or 0,
                    'win_count': row['win_count'] or 0,
                    'loss_count': row['loss_count'] or 0,
                    'avg_pnl': float(row['avg_pnl'] or 0),
                    'pnl_stddev': float(row['pnl_stddev'] or 0)
                }

        except Exception as e:
            logger.warning(f"Could not get historical stats: {e}")
            return {
                'observation_count': 0,
                'win_count': 0,
                'loss_count': 0,
                'avg_pnl': 0.0,
                'pnl_stddev': 0.0
            }

    def _get_current_weight(self, signal_type: str, regime: str) -> float:
        """Get current weight from IoS-013 (read-only)."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT regime_confidence
                    FROM fhq_signal_context.weighted_signal_plan
                    WHERE regime_context = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (regime,))
                row = cur.fetchone()
                return float(row[0]) if row else 1.0
        except Exception:
            return 1.0

    def _log_observation(self, obs: Observation):
        """Log observation to sandbox table."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_sandbox.rlmf_observation_log (
                        signal_id, signal_type, regime_at_signal,
                        suggested_weight_adjustment, actual_outcome,
                        realized_pnl, observation_timestamp,
                        production_write_blocked, observation_only_mode
                    ) VALUES (
                        %s, %s, %s, NULL, %s, %s, NOW(), %s, %s
                    )
                """, (
                    obs.signal_id,
                    obs.signal_type,
                    obs.regime_at_signal,
                    obs.actual_outcome,
                    obs.realized_pnl,
                    PRODUCTION_WRITE_BLOCKED,  # ALWAYS True in Phase 1
                    OBSERVATION_ONLY_MODE      # ALWAYS True in Phase 1
                ))
                self.conn.commit()

        except Exception as e:
            logger.error(f"Failed to log observation: {e}")
            self.conn.rollback()

    def _log_suggestion(self, suggestion: WeightSuggestion):
        """Log suggestion to sandbox (NEVER applied)."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_sandbox.rlmf_observation_log (
                        signal_type, regime_at_signal,
                        suggested_weight_adjustment, actual_outcome,
                        observation_timestamp,
                        production_write_blocked, observation_only_mode
                    ) VALUES (
                        %s, %s, %s, 'SUGGESTION_ONLY', NOW(), %s, %s
                    )
                """, (
                    suggestion.signal_type,
                    suggestion.regime,
                    suggestion.suggested_weight - suggestion.current_weight,
                    PRODUCTION_WRITE_BLOCKED,
                    OBSERVATION_ONLY_MODE
                ))
                self.conn.commit()

        except Exception as e:
            logger.error(f"Failed to log suggestion: {e}")
            self.conn.rollback()

    def get_observation_summary(self) -> Dict[str, Any]:
        """Get summary of all observations."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        signal_type,
                        regime_at_signal,
                        COUNT(*) as count,
                        COUNT(*) FILTER (WHERE actual_outcome = 'WIN') as wins,
                        COUNT(*) FILTER (WHERE actual_outcome = 'LOSS') as losses,
                        AVG(realized_pnl) as avg_pnl
                    FROM fhq_sandbox.rlmf_observation_log
                    WHERE actual_outcome IS NOT NULL
                    GROUP BY signal_type, regime_at_signal
                    ORDER BY count DESC
                """)
                rows = cur.fetchall()

                return {
                    'observation_mode': OBSERVATION_ONLY_MODE,
                    'production_blocked': PRODUCTION_WRITE_BLOCKED,
                    'total_observations': self._observation_count,
                    'total_suggestions': self._suggestion_count,
                    'by_signal_regime': [dict(r) for r in rows]
                }

        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            return {
                'observation_mode': OBSERVATION_ONLY_MODE,
                'production_blocked': PRODUCTION_WRITE_BLOCKED,
                'error': str(e)
            }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='RLMF Agent Prototype (CEO-DIR-2026-120 P4.1) - OBSERVATION ONLY'
    )
    parser.add_argument('--observe', action='store_true', help='Record test observation')
    parser.add_argument('--suggest', action='store_true', help='Generate test suggestion')
    parser.add_argument('--summary', action='store_true', help='Show observation summary')

    args = parser.parse_args()

    print("=" * 60)
    print("RLMF AGENT PROTOTYPE - OBSERVATION MODE ONLY")
    print("STRICT: NO PRODUCTION WRITES IN PHASE 1")
    print("=" * 60)

    agent = RLMFAgentPrototype()
    agent.connect()

    try:
        if args.observe:
            obs = agent.observe(
                signal_id='test-signal-001',
                signal_type='MOMENTUM_UP',
                regime='MODERATE_BULL',
                direction='UP',
                confidence=0.75,
                outcome='WIN',
                realized_pnl=125.50
            )
            print(f"\nObservation recorded: {obs.observation_id}")

        elif args.suggest:
            suggestion = agent.suggest_weight_adjustment(
                signal_type='MOMENTUM_UP',
                regime='MODERATE_BULL'
            )
            if suggestion:
                print(f"\nSuggestion (NOT APPLIED):")
                print(f"  Current: {suggestion.current_weight:.3f}")
                print(f"  Suggested: {suggestion.suggested_weight:.3f}")
                print(f"  Reason: {suggestion.adjustment_reason}")
            else:
                print("\nInsufficient data for suggestion")

        elif args.summary:
            summary = agent.get_observation_summary()
            print(json.dumps(summary, indent=2, default=str))

        else:
            parser.print_help()

    finally:
        agent.close()


if __name__ == '__main__':
    main()
