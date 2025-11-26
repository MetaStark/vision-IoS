#!/usr/bin/env python3
"""
VEGA SUSPENSION WORKFLOW - ADR-009 Implementation
Agent: VEGA (Constitutional Governance Engine)
Purpose: Dual-approval agent suspension workflow per ADR-009
Compliance: ADR-009, ADR-010, ADR-008, ADR-007

ADR-009 Key Requirements:
  - VEGA can only RECOMMEND suspension (Stage 1)
  - CEO must APPROVE/REJECT (Stage 2)
  - All decisions logged with hash-linked evidence
  - Worker respects suspended status

Authority Chain: ADR-001 -> ADR-002 -> ADR-006 -> ADR-007 -> ADR-008 -> EC-001

Usage:
    # VEGA Recommendation (when discrepancy_score > 0.10)
    python vega_suspension_workflow.py recommend --agent=FINN --score=0.15

    # CEO Approval/Rejection
    python vega_suspension_workflow.py approve --request-id=<UUID> --rationale="Evidence reviewed"
    python vega_suspension_workflow.py reject --request-id=<UUID> --rationale="False positive"

    # List pending requests
    python vega_suspension_workflow.py list-pending

    # Check agent status
    python vega_suspension_workflow.py status --agent=FINN
"""

import os
import sys
import json
import hashlib
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from uuid import UUID

# Database
import psycopg2
from psycopg2.extras import RealDictCursor, Json

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """ADR-009 Suspension Workflow Configuration"""

    # Agent identity for VEGA
    VEGA_AGENT_ID = "VEGA"

    # CEO agent ID (LARS has CEO authority per ADR-007)
    CEO_AGENT_ID = "LARS"

    # ADR reference
    ADR_REFERENCE = "ADR-009"

    # Discrepancy threshold per ADR-010
    DISCREPANCY_THRESHOLD = 0.10

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
# LOGGING SETUP
# =============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger("vega_suspension_workflow")
    logger.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - VEGA-ADR009 - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(console)

    return logger


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class SuspensionStatus(Enum):
    """Suspension request status"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AuditActionType(Enum):
    """Audit log action types"""
    REQUEST_CREATED = "REQUEST_CREATED"
    CEO_APPROVED = "CEO_APPROVED"
    CEO_REJECTED = "CEO_REJECTED"
    SUSPENSION_ENFORCED = "SUSPENSION_ENFORCED"
    AGENT_REINSTATED = "AGENT_REINSTATED"
    EVIDENCE_UPDATED = "EVIDENCE_UPDATED"
    NOTIFICATION_SENT = "NOTIFICATION_SENT"


@dataclass
class EvidenceBundle:
    """Evidence bundle for suspension request (ADR-009 Section 5.2)"""
    discrepancy_score: float
    threshold_exceeded: bool
    reconciliation_snapshot_ids: List[str]
    metrics: Dict[str, Any]
    signatures: Dict[str, str]
    timestamps: Dict[str, str]
    reconciliation_data: Dict[str, Any]
    adr_010_compliance: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            'discrepancy_score': self.discrepancy_score,
            'threshold_exceeded': self.threshold_exceeded,
            'reconciliation_snapshot_ids': self.reconciliation_snapshot_ids,
            'metrics': self.metrics,
            'signatures': self.signatures,
            'timestamps': self.timestamps,
            'reconciliation_data': self.reconciliation_data,
            'adr_010_compliance': self.adr_010_compliance
        }


@dataclass
class SuspensionRequest:
    """Suspension request record"""
    request_id: str
    agent_id: str
    requested_by: str
    reason: str
    discrepancy_score: float
    evidence: EvidenceBundle
    status: SuspensionStatus
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_rationale: Optional[str] = None
    created_at: Optional[str] = None


# =============================================================================
# DATABASE INTERFACE
# =============================================================================

class SuspensionWorkflowDB:
    """Database interface for suspension workflow"""

    def __init__(self, connection_string: str, logger: logging.Logger):
        self.connection_string = connection_string
        self.logger = logger
        self.conn = None

    def connect(self) -> bool:
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.logger.info("Database connection established")
            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed")

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute query and return results"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def execute_scalar(self, query: str, params: tuple = None) -> Any:
        """Execute query and return single value"""
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            result = cur.fetchone()
            return result[0] if result else None

    def table_exists(self, schema: str, table: str) -> bool:
        """Check if table exists"""
        result = self.execute_scalar("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
        """, (schema, table))
        return result

    def agent_exists(self, agent_id: str) -> bool:
        """Check if agent exists"""
        return self.execute_scalar("""
            SELECT EXISTS (
                SELECT 1 FROM fhq_org.org_agents WHERE agent_id = %s
            )
        """, (agent_id,))

    def is_agent_suspended(self, agent_id: str) -> bool:
        """Check if agent is currently suspended"""
        return self.execute_scalar("""
            SELECT is_suspended FROM fhq_org.org_agents WHERE agent_id = %s
        """, (agent_id,)) or False

    def get_agent_info(self, agent_id: str) -> Optional[Dict]:
        """Get agent information"""
        result = self.execute_query("""
            SELECT agent_id, agent_name, agent_role, authority_level,
                   is_suspended, suspension_reason, suspended_at
            FROM fhq_org.org_agents WHERE agent_id = %s
        """, (agent_id,))
        return result[0] if result else None


