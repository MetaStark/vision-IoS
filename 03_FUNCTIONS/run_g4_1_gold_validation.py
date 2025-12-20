#!/usr/bin/env python3
"""
G4.1 Deep Validation Runner - GOLD Signals Only
CEO Directive: Validate 22 GOLD signals from 7-year backtest
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Add path for imports
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
    print("G4.1 DEEP VALIDATION - 22 GOLD SIGNALS (7-YEAR WINDOWS)")
    print("CEO Directive: Edge Verification & Anti-Illusion Testing")
    print("=" * 70)

    conn = psycopg2.connect(**DB_CONFIG)

    # Get GOLD signals with all required fields
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                gn.needle_id,
                gn.hypothesis_title,
                gn.hypothesis_category,
                gn.target_asset,
                gn.hypothesis_statement,
                gn.eqs_score,
                sc.classification,
                sc.oos_sharpe
            FROM fhq_canonical.g4_composite_scorecard sc
            JOIN fhq_canonical.golden_needles gn ON sc.needle_id = gn.needle_id
            WHERE sc.classification = 'GOLD'
            ORDER BY sc.oos_sharpe DESC
        """)
        gold_needles = cur.fetchall()

    print(f"\nGOLD signals to validate: {len(gold_needles)}")
    print(f"Backtest window: 7 years")
    print(f"Started at: {datetime.now().isoformat()}")
    print()

    # Clear previous G4.1 results for these needles
    with conn.cursor() as cur:
        needle_ids = [str(n['needle_id']) for n in gold_needles]
        cur.execute("""
            DELETE FROM fhq_canonical.g4_1_stability_results
            WHERE needle_id = ANY(%s::uuid[])
        """, (needle_ids,))
        cur.execute("""
            DELETE FROM fhq_canonical.g4_1_regime_rotation_results
            WHERE needle_id = ANY(%s::uuid[])
        """, (needle_ids,))
        cur.execute("""
            DELETE FROM fhq_canonical.g4_1_sensitivity_results
            WHERE needle_id = ANY(%s::uuid[])
        """, (needle_ids,))
        cur.execute("""
            DELETE FROM fhq_canonical.g4_1_density_results
            WHERE needle_id = ANY(%s::uuid[])
        """, (needle_ids,))
        cur.execute("""
            DELETE FROM fhq_canonical.g4_1_composite_verdict
            WHERE needle_id = ANY(%s::uuid[])
        """, (needle_ids,))
        conn.commit()
        print("Cleared previous G4.1 results for GOLD signals\n")

    conn.close()

    # Import and run G4.1 engine
    from g4_1_deep_validation_engine import G4_1_DeepValidationEngine

    engine = G4_1_DeepValidationEngine()

    results = {
        'STABLE': [],
        'CONDITIONAL': [],
        'FRAGILE': [],
        'ILLUSORY': []
    }

    for i, needle in enumerate(gold_needles, 1):
        # Convert to dict format expected by engine
        needle_dict = dict(needle)
        title = needle['hypothesis_title'][:45]
        sharpe = float(needle['oos_sharpe'])

        print(f"[{i:2d}/22] Validating: {title}...")

        try:
            result = engine.run_full_validation(needle_dict)
            assessment = result.get('edge_assessment', 'UNKNOWN')
            final_class = result.get('final_classification', 'UNKNOWN')

            status = {
                'STABLE': '[STABLE]',
                'CONDITIONAL': '[COND]  ',
                'FRAGILE': '[FRAG]  ',
                'ILLUSORY': '[ILLUS] '
            }.get(assessment, '[???]   ')

            print(f"        {status} -> {final_class}")

            if assessment in results:
                results[assessment].append({
                    'needle_id': str(needle['needle_id']),
                    'title': needle['hypothesis_title'],
                    'original_sharpe': sharpe,
                    'assessment': assessment,
                    'final_classification': final_class
                })

        except Exception as e:
            import traceback
            print(f"        [ERROR] {str(e)[:50]}")
            traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print("G4.1 VALIDATION RESULTS - 22 GOLD SIGNALS")
    print("=" * 70)

    print(f"\n  STABLE:      {len(results['STABLE']):2d}  (G5 eligible)")
    print(f"  CONDITIONAL: {len(results['CONDITIONAL']):2d}")
    print(f"  FRAGILE:     {len(results['FRAGILE']):2d}")
    print(f"  ILLUSORY:    {len(results['ILLUSORY']):2d}")

    # Get final classification distribution
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                final_classification,
                edge_assessment,
                COUNT(*) as count,
                COUNT(*) FILTER (WHERE g5_eligible = true) as g5_count
            FROM fhq_canonical.g4_1_composite_verdict cv
            JOIN fhq_canonical.g4_composite_scorecard sc ON cv.needle_id = sc.needle_id
            WHERE sc.classification = 'GOLD'
            GROUP BY final_classification, edge_assessment
            ORDER BY
                CASE edge_assessment
                    WHEN 'STABLE' THEN 1
                    WHEN 'CONDITIONAL' THEN 2
                    WHEN 'FRAGILE' THEN 3
                    WHEN 'ILLUSORY' THEN 4
                END
        """)
        final_results = cur.fetchall()

        print("\n  FINAL CLASSIFICATION AFTER G4.1:")
        for r in final_results:
            print(f"    {r['edge_assessment']:12s} -> {r['final_classification']:10s}: {r['count']} (G5: {r['g5_count']})")

        # Check G5 eligibility
        cur.execute("""
            SELECT COUNT(*) FROM fhq_canonical.g4_1_composite_verdict
            WHERE g5_eligible = true
        """)
        g5_total = cur.fetchone()['count']
        print(f"\n  TOTAL G5 ELIGIBLE: {g5_total}")

    conn.close()

    print("\n" + "=" * 70)
    print(f"Completed at: {datetime.now().isoformat()}")
    print("=" * 70)

if __name__ == "__main__":
    main()
