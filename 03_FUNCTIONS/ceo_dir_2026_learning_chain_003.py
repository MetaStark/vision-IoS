#!/usr/bin/env python3
"""
CEO-DIR-2026-LEARNING-CHAIN-IMPLEMENTATION-003
===============================================

Implementerer den reelle læringskjeden:
outcome → alpha_graph → brier → prior → bedre beslutninger

Deliverables:
- T+48h: Alpha Graph ≥5000 noder, brier_contribution ≥1000 noder
- T+72h: lvi_timeseries med ≥2 datapunkter, prior-justering

Authority: CEO
Contract: EC-003_2026_PRODUCTION
"""

import os
import sys
import json
import math
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format='[CEO-DIR-003] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

DIRECTIVE_ID = 'CEO-DIR-2026-LEARNING-CHAIN-IMPLEMENTATION-003'


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def step1_implement_freeze_order(conn):
    """Step 1: Fryseordre - stopp hypotese-generering"""
    logger.info("Step 1: Implementing freeze order")

    with conn.cursor() as cur:
        # Use upsert pattern with explicit check
        for gate_id in ['HYPOTHESIS_GENERATION_FREEZE', 'EXPERIMENT_CREATION_FREEZE']:
            reason = json.dumps({'reason': f'{DIRECTIVE_ID}: Fryseordre aktiv.'})

            # Try update first
            cur.execute("""
                UPDATE fhq_meta.gate_status
                SET status = 'CLOSED',
                    validation_evidence = %s,
                    updated_at = NOW()
                WHERE gate_id = %s
            """, (reason, gate_id))

            # If no rows updated, insert
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO fhq_meta.gate_status (gate_id, status, validation_evidence, updated_at)
                    VALUES (%s, 'CLOSED', %s, NOW())
                """, (gate_id, reason))

        conn.commit()
        logger.info("  Freeze gates activated: HYPOTHESIS_GENERATION_FREEZE, EXPERIMENT_CREATION_FREEZE")


def step2_ensure_alpha_graph_schema(conn):
    """Step 2: Ensure Alpha Graph has correct schema with all required columns"""
    logger.info("Step 2: Ensuring Alpha Graph schema")

    with conn.cursor() as cur:
        # Add missing columns to alpha_graph_nodes
        columns_to_add = [
            ("experiment_id", "UUID"),
            ("trigger_type", "VARCHAR(100)"),
            ("regime", "VARCHAR(50)"),
            ("predicted_probability", "NUMERIC"),
            ("outcome_bool", "BOOLEAN"),
            ("brier_contribution", "NUMERIC"),
        ]

        for col_name, col_type in columns_to_add:
            try:
                cur.execute(f"""
                    ALTER TABLE fhq_learning.alpha_graph_nodes
                    ADD COLUMN IF NOT EXISTS {col_name} {col_type}
                """)
            except Exception as e:
                logger.warning(f"  Column {col_name} may already exist: {e}")

        conn.commit()
        logger.info("  Alpha Graph schema updated with all required columns")


def step3_create_lvi_timeseries(conn):
    """Step 3: Create LVI timeseries table"""
    logger.info("Step 3: Creating LVI timeseries table")

    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fhq_learning.lvi_timeseries (
                lvi_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                calculation_date DATE NOT NULL UNIQUE,
                global_brier NUMERIC NOT NULL,
                global_brier_previous NUMERIC,
                lvi_value NUMERIC,
                sample_size INTEGER NOT NULL,
                window_days INTEGER NOT NULL DEFAULT 7,
                notes TEXT,
                evidence_hash TEXT,
                created_by TEXT DEFAULT 'lvi_daemon'
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_lvi_date ON fhq_learning.lvi_timeseries(calculation_date)
        """)

        conn.commit()
        logger.info("  LVI timeseries table created")


