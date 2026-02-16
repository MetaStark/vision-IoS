#!/usr/bin/env python3
"""
TRADE FALSIFICATION DAEMON
===========================
CEO-DIR-2026-LEARNING-ARCHITECTURE-CORRECTION-003

PURPOSE: Evaluate hypothesis falsification based on ACTUAL shadow trade performance.
         This daemon replaces OHLCV-based direction_accuracy with trade-based Sharpe.

CRITICAL CHANGE:
- OLD: Hypotheses falsified based on price_series direction_accuracy (OHLCV)
- NEW: Hypotheses falsified based on closed shadow trade performance (Sharpe < threshold)

FALSIFICATION RULES:
1. Minimum 5 CLOSED trades with pnl_type='REAL' required for evaluation
2. Trade Sharpe < 0.0 after N trades = FALSIFIED
3. EXPIRED/COUNTERFACTUAL trades do NOT count toward falsification

Author: STIG (EC-003)
Date: 2026-02-10
Classification: G4_PRODUCTION_DAEMON
"""

import os
import sys
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal
import uuid
import math

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', '')
}

# Falsification thresholds (FROZEN - CEO approval required to change)
# CEO-DIR-2026-TRADE-LEARNING-ACTIVATION-004: N_min = 30
MIN_TRADES_FOR_EVAL = 30          # GUARDRAIL: Minimum closed trades before status change
SHARPE_THRESHOLD = 0.0            # Sharpe below this = FALSIFIED
LEARNING_WEIGHT_REAL = 1.0        # Full weight for REALIZED trades
LEARNING_WEIGHT_COUNTERFACTUAL = 0.0  # ZERO weight for counterfactual (excluded)
PNL_TYPE_REAL = 'REALIZED'        # Actual pnl_type value in shadow_trades

# Exit Coverage SLA
EXIT_SLA_THRESHOLD = 1            # Minimum exits per window
EXIT_SLA_WINDOW_HOURS = 48        # Window for SLA check


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def calculate_trade_sharpe(returns: List[float]) -> Optional[float]:
    """
    Calculate Sharpe ratio from trade returns.

    Sharpe = mean(returns) / std(returns)
    Returns None if insufficient data.
    """
    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance) if variance > 0 else 0.0001

    return mean_return / std_dev


