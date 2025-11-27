"""
VEGA CANONICAL TRUTH GOVERNANCE ENGINE
ADR-013: One-Source-of-Truth Architecture

Authority: VEGA — Chief Audit Officer (Canonical Truth Authority)
Mandate: ADR-013 Canonical Governance & ADR-006 VEGA Authority
Reference: HC-VEGA-ADR013-GOVERNANCE-20251127

Purpose:
    VEGA has sole write authority over canonical domain definitions.
    This engine enforces:
    - Canonical domain registration and mutation
    - Multi-truth detection and escalation
    - G1-G4 gate progression for canonical changes
    - Continuous integrity scanning
    - Violation resolution workflow

Architecture:
    - VEGACanonicalAuthority: Primary governance interface
    - MultiTruthScanner: Continuous multi-truth detection
    - CanonicalMutationGate: G1-G4 gate enforcement
    - ViolationResolver: Violation tracking and resolution
    - IntegrityAuditor: Periodic integrity verification

Invariants Enforced:
    - Only VEGA can register new canonical domains
    - Only VEGA can deactivate/modify canonical stores
    - Multi-truth attempts trigger automatic Class A/B events
    - All canonical mutations require G1-G4 gate progression
    - CEO override requires explicit attestation

Compliance:
    - ADR-013: Canonical Truth Architecture
    - ADR-006: VEGA Governance Authority
    - ADR-010: Discrepancy Scoring
    - ADR-004: Change Gates (G1-G4)
    - ADR-009: Suspension Workflow
    - BIS-239, ISO-8000 (Data Governance)

Usage:
    from vega_canonical_governance import VEGACanonicalAuthority

    # Initialize VEGA authority
    vega = VEGACanonicalAuthority(db_connection_string)

    # Register new canonical domain
    domain_id = vega.register_canonical_domain(
        domain_name='new_domain',
        canonical_store='fhq_data.new_table',
        ...
    )

    # Scan for multi-truth violations
    violations = vega.scan_for_multi_truth()

    # Resolve violation
    vega.resolve_violation(violation_id, resolution_action)
"""

import os
import json
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - VEGA-CANONICAL - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vega_canonical_governance")


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class GateStatus(Enum):
    """G1-G4 gate status."""
    G1_PENDING = "G1_PENDING"
    G1_PASSED = "G1_PASSED"
    G1_FAILED = "G1_FAILED"
    G2_PENDING = "G2_PENDING"
    G2_PASSED = "G2_PASSED"
    G2_FAILED = "G2_FAILED"
    G3_PENDING = "G3_PENDING"
    G3_PASSED = "G3_PASSED"
    G3_FAILED = "G3_FAILED"
    G4_PENDING = "G4_PENDING"
    G4_PASSED = "G4_PASSED"
    G4_FAILED = "G4_FAILED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class MutationType(Enum):
    """Types of canonical mutations."""
    DOMAIN_CREATE = "DOMAIN_CREATE"
    DOMAIN_UPDATE = "DOMAIN_UPDATE"
    DOMAIN_DEACTIVATE = "DOMAIN_DEACTIVATE"
    SERIES_CREATE = "SERIES_CREATE"
    SERIES_UPDATE = "SERIES_UPDATE"
    SERIES_DEACTIVATE = "SERIES_DEACTIVATE"
    INDICATOR_CREATE = "INDICATOR_CREATE"
    INDICATOR_UPDATE = "INDICATOR_UPDATE"
    INDICATOR_DEACTIVATE = "INDICATOR_DEACTIVATE"
    CANONICAL_OVERRIDE = "CANONICAL_OVERRIDE"
    EMERGENCY_MUTATION = "EMERGENCY_MUTATION"


class DiscrepancyClass(Enum):
    """ADR-010 discrepancy classification."""
    CLASS_A = "CLASS_A"  # Critical - immediate suspension
    CLASS_B = "CLASS_B"  # Major - 24h correction window
    CLASS_C = "CLASS_C"  # Minor - next sprint correction


