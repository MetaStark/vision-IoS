#!/usr/bin/env python3
"""
CEO-DIR-2026-TRUTH-ENFORCEMENT-AND-CONTINUOUS-OPS-006
======================================================

Implementation script for Continuous Ops requirements.

P0 Deliverables:
1. Create job_runs table
2. Create lag monitoring view
3. Fix prior update threshold (>= 30)
4. Update fn_sync_alpha_graph to log to job_runs
5. Update fn_auto_adjust_priors to use >= 30 threshold

Authority: CEO
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[CEO-DIR-006] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DIRECTIVE_ID = 'CEO-DIR-2026-TRUTH-ENFORCEMENT-AND-CONTINUOUS-OPS-006'


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def step1_create_job_runs_table(conn):
    """Step 1: Create job_runs table per CEO spec"""
    logger.info("Step 1: Creating job_runs table")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_monitoring'
                AND table_name = 'job_runs'
            )
        """)
        if cur.fetchone()[0]:
            logger.info("  job_runs table already exists")
            return True

        cur.execute("""
            CREATE TABLE fhq_monitoring.job_runs (
                run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                job_name TEXT NOT NULL,
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMPTZ,
                status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAIL')),
                rows_inserted INTEGER DEFAULT 0,
                rows_updated INTEGER DEFAULT 0,
                error_message TEXT,
                evidence_hash TEXT,
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE INDEX idx_job_runs_name_time ON fhq_monitoring.job_runs(job_name, started_at DESC);
            CREATE INDEX idx_job_runs_status ON fhq_monitoring.job_runs(status);
        """)

        conn.commit()
        logger.info("  Created job_runs table with indexes")
        return True


