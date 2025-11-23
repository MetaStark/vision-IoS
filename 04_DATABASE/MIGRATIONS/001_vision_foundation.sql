-- =====================================================
-- VISION-IOS DATABASE SCHEMAS
-- Template for vision_* schemas
-- =====================================================
--
-- Foundation: ADR-001–013 (fhq-market-system)
-- Compliance: FOUNDATION_COMPATIBILITY.md
-- Database: SAME as foundation (not separate)
-- Access: READ foundation schemas, WRITE vision schemas
--
-- Generated for Vision-IoS initialization
--
-- =====================================================

BEGIN;

-- =====================================================
-- SCHEMA: vision_core
-- Purpose: Core execution engine and state management
-- =====================================================

CREATE SCHEMA IF NOT EXISTS vision_core;

-- Noise profile table (Function #2: Noise Floor Estimator)
CREATE TABLE IF NOT EXISTS vision_core.noise_profile (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Temporal scope
    analysis_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,

    -- Noise metrics
    noise_floor_value NUMERIC NOT NULL,
    noise_variance NUMERIC,
    noise_distribution JSONB,  -- Statistical distribution

    -- Signal detection threshold
    signal_threshold NUMERIC NOT NULL,
    confidence_level NUMERIC,  -- 0.0 to 1.0

    -- Metadata
    calculation_method TEXT NOT NULL,
    data_sources TEXT[],

    -- Audit trail (ADR-002)
    created_by TEXT NOT NULL,  -- Agent identity
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Verification (ADR-011)
    hash_chain_id TEXT,
    signature_id UUID,

    CONSTRAINT noise_profile_window_check CHECK (window_end > window_start),
    CONSTRAINT noise_profile_confidence_check CHECK (confidence_level >= 0 AND confidence_level <= 1)
);

CREATE INDEX idx_noise_profile_timestamp ON vision_core.noise_profile(analysis_timestamp);
CREATE INDEX idx_noise_profile_window ON vision_core.noise_profile(window_start, window_end);

-- Execution state table
CREATE TABLE IF NOT EXISTS vision_core.execution_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- State tracking
    component_name TEXT NOT NULL,
    state_type TEXT NOT NULL,  -- 'ACTIVE', 'SUSPENDED', 'MAINTENANCE'
    state_value JSONB NOT NULL,

    -- Versioning
    state_version INTEGER NOT NULL DEFAULT 1,
    previous_state_id UUID REFERENCES vision_core.execution_state(state_id),

    -- Audit trail (ADR-002)
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Verification
    hash_chain_id TEXT,
    signature_id UUID
);

CREATE INDEX idx_execution_state_component ON vision_core.execution_state(component_name);
CREATE INDEX idx_execution_state_type ON vision_core.execution_state(state_type);

-- =====================================================
-- SCHEMA: vision_signals
-- Purpose: Alpha signal storage and analysis
-- =====================================================

CREATE SCHEMA IF NOT EXISTS vision_signals;

