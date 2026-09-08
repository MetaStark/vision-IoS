#!/usr/bin/env python3
"""
Calibration Gate Enforcer - CEO-DIR-2026-045
STIG (CTO) - System for Technical Implementation & Governance

CONSTITUTIONAL CONSTRAINT - NOT A TUNING PARAMETER

This script enforces confidence calibration gates based on historical accuracy.
It prevents "Algorithmic Arrogance" by capping confidence at proven accuracy levels.

PHASE 1: STATIC GATES (per CEO-DIR-2026-045)
- Gates are computed once from empirical data
- Gates are READ-ONLY - no adaptive updates
- Every gate requires VEGA attestation
- No recalibration until CEO authorizes Phase 2

CALIBRATION BANDS (derived from forecast_outcome_pairs):
  PRICE_DIRECTION:
    95-100% confidence -> 35.08% accuracy -> ceiling 40.08%
    80-95%  confidence -> 38.12% accuracy -> ceiling 43.12%
    60-80%  confidence -> 47.51% accuracy -> ceiling 52.51%
    40-60%  confidence -> 57.30% accuracy -> ceiling 62.30%
    0-40%   confidence -> 56.12% accuracy -> ceiling 61.12%

Usage:
    python calibration_gate_enforcer.py --status        # Show current gates
    python calibration_gate_enforcer.py --violations    # Show recent violations
    python calibration_gate_enforcer.py --test          # Test enforcement
"""

import os
import sys
import json
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from uuid import uuid4
from decimal import Decimal

DIRECTIVE_ID = "CEO-DIR-2026-045"
PHASE = "Phase 1 - Static Gates"
MIN_SAMPLE_SIZE = 10  # Lowered for Phase 1 to include all bands


def get_db_connection():
    """Create database connection."""
    return psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '54322'),
        database=os.environ.get('PGDATABASE', 'postgres'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', 'postgres')
    )


def calculate_asymmetric_safety_margin(accuracy: float) -> float:
    """
    Calculate asymmetric safety margin (Hardening #2).

    +5% when accuracy < 50% (maximum humility)
    +2% when accuracy >= 50% and < 60% (cautious recovery)
    +0% when accuracy >= 60% (earned confidence)
    """
    if accuracy < 0.50:
        return 0.05
    elif accuracy < 0.60:
        return 0.02
    else:
        return 0.00


def get_confidence_ceiling(conn, forecast_type: str, raw_confidence: float, regime: str = 'ALL') -> dict:
    """
    Get active confidence ceiling for a specific raw confidence value.

    The function finds the appropriate band for the raw_confidence and returns
    the ceiling for that band.

    Precedence order:
    1. Band match: (forecast_type, regime, band containing raw_confidence)
    2. Type + ALL fallback
    3. Global fallback: 0.50
    """
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get ceiling for the specific confidence band
    cursor.execute("""
        SELECT ceiling, gate_id, match_type, historical_accuracy, sample_size, band_matched
        FROM fhq_governance.get_active_confidence_ceiling(%s, %s, %s)
    """, (forecast_type, raw_confidence, regime))

    result = cursor.fetchone()
    cursor.close()

    if result:
        return {
            'ceiling': float(result['ceiling']) if result['ceiling'] else 0.50,
            'gate_id': str(result['gate_id']) if result['gate_id'] else None,
            'match_type': result['match_type'],
            'historical_accuracy': float(result['historical_accuracy']) if result['historical_accuracy'] else None,
            'sample_size': result['sample_size'],
            'band_matched': result['band_matched']
        }

    # Fallback (shouldn't reach here if function works correctly)
    return {
        'ceiling': 0.50,
        'gate_id': None,
        'match_type': 'GLOBAL_FALLBACK',
        'historical_accuracy': None,
        'sample_size': None,
        'band_matched': None
    }


