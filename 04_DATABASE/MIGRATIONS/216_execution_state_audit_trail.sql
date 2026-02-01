-- =============================================================================
-- MIGRATION 216: EXECUTION STATE AUDIT TRAIL
-- =============================================================================
-- CEO-DIR-2026-020 D4: Execution State Initialization and State-Change Audit Trail
--
-- Purpose: Make execution_state the single source of truth for system posture
--          with immutable change logging
--
-- Author: STIG (CTO)
-- Date: 2026-01-08
-- =============================================================================

-- 1. Add missing columns to execution_state
ALTER TABLE fhq_governance.execution_state
ADD COLUMN IF NOT EXISTS defcon_level VARCHAR(20) DEFAULT 'NORMAL',
ADD COLUMN IF NOT EXISTS last_updated_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS last_updated_by VARCHAR(100),
ADD COLUMN IF NOT EXISTS last_update_reason TEXT,
ADD COLUMN IF NOT EXISTS paper_trading_eligible BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS learning_eligible BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS state_version INTEGER DEFAULT 1;

-- Add comments
COMMENT ON COLUMN fhq_governance.execution_state.defcon_level IS 'CEO-DIR-2026-020 D4: Current DEFCON level (NORMAL, ELEVATED, HIGH, CRITICAL)';
COMMENT ON COLUMN fhq_governance.execution_state.last_updated_at IS 'CEO-DIR-2026-020 D4: Timestamp of last state mutation';
COMMENT ON COLUMN fhq_governance.execution_state.last_updated_by IS 'CEO-DIR-2026-020 D4: Agent/daemon that last mutated state';
COMMENT ON COLUMN fhq_governance.execution_state.last_update_reason IS 'CEO-DIR-2026-020 D4: Reason for last state mutation';
COMMENT ON COLUMN fhq_governance.execution_state.paper_trading_eligible IS 'CEO-DIR-2026-020 D4: Whether paper trading is currently allowed';
COMMENT ON COLUMN fhq_governance.execution_state.learning_eligible IS 'CEO-DIR-2026-020 D4: Whether learning updates are currently allowed';
COMMENT ON COLUMN fhq_governance.execution_state.state_version IS 'CEO-DIR-2026-020 D4: Monotonic version counter for optimistic locking';

-- 2. Create execution_state_change_log table (APPEND-ONLY)
CREATE TABLE IF NOT EXISTS fhq_governance.execution_state_change_log (
    change_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_id INTEGER NOT NULL,
    state_version_before INTEGER NOT NULL,
    state_version_after INTEGER NOT NULL,
    previous_state JSONB NOT NULL,
    new_state JSONB NOT NULL,
    change_type VARCHAR(50) NOT NULL,
    change_reason TEXT NOT NULL,
    initiated_by VARCHAR(100) NOT NULL,
    initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hash_chain_id VARCHAR(100),

    -- Prevent modifications
    CONSTRAINT no_updates CHECK (true)
);

-- Add comments
COMMENT ON TABLE fhq_governance.execution_state_change_log IS 'CEO-DIR-2026-020 D4: Immutable audit trail of all execution_state transitions. APPEND-ONLY.';
COMMENT ON COLUMN fhq_governance.execution_state_change_log.previous_state IS 'Full JSONB snapshot of state before change';
COMMENT ON COLUMN fhq_governance.execution_state_change_log.new_state IS 'Full JSONB snapshot of state after change';
COMMENT ON COLUMN fhq_governance.execution_state_change_log.change_type IS 'Type of change: LIDS_BLOCK, DEFCON_CHANGE, FASTING_START, FASTING_END, REVALIDATION, CNRP_COMPLETE';

-- Create index for efficient querying
CREATE INDEX IF NOT EXISTS idx_execution_state_change_log_initiated_at
ON fhq_governance.execution_state_change_log(initiated_at DESC);

CREATE INDEX IF NOT EXISTS idx_execution_state_change_log_change_type
ON fhq_governance.execution_state_change_log(change_type);

-- 3. Create trigger to prevent updates/deletes on change_log (APPEND-ONLY enforcement)
CREATE OR REPLACE FUNCTION fhq_governance.prevent_change_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'CEO-DIR-2026-020 D4: execution_state_change_log is APPEND-ONLY. Updates and deletes are forbidden.';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_change_log_update ON fhq_governance.execution_state_change_log;
CREATE TRIGGER trg_prevent_change_log_update
    BEFORE UPDATE OR DELETE ON fhq_governance.execution_state_change_log
    FOR EACH ROW EXECUTE FUNCTION fhq_governance.prevent_change_log_modification();

-- 4. Create helper function to log state changes
CREATE OR REPLACE FUNCTION fhq_governance.log_execution_state_change(
    p_change_type VARCHAR(50),
    p_change_reason TEXT,
    p_initiated_by VARCHAR(100)
) RETURNS UUID AS $$
DECLARE
    v_state_before JSONB;
    v_state_after JSONB;
    v_version_before INTEGER;
    v_version_after INTEGER;
    v_state_id INTEGER;
    v_change_id UUID;
