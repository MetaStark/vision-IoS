-- ============================================================================
-- VEGA CONSOLIDATED FIX - CLEAN INSTALL
-- ============================================================================
-- Migration: 022_vega_consolidated_fix.sql
-- Purpose: Fix conflicts from 018-021, clean reinstall of all VEGA tables
-- Database: 127.0.0.1:54322
--
-- RUN THIS MIGRATION ONLY - IT REPLACES 018, 019, 020, 021
-- ============================================================================

-- Disable transaction for DDL
SET client_min_messages TO WARNING;

-- ============================================================================
-- STEP 1: CREATE SCHEMAS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_meta;
CREATE SCHEMA IF NOT EXISTS fhq_governance;
CREATE SCHEMA IF NOT EXISTS fhq_monitoring;
CREATE SCHEMA IF NOT EXISTS fhq_data;
CREATE SCHEMA IF NOT EXISTS vega;

-- ============================================================================
-- STEP 2: DROP CONFLICTING OBJECTS (IF ANY)
-- ============================================================================

-- Drop existing vega tables to recreate cleanly
DROP TABLE IF EXISTS vega.cost_alerts CASCADE;
DROP TABLE IF EXISTS vega.budget_allocations CASCADE;
DROP TABLE IF EXISTS vega.rate_limits CASCADE;
DROP TABLE IF EXISTS vega.cost_tracking CASCADE;
DROP TABLE IF EXISTS vega.llm_usage_log CASCADE;

-- Drop existing fhq_meta tables that conflict
DROP TABLE IF EXISTS fhq_meta.validation_reports CASCADE;
DROP TABLE IF EXISTS fhq_meta.validation_checks CASCADE;
DROP TABLE IF EXISTS fhq_meta.function_registry CASCADE;
DROP TABLE IF EXISTS fhq_meta.baseline_history CASCADE;
DROP TABLE IF EXISTS fhq_meta.baseline_state CASCADE;
DROP TABLE IF EXISTS fhq_meta.key_archival_log CASCADE;
DROP TABLE IF EXISTS fhq_meta.agent_keys CASCADE;
DROP TABLE IF EXISTS fhq_meta.data_source_registry CASCADE;
DROP TABLE IF EXISTS fhq_meta.vega_sovereignty_log CASCADE;
DROP TABLE IF EXISTS fhq_meta.data_lineage_log CASCADE;
DROP TABLE IF EXISTS fhq_meta.model_certifications CASCADE;
DROP TABLE IF EXISTS fhq_meta.adr_version_history CASCADE;
DROP TABLE IF EXISTS fhq_meta.adr_audit_log CASCADE;
DROP TABLE IF EXISTS fhq_meta.adr_registry CASCADE;

-- Drop existing fhq_governance tables
DROP TABLE IF EXISTS fhq_governance.gate_status CASCADE;
DROP TABLE IF EXISTS fhq_governance.gate_registry CASCADE;
DROP TABLE IF EXISTS fhq_governance.authority_matrix CASCADE;
DROP TABLE IF EXISTS fhq_governance.agent_contracts CASCADE;
DROP TABLE IF EXISTS fhq_governance.executive_roles CASCADE;

-- Drop existing fhq_monitoring tables
DROP TABLE IF EXISTS fhq_monitoring.execution_log CASCADE;
DROP TABLE IF EXISTS fhq_monitoring.ingestion_log CASCADE;

-- Drop existing fhq_data tables
DROP TABLE IF EXISTS fhq_data.price_series CASCADE;

-- Drop existing functions
DROP FUNCTION IF EXISTS fhq_meta.vega_verify_hashes CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.vega_compare_registry CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.vega_snapshot_canonical CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.vega_issue_certificate CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.vega_record_adversarial_event CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.vega_trigger_dora_assessment CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.vega_log_bias_drift CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.vega_enforce_class_b_threshold CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.vega_calculate_sovereignty_score CASCADE;
DROP FUNCTION IF EXISTS fhq_meta.trigger_audit_hash_chain CASCADE;
DROP FUNCTION IF EXISTS vega.log_llm_usage CASCADE;
DROP FUNCTION IF EXISTS vega.check_rate_limit CASCADE;
DROP FUNCTION IF EXISTS vega.get_daily_cost_summary CASCADE;

-- Drop views
DROP VIEW IF EXISTS fhq_meta.v_governance_health CASCADE;
DROP VIEW IF EXISTS fhq_meta.v_certification_status CASCADE;
DROP VIEW IF EXISTS fhq_meta.v_sovereignty_trend CASCADE;
DROP VIEW IF EXISTS vega.v_daily_cost_dashboard CASCADE;
DROP VIEW IF EXISTS vega.v_agent_cost_breakdown CASCADE;
DROP VIEW IF EXISTS vega.v_active_alerts CASCADE;

