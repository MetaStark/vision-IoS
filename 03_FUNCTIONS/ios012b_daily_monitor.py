#!/usr/bin/env python3
"""
IoS-012-B DAILY MONITORING DASHBOARD
====================================
Directive: CEO-DIR-2026-106
Date: 2026-01-19

Generates daily monitoring data for IoS-012-B shadow performance.
Outputs JSON section for inclusion in daily reports.

Run daily at 04:00 UTC (after market close outcome evaluation).
"""

import os
import json
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Hindsight firewall end date
NON_ELIGIBILITY_END = date(2026, 2, 2)

# G4 activation threshold
G4_HIT_RATE_THRESHOLD = 0.80


class DailyMonitor:
    """Daily monitoring dashboard for IoS-012-B shadow performance."""

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.report_date = date.today()

    def close(self):
        if self.conn:
            self.conn.close()

    def generate_dashboard(self) -> Dict[str, Any]:
        """Generate complete daily monitoring dashboard."""
        dashboard = {
            "section_id": "ios012b_shadow_monitor",
            "section_title": "IoS-012-B Alpha Inversion Shadow Monitor",
            "report_date": self.report_date.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "SHADOW_ONLY",

            "hindsight_firewall": self._get_firewall_status(),
            "signal_summary": self._get_signal_summary(),
            "performance_metrics": self._get_performance_metrics(),
            "ticker_breakdown": self._get_ticker_breakdown(),
            "health_status": self._get_health_status(),
            "g4_readiness": self._get_g4_readiness(),
            "action_items": self._get_action_items(),
            "evidence_hash": None  # Set after
        }

        # Generate evidence hash
        dashboard["evidence_hash"] = hashlib.sha256(
            json.dumps(dashboard, sort_keys=True, default=str).encode()
        ).hexdigest()[:32]

        return dashboard

    def _get_firewall_status(self) -> Dict[str, Any]:
        """Get hindsight firewall status."""
        days_remaining = max(0, (NON_ELIGIBILITY_END - self.report_date).days)
        return {
            "active": self.report_date < NON_ELIGIBILITY_END,
            "eligibility_date": NON_ELIGIBILITY_END.isoformat(),
            "days_remaining": days_remaining,
            "status": "SHADOW_ENFORCED" if days_remaining > 0 else "ELIGIBLE_FOR_G4"
        }

    def _get_signal_summary(self) -> Dict[str, Any]:
        """Get summary of shadow signals."""
        query = """
            SELECT
                COUNT(*) as total_signals,
                COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END) as evaluated,
                COUNT(CASE WHEN actual_outcome IS NULL THEN 1 END) as pending,
                COUNT(CASE WHEN actual_outcome = TRUE THEN 1 END) as correct,
                COUNT(CASE WHEN actual_outcome = FALSE THEN 1 END) as incorrect,
                MIN(entry_timestamp) as first_signal,
                MAX(entry_timestamp) as last_signal,
                COUNT(DISTINCT ticker) as unique_tickers
            FROM fhq_alpha.inversion_overlay_shadow
            WHERE is_shadow = TRUE
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            row = cur.fetchone()

        if not row:
            return {"total_signals": 0}

        total_eval = (row['correct'] or 0) + (row['incorrect'] or 0)
        hit_rate = row['correct'] / total_eval if total_eval > 0 else None

        return {
            "total_signals": row['total_signals'],
            "evaluated": row['evaluated'] or 0,
            "pending_evaluation": row['pending'] or 0,
            "correct_inversions": row['correct'] or 0,
            "incorrect_inversions": row['incorrect'] or 0,
            "inverted_hit_rate": float(hit_rate) if hit_rate else None,
            "inverted_hit_rate_pct": f"{hit_rate*100:.1f}%" if hit_rate else "N/A",
            "unique_tickers": row['unique_tickers'],
            "signal_window": {
                "first": str(row['first_signal']) if row['first_signal'] else None,
                "last": str(row['last_signal']) if row['last_signal'] else None
            }
        }

    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from system view."""
        query = "SELECT * FROM fhq_alpha.v_inversion_overlay_system_performance"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            row = cur.fetchone()

        if not row:
            return {"status": "NO_DATA"}

        return {
            "total_signals": row['total_signals'],
            "inverted_hit_rate_pct": self._safe_pct(row['inverted_hit_rate_pct']),
            "avg_inverted_brier": self._safe_float(row['avg_inverted_brier']),
            "health_status": row['health_status'],
            "all_shadow": row['all_shadow']
        }

    def _get_ticker_breakdown(self) -> List[Dict[str, Any]]:
        """Get per-ticker performance breakdown."""
        query = """
            SELECT
                ticker,
                COUNT(*) as signals,
                COUNT(CASE WHEN actual_outcome = TRUE THEN 1 END) as correct,
                COUNT(CASE WHEN actual_outcome = FALSE THEN 1 END) as incorrect,
                AVG(inverted_brier) as avg_brier
            FROM fhq_alpha.inversion_overlay_shadow
            WHERE is_shadow = TRUE
            GROUP BY ticker
            ORDER BY signals DESC
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

        result = []
        for row in rows:
            total_eval = (row['correct'] or 0) + (row['incorrect'] or 0)
            hit_rate = row['correct'] / total_eval if total_eval > 0 else None

            result.append({
                "ticker": row['ticker'],
                "total_signals": row['signals'],
                "correct": row['correct'] or 0,
                "incorrect": row['incorrect'] or 0,
                "hit_rate": f"{hit_rate*100:.1f}%" if hit_rate else "N/A",
                "avg_brier": self._safe_float(row['avg_brier'])
            })

        return result

    def _get_health_status(self) -> Dict[str, Any]:
        """Get dual-layer health status."""
        query = "SELECT * FROM fhq_alpha.check_inversion_health_v2(30)"
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            row = cur.fetchone()

        if not row:
            return {"status": "NO_DATA"}

        return {
            "directional_health": self._safe_pct(row['directional_health']),
            "pnl_health": self._safe_pct(row['pnl_health']),
            "health_status": row['health_status'],
            "should_disable": row['should_disable'],
            "recommendation": row['recommendation'],
            "total_signals": row['total_signals'],
            "closed_positions": row['closed_positions']
        }

    def _get_g4_readiness(self) -> Dict[str, Any]:
        """Assess G4 activation readiness."""
        firewall = self._get_firewall_status()
        summary = self._get_signal_summary()
        health = self._get_health_status()

        # Criteria checks
        firewall_clear = not firewall['active']
        hit_rate_met = (summary.get('inverted_hit_rate') or 0) >= G4_HIT_RATE_THRESHOLD
        health_ok = health.get('health_status') == 'HEALTHY'
        min_signals = (summary.get('evaluated') or 0) >= 10

        all_criteria_met = firewall_clear and hit_rate_met and health_ok and min_signals

        return {
            "g4_threshold": f"{G4_HIT_RATE_THRESHOLD*100:.0f}%",
            "criteria": {
                "hindsight_firewall_clear": {
                    "met": firewall_clear,
                    "value": "Yes" if firewall_clear else f"{firewall['days_remaining']} days remaining"
                },
                "hit_rate_threshold": {
                    "met": hit_rate_met,
                    "value": summary.get('inverted_hit_rate_pct', 'N/A'),
                    "required": f">= {G4_HIT_RATE_THRESHOLD*100:.0f}%"
                },
                "health_status": {
                    "met": health_ok,
                    "value": health.get('health_status', 'UNKNOWN')
                },
                "minimum_signals": {
                    "met": min_signals,
                    "value": summary.get('evaluated', 0),
                    "required": ">= 10"
                }
            },
            "g4_eligible": all_criteria_met,
            "recommendation": "READY_FOR_G4_SUBMISSION" if all_criteria_met else "CONTINUE_SHADOW_MONITORING"
        }

    def _get_action_items(self) -> List[Dict[str, str]]:
        """Generate action items based on current state."""
        items = []

        firewall = self._get_firewall_status()
        if firewall['active']:
            items.append({
                "priority": "INFO",
                "action": f"Hindsight firewall active. {firewall['days_remaining']} days until G4 eligibility."
            })

        summary = self._get_signal_summary()
        if summary.get('pending_evaluation', 0) > 0:
            items.append({
                "priority": "ROUTINE",
                "action": f"Evaluate {summary['pending_evaluation']} pending signals (T+1 outcomes)"
            })

        if (summary.get('evaluated') or 0) < 10:
            items.append({
                "priority": "INFO",
                "action": f"Need {10 - (summary.get('evaluated') or 0)} more evaluated signals for health assessment"
            })

        health = self._get_health_status()
        if health.get('should_disable'):
            items.append({
                "priority": "CRITICAL",
                "action": "AUTO-DISABLE triggered. P&L breach detected. Manual review required."
            })

        if not items:
            items.append({
                "priority": "OK",
                "action": "Shadow monitoring operational. Continue daily measurement."
            })

        return items

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert to float."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

    def _safe_pct(self, value) -> Optional[str]:
        """Safely format as percentage."""
        if value is None:
            return None
        return f"{float(value)*100:.1f}%"

    def save_dashboard(self, dashboard: Dict[str, Any]) -> str:
        """Save dashboard to evidence file."""
        filepath = os.path.join(
            os.path.dirname(__file__),
            'evidence',
            f"IOS012B_DAILY_MONITOR_{self.report_date.strftime('%Y%m%d')}.json"
        )

        with open(filepath, 'w') as f:
            json.dump(dashboard, f, indent=2, default=str)

        return filepath


def main():
    """Generate and display daily monitoring dashboard."""
    monitor = DailyMonitor()
    try:
        print("=" * 60)
        print("IoS-012-B DAILY SHADOW MONITOR")
        print(f"Report Date: {monitor.report_date}")
        print("=" * 60)

        dashboard = monitor.generate_dashboard()

        # Print summary
        print(f"\n[FIREWALL STATUS] {dashboard['hindsight_firewall']['status']}")
        print(f"  Days remaining: {dashboard['hindsight_firewall']['days_remaining']}")

        print(f"\n[SIGNAL SUMMARY]")
        sig = dashboard['signal_summary']
        print(f"  Total signals: {sig['total_signals']}")
        print(f"  Evaluated: {sig['evaluated']}")
        print(f"  Hit rate: {sig['inverted_hit_rate_pct']}")

        print(f"\n[HEALTH STATUS]")
        health = dashboard['health_status']
        print(f"  Status: {health.get('health_status', 'N/A')}")
        print(f"  Directional: {health.get('directional_health', 'N/A')}")

        print(f"\n[G4 READINESS]")
        g4 = dashboard['g4_readiness']
        print(f"  Eligible: {g4['g4_eligible']}")
        print(f"  Recommendation: {g4['recommendation']}")

        print(f"\n[ACTION ITEMS]")
        for item in dashboard['action_items']:
            print(f"  [{item['priority']}] {item['action']}")

        # Save
        filepath = monitor.save_dashboard(dashboard)
        print(f"\nDashboard saved: {filepath}")

        # Print full JSON for daily report inclusion
        print("\n" + "=" * 60)
        print("DAILY REPORT SECTION (copy to daily report):")
        print("=" * 60)
        print(json.dumps(dashboard, indent=2, default=str))

        return dashboard

    finally:
        monitor.close()


if __name__ == '__main__':
    main()
