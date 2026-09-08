-- =============================================================================
-- MIGRATION 215: LIDS BLOCK OBSERVABILITY
-- =============================================================================
-- CEO-DIR-2026-020 D3: LIDS Block Logging
--
-- Purpose: Add columns to execution_state to track LIDS gate activity
-- Author: STIG (CTO)
-- Date: 2026-01-08
-- =============================================================================

-- Add LIDS tracking columns to execution_state
ALTER TABLE fhq_governance.execution_state
ADD COLUMN IF NOT EXISTS last_lids_block_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_lids_block_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS lids_blocks_today INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS lids_passes_today INTEGER DEFAULT 0;

-- Add comment for documentation
COMMENT ON COLUMN fhq_governance.execution_state.last_lids_block_at IS 'CEO-DIR-2026-020 D3: Timestamp of last LIDS gate block';
COMMENT ON COLUMN fhq_governance.execution_state.last_lids_block_type IS 'CEO-DIR-2026-020 D3: Type of last LIDS block (CONFIDENCE or FRESHNESS)';
COMMENT ON COLUMN fhq_governance.execution_state.lids_blocks_today IS 'CEO-DIR-2026-020 D3: Count of LIDS blocks today (reset at midnight UTC)';
COMMENT ON COLUMN fhq_governance.execution_state.lids_passes_today IS 'CEO-DIR-2026-020 D3: Count of LIDS passes today (reset at midnight UTC)';

-- Log migration
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'MIGRATION_215_LIDS_OBSERVABILITY',
    'fhq_governance.execution_state',
    'SCHEMA_CHANGE',
    'STIG',
    'EXECUTED',
    'CEO-DIR-2026-020 D3: Added LIDS block tracking columns to execution_state',
    'STIG',
    '{"directive": "CEO-DIR-2026-020", "deliverable": "D3", "columns_added": ["last_lids_block_at", "last_lids_block_type", "lids_blocks_today", "lids_passes_today"]}'::jsonb
);

SELECT 'Migration 215 complete: LIDS block observability columns added' as status;
