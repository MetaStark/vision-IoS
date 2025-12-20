#!/usr/bin/env python3
"""
G4 Validation Runner - 7-Year Backtest Windows
CEO Directive: Extended lookback for multi-regime validation

This script:
1. Resets all G4 validation queue entries to PENDING
2. Runs G4 validation on all 122 golden needles with 7-year windows
3. Reports classification distribution
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def reset_validation_queue(conn):
    """Reset all needles in queue to PENDING for re-validation."""
    print("\n=== RESETTING G4 VALIDATION QUEUE ===")

    with conn.cursor() as cur:
        # First, ensure all golden needles are in the queue
        cur.execute("""
            INSERT INTO fhq_canonical.g4_validation_queue (needle_id, priority, refinery_status, physics_status)
            SELECT needle_id, 1, 'PENDING', 'PENDING'
            FROM fhq_canonical.golden_needles
            WHERE is_current = true
            AND needle_id NOT IN (SELECT needle_id FROM fhq_canonical.g4_validation_queue)
        """)
        added = cur.rowcount
        print(f"  Added {added} new needles to queue")

        # Reset all to PENDING
        cur.execute("""
            UPDATE fhq_canonical.g4_validation_queue
            SET refinery_status = 'PENDING',
                physics_status = 'PENDING',
                refinery_started_at = NULL,
                refinery_completed_at = NULL,
                physics_started_at = NULL,
                physics_completed_at = NULL,
                refinery_error = NULL,
                physics_error = NULL,
                worker_id = NULL
        """)
        reset_count = cur.rowcount
        print(f"  Reset {reset_count} needles to PENDING")

        # Clear previous results
        cur.execute("DELETE FROM fhq_canonical.g4_refinery_results")
        ref_deleted = cur.rowcount
        cur.execute("DELETE FROM fhq_canonical.g4_physics_results")
        phys_deleted = cur.rowcount
        cur.execute("DELETE FROM fhq_canonical.g4_composite_scorecard")
        score_deleted = cur.rowcount

        print(f"  Cleared {ref_deleted} refinery results")
        print(f"  Cleared {phys_deleted} physics results")
        print(f"  Cleared {score_deleted} scorecards")

        conn.commit()

    return reset_count

def run_validation():
    """Run G4 validation engine on all pending needles."""
    print("\n=== RUNNING G4 VALIDATION (7-YEAR WINDOWS) ===")

    # Import the validation engine
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from g4_validation_engine import G4ValidationEngine

    engine = G4ValidationEngine()

    # Get count of pending
    with engine.conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM fhq_canonical.g4_validation_queue
            WHERE refinery_status = 'PENDING'
        """)
        total = cur.fetchone()[0]

    print(f"  Total needles to validate: {total}")
    print(f"  Backtest window: 7 years")
    print(f"  Started at: {datetime.now().isoformat()}")
    print()

    validated = 0
    errors = 0
    batch_size = 10

    while True:
        # Get next batch and run validation
        results = engine.run_validation_batch(batch_size)
        if not results:
            break

        for r in results:
            validated += 1
            classification = r.get('classification', 'UNKNOWN')

            status_char = {
                'PLATINUM': '[P]',
                'GOLD': '[G]',
                'SILVER': '[S]',
                'BRONZE': '[B]',
                'REJECT': '[R]'
            }.get(classification, '[?]')

            title = r.get('title', 'Unknown')[:45]
            eqs = r.get('eqs', 0)

            print(f"  {validated:3d}/{total} {status_char} EQS={eqs:.2f} | {title}")

    print(f"\n  Completed at: {datetime.now().isoformat()}")
    print(f"  Validated: {validated}")

    return validated

def get_classification_report(conn):
    """Generate classification distribution report."""
    print("\n=== G4 CLASSIFICATION REPORT (7-YEAR BACKTEST) ===")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Overall distribution
        cur.execute("""
            SELECT
                classification,
                COUNT(*) as count,
                ROUND(AVG(oos_sharpe)::numeric, 4) as avg_sharpe,
                ROUND(MIN(oos_sharpe)::numeric, 4) as min_sharpe,
                ROUND(MAX(oos_sharpe)::numeric, 4) as max_sharpe
            FROM fhq_canonical.g4_composite_scorecard
            GROUP BY classification
            ORDER BY
                CASE classification
                    WHEN 'PLATINUM' THEN 1
                    WHEN 'GOLD' THEN 2
                    WHEN 'SILVER' THEN 3
                    WHEN 'BRONZE' THEN 4
                    WHEN 'REJECT' THEN 5
                END
        """)
        results = cur.fetchall()

        print("\n  CLASSIFICATION | COUNT | AVG SHARPE | MIN     | MAX")
        print("  " + "-" * 60)

        total = 0
        for r in results:
            total += r['count']
            print(f"  {r['classification']:13s} | {r['count']:5d} | {r['avg_sharpe']:10.4f} | {r['min_sharpe']:7.4f} | {r['max_sharpe']:7.4f}")

        print("  " + "-" * 60)
        print(f"  {'TOTAL':13s} | {total:5d}")

        # By category
        cur.execute("""
            SELECT
                hypothesis_category,
                classification,
                COUNT(*) as count,
                ROUND(AVG(oos_sharpe)::numeric, 4) as avg_sharpe
            FROM fhq_canonical.g4_composite_scorecard
            GROUP BY hypothesis_category, classification
            ORDER BY hypothesis_category,
                CASE classification
                    WHEN 'PLATINUM' THEN 1
                    WHEN 'GOLD' THEN 2
                    WHEN 'SILVER' THEN 3
                    WHEN 'BRONZE' THEN 4
                    WHEN 'REJECT' THEN 5
                END
        """)
        by_cat = cur.fetchall()

        print("\n  BY CATEGORY:")
        print("  " + "-" * 60)

        current_cat = None
        for r in by_cat:
            if r['hypothesis_category'] != current_cat:
                current_cat = r['hypothesis_category']
                print(f"\n  {current_cat}:")
            print(f"    {r['classification']:10s}: {r['count']:3d} (avg Sharpe: {r['avg_sharpe']:7.4f})")

        # G5 eligible count
        cur.execute("""
            SELECT COUNT(*) FROM fhq_canonical.g4_composite_scorecard
            WHERE classification IN ('PLATINUM', 'GOLD')
            AND eligible_for_g5 = true
        """)
        g5_eligible = cur.fetchone()[0]

        print(f"\n  G5 ELIGIBLE: {g5_eligible}")

    return results

def main():
    print("=" * 70)
    print("G4 VALIDATION - 7-YEAR BACKTEST WINDOWS")
    print("CEO Directive: Extended lookback for multi-regime validation")
    print("=" * 70)

    conn = get_connection()

    try:
        # Step 1: Reset queue
        reset_count = reset_validation_queue(conn)
        conn.close()

        # Step 2: Run validation (uses its own connection)
        validated = run_validation()

        # Step 3: Report (new connection)
        conn = get_connection()
        get_classification_report(conn)

        print("\n" + "=" * 70)
        print("G4 VALIDATION COMPLETE")
        print("=" * 70)

    finally:
        if conn and not conn.closed:
            conn.close()

if __name__ == "__main__":
    main()