def get_hypothesis_trade_metrics(canon_id: str) -> Dict[str, Any]:
    """
    Calculate trade performance metrics for a hypothesis.
    ONLY uses CLOSED trades with pnl_type='REAL'.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get closed trades for this hypothesis
            cur.execute("""
                SELECT
                    st.shadow_pnl,
                    st.shadow_return_pct,
                    st.pnl_type,
                    st.learning_weight
                FROM fhq_execution.shadow_trades st
                WHERE st.source_hypothesis_id = %s
                  AND st.status = 'CLOSED'
                  AND st.pnl_type = 'REALIZED'
                ORDER BY st.exit_time
            """, (canon_id,))

            trades = cur.fetchall()

            if not trades:
                return {
                    'closed_trades': 0,
                    'returns': [],
                    'total_pnl': 0,
                    'avg_return': None,
                    'win_count': 0,
                    'loss_count': 0,
                    'win_rate': None,
                    'trade_sharpe': None
                }

            returns = [float(t['shadow_return_pct']) for t in trades if t['shadow_return_pct'] is not None]
            pnls = [float(t['shadow_pnl']) for t in trades if t['shadow_pnl'] is not None]

            total_pnl = sum(pnls)
            win_count = sum(1 for p in pnls if p > 0)
            loss_count = sum(1 for p in pnls if p <= 0)
            avg_return = sum(returns) / len(returns) if returns else None
            win_rate = win_count / len(pnls) if pnls else None
            trade_sharpe = calculate_trade_sharpe(returns) if len(returns) >= 2 else None

            return {
                'closed_trades': len(trades),
                'returns': returns,
                'total_pnl': total_pnl,
                'avg_return': avg_return,
                'win_count': win_count,
                'loss_count': loss_count,
                'win_rate': win_rate,
                'trade_sharpe': trade_sharpe
            }
    finally:
        conn.close()


def evaluate_hypothesis(canon_id: str, hypothesis_code: str) -> Dict[str, Any]:
    """
    Evaluate a hypothesis for trade-based falsification.

    Returns evaluation result with status and metrics.
    """
    metrics = get_hypothesis_trade_metrics(canon_id)

    result = {
        'canon_id': canon_id,
        'hypothesis_code': hypothesis_code,
        'metrics': metrics,
        'eval_timestamp': datetime.now(timezone.utc).isoformat()
    }

    # Determine evaluation status
    if metrics['closed_trades'] < MIN_TRADES_FOR_EVAL:
        result['eval_status'] = 'INSUFFICIENT_DATA'
        result['reason'] = f"Only {metrics['closed_trades']} CLOSED trades, need {MIN_TRADES_FOR_EVAL}"
    elif metrics['trade_sharpe'] is None:
        result['eval_status'] = 'INSUFFICIENT_DATA'
        result['reason'] = 'Cannot calculate Sharpe (insufficient return data)'
    elif metrics['trade_sharpe'] < SHARPE_THRESHOLD:
        result['eval_status'] = 'FALSIFIED'
        result['reason'] = f"Trade Sharpe {metrics['trade_sharpe']:.4f} < threshold {SHARPE_THRESHOLD}"
    else:
        result['eval_status'] = 'PASSING'
        result['reason'] = f"Trade Sharpe {metrics['trade_sharpe']:.4f} >= threshold {SHARPE_THRESHOLD}"

    return result


def check_exit_coverage_sla() -> Dict[str, Any]:
    """
    Check if exit coverage SLA is met.
    CEO-DIR-2026-TRADE-LEARNING-ACTIVATION-004: Fail-closed rule.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Count exits in last 48 hours
            cur.execute("""
                SELECT COUNT(*) as exits_48h
                FROM fhq_execution.shadow_trades
                WHERE status = 'CLOSED'
                  AND pnl_type = 'REALIZED'
                  AND exit_time >= NOW() - INTERVAL '48 hours'
            """)
            result = cur.fetchone()
            exits_48h = result['exits_48h'] if result else 0

            sla_met = exits_48h >= EXIT_SLA_THRESHOLD
            learning_blocked = not sla_met

            return {
                'exits_48h': exits_48h,
                'threshold': EXIT_SLA_THRESHOLD,
                'sla_met': sla_met,
                'learning_blocked': learning_blocked
            }
    finally:
        conn.close()


def update_hypothesis_status(canon_id: str, eval_result: Dict) -> bool:
    """
    Update hypothesis status based on trade evaluation.
    ONLY changes status to FALSIFIED if evaluation dictates.

    CEO-DIR-2026-TRADE-LEARNING-ACTIVATION-004:
    - Checks exit coverage SLA before status write
    - Blocks if LEARNING_BLOCKED
    """
    if eval_result['eval_status'] != 'FALSIFIED':
        return False  # No status change for non-falsified

    # GUARDRAIL: Check exit coverage SLA
    sla_status = check_exit_coverage_sla()
    if sla_status['learning_blocked']:
        logger.warning(
            f"LEARNING_BLOCKED: Cannot falsify {eval_result['hypothesis_code']}. "
            f"Exit coverage SLA not met ({sla_status['exits_48h']} exits in 48h, "
            f"need {sla_status['threshold']})"
        )
        eval_result['blocked_reason'] = 'LEARNING_BLOCKED: Exit coverage SLA not met'
        return False

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_learning.hypothesis_canon
                SET
                    status = 'FALSIFIED',
                    falsified_at = NOW(),
                    annihilation_reason = %s,
                    last_updated_at = NOW(),
                    last_updated_by = 'trade_falsification_daemon'
                WHERE canon_id = %s
                  AND status != 'FALSIFIED'  -- Don't re-falsify
                RETURNING hypothesis_code
            """, (
                eval_result['reason'],
                canon_id
            ))

            result = cur.fetchone()
            conn.commit()

            if result:
                logger.info(f"FALSIFIED: {result[0]} - {eval_result['reason']}")
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to update hypothesis {canon_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_hypotheses_for_evaluation() -> List[Dict]:
    """
    Get hypotheses that have CLOSED trades and need evaluation.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Find hypotheses with closed trades that are not already falsified
            cur.execute("""
                SELECT DISTINCT
                    hc.canon_id,
                    hc.hypothesis_code,
                    hc.status,
                    COUNT(st.trade_id) as closed_trade_count
                FROM fhq_learning.hypothesis_canon hc
                JOIN fhq_execution.shadow_trades st
                    ON st.source_hypothesis_id = hc.canon_id::text
                   OR st.source_hypothesis_id = hc.hypothesis_code
                WHERE hc.status NOT IN ('FALSIFIED')
                  AND st.status = 'CLOSED'
                  AND st.pnl_type = 'REALIZED'
                GROUP BY hc.canon_id, hc.hypothesis_code, hc.status
                HAVING COUNT(st.trade_id) >= %s
                ORDER BY closed_trade_count DESC
            """, (MIN_TRADES_FOR_EVAL,))

            return cur.fetchall()
    finally:
        conn.close()


