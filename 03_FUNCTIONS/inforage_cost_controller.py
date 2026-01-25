#!/usr/bin/env python3
"""
INFORAGE COST CONTROLLER
=========================
CEO DIRECTIVE EC-005 PHASE 2: Activate the Pain Mechanism

The agent must feel API costs DURING the search, not just after.
This module implements economic stops based on predicted ROI.

Reference: InForage (NeurIPS 2025), ADR-012 (Economic Safety)
Authority: CEO Directive EC-005
Executor: STIG (CTO)
Date: 2025-12-09
"""

import os
import uuid
import logging
import traceback
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("INFORAGE_COST")


class StepType(Enum):
    """Types of steps that incur cost."""
    API_CALL = "API_CALL"
    LLM_INFERENCE = "LLM_INFERENCE"
    DB_QUERY = "DB_QUERY"


class CostDecision(Enum):
    """Decision outcomes from cost check."""
    CONTINUE = "CONTINUE"
    ABORT_LOW_ROI = "ABORT_LOW_ROI"
    ABORT_BUDGET = "ABORT_BUDGET"
    COMPLETED = "COMPLETED"


@dataclass
class CostCheckResult:
    """Result of InForage cost check."""
    decision: CostDecision
    cumulative_cost: float
    predicted_roi: Optional[float]
    abort_reason: Optional[str]

    @property
    def should_abort(self) -> bool:
        return self.decision in (CostDecision.ABORT_LOW_ROI, CostDecision.ABORT_BUDGET)


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('PGHOST', '127.0.0.1'),
        port=os.getenv('PGPORT', '54322'),
        dbname=os.getenv('PGDATABASE', 'postgres'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', 'postgres')
    )


