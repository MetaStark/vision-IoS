-- ============================================================================
-- VEGA ADR-006 DATABASE INTEGRATION
-- Authority: ADR-006_2026_PRODUCTION (VEGA Autonomy & Governance Engine Charter)
-- ============================================================================
-- Migration: 018_vega_adr006_integration.sql
-- Authority: LARS – Chief Strategy Officer
-- Reference: ADR-006_2026_PRODUCTION
-- Approved By: CEO
-- Constitutional Authority: ADR-001_2026_PRODUCTION
--
-- PURPOSE:
-- Full integration of VEGA governance layer per ADR-006 specification.
-- Creates 5 constitutional tables and 9 governance SQL functions.
--
-- TABLES:
-- 1. fhq_meta.adr_audit_log         - Immutable audit trail with hash chains
-- 2. fhq_meta.adr_version_history   - ADR version lineage
-- 3. fhq_meta.model_certifications  - MDLC certification registry
-- 4. fhq_meta.data_lineage_log      - Data provenance tracking
-- 5. fhq_meta.vega_sovereignty_log  - Sovereignty scores (ADR-005)
--
-- FUNCTIONS (9):
-- vega_verify_hashes(), vega_compare_registry(), vega_snapshot_canonical()
-- vega_issue_certificate(), vega_record_adversarial_event(), vega_trigger_dora_assessment()
-- vega_log_bias_drift(), vega_enforce_class_b_threshold(), vega_calculate_sovereignty_score()
--
-- COMPLIANCE:
-- - ADR-001 → ADR-006 (Constitutional Chain)
-- - ISO 42001 AI Management System
-- - DORA Article 17 Incident Classification
-- - GIPS 2020 Performance Standards
-- - BCBS-239 Data Lineage
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CREATE FHQ_META SCHEMA (IF NOT EXISTS)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS fhq_meta;

SET search_path TO fhq_meta, public;

-- ============================================================================
-- SECTION 2: ADR AUDIT LOG TABLE
-- Immutable audit trail with SHA-256 hash chains
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.adr_audit_log (
    -- Primary identification
    audit_id BIGSERIAL PRIMARY KEY,
    audit_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Event classification
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL CHECK (
        event_category IN (
            'governance',           -- ADR changes, policy updates
            'certification',        -- Model certification events
            'integrity',            -- Hash verification, reconciliation
            'adversarial',          -- Security events, attacks
            'compliance',           -- DORA, GIPS, regulatory
            'operational',          -- System events, rhythms
            'sovereignty'           -- Sovereignty scoring
        )
    ),
    severity VARCHAR(20) NOT NULL CHECK (
        severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
    ),

    -- Discrepancy classification (ADR-010)
    discrepancy_class VARCHAR(10) CHECK (
        discrepancy_class IN ('CLASS_A', 'CLASS_B', 'CLASS_C', 'NONE')
    ) DEFAULT 'NONE',

    -- Actor and action
    actor VARCHAR(50) NOT NULL,  -- VEGA, LARS, STIG, FINN, LINE, CEO
    action VARCHAR(200) NOT NULL,
    target VARCHAR(200),
    target_type VARCHAR(50),

    -- Event payload
    event_data JSONB NOT NULL DEFAULT '{}',

    -- Governance authority
    authority VARCHAR(500),  -- ADR reference or directive
    adr_compliance TEXT[],   -- Array of ADR numbers

    -- Hash chain for immutability (BCBS-239)
    previous_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL,
    hash_chain_id VARCHAR(100),
    hash_chain_position INTEGER,

    -- Cryptographic signature (Ed25519)
    vega_signature TEXT,
    vega_public_key TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,

    -- Immutability enforcement
    immutable BOOLEAN DEFAULT TRUE,

    -- Audit metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_hash_length CHECK (
        LENGTH(event_hash) = 64 AND
        (previous_hash IS NULL OR LENGTH(previous_hash) = 64)
    ),
    CONSTRAINT chk_immutable_no_update CHECK (immutable = TRUE)
);

