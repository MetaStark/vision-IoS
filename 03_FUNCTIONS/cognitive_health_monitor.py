"""
Cognitive Health Monitor
CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001

Two early warning sirens to prevent silent degradation:
1. Evidence Coverage Ratio (ECR) - are we starving for evidence?
2. NO_SIGNAL Rate by DEFCON - is cognitive engine breaking down?

Author: STIG (CTO)
Date: 2026-01-04
"""

import os
import psycopg2
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json
import logging

# Database connection parameters
DB_HOST = os.environ.get('PGHOST', 'localhost')
DB_PORT = os.environ.get('PGPORT', '54322')
DB_NAME = os.environ.get('PGDATABASE', 'postgres')
DB_USER = os.environ.get('PGUSER', 'postgres')
DB_PASS = os.environ.get('PGPASSWORD', 'postgres')

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# EVIDENCE COVERAGE RATIO (ECR)
# =============================================================================

EXPECTED_MINIMUM_SNIPPETS = 3  # At least 3 evidence snippets per query

# ECR thresholds
ECR_HEALTHY = 1.5       # >= 1.5 is healthy
ECR_ACCEPTABLE = 1.0    # 1.0 - 1.5 is acceptable
ECR_WARNING = 0.5       # 0.5 - 1.0 is warning
# < 0.5 is critical


@dataclass
class ECRResult:
    """Evidence Coverage Ratio result for a single retrieval."""
    retrieved_count: int
    expected_minimum: int
    ecr: float
    status: str  # HEALTHY, ACCEPTABLE, WARNING, CRITICAL

    def to_dict(self) -> Dict:
        return {
            'retrieved_count': self.retrieved_count,
            'expected_minimum': self.expected_minimum,
            'ecr': self.ecr,
            'status': self.status
        }


def calculate_evidence_coverage_ratio(retrieved_count: int) -> ECRResult:
    """
    ECR = retrieved snippets / expected minimum
    If ECR < 1.0, cognition is starving for evidence.

    Returns:
        ECRResult with ECR value and status
    """
    ecr = retrieved_count / EXPECTED_MINIMUM_SNIPPETS

    if ecr >= ECR_HEALTHY:
        status = "HEALTHY"
    elif ecr >= ECR_ACCEPTABLE:
        status = "ACCEPTABLE"
    elif ecr >= ECR_WARNING:
        status = "WARNING"
        msg = (
            "LOW_EVIDENCE_COVERAGE: ECR=" + str(round(ecr, 2)) +
            ", retrieved=" + str(retrieved_count) +
            ", expected_min=" + str(EXPECTED_MINIMUM_SNIPPETS)
        )
        logger.warning(msg)
    else:
        status = "CRITICAL"
        msg = (
            "CRITICAL_EVIDENCE_COVERAGE: ECR=" + str(round(ecr, 2)) +
            ", retrieved=" + str(retrieved_count) +
            ", expected_min=" + str(EXPECTED_MINIMUM_SNIPPETS)
        )
        logger.error(msg)

    return ECRResult(
        retrieved_count=retrieved_count,
        expected_minimum=EXPECTED_MINIMUM_SNIPPETS,
        ecr=ecr,
        status=status
    )


# =============================================================================
# NO_SIGNAL RATE MONITORING
# =============================================================================

# NO_SIGNAL rate thresholds
NO_SIGNAL_HEALTHY = 10.0       # < 10% is healthy
NO_SIGNAL_ACCEPTABLE = 30.0    # 10-30% is acceptable
NO_SIGNAL_WARNING = 50.0       # 30-50% is warning
# > 50% is critical


@dataclass
class NOSignalRateResult:
    """NO_SIGNAL rate for a DEFCON level."""
    defcon_level: str
    total_queries: int
    no_signal_count: int
    rate_percent: float
    status: str  # HEALTHY, ACCEPTABLE, WARNING, CRITICAL

    def to_dict(self) -> Dict:
        return {
            'defcon_level': self.defcon_level,
            'total_queries': self.total_queries,
            'no_signal_count': self.no_signal_count,
            'rate_percent': self.rate_percent,
            'status': self.status
        }


@dataclass
class NOSignalReport:
    """Aggregate NO_SIGNAL rate report across all DEFCON levels."""
    timestamp: datetime
    window_hours: int
    results: Dict[str, NOSignalRateResult]
    alerts: List[str]

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'window_hours': self.window_hours,
            'results': {k: v.to_dict() for k, v in self.results.items()},
            'alerts': self.alerts
        }


