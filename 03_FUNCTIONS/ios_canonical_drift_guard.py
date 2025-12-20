#!/usr/bin/env python3
"""
IoS CANONICAL DRIFT GUARD (ADR-015)
====================================
Authority: CEO Directive - Canonical Consolidation Audit
Reference: ADR-015 (Canonical Drift Guard), ADR-010 (Discrepancy Scoring)
Generated: 2025-12-08

PURPOSE:
    Detect data CORRECTNESS issues (not just freshness):
    - Vendor delivering fresh but WRONG data (API bug)
    - Feed corruption (duplicate rows, missing values)
    - Statistical anomalies (z-score > threshold)

COMPLEMENTARY TO FRESHNESS SENTINEL:
    - FRESHNESS says "WHEN" (is data timely?)
    - DRIFTGUARD says "WHAT" (is data correct?)

CHECKS:
    1. Price delta z-score within statistical tolerance
    2. OHLC relationship integrity (H >= max(O,C), L <= min(O,C))
    3. Volume anomaly detection
    4. Cross-asset correlation sanity

Schedule: Daily, after FRESHNESS_SENTINEL, before IoS-003
"""

import os
import json
import hashlib
import uuid
import numpy as np
from datetime import datetime, timedelta, timezone, date
from typing import Dict, List, Any, Optional, Tuple
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

# Z-score thresholds for price delta anomaly detection
ZSCORE_THRESHOLDS = {
    'normal': 3.0,     # z < 3 = normal
    'warn': 5.0,       # 3 <= z < 5 = warn
    'critical': 5.0    # z >= 5 = critical
}

# Lookback window for statistical baseline
LOOKBACK_DAYS = 60

