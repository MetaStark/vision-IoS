#!/usr/bin/env python3
"""
CEO-DIR-2026-088: CONTINUOUS TRADING CALENDAR GOVERNANCE

This daemon ensures the FjordHQ trading calendar is:
- Forward-complete (minimum 24 months ahead)
- Continuously maintained
- Audit-verifiable
- Idempotent (never rewrites history)

SOURCE OF TRUTH: exchange_calendars library (industry standard)
- Uses official NYSE/NASDAQ exchange calendars
- Maintained by quantitative finance community
- Documented, stable, reviewable

AUTHORITY: CEO
EXECUTED BY: STIG (EC-003)
"""

import os
import sys
import json
import hashlib
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
import exchange_calendars as xcals


# Holiday calculation helpers (for projecting beyond library range)
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Get nth occurrence of weekday in month (1-indexed)."""
    first = date(year, month, 1)
    first_weekday = first.weekday()
    days_until = (weekday - first_weekday) % 7
    return first + timedelta(days=days_until + (n - 1) * 7)

def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Get last occurrence of weekday in month."""
    # Start from 5th week possibility and work back
    for n in range(5, 0, -1):
        try:
            d = _nth_weekday(year, month, weekday, n)
            if d.month == month:
                return d
        except:
            pass
    return _nth_weekday(year, month, weekday, 4)

def _mlk_day(year: int) -> date:
    """Martin Luther King Jr. Day: 3rd Monday of January."""
    return _nth_weekday(year, 1, 0, 3)  # 0 = Monday

def _presidents_day(year: int) -> date:
    """Presidents Day: 3rd Monday of February."""
    return _nth_weekday(year, 2, 0, 3)

def _memorial_day(year: int) -> date:
    """Memorial Day: Last Monday of May."""
    return _last_weekday(year, 5, 0)

def _labor_day(year: int) -> date:
    """Labor Day: 1st Monday of September."""
    return _nth_weekday(year, 9, 0, 1)

def _thanksgiving(year: int) -> date:
    """Thanksgiving: 4th Thursday of November."""
    return _nth_weekday(year, 11, 3, 4)  # 3 = Thursday

def _day_after_thanksgiving(year: int) -> date:
    """Day after Thanksgiving (early close)."""
    return _thanksgiving(year) + timedelta(days=1)

def _good_friday(year: int) -> date:
    """Good Friday: Friday before Easter Sunday."""
    # Computus algorithm for Easter
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, month, day)
    return easter - timedelta(days=2)

def _independence_day_observed(year: int) -> date:
    """July 4th or observed date if falls on weekend."""
    july4 = date(year, 7, 4)
    if july4.weekday() == 5:  # Saturday
        return date(year, 7, 3)  # Friday
    elif july4.weekday() == 6:  # Sunday
        return date(year, 7, 5)  # Monday
    return july4

def _christmas_observed(year: int) -> date:
    """Christmas or observed date if falls on weekend."""
    xmas = date(year, 12, 25)
    if xmas.weekday() == 5:  # Saturday
        return date(year, 12, 24)  # Friday
    elif xmas.weekday() == 6:  # Sunday
        return date(year, 12, 26)  # Monday
    return xmas


# Configuration
CALENDAR_CONFIGS = {
    'US_EQUITY': {
        'exchange_calendar': 'XNYS',  # NYSE calendar (covers NASDAQ too)
        'display_name': 'US Equity Markets (NYSE/NASDAQ)',
        'min_forward_months': 24,
        'source': 'exchange_calendars library (XNYS)',
        'source_url': 'https://github.com/gerrymanoim/exchange_calendars'
    }
}


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "54322"),
        database=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres")
    )


def get_current_coverage(conn, calendar_id: str) -> Tuple[Optional[date], Optional[date]]:
    """Get current calendar coverage dates."""
    cur = conn.cursor()
    cur.execute("""
        SELECT MIN(date), MAX(date)
        FROM fhq_meta.calendar_days
        WHERE calendar_id = %s
    """, (calendar_id,))
    row = cur.fetchone()
    return row[0], row[1]


