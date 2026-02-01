-- Migration: 191_reasoning_driven_sql_refinement.sql
-- ADR-022: The Autonomous Database Horizon Implementation Charter
-- Purpose: SQL refinement log, correction guidelines, circuit breaker integration
-- Execution Order: THIRD (after 196 and 191b)
-- Schema: fhq_governance (per ADR-016 anchor requirement)
--
-- CEO PRE-IMPLEMENTATION REVIEW: 8 corrections applied 2026-01-03 (DB-grounded)
-- 1. Latency ceiling: 2000ms (matches ADR-016 HIGH_LATENCY breaker exactly)
-- 2. circuit_state default: CLOSED (traffic allowed)
-- 3. Schema: fhq_governance (not fhq_meta)
-- 4. FK constraints: All added
-- 5. Reasoning artifact only: No full CoT storage (forensic bundle exception)
-- 6. No new circuit breaker tables: Reuse existing fhq_governance.circuit_breakers
-- 7. Evidence bundle pattern: Follows vision_verification.summary_evidence_ledger
-- 8. AIQF integration: FK to benchmark_runs
--
-- Dependencies:
--   - 196_observability_2_immediate.sql (metrics tables)
--   - 191b_aiqf_benchmark_registry.sql (FK to aiqf_benchmark_runs)
--   - fhq_governance.circuit_breakers (existing table)
--   - fhq_governance.vega_attestations (existing table)
--   - fhq_governance.system_state (existing table - ADR-016 anchor)

BEGIN;

-- ============================================================================
-- SECTION 1: SQL Correction Guidelines
-- Purpose: MAGIC-inspired auto-generated correction templates
-- Must be created FIRST (referenced by sql_refinement_log FK)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.sql_correction_guidelines (
    guideline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Error pattern matching
    error_pattern VARCHAR(100) NOT NULL,
    error_taxonomy VARCHAR(50) CHECK (error_taxonomy IN (
        'SYNTAX',             -- SQL syntax errors
        'SEMANTIC',           -- Wrong table/column references
        'JOIN_PATH',          -- Incorrect FK traversal
        'AGGREGATION',        -- GROUP BY / aggregation issues
        'NULL_EXPLOSION',     -- Unexpected NULL handling
        'TYPE_MISMATCH',      -- Data type conflicts
        'PERMISSION',         -- Access denied
        'TIMEOUT',            -- Query too slow
        'RESULT_MISMATCH'     -- Output doesn't match expectation
    )),

    -- Correction template
    correction_template TEXT NOT NULL,
    correction_example JSONB,  -- Before/after SQL example

    -- Lifecycle controls (per CEO directive)
    guideline_version INTEGER DEFAULT 1,
    supersedes_guideline_id UUID REFERENCES fhq_governance.sql_correction_guidelines(guideline_id),

    -- Effectiveness tracking
    success_rate FLOAT DEFAULT 0.0 CHECK (success_rate >= 0.0 AND success_rate <= 1.0),
    success_rate_confidence_lower FLOAT,  -- 95% CI lower bound
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMPTZ,

    -- Validation linkage
    validated_on_benchmark_run_id UUID,  -- FK added after aiqf_benchmark_runs exists

    -- Authorship
    created_by VARCHAR(20) NOT NULL,
    approved_by VARCHAR(20),

    -- Governance controls
    is_active BOOLEAN DEFAULT TRUE,
    is_global_default BOOLEAN DEFAULT FALSE,  -- Requires VEGA signoff
    vega_signoff_attestation_id UUID,  -- FK to vega_attestations
    vega_signoff_date TIMESTAMPTZ,

    -- Deprecation
    sunset_at TIMESTAMPTZ,
    sunset_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add FK to vega_attestations
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'fhq_governance' AND table_name = 'vega_attestations') THEN
        ALTER TABLE fhq_governance.sql_correction_guidelines
            ADD CONSTRAINT fk_guideline_vega_signoff
            FOREIGN KEY (vega_signoff_attestation_id)
            REFERENCES fhq_governance.vega_attestations(attestation_id);
    END IF;
END $$;

