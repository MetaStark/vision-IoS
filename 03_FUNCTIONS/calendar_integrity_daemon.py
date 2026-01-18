#!/usr/bin/env python3
"""
Calendar Integrity Daemon - CEO-DIR-2026-091

Daily lightweight integrity check that:
- Asserts forward coverage >= 720 days
- Asserts "tomorrow" and "next 7 trading days" resolve cleanly
- Emits RED status if calendar is within 30 days of coverage threshold
- Emits RED status if any required market-day fields are missing/NULL

Scheduled: Daily at 05:00 (before market open)
"""

import os
import sys
import json
import hashlib
import psycopg2
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

# Database connection parameters
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

# Evidence directory
EVIDENCE_DIR = Path(__file__).parent / 'evidence'


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def run_integrity_check(conn, market: str = 'US_EQUITY') -> Dict[str, Any]:
    """
    Run the database integrity check function and return results.

    Status levels (per CEO-DIR-2026-091):
    - GREEN: All clear
    - AMBER: Warning condition (actionable but not halting)
    - RED: Failure condition (requires immediate action or halt)
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT check_name, status, value, threshold, message, severity
            FROM fhq_meta.check_calendar_integrity(%s)
        """, (market,))

        checks = []
        overall_status = 'GREEN'
        has_failure = False
        has_warning = False

        for row in cur.fetchall():
            check = {
                'check_name': row[0],
                'status': row[1],
                'value': row[2],
                'threshold': row[3],
                'message': row[4],
                'severity': row[5]
            }
            checks.append(check)

            # Determine overall status using severity
            if row[5] == 'FAILURE':
                has_failure = True
            elif row[5] == 'WARNING':
                has_warning = True

        # Overall status: RED only for failures, AMBER for warnings
        if has_failure:
            overall_status = 'RED'
        elif has_warning:
            overall_status = 'AMBER'
        else:
            overall_status = 'GREEN'

        return {
            'market': market,
            'checks': checks,
            'overall_status': overall_status,
            'has_failure': has_failure,
            'has_warning': has_warning
        }


