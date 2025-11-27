-- =====================================================
-- MIGRATION 019: ADR-012 ECONOMIC SAFETY ARCHITECTURE
-- =====================================================
--
-- Authority: LARS (ADR-012 Economic Safety Architecture)
-- Purpose: Create VEGA schema and economic safety tables
-- Compliance: ADR-012 Section 5 (Data Model)
--
-- This migration creates:
--   1. vega schema - Governance-owned economic controls
--   2. vega.llm_rate_limits - Per-agent and global rate ceilings
--   3. vega.llm_cost_limits - Per-agent, per-task, global cost ceilings
--   4. vega.llm_usage_log - Canonical usage ledger for all LLM calls
--   5. vega.llm_violation_events - Governance log for violations (hash-chained)
--
-- Database: Local Postgres instance at 127.0.0.1:54322
-- =====================================================

BEGIN;

-- =====================================================
-- SCHEMA CREATION
-- =====================================================

CREATE SCHEMA IF NOT EXISTS vega;

COMMENT ON SCHEMA vega IS 'ADR-012: VEGA-owned economic safety controls. Governance owns this schema, not agents.';

-- =====================================================
-- 5.1: LLM RATE LIMITS TABLE
-- =====================================================
-- Purpose: Prevent rate-driven failure modes (throttling, bans, pipeline storming)
-- ADR-012 Section 4.1: Rate Governance Layer

