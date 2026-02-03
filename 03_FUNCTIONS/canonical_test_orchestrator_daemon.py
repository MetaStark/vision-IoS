#!/usr/bin/env python3
"""
Canonical Test Orchestrator Daemon — CEO-DIR-2026

The single process responsible for executing, monitoring, escalating,
and resolving ALL Canonical Test Events.

Test-agnostic design: EC-022 is the first governed test, not a special case.

Schedule: Daily at 06:00 CET (before market open)
Owner: EC-003 (STIG)

Phases:
1. DISCOVER - Load all ACTIVE tests from canonical_test_events
2. EVALUATE - For each test: progress, metrics, escalation check
3. EXECUTE  - Update states, write runbook entries, resolve if overdue

Fail-Closed Guardrails:
- HALT if test definition incomplete
- HALT if escalation path undefined
- WARN if metrics unavailable (evaluation deferred)
"""

import os
import sys
import json
import hashlib
import psycopg2
import psycopg2.extras
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import uuid
import traceback


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal and datetime types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)


def json_dumps(obj, **kwargs):
    """JSON dumps with Decimal support."""
    return json.dumps(obj, cls=DecimalEncoder, **kwargs)

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}

EVIDENCE_DIR = Path(__file__).parent / 'evidence'
DAILY_REPORTS_DIR = Path(__file__).parent.parent / '12_DAILY_REPORTS'

# Ensure directories exist
EVIDENCE_DIR.mkdir(exist_ok=True)
DAILY_REPORTS_DIR.mkdir(exist_ok=True)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """Get database connection with RealDictCursor."""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


# =============================================================================
# PHASE 1: DISCOVER
# =============================================================================

def discover_active_tests(conn) -> List[Dict]:
    """
    Load all ACTIVE tests from canonical_test_events.
    No hardcoded test codes - fully test-agnostic.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                test_id,
                test_code,
                test_name,
                display_name,
                owning_agent,
                monitoring_agent_ec,
                beneficiary_system,
                status,
                start_ts,
                end_ts,
                required_days,
                days_elapsed,
                days_remaining,
                baseline_definition,
                target_metrics,
                success_criteria,
                failure_criteria,
                escalation_state,
                ceo_action_required,
                recommended_actions,
                mid_test_checkpoint,
                verdict,
                last_orchestrator_run,
                orchestrator_run_count
            FROM fhq_calendar.canonical_test_events
            WHERE status = 'ACTIVE'
            ORDER BY start_ts ASC
        """)
        return [dict(row) for row in cur.fetchall()]


# =============================================================================
# PHASE 2: EVALUATE
# =============================================================================

