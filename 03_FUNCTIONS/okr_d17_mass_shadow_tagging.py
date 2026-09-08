"""
OKR-2026-D17-001: Mass Shadow Tagging Execution
KR1: Execute 10,000+ shadow tagging checks

This script runs shadow tagging on all forecasts in the database to:
1. Prove determinism at scale
2. Accumulate evidence for court-defensibility
3. Prepare for G4 promotion

Author: UMA (via STIG)
Date: 2026-01-17
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': os.environ.get('PGPORT', '54322'),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

# Shadow mode session
SHADOW_SESSION_ID = '9c495eb2-9bb1-46f0-acd5-3a73b233e2ed'


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_active_shadow_session(conn) -> dict:
    """Get the active shadow mode session."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT session_id, session_name, status, started_at, planned_end_at
            FROM fhq_calendar.shadow_mode_sessions
            WHERE status = 'ACTIVE'
            ORDER BY started_at DESC LIMIT 1
        """)
        return cur.fetchone()


def get_forecasts_for_tagging(conn, limit: int = 1000, offset: int = 0) -> List[dict]:
    """Get forecasts to run shadow tagging on."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                forecast_id,
                forecast_domain as asset_id,
                forecast_made_at as forecast_timestamp
            FROM fhq_research.forecast_ledger
            WHERE forecast_made_at >= '2026-01-01'
            ORDER BY forecast_made_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return cur.fetchall()


def run_shadow_tagging(conn, session_id: str, asset_id: str,
                       forecast_timestamp: datetime, forecast_id: str) -> dict:
    """Run shadow tagging for a single forecast."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        try:
            cur.execute("""
                SELECT * FROM fhq_calendar.run_shadow_tagging(%s, %s, %s, %s)
            """, (session_id, asset_id, forecast_timestamp, forecast_id))
            result = cur.fetchone()
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            return {'error': str(e), 'asset_id': asset_id}


def get_shadow_stats(conn) -> dict:
    """Get current shadow tagging statistics."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_checks,
                COUNT(*) FILTER (WHERE matches_previous = true) as matches,
                COUNT(*) FILTER (WHERE matches_previous = false) as mismatches,
                COUNT(*) FILTER (WHERE drift_detected = true) as drift_count,
                COUNT(DISTINCT asset_id) as unique_assets
            FROM fhq_calendar.shadow_tagging_results
        """)
        return cur.fetchone()


def update_okr_progress(conn, kr_id: str, value: int) -> None:
    """Update OKR key result progress."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fhq_governance.update_key_result(%s, %s, 'UMA')
        """, (kr_id, value))
        conn.commit()


def main():
    """Execute mass shadow tagging."""
    print("=" * 70)
    print("OKR-2026-D17-001: Mass Shadow Tagging Execution")
    print("KR1: Execute 10,000+ shadow tagging checks")
    print("=" * 70)

    conn = get_connection()

    # Verify shadow session
    session = get_active_shadow_session(conn)
    if not session:
        logger.error("No active shadow mode session found!")
        return

    logger.info(f"Shadow Session: {session['session_name']}")
    logger.info(f"Session ID: {session['session_id']}")

    # Get initial stats
    initial_stats = get_shadow_stats(conn)
    logger.info(f"Initial checks: {initial_stats['total_checks']}")

    # Process forecasts in batches
    batch_size = 500
    total_processed = 0
    total_errors = 0
    max_forecasts = 12000  # Slightly over 10k target

    for offset in range(0, max_forecasts, batch_size):
        forecasts = get_forecasts_for_tagging(conn, batch_size, offset)

        if not forecasts:
            logger.info("No more forecasts to process")
            break

        batch_success = 0
        batch_errors = 0

        for f in forecasts:
            result = run_shadow_tagging(
                conn,
                str(session['session_id']),
                f['asset_id'],
                f['forecast_timestamp'],
                str(f['forecast_id'])
            )

            if result and 'error' not in result:
                batch_success += 1
            else:
                batch_errors += 1

        total_processed += batch_success
        total_errors += batch_errors

        # Progress update
        current_stats = get_shadow_stats(conn)
        logger.info(
            f"Batch {offset//batch_size + 1}: "
            f"+{batch_success} checks, "
            f"Total: {current_stats['total_checks']}, "
            f"Drift: {current_stats['drift_count']}"
        )

        # Check for drift - STOP if detected
        if current_stats['drift_count'] > 0:
            logger.error("DRIFT DETECTED! Stopping execution.")
            break

        # Check if we've hit target
        if int(current_stats['total_checks']) >= 10000:
            logger.info("TARGET REACHED: 10,000+ checks!")
            break

    # Final stats
    final_stats = get_shadow_stats(conn)

    print("\n" + "=" * 70)
    print("EXECUTION COMPLETE")
    print("=" * 70)
    print(f"Total Checks: {final_stats['total_checks']}")
    print(f"Matches: {final_stats['matches']}")
    print(f"Mismatches: {final_stats['mismatches']}")
    print(f"Drift Detected: {final_stats['drift_count']}")
    print(f"Unique Assets: {final_stats['unique_assets']}")
    print(f"Errors: {total_errors}")

    # Determine status
    if int(final_stats['drift_count']) > 0:
        print("\nSTATUS: FAILED - Drift detected!")
    elif int(final_stats['total_checks']) >= 10000:
        print("\nSTATUS: SUCCESS - KR1 target achieved!")
    else:
        print(f"\nSTATUS: IN_PROGRESS - {final_stats['total_checks']}/10000")

    # Save evidence
    evidence = {
        'okr_code': 'OKR-2026-D17-001',
        'key_result': 'KR1',
        'execution_timestamp': datetime.now(timezone.utc).isoformat(),
        'session_id': str(session['session_id']),
        'initial_checks': int(initial_stats['total_checks']),
        'final_checks': int(final_stats['total_checks']),
        'drift_detected': int(final_stats['drift_count']) > 0,
        'drift_count': int(final_stats['drift_count']),
        'unique_assets': int(final_stats['unique_assets']),
        'errors': total_errors,
        'target_achieved': int(final_stats['total_checks']) >= 10000
    }

    evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
    os.makedirs(evidence_dir, exist_ok=True)

    evidence_file = os.path.join(
        evidence_dir,
        f"OKR_D17_KR1_SHADOW_TAGGING_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2)

    print(f"\nEvidence saved: {evidence_file}")

    conn.close()


if __name__ == '__main__':
    main()
