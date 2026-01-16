-- Migration 272: G3.5 Shadow Mode Infrastructure
-- CEO Directive: 48h shadow mode before G4 production activation
-- Purpose: Verify determinism, no drift in tagging logic
-- Classification: GOVERNANCE-CRITICAL / PRE-PRODUCTION
-- Executed by: STIG (EC-003_2026_PRODUCTION)

BEGIN;

-- ============================================================================
-- 272.1: Create Shadow Mode State Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.shadow_mode_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    planned_end_at TIMESTAMPTZ NOT NULL,
    actual_end_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'COMPLETED', 'ABORTED', 'PROMOTED')),
    initiated_by TEXT NOT NULL,
    determinism_checks INTEGER DEFAULT 0,
    determinism_failures INTEGER DEFAULT 0,
    drift_detected BOOLEAN DEFAULT FALSE,
    promotion_eligible BOOLEAN DEFAULT FALSE,
    promotion_decision TEXT,
    promoted_at TIMESTAMPTZ,
    promoted_by TEXT,
    session_hash TEXT,
    metadata JSONB DEFAULT '{}'::JSONB
);

CREATE INDEX idx_shadow_session_status ON fhq_calendar.shadow_mode_sessions(status);

COMMENT ON TABLE fhq_calendar.shadow_mode_sessions IS
'G3.5: Shadow mode session tracking. 48h parallel operation before G4 promotion.';

-- ============================================================================
-- 272.2: Create Shadow Tagging Results Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.shadow_tagging_results (
    shadow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES fhq_calendar.shadow_mode_sessions(session_id),
    forecast_id UUID,
    asset_id TEXT NOT NULL,
    forecast_timestamp TIMESTAMPTZ NOT NULL,

    -- Shadow tagging output
    shadow_proximity_tag TEXT,
    shadow_adjacent_event_id UUID,
    shadow_impact_rank INTEGER,
    shadow_computation_hash TEXT,

    -- For determinism comparison
    run_number INTEGER NOT NULL DEFAULT 1,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Determinism check
    matches_previous BOOLEAN,
    previous_hash TEXT,
    drift_detected BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_shadow_tagging_session ON fhq_calendar.shadow_tagging_results(session_id);
CREATE INDEX idx_shadow_tagging_forecast ON fhq_calendar.shadow_tagging_results(forecast_id);
CREATE INDEX idx_shadow_tagging_drift ON fhq_calendar.shadow_tagging_results(drift_detected) WHERE drift_detected = TRUE;

COMMENT ON TABLE fhq_calendar.shadow_tagging_results IS
'G3.5: Shadow tagging results for determinism verification. Each run stored for comparison.';

-- ============================================================================
-- 272.3: Create Shadow Mode Activation Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.activate_shadow_mode(
    p_session_name TEXT,
    p_duration_hours INTEGER DEFAULT 48,
    p_initiated_by TEXT DEFAULT 'STIG'
)
RETURNS TABLE (
    session_id UUID,
    status TEXT,
    started_at TIMESTAMPTZ,
    planned_end_at TIMESTAMPTZ,
    message TEXT
) AS $$
DECLARE
    v_session_id UUID;
    v_end_at TIMESTAMPTZ;
BEGIN
    -- Check for existing active session
    IF EXISTS (SELECT 1 FROM fhq_calendar.shadow_mode_sessions WHERE status = 'ACTIVE') THEN
        RETURN QUERY SELECT
            NULL::UUID,
            'ERROR'::TEXT,
            NULL::TIMESTAMPTZ,
            NULL::TIMESTAMPTZ,
            'Active shadow mode session already exists. Complete or abort before starting new.'::TEXT;
        RETURN;
    END IF;

    v_end_at := NOW() + (p_duration_hours || ' hours')::INTERVAL;

    INSERT INTO fhq_calendar.shadow_mode_sessions (
        session_name,
        started_at,
        planned_end_at,
        status,
        initiated_by,
        metadata
    ) VALUES (
        p_session_name,
        NOW(),
        v_end_at,
        'ACTIVE',
        p_initiated_by,
        jsonb_build_object(
            'duration_hours', p_duration_hours,
            'activation_context', 'G3.5 pre-G4 validation',
            'verification_targets', ARRAY['tag_event_proximity', 'resolve_source_conflict', 'canonicalize_staging_event']
        )
    )
    RETURNING shadow_mode_sessions.session_id INTO v_session_id;

    -- Log activation
    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type,
        initiated_by, initiated_at, decision, decision_rationale,
        metadata, agent_id, timestamp
    ) VALUES (
        gen_random_uuid(),
        'G3_5_SHADOW_MODE_ACTIVATED',
        'IoS-016',
        'INSTITUTIONAL_OPERATING_STANDARD',
        p_initiated_by,
        NOW(),
        'ACTIVATED',
        format('Shadow mode session %s activated for %s hours', v_session_id, p_duration_hours),
        jsonb_build_object(
            'session_id', v_session_id,
            'duration_hours', p_duration_hours,
            'planned_end', v_end_at
        ),
        'STIG',
        NOW()
    );

    RETURN QUERY SELECT
        v_session_id,
        'ACTIVE'::TEXT,
        NOW(),
        v_end_at,
        format('Shadow mode activated. Session %s runs until %s', v_session_id, v_end_at)::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_calendar.activate_shadow_mode IS