# =============================================================================
# STAGE 1: VEGA RECOMMENDATION (Automatic)
# =============================================================================

class VEGASuspensionRecommender:
    """
    VEGA Suspension Recommender - Stage 1 of ADR-009 Workflow

    VEGA:
      - Monitors discrepancy scores and reconciliation outputs
      - Generates suspension request when discrepancy_score > 0.10
      - Packages evidence including state snapshots, metrics, signatures
      - Records request in governance ledger
      - Notifies LARS and CEO
      - Does NOT suspend the agent (recommendation only)
    """

    def __init__(self, db: SuspensionWorkflowDB, logger: logging.Logger):
        self.db = db
        self.logger = logger
        self.agent_id = Config.VEGA_AGENT_ID

    def _generate_hash(self, data: Any) -> str:
        """Generate SHA-256 hash for evidence"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _generate_signature(self, data: str) -> str:
        """Generate signature (ADR-008 compliant pattern)"""
        signature_data = f"{self.agent_id}:{data}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(signature_data.encode()).hexdigest()

    def _generate_hash_chain_id(self) -> str:
        """Generate hash chain ID"""
        return f"HC-{self.agent_id}-ADR009-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def _build_evidence_bundle(
        self,
        agent_id: str,
        discrepancy_score: float,
        reconciliation_data: Optional[Dict] = None
    ) -> EvidenceBundle:
        """Build comprehensive evidence bundle for suspension request"""

        now = datetime.now(timezone.utc).isoformat()

        # Get reconciliation snapshots if available
        snapshot_ids = []
        try:
            if self.db.table_exists("fhq_meta", "reconciliation_snapshots"):
                snapshots = self.db.execute_query("""
                    SELECT snapshot_id::text FROM fhq_meta.reconciliation_snapshots
                    WHERE component_name = %s
                    ORDER BY snapshot_timestamp DESC LIMIT 5
                """, (agent_id,))
                snapshot_ids = [s['snapshot_id'] for s in snapshots]
        except Exception as e:
            self.logger.warning(f"Could not retrieve snapshots: {e}")

        # Build metrics
        metrics = {
            'discrepancy_score': discrepancy_score,
            'threshold': Config.DISCREPANCY_THRESHOLD,
            'threshold_exceeded': discrepancy_score > Config.DISCREPANCY_THRESHOLD,
            'detection_timestamp': now,
            'agent_id': agent_id,
            'detection_source': 'VEGA_ADR009_MONITOR'
        }

        # Generate signatures
        metrics_hash = self._generate_hash(metrics)
        signatures = {
            'metrics_hash': metrics_hash,
            'vega_signature': self._generate_signature(metrics_hash),
            'signing_algorithm': 'SHA-256'
        }

        # Timestamps
        timestamps = {
            'detection_time': now,
            'request_creation_time': now,
            'discrepancy_detected_at': now
        }

        return EvidenceBundle(
            discrepancy_score=discrepancy_score,
            threshold_exceeded=discrepancy_score > Config.DISCREPANCY_THRESHOLD,
            reconciliation_snapshot_ids=snapshot_ids,
            metrics=metrics,
            signatures=signatures,
            timestamps=timestamps,
            reconciliation_data=reconciliation_data or {},
            adr_010_compliance=True
        )

    def recommend_suspension(
        self,
        agent_id: str,
        discrepancy_score: float,
        reason: Optional[str] = None,
        reconciliation_data: Optional[Dict] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Generate a suspension recommendation (VEGA Stage 1).

        IMPORTANT: VEGA does NOT enforce suspension. This only creates a PENDING
        request that requires CEO approval.

        Args:
            agent_id: The agent to recommend for suspension
            discrepancy_score: The discrepancy score that triggered this
            reason: Optional reason text
            reconciliation_data: Optional reconciliation data from ADR-010

        Returns:
            Tuple of (success, message, request_id or None)
        """

        self.logger.info("=" * 70)
        self.logger.info("VEGA ADR-009 SUSPENSION RECOMMENDATION")
        self.logger.info(f"Agent: {agent_id}")
        self.logger.info(f"Discrepancy Score: {discrepancy_score}")
        self.logger.info("=" * 70)

        # Validate threshold
        if discrepancy_score <= Config.DISCREPANCY_THRESHOLD:
            msg = f"Discrepancy score {discrepancy_score} does not exceed threshold {Config.DISCREPANCY_THRESHOLD}"
            self.logger.warning(msg)
            return False, msg, None

        # Verify agent exists
        if not self.db.agent_exists(agent_id):
            msg = f"Agent {agent_id} does not exist"
            self.logger.error(msg)
            return False, msg, None

        # Check if agent already suspended
        if self.db.is_agent_suspended(agent_id):
            msg = f"Agent {agent_id} is already suspended"
            self.logger.warning(msg)
            return False, msg, None

        # Check for existing pending request
        existing_pending = self.db.execute_scalar("""
            SELECT request_id FROM fhq_governance.agent_suspension_requests
            WHERE agent_id = %s AND status = 'PENDING'
            LIMIT 1
        """, (agent_id,))

        if existing_pending:
            msg = f"Agent {agent_id} already has pending suspension request: {existing_pending}"
            self.logger.warning(msg)
            return False, msg, str(existing_pending)

        # Build evidence bundle
        evidence = self._build_evidence_bundle(agent_id, discrepancy_score, reconciliation_data)

        # Generate hashes
        evidence_hash = self._generate_hash(evidence.to_dict())
        hash_chain_id = self._generate_hash_chain_id()
        request_signature = self._generate_signature(f"{agent_id}:{discrepancy_score}:{evidence_hash}")

        # Build reason
        if not reason:
            reason = (
                f"ADR-010 discrepancy score ({discrepancy_score:.5f}) exceeds "
                f"catastrophic threshold ({Config.DISCREPANCY_THRESHOLD}). "
                f"Agent state reconciliation indicates potential drift or corruption. "
                f"VEGA recommends suspension pending CEO review per ADR-009."
            )

        try:
            # Insert suspension request
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.agent_suspension_requests (
                        agent_id, requested_by, reason, discrepancy_score,
                        evidence, status, evidence_hash, hash_chain_id,
                        request_signature, adr_reference, discrepancy_threshold
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING request_id
                """, (
                    agent_id,
                    self.agent_id,  # VEGA
                    reason,
                    discrepancy_score,
                    Json(evidence.to_dict()),
                    SuspensionStatus.PENDING.value,
                    evidence_hash,
                    hash_chain_id,
                    request_signature,
                    Config.ADR_REFERENCE,
                    Config.DISCREPANCY_THRESHOLD
                ))

                request_id = cur.fetchone()[0]

                # Log audit entry
                audit_data = {
                    'request_id': str(request_id),
                    'agent_id': agent_id,
                    'discrepancy_score': discrepancy_score,
                    'threshold': Config.DISCREPANCY_THRESHOLD,
                    'action': 'SUSPENSION_RECOMMENDATION_CREATED',
                    'vega_agent_id': self.agent_id,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                audit_hash = self._generate_hash(audit_data)

                cur.execute("""
                    INSERT INTO fhq_governance.suspension_audit_log (
                        request_id, action_type, performed_by, action_data,
                        action_hash, signature
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    request_id,
                    AuditActionType.REQUEST_CREATED.value,
                    self.agent_id,
                    Json(audit_data),
                    audit_hash,
                    self._generate_signature(audit_hash)
                ))

                self.db.conn.commit()

            self.logger.info(f"SUSPENSION REQUEST CREATED: {request_id}")
            self.logger.info(f"Status: PENDING (awaiting CEO review)")
            self.logger.info(f"Agent {agent_id} is NOT suspended - requires CEO approval")

            return True, f"Suspension request created: {request_id}", str(request_id)

        except Exception as e:
            self.db.conn.rollback()
            self.logger.error(f"Failed to create suspension request: {e}")
            return False, f"Failed to create request: {e}", None


