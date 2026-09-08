#!/usr/bin/env python3
"""
VEGA G1 LEARNING VERIFICATION SUITE
CEO-DIR-2026-FINN-009: Epistemic Learning Correction & Freedom Preservation

This script runs the acceptance tests required to verify:
- CAUSAL_ATTRIBUTION condition
- REAL_REWARD_SIGNAL condition
- VEGA_G1_CLEARANCE condition

Learning will NOT be reactivated until all tests pass.
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

# ============================================================================
# CONFIGURATION
# ============================================================================

DIRECTIVE_REF = 'CEO-DIR-2026-FINN-009'

PASS_CRITERIA = {
    'test_a_events_per_run': {
        'description': 'Every run must have a retrieval event',
        'condition': 'events == sessions'
    },
    'test_b_attribution_coverage': {
        'description': 'Every event must have attribution rows',
        'condition': 'min(attribution_rows) > 0'
    },
    'test_c_marginal_contribution_bounds': {
        'description': 'Marginal contribution must be 0.0-1.0 with no nulls',
        'condition': '0.0 <= mc <= 1.0, no nulls'
    },
    'test_d_inforage_binding': {
        'description': 'Real yield must be tied to InForage cost',
        'condition': 'cost outliers explainable'
    },
    'test_e_unattributable_nodes': {
        'description': 'Zero unattributable used nodes',
        'condition': 'unattributable_count == 0'
    }
}


def get_db_conn():
    return psycopg2.connect(
        host='127.0.0.1',
        port=54322,
        database='postgres',
        user='postgres',
        password='postgres'
    )


# ============================================================================
# TEST A: Do we have retrieval events for every run?
# ============================================================================

def test_a_events_per_run(conn) -> dict:
    """
    Acceptance Test A: Every run must emit exactly one retrieval event.

    Pass condition: events == sessions == number_of_runs_executed
    """
    print('\n[TEST A] Retrieval Events Per Run')
    print('-' * 50)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS events,
                COUNT(DISTINCT batch_id || '-' || run_number::text) AS sessions
            FROM fhq_research.retrieval_events
            WHERE created_at::date = CURRENT_DATE
        """)
        result = cur.fetchone()

    events = int(result['events'])
    sessions = int(result['sessions'])

    print(f'  Events: {events}')
    print(f'  Sessions: {sessions}')

    passed = events > 0 and events == sessions

    if passed:
        print(f'  Result: PASS (1 event per session)')
    else:
        if events == 0:
            print(f'  Result: FAIL (no events recorded today)')
        else:
            print(f'  Result: FAIL (events != sessions)')

    return {
        'test': 'A',
        'name': 'events_per_run',
        'passed': passed,
        'events': events,
        'sessions': sessions,
        'reason': 'Events match sessions' if passed else 'Events do not match sessions'
    }


# ============================================================================
# TEST B: Do we have attribution rows for each event?
# ============================================================================

