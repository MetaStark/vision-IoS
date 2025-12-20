-- ============================================================================
-- MIGRATION 107: PHASE 3 LLM Telemetry Capture Infrastructure
-- Authority: CEO Directive - PHASE 3 AUTHORIZATION
-- Compliance: ADR-001, ADR-003, ADR-012, ADR-013, ADR-018, ADR-020, ADR-021
-- Executor: STIG (CTO)
-- Date: 2025-12-10
-- ============================================================================
-- "No Agent May Think Unobserved"
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: llm_routing_log EXTENSION (Cognitive + Streaming Fields)
-- ============================================================================

-- Add envelope_id for telemetry linking
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS envelope_id UUID UNIQUE;

-- Add task metadata fields
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS task_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS task_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS model VARCHAR(100),
ADD COLUMN IF NOT EXISTS tokens_in INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS tokens_out INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS latency_ms INTEGER,
ADD COLUMN IF NOT EXISTS cost_usd DECIMAL(10,6) DEFAULT 0,
ADD COLUMN IF NOT EXISTS timestamp_utc TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS correlation_id UUID;

-- Add cognitive link fields (ADR-021)
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS cognitive_parent_id UUID,
ADD COLUMN IF NOT EXISTS protocol_ref UUID,
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

-- Add backfill marker
ALTER TABLE fhq_governance.llm_routing_log
ADD COLUMN IF NOT EXISTS backfill BOOLEAN DEFAULT false;

