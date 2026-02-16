#!/usr/bin/env python3
"""
CEO-DIR-2026-WINNER-STRUCTURE-ANALYSIS-010
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
        with conn.cursor(cursor_factory=psycopg2.DictCursor) as cur:
            # Get all winners (deflated_sharpe >= 1.0)
            # Limit to 100 to get full distribution context
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
                    pga.metrics_snapshot->>'deflated_sharpe' as deflated_sharpe,
                    pga.metrics_snapshot->>'win_rate' as win_rate,
                    pga.metrics_snapshot->>'n_outcomes' as n_outcomes
                FROM fhq_learning.promotion_gate_audit pga
                JOIN fhq_learning.hypothesis_canon hc ON pga.hypothesis_id = hc.canon_id
                WHERE pga.gate_name = 'DEFLATED_SHARPE_GATE'
                  AND pga.metrics_snapshot->>'deflated_sharpe'::numeric >= 1.0)
                  AND pga.evaluated_at >= NOW() - INTERVAL '24 hours'
                LIMIT 100
            """)

            all_winners = cur.fetchall()
            print("[DIR-010] Found " + str(len(all_winners)) + " winners")

            # Count by deflated_sharpe ranges
            negative = sum(1 for w in all_winners if w['deflated_sharpe'] < 0)
            zero_to_half = sum(1 for w in all_winners if 0 <= w['deflated_sharpe'] < 0.5)
            half_to_one = sum(1 for w in all_winners if 0.5 <= w['deflated_sharpe'] < 1.0)
            one_plus = sum(1 for w in all_winners if w['deflated_sharpe'] >= 1.0)

            print("[DIR-010] Distribution: neg=" + str(negative) + " (<0), zero=" + str(zero_to_half) + " ([0-0.5]), half=" + str(half_to_one) + " ([0.5-1]), pos=" + str(one_plus) + " (>1.0))")

            # Generate evidence
            evidence_dir = "C:/fhq-market-system/vision-ios/03_FUNCTIONS/evidence"
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            evidence_path = evidence_dir + "/CEO_DIR_WINNER_STRUCTURE_ANALYSIS_010_" + ts + ".json"

            winners_list = [
                {
                    "hypothesis_id": str(w["hypothesis_id"]),
                    "hypothesis_code": w["hypothesis_code"],
                    "deflated_sharpe": float(w["deflated_sharpe"])
                }
                for w in all_winners
            ]

            evidence = {
                "directive": "CEO-DIR-2026-WINNER-STRUCTURE-ANALYSIS-010",
                "agent": "STIG (EC-003)",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "status": "PHASE_A_COMPLETE",
                "phase_a": {
                    "description": "Retrieved all winners for distribution analysis",
                    "n": len(all_winners),
                    "distribution": {
                        "negative": negative,
                        "zero_to_half": zero_to_half,
                        "half_to_one": half_to_one,
                        "one_plus": one_plus
                    }
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
