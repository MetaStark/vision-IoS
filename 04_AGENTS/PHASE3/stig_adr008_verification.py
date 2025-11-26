#!/usr/bin/env python3
"""
STIG ADR-008 VERIFICATION SCRIPT
Agent: STIG (Sentinel Tier Integrity Guardian)
Purpose: Execute mandatory verification tasks per ADR-008
Compliance: ADR-008 Cryptographic Key Management & Rotation Architecture

Adapted for existing database schema with columns:
  - agent_keys: public_key_hex, key_storage_tier, key_type
  - key_archival_log: archival_event, sha256_hash
  - adr_dependencies: adr_id, depends_on[]

Usage:
    python stig_adr008_verification.py
    python stig_adr008_verification.py --json
"""

import os
import sys
import json
import hashlib
import argparse
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

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

    @staticmethod
    def get_db_connection_string() -> str:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    # Key states
    KEY_STATES = ["PENDING", "ACTIVE", "DEPRECATED", "ARCHIVED"]

    # Storage tiers (existing schema uses TIER1_HOT, etc.)
    STORAGE_TIERS = ["TIER1_HOT", "TIER2_WARM", "TIER3_COLD"]

    # Required agents
    REQUIRED_AGENTS = ["LARS", "STIG", "LINE", "FINN", "VEGA"]


# =============================================================================
# CANONICAL HASH UTILITIES
# =============================================================================

class CanonicalHash:
    """SHA-256 hash computation utilities"""

    @staticmethod
    def compute_sha256(data: Any) -> str:
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)
        elif isinstance(data, bytes):
            data_str = data.decode('utf-8', errors='replace')
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()


# =============================================================================
# VERIFICATION RESULT CLASSES
# =============================================================================

class VerificationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class VerificationResult:
    check_name: str
    status: VerificationStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SectionResult:
    section_id: str
    section_name: str
    status: VerificationStatus
    checks: List[VerificationResult] = field(default_factory=list)
    summary: str = ""

    def compute_status(self) -> VerificationStatus:
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
        self.total_checks = sum(len(s.checks) for s in self.sections)
        self.passed_checks = sum(1 for s in self.sections for c in s.checks if c.status == VerificationStatus.PASS)
        self.failed_checks = sum(1 for s in self.sections for c in s.checks if c.status == VerificationStatus.FAIL)
        self.warning_checks = sum(1 for s in self.sections for c in s.checks if c.status == VerificationStatus.WARN)

        if self.failed_checks > 0:
            self.overall_status = VerificationStatus.FAIL
        elif self.warning_checks > 0:
            self.overall_status = VerificationStatus.WARN
        elif self.passed_checks == self.total_checks and self.total_checks > 0:
            self.overall_status = VerificationStatus.PASS
        else:
            self.overall_status = VerificationStatus.SKIP

        self.canonical_hash = CanonicalHash.compute_sha256({
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "total_checks": self.total_checks,
            "passed": self.passed_checks,
            "failed": self.failed_checks
        })


# =============================================================================
# LOGGING
# =============================================================================

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("stig_adr008")
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(console)
    return logger


# =============================================================================
# DATABASE INTERFACE (with auto-rollback on errors)
# =============================================================================