def get_exchange_calendar_data(
    exchange_code: str,
    start_date: date,
    end_date: date
) -> List[Dict[str, Any]]:
    """
    Get trading calendar data from exchange_calendars library.

    This is the SOURCE OF TRUTH for trading days.
    - Uses official exchange schedules
    - Industry-standard library
    - Documented and reviewable

    NOTE: exchange_calendars has a finite forward horizon (typically 1-2 years).
    For dates beyond the library's range, we project using known patterns:
    - Weekends are always closed
    - Standard US holidays are projected (conservative approach)
    """
    cal = xcals.get_calendar(exchange_code)

    # Get library bounds
    lib_start = cal.first_session.date()
    lib_end = cal.last_session.date()

    # Clamp to library bounds for authoritative data
    query_start = max(start_date, lib_start)
    query_end = min(end_date, lib_end)

    # Get all sessions (trading days) from library
    trading_days = set()
    if query_start <= query_end:
        sessions = cal.sessions_in_range(
            query_start.isoformat(),
            query_end.isoformat()
        )
        trading_days = set(s.date() for s in sessions)

    # Get early closes from library
    early_closes = set()
    try:
        early_close_times = cal.early_closes
        for ts in early_close_times:
            if start_date <= ts.date() <= end_date:
                early_closes.add(ts.date())
    except:
        pass  # Some calendars don't have early close info

    # For dates beyond library range, project holidays
    # US holidays follow predictable patterns
    projected_holidays = set()
    projected_early_closes = set()

    for year in range(start_date.year, end_date.year + 1):
        if year > lib_end.year:
            # Project standard US holidays
            projected_holidays.update([
                date(year, 1, 1),  # New Year's Day (or observed)
                _mlk_day(year),    # MLK Day (3rd Monday Jan)
                _presidents_day(year),  # Presidents Day (3rd Monday Feb)
                _good_friday(year),     # Good Friday
                _memorial_day(year),    # Memorial Day (last Monday May)
                date(year, 6, 19) if date(year, 6, 19).weekday() < 5 else
                    (date(year, 6, 18) if date(year, 6, 19).weekday() == 6 else date(year, 6, 20)),  # Juneteenth
                _independence_day_observed(year),  # July 4 (or observed)
                _labor_day(year),       # Labor Day (1st Monday Sep)
                _thanksgiving(year),    # Thanksgiving (4th Thursday Nov)
                _christmas_observed(year),  # Christmas (or observed)
            ])
            # Project early closes
            projected_early_closes.add(_day_after_thanksgiving(year))
            projected_early_closes.add(date(year, 12, 24) if date(year, 12, 24).weekday() < 5 else None)

    projected_early_closes.discard(None)

    # Generate all days in range
    calendar_data = []
    current = start_date
    while current <= end_date:
        is_weekend = current.weekday() >= 5

        # Determine if trading day
        if current <= lib_end:
            # Use authoritative library data
            is_trading = current in trading_days
        else:
            # Project: weekdays that aren't projected holidays
            is_trading = not is_weekend and current not in projected_holidays

        # Determine early close
        is_early = current in early_closes or current in projected_early_closes

        # Build notes and session times
        is_projected = current > lib_end

        if is_weekend:
            notes = "Saturday" if current.weekday() == 5 else "Sunday"
            session_open = None
            session_close = None
        elif not is_trading:
            notes = "Holiday" + (" (projected)" if is_projected else "")
            session_open = None
            session_close = None
        elif is_early:
            notes = "Early Close" + (" (projected)" if is_projected else "")
            session_open = "09:30"
            session_close = "13:00"
        else:
            notes = "(projected)" if is_projected else None
            session_open = "09:30"
            session_close = "16:00"

        calendar_data.append({
            'date': current,
            'is_open': is_trading,
            'session_open': session_open,
            'session_close': session_close,
            'early_close': is_early,
            'notes': notes
        })

        current += timedelta(days=1)

    return calendar_data


