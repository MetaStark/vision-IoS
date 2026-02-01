#!/usr/bin/env python3
"""
Epistemic Proposal Daemon
=========================
Generates improvement proposals at configurable intervals.

KEY PRINCIPLE: System PROPOSES, humans APPROVE.
All proposals require explicit VEGA/human approval before implementation.

Schedule: Weekly (Sunday 00:00 UTC) by default, configurable via database.

Usage:
    python epistemic_proposal_daemon.py              # Single run
    python epistemic_proposal_daemon.py --daemon     # Continuous daemon mode
    python epistemic_proposal_daemon.py --force      # Force generation even if not scheduled
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | EPISTEMIC | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class EpistemicProposalEngine:
    """
    Epistemic Proposal Engine

    Analyzes outcomes and generates concrete, actionable improvement proposals.
    All proposals include:
    - Clear description of the change
    - Evidence supporting the proposal
    - Expected impact
    - Risk assessment
    - Rollback plan
    """

    def __init__(self):
        self.conn = self._get_connection()
        self.config = self._load_config()

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Establish database connection."""
        return psycopg2.connect(
            host=os.getenv('PGHOST', '127.0.0.1'),
            port=os.getenv('PGPORT', '54322'),
            database=os.getenv('PGDATABASE', 'postgres'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', 'postgres')
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load schedule configuration from database."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_governance.epistemic_schedule_config
                WHERE config_id = 'DEFAULT'
            """)
            row = cur.fetchone()
            if row:
                return dict(row)
            return {
                'run_interval_hours': 168,
                'run_day_of_week': 0,
                'run_hour_utc': 0,
                'min_outcomes_for_analysis': 30,
                'min_confidence_for_proposal': 0.70,
                'is_active': True
            }

    def should_run(self) -> bool:
        """Check if it's time to run based on schedule."""
        if not self.config.get('is_active', True):
            logger.info("Epistemic engine is disabled in config")
            return False

        now = datetime.utcnow()

        # Check day of week (0 = Monday in Python, but 0 = Sunday in our config)
        # Adjust: Python Monday=0, config Sunday=0
        python_dow = now.weekday()  # 0=Mon, 6=Sun
        config_dow = self.config.get('run_day_of_week', 0)  # 0=Sun, 6=Sat

        # Convert config dow to python dow
        expected_dow = (config_dow - 1) % 7 if config_dow > 0 else 6

        if python_dow != expected_dow:
            logger.debug(f"Not scheduled day: today={python_dow}, expected={expected_dow}")
            return False

        # Check hour
        expected_hour = self.config.get('run_hour_utc', 0)
        if now.hour != expected_hour:
            logger.debug(f"Not scheduled hour: now={now.hour}, expected={expected_hour}")
            return False

        # Check if already ran today
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM fhq_governance.epistemic_proposal_runs
                WHERE run_started_at::DATE = CURRENT_DATE
                AND run_status = 'COMPLETED'
            """)
            if cur.fetchone()[0] > 0:
                logger.info("Already ran today, skipping")
                return False

        return True

    def generate_proposals(self, triggered_by: str = 'DAEMON') -> Dict[str, Any]:
        """
        Main entry point: Generate all epistemic proposals.

        Returns:
            Dict with run_id, proposals_generated, and proposal details
        """
        logger.info("="*60)
        logger.info("EPISTEMIC PROPOSAL ENGINE - Starting Analysis")
        logger.info("="*60)

        # Call the database function
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT fhq_governance.fn_generate_epistemic_proposals(%s, %s)
            """, ('SCHEDULED' if triggered_by == 'DAEMON' else 'MANUAL', triggered_by))
            run_id = cur.fetchone()[0]
            self.conn.commit()

        # Get run results
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_governance.epistemic_proposal_runs
                WHERE run_id = %s
            """, (run_id,))
            run_result = dict(cur.fetchone())

        logger.info(f"Run ID: {run_id}")
        logger.info(f"Outcomes analyzed: {run_result['outcomes_analyzed']}")
        logger.info(f"Proposals generated: {run_result['proposals_generated']}")
        logger.info(f"Proposals skipped: {run_result['proposals_skipped']}")

        # Get generated proposals
        proposals = self._get_proposals_for_run(run_id)

        if proposals:
            self._print_proposals(proposals)
        else:
            logger.info("No proposals generated - all metrics within acceptable ranges")

        return {
            'run_id': str(run_id),
            'outcomes_analyzed': run_result['outcomes_analyzed'],
            'proposals_generated': run_result['proposals_generated'],
            'proposals': proposals
        }

    def _get_proposals_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetch proposals generated in this run."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    proposal_code,
                    proposal_type,
                    target_parameter,
                    delta_description,
                    reasoning_summary,
                    reasoning_detailed,
                    evidence_sample_size,
                    evidence_time_window,
                    confidence_in_proposal,
                    risk_severity,
                    risk_assessment,
                    expected_improvement,
                    expected_magnitude,
                    rollback_plan,
                    expires_at
                FROM fhq_governance.epistemic_proposals
                WHERE generation_run_id = %s
                ORDER BY confidence_in_proposal DESC
            """, (run_id,))
            return [dict(row) for row in cur.fetchall()]

    def _print_proposals(self, proposals: List[Dict[str, Any]]):
        """Print proposals in human-readable format."""
        logger.info("")
        logger.info("="*60)
        logger.info("GENERATED PROPOSALS FOR REVIEW")
        logger.info("="*60)

        for i, p in enumerate(proposals, 1):
            print(f"""
┌──────────────────────────────────────────────────────────────┐
│ PROPOSAL {i}: {p['proposal_code']}
├──────────────────────────────────────────────────────────────┤
│ TYPE:       {p['proposal_type']}
│ TARGET:     {p['target_parameter']}
│ CHANGE:     {p['delta_description']}
├──────────────────────────────────────────────────────────────┤
│ SUMMARY:
│   {p['reasoning_summary']}
├──────────────────────────────────────────────────────────────┤
│ EVIDENCE:
│   • Sample size: {p['evidence_sample_size']} outcomes
│   • Time window: {p['evidence_time_window']}
│   • Confidence: {float(p['confidence_in_proposal'])*100:.0f}%
├──────────────────────────────────────────────────────────────┤
│ EXPECTED IMPACT:
│   {p['expected_improvement']}
│   Magnitude: {p['expected_magnitude']}
├──────────────────────────────────────────────────────────────┤
│ RISK:
│   Severity: {p['risk_severity']}
│   {p['risk_assessment'][:80]}...
├──────────────────────────────────────────────────────────────┤
│ ROLLBACK:
│   {p['rollback_plan'][:80]}...
├──────────────────────────────────────────────────────────────┤
│ EXPIRES: {p['expires_at']}
│
│ TO APPROVE: SELECT fhq_governance.fn_approve_epistemic_proposal(
│               '{p['proposal_code']}', 'YOUR_NAME', 'Approval reason');
│ TO REJECT:  SELECT fhq_governance.fn_reject_epistemic_proposal(
│               '{p['proposal_code']}', 'YOUR_NAME', 'Rejection reason');
└──────────────────────────────────────────────────────────────┘
""")

    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """Get all pending proposals awaiting review."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_governance.v_pending_epistemic_proposals
            """)
            return [dict(row) for row in cur.fetchall()]

    def get_proposal_detail(self, proposal_code: str) -> Optional[Dict[str, Any]]:
        """Get full detail for a specific proposal."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_governance.epistemic_proposals
                WHERE proposal_code = %s
            """, (proposal_code,))
            row = cur.fetchone()
            return dict(row) if row else None

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def run_daemon(check_interval_minutes: int = 60):
    """
    Run as a continuous daemon, checking schedule periodically.

    Args:
        check_interval_minutes: How often to check if it's time to run
    """
    import time

    logger.info("Epistemic Proposal Daemon starting in daemon mode")
    logger.info(f"Check interval: {check_interval_minutes} minutes")

    while True:
        try:
            engine = EpistemicProposalEngine()

            if engine.should_run():
                logger.info("Scheduled run triggered")
                engine.generate_proposals('DAEMON')
            else:
                logger.debug("Not time to run yet")

            engine.close()

        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")

        time.sleep(check_interval_minutes * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Epistemic Proposal Engine - Generate improvement proposals'
    )
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run in continuous daemon mode'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force generation even if not scheduled'
    )
    parser.add_argument(
        '--list-pending',
        action='store_true',
        help='List all pending proposals'
    )
    parser.add_argument(
        '--detail',
        type=str,
        help='Show detail for a specific proposal code'
    )
    parser.add_argument(
        '--triggered-by',
        type=str,
        default='CLI',
        help='Who/what triggered this run'
    )

    args = parser.parse_args()

    if args.daemon:
        run_daemon()
    elif args.list_pending:
        engine = EpistemicProposalEngine()
        proposals = engine.get_pending_proposals()
        if proposals:
            print(f"\n{'='*60}")
            print(f"PENDING PROPOSALS: {len(proposals)}")
            print('='*60)
            for p in proposals:
                print(f"""
  {p['proposal_code']} | {p['proposal_type']}
    Target: {p['target_parameter']}
    Change: {p['delta_description']}
    Confidence: {float(p['confidence_in_proposal'])*100:.0f}%
    Risk: {p['risk_severity']}
    Expires: {p['expires_at']}
""")
        else:
            print("\nNo pending proposals.")
        engine.close()
    elif args.detail:
        engine = EpistemicProposalEngine()
        proposal = engine.get_proposal_detail(args.detail)
        if proposal:
            print(json.dumps(proposal, indent=2, default=str))
        else:
            print(f"Proposal not found: {args.detail}")
        engine.close()
    else:
        engine = EpistemicProposalEngine()

        if args.force or engine.should_run():
            result = engine.generate_proposals(args.triggered_by)
            print(f"\nRun complete. Generated {result['proposals_generated']} proposals.")
        else:
            logger.info("Not scheduled to run. Use --force to override.")
            pending = engine.get_pending_proposals()
            if pending:
                print(f"\n{len(pending)} proposals pending review. Use --list-pending to view.")

        engine.close()


if __name__ == '__main__':
    main()
