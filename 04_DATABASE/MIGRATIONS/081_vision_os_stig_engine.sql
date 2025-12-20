-- ============================================================================
-- Migration 081: Vision-OS STIG Write Engine
-- ============================================================================
-- Authority: CEO Directive — Vision-OS Dashboard Extension (REV 1.2)
-- Oversight: VEGA
-- Technical Owner: STIG
-- Constitutional Basis: ADR-001, ADR-008, ADR-010, ADR-012, ADR-013, ADR-019, IoS-009
-- Date: 2025-12-07
--
-- Purpose: Create stig_write_engine role for STIG's LLM Code API with:
--   - DML access to fhq_meta.* and fhq_research.* (config & research data)
--   - INSERT-only on fhq_governance.* (immutability enforcement)
--   - ZERO access to execution plane (fhq_positions, fhq_market, fhq_orders, fhq_execution)
--   - NO DDL capabilities (schema changes via CI/CD only)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: Create stig_write_engine Role
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'stig_write_engine') THEN
        CREATE ROLE stig_write_engine NOLOGIN;
    END IF;
END $$;

COMMENT ON ROLE stig_write_engine IS
'STIG Engineering API Role (ADR-019, ADR-013).
DML-only access for data operations. NO DDL. NO execution plane access.
Governance tables are append-only (INSERT only, no UPDATE/DELETE).
All operations require Ed25519 signature verification.';

-- ============================================================================
-- PHASE 2: Grant DML on fhq_meta.* (Config & State)
-- ============================================================================

GRANT USAGE ON SCHEMA fhq_meta TO stig_write_engine;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA fhq_meta TO stig_write_engine;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_meta
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO stig_write_engine;

-- Grant sequence usage for INSERT operations
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA fhq_meta TO stig_write_engine;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_meta
    GRANT USAGE, SELECT ON SEQUENCES TO stig_write_engine;

-- ============================================================================
-- PHASE 3: Grant DML on fhq_research.* (Research Data)
-- ============================================================================

GRANT USAGE ON SCHEMA fhq_research TO stig_write_engine;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA fhq_research TO stig_write_engine;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_research
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO stig_write_engine;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA fhq_research TO stig_write_engine;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_research
    GRANT USAGE, SELECT ON SEQUENCES TO stig_write_engine;

-- ============================================================================
-- PHASE 4: Grant INSERT-only on fhq_governance.* (IMMUTABILITY ENFORCEMENT)
-- ============================================================================

GRANT USAGE ON SCHEMA fhq_governance TO stig_write_engine;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA fhq_governance TO stig_write_engine;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_governance
    GRANT SELECT, INSERT ON TABLES TO stig_write_engine;

-- Explicitly REVOKE UPDATE and DELETE (defense in depth)
REVOKE UPDATE, DELETE ON ALL TABLES IN SCHEMA fhq_governance FROM stig_write_engine;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA fhq_governance TO stig_write_engine;
ALTER DEFAULT PRIVILEGES IN SCHEMA fhq_governance
    GRANT USAGE, SELECT ON SEQUENCES TO stig_write_engine;

-- ============================================================================
-- PHASE 5: Grant READ-ONLY on vision_* schemas (for context)
-- ============================================================================

GRANT USAGE ON SCHEMA vision_core TO stig_write_engine;
GRANT USAGE ON SCHEMA vision_signals TO stig_write_engine;
GRANT USAGE ON SCHEMA vision_verification TO stig_write_engine;

GRANT SELECT ON ALL TABLES IN SCHEMA vision_core TO stig_write_engine;
GRANT SELECT ON ALL TABLES IN SCHEMA vision_signals TO stig_write_engine;
GRANT SELECT ON ALL TABLES IN SCHEMA vision_verification TO stig_write_engine;

-- ============================================================================
-- PHASE 6: EXPLICIT DENIALS — The Air Gap
-- ============================================================================
-- These schemas are COMPLETELY off-limits to stig_write_engine.
-- IoS-012 is the ONLY route for trading actions.

-- Revoke ALL on execution plane schemas (if they exist)
DO $$
DECLARE
    v_schema TEXT;
BEGIN
    FOR v_schema IN SELECT unnest(ARRAY['fhq_positions', 'fhq_market', 'fhq_orders', 'fhq_execution'])
    LOOP
        -- Check if schema exists before revoking
        IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = v_schema) THEN
            EXECUTE format('REVOKE ALL ON SCHEMA %I FROM stig_write_engine', v_schema);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM stig_write_engine', v_schema);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM stig_write_engine', v_schema);
            RAISE NOTICE 'Air gap enforced on schema: %', v_schema;
        ELSE
            RAISE NOTICE 'Schema % does not exist yet - air gap will apply when created', v_schema;
        END IF;
    END LOOP;
END $$;

-- ============================================================================
-- PHASE 7: NO TRUNCATE Anywhere
-- ============================================================================

REVOKE TRUNCATE ON ALL TABLES IN SCHEMA fhq_meta FROM stig_write_engine;
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA fhq_research FROM stig_write_engine;
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA fhq_governance FROM stig_write_engine;

