#!/usr/bin/env python3
"""
CEO-DIR-2026-ALPHA-GRAPH-AUTOSYNC-REPAIR-005
=============================================

Repair script for Alpha Graph autosync.

Fixes:
1. Add trigger_event_id column to alpha_graph_nodes
2. Create fn_sync_alpha_graph() function
3. Create hypothesis_prior_updates audit table
4. Backfill missing outcomes
5. Register daemon for continuous sync

Authority: CEO
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[CEO-DIR-005] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DIRECTIVE_ID = 'CEO-DIR-2026-ALPHA-GRAPH-AUTOSYNC-REPAIR-005'
WINDOW_START = '2026-02-09 20:01:00+01'


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def step1_add_trigger_event_id_column(conn):
    """Step 1: Add trigger_event_id column to alpha_graph_nodes for 1:1 linking"""
    logger.info("Step 1: Adding trigger_event_id column to alpha_graph_nodes")

    with conn.cursor() as cur:
        # Check if column exists
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'fhq_learning'
            AND table_name = 'alpha_graph_nodes'
            AND column_name = 'trigger_event_id'
        """)
        if cur.fetchone():
            logger.info("  Column trigger_event_id already exists")
            return True

        # Add column
        cur.execute("""
            ALTER TABLE fhq_learning.alpha_graph_nodes
            ADD COLUMN trigger_event_id UUID
        """)

        # Add unique constraint for idempotent inserts
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_alpha_graph_trigger_event
            ON fhq_learning.alpha_graph_nodes(trigger_event_id)
            WHERE trigger_event_id IS NOT NULL
        """)

        conn.commit()
        logger.info("  Added trigger_event_id column with unique index")
        return True


def step2_create_sync_function(conn):
    """Step 2: Create deterministic sync function"""
    logger.info("Step 2: Creating fn_sync_alpha_graph function")

    with conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE FUNCTION fhq_learning.fn_sync_alpha_graph(p_since timestamptz)
            RETURNS TABLE(inserted_count integer, synced_outcomes uuid[]) AS $$
            DECLARE
                v_inserted_count integer;
                v_synced_ids uuid[];
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
                SELECT COUNT(*)::integer, ARRAY_AGG(trigger_event_id)
                INTO v_inserted_count, v_synced_ids
                FROM inserted;

                RETURN QUERY SELECT v_inserted_count, v_synced_ids;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        logger.info("  Created fn_sync_alpha_graph function")

        # Get function hash for evidence
        cur.execute("""
            SELECT md5(prosrc) as func_hash
            FROM pg_proc
            WHERE proname = 'fn_sync_alpha_graph'
        """)
        result = cur.fetchone()
        func_hash = result[0] if result else 'unknown'
        logger.info(f"  Function hash: {func_hash}")
        return func_hash


def step3_create_prior_updates_table(conn):
    """Step 3: Create hypothesis_prior_updates audit table"""
    logger.info("Step 3: Creating hypothesis_prior_updates audit table")

    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'fhq_learning'
                AND table_name = 'hypothesis_prior_updates'
            )
        """)
        if cur.fetchone()[0]:
            logger.info("  Table hypothesis_prior_updates already exists")
            return True

        cur.execute("""
            CREATE TABLE fhq_learning.hypothesis_prior_updates (
                update_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                hypothesis_id UUID NOT NULL REFERENCES fhq_learning.hypothesis_canon(canon_id),
                old_prior NUMERIC NOT NULL,
                new_prior NUMERIC NOT NULL,
                prior_delta NUMERIC GENERATED ALWAYS AS (new_prior - old_prior) STORED,
                mean_brier NUMERIC,
                sample_size INTEGER,
                lambda_used NUMERIC DEFAULT 0.5,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                updated_by TEXT NOT NULL,
                evidence_hash TEXT,
                CONSTRAINT chk_prior_range CHECK (new_prior >= 0 AND new_prior <= 1)
            )
        """)

        cur.execute("""
            CREATE INDEX idx_prior_updates_hypothesis ON fhq_learning.hypothesis_prior_updates(hypothesis_id);
            CREATE INDEX idx_prior_updates_time ON fhq_learning.hypothesis_prior_updates(updated_at);
        """)

        conn.commit()
        logger.info("  Created hypothesis_prior_updates table")
        return True


