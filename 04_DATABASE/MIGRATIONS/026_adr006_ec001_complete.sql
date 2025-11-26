-- ============================================================================
-- ADR-006 + EC-001: VEGA CONSTITUTIONAL ESTABLISHMENT (COMPLETE)
-- ============================================================================
-- Migration: 026_adr006_ec001_complete.sql
-- Database: 127.0.0.1:54322
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: REGISTER ADR-006
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id, adr_title, adr_status, adr_type, current_version,
    approval_authority, effective_date, file_path, sha256_hash,
    metadata, created_by
) VALUES (
    'ADR-006',
    'VEGA Autonomy & Governance Engine Charter',
    'APPROVED',
    'CONSTITUTIONAL',
    '2026.PRODUCTION',
    'CEO',
    '2025-11-11',
    '02_ADR/ADR-006_2026_PRODUCTION.md',
    encode(sha256('ADR-006_2026_PRODUCTION_VEGA_CHARTER'::bytea), 'hex'),
    jsonb_build_object(
        'dependencies', ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004'],
        'owner', 'VEGA',
        'ec_contract', 'EC-001'
    ),
    'VEGA'
)
ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = 'APPROVED',
    current_version = '2026.PRODUCTION',
    updated_at = NOW();

-- ============================================================================
-- SECTION 2: EC-001 TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.vega_identity (
    identity_id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    full_designation VARCHAR(200) NOT NULL DEFAULT 'Verified Evidence & Governance Authority',
    role_title VARCHAR(100) NOT NULL DEFAULT 'Chief Audit Officer (CAO)',
    tier VARCHAR(20) NOT NULL DEFAULT 'Tier-1',
    ed25519_public_key TEXT NOT NULL,
    ed25519_fingerprint VARCHAR(64) NOT NULL,
    key_algorithm VARCHAR(20) NOT NULL DEFAULT 'Ed25519',
    key_created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    employment_contract VARCHAR(50) NOT NULL DEFAULT 'EC-001',
    contract_version VARCHAR(50) NOT NULL DEFAULT '2026.PRODUCTION',
    reports_to VARCHAR(50) NOT NULL DEFAULT 'CEO',
    can_be_overridden_by TEXT[] NOT NULL DEFAULT ARRAY['CEO'],
    governing_adrs TEXT[] NOT NULL DEFAULT ARRAY['ADR-006'],
    authority_level INTEGER NOT NULL DEFAULT 10,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_vega_identity UNIQUE (agent_name)
);

