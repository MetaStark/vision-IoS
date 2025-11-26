-- ============================================================================
-- FOUNDATION SCHEMA - VISION-IOS & FJORDHQ
-- ============================================================================
-- Migration: 019_foundation_schema.sql
-- Authority: ADR-001_2026_PRODUCTION (System Charter)
-- Database: 127.0.0.1:54322 (Local Supabase PostgreSQL)
--
-- PURPOSE:
-- Creates all missing foundation tables required for full system activation.
-- This migration completes the database structure per ADR-001 → ADR-015.
--
-- SCHEMAS CREATED/USED:
-- - fhq_meta: Metadata, registry, keys, lineage
-- - fhq_governance: Roles, contracts, authority, gates
-- - fhq_monitoring: Ingestion, execution logging
-- - fhq_data: Price series, data sources
--
-- TABLES CREATED (16):
-- A. fhq_meta: adr_registry, agent_keys, key_archival_log, data_source_registry,
--              baseline_state, baseline_history
-- B. fhq_governance: executive_roles, agent_contracts, authority_matrix,
--                    gate_registry, gate_status
-- C. fhq_monitoring: ingestion_log, execution_log
-- D. fhq_data: price_series
-- E. fhq_meta: function_registry, validation_checks, validation_reports
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 0: CREATE SCHEMAS IF NOT EXISTS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_meta;
CREATE SCHEMA IF NOT EXISTS fhq_governance;
CREATE SCHEMA IF NOT EXISTS fhq_monitoring;
CREATE SCHEMA IF NOT EXISTS fhq_data;

-- ============================================================================
-- SECTION A: FHQ_META FOUNDATION TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- A.1: ADR Registry - Constitutional document tracking
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.adr_registry (
    adr_id SERIAL PRIMARY KEY,
    adr_number VARCHAR(20) NOT NULL UNIQUE,  -- e.g., 'ADR-001'
    title VARCHAR(500) NOT NULL,
    version VARCHAR(50) NOT NULL,  -- e.g., '2026.PRODUCTION'
    status VARCHAR(50) NOT NULL CHECK (
        status IN ('DRAFT', 'REVIEW', 'APPROVED', 'CANONICAL', 'SUPERSEDED', 'DEPRECATED')
    ),
    phase VARCHAR(50) CHECK (
        phase IN ('DRAFT', 'STAGING', 'PRODUCTION', 'CANONICAL')
    ),

    -- Content integrity
    content_hash VARCHAR(64) NOT NULL,
    file_path VARCHAR(500),

    -- Ownership
    owner VARCHAR(100) NOT NULL,
    approved_by VARCHAR(100),
    effective_date DATE,

    -- Relationships
    supersedes VARCHAR(500),
    dependencies TEXT[],  -- Array of ADR numbers this depends on

    -- Classification
    classification VARCHAR(50) CHECK (
        classification IN ('Constitutional', 'Operational', 'Technical', 'Process')
    ),

    -- Audit
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    last_verified_at TIMESTAMPTZ,

    -- VEGA attestation
    vega_signature TEXT,
    signature_verified BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_adr_registry_number ON fhq_meta.adr_registry(adr_number);
CREATE INDEX IF NOT EXISTS idx_adr_registry_status ON fhq_meta.adr_registry(status);

COMMENT ON TABLE fhq_meta.adr_registry IS
    'ADR-001: Constitutional ADR document registry (ADR-001 → ADR-015)';

-- ----------------------------------------------------------------------------
-- A.2: Agent Keys - Ed25519 cryptographic key storage
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.agent_keys (
    key_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,  -- LARS, STIG, VEGA, LINE, FINN, CODE, CEO
    key_type VARCHAR(20) NOT NULL CHECK (key_type IN ('Ed25519', 'RSA', 'ECDSA')),

    -- Key material (public only - private keys stored securely elsewhere)
    public_key_hex TEXT NOT NULL,
    public_key_fingerprint VARCHAR(64) NOT NULL,

    -- Key metadata
    key_purpose VARCHAR(100) NOT NULL,  -- 'signing', 'verification', 'encryption'
    algorithm_params JSONB DEFAULT '{}',

    -- Lifecycle
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('ACTIVE', 'ROTATED', 'REVOKED', 'EXPIRED')
    ) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    rotated_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revocation_reason TEXT,

    -- Key rotation
    previous_key_id INTEGER REFERENCES fhq_meta.agent_keys(key_id),
    rotation_count INTEGER DEFAULT 0,

    -- Audit
    registered_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',

    CONSTRAINT unique_active_agent_key UNIQUE (agent_id, key_purpose, status)
);

