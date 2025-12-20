-- ============================================================================
-- MIGRATION PLAN: LLM Capture Infrastructure
-- Document ID: MP-LLM-001
-- Status: DESIGN ONLY - DO NOT EXECUTE
-- Authority: CEO Directive - PHASE 2
-- Compliance: ADR-001, ADR-003, ADR-012, ADR-013, ADR-018, ADR-020, ADR-021
-- Author: STIG (CTO)
-- Date: 2025-12-10
-- ============================================================================
--
-- WARNING: THIS IS A DESIGN DOCUMENT
-- NO SQL IN THIS FILE SHALL BE EXECUTED UNTIL PHASE 3 IS AUTHORIZED BY CEO
--
-- ============================================================================

-- ============================================================================
-- SECTION 1: agent_task_log EXTENSION
-- ============================================================================
-- Purpose: Add LLM telemetry fields to existing agent_task_log
-- Current state: 45 rows, all provider/cost/latency = NULL
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
ALTER TABLE fhq_governance.agent_task_log
ADD COLUMN IF NOT EXISTS provider VARCHAR(50),
ADD COLUMN IF NOT EXISTS model VARCHAR(100),
ADD COLUMN IF NOT EXISTS tokens_in INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS tokens_out INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS latency_ms INTEGER,
ADD COLUMN IF NOT EXISTS cost_usd DECIMAL(10,6) DEFAULT 0,
ADD COLUMN IF NOT EXISTS stream_mode BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS stream_chunks INTEGER,
ADD COLUMN IF NOT EXISTS correlation_id UUID,
ADD COLUMN IF NOT EXISTS telemetry_envelope_id UUID,
ADD COLUMN IF NOT EXISTS error_type VARCHAR(100),
ADD COLUMN IF NOT EXISTS error_payload JSONB;

COMMENT ON COLUMN fhq_governance.agent_task_log.provider IS 'LLM provider (DEEPSEEK, ANTHROPIC, OPENAI, GEMINI)';
COMMENT ON COLUMN fhq_governance.agent_task_log.model IS 'Specific model used';
COMMENT ON COLUMN fhq_governance.agent_task_log.tokens_in IS 'Input/prompt tokens consumed';
COMMENT ON COLUMN fhq_governance.agent_task_log.tokens_out IS 'Output/completion tokens generated';
COMMENT ON COLUMN fhq_governance.agent_task_log.latency_ms IS 'Wall-clock latency in milliseconds';
COMMENT ON COLUMN fhq_governance.agent_task_log.cost_usd IS 'Calculated cost in USD';
COMMENT ON COLUMN fhq_governance.agent_task_log.stream_mode IS 'Whether streaming was used';
COMMENT ON COLUMN fhq_governance.agent_task_log.correlation_id IS 'Links related LLM calls';
COMMENT ON COLUMN fhq_governance.agent_task_log.telemetry_envelope_id IS 'FK to llm_routing_log';
*/

-- ============================================================================
-- SECTION 2: llm_routing_log EXTENSION
-- ============================================================================
-- Purpose: Extend existing llm_routing_log with cognitive and streaming fields
-- Current state: 0 rows (not being written to)
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
-- First, check existing structure
-- SELECT column_name FROM information_schema.columns
-- WHERE table_schema = 'fhq_governance' AND table_name = 'llm_routing_log';

-- Add cognitive link fields (ADR-021)
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS cognitive_parent_id UUID
    REFERENCES fhq_cognition.cognitive_nodes(cognitive_node_id),
ADD COLUMN IF NOT EXISTS protocol_ref UUID
    REFERENCES fhq_cognition.research_protocols(protocol_id),
ADD COLUMN IF NOT EXISTS cognitive_modality fhq_cognition.cognitive_modality;

-- Add streaming fields
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS stream_mode BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS stream_chunks INTEGER,
ADD COLUMN IF NOT EXISTS stream_token_accumulator INTEGER,
ADD COLUMN IF NOT EXISTS stream_first_token_ms INTEGER;

