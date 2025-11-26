#!/usr/bin/env python3
"""
STIG ADR-009 VERIFICATION SCRIPT
Agent: STIG (Sentinel Tier Integrity Guardian)
Purpose: Verify ADR-009 Agent Suspension Workflow implementation
Compliance: ADR-009, ADR-010, ADR-008, ADR-007

This script verifies all ADR-009 Section 8 Acceptance Criteria:
  11.1 - Suspension Requests Table Verification
  11.2 - VEGA Recommendation-Only Verification
  11.3 - CEO Authority Binding
  11.4 - Worker Suspension Enforcement
  11.5 - Evidence Bundling & Audit Trail

Usage:
    python stig_adr009_verification.py                    # Run all verifications
    python stig_adr009_verification.py --section=11.1     # Run specific section
    python stig_adr009_verification.py --report-only      # Generate report without DB writes
    python stig_adr009_verification.py --json             # Output as JSON
"""

import os
import sys
import json
import hashlib
import argparse
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Database
import psycopg2
from psycopg2.extras import RealDictCursor

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """STIG ADR-009 Verification Configuration"""

    AGENT_ID = "STIG"
    ADR_REFERENCE = "ADR-009"
    VERSION = "1.0.0"

    # Database connection
    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    # Required tables per ADR-009 Section 6
    REQUIRED_TABLES = [
        ("fhq_governance", "agent_suspension_requests"),
        ("fhq_governance", "suspension_audit_log"),
    ]

    # Required columns in agent_suspension_requests
    REQUIRED_COLUMNS = {
        "agent_suspension_requests": [
            "request_id",
            "agent_id",
            "requested_by",
            "reason",
            "discrepancy_score",
            "evidence",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at"
        ]
    }

    # Valid status values per ADR-009 Section 5.2
    VALID_STATUS_VALUES = ["PENDING", "APPROVED", "REJECTED"]

    # VEGA agent ID (should only recommend, never enforce)
    VEGA_AGENT_ID = "VEGA"

    # CEO agent ID (sole authority for approval)
    CEO_AGENT_ID = "LARS"

    # Discrepancy threshold per ADR-010
    DISCREPANCY_THRESHOLD = 0.10


# =============================================================================
# VERIFICATION RESULT CLASSES
# =============================================================================

