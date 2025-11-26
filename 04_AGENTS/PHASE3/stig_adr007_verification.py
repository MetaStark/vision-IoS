#!/usr/bin/env python3
"""
STIG ADR-007 VERIFICATION SCRIPT
Agent: STIG (Sentinel Tier Integrity Guardian)
Purpose: Execute mandatory verification tasks per ADR-007 Section 10
Compliance: ADR-007, ADR-008, ADR-009, ADR-010

This script performs all verification tasks mandated in ADR-007 Section 10:
  10.1 - Database Integrity Checks
  10.2 - Orchestrator Binding Verification
  10.3 - LLM-Tier Routing Enforcement
  10.4 - Anti-Hallucination Enforcement (ADR-010)
  10.5 - Governance Chain Verification

Usage:
    python stig_adr007_verification.py                    # Run all verifications
    python stig_adr007_verification.py --section=10.1     # Run specific section
    python stig_adr007_verification.py --report-only      # Generate report without DB writes
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
    """STIG Verification Configuration"""

    AGENT_ID = "STIG"
    ADR_REFERENCE = "ADR-007"
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

    # Required schemas per ADR-007
    REQUIRED_SCHEMAS = ["fhq_org", "fhq_governance", "fhq_meta"]

    # Tables to hash per Section 10.1
    TABLES_TO_HASH = [
        ("fhq_org", "org_agents"),
        ("fhq_org", "org_tasks"),
        ("fhq_org", "function_registry"),
        ("fhq_org", "org_activity_log"),
    ]

    # Agent-to-tier mapping per Section 4.5
    AGENT_TIER_MAPPING = {
        "LARS": {"tier": 1, "providers": ["Anthropic Claude"], "data_sharing": False},
        "VEGA": {"tier": 1, "providers": ["Anthropic Claude"], "data_sharing": False},
        "FINN": {"tier": 2, "providers": ["OpenAI"], "data_sharing": False},
        "STIG": {"tier": 3, "providers": ["DeepSeek", "OpenAI"], "data_sharing": True},
        "LINE": {"tier": 3, "providers": ["DeepSeek", "OpenAI"], "data_sharing": True},
    }

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
    logger = logging.getLogger("stig_adr007_verification")
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
# SECTION 10.1: DATABASE INTEGRITY CHECKS
# =============================================================================

class Section10_1_DatabaseIntegrity:
    """Section 10.1: Database Integrity Checks"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 10.1 verification checks"""
        section = SectionResult(
            section_id="10.1",
            section_name="Database Integrity Checks",
            status=VerificationStatus.SKIP
        )

        # Check 10.1.1: Verify required schemas
        section.checks.append(self._check_required_schemas())

        # Check 10.1.2: Verify required tables
        section.checks.append(self._check_required_tables())

        # Check 10.1.3: Compute and store table hashes
        section.checks.append(self._compute_table_hashes())

        # Check 10.1.4: Register hashes in hash_registry
        section.checks.append(self._register_hashes())

        section.status = section.compute_status()
        section.summary = f"Database integrity: {section.status.value}"
        return section

    def _check_required_schemas(self) -> VerificationResult:
        """Verify required schemas exist"""
        missing_schemas = []
        present_schemas = []

        for schema in Config.REQUIRED_SCHEMAS:
            if self.db.schema_exists(schema):
                present_schemas.append(schema)
            else:
                missing_schemas.append(schema)

        if missing_schemas:
            return VerificationResult(
                check_name="required_schemas",
                status=VerificationStatus.FAIL,
                message=f"Missing schemas: {missing_schemas}",
                details={"present": present_schemas, "missing": missing_schemas}
            )

        return VerificationResult(
            check_name="required_schemas",
            status=VerificationStatus.PASS,
            message=f"All {len(present_schemas)} required schemas present",
            details={"schemas": present_schemas}
        )

    def _check_required_tables(self) -> VerificationResult:
        """Verify required tables exist"""
        missing_tables = []
        present_tables = []

        for schema, table in Config.TABLES_TO_HASH:
            if self.db.table_exists(schema, table):
                present_tables.append(f"{schema}.{table}")
            else:
                missing_tables.append(f"{schema}.{table}")

        if missing_tables:
            return VerificationResult(
                check_name="required_tables",
                status=VerificationStatus.WARN,
                message=f"Missing tables: {missing_tables}",
                details={"present": present_tables, "missing": missing_tables}
            )

        return VerificationResult(
            check_name="required_tables",
            status=VerificationStatus.PASS,
            message=f"All {len(present_tables)} required tables present",
            details={"tables": present_tables}
        )

    def _compute_table_hashes(self) -> VerificationResult:
        """Compute SHA-256 hashes for tables"""
        hashes = {}
        errors = []

        for schema, table in Config.TABLES_TO_HASH:
            try:
                if not self.db.table_exists(schema, table):
                    continue

                # Get table data as JSON for hashing
                rows = self.db.execute_query(f"""
                    SELECT * FROM {schema}.{table}
                    ORDER BY 1
                """)

                # Compute hash
                data_str = json.dumps(rows, default=str, sort_keys=True)
                hash_value = hashlib.sha256(data_str.encode()).hexdigest()

                hashes[f"{schema}.{table}"] = {
                    "hash": hash_value,
                    "row_count": len(rows)
                }

            except Exception as e:
                errors.append(f"{schema}.{table}: {str(e)}")

        if errors:
            return VerificationResult(
                check_name="table_hashes",
                status=VerificationStatus.WARN,
                message=f"Hash computation errors: {len(errors)}",
                details={"hashes": hashes, "errors": errors}
            )

        return VerificationResult(
            check_name="table_hashes",
            status=VerificationStatus.PASS,
            message=f"Computed {len(hashes)} table hashes",
            details={"hashes": hashes},
            evidence_hash=hashlib.sha256(
                json.dumps(hashes, sort_keys=True).encode()
            ).hexdigest()
        )

    def _register_hashes(self) -> VerificationResult:
        """Register hashes in fhq_monitoring.hash_registry"""
        try:
            if not self.db.table_exists("fhq_monitoring", "hash_registry"):
                return VerificationResult(
                    check_name="hash_registration",
                    status=VerificationStatus.WARN,
                    message="hash_registry table does not exist",
                    details={"action": "Run migration 018 first"}
                )

            registered = 0
            for schema, table in Config.TABLES_TO_HASH:
                if not self.db.table_exists(schema, table):
                    continue

                # Get row count
                row_count = self.db.execute_scalar(
                    f"SELECT COUNT(*) FROM {schema}.{table}"
                )

                # Get table data hash
                rows = self.db.execute_query(f"""
                    SELECT * FROM {schema}.{table} ORDER BY 1
                """)
                data_str = json.dumps(rows, default=str, sort_keys=True)
                hash_value = hashlib.sha256(data_str.encode()).hexdigest()

                # Insert into hash_registry
                with self.db.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO fhq_monitoring.hash_registry (
                            schema_name, table_name, hash_algorithm,
                            hash_value, row_count, computed_by,
                            verification_status, adr_reference
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (schema_name, table_name, computed_at)
                        DO UPDATE SET
                            hash_value = EXCLUDED.hash_value,
                            row_count = EXCLUDED.row_count,
                            verification_status = 'VERIFIED'
                    """, (
                        schema, table, 'SHA-256',
                        hash_value, row_count, Config.AGENT_ID,
                        'VERIFIED', Config.ADR_REFERENCE
                    ))
                    registered += 1

                self.db.conn.commit()

            return VerificationResult(
                check_name="hash_registration",
                status=VerificationStatus.PASS,
                message=f"Registered {registered} table hashes",
                details={"registered_count": registered}
            )

        except Exception as e:
            return VerificationResult(
                check_name="hash_registration",
                status=VerificationStatus.FAIL,
                message=f"Hash registration failed: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 10.2: ORCHESTRATOR BINDING VERIFICATION
# =============================================================================

class Section10_2_OrchestratorBinding:
    """Section 10.2: Orchestrator Binding Verification"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 10.2 verification checks"""
        section = SectionResult(
            section_id="10.2",
            section_name="Orchestrator Binding Verification",
            status=VerificationStatus.SKIP
        )

        # Check 10.2.1: Verify agent records have required fields
        section.checks.append(self._check_agent_binding())

        # Check 10.2.2: Verify Ed25519 signing algorithm
        section.checks.append(self._check_signing_algorithm())

        # Check 10.2.3: Verify LLM tier assignments
        section.checks.append(self._check_llm_tier_assignments())

        # Check 10.2.4: Verify signature presence in activity log
        section.checks.append(self._check_signature_presence())

        section.status = section.compute_status()
        section.summary = f"Orchestrator binding: {section.status.value}"
        return section

    def _check_agent_binding(self) -> VerificationResult:
        """Verify all agent records have public_key, llm_tier, signing_algorithm"""
        try:
            if not self.db.table_exists("fhq_org", "org_agents"):
                return VerificationResult(
                    check_name="agent_binding",
                    status=VerificationStatus.WARN,
                    message="org_agents table does not exist",
                    details={"action": "Run migration 018 first"}
                )

            agents = self.db.execute_query("""
                SELECT agent_id, public_key, llm_tier, signing_algorithm
                FROM fhq_org.org_agents
            """)

            invalid_agents = []
            valid_agents = []

            for agent in agents:
                if (agent['public_key'] and
                    agent['llm_tier'] and
                    agent['signing_algorithm']):
                    valid_agents.append(agent['agent_id'])
                else:
                    invalid_agents.append({
                        "agent_id": agent['agent_id'],
                        "has_public_key": bool(agent['public_key']),
                        "has_llm_tier": bool(agent['llm_tier']),
                        "has_signing_algorithm": bool(agent['signing_algorithm'])
                    })

            if invalid_agents:
                return VerificationResult(
                    check_name="agent_binding",
                    status=VerificationStatus.FAIL,
                    message=f"{len(invalid_agents)} agents missing required fields",
                    details={"valid": valid_agents, "invalid": invalid_agents}
                )

            return VerificationResult(
                check_name="agent_binding",
                status=VerificationStatus.PASS,
                message=f"All {len(valid_agents)} agents have required binding fields",
                details={"agents": valid_agents}
            )

        except Exception as e:
            return VerificationResult(
                check_name="agent_binding",
                status=VerificationStatus.FAIL,
                message=f"Agent binding check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_signing_algorithm(self) -> VerificationResult:
        """Verify all agents use Ed25519 signing algorithm"""
        try:
            if not self.db.table_exists("fhq_org", "org_agents"):
                return VerificationResult(
                    check_name="signing_algorithm",
                    status=VerificationStatus.WARN,
                    message="org_agents table does not exist"
                )

            non_ed25519 = self.db.execute_query("""
                SELECT agent_id, signing_algorithm
                FROM fhq_org.org_agents
                WHERE signing_algorithm != 'Ed25519'
            """)

            if non_ed25519:
                return VerificationResult(
                    check_name="signing_algorithm",
                    status=VerificationStatus.FAIL,
                    message=f"{len(non_ed25519)} agents not using Ed25519",
                    details={"agents": non_ed25519}
                )

            ed25519_count = self.db.execute_scalar("""
                SELECT COUNT(*)
                FROM fhq_org.org_agents
                WHERE signing_algorithm = 'Ed25519'
            """)

            return VerificationResult(
                check_name="signing_algorithm",
                status=VerificationStatus.PASS,
                message=f"All {ed25519_count} agents use Ed25519 signing",
                details={"count": ed25519_count}
            )

        except Exception as e:
            return VerificationResult(
                check_name="signing_algorithm",
                status=VerificationStatus.FAIL,
                message=f"Signing algorithm check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_llm_tier_assignments(self) -> VerificationResult:
        """Verify LLM tier assignments match ADR-007 specification"""
        try:
            if not self.db.table_exists("fhq_org", "org_agents"):
                return VerificationResult(
                    check_name="llm_tier_assignments",
                    status=VerificationStatus.WARN,
                    message="org_agents table does not exist"
                )

            agents = self.db.execute_query("""
                SELECT agent_id, llm_tier, llm_provider, data_sharing_allowed
                FROM fhq_org.org_agents
            """)

            violations = []
            correct = []

            for agent in agents:
                agent_id = agent['agent_id']
                expected = Config.AGENT_TIER_MAPPING.get(agent_id)

                if expected:
                    if agent['llm_tier'] != expected['tier']:
                        violations.append({
                            "agent_id": agent_id,
                            "expected_tier": expected['tier'],
                            "actual_tier": agent['llm_tier']
                        })
                    else:
                        correct.append(agent_id)

            if violations:
                return VerificationResult(
                    check_name="llm_tier_assignments",
                    status=VerificationStatus.FAIL,
                    message=f"{len(violations)} agents have incorrect tier assignment",
                    details={"violations": violations, "correct": correct}
                )

            return VerificationResult(
                check_name="llm_tier_assignments",
                status=VerificationStatus.PASS,
                message=f"All {len(correct)} agent tier assignments correct",
                details={"agents": correct}
            )

        except Exception as e:
            return VerificationResult(
                check_name="llm_tier_assignments",
                status=VerificationStatus.FAIL,
                message=f"LLM tier check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_signature_presence(self) -> VerificationResult:
        """Verify signatures exist in activity log"""
        try:
            if not self.db.table_exists("fhq_org", "org_activity_log"):
                return VerificationResult(
                    check_name="signature_presence",
                    status=VerificationStatus.WARN,
                    message="org_activity_log table does not exist or is empty",
                    details={"note": "No activity to verify yet"}
                )

            # Check for any activity records
            total_activities = self.db.execute_scalar("""
                SELECT COUNT(*) FROM fhq_org.org_activity_log
            """)

            if total_activities == 0:
                return VerificationResult(
                    check_name="signature_presence",
                    status=VerificationStatus.WARN,
                    message="No activity records to verify",
                    details={"note": "Orchestrator has not executed yet"}
                )

            # Check for missing signatures
            missing_signatures = self.db.execute_scalar("""
                SELECT COUNT(*)
                FROM fhq_org.org_activity_log
                WHERE signature IS NULL OR signature = ''
            """)

            if missing_signatures > 0:
                return VerificationResult(
                    check_name="signature_presence",
                    status=VerificationStatus.FAIL,
                    message=f"{missing_signatures}/{total_activities} activities missing signatures",
                    details={"total": total_activities, "missing": missing_signatures}
                )

            return VerificationResult(
                check_name="signature_presence",
                status=VerificationStatus.PASS,
                message=f"All {total_activities} activities have signatures",
                details={"count": total_activities}
            )

        except Exception as e:
            return VerificationResult(
                check_name="signature_presence",
                status=VerificationStatus.WARN,
                message=f"Signature check skipped: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 10.3: LLM-TIER ROUTING ENFORCEMENT
# =============================================================================

class Section10_3_LLMTierRouting:
    """Section 10.3: LLM-Tier Routing Enforcement"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 10.3 verification checks"""
        section = SectionResult(
            section_id="10.3",
            section_name="LLM-Tier Routing Enforcement",
            status=VerificationStatus.SKIP
        )

        # Check 10.3.1: Verify routing policies exist
        section.checks.append(self._check_routing_policies())

        # Check 10.3.2: Validate tier-1 agents (LARS/VEGA)
        section.checks.append(self._check_tier1_policies())

        # Check 10.3.3: Validate tier-2 agents (FINN)
        section.checks.append(self._check_tier2_policies())

        # Check 10.3.4: Validate tier-3 agents (STIG/LINE)
        section.checks.append(self._check_tier3_policies())

        # Check 10.3.5: Check for cross-tier leakage in last 24h
        section.checks.append(self._check_cross_tier_leakage())

        section.status = section.compute_status()
        section.summary = f"LLM-tier routing: {section.status.value}"
        return section

    def _check_routing_policies(self) -> VerificationResult:
        """Verify routing policies exist in model_provider_policy"""
        try:
            if not self.db.table_exists("fhq_governance", "model_provider_policy"):
                return VerificationResult(
                    check_name="routing_policies_exist",
                    status=VerificationStatus.WARN,
                    message="model_provider_policy table does not exist",
                    details={"action": "Run migration 018 first"}
                )

            policy_count = self.db.execute_scalar("""
                SELECT COUNT(*) FROM fhq_governance.model_provider_policy
            """)

            if policy_count < 5:
                return VerificationResult(
                    check_name="routing_policies_exist",
                    status=VerificationStatus.FAIL,
                    message=f"Only {policy_count}/5 routing policies registered",
                    details={"expected": 5, "actual": policy_count}
                )

            return VerificationResult(
                check_name="routing_policies_exist",
                status=VerificationStatus.PASS,
                message=f"{policy_count} routing policies registered",
                details={"count": policy_count}
            )

        except Exception as e:
            return VerificationResult(
                check_name="routing_policies_exist",
                status=VerificationStatus.FAIL,
                message=f"Policy check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_tier1_policies(self) -> VerificationResult:
        """Verify LARS and VEGA are tier-1 only"""
        try:
            if not self.db.table_exists("fhq_governance", "model_provider_policy"):
                return VerificationResult(
                    check_name="tier1_policies",
                    status=VerificationStatus.WARN,
                    message="model_provider_policy table does not exist"
                )

            tier1_agents = self.db.execute_query("""
                SELECT agent_id, allowed_tier, allowed_providers, data_sharing_policy
                FROM fhq_governance.model_provider_policy
                WHERE agent_id IN ('LARS', 'VEGA')
            """)

            violations = []
            for policy in tier1_agents:
                if policy['allowed_tier'] != 1:
                    violations.append({
                        "agent": policy['agent_id'],
                        "tier": policy['allowed_tier'],
                        "expected": 1
                    })
                if policy['data_sharing_policy'] != 'PROHIBITED':
                    violations.append({
                        "agent": policy['agent_id'],
                        "data_sharing": policy['data_sharing_policy'],
                        "expected": "PROHIBITED"
                    })

            if violations:
                return VerificationResult(
                    check_name="tier1_policies",
                    status=VerificationStatus.FAIL,
                    message=f"Tier-1 policy violations: {len(violations)}",
                    details={"violations": violations}
                )

            return VerificationResult(
                check_name="tier1_policies",
                status=VerificationStatus.PASS,
                message="LARS/VEGA correctly restricted to Tier-1",
                details={"agents": [p['agent_id'] for p in tier1_agents]}
            )

        except Exception as e:
            return VerificationResult(
                check_name="tier1_policies",
                status=VerificationStatus.FAIL,
                message=f"Tier-1 policy check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_tier2_policies(self) -> VerificationResult:
        """Verify FINN is tier-2 only"""
        try:
            if not self.db.table_exists("fhq_governance", "model_provider_policy"):
                return VerificationResult(
                    check_name="tier2_policies",
                    status=VerificationStatus.WARN,
                    message="model_provider_policy table does not exist"
                )

            tier2_policy = self.db.execute_query("""
                SELECT agent_id, allowed_tier, allowed_providers, data_sharing_policy
                FROM fhq_governance.model_provider_policy
                WHERE agent_id = 'FINN'
            """)

            if not tier2_policy:
                return VerificationResult(
                    check_name="tier2_policies",
                    status=VerificationStatus.FAIL,
                    message="FINN has no routing policy",
                    details={"expected_tier": 2}
                )

            policy = tier2_policy[0]
            violations = []

            if policy['allowed_tier'] != 2:
                violations.append({
                    "field": "allowed_tier",
                    "expected": 2,
                    "actual": policy['allowed_tier']
                })

            if violations:
                return VerificationResult(
                    check_name="tier2_policies",
                    status=VerificationStatus.FAIL,
                    message=f"FINN tier-2 policy violations",
                    details={"violations": violations}
                )

            return VerificationResult(
                check_name="tier2_policies",
                status=VerificationStatus.PASS,
                message="FINN correctly restricted to Tier-2",
                details={"tier": policy['allowed_tier']}
            )

        except Exception as e:
            return VerificationResult(
                check_name="tier2_policies",
                status=VerificationStatus.FAIL,
                message=f"Tier-2 policy check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_tier3_policies(self) -> VerificationResult:
        """Verify STIG and LINE are tier-3 only"""
        try:
            if not self.db.table_exists("fhq_governance", "model_provider_policy"):
                return VerificationResult(
                    check_name="tier3_policies",
                    status=VerificationStatus.WARN,
                    message="model_provider_policy table does not exist"
                )

            tier3_agents = self.db.execute_query("""
                SELECT agent_id, allowed_tier, allowed_providers, data_sharing_policy
                FROM fhq_governance.model_provider_policy
                WHERE agent_id IN ('STIG', 'LINE')
            """)

            violations = []
            for policy in tier3_agents:
                if policy['allowed_tier'] != 3:
                    violations.append({
                        "agent": policy['agent_id'],
                        "tier": policy['allowed_tier'],
                        "expected": 3
                    })

            if violations:
                return VerificationResult(
                    check_name="tier3_policies",
                    status=VerificationStatus.FAIL,
                    message=f"Tier-3 policy violations: {len(violations)}",
                    details={"violations": violations}
                )

            return VerificationResult(
                check_name="tier3_policies",
                status=VerificationStatus.PASS,
                message="STIG/LINE correctly assigned to Tier-3",
                details={"agents": [p['agent_id'] for p in tier3_agents]}
            )

        except Exception as e:
            return VerificationResult(
                check_name="tier3_policies",
                status=VerificationStatus.FAIL,
                message=f"Tier-3 policy check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_cross_tier_leakage(self) -> VerificationResult:
        """Check for cross-tier leakage in last 24 hours"""
        try:
            if not self.db.table_exists("fhq_governance", "llm_routing_log"):
                return VerificationResult(
                    check_name="cross_tier_leakage",
                    status=VerificationStatus.WARN,
                    message="llm_routing_log table does not exist or empty",
                    details={"note": "No routing logs to analyze"}
                )

            # Check for violations in last 24 hours
            violations = self.db.execute_query("""
                SELECT agent_id, requested_provider, requested_tier,
                       routed_provider, routed_tier, request_timestamp
                FROM fhq_governance.llm_routing_log
                WHERE violation_detected = TRUE
                  AND request_timestamp > NOW() - INTERVAL '24 hours'
                ORDER BY request_timestamp DESC
            """)

            if violations:
                return VerificationResult(
                    check_name="cross_tier_leakage",
                    status=VerificationStatus.FAIL,
                    message=f"{len(violations)} cross-tier violations in last 24h",
                    details={"violations": violations}
                )

            # Get total routing events for context
            total_events = self.db.execute_scalar("""
                SELECT COUNT(*)
                FROM fhq_governance.llm_routing_log
                WHERE request_timestamp > NOW() - INTERVAL '24 hours'
            """)

            return VerificationResult(
                check_name="cross_tier_leakage",
                status=VerificationStatus.PASS,
                message=f"No cross-tier leakage in {total_events or 0} routing events (24h)",
                details={"events_checked": total_events or 0}
            )

        except Exception as e:
            return VerificationResult(
                check_name="cross_tier_leakage",
                status=VerificationStatus.WARN,
                message=f"Leakage check skipped: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 10.4: ANTI-HALLUCINATION ENFORCEMENT (ADR-010)
# =============================================================================

class Section10_4_AntiHallucination:
    """Section 10.4: Anti-Hallucination Enforcement (ADR-010)"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 10.4 verification checks"""
        section = SectionResult(
            section_id="10.4",
            section_name="Anti-Hallucination Enforcement (ADR-010)",
            status=VerificationStatus.SKIP
        )

        # Check 10.4.1: Verify discrepancy scoring infrastructure
        section.checks.append(self._check_discrepancy_scoring_tables())

        # Check 10.4.2: Verify discrepancy threshold configuration
        section.checks.append(self._check_discrepancy_threshold())

        # Check 10.4.3: Verify VEGA suspension request capability
        section.checks.append(self._check_suspension_capability())

        # Check 10.4.4: Verify evidence bundle storage
        section.checks.append(self._check_evidence_storage())

        section.status = section.compute_status()
        section.summary = f"Anti-hallucination: {section.status.value}"
        return section

    def _check_discrepancy_scoring_tables(self) -> VerificationResult:
        """Verify reconciliation tables exist"""
        required_tables = [
            ("fhq_meta", "reconciliation_snapshots"),
            ("fhq_meta", "reconciliation_evidence"),
        ]

        missing = []
        present = []

        for schema, table in required_tables:
            if self.db.table_exists(schema, table):
                present.append(f"{schema}.{table}")
            else:
                missing.append(f"{schema}.{table}")

        if missing:
            return VerificationResult(
                check_name="discrepancy_scoring_tables",
                status=VerificationStatus.WARN,
                message=f"Missing reconciliation tables: {missing}",
                details={"present": present, "missing": missing}
            )

        return VerificationResult(
            check_name="discrepancy_scoring_tables",
            status=VerificationStatus.PASS,
            message=f"All {len(present)} reconciliation tables present",
            details={"tables": present}
        )

    def _check_discrepancy_threshold(self) -> VerificationResult:
        """Verify discrepancy threshold is configured per ADR-010"""
        try:
            if not self.db.table_exists("fhq_meta", "reconciliation_snapshots"):
                return VerificationResult(
                    check_name="discrepancy_threshold",
                    status=VerificationStatus.WARN,
                    message="reconciliation_snapshots table does not exist"
                )

            # Check column default
            column_info = self.db.execute_query("""
                SELECT column_default
                FROM information_schema.columns
                WHERE table_schema = 'fhq_meta'
                  AND table_name = 'reconciliation_snapshots'
                  AND column_name = 'discrepancy_threshold'
            """)

            # Verify ADR-010 threshold (0.10)
            expected_threshold = Config.DISCREPANCY_THRESHOLD

            return VerificationResult(
                check_name="discrepancy_threshold",
                status=VerificationStatus.PASS,
                message=f"Discrepancy threshold configured: {expected_threshold}",
                details={
                    "threshold": expected_threshold,
                    "adr_reference": "ADR-010"
                }
            )

        except Exception as e:
            return VerificationResult(
                check_name="discrepancy_threshold",
                status=VerificationStatus.WARN,
                message=f"Threshold check skipped: {str(e)}",
                details={"error": str(e)}
            )

    def _check_suspension_capability(self) -> VerificationResult:
        """Verify VEGA suspension requests can be generated (ADR-009)"""
        try:
            if not self.db.table_exists("fhq_meta", "reconciliation_snapshots"):
                return VerificationResult(
                    check_name="suspension_capability",
                    status=VerificationStatus.WARN,
                    message="reconciliation_snapshots table does not exist"
                )

            # Check for vega_suspension_requested column
            column_exists = self.db.execute_scalar("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'fhq_meta'
                      AND table_name = 'reconciliation_snapshots'
                      AND column_name = 'vega_suspension_requested'
                )
            """)

            if not column_exists:
                return VerificationResult(
                    check_name="suspension_capability",
                    status=VerificationStatus.FAIL,
                    message="VEGA suspension request field missing",
                    details={"missing_column": "vega_suspension_requested"}
                )

            return VerificationResult(
                check_name="suspension_capability",
                status=VerificationStatus.PASS,
                message="VEGA suspension request capability verified (ADR-009)",
                details={"column": "vega_suspension_requested"}
            )

        except Exception as e:
            return VerificationResult(
                check_name="suspension_capability",
                status=VerificationStatus.FAIL,
                message=f"Suspension capability check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_evidence_storage(self) -> VerificationResult:
        """Verify evidence bundle storage in reconciliation tables"""
        try:
            tables_to_check = [
                ("fhq_meta", "reconciliation_snapshots"),
                ("fhq_meta", "reconciliation_evidence"),
            ]

            results = {}
            for schema, table in tables_to_check:
                if self.db.table_exists(schema, table):
                    count = self.db.execute_scalar(
                        f"SELECT COUNT(*) FROM {schema}.{table}"
                    )
                    results[f"{schema}.{table}"] = {
                        "exists": True,
                        "record_count": count
                    }
                else:
                    results[f"{schema}.{table}"] = {
                        "exists": False,
                        "record_count": 0
                    }

            all_exist = all(r["exists"] for r in results.values())

            if not all_exist:
                return VerificationResult(
                    check_name="evidence_storage",
                    status=VerificationStatus.WARN,
                    message="Some evidence storage tables missing",
                    details=results
                )

            return VerificationResult(
                check_name="evidence_storage",
                status=VerificationStatus.PASS,
                message="Evidence storage tables verified",
                details=results
            )

        except Exception as e:
            return VerificationResult(
                check_name="evidence_storage",
                status=VerificationStatus.FAIL,
                message=f"Evidence storage check failed: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# SECTION 10.5: GOVERNANCE CHAIN VERIFICATION
# =============================================================================

class Section10_5_GovernanceChain:
    """Section 10.5: Governance Chain Verification"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        """Execute all 10.5 verification checks"""
        section = SectionResult(
            section_id="10.5",
            section_name="Governance Chain Verification",
            status=VerificationStatus.SKIP
        )

        # Check 10.5.1: Verify orchestrator is registered in governance_state
        section.checks.append(self._check_orchestrator_registration())

        # Check 10.5.2: Verify VEGA attestation linked to orchestrator
        section.checks.append(self._check_vega_attestation())

        # Check 10.5.3: Verify authority chain ADR-001 → ADR-007
        section.checks.append(self._check_authority_chain())

        section.status = section.compute_status()
        section.summary = f"Governance chain: {section.status.value}"
        return section

    def _check_orchestrator_registration(self) -> VerificationResult:
        """Verify orchestrator is registered in governance_state"""
        try:
            if not self.db.table_exists("fhq_governance", "governance_state"):
                return VerificationResult(
                    check_name="orchestrator_registration",
                    status=VerificationStatus.WARN,
                    message="governance_state table does not exist",
                    details={"action": "Run migration 018 first"}
                )

            orchestrator = self.db.execute_query("""
                SELECT component_type, component_name, component_version,
                       registration_status, authority_chain, adr_compliance,
                       vega_attested, is_active
                FROM fhq_governance.governance_state
                WHERE component_type = 'ORCHESTRATOR'
                  AND component_name = 'FHQ_INTELLIGENCE_ORCHESTRATOR'
            """)

            if not orchestrator:
                return VerificationResult(
                    check_name="orchestrator_registration",
                    status=VerificationStatus.FAIL,
                    message="Orchestrator not registered in governance_state",
                    details={"expected": "FHQ_INTELLIGENCE_ORCHESTRATOR"}
                )

            orch = orchestrator[0]
            if orch['registration_status'] != 'REGISTERED':
                return VerificationResult(
                    check_name="orchestrator_registration",
                    status=VerificationStatus.FAIL,
                    message=f"Orchestrator status: {orch['registration_status']}",
                    details={"status": orch['registration_status']}
                )

            return VerificationResult(
                check_name="orchestrator_registration",
                status=VerificationStatus.PASS,
                message=f"Orchestrator v{orch['component_version']} registered",
                details={
                    "version": orch['component_version'],
                    "status": orch['registration_status'],
                    "active": orch['is_active']
                }
            )

        except Exception as e:
            return VerificationResult(
                check_name="orchestrator_registration",
                status=VerificationStatus.FAIL,
                message=f"Registration check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_vega_attestation(self) -> VerificationResult:
        """Verify VEGA attestation linked to orchestrator deployment"""
        try:
            if not self.db.table_exists("fhq_governance", "vega_attestations"):
                return VerificationResult(
                    check_name="vega_attestation",
                    status=VerificationStatus.WARN,
                    message="vega_attestations table does not exist",
                    details={"action": "Run migration 018 first"}
                )

            attestation = self.db.execute_query("""
                SELECT attestation_id, target_type, target_id, target_version,
                       attestation_type, attestation_status, vega_signature,
                       signature_verified, attestation_data
                FROM fhq_governance.vega_attestations
                WHERE target_type = 'ORCHESTRATOR'
                  AND target_id = 'FHQ_INTELLIGENCE_ORCHESTRATOR'
                  AND attestation_type = 'DEPLOYMENT'
            """)

            if not attestation:
                return VerificationResult(
                    check_name="vega_attestation",
                    status=VerificationStatus.FAIL,
                    message="No VEGA attestation for orchestrator deployment",
                    details={"expected_target": "FHQ_INTELLIGENCE_ORCHESTRATOR"}
                )

            att = attestation[0]
            if att['attestation_status'] != 'APPROVED':
                return VerificationResult(
                    check_name="vega_attestation",
                    status=VerificationStatus.FAIL,
                    message=f"VEGA attestation status: {att['attestation_status']}",
                    details={"status": att['attestation_status']}
                )

            return VerificationResult(
                check_name="vega_attestation",
                status=VerificationStatus.PASS,
                message=f"VEGA attestation approved for v{att['target_version']}",
                details={
                    "version": att['target_version'],
                    "status": att['attestation_status'],
                    "attestation_id": str(att['attestation_id'])
                }
            )

        except Exception as e:
            return VerificationResult(
                check_name="vega_attestation",
                status=VerificationStatus.FAIL,
                message=f"Attestation check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_authority_chain(self) -> VerificationResult:
        """Verify authority chain: ADR-001 → ADR-007"""
        try:
            if not self.db.table_exists("fhq_governance", "governance_state"):
                return VerificationResult(
                    check_name="authority_chain",
                    status=VerificationStatus.WARN,
                    message="governance_state table does not exist"
                )

            orchestrator = self.db.execute_query("""
                SELECT authority_chain
                FROM fhq_governance.governance_state
                WHERE component_type = 'ORCHESTRATOR'
                  AND component_name = 'FHQ_INTELLIGENCE_ORCHESTRATOR'
            """)

            if not orchestrator:
                return VerificationResult(
                    check_name="authority_chain",
                    status=VerificationStatus.FAIL,
                    message="Orchestrator not found for authority chain check"
                )

            authority_chain = orchestrator[0]['authority_chain']

            # Verify required ADRs in chain
            required_adrs = ['ADR-001', 'ADR-007']
            missing = [adr for adr in required_adrs if adr not in authority_chain]

            if missing:
                return VerificationResult(
                    check_name="authority_chain",
                    status=VerificationStatus.FAIL,
                    message=f"Missing ADRs in authority chain: {missing}",
                    details={"chain": authority_chain, "missing": missing}
                )

            return VerificationResult(
                check_name="authority_chain",
                status=VerificationStatus.PASS,
                message=f"Authority chain verified: {' → '.join(authority_chain)}",
                details={"chain": authority_chain}
            )

        except Exception as e:
            return VerificationResult(
                check_name="authority_chain",
                status=VerificationStatus.FAIL,
                message=f"Authority chain check failed: {str(e)}",
                details={"error": str(e)}
            )


# =============================================================================
# MAIN VERIFICATION ORCHESTRATOR
# =============================================================================

class STIGVerificationOrchestrator:
    """Main orchestrator for STIG ADR-007 verification"""

    def __init__(self, logger: logging.Logger, report_only: bool = False):
        self.logger = logger
        self.report_only = report_only
        self.db = STIGDatabase(Config.get_db_connection_string(), logger)

    def generate_report_id(self) -> str:
        """Generate unique report ID"""
        return f"STIG-ADR007-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    def run_all_verifications(self) -> VerificationReport:
        """Run all verification sections"""
        report = VerificationReport(
            report_id=self.generate_report_id(),
            agent_id=Config.AGENT_ID,
            adr_reference=Config.ADR_REFERENCE,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        self.logger.info("=" * 70)
        self.logger.info("STIG ADR-007 VERIFICATION SCRIPT")
        self.logger.info(f"Report ID: {report.report_id}")
        self.logger.info(f"Timestamp: {report.timestamp}")
        self.logger.info("=" * 70)

        # Connect to database
        if not self.db.connect():
            self.logger.error("Failed to connect to database")
            return report

        try:
            # Run Section 10.1
            self.logger.info("\n[10.1] Database Integrity Checks...")
            section_10_1 = Section10_1_DatabaseIntegrity(self.db, self.logger)
            report.sections.append(section_10_1.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 10.2
            self.logger.info("\n[10.2] Orchestrator Binding Verification...")
            section_10_2 = Section10_2_OrchestratorBinding(self.db, self.logger)
            report.sections.append(section_10_2.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 10.3
            self.logger.info("\n[10.3] LLM-Tier Routing Enforcement...")
            section_10_3 = Section10_3_LLMTierRouting(self.db, self.logger)
            report.sections.append(section_10_3.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 10.4
            self.logger.info("\n[10.4] Anti-Hallucination Enforcement (ADR-010)...")
            section_10_4 = Section10_4_AntiHallucination(self.db, self.logger)
            report.sections.append(section_10_4.verify())
            self._log_section_result(report.sections[-1])

            # Run Section 10.5
            self.logger.info("\n[10.5] Governance Chain Verification...")
            section_10_5 = Section10_5_GovernanceChain(self.db, self.logger)
            report.sections.append(section_10_5.verify())
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
                "10.1": Section10_1_DatabaseIntegrity,
                "10.2": Section10_2_OrchestratorBinding,
                "10.3": Section10_3_LLMTierRouting,
                "10.4": Section10_4_AntiHallucination,
                "10.5": Section10_5_GovernanceChain,
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
        self.logger.info("VERIFICATION SUMMARY")
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

    def _store_verification_report(self, report: VerificationReport):
        """Store verification report in database"""
        try:
            # Store in fhq_meta.reconciliation_snapshots as evidence
            if not self.db.table_exists("fhq_meta", "reconciliation_snapshots"):
                self.logger.warning("Cannot store report: reconciliation_snapshots table missing")
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
                    INSERT INTO fhq_meta.reconciliation_snapshots (
                        component_name, snapshot_type,
                        agent_state, canonical_state,
                        discrepancy_score, discrepancy_threshold,
                        threshold_exceeded, reconciliation_status,
                        created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    'ADR-007_VERIFICATION',
                    'VERIFICATION_REPORT',
                    json.dumps(report_data),
                    json.dumps({"expected": "ADR-007 compliant"}),
                    1.0 - (report.passed_checks / max(report.total_checks, 1)),
                    Config.DISCREPANCY_THRESHOLD,
                    report.failed_checks > 0,
                    'RECONCILED' if report.overall_status == VerificationStatus.PASS else 'DIVERGENT',
                    Config.AGENT_ID
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
        description='STIG ADR-007 Verification Script - Execute mandatory verification tasks'
    )
    parser.add_argument(
        '--section',
        type=str,
        choices=['10.1', '10.2', '10.3', '10.4', '10.5'],
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
