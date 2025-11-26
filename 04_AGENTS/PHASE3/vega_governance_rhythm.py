#!/usr/bin/env python3
"""
VEGA GOVERNANCE RHYTHM - ADR-009 Integration
Agent: VEGA (Constitutional Governance Engine)
Purpose: Integrate suspension monitoring into VEGA's governance rhythm
Compliance: ADR-009, ADR-010, ADR-007, ADR-006

This module extends VEGA's governance rhythm to include:
  1. Monitoring for pending suspension requests
  2. Verifying no agent is suspended without approved request
  3. Triggering suspension recommendations when discrepancy > 0.10
  4. Generating governance integrity reports

ADR-009 Section 6 (VEGA Test - Governance Rhythm):
  - List all PENDING suspension requests daily/weekly
  - Verify no agent suspended without approved request
  - Integrate with existing VEGA integrity checks

Usage:
    python vega_governance_rhythm.py                    # Run full governance check
    python vega_governance_rhythm.py --check-pending    # List pending requests only
    python vega_governance_rhythm.py --verify-integrity # Verify suspension integrity
    python vega_governance_rhythm.py --monitor          # Run continuous monitoring
"""

import os
import sys
import json
import hashlib
import argparse
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Database
import psycopg2
from psycopg2.extras import RealDictCursor, Json

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """VEGA Governance Rhythm Configuration"""

    # Agent identity
    VEGA_AGENT_ID = "VEGA"
    ADR_REFERENCE = "ADR-009"

    # Discrepancy threshold per ADR-010
    DISCREPANCY_THRESHOLD = 0.10

    # Governance rhythm intervals
    DAILY_CHECK_HOUR = 6  # 6 AM UTC
    WEEKLY_CHECK_DAY = 0  # Monday
    MONITOR_INTERVAL_SECONDS = 300  # 5 minutes for continuous monitoring

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
    logger = logging.getLogger("vega_governance_rhythm")
    logger.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - VEGA-RHYTHM - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(console)

    return logger


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class IntegrityStatus(Enum):
    """Integrity check status"""
    COMPLIANT = "COMPLIANT"
    VIOLATION = "VIOLATION"
    WARNING = "WARNING"


@dataclass
class PendingSuspensionReport:
    """Report on pending suspension requests"""
    total_pending: int
    requests: List[Dict[str, Any]]
    oldest_pending_age_hours: Optional[float]
    agents_at_risk: List[str]
    generated_at: str


@dataclass
class IntegrityViolation:
    """Record of an integrity violation"""
    agent_id: str
    violation_type: str
    description: str
    severity: str
    detected_at: str


@dataclass
class GovernanceRhythmReport:
    """Complete governance rhythm report"""
    report_id: str
    report_type: str  # DAILY, WEEKLY, AD_HOC
    generated_at: str
    integrity_status: IntegrityStatus
    pending_requests: PendingSuspensionReport
    violations: List[IntegrityViolation]
    recommendations: List[str]
    report_hash: str


# =============================================================================
# DATABASE INTERFACE
# =============================================================================