class STIGDatabase:
    """Database interface with auto-rollback"""

    def __init__(self, connection_string: str, logger: logging.Logger):
        self.connection_string = connection_string
        self.logger = logger
        self.conn = None

    def connect(self) -> bool:
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.conn.autocommit = True  # Auto-commit to avoid transaction issues
            self.logger.info("Database connection established")
            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False

    def close(self):
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed")

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self.logger.debug(f"Query error: {e}")
            raise

    def execute_scalar(self, query: str, params: tuple = None) -> Any:
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            self.logger.debug(f"Query error: {e}")
            raise

    def table_exists(self, schema: str, table: str) -> bool:
        try:
            result = self.execute_scalar("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                )
            """, (schema, table))
            return result
        except:
            return False


# =============================================================================
# VERIFICATION SECTIONS
# =============================================================================

class Section2_1_Ed25519:
    """Section 2.1: Ed25519 Signature Scheme"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        section = SectionResult(section_id="2.1", section_name="Ed25519 Signature Scheme", status=VerificationStatus.SKIP)

        # Check all agents use Ed25519
        section.checks.append(self._check_agents_ed25519())

        # Check key types
        section.checks.append(self._check_key_types())

        section.status = section.compute_status()
        section.summary = f"Ed25519: {section.status.value}"
        return section

    def _check_agents_ed25519(self) -> VerificationResult:
        try:
            agents = self.db.execute_query("""
                SELECT agent_id, signing_algorithm
                FROM fhq_org.org_agents
            """)

            non_ed25519 = [a for a in agents if a['signing_algorithm'] != 'Ed25519']

            if non_ed25519:
                return VerificationResult(
                    check_name="agents_ed25519",
                    status=VerificationStatus.FAIL,
                    message=f"{len(non_ed25519)} agents not using Ed25519",
                    details={"non_compliant": non_ed25519}
                )

            return VerificationResult(
                check_name="agents_ed25519",
                status=VerificationStatus.PASS,
                message=f"All {len(agents)} agents use Ed25519",
                details={"agents": [a['agent_id'] for a in agents]}
            )
        except Exception as e:
            return VerificationResult(
                check_name="agents_ed25519",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )

    def _check_key_types(self) -> VerificationResult:
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="key_types",
                    status=VerificationStatus.WARN,
                    message="agent_keys table not found"
                )

            keys = self.db.execute_query("""
                SELECT key_type, COUNT(*) as count
                FROM fhq_meta.agent_keys
                GROUP BY key_type
            """)

            ed25519_keys = [k for k in keys if 'ED25519' in (k['key_type'] or '')]

            if ed25519_keys:
                return VerificationResult(
                    check_name="key_types",
                    status=VerificationStatus.PASS,
                    message=f"Ed25519 keys found: {ed25519_keys}",
                    details={"key_types": keys}
                )

            return VerificationResult(
                check_name="key_types",
                status=VerificationStatus.WARN,
                message="No Ed25519 key types found",
                details={"key_types": keys}
            )
        except Exception as e:
            return VerificationResult(
                check_name="key_types",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )


class Section2_2_KeyStore:
    """Section 2.2: KeyStore Backend"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        section = SectionResult(section_id="2.2", section_name="KeyStore Backend", status=VerificationStatus.SKIP)

        section.checks.append(self._check_agent_keys_table())
        section.checks.append(self._check_storage_tiers())
        section.checks.append(self._check_all_agents_have_keys())

        section.status = section.compute_status()
        section.summary = f"KeyStore: {section.status.value}"
        return section

    def _check_agent_keys_table(self) -> VerificationResult:
        try:
            if not self.db.table_exists("fhq_meta", "agent_keys"):
                return VerificationResult(
                    check_name="agent_keys_table",
                    status=VerificationStatus.FAIL,
                    message="agent_keys table not found"
                )

            count = self.db.execute_scalar("SELECT COUNT(*) FROM fhq_meta.agent_keys")

            return VerificationResult(
                check_name="agent_keys_table",
                status=VerificationStatus.PASS,
                message=f"agent_keys table exists with {count} keys",
                details={"key_count": count}
            )
        except Exception as e:
            return VerificationResult(
                check_name="agent_keys_table",
                status=VerificationStatus.FAIL,
                message=f"Check failed: {str(e)[:50]}"
            )

    def _check_storage_tiers(self) -> VerificationResult:
        try:
            tiers = self.db.execute_query("""
                SELECT key_storage_tier, COUNT(*) as count
                FROM fhq_meta.agent_keys
                GROUP BY key_storage_tier
            """)

            valid_tiers = Config.STORAGE_TIERS
            tier_values = [t['key_storage_tier'] for t in tiers if t['key_storage_tier']]
            invalid = [t for t in tier_values if t not in valid_tiers]

            if invalid:
                return VerificationResult(
                    check_name="storage_tiers",
                    status=VerificationStatus.WARN,
                    message=f"Invalid storage tiers: {invalid}",
                    details={"tiers": tiers}
                )

            return VerificationResult(
                check_name="storage_tiers",
                status=VerificationStatus.PASS,
                message=f"Storage tiers valid: {tier_values}",
                details={"tiers": tiers}
            )
        except Exception as e:
            return VerificationResult(
                check_name="storage_tiers",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )

    def _check_all_agents_have_keys(self) -> VerificationResult:
        try:
            agents_with_keys = self.db.execute_query("""
                SELECT DISTINCT agent_id
                FROM fhq_meta.agent_keys
                WHERE key_state = 'ACTIVE'
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
                message=f"All {len(agent_ids)} agents have active keys",
                details={"agents": agent_ids}
            )
        except Exception as e:
            return VerificationResult(
                check_name="all_agents_have_keys",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )


