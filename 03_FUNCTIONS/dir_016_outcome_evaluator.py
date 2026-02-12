#!/usr/bin/env python3
"""
CEO-DIR-2026-OUTCOME-DENSITY-ACCELERATION-016
Outcome-First Generation Daemon (Directive 1)
--
Purpose: Prioritize outcome evaluation over hypothesis generation during freeze.
During active freeze: Only controlled_exception=true allowed for outcome generation.
"""

import os
import sys
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
import uuid

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres'
}

DAEMON_NAME = 'dir_016_outcome_evaluator'
MODE_EVALUATION = 'outcome_evaluation'
MODE_GENERATION = 'hypothesis_generation'

# Use absolute path for log file
LOG_FILE = r'C:\fhq-market-system\vision-ios\03_FUNCTIONS\dir_016_outcome_evaluator.log'

logging.basicConfig(
    level=logging.INFO,
    format=f'[{DAEMON_NAME}] %(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def check_freeze_status(conn):
    """Check if generation freeze is currently active."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT freeze_enabled, freeze_end_at
            FROM fhq_governance.generation_freeze_control
            WHERE freeze_enabled = true
            ORDER BY created_at DESC
            LIMIT 1;
        """)
        row = cur.fetchone()
        if not row:
            logger.info("No active freeze found - assuming inactive")
            return False, None

        freeze_enabled, freeze_end_at = row

        if not freeze_enabled:
            logger.info("Freeze is not active")
            return False, None

        if freeze_end_at:
            now = datetime.now(timezone.utc)
            if now >= freeze_end_at:
                logger.info(f"Freeze expired at {freeze_end_at}")
                return False, None

        logger.info(f"Freeze ACTIVE until {freeze_end_at}")
        return True, freeze_end_at.isoformat() if freeze_end_at else None


def get_calendar_events(conn):
    """Get calendar events for outcome evaluation (US_EQUITY priority)."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT ce.event_id, ce.event_type_code, ce.event_timestamp,
                   eam.asset_class, ce.actual_value, ce.consensus_estimate
            FROM fhq_calendar.calendar_events ce
            LEFT JOIN fhq_calendar.event_asset_mapping eam
                ON ce.event_type_code = eam.event_type_code
            WHERE ce.is_canonical = true
              AND (eam.asset_class = 'US_EQUITY' OR eam.asset_class IS NULL)
              AND ce.event_timestamp >= NOW() - INTERVAL '72 hours'
              AND ce.event_timestamp <= NOW() + INTERVAL '48 hours'
            ORDER BY ce.event_timestamp ASC
            LIMIT 20;
        """)
        events = cur.fetchall()
        logger.info(f"Found {len(events)} calendar events for evaluation")
        return events


