#!/usr/bin/env python3
"""
IoS-014 AUTONOMOUS TASK ORCHESTRATION ENGINE
Authority: CEO DIRECTIVE — IoS-014 BUILD & AUTONOMOUS AGENT ACTIVATION
Purpose: Orchestrate all IoS modules with economic safety and DEFCON awareness

This is the IoS-014 upgrade to orchestrator_v1.py, adding:
1. VendorGuard - 90% soft ceiling enforcement, fallback routing
2. DEFCONRouter - DEFCON-aware task scheduling
3. ModeRouter - Execution mode control (LOCAL_DEV, PAPER_PROD, LIVE_PROD)
4. Health monitoring and heartbeat
5. Enhanced audit logging for VEGA compliance

Usage:
    python ios014_orchestrator.py                    # Run one cycle
    python ios014_orchestrator.py --continuous       # Run autonomously
    python ios014_orchestrator.py --dry-run          # Show plan without execution
    python ios014_orchestrator.py --status           # Show system status
"""

import os
import sys
import subprocess
import json
import hashlib
import argparse
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Database
import psycopg2
from psycopg2.extras import RealDictCursor

# IoS-014 Components
from vendor_guard import VendorGuard, get_vendor_guard, QuotaDecision
from defcon_router import (
    CombinedRouter, get_router,
    DEFCONLevel, ExecutionMode, TaskCriticality
)


# =============================================================================
# CONFIGURATION
# =============================================================================

class IoS014Config:
    """IoS-014 Orchestrator configuration"""

    # Agent identity
    AGENT_ID = "IOS014"
    ORCHESTRATOR_VERSION = "14.0.0"
    ORCHESTRATOR_NAME = "IoS-014 Autonomous Task Orchestration Engine"

    # Database connection
    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    # Scheduling configuration
    CYCLE_INTERVALS = {
        'NIGHTLY': 86400,     # 24 hours
        'HOURLY': 3600,       # 1 hour
        'REALTIME': 300,      # 5 minutes
        'EVENT': 0,           # Event-driven
    }

    DEFAULT_CYCLE_INTERVAL = 3600  # 1 hour default
    FUNCTION_TIMEOUT_SECONDS = 300  # 5 minutes per function
    HEARTBEAT_INTERVAL_SECONDS = 60  # Heartbeat every minute

    # Vision-IoS functions directory
    @staticmethod
    def get_functions_dir() -> Path:
        return Path(__file__).parent.parent / "03_FUNCTIONS"

    # Governance evidence directory
    @staticmethod
    def get_evidence_dir() -> Path:
        evidence_dir = Path(__file__).parent.parent / "05_GOVERNANCE" / "PHASE3"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        return evidence_dir


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger("ios014_orchestrator")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Console handler
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger


# =============================================================================
# DATABASE INTERFACE
# =============================================================================

