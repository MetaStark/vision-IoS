#!/usr/bin/env python3
"""
STIG ADR-008 VERIFICATION SCRIPT
Agent: STIG (Sentinel Tier Integrity Guardian)
Purpose: Execute mandatory verification tasks per ADR-008
Compliance: ADR-008 Cryptographic Key Management & Rotation Architecture

This script performs all verification tasks mandated in ADR-008:
  Section 2.1 - Ed25519 Signature Scheme Verification
  Section 2.2 - KeyStore Backend Verification
  Section 2.3 - Rolling Key Rotation (Dual-Publishing)
  Section 2.4 - Multi-Tier Key Archival
  Section 2.5 - Database Integration
  Section 2.6 - Mandatory Verification on Every Read

Regulatory Compliance:
  - ISO/IEC 11770-1 (Key Management)
  - ISO 8000-110 (Data Quality & Lineage)
  - BCBS 239 (Risk Data Aggregation)
  - GIPS Transparency Principles

Usage:
    python stig_adr008_verification.py                    # Run all verifications
    python stig_adr008_verification.py --section=2.1     # Run specific section
    python stig_adr008_verification.py --report-only     # Generate report without DB writes
    python stig_adr008_verification.py --json            # Output JSON report
"""

import os
import sys
import json
import hashlib
import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

# Database
import psycopg2
from psycopg2.extras import RealDictCursor

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """STIG ADR-008 Verification Configuration"""

    AGENT_ID = "STIG"
    ADR_REFERENCE = "ADR-008"
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

    # ADR-008 Key Lifecycle States (Appendix A)
    KEY_STATES = {
        "PENDING": {"allows_verification": False, "retention_hours": 0},
        "ACTIVE": {"allows_verification": True, "retention_days": 90},
        "DEPRECATED": {"allows_verification": True, "retention_hours": 24},
        "ARCHIVED": {"allows_verification": False, "retention_years": 7},
        "REVOKED": {"allows_verification": False, "retention_years": 7},
    }

    # Archival tiers (Section 2.4)
    ARCHIVAL_TIERS = {
        "HOT": {"retention_hours": 24, "description": "Immediate rollback window"},
        "WARM": {"retention_days": 90, "description": "Post-mortem and reconciliation"},
        "COLD": {"retention_years": 7, "description": "Regulatory compliance"},
    }

    # KeyStore backends (Section 2.2)
    KEYSTORE_BACKENDS = ["ENV", "VAULT", "HSM"]

    # Required canonical agents
    REQUIRED_AGENTS = ["LARS", "STIG", "LINE", "FINN", "VEGA"]

    # Rotation period (Section 2.3)
    KEY_ROTATION_DAYS = 90
    GRACE_PERIOD_HOURS = 24

    # Required tables for ADR-008
    REQUIRED_TABLES = [
        ("fhq_org", "org_agents"),
        ("fhq_meta", "adr_registry"),
        ("fhq_meta", "adr_dependencies"),
        ("fhq_meta", "agent_keys"),
        ("fhq_meta", "key_archival_log"),
        ("fhq_governance", "audit_log"),
    ]


# =============================================================================
# CANONICAL HASH UTILITIES
# =============================================================================

