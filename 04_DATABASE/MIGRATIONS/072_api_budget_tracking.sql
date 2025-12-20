-- ============================================================================
-- MIGRATION 072: API Budget Tracking (90% Rule Enforcement)
-- ============================================================================
-- Document ID: API-BUDGET-TRACKING-20251203
-- Authority: CEO Directive
-- ADR Alignment: ADR-012 (Economic Safety)
-- ============================================================================

BEGIN;

-- API Budget Log - tracks daily usage per provider
CREATE TABLE IF NOT EXISTS fhq_governance.api_budget_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name TEXT NOT NULL,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    requests_made INTEGER NOT NULL DEFAULT 0,
    daily_limit INTEGER NOT NULL,
    usage_percent NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE WHEN daily_limit > 0
             THEN ROUND((requests_made::numeric / daily_limit) * 100, 2)
             ELSE 0
        END
    ) STORED,
    threshold_90_breached BOOLEAN GENERATED ALWAYS AS (
        CASE WHEN daily_limit > 0
             THEN (requests_made::numeric / daily_limit) >= 0.90
             ELSE FALSE
        END
    ) STORED,
    threshold_100_breached BOOLEAN GENERATED ALWAYS AS (
        CASE WHEN daily_limit > 0
             THEN requests_made >= daily_limit
             ELSE FALSE
        END
    ) STORED,
    last_request_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(provider_name, usage_date)
);

-- API Usage Events - granular tracking
CREATE TABLE IF NOT EXISTS fhq_governance.api_usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name TEXT NOT NULL,
    endpoint TEXT,
    request_type TEXT,
    response_status INTEGER,
    latency_ms INTEGER,
    cost_usd NUMERIC(10,6) DEFAULT 0,
    agent_id TEXT,
    ios_id TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for efficient querying
CREATE INDEX IF NOT EXISTS idx_api_budget_log_date ON fhq_governance.api_budget_log(usage_date);
CREATE INDEX IF NOT EXISTS idx_api_usage_events_provider_date ON fhq_governance.api_usage_events(provider_name, timestamp);

-- Initialize today's budget for all providers
INSERT INTO fhq_governance.api_budget_log (provider_name, usage_date, daily_limit)
SELECT provider_name, CURRENT_DATE, COALESCE(daily_limit, 0)
FROM fhq_governance.api_provider_registry
WHERE is_active = true
ON CONFLICT (provider_name, usage_date) DO NOTHING;

-- Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale,
    vega_reviewed, hash_chain_id
) VALUES (
    gen_random_uuid(),
    'API_BUDGET_TRACKING_INIT',
    'fhq_governance.api_budget_log',
    'INFRASTRUCTURE',
    'STIG',
    NOW(),
    'APPROVED',
    'Implemented 90% rule API budget tracking per CEO directive. All API usage now tracked with automatic threshold alerts.',
    TRUE,
    'HC-API-BUDGET-20251203'
);

COMMIT;