BEGIN
    -- Get current state as snapshot
    SELECT
        state_id,
        state_version,
        jsonb_build_object(
            'cognitive_fasting', cognitive_fasting,
            'defcon_level', defcon_level,
            'revalidation_required', revalidation_required,
            'fasting_reason', fasting_reason,
            'fasting_started_at', fasting_started_at,
            'last_lids_block_at', last_lids_block_at,
            'last_lids_block_type', last_lids_block_type,
            'lids_blocks_today', lids_blocks_today,
            'lids_passes_today', lids_passes_today,
            'paper_trading_eligible', paper_trading_eligible,
            'learning_eligible', learning_eligible,
            'last_cnrp_completion', last_cnrp_completion
        )
    INTO v_state_id, v_version_before, v_state_before
    FROM fhq_governance.execution_state
    ORDER BY state_id DESC
    LIMIT 1;

    -- Increment version
    v_version_after := v_version_before + 1;

    -- Update execution_state
    UPDATE fhq_governance.execution_state
    SET state_version = v_version_after,
        last_updated_at = NOW(),
        last_updated_by = p_initiated_by,
        last_update_reason = p_change_reason
    WHERE state_id = v_state_id;

    -- Get new state snapshot
    SELECT jsonb_build_object(
        'cognitive_fasting', cognitive_fasting,
        'defcon_level', defcon_level,
        'revalidation_required', revalidation_required,
        'fasting_reason', fasting_reason,
        'fasting_started_at', fasting_started_at,
        'last_lids_block_at', last_lids_block_at,
        'last_lids_block_type', last_lids_block_type,
        'lids_blocks_today', lids_blocks_today,
        'lids_passes_today', lids_passes_today,
        'paper_trading_eligible', paper_trading_eligible,
        'learning_eligible', learning_eligible,
        'last_cnrp_completion', last_cnrp_completion
    )
    INTO v_state_after
    FROM fhq_governance.execution_state
    WHERE state_id = v_state_id;

    -- Insert change log (APPEND-ONLY)
    INSERT INTO fhq_governance.execution_state_change_log (
        state_id,
        state_version_before,
        state_version_after,
        previous_state,
        new_state,
        change_type,
        change_reason,
        initiated_by
    ) VALUES (
        v_state_id,
        v_version_before,
        v_version_after,
        v_state_before,
        v_state_after,
        p_change_type,
        p_change_reason,
        p_initiated_by
    )
    RETURNING change_id INTO v_change_id;

    RETURN v_change_id;
END;
$$ LANGUAGE plpgsql;

-- 5. Update existing row to be canonical
UPDATE fhq_governance.execution_state
SET cycle_id = 'CANONICAL-V1',
    defcon_level = 'NORMAL',
    last_updated_at = NOW(),
    last_updated_by = 'STIG',
    last_update_reason = 'CEO-DIR-2026-020 D4: Initialized canonical execution state',
    paper_trading_eligible = FALSE,
    learning_eligible = TRUE,
    state_version = 1,
    state_data = jsonb_build_object(
        'initialized_at', NOW(),
        'initialized_by', 'STIG',
        'directive', 'CEO-DIR-2026-020',
        'deliverable', 'D4',
        'purpose', 'Single source of truth for system posture'
    )
WHERE state_id = (SELECT MAX(state_id) FROM fhq_governance.execution_state);

-- 6. Log the initialization as first change entry
INSERT INTO fhq_governance.execution_state_change_log (
    state_id,
    state_version_before,
    state_version_after,
    previous_state,
    new_state,
    change_type,
    change_reason,
    initiated_by
)
SELECT
    state_id,
    0,  -- Version before (none)
    1,  -- Version after
    '{}'::jsonb,  -- No previous state
    jsonb_build_object(
        'cognitive_fasting', cognitive_fasting,
        'defcon_level', defcon_level,
        'revalidation_required', revalidation_required,
        'fasting_reason', fasting_reason,
        'paper_trading_eligible', paper_trading_eligible,
        'learning_eligible', learning_eligible,
        'last_lids_block_at', last_lids_block_at,
        'lids_blocks_today', lids_blocks_today
    ),
    'INITIALIZATION',
    'CEO-DIR-2026-020 D4: Canonical execution state initialized',
    'STIG'
FROM fhq_governance.execution_state
ORDER BY state_id DESC
LIMIT 1;

-- 7. Log migration
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
    'MIGRATION_216_EXECUTION_STATE_AUDIT',
    'fhq_governance.execution_state',
    'SCHEMA_CHANGE',
    'STIG',
    'EXECUTED',
    'CEO-DIR-2026-020 D4: Created execution_state_change_log and initialized canonical state',
    'STIG',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-020',
        'deliverable', 'D4',
        'tables_created', ARRAY['fhq_governance.execution_state_change_log'],
        'columns_added', ARRAY['defcon_level', 'last_updated_at', 'last_updated_by', 'paper_trading_eligible', 'learning_eligible', 'state_version'],
        'functions_created', ARRAY['log_execution_state_change'],
        'triggers_created', ARRAY['trg_prevent_change_log_update']
    )
);

SELECT 'Migration 216 complete: Execution state audit trail established' as status;