-- Add governance hash (IoS-013)
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS governance_context_hash CHAR(64);

-- Add error fields
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS error_type VARCHAR(100),
ADD COLUMN IF NOT EXISTS error_payload JSONB;

-- Add hash chain fields (ADR-013)
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS hash_chain_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS hash_self CHAR(64),
ADD COLUMN IF NOT EXISTS hash_prev CHAR(64),
ADD COLUMN IF NOT EXISTS lineage_hash CHAR(64);

COMMENT ON COLUMN fhq_governance.llm_routing_log.cognitive_parent_id IS 'Parent node in reasoning chain (ADR-021)';
COMMENT ON COLUMN fhq_governance.llm_routing_log.protocol_ref IS 'Research protocol reference (SitC)';
COMMENT ON COLUMN fhq_governance.llm_routing_log.cognitive_modality IS 'Cognitive classification';
COMMENT ON COLUMN fhq_governance.llm_routing_log.governance_context_hash IS 'IoS-013 Truth Gateway hash';
*/

-- ============================================================================
-- SECTION 3: telemetry_config TABLE (NEW)
-- ============================================================================
-- Purpose: Configuration for telemetry behavior
-- Current state: TABLE DOES NOT EXIST
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
CREATE TABLE IF NOT EXISTS fhq_governance.telemetry_config (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    config_type VARCHAR(20) NOT NULL DEFAULT 'STRING',
    description TEXT,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    created_by VARCHAR(50) NOT NULL DEFAULT 'STIG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_config_type CHECK (config_type IN ('STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN', 'JSON'))
);

-- Initial configuration values
INSERT INTO fhq_governance.telemetry_config (config_key, config_value, config_type, description) VALUES
    ('FAIL_CLOSED_ENABLED', 'true', 'BOOLEAN', 'If true, block LLM response when telemetry write fails'),
    ('STREAMING_AGGREGATION_ENABLED', 'true', 'BOOLEAN', 'Enable streaming response aggregation'),
    ('BUDGET_CHECK_ENABLED', 'true', 'BOOLEAN', 'Enable ADR-012 budget enforcement'),
    ('GOVERNANCE_HASH_REQUIRED', 'true', 'BOOLEAN', 'Require IoS-013 governance context hash'),
    ('COGNITIVE_LINKING_ENABLED', 'true', 'BOOLEAN', 'Enable ADR-021 cognitive context attachment'),
    ('DEFAULT_TIMEOUT_MS', '60000', 'INTEGER', 'Default LLM call timeout in milliseconds'),
    ('MAX_RETRY_COUNT', '3', 'INTEGER', 'Maximum retry attempts for transient failures'),
    ('TOKEN_ESTIMATION_CHARS_PER_TOKEN', '4', 'INTEGER', 'Characters per token for estimation'),
    ('HASH_CHAIN_ENABLED', 'true', 'BOOLEAN', 'Enable ADR-013 hash chain linkage');

CREATE INDEX idx_telemetry_config_key ON fhq_governance.telemetry_config(config_key);

COMMENT ON TABLE fhq_governance.telemetry_config IS 'Configuration for LLM telemetry system';
*/

-- ============================================================================
-- SECTION 4: telemetry_errors TABLE (NEW)
-- ============================================================================
-- Purpose: Capture and track LLM call errors
-- Current state: TABLE DOES NOT EXIST
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
CREATE TYPE fhq_governance.telemetry_error_type AS ENUM (
    'TIMEOUT_ERROR',
    'PROVIDER_ERROR',
    'HALLUCINATION_BLOCK',
    'IKEA_BOUNDARY_VIOLATION',
    'DIMINISHING_RETURNS_TERMINATION',
    'BUDGET_EXCEEDED',
    'GOVERNANCE_BLOCK',
    'TELEMETRY_WRITE_FAILURE',
    'VALIDATION_ERROR',
    'UNKNOWN_ERROR'
);