'G3.5: Activates shadow mode for specified duration. Default 48h per CEO directive.';

-- ============================================================================
-- 272.4: Create Shadow Tagging Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.run_shadow_tagging(
    p_session_id UUID,
    p_asset_id TEXT,
    p_forecast_timestamp TIMESTAMPTZ,
    p_forecast_id UUID DEFAULT NULL
)
RETURNS TABLE (
    shadow_id UUID,
    proximity_tag TEXT,
    adjacent_event_id UUID,
    impact_rank INTEGER,
    determinism_status TEXT,
    computation_hash TEXT
) AS $$
DECLARE
    v_shadow_id UUID;
    v_tag TEXT;
    v_event_id UUID;
    v_impact INTEGER;
    v_hash TEXT;
    v_run_number INTEGER;
    v_previous_hash TEXT;
    v_matches BOOLEAN;
    v_session_status TEXT;
BEGIN
    -- Verify session is active
    SELECT status INTO v_session_status
    FROM fhq_calendar.shadow_mode_sessions
    WHERE session_id = p_session_id;

    IF v_session_status IS NULL THEN
        RAISE EXCEPTION 'Shadow session % not found', p_session_id;
    END IF;

    IF v_session_status != 'ACTIVE' THEN
        RAISE EXCEPTION 'Shadow session % is not active (status: %)', p_session_id, v_session_status;
    END IF;

    -- Get run number for this forecast
    SELECT COALESCE(MAX(run_number), 0) + 1 INTO v_run_number
    FROM fhq_calendar.shadow_tagging_results
    WHERE session_id = p_session_id
    AND asset_id = p_asset_id
    AND forecast_timestamp = p_forecast_timestamp;

    -- Compute proximity tag (same logic as production)
    SELECT
        CASE
            WHEN ce.event_id IS NOT NULL AND
                 ABS(EXTRACT(EPOCH FROM (p_forecast_timestamp - ce.event_timestamp))) <=
                 ldc.pre_event_window_hours * 3600 THEN 'EVENT_ADJACENT'
            WHEN ce.event_id IS NOT NULL AND
                 p_forecast_timestamp > ce.event_timestamp AND
                 EXTRACT(EPOCH FROM (p_forecast_timestamp - ce.event_timestamp)) <=
                 ldc.post_event_window_hours * 3600 THEN 'POST_EVENT'
            ELSE 'EVENT_NEUTRAL'
        END,
        ce.event_id,
        COALESCE(etr.impact_rank, 0)
    INTO v_tag, v_event_id, v_impact
    FROM (SELECT 1) AS dummy
    LEFT JOIN fhq_calendar.event_asset_mapping eam ON eam.asset_id = p_asset_id
    LEFT JOIN fhq_calendar.calendar_events ce ON ce.event_id = eam.event_id
        AND ce.is_canonical = TRUE
        AND ABS(EXTRACT(EPOCH FROM (p_forecast_timestamp - ce.event_timestamp))) < 86400 * 14
    LEFT JOIN fhq_calendar.event_type_registry etr ON etr.event_type_code = ce.event_type_code
    LEFT JOIN fhq_calendar.leakage_detection_config ldc ON ldc.impact_rank = etr.impact_rank
    ORDER BY ABS(EXTRACT(EPOCH FROM (p_forecast_timestamp - ce.event_timestamp))) NULLS LAST
    LIMIT 1;

    -- Default if no events
    v_tag := COALESCE(v_tag, 'EVENT_NEUTRAL');
    v_impact := COALESCE(v_impact, 0);

    -- Compute deterministic hash
    v_hash := encode(sha256(
        (p_asset_id || p_forecast_timestamp::TEXT || v_tag ||
         COALESCE(v_event_id::TEXT, 'NULL') || v_impact::TEXT)::BYTEA
    ), 'hex');

    -- Get previous hash for comparison
    SELECT computation_hash INTO v_previous_hash
    FROM fhq_calendar.shadow_tagging_results
    WHERE session_id = p_session_id
    AND asset_id = p_asset_id
    AND forecast_timestamp = p_forecast_timestamp
    AND run_number = v_run_number - 1;

    v_matches := (v_previous_hash IS NULL) OR (v_hash = v_previous_hash);

    -- Store result
    INSERT INTO fhq_calendar.shadow_tagging_results (
        session_id, forecast_id, asset_id, forecast_timestamp,
        shadow_proximity_tag, shadow_adjacent_event_id, shadow_impact_rank,
        shadow_computation_hash, run_number, matches_previous, previous_hash,
        drift_detected
    ) VALUES (
        p_session_id, p_forecast_id, p_asset_id, p_forecast_timestamp,
        v_tag, v_event_id, v_impact,
        v_hash, v_run_number, v_matches, v_previous_hash,
        NOT v_matches AND v_previous_hash IS NOT NULL
    )
    RETURNING shadow_tagging_results.shadow_id INTO v_shadow_id;

    -- Update session stats
    UPDATE fhq_calendar.shadow_mode_sessions
    SET
        determinism_checks = determinism_checks + 1,
        determinism_failures = determinism_failures + CASE WHEN NOT v_matches AND v_previous_hash IS NOT NULL THEN 1 ELSE 0 END,
        drift_detected = drift_detected OR (NOT v_matches AND v_previous_hash IS NOT NULL)
    WHERE session_id = p_session_id;

    RETURN QUERY SELECT
        v_shadow_id,
        v_tag,
        v_event_id,
        v_impact,
        CASE
            WHEN v_previous_hash IS NULL THEN 'BASELINE'
            WHEN v_matches THEN 'DETERMINISTIC'
            ELSE 'DRIFT_DETECTED'
        END,
        v_hash;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_calendar.run_shadow_tagging IS