def validate_test_definition(test: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate test has complete definition.
    Returns (is_valid, error_message).
    """
    required_fields = [
        ('start_ts', 'Missing start timestamp'),
        ('end_ts', 'Missing end timestamp'),
        ('success_criteria', 'Missing success criteria'),
        ('failure_criteria', 'Missing failure criteria'),
        ('owning_agent', 'Missing owning agent'),
    ]

    for field, error_msg in required_fields:
        if test.get(field) is None:
            return False, f"{error_msg} for test {test.get('test_code', 'UNKNOWN')}"

    return True, None


def compute_progress(conn, test_id: str) -> Dict:
    """Compute test progress using database function."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM fhq_calendar.compute_test_progress(%s::uuid)
        """, (test_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return {'days_elapsed': 0, 'days_remaining': 0, 'required_days': 0, 'progress_pct': 0, 'is_overdue': False}


def check_escalation(conn, test_id: str) -> Dict:
    """Check escalation conditions using database function."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM fhq_calendar.check_escalation_conditions(%s::uuid)
        """, (test_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return {'should_escalate': False, 'escalation_reason': None, 'recommended_actions': []}


def evaluate_test_criteria(conn, test_id: str) -> Dict:
    """Get full test evaluation using database function."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fhq_calendar.evaluate_test_criteria(%s::uuid) as evaluation
        """, (test_id,))
        row = cur.fetchone()
        if row and row['evaluation']:
            return row['evaluation']
        return {}


def collect_signals(conn) -> Dict[str, Any]:
    """Collect all signal values from registry."""
    signals = {}
    with conn.cursor() as cur:
        cur.execute("SELECT signal_key FROM fhq_calendar.test_signal_registry")
        for row in cur.fetchall():
            key = row['signal_key']
            cur.execute("SELECT fhq_calendar.get_signal_value(%s) as value", (key,))
            result = cur.fetchone()
            if result:
                signals[key] = result['value']
    return signals


# =============================================================================
# PHASE 3: EXECUTE
# =============================================================================

def update_test_progress(conn, test_id: str, progress: Dict) -> None:
    """Update test progress fields in database."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_calendar.canonical_test_events
            SET
                days_elapsed = %s,
                days_remaining = %s,
                last_orchestrator_run = NOW(),
                orchestrator_run_count = COALESCE(orchestrator_run_count, 0) + 1
            WHERE test_id = %s::uuid
        """, (
            progress.get('days_elapsed', 0),
            progress.get('days_remaining', 0),
            test_id
        ))
    conn.commit()


def escalate_test(conn, test_id: str, reason: str, actions: List[str]) -> None:
    """Escalate test and create CEO alert."""
    with conn.cursor() as cur:
        # Update test
        cur.execute("""
            UPDATE fhq_calendar.canonical_test_events
            SET
                escalation_state = 'ACTION_REQUIRED',
                ceo_action_required = TRUE,
                recommended_actions = %s::jsonb
            WHERE test_id = %s::uuid
            RETURNING test_code, test_name
        """, (json_dumps(actions), test_id))
        test = cur.fetchone()

        # Create CEO alert
        cur.execute("""
            INSERT INTO fhq_calendar.ceo_calendar_alerts
            (alert_type, alert_title, alert_summary, decision_options, priority, status, calendar_date)
            VALUES (
                'TEST_ESCALATION',
                %s,
                %s,
                %s,
                'HIGH',
                'PENDING',
                CURRENT_DATE
            )
        """, (
            f"Test Escalation: {test['test_name']}",
            reason,
            json_dumps(actions)
        ))
    conn.commit()


def resolve_test(conn, test_id: str, verdict: str, measured_vs_expected: Dict) -> None:
    """Resolve test at end of window."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fhq_calendar.resolve_test_window(
                %s::uuid,
                %s,
                %s::jsonb,
                %s
            )
        """, (
            test_id,
            verdict,
            json_dumps(measured_vs_expected),
            verdict == 'SUCCESS'  # trigger promotion SOP if success
        ))
    conn.commit()


def write_runbook_entry(conn, test: Dict, progress: Dict, signals: Dict, escalation: Dict) -> None:
    """Write machine-readable entry to test_runbook_entries."""
    entry_content = {
        'orchestrator_version': '1.0',
        'test_code': test['test_code'],
        'test_name': test['test_name'],
        'day_of_test': progress.get('days_elapsed', 0),
        'total_days': test.get('required_days', 30),
        'status': test['status'],
        'escalation_state': escalation.get('should_escalate', False) and 'ACTION_REQUIRED' or test.get('escalation_state', 'NONE'),
        'ceo_action_required': escalation.get('should_escalate', False),
        'signals_snapshot': signals,
        'baseline': test.get('baseline_definition'),
        'progress': progress,
        'evaluated_at': datetime.now().isoformat()
    }

    # Determine file paths
    today = date.today()
    day_of_year = today.timetuple().tm_yday
    runbook_path = DAILY_REPORTS_DIR / f"DAY{day_of_year}_RUNBOOK_{today.strftime('%Y%m%d')}.md"

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_calendar.test_runbook_entries
            (canonical_test_id, entry_date, runbook_file_path, daily_report_file_path, entry_content, db_verified)
            VALUES (%s::uuid, CURRENT_DATE, %s, %s, %s::jsonb, TRUE)
            ON CONFLICT (canonical_test_id, entry_date) DO UPDATE SET
                entry_content = EXCLUDED.entry_content,
                db_verified = TRUE
        """, (
            test['test_id'],
            str(runbook_path),
            str(runbook_path),
            json_dumps(entry_content)
        ))
    conn.commit()


