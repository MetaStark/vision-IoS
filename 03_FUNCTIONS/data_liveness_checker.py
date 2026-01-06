"""
Data Liveness Checker
CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001

Per-domain staleness gates for Cognitive Engine.
Not one global 24h rule - each data domain has its own freshness requirement.

Author: STIG (CTO)
Date: 2026-01-04
"""

import os
import psycopg2
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Dict, Optional, List
import json

# Database connection parameters
DB_HOST = os.environ.get('PGHOST', 'localhost')
DB_PORT = os.environ.get('PGPORT', '54322')
DB_NAME = os.environ.get('PGDATABASE', 'postgres')
DB_USER = os.environ.get('PGUSER', 'postgres')
DB_PASS = os.environ.get('PGPASSWORD', 'postgres')


@dataclass
class LivenessResult:
    """Result of staleness check for a single data domain."""
    domain: str
    actual_staleness: timedelta
    max_allowed: timedelta
    is_stale: bool
    abort_reason: Optional[str]
    record_count: int = 0
    latest_timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            'domain': self.domain,
            'actual_staleness_hours': self.actual_staleness.total_seconds() / 3600,
            'max_allowed_hours': self.max_allowed.total_seconds() / 3600,
            'is_stale': self.is_stale,
            'abort_reason': self.abort_reason,
            'record_count': self.record_count,
            'latest_timestamp': self.latest_timestamp.isoformat() if self.latest_timestamp else None
        }


@dataclass
class LivenessReport:
    """Aggregate report of all domain staleness checks."""
    timestamp: datetime
    all_fresh: bool
    stale_domains: List[str]
    results: Dict[str, LivenessResult]
    abort_message: Optional[str]

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'all_fresh': self.all_fresh,
            'stale_domains': self.stale_domains,
            'results': {k: v.to_dict() for k, v in self.results.items()},
            'abort_message': self.abort_message
        }


# Per-domain staleness gates (CEO directive)
# CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001 P1: Market-aware staleness
# CRYPTO (24/7 markets): max_ok=6h, warn=6-12h, blackout=12h+
# The 12h gate allows crypto signals with graded confidence penalty
# EQUITY/FX would use stricter rules (2h) during trading hours
STALENESS_GATES = {
    'regime_state': timedelta(hours=12),  # P1: Relaxed for SHADOW mode testing
    'market_prices': timedelta(hours=12), # P1: Crypto blackout threshold (was 6h)
    'evidence_nodes': timedelta(hours=48), # P1: Relaxed for SHADOW mode testing
    'causal_edges': timedelta(hours=72)
}

# Market-aware price staleness thresholds (CEO-DIR-2026-SITC-DATA-BLACKOUT-FIX-001 P1)
PRICE_STALENESS_CRYPTO = {
    'max_ok_hours': 6,       # Full confidence
    'warn_hours': 12,        # Graded confidence penalty (0.5-0.8x)
    'blackout_hours': 12     # Abort threshold
}

PRICE_STALENESS_EQUITY = {
    'max_ok_hours': 2,       # Trading hours only
    'warn_hours': 4,
    'blackout_hours': 8      # Extended closure
}

# SQL queries to check freshness per domain
# Schema mapping verified against production database
STALENESS_QUERIES = {
    'regime_state': """
        SELECT
            COUNT(*) as record_count,
            MAX(last_updated_at) as latest_timestamp
        FROM fhq_meta.regime_state
    """,
    'market_prices': """
        SELECT
            COUNT(*) as record_count,
            MAX(timestamp) as latest_timestamp
        FROM fhq_market.prices
    """,
    'evidence_nodes': """
        SELECT
            COUNT(*) as record_count,
            MAX(updated_at) as latest_timestamp
        FROM fhq_canonical.evidence_nodes
    """,
    'causal_edges': """
        SELECT
            COUNT(*) as record_count,
            MAX(created_at) as latest_timestamp
        FROM fhq_alpha.causal_edges
    """
}


def get_staleness(conn, domain: str) -> tuple:
    """
    Get staleness for a specific data domain.

    Returns:
        Tuple of (actual_staleness: timedelta, record_count: int, latest_timestamp: datetime)
    """
    query = STALENESS_QUERIES.get(domain)
    if not query:
        raise ValueError(f"Unknown domain: {domain}")

    cursor = conn.cursor()
    try:
        cursor.execute(query)
        row = cursor.fetchone()

        if row is None or row[1] is None:
            # No data - treat as infinitely stale
            return (timedelta(hours=9999), 0, None)

        record_count = row[0]
        latest_timestamp = row[1]

        # Ensure timezone-aware comparison
        if latest_timestamp.tzinfo is None:
            latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        actual_staleness = now - latest_timestamp

        return (actual_staleness, record_count, latest_timestamp)
    finally:
        cursor.close()