-- ============================================================================
-- STEP 3: CREATE FHQ_META TABLES
-- ============================================================================

-- ADR Audit Log (immutable)
CREATE TABLE fhq_meta.adr_audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    audit_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'INFO',
    discrepancy_class VARCHAR(10) DEFAULT 'NONE',
    actor VARCHAR(50) NOT NULL,
    action VARCHAR(200) NOT NULL,
    target VARCHAR(200),
    target_type VARCHAR(50),
    event_data JSONB NOT NULL DEFAULT '{}',
    authority VARCHAR(500),
    adr_compliance TEXT[],
    previous_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL,
    hash_chain_id VARCHAR(100),
    hash_chain_position INTEGER,
    vega_signature TEXT,
    vega_public_key TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,
    immutable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_timestamp ON fhq_meta.adr_audit_log(audit_timestamp DESC);
CREATE INDEX idx_audit_log_actor ON fhq_meta.adr_audit_log(actor);
CREATE INDEX idx_audit_log_event_type ON fhq_meta.adr_audit_log(event_type);

-- ADR Registry
CREATE TABLE fhq_meta.adr_registry (
    adr_id SERIAL PRIMARY KEY,
    adr_number VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    version VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    phase VARCHAR(50),
    content_hash VARCHAR(64) NOT NULL,
    file_path VARCHAR(500),
    owner VARCHAR(100) NOT NULL,
    approved_by VARCHAR(100),
    effective_date DATE,
    supersedes VARCHAR(500),
    dependencies TEXT[],
    classification VARCHAR(50),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    last_verified_at TIMESTAMPTZ,
    vega_signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_adr_registry_number ON fhq_meta.adr_registry(adr_number);

-- ADR Version History
CREATE TABLE fhq_meta.adr_version_history (
    version_id BIGSERIAL PRIMARY KEY,
    adr_number VARCHAR(20) NOT NULL,
    adr_title VARCHAR(500) NOT NULL,
    version_number VARCHAR(50) NOT NULL,
    version_status VARCHAR(50) NOT NULL,
    version_phase VARCHAR(50),
    effective_date DATE,
    supersedes VARCHAR(500),
    superseded_by VARCHAR(500),
    owner VARCHAR(100) NOT NULL,
    approved_by VARCHAR(100),
    content_hash VARCHAR(64) NOT NULL,
    file_path VARCHAR(500),
    change_summary TEXT,
    change_type VARCHAR(50),
    vega_signature TEXT,
    signature_timestamp TIMESTAMPTZ,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    UNIQUE (adr_number, version_number)
);

-- Model Certifications
CREATE TABLE fhq_meta.model_certifications (
    certification_id BIGSERIAL PRIMARY KEY,
    model_id VARCHAR(100) NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50),
    gate_1_research BOOLEAN DEFAULT FALSE,
    gate_1_timestamp TIMESTAMPTZ,
    gate_2_development BOOLEAN DEFAULT FALSE,
    gate_2_timestamp TIMESTAMPTZ,
    gate_3_validation BOOLEAN DEFAULT FALSE,
    gate_3_timestamp TIMESTAMPTZ,
    gate_4_staging BOOLEAN DEFAULT FALSE,
    gate_4_timestamp TIMESTAMPTZ,
    gate_5_production BOOLEAN DEFAULT FALSE,
    gate_5_timestamp TIMESTAMPTZ,
    gate_6_monitoring BOOLEAN DEFAULT FALSE,
    gate_6_timestamp TIMESTAMPTZ,
    certification_status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    bias_score DECIMAL(5,4),
    drift_score DECIMAL(5,4),
    explainability_score DECIMAL(5,4),
    robustness_score DECIMAL(5,4),
    overall_certification_score DECIMAL(5,4),
    xai_artifacts JSONB DEFAULT '{}',
    adversarial_test_passed BOOLEAN DEFAULT FALSE,
    adversarial_test_timestamp TIMESTAMPTZ,
    adversarial_results JSONB DEFAULT '{}',
    iso_42001_compliant BOOLEAN DEFAULT FALSE,
    dora_compliant BOOLEAN DEFAULT FALSE,
    gips_compliant BOOLEAN DEFAULT FALSE,
    vega_signature TEXT NOT NULL,
    vega_public_key TEXT NOT NULL,
    signature_verified BOOLEAN DEFAULT FALSE,
    retirement_date DATE,
    retirement_reason TEXT,
    certified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    certified_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    last_review_at TIMESTAMPTZ,
    next_review_due DATE,
    UNIQUE (model_id, model_version)
);

