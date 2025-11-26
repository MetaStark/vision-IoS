-- ============================================================================
-- ADR INGEST & ED25519 KEY REGISTRATION
-- ============================================================================
-- Migration: 020_adr_ingest_keys.sql
-- Authority: ADR-001_2026_PRODUCTION
-- Database: 127.0.0.1:54322 (Local Supabase PostgreSQL)
--
-- PURPOSE:
-- 1. Ingest ADR-001 → ADR-015 into fhq_meta.adr_registry
-- 2. Generate and register Ed25519 keys for all 7 agents
-- 3. Initialize key archival log
-- 4. Create authority matrix entries
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: INGEST ADR-001 → ADR-015
-- ============================================================================

-- ADR-001: System Charter
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies, governing_adrs
) VALUES
    ('ADR-001', 'FjordHQ System Charter', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-001-SYSTEM-CHARTER-V1'::bytea), 'hex'),
     'LARS', 'CEO', '2025-11-11', 'Constitutional', NULL,
     ARRAY[]::TEXT[])
ON CONFLICT (adr_number) DO UPDATE SET
    status = 'CANONICAL', last_verified_at = NOW();

-- ADR-002: Audit & Error Reconciliation
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-002', 'Audit & Error Reconciliation Protocol', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-002-AUDIT-RECONCILIATION-V1'::bytea), 'hex'),
     'LARS', 'CEO', '2025-11-11', 'Constitutional', ARRAY['ADR-001'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-003: Institutional Standards
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-003', 'Institutional Engineering Standards', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-003-INSTITUTIONAL-STANDARDS-V1'::bytea), 'hex'),
     'CODE', 'LARS', '2025-11-11', 'Technical', ARRAY['ADR-001'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-004: Change Gates
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-004', 'Production Change Gates (G0-G4)', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-004-CHANGE-GATES-V1'::bytea), 'hex'),
     'LARS', 'CEO', '2025-11-11', 'Constitutional', ARRAY['ADR-001'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-005: Mission & Vision
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-005', 'FjordHQ Mission & Commercial Sovereignty', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-005-MISSION-VISION-V1'::bytea), 'hex'),
     'LARS', 'CEO', '2025-11-11', 'Constitutional', ARRAY['ADR-001'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-006: VEGA Autonomy & Governance Engine Charter
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-006', 'VEGA Autonomy & Governance Engine Charter', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-006-VEGA-CHARTER-V1'::bytea), 'hex'),
     'LARS', 'CEO', '2025-11-11', 'Constitutional', ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-005'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-007: FINN Market Analysis Protocol
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-007', 'FINN+ Market Analysis & Regime Classification', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-007-FINN-ANALYSIS-V1'::bytea), 'hex'),
     'FINN', 'LARS', '2025-11-11', 'Operational', ARRAY['ADR-001', 'ADR-008'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-008: Cryptographic Signature Standard
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-008', 'Ed25519 Cryptographic Signature Standard', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-008-CRYPTO-SIGNATURES-V1'::bytea), 'hex'),
     'STIG', 'LARS', '2025-11-11', 'Technical', ARRAY['ADR-001', 'ADR-002'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-009: Determinism & Reproducibility
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-009', 'Determinism & Reproducibility Standards', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-009-DETERMINISM-V1'::bytea), 'hex'),
     'VEGA', 'LARS', '2025-11-11', 'Technical', ARRAY['ADR-001', 'ADR-006'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-010: Reconciliation Protocol
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-010', 'Canonical Reconciliation Protocol (CRP)', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-010-RECONCILIATION-V1'::bytea), 'hex'),
     'STIG', 'LARS', '2025-11-11', 'Operational', ARRAY['ADR-001', 'ADR-002', 'ADR-006'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-011: Data Lineage & Provenance
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-011', 'Data Lineage & Provenance (BCBS-239)', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-011-DATA-LINEAGE-V1'::bytea), 'hex'),
     'LINE', 'LARS', '2025-11-11', 'Technical', ARRAY['ADR-001', 'ADR-002'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-012: Economic Safety & Cost Control
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-012', 'Economic Safety & LLM Cost Control', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-012-ECONOMIC-SAFETY-V1'::bytea), 'hex'),
     'LARS', 'CEO', '2025-11-11', 'Operational', ARRAY['ADR-001', 'ADR-006'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-013: DORA Compliance
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-013', 'DORA Digital Operational Resilience', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-013-DORA-COMPLIANCE-V1'::bytea), 'hex'),
     'VEGA', 'LARS', '2025-11-11', 'Constitutional', ARRAY['ADR-001', 'ADR-006'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-014: Canonical ADR Governance
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-014', 'Canonical ADR Governance Framework', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-014-ADR-GOVERNANCE-V1'::bytea), 'hex'),
     'LARS', 'CEO', '2025-11-11', 'Constitutional', ARRAY['ADR-001'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ADR-015: Meta-Governance Framework
INSERT INTO fhq_meta.adr_registry (
    adr_number, title, version, status, phase, content_hash, owner, approved_by,
    effective_date, classification, dependencies
) VALUES
    ('ADR-015', 'Meta-Governance & Constitutional Framework', '2026.PRODUCTION', 'CANONICAL', 'CANONICAL',
     encode(sha256('ADR-015-META-GOVERNANCE-V1'::bytea), 'hex'),
     'LARS', 'CEO', '2025-11-11', 'Constitutional', ARRAY['ADR-001', 'ADR-006', 'ADR-014'])
ON CONFLICT (adr_number) DO UPDATE SET status = 'CANONICAL', last_verified_at = NOW();

-- ============================================================================
-- SECTION 2: REGISTER ED25519 KEYS FOR ALL AGENTS
-- Note: These are placeholder public keys. Real keys should be generated
-- by the key generation service and imported securely.
-- ============================================================================

-- Generate deterministic placeholder keys for each agent
-- In production, these would be generated by a secure key ceremony

INSERT INTO fhq_meta.agent_keys (
    agent_id, key_type, public_key_hex, public_key_fingerprint, key_purpose, status
) VALUES
    ('LARS', 'Ed25519',
     encode(sha256('LARS-ED25519-PUBLIC-KEY-PLACEHOLDER'::bytea), 'hex'),
     encode(sha256('LARS-FINGERPRINT'::bytea), 'hex'),
     'signing', 'ACTIVE'),

    ('STIG', 'Ed25519',
     encode(sha256('STIG-ED25519-PUBLIC-KEY-PLACEHOLDER'::bytea), 'hex'),
     encode(sha256('STIG-FINGERPRINT'::bytea), 'hex'),
     'signing', 'ACTIVE'),

    ('VEGA', 'Ed25519',
     encode(sha256('VEGA-ED25519-PUBLIC-KEY-PLACEHOLDER'::bytea), 'hex'),
     encode(sha256('VEGA-FINGERPRINT'::bytea), 'hex'),
     'signing', 'ACTIVE'),

    ('LINE', 'Ed25519',
     encode(sha256('LINE-ED25519-PUBLIC-KEY-PLACEHOLDER'::bytea), 'hex'),
     encode(sha256('LINE-FINGERPRINT'::bytea), 'hex'),
     'signing', 'ACTIVE'),

    ('FINN', 'Ed25519',
     encode(sha256('FINN-ED25519-PUBLIC-KEY-PLACEHOLDER'::bytea), 'hex'),
     encode(sha256('FINN-FINGERPRINT'::bytea), 'hex'),
     'signing', 'ACTIVE'),

    ('CODE', 'Ed25519',
     encode(sha256('CODE-ED25519-PUBLIC-KEY-PLACEHOLDER'::bytea), 'hex'),
     encode(sha256('CODE-FINGERPRINT'::bytea), 'hex'),
     'signing', 'ACTIVE'),

    ('CEO', 'Ed25519',
     encode(sha256('CEO-ED25519-PUBLIC-KEY-PLACEHOLDER'::bytea), 'hex'),
     encode(sha256('CEO-FINGERPRINT'::bytea), 'hex'),
     'signing', 'ACTIVE')
ON CONFLICT ON CONSTRAINT unique_active_agent_key DO NOTHING;

-- Log key creation events
INSERT INTO fhq_meta.key_archival_log (key_id, agent_id, event_type, public_key_fingerprint, event_reason, event_hash)
SELECT
    key_id,
    agent_id,
    'CREATED',
    public_key_fingerprint,
    'Initial key registration via Migration 020',
    encode(sha256((agent_id || '-KEY-CREATED-' || NOW()::TEXT)::bytea), 'hex')
FROM fhq_meta.agent_keys
WHERE status = 'ACTIVE';

-- ============================================================================
-- SECTION 3: POPULATE AUTHORITY MATRIX
-- ============================================================================

-- VEGA authority (highest for governance)
INSERT INTO fhq_governance.authority_matrix (agent_id, action_type, resource_type, permission, resource_scope, governing_adr, established_by)
VALUES
    ('VEGA', 'WRITE', 'audit_log', 'ALLOW', 'fhq_meta.adr_audit_log', 'ADR-006', 'LARS'),
    ('VEGA', 'WRITE', 'certifications', 'ALLOW', 'fhq_meta.model_certifications', 'ADR-006', 'LARS'),
    ('VEGA', 'WRITE', 'sovereignty', 'ALLOW', 'fhq_meta.vega_sovereignty_log', 'ADR-006', 'LARS'),
    ('VEGA', 'READ', 'all', 'ALLOW', '*', 'ADR-006', 'LARS'),
    ('VEGA', 'TRIGGER_CRP', 'governance', 'ALLOW', '*', 'ADR-006', 'LARS')
ON CONFLICT ON CONSTRAINT unique_authority_entry DO NOTHING;

-- LARS authority (strategic)
INSERT INTO fhq_governance.authority_matrix (agent_id, action_type, resource_type, permission, resource_scope, governing_adr, established_by)
VALUES
    ('LARS', 'WRITE', 'governance_state', 'ALLOW', 'fhq_governance.*', 'ADR-001', 'CEO'),
    ('LARS', 'APPROVE', 'gate_transition', 'ALLOW', 'fhq_governance.gate_status', 'ADR-004', 'CEO'),
    ('LARS', 'READ', 'all', 'ALLOW', '*', 'ADR-001', 'CEO')
ON CONFLICT ON CONSTRAINT unique_authority_entry DO NOTHING;

-- STIG authority (validation)
INSERT INTO fhq_governance.authority_matrix (agent_id, action_type, resource_type, permission, resource_scope, governing_adr, established_by)
VALUES
    ('STIG', 'WRITE', 'validation', 'ALLOW', 'fhq_phase3.validation_results', 'ADR-010', 'LARS'),
    ('STIG', 'VALIDATE', 'predictions', 'ALLOW', 'fhq_phase3.regime_predictions', 'ADR-008', 'LARS'),
    ('STIG', 'READ', 'all', 'ALLOW', '*', 'ADR-001', 'LARS')
ON CONFLICT ON CONSTRAINT unique_authority_entry DO NOTHING;

-- FINN authority (analysis)
INSERT INTO fhq_governance.authority_matrix (agent_id, action_type, resource_type, permission, resource_scope, governing_adr, established_by)
VALUES
    ('FINN', 'WRITE', 'predictions', 'ALLOW', 'fhq_phase3.regime_predictions', 'ADR-007', 'LARS'),
    ('FINN', 'READ', 'market_data', 'ALLOW', 'fhq_data.*', 'ADR-007', 'LARS'),
    ('FINN', 'EXECUTE', 'analysis', 'ALLOW', 'fhq_phase3.*', 'ADR-007', 'LARS')
ON CONFLICT ON CONSTRAINT unique_authority_entry DO NOTHING;

-- LINE authority (data)
INSERT INTO fhq_governance.authority_matrix (agent_id, action_type, resource_type, permission, resource_scope, governing_adr, established_by)
VALUES
    ('LINE', 'WRITE', 'market_data', 'ALLOW', 'fhq_data.*', 'ADR-011', 'LARS'),
    ('LINE', 'WRITE', 'ohlcv', 'ALLOW', 'fhq_phase3.ohlcv_data', 'ADR-011', 'LARS'),
    ('LINE', 'INGEST', 'external_data', 'ALLOW', 'fhq_monitoring.ingestion_log', 'ADR-002', 'LARS')
ON CONFLICT ON CONSTRAINT unique_authority_entry DO NOTHING;

-- CODE authority (engineering)
INSERT INTO fhq_governance.authority_matrix (agent_id, action_type, resource_type, permission, resource_scope, governing_adr, established_by)
VALUES
    ('CODE', 'WRITE', 'function_registry', 'ALLOW', 'fhq_meta.function_registry', 'ADR-003', 'LARS'),
    ('CODE', 'READ', 'all', 'ALLOW', '*', 'ADR-003', 'LARS')
ON CONFLICT ON CONSTRAINT unique_authority_entry DO NOTHING;

-- CEO authority (ultimate)
INSERT INTO fhq_governance.authority_matrix (agent_id, action_type, resource_type, permission, resource_scope, governing_adr, established_by)
VALUES
    ('CEO', 'OVERRIDE', 'all', 'ALLOW', '*', 'ADR-001', 'CEO'),
    ('CEO', 'APPROVE', 'constitutional_exception', 'ALLOW', '*', 'ADR-001', 'CEO')
ON CONFLICT ON CONSTRAINT unique_authority_entry DO NOTHING;

-- ============================================================================
-- SECTION 4: INITIALIZE BASELINE STATE
-- ============================================================================

INSERT INTO fhq_meta.baseline_state (baseline_type, baseline_name, current_state, state_hash, established_by, authority)
VALUES
    ('GOVERNANCE', 'ADR_REGISTRY_BASELINE',
     jsonb_build_object('adr_count', 15, 'all_canonical', true, 'timestamp', NOW()),
     encode(sha256('ADR_REGISTRY_BASELINE_V1'::bytea), 'hex'),
     'VEGA', 'ADR-006'),

    ('SYSTEM', 'AGENT_KEYS_BASELINE',
     jsonb_build_object('agent_count', 7, 'all_active', true, 'key_type', 'Ed25519'),
     encode(sha256('AGENT_KEYS_BASELINE_V1'::bytea), 'hex'),
     'VEGA', 'ADR-008'),

    ('GOVERNANCE', 'AUTHORITY_MATRIX_BASELINE',
     jsonb_build_object('entries_count', 20, 'agents_covered', 7),
     encode(sha256('AUTHORITY_MATRIX_BASELINE_V1'::bytea), 'hex'),
     'VEGA', 'ADR-001')
ON CONFLICT ON CONSTRAINT unique_current_baseline DO NOTHING;

-- ============================================================================
-- SECTION 5: LOG MIGRATION EVENT
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    event_type, event_category, severity, actor, action, target,
    event_data, authority, adr_compliance, event_hash, hash_chain_id
) VALUES (
    'schema_migration', 'governance', 'INFO', 'VEGA',
    'APPLY_MIGRATION_020', '020_adr_ingest_keys.sql',
    jsonb_build_object(
        'migration_number', '020',
        'adrs_ingested', 15,
        'agents_keyed', 7,
        'authority_entries', 20,
        'baselines_created', 3,
        'database', '127.0.0.1:54322'
    ),
    'ADR-001_2026_PRODUCTION',
    ARRAY['ADR-001', 'ADR-006', 'ADR-008'],
    encode(sha256('MIGRATION_020_ADR_INGEST_KEYS'::bytea), 'hex'),
    'VEGA_GOVERNANCE_CHAIN'
);

