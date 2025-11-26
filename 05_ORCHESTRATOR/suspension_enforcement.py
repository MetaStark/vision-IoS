#!/usr/bin/env python3
"""
SUSPENSION ENFORCEMENT MODULE - ADR-009 Worker Integration
Purpose: Worker integration for deterministic suspension enforcement
Compliance: ADR-009 Section 7, ADR-007, ADR-008

ADR-009 Section 7 Requirements:
  - Worker must check agent status before starting any task
  - Worker must halt task execution for agents marked SUSPENDED
  - Worker must write full audit logs for each decision
  - Worker must attach cryptographic signatures to all actions

This module provides the suspension enforcement layer that integrates
with the Orchestrator to ensure suspended agents cannot execute tasks.

Usage:
    from suspension_enforcement import SuspensionEnforcer

    enforcer = SuspensionEnforcer(db_connection_string, logger)
    can_execute, reason = enforcer.check_agent_can_execute(agent_id)

    if not can_execute:
        # Log rejection and skip task
        enforcer.log_task_rejection(agent_id, task_id, reason)
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

# Database
import psycopg2
from psycopg2.extras import RealDictCursor, Json


# =============================================================================
# CONFIGURATION
# =============================================================================

class SuspensionEnforcementConfig:
    """Configuration for suspension enforcement"""

    # Module identity
    MODULE_NAME = "SUSPENSION_ENFORCER"
    ADR_REFERENCE = "ADR-009"

    # Database connection
    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class AgentExecutionStatus:
    """Agent execution status for suspension enforcement"""
    agent_id: str
    can_execute: bool
    is_suspended: bool
    has_pending_request: bool
    suspension_reason: Optional[str]
    pending_request_id: Optional[str]
    checked_at: str


@dataclass
class TaskRejectionLog:
    """Log entry for rejected task due to suspension"""
    agent_id: str
    task_id: str
    task_name: Optional[str]
    rejection_reason: str
    suspension_request_id: Optional[str]
    logged_at: str
    signature: str


# =============================================================================
# SUSPENSION ENFORCER
# =============================================================================

class SuspensionEnforcer:
    """
    Suspension Enforcer - ADR-009 Section 7 Worker Integration

    This class provides the enforcement layer for the orchestrator/worker
    to deterministically respect suspended agent status.

    Responsibilities:
      1. Check agent status before task execution
      2. Block tasks for suspended agents
      3. Log all enforcement decisions
      4. Provide audit trail for compliance
    """

    def __init__(
        self,
        connection_string: str = None,
        logger: logging.Logger = None,
        conn: Any = None
    ):
        """
        Initialize Suspension Enforcer.

        Args:
            connection_string: Database connection string (optional if conn provided)
            logger: Logger instance
            conn: Existing database connection (optional)
        """
        self.connection_string = connection_string or SuspensionEnforcementConfig.get_db_connection_string()
        self.logger = logger or logging.getLogger("suspension_enforcer")
        self._conn = conn
        self._owns_connection = False

    def _get_connection(self):
        """Get or create database connection"""
        if self._conn is not None:
            return self._conn

        self._conn = psycopg2.connect(self.connection_string)
        self._owns_connection = True
        return self._conn

    def close(self):
        """Close database connection if we own it"""
        if self._owns_connection and self._conn:
            self._conn.close()
            self._conn = None

    def _generate_hash(self, data: Any) -> str:
        """Generate SHA-256 hash"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _generate_signature(self, data: str) -> str:
        """Generate signature for audit trail"""
        sig_data = f"WORKER:{SuspensionEnforcementConfig.MODULE_NAME}:{data}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(sig_data.encode()).hexdigest()

    # =========================================================================
    # CORE ENFORCEMENT METHODS
    # =========================================================================

    def check_agent_can_execute(self, agent_id: str) -> Tuple[bool, str, Optional[str]]:
        """
        Check if an agent can execute tasks (ADR-009 Section 7).

        This is the primary method that Workers must call before executing
        any task for an agent.

        Args:
            agent_id: The agent ID to check

        Returns:
            Tuple of (can_execute, reason, request_id or None)
            - can_execute: True if agent can execute tasks
            - reason: Human-readable reason
            - request_id: Suspension request ID if suspended (for logging)
        """
        conn = self._get_connection()

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check agent status
            cur.execute("""
                SELECT
                    agent_id,
                    agent_name,
                    is_suspended,
                    suspension_reason,
                    suspended_at
                FROM fhq_org.org_agents
                WHERE agent_id = %s
            """, (agent_id,))

            agent = cur.fetchone()

            if not agent:
                return False, f"Agent {agent_id} does not exist", None

            if agent['is_suspended']:
                # Get the suspension request ID for logging
                cur.execute("""
                    SELECT request_id
                    FROM fhq_governance.agent_suspension_requests
                    WHERE agent_id = %s AND status = 'APPROVED'
                    ORDER BY created_at DESC LIMIT 1
                """, (agent_id,))
                req = cur.fetchone()
                request_id = str(req['request_id']) if req else None

                reason = f"Agent {agent_id} is SUSPENDED: {agent['suspension_reason'] or 'No reason provided'}"
                return False, reason, request_id

            return True, f"Agent {agent_id} is active and can execute tasks", None

    def get_agent_execution_status(self, agent_id: str) -> AgentExecutionStatus:
        """
        Get comprehensive execution status for an agent.

        Args:
            agent_id: The agent ID to check

        Returns:
            AgentExecutionStatus dataclass with full status information
        """
        conn = self._get_connection()

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get agent info
            cur.execute("""
                SELECT
                    agent_id,
                    is_suspended,
                    suspension_reason
                FROM fhq_org.org_agents
                WHERE agent_id = %s
            """, (agent_id,))

            agent = cur.fetchone()

            if not agent:
                return AgentExecutionStatus(
                    agent_id=agent_id,
                    can_execute=False,
                    is_suspended=False,
                    has_pending_request=False,
                    suspension_reason="Agent does not exist",
                    pending_request_id=None,
                    checked_at=datetime.now(timezone.utc).isoformat()
                )

            # Check for pending requests
            cur.execute("""
                SELECT request_id
                FROM fhq_governance.agent_suspension_requests
                WHERE agent_id = %s AND status = 'PENDING'
                ORDER BY created_at DESC LIMIT 1
            """, (agent_id,))

            pending = cur.fetchone()

            return AgentExecutionStatus(
                agent_id=agent_id,
                can_execute=not agent['is_suspended'],
                is_suspended=agent['is_suspended'],
                has_pending_request=pending is not None,
                suspension_reason=agent['suspension_reason'],
                pending_request_id=str(pending['request_id']) if pending else None,
                checked_at=datetime.now(timezone.utc).isoformat()
            )

    def log_task_rejection(
        self,
        agent_id: str,
        task_id: str,
        reason: str,
        task_name: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Log a task rejection due to agent suspension (ADR-009 Section 7).

        This method records that a task was blocked because the agent
        is suspended, providing audit trail for compliance.

        Args:
            agent_id: The suspended agent
            task_id: The task that was blocked
            reason: Reason for rejection
            task_name: Optional task name for readability
            request_id: Optional suspension request ID

        Returns:
            True if logged successfully
        """
        conn = self._get_connection()

        try:
            with conn.cursor() as cur:
                # Build audit data
                audit_data = {
                    'agent_id': agent_id,
                    'task_id': str(task_id),
                    'task_name': task_name,
                    'rejection_reason': reason,
                    'suspension_request_id': request_id,
                    'enforcement_module': SuspensionEnforcementConfig.MODULE_NAME,
                    'adr_reference': SuspensionEnforcementConfig.ADR_REFERENCE,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }

                audit_hash = self._generate_hash(audit_data)
                signature = self._generate_signature(audit_hash)

                # Log to org_activity_log
                cur.execute("""
                    INSERT INTO fhq_org.org_activity_log (
                        agent_id,
                        activity_type,
                        input_data,
                        output_data,
                        signature,
                        hash_chain_id,
                        reconciliation_score,
                        discrepancy_detected
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    agent_id,
                    'TASK_REJECTED_SUSPENDED',
                    Json({
                        'task_id': str(task_id),
                        'task_name': task_name,
                        'reason': reason
                    }),
                    Json({
                        'status': 'REJECTED',
                        'suspension_enforced': True,
                        'request_id': request_id
                    }),
                    signature,
                    f"HC-WORKER-SUSPENSION-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                    1.0,  # Full discrepancy (task blocked)
                    True
                ))

                # Also log to suspension_audit_log if we have a request_id
                if request_id:
                    try:
                        cur.execute("""
                            INSERT INTO fhq_governance.suspension_audit_log (
                                request_id,
                                action_type,
                                performed_by,
                                action_data,
                                action_hash,
                                signature
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            request_id,
                            'TASK_BLOCKED',  # Custom action type for task blocking
                            'WORKER',
                            Json(audit_data),
                            audit_hash,
                            signature
                        ))
                    except psycopg2.errors.CheckViolation:
                        # action_type may not be in the enum, log to activity log only
                        pass

                conn.commit()
                self.logger.info(f"Task rejection logged: agent={agent_id}, task={task_id}")
                return True

        except Exception as e:
            conn.rollback()
            self.logger.error(f"Failed to log task rejection: {e}")
            return False

    def get_all_suspended_agents(self) -> List[str]:
        """
        Get list of all currently suspended agents.

        Useful for batch operations or dashboard displays.

        Returns:
            List of suspended agent IDs
        """
        conn = self._get_connection()

        with conn.cursor() as cur:
            cur.execute("""
                SELECT agent_id
                FROM fhq_org.org_agents
                WHERE is_suspended = TRUE
            """)
            return [row[0] for row in cur.fetchall()]

    def filter_executable_tasks(
        self,
        tasks: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter a list of tasks, separating executable from blocked.

        Args:
            tasks: List of task dictionaries with 'agent_id' key

        Returns:
            Tuple of (executable_tasks, blocked_tasks)
        """
        executable = []
        blocked = []

        for task in tasks:
            agent_id = task.get('agent_id') or task.get('assigned_agent_id')
            if not agent_id:
                blocked.append({**task, 'block_reason': 'No agent_id specified'})
                continue

            can_execute, reason, _ = self.check_agent_can_execute(agent_id)
            if can_execute:
                executable.append(task)
            else:
                blocked.append({**task, 'block_reason': reason})

        return executable, blocked


# =============================================================================
# ORCHESTRATOR INTEGRATION MIXIN
# =============================================================================

class SuspensionEnforcementMixin:
    """
    Mixin class for Orchestrator integration.

    Add this mixin to the Orchestrator class to integrate
    suspension enforcement into the task execution flow.

    Example:
        class VisionIoSOrchestrator(SuspensionEnforcementMixin, BaseOrchestrator):
            pass
    """

    def init_suspension_enforcement(self, connection_string: str, logger: logging.Logger):
        """Initialize suspension enforcement"""
        self._suspension_enforcer = SuspensionEnforcer(connection_string, logger)

    def check_suspension_before_task(
        self,
        agent_id: str,
        task_id: str,
        task_name: str = None
    ) -> bool:
        """
        Check suspension status and log if blocked.

        Call this before executing any task.

        Returns:
            True if task can proceed, False if blocked
        """
        can_execute, reason, request_id = self._suspension_enforcer.check_agent_can_execute(agent_id)

        if not can_execute:
            self._suspension_enforcer.log_task_rejection(
                agent_id=agent_id,
                task_id=task_id,
                reason=reason,
                task_name=task_name,
                request_id=request_id
            )
            return False

        return True


# =============================================================================
# STANDALONE UTILITIES
# =============================================================================

def check_agent_suspended(agent_id: str, connection_string: str = None) -> bool:
    """
    Standalone function to check if an agent is suspended.

    Args:
        agent_id: Agent to check
        connection_string: Optional database connection string

    Returns:
        True if agent is suspended, False otherwise
    """
    enforcer = SuspensionEnforcer(connection_string)
    try:
        can_execute, _, _ = enforcer.check_agent_can_execute(agent_id)
        return not can_execute
    finally:
        enforcer.close()


def get_suspended_agents(connection_string: str = None) -> List[str]:
    """
    Standalone function to get all suspended agents.

    Args:
        connection_string: Optional database connection string

    Returns:
        List of suspended agent IDs
    """
    enforcer = SuspensionEnforcer(connection_string)
    try:
        return enforcer.get_all_suspended_agents()
    finally:
        enforcer.close()


# =============================================================================
# MAIN (Testing/CLI)
# =============================================================================

def main():
    """CLI for testing suspension enforcement"""
    import argparse

    parser = argparse.ArgumentParser(
        description='ADR-009 Suspension Enforcement Module - Worker Integration'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Check agent command
    check_parser = subparsers.add_parser('check', help='Check if agent can execute')
    check_parser.add_argument('--agent', required=True, help='Agent ID to check')

    # List suspended command
    list_parser = subparsers.add_parser('list-suspended', help='List all suspended agents')

    # Status command
    status_parser = subparsers.add_parser('status', help='Get detailed agent status')
    status_parser.add_argument('--agent', required=True, help='Agent ID')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("suspension_enforcer")

    enforcer = SuspensionEnforcer(logger=logger)

    try:
        if args.command == 'check':
            can_execute, reason, request_id = enforcer.check_agent_can_execute(args.agent)
            print(f"\nAgent: {args.agent}")
            print(f"Can Execute: {can_execute}")
            print(f"Reason: {reason}")
            if request_id:
                print(f"Request ID: {request_id}")

        elif args.command == 'list-suspended':
            suspended = enforcer.get_all_suspended_agents()
            print(f"\nSuspended Agents: {len(suspended)}")
            for agent in suspended:
                print(f"  - {agent}")

        elif args.command == 'status':
            status = enforcer.get_agent_execution_status(args.agent)
            print(f"\nAgent Execution Status: {args.agent}")
            print(f"  Can Execute: {status.can_execute}")
            print(f"  Is Suspended: {status.is_suspended}")
            print(f"  Has Pending Request: {status.has_pending_request}")
            if status.suspension_reason:
                print(f"  Suspension Reason: {status.suspension_reason}")
            if status.pending_request_id:
                print(f"  Pending Request ID: {status.pending_request_id}")
            print(f"  Checked At: {status.checked_at}")

    finally:
        enforcer.close()


if __name__ == '__main__':
    main()