-- Data Lineage Log
CREATE TABLE fhq_meta.data_lineage_log (
    lineage_id BIGSERIAL PRIMARY KEY,
    lineage_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lineage_chain_id VARCHAR(100) NOT NULL,
    lineage_position INTEGER NOT NULL,
    source_system VARCHAR(100) NOT NULL,
    source_schema VARCHAR(100),
    source_table VARCHAR(100),
    source_column VARCHAR(100),
    source_record_id TEXT,
    target_system VARCHAR(100) NOT NULL,
    target_schema VARCHAR(100),
    target_table VARCHAR(100),
    target_column VARCHAR(100),
    target_record_id TEXT,
    transformation_type VARCHAR(50),
    transformation_logic TEXT,
    transformation_hash VARCHAR(64),
    quality_score DECIMAL(5,4),
    quality_checks JSONB DEFAULT '{}',
    processing_agent VARCHAR(50) NOT NULL,
    previous_lineage_hash VARCHAR(64),
    lineage_hash VARCHAR(64) NOT NULL,
    vega_signature TEXT,
    attested BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (lineage_chain_id, lineage_position)
);

-- Sovereignty Log
CREATE TABLE fhq_meta.vega_sovereignty_log (
    sovereignty_id BIGSERIAL PRIMARY KEY,
    score_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scoring_period VARCHAR(20) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    overall_sovereignty_score DECIMAL(5,4) NOT NULL,
    constitutional_compliance_score DECIMAL(5,4),
    operational_autonomy_score DECIMAL(5,4),
    data_sovereignty_score DECIMAL(5,4),
    regulatory_compliance_score DECIMAL(5,4),
    economic_sovereignty_score DECIMAL(5,4),
    metrics_breakdown JSONB NOT NULL DEFAULT '{}',
    adr_compliance_status JSONB DEFAULT '{}',
    total_adrs_compliant INTEGER DEFAULT 0,
    total_adrs_evaluated INTEGER DEFAULT 0,
    audit_findings_count INTEGER DEFAULT 0,
    class_a_events INTEGER DEFAULT 0,
    class_b_events INTEGER DEFAULT 0,
    class_c_events INTEGER DEFAULT 0,
    models_certified INTEGER DEFAULT 0,
    models_pending INTEGER DEFAULT 0,
    models_suspended INTEGER DEFAULT 0,
    dora_compliance_status VARCHAR(20),
    gips_compliance_status VARCHAR(20),
    vega_signature TEXT NOT NULL,
    vega_public_key TEXT NOT NULL,
    signature_verified BOOLEAN DEFAULT FALSE,
    previous_score DECIMAL(5,4),
    score_delta DECIMAL(5,4),
    trend VARCHAR(20),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    calculated_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    UNIQUE (scoring_period, period_start, period_end)
);

-- Agent Keys
CREATE TABLE fhq_meta.agent_keys (
    key_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    key_type VARCHAR(20) NOT NULL DEFAULT 'Ed25519',
    public_key_hex TEXT NOT NULL,
    public_key_fingerprint VARCHAR(64) NOT NULL,
    key_purpose VARCHAR(100) NOT NULL,
    algorithm_params JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    rotated_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revocation_reason TEXT,
    previous_key_id INTEGER,
    rotation_count INTEGER DEFAULT 0,
    registered_by VARCHAR(50) NOT NULL DEFAULT 'VEGA'
);

CREATE INDEX idx_agent_keys_agent ON fhq_meta.agent_keys(agent_id);

-- Key Archival Log
CREATE TABLE fhq_meta.key_archival_log (
    archive_id SERIAL PRIMARY KEY,
    key_id INTEGER NOT NULL,
    agent_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    public_key_fingerprint VARCHAR(64) NOT NULL,
    previous_fingerprint VARCHAR(64),
    event_reason TEXT,
    event_hash VARCHAR(64) NOT NULL,
    vega_signature TEXT,
    recorded_by VARCHAR(50) NOT NULL DEFAULT 'VEGA'
);

-- Data Source Registry
CREATE TABLE fhq_meta.data_source_registry (
    source_id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL UNIQUE,
    source_type VARCHAR(50) NOT NULL,
    api_endpoint VARCHAR(500),
    api_version VARCHAR(50),
    auth_type VARCHAR(50),
    data_types TEXT[],
    update_frequency VARCHAR(50),
    historical_depth VARCHAR(50),
    reliability_score DECIMAL(5,4),
    latency_ms INTEGER,
    uptime_percentage DECIMAL(5,2),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    data_license VARCHAR(200),
    gdpr_compliant BOOLEAN DEFAULT FALSE,
    retention_policy VARCHAR(200),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_health_check TIMESTAMPTZ,
    last_ingestion TIMESTAMPTZ
);