-- Add FK to aiqf_benchmark_runs
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'fhq_governance' AND table_name = 'aiqf_benchmark_runs') THEN
        ALTER TABLE fhq_governance.sql_correction_guidelines
            ADD CONSTRAINT fk_guideline_benchmark_validation
            FOREIGN KEY (validated_on_benchmark_run_id)
            REFERENCES fhq_governance.aiqf_benchmark_runs(run_id);
    END IF;
END $$;

-- Indexes for guideline lookup
CREATE INDEX idx_guidelines_pattern
    ON fhq_governance.sql_correction_guidelines(error_pattern, success_rate DESC);
CREATE INDEX idx_guidelines_taxonomy
    ON fhq_governance.sql_correction_guidelines(error_taxonomy, is_active);
CREATE INDEX idx_guidelines_active_global
    ON fhq_governance.sql_correction_guidelines(is_active, is_global_default)
    WHERE is_active = TRUE;

-- ============================================================================
-- SECTION 2: Refinement Evidence Bundle
-- Purpose: Court-proof evidence for escalated/forensic queries
-- Pattern: Follows vision_verification.summary_evidence_ledger (CEO Directive 2025-12-20)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.refinement_evidence_bundle (
    bundle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Bundle classification
    bundle_type VARCHAR(30) NOT NULL CHECK (bundle_type IN (
        'ESCALATION',    -- Query escalated to human
        'FORENSIC',      -- Post-mortem analysis
        'G4_INCIDENT'    -- Governance incident requiring full CoT
    )),

    -- Preservation reason (required)
    preservation_reason TEXT NOT NULL,
    preserved_by VARCHAR(20) NOT NULL,

    -- Full Chain-of-Thought (ONLY for G4 incidents)
    -- Normal operations use structured artifact only
    raw_cot_preserved TEXT,

    -- Court-proof evidence fields (per vision_verification.summary_evidence_ledger pattern)
    raw_query TEXT NOT NULL,  -- The exact SQL that was attempted
    query_result_hash VARCHAR(64),  -- SHA-256 of results for verification
    query_result_snapshot JSONB,  -- Actual data at time of escalation

    -- Error context
    error_message TEXT,
    error_stack_trace TEXT,

    -- Linked refinement (set after refinement_log insert)
    refinement_id UUID,

    -- Governance linkage
    governance_action_id UUID,
    defcon_level_at_creation VARCHAR(10),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for bundle lookups
CREATE INDEX idx_evidence_bundle_type
    ON fhq_governance.refinement_evidence_bundle(bundle_type, created_at DESC);

-- ============================================================================
-- SECTION 3: SQL Refinement Log
-- Purpose: Main tracking table for SQL generation/refinement attempts
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.sql_refinement_log (
    refinement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Original request
    original_query TEXT NOT NULL,  -- Natural language or partial SQL
    query_intent VARCHAR(200),  -- Short description of what query should do

    -- Structured Reasoning Artifact (NOT full CoT - per CEO directive)
    -- Full CoT is ephemeral unless G4 incident forces retention
    reasoning_artifact JSONB NOT NULL CHECK (
        reasoning_artifact ? 'intent' AND
        reasoning_artifact ? 'schema_elements' AND
        reasoning_artifact ? 'verification_steps'
    ),
    -- Required artifact structure:
    -- {
    --   "intent": "what the query aims to answer",
    --   "schema_elements": {"tables": [], "columns": [], "joins": []},
    --   "join_plan": "FK path or explicit join keys",
    --   "filters": [],
    --   "aggregation_grain": null|"day"|"ticker"|etc,
    --   "verification_steps": ["step1", "step2", ...],
    --   "risk_flags": ["wide_join", "unknown_column", etc]
    -- }
    reasoning_hash VARCHAR(64) NOT NULL,  -- SHA-256 of artifact for verification
    artifact_version INTEGER DEFAULT 1,

    -- Generated output
    generated_sql TEXT NOT NULL,
    generated_sql_hash VARCHAR(64),  -- For deduplication

    -- Error handling
    error_message TEXT,
    error_type VARCHAR(50),
    error_taxonomy VARCHAR(50) CHECK (error_taxonomy IN (
        'SYNTAX', 'SEMANTIC', 'JOIN_PATH', 'AGGREGATION',
        'NULL_EXPLOSION', 'TYPE_MISMATCH', 'PERMISSION',
        'TIMEOUT', 'RESULT_MISMATCH', NULL
    )),

    -- MAGIC-inspired self-correction
    correction_guideline_id UUID REFERENCES fhq_governance.sql_correction_guidelines(guideline_id),
    refined_query TEXT,  -- Corrected SQL after applying guideline

    -- Hard-bound circuit breaker (ADR-012 + ADR-016)
    attempt_number INTEGER DEFAULT 1 CHECK (attempt_number >= 1 AND attempt_number <= 3),
    max_attempts INTEGER DEFAULT 3,

    -- Token budget (ADR-012)
    tokens_consumed INTEGER DEFAULT 0,
    tokens_budget INTEGER DEFAULT 4000,  -- Per-query ceiling
    tokens_exceeded BOOLEAN GENERATED ALWAYS AS (tokens_consumed > tokens_budget) STORED,

    -- Latency budget (ADR-016: HIGH_LATENCY breaker at 2000ms)
    latency_ms INTEGER,
    latency_budget_ms INTEGER DEFAULT 2000,  -- CORRECTED: matches ADR-016 exactly
    latency_exceeded BOOLEAN GENERATED ALWAYS AS (latency_ms > latency_budget_ms) STORED,

    -- Cost budget (ADR-012)
    cost_usd FLOAT DEFAULT 0.0,
    cost_budget_usd FLOAT DEFAULT 0.02,  -- $0.02 per query ceiling
    cost_exceeded BOOLEAN GENERATED ALWAYS AS (cost_usd > cost_budget_usd) STORED,

    -- Circuit breaker status
    -- CORRECTED: Default CLOSED (traffic allowed), OPEN means blocked
    circuit_state VARCHAR(20) DEFAULT 'CLOSED' CHECK (circuit_state IN ('CLOSED', 'OPEN', 'HALF_OPEN')),

    -- Human escalation
    escalated_to_human BOOLEAN DEFAULT FALSE,
    escalation_bundle_id UUID REFERENCES fhq_governance.refinement_evidence_bundle(bundle_id),
    escalation_reason TEXT,

    -- Outcome
    success BOOLEAN DEFAULT FALSE,
    execution_result_hash VARCHAR(64),  -- Hash of actual query results

    -- Semantic verification
    semantic_check_passed BOOLEAN,
    semantic_check_details JSONB,  -- FK path plausibility, rowcount bounds, null explosion risk

    -- Attribution
    agent_id VARCHAR(20) NOT NULL,
    model_used VARCHAR(100),
    prompt_template_version VARCHAR(20),

    -- AIQF linkage (for benchmark runs)
    benchmark_run_id UUID,  -- FK added below

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add FK to aiqf_benchmark_runs
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'fhq_governance' AND table_name = 'aiqf_benchmark_runs') THEN
        ALTER TABLE fhq_governance.sql_refinement_log
            ADD CONSTRAINT fk_refinement_benchmark_run
            FOREIGN KEY (benchmark_run_id)
            REFERENCES fhq_governance.aiqf_benchmark_runs(run_id);
    END IF;
END $$;

-- Add back-reference from evidence bundle to refinement log
ALTER TABLE fhq_governance.refinement_evidence_bundle
    ADD CONSTRAINT fk_evidence_refinement
    FOREIGN KEY (refinement_id) REFERENCES fhq_governance.sql_refinement_log(refinement_id);

-- Indexes for refinement log
CREATE INDEX idx_refinement_success
    ON fhq_governance.sql_refinement_log(success, created_at DESC);
CREATE INDEX idx_refinement_agent
    ON fhq_governance.sql_refinement_log(agent_id, created_at DESC);
CREATE INDEX idx_refinement_circuit_state
    ON fhq_governance.sql_refinement_log(circuit_state)
    WHERE circuit_state != 'CLOSED';
CREATE INDEX idx_refinement_escalated
    ON fhq_governance.sql_refinement_log(escalated_to_human)
    WHERE escalated_to_human = TRUE;
CREATE INDEX idx_refinement_exceeded
    ON fhq_governance.sql_refinement_log(latency_exceeded, tokens_exceeded, cost_exceeded)
    WHERE latency_exceeded OR tokens_exceeded OR cost_exceeded;

-- ============================================================================
-- SECTION 4: Circuit Breaker Integration
-- Purpose: Register SQL refinement breaker in EXISTING circuit_breakers table
-- CEO DIRECTIVE: No new circuit breaker tables - reuse fhq_governance.circuit_breakers
-- ============================================================================

-- Insert refinement circuit breaker (ON CONFLICT handles idempotency)
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name,
    breaker_type,
    trigger_condition,
    defcon_threshold,
    action_on_trigger,
    is_enabled
) VALUES (
    'SQL_REFINEMENT_FAILURE',
    'GOVERNANCE',
    jsonb_build_object(
        'condition', 'refinement_failures_10min > 5',
        'description', 'SQL refinement loop failure rate exceeded threshold',
        'measurement_window_minutes', 10,
        'failure_threshold', 5,
        'metrics_table', 'fhq_monitoring.sql_refinement_metrics',
        'health_table', 'fhq_monitoring.agent_semantic_health'
    ),
    'YELLOW',
    jsonb_build_object(
        'actions', ARRAY['THROTTLE_REFINEMENT', 'LOG_TO_GOVERNANCE', 'ALERT_STIG'],
        'throttle_factor', 0.5,
        'cooldown_minutes', 5
    ),
    true
)
ON CONFLICT (breaker_name) DO NOTHING;

