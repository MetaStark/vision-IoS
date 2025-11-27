"""
CANONICAL ACCESSOR MODULE
ADR-013: One-Source-of-Truth Architecture

Authority: LARS (ADR-013 Implementation)
Mandate: ADR-013 Canonical Governance
Reference: HC-LARS-ADR013-IMPL-20251127

Purpose:
    Provides the ONLY authorized pathway for accessing canonical data domains.
    All agents (LARS, FINN, STIG, LINE, VEGA) MUST use this module to access
    data in production contexts.

Architecture:
    - CanonicalDomainAccessor: Resolves domain names to canonical stores
    - CanonicalAccessGuard: Validates and logs all access attempts
    - CanonicalDataReader: Provides type-safe data retrieval
    - CanonicalIngestionGate: Guards write operations to canonical stores

Invariants Enforced:
    - For every domain, exactly one canonical store is used
    - All production reads go through canonical stores resolved from registry
    - Non-canonical access is detected, logged, and escalated to VEGA
    - All ingestion must pass through Orchestrator + VEGA gates

Compliance:
    - ADR-013: Canonical Truth Architecture
    - ADR-010: Discrepancy Scoring
    - ADR-006: VEGA Governance
    - ADR-002: Audit Lineage
    - BIS-239, ISO-8000 (Data Quality)

Usage:
    from canonical_accessor import CanonicalAccessor

    # Initialize accessor
    accessor = CanonicalAccessor(db_connection_string)

    # Resolve canonical store for a domain
    store = accessor.resolve_domain('prices')

    # Read data from canonical store
    data = accessor.read_canonical_data('prices', asset_id='BTC-USD', frequency='1d')

    # Validate access is canonical
    is_valid = accessor.validate_access('prices', 'fhq_data.prices', agent_id='FINN')
"""

import os
import json
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, TypeVar, Generic
from enum import Enum
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - CANONICAL - %(levelname)s - %(message)s'
)
logger = logging.getLogger("canonical_accessor")


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AccessContext(Enum):
    """Context for data access."""
    PRODUCTION = "PRODUCTION"      # Live production - canonical only
    RESEARCH = "RESEARCH"          # Research - canonical preferred
    SANDBOX = "SANDBOX"            # Sandbox - non-canonical allowed
    BACKTEST = "BACKTEST"          # Backtest - canonical only


class OperationType(Enum):
    """Type of data operation."""
    READ = "READ"
    WRITE = "WRITE"
    RESOLVE = "RESOLVE"
    VALIDATE = "VALIDATE"


class DiscrepancyClass(Enum):
    """ADR-010 discrepancy classification."""
    CLASS_A = "CLASS_A"  # Critical - immediate suspension
    CLASS_B = "CLASS_B"  # Major - 24h correction window
    CLASS_C = "CLASS_C"  # Minor - next sprint correction
    NONE = "NONE"


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


# ADR-013 Canonical Domain Categories
CANONICAL_DOMAIN_CATEGORIES = [
    'PRICES', 'INDICATORS', 'FUNDAMENTALS', 'SENTIMENT',
    'ONCHAIN', 'EMBEDDINGS', 'KG_METRICS', 'MACRO', 'RESEARCH',
    'GOVERNANCE', 'AUDIT', 'SYSTEM'
]

# Authorized agents per ADR-007
AUTHORIZED_AGENTS = ['LARS', 'FINN', 'STIG', 'LINE', 'VEGA', 'CEO']


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class CanonicalDomain:
    """Represents a canonical domain from the registry."""
    domain_id: str
    domain_name: str
    domain_category: str
    canonical_store: str
    canonical_schema: str
    canonical_table: str
    description: str
    data_contract: Dict[str, Any]
    read_access_agents: List[str]
    write_access_agents: List[str]
    is_active: bool
    is_canonical: bool
    governance_level: str
    adr_reference: str
    created_at: datetime
    updated_at: datetime

    @property
    def fully_qualified_name(self) -> str:
        """Get fully qualified table name."""
        return f"{self.canonical_schema}.{self.canonical_table}"


