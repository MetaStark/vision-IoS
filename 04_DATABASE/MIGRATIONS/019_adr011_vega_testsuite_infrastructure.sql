-- =====================================================
-- MIGRATION 019: ADR-011 VEGA TESTSUITE INFRASTRUCTURE
-- =====================================================
--
-- Authority: LARS (ADR-011 Production Fortress & VEGA Testsuite Architecture)
-- Purpose: Create VEGA attestation tables for Production Fortress
-- Compliance: ADR-011 Section 4.2 (VEGA Attestation Layer)
--
-- This migration creates:
--   1. vega.test_runs - Test execution records
--   2. vega.test_coverage - Coverage metrics
--   3. vega.quality_gate_results - QG-F Series results
--   4. vega.test_failures - Failure tracking
--   5. vega.agent_test_execution - Agent-level test results
--   6. vega.api_endpoint_tests - API endpoint verification
--   7. fhq_meta.adr_registry - ADR registration table
--   8. fhq_meta.adr_dependencies - ADR dependency tracking
--
-- Target Database: 127.0.0.1:54322
-- =====================================================

BEGIN;

-- =====================================================
-- SCHEMA CREATION
-- =====================================================

CREATE SCHEMA IF NOT EXISTS vega;
CREATE SCHEMA IF NOT EXISTS fhq_meta;

-- =====================================================
-- ADR REGISTRY TABLE (for all ADR registrations)
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_meta.adr_registry (
    adr_id TEXT PRIMARY KEY,

    -- ADR metadata
    adr_title TEXT NOT NULL,
    adr_type TEXT NOT NULL CHECK (adr_type IN ('CONSTITUTIONAL', 'OPERATIONAL', 'GOVERNANCE', 'TECHNICAL')),
    adr_version TEXT NOT NULL,

    -- Status
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'PROPOSED', 'APPROVED', 'DEPRECATED', 'SUPERSEDED')),

    -- Authority
    approval_authority TEXT NOT NULL,
    approval_date TIMESTAMPTZ,

    -- Integrity
    sha256_hash TEXT NOT NULL,
    document_path TEXT,

    -- Governance tier
    governance_tier TEXT CHECK (governance_tier IN ('Tier-0', 'Tier-1', 'Tier-2', 'Tier-3')),

    -- Audit
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by TEXT NOT NULL DEFAULT 'SYSTEM',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_meta.adr_registry IS 'ADR-002: Registry of all Architecture Decision Records';

