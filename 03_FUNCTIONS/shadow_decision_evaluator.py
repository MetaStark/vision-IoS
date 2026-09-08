#!/usr/bin/env python3
"""
SHADOW DECISION EVALUATOR
=========================
CEO Directive: CEO-DIR-2026-050
Classification: SHADOW_EVALUATION (Non-Executing)

Purpose:
    Evaluates golden needles through LIDS gates WITHOUT execution.
    Logs all decisions to fhq_governance.shadow_decision_log.
    Provides observability into what WOULD have happened.

Key Properties:
    - paper_trading_eligible = FALSE (intentional)
    - NO execution, NO capital exposure
    - Logs to shadow_decision_log for learning
    - Proves LIDS gate behavior

Flow:
    1. Fetch fresh signals from golden_needles
    2. Evaluate each through LIDS gates (confidence, freshness)
    3. Log decision to shadow_decision_log
    4. Generate cycle evidence

Author: STIG (CTO)
Date: 2026-01-14
"""

import os
import sys
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('shadow_decision_evaluator')

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# LIDS Gate Thresholds (CEO-DIR-2026-019)
LIDS_MIN_CONFIDENCE = 0.70
LIDS_MAX_FRESHNESS_HOURS = 12.0


class ShadowDecisionEvaluator:
    """
    CEO-DIR-2026-050: Shadow Decision Evaluator

    Evaluates signals through LIDS gates and logs to shadow_decision_log.
    Zero execution, zero capital exposure.
    """

    def __init__(self):
        self.conn = None
        self.cycle_id = uuid.uuid4()
        self.cycle_count = 0

    def connect(self) -> bool:
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Database connected")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def get_fresh_signals(self, limit: int = 20) -> List[Dict]:
        """
        Fetch signals from golden_needles for evaluation.

        Unlike execution mode, we fetch ALL signals (not just fresh ones)
        to demonstrate what would happen.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    needle_id,
                    hypothesis_title,
                    hypothesis_category,
                    eqs_score,
                    sitc_confidence_level,
                    price_witness_symbol,
                    price_witness_timestamp,
                    regime_sovereign,
                    created_at
                FROM fhq_canonical.golden_needles
                WHERE is_current = TRUE
                ORDER BY eqs_score DESC, created_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

    def evaluate_lids_gates(self, signal: Dict) -> Dict:
        """
        Evaluate a signal through LIDS gates.

        Returns evaluation result with:
        - lids_verdict: PASS, BLOCKED_CONFIDENCE, BLOCKED_FRESHNESS
        - lids_confidence: numeric value
        - lids_freshness_hours: data age in hours
        - would_have_executed: whether all gates passed
        """
        result = {
            'signal_id': str(signal.get('needle_id', uuid.uuid4())),
            'needle_id': signal.get('needle_id'),
            'symbol': signal.get('price_witness_symbol', 'UNKNOWN'),
            'signal_created_at': signal.get('created_at'),
            'evaluation_time': datetime.now(timezone.utc),
            'lids_verdict': 'PENDING',
            'lids_confidence': 0.0,
            'lids_confidence_threshold': LIDS_MIN_CONFIDENCE,
            'lids_freshness_hours': 999.0,
            'lids_freshness_threshold_hours': LIDS_MAX_FRESHNESS_HOURS,
            'eqs_score': float(signal.get('eqs_score', 0) or 0),
            'sitc_confidence_level': signal.get('sitc_confidence_level', 'UNKNOWN'),
            'would_have_executed': False,
            'blocked_at_gate': None,
            'decision_formula': {}
        }

        # =====================================================================
        # LIDS CONFIDENCE GATE
        # =====================================================================
        confidence_raw = signal.get('sitc_confidence_level', 'LOW')
        if isinstance(confidence_raw, str):
            confidence_map = {'HIGH': 0.85, 'MEDIUM': 0.70, 'LOW': 0.50}
            confidence = confidence_map.get(confidence_raw.upper(), 0.5)
        else:
            confidence = float(confidence_raw or 0)

        result['lids_confidence'] = confidence
        result['decision_formula']['confidence_raw'] = confidence_raw
        result['decision_formula']['confidence_numeric'] = confidence

        if confidence < LIDS_MIN_CONFIDENCE:
            result['lids_verdict'] = 'BLOCKED_CONFIDENCE'
            result['blocked_at_gate'] = 'LIDS_CONFIDENCE'
            result['decision_formula']['block_reason'] = f'confidence {confidence:.2f} < {LIDS_MIN_CONFIDENCE}'
            return result

        # =====================================================================
        # LIDS FRESHNESS GATE
        # =====================================================================
        data_timestamp = signal.get('price_witness_timestamp', signal.get('created_at'))
        freshness_hours = 999.0

        if data_timestamp:
            try:
                if isinstance(data_timestamp, str):
                    from dateutil import parser
                    data_timestamp = parser.parse(data_timestamp)
                if data_timestamp.tzinfo is None:
                    data_timestamp = data_timestamp.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - data_timestamp).total_seconds()
                freshness_hours = max(0, age_seconds / 3600)
            except Exception as e:
                logger.warning(f"Could not parse data_timestamp: {e}")

        result['lids_freshness_hours'] = freshness_hours
        result['decision_formula']['data_timestamp'] = str(data_timestamp) if data_timestamp else None
        result['decision_formula']['freshness_hours'] = freshness_hours

        if freshness_hours > LIDS_MAX_FRESHNESS_HOURS:
            result['lids_verdict'] = 'BLOCKED_FRESHNESS'
            result['blocked_at_gate'] = 'LIDS_FRESHNESS'
            result['decision_formula']['block_reason'] = f'freshness {freshness_hours:.1f}h > {LIDS_MAX_FRESHNESS_HOURS}h'
            return result

        # =====================================================================
        # ALL LIDS GATES PASSED
        # =====================================================================
        result['lids_verdict'] = 'PASS'
        result['would_have_executed'] = True
        result['decision_formula']['all_gates_passed'] = True

        return result

    def log_shadow_decision(self, evaluation: Dict) -> bool:
        """
        Log evaluation result to shadow_decision_log.

        CEO-DIR-2026-050: Non-executing ledger for LIDS gate observability.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.shadow_decision_log (
                        signal_id,
                        needle_id,
                        symbol,
                        signal_created_at,
                        evaluation_time,
                        lids_verdict,
                        lids_confidence,
                        lids_confidence_threshold,
                        lids_freshness_hours,
                        lids_freshness_threshold_hours,
                        eqs_score,
                        sitc_confidence_level,
                        decision_formula,
                        execution_mode,
                        would_have_executed,
                        blocked_at_gate,
                        daemon_cycle_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    evaluation['signal_id'],
                    evaluation.get('needle_id'),
                    evaluation['symbol'],
                    evaluation.get('signal_created_at'),
                    evaluation['evaluation_time'],
                    evaluation['lids_verdict'],
                    evaluation['lids_confidence'],
                    evaluation['lids_confidence_threshold'],
                    evaluation['lids_freshness_hours'],
                    evaluation['lids_freshness_threshold_hours'],
                    evaluation['eqs_score'],
                    evaluation['sitc_confidence_level'],
                    json.dumps(evaluation['decision_formula']),
                    'SHADOW_EVALUATION',
                    evaluation['would_have_executed'],
                    evaluation['blocked_at_gate'],
                    str(self.cycle_id)
                ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to log shadow decision: {e}")
            self.conn.rollback()
            return False

    def log_heartbeat(self):
        """Log daemon heartbeat to agent_heartbeats"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.agent_heartbeats (
                        agent_id,
                        component,
                        health_score,
                        events_since_last,
                        last_heartbeat,
                        metadata
                    ) VALUES (
                        'LINE',
                        'SHADOW_DECISION_EVALUATOR',
                        1.0,
                        1,
                        NOW(),
                        jsonb_build_object(
                            'daemon', 'shadow_decision_evaluator',
                            'directive', 'CEO-DIR-2026-050',
                            'cycle_id', %s,
                            'cycle_count', %s
                        )
                    )
                    ON CONFLICT (agent_id, component) DO UPDATE SET
                        health_score = 1.0,
                        events_since_last = fhq_governance.agent_heartbeats.events_since_last + 1,
                        last_heartbeat = NOW(),
                        metadata = EXCLUDED.metadata
                """, (str(self.cycle_id), self.cycle_count))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to log heartbeat: {e}")
            self.conn.rollback()

    def run_evaluation_cycle(self) -> Dict:
        """
        Run one shadow evaluation cycle.

        Fetches signals, evaluates through LIDS gates, logs to shadow_decision_log.
        NO execution occurs.
        """
        self.cycle_count += 1
        self.cycle_id = uuid.uuid4()

        result = {
            'cycle_id': str(self.cycle_id),
            'cycle_count': self.cycle_count,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'mode': 'SHADOW_EVALUATION',
            'signals_evaluated': 0,
            'lids_passed': 0,
            'lids_blocked_confidence': 0,
            'lids_blocked_freshness': 0,
            'would_have_executed': 0,
            'evaluations': []
        }

        logger.info("=" * 60)
        logger.info("CEO-DIR-2026-050: SHADOW DECISION EVALUATION CYCLE")
        logger.info(f"Cycle ID: {self.cycle_id}")
        logger.info("=" * 60)

        # Fetch signals
        signals = self.get_fresh_signals(limit=20)
        logger.info(f"Found {len(signals)} signals to evaluate")

        for signal in signals:
            logger.info(f"\n--- Evaluating: {signal['needle_id']} ---")
            logger.info(f"    Title: {signal.get('hypothesis_title', 'N/A')}")
            logger.info(f"    EQS: {signal.get('eqs_score', 0)}")
            logger.info(f"    Confidence: {signal.get('sitc_confidence_level', 'N/A')}")

            # Evaluate through LIDS gates
            evaluation = self.evaluate_lids_gates(signal)

            # Log to database
            if self.log_shadow_decision(evaluation):
                result['signals_evaluated'] += 1

                if evaluation['lids_verdict'] == 'PASS':
                    result['lids_passed'] += 1
                    result['would_have_executed'] += 1
                    logger.info(f"    Verdict: PASS - Would have executed")
                elif evaluation['lids_verdict'] == 'BLOCKED_CONFIDENCE':
                    result['lids_blocked_confidence'] += 1
                    logger.info(f"    Verdict: BLOCKED_CONFIDENCE ({evaluation['lids_confidence']:.2f} < {LIDS_MIN_CONFIDENCE})")
                elif evaluation['lids_verdict'] == 'BLOCKED_FRESHNESS':
                    result['lids_blocked_freshness'] += 1
                    logger.info(f"    Verdict: BLOCKED_FRESHNESS ({evaluation['lids_freshness_hours']:.1f}h > {LIDS_MAX_FRESHNESS_HOURS}h)")

                result['evaluations'].append({
                    'signal_id': evaluation['signal_id'],
                    'symbol': evaluation['symbol'],
                    'verdict': evaluation['lids_verdict'],
                    'confidence': evaluation['lids_confidence'],
                    'freshness_hours': evaluation['lids_freshness_hours']
                })

        # Log heartbeat
        self.log_heartbeat()

        # Log cycle to governance
        self.log_cycle_completion(result)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"SHADOW EVALUATION SUMMARY:")
        logger.info(f"  Signals evaluated: {result['signals_evaluated']}")
        logger.info(f"  LIDS passed: {result['lids_passed']}")
        logger.info(f"  Blocked (confidence): {result['lids_blocked_confidence']}")
        logger.info(f"  Blocked (freshness): {result['lids_blocked_freshness']}")
        logger.info(f"  Would have executed: {result['would_have_executed']}")
        logger.info(f"{'=' * 60}")

        return result

    def log_cycle_completion(self, result: Dict):
        """Log cycle completion to governance_actions_log"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type,
                        action_target,
                        action_target_type,
                        initiated_by,
                        decision,
                        decision_rationale,
                        agent_id,
                        metadata
                    ) VALUES (
                        'SHADOW_EVALUATION_CYCLE',
                        %s,
                        'DAEMON_CYCLE',
                        'shadow_decision_evaluator',
                        'EXECUTED',
                        'CEO-DIR-2026-050: Shadow evaluation cycle completed',
                        'LINE',
                        %s
                    )
                """, (
                    str(self.cycle_id),
                    json.dumps({
                        'directive': 'CEO-DIR-2026-050',
                        'cycle_id': str(self.cycle_id),
                        'cycle_count': self.cycle_count,
                        'signals_evaluated': result['signals_evaluated'],
                        'lids_passed': result['lids_passed'],
                        'lids_blocked_confidence': result['lids_blocked_confidence'],
                        'lids_blocked_freshness': result['lids_blocked_freshness'],
                        'would_have_executed': result['would_have_executed'],
                        'execution_occurred': False,
                        'capital_exposure': 0
                    })
                ))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to log cycle completion: {e}")
            self.conn.rollback()


