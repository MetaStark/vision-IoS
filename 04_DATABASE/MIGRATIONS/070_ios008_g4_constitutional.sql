-- ============================================================================
-- MIGRATION 070: IoS-008 Runtime Decision Engine G4 Constitutional Activation
-- ============================================================================
-- Document ID: CP4-IOS008-G4-ACTIVATION-20251203
-- Authority: CEO Directive via LARS CSO Mandate (2025-12-03)
-- Scope: IoS-008 Runtime Decision Engine
-- ADR Alignment: ADR-004, ADR-008, ADR-011, ADR-013
-- ============================================================================
--
-- CRITICAL: Zero functional changes - governance state transition only
--
-- PRE-FREEZE STATE:
--   status: G2_VALIDATED
--   governance_state: G2_COMPLETE
--   immutability_level: MUTABLE
--   canonical: FALSE
--
-- POST-FREEZE STATE:
--   status: G4_CONSTITUTIONAL
--   governance_state: G4_CONSTITUTIONAL
--   immutability_level: FROZEN
--   canonical: TRUE
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- CHECKPOINT 4: IoS-008 G4 Constitutional Activation
-- ============================================================================

-- Step 1: Update IoS-008 to G4 Constitutional
UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONSTITUTIONAL',
    immutability_level = 'FROZEN',
    modification_requires = 'FULL_G1_G4_CYCLE',
    canonical = TRUE,
    version = '2026.PROD.G4',
    hash_chain_id = gen_random_uuid(),
    updated_at = NOW()
WHERE ios_id = 'IoS-008';

-- Step 2: Log governance action for CP-4
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
    'CP4_IOS008_G4_CONSTITUTIONAL',
    'IoS-008',
    'IOS_RUNTIME_DECISION_ENGINE',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO approved CP-4: IoS-008 Runtime Decision Engine G4 Constitutional activation. Status G2_VALIDATED → G4_CONSTITUTIONAL. Immutability MUTABLE → FROZEN. Zero functional changes - governance state transition only. ADR-004, ADR-008, ADR-011, ADR-013 compliant. Dependencies satisfied: IoS-001→006 all G4 Constitutional.',
    TRUE,
    'HC-CP4-IOS008-G4-20251203'
);

-- Step 3: Register in task_registry
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
    'CP4_IOS008_G4_CONSTITUTIONAL',
    'G4_ACTIVATION',
    'IoS-008',
    'STIG',
    'STIG',
    'G4',
    TRUE,
    'CEO',
    NOW(),
    TRUE,
    TRUE,
    'Checkpoint 4: IoS-008 Runtime Decision Engine G4 Constitutional activation per CEO directive 2025-12-03. Pre-requisites (IoS-001→006 G4) satisfied.',
    'ACTIVE',
    'STIG',
    'HC-CP4-IOS008-G4-20251203'
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- SELECT ios_id, title, status, governance_state, immutability_level,
--        version, canonical, hash_chain_id
-- FROM fhq_meta.ios_registry
-- WHERE ios_id = 'IoS-008';
-- ============================================================================
