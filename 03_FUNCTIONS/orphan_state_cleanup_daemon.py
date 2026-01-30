#!/usr/bin/env python3
"""
Orphan State Cleanup Daemon
============================
Authority: DAY30 Session 9 — Pipeline Integrity

Finds FALSIFIED hypotheses with orphaned downstream state:
  - OPEN shadow trades  -> EXPIRED
  - OPEN capital sims   -> STOPPED
  - RUNNING experiments  -> COMPLETED (result=FALSIFIED)

Runs every 60 minutes. Registers as FHQ_ORPHAN_STATE_CLEANUP.
"""

import os
import sys
import json
import time
import uuid
import logging
import pathlib
from datetime import datetime, timezone, timedelta

env_path = pathlib.Path(__file__).parent.parent / '.env'
from dotenv import load_dotenv
load_dotenv(env_path)

import psycopg2
from psycopg2.extras import RealDictCursor, Json

# ── Configuration ─────────────────────────────────────────────────
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres'),
}

DAEMON_NAME = 'orphan_state_cleanup'
TASK_NAME = 'FHQ_ORPHAN_STATE_CLEANUP'
CYCLE_INTERVAL_SECONDS = 3600  # 60 minutes
EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), 'evidence')

logging.basicConfig(
    level=logging.INFO,
    format='[ORPHAN_CLEANUP] %(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'orphan_state_cleanup.log')),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(DAEMON_NAME)


# ── Daemon Class ──────────────────────────────────────────────────
class OrphanStateCleanupDaemon:
    """
    Periodic daemon that cascades FALSIFIED hypothesis status to
    downstream pipeline tables (shadow_trades, capital_simulation_ledger,
    experiment_registry).
    """

    def __init__(self):
        self.db_conn = None

    # ── Lifecycle ─────────────────────────────────────────────────
    def initialize(self) -> bool:
        try:
            self.db_conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Connected to PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"FATAL: Cannot connect to database: {e}")
            return False

    def _heartbeat(self, status: str, metadata: dict = None):
        # Valid statuses: HEALTHY, DEGRADED, UNHEALTHY, STOPPED
        if status not in ('HEALTHY', 'DEGRADED', 'UNHEALTHY', 'STOPPED'):
            status = 'HEALTHY'
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_monitoring.daemon_health
                        (daemon_name, status, last_heartbeat, metadata,
                         created_at, updated_at, expected_interval_minutes,
                         is_critical, lifecycle_status)
                    VALUES (%s, %s, NOW(), %s, NOW(), NOW(), 60, FALSE, 'ACTIVE')
                    ON CONFLICT (daemon_name) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_heartbeat = NOW(),
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                """, (DAEMON_NAME, status, Json(metadata or {})))
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            try:
                self.db_conn.rollback()
            except Exception:
                pass

    def _log_run(self, started_at, exit_code: int, rows: dict, error: str = None):
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_monitoring.run_ledger
                        (task_name, run_id, started_at, finished_at,
                         exit_code, rows_written_by_table, error_excerpt)
                    VALUES (%s, %s, %s, NOW(), %s, %s, %s)
                """, (
                    TASK_NAME,
                    str(uuid.uuid4()),
                    started_at,
                    exit_code,
                    Json(rows),
                    error,
                ))
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Run ledger write failed: {e}")

    # ── Core Logic ────────────────────────────────────────────────
    def _find_orphaned_hypotheses(self):
        """Find FALSIFIED hypotheses that still have OPEN downstream state."""
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT hc.canon_id, hc.hypothesis_code
                FROM fhq_learning.hypothesis_canon hc
                WHERE hc.status = 'FALSIFIED'
                AND (
                    EXISTS (
                        SELECT 1 FROM fhq_execution.shadow_trades st
                        WHERE st.source_hypothesis_id = hc.canon_id::text
                        AND st.status = 'OPEN'
                    )
                    OR EXISTS (
                        SELECT 1 FROM fhq_learning.capital_simulation_ledger csl
                        WHERE csl.hypothesis_id = hc.canon_id
                        AND csl.status = 'OPEN'
                    )
                    OR EXISTS (
                        SELECT 1 FROM fhq_learning.experiment_registry er
                        WHERE er.hypothesis_id = hc.canon_id
                        AND er.status = 'RUNNING'
                    )
                )
            """)
            return cur.fetchall()

    def _expire_shadow_trades(self, canon_id: str) -> int:
        with self.db_conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_execution.shadow_trades
                SET status = 'EXPIRED',
                    exit_reason = 'HYPOTHESIS_FALSIFIED',
                    exit_time = NOW()
                WHERE source_hypothesis_id = %s::text AND status = 'OPEN'
            """, (str(canon_id),))
            return cur.rowcount

    def _stop_simulations(self, canon_id: str) -> int:
        with self.db_conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_learning.capital_simulation_ledger
                SET status = 'STOPPED'
                WHERE hypothesis_id = %s AND status = 'OPEN'
            """, (canon_id,))
            return cur.rowcount

    def _complete_experiments(self, canon_id: str) -> int:
        with self.db_conn.cursor() as cur:
            cur.execute("""
                UPDATE fhq_learning.experiment_registry
                SET status = 'COMPLETED',
                    result = 'FALSIFIED',
                    completed_at = NOW()
                WHERE hypothesis_id = %s AND status = 'RUNNING'
            """, (canon_id,))
            return cur.rowcount

    # ── Cycle ─────────────────────────────────────────────────────
    def run_once(self) -> dict:
        logger.info(f"{'='*60}")
        logger.info(f"CYCLE: {datetime.now(timezone.utc).isoformat()}")
        logger.info(f"{'='*60}")

        started_at = datetime.now(timezone.utc)
        self._heartbeat('HEALTHY', {'phase': 'RUNNING'})

        result = {
            'timestamp': started_at.isoformat(),
            'orphans_found': 0,
            'trades_expired': 0,
            'simulations_stopped': 0,
            'experiments_completed': 0,
            'details': [],
        }

        try:
            orphans = self._find_orphaned_hypotheses()
            result['orphans_found'] = len(orphans)

            if not orphans:
                logger.info("No orphaned state found. Pipeline clean.")
                self._heartbeat('HEALTHY', {'last_result': 'NO_ORPHANS'})
                self._log_run(started_at, 0, {})
                return result

            logger.info(f"Found {len(orphans)} FALSIFIED hypotheses with orphaned state")

            for hyp in orphans:
                cid = hyp['canon_id']
                code = hyp.get('hypothesis_code', 'UNKNOWN')

                trades = self._expire_shadow_trades(cid)
                sims = self._stop_simulations(cid)
                exps = self._complete_experiments(cid)
                self.db_conn.commit()

                result['trades_expired'] += trades
                result['simulations_stopped'] += sims
                result['experiments_completed'] += exps
                result['details'].append({
                    'canon_id': str(cid),
                    'hypothesis_code': code,
                    'trades_expired': trades,
                    'simulations_stopped': sims,
                    'experiments_completed': exps,
                })

                logger.info(
                    f"  [{code}] trades={trades}, sims={sims}, exps={exps}"
                )

            # Write evidence
            self._write_evidence(result)

            total = (
                result['trades_expired']
                + result['simulations_stopped']
                + result['experiments_completed']
            )
            self._heartbeat('HEALTHY', {
                'last_result': 'CLEANED',
                'orphans': len(orphans),
                'total_rows': total,
            })
            self._log_run(started_at, 0, {
                'fhq_execution.shadow_trades': result['trades_expired'],
                'fhq_learning.capital_simulation_ledger': result['simulations_stopped'],
                'fhq_learning.experiment_registry': result['experiments_completed'],
            })

        except Exception as e:
            logger.error(f"Cycle failed: {e}")
            # Rollback FIRST before any further DB operations
            try:
                self.db_conn.rollback()
            except Exception:
                pass
            self._heartbeat('UNHEALTHY', {'error': str(e)})
            self._log_run(started_at, 1, {}, str(e))
            result['error'] = str(e)

        return result

    def _write_evidence(self, result: dict):
        os.makedirs(EVIDENCE_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        evidence = {
            'directive': 'DAY30_SESSION9_ORPHAN_CLEANUP',
            'executed_at': result['timestamp'],
            'executed_by': 'STIG_ORPHAN_CLEANUP',
            'dry_run': False,
            'result_summary': {
                'orphans_found': result['orphans_found'],
                'trades_expired': result['trades_expired'],
                'simulations_stopped': result['simulations_stopped'],
                'experiments_completed': result['experiments_completed'],
            },
            'details': result['details'],
        }
        path = os.path.join(EVIDENCE_DIR, f'ORPHAN_CLEANUP_{ts}.json')
        with open(path, 'w') as f:
            json.dump(evidence, f, indent=2, default=str)
        logger.info(f"Evidence: {path}")

    # ── Continuous Loop ───────────────────────────────────────────
    def run_continuous(self):
        logger.info("="*60)
        logger.info("ORPHAN STATE CLEANUP DAEMON — CONTINUOUS MODE")
        logger.info(f"Cycle interval: {CYCLE_INTERVAL_SECONDS}s")
        logger.info("="*60)

        if not self.initialize():
            logger.error("FATAL: Initialization failed.")
            sys.exit(1)

        while True:
            try:
                self.run_once()
                logger.info(f"Next cycle in {CYCLE_INTERVAL_SECONDS}s")
                time.sleep(CYCLE_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                logger.info("Daemon stopped by user.")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(60)


# ── Entry Point ───────────────────────────────────────────────────
def main():
    daemon = OrphanStateCleanupDaemon()
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        if daemon.initialize():
            result = daemon.run_once()
            print(json.dumps(result, indent=2, default=str))
            sys.exit(0 if 'error' not in result else 1)
    else:
        daemon.run_continuous()


if __name__ == '__main__':
    main()