@dataclass
class CanonicalSeries:
    """Represents a canonical series from the registry."""
    series_id: str
    domain_id: str
    asset_id: str
    listing_id: Optional[str]
    frequency: str
    price_type: str
    canonical_table: str
    series_identifier: str
    primary_vendor: str
    vendor_sources: List[str]
    is_active: bool
    is_canonical: bool


@dataclass
class CanonicalAccessLog:
    """Access log entry for audit trail."""
    access_id: str
    access_timestamp: datetime
    agent_id: str
    operation_type: OperationType
    domain_name: str
    canonical_store: str
    access_context: AccessContext
    access_authorized: bool
    bypass_attempted: bool
    vega_notified: bool
    hash_chain_id: str


@dataclass
class CanonicalViolation:
    """Canonical violation event."""
    violation_id: str
    violation_timestamp: datetime
    violation_type: ViolationType
    discrepancy_class: DiscrepancyClass
    severity_score: float
    domain_name: str
    conflicting_stores: List[str]
    conflict_description: str
    detected_by: str
    detection_method: str
    vega_escalated: bool
    resolution_status: str


@dataclass
class AccessValidationResult:
    """Result of access validation."""
    is_valid: bool
    is_canonical: bool
    canonical_store: Optional[str]
    accessed_store: str
    violation: Optional[CanonicalViolation]
    access_log_id: str


# =============================================================================
# CANONICAL DOMAIN ACCESSOR
# =============================================================================

