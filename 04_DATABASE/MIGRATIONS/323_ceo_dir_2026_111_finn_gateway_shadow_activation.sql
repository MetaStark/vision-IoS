-- CEO-DIR-2026-111: FINN Cognitive Gateway SHADOW Activation
-- Classification: MANDATORY – IMMEDIATE EXECUTION
-- Authority: CEO Executive Override (ADR-013 Section 4.2)
-- Implementor: STIG
-- Date: 2026-01-20

-- =============================================================================
-- CEO OVERRIDE AUTHORIZATION
-- =============================================================================
-- Per ADR-013 Section 4.2: CEO retains override authority for operational
-- configuration changes when accompanied by:
-- 1. Explicit directive reference
-- 2. Governance log entry
-- 3. Immediate trigger restoration
-- =============================================================================

BEGIN;

-- Step 1: Temporarily disable immutability trigger (CEO authority)
ALTER TABLE fhq_governance.task_registry DISABLE TRIGGER trg_immutability_task_registry;

-- Step 2: Execute mandated configuration change
UPDATE fhq_governance.task_registry
SET
    task_config = task_config || jsonb_build_object(
        'mode', 'SHADOW',
        'shadow_generated', true,
        'observation_window_hours', 48,
        'activated_by_directive', 'CEO-DIR-2026-111',
        'activation_timestamp', NOW()
    ),
    updated_at = NOW()
WHERE task_name = 'FINN_COGNITIVE_GATEWAY';

-- Step 3: Re-enable immutability trigger immediately
ALTER TABLE fhq_governance.task_registry ENABLE TRIGGER trg_immutability_task_registry;

-- Step 4: Log governance action (append-only, no trigger bypass needed)
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    vega_reviewed
) VALUES (
    'COGNITIVE_GATEWAY_ACTIVATION',
    'FINN_COGNITIVE_GATEWAY',
    'TASK_CONFIGURATION',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-111 Phase 1: FINN Cognitive Gateway activated to SHADOW mode. ' ||
    '48-hour observation window initiated. All outputs tagged shadow_generated=true. ' ||
    'Root cause addressed: Gateway was in mode=OFF since 2026-01-04, never activated.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-111',
        'previous_mode', 'OFF',
        'new_mode', 'SHADOW',
        'observation_window_hours', 48,
        'observation_ends', NOW() + INTERVAL '48 hours',
        'constraints', ARRAY['No execution side effects', 'All outputs shadow_generated=true'],
        'success_criteria', ARRAY[
            'fhq_finn.ensemble_signals contains today-dated rows',
            'g2_decision_plans median age < 5 minutes',
            'CPTO produces TradePacket in SHADOW',
            'Zero LINE submissions'
        ]
    ),
    false  -- VEGA will attest post-observation
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify FINN gateway is now in SHADOW mode
SELECT
    task_name,
    task_config->>'mode' as current_mode,
    task_config->>'shadow_generated' as shadow_flag,
    task_config->>'observation_window_hours' as observation_hours,
    task_config->>'activation_timestamp' as activated_at,
    updated_at
FROM fhq_governance.task_registry
WHERE task_name = 'FINN_COGNITIVE_GATEWAY';

-- Verify governance log entry exists
SELECT
    action_type,
    action_target,
    decision,
    initiated_at,
    decision_rationale
FROM fhq_governance.governance_actions_log
WHERE action_type = 'COGNITIVE_GATEWAY_ACTIVATION'
ORDER BY initiated_at DESC
LIMIT 1;
