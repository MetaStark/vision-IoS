#!/usr/bin/env python3
"""
CEO-DIR-2026-014A-R2 — Generation Freeze Function Deployment
"""

import psycopg2
import sys
from datetime import datetime, timezone

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres'
}

def main():
    print("=" * 60)
    print("DIR-014A-R2: Generation Freeze Function Deployment")
    print("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("\nDeploying control table...")
    cur.execute("""
        INSERT INTO fhq_governance.generation_freeze_control (
            freeze_enabled, freeze_start_at, freeze_end_at, exception_quota_pct,
            created_by, evidence_hash, note
        ) VALUES (
            false, NOW(), NULL, 0.05, 'STIG',
            'DIR-014A-R2_DEPLOYMENT_HASH',
            'DIR-014A deployed via Python with custom delimiter'
        )
        ON CONFLICT (freeze_id) DO NOTHING;
    """)
    conn.commit()
    print("Control table record inserted")

    print("\nCreating function with custom delimiter ($freeze$)...")
    function_sql = """
    CREATE OR REPLACE FUNCTION fhq_governance.fn_enforce_generation_freeze()
    RETURNS TRIGGER AS $freeze$
    DECLARE
        v_freeze_enabled BOOLEAN;
        v_freeze_end_at TIMESTAMP WITH TIME ZONE;
        v_exception_quota_pct NUMERIC;
        v_is_controlled_exception BOOLEAN;
        v_exception_budget BIGINT;
        v_active_window BIGINT;
        v_controlled_count BIGINT;
        v_controlled_total BIGINT;
        v_allow_insert BOOLEAN;
        v_reason TEXT;
    BEGIN
        SELECT freeze_enabled, freeze_end_at, exception_quota_pct
        INTO v_freeze_enabled, v_freeze_end_at, v_exception_quota_pct
        FROM fhq_governance.generation_freeze_control
        ORDER BY created_at DESC LIMIT 1;

        IF v_freeze_enabled IS NULL THEN
            RETURN NEW;
        END IF;

        IF v_freeze_enabled = true AND NOW() > v_freeze_end_at THEN
            RETURN NEW;
        END IF;

        v_is_controlled_exception := NEW.controlled_exception = true;

        IF NOT v_is_controlled_exception THEN
            SELECT COUNT(*), SUM(CASE WHEN controlled_exception = true THEN 1 ELSE 0 END)
            INTO v_controlled_count, v_controlled_total
            FROM fhq_learning.hypothesis_canon
            WHERE created_at >= NOW() - INTERVAL '720 hours';

        v_active_window := v_controlled_total;
        v_exception_budget := CEIL(v_active_window * v_exception_quota_pct);

        IF v_controlled_count < v_exception_budget THEN
            v_allow_insert := true;
            v_reason := NULL;
        ELSE
            v_allow_insert := false;
            v_reason := 'GENERATION_FREEZE: Controlled exception quota exceeded. ' ||
                         v_exception_quota_pct * 100 || '% (budget=' ||
                         v_exception_budget || ', current=' || v_controlled_count || ')';
        END IF;
    ELSE
        v_allow_insert := true;
        v_reason := NULL;
    END IF;

    IF v_allow_insert THEN
        RETURN NEW;
    ELSE
        RAISE EXCEPTION 'GENERATION_FREEZE_VIOLATION'
        USING MESSAGE = v_reason,
              HINT = 'Use controlled_exception=true for controlled batch generation',
              DETAIL = 'freeze_enabled=' || v_freeze_enabled || '|freeze_end_at=' || v_freeze_end_at ||
                         'exception_quota_pct=' || v_exception_quota_pct || '|controlled_exception=' || v_is_controlled_exception;
    END;
    $freeze$
    LANGUAGE plpgsql;
    """

    try:
        cur.execute(function_sql)
        conn.commit()
        print("Function created successfully")
    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print("\nCreating trigger...")
    trigger_sql = """
        DROP TRIGGER IF EXISTS trg_enforce_generation_freeze ON fhq_learning.hypothesis_canon;

        CREATE TRIGGER trg_enforce_generation_freeze
        BEFORE INSERT ON fhq_learning.hypothesis_canon
        FOR EACH ROW EXECUTE FUNCTION fhq_governance.fn_enforce_generation_freeze();
    """

    try:
        cur.execute(trigger_sql)
        conn.commit()
        print("Trigger created successfully")
    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print("\n" + "=" * 60)
    print("Deployment complete.")
    print("=" * 60)

if __name__ == "__main__":
    main()
