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
        self.session_id = session_id or str(uuid.uuid4())
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