# =============================================================================
# STAGE 2: CEO APPROVAL/REJECTION
# =============================================================================

class CEOApprovalHandler:
    """
    CEO Approval Handler - Stage 2 of ADR-009 Workflow

    CEO (or delegated authority):
      - Reviews the evidence bundle and context
      - Chooses APPROVE or REJECT
      - On APPROVE: Agent status set to SUSPENDED
      - On REJECT: Override logged, agent continues with elevated monitoring
    """

    def __init__(self, db: SuspensionWorkflowDB, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def _generate_hash(self, data: Any) -> str:
        """Generate SHA-256 hash"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _generate_signature(self, agent_id: str, data: str) -> str:
        """Generate signature"""
        signature_data = f"{agent_id}:{data}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(signature_data.encode()).hexdigest()

    def _get_request(self, request_id: str) -> Optional[Dict]:
        """Get suspension request by ID"""
        result = self.db.execute_query("""
            SELECT * FROM fhq_governance.agent_suspension_requests
            WHERE request_id = %s
        """, (request_id,))
        return result[0] if result else None

    def approve_suspension(
        self,
        request_id: str,
        rationale: str,
        approver_id: str = None
    ) -> Tuple[bool, str]:
        """
        Approve a suspension request (CEO Stage 2 - APPROVE).

        Actions on APPROVE:
          1. Set request status to APPROVED
          2. Set agent status to SUSPENDED in fhq_org.org_agents
          3. Write immutable audit entry with hash-linked evidence
          4. Notify VEGA and monitoring systems

        Args:
            request_id: UUID of the suspension request
            rationale: Reason for approval decision
            approver_id: ID of approving agent (defaults to LARS)

        Returns:
            Tuple of (success, message)
        """

        approver_id = approver_id or Config.CEO_AGENT_ID

        self.logger.info("=" * 70)
        self.logger.info("CEO SUSPENSION APPROVAL - ADR-009 Stage 2")
        self.logger.info(f"Request ID: {request_id}")
        self.logger.info(f"Approver: {approver_id}")
        self.logger.info("=" * 70)

        # Get request
        request = self._get_request(request_id)
        if not request:
            msg = f"Suspension request not found: {request_id}"
            self.logger.error(msg)
            return False, msg

        # Verify request is PENDING
        if request['status'] != SuspensionStatus.PENDING.value:
            msg = f"Request is not pending. Current status: {request['status']}"
            self.logger.error(msg)
            return False, msg

        # Verify approver has authority (must be LARS or designated delegate)
        if not self.db.agent_exists(approver_id):
            msg = f"Approver agent {approver_id} does not exist"
            self.logger.error(msg)
            return False, msg

        approver_info = self.db.get_agent_info(approver_id)
        if approver_info['authority_level'] < 9:  # CEO authority level
            msg = f"Approver {approver_id} does not have CEO authority (level {approver_info['authority_level']} < 9)"
            self.logger.error(msg)
            return False, msg

        agent_id = request['agent_id']
        now = datetime.now(timezone.utc)

        try:
            with self.db.conn.cursor() as cur:
                # 1. Update suspension request status
                cur.execute("""
                    UPDATE fhq_governance.agent_suspension_requests
                    SET status = %s,
                        reviewed_by = %s,
                        reviewed_at = %s,
                        review_rationale = %s
                    WHERE request_id = %s
                """, (
                    SuspensionStatus.APPROVED.value,
                    approver_id,
                    now,
                    rationale,
                    request_id
                ))

                # 2. Set agent status to SUSPENDED
                cur.execute("""
                    UPDATE fhq_org.org_agents
                    SET is_suspended = TRUE,
                        suspension_reason = %s,
                        suspended_at = %s,
                        updated_at = %s
                    WHERE agent_id = %s
                """, (
                    f"ADR-009 Suspension - Request {request_id}: {rationale}",
                    now,
                    now,
                    agent_id
                ))

                # 3. Log audit entry for approval
                audit_data = {
                    'request_id': str(request_id),
                    'agent_id': agent_id,
                    'approver_id': approver_id,
                    'decision': 'APPROVED',
                    'rationale': rationale,
                    'timestamp': now.isoformat(),
                    'agent_suspended': True
                }
                audit_hash = self._generate_hash(audit_data)

                cur.execute("""
                    INSERT INTO fhq_governance.suspension_audit_log (
                        request_id, action_type, performed_by, action_data,
                        action_hash, signature
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    request_id,
                    AuditActionType.CEO_APPROVED.value,
                    approver_id,
                    Json(audit_data),
                    audit_hash,
                    self._generate_signature(approver_id, audit_hash)
                ))

                # 4. Log suspension enforcement
                enforce_data = {
                    'request_id': str(request_id),
                    'agent_id': agent_id,
                    'enforced_by': approver_id,
                    'enforcement_time': now.isoformat(),
                    'is_suspended': True
                }
                enforce_hash = self._generate_hash(enforce_data)

                cur.execute("""
                    INSERT INTO fhq_governance.suspension_audit_log (
                        request_id, action_type, performed_by, action_data,
                        action_hash, signature
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    request_id,
                    AuditActionType.SUSPENSION_ENFORCED.value,
                    approver_id,
                    Json(enforce_data),
                    enforce_hash,
                    self._generate_signature(approver_id, enforce_hash)
                ))

                self.db.conn.commit()

            self.logger.info(f"SUSPENSION APPROVED")
            self.logger.info(f"Agent {agent_id} is now SUSPENDED")
            self.logger.info(f"Orchestrator Worker will halt all tasks for {agent_id}")

            return True, f"Suspension approved. Agent {agent_id} is now SUSPENDED."

        except Exception as e:
            self.db.conn.rollback()
            self.logger.error(f"Failed to approve suspension: {e}")
            return False, f"Failed to approve: {e}"

    def reject_suspension(
        self,
        request_id: str,
        rationale: str,
        rejector_id: str = None
    ) -> Tuple[bool, str]:
        """
        Reject a suspension request (CEO Stage 2 - REJECT).

        Actions on REJECT:
          1. Set request status to REJECTED
          2. No suspension applied
          3. Log override in governance log
          4. Agent continues under elevated monitoring

        Args:
            request_id: UUID of the suspension request
            rationale: Reason for rejection (required for governance audit)
            rejector_id: ID of rejecting agent (defaults to LARS)

        Returns:
            Tuple of (success, message)
        """

        rejector_id = rejector_id or Config.CEO_AGENT_ID

        self.logger.info("=" * 70)
        self.logger.info("CEO SUSPENSION REJECTION - ADR-009 Stage 2")
        self.logger.info(f"Request ID: {request_id}")
        self.logger.info(f"Rejector: {rejector_id}")
        self.logger.info("=" * 70)

        # Get request
        request = self._get_request(request_id)
        if not request:
            msg = f"Suspension request not found: {request_id}"
            self.logger.error(msg)
            return False, msg

        # Verify request is PENDING
        if request['status'] != SuspensionStatus.PENDING.value:
            msg = f"Request is not pending. Current status: {request['status']}"
            self.logger.error(msg)
            return False, msg

        # Verify rejector has authority
        if not self.db.agent_exists(rejector_id):
            msg = f"Rejector agent {rejector_id} does not exist"
            self.logger.error(msg)
            return False, msg

        rejector_info = self.db.get_agent_info(rejector_id)
        if rejector_info['authority_level'] < 9:
            msg = f"Rejector {rejector_id} does not have CEO authority"
            self.logger.error(msg)
            return False, msg

        agent_id = request['agent_id']
        now = datetime.now(timezone.utc)

        try:
            with self.db.conn.cursor() as cur:
                # 1. Update suspension request status
                cur.execute("""
                    UPDATE fhq_governance.agent_suspension_requests
                    SET status = %s,
                        reviewed_by = %s,
                        reviewed_at = %s,
                        review_rationale = %s
                    WHERE request_id = %s
                """, (
                    SuspensionStatus.REJECTED.value,
                    rejector_id,
                    now,
                    rationale,
                    request_id
                ))

                # 2. Log audit entry for rejection
                audit_data = {
                    'request_id': str(request_id),
                    'agent_id': agent_id,
                    'rejector_id': rejector_id,
                    'decision': 'REJECTED',
                    'rationale': rationale,
                    'timestamp': now.isoformat(),
                    'override_logged': True,
                    'elevated_monitoring': True
                }
                audit_hash = self._generate_hash(audit_data)

                cur.execute("""
                    INSERT INTO fhq_governance.suspension_audit_log (
                        request_id, action_type, performed_by, action_data,
                        action_hash, signature
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    request_id,
                    AuditActionType.CEO_REJECTED.value,
                    rejector_id,
                    Json(audit_data),
                    audit_hash,
                    self._generate_signature(rejector_id, audit_hash)
                ))

                self.db.conn.commit()

            self.logger.info(f"SUSPENSION REJECTED")
            self.logger.info(f"Agent {agent_id} continues operating")
            self.logger.info(f"Override logged in governance audit trail")
            self.logger.info(f"Agent under elevated monitoring")

            return True, f"Suspension rejected. Agent {agent_id} continues with elevated monitoring."

        except Exception as e:
            self.db.conn.rollback()
            self.logger.error(f"Failed to reject suspension: {e}")
            return False, f"Failed to reject: {e}"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