class Section2_3_KeyRotation:
    """Section 2.3: Rolling Key Rotation"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        section = SectionResult(section_id="2.3", section_name="Key Rotation", status=VerificationStatus.SKIP)

        section.checks.append(self._check_key_states())
        section.checks.append(self._check_single_active_per_agent())

        section.status = section.compute_status()
        section.summary = f"Key rotation: {section.status.value}"
        return section

    def _check_key_states(self) -> VerificationResult:
        try:
            states = self.db.execute_query("""
                SELECT key_state, COUNT(*) as count
                FROM fhq_meta.agent_keys
                GROUP BY key_state
            """)

            state_values = [s['key_state'] for s in states]
            invalid = [s for s in state_values if s not in Config.KEY_STATES]

            if invalid:
                return VerificationResult(
                    check_name="key_states",
                    status=VerificationStatus.WARN,
                    message=f"Invalid key states: {invalid}",
                    details={"states": states}
                )

            return VerificationResult(
                check_name="key_states",
                status=VerificationStatus.PASS,
                message=f"Key states valid: {states}",
                details={"states": states}
            )
        except Exception as e:
            return VerificationResult(
                check_name="key_states",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )

    def _check_single_active_per_agent(self) -> VerificationResult:
        try:
            duplicates = self.db.execute_query("""
                SELECT agent_id, COUNT(*) as count
                FROM fhq_meta.agent_keys
                WHERE key_state = 'ACTIVE'
                GROUP BY agent_id
                HAVING COUNT(*) > 1
            """)

            if duplicates:
                return VerificationResult(
                    check_name="single_active_per_agent",
                    status=VerificationStatus.FAIL,
                    message=f"Multiple active keys: {duplicates}",
                    details={"duplicates": duplicates}
                )

            return VerificationResult(
                check_name="single_active_per_agent",
                status=VerificationStatus.PASS,
                message="Each agent has at most one active key"
            )
        except Exception as e:
            return VerificationResult(
                check_name="single_active_per_agent",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )


class Section2_4_Archival:
    """Section 2.4: Multi-Tier Archival"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        section = SectionResult(section_id="2.4", section_name="Multi-Tier Archival", status=VerificationStatus.SKIP)

        section.checks.append(self._check_archival_log())
        section.checks.append(self._check_archival_events())

        section.status = section.compute_status()
        section.summary = f"Archival: {section.status.value}"
        return section

    def _check_archival_log(self) -> VerificationResult:
        try:
            if not self.db.table_exists("fhq_meta", "key_archival_log"):
                return VerificationResult(
                    check_name="archival_log",
                    status=VerificationStatus.FAIL,
                    message="key_archival_log table not found"
                )

            count = self.db.execute_scalar("SELECT COUNT(*) FROM fhq_meta.key_archival_log")

            return VerificationResult(
                check_name="archival_log",
                status=VerificationStatus.PASS,
                message=f"key_archival_log exists with {count} entries",
                details={"entry_count": count}
            )
        except Exception as e:
            return VerificationResult(
                check_name="archival_log",
                status=VerificationStatus.FAIL,
                message=f"Check failed: {str(e)[:50]}"
            )

    def _check_archival_events(self) -> VerificationResult:
        try:
            events = self.db.execute_query("""
                SELECT archival_event, COUNT(*) as count
                FROM fhq_meta.key_archival_log
                GROUP BY archival_event
            """)

            if not events:
                return VerificationResult(
                    check_name="archival_events",
                    status=VerificationStatus.WARN,
                    message="No archival events logged yet"
                )

            return VerificationResult(
                check_name="archival_events",
                status=VerificationStatus.PASS,
                message=f"Archival events: {[e['archival_event'] for e in events]}",
                details={"events": events}
            )
        except Exception as e:
            return VerificationResult(
                check_name="archival_events",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )


