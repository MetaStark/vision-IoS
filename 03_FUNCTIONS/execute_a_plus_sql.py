#!/usr/bin/env python3
"""
Execute A+B SQL queries and output to evidence.
CEO-DIR-2026-FIX-013: No evidence - no PASS. Execute A+B, then prove invariants with raw SQL.

Author: STIG (CTO)
Date: 2026-02-13
"""

import json
import hashlib
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

# SQL-spørringer fra CEO-DIR-2026-FIX-012
queries = [
    """
-- 1) Baseline ikke lenger konstant
SELECT
  COUNT(*) FILTER (WHERE brier_ref = 0.25) AS n_still_025
FROM fhq_research.fss_computation_log;

-- 2) 0.25 er akseptabelt (hardcoded baseline)
SELECT
  baseline_method,
  COUNT(*) AS n
FROM fhq_research.fss_computation_log
GROUP BY 1
ORDER BY 2 DESC;

-- 3) Gate violations
SELECT
  COUNT(*) FILTER (WHERE sample_size < 50 AND fss_value IS NOT NULL) AS gate_violation
FROM fhq_research.fss_computation_log;

-- 4) Degenerate guard
SELECT
  COUNT(*) FILTER (WHERE brier_ref <= 1e-9 AND fss_value IS NOT NULL) AS degenerate_guard
FROM fhq_research.fss_computation_log;

-- 5) Lookback empty check
SELECT
  COUNT(*) FILTER (WHERE baseline_method = 'LOOKBACK_EMPTY') AS lookback_empty,
  COUNT(*) FILTER (WHERE baseline_method = 'BASE_RATE_EMPIRICAL_BETA_30D_STRICT') AS baseline_computed
FROM fhq_research.fss_computation_log;
"""
]


def main():
    """Hovedutførelse."""
    # Get DATABASE_URL
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        import sys
        sys.exit(2)

    # Evidence output directory
    evidence_dir = os.path.join(
        os.path.dirname(__file__),
        '../evidence'
    )
    os.makedirs(evidence_dir, exist_ok=True)

    # Connect to database
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False

        evidence_data = {
            'report_id': 'A_PLUS_SQL_EVIDENCE',
            'report_type': 'CEO-DIR-2026-FIX-013_EVIDENCE',
            'executed_by': 'STIG',
            'executed_at': datetime.now(timezone.utc).isoformat(),
            'directive': 'CEO-DIR-2026-FIX-013',
            'sql_queries': queries
        }

        raw_outputs = {}

        # Execute each query
        for i, query in enumerate(queries):
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                result = cur.fetchall()

            if len(result) == 0:
                raw_outputs[f"Query {i+1}"] = {
                    'query': query.strip(),
                    'result': 'No rows',
                    'rows': []
                }
            else:
                raw_outputs[f"Query {i+1}"] = {
                    'query': query.strip(),
                    'result': result[0] if len(result) == 1 else result,
                    'rows': result if len(result) == 1 else [row for row in result]
                }

        # Compute SHA-256
        evidence_json = json.dumps(raw_outputs, indent=2, default=str)
        sha256_hash = hashlib.sha256(evidence_json.encode()).hexdigest()
        evidence_data['attestation'] = {
            'sha256_hash': sha256_hash
        }

        # Write evidence file
        filename = f"A_PLUS_SQL_EVIDENCE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(evidence_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(evidence_data, f, indent=2)

        print(f"EVIDENCE: {filepath}")
        print(f"SHA-256: {sha256_hash}")
        print(f"n_still_025: {raw_outputs['Query 1']['result'][0]}")
        print(f"baseline_computed: {raw_outputs['Query 4']['result'][0]['baseline_computed']}")

        # Determine status
        # Invariant check: gate_violation == 0
        # If FAIL, we have gate violations. If PASS, no gate violations.

        status = 'PASS' if raw_outputs['Query 3']['result'][0]['gate_violation'] == 0 else 'FAIL'

        print(f"STATUS: {status}")

        # Exit codes
        if status == 'PASS':
            sys.exit(0)
        else:
            sys.exit(2)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {e}")
        sys.exit(2)

    finally:
        conn.close()