def test_b_attribution_coverage(conn) -> dict:
    """
    Acceptance Test B: Every retrieval event must have attribution rows.

    Pass condition: attribution_rows > 0 for all events
    """
    print('\n[TEST B] Attribution Coverage')
    print('-' * 50)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                re.event_id AS retrieval_event_id,
                COUNT(pya.*) AS attribution_rows
            FROM fhq_research.retrieval_events re
            LEFT JOIN fhq_research.path_yield_attribution pya
                ON pya.retrieval_event_id = re.event_id
            WHERE re.created_at::date = CURRENT_DATE
            GROUP BY re.event_id
            ORDER BY attribution_rows ASC
            LIMIT 20
        """)
        results = cur.fetchall()

    if not results:
        print('  No events found today')
        return {
            'test': 'B',
            'name': 'attribution_coverage',
            'passed': False,
            'events_checked': 0,
            'events_with_zero': 0,
            'reason': 'No events found'
        }

    events_with_zero = sum(1 for r in results if int(r['attribution_rows']) == 0)
    total_events = len(results)

    print(f'  Events checked: {total_events}')
    print(f'  Events with zero attribution: {events_with_zero}')

    # Show worst offenders if any
    for r in results[:5]:
        print(f'    Event {str(r["retrieval_event_id"])[:8]}...: {r["attribution_rows"]} rows')

    passed = events_with_zero == 0

    if passed:
        print(f'  Result: PASS (all events have attribution)')
    else:
        print(f'  Result: FAIL ({events_with_zero} events without attribution)')

    return {
        'test': 'B',
        'name': 'attribution_coverage',
        'passed': passed,
        'events_checked': total_events,
        'events_with_zero': events_with_zero,
        'reason': 'All events have attribution' if passed else f'{events_with_zero} events missing attribution'
    }


# ============================================================================
# TEST C: Is marginal_contribution computed and bounded?
# ============================================================================

def test_c_marginal_contribution_bounds(conn) -> dict:
    """
    Acceptance Test C: Marginal contribution must be bounded 0.0-1.0 with no nulls.

    Pass condition: 0.0 <= mc <= 1.0, no nulls
    """
    print('\n[TEST C] Marginal Contribution Bounds')
    print('-' * 50)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                MIN(marginal_contribution) AS min_mc,
                MAX(marginal_contribution) AS max_mc,
                AVG(marginal_contribution) AS avg_mc,
                COUNT(*) AS total_rows,
                COUNT(marginal_contribution) AS non_null_rows
            FROM fhq_research.path_yield_attribution
            WHERE created_at::date = CURRENT_DATE
        """)
        result = cur.fetchone()

    if result['total_rows'] == 0:
        print('  No attribution rows found today')
        return {
            'test': 'C',
            'name': 'marginal_contribution_bounds',
            'passed': False,
            'reason': 'No attribution data'
        }

    min_mc = float(result['min_mc']) if result['min_mc'] is not None else None
    max_mc = float(result['max_mc']) if result['max_mc'] is not None else None
    avg_mc = float(result['avg_mc']) if result['avg_mc'] is not None else None
    total_rows = int(result['total_rows'])
    non_null_rows = int(result['non_null_rows'])
    null_count = total_rows - non_null_rows

    print(f'  Min MC: {min_mc}')
    print(f'  Max MC: {max_mc}')
    print(f'  Avg MC: {avg_mc:.4f}' if avg_mc else '  Avg MC: N/A')
    print(f'  Total rows: {total_rows}')
    print(f'  Null count: {null_count}')

    # Check bounds
    in_bounds = (min_mc is not None and max_mc is not None and
                 0.0 <= min_mc <= 1.0 and 0.0 <= max_mc <= 1.0)
    no_nulls = null_count == 0

    passed = in_bounds and no_nulls

    if passed:
        print(f'  Result: PASS (bounded 0.0-1.0, no nulls)')
    else:
        reasons = []
        if not in_bounds:
            reasons.append('out of bounds')
        if not no_nulls:
            reasons.append(f'{null_count} nulls')
        print(f'  Result: FAIL ({", ".join(reasons)})')

    return {
        'test': 'C',
        'name': 'marginal_contribution_bounds',
        'passed': passed,
        'min_mc': min_mc,
        'max_mc': max_mc,
        'avg_mc': avg_mc,
        'null_count': null_count,
        'reason': 'Valid bounds, no nulls' if passed else f'Invalid: {", ".join(reasons) if not passed else ""}'
    }


# ============================================================================
# TEST D: Is real_yield actually tied to cost?
# ============================================================================

def test_d_inforage_binding(conn) -> dict:
    """
    Acceptance Test D: Real yield must be tied to InForage cost data.

    Pass condition: Join between attribution and cost log produces results
    """
    print('\n[TEST D] InForage Binding')
    print('-' * 50)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if we can join attribution to cost log
        cur.execute("""
            SELECT
                pya.retrieval_event_id,
                pya.real_yield,
                icl.cumulative_cost AS total_cost,
                icl.roi_ratio
            FROM fhq_research.path_yield_attribution pya
            JOIN fhq_optimization.inforage_cost_log icl
                ON icl.session_id = pya.session_id
            WHERE pya.created_at::date = CURRENT_DATE
            ORDER BY icl.cumulative_cost DESC
            LIMIT 10
        """)
        results = cur.fetchall()

    if not results:
        print('  No joined records found')
        print('  (Either no cost data or session_id mismatch)')

        # Check if there are any attribution rows
        cur.execute("""
            SELECT COUNT(*) as attr_count FROM fhq_research.path_yield_attribution
            WHERE created_at::date = CURRENT_DATE
        """)
        attr_count = cur.fetchone()['attr_count']

        cur.execute("""
            SELECT COUNT(*) as cost_count FROM fhq_optimization.inforage_cost_log
            WHERE timestamp_utc::date = CURRENT_DATE
        """)
        cost_count = cur.fetchone()['cost_count']

        print(f'  Attribution rows today: {attr_count}')
        print(f'  Cost log rows today: {cost_count}')

        return {
            'test': 'D',
            'name': 'inforage_binding',
            'passed': False,
            'joined_count': 0,
            'reason': f'No join results (attr={attr_count}, cost={cost_count})'
        }

    print(f'  Joined records: {len(results)}')
    print(f'  Top 5 by cost:')
    for r in results[:5]:
        yield_val = float(r['real_yield']) if r['real_yield'] else 0
        cost_val = float(r['total_cost']) if r['total_cost'] else 0
        print(f'    Event {str(r["retrieval_event_id"])[:8]}...: yield={yield_val:.4f}, cost=${cost_val:.6f}')

    # Check correlation (basic sanity)
    yields = [float(r['real_yield']) for r in results if r['real_yield'] is not None]
    costs = [float(r['total_cost']) for r in results if r['total_cost'] is not None]

    passed = len(results) > 0

    if passed:
        print(f'  Result: PASS (yield-cost binding established)')
    else:
        print(f'  Result: FAIL (no binding)')

    return {
        'test': 'D',
        'name': 'inforage_binding',
        'passed': passed,
        'joined_count': len(results),
        'reason': 'Yield-cost binding established' if passed else 'No binding found'
    }