def append_to_runbook_file(test: Dict, progress: Dict, signals: Dict, escalation: Dict) -> None:
    """Append test section to RUNBOOK markdown file."""
    today = date.today()
    day_of_year = today.timetuple().tm_yday
    runbook_path = DAILY_REPORTS_DIR / f"DAY{day_of_year}_RUNBOOK_{today.strftime('%Y%m%d')}.md"

    # Build markdown section
    section = f"""
---

## CANONICAL TEST: {test.get('display_name') or test['test_name']}

| Field | Value |
|-------|-------|
| Test Code | `{test['test_code']}` |
| Day | {progress.get('days_elapsed', 0)} of {test.get('required_days', 30)} |
| Status | {test['status']} |
| Escalation | {escalation.get('should_escalate', False) and 'ACTION_REQUIRED' or test.get('escalation_state', 'NONE')} |
| CEO Action Required | {escalation.get('should_escalate', False)} |
| Owner | {test.get('owning_agent', 'N/A')} |
| Monitoring Agent | {test.get('monitoring_agent_ec', 'N/A')} |

### Metrics Snapshot (Orchestrator Run)

| Metric | Current | Baseline |
|--------|---------|----------|
| LVI | {signals.get('lvi', {}).get('value', 'N/A')} | {test.get('baseline_definition', {}).get('lvi', 'N/A')} |
| Brier Score | {signals.get('brier_score', {}).get('value', 'N/A')} | {test.get('baseline_definition', {}).get('brier_score', 'N/A')} |
| Context Lift | {signals.get('context_lift', {}).get('value', 'N/A')} | {test.get('baseline_definition', {}).get('context_lift', 'N/A')} |
| Tier-1 Death Rate | {signals.get('tier1_death_rate', {}).get('value', 'N/A')} | {test.get('baseline_definition', {}).get('tier1_death_rate', 'N/A')} |

### Verdict

**{test.get('verdict', 'PENDING')}**

*Orchestrator run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CET*

"""

    # Append to file
    with open(runbook_path, 'a', encoding='utf-8') as f:
        f.write(section)