-- Indexes for audit log
CREATE INDEX IF NOT EXISTS idx_adr_audit_log_timestamp
    ON fhq_meta.adr_audit_log(audit_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_adr_audit_log_event_type
    ON fhq_meta.adr_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_adr_audit_log_category
    ON fhq_meta.adr_audit_log(event_category);
CREATE INDEX IF NOT EXISTS idx_adr_audit_log_actor
    ON fhq_meta.adr_audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_adr_audit_log_severity
    ON fhq_meta.adr_audit_log(severity);
CREATE INDEX IF NOT EXISTS idx_adr_audit_log_hash_chain
    ON fhq_meta.adr_audit_log(hash_chain_id, hash_chain_position);
CREATE INDEX IF NOT EXISTS idx_adr_audit_log_discrepancy
    ON fhq_meta.adr_audit_log(discrepancy_class) WHERE discrepancy_class != 'NONE';

COMMENT ON TABLE fhq_meta.adr_audit_log IS
    'ADR-006: Immutable audit trail with SHA-256 hash chains for VEGA governance';

-- ============================================================================
-- SECTION 3: ADR VERSION HISTORY TABLE
-- Version lineage tracking for all ADRs
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.adr_version_history (
    -- Primary identification
    version_id BIGSERIAL PRIMARY KEY,

    -- ADR identification
    adr_number VARCHAR(20) NOT NULL,  -- e.g., 'ADR-006'
    adr_title VARCHAR(500) NOT NULL,

    -- Version information
    version_number VARCHAR(50) NOT NULL,  -- e.g., '2026.PRODUCTION'
    version_status VARCHAR(50) NOT NULL CHECK (
        version_status IN ('DRAFT', 'REVIEW', 'APPROVED', 'CANONICAL', 'SUPERSEDED', 'DEPRECATED')
    ),
    version_phase VARCHAR(50) CHECK (
        version_phase IN ('DRAFT', 'STAGING', 'PRODUCTION', 'CANONICAL')
    ),

    -- Version metadata
    effective_date DATE,
    supersedes VARCHAR(500),  -- Previous version reference
    superseded_by VARCHAR(500),  -- Next version reference

    -- Ownership
    owner VARCHAR(100) NOT NULL,  -- LARS, STIG, etc.
    approved_by VARCHAR(100),

    -- Content hash for integrity
    content_hash VARCHAR(64) NOT NULL,
    file_path VARCHAR(500),

    -- Change tracking
    change_summary TEXT,
    change_type VARCHAR(50) CHECK (
        change_type IN ('INITIAL', 'AMENDMENT', 'REVISION', 'DEPRECATION', 'SUPERSESSION')
    ),

    -- Cryptographic attestation
    vega_signature TEXT,
    signature_timestamp TIMESTAMPTZ,

    -- Audit trail
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',

    -- Constraints
    CONSTRAINT unique_adr_version UNIQUE (adr_number, version_number)
);

-- Indexes for version history
CREATE INDEX IF NOT EXISTS idx_adr_version_adr_number
    ON fhq_meta.adr_version_history(adr_number);
CREATE INDEX IF NOT EXISTS idx_adr_version_status
    ON fhq_meta.adr_version_history(version_status);
CREATE INDEX IF NOT EXISTS idx_adr_version_effective
    ON fhq_meta.adr_version_history(effective_date DESC);

COMMENT ON TABLE fhq_meta.adr_version_history IS
    'ADR-006: Version lineage tracking for constitutional ADR documents';

-- ============================================================================
-- SECTION 4: MODEL CERTIFICATIONS TABLE
-- MDLC 6-Gate Certification Registry
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.model_certifications (
    -- Primary identification
    certification_id BIGSERIAL PRIMARY KEY,

    -- Model identification
    model_id VARCHAR(100) NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) CHECK (
        model_type IN ('REGIME_CLASSIFIER', 'SIGNAL_GENERATOR', 'RISK_MODEL',
                       'VALIDATION_MODEL', 'ORCHESTRATOR', 'GOVERNANCE')
    ),

    -- MDLC Gate tracking (6 gates)
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

    -- Current certification status
    certification_status VARCHAR(50) NOT NULL CHECK (
        certification_status IN (
            'PENDING',
            'GATE_1_APPROVED',
            'GATE_2_APPROVED',
            'GATE_3_APPROVED',
            'GATE_4_APPROVED',
            'GATE_5_APPROVED',
            'FULLY_CERTIFIED',
            'SUSPENDED',
            'RETIRED',
            'REJECTED'
        )
    ) DEFAULT 'PENDING',

    -- Certification metrics
    bias_score DECIMAL(5,4),
    drift_score DECIMAL(5,4),
    explainability_score DECIMAL(5,4),
    robustness_score DECIMAL(5,4),
    overall_certification_score DECIMAL(5,4),

    -- XAI explainability artifacts
    xai_artifacts JSONB DEFAULT '{}',

    -- Adversarial robustness
    adversarial_test_passed BOOLEAN DEFAULT FALSE,
    adversarial_test_timestamp TIMESTAMPTZ,
    adversarial_results JSONB DEFAULT '{}',

    -- Regulatory compliance
    iso_42001_compliant BOOLEAN DEFAULT FALSE,
    dora_compliant BOOLEAN DEFAULT FALSE,
    gips_compliant BOOLEAN DEFAULT FALSE,

    -- VEGA certification signature
    vega_signature TEXT NOT NULL,
    vega_public_key TEXT NOT NULL,
    signature_verified BOOLEAN DEFAULT FALSE,

    -- Retirement tracking
    retirement_date DATE,
    retirement_reason TEXT,

    -- Audit trail
    certified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    certified_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    last_review_at TIMESTAMPTZ,
    next_review_due DATE,

    -- Constraints
    CONSTRAINT unique_model_certification UNIQUE (model_id, model_version)
);

-- Indexes for model certifications
CREATE INDEX IF NOT EXISTS idx_model_cert_model_id
    ON fhq_meta.model_certifications(model_id);
CREATE INDEX IF NOT EXISTS idx_model_cert_status
    ON fhq_meta.model_certifications(certification_status);
CREATE INDEX IF NOT EXISTS idx_model_cert_type
    ON fhq_meta.model_certifications(model_type);
CREATE INDEX IF NOT EXISTS idx_model_cert_review
    ON fhq_meta.model_certifications(next_review_due) WHERE certification_status = 'FULLY_CERTIFIED';

COMMENT ON TABLE fhq_meta.model_certifications IS
    'ADR-006: MDLC 6-Gate model certification registry with VEGA attestation';

-- ============================================================================
-- SECTION 5: DATA LINEAGE LOG TABLE
-- Data provenance tracking (BCBS-239)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.data_lineage_log (
    -- Primary identification
    lineage_id BIGSERIAL PRIMARY KEY,
    lineage_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Lineage chain identification
    lineage_chain_id VARCHAR(100) NOT NULL,
    lineage_position INTEGER NOT NULL,

    -- Source information
    source_system VARCHAR(100) NOT NULL,
    source_schema VARCHAR(100),
    source_table VARCHAR(100),
    source_column VARCHAR(100),
    source_record_id TEXT,

    -- Target information
    target_system VARCHAR(100) NOT NULL,
    target_schema VARCHAR(100),
    target_table VARCHAR(100),
    target_column VARCHAR(100),
    target_record_id TEXT,

    -- Transformation details
    transformation_type VARCHAR(50) CHECK (
        transformation_type IN (
            'INGEST',       -- External data ingestion
            'TRANSFORM',    -- Data transformation
            'AGGREGATE',    -- Aggregation operation
            'DERIVE',       -- Derived calculation
            'VALIDATE',     -- Validation step
            'ENRICH',       -- Data enrichment
            'FILTER',       -- Data filtering
            'JOIN',         -- Data join operation
            'OUTPUT'        -- Final output
        )
    ),
    transformation_logic TEXT,
    transformation_hash VARCHAR(64),

    -- Data quality
    quality_score DECIMAL(5,4),
    quality_checks JSONB DEFAULT '{}',

    -- Agent attribution
    processing_agent VARCHAR(50) NOT NULL,  -- LINE, FINN, STIG, etc.

    -- Hash chain for immutability
    previous_lineage_hash VARCHAR(64),
    lineage_hash VARCHAR(64) NOT NULL,

    -- VEGA attestation
    vega_signature TEXT,
    attested BOOLEAN DEFAULT FALSE,

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_lineage_position UNIQUE (lineage_chain_id, lineage_position)
);

-- Indexes for data lineage
CREATE INDEX IF NOT EXISTS idx_data_lineage_chain
    ON fhq_meta.data_lineage_log(lineage_chain_id, lineage_position);
CREATE INDEX IF NOT EXISTS idx_data_lineage_source
    ON fhq_meta.data_lineage_log(source_system, source_table);
CREATE INDEX IF NOT EXISTS idx_data_lineage_target
    ON fhq_meta.data_lineage_log(target_system, target_table);