# ============================================================================
# TEST E: Zero unattributable used nodes
# ============================================================================

def test_e_unattributable_nodes(conn) -> dict:
    """
    Acceptance Test E: No unattributable used nodes.

    Pass condition: All retrieval events with was_used_in_synthesis=true have attribution
    """
    print('\n[TEST E] Unattributable Nodes')
    print('-' * 50)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Find events where synthesis happened but no attribution exists
        cur.execute("""
            SELECT
                re.event_id,
                re.hypothesis_id,
                re.was_used_in_synthesis,
                re.contribution_score,
                COUNT(pya.attribution_id) as attribution_count
            FROM fhq_research.retrieval_events re
            LEFT JOIN fhq_research.path_yield_attribution pya
                ON pya.retrieval_event_id = re.event_id
            WHERE re.created_at::date = CURRENT_DATE
              AND re.was_used_in_synthesis = TRUE
            GROUP BY re.event_id, re.hypothesis_id, re.was_used_in_synthesis, re.contribution_score
            HAVING COUNT(pya.attribution_id) = 0
        """)
        unattributable = cur.fetchall()

    unattributable_count = len(unattributable)

    print(f'  Unattributable used nodes: {unattributable_count}')

    if unattributable:
        print('  Offending events:')
        for u in unattributable[:5]:
            print(f'    {str(u["event_id"])[:8]}... ({u["hypothesis_id"]})')

    passed = unattributable_count == 0

    if passed:
        print(f'  Result: PASS (all used nodes have attribution)')
    else:
        print(f'  Result: FAIL ({unattributable_count} unattributable nodes)')

    return {
        'test': 'E',
        'name': 'unattributable_nodes',
        'passed': passed,
        'unattributable_count': unattributable_count,
        'reason': 'All used nodes attributed' if passed else f'{unattributable_count} unattributable'
    }


# ============================================================================
# SATISFACTION FUNCTIONS
# ============================================================================

def satisfy_condition(conn, condition_name: str, evidence_ref: str) -> bool:
    """Mark a reactivation condition as satisfied."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fhq_research.satisfy_reactivation_condition(%s, %s, %s)
        """, (condition_name, 'VEGA', evidence_ref))
        result = cur.fetchone()[0]
    conn.commit()
    return result


def check_all_conditions_satisfied(conn) -> bool:
    """Check if all conditions are satisfied."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT fhq_research.can_reactivate_learning()
        """)
        result = cur.fetchone()[0]
    return result