-- Also register a latency-specific breaker for refinement
INSERT INTO fhq_governance.circuit_breakers (
    breaker_name,
    breaker_type,
    trigger_condition,
    defcon_threshold,
    action_on_trigger,
    is_enabled
) VALUES (
    'SQL_REFINEMENT_LATENCY',
    'GOVERNANCE',
    jsonb_build_object(
        'condition', 'p95_latency_ms > 1800',
        'description', 'SQL refinement approaching 2000ms latency ceiling',
        'warning_threshold_ms', 1800,
        'hard_ceiling_ms', 2000,
        'measurement_window_minutes', 5
    ),
    'YELLOW',
    jsonb_build_object(
        'actions', ARRAY['REDUCE_COMPLEXITY', 'SWITCH_TO_FASTER_MODEL', 'LOG_WARNING'],
        'pre_emptive', true
    ),
    true
)
ON CONFLICT (breaker_name) DO NOTHING;

-- ============================================================================
-- SECTION 5: Seed Correction Guidelines (Common Patterns)
-- Purpose: Initial set of correction templates based on known error patterns
-- ============================================================================

INSERT INTO fhq_governance.sql_correction_guidelines (
    error_pattern, error_taxonomy, correction_template, created_by, is_active
) VALUES
    -- Syntax errors
    ('missing FROM clause', 'SYNTAX',
     'Add FROM clause with the primary table. Check reasoning artifact for schema_elements.tables.',
     'STIG', true),

    ('column ambiguous', 'SYNTAX',
     'Prefix column with table alias. Use reasoning artifact join_plan to determine correct table.',
     'STIG', true),

    -- Semantic errors
    ('column does not exist', 'SEMANTIC',
     'Verify column name against schema. Check for typos or use INFORMATION_SCHEMA lookup.',
     'STIG', true),

    ('relation does not exist', 'SEMANTIC',
     'Verify table name and schema. Ensure schema prefix is included (e.g., fhq_meta.table_name).',
     'STIG', true),

    -- Join path errors
    ('invalid foreign key path', 'JOIN_PATH',
     'Use fhq_graph.edges to find valid FK relationship. Avoid assumed joins without FK evidence.',
     'STIG', true),

    ('cartesian product detected', 'JOIN_PATH',
     'Add explicit JOIN condition. Never use implicit cross joins without explicit WHERE.',
     'STIG', true),

    -- Aggregation errors
    ('not in GROUP BY', 'AGGREGATION',
     'Add non-aggregated column to GROUP BY or wrap in aggregate function.',
     'STIG', true),

    -- Timeout errors
    ('query timeout exceeded', 'TIMEOUT',
     'Simplify query: reduce JOINs, add LIMIT, use indexed columns in WHERE. Consider pagination.',
     'STIG', true)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 6: Views for Refinement Analysis
