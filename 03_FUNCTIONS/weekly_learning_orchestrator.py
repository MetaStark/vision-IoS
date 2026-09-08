#!/usr/bin/env python3
"""
CEO-DIR-2026-021 STEP 4: Weekly Learning Orchestrator
======================================================
Authority: CEO Directive CEO-DIR-2026-021
Classification: P0 - Blocking All Learning
Purpose: State-gated weekly learning execution with court-proof evidence

CEO Conditions (non-negotiable):
1. State-gated execution (learning_eligible, cognitive_fasting, defcon, paper_trading)
2. Court-proof evidence for every run (success or blocked)
3. ISO week idempotency guard (one run per week)

Scope Lock: Orchestrator = scheduler + gatekeeper only. No logic changes.

Usage:
    python weekly_learning_orchestrator.py          # Execute weekly learning cycle
    python weekly_learning_orchestrator.py --dry-run  # Show what would run
"""

import os
import sys
import json
import hashlib
import subprocess
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("weekly_learning_orchestrator")

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__))
LESSON_EXTRACTION_SCRIPT = os.path.join(FUNCTIONS_DIR, "ios010_lesson_extraction_engine.py")

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Establish database connection"""
    return psycopg2.connect(**DB_CONFIG)

# =============================================================================
# GATE CHECK AND RUN INITIALIZATION
# =============================================================================

def init_learning_run(conn) -> Tuple[bool, Dict[str, Any]]:
    """
    Initialize weekly learning run with state gate check.
    CEO Condition 1 & 3: State-gated + idempotency.

    Returns: (should_proceed, run_info)
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM fhq_governance.init_weekly_learning_run('LARS_ORCHESTRATOR')
        """)

        result = cur.fetchone()
        conn.commit()

        run_info = {
            'run_id': str(result['run_id']),
            'iso_year': result['iso_year'],
            'iso_week': result['iso_week'],
            'gate_passed': result['gate_passed'],
            'block_reason': result['block_reason'],
            'already_ran_this_week': result['already_ran_this_week']
        }

        should_proceed = result['gate_passed'] and not result['already_ran_this_week']

        return should_proceed, run_info

# =============================================================================
# LESSON EXTRACTION EXECUTION
# =============================================================================

def execute_lesson_extraction(run_id: str) -> Dict[str, Any]:
    """
    Execute ios010_lesson_extraction_engine.py
    Scope Lock: No logic changes, just execution.
    """
    logger.info(f"Executing lesson extraction for run {run_id}")

    start_time = datetime.now(timezone.utc)

    try:
        result = subprocess.run(
            [sys.executable, LESSON_EXTRACTION_SCRIPT],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes max
        )

        execution_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        if result.returncode == 0:
            # Parse JSON output
            try:
                output = json.loads(result.stdout)
                return {
                    'status': 'SUCCESS',
                    'lessons_created': output.get('lessons_stored', 0),
                    'regret_records_created': 1 if output.get('suppression_lessons', 0) > 0 else 0,
                    'suppressions_processed': 0,  # Not tracked in current version
                    'execution_duration_ms': execution_duration_ms,
                    'error_message': None,
                    'raw_output': output
                }
            except json.JSONDecodeError:
                return {
                    'status': 'SUCCESS',
                    'lessons_created': 0,
                    'regret_records_created': 0,
                    'suppressions_processed': 0,
                    'execution_duration_ms': execution_duration_ms,
                    'error_message': None,
                    'raw_output': {'stdout': result.stdout}
                }
        else:
            return {
                'status': 'FAILED',
                'lessons_created': 0,
                'regret_records_created': 0,
                'suppressions_processed': 0,
                'execution_duration_ms': execution_duration_ms,
                'error_message': result.stderr or 'Unknown error',
                'raw_output': {'stdout': result.stdout, 'stderr': result.stderr}
            }

    except subprocess.TimeoutExpired:
        execution_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return {
            'status': 'FAILED',
            'lessons_created': 0,
            'regret_records_created': 0,
            'suppressions_processed': 0,
            'execution_duration_ms': execution_duration_ms,
            'error_message': 'Execution timeout (600s)',
            'raw_output': None
        }
    except Exception as e:
        execution_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        return {
            'status': 'FAILED',
            'lessons_created': 0,
            'regret_records_created': 0,
            'suppressions_processed': 0,
            'execution_duration_ms': execution_duration_ms,
            'error_message': str(e),
            'raw_output': None
        }

# =============================================================================
# EVIDENCE GENERATION
# =============================================================================

def generate_evidence_artifact(
    conn,
    run_id: str,
    run_info: Dict[str, Any],
    execution_result: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate court-proof evidence artifact for this run.
    CEO Condition 2: Evidence for every run (success or blocked).

    Returns: evidence_id
    """
    # Capture execution state snapshot
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                learning_eligible,
                cognitive_fasting,
                defcon_level::TEXT,
                paper_trading_eligible,
                state_version
            FROM fhq_governance.execution_state
            WHERE state_id = 1
        """)
        state_snapshot = dict(cur.fetchone())

    # Build evidence content
    evidence_content = {
        'directive': 'CEO-DIR-2026-021',
        'step': 'STEP_4',
        'run_id': run_id,
        'iso_year': run_info['iso_year'],
        'iso_week': run_info['iso_week'],
        'gate_passed': run_info['gate_passed'],
        'block_reason': run_info['block_reason'],
        'already_ran_this_week': run_info['already_ran_this_week'],
        'execution_state_snapshot': state_snapshot,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    if execution_result:
        evidence_content['execution_result'] = execution_result

    # Query for weekly_learning_runs snapshot
    raw_query = f"""
        SELECT * FROM fhq_governance.weekly_learning_runs
        WHERE run_id = '{run_id}'::uuid
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(raw_query)
        query_result = [dict(r) for r in cur.fetchall()]

    # Compute hashes
    query_result_hash = hashlib.sha256(json.dumps(query_result, default=str).encode()).hexdigest()
    summary_hash = hashlib.sha256(json.dumps(evidence_content, default=str).encode()).hexdigest()

    # Store evidence
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.epistemic_lesson_evidence (
                evidence_id,
                lesson_id,
                raw_query,
                query_result_hash,
                query_result_snapshot,
                extraction_context,
                created_by,
                created_at
            ) VALUES (
                gen_random_uuid(),
                NULL,  -- Not bound to specific lesson
                %s,
                %s,
                %s,
                %s,
                'LARS_ORCHESTRATOR',
                NOW()
            )
            RETURNING evidence_id
        """, (
            raw_query,
            query_result_hash,
            json.dumps(query_result, default=str),
            json.dumps(evidence_content, default=str)
        ))

        evidence_id = cur.fetchone()[0]
        conn.commit()

    logger.info(f"Generated evidence artifact: {evidence_id}")
    return str(evidence_id)

# =============================================================================
# RUN COMPLETION
# =============================================================================

def complete_learning_run(
    conn,
    run_id: str,
    execution_result: Dict[str, Any],
    evidence_id: str
):
    """Update weekly_learning_runs with completion status"""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_governance.weekly_learning_runs
            SET
                run_status = CASE
                    WHEN %s = 'SUCCESS' THEN 'COMPLETED'
                    ELSE 'FAILED'
                END,
                completed_at = NOW(),
                regret_records_created = %s,
                lessons_created = %s,
                suppressions_processed = %s,
                evidence_id = %s::uuid,
                execution_duration_ms = %s,
                error_message = %s
            WHERE run_id = %s::uuid
        """, (
            execution_result['status'],
            execution_result.get('regret_records_created', 0),
            execution_result.get('lessons_created', 0),
            execution_result.get('suppressions_processed', 0),
            evidence_id,
            execution_result.get('execution_duration_ms'),
            execution_result.get('error_message'),
            run_id
        ))
        conn.commit()

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_weekly_learning_cycle(dry_run: bool = False) -> Dict[str, Any]:
    """
    Main execution function.
    CEO-DIR-2026-021 Step 4: State-gated weekly learning orchestration.
    """
    logger.info("=" * 60)
    logger.info("WEEKLY LEARNING ORCHESTRATOR")
    logger.info("Directive: CEO-DIR-2026-021 Step 4")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info("=" * 60)

    conn = None
    summary = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'dry_run': dry_run,
        'status': 'SUCCESS'
    }

    try:
        conn = get_db_connection()

        # Step 1: Initialize run and check gate (CEO Condition 1 & 3)
        logger.info("Initializing weekly learning run...")
        should_proceed, run_info = init_learning_run(conn)
        summary['run_info'] = run_info

        logger.info(f"Run ID: {run_info['run_id']}")
        logger.info(f"ISO Week: {run_info['iso_year']}-W{run_info['iso_week']}")
        logger.info(f"Gate Passed: {run_info['gate_passed']}")

        if run_info['already_ran_this_week']:
            logger.info("[IDEMPOTENCY] Already ran this ISO week. Skipping.")
            summary['action'] = 'SKIPPED_ALREADY_RAN'
            summary['evidence_id'] = None
            return summary

        if not run_info['gate_passed']:
            logger.warning(f"[GATE BLOCKED] {run_info['block_reason']}")
            summary['action'] = 'GATE_BLOCKED'

            # CEO Condition 2: Generate evidence even when blocked
            evidence_id = generate_evidence_artifact(conn, run_info['run_id'], run_info, None)
            summary['evidence_id'] = evidence_id

            # Update run record with evidence
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_governance.weekly_learning_runs
                    SET evidence_id = %s::uuid
                    WHERE run_id = %s::uuid
                """, (evidence_id, run_info['run_id']))
                conn.commit()

            return summary

        # Gate passed - proceed with execution
        logger.info("[GATE PASSED] Proceeding with learning cycle")

        if dry_run:
            logger.info("[DRY RUN] Would execute ios010_lesson_extraction_engine.py")
            summary['action'] = 'DRY_RUN_GATE_PASSED'
            summary['evidence_id'] = None
            return summary

        # Step 2: Execute lesson extraction
        logger.info("Executing lesson extraction...")
        execution_result = execute_lesson_extraction(run_info['run_id'])
        summary['execution_result'] = execution_result

        logger.info(f"Execution Status: {execution_result['status']}")
        logger.info(f"Lessons Created: {execution_result['lessons_created']}")
        logger.info(f"Duration: {execution_result['execution_duration_ms']}ms")

        # Step 3: Generate evidence (CEO Condition 2)
        logger.info("Generating evidence artifact...")
        evidence_id = generate_evidence_artifact(conn, run_info['run_id'], run_info, execution_result)
        summary['evidence_id'] = evidence_id

        # Step 4: Complete run
        complete_learning_run(conn, run_info['run_id'], execution_result, evidence_id)

        logger.info("Weekly learning cycle complete")
        summary['action'] = 'EXECUTED'
        summary['status'] = execution_result['status']

    except Exception as e:
        logger.error(f"Weekly learning cycle failed: {e}")
        summary['status'] = 'FAILED'
        summary['error_message'] = str(e)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    summary['completed_at'] = datetime.now(timezone.utc).isoformat()
    return summary

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CEO-DIR-2026-021 Step 4: Weekly Learning Orchestrator")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run without executing")
    args = parser.parse_args()

    result = run_weekly_learning_cycle(dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result['status'] == 'SUCCESS' else 1)