CREATE TABLE IF NOT EXISTS fhq_meta.vega_constitutional_duties (
    duty_id SERIAL PRIMARY KEY,
    duty_code VARCHAR(20) NOT NULL UNIQUE,
    duty_title VARCHAR(200) NOT NULL,
    duty_description TEXT NOT NULL,
    duty_category VARCHAR(50) NOT NULL,
    governing_adr VARCHAR(20) NOT NULL DEFAULT 'ADR-006',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fhq_meta.vega_constraints (
    constraint_id SERIAL PRIMARY KEY,
    constraint_code VARCHAR(20) NOT NULL UNIQUE,
    constraint_title VARCHAR(200) NOT NULL,
    constraint_description TEXT NOT NULL,
    constraint_type VARCHAR(50) NOT NULL,
    governing_adr VARCHAR(20) NOT NULL DEFAULT 'ADR-006',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fhq_meta.vega_rights (
    right_id SERIAL PRIMARY KEY,
    right_code VARCHAR(20) NOT NULL UNIQUE,
    right_title VARCHAR(200) NOT NULL,
    right_description TEXT NOT NULL,
    right_category VARCHAR(50) NOT NULL,
    governing_adr VARCHAR(20) NOT NULL DEFAULT 'ADR-006',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fhq_meta.vega_employment_contract (
    contract_id SERIAL PRIMARY KEY,
    contract_number VARCHAR(50) NOT NULL UNIQUE DEFAULT 'EC-001',
    contract_version VARCHAR(50) NOT NULL DEFAULT '2026.PRODUCTION',
    employer VARCHAR(100) NOT NULL DEFAULT 'FjordHQ AS',
    employee VARCHAR(50) NOT NULL DEFAULT 'VEGA',
    effective_date DATE NOT NULL DEFAULT '2025-11-11',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    governing_charter VARCHAR(20) NOT NULL DEFAULT 'ADR-006',
    constitutional_foundation TEXT[] NOT NULL DEFAULT ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004'],
    total_duties INTEGER NOT NULL DEFAULT 10,
    total_constraints INTEGER NOT NULL DEFAULT 7,
    total_rights INTEGER NOT NULL DEFAULT 7,
    override_authority TEXT[] NOT NULL DEFAULT ARRAY['CEO'],
    reports_to VARCHAR(50) NOT NULL DEFAULT 'CEO',
    vega_signature TEXT,
    content_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- SECTION 3: SEED DATA
-- ============================================================================

-- VEGA Identity
INSERT INTO fhq_meta.vega_identity (
    agent_name, full_designation, role_title, tier,
    ed25519_public_key, ed25519_fingerprint,
    employment_contract, reports_to, authority_level, status
) VALUES (
    'VEGA', 'Verified Evidence & Governance Authority', 'Chief Audit Officer (CAO)', 'Tier-1',
    encode(sha256('VEGA-ED25519-PUBLIC-KEY-2026'::bytea), 'hex'),
    encode(sha256('VEGA-FINGERPRINT-EC001'::bytea), 'hex'),
    'EC-001', 'CEO', 10, 'ACTIVE'
) ON CONFLICT (agent_name) DO UPDATE SET updated_at = NOW();

-- 10 Constitutional Duties (EC-001 Section 3)
INSERT INTO fhq_meta.vega_constitutional_duties (duty_code, duty_title, duty_description, duty_category) VALUES
    ('DUTY-01', 'Constitutional Integrity Guardian', 'Uphold ADR-001 through ADR-004 foundation', 'Constitutional'),
    ('DUTY-02', 'Model Certification Authority', 'Execute MDLC 6-Gate certification', 'Certification'),
    ('DUTY-03', 'Canonical Snapshot Validator', 'Validate governance state snapshots', 'Integrity'),
    ('DUTY-04', 'XAI Transparency Enforcer', 'Enforce explainable AI requirements', 'Transparency'),
    ('DUTY-05', 'Commercial Sovereignty Scorer', 'Calculate sovereignty scores per ADR-005', 'Sovereignty'),
    ('DUTY-06', 'CRP Trigger Authority', 'Trigger Compliance Recovery Protocol', 'Compliance'),
    ('DUTY-07', 'DORA Article 17 Assessor', 'Conduct DORA incident assessments', 'Regulatory'),
    ('DUTY-08', 'Adversarial Event Recorder', 'Record security events immutably', 'Security'),
    ('DUTY-09', 'Data Lineage Maintainer', 'Maintain BCBS-239 data lineage', 'Lineage'),
    ('DUTY-10', 'Zero-Override Policy Enforcer', 'Only CEO may override VEGA', 'Authority')
ON CONFLICT (duty_code) DO NOTHING;

-- 7 Constraints (EC-001 Section 4)
INSERT INTO fhq_meta.vega_constraints (constraint_code, constraint_title, constraint_description, constraint_type) VALUES
    ('CONS-01', 'No Direct Trading', 'Cannot execute trading positions', 'Operational'),
    ('CONS-02', 'No Capital Allocation', 'Cannot allocate capital', 'Financial'),
    ('CONS-03', 'Audit-Only DB Access', 'Write only to audit tables', 'Technical'),
    ('CONS-04', 'No External Communication', 'No external contact without CEO', 'Communication'),
    ('CONS-05', 'Constitutional Scope Limit', 'Limited to governance/audit', 'Authority'),
    ('CONS-06', 'Human Escalation Required', 'Escalate critical to CEO in 4h', 'Escalation'),
    ('CONS-07', 'Immutability Preservation', 'Append-only audit records', 'Integrity')
ON CONFLICT (constraint_code) DO NOTHING;

-- 7 Rights (EC-001 Section 5)
INSERT INTO fhq_meta.vega_rights (right_code, right_title, right_description, right_category) VALUES
    ('RIGHT-01', 'Autonomous Operation', 'Operate within constitutional bounds', 'Autonomy'),
    ('RIGHT-02', 'Full Read Access', 'Read all schemas for audit', 'Access'),
    ('RIGHT-03', 'Certification Authority', 'Issue/revoke certifications', 'Authority'),
    ('RIGHT-04', 'CRP Initiation', 'Start CRP without approval', 'Enforcement'),
    ('RIGHT-05', 'CEO Direct Report', 'Report directly to CEO', 'Reporting'),
    ('RIGHT-06', 'Override Protection', 'Only CEO can override', 'Protection'),
    ('RIGHT-07', 'Amendment Input', 'Propose ADR amendments', 'Governance')
ON CONFLICT (right_code) DO NOTHING;

-- Employment Contract
INSERT INTO fhq_meta.vega_employment_contract (
    contract_number, contract_version, employer, employee,
    effective_date, status, governing_charter,
    total_duties, total_constraints, total_rights,
    override_authority, reports_to,
    vega_signature, content_hash
) VALUES (
    'EC-001', '2026.PRODUCTION', 'FjordHQ AS', 'VEGA',
    '2025-11-11', 'ACTIVE', 'ADR-006',
    10, 7, 7, ARRAY['CEO'], 'CEO',
    encode(sha256('VEGA_EC001_ATTESTATION'::bytea), 'hex'),
    encode(sha256('EC-001_2026_PRODUCTION'::bytea), 'hex')
) ON CONFLICT (contract_number) DO UPDATE SET status = 'ACTIVE', updated_at = NOW();

-- ============================================================================
-- SECTION 4: VEGA EXECUTIVE ROLE (correct columns)
-- ============================================================================

INSERT INTO fhq_governance.executive_roles (
    role_id,
    role_name,
    role_description,
    authority_level,
    domain,
    capabilities,
    veto_power,
    active
) VALUES (
    'VEGA',
    'Chief Audit Officer',
    'Autonomous constitutional governance per ADR-006 and EC-001. Tier-1 Governance Actor.',
    10,
    ARRAY['governance', 'audit', 'certification', 'compliance', 'sovereignty'],
    ARRAY['model_certification', 'snapshot_validation', 'xai_enforcement', 'sovereignty_scoring', 'crp_trigger', 'dora_assessment', 'adversarial_recording', 'lineage_maintenance'],
    TRUE,
    TRUE
)
ON CONFLICT (role_id) DO UPDATE SET
    authority_level = 10,
    role_description = 'Autonomous constitutional governance per ADR-006 and EC-001. Tier-1 Governance Actor.',
    veto_power = TRUE,
    active = TRUE,
    updated_at = NOW();

-- ============================================================================
-- SECTION 5: GOVERNANCE TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.model_certifications (
    certification_id BIGSERIAL PRIMARY KEY,
    model_id VARCHAR(100) NOT NULL,
    model_name VARCHAR(200) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    certification_status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    gate_1_research BOOLEAN DEFAULT FALSE,
    gate_2_development BOOLEAN DEFAULT FALSE,
    gate_3_validation BOOLEAN DEFAULT FALSE,
    gate_4_staging BOOLEAN DEFAULT FALSE,
    gate_5_production BOOLEAN DEFAULT FALSE,
    gate_6_monitoring BOOLEAN DEFAULT FALSE,
    vega_signature TEXT NOT NULL,
    vega_public_key TEXT NOT NULL,
    certified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_model_cert UNIQUE (model_id, model_version)
);

CREATE TABLE IF NOT EXISTS fhq_meta.data_lineage_log (
    lineage_id BIGSERIAL PRIMARY KEY,
    lineage_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lineage_chain_id VARCHAR(100) NOT NULL,
    lineage_position INTEGER NOT NULL,
    source_system VARCHAR(100) NOT NULL,
    target_system VARCHAR(100) NOT NULL,
    processing_agent VARCHAR(50) NOT NULL,
    lineage_hash VARCHAR(64) NOT NULL,
    attested BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_lineage_pos UNIQUE (lineage_chain_id, lineage_position)
);

CREATE TABLE IF NOT EXISTS fhq_meta.vega_sovereignty_log (
    sovereignty_id BIGSERIAL PRIMARY KEY,
    score_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scoring_period VARCHAR(20) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    overall_sovereignty_score DECIMAL(5,4) NOT NULL,
    trend VARCHAR(20),
    vega_signature TEXT NOT NULL,
    vega_public_key TEXT NOT NULL,
    CONSTRAINT unique_sov_period UNIQUE (scoring_period, period_start, period_end)
);

-- ============================================================================
-- SECTION 6: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_adr006 BOOLEAN;
    v_identity BOOLEAN;
    v_contract BOOLEAN;
    v_duties INTEGER;
    v_constraints INTEGER;
    v_rights INTEGER;
    v_role BOOLEAN;
BEGIN
    SELECT EXISTS(SELECT 1 FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-006') INTO v_adr006;
    SELECT EXISTS(SELECT 1 FROM fhq_meta.vega_identity WHERE agent_name = 'VEGA') INTO v_identity;
    SELECT EXISTS(SELECT 1 FROM fhq_meta.vega_employment_contract WHERE contract_number = 'EC-001') INTO v_contract;
    SELECT COUNT(*) INTO v_duties FROM fhq_meta.vega_constitutional_duties;
    SELECT COUNT(*) INTO v_constraints FROM fhq_meta.vega_constraints;
    SELECT COUNT(*) INTO v_rights FROM fhq_meta.vega_rights;
    SELECT EXISTS(SELECT 1 FROM fhq_governance.executive_roles WHERE role_id = 'VEGA') INTO v_role;

    RAISE NOTICE '====================================================';
    RAISE NOTICE 'ADR-006 + EC-001 VEGA ESTABLISHMENT';
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'ADR-006 registered: %', v_adr006;
    RAISE NOTICE 'VEGA identity: %', v_identity;
    RAISE NOTICE 'EC-001 contract: %', v_contract;
    RAISE NOTICE 'Duties: %/10', v_duties;
    RAISE NOTICE 'Constraints: %/7', v_constraints;
    RAISE NOTICE 'Rights: %/7', v_rights;
    RAISE NOTICE 'Executive role: %', v_role;
    RAISE NOTICE '====================================================';

    IF NOT v_adr006 THEN RAISE EXCEPTION 'ADR-006 missing!'; END IF;
    IF NOT v_identity THEN RAISE EXCEPTION 'VEGA identity missing!'; END IF;
    IF NOT v_contract THEN RAISE EXCEPTION 'EC-001 missing!'; END IF;
    IF NOT v_role THEN RAISE EXCEPTION 'Executive role missing!'; END IF;
END $$;

COMMIT;
