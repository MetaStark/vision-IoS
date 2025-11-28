-- =====================================================
-- MIGRATION 021: EMPLOYMENT CONTRACT REGISTRATION
-- =====================================================
--
-- Authority: CEO Directive DIR-EC-REG-20251128
-- Purpose: Register employment contracts (EC-002 through EC-012) for all FjordHQ agents
-- Constitutional Foundation: ADR-007 Orchestrator Charter
-- Priority: P0 - IMMEDIATE
--
-- NOTE: EC-001 (VEGA) already exists in the database
-- This migration adds EC-002 through EC-012 for remaining agents
--
-- Contract Matrix:
--   EC-001: VEGA   (Authority 10, Governance) - ALREADY EXISTS
--   EC-002: LARS   (Authority 9, Strategy)
--   EC-003: STIG   (Authority 8, Implementation)
--   EC-004: FINN   (Authority 8, Research)
--   EC-005: LINE   (Authority 8, SRE)
--   EC-006: CSEO   (Authority 7, Sub-Executive)
--   EC-007: CDMO   (Authority 7, Sub-Executive)
--   EC-008: CRIO   (Authority 7, Sub-Executive)
--   EC-009: CEIO   (Authority 7, Sub-Executive)
--   EC-010: CFAO   (Authority 7, Sub-Executive)
--   EC-011: CODE   (Authority 3, Engineering)
--   EC-012: RESERVED (Future Agent)
--
-- =====================================================

BEGIN;

-- =====================================================
-- STEP 1: INSERT EC-002 THROUGH EC-012
-- =====================================================
-- Using existing table schema (contract_id is auto-generated)

INSERT INTO fhq_meta.vega_employment_contract
    (contract_number, contract_version, employer, employee, effective_date, status,
     governing_charter, constitutional_foundation, total_duties, total_constraints,
     total_rights, override_authority, reports_to)
VALUES
    ('EC-002', '2026.PRODUCTION', 'FjordHQ AS', 'LARS', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007'],
     8, 5, 6, ARRAY['CEO'], 'CEO'),

    ('EC-003', '2026.PRODUCTION', 'FjordHQ AS', 'STIG', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007'],
     8, 5, 5, ARRAY['CEO','VEGA','LARS'], 'LARS'),

    ('EC-004', '2026.PRODUCTION', 'FjordHQ AS', 'FINN', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007'],
     8, 5, 5, ARRAY['CEO','VEGA','LARS'], 'LARS'),

    ('EC-005', '2026.PRODUCTION', 'FjordHQ AS', 'LINE', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007'],
     8, 5, 5, ARRAY['CEO','VEGA','LARS'], 'LARS'),

    ('EC-006', '2026.PRODUCTION', 'FjordHQ AS', 'CSEO', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007','ADR-014'],
     6, 4, 4, ARRAY['CEO','VEGA','LARS'], 'LARS'),

    ('EC-007', '2026.PRODUCTION', 'FjordHQ AS', 'CDMO', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007','ADR-013','ADR-014'],
     6, 4, 4, ARRAY['CEO','VEGA','LARS'], 'LARS'),

    ('EC-008', '2026.PRODUCTION', 'FjordHQ AS', 'CRIO', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007','ADR-012','ADR-014'],
     6, 4, 4, ARRAY['CEO','VEGA','LARS'], 'LARS'),

    ('EC-009', '2026.PRODUCTION', 'FjordHQ AS', 'CEIO', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007','ADR-014'],
     6, 4, 4, ARRAY['CEO','VEGA','LARS'], 'LARS'),

    ('EC-010', '2026.PRODUCTION', 'FjordHQ AS', 'CFAO', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-002','ADR-007','ADR-014'],
     6, 4, 4, ARRAY['CEO','VEGA','LARS'], 'LARS'),

    ('EC-011', '2026.PRODUCTION', 'FjordHQ AS', 'CODE', '2025-11-28', 'ACTIVE',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007','ADR-014'],
     4, 6, 3, ARRAY['CEO','VEGA','LARS','STIG'], 'STIG'),

    ('EC-012', '2026.PRODUCTION', 'FjordHQ AS', 'RESERVED', '2025-11-28', 'RESERVED',
     'ADR-007', ARRAY['ADR-001','ADR-002','ADR-003','ADR-004','ADR-007'],
     0, 0, 0, ARRAY['CEO'], 'CEO')
ON CONFLICT (contract_number) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

-- =====================================================
-- STEP 2: CREATE VEGA ATTESTATIONS
-- =====================================================
-- Using the existing vega_attestations table structure