def step2_create_lag_view(conn):
    """Step 2: Create lag monitoring view"""
    logger.info("Step 2: Creating lag monitoring view")

    with conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE VIEW fhq_monitoring.v_alpha_graph_sync_lag AS
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
            WHERE ol.created_at > NOW() - INTERVAL '1 hour'
        """)
        conn.commit()
        logger.info("  Created v_alpha_graph_sync_lag view")
        return True


def step3_update_sync_function_with_logging(conn):
    """Step 3: Update sync function to log to job_runs"""
    logger.info("Step 3: Updating fn_sync_alpha_graph with job_runs logging")

    with conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE FUNCTION fhq_learning.fn_sync_alpha_graph_with_logging(p_since timestamptz)
            RETURNS TABLE(run_id uuid, inserted_count integer, status text) AS $$
            DECLARE
                v_run_id uuid;
                v_inserted_count integer := 0;
                v_error_message text;
                v_evidence_hash text;
            BEGIN
                -- Start job run
                INSERT INTO fhq_monitoring.job_runs (job_name, started_at, status)
                VALUES ('alpha_graph_sync', NOW(), 'RUNNING')
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
                        WHERE ol.created_at > p_since
                        AND ag.trigger_event_id IS NULL
                        ON CONFLICT DO NOTHING
                        RETURNING trigger_event_id
                    )
                    SELECT COUNT(*)::integer INTO v_inserted_count FROM inserted;

                    -- Create evidence hash
                    v_evidence_hash := md5(v_run_id::text || v_inserted_count::text || NOW()::text);

                    -- Update job run to SUCCESS
                    UPDATE fhq_monitoring.job_runs
                    SET finished_at = NOW(),
                        status = 'SUCCESS',
                        rows_inserted = v_inserted_count,
                        evidence_hash = v_evidence_hash,
                        metadata = jsonb_build_object(
                            'since', p_since,
                            'inserted', v_inserted_count
                        )
                    WHERE job_runs.run_id = v_run_id;

                    -- Update daemon heartbeat
                    UPDATE fhq_monitoring.daemon_health
                    SET last_heartbeat = NOW(),
                        metadata = metadata || jsonb_build_object(
                            'last_sync_count', v_inserted_count,
                            'last_sync_at', NOW()::text,
                            'last_run_id', v_run_id::text
                        )
                    WHERE daemon_name = 'alpha_graph_sync';

                EXCEPTION WHEN OTHERS THEN
                    v_error_message := SQLERRM;
                    UPDATE fhq_monitoring.job_runs
                    SET finished_at = NOW(),
                        status = 'FAIL',
                        error_message = v_error_message
                    WHERE job_runs.run_id = v_run_id;

                    RETURN QUERY SELECT v_run_id, 0, 'FAIL'::text;
                    RETURN;
                END;

                RETURN QUERY SELECT v_run_id, v_inserted_count, 'SUCCESS'::text;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        logger.info("  Created fn_sync_alpha_graph_with_logging function")
        return True


def step4_fix_prior_threshold(conn):
    """Step 4: Fix prior update threshold to >= 30 with damping"""
    logger.info("Step 4: Fixing fn_auto_adjust_priors with >= 30 threshold and damping")

    with conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE FUNCTION fhq_learning.fn_auto_adjust_priors_v2(p_lambda numeric DEFAULT 0.5)
            RETURNS TABLE(run_id uuid, adjusted_count integer, status text) AS $$
            DECLARE
                v_run_id uuid;
                v_adjusted_count integer := 0;
                v_hypothesis RECORD;
                v_new_prior numeric;
                v_effective_lambda numeric;
                v_error_message text;
            BEGIN
                -- Start job run
                INSERT INTO fhq_monitoring.job_runs (job_name, started_at, status)
                VALUES ('prior_adjustment', NOW(), 'RUNNING')
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
                        WHERE ag.created_at > NOW() - INTERVAL '1 day'
                        AND hc.status IN ('ACTIVE', 'TIMEOUT_PENDING', 'SURVIVED')
                        GROUP BY hc.canon_id, hc.current_confidence, hc.initial_confidence
                        HAVING COUNT(*) >= 30  -- CEO-DIR-006: Minimum 30 samples
                    LOOP
                        -- Damping based on sample size (CEO-DIR-006 Section 5.2)
                        -- 30-99 samples: lambda * 0.5 (damped)
                        -- 100+ samples: lambda * 1.0 (normal)
                        IF v_hypothesis.sample_size < 100 THEN
                            v_effective_lambda := p_lambda * 0.5;  -- Damped
                        ELSE
                            v_effective_lambda := p_lambda;  -- Normal
                        END IF;

                        -- Calculate new prior: new_prior = old_prior * exp(-lambda * mean_brier)
                        v_new_prior := GREATEST(0.01, LEAST(0.99,
                            v_hypothesis.old_prior * EXP(-v_effective_lambda * v_hypothesis.mean_brier)
                        ));

                        -- Only update if meaningful change (> 1%)
                        IF ABS(v_new_prior - v_hypothesis.old_prior) > 0.01 THEN
                            -- Update hypothesis
                            UPDATE fhq_learning.hypothesis_canon
                            SET current_confidence = v_new_prior,
                                last_updated_at = NOW()
                            WHERE canon_id = v_hypothesis.canon_id;

                            -- Log to audit table (CEO-DIR-006 Section 5.3)
                            INSERT INTO fhq_learning.hypothesis_prior_updates (
                                hypothesis_id,
                                old_prior,
                                new_prior,
                                mean_brier,
                                sample_size,
                                lambda_used,
                                updated_by,
                                evidence_hash
                            ) VALUES (
                                v_hypothesis.canon_id,
                                v_hypothesis.old_prior,
                                v_new_prior,
                                v_hypothesis.mean_brier,
                                v_hypothesis.sample_size,
                                v_effective_lambda,
                                'fn_auto_adjust_priors_v2',
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
                            'damping_threshold', 100
                        )
                    WHERE job_runs.run_id = v_run_id;

                EXCEPTION WHEN OTHERS THEN
                    v_error_message := SQLERRM;
                    UPDATE fhq_monitoring.job_runs
                    SET finished_at = NOW(),
                        status = 'FAIL',
                        error_message = v_error_message
                    WHERE job_runs.run_id = v_run_id;

                    RETURN QUERY SELECT v_run_id, 0, 'FAIL'::text;
                    RETURN;
                END;

                RETURN QUERY SELECT v_run_id, v_adjusted_count, 'SUCCESS'::text;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        logger.info("  Created fn_auto_adjust_priors_v2 with >= 30 threshold and damping")
        return True


def step5_run_initial_syncs(conn):
    """Step 5: Run 3 initial syncs to establish baseline"""
    logger.info("Step 5: Running initial syncs")

    results = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Run sync 3 times
        for i in range(3):
            cur.execute("""
                SELECT * FROM fhq_learning.fn_sync_alpha_graph_with_logging(
                    NOW() - INTERVAL '2 hours'
                )
            """)
            result = cur.fetchone()
            conn.commit()
            results.append({
                'run': i + 1,
                'run_id': str(result['run_id']),
                'inserted_count': result['inserted_count'],
                'status': result['status']
            })
            logger.info(f"  Sync {i+1}: inserted={result['inserted_count']}, status={result['status']}")

    return results


def step6_run_prior_adjustment(conn):
    """Step 6: Run prior adjustment with new threshold"""
    logger.info("Step 6: Running prior adjustment with >= 30 threshold")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM fhq_learning.fn_auto_adjust_priors_v2(0.5)")
        result = cur.fetchone()
        conn.commit()
        logger.info(f"  Prior adjustment: adjusted={result['adjusted_count']}, status={result['status']}")
        return {
            'run_id': str(result['run_id']),
            'adjusted_count': result['adjusted_count'],
            'status': result['status']
        }


def step7_verify_and_report(conn):
    """Step 7: Generate verification report"""
    logger.info("Step 7: Generating verification report")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get last 10 job_runs for alpha_graph_sync
        cur.execute("""
            SELECT run_id, job_name, started_at, finished_at, status,
                   rows_inserted, rows_updated, error_message, evidence_hash
            FROM fhq_monitoring.job_runs
            WHERE job_name = 'alpha_graph_sync'
            ORDER BY started_at DESC
            LIMIT 10
        """)
        job_runs = [dict(r) for r in cur.fetchall()]

        # Get lag view output
        cur.execute("SELECT * FROM fhq_monitoring.v_alpha_graph_sync_lag")
        lag_view = dict(cur.fetchone()) if cur.rowcount > 0 else None

        # Check prior update threshold
        cur.execute("""
            SELECT
                pg_get_functiondef(oid) as func_def
            FROM pg_proc
            WHERE proname = 'fn_auto_adjust_priors_v2'
        """)
        func_result = cur.fetchone()
        threshold_verified = 'HAVING COUNT(*) >= 30' in func_result['func_def'] if func_result else False

        # Count SUCCESS runs
        cur.execute("""
            SELECT COUNT(*) as success_count
            FROM fhq_monitoring.job_runs
            WHERE job_name = 'alpha_graph_sync'
            AND status = 'SUCCESS'
        """)
        success_count = cur.fetchone()['success_count']

        return {
            'job_runs': job_runs,
            'lag_view': lag_view,
            'prior_threshold_verified': threshold_verified,
            'success_run_count': success_count
        }


def generate_evidence(results):
    """Generate evidence file"""
    evidence = {
        "directive_id": DIRECTIVE_ID,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "executed_by": "STIG",
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

    conn = get_connection()
    results = {}

    try:
        # Step 1: Create job_runs table
        step1_create_job_runs_table(conn)
        results['job_runs_table'] = True

        # Step 2: Create lag view
        step2_create_lag_view(conn)
        results['lag_view'] = True

        # Step 3: Update sync function with logging
        step3_update_sync_function_with_logging(conn)
        results['sync_function_updated'] = True

        # Step 4: Fix prior threshold
        step4_fix_prior_threshold(conn)
        results['prior_threshold_fixed'] = True

        # Step 5: Run initial syncs
        sync_results = step5_run_initial_syncs(conn)
        results['initial_syncs'] = sync_results

        # Step 6: Run prior adjustment
        prior_result = step6_run_prior_adjustment(conn)
        results['prior_adjustment'] = prior_result

        # Step 7: Verify and report
        verification = step7_verify_and_report(conn)
        results['verification'] = verification

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