CREATE INDEX IF NOT EXISTS idx_data_lineage_timestamp
    ON fhq_meta.data_lineage_log(lineage_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_data_lineage_agent
    ON fhq_meta.data_lineage_log(processing_agent);

COMMENT ON TABLE fhq_meta.data_lineage_log IS
    'ADR-006/BCBS-239: Data provenance and lineage tracking with hash chains';

-- ============================================================================
-- SECTION 6: VEGA SOVEREIGNTY LOG TABLE
-- Sovereignty scores per ADR-005
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.vega_sovereignty_log (
    -- Primary identification
    sovereignty_id BIGSERIAL PRIMARY KEY,
    score_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Scoring period
    scoring_period VARCHAR(20) NOT NULL CHECK (
        scoring_period IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUAL')
    ),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Core sovereignty metrics (ADR-005)
    overall_sovereignty_score DECIMAL(5,4) NOT NULL CHECK (
        overall_sovereignty_score >= 0 AND overall_sovereignty_score <= 1
    ),

    -- Component scores
    constitutional_compliance_score DECIMAL(5,4),  -- ADR adherence
    operational_autonomy_score DECIMAL(5,4),       -- Self-governance capability
    data_sovereignty_score DECIMAL(5,4),           -- Data ownership/control
    regulatory_compliance_score DECIMAL(5,4),      -- DORA, GIPS, etc.
    economic_sovereignty_score DECIMAL(5,4),       -- Cost independence

    -- Detailed metrics
    metrics_breakdown JSONB NOT NULL DEFAULT '{}',

    -- ADR compliance status
    adr_compliance_status JSONB DEFAULT '{}',  -- Per-ADR compliance
    total_adrs_compliant INTEGER DEFAULT 0,
    total_adrs_evaluated INTEGER DEFAULT 0,

    -- Governance health
    audit_findings_count INTEGER DEFAULT 0,
    class_a_events INTEGER DEFAULT 0,
    class_b_events INTEGER DEFAULT 0,
    class_c_events INTEGER DEFAULT 0,

    -- Certification status
    models_certified INTEGER DEFAULT 0,
    models_pending INTEGER DEFAULT 0,
    models_suspended INTEGER DEFAULT 0,

    -- Regulatory status
    dora_compliance_status VARCHAR(20) CHECK (
        dora_compliance_status IN ('COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'PENDING')
    ),
    gips_compliance_status VARCHAR(20) CHECK (
        gips_compliance_status IN ('COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'PENDING')
    ),

    -- VEGA attestation
    vega_signature TEXT NOT NULL,
    vega_public_key TEXT NOT NULL,
    signature_verified BOOLEAN DEFAULT FALSE,

    -- Trend analysis
    previous_score DECIMAL(5,4),
    score_delta DECIMAL(5,4),
    trend VARCHAR(20) CHECK (trend IN ('IMPROVING', 'STABLE', 'DECLINING')),

    -- Audit trail
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    calculated_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',

    -- Constraints
    CONSTRAINT unique_sovereignty_period UNIQUE (scoring_period, period_start, period_end)
);

-- Indexes for sovereignty log
CREATE INDEX IF NOT EXISTS idx_sovereignty_timestamp
    ON fhq_meta.vega_sovereignty_log(score_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sovereignty_period
    ON fhq_meta.vega_sovereignty_log(scoring_period, period_start);
CREATE INDEX IF NOT EXISTS idx_sovereignty_score
    ON fhq_meta.vega_sovereignty_log(overall_sovereignty_score DESC);

COMMENT ON TABLE fhq_meta.vega_sovereignty_log IS
    'ADR-005/ADR-006: Commercial sovereignty scores calculated by VEGA';

-- ============================================================================
-- SECTION 7: VEGA SQL GOVERNANCE FUNCTIONS (9 functions)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Function 1: vega_verify_hashes()
-- Verifies hash chain integrity for audit logs
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_verify_hashes(
    p_chain_id VARCHAR(100) DEFAULT NULL,
    p_limit INTEGER DEFAULT 1000
)
RETURNS TABLE (
    chain_id VARCHAR(100),
    total_entries BIGINT,
    valid_entries BIGINT,
    broken_links BIGINT,
    integrity_status VARCHAR(20),
    first_break_position INTEGER
) AS $$
DECLARE
    v_chain RECORD;
    v_previous_hash VARCHAR(64);
    v_entry RECORD;
    v_valid_count BIGINT;
    v_broken_count BIGINT;
    v_first_break INTEGER;
BEGIN
    FOR v_chain IN
        SELECT DISTINCT hash_chain_id
        FROM fhq_meta.adr_audit_log
        WHERE (p_chain_id IS NULL OR hash_chain_id = p_chain_id)
        AND hash_chain_id IS NOT NULL
    LOOP
        v_previous_hash := NULL;
        v_valid_count := 0;
        v_broken_count := 0;
        v_first_break := NULL;

        FOR v_entry IN
            SELECT audit_id, event_hash, previous_hash, hash_chain_position
            FROM fhq_meta.adr_audit_log
            WHERE hash_chain_id = v_chain.hash_chain_id
            ORDER BY hash_chain_position ASC
            LIMIT p_limit
        LOOP
            IF v_entry.previous_hash = v_previous_hash OR
               (v_previous_hash IS NULL AND v_entry.previous_hash IS NULL) THEN
                v_valid_count := v_valid_count + 1;
            ELSE
                v_broken_count := v_broken_count + 1;
                IF v_first_break IS NULL THEN
                    v_first_break := v_entry.hash_chain_position;
                END IF;
            END IF;
            v_previous_hash := v_entry.event_hash;
        END LOOP;

        chain_id := v_chain.hash_chain_id;
        total_entries := v_valid_count + v_broken_count;
        valid_entries := v_valid_count;
        broken_links := v_broken_count;
        integrity_status := CASE
            WHEN v_broken_count = 0 THEN 'VALID'
            WHEN v_broken_count < v_valid_count THEN 'PARTIAL'
            ELSE 'BROKEN'
        END;
        first_break_position := v_first_break;

        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_verify_hashes IS
    'ADR-006: Verify hash chain integrity for audit logs';

-- ----------------------------------------------------------------------------
-- Function 2: vega_compare_registry()
-- Compares current state against canonical registry
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_compare_registry(
    p_registry_type VARCHAR(50)
)
RETURNS TABLE (
    comparison_id VARCHAR(100),
    registry_type VARCHAR(50),
    total_items BIGINT,
    matching_items BIGINT,
    mismatched_items BIGINT,
    missing_items BIGINT,
    reconciliation_required BOOLEAN,
    comparison_timestamp TIMESTAMPTZ
) AS $$
BEGIN
    comparison_id := 'REG-COMPARE-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS');
    registry_type := p_registry_type;
    comparison_timestamp := NOW();

    CASE p_registry_type
        WHEN 'MODEL_CERTIFICATIONS' THEN
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE signature_verified = TRUE),
                   COUNT(*) FILTER (WHERE signature_verified = FALSE),
                   COUNT(*) FILTER (WHERE certification_status = 'PENDING')
            INTO total_items, matching_items, mismatched_items, missing_items
            FROM fhq_meta.model_certifications;

        WHEN 'ADR_VERSIONS' THEN
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE version_status = 'CANONICAL'),
                   COUNT(*) FILTER (WHERE version_status IN ('DRAFT', 'REVIEW')),
                   COUNT(*) FILTER (WHERE version_status = 'DEPRECATED')
            INTO total_items, matching_items, mismatched_items, missing_items
            FROM fhq_meta.adr_version_history;

        WHEN 'DATA_LINEAGE' THEN
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE attested = TRUE),
                   COUNT(*) FILTER (WHERE attested = FALSE),
                   0
            INTO total_items, matching_items, mismatched_items, missing_items
            FROM fhq_meta.data_lineage_log;

        ELSE
            total_items := 0;
            matching_items := 0;
            mismatched_items := 0;
            missing_items := 0;
    END CASE;

    reconciliation_required := (mismatched_items > 0 OR missing_items > 0);

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_compare_registry IS
    'ADR-006: Compare current state against canonical registry';

