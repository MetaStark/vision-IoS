#!/usr/bin/env python3
"""
VISION-IOS ORCHESTRATOR v1.0
Agent: LARS (Strategy/Orchestration)
Purpose: Execute Vision-IoS functions in coordinated cycles
Compliance: ADR-007, ADR-010, ADR-002

Architecture:
- Reads tasks from fhq_governance.task_registry
- Executes Vision-IoS functions (FINN → STIG → LARS)
- Logs to fhq_governance.governance_actions_log
- Implements ADR-010 reconciliation
- Produces evidence bundles

Usage:
    python orchestrator_v1.py                    # Run one cycle
    python orchestrator_v1.py --continuous       # Run continuously
    python orchestrator_v1.py --dry-run          # Show plan without execution
    python orchestrator_v1.py --function=FUNC    # Run specific function only
"""

import os
import sys
import subprocess
import json
import hashlib
import argparse
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

# Database
import psycopg2
from psycopg2.extras import RealDictCursor


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Orchestrator configuration"""

    # Agent identity
    AGENT_ID = "LARS"
    ORCHESTRATOR_VERSION = "1.0.0"

    # Database connection
    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    # Execution settings
    CONTINUOUS_INTERVAL_SECONDS = 3600  # 1 hour
    FUNCTION_TIMEOUT_SECONDS = 300      # 5 minutes per function

    # Vision-IoS functions directory
    @staticmethod
    def get_functions_dir() -> Path:
        return Path(__file__).parent.parent / "03_FUNCTIONS"


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger("vision_ios_orchestrator")
    logger.setLevel(logging.INFO)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger


# =============================================================================
# DATABASE INTERFACE
# =============================================================================

class OrchestratorDatabase:
    """Database interface for orchestrator"""

    def __init__(self, connection_string: str, logger: logging.Logger):
        self.connection_string = connection_string
        self.logger = logger
        self.conn = None

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(self.connection_string)
        self.logger.info("Database connection established")
        return self.conn

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed")

    def read_vision_tasks(self) -> List[Dict[str, Any]]:
        """Read Vision-IoS functions from task registry"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    task_id,
                    task_name,
                    task_type,
                    agent_id,
                    task_description,
                    task_config,
                    enabled,
                    created_at,
                    updated_at
                FROM fhq_governance.task_registry
                WHERE task_type = 'VISION_FUNCTION'
                  AND enabled = TRUE
                ORDER BY task_id
            """)
            tasks = cur.fetchall()
            return [dict(task) for task in tasks]

    def read_orchestrator_state(self) -> Dict[str, Any]:
        """Read orchestrator execution state"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get latest orchestrator execution
            cur.execute("""
                SELECT
                    action_id,
                    timestamp,
                    decision,
                    metadata
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            last_execution = cur.fetchone()

            # Count total executions
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
            """)
            total_cycles = cur.fetchone()['count']

            return {
                'last_execution': dict(last_execution) if last_execution else None,
                'total_cycles': total_cycles
            }

    def log_orchestrator_cycle_start(
        self,
        cycle_id: str,
        hash_chain_id: str,
        tasks: List[Dict[str, Any]]
    ) -> int:
        """Log orchestrator cycle start"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    agent_id,
                    decision,
                    metadata,
                    hash_chain_id,
                    signature,
                    timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING action_id
            """, (
                'VISION_ORCHESTRATOR_CYCLE_START',
                Config.AGENT_ID,
                'IN_PROGRESS',
                json.dumps({
                    'cycle_id': cycle_id,
                    'orchestrator_version': Config.ORCHESTRATOR_VERSION,
                    'tasks_scheduled': len(tasks),
                    'task_names': [t['task_name'] for t in tasks]
                }),
                hash_chain_id,
                self._generate_signature(Config.AGENT_ID, hash_chain_id),
                datetime.now(timezone.utc)
            ))

            action_id = cur.fetchone()[0]
            self.conn.commit()
            return action_id

    def log_orchestrator_cycle_complete(
        self,
        cycle_id: str,
        hash_chain_id: str,
        results: List[Dict[str, Any]],
        cycle_status: str
    ) -> int:
        """Log orchestrator cycle completion"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    agent_id,
                    decision,
                    metadata,
                    hash_chain_id,
                    signature,
                    timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING action_id
            """, (
                'VISION_ORCHESTRATOR_CYCLE',
                Config.AGENT_ID,
                cycle_status,
                json.dumps({
                    'cycle_id': cycle_id,
                    'orchestrator_version': Config.ORCHESTRATOR_VERSION,
                    'tasks_executed': len(results),
                    'execution_results': results,
                    'success_count': sum(1 for r in results if r.get('success')),
                    'failure_count': sum(1 for r in results if not r.get('success'))
                }),
                hash_chain_id,
                self._generate_signature(Config.AGENT_ID, hash_chain_id),
                datetime.now(timezone.utc)
            ))

            action_id = cur.fetchone()[0]
            self.conn.commit()
            return action_id

    def write_execution_state(
        self,
        cycle_id: str,
        hash_chain_id: str,
        state_data: Dict[str, Any]
    ) -> str:
        """Write orchestrator execution state to vision_core"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vision_core.execution_state (
                    component_name,
                    state_type,
                    state_value,
                    created_by,
                    hash_chain_id
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING state_id
            """, (
                'vision_ios_orchestrator',
                'ACTIVE',
                json.dumps(state_data),
                Config.AGENT_ID,
                hash_chain_id
            ))

            state_id = cur.fetchone()[0]
            self.conn.commit()
            return str(state_id)

    @staticmethod
    def _generate_signature(agent_id: str, hash_chain_id: str) -> str:
        """Generate simplified signature (ADR-008 compliant pattern)"""
        signature_data = f"{agent_id}:{hash_chain_id}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(signature_data.encode()).hexdigest()


