-- ============================================================================
-- ADR-006: VEGA AUTONOMY & GOVERNANCE ENGINE - CONSTITUTIONAL ESTABLISHMENT
-- ============================================================================
-- Migration: 023_adr006_vega_constitutional.sql
-- Authority: ADR-001_2026_PRODUCTION (System Charter)
-- Database: 127.0.0.1:54322 (Local Supabase PostgreSQL)
--
-- CONSTITUTIONAL HIERARCHY:
-- ADR-001 (System Charter)        ─┐
-- ADR-002 (Audit & Reconciliation) ├─→ FUNDAMENT (eksisterer, URØRT)
-- ADR-003 (Institutional Standards)│
-- ADR-004 (Change Gates)          ─┘
--                                  │
--                                  ▼
--                         ADR-006 (VEGA Charter) ← ETABLERES NÅ
--
-- SCOPE:
-- ✓ Registrer ADR-006 med dependencies til ADR-001-004
-- ✓ Opprett VEGA-tabeller (5 stk)
-- ✓ Opprett VEGA SQL-funksjoner (9 stk)
-- ✓ Seed VEGA rolle, key, authority, gate ownership
-- ✗ IKKE røre ADR-001-004 i adr_registry
-- ✗ IKKE endre eksisterende governance_state fra ADR-001
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: REGISTER ADR-006 (VEGA CHARTER)
-- Constitutional establishment on top of ADR-001-004 foundation
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_number,
    title,
    version,
    status,
    phase,
    content_hash,
    file_path,
    owner,
    approved_by,
    effective_date,
    supersedes,
    dependencies,
    classification,
    registered_by,
    vega_signature
) VALUES (
    'ADR-006',
    'VEGA Autonomy & Governance Engine Charter',
    '2026.PRODUCTION',
    'CANONICAL',
    'CANONICAL',
    encode(sha256('ADR-006_2026_PRODUCTION_VEGA_CHARTER'::bytea), 'hex'),
    '02_ADR/ADR-006_2026_PRODUCTION.md',
    'LARS',
    'CEO',
    '2025-11-11',
    NULL,
    ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004'],  -- Constitutional dependencies
    'Constitutional',
    'VEGA',
    encode(sha256('VEGA_SELF_ATTESTATION_ADR006_ESTABLISHMENT'::bytea), 'hex')
)
ON CONFLICT (adr_number) DO UPDATE SET
    status = 'CANONICAL',
    phase = 'CANONICAL',
    last_verified_at = NOW();

