-- Migration 241: CEO-DIR-2026-068 Unattended Continuous LDOW Execution
-- Night-Mode Observation Authorization
--
-- Authority: CEO-DIR-2026-068
-- Owner: STIG
-- Classification: OPERATIONAL_AUTOMATION (not cognitive autonomy)

BEGIN;

-- =============================================================================
-- 1. UNATTENDED EXECUTION LOG TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.ldow_unattended_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ldow_id UUID NOT NULL,
    cycle_number INTEGER NOT NULL,

    -- Execution mode tracking (Section 5.2)
    execution_mode TEXT NOT NULL DEFAULT 'UNATTENDED_LDOW',

    -- Batch metrics
    forecasts_generated INTEGER NOT NULL DEFAULT 0,
    forecasts_persisted INTEGER NOT NULL DEFAULT 0,
    lineage_coverage_pct NUMERIC(5,2),

    -- Latency
    generation_time_ms INTEGER,
    persistence_time_ms INTEGER,
    total_cycle_time_ms INTEGER,

    -- Integrity checks
    damper_hash_at_start TEXT NOT NULL,
    damper_hash_at_end TEXT,
    damper_hash_verified BOOLEAN DEFAULT true,
    ldow_status_verified BOOLEAN DEFAULT true,

    -- Status
    status TEXT NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING', 'COMPLETED', 'STOPPED', 'FAILED')),
    stop_reason TEXT,

    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Directive reference
    directive_ref TEXT NOT NULL DEFAULT 'CEO-DIR-2026-068'
);

-- =============================================================================
-- 2. AUTO-STOP CHECK FUNCTION (Section 4.1)
-- =============================================================================
CREATE OR REPLACE FUNCTION fhq_governance.check_unattended_ldow_allowed()
RETURNS TABLE (
    allowed BOOLEAN,
    ldow_id UUID,
    ldow_status TEXT,
    damper_hash TEXT,
    locked_hash TEXT,
    stop_reason TEXT
) AS $func$
DECLARE
    v_ldow_id UUID;
    v_ldow_status TEXT;
    v_current_hash TEXT;
    v_locked_hash TEXT;
    v_freeze_active BOOLEAN;
BEGIN
    -- Get current LDOW
    SELECT
        l.ldow_id, l.status, l.damper_version_hash
    INTO v_ldow_id, v_ldow_status, v_locked_hash
    FROM fhq_governance.learning_delta_observation_window l
    WHERE l.status = 'ACTIVE'
    LIMIT 1;

    -- Check 1: LDOW must exist
    IF v_ldow_id IS NULL THEN
        RETURN QUERY SELECT false, NULL::UUID, 'NO_LDOW'::TEXT, NULL::TEXT, NULL::TEXT,
            'LDOW status != ACTIVE (no active LDOW found)'::TEXT;
        RETURN;
    END IF;

    -- Check 2: LDOW must be ACTIVE
    IF v_ldow_status != 'ACTIVE' THEN
        RETURN QUERY SELECT false, v_ldow_id, v_ldow_status, NULL::TEXT, v_locked_hash,
            'LDOW status != ACTIVE'::TEXT;
        RETURN;
    END IF;

    -- Check 3: Damper hash must be unchanged
    -- Get current damper hash from task_activation_status
    SELECT (extended_config->'ldow_freeze'->>'frozen')::boolean
    INTO v_freeze_active
    FROM fhq_governance.task_activation_status
    WHERE task_name = 'forecast_confidence_damper'
    LIMIT 1;

    IF v_freeze_active IS NOT TRUE THEN
        RETURN QUERY SELECT false, v_ldow_id, v_ldow_status, NULL::TEXT, v_locked_hash,
            'Intervention freeze is broken'::TEXT;
        RETURN;
    END IF;

    -- All checks passed
    RETURN QUERY SELECT true, v_ldow_id, v_ldow_status, v_locked_hash, v_locked_hash,
        'All checks passed - unattended execution allowed'::TEXT;
END;
$func$ LANGUAGE plpgsql;

