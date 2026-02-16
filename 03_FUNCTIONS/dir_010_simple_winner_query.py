#!/usr/bin/env python3
"""
CEO-DIR-2026-WINNER-STRUCTURE-ANALYSIS-010
Simple query without ORDER BY
"""

import psycopg2
import json
from datetime import datetime, timezone

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres'
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Phase A: Get winners (deflated_sharpe >= 1.0)
            cur.execute("""
                SELECT
                    pga.audit_id,
                    pga.hypothesis_id,
                    hc.hypothesis_code,
                    pga.gate_name,
                    pga.gate_result,
                    pga.failure_reason,
                    hc.parameter_search_breadth,
                    hc.prior_hypotheses_count,
                    hc.falsification_criteria,
                    pga.metrics_snapshot->'deflated_sharpe' as deflated_sharpe,
                    pga.metrics_snapshot->'win_rate' as win_rate,
                    pga.metrics_snapshot->'n_outcomes' as n_outcomes
                FROM fhq_learning.promotion_gate_audit pga
                JOIN fhq_learning.hypothesis_canon hc ON pga.hypothesis_id = hc.canon_id
                WHERE pga.gate_name = 'DEFLATED_SHARPE_GATE'
                  AND pga.metrics_snapshot->'deflated_sharpe'::numeric >= 1.0)
                  AND pga.evaluated_at >= NOW() - INTERVAL '24 hours'
                LIMIT 100
            """)

            winners = cur.fetchall()

            print("[DIR-010] Found " + str(len(winners)) + " winners")

            # Sort in Python to get top 32
            winners_sorted = sorted(winners, key=lambda x: x['deflated_sharpe'] if 'deflated_sharpe' in x else 0.0, reverse=True)
            winners_top32 = winners_sorted[:32]

            # Generate evidence
            evidence_dir = "C:/fhq-market-system/vision-ios/03_FUNCTIONS/evidence"
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence_path = evidence_dir + "/CEO_DIR_WINNER_STRUCTURE_ANALYSIS_010_" + ts + ".json"

            winners_list = []
            for w in winners_top32:
                w_dict = {
                    "hypothesis_id": str(w["hypothesis_id"]),
                    "hypothesis_code": w["hypothesis_code"],
                    "deflated_sharpe": float(w["deflated_sharpe"])
                }
                winners_list.append(w_dict)

            evidence = {
                "directive": "CEO-DIR-2026-WINNER-STRUCTURE-ANALYSIS-010",
                "agent": "STIG (EC-003)",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "status": "PHASE_A_COMPLETE",
                "phase_a": {
                    "description": "Retrieved winner experiment data (top 32)",
                    "n": 32,
                    "winners": winners_list
                }
            }

            with open(evidence_path, 'w') as f:
                json.dump(evidence, f, indent=2)

            print("[DIR-010] Evidence: " + evidence_path)

    except Exception as e:
        print("[DIR-010] ERROR: " + str(e))

    finally:
        conn.close()

if __name__ == "__main__":
    main()