def extend_calendar(
    conn,
    calendar_id: str,
    config: Dict[str, Any],
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Extend trading calendar forward.

    IDEMPOTENCY GUARANTEE:
    - Only inserts dates that don't exist
    - Never modifies historical data
    - Safe to run multiple times
    """
    today = date.today()
    target_end = today + timedelta(days=config['min_forward_months'] * 30)

    # Get current coverage
    current_start, current_end = get_current_coverage(conn, calendar_id)

    result = {
        'calendar_id': calendar_id,
        'execution_timestamp': datetime.now().isoformat(),
        'current_coverage': {
            'start': str(current_start) if current_start else None,
            'end': str(current_end) if current_end else None
        },
        'target_end': str(target_end),
        'source': config['source'],
        'dry_run': dry_run
    }

    if current_end and current_end >= target_end:
        result['action'] = 'NO_ACTION_NEEDED'
        result['message'] = f"Calendar already covers through {current_end}"
        return result

    # Determine extension range (never rewrite history)
    if current_end:
        extension_start = current_end + timedelta(days=1)
    else:
        extension_start = today - timedelta(days=365)  # Start 1 year back if empty

    extension_end = target_end

    result['extension_range'] = {
        'start': str(extension_start),
        'end': str(extension_end)
    }

    # Get calendar data from source of truth
    calendar_data = get_exchange_calendar_data(
        config['exchange_calendar'],
        extension_start,
        extension_end
    )

    if dry_run:
        result['action'] = 'DRY_RUN'
        result['would_insert'] = len(calendar_data)
        return result

    # Insert new days (idempotent via ON CONFLICT DO NOTHING)
    cur = conn.cursor()
    inserted = 0

    for day in calendar_data:
        try:
            cur.execute("""
                INSERT INTO fhq_meta.calendar_days
                (calendar_id, date, is_open, session_open, session_close, early_close, notes)
                VALUES (%s, %s, %s, %s::time, %s::time, %s, %s)
                ON CONFLICT (calendar_id, date) DO NOTHING
            """, (
                calendar_id,
                day['date'],
                day['is_open'],
                day['session_open'],
                day['session_close'],
                day['early_close'],
                day['notes']
            ))
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            conn.rollback()
            result['action'] = 'ERROR'
            result['error'] = str(e)
            return result

    conn.commit()

    # Get new coverage
    new_start, new_end = get_current_coverage(conn, calendar_id)

    result['action'] = 'EXTENDED'
    result['days_inserted'] = inserted
    result['new_coverage'] = {
        'start': str(new_start),
        'end': str(new_end)
    }

    # Count trading days in new range
    cur.execute("""
        SELECT COUNT(*) FROM fhq_meta.calendar_days
        WHERE calendar_id = %s AND is_open = true
        AND date BETWEEN %s AND %s
    """, (calendar_id, extension_start, extension_end))
    result['trading_days_added'] = cur.fetchone()[0]

    return result


def log_governance_action(conn, result: Dict[str, Any]):
    """Log calendar update to governance_actions_log."""
    cur = conn.cursor()

    # Compute evidence hash
    evidence_json = json.dumps(result, sort_keys=True, default=str)
    evidence_hash = hashlib.sha256(evidence_json.encode()).hexdigest()[:16]

    description = (
        f"CEO-DIR-2026-088: Extended {result['calendar_id']} calendar. "
        f"Action: {result['action']}. "
        f"Days inserted: {result.get('days_inserted', 0)}. "
        f"Coverage through: {result.get('new_coverage', {}).get('end', 'N/A')}"
    )

    cur.execute("""
        INSERT INTO fhq_governance.governance_actions_log
        (action_id, action_type, action_target, action_target_type,
         initiated_by, initiated_at, decision, decision_rationale,
         metadata, hash_chain_id, agent_id, timestamp)
        VALUES (
            gen_random_uuid(),
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        'CALENDAR_EXTENSION',
        result['calendar_id'],
        'TRADING_CALENDAR',
        'STIG',
        datetime.now(),
        'APPROVED',
        description,
        json.dumps(result, default=str),
        evidence_hash,
        'STIG',
        datetime.now()
    ))
    conn.commit()

    return evidence_hash


def get_calendar_coverage_indicator(conn, calendar_id: str) -> Dict[str, Any]:
    """
    Get board-readable calendar coverage indicator.

    This answers the CEO's question:
    "Do we know what happens next week?"
    """
    cur = conn.cursor()

    today = date.today()
    target_24m = today + timedelta(days=24 * 30)

    cur.execute("""
        SELECT
            MIN(date) as coverage_start,
            MAX(date) as coverage_end,
            COUNT(*) as total_days,
            SUM(CASE WHEN is_open THEN 1 ELSE 0 END) as trading_days
        FROM fhq_meta.calendar_days
        WHERE calendar_id = %s
    """, (calendar_id,))
    row = cur.fetchone()

    coverage_end = row[1]
    is_compliant = coverage_end and coverage_end >= target_24m

    # Days of forward coverage
    if coverage_end:
        forward_days = (coverage_end - today).days
        forward_months = forward_days / 30
    else:
        forward_days = 0
        forward_months = 0

    return {
        'calendar_id': calendar_id,
        'coverage_start': str(row[0]) if row[0] else None,
        'coverage_end': str(coverage_end) if coverage_end else None,
        'total_days': row[2],
        'trading_days': row[3],
        'forward_days': forward_days,
        'forward_months': round(forward_months, 1),
        'target_months': 24,
        'compliant': is_compliant,
        'status': 'COMPLIANT' if is_compliant else 'EXTENSION_REQUIRED',
        'board_summary': f"US_EQUITY calendar valid through: {coverage_end}" if coverage_end else "CALENDAR NOT POPULATED"
    }