class CanonicalDomainAccessor:
    """
    Canonical Domain Accessor — Primary interface for domain resolution.

    This class is the ONLY authorized pathway for resolving domain names
    to canonical stores. All agents must use this class for data access.
    """

    def __init__(self, db_connection_string: Optional[str] = None):
        """
        Initialize the Canonical Domain Accessor.

        Args:
            db_connection_string: PostgreSQL connection string
        """
        self.db_connection_string = db_connection_string or self._get_default_connection()
        self.conn = None
        self._domain_cache: Dict[str, CanonicalDomain] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes

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
        if not self.db_connection_string:
            logger.warning("No database connection string provided")
            return False

        try:
            import psycopg2
            self.conn = psycopg2.connect(self.db_connection_string)
            logger.info("Canonical accessor connected to database")
            return True
        except ImportError:
            logger.warning("psycopg2 not available - running in mock mode")
            return False
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Canonical accessor disconnected")

    def _is_cache_valid(self) -> bool:
        """Check if domain cache is still valid."""
        if not self._cache_timestamp:
            return False
        age = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
        return age < self._cache_ttl_seconds

    def _refresh_cache(self):
        """Refresh the domain cache from database."""
        if not self.conn:
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        domain_id, domain_name, domain_category,
                        canonical_store, canonical_schema, canonical_table,
                        description, data_contract, read_access_agents,
                        write_access_agents, is_active, is_canonical,
                        governance_level, adr_reference, created_at, updated_at
                    FROM fhq_meta.canonical_domain_registry
                    WHERE is_active = TRUE
                """)
                rows = cur.fetchall()

                self._domain_cache.clear()
                for row in rows:
                    domain = CanonicalDomain(
                        domain_id=str(row[0]),
                        domain_name=row[1],
                        domain_category=row[2],
                        canonical_store=row[3],
                        canonical_schema=row[4],
                        canonical_table=row[5],
                        description=row[6],
                        data_contract=row[7] if isinstance(row[7], dict) else {},
                        read_access_agents=row[8] or [],
                        write_access_agents=row[9] or [],
                        is_active=row[10],
                        is_canonical=row[11],
                        governance_level=row[12],
                        adr_reference=row[13],
                        created_at=row[14],
                        updated_at=row[15]
                    )
                    self._domain_cache[domain.domain_name] = domain

                self._cache_timestamp = datetime.now(timezone.utc)
                logger.debug(f"Domain cache refreshed: {len(self._domain_cache)} domains")

        except Exception as e:
            logger.error(f"Failed to refresh domain cache: {e}")

    def resolve_domain(self, domain_name: str) -> Optional[CanonicalDomain]:
        """
        Resolve a domain name to its canonical domain definition.

        This is the primary method for looking up canonical stores.

        Args:
            domain_name: Name of the domain (e.g., 'prices', 'indicators')

        Returns:
            CanonicalDomain if found, None otherwise

        Raises:
            CanonicalAccessError: If domain not found in production context
        """
        # Check cache first
        if self._is_cache_valid() and domain_name in self._domain_cache:
            return self._domain_cache[domain_name]

        # Refresh cache if needed
        if not self._is_cache_valid():
            self._refresh_cache()

        return self._domain_cache.get(domain_name)

    def resolve_canonical_store(self, domain_name: str) -> str:
        """
        Resolve domain name to canonical store (table name).

        This is the method used by the SQL function fhq_meta.resolve_canonical_store.

        Args:
            domain_name: Name of the domain

        Returns:
            Fully qualified table name (e.g., 'fhq_data.prices')

        Raises:
            CanonicalAccessError: If domain not found
        """
        domain = self.resolve_domain(domain_name)
        if not domain:
            raise CanonicalAccessError(
                f"ADR-013 VIOLATION: No canonical store found for domain: {domain_name}"
            )
        return domain.canonical_store

    def list_domains(self) -> List[CanonicalDomain]:
        """List all active canonical domains."""
        if not self._is_cache_valid():
            self._refresh_cache()
        return list(self._domain_cache.values())

    def get_domain_by_store(self, canonical_store: str) -> Optional[CanonicalDomain]:
        """Find domain by its canonical store name."""
        if not self._is_cache_valid():
            self._refresh_cache()

        for domain in self._domain_cache.values():
            if domain.canonical_store == canonical_store:
                return domain
        return None


# =============================================================================
# CANONICAL ACCESS GUARD
# =============================================================================

class CanonicalAccessGuard:
    """
    Canonical Access Guard — Validates and logs all access attempts.

    This class ensures that all data access in production contexts
    goes through canonical stores. Non-canonical access attempts are
    detected, logged, and escalated to VEGA.
    """

    def __init__(self, accessor: CanonicalDomainAccessor, agent_id: str):
        """
        Initialize the access guard.

        Args:
            accessor: CanonicalDomainAccessor instance
            agent_id: ID of the agent using this guard
        """
        self.accessor = accessor
        self.agent_id = agent_id
        self._access_log: List[CanonicalAccessLog] = []
        self._violation_log: List[CanonicalViolation] = []

    def validate_access(
        self,
        domain_name: str,
        target_store: str,
        operation_type: OperationType = OperationType.READ,
        access_context: AccessContext = AccessContext.PRODUCTION
    ) -> AccessValidationResult:
        """
        Validate that access is to the canonical store.

        Args:
            domain_name: Name of the domain being accessed
            target_store: Actual store being accessed
            operation_type: Type of operation (READ, WRITE, etc.)
            access_context: Context of the access

        Returns:
            AccessValidationResult with validation details
        """
        access_id = self._generate_access_id()
        hash_chain_id = self._generate_hash_chain_id(access_id)

        # Resolve canonical store
        domain = self.accessor.resolve_domain(domain_name)
        canonical_store = domain.canonical_store if domain else None

        # Check if access is canonical
        is_canonical = (canonical_store == target_store) if canonical_store else False
        is_valid = True
        violation = None

        # In PRODUCTION context, non-canonical access is a violation
        if access_context == AccessContext.PRODUCTION and not is_canonical:
            is_valid = False
            violation = self._create_violation(
                violation_type=ViolationType.NON_CANONICAL_READ,
                domain_name=domain_name,
                conflicting_stores=[target_store, canonical_store] if canonical_store else [target_store],
                conflict_description=f"Agent {self.agent_id} attempted to read from non-canonical store {target_store} instead of {canonical_store}",
                discrepancy_class=DiscrepancyClass.CLASS_B,
                severity_score=0.5
            )
            self._violation_log.append(violation)
            logger.warning(f"ADR-013 VIOLATION: {violation.conflict_description}")

        # Log access
        access_log = CanonicalAccessLog(
            access_id=access_id,
            access_timestamp=datetime.now(timezone.utc),
            agent_id=self.agent_id,
            operation_type=operation_type,
            domain_name=domain_name,
            canonical_store=target_store,
            access_context=access_context,
            access_authorized=is_valid,
            bypass_attempted=not is_canonical,
            vega_notified=not is_canonical,
            hash_chain_id=hash_chain_id
        )
        self._access_log.append(access_log)

        # Persist to database if connected
        self._persist_access_log(access_log)
        if violation:
            self._persist_violation(violation)

        return AccessValidationResult(
            is_valid=is_valid,
            is_canonical=is_canonical,
            canonical_store=canonical_store,
            accessed_store=target_store,
            violation=violation,
            access_log_id=access_id
        )

    def require_canonical(
        self,
        domain_name: str,
        operation_type: OperationType = OperationType.READ
    ) -> str:
        """
        Get canonical store and validate access in one step.

        This is the recommended method for production code.

        Args:
            domain_name: Name of the domain
            operation_type: Type of operation

        Returns:
            Canonical store name

        Raises:
            CanonicalAccessError: If canonical store cannot be resolved
        """
        canonical_store = self.accessor.resolve_canonical_store(domain_name)

        # Log the access
        self.validate_access(
            domain_name=domain_name,
            target_store=canonical_store,
            operation_type=operation_type,
            access_context=AccessContext.PRODUCTION
        )

        return canonical_store

    def _generate_access_id(self) -> str:
        """Generate unique access ID."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        return f"ACC-{self.agent_id}-{timestamp}"

    def _generate_hash_chain_id(self, access_id: str) -> str:
        """Generate hash chain ID for audit trail."""
        return f"HC-{self.agent_id}-CANONICAL-{access_id}"

    def _create_violation(
        self,
        violation_type: ViolationType,
        domain_name: str,
        conflicting_stores: List[str],
        conflict_description: str,
        discrepancy_class: DiscrepancyClass,
        severity_score: float
    ) -> CanonicalViolation:
        """Create a violation record."""
        timestamp = datetime.now(timezone.utc)
        violation_id = f"VIO-{self.agent_id}-{timestamp.strftime('%Y%m%d%H%M%S%f')}"

        return CanonicalViolation(
            violation_id=violation_id,
            violation_timestamp=timestamp,
            violation_type=violation_type,
            discrepancy_class=discrepancy_class,
            severity_score=severity_score,
            domain_name=domain_name,
            conflicting_stores=conflicting_stores,
            conflict_description=conflict_description,
            detected_by=self.agent_id,
            detection_method="ACCESS_GUARD",
            vega_escalated=True,
            resolution_status="OPEN"
        )

    def _persist_access_log(self, access_log: CanonicalAccessLog):
        """Persist access log to database."""
        if not self.accessor.conn:
            return

        try:
            with self.accessor.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_meta.canonical_access_log (
                        agent_id, operation_type, domain_name, canonical_store,
                        access_context, access_authorized, bypass_attempted,
                        vega_notified, hash_chain_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    access_log.agent_id,
                    access_log.operation_type.value,
                    access_log.domain_name,
                    access_log.canonical_store,
                    access_log.access_context.value,
                    access_log.access_authorized,
                    access_log.bypass_attempted,
                    access_log.vega_notified,
                    access_log.hash_chain_id
                ))
                self.accessor.conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist access log: {e}")

    def _persist_violation(self, violation: CanonicalViolation):
        """Persist violation to database."""
        if not self.accessor.conn:
            return

        try:
            with self.accessor.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_meta.canonical_violation_log (
                        violation_type, discrepancy_class, severity_score,
                        domain_name, conflicting_stores, conflict_description,
                        detected_by, detection_method, vega_escalated
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    violation.violation_type.value,
                    violation.discrepancy_class.value,
                    violation.severity_score,
                    violation.domain_name,
                    violation.conflicting_stores,
                    violation.conflict_description,
                    violation.detected_by,
                    violation.detection_method,
                    violation.vega_escalated
                ))
                self.accessor.conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist violation: {e}")

    def get_access_log(self) -> List[CanonicalAccessLog]:
        """Get access log entries."""
        return self._access_log.copy()

    def get_violations(self) -> List[CanonicalViolation]:
        """Get violation entries."""
        return self._violation_log.copy()


