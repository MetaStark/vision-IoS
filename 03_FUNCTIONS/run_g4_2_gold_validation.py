#!/usr/bin/env python3
"""
G4.2 Contextual Orchestration - GOLD Signals Validation
CEO Directive WAVE 16C - 2025-12-18

Validates 22 GOLD (CONDITIONAL) signals with context gating.
Implements "Permission to Speak" protocol.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '54322'),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


def main():
    print("=" * 70)
    print("G4.2 CONTEXTUAL ORCHESTRATION - 22 GOLD SIGNALS")
    print("CEO Directive WAVE 16C: Permission to Speak Protocol")
    print("=" * 70)

    conn = psycopg2.connect(**DB_CONFIG)

    # Get GOLD signals
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                gn.needle_id,
                gn.hypothesis_title,
                gn.hypothesis_category,
                gn.target_asset,
                gn.price_witness_symbol,
                gn.hypothesis_statement,
                sc.classification,
                sc.oos_sharpe,
                cv.edge_assessment as g4_1_assessment
            FROM fhq_canonical.g4_composite_scorecard sc
            JOIN fhq_canonical.golden_needles gn ON sc.needle_id = gn.needle_id
            LEFT JOIN fhq_canonical.g4_1_composite_verdict cv ON sc.needle_id = cv.needle_id
            WHERE sc.classification = 'GOLD'
            ORDER BY sc.oos_sharpe DESC
        """)
        gold_needles = cur.fetchall()

    print(f"\nGOLD signals to validate: {len(gold_needles)}")
    print(f"Started at: {datetime.now().isoformat()}\n")

    # Clear previous G4.2 results for these needles
    with conn.cursor() as cur:
        needle_ids = [str(n['needle_id']) for n in gold_needles]
        cur.execute("""
            DELETE FROM fhq_canonical.g4_2_composite_verdict
            WHERE needle_id = ANY(%s::uuid[])
        """, (needle_ids,))
        cur.execute("""
            DELETE FROM fhq_canonical.g4_2_contextual_backtest
            WHERE needle_id = ANY(%s::uuid[])
        """, (needle_ids,))
        cur.execute("""
            DELETE FROM fhq_canonical.g4_2_context_profiles
            WHERE needle_id = ANY(%s::uuid[])
        """, (needle_ids,))
        conn.commit()
        print("Cleared previous G4.2 results\n")

    conn.close()

    # Import and run G4.2 engine
    from g4_2_contextual_orchestration_engine import G4_2_ContextualOrchestrationEngine

    engine = G4_2_ContextualOrchestrationEngine()

    results = {
        'VALIDATED-CONTEXTUAL': [],
        'UNSTABLE-CONTEXTUAL': [],
        'INSUFFICIENT_SAMPLE': [],
        'ILLUSORY': [],
        'NO_VALID_CONTEXT': []
    }

    for i, needle in enumerate(gold_needles, 1):
        needle_dict = dict(needle)
        title = needle['hypothesis_title'][:45]
        g4_1_assessment = needle.get('g4_1_assessment', 'N/A')

        print(f"[{i:2d}/{len(gold_needles)}] {title}")
        print(f"         G4.1: {g4_1_assessment}")

        try:
            result = engine.run_full_validation(needle_dict)
            classification = result.get('classification', 'UNKNOWN')
            g5_eligible = result.get('g5_eligible', False)
            best_context = result.get('best_context', 'None')
            best_sharpe = result.get('best_sharpe')

            status = {
                'VALIDATED-CONTEXTUAL': '[VALID] ',
                'UNSTABLE-CONTEXTUAL': '[UNSTAB]',
                'INSUFFICIENT_SAMPLE': '[INSUFF]',
                'ILLUSORY': '[ILLUS] ',
                'NO_VALID_CONTEXT': '[NOCON] '
            }.get(classification, '[???]   ')

            sharpe_str = f"{best_sharpe:.2f}" if best_sharpe else "N/A"
            print(f"         {status} Context: {best_context}, Sharpe: {sharpe_str}, G5: {g5_eligible}\n")

            if classification in results:
                results[classification].append({
                    'needle_id': str(needle['needle_id']),
                    'title': needle['hypothesis_title'],
                    'best_context': best_context,
                    'best_sharpe': best_sharpe,
                    'g5_eligible': g5_eligible
                })

        except Exception as e:
            import traceback
            print(f"         [ERROR] {str(e)[:60]}")
            traceback.print_exc()
            print()

    engine.close()

    # Summary
    print("\n" + "=" * 70)
    print("G4.2 VALIDATION RESULTS - 22 GOLD SIGNALS")
    print("=" * 70)

    print(f"\n  VALIDATED-CONTEXTUAL: {len(results['VALIDATED-CONTEXTUAL']):2d}  (G5 eligible)")
    print(f"  UNSTABLE-CONTEXTUAL:  {len(results['UNSTABLE-CONTEXTUAL']):2d}")
    print(f"  INSUFFICIENT_SAMPLE:  {len(results['INSUFFICIENT_SAMPLE']):2d}")
    print(f"  ILLUSORY:             {len(results['ILLUSORY']):2d}")
    print(f"  NO_VALID_CONTEXT:     {len(results['NO_VALID_CONTEXT']):2d}")

    # Get database summary
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                final_classification,
                COUNT(*) as count,
                COUNT(*) FILTER (WHERE g5_eligible = true) as g5_count,
                ROUND(AVG(best_contextual_sharpe)::numeric, 4) as avg_sharpe,
                ROUND(AVG(best_suppression_rate)::numeric, 4) as avg_suppression
            FROM fhq_canonical.g4_2_composite_verdict cv
            JOIN fhq_canonical.g4_composite_scorecard sc ON cv.needle_id = sc.needle_id
            WHERE sc.classification = 'GOLD'
            GROUP BY final_classification
            ORDER BY
                CASE final_classification
                    WHEN 'VALIDATED-CONTEXTUAL' THEN 1
                    WHEN 'UNSTABLE-CONTEXTUAL' THEN 2
                    WHEN 'INSUFFICIENT_SAMPLE' THEN 3
                    WHEN 'ILLUSORY' THEN 4
                    WHEN 'NO_VALID_CONTEXT' THEN 5
                END
        """)
        db_results = cur.fetchall()

        if db_results:
            print("\n  DATABASE SUMMARY:")
            print("  " + "-" * 60)
            print(f"  {'Classification':<25} {'Count':>6} {'G5':>4} {'Sharpe':>8} {'Suppression':>12}")
            print("  " + "-" * 60)
            for r in db_results:
                sharpe = f"{r['avg_sharpe']:.2f}" if r['avg_sharpe'] else "N/A"
                supp = f"{r['avg_suppression']:.1%}" if r['avg_suppression'] else "N/A"
                print(f"  {r['final_classification']:<25} {r['count']:>6} {r['g5_count']:>4} {sharpe:>8} {supp:>12}")

        # Check total G5 eligibility
        cur.execute("""
            SELECT COUNT(*) as g5_total
            FROM fhq_canonical.g4_2_composite_verdict
            WHERE g5_eligible = true
        """)
        g5_total = cur.fetchone()['g5_total']
        print(f"\n  TOTAL G5 ELIGIBLE: {g5_total}")

        # Show best performers
        cur.execute("""
            SELECT
                gn.hypothesis_title,
                cv.best_context_name,
                cv.best_contextual_sharpe,
                cv.best_suppression_rate,
                cv.g5_eligible
            FROM fhq_canonical.g4_2_composite_verdict cv
            JOIN fhq_canonical.golden_needles gn ON cv.needle_id = gn.needle_id
            WHERE cv.final_classification = 'VALIDATED-CONTEXTUAL'
            ORDER BY cv.best_contextual_sharpe DESC
            LIMIT 5
        """)
        top_performers = cur.fetchall()

        if top_performers:
            print("\n  TOP VALIDATED-CONTEXTUAL SIGNALS:")
            print("  " + "-" * 60)
            for p in top_performers:
                title = p['hypothesis_title'][:40]
                sharpe = p['best_contextual_sharpe'] or 0
                supp = (p['best_suppression_rate'] or 0) * 100
                print(f"    {title}")
                print(f"      Context: {p['best_context_name']}, Sharpe: {sharpe:.2f}, Suppression: {supp:.0f}%")

    conn.close()

    print("\n" + "=" * 70)
    print(f"Completed at: {datetime.now().isoformat()}")
    print("=" * 70)


if __name__ == "__main__":
    main()