-- ============================================================================

-- View: Recent refinement performance by agent
CREATE OR REPLACE VIEW fhq_governance.vw_refinement_performance AS
SELECT
    agent_id,
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as total_attempts,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN success AND attempt_number = 1 THEN 1 ELSE 0 END) as first_attempt_success,
    SUM(CASE WHEN escalated_to_human THEN 1 ELSE 0 END) as escalated,
    AVG(latency_ms) as avg_latency_ms,
    MAX(latency_ms) as max_latency_ms,
    SUM(tokens_consumed) as total_tokens,
    SUM(cost_usd) as total_cost_usd,
    AVG(CASE WHEN success THEN attempt_number ELSE NULL END) as avg_attempts_when_success
FROM fhq_governance.sql_refinement_log
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY agent_id, DATE_TRUNC('hour', created_at)
ORDER BY hour DESC, agent_id;

-- View: Guideline effectiveness ranking
CREATE OR REPLACE VIEW fhq_governance.vw_guideline_effectiveness AS
SELECT
    g.guideline_id,
    g.error_pattern,
    g.error_taxonomy,
    g.usage_count,
    g.success_rate,
    g.success_rate_confidence_lower,
    g.is_global_default,
    g.vega_signoff_attestation_id IS NOT NULL as vega_approved,
    CASE
        WHEN g.usage_count < 10 THEN 'INSUFFICIENT_DATA'
        WHEN g.success_rate >= 0.9 THEN 'HIGHLY_EFFECTIVE'
        WHEN g.success_rate >= 0.7 THEN 'EFFECTIVE'
        WHEN g.success_rate >= 0.5 THEN 'MARGINAL'
        ELSE 'INEFFECTIVE'
    END as effectiveness_tier