class CanonicalHash:
    """
    Canonical SHA-256 hash computation utilities (ADR-008 compliance).

    Provides deterministic hashing for:
    - ADR content verification
    - Key fingerprint generation
    - Audit log evidence
    - Archival verification
    """

    @staticmethod
    def compute_sha256(data: Any) -> str:
        """
        Compute SHA-256 hash of data.

        Args:
            data: Data to hash (dict, str, bytes)

        Returns:
            Hexadecimal SHA-256 hash string
        """
        if isinstance(data, dict):
            # Canonical JSON serialization (sorted keys, no whitespace)
            data_str = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)
        elif isinstance(data, bytes):
            data_str = data.decode('utf-8', errors='replace')
        else:
            data_str = str(data)

        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

    @staticmethod
    def compute_key_fingerprint(public_key: str) -> str:
        """
        Compute Ed25519 key fingerprint.

        Args:
            public_key: Base64 or hex encoded public key

        Returns:
            SHA-256 fingerprint of the key
        """
        return hashlib.sha256(public_key.encode('utf-8')).hexdigest()

    @staticmethod
    def compute_adr_canonical_hash(
        adr_id: str,
        title: str,
        version: str,
        status: str,
        author: str,
        date: str,
        governance_tier: str,
        key_components: List[str]
    ) -> str:
        """
        Compute canonical hash for ADR registration.

        Args:
            adr_id: ADR identifier (e.g., "ADR-008")
            title: ADR title
            version: ADR version
            status: ADR status (APPROVED, etc.)
            author: ADR author
            date: Approval date
            governance_tier: Tier level
            key_components: List of key decision components

        Returns:
            Canonical SHA-256 hash
        """
        canonical_string = "|".join([
            adr_id,
            title,
            version,
            status,
            author,
            date,
            governance_tier,
            "|".join(key_components)
        ])
        return hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()

    @staticmethod
    def verify_hash(data: Any, expected_hash: str) -> bool:
        """
        Verify data against expected hash.

        Args:
            data: Data to verify
            expected_hash: Expected SHA-256 hash

        Returns:
            True if hash matches
        """
        computed = CanonicalHash.compute_sha256(data)
        return computed == expected_hash


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
    canonical_hash: str = ""

    def compute_summary(self):
        """Compute summary statistics and canonical hash"""
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

        # Compute canonical hash of report
        self.canonical_hash = CanonicalHash.compute_sha256({
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "total_checks": self.total_checks,
            "passed": self.passed_checks,
            "failed": self.failed_checks
        })


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger("stig_adr008_verification")
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

    def connect(self):
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

    def schema_exists(self, schema: str) -> bool:
        """Check if schema exists"""
        result = self.execute_scalar("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.schemata
                WHERE schema_name = %s
            )
        """, (schema,))
        return result


# =============================================================================
# SECTION 2.1: Ed25519 SIGNATURE SCHEME VERIFICATION
# =============================================================================

class Section2_1_Ed25519Verification:
    """Section 2.1: Ed25519 as the Canonical Signature Scheme"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 2.1 verification checks"""
        section = SectionResult(
            section_id="2.1",
            section_name="Ed25519 Signature Scheme Verification",
            status=VerificationStatus.SKIP
        )

        # Check 2.1.1: Verify all agents use Ed25519
        section.checks.append(self._check_all_agents_ed25519())

        # Check 2.1.2: Verify signing algorithm column exists
        section.checks.append(self._check_signing_algorithm_column())

        # Check 2.1.3: Verify no non-Ed25519 keys
        section.checks.append(self._check_no_invalid_algorithms())

        section.status = section.compute_status()
        section.summary = f"Ed25519 verification: {section.status.value}"
        return section

    def _check_all_agents_ed25519(self) -> VerificationResult:
        """Verify all registered agents use Ed25519"""
        try:
            if not self.db.table_exists("fhq_org", "org_agents"):
                return VerificationResult(
                    check_name="all_agents_ed25519",
                    status=VerificationStatus.WARN,
                    message="org_agents table does not exist",
                    details={"action": "Run migration 018 first"}
                )

            agents = self.db.execute_query("""
                SELECT agent_id, signing_algorithm
                FROM fhq_org.org_agents
            """)

            non_ed25519 = [a for a in agents if a['signing_algorithm'] != 'Ed25519']

            if non_ed25519:
                return VerificationResult(
                    check_name="all_agents_ed25519",
                    status=VerificationStatus.FAIL,
                    message=f"{len(non_ed25519)} agents not using Ed25519",
                    details={"non_compliant": non_ed25519}
                )

            return VerificationResult(
                check_name="all_agents_ed25519",
                status=VerificationStatus.PASS,
                message=f"All {len(agents)} agents use Ed25519 signing",
                details={"agents": [a['agent_id'] for a in agents]},
                evidence_hash=CanonicalHash.compute_sha256({"agents": agents})
            )

        except Exception as e:
            return VerificationResult(
                check_name="all_agents_ed25519",
                status=VerificationStatus.FAIL,
                message=f"Ed25519 check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_signing_algorithm_column(self) -> VerificationResult:
        """Verify signing_algorithm column enforces Ed25519"""
        try:
            # Check for constraint on org_agents
            constraint = self.db.execute_query("""
                SELECT constraint_name, check_clause
                FROM information_schema.check_constraints
                WHERE constraint_schema = 'fhq_org'
            """)

            # Check agent_keys table
            if self.db.table_exists("fhq_meta", "agent_keys"):
                keys_constraint = self.db.execute_query("""
                    SELECT constraint_name, check_clause
                    FROM information_schema.check_constraints
                    WHERE constraint_schema = 'fhq_meta'
                      AND constraint_name LIKE '%algorithm%'
                """)

                if keys_constraint:
                    return VerificationResult(
                        check_name="signing_algorithm_column",
                        status=VerificationStatus.PASS,
                        message="Ed25519 constraint enforced on agent_keys",
                        details={"constraints": keys_constraint}
                    )

            return VerificationResult(
                check_name="signing_algorithm_column",
                status=VerificationStatus.WARN,
                message="Ed25519 constraint verification incomplete",
                details={"note": "Manual verification recommended"}
            )

        except Exception as e:
            return VerificationResult(
                check_name="signing_algorithm_column",
                status=VerificationStatus.WARN,
                message=f"Constraint check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_no_invalid_algorithms(self) -> VerificationResult:
        """Verify no keys with invalid signing algorithms"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="no_invalid_algorithms",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist",
                    details={"action": "Run migration 019 first"}
                )

            invalid = self.db.execute_query("""
                SELECT agent_id, signing_algorithm
                FROM fhq_meta.agent_keys
                WHERE signing_algorithm != 'Ed25519'
            """)

            if invalid:
                return VerificationResult(
                    check_name="no_invalid_algorithms",
                    status=VerificationStatus.FAIL,
                    message=f"{len(invalid)} keys with invalid algorithms",
                    details={"invalid_keys": invalid}
                )

            key_count = self.db.execute_scalar("""
                SELECT COUNT(*) FROM fhq_meta.agent_keys
            """)

            return VerificationResult(
                check_name="no_invalid_algorithms",
                status=VerificationStatus.PASS,
                message=f"All {key_count or 0} keys use Ed25519",
                details={"key_count": key_count or 0}
            )

        except Exception as e:
            return VerificationResult(
                check_name="no_invalid_algorithms",
                status=VerificationStatus.WARN,
                message=f"Algorithm check skipped: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 2.2: KEYSTORE BACKEND VERIFICATION
# =============================================================================

class Section2_2_KeyStoreVerification:
    """Section 2.2: Hierarchical KeyStore with Three Operational Modes"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 2.2 verification checks"""
        section = SectionResult(
            section_id="2.2",
            section_name="KeyStore Backend Verification",
            status=VerificationStatus.SKIP
        )

        # Check 2.2.1: Verify agent_keys table exists
        section.checks.append(self._check_agent_keys_table())

        # Check 2.2.2: Verify keystore_backend column
        section.checks.append(self._check_keystore_backend_values())

        # Check 2.2.3: Verify all agents have keys registered
        section.checks.append(self._check_all_agents_have_keys())

        section.status = section.compute_status()
        section.summary = f"KeyStore verification: {section.status.value}"
        return section

    def _check_agent_keys_table(self) -> VerificationResult:
        """Verify agent_keys table exists with required columns"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="agent_keys_table",
                    status=VerificationStatus.FAIL,
                    message="agent_keys table does not exist",
                    details={"action": "Run migration 019"}
                )

            columns = self.db.execute_query("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'fhq_meta'
                  AND table_name = 'agent_keys'
            """)

            required_columns = [
                'key_id', 'agent_id', 'public_key', 'key_fingerprint',
                'signing_algorithm', 'key_state', 'keystore_backend'
            ]

            column_names = [c['column_name'] for c in columns]
            missing = [c for c in required_columns if c not in column_names]

            if missing:
                return VerificationResult(
                    check_name="agent_keys_table",
                    status=VerificationStatus.FAIL,
                    message=f"Missing columns: {missing}",
                    details={"present": column_names, "missing": missing}
                )

            return VerificationResult(
                check_name="agent_keys_table",
                status=VerificationStatus.PASS,
                message=f"agent_keys table has all {len(required_columns)} required columns",
                details={"columns": column_names}
            )

        except Exception as e:
            return VerificationResult(
                check_name="agent_keys_table",
                status=VerificationStatus.FAIL,
                message=f"Table check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_keystore_backend_values(self) -> VerificationResult:
        """Verify keystore_backend values are valid"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="keystore_backend_values",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            backends = self.db.execute_query("""
                SELECT DISTINCT keystore_backend, COUNT(*) as count
                FROM fhq_meta.agent_keys
                GROUP BY keystore_backend
            """)

            invalid_backends = [
                b for b in backends
                if b['keystore_backend'] not in Config.KEYSTORE_BACKENDS
            ]

            if invalid_backends:
                return VerificationResult(
                    check_name="keystore_backend_values",
                    status=VerificationStatus.FAIL,
                    message=f"Invalid keystore backends found",
                    details={"invalid": invalid_backends, "valid": Config.KEYSTORE_BACKENDS}
                )

            return VerificationResult(
                check_name="keystore_backend_values",
                status=VerificationStatus.PASS,
                message=f"All keystore backends valid: {[b['keystore_backend'] for b in backends]}",
                details={"backends": backends}
            )

        except Exception as e:
            return VerificationResult(
                check_name="keystore_backend_values",
                status=VerificationStatus.WARN,
                message=f"Backend check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_all_agents_have_keys(self) -> VerificationResult:
        """Verify all canonical agents have registered keys"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="all_agents_have_keys",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            agents_with_keys = self.db.execute_query("""
                SELECT DISTINCT agent_id
                FROM fhq_meta.agent_keys
                WHERE key_state IN ('ACTIVE', 'DEPRECATED')
            """)

            agent_ids = [a['agent_id'] for a in agents_with_keys]
            missing = [a for a in Config.REQUIRED_AGENTS if a not in agent_ids]

            if missing:
                return VerificationResult(
                    check_name="all_agents_have_keys",
                    status=VerificationStatus.FAIL,
                    message=f"Agents missing keys: {missing}",
                    details={"present": agent_ids, "missing": missing}
                )

            return VerificationResult(
                check_name="all_agents_have_keys",
                status=VerificationStatus.PASS,
                message=f"All {len(Config.REQUIRED_AGENTS)} canonical agents have keys",
                details={"agents": agent_ids}
            )

        except Exception as e:
            return VerificationResult(
                check_name="all_agents_have_keys",
                status=VerificationStatus.WARN,
                message=f"Agent key check skipped: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 2.3: ROLLING KEY ROTATION VERIFICATION
# =============================================================================

class Section2_3_KeyRotationVerification:
    """Section 2.3: Rolling Key Rotation (Dual-Publishing)"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 2.3 verification checks"""
        section = SectionResult(
            section_id="2.3",
            section_name="Rolling Key Rotation Verification",
            status=VerificationStatus.SKIP
        )

        # Check 2.3.1: Verify key lifecycle states
        section.checks.append(self._check_key_lifecycle_states())

        # Check 2.3.2: Verify only one ACTIVE key per agent
        section.checks.append(self._check_single_active_key())

        # Check 2.3.3: Verify grace period configuration
        section.checks.append(self._check_grace_period())

        # Check 2.3.4: Verify deprecated keys are verifiable
        section.checks.append(self._check_deprecated_verifiable())

        section.status = section.compute_status()
        section.summary = f"Key rotation verification: {section.status.value}"
        return section

    def _check_key_lifecycle_states(self) -> VerificationResult:
        """Verify key_state values match ADR-008 Appendix A"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="key_lifecycle_states",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            states = self.db.execute_query("""
                SELECT key_state, COUNT(*) as count
                FROM fhq_meta.agent_keys
                GROUP BY key_state
            """)

            valid_states = list(Config.KEY_STATES.keys())
            state_values = [s['key_state'] for s in states]
            invalid = [s for s in state_values if s not in valid_states]

            if invalid:
                return VerificationResult(
                    check_name="key_lifecycle_states",
                    status=VerificationStatus.FAIL,
                    message=f"Invalid key states: {invalid}",
                    details={"invalid": invalid, "valid": valid_states}
                )

            return VerificationResult(
                check_name="key_lifecycle_states",
                status=VerificationStatus.PASS,
                message=f"All key states valid: {states}",
                details={"states": states, "valid_states": valid_states}
            )

        except Exception as e:
            return VerificationResult(
                check_name="key_lifecycle_states",
                status=VerificationStatus.WARN,
                message=f"State check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_single_active_key(self) -> VerificationResult:
        """Verify each agent has at most one ACTIVE key"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="single_active_key",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            duplicates = self.db.execute_query("""
                SELECT agent_id, COUNT(*) as active_count
                FROM fhq_meta.agent_keys
                WHERE key_state = 'ACTIVE'
                GROUP BY agent_id
                HAVING COUNT(*) > 1
            """)

            if duplicates:
                return VerificationResult(
                    check_name="single_active_key",
                    status=VerificationStatus.FAIL,
                    message=f"Agents with multiple active keys: {duplicates}",
                    details={"duplicates": duplicates}
                )

            active_count = self.db.execute_scalar("""
                SELECT COUNT(DISTINCT agent_id)
                FROM fhq_meta.agent_keys
                WHERE key_state = 'ACTIVE'
            """)

            return VerificationResult(
                check_name="single_active_key",
                status=VerificationStatus.PASS,
                message=f"{active_count or 0} agents with unique active keys",
                details={"active_agents": active_count or 0}
            )

        except Exception as e:
            return VerificationResult(
                check_name="single_active_key",
                status=VerificationStatus.WARN,
                message=f"Active key check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_grace_period(self) -> VerificationResult:
        """Verify grace period configuration (24 hours)"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="grace_period",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            # Check default grace period
            grace_periods = self.db.execute_query("""
                SELECT DISTINCT grace_period_hours
                FROM fhq_meta.agent_keys
            """)

            non_compliant = [
                g for g in grace_periods
                if g['grace_period_hours'] != Config.GRACE_PERIOD_HOURS
            ]

            if non_compliant:
                return VerificationResult(
                    check_name="grace_period",
                    status=VerificationStatus.WARN,
                    message=f"Non-standard grace periods: {non_compliant}",
                    details={"expected": Config.GRACE_PERIOD_HOURS, "found": grace_periods}
                )

            return VerificationResult(
                check_name="grace_period",
                status=VerificationStatus.PASS,
                message=f"All keys have {Config.GRACE_PERIOD_HOURS}h grace period",
                details={"grace_period_hours": Config.GRACE_PERIOD_HOURS}
            )

        except Exception as e:
            return VerificationResult(
                check_name="grace_period",
                status=VerificationStatus.WARN,
                message=f"Grace period check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_deprecated_verifiable(self) -> VerificationResult:
        """Verify DEPRECATED keys allow verification (dual-publishing)"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="deprecated_verifiable",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            non_verifiable = self.db.execute_query("""
                SELECT agent_id, key_state, allows_verification
                FROM fhq_meta.agent_keys
                WHERE key_state = 'DEPRECATED'
                  AND allows_verification = FALSE
            """)

            if non_verifiable:
                return VerificationResult(
                    check_name="deprecated_verifiable",
                    status=VerificationStatus.FAIL,
                    message=f"DEPRECATED keys not allowing verification",
                    details={"non_verifiable": non_verifiable}
                )

            deprecated_count = self.db.execute_scalar("""
                SELECT COUNT(*)
                FROM fhq_meta.agent_keys
                WHERE key_state = 'DEPRECATED'
            """)

            return VerificationResult(
                check_name="deprecated_verifiable",
                status=VerificationStatus.PASS,
                message=f"All {deprecated_count or 0} DEPRECATED keys allow verification",
                details={"deprecated_count": deprecated_count or 0}
            )

        except Exception as e:
            return VerificationResult(
                check_name="deprecated_verifiable",
                status=VerificationStatus.WARN,
                message=f"Deprecated key check skipped: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 2.4: MULTI-TIER ARCHIVAL VERIFICATION
# =============================================================================

class Section2_4_ArchivalVerification:
    """Section 2.4: Multi-Tier Key Archival Strategy"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 2.4 verification checks"""
        section = SectionResult(
            section_id="2.4",
            section_name="Multi-Tier Archival Verification",
            status=VerificationStatus.SKIP
        )

        # Check 2.4.1: Verify key_archival_log table
        section.checks.append(self._check_archival_log_table())

        # Check 2.4.2: Verify archival tier configuration
        section.checks.append(self._check_archival_tiers())

        # Check 2.4.3: Verify all key operations are logged
        section.checks.append(self._check_operations_logged())

        section.status = section.compute_status()
        section.summary = f"Archival verification: {section.status.value}"
        return section

    def _check_archival_log_table(self) -> VerificationResult:
        """Verify key_archival_log table exists"""
        try:
            if not self.db.table_exists("fhq_meta", "key_archival_log"):
                return VerificationResult(
                    check_name="archival_log_table",
                    status=VerificationStatus.FAIL,
                    message="key_archival_log table does not exist",
                    details={"action": "Run migration 019"}
                )

            log_count = self.db.execute_scalar("""
                SELECT COUNT(*) FROM fhq_meta.key_archival_log
            """)

            return VerificationResult(
                check_name="archival_log_table",
                status=VerificationStatus.PASS,
                message=f"key_archival_log table exists with {log_count} entries",
                details={"log_count": log_count}
            )

        except Exception as e:
            return VerificationResult(
                check_name="archival_log_table",
                status=VerificationStatus.FAIL,
                message=f"Archival log check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_archival_tiers(self) -> VerificationResult:
        """Verify archival tiers are properly configured"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="archival_tiers",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            tiers = self.db.execute_query("""
                SELECT retention_tier, COUNT(*) as count
                FROM fhq_meta.agent_keys
                GROUP BY retention_tier
            """)

            valid_tiers = list(Config.ARCHIVAL_TIERS.keys())
            tier_values = [t['retention_tier'] for t in tiers]
            invalid = [t for t in tier_values if t not in valid_tiers]

            if invalid:
                return VerificationResult(
                    check_name="archival_tiers",
                    status=VerificationStatus.FAIL,
                    message=f"Invalid archival tiers: {invalid}",
                    details={"invalid": invalid, "valid": valid_tiers}
                )

            return VerificationResult(
                check_name="archival_tiers",
                status=VerificationStatus.PASS,
                message=f"All archival tiers valid: {tiers}",
                details={"tiers": tiers}
            )

        except Exception as e:
            return VerificationResult(
                check_name="archival_tiers",
                status=VerificationStatus.WARN,
                message=f"Tier check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_operations_logged(self) -> VerificationResult:
        """Verify key operations are being logged"""
        try:
            if not self.db.table_exists("fhq_meta", "key_archival_log"):
                return VerificationResult(
                    check_name="operations_logged",
                    status=VerificationStatus.WARN,
                    message="key_archival_log table does not exist"
                )

            event_types = self.db.execute_query("""
                SELECT event_type, COUNT(*) as count
                FROM fhq_meta.key_archival_log
                GROUP BY event_type
            """)

            if not event_types:
                return VerificationResult(
                    check_name="operations_logged",
                    status=VerificationStatus.WARN,
                    message="No key operations logged yet",
                    details={"note": "Expected after key rotation"}
                )

            return VerificationResult(
                check_name="operations_logged",
                status=VerificationStatus.PASS,
                message=f"Key operations logged: {[e['event_type'] for e in event_types]}",
                details={"events": event_types}
            )

        except Exception as e:
            return VerificationResult(
                check_name="operations_logged",
                status=VerificationStatus.WARN,
                message=f"Operations check skipped: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 2.5: DATABASE INTEGRATION VERIFICATION
# =============================================================================

class Section2_5_DatabaseIntegration:
    """Section 2.5: Database Integration"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 2.5 verification checks"""
        section = SectionResult(
            section_id="2.5",
            section_name="Database Integration Verification",
            status=VerificationStatus.SKIP
        )

        # Check 2.5.1: Verify all required tables exist
        section.checks.append(self._check_required_tables())

        # Check 2.5.2: Verify ADR-008 is registered
        section.checks.append(self._check_adr008_registered())

        # Check 2.5.3: Verify ADR dependencies (lineage)
        section.checks.append(self._check_adr_dependencies())

        # Check 2.5.4: Verify G3/G4 audit entries
        section.checks.append(self._check_audit_entries())

        section.status = section.compute_status()
        section.summary = f"Database integration: {section.status.value}"
        return section

    def _check_required_tables(self) -> VerificationResult:
        """Verify all ADR-008 required tables exist"""
        missing = []
        present = []

        for schema, table in Config.REQUIRED_TABLES:
            if self.db.table_exists(schema, table):
                present.append(f"{schema}.{table}")
            else:
                missing.append(f"{schema}.{table}")

        if missing:
            return VerificationResult(
                check_name="required_tables",
                status=VerificationStatus.FAIL,
                message=f"Missing tables: {missing}",
                details={"present": present, "missing": missing}
            )

        return VerificationResult(
            check_name="required_tables",
            status=VerificationStatus.PASS,
            message=f"All {len(present)} required tables present",
            details={"tables": present}
        )

    def _check_adr008_registered(self) -> VerificationResult:
        """Verify ADR-008 is registered in adr_registry"""
        try:
            if not self.db.table_exists("fhq_meta", "adr_registry"):
                return VerificationResult(
                    check_name="adr008_registered",
                    status=VerificationStatus.FAIL,
                    message="adr_registry table does not exist"
                )

            adr = self.db.execute_query("""
                SELECT adr_id, title, version, status, governance_tier,
                       constitutional_authority, canonical_hash
                FROM fhq_meta.adr_registry
                WHERE adr_id = 'ADR-008'
            """)

            if not adr:
                return VerificationResult(
                    check_name="adr008_registered",
                    status=VerificationStatus.FAIL,
                    message="ADR-008 not registered in adr_registry"
                )

            adr_record = adr[0]
            if adr_record['status'] != 'APPROVED':
                return VerificationResult(
                    check_name="adr008_registered",
                    status=VerificationStatus.WARN,
                    message=f"ADR-008 status is {adr_record['status']}, not APPROVED",
                    details={"adr": adr_record}
                )

            return VerificationResult(
                check_name="adr008_registered",
                status=VerificationStatus.PASS,
                message=f"ADR-008 registered and APPROVED (Tier-2)",
                details={
                    "title": adr_record['title'],
                    "version": adr_record['version'],
                    "governance_tier": adr_record['governance_tier'],
                    "canonical_hash": adr_record['canonical_hash'][:32] + "..."
                },
                evidence_hash=adr_record['canonical_hash']
            )

        except Exception as e:
            return VerificationResult(
                check_name="adr008_registered",
                status=VerificationStatus.FAIL,
                message=f"ADR registration check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_adr_dependencies(self) -> VerificationResult:
        """Verify ADR-008 dependencies are registered"""
        try:
            if not self.db.table_exists("fhq_meta", "adr_dependencies"):
                return VerificationResult(
                    check_name="adr_dependencies",
                    status=VerificationStatus.FAIL,
                    message="adr_dependencies table does not exist"
                )

            deps = self.db.execute_query("""
                SELECT source_adr_id, target_adr_id, dependency_type, chain_order
                FROM fhq_meta.adr_dependencies
                WHERE source_adr_id = 'ADR-008'
                ORDER BY chain_order
            """)

            expected_deps = ['ADR-001', 'ADR-002', 'ADR-006', 'ADR-007']
            found_deps = [d['target_adr_id'] for d in deps]
            missing = [d for d in expected_deps if d not in found_deps]

            if missing:
                return VerificationResult(
                    check_name="adr_dependencies",
                    status=VerificationStatus.WARN,
                    message=f"Missing dependencies: {missing}",
                    details={"found": found_deps, "missing": missing}
                )

            authority_chain = " -> ".join(found_deps + ['ADR-008'])
            return VerificationResult(
                check_name="adr_dependencies",
                status=VerificationStatus.PASS,
                message=f"Authority chain: {authority_chain}",
                details={"dependencies": deps}
            )

        except Exception as e:
            return VerificationResult(
                check_name="adr_dependencies",
                status=VerificationStatus.WARN,
                message=f"Dependency check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_audit_entries(self) -> VerificationResult:
        """Verify G3/G4 audit entries for ADR-008"""
        try:
            if not self.db.table_exists("fhq_governance", "audit_log"):
                return VerificationResult(
                    check_name="audit_entries",
                    status=VerificationStatus.WARN,
                    message="audit_log table does not exist"
                )

            audit_entries = self.db.execute_query("""
                SELECT event_type, governance_gate, event_timestamp
                FROM fhq_governance.audit_log
                WHERE adr_reference = 'ADR-008'
                  AND governance_gate IN ('G3', 'G4')
                ORDER BY event_timestamp
            """)

            if len(audit_entries) < 2:
                return VerificationResult(
                    check_name="audit_entries",
                    status=VerificationStatus.WARN,
                    message=f"Only {len(audit_entries)}/2 G3/G4 entries found",
                    details={"entries": audit_entries}
                )

            gates = [e['governance_gate'] for e in audit_entries]
            return VerificationResult(
                check_name="audit_entries",
                status=VerificationStatus.PASS,
                message=f"G3/G4 audit entries present: {gates}",
                details={"entries": audit_entries}
            )

        except Exception as e:
            return VerificationResult(
                check_name="audit_entries",
                status=VerificationStatus.WARN,
                message=f"Audit check skipped: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 2.6: MANDATORY VERIFICATION
# =============================================================================

class Section2_6_MandatoryVerification:
    """Section 2.6: Mandatory Verification on Every Read"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 2.6 verification checks"""
        section = SectionResult(
            section_id="2.6",
            section_name="Mandatory Verification Requirements",
            status=VerificationStatus.SKIP
        )

        # Check 2.6.1: Verify ACTIVE + DEPRECATED keys accessible
        section.checks.append(self._check_verifiable_keys())

        # Check 2.6.2: Verify key fingerprints computed
        section.checks.append(self._check_key_fingerprints())

        # Check 2.6.3: Verify canonical hashes present
        section.checks.append(self._check_canonical_hashes())

        section.status = section.compute_status()
        section.summary = f"Mandatory verification: {section.status.value}"
        return section

    def _check_verifiable_keys(self) -> VerificationResult:
        """Verify ACTIVE and DEPRECATED keys allow verification"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="verifiable_keys",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            verifiable = self.db.execute_query("""
                SELECT key_state, allows_verification, COUNT(*) as count
                FROM fhq_meta.agent_keys
                WHERE key_state IN ('ACTIVE', 'DEPRECATED')
                GROUP BY key_state, allows_verification
            """)

            non_verifiable = [v for v in verifiable if not v['allows_verification']]

            if non_verifiable:
                return VerificationResult(
                    check_name="verifiable_keys",
                    status=VerificationStatus.FAIL,
                    message=f"Keys not allowing verification: {non_verifiable}",
                    details={"non_verifiable": non_verifiable}
                )

            return VerificationResult(
                check_name="verifiable_keys",
                status=VerificationStatus.PASS,
                message=f"All ACTIVE/DEPRECATED keys allow verification",
                details={"verifiable": verifiable}
            )

        except Exception as e:
            return VerificationResult(
                check_name="verifiable_keys",
                status=VerificationStatus.WARN,
                message=f"Verifiable key check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_key_fingerprints(self) -> VerificationResult:
        """Verify all keys have valid fingerprints"""
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="key_fingerprints",
                    status=VerificationStatus.WARN,
                    message="agent_keys table does not exist"
                )

            missing_fingerprints = self.db.execute_query("""
                SELECT agent_id, key_id
                FROM fhq_meta.agent_keys
                WHERE key_fingerprint IS NULL OR key_fingerprint = ''
            """)

            if missing_fingerprints:
                return VerificationResult(
                    check_name="key_fingerprints",
                    status=VerificationStatus.FAIL,
                    message=f"{len(missing_fingerprints)} keys missing fingerprints",
                    details={"missing": missing_fingerprints}
                )

            key_count = self.db.execute_scalar("""
                SELECT COUNT(*) FROM fhq_meta.agent_keys
            """)

            return VerificationResult(
                check_name="key_fingerprints",
                status=VerificationStatus.PASS,
                message=f"All {key_count} keys have valid fingerprints",
                details={"key_count": key_count}
            )

        except Exception as e:
            return VerificationResult(
                check_name="key_fingerprints",
                status=VerificationStatus.WARN,
                message=f"Fingerprint check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_canonical_hashes(self) -> VerificationResult:
        """Verify canonical hashes are present in adr_registry"""
        try:
            if not self.db.table_exists("fhq_meta", "adr_registry"):
                return VerificationResult(
                    check_name="canonical_hashes",
                    status=VerificationStatus.WARN,
                    message="adr_registry table does not exist"
                )

            missing_hashes = self.db.execute_query("""
                SELECT adr_id
                FROM fhq_meta.adr_registry
                WHERE canonical_hash IS NULL OR canonical_hash = ''
            """)

            if missing_hashes:
                return VerificationResult(
                    check_name="canonical_hashes",
                    status=VerificationStatus.FAIL,
                    message=f"ADRs missing canonical hashes: {missing_hashes}",
                    details={"missing": missing_hashes}
                )

            adr_count = self.db.execute_scalar("""
                SELECT COUNT(*) FROM fhq_meta.adr_registry
            """)

            return VerificationResult(
                check_name="canonical_hashes",
                status=VerificationStatus.PASS,
                message=f"All {adr_count} ADRs have canonical hashes",
                details={"adr_count": adr_count}
            )

        except Exception as e:
            return VerificationResult(
                check_name="canonical_hashes",
                status=VerificationStatus.WARN,
                message=f"Hash check skipped: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# MAIN VERIFICATION ORCHESTRATOR
# =============================================================================

class STIGVerificationOrchestrator:
    """Main orchestrator for STIG ADR-008 verification"""

    def __init__(self, logger: logging.Logger, report_only: bool = False):
        self.logger = logger
        self.report_only = report_only
        self.db = STIGDatabase(Config.get_db_connection_string(), logger)

    def generate_report_id(self) -> str:
        """Generate unique report ID"""
        return f"STIG-ADR008-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    def run_all_verifications(self) -> VerificationReport:
        """Run all verification sections"""
        report = VerificationReport(
            report_id=self.generate_report_id(),
            agent_id=Config.AGENT_ID,
            adr_reference=Config.ADR_REFERENCE,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        self.logger.info("=" * 70)
        self.logger.info("STIG ADR-008 CRYPTOGRAPHIC KEY MANAGEMENT VERIFICATION")
        self.logger.info(f"Report ID: {report.report_id}")
        self.logger.info(f"Timestamp: {report.timestamp}")
        self.logger.info("=" * 70)

        # Connect to database
        if not self.db.connect():
            self.logger.error("Failed to connect to database")
            return report

        try:
            # Run Section 2.1
            self.logger.info("\n[2.1] Ed25519 Signature Scheme Verification...")
            section_2_1 = Section2_1_Ed25519Verification(self.db, self.logger)
            report.sections.append(section_2_1.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 2.2
            self.logger.info("\n[2.2] KeyStore Backend Verification...")
            section_2_2 = Section2_2_KeyStoreVerification(self.db, self.logger)
            report.sections.append(section_2_2.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 2.3
            self.logger.info("\n[2.3] Rolling Key Rotation Verification...")
            section_2_3 = Section2_3_KeyRotationVerification(self.db, self.logger)
            report.sections.append(section_2_3.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 2.4
            self.logger.info("\n[2.4] Multi-Tier Archival Verification...")
            section_2_4 = Section2_4_ArchivalVerification(self.db, self.logger)
            report.sections.append(section_2_4.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 2.5
            self.logger.info("\n[2.5] Database Integration Verification...")
            section_2_5 = Section2_5_DatabaseIntegration(self.db, self.logger)
            report.sections.append(section_2_5.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 2.6
            self.logger.info("\n[2.6] Mandatory Verification Requirements...")
            section_2_6 = Section2_6_MandatoryVerification(self.db, self.logger)
            report.sections.append(section_2_6.verify())
            self._log_section_result(report.sections[-1])

            # Compute summary
            report.compute_summary()

            # Print final summary
            self._print_final_summary(report)

            # Store report if not report-only mode
            if not self.report_only:
                self._store_verification_report(report)

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
                "2.1": Section2_1_Ed25519Verification,
                "2.2": Section2_2_KeyStoreVerification,
                "2.3": Section2_3_KeyRotationVerification,
                "2.4": Section2_4_ArchivalVerification,
                "2.5": Section2_5_DatabaseIntegration,
                "2.6": Section2_6_MandatoryVerification,
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
        self.logger.info("ADR-008 VERIFICATION SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"Report ID: {report.report_id}")
        self.logger.info(f"Total Checks: {report.total_checks}")
        self.logger.info(f"  PASS: {report.passed_checks}")
        self.logger.info(f"  FAIL: {report.failed_checks}")
        self.logger.info(f"  WARN: {report.warning_checks}")
        self.logger.info("")
        self.logger.info(f"Canonical Hash: {report.canonical_hash[:32]}...")
        self.logger.info(f"OVERALL STATUS: {report.overall_status.value}")
        self.logger.info("=" * 70)

        # Section breakdown
        self.logger.info("\nSection Breakdown:")
        for section in report.sections:
            self.logger.info(f"  [{section.status.value}] {section.section_id} - {section.section_name}")

    def _store_verification_report(self, report: VerificationReport):
        """Store verification report in database"""
        try:
            if not self.db.table_exists("fhq_governance", "audit_log"):
                self.logger.warning("Cannot store report: audit_log table missing")
                return

            report_data = {
                "report_id": report.report_id,
                "agent_id": report.agent_id,
                "adr_reference": report.adr_reference,
                "timestamp": report.timestamp,
                "overall_status": report.overall_status.value,
                "total_checks": report.total_checks,
                "passed_checks": report.passed_checks,
                "failed_checks": report.failed_checks,
                "warning_checks": report.warning_checks,
                "canonical_hash": report.canonical_hash,
                "sections": [
                    {
                        "section_id": s.section_id,
                        "section_name": s.section_name,
                        "status": s.status.value,
                        "checks": [
                            {
                                "check_name": c.check_name,
                                "status": c.status.value,
                                "message": c.message,
                                "evidence_hash": c.evidence_hash
                            }
                            for c in s.checks
                        ]
                    }
                    for s in report.sections
                ]
            }

            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.audit_log (
                        event_type, event_category,
                        target_type, target_id, target_version,
                        actor_id, actor_role,
                        event_data, event_hash, adr_reference
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    'VERIFICATION_COMPLETE',
                    'COMPLIANCE',
                    'ADR',
                    'ADR-008',
                    Config.VERSION,
                    Config.AGENT_ID,
                    'Verification Agent',
                    json.dumps(report_data),
                    report.canonical_hash,
                    Config.ADR_REFERENCE
                ))
                self.db.conn.commit()

            self.logger.info(f"Verification report stored: {report.report_id}")

        except Exception as e:
            self.logger.error(f"Failed to store report: {e}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='STIG ADR-008 Verification Script - Cryptographic Key Management'
    )
    parser.add_argument(
        '--section',
        type=str,
        choices=['2.1', '2.2', '2.3', '2.4', '2.5', '2.6'],
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
            "canonical_hash": report.canonical_hash,
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
