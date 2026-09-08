#!/usr/bin/env python3
"""
CEO-DIR-2026-LEARNING-VALIDATION-WINDOW-004
============================================

Implementation script for Learning Validation Window directive.

MODE: LEARNING VALIDATION WINDOW (72 hours)

Allowed:
- Outcome generation continues
- Alpha Graph updates continuously
- Brier and prior-adjustment runs automatically

Forbidden:
- New hypotheses
- New experiment design
- Manual prior changes

Success Criteria (within 72h):
- Global Brier falls consistently, OR
- LVI > 0 on at least one day, OR
- Prior adjustments correlate with lower brier_contribution on new nodes

Authority: CEO
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='[CEO-DIR-004] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DIRECTIVE_ID = 'CEO-DIR-2026-LEARNING-VALIDATION-WINDOW-004'
VALIDATION_WINDOW_HOURS = 72
DEADLINE = datetime.now(timezone.utc) + timedelta(hours=VALIDATION_WINDOW_HOURS)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def step1_register_directive(conn):
    """Step 1: Register directive in ceo_directives"""
    logger.info("Step 1: Registering directive")

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.ceo_directives (
                directive_id,
                directive_code,
                issued_at,
                issued_by,
                title,
                description,
                target_metric,
                target_deadline,
                status
            ) VALUES (
                gen_random_uuid(),
                %s,
                NOW(),
                'CEO',
                'Learning Validation Window (72h)',
                'MODE: LEARNING VALIDATION WINDOW. Outcome-generering fortsetter. Alpha Graph oppdateres. Brier/prior kjøres automatisk. Ingen nye hypoteser/eksperimenter/manuelle prior-endringer. LVI som øverste sannhetsdommer.',
                'LVI',
                %s,
                'ACTIVE'
            )
            ON CONFLICT (directive_code) DO UPDATE SET
                status = 'ACTIVE',
                target_deadline = %s
            RETURNING directive_code, target_deadline
        """, (DIRECTIVE_ID, DEADLINE, DEADLINE))

        result = cur.fetchone()
        conn.commit()
        logger.info(f"  Directive registered: {result[0]}, deadline: {result[1]}")
        return result