-- ============================================================================
-- SECTION 2: VEGA GOVERNANCE TABLES (5 tables)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 2.1: ADR Audit Log - Immutable governance audit trail with hash chains
-- ADR-006 Section 3.1: VEGA_SQL Database Governance Layer
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.adr_audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    audit_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Event classification
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL CHECK (
        event_category IN ('governance', 'certification', 'integrity',
                           'adversarial', 'compliance', 'operational', 'sovereignty')
    ),
    severity VARCHAR(20) NOT NULL DEFAULT 'INFO' CHECK (
        severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
    ),

    -- Discrepancy classification (ADR-002/ADR-010)
    discrepancy_class VARCHAR(10) DEFAULT 'NONE' CHECK (
        discrepancy_class IN ('CLASS_A', 'CLASS_B', 'CLASS_C', 'NONE')
    ),

    -- Actor and action
    actor VARCHAR(50) NOT NULL,
    action VARCHAR(200) NOT NULL,
    target VARCHAR(200),
    target_type VARCHAR(50),

    -- Event payload
    event_data JSONB NOT NULL DEFAULT '{}',

    -- Governance authority
    authority VARCHAR(500),
    adr_compliance TEXT[],

    -- Hash chain for immutability (BCBS-239 / ADR-002)
    previous_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL,
    hash_chain_id VARCHAR(100),
    hash_chain_position INTEGER,

    -- VEGA cryptographic attestation (ADR-008)
    vega_signature TEXT,
    vega_public_key TEXT,
    signature_verified BOOLEAN DEFAULT FALSE,

    -- Immutability enforcement
    immutable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_immutable CHECK (immutable = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_adr_audit_timestamp ON fhq_meta.adr_audit_log(audit_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_adr_audit_actor ON fhq_meta.adr_audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_adr_audit_event_type ON fhq_meta.adr_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_adr_audit_category ON fhq_meta.adr_audit_log(event_category);
CREATE INDEX IF NOT EXISTS idx_adr_audit_severity ON fhq_meta.adr_audit_log(severity);
CREATE INDEX IF NOT EXISTS idx_adr_audit_discrepancy ON fhq_meta.adr_audit_log(discrepancy_class)
    WHERE discrepancy_class != 'NONE';
CREATE INDEX IF NOT EXISTS idx_adr_audit_hash_chain ON fhq_meta.adr_audit_log(hash_chain_id, hash_chain_position);

COMMENT ON TABLE fhq_meta.adr_audit_log IS
    'ADR-006 Section 3.1: Immutable audit trail with SHA-256 hash chains for VEGA governance';

-- ----------------------------------------------------------------------------
-- 2.2: ADR Version History - Version lineage tracking
-- ADR-006 Section 3.1: fhq_meta.adr_version_history
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.adr_version_history (
    version_id BIGSERIAL PRIMARY KEY,
    adr_number VARCHAR(20) NOT NULL,
    adr_title VARCHAR(500) NOT NULL,
    version_number VARCHAR(50) NOT NULL,
    version_status VARCHAR(50) NOT NULL CHECK (
        version_status IN ('DRAFT', 'REVIEW', 'APPROVED', 'CANONICAL', 'SUPERSEDED', 'DEPRECATED')
    ),
    version_phase VARCHAR(50) CHECK (
        version_phase IN ('DRAFT', 'STAGING', 'PRODUCTION', 'CANONICAL')
    ),
    effective_date DATE,
    supersedes VARCHAR(500),
    superseded_by VARCHAR(500),
    owner VARCHAR(100) NOT NULL,
    approved_by VARCHAR(100),
    content_hash VARCHAR(64) NOT NULL,
    file_path VARCHAR(500),
    change_summary TEXT,
    change_type VARCHAR(50) CHECK (
        change_type IN ('INITIAL', 'AMENDMENT', 'REVISION', 'DEPRECATION', 'SUPERSESSION')
    ),
    vega_signature TEXT,
    signature_timestamp TIMESTAMPTZ,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    CONSTRAINT unique_adr_version UNIQUE (adr_number, version_number)
);

CREATE INDEX IF NOT EXISTS idx_adr_version_number ON fhq_meta.adr_version_history(adr_number);
CREATE INDEX IF NOT EXISTS idx_adr_version_status ON fhq_meta.adr_version_history(version_status);

COMMENT ON TABLE fhq_meta.adr_version_history IS
    'ADR-006 Section 3.1: Version lineage tracking for constitutional ADR documents';

-- ----------------------------------------------------------------------------
-- 2.3: Model Certifications - MDLC 6-Gate Certification Registry
-- ADR-006 Section 2.2: Model Governance
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.model_certifications (
    certification_id BIGSERIAL PRIMARY KEY,
    model_id VARCHAR(100) NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) CHECK (
        model_type IN ('REGIME_CLASSIFIER', 'SIGNAL_GENERATOR', 'RISK_MODEL',
                       'VALIDATION_MODEL', 'ORCHESTRATOR', 'GOVERNANCE')
    ),

    -- MDLC 6-Gate tracking (ADR-006 Section 2.2)
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
    certification_status VARCHAR(50) NOT NULL DEFAULT 'PENDING' CHECK (
        certification_status IN ('PENDING', 'GATE_1_APPROVED', 'GATE_2_APPROVED',
            'GATE_3_APPROVED', 'GATE_4_APPROVED', 'GATE_5_APPROVED',
            'FULLY_CERTIFIED', 'SUSPENDED', 'RETIRED', 'REJECTED')
    ),

    -- Certification metrics
    bias_score DECIMAL(5,4),
    drift_score DECIMAL(5,4),
    explainability_score DECIMAL(5,4),
    robustness_score DECIMAL(5,4),
    overall_certification_score DECIMAL(5,4),

    -- XAI explainability artifacts (ADR-006 Section 2.2)
    xai_artifacts JSONB DEFAULT '{}',

    -- Adversarial robustness (ADR-006 Section 2.2)
    adversarial_test_passed BOOLEAN DEFAULT FALSE,
    adversarial_test_timestamp TIMESTAMPTZ,
    adversarial_results JSONB DEFAULT '{}',

    -- Regulatory compliance flags
    iso_42001_compliant BOOLEAN DEFAULT FALSE,
    dora_compliant BOOLEAN DEFAULT FALSE,
    gips_compliant BOOLEAN DEFAULT FALSE,

    -- VEGA certification signature (ADR-006 Section 4)
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

    CONSTRAINT unique_model_cert UNIQUE (model_id, model_version)
);

CREATE INDEX IF NOT EXISTS idx_model_cert_model ON fhq_meta.model_certifications(model_id);
CREATE INDEX IF NOT EXISTS idx_model_cert_status ON fhq_meta.model_certifications(certification_status);
CREATE INDEX IF NOT EXISTS idx_model_cert_type ON fhq_meta.model_certifications(model_type);

COMMENT ON TABLE fhq_meta.model_certifications IS
    'ADR-006 Section 2.2: MDLC 6-Gate model certification registry with VEGA attestation';

-- ----------------------------------------------------------------------------
-- 2.4: Data Lineage Log - Data provenance tracking (BCBS-239)
-- ADR-006 Section 3.1: fhq_meta.data_lineage_log
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.data_lineage_log (
    lineage_id BIGSERIAL PRIMARY KEY,
    lineage_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
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
        transformation_type IN ('INGEST', 'TRANSFORM', 'AGGREGATE', 'DERIVE',
                                'VALIDATE', 'ENRICH', 'FILTER', 'JOIN', 'OUTPUT')
    ),
    transformation_logic TEXT,
    transformation_hash VARCHAR(64),

    -- Data quality
    quality_score DECIMAL(5,4),
    quality_checks JSONB DEFAULT '{}',

    -- Agent attribution
    processing_agent VARCHAR(50) NOT NULL,

    -- Hash chain for immutability
    previous_lineage_hash VARCHAR(64),
    lineage_hash VARCHAR(64) NOT NULL,

    -- VEGA attestation
    vega_signature TEXT,
    attested BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_lineage_position UNIQUE (lineage_chain_id, lineage_position)
);