def track_no_signal_rate(conn, window_hours: int = 24) -> NOSignalReport:
    """
    Track NO_SIGNAL rate per DEFCON level.
    Spike detection = early warning of cognitive breakdown.

    Args:
        conn: Database connection
        window_hours: Time window to analyze (default 24h)

    Returns:
        NOSignalReport with per-DEFCON stats and alerts
    """
    cursor = conn.cursor()

    # Check if table exists first
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'fhq_governance'
              AND table_name = 'inforage_query_log'
        )
    """)
    table_exists = cursor.fetchone()[0]

    if not table_exists:
        cursor.close()
        return NOSignalReport(
            timestamp=datetime.now(timezone.utc),
            window_hours=window_hours,
            results={},
            alerts=["inforage_query_log table does not exist"]
        )

    try:
        # Check if result_type column exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'fhq_governance'
                  AND table_name = 'inforage_query_log'
                  AND column_name = 'result_type'
            )
        """)
        has_result_type = cursor.fetchone()[0]

        if not has_result_type:
            cursor.close()
            return NOSignalReport(
                timestamp=datetime.now(timezone.utc),
                window_hours=window_hours,
                results={},
                alerts=["result_type column not yet added (run migration 203)"]
            )

        cursor.execute("""
            SELECT
                defcon_level,
                COUNT(*) as total_queries,
                COUNT(*) FILTER (WHERE result_type = 'NO_SIGNAL') as no_signal_count,
                ROUND(100.0 * COUNT(*) FILTER (WHERE result_type = 'NO_SIGNAL') / NULLIF(COUNT(*), 0), 2) as no_signal_rate
            FROM fhq_governance.inforage_query_log
            WHERE created_at > NOW() - INTERVAL '%s hours'
            GROUP BY defcon_level
            ORDER BY defcon_level
        """, [window_hours])

        rows = cursor.fetchall()
    except Exception as e:
        cursor.close()
        return NOSignalReport(
            timestamp=datetime.now(timezone.utc),
            window_hours=window_hours,
            results={},
            alerts=[f"Query failed: {str(e)}"]
        )
    finally:
        cursor.close()

    results = {}
    alerts = []

    for row in rows:
        defcon = row[0] if row[0] else "UNKNOWN"
        total = row[1] or 0
        no_signal = row[2] or 0
        rate = float(row[3]) if row[3] else 0.0

        # Determine status
        if rate < NO_SIGNAL_HEALTHY:
            status = "HEALTHY"
        elif rate < NO_SIGNAL_ACCEPTABLE:
            status = "ACCEPTABLE"
        elif rate < NO_SIGNAL_WARNING:
            status = "WARNING"
            alert_msg = f"HIGH_NO_SIGNAL_RATE: DEFCON={defcon}, rate={rate}%, count={no_signal}/{total}"
            alerts.append(alert_msg)
            logger.warning(alert_msg)
        else:
            status = "CRITICAL"
            alert_msg = f"CRITICAL_NO_SIGNAL_RATE: DEFCON={defcon}, rate={rate}%, count={no_signal}/{total}"
            alerts.append(alert_msg)
            logger.error(alert_msg)

        results[defcon] = NOSignalRateResult(
            defcon_level=defcon,
            total_queries=total,
            no_signal_count=no_signal,
            rate_percent=rate,
            status=status
        )

    return NOSignalReport(
        timestamp=datetime.now(timezone.utc),
        window_hours=window_hours,
        results=results,
        alerts=alerts
    )


# =============================================================================
# AGGREGATE HEALTH CHECK
# =============================================================================

@dataclass
class CognitiveHealthReport:
    """Complete cognitive health status."""
    timestamp: datetime
    overall_status: str  # HEALTHY, ACCEPTABLE, WARNING, CRITICAL
    no_signal_report: NOSignalReport
    recent_ecr_avg: Optional[float]
    data_liveness_ok: bool
    alerts: List[str]

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'overall_status': self.overall_status,
            'no_signal_report': self.no_signal_report.to_dict(),
            'recent_ecr_avg': self.recent_ecr_avg,
            'data_liveness_ok': self.data_liveness_ok,
            'alerts': self.alerts
        }


