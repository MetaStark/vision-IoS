-- Migration: 191b_aiqf_benchmark_registry.sql
-- ADR-022: The Autonomous Database Horizon Implementation Charter
-- Purpose: AIQF (AI Quality Factor) canonical metric definition + benchmark registry
-- Execution Order: SECOND (after 196, before 191)
-- Schema: fhq_governance (governance metric, not monitoring)
--
-- AIQF CANONICAL FORMULA (CEO-Approved):
-- AIQF = (correct_first_attempt × 0.60) +
--        (correct_within_3 × 0.25) +
--        (semantic_correct × 0.10) +
--        (no_escalation × 0.05)
--
-- PASS THRESHOLD: AIQF ≥ 0.95
-- DRIFT ALERT: AIQF drop > 2% from certified baseline
--
-- Dependencies: 196_observability_2_immediate.sql (for drift detection views)
-- Required By: 191_reasoning_driven_sql_refinement.sql (FK to benchmark_runs)

BEGIN;

-- ============================================================================
-- SECTION 1: AIQF Benchmark Registry
-- Purpose: Define test sets for measuring SQL refinement quality
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.aiqf_benchmark_registry (
    benchmark_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_name VARCHAR(100) NOT NULL,
    benchmark_version INTEGER NOT NULL,

    -- Test set specification
    dataset_hash VARCHAR(64) NOT NULL,  -- SHA-256 of query set JSON
    query_count INTEGER NOT NULL CHECK (query_count > 0),
    query_set JSONB NOT NULL,  -- Array of query objects (see structure below)
    -- Query object structure:
    -- {
    --   "query_id": "Q001",
    --   "natural_language": "Find all golden needles from last week",
    --   "expected_sql": "SELECT * FROM fhq_canonical.golden_needles WHERE...",
    --   "expected_result_hash": "sha256...",
    --   "query_class": "multi_table_join",
    --   "complexity_score": 3,
    --   "schema_elements": {"tables": [...], "columns": [...]}
    -- }
    expected_results_fingerprint VARCHAR(64) NOT NULL,  -- Hash of all expected results

    -- Query class distribution (for balanced testing)
    query_class_distribution JSONB NOT NULL DEFAULT '{
        "simple_lookup": 10,
        "multi_table_join": 15,
        "aggregation_filter": 15,
        "complex_nested_window": 10
    }'::jsonb,

    -- Scoring specification (canonical formula)
    scoring_function_version VARCHAR(20) NOT NULL DEFAULT 'v1.0',
    scoring_formula TEXT NOT NULL DEFAULT
        '(correct_first_attempt * 0.6) + (correct_within_3 * 0.25) + (semantic_correct * 0.1) + (no_escalation * 0.05)',

    -- Model/prompt context (for reproducibility)
    model_version VARCHAR(100),
    prompt_template_hash VARCHAR(64),
    prompt_template_version VARCHAR(20),

    -- Thresholds
    pass_threshold FLOAT NOT NULL DEFAULT 0.95,
    drift_tolerance FLOAT NOT NULL DEFAULT 0.02,  -- Alert if AIQF drops >2%
    minimum_sample_size INTEGER NOT NULL DEFAULT 50,

    -- Governance controls
    created_by VARCHAR(20) NOT NULL,
    vega_certified BOOLEAN DEFAULT FALSE,
    vega_certification_attestation_id UUID,  -- FK to vega_attestations when certified
    vega_certification_date TIMESTAMPTZ,

    -- Lifecycle
    is_active BOOLEAN DEFAULT TRUE,
    supersedes_benchmark_id UUID REFERENCES fhq_governance.aiqf_benchmark_registry(benchmark_id),
    sunset_at TIMESTAMPTZ,
    sunset_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT benchmark_name_version_unique UNIQUE (benchmark_name, benchmark_version)
);

-- Add FK for VEGA attestation after confirming table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'fhq_governance' AND table_name = 'vega_attestations') THEN
        ALTER TABLE fhq_governance.aiqf_benchmark_registry
            ADD CONSTRAINT fk_aiqf_vega_attestation
            FOREIGN KEY (vega_certification_attestation_id)
            REFERENCES fhq_governance.vega_attestations(attestation_id);
    END IF;
END $$;

-- Indexes
CREATE INDEX idx_benchmark_active
    ON fhq_governance.aiqf_benchmark_registry(is_active, benchmark_name);
CREATE INDEX idx_benchmark_certified
    ON fhq_governance.aiqf_benchmark_registry(vega_certified)
    WHERE vega_certified = TRUE;