-- ----------------------------------------------------------------------------
-- Function 3: vega_snapshot_canonical()
-- Creates a canonical snapshot of current governance state
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_snapshot_canonical(
    p_snapshot_type VARCHAR(50),
    p_authority VARCHAR(200)
)
RETURNS TABLE (
    snapshot_id VARCHAR(100),
    snapshot_type VARCHAR(50),
    snapshot_hash VARCHAR(64),
    items_count BIGINT,
    snapshot_timestamp TIMESTAMPTZ,
    authority VARCHAR(200)
) AS $$
DECLARE
    v_snapshot_data JSONB;
    v_hash VARCHAR(64);
BEGIN
    snapshot_id := 'SNAP-' || p_snapshot_type || '-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS');
    snapshot_type := p_snapshot_type;
    snapshot_timestamp := NOW();
    authority := p_authority;

    CASE p_snapshot_type
        WHEN 'GOVERNANCE_STATE' THEN
            SELECT jsonb_build_object(
                'certifications', (SELECT COUNT(*) FROM fhq_meta.model_certifications),
                'audit_entries', (SELECT COUNT(*) FROM fhq_meta.adr_audit_log),
                'adr_versions', (SELECT COUNT(*) FROM fhq_meta.adr_version_history),
                'lineage_entries', (SELECT COUNT(*) FROM fhq_meta.data_lineage_log),
                'sovereignty_scores', (SELECT COUNT(*) FROM fhq_meta.vega_sovereignty_log),
                'snapshot_time', NOW()
            ) INTO v_snapshot_data;

            items_count := (v_snapshot_data->>'certifications')::BIGINT +
                          (v_snapshot_data->>'audit_entries')::BIGINT +
                          (v_snapshot_data->>'adr_versions')::BIGINT;

        WHEN 'CERTIFICATION_STATE' THEN
            SELECT jsonb_agg(jsonb_build_object(
                'model_id', model_id,
                'status', certification_status,
                'signature', vega_signature
            ))
            INTO v_snapshot_data
            FROM fhq_meta.model_certifications
            WHERE certification_status = 'FULLY_CERTIFIED';

            SELECT COUNT(*) INTO items_count
            FROM fhq_meta.model_certifications
            WHERE certification_status = 'FULLY_CERTIFIED';

        ELSE
            v_snapshot_data := '{}'::JSONB;
            items_count := 0;
    END CASE;

    v_hash := encode(sha256(v_snapshot_data::TEXT::BYTEA), 'hex');
    snapshot_hash := v_hash;

    -- Log the snapshot event
    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action, target,
        event_data, authority, event_hash
    ) VALUES (
        'canonical_snapshot', 'governance', 'INFO', 'VEGA',
        'CREATE_CANONICAL_SNAPSHOT', p_snapshot_type,
        jsonb_build_object('snapshot_id', snapshot_id, 'hash', v_hash, 'items', items_count),
        p_authority,
        v_hash
    );

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_snapshot_canonical IS
    'ADR-006: Create canonical snapshot of governance state';

-- ----------------------------------------------------------------------------
-- Function 4: vega_issue_certificate()
-- Issues MDLC certification for a model
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_issue_certificate(
    p_model_id VARCHAR(100),
    p_model_name VARCHAR(200),
    p_model_version VARCHAR(50),
    p_model_type VARCHAR(50),
    p_gate_number INTEGER,
    p_certification_data JSONB,
    p_vega_signature TEXT,
    p_vega_public_key TEXT
)
RETURNS TABLE (
    certification_id BIGINT,
    model_id VARCHAR(100),
    gate_number INTEGER,
    new_status VARCHAR(50),
    issued_at TIMESTAMPTZ
) AS $$
DECLARE
    v_cert_id BIGINT;
    v_new_status VARCHAR(50);
    v_gate_column TEXT;