'G3.5: Runs shadow tagging and compares to previous runs for determinism verification.';

-- ============================================================================
-- 272.5: Create Shadow Mode Status Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.get_shadow_mode_status(
    p_session_id UUID DEFAULT NULL
)
RETURNS TABLE (
    session_id UUID,
    session_name TEXT,
    status TEXT,
    started_at TIMESTAMPTZ,
    planned_end_at TIMESTAMPTZ,
    hours_remaining NUMERIC,
    determinism_checks INTEGER,
    determinism_failures INTEGER,
    drift_detected BOOLEAN,
    promotion_eligible BOOLEAN,
    health_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.session_id,
        s.session_name,
        s.status,
        s.started_at,
        s.planned_end_at,
        ROUND(EXTRACT(EPOCH FROM (s.planned_end_at - NOW())) / 3600, 1),
        s.determinism_checks,
        s.determinism_failures,
        s.drift_detected,
        s.promotion_eligible,
        CASE
            WHEN s.status != 'ACTIVE' THEN s.status
            WHEN s.drift_detected THEN 'DRIFT_DETECTED'
            WHEN s.determinism_failures > 0 THEN 'FAILURES_DETECTED'
            WHEN NOW() > s.planned_end_at THEN 'READY_FOR_PROMOTION'
            WHEN s.determinism_checks < 10 THEN 'WARMING_UP'
            ELSE 'HEALTHY'
        END
    FROM fhq_calendar.shadow_mode_sessions s
    WHERE (p_session_id IS NULL AND s.status = 'ACTIVE')
       OR s.session_id = p_session_id
    ORDER BY s.started_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_calendar.get_shadow_mode_status IS
'G3.5: Returns current shadow mode session status and health.';

-- ============================================================================
-- 272.6: Create Shadow Mode Completion Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.complete_shadow_mode(
    p_session_id UUID,
    p_decision TEXT,  -- 'PROMOTE' or 'ABORT'
    p_decided_by TEXT DEFAULT 'CEO'
)
RETURNS TABLE (
    session_id UUID,
    final_status TEXT,
    determinism_checks INTEGER,
    determinism_failures INTEGER,
    drift_detected BOOLEAN,
    promotion_eligible BOOLEAN,
    message TEXT
) AS $$
DECLARE
    v_session RECORD;
    v_final_status TEXT;
    v_session_hash TEXT;
BEGIN
    -- Get session
    SELECT * INTO v_session
    FROM fhq_calendar.shadow_mode_sessions
    WHERE shadow_mode_sessions.session_id = p_session_id;

    IF v_session IS NULL THEN
        RAISE EXCEPTION 'Session % not found', p_session_id;
    END IF;

    IF v_session.status != 'ACTIVE' THEN
        RAISE EXCEPTION 'Session % is not active (status: %)', p_session_id, v_session.status;
    END IF;

    -- Compute session hash
    SELECT encode(sha256(string_agg(
        shadow_id::TEXT || shadow_computation_hash,
        '|' ORDER BY shadow_id
    )::BYTEA), 'hex')
    INTO v_session_hash
    FROM fhq_calendar.shadow_tagging_results
    WHERE shadow_tagging_results.session_id = p_session_id;

    -- Determine eligibility
    IF v_session.drift_detected THEN
        v_final_status := 'ABORTED';
    ELSIF p_decision = 'PROMOTE' AND v_session.determinism_failures = 0 THEN
        v_final_status := 'PROMOTED';
    ELSIF p_decision = 'ABORT' THEN
        v_final_status := 'ABORTED';
    ELSE
        v_final_status := 'COMPLETED';
    END IF;

    -- Update session
    UPDATE fhq_calendar.shadow_mode_sessions
    SET
        status = v_final_status,
        actual_end_at = NOW(),
        promotion_eligible = (v_session.determinism_failures = 0 AND NOT v_session.drift_detected),
        promotion_decision = p_decision,
        promoted_at = CASE WHEN v_final_status = 'PROMOTED' THEN NOW() ELSE NULL END,
        promoted_by = CASE WHEN v_final_status = 'PROMOTED' THEN p_decided_by ELSE NULL END,
        session_hash = v_session_hash
    WHERE shadow_mode_sessions.session_id = p_session_id;

    -- Log completion
    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type,
        initiated_by, initiated_at, decision, decision_rationale,
        metadata, agent_id, timestamp
    ) VALUES (
        gen_random_uuid(),
        'G3_5_SHADOW_MODE_' || v_final_status,
        'IoS-016',
        'INSTITUTIONAL_OPERATING_STANDARD',
        p_decided_by,
        NOW(),
        v_final_status,
        format('Shadow mode session %s %s. Checks: %s, Failures: %s, Drift: %s',
            p_session_id, v_final_status, v_session.determinism_checks,
            v_session.determinism_failures, v_session.drift_detected),
        jsonb_build_object(
            'session_id', p_session_id,
            'session_hash', v_session_hash,
            'determinism_checks', v_session.determinism_checks,
            'determinism_failures', v_session.determinism_failures,
            'drift_detected', v_session.drift_detected
        ),
        'STIG',
        NOW()
    );

    RETURN QUERY SELECT
        p_session_id,
        v_final_status,
        v_session.determinism_checks,
        v_session.determinism_failures,
        v_session.drift_detected,
        (v_session.determinism_failures = 0 AND NOT v_session.drift_detected),
        format('Shadow mode %s. Session hash: %s', v_final_status, LEFT(v_session_hash, 16) || '...')::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_calendar.complete_shadow_mode IS
