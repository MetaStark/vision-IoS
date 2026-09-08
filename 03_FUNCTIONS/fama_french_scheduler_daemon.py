#!/usr/bin/env python3
"""
FAMA-FRENCH SCHEDULER DAEMON
============================
Directive: CEO-DIR-2026-120 P2.1
Classification: G2_DATA_PIPELINE
Date: 2026-01-22

Weekly ingestion of Fama-French 5-Factor + Momentum from Kenneth French Data Library.

Schedule: Every Monday at 08:00 UTC (cron: 0 8 * * 1)
Rationale: Kenneth French publishes daily data but batches updates monthly.
           Weekly checks are sufficient to catch new data while minimizing load.

Authority: CEO, STIG (Technical)
Employment Contract: EC-003
"""

import os
import sys
import json
import hashlib
import logging
import argparse
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas_datareader.data as web
from dotenv import load_dotenv

# Load environment
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[FF-SCHEDULER] %(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

TASK_ID = 'FAMA-FRENCH-WEEKLY-001'


class FamaFrenchSchedulerDaemon:
    """
    Daemon for weekly Fama-French factor ingestion.

    Reads schedule from fhq_governance.scheduled_tasks and executes
    when due. Updates task status and logs evidence.
    """

    def __init__(self):
        self.conn = None
        self._run_id = None

    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Connected to database")

    def close(self):
        """Close connection."""
        if self.conn:
            self.conn.close()

    def check_if_due(self) -> bool:
        """Check if task is due for execution."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT task_id, scheduled_at, status, action_params
                FROM fhq_governance.scheduled_tasks
                WHERE task_id = %s
            """, (TASK_ID,))
            task = cur.fetchone()

            if not task:
                logger.warning(f"Task {TASK_ID} not found in scheduled_tasks")
                return False

            if task['status'] == 'RUNNING':
                logger.info("Task already running, skipping")
                return False

            scheduled_at = task['scheduled_at']
            if scheduled_at and scheduled_at <= datetime.now(timezone.utc):
                logger.info(f"Task is due (scheduled: {scheduled_at})")
                return True

            logger.info(f"Task not yet due (scheduled: {scheduled_at})")
            return False

    def mark_running(self):
        """Mark task as running."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_governance.scheduled_tasks
                SET status = 'RUNNING', executed_at = NOW()
                WHERE task_id = %s
            """, (TASK_ID,))
            self.conn.commit()

    def mark_complete(self, result: Dict[str, Any]):
        """Mark task as complete and schedule next run."""
        with self.conn.cursor() as cur:
            # Update task status
            cur.execute("""
                UPDATE fhq_governance.scheduled_tasks
                SET status = 'COMPLETED',
                    result = %s,
                    scheduled_at = NOW() + INTERVAL '1 week'
                WHERE task_id = %s
            """, (json.dumps(result), TASK_ID))

            # Update ingest_schedule next_run
            cur.execute("""
                UPDATE fhq_market.ingest_schedule
                SET last_run_at = NOW(),
                    last_run_status = 'SUCCESS',
                    next_run_at = NOW() + INTERVAL '1 week'
                WHERE schedule_name = 'FAMA_FRENCH_FACTORS'
            """)

            self.conn.commit()
            logger.info("Task marked complete, next run in 1 week")

    def mark_failed(self, error: str):
        """Mark task as failed."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_governance.scheduled_tasks
                SET status = 'FAILED',
                    result = %s,
                    scheduled_at = NOW() + INTERVAL '1 hour'
                WHERE task_id = %s
            """, (json.dumps({'error': error}), TASK_ID))

            cur.execute("""
                UPDATE fhq_market.ingest_schedule
                SET last_run_at = NOW(),
                    last_run_status = 'FAILED',
                    next_run_at = NOW() + INTERVAL '1 hour'
                WHERE schedule_name = 'FAMA_FRENCH_FACTORS'
            """)

            self.conn.commit()
            logger.error(f"Task marked failed, retry in 1 hour: {error}")

    def ingest_fama_french(self) -> Dict[str, Any]:
        """
        Ingest Fama-French factors from Kenneth French Data Library.

        Returns:
            Dict with ingestion results
        """
        logger.info("Starting Fama-French factor ingestion...")

        start = datetime(1963, 7, 1)
        end = datetime.now()

        # Fetch FF5 factors
        logger.info("Fetching FF5 factors...")
        ff5 = web.DataReader('F-F_Research_Data_5_Factors_2x3_daily', 'famafrench', start, end)
        ff5_df = ff5[0]

        # Fetch Momentum
        logger.info("Fetching Momentum factor...")
        mom = web.DataReader('F-F_Momentum_Factor_daily', 'famafrench', start, end)
        mom_df = mom[0]

        # Merge
        ff_df = ff5_df.join(mom_df, how='inner')
        ff_df = ff_df.reset_index()
        ff_df.columns = ['date', 'mkt_rf', 'smb', 'hml', 'rmw', 'cma', 'rf', 'mom']

        # Convert from percent to decimal
        for col in ['mkt_rf', 'smb', 'hml', 'rmw', 'cma', 'rf', 'mom']:
            ff_df[col] = ff_df[col] / 100

        logger.info(f"Merged data: {len(ff_df)} rows, {ff_df['date'].min()} to {ff_df['date'].max()}")

        # Get existing max date
        with self.conn.cursor() as cur:
            cur.execute("SELECT MAX(date) FROM fhq_research.fama_french_factors")
            existing_max = cur.fetchone()[0]

        # Filter to only new data
        if existing_max:
            new_data = ff_df[ff_df['date'].dt.date > existing_max]
            logger.info(f"New data since {existing_max}: {len(new_data)} rows")
        else:
            new_data = ff_df
            logger.info("No existing data, inserting all rows")

        # Insert new data
        inserted = 0
        with self.conn.cursor() as cur:
            for _, row in new_data.iterrows():
                cur.execute("""
                    INSERT INTO fhq_research.fama_french_factors
                    (date, mkt_rf, smb, hml, rmw, cma, rf, mom)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date) DO UPDATE SET
                        mkt_rf = EXCLUDED.mkt_rf,
                        smb = EXCLUDED.smb,
                        hml = EXCLUDED.hml,
                        rmw = EXCLUDED.rmw,
                        cma = EXCLUDED.cma,
                        rf = EXCLUDED.rf,
                        mom = EXCLUDED.mom
                """, (row['date'].date(), float(row['mkt_rf']), float(row['smb']),
                      float(row['hml']), float(row['rmw']), float(row['cma']),
                      float(row['rf']), float(row['mom'])))
                inserted += 1

            self.conn.commit()

        # Get final count
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM fhq_research.fama_french_factors")
            total, min_date, max_date = cur.fetchone()

        result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'rows_inserted': inserted,
            'total_rows': total,
            'date_range': {
                'min': str(min_date),
                'max': str(max_date)
            },
            'source': 'Kenneth French Data Library'
        }

        logger.info(f"Ingestion complete: {inserted} new rows, {total} total")
        return result

    def run(self, force: bool = False):
        """
        Main daemon run method.

        Args:
            force: If True, run regardless of schedule
        """
        self.connect()

        try:
            if force or self.check_if_due():
                self.mark_running()

                try:
                    result = self.ingest_fama_french()
                    self.mark_complete(result)
                    self._generate_evidence(result)

                except Exception as e:
                    self.mark_failed(str(e))
                    raise

            else:
                logger.info("Task not due, exiting")

        finally:
            self.close()

    def _generate_evidence(self, result: Dict[str, Any]):
        """Generate evidence file for the run."""
        evidence = {
            'directive': 'CEO-DIR-2026-120',
            'phase': 'P2.1',
            'title': 'Fama-French Weekly Ingestion',
            'task_id': TASK_ID,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'generated_by': 'FF-SCHEDULER-DAEMON',
            'result': result
        }

        evidence_hash = hashlib.sha256(
            json.dumps(evidence, sort_keys=True).encode()
        ).hexdigest()[:16]

        filename = f"evidence/FF_WEEKLY_INGEST_{evidence_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(os.path.dirname(__file__), filename)

        with open(filepath, 'w') as f:
            json.dump(evidence, f, indent=2)

        logger.info(f"Evidence file: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description='Fama-French Weekly Scheduler Daemon (CEO-DIR-2026-120 P2.1)'
    )
    parser.add_argument('--run', action='store_true', help='Check schedule and run if due')
    parser.add_argument('--force', action='store_true', help='Force run regardless of schedule')
    parser.add_argument('--status', action='store_true', help='Show task status')

    args = parser.parse_args()

    daemon = FamaFrenchSchedulerDaemon()

    if args.status:
        daemon.connect()
        with daemon.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT task_id, status, scheduled_at, executed_at,
                       action_params->>'schedule_cron' as cron
                FROM fhq_governance.scheduled_tasks
                WHERE task_id = %s
            """, (TASK_ID,))
            task = cur.fetchone()

            cur.execute("""
                SELECT COUNT(*), MIN(date), MAX(date)
                FROM fhq_research.fama_french_factors
            """)
            count, min_date, max_date = cur.fetchone()

        daemon.close()

        print(f"\n{'='*60}")
        print("FAMA-FRENCH SCHEDULER STATUS")
        print(f"{'='*60}")
        print(f"Task ID:      {task['task_id']}")
        print(f"Status:       {task['status']}")
        print(f"Cron:         {task['cron']}")
        print(f"Scheduled:    {task['scheduled_at']}")
        print(f"Last Run:     {task['executed_at']}")
        print(f"\nData Status:")
        print(f"  Rows:       {count}")
        print(f"  Range:      {min_date} to {max_date}")
        print(f"{'='*60}\n")

    elif args.run or args.force:
        daemon.run(force=args.force)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
