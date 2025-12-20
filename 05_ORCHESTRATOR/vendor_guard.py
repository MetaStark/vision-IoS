#!/usr/bin/env python3
"""
IoS-014 VENDOR GUARD
Authority: CEO DIRECTIVE — IoS-014 BUILD & AUTONOMOUS AGENT ACTIVATION
Purpose: Enforce 90% soft ceiling, fallback routing, quota protection

This module prevents the "45-minute crash scenario" by:
1. Checking vendor quotas BEFORE any API call
2. Routing to fallback vendors when soft ceiling reached
3. Logging all quota decisions for VEGA audit
4. Gracefully degrading instead of crashing
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor


class QuotaDecision(Enum):
    """Possible quota check outcomes"""
    PROCEED = "PROCEED"
    USE_FALLBACK = "USE_FALLBACK"
    SKIP_QUOTA_PROTECTION = "SKIP_QUOTA_PROTECTION"
    VENDOR_NOT_FOUND = "VENDOR_NOT_FOUND"
    HARD_LIMIT_REACHED = "HARD_LIMIT_REACHED"


@dataclass
class VendorQuotaResult:
    """Result of a vendor quota check"""
    vendor_name: str
    can_proceed: bool
    decision: QuotaDecision
    current_usage: int
    soft_ceiling: int
    hard_limit: Optional[int]
    fallback_vendor: Optional[str]
    message: str


class VendorGuard:
    """
    IoS-014 Vendor Rate Limit Guard

    Implements ADR-012 Economic Safety at runtime:
    - 90% soft ceiling enforcement
    - Vendor priority routing
    - Fallback chain execution
    - Quota event logging
    """

    def __init__(self, connection_string: str, logger: Optional[logging.Logger] = None):
        self.connection_string = connection_string
        self.logger = logger or logging.getLogger("vendor_guard")
        self._conn = None
        self._vendor_cache: Dict[str, Dict] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Refresh cache every minute

    def connect(self):
        """Establish database connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.connection_string)
        return self._conn

    def close(self):
        """Close database connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()

    def _refresh_vendor_cache(self):
        """Refresh vendor configuration cache from database"""
        now = datetime.now(timezone.utc)
        if (self._cache_timestamp is None or
            (now - self._cache_timestamp).total_seconds() > self._cache_ttl_seconds):

            conn = self.connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        v.vendor_id,
                        v.vendor_name,
                        v.tier,
                        v.free_tier_limit,
                        v.interval_type,
                        v.soft_ceiling_pct,
                        v.hard_limit,
                        v.priority_rank,
                        v.data_domains,
                        v.is_active,
                        v.fallback_vendor_id,
                        f.vendor_name as fallback_vendor_name
                    FROM fhq_meta.vendor_limits v
                    LEFT JOIN fhq_meta.vendor_limits f ON f.vendor_id = v.fallback_vendor_id
                    WHERE v.is_active = TRUE
                    ORDER BY v.priority_rank
                """)
                vendors = cur.fetchall()
                self._vendor_cache = {v['vendor_name']: dict(v) for v in vendors}
                self._cache_timestamp = now
                self.logger.debug(f"Refreshed vendor cache: {len(self._vendor_cache)} vendors")

    def _get_interval_start(self, interval_type: str) -> datetime:
        """Calculate the start of the current interval"""
        now = datetime.now(timezone.utc)
        if interval_type == 'MINUTE':
            return now.replace(second=0, microsecond=0)
        elif interval_type == 'HOUR':
            return now.replace(minute=0, second=0, microsecond=0)
        elif interval_type == 'DAY':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif interval_type == 'MONTH':
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return now

    def _get_current_usage(self, vendor_id: str, interval_start: datetime, interval_type: str) -> int:
        """Get current usage for a vendor in the current interval"""
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(current_usage, 0) as usage
                FROM fhq_meta.vendor_usage_counters
                WHERE vendor_id = %s
                  AND interval_start = %s
                  AND interval_type = %s
            """, (vendor_id, interval_start, interval_type))
            row = cur.fetchone()
            return row[0] if row else 0

    def check_quota(self, vendor_name: str, calls_needed: int = 1) -> VendorQuotaResult:
        """
        Check if a vendor can handle the requested number of calls.

        This is the primary method called BEFORE any API request.

        Args:
            vendor_name: Name of the vendor (e.g., 'BINANCE', 'OPENAI')
            calls_needed: Number of API calls being requested

        Returns:
            VendorQuotaResult with decision and fallback info
        """
        self._refresh_vendor_cache()

        vendor = self._vendor_cache.get(vendor_name)
        if not vendor:
            return VendorQuotaResult(
                vendor_name=vendor_name,
                can_proceed=False,
                decision=QuotaDecision.VENDOR_NOT_FOUND,
                current_usage=0,
                soft_ceiling=0,
                hard_limit=None,
                fallback_vendor=None,
                message=f"Vendor '{vendor_name}' not found or not active"
            )

        # Calculate soft ceiling
        soft_ceiling = int(vendor['free_tier_limit'] * float(vendor['soft_ceiling_pct']))
        hard_limit = vendor['hard_limit']

        # Get current usage
        interval_start = self._get_interval_start(vendor['interval_type'])
        current_usage = self._get_current_usage(
            str(vendor['vendor_id']),
            interval_start,
            vendor['interval_type']
        )

        projected_usage = current_usage + calls_needed

        # Check hard limit first
        if hard_limit and projected_usage > hard_limit:
            self._log_quota_event(
                vendor_id=str(vendor['vendor_id']),
                event_type='HARD_LIMIT_REACHED',
                task_name=None,
                previous_usage=current_usage,
                new_usage=projected_usage,
                ceiling_value=hard_limit,
                decision='BLOCKED',
                decision_rationale=f"Hard limit {hard_limit} would be exceeded"
            )
            return VendorQuotaResult(
                vendor_name=vendor_name,
                can_proceed=False,
                decision=QuotaDecision.HARD_LIMIT_REACHED,
                current_usage=current_usage,
                soft_ceiling=soft_ceiling,
                hard_limit=hard_limit,
                fallback_vendor=vendor['fallback_vendor_name'],
                message=f"Hard limit {hard_limit} would be exceeded ({projected_usage})"
            )

        # Check soft ceiling
        if projected_usage <= soft_ceiling:
            return VendorQuotaResult(
                vendor_name=vendor_name,
                can_proceed=True,
                decision=QuotaDecision.PROCEED,
                current_usage=current_usage,
                soft_ceiling=soft_ceiling,
                hard_limit=hard_limit,
                fallback_vendor=None,
                message=f"Within quota: {current_usage}/{soft_ceiling} ({vendor['interval_type']})"
            )

        # Soft ceiling exceeded - check for fallback
        if vendor['fallback_vendor_name']:
            self._log_quota_event(
                vendor_id=str(vendor['vendor_id']),
                event_type='SOFT_CEILING_REACHED',
                task_name=None,
                previous_usage=current_usage,
                new_usage=projected_usage,
                ceiling_value=soft_ceiling,
                decision='FALLBACK_TRIGGERED',
                decision_rationale=f"Routing to {vendor['fallback_vendor_name']}"
            )
            return VendorQuotaResult(
                vendor_name=vendor_name,
                can_proceed=False,
                decision=QuotaDecision.USE_FALLBACK,
                current_usage=current_usage,
                soft_ceiling=soft_ceiling,
                hard_limit=hard_limit,
                fallback_vendor=vendor['fallback_vendor_name'],
                message=f"Soft ceiling reached ({current_usage}/{soft_ceiling}), use fallback: {vendor['fallback_vendor_name']}"
            )

        # No fallback available - skip with protection
        self._log_quota_event(
            vendor_id=str(vendor['vendor_id']),
            event_type='SOFT_CEILING_REACHED',
            task_name=None,
            previous_usage=current_usage,
            new_usage=projected_usage,
            ceiling_value=soft_ceiling,
            decision='SKIPPED_QUOTA_PROTECTION',
            decision_rationale="No fallback available, skipping to protect quota"
        )
        return VendorQuotaResult(
            vendor_name=vendor_name,
            can_proceed=False,
            decision=QuotaDecision.SKIP_QUOTA_PROTECTION,
            current_usage=current_usage,
            soft_ceiling=soft_ceiling,
            hard_limit=hard_limit,
            fallback_vendor=None,
            message=f"Soft ceiling reached ({current_usage}/{soft_ceiling}), no fallback - SKIPPING"
        )

    def increment_usage(self, vendor_name: str, calls: int = 1, task_name: Optional[str] = None) -> bool:
        """
        Increment usage counter after a successful API call.

        Call this AFTER each successful API request.
        """
        self._refresh_vendor_cache()
        vendor = self._vendor_cache.get(vendor_name)
        if not vendor:
            return False

        interval_start = self._get_interval_start(vendor['interval_type'])

        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fhq_meta.vendor_usage_counters
                    (vendor_id, interval_start, interval_type, current_usage)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (vendor_id, interval_start, interval_type)
                DO UPDATE SET
                    current_usage = fhq_meta.vendor_usage_counters.current_usage + %s,
                    peak_usage = GREATEST(
                        fhq_meta.vendor_usage_counters.peak_usage,
                        fhq_meta.vendor_usage_counters.current_usage + %s
                    ),
                    last_updated = NOW()
                RETURNING current_usage
            """, (
                str(vendor['vendor_id']),
                interval_start,
                vendor['interval_type'],
                calls,
                calls,
                calls
            ))
            new_usage = cur.fetchone()[0]
            conn.commit()

            self._log_quota_event(
                vendor_id=str(vendor['vendor_id']),
                event_type='USAGE_INCREMENT',
                task_name=task_name,
                previous_usage=new_usage - calls,
                new_usage=new_usage,
                ceiling_value=int(vendor['free_tier_limit'] * float(vendor['soft_ceiling_pct'])),
                decision='RECORDED',
                decision_rationale=f"Usage incremented by {calls}"
            )
            return True

    def resolve_vendor_chain(self, vendor_name: str, calls_needed: int = 1) -> Tuple[Optional[str], VendorQuotaResult]:
        """
        Resolve the best available vendor following the fallback chain.

        Returns:
            Tuple of (resolved_vendor_name, quota_result)
            If no vendor available, returns (None, last_result)
        """
        visited = set()
        current_vendor = vendor_name
        last_result = None

        while current_vendor and current_vendor not in visited:
            visited.add(current_vendor)
            result = self.check_quota(current_vendor, calls_needed)
            last_result = result

            if result.can_proceed:
                self.logger.info(f"Resolved vendor chain: {vendor_name} -> {current_vendor}")
                return current_vendor, result

            if result.decision == QuotaDecision.USE_FALLBACK and result.fallback_vendor:
                self.logger.info(f"Fallback: {current_vendor} -> {result.fallback_vendor}")
                current_vendor = result.fallback_vendor
            else:
                break

        return None, last_result

    def get_best_vendor_for_domain(self, domain: str, calls_needed: int = 1) -> Tuple[Optional[str], VendorQuotaResult]:
        """
        Get the best available vendor for a given data domain.

        Args:
            domain: Data domain (e.g., 'CRYPTO', 'EQUITY', 'LLM', 'NEWS')
            calls_needed: Number of calls needed

        Returns:
            Tuple of (vendor_name, quota_result) or (None, None) if no vendor available
        """
        self._refresh_vendor_cache()

        # Find vendors that serve this domain, sorted by priority
        candidates = [
            v for v in self._vendor_cache.values()
            if domain in v.get('data_domains', [])
        ]
        candidates.sort(key=lambda x: x['priority_rank'])

        for vendor in candidates:
            resolved, result = self.resolve_vendor_chain(vendor['vendor_name'], calls_needed)
            if resolved:
                return resolved, result

        return None, None

    def get_quota_summary(self) -> List[Dict[str, Any]]:
        """Get current quota status for all vendors"""
        self._refresh_vendor_cache()
        summary = []

        for vendor_name, vendor in self._vendor_cache.items():
            interval_start = self._get_interval_start(vendor['interval_type'])
            current_usage = self._get_current_usage(
                str(vendor['vendor_id']),
                interval_start,
                vendor['interval_type']
            )
            soft_ceiling = int(vendor['free_tier_limit'] * float(vendor['soft_ceiling_pct']))
            usage_pct = (current_usage / soft_ceiling * 100) if soft_ceiling > 0 else 0

            summary.append({
                'vendor': vendor_name,
                'tier': vendor['tier'],
                'usage': current_usage,
                'ceiling': soft_ceiling,
                'limit': vendor['free_tier_limit'],
                'interval': vendor['interval_type'],
                'usage_pct': round(usage_pct, 1),
                'status': 'OK' if usage_pct < 90 else 'WARNING' if usage_pct < 100 else 'CRITICAL'
            })

        return sorted(summary, key=lambda x: x['usage_pct'], reverse=True)

    def _log_quota_event(
        self,
        vendor_id: str,
        event_type: str,
        task_name: Optional[str],
        previous_usage: int,
        new_usage: int,
        ceiling_value: int,
        decision: str,
        decision_rationale: str
    ):
        """Log a quota event for VEGA audit"""
        try:
            conn = self.connect()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO fhq_governance.vendor_quota_events (
                        vendor_id, event_type, task_name,
                        previous_usage, new_usage, ceiling_value,
                        decision, decision_rationale
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    vendor_id, event_type, task_name,
                    previous_usage, new_usage, ceiling_value,
                    decision, decision_rationale
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to log quota event: {e}")


# =============================================================================
# Convenience functions for direct usage
# =============================================================================

_guard_instance: Optional[VendorGuard] = None

def get_vendor_guard() -> VendorGuard:
    """Get or create singleton VendorGuard instance"""
    global _guard_instance
    if _guard_instance is None:
        host = os.getenv("PGHOST", "127.0.0.1")
        port = os.getenv("PGPORT", "54322")
        database = os.getenv("PGDATABASE", "postgres")
        user = os.getenv("PGUSER", "postgres")
        password = os.getenv("PGPASSWORD", "postgres")
        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        _guard_instance = VendorGuard(conn_string)
    return _guard_instance


def check_and_route(vendor_name: str, calls: int = 1) -> Tuple[Optional[str], str]:
    """
    Convenience function: Check quota and resolve to best vendor.

    Returns:
        Tuple of (vendor_to_use, status_message)
        If None returned, operation should be skipped.
    """
    guard = get_vendor_guard()
    resolved, result = guard.resolve_vendor_chain(vendor_name, calls)
    return resolved, result.message if result else "No result"


if __name__ == "__main__":
    # Test the VendorGuard
    logging.basicConfig(level=logging.INFO)
    guard = get_vendor_guard()

    print("\n=== VENDOR QUOTA SUMMARY ===")
    for item in guard.get_quota_summary():
        status_icon = "✓" if item['status'] == 'OK' else "⚠" if item['status'] == 'WARNING' else "✗"
        print(f"{status_icon} {item['vendor']:15} [{item['tier']:6}] {item['usage']:>5}/{item['ceiling']:<5} ({item['usage_pct']:>5.1f}%) {item['interval']}")

    print("\n=== TEST QUOTA CHECKS ===")
    for vendor in ['BINANCE', 'DEEPSEEK', 'ALPHAVANTAGE', 'OPENAI']:
        result = guard.check_quota(vendor, 1)
        print(f"{vendor}: {result.decision.value} - {result.message}")

    print("\n=== TEST DOMAIN ROUTING ===")
    for domain in ['CRYPTO', 'EQUITY', 'LLM', 'NEWS']:
        vendor, result = guard.get_best_vendor_for_domain(domain)
        print(f"{domain}: Best vendor = {vendor}")
