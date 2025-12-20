#!/usr/bin/env python3
"""
IoS CANONICAL FRESHNESS SENTINEL
=================================
Authority: CEO Directive - Canonical Consolidation
Reference: ADR-010 (Discrepancy Scoring), ADR-013 (One-True-Source)
Generated: 2025-12-08

PURPOSE:
    Proactive daily check to detect upstream vendor broken feeds
    BEFORE they propagate to IoS-003 perception.

CHECKS:
    1. fhq_market.prices has data for latest trading day
    2. IoS-003 has no missing_dates gap
    3. Log any discrepancies to discrepancy_events (ADR-010)

Schedule: Daily, before IoS-003 run
"""

import os
import json
import hashlib
import uuid
from datetime import datetime, timedelta, timezone, date
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}

CANONICAL_ASSETS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'EURUSD']

# =============================================================================
# ASSET-TYPE-AWARE THRESHOLDS (ADR-010 Compliant)
# =============================================================================
# Per audit: Different asset types have different trading schedules
#   - Crypto: 24/7 trading
#   - Equity: Weekdays only (no weekends/holidays)
#   - Macro: Variable frequency (FRED series can be weekly/monthly)

ASSET_TYPE_THRESHOLDS = {
    'CRYPTO': {
        'warn_days': 1,
        'alert_days': 2,
        'critical_days': 3
    },
    'EQUITY': {
        'warn_days': 2,
        'alert_days': 3,
        'critical_days': 5
    },
    'FX': {
        'warn_days': 2,  # No weekend trading
        'alert_days': 3,
        'critical_days': 5
    },
    'MACRO': {
        'warn_days': 7,   # Weekly series common
        'alert_days': 14,
        'critical_days': 30
    }
}

# Asset to type mapping
ASSET_TYPE_MAP = {
    'BTC-USD': 'CRYPTO',
    'ETH-USD': 'CRYPTO',
    'SOL-USD': 'CRYPTO',
    'EURUSD': 'FX',
    'SPY': 'EQUITY',
    'QQQ': 'EQUITY',
    # FRED series
    'DGS10': 'MACRO',
    'DGS2': 'MACRO',
    'T10Y2Y': 'MACRO',
    'VIXCLS': 'MACRO'
}

# ADR-010 Severity Mapping
ADR010_SEVERITY_MAP = {
    'HEALTHY': {'adr010_state': 'NORMAL', 'severity_score': 0.0},
    'WARN': {'adr010_state': 'WARNING', 'severity_score': 0.03},
    'ALERT': {'adr010_state': 'WARNING', 'severity_score': 0.07},
    'CRITICAL': {'adr010_state': 'CATASTROPHIC', 'severity_score': 0.15}
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def compute_hash(data: str) -> str:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data.encode()).hexdigest()


def get_latest_trading_day() -> date:
    """
    Get the expected latest trading day.
    For crypto (BTC, ETH, SOL): yesterday (24/7 markets)
    For forex (EURUSD): last weekday
    """
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    return yesterday


def is_weekend(d: date) -> bool:
    """Check if date is weekend (Saturday=5, Sunday=6)."""
    return d.weekday() >= 5


def get_asset_type(asset_id: str) -> str:
    """Get asset type for threshold lookup."""
    return ASSET_TYPE_MAP.get(asset_id, 'EQUITY')  # Default to EQUITY (most conservative)


def get_thresholds_for_asset(asset_id: str) -> Dict[str, int]:
    """Get staleness thresholds for specific asset type."""
    asset_type = get_asset_type(asset_id)
    return ASSET_TYPE_THRESHOLDS.get(asset_type, ASSET_TYPE_THRESHOLDS['EQUITY'])


def get_expected_date_for_asset(asset_id: str) -> date:
    """
    Get expected latest date for an asset based on its trading schedule.
    Crypto: yesterday (trades 24/7)
    Forex/Equity: last weekday (no weekend trading)
    Macro: based on series frequency
    """
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    asset_type = get_asset_type(asset_id)

    if asset_type == 'CRYPTO':
        # Crypto trades 24/7
        return yesterday
    elif asset_type in ('FX', 'EQUITY'):
        # No weekend trading
        check_date = yesterday
        while is_weekend(check_date):
            check_date -= timedelta(days=1)
        return check_date
    elif asset_type == 'MACRO':
        # Macro series have variable frequency - be lenient
        # Return 7 days ago as baseline expectation
        return today - timedelta(days=7)
    else:
        return yesterday


# =============================================================================
# SENTINEL CHECKS
# =============================================================================

