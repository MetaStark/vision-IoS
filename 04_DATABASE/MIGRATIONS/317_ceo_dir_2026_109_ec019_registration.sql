-- ============================================================================
-- Migration 317: CEO-DIR-2026-109 EC-019 Registration to CANONICAL Table
-- ============================================================================
-- Directive: CEO-DIR-2026-109
-- Classification: CONSTITUTIONAL
-- Implementor: STIG (CTO)
-- Target: fhq_meta.vega_employment_contract (SINGLE SOURCE OF TRUTH per Fix #1)
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Register EC-019 to CANONICAL table
-- Status: PENDING_VEGA_ATTESTATION (Fix #2: Not self-asserted)
-- ============================================================================

INSERT INTO fhq_meta.vega_employment_contract (
    contract_number,
    contract_version,
    employer,
    employee,
    effective_date,
    status,
    governing_charter,
    constitutional_foundation,
    total_duties,
    total_constraints,
    total_rights,
    override_authority,
    reports_to,
    vega_signature,  -- NULL: requires explicit VEGA attestation (Fix #2)
    content_hash,
    created_at,
    updated_at
) VALUES (
    'EC-019',
    '2026.PRODUCTION',
    'FjordHQ AS',
    'HUMAN_GOVERNOR',
    '2026-01-19',
    'PENDING_VEGA',  -- Shortened to fit varchar(20). NOT ACTIVE until VEGA attests (Fix #2)
    'ADR-007',
    ARRAY['ADR-001', 'ADR-002', 'ADR-004', 'ADR-013'],
    4,  -- Core responsibilities: (1) G0 accumulation watchdog, (2) Strategic override, (3) Agent veto, (4) Budget allocation
    3,  -- Explicit exclusions: (1) No direct code execution, (2) No DB write access, (3) No LLM prompt injection
    2,  -- Rights: (1) Full audit visibility, (2) Emergency halt authority
    ARRAY['CEO'],
    'CEO',
    NULL,  -- VEGA must sign separately (Fix #2)
    md5('EC-019:HUMAN_GOVERNOR:2026-01-19'),
    NOW(),
    NOW()
)
ON CONFLICT (contract_number) DO UPDATE SET
    contract_version = EXCLUDED.contract_version,
    status = EXCLUDED.status,
    updated_at = NOW();

-- ============================================================================
-- STEP 2: Log governance action (PENDING attestation, Fix #2)
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,  -- FALSE until explicit attestation (Fix #2)
    metadata
) VALUES (
    gen_random_uuid(),
    'EC_REGISTRATION',
    'EC-019',
    'EMPLOYMENT_CONTRACT',
    'STIG',
    NOW(),
    'PENDING_ATTESTATION',
    'CEO-DIR-2026-109: EC-019 HUMAN_GOVERNOR registered. Status PENDING_VEGA requires explicit attestation per Fix #2.',
    false,  -- Fix #2: Not self-asserted
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-109',
        'phase', 'A',
        'canonical_table', 'fhq_meta.vega_employment_contract',
        'fix_applied', 'Fix #2: Explicit VEGA attestation required'
    )
);

-- ============================================================================
-- STEP 3: Deprecate ec_registry for new writes (Fix #1)
-- ============================================================================

COMMENT ON TABLE fhq_governance.ec_registry IS
'DEPRECATED per CEO-DIR-2026-109 (2026-01-19): Read-only. Canonical register is fhq_meta.vega_employment_contract. No new writes permitted. Existing records (EC-014, EC-018, EC-020-022) to be migrated.';

-- ============================================================================
-- STEP 4: Migrate EC-014, EC-018, EC-020-022 from ec_registry to canonical table
-- ============================================================================

-- EC-014: UMA - Learning Velocity & ROI Acceleration
INSERT INTO fhq_meta.vega_employment_contract (
    contract_number, contract_version, employer, employee, effective_date, status,
    governing_charter, constitutional_foundation, total_duties, total_constraints, total_rights,
    override_authority, reports_to, vega_signature, content_hash, created_at, updated_at
) VALUES (
    'EC-014', '2026.PRODUCTION', 'FjordHQ AS', 'UMA', '2026-01-16', 'ACTIVE',
    'ADR-014', ARRAY['ADR-001', 'ADR-002', 'ADR-014'], 3, 2, 2,
    ARRAY['CEO', 'VEGA'], 'CEO', NULL, md5('EC-014:UMA:2026-01-16'), NOW(), NOW()
) ON CONFLICT (contract_number) DO NOTHING;

-- EC-018: Meta-Alpha & Freedom Optimizer
INSERT INTO fhq_meta.vega_employment_contract (
    contract_number, contract_version, employer, employee, effective_date, status,
    governing_charter, constitutional_foundation, total_duties, total_constraints, total_rights,
    override_authority, reports_to, vega_signature, content_hash, created_at, updated_at
) VALUES (
    'EC-018', '2026.PRODUCTION', 'FjordHQ AS', 'META_ALPHA', '2025-12-09', 'ACTIVE',
    'ADR-014', ARRAY['ADR-001', 'ADR-002', 'ADR-014'], 3, 2, 2,
    ARRAY['CEO', 'VEGA'], 'CEO', NULL, md5('EC-018:META_ALPHA:2025-12-09'), NOW(), NOW()
) ON CONFLICT (contract_number) DO NOTHING;

-- EC-020: SitC - Search-in-the-Chain
INSERT INTO fhq_meta.vega_employment_contract (
    contract_number, contract_version, employer, employee, effective_date, status,
    governing_charter, constitutional_foundation, total_duties, total_constraints, total_rights,
    override_authority, reports_to, vega_signature, content_hash, created_at, updated_at
) VALUES (
    'EC-020', '2026.PRODUCTION', 'FjordHQ AS', 'SITC', '2025-12-09', 'ACTIVE',
    'ADR-014', ARRAY['ADR-001', 'ADR-002', 'ADR-014'], 3, 2, 2,
    ARRAY['CEO', 'VEGA', 'LARS'], 'LARS', NULL, md5('EC-020:SITC:2025-12-09'), NOW(), NOW()
) ON CONFLICT (contract_number) DO NOTHING;

-- EC-021: InForage - Information Economist
INSERT INTO fhq_meta.vega_employment_contract (
    contract_number, contract_version, employer, employee, effective_date, status,
    governing_charter, constitutional_foundation, total_duties, total_constraints, total_rights,
    override_authority, reports_to, vega_signature, content_hash, created_at, updated_at
) VALUES (
    'EC-021', '2026.PRODUCTION', 'FjordHQ AS', 'INFORAGE', '2025-12-09', 'ACTIVE',
    'ADR-014', ARRAY['ADR-001', 'ADR-002', 'ADR-012', 'ADR-014'], 3, 3, 2,
    ARRAY['CEO', 'VEGA', 'FINN'], 'FINN', NULL, md5('EC-021:INFORAGE:2025-12-09'), NOW(), NOW()
) ON CONFLICT (contract_number) DO NOTHING;

-- EC-022: IKEA - Knowledge Boundary Officer
INSERT INTO fhq_meta.vega_employment_contract (
    contract_number, contract_version, employer, employee, effective_date, status,
    governing_charter, constitutional_foundation, total_duties, total_constraints, total_rights,
    override_authority, reports_to, vega_signature, content_hash, created_at, updated_at
) VALUES (
    'EC-022', '2026.PRODUCTION', 'FjordHQ AS', 'IKEA', '2025-12-09', 'ACTIVE',
    'ADR-014', ARRAY['ADR-001', 'ADR-002', 'ADR-014'], 3, 2, 2,
    ARRAY['CEO', 'VEGA'], 'VEGA', NULL, md5('EC-022:IKEA:2025-12-09'), NOW(), NOW()
) ON CONFLICT (contract_number) DO NOTHING;

-- ============================================================================
-- STEP 5: Verification query
-- ============================================================================

DO $$
DECLARE
    ec019_count INTEGER;
    canonical_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO ec019_count
    FROM fhq_meta.vega_employment_contract
    WHERE contract_number = 'EC-019';

    SELECT COUNT(*) INTO canonical_count
    FROM fhq_meta.vega_employment_contract;

    IF ec019_count = 0 THEN
        RAISE EXCEPTION 'EC-019 registration failed';
    END IF;

    RAISE NOTICE 'Migration 317 SUCCESS: EC-019 registered. Total ECs in canonical table: %', canonical_count;
END $$;

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION (Run manually)
-- ============================================================================
-- SELECT contract_number, employee, status, effective_date
-- FROM fhq_meta.vega_employment_contract
-- ORDER BY contract_number;
-- ============================================================================