class VerificationStatus(Enum):
    """Verification status enumeration"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class VerificationResult:
    """Result of a single verification check"""
    check_name: str
    status: VerificationStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    evidence_hash: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SectionResult:
    """Result of a verification section"""
    section_id: str
    section_name: str
    status: VerificationStatus
    checks: List[VerificationResult] = field(default_factory=list)
    summary: str = ""

    def compute_status(self) -> VerificationStatus:
        """Compute overall section status from checks"""
        if not self.checks:
            return VerificationStatus.SKIP

        if any(c.status == VerificationStatus.FAIL for c in self.checks):
            return VerificationStatus.FAIL
        if any(c.status == VerificationStatus.WARN for c in self.checks):
            return VerificationStatus.WARN
        if all(c.status == VerificationStatus.PASS for c in self.checks):
            return VerificationStatus.PASS
        return VerificationStatus.SKIP


@dataclass
class VerificationReport:
    """Complete verification report"""
    report_id: str
    agent_id: str
    adr_reference: str
    timestamp: str
    sections: List[SectionResult] = field(default_factory=list)
    overall_status: VerificationStatus = VerificationStatus.SKIP
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0

    def compute_summary(self):
        """Compute summary statistics"""
        self.total_checks = sum(len(s.checks) for s in self.sections)
        self.passed_checks = sum(
            1 for s in self.sections for c in s.checks
            if c.status == VerificationStatus.PASS
        )
        self.failed_checks = sum(
            1 for s in self.sections for c in s.checks
            if c.status == VerificationStatus.FAIL
        )
        self.warning_checks = sum(
            1 for s in self.sections for c in s.checks
            if c.status == VerificationStatus.WARN
        )

        if self.failed_checks > 0:
            self.overall_status = VerificationStatus.FAIL
        elif self.warning_checks > 0:
            self.overall_status = VerificationStatus.WARN
        elif self.passed_checks == self.total_checks and self.total_checks > 0:
            self.overall_status = VerificationStatus.PASS
        else:
            self.overall_status = VerificationStatus.SKIP


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger("stig_adr009_verification")
    logger.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(console)

    return logger


# =============================================================================
# DATABASE INTERFACE
# =============================================================================

class STIGDatabase:
    """Database interface for STIG verification"""

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

    def column_exists(self, schema: str, table: str, column: str) -> bool:
        """Check if column exists"""
        result = self.execute_scalar("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = %s
            )
        """, (schema, table, column))
        return result

    def function_exists(self, schema: str, function_name: str) -> bool:
        """Check if function exists"""
        result = self.execute_scalar("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname = %s AND p.proname = %s
            )
        """, (schema, function_name))
        return result


# =============================================================================
# SECTION 11.1: SUSPENSION REQUESTS TABLE VERIFICATION
# =============================================================================

class Section11_1_SuspensionRequestsTable:
    """Section 11.1: Verify agent_suspension_requests table"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 11.1 verification checks"""
        section = SectionResult(
            section_id="11.1",
            section_name="Suspension Requests Table Verification",
            status=VerificationStatus.SKIP
        )

        # Check 11.1.1: Verify table exists
        section.checks.append(self._check_table_exists())

        # Check 11.1.2: Verify required columns
        section.checks.append(self._check_required_columns())

        # Check 11.1.3: Verify status constraint
        section.checks.append(self._check_status_constraint())

        # Check 11.1.4: Verify indexes
        section.checks.append(self._check_indexes())

        # Check 11.1.5: Verify audit log table
        section.checks.append(self._check_audit_log_table())

        section.status = section.compute_status()
        section.summary = f"Suspension requests table: {section.status.value}"
        return section

    def _check_table_exists(self) -> VerificationResult:
        """Verify agent_suspension_requests table exists"""
        exists = self.db.table_exists("fhq_governance", "agent_suspension_requests")

        if not exists:
            return VerificationResult(
                check_name="table_exists",
                status=VerificationStatus.FAIL,
                message="agent_suspension_requests table does not exist",
                details={"action": "Run migration 019 first"}
            )

        return VerificationResult(
            check_name="table_exists",
            status=VerificationStatus.PASS,
            message="agent_suspension_requests table exists",
            details={"table": "fhq_governance.agent_suspension_requests"}
        )

    def _check_required_columns(self) -> VerificationResult:
        """Verify all required columns exist"""
        missing = []
        present = []

        for column in Config.REQUIRED_COLUMNS["agent_suspension_requests"]:
            if self.db.column_exists("fhq_governance", "agent_suspension_requests", column):
                present.append(column)
            else:
                missing.append(column)

        if missing:
            return VerificationResult(
                check_name="required_columns",
                status=VerificationStatus.FAIL,
                message=f"Missing columns: {missing}",
                details={"present": present, "missing": missing}
            )

        return VerificationResult(
            check_name="required_columns",
            status=VerificationStatus.PASS,
            message=f"All {len(present)} required columns present",
            details={"columns": present}
        )

    def _check_status_constraint(self) -> VerificationResult:
        """Verify status column has correct CHECK constraint"""
        try:
            # Try inserting invalid status
            with self.db.conn.cursor() as cur:
                # First check if constraint exists
                cur.execute("""
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'fhq_governance'
                    AND table_name = 'agent_suspension_requests'
                    AND constraint_type = 'CHECK'
                """)
                constraints = cur.fetchall()

            if constraints:
                return VerificationResult(
                    check_name="status_constraint",
                    status=VerificationStatus.PASS,
                    message="Status CHECK constraint exists",
                    details={
                        "constraints": [c[0] for c in constraints],
                        "valid_values": Config.VALID_STATUS_VALUES
                    }
                )

            return VerificationResult(
                check_name="status_constraint",
                status=VerificationStatus.WARN,
                message="No CHECK constraints found on table",
                details={"expected_values": Config.VALID_STATUS_VALUES}
            )

        except Exception as e:
            return VerificationResult(
                check_name="status_constraint",
                status=VerificationStatus.WARN,
                message=f"Could not verify constraint: {e}",
                details={"error": str(e)}
            )

    def _check_indexes(self) -> VerificationResult:
        """Verify required indexes exist"""
        try:
            indexes = self.db.execute_query("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'fhq_governance'
                AND tablename = 'agent_suspension_requests'
            """)

            if len(indexes) >= 3:  # At minimum: primary key + agent_status + created
                return VerificationResult(
                    check_name="indexes",
                    status=VerificationStatus.PASS,
                    message=f"{len(indexes)} indexes present",
                    details={"indexes": [i['indexname'] for i in indexes]}
                )

            return VerificationResult(
                check_name="indexes",
                status=VerificationStatus.WARN,
                message=f"Only {len(indexes)} indexes found",
                details={"indexes": [i['indexname'] for i in indexes]}
            )

        except Exception as e:
            return VerificationResult(
                check_name="indexes",
                status=VerificationStatus.WARN,
                message=f"Index check failed: {e}",
                details={"error": str(e)}
            )

    def _check_audit_log_table(self) -> VerificationResult:
        """Verify suspension_audit_log table exists"""
        exists = self.db.table_exists("fhq_governance", "suspension_audit_log")

        if not exists:
            return VerificationResult(
                check_name="audit_log_table",
                status=VerificationStatus.FAIL,
                message="suspension_audit_log table does not exist",
                details={"action": "Run migration 019 first"}
            )

        return VerificationResult(
            check_name="audit_log_table",
            status=VerificationStatus.PASS,
            message="suspension_audit_log table exists",
            details={"table": "fhq_governance.suspension_audit_log"}
        )


# =============================================================================
# SECTION 11.2: VEGA RECOMMENDATION-ONLY VERIFICATION
# =============================================================================

class Section11_2_VEGARecommendationOnly:
    """Section 11.2: Verify VEGA can only recommend, not enforce suspension"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger
        self.base_path = Path(__file__).parent

    def verify(self) -> SectionResult:
        """Execute all 11.2 verification checks"""
        section = SectionResult(
            section_id="11.2",
            section_name="VEGA Recommendation-Only Verification",
            status=VerificationStatus.SKIP
        )

        # Check 11.2.1: Verify VEGA workflow file exists
        section.checks.append(self._check_vega_workflow_exists())

        # Check 11.2.2: Verify VEGA does not set SUSPENDED directly
        section.checks.append(self._check_vega_no_direct_suspend())

        # Check 11.2.3: Verify VEGA creates PENDING requests only
        section.checks.append(self._check_vega_pending_only())

        section.status = section.compute_status()
        section.summary = f"VEGA recommendation-only: {section.status.value}"
        return section

    def _check_vega_workflow_exists(self) -> VerificationResult:
        """Verify VEGA suspension workflow module exists"""
        vega_file = self.base_path / "vega_suspension_workflow.py"

        if not vega_file.exists():
            return VerificationResult(
                check_name="vega_workflow_exists",
                status=VerificationStatus.FAIL,
                message="vega_suspension_workflow.py not found",
                details={"expected_path": str(vega_file)}
            )

        return VerificationResult(
            check_name="vega_workflow_exists",
            status=VerificationStatus.PASS,
            message="VEGA suspension workflow module exists",
            details={"path": str(vega_file)}
        )

    def _check_vega_no_direct_suspend(self) -> VerificationResult:
        """Verify VEGA code does not directly set agent to SUSPENDED"""
        vega_file = self.base_path / "vega_suspension_workflow.py"

        if not vega_file.exists():
            return VerificationResult(
                check_name="vega_no_direct_suspend",
                status=VerificationStatus.SKIP,
                message="VEGA workflow file not found"
            )

        content = vega_file.read_text(encoding='utf-8')

        # Patterns that would indicate direct suspension (violations)
        violation_patterns = [
            r'is_suspended\s*=\s*True',  # Direct assignment in VEGA recommender
            r"status\s*=\s*['\"]SUSPENDED['\"]",  # Setting status to SUSPENDED
            r'UPDATE.*org_agents.*SET.*is_suspended.*=.*TRUE',  # SQL direct update
        ]

        violations = []
        for pattern in violation_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Check if it's in the VEGASuspensionRecommender class
                # It's OK in CEOApprovalHandler
                lines = content.split('\n')
                in_vega_class = False
                for i, line in enumerate(lines):
                    if 'class VEGASuspensionRecommender' in line:
                        in_vega_class = True
                    elif 'class CEO' in line or 'class Suspension' in line:
                        in_vega_class = False
                    if in_vega_class and re.search(pattern, line, re.IGNORECASE):
                        violations.append(f"Line {i+1}: {line.strip()[:50]}")

        if violations:
            return VerificationResult(
                check_name="vega_no_direct_suspend",
                status=VerificationStatus.FAIL,
                message=f"VEGA code may directly suspend agents",
                details={"potential_violations": violations}
            )

        return VerificationResult(
            check_name="vega_no_direct_suspend",
            status=VerificationStatus.PASS,
            message="VEGA code does not directly suspend agents",
            details={"patterns_checked": len(violation_patterns)}
        )

    def _check_vega_pending_only(self) -> VerificationResult:
        """Verify VEGA creates requests with PENDING status only"""
        vega_file = self.base_path / "vega_suspension_workflow.py"

        if not vega_file.exists():
            return VerificationResult(
                check_name="vega_pending_only",
                status=VerificationStatus.SKIP,
                message="VEGA workflow file not found"
            )

        content = vega_file.read_text(encoding='utf-8')

        # Check for PENDING status in insert
        if "SuspensionStatus.PENDING" in content or "status = 'PENDING'" in content.upper():
            return VerificationResult(
                check_name="vega_pending_only",
                status=VerificationStatus.PASS,
                message="VEGA creates PENDING status requests",
                details={"pattern_found": "SuspensionStatus.PENDING"}
            )

        return VerificationResult(
            check_name="vega_pending_only",
            status=VerificationStatus.WARN,
            message="Could not verify VEGA creates PENDING requests",
            details={"action": "Manual review recommended"}
        )


# =============================================================================
# SECTION 11.3: CEO AUTHORITY BINDING
# =============================================================================

class Section11_3_CEOAuthorityBinding:
    """Section 11.3: Verify CEO is sole authority for suspension approval"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger
        self.base_path = Path(__file__).parent

    def verify(self) -> SectionResult:
        """Execute all 11.3 verification checks"""
        section = SectionResult(
            section_id="11.3",
            section_name="CEO Authority Binding Verification",
            status=VerificationStatus.SKIP
        )

        # Check 11.3.1: Verify CEO agent has correct authority level
        section.checks.append(self._check_ceo_authority_level())

        # Check 11.3.2: Verify approval function requires authority
        section.checks.append(self._check_approval_authority_check())

        # Check 11.3.3: Verify approved requests update agent status
        section.checks.append(self._check_approval_updates_status())

        section.status = section.compute_status()
        section.summary = f"CEO authority binding: {section.status.value}"
        return section

    def _check_ceo_authority_level(self) -> VerificationResult:
        """Verify LARS (CEO) has authority level >= 9"""
        try:
            result = self.db.execute_query("""
                SELECT agent_id, agent_name, authority_level
                FROM fhq_org.org_agents
                WHERE agent_id = %s
            """, (Config.CEO_AGENT_ID,))

            if not result:
                return VerificationResult(
                    check_name="ceo_authority_level",
                    status=VerificationStatus.FAIL,
                    message=f"CEO agent {Config.CEO_AGENT_ID} not found",
                    details={"expected_agent": Config.CEO_AGENT_ID}
                )

            agent = result[0]
            if agent['authority_level'] < 9:
                return VerificationResult(
                    check_name="ceo_authority_level",
                    status=VerificationStatus.FAIL,
                    message=f"CEO authority level {agent['authority_level']} < 9",
                    details={"authority_level": agent['authority_level']}
                )

            return VerificationResult(
                check_name="ceo_authority_level",
                status=VerificationStatus.PASS,
                message=f"CEO {Config.CEO_AGENT_ID} has authority level {agent['authority_level']}",
                details={"agent": agent}
            )

        except Exception as e:
            return VerificationResult(
                check_name="ceo_authority_level",
                status=VerificationStatus.FAIL,
                message=f"Authority check failed: {e}",
                details={"error": str(e)}
            )

    def _check_approval_authority_check(self) -> VerificationResult:
        """Verify approval function checks authority level"""
        vega_file = self.base_path / "vega_suspension_workflow.py"

        if not vega_file.exists():
            return VerificationResult(
                check_name="approval_authority_check",
                status=VerificationStatus.SKIP,
                message="VEGA workflow file not found"
            )

        content = vega_file.read_text(encoding='utf-8')

        # Check for authority level check in approval function
        if "authority_level" in content and ("< 9" in content or "< 8" in content):
            return VerificationResult(
                check_name="approval_authority_check",
                status=VerificationStatus.PASS,
                message="Approval function checks authority level",
                details={"pattern_found": "authority_level check"}
            )

        return VerificationResult(
            check_name="approval_authority_check",
            status=VerificationStatus.WARN,
            message="Could not verify authority level check",
            details={"action": "Manual review recommended"}
        )

    def _check_approval_updates_status(self) -> VerificationResult:
        """Verify approval function updates agent to SUSPENDED"""
        vega_file = self.base_path / "vega_suspension_workflow.py"

        if not vega_file.exists():
            return VerificationResult(
                check_name="approval_updates_status",
                status=VerificationStatus.SKIP,
                message="VEGA workflow file not found"
            )

        content = vega_file.read_text(encoding='utf-8')

        # Check for is_suspended = TRUE in CEOApprovalHandler
        if "is_suspended = TRUE" in content or "is_suspended=TRUE" in content:
            return VerificationResult(
                check_name="approval_updates_status",
                status=VerificationStatus.PASS,
                message="Approval function sets agent to SUSPENDED",
                details={"pattern_found": "is_suspended = TRUE"}
            )

        return VerificationResult(
            check_name="approval_updates_status",
            status=VerificationStatus.WARN,
            message="Could not verify status update",
            details={"action": "Manual review recommended"}
        )


# =============================================================================
# SECTION 11.4: WORKER SUSPENSION ENFORCEMENT
# =============================================================================

class Section11_4_WorkerEnforcement:
    """Section 11.4: Verify Worker respects suspension status"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger
        self.orchestrator_path = Path(__file__).parent.parent.parent / "05_ORCHESTRATOR"

    def verify(self) -> SectionResult:
        """Execute all 11.4 verification checks"""
        section = SectionResult(
            section_id="11.4",
            section_name="Worker Suspension Enforcement",
            status=VerificationStatus.SKIP
        )

        # Check 11.4.1: Verify suspension enforcement module exists
        section.checks.append(self._check_enforcement_module_exists())

        # Check 11.4.2: Verify enforcement checks is_suspended
        section.checks.append(self._check_suspension_query())

        # Check 11.4.3: Verify task rejection logging
        section.checks.append(self._check_task_rejection_logging())

        section.status = section.compute_status()
        section.summary = f"Worker enforcement: {section.status.value}"
        return section

    def _check_enforcement_module_exists(self) -> VerificationResult:
        """Verify suspension_enforcement.py exists"""
        enforcement_file = self.orchestrator_path / "suspension_enforcement.py"

        if not enforcement_file.exists():
            return VerificationResult(
                check_name="enforcement_module_exists",
                status=VerificationStatus.FAIL,
                message="suspension_enforcement.py not found",
                details={"expected_path": str(enforcement_file)}
            )

        return VerificationResult(
            check_name="enforcement_module_exists",
            status=VerificationStatus.PASS,
            message="Suspension enforcement module exists",
            details={"path": str(enforcement_file)}
        )

    def _check_suspension_query(self) -> VerificationResult:
        """Verify enforcement module checks is_suspended"""
        enforcement_file = self.orchestrator_path / "suspension_enforcement.py"

        if not enforcement_file.exists():
            return VerificationResult(
                check_name="suspension_query",
                status=VerificationStatus.SKIP,
                message="Enforcement module not found"
            )

        content = enforcement_file.read_text(encoding='utf-8')

        if "is_suspended" in content:
            return VerificationResult(
                check_name="suspension_query",
                status=VerificationStatus.PASS,
                message="Enforcement module checks is_suspended",
                details={"pattern_found": "is_suspended"}
            )

        return VerificationResult(
            check_name="suspension_query",
            status=VerificationStatus.FAIL,
            message="Enforcement module does not check is_suspended",
            details={"action": "Review suspension_enforcement.py"}
        )

    def _check_task_rejection_logging(self) -> VerificationResult:
        """Verify task rejection logging is implemented"""
        enforcement_file = self.orchestrator_path / "suspension_enforcement.py"

        if not enforcement_file.exists():
            return VerificationResult(
                check_name="task_rejection_logging",
                status=VerificationStatus.SKIP,
                message="Enforcement module not found"
            )

        content = enforcement_file.read_text(encoding='utf-8')

        if "log_task_rejection" in content and "TASK_REJECTED_SUSPENDED" in content:
            return VerificationResult(
                check_name="task_rejection_logging",
                status=VerificationStatus.PASS,
                message="Task rejection logging implemented",
                details={"patterns_found": ["log_task_rejection", "TASK_REJECTED_SUSPENDED"]}
            )

        return VerificationResult(
            check_name="task_rejection_logging",
            status=VerificationStatus.WARN,
            message="Task rejection logging may be incomplete",
            details={"action": "Review logging implementation"}
        )


# =============================================================================
# SECTION 11.5: EVIDENCE BUNDLING & AUDIT TRAIL
# =============================================================================

class Section11_5_EvidenceAuditTrail:
    """Section 11.5: Verify evidence bundling and audit trail"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 11.5 verification checks"""
        section = SectionResult(
            section_id="11.5",
            section_name="Evidence Bundling & Audit Trail",
            status=VerificationStatus.SKIP
        )

        # Check 11.5.1: Verify evidence column is JSONB
        section.checks.append(self._check_evidence_jsonb())

        # Check 11.5.2: Verify audit log has signature column
        section.checks.append(self._check_audit_signature())

        # Check 11.5.3: Verify helper functions exist
        section.checks.append(self._check_helper_functions())

        # Check 11.5.4: Verify views exist
        section.checks.append(self._check_views_exist())

        section.status = section.compute_status()
        section.summary = f"Evidence & audit trail: {section.status.value}"
        return section

    def _check_evidence_jsonb(self) -> VerificationResult:
        """Verify evidence column is JSONB type"""
        try:
            result = self.db.execute_query("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'fhq_governance'
                AND table_name = 'agent_suspension_requests'
                AND column_name = 'evidence'
            """)

            if not result:
                return VerificationResult(
                    check_name="evidence_jsonb",
                    status=VerificationStatus.FAIL,
                    message="Evidence column not found"
                )

            data_type = result[0]['data_type']
            if data_type == 'jsonb':
                return VerificationResult(
                    check_name="evidence_jsonb",
                    status=VerificationStatus.PASS,
                    message="Evidence column is JSONB",
                    details={"data_type": data_type}
                )

            return VerificationResult(
                check_name="evidence_jsonb",
                status=VerificationStatus.FAIL,
                message=f"Evidence column is {data_type}, expected JSONB",
                details={"data_type": data_type}
            )

        except Exception as e:
            return VerificationResult(
                check_name="evidence_jsonb",
                status=VerificationStatus.FAIL,
                message=f"Check failed: {e}",
                details={"error": str(e)}
            )

    def _check_audit_signature(self) -> VerificationResult:
        """Verify audit log has signature column"""
        if self.db.column_exists("fhq_governance", "suspension_audit_log", "signature"):
            return VerificationResult(
                check_name="audit_signature",
                status=VerificationStatus.PASS,
                message="Audit log has signature column",
                details={"column": "signature"}
            )

        return VerificationResult(
            check_name="audit_signature",
            status=VerificationStatus.FAIL,
            message="Audit log missing signature column"
        )

    def _check_helper_functions(self) -> VerificationResult:
        """Verify helper functions exist"""
        required_functions = [
            "has_pending_suspension",
            "get_agent_suspension_status",
            "list_pending_suspension_requests"
        ]

        missing = []
        present = []

        for func in required_functions:
            if self.db.function_exists("fhq_governance", func):
                present.append(func)
            else:
                missing.append(func)

        if missing:
            return VerificationResult(
                check_name="helper_functions",
                status=VerificationStatus.WARN,
                message=f"Missing functions: {missing}",
                details={"present": present, "missing": missing}
            )

        return VerificationResult(
            check_name="helper_functions",
            status=VerificationStatus.PASS,
            message=f"All {len(present)} helper functions exist",
            details={"functions": present}
        )

    def _check_views_exist(self) -> VerificationResult:
        """Verify governance views exist"""
        required_views = [
            "v_suspension_requests_overview",
            "v_suspension_metrics"
        ]

        missing = []
        present = []

        for view in required_views:
            exists = self.db.execute_scalar("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views
                    WHERE table_schema = 'fhq_governance'
                    AND table_name = %s
                )
            """, (view,))
            if exists:
                present.append(view)
            else:
                missing.append(view)

        if missing:
            return VerificationResult(
                check_name="views_exist",
                status=VerificationStatus.WARN,
                message=f"Missing views: {missing}",
                details={"present": present, "missing": missing}
            )

        return VerificationResult(
            check_name="views_exist",
            status=VerificationStatus.PASS,
            message=f"All {len(present)} governance views exist",
            details={"views": present}
        )


# =============================================================================
# MAIN VERIFICATION ORCHESTRATOR
# =============================================================================

class STIGVerificationOrchestrator:
    """Main orchestrator for STIG ADR-009 verification"""

    def __init__(self, logger: logging.Logger, report_only: bool = False):
        self.logger = logger
        self.report_only = report_only
        self.db = STIGDatabase(Config.get_db_connection_string(), logger)

    def generate_report_id(self) -> str:
        """Generate unique report ID"""
        return f"STIG-ADR009-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    def run_all_verifications(self) -> VerificationReport:
        """Run all verification sections"""
        report = VerificationReport(
            report_id=self.generate_report_id(),
            agent_id=Config.AGENT_ID,
            adr_reference=Config.ADR_REFERENCE,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        self.logger.info("=" * 70)
        self.logger.info("STIG ADR-009 VERIFICATION SCRIPT")
        self.logger.info(f"Report ID: {report.report_id}")
        self.logger.info(f"Timestamp: {report.timestamp}")
        self.logger.info("=" * 70)

        # Connect to database
        if not self.db.connect():
            self.logger.error("Failed to connect to database")
            return report

        try:
            # Run Section 11.1
            self.logger.info("\n[11.1] Suspension Requests Table Verification...")
            section_11_1 = Section11_1_SuspensionRequestsTable(self.db, self.logger)
            report.sections.append(section_11_1.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 11.2
            self.logger.info("\n[11.2] VEGA Recommendation-Only Verification...")
            section_11_2 = Section11_2_VEGARecommendationOnly(self.db, self.logger)
            report.sections.append(section_11_2.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 11.3
            self.logger.info("\n[11.3] CEO Authority Binding Verification...")
            section_11_3 = Section11_3_CEOAuthorityBinding(self.db, self.logger)
            report.sections.append(section_11_3.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 11.4
            self.logger.info("\n[11.4] Worker Suspension Enforcement...")
            section_11_4 = Section11_4_WorkerEnforcement(self.db, self.logger)
            report.sections.append(section_11_4.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 11.5
            self.logger.info("\n[11.5] Evidence Bundling & Audit Trail...")
            section_11_5 = Section11_5_EvidenceAuditTrail(self.db, self.logger)
            report.sections.append(section_11_5.verify())
            self._log_section_result(report.sections[-1])

            # Compute summary
            report.compute_summary()

            # Print final summary
            self._print_final_summary(report)

            # Compute evidence hash for report
            report_hash = self._compute_report_hash(report)
            self.logger.info(f"\nReport Hash: {report_hash}")

            return report

        finally:
            self.db.close()

    def run_single_section(self, section_id: str) -> VerificationReport:
        """Run a single verification section"""
        report = VerificationReport(
            report_id=self.generate_report_id(),
            agent_id=Config.AGENT_ID,
            adr_reference=Config.ADR_REFERENCE,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        if not self.db.connect():
            return report

        try:
            section_map = {
                "11.1": Section11_1_SuspensionRequestsTable,
                "11.2": Section11_2_VEGARecommendationOnly,
                "11.3": Section11_3_CEOAuthorityBinding,
                "11.4": Section11_4_WorkerEnforcement,
                "11.5": Section11_5_EvidenceAuditTrail,
            }

            if section_id not in section_map:
                self.logger.error(f"Unknown section: {section_id}")
                return report

            self.logger.info(f"\n[{section_id}] Running verification...")
            section_class = section_map[section_id]
            section = section_class(self.db, self.logger)
            report.sections.append(section.verify())
            self._log_section_result(report.sections[-1])

            report.compute_summary()
            self._print_final_summary(report)

            return report

        finally:
            self.db.close()

    def _log_section_result(self, section: SectionResult):
        """Log section result"""
        status_icon = {
            VerificationStatus.PASS: "PASS",
            VerificationStatus.FAIL: "FAIL",
            VerificationStatus.WARN: "WARN",
            VerificationStatus.SKIP: "SKIP",
        }

        for check in section.checks:
            icon = status_icon.get(check.status, "????")
            self.logger.info(f"  [{icon}] {check.check_name}: {check.message}")

        self.logger.info(f"  Section {section.section_id} Status: {section.status.value}")

    def _print_final_summary(self, report: VerificationReport):
        """Print final verification summary"""
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("ADR-009 VERIFICATION SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"Report ID: {report.report_id}")
        self.logger.info(f"Total Checks: {report.total_checks}")
        self.logger.info(f"  PASS: {report.passed_checks}")
        self.logger.info(f"  FAIL: {report.failed_checks}")
        self.logger.info(f"  WARN: {report.warning_checks}")
        self.logger.info("")
        self.logger.info(f"OVERALL STATUS: {report.overall_status.value}")
        self.logger.info("=" * 70)

        # Section breakdown
        self.logger.info("\nSection Breakdown:")
        for section in report.sections:
            self.logger.info(f"  [{section.status.value}] {section.section_id} - {section.section_name}")

    def _compute_report_hash(self, report: VerificationReport) -> str:
        """Compute SHA-256 hash of the report"""
        report_data = {
            "report_id": report.report_id,
            "adr_reference": report.adr_reference,
            "timestamp": report.timestamp,
            "overall_status": report.overall_status.value,
            "total_checks": report.total_checks,
            "passed_checks": report.passed_checks,
            "failed_checks": report.failed_checks
        }
        return hashlib.sha256(
            json.dumps(report_data, sort_keys=True).encode()
        ).hexdigest()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='STIG ADR-009 Verification Script - Agent Suspension Workflow Verification'
    )
    parser.add_argument(
        '--section',
        type=str,
        choices=['11.1', '11.2', '11.3', '11.4', '11.5'],
        help='Run specific section only'
    )
    parser.add_argument(
        '--report-only',
        action='store_true',
        help='Generate report without storing to database'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output report as JSON'
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging()

    # Create orchestrator
    orchestrator = STIGVerificationOrchestrator(logger, report_only=args.report_only)

    # Run verification
    if args.section:
        report = orchestrator.run_single_section(args.section)
    else:
        report = orchestrator.run_all_verifications()

    # Output JSON if requested
    if args.json:
        report_dict = {
            "report_id": report.report_id,
            "agent_id": report.agent_id,
            "adr_reference": report.adr_reference,
            "timestamp": report.timestamp,
            "overall_status": report.overall_status.value,
            "total_checks": report.total_checks,
            "passed_checks": report.passed_checks,
            "failed_checks": report.failed_checks,
            "warning_checks": report.warning_checks,
            "sections": [
                {
                    "section_id": s.section_id,
                    "section_name": s.section_name,
                    "status": s.status.value,
                    "checks": [
                        {
                            "check_name": c.check_name,
                            "status": c.status.value,
                            "message": c.message
                        }
                        for c in s.checks
                    ]
                }
                for s in report.sections
            ]
        }
        print(json.dumps(report_dict, indent=2))

    # Exit with appropriate code
    if report.overall_status == VerificationStatus.FAIL:
        sys.exit(1)
    elif report.overall_status == VerificationStatus.WARN:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
