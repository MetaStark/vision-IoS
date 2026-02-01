#!/usr/bin/env python3
"""
DAILY GOAL TRACKER
==================
CEO-DIR-2026-0ZD: Track 1 Operational Discipline
Baseline: CEO-DIR-2026-0ZC (Day 3 Truth Freeze)

Commands:
    python daily_goal_tracker.py              # Show today's goals
    python daily_goal_tracker.py --verify     # Verify completions
    python daily_goal_tracker.py --week       # Show full week view
    python daily_goal_tracker.py --status     # Show status summary

Process: Hybrid (CEO defines goals, STIG verifies completion)

Author: STIG (CTO)
Date: 2026-01-11
"""

import os
import sys
import json
import argparse
import hashlib
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', 54322)),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


class GoalStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"


@dataclass
class DailyGoal:
    """Represents a daily goal from the calendar."""
    goal_id: str
    phase_name: str
    day_number: int
    calendar_date: date
    goal_title: str
    goal_description: str
    goal_type: str
    priority: str
    status: str
    completion_percentage: float
    assigned_agent: str
    verification_query: Optional[str]
    expected_threshold: Optional[float]
    evidence_id: Optional[str]


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_todays_goals(conn, target_date: date = None) -> List[DailyGoal]:
    """Fetch goals for today (or specified date)."""
    if target_date is None:
        target_date = date.today()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                goal_id::text,
                phase_name,
                day_number,
                calendar_date,
                goal_title,
                goal_description,
                goal_type,
                priority,
                status,
                COALESCE(completion_percentage, 0) as completion_percentage,
                assigned_agent,
                verification_query,
                expected_threshold,
                evidence_id::text
            FROM fhq_governance.daily_goal_calendar
            WHERE calendar_date = %s
            ORDER BY priority, goal_title
        """, (target_date,))

        rows = cur.fetchall()

        return [
            DailyGoal(
                goal_id=row['goal_id'],
                phase_name=row['phase_name'],
                day_number=row['day_number'],
                calendar_date=row['calendar_date'],
                goal_title=row['goal_title'],
                goal_description=row['goal_description'],
                goal_type=row['goal_type'],
                priority=row['priority'],
                status=row['status'],
                completion_percentage=float(row['completion_percentage']),
                assigned_agent=row['assigned_agent'],
                verification_query=row['verification_query'],
                expected_threshold=float(row['expected_threshold']) if row['expected_threshold'] else None,
                evidence_id=row['evidence_id']
            )
            for row in rows
        ]


def get_week_goals(conn, start_date: date = None) -> Dict[date, List[DailyGoal]]:
    """Fetch goals for the current week."""
    if start_date is None:
        start_date = date.today()

    # Get 7 days starting from start_date
    end_date = start_date + timedelta(days=6)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                goal_id::text,
                phase_name,
                day_number,
                calendar_date,
                goal_title,
                goal_description,
                goal_type,
                priority,
                status,
                COALESCE(completion_percentage, 0) as completion_percentage,
                assigned_agent,
                verification_query,
                expected_threshold,
                evidence_id::text
            FROM fhq_governance.daily_goal_calendar
            WHERE calendar_date BETWEEN %s AND %s
            ORDER BY calendar_date, priority, goal_title
        """, (start_date, end_date))

        rows = cur.fetchall()

        # Group by date
        goals_by_date: Dict[date, List[DailyGoal]] = {}
        for row in rows:
            goal = DailyGoal(
                goal_id=row['goal_id'],
                phase_name=row['phase_name'],
                day_number=row['day_number'],
                calendar_date=row['calendar_date'],
                goal_title=row['goal_title'],
                goal_description=row['goal_description'],
                goal_type=row['goal_type'],
                priority=row['priority'],
                status=row['status'],
                completion_percentage=float(row['completion_percentage']),
                assigned_agent=row['assigned_agent'],
                verification_query=row['verification_query'],
                expected_threshold=float(row['expected_threshold']) if row['expected_threshold'] else None,
                evidence_id=row['evidence_id']
            )

            if goal.calendar_date not in goals_by_date:
                goals_by_date[goal.calendar_date] = []
            goals_by_date[goal.calendar_date].append(goal)

        return goals_by_date


def verify_goal(conn, goal: DailyGoal) -> Tuple[bool, Optional[float], str]:
    """
    Verify a goal's completion using its verification query.
    Returns: (threshold_met, actual_value, message)
    """
    if not goal.verification_query:
        return False, None, "No verification query defined - requires manual verification"

    try:
        with conn.cursor() as cur:
            cur.execute(goal.verification_query)
            result = cur.fetchone()

            if result is None:
                return False, None, "Query returned no results"

            actual_value = float(result[0]) if result[0] is not None else 0

            if goal.expected_threshold is None:
                return True, actual_value, f"Query executed, value={actual_value} (no threshold defined)"

            threshold_met = actual_value >= goal.expected_threshold

            if threshold_met:
                return True, actual_value, f"PASS: {actual_value} >= {goal.expected_threshold}"
            else:
                return False, actual_value, f"FAIL: {actual_value} < {goal.expected_threshold}"

    except Exception as e:
        return False, None, f"Query error: {str(e)}"


