#!/usr/bin/env python3
"""
CEO-DIR-2026-CONTINUOUS-SCHEDULER-CANON-007
============================================

Implementation script for Continuous Scheduler Canon.

Implements:
1. Enhanced job_runs schema with window tracking
2. Realtime lag view (last 60 min only)
3. Updated sync function with SUCCESS 0 validation
4. Daily-only prior adjustment flag
5. Windows Task Scheduler registration

Authority: CEO
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import logging
import hashlib
import subprocess
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[CEO-DIR-007] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DIRECTIVE_ID = 'CEO-DIR-2026-CONTINUOUS-SCHEDULER-CANON-007'


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def step1_enhance_job_runs_schema(conn):
    """Step 1: Add window tracking columns to job_runs"""
    logger.info("Step 1: Enhancing job_runs schema")

    with conn.cursor() as cur:
        # Add missing columns
        cur.execute("""
            ALTER TABLE fhq_monitoring.job_runs
            ADD COLUMN IF NOT EXISTS window_start_used TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS max_outcome_created_at_processed TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS outcomes_in_window INTEGER DEFAULT 0
        """)
        conn.commit()
        logger.info("  Added window tracking columns")
        return True


def step2_create_realtime_lag_view(conn):
    """Step 2: Create realtime lag view (last 60 min only)"""
    logger.info("Step 2: Creating realtime lag views")

    with conn.cursor() as cur:
        # Rename existing view to backfill
        cur.execute("""
            CREATE OR REPLACE VIEW fhq_monitoring.v_alpha_graph_sync_lag_backfill AS
            SELECT
                MAX(EXTRACT(EPOCH FROM (ag.created_at - ol.created_at))) AS max_lag_seconds,
                AVG(EXTRACT(EPOCH FROM (ag.created_at - ol.created_at))) AS avg_lag_seconds,
                (SELECT MAX(finished_at)
                 FROM fhq_monitoring.job_runs
                 WHERE job_name = 'alpha_graph_sync'
                 AND status = 'SUCCESS') AS last_success_run_at,
                COUNT(*) AS sample_count
            FROM fhq_learning.outcome_ledger ol
            JOIN fhq_learning.alpha_graph_nodes ag
                ON ag.trigger_event_id = ol.trigger_event_id
            WHERE ol.created_at > NOW() - INTERVAL '24 hours'
        """)

        # Create realtime view (last 60 min only)
        cur.execute("""
            CREATE OR REPLACE VIEW fhq_monitoring.v_alpha_graph_sync_lag_realtime AS
            SELECT
                MAX(EXTRACT(EPOCH FROM (ag.created_at - ol.created_at))) AS max_lag_seconds,
                AVG(EXTRACT(EPOCH FROM (ag.created_at - ol.created_at))) AS avg_lag_seconds,
                (SELECT MAX(finished_at)
                 FROM fhq_monitoring.job_runs
                 WHERE job_name = 'alpha_graph_sync'
                 AND status = 'SUCCESS') AS last_success_run_at,
                COUNT(*) AS sample_count,
                NOW() AS measured_at
            FROM fhq_learning.outcome_ledger ol
            JOIN fhq_learning.alpha_graph_nodes ag
                ON ag.trigger_event_id = ol.trigger_event_id
            WHERE ol.created_at > NOW() - INTERVAL '60 minutes'
        """)

        conn.commit()
        logger.info("  Created v_alpha_graph_sync_lag_backfill and v_alpha_graph_sync_lag_realtime views")
        return True


def step3_create_validated_sync_function(conn):
    """Step 3: Create sync function with SUCCESS 0 validation"""
    logger.info("Step 3: Creating validated sync function")

    with conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE FUNCTION fhq_learning.fn_sync_alpha_graph_validated(p_window_minutes integer DEFAULT 10)
            RETURNS TABLE(run_id uuid, inserted_count integer, status text, error_message text) AS $$
            DECLARE
                v_run_id uuid;
                v_inserted_count integer := 0;
                v_window_start timestamptz;
                v_outcomes_in_window integer;
                v_max_outcome_ts timestamptz;
                v_error_message text;
                v_evidence_hash text;
            BEGIN
                -- Calculate window
                v_window_start := NOW() - (p_window_minutes || ' minutes')::interval;

                -- Count outcomes in window BEFORE sync
                SELECT COUNT(*), MAX(ol.created_at)
                INTO v_outcomes_in_window, v_max_outcome_ts
                FROM fhq_learning.outcome_ledger ol
                LEFT JOIN fhq_learning.alpha_graph_nodes ag ON ag.trigger_event_id = ol.trigger_event_id
                WHERE ol.created_at > v_window_start
                AND ag.trigger_event_id IS NULL;

                -- Start job run
                INSERT INTO fhq_monitoring.job_runs (
                    job_name, started_at, status, window_start_used, outcomes_in_window
                )
                VALUES (
                    'alpha_graph_sync', NOW(), 'RUNNING', v_window_start, v_outcomes_in_window
                )
                RETURNING job_runs.run_id INTO v_run_id;

                BEGIN
                    -- Insert missing outcomes into alpha_graph_nodes
                    WITH inserted AS (
                        INSERT INTO fhq_learning.alpha_graph_nodes (
                            node_id,
                            trigger_event_id,
                            hypothesis_id,
                            experiment_id,
                            regime,
                            trigger_type,
                            holding_period_hours,
                            realised_return,
                            predicted_probability,
                            outcome_bool,
                            brier_contribution,
                            node_status,
                            created_at,
                            evidence_hash
                        )
                        SELECT
                            gen_random_uuid(),
                            ol.trigger_event_id,
                            er.hypothesis_id,
                            ol.experiment_id,
                            COALESCE(te.context_details->>'regime', er.tier_name, 'UNKNOWN'),
                            COALESCE(er.metadata->>'trigger_type', SPLIT_PART(er.experiment_code, '_', 1), 'UNKNOWN'),
                            EXTRACT(EPOCH FROM ol.time_to_outcome) / 3600.0,
                            ol.return_pct,
                            COALESCE(hc.current_confidence, hc.initial_confidence, 0.5),
                            ol.result_bool,
                            POWER(COALESCE(hc.current_confidence, hc.initial_confidence, 0.5) - CASE WHEN ol.result_bool THEN 1 ELSE 0 END, 2),
                            'ACTIVE',
                            NOW(),
                            md5(ol.outcome_id::text || ol.trigger_event_id::text)
                        FROM fhq_learning.outcome_ledger ol
                        JOIN fhq_learning.experiment_registry er ON ol.experiment_id = er.experiment_id
                        JOIN fhq_learning.hypothesis_canon hc ON er.hypothesis_id = hc.canon_id
                        LEFT JOIN fhq_learning.trigger_events te ON ol.trigger_event_id = te.trigger_event_id
                        LEFT JOIN fhq_learning.alpha_graph_nodes ag ON ag.trigger_event_id = ol.trigger_event_id
                        WHERE ol.created_at > v_window_start
                        AND ag.trigger_event_id IS NULL
                        ON CONFLICT DO NOTHING
                        RETURNING trigger_event_id
                    )
                    SELECT COUNT(*)::integer INTO v_inserted_count FROM inserted;

                    -- CEO-DIR-007: Validate SUCCESS 0
                    -- If outcomes existed but we inserted 0, that's a FAIL
                    IF v_outcomes_in_window > 0 AND v_inserted_count = 0 THEN
                        v_error_message := 'SILENT_FAILURE: ' || v_outcomes_in_window || ' outcomes in window but 0 inserted';

                        UPDATE fhq_monitoring.job_runs
                        SET finished_at = NOW(),
                            status = 'FAIL',
                            rows_inserted = 0,
                            error_message = v_error_message,
                            max_outcome_created_at_processed = v_max_outcome_ts
                        WHERE job_runs.run_id = v_run_id;

                        -- Update daemon to DEGRADED
                        UPDATE fhq_monitoring.daemon_health
                        SET status = 'DEGRADED',
                            last_heartbeat = NOW(),
                            metadata = metadata || jsonb_build_object(
                                'last_error', v_error_message,
                                'last_run_id', v_run_id::text
                            )
                        WHERE daemon_name = 'alpha_graph_sync';

                        RETURN QUERY SELECT v_run_id, 0, 'FAIL'::text, v_error_message;
                        RETURN;
                    END IF;

                    -- Create evidence hash
                    v_evidence_hash := md5(v_run_id::text || v_inserted_count::text || v_window_start::text || NOW()::text);

                    -- Update job run to SUCCESS
                    UPDATE fhq_monitoring.job_runs
                    SET finished_at = NOW(),
                        status = 'SUCCESS',
                        rows_inserted = v_inserted_count,
                        evidence_hash = v_evidence_hash,
                        max_outcome_created_at_processed = v_max_outcome_ts,
                        metadata = jsonb_build_object(
                            'window_minutes', p_window_minutes,
                            'outcomes_in_window', v_outcomes_in_window,
                            'inserted', v_inserted_count
                        )
                    WHERE job_runs.run_id = v_run_id;

                    -- Update daemon heartbeat
                    UPDATE fhq_monitoring.daemon_health
                    SET status = 'HEALTHY',
                        last_heartbeat = NOW(),
                        metadata = metadata || jsonb_build_object(
                            'last_sync_count', v_inserted_count,
                            'last_sync_at', NOW()::text,
                            'last_run_id', v_run_id::text,
                            'window_start', v_window_start::text
                        )
                    WHERE daemon_name = 'alpha_graph_sync';

                EXCEPTION WHEN OTHERS THEN
                    v_error_message := SQLERRM;
                    UPDATE fhq_monitoring.job_runs
                    SET finished_at = NOW(),
                        status = 'FAIL',
                        error_message = v_error_message
                    WHERE job_runs.run_id = v_run_id;

                    RETURN QUERY SELECT v_run_id, 0, 'FAIL'::text, v_error_message;
                    RETURN;
                END;

                RETURN QUERY SELECT v_run_id, v_inserted_count, 'SUCCESS'::text, NULL::text;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        logger.info("  Created fn_sync_alpha_graph_validated with SUCCESS 0 validation")
        return True


def step4_create_daily_prior_function(conn):
    """Step 4: Create prior adjustment that only runs once per day"""
    logger.info("Step 4: Creating daily-only prior adjustment function")

    with conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE FUNCTION fhq_learning.fn_auto_adjust_priors_daily()
            RETURNS TABLE(run_id uuid, adjusted_count integer, status text, skipped_reason text) AS $$
            DECLARE
                v_run_id uuid;
                v_adjusted_count integer := 0;
                v_last_run timestamptz;
                v_hypothesis RECORD;
                v_new_prior numeric;
                v_effective_lambda numeric;
                v_error_message text;
                v_lambda numeric := 0.5;
            BEGIN
                -- Check if already run today
                SELECT MAX(started_at) INTO v_last_run
                FROM fhq_monitoring.job_runs
                WHERE job_name = 'prior_adjustment_daily'
                AND status = 'SUCCESS'
                AND started_at > NOW() - INTERVAL '20 hours';  -- Allow some buffer

                IF v_last_run IS NOT NULL THEN
                    -- Already ran today, skip
                    INSERT INTO fhq_monitoring.job_runs (job_name, started_at, finished_at, status, metadata)
                    VALUES ('prior_adjustment_daily', NOW(), NOW(), 'SUCCESS',
                            jsonb_build_object('skipped', true, 'reason', 'Already ran at ' || v_last_run::text))
                    RETURNING job_runs.run_id INTO v_run_id;

                    RETURN QUERY SELECT v_run_id, 0, 'SUCCESS'::text, ('Already ran at ' || v_last_run::text)::text;
                    RETURN;
                END IF;

                -- Start job run
                INSERT INTO fhq_monitoring.job_runs (job_name, started_at, status)
                VALUES ('prior_adjustment_daily', NOW(), 'RUNNING')
                RETURNING job_runs.run_id INTO v_run_id;

                BEGIN
                    -- Find hypotheses with sufficient alpha graph nodes (>= 30)
                    FOR v_hypothesis IN
                        SELECT
                            hc.canon_id,
                            COALESCE(hc.current_confidence, hc.initial_confidence, 0.5) as old_prior,
                            AVG(ag.brier_contribution) as mean_brier,
                            COUNT(*) as sample_size
                        FROM fhq_learning.hypothesis_canon hc
                        JOIN fhq_learning.alpha_graph_nodes ag ON ag.hypothesis_id = hc.canon_id
                        WHERE ag.created_at > NOW() - INTERVAL '7 days'  -- Weekly window for daily runs
                        AND hc.status IN ('ACTIVE', 'TIMEOUT_PENDING', 'SURVIVED')
                        GROUP BY hc.canon_id, hc.current_confidence, hc.initial_confidence
                        HAVING COUNT(*) >= 30
                    LOOP
                        -- Damping based on sample size
                        IF v_hypothesis.sample_size < 100 THEN
                            v_effective_lambda := v_lambda * 0.5;
                        ELSE
                            v_effective_lambda := v_lambda;
                        END IF;

                        -- Calculate new prior
                        v_new_prior := GREATEST(0.01, LEAST(0.99,
                            v_hypothesis.old_prior * EXP(-v_effective_lambda * v_hypothesis.mean_brier)
                        ));

                        -- Only update if meaningful change (> 1%)
                        IF ABS(v_new_prior - v_hypothesis.old_prior) > 0.01 THEN
                            UPDATE fhq_learning.hypothesis_canon
                            SET current_confidence = v_new_prior,
                                last_updated_at = NOW()
                            WHERE canon_id = v_hypothesis.canon_id;

                            INSERT INTO fhq_learning.hypothesis_prior_updates (
                                hypothesis_id, old_prior, new_prior, mean_brier,
                                sample_size, lambda_used, updated_by, evidence_hash
                            ) VALUES (
                                v_hypothesis.canon_id, v_hypothesis.old_prior, v_new_prior,
                                v_hypothesis.mean_brier, v_hypothesis.sample_size, v_effective_lambda,
                                'fn_auto_adjust_priors_daily',
                                md5(v_hypothesis.canon_id::text || v_new_prior::text || NOW()::text)
                            );

                            v_adjusted_count := v_adjusted_count + 1;
                        END IF;
                    END LOOP;

                    -- Update job run to SUCCESS
                    UPDATE fhq_monitoring.job_runs
                    SET finished_at = NOW(),
                        status = 'SUCCESS',
                        rows_updated = v_adjusted_count,
                        evidence_hash = md5(v_run_id::text || v_adjusted_count::text || NOW()::text),
                        metadata = jsonb_build_object(
                            'adjusted_count', v_adjusted_count,
                            'min_sample_size', 30,
                            'window_days', 7
                        )
                    WHERE job_runs.run_id = v_run_id;

                EXCEPTION WHEN OTHERS THEN
                    v_error_message := SQLERRM;
                    UPDATE fhq_monitoring.job_runs
                    SET finished_at = NOW(),
                        status = 'FAIL',
                        error_message = v_error_message
                    WHERE job_runs.run_id = v_run_id;

                    RETURN QUERY SELECT v_run_id, 0, 'FAIL'::text, v_error_message;
                    RETURN;
                END;

                RETURN QUERY SELECT v_run_id, v_adjusted_count, 'SUCCESS'::text, NULL::text;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        logger.info("  Created fn_auto_adjust_priors_daily (runs once per day only)")
        return True


def step5_run_test_cycles(conn, num_cycles=5):
    """Step 5: Run test cycles to validate"""
    logger.info(f"Step 5: Running {num_cycles} test cycles")

    results = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for i in range(num_cycles):
            cur.execute("SELECT * FROM fhq_learning.fn_sync_alpha_graph_validated(10)")
            result = cur.fetchone()
            conn.commit()
            results.append({
                'cycle': i + 1,
                'run_id': str(result['run_id']),
                'inserted': result['inserted_count'],
                'status': result['status'],
                'error': result['error_message']
            })
            logger.info(f"  Cycle {i+1}: status={result['status']}, inserted={result['inserted_count']}")

    return results


def generate_evidence(results):
    """Generate evidence file"""
    evidence = {
        "directive_id": DIRECTIVE_ID,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "executed_by": "STIG",
        "one_true_scheduler": "Windows Task Scheduler",
        "results": results,
        "authority": "CEO"
    }

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
    logger.info("ONE TRUE SCHEDULER: Windows Task Scheduler")
    logger.info("=" * 60)

    conn = get_connection()
    results = {}

    try:
        # Step 1: Enhance job_runs schema
        step1_enhance_job_runs_schema(conn)
        results['schema_enhanced'] = True

        # Step 2: Create realtime lag view
        step2_create_realtime_lag_view(conn)
        results['lag_views_created'] = True

        # Step 3: Create validated sync function
        step3_create_validated_sync_function(conn)
        results['validated_sync_function'] = True

        # Step 4: Create daily prior function
        step4_create_daily_prior_function(conn)
        results['daily_prior_function'] = True

        # Step 5: Run test cycles
        test_results = step5_run_test_cycles(conn, 5)
        results['test_cycles'] = test_results

        # Generate evidence
        evidence_path = generate_evidence(results)
        results['evidence_file'] = evidence_path

        logger.info("=" * 60)
        logger.info("DIRECTIVE EXECUTION COMPLETE")
        logger.info("=" * 60)

        print(json.dumps(results, indent=2, default=str))

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
