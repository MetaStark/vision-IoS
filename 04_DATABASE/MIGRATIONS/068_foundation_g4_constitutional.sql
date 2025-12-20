-- ============================================================================
-- MIGRATION 068: Foundation Layer G4 Constitutional Activation
-- ============================================================================
-- Document ID: CP-1-FOUNDATION-G4-20251203
-- Authority: CEO Approval (2025-12-03)
-- Scope: IoS-001, IoS-002, IoS-003, IoS-004
-- ADR Alignment: ADR-004, ADR-011, ADR-013
-- ============================================================================

BEGIN;

-- ============================================================================
-- CHECKPOINT 1: Foundation Layer G4 Constitutional
-- ============================================================================

-- Step 1: Update IoS-001 to G4 Constitutional
UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONSTITUTIONAL',
    immutability_level = 'FROZEN',
    modification_requires = 'FULL_G1_G4_CYCLE',
    canonical = TRUE,
    updated_at = NOW()
WHERE ios_id = 'IoS-001';

-- Step 2: Update IoS-002 to G4 Constitutional
UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONSTITUTIONAL',
    immutability_level = 'FROZEN',
    modification_requires = 'FULL_G1_G4_CYCLE',
    canonical = TRUE,
    updated_at = NOW()
WHERE ios_id = 'IoS-002';

-- Step 3: Update IoS-003 to G4 Constitutional
UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONSTITUTIONAL',
    immutability_level = 'FROZEN',
    modification_requires = 'FULL_G1_G4_CYCLE',
    canonical = TRUE,
    updated_at = NOW()
WHERE ios_id = 'IoS-003';

-- Step 4: Update IoS-004 to G4 Constitutional
UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONSTITUTIONAL',
    immutability_level = 'FROZEN',
    modification_requires = 'FULL_G1_G4_CYCLE',
    canonical = TRUE,
    updated_at = NOW()
WHERE ios_id = 'IoS-004';

-- Step 5: Log governance action for CP-1
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'CHECKPOINT_1_G4_CONSTITUTIONAL',
    'IoS-001,IoS-002,IoS-003,IoS-004',
    'IOS_FOUNDATION_LAYER',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO approved Checkpoint 1: Foundation Layer G4 Constitutional activation for IoS-001 through IoS-004. Immutability set to FROZEN. ADR-004, ADR-011, ADR-013 compliant.',
    TRUE,
    'HC-CP1-FOUNDATION-G4-20251203'
);

-- Step 6: Register in task_registry
INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    task_scope,
    owned_by_agent,
    executed_by_agent,
    gate_level,
    gate_approved,
    gate_approved_by,
    gate_approved_at,
    vega_reviewed,
    vega_approved,
    description,
    task_status,
    created_by,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'CP1_FOUNDATION_G4_CONSTITUTIONAL',
    'G4_ACTIVATION',
    'IoS-001,IoS-002,IoS-003,IoS-004',
    'STIG',
    'STIG',
    'G4',
    TRUE,
    'CEO',
    NOW(),
    TRUE,
    TRUE,
    'Checkpoint 1: Foundation Layer G4 Constitutional activation per CEO approval 2025-12-03',
    'ACTIVE',
    'STIG',
    'HC-CP1-FOUNDATION-G4-20251203'
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY (run after migration)
-- ============================================================================
-- SELECT ios_id, title, status, governance_state, immutability_level
-- FROM fhq_meta.ios_registry
-- WHERE ios_id IN ('IoS-001', 'IoS-002', 'IoS-003', 'IoS-004');
-- ============================================================================