-- ============================================================================
-- SECTION 2: AIQF Benchmark Runs
-- Purpose: Track individual benchmark executions and their results
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.aiqf_benchmark_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_id UUID NOT NULL REFERENCES fhq_governance.aiqf_benchmark_registry(benchmark_id),

    -- Run context
    run_purpose VARCHAR(50) CHECK (run_purpose IN (
        'BASELINE',           -- Initial measurement
        'REGRESSION',         -- Checking for quality drop
        'PROMOTION',          -- Before promoting to production
        'CERTIFICATION',      -- VEGA G3→G4 gate
        'DRIFT_CHECK',        -- Scheduled drift detection
        'POST_CHANGE'         -- After guideline/model change
    )),

    -- Component breakdown (for AIQF formula)
    correct_first_attempt_count INTEGER NOT NULL DEFAULT 0,
    correct_within_3_count INTEGER NOT NULL DEFAULT 0,
    semantic_correct_count INTEGER NOT NULL DEFAULT 0,
    escalated_count INTEGER NOT NULL DEFAULT 0,
    total_queries_run INTEGER NOT NULL,

    -- Calculated rates
    correct_first_attempt_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN total_queries_run > 0
             THEN correct_first_attempt_count::FLOAT / total_queries_run
             ELSE 0.0 END
    ) STORED,
    correct_within_3_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN total_queries_run > 0
             THEN correct_within_3_count::FLOAT / total_queries_run
             ELSE 0.0 END
    ) STORED,
    semantic_correct_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN total_queries_run > 0
             THEN semantic_correct_count::FLOAT / total_queries_run
             ELSE 0.0 END
    ) STORED,
    no_escalation_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN total_queries_run > 0
             THEN 1.0 - (escalated_count::FLOAT / total_queries_run)
             ELSE 1.0 END
    ) STORED,

    -- AIQF score (canonical formula applied)
    aiqf_score FLOAT GENERATED ALWAYS AS (
        (CASE WHEN total_queries_run > 0
              THEN correct_first_attempt_count::FLOAT / total_queries_run * 0.60
              ELSE 0.0 END) +
        (CASE WHEN total_queries_run > 0
              THEN correct_within_3_count::FLOAT / total_queries_run * 0.25
              ELSE 0.0 END) +
        (CASE WHEN total_queries_run > 0
              THEN semantic_correct_count::FLOAT / total_queries_run * 0.10
              ELSE 0.0 END) +
        (CASE WHEN total_queries_run > 0
              THEN (1.0 - escalated_count::FLOAT / total_queries_run) * 0.05
              ELSE 0.05 END)
    ) STORED,

    -- Pass/fail determination (threshold from benchmark registry)
    passed BOOLEAN,  -- Set by trigger based on aiqf_score vs threshold
    gate_decision VARCHAR(20) CHECK (gate_decision IN ('PASS', 'FAIL', 'CONDITIONAL', 'PENDING')),
    gate_decision_reason TEXT,

    -- Performance metrics
    avg_latency_ms FLOAT,
    p95_latency_ms FLOAT,
    max_latency_ms INTEGER,
    total_tokens_consumed INTEGER,
    total_cost_usd FLOAT,

    -- Evidence chain (court-proof)
    run_evidence_hash VARCHAR(64) NOT NULL,  -- SHA-256 of full results
    detailed_results JSONB,  -- Per-query breakdown
    -- Structure: [{"query_id": "Q001", "success": true, "attempts": 1, "latency_ms": 150, ...}, ...]

    -- Comparison to baseline (drift detection)
    baseline_run_id UUID REFERENCES fhq_governance.aiqf_benchmark_runs(run_id),
    drift_from_baseline FLOAT,  -- aiqf_score difference
    drift_alert_triggered BOOLEAN DEFAULT FALSE,

    -- Execution metadata
    executed_by VARCHAR(20) NOT NULL,
    execution_environment JSONB,  -- Model version, prompt version, etc.
    executed_at TIMESTAMPTZ DEFAULT NOW(),

    -- Governance linkage
    governance_action_id UUID,
    vega_review_required BOOLEAN DEFAULT FALSE,
    vega_review_attestation_id UUID
);

-- Trigger to set 'passed' based on threshold
CREATE OR REPLACE FUNCTION fhq_governance.check_aiqf_pass()
RETURNS TRIGGER AS $$
DECLARE
    threshold FLOAT;
BEGIN
    SELECT pass_threshold INTO threshold
    FROM fhq_governance.aiqf_benchmark_registry
    WHERE benchmark_id = NEW.benchmark_id;

    NEW.passed := NEW.aiqf_score >= COALESCE(threshold, 0.95);

    IF NEW.gate_decision IS NULL THEN
        NEW.gate_decision := CASE
            WHEN NEW.passed THEN 'PASS'
            ELSE 'FAIL'
        END;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_aiqf_pass_check
    BEFORE INSERT OR UPDATE ON fhq_governance.aiqf_benchmark_runs
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.check_aiqf_pass();