CREATE INDEX IF NOT EXISTS idx_lineage_chain ON fhq_meta.data_lineage_log(lineage_chain_id, lineage_position);
CREATE INDEX IF NOT EXISTS idx_lineage_source ON fhq_meta.data_lineage_log(source_system, source_table);
CREATE INDEX IF NOT EXISTS idx_lineage_target ON fhq_meta.data_lineage_log(target_system, target_table);
CREATE INDEX IF NOT EXISTS idx_lineage_agent ON fhq_meta.data_lineage_log(processing_agent);

COMMENT ON TABLE fhq_meta.data_lineage_log IS
    'ADR-006/BCBS-239: Data provenance and lineage tracking with hash chains';

-- ----------------------------------------------------------------------------
-- 2.5: VEGA Sovereignty Log - Commercial sovereignty scores (ADR-005)
-- ADR-006 Section 3.1: fhq_meta.vega_sovereignty_log
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fhq_meta.vega_sovereignty_log (
    sovereignty_id BIGSERIAL PRIMARY KEY,
    score_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Scoring period (ADR-006 Section 5: Governance Rhythms)
    scoring_period VARCHAR(20) NOT NULL CHECK (
        scoring_period IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUAL')
    ),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Core sovereignty score (ADR-005)
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
    adr_compliance_status JSONB DEFAULT '{}',
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

    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    calculated_by VARCHAR(50) NOT NULL DEFAULT 'VEGA',

    CONSTRAINT unique_sovereignty_period UNIQUE (scoring_period, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_sovereignty_timestamp ON fhq_meta.vega_sovereignty_log(score_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sovereignty_period ON fhq_meta.vega_sovereignty_log(scoring_period, period_start);
CREATE INDEX IF NOT EXISTS idx_sovereignty_score ON fhq_meta.vega_sovereignty_log(overall_sovereignty_score DESC);

COMMENT ON TABLE fhq_meta.vega_sovereignty_log IS
    'ADR-005/ADR-006: Commercial sovereignty scores calculated by VEGA';

-- ============================================================================
-- SECTION 3: VEGA SQL GOVERNANCE FUNCTIONS (9 functions)
-- ADR-006 Section 3.1: SQL Governance Functions
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 3.1: vega_verify_hashes() - Hash chain integrity verification
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
-- 3.2: vega_compare_registry() - Registry reconciliation
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
    comparison_id := 'REG-CMP-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS');
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
                   0::BIGINT
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
-- 3.3: vega_snapshot_canonical() - Canonical snapshot creation
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

    -- Log snapshot event
    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action, target,
        event_data, authority, event_hash
    ) VALUES (
        'canonical_snapshot', 'governance', 'INFO', 'VEGA',
        'CREATE_CANONICAL_SNAPSHOT', p_snapshot_type,
        jsonb_build_object('snapshot_id', snapshot_id, 'hash', v_hash, 'items', items_count),
        p_authority, v_hash
    );

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_snapshot_canonical IS
    'ADR-006: Create canonical snapshot of governance state';

-- ----------------------------------------------------------------------------
-- 3.4: vega_issue_certificate() - MDLC certification issuance
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
        certification_status, vega_signature, vega_public_key, xai_artifacts
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

    -- Update gate timestamp
    EXECUTE format(
        'UPDATE fhq_meta.model_certifications SET gate_%s_%s = TRUE, gate_%s_timestamp = NOW() WHERE certification_id = $1',
        p_gate_number,
        CASE p_gate_number
            WHEN 1 THEN 'research' WHEN 2 THEN 'development' WHEN 3 THEN 'validation'
            WHEN 4 THEN 'staging' WHEN 5 THEN 'production' WHEN 6 THEN 'monitoring'
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
        jsonb_build_object('model_id', p_model_id, 'gate', p_gate_number, 'status', v_new_status),
        encode(sha256((p_model_id || p_gate_number::TEXT || NOW()::TEXT)::BYTEA), 'hex')
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
    'ADR-006 Section 4: Issue MDLC certification (VEGA constitutional responsibility)';

-- ----------------------------------------------------------------------------
-- 3.5: vega_record_adversarial_event() - Security event logging with CRP trigger
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
    -- Class A = immediate CRP (ADR-006 Section 3.3)
    IF p_discrepancy_class = 'CLASS_A' THEN
        v_crp_triggered := TRUE;
        v_escalation_required := TRUE;
    -- Class B = check threshold (5 in 7 days)
    ELSIF p_discrepancy_class = 'CLASS_B' THEN
        SELECT COUNT(*) >= 5 INTO v_crp_triggered
        FROM fhq_meta.adr_audit_log
        WHERE event_category = 'adversarial'
        AND discrepancy_class = 'CLASS_B'
        AND audit_timestamp > NOW() - INTERVAL '7 days';
        v_escalation_required := v_crp_triggered;
    END IF;

    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, discrepancy_class,
        actor, action, target, event_data, vega_signature, event_hash
    ) VALUES (
        p_event_type, 'adversarial', p_severity, p_discrepancy_class,
        'VEGA', 'RECORD_ADVERSARIAL_EVENT', p_target,
        jsonb_build_object('original_data', p_event_data, 'crp_triggered', v_crp_triggered),
        p_vega_signature,
        encode(sha256((p_event_type || p_target || NOW()::TEXT)::BYTEA), 'hex')
    ) RETURNING audit_id INTO v_event_id;

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
    'ADR-006 Section 3.3: Record adversarial events with CRP trigger logic';

-- ----------------------------------------------------------------------------
-- 3.6: vega_trigger_dora_assessment() - DORA Article 17 compliance
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

    v_classification := CASE p_severity
        WHEN 'CRITICAL' THEN 'MAJOR_INCIDENT'
        WHEN 'ERROR' THEN 'SIGNIFICANT_INCIDENT'
        WHEN 'WARNING' THEN 'MINOR_INCIDENT'
        ELSE 'OBSERVATION'
    END;

    v_reporting_required := (p_severity IN ('CRITICAL', 'ERROR'));
    v_reporting_deadline := CASE v_classification
        WHEN 'MAJOR_INCIDENT' THEN INTERVAL '4 hours'
        WHEN 'SIGNIFICANT_INCIDENT' THEN INTERVAL '24 hours'
        ELSE INTERVAL '72 hours'
    END;

    classification := v_classification;
    reporting_required := v_reporting_required;
    reporting_deadline := v_reporting_deadline;

    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action, target,
        event_data, authority, adr_compliance, event_hash
    ) VALUES (
        'dora_assessment', 'compliance', p_severity, 'VEGA',
        'TRIGGER_DORA_ARTICLE_17', p_incident_type,
        jsonb_build_object('assessment_id', assessment_id, 'classification', v_classification,
                           'affected_systems', p_affected_systems, 'reporting_required', v_reporting_required),
        'DORA Article 17', ARRAY['ADR-006'],
        encode(sha256((assessment_id || p_incident_type)::BYTEA), 'hex')
    );

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_trigger_dora_assessment IS
    'ADR-006 Section 2.4: Trigger DORA Article 17 incident assessment';

