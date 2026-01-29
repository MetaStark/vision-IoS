#!/usr/bin/env python3
"""
ALPHA GRAPH PHASE 0 CLEANUP
============================
Cleans up zombie hunt_sessions and duplicate backtest results in fhq_alpha.

Operations:
  1. Mark 8,888 zombie hunt_sessions (ACTIVE, 0 hypotheses, NULL completed_at) as ABANDONED
  2. Flag duplicate VALIDATED backtest results as DATA_CONTAMINATION

Database operations:
  UPDATES: fhq_alpha.hunt_sessions (session_status ACTIVE -> ABANDONED)
  UPDATES: fhq_alpha.backtest_results (validation_outcome VALIDATED -> DATA_CONTAMINATION)
  READS:   Both tables for verification

Usage:
    python alpha_graph_phase0_cleanup.py              # Execute cleanup
    python alpha_graph_phase0_cleanup.py --check      # Dry run
    python alpha_graph_phase0_cleanup.py --verify     # Verify results

Author: STIG (CTO)
Date: 2026-01-29
Contract: EC-003_2026_PRODUCTION
Directive: CEO Alpha Graph Phase 0 Cleanup
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[PHASE0_CLEANUP] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('03_FUNCTIONS/alpha_graph_phase0_cleanup.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('phase0_cleanup')

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def cleanup_zombie_sessions(conn, dry_run=False):
    """Mark zombie hunt_sessions as ABANDONED.

    Zombie definition:
    - session_status = 'ACTIVE'
    - hypotheses_generated = 0 OR NULL
    - completed_at IS NULL
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Count zombies
        cur.execute("""
            SELECT COUNT(*) as zombie_count
            FROM fhq_alpha.hunt_sessions
            WHERE session_status = 'ACTIVE'
            AND (hypotheses_generated = 0 OR hypotheses_generated IS NULL)
            AND completed_at IS NULL
        """)
        zombie_count = cur.fetchone()['zombie_count']
        logger.info(f"Zombie hunt_sessions found: {zombie_count}")

        if zombie_count == 0:
            logger.info("No zombies to clean up")
            return {'zombies_found': 0, 'zombies_cleaned': 0}

        if dry_run:
            logger.info(f"DRY RUN: Would mark {zombie_count} sessions as ABANDONED")
            return {'zombies_found': zombie_count, 'zombies_cleaned': 0, 'dry_run': True}

        # Mark as ABANDONED
        cur.execute("""
            UPDATE fhq_alpha.hunt_sessions
            SET session_status = 'ABANDONED',
                completed_at = NOW(),
                session_metadata = COALESCE(session_metadata, '{}'::jsonb) ||
                    jsonb_build_object(
                        'abandoned_reason', 'PHASE0_CLEANUP: Zero hypotheses generated, stuck in ACTIVE',
                        'abandoned_at', NOW()::text,
                        'abandoned_by', 'STIG_PHASE0_CLEANUP'
                    )
            WHERE session_status = 'ACTIVE'
            AND (hypotheses_generated = 0 OR hypotheses_generated IS NULL)
            AND completed_at IS NULL
        """)
        cleaned = cur.rowcount
        conn.commit()
        logger.info(f"Marked {cleaned} zombie sessions as ABANDONED")

        # Verify
        cur.execute("""
            SELECT session_status, COUNT(*) as cnt
            FROM fhq_alpha.hunt_sessions
            GROUP BY session_status
            ORDER BY cnt DESC
        """)
        post_state = [dict(r) for r in cur.fetchall()]
        logger.info(f"Post-cleanup state: {post_state}")

        return {
            'zombies_found': zombie_count,
            'zombies_cleaned': cleaned,
            'post_state': post_state
        }