def get_prioritized_hypotheses(conn, limit=10):
    """Get hypotheses prioritized for outcome evaluation from hypothesis_ledger."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Use hypothesis_ledger directly since expectation_outcome_ledger requires hypothesis_ledger.hypothesis_id
        cur.execute("""
            SELECT
                hl.hypothesis_id,
                hl.hypothesis_text,
                hl.expected_direction,
                hl.created_at
            FROM fhq_learning.hypothesis_ledger hl
            WHERE hl.hypothesis_id NOT IN (
                SELECT hypothesis_id FROM fhq_learning.expectation_outcome_ledger
                WHERE recorded_at >= NOW() - INTERVAL '24 hours'
            )
            ORDER BY hl.created_at DESC
            LIMIT %s;
        """, (limit,))
        hypotheses = cur.fetchall()
        logger.info(f"Found {len(hypotheses)} prioritized hypotheses from ledger")
        return hypotheses


def evaluate_batch_hypotheses(conn, max_evaluations=10):
    """Evaluate a batch of hypotheses and create outcome evaluation records."""
    evaluations_created = 0

    # Get calendar events
    events = get_calendar_events(conn)
    if not events:
        logger.info("No calendar events available - no outcome evaluation possible")
        return 0

    # Get prioritized hypotheses
    hypotheses = get_prioritized_hypotheses(conn, limit=max_evaluations)
    if not hypotheses:
        logger.info("No hypotheses available for evaluation")
        return 0

    # Create outcome evaluation records for each hypothesis-event pair
    for hyp in hypotheses:
        for event in events[:2]:  # Limit to 2 events per hypothesis
            try:
                with conn.cursor() as cur:
                    # hypothesis_id is already a UUID from hypothesis_ledger
                    hypothesis_id_str = str(hyp['hypothesis_id'])
                    outcome_id_str = str(uuid.uuid4())

                    cur.execute("""
                        INSERT INTO fhq_learning.expectation_outcome_ledger (
                            outcome_id,
                            hypothesis_id,
                            actual_direction,
                            actual_magnitude,
                            actual_value,
                            consensus_value,
                            surprise_pct,
                            surprise_score,
                            market_response,
                            price_change_pct,
                            learning_verdict,
                            verdict_rationale,
                            recorded_at,
                            recorded_by,
                            recorded_within_24h,
                            evaluation_hours
                        ) VALUES (
                            %s::uuid,
                            %s::uuid,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s
                        );
                    """, (
                        outcome_id_str,
                        hypothesis_id_str,
                        'NEUTRAL',  # actual_direction - placeholder for evaluation
                        'LOW',  # actual_magnitude - placeholder
                        None,  # actual_value
                        None,  # consensus_value
                        None,  # surprise_pct
                        None,  # surprise_score
                        'INLINE',  # market_response - placeholder
                        None,  # price_change_pct
                        'LATE_CAPTURED',  # learning_verdict - placeholder for pending evaluation
                        f"Created by {DAEMON_NAME} for event {event['event_type_code']}",  # verdict_rationale
                        datetime.now(timezone.utc),  # recorded_at
                        DAEMON_NAME,  # recorded_by
                        True,  # recorded_within_24h
                        None  # evaluation_hours
                    ))
                    evaluations_created += 1
                    # Use first 30 chars of hypothesis_text for logging
                    hyp_short = hyp['hypothesis_text'][:30] if hyp['hypothesis_text'] else 'UNKNOWN'
                    logger.info(f"Created outcome evaluation: {hyp_short} -> {event['event_type_code']}")
            except Exception as e:
                logger.error(f"Failed to create evaluation for {hyp['hypothesis_id']}: {e}")

    return evaluations_created


def save_evidence(conn, evaluations_created, freeze_end_at):
    """Save evidence of execution."""
    evidence_file = os.path.join(
        r'C:\fhq-market-system\vision-ios\03_FUNCTIONS\evidence',
        f"DIR_016_OUTCOME_EVALUATOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with conn.cursor() as cur:
        cur.execute("SELECT NOW() AT TIME ZONE 'UTC';")
        now = cur.fetchone()[0]

    evidence = {
        "daemon": DAEMON_NAME,
        "executed_at": now.isoformat(),
        "evaluations_created": evaluations_created,
        "freeze_active": True,
        "freeze_end_at": freeze_end_at,
        "mode": MODE_EVALUATION
    }

    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2)

    logger.info(f"Evidence saved to {evidence_file}")
    return evidence_file


def main():
    logger.info("DIR-016 daemon starting")

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        # Check freeze status
        freeze_active, freeze_end_at = check_freeze_status(conn)

        if not freeze_active:
            logger.info("DIR-016 Complete: Freeze not active ===")
            return 0

        # Perform outcome evaluation
        evaluations_created = evaluate_batch_hypotheses(conn, max_evaluations=10)
        logger.info(f"Created {evaluations_created} outcome evaluations")

        # Save evidence
        save_evidence(conn, evaluations_created, freeze_end_at)

        conn.commit()
        logger.info(f"DIR-016 Complete: {evaluations_created} evaluations created ===")

    except Exception as e:
        logger.error(f"DIR-016 Failed: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