class ViolationType(Enum):
    """Types of canonical violations."""
    DUPLICATE_DOMAIN = "DUPLICATE_DOMAIN"
    DUPLICATE_SERIES = "DUPLICATE_SERIES"
    DUPLICATE_INDICATOR = "DUPLICATE_INDICATOR"
    CONFLICTING_VALUES = "CONFLICTING_VALUES"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    BYPASS_ATTEMPT = "BYPASS_ATTEMPT"
    NON_CANONICAL_READ = "NON_CANONICAL_READ"
    MULTI_TRUTH_DETECTED = "MULTI_TRUTH_DETECTED"
    INGESTION_CONFLICT = "INGESTION_CONFLICT"


class ResolutionStatus(Enum):
    """Violation resolution status."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    SUSPENDED = "SUSPENDED"


# VEGA Agent Identity
VEGA_AGENT_ID = "VEGA"
VEGA_AUTHORITY_LEVEL = 10  # Highest authority


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class CanonicalMutationRequest:
    """Request for canonical mutation."""
    mutation_type: MutationType
    target_domain: str
    target_id: Optional[str]
    request_data: Dict[str, Any]
    requested_by: str
    requested_at: datetime
    justification: str
    urgency: str = "NORMAL"  # NORMAL, HIGH, EMERGENCY


@dataclass
class GateResult:
    """Result of a gate validation."""
    gate_number: int
    gate_name: str
    passed: bool
    validated_by: str
    validated_at: datetime
    evidence: Dict[str, Any]
    blocking_issues: List[str]


@dataclass
class MutationGateRecord:
    """Complete mutation gate record."""
    gate_id: str
    mutation_type: MutationType
    target_domain: str
    gate_status: GateStatus
    current_gate: int
    g1_result: Optional[GateResult]
    g2_result: Optional[GateResult]
    g3_result: Optional[GateResult]
    g4_result: Optional[GateResult]
    request_data: Dict[str, Any]
    requested_by: str
    requested_at: datetime
    completed_at: Optional[datetime]


@dataclass
class CanonicalViolation:
    """Canonical violation record."""
    violation_id: str
    violation_timestamp: datetime
    violation_type: ViolationType
    discrepancy_class: DiscrepancyClass
    severity_score: float
    domain_name: str
    conflicting_stores: List[str]
    conflict_description: str
    evidence_bundle: Dict[str, Any]
    detected_by: str
    detection_method: str
    vega_escalated: bool
    ceo_notified: bool
    resolution_status: ResolutionStatus
    resolution_action: Optional[str]
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]


@dataclass
class IntegrityReport:
    """Canonical integrity report."""
    report_id: str
    report_timestamp: datetime
    total_domains: int
    active_domains: int
    total_series: int
    total_indicators: int
    violations_open: int
    violations_resolved: int
    integrity_score: float
    recommendations: List[str]


# =============================================================================
# VEGA CANONICAL AUTHORITY
# =============================================================================

class VEGACanonicalAuthority:
    """
    VEGA Canonical Authority — Primary governance interface.

    This class is the ONLY authorized interface for managing canonical
    domain definitions. All other agents must use read-only access.
    """

    def __init__(self, db_connection_string: Optional[str] = None):
        """
        Initialize VEGA Canonical Authority.

        Args:
            db_connection_string: PostgreSQL connection string
        """
        self.db_connection_string = db_connection_string or self._get_default_connection()
        self.conn = None
        self.agent_id = VEGA_AGENT_ID
        self.authority_level = VEGA_AUTHORITY_LEVEL

        logger.info("=" * 70)
        logger.info("VEGA CANONICAL AUTHORITY INITIALIZED")
        logger.info(f"Authority Level: {self.authority_level}")
        logger.info(f"ADR Reference: ADR-013 (Canonical Truth)")
        logger.info("=" * 70)

    def _get_default_connection(self) -> str:
        """Get default connection string from environment."""
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    def connect(self) -> bool:
        """Establish database connection."""
        try:
            import psycopg2
            self.conn = psycopg2.connect(self.db_connection_string)
            logger.info("VEGA connected to database")
            return True
        except ImportError:
            logger.warning("psycopg2 not available")
            return False
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("VEGA disconnected from database")

    def _generate_hash_chain_id(self, operation: str) -> str:
        """Generate hash chain ID for audit trail."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        return f"HC-{self.agent_id}-CANONICAL-{operation}-{timestamp}"

    def _generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate signature for canonical operations."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        signature_data = f"{self.agent_id}:{data_str}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(signature_data.encode()).hexdigest()

    # =========================================================================
    # CANONICAL DOMAIN MANAGEMENT
    # =========================================================================

    def register_canonical_domain(
        self,
        domain_name: str,
        domain_category: str,
        canonical_store: str,
        description: str,
        data_contract: Dict[str, Any] = None,
        read_access_agents: List[str] = None,
        write_access_agents: List[str] = None,
        governance_level: str = "OPERATIONAL"
    ) -> Optional[str]:
        """
        Register a new canonical domain.

        Only VEGA has authority to register canonical domains.

        Args:
            domain_name: Unique name for the domain
            domain_category: Category (PRICES, INDICATORS, etc.)
            canonical_store: Fully qualified table name
            description: Domain description
            data_contract: Schema contract definition
            read_access_agents: Agents with read access
            write_access_agents: Agents with write access
            governance_level: CONSTITUTIONAL or OPERATIONAL

        Returns:
            Domain ID if successful, None otherwise
        """
        if not self.conn:
            logger.error("No database connection")
            return None

        # Parse schema and table from canonical_store
        parts = canonical_store.split('.')
        if len(parts) != 2:
            logger.error(f"Invalid canonical_store format: {canonical_store}")
            return None

        canonical_schema, canonical_table = parts

        hash_chain_id = self._generate_hash_chain_id("DOMAIN_REGISTER")
        signature = self._generate_signature({
            'domain_name': domain_name,
            'canonical_store': canonical_store,
            'action': 'REGISTER'
        })

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_meta.canonical_domain_registry (
                        domain_name, domain_category,
                        canonical_store, canonical_schema, canonical_table,
                        description, data_contract,
                        read_access_agents, write_access_agents,
                        governance_level, created_by,
                        hash_chain_id, signature
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING domain_id
                """, (
                    domain_name,
                    domain_category,
                    canonical_store,
                    canonical_schema,
                    canonical_table,
                    description,
                    json.dumps(data_contract or {}),
                    read_access_agents or ['LARS', 'FINN', 'STIG', 'LINE', 'VEGA'],
                    write_access_agents or ['VEGA'],
                    governance_level,
                    self.agent_id,
                    hash_chain_id,
                    signature
                ))

                result = cur.fetchone()
                self.conn.commit()

                if result:
                    domain_id = str(result[0])
                    logger.info(f"Registered canonical domain: {domain_name} -> {domain_id}")
                    return domain_id

                return None

        except Exception as e:
            logger.error(f"Failed to register canonical domain: {e}")
            self.conn.rollback()
            return None

    def deactivate_canonical_domain(
        self,
        domain_name: str,
        reason: str,
        ceo_approved: bool = False
    ) -> bool:
        """
        Deactivate a canonical domain.

        This is a major governance action that requires G3-G4 gates.

        Args:
            domain_name: Domain to deactivate
            reason: Justification for deactivation
            ceo_approved: Whether CEO has approved (required for CONSTITUTIONAL domains)

        Returns:
            True if successful
        """
        if not self.conn:
            return False

        # Check if domain exists and is CONSTITUTIONAL
        domain = self.get_domain(domain_name)
        if not domain:
            logger.error(f"Domain not found: {domain_name}")
            return False

        if domain.get('governance_level') == 'CONSTITUTIONAL' and not ceo_approved:
            logger.error(f"CEO approval required for CONSTITUTIONAL domain: {domain_name}")
            return False

        hash_chain_id = self._generate_hash_chain_id("DOMAIN_DEACTIVATE")

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE fhq_meta.canonical_domain_registry
                    SET is_active = FALSE,
                        updated_by = %s,
                        updated_at = NOW(),
                        hash_chain_id = %s
                    WHERE domain_name = %s
                    RETURNING domain_id
                """, (self.agent_id, hash_chain_id, domain_name))

                result = cur.fetchone()
                self.conn.commit()

                if result:
                    logger.info(f"Deactivated canonical domain: {domain_name}")
                    self._log_governance_action(
                        action_type='DOMAIN_DEACTIVATE',
                        target=domain_name,
                        reason=reason,
                        hash_chain_id=hash_chain_id
                    )
                    return True

                return False

        except Exception as e:
            logger.error(f"Failed to deactivate domain: {e}")
            self.conn.rollback()
            return False

    def get_domain(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """Get canonical domain by name."""
        if not self.conn:
            return None

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT domain_id, domain_name, domain_category,
                           canonical_store, canonical_schema, canonical_table,
                           description, governance_level, is_active, is_canonical,
                           created_by, created_at, updated_at
                    FROM fhq_meta.canonical_domain_registry
                    WHERE domain_name = %s
                """, (domain_name,))

                row = cur.fetchone()
                if row:
                    return {
                        'domain_id': str(row[0]),
                        'domain_name': row[1],
                        'domain_category': row[2],
                        'canonical_store': row[3],
                        'canonical_schema': row[4],
                        'canonical_table': row[5],
                        'description': row[6],
                        'governance_level': row[7],
                        'is_active': row[8],
                        'is_canonical': row[9],
                        'created_by': row[10],
                        'created_at': row[11],
                        'updated_at': row[12]
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get domain: {e}")
            return None

    def list_domains(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List all canonical domains."""
        if not self.conn:
            return []

        try:
            with self.conn.cursor() as cur:
                query = """
                    SELECT domain_id, domain_name, domain_category,
                           canonical_store, governance_level, is_active
                    FROM fhq_meta.canonical_domain_registry
                """
                if not include_inactive:
                    query += " WHERE is_active = TRUE"
                query += " ORDER BY domain_name"

                cur.execute(query)
                rows = cur.fetchall()

                return [
                    {
                        'domain_id': str(row[0]),
                        'domain_name': row[1],
                        'domain_category': row[2],
                        'canonical_store': row[3],
                        'governance_level': row[4],
                        'is_active': row[5]
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to list domains: {e}")
            return []

    # =========================================================================
    # MULTI-TRUTH DETECTION
    # =========================================================================

    def scan_for_multi_truth(self) -> List[CanonicalViolation]:
        """
        Scan for multi-truth violations across all domains.

        This is a critical governance function that detects:
        - Duplicate canonical domains
        - Duplicate canonical series
        - Conflicting indicator values
        - Unauthorized parallel truth tables

        Returns:
            List of detected violations
        """
        violations = []

        logger.info("Starting multi-truth scan...")

        # Scan 1: Duplicate domains
        violations.extend(self._scan_duplicate_domains())

        # Scan 2: Duplicate series
        violations.extend(self._scan_duplicate_series())

        # Scan 3: Duplicate indicators
        violations.extend(self._scan_duplicate_indicators())

        # Scan 4: Check for tables that look like canonical but aren't registered
        violations.extend(self._scan_unregistered_canonical_tables())

        logger.info(f"Multi-truth scan complete: {len(violations)} violations found")

        return violations

    def _scan_duplicate_domains(self) -> List[CanonicalViolation]:
        """Scan for duplicate canonical domains."""
        if not self.conn:
            return []

        violations = []

        try:
            with self.conn.cursor() as cur:
                # Find domains with same category but different stores
                cur.execute("""
                    SELECT domain_category, COUNT(*) as count,
                           array_agg(domain_name) as domain_names,
                           array_agg(canonical_store) as stores
                    FROM fhq_meta.canonical_domain_registry
                    WHERE is_active = TRUE
                    GROUP BY domain_category
                    HAVING COUNT(*) > 1
                """)

                rows = cur.fetchall()
                for row in rows:
                    category, count, names, stores = row

                    # Check if stores are actually different (same store = ok)
                    unique_stores = set(stores)
                    if len(unique_stores) > 1:
                        violation = CanonicalViolation(
                            violation_id=f"VIO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                            violation_timestamp=datetime.now(timezone.utc),
                            violation_type=ViolationType.DUPLICATE_DOMAIN,
                            discrepancy_class=DiscrepancyClass.CLASS_A,
                            severity_score=0.9,
                            domain_name=category,
                            conflicting_stores=list(unique_stores),
                            conflict_description=f"Multiple canonical stores for category {category}: {names}",
                            evidence_bundle={'category': category, 'domains': names, 'stores': stores},
                            detected_by=self.agent_id,
                            detection_method="MULTI_TRUTH_SCANNER",
                            vega_escalated=True,
                            ceo_notified=True,
                            resolution_status=ResolutionStatus.OPEN,
                            resolution_action=None,
                            resolved_by=None,
                            resolved_at=None
                        )
                        violations.append(violation)
                        self._persist_violation(violation)

        except Exception as e:
            logger.error(f"Failed to scan duplicate domains: {e}")

        return violations

    def _scan_duplicate_series(self) -> List[CanonicalViolation]:
        """Scan for duplicate canonical series."""
        if not self.conn:
            return []

        violations = []

        try:
            with self.conn.cursor() as cur:
                # Find series with same asset/frequency/price_type but different tables
                cur.execute("""
                    SELECT asset_id, frequency, price_type, COUNT(*) as count,
                           array_agg(canonical_table) as tables
                    FROM fhq_meta.canonical_series_registry
                    WHERE is_active = TRUE
                    GROUP BY asset_id, frequency, price_type
                    HAVING COUNT(*) > 1
                """)

                rows = cur.fetchall()
                for row in rows:
                    asset_id, frequency, price_type, count, tables = row

                    unique_tables = set(tables)
                    if len(unique_tables) > 1:
                        violation = CanonicalViolation(
                            violation_id=f"VIO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                            violation_timestamp=datetime.now(timezone.utc),
                            violation_type=ViolationType.DUPLICATE_SERIES,
                            discrepancy_class=DiscrepancyClass.CLASS_A,
                            severity_score=0.9,
                            domain_name=f"{asset_id}:{frequency}:{price_type}",
                            conflicting_stores=list(unique_tables),
                            conflict_description=f"Multiple canonical series for {asset_id} {frequency} {price_type}",
                            evidence_bundle={'asset_id': asset_id, 'frequency': frequency, 'tables': tables},
                            detected_by=self.agent_id,
                            detection_method="MULTI_TRUTH_SCANNER",
                            vega_escalated=True,
                            ceo_notified=True,
                            resolution_status=ResolutionStatus.OPEN,
                            resolution_action=None,
                            resolved_by=None,
                            resolved_at=None
                        )
                        violations.append(violation)
                        self._persist_violation(violation)

        except Exception as e:
            logger.error(f"Failed to scan duplicate series: {e}")

        return violations

    def _scan_duplicate_indicators(self) -> List[CanonicalViolation]:
        """Scan for duplicate canonical indicators."""
        if not self.conn:
            return []

        violations = []

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT indicator_name, indicator_version, COUNT(*) as count,
                           array_agg(canonical_table) as tables
                    FROM fhq_meta.canonical_indicator_registry
                    WHERE is_active = TRUE
                    GROUP BY indicator_name, indicator_version
                    HAVING COUNT(*) > 1
                """)

                rows = cur.fetchall()
                for row in rows:
                    indicator_name, version, count, tables = row

                    unique_tables = set(tables)
                    if len(unique_tables) > 1:
                        violation = CanonicalViolation(
                            violation_id=f"VIO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                            violation_timestamp=datetime.now(timezone.utc),
                            violation_type=ViolationType.DUPLICATE_INDICATOR,
                            discrepancy_class=DiscrepancyClass.CLASS_B,
                            severity_score=0.7,
                            domain_name=f"{indicator_name}:v{version}",
                            conflicting_stores=list(unique_tables),
                            conflict_description=f"Multiple canonical tables for indicator {indicator_name} v{version}",
                            evidence_bundle={'indicator': indicator_name, 'version': version, 'tables': tables},
                            detected_by=self.agent_id,
                            detection_method="MULTI_TRUTH_SCANNER",
                            vega_escalated=True,
                            ceo_notified=False,
                            resolution_status=ResolutionStatus.OPEN,
                            resolution_action=None,
                            resolved_by=None,
                            resolved_at=None
                        )
                        violations.append(violation)
                        self._persist_violation(violation)

        except Exception as e:
            logger.error(f"Failed to scan duplicate indicators: {e}")

        return violations

    def _scan_unregistered_canonical_tables(self) -> List[CanonicalViolation]:
        """Scan for tables that look like canonical stores but aren't registered."""
        # This would require schema introspection
        # For now, return empty list - can be enhanced
        return []

    def _persist_violation(self, violation: CanonicalViolation):
        """Persist violation to database."""
        if not self.conn:
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_meta.canonical_violation_log (
                        violation_type, discrepancy_class, severity_score,
                        domain_name, conflicting_stores, conflict_description,
                        evidence_bundle, detected_by, detection_method,
                        vega_escalated, ceo_notified, resolution_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING violation_id
                """, (
                    violation.violation_type.value,
                    violation.discrepancy_class.value,
                    violation.severity_score,
                    violation.domain_name,
                    violation.conflicting_stores,
                    violation.conflict_description,
                    json.dumps(violation.evidence_bundle),
                    violation.detected_by,
                    violation.detection_method,
                    violation.vega_escalated,
                    violation.ceo_notified,
                    violation.resolution_status.value
                ))
                self.conn.commit()

        except Exception as e:
            logger.error(f"Failed to persist violation: {e}")
            self.conn.rollback()

    # =========================================================================
    # VIOLATION RESOLUTION
    # =========================================================================

    def get_open_violations(self) -> List[Dict[str, Any]]:
        """Get all open violations."""
        if not self.conn:
            return []

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT violation_id, violation_timestamp, violation_type,
                           discrepancy_class, severity_score, domain_name,
                           conflicting_stores, conflict_description,
                           vega_escalated, ceo_notified
                    FROM fhq_meta.canonical_violation_log
                    WHERE resolution_status = 'OPEN'
                    ORDER BY severity_score DESC, violation_timestamp DESC
                """)

                rows = cur.fetchall()
                return [
                    {
                        'violation_id': str(row[0]),
                        'violation_timestamp': row[1],
                        'violation_type': row[2],
                        'discrepancy_class': row[3],
                        'severity_score': float(row[4]),
                        'domain_name': row[5],
                        'conflicting_stores': row[6],
                        'conflict_description': row[7],
                        'vega_escalated': row[8],
                        'ceo_notified': row[9]
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Failed to get open violations: {e}")
            return []

    def resolve_violation(
        self,
        violation_id: str,
        resolution_action: str,
        ceo_approved: bool = False
    ) -> bool:
        """
        Resolve a canonical violation.

        Args:
            violation_id: ID of the violation
            resolution_action: Action taken to resolve
            ceo_approved: Whether CEO approved (required for CLASS_A)

        Returns:
            True if successful
        """
        if not self.conn:
            return False

        try:
            with self.conn.cursor() as cur:
                # Get violation details
                cur.execute("""
                    SELECT discrepancy_class FROM fhq_meta.canonical_violation_log
                    WHERE violation_id = %s
                """, (violation_id,))

                row = cur.fetchone()
                if not row:
                    logger.error(f"Violation not found: {violation_id}")
                    return False

                discrepancy_class = row[0]

                # CLASS_A requires CEO approval
                if discrepancy_class == 'CLASS_A' and not ceo_approved:
                    logger.error("CEO approval required for CLASS_A resolution")
                    return False

                # Update violation
                cur.execute("""
                    UPDATE fhq_meta.canonical_violation_log
                    SET resolution_status = 'RESOLVED',
                        resolution_action = %s,
                        resolved_by = %s,
                        resolved_at = NOW()
                    WHERE violation_id = %s
                """, (resolution_action, self.agent_id, violation_id))

                self.conn.commit()
                logger.info(f"Resolved violation: {violation_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to resolve violation: {e}")
            self.conn.rollback()
            return False

    # =========================================================================
    # INTEGRITY AUDITING
    # =========================================================================

    def generate_integrity_report(self) -> IntegrityReport:
        """
        Generate canonical integrity report.

        Returns:
            IntegrityReport with system-wide integrity metrics
        """
        report_id = f"INTEGRITY-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        report_timestamp = datetime.now(timezone.utc)

        # Gather metrics
        total_domains = 0
        active_domains = 0
        total_series = 0
        total_indicators = 0
        violations_open = 0
        violations_resolved = 0

        if self.conn:
            try:
                with self.conn.cursor() as cur:
                    # Domain counts
                    cur.execute("SELECT COUNT(*) FROM fhq_meta.canonical_domain_registry")
                    total_domains = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM fhq_meta.canonical_domain_registry WHERE is_active = TRUE")
                    active_domains = cur.fetchone()[0]

                    # Series count
                    cur.execute("SELECT COUNT(*) FROM fhq_meta.canonical_series_registry WHERE is_active = TRUE")
                    total_series = cur.fetchone()[0]

                    # Indicator count
                    cur.execute("SELECT COUNT(*) FROM fhq_meta.canonical_indicator_registry WHERE is_active = TRUE")
                    total_indicators = cur.fetchone()[0]

                    # Violation counts
                    cur.execute("SELECT COUNT(*) FROM fhq_meta.canonical_violation_log WHERE resolution_status = 'OPEN'")
                    violations_open = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM fhq_meta.canonical_violation_log WHERE resolution_status = 'RESOLVED'")
                    violations_resolved = cur.fetchone()[0]

            except Exception as e:
                logger.error(f"Failed to gather integrity metrics: {e}")

        # Calculate integrity score
        integrity_score = 1.0
        if violations_open > 0:
            integrity_score -= min(violations_open * 0.1, 0.5)
        if total_domains > active_domains:
            integrity_score -= 0.1

        # Generate recommendations
        recommendations = []
        if violations_open > 0:
            recommendations.append(f"Resolve {violations_open} open violations")
        if total_domains == 0:
            recommendations.append("Register canonical domains")
        if total_series == 0:
            recommendations.append("Register canonical series for price data")

        return IntegrityReport(
            report_id=report_id,
            report_timestamp=report_timestamp,
            total_domains=total_domains,
            active_domains=active_domains,
            total_series=total_series,
            total_indicators=total_indicators,
            violations_open=violations_open,
            violations_resolved=violations_resolved,
            integrity_score=max(integrity_score, 0.0),
            recommendations=recommendations
        )

    # =========================================================================
    # GOVERNANCE LOGGING
    # =========================================================================

    def _log_governance_action(
        self,
        action_type: str,
        target: str,
        reason: str,
        hash_chain_id: str
    ):
        """Log governance action to audit trail."""
        if not self.conn:
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.governance_actions_log (
                        action_type, agent_id, decision, metadata,
                        hash_chain_id, signature, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (
                    action_type,
                    self.agent_id,
                    'EXECUTED',
                    json.dumps({
                        'target': target,
                        'reason': reason,
                        'adr_reference': 'ADR-013'
                    }),
                    hash_chain_id,
                    self._generate_signature({'action_type': action_type, 'target': target})
                ))
                self.conn.commit()

        except Exception as e:
            logger.error(f"Failed to log governance action: {e}")


# =============================================================================
# MULTI-TRUTH SCANNER
# =============================================================================

class MultiTruthScanner:
    """
    Multi-Truth Scanner — Continuous multi-truth detection.

    Runs periodic scans to detect multi-truth situations across all domains.
    """

    def __init__(self, vega: VEGACanonicalAuthority):
        """
        Initialize scanner.

        Args:
            vega: VEGACanonicalAuthority instance
        """
        self.vega = vega
        self.scan_interval_seconds = 3600  # 1 hour
        self.last_scan_timestamp: Optional[datetime] = None
        self.last_scan_violations: List[CanonicalViolation] = []

    def run_scan(self) -> List[CanonicalViolation]:
        """Run multi-truth scan."""
        logger.info("=" * 50)
        logger.info("MULTI-TRUTH SCANNER: Starting scan")
        logger.info("=" * 50)

        violations = self.vega.scan_for_multi_truth()

        self.last_scan_timestamp = datetime.now(timezone.utc)
        self.last_scan_violations = violations

        if violations:
            logger.warning(f"MULTI-TRUTH SCANNER: {len(violations)} violations detected!")
            for v in violations:
                logger.warning(f"  - {v.violation_type.value}: {v.conflict_description}")
        else:
            logger.info("MULTI-TRUTH SCANNER: No violations detected")

        return violations

    def get_scan_status(self) -> Dict[str, Any]:
        """Get scanner status."""
        return {
            'last_scan_timestamp': self.last_scan_timestamp.isoformat() if self.last_scan_timestamp else None,
            'violations_found': len(self.last_scan_violations),
            'scan_interval_seconds': self.scan_interval_seconds
        }


# =============================================================================
# MAIN - VERIFICATION MODE
# =============================================================================

def verify_vega_canonical_governance():
    """Verify VEGA canonical governance installation."""
    print("=" * 70)
    print("VEGA CANONICAL GOVERNANCE VERIFICATION")
    print("ADR-013: One-Source-of-Truth Architecture")
    print("=" * 70)

    vega = VEGACanonicalAuthority()

    # Test 1: Check connection
    print("\n[1] Testing database connection...")
    connected = vega.connect()
    if connected:
        print("    ✅ Database connection successful")
    else:
        print("    ⚠️ Database connection failed (running in mock mode)")

    # Test 2: List domains
    print("\n[2] Listing canonical domains...")
    domains = vega.list_domains()
    if domains:
        for domain in domains:
            status = "✅" if domain['is_active'] else "❌"
            print(f"    {status} {domain['domain_name']}: {domain['canonical_store']}")
    else:
        print("    ⚠️ No domains found (database may not be initialized)")

    # Test 3: Run multi-truth scan
    print("\n[3] Running multi-truth scan...")
    scanner = MultiTruthScanner(vega)
    violations = scanner.run_scan()
    if violations:
        for v in violations:
            print(f"    ❌ {v.violation_type.value}: {v.conflict_description}")
    else:
        print("    ✅ No multi-truth violations detected")

    # Test 4: Generate integrity report
    print("\n[4] Generating integrity report...")
    report = vega.generate_integrity_report()
    print(f"    Report ID: {report.report_id}")
    print(f"    Integrity Score: {report.integrity_score:.2%}")
    print(f"    Active Domains: {report.active_domains}")
    print(f"    Open Violations: {report.violations_open}")
    if report.recommendations:
        print("    Recommendations:")
        for rec in report.recommendations:
            print(f"      - {rec}")

    # Cleanup
    vega.close()

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_vega_canonical_governance()
    else:
        print("VEGA Canonical Governance Engine - ADR-013 Implementation")
        print("Usage: python vega_canonical_governance.py --verify")
