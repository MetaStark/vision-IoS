"""
Canonical Time Converter (CTC) - ADR-013A Execution Layer
=========================================================

CEO-DIR-2026-DBV-002 Directive Implementation
Reference Clock: CET/CEST (Europe/Oslo) - FjordHQ Bergen HQ

All canonical timestamps must:
1. Store in UTC
2. Include linked CET field
3. Be verifiable before any trade/signal/forecast is valid

Author: STIG (EC-003_2026_PRODUCTION)
Created: 2026-01-20T19:30:00Z
"""

from datetime import datetime, timezone
from typing import Tuple, Optional
import hashlib
import json

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False
    print("WARNING: pytz not installed. Using fallback timezone handling.")

# Reference timezone for FjordHQ HQ (Bergen, Norway)
CANONICAL_TZ_NAME = "Europe/Oslo"
CANONICAL_TZ = pytz.timezone(CANONICAL_TZ_NAME) if PYTZ_AVAILABLE else None


class CanonicalTimeConverter:
    """
    Audit-grade timezone converter with DST handling.

    All FjordHQ timestamps must pass through this converter to ensure:
    - UTC storage consistency
    - CET/CEST display for human operators
    - Deterministic audit trails
    """

    VERSION = "1.0.0"
    ADR_REFERENCE = "ADR-013A"

    def __init__(self):
        if not PYTZ_AVAILABLE:
            raise RuntimeError("CTC requires pytz for audit-grade DST handling. Install: pip install pytz")
        self.tz_oslo = pytz.timezone(CANONICAL_TZ_NAME)
        self.tz_utc = pytz.UTC

    def now_utc(self) -> datetime:
        """Get current UTC time (timezone-aware)."""
        return datetime.now(self.tz_utc)

    def now_cet(self) -> datetime:
        """Get current CET/CEST time (timezone-aware)."""
        return datetime.now(self.tz_oslo)

    def utc_to_cet(self, utc_dt: datetime) -> datetime:
        """
        Convert UTC datetime to CET/CEST.

        Args:
            utc_dt: UTC datetime (naive or aware)

        Returns:
            CET/CEST datetime (timezone-aware)
        """
        if utc_dt.tzinfo is None:
            utc_dt = self.tz_utc.localize(utc_dt)
        return utc_dt.astimezone(self.tz_oslo)

    def cet_to_utc(self, cet_dt: datetime) -> datetime:
        """
        Convert CET/CEST datetime to UTC.

        Args:
            cet_dt: CET/CEST datetime (naive or aware)

        Returns:
            UTC datetime (timezone-aware)
        """
        if cet_dt.tzinfo is None:
            cet_dt = self.tz_oslo.localize(cet_dt)
        return cet_dt.astimezone(self.tz_utc)

    def canonical_pair(self, utc_dt: Optional[datetime] = None) -> Tuple[str, str]:
        """
        Generate canonical timestamp pair (UTC + CET) for storage.

        Args:
            utc_dt: Optional UTC datetime. If None, uses current time.

        Returns:
            Tuple of (utc_iso, cet_iso) strings
        """
        if utc_dt is None:
            utc_dt = self.now_utc()
        elif utc_dt.tzinfo is None:
            utc_dt = self.tz_utc.localize(utc_dt)

        cet_dt = self.utc_to_cet(utc_dt)

        utc_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        cet_iso = cet_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + cet_dt.strftime("%z")

        return (utc_iso, cet_iso)

    def canonical_dict(self, utc_dt: Optional[datetime] = None, field_prefix: str = "") -> dict:
        """
        Generate canonical timestamp dictionary for database storage.

        Args:
            utc_dt: Optional UTC datetime
            field_prefix: Optional prefix for field names

        Returns:
            Dict with {prefix}timestamp_utc and {prefix}timestamp_cet fields
        """
        utc_iso, cet_iso = self.canonical_pair(utc_dt)
        prefix = f"{field_prefix}_" if field_prefix else ""
        return {
            f"{prefix}timestamp_utc": utc_iso,
            f"{prefix}timestamp_cet": cet_iso,
            f"{prefix}timezone_source": CANONICAL_TZ_NAME,
            f"{prefix}ctc_version": self.VERSION
        }

    def validate_canonical_timestamp(self, utc_str: str, cet_str: str) -> Tuple[bool, str]:
        """
        Validate that a UTC/CET pair is consistent.

        Args:
            utc_str: UTC ISO timestamp string
            cet_str: CET ISO timestamp string

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Parse UTC
            utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))

            # Parse CET
            cet_dt = datetime.fromisoformat(cet_str)

            # Convert CET to UTC and compare
            cet_as_utc = self.cet_to_utc(cet_dt)

            # Allow 1 second tolerance for rounding
            delta = abs((utc_dt - cet_as_utc).total_seconds())
            if delta > 1.0:
                return (False, f"Timestamp drift detected: {delta}s between UTC and CET conversion")

            return (True, "OK")

        except Exception as e:
            return (False, f"Validation error: {str(e)}")

    def is_dst(self, dt: Optional[datetime] = None) -> bool:
        """Check if given datetime is in DST (summer time)."""
        if dt is None:
            dt = self.now_cet()
        elif dt.tzinfo is None:
            dt = self.tz_oslo.localize(dt)
        return bool(dt.dst())

    def generate_audit_hash(self, utc_str: str, cet_str: str, context: str = "") -> str:
        """
        Generate audit hash for timestamp pair.

        Args:
            utc_str: UTC timestamp
            cet_str: CET timestamp
            context: Additional context for hash

        Returns:
            SHA256 hash of canonical timestamp data
        """
        payload = json.dumps({
            "utc": utc_str,
            "cet": cet_str,
            "tz": CANONICAL_TZ_NAME,
            "ctc_version": self.VERSION,
            "context": context
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


# Global singleton instance
_ctc_instance = None

def get_ctc() -> CanonicalTimeConverter:
    """Get or create the global CTC instance."""
    global _ctc_instance
    if _ctc_instance is None:
        _ctc_instance = CanonicalTimeConverter()
    return _ctc_instance


def canonical_now() -> Tuple[str, str]:
    """Convenience function: Get current canonical timestamp pair."""
    return get_ctc().canonical_pair()


def canonical_dict(utc_dt: Optional[datetime] = None, prefix: str = "") -> dict:
    """Convenience function: Get canonical timestamp dict."""
    return get_ctc().canonical_dict(utc_dt, prefix)


# Pre-execution validation decorator
def requires_canonical_time(func):
    """
    Decorator to ensure function has valid canonical time context.

    Usage:
        @requires_canonical_time
        def submit_trade(trade_data: dict):
            # trade_data must contain valid timestamp_utc and timestamp_cet
            pass
    """
    def wrapper(*args, **kwargs):
        ctc = get_ctc()

        # Add canonical timestamps if not present
        if 'timestamp_utc' not in kwargs:
            utc_iso, cet_iso = ctc.canonical_pair()
            kwargs['timestamp_utc'] = utc_iso
            kwargs['timestamp_cet'] = cet_iso

        return func(*args, **kwargs)
    return wrapper


if __name__ == "__main__":
    # Self-test
    ctc = CanonicalTimeConverter()

    print("=" * 60)
    print("CANONICAL TIME CONVERTER (CTC) - ADR-013A")
    print("=" * 60)
    print(f"Version: {ctc.VERSION}")
    print(f"Reference TZ: {CANONICAL_TZ_NAME}")
    print(f"DST Active: {ctc.is_dst()}")
    print()

    utc_iso, cet_iso = ctc.canonical_pair()
    print(f"UTC:  {utc_iso}")
    print(f"CET:  {cet_iso}")
    print()

    is_valid, msg = ctc.validate_canonical_timestamp(utc_iso, cet_iso)
    print(f"Validation: {msg}")

    audit_hash = ctc.generate_audit_hash(utc_iso, cet_iso, "CTC_SELF_TEST")
    print(f"Audit Hash: {audit_hash[:16]}...")
    print("=" * 60)