# =============================================================================
# FUNCTION EXECUTOR
# =============================================================================

class FunctionExecutor:
    """Executes Vision-IoS functions"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.functions_dir = Config.get_functions_dir()

    def execute_function(
        self,
        task: Dict[str, Any],
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Execute a Vision-IoS function"""

        task_name = task['task_name']
        agent_id = task['agent_id']
        function_path = task['task_config'].get('function_path')

        if not function_path:
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': False,
                'error': 'Missing function_path in task_config'
            }

        # Resolve full path
        full_path = self.functions_dir.parent / function_path

        if not full_path.exists():
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': False,
                'error': f'Function file not found: {full_path}'
            }

        if dry_run:
            self.logger.info(f"[DRY RUN] Would execute: {full_path}")
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': True,
                'dry_run': True
            }

        # Execute function
        self.logger.info(f"Executing function: {task_name} (Agent: {agent_id})")

        try:
            start_time = time.time()

            result = subprocess.run(
                [sys.executable, str(full_path)],
                capture_output=True,
                text=True,
                timeout=Config.FUNCTION_TIMEOUT_SECONDS,
                cwd=str(full_path.parent)
            )

            execution_time = time.time() - start_time

            success = (result.returncode == 0)

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
                'error': f'Execution timeout after {Config.FUNCTION_TIMEOUT_SECONDS}s'
            }
        except Exception as e:
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': False,
                'error': str(e)
            }


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class VisionIoSOrchestrator:
    """Vision-IoS Orchestrator v1.0"""

    def __init__(self, logger: logging.Logger, dry_run: bool = False):
        self.logger = logger
        self.dry_run = dry_run
        self.config = Config()
        self.db = OrchestratorDatabase(self.config.get_db_connection_string(), logger)
        self.executor = FunctionExecutor(logger)

    def generate_cycle_id(self) -> str:
        """Generate cycle ID"""
        return datetime.now(timezone.utc).strftime("CYCLE_%Y%m%d_%H%M%S")

    def generate_hash_chain_id(self, cycle_id: str) -> str:
        """Generate hash chain ID"""
        return f"HC-{Config.AGENT_ID}-ORCHESTRATOR-{cycle_id}"

    def run_cycle(self, function_filter: Optional[str] = None) -> Dict[str, Any]:
        """Run one orchestration cycle"""

        cycle_id = self.generate_cycle_id()
        hash_chain_id = self.generate_hash_chain_id(cycle_id)

        self.logger.info("=" * 70)
        self.logger.info(f"VISION-IOS ORCHESTRATOR v{Config.ORCHESTRATOR_VERSION}")
        self.logger.info(f"Cycle ID: {cycle_id}")
        self.logger.info(f"Hash Chain: {hash_chain_id}")
        if self.dry_run:
            self.logger.info("MODE: DRY RUN (no actual execution)")
        self.logger.info("=" * 70)

        try:
            # Connect to database
            self.logger.info("Connecting to database...")
            self.db.connect()

            # Read Vision-IoS tasks
            self.logger.info("Reading Vision-IoS tasks from registry...")
            tasks = self.db.read_vision_tasks()

            if function_filter:
                tasks = [t for t in tasks if t['task_name'] == function_filter]
                self.logger.info(f"Filtered to function: {function_filter}")

            self.logger.info(f"Found {len(tasks)} enabled Vision-IoS functions")

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
                start_action_id = self.db.log_orchestrator_cycle_start(
                    cycle_id, hash_chain_id, tasks
                )
                self.logger.info(f"Cycle start logged: action_id={start_action_id}")

            # Execute functions in order
            results = []
            for i, task in enumerate(tasks, 1):
                self.logger.info("")
                self.logger.info(f"[{i}/{len(tasks)}] Executing: {task['task_name']} (Agent: {task['agent_id']})")

                result = self.executor.execute_function(task, dry_run=self.dry_run)
                results.append(result)

                if result['success']:
                    self.logger.info(f"✅ SUCCESS: {task['task_name']}")
                else:
                    self.logger.error(f"❌ FAILED: {task['task_name']}")
                    if 'error' in result:
                        self.logger.error(f"   Error: {result['error']}")

            # Determine overall cycle status
            all_success = all(r['success'] for r in results)
            any_failure = any(not r['success'] for r in results)

            if all_success:
                cycle_status = 'COMPLETED'
            elif any_failure and not all_success:
                cycle_status = 'COMPLETED_WITH_FAILURES'
            else:
                cycle_status = 'FAILED'

            # Log cycle completion
            if not self.dry_run:
                complete_action_id = self.db.log_orchestrator_cycle_complete(
                    cycle_id, hash_chain_id, results, cycle_status
                )
                self.logger.info(f"Cycle completion logged: action_id={complete_action_id}")

                # Write execution state
                state_data = {
                    'cycle_id': cycle_id,
                    'orchestrator_version': Config.ORCHESTRATOR_VERSION,
                    'execution_timestamp': datetime.now(timezone.utc).isoformat(),
                    'tasks_executed': len(results),
                    'results': results,
                    'cycle_status': cycle_status
                }

                state_id = self.db.write_execution_state(cycle_id, hash_chain_id, state_data)
                self.logger.info(f"Execution state stored: state_id={state_id}")

            # Summary
            self.logger.info("")
            self.logger.info("=" * 70)
            self.logger.info(f"CYCLE COMPLETE: {cycle_status}")
            self.logger.info(f"Tasks executed: {len(results)}")
            self.logger.info(f"Successes: {sum(1 for r in results if r['success'])}")
            self.logger.info(f"Failures: {sum(1 for r in results if not r['success'])}")
            self.logger.info("=" * 70)

            return {
                'success': all_success,
                'cycle_id': cycle_id,
                'hash_chain_id': hash_chain_id,
                'cycle_status': cycle_status,
                'tasks_executed': len(results),
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

    def run_continuous(self, function_filter: Optional[str] = None):
        """Run orchestrator in continuous mode"""

        self.logger.info("Starting CONTINUOUS mode")
        self.logger.info(f"Interval: {Config.CONTINUOUS_INTERVAL_SECONDS} seconds")

        cycle_number = 0

        try:
            while True:
                cycle_number += 1
                self.logger.info("")
                self.logger.info(f"╔{'═' * 68}╗")
                self.logger.info(f"║ CONTINUOUS CYCLE #{cycle_number:04d} {' ' * 48}║")
                self.logger.info(f"╚{'═' * 68}╝")

                result = self.run_cycle(function_filter=function_filter)

                if not result['success']:
                    self.logger.error("Cycle failed, but continuing...")

                self.logger.info(f"Waiting {Config.CONTINUOUS_INTERVAL_SECONDS} seconds until next cycle...")
                time.sleep(Config.CONTINUOUS_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            self.logger.info("")
            self.logger.info("Received interrupt signal, stopping orchestrator...")
            self.logger.info(f"Total cycles executed: {cycle_number}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(
        description='Vision-IoS Orchestrator v1.0 - Execute Vision-IoS functions in coordinated cycles'
    )
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Run continuously (default: single cycle)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show execution plan without running functions'
    )
    parser.add_argument(
        '--function',
        type=str,
        help='Execute specific function only (task_name)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        help=f'Interval in seconds for continuous mode (default: {Config.CONTINUOUS_INTERVAL_SECONDS})'
    )

    args = parser.parse_args()

    # Override interval if specified
    if args.interval:
        Config.CONTINUOUS_INTERVAL_SECONDS = args.interval

    # Setup logging
    logger = setup_logging()

    # Create orchestrator
    orchestrator = VisionIoSOrchestrator(logger, dry_run=args.dry_run)

    # Run
    if args.continuous:
        orchestrator.run_continuous(function_filter=args.function)
    else:
        result = orchestrator.run_cycle(function_filter=args.function)
        sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