def enforce_gate(conn, forecast_id: str, confidence: float,
                 forecast_type: str, regime: str = 'ALL') -> dict:
    """
    Enforce calibration gate on a confidence value.
    Returns adjusted confidence and metadata.
    """
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT adjusted_confidence, was_capped, gate_id, match_type
        FROM fhq_governance.enforce_calibration_gate(%s, %s, %s, %s)
    """, (forecast_id, confidence, forecast_type, regime))

    result = cursor.fetchone()
    conn.commit()
    cursor.close()

    return {
        'adjusted_confidence': float(result['adjusted_confidence']),
        'was_capped': result['was_capped'],
        'gate_id': str(result['gate_id']) if result['gate_id'] else None,
        'match_type': result['match_type'],
        'original_confidence': confidence,
        'reduction': round(confidence - float(result['adjusted_confidence']), 4) if result['was_capped'] else 0
    }


def recalculate_gates(conn, window_days: int = 30,
                      min_sample_size: int = 100, approver: str = 'STIG') -> list:
    """
    Recalculate all calibration gates from recent forecast outcomes.
    Uses asymmetric safety margin and respects sample-size floor.
    """
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT forecast_type, regime, historical_accuracy, sample_size,
               safety_margin, new_ceiling, status
        FROM fhq_governance.recalculate_calibration_gates(%s, %s, %s)
    """, (window_days, min_sample_size, approver))

    results = cursor.fetchall()
    conn.commit()
    cursor.close()

    return [dict(row) for row in results]


def get_current_gates(conn) -> list:
    """Get all active calibration gates."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT gate_id, forecast_type, regime, historical_accuracy,
               sample_size, confidence_ceiling, safety_margin,
               calculation_window_days, effective_from, approved_by
        FROM fhq_governance.confidence_calibration_gates
        WHERE effective_until IS NULL
        ORDER BY forecast_type, regime
    """)

    results = cursor.fetchall()
    cursor.close()

    return [dict(row) for row in results]


def get_recent_violations(conn, limit: int = 50) -> list:
    """Get recent gate violations."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT violation_id, forecast_id, original_confidence, applied_ceiling,
               confidence_reduction, forecast_type, regime, violation_timestamp,
               enforced_by
        FROM fhq_governance.gate_violation_log
        ORDER BY violation_timestamp DESC
        LIMIT %s
    """, (limit,))

    results = cursor.fetchall()
    cursor.close()

    return [dict(row) for row in results]


def get_calibration_summary(conn) -> dict:
    """Get overall calibration metrics."""
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Overall accuracy by forecast type
    cursor.execute("""
        SELECT
            fl.forecast_type,
            COUNT(*) as total_forecasts,
            SUM(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END) as correct,
            ROUND(100.0 * SUM(CASE WHEN fop.hit_rate_contribution THEN 1 ELSE 0 END)::numeric
                  / NULLIF(COUNT(*), 0), 2) as accuracy_pct,
            ROUND(AVG(fop.brier_score)::numeric, 4) as avg_brier
        FROM fhq_research.forecast_outcome_pairs fop
        JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
        WHERE fop.reconciled_at >= NOW() - INTERVAL '30 days'
        GROUP BY fl.forecast_type
        ORDER BY fl.forecast_type
    """)

    accuracy_data = [dict(row) for row in cursor.fetchall()]

    # Violation stats
    cursor.execute("""
        SELECT
            COUNT(*) as total_violations,
            AVG(confidence_reduction) as avg_reduction,
            MAX(confidence_reduction) as max_reduction
        FROM fhq_governance.gate_violation_log
        WHERE violation_timestamp >= NOW() - INTERVAL '7 days'
    """)

    violation_stats = dict(cursor.fetchone())

    cursor.close()

    return {
        'accuracy_by_type': accuracy_data,
        'violation_stats': violation_stats,
        'timestamp': datetime.now().isoformat()
    }


def log_evidence(conn, action: str, data: dict):
    """Log evidence file for court-proof compliance."""
    evidence = {
        'directive_id': DIRECTIVE_ID,
        'action': action,
        'executed_by': 'STIG',
        'execution_timestamp': datetime.now().isoformat(),
        'data': data
    }

    evidence_path = os.path.join(
        os.path.dirname(__file__),
        'evidence',
        f'CEO_DIR_2026_032_{action}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )

    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2, default=str)

    print(f"  [OK] Evidence logged: {os.path.basename(evidence_path)}")
    return evidence_path