def check_domain_liveness(conn, domain: str) -> LivenessResult:
    """
    Check liveness for a single data domain.

    Returns:
        LivenessResult with staleness info and abort reason if stale
    """
    max_stale = STALENESS_GATES.get(domain)
    if max_stale is None:
        raise ValueError(f"Unknown domain: {domain}")

    try:
        actual_staleness, record_count, latest_timestamp = get_staleness(conn, domain)
        is_stale = actual_staleness > max_stale

        if is_stale:
            hours_stale = actual_staleness.total_seconds() / 3600
            max_hours = max_stale.total_seconds() / 3600
            abort_reason = f"{domain} is {hours_stale:.2f}h stale (max: {max_hours:.0f}h)"
        else:
            abort_reason = None

        return LivenessResult(
            domain=domain,
            actual_staleness=actual_staleness,
            max_allowed=max_stale,
            is_stale=is_stale,
            abort_reason=abort_reason,
            record_count=record_count,
            latest_timestamp=latest_timestamp
        )
    except Exception as e:
        # Rollback the failed transaction to allow subsequent queries
        try:
            conn.rollback()
        except:
            pass
        # Domain check failed - treat as stale for safety
        return LivenessResult(
            domain=domain,
            actual_staleness=timedelta(hours=9999),
            max_allowed=max_stale,
            is_stale=True,
            abort_reason=f"{domain} check failed: {str(e)}",
            record_count=0,
            latest_timestamp=None
        )


def check_data_liveness(conn) -> LivenessReport:
    """
    Check liveness for all data domains.

    Abort semantics: If ANY domain exceeds its gate, return with specific domain identified.

    Returns:
        LivenessReport with all domain results and aggregate status
    """
    results = {}
    stale_domains = []

    for domain in STALENESS_GATES.keys():
        result = check_domain_liveness(conn, domain)
        results[domain] = result

        if result.is_stale:
            stale_domains.append(domain)

    all_fresh = len(stale_domains) == 0

    if stale_domains:
        abort_reasons = [results[d].abort_reason for d in stale_domains if results[d].abort_reason]
        abort_message = "; ".join(abort_reasons)
    else:
        abort_message = None

    return LivenessReport(
        timestamp=datetime.now(timezone.utc),
        all_fresh=all_fresh,
        stale_domains=stale_domains,
        results=results,
        abort_message=abort_message
    )


def should_abort_cognitive_cycle(conn) -> tuple:
    """
    Convenience function for gateway to check if cognitive cycle should abort.

    Returns:
        Tuple of (should_abort: bool, abort_reason: Optional[str], report: LivenessReport)
    """
    report = check_data_liveness(conn)

    if not report.all_fresh:
        return (True, report.abort_message, report)

    return (False, None, report)


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
        report = check_data_liveness(conn)

        print("=" * 60)
        print("DATA LIVENESS REPORT")
        print("CEO-DIR-2026-PLANMODE-COGNITIVE-INTEGRATION-001")
        print("=" * 60)
        print(f"Timestamp: {report.timestamp.isoformat()}")
        print(f"All Fresh: {report.all_fresh}")
        print()

        for domain, result in report.results.items():
            status = "FRESH" if not result.is_stale else "STALE"
            hours = result.actual_staleness.total_seconds() / 3600
            max_hours = result.max_allowed.total_seconds() / 3600
            print(f"  {domain}:")
            print(f"    Status: {status}")
            print(f"    Staleness: {hours:.2f}h / {max_hours:.0f}h max")
            print(f"    Records: {result.record_count:,}")
            if result.latest_timestamp:
                print(f"    Latest: {result.latest_timestamp.isoformat()}")
            print()

        if report.abort_message:
            print(f"ABORT REASON: {report.abort_message}")
        else:
            print("STATUS: All domains within freshness gates")

        # Output JSON for programmatic use
        print("\n" + "=" * 60)
        print("JSON OUTPUT:")
        print(json.dumps(report.to_dict(), indent=2))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
