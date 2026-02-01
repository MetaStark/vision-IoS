-- CEO-DIR-2026-111 Phase 4: Broker Truth Precondition
-- Classification: MANDATORY – IMMEDIATE EXECUTION
-- Eliminates CD-EXEC-ALPACA-SOT-001 class errors
-- Implementor: STIG
-- Date: 2026-01-20

-- =============================================================================
-- PHASE 4: BROKER TRUTH PRECONDITION
-- Mandate: broker_truth_capture.py must execute before every paper-trading loop
-- Failure condition: If broker snapshot is stale → entire loop aborts
-- =============================================================================

BEGIN;

-- Step 1: Create broker truth precondition configuration
CREATE TABLE IF NOT EXISTS fhq_execution.broker_truth_precondition (
    precondition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Staleness threshold
    max_staleness_seconds INTEGER NOT NULL DEFAULT 300,  -- 5 minutes

    -- Enforcement mode
    enforcement_enabled BOOLEAN NOT NULL DEFAULT true,
    abort_on_stale BOOLEAN NOT NULL DEFAULT true,

    -- Affected execution loops
    affected_loops TEXT[] NOT NULL DEFAULT ARRAY['paper_trading', 'shadow_trading', 'signal_execution'],

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive_reference TEXT NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT true
);

-- Step 2: Insert CEO-DIR-2026-111 precondition configuration
INSERT INTO fhq_execution.broker_truth_precondition (
    max_staleness_seconds,
    enforcement_enabled,
    abort_on_stale,
    affected_loops,
    directive_reference,
    is_current
) VALUES (
    300,  -- 5 minute max staleness
    true,
    true,  -- CEO-DIR-2026-111: abort if stale
    ARRAY['paper_trading', 'shadow_trading', 'signal_execution', 'cpto_shadow'],
    'CEO-DIR-2026-111',
    true
);