-- Signal baseline table (Function #1: Signal Inference Baseline)
CREATE TABLE IF NOT EXISTS vision_signals.signal_baseline (
    baseline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal identification
    signal_type TEXT NOT NULL,
    signal_name TEXT NOT NULL,

    -- Baseline metrics
    baseline_value NUMERIC NOT NULL,
    baseline_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Statistical properties
    mean_value NUMERIC,
    std_deviation NUMERIC,
    percentile_25 NUMERIC,
    percentile_50 NUMERIC,
    percentile_75 NUMERIC,
    percentile_95 NUMERIC,
    percentile_99 NUMERIC,

    -- Data quality
    sample_size INTEGER NOT NULL,
    confidence_interval NUMERIC,

    -- Source data
    source_schemas TEXT[],  -- Which fhq_* schemas were read
    calculation_window INTERVAL NOT NULL,

    -- Metadata
    calculation_method TEXT NOT NULL,
    parameters JSONB,

    -- Audit trail (ADR-002)
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Verification (ADR-011)
    hash_chain_id TEXT,
    signature_id UUID,

    CONSTRAINT signal_baseline_sample_size_check CHECK (sample_size > 0)
);

CREATE INDEX idx_signal_baseline_type ON vision_signals.signal_baseline(signal_type);
CREATE INDEX idx_signal_baseline_name ON vision_signals.signal_baseline(signal_name);
CREATE INDEX idx_signal_baseline_timestamp ON vision_signals.signal_baseline(baseline_timestamp);

-- Alpha signals table (future use - not for initial 3 functions)
CREATE TABLE IF NOT EXISTS vision_signals.alpha_signals (
    signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal properties
    signal_type TEXT NOT NULL,
    signal_strength NUMERIC NOT NULL,
    confidence_score NUMERIC NOT NULL,

    -- Temporal scope
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,

    -- Signal data
    signal_data JSONB NOT NULL,

    -- Baseline reference
    baseline_id UUID REFERENCES vision_signals.signal_baseline(baseline_id),
    deviation_from_baseline NUMERIC,

    -- Execution status (ADR-012 - cannot execute until QG-F6 passes)
    is_executable BOOLEAN NOT NULL DEFAULT FALSE,
    execution_blocked_reason TEXT,

    -- Audit trail (ADR-002)
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Verification (ADR-011)
    hash_chain_id TEXT,
    signature_id UUID,

    CONSTRAINT alpha_signals_confidence_check CHECK (confidence_score >= 0 AND confidence_score <= 1),
    CONSTRAINT alpha_signals_execution_block CHECK (
        is_executable = FALSE OR execution_blocked_reason IS NULL
    )
);

CREATE INDEX idx_alpha_signals_type ON vision_signals.alpha_signals(signal_type);
CREATE INDEX idx_alpha_signals_generated ON vision_signals.alpha_signals(generated_at);
CREATE INDEX idx_alpha_signals_executable ON vision_signals.alpha_signals(is_executable);

-- =====================================================
-- SCHEMA: vision_autonomy
-- Purpose: Self-governance state and meta-sync
-- =====================================================

CREATE SCHEMA IF NOT EXISTS vision_autonomy;

-- Meta-state sync table (Function #3: Meta-State Sync)
CREATE TABLE IF NOT EXISTS vision_autonomy.meta_state_sync (
    sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Sync properties
    sync_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sync_type TEXT NOT NULL,  -- 'FULL', 'INCREMENTAL', 'RECONCILIATION'

    -- Source and target
    source_schema TEXT NOT NULL,  -- vision_*
    target_schema TEXT NOT NULL,  -- fhq_meta

    -- Sync metrics
    records_read INTEGER NOT NULL DEFAULT 0,
    records_written INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,

    -- Sync status
    sync_status TEXT NOT NULL,  -- 'SUCCESS', 'PARTIAL', 'FAILED'
    error_details JSONB,

    -- Reconciliation (ADR-010)
    reconciliation_snapshot_id UUID,  -- Links to fhq_meta reconciliation
    discrepancy_count INTEGER DEFAULT 0,

    -- Audit trail (ADR-002)
    initiated_by TEXT NOT NULL,
    completed_at TIMESTAMPTZ,

    -- Verification (ADR-011)
    hash_chain_id TEXT,
    signature_id UUID,

    CONSTRAINT meta_sync_status_check CHECK (sync_status IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    CONSTRAINT meta_sync_completion_check CHECK (
        (sync_status = 'SUCCESS' AND completed_at IS NOT NULL) OR
        (sync_status != 'SUCCESS')
    )
);

CREATE INDEX idx_meta_sync_timestamp ON vision_autonomy.meta_state_sync(sync_timestamp);
CREATE INDEX idx_meta_sync_status ON vision_autonomy.meta_state_sync(sync_status);
CREATE INDEX idx_meta_sync_type ON vision_autonomy.meta_state_sync(sync_type);

-- Governance decisions table
CREATE TABLE IF NOT EXISTS vision_autonomy.governance_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Decision context
    decision_type TEXT NOT NULL,
    decision_scope TEXT NOT NULL,

    -- Decision outcome
    decision TEXT NOT NULL,
    rationale TEXT,

    -- VEGA integration (ADR-006)
    vega_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    vega_approved BOOLEAN,
    vega_reviewer TEXT,
    vega_review_timestamp TIMESTAMPTZ,

    -- Gate compliance (ADR-004)
    gate_level TEXT NOT NULL,  -- 'G0', 'G1', 'G2', 'G3', 'G4'
    gate_passed BOOLEAN NOT NULL DEFAULT FALSE,

    -- Audit trail (ADR-002)
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Verification (ADR-011)
    hash_chain_id TEXT,
    signature_id UUID,

    CONSTRAINT governance_gate_check CHECK (gate_level IN ('G0', 'G1', 'G2', 'G3', 'G4')),
    CONSTRAINT governance_vega_check CHECK (
        (vega_reviewed = FALSE) OR
        (vega_reviewed = TRUE AND vega_reviewer IS NOT NULL AND vega_review_timestamp IS NOT NULL)
    )
);

CREATE INDEX idx_governance_decision_type ON vision_autonomy.governance_decisions(decision_type);
CREATE INDEX idx_governance_vega ON vision_autonomy.governance_decisions(vega_reviewed, vega_approved);
CREATE INDEX idx_governance_gate ON vision_autonomy.governance_decisions(gate_level, gate_passed);

-- =====================================================
-- SCHEMA: vision_verification
-- Purpose: Cryptographic proofs and verification
-- =====================================================

CREATE SCHEMA IF NOT EXISTS vision_verification;

-- Operation signatures table (ADR-008 - Ed25519)
CREATE TABLE IF NOT EXISTS vision_verification.operation_signatures (
    signature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Operation being signed
    operation_type TEXT NOT NULL,
    operation_id UUID NOT NULL,
    operation_table TEXT NOT NULL,  -- Which table the operation is in
    operation_schema TEXT NOT NULL,  -- Which schema

    -- Signature details (ADR-008)
    signing_agent TEXT NOT NULL,  -- LARS, STIG, LINE, or FINN
    signing_key_id TEXT NOT NULL,  -- References fhq_meta.agent_keys

    -- Signature
    signature_value TEXT NOT NULL,  -- Ed25519 signature (hex)
    signed_payload JSONB NOT NULL,  -- What was signed

    -- Verification
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    verified_by TEXT,

    -- Audit trail (ADR-002)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Hash chain (ADR-011)
    hash_chain_id TEXT NOT NULL,
    previous_signature_id UUID REFERENCES vision_verification.operation_signatures(signature_id),

    CONSTRAINT operation_signature_agent_check CHECK (signing_agent IN ('LARS', 'STIG', 'LINE', 'FINN')),
    CONSTRAINT operation_signature_verified_check CHECK (
        (verified = FALSE) OR
        (verified = TRUE AND verified_at IS NOT NULL AND verified_by IS NOT NULL)
    )
);

CREATE INDEX idx_operation_signatures_operation ON vision_verification.operation_signatures(operation_schema, operation_table, operation_id);
CREATE INDEX idx_operation_signatures_agent ON vision_verification.operation_signatures(signing_agent);
CREATE INDEX idx_operation_signatures_chain ON vision_verification.operation_signatures(hash_chain_id);
CREATE INDEX idx_operation_signatures_verified ON vision_verification.operation_signatures(verified);

-- Hash chains table (ADR-011 - Fortress)
CREATE TABLE IF NOT EXISTS vision_verification.hash_chains (
    chain_id TEXT PRIMARY KEY,

    -- Chain metadata
    chain_type TEXT NOT NULL,
    chain_scope TEXT NOT NULL,

    -- Chain state
    genesis_hash TEXT NOT NULL,
    current_hash TEXT NOT NULL,
    chain_length INTEGER NOT NULL DEFAULT 1,

    -- Chain integrity
    integrity_verified BOOLEAN NOT NULL DEFAULT TRUE,
    last_verification_at TIMESTAMPTZ,

    -- Audit trail (ADR-002)
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT hash_chain_length_check CHECK (chain_length > 0)
);

CREATE INDEX idx_hash_chains_type ON vision_verification.hash_chains(chain_type);
CREATE INDEX idx_hash_chains_integrity ON vision_verification.hash_chains(integrity_verified);

-- =====================================================
-- ACCESS CONTROL GRANTS
-- =====================================================

-- Note: Run these grants AFTER creating a vision_app database role
--
-- -- Foundation schemas: SELECT only
-- GRANT USAGE ON SCHEMA fhq_data TO vision_app;
-- GRANT SELECT ON ALL TABLES IN SCHEMA fhq_data TO vision_app;
--
-- GRANT USAGE ON SCHEMA fhq_meta TO vision_app;
-- GRANT SELECT ON ALL TABLES IN SCHEMA fhq_meta TO vision_app;
--
-- GRANT USAGE ON SCHEMA fhq_monitoring TO vision_app;
-- GRANT SELECT ON ALL TABLES IN SCHEMA fhq_monitoring TO vision_app;
--
-- GRANT USAGE ON SCHEMA fhq_research TO vision_app;
-- GRANT SELECT ON ALL TABLES IN SCHEMA fhq_research TO vision_app;
--
-- -- Vision schemas: ALL privileges
-- GRANT ALL ON SCHEMA vision_core TO vision_app;
-- GRANT ALL ON ALL TABLES IN SCHEMA vision_core TO vision_app;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA vision_core TO vision_app;
--
-- GRANT ALL ON SCHEMA vision_signals TO vision_app;
-- GRANT ALL ON ALL TABLES IN SCHEMA vision_signals TO vision_app;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA vision_signals TO vision_app;
--
-- GRANT ALL ON SCHEMA vision_autonomy TO vision_app;
-- GRANT ALL ON ALL TABLES IN SCHEMA vision_autonomy TO vision_app;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA vision_autonomy TO vision_app;
--
-- GRANT ALL ON SCHEMA vision_verification TO vision_app;
-- GRANT ALL ON ALL TABLES IN SCHEMA vision_verification TO vision_app;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA vision_verification TO vision_app;

COMMIT;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify schemas were created
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name LIKE 'vision_%'
ORDER BY schema_name;

-- Verify tables were created
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema LIKE 'vision_%'
ORDER BY table_schema, table_name;

-- =====================================================
-- END OF VISION SCHEMAS
-- =====================================================