CREATE TABLE IF NOT EXISTS fhq_governance.telemetry_errors (
    error_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    envelope_id UUID NOT NULL,  -- Links to llm_routing_log even for failures
    agent_id VARCHAR(50) NOT NULL,
    task_name VARCHAR(255),
    error_type fhq_governance.telemetry_error_type NOT NULL,
    error_code VARCHAR(100),
    error_message TEXT,
    error_payload JSONB,
    stack_trace TEXT,
    provider VARCHAR(50),
    model VARCHAR(100),
    recoverable BOOLEAN DEFAULT false,
    retry_count INTEGER DEFAULT 0,
    retry_after_seconds INTEGER,
    http_status INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_error_agent FOREIGN KEY (agent_id)
        REFERENCES fhq_governance.agent_contracts(agent_id)
);

CREATE INDEX idx_telemetry_errors_envelope ON fhq_governance.telemetry_errors(envelope_id);
CREATE INDEX idx_telemetry_errors_agent ON fhq_governance.telemetry_errors(agent_id);
CREATE INDEX idx_telemetry_errors_type ON fhq_governance.telemetry_errors(error_type);
CREATE INDEX idx_telemetry_errors_created ON fhq_governance.telemetry_errors(created_at DESC);

COMMENT ON TABLE fhq_governance.telemetry_errors IS 'LLM call error tracking for debugging and governance';
*/

-- ============================================================================
-- SECTION 5: TRIGGERS FOR AUTOMATIC TRACKING
-- ============================================================================
-- Purpose: Automate budget increment and cost ledger updates
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
-- Trigger: Auto-increment api_budget_log on llm_routing_log insert
CREATE OR REPLACE FUNCTION fhq_governance.fn_increment_api_budget()
RETURNS TRIGGER AS $$
BEGIN
    -- Upsert daily budget entry
    INSERT INTO fhq_governance.api_budget_log (
        provider_name,
        usage_date,
        requests_made,
        daily_limit,
        usage_percent,
        last_request_at
    ) VALUES (
        NEW.provider,
        CURRENT_DATE,
        1,
        COALESCE(
            (SELECT daily_limit FROM fhq_governance.api_budget_log
             WHERE provider_name = NEW.provider ORDER BY usage_date DESC LIMIT 1),
            1000  -- Default limit
        ),
        0,
        NOW()
    )
    ON CONFLICT (provider_name, usage_date) DO UPDATE SET
        requests_made = fhq_governance.api_budget_log.requests_made + 1,
        usage_percent = (fhq_governance.api_budget_log.requests_made + 1)::numeric
                        / NULLIF(fhq_governance.api_budget_log.daily_limit, 0) * 100,
        last_request_at = NOW(),
        updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_llm_routing_budget_increment
AFTER INSERT ON fhq_governance.llm_routing_log
FOR EACH ROW
EXECUTE FUNCTION fhq_governance.fn_increment_api_budget();