def run_calendar_governance(dry_run: bool = False) -> Dict[str, Any]:
    """
    Main entry point for calendar governance daemon.

    This function:
    1. Checks all configured calendars
    2. Extends forward as needed (24+ months)
    3. Logs all actions to governance
    4. Returns board-readable status
    """
    print("=" * 70)
    print("CEO-DIR-2026-088: CONTINUOUS TRADING CALENDAR GOVERNANCE")
    print("=" * 70)
    print(f"Execution: {datetime.now().isoformat()}")
    print(f"Dry Run: {dry_run}")
    print(f"Source: exchange_calendars library (industry standard)")
    print()

    conn = get_db_connection()
    results = {
        'directive': 'CEO-DIR-2026-088',
        'executed_at': datetime.now().isoformat(),
        'executed_by': 'STIG (EC-003)',
        'calendars': {}
    }

    try:
        for calendar_id, config in CALENDAR_CONFIGS.items():
            print(f"Processing: {calendar_id}")
            print(f"  Source: {config['source']}")

            # Extend calendar
            result = extend_calendar(conn, calendar_id, config, dry_run)

            print(f"  Action: {result['action']}")
            if result.get('days_inserted'):
                print(f"  Days Inserted: {result['days_inserted']}")
            if result.get('new_coverage'):
                print(f"  Coverage: {result['new_coverage']['start']} to {result['new_coverage']['end']}")

            # Log to governance (unless dry run)
            if not dry_run and result['action'] in ('EXTENDED', 'NO_ACTION_NEEDED'):
                evidence_hash = log_governance_action(conn, result)
                result['governance_hash'] = evidence_hash
                print(f"  Governance Hash: {evidence_hash}")

            # Get coverage indicator
            indicator = get_calendar_coverage_indicator(conn, calendar_id)
            result['coverage_indicator'] = indicator

            print(f"  Status: {indicator['status']}")
            print(f"  Board Summary: {indicator['board_summary']}")
            print()

            results['calendars'][calendar_id] = result

        # Overall status
        all_compliant = all(
            r.get('coverage_indicator', {}).get('compliant', False)
            for r in results['calendars'].values()
        )
        results['overall_status'] = 'ALL_COMPLIANT' if all_compliant else 'EXTENSION_REQUIRED'

        print("=" * 70)
        print(f"OVERALL STATUS: {results['overall_status']}")
        print("=" * 70)

    finally:
        conn.close()

    return results


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(
        description='CEO-DIR-2026-088: Trading Calendar Governance Daemon'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--status-only',
        action='store_true',
        help='Only show current coverage status'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )

    args = parser.parse_args()

    if args.status_only:
        conn = get_db_connection()
        try:
            for calendar_id in CALENDAR_CONFIGS:
                indicator = get_calendar_coverage_indicator(conn, calendar_id)
                if args.json:
                    print(json.dumps(indicator, indent=2))
                else:
                    print(f"{calendar_id}: {indicator['board_summary']}")
                    print(f"  Forward Coverage: {indicator['forward_months']} months")
                    print(f"  Status: {indicator['status']}")
        finally:
            conn.close()
    else:
        results = run_calendar_governance(dry_run=args.dry_run)

        if args.json:
            print(json.dumps(results, indent=2, default=str))

        # Write evidence file
        if not args.dry_run:
            evidence_path = Path(__file__).parent / 'evidence' / f"CEO_DIR_2026_088_CALENDAR_GOVERNANCE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            evidence_path.parent.mkdir(exist_ok=True)
            with open(evidence_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\nEvidence: {evidence_path}")


if __name__ == "__main__":
    main()
