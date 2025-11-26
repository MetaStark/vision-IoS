-- ============================================================================
-- VEGA ECONOMIC SAFETY (ADR-012)
-- ============================================================================
-- Migration: 021_vega_economic_safety.sql
-- Authority: ADR-012_2026_PRODUCTION (Economic Safety & LLM Cost Control)
-- Database: 127.0.0.1:54322 (Local Supabase PostgreSQL)
--
-- PURPOSE:
-- Implements ADR-012 economic safety controls:
-- 1. LLM usage logging and cost tracking
-- 2. Rate limiting infrastructure
-- 3. Budget enforcement
-- 4. Cost alerts and thresholds
--
-- ADR-012 REQUIREMENTS:
-- - Per-summary cost ceiling: $0.050 USD
-- - Daily budget cap: $500 USD
-- - Daily rate limit: 100 executions
-- - Real-time cost tracking
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CREATE VEGA SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS vega;

-- ============================================================================
-- SECTION 2: LLM USAGE LOG
-- Core cost tracking table
-- ============================================================================

CREATE TABLE IF NOT EXISTS vega.llm_usage_log (
    usage_id BIGSERIAL PRIMARY KEY,
    usage_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Agent identification
    agent_id VARCHAR(50) NOT NULL,
    agent_version VARCHAR(50),

    -- Operation context
    operation_type VARCHAR(100) NOT NULL,  -- 'conflict_summary', 'regime_analysis', etc.
    operation_id VARCHAR(100),  -- Unique operation identifier
    cycle_id VARCHAR(100),  -- Orchestrator cycle reference

    -- Model information
    llm_provider VARCHAR(50) NOT NULL DEFAULT 'anthropic',  -- anthropic, openai, etc.
    llm_model VARCHAR(100) NOT NULL,  -- claude-3-5-sonnet, gpt-4, etc.
    llm_model_version VARCHAR(50),

    -- Token usage
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,

    -- Cost calculation
    input_cost_usd DECIMAL(10,6) NOT NULL DEFAULT 0.0,
    output_cost_usd DECIMAL(10,6) NOT NULL DEFAULT 0.0,
    total_cost_usd DECIMAL(10,6) GENERATED ALWAYS AS (input_cost_usd + output_cost_usd) STORED,

    -- Rate information
    cost_per_1k_input DECIMAL(10,6),
    cost_per_1k_output DECIMAL(10,6),

    -- Request metadata
    request_id VARCHAR(100),
    latency_ms INTEGER,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_code VARCHAR(50),
    error_message TEXT,

    -- Budget tracking
    daily_budget_remaining DECIMAL(10,2),
    daily_calls_remaining INTEGER,

    -- Compliance
    within_ceiling BOOLEAN NOT NULL DEFAULT TRUE,
    ceiling_value DECIMAL(10,6) DEFAULT 0.050,  -- ADR-012: $0.05 per summary

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT positive_tokens CHECK (input_tokens >= 0 AND output_tokens >= 0),
    CONSTRAINT positive_costs CHECK (input_cost_usd >= 0 AND output_cost_usd >= 0)
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_timestamp ON vega.llm_usage_log(usage_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_agent ON vega.llm_usage_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_operation ON vega.llm_usage_log(operation_type);
CREATE INDEX IF NOT EXISTS idx_llm_usage_cycle ON vega.llm_usage_log(cycle_id);
CREATE INDEX IF NOT EXISTS idx_llm_usage_date ON vega.llm_usage_log(DATE(usage_timestamp));

COMMENT ON TABLE vega.llm_usage_log IS
    'ADR-012: LLM API usage and cost tracking';

-- ============================================================================
-- SECTION 3: COST TRACKING (Aggregated)
-- Daily/hourly cost aggregations
-- ============================================================================

CREATE TABLE IF NOT EXISTS vega.cost_tracking (
    tracking_id BIGSERIAL PRIMARY KEY,
    tracking_date DATE NOT NULL,
    tracking_hour INTEGER CHECK (tracking_hour BETWEEN 0 AND 23),

    -- Aggregation level
    aggregation_level VARCHAR(20) NOT NULL CHECK (
        aggregation_level IN ('HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY')
    ),

    -- Agent breakdown
    agent_id VARCHAR(50),  -- NULL for system total

    -- Metrics
    total_calls INTEGER NOT NULL DEFAULT 0,
    successful_calls INTEGER NOT NULL DEFAULT 0,
    failed_calls INTEGER NOT NULL DEFAULT 0,

    -- Token totals
    total_input_tokens BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,

    -- Cost totals
    total_cost_usd DECIMAL(12,6) NOT NULL DEFAULT 0.0,
    avg_cost_per_call DECIMAL(10,6),
    max_single_call_cost DECIMAL(10,6),
    min_single_call_cost DECIMAL(10,6),

    -- Budget status
    budget_used_pct DECIMAL(5,2),
    budget_remaining_usd DECIMAL(12,6),
    rate_limit_hits INTEGER DEFAULT 0,

    -- Ceiling violations
    ceiling_violations INTEGER DEFAULT 0,

    -- Audit
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint
    CONSTRAINT unique_tracking_period UNIQUE (tracking_date, tracking_hour, aggregation_level, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_cost_tracking_date ON vega.cost_tracking(tracking_date DESC);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_agent ON vega.cost_tracking(agent_id);

COMMENT ON TABLE vega.cost_tracking IS
    'ADR-012: Aggregated cost tracking by period';

-- ============================================================================
-- SECTION 4: RATE LIMITS
-- Rate limit configuration and enforcement
-- ============================================================================

CREATE TABLE IF NOT EXISTS vega.rate_limits (
    limit_id SERIAL PRIMARY KEY,
    limit_name VARCHAR(100) NOT NULL UNIQUE,
    limit_type VARCHAR(50) NOT NULL CHECK (
        limit_type IN ('CALLS_PER_MINUTE', 'CALLS_PER_HOUR', 'CALLS_PER_DAY',
                       'COST_PER_CALL', 'COST_PER_DAY', 'TOKENS_PER_MINUTE')
    ),

    -- Scope
    scope_type VARCHAR(50) NOT NULL CHECK (
        scope_type IN ('SYSTEM', 'AGENT', 'OPERATION')
    ),
    scope_value VARCHAR(100),  -- Agent ID or operation type

    -- Limit values
    limit_value DECIMAL(12,4) NOT NULL,
    warning_threshold DECIMAL(12,4),  -- Warn at this level
    hard_limit DECIMAL(12,4),  -- Block at this level

    -- Enforcement
    enforcement_action VARCHAR(50) NOT NULL CHECK (
        enforcement_action IN ('WARN', 'THROTTLE', 'BLOCK', 'ALERT')
    ),

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- ADR reference
    governing_adr VARCHAR(20) DEFAULT 'ADR-012',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

COMMENT ON TABLE vega.rate_limits IS
    'ADR-012: Rate limit definitions and thresholds';

-- ============================================================================
-- SECTION 5: BUDGET ALLOCATIONS
-- Daily/monthly budget allocation
-- ============================================================================

CREATE TABLE IF NOT EXISTS vega.budget_allocations (
    allocation_id SERIAL PRIMARY KEY,
    budget_period VARCHAR(20) NOT NULL CHECK (
        budget_period IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY')
    ),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Scope
    scope_type VARCHAR(50) NOT NULL CHECK (
        scope_type IN ('SYSTEM', 'AGENT', 'PROJECT')
    ),
    scope_value VARCHAR(100),

    -- Budget
    allocated_budget_usd DECIMAL(12,2) NOT NULL,
    used_budget_usd DECIMAL(12,6) NOT NULL DEFAULT 0.0,
    remaining_budget_usd DECIMAL(12,6) GENERATED ALWAYS AS (allocated_budget_usd - used_budget_usd) STORED,

    -- Utilization
    utilization_pct DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE WHEN allocated_budget_usd > 0
            THEN (used_budget_usd / allocated_budget_usd * 100)
            ELSE 0
        END
    ) STORED,

    -- Alerts
    alert_threshold_pct DECIMAL(5,2) DEFAULT 80.0,
    alert_triggered BOOLEAN DEFAULT FALSE,
    alert_triggered_at TIMESTAMPTZ,

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('ACTIVE', 'EXHAUSTED', 'EXPIRED', 'SUSPENDED')
    ) DEFAULT 'ACTIVE',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT valid_period CHECK (period_end >= period_start),
    CONSTRAINT unique_budget_period UNIQUE (budget_period, period_start, scope_type, scope_value)
);

CREATE INDEX IF NOT EXISTS idx_budget_period ON vega.budget_allocations(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_budget_status ON vega.budget_allocations(status);

COMMENT ON TABLE vega.budget_allocations IS
    'ADR-012: Budget allocation and tracking';

-- ============================================================================
-- SECTION 6: COST ALERTS
-- Alert history for budget/rate violations
-- ============================================================================

CREATE TABLE IF NOT EXISTS vega.cost_alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    alert_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Alert type
    alert_type VARCHAR(50) NOT NULL CHECK (
        alert_type IN ('BUDGET_WARNING', 'BUDGET_EXCEEDED', 'RATE_LIMIT_HIT',
                       'CEILING_VIOLATION', 'ANOMALY_DETECTED', 'COST_SPIKE')
    ),
    severity VARCHAR(20) NOT NULL CHECK (
        severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
    ),

    -- Context
    agent_id VARCHAR(50),
    operation_type VARCHAR(100),
    cycle_id VARCHAR(100),

    -- Alert details
    alert_message TEXT NOT NULL,
    alert_data JSONB NOT NULL DEFAULT '{}',

    -- Thresholds
    threshold_type VARCHAR(50),
    threshold_value DECIMAL(12,6),
    actual_value DECIMAL(12,6),

    -- Response
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(50),
    acknowledged_at TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Escalation
    escalated BOOLEAN DEFAULT FALSE,
    escalated_to VARCHAR(50),
    escalated_at TIMESTAMPTZ,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_alerts_timestamp ON vega.cost_alerts(alert_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_type ON vega.cost_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_severity ON vega.cost_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_unacknowledged ON vega.cost_alerts(acknowledged) WHERE acknowledged = FALSE;

COMMENT ON TABLE vega.cost_alerts IS
    'ADR-012: Cost and rate limit alert history';

-- ============================================================================
-- SECTION 7: SEED ADR-012 RATE LIMITS
-- ============================================================================

INSERT INTO vega.rate_limits (limit_name, limit_type, scope_type, scope_value, limit_value, warning_threshold, hard_limit, enforcement_action)
VALUES
    -- System-wide limits (ADR-012)
    ('system_daily_budget', 'COST_PER_DAY', 'SYSTEM', NULL, 500.00, 400.00, 500.00, 'BLOCK'),
    ('system_daily_calls', 'CALLS_PER_DAY', 'SYSTEM', NULL, 100, 80, 100, 'BLOCK'),
    ('per_summary_ceiling', 'COST_PER_CALL', 'OPERATION', 'conflict_summary', 0.050, 0.040, 0.050, 'BLOCK'),

    -- Agent-specific limits
    ('finn_daily_calls', 'CALLS_PER_DAY', 'AGENT', 'FINN', 50, 40, 50, 'THROTTLE'),
    ('finn_hourly_calls', 'CALLS_PER_HOUR', 'AGENT', 'FINN', 10, 8, 10, 'THROTTLE'),

    -- Token limits
    ('system_tokens_per_minute', 'TOKENS_PER_MINUTE', 'SYSTEM', NULL, 100000, 80000, 100000, 'THROTTLE')
ON CONFLICT (limit_name) DO NOTHING;

-- ============================================================================
-- SECTION 8: SEED INITIAL BUDGET ALLOCATION
-- ============================================================================

INSERT INTO vega.budget_allocations (budget_period, period_start, period_end, scope_type, allocated_budget_usd, alert_threshold_pct)
VALUES
    ('DAILY', CURRENT_DATE, CURRENT_DATE, 'SYSTEM', 500.00, 80.0),
    ('MONTHLY', DATE_TRUNC('month', CURRENT_DATE)::DATE,
     (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month - 1 day')::DATE,
     'SYSTEM', 5000.00, 80.0)
ON CONFLICT ON CONSTRAINT unique_budget_period DO NOTHING;

-- ============================================================================
-- SECTION 9: VEGA COST TRACKING FUNCTIONS
-- ============================================================================

-- Function: Log LLM usage
CREATE OR REPLACE FUNCTION vega.log_llm_usage(
    p_agent_id VARCHAR(50),
    p_operation_type VARCHAR(100),
    p_llm_model VARCHAR(100),
    p_input_tokens INTEGER,
    p_output_tokens INTEGER,
    p_input_cost DECIMAL(10,6),
    p_output_cost DECIMAL(10,6),
    p_cycle_id VARCHAR(100) DEFAULT NULL,
    p_request_id VARCHAR(100) DEFAULT NULL,
    p_latency_ms INTEGER DEFAULT NULL
)
RETURNS TABLE (
    usage_id BIGINT,
    total_cost DECIMAL(10,6),
    within_ceiling BOOLEAN,
    daily_remaining DECIMAL(10,6)
) AS $$
DECLARE
    v_usage_id BIGINT;
    v_total_cost DECIMAL(10,6);
    v_within_ceiling BOOLEAN;
    v_daily_used DECIMAL(10,6);
    v_daily_remaining DECIMAL(10,6);
    v_ceiling DECIMAL(10,6) := 0.050;  -- ADR-012 ceiling
BEGIN
    v_total_cost := p_input_cost + p_output_cost;
    v_within_ceiling := v_total_cost <= v_ceiling;

    -- Get daily usage
    SELECT COALESCE(SUM(total_cost_usd), 0) INTO v_daily_used
    FROM vega.llm_usage_log
    WHERE DATE(usage_timestamp) = CURRENT_DATE;

    v_daily_remaining := 500.00 - v_daily_used - v_total_cost;

    -- Insert usage record
    INSERT INTO vega.llm_usage_log (
        agent_id, operation_type, llm_model, input_tokens, output_tokens,
        input_cost_usd, output_cost_usd, cycle_id, request_id, latency_ms,
        within_ceiling, daily_budget_remaining
    ) VALUES (
        p_agent_id, p_operation_type, p_llm_model, p_input_tokens, p_output_tokens,
        p_input_cost, p_output_cost, p_cycle_id, p_request_id, p_latency_ms,
        v_within_ceiling, v_daily_remaining
    )
    RETURNING llm_usage_log.usage_id INTO v_usage_id;

    -- Create alert if ceiling violated
    IF NOT v_within_ceiling THEN
        INSERT INTO vega.cost_alerts (
            alert_type, severity, agent_id, operation_type, cycle_id,
            alert_message, alert_data, threshold_value, actual_value
        ) VALUES (
            'CEILING_VIOLATION', 'WARNING', p_agent_id, p_operation_type, p_cycle_id,
            format('Cost ceiling exceeded: $%s > $%s', v_total_cost, v_ceiling),
            jsonb_build_object('total_cost', v_total_cost, 'ceiling', v_ceiling),
            v_ceiling, v_total_cost
        );
    END IF;

    -- Check daily budget
    IF v_daily_remaining < 0 THEN
        INSERT INTO vega.cost_alerts (
            alert_type, severity, agent_id,
            alert_message, alert_data, threshold_value, actual_value
        ) VALUES (
            'BUDGET_EXCEEDED', 'CRITICAL', p_agent_id,
            'Daily budget exhausted',
            jsonb_build_object('daily_used', v_daily_used + v_total_cost, 'daily_budget', 500.00),
            500.00, v_daily_used + v_total_cost
        );
    END IF;

    usage_id := v_usage_id;
    total_cost := v_total_cost;
    within_ceiling := v_within_ceiling;
    daily_remaining := v_daily_remaining;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vega.log_llm_usage IS
    'ADR-012: Log LLM usage with automatic ceiling/budget checking';

-- Function: Check rate limit
CREATE OR REPLACE FUNCTION vega.check_rate_limit(
    p_agent_id VARCHAR(50),
    p_operation_type VARCHAR(100) DEFAULT NULL
)
RETURNS TABLE (
    allowed BOOLEAN,
    reason VARCHAR(200),
    calls_remaining INTEGER,
    budget_remaining DECIMAL(10,6)
) AS $$
DECLARE
    v_daily_calls INTEGER;
    v_daily_cost DECIMAL(10,6);
    v_daily_call_limit INTEGER := 100;
    v_daily_budget DECIMAL(10,6) := 500.00;
BEGIN
    -- Get daily usage
    SELECT COUNT(*), COALESCE(SUM(total_cost_usd), 0)
    INTO v_daily_calls, v_daily_cost
    FROM vega.llm_usage_log
    WHERE DATE(usage_timestamp) = CURRENT_DATE;

    -- Check limits
    IF v_daily_calls >= v_daily_call_limit THEN
        allowed := FALSE;
        reason := 'Daily call limit reached (100)';
        calls_remaining := 0;
        budget_remaining := v_daily_budget - v_daily_cost;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_daily_cost >= v_daily_budget THEN
        allowed := FALSE;
        reason := 'Daily budget exhausted ($500)';
        calls_remaining := v_daily_call_limit - v_daily_calls;
        budget_remaining := 0;
        RETURN NEXT;
        RETURN;
    END IF;

    allowed := TRUE;
    reason := 'OK';
    calls_remaining := v_daily_call_limit - v_daily_calls;
    budget_remaining := v_daily_budget - v_daily_cost;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vega.check_rate_limit IS
    'ADR-012: Check if operation is allowed within rate limits';

-- Function: Get daily cost summary
CREATE OR REPLACE FUNCTION vega.get_daily_cost_summary(
    p_date DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    summary_date DATE,
    total_calls INTEGER,
    total_cost DECIMAL(10,6),
    avg_cost_per_call DECIMAL(10,6),
    budget_used_pct DECIMAL(5,2),
    calls_by_agent JSONB,
    cost_by_agent JSONB
) AS $$
BEGIN
    summary_date := p_date;

    SELECT
        COUNT(*),
        COALESCE(SUM(total_cost_usd), 0),
        COALESCE(AVG(total_cost_usd), 0),
        COALESCE(SUM(total_cost_usd) / 500.00 * 100, 0)
    INTO total_calls, total_cost, avg_cost_per_call, budget_used_pct
    FROM vega.llm_usage_log
    WHERE DATE(usage_timestamp) = p_date;

    SELECT jsonb_object_agg(agent_id, call_count)
    INTO calls_by_agent
    FROM (
        SELECT agent_id, COUNT(*) as call_count
        FROM vega.llm_usage_log
        WHERE DATE(usage_timestamp) = p_date
        GROUP BY agent_id
    ) t;

    SELECT jsonb_object_agg(agent_id, agent_cost)
    INTO cost_by_agent
    FROM (
        SELECT agent_id, SUM(total_cost_usd) as agent_cost
        FROM vega.llm_usage_log
        WHERE DATE(usage_timestamp) = p_date
        GROUP BY agent_id
    ) t;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vega.get_daily_cost_summary IS
    'ADR-012: Get daily cost summary with agent breakdown';

-- ============================================================================
-- SECTION 10: VIEWS
-- ============================================================================

-- Daily cost dashboard
CREATE OR REPLACE VIEW vega.v_daily_cost_dashboard AS
SELECT
    DATE(usage_timestamp) as date,
    COUNT(*) as total_calls,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(total_cost_usd) as total_cost,
    AVG(total_cost_usd) as avg_cost_per_call,
    MAX(total_cost_usd) as max_cost_per_call,
    SUM(total_cost_usd) / 500.00 * 100 as budget_used_pct,
    COUNT(*) FILTER (WHERE NOT within_ceiling) as ceiling_violations,
    AVG(latency_ms) as avg_latency_ms
FROM vega.llm_usage_log
GROUP BY DATE(usage_timestamp)
ORDER BY date DESC;

COMMENT ON VIEW vega.v_daily_cost_dashboard IS
    'ADR-012: Daily cost and usage dashboard';

-- Agent cost breakdown
CREATE OR REPLACE VIEW vega.v_agent_cost_breakdown AS
SELECT
    agent_id,
    DATE(usage_timestamp) as date,
    COUNT(*) as calls,
    SUM(total_cost_usd) as total_cost,
    AVG(total_cost_usd) as avg_cost,
    SUM(input_tokens) as input_tokens,
    SUM(output_tokens) as output_tokens
FROM vega.llm_usage_log
GROUP BY agent_id, DATE(usage_timestamp)
ORDER BY date DESC, total_cost DESC;

COMMENT ON VIEW vega.v_agent_cost_breakdown IS
    'ADR-012: Cost breakdown by agent';

-- Active alerts
CREATE OR REPLACE VIEW vega.v_active_alerts AS
SELECT
    alert_id,
    alert_timestamp,
    alert_type,
    severity,
    agent_id,
    alert_message,
    threshold_value,
    actual_value
FROM vega.cost_alerts
WHERE acknowledged = FALSE
ORDER BY
    CASE severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'ERROR' THEN 2
        WHEN 'WARNING' THEN 3
        ELSE 4
    END,
    alert_timestamp DESC;

COMMENT ON VIEW vega.v_active_alerts IS
    'ADR-012: Active (unacknowledged) cost alerts';

-- ============================================================================
-- SECTION 11: LOG MIGRATION
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    event_type, event_category, severity, actor, action, target,
    event_data, authority, adr_compliance, event_hash, hash_chain_id
) VALUES (
    'schema_migration', 'governance', 'INFO', 'VEGA',
    'APPLY_MIGRATION_021', '021_vega_economic_safety.sql',
    jsonb_build_object(
        'migration_number', '021',
        'schema_created', 'vega',
        'tables_created', ARRAY['llm_usage_log', 'cost_tracking', 'rate_limits', 'budget_allocations', 'cost_alerts'],
        'functions_created', ARRAY['log_llm_usage', 'check_rate_limit', 'get_daily_cost_summary'],
        'adr_reference', 'ADR-012',
        'database', '127.0.0.1:54322'
    ),
    'ADR-012_2026_PRODUCTION',
    ARRAY['ADR-012'],
    encode(sha256('MIGRATION_021_VEGA_ECONOMIC_SAFETY'::bytea), 'hex'),
    'VEGA_GOVERNANCE_CHAIN'
);

-- ============================================================================
-- SECTION 12: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_table_count INTEGER;
    v_function_count INTEGER;
    v_limit_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_table_count
    FROM information_schema.tables
    WHERE table_schema = 'vega';

    SELECT COUNT(*) INTO v_function_count
    FROM information_schema.routines
    WHERE routine_schema = 'vega';

    SELECT COUNT(*) INTO v_limit_count
    FROM vega.rate_limits WHERE is_active = TRUE;

    RAISE NOTICE '====================================================';
    RAISE NOTICE 'MIGRATION 021 VERIFICATION';
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'VEGA schema tables: %', v_table_count;
    RAISE NOTICE 'VEGA functions: %', v_function_count;
    RAISE NOTICE 'Active rate limits: %', v_limit_count;
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'ADR-012 Economic Safety: ACTIVE';
    RAISE NOTICE '  - Per-summary ceiling: $0.050';
    RAISE NOTICE '  - Daily budget: $500.00';
    RAISE NOTICE '  - Daily call limit: 100';
    RAISE NOTICE '====================================================';
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION 021 COMPLETE
-- ============================================================================
-- VEGA Economic Safety (ADR-012):
-- - 5 tables in vega schema
-- - 3 cost tracking functions
-- - 3 monitoring views
-- - Rate limits seeded
-- - Budget allocations initialized
-- - Database: 127.0.0.1:54322
-- ============================================================================