def record_completion(conn, goal: DailyGoal, actual_value: float, threshold_met: bool) -> str:
    """Record goal completion with evidence."""
    verification_result = {
        'goal_id': goal.goal_id,
        'goal_title': goal.goal_title,
        'verification_timestamp': datetime.now(timezone.utc).isoformat(),
        'query': goal.verification_query,
        'actual_value': actual_value,
        'threshold': goal.expected_threshold,
        'threshold_met': threshold_met
    }

    with conn.cursor() as cur:
        cur.execute("""
            SELECT fhq_governance.record_goal_completion(
                %s::uuid,
                %s,
                %s::jsonb,
                %s,
                %s,
                %s,
                'STIG'
            )
        """, (
            goal.goal_id,
            goal.verification_query or '',
            json.dumps(verification_result),
            threshold_met,
            goal.expected_threshold,
            actual_value
        ))

        evidence_id = cur.fetchone()[0]
        conn.commit()

        return str(evidence_id)


def print_goal(goal: DailyGoal, verbose: bool = False):
    """Print a single goal with formatting."""
    status_icons = {
        'PENDING': '[ ]',
        'IN_PROGRESS': '[~]',
        'COMPLETED': '[x]',
        'BLOCKED': '[!]',
        'DEFERRED': '[-]'
    }

    priority_colors = {
        'P0': '\033[91m',  # Red
        'P1': '\033[93m',  # Yellow
        'P2': '\033[92m',  # Green
    }

    reset = '\033[0m'
    icon = status_icons.get(goal.status, '[?]')
    color = priority_colors.get(goal.priority, '')

    print(f"  {icon} {color}[{goal.priority}]{reset} {goal.goal_title}")
    print(f"      Type: {goal.goal_type} | Agent: {goal.assigned_agent} | Status: {goal.status}")

    if goal.completion_percentage > 0 and goal.status != 'COMPLETED':
        print(f"      Progress: {goal.completion_percentage:.0f}%")

    if verbose:
        print(f"      Description: {goal.goal_description}")
        if goal.verification_query:
            print(f"      Verification: SQL query defined (threshold: {goal.expected_threshold})")
        else:
            print(f"      Verification: Manual")


def cmd_show_today(args):
    """Show today's goals."""
    conn = get_connection()
    try:
        target_date = date.today()
        goals = get_todays_goals(conn, target_date)

        print("=" * 60)
        print(f"DAILY GOALS: {target_date.strftime('%A, %B %d, %Y')}")
        print("CEO-DIR-2026-0ZD | Track 1: Operational Discipline")
        print("=" * 60)

        if not goals:
            print("\nNo goals scheduled for today.")
            return

        # Group by priority
        p0_goals = [g for g in goals if g.priority == 'P0']
        p1_goals = [g for g in goals if g.priority == 'P1']
        p2_goals = [g for g in goals if g.priority == 'P2']

        if p0_goals:
            print(f"\n\033[91mP0 - CRITICAL ({len(p0_goals)})\033[0m")
            for goal in p0_goals:
                print_goal(goal, args.verbose)

        if p1_goals:
            print(f"\n\033[93mP1 - HIGH ({len(p1_goals)})\033[0m")
            for goal in p1_goals:
                print_goal(goal, args.verbose)

        if p2_goals:
            print(f"\n\033[92mP2 - NORMAL ({len(p2_goals)})\033[0m")
            for goal in p2_goals:
                print_goal(goal, args.verbose)

        # Summary
        completed = sum(1 for g in goals if g.status == 'COMPLETED')
        in_progress = sum(1 for g in goals if g.status == 'IN_PROGRESS')
        pending = sum(1 for g in goals if g.status == 'PENDING')

        print(f"\n{'─' * 60}")
        print(f"Summary: {completed}/{len(goals)} completed | {in_progress} in progress | {pending} pending")

    finally:
        conn.close()