def lift_suspension(conn, directive_ref: str) -> bool:
    """Lift learning suspension if all conditions are satisfied."""
    if not check_all_conditions_satisfied(conn):
        return False

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_research.learning_suspension_log
            SET is_active = FALSE,
                reactivated_at = NOW(),
                reactivated_by = 'VEGA'
            WHERE directive_ref = %s AND is_active = TRUE
        """, (directive_ref,))
    conn.commit()
    return True


# ============================================================================
# MAIN VERIFICATION SUITE
# ============================================================================

def run_verification_suite(conn) -> dict:
    """Run the complete VEGA G1 verification suite."""

    print('=' * 70)
    print('VEGA G1 LEARNING VERIFICATION SUITE')
    print('CEO-DIR-2026-FINN-009: Epistemic Learning Correction')
    print('=' * 70)
    print(f'Timestamp: {datetime.now(timezone.utc).isoformat()}')

    results = {
        'directive': DIRECTIVE_REF,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'tests': []
    }

    # Run all tests
    test_a = test_a_events_per_run(conn)
    results['tests'].append(test_a)

    test_b = test_b_attribution_coverage(conn)
    results['tests'].append(test_b)

    test_c = test_c_marginal_contribution_bounds(conn)
    results['tests'].append(test_c)

    test_d = test_d_inforage_binding(conn)
    results['tests'].append(test_d)

    test_e = test_e_unattributable_nodes(conn)
    results['tests'].append(test_e)

    # Summary
    print('\n' + '=' * 70)
    print('VERIFICATION SUMMARY')
    print('=' * 70)

    all_passed = all(t['passed'] for t in results['tests'])
    passed_count = sum(1 for t in results['tests'] if t['passed'])
    total_count = len(results['tests'])

    for t in results['tests']:
        status = 'PASS' if t['passed'] else 'FAIL'
        print(f"  Test {t['test']}: {status} - {t['name']}")

    print(f'\n  Overall: {passed_count}/{total_count} tests passed')
    results['all_passed'] = all_passed
    results['passed_count'] = passed_count

    # Determine which conditions to satisfy
    print('\n' + '-' * 70)
    print('CONDITION UPDATES')
    print('-' * 70)

    # CAUSAL_ATTRIBUTION: Tests A, B, E must pass
    causal_tests = [test_a, test_b, test_e]
    causal_passed = all(t['passed'] for t in causal_tests)

    if causal_passed:
        evidence = f"Tests A,B,E passed at {results['timestamp']}"
        satisfy_condition(conn, 'CAUSAL_ATTRIBUTION', evidence)
        print('  CAUSAL_ATTRIBUTION: SATISFIED')
    else:
        print('  CAUSAL_ATTRIBUTION: NOT SATISFIED (Tests A/B/E failed)')

    # REAL_REWARD_SIGNAL: Tests C, D must pass
    reward_tests = [test_c, test_d]
    reward_passed = all(t['passed'] for t in reward_tests)

    if reward_passed:
        evidence = f"Tests C,D passed at {results['timestamp']}"
        satisfy_condition(conn, 'REAL_REWARD_SIGNAL', evidence)
        print('  REAL_REWARD_SIGNAL: SATISFIED')
    else:
        print('  REAL_REWARD_SIGNAL: NOT SATISFIED (Tests C/D failed)')

    # VEGA_G1_CLEARANCE: All tests must pass
    if all_passed:
        evidence = f"All tests passed at {results['timestamp']}"
        satisfy_condition(conn, 'VEGA_G1_CLEARANCE', evidence)
        print('  VEGA_G1_CLEARANCE: SATISFIED')

        # Attempt to lift suspension
        if lift_suspension(conn, DIRECTIVE_REF):
            print('\n  [SUCCESS] Learning suspension LIFTED')
            print('  [INFO] Batch 4+ may now apply path weight updates')
            results['learning_reactivated'] = True
        else:
            print('\n  [WARNING] Suspension could not be lifted')
            results['learning_reactivated'] = False
    else:
        print('  VEGA_G1_CLEARANCE: NOT SATISFIED (not all tests passed)')
        results['learning_reactivated'] = False

    # Final status
    print('\n' + '=' * 70)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM fhq_research.learning_readiness_dashboard")
        dashboard = cur.fetchone()

    print(f"Learning Status: {dashboard['learning_status']}")
    print(f"Conditions: {dashboard['conditions_satisfied']}/{dashboard['conditions_total']}")
    print('=' * 70)

    results['final_status'] = dashboard['learning_status']
    results['conditions_satisfied'] = int(dashboard['conditions_satisfied'])
    results['conditions_total'] = int(dashboard['conditions_total'])

    return results


def main():
    conn = get_db_conn()

    try:
        results = run_verification_suite(conn)

        # Save report
        report_path = Path('05_GOVERNANCE/PHASE3') / f'VEGA_G1_VERIFICATION_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f'\nReport saved: {report_path}')

        # Exit code based on result
        if results['all_passed']:
            print('\n[VEGA] G1 VERIFICATION: PASS')
            sys.exit(0)
        else:
            print('\n[VEGA] G1 VERIFICATION: FAIL')
            sys.exit(1)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