FROM fhq_governance.sql_correction_guidelines g
WHERE g.is_active = TRUE
ORDER BY g.success_rate DESC, g.usage_count DESC;

-- ============================================================================
-- SECTION 7: Governance Integration - Log this migration
-- ============================================================================

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
    '191_reasoning_driven_sql_refinement.sql',
    'DATABASE_MIGRATION',
    'STIG',
    'EXECUTE',
    'CEO-AUTH-2026-ADR022-M191: SQL refinement log, correction guidelines, circuit breaker integration',
    jsonb_build_object(
        'migration_id', '191_reasoning_driven_sql_refinement',
        'adr_reference', 'ADR-022',
        'purpose', 'SQL refinement log, correction guidelines, circuit breaker integration',
        'ceo_corrections_applied', 8,
        'tables_created', ARRAY[
            'fhq_governance.sql_correction_guidelines',
            'fhq_governance.refinement_evidence_bundle',
            'fhq_governance.sql_refinement_log'
        ],
        'views_created', ARRAY[
            'fhq_governance.vw_refinement_performance',
            'fhq_governance.vw_guideline_effectiveness'
        ],
        'circuit_breakers_registered', ARRAY[
            'SQL_REFINEMENT_FAILURE',
            'SQL_REFINEMENT_LATENCY'
        ],
        'hard_ceilings', jsonb_build_object(
            'max_attempts', 3,
            'max_tokens', 4000,
            'max_latency_ms', 2000,
            'max_cost_usd', 0.02
        ),
        'execution_order', 3,
        'previous_migration', '191b_aiqf_benchmark_registry.sql',
        'dependency_attestations', ARRAY[
            '869709bf-b45f-428b-afd8-dacb5770b825',
            'd95de074-6b8e-4664-b368-343cec670f6b'
        ]
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================================

-- Verification Query 1: Check all tables exist
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'fhq_governance'
-- AND table_name IN ('sql_correction_guidelines', 'refinement_evidence_bundle', 'sql_refinement_log');

-- Verification Query 2: Check circuit breakers registered
-- SELECT breaker_name, breaker_type, defcon_threshold, is_active
-- FROM fhq_governance.circuit_breakers
-- WHERE breaker_name LIKE 'SQL_REFINEMENT%';

-- Verification Query 3: Check seed guidelines inserted
-- SELECT error_pattern, error_taxonomy, is_active
-- FROM fhq_governance.sql_correction_guidelines;

-- Verification Query 4: Check hard ceilings are correct
-- SELECT
--     column_name,
--     column_default
-- FROM information_schema.columns
-- WHERE table_schema = 'fhq_governance'
-- AND table_name = 'sql_refinement_log'
-- AND column_name IN ('latency_budget_ms', 'tokens_budget', 'cost_budget_usd', 'max_attempts');
-- Expected: latency_budget_ms=2000, tokens_budget=4000, cost_budget_usd=0.02, max_attempts=3
