-- Migration: 196_observability_2_immediate.sql
-- ADR-022: The Autonomous Database Horizon Implementation Charter
-- Purpose: Pillar 1-3 instrumentation for SQL refinement observability
-- Execution Order: FIRST (before 191b and 191)
-- Schema: fhq_monitoring (extends existing observability infrastructure)
--
-- CEO DIRECTIVE: Observability must be IMMEDIATE, not deferred to Q4 2026.
-- Rationale: Cannot measure refinement loop compliance without instrumentation.
--            ADR-016 HIGH_LATENCY breaker triggers at >2000ms - we must KNOW when approaching.
--
-- Dependencies: None (this is the foundation)
-- Depends On: fhq_monitoring schema (exists)
-- Required By: 191b_aiqf_benchmark_registry.sql, 191_reasoning_driven_sql_refinement.sql

BEGIN;

-- ============================================================================
-- SECTION 1: Agent Semantic Health Monitoring
-- Purpose: Track SQL refinement quality per agent, detect anomalies
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.agent_semantic_health (
    health_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(20) NOT NULL,

    -- Health check classification
    health_check_type VARCHAR(50) NOT NULL CHECK (
        health_check_type IN (
            'sql_accuracy',           -- Query correctness rate
            'cot_quality',            -- Reasoning artifact quality
            'latency_compliance',     -- Within 2000ms budget
            'token_efficiency',       -- Tokens vs. query complexity
            'error_taxonomy',         -- Error pattern distribution
            'policy_compliance',      -- ABAC/governance adherence
            'circuit_breaker_state'   -- Breaker health
        )
    ),

    -- Metrics
    health_score FLOAT NOT NULL CHECK (health_score >= 0.0 AND health_score <= 1.0),
    sample_size INTEGER DEFAULT 1,
    measurement_window_minutes INTEGER DEFAULT 10,

    -- Anomaly detection
    anomaly_detected BOOLEAN DEFAULT FALSE,
    anomaly_severity VARCHAR(20) CHECK (anomaly_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    anomaly_details JSONB,
    baseline_score FLOAT,  -- Expected score for comparison
    deviation_from_baseline FLOAT,  -- How far from expected

    -- Auto-correction tracking
    auto_correction_triggered BOOLEAN DEFAULT FALSE,
    correction_action TEXT,
    correction_success BOOLEAN,

    -- Audit trail
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure we can query efficiently by agent and time
    CONSTRAINT agent_health_time_unique UNIQUE (agent_id, health_check_type, created_at)
);

-- Indexes for efficient querying
CREATE INDEX idx_agent_health_agent_time
    ON fhq_monitoring.agent_semantic_health(agent_id, created_at DESC);
CREATE INDEX idx_agent_health_anomaly
    ON fhq_monitoring.agent_semantic_health(anomaly_detected, anomaly_severity)
    WHERE anomaly_detected = TRUE;
CREATE INDEX idx_agent_health_type_score
    ON fhq_monitoring.agent_semantic_health(health_check_type, health_score);

-- ============================================================================
-- SECTION 2: SQL Refinement Metrics (Observability for Migration 191)
-- Purpose: Real-time metrics for refinement loop, feeds into AIQF calculation
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.sql_refinement_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Time bucketing for aggregation
    bucket_start TIMESTAMPTZ NOT NULL,
    bucket_end TIMESTAMPTZ NOT NULL,
    bucket_size_minutes INTEGER NOT NULL DEFAULT 10,

    -- Agent scope
    agent_id VARCHAR(20) NOT NULL,
    schema_domain VARCHAR(50),  -- 'fhq_meta', 'fhq_research', etc.

    -- Success metrics (feed into AIQF)
    total_queries INTEGER DEFAULT 0,
    successful_first_attempt INTEGER DEFAULT 0,
    successful_within_3_attempts INTEGER DEFAULT 0,
    semantic_correct INTEGER DEFAULT 0,
    escalated_to_human INTEGER DEFAULT 0,

    -- Calculated rates
    first_attempt_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN total_queries > 0
             THEN successful_first_attempt::FLOAT / total_queries
             ELSE 0.0 END
    ) STORED,
    within_3_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN total_queries > 0
             THEN successful_within_3_attempts::FLOAT / total_queries
             ELSE 0.0 END
    ) STORED,

    -- Latency metrics (ADR-016 compliance)
    avg_latency_ms FLOAT,
    p50_latency_ms FLOAT,
    p95_latency_ms FLOAT,
    p99_latency_ms FLOAT,
    max_latency_ms INTEGER,
    latency_budget_violations INTEGER DEFAULT 0,  -- Count of >2000ms

    -- Token metrics (ADR-012 compliance)
    total_tokens_consumed INTEGER DEFAULT 0,
    avg_tokens_per_query FLOAT,
    token_budget_violations INTEGER DEFAULT 0,  -- Count of >4000 tokens

    -- Cost metrics
    total_cost_usd FLOAT DEFAULT 0.0,
    avg_cost_per_query FLOAT,
    cost_budget_violations INTEGER DEFAULT 0,  -- Count of >$0.02/query

    -- Error taxonomy
    error_distribution JSONB,  -- {"syntax": 5, "semantic": 3, "timeout": 1, ...}

    -- Circuit breaker state at bucket end
    circuit_breaker_state VARCHAR(20),
    circuit_breaker_transitions INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT bucket_agent_unique UNIQUE (bucket_start, agent_id, schema_domain)
);

