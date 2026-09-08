#!/usr/bin/env python3
"""Fix enforcement trigger to use evaluated_at for promotion_gate_audit"""

import psycopg2

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 54322,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres'
}

trigger_fix_sql = """
CREATE OR REPLACE FUNCTION fhq_learning.fn_enforce_chain_binding()
RETURNS TRIGGER AS $$
DECLARE
    migration_cutoff TIMESTAMPTZ;
    row_timestamp TIMESTAMPTZ;
BEGIN
    -- Get cutoff from first gate creation or NOW
    migration_cutoff := (
        SELECT COALESCE(
            (SELECT created_at FROM fhq_governance.canonical_mutation_gates LIMIT 1),
            NOW()
        )
    );

    -- Determine timestamp based on table (different tables use different column names)
    IF TG_TABLE_NAME = 'promotion_gate_audit' THEN
        row_timestamp := NEW.evaluated_at;
    ELSE
        row_timestamp := NEW.created_at;
    END IF;

    -- Only enforce on genuinely new rows (post-migration)
    IF row_timestamp >= migration_cutoff THEN
        IF TG_TABLE_NAME = 'promotion_gate_audit' THEN
            IF NEW.gate_id IS NULL THEN
                RAISE EXCEPTION 'CHAIN BINDING VIOLATION: gate_id required post-migration';
            END IF;
            IF NEW.causal_node_id IS NULL THEN
                RAISE EXCEPTION 'CHAIN BINDING VIOLATION: causal_node_id required post-migration';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

try:
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute(trigger_fix_sql)
    print("[TRIGGER FIX] Enforcement trigger updated to use evaluated_at for promotion_gate_audit")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)