'G3.5: Completes shadow mode session with PROMOTE or ABORT decision.';

-- ============================================================================
-- 272.7: Create Shadow Mode Dashboard View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_calendar.shadow_mode_dashboard AS
SELECT
    s.session_id,
    s.session_name,
    s.status,
    s.started_at,
    s.planned_end_at,
    ROUND(EXTRACT(EPOCH FROM (s.planned_end_at - NOW())) / 3600, 1) AS hours_remaining,
    s.determinism_checks,
    s.determinism_failures,
    s.drift_detected,
    s.promotion_eligible,
    CASE
        WHEN s.status != 'ACTIVE' THEN s.status
        WHEN s.drift_detected THEN 'DRIFT_DETECTED - WILL ABORT'
        WHEN s.determinism_failures > 0 THEN 'FAILURES - REVIEW REQUIRED'
        WHEN NOW() > s.planned_end_at THEN 'READY FOR PROMOTION'
        WHEN s.determinism_checks < 10 THEN 'WARMING UP'
        ELSE 'HEALTHY - MONITORING'
    END AS health_status,
    (SELECT COUNT(*) FROM fhq_calendar.shadow_tagging_results r WHERE r.session_id = s.session_id) AS total_tags,
    (SELECT COUNT(DISTINCT asset_id) FROM fhq_calendar.shadow_tagging_results r WHERE r.session_id = s.session_id) AS unique_assets