-- Baseline State
CREATE TABLE fhq_meta.baseline_state (
    baseline_id SERIAL PRIMARY KEY,
    baseline_type VARCHAR(50) NOT NULL,
    baseline_name VARCHAR(200) NOT NULL,
    current_state JSONB NOT NULL,
    state_hash VARCHAR(64) NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    established_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,
    next_verification_due TIMESTAMPTZ,
    established_by VARCHAR(50) NOT NULL,
    authority VARCHAR(200),
    vega_signature TEXT
);

-- Baseline History
CREATE TABLE fhq_meta.baseline_history (
    history_id SERIAL PRIMARY KEY,
    baseline_id INTEGER NOT NULL,
    snapshot_state JSONB NOT NULL,
    snapshot_hash VARCHAR(64) NOT NULL,
    version_number INTEGER NOT NULL,
    change_type VARCHAR(50),
    change_reason TEXT,
    changes_summary JSONB,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    superseded_at TIMESTAMPTZ,
    changed_by VARCHAR(50) NOT NULL,
    previous_hash VARCHAR(64),
    history_hash VARCHAR(64) NOT NULL
);

-- Function Registry
CREATE TABLE fhq_meta.function_registry (
    function_id SERIAL PRIMARY KEY,
    function_name VARCHAR(200) NOT NULL,
    module_path VARCHAR(500) NOT NULL,
    schema_name VARCHAR(100),
    function_type VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    input_params JSONB,
    output_type VARCHAR(200),
    return_schema JSONB,
    depends_on TEXT[],
    used_by TEXT[],
    adr_compliance TEXT[],
    requires_signature BOOLEAN DEFAULT FALSE,
    vega_attestation_required BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    version VARCHAR(50) NOT NULL,
    introduced_in VARCHAR(50),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_executed_at TIMESTAMPTZ,
    execution_count BIGINT DEFAULT 0
);

-- Validation Checks
CREATE TABLE fhq_meta.validation_checks (
    check_id SERIAL PRIMARY KEY,
    check_name VARCHAR(200) NOT NULL UNIQUE,
    check_type VARCHAR(50) NOT NULL,
    check_description TEXT NOT NULL,
    check_logic TEXT NOT NULL,
    check_language VARCHAR(20),
    target_schema VARCHAR(100),
    target_table VARCHAR(100),
    target_column VARCHAR(100),
    severity VARCHAR(20) NOT NULL,
    threshold_value DECIMAL(10,4),
    threshold_operator VARCHAR(10),
    check_frequency VARCHAR(50),
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    governing_adr VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL
);

-- Validation Reports
CREATE TABLE fhq_meta.validation_reports (
    report_id BIGSERIAL PRIMARY KEY,
    report_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    check_id INTEGER NOT NULL,
    check_name VARCHAR(200) NOT NULL,
    passed BOOLEAN NOT NULL,
    result_value DECIMAL(10,4),
    result_details JSONB,
    records_checked BIGINT,
    records_passed BIGINT,
    records_failed BIGINT,
    pass_rate DECIMAL(5,4),
    failure_samples JSONB,
    failure_reasons TEXT[],
    execution_started_at TIMESTAMPTZ NOT NULL,
    execution_completed_at TIMESTAMPTZ,
    execution_duration_ms INTEGER,
    executed_by VARCHAR(50) NOT NULL,
    requires_remediation BOOLEAN DEFAULT FALSE,
    remediation_status VARCHAR(20),
    remediation_notes TEXT
);

-- ============================================================================
-- STEP 4: CREATE FHQ_GOVERNANCE TABLES
-- ============================================================================

-- Executive Roles
CREATE TABLE fhq_governance.executive_roles (
    role_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL UNIQUE,
    role_title VARCHAR(100) NOT NULL,
    role_acronym VARCHAR(10),
    primary_function TEXT NOT NULL,
    responsibilities TEXT[],
    governance_scope TEXT[],
    authority_level INTEGER NOT NULL,
    can_override TEXT[],
    requires_approval_from TEXT[],
    governing_adrs TEXT[],
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    established_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_review_at TIMESTAMPTZ
);

-- Agent Contracts
CREATE TABLE fhq_governance.agent_contracts (
    contract_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    contract_name VARCHAR(200) NOT NULL,
    contract_version VARCHAR(50) NOT NULL,
    mandate_type VARCHAR(50) NOT NULL,
    mandate_description TEXT NOT NULL,
    mandate_scope JSONB NOT NULL,
    permitted_actions TEXT[],
    prohibited_actions TEXT[],
    resource_limits JSONB,
    input_contracts TEXT[],
    output_contracts TEXT[],
    sla_requirements JSONB,
    performance_metrics JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    approved_by VARCHAR(50),
    approval_timestamp TIMESTAMPTZ,
    vega_signature TEXT,
    UNIQUE (agent_id, contract_name, contract_version)
);

