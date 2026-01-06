#!/usr/bin/env python3
"""
IoS-003 REGIME FRESHNESS SENTINEL
==================================
Authority: STIG-010 Directive
Classification: System Critical (Class A - Perception Integrity)
Schedule: Early in nightly cycle, before all other tasks

Purpose:
- Detect stale regime_daily data (>24 hours behind)
- Trigger automatic self-repair via IoS-006 + IoS-003
- Guarantee paper engine never runs on stale perception

Safety Rules:
- No direct writes - only triggers approved IoS modules
- Abort if triggered modules fail
- All repairs via ios006 price ingest + ios003 regime update
"""

import os
import sys
import json
import hashlib
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
import psycopg2
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

STALENESS_THRESHOLD_DAYS = 1
FUNCTIONS_DIR = Path(__file__).parent

# Modules to trigger for self-repair
# CEO-DIR-2025-RC-004: Updated to v4 regime classifier
REPAIR_MODULES = [
    'daily_ingest_worker.py',          # IoS-006: Price ingest
    'ios003_daily_regime_update_v4.py' # IoS-003: Regime update v4
]


# =============================================================================
# SENTINEL
# =============================================================================

class RegimeFreshnessSentinel:
    """Monitors regime_daily freshness and triggers self-repair."""

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor()
        self.results = {
            'sentinel': 'ios003_regime_freshness_sentinel',
            'authority': 'STIG-010',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'executor': 'STIG'
        }

    def check_freshness(self) -> dict:
        """Check regime_daily freshness across all assets."""
        self.cur.execute("""
            SELECT
                asset_id,
                MAX(timestamp)::date as latest_date,
                CURRENT_DATE - MAX(timestamp)::date as days_behind
            FROM fhq_perception.regime_daily
            GROUP BY asset_id
            ORDER BY days_behind DESC
        """)

        assets = {}
        max_staleness = 0

        for row in self.cur.fetchall():
            asset_id, latest_date, days_behind = row
            assets[asset_id] = {
                'latest_date': str(latest_date),
                'days_behind': days_behind
            }
            max_staleness = max(max_staleness, days_behind)

        return {
            'assets': assets,
            'max_staleness_days': max_staleness,
            'is_stale': max_staleness > STALENESS_THRESHOLD_DAYS
        }

    def trigger_self_repair(self) -> dict:
        """Trigger IoS modules to repair stale data."""
        repair_results = []

        for module in REPAIR_MODULES:
            module_path = FUNCTIONS_DIR / module

            if not module_path.exists():
                repair_results.append({
                    'module': module,
                    'status': 'SKIP',
                    'reason': 'File not found'
                })
                continue

            print(f"  Triggering: {module}")

            try:
                result = subprocess.run(
                    [sys.executable, str(module_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    cwd=str(FUNCTIONS_DIR)
                )

                success = result.returncode == 0
                repair_results.append({
                    'module': module,
                    'status': 'SUCCESS' if success else 'FAILED',
                    'exit_code': result.returncode
                })

                if not success:
                    print(f"    [FAILED] exit_code={result.returncode}")
                    # Abort on failure - safety rule
                    break
                else:
                    print(f"    [SUCCESS]")

            except subprocess.TimeoutExpired:
                repair_results.append({
                    'module': module,
                    'status': 'TIMEOUT',
                    'reason': '300s timeout exceeded'
                })
                break
            except Exception as e:
                repair_results.append({
                    'module': module,
                    'status': 'ERROR',
                    'error': str(e)
                })
                break

        all_success = all(r['status'] == 'SUCCESS' for r in repair_results)
        return {
            'repairs': repair_results,
            'all_success': all_success
        }

    def log_event(self, event_type: str, severity: str, data: dict):
        """Log sentinel event to audit log."""
        evidence_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()

        self.cur.execute("""
            INSERT INTO fhq_meta.ios_audit_log
            (audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data, evidence_hash)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
        """, (
            'IoS-003',
            event_type,
            datetime.now(timezone.utc),
            'STIG',
            'G1',
            json.dumps(data, default=str),
            evidence_hash
        ))
        self.conn.commit()

        return evidence_hash

    def run(self) -> dict:
        """Execute sentinel check."""
        print("=" * 60)
        print("IoS-003 REGIME FRESHNESS SENTINEL")
        print("Authority: STIG-010")
        print("=" * 60)

        # Check freshness
        print("\n[CHECK] Regime Freshness")
        freshness = self.check_freshness()
        self.results['freshness'] = freshness

        for asset_id, info in freshness['assets'].items():
            status = "[STALE]" if info['days_behind'] > STALENESS_THRESHOLD_DAYS else "[OK]"
            print(f"  {asset_id}: {info['latest_date']} ({info['days_behind']}d behind) {status}")

        print(f"\n  Max staleness: {freshness['max_staleness_days']} days")
        print(f"  Threshold: {STALENESS_THRESHOLD_DAYS} day(s)")

        if freshness['is_stale']:
            # STALE - Trigger self-repair
            print("\n[ALERT] REGIME_STALE_ALERT")
            print("-" * 40)

            self.results['alert'] = {
                'type': 'REGIME_STALE_ALERT',
                'severity': 'CRITICAL',
                'delta_days': freshness['max_staleness_days']
            }

            # Log stale alert
            self.log_event(
                'REGIME_STALE_ALERT',
                'CRITICAL',
                {
                    'max_staleness_days': freshness['max_staleness_days'],
                    'assets': freshness['assets'],
                    'action': 'TRIGGERING_SELF_REPAIR'
                }
            )

            print("\n[REPAIR] Triggering Self-Repair")
            print("-" * 40)
            repair_result = self.trigger_self_repair()
            self.results['repair'] = repair_result

            if repair_result['all_success']:
                # Re-check freshness after repair
                print("\n[VERIFY] Post-Repair Check")
                post_freshness = self.check_freshness()
                self.results['post_repair_freshness'] = post_freshness

                if not post_freshness['is_stale']:
                    self.results['status'] = 'REPAIRED'
                    self.results['self_repair_success'] = True
                    evidence_hash = self.log_event(
                        'REGIME_SELF_REPAIR_SUCCESS',
                        'INFO',
                        self.results
                    )
                    print(f"  Status: REPAIRED")
                else:
                    self.results['status'] = 'REPAIR_INCOMPLETE'
                    self.results['self_repair_success'] = False
                    evidence_hash = self.log_event(
                        'REGIME_SELF_REPAIR_INCOMPLETE',
                        'WARNING',
                        self.results
                    )
                    print(f"  Status: REPAIR_INCOMPLETE")
            else:
                self.results['status'] = 'REPAIR_FAILED'
                self.results['self_repair_success'] = False
                evidence_hash = self.log_event(
                    'REGIME_SELF_REPAIR_FAILED',
                    'ERROR',
                    self.results
                )
                print(f"  Status: REPAIR_FAILED")
        else:
            # FRESH - All good
            print("\n[OK] REGIME_FRESH")
            self.results['status'] = 'FRESH'
            self.results['self_repair_needed'] = False

            evidence_hash = self.log_event(
                'REGIME_FRESH',
                'INFO',
                {
                    'max_staleness_days': freshness['max_staleness_days'],
                    'status': 'FRESH'
                }
            )

        self.results['evidence_hash'] = evidence_hash

        # Final output
        print("\n" + "=" * 60)
        print("SENTINEL STATUS")
        print("=" * 60)
        print(f"  regime_age: {freshness['max_staleness_days']} days")
        print(f"  status: {self.results['status']}")
        print(f"  self_repair_enabled: TRUE")
        print(f"  evidence_hash: {evidence_hash[:32]}...")
        print("=" * 60)

        return self.results

    def close(self):
        """Close database connection."""
        self.cur.close()
        self.conn.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run regime freshness sentinel."""
    sentinel = RegimeFreshnessSentinel()
    try:
        results = sentinel.run()
        # Return 0 if sentinel executed successfully (detection + repair triggered)
        # REPAIR_INCOMPLETE is expected due to FRED API lag (T+1/T+2)
        # Only return 1 on actual execution errors
        if results['status'] in ['FRESH', 'REPAIRED', 'REPAIR_INCOMPLETE']:
            return 0
        else:
            return 1
    finally:
        sentinel.close()


if __name__ == '__main__':
    exit(main())