-- Indexes
CREATE INDEX idx_benchmark_runs_benchmark
    ON fhq_governance.aiqf_benchmark_runs(benchmark_id, executed_at DESC);
CREATE INDEX idx_benchmark_runs_passed
    ON fhq_governance.aiqf_benchmark_runs(passed, gate_decision);
CREATE INDEX idx_benchmark_runs_drift
    ON fhq_governance.aiqf_benchmark_runs(drift_alert_triggered)
    WHERE drift_alert_triggered = TRUE;

-- ============================================================================
-- SECTION 3: AIQF Drift Alert Log
-- Purpose: Track when AIQF drops below threshold or drifts significantly
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.aiqf_drift_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES fhq_governance.aiqf_benchmark_runs(run_id),
    benchmark_id UUID NOT NULL REFERENCES fhq_governance.aiqf_benchmark_registry(benchmark_id),

    -- Alert type
    alert_type VARCHAR(30) CHECK (alert_type IN (
        'THRESHOLD_BREACH',   -- Below 0.95
        'DRIFT_EXCEEDED',     -- >2% drop from baseline
        'COMPONENT_ANOMALY',  -- One component drastically changed
        'LATENCY_SPIKE',      -- Latency exceeded budget
        'COST_SPIKE'          -- Cost exceeded budget
    )),

    -- Severity
    severity VARCHAR(20) CHECK (severity IN ('WARNING', 'CRITICAL', 'EMERGENCY')),

    -- Details
    current_aiqf FLOAT NOT NULL,
    baseline_aiqf FLOAT,
    threshold FLOAT NOT NULL DEFAULT 0.95,
    drift_amount FLOAT,
    anomaly_component VARCHAR(30),  -- Which AIQF component is problematic
    anomaly_details JSONB,

    -- Response
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(20),
    acknowledged_at TIMESTAMPTZ,
    resolution_action TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,

    -- Escalation
    defcon_escalation_triggered BOOLEAN DEFAULT FALSE,
    defcon_level VARCHAR(10),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_drift_alerts_unresolved
    ON fhq_governance.aiqf_drift_alerts(resolved, severity)
    WHERE resolved = FALSE;

-- ============================================================================
-- SECTION 4: Initial Benchmark Template (50 queries)
-- Purpose: Seed the benchmark registry with initial test set structure
-- ============================================================================

-- Insert template benchmark (to be populated with actual queries)
INSERT INTO fhq_governance.aiqf_benchmark_registry (
    benchmark_name,
    benchmark_version,
    dataset_hash,
    query_count,
    query_set,
    expected_results_fingerprint,
    query_class_distribution,
    scoring_function_version,
    pass_threshold,
    drift_tolerance,
    minimum_sample_size,
    created_by,
    is_active
) VALUES (
    'ADR022_INITIAL_BENCHMARK',
    1,
    'PLACEHOLDER_HASH_TO_BE_COMPUTED',  -- Will be updated when queries added
    50,
    '[]'::jsonb,  -- Empty, to be populated
    'PLACEHOLDER_FINGERPRINT_TO_BE_COMPUTED',
    '{
        "simple_lookup": 10,
        "multi_table_join": 15,
        "aggregation_filter": 15,
        "complex_nested_window": 10
    }'::jsonb,
    'v1.0',
    0.95,
    0.02,
    50,
    'STIG',
    FALSE  -- Not active until populated
);

-- ============================================================================
-- SECTION 5: View for VEGA Gate Integration
-- Purpose: Single view for VEGA to check if refinement is gate-ready
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.vw_aiqf_gate_status AS
WITH latest_runs AS (
    SELECT
        r.benchmark_id,
        r.run_id,
        r.aiqf_score,
        r.passed,
        r.gate_decision,
        r.drift_from_baseline,
        r.drift_alert_triggered,
        r.executed_at,
        ROW_NUMBER() OVER (PARTITION BY r.benchmark_id ORDER BY r.executed_at DESC) as rn
    FROM fhq_governance.aiqf_benchmark_runs r
),
active_benchmarks AS (
    SELECT
        b.benchmark_id,
        b.benchmark_name,
        b.benchmark_version,
        b.pass_threshold,
        b.drift_tolerance,
        b.vega_certified
    FROM fhq_governance.aiqf_benchmark_registry b
    WHERE b.is_active = TRUE
)
SELECT
    ab.benchmark_name,
    ab.benchmark_version,
    ab.vega_certified,
    lr.aiqf_score,
    ab.pass_threshold,
    lr.passed,
    lr.gate_decision,
    lr.drift_from_baseline,
    ab.drift_tolerance,
    lr.drift_alert_triggered,
    lr.executed_at as last_run_at,
    -- Gate readiness
    CASE
        WHEN lr.aiqf_score IS NULL THEN 'NO_RUNS'
        WHEN NOT lr.passed THEN 'BELOW_THRESHOLD'
        WHEN lr.drift_alert_triggered THEN 'DRIFT_ALERT'
        WHEN NOT ab.vega_certified THEN 'AWAITING_CERTIFICATION'
        ELSE 'READY'
    END as gate_status