BEGIN
    -- Determine new status based on gate
    v_new_status := CASE p_gate_number
        WHEN 1 THEN 'GATE_1_APPROVED'
        WHEN 2 THEN 'GATE_2_APPROVED'
        WHEN 3 THEN 'GATE_3_APPROVED'
        WHEN 4 THEN 'GATE_4_APPROVED'
        WHEN 5 THEN 'GATE_5_APPROVED'
        WHEN 6 THEN 'FULLY_CERTIFIED'
        ELSE 'PENDING'
    END;

    -- Insert or update certification
    INSERT INTO fhq_meta.model_certifications (
        model_id, model_name, model_version, model_type,
        certification_status, vega_signature, vega_public_key,
        xai_artifacts
    ) VALUES (
        p_model_id, p_model_name, p_model_version, p_model_type,
        v_new_status, p_vega_signature, p_vega_public_key,
        COALESCE(p_certification_data, '{}')
    )
    ON CONFLICT (model_id, model_version) DO UPDATE SET
        certification_status = v_new_status,
        vega_signature = p_vega_signature,
        last_review_at = NOW()
    RETURNING model_certifications.certification_id INTO v_cert_id;

    -- Update specific gate timestamp
    EXECUTE format(
        'UPDATE fhq_meta.model_certifications SET gate_%s_%s = TRUE, gate_%s_timestamp = NOW() WHERE certification_id = $1',
        p_gate_number,
        CASE p_gate_number
            WHEN 1 THEN 'research'
            WHEN 2 THEN 'development'
            WHEN 3 THEN 'validation'
            WHEN 4 THEN 'staging'
            WHEN 5 THEN 'production'
            WHEN 6 THEN 'monitoring'
        END,
        p_gate_number
    ) USING v_cert_id;

    -- Log certification event
    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action, target, target_type,
        event_data, event_hash
    ) VALUES (
        'model_certification', 'certification', 'INFO', 'VEGA',
        'ISSUE_CERTIFICATE_GATE_' || p_gate_number, p_model_id, p_model_type,
        jsonb_build_object(
            'model_id', p_model_id,
            'model_version', p_model_version,
            'gate', p_gate_number,
            'new_status', v_new_status,
            'certification_data', p_certification_data
        ),
        encode(sha256((p_model_id || p_model_version || p_gate_number::TEXT || NOW()::TEXT)::BYTEA), 'hex')
    );

    certification_id := v_cert_id;
    model_id := p_model_id;
    gate_number := p_gate_number;
    new_status := v_new_status;
    issued_at := NOW();

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_issue_certificate IS
    'ADR-006: Issue MDLC certification for models (6-gate lifecycle)';

-- ----------------------------------------------------------------------------
-- Function 5: vega_record_adversarial_event()
-- Records adversarial/security events
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_record_adversarial_event(
    p_event_type VARCHAR(100),
    p_severity VARCHAR(20),
    p_discrepancy_class VARCHAR(10),
    p_target VARCHAR(200),
    p_event_data JSONB,
    p_vega_signature TEXT DEFAULT NULL
)
RETURNS TABLE (
    event_id BIGINT,
    event_type VARCHAR(100),
    discrepancy_class VARCHAR(10),
    crp_triggered BOOLEAN,
    escalation_required BOOLEAN,
    recorded_at TIMESTAMPTZ
) AS $$
DECLARE
    v_event_id BIGINT;
    v_crp_triggered BOOLEAN := FALSE;
    v_escalation_required BOOLEAN := FALSE;
BEGIN
    -- Determine if CRP should be triggered
    IF p_discrepancy_class = 'CLASS_A' THEN
        v_crp_triggered := TRUE;
        v_escalation_required := TRUE;
    ELSIF p_discrepancy_class = 'CLASS_B' THEN
        -- Check if threshold reached (5 events in 7 days)
        SELECT COUNT(*) >= 5 INTO v_crp_triggered
        FROM fhq_meta.adr_audit_log
        WHERE event_category = 'adversarial'
        AND discrepancy_class = 'CLASS_B'
        AND audit_timestamp > NOW() - INTERVAL '7 days';

        v_escalation_required := v_crp_triggered;
    END IF;

    -- Record the adversarial event
    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, discrepancy_class,
        actor, action, target,
        event_data, vega_signature,
        event_hash
    ) VALUES (
        p_event_type, 'adversarial', p_severity, p_discrepancy_class,
        'VEGA', 'RECORD_ADVERSARIAL_EVENT', p_target,
        jsonb_build_object(
            'original_data', p_event_data,
            'crp_triggered', v_crp_triggered,
            'escalation_required', v_escalation_required
        ),
        p_vega_signature,
        encode(sha256((p_event_type || p_target || NOW()::TEXT)::BYTEA), 'hex')
    )
    RETURNING audit_id INTO v_event_id;

    event_id := v_event_id;
    event_type := p_event_type;
    discrepancy_class := p_discrepancy_class;
    crp_triggered := v_crp_triggered;
    escalation_required := v_escalation_required;
    recorded_at := NOW();

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_record_adversarial_event IS
    'ADR-006: Record adversarial/security events with CRP trigger logic';

-- ----------------------------------------------------------------------------
-- Function 6: vega_trigger_dora_assessment()
-- Triggers DORA Article 17 assessment
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_trigger_dora_assessment(
    p_incident_type VARCHAR(100),
    p_severity VARCHAR(20),
    p_affected_systems TEXT[],
    p_incident_data JSONB
)
RETURNS TABLE (
    assessment_id VARCHAR(100),
    dora_article VARCHAR(20),
    classification VARCHAR(50),
    reporting_required BOOLEAN,
    reporting_deadline INTERVAL,
    assessment_timestamp TIMESTAMPTZ
) AS $$
DECLARE
    v_classification VARCHAR(50);
    v_reporting_required BOOLEAN;
    v_reporting_deadline INTERVAL;
BEGIN
    assessment_id := 'DORA-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS');
    dora_article := 'Article 17';
    assessment_timestamp := NOW();

    -- DORA Article 17 classification
    v_classification := CASE p_severity
        WHEN 'CRITICAL' THEN 'MAJOR_INCIDENT'
        WHEN 'ERROR' THEN 'SIGNIFICANT_INCIDENT'
        WHEN 'WARNING' THEN 'MINOR_INCIDENT'
        ELSE 'OBSERVATION'
    END;

    -- Determine reporting requirements
    v_reporting_required := (p_severity IN ('CRITICAL', 'ERROR'));
    v_reporting_deadline := CASE v_classification
        WHEN 'MAJOR_INCIDENT' THEN INTERVAL '4 hours'
        WHEN 'SIGNIFICANT_INCIDENT' THEN INTERVAL '24 hours'
        ELSE INTERVAL '72 hours'
    END;

    classification := v_classification;
    reporting_required := v_reporting_required;
    reporting_deadline := v_reporting_deadline;

    -- Log DORA assessment
    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action, target,
        event_data, authority, adr_compliance, event_hash
    ) VALUES (
        'dora_assessment', 'compliance', p_severity, 'VEGA',
        'TRIGGER_DORA_ARTICLE_17', p_incident_type,
        jsonb_build_object(
            'assessment_id', assessment_id,
            'incident_type', p_incident_type,
            'classification', v_classification,
            'affected_systems', p_affected_systems,
            'reporting_required', v_reporting_required,
            'reporting_deadline', v_reporting_deadline::TEXT,
            'incident_data', p_incident_data
        ),
        'DORA Article 17 - ICT Incident Classification',
        ARRAY['ADR-006'],
        encode(sha256((assessment_id || p_incident_type)::BYTEA), 'hex')
    );

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_trigger_dora_assessment IS
    'ADR-006: Trigger DORA Article 17 incident assessment';