class GovernanceRhythmDB:
    """Database interface for governance rhythm"""

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
        return self.execute_scalar("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
        """, (schema, table))


# =============================================================================
# VEGA GOVERNANCE RHYTHM ENGINE
# =============================================================================

class VEGAGovernanceRhythm:
    """
    VEGA Governance Rhythm Engine

    Implements the governance rhythm checks required by ADR-009 Section 6:
      - Daily: List pending suspension requests
      - Weekly: Full integrity verification
      - Continuous: Monitor for discrepancy threshold violations
    """

    def __init__(self, db: GovernanceRhythmDB, logger: logging.Logger):
        self.db = db
        self.logger = logger
        self.agent_id = Config.VEGA_AGENT_ID

    def _generate_hash(self, data: Any) -> str:
        """Generate SHA-256 hash"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _generate_report_id(self, report_type: str) -> str:
        """Generate report ID"""
        return f"VEGA-{report_type}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # =========================================================================
    # PENDING REQUESTS MONITORING
    # =========================================================================

    def get_pending_suspension_requests(self) -> PendingSuspensionReport:
        """
        Get all pending suspension requests (ADR-009 Section 6).

        This should be run daily to ensure CEO has visibility
        into all requests awaiting review.
        """
        self.logger.info("Checking pending suspension requests...")

        if not self.db.table_exists("fhq_governance", "agent_suspension_requests"):
            self.logger.warning("agent_suspension_requests table not found")
            return PendingSuspensionReport(
                total_pending=0,
                requests=[],
                oldest_pending_age_hours=None,
                agents_at_risk=[],
                generated_at=datetime.now(timezone.utc).isoformat()
            )

        # Get pending requests
        requests = self.db.execute_query("""
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
                EXTRACT(EPOCH FROM (NOW() - r.created_at)) / 3600 AS age_hours
            FROM fhq_governance.agent_suspension_requests r
            JOIN fhq_org.org_agents a ON r.agent_id = a.agent_id
            WHERE r.status = 'PENDING'
            ORDER BY r.created_at ASC
        """)

        agents_at_risk = list(set(r['agent_id'] for r in requests))
        oldest_age = max((r['age_hours'] for r in requests), default=None)

        report = PendingSuspensionReport(
            total_pending=len(requests),
            requests=requests,
            oldest_pending_age_hours=float(oldest_age) if oldest_age else None,
            agents_at_risk=agents_at_risk,
            generated_at=datetime.now(timezone.utc).isoformat()
        )

        if report.total_pending > 0:
            self.logger.warning(f"Found {report.total_pending} pending suspension requests")
            for req in requests:
                self.logger.info(f"  - Agent {req['agent_id']}: score={req['discrepancy_score']}, age={req['age_hours']:.1f}h")
        else:
            self.logger.info("No pending suspension requests")

        return report

    # =========================================================================
    # INTEGRITY VERIFICATION
    # =========================================================================

    def verify_suspension_integrity(self) -> List[IntegrityViolation]:
        """
        Verify no agent is suspended without an approved request (ADR-009 Section 6).

        This is a critical governance check to ensure:
          1. All suspended agents have corresponding APPROVED requests
          2. No agent was suspended by bypassing the governance workflow
          3. Request and agent state are consistent
        """
        self.logger.info("Verifying suspension integrity...")
        violations = []

        if not self.db.table_exists("fhq_governance", "agent_suspension_requests"):
            self.logger.warning("Cannot verify - table not found")
            return violations

        # Check 1: Suspended agents without approved request
        suspended_without_request = self.db.execute_query("""
            SELECT
                a.agent_id,
                a.agent_name,
                a.is_suspended,
                a.suspension_reason,
                a.suspended_at
            FROM fhq_org.org_agents a
            WHERE a.is_suspended = TRUE
            AND NOT EXISTS (
                SELECT 1 FROM fhq_governance.agent_suspension_requests r
                WHERE r.agent_id = a.agent_id
                AND r.status = 'APPROVED'
            )
        """)

        for agent in suspended_without_request:
            violation = IntegrityViolation(
                agent_id=agent['agent_id'],
                violation_type="SUSPENDED_WITHOUT_APPROVED_REQUEST",
                description=f"Agent {agent['agent_id']} is suspended but has no approved suspension request",
                severity="CRITICAL",
                detected_at=datetime.now(timezone.utc).isoformat()
            )
            violations.append(violation)
            self.logger.error(f"VIOLATION: {violation.description}")

        # Check 2: Approved requests where agent is not suspended
        approved_but_not_suspended = self.db.execute_query("""
            SELECT
                r.request_id,
                r.agent_id,
                a.agent_name,
                a.is_suspended,
                r.reviewed_at
            FROM fhq_governance.agent_suspension_requests r
            JOIN fhq_org.org_agents a ON r.agent_id = a.agent_id
            WHERE r.status = 'APPROVED'
            AND a.is_suspended = FALSE
            AND r.reviewed_at > NOW() - INTERVAL '24 hours'
        """)

        for req in approved_but_not_suspended:
            violation = IntegrityViolation(
                agent_id=req['agent_id'],
                violation_type="APPROVED_BUT_NOT_SUSPENDED",
                description=f"Agent {req['agent_id']} has approved suspension but is_suspended=FALSE",
                severity="HIGH",
                detected_at=datetime.now(timezone.utc).isoformat()
            )
            violations.append(violation)
            self.logger.error(f"VIOLATION: {violation.description}")

        # Check 3: Multiple pending requests for same agent
        multiple_pending = self.db.execute_query("""
            SELECT
                agent_id,
                COUNT(*) as pending_count
            FROM fhq_governance.agent_suspension_requests
            WHERE status = 'PENDING'
            GROUP BY agent_id
            HAVING COUNT(*) > 1
        """)

        for item in multiple_pending:
            violation = IntegrityViolation(
                agent_id=item['agent_id'],
                violation_type="MULTIPLE_PENDING_REQUESTS",
                description=f"Agent {item['agent_id']} has {item['pending_count']} pending requests",
                severity="WARNING",
                detected_at=datetime.now(timezone.utc).isoformat()
            )
            violations.append(violation)
            self.logger.warning(f"WARNING: {violation.description}")

        if not violations:
            self.logger.info("Suspension integrity verified - no violations found")

        return violations

    # =========================================================================
    # DISCREPANCY MONITORING
    # =========================================================================

    def check_discrepancy_thresholds(self) -> List[Dict[str, Any]]:
        """
        Check for agents with discrepancy scores exceeding threshold.

        When an agent's discrepancy score exceeds 0.10 (per ADR-010),
        VEGA should consider recommending suspension.

        Returns list of agents that may need suspension recommendation.
        """
        self.logger.info("Checking discrepancy thresholds...")

        if not self.db.table_exists("fhq_meta", "reconciliation_snapshots"):
            self.logger.warning("reconciliation_snapshots table not found")
            return []

        # Get recent reconciliation snapshots with high discrepancy
        high_discrepancy = self.db.execute_query("""
            SELECT
                rs.component_name as agent_id,
                rs.discrepancy_score,
                rs.discrepancy_threshold,
                rs.threshold_exceeded,
                rs.snapshot_timestamp,
                a.agent_name,
                a.is_suspended
            FROM fhq_meta.reconciliation_snapshots rs
            JOIN fhq_org.org_agents a ON rs.component_name = a.agent_id
            WHERE rs.discrepancy_score > %s
            AND rs.snapshot_timestamp > NOW() - INTERVAL '24 hours'
            AND a.is_suspended = FALSE
            AND NOT EXISTS (
                SELECT 1 FROM fhq_governance.agent_suspension_requests r
                WHERE r.agent_id = rs.component_name
                AND r.status = 'PENDING'
            )
            ORDER BY rs.discrepancy_score DESC
        """, (Config.DISCREPANCY_THRESHOLD,))

        if high_discrepancy:
            self.logger.warning(f"Found {len(high_discrepancy)} agents with high discrepancy scores")
            for agent in high_discrepancy:
                self.logger.warning(
                    f"  - {agent['agent_id']}: score={agent['discrepancy_score']:.5f} "
                    f"(threshold={Config.DISCREPANCY_THRESHOLD})"
                )
        else:
            self.logger.info("No agents exceed discrepancy threshold")

        return high_discrepancy

    # =========================================================================
    # GOVERNANCE REPORTS
    # =========================================================================

    def generate_daily_report(self) -> GovernanceRhythmReport:
        """
        Generate daily governance rhythm report.

        This should be run every day at 6 AM UTC to provide
        CEO with overnight governance status.
        """
        self.logger.info("=" * 70)
        self.logger.info("VEGA DAILY GOVERNANCE RHYTHM REPORT")
        self.logger.info(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        self.logger.info("=" * 70)

        report_id = self._generate_report_id("DAILY")

        # Get pending requests
        pending_report = self.get_pending_suspension_requests()

        # Verify integrity
        violations = self.verify_suspension_integrity()

        # Check discrepancies
        high_discrepancy = self.check_discrepancy_thresholds()

        # Generate recommendations
        recommendations = []
        if pending_report.total_pending > 0:
            recommendations.append(
                f"Review {pending_report.total_pending} pending suspension request(s)"
            )
        if pending_report.oldest_pending_age_hours and pending_report.oldest_pending_age_hours > 24:
            recommendations.append(
                f"URGENT: Oldest pending request is {pending_report.oldest_pending_age_hours:.1f} hours old"
            )
        if violations:
            recommendations.append(
                f"CRITICAL: {len(violations)} integrity violation(s) require immediate attention"
            )
        if high_discrepancy:
            recommendations.append(
                f"Consider suspension recommendations for {len(high_discrepancy)} agent(s) with high discrepancy"
            )

        # Determine overall status
        if any(v.severity == "CRITICAL" for v in violations):
            integrity_status = IntegrityStatus.VIOLATION
        elif violations:
            integrity_status = IntegrityStatus.WARNING
        else:
            integrity_status = IntegrityStatus.COMPLIANT

        # Build report
        report_data = {
            "report_id": report_id,
            "report_type": "DAILY",
            "integrity_status": integrity_status.value,
            "pending_count": pending_report.total_pending,
            "violation_count": len(violations),
            "high_discrepancy_count": len(high_discrepancy)
        }
        report_hash = self._generate_hash(report_data)

        report = GovernanceRhythmReport(
            report_id=report_id,
            report_type="DAILY",
            generated_at=datetime.now(timezone.utc).isoformat(),
            integrity_status=integrity_status,
            pending_requests=pending_report,
            violations=violations,
            recommendations=recommendations,
            report_hash=report_hash
        )

        # Print summary
        self._print_report_summary(report)

        return report

    def generate_weekly_report(self) -> GovernanceRhythmReport:
        """
        Generate weekly governance rhythm report.

        This provides a more comprehensive view including:
          - All suspension activity in the past week
          - Trend analysis
          - Compliance metrics
        """
        self.logger.info("=" * 70)
        self.logger.info("VEGA WEEKLY GOVERNANCE RHYTHM REPORT")
        self.logger.info(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        self.logger.info("=" * 70)

        # Start with daily checks
        report = self.generate_daily_report()
        report.report_type = "WEEKLY"
        report.report_id = self._generate_report_id("WEEKLY")

        # Add weekly statistics
        if self.db.table_exists("fhq_governance", "agent_suspension_requests"):
            weekly_stats = self.db.execute_query("""
                SELECT
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as requests_this_week,
                    COUNT(*) FILTER (WHERE status = 'APPROVED' AND reviewed_at > NOW() - INTERVAL '7 days') as approved_this_week,
                    COUNT(*) FILTER (WHERE status = 'REJECTED' AND reviewed_at > NOW() - INTERVAL '7 days') as rejected_this_week,
                    AVG(EXTRACT(EPOCH FROM (reviewed_at - created_at)) / 3600)
                        FILTER (WHERE status IN ('APPROVED', 'REJECTED') AND reviewed_at > NOW() - INTERVAL '7 days')
                        as avg_review_time_hours
                FROM fhq_governance.agent_suspension_requests
            """)

            if weekly_stats:
                stats = weekly_stats[0]
                self.logger.info("\nWeekly Statistics:")
                self.logger.info(f"  Requests this week: {stats['requests_this_week']}")
                self.logger.info(f"  Approved: {stats['approved_this_week']}")
                self.logger.info(f"  Rejected: {stats['rejected_this_week']}")
                if stats['avg_review_time_hours']:
                    self.logger.info(f"  Avg review time: {stats['avg_review_time_hours']:.1f} hours")

        return report

    def _print_report_summary(self, report: GovernanceRhythmReport):
        """Print report summary to log"""
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info(f"GOVERNANCE RHYTHM SUMMARY - {report.report_type}")
        self.logger.info("=" * 70)
        self.logger.info(f"Report ID: {report.report_id}")
        self.logger.info(f"Status: {report.integrity_status.value}")
        self.logger.info(f"Pending Requests: {report.pending_requests.total_pending}")
        self.logger.info(f"Integrity Violations: {len(report.violations)}")

        if report.recommendations:
            self.logger.info("\nRecommendations:")
            for i, rec in enumerate(report.recommendations, 1):
                self.logger.info(f"  {i}. {rec}")

        self.logger.info(f"\nReport Hash: {report.report_hash}")
        self.logger.info("=" * 70)

    # =========================================================================
    # CONTINUOUS MONITORING
    # =========================================================================

    def run_continuous_monitoring(self):
        """
        Run continuous governance monitoring.

        Checks every 5 minutes for:
          - New pending requests
          - Integrity violations
          - High discrepancy agents
        """
        self.logger.info("Starting continuous governance monitoring...")
        self.logger.info(f"Check interval: {Config.MONITOR_INTERVAL_SECONDS} seconds")

        cycle = 0
        try:
            while True:
                cycle += 1
                self.logger.info(f"\n--- Monitoring Cycle {cycle} ---")

                # Quick integrity check
                violations = self.verify_suspension_integrity()
                if violations:
                    self.logger.error(f"ALERT: {len(violations)} integrity violation(s) detected!")

                # Check pending requests
                pending = self.get_pending_suspension_requests()
                if pending.oldest_pending_age_hours and pending.oldest_pending_age_hours > 24:
                    self.logger.warning(f"ALERT: Pending request older than 24 hours!")

                # Check discrepancies
                high_disc = self.check_discrepancy_thresholds()
                if high_disc:
                    self.logger.warning(f"ALERT: {len(high_disc)} agent(s) with high discrepancy")

                self.logger.info(f"Next check in {Config.MONITOR_INTERVAL_SECONDS} seconds...")
                time.sleep(Config.MONITOR_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            self.logger.info("\nMonitoring stopped by user")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='VEGA Governance Rhythm - ADR-009 Integration'
    )

    parser.add_argument(
        '--check-pending',
        action='store_true',
        help='List pending suspension requests only'
    )
    parser.add_argument(
        '--verify-integrity',
        action='store_true',
        help='Verify suspension integrity only'
    )
    parser.add_argument(
        '--check-discrepancy',
        action='store_true',
        help='Check discrepancy thresholds only'
    )
    parser.add_argument(
        '--daily',
        action='store_true',
        help='Generate daily governance report'
    )
    parser.add_argument(
        '--weekly',
        action='store_true',
        help='Generate weekly governance report'
    )
    parser.add_argument(
        '--monitor',
        action='store_true',
        help='Run continuous monitoring'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    args = parser.parse_args()

    # Setup
    logger = setup_logging()
    db = GovernanceRhythmDB(Config.get_db_connection_string(), logger)

    if not db.connect():
        logger.error("Failed to connect to database")
        sys.exit(1)

    try:
        rhythm = VEGAGovernanceRhythm(db, logger)

        if args.check_pending:
            report = rhythm.get_pending_suspension_requests()
            if args.json:
                print(json.dumps({
                    "total_pending": report.total_pending,
                    "agents_at_risk": report.agents_at_risk,
                    "oldest_pending_age_hours": report.oldest_pending_age_hours,
                    "generated_at": report.generated_at
                }, indent=2, default=str))

        elif args.verify_integrity:
            violations = rhythm.verify_suspension_integrity()
            if args.json:
                print(json.dumps([{
                    "agent_id": v.agent_id,
                    "violation_type": v.violation_type,
                    "description": v.description,
                    "severity": v.severity
                } for v in violations], indent=2))

        elif args.check_discrepancy:
            high_disc = rhythm.check_discrepancy_thresholds()
            if args.json:
                print(json.dumps(high_disc, indent=2, default=str))

        elif args.weekly:
            report = rhythm.generate_weekly_report()
            if args.json:
                print(json.dumps({
                    "report_id": report.report_id,
                    "report_type": report.report_type,
                    "integrity_status": report.integrity_status.value,
                    "pending_count": report.pending_requests.total_pending,
                    "violation_count": len(report.violations),
                    "recommendations": report.recommendations,
                    "report_hash": report.report_hash
                }, indent=2))

        elif args.monitor:
            rhythm.run_continuous_monitoring()

        else:
            # Default: generate daily report
            report = rhythm.generate_daily_report()
            if args.json:
                print(json.dumps({
                    "report_id": report.report_id,
                    "report_type": report.report_type,
                    "integrity_status": report.integrity_status.value,
                    "pending_count": report.pending_requests.total_pending,
                    "violation_count": len(report.violations),
                    "recommendations": report.recommendations,
                    "report_hash": report.report_hash
                }, indent=2))

    finally:
        db.close()


if __name__ == '__main__':
    main()