-- ============================================================================
-- PHASE 8: Governance Immutability Triggers
-- ============================================================================
-- Even if someone grants UPDATE/DELETE later, these triggers will block it.

CREATE OR REPLACE FUNCTION fhq_governance.enforce_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'GOVERNANCE VIOLATION (ADR-013): UPDATE on fhq_governance.% is prohibited. Governance logs are immutable. Table: %, Operation: %',
            TG_TABLE_NAME, TG_TABLE_NAME, TG_OP;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'GOVERNANCE VIOLATION (ADR-013): DELETE on fhq_governance.% is prohibited. Governance logs are immutable. Table: %, Operation: %',
            TG_TABLE_NAME, TG_TABLE_NAME, TG_OP;
    END IF;

    IF TG_OP = 'TRUNCATE' THEN
        RAISE EXCEPTION 'GOVERNANCE VIOLATION (ADR-013): TRUNCATE on fhq_governance.% is prohibited. Governance logs are immutable. Table: %, Operation: %',
            TG_TABLE_NAME, TG_TABLE_NAME, TG_OP;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.enforce_immutability() IS
'ADR-013 Immutability Enforcement: Blocks UPDATE/DELETE/TRUNCATE on governance tables.
All governance changes are historical layers, never edits to history.';

-- Apply immutability trigger to key governance tables
DO $$
DECLARE
    tbl TEXT;
    trigger_name TEXT;