-- ----------------------------------------------------------------------------
-- 3.7: vega_log_bias_drift() - Model bias/drift monitoring
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
    v_cert_impact := CASE
        WHEN p_drift_score > 0.30 THEN 'SUSPENSION_REQUIRED'
        WHEN p_drift_score > 0.20 THEN 'REVIEW_REQUIRED'
        WHEN p_drift_score > 0.10 THEN 'MONITORING_ENHANCED'
        ELSE 'NONE'
    END;

    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action, target, target_type,
        event_data, event_hash
    ) VALUES (
        'bias_drift_detection', 'operational',
        CASE WHEN p_drift_score > 0.20 THEN 'WARNING' ELSE 'INFO' END,
        'VEGA', 'LOG_BIAS_DRIFT', p_model_id, 'MODEL',
        jsonb_build_object('drift_type', p_drift_type, 'drift_score', p_drift_score,
                           'bias_metrics', p_bias_metrics, 'certification_impact', v_cert_impact),
        encode(sha256((p_model_id || p_drift_type || NOW()::TEXT)::BYTEA), 'hex')
    ) RETURNING audit_id INTO v_log_id;

    -- Auto-suspend if drift too high
    IF v_cert_impact = 'SUSPENSION_REQUIRED' THEN
        UPDATE fhq_meta.model_certifications
        SET drift_score = p_drift_score, certification_status = 'SUSPENDED', last_review_at = NOW()
        WHERE model_id = p_model_id AND certification_status = 'FULLY_CERTIFIED';
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
    'ADR-006 Section 2.2: Log model bias/drift with automatic certification impact';

-- ----------------------------------------------------------------------------
-- 3.8: vega_enforce_class_b_threshold() - Class B CRP threshold enforcement
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

    INSERT INTO fhq_meta.adr_audit_log (
        event_type, event_category, severity, actor, action, event_data, event_hash
    ) VALUES (
        'class_b_threshold_check', 'governance',
        CASE WHEN v_exceeded THEN 'CRITICAL' ELSE 'INFO' END,
        'VEGA', 'ENFORCE_CLASS_B_THRESHOLD',
        jsonb_build_object('count', v_count, 'threshold', v_threshold, 'exceeded', v_exceeded),
        encode(sha256(('CLASS_B_CHECK_' || NOW()::TEXT)::BYTEA), 'hex')
    );

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_enforce_class_b_threshold IS
    'ADR-006 Section 3.3: Enforce Class B threshold (5 in 7 days = CRP)';