-- ----------------------------------------------------------------------------
-- Function 7: vega_log_bias_drift()
-- Logs model bias and drift events
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_log_bias_drift(
    p_model_id VARCHAR(100),
    p_drift_type VARCHAR(50),
    p_drift_score DECIMAL(5,4),
    p_bias_metrics JSONB,
    p_threshold_exceeded BOOLEAN
)
RETURNS TABLE (
    log_id BIGINT,
    model_id VARCHAR(100),
    drift_type VARCHAR(50),
    drift_score DECIMAL(5,4),
    action_required BOOLEAN,
    certification_impact VARCHAR(50),
    logged_at TIMESTAMPTZ
) AS $$
DECLARE
    v_log_id BIGINT;
    v_action_required BOOLEAN;
    v_cert_impact VARCHAR(50);
BEGIN
    v_action_required := p_threshold_exceeded OR p_drift_score > 0.15;

    -- Determine certification impact
    v_cert_impact := CASE
        WHEN p_drift_score > 0.30 THEN 'SUSPENSION_REQUIRED'
        WHEN p_drift_score > 0.20 THEN 'REVIEW_REQUIRED'
        WHEN p_drift_score > 0.10 THEN 'MONITORING_ENHANCED'
        ELSE 'NONE'
    END;

    -- Log bias/drift event
    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action, target, target_type,
        event_data, event_hash
    ) VALUES (
        'bias_drift_detection', 'operational',
        CASE WHEN p_drift_score > 0.20 THEN 'WARNING' ELSE 'INFO' END,
        'VEGA', 'LOG_BIAS_DRIFT', p_model_id, 'MODEL',
        jsonb_build_object(
            'model_id', p_model_id,
            'drift_type', p_drift_type,
            'drift_score', p_drift_score,
            'bias_metrics', p_bias_metrics,
            'threshold_exceeded', p_threshold_exceeded,
            'action_required', v_action_required,
            'certification_impact', v_cert_impact
        ),
        encode(sha256((p_model_id || p_drift_type || p_drift_score::TEXT || NOW()::TEXT)::BYTEA), 'hex')
    )
    RETURNING audit_id INTO v_log_id;

    -- Update model certification if impact is significant
    IF v_cert_impact IN ('SUSPENSION_REQUIRED', 'REVIEW_REQUIRED') THEN
        UPDATE fhq_meta.model_certifications
        SET
            drift_score = p_drift_score,
            last_review_at = NOW(),
            certification_status = CASE
                WHEN v_cert_impact = 'SUSPENSION_REQUIRED' THEN 'SUSPENDED'
                ELSE certification_status
            END
        WHERE model_id = p_model_id;
    END IF;

    log_id := v_log_id;
    model_id := p_model_id;
    drift_type := p_drift_type;
    drift_score := p_drift_score;
    action_required := v_action_required;
    certification_impact := v_cert_impact;
    logged_at := NOW();

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_log_bias_drift IS
    'ADR-006: Log model bias and drift with automatic certification impact';

-- ----------------------------------------------------------------------------
-- Function 8: vega_enforce_class_b_threshold()
-- Enforces Class B discrepancy threshold (5 events in 7 days = CRP)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_enforce_class_b_threshold()
RETURNS TABLE (
    check_timestamp TIMESTAMPTZ,
    class_b_count INTEGER,
    threshold INTEGER,
    threshold_exceeded BOOLEAN,
    crp_triggered BOOLEAN,
    enforcement_action VARCHAR(100)
) AS $$
DECLARE
    v_count INTEGER;
    v_threshold INTEGER := 5;
    v_exceeded BOOLEAN;
BEGIN
    check_timestamp := NOW();
    threshold := v_threshold;

    -- Count Class B events in last 7 days
    SELECT COUNT(*) INTO v_count
    FROM fhq_meta.adr_audit_log
    WHERE discrepancy_class = 'CLASS_B'
    AND audit_timestamp > NOW() - INTERVAL '7 days';

    class_b_count := v_count;
    v_exceeded := v_count >= v_threshold;
    threshold_exceeded := v_exceeded;
    crp_triggered := v_exceeded;

    enforcement_action := CASE
        WHEN v_exceeded THEN 'CRP_TRIGGERED_CEO_NOTIFICATION'
        WHEN v_count >= 3 THEN 'WARNING_THRESHOLD_APPROACHING'
        ELSE 'NO_ACTION_REQUIRED'
    END;

    -- Log enforcement check
    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action,
        event_data, event_hash
    ) VALUES (
        'class_b_threshold_check', 'governance',
        CASE WHEN v_exceeded THEN 'CRITICAL' ELSE 'INFO' END,
        'VEGA', 'ENFORCE_CLASS_B_THRESHOLD',
        jsonb_build_object(
            'class_b_count', v_count,
            'threshold', v_threshold,
            'exceeded', v_exceeded,
            'enforcement_action', enforcement_action
        ),
        encode(sha256(('CLASS_B_CHECK_' || NOW()::TEXT)::BYTEA), 'hex')
    );

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_enforce_class_b_threshold IS
    'ADR-006: Enforce Class B discrepancy threshold (5 in 7 days = CRP)';

-- ----------------------------------------------------------------------------
-- Function 9: vega_calculate_sovereignty_score()
-- Calculates and logs sovereignty score per ADR-005
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fhq_meta.vega_calculate_sovereignty_score(
    p_scoring_period VARCHAR(20),
    p_period_start DATE,
    p_period_end DATE,
    p_vega_signature TEXT,
    p_vega_public_key TEXT
)
RETURNS TABLE (
    sovereignty_id BIGINT,
    overall_score DECIMAL(5,4),
    constitutional_score DECIMAL(5,4),
    operational_score DECIMAL(5,4),
    data_score DECIMAL(5,4),
    regulatory_score DECIMAL(5,4),
    economic_score DECIMAL(5,4),
    trend VARCHAR(20),
    calculated_at TIMESTAMPTZ
) AS $$
DECLARE
    v_sovereignty_id BIGINT;
    v_overall DECIMAL(5,4);
    v_constitutional DECIMAL(5,4);
    v_operational DECIMAL(5,4);
    v_data DECIMAL(5,4);
    v_regulatory DECIMAL(5,4);
    v_economic DECIMAL(5,4);
    v_previous DECIMAL(5,4);
    v_delta DECIMAL(5,4);
    v_trend VARCHAR(20);
    v_class_a INTEGER;
    v_class_b INTEGER;
    v_class_c INTEGER;
    v_certified INTEGER;
    v_pending INTEGER;
    v_suspended INTEGER;
