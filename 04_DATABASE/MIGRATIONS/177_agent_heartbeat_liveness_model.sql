-- Migration 177: Agent Heartbeat Liveness Model Extension
-- CEO-DIR-2026-044: Agent Health Signal Separation & FINN Liveness Augmentation
--
-- Purpose: Extend agent_heartbeats to support agent-specific liveness probes
-- separating governance activity from productive output.
--
-- Constraints:
-- - Existing fields MUST remain untouched
-- - Non-breaking schema change
-- - No governance semantics changed
--
-- Author: STIG (CTO)
-- Date: 2026-01-13

-- Add health_source column: governance, research, execution, mixed
ALTER TABLE fhq_governance.agent_heartbeats
ADD COLUMN IF NOT EXISTS health_source VARCHAR(50) DEFAULT 'governance';

COMMENT ON COLUMN fhq_governance.agent_heartbeats.health_source IS
'Source of health signal: governance (actions log), research (forecast output), execution (daemon status), mixed (multiple sources)';

-- Add liveness_basis column: human-readable explanation
ALTER TABLE fhq_governance.agent_heartbeats
ADD COLUMN IF NOT EXISTS liveness_basis TEXT;

COMMENT ON COLUMN fhq_governance.agent_heartbeats.liveness_basis IS
'Human-readable explanation of how liveness was determined for this agent';

-- Add liveness_metadata column: structured probe results
ALTER TABLE fhq_governance.agent_heartbeats
ADD COLUMN IF NOT EXISTS liveness_metadata JSONB;

COMMENT ON COLUMN fhq_governance.agent_heartbeats.liveness_metadata IS
'Structured metadata from liveness probes (forecast counts, daemon status, etc.)';

-- Log migration
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'SCHEMA_MIGRATION',
    'fhq_governance.agent_heartbeats',
    'TABLE',
    'STIG',
    NOW(),
    'EXECUTED',
    'CEO-DIR-2026-044: Added health_source, liveness_basis, liveness_metadata columns for agent-specific liveness probes',
    jsonb_build_object(
        'migration_id', 177,
        'directive', 'CEO-DIR-2026-044',
        'columns_added', ARRAY['health_source', 'liveness_basis', 'liveness_metadata'],
        'breaking_change', false
    )
);
