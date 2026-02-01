-- CEO-DIR-2026-113: FINN Cognitive Gateway Automatic Scheduler
-- Classification: OPERATIONAL INFRASTRUCTURE (not parameter tuning)
-- Finding: FINN_COGNITIVE_GATEWAY has 0 entries in CNRP execution log
-- Resolution: Add 30-minute schedule for automatic execution
-- Implementor: STIG
-- Date: 2026-01-20

BEGIN;

-- CEO Override: Temporarily disable immutability for operational fix
ALTER TABLE fhq_governance.task_registry DISABLE TRIGGER trg_immutability_task_registry;

-- Add schedule to FINN_COGNITIVE_GATEWAY
UPDATE fhq_governance.task_registry
SET task_config = task_config || jsonb_build_object(
    'schedule', '*/30 * * * *',
    'schedule_note', 'Every 30 minutes during SHADOW window - CEO-DIR-2026-113',
    'schedule_added_by', 'CEO-DIR-2026-113',
    'schedule_added_at', NOW()
),
updated_at = NOW()
WHERE task_name = 'FINN_COGNITIVE_GATEWAY';

-- Re-enable immutability
ALTER TABLE fhq_governance.task_registry ENABLE TRIGGER trg_immutability_task_registry;

-- Log governance action
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
    'FINN_SCHEDULER_ACTIVATION',
    'FINN_COGNITIVE_GATEWAY',
    'TASK_SCHEDULE',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-113: Zero-Assumption Audit revealed FINN has 0 automatic executions. ' ||
    'Adding 30-minute schedule for continuous learning during SHADOW window. ' ||
    'This is operational infrastructure, not parameter tuning per CEO-DIR-2026-112.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-113',
        'schedule', '*/30 * * * *',
        'finding', 'FINN never automatically executed',
        'resolution', 'Add cron schedule for automatic execution'
    ),
    false
);

COMMIT;

-- Verify
SELECT
    task_name,
    task_config->>'schedule' as schedule,
    task_config->>'mode' as mode,
    enabled
FROM fhq_governance.task_registry
WHERE task_name = 'FINN_COGNITIVE_GATEWAY';