FROM fhq_calendar.shadow_mode_sessions s
ORDER BY s.started_at DESC;

COMMENT ON VIEW fhq_calendar.shadow_mode_dashboard IS
'G3.5: Real-time dashboard for shadow mode monitoring.';

-- ============================================================================
-- 272.8: Governance Logging
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'G3_5_SHADOW_MODE_INFRASTRUCTURE',
    'IoS-016',
    'INSTITUTIONAL_OPERATING_STANDARD',
    'STIG',
    NOW(),
    'IMPLEMENTED',
    'G3.5 Shadow Mode infrastructure created. 48h parallel operation before G4 promotion.',
    jsonb_build_object(
        'migration', '272_g3_5_shadow_mode.sql',
        'tables_created', ARRAY['shadow_mode_sessions', 'shadow_tagging_results'],
        'functions_created', ARRAY[
            'activate_shadow_mode',
            'run_shadow_tagging',
            'get_shadow_mode_status',
            'complete_shadow_mode'
        ],
        'views_created', ARRAY['shadow_mode_dashboard'],
        'verification_targets', ARRAY['tag_event_proximity', 'determinism', 'drift_detection']
    ),
    'STIG',
    NOW()
);

-- ============================================================================
-- 272.9: Update IoS Audit Log
-- ============================================================================

INSERT INTO fhq_meta.ios_audit_log (
    audit_id,
    ios_id,
    event_type,
    event_timestamp,
    actor,
    gate_level,
    event_data,
    evidence_hash
) VALUES (
    gen_random_uuid(),
    'IoS-016',
    'G3_5_SHADOW_MODE_READY',
    NOW(),
    'STIG',
    'G3.5',
    jsonb_build_object(
        'status', 'INFRASTRUCTURE_READY',
        'duration_default', '48 hours',
        'verification', ARRAY['determinism', 'drift_detection', 'hash_comparison'],
        'promotion_criteria', 'Zero drift, zero failures'
    ),
    encode(sha256('G3_5_SHADOW_MODE_READY_20260116'::BYTEA), 'hex')
);

COMMIT;

-- ============================================================================
-- Verification
-- ============================================================================
-- Activate shadow mode:
-- SELECT * FROM fhq_calendar.activate_shadow_mode('G3.5_PRE_G4', 48, 'CEO');
--
-- Check status:
-- SELECT * FROM fhq_calendar.shadow_mode_dashboard;
--
-- Run shadow tagging:
-- SELECT * FROM fhq_calendar.run_shadow_tagging(session_id, 'BTC-USD', NOW());
--
-- Complete session:
-- SELECT * FROM fhq_calendar.complete_shadow_mode(session_id, 'PROMOTE', 'CEO');