def main():
    import argparse
    import time

    parser = argparse.ArgumentParser(description='Shadow Decision Evaluator (CEO-DIR-2026-050)')
    parser.add_argument('--once', action='store_true', help='Run single cycle and exit')
    parser.add_argument('--interval', type=int, default=60, help='Cycle interval in seconds')
    parser.add_argument('--max-cycles', type=int, help='Maximum cycles to run')
    args = parser.parse_args()

    evaluator = ShadowDecisionEvaluator()

    if not evaluator.connect():
        logger.error("Failed to connect to database")
        sys.exit(1)

    try:
        if args.once:
            result = evaluator.run_evaluation_cycle()

            # Write evidence artifact
            artifact = {
                'evidence_type': 'SHADOW_EVALUATION_CYCLE',
                'directive': 'CEO-DIR-2026-050',
                'generated_by': 'STIG',
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'cycle_id': result['cycle_id'],
                'summary': {
                    'signals_evaluated': result['signals_evaluated'],
                    'lids_passed': result['lids_passed'],
                    'lids_blocked_confidence': result['lids_blocked_confidence'],
                    'lids_blocked_freshness': result['lids_blocked_freshness'],
                    'would_have_executed': result['would_have_executed']
                },
                'execution_occurred': False,
                'capital_exposure': 0,
                'evaluations': result['evaluations']
            }

            artifact_path = os.path.join(
                os.path.dirname(__file__),
                'evidence',
                f'CEO_DIR_2026_050_SHADOW_EVAL_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            )
            os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
            with open(artifact_path, 'w') as f:
                json.dump(artifact, f, indent=2)
            logger.info(f"Evidence artifact written to: {artifact_path}")

        else:
            # Continuous mode
            cycles_run = 0
            while True:
                result = evaluator.run_evaluation_cycle()
                cycles_run += 1

                if args.max_cycles and cycles_run >= args.max_cycles:
                    logger.info(f"Reached max cycles ({args.max_cycles})")
                    break

                logger.info(f"Sleeping {args.interval}s until next cycle...")
                time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        evaluator.close()


if __name__ == '__main__':
    main()
