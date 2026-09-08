#!/usr/bin/env python3
"""
SHADOW Window Monitor - CEO-DIR-2026-112
Monitors the 48h SHADOW learning lockdown window and updates the daily report.
Triggers post-lockdown actions when window expires.

Author: STIG
"""

import psycopg2
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

class ShadowWindowMonitor:
    """
    Monitors CEO-DIR-2026-112 48h SHADOW window.
    Updates daily report with real-time status.
    Triggers post-lockdown actions on expiry.
    """

    def __init__(self, db_conn):
        self.conn = db_conn
        self.conn.autocommit = True
        self.cur = db_conn.cursor()
        self.daily_report_path = Path(__file__).parent.parent / "12_DAILY_REPORTS"

    def get_window_status(self) -> Dict[str, Any]:
        """Get current SHADOW window status from database."""
        self.cur.execute('''
            SELECT
                lockdown_id,
                directive_reference,
                lockdown_started_at,
                lockdown_ends_at,
                lockdown_duration_hours,
                lockdown_status,
                violations_detected,
                hours_remaining,
                hours_elapsed,
                progress_percent,
                computed_status,
                window_expired,
                success_criteria
            FROM fhq_governance.v_shadow_window_status
        ''')

        row = self.cur.fetchone()
        if not row:
            return {'error': 'No active lockdown found'}

        return {
            'lockdown_id': str(row[0]),
            'directive': row[1],
            'started_at': row[2].isoformat() if row[2] else None,
            'ends_at': row[3].isoformat() if row[3] else None,
            'duration_hours': row[4],
            'status': row[5],
            'violations_detected': row[6],
            'hours_remaining': float(row[7]) if row[7] else 0,
            'hours_elapsed': float(row[8]) if row[8] else 0,
            'progress_percent': float(row[9]) if row[9] else 0,
            'computed_status': row[10],
            'window_expired': row[11],
            'success_criteria': row[12]
        }

    def get_learning_summary(self) -> Dict[str, Any]:
        """Get learning summary from database."""
        self.cur.execute('SELECT * FROM fhq_research.v_learning_summary')
        row = self.cur.fetchone()

        if not row:
            return {
                'total_evaluations': 0,
                'accepted_count': 0,
                'blocked_count': 0
            }

        return {
            'total_evaluations': row[0],
            'accepted_count': row[1],
            'blocked_count': row[2],
            'inversion_candidates': row[3],
            'friction_events': row[4],
            'calibration_events': row[5],
            'avg_slippage_saved_bps': float(row[6]) if row[6] else 0,
            'avg_confidence': float(row[7]) if row[7] else 0,
            'ttl_compliance_rate': float(row[8]) if row[8] else 0,
            'first_evaluation': row[9].isoformat() if row[9] else None,
            'last_evaluation': row[10].isoformat() if row[10] else None
        }

    def get_signal_flow_stats(self) -> Dict[str, Any]:
        """Get signal flow statistics."""
        self.cur.execute('SELECT * FROM fhq_research.v_signal_flow_statistics')
        row = self.cur.fetchone()

        if not row:
            return {'total_signals': 0}

        return {
            'total_signals': row[0],
            'accepted_count': row[1],
            'refused_count': row[2],
            'pending_count': row[3],
            'expired_count': row[4],
            'median_latency_seconds': float(row[5]) if row[5] else None,
            'max_latency_seconds': float(row[6]) if row[6] else None,
            'freshness_rate': float(row[9]) if row[9] else 0  # Index 9, not 10
        }

    def check_success_criteria(self, window_status: Dict) -> Dict[str, Any]:
        """Evaluate success criteria against current state."""
        learning = self.get_learning_summary()
        flow = self.get_signal_flow_stats()

        criteria = {
            'calibration_curve_exists': {
                'status': 'PENDING',
                'note': 'Awaiting UMA delivery at 18:00 UTC'
            },
            'signal_to_cpto_verified': {
                'status': 'VERIFIED' if flow['total_signals'] > 0 else 'PENDING',
                'count': flow['total_signals']
            },
            'median_freshness_under_5min': {
                'status': 'VERIFIED' if flow.get('median_latency_seconds', 999) < 300 else 'PENDING',
                'median_seconds': flow.get('median_latency_seconds')
            },
            'learning_data_accepted': {
                'status': 'VERIFIED' if learning['accepted_count'] > 0 else 'PENDING',
                'count': learning['accepted_count']
            },
            'learning_data_refused': {
                'status': 'VERIFIED' if learning['blocked_count'] > 0 else 'PENDING',
                'count': learning['blocked_count']
            },
            'no_parameters_changed': {
                'status': 'VERIFIED' if window_status['violations_detected'] == 0 else 'VIOLATED',
                'violations': window_status['violations_detected']
            }
        }

        return criteria

    def handle_window_expiry(self) -> Dict[str, Any]:
        """Handle post-lockdown actions when window expires."""
        print('[SHADOW WINDOW EXPIRED]')
        print('Executing post-lockdown actions...')

        # Update lockdown status
        self.cur.execute('''
            UPDATE fhq_governance.shadow_lockdown_config
            SET lockdown_status = 'EXPIRED',
                updated_at = NOW()
            WHERE is_current = true
            AND lockdown_status = 'ACTIVE'
        ''')

        # Generate final summary
        learning = self.get_learning_summary()
        flow = self.get_signal_flow_stats()

        return {
            'action': 'WINDOW_EXPIRED',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'final_summary': {
                'total_evaluations': learning['total_evaluations'],
                'accepted': learning['accepted_count'],
                'blocked': learning['blocked_count'],
                'avg_slippage_saved_bps': learning['avg_slippage_saved_bps'],
                'signal_flow_total': flow['total_signals'],
                'freshness_rate': flow['freshness_rate']
            },
            'next_steps': [
                'Generate final calibration curve',
                'Compile G4 attestation package',
                'CEO decision: SHADOW → PAPER transition'
            ]
        }

    def update_daily_report(self) -> Dict[str, Any]:
        """Update the daily report with current SHADOW window status."""
        window = self.get_window_status()
        learning = self.get_learning_summary()
        flow = self.get_signal_flow_stats()
        criteria = self.check_success_criteria(window)

        # Check for expiry
        if window.get('window_expired'):
            expiry_result = self.handle_window_expiry()
            window['expiry_action'] = expiry_result

        # Find current daily report
        today = datetime.now().strftime('%Y%m%d')
        day_num = (datetime.now() - datetime(2026, 1, 1)).days + 1
        report_file = self.daily_report_path / f"DAILY_REPORT_DAY{day_num}_{today}.json"

        if report_file.exists():
            with open(report_file, 'r') as f:
                report = json.load(f)

            # Update SHADOW lockdown section
            report['SHADOW_LOCKDOWN_STATUS']['hours_remaining'] = window['hours_remaining']
            report['SHADOW_LOCKDOWN_STATUS']['progress_percent'] = window['progress_percent']
            report['SHADOW_LOCKDOWN_STATUS']['status'] = window['computed_status']
            report['SHADOW_LOCKDOWN_STATUS']['violations_detected'] = window['violations_detected']
            report['SHADOW_LOCKDOWN_STATUS']['success_criteria_tracking'] = criteria
            report['SHADOW_LOCKDOWN_STATUS']['last_updated'] = datetime.now(timezone.utc).isoformat()

            # Update learning metrics
            report['LEARNING_METRICS']['summary'] = {
                'total_evaluations': learning['total_evaluations'],
                'accepted': learning['accepted_count'],
                'blocked': learning['blocked_count'],
                'avg_slippage_saved_bps': learning['avg_slippage_saved_bps'],
                'avg_confidence': learning['avg_confidence'],
                'ttl_compliance_rate': learning['ttl_compliance_rate']
            }

            # Update signal flow stats
            report['MANDATE_B_SIGNAL_FLOW_VERIFICATION']['pipeline_verification']['q2_latency_statistics']['median_latency_seconds'] = flow.get('median_latency_seconds')
            report['MANDATE_B_SIGNAL_FLOW_VERIFICATION']['freshness_kpi']['current_rate'] = flow.get('freshness_rate', 0)
            report['MANDATE_B_SIGNAL_FLOW_VERIFICATION']['freshness_kpi']['samples'] = flow.get('total_signals', 0)

            report['updated_at'] = datetime.now(timezone.utc).isoformat()

            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)

            print(f'[DAILY REPORT UPDATED] {report_file.name}')

        return {
            'window_status': window,
            'learning_summary': learning,
            'signal_flow': flow,
            'success_criteria': criteria,
            'report_updated': report_file.exists()
        }

    def run_check(self) -> Dict[str, Any]:
        """Run a single check of the SHADOW window status."""
        print('=' * 60)
        print('CEO-DIR-2026-112 SHADOW WINDOW MONITOR')
        print('=' * 60)

        window = self.get_window_status()

        print(f'\n[WINDOW STATUS]')
        print(f'  Directive: {window["directive"]}')
        print(f'  Status: {window["computed_status"]}')
        print(f'  Hours Remaining: {window["hours_remaining"]:.2f}')
        print(f'  Progress: {window["progress_percent"]:.2f}%')
        print(f'  Violations: {window["violations_detected"]}')

        if window.get('window_expired'):
            print(f'\n  *** WINDOW EXPIRED ***')

        learning = self.get_learning_summary()
        print(f'\n[LEARNING SUMMARY]')
        print(f'  Total Evaluations: {learning["total_evaluations"]}')
        print(f'  Accepted: {learning["accepted_count"]}')
        print(f'  Blocked: {learning["blocked_count"]}')
        print(f'  Avg Slippage Saved: {learning["avg_slippage_saved_bps"]:.2f} bps')

        criteria = self.check_success_criteria(window)
        print(f'\n[SUCCESS CRITERIA]')
        for name, status in criteria.items():
            print(f'  {name}: {status["status"]}')

        # Update daily report
        result = self.update_daily_report()

        print('\n' + '=' * 60)

        return result


def main():
    """Run SHADOW window monitor."""
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )

    monitor = ShadowWindowMonitor(conn)
    result = monitor.run_check()

    conn.close()

    return result


if __name__ == '__main__':
    main()
