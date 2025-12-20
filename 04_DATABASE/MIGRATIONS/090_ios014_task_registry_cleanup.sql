-- ============================================================================
-- Migration 090: IoS-014 Task Registry Cleanup
-- Authority: CEO DIRECTIVE - IoS-014 BUILD & AUTONOMOUS AGENT ACTIVATION
--
-- Marks tasks without function_path as PENDING so orchestrator skips them
-- ============================================================================

-- Mark non-executable tasks (no function_path) as PENDING
UPDATE fhq_governance.task_registry
SET task_status = 'PENDING',
    updated_at = NOW()
WHERE task_status = 'ACTIVE'
  AND (parameters_schema->>'function_path' IS NULL
       OR parameters_schema->>'function_path' = '');

-- Log migration
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by,
    decision, decision_rationale, hash_chain_id
) VALUES (
    'MIGRATION',
    'ios014_task_registry_cleanup',
    'DATABASE_SCHEMA',
    'STIG',
    'COMPLETED',
    'Marked non-executable tasks (no function_path) as PENDING per IoS-014 orchestrator requirements',
    'HC-MIGRATION-090-2025-12-07'
);

COMMENT ON TABLE fhq_governance.task_registry IS 'Task registry. Tasks with function_path are executable by IoS-014.';