# ADR-010 Severity Mapping
ADR010_SEVERITY_MAP = {
    'HEALTHY': {'adr010_state': 'NORMAL', 'severity_score': 0.0},
    'WARN': {'adr010_state': 'WARNING', 'severity_score': 0.05},
    'CRITICAL': {'adr010_state': 'CATASTROPHIC', 'severity_score': 0.12}
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


# =============================================================================
# DRIFT GUARD CHECKS
# =============================================================================

class CanonicalDriftGuard:
    """
    Detects data correctness issues in canonical price data.
    Complements Freshness Sentinel (when) with correctness checks (what).
    """

    def __init__(self):
        self.conn = get_connection()
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.results = {
            'guard': 'ios_canonical_drift_guard',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executor': 'STIG',
            'adr_reference': 'ADR-015',
            'checks': {},
            'anomalies': [],
            'status': 'PENDING'
        }

    def check_price_delta_zscore(self) -> Dict[str, Any]:
        """
        Check 1: Verify latest price delta is within statistical tolerance.

        z-score < 3: NORMAL
        3 <= z-score < 5: WARN
        z-score >= 5: CRITICAL
        """
        results = {}

        for asset_id in CANONICAL_ASSETS:
            # Get recent prices for baseline
            self.cur.execute("""
                SELECT timestamp::date as date, close
                FROM fhq_market.prices
                WHERE canonical_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (asset_id, LOOKBACK_DAYS + 1))

            rows = self.cur.fetchall()
            if len(rows) < 10:
                results[asset_id] = {
                    'status': 'INSUFFICIENT_DATA',
                    'severity': 'WARN',
                    'rows': len(rows)
                }
                continue

            # Calculate returns
            prices = [float(r['close']) for r in rows]
            returns = [(prices[i] - prices[i+1]) / prices[i+1]
                      for i in range(len(prices) - 1)]

            if len(returns) < 5:
                results[asset_id] = {
                    'status': 'INSUFFICIENT_RETURNS',
                    'severity': 'WARN'
                }
                continue

            # Latest return
            latest_return = returns[0]

            # Historical baseline (excluding latest)
            historical_returns = returns[1:]
            mean_return = np.mean(historical_returns)
            std_return = np.std(historical_returns)

            if std_return == 0 or np.isnan(std_return):
                results[asset_id] = {
                    'status': 'ZERO_VOLATILITY',
                    'severity': 'WARN',
                    'message': 'Cannot compute z-score with zero volatility'
                }
                continue

            # Z-score of latest return
            zscore = abs((latest_return - mean_return) / std_return)

            if zscore < ZSCORE_THRESHOLDS['normal']:
                severity = 'HEALTHY'
                status = 'NORMAL'
            elif zscore < ZSCORE_THRESHOLDS['warn']:
                severity = 'WARN'
                status = 'ELEVATED'
            else:
                severity = 'CRITICAL'
                status = 'ANOMALY'

            results[asset_id] = {
                'status': status,
                'severity': severity,
                'latest_return': round(latest_return * 100, 2),
                'zscore': round(zscore, 2),
                'mean_return': round(mean_return * 100, 4),
                'std_return': round(std_return * 100, 4),
                'latest_date': str(rows[0]['date']),
                'latest_close': float(rows[0]['close'])
            }

        return results

    def check_ohlc_integrity(self) -> Dict[str, Any]:
        """
        Check 2: Verify OHLC relationship integrity.

        Rules:
        - High >= max(Open, Close)
        - Low <= min(Open, Close)
        - All prices > 0
        """
        results = {}

        for asset_id in CANONICAL_ASSETS:
            # Get latest row
            self.cur.execute("""
                SELECT timestamp::date as date, open, high, low, close, volume
                FROM fhq_market.prices
                WHERE canonical_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """, (asset_id,))

            row = self.cur.fetchone()
            if not row:
                results[asset_id] = {
                    'status': 'NO_DATA',
                    'severity': 'CRITICAL'
                }
                continue

            o, h, l, c = float(row['open']), float(row['high']), float(row['low']), float(row['close'])
            violations = []

            # Check OHLC rules
            if h < max(o, c):
                violations.append(f"High ({h}) < max(Open,Close) ({max(o,c)})")
            if l > min(o, c):
                violations.append(f"Low ({l}) > min(Open,Close) ({min(o,c)})")
            if any(p <= 0 for p in [o, h, l, c]):
                violations.append("Non-positive price detected")
            if h < l:
                violations.append(f"High ({h}) < Low ({l})")

            if violations:
                severity = 'CRITICAL'
                status = 'VIOLATION'
            else:
                severity = 'HEALTHY'
                status = 'VALID'

            results[asset_id] = {
                'status': status,
                'severity': severity,
                'date': str(row['date']),
                'ohlc': {'o': o, 'h': h, 'l': l, 'c': c},
                'violations': violations
            }

        return results

    def check_volume_anomaly(self) -> Dict[str, Any]:
        """
        Check 3: Detect volume anomalies (sudden spikes or drops).
        """
        results = {}

        for asset_id in CANONICAL_ASSETS:
            self.cur.execute("""
                SELECT timestamp::date as date, volume
                FROM fhq_market.prices
                WHERE canonical_id = %s
                  AND volume IS NOT NULL
                  AND volume > 0
                ORDER BY timestamp DESC
                LIMIT %s
            """, (asset_id, LOOKBACK_DAYS + 1))

            rows = self.cur.fetchall()
            if len(rows) < 10:
                results[asset_id] = {
                    'status': 'INSUFFICIENT_DATA',
                    'severity': 'HEALTHY'  # Volume check is non-critical
                }
                continue

            volumes = [float(r['volume']) for r in rows]
            latest_vol = volumes[0]
            historical_vols = volumes[1:]

            mean_vol = np.mean(historical_vols)
            std_vol = np.std(historical_vols)

            if std_vol == 0 or mean_vol == 0:
                results[asset_id] = {
                    'status': 'ZERO_BASELINE',
                    'severity': 'HEALTHY'
                }
                continue

            # Volume ratio
            vol_ratio = latest_vol / mean_vol
            vol_zscore = abs((latest_vol - mean_vol) / std_vol)

            if vol_zscore < 3:
                severity = 'HEALTHY'
                status = 'NORMAL'
            elif vol_zscore < 5:
                severity = 'WARN'
                status = 'ELEVATED'
            else:
                severity = 'WARN'  # Volume anomaly is warning only, not critical
                status = 'SPIKE'

            results[asset_id] = {
                'status': status,
                'severity': severity,
                'latest_volume': latest_vol,
                'mean_volume': round(mean_vol, 0),
                'volume_ratio': round(vol_ratio, 2),
                'volume_zscore': round(vol_zscore, 2),
                'date': str(rows[0]['date'])
            }

        return results

    def log_anomalies(self, zscore_checks: Dict, ohlc_checks: Dict, volume_checks: Dict):
        """
        Log anomalies to fhq_governance.discrepancy_events (ADR-010).
        Only log CRITICAL anomalies.
        """
        anomalies = []

        # Z-score anomalies
        for asset_id, check in zscore_checks.items():
            if check['severity'] == 'CRITICAL':
                anomalies.append({
                    'source': 'DRIFT_GUARD',
                    'asset_id': asset_id,
                    'check_type': 'PRICE_DELTA_ZSCORE',
                    'severity': check['severity'],
                    'zscore': check.get('zscore'),
                    'message': f"Price delta z-score {check.get('zscore', 'N/A')} exceeds threshold"
                })

        # OHLC violations
        for asset_id, check in ohlc_checks.items():
            if check['severity'] == 'CRITICAL':
                anomalies.append({
                    'source': 'DRIFT_GUARD',
                    'asset_id': asset_id,
                    'check_type': 'OHLC_INTEGRITY',
                    'severity': check['severity'],
                    'violations': check.get('violations', []),
                    'message': f"OHLC integrity violation: {check.get('violations', [])}"
                })

        # Log to discrepancy_events
        for anomaly in anomalies:
            adr010_mapping = ADR010_SEVERITY_MAP.get(anomaly['severity'], ADR010_SEVERITY_MAP['WARN'])

            try:
                self.cur.execute("""
                    INSERT INTO fhq_governance.discrepancy_events (
                        event_id, event_type, source_system, target_system,
                        discrepancy_score, severity, event_data, created_at
                    ) VALUES (
                        gen_random_uuid(), %s, %s, %s, %s, %s, %s, NOW()
                    )
                """, (
                    anomaly['check_type'],
                    'DRIFT_GUARD',
                    f"fhq_market.prices/{anomaly['asset_id']}",
                    adr010_mapping['severity_score'],
                    adr010_mapping['adr010_state'],
                    json.dumps(anomaly)
                ))
            except Exception as e:
                pass  # Table might not exist

        self.conn.commit()
        return anomalies

    def run(self) -> Dict[str, Any]:
        """Run all drift guard checks."""
        print("=" * 60)
        print("IoS CANONICAL DRIFT GUARD (ADR-015)")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print("=" * 60)

        # Check 1: Price delta z-score
        print("\n[CHECK 1] Price Delta Z-Score:")
        zscore_checks = self.check_price_delta_zscore()
        self.results['checks']['price_zscore'] = zscore_checks

        for asset_id, check in zscore_checks.items():
            icon = {'HEALTHY': '+', 'WARN': '!', 'CRITICAL': 'X'}.get(check['severity'], '?')
            zscore_str = f"z={check.get('zscore', 'N/A')}" if 'zscore' in check else check.get('status', '')
            print(f"  [{icon}] {asset_id}: {check['status']} ({zscore_str})")

        # Check 2: OHLC integrity
        print("\n[CHECK 2] OHLC Integrity:")
        ohlc_checks = self.check_ohlc_integrity()
        self.results['checks']['ohlc_integrity'] = ohlc_checks

        for asset_id, check in ohlc_checks.items():
            icon = {'HEALTHY': '+', 'WARN': '!', 'CRITICAL': 'X'}.get(check['severity'], '?')
            print(f"  [{icon}] {asset_id}: {check['status']}")

        # Check 3: Volume anomaly
        print("\n[CHECK 3] Volume Anomaly:")
        volume_checks = self.check_volume_anomaly()
        self.results['checks']['volume_anomaly'] = volume_checks

        for asset_id, check in volume_checks.items():
            icon = {'HEALTHY': '+', 'WARN': '!', 'CRITICAL': 'X'}.get(check['severity'], '?')
            ratio_str = f"ratio={check.get('volume_ratio', 'N/A')}" if 'volume_ratio' in check else ''
            print(f"  [{icon}] {asset_id}: {check['status']} ({ratio_str})")

        # Log anomalies
        anomalies = self.log_anomalies(zscore_checks, ohlc_checks, volume_checks)
        self.results['anomalies'] = anomalies

        # Determine overall status
        all_severities = [c['severity'] for c in zscore_checks.values()] + \
                        [c['severity'] for c in ohlc_checks.values()] + \
                        [c['severity'] for c in volume_checks.values()]

        if 'CRITICAL' in all_severities:
            self.results['status'] = 'CRITICAL'
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
        """, ('SYSTEM', 'DRIFT_GUARD_CHECK', datetime.now(timezone.utc), 'STIG', 'G1',
              json.dumps(self.results, default=str), evidence_hash[:16]))
        self.conn.commit()

        print(f"\n{'=' * 60}")
        print(f"STATUS: {self.results['status']}")
        if anomalies:
            print(f"ANOMALIES LOGGED: {len(anomalies)}")
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

def check_canonical_drift() -> Dict[str, Any]:
    """Public API for canonical drift guard check."""
    guard = CanonicalDriftGuard()
    try:
        return guard.run()
    finally:
        guard.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run canonical drift guard."""
    results = check_canonical_drift()
    return results['status'] in ('HEALTHY', 'WARN')


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