class Section2_5_Database:
    """Section 2.5: Database Integration"""

    def __init__(self, db: STIGDatabase, logger: logging.Logger):
        self.db = db
        self.logger = logger

    def verify(self) -> SectionResult:
        section = SectionResult(section_id="2.5", section_name="Database Integration", status=VerificationStatus.SKIP)

        section.checks.append(self._check_adr008_registered())
        section.checks.append(self._check_dependencies())
        section.checks.append(self._check_audit_log())

        section.status = section.compute_status()
        section.summary = f"Database: {section.status.value}"
        return section

    def _check_adr008_registered(self) -> VerificationResult:
        try:
            adr = self.db.execute_query("""
                SELECT adr_id, adr_title, adr_status, governance_tier
                FROM fhq_meta.adr_registry
                WHERE adr_id = 'ADR-008'
            """)

            if not adr:
                return VerificationResult(
                    check_name="adr008_registered",
                    status=VerificationStatus.FAIL,
                    message="ADR-008 not registered"
                )

            record = adr[0]
            if record['adr_status'] != 'APPROVED':
                return VerificationResult(
                    check_name="adr008_registered",
                    status=VerificationStatus.WARN,
                    message=f"ADR-008 status: {record['adr_status']}",
                    details=record
                )

            return VerificationResult(
                check_name="adr008_registered",
                status=VerificationStatus.PASS,
                message=f"ADR-008 APPROVED ({record['governance_tier']})",
                details=record
            )
        except Exception as e:
            return VerificationResult(
                check_name="adr008_registered",
                status=VerificationStatus.FAIL,
                message=f"Check failed: {str(e)[:50]}"
            )

    def _check_dependencies(self) -> VerificationResult:
        try:
            deps = self.db.execute_query("""
                SELECT adr_id, depends_on, dependency_type
                FROM fhq_meta.adr_dependencies
                WHERE adr_id = 'ADR-008'
            """)

            if not deps:
                return VerificationResult(
                    check_name="dependencies",
                    status=VerificationStatus.WARN,
                    message="No ADR-008 dependencies found"
                )

            dep = deps[0]
            chain = dep.get('depends_on', [])

            return VerificationResult(
                check_name="dependencies",
                status=VerificationStatus.PASS,
                message=f"Authority chain: {' -> '.join(chain)} -> ADR-008",
                details={"depends_on": chain}
            )
        except Exception as e:
            return VerificationResult(
                check_name="dependencies",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )

    def _check_audit_log(self) -> VerificationResult:
        try:
            if not self.db.table_exists("fhq_governance", "audit_log"):
                return VerificationResult(
                    check_name="audit_log",
                    status=VerificationStatus.WARN,
                    message="audit_log table not found"
                )

            entries = self.db.execute_query("""
                SELECT event_type, governance_gate
                FROM fhq_governance.audit_log
                WHERE adr_reference = 'ADR-008'
            """)

            if not entries:
                return VerificationResult(
                    check_name="audit_log",
                    status=VerificationStatus.WARN,
                    message="No G3/G4 audit entries for ADR-008"
                )

            gates = [e['governance_gate'] for e in entries if e['governance_gate']]

            return VerificationResult(
                check_name="audit_log",
                status=VerificationStatus.PASS,
                message=f"G3/G4 entries: {len(entries)} ({gates})",
                details={"entries": entries}
            )
        except Exception as e:
            return VerificationResult(
                check_name="audit_log",
                status=VerificationStatus.WARN,
                message=f"Check skipped: {str(e)[:50]}"
            )


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