-- Step 3: Create broker truth check log table
CREATE TABLE IF NOT EXISTS fhq_execution.broker_truth_check_log (
    check_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Check context
    execution_loop TEXT NOT NULL,
    check_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Broker state reference
    snapshot_id UUID,
    snapshot_timestamp TIMESTAMPTZ,
    snapshot_age_seconds NUMERIC,

    -- Threshold
    max_staleness_seconds INTEGER NOT NULL,

    -- Result
    is_fresh BOOLEAN NOT NULL,
    check_passed BOOLEAN NOT NULL,
    abort_triggered BOOLEAN NOT NULL DEFAULT false,

    -- Action taken
    action TEXT NOT NULL,  -- 'PROCEED', 'ABORT', 'REFRESH_REQUESTED'

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_broker_truth_check_loop
ON fhq_execution.broker_truth_check_log(execution_loop, check_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_broker_truth_check_abort
ON fhq_execution.broker_truth_check_log(abort_triggered, created_at DESC);

-- Step 4: Create function to check broker truth freshness
CREATE OR REPLACE FUNCTION fhq_execution.check_broker_truth_freshness(
    p_execution_loop TEXT
) RETURNS JSONB AS $$
DECLARE
    v_precondition RECORD;
    v_snapshot RECORD;
    v_age_seconds NUMERIC;
    v_is_fresh BOOLEAN;
    v_action TEXT;
    v_check_id UUID;
BEGIN
    -- Get precondition config
    SELECT * INTO v_precondition
    FROM fhq_execution.broker_truth_precondition
    WHERE is_current = true
    AND p_execution_loop = ANY(affected_loops)
    LIMIT 1;

    -- If no precondition for this loop, allow
    IF v_precondition IS NULL THEN
        RETURN jsonb_build_object(
            'check_passed', true,
            'action', 'PROCEED',
            'reason', 'No precondition configured for this loop',
            'execution_loop', p_execution_loop
        );
    END IF;

    -- Get latest broker snapshot
    SELECT snapshot_id, captured_at INTO v_snapshot
    FROM fhq_execution.broker_state_snapshots
    ORDER BY captured_at DESC
    LIMIT 1;

    -- Calculate age
    IF v_snapshot.snapshot_id IS NOT NULL THEN
        v_age_seconds := EXTRACT(EPOCH FROM (NOW() - v_snapshot.captured_at));
        v_is_fresh := v_age_seconds <= v_precondition.max_staleness_seconds;
    ELSE
        v_age_seconds := NULL;
        v_is_fresh := false;
    END IF;

    -- Determine action
    IF v_is_fresh THEN
        v_action := 'PROCEED';
    ELSIF v_precondition.abort_on_stale THEN
        v_action := 'ABORT';
    ELSE
        v_action := 'PROCEED_WITH_WARNING';
    END IF;

    -- Log check
    INSERT INTO fhq_execution.broker_truth_check_log (
        execution_loop,
        snapshot_id,
        snapshot_timestamp,
        snapshot_age_seconds,
        max_staleness_seconds,
        is_fresh,
        check_passed,
        abort_triggered,
        action
    ) VALUES (
        p_execution_loop,
        v_snapshot.snapshot_id,
        v_snapshot.captured_at,
        v_age_seconds,
        v_precondition.max_staleness_seconds,
        v_is_fresh,
        v_is_fresh OR NOT v_precondition.abort_on_stale,
        v_action = 'ABORT',
        v_action
    ) RETURNING check_id INTO v_check_id;

    RETURN jsonb_build_object(
        'check_id', v_check_id,
        'check_passed', v_is_fresh OR NOT v_precondition.abort_on_stale,
        'action', v_action,
        'is_fresh', v_is_fresh,
        'snapshot_age_seconds', v_age_seconds,
        'max_staleness_seconds', v_precondition.max_staleness_seconds,
        'snapshot_id', v_snapshot.snapshot_id,
        'snapshot_timestamp', v_snapshot.captured_at,
        'execution_loop', p_execution_loop,
        'enforcement_enabled', v_precondition.enforcement_enabled
    );
END;
$$ LANGUAGE plpgsql;

-- Step 5: Create execution loop abort function
CREATE OR REPLACE FUNCTION fhq_execution.abort_if_broker_stale(
    p_execution_loop TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    v_result JSONB;
BEGIN
    v_result := fhq_execution.check_broker_truth_freshness(p_execution_loop);

    IF (v_result->>'action') = 'ABORT' THEN
        RAISE NOTICE 'BROKER_TRUTH_ABORT: % loop aborted - broker snapshot stale (age: %s, max: %s)',
            p_execution_loop,
            v_result->>'snapshot_age_seconds',
            v_result->>'max_staleness_seconds';
        RETURN false;  -- Abort
    END IF;

    RETURN true;  -- Proceed
END;
$$ LANGUAGE plpgsql;

-- Step 6: Log governance action
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
    'BROKER_TRUTH_PRECONDITION',
    'CEO-DIR-2026-111-PHASE-4',
    'EXECUTION_CONSTRAINT',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-111 Phase 4: Broker truth precondition enforced. ' ||
    'broker_truth_capture.py must execute before every paper-trading loop. ' ||
    'If broker snapshot is stale (>300s) → entire loop ABORTS. ' ||
    'Eliminates CD-EXEC-ALPACA-SOT-001 class errors. ' ||
    'Ensures belief == reality at all times.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-111',
        'phase', 4,
        'max_staleness_seconds', 300,
        'abort_on_stale', true,
        'affected_loops', ARRAY['paper_trading', 'shadow_trading', 'signal_execution', 'cpto_shadow'],
        'error_class_eliminated', 'CD-EXEC-ALPACA-SOT-001'
    ),
    false
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify precondition config
SELECT * FROM fhq_execution.broker_truth_precondition WHERE is_current = true;

-- Test freshness check
SELECT fhq_execution.check_broker_truth_freshness('shadow_trading');