def step4_create_auto_prior_function(conn):
    """Step 4: Create function for automatic prior adjustment with audit"""
    logger.info("Step 4: Creating fn_auto_adjust_priors function")

    with conn.cursor() as cur:
        cur.execute("""
            CREATE OR REPLACE FUNCTION fhq_learning.fn_auto_adjust_priors(p_lambda numeric DEFAULT 0.5)
            RETURNS TABLE(adjusted_count integer) AS $$
            DECLARE
                v_adjusted_count integer := 0;
                v_hypothesis RECORD;
                v_new_prior numeric;
                v_mean_brier numeric;
                v_sample_size integer;
            BEGIN
                -- Find hypotheses with new alpha graph nodes that need prior adjustment
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
                    GROUP BY hc.canon_id, COALESCE(hc.current_confidence, hc.initial_confidence, 0.5)
                    HAVING COUNT(*) >= 5  -- Minimum sample size
                LOOP
                    -- Calculate new prior: new_prior = old_prior * exp(-lambda * mean_brier)
                    v_new_prior := GREATEST(0.01, LEAST(0.99,
                        v_hypothesis.old_prior * EXP(-p_lambda * v_hypothesis.mean_brier)
                    ));

                    -- Only update if meaningful change (> 1%)
                    IF ABS(v_new_prior - v_hypothesis.old_prior) > 0.01 THEN
                        -- Update hypothesis
                        UPDATE fhq_learning.hypothesis_canon
                        SET current_confidence = v_new_prior,
                            last_updated_at = NOW()
                        WHERE canon_id = v_hypothesis.canon_id;

                        -- Log to audit table
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
                            p_lambda,
                            'fn_auto_adjust_priors',
                            md5(v_hypothesis.canon_id::text || v_new_prior::text || NOW()::text)
                        );

                        v_adjusted_count := v_adjusted_count + 1;
                    END IF;
                END LOOP;

                RETURN QUERY SELECT v_adjusted_count;
            END;
            $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        logger.info("  Created fn_auto_adjust_priors function")
        return True


def step5_register_daemon(conn):
    """Step 5: Register alpha_graph_sync daemon in daemon_health"""
    logger.info("Step 5: Registering alpha_graph_sync daemon")

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_monitoring.daemon_health (
                daemon_name,
                status,
                last_heartbeat,
                metadata
            ) VALUES (
                'alpha_graph_sync',
                'HEALTHY',
                NOW(),
                jsonb_build_object(
                    'directive', %s,
                    'sync_interval_minutes', 5,
                    'last_sync_count', 0,
                    'window_start', %s
                )
            )
            ON CONFLICT (daemon_name) DO UPDATE SET
                status = 'HEALTHY',
                last_heartbeat = NOW(),
                metadata = jsonb_build_object(
                    'directive', %s,
                    'sync_interval_minutes', 5,
                    'last_sync_count', 0,
                    'window_start', %s
                )
        """, (DIRECTIVE_ID, WINDOW_START, DIRECTIVE_ID, WINDOW_START))
        conn.commit()
        logger.info("  Registered alpha_graph_sync daemon")
        return True


def step6_backfill_missing(conn):
    """Step 6: Backfill all missing outcomes since window start"""
    logger.info("Step 6: Backfilling missing outcomes")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Count before
        cur.execute("""
            SELECT COUNT(*) as count
            FROM fhq_learning.outcome_ledger ol
            LEFT JOIN fhq_learning.alpha_graph_nodes ag ON ag.trigger_event_id = ol.trigger_event_id
            WHERE ol.created_at > %s
            AND ag.trigger_event_id IS NULL
        """, (WINDOW_START,))
        before_count = cur.fetchone()['count']
        logger.info(f"  Missing outcomes before sync: {before_count}")

        # Run sync function
        cur.execute("SELECT * FROM fhq_learning.fn_sync_alpha_graph(%s)", (WINDOW_START,))
        result = cur.fetchone()
        inserted_count = result['inserted_count'] if result else 0
        conn.commit()
        logger.info(f"  Inserted {inserted_count} new alpha graph nodes")

        # Count after
        cur.execute("""
            SELECT COUNT(*) as count
            FROM fhq_learning.outcome_ledger ol
            LEFT JOIN fhq_learning.alpha_graph_nodes ag ON ag.trigger_event_id = ol.trigger_event_id
            WHERE ol.created_at > %s
            AND ag.trigger_event_id IS NULL
        """, (WINDOW_START,))
        after_count = cur.fetchone()['count']
        logger.info(f"  Missing outcomes after sync: {after_count}")

        # Update daemon metadata
        cur.execute("""
            UPDATE fhq_monitoring.daemon_health
            SET metadata = metadata || jsonb_build_object('last_sync_count', %s, 'last_sync_at', NOW()::text),
                last_heartbeat = NOW()
            WHERE daemon_name = 'alpha_graph_sync'
        """, (inserted_count,))
        conn.commit()

        return {
            'before': before_count,
            'inserted': inserted_count,
            'after': after_count
        }