def run_evaluation_cycle() -> Dict[str, Any]:
    """Run one evaluation cycle."""
    cycle_start = datetime.now(timezone.utc)
    cycle_id = str(uuid.uuid4())[:8]

    result = {
        'cycle_id': cycle_id,
        'timestamp': cycle_start.isoformat(),
        'daemon': 'trade_falsification_daemon',
        'directive': 'CEO-DIR-2026-LEARNING-ARCHITECTURE-CORRECTION-003',
        'thresholds': {
            'min_trades': MIN_TRADES_FOR_EVAL,
            'sharpe_threshold': SHARPE_THRESHOLD
        },
        'hypotheses_evaluated': 0,
        'results': {
            'FALSIFIED': 0,
            'PASSING': 0,
            'INSUFFICIENT_DATA': 0
        },
        'evaluations': []
    }

    # Get candidates
    hypotheses = get_hypotheses_for_evaluation()
    logger.info(f"Cycle {cycle_id}: Found {len(hypotheses)} hypotheses for evaluation")

    for hyp in hypotheses:
        canon_id = str(hyp['canon_id'])
        hypothesis_code = hyp['hypothesis_code']

        # Evaluate
        eval_result = evaluate_hypothesis(canon_id, hypothesis_code)
        result['hypotheses_evaluated'] += 1
        result['results'][eval_result['eval_status']] += 1
        result['evaluations'].append(eval_result)

        # Update status if falsified
        if eval_result['eval_status'] == 'FALSIFIED':
            update_hypothesis_status(canon_id, eval_result)

    result['duration_seconds'] = (datetime.now(timezone.utc) - cycle_start).total_seconds()

    return result


def write_evidence_file(cycle_results: Dict) -> str:
    """Write evidence file."""
    evidence_dir = 'C:/fhq-market-system/vision-ios/03_FUNCTIONS/evidence'
    os.makedirs(evidence_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"TRADE_FALSIFICATION_{timestamp}.json"
    filepath = os.path.join(evidence_dir, filename)

    def serialize(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return str(obj)

    with open(filepath, 'w') as f:
        json.dump(cycle_results, f, indent=2, default=serialize)

    return filepath


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("TRADE FALSIFICATION DAEMON")
    logger.info("CEO-DIR-2026-LEARNING-ARCHITECTURE-CORRECTION-003")
    logger.info("=" * 60)
    logger.info(f"Min trades for eval: {MIN_TRADES_FOR_EVAL}")
    logger.info(f"Sharpe threshold: {SHARPE_THRESHOLD}")
    logger.info("")

    try:
        # Run evaluation cycle
        result = run_evaluation_cycle()

        # Write evidence
        evidence_path = write_evidence_file(result)

        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"Cycle complete: {result['cycle_id']}")
        logger.info(f"Hypotheses evaluated: {result['hypotheses_evaluated']}")
        logger.info(f"FALSIFIED: {result['results']['FALSIFIED']}")
        logger.info(f"PASSING: {result['results']['PASSING']}")
        logger.info(f"INSUFFICIENT_DATA: {result['results']['INSUFFICIENT_DATA']}")
        logger.info(f"Evidence: {evidence_path}")
        logger.info("=" * 60)

        return result

    except Exception as e:
        logger.error(f"Daemon failed: {e}")
        raise


if __name__ == '__main__':
    main()