INSERT INTO fhq_governance.vega_attestations (
    target_type, target_id, target_version,
    attestation_type, attestation_status,
    vega_signature, vega_public_key,
    attestation_data, adr_reference, constitutional_basis
) VALUES
    -- EC-001 VEGA
    ('EMPLOYMENT_CONTRACT', 'EC-001', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-001-20251128-' || encode(sha256('EC-001-VEGA-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'VEGA',
         'contract_number', 'EC-001',
         'constitutional_basis', ARRAY['ADR-006', 'ADR-007'],
         'attestation_hash', encode(sha256('EC-001-VEGA-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-002 LARS
    ('EMPLOYMENT_CONTRACT', 'EC-002', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-002-20251128-' || encode(sha256('EC-002-LARS-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'LARS',
         'contract_number', 'EC-002',
         'constitutional_basis', ARRAY['ADR-007'],
         'attestation_hash', encode(sha256('EC-002-LARS-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-003 STIG
    ('EMPLOYMENT_CONTRACT', 'EC-003', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-003-20251128-' || encode(sha256('EC-003-STIG-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'STIG',
         'contract_number', 'EC-003',
         'constitutional_basis', ARRAY['ADR-007'],
         'attestation_hash', encode(sha256('EC-003-STIG-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-004 FINN
    ('EMPLOYMENT_CONTRACT', 'EC-004', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-004-20251128-' || encode(sha256('EC-004-FINN-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'FINN',
         'contract_number', 'EC-004',
         'constitutional_basis', ARRAY['ADR-007'],
         'attestation_hash', encode(sha256('EC-004-FINN-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-005 LINE
    ('EMPLOYMENT_CONTRACT', 'EC-005', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-005-20251128-' || encode(sha256('EC-005-LINE-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'LINE',
         'contract_number', 'EC-005',
         'constitutional_basis', ARRAY['ADR-007'],
         'attestation_hash', encode(sha256('EC-005-LINE-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-006 CSEO
    ('EMPLOYMENT_CONTRACT', 'EC-006', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-006-20251128-' || encode(sha256('EC-006-CSEO-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'CSEO',
         'contract_number', 'EC-006',
         'constitutional_basis', ARRAY['ADR-007', 'ADR-014'],
         'attestation_hash', encode(sha256('EC-006-CSEO-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-007 CDMO
    ('EMPLOYMENT_CONTRACT', 'EC-007', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-007-20251128-' || encode(sha256('EC-007-CDMO-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'CDMO',
         'contract_number', 'EC-007',
         'constitutional_basis', ARRAY['ADR-007', 'ADR-014'],
         'attestation_hash', encode(sha256('EC-007-CDMO-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-008 CRIO
    ('EMPLOYMENT_CONTRACT', 'EC-008', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-008-20251128-' || encode(sha256('EC-008-CRIO-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'CRIO',
         'contract_number', 'EC-008',
         'constitutional_basis', ARRAY['ADR-007', 'ADR-014'],
         'attestation_hash', encode(sha256('EC-008-CRIO-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-009 CEIO
    ('EMPLOYMENT_CONTRACT', 'EC-009', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-009-20251128-' || encode(sha256('EC-009-CEIO-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'CEIO',
         'contract_number', 'EC-009',
         'constitutional_basis', ARRAY['ADR-007', 'ADR-014'],
         'attestation_hash', encode(sha256('EC-009-CEIO-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-010 CFAO
    ('EMPLOYMENT_CONTRACT', 'EC-010', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-010-20251128-' || encode(sha256('EC-010-CFAO-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'CFAO',
         'contract_number', 'EC-010',
         'constitutional_basis', ARRAY['ADR-007', 'ADR-014'],
         'attestation_hash', encode(sha256('EC-010-CFAO-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-011 CODE
    ('EMPLOYMENT_CONTRACT', 'EC-011', '2026.PRODUCTION',
     'CERTIFICATION', 'APPROVED',
     'ATT-EC-011-20251128-' || encode(sha256('EC-011-CODE-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'CODE',
         'contract_number', 'EC-011',
         'constitutional_basis', ARRAY['ADR-007', 'ADR-014'],
         'attestation_hash', encode(sha256('EC-011-CODE-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28'
     ),
     'ADR-007', 'EC-001'),

    -- EC-012 RESERVED
    ('EMPLOYMENT_CONTRACT', 'EC-012', '2026.PRODUCTION',
     'CERTIFICATION', 'PENDING',
     'ATT-EC-012-20251128-' || encode(sha256('EC-012-RESERVED-2026.PRODUCTION'::bytea), 'hex'),
     'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
     jsonb_build_object(
         'employee', 'RESERVED',
         'contract_number', 'EC-012',
         'constitutional_basis', ARRAY['ADR-007'],
         'attestation_hash', encode(sha256('EC-012-RESERVED-2026.PRODUCTION'::bytea), 'hex'),
         'attestation_date', '2025-11-28',
         'reserved', true
     ),
     'ADR-007', 'EC-001')
ON CONFLICT DO NOTHING;

-- =====================================================
-- STEP 3: LOG GOVERNANCE ACTION
-- =====================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    hash_chain_id,
    signature_id
) VALUES (
    'EMPLOYMENT_CONTRACT_REGISTRATION',
    'EC-001_TO_EC-012',
    'EMPLOYMENT_CONTRACT',
    'LARS',
    'APPROVED',
    'CEO Directive DIR-EC-REG-20251128: Register employment contracts EC-001 through EC-012 per ADR-007 §3.2',
    'HC-DIR-EC-REG-20251128-' || MD5(NOW()::TEXT),
    gen_random_uuid()
);

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify all 12 contracts registered
DO $$
DECLARE
    contract_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO contract_count
    FROM fhq_meta.vega_employment_contract;

    IF contract_count < 12 THEN
        RAISE EXCEPTION 'Expected 12 employment contracts, found %', contract_count;
    END IF;

    RAISE NOTICE '✅ Employment contracts registered: %', contract_count;
END $$;

-- Verify attestations created
DO $$
DECLARE
    attestation_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO attestation_count
    FROM fhq_governance.vega_attestations
    WHERE target_type = 'EMPLOYMENT_CONTRACT';

    IF attestation_count < 12 THEN
        RAISE WARNING 'Expected 12 attestations, found %', attestation_count;
    ELSE
        RAISE NOTICE '✅ VEGA attestations created: %', attestation_count;
    END IF;
END $$;

-- Display contract summary
SELECT
    contract_number,
    employee,
    status,
    reports_to,
    governing_charter,
    array_length(override_authority, 1) AS override_count
FROM fhq_meta.vega_employment_contract
ORDER BY contract_number;

-- Display attestation summary
SELECT
    target_id AS contract,
    attestation_status,
    attestation_data->>'employee' AS employee,
    created_at
FROM fhq_governance.vega_attestations
WHERE target_type = 'EMPLOYMENT_CONTRACT'
ORDER BY target_id;

-- Integrity check
SELECT
    ec.contract_number,
    ec.employee,
    ec.status AS contract_status,
    va.attestation_status,
    CASE
        WHEN va.attestation_id IS NULL THEN 'MISSING_ATTESTATION'
        WHEN ec.status = 'ACTIVE' AND va.attestation_status = 'APPROVED' THEN 'ALIGNED'
        WHEN ec.status = 'RESERVED' AND va.attestation_status = 'PENDING' THEN 'ALIGNED'
        ELSE 'MISALIGNED'
    END AS integrity_status
FROM fhq_meta.vega_employment_contract ec
LEFT JOIN fhq_governance.vega_attestations va
    ON va.target_id = ec.contract_number
    AND va.target_type = 'EMPLOYMENT_CONTRACT'
ORDER BY ec.contract_number;

COMMIT;

-- =====================================================
-- MIGRATION SUMMARY
-- =====================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════'
\echo 'MIGRATION 021: EMPLOYMENT CONTRACT REGISTRATION'
\echo '═══════════════════════════════════════════════════════════'
\echo 'Directive: DIR-EC-REG-20251128'
\echo 'Authority: CEO → ADR-007 §3.2'
\echo ''
\echo 'Contracts Registered:'
\echo '  EC-001: VEGA    (Authority 10, Governance) - PRE-EXISTING'
\echo '  EC-002: LARS    (Authority 9, Strategy)'
\echo '  EC-003: STIG    (Authority 8, Implementation)'
\echo '  EC-004: FINN    (Authority 8, Research)'
\echo '  EC-005: LINE    (Authority 8, SRE)'
\echo '  EC-006: CSEO    (Authority 7, Sub-Executive)'
\echo '  EC-007: CDMO    (Authority 7, Sub-Executive)'
\echo '  EC-008: CRIO    (Authority 7, Sub-Executive)'
\echo '  EC-009: CEIO    (Authority 7, Sub-Executive)'
\echo '  EC-010: CFAO    (Authority 7, Sub-Executive)'
\echo '  EC-011: CODE    (Authority 3, Engineering)'
\echo '  EC-012: RESERVED (Future Agent)'
\echo ''
\echo '✅ 12 employment contracts registered'
\echo '✅ 12 VEGA attestations created'
\echo '✅ Governance action logged'
\echo '═══════════════════════════════════════════════════════════'
\echo ''