-- =====================================================
-- ADR DEPENDENCIES TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_meta.adr_dependencies (
    dependency_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Dependency relationship
    adr_id TEXT NOT NULL REFERENCES fhq_meta.adr_registry(adr_id),
    depends_on_adr_id TEXT NOT NULL,

    -- Dependency metadata
    dependency_type TEXT NOT NULL CHECK (dependency_type IN ('GOVERNANCE', 'TECHNICAL', 'CONSTITUTIONAL', 'OPERATIONAL')),
    criticality TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (criticality IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    version TEXT NOT NULL,

    -- Description
    dependency_description TEXT,

    -- Audit
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT adr_dependencies_unique UNIQUE (adr_id, depends_on_adr_id)
);

COMMENT ON TABLE fhq_meta.adr_dependencies IS 'ADR-002: Dependency tracking between ADRs';

-- =====================================================
-- 4.2: VEGA TEST RUNS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS vega.test_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run identification
    run_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_type TEXT NOT NULL DEFAULT 'FULL',
    run_environment TEXT NOT NULL DEFAULT 'PRODUCTION',

    -- Test configuration
    test_layers TEXT[] NOT NULL DEFAULT ARRAY['UNIT', 'SERVICES', 'WORKER_API', 'INTEGRATION', 'TIER3', 'TIER3_5'],
    platform TEXT NOT NULL,  -- 'linux', 'windows', 'darwin'

    -- Results summary
    total_tests INTEGER NOT NULL DEFAULT 0,
    tests_passed INTEGER NOT NULL DEFAULT 0,
    tests_failed INTEGER NOT NULL DEFAULT 0,
    tests_skipped INTEGER NOT NULL DEFAULT 0,

    -- Execution metrics
    execution_time_ms INTEGER NOT NULL DEFAULT 0,
    coverage_percentage NUMERIC(5, 2) DEFAULT 0.0,

    -- Status
    run_status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (run_status IN ('RUNNING', 'COMPLETED', 'FAILED', 'ABORTED')),

    -- VEGA attestation
    vega_attested BOOLEAN NOT NULL DEFAULT FALSE,
    vega_signature TEXT,
    attestation_timestamp TIMESTAMPTZ,

    -- ADR reference
    adr_reference TEXT NOT NULL DEFAULT 'ADR-011',

    -- Audit
    initiated_by TEXT NOT NULL DEFAULT 'SYSTEM',
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vega_test_runs_timestamp ON vega.test_runs(run_timestamp DESC);
CREATE INDEX idx_vega_test_runs_status ON vega.test_runs(run_status);
CREATE INDEX idx_vega_test_runs_attested ON vega.test_runs(vega_attested);

COMMENT ON TABLE vega.test_runs IS 'ADR-011 Section 4.2: VEGA test run records for Production Fortress';

-- =====================================================
-- 4.2: VEGA TEST COVERAGE TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS vega.test_coverage (
    coverage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to run
    run_id UUID NOT NULL REFERENCES vega.test_runs(run_id),

    -- Coverage scope
    module_name TEXT NOT NULL,
    module_type TEXT NOT NULL CHECK (module_type IN ('CRYPTO', 'GOVERNANCE', 'ORCHESTRATOR', 'AGENT', 'API', 'ECONOMIC')),

    -- Coverage metrics
    lines_total INTEGER NOT NULL DEFAULT 0,
    lines_covered INTEGER NOT NULL DEFAULT 0,
    lines_missed INTEGER NOT NULL DEFAULT 0,

    branches_total INTEGER NOT NULL DEFAULT 0,
    branches_covered INTEGER NOT NULL DEFAULT 0,

    -- Coverage percentage
    line_coverage_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    branch_coverage_pct NUMERIC(5, 2) DEFAULT 0.0,

    -- Quality gate compliance (QG-F1)
    meets_threshold BOOLEAN NOT NULL DEFAULT FALSE,
    required_threshold NUMERIC(5, 2) NOT NULL DEFAULT 80.0,

    -- Audit
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT test_coverage_line_check CHECK (lines_covered <= lines_total),
    CONSTRAINT test_coverage_branch_check CHECK (branches_covered <= branches_total)
);

CREATE INDEX idx_vega_test_coverage_run ON vega.test_coverage(run_id);
CREATE INDEX idx_vega_test_coverage_module ON vega.test_coverage(module_name);
CREATE INDEX idx_vega_test_coverage_threshold ON vega.test_coverage(meets_threshold);

COMMENT ON TABLE vega.test_coverage IS 'ADR-011 Section 4.2: Test coverage metrics per module';

-- =====================================================
-- 4.2: VEGA QUALITY GATE RESULTS TABLE (QG-F Series)
-- =====================================================

CREATE TABLE IF NOT EXISTS vega.quality_gate_results (
    gate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to run
    run_id UUID NOT NULL REFERENCES vega.test_runs(run_id),

    -- Gate identification (QG-F1 through QG-F6)
    gate_code TEXT NOT NULL CHECK (gate_code IN ('QG-F1', 'QG-F2', 'QG-F3', 'QG-F4', 'QG-F5', 'QG-F6')),
    gate_name TEXT NOT NULL,
    gate_description TEXT,

    -- Gate status
    gate_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (gate_status IN ('PENDING', 'PASS', 'FAIL', 'BLOCKED', 'SKIPPED')),

    -- Gate requirements
    requirement_type TEXT NOT NULL,
    requirement_value TEXT NOT NULL,
    actual_value TEXT,

    -- Evaluation
    evaluated_at TIMESTAMPTZ,
    evaluation_notes TEXT,

    -- Evidence
    evidence_bundle_id UUID,
    evidence_hash TEXT,

    -- ADR reference
    adr_reference TEXT NOT NULL DEFAULT 'ADR-011',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vega_quality_gates_run ON vega.quality_gate_results(run_id);
CREATE INDEX idx_vega_quality_gates_code ON vega.quality_gate_results(gate_code);
CREATE INDEX idx_vega_quality_gates_status ON vega.quality_gate_results(gate_status);

COMMENT ON TABLE vega.quality_gate_results IS 'ADR-011 Section 6: Quality Gate (QG-F1 to QG-F6) evaluation results';

-- =====================================================
-- 4.2: VEGA TEST FAILURES TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS vega.test_failures (
    failure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to run
    run_id UUID NOT NULL REFERENCES vega.test_runs(run_id),

    -- Test identification
    test_name TEXT NOT NULL,
    test_module TEXT NOT NULL,
    test_layer TEXT NOT NULL CHECK (test_layer IN ('UNIT', 'SERVICES', 'WORKER_API', 'INTEGRATION', 'TIER3', 'TIER3_5')),

    -- Failure details
    failure_type TEXT NOT NULL DEFAULT 'ASSERTION',
    failure_message TEXT NOT NULL,
    stack_trace TEXT,

    -- Failure context
    input_data JSONB,
    expected_output JSONB,
    actual_output JSONB,

    -- Reproducibility (QG-F4)
    is_reproducible BOOLEAN DEFAULT NULL,
    reproduction_count INTEGER DEFAULT 0,

    -- Resolution
    resolution_status TEXT NOT NULL DEFAULT 'OPEN' CHECK (resolution_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'WONT_FIX', 'KNOWN_ISSUE')),
    resolution_notes TEXT,
    resolved_at TIMESTAMPTZ,

    -- Audit
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vega_test_failures_run ON vega.test_failures(run_id);
CREATE INDEX idx_vega_test_failures_module ON vega.test_failures(test_module);
CREATE INDEX idx_vega_test_failures_status ON vega.test_failures(resolution_status);

COMMENT ON TABLE vega.test_failures IS 'ADR-011 Section 4.2: Test failure tracking with reproducibility verification';

-- =====================================================
-- 4.2: VEGA AGENT TEST EXECUTION TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS vega.agent_test_execution (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to run
    run_id UUID NOT NULL REFERENCES vega.test_runs(run_id),

    -- Agent identification (ADR-007 agents)
    agent_id TEXT NOT NULL CHECK (agent_id IN ('LARS', 'STIG', 'LINE', 'FINN', 'VEGA')),

    -- Test scope
    test_category TEXT NOT NULL,
    tests_executed INTEGER NOT NULL DEFAULT 0,
    tests_passed INTEGER NOT NULL DEFAULT 0,
    tests_failed INTEGER NOT NULL DEFAULT 0,

    -- Agent-specific metrics
    governance_loop_verified BOOLEAN DEFAULT FALSE,
    authority_boundary_verified BOOLEAN DEFAULT FALSE,
    llm_tier_verified BOOLEAN DEFAULT FALSE,

    -- Integration tests (QG-F2)
    integration_status TEXT DEFAULT 'PENDING' CHECK (integration_status IN ('PENDING', 'PASS', 'FAIL', 'PARTIAL')),

    -- Execution context
    execution_duration_ms INTEGER DEFAULT 0,
    execution_context JSONB,

    -- Audit
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vega_agent_execution_run ON vega.agent_test_execution(run_id);
CREATE INDEX idx_vega_agent_execution_agent ON vega.agent_test_execution(agent_id);
CREATE INDEX idx_vega_agent_execution_status ON vega.agent_test_execution(integration_status);

COMMENT ON TABLE vega.agent_test_execution IS 'ADR-011 Section 5.1: Per-agent test execution results';

-- =====================================================
-- 4.2: VEGA API ENDPOINT TESTS TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS vega.api_endpoint_tests (
    test_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to run
    run_id UUID NOT NULL REFERENCES vega.test_runs(run_id),

    -- Endpoint identification
    endpoint_path TEXT NOT NULL,
    endpoint_method TEXT NOT NULL CHECK (endpoint_method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')),
    endpoint_category TEXT NOT NULL,

    -- Test results
    test_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (test_status IN ('PENDING', 'PASS', 'FAIL', 'SKIPPED')),

    -- Response metrics
    response_time_ms INTEGER,
    response_status_code INTEGER,

    -- Validation
    schema_validated BOOLEAN DEFAULT FALSE,
    auth_validated BOOLEAN DEFAULT FALSE,
    governance_validated BOOLEAN DEFAULT FALSE,

    -- Test evidence
    request_payload JSONB,
    response_payload JSONB,
    validation_errors JSONB,

    -- Audit
    tested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vega_api_tests_run ON vega.api_endpoint_tests(run_id);
CREATE INDEX idx_vega_api_tests_endpoint ON vega.api_endpoint_tests(endpoint_path, endpoint_method);
CREATE INDEX idx_vega_api_tests_status ON vega.api_endpoint_tests(test_status);

COMMENT ON TABLE vega.api_endpoint_tests IS 'ADR-011 Section 5.2: API endpoint verification results';

-- =====================================================
-- UTILITY FUNCTIONS
-- =====================================================

-- Function to get latest attestation
CREATE OR REPLACE FUNCTION vega.latest_attestation()
RETURNS TABLE (
    run_id UUID,
    run_timestamp TIMESTAMPTZ,
    total_tests INTEGER,
    tests_passed INTEGER,
    tests_failed INTEGER,
    status TEXT,
    vega_attested BOOLEAN,
    vega_signature TEXT,
    attestation_timestamp TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tr.run_id,
        tr.run_timestamp,
        tr.total_tests,
        tr.tests_passed,
        tr.tests_failed,
        tr.run_status,
        tr.vega_attested,
        tr.vega_signature,
        tr.attestation_timestamp
    FROM vega.test_runs tr
    WHERE tr.vega_attested = TRUE
    ORDER BY tr.attestation_timestamp DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to validate fortress integrity
CREATE OR REPLACE FUNCTION vega.vega_validate_fortress_integrity()
RETURNS BOOLEAN AS $$
DECLARE
    latest_run RECORD;
    all_gates_pass BOOLEAN;
BEGIN
    -- Get latest attested run
    SELECT * INTO latest_run
    FROM vega.test_runs
    WHERE vega_attested = TRUE
    ORDER BY attestation_timestamp DESC
    LIMIT 1;

    IF latest_run IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Check all quality gates passed
    SELECT NOT EXISTS (
        SELECT 1 FROM vega.quality_gate_results
        WHERE run_id = latest_run.run_id
          AND gate_status != 'PASS'
    ) INTO all_gates_pass;

    -- Return TRUE only if:
    -- 1. We have an attested run
    -- 2. All quality gates passed
    -- 3. No failures in the run
    RETURN latest_run.vega_attested
           AND all_gates_pass
           AND latest_run.tests_failed = 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vega.latest_attestation() IS 'ADR-011: Returns the most recent VEGA attestation';
COMMENT ON FUNCTION vega.vega_validate_fortress_integrity() IS 'ADR-011: Validates Production Fortress integrity status';

-- =====================================================
-- VERIFICATION
-- =====================================================

DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'vega';

    IF table_count < 6 THEN
        RAISE EXCEPTION 'VEGA schema tables not fully created. Found: %', table_count;
    END IF;

    RAISE NOTICE 'ADR-011 VEGA Testsuite Infrastructure: % tables created', table_count;
END $$;

COMMIT;

-- =====================================================
-- MIGRATION SUMMARY
-- =====================================================

SELECT
    'MIGRATION 019 COMPLETE' AS status,
    'ADR-011 VEGA Testsuite Infrastructure' AS description,
    NOW() AS completed_at;

\echo ''
\echo '=========================================='
\echo 'MIGRATION 019: ADR-011 VEGA TESTSUITE'
\echo '=========================================='
\echo 'Tables created in vega schema:'
\echo '  - vega.test_runs'
\echo '  - vega.test_coverage'
\echo '  - vega.quality_gate_results'
\echo '  - vega.test_failures'
\echo '  - vega.agent_test_execution'
\echo '  - vega.api_endpoint_tests'
\echo ''
\echo 'Tables created in fhq_meta schema:'
\echo '  - fhq_meta.adr_registry'
\echo '  - fhq_meta.adr_dependencies'
\echo ''
\echo 'Functions created:'
\echo '  - vega.latest_attestation()'
\echo '  - vega.vega_validate_fortress_integrity()'
\echo '=========================================='
\echo ''