-- Authority Matrix
CREATE TABLE fhq_governance.authority_matrix (
    authority_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    permission VARCHAR(20) NOT NULL,
    conditions JSONB,
    resource_scope VARCHAR(200),
    can_be_overridden_by TEXT[],
    override_conditions JSONB,
    governing_adr VARCHAR(20),
    established_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    established_by VARCHAR(50) NOT NULL
);

-- Gate Registry
CREATE TABLE fhq_governance.gate_registry (
    gate_id SERIAL PRIMARY KEY,
    gate_number INTEGER NOT NULL UNIQUE,
    gate_name VARCHAR(100) NOT NULL,
    gate_description TEXT NOT NULL,
    entry_criteria JSONB NOT NULL,
    exit_criteria JSONB NOT NULL,
    required_approvers TEXT[],
    required_artifacts TEXT[],
    governing_adrs TEXT[],
    compliance_checks JSONB,
    minimum_duration INTERVAL,
    maximum_duration INTERVAL,
    defined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ
);

-- Gate Status
CREATE TABLE fhq_governance.gate_status (
    status_id SERIAL PRIMARY KEY,
    gate_id INTEGER NOT NULL,
    component_id VARCHAR(100) NOT NULL,
    component_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    entry_timestamp TIMESTAMPTZ,
    exit_timestamp TIMESTAMPTZ,
    time_in_gate INTERVAL,
    evidence_collected JSONB,
    artifacts_submitted TEXT[],
    approvers_signed TEXT[],
    pending_approvers TEXT[],
    notes TEXT,
    blocking_issues TEXT[],
    vega_signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE (gate_id, component_id)
);

-- ============================================================================
-- STEP 5: CREATE FHQ_MONITORING TABLES
-- ============================================================================

-- Ingestion Log
CREATE TABLE fhq_monitoring.ingestion_log (
    ingestion_id BIGSERIAL PRIMARY KEY,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_id INTEGER,
    source_name VARCHAR(100) NOT NULL,
    target_schema VARCHAR(100) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    records_fetched INTEGER NOT NULL DEFAULT 0,
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    data_quality_score DECIMAL(5,4),
    validation_passed BOOLEAN DEFAULT TRUE,
    validation_errors JSONB,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    executed_by VARCHAR(50) NOT NULL,
    ingestion_hash VARCHAR(64)
);

-- Execution Log
CREATE TABLE fhq_monitoring.execution_log (
    execution_id BIGSERIAL PRIMARY KEY,
    execution_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id VARCHAR(50) NOT NULL,
    agent_version VARCHAR(50),
    operation_type VARCHAR(100) NOT NULL,
    operation_name VARCHAR(200) NOT NULL,
    operation_params JSONB,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status VARCHAR(20) NOT NULL,
    error_code VARCHAR(50),
    error_message TEXT,
    stack_trace TEXT,
    llm_calls INTEGER DEFAULT 0,
    llm_cost_usd DECIMAL(10,6) DEFAULT 0.0,
    memory_used_mb INTEGER,
    cpu_time_ms INTEGER,
    result_summary JSONB,
    output_artifacts TEXT[],
    adr_compliance TEXT[],
    vega_attestation_required BOOLEAN DEFAULT FALSE,
    execution_hash VARCHAR(64),
    agent_signature TEXT
);

-- ============================================================================
-- STEP 6: CREATE FHQ_DATA TABLES
-- ============================================================================

-- Price Series
CREATE TABLE fhq_data.price_series (
    price_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,8) NOT NULL,
    vwap DECIMAL(20,8),
    trade_count INTEGER,
    taker_buy_volume DECIMAL(20,8),
    source_id INTEGER,
    source_name VARCHAR(100),
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    quality_score DECIMAL(5,4),
    quality_flags JSONB,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_by VARCHAR(50) DEFAULT 'LINE',
    UNIQUE (timestamp, symbol, interval)
);

CREATE INDEX idx_price_series_symbol ON fhq_data.price_series(symbol, timestamp DESC);

-- ============================================================================
-- STEP 7: CREATE VEGA SCHEMA TABLES
-- ============================================================================

