-- ============================================================================
-- Migration 105: AOL Telemetry Activation
-- CEO Directive 2026-FHQ-AOL-PATCH-01
-- ============================================================================
--
-- Authority: ADR-001, ADR-006, ADR-009, ADR-012, ADR-013, ADR-018, ADR-019
-- Classification: CONSTITUTIONAL - Telemetry Infrastructure
--
-- This migration activates the telemetry engine for the Agent Observability Layer.
-- It creates missing tables, views, and functions required for LIVE metrics.
-- ============================================================================

-- ============================================================================
-- Section 1: Agent Task Log (if not exists)
-- Unified task tracking per agent
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.agent_task_log (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    task_type TEXT NOT NULL, -- 'LLM_CALL', 'API_CALL', 'EXECUTION', 'RESEARCH', 'GOVERNANCE'
    status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'RUNNING', 'SUCCESS', 'FAILED', 'RETRY'

    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    latency_ms INTEGER,

    -- Cost tracking
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,

    -- Provider info
    provider TEXT,
    model TEXT,
    tier INTEGER,

    -- Governance
    signature_hash TEXT,
    quad_hash TEXT,
    fallback_used BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,

    -- Result
    result_summary TEXT,
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_task_log_agent_id ON fhq_governance.agent_task_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_created_at ON fhq_governance.agent_task_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_task_log_status ON fhq_governance.agent_task_log(status);

-- ============================================================================
-- Section 2: Telemetry Cost Ledger
-- Aggregated cost tracking per agent per day
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.telemetry_cost_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    ledger_date DATE NOT NULL DEFAULT CURRENT_DATE,

    -- LLM costs
    llm_requests INTEGER DEFAULT 0,
    llm_tokens_in BIGINT DEFAULT 0,
    llm_tokens_out BIGINT DEFAULT 0,
    llm_cost_usd NUMERIC(10, 4) DEFAULT 0,

    -- API costs
    api_requests INTEGER DEFAULT 0,
    api_cost_usd NUMERIC(10, 4) DEFAULT 0,

    -- Totals
    total_cost_usd NUMERIC(10, 4) DEFAULT 0,
    total_requests INTEGER DEFAULT 0,

    -- Performance
    avg_latency_ms INTEGER DEFAULT 0,
    p95_latency_ms INTEGER DEFAULT 0,

    -- Stats
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    fallback_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(agent_id, ledger_date)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_cost_ledger_agent ON fhq_governance.telemetry_cost_ledger(agent_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_cost_ledger_date ON fhq_governance.telemetry_cost_ledger(ledger_date DESC);

-- ============================================================================
-- Section 3: Cognitive Metrics Table (IoS-013 Binding)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_cognition.cognitive_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    cycle_id UUID, -- Links to reasoning cycle

    -- IoS-013 Entropy Metrics
    reasoning_entropy NUMERIC(8, 6), -- 0-1 scale
    chain_length INTEGER DEFAULT 0,
    branching_factor NUMERIC(6, 3) DEFAULT 1.0,
    collapse_rate NUMERIC(8, 6) DEFAULT 0, -- Rate of reasoning path collapse

    -- Truth Vector
    truth_vector_drift NUMERIC(8, 6) DEFAULT 0, -- Deviation from canonical truth
    confidence_spread NUMERIC(8, 6) DEFAULT 0, -- Variance in confidence scores

    -- Decision Metrics
    decision_drift_score NUMERIC(8, 6) DEFAULT 0, -- DDS
    thought_coherence NUMERIC(8, 6) DEFAULT 1.0,

    -- Context
    context_window_used INTEGER DEFAULT 0,
    context_utilization NUMERIC(5, 2) DEFAULT 0, -- Percentage

    -- Timestamps
    measured_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cognitive_metrics_agent ON fhq_cognition.cognitive_metrics(agent_id);
CREATE INDEX IF NOT EXISTS idx_cognitive_metrics_measured ON fhq_cognition.cognitive_metrics(measured_at DESC);

-- ============================================================================
-- Section 4: ASRP State Log (ADR-018 Compliance)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.asrp_state_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    task_id UUID,

    -- State Hashes
    pre_state_hash TEXT NOT NULL,
    post_state_hash TEXT,
    expected_state_hash TEXT,

    -- Verification
    signature_hash TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,
    state_mismatch BOOLEAN DEFAULT FALSE,
    mismatch_severity TEXT, -- 'MINOR', 'MAJOR', 'CRITICAL'

    -- Action taken
    enforcement_action TEXT, -- 'NONE', 'LOGGED', 'BLOCKED', 'ESCALATED'

    -- Context
    operation_type TEXT,
    operation_context JSONB,

    -- Timestamps
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_asrp_state_log_agent ON fhq_governance.asrp_state_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_asrp_state_log_mismatch ON fhq_governance.asrp_state_log(state_mismatch) WHERE state_mismatch = true;

-- ============================================================================
-- Section 5: Agent Last Activity View (Unified)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.agent_last_activity_v CASCADE;

CREATE VIEW fhq_governance.agent_last_activity_v AS
WITH activity_sources AS (
    -- From heartbeats
    SELECT agent_id::text, last_heartbeat_at as activity_time, 'HEARTBEAT' as source
    FROM fhq_governance.agent_heartbeats
    WHERE last_heartbeat_at IS NOT NULL

    UNION ALL

    -- From task log
    SELECT agent_id, COALESCE(completed_at, started_at) as activity_time, 'TASK' as source
    FROM fhq_governance.agent_task_log
    WHERE started_at IS NOT NULL

    UNION ALL

    -- From research log
    SELECT agent_id::text, created_at as activity_time, 'RESEARCH' as source
    FROM fhq_governance.research_log
    WHERE created_at IS NOT NULL

    UNION ALL

    -- From API usage events
    SELECT agent_id, timestamp as activity_time, 'API' as source
    FROM fhq_governance.api_usage_events
    WHERE timestamp IS NOT NULL

    UNION ALL

    -- From LLM routing log
    SELECT agent_id, request_timestamp as activity_time, 'LLM' as source
    FROM fhq_governance.llm_routing_log
    WHERE request_timestamp IS NOT NULL

    UNION ALL

    -- From cognitive metrics
    SELECT agent_id, measured_at as activity_time, 'COGNITION' as source
    FROM fhq_cognition.cognitive_metrics
    WHERE measured_at IS NOT NULL

    UNION ALL

    -- From causal entropy audit
    SELECT executed_by as agent_id, executed_at as activity_time, 'ENTROPY' as source
    FROM fhq_governance.causal_entropy_audit
    WHERE executed_at IS NOT NULL
)
SELECT
    agent_id,
    MAX(activity_time) as last_activity,
    (array_agg(source ORDER BY activity_time DESC))[1] as last_activity_source
FROM activity_sources
WHERE agent_id IS NOT NULL
GROUP BY agent_id;

-- ============================================================================
-- Section 6: Agent Task Stats View (for ARS calculation)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.agent_task_stats_v CASCADE;

CREATE VIEW fhq_governance.agent_task_stats_v AS
SELECT
    agent_id,
    COUNT(*) as total_tasks,
    COUNT(*) FILTER (WHERE status = 'SUCCESS') as success_count,
    COUNT(*) FILTER (WHERE status = 'FAILED') as failure_count,
    COUNT(*) FILTER (WHERE retry_count > 0) as retry_count,
    COUNT(*) FILTER (WHERE fallback_used = true) as fallback_count,
    ROUND(AVG(latency_ms)) as avg_latency_ms,
    SUM(cost_usd) as total_cost_usd,
    MAX(completed_at) as last_task_completed
FROM fhq_governance.agent_task_log
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY agent_id;

-- ============================================================================
-- Section 7: Agent Cost Stats View (for RBR calculation)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.agent_cost_stats_v CASCADE;

CREATE VIEW fhq_governance.agent_cost_stats_v AS
WITH daily_costs AS (
    SELECT
        agent_id,
        ledger_date,
        total_cost_usd,
        total_requests,
        llm_requests,
        api_requests
    FROM fhq_governance.telemetry_cost_ledger
    WHERE ledger_date >= CURRENT_DATE - INTERVAL '7 days'
),
api_costs AS (
    SELECT
        agent_id,
        SUM(CASE WHEN timestamp >= NOW() - INTERVAL '24 hours' THEN 1 ELSE 0 END) as api_requests_24h,
        SUM(CASE WHEN timestamp >= NOW() - INTERVAL '24 hours' THEN cost_usd ELSE 0 END) as api_cost_24h,
        COUNT(*) as api_requests_7d,
        SUM(cost_usd) as api_cost_7d
    FROM fhq_governance.api_usage_events
    WHERE timestamp >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
)
SELECT
    ac.agent_id,
    COALESCE(ac.api_requests_24h, 0) as api_requests_24h,
    COALESCE(ac.api_cost_24h, 0) as api_cost_24h,
    COALESCE(ac.api_requests_7d, 0) as api_requests_7d,
    COALESCE(ac.api_cost_7d, 0) as api_cost_7d,
    COALESCE(SUM(dc.total_cost_usd), 0) as total_cost_7d,
    COALESCE(SUM(dc.llm_requests), 0) as llm_requests_7d
FROM fhq_governance.agent_contracts agents
LEFT JOIN api_costs ac ON agents.agent_id = ac.agent_id
LEFT JOIN daily_costs dc ON agents.agent_id = dc.agent_id
WHERE agents.contract_status = 'ACTIVE'
GROUP BY ac.agent_id, ac.api_requests_24h, ac.api_cost_24h, ac.api_requests_7d, ac.api_cost_7d;

-- ============================================================================
-- Section 8: Agent GII Stats View (Governance Integrity Index)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.agent_gii_stats_v CASCADE;

CREATE VIEW fhq_governance.agent_gii_stats_v AS
WITH asrp_stats AS (
    SELECT
        agent_id,
        COUNT(*) FILTER (WHERE resolution_status != 'RESOLVED') as unresolved_violations,
        COUNT(*) FILTER (WHERE violation_class = 'CLASS_A') as class_a_violations,
        COUNT(*) FILTER (WHERE violation_class = 'CLASS_B') as class_b_violations
    FROM fhq_governance.asrp_violations
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
),
entropy_stats AS (
    SELECT
        executed_by as agent_id,
        COUNT(*) FILTER (WHERE propagation_blocked = true) as blocked_ops,
        COUNT(*) FILTER (WHERE gate = 'G4' AND propagation_blocked = true) as g4_blocked
    FROM fhq_governance.causal_entropy_audit
    WHERE executed_at >= NOW() - INTERVAL '7 days'
    GROUP BY executed_by
),
drift_stats AS (
    SELECT
        agent_id,
        AVG(truth_vector_drift) as avg_drift,
        MAX(decision_drift_score) as max_dds
    FROM fhq_cognition.cognitive_metrics
    WHERE measured_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
)
SELECT
    ac.agent_id,
    COALESCE(asrp.unresolved_violations, 0) as asrp_violations,
    COALESCE(asrp.class_a_violations, 0) as class_a_violations,
    COALESCE(es.blocked_ops, 0) as blocked_operations,
    COALESCE(es.g4_blocked, 0) as g4_blocked_ops,
    COALESCE(ds.avg_drift, 0) as truth_vector_drift,
    COALESCE(ds.max_dds, 0) as decision_drift_score,
    -- Calculate GII state
    CASE
        WHEN COALESCE(asrp.class_a_violations, 0) > 0 THEN 'RED'
        WHEN COALESCE(es.blocked_ops, 0) > 5 THEN 'RED'
        WHEN COALESCE(asrp.unresolved_violations, 0) > 3 THEN 'RED'
        WHEN COALESCE(es.blocked_ops, 0) > 0 THEN 'YELLOW'
        WHEN COALESCE(asrp.unresolved_violations, 0) > 0 THEN 'YELLOW'
        WHEN COALESCE(ds.avg_drift, 0) > 0.3 THEN 'YELLOW'
        ELSE 'GREEN'
    END as gii_state,
    -- Calculate GII score (0-100, higher is better)
    GREATEST(0, 100 -
        (COALESCE(asrp.class_a_violations, 0) * 25) -
        (COALESCE(asrp.unresolved_violations, 0) * 10) -
        (COALESCE(es.blocked_ops, 0) * 5) -
        (COALESCE(ds.avg_drift, 0) * 50)
    )::integer as gii_score
FROM fhq_governance.agent_contracts ac
LEFT JOIN asrp_stats asrp ON ac.agent_id = asrp.agent_id
LEFT JOIN entropy_stats es ON ac.agent_id = es.agent_id
LEFT JOIN drift_stats ds ON ac.agent_id = ds.agent_id
WHERE ac.contract_status = 'ACTIVE';

-- ============================================================================
-- Section 9: Agent CSI Stats View (Cognitive Stability Index)
-- ============================================================================

DROP VIEW IF EXISTS fhq_governance.agent_csi_stats_v CASCADE;

CREATE VIEW fhq_governance.agent_csi_stats_v AS
SELECT
    agent_id,
    COUNT(*) as measurement_count,
    AVG(reasoning_entropy) as avg_entropy,
    AVG(chain_length) as avg_chain_length,
    AVG(branching_factor) as avg_branching,
    AVG(collapse_rate) as avg_collapse_rate,
    AVG(thought_coherence) as avg_coherence,
    AVG(confidence_spread) as avg_confidence_spread,
    -- Calculate CSI (0-100, higher is more stable)
    GREATEST(0, LEAST(100,
        80 +
        (20 * COALESCE(AVG(thought_coherence), 0.5)) -
        (30 * COALESCE(AVG(reasoning_entropy), 0.5)) -
        (10 * COALESCE(AVG(collapse_rate), 0)) -
        (10 * COALESCE(AVG(confidence_spread), 0.3))
    ))::integer as csi_score
FROM fhq_cognition.cognitive_metrics
WHERE measured_at >= NOW() - INTERVAL '7 days'
GROUP BY agent_id;

-- ============================================================================
-- Section 10: Comprehensive Agent Metrics View (AOL Master View)
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS fhq_governance.mv_aol_agent_metrics CASCADE;

CREATE MATERIALIZED VIEW fhq_governance.mv_aol_agent_metrics AS
SELECT
    ac.agent_id,
    ac.contract_status,
    ac.mandate_scope,

    -- Last Activity
    la.last_activity,
    la.last_activity_source,

    -- ARS (Agent Reliability Score)
    COALESCE(ts.success_count, 0) as success_count_7d,
    COALESCE(ts.failure_count, 0) as failure_count_7d,
    COALESCE(ts.retry_count, 0) as retry_count_7d,
    COALESCE(ts.fallback_count, 0) as fallback_count_7d,
    CASE
        WHEN COALESCE(ts.success_count, 0) + COALESCE(ts.failure_count, 0) > 0
        THEN ROUND((COALESCE(ts.success_count, 0)::numeric /
              (COALESCE(ts.success_count, 0) + COALESCE(ts.failure_count, 0))) * 100)::integer
        ELSE NULL -- No data, show as null not 100
    END as ars_score,

    -- CSI (Cognitive Stability Index)
    csi.csi_score,
    csi.avg_entropy as reasoning_entropy,
    csi.avg_chain_length,
    csi.avg_coherence as thought_coherence,

    -- RBR (Resource Burn Rate)
    COALESCE(cs.api_requests_24h, 0) as api_requests_24h,
    COALESCE(cs.api_requests_7d, 0) as api_requests_7d,
    COALESCE(cs.api_cost_7d, 0) as api_cost_7d,
    COALESCE(cs.llm_requests_7d, 0) as llm_requests_7d,
    COALESCE(cs.total_cost_7d, 0) as total_cost_7d,

    -- GII (Governance Integrity Index)
    gii.gii_state,
    gii.gii_score,
    gii.asrp_violations,
    gii.blocked_operations,
    gii.truth_vector_drift,

    -- DDS (Decision Drift Score)
    gii.decision_drift_score as dds_score,

    -- Research Activity
    COALESCE(rs.total_events, 0) as research_events_7d,

    -- Metadata
    NOW() as refreshed_at

FROM fhq_governance.agent_contracts ac
LEFT JOIN fhq_governance.agent_last_activity_v la ON ac.agent_id = la.agent_id
LEFT JOIN fhq_governance.agent_task_stats_v ts ON ac.agent_id = ts.agent_id
LEFT JOIN fhq_governance.agent_csi_stats_v csi ON ac.agent_id = csi.agent_id
LEFT JOIN fhq_governance.agent_cost_stats_v cs ON ac.agent_id = cs.agent_id
LEFT JOIN fhq_governance.agent_gii_stats_v gii ON ac.agent_id = gii.agent_id
LEFT JOIN (
    SELECT agent_id::text, COUNT(*) as total_events
    FROM fhq_governance.research_log
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY agent_id
) rs ON ac.agent_id = rs.agent_id
WHERE ac.contract_status = 'ACTIVE';

CREATE UNIQUE INDEX idx_mv_aol_agent_metrics_id ON fhq_governance.mv_aol_agent_metrics(agent_id);

-- ============================================================================
-- Section 11: Refresh Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.refresh_aol_telemetry()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY fhq_governance.mv_aol_agent_metrics;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Section 12: Initial Data Population
-- ============================================================================

-- Populate task log from existing research_log events
INSERT INTO fhq_governance.agent_task_log (agent_id, task_name, task_type, status, started_at, completed_at, signature_hash, quad_hash)
SELECT
    agent_id::text,
    COALESCE(event_type, 'RESEARCH')::text,
    'RESEARCH',
    CASE
        WHEN status IN ('SUCCESS', 'COMPLETED') THEN 'SUCCESS'
        WHEN status IN ('FAILED', 'ERROR') THEN 'FAILED'
        ELSE 'SUCCESS'
    END,
    created_at,
    created_at,
    NULL,
    quad_hash::text
FROM fhq_governance.research_log
WHERE created_at >= NOW() - INTERVAL '30 days'
ON CONFLICT DO NOTHING;

-- Populate task log from API usage events
INSERT INTO fhq_governance.agent_task_log (agent_id, task_name, task_type, status, started_at, completed_at, latency_ms, cost_usd, provider)
SELECT
    agent_id,
    COALESCE(endpoint, 'API_CALL'),
    'API_CALL',
    CASE WHEN response_status >= 200 AND response_status < 300 THEN 'SUCCESS' ELSE 'FAILED' END,
    timestamp,
    timestamp,
    latency_ms,
    cost_usd,
    provider_name
FROM fhq_governance.api_usage_events
WHERE timestamp >= NOW() - INTERVAL '30 days'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Section 13: Refresh Views
-- ============================================================================

SELECT fhq_governance.refresh_aol_telemetry();

-- ============================================================================
-- Section 14: Governance Audit Entry
-- ============================================================================

INSERT INTO fhq_governance.causal_entropy_audit (
    operation,
    gate,
    entity_type,
    entity_id,
    executed_by,
    executed_at
) VALUES (
    'MIGRATION',
    'G1',
    'SCHEMA',
    '105_aol_telemetry_activation',
    'STIG',
    NOW()
);

-- ============================================================================
-- Migration Complete: AOL Telemetry Activation
-- ============================================================================