def main():
    parser = argparse.ArgumentParser(
        description='Calibration Gate Enforcer - CEO-DIR-2026-032'
    )
    parser.add_argument('--recalculate', action='store_true',
                        help='Recalculate gates from recent data')
    parser.add_argument('--status', action='store_true',
                        help='Show current gate status')
    parser.add_argument('--violations', action='store_true',
                        help='Show recent violations')
    parser.add_argument('--summary', action='store_true',
                        help='Show calibration summary')
    parser.add_argument('--test', action='store_true',
                        help='Test gate enforcement with sample confidence')
    parser.add_argument('--window', type=int, default=30,
                        help='Calculation window in days (default: 30)')
    parser.add_argument('--min-samples', type=int, default=100,
                        help='Minimum sample size for gate activation (default: 100)')

    args = parser.parse_args()

    print("=" * 60)
    print("CALIBRATION GATE ENFORCER")
    print(f"Directive: {DIRECTIVE_ID}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    conn = get_db_connection()

    try:
        if args.recalculate:
            print("\n--- RECALCULATING GATES ---")
            print(f"Window: {args.window} days | Min samples: {args.min_samples}")

            results = recalculate_gates(conn, args.window, args.min_samples)

            if results:
                print(f"\n  Updated {len(results)} gates:")
                for r in results:
                    margin_pct = f"+{r['safety_margin']*100:.0f}%" if r['safety_margin'] else "+0%"
                    print(f"    {r['forecast_type']}/{r['regime']}: "
                          f"accuracy={r['historical_accuracy']*100:.1f}% "
                          f"({margin_pct}) → ceiling={r['new_ceiling']*100:.1f}% "
                          f"(n={r['sample_size']})")

                log_evidence(conn, 'RECALIBRATION', {'gates_updated': results})
            else:
                print("  No gates met minimum sample size requirements.")

        elif args.status:
            print("\n--- CURRENT GATES ---")
            gates = get_current_gates(conn)

            if gates:
                for g in gates:
                    print(f"\n  [{g['forecast_type']}/{g['regime']}]")
                    print(f"    Ceiling: {float(g['confidence_ceiling'])*100:.1f}%")
                    print(f"    Accuracy: {float(g['historical_accuracy'])*100:.1f}%")
                    print(f"    Safety Margin: +{float(g['safety_margin'])*100:.0f}%")
                    print(f"    Sample Size: {g['sample_size']}")
                    print(f"    Approved by: {g['approved_by']}")
            else:
                print("  No active gates found.")

        elif args.violations:
            print("\n--- RECENT VIOLATIONS ---")
            violations = get_recent_violations(conn)

            if violations:
                print(f"  Last {len(violations)} violations:")
                for v in violations:
                    print(f"\n    {v['violation_timestamp']}")
                    print(f"    Type: {v['forecast_type']}/{v['regime']}")
                    print(f"    Original: {float(v['original_confidence'])*100:.1f}% → "
                          f"Capped: {float(v['applied_ceiling'])*100:.1f}%")
                    print(f"    Reduction: {float(v['confidence_reduction'])*100:.1f}%")
            else:
                print("  No violations recorded.")

        elif args.summary:
            print("\n--- CALIBRATION SUMMARY ---")
            summary = get_calibration_summary(conn)

            print("\n  Accuracy by Forecast Type (30-day):")
            for a in summary['accuracy_by_type']:
                print(f"    {a['forecast_type']}: {a['accuracy_pct']}% "
                      f"({a['correct']}/{a['total_forecasts']}) "
                      f"Brier: {a['avg_brier']}")

            print("\n  Violation Stats (7-day):")
            vs = summary['violation_stats']
            if vs['total_violations']:
                print(f"    Total: {vs['total_violations']}")
                print(f"    Avg Reduction: {float(vs['avg_reduction'])*100:.1f}%")
                print(f"    Max Reduction: {float(vs['max_reduction'])*100:.1f}%")
            else:
                print("    No violations in last 7 days.")

        elif args.test:
            print("\n--- TEST GATE ENFORCEMENT ---")
            test_forecast_id = str(uuid4())

            # Test with high confidence
            for test_conf in [0.95, 0.80, 0.60, 0.45]:
                result = enforce_gate(conn, test_forecast_id, test_conf,
                                       'PRICE_DIRECTION', 'ALL')
                status = "CAPPED" if result['was_capped'] else "PASSED"
                print(f"\n  Input: {test_conf*100:.0f}% -> Output: "
                      f"{result['adjusted_confidence']*100:.1f}% [{status}]")
                print(f"    Match: {result['match_type']}")
                if result['was_capped']:
                    print(f"    Reduction: {result['reduction']*100:.1f}%")

        else:
            # Default: show status
            print("\n--- CURRENT GATES ---")
            gates = get_current_gates(conn)

            if gates:
                for g in gates:
                    print(f"  {g['forecast_type']}/{g['regime']}: "
                          f"ceiling={float(g['confidence_ceiling'])*100:.1f}% "
                          f"(accuracy={float(g['historical_accuracy'])*100:.1f}%, n={g['sample_size']})")
            else:
                print("  No active gates. Run --recalculate to initialize.")

    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("ENFORCER COMPLETE")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