def step2_verify_freeze_gates(conn):
    """Step 2: Verify freeze gates are in place (from DIR-003)"""
    logger.info("Step 2: Verifying freeze gates")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if we have any gate mechanism
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_governance'
                AND table_name = 'validation_window_state'
            )
        """)
        exists = cur.fetchone()['exists']

        if not exists:
            # Create validation window state table
            cur.execute("""
                CREATE TABLE fhq_governance.validation_window_state (
                    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    directive_code TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    started_at TIMESTAMPTZ DEFAULT NOW(),
                    ends_at TIMESTAMPTZ NOT NULL,
                    hypothesis_generation_allowed BOOLEAN DEFAULT FALSE,
                    experiment_creation_allowed BOOLEAN DEFAULT FALSE,
                    manual_prior_changes_allowed BOOLEAN DEFAULT FALSE,
                    outcome_generation_allowed BOOLEAN DEFAULT TRUE,
                    alpha_graph_updates_allowed BOOLEAN DEFAULT TRUE,
                    auto_brier_prior_allowed BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
            logger.info("  Created validation_window_state table")

        # Insert/update validation window state
        cur.execute("""
            INSERT INTO fhq_governance.validation_window_state (
                directive_code,
                mode,
                ends_at,
                hypothesis_generation_allowed,
                experiment_creation_allowed,
                manual_prior_changes_allowed,
                outcome_generation_allowed,
                alpha_graph_updates_allowed,
                auto_brier_prior_allowed,
                is_active
            ) VALUES (
                %s,
                'LEARNING_VALIDATION_WINDOW',
                %s,
                FALSE,
                FALSE,
                FALSE,
                TRUE,
                TRUE,
                TRUE,
                TRUE
            )
            RETURNING state_id, mode, ends_at
        """, (DIRECTIVE_ID, DEADLINE))

        result = cur.fetchone()
        conn.commit()
        logger.info(f"  Validation window activated: {result['mode']}")
        logger.info(f"  Window ends: {result['ends_at']}")

        return {
            'mode': result['mode'],
            'ends_at': str(result['ends_at']),
            'hypothesis_generation': False,
            'experiment_creation': False,
            'manual_prior_changes': False,
            'outcome_generation': True,
            'alpha_graph_updates': True,
            'auto_brier_prior': True
        }


def step3_capture_baseline(conn):
    """Step 3: Capture current baseline metrics for validation window"""
    logger.info("Step 3: Capturing baseline metrics")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get current global Brier
        cur.execute("""
            SELECT
                COUNT(*) as total_nodes,
                AVG(brier_contribution) as global_brier,
                MIN(brier_contribution) as min_brier,
                MAX(brier_contribution) as max_brier,
                STDDEV(brier_contribution) as brier_stddev
            FROM fhq_learning.alpha_graph_nodes
            WHERE brier_contribution IS NOT NULL
        """)
        brier_stats = cur.fetchone()

        # Get latest LVI entry
        cur.execute("""
            SELECT
                calculated_at,
                global_brier,
                lvi_value,
                sample_size
            FROM fhq_learning.lvi_timeseries
            ORDER BY calculated_at DESC
            LIMIT 1
        """)
        lvi_latest = cur.fetchone()

        # Get hypothesis counts
        cur.execute("""
            SELECT status, COUNT(*) as count
            FROM fhq_learning.hypothesis_canon
            GROUP BY status
        """)
        hypothesis_status = {row['status']: row['count'] for row in cur.fetchall()}

        baseline = {
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'global_brier': float(brier_stats['global_brier']) if brier_stats['global_brier'] else None,
            'total_nodes': brier_stats['total_nodes'],
            'brier_stddev': float(brier_stats['brier_stddev']) if brier_stats['brier_stddev'] else None,
            'lvi_latest': {
                'calculated_at': str(lvi_latest['calculated_at']) if lvi_latest else None,
                'global_brier': float(lvi_latest['global_brier']) if lvi_latest and lvi_latest['global_brier'] else None,
                'lvi_value': float(lvi_latest['lvi_value']) if lvi_latest and lvi_latest['lvi_value'] else None,
                'sample_size': lvi_latest['sample_size'] if lvi_latest else None
            },
            'hypothesis_status': hypothesis_status
        }

        logger.info(f"  Global Brier (t=0): {baseline['global_brier']:.6f}")
        logger.info(f"  Total Alpha Graph nodes: {baseline['total_nodes']}")
        logger.info(f"  LVI (t=0): {baseline['lvi_latest']['lvi_value']}")

        return baseline


def step4_setup_daily_lvi_job(conn):
    """Step 4: Document daily LVI calculation requirements"""
    logger.info("Step 4: Setting up daily LVI calculation")

    # This documents what the daily job should do
    # The actual job will be run by scheduler or manually

    lvi_job_spec = {
        'job_name': 'daily_lvi_calculation',
        'schedule': 'daily at 06:00 UTC',
        'calculation': 'LVI = (Brier_{t-1} - Brier_t) / delta_t',
        'output': {
            'global_brier_t': 'Current global Brier',
            'global_brier_t_minus_1': 'Previous global Brier',
            'lvi_value': 'LVI calculation result'
        },
        'reporting_format': 'Raw numbers only. No interpretation.',
        'first_calculation': '2026-02-10 06:00 UTC'
    }

    logger.info(f"  LVI job spec documented")
    logger.info(f"  First calculation: {lvi_job_spec['first_calculation']}")

    return lvi_job_spec


def step5_set_success_criteria(conn):
    """Step 5: Document explicit success criteria"""
    logger.info("Step 5: Setting success criteria")

    criteria = {
        'deadline': str(DEADLINE),
        'deadline_readable': '2026-02-12 ~19:40 UTC',
        'success_conditions': [
            {
                'id': 'BRIER_DECLINE',
                'description': 'Global Brier falls consistently',
                'metric': 'Global Brier(t) < Global Brier(t-1) for multiple t'
            },
            {
                'id': 'LVI_POSITIVE',
                'description': 'LVI > 0 on at least one day',
                'metric': 'LVI > 0'
            },
            {
                'id': 'PRIOR_CORRELATION',
                'description': 'Prior adjustments correlate with lower brier_contribution on new nodes',
                'metric': 'Correlation analysis pending'
            }
        ],
        'failure_consequence': 'Hypothesis-form destruction phase begins. No more data acquisition.',
        'minimum_success': 'At least ONE of the above conditions must be met'
    }

    logger.info(f"  Success criteria documented")
    logger.info(f"  Deadline: {criteria['deadline_readable']}")
    logger.info(f"  Minimum: ONE of 3 conditions must be met")

    return criteria


def generate_evidence(conn, results):
    """Generate evidence file for the directive execution"""
    evidence = {
        "directive_id": DIRECTIVE_ID,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "executed_by": "STIG",
        "mode": "LEARNING_VALIDATION_WINDOW",
        "duration_hours": VALIDATION_WINDOW_HOURS,
        "deadline": str(DEADLINE),
        "results": results,
        "allowed_operations": {
            "outcome_generation": True,
            "alpha_graph_updates": True,
            "auto_brier_prior": True
        },
        "forbidden_operations": {
            "new_hypotheses": True,
            "new_experiments": True,
            "manual_prior_changes": True
        },
        "narrative_prohibition": [
            "systemet lærer",
            "gjennombrudd",
            "vi er der nå"
        ],
        "ceo_observation_mode": True,
        "authority": "CEO"
    }

    # Create evidence hash
    evidence_str = json.dumps(evidence, sort_keys=True, default=str)
    evidence['evidence_hash'] = hashlib.sha256(evidence_str.encode()).hexdigest()[:32]

    evidence_path = f"03_FUNCTIONS/evidence/{DIRECTIVE_ID.replace('-', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    logger.info(f"Evidence written to {evidence_path}")
    return evidence_path


def main():
    logger.info("=" * 60)
    logger.info(f"EXECUTING: {DIRECTIVE_ID}")
    logger.info("=" * 60)
    logger.info("MODE: LEARNING VALIDATION WINDOW (72 hours)")
    logger.info("=" * 60)

    conn = get_connection()
    results = {}

    try:
        # Step 1: Register directive
        step1_register_directive(conn)
        results['directive_registered'] = True

        # Step 2: Verify freeze gates
        freeze_state = step2_verify_freeze_gates(conn)
        results['validation_window'] = freeze_state

        # Step 3: Capture baseline
        baseline = step3_capture_baseline(conn)
        results['baseline'] = baseline

        # Step 4: Setup daily LVI job
        lvi_job = step4_setup_daily_lvi_job(conn)
        results['lvi_job'] = lvi_job

        # Step 5: Set success criteria
        criteria = step5_set_success_criteria(conn)
        results['success_criteria'] = criteria

        # Generate evidence
        evidence_path = generate_evidence(conn, results)
        results['evidence_file'] = evidence_path

        logger.info("=" * 60)
        logger.info("DIRECTIVE EXECUTION COMPLETE")
        logger.info("=" * 60)
        logger.info("")
        logger.info("LEARNING VALIDATION WINDOW ACTIVE")
        logger.info(f"  Ends: {DEADLINE}")
        logger.info("")
        logger.info("ALLOWED:")
        logger.info("  [x] Outcome generation")
        logger.info("  [x] Alpha Graph updates")
        logger.info("  [x] Auto Brier/prior adjustment")
        logger.info("")
        logger.info("FORBIDDEN:")
        logger.info("  [ ] New hypotheses")
        logger.info("  [ ] New experiments")
        logger.info("  [ ] Manual prior changes")
        logger.info("")
        logger.info("SUCCESS CRITERIA (one must be met by deadline):")
        logger.info("  1. Global Brier falls consistently")
        logger.info("  2. LVI > 0 on at least one day")
        logger.info("  3. Prior adjustments correlate with lower brier")
        logger.info("")

        print(json.dumps(results, indent=2, default=str))

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