-- LLM Usage Log
CREATE TABLE vega.llm_usage_log (
    usage_id BIGSERIAL PRIMARY KEY,
    usage_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id VARCHAR(50) NOT NULL,
    agent_version VARCHAR(50),
    operation_type VARCHAR(100) NOT NULL,
    operation_id VARCHAR(100),
    cycle_id VARCHAR(100),
    llm_provider VARCHAR(50) NOT NULL DEFAULT 'anthropic',
    llm_model VARCHAR(100) NOT NULL,
    llm_model_version VARCHAR(50),
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    input_cost_usd DECIMAL(10,6) NOT NULL DEFAULT 0.0,
    output_cost_usd DECIMAL(10,6) NOT NULL DEFAULT 0.0,
    total_cost_usd DECIMAL(10,6) GENERATED ALWAYS AS (input_cost_usd + output_cost_usd) STORED,
    cost_per_1k_input DECIMAL(10,6),
    cost_per_1k_output DECIMAL(10,6),
    request_id VARCHAR(100),
    latency_ms INTEGER,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_code VARCHAR(50),
    error_message TEXT,
    daily_budget_remaining DECIMAL(10,2),
    daily_calls_remaining INTEGER,
    within_ceiling BOOLEAN NOT NULL DEFAULT TRUE,
    ceiling_value DECIMAL(10,6) DEFAULT 0.050,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_llm_usage_timestamp ON vega.llm_usage_log(usage_timestamp DESC);
CREATE INDEX idx_llm_usage_agent ON vega.llm_usage_log(agent_id);

-- Cost Tracking
CREATE TABLE vega.cost_tracking (
    tracking_id BIGSERIAL PRIMARY KEY,
    tracking_date DATE NOT NULL,
    tracking_hour INTEGER,
    aggregation_level VARCHAR(20) NOT NULL,
    agent_id VARCHAR(50),
    total_calls INTEGER NOT NULL DEFAULT 0,
    successful_calls INTEGER NOT NULL DEFAULT 0,
    failed_calls INTEGER NOT NULL DEFAULT 0,
    total_input_tokens BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    total_cost_usd DECIMAL(12,6) NOT NULL DEFAULT 0.0,
    avg_cost_per_call DECIMAL(10,6),
    max_single_call_cost DECIMAL(10,6),
    min_single_call_cost DECIMAL(10,6),
    budget_used_pct DECIMAL(5,2),
    budget_remaining_usd DECIMAL(12,6),
    rate_limit_hits INTEGER DEFAULT 0,
    ceiling_violations INTEGER DEFAULT 0,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Rate Limits
CREATE TABLE vega.rate_limits (
    limit_id SERIAL PRIMARY KEY,
    limit_name VARCHAR(100) NOT NULL UNIQUE,
    limit_type VARCHAR(50) NOT NULL,
    scope_type VARCHAR(50) NOT NULL,
    scope_value VARCHAR(100),
    limit_value DECIMAL(12,4) NOT NULL,
    warning_threshold DECIMAL(12,4),
    hard_limit DECIMAL(12,4),
    enforcement_action VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    governing_adr VARCHAR(20) DEFAULT 'ADR-012',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Budget Allocations
CREATE TABLE vega.budget_allocations (
    allocation_id SERIAL PRIMARY KEY,
    budget_period VARCHAR(20) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    scope_type VARCHAR(50) NOT NULL,
    scope_value VARCHAR(100),
    allocated_budget_usd DECIMAL(12,2) NOT NULL,
    used_budget_usd DECIMAL(12,6) NOT NULL DEFAULT 0.0,
    remaining_budget_usd DECIMAL(12,6) GENERATED ALWAYS AS (allocated_budget_usd - used_budget_usd) STORED,
    utilization_pct DECIMAL(5,2) GENERATED ALWAYS AS (CASE WHEN allocated_budget_usd > 0 THEN (used_budget_usd / allocated_budget_usd * 100) ELSE 0 END) STORED,
    alert_threshold_pct DECIMAL(5,2) DEFAULT 80.0,
    alert_triggered BOOLEAN DEFAULT FALSE,
    alert_triggered_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Cost Alerts
CREATE TABLE vega.cost_alerts (
    alert_id BIGSERIAL PRIMARY KEY,
    alert_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    agent_id VARCHAR(50),
    operation_type VARCHAR(100),
    cycle_id VARCHAR(100),
    alert_message TEXT NOT NULL,
    alert_data JSONB NOT NULL DEFAULT '{}',
    threshold_type VARCHAR(50),
    threshold_value DECIMAL(12,6),
    actual_value DECIMAL(12,6),
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(50),
    acknowledged_at TIMESTAMPTZ,
    resolution_notes TEXT,
    escalated BOOLEAN DEFAULT FALSE,
    escalated_to VARCHAR(50),
    escalated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- STEP 8: SEED DATA
-- ============================================================================

-- Executive Roles
INSERT INTO fhq_governance.executive_roles (agent_id, role_title, role_acronym, primary_function, responsibilities, authority_level, governing_adrs, status) VALUES
    ('LARS', 'Chief Strategy Officer', 'CSO', 'Strategic direction and governance oversight', ARRAY['System strategy', 'ADR governance'], 9, ARRAY['ADR-001', 'ADR-004'], 'ACTIVE'),
    ('STIG', 'Chief Technology Officer', 'CTO', 'Technical validation and compliance', ARRAY['Code review', 'Validation'], 8, ARRAY['ADR-008', 'ADR-010'], 'ACTIVE'),
    ('VEGA', 'Chief Audit Officer', 'CAO', 'Autonomous constitutional governance', ARRAY['Model certification', 'Audit'], 10, ARRAY['ADR-006'], 'ACTIVE'),
    ('LINE', 'Chief Data Officer', 'CDO', 'Data ingestion and pipeline management', ARRAY['Data ingestion', 'Quality'], 7, ARRAY['ADR-002', 'ADR-011'], 'ACTIVE'),
    ('FINN', 'Chief Analytics Officer', 'CAnO', 'Market analysis and regime classification', ARRAY['Regime classification', 'Signals'], 7, ARRAY['ADR-007', 'ADR-009'], 'ACTIVE'),
    ('CODE', 'Chief Engineering Officer', 'CEO', 'Code generation and implementation', ARRAY['Code generation', 'Implementation'], 6, ARRAY['ADR-003'], 'ACTIVE'),
    ('CEO', 'Chief Executive Officer', 'CEO', 'Ultimate authority', ARRAY['Constitutional exceptions', 'Final approvals'], 10, ARRAY['ADR-001'], 'ACTIVE')
ON CONFLICT (agent_id) DO NOTHING;

-- Gate Registry
INSERT INTO fhq_governance.gate_registry (gate_number, gate_name, gate_description, entry_criteria, exit_criteria, required_approvers, governing_adrs) VALUES
    (0, 'G0: Initialization', 'System initialization', '{"checks": ["schema_exists"]}'::JSONB, '{"checks": ["baseline_established"]}'::JSONB, ARRAY['LARS'], ARRAY['ADR-001']),
    (1, 'G1: Development', 'Development phase', '{"checks": ["g0_passed"]}'::JSONB, '{"checks": ["tests_pass"]}'::JSONB, ARRAY['STIG'], ARRAY['ADR-003']),
    (2, 'G2: Validation', 'Validation phase', '{"checks": ["g1_passed"]}'::JSONB, '{"checks": ["vega_audit_pass"]}'::JSONB, ARRAY['STIG', 'VEGA'], ARRAY['ADR-008']),
    (3, 'G3: Staging', 'Pre-production staging', '{"checks": ["g2_passed"]}'::JSONB, '{"checks": ["gold_baseline"]}'::JSONB, ARRAY['LARS', 'VEGA'], ARRAY['ADR-006']),
    (4, 'G4: Production', 'Production deployment', '{"checks": ["g3_passed"]}'::JSONB, '{"checks": ["monitoring_active"]}'::JSONB, ARRAY['LARS', 'CEO'], ARRAY['ADR-006'])
ON CONFLICT (gate_number) DO NOTHING;

-- Data Sources
INSERT INTO fhq_meta.data_source_registry (source_name, source_type, api_endpoint, data_types, update_frequency, status) VALUES
    ('Binance', 'EXCHANGE', 'https://api.binance.com', ARRAY['OHLCV', 'TRADES'], 'REALTIME', 'ACTIVE'),
    ('Alpaca', 'BROKER', 'https://api.alpaca.markets', ARRAY['OHLCV', 'TRADES'], 'REALTIME', 'ACTIVE'),
    ('Yahoo Finance', 'DATA_VENDOR', 'https://query1.finance.yahoo.com', ARRAY['OHLCV'], 'DAILY', 'ACTIVE'),
    ('FRED', 'GOVERNMENT', 'https://api.stlouisfed.org', ARRAY['FUNDAMENTALS'], 'DAILY', 'ACTIVE')
ON CONFLICT (source_name) DO NOTHING;

-- Agent Keys
INSERT INTO fhq_meta.agent_keys (agent_id, key_type, public_key_hex, public_key_fingerprint, key_purpose, status) VALUES
    ('LARS', 'Ed25519', encode(sha256('LARS-KEY'::bytea), 'hex'), encode(sha256('LARS-FP'::bytea), 'hex'), 'signing', 'ACTIVE'),
    ('STIG', 'Ed25519', encode(sha256('STIG-KEY'::bytea), 'hex'), encode(sha256('STIG-FP'::bytea), 'hex'), 'signing', 'ACTIVE'),
    ('VEGA', 'Ed25519', encode(sha256('VEGA-KEY'::bytea), 'hex'), encode(sha256('VEGA-FP'::bytea), 'hex'), 'signing', 'ACTIVE'),
    ('LINE', 'Ed25519', encode(sha256('LINE-KEY'::bytea), 'hex'), encode(sha256('LINE-FP'::bytea), 'hex'), 'signing', 'ACTIVE'),
    ('FINN', 'Ed25519', encode(sha256('FINN-KEY'::bytea), 'hex'), encode(sha256('FINN-FP'::bytea), 'hex'), 'signing', 'ACTIVE'),
    ('CODE', 'Ed25519', encode(sha256('CODE-KEY'::bytea), 'hex'), encode(sha256('CODE-FP'::bytea), 'hex'), 'signing', 'ACTIVE'),
    ('CEO', 'Ed25519', encode(sha256('CEO-KEY'::bytea), 'hex'), encode(sha256('CEO-FP'::bytea), 'hex'), 'signing', 'ACTIVE');

-- ADR Registry
INSERT INTO fhq_meta.adr_registry (adr_number, title, version, status, phase, content_hash, owner, approved_by, classification) VALUES
    ('ADR-001', 'FjordHQ System Charter', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-001'::bytea), 'hex'), 'LARS', 'CEO', 'Constitutional'),
    ('ADR-002', 'Audit & Error Reconciliation', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-002'::bytea), 'hex'), 'LARS', 'CEO', 'Constitutional'),
    ('ADR-003', 'Institutional Standards', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-003'::bytea), 'hex'), 'CODE', 'LARS', 'Technical'),
    ('ADR-004', 'Change Gates', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-004'::bytea), 'hex'), 'LARS', 'CEO', 'Constitutional'),
    ('ADR-005', 'Mission & Vision', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-005'::bytea), 'hex'), 'LARS', 'CEO', 'Constitutional'),
    ('ADR-006', 'VEGA Charter', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-006'::bytea), 'hex'), 'LARS', 'CEO', 'Constitutional'),
    ('ADR-007', 'FINN Analysis', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-007'::bytea), 'hex'), 'FINN', 'LARS', 'Operational'),
    ('ADR-008', 'Ed25519 Signatures', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-008'::bytea), 'hex'), 'STIG', 'LARS', 'Technical'),
    ('ADR-009', 'Determinism', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-009'::bytea), 'hex'), 'VEGA', 'LARS', 'Technical'),
    ('ADR-010', 'Reconciliation Protocol', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-010'::bytea), 'hex'), 'STIG', 'LARS', 'Operational'),
    ('ADR-011', 'Data Lineage', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-011'::bytea), 'hex'), 'LINE', 'LARS', 'Technical'),
    ('ADR-012', 'Economic Safety', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-012'::bytea), 'hex'), 'LARS', 'CEO', 'Operational'),
    ('ADR-013', 'DORA Compliance', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-013'::bytea), 'hex'), 'VEGA', 'LARS', 'Constitutional'),
    ('ADR-014', 'ADR Governance', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-014'::bytea), 'hex'), 'LARS', 'CEO', 'Constitutional'),
    ('ADR-015', 'Meta-Governance', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL', encode(sha256('ADR-015'::bytea), 'hex'), 'LARS', 'CEO', 'Constitutional')
ON CONFLICT (adr_number) DO NOTHING;

-- Rate Limits (ADR-012)
INSERT INTO vega.rate_limits (limit_name, limit_type, scope_type, limit_value, warning_threshold, hard_limit, enforcement_action) VALUES
    ('system_daily_budget', 'COST_PER_DAY', 'SYSTEM', 500.00, 400.00, 500.00, 'BLOCK'),
    ('system_daily_calls', 'CALLS_PER_DAY', 'SYSTEM', 100, 80, 100, 'BLOCK'),
    ('per_summary_ceiling', 'COST_PER_CALL', 'OPERATION', 0.050, 0.040, 0.050, 'BLOCK')
ON CONFLICT (limit_name) DO NOTHING;

-- Budget Allocation
INSERT INTO vega.budget_allocations (budget_period, period_start, period_end, scope_type, allocated_budget_usd) VALUES
    ('DAILY', CURRENT_DATE, CURRENT_DATE, 'SYSTEM', 500.00);

-- ============================================================================
-- STEP 9: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_adr_count INTEGER;
    v_role_count INTEGER;
    v_key_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_adr_count FROM fhq_meta.adr_registry;
    SELECT COUNT(*) INTO v_role_count FROM fhq_governance.executive_roles;
    SELECT COUNT(*) INTO v_key_count FROM fhq_meta.agent_keys;

    RAISE NOTICE '====================================================';
    RAISE NOTICE 'VEGA CONSOLIDATED INSTALLATION COMPLETE';
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Database: 127.0.0.1:54322';
    RAISE NOTICE 'ADRs registered: %', v_adr_count;
    RAISE NOTICE 'Executive roles: %', v_role_count;
    RAISE NOTICE 'Agent keys: %', v_key_count;
    RAISE NOTICE '====================================================';
END $$;

-- ============================================================================
-- MIGRATION 022 COMPLETE
-- ============================================================================