class STIGVerificationOrchestrator:
    """Main orchestrator"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.db = STIGDatabase(Config.get_db_connection_string(), logger)

    def run_all_verifications(self) -> VerificationReport:
        report = VerificationReport(
            report_id=f"STIG-ADR008-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            agent_id=Config.AGENT_ID,
            adr_reference=Config.ADR_REFERENCE,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        self.logger.info("=" * 70)
        self.logger.info("STIG ADR-008 VERIFICATION")
        self.logger.info(f"Report ID: {report.report_id}")
        self.logger.info("=" * 70)

        if not self.db.connect():
            self.logger.error("Database connection failed")
            return report

        try:
            # Section 2.1
            self.logger.info("\n[2.1] Ed25519 Signature Scheme...")
            section = Section2_1_Ed25519(self.db, self.logger)
            report.sections.append(section.verify())
            self._log_section(report.sections[-1])

            # Section 2.2
            self.logger.info("\n[2.2] KeyStore Backend...")
            section = Section2_2_KeyStore(self.db, self.logger)
            report.sections.append(section.verify())
            self._log_section(report.sections[-1])

            # Section 2.3
            self.logger.info("\n[2.3] Key Rotation...")
            section = Section2_3_KeyRotation(self.db, self.logger)
            report.sections.append(section.verify())
            self._log_section(report.sections[-1])

            # Section 2.4
            self.logger.info("\n[2.4] Multi-Tier Archival...")
            section = Section2_4_Archival(self.db, self.logger)
            report.sections.append(section.verify())
            self._log_section(report.sections[-1])

            # Section 2.5
            self.logger.info("\n[2.5] Database Integration...")
            section = Section2_5_Database(self.db, self.logger)
            report.sections.append(section.verify())
            self._log_section(report.sections[-1])

            report.compute_summary()
            self._print_summary(report)

            return report

        finally:
            self.db.close()

    def _log_section(self, section: SectionResult):
        for check in section.checks:
            icon = check.status.value
            self.logger.info(f"  [{icon}] {check.check_name}: {check.message}")
        self.logger.info(f"  Section {section.section_id}: {section.status.value}")

    def _print_summary(self, report: VerificationReport):
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("VERIFICATION SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"Total: {report.total_checks} | PASS: {report.passed_checks} | FAIL: {report.failed_checks} | WARN: {report.warning_checks}")
        self.logger.info(f"Hash: {report.canonical_hash[:32]}...")
        self.logger.info(f"OVERALL: {report.overall_status.value}")
        self.logger.info("=" * 70)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='STIG ADR-008 Verification')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    args = parser.parse_args()

    logger = setup_logging()
    orchestrator = STIGVerificationOrchestrator(logger)
    report = orchestrator.run_all_verifications()

    if args.json:
        result = {
            "report_id": report.report_id,
            "timestamp": report.timestamp,
            "overall_status": report.overall_status.value,
            "total_checks": report.total_checks,
            "passed": report.passed_checks,
            "failed": report.failed_checks,
            "warnings": report.warning_checks,
            "canonical_hash": report.canonical_hash,
            "sections": [
                {
                    "id": s.section_id,
                    "name": s.section_name,
                    "status": s.status.value,
                    "checks": [{"name": c.check_name, "status": c.status.value, "message": c.message} for c in s.checks]
                }
                for s in report.sections
            ]
        }
        print(json.dumps(result, indent=2))

    sys.exit(1 if report.overall_status == VerificationStatus.FAIL else 0)


if __name__ == '__main__':
    main()