-- ----------------------------------------------------------------------------
-- 3.9: vega_calculate_sovereignty_score() - ADR-005 sovereignty calculation
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
    v_id BIGINT;
    v_overall DECIMAL(5,4);
    v_const DECIMAL(5,4);
    v_oper DECIMAL(5,4);
    v_data DECIMAL(5,4);
    v_reg DECIMAL(5,4);
    v_econ DECIMAL(5,4);
    v_prev DECIMAL(5,4);
    v_delta DECIMAL(5,4);
    v_trend VARCHAR(20);
    v_class_a INTEGER; v_class_b INTEGER; v_class_c INTEGER;
    v_certified INTEGER; v_pending INTEGER; v_suspended INTEGER;
BEGIN
    -- Constitutional compliance
    SELECT COALESCE(1.0 - (COUNT(*) FILTER (WHERE severity = 'CRITICAL')::DECIMAL / NULLIF(COUNT(*), 0)), 1.0)
    INTO v_const FROM fhq_meta.adr_audit_log
    WHERE audit_timestamp BETWEEN p_period_start AND p_period_end;

    -- Operational autonomy
    SELECT COALESCE(COUNT(*) FILTER (WHERE certification_status = 'FULLY_CERTIFIED')::DECIMAL / NULLIF(COUNT(*), 0), 1.0)
    INTO v_oper FROM fhq_meta.model_certifications;

    -- Data sovereignty
    SELECT COALESCE(COUNT(*) FILTER (WHERE attested = TRUE)::DECIMAL / NULLIF(COUNT(*), 0), 1.0)
    INTO v_data FROM fhq_meta.data_lineage_log
    WHERE lineage_timestamp BETWEEN p_period_start AND p_period_end;

    -- Regulatory compliance
    SELECT COALESCE((COUNT(*) FILTER (WHERE dora_compliant) + COUNT(*) FILTER (WHERE gips_compliant))::DECIMAL / (NULLIF(COUNT(*), 0) * 2), 1.0)
    INTO v_reg FROM fhq_meta.model_certifications;

    v_econ := 0.85;  -- Default economic score

    -- Weighted overall score
    v_overall := (v_const * 0.25 + v_oper * 0.20 + v_data * 0.20 + v_reg * 0.20 + v_econ * 0.15);

    -- Trend
    SELECT overall_sovereignty_score INTO v_prev FROM fhq_meta.vega_sovereignty_log
    WHERE scoring_period = p_scoring_period ORDER BY score_timestamp DESC LIMIT 1;

    v_delta := v_overall - COALESCE(v_prev, v_overall);
    v_trend := CASE WHEN v_delta > 0.02 THEN 'IMPROVING' WHEN v_delta < -0.02 THEN 'DECLINING' ELSE 'STABLE' END;

    -- Discrepancy counts
    SELECT COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_A'),
           COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_B'),
           COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_C')
    INTO v_class_a, v_class_b, v_class_c
    FROM fhq_meta.adr_audit_log WHERE audit_timestamp BETWEEN p_period_start AND p_period_end;

    -- Certification counts
    SELECT COUNT(*) FILTER (WHERE certification_status = 'FULLY_CERTIFIED'),
           COUNT(*) FILTER (WHERE certification_status = 'PENDING'),
           COUNT(*) FILTER (WHERE certification_status = 'SUSPENDED')
    INTO v_certified, v_pending, v_suspended FROM fhq_meta.model_certifications;

    INSERT INTO fhq_meta.vega_sovereignty_log (
        scoring_period, period_start, period_end, overall_sovereignty_score,
        constitutional_compliance_score, operational_autonomy_score, data_sovereignty_score,
        regulatory_compliance_score, economic_sovereignty_score, metrics_breakdown,
        class_a_events, class_b_events, class_c_events,
        models_certified, models_pending, models_suspended,
        previous_score, score_delta, trend, vega_signature, vega_public_key
    ) VALUES (
        p_scoring_period, p_period_start, p_period_end, v_overall,
        v_const, v_oper, v_data, v_reg, v_econ,
        jsonb_build_object('weights', jsonb_build_object('constitutional', 0.25, 'operational', 0.20,
                                                          'data', 0.20, 'regulatory', 0.20, 'economic', 0.15)),
        v_class_a, v_class_b, v_class_c, v_certified, v_pending, v_suspended,
        v_prev, v_delta, v_trend, p_vega_signature, p_vega_public_key
    ) RETURNING vega_sovereignty_log.sovereignty_id INTO v_id;

    sovereignty_id := v_id;
    overall_score := v_overall;
    constitutional_score := v_const;
    operational_score := v_oper;
    data_score := v_data;
    regulatory_score := v_reg;
    economic_score := v_econ;
    trend := v_trend;
    calculated_at := NOW();
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fhq_meta.vega_calculate_sovereignty_score IS
    'ADR-005/ADR-006: Calculate commercial sovereignty score';

-- ============================================================================
-- SECTION 4: HASH CHAIN TRIGGER FOR AUDIT LOG IMMUTABILITY
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_meta.trigger_audit_hash_chain()
RETURNS TRIGGER AS $$
DECLARE
    v_previous_hash VARCHAR(64);
    v_chain_position INTEGER;