def step7_run_prior_adjustment(conn):
    """Step 7: Run automatic prior adjustment"""
    logger.info("Step 7: Running automatic prior adjustment")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM fhq_learning.fn_auto_adjust_priors(0.5)")
        result = cur.fetchone()
        adjusted = result['adjusted_count'] if result else 0
        conn.commit()
        logger.info(f"  Adjusted {adjusted} hypothesis priors")

        # Get audit trail
        cur.execute("""
            SELECT hypothesis_id, old_prior, new_prior, prior_delta, mean_brier, sample_size
            FROM fhq_learning.hypothesis_prior_updates
            WHERE updated_at > NOW() - INTERVAL '5 minutes'
            ORDER BY updated_at DESC
            LIMIT 10
        """)
        recent_updates = cur.fetchall()

        return {
            'adjusted_count': adjusted,
            'recent_updates': [dict(r) for r in recent_updates]
        }


def step8_verify(conn):
    """Step 8: Triple verification"""
    logger.info("Step 8: Running triple verification")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # V5.2 - Missing should be 0
        cur.execute("""
            SELECT COUNT(*) AS outcomes_missing_graph
            FROM fhq_learning.outcome_ledger ol
            LEFT JOIN fhq_learning.alpha_graph_nodes ag
              ON ag.trigger_event_id = ol.trigger_event_id
            WHERE ol.created_at > %s
              AND ag.trigger_event_id IS NULL
        """, (WINDOW_START,))
        missing = cur.fetchone()['outcomes_missing_graph']
        logger.info(f"  V5.2 outcomes_missing_graph = {missing}")

        # New nodes count
        cur.execute("""
            SELECT COUNT(*) as new_nodes
            FROM fhq_learning.alpha_graph_nodes
            WHERE created_at > %s
        """, (WINDOW_START,))
        new_nodes = cur.fetchone()['new_nodes']
        logger.info(f"  New alpha graph nodes = {new_nodes}")

        # Prior updates audit
        cur.execute("""
            SELECT COUNT(*) as prior_updates
            FROM fhq_learning.hypothesis_prior_updates
            WHERE updated_at > %s
        """, (WINDOW_START,))
        prior_updates = cur.fetchone()['prior_updates']
        logger.info(f"  Prior updates logged = {prior_updates}")

        # Daemon heartbeat
        cur.execute("""
            SELECT daemon_name, status, last_heartbeat, metadata
            FROM fhq_monitoring.daemon_health
            WHERE daemon_name = 'alpha_graph_sync'
        """)
        daemon = cur.fetchone()
        logger.info(f"  Daemon status = {daemon['status'] if daemon else 'NOT FOUND'}")

        return {
            'outcomes_missing_graph': missing,
            'new_alpha_nodes': new_nodes,
            'prior_updates_logged': prior_updates,
            'daemon_status': dict(daemon) if daemon else None,
            'v5_2_pass': missing == 0,
            'autosync_registered': daemon is not None
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
        # Step 1: Add trigger_event_id column
        step1_add_trigger_event_id_column(conn)
        results['schema_updated'] = True

        # Step 2: Create sync function
        func_hash = step2_create_sync_function(conn)
        results['sync_function_hash'] = func_hash

        # Step 3: Create prior updates audit table
        step3_create_prior_updates_table(conn)
        results['prior_audit_table'] = True

        # Step 4: Create auto prior function
        step4_create_auto_prior_function(conn)
        results['prior_function'] = True

        # Step 5: Register daemon
        step5_register_daemon(conn)
        results['daemon_registered'] = True

        # Step 6: Backfill
        backfill_result = step6_backfill_missing(conn)
        results['backfill'] = backfill_result

        # Step 7: Run prior adjustment
        prior_result = step7_run_prior_adjustment(conn)
        results['prior_adjustment'] = prior_result

        # Step 8: Verify
        verify_result = step8_verify(conn)
        results['verification'] = verify_result

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