class InForageCostController:
    """
    Cost controller that enforces economic stops during research.

    The agent "feels pain" when:
    1. Predicted information gain < cumulative API cost (Low ROI)
    2. Session budget is exceeded

    This forces efficiency by making the agent learn that
    wasteful searches are punished.
    """

    def __init__(self, session_id: Optional[str] = None):
        # CEO-DIR-2026-DAY25: Validate UUID format with explicit WARN
        if session_id:
            try:
                uuid.UUID(session_id)  # Validate format
                self.session_id = session_id
            except ValueError:
                logger.warning(f"MALFORMED UUID: '{session_id}' - Generating valid UUID. "
                              f"Traceback: {traceback.format_stack()[-3].strip()}")
                self.session_id = str(uuid.uuid4())
        else:
            self.session_id = str(uuid.uuid4())
        self.step_count = 0
        self.total_cost = 0.0
        self.aborted = False
        self.abort_reason = None

    def check_cost(
        self,
        step_type: StepType,
        predicted_gain: Optional[float] = None
    ) -> CostCheckResult:
        """
        Check if the next step should be allowed based on cost/benefit.

        This is the "pain mechanism" - called BEFORE every API call.

        Args:
            step_type: Type of step being taken
            predicted_gain: Expected information gain (0-1 scale)

        Returns:
            CostCheckResult with decision and cost info
        """
        if self.aborted:
            return CostCheckResult(
                decision=CostDecision.ABORT_LOW_ROI,
                cumulative_cost=self.total_cost,
                predicted_roi=0.0,
                abort_reason=self.abort_reason or "Session already aborted"
            )

        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Call the database function
                cur.execute("""
                    SELECT * FROM fhq_optimization.fn_inforage_cost_check(
                        %s::uuid,
                        %s,
                        %s
                    )
                """, (
                    self.session_id,
                    step_type.value,
                    predicted_gain
                ))

                row = cur.fetchone()
                conn.commit()

            if row:
                decision = CostDecision(row['decision'])
                result = CostCheckResult(
                    decision=decision,
                    cumulative_cost=float(row['cumulative_cost'] or 0),
                    predicted_roi=float(row['predicted_roi']) if row['predicted_roi'] else None,
                    abort_reason=row['abort_reason']
                )

                self.step_count += 1
                self.total_cost = result.cumulative_cost

                if result.should_abort:
                    self.aborted = True
                    self.abort_reason = result.abort_reason
                    logger.warning(f"INFORAGE ABORT: {result.abort_reason}")

                return result

        except Exception as e:
            logger.error(f"Cost check failed: {e}")

        # Default: allow if check fails
        return CostCheckResult(
            decision=CostDecision.CONTINUE,
            cumulative_cost=self.total_cost,
            predicted_roi=None,
            abort_reason=None
        )

    def complete_session(self, actual_gain: Optional[float] = None) -> Dict[str, Any]:
        """
        Mark session as complete and log final metrics.

        Args:
            actual_gain: The actual information gain realized

        Returns:
            Session summary
        """
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Update all log entries with actual gain
                if actual_gain is not None:
                    cur.execute("""
                        UPDATE fhq_optimization.inforage_cost_log
                        SET actual_gain = %s,
                            roi_ratio = %s / NULLIF(cumulative_cost, 0),
                            decision = CASE
                                WHEN decision = 'CONTINUE' THEN 'COMPLETED'
                                ELSE decision
                            END
                        WHERE session_id = %s
                    """, (actual_gain, actual_gain, self.session_id))

                # Get session summary
                cur.execute("""
                    SELECT
                        COUNT(*) as total_steps,
                        MAX(cumulative_cost) as final_cost,
                        AVG(predicted_gain) as avg_predicted_gain,
                        MAX(actual_gain) as actual_gain,
                        MAX(roi_ratio) as final_roi,
                        COUNT(*) FILTER (WHERE decision LIKE 'ABORT%') as abort_count
                    FROM fhq_optimization.inforage_cost_log
                    WHERE session_id = %s
                """, (self.session_id,))

                summary = cur.fetchone()
                conn.commit()

            return {
                'session_id': self.session_id,
                'total_steps': summary['total_steps'],
                'final_cost': float(summary['final_cost'] or 0),
                'actual_gain': float(summary['actual_gain']) if summary['actual_gain'] else None,
                'final_roi': float(summary['final_roi']) if summary['final_roi'] else None,
                'was_aborted': self.aborted,
                'abort_reason': self.abort_reason
            }

        except Exception as e:
            logger.error(f"Session completion failed: {e}")
            return {
                'session_id': self.session_id,
                'error': str(e)
            }


def predict_information_gain(
    query: str,
    current_coverage: float = 0.5,
    step_number: int = 0
) -> float:
    """
    Predict expected information gain from next search step.

    This is a heuristic that decays with step count and
    increases with query specificity.

    Args:
        query: The search query
        current_coverage: Current graph coverage (0-1)
        step_number: Current step number

    Returns:
        Predicted information gain (0-1 scale)
    """
    # Base gain depends on current coverage gap
    base_gain = 1.0 - current_coverage

    # Decay with step number (diminishing returns)
    decay_factor = 0.85 ** step_number

    # Query specificity bonus (longer queries usually more specific)
    specificity_bonus = min(0.2, len(query.split()) * 0.02)

    predicted = base_gain * decay_factor + specificity_bonus

    return max(0.05, min(1.0, predicted))


# =============================================================================
# INTEGRATION DECORATOR
# =============================================================================

def cost_controlled(step_type: StepType = StepType.API_CALL):
    """
    Decorator to wrap API calls with cost control.

    Usage:
        @cost_controlled(StepType.API_CALL)
        def my_api_call(query):
            return requests.get(...)
    """
    def decorator(func):
        def wrapper(*args, controller: InForageCostController = None, **kwargs):
            if controller is None:
                # No controller, just execute
                return func(*args, **kwargs)

            # Check cost before execution
            result = controller.check_cost(step_type)

            if result.should_abort:
                raise CostAbortError(result.abort_reason)

            # Execute the function
            return func(*args, **kwargs)

        return wrapper
    return decorator


class CostAbortError(Exception):
    """Raised when cost controller aborts a search."""
    pass