-- Indexes for dashboard queries
CREATE INDEX idx_refinement_metrics_time
    ON fhq_monitoring.sql_refinement_metrics(bucket_start DESC);
CREATE INDEX idx_refinement_metrics_agent
    ON fhq_monitoring.sql_refinement_metrics(agent_id, bucket_start DESC);
CREATE INDEX idx_refinement_metrics_violations
    ON fhq_monitoring.sql_refinement_metrics(latency_budget_violations, token_budget_violations)
    WHERE latency_budget_violations > 0 OR token_budget_violations > 0;

-- ============================================================================
-- SECTION 3: Self-Healing Action Log
-- Purpose: Track automated corrective actions, audit trail for governance
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.self_healing_actions (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Trigger classification
    trigger_event_type VARCHAR(50) NOT NULL CHECK (
        trigger_event_type IN (
            'latency_threshold',      -- Approaching 2000ms
            'error_rate_spike',       -- Sudden increase in failures
            'token_budget_risk',      -- Approaching 4000 tokens
            'circuit_breaker_trip',   -- Breaker state change
            'anomaly_detected',       -- From agent_semantic_health
            'aiqf_drift',             -- AIQF score dropping
            'defcon_escalation',      -- DEFCON level change
            'guideline_failure'       -- Correction guideline not working
        )
    ),
    trigger_details JSONB NOT NULL,
    trigger_severity VARCHAR(20) CHECK (trigger_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),

    -- Action taken
    healing_action_type VARCHAR(50) NOT NULL CHECK (
        healing_action_type IN (
            'throttle_requests',      -- Slow down query rate
            'switch_model_tier',      -- Use cheaper/faster model
            'activate_cache',         -- Use cached results
            'reduce_complexity',      -- Simplify query approach
            'escalate_to_human',      -- Give up, ask for help
            'update_guideline',       -- Modify correction guideline
            'reset_circuit_breaker',  -- Manual breaker reset
            'log_only'                -- Just observe, no action
        )
    ),
    healing_action_details TEXT NOT NULL,

    -- State before/after for audit
    before_state JSONB,
    after_state JSONB,

    -- Outcome
    action_success BOOLEAN,
    failure_reason TEXT,

    -- Attribution
    agent_id VARCHAR(20),
    triggered_by VARCHAR(50),  -- 'system', 'agent_id', 'human'

    -- Governance linkage
    governance_action_id UUID,  -- FK to fhq_governance.governance_actions_log
    defcon_state_at_action VARCHAR(10),  -- GREEN, YELLOW, ORANGE, RED, BLACK

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_healing_trigger_type
    ON fhq_monitoring.self_healing_actions(trigger_event_type, created_at DESC);
CREATE INDEX idx_healing_success
    ON fhq_monitoring.self_healing_actions(action_success, created_at DESC);
CREATE INDEX idx_healing_severity
    ON fhq_monitoring.self_healing_actions(trigger_severity)
    WHERE trigger_severity IN ('HIGH', 'CRITICAL');

-- ============================================================================
-- SECTION 4: Query-Level Lineage (Extends existing data_lineage for SQL tracking)
-- Purpose: Track data flow through SQL refinement pipeline
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.query_lineage (
    lineage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Query identification
    query_hash VARCHAR(64) NOT NULL,  -- SHA-256 of original query
    refinement_id UUID,  -- FK to fhq_governance.sql_refinement_log (after 191)

    -- Source tracking
    source_table VARCHAR(200) NOT NULL,
    source_columns JSONB,  -- ["col1", "col2", ...]

    -- Target tracking (if writing)
    target_table VARCHAR(200),
    target_columns JSONB,

    -- Transformation metadata
    transformation_type VARCHAR(50) CHECK (
        transformation_type IN (
            'SELECT', 'INSERT', 'UPDATE', 'DELETE',
            'AGGREGATE', 'JOIN', 'WINDOW', 'CTE'
        )
    ),
    transformation_details JSONB,

    -- Execution context
    agent_id VARCHAR(20) NOT NULL,
    execution_timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Row counts for validation
    rows_read INTEGER,
    rows_affected INTEGER,

    -- Hash for verification
    lineage_hash VARCHAR(64) NOT NULL,  -- SHA-256 of full lineage record

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_query_lineage_hash
    ON fhq_monitoring.query_lineage(query_hash);
CREATE INDEX idx_query_lineage_source
    ON fhq_monitoring.query_lineage(source_table, created_at DESC);
CREATE INDEX idx_query_lineage_agent
    ON fhq_monitoring.query_lineage(agent_id, created_at DESC);

-- ============================================================================
-- SECTION 5: Observability Dashboard Summary View
-- NOTE: vw_aiqf_realtime MOVED to 191b per CEO scope discipline
-- 196 = observability only, 191b = AIQF only
-- ============================================================================

-- ============================================================================
-- SECTION 5: Observability Dashboard Summary View
-- Purpose: Single-query dashboard data for Cognitive Performance Dashboard
-- ============================================================================

CREATE OR REPLACE VIEW fhq_monitoring.vw_observability_dashboard AS
WITH recent_health AS (
    SELECT
        agent_id,
        health_check_type,
        health_score,
        anomaly_detected,
        ROW_NUMBER() OVER (PARTITION BY agent_id, health_check_type ORDER BY created_at DESC) as rn
    FROM fhq_monitoring.agent_semantic_health
    WHERE created_at > NOW() - INTERVAL '1 hour'
),
recent_metrics AS (
    SELECT
        agent_id,
        SUM(total_queries) as queries_1h,
        AVG(first_attempt_rate) as avg_first_attempt_rate,
        AVG(avg_latency_ms) as avg_latency,
        MAX(max_latency_ms) as max_latency,
        SUM(total_cost_usd) as cost_1h,
        SUM(latency_budget_violations) as latency_violations_1h
    FROM fhq_monitoring.sql_refinement_metrics
    WHERE bucket_start > NOW() - INTERVAL '1 hour'
    GROUP BY agent_id
),
recent_healing AS (
    SELECT
        agent_id,
        COUNT(*) as healing_actions_1h,
        SUM(CASE WHEN action_success THEN 1 ELSE 0 END) as successful_healings
    FROM fhq_monitoring.self_healing_actions
    WHERE created_at > NOW() - INTERVAL '1 hour'
    GROUP BY agent_id
)
SELECT
    COALESCE(m.agent_id, h.agent_id) as agent_id,
    m.queries_1h,
    m.avg_first_attempt_rate,
    m.avg_latency,
    m.max_latency,
    m.cost_1h,
    m.latency_violations_1h,
    hh.healing_actions_1h,
    hh.successful_healings,
    -- Aggregate health scores
    (SELECT AVG(health_score) FROM recent_health rh
     WHERE rh.agent_id = COALESCE(m.agent_id, h.agent_id) AND rh.rn = 1) as avg_health_score,
    (SELECT bool_or(anomaly_detected) FROM recent_health rh
     WHERE rh.agent_id = COALESCE(m.agent_id, h.agent_id) AND rh.rn = 1) as has_anomaly
FROM recent_metrics m
FULL OUTER JOIN (SELECT DISTINCT agent_id FROM recent_health WHERE rn = 1) h ON m.agent_id = h.agent_id
LEFT JOIN recent_healing hh ON COALESCE(m.agent_id, h.agent_id) = hh.agent_id;

-- ============================================================================
-- SECTION 7: Governance Integration - Log this migration
-- ============================================================================

-- Record migration in governance log (using actual governance_actions_log schema)
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    'MIGRATION_EXECUTE',
    '196_observability_2_immediate.sql',
    'DATABASE_MIGRATION',
    'STIG',
    'EXECUTE',
    'CEO-AUTH-2026-ADR022-M196: Pillar 1-3 instrumentation for SQL refinement observability',
    jsonb_build_object(
        'migration_id', '196_observability_2_immediate',
        'adr_reference', 'ADR-022',
        'purpose', 'Pillar 1-3 instrumentation for SQL refinement observability',
        'tables_created', ARRAY[
            'fhq_monitoring.agent_semantic_health',
            'fhq_monitoring.sql_refinement_metrics',
            'fhq_monitoring.self_healing_actions',
            'fhq_monitoring.query_lineage'
        ],
        'views_created', ARRAY[
            'fhq_monitoring.vw_observability_dashboard'
        ],
        'scope_note', 'vw_aiqf_realtime moved to 191b per CEO scope discipline',
        'execution_order', 1,
        'next_migration', '191b_aiqf_benchmark_registry.sql',
        'file_hash', 'a8c0bb454ccdda06c6fc0f956f42cf3b80b537f28d187f92fdebbe2fa61f6a87',
        'git_commit', '3f98f4ae55f303aaaa071dae8ca6212c0640f867'
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- Run these queries to verify successful installation
-- ============================================================================

-- Verification Query 1: Check all tables exist
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'fhq_monitoring'
-- AND table_name IN ('agent_semantic_health', 'sql_refinement_metrics', 'self_healing_actions', 'query_lineage');

-- Verification Query 2: Check views exist
-- SELECT table_name FROM information_schema.views
-- WHERE table_schema = 'fhq_monitoring'
-- AND table_name = 'vw_observability_dashboard';
-- NOTE: vw_aiqf_realtime is in 191b, not here

-- Verification Query 3: Check governance log entry
-- SELECT * FROM fhq_governance.governance_actions_log
-- WHERE action_details->>'migration_id' = '196_observability_2_immediate';