BEGIN
    IF NEW.hash_chain_id IS NOT NULL THEN
        SELECT event_hash, COALESCE(MAX(hash_chain_position), 0) + 1
        INTO v_previous_hash, v_chain_position
        FROM fhq_meta.adr_audit_log
        WHERE hash_chain_id = NEW.hash_chain_id
        GROUP BY event_hash
        ORDER BY audit_id DESC LIMIT 1;

        NEW.previous_hash := v_previous_hash;
        NEW.hash_chain_position := COALESCE(v_chain_position, 1);
    END IF;

    IF NEW.event_hash IS NULL OR NEW.event_hash = '' THEN
        NEW.event_hash := encode(sha256((COALESCE(NEW.event_type, '') || COALESCE(NEW.actor, '') ||
                                         COALESCE(NEW.action, '') || COALESCE(NEW.previous_hash, '') ||
                                         NEW.audit_timestamp::TEXT)::BYTEA), 'hex');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_hash_chain ON fhq_meta.adr_audit_log;
CREATE TRIGGER trg_audit_hash_chain
    BEFORE INSERT ON fhq_meta.adr_audit_log
    FOR EACH ROW EXECUTE FUNCTION fhq_meta.trigger_audit_hash_chain();

-- ============================================================================
-- SECTION 5: VEGA ROLE, KEY, AUTHORITY (SEED DATA)
-- ============================================================================

-- 5.1: VEGA Executive Role (Chief Audit Officer)
INSERT INTO fhq_governance.executive_roles (
    agent_id, role_title, role_acronym, primary_function, responsibilities,
    authority_level, can_override, requires_approval_from, governing_adrs, status
) VALUES (
    'VEGA',
    'Chief Audit Officer',
    'CAO',
    'Autonomous constitutional governance, certification, and enforcement',
    ARRAY[
        'Model certification (MDLC 6-gate)',
        'Canonical snapshot validation',
        'XAI transparency enforcement',
        'Commercial sovereignty scoring',
        'CRP triggering',
        'DORA Article 17 assessments',
        'Adversarial event recording',
        'Lineage log maintenance',
        'Zero-override policy enforcement'
    ],
    10,  -- Highest authority level (ADR-006 Section 4)
    ARRAY[]::TEXT[],  -- Cannot be overridden except by CEO
    ARRAY['CEO'],     -- Only CEO can override VEGA
    ARRAY['ADR-006'],
    'ACTIVE'
)
ON CONFLICT (agent_id) DO UPDATE SET
    authority_level = 10,
    governing_adrs = ARRAY['ADR-006'],
    responsibilities = EXCLUDED.responsibilities;

-- 5.2: VEGA Ed25519 Key
INSERT INTO fhq_meta.agent_keys (
    agent_id, key_type, public_key_hex, public_key_fingerprint,
    key_purpose, status, registered_by
) VALUES (
    'VEGA',
    'Ed25519',
    encode(sha256('VEGA-ED25519-PUBLIC-KEY-ADR006-CONSTITUTIONAL'::bytea), 'hex'),
    encode(sha256('VEGA-FINGERPRINT-ADR006'::bytea), 'hex'),
    'signing',
    'ACTIVE',
    'VEGA'
)
ON CONFLICT DO NOTHING;

-- 5.3: VEGA Authority Matrix (Constitutional Responsibilities from ADR-006 Section 4)
INSERT INTO fhq_governance.authority_matrix (agent_id, action_type, resource_type, permission, resource_scope, governing_adr, established_by) VALUES
    -- Exclusive VEGA rights (ADR-006 Section 4)
    ('VEGA', 'CERTIFY_MODEL', 'model_certifications', 'ALLOW', 'fhq_meta.model_certifications', 'ADR-006', 'CEO'),
    ('VEGA', 'VALIDATE_SNAPSHOT', 'canonical_state', 'ALLOW', 'fhq_meta.*', 'ADR-006', 'CEO'),
    ('VEGA', 'ENFORCE_XAI', 'transparency', 'ALLOW', '*', 'ADR-006', 'CEO'),
    ('VEGA', 'SCORE_SOVEREIGNTY', 'sovereignty', 'ALLOW', 'fhq_meta.vega_sovereignty_log', 'ADR-006', 'CEO'),
    ('VEGA', 'TRIGGER_CRP', 'governance', 'ALLOW', '*', 'ADR-006', 'CEO'),
    ('VEGA', 'TRIGGER_DORA', 'compliance', 'ALLOW', '*', 'ADR-006', 'CEO'),
    ('VEGA', 'RECORD_ADVERSARIAL', 'adversarial', 'ALLOW', 'fhq_meta.adr_audit_log', 'ADR-006', 'CEO'),
    ('VEGA', 'MAINTAIN_LINEAGE', 'lineage', 'ALLOW', 'fhq_meta.data_lineage_log', 'ADR-006', 'CEO'),
    ('VEGA', 'ISSUE_ALERTS', 'governance', 'ALLOW', '*', 'ADR-006', 'CEO'),
    ('VEGA', 'ENFORCE_ZERO_OVERRIDE', 'policy', 'ALLOW', '*', 'ADR-006', 'CEO'),
    -- General VEGA permissions
    ('VEGA', 'WRITE', 'audit_log', 'ALLOW', 'fhq_meta.adr_audit_log', 'ADR-006', 'CEO'),
    ('VEGA', 'READ', 'all', 'ALLOW', '*', 'ADR-006', 'CEO')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 6: GATE OWNERSHIP (VEGA owns G3, shares G2)