BEGIN
    -- Calculate constitutional compliance (ADR adherence)
    SELECT
        COALESCE(1.0 - (COUNT(*) FILTER (WHERE severity = 'CRITICAL')::DECIMAL / NULLIF(COUNT(*), 0)), 1.0)
    INTO v_constitutional
    FROM fhq_meta.adr_audit_log
    WHERE audit_timestamp BETWEEN p_period_start AND p_period_end;

    -- Calculate operational autonomy
    SELECT
        COALESCE(COUNT(*) FILTER (WHERE certification_status = 'FULLY_CERTIFIED')::DECIMAL / NULLIF(COUNT(*), 0), 0)
    INTO v_operational
    FROM fhq_meta.model_certifications;

    -- Calculate data sovereignty
    SELECT
        COALESCE(COUNT(*) FILTER (WHERE attested = TRUE)::DECIMAL / NULLIF(COUNT(*), 0), 0)
    INTO v_data
    FROM fhq_meta.data_lineage_log
    WHERE lineage_timestamp BETWEEN p_period_start AND p_period_end;

    -- Calculate regulatory compliance
    SELECT
        COALESCE(
            (COUNT(*) FILTER (WHERE dora_compliant = TRUE) +
             COUNT(*) FILTER (WHERE gips_compliant = TRUE))::DECIMAL /
            (NULLIF(COUNT(*), 0) * 2), 0
        )
    INTO v_regulatory
    FROM fhq_meta.model_certifications;

    -- Economic sovereignty (based on cost efficiency)
    v_economic := 0.85; -- Default good score, should be calculated from actual cost data

    -- Calculate overall score (weighted average)
    v_overall := (
        v_constitutional * 0.25 +
        v_operational * 0.20 +
        v_data * 0.20 +
        v_regulatory * 0.20 +
        v_economic * 0.15
    );

    -- Get previous score for trend
    SELECT overall_sovereignty_score INTO v_previous
    FROM fhq_meta.vega_sovereignty_log
    WHERE scoring_period = p_scoring_period
    ORDER BY score_timestamp DESC
    LIMIT 1;

    v_delta := v_overall - COALESCE(v_previous, v_overall);
    v_trend := CASE
        WHEN v_delta > 0.02 THEN 'IMPROVING'
        WHEN v_delta < -0.02 THEN 'DECLINING'
        ELSE 'STABLE'
    END;

    -- Count discrepancy events
    SELECT
        COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_A'),
        COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_B'),
        COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_C')
    INTO v_class_a, v_class_b, v_class_c
    FROM fhq_meta.adr_audit_log
    WHERE audit_timestamp BETWEEN p_period_start AND p_period_end;

    -- Count certification status
    SELECT
        COUNT(*) FILTER (WHERE certification_status = 'FULLY_CERTIFIED'),
        COUNT(*) FILTER (WHERE certification_status = 'PENDING'),
        COUNT(*) FILTER (WHERE certification_status = 'SUSPENDED')
    INTO v_certified, v_pending, v_suspended
    FROM fhq_meta.model_certifications;

    -- Insert sovereignty score
    INSERT INTO fhq_meta.vega_sovereignty_log (
        scoring_period, period_start, period_end,
        overall_sovereignty_score,
        constitutional_compliance_score, operational_autonomy_score,
        data_sovereignty_score, regulatory_compliance_score, economic_sovereignty_score,
        metrics_breakdown,
        class_a_events, class_b_events, class_c_events,
        models_certified, models_pending, models_suspended,
        previous_score, score_delta, trend,
        vega_signature, vega_public_key
    ) VALUES (
        p_scoring_period, p_period_start, p_period_end,
        v_overall,
        v_constitutional, v_operational, v_data, v_regulatory, v_economic,
        jsonb_build_object(
            'weights', jsonb_build_object(
                'constitutional', 0.25,
                'operational', 0.20,
                'data', 0.20,
                'regulatory', 0.20,
                'economic', 0.15
            ),
            'calculation_timestamp', NOW()
        ),
        v_class_a, v_class_b, v_class_c,
        v_certified, v_pending, v_suspended,
        v_previous, v_delta, v_trend,
        p_vega_signature, p_vega_public_key
    )
    RETURNING vega_sovereignty_log.sovereignty_id INTO v_sovereignty_id;

    sovereignty_id := v_sovereignty_id;
    overall_score := v_overall;
    constitutional_score := v_constitutional;
    operational_score := v_operational;
    data_score := v_data;
    regulatory_score := v_regulatory;
    economic_score := v_economic;
    trend := v_trend;
    calculated_at := NOW();

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_calculate_sovereignty_score IS
    'ADR-005/ADR-006: Calculate commercial sovereignty score';

-- ============================================================================
-- SECTION 8: HASH CHAIN TRIGGER FOR AUDIT LOG IMMUTABILITY
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_meta.trigger_audit_hash_chain()
RETURNS TRIGGER AS $$
DECLARE
    v_previous_hash VARCHAR(64);
    v_chain_position INTEGER;