def step4_migrate_outcomes_to_alpha_graph(conn):
    """Step 4: Migrate ALL outcomes to Alpha Graph nodes"""
    logger.info("Step 4: Migrating outcomes to Alpha Graph")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Get all outcomes with their experiment and hypothesis info
        cur.execute("""
            SELECT
                ol.outcome_id,
                ol.experiment_id,
                ol.trigger_event_id,
                ol.result_bool,
                ol.return_pct,
                ol.return_bps,
                ol.pnl_gross_simulated,
                ol.time_to_outcome,
                ol.mfe,
                ol.mae,
                ol.created_at,
                er.hypothesis_id,
                hc.current_confidence as predicted_probability,
                hc.hypothesis_code,
                te.asset_id,
                te.event_timestamp as trigger_timestamp
            FROM fhq_learning.outcome_ledger ol
            JOIN fhq_learning.experiment_registry er ON ol.experiment_id = er.experiment_id
            JOIN fhq_learning.hypothesis_canon hc ON er.hypothesis_id = hc.canon_id
            LEFT JOIN fhq_learning.trigger_events te ON ol.trigger_event_id = te.trigger_event_id
            WHERE NOT EXISTS (
                SELECT 1 FROM fhq_learning.alpha_graph_nodes agn
                WHERE agn.hypothesis_id = er.hypothesis_id
                AND agn.experiment_id = ol.experiment_id
                AND agn.created_at = ol.created_at
            )
        """)

        outcomes = cur.fetchall()
        logger.info(f"  Found {len(outcomes)} outcomes to migrate")

        migrated = 0
        for o in outcomes:
            # Calculate holding period
            holding_hours = None
            if o['time_to_outcome']:
                # time_to_outcome is an interval, extract hours
                total_seconds = o['time_to_outcome'].total_seconds() if hasattr(o['time_to_outcome'], 'total_seconds') else 0
                holding_hours = total_seconds / 3600

            # Calculate Brier contribution
            # brier = (predicted_probability - outcome)^2
            predicted_prob = float(o['predicted_probability']) if o['predicted_probability'] else 0.5
            outcome_val = 1.0 if o['result_bool'] else 0.0
            brier = (predicted_prob - outcome_val) ** 2

            # Determine node status
            node_status = 'COMPLETE'
            if holding_hours is None or o['return_pct'] is None:
                node_status = 'INCOMPLETE'

            # Create evidence hash
            evidence_str = f"{o['outcome_id']}:{o['experiment_id']}:{o['result_bool']}:{o['return_pct']}"
            evidence_hash = hashlib.sha256(evidence_str.encode()).hexdigest()[:32]

            # Insert node
            cur.execute("""
                INSERT INTO fhq_learning.alpha_graph_nodes (
                    hypothesis_id,
                    experiment_id,
                    trigger_type,
                    regime,
                    holding_period_hours,
                    realised_return,
                    survival_time_hours,
                    predicted_probability,
                    outcome_bool,
                    brier_contribution,
                    node_status,
                    created_at,
                    evidence_hash
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                o['hypothesis_id'],
                o['experiment_id'],
                o['asset_id'],  # Using asset_id as trigger_type for now
                None,  # regime - would need IoS-003 lookup
                holding_hours,
                float(o['return_pct']) if o['return_pct'] else None,
                holding_hours,  # survival_time = holding_period for completed trades
                predicted_prob,
                o['result_bool'],
                brier,
                node_status,
                o['created_at'],
                evidence_hash
            ))
            migrated += 1

            if migrated % 1000 == 0:
                conn.commit()
                logger.info(f"  Migrated {migrated} nodes...")

        conn.commit()
        logger.info(f"  Migration complete: {migrated} nodes created")
        return migrated


def step5_calculate_initial_lvi(conn):
    """Step 5: Calculate initial LVI data points"""
    logger.info("Step 5: Calculating initial LVI")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Calculate global Brier for today
        cur.execute("""
            SELECT
                AVG(brier_contribution) as global_brier,
                COUNT(*) as sample_size
            FROM fhq_learning.alpha_graph_nodes
            WHERE brier_contribution IS NOT NULL
        """)

        result = cur.fetchone()

        if result['sample_size'] and result['sample_size'] > 0:
            global_brier = float(result['global_brier'])
            sample_size = result['sample_size']

            # Check if we have a previous calculation
            cur.execute("""
                SELECT global_brier, calculation_date
                FROM fhq_learning.lvi_timeseries
                ORDER BY calculation_date DESC
                LIMIT 1
            """)
            prev = cur.fetchone()

            lvi_value = None
            prev_brier = None
            if prev:
                prev_brier = float(prev['global_brier'])
                # LVI = (Brier_{t-1} - Brier_t) / delta_t
                # Positive LVI = improving (Brier decreasing)
                days_diff = 1  # Assuming daily calculation
                lvi_value = (prev_brier - global_brier) / days_diff

            # Insert LVI record
            evidence_str = f"{datetime.now().date()}:{global_brier}:{sample_size}"
            evidence_hash = hashlib.sha256(evidence_str.encode()).hexdigest()[:32]

            cur.execute("""
                INSERT INTO fhq_learning.lvi_timeseries (
                    calculation_date,
                    global_brier,
                    global_brier_previous,
                    lvi_value,
                    sample_size,
                    window_days,
                    notes,
                    evidence_hash,
                    created_by
                ) VALUES (
                    CURRENT_DATE,
                    %s,
                    %s,
                    %s,
                    %s,
                    7,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (calculation_date) DO UPDATE SET
                    global_brier = EXCLUDED.global_brier,
                    lvi_value = EXCLUDED.lvi_value,
                    sample_size = EXCLUDED.sample_size,
                    calculated_at = NOW()
            """, (
                global_brier,
                prev_brier,
                lvi_value,
                sample_size,
                f'{DIRECTIVE_ID}: Initial LVI calculation',
                evidence_hash,
                DIRECTIVE_ID
            ))

            conn.commit()
            logger.info(f"  LVI calculated: global_brier={global_brier:.6f}, lvi={lvi_value}, n={sample_size}")
            return {'global_brier': global_brier, 'lvi': lvi_value, 'sample_size': sample_size}
        else:
            logger.warning("  No brier data available for LVI calculation")
            return None


def step6_implement_prior_adjustment(conn):
    """Step 6: Create prior adjustment mechanism"""
    logger.info("Step 6: Implementing prior adjustment mechanism")

    with conn.cursor() as cur:
        # Create prior adjustment log table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fhq_learning.prior_adjustment_log (
                adjustment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                hypothesis_id UUID NOT NULL,
                old_prior NUMERIC NOT NULL,
                new_prior NUMERIC NOT NULL,
                adjustment_reason TEXT,
                mean_brier NUMERIC,
                sample_size INTEGER,
                lambda_used NUMERIC,
                adjusted_at TIMESTAMPTZ DEFAULT NOW(),
                adjusted_by TEXT
            )
        """)

        # Create the adjustment function
        # Formula: new_prior = old_prior * exp(-lambda * mean_brier)
        # Lambda = 0.5 (initial setting, to be tuned by FINN)
        LAMBDA = 0.5

        # Get hypotheses with enough brier data
        cur.execute("""
            SELECT
                agn.hypothesis_id,
                hc.current_confidence as old_prior,
                AVG(agn.brier_contribution) as mean_brier,
                COUNT(*) as sample_size
            FROM fhq_learning.alpha_graph_nodes agn
            JOIN fhq_learning.hypothesis_canon hc ON agn.hypothesis_id = hc.canon_id
            WHERE agn.brier_contribution IS NOT NULL
            GROUP BY agn.hypothesis_id, hc.current_confidence
            HAVING COUNT(*) >= 5
        """)

        hypotheses = cur.fetchall()
        adjusted = 0

        for h in hypotheses:
            hypothesis_id, old_prior, mean_brier, sample_size = h
            old_prior = float(old_prior) if old_prior else 0.5
            mean_brier = float(mean_brier)

            # Calculate new prior
            # new_prior = old_prior * exp(-lambda * mean_brier)
            new_prior = old_prior * math.exp(-LAMBDA * mean_brier)

            # Clamp to [0.01, 0.99]
            new_prior = max(0.01, min(0.99, new_prior))

            # Only adjust if meaningful change (>1%)
            if abs(new_prior - old_prior) > 0.01:
                # Update hypothesis
                cur.execute("""
                    UPDATE fhq_learning.hypothesis_canon
                    SET current_confidence = %s,
                        last_updated_at = NOW(),
                        last_updated_by = %s
                    WHERE canon_id = %s
                """, (new_prior, DIRECTIVE_ID, hypothesis_id))

                # Log adjustment
                cur.execute("""
                    INSERT INTO fhq_learning.prior_adjustment_log (
                        hypothesis_id, old_prior, new_prior,
                        adjustment_reason, mean_brier, sample_size,
                        lambda_used, adjusted_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    hypothesis_id, old_prior, new_prior,
                    'Brier-based prior adjustment per CEO-DIR-003',
                    mean_brier, sample_size, LAMBDA, DIRECTIVE_ID
                ))

                adjusted += 1

        conn.commit()
        logger.info(f"  Prior adjustment complete: {adjusted} hypotheses adjusted (lambda={LAMBDA})")
        return adjusted


def step7_generate_status_report(conn):
    """Step 7: Generate honest status report"""
    logger.info("Step 7: Generating status report")

    report = {
        'directive': DIRECTIVE_ID,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'layers': {
            'infrastructure': {},
            'activity': {},
            'learning': {}
        }
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Infrastructure layer
        cur.execute("SELECT COUNT(*) as count FROM fhq_learning.alpha_graph_nodes")
        report['layers']['infrastructure']['alpha_graph_nodes'] = cur.fetchone()['count']

        cur.execute("SELECT COUNT(*) as count FROM fhq_learning.lvi_timeseries")
        report['layers']['infrastructure']['lvi_records'] = cur.fetchone()['count']

        cur.execute("SELECT COUNT(*) as count FROM fhq_learning.prior_adjustment_log")
        report['layers']['infrastructure']['prior_adjustments'] = cur.fetchone()['count']

        # Activity layer
        cur.execute("SELECT COUNT(*) as count FROM fhq_learning.outcome_ledger")
        report['layers']['activity']['total_outcomes'] = cur.fetchone()['count']

        cur.execute("""
            SELECT COUNT(*) as count FROM fhq_learning.outcome_ledger
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """)
        report['layers']['activity']['outcomes_24h'] = cur.fetchone()['count']

        # Learning layer
        cur.execute("""
            SELECT
                AVG(brier_contribution) as global_brier,
                COUNT(*) as nodes_with_brier
            FROM fhq_learning.alpha_graph_nodes
            WHERE brier_contribution IS NOT NULL
        """)
        brier_stats = cur.fetchone()
        report['layers']['learning']['global_brier'] = float(brier_stats['global_brier']) if brier_stats['global_brier'] else None
        report['layers']['learning']['nodes_with_brier'] = brier_stats['nodes_with_brier']

        cur.execute("""
            SELECT lvi_value, global_brier, sample_size
            FROM fhq_learning.lvi_timeseries
            ORDER BY calculation_date DESC
            LIMIT 1
        """)
        lvi_latest = cur.fetchone()
        if lvi_latest:
            report['layers']['learning']['latest_lvi'] = float(lvi_latest['lvi_value']) if lvi_latest['lvi_value'] else None
        else:
            report['layers']['learning']['latest_lvi'] = None

        # Deflated Sharpe coverage
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE deflated_sharpe_estimate IS NOT NULL) as with_sharpe,
                COUNT(*) as total
            FROM fhq_learning.hypothesis_canon
        """)
        sharpe_stats = cur.fetchone()
        report['layers']['learning']['deflated_sharpe_coverage_pct'] = round(
            100.0 * sharpe_stats['with_sharpe'] / sharpe_stats['total'], 2
        ) if sharpe_stats['total'] > 0 else 0

    return report


def main():
    logger.info("=" * 70)
    logger.info(f"EXECUTING: {DIRECTIVE_ID}")
    logger.info("=" * 70)

    conn = get_connection()
    results = {}

    try:
        # Step 1: Freeze order
        step1_implement_freeze_order(conn)
        results['freeze_order'] = 'ACTIVE'

        # Step 2: Alpha Graph schema
        step2_ensure_alpha_graph_schema(conn)
        results['alpha_graph_schema'] = 'UPDATED'

        # Step 3: LVI timeseries table
        step3_create_lvi_timeseries(conn)
        results['lvi_timeseries'] = 'CREATED'

        # Step 4: Migrate outcomes to Alpha Graph
        migrated = step4_migrate_outcomes_to_alpha_graph(conn)
        results['alpha_graph_nodes_created'] = migrated

        # Step 5: Calculate initial LVI
        lvi_result = step5_calculate_initial_lvi(conn)
        results['lvi_calculation'] = lvi_result

        # Step 6: Prior adjustment
        adjusted = step6_implement_prior_adjustment(conn)
        results['priors_adjusted'] = adjusted

        # Step 7: Status report
        report = step7_generate_status_report(conn)
        results['status_report'] = report

        # Write evidence file
        evidence_path = f"03_FUNCTIONS/evidence/{DIRECTIVE_ID.replace('-', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(evidence_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info("=" * 70)
        logger.info("DIRECTIVE EXECUTION COMPLETE")
        logger.info("=" * 70)

        print(json.dumps(results, indent=2, default=str))

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