-- Trigger: Auto-insert to telemetry_cost_ledger
CREATE OR REPLACE FUNCTION fhq_governance.fn_insert_cost_ledger()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO fhq_governance.telemetry_cost_ledger (
        envelope_id,
        agent_id,
        provider,
        model,
        tokens_in,
        tokens_out,
        cost_usd,
        recorded_at
    ) VALUES (
        NEW.envelope_id,
        NEW.agent_id,
        NEW.provider,
        NEW.model,
        NEW.tokens_in,
        NEW.tokens_out,
        NEW.cost_usd,
        NOW()
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_llm_routing_cost_ledger
AFTER INSERT ON fhq_governance.llm_routing_log
FOR EACH ROW
EXECUTE FUNCTION fhq_governance.fn_insert_cost_ledger();
*/

-- ============================================================================
-- SECTION 6: BACKFILL FROM reward_traces
-- ============================================================================
-- Purpose: Migrate historical LLM usage from reward_traces to telemetry tables
-- Current state: 555 rows in reward_traces with token data
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
-- Backfill llm_routing_log from reward_traces
INSERT INTO fhq_governance.llm_routing_log (
    envelope_id,
    agent_id,
    task_name,
    task_type,
    provider,
    model,
    tokens_in,
    tokens_out,
    latency_ms,
    cost_usd,
    timestamp_utc,
    correlation_id,
    stream_mode,
    created_at
)
SELECT
    trace_id as envelope_id,
    CASE
        WHEN agent_id = 'CRIO_RESEARCHER' THEN 'CRIO'
        ELSE COALESCE(agent_id, 'UNKNOWN')
    END as agent_id,
    input_query as task_name,
    'RESEARCH' as task_type,
    CASE
        WHEN model_used LIKE '%deepseek%' THEN 'DEEPSEEK'
        ELSE 'DEEPSEEK'
    END as provider,
    CASE
        WHEN model_used = 'serper+deepseek' THEN 'deepseek-reasoner'
        ELSE COALESCE(model_used, 'deepseek-reasoner')
    END as model,
    0 as tokens_in,  -- Not captured in reward_traces
    COALESCE(total_tokens, reasoning_tokens, 0) as tokens_out,
    NULL as latency_ms,  -- Not captured
    -- Estimate cost: deepseek-reasoner output at $0.00219/1k tokens
    COALESCE(total_tokens, reasoning_tokens, 0) / 1000.0 * 0.00219 as cost_usd,
    timestamp_utc,
    session_id as correlation_id,
    true as stream_mode,  -- deepseek-reasoner uses streaming
    created_at
FROM fhq_optimization.reward_traces
WHERE model_used IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM fhq_governance.llm_routing_log
    WHERE envelope_id = reward_traces.trace_id
  );

-- Log backfill operation
INSERT INTO fhq_meta.adr_audit_log (
    adr_id, event_type, gate_stage, initiated_by, decision, resolution_notes
) VALUES (
    'ADR-012',
    'BACKFILL',
    'G3',
    'STIG',
    'EXECUTED',
    'Backfilled 555 LLM calls from reward_traces to llm_routing_log'
);
*/

-- ============================================================================
-- SECTION 7: VIEWS FOR AOL DASHBOARD
-- ============================================================================
-- Purpose: Create views for AOL page telemetry display
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
-- View: Agent LLM usage summary for AOL
CREATE OR REPLACE VIEW fhq_governance.agent_llm_usage_v AS
SELECT
    agent_id,
    COUNT(*) as total_calls_7d,
    SUM(tokens_in) as total_tokens_in_7d,
    SUM(tokens_out) as total_tokens_out_7d,
    SUM(cost_usd) as total_cost_7d,
    AVG(latency_ms) as avg_latency_ms,
    COUNT(*) FILTER (WHERE error_type IS NOT NULL) as error_count_7d,
    MAX(timestamp_utc) as last_llm_call
FROM fhq_governance.llm_routing_log
WHERE timestamp_utc >= NOW() - INTERVAL '7 days'
GROUP BY agent_id;

-- View: Provider usage summary
CREATE OR REPLACE VIEW fhq_governance.provider_usage_v AS
SELECT
    provider,
    model,
    COUNT(*) as call_count_7d,
    SUM(tokens_in + tokens_out) as total_tokens_7d,
    SUM(cost_usd) as total_cost_7d,
    AVG(latency_ms) as avg_latency_ms,
    COUNT(*) FILTER (WHERE stream_mode = true) as streaming_calls,
    MIN(timestamp_utc) as first_call,
    MAX(timestamp_utc) as last_call
FROM fhq_governance.llm_routing_log
WHERE timestamp_utc >= NOW() - INTERVAL '7 days'
GROUP BY provider, model;
*/

