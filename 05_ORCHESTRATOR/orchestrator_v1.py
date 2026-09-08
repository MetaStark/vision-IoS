#!/usr/bin/env python3
"""
VISION-IOS ORCHESTRATOR v1.1
Agent: LARS (Strategy/Orchestration)
Purpose: Execute Vision-IoS functions in coordinated cycles
Compliance: ADR-007, ADR-010, ADR-002, ADR-017, CEO-DIR-2026-009-B

Architecture:
- Reads tasks from fhq_governance.task_registry
- Executes Vision-IoS functions (FINN -> STIG -> LARS)
- Logs to fhq_governance.governance_actions_log
- Implements ADR-010 reconciliation
- Produces evidence bundles
- CNRP-001: Cognitive Node Refresh Protocol (CEO-DIR-2026-009-B)

CNRP Integration (v1.1):
- 4-hour CNRP cycles: R1 -> R2 -> R3 -> R4 causal chain
- 15-minute R4 standalone integrity monitoring
- Orchestrator-native execution (ADR-017 compliant)
- Windows Scheduler is watchdog only, not executor

CEO Position: "Clocks trigger. Brainstems decide."

Usage:
    python orchestrator_v1.py                    # Run one cycle
    python orchestrator_v1.py --continuous       # Run continuously
    python orchestrator_v1.py --dry-run          # Show plan without execution
    python orchestrator_v1.py --function=FUNC    # Run specific function only
    python orchestrator_v1.py --cnrp-cycle       # Run CNRP R1-R4 chain
    python orchestrator_v1.py --cnrp-r4          # Run R4 integrity monitor only
    python orchestrator_v1.py --cnrp-continuous  # Run with CNRP scheduling
    python orchestrator_v1.py --healthcheck      # Health check for watchdog
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
    ORCHESTRATOR_VERSION = "1.1.0"

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

    # CEO-DIR-2026-042: Tasks that are long-running daemons (should run as services, not scheduled)
    # These have while True loops and are designed to run continuously
    CONTINUOUS_DAEMON_TASKS = {
        'g2c_continuous_forecast_engine',   # Continuous forecasting daemon
        'ios003b_intraday_regime_delta',    # Intraday regime monitoring (15-min intervals)
        'wave15_autonomous_hunter',         # Autonomous hunting daemon
        'wave17c_promotion_daemon',         # Promotion evaluation daemon
    }

    # CEO-DIR-2026-046: Critical tasks that MUST NEVER be skipped or classified as daemon
    # These maintain system reality awareness - skipping them = EPISTEMICALLY_BLIND state
    PROTECTED_REGIME_TASKS = {
        'ios003_daily_regime_update_v4',    # Primary regime belief state update
        'ios003_regime_freshness_sentinel', # Regime staleness monitor
    }

    # CEO-DIR-2026-047: REGIME AS A MANDATORY SYSTEM CLOCK
    # Regime is the system clock - ACI may not exist in time without fresh regime
    REGIME_CLOCK_INTERVAL_HOURS = 3       # Regime must refresh every 3 hours
    REGIME_CLOCK_GRACE_HOURS = 1          # 1 hour grace period
    REGIME_CLOCK_MAX_HOURS = 4            # 3h interval + 1h grace = 4h max
    REGIME_CLOCK_RETRY_ATTEMPTS = 3       # Self-healing: 3 retry attempts
    REGIME_CLOCK_RETRY_BACKOFF = [30, 60, 120]  # Exponential backoff (seconds)
    REGIME_FIRST_TASK = 'ios003_daily_regime_update_v4'  # Must run FIRST in every cycle

    # CEO-DIR-2026-043: Orchestrator Stability & Regression Lock
    # SLA Guard: If no cycles in 2× interval → automatic DATA_BLACKOUT
    CYCLE_SLA_MULTIPLIER = 2  # Trigger blackout if no cycles in 2× CONTINUOUS_INTERVAL_SECONDS

    # CNRP-001 Configuration (CEO-DIR-2026-009-B)
    # CEO-DIR-2026-024: 10-minute probe cycle for continuous perception
    CNRP_CYCLE_INTERVAL_SECONDS = 14400  # 4 hours
    CNRP_R4_INTERVAL_SECONDS = 600       # 10 minutes (CEO-DIR-2026-024)
    CNRP_CHAIN_DELAY_SECONDS = {
        'R1_TO_R2': 300,   # 5 minutes
        'R2_TO_R3': 120,   # 2 minutes
        'R3_TO_R4': 60     # 1 minute
    }

    # CNRP Daemon Paths (relative to functions dir)
    CNRP_DAEMONS = {
        'R1': 'ceio_evidence_refresh_daemon.py',
        'R2': 'crio_alpha_graph_rebuild.py',
        'R3': 'cdmo_data_hygiene_attestation.py',
        'R4': 'vega_epistemic_integrity_monitor.py'
    }

    # CEO-DIR-2026-040: IOS-TRUTH-LOOP Cadence Configuration
    # Default: 2-hour baseline cadence (can be escalated to 1h or 30m)
    TRUTH_LOOP_INTERVAL_SECONDS = 7200  # 2 hours baseline
    TRUTH_LOOP_TASK_PATH = 'tasks/ios_truth_snapshot_engine.py'

    # CEO-DIR-2026-042: Heartbeat Configuration
    # Orchestrator publishes heartbeat every 60 seconds to prove liveness
    HEARTBEAT_INTERVAL_SECONDS = 60  # 1 minute heartbeat interval

    # CEO-DIR-2026-045: DEFCON Live Evaluation
    # Evaluate and update DEFCON state every 5 minutes to keep it fresh
    DEFCON_EVAL_INTERVAL_SECONDS = 300  # 5 minutes
    DEFCON_EVALUATOR_PATH = 'defcon_live_evaluator.py'

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
                ORDER BY (task_config->>'priority')::int NULLS LAST, task_name
            """)
            tasks = cur.fetchall()
            return [dict(task) for task in tasks]

    def read_cognitive_queries(self) -> List[Dict[str, Any]]:
        """
        Read governed cognitive queries from cognitive_query_set.
        CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Section 8.5

        No hardcoded queries in code - all queries live in governance table.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if table exists first
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'fhq_governance'
                      AND table_name = 'cognitive_query_set'
                )
            """)
            if not cur.fetchone()['exists']:
                self.logger.info("cognitive_query_set table not found - skipping cognitive queries")
                return []

            cur.execute("""
                SELECT
                    query_id,
                    query_template,
                    query_type,
                    asset_scope
                FROM fhq_governance.cognitive_query_set
                WHERE enabled = TRUE
                ORDER BY query_type
            """)
            queries = cur.fetchall()
            return [dict(q) for q in queries]

    def get_current_regime(self) -> str:
        """Get current market regime from regime_state."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT current_regime
                FROM fhq_meta.regime_state
                ORDER BY last_updated_at DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            return row['current_regime'] if row else 'UNKNOWN'

    def get_current_defcon(self) -> str:
        """Get current DEFCON level (placeholder - actual logic TBD)."""
        # For now, default to YELLOW for cognitive operations
        return 'YELLOW'

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

    # =========================================================================
    # CEO-DIR-2026-043: Orchestrator Stability & Regression Lock
    # =========================================================================

    def check_cycle_sla(self) -> tuple:
        """
        Check if orchestrator cycle SLA is met.
        If no cycles in 2× CONTINUOUS_INTERVAL_SECONDS, trigger DATA_BLACKOUT.

        Returns (sla_met: bool, cycles_found: int, max_allowed_gap_seconds: int)

        Special case: If NO cycles exist at all (bootstrap), SLA is considered met
        to allow initial startup. SLA violation only applies when cycles existed
        but then stopped.
        """
        max_gap_seconds = Config.CONTINUOUS_INTERVAL_SECONDS * Config.CYCLE_SLA_MULTIPLIER

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check governance_actions_log for VISION_ORCHESTRATOR_CYCLE entries
            # (this is where orchestrator actually logs cycles)
            cur.execute("""
                SELECT COUNT(*) as total_cycles
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
            """)
            total_result = cur.fetchone()
            total_cycles = total_result['total_cycles'] if total_result else 0

            # Bootstrap case: no cycles ever = allow startup
            if total_cycles == 0:
                return (True, 0, max_gap_seconds)

            # Check recent cycles within SLA window
            cur.execute("""
                SELECT COUNT(*) as cycle_count
                FROM fhq_governance.governance_actions_log
                WHERE action_type = 'VISION_ORCHESTRATOR_CYCLE'
                  AND timestamp > NOW() - INTERVAL '%s seconds'
            """, (max_gap_seconds,))
            result = cur.fetchone()
            cycles_found = result['cycle_count'] if result else 0

        sla_met = cycles_found > 0
        return (sla_met, cycles_found, max_gap_seconds)

    def trigger_data_blackout(self, reason: str) -> str:
        """
        Trigger DATA_BLACKOUT state per CEO-DIR-2026-043.
        Returns blackout_id.
        """
        with self.conn.cursor() as cur:
            # Use correct column names per actual schema
            cur.execute("""
                INSERT INTO fhq_governance.data_blackout_state (
                    trigger_reason,
                    triggered_by,
                    triggered_at,
                    is_active
                ) VALUES (%s, %s, NOW(), TRUE)
                RETURNING blackout_id
            """, (
                f"ORCHESTRATOR_SLA_VIOLATION: {reason}",
                Config.AGENT_ID
            ))
            result = cur.fetchone()
            self.conn.commit()
            return str(result[0]) if result else None

    def check_daemon_task_violations(self) -> list:
        """
        CEO-DIR-2026-043 Section 2.2: Task Classification Invariant
        Check if any CONTINUOUS_DAEMON_TASKS appeared in execution logs.
        Any appearance = P0 incident.

        Returns list of violations found.
        """
        daemon_tasks = list(Config.CONTINUOUS_DAEMON_TASKS)
        if not daemon_tasks:
            return []

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check for daemon tasks in recent execution logs
            cur.execute("""
                SELECT DISTINCT
                    metadata->>'task_name' as task_name,
                    timestamp,
                    action_id
                FROM fhq_governance.governance_actions_log
                WHERE action_type IN ('VISION_FUNCTION_EXECUTION', 'VISION_ORCHESTRATOR_CYCLE')
                  AND metadata->>'task_name' = ANY(%s)
                  AND timestamp > NOW() - INTERVAL '24 hours'
                  AND (metadata->>'skipped')::boolean IS NOT TRUE
                ORDER BY timestamp DESC
            """, (daemon_tasks,))
            violations = [dict(row) for row in cur.fetchall()]

        return violations

    def log_p0_incident(self, incident_type: str, details: dict) -> str:
        """Log a P0 incident for governance violations."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_governance.governance_actions_log (
                    action_type,
                    agent_id,
                    decision,
                    metadata,
                    timestamp
                ) VALUES (%s, %s, %s, %s, NOW())
                RETURNING action_id
            """, (
                'P0_INCIDENT',
                Config.AGENT_ID,
                'VIOLATION_DETECTED',
                json.dumps({
                    'incident_type': incident_type,
                    'severity': 'P0',
                    'directive': 'CEO-DIR-2026-043',
                    'details': details
                })
            ))
            result = cur.fetchone()
            self.conn.commit()
            return str(result[0]) if result else None

    def check_regime_freshness(self, max_age_hours: int = 6) -> tuple:
        """
        CEO-DIR-2026-046: Regime Continuity Invariant (RCI)
        Check if regime belief state is within freshness SLA.

        Returns (is_fresh: bool, regime_state: str, staleness_hours: float)
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM fhq_governance.check_regime_freshness(%s)
            """, (max_age_hours,))
            result = cur.fetchone()

            if result:
                return (
                    result['is_fresh'],
                    result['regime_state'],
                    float(result['staleness_hours']) if result['staleness_hours'] else 0.0
                )
            # No regime data at all - not fresh
            return (False, 'NO_REGIME_DATA', 9999.0)

    def trigger_regime_blackout(self, staleness_hours: float) -> str:
        """
        CEO-DIR-2026-046: Trigger DATA_BLACKOUT for regime staleness.
        Returns blackout_id.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT fhq_governance.trigger_regime_blackout(%s, %s)
            """, (staleness_hours, Config.AGENT_ID))
            result = cur.fetchone()
            self.conn.commit()
            return str(result[0]) if result else None

    def check_regime_clock(self) -> tuple:
        """
        CEO-DIR-2026-047: Check regime clock status.
        Regime must refresh every 3h (+1h grace = 4h max).

        Returns (clock_running: bool, last_refresh: datetime, hours_since: float, status: str)
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM fhq_governance.check_regime_clock()")
            result = cur.fetchone()

            if result:
                return (
                    result['clock_running'],
                    result['last_refresh'],
                    float(result['hours_since_refresh']) if result['hours_since_refresh'] else 9999.0,
                    result['status']
                )
            return (False, None, 9999.0, 'NO_REGIME_DATA')

    def trigger_regime_clock_blackout(self, hours_since_refresh: float) -> str:
        """
        CEO-DIR-2026-047: Trigger REGIME_CLOCK_STOPPED blackout.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT fhq_governance.trigger_regime_clock_blackout(%s, %s)
            """, (hours_since_refresh, Config.AGENT_ID))
            result = cur.fetchone()
            self.conn.commit()
            return str(result[0]) if result else None


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
        task_config = task['task_config']

        # CEO-DIR-2026-046: Protected regime tasks MUST NEVER be skipped
        # These maintain system reality awareness
        if task_name in Config.PROTECTED_REGIME_TASKS:
            self.logger.info(f"[PROTECTED] {task_name} is a protected regime task - MUST execute")
            # Fall through to execution - never skip

        # CEO-DIR-2026-042: Skip continuous/daemon tasks - they should run as persistent services
        # Not suitable for orchestrator's timeout-limited execution model
        # CEO-DIR-2026-046: But never skip protected regime tasks
        is_continuous = (
            (task_config.get('continuous', False) or task_name in Config.CONTINUOUS_DAEMON_TASKS)
            and task_name not in Config.PROTECTED_REGIME_TASKS
        )
        if is_continuous:
            self.logger.info(f"[SKIP] {task_name} is a continuous daemon - requires service mode")
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': True,
                'skipped': True,
                'reason': 'Continuous daemon task - requires service mode (systemd/pm2)'
            }

        # Support both function_path and script fields (CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001)
        # CEO-DIR-2026-041: Fixed double path bug - normalize all path patterns
        function_path = task_config.get('function_path')
        if not function_path:
            # Fall back to script field (legacy task configs)
            script = task_config.get('script')
            if script:
                # CEO-DIR-2026-041: Only prepend 03_FUNCTIONS if not already present
                if script.startswith('03_FUNCTIONS/') or script.startswith('03_FUNCTIONS\\'):
                    function_path = script
                else:
                    function_path = f"03_FUNCTIONS/{script}"

        if not function_path:
            return {
                'task_name': task_name,
                'agent_id': agent_id,
                'success': False,
                'error': 'Missing function_path or script in task_config'
            }

        # Resolve full path - handle both absolute and relative paths
        # CEO-DIR-2026-041: Normalize path handling to prevent double path segments
        if os.path.isabs(function_path):
            full_path = Path(function_path)
        else:
            # Strip leading 03_FUNCTIONS if present, then use functions_dir directly
            normalized_path = function_path
            if normalized_path.startswith('03_FUNCTIONS/') or normalized_path.startswith('03_FUNCTIONS\\'):
                normalized_path = normalized_path.replace('03_FUNCTIONS/', '').replace('03_FUNCTIONS\\', '')
            full_path = self.functions_dir / normalized_path

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
# CNRP EXECUTOR (CEO-DIR-2026-009-B)
# =============================================================================

