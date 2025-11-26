"""
VEGA Database Services
ADR-006: Autonomous Constitutional Governance Engine

Authority: ADR-006_2026_PRODUCTION
Database: 127.0.0.1:54322 (Local Supabase PostgreSQL)

8 Core VEGA Services:
1. IntegrityService - Hash verification, canonical validation
2. CertificationService - MDLC 6-gate lifecycle
3. AdversarialDefenseService - Class A/B/C event detection
4. BiasDriftMonitor - Bias/drift logging
5. DORAComplianceService - Article 17/24 compliance
6. StrategyReviewService - KPI review, calibration
7. SovereigntyScoringEngine - ADR-005 scoring
8. GovernanceEnforcer - Zero-override policy enforcement

Usage:
    from vega_database_services import VEGADatabaseServices

    vega = VEGADatabaseServices()
    vega.connect()

    # Use services
    result = vega.integrity.verify_hash_chain('VEGA_GOVERNANCE_CHAIN')
    cert = vega.certification.issue_certificate(...)
    score = vega.sovereignty.calculate_score(...)
"""

import os
import sys
import json
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - VEGA DB - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vega_database")


# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

@dataclass
class VEGADatabaseConfig:
    """
    VEGA Database Configuration

    CANONICAL DATABASE: 127.0.0.1:54322
    """
    host: str = "127.0.0.1"
    port: int = 54322
    database: str = "postgres"
    user: str = "postgres"
    password: str = "postgres"

    # Schemas
    meta_schema: str = "fhq_meta"
    governance_schema: str = "fhq_governance"
    vega_schema: str = "vega"
    phase3_schema: str = "fhq_phase3"

    @classmethod
    def from_env(cls) -> "VEGADatabaseConfig":
        """Load from environment variables."""
        return cls(
            host=os.getenv("PGHOST", "127.0.0.1"),
            port=int(os.getenv("PGPORT", "54322")),
            database=os.getenv("PGDATABASE", "postgres"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", "postgres"),
        )

    def get_dsn(self) -> dict:
        """Get connection parameters."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
        }


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class DiscrepancyClass(Enum):
    """ADR-010 Discrepancy Classification"""
    CLASS_A = "CLASS_A"  # Critical - Immediate CRP
    CLASS_B = "CLASS_B"  # Major - 24h correction
    CLASS_C = "CLASS_C"  # Minor - Next sprint
    NONE = "NONE"


class CertificationStatus(Enum):
    """MDLC Certification Status"""
    PENDING = "PENDING"
    GATE_1_APPROVED = "GATE_1_APPROVED"
    GATE_2_APPROVED = "GATE_2_APPROVED"
    GATE_3_APPROVED = "GATE_3_APPROVED"
    GATE_4_APPROVED = "GATE_4_APPROVED"
    GATE_5_APPROVED = "GATE_5_APPROVED"
    FULLY_CERTIFIED = "FULLY_CERTIFIED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class ScoringPeriod(Enum):
    """Sovereignty Scoring Period"""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


@dataclass
class HashVerificationResult:
    """Result of hash chain verification."""
    chain_id: str
    total_entries: int
    valid_entries: int
    broken_links: int
    integrity_status: str
    first_break_position: Optional[int]


@dataclass
class CertificationResult:
    """Result of model certification."""
    certification_id: int
    model_id: str
    gate_number: int
    new_status: str
    issued_at: datetime


@dataclass
class SovereigntyScore:
    """Sovereignty score calculation result."""
    sovereignty_id: int
    overall_score: Decimal
    constitutional_score: Decimal
    operational_score: Decimal
    data_score: Decimal
    regulatory_score: Decimal
    economic_score: Decimal
    trend: str
    calculated_at: datetime


# =============================================================================
# SERVICE 1: INTEGRITY SERVICE
# =============================================================================

class IntegrityService:
    """
    Hash verification and canonical validation.

    ADR-006 Section 3.1: VEGA_SQL Database Governance Layer
    """

    def __init__(self, conn):
        self.conn = conn

    def verify_hash_chain(self, chain_id: Optional[str] = None, limit: int = 1000) -> List[HashVerificationResult]:
        """
        Verify hash chain integrity.

        Calls: fhq_meta.vega_verify_hashes()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM fhq_meta.vega_verify_hashes(%s, %s)",
                (chain_id, limit)
            )
            results = cur.fetchall()

        return [
            HashVerificationResult(
                chain_id=r['chain_id'],
                total_entries=r['total_entries'],
                valid_entries=r['valid_entries'],
                broken_links=r['broken_links'],
                integrity_status=r['integrity_status'],
                first_break_position=r['first_break_position']
            )
            for r in results
        ]

    def compare_registry(self, registry_type: str) -> Dict[str, Any]:
        """
        Compare current state against canonical registry.

        Calls: fhq_meta.vega_compare_registry()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM fhq_meta.vega_compare_registry(%s)",
                (registry_type,)
            )
            result = cur.fetchone()

        return dict(result) if result else {}

    def snapshot_canonical(self, snapshot_type: str, authority: str) -> Dict[str, Any]:
        """
        Create canonical snapshot of governance state.

        Calls: fhq_meta.vega_snapshot_canonical()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM fhq_meta.vega_snapshot_canonical(%s, %s)",
                (snapshot_type, authority)
            )
            result = cur.fetchone()

        return dict(result) if result else {}

    def calculate_hash(self, data: str) -> str:
        """Calculate SHA-256 hash of data."""
        return hashlib.sha256(data.encode()).hexdigest()