def get_recent_ecr_average(conn, window_hours: int = 24) -> Optional[float]:
    """Get average ECR from recent queries (if ECR column exists)."""
    cursor = conn.cursor()

    try:
        # Check if ECR column exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'fhq_governance'
                  AND table_name = 'inforage_query_log'
                  AND column_name = 'evidence_coverage_ratio'
            )
        """)
        column_exists = cursor.fetchone()[0]

        if not column_exists:
            return None

        cursor.execute("""
            SELECT AVG(evidence_coverage_ratio)
            FROM fhq_governance.inforage_query_log
            WHERE created_at > NOW() - INTERVAL '%s hours'
              AND evidence_coverage_ratio IS NOT NULL
        """, [window_hours])

        result = cursor.fetchone()
        return float(result[0]) if result and result[0] else None

    except Exception:
        return None
    finally:
        cursor.close()


def check_cognitive_health(conn, window_hours: int = 24) -> CognitiveHealthReport:
    """
    Comprehensive cognitive health check.

    Args:
        conn: Database connection
        window_hours: Time window for analysis

    Returns:
        CognitiveHealthReport with overall status and details
    """
    from data_liveness_checker import check_data_liveness

    alerts = []

    # Check NO_SIGNAL rates
    no_signal_report = track_no_signal_rate(conn, window_hours)
    alerts.extend(no_signal_report.alerts)

    # Check recent ECR average
    recent_ecr_avg = get_recent_ecr_average(conn, window_hours)
    if recent_ecr_avg is not None and recent_ecr_avg < 1.0:
        alerts.append(f"LOW_AVG_ECR: {recent_ecr_avg:.2f} over {window_hours}h")

    # Check data liveness
    try:
        liveness_report = check_data_liveness(conn)
        data_liveness_ok = liveness_report.all_fresh
        if not data_liveness_ok:
            alerts.append(f"STALE_DATA: {', '.join(liveness_report.stale_domains)}")
    except Exception as e:
        data_liveness_ok = False
        alerts.append(f"LIVENESS_CHECK_FAILED: {str(e)}")

    # Determine overall status
    if not alerts:
        overall_status = "HEALTHY"
    elif any("CRITICAL" in a for a in alerts):
        overall_status = "CRITICAL"
    elif any("HIGH" in a or "WARNING" in a for a in alerts):
        overall_status = "WARNING"
    else:
        overall_status = "ACCEPTABLE"

    return CognitiveHealthReport(
        timestamp=datetime.now(timezone.utc),
        overall_status=overall_status,
        no_signal_report=no_signal_report,
        recent_ecr_avg=recent_ecr_avg,
        data_liveness_ok=data_liveness_ok,
        alerts=alerts
    )


# =============================================================================
# DASHBOARD QUERY (for external monitoring tools)
# =============================================================================

def get_dashboard_metrics(conn, window_hours: int = 24) -> List[Dict]:
    """
    Real-time cognitive health dashboard metrics.

    Returns hourly aggregates for visualization.
    """
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'fhq_governance'
                  AND table_name = 'inforage_query_log'
            )
        """)
        if not cursor.fetchone()[0]:
            return []

        # Check which columns exist
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'fhq_governance'
              AND table_name = 'inforage_query_log'
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]

        # Build query based on available columns
        select_parts = [
            "DATE_TRUNC('hour', created_at) as hour",
            "defcon_level",
            "COUNT(*) as queries"
        ]

        if 'latency_ms' in existing_columns:
            select_parts.append("AVG(latency_ms) as avg_latency")
        if 'cost_usd' in existing_columns:
            select_parts.append("AVG(cost_usd) as avg_cost")
        if 'result_type' in existing_columns:
            select_parts.append("COUNT(*) FILTER (WHERE result_type = 'NO_SIGNAL') as no_signal_count")
            select_parts.append(
                "ROUND(100.0 * COUNT(*) FILTER (WHERE result_type = 'NO_SIGNAL') / NULLIF(COUNT(*), 0), 2) as no_signal_rate"
            )
        if 'evidence_coverage_ratio' in existing_columns:
            select_parts.append("AVG(evidence_coverage_ratio) as avg_ecr")

        query = f"""
            SELECT {', '.join(select_parts)}
            FROM fhq_governance.inforage_query_log
            WHERE created_at > NOW() - INTERVAL '{window_hours} hours'
            GROUP BY DATE_TRUNC('hour', created_at), defcon_level
            ORDER BY hour DESC, defcon_level
        """

        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        return [dict(zip(columns, row)) for row in rows]

    except Exception as e:
        logger.error(f"Dashboard query failed: {e}")
        return []
    finally:
        cursor.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Standalone execution for testing/monitoring."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

    try:
        print("=" * 60)
        print("COGNITIVE HEALTH MONITOR")
        print("CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001")
        print("=" * 60)

        report = check_cognitive_health(conn, window_hours=24)

        print(f"\nTimestamp: {report.timestamp.isoformat()}")
        print(f"Overall Status: {report.overall_status}")
        print(f"Data Liveness OK: {report.data_liveness_ok}")
        print(f"Recent ECR Average: {report.recent_ecr_avg}")

        print("\nNO_SIGNAL Rate by DEFCON:")
        if report.no_signal_report.results:
            for defcon, result in report.no_signal_report.results.items():
                print(f"  {defcon}: {result.rate_percent}% "
                      f"({result.no_signal_count}/{result.total_queries}) - {result.status}")
        else:
            print("  No data available")

        print("\nAlerts:")
        if report.alerts:
            for alert in report.alerts:
                print(f"  - {alert}")
        else:
            print("  No alerts")

        print("\n" + "=" * 60)
        print("JSON OUTPUT:")
        print(json.dumps(report.to_dict(), indent=2, default=str))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