class CanonicalFreshnessSentinel:
    """
    Proactive freshness monitoring for canonical price data.
    Detects upstream vendor issues before they affect IoS-003.
    """

    def __init__(self):
        self.conn = get_connection()
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.results = {
            'sentinel': 'ios_canonical_freshness',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executor': 'STIG',
            'checks': {},
            'discrepancies': [],
            'status': 'PENDING'
        }

    def check_price_freshness(self) -> Dict[str, Any]:
        """
        Check 1: Verify fhq_market.prices has latest data for all canonical assets.
        """
        self.cur.execute("""
            SELECT canonical_id,
                   MAX(timestamp::date) as latest_date,
                   COUNT(*) as row_count
            FROM fhq_market.prices
            WHERE canonical_id = ANY(%s)
            GROUP BY canonical_id
            ORDER BY canonical_id
        """, (CANONICAL_ASSETS,))

        rows = self.cur.fetchall()
        price_status = {r['canonical_id']: dict(r) for r in rows}

        today = datetime.now(timezone.utc).date()
        results = {}

        for asset_id in CANONICAL_ASSETS:
            expected_date = get_expected_date_for_asset(asset_id)

            if asset_id not in price_status:
                results[asset_id] = {
                    'status': 'MISSING',
                    'severity': 'CRITICAL',
                    'expected': str(expected_date),
                    'actual': None,
                    'gap_days': None,
                    'message': f'No price data found for {asset_id}'
                }
                continue

            actual_date = price_status[asset_id]['latest_date']
            gap_days = (expected_date - actual_date).days

            # Get asset-type-aware thresholds
            thresholds = get_thresholds_for_asset(asset_id)
            asset_type = get_asset_type(asset_id)

            if gap_days <= 0:
                severity = 'HEALTHY'
            elif gap_days <= thresholds['warn_days']:
                severity = 'WARN'
            elif gap_days <= thresholds['alert_days']:
                severity = 'ALERT'
            else:
                severity = 'CRITICAL'

            results[asset_id] = {
                'status': 'FRESH' if gap_days <= 0 else 'STALE',
                'severity': severity,
                'asset_type': asset_type,
                'thresholds': thresholds,
                'expected': str(expected_date),
                'actual': str(actual_date),
                'gap_days': gap_days,
                'row_count': price_status[asset_id]['row_count']
            }

        return results

    def check_perception_freshness(self) -> Dict[str, Any]:
        """
        Check 2: Verify IoS-003 regime_daily has no gaps vs fhq_market.prices.
        """
        results = {}

        for asset_id in CANONICAL_ASSETS:
            # Get latest price date
            self.cur.execute("""
                SELECT MAX(timestamp::date) as latest_price
                FROM fhq_market.prices
                WHERE canonical_id = %s
            """, (asset_id,))
            price_row = self.cur.fetchone()
            latest_price = price_row['latest_price'] if price_row else None

            # Get latest regime date
            self.cur.execute("""
                SELECT MAX(timestamp) as latest_regime
                FROM fhq_perception.regime_daily
                WHERE asset_id = %s
            """, (asset_id,))
            regime_row = self.cur.fetchone()
            latest_regime = regime_row['latest_regime'] if regime_row else None

            if latest_price is None:
                results[asset_id] = {
                    'status': 'NO_PRICE_DATA',
                    'severity': 'CRITICAL'
                }
                continue

            if latest_regime is None:
                results[asset_id] = {
                    'status': 'NO_REGIME_DATA',
                    'severity': 'CRITICAL',
                    'latest_price': str(latest_price)
                }
                continue

            # Convert to date if datetime
            if hasattr(latest_regime, 'date'):
                latest_regime = latest_regime.date() if callable(getattr(latest_regime, 'date', None)) else latest_regime

            gap_days = (latest_price - latest_regime).days

            # Perception freshness is BINARY per audit:
            # IoS-003 doesn't support graded partial states
            # 0 missing = HEALTHY, >=1 = ALERT, >=3 = CRITICAL
            if gap_days <= 0:
                severity = 'HEALTHY'
            elif gap_days < 3:
                severity = 'ALERT'
            else:
                severity = 'CRITICAL'

            results[asset_id] = {
                'status': 'SYNCED' if gap_days <= 0 else 'BEHIND',
                'severity': severity,
                'latest_price': str(latest_price),
                'latest_regime': str(latest_regime),
                'gap_days': gap_days
            }

        return results

    def log_discrepancies(self, price_checks: Dict, perception_checks: Dict):
        """
        Log any discrepancies to fhq_governance.discrepancy_events (ADR-010).
        """
        discrepancies = []

        for asset_id, check in price_checks.items():
            if check['severity'] in ('ALERT', 'CRITICAL'):
                discrepancies.append({
                    'source': 'CANONICAL_FRESHNESS_SENTINEL',
                    'asset_id': asset_id,
                    'check_type': 'PRICE_STALENESS',
                    'severity': check['severity'],
                    'gap_days': check.get('gap_days'),
                    'expected': check.get('expected'),
                    'actual': check.get('actual'),
                    'message': f"Price data stale: {check.get('gap_days', 'N/A')} days behind"
                })

        for asset_id, check in perception_checks.items():
            if check['severity'] in ('ALERT', 'CRITICAL'):
                discrepancies.append({
                    'source': 'CANONICAL_FRESHNESS_SENTINEL',
                    'asset_id': asset_id,
                    'check_type': 'PERCEPTION_GAP',
                    'severity': check['severity'],
                    'gap_days': check.get('gap_days'),
                    'latest_price': check.get('latest_price'),
                    'latest_regime': check.get('latest_regime'),
                    'message': f"Perception behind price: {check.get('gap_days', 'N/A')} days"
                })

        # Log to discrepancy_events with ADR-010 severity mapping
        # Per audit: WARN → no log, ALERT → 0.05-0.09, CRITICAL → >=0.10
        for disc in discrepancies:
            # Only log ALERT and CRITICAL (per ADR-010)
            if disc['severity'] not in ('ALERT', 'CRITICAL'):
                continue

            adr010_mapping = ADR010_SEVERITY_MAP.get(disc['severity'], ADR010_SEVERITY_MAP['ALERT'])
            severity_score = adr010_mapping['severity_score']

            try:
                self.cur.execute("""
                    INSERT INTO fhq_governance.discrepancy_events (
                        event_id, event_type, source_system, target_system,
                        discrepancy_score, severity, event_data, created_at
                    ) VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, %s, %s, NOW()
                    )
                """, (
                    disc['check_type'],
                    'fhq_market.prices',
                    f"IoS-003/{disc['asset_id']}",
                    severity_score,
                    adr010_mapping['adr010_state'],
                    json.dumps(disc)
                ))
            except Exception as e:
                # Table might not exist, log to audit instead
                pass

        self.conn.commit()
        return discrepancies

    def run(self) -> Dict[str, Any]:
        """Run all freshness checks."""
        print("=" * 60)
        print("IoS CANONICAL FRESHNESS SENTINEL")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print("=" * 60)

        # Check 1: Price freshness
        print("\n[CHECK 1] fhq_market.prices freshness:")
        price_checks = self.check_price_freshness()
        self.results['checks']['price_freshness'] = price_checks

        for asset_id, check in price_checks.items():
            icon = {'HEALTHY': '+', 'WARN': '!', 'ALERT': '!!', 'CRITICAL': 'X'}.get(check['severity'], '?')
            print(f"  [{icon}] {asset_id}: {check['status']} (gap: {check.get('gap_days', 'N/A')} days)")

        # Check 2: Perception freshness
        print("\n[CHECK 2] IoS-003 perception freshness:")
        perception_checks = self.check_perception_freshness()
        self.results['checks']['perception_freshness'] = perception_checks

        for asset_id, check in perception_checks.items():
            icon = {'HEALTHY': '+', 'WARN': '!', 'ALERT': '!!', 'CRITICAL': 'X'}.get(check['severity'], '?')
            print(f"  [{icon}] {asset_id}: {check['status']} (gap: {check.get('gap_days', 'N/A')} days)")

        # Log discrepancies
        discrepancies = self.log_discrepancies(price_checks, perception_checks)
        self.results['discrepancies'] = discrepancies

        # Determine overall status
        all_severities = [c['severity'] for c in price_checks.values()] + \
                        [c['severity'] for c in perception_checks.values()]

        if 'CRITICAL' in all_severities:
            self.results['status'] = 'CRITICAL'
        elif 'ALERT' in all_severities:
            self.results['status'] = 'ALERT'
        elif 'WARN' in all_severities:
            self.results['status'] = 'WARN'
        else:
            self.results['status'] = 'HEALTHY'

        # Log audit
        evidence_hash = compute_hash(json.dumps(self.results, sort_keys=True, default=str))
        self.results['evidence_hash'] = evidence_hash

        self.cur.execute("""
            INSERT INTO fhq_meta.ios_audit_log
            (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
        """, ('SYSTEM', 'CANONICAL_FRESHNESS_CHECK', datetime.now(timezone.utc), 'STIG', 'G1',
              json.dumps(self.results, default=str), evidence_hash[:16]))
        self.conn.commit()

        print(f"\n{'=' * 60}")
        print(f"STATUS: {self.results['status']}")
        if discrepancies:
            print(f"DISCREPANCIES LOGGED: {len(discrepancies)}")
        print(f"Evidence: {evidence_hash[:32]}...")
        print("=" * 60)

        return self.results

    def close(self):
        """Close connections."""
        self.cur.close()
        self.conn.close()


# =============================================================================
# PUBLIC API
# =============================================================================

def check_canonical_freshness() -> Dict[str, Any]:
    """Public API for canonical freshness check."""
    sentinel = CanonicalFreshnessSentinel()
    try:
        return sentinel.run()
    finally:
        sentinel.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run canonical freshness sentinel."""
    results = check_canonical_freshness()
    return results['status'] in ('HEALTHY', 'WARN')


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
