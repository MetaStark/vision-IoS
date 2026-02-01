#!/usr/bin/env python3
"""Test gate blocking scenario for CEO-DIR-2026-021 Step 4"""

import os
import psycopg2
import subprocess
import sys
import json
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("PGHOST", "127.0.0.1"),
    "port": os.getenv("PGPORT", "54322"),
    "database": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres")
}

conn = psycopg2.connect(**DB_CONFIG)

try:
    # Step 1: Set learning_eligible to FALSE
    print("[TEST] Setting learning_eligible = FALSE...")
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_governance.execution_state
            SET learning_eligible = FALSE,
                last_updated_by = 'STIG',
                last_update_reason = 'CEO-DIR-2026-021 Step 4: Test gate blocking scenario'
            WHERE state_id = 1
        """)
        conn.commit()
    print("[TEST] State updated")

    # Step 2: Clear existing week 2 run to allow new test
    print("[TEST] Clearing existing ISO week run...")
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM fhq_governance.weekly_learning_runs
            WHERE iso_year = 2026 AND iso_week = 2
        """)
        conn.commit()
    print("[TEST] Run cleared")

    # Step 3: Run orchestrator (should be blocked)
    print("[TEST] Running orchestrator (expecting gate block)...")
    result = subprocess.run(
        [sys.executable, "weekly_learning_orchestrator.py", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__)
    )

    print("\n" + "=" * 60)
    print("ORCHESTRATOR OUTPUT (GATE BLOCKED SCENARIO):")
    print("=" * 60)
    print(result.stdout)

    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)

    # Parse and display run_info
    try:
        output = json.loads(result.stdout)
        print("\n" + "=" * 60)
        print("PARSED RESULT:")
        print("=" * 60)
        print(f"Action: {output.get('action')}")
        print(f"Gate Passed: {output['run_info']['gate_passed']}")
        print(f"Block Reason: {output['run_info']['block_reason']}")
        print(f"Evidence ID: {output.get('evidence_id')}")
    except:
        pass

finally:
    # Step 4: Restore original state
    print("\n[TEST] Restoring original state...")
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE fhq_governance.execution_state
            SET learning_eligible = TRUE,
                last_updated_by = 'STIG',
                last_update_reason = 'CEO-DIR-2026-021 Step 4: Test complete, state restored'
            WHERE state_id = 1
        """)
        conn.commit()
    print("[TEST] State restored to learning_eligible = TRUE")

    conn.close()
    print("[TEST] Test complete")