def get_tomorrow_status(conn, market: str = 'US_EQUITY') -> Dict[str, Any]:
    """
    Get tomorrow's market status for daily report.
    """
    tomorrow = date.today() + timedelta(days=1)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                date,
                status,
                reason,
                provenance,
                is_tentative
            FROM fhq_meta.ios016_calendar_truth
            WHERE market = %s AND date = %s
        """, (market, tomorrow))

        row = cur.fetchone()
        if row:
            return {
                'date': row[0].isoformat(),
                'is_open': row[1] == 'OPEN',
                'status': row[1],
                'reason': row[2],
                'provenance': row[3],
                'is_tentative': row[4]
            }
        else:
            return {
                'date': tomorrow.isoformat(),
                'is_open': None,
                'status': 'UNKNOWN',
                'reason': 'NO_DATA',
                'provenance': None,
                'is_tentative': True
            }


def get_next_trading_days(conn, market: str = 'US_EQUITY', count: int = 5) -> List[Dict[str, Any]]:
    """
    Get next N trading days for daily report.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT trading_date, day_number
            FROM fhq_meta.get_next_trading_days(%s, CURRENT_DATE, %s)
        """, (market, count))

        return [
            {'date': row[0].isoformat(), 'day_number': row[1]}
            for row in cur.fetchall()
        ]


def get_projection_window_status(conn, market: str = 'US_EQUITY', days: int = 30) -> Dict[str, Any]:
    """
    Check if any days in the next N days are PROJECTED.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE provenance = 'PROJECTED') as projected_count,
                COUNT(*) as total_count,
                MIN(date) FILTER (WHERE provenance = 'PROJECTED') as first_projected
            FROM fhq_meta.calendar_days
            WHERE calendar_id = %s
            AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + %s
        """, (market, days))

        row = cur.fetchone()
        return {
            'window_days': days,
            'projected_count': row[0],
            'total_count': row[1],
            'first_projected_date': row[2].isoformat() if row[2] else None,
            'all_verified': row[0] == 0
        }


def get_coverage_summary(conn, market: str = 'US_EQUITY') -> Dict[str, Any]:
    """
    Get calendar coverage summary.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                MIN(date) as coverage_start,
                MAX(date) as coverage_end,
                MAX(date) - CURRENT_DATE as forward_days,
                COUNT(*) as total_days,
                COUNT(*) FILTER (WHERE is_open) as trading_days,
                COUNT(*) FILTER (WHERE NOT is_open AND reason = 'HOLIDAY') as holidays,
                COUNT(*) FILTER (WHERE NOT is_open AND reason = 'WEEKEND') as weekends,
                COUNT(*) FILTER (WHERE provenance = 'LIBRARY') as library_days,
                COUNT(*) FILTER (WHERE provenance = 'PROJECTED') as projected_days
            FROM fhq_meta.calendar_days
            WHERE calendar_id = %s
        """, (market,))

        row = cur.fetchone()
        return {
            'coverage_start': row[0].isoformat(),
            'coverage_end': row[1].isoformat(),
            'forward_days': row[2],
            'total_days': row[3],
            'trading_days': row[4],
            'holidays': row[5],
            'weekends': row[6],
            'library_days': row[7],
            'projected_days': row[8],
            'meets_minimum': row[2] >= 720
        }


def log_integrity_check(conn, result: Dict[str, Any]) -> str:
    """
    Log the integrity check result to governance_actions_log.
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_governance.governance_actions_log
                (action_type, action_target, action_target_type, initiated_by, decision, decision_rationale, metadata)
            VALUES
                ('CALENDAR_INTEGRITY_CHECK', %s, 'DAEMON_RUN', 'STIG', %s,
                 'Daily calendar integrity check per CEO-DIR-2026-091',
                 %s::jsonb)
            RETURNING action_id
        """, (
            f"CALENDAR_INTEGRITY_{result['market']}_{datetime.now().strftime('%Y%m%d')}",
            result['overall_status'],
            json.dumps(result)
        ))

        action_id = cur.fetchone()[0]
        conn.commit()
        return str(action_id)


def generate_evidence_file(result: Dict[str, Any]) -> str:
    """
    Generate an evidence file for the integrity check.
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"CALENDAR_INTEGRITY_{result['market']}_{timestamp}.json"
    filepath = EVIDENCE_DIR / filename

    # Add metadata
    evidence = {
        'evidence_id': f"CAL-INTEG-{timestamp}",
        'directive': 'CEO-DIR-2026-091',
        'generated_at': datetime.now().isoformat(),
        'generated_by': 'calendar_integrity_daemon.py',
        **result
    }

    # Compute hash
    content_str = json.dumps(evidence, sort_keys=True)
    evidence['content_hash'] = hashlib.sha256(content_str.encode()).hexdigest()[:16]

    # Write file
    with open(filepath, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    return str(filepath)


def run_daily_check(market: str = 'US_EQUITY', dry_run: bool = False) -> Dict[str, Any]:
    """
    Run the complete daily calendar integrity check.

    Returns a comprehensive result including:
    - Integrity check results
    - Tomorrow's market status
    - Next 5 trading days
    - Projection window status
    - Coverage summary
    """
    conn = get_db_connection()

    try:
        # Run all checks
        integrity = run_integrity_check(conn, market)
        tomorrow = get_tomorrow_status(conn, market)
        next_5_days = get_next_trading_days(conn, market, 5)
        projection_status = get_projection_window_status(conn, market, 30)
        coverage = get_coverage_summary(conn, market)

        # Compile result
        result = {
            'run_timestamp': datetime.now().isoformat(),
            'market': market,
            'overall_status': integrity['overall_status'],

            'integrity_checks': integrity['checks'],

            'daily_report_fields': {
                'market_open_tomorrow': {
                    'answer': 'YES' if tomorrow['is_open'] else 'NO',
                    'date': tomorrow['date'],
                    'reason': tomorrow['reason'],
                    'is_tentative': tomorrow['is_tentative']
                },
                'next_5_trading_days': next_5_days,
                'projection_window_status': projection_status
            },

            'coverage_summary': coverage,

            'governance': {
                'directive': 'CEO-DIR-2026-091',
                'check_type': 'DAILY_INTEGRITY',
                'daemon': 'calendar_integrity_daemon.py'
            }
        }

        # Determine action requirements based on severity
        # RED (FAILURE) = halt required, AMBER (WARNING) = actionable but not halting
        red_checks = [c for c in integrity['checks'] if c.get('severity') == 'FAILURE']
        amber_checks = [c for c in integrity['checks'] if c.get('severity') == 'WARNING']

        result['action_required'] = integrity.get('has_failure', len(red_checks) > 0)
        result['red_alerts'] = red_checks
        result['amber_alerts'] = amber_checks

        if not dry_run:
            # Log to governance
            action_id = log_integrity_check(conn, result)
            result['governance_action_id'] = action_id

            # Generate evidence file
            evidence_path = generate_evidence_file(result)
            result['evidence_file'] = evidence_path

            print(f"[CALENDAR_INTEGRITY] {datetime.now().isoformat()}")
            print(f"  Market: {market}")
            print(f"  Overall Status: {result['overall_status']}")
            print(f"  Forward Coverage: {coverage['forward_days']} days")
            print(f"  Tomorrow: {tomorrow['status']} ({tomorrow['reason']})")
            print(f"  Action Required (HALT): {result['action_required']}")

            if red_checks:
                print(f"  RED ALERTS (FAILURE - requires halt):")
                for check in red_checks:
                    print(f"    - {check['check_name']}: {check['message']}")

            if amber_checks:
                print(f"  AMBER ALERTS (WARNING - actionable):")
                for check in amber_checks:
                    print(f"    - {check['check_name']}: {check['message']}")

            print(f"  Evidence: {evidence_path}")

        return result

    finally:
        conn.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Calendar Integrity Daemon - CEO-DIR-2026-091')
    parser.add_argument('--market', default='US_EQUITY', help='Market to check')
    parser.add_argument('--dry-run', action='store_true', help='Run without logging')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    result = run_daily_check(market=args.market, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result, indent=2, default=str))

    # Exit with non-zero if action required
    if result.get('action_required'):
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