-- Create index for envelope_id lookups
CREATE INDEX IF NOT EXISTS idx_llm_routing_envelope ON fhq_governance.llm_routing_log(envelope_id);
CREATE INDEX IF NOT EXISTS idx_llm_routing_timestamp ON fhq_governance.llm_routing_log(timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_llm_routing_agent ON fhq_governance.llm_routing_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_llm_routing_correlation ON fhq_governance.llm_routing_log(correlation_id);

COMMENT ON COLUMN fhq_governance.llm_routing_log.envelope_id IS 'Unique telemetry envelope identifier';
COMMENT ON COLUMN fhq_governance.llm_routing_log.cognitive_parent_id IS 'Parent node in reasoning chain (ADR-021)';
COMMENT ON COLUMN fhq_governance.llm_routing_log.protocol_ref IS 'Research protocol reference (SitC Chain-of-Query)';
COMMENT ON COLUMN fhq_governance.llm_routing_log.cognitive_modality IS 'Cognitive classification per ADR-021';
COMMENT ON COLUMN fhq_governance.llm_routing_log.governance_context_hash IS 'IoS-013 Truth Gateway hash';
COMMENT ON COLUMN fhq_governance.llm_routing_log.stream_mode IS 'Whether streaming was used';
COMMENT ON COLUMN fhq_governance.llm_routing_log.stream_first_token_ms IS 'Time to first token (TTFT)';
COMMENT ON COLUMN fhq_governance.llm_routing_log.backfill IS 'TRUE if row was backfilled from historical data';

-- ============================================================================
-- SECTION 2: agent_task_log EXTENSION
-- ============================================================================

-- Add telemetry link field
ALTER TABLE fhq_governance.agent_task_log
ADD COLUMN IF NOT EXISTS telemetry_envelope_id UUID,
ADD COLUMN IF NOT EXISTS stream_mode BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS stream_chunks INTEGER,
ADD COLUMN IF NOT EXISTS correlation_id UUID,
ADD COLUMN IF NOT EXISTS error_type VARCHAR(100),
ADD COLUMN IF NOT EXISTS error_payload JSONB;

CREATE INDEX IF NOT EXISTS idx_agent_task_envelope ON fhq_governance.agent_task_log(telemetry_envelope_id);

COMMENT ON COLUMN fhq_governance.agent_task_log.telemetry_envelope_id IS 'FK to llm_routing_log.envelope_id';

-- ============================================================================
-- SECTION 3: telemetry_config TABLE
-- ============================================================================

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
    ('HASH_CHAIN_ENABLED', 'true', 'BOOLEAN', 'Enable ADR-013 hash chain linkage'),
    ('COGNITIVE_CONTEXT_REQUIRED_FOR_RESEARCH', 'true', 'BOOLEAN', 'Require cognitive_parent_id for RESEARCH task types'),
    ('ASRP_CHECK_ENABLED', 'true', 'BOOLEAN', 'Enable ADR-018 ASRP state validation'),
    ('DEFCON_CHECK_ENABLED', 'true', 'BOOLEAN', 'Enable ADR-016 DEFCON level validation')
ON CONFLICT (config_key) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_telemetry_config_key ON fhq_governance.telemetry_config(config_key);

COMMENT ON TABLE fhq_governance.telemetry_config IS 'Configuration for LLM telemetry system - PHASE 3';

-- ============================================================================
-- SECTION 4: telemetry_errors TABLE
-- ============================================================================

-- Create error type enum if not exists
DO $$ BEGIN
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
        'COGNITIVE_CONTEXT_MISSING',
        'ASRP_STATE_BLOCKED',
        'DEFCON_BLOCKED',
        'UNKNOWN_ERROR'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS fhq_governance.telemetry_errors (
    error_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    envelope_id UUID NOT NULL,
    agent_id VARCHAR(50) NOT NULL,
    task_name VARCHAR(255),
    task_type VARCHAR(50),
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
    blocked_response_hash CHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_telemetry_errors_envelope ON fhq_governance.telemetry_errors(envelope_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_errors_agent ON fhq_governance.telemetry_errors(agent_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_errors_type ON fhq_governance.telemetry_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_telemetry_errors_created ON fhq_governance.telemetry_errors(created_at DESC);

COMMENT ON TABLE fhq_governance.telemetry_errors IS 'LLM call error tracking for debugging and governance - PHASE 3';

-- ============================================================================
-- SECTION 5: TRIGGERS FOR AUTOMATIC TRACKING
-- ============================================================================

-- Function: Auto-increment api_budget_log on llm_routing_log insert
CREATE OR REPLACE FUNCTION fhq_governance.fn_increment_api_budget()
RETURNS TRIGGER AS $$
BEGIN
    -- Only process if provider is set
    IF NEW.routed_provider IS NOT NULL AND NEW.routed_provider != '' THEN
        -- Upsert daily budget entry
        INSERT INTO fhq_governance.api_budget_log (
            provider_name,
            usage_date,
            requests_made,
            daily_limit,
            usage_percent,
            last_request_at
        ) VALUES (
            NEW.routed_provider,
            CURRENT_DATE,
            1,
            COALESCE(
                (SELECT daily_limit FROM fhq_governance.api_budget_log
                 WHERE provider_name = NEW.routed_provider ORDER BY usage_date DESC LIMIT 1),
                1000
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
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if exists and recreate
DROP TRIGGER IF EXISTS trg_llm_routing_budget_increment ON fhq_governance.llm_routing_log;
CREATE TRIGGER trg_llm_routing_budget_increment
AFTER INSERT ON fhq_governance.llm_routing_log
FOR EACH ROW
EXECUTE FUNCTION fhq_governance.fn_increment_api_budget();

-- Function: Update telemetry_cost_ledger aggregates
CREATE OR REPLACE FUNCTION fhq_governance.fn_update_cost_ledger()
RETURNS TRIGGER AS $$
BEGIN
    -- Upsert daily cost ledger entry
    INSERT INTO fhq_governance.telemetry_cost_ledger (
        ledger_id,
        agent_id,
        ledger_date,
        llm_requests,
        llm_tokens_in,
        llm_tokens_out,
        llm_cost_usd,
        total_cost_usd,
        total_requests,
        created_at,
        updated_at
    ) VALUES (
        gen_random_uuid(),
        NEW.agent_id,
        CURRENT_DATE,
        1,
        COALESCE(NEW.tokens_in, 0),
        COALESCE(NEW.tokens_out, 0),
        COALESCE(NEW.cost_usd, 0),
        COALESCE(NEW.cost_usd, 0),
        1,
        NOW(),
        NOW()
    )
    ON CONFLICT (agent_id, ledger_date) DO UPDATE SET
        llm_requests = fhq_governance.telemetry_cost_ledger.llm_requests + 1,
        llm_tokens_in = fhq_governance.telemetry_cost_ledger.llm_tokens_in + COALESCE(NEW.tokens_in, 0),
        llm_tokens_out = fhq_governance.telemetry_cost_ledger.llm_tokens_out + COALESCE(NEW.tokens_out, 0),
        llm_cost_usd = fhq_governance.telemetry_cost_ledger.llm_cost_usd + COALESCE(NEW.cost_usd, 0),
        total_cost_usd = fhq_governance.telemetry_cost_ledger.total_cost_usd + COALESCE(NEW.cost_usd, 0),
        total_requests = fhq_governance.telemetry_cost_ledger.total_requests + 1,
        updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_llm_routing_cost_ledger ON fhq_governance.llm_routing_log;
CREATE TRIGGER trg_llm_routing_cost_ledger
AFTER INSERT ON fhq_governance.llm_routing_log
FOR EACH ROW
EXECUTE FUNCTION fhq_governance.fn_update_cost_ledger();

-- ============================================================================
-- SECTION 6: VIEWS FOR AOL DASHBOARD
-- ============================================================================

-- View: Agent LLM usage summary for AOL
CREATE OR REPLACE VIEW fhq_governance.agent_llm_usage_v AS
SELECT
    agent_id,
    COUNT(*) as total_calls_7d,
    COALESCE(SUM(tokens_in), 0) as total_tokens_in_7d,
    COALESCE(SUM(tokens_out), 0) as total_tokens_out_7d,
    COALESCE(SUM(cost_usd), 0) as total_cost_7d,
    COALESCE(AVG(latency_ms), 0)::INTEGER as avg_latency_ms,
    COUNT(*) FILTER (WHERE error_type IS NOT NULL) as error_count_7d,
    COUNT(*) FILTER (WHERE stream_mode = true) as streaming_calls_7d,
    MAX(timestamp_utc) as last_llm_call
FROM fhq_governance.llm_routing_log
WHERE timestamp_utc >= NOW() - INTERVAL '7 days'
  AND envelope_id IS NOT NULL
GROUP BY agent_id;

-- View: Provider usage summary
CREATE OR REPLACE VIEW fhq_governance.provider_usage_v AS
SELECT
    routed_provider as provider,
    model,
    COUNT(*) as call_count_7d,
    COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens_7d,
    COALESCE(SUM(cost_usd), 0) as total_cost_7d,
    COALESCE(AVG(latency_ms), 0)::INTEGER as avg_latency_ms,
    COUNT(*) FILTER (WHERE stream_mode = true) as streaming_calls,
    MIN(timestamp_utc) as first_call,
    MAX(timestamp_utc) as last_call
FROM fhq_governance.llm_routing_log
WHERE timestamp_utc >= NOW() - INTERVAL '7 days'
  AND envelope_id IS NOT NULL
GROUP BY routed_provider, model;

-- View: Daily telemetry summary for AOL
CREATE OR REPLACE VIEW fhq_governance.daily_telemetry_summary_v AS
SELECT
    DATE(timestamp_utc) as call_date,
    COUNT(*) as total_calls,
    COUNT(DISTINCT agent_id) as unique_agents,
    COALESCE(SUM(tokens_in), 0) as total_tokens_in,
    COALESCE(SUM(tokens_out), 0) as total_tokens_out,
    COALESCE(SUM(cost_usd), 0)::DECIMAL(10,4) as total_cost_usd,
    COALESCE(AVG(latency_ms), 0)::INTEGER as avg_latency_ms,
    COUNT(*) FILTER (WHERE error_type IS NOT NULL) as error_count,
    COUNT(*) FILTER (WHERE stream_mode = true) as streaming_count,
    COUNT(*) FILTER (WHERE backfill = true) as backfilled_count
FROM fhq_governance.llm_routing_log
WHERE envelope_id IS NOT NULL
GROUP BY DATE(timestamp_utc)
ORDER BY call_date DESC;

-- ============================================================================
-- SECTION 7: PERMISSIONS
-- ============================================================================

GRANT SELECT ON fhq_governance.telemetry_config TO PUBLIC;
GRANT SELECT ON fhq_governance.telemetry_errors TO PUBLIC;
GRANT SELECT ON fhq_governance.agent_llm_usage_v TO PUBLIC;
GRANT SELECT ON fhq_governance.provider_usage_v TO PUBLIC;
GRANT SELECT ON fhq_governance.daily_telemetry_summary_v TO PUBLIC;

-- ============================================================================
-- SECTION 8: AUDIT LOG ENTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    sha256_hash
) VALUES (
    'CP-PHASE3-TELEMETRY-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS'),
    'G3_AUDIT_VERIFICATION',
    'G3',
    'ADR-012',
    'STIG',
    'EXECUTED',
    'PHASE 3 LLM Telemetry Capture Infrastructure - Migration 107 executed. Tables extended, telemetry_config created, telemetry_errors created, triggers activated, views created.',
    encode(sha256('PHASE3_TELEMETRY_MIGRATION_107'::bytea), 'hex')
);

COMMIT;

-- ============================================================================
-- PHASE 3 MIGRATION COMPLETE
-- ============================================================================
-- Next steps:
-- 1. Implement LLM Router (lib/fhq_telemetry/llm_router.py)
-- 2. Implement @metered_execution decorator (lib/fhq_telemetry/metered_execution.py)
-- 3. Apply decorator to all 12 LLM call sites
-- 4. Execute backfill from reward_traces
-- 5. Verify AOL dashboard shows non-zero telemetry
-- ============================================================================