class IoS014Database:
    """Database interface for IoS-014 orchestrator"""

    def __init__(self, connection_string: str, logger: logging.Logger):
        self.connection_string = connection_string
        self.logger = logger
        self.conn = None

    def connect(self):
        """Establish database connection"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(self.connection_string)
            self.logger.debug("Database connection established")
        return self.conn

    def close(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.logger.debug("Database connection closed")

    def read_active_tasks(self) -> List[Dict[str, Any]]:
        """Read active executable tasks from task registry (must have function_path)"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    task_id,
                    task_name,
                    task_type,
                    owned_by_agent as agent_id,
                    description as task_description,
                    parameters_schema as task_config,
                    (task_status = 'ACTIVE') as enabled,
                    created_at,
                    updated_at
                FROM fhq_governance.task_registry
                WHERE task_status = 'ACTIVE'
                  AND parameters_schema->>'function_path' IS NOT NULL
                  AND parameters_schema->>'function_path' != ''
                ORDER BY task_id
            """)
            tasks = cur.fetchall()
            return [dict(task) for task in tasks]

    def read_task_schedule(self, task_name: str) -> Optional[Dict[str, Any]]:
        """Read schedule configuration for a task"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    parameters_schema as config
                FROM fhq_governance.task_registry
                WHERE task_name = %s AND task_status = 'ACTIVE'
            """, (task_name,))
            row = cur.fetchone()
            if row and row['config']:
                return row['config'] if isinstance(row['config'], dict) else {}
            return None

    def log_cycle_start(self, cycle_id: str, hash_chain_id: str, tasks: List[Dict], defcon: str, mode: str) -> str:
        """Log orchestrator cycle start"""
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id,
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    initiated_at,
                    decision,
                    decision_rationale,
                    vega_reviewed,
                    vega_override,
                    hash_chain_id
                ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING action_id
            """, (
                'IOS014_CYCLE_START',
                cycle_id,
                'ORCHESTRATOR_CYCLE',
                IoS014Config.AGENT_ID,
                datetime.now(timezone.utc),
                'IN_PROGRESS',
                json.dumps({
                    'cycle_id': cycle_id,
                    'orchestrator_version': IoS014Config.ORCHESTRATOR_VERSION,
                    'tasks_scheduled': len(tasks),
                    'task_names': [t['task_name'] for t in tasks],
                    'defcon_level': defcon,
                    'execution_mode': mode
                }),
                False,
                False,
                hash_chain_id
            ))
            action_id = cur.fetchone()[0]
            conn.commit()
            return str(action_id)

    def log_cycle_complete(
        self,
        cycle_id: str,
        hash_chain_id: str,
        results: List[Dict],
        cycle_status: str,
        vendor_snapshot: Dict
    ) -> str:
        """Log orchestrator cycle completion"""
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_id,
                    action_type,
                    action_target,
                    action_target_type,
                    initiated_by,
                    initiated_at,
                    decision,
                    decision_rationale,
                    vega_reviewed,
                    vega_override,
                    hash_chain_id
                ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING action_id
            """, (
                'IOS014_CYCLE_COMPLETE',
                cycle_id,
                'ORCHESTRATOR_CYCLE',
                IoS014Config.AGENT_ID,
                datetime.now(timezone.utc),
                cycle_status,
                json.dumps({
                    'cycle_id': cycle_id,
                    'orchestrator_version': IoS014Config.ORCHESTRATOR_VERSION,
                    'tasks_executed': len(results),
                    'success_count': sum(1 for r in results if r.get('success')),
                    'failure_count': sum(1 for r in results if not r.get('success')),
                    'skipped_count': sum(1 for r in results if r.get('skipped')),
                    'vendor_snapshot': vendor_snapshot
                }),
                False,
                False,
                hash_chain_id
            ))
            action_id = cur.fetchone()[0]
            conn.commit()
            return str(action_id)

    def write_heartbeat(self, cycle_id: str, status: str, metadata: Dict) -> None:
        """Write heartbeat to monitoring table"""
        try:
            conn = self.connect()
            with conn.cursor() as cur:
                # Try to insert/update heartbeat
                cur.execute("""
                    INSERT INTO fhq_monitoring.daemon_health (
                        daemon_name, status, last_heartbeat, metadata
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (daemon_name) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_heartbeat = EXCLUDED.last_heartbeat,
                        metadata = EXCLUDED.metadata
                """, (
                    'ios014_orchestrator',
                    status,
                    datetime.now(timezone.utc),
                    json.dumps(metadata)
                ))
                conn.commit()
        except Exception as e:
            self.logger.warning(f"Failed to write heartbeat: {e}")


# =============================================================================
# FUNCTION EXECUTOR
# =============================================================================

class IoS014Executor:
    """Executes Vision-IoS functions with vendor quota protection"""

    def __init__(self, logger: logging.Logger, vendor_guard: VendorGuard):
        self.logger = logger
        self.vendor_guard = vendor_guard
        self.functions_dir = IoS014Config.get_functions_dir()

    def get_task_vendors(self, task_config: Dict) -> List[str]:
        """Extract vendor requirements from task config"""
        return task_config.get('vendors', [])

    def check_vendor_availability(self, task_name: str, vendors: List[str]) -> Tuple[bool, str, Optional[str]]:
        """
        Check if required vendors are available within quota.

        Returns:
            Tuple of (can_proceed, reason, resolved_vendor)
        """
        if not vendors:
            return True, "No vendor requirements", None

        for vendor in vendors:
            resolved, result = self.vendor_guard.resolve_vendor_chain(vendor, 1)
            if resolved:
                return True, f"Using vendor: {resolved}", resolved
            elif result:
                self.logger.warning(f"Vendor {vendor}: {result.message}")

        return False, f"No available vendor from: {vendors}", None

    def execute_function(
        self,
        task: Dict[str, Any],
        dry_run: bool = False,
        vendor_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a Vision-IoS function with quota protection"""

        task_name = task['task_name']
        agent_id = task.get('agent_id', 'UNKNOWN')
        task_config = task.get('task_config', {}) or {}

        # Support both function_path and script fields (CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001)
        function_path = task_config.get('function_path')
        if not function_path:
            # Fall back to script field (legacy task configs)
            script = task_config.get('script')
            if script:
                function_path = f"03_FUNCTIONS/{script}"

        if not function_path:
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': False,
                'error': 'Missing function_path or script in task_config'
            }

        # Resolve full path - handle both absolute and relative paths
        if os.path.isabs(function_path):
            full_path = Path(function_path)
        else:
            full_path = self.functions_dir.parent / function_path

        if not full_path.exists():
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': False,
                'error': f'Function file not found: {full_path}'
            }

        # Check vendor availability
        vendors = self.get_task_vendors(task_config)
        if vendors and not dry_run:
            can_proceed, reason, resolved_vendor = self.check_vendor_availability(task_name, vendors)
            if not can_proceed:
                return {
                    'task_name': task_name,
                    'agent_id': agent_id,
                    'success': False,
                    'skipped': True,
                    'skip_reason': 'QUOTA_PROTECTION',
                    'error': reason
                }
            # Set resolved vendor in environment
            if resolved_vendor:
                os.environ['IOS014_RESOLVED_VENDOR'] = resolved_vendor

        if dry_run:
            self.logger.info(f"[DRY RUN] Would execute: {full_path}")
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': True,
                'dry_run': True
            }

        # Execute function
        self.logger.info(f"Executing: {task_name}")

        try:
            start_time = time.time()

            # Build command
            cmd = [sys.executable, str(full_path)]
            if task_config.get('args'):
                cmd.extend(task_config['args'])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=IoS014Config.FUNCTION_TIMEOUT_SECONDS,
                cwd=str(full_path.parent),
                env={**os.environ}
            )

            execution_time = time.time() - start_time
            success = (result.returncode == 0)

            # Increment vendor usage on success
            if success and vendors:
                for vendor in vendors:
                    self.vendor_guard.increment_usage(vendor, 1, task_name)

            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': success,
                'exit_code': result.returncode,
                'execution_time_seconds': round(execution_time, 2),
                'stdout': result.stdout[-500:] if len(result.stdout) > 500 else result.stdout,
                'stderr': result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
            }

        except subprocess.TimeoutExpired:
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': False,
                'error': f'Execution timeout after {IoS014Config.FUNCTION_TIMEOUT_SECONDS}s'
            }
        except Exception as e:
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': False,
                'error': str(e)
            }