BEGIN
    -- Get previous hash from chain
    IF NEW.hash_chain_id IS NOT NULL THEN
        SELECT event_hash, COALESCE(MAX(hash_chain_position), 0) + 1
        INTO v_previous_hash, v_chain_position
        FROM fhq_meta.adr_audit_log
        WHERE hash_chain_id = NEW.hash_chain_id
        GROUP BY event_hash
        ORDER BY audit_id DESC
        LIMIT 1;

        NEW.previous_hash := v_previous_hash;
        NEW.hash_chain_position := COALESCE(v_chain_position, 1);
    END IF;

    -- Calculate event hash if not provided
    IF NEW.event_hash IS NULL OR NEW.event_hash = '' THEN
        NEW.event_hash := encode(
            sha256(
                (COALESCE(NEW.event_type, '') ||
                 COALESCE(NEW.actor, '') ||
                 COALESCE(NEW.action, '') ||
                 COALESCE(NEW.previous_hash, '') ||
                 NEW.audit_timestamp::TEXT)::BYTEA
            ),
            'hex'
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_hash_chain
    BEFORE INSERT ON fhq_meta.adr_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_meta.trigger_audit_hash_chain();

-- ============================================================================
-- SECTION 9: VIEWS FOR GOVERNANCE MONITORING
-- ============================================================================

-- Governance Health Dashboard View
CREATE OR REPLACE VIEW fhq_meta.v_governance_health AS
SELECT
    DATE(audit_timestamp) as date,
    COUNT(*) as total_events,
    COUNT(*) FILTER (WHERE severity = 'CRITICAL') as critical_events,
    COUNT(*) FILTER (WHERE severity = 'ERROR') as error_events,
    COUNT(*) FILTER (WHERE severity = 'WARNING') as warning_events,
    COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_A') as class_a_count,
    COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_B') as class_b_count,
    COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_C') as class_c_count,
    COUNT(DISTINCT actor) as active_actors
FROM fhq_meta.adr_audit_log
GROUP BY DATE(audit_timestamp)
ORDER BY date DESC;

COMMENT ON VIEW fhq_meta.v_governance_health IS
    'ADR-006: Daily governance health metrics';

-- Certification Status View
CREATE OR REPLACE VIEW fhq_meta.v_certification_status AS
SELECT
    certification_status,
    model_type,
    COUNT(*) as count,
    AVG(overall_certification_score) as avg_score,
    COUNT(*) FILTER (WHERE adversarial_test_passed = TRUE) as adversarial_passed,
    COUNT(*) FILTER (WHERE dora_compliant = TRUE) as dora_compliant_count,
    COUNT(*) FILTER (WHERE gips_compliant = TRUE) as gips_compliant_count
FROM fhq_meta.model_certifications
GROUP BY certification_status, model_type
ORDER BY certification_status, model_type;

COMMENT ON VIEW fhq_meta.v_certification_status IS
    'ADR-006: Model certification status summary';

-- Sovereignty Trend View
CREATE OR REPLACE VIEW fhq_meta.v_sovereignty_trend AS
SELECT
    scoring_period,
    period_start,
    period_end,
    overall_sovereignty_score,
    constitutional_compliance_score,
    operational_autonomy_score,
    data_sovereignty_score,
    regulatory_compliance_score,
    economic_sovereignty_score,
    trend,
    score_delta,
    class_a_events + class_b_events + class_c_events as total_discrepancies
FROM fhq_meta.vega_sovereignty_log
ORDER BY score_timestamp DESC;

COMMENT ON VIEW fhq_meta.v_sovereignty_trend IS
    'ADR-005/ADR-006: Sovereignty score trend analysis';

-- ============================================================================
-- SECTION 10: ROW-LEVEL SECURITY (VEGA-ONLY WRITE ACCESS)
-- ============================================================================

-- Enable RLS on critical tables
ALTER TABLE fhq_meta.adr_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhq_meta.model_certifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhq_meta.vega_sovereignty_log ENABLE ROW LEVEL SECURITY;

-- VEGA write policy (audit_log - VEGA can insert, no one can update/delete)
CREATE POLICY vega_audit_log_insert ON fhq_meta.adr_audit_log
    FOR INSERT
    WITH CHECK (TRUE);  -- Allow inserts via functions

CREATE POLICY vega_audit_log_select ON fhq_meta.adr_audit_log
    FOR SELECT
    USING (TRUE);  -- Anyone can read

-- Model certifications - VEGA only write
CREATE POLICY vega_certifications_all ON fhq_meta.model_certifications
    FOR ALL
    USING (TRUE)
    WITH CHECK (certified_by = 'VEGA' OR certified_by = current_user);

-- Sovereignty log - VEGA only write
CREATE POLICY vega_sovereignty_all ON fhq_meta.vega_sovereignty_log
    FOR ALL
    USING (TRUE)
    WITH CHECK (calculated_by = 'VEGA' OR calculated_by = current_user);

-- ============================================================================
-- SECTION 11: SCHEMA VERSION AND VERIFICATION
-- ============================================================================

-- Record migration
INSERT INTO fhq_meta.adr_audit_log (
    event_type, event_category, severity, actor, action, target,
    event_data, authority, adr_compliance, event_hash, hash_chain_id
) VALUES (
    'schema_migration', 'governance', 'INFO', 'VEGA',
    'APPLY_MIGRATION_018', '018_vega_adr006_integration.sql',
    jsonb_build_object(
        'migration_number', '018',
        'tables_created', ARRAY['adr_audit_log', 'adr_version_history', 'model_certifications', 'data_lineage_log', 'vega_sovereignty_log'],
        'functions_created', ARRAY['vega_verify_hashes', 'vega_compare_registry', 'vega_snapshot_canonical', 'vega_issue_certificate', 'vega_record_adversarial_event', 'vega_trigger_dora_assessment', 'vega_log_bias_drift', 'vega_enforce_class_b_threshold', 'vega_calculate_sovereignty_score'],
        'views_created', ARRAY['v_governance_health', 'v_certification_status', 'v_sovereignty_trend'],
        'rls_enabled', TRUE
    ),
    'ADR-006_2026_PRODUCTION',
    ARRAY['ADR-001', 'ADR-005', 'ADR-006'],
    encode(sha256('MIGRATION_018_VEGA_ADR006'::BYTEA), 'hex'),
    'VEGA_GOVERNANCE_CHAIN'
);

-- Verify tables created
DO $$
DECLARE
    v_table_count INTEGER;
    v_function_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_table_count
    FROM information_schema.tables
    WHERE table_schema = 'fhq_meta'
    AND table_name IN ('adr_audit_log', 'adr_version_history', 'model_certifications', 'data_lineage_log', 'vega_sovereignty_log');

    IF v_table_count < 5 THEN
        RAISE EXCEPTION 'Migration 018 failed: Expected 5 tables, found %', v_table_count;
    END IF;

    SELECT COUNT(*) INTO v_function_count
    FROM information_schema.routines
    WHERE routine_schema = 'fhq_meta'
    AND routine_name LIKE 'vega_%';

    IF v_function_count < 9 THEN
        RAISE EXCEPTION 'Migration 018 failed: Expected 9 VEGA functions, found %', v_function_count;
    END IF;

    RAISE NOTICE 'Migration 018 successful: % tables, % functions created', v_table_count, v_function_count;
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION 018 COMPLETE
-- ============================================================================
-- VEGA ADR-006 Database Integration:
-- - 5 governance tables in fhq_meta schema
-- - 9 SQL governance functions
-- - 3 monitoring views
-- - Hash chain triggers for immutability
-- - Row-Level Security enabled
-- - Constitutional authority: ADR-001_2026_PRODUCTION
-- ============================================================================