CREATE INDEX IF NOT EXISTS idx_agent_keys_agent ON fhq_meta.agent_keys(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_keys_status ON fhq_meta.agent_keys(status);
CREATE INDEX IF NOT EXISTS idx_agent_keys_fingerprint ON fhq_meta.agent_keys(public_key_fingerprint);

COMMENT ON TABLE fhq_meta.agent_keys IS
    'ADR-008: Ed25519 public key storage for all agents (7 agents)';

-- ----------------------------------------------------------------------------
-- A.3: Key Archival Log - Key rotation and lifecycle tracking
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.key_archival_log (
    archive_id SERIAL PRIMARY KEY,
    key_id INTEGER NOT NULL REFERENCES fhq_meta.agent_keys(key_id),
    agent_id VARCHAR(50) NOT NULL,

    -- Event
    event_type VARCHAR(50) NOT NULL CHECK (
        event_type IN ('CREATED', 'ROTATED', 'REVOKED', 'EXPIRED', 'ARCHIVED')
    ),
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Key state at event
    public_key_fingerprint VARCHAR(64) NOT NULL,
    previous_fingerprint VARCHAR(64),

    -- Reason
    event_reason TEXT,

    -- Cryptographic proof
    event_hash VARCHAR(64) NOT NULL,
    vega_signature TEXT,

    -- Audit
    recorded_by VARCHAR(50) NOT NULL DEFAULT 'VEGA'
);

CREATE INDEX IF NOT EXISTS idx_key_archival_agent ON fhq_meta.key_archival_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_key_archival_key ON fhq_meta.key_archival_log(key_id);
CREATE INDEX IF NOT EXISTS idx_key_archival_timestamp ON fhq_meta.key_archival_log(event_timestamp DESC);

COMMENT ON TABLE fhq_meta.key_archival_log IS
    'ADR-008: Key lifecycle and rotation audit trail';

-- ----------------------------------------------------------------------------
-- A.4: Data Source Registry - External data source tracking
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.data_source_registry (
    source_id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL UNIQUE,  -- Binance, Alpaca, Yahoo, FRED
    source_type VARCHAR(50) NOT NULL CHECK (
        source_type IN ('EXCHANGE', 'BROKER', 'DATA_VENDOR', 'GOVERNMENT', 'INTERNAL')
    ),

    -- Connection
    api_endpoint VARCHAR(500),
    api_version VARCHAR(50),
    auth_type VARCHAR(50) CHECK (
        auth_type IN ('API_KEY', 'OAUTH', 'BASIC', 'NONE')
    ),

    -- Data characteristics
    data_types TEXT[],  -- ['OHLCV', 'ORDERBOOK', 'TRADES', 'FUNDAMENTALS']
    update_frequency VARCHAR(50),  -- 'REALTIME', 'MINUTE', 'HOURLY', 'DAILY'
    historical_depth VARCHAR(50),  -- '5Y', '10Y', 'ALL'

    -- Quality
    reliability_score DECIMAL(5,4),
    latency_ms INTEGER,
    uptime_percentage DECIMAL(5,2),

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('ACTIVE', 'INACTIVE', 'DEPRECATED', 'TESTING')
    ) DEFAULT 'ACTIVE',

    -- Compliance
    data_license VARCHAR(200),
    gdpr_compliant BOOLEAN DEFAULT FALSE,
    retention_policy VARCHAR(200),

    -- Audit
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_health_check TIMESTAMPTZ,
    last_ingestion TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_data_source_name ON fhq_meta.data_source_registry(source_name);
CREATE INDEX IF NOT EXISTS idx_data_source_status ON fhq_meta.data_source_registry(status);

COMMENT ON TABLE fhq_meta.data_source_registry IS
    'ADR-002: External data source registry (Binance, Alpaca, Yahoo, FRED)';

-- ----------------------------------------------------------------------------
-- A.5: Baseline State - Current reconciliation baseline
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.baseline_state (
    baseline_id SERIAL PRIMARY KEY,
    baseline_type VARCHAR(50) NOT NULL,  -- 'GOVERNANCE', 'DATA', 'MODEL', 'SYSTEM'
    baseline_name VARCHAR(200) NOT NULL,

    -- State
    current_state JSONB NOT NULL,
    state_hash VARCHAR(64) NOT NULL,

    -- Version
    version_number INTEGER NOT NULL DEFAULT 1,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,

    -- Timestamps
    established_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,
    next_verification_due TIMESTAMPTZ,

    -- Authority
    established_by VARCHAR(50) NOT NULL,
    authority VARCHAR(200),

    -- VEGA attestation
    vega_signature TEXT,

    CONSTRAINT unique_current_baseline UNIQUE (baseline_type, baseline_name, is_current)
);

CREATE INDEX IF NOT EXISTS idx_baseline_type ON fhq_meta.baseline_state(baseline_type);
CREATE INDEX IF NOT EXISTS idx_baseline_current ON fhq_meta.baseline_state(is_current) WHERE is_current = TRUE;

COMMENT ON TABLE fhq_meta.baseline_state IS
    'ADR-010: Reconciliation baseline state tracking';

-- ----------------------------------------------------------------------------
-- A.6: Baseline History - Historical baseline snapshots
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.baseline_history (
    history_id SERIAL PRIMARY KEY,
    baseline_id INTEGER NOT NULL REFERENCES fhq_meta.baseline_state(baseline_id),

    -- Snapshot
    snapshot_state JSONB NOT NULL,
    snapshot_hash VARCHAR(64) NOT NULL,
    version_number INTEGER NOT NULL,

    -- Change tracking
    change_type VARCHAR(50) CHECK (
        change_type IN ('INITIAL', 'UPDATE', 'CORRECTION', 'ROLLBACK')
    ),
    change_reason TEXT,
    changes_summary JSONB,

    -- Timestamps
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    superseded_at TIMESTAMPTZ,

    -- Authority
    changed_by VARCHAR(50) NOT NULL,

    -- Hash chain
    previous_hash VARCHAR(64),
    history_hash VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_baseline_history_baseline ON fhq_meta.baseline_history(baseline_id);
CREATE INDEX IF NOT EXISTS idx_baseline_history_timestamp ON fhq_meta.baseline_history(snapshot_at DESC);

COMMENT ON TABLE fhq_meta.baseline_history IS
    'ADR-010: Historical baseline snapshots for reconciliation';

-- ============================================================================
-- SECTION B: FHQ_GOVERNANCE TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- B.1: Executive Roles - Agent role definitions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_governance.executive_roles (
    role_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL UNIQUE,  -- LARS, STIG, VEGA, LINE, FINN, CODE, CEO
    role_title VARCHAR(100) NOT NULL,
    role_acronym VARCHAR(10),

    -- Responsibilities
    primary_function TEXT NOT NULL,
    responsibilities TEXT[],
    governance_scope TEXT[],

    -- Authority
    authority_level INTEGER NOT NULL CHECK (authority_level BETWEEN 1 AND 10),
    can_override TEXT[],  -- Array of agent_ids this role can override
    requires_approval_from TEXT[],  -- Array of agent_ids required for approval

    -- ADR compliance
    governing_adrs TEXT[],  -- ADRs that define this role

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')
    ) DEFAULT 'ACTIVE',

    -- Audit
    established_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_review_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_exec_roles_agent ON fhq_governance.executive_roles(agent_id);
CREATE INDEX IF NOT EXISTS idx_exec_roles_status ON fhq_governance.executive_roles(status);

COMMENT ON TABLE fhq_governance.executive_roles IS
    'ADR-001: Executive agent role definitions (7 agents)';

-- ----------------------------------------------------------------------------
-- B.2: Agent Contracts - Operational mandates
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_governance.agent_contracts (
    contract_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    contract_name VARCHAR(200) NOT NULL,
    contract_version VARCHAR(50) NOT NULL,

    -- Mandate
    mandate_type VARCHAR(50) NOT NULL CHECK (
        mandate_type IN ('OPERATIONAL', 'GOVERNANCE', 'COMPLIANCE', 'DATA', 'EXECUTION')
    ),
    mandate_description TEXT NOT NULL,
    mandate_scope JSONB NOT NULL,

    -- Boundaries
    permitted_actions TEXT[],
    prohibited_actions TEXT[],
    resource_limits JSONB,

    -- Dependencies
    input_contracts TEXT[],  -- Contract IDs this depends on
    output_contracts TEXT[],  -- Contract IDs that depend on this

    -- SLA
    sla_requirements JSONB,
    performance_metrics JSONB,

    -- Lifecycle
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('DRAFT', 'ACTIVE', 'SUSPENDED', 'TERMINATED')
    ) DEFAULT 'ACTIVE',
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,

    -- Authority
    approved_by VARCHAR(50),
    approval_timestamp TIMESTAMPTZ,

    -- VEGA attestation
    vega_signature TEXT,

    CONSTRAINT unique_agent_contract UNIQUE (agent_id, contract_name, contract_version)
);

CREATE INDEX IF NOT EXISTS idx_agent_contracts_agent ON fhq_governance.agent_contracts(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_contracts_status ON fhq_governance.agent_contracts(status);

COMMENT ON TABLE fhq_governance.agent_contracts IS
    'ADR-001: Agent operational mandates and contracts';

-- ----------------------------------------------------------------------------
-- B.3: Authority Matrix - Permission mappings
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_governance.authority_matrix (
    authority_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,

    -- Permission
    permission VARCHAR(20) NOT NULL CHECK (
        permission IN ('ALLOW', 'DENY', 'REQUIRE_APPROVAL', 'CONDITIONAL')
    ),
    conditions JSONB,  -- Conditions for CONDITIONAL permission

    -- Scope
    resource_scope VARCHAR(200),  -- e.g., 'fhq_meta.*', 'fhq_governance.agent_contracts'

    -- Override rules
    can_be_overridden_by TEXT[],
    override_conditions JSONB,

    -- ADR reference
    governing_adr VARCHAR(20),

    -- Audit
    established_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    established_by VARCHAR(50) NOT NULL,

    CONSTRAINT unique_authority_entry UNIQUE (agent_id, action_type, resource_type, resource_scope)
);

CREATE INDEX IF NOT EXISTS idx_authority_agent ON fhq_governance.authority_matrix(agent_id);
CREATE INDEX IF NOT EXISTS idx_authority_action ON fhq_governance.authority_matrix(action_type);
CREATE INDEX IF NOT EXISTS idx_authority_permission ON fhq_governance.authority_matrix(permission);

COMMENT ON TABLE fhq_governance.authority_matrix IS
    'ADR-001: Agent authority and permission matrix';

-- ----------------------------------------------------------------------------
-- B.4: Gate Registry - G0 → G4 gate definitions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_governance.gate_registry (
    gate_id SERIAL PRIMARY KEY,
    gate_number INTEGER NOT NULL UNIQUE CHECK (gate_number BETWEEN 0 AND 4),
    gate_name VARCHAR(100) NOT NULL,
    gate_description TEXT NOT NULL,

    -- Requirements
    entry_criteria JSONB NOT NULL,
    exit_criteria JSONB NOT NULL,
    required_approvers TEXT[],
    required_artifacts TEXT[],

    -- Governance
    governing_adrs TEXT[],
    compliance_checks JSONB,

    -- Timing
    minimum_duration INTERVAL,
    maximum_duration INTERVAL,

    -- Audit
    defined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ
);

COMMENT ON TABLE fhq_governance.gate_registry IS
    'ADR-004: Production gate definitions (G0 → G4)';

-- ----------------------------------------------------------------------------
-- B.5: Gate Status - Current gate positions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_governance.gate_status (
    status_id SERIAL PRIMARY KEY,
    gate_id INTEGER NOT NULL REFERENCES fhq_governance.gate_registry(gate_id),
    component_id VARCHAR(100) NOT NULL,  -- System component being gated
    component_type VARCHAR(50) NOT NULL,

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('PENDING', 'IN_PROGRESS', 'PASSED', 'FAILED', 'BLOCKED', 'BYPASSED')
    ),

    -- Progress
    entry_timestamp TIMESTAMPTZ,
    exit_timestamp TIMESTAMPTZ,
    time_in_gate INTERVAL,

    -- Evidence
    evidence_collected JSONB,
    artifacts_submitted TEXT[],

    -- Approval
    approvers_signed TEXT[],
    pending_approvers TEXT[],

    -- Notes
    notes TEXT,
    blocking_issues TEXT[],

    -- VEGA attestation
    vega_signature TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,

    CONSTRAINT unique_component_gate UNIQUE (gate_id, component_id)
);

CREATE INDEX IF NOT EXISTS idx_gate_status_gate ON fhq_governance.gate_status(gate_id);
CREATE INDEX IF NOT EXISTS idx_gate_status_component ON fhq_governance.gate_status(component_id);
CREATE INDEX IF NOT EXISTS idx_gate_status_status ON fhq_governance.gate_status(status);

COMMENT ON TABLE fhq_governance.gate_status IS
    'ADR-004: Current gate status for system components';

-- ============================================================================
-- SECTION C: FHQ_MONITORING TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- C.1: Ingestion Log - Data ingestion tracking
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_monitoring.ingestion_log (
    ingestion_id BIGSERIAL PRIMARY KEY,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Source
    source_id INTEGER REFERENCES fhq_meta.data_source_registry(source_id),
    source_name VARCHAR(100) NOT NULL,

    -- Target
    target_schema VARCHAR(100) NOT NULL,
    target_table VARCHAR(100) NOT NULL,

    -- Metrics
    records_fetched INTEGER NOT NULL DEFAULT 0,
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,

    -- Quality
    data_quality_score DECIMAL(5,4),
    validation_passed BOOLEAN DEFAULT TRUE,
    validation_errors JSONB,

    -- Timing
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('RUNNING', 'COMPLETED', 'FAILED', 'PARTIAL')
    ),
    error_message TEXT,

    -- Agent
    executed_by VARCHAR(50) NOT NULL,  -- LINE, FINN, etc.

    -- Hash for integrity
    ingestion_hash VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_timestamp ON fhq_monitoring.ingestion_log(ingestion_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_source ON fhq_monitoring.ingestion_log(source_name);
CREATE INDEX IF NOT EXISTS idx_ingestion_status ON fhq_monitoring.ingestion_log(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_agent ON fhq_monitoring.ingestion_log(executed_by);

COMMENT ON TABLE fhq_monitoring.ingestion_log IS
    'ADR-002: Data ingestion audit log';

-- ----------------------------------------------------------------------------
-- C.2: Execution Log - Agent execution tracking
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_monitoring.execution_log (
    execution_id BIGSERIAL PRIMARY KEY,
    execution_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Agent
    agent_id VARCHAR(50) NOT NULL,
    agent_version VARCHAR(50),

    -- Operation
    operation_type VARCHAR(100) NOT NULL,
    operation_name VARCHAR(200) NOT NULL,
    operation_params JSONB,

    -- Execution
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('RUNNING', 'COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED')
    ),
    error_code VARCHAR(50),
    error_message TEXT,
    stack_trace TEXT,

    -- Resources (ADR-012)
    llm_calls INTEGER DEFAULT 0,
    llm_cost_usd DECIMAL(10,6) DEFAULT 0.0,
    memory_used_mb INTEGER,
    cpu_time_ms INTEGER,

    -- Result
    result_summary JSONB,
    output_artifacts TEXT[],

    -- Governance
    adr_compliance TEXT[],
    vega_attestation_required BOOLEAN DEFAULT FALSE,

    -- Hash for integrity
    execution_hash VARCHAR(64),

    -- Signature
    agent_signature TEXT
);

CREATE INDEX IF NOT EXISTS idx_execution_timestamp ON fhq_monitoring.execution_log(execution_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_execution_agent ON fhq_monitoring.execution_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_execution_status ON fhq_monitoring.execution_log(status);
CREATE INDEX IF NOT EXISTS idx_execution_operation ON fhq_monitoring.execution_log(operation_type);

COMMENT ON TABLE fhq_monitoring.execution_log IS
    'ADR-002: Agent execution audit log with cost tracking';

-- ============================================================================
-- SECTION D: FHQ_DATA TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- D.1: Price Series - Core market data
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_data.price_series (
    price_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL CHECK (interval IN ('1m', '5m', '15m', '1h', '4h', '1d', '1w')),

    -- OHLCV
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,8) NOT NULL,

    -- Additional metrics
    vwap DECIMAL(20,8),
    trade_count INTEGER,
    taker_buy_volume DECIMAL(20,8),

    -- Source
    source_id INTEGER REFERENCES fhq_meta.data_source_registry(source_id),
    source_name VARCHAR(100),

    -- Quality
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    quality_score DECIMAL(5,4),
    quality_flags JSONB,

    -- Audit
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_by VARCHAR(50) DEFAULT 'LINE',

    -- Constraints
    CONSTRAINT unique_price_series UNIQUE (timestamp, symbol, interval),
    CONSTRAINT valid_ohlc CHECK (
        low <= open AND low <= close AND
        high >= open AND high >= close AND
        low <= high
    ),
    CONSTRAINT positive_values CHECK (
        open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_price_series_symbol_time ON fhq_data.price_series(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_price_series_interval ON fhq_data.price_series(interval, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_price_series_source ON fhq_data.price_series(source_name);

COMMENT ON TABLE fhq_data.price_series IS
    'Core market data: OHLCV price series with quality tracking';

-- ============================================================================
-- SECTION E: FHQ_META ADDITIONAL TABLES (Vision-IoS)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- E.1: Function Registry - Vision-IoS function tracking
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.function_registry (
    function_id SERIAL PRIMARY KEY,
    function_name VARCHAR(200) NOT NULL,
    module_path VARCHAR(500) NOT NULL,
    schema_name VARCHAR(100),

    -- Classification
    function_type VARCHAR(50) NOT NULL CHECK (
        function_type IN ('CORE', 'SIGNAL', 'AUTONOMY', 'VERIFICATION', 'GOVERNANCE', 'UTILITY')
    ),
    category VARCHAR(100),

    -- Signature
    input_params JSONB,
    output_type VARCHAR(200),
    return_schema JSONB,

    -- Dependencies
    depends_on TEXT[],
    used_by TEXT[],

    -- Compliance
    adr_compliance TEXT[],
    requires_signature BOOLEAN DEFAULT FALSE,
    vega_attestation_required BOOLEAN DEFAULT FALSE,

    -- Status
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('ACTIVE', 'DEPRECATED', 'TESTING', 'DISABLED')
    ) DEFAULT 'ACTIVE',

    -- Version
    version VARCHAR(50) NOT NULL,
    introduced_in VARCHAR(50),  -- Migration/release version

    -- Audit
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_executed_at TIMESTAMPTZ,
    execution_count BIGINT DEFAULT 0,

    CONSTRAINT unique_function UNIQUE (function_name, module_path, version)
);

CREATE INDEX IF NOT EXISTS idx_function_registry_name ON fhq_meta.function_registry(function_name);
CREATE INDEX IF NOT EXISTS idx_function_registry_type ON fhq_meta.function_registry(function_type);
CREATE INDEX IF NOT EXISTS idx_function_registry_status ON fhq_meta.function_registry(status);

COMMENT ON TABLE fhq_meta.function_registry IS
    'Vision-IoS function registry for all vision_* modules';

-- ----------------------------------------------------------------------------
-- E.2: Validation Checks - Quality validation definitions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.validation_checks (
    check_id SERIAL PRIMARY KEY,
    check_name VARCHAR(200) NOT NULL UNIQUE,
    check_type VARCHAR(50) NOT NULL CHECK (
        check_type IN ('DATA_QUALITY', 'SCHEMA', 'INTEGRITY', 'BUSINESS_RULE', 'COMPLIANCE')
    ),

    -- Definition
    check_description TEXT NOT NULL,
    check_logic TEXT NOT NULL,  -- SQL or Python expression
    check_language VARCHAR(20) CHECK (check_language IN ('SQL', 'PYTHON', 'REGEX')),

    -- Target
    target_schema VARCHAR(100),
    target_table VARCHAR(100),
    target_column VARCHAR(100),

    -- Thresholds
    severity VARCHAR(20) NOT NULL CHECK (
        severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
    ),
    threshold_value DECIMAL(10,4),
    threshold_operator VARCHAR(10) CHECK (
        threshold_operator IN ('=', '!=', '<', '>', '<=', '>=', 'BETWEEN', 'IN')
    ),

    -- Schedule
    check_frequency VARCHAR(50),  -- 'REALTIME', 'HOURLY', 'DAILY'
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- ADR
    governing_adr VARCHAR(20),

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_validation_checks_type ON fhq_meta.validation_checks(check_type);
CREATE INDEX IF NOT EXISTS idx_validation_checks_target ON fhq_meta.validation_checks(target_schema, target_table);
CREATE INDEX IF NOT EXISTS idx_validation_checks_active ON fhq_meta.validation_checks(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE fhq_meta.validation_checks IS
    'Data quality validation check definitions';

-- ----------------------------------------------------------------------------
-- E.3: Validation Reports - Validation execution results
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.validation_reports (
    report_id BIGSERIAL PRIMARY KEY,
    report_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Check reference
    check_id INTEGER NOT NULL REFERENCES fhq_meta.validation_checks(check_id),
    check_name VARCHAR(200) NOT NULL,

    -- Result
    passed BOOLEAN NOT NULL,
    result_value DECIMAL(10,4),
    result_details JSONB,

    -- Scope
    records_checked BIGINT,
    records_passed BIGINT,
    records_failed BIGINT,
    pass_rate DECIMAL(5,4),

    -- Failures
    failure_samples JSONB,  -- Sample of failing records
    failure_reasons TEXT[],

    -- Timing
    execution_started_at TIMESTAMPTZ NOT NULL,
    execution_completed_at TIMESTAMPTZ,
    execution_duration_ms INTEGER,

    -- Agent
    executed_by VARCHAR(50) NOT NULL,

    -- Remediation
    requires_remediation BOOLEAN DEFAULT FALSE,
    remediation_status VARCHAR(20) CHECK (
        remediation_status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'DEFERRED')
    ),
    remediation_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_validation_reports_timestamp ON fhq_meta.validation_reports(report_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_validation_reports_check ON fhq_meta.validation_reports(check_id);
CREATE INDEX IF NOT EXISTS idx_validation_reports_passed ON fhq_meta.validation_reports(passed);

COMMENT ON TABLE fhq_meta.validation_reports IS
    'Validation check execution results and reports';

-- ============================================================================
-- SECTION F: SEED DATA
-- ============================================================================

-- ----------------------------------------------------------------------------
-- F.1: Seed Executive Roles (7 agents)
-- ----------------------------------------------------------------------------
INSERT INTO fhq_governance.executive_roles (agent_id, role_title, role_acronym, primary_function, responsibilities, authority_level, governing_adrs, status)
VALUES
    ('LARS', 'Chief Strategy Officer', 'CSO', 'Strategic direction and governance oversight',
     ARRAY['System strategy', 'ADR governance', 'Phase transitions', 'Resource allocation'],
     9, ARRAY['ADR-001', 'ADR-004', 'ADR-005'], 'ACTIVE'),

    ('STIG', 'Chief Technology Officer', 'CTO', 'Technical validation and compliance verification',
     ARRAY['Code review', 'Technical validation', 'STIG+ compliance', 'Architecture oversight'],
     8, ARRAY['ADR-001', 'ADR-008', 'ADR-010'], 'ACTIVE'),

    ('VEGA', 'Chief Audit Officer', 'CAO', 'Autonomous constitutional governance and certification',
     ARRAY['Model certification', 'Audit execution', 'Hash verification', 'Sovereignty scoring'],
     10, ARRAY['ADR-006'], 'ACTIVE'),

    ('LINE', 'Chief Data Officer', 'CDO', 'Data ingestion, pipeline management, and quality',
     ARRAY['Data ingestion', 'Pipeline orchestration', 'Data quality', 'Source management'],
     7, ARRAY['ADR-002', 'ADR-011'], 'ACTIVE'),

    ('FINN', 'Chief Analytics Officer', 'CAnO', 'Market analysis, regime classification, and signals',
     ARRAY['Regime classification', 'CDS computation', 'Signal generation', 'Market analysis'],
     7, ARRAY['ADR-007', 'ADR-009'], 'ACTIVE'),

    ('CODE', 'Chief Engineering Officer', 'CEO', 'Code generation, implementation, and maintenance',
     ARRAY['Code generation', 'Implementation', 'Bug fixes', 'Technical documentation'],
     6, ARRAY['ADR-003'], 'ACTIVE'),

    ('CEO', 'Chief Executive Officer', 'CEO', 'Ultimate authority and constitutional exceptions',
     ARRAY['Constitutional exceptions', 'Final approvals', 'Crisis management', 'Strategic decisions'],
     10, ARRAY['ADR-001'], 'ACTIVE')
ON CONFLICT (agent_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- F.2: Seed Gate Registry (G0 → G4)
-- ----------------------------------------------------------------------------
INSERT INTO fhq_governance.gate_registry (gate_number, gate_name, gate_description, entry_criteria, exit_criteria, required_approvers, governing_adrs)
VALUES
    (0, 'G0: Initialization', 'System initialization and setup',
     '{"checks": ["schema_exists", "config_valid"]}'::JSONB,
     '{"checks": ["all_schemas_created", "baseline_established"]}'::JSONB,
     ARRAY['LARS'], ARRAY['ADR-001', 'ADR-004']),

    (1, 'G1: Development', 'Active development and testing phase',
     '{"checks": ["g0_passed", "requirements_defined"]}'::JSONB,
     '{"checks": ["unit_tests_pass", "integration_tests_pass"]}'::JSONB,
     ARRAY['STIG', 'CODE'], ARRAY['ADR-003', 'ADR-004']),

    (2, 'G2: Validation', 'Comprehensive validation and compliance',
     '{"checks": ["g1_passed", "code_review_complete"]}'::JSONB,
     '{"checks": ["stig_validation_pass", "vega_audit_pass"]}'::JSONB,
     ARRAY['STIG', 'VEGA'], ARRAY['ADR-004', 'ADR-008']),

    (3, 'G3: Staging', 'Pre-production staging and final checks',
     '{"checks": ["g2_passed", "security_review_complete"]}'::JSONB,
     '{"checks": ["performance_acceptable", "gold_baseline_approved"]}'::JSONB,
     ARRAY['LARS', 'VEGA'], ARRAY['ADR-004', 'ADR-006']),

    (4, 'G4: Production', 'Production deployment and monitoring',
     '{"checks": ["g3_passed", "lars_approval"]}'::JSONB,
     '{"checks": ["production_stable", "monitoring_active"]}'::JSONB,
     ARRAY['LARS', 'CEO'], ARRAY['ADR-004', 'ADR-006'])
ON CONFLICT (gate_number) DO NOTHING;

-- ----------------------------------------------------------------------------
-- F.3: Seed Data Sources
-- ----------------------------------------------------------------------------
INSERT INTO fhq_meta.data_source_registry (source_name, source_type, api_endpoint, data_types, update_frequency, status)
VALUES
    ('Binance', 'EXCHANGE', 'https://api.binance.com', ARRAY['OHLCV', 'ORDERBOOK', 'TRADES'], 'REALTIME', 'ACTIVE'),
    ('Alpaca', 'BROKER', 'https://api.alpaca.markets', ARRAY['OHLCV', 'TRADES'], 'REALTIME', 'ACTIVE'),
    ('Yahoo Finance', 'DATA_VENDOR', 'https://query1.finance.yahoo.com', ARRAY['OHLCV', 'FUNDAMENTALS'], 'DAILY', 'ACTIVE'),
    ('FRED', 'GOVERNMENT', 'https://api.stlouisfed.org', ARRAY['FUNDAMENTALS', 'ECONOMIC'], 'DAILY', 'ACTIVE')
ON CONFLICT (source_name) DO NOTHING;

-- ============================================================================
-- SECTION G: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_table_count INTEGER;
    v_role_count INTEGER;
    v_gate_count INTEGER;
    v_source_count INTEGER;
BEGIN
    -- Count tables created
    SELECT COUNT(*) INTO v_table_count
    FROM information_schema.tables
    WHERE table_schema IN ('fhq_meta', 'fhq_governance', 'fhq_monitoring', 'fhq_data')
    AND table_name IN (
        'adr_registry', 'agent_keys', 'key_archival_log', 'data_source_registry',
        'baseline_state', 'baseline_history', 'executive_roles', 'agent_contracts',
        'authority_matrix', 'gate_registry', 'gate_status', 'ingestion_log',
        'execution_log', 'price_series', 'function_registry', 'validation_checks',
        'validation_reports'
    );

    -- Count seeded data
    SELECT COUNT(*) INTO v_role_count FROM fhq_governance.executive_roles;
    SELECT COUNT(*) INTO v_gate_count FROM fhq_governance.gate_registry;
    SELECT COUNT(*) INTO v_source_count FROM fhq_meta.data_source_registry;

    RAISE NOTICE '====================================================';
    RAISE NOTICE 'MIGRATION 019 VERIFICATION';
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Tables created: %', v_table_count;
    RAISE NOTICE 'Executive roles seeded: %', v_role_count;
    RAISE NOTICE 'Gates defined: %', v_gate_count;
    RAISE NOTICE 'Data sources registered: %', v_source_count;
    RAISE NOTICE '====================================================';

    IF v_table_count < 15 THEN
        RAISE EXCEPTION 'Migration 019 failed: Expected 17 tables, found %', v_table_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION 019 COMPLETE
-- ============================================================================
-- Foundation Schema created:
-- - 17 new tables across 4 schemas
-- - 7 executive roles seeded
-- - 5 gates (G0-G4) defined
-- - 4 data sources registered
-- - Database: 127.0.0.1:54322
-- ============================================================================