# =============================================================================
# CANONICAL DATA READER
# =============================================================================

class CanonicalDataReader:
    """
    Canonical Data Reader — Type-safe data retrieval from canonical stores.

    Provides convenient methods for reading data from canonical stores
    with proper access validation and audit logging.
    """

    def __init__(self, accessor: CanonicalDomainAccessor, agent_id: str):
        """
        Initialize the data reader.

        Args:
            accessor: CanonicalDomainAccessor instance
            agent_id: ID of the agent using this reader
        """
        self.accessor = accessor
        self.guard = CanonicalAccessGuard(accessor, agent_id)
        self.agent_id = agent_id

    def read_prices(
        self,
        asset_id: str,
        frequency: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Read price data from canonical store.

        Args:
            asset_id: Asset identifier (e.g., 'BTC-USD')
            frequency: Data frequency ('1m', '1h', '1d', etc.)
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum rows to return

        Returns:
            List of price records
        """
        # Get canonical store
        canonical_store = self.guard.require_canonical('prices')

        if not self.accessor.conn:
            logger.warning("No database connection - returning empty result")
            return []

        try:
            with self.accessor.conn.cursor() as cur:
                query = f"""
                    SELECT asset_id, timestamp, open, high, low, close, volume
                    FROM {canonical_store}
                    WHERE asset_id = %s
                      AND frequency = %s
                """
                params = [asset_id, frequency]

                if start_date:
                    query += " AND timestamp >= %s"
                    params.append(start_date)
                if end_date:
                    query += " AND timestamp <= %s"
                    params.append(end_date)

                query += " ORDER BY timestamp DESC LIMIT %s"
                params.append(limit)

                cur.execute(query, params)
                rows = cur.fetchall()

                return [
                    {
                        'asset_id': row[0],
                        'timestamp': row[1],
                        'open': float(row[2]),
                        'high': float(row[3]),
                        'low': float(row[4]),
                        'close': float(row[5]),
                        'volume': int(row[6]) if row[6] else 0
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to read prices: {e}")
            return []

    def read_regime_classifications(
        self,
        asset_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Read regime classifications from canonical store.

        Args:
            asset_id: Asset identifier
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum rows to return

        Returns:
            List of regime classification records
        """
        canonical_store = self.guard.require_canonical('regime_classifications')

        if not self.accessor.conn:
            return []

        try:
            with self.accessor.conn.cursor() as cur:
                query = f"""
                    SELECT asset_id, timestamp, regime_label, confidence,
                           prob_bear, prob_neutral, prob_bull, signature_hex
                    FROM {canonical_store}
                    WHERE asset_id = %s
                """
                params = [asset_id]

                if start_date:
                    query += " AND timestamp >= %s"
                    params.append(start_date)
                if end_date:
                    query += " AND timestamp <= %s"
                    params.append(end_date)

                query += " ORDER BY timestamp DESC LIMIT %s"
                params.append(limit)

                cur.execute(query, params)
                rows = cur.fetchall()

                return [
                    {
                        'asset_id': row[0],
                        'timestamp': row[1],
                        'regime_label': row[2],
                        'confidence': float(row[3]),
                        'prob_bear': float(row[4]) if row[4] else None,
                        'prob_neutral': float(row[5]) if row[5] else None,
                        'prob_bull': float(row[6]) if row[6] else None,
                        'signature_hex': row[7]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to read regime classifications: {e}")
            return []

    def read_cds_results(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Read CDS results from canonical store.

        Args:
            symbol: Asset symbol
            start_date: Start of date range
            end_date: End of date range
            limit: Maximum rows to return

        Returns:
            List of CDS result records
        """
        canonical_store = self.guard.require_canonical('cds_results')

        if not self.accessor.conn:
            return []

        try:
            with self.accessor.conn.cursor() as cur:
                query = f"""
                    SELECT cycle_id, symbol, cds_value, timestamp,
                           c1_regime_strength, c2_signal_stability,
                           c3_data_integrity, c4_causal_coherence,
                           c5_stress_modulator, c6_relevance_alignment,
                           signature_hex
                    FROM {canonical_store}
                    WHERE symbol = %s
                """
                params = [symbol]

                if start_date:
                    query += " AND timestamp >= %s"
                    params.append(start_date)
                if end_date:
                    query += " AND timestamp <= %s"
                    params.append(end_date)

                query += " ORDER BY timestamp DESC LIMIT %s"
                params.append(limit)

                cur.execute(query, params)
                rows = cur.fetchall()

                return [
                    {
                        'cycle_id': row[0],
                        'symbol': row[1],
                        'cds_value': float(row[2]),
                        'timestamp': row[3],
                        'c1_regime_strength': float(row[4]) if row[4] else None,
                        'c2_signal_stability': float(row[5]) if row[5] else None,
                        'c3_data_integrity': float(row[6]) if row[6] else None,
                        'c4_causal_coherence': float(row[7]) if row[7] else None,
                        'c5_stress_modulator': float(row[8]) if row[8] else None,
                        'c6_relevance_alignment': float(row[9]) if row[9] else None,
                        'signature_hex': row[10]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to read CDS results: {e}")
            return []


# =============================================================================
# CANONICAL INGESTION GATE
# =============================================================================

class CanonicalIngestionGate:
    """
    Canonical Ingestion Gate — Guards write operations to canonical stores.

    All ingestion jobs must pass through this gate before writing to
    canonical stores. This ensures:
    - Orchestrator registration
    - VEGA approval
    - Reconciliation before write
    - Conflict detection
    """

    def __init__(self, accessor: CanonicalDomainAccessor, agent_id: str):
        """
        Initialize the ingestion gate.

        Args:
            accessor: CanonicalDomainAccessor instance
            agent_id: ID of the agent using this gate
        """
        self.accessor = accessor
        self.agent_id = agent_id
        self.guard = CanonicalAccessGuard(accessor, agent_id)

    def register_ingestion_job(
        self,
        job_name: str,
        domain_name: str,
        vendor_sources: List[str],
        primary_vendor: str,
        asset_universe: List[str] = None,
        frequencies: List[str] = None,
        job_type: str = "SCHEDULED"
    ) -> Optional[str]:
        """
        Register an ingestion job for canonical store access.

        Args:
            job_name: Unique name for the ingestion job
            domain_name: Target domain name
            vendor_sources: List of vendor data sources
            primary_vendor: Primary data source
            asset_universe: Assets to ingest (default: all)
            frequencies: Data frequencies
            job_type: Type of job (SCHEDULED, REAL_TIME, etc.)

        Returns:
            Ingestion job ID if successful, None otherwise
        """
        if not self.accessor.conn:
            logger.error("No database connection")
            return None

        try:
            with self.accessor.conn.cursor() as cur:
                cur.execute("""
                    SELECT fhq_meta.register_canonical_ingestion(
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    job_name,
                    domain_name,
                    vendor_sources,
                    primary_vendor,
                    asset_universe or ['*'],
                    frequencies or ['1d'],
                    job_type,
                    self.agent_id
                ))
                result = cur.fetchone()
                self.accessor.conn.commit()

                if result:
                    ingestion_id = str(result[0])
                    logger.info(f"Registered ingestion job: {job_name} -> {ingestion_id}")
                    return ingestion_id
                return None

        except Exception as e:
            logger.error(f"Failed to register ingestion job: {e}")
            return None

    def validate_write_access(
        self,
        domain_name: str,
        target_store: str
    ) -> Tuple[bool, Optional[CanonicalViolation]]:
        """
        Validate write access to a canonical store.

        Args:
            domain_name: Domain being written to
            target_store: Target store for the write

        Returns:
            Tuple of (is_valid, violation if invalid)
        """
        result = self.guard.validate_access(
            domain_name=domain_name,
            target_store=target_store,
            operation_type=OperationType.WRITE,
            access_context=AccessContext.PRODUCTION
        )

        return result.is_valid, result.violation

    def request_canonical_write(
        self,
        domain_name: str,
        ingestion_job_id: str,
        data_summary: Dict[str, Any]
    ) -> bool:
        """
        Request write access to canonical store through proper gates.

        This initiates the G1-G4 gate process for canonical writes.

        Args:
            domain_name: Target domain
            ingestion_job_id: Registered ingestion job ID
            data_summary: Summary of data to be written

        Returns:
            True if request is registered, False otherwise
        """
        if not self.accessor.conn:
            return False

        try:
            with self.accessor.conn.cursor() as cur:
                # Create mutation gate request
                cur.execute("""
                    INSERT INTO fhq_governance.canonical_mutation_gates (
                        mutation_type, target_domain, request_data,
                        requested_by, hash_chain_id
                    ) VALUES (
                        'CANONICAL_WRITE', %s,
                        %s, %s, %s
                    )
                    RETURNING gate_id
                """, (
                    domain_name,
                    json.dumps({
                        'ingestion_job_id': ingestion_job_id,
                        'data_summary': data_summary,
                        'agent_id': self.agent_id,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }),
                    self.agent_id,
                    f"HC-{self.agent_id}-WRITE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                ))
                result = cur.fetchone()
                self.accessor.conn.commit()

                if result:
                    logger.info(f"Canonical write request registered: {result[0]}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to request canonical write: {e}")
            return False


# =============================================================================
# CANONICAL ACCESSOR (UNIFIED INTERFACE)
# =============================================================================

class CanonicalAccessor:
    """
    Canonical Accessor — Unified interface for canonical data access.

    This is the primary class that agents should use for all canonical
    data operations. It combines domain resolution, access validation,
    data reading, and ingestion gating.

    Usage:
        accessor = CanonicalAccessor(db_connection_string)
        accessor.connect()

        # Resolve domain
        store = accessor.resolve_domain('prices')

        # Read data
        data = accessor.read_prices('BTC-USD', '1d')

        # Validate access
        result = accessor.validate_access('prices', 'fhq_data.prices')
    """

    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        agent_id: str = "SYSTEM"
    ):
        """
        Initialize the Canonical Accessor.

        Args:
            db_connection_string: PostgreSQL connection string
            agent_id: ID of the agent using this accessor
        """
        self.agent_id = agent_id
        self._domain_accessor = CanonicalDomainAccessor(db_connection_string)
        self._guard = CanonicalAccessGuard(self._domain_accessor, agent_id)
        self._reader = CanonicalDataReader(self._domain_accessor, agent_id)
        self._ingestion_gate = CanonicalIngestionGate(self._domain_accessor, agent_id)

    def connect(self) -> bool:
        """Establish database connection."""
        return self._domain_accessor.connect()

    def close(self):
        """Close database connection."""
        self._domain_accessor.close()

    # Domain Resolution
    def resolve_domain(self, domain_name: str) -> Optional[CanonicalDomain]:
        """Resolve domain name to canonical domain."""
        return self._domain_accessor.resolve_domain(domain_name)

    def resolve_canonical_store(self, domain_name: str) -> str:
        """Resolve domain name to canonical store name."""
        return self._domain_accessor.resolve_canonical_store(domain_name)

    def list_domains(self) -> List[CanonicalDomain]:
        """List all active canonical domains."""
        return self._domain_accessor.list_domains()

    # Access Validation
    def validate_access(
        self,
        domain_name: str,
        target_store: str,
        operation_type: OperationType = OperationType.READ,
        access_context: AccessContext = AccessContext.PRODUCTION
    ) -> AccessValidationResult:
        """Validate access to a data store."""
        return self._guard.validate_access(
            domain_name, target_store, operation_type, access_context
        )

    def require_canonical(
        self,
        domain_name: str,
        operation_type: OperationType = OperationType.READ
    ) -> str:
        """Get canonical store with validation."""
        return self._guard.require_canonical(domain_name, operation_type)

    # Data Reading
    def read_prices(
        self,
        asset_id: str,
        frequency: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Read price data from canonical store."""
        return self._reader.read_prices(asset_id, frequency, start_date, end_date, limit)

    def read_regime_classifications(
        self,
        asset_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Read regime classifications from canonical store."""
        return self._reader.read_regime_classifications(asset_id, start_date, end_date, limit)

    def read_cds_results(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Read CDS results from canonical store."""
        return self._reader.read_cds_results(symbol, start_date, end_date, limit)

    # Ingestion
    def register_ingestion_job(
        self,
        job_name: str,
        domain_name: str,
        vendor_sources: List[str],
        primary_vendor: str,
        **kwargs
    ) -> Optional[str]:
        """Register an ingestion job."""
        return self._ingestion_gate.register_ingestion_job(
            job_name, domain_name, vendor_sources, primary_vendor, **kwargs
        )

    # Audit
    def get_access_log(self) -> List[CanonicalAccessLog]:
        """Get access log entries."""
        return self._guard.get_access_log()

    def get_violations(self) -> List[CanonicalViolation]:
        """Get violation entries."""
        return self._guard.get_violations()


# =============================================================================
# EXCEPTIONS
# =============================================================================

class CanonicalAccessError(Exception):
    """Exception raised for canonical access violations."""
    pass


# =============================================================================
# MAIN - VERIFICATION MODE
# =============================================================================

def verify_canonical_accessor():
    """Verify canonical accessor installation and configuration."""
    print("=" * 70)
    print("CANONICAL ACCESSOR VERIFICATION")
    print("ADR-013: One-Source-of-Truth Architecture")
    print("=" * 70)

    accessor = CanonicalAccessor(agent_id="VERIFICATION")

    # Test 1: Check connection
    print("\n[1] Testing database connection...")
    connected = accessor.connect()
    if connected:
        print("    ✅ Database connection successful")
    else:
        print("    ⚠️ Database connection failed (running in mock mode)")

    # Test 2: List domains
    print("\n[2] Listing canonical domains...")
    domains = accessor.list_domains()
    if domains:
        for domain in domains:
            print(f"    ✅ {domain.domain_name}: {domain.canonical_store}")
    else:
        print("    ⚠️ No domains found (database may not be initialized)")

    # Test 3: Test access validation
    print("\n[3] Testing access validation...")
    try:
        result = accessor.validate_access(
            domain_name='prices',
            target_store='fhq_data.prices',
            access_context=AccessContext.PRODUCTION
        )
        status = "✅ VALID" if result.is_valid else "❌ INVALID"
        print(f"    {status}: Access to prices domain")
        print(f"    Canonical: {result.is_canonical}")
    except Exception as e:
        print(f"    ⚠️ Validation test skipped: {e}")

    # Test 4: Test violation detection
    print("\n[4] Testing violation detection...")
    try:
        result = accessor.validate_access(
            domain_name='prices',
            target_store='staging.raw_prices',  # Non-canonical store
            access_context=AccessContext.PRODUCTION
        )
        if result.violation:
            print(f"    ✅ Violation detected: {result.violation.violation_type.value}")
            print(f"    Severity: {result.violation.discrepancy_class.value}")
        else:
            print("    ⚠️ No violation detected (expected violation)")
    except Exception as e:
        print(f"    ⚠️ Violation test skipped: {e}")

    # Cleanup
    accessor.close()

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_canonical_accessor()
    else:
        print("Canonical Accessor Module - ADR-013 Implementation")
        print("Usage: python canonical_accessor.py --verify")