def cleanup_duplicate_backtests(conn, dry_run=False):
    """Flag duplicate VALIDATED backtest results as DATA_CONTAMINATION.

    Two backtests have identical metrics (win_rate, sharpe, return, p_value)
    despite different hypothesis titles. Keep the one with the later
    backtest_completed_at, flag the earlier one.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Find duplicates: same win_rate, sharpe_ratio, total_return_pct, p_value
        cur.execute("""
            SELECT result_id, proposal_id, win_rate, sharpe_ratio,
                   total_return_pct, p_value, backtest_completed_at
            FROM fhq_alpha.backtest_results
            WHERE validation_outcome = 'VALIDATED'
            ORDER BY backtest_completed_at ASC
        """)
        validated = cur.fetchall()

        if len(validated) < 2:
            logger.info("Fewer than 2 VALIDATED backtests, no duplicates possible")
            return {'duplicates_found': 0, 'duplicates_flagged': 0}

        # Group by (win_rate, sharpe_ratio, total_return_pct, p_value)
        seen = {}
        duplicates = []
        keeper = None
        for row in validated:
            key = (
                float(row['win_rate']),
                float(row['sharpe_ratio']),
                float(row['total_return_pct']),
                float(row['p_value'])
            )
            if key in seen:
                # This is a duplicate - flag this one (keep the later one)
                duplicates.append(row)
                logger.info(f"Duplicate found: {row['result_id']} "
                           f"(win_rate={row['win_rate']}, sharpe={row['sharpe_ratio']})")
            else:
                seen[key] = row

        if not duplicates:
            logger.info("No duplicate VALIDATED backtests found")
            return {'duplicates_found': 0, 'duplicates_flagged': 0}

        logger.info(f"Found {len(duplicates)} duplicate VALIDATED backtests")

        if dry_run:
            logger.info(f"DRY RUN: Would flag {len(duplicates)} as DATA_CONTAMINATION")
            return {
                'duplicates_found': len(duplicates),
                'duplicates_flagged': 0,
                'dry_run': True,
                'duplicate_ids': [str(d['result_id']) for d in duplicates]
            }

        # Flag duplicates
        dup_ids = [d['result_id'] for d in duplicates]
        for dup_id in dup_ids:
            cur.execute("""
                UPDATE fhq_alpha.backtest_results
                SET validation_outcome = 'DATA_CONTAMINATION',
                    rejection_reason = 'PHASE0_CLEANUP: Identical metrics to another VALIDATED backtest. '
                                      'Same win_rate, sharpe_ratio, total_return_pct, p_value. '
                                      'Flagged as data contamination artifact.'
                WHERE result_id = %s
            """, (dup_id,))
        conn.commit()
        logger.info(f"Flagged {len(dup_ids)} backtests as DATA_CONTAMINATION")

        # Verify
        cur.execute("""
            SELECT validation_outcome, COUNT(*) as cnt
            FROM fhq_alpha.backtest_results
            GROUP BY validation_outcome
            ORDER BY cnt DESC
        """)
        post_state = [dict(r) for r in cur.fetchall()]
        logger.info(f"Post-cleanup backtest state: {post_state}")

        return {
            'duplicates_found': len(duplicates),
            'duplicates_flagged': len(dup_ids),
            'flagged_ids': [str(d) for d in dup_ids],
            'post_state': post_state
        }


def verify_cleanup(conn):
    """Verify cleanup results."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Hunt sessions state
        cur.execute("""
            SELECT session_status, COUNT(*) as cnt
            FROM fhq_alpha.hunt_sessions
            GROUP BY session_status ORDER BY cnt DESC
        """)
        sessions = [dict(r) for r in cur.fetchall()]

        # Backtest state
        cur.execute("""
            SELECT validation_outcome, COUNT(*) as cnt
            FROM fhq_alpha.backtest_results
            GROUP BY validation_outcome ORDER BY cnt DESC
        """)
        backtests = [dict(r) for r in cur.fetchall()]

        # Remaining VALIDATED detail
        cur.execute("""
            SELECT br.result_id,
                   LEFT(gp.hypothesis_title, 50) as title,
                   br.win_rate, br.sharpe_ratio, br.total_return_pct, br.p_value
            FROM fhq_alpha.backtest_results br
            JOIN fhq_alpha.g0_draft_proposals gp ON br.proposal_id = gp.proposal_id
            WHERE br.validation_outcome = 'VALIDATED'
        """)
        remaining_valid = [dict(r) for r in cur.fetchall()]

        return {
            'hunt_sessions': sessions,
            'backtest_results': backtests,
            'remaining_validated': remaining_valid
        }


def run_phase0(dry_run=False, verify_only=False):
    """Main entry."""
    logger.info("=" * 60)
    logger.info("ALPHA GRAPH PHASE 0 CLEANUP")
    logger.info(f"  dry_run={dry_run}, verify_only={verify_only}")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        if verify_only:
            result = verify_cleanup(conn)
            print("\n=== PHASE 0 VERIFICATION ===\n")
            print("Hunt Sessions:")
            for s in result['hunt_sessions']:
                print(f"  {s['session_status']}: {s['cnt']}")
            print("\nBacktest Results:")
            for b in result['backtest_results']:
                print(f"  {b['validation_outcome']}: {b['cnt']}")
            print("\nRemaining VALIDATED backtests:")
            for v in result['remaining_validated']:
                print(f"  {v['title']}: Sharpe={v['sharpe_ratio']}, "
                      f"return={v['total_return_pct']}%, p={v['p_value']}")
            return

        # Step 1: Zombie sessions
        logger.info("--- STEP 1: Zombie Hunt Sessions ---")
        zombie_result = cleanup_zombie_sessions(conn, dry_run=dry_run)

        # Step 2: Duplicate backtests
        logger.info("--- STEP 2: Duplicate Backtests ---")
        backtest_result = cleanup_duplicate_backtests(conn, dry_run=dry_run)

        # Verification
        if not dry_run:
            logger.info("--- VERIFICATION ---")
            verify_result = verify_cleanup(conn)

            # Evidence
            evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
            os.makedirs(evidence_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence = {
                'executed_at': datetime.now(timezone.utc).isoformat(),
                'executed_by': 'STIG_PHASE0_CLEANUP',
                'directive': 'CEO Alpha Graph Phase 0 Cleanup',
                'operations': {
                    'zombie_sessions': zombie_result,
                    'duplicate_backtests': backtest_result
                },
                'verification': verify_result
            }
            evidence_path = os.path.join(evidence_dir,
                                         f'ALPHA_GRAPH_PHASE0_CLEANUP_{ts}.json')
            with open(evidence_path, 'w') as f:
                json.dump(evidence, f, indent=2, default=str)
            logger.info(f"Evidence: {evidence_path}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Alpha Graph Phase 0 Cleanup')
    parser.add_argument('--check', action='store_true', help='Dry run')
    parser.add_argument('--verify', action='store_true', help='Verify results')
    args = parser.parse_args()

    run_phase0(dry_run=args.check, verify_only=args.verify)


if __name__ == '__main__':
    main()
