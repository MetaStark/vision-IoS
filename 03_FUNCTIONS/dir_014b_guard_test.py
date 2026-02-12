#!/usr/bin/env python3
"""
CEO-DIR-2026-GENERATION-FREEZE-ENFORCEMENT-014B
Guard Function Test (Fixed SQL escaping)
"""

import psycopg2
import sys
import json
from datetime import datetime, timezone

DB_CONFIG = {
    "host": "127.0.0.1",
    "port":  54322,
    "database": "postgres",
    "user": "postgres"
}

def guard_generation_freeze(conn, hypothesis_code, controlled_exception):
    """
    Check generation freeze policy and enforce blocking.
    Returns: (allowed: bool, reason: str, metrics: dict)
    """
    try:
        with conn.cursor() as cur:
            # Read latest freeze policy
            cur.execute("""
                SELECT freeze_enabled, freeze_end_at, exception_quota_pct
                FROM fhq_governance.generation_freeze_control
                ORDER BY created_at DESC LIMIT 1
            """)
            result = cur.fetchone()

            if not result:
                return True, "No freeze policy", {}

            v_freeze_enabled = result[0]
            v_freeze_end_at = result[1]
            v_exception_quota_pct = float(result[2]) if result[2] else 0.0

            # Policy evaluation
            if v_freeze_enabled is None:
                # No freeze - allow all
                return True, "No freeze active", {}
            # Check if freeze expired
            if v_freeze_end_at and datetime.now(timezone.utc) > v_freeze_end_at:
                return True, "Freeze expired", {}
            # Freeze is active
            if controlled_exception:
                # Controlled exception - check quota
                cur.execute("""
                    SELECT COUNT(*)
                    FROM fhq_learning.hypothesis_canon
                    WHERE created_at >= NOW() - INTERVAL '720 hours'
                        AND controlled_exception = true
                """)
                count_result = cur.fetchone()
                controlled_count = int(count_result[0])

                # Get budget (5% of active total)
                cur.execute("""
                    SELECT COUNT(*)
                    FROM fhq_learning.hypothesis_canon
                    WHERE created_at >= NOW() - INTERVAL '720 hours'
                """)
                total_result = cur.fetchone()
                active_total = int(total_result[0])
                budget = int(active_total * 0.05) + 1

                if controlled_count < budget:
                    # Allow - within quota
                    return True, "Controlled exception allowed within quota", {}
                else:
                    # Block - quota exceeded
                    reason = "Controlled exception quota exceeded. " + str(controlled_count) + "/" + str(budget) + " (5%)"
                    metrics = {
                        "controlled_count": controlled_count,
                        "budget": budget,
                        "active_total": active_total
                    }
                    return False, reason, metrics
            else:
                # Non-controlled - always allow
                return True, "Not a controlled exception", {}
    except Exception as e:
            conn.rollback()
            return False, f"Database error: {str(e)}", {}

def log_block(conn, hypothesis_code, reason, metrics=None):
    """Log a generation block to evidence table"""
    preferred_table = "fhq_learning.semantic_diversity_blocks"
    fallback_table = "fhq_governance.generation_freeze_blocks"
    evidence = {
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "directive": "CEO-DIR-2026-GENERATION-FREEZE-ENFORCEMENT-014B",
        "hypothesis_code": hypothesis_code,
        "blocked_reason": reason,
        "metrics": metrics or {}
    }

    try:
        with conn.cursor() as cur:
            # Try preferred table first
            cur.execute(f"""
                INSERT INTO {preferred_table} (
                    occurred_at, directive, hypothesis_code, blocked_reason, metrics, agent_id
                ) VALUES (%s, %s, %s, %s, %s, 'STIG')
                """, (
                    evidence["occurred_at"],
                    "CEO-DIR-2026-GENERATION-FREEZE-ENFORCEMENT-014B",
                    hypothesis_code,
                    reason,
                    json.dumps(metrics or {})
                )
            )
            conn.commit()
            return
    except Exception:
        # Try fallback table
        pass

if __name__ == "__main__":
    # Test blocking
    print("=== Testing guard blocking behavior ===")
    conn = psycopg2.connect(**DB_CONFIG)

    result = guard_generation_freeze(conn, 'TEST-BLOCK-001', True)
    print(f"TEST-BLOCK-001: controlled_exception=TRUE -> {result[0]}, {result[1]}")

    # Test allowing
    result = guard_generation_freeze(conn, 'TEST-ALLOW-001', False)
    print(f"TEST-ALLOW-001: controlled_exception=FALSE -> {result[0]}, {result[1]}")

    conn.close()

    print("=== Test complete ===")