-- ============================================================================
-- SECTION 8: PERMISSIONS
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
GRANT SELECT ON fhq_governance.telemetry_config TO PUBLIC;
GRANT SELECT ON fhq_governance.telemetry_errors TO PUBLIC;
GRANT SELECT ON fhq_governance.agent_llm_usage_v TO PUBLIC;
GRANT SELECT ON fhq_governance.provider_usage_v TO PUBLIC;
*/

-- ============================================================================
-- SECTION 9: ROLLBACK SCRIPT
-- ============================================================================
-- Purpose: Reverse all changes if PHASE 3 fails
-- ============================================================================

-- DESIGN ONLY - DO NOT EXECUTE
/*
-- ROLLBACK SCRIPT - Use only if PHASE 3 fails

-- Drop triggers
DROP TRIGGER IF EXISTS trg_llm_routing_budget_increment ON fhq_governance.llm_routing_log;
DROP TRIGGER IF EXISTS trg_llm_routing_cost_ledger ON fhq_governance.llm_routing_log;

-- Drop functions
DROP FUNCTION IF EXISTS fhq_governance.fn_increment_api_budget();
DROP FUNCTION IF EXISTS fhq_governance.fn_insert_cost_ledger();

-- Drop views
DROP VIEW IF EXISTS fhq_governance.agent_llm_usage_v;
DROP VIEW IF EXISTS fhq_governance.provider_usage_v;

-- Drop new tables
DROP TABLE IF EXISTS fhq_governance.telemetry_errors;
DROP TABLE IF EXISTS fhq_governance.telemetry_config;

-- Drop enum
DROP TYPE IF EXISTS fhq_governance.telemetry_error_type;

-- Remove added columns from llm_routing_log
ALTER TABLE fhq_governance.llm_routing_log
DROP COLUMN IF EXISTS cognitive_parent_id,
DROP COLUMN IF EXISTS protocol_ref,
DROP COLUMN IF EXISTS cognitive_modality,
DROP COLUMN IF EXISTS stream_mode,
DROP COLUMN IF EXISTS stream_chunks,
DROP COLUMN IF EXISTS stream_token_accumulator,
DROP COLUMN IF EXISTS stream_first_token_ms,
DROP COLUMN IF EXISTS governance_context_hash,
DROP COLUMN IF EXISTS error_type,
DROP COLUMN IF EXISTS error_payload,
DROP COLUMN IF EXISTS hash_chain_id,
DROP COLUMN IF EXISTS hash_self,
DROP COLUMN IF EXISTS hash_prev,
DROP COLUMN IF EXISTS lineage_hash;

-- Remove added columns from agent_task_log
ALTER TABLE fhq_governance.agent_task_log
DROP COLUMN IF EXISTS provider,
DROP COLUMN IF EXISTS model,
DROP COLUMN IF EXISTS tokens_in,
DROP COLUMN IF EXISTS tokens_out,
DROP COLUMN IF EXISTS latency_ms,
DROP COLUMN IF EXISTS cost_usd,
DROP COLUMN IF EXISTS stream_mode,
DROP COLUMN IF EXISTS stream_chunks,
DROP COLUMN IF EXISTS correlation_id,
DROP COLUMN IF EXISTS telemetry_envelope_id,
DROP COLUMN IF EXISTS error_type,
DROP COLUMN IF EXISTS error_payload;
*/

-- ============================================================================
-- END OF MIGRATION PLAN
-- ============================================================================
--
-- EXECUTION ORDER FOR PHASE 3:
-- 1. Section 1: agent_task_log extension
-- 2. Section 2: llm_routing_log extension
-- 3. Section 3: telemetry_config table
-- 4. Section 4: telemetry_errors table
-- 5. Section 5: Triggers
-- 6. Section 6: Backfill from reward_traces
-- 7. Section 7: Views
-- 8. Section 8: Permissions
--
-- CEO AUTHORIZATION REQUIRED BEFORE EXECUTION
-- ============================================================================