# =============================================================================
# SERVICE 2: CERTIFICATION SERVICE
# =============================================================================

class CertificationService:
    """
    MDLC 6-Gate Model Certification.

    ADR-006 Section 2.2: Model Governance
    """

    def __init__(self, conn):
        self.conn = conn

    def issue_certificate(
        self,
        model_id: str,
        model_name: str,
        model_version: str,
        model_type: str,
        gate_number: int,
        certification_data: Dict[str, Any],
        vega_signature: str,
        vega_public_key: str
    ) -> CertificationResult:
        """
        Issue MDLC certification for a model.

        Calls: fhq_meta.vega_issue_certificate()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fhq_meta.vega_issue_certificate(
                    %s, %s, %s, %s, %s, %s, %s, %s
                )""",
                (model_id, model_name, model_version, model_type,
                 gate_number, json.dumps(certification_data),
                 vega_signature, vega_public_key)
            )
            result = cur.fetchone()
            self.conn.commit()

        return CertificationResult(
            certification_id=result['certification_id'],
            model_id=result['model_id'],
            gate_number=result['gate_number'],
            new_status=result['new_status'],
            issued_at=result['issued_at']
        )

    def get_certification_status(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get current certification status for a model."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fhq_meta.model_certifications
                   WHERE model_id = %s
                   ORDER BY certified_at DESC LIMIT 1""",
                (model_id,)
            )
            result = cur.fetchone()

        return dict(result) if result else None

    def suspend_certification(self, model_id: str, reason: str) -> bool:
        """Suspend a model's certification."""
        with self.conn.cursor() as cur:
            cur.execute(
                """UPDATE fhq_meta.model_certifications
                   SET certification_status = 'SUSPENDED',
                       retirement_reason = %s,
                       last_review_at = NOW()
                   WHERE model_id = %s AND certification_status = 'FULLY_CERTIFIED'""",
                (reason, model_id)
            )
            self.conn.commit()
            return cur.rowcount > 0


# =============================================================================
# SERVICE 3: ADVERSARIAL DEFENSE SERVICE
# =============================================================================

class AdversarialDefenseService:
    """
    Class A/B/C Event Detection and Response.

    ADR-006 Section 3.3: VEGA_EVENT_ENGINE
    """

    def __init__(self, conn):
        self.conn = conn

    def record_event(
        self,
        event_type: str,
        severity: str,
        discrepancy_class: DiscrepancyClass,
        target: str,
        event_data: Dict[str, Any],
        vega_signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record an adversarial/security event.

        Calls: fhq_meta.vega_record_adversarial_event()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fhq_meta.vega_record_adversarial_event(
                    %s, %s, %s, %s, %s, %s
                )""",
                (event_type, severity, discrepancy_class.value,
                 target, json.dumps(event_data), vega_signature)
            )
            result = cur.fetchone()
            self.conn.commit()

        return {
            'event_id': result['event_id'],
            'event_type': result['event_type'],
            'discrepancy_class': result['discrepancy_class'],
            'crp_triggered': result['crp_triggered'],
            'escalation_required': result['escalation_required'],
            'recorded_at': result['recorded_at']
        }

    def check_class_b_threshold(self) -> Dict[str, Any]:
        """
        Check if Class B threshold is exceeded (5 events in 7 days).

        Calls: fhq_meta.vega_enforce_class_b_threshold()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM fhq_meta.vega_enforce_class_b_threshold()")
            result = cur.fetchone()
            self.conn.commit()

        return dict(result) if result else {}

    def get_recent_events(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent adversarial events."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fhq_meta.adr_audit_log
                   WHERE event_category = 'adversarial'
                   AND audit_timestamp > NOW() - INTERVAL '%s days'
                   ORDER BY audit_timestamp DESC""",
                (days,)
            )
            results = cur.fetchall()

        return [dict(r) for r in results]


# =============================================================================
# SERVICE 4: BIAS/DRIFT MONITOR
# =============================================================================

class BiasDriftMonitor:
    """
    Model Bias and Drift Detection.

    ADR-006 Section 2.2: Model Governance
    """

    def __init__(self, conn):
        self.conn = conn

    def log_bias_drift(
        self,
        model_id: str,
        drift_type: str,
        drift_score: Decimal,
        bias_metrics: Dict[str, Any],
        threshold_exceeded: bool
    ) -> Dict[str, Any]:
        """
        Log model bias and drift event.

        Calls: fhq_meta.vega_log_bias_drift()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fhq_meta.vega_log_bias_drift(
                    %s, %s, %s, %s, %s
                )""",
                (model_id, drift_type, drift_score,
                 json.dumps(bias_metrics), threshold_exceeded)
            )
            result = cur.fetchone()
            self.conn.commit()

        return {
            'log_id': result['log_id'],
            'model_id': result['model_id'],
            'drift_type': result['drift_type'],
            'drift_score': float(result['drift_score']),
            'action_required': result['action_required'],
            'certification_impact': result['certification_impact'],
            'logged_at': result['logged_at']
        }

    def get_drift_history(self, model_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get drift history for a model."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fhq_meta.adr_audit_log
                   WHERE event_type = 'bias_drift_detection'
                   AND target = %s
                   AND audit_timestamp > NOW() - INTERVAL '%s days'
                   ORDER BY audit_timestamp DESC""",
                (model_id, days)
            )
            results = cur.fetchall()

        return [dict(r) for r in results]


# =============================================================================
# SERVICE 5: DORA COMPLIANCE SERVICE
# =============================================================================

class DORAComplianceService:
    """
    DORA Article 17/24 Compliance.

    ADR-006 Section 2.4: Regulatory Compliance
    """

    def __init__(self, conn):
        self.conn = conn

    def trigger_assessment(
        self,
        incident_type: str,
        severity: str,
        affected_systems: List[str],
        incident_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger DORA Article 17 assessment.

        Calls: fhq_meta.vega_trigger_dora_assessment()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fhq_meta.vega_trigger_dora_assessment(
                    %s, %s, %s, %s
                )""",
                (incident_type, severity, affected_systems,
                 json.dumps(incident_data))
            )
            result = cur.fetchone()
            self.conn.commit()

        return {
            'assessment_id': result['assessment_id'],
            'dora_article': result['dora_article'],
            'classification': result['classification'],
            'reporting_required': result['reporting_required'],
            'reporting_deadline': str(result['reporting_deadline']),
            'assessment_timestamp': result['assessment_timestamp']
        }

    def get_compliance_status(self) -> Dict[str, Any]:
        """Get current DORA compliance status."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Count recent DORA assessments
            cur.execute(
                """SELECT
                    COUNT(*) as total_assessments,
                    COUNT(*) FILTER (WHERE event_data->>'reporting_required' = 'true') as requiring_report
                   FROM fhq_meta.adr_audit_log
                   WHERE event_type = 'dora_assessment'
                   AND audit_timestamp > NOW() - INTERVAL '30 days'"""
            )
            result = cur.fetchone()

        return {
            'total_assessments_30d': result['total_assessments'],
            'requiring_report': result['requiring_report'],
            'compliance_status': 'COMPLIANT' if result['requiring_report'] == 0 else 'REVIEW_REQUIRED'
        }


# =============================================================================
# SERVICE 6: STRATEGY REVIEW SERVICE
# =============================================================================

class StrategyReviewService:
    """
    KPI Review and Strategy Calibration.

    ADR-006 Section 2.3: Operational Governance
    """

    def __init__(self, conn):
        self.conn = conn

    def record_kpi_review(
        self,
        review_type: str,
        metrics: Dict[str, Any],
        period_start: date,
        period_end: date,
        reviewer: str = "VEGA"
    ) -> int:
        """Record a KPI review event."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO fhq_meta.adr_audit_log (
                    event_type, event_category, severity, actor, action,
                    event_data, event_hash
                ) VALUES (
                    'kpi_review', 'operational', 'INFO', %s, 'RECORD_KPI_REVIEW',
                    %s, encode(sha256(%s::bytea), 'hex')
                ) RETURNING audit_id""",
                (reviewer, json.dumps({
                    'review_type': review_type,
                    'metrics': metrics,
                    'period_start': period_start.isoformat(),
                    'period_end': period_end.isoformat()
                }), f"KPI_REVIEW_{datetime.now().isoformat()}")
            )
            audit_id = cur.fetchone()[0]
            self.conn.commit()

        return audit_id

    def get_governance_health(self, days: int = 7) -> Dict[str, Any]:
        """Get governance health metrics."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM fhq_meta.v_governance_health LIMIT %s", (days,))
            results = cur.fetchall()

        return {
            'daily_metrics': [dict(r) for r in results],
            'period_days': days
        }


# =============================================================================
# SERVICE 7: SOVEREIGNTY SCORING ENGINE
# =============================================================================

class SovereigntyScoringEngine:
    """
    ADR-005 Commercial Sovereignty Scoring.

    ADR-006 Section 5: Governance Rhythms
    """

    def __init__(self, conn):
        self.conn = conn

    def calculate_score(
        self,
        scoring_period: ScoringPeriod,
        period_start: date,
        period_end: date,
        vega_signature: str,
        vega_public_key: str
    ) -> SovereigntyScore:
        """
        Calculate sovereignty score.

        Calls: fhq_meta.vega_calculate_sovereignty_score()
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fhq_meta.vega_calculate_sovereignty_score(
                    %s, %s, %s, %s, %s
                )""",
                (scoring_period.value, period_start, period_end,
                 vega_signature, vega_public_key)
            )
            result = cur.fetchone()
            self.conn.commit()

        return SovereigntyScore(
            sovereignty_id=result['sovereignty_id'],
            overall_score=result['overall_score'],
            constitutional_score=result['constitutional_score'],
            operational_score=result['operational_score'],
            data_score=result['data_score'],
            regulatory_score=result['regulatory_score'],
            economic_score=result['economic_score'],
            trend=result['trend'],
            calculated_at=result['calculated_at']
        )

    def get_trend(self, periods: int = 10) -> List[Dict[str, Any]]:
        """Get sovereignty score trend."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM fhq_meta.v_sovereignty_trend LIMIT %s",
                (periods,)
            )
            results = cur.fetchall()

        return [dict(r) for r in results]


# =============================================================================
# SERVICE 8: GOVERNANCE ENFORCER
# =============================================================================

class GovernanceEnforcer:
    """
    Zero-Override Policy Enforcement.

    ADR-006 Section 4: Constitutional Responsibilities
    """

    def __init__(self, conn):
        self.conn = conn

    def check_authority(self, agent_id: str, action: str, resource: str) -> Dict[str, Any]:
        """Check if an agent has authority to perform an action."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT permission, conditions
                   FROM fhq_governance.authority_matrix
                   WHERE agent_id = %s
                   AND action_type = %s
                   AND (resource_scope = '*' OR resource_scope LIKE %s)""",
                (agent_id, action, f"%{resource}%")
            )
            result = cur.fetchone()

        if not result:
            return {
                'allowed': False,
                'reason': 'No authority entry found'
            }

        return {
            'allowed': result['permission'] == 'ALLOW',
            'permission': result['permission'],
            'conditions': result['conditions']
        }

    def log_governance_event(
        self,
        event_type: str,
        actor: str,
        action: str,
        target: str,
        event_data: Dict[str, Any],
        severity: str = "INFO"
    ) -> int:
        """Log a governance event."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO fhq_meta.adr_audit_log (
                    event_type, event_category, severity, actor, action, target,
                    event_data, event_hash, hash_chain_id
                ) VALUES (
                    %s, 'governance', %s, %s, %s, %s,
                    %s, encode(sha256(%s::bytea), 'hex'), 'VEGA_GOVERNANCE_CHAIN'
                ) RETURNING audit_id""",
                (event_type, severity, actor, action, target,
                 json.dumps(event_data), f"{event_type}_{datetime.now().isoformat()}")
            )
            audit_id = cur.fetchone()[0]
            self.conn.commit()

        return audit_id

    def get_audit_trail(
        self,
        actor: Optional[str] = None,
        event_type: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get governance audit trail."""
        query = """SELECT * FROM fhq_meta.adr_audit_log
                   WHERE audit_timestamp > NOW() - INTERVAL '%s days'"""
        params = [days]

        if actor:
            query += " AND actor = %s"
            params.append(actor)

        if event_type:
            query += " AND event_type = %s"
            params.append(event_type)

        query += " ORDER BY audit_timestamp DESC LIMIT 100"

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            results = cur.fetchall()

        return [dict(r) for r in results]


# =============================================================================
# MAIN VEGA DATABASE SERVICES CLASS
# =============================================================================

class VEGADatabaseServices:
    """
    VEGA Database Services - Main Interface

    Provides access to all 8 VEGA core services:
    - integrity: Hash verification, canonical validation
    - certification: MDLC 6-gate lifecycle
    - adversarial: Class A/B/C event detection
    - bias_drift: Bias/drift monitoring
    - dora: DORA compliance
    - strategy: KPI review
    - sovereignty: Sovereignty scoring
    - enforcer: Governance enforcement
    """

    def __init__(self, config: Optional[VEGADatabaseConfig] = None):
        """
        Initialize VEGA Database Services.

        Args:
            config: Database configuration (defaults to 127.0.0.1:54322)
        """
        self.config = config or VEGADatabaseConfig.from_env()
        self.conn = None
        self.connected = False

        # Services (initialized on connect)
        self.integrity: Optional[IntegrityService] = None
        self.certification: Optional[CertificationService] = None
        self.adversarial: Optional[AdversarialDefenseService] = None
        self.bias_drift: Optional[BiasDriftMonitor] = None
        self.dora: Optional[DORAComplianceService] = None
        self.strategy: Optional[StrategyReviewService] = None
        self.sovereignty: Optional[SovereigntyScoringEngine] = None
        self.enforcer: Optional[GovernanceEnforcer] = None

    def connect(self) -> bool:
        """
        Connect to database and initialize services.

        Returns:
            True if connection successful
        """
        try:
            self.conn = psycopg2.connect(**self.config.get_dsn())
            self.connected = True

            # Initialize all services
            self.integrity = IntegrityService(self.conn)
            self.certification = CertificationService(self.conn)
            self.adversarial = AdversarialDefenseService(self.conn)
            self.bias_drift = BiasDriftMonitor(self.conn)
            self.dora = DORAComplianceService(self.conn)
            self.strategy = StrategyReviewService(self.conn)
            self.sovereignty = SovereigntyScoringEngine(self.conn)
            self.enforcer = GovernanceEnforcer(self.conn)

            logger.info(f"Connected to {self.config.host}:{self.config.port}")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.connected = False
            logger.info("Disconnected from database")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        if not self.connected:
            return {'status': 'DISCONNECTED', 'error': 'Not connected'}

        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.execute("SELECT NOW()")
                db_time = cur.fetchone()[0]

            return {
                'status': 'HEALTHY',
                'database': f"{self.config.host}:{self.config.port}",
                'db_time': db_time.isoformat(),
                'services_active': 8
            }

        except Exception as e:
            return {'status': 'UNHEALTHY', 'error': str(e)}


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("VEGA DATABASE SERVICES")
    print("ADR-006: Autonomous Constitutional Governance Engine")
    print("=" * 60)
    print(f"Database: 127.0.0.1:54322")
    print("=" * 60)

    # Test connection
    with VEGADatabaseServices() as vega:
        health = vega.health_check()
        print(f"Health Check: {health['status']}")

        if health['status'] == 'HEALTHY':
            print(f"Database Time: {health['db_time']}")
            print(f"Services Active: {health['services_active']}")

            # Test integrity service
            print("\n--- Testing Integrity Service ---")
            try:
                chains = vega.integrity.verify_hash_chain(limit=10)
                print(f"Hash chains verified: {len(chains)}")
            except Exception as e:
                print(f"Note: {e}")

            # Test governance health
            print("\n--- Testing Strategy Service ---")
            try:
                health_metrics = vega.strategy.get_governance_health(days=1)
                print(f"Governance metrics: {len(health_metrics.get('daily_metrics', []))} days")
            except Exception as e:
                print(f"Note: {e}")

    print("\n" + "=" * 60)
    print("VEGA Database Services: Ready")
    print("=" * 60)