# =============================================================================
# CEO-DIR-2026-FINN-019: TRADE DECISION ROI CHECK
# =============================================================================

@dataclass
class TradeDecisionResult:
    """
    Result of trade decision ROI check.

    CEO Issue #3: Deterministic expected_pnl source
    CEO Issue #17: Include slippage in ROI calculation
    """
    session_id: str
    roi: float
    should_abort: bool
    abort_reason: Optional[str]
    components: Dict[str, Any]


# R3: Configurable InForage parameters (changes require ADR amendment)
INFORAGE_CONFIG = {
    'expected_tp_pct': 0.05,           # 5% take profit target
    'min_roi_threshold': 1.2,          # Minimum ROI to proceed
    'default_slippage_bps': 15.0,      # Default slippage in basis points
    'default_spread_bps': 5.0,         # Default spread in basis points
    'default_commission_usd': 0.0,     # Alpaca zero commission
}


def calculate_trade_roi(
    eqs_score: float,
    position_usd: float,
    spread_bps: float = None,
    commission_usd: float = None,
    slippage_estimate_bps: float = None,
    expected_tp_pct: float = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Grounded ROI calculation with explicit components.

    CEO Issue #3: Deterministic expected_pnl
    CEO Issue #17: Explicit slippage

    Expected Value Model:
    - EQS 0.8 = 80% confidence of hitting TP (assume +5%)
    - Expected return = EQS * TP%  (e.g., 0.8 * 0.05 = 4%)

    Returns: (roi, components_dict)
    """
    # Use configured defaults if not provided
    spread_bps = spread_bps if spread_bps is not None else INFORAGE_CONFIG['default_spread_bps']
    slippage_estimate_bps = slippage_estimate_bps if slippage_estimate_bps is not None else INFORAGE_CONFIG['default_slippage_bps']
    commission_usd = commission_usd if commission_usd is not None else INFORAGE_CONFIG['default_commission_usd']
    expected_tp_pct = expected_tp_pct if expected_tp_pct is not None else INFORAGE_CONFIG['expected_tp_pct']

    # Expected PnL (conservative: EQS * take_profit_pct * position * slippage_discount)
    expected_return_pct = eqs_score * expected_tp_pct
    slippage_factor = 1 - (slippage_estimate_bps / 10000)
    expected_pnl = position_usd * expected_return_pct * slippage_factor

    # Execution costs
    spread_cost = position_usd * (spread_bps / 10000)
    slippage_cost = position_usd * (slippage_estimate_bps / 10000)
    total_cost = spread_cost + commission_usd + slippage_cost

    # ROI = Expected PnL / Total Cost
    roi = expected_pnl / max(total_cost, 0.01)

    components = {
        'expected_pnl': expected_pnl,
        'expected_return_pct': expected_return_pct,
        'spread_cost': spread_cost,
        'slippage_cost': slippage_cost,
        'commission_usd': commission_usd,
        'total_cost': total_cost,
        'slippage_estimate_bps': slippage_estimate_bps,
        'spread_bps': spread_bps,
        'eqs_score': eqs_score,
        'position_usd': position_usd,
        'expected_tp_pct': expected_tp_pct
    }

    return roi, components


class InForageTradeController:
    """
    Trade decision controller for CEO-DIR-2026-FINN-019 Neural Bridge.

    Evaluates trade ROI and enforces minimum threshold.
    """

    def __init__(self, db_conn=None, session_id: Optional[str] = None):
        self.conn = db_conn
        self.session_id = session_id or str(uuid.uuid4())

    def check_trade_decision(
        self,
        needle_id: str,
        eqs_score: float,
        position_usd: float,
        spread_bps: float = None,
        slippage_bps: float = None,
        min_roi: float = None
    ) -> TradeDecisionResult:
        """
        Evaluate trade ROI with grounded calculation.

        CEO Issue #3: Deterministic expected_pnl
        CEO Issue #17: Explicit slippage

        Args:
            needle_id: Needle being evaluated
            eqs_score: EQS score (0.0-1.0)
            position_usd: Dollar amount for position
            spread_bps: Current spread in basis points
            slippage_bps: Estimated slippage in basis points
            min_roi: Minimum ROI threshold (default 1.2)

        Returns:
            TradeDecisionResult with ROI and abort decision
        """
        min_roi = min_roi if min_roi is not None else INFORAGE_CONFIG['min_roi_threshold']

        roi, components = calculate_trade_roi(
            eqs_score=eqs_score,
            position_usd=position_usd,
            spread_bps=spread_bps,
            slippage_estimate_bps=slippage_bps
        )

        should_abort = roi < min_roi
        abort_reason = f'LOW_ROI: {roi:.2f} < {min_roi}' if should_abort else None

        # Log to database
        self._log_trade_decision(needle_id, roi, components, should_abort)

        if should_abort:
            logger.warning(f"INFORAGE TRADE ABORT: {abort_reason}")
        else:
            logger.info(f"INFORAGE TRADE APPROVED: ROI={roi:.2f}")

        return TradeDecisionResult(
            session_id=self.session_id,
            roi=roi,
            should_abort=should_abort,
            abort_reason=abort_reason,
            components=components
        )

    def _log_trade_decision(
        self,
        needle_id: str,
        roi: float,
        components: Dict,
        aborted: bool
    ):
        """Log trade decision to database."""
        if self.conn is None:
            return

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO fhq_optimization.inforage_cost_log (
                    session_id, step_type, step_number,
                    predicted_gain, predicted_roi, decision,
                    notes
                ) VALUES (
                    %s, 'TRADE_DECISION', 0,
                    %s, %s, %s,
                    %s
                )
            ''', (
                self.session_id,
                components.get('expected_pnl', 0),
                roi,
                'ABORT_LOW_ROI' if aborted else 'APPROVED',
                str(components)
            ))
            self.conn.commit()
        except Exception as e:
            logger.warning(f"Failed to log trade decision: {e}")
            try:
                self.conn.rollback()
            except:
                pass


# =============================================================================
# TESTING
# =============================================================================

def test_cost_controller():
    """Test the cost controller with simulated steps."""
    logger.info("=" * 60)
    logger.info("INFORAGE COST CONTROLLER TEST")
    logger.info("=" * 60)

    controller = InForageCostController()

    # Simulate a research session
    steps = [
        (StepType.DB_QUERY, 0.8),      # Initial DB lookup
        (StepType.API_CALL, 0.6),      # First API call
        (StepType.LLM_INFERENCE, 0.5), # LLM processing
        (StepType.API_CALL, 0.4),      # Second API call
        (StepType.API_CALL, 0.3),      # Third API call
        (StepType.API_CALL, 0.2),      # Fourth API call - should abort
        (StepType.API_CALL, 0.1),      # Fifth - definitely abort
    ]

    for i, (step_type, predicted_gain) in enumerate(steps):
        result = controller.check_cost(step_type, predicted_gain)

        logger.info(f"Step {i+1}: {step_type.value}")
        logger.info(f"  Predicted Gain: {predicted_gain}")
        logger.info(f"  Cumulative Cost: ${result.cumulative_cost:.4f}")
        logger.info(f"  Predicted ROI: {result.predicted_roi:.2f}x" if result.predicted_roi else "  Predicted ROI: N/A")
        logger.info(f"  Decision: {result.decision.value}")

        if result.should_abort:
            logger.warning(f"  ABORT: {result.abort_reason}")
            break

    # Complete session
    summary = controller.complete_session(actual_gain=0.75)
    logger.info("\nSESSION SUMMARY:")
    logger.info(f"  Total Steps: {summary.get('total_steps', controller.step_count)}")
    logger.info(f"  Final Cost: ${summary.get('final_cost', controller.total_cost):.4f}")
    logger.info(f"  Was Aborted: {summary.get('was_aborted', controller.aborted)}")
    if controller.abort_reason:
        logger.info(f"  Abort Reason: {controller.abort_reason}")

    return summary


if __name__ == "__main__":
    test_cost_controller()