FROM active_benchmarks ab
LEFT JOIN latest_runs lr ON ab.benchmark_id = lr.benchmark_id AND lr.rn = 1;

-- ============================================================================
-- SECTION 6: AIQF Real-Time Monitoring View (Moved from 196 per CEO scope discipline)
-- Purpose: Real-time AIQF calculation from observability metrics
-- Reads from: fhq_monitoring.sql_refinement_metrics (created in 196)
-- ============================================================================

CREATE OR REPLACE VIEW fhq_monitoring.vw_aiqf_realtime AS
SELECT
    agent_id,
    bucket_start,
    total_queries,
    -- AIQF calculation per ADR-022 canonical formula
    (first_attempt_rate * 0.60) +
    (within_3_rate * 0.25) +
    (CASE WHEN total_queries > 0
          THEN semantic_correct::FLOAT / total_queries * 0.10
          ELSE 0.0 END) +
    (CASE WHEN total_queries > 0
          THEN (1.0 - escalated_to_human::FLOAT / total_queries) * 0.05
          ELSE 0.05 END) AS aiqf_score,
    -- Compliance flags
    CASE WHEN max_latency_ms > 2000 THEN TRUE ELSE FALSE END AS latency_violation,
    CASE WHEN latency_budget_violations > 0 THEN latency_budget_violations ELSE 0 END AS violation_count,
    avg_latency_ms,
    p95_latency_ms,
    total_cost_usd,
    circuit_breaker_state
FROM fhq_monitoring.sql_refinement_metrics
WHERE bucket_start > NOW() - INTERVAL '24 hours'
ORDER BY bucket_start DESC;

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
    '191b_aiqf_benchmark_registry.sql',
    'DATABASE_MIGRATION',
    'STIG',
    'EXECUTE',
    'CEO-AUTH-2026-ADR022-M191B: AIQF canonical metric definition + benchmark registry',
    jsonb_build_object(
        'migration_id', '191b_aiqf_benchmark_registry',
        'adr_reference', 'ADR-022',
        'purpose', 'AIQF canonical metric definition + benchmark registry',
        'aiqf_formula', '(first×0.6) + (within3×0.25) + (semantic×0.1) + (no_escalation×0.05)',
        'pass_threshold', 0.95,
        'drift_tolerance', 0.02,
        'tables_created', ARRAY[
            'fhq_governance.aiqf_benchmark_registry',
            'fhq_governance.aiqf_benchmark_runs',
            'fhq_governance.aiqf_drift_alerts'
        ],
        'views_created', ARRAY[
            'fhq_governance.vw_aiqf_gate_status',
            'fhq_monitoring.vw_aiqf_realtime'
        ],
        'execution_order', 2,
        'previous_migration', '196_observability_2_immediate.sql',
        'next_migration', '191_reasoning_driven_sql_refinement.sql',
        'file_hash', '4ada4d69a048614d89e514dc469dd9f7cb586b31bb307c2dbdb32dda4b6032d4',
        'git_commit', '3f98f4ae55f303aaaa071dae8ca6212c0640f867'
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================================

-- Verification Query 1: Check AIQF formula is correctly implemented
-- SELECT
--     50 as total_queries,
--     45 as correct_first,
--     48 as correct_within_3,
--     47 as semantic_correct,
--     2 as escalated,
--     (45.0/50 * 0.60) + (48.0/50 * 0.25) + (47.0/50 * 0.10) + ((1.0 - 2.0/50) * 0.05) as expected_aiqf;
-- Expected: 0.9 + 0.24 + 0.094 + 0.048 = 0.882 (would FAIL threshold)

-- Verification Query 2: Check tables exist
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'fhq_governance'
-- AND table_name IN ('aiqf_benchmark_registry', 'aiqf_benchmark_runs', 'aiqf_drift_alerts');

-- Verification Query 3: Check template benchmark inserted
-- SELECT benchmark_name, benchmark_version, is_active
-- FROM fhq_governance.aiqf_benchmark_registry;