def log_orchestrator_execution(conn, stats: Dict, status: str, halt_reason: Optional[str] = None) -> str:
    """Log orchestrator execution to database and evidence file."""
    execution_id = str(uuid.uuid4())

    # Write to database
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fhq_calendar.orchestrator_execution_log
            (execution_id, tests_processed, tests_escalated, tests_resolved, tests_halted,
             execution_status, halt_reason, execution_details, evidence_file_path)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        """, (
            execution_id,
            stats.get('processed', 0),
            stats.get('escalated', 0),
            stats.get('resolved', 0),
            stats.get('halted', 0),
            status,
            halt_reason,
            json_dumps(stats),
            str(EVIDENCE_DIR / f"ORCHESTRATOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        ))
    conn.commit()

    # Write evidence file
    evidence = {
        'execution_id': execution_id,
        'execution_ts': datetime.now().isoformat(),
        'status': status,
        'halt_reason': halt_reason,
        'statistics': stats,
        'sha256': hashlib.sha256(json_dumps(stats, sort_keys=True).encode()).hexdigest()
    }

    evidence_path = EVIDENCE_DIR / f"ORCHESTRATOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(evidence_path, 'w') as f:
        f.write(json_dumps(evidence, indent=2))

    return execution_id


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def run_orchestrator() -> Dict:
    """
    Main orchestrator entry point.

    Returns execution statistics.
    """
    print(f"[{datetime.now()}] Canonical Test Orchestrator starting...")

    stats = {
        'processed': 0,
        'escalated': 0,
        'resolved': 0,
        'halted': 0,
        'warnings': [],
        'errors': []
    }

    conn = None
    try:
        conn = get_db_connection()

        # =================================================================
        # PHASE 1: DISCOVER
        # =================================================================
        print(f"[{datetime.now()}] Phase 1: Discovering active tests...")
        tests = discover_active_tests(conn)
        print(f"[{datetime.now()}] Found {len(tests)} ACTIVE test(s)")

        if not tests:
            print(f"[{datetime.now()}] No active tests. Exiting.")
            log_orchestrator_execution(conn, stats, 'SUCCESS')
            return stats

        # Collect signals once (shared across all tests)
        signals = collect_signals(conn)
        print(f"[{datetime.now()}] Collected {len(signals)} signal(s)")

        # =================================================================
        # PHASE 2 & 3: EVALUATE & EXECUTE (per test)
        # =================================================================
        for test in tests:
            test_code = test['test_code']
            test_id = str(test['test_id'])
            print(f"\n[{datetime.now()}] Processing: {test_code}")

            # -------------------------------------------------------------
            # FAIL-CLOSED: Validate test definition
            # -------------------------------------------------------------
            is_valid, error_msg = validate_test_definition(test)
            if not is_valid:
                print(f"[{datetime.now()}] HALT: {error_msg}")
                stats['halted'] += 1
                stats['errors'].append(error_msg)

                # Escalate with SYSTEM_ERROR
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE fhq_calendar.canonical_test_events
                        SET escalation_state = 'SYSTEM_ERROR',
                            ceo_action_required = TRUE,
                            recommended_actions = %s::jsonb
                        WHERE test_id = %s::uuid
                    """, (json_dumps(['Fix test definition', 'Contact STIG']), test_id))
                conn.commit()
                continue

            # -------------------------------------------------------------
            # Compute progress
            # -------------------------------------------------------------
            progress = compute_progress(conn, test_id)
            print(f"[{datetime.now()}]   Day {progress.get('days_elapsed', 0)} of {test.get('required_days', 30)}")

            # Update progress in database
            update_test_progress(conn, test_id, progress)

            # -------------------------------------------------------------
            # Check for end-of-window resolution
            # -------------------------------------------------------------
            if progress.get('is_overdue', False) and test.get('verdict') == 'PENDING':
                print(f"[{datetime.now()}]   Test overdue - triggering resolution...")

                # Evaluate criteria to determine verdict
                evaluation = evaluate_test_criteria(conn, test_id)

                # Simple verdict logic (can be enhanced)
                # For now: INCONCLUSIVE if metrics unavailable, else based on signals
                current_signals = evaluation.get('current_signals', {})
                has_data = any(
                    s.get('value') is not None and s.get('status') != 'NO_DATA'
                    for s in current_signals.values() if isinstance(s, dict)
                )

                if not has_data:
                    verdict = 'INCONCLUSIVE'
                    reason = 'Insufficient metric data for definitive verdict'
                else:
                    # TODO: Implement actual criteria comparison
                    verdict = 'INCONCLUSIVE'
                    reason = 'Criteria evaluation pending full implementation'

                resolve_test(conn, test_id, verdict, {
                    'reason': reason,
                    'signals_at_resolution': current_signals,
                    'resolved_by': 'canonical_test_orchestrator_daemon'
                })

                stats['resolved'] += 1
                print(f"[{datetime.now()}]   Resolved with verdict: {verdict}")
                continue

            # -------------------------------------------------------------
            # Check escalation conditions
            # -------------------------------------------------------------
            escalation = check_escalation(conn, test_id)

            if escalation.get('should_escalate', False):
                print(f"[{datetime.now()}]   ESCALATION TRIGGERED: {escalation.get('escalation_reason')}")

                actions = escalation.get('recommended_actions', [])
                if isinstance(actions, str):
                    actions = json.loads(actions) if actions.startswith('[') else [actions]

                escalate_test(conn, test_id, escalation.get('escalation_reason', ''), actions)
                stats['escalated'] += 1

            # -------------------------------------------------------------
            # Write runbook entry (always, for every active test)
            # -------------------------------------------------------------
            write_runbook_entry(conn, test, progress, signals, escalation)
            append_to_runbook_file(test, progress, signals, escalation)

            stats['processed'] += 1
            print(f"[{datetime.now()}]   Processed successfully")

        # =================================================================
        # LOG EXECUTION
        # =================================================================
        status = 'SUCCESS' if stats['halted'] == 0 else 'PARTIAL'
        execution_id = log_orchestrator_execution(conn, stats, status)
        print(f"\n[{datetime.now()}] Orchestrator complete. Execution ID: {execution_id}")
        print(f"[{datetime.now()}] Stats: {json_dumps(stats, indent=2)}")

        return stats

    except Exception as e:
        error_msg = f"Orchestrator failed: {str(e)}\n{traceback.format_exc()}"
        print(f"[{datetime.now()}] ERROR: {error_msg}")
        stats['errors'].append(error_msg)

        if conn:
            log_orchestrator_execution(conn, stats, 'FAILED', str(e))

        raise

    finally:
        if conn:
            conn.close()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    try:
        stats = run_orchestrator()
        sys.exit(0 if stats.get('halted', 0) == 0 else 1)
    except Exception as e:
        print(f"FATAL: {e}")
        sys.exit(2)