-- ============================================================================
-- SECTION 6: VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_adr_count INTEGER;
    v_key_count INTEGER;
    v_authority_count INTEGER;
    v_baseline_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_adr_count FROM fhq_meta.adr_registry WHERE status = 'CANONICAL';
    SELECT COUNT(*) INTO v_key_count FROM fhq_meta.agent_keys WHERE status = 'ACTIVE';
    SELECT COUNT(*) INTO v_authority_count FROM fhq_governance.authority_matrix;
    SELECT COUNT(*) INTO v_baseline_count FROM fhq_meta.baseline_state WHERE is_current = TRUE;

    RAISE NOTICE '====================================================';
    RAISE NOTICE 'MIGRATION 020 VERIFICATION';
    RAISE NOTICE '====================================================';
    RAISE NOTICE 'ADRs ingested (CANONICAL): %', v_adr_count;
    RAISE NOTICE 'Agent keys registered: %', v_key_count;
    RAISE NOTICE 'Authority matrix entries: %', v_authority_count;
    RAISE NOTICE 'Baselines established: %', v_baseline_count;
    RAISE NOTICE '====================================================';

    IF v_adr_count < 15 THEN
        RAISE WARNING 'Expected 15 ADRs, found %', v_adr_count;
    END IF;

    IF v_key_count < 7 THEN
        RAISE WARNING 'Expected 7 agent keys, found %', v_key_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION 020 COMPLETE
-- ============================================================================
-- ADR Ingest & Key Registration:
-- - 15 ADRs ingested (ADR-001 → ADR-015)
-- - 7 agent Ed25519 keys registered
-- - Authority matrix populated
-- - Baselines established
-- - Database: 127.0.0.1:54322
-- ============================================================================