# =============================================================================
# IoS-014 ORCHESTRATOR
# =============================================================================

class IoS014Orchestrator:
    """
    IoS-014 Autonomous Task Orchestration Engine

    Implements:
    - Schedule Engine
    - Task DAG Engine
    - Vendor & Rate Limit Guard
    - Mode & DEFCON Router
    - Health & Heartbeat Monitor
    - Audit & Evidence Engine
    """

    def __init__(self, logger: logging.Logger, dry_run: bool = False):
        self.logger = logger
        self.dry_run = dry_run
        self.config = IoS014Config()

        # Initialize components
        conn_string = self.config.get_db_connection_string()
        self.db = IoS014Database(conn_string, logger)
        self.vendor_guard = VendorGuard(conn_string, logger)
        self.router = CombinedRouter(conn_string, logger)
        self.executor = IoS014Executor(logger, self.vendor_guard)

        # State
        self.cycle_count = 0
        self.start_time = datetime.now(timezone.utc)

    def generate_cycle_id(self) -> str:
        """Generate unique cycle ID"""
        return datetime.now(timezone.utc).strftime("IOS014_%Y%m%d_%H%M%S")

    def generate_hash_chain_id(self, cycle_id: str) -> str:
        """Generate hash chain ID for audit trail"""
        return f"HC-{IoS014Config.AGENT_ID}-{cycle_id}"

    def get_system_state(self) -> Dict[str, Any]:
        """Get current system state"""
        return self.router.get_system_state()

    def show_status(self) -> None:
        """Display current system status"""
        state = self.get_system_state()
        quota_summary = self.vendor_guard.get_quota_summary()

        print("\n" + "=" * 70)
        print(f"IoS-014 AUTONOMOUS TASK ORCHESTRATION ENGINE v{IoS014Config.ORCHESTRATOR_VERSION}")
        print("=" * 70)

        print(f"\nDEFCON Level: {state['defcon']['level']}")
        print(f"  Triggered by: {state['defcon']['triggered_by']}")
        print(f"  Reason: {state['defcon']['reason']}")

        print(f"\nExecution Mode: {state['mode']['mode']}")
        print(f"  Set by: {state['mode']['set_by']}")
        print(f"  Reason: {state['mode']['reason']}")

        print(f"\nMode Restrictions:")
        for key, value in state['restrictions'].items():
            print(f"  {key}: {value}")

        print("\n" + "-" * 70)
        print("VENDOR QUOTA STATUS")
        print("-" * 70)
        print(f"{'Vendor':<15} {'Tier':<8} {'Usage':<12} {'Status':<10} {'Interval'}")
        print("-" * 70)
        for item in quota_summary[:10]:  # Top 10
            status_icon = "OK" if item['status'] == 'OK' else "WARN" if item['status'] == 'WARNING' else "CRIT"
            print(f"{item['vendor']:<15} {item['tier']:<8} {item['usage']:>4}/{item['ceiling']:<6} {status_icon:<10} {item['interval']}")

        print("=" * 70)

    def run_cycle(self, function_filter: Optional[str] = None) -> Dict[str, Any]:
        """Run one orchestration cycle"""

        cycle_id = self.generate_cycle_id()
        hash_chain_id = self.generate_hash_chain_id(cycle_id)
        self.cycle_count += 1

        self.logger.info("=" * 70)
        self.logger.info(f"IoS-014 ORCHESTRATION CYCLE #{self.cycle_count}")
        self.logger.info(f"Cycle ID: {cycle_id}")
        if self.dry_run:
            self.logger.info("MODE: DRY RUN (no actual execution)")
        self.logger.info("=" * 70)

        try:
            # Connect
            self.db.connect()
            self.vendor_guard.connect()

            # Get system state
            system_state = self.get_system_state()
            defcon_level = system_state['defcon']['level']
            exec_mode = system_state['mode']['mode']

            self.logger.info(f"DEFCON: {defcon_level} | Mode: {exec_mode}")

            # Check for BLACK DEFCON
            if defcon_level == 'BLACK':
                self.logger.error("DEFCON BLACK: Complete halt. CEO-only manual override required.")
                return {
                    'success': False,
                    'cycle_id': cycle_id,
                    'error': 'DEFCON_BLACK_HALT'
                }

            # Read tasks
            self.logger.info("Reading tasks from registry...")
            all_tasks = self.db.read_active_tasks()

            if function_filter:
                all_tasks = [t for t in all_tasks if t['task_name'] == function_filter]
                self.logger.info(f"Filtered to function: {function_filter}")

            # Filter by DEFCON
            tasks = self.router.filter_tasks(all_tasks)
            self.logger.info(f"Tasks after DEFCON filter: {len(tasks)}/{len(all_tasks)}")

            if not tasks:
                self.logger.warning("No tasks to execute!")
                return {
                    'success': True,
                    'cycle_id': cycle_id,
                    'tasks_executed': 0,
                    'message': 'No tasks found'
                }

            # Log cycle start
            if not self.dry_run:
                self.db.log_cycle_start(
                    cycle_id, hash_chain_id, tasks, defcon_level, exec_mode
                )

            # Execute tasks
            results = []
            for i, task in enumerate(tasks, 1):
                self.logger.info(f"\n[{i}/{len(tasks)}] {task['task_name']}")

                result = self.executor.execute_function(task, dry_run=self.dry_run)
                results.append(result)

                if result.get('skipped'):
                    self.logger.warning(f"  SKIPPED: {result.get('skip_reason')} - {result.get('error')}")
                elif result['success']:
                    self.logger.info(f"  SUCCESS ({result.get('execution_time_seconds', 0):.1f}s)")
                else:
                    self.logger.error(f"  FAILED: {result.get('error')}")
                    if result.get('stderr'):
                        self.logger.error(f"  Stderr: {result['stderr'][:200]}")

            # Determine cycle status
            successes = sum(1 for r in results if r.get('success') and not r.get('dry_run'))
            failures = sum(1 for r in results if not r.get('success') and not r.get('skipped'))
            skipped = sum(1 for r in results if r.get('skipped'))

            if failures == 0:
                cycle_status = 'COMPLETED'
            elif successes > 0:
                cycle_status = 'COMPLETED_WITH_FAILURES'
            else:
                cycle_status = 'FAILED'

            # Get vendor snapshot
            vendor_snapshot = {}
            try:
                vendor_snapshot = {
                    v['vendor']: {
                        'usage': v['usage'],
                        'ceiling': v['ceiling'],
                        'status': v['status']
                    }
                    for v in self.vendor_guard.get_quota_summary()
                }
            except Exception as e:
                self.logger.warning(f"Failed to get vendor snapshot: {e}")

            # Log cycle completion
            if not self.dry_run:
                self.db.log_cycle_complete(
                    cycle_id, hash_chain_id, results, cycle_status, vendor_snapshot
                )

                # Write heartbeat
                self.db.write_heartbeat(cycle_id, 'HEALTHY', {
                    'cycle_id': cycle_id,
                    'cycle_count': self.cycle_count,
                    'defcon': defcon_level,
                    'mode': exec_mode,
                    'tasks': len(tasks),
                    'successes': successes,
                    'failures': failures,
                    'skipped': skipped
                })

                # Write evidence
                self._write_evidence(cycle_id, results, system_state, vendor_snapshot)

            # Summary
            self.logger.info("\n" + "=" * 70)
            self.logger.info(f"CYCLE {cycle_status}")
            self.logger.info(f"  Tasks: {len(results)} | Success: {successes} | Failed: {failures} | Skipped: {skipped}")
            self.logger.info("=" * 70)

            return {
                'success': failures == 0,
                'cycle_id': cycle_id,
                'hash_chain_id': hash_chain_id,
                'cycle_status': cycle_status,
                'tasks_executed': len(results),
                'successes': successes,
                'failures': failures,
                'skipped': skipped,
                'results': results
            }

        except Exception as e:
            self.logger.error(f"Orchestrator cycle failed: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'cycle_id': cycle_id,
                'error': str(e)
            }

        finally:
            self.db.close()
            self.vendor_guard.close()

    def _write_evidence(
        self,
        cycle_id: str,
        results: List[Dict],
        system_state: Dict,
        vendor_snapshot: Dict
    ) -> None:
        """Write evidence bundle for VEGA audit"""
        try:
            evidence_dir = IoS014Config.get_evidence_dir()
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"IOS014_CYCLE_{timestamp}.json"

            evidence = {
                'cycle_id': cycle_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'orchestrator_version': IoS014Config.ORCHESTRATOR_VERSION,
                'system_state': system_state,
                'vendor_snapshot': vendor_snapshot,
                'execution_results': results,
                'summary': {
                    'total_tasks': len(results),
                    'successes': sum(1 for r in results if r.get('success')),
                    'failures': sum(1 for r in results if not r.get('success') and not r.get('skipped')),
                    'skipped': sum(1 for r in results if r.get('skipped'))
                }
            }

            evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
            evidence['evidence_hash'] = evidence_hash

            filepath = evidence_dir / filename
            with open(filepath, 'w') as f:
                json.dump(evidence, f, indent=2, default=str)

            self.logger.info(f"Evidence written: {filename}")

        except Exception as e:
            self.logger.warning(f"Failed to write evidence: {e}")

    def run_continuous(self, function_filter: Optional[str] = None, interval: Optional[int] = None):
        """Run orchestrator in continuous autonomous mode"""

        interval = interval or IoS014Config.DEFAULT_CYCLE_INTERVAL

        self.logger.info("=" * 70)
        self.logger.info("IoS-014 CONTINUOUS AUTONOMOUS MODE")
        self.logger.info(f"Interval: {interval} seconds")
        self.logger.info("Press Ctrl+C to stop")
        self.logger.info("=" * 70)

        try:
            while True:
                result = self.run_cycle(function_filter=function_filter)

                if not result['success']:
                    self.logger.warning("Cycle had issues, but continuing autonomous operation...")

                # Calculate next run time
                next_run = datetime.now(timezone.utc) + timedelta(seconds=interval)
                self.logger.info(f"\nNext cycle at: {next_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                self.logger.info(f"Waiting {interval} seconds...")

                time.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info("\n" + "=" * 70)
            self.logger.info("Received shutdown signal")
            self.logger.info(f"Total cycles executed: {self.cycle_count}")
            self.logger.info(f"Uptime: {datetime.now(timezone.utc) - self.start_time}")
            self.logger.info("=" * 70)

    def cleanup(self):
        """Clean up resources"""
        self.db.close()
        self.vendor_guard.close()
        self.router.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(
        description='IoS-014 Autonomous Task Orchestration Engine'
    )
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Run continuously in autonomous mode'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show execution plan without running functions'
    )
    parser.add_argument(
        '--function',
        type=str,
        help='Execute specific function only'
    )
    parser.add_argument(
        '--interval',
        type=int,
        help=f'Interval in seconds for continuous mode (default: {IoS014Config.DEFAULT_CYCLE_INTERVAL})'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show current system status and exit'
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging()

    # Create orchestrator
    orchestrator = IoS014Orchestrator(logger, dry_run=args.dry_run)

    try:
        if args.status:
            orchestrator.show_status()
        elif args.continuous:
            orchestrator.run_continuous(
                function_filter=args.function,
                interval=args.interval
            )
        else:
            result = orchestrator.run_cycle(function_filter=args.function)
            sys.exit(0 if result['success'] else 1)

    finally:
        orchestrator.cleanup()


if __name__ == '__main__':
    main()