class SuspensionWorkflowUtils:
    """Utility functions for suspension workflow"""

    def __init__(self, db: SuspensionWorkflowDB, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def list_pending_requests(self) -> List[Dict]:
        """List all pending suspension requests"""
        return self.db.execute_query("""
            SELECT
                r.request_id,
                r.agent_id,
                a.agent_name,
                a.agent_role,
                r.requested_by,
                r.reason,
                r.discrepancy_score,
                r.discrepancy_threshold,
                r.created_at,
                r.evidence
            FROM fhq_governance.agent_suspension_requests r
            JOIN fhq_org.org_agents a ON r.agent_id = a.agent_id
            WHERE r.status = 'PENDING'
            ORDER BY r.created_at DESC
        """)

    def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """Get comprehensive agent suspension status"""
        result = self.db.execute_query("""
            SELECT * FROM fhq_governance.get_agent_suspension_status(%s)
        """, (agent_id,))
        return result[0] if result else None

    def get_suspension_metrics(self) -> Dict:
        """Get suspension workflow metrics"""
        result = self.db.execute_query("""
            SELECT * FROM fhq_governance.v_suspension_metrics
        """)
        return result[0] if result else {}

    def reinstate_agent(self, agent_id: str, rationale: str, reinstated_by: str = None) -> Tuple[bool, str]:
        """Reinstate a suspended agent (manual action)"""

        reinstated_by = reinstated_by or Config.CEO_AGENT_ID

        self.logger.info(f"Reinstating agent: {agent_id}")

        if not self.db.is_agent_suspended(agent_id):
            return False, f"Agent {agent_id} is not suspended"

        try:
            with self.db.conn.cursor() as cur:
                # Update agent status
                cur.execute("""
                    UPDATE fhq_org.org_agents
                    SET is_suspended = FALSE,
                        suspension_reason = NULL,
                        suspended_at = NULL,
                        updated_at = NOW()
                    WHERE agent_id = %s
                """, (agent_id,))

                # Get the most recent approved suspension request
                request = self.db.execute_query("""
                    SELECT request_id FROM fhq_governance.agent_suspension_requests
                    WHERE agent_id = %s AND status = 'APPROVED'
                    ORDER BY created_at DESC LIMIT 1
                """, (agent_id,))

                if request:
                    request_id = request[0]['request_id']

                    # Log reinstatement
                    from psycopg2.extras import Json
                    reinstate_data = {
                        'agent_id': agent_id,
                        'reinstated_by': reinstated_by,
                        'rationale': rationale,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    reinstate_hash = hashlib.sha256(
                        json.dumps(reinstate_data, sort_keys=True).encode()
                    ).hexdigest()

                    cur.execute("""
                        INSERT INTO fhq_governance.suspension_audit_log (
                            request_id, action_type, performed_by, action_data,
                            action_hash, signature
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        request_id,
                        AuditActionType.AGENT_REINSTATED.value,
                        reinstated_by,
                        Json(reinstate_data),
                        reinstate_hash,
                        hashlib.sha256(f"{reinstated_by}:{reinstate_hash}".encode()).hexdigest()
                    ))

                self.db.conn.commit()

            self.logger.info(f"Agent {agent_id} reinstated")
            return True, f"Agent {agent_id} has been reinstated"

        except Exception as e:
            self.db.conn.rollback()
            self.logger.error(f"Failed to reinstate agent: {e}")
            return False, f"Failed to reinstate: {e}"


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for suspension workflow CLI"""

    parser = argparse.ArgumentParser(
        description='VEGA ADR-009 Suspension Workflow - Dual-approval agent suspension'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Recommend command (VEGA Stage 1)
    recommend_parser = subparsers.add_parser('recommend', help='Create suspension recommendation (VEGA)')
    recommend_parser.add_argument('--agent', required=True, help='Agent ID to recommend for suspension')
    recommend_parser.add_argument('--score', type=float, required=True, help='Discrepancy score')
    recommend_parser.add_argument('--reason', help='Optional reason text')

    # Approve command (CEO Stage 2)
    approve_parser = subparsers.add_parser('approve', help='Approve suspension request (CEO)')
    approve_parser.add_argument('--request-id', required=True, help='Request UUID to approve')
    approve_parser.add_argument('--rationale', required=True, help='Approval rationale')
    approve_parser.add_argument('--approver', help='Approver agent ID (default: LARS)')

    # Reject command (CEO Stage 2)
    reject_parser = subparsers.add_parser('reject', help='Reject suspension request (CEO)')
    reject_parser.add_argument('--request-id', required=True, help='Request UUID to reject')
    reject_parser.add_argument('--rationale', required=True, help='Rejection rationale')
    reject_parser.add_argument('--rejector', help='Rejector agent ID (default: LARS)')

    # List pending command
    list_parser = subparsers.add_parser('list-pending', help='List pending suspension requests')

    # Status command
    status_parser = subparsers.add_parser('status', help='Check agent suspension status')
    status_parser.add_argument('--agent', required=True, help='Agent ID to check')

    # Reinstate command
    reinstate_parser = subparsers.add_parser('reinstate', help='Reinstate a suspended agent')
    reinstate_parser.add_argument('--agent', required=True, help='Agent ID to reinstate')
    reinstate_parser.add_argument('--rationale', required=True, help='Reinstatement rationale')

    # Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Show suspension workflow metrics')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Setup
    logger = setup_logging()
    db = SuspensionWorkflowDB(Config.get_db_connection_string(), logger)

    if not db.connect():
        logger.error("Failed to connect to database")
        sys.exit(1)

    try:
        # Verify tables exist
        if not db.table_exists("fhq_governance", "agent_suspension_requests"):
            logger.error("agent_suspension_requests table not found. Run migration 019 first.")
            sys.exit(1)

        if args.command == 'recommend':
            recommender = VEGASuspensionRecommender(db, logger)
            success, msg, request_id = recommender.recommend_suspension(
                args.agent, args.score, args.reason
            )
            print(f"\n{'SUCCESS' if success else 'FAILED'}: {msg}")
            if request_id:
                print(f"Request ID: {request_id}")
            sys.exit(0 if success else 1)

        elif args.command == 'approve':
            handler = CEOApprovalHandler(db, logger)
            success, msg = handler.approve_suspension(
                args.request_id, args.rationale, args.approver
            )
            print(f"\n{'SUCCESS' if success else 'FAILED'}: {msg}")
            sys.exit(0 if success else 1)

        elif args.command == 'reject':
            handler = CEOApprovalHandler(db, logger)
            success, msg = handler.reject_suspension(
                args.request_id, args.rationale, args.rejector
            )
            print(f"\n{'SUCCESS' if success else 'FAILED'}: {msg}")
            sys.exit(0 if success else 1)

        elif args.command == 'list-pending':
            utils = SuspensionWorkflowUtils(db, logger)
            pending = utils.list_pending_requests()
            print(f"\n{'=' * 70}")
            print("PENDING SUSPENSION REQUESTS (Awaiting CEO Review)")
            print(f"{'=' * 70}")
            if pending:
                for req in pending:
                    print(f"\nRequest ID: {req['request_id']}")
                    print(f"  Agent: {req['agent_id']} ({req['agent_name']})")
                    print(f"  Role: {req['agent_role']}")
                    print(f"  Discrepancy Score: {req['discrepancy_score']}")
                    print(f"  Requested By: {req['requested_by']}")
                    print(f"  Created: {req['created_at']}")
                    print(f"  Reason: {req['reason'][:100]}...")
            else:
                print("\nNo pending suspension requests.")
            print(f"\n{'=' * 70}")

        elif args.command == 'status':
            utils = SuspensionWorkflowUtils(db, logger)
            status = utils.get_agent_status(args.agent)
            print(f"\n{'=' * 70}")
            print(f"AGENT SUSPENSION STATUS: {args.agent}")
            print(f"{'=' * 70}")
            if status:
                print(f"  Suspended: {status['is_suspended']}")
                print(f"  Pending Request: {status['has_pending_request']}")
                if status['pending_request_id']:
                    print(f"  Pending Request ID: {status['pending_request_id']}")
                if status['discrepancy_score']:
                    print(f"  Discrepancy Score: {status['discrepancy_score']}")
                if status['last_suspension_request_at']:
                    print(f"  Last Request: {status['last_suspension_request_at']}")
            else:
                print(f"  Agent {args.agent} not found")
            print(f"{'=' * 70}")

        elif args.command == 'reinstate':
            utils = SuspensionWorkflowUtils(db, logger)
            success, msg = utils.reinstate_agent(args.agent, args.rationale)
            print(f"\n{'SUCCESS' if success else 'FAILED'}: {msg}")
            sys.exit(0 if success else 1)

        elif args.command == 'metrics':
            utils = SuspensionWorkflowUtils(db, logger)
            metrics = utils.get_suspension_metrics()
            print(f"\n{'=' * 70}")
            print("SUSPENSION WORKFLOW METRICS")
            print(f"{'=' * 70}")
            print(f"  Pending Requests: {metrics.get('pending_requests', 0)}")
            print(f"  Approved Requests: {metrics.get('approved_requests', 0)}")
            print(f"  Rejected Requests: {metrics.get('rejected_requests', 0)}")
            print(f"  Total Requests: {metrics.get('total_requests', 0)}")
            print(f"  Unique Agents Flagged: {metrics.get('unique_agents_flagged', 0)}")
            if metrics.get('avg_review_time_seconds'):
                print(f"  Avg Review Time: {metrics['avg_review_time_seconds']:.1f}s")
            if metrics.get('max_discrepancy_score'):
                print(f"  Max Discrepancy Score: {metrics['max_discrepancy_score']}")
            print(f"{'=' * 70}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