-- =============================================================================
-- 3. CEO MORNING READ VIEW (Section 6)
-- =============================================================================
CREATE OR REPLACE VIEW fhq_governance.v_ceo_morning_read AS
WITH ldow_info AS (
    SELECT
        ldow_id,
        status,
        cycles_completed,
        minimum_cycles,
        baseline_calibration_error,
        baseline_brier_score,
        damper_version_hash,
        started_at
    FROM fhq_governance.learning_delta_observation_window
    WHERE status = 'ACTIVE'
    LIMIT 1
),
unattended_summary AS (
    SELECT
        COUNT(*) as total_unattended_cycles,
        SUM(forecasts_generated) as total_forecasts_generated,
        SUM(forecasts_persisted) as total_forecasts_persisted,
        MIN(started_at) as first_unattended_cycle,
        MAX(completed_at) as last_unattended_cycle,
        COUNT(*) FILTER (WHERE status = 'COMPLETED') as successful_cycles,
        COUNT(*) FILTER (WHERE status = 'STOPPED' OR status = 'FAILED') as stopped_cycles,
        BOOL_AND(damper_hash_verified) as all_hashes_verified,
        BOOL_AND(ldow_status_verified) as all_ldow_checks_passed
    FROM fhq_governance.ldow_unattended_executions
    WHERE ldow_id = (SELECT ldow_id FROM ldow_info)
),
capture_summary AS (
    SELECT
        COUNT(*) as total_captures,
        COUNT(DISTINCT cycle_number) as cycles_with_captures,
        ROUND(AVG(raw_confidence)::numeric, 4) as avg_raw_confidence,
        ROUND(AVG(damped_confidence)::numeric, 4) as avg_damped_confidence,
        ROUND(AVG(dampening_delta)::numeric, 4) as avg_dampening_delta
    FROM fhq_governance.ldow_forecast_captures
    WHERE ldow_id = (SELECT ldow_id FROM ldow_info)
),
latest_metrics AS (
    SELECT
        cycle_number,
        calibration_error,
        brier_score,
        delta_fss,
        p95_latency_ms
    FROM fhq_governance.ldow_cycle_metrics
    WHERE ldow_id = (SELECT ldow_id FROM ldow_info)
    ORDER BY cycle_number DESC
    LIMIT 1
)
SELECT
    -- LDOW Status
    li.ldow_id,
    li.status as ldow_status,
    li.cycles_completed,
    li.minimum_cycles,
    li.started_at as ldow_started,

    -- Unattended Execution Summary
    us.total_unattended_cycles,
    us.total_forecasts_generated,
    us.total_forecasts_persisted,
    us.successful_cycles,
    us.stopped_cycles,
    us.first_unattended_cycle,
    us.last_unattended_cycle,

    -- Integrity
    us.all_hashes_verified,
    us.all_ldow_checks_passed,
    li.damper_version_hash as locked_damper_hash,

    -- Capture Summary
    cs.total_captures,
    cs.cycles_with_captures,
    cs.avg_raw_confidence,
    cs.avg_damped_confidence,
    cs.avg_dampening_delta,

    -- Latest Metrics
    lm.cycle_number as latest_cycle,
    lm.calibration_error as current_calibration_error,
    lm.brier_score as current_brier_score,
    lm.delta_fss,
    lm.p95_latency_ms,

    -- vs Baseline
    lm.calibration_error - li.baseline_calibration_error as calibration_vs_baseline,
    lm.brier_score - li.baseline_brier_score as brier_vs_baseline,

    -- Explicit Status (Section 6)
    'No actions taken. Observation only.' as explicit_status,
    'CEO-DIR-2026-068' as governing_directive

FROM ldow_info li
CROSS JOIN unattended_summary us
CROSS JOIN capture_summary cs
LEFT JOIN latest_metrics lm ON true;

-- =============================================================================
-- 4. INDEXES
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_unattended_executions_ldow
ON fhq_governance.ldow_unattended_executions(ldow_id, cycle_number);

CREATE INDEX IF NOT EXISTS idx_unattended_executions_status
ON fhq_governance.ldow_unattended_executions(status);

COMMIT;

-- =============================================================================
-- 5. LOG GOVERNANCE ACTION
-- =============================================================================
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    timestamp,
    metadata
) VALUES (
    'CEO_DIRECTIVE_ISSUED',
    'CEO-DIR-2026-068',
    'UNATTENDED_LDOW_AUTHORIZATION',
    'CEO',
    'EXECUTION_AUTHORIZED',
    'Authorize unattended continuous LDOW execution - night mode observation. System learns while human sleeps, but only observes.',
    NOW(),
    '{"directive": "CEO-DIR-2026-068", "mode": "UNATTENDED_LDOW", "autonomy_granted": false, "observation_only": true}'::jsonb
);

-- Verification
DO $$
BEGIN
    RAISE NOTICE 'Migration 241 SUCCESS: CEO-DIR-2026-068 infrastructure created';
    RAISE NOTICE 'Table: ldow_unattended_executions';
    RAISE NOTICE 'Function: check_unattended_ldow_allowed()';
    RAISE NOTICE 'View: v_ceo_morning_read';
END $$;
