-- ============================================================================
-- MIGRATION 069: Skill & Macro Layer G4 Constitutional Activation
-- ============================================================================
-- Document ID: CP-2-SKILL-MACRO-G4-20251203
-- Authority: CEO Approval (2025-12-03)
-- Scope: IoS-005, IoS-006
-- ADR Alignment: ADR-004, ADR-011, ADR-012, ADR-013
-- ============================================================================

BEGIN;

-- ============================================================================
-- CHECKPOINT 2: Skill & Macro Layer G4 Constitutional
-- ============================================================================

-- Step 1: Formalize IoS-005 G4 Constitutional status
UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONSTITUTIONAL',
    immutability_level = 'FROZEN',
    modification_requires = 'FULL_G1_G4_CYCLE',
    canonical = TRUE,
    updated_at = NOW()
WHERE ios_id = 'IoS-005';

-- Step 2: Formalize IoS-006 G4 Constitutional status
UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONSTITUTIONAL',
    immutability_level = 'FROZEN',
    modification_requires = 'FULL_G1_G4_CYCLE',
    canonical = TRUE,
    updated_at = NOW()
WHERE ios_id = 'IoS-006';

-- Step 3: Log governance action for CP-2
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
    'CHECKPOINT_2_G4_CONSTITUTIONAL',
    'IoS-005,IoS-006',
    'IOS_SKILL_MACRO_LAYER',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO approved Checkpoint 2: Skill & Macro Layer G4 Constitutional activation for IoS-005 (Forecast Calibration) and IoS-006 (Global Macro). Immutability set to FROZEN. ADR-004, ADR-011, ADR-012, ADR-013 compliant.',
    TRUE,
    'HC-CP2-SKILL-MACRO-G4-20251203'
);

-- Step 4: Register in task_registry
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
    'CP2_SKILL_MACRO_G4_CONSTITUTIONAL',
    'G4_ACTIVATION',
    'IoS-005,IoS-006',
    'STIG',
    'STIG',
    'G4',
    TRUE,
    'CEO',
    NOW(),
    TRUE,
    TRUE,
    'Checkpoint 2: Skill & Macro Layer G4 Constitutional activation per CEO approval 2025-12-03',
    'ACTIVE',
    'STIG',
    'HC-CP2-SKILL-MACRO-G4-20251203'
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- SELECT ios_id, title, status, governance_state, immutability_level
-- FROM fhq_meta.ios_registry
-- WHERE ios_id IN ('IoS-005', 'IoS-006');
-- ============================================================================