class CNRPExecutor:
    """
    CNRP-001 Chain Executor
    CEO Directive: CEO-DIR-2026-009-B

    Executes CNRP causal chain: R1 -> R2 -> R3 -> R4
    ADR-017 Compliant: All cognition through orchestrator
    """

    # Gate levels for authorization
    GATE_LEVELS = {
        'R1': 'G2',
        'R2': 'G3',
        'R3': 'G3',
        'R4': 'G1'
    }

    # Authorities per phase
    AUTHORITIES = {
        'R1': 'CEIO',
        'R2': 'CRIO',
        'R3': 'CDMO',
        'R4': 'VEGA'
    }

    def __init__(self, db: 'OrchestratorDatabase', logger: logging.Logger):
        self.db = db
        self.logger = logger
        self.functions_dir = Config.get_functions_dir()

    def check_gate_authorization(self, phase: str) -> tuple:
        """Check if phase is authorized to execute based on gate level"""
        gate = self.GATE_LEVELS.get(phase, 'G4')

        with self.db.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check DEFCON level
            try:
                cur.execute("""
                    SELECT current_level
                    FROM fhq_governance.defcon_status
                    ORDER BY changed_at DESC
                    LIMIT 1
                """)
                defcon = cur.fetchone()
                if defcon and defcon['current_level'] in ('RED', 'BLACK'):
                    return False, f"DEFCON {defcon['current_level']} blocks execution"
            except Exception:
                pass  # Table may not exist

        return True, "Authorized"

    def execute_daemon(self, phase: str, dry_run: bool = False) -> Dict[str, Any]:
        """Execute a CNRP daemon"""
        daemon_name = Config.CNRP_DAEMONS.get(phase)
        if not daemon_name:
            return {'success': False, 'error': f'Unknown phase: {phase}'}

        daemon_path = self.functions_dir / daemon_name

        if not daemon_path.exists():
            return {'success': False, 'error': f'Daemon not found: {daemon_path}'}

        if dry_run:
            self.logger.info(f"[DRY RUN] Would execute {phase}: {daemon_name}")
            return {'success': True, 'dry_run': True, 'phase': phase}

        self.logger.info(f"Executing {phase}: {daemon_name}")

        try:
            start_time = time.time()

            result = subprocess.run(
                [sys.executable, str(daemon_path)],
                capture_output=True,
                text=True,
                timeout=Config.FUNCTION_TIMEOUT_SECONDS,
                cwd=str(daemon_path.parent)
            )

            execution_time = time.time() - start_time

            # Parse JSON output if possible
            try:
                output_data = json.loads(result.stdout) if result.stdout.strip() else {}
            except json.JSONDecodeError:
                output_data = {'raw_output': result.stdout[-500:]}

            success = result.returncode == 0 or result.returncode == 2  # 2 = violations detected but monitored

            return {
                'success': success,
                'phase': phase,
                'daemon': daemon_name,
                'exit_code': result.returncode,
                'execution_time': round(execution_time, 2),
                'output': output_data,
                'stderr': result.stderr[-300:] if result.stderr else None
            }

        except subprocess.TimeoutExpired:
            return {'success': False, 'phase': phase, 'error': 'Timeout'}
        except Exception as e:
            return {'success': False, 'phase': phase, 'error': str(e)}

    def log_cnrp_execution(self, cycle_id: str, phase: str, status: str,
                           result: Dict, authority: str, schedule_source: str = None):
        """Log CNRP execution to governance"""
        try:
            # Rollback any aborted transaction before logging
            try:
                self.db.conn.rollback()
            except Exception:
                pass  # Connection might be in autocommit mode

            with self.db.conn.cursor() as cur:
                metadata = {
                    'cycle_id': cycle_id,
                    'phase': phase,
                    'result_status': result.get('output', {}).get('status', 'UNKNOWN'),
                    'execution_time': result.get('execution_time'),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }

                # CEO-DIR-2026-024: Log R4 schedule source for metronome verification
                if phase == 'R4' and schedule_source:
                    metadata['r4_schedule_source'] = schedule_source

                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type,
                        action_target,
                        action_target_type,
                        initiated_by,
                        decision,
                        decision_rationale,
                        metadata
                    ) VALUES (
                        'CNRP_ORCHESTRATOR_EXECUTION',
                        %s,
                        'DAEMON_EXECUTION',
                        %s,
                        %s,
                        'CEO-DIR-2026-009-B: Orchestrator-native CNRP execution',
                        %s
                    )
                """, (
                    f"CNRP-{phase}",
                    authority,
                    status,
                    json.dumps(metadata, default=str)
                ))
                self.db.conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to log CNRP execution: {e}")
            # Try to rollback to clean up transaction state for next operation
            try:
                self.db.conn.rollback()
            except Exception:
                pass

    def run_chain(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute full CNRP causal chain: R1 -> R2 -> R3
        CEO-DIR-2026-024: R4 removed from chain (timer-only, 600s metronome)

        CEO Position: "Clocks trigger. Brainstems decide."
        This is the ONLY authorized way to run CNRP daemons.
        """
        cycle_id = f"CNRP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        self.logger.info("=" * 70)
        self.logger.info("CNRP-001 CAUSAL CHAIN EXECUTION")
        self.logger.info("Directive: CEO-DIR-2026-009-B")
        self.logger.info(f"Cycle: {cycle_id}")
        self.logger.info("=" * 70)

        chain_result = {
            'cycle_id': cycle_id,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'phases': {},
            'chain_status': 'SUCCESS'
        }

        # CEO-DIR-2026-024: R4 removed from chain, runs timer-only (600s metronome)
        phases = ['R1', 'R2', 'R3']
        delays = [0, Config.CNRP_CHAIN_DELAY_SECONDS['R1_TO_R2'],
                  Config.CNRP_CHAIN_DELAY_SECONDS['R2_TO_R3']]

        for i, phase in enumerate(phases):
            self.logger.info(f"\n--- Phase {phase} ({self.AUTHORITIES[phase]}) ---")

            # Check authorization
            authorized, reason = self.check_gate_authorization(phase)
            if not authorized:
                self.logger.error(f"Authorization failed: {reason}")
                chain_result['phases'][phase] = {'status': 'BLOCKED', 'reason': reason}
                chain_result['chain_status'] = 'HALTED'
                break

            # Apply delay (except for first phase)
            if i > 0 and delays[i] > 0 and not dry_run:
                self.logger.info(f"Waiting {delays[i]}s before {phase}...")
                time.sleep(delays[i])

            # Execute daemon
            result = self.execute_daemon(phase, dry_run=dry_run)
            chain_result['phases'][phase] = result

            # Log execution
            if not dry_run:
                status = 'SUCCESS' if result['success'] else 'FAILED'
                self.log_cnrp_execution(cycle_id, phase, status,
                                        result, self.AUTHORITIES[phase])

            if result['success']:
                self.logger.info(f"Phase {phase}: SUCCESS")
            else:
                self.logger.error(f"Phase {phase}: FAILED - {result.get('error', 'Unknown')}")
                chain_result['chain_status'] = 'HALTED'
                break

        chain_result['completed_at'] = datetime.now(timezone.utc).isoformat()

        self.logger.info("\n" + "=" * 70)
        self.logger.info(f"Chain Status: {chain_result['chain_status']}")
        self.logger.info("=" * 70)

        return chain_result

    def run_r4_standalone(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute R4 integrity monitor standalone.
        CEO-DIR-2026-024: Timer-only R4 (600s metronome, not in chain).
        """
        self.logger.info("R4 Standalone Integrity Monitor")

        # Check authorization
        authorized, reason = self.check_gate_authorization('R4')
        if not authorized:
            return {'success': False, 'error': reason}

        result = self.execute_daemon('R4', dry_run=dry_run)

        if not dry_run:
            status = 'SUCCESS' if result['success'] else 'FAILED'
            self.log_cnrp_execution(
                f"R4-MONITOR-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
                'R4', status, result, 'VEGA', schedule_source='timer'
            )

        return result


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class VisionIoSOrchestrator:
    """Vision-IoS Orchestrator v1.1 (with CNRP Integration)"""

    def __init__(self, logger: logging.Logger, dry_run: bool = False):
        self.logger = logger
        self.dry_run = dry_run
        self.config = Config()
        self.db = OrchestratorDatabase(self.config.get_db_connection_string(), logger)
        self.executor = FunctionExecutor(logger)
        self.cnrp_executor = None  # Initialized when DB connected

    def generate_cycle_id(self) -> str:
        """Generate cycle ID"""
        return datetime.now(timezone.utc).strftime("CYCLE_%Y%m%d_%H%M%S")

    def publish_heartbeat(self, current_task: str = "CONTINUOUS_MODE", events_processed: int = 0) -> bool:
        """
        Publish orchestrator heartbeat to fhq_governance.agent_heartbeats.
        CEO-DIR-2026-042: Proves liveness, eliminates "orchestrator running" assumption.

        Args:
            current_task: Current task being executed
            events_processed: Number of events processed since start

        Returns:
            True if heartbeat published successfully
        """
        try:
            # Check if connection exists and is open (not just non-None)
            if not self.db.conn or self.db.conn.closed:
                self.db.connect()

            cursor = self.db.conn.cursor()

            # Upsert heartbeat for LARS (orchestrator agent)
            cursor.execute("""
                INSERT INTO fhq_governance.agent_heartbeats
                    (agent_id, component, current_task, health_score, events_processed, errors_count, last_heartbeat, created_at)
                VALUES
                    ('LARS', 'ORCHESTRATOR', %s, 1.0, %s, 0, NOW(), NOW())
                ON CONFLICT (agent_id) DO UPDATE SET
                    current_task = EXCLUDED.current_task,
                    health_score = 1.0,
                    events_processed = fhq_governance.agent_heartbeats.events_processed + 1,
                    last_heartbeat = NOW()
            """, (current_task, events_processed))

            self.db.conn.commit()
            return True

        except Exception as e:
            self.logger.warning(f"Failed to publish heartbeat: {e}")
            return False

    def run_cognitive_queries(self) -> List[Dict[str, Any]]:
        """
        Execute governed cognitive queries via FINN Cognitive Gateway.
        CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001 Section 8.5

        Pull-based orchestration: queries come from database, not code.
        """
        results = []

        try:
            # Read governed queries
            queries = self.db.read_cognitive_queries()

            if not queries:
                self.logger.info("No cognitive queries to execute")
                return results

            # Get current context
            current_regime = self.db.get_current_regime()
            current_defcon = self.db.get_current_defcon()

            self.logger.info(f"Running {len(queries)} cognitive queries (Regime: {current_regime}, DEFCON: {current_defcon})")

            # Import gateway
            import sys
            sys.path.insert(0, str(Config.get_functions_dir()))

            try:
                from finn_cognitive_gateway import run_cognitive_cycle
                from schemas.signal_envelope import DEFCONLevel, NoSignal, SignalEnvelope
            except ImportError as e:
                self.logger.error(f"Failed to import cognitive gateway: {e}")
                return results

            # Map DEFCON string to enum
            defcon_map = {
                'GREEN': DEFCONLevel.GREEN,
                'YELLOW': DEFCONLevel.YELLOW,
                'ORANGE': DEFCONLevel.ORANGE,
                'RED': DEFCONLevel.RED,
                'BLACK': DEFCONLevel.BLACK
            }
            defcon_level = defcon_map.get(current_defcon, DEFCONLevel.YELLOW)

            # Execute each query
            for query in queries:
                query_template = query['query_template']
                query_type = query['query_type']
                asset_scope = query.get('asset_scope', 'ALL')

                # Expand template with current context
                expanded_query = query_template.format(
                    regime=current_regime,
                    asset=asset_scope if asset_scope != 'ALL' else 'portfolio'
                )

                self.logger.info(f"  Executing {query_type}: {expanded_query[:50]}...")

                try:
                    if self.dry_run:
                        self.logger.info(f"  [DRY RUN] Would execute cognitive query")
                        result = {
                            'query_type': query_type,
                            'query': expanded_query[:100],
                            'success': True,
                            'dry_run': True
                        }
                    else:
                        # Run cognitive cycle
                        signal_result = run_cognitive_cycle(
                            query=expanded_query,
                            defcon_level=defcon_level,
                            regime=current_regime,
                            asset=asset_scope if asset_scope not in ('ALL', 'PORTFOLIO', 'MACRO') else None
                        )

                        if isinstance(signal_result, NoSignal):
                            result = {
                                'query_type': query_type,
                                'query': expanded_query[:100],
                                'success': True,
                                'signal_type': 'NO_SIGNAL',
                                'reason': signal_result.reason
                            }
                            self.logger.info(f"    -> NO_SIGNAL: {signal_result.reason}")
                        else:
                            result = {
                                'query_type': query_type,
                                'query': expanded_query[:100],
                                'success': True,
                                'signal_type': 'SIGNAL',
                                'action': signal_result.action.value if hasattr(signal_result.action, 'value') else str(signal_result.action),
                                'confidence': signal_result.confidence,
                                'bundle_id': signal_result.bundle_id
                            }
                            self.logger.info(f"    -> SIGNAL: {signal_result.action}, confidence={signal_result.confidence:.2f}")

                except Exception as e:
                    result = {
                        'query_type': query_type,
                        'query': expanded_query[:100],
                        'success': False,
                        'error': str(e)
                    }
                    self.logger.error(f"    -> ERROR: {e}")

                results.append(result)

        except Exception as e:
            self.logger.error(f"Cognitive query execution failed: {e}")

        return results

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

            # CEO-DIR-2026-043: Orchestrator Cycle SLA Guard
            # Check that cycles are running within SLA (2× interval)
            if not self.dry_run:
                sla_met, cycles_found, max_gap = self.db.check_cycle_sla()
                self.logger.info(f"Cycle SLA Check: {cycles_found} cycles in last {max_gap}s (SLA: {'MET' if sla_met else 'VIOLATED'})")

                if not sla_met:
                    self.logger.critical("ORCHESTRATOR SLA VIOLATION: No cycles in 2× interval")
                    self.logger.critical("Triggering DATA_BLACKOUT per CEO-DIR-2026-043")
                    blackout_id = self.db.trigger_data_blackout(
                        f"No orchestrator cycles found in {max_gap} seconds (2× standard interval)"
                    )
                    self.logger.critical(f"DATA_BLACKOUT triggered: {blackout_id}")
                    # Continue execution but log the violation

            # CEO-DIR-2026-043: Task Classification Invariant Check
            if not self.dry_run:
                violations = self.db.check_daemon_task_violations()
                if violations:
                    self.logger.critical(f"P0 INCIDENT: {len(violations)} daemon task violations detected")
                    for v in violations:
                        self.logger.critical(f"  - {v['task_name']} executed at {v['timestamp']}")
                    incident_id = self.db.log_p0_incident(
                        'DAEMON_TASK_EXECUTION',
                        {'violations': violations, 'count': len(violations)}
                    )
                    self.logger.critical(f"P0 Incident logged: {incident_id}")

            # CEO-DIR-2026-046: Regime Continuity Invariant (RCI)
            # Regime must be fresh (<=6h) for cognitive operations to be valid
            if not self.dry_run:
                regime_fresh, regime_state, staleness_hours = self.db.check_regime_freshness(max_age_hours=6)
                self.logger.info(f"Regime Freshness Check: {regime_state} (staleness={staleness_hours:.2f}h, SLA: {'MET' if regime_fresh else 'VIOLATED'})")

                if not regime_fresh:
                    self.logger.critical(f"REGIME REALITY VIOLATION: Regime is {staleness_hours:.2f}h stale (max 6h)")
                    self.logger.critical("Triggering DATA_BLACKOUT per CEO-DIR-2026-046")
                    blackout_id = self.db.trigger_regime_blackout(staleness_hours)
                    self.logger.critical(f"DATA_BLACKOUT triggered: {blackout_id}")
                    self.logger.critical("System is EPISTEMICALLY_BLIND until regime refresh completes")
                    # Continue execution but cognitive queries will be blocked

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

            # CEO-DIR-2026-047: REGIME-FIRST EXECUTION ORDER
            # Regime refresh must run FIRST - if it fails, abort all subsequent tasks
            results = []
            regime_task = None
            other_tasks = []

            # Separate regime task from others
            for task in tasks:
                if task['task_name'] == Config.REGIME_FIRST_TASK:
                    regime_task = task
                else:
                    other_tasks.append(task)

            # STEP 1: Execute regime task FIRST with retry logic
            regime_success = False
            if regime_task:
                self.logger.info("")
                self.logger.info("=" * 50)
                self.logger.info("CEO-DIR-2026-047: REGIME CLOCK - MANDATORY FIRST")
                self.logger.info("=" * 50)

                for attempt in range(Config.REGIME_CLOCK_RETRY_ATTEMPTS):
                    self.logger.info(f"[REGIME] Attempt {attempt + 1}/{Config.REGIME_CLOCK_RETRY_ATTEMPTS}: {regime_task['task_name']}")

                    result = self.executor.execute_function(regime_task, dry_run=self.dry_run)
                    results.append(result)

                    if result['success'] and not result.get('skipped', False):
                        self.logger.info(f"[REGIME] SUCCESS - System clock refreshed")
                        regime_success = True
                        break
                    else:
                        if attempt < Config.REGIME_CLOCK_RETRY_ATTEMPTS - 1:
                            backoff = Config.REGIME_CLOCK_RETRY_BACKOFF[attempt]
                            self.logger.warning(f"[REGIME] FAILED - Retrying in {backoff}s...")
                            import time
                            time.sleep(backoff)
                        else:
                            self.logger.critical("[REGIME] ALL RETRIES EXHAUSTED - REGIME CLOCK STOPPED")

                if not regime_success and not self.dry_run:
                    # Trigger REGIME_CLOCK_STOPPED blackout
                    clock_running, last_refresh, hours_since, status = self.db.check_regime_clock()
                    self.logger.critical(f"REGIME_CLOCK_STOPPED: No refresh in {hours_since:.2f}h")
                    self.logger.critical("Aborting all subsequent tasks per CEO-DIR-2026-047")
                    blackout_id = self.db.trigger_regime_clock_blackout(hours_since)
                    self.logger.critical(f"DATA_BLACKOUT triggered: {blackout_id}")
                    # Return early - do not execute any other tasks
                    return {
                        'success': False,
                        'cycle_id': cycle_id,
                        'tasks_executed': len(results),
                        'successes': 0,
                        'failures': len(results),
                        'message': 'REGIME_CLOCK_STOPPED - All tasks aborted',
                        'status': 'ABORTED'
                    }

            # STEP 2: Execute remaining tasks in order (only if regime succeeded)
            for i, task in enumerate(other_tasks, 1):
                self.logger.info("")
                self.logger.info(f"[{i}/{len(other_tasks)}] Executing: {task['task_name']} (Agent: {task['agent_id']})")

                result = self.executor.execute_function(task, dry_run=self.dry_run)
                results.append(result)

                if result['success']:
                    self.logger.info(f"SUCCESS: {task['task_name']}")
                else:
                    self.logger.error(f"❌ FAILED: {task['task_name']}")
                    if 'error' in result:
                        self.logger.error(f"   Error: {result['error']}")

            # CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001: Execute cognitive queries
            self.logger.info("")
            self.logger.info("-" * 40)
            self.logger.info("COGNITIVE ENGINE QUERIES")
            self.logger.info("-" * 40)
            cognitive_results = self.run_cognitive_queries()

            if cognitive_results:
                self.logger.info(f"Cognitive queries executed: {len(cognitive_results)}")
                # Add to results for logging
                for cr in cognitive_results:
                    results.append({
                        'task_name': f"COGNITIVE_{cr.get('query_type', 'QUERY')}",
                        'agent_id': 'FINN',
                        'success': cr.get('success', False),
                        'cognitive_result': cr
                    })

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

    # =========================================================================
    # CNRP-001 METHODS (CEO-DIR-2026-009-B)
    # =========================================================================

    def run_cnrp_chain(self) -> Dict[str, Any]:
        """Run CNRP R1->R2->R3->R4 causal chain"""
        try:
            self.db.connect()
            self.cnrp_executor = CNRPExecutor(self.db, self.logger)
            return self.cnrp_executor.run_chain(dry_run=self.dry_run)
        finally:
            self.db.close()

    def run_cnrp_r4(self) -> Dict[str, Any]:
        """Run R4 integrity monitor standalone"""
        try:
            self.db.connect()
            self.cnrp_executor = CNRPExecutor(self.db, self.logger)
            return self.cnrp_executor.run_r4_standalone(dry_run=self.dry_run)
        finally:
            self.db.close()

    def run_truth_loop(self) -> Dict[str, Any]:
        """
        Run IOS-TRUTH-LOOP snapshot (CEO-DIR-2026-039B, CEO-DIR-2026-040).

        Generates database-verified learning snapshots with ACI bindings.
        Cadence: 2-hour baseline (can be dynamically adjusted by snapshot engine).
        """
        self.logger.info("-" * 50)
        self.logger.info("IOS-TRUTH-LOOP v2 (CEO-DIR-2026-039B/040)")
        self.logger.info("-" * 50)

        result = {
            'success': False,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'snapshot_id': None,
            'status': None,
            'cadence_mode': None,
        }

        if self.dry_run:
            self.logger.info("[DRY RUN] Would execute ios_truth_snapshot_engine.py")
            result['success'] = True
            result['dry_run'] = True
            return result

        try:
            task_path = Path(__file__).parent / Config.TRUTH_LOOP_TASK_PATH
            if not task_path.exists():
                self.logger.error(f"Truth Loop task not found: {task_path}")
                result['error'] = f"Task not found: {task_path}"
                return result

            # Execute the truth loop engine
            process = subprocess.run(
                ['python', str(task_path)],
                capture_output=True,
                text=True,
                timeout=Config.FUNCTION_TIMEOUT_SECONDS,
                cwd=str(task_path.parent.parent)
            )

            if process.returncode == 0:
                self.logger.info("Truth Loop snapshot completed successfully")
                result['success'] = True
                result['stdout'] = process.stdout[-1000:] if process.stdout else None
            else:
                self.logger.error(f"Truth Loop failed with exit code {process.returncode}")
                result['error'] = process.stderr[-500:] if process.stderr else "Unknown error"

            # Try to read the latest snapshot for status
            try:
                latest_path = Path(__file__).parent.parent / "12_DAILY_REPORTS" / "TRUTH_SNAPSHOT" / "LATEST.json"
                if latest_path.exists():
                    import json
                    with open(latest_path, 'r') as f:
                        snapshot = json.load(f)
                    result['snapshot_id'] = snapshot.get('snapshot_id')
                    result['status'] = snapshot.get('status')
                    result['cadence_mode'] = snapshot.get('cadence', {}).get('mode')
            except Exception as e:
                self.logger.warning(f"Could not read latest snapshot: {e}")

        except subprocess.TimeoutExpired:
            self.logger.error("Truth Loop timed out")
            result['error'] = "Execution timeout"
        except Exception as e:
            self.logger.error(f"Truth Loop error: {e}")
            result['error'] = str(e)

        return result

    def run_defcon_evaluation(self) -> Dict[str, Any]:
        """
        Run DEFCON live evaluation (CEO-DIR-2026-045).

        Evaluates system health and updates DEFCON state timestamp.
        Level changes only occur if thresholds are breached.
        """
        result = {
            'success': False,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': None,
            'action': None,
        }

        if self.dry_run:
            self.logger.info("[DRY RUN] Would run DEFCON evaluation")
            result['success'] = True
            result['dry_run'] = True
            return result

        try:
            # Import and run the evaluator directly for efficiency
            functions_dir = Config.get_functions_dir()
            sys.path.insert(0, str(functions_dir))

            from defcon_live_evaluator import evaluate_defcon, update_defcon_state

            # Connect and evaluate
            if not self.db.conn or self.db.conn.closed:
                self.db.connect()

            evaluation = evaluate_defcon(self.db.conn)
            update_result = update_defcon_state(self.db.conn, evaluation)

            result['success'] = True
            result['level'] = evaluation['recommendation']['level']
            result['action'] = update_result['action']
            result['warnings'] = len(evaluation.get('warnings', []))

            self.logger.info(f"DEFCON evaluated: Level {result['level']} ({result['action']})")

        except Exception as e:
            self.logger.warning(f"DEFCON evaluation failed: {e}")
            result['error'] = str(e)

        return result

    def run_cnrp_continuous(self):
        """
        Run orchestrator with integrated CNRP and Truth Loop scheduling.

        Schedule:
        - Every 4 hours: Full CNRP chain (R1->R2->R3) (CEO-DIR-2026-009-B)
        - Every 10 minutes: R4 standalone monitor (CEO-DIR-2026-024)
        - Every 2 hours: IOS-TRUTH-LOOP snapshot (CEO-DIR-2026-040)

        CEO Position: "Clocks trigger. Brainstems decide."
        """
        self.logger.info("=" * 70)
        self.logger.info("CNRP-INTEGRATED CONTINUOUS MODE + IOS-TRUTH-LOOP")
        self.logger.info("CEO-DIR-2026-009-B, CEO-DIR-2026-040: Orchestrator-Native Execution")
        self.logger.info("=" * 70)
        self.logger.info(f"CNRP Cycle Interval: {Config.CNRP_CYCLE_INTERVAL_SECONDS}s (4 hours)")
        self.logger.info(f"R4 Monitor Interval: {Config.CNRP_R4_INTERVAL_SECONDS}s (10 minutes)")
        self.logger.info(f"Truth Loop Interval: {Config.TRUTH_LOOP_INTERVAL_SECONDS}s (2 hours)")
        self.logger.info(f"DEFCON Eval Interval: {Config.DEFCON_EVAL_INTERVAL_SECONDS}s (5 minutes)")
        self.logger.info(f"Heartbeat Interval: {Config.HEARTBEAT_INTERVAL_SECONDS}s (CEO-DIR-2026-042)")

        last_cnrp_cycle = 0    # Epoch time of last full CNRP cycle
        last_r4_monitor = 0    # Epoch time of last R4 monitor
        last_truth_loop = 0    # Epoch time of last Truth Loop snapshot
        last_defcon_eval = 0   # CEO-DIR-2026-045: Epoch time of last DEFCON evaluation
        last_heartbeat = 0     # CEO-DIR-2026-042: Epoch time of last heartbeat
        cycle_number = 0
        truth_loop_count = 0
        total_events = 0       # Total events processed for heartbeat

        try:
            while True:
                now = time.time()

                # CEO-DIR-2026-042: Publish heartbeat every HEARTBEAT_INTERVAL_SECONDS
                if now - last_heartbeat >= Config.HEARTBEAT_INTERVAL_SECONDS:
                    current_task = f"CNRP#{cycle_number}|TRUTH#{truth_loop_count}"
                    self.publish_heartbeat(current_task, total_events)
                    last_heartbeat = now

                # Check if full CNRP cycle is due (every 4 hours)
                time_since_cnrp = now - last_cnrp_cycle
                if time_since_cnrp >= Config.CNRP_CYCLE_INTERVAL_SECONDS:
                    cycle_number += 1
                    self.logger.info("")
                    self.logger.info(f"╔{'═' * 68}╗")
                    self.logger.info(f"║ CNRP FULL CYCLE #{cycle_number:04d} {' ' * 46}║")
                    self.logger.info(f"╚{'═' * 68}╝")

                    result = self.run_cnrp_chain()
                    last_cnrp_cycle = now
                    total_events += 1  # CEO-DIR-2026-042: Increment for heartbeat tracking
                    # CEO-DIR-2026-024: R4 timer-only, do NOT reset last_r4_monitor here

                    if result.get('chain_status') != 'SUCCESS':
                        self.logger.error("CNRP chain failed, but continuing...")

                # Check if IOS-TRUTH-LOOP is due (every 2 hours - CEO-DIR-2026-040)
                time_since_truth = now - last_truth_loop
                if time_since_truth >= Config.TRUTH_LOOP_INTERVAL_SECONDS:
                    truth_loop_count += 1
                    self.logger.info("")
                    self.logger.info(f"╔{'═' * 68}╗")
                    self.logger.info(f"║ IOS-TRUTH-LOOP #{truth_loop_count:04d} (CEO-DIR-2026-040) {' ' * 29}║")
                    self.logger.info(f"╚{'═' * 68}╝")

                    result = self.run_truth_loop()
                    last_truth_loop = now
                    total_events += 1  # CEO-DIR-2026-042

                    if result.get('success'):
                        self.logger.info(f"Snapshot: {result.get('snapshot_id')} | Status: {result.get('status')} | Cadence: {result.get('cadence_mode')}")
                    else:
                        self.logger.error("Truth Loop failed, but continuing...")

                # Check if R4 monitor is due (timer-only: every 600s metronome)
                time_since_r4 = now - last_r4_monitor
                if time_since_r4 >= Config.CNRP_R4_INTERVAL_SECONDS:
                    self.logger.info("")
                    self.logger.info("-" * 40)
                    self.logger.info("R4 INTEGRITY MONITOR (standalone)")
                    self.logger.info("-" * 40)

                    result = self.run_cnrp_r4()
                    last_r4_monitor = now
                    total_events += 1  # CEO-DIR-2026-042

                    if not result.get('success'):
                        self.logger.error("R4 monitor failed, but continuing...")

                # Check if DEFCON evaluation is due (every 5 minutes - CEO-DIR-2026-045)
                time_since_defcon = now - last_defcon_eval
                if time_since_defcon >= Config.DEFCON_EVAL_INTERVAL_SECONDS:
                    result = self.run_defcon_evaluation()
                    last_defcon_eval = now
                    total_events += 1

                # Calculate sleep time until next action
                time_to_cnrp = max(0, Config.CNRP_CYCLE_INTERVAL_SECONDS - (time.time() - last_cnrp_cycle))
                time_to_r4 = max(0, Config.CNRP_R4_INTERVAL_SECONDS - (time.time() - last_r4_monitor))
                time_to_truth = max(0, Config.TRUTH_LOOP_INTERVAL_SECONDS - (time.time() - last_truth_loop))
                time_to_defcon = max(0, Config.DEFCON_EVAL_INTERVAL_SECONDS - (time.time() - last_defcon_eval))
                sleep_time = min(time_to_cnrp, time_to_r4, time_to_truth, time_to_defcon, 60)  # Check at least every minute

                if sleep_time > 0:
                    next_times = [
                        ("CNRP chain", time_to_cnrp),
                        ("R4 monitor", time_to_r4),
                        ("Truth Loop", time_to_truth),
                        ("DEFCON eval", time_to_defcon)
                    ]
                    next_action, next_time = min(next_times, key=lambda x: x[1])
                    self.logger.info(f"Next {next_action} in {next_time:.0f}s. Sleeping {sleep_time:.0f}s...")
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("")
            self.logger.info("Received interrupt signal, stopping orchestrator...")
            self.logger.info(f"Total CNRP cycles: {cycle_number}, Truth Loop: {truth_loop_count}, Events: {total_events}")
            # Final heartbeat to mark shutdown
            self.publish_heartbeat("SHUTDOWN", total_events)

    def run_healthcheck(self) -> Dict[str, Any]:
        """
        Health check for Windows Scheduler watchdog.

        Returns orchestrator and CNRP health status.
        Does NOT execute any daemons - monitoring only.
        """
        self.logger.info("Orchestrator Health Check")

        health = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'orchestrator_version': Config.ORCHESTRATOR_VERSION,
            'status': 'HEALTHY',
            'checks': {}
        }

        try:
            self.db.connect()

            # Check database connection
            health['checks']['database'] = {'status': 'OK'}

            # Check last CNRP execution
            with self.db.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT phase, status, completed_at
                    FROM fhq_governance.cnrp_execution_log
                    ORDER BY completed_at DESC
                    LIMIT 1
                """)
                last_cnrp = cur.fetchone()

                if last_cnrp:
                    age_hours = (datetime.now(timezone.utc) -
                                 last_cnrp['completed_at'].replace(tzinfo=timezone.utc)).total_seconds() / 3600
                    health['checks']['cnrp_last_execution'] = {
                        'phase': last_cnrp['phase'],
                        'status': last_cnrp['status'],
                        'hours_ago': round(age_hours, 2)
                    }

                    # Alert if no CNRP execution in 5+ hours
                    if age_hours > 5:
                        health['checks']['cnrp_last_execution']['warning'] = 'Stale - no execution in 5+ hours'
                        health['status'] = 'WARNING'
                else:
                    health['checks']['cnrp_last_execution'] = {'status': 'NO_DATA'}

                # Check evidence staleness
                cur.execute("""
                    SELECT
                        EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/3600 as hours_stale
                    FROM fhq_canonical.evidence_nodes
                """)
                staleness = cur.fetchone()

                if staleness and staleness['hours_stale']:
                    hours = round(staleness['hours_stale'], 2)
                    health['checks']['evidence_staleness'] = {
                        'hours': hours,
                        'threshold': 24,
                        'status': 'OK' if hours < 24 else 'CRITICAL'
                    }

                    if hours >= 20:
                        health['status'] = 'CRITICAL'
                        health['alert'] = f'Evidence staleness critical: {hours}h (threshold: 24h)'

        except Exception as e:
            health['status'] = 'ERROR'
            health['error'] = str(e)
        finally:
            self.db.close()

        # Output health status
        self.logger.info(f"Health Status: {health['status']}")
        if health.get('alert'):
            self.logger.critical(f"ALERT: {health['alert']}")

        return health


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point"""

    parser = argparse.ArgumentParser(
        description='Vision-IoS Orchestrator v1.1 - Execute Vision-IoS functions in coordinated cycles (CEO-DIR-2026-009-B)'
    )

    # Standard orchestrator arguments
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

    # CNRP-001 arguments (CEO-DIR-2026-009-B)
    cnrp_group = parser.add_argument_group('CNRP-001 Options',
        'Cognitive Node Refresh Protocol (CEO-DIR-2026-009-B)')
    cnrp_group.add_argument(
        '--cnrp-cycle',
        action='store_true',
        help='Run CNRP R1->R2->R3->R4 causal chain once'
    )
    cnrp_group.add_argument(
        '--cnrp-r4',
        action='store_true',
        help='Run R4 (VEGA) integrity monitor only (standalone)'
    )
    cnrp_group.add_argument(
        '--cnrp-continuous',
        action='store_true',
        help='Run with full scheduling (4h CNRP + 2h Truth Loop + 10m R4)'
    )
    cnrp_group.add_argument(
        '--healthcheck',
        action='store_true',
        help='Health check for Windows watchdog (no execution)'
    )

    # IOS-TRUTH-LOOP arguments (CEO-DIR-2026-039B/040)
    truth_group = parser.add_argument_group('IOS-TRUTH-LOOP Options',
        'Learning Velocity Engine (CEO-DIR-2026-039B, CEO-DIR-2026-040)')
    truth_group.add_argument(
        '--truth-loop',
        action='store_true',
        help='Run IOS-TRUTH-LOOP snapshot once'
    )

    args = parser.parse_args()

    # Override interval if specified
    if args.interval:
        Config.CONTINUOUS_INTERVAL_SECONDS = args.interval

    # Setup logging
    logger = setup_logging()

    # Create orchestrator
    orchestrator = VisionIoSOrchestrator(logger, dry_run=args.dry_run)

    # CNRP-001 execution modes (CEO-DIR-2026-009-B)
    if args.healthcheck:
        # Windows watchdog mode - health check only
        result = orchestrator.run_healthcheck()
        sys.exit(0 if result.get('status') in ('HEALTHY', 'WARNING') else 1)

    elif args.cnrp_cycle:
        # Single CNRP chain execution
        result = orchestrator.run_cnrp_chain()
        sys.exit(0 if result.get('chain_status') == 'SUCCESS' else 1)

    elif args.cnrp_r4:
        # R4 standalone integrity monitor
        result = orchestrator.run_cnrp_r4()
        sys.exit(0 if result.get('success') else 1)

    elif args.truth_loop:
        # IOS-TRUTH-LOOP standalone execution (CEO-DIR-2026-039B/040)
        result = orchestrator.run_truth_loop()
        sys.exit(0 if result.get('success') else 1)

    elif args.cnrp_continuous:
        # Full scheduling mode (4h CNRP + 2h Truth Loop + 10m R4)
        orchestrator.run_cnrp_continuous()

    elif args.continuous:
        # Standard Vision-IoS continuous mode
        orchestrator.run_continuous(function_filter=args.function)

    else:
        # Single cycle execution
        result = orchestrator.run_cycle(function_filter=args.function)
        sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
