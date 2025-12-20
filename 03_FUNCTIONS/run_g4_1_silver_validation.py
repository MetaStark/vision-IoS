#!/usr/bin/env python3
"""
G4.1 Deep Validation Runner - SILVER Signals Only
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
    print("G4.1 DEEP VALIDATION - 15 SILVER SIGNALS (7-YEAR WINDOWS)")
    print("=" * 70)

    conn = psycopg2.connect(**DB_CONFIG)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT gn.needle_id, gn.hypothesis_title, gn.hypothesis_category,
                   gn.target_asset, gn.hypothesis_statement, gn.eqs_score,
                   sc.classification, sc.oos_sharpe
            FROM fhq_canonical.g4_composite_scorecard sc
            JOIN fhq_canonical.golden_needles gn ON sc.needle_id = gn.needle_id
            WHERE sc.classification = 'SILVER'
            ORDER BY sc.oos_sharpe DESC
        """)
        silver_needles = cur.fetchall()

    print(f"\nSILVER signals to validate: {len(silver_needles)}")
    print(f"Started at: {datetime.now().isoformat()}\n")

    # Clear previous results
    with conn.cursor() as cur:
        needle_ids = [str(n['needle_id']) for n in silver_needles]
        for table in ['g4_1_stability_results', 'g4_1_regime_rotation_results',
                      'g4_1_sensitivity_results', 'g4_1_density_results', 'g4_1_composite_verdict']:
            cur.execute(f"DELETE FROM fhq_canonical.{table} WHERE needle_id = ANY(%s::uuid[])", (needle_ids,))
        conn.commit()
    conn.close()

    from g4_1_deep_validation_engine import G4_1_DeepValidationEngine
    engine = G4_1_DeepValidationEngine()

    results = {'STABLE': 0, 'CONDITIONAL': 0, 'FRAGILE': 0, 'ILLUSORY': 0}

    for i, needle in enumerate(silver_needles, 1):
        title = needle['hypothesis_title'][:45]
        print(f"[{i:2d}/{len(silver_needles)}] {title}...")

        try:
            result = engine.run_full_validation(dict(needle))
            assessment = result.get('edge_assessment', 'UNKNOWN')
            final_class = result.get('final_classification', 'UNKNOWN')

            status = {'STABLE': '[STABLE]', 'CONDITIONAL': '[COND]  ',
                      'FRAGILE': '[FRAG]  ', 'ILLUSORY': '[ILLUS] '}.get(assessment, '[???]')
            print(f"        {status} -> {final_class}")

            if assessment in results:
                results[assessment] += 1
        except Exception as e:
            print(f"        [ERROR] {str(e)[:50]}")

    print("\n" + "=" * 70)
    print("G4.1 RESULTS - SILVER SIGNALS")
    print("=" * 70)
    print(f"\n  STABLE:      {results['STABLE']:2d}  (G5 eligible)")
    print(f"  CONDITIONAL: {results['CONDITIONAL']:2d}")
    print(f"  FRAGILE:     {results['FRAGILE']:2d}")
    print(f"  ILLUSORY:    {results['ILLUSORY']:2d}")

    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT final_classification, edge_assessment, COUNT(*) as count
            FROM fhq_canonical.g4_1_composite_verdict cv
            JOIN fhq_canonical.g4_composite_scorecard sc ON cv.needle_id = sc.needle_id
            WHERE sc.classification = 'SILVER'
            GROUP BY final_classification, edge_assessment
        """)
        for r in cur.fetchall():
            print(f"\n  {r['edge_assessment']} -> {r['final_classification']}: {r['count']}")
    conn.close()

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