CREATE TABLE IF NOT EXISTS vega.llm_rate_limits (
    rate_limit_id BIGSERIAL PRIMARY KEY,

    -- Scope identification (NULL = global default)
    agent_id VARCHAR(50),
    provider VARCHAR(50),

    -- Rate ceilings (ADR-012 defaults)
    max_calls_per_minute INTEGER NOT NULL DEFAULT 3,
    max_calls_per_pipeline_execution INTEGER NOT NULL DEFAULT 5,
    global_daily_limit INTEGER NOT NULL DEFAULT 100,

    -- Configuration metadata
    source_adr VARCHAR(20) NOT NULL DEFAULT 'ADR-012',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL DEFAULT 'SYSTEM',
    updated_by VARCHAR(50),

    -- Constraints
    CONSTRAINT llm_rate_limits_agent_provider_unique UNIQUE (agent_id, provider)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_llm_rate_limits_agent ON vega.llm_rate_limits(agent_id);
CREATE INDEX IF NOT EXISTS idx_llm_rate_limits_provider ON vega.llm_rate_limits(provider);
CREATE INDEX IF NOT EXISTS idx_llm_rate_limits_active ON vega.llm_rate_limits(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE vega.llm_rate_limits IS 'ADR-012 Section 4.1: Rate governance layer - per-agent and global rate ceilings';
COMMENT ON COLUMN vega.llm_rate_limits.max_calls_per_minute IS 'Default: 3 (ADR-012 constitutional baseline)';
COMMENT ON COLUMN vega.llm_rate_limits.max_calls_per_pipeline_execution IS 'Default: 5 (ADR-012 constitutional baseline)';
COMMENT ON COLUMN vega.llm_rate_limits.global_daily_limit IS 'Default: 100 (ADR-012 constitutional baseline)';

-- =====================================================
-- 5.2: LLM COST LIMITS TABLE
-- =====================================================
-- Purpose: Make LLM spend predictable, capped, and provable
-- ADR-012 Section 4.2: Cost Governance Layer

CREATE TABLE IF NOT EXISTS vega.llm_cost_limits (
    cost_limit_id BIGSERIAL PRIMARY KEY,

    -- Scope identification (NULL = global default)
    agent_id VARCHAR(50),
    provider VARCHAR(50),

    -- Cost ceilings (ADR-012 defaults in USD)
    max_daily_cost DECIMAL(10, 2) NOT NULL DEFAULT 5.00,
    max_cost_per_task DECIMAL(10, 2) NOT NULL DEFAULT 0.50,
    max_cost_per_agent_per_day DECIMAL(10, 2) NOT NULL DEFAULT 1.00,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',

    -- Provider-specific pricing envelope (for cost estimation)
    estimated_min_cost_per_call DECIMAL(10, 6) DEFAULT 0.001,
    estimated_max_cost_per_call DECIMAL(10, 6) DEFAULT 0.05,

    -- Configuration metadata
    source_adr VARCHAR(20) NOT NULL DEFAULT 'ADR-012',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL DEFAULT 'SYSTEM',
    updated_by VARCHAR(50),

    -- Constraints
    CONSTRAINT llm_cost_limits_agent_provider_unique UNIQUE (agent_id, provider),
    CONSTRAINT llm_cost_limits_positive_costs CHECK (
        max_daily_cost >= 0 AND
        max_cost_per_task >= 0 AND
        max_cost_per_agent_per_day >= 0
    )
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_llm_cost_limits_agent ON vega.llm_cost_limits(agent_id);
CREATE INDEX IF NOT EXISTS idx_llm_cost_limits_provider ON vega.llm_cost_limits(provider);
CREATE INDEX IF NOT EXISTS idx_llm_cost_limits_active ON vega.llm_cost_limits(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE vega.llm_cost_limits IS 'ADR-012 Section 4.2: Cost governance layer - monetary ceilings per agent/task/day';
COMMENT ON COLUMN vega.llm_cost_limits.max_daily_cost IS 'Default: $5.00 (ADR-012 hard ceiling)';
COMMENT ON COLUMN vega.llm_cost_limits.max_cost_per_task IS 'Default: $0.50 (ADR-012 hard ceiling)';
COMMENT ON COLUMN vega.llm_cost_limits.max_cost_per_agent_per_day IS 'Default: $1.00 (ADR-012 hard ceiling)';

-- =====================================================
-- 5.3: LLM USAGE LOG TABLE
-- =====================================================
-- Purpose: Canonical usage ledger for all LLM calls (LIVE or STUB)
-- ADR-012 Section 5: Data Model

CREATE TABLE IF NOT EXISTS vega.llm_usage_log (
    usage_id BIGSERIAL PRIMARY KEY,

    -- Call identification
    agent_id VARCHAR(50) NOT NULL,
    task_id VARCHAR(100),
    cycle_id VARCHAR(100),
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100),

    -- Token usage
    tokens_in INTEGER,
    tokens_out INTEGER,
    tokens_total INTEGER GENERATED ALWAYS AS (COALESCE(tokens_in, 0) + COALESCE(tokens_out, 0)) STORED,

    -- Cost tracking
    cost_usd DECIMAL(10, 6) NOT NULL DEFAULT 0.0,
    estimated_cost_usd DECIMAL(10, 6),

    -- Performance metrics
    latency_ms INTEGER,

    -- Mode tracking (ADR-012: LIVE vs STUB)
    mode VARCHAR(10) NOT NULL DEFAULT 'STUB' CHECK (mode IN ('LIVE', 'STUB')),

    -- Request metadata
    request_hash VARCHAR(64),  -- SHA-256 of request payload
    response_hash VARCHAR(64), -- SHA-256 of response payload

    -- Cryptographic signature (ADR-008)
    signature_hex TEXT,
    public_key_hex TEXT,

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_agent ON vega.llm_usage_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_provider ON vega.llm_usage_log(provider);
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_timestamp ON vega.llm_usage_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_mode ON vega.llm_usage_log(mode);
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_task ON vega.llm_usage_log(task_id) WHERE task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_cycle ON vega.llm_usage_log(cycle_id) WHERE cycle_id IS NOT NULL;

-- Partition-ready index for daily aggregation
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_daily ON vega.llm_usage_log(DATE(timestamp), agent_id);

COMMENT ON TABLE vega.llm_usage_log IS 'ADR-012 Section 5: Canonical usage ledger for all LLM calls';
COMMENT ON COLUMN vega.llm_usage_log.mode IS 'LIVE = real API call, STUB = mock/placeholder response';

-- =====================================================
-- 5.4: LLM VIOLATION EVENTS TABLE
-- =====================================================
-- Purpose: Governance log for rate, cost, and execution violations
-- ADR-012 Section 5: Hash-chained under ADR-011

CREATE TABLE IF NOT EXISTS vega.llm_violation_events (
    violation_id BIGSERIAL PRIMARY KEY,

    -- Violation context
    agent_id VARCHAR(50) NOT NULL,
    task_id VARCHAR(100),
    cycle_id VARCHAR(100),
    provider VARCHAR(50),

    -- Violation classification (ADR-012 Section 4)
    violation_type VARCHAR(20) NOT NULL CHECK (
        violation_type IN ('RATE', 'COST', 'EXECUTION')
    ),
    violation_subtype VARCHAR(50),  -- e.g., 'PER_MINUTE', 'DAILY_COST', 'STEPS_EXCEEDED'

    -- Governance action taken
    governance_action VARCHAR(30) NOT NULL CHECK (
        governance_action IN ('NONE', 'WARN', 'SUSPEND_RECOMMENDATION', 'SWITCH_TO_STUB')
    ),

    -- Severity classification (ADR-002)
    severity VARCHAR(20) NOT NULL DEFAULT 'CLASS_B' CHECK (
        severity IN ('CLASS_A', 'CLASS_B', 'CLASS_C')
    ),

    -- Discrepancy score (ADR-010 integration)
    discrepancy_score DECIMAL(5, 4),

    -- Evidence bundle (JSONB for flexibility)
    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Limit values at time of violation
    limit_value DECIMAL(10, 4),
    actual_value DECIMAL(10, 4),

    -- Hash chain (ADR-011 Fortress integration)
    hash_prev VARCHAR(64),
    hash_self VARCHAR(64) NOT NULL,

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Resolution tracking
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(50),
    resolution_notes TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_llm_violation_events_agent ON vega.llm_violation_events(agent_id);
CREATE INDEX IF NOT EXISTS idx_llm_violation_events_type ON vega.llm_violation_events(violation_type);
CREATE INDEX IF NOT EXISTS idx_llm_violation_events_action ON vega.llm_violation_events(governance_action);
CREATE INDEX IF NOT EXISTS idx_llm_violation_events_timestamp ON vega.llm_violation_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_llm_violation_events_unresolved ON vega.llm_violation_events(is_resolved) WHERE is_resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_llm_violation_events_severity ON vega.llm_violation_events(severity);
CREATE INDEX IF NOT EXISTS idx_llm_violation_events_hash_chain ON vega.llm_violation_events(hash_prev);

-- Daily index for QG-F6 checks
CREATE INDEX IF NOT EXISTS idx_llm_violation_events_24h ON vega.llm_violation_events(timestamp)
    WHERE timestamp > NOW() - INTERVAL '24 hours';

COMMENT ON TABLE vega.llm_violation_events IS 'ADR-012 Section 5: Hash-chained governance log for violations';
COMMENT ON COLUMN vega.llm_violation_events.violation_type IS 'RATE = rate limit, COST = cost ceiling, EXECUTION = steps/latency/tokens';
COMMENT ON COLUMN vega.llm_violation_events.governance_action IS 'Action taken: NONE, WARN, SUSPEND_RECOMMENDATION, SWITCH_TO_STUB';
COMMENT ON COLUMN vega.llm_violation_events.hash_self IS 'SHA-256 hash for Fortress integrity (ADR-011)';

-- =====================================================
-- 5.5: EXECUTION GOVERNANCE CONFIG TABLE
-- =====================================================
-- Purpose: Execution ceilings for reasoning depth control
-- ADR-012 Section 4.3: Execution Governance Layer

CREATE TABLE IF NOT EXISTS vega.llm_execution_limits (
    execution_limit_id BIGSERIAL PRIMARY KEY,

    -- Scope identification (NULL = global default)
    agent_id VARCHAR(50),
    provider VARCHAR(50),

    -- Execution ceilings (ADR-012 defaults)
    max_llm_steps_per_task INTEGER NOT NULL DEFAULT 3,
    max_total_latency_ms INTEGER NOT NULL DEFAULT 3000,
    max_total_tokens_generated INTEGER,  -- NULL = use provider default
    abort_on_overrun BOOLEAN NOT NULL DEFAULT TRUE,

    -- Configuration metadata
    source_adr VARCHAR(20) NOT NULL DEFAULT 'ADR-012',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL DEFAULT 'SYSTEM',

    -- Constraints
    CONSTRAINT llm_execution_limits_agent_provider_unique UNIQUE (agent_id, provider)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_llm_execution_limits_agent ON vega.llm_execution_limits(agent_id);
CREATE INDEX IF NOT EXISTS idx_llm_execution_limits_active ON vega.llm_execution_limits(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE vega.llm_execution_limits IS 'ADR-012 Section 4.3: Execution governance - reasoning depth control';
COMMENT ON COLUMN vega.llm_execution_limits.max_llm_steps_per_task IS 'Default: 3 (prevents infinite thought spirals)';
COMMENT ON COLUMN vega.llm_execution_limits.max_total_latency_ms IS 'Default: 3000ms (ADR-012 ceiling)';

-- =====================================================
-- 5.6: DAILY AGGREGATES VIEW
-- =====================================================
-- Purpose: Efficient daily cost/usage queries for governance

CREATE OR REPLACE VIEW vega.llm_daily_usage AS
SELECT
    DATE(timestamp) AS usage_date,
    agent_id,
    provider,
    mode,
    COUNT(*) AS call_count,
    SUM(cost_usd) AS total_cost_usd,
    SUM(tokens_in) AS total_tokens_in,
    SUM(tokens_out) AS total_tokens_out,
    AVG(latency_ms) AS avg_latency_ms,
    MAX(latency_ms) AS max_latency_ms
FROM vega.llm_usage_log
GROUP BY DATE(timestamp), agent_id, provider, mode;

COMMENT ON VIEW vega.llm_daily_usage IS 'ADR-012: Daily aggregated LLM usage for cost governance';

-- =====================================================
-- 5.7: VIOLATION SUMMARY VIEW
-- =====================================================
-- Purpose: Quick violation status for QG-F6 gate checks

CREATE OR REPLACE VIEW vega.llm_violation_summary_24h AS
SELECT
    violation_type,
    governance_action,
    severity,
    COUNT(*) AS violation_count,
    MAX(timestamp) AS last_violation_at
FROM vega.llm_violation_events
WHERE timestamp > NOW() - INTERVAL '24 hours'
    AND is_resolved = FALSE
GROUP BY violation_type, governance_action, severity;

COMMENT ON VIEW vega.llm_violation_summary_24h IS 'ADR-012: 24-hour violation summary for QG-F6 quality gate';

-- =====================================================
-- 5.8: DEFAULT CONFIGURATION (Constitutional Baselines)
-- =====================================================
-- Insert global defaults per ADR-012 Section 4

-- Global rate limits (no agent_id = system default)
INSERT INTO vega.llm_rate_limits (agent_id, provider, max_calls_per_minute, max_calls_per_pipeline_execution, global_daily_limit, created_by)
VALUES (NULL, NULL, 3, 5, 100, 'ADR-012-BOOTSTRAP')
ON CONFLICT (agent_id, provider) DO NOTHING;

-- Global cost limits
INSERT INTO vega.llm_cost_limits (agent_id, provider, max_daily_cost, max_cost_per_task, max_cost_per_agent_per_day, created_by)
VALUES (NULL, NULL, 5.00, 0.50, 1.00, 'ADR-012-BOOTSTRAP')
ON CONFLICT (agent_id, provider) DO NOTHING;

-- Global execution limits
INSERT INTO vega.llm_execution_limits (agent_id, provider, max_llm_steps_per_task, max_total_latency_ms, abort_on_overrun, created_by)
VALUES (NULL, NULL, 3, 3000, TRUE, 'ADR-012-BOOTSTRAP')
ON CONFLICT (agent_id, provider) DO NOTHING;

-- Per-agent defaults for core agents
INSERT INTO vega.llm_rate_limits (agent_id, provider, max_calls_per_minute, max_calls_per_pipeline_execution, global_daily_limit, created_by)
VALUES
    ('FINN', NULL, 3, 5, 50, 'ADR-012-BOOTSTRAP'),
    ('STIG', NULL, 2, 3, 30, 'ADR-012-BOOTSTRAP'),
    ('LARS', NULL, 5, 10, 100, 'ADR-012-BOOTSTRAP'),
    ('VEGA', NULL, 2, 3, 30, 'ADR-012-BOOTSTRAP'),
    ('LINE', NULL, 10, 20, 200, 'ADR-012-BOOTSTRAP')  -- LINE uses data APIs, higher limits
ON CONFLICT (agent_id, provider) DO NOTHING;

INSERT INTO vega.llm_cost_limits (agent_id, provider, max_daily_cost, max_cost_per_task, max_cost_per_agent_per_day, created_by)
VALUES
    ('FINN', NULL, 1.00, 0.50, 1.00, 'ADR-012-BOOTSTRAP'),
    ('STIG', NULL, 0.50, 0.25, 0.50, 'ADR-012-BOOTSTRAP'),
    ('LARS', NULL, 2.00, 0.50, 2.00, 'ADR-012-BOOTSTRAP'),
    ('VEGA', NULL, 0.50, 0.25, 0.50, 'ADR-012-BOOTSTRAP'),
    ('LINE', NULL, 0.10, 0.05, 0.10, 'ADR-012-BOOTSTRAP')  -- LINE uses data APIs, minimal LLM
ON CONFLICT (agent_id, provider) DO NOTHING;

-- =====================================================
-- 5.9: HELPER FUNCTIONS
-- =====================================================

-- Function to compute hash for violation event chain
CREATE OR REPLACE FUNCTION vega.compute_violation_hash(
    p_violation_id BIGINT,
    p_agent_id VARCHAR,
    p_violation_type VARCHAR,
    p_governance_action VARCHAR,
    p_timestamp TIMESTAMPTZ,
    p_details JSONB,
    p_hash_prev VARCHAR
) RETURNS VARCHAR AS $$
DECLARE
    v_payload TEXT;
BEGIN
    v_payload := p_violation_id::TEXT || '|' ||
                 COALESCE(p_agent_id, 'NULL') || '|' ||
                 p_violation_type || '|' ||
                 p_governance_action || '|' ||
                 p_timestamp::TEXT || '|' ||
                 p_details::TEXT || '|' ||
                 COALESCE(p_hash_prev, 'GENESIS');

    RETURN encode(sha256(v_payload::bytea), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION vega.compute_violation_hash IS 'ADR-012/ADR-011: Compute SHA-256 hash for violation event chain';

-- Function to check QG-F6 (Economic Safety Gate)
CREATE OR REPLACE FUNCTION vega.check_qg_f6()
RETURNS TABLE (
    gate_passed BOOLEAN,
    rate_violations INTEGER,
    cost_violations INTEGER,
    execution_violations INTEGER,
    last_violation_at TIMESTAMPTZ,
    check_timestamp TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    WITH violation_counts AS (
        SELECT
            SUM(CASE WHEN violation_type = 'RATE' THEN 1 ELSE 0 END)::INTEGER AS rate_v,
            SUM(CASE WHEN violation_type = 'COST' THEN 1 ELSE 0 END)::INTEGER AS cost_v,
            SUM(CASE WHEN violation_type = 'EXECUTION' THEN 1 ELSE 0 END)::INTEGER AS exec_v,
            MAX(timestamp) AS last_v
        FROM vega.llm_violation_events
        WHERE timestamp > NOW() - INTERVAL '24 hours'
            AND is_resolved = FALSE
    )
    SELECT
        (COALESCE(rate_v, 0) = 0 AND COALESCE(cost_v, 0) = 0 AND COALESCE(exec_v, 0) = 0) AS gate_passed,
        COALESCE(rate_v, 0) AS rate_violations,
        COALESCE(cost_v, 0) AS cost_violations,
        COALESCE(exec_v, 0) AS execution_violations,
        last_v AS last_violation_at,
        NOW() AS check_timestamp
    FROM violation_counts;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vega.check_qg_f6 IS 'ADR-012 Section 6: QG-F6 Economic Safety Gate check';

-- =====================================================
-- COMMIT TRANSACTION
-- =====================================================

COMMIT;

-- =====================================================
-- VERIFICATION QUERIES (for manual testing)
-- =====================================================

-- Verify schema created
-- SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'vega';

-- Verify tables created
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'vega';

-- Verify default limits
-- SELECT * FROM vega.llm_rate_limits;
-- SELECT * FROM vega.llm_cost_limits;
-- SELECT * FROM vega.llm_execution_limits;

-- Check QG-F6 gate
-- SELECT * FROM vega.check_qg_f6();
