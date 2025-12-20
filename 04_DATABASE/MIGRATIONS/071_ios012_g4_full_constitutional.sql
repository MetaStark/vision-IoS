-- ============================================================================
-- MIGRATION 071: IoS-012 Execution Engine G4 Full Constitutional Activation
-- ============================================================================
-- Document ID: CP5-IOS012-G4-FULL-20251203
-- Authority: CEO Directive via LARS CSO Mandate (2025-12-03)
-- Scope: IoS-012 Execution Engine
-- ADR Alignment: ADR-008, ADR-012, ADR-013, ADR-016
-- ============================================================================
--
-- CRITICAL NOTES:
-- 1. Zero functional changes - governance state transition only
-- 2. LIVE EXECUTION REMAINS BLOCKED per ADR-012
-- 3. PAPER mode continues as authorized
-- 4. Requires CP-6 for LIVE authorization
--
-- PRE-FREEZE STATE:
--   status: G4_CONSTITUTIONAL
--   governance_state: G4_CONDITIONAL
--   immutability_level: FROZEN_PAPER_ACTIVE
--   canonical: FALSE
--
-- POST-FREEZE STATE:
--   status: G4_CONSTITUTIONAL_FULL
--   governance_state: G4_CONSTITUTIONAL_FULL
--   immutability_level: FROZEN
--   canonical: TRUE
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- CHECKPOINT 5: IoS-012 G4 Full Constitutional Activation
-- ============================================================================

-- Step 1: Update IoS-012 to G4 Constitutional Full
-- Note: status uses G4_CONSTITUTIONAL (valid enum), governance_state tracks FULL designation
UPDATE fhq_meta.ios_registry
SET
    status = 'G4_CONSTITUTIONAL',
    governance_state = 'G4_CONSTITUTIONAL_FULL',
    immutability_level = 'FROZEN',
    modification_requires = 'FULL_G1_G4_CYCLE + CEO_VEGA_DUAL_APPROVAL',
    canonical = TRUE,
    version = '2026.PROD.G4.FULL',
    hash_chain_id = gen_random_uuid(),
    updated_at = NOW()
WHERE ios_id = 'IoS-012';

-- Step 2: Update paper_execution_authority to reflect full constitutional status
-- Note: activation_mode stays 'PAPER' (valid enum), immutability flags enforce constitutional
UPDATE fhq_governance.paper_execution_authority
SET
    activation_mode = 'PAPER',
    code_immutability_enforced = TRUE,
    adr_012_constraints_enforced = TRUE,
    updated_at = NOW()
WHERE ios_id = 'IoS-012';

-- Step 3: Log governance action for CP-5
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
    'CP5_IOS012_G4_CONSTITUTIONAL_FULL',
    'IoS-012',
    'IOS_EXECUTION_ENGINE',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO approved CP-5: IoS-012 Execution Engine G4 Constitutional Full activation. Status G4_CONDITIONAL → G4_CONSTITUTIONAL_FULL. Immutability FROZEN_PAPER_ACTIVE → FROZEN. Zero functional changes. LIVE remains BLOCKED per ADR-012 until CP-6. ADR-008, ADR-012, ADR-013, ADR-016 compliant. Prerequisite IoS-008 G4 satisfied.',
    TRUE,
    'HC-CP5-IOS012-G4-20251203'
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
    'CP5_IOS012_G4_CONSTITUTIONAL_FULL',
    'G4_FULL_ACTIVATION',
    'IoS-012',
    'STIG',
    'STIG',
    'G4',
    TRUE,
    'CEO',
    NOW(),
    TRUE,
    TRUE,
    'Checkpoint 5: IoS-012 Execution Engine G4 Constitutional Full activation per CEO directive 2025-12-03. PAPER mode active. LIVE remains blocked until CP-6.',
    'ACTIVE',
    'STIG',
    'HC-CP5-IOS012-G4-20251203'
);

COMMIT;

-- ============================================================================
-- SAFETY VERIFICATION: LIVE must remain blocked
-- ============================================================================
-- SELECT ios_id, live_api_enabled FROM fhq_governance.paper_execution_authority
-- WHERE ios_id = 'IoS-012';
-- Expected: live_api_enabled = FALSE
-- ============================================================================