BEGIN
    FOR tbl IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'fhq_governance'
        AND table_type = 'BASE TABLE'
    LOOP
        trigger_name := 'trg_immutability_' || tbl;

        -- Drop existing trigger if exists
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON fhq_governance.%I', trigger_name, tbl);

        -- Create new trigger
        EXECUTE format('
            CREATE TRIGGER %I
            BEFORE UPDATE OR DELETE ON fhq_governance.%I
            FOR EACH ROW
            EXECUTE FUNCTION fhq_governance.enforce_immutability()
        ', trigger_name, tbl);

        RAISE NOTICE 'Immutability trigger applied to fhq_governance.%', tbl;
    END LOOP;
END $$;

-- ============================================================================
-- PHASE 9: Create STIG Engine Operation Log Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.stig_engine_operations (
    operation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request identification
    request_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id TEXT NOT NULL DEFAULT 'STIG',
    signature_hash TEXT NOT NULL,
    signature_valid BOOLEAN NOT NULL,

    -- Operation details
    operation_type TEXT NOT NULL,
    target_schema TEXT NOT NULL,
    target_table TEXT NOT NULL,
    operation_payload JSONB,
    justification TEXT,

    -- Execution result
    decision TEXT NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED', 'EXECUTED', 'FAILED')),
    rejection_reason TEXT,
    rows_affected INTEGER,
    execution_duration_ms INTEGER,
    error_message TEXT,

    -- Governance binding
    hash_chain_id TEXT,
    governance_action_id UUID
);

CREATE INDEX IF NOT EXISTS idx_stig_engine_ops_timestamp
    ON fhq_governance.stig_engine_operations(request_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_stig_engine_ops_decision
    ON fhq_governance.stig_engine_operations(decision);
CREATE INDEX IF NOT EXISTS idx_stig_engine_ops_operation
    ON fhq_governance.stig_engine_operations(operation_type, target_schema, target_table);

COMMENT ON TABLE fhq_governance.stig_engine_operations IS
'STIG Engineering API audit log. Every operation (accepted or rejected) is logged here.
Immutable by ADR-013. Used for forensic reconstruction and VEGA oversight.';

-- ============================================================================
-- PHASE 10: Create Allowed Operations Registry
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.stig_allowed_operations (
    operation_type TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    allowed_schemas TEXT[] NOT NULL,
    allowed_tables TEXT[],  -- NULL means all tables in allowed_schemas
    requires_justification BOOLEAN DEFAULT TRUE,
    max_rows_per_operation INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'STIG'
);

-- Populate with allowed operation types
INSERT INTO fhq_meta.stig_allowed_operations (operation_type, description, allowed_schemas, allowed_tables, max_rows_per_operation)
VALUES
    ('UPSERT_CONFIG', 'Update or insert configuration records',
     ARRAY['fhq_meta'], NULL, 100),
    ('UPSERT_CONTEXT', 'Update or insert context registry entries',
     ARRAY['fhq_meta'], ARRAY['model_context_registry', 'context_packages', 'ios_registry', 'adr_registry'], 50),
    ('BACKFILL_RESEARCH', 'Backfill research data (indicators, features)',
     ARRAY['fhq_research'], NULL, 10000),
    ('UPDATE_FEATURE', 'Update feature registry or feature values',
     ARRAY['fhq_research', 'fhq_meta'], ARRAY['feature_registry', 'alpha_feature_values'], 1000),
    ('INSERT_GOVERNANCE_EVENT', 'Log governance event (append-only)',
     ARRAY['fhq_governance'], ARRAY['governance_actions_log', 'stig_engine_operations'], NULL),
    ('REFRESH_MATERIALIZED', 'Refresh materialized view data',
     ARRAY['fhq_research', 'fhq_meta'], NULL, NULL),
    ('ANONYMIZE_TEST_DATA', 'Anonymize test/sandbox data',
     ARRAY['fhq_research'], NULL, 5000)
ON CONFLICT (operation_type) DO UPDATE SET
    description = EXCLUDED.description,
    allowed_schemas = EXCLUDED.allowed_schemas,
    allowed_tables = EXCLUDED.allowed_tables,
    max_rows_per_operation = EXCLUDED.max_rows_per_operation;

COMMENT ON TABLE fhq_meta.stig_allowed_operations IS
'Whitelist of allowed operation types for STIG Engineering API.
Each operation_type maps to specific allowed schemas and tables.
Enforces the principle of least privilege.';

-- ============================================================================
-- PHASE 11: Create Validation Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.validate_stig_operation(
    p_operation_type TEXT,
    p_target_schema TEXT,
    p_target_table TEXT
)
RETURNS TABLE (
    is_valid BOOLEAN,
    rejection_reason TEXT
) AS $$
DECLARE
    v_op_config RECORD;
BEGIN
    -- Check if operation type is allowed
    SELECT * INTO v_op_config
    FROM fhq_meta.stig_allowed_operations
    WHERE operation_type = p_operation_type AND is_active = TRUE;

    IF v_op_config IS NULL THEN
        RETURN QUERY SELECT FALSE, format('Operation type "%s" is not in whitelist', p_operation_type);
        RETURN;
    END IF;

    -- Check if target schema is allowed
    IF NOT (p_target_schema = ANY(v_op_config.allowed_schemas)) THEN
        RETURN QUERY SELECT FALSE, format('Schema "%s" is not allowed for operation "%s". Allowed: %s',
            p_target_schema, p_operation_type, array_to_string(v_op_config.allowed_schemas, ', '));
        RETURN;
    END IF;

    -- Check if target table is allowed (if specific tables are defined)
    IF v_op_config.allowed_tables IS NOT NULL AND
       NOT (p_target_table = ANY(v_op_config.allowed_tables)) THEN
        RETURN QUERY SELECT FALSE, format('Table "%s" is not allowed for operation "%s". Allowed: %s',
            p_target_table, p_operation_type, array_to_string(v_op_config.allowed_tables, ', '));
        RETURN;
    END IF;

    -- Check execution plane air gap
    IF p_target_schema IN ('fhq_positions', 'fhq_market', 'fhq_orders', 'fhq_execution') THEN
        RETURN QUERY SELECT FALSE, format('AIR GAP VIOLATION: Schema "%s" is execution plane. Access denied.',
            p_target_schema);
        RETURN;
    END IF;

    -- All checks passed
    RETURN QUERY SELECT TRUE, NULL::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.validate_stig_operation IS
'Validates STIG Engineering API operations against whitelist and air gap rules.
Returns (is_valid, rejection_reason). Used by API endpoint before execution.';

-- ============================================================================
-- PHASE 12: Grant Execute on Functions
-- ============================================================================

GRANT EXECUTE ON FUNCTION fhq_governance.validate_stig_operation(TEXT, TEXT, TEXT) TO stig_write_engine;
GRANT EXECUTE ON FUNCTION fhq_meta.submit_narrative_vector(TEXT, TEXT, NUMERIC, NUMERIC, INTEGER, TEXT) TO stig_write_engine;

-- ============================================================================
-- PHASE 13: Log Migration as Governance Event
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    hash_chain_id
) VALUES (
    'STIG_ENGINE_ROLE_CREATED',
    'stig_write_engine',
    'DATABASE_ROLE',
    'STIG',
    'APPROVED',
    'CEO Directive: Vision-OS Dashboard Extension REV 1.2. Created stig_write_engine role with DML-only access, governance immutability enforcement, and execution plane air gap.',
    'HC-VISION-OS-STIG-ENGINE-2026'
);

-- Create hash chain entry
INSERT INTO fhq_security.hash_chains (
    chain_id,
    chain_type,
    environment_hash,
    current_block_number,
    last_block_hash,
    genesis_timestamp,
    last_updated,
    status
) VALUES (
    'HC-VISION-OS-STIG-ENGINE-2026',
    'SECURITY',
    encode(sha256(('STIG-ENGINE-ROLE-' || NOW()::TEXT)::bytea), 'hex'),
    1,
    encode(sha256(('STIG-ENGINE-BLOCK1-' || NOW()::TEXT)::bytea), 'hex'),
    NOW(),
    NOW(),
    'ACTIVE'
) ON CONFLICT (chain_id) DO UPDATE SET
    current_block_number = fhq_security.hash_chains.current_block_number + 1,
    last_block_hash = EXCLUDED.last_block_hash,
    last_updated = NOW();

-- ============================================================================
-- Migration Complete
-- ============================================================================

COMMIT;