-- ADR-006 establishes VEGA as audit authority
-- ============================================================================

-- Update gate registry to include VEGA as approver
UPDATE fhq_governance.gate_registry
SET required_approvers = array_append(required_approvers, 'VEGA')
WHERE gate_number = 2
AND NOT ('VEGA' = ANY(required_approvers));

UPDATE fhq_governance.gate_registry
SET required_approvers = ARRAY['VEGA', 'LARS']
WHERE gate_number = 3;

-- Add VEGA gate ownership records
INSERT INTO fhq_governance.gate_status (
    gate_id, component_id, component_type, status, notes, vega_signature
)
SELECT
    gr.gate_id,
    'VEGA_AUDIT_AUTHORITY',
    'GOVERNANCE',
    'PASSED',
    'VEGA established as constitutional auditor per ADR-006',
    encode(sha256('VEGA_GATE_OWNERSHIP_ADR006'::bytea), 'hex')
FROM fhq_governance.gate_registry gr
WHERE gr.gate_number IN (2, 3)
ON CONFLICT (gate_id, component_id) DO NOTHING;

-- ============================================================================
-- SECTION 7: GOVERNANCE RHYTHMS (ADR-006 Section 5)
-- ============================================================================

-- Create governance rhythms table if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.governance_rhythms (
    rhythm_id SERIAL PRIMARY KEY,
    rhythm_name VARCHAR(100) NOT NULL UNIQUE,
    rhythm_frequency VARCHAR(20) NOT NULL CHECK (
        rhythm_frequency IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUAL')
    ),
    responsible_agent VARCHAR(50) NOT NULL,
    actions JSONB NOT NULL,
    last_execution TIMESTAMPTZ,
    next_execution TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    governing_adr VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed VEGA governance rhythms (ADR-006 Section 5)
INSERT INTO fhq_governance.governance_rhythms (rhythm_name, rhythm_frequency, responsible_agent, actions, governing_adr) VALUES
    ('vega_daily_integrity', 'DAILY', 'VEGA',
     '{"checks": ["hash_verification", "adversarial_detection", "bias_drift_logging", "data_lineage_integrity"]}'::JSONB,
     'ADR-006'),
    ('vega_weekly_reconciliation', 'WEEKLY', 'VEGA',
     '{"checks": ["registry_reconciliation", "gips_2020_review", "mdlc_certification_consistency"]}'::JSONB,
     'ADR-006'),
    ('vega_monthly_snapshot', 'MONTHLY', 'VEGA',
     '{"checks": ["canonical_snapshot", "sovereignty_scoring", "kpi_review"]}'::JSONB,
     'ADR-006'),
    ('vega_quarterly_calibration', 'QUARTERLY', 'VEGA',
     '{"checks": ["capital_allocation_calibration", "strategy_weight_proposals"]}'::JSONB,
     'ADR-006'),
    ('vega_annual_audit', 'ANNUAL', 'VEGA',
     '{"checks": ["sovereignty_audit", "tlpt_alignment", "constitutional_review"]}'::JSONB,
     'ADR-006')
ON CONFLICT (rhythm_name) DO NOTHING;

-- ============================================================================
-- SECTION 8: VIEWS FOR GOVERNANCE MONITORING
-- ============================================================================

CREATE OR REPLACE VIEW fhq_meta.v_governance_health AS
SELECT
    DATE(audit_timestamp) as date,
    COUNT(*) as total_events,
    COUNT(*) FILTER (WHERE severity = 'CRITICAL') as critical_events,
    COUNT(*) FILTER (WHERE severity = 'ERROR') as error_events,
    COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_A') as class_a_count,
    COUNT(*) FILTER (WHERE discrepancy_class = 'CLASS_B') as class_b_count,
    COUNT(DISTINCT actor) as active_actors
FROM fhq_meta.adr_audit_log
GROUP BY DATE(audit_timestamp)
ORDER BY date DESC;

CREATE OR REPLACE VIEW fhq_meta.v_certification_status AS
SELECT
    certification_status,
    model_type,
    COUNT(*) as count,
    AVG(overall_certification_score) as avg_score,
    COUNT(*) FILTER (WHERE dora_compliant) as dora_compliant_count,
    COUNT(*) FILTER (WHERE gips_compliant) as gips_compliant_count
FROM fhq_meta.model_certifications
GROUP BY certification_status, model_type;

CREATE OR REPLACE VIEW fhq_meta.v_sovereignty_trend AS
SELECT
    scoring_period, period_start, period_end,
    overall_sovereignty_score,
    constitutional_compliance_score,
    operational_autonomy_score,
    data_sovereignty_score,
    regulatory_compliance_score,
    economic_sovereignty_score,
    trend, score_delta
FROM fhq_meta.vega_sovereignty_log
ORDER BY score_timestamp DESC;

-- ============================================================================
-- SECTION 9: LOG ADR-006 ESTABLISHMENT
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    event_type, event_category, severity, actor, action, target,
    event_data, authority, adr_compliance, event_hash, hash_chain_id
) VALUES (
    'adr_establishment', 'governance', 'INFO', 'VEGA',
    'ESTABLISH_ADR_006', 'ADR-006',
    jsonb_build_object(
        'adr_number', 'ADR-006',
        'title', 'VEGA Autonomy & Governance Engine Charter',
        'version', '2026.PRODUCTION',
        'dependencies', ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004'],
        'tables_created', ARRAY['adr_audit_log', 'adr_version_history', 'model_certifications', 'data_lineage_log', 'vega_sovereignty_log'],
        'functions_created', 9,
        'constitutional_authority', 'ADR-001_2026_PRODUCTION',
        'database', '127.0.0.1:54322'
    ),
    'ADR-001_2026_PRODUCTION',
    ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-006'],
    encode(sha256('ADR006_ESTABLISHMENT_CONSTITUTIONAL'::bytea), 'hex'),
    'VEGA_GOVERNANCE_CHAIN'
);