def cmd_verify(args):
    """Verify goal completions."""
    conn = get_connection()
    try:
        target_date = date.today()
        goals = get_todays_goals(conn, target_date)

        print("=" * 60)
        print(f"GOAL VERIFICATION: {target_date.strftime('%A, %B %d, %Y')}")
        print("CEO-DIR-2026-0ZD | STIG Verification Protocol")
        print("=" * 60)

        if not goals:
            print("\nNo goals scheduled for today.")
            return

        # Filter to verifiable goals (with SQL queries)
        verifiable = [g for g in goals if g.verification_query and g.status != 'COMPLETED']
        manual = [g for g in goals if not g.verification_query and g.status != 'COMPLETED']
        completed = [g for g in goals if g.status == 'COMPLETED']

        if completed:
            print(f"\n\033[92mALREADY COMPLETED ({len(completed)})\033[0m")
            for goal in completed:
                print(f"  [x] {goal.goal_title}")
                if goal.evidence_id:
                    print(f"      Evidence: {goal.evidence_id[:8]}...")

        if verifiable:
            print(f"\n\033[93mVERIFYING ({len(verifiable)})\033[0m")
            for goal in verifiable:
                print(f"\n  Checking: {goal.goal_title}")
                print(f"  Query: {goal.verification_query[:60]}..." if len(goal.verification_query) > 60 else f"  Query: {goal.verification_query}")

                threshold_met, actual_value, message = verify_goal(conn, goal)

                if threshold_met:
                    print(f"  Result: \033[92m{message}\033[0m")

                    if args.record and actual_value is not None:
                        evidence_id = record_completion(conn, goal, actual_value, threshold_met)
                        print(f"  Evidence recorded: {evidence_id}")
                else:
                    print(f"  Result: \033[91m{message}\033[0m")

        if manual:
            print(f"\n\033[93mMANUAL VERIFICATION REQUIRED ({len(manual)})\033[0m")
            for goal in manual:
                print(f"  [ ] {goal.goal_title}")
                print(f"      Agent: {goal.assigned_agent} | Type: {goal.goal_type}")

    finally:
        conn.close()


def cmd_week(args):
    """Show week view of goals."""
    conn = get_connection()
    try:
        start_date = date.today()
        goals_by_date = get_week_goals(conn, start_date)

        print("=" * 60)
        print(f"WEEK VIEW: {start_date.strftime('%B %d')} - {(start_date + timedelta(days=6)).strftime('%B %d, %Y')}")
        print("CEO-DIR-2026-0ZD | Track 1: Operational Discipline")
        print("=" * 60)

        for i in range(7):
            current_date = start_date + timedelta(days=i)
            goals = goals_by_date.get(current_date, [])

            day_name = current_date.strftime('%A')
            is_today = current_date == date.today()

            marker = " <-- TODAY" if is_today else ""
            print(f"\n\033[1m{day_name}, {current_date.strftime('%b %d')}{marker}\033[0m")

            if not goals:
                print("  No goals scheduled")
                continue

            completed = sum(1 for g in goals if g.status == 'COMPLETED')
            total = len(goals)

            for goal in goals:
                status_char = 'x' if goal.status == 'COMPLETED' else ' '
                print(f"  [{status_char}] [{goal.priority}] {goal.goal_title}")

            print(f"      ({completed}/{total} completed)")

    finally:
        conn.close()


def cmd_status(args):
    """Show status summary."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Overall stats
            cur.execute("""
                SELECT
                    phase_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'BLOCKED' THEN 1 ELSE 0 END) as blocked
                FROM fhq_governance.daily_goal_calendar
                GROUP BY phase_name
                ORDER BY phase_name
            """)

            phases = cur.fetchall()

            print("=" * 60)
            print("GOAL CALENDAR STATUS")
            print("CEO-DIR-2026-0ZD | Track 1: Operational Discipline")
            print("=" * 60)

            for phase in phases:
                pct = (phase['completed'] / phase['total'] * 100) if phase['total'] > 0 else 0
                print(f"\n{phase['phase_name']}")
                print(f"  Total: {phase['total']} | Completed: {phase['completed']} ({pct:.0f}%)")
                print(f"  In Progress: {phase['in_progress']} | Pending: {phase['pending']} | Blocked: {phase['blocked']}")

            # Evidence chain stats
            cur.execute("""
                SELECT
                    COUNT(*) as total_evidence,
                    COUNT(DISTINCT goal_id) as goals_with_evidence
                FROM fhq_governance.goal_completion_evidence
            """)

            evidence = cur.fetchone()

            print(f"\n{'─' * 60}")
            print(f"Evidence Chain: {evidence['total_evidence']} records | {evidence['goals_with_evidence']} goals verified")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Daily Goal Tracker - CEO-DIR-2026-0ZD Track 1',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python daily_goal_tracker.py              # Show today's goals
  python daily_goal_tracker.py --verify     # Verify completions
  python daily_goal_tracker.py --week       # Show full week view
  python daily_goal_tracker.py --status     # Show status summary
        """
    )

    parser.add_argument('--verify', action='store_true', help='Run verification queries')
    parser.add_argument('--record', action='store_true', help='Record completed verifications (use with --verify)')
    parser.add_argument('--week', action='store_true', help='Show week view')
    parser.add_argument('--status', action='store_true', help='Show status summary')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    try:
        if args.verify:
            cmd_verify(args)
        elif args.week:
            cmd_week(args)
        elif args.status:
            cmd_status(args)
        else:
            cmd_show_today(args)

    except psycopg2.Error as e:
        print(f"\033[91mDatabase error: {e}\033[0m")
        print("Ensure migration 231_daily_goal_calendar.sql has been applied.")
        sys.exit(1)
    except Exception as e:
        print(f"\033[91mError: {e}\033[0m")
        sys.exit(1)


if __name__ == '__main__':
    main()