-- ============================================================================
-- SECTION 10: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_adr006_exists BOOLEAN;
    v_table_count INTEGER;
    v_function_count INTEGER;
    v_vega_role_exists BOOLEAN;
    v_vega_key_exists BOOLEAN;
    v_vega_authority_count INTEGER;
BEGIN
    -- Check ADR-006 registered
    SELECT EXISTS(SELECT 1 FROM fhq_meta.adr_registry WHERE adr_number = 'ADR-006' AND status = 'CANONICAL')
    INTO v_adr006_exists;

    -- Count VEGA tables
    SELECT COUNT(*) INTO v_table_count
    FROM information_schema.tables
    WHERE table_schema = 'fhq_meta'
    AND table_name IN ('adr_audit_log', 'adr_version_history', 'model_certifications', 'data_lineage_log', 'vega_sovereignty_log');

    -- Count VEGA functions
    SELECT COUNT(*) INTO v_function_count
    FROM information_schema.routines
    WHERE routine_schema = 'fhq_meta' AND routine_name LIKE 'vega_%';

    -- Check VEGA role
    SELECT EXISTS(SELECT 1 FROM fhq_governance.executive_roles WHERE agent_id = 'VEGA')
    INTO v_vega_role_exists;

    -- Check VEGA key
    SELECT EXISTS(SELECT 1 FROM fhq_meta.agent_keys WHERE agent_id = 'VEGA' AND status = 'ACTIVE')
    INTO v_vega_key_exists;

    -- Count VEGA authority entries
    SELECT COUNT(*) INTO v_vega_authority_count
    FROM fhq_governance.authority_matrix WHERE agent_id = 'VEGA';

    RAISE NOTICE '====================================================';
    RAISE NOTICE 'ADR-006 VEGA CONSTITUTIONAL ESTABLISHMENT';
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'Database: 127.0.0.1:54322';
    RAISE NOTICE '----------------------------------------------------';
    RAISE NOTICE 'ADR-006 registered: %', v_adr006_exists;
    RAISE NOTICE 'VEGA tables created: %/5', v_table_count;
    RAISE NOTICE 'VEGA functions created: %/9', v_function_count;
    RAISE NOTICE 'VEGA role exists: %', v_vega_role_exists;
    RAISE NOTICE 'VEGA key exists: %', v_vega_key_exists;
    RAISE NOTICE 'VEGA authority entries: %', v_vega_authority_count;
    RAISE NOTICE '----------------------------------------------------';
    RAISE NOTICE 'Constitutional hierarchy:';
    RAISE NOTICE '  ADR-001 (System Charter)        ─┐';
    RAISE NOTICE '  ADR-002 (Audit & Reconciliation) ├→ FUNDAMENT';
    RAISE NOTICE '  ADR-003 (Institutional Standards)│';
    RAISE NOTICE '  ADR-004 (Change Gates)          ─┘';
    RAISE NOTICE '                                   │';
    RAISE NOTICE '                                   ▼';
    RAISE NOTICE '                          ADR-006 (VEGA) ✓';
    RAISE NOTICE '====================================================';

    IF NOT v_adr006_exists THEN
        RAISE EXCEPTION 'ADR-006 not registered!';
    END IF;

    IF v_table_count < 5 THEN
        RAISE EXCEPTION 'Expected 5 VEGA tables, found %', v_table_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- ADR-006 ESTABLISHMENT COMPLETE
-- ============================================================================
-- VEGA Autonomy & Governance Engine Charter established on constitutional
-- foundation of ADR-001 through ADR-004.
--
-- VEGA is now the autonomous constitutional governance AI-engine responsible
-- for upholding constitutional integrity, AI governance, model certification,
-- data lineage, adversarial defense, DORA compliance, and commercial
-- sovereignty scoring.
--
-- No agent, including STIG or LARS, may override VEGA decisions.
-- Only CEO may issue constitutional exceptions.
-- ============================================================================
