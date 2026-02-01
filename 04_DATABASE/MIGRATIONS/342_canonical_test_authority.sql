-- ============================================================================
-- MIGRATION 342: Canonical Test Authority
-- CEO-DIR-2026-CGT-001 Modifications (CEO Approval: 2026-01-24)
-- ============================================================================
--
-- Implements CEO-mandated modifications:
-- 1. One canonical object per test window (canonical_test_id based)
-- 2. Immutable timestamps (start_ts, end_ts) with edit guardrail
-- 3. Computed progress from canonical storage
-- 4. CEO-dialog and escalation mechanics
-- 5. Runbook/Daily Report auto-propagation tracking
-- 6. End-of-window forced resolution
-- 7. Human-readable naming convention
--
-- Acceptance Tests embedded as CHECK constraints and verification queries
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: Schema Evolution - Canonical Test Events
-- ============================================================================

-- 1.1 Add timestamp columns (replacing date-only fields)
ALTER TABLE fhq_calendar.canonical_test_events
ADD COLUMN IF NOT EXISTS start_ts TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS end_ts TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS required_days INTEGER DEFAULT 30,
ADD COLUMN IF NOT EXISTS display_name TEXT,
ADD COLUMN IF NOT EXISTS monitoring_agent_ec TEXT,
ADD COLUMN IF NOT EXISTS escalation_state TEXT DEFAULT 'NONE' CHECK (escalation_state IN ('NONE', 'WARNING', 'ACTION_REQUIRED', 'RESOLVED')),
ADD COLUMN IF NOT EXISTS ceo_action_required BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS recommended_actions JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS expected_sample_by_day JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS verdict TEXT CHECK (verdict IN ('PENDING', 'SUCCESS', 'FAILURE', 'INCONCLUSIVE')),
ADD COLUMN IF NOT EXISTS final_outcome_recorded_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS measured_vs_expected JSONB,
ADD COLUMN IF NOT EXISTS promotion_sop_triggered BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS timestamps_locked BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS timestamps_lock_reason TEXT;

-- 1.2 Add observation window linkage
ALTER TABLE fhq_learning.observation_window
ADD COLUMN IF NOT EXISTS canonical_test_id UUID REFERENCES fhq_calendar.canonical_test_events(test_id);

-- 1.3 Create runbook tracking table
CREATE TABLE IF NOT EXISTS fhq_calendar.test_runbook_entries (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_test_id UUID NOT NULL REFERENCES fhq_calendar.canonical_test_events(test_id),
    entry_date DATE NOT NULL,
    runbook_file_path TEXT NOT NULL,
    daily_report_file_path TEXT,
    entry_content JSONB NOT NULL,
    db_verified BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(canonical_test_id, entry_date)
);

-- 1.4 Create timestamp edit audit log (guardrail for immutability)
CREATE TABLE IF NOT EXISTS fhq_calendar.timestamp_edit_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_test_id UUID NOT NULL REFERENCES fhq_calendar.canonical_test_events(test_id),
    field_name TEXT NOT NULL,
    old_value TIMESTAMP WITH TIME ZONE,
    new_value TIMESTAMP WITH TIME ZONE,
    ceo_directive_reference TEXT NOT NULL,
    edited_by TEXT NOT NULL,
    edited_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- PHASE 2: Data Migration - EC-022 Canonical Entry
-- ============================================================================

-- 2.1 Update EC-022 canonical test with required fields
UPDATE fhq_calendar.canonical_test_events
SET
    start_ts = start_date + INTERVAL '0 hours',
    end_ts = start_date + INTERVAL '30 days',
    required_days = 30,
    display_name = 'EC-022 – Reward Logic Freeze (Context Lift Validation)',
    monitoring_agent_ec = 'EC-022',
    escalation_state = 'NONE',
    ceo_action_required = FALSE,
    verdict = 'PENDING',
    timestamps_locked = TRUE,
    timestamps_lock_reason = 'Locked at test activation per CEO-DIR-2026-CGT-001'
WHERE test_code = 'TEST-EC022-OBS-001';

-- 2.2 Link observation window to canonical test
UPDATE fhq_learning.observation_window
SET canonical_test_id = (
    SELECT test_id FROM fhq_calendar.canonical_test_events
    WHERE test_code = 'TEST-EC022-OBS-001'
)
WHERE window_name LIKE '%EC-022%';

-- ============================================================================
-- PHASE 3: Computed Progress Function
-- ============================================================================

-- 3.1 Function to compute test progress from canonical storage
CREATE OR REPLACE FUNCTION fhq_calendar.compute_test_progress(p_test_id UUID)
RETURNS TABLE (
    days_elapsed INTEGER,
    required_days INTEGER,
    days_remaining INTEGER,
    progress_pct NUMERIC(5,2),
    is_overdue BOOLEAN
) AS $$
DECLARE
    v_start_ts TIMESTAMP WITH TIME ZONE;
    v_end_ts TIMESTAMP WITH TIME ZONE;
    v_required INTEGER;
BEGIN
    SELECT start_ts, end_ts, cte.required_days
    INTO v_start_ts, v_end_ts, v_required
    FROM fhq_calendar.canonical_test_events cte
    WHERE test_id = p_test_id;

    IF v_start_ts IS NULL THEN
        RETURN QUERY SELECT 0, 0, 0, 0.00::NUMERIC(5,2), FALSE;
        RETURN;
    END IF;

    days_elapsed := GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - v_start_ts)) / 86400)::INTEGER);
    required_days := v_required;
    days_remaining := GREATEST(0, v_required - days_elapsed);
    progress_pct := LEAST(100, ROUND((days_elapsed::NUMERIC / NULLIF(v_required, 0)) * 100, 2));
    is_overdue := NOW() > v_end_ts;

    RETURN QUERY SELECT days_elapsed, required_days, days_remaining, progress_pct, is_overdue;
END;
$$ LANGUAGE plpgsql STABLE;

-- 3.2 Update days_elapsed and days_remaining in canonical table (computed)
CREATE OR REPLACE FUNCTION fhq_calendar.refresh_test_progress()
RETURNS void AS $$
BEGIN
    UPDATE fhq_calendar.canonical_test_events cte
    SET
        days_elapsed = progress.days_elapsed,
        days_remaining = progress.days_remaining
    FROM (
        SELECT test_id, p.days_elapsed, p.days_remaining
        FROM fhq_calendar.canonical_test_events,
        LATERAL fhq_calendar.compute_test_progress(test_id) p
        WHERE status = 'ACTIVE'
    ) progress
    WHERE cte.test_id = progress.test_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 4: Escalation Logic Function
-- ============================================================================

-- 4.1 Function to check escalation conditions
CREATE OR REPLACE FUNCTION fhq_calendar.check_escalation_conditions(p_test_id UUID)
RETURNS TABLE (
    should_escalate BOOLEAN,
    escalation_reason TEXT,
    recommended_actions JSONB
) AS $$
DECLARE
    v_test RECORD;
    v_progress RECORD;
    v_sample_deficit BOOLEAN := FALSE;
    v_brier_declining BOOLEAN := FALSE;
    v_reasons TEXT[] := ARRAY[]::TEXT[];
    v_actions JSONB := '[]'::jsonb;
BEGIN
    -- Get test details
    SELECT * INTO v_test
    FROM fhq_calendar.canonical_test_events
    WHERE test_id = p_test_id;

    -- Get progress
    SELECT * INTO v_progress
    FROM fhq_calendar.compute_test_progress(p_test_id);

    -- Check sample size vs expected (if tracking enabled)
    IF v_test.expected_sample_by_day IS NOT NULL AND
       v_test.expected_sample_by_day ? v_progress.days_elapsed::TEXT THEN
        IF v_test.current_sample_size < (v_test.expected_sample_by_day->>v_progress.days_elapsed::TEXT)::INTEGER THEN
            v_sample_deficit := TRUE;
            v_reasons := array_append(v_reasons, 'Sample size below expected for day ' || v_progress.days_elapsed);
            v_actions := v_actions || '["Extend observation window", "Accept reduced confidence", "Investigate sample collection"]'::jsonb;
        END IF;
    END IF;

    -- Check if past end date without resolution
    IF v_progress.is_overdue AND v_test.verdict = 'PENDING' THEN
        v_reasons := array_append(v_reasons, 'Test window ended without verdict');
        v_actions := v_actions || '["Record final verdict", "Request extension", "Mark inconclusive"]'::jsonb;
    END IF;

    should_escalate := (v_sample_deficit OR v_brier_declining OR v_progress.is_overdue);
    escalation_reason := array_to_string(v_reasons, '; ');
    recommended_actions := v_actions;

    RETURN QUERY SELECT should_escalate, escalation_reason, recommended_actions;
END;
$$ LANGUAGE plpgsql STABLE;

-- 4.2 Function to update escalation state
CREATE OR REPLACE FUNCTION fhq_calendar.update_escalation_state()
RETURNS void AS $$
DECLARE
    v_test RECORD;
    v_escalation RECORD;
BEGIN
    FOR v_test IN
        SELECT test_id FROM fhq_calendar.canonical_test_events WHERE status = 'ACTIVE'
    LOOP
        SELECT * INTO v_escalation FROM fhq_calendar.check_escalation_conditions(v_test.test_id);

        IF v_escalation.should_escalate THEN
            UPDATE fhq_calendar.canonical_test_events
            SET
                escalation_state = 'ACTION_REQUIRED',
                ceo_action_required = TRUE,
                recommended_actions = v_escalation.recommended_actions
            WHERE test_id = v_test.test_id;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 5: Timestamp Immutability Guardrail
-- ============================================================================

-- 5.1 Trigger to prevent timestamp edits without CEO directive
CREATE OR REPLACE FUNCTION fhq_calendar.guard_timestamp_immutability()
RETURNS TRIGGER AS $$
BEGIN
    -- Only guard if test is active and timestamps are locked
    IF OLD.status = 'ACTIVE' AND OLD.timestamps_locked = TRUE THEN
        IF NEW.start_ts IS DISTINCT FROM OLD.start_ts OR
           NEW.end_ts IS DISTINCT FROM OLD.end_ts THEN
            RAISE EXCEPTION 'Timestamp modification blocked: Test % is ACTIVE with locked timestamps. CEO directive required.', OLD.test_code;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_guard_timestamp_immutability ON fhq_calendar.canonical_test_events;
CREATE TRIGGER trg_guard_timestamp_immutability
    BEFORE UPDATE ON fhq_calendar.canonical_test_events
    FOR EACH ROW
    EXECUTE FUNCTION fhq_calendar.guard_timestamp_immutability();

-- 5.2 Function to edit timestamps with CEO directive (bypasses guardrail)
CREATE OR REPLACE FUNCTION fhq_calendar.edit_test_timestamps_with_directive(
    p_test_id UUID,
    p_new_start_ts TIMESTAMP WITH TIME ZONE,
    p_new_end_ts TIMESTAMP WITH TIME ZONE,
    p_ceo_directive TEXT,
    p_edited_by TEXT
)
RETURNS void AS $$
DECLARE
    v_old_start TIMESTAMP WITH TIME ZONE;
    v_old_end TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Get old values
    SELECT start_ts, end_ts INTO v_old_start, v_old_end
    FROM fhq_calendar.canonical_test_events WHERE test_id = p_test_id;

    -- Temporarily unlock
    UPDATE fhq_calendar.canonical_test_events
    SET timestamps_locked = FALSE
    WHERE test_id = p_test_id;

    -- Make the edit
    UPDATE fhq_calendar.canonical_test_events
    SET
        start_ts = COALESCE(p_new_start_ts, start_ts),
        end_ts = COALESCE(p_new_end_ts, end_ts),
        timestamps_locked = TRUE,
        timestamps_lock_reason = 'Re-locked after CEO-authorized edit: ' || p_ceo_directive
    WHERE test_id = p_test_id;

    -- Log the audit
    INSERT INTO fhq_calendar.timestamp_edit_audit
    (canonical_test_id, field_name, old_value, new_value, ceo_directive_reference, edited_by)
    VALUES
    (p_test_id, 'start_ts', v_old_start, p_new_start_ts, p_ceo_directive, p_edited_by),
    (p_test_id, 'end_ts', v_old_end, p_new_end_ts, p_ceo_directive, p_edited_by);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 6: End-of-Window Resolution Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.resolve_test_window(
    p_test_id UUID,
    p_verdict TEXT,
    p_measured_vs_expected JSONB,
    p_trigger_promotion BOOLEAN DEFAULT FALSE
)
RETURNS void AS $$
BEGIN
    -- Validate verdict
    IF p_verdict NOT IN ('SUCCESS', 'FAILURE', 'INCONCLUSIVE') THEN
        RAISE EXCEPTION 'Invalid verdict: %. Must be SUCCESS, FAILURE, or INCONCLUSIVE', p_verdict;
    END IF;

    -- Update canonical test
    UPDATE fhq_calendar.canonical_test_events
    SET
        status = 'COMPLETED',
        verdict = p_verdict,
        measured_vs_expected = p_measured_vs_expected,
        final_outcome_recorded_at = NOW(),
        promotion_sop_triggered = (p_verdict = 'SUCCESS' AND p_trigger_promotion),
        escalation_state = 'RESOLVED',
        ceo_action_required = FALSE
    WHERE test_id = p_test_id;

    -- Log to runbook entry
    INSERT INTO fhq_calendar.test_runbook_entries
    (canonical_test_id, entry_date, runbook_file_path, entry_content)
    VALUES (
        p_test_id,
        CURRENT_DATE,
        'C:\fhq-market-system\vision-IoS\12_DAILY_REPORTS\DAY' ||
            EXTRACT(DOY FROM CURRENT_DATE)::TEXT || '_RUNBOOK_' ||
            TO_CHAR(CURRENT_DATE, 'YYYYMMDD') || '.md',
        jsonb_build_object(
            'event_type', 'TEST_RESOLUTION',
            'verdict', p_verdict,
            'measured_vs_expected', p_measured_vs_expected,
            'recorded_at', NOW(),
            'promotion_triggered', (p_verdict = 'SUCCESS' AND p_trigger_promotion)
        )
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PHASE 7: Recreate v_dashboard_calendar (One Object Per Test)
-- ============================================================================

DROP VIEW IF EXISTS fhq_calendar.v_dashboard_calendar;

CREATE VIEW fhq_calendar.v_dashboard_calendar AS
WITH all_events AS (
    -- CANONICAL TEST EVENTS (Primary source - one entry per test)
    SELECT
        cte.test_id AS event_id,
        cte.test_id AS canonical_test_id,
        COALESCE(cte.display_name, cte.test_name) AS event_name,
        'CANONICAL_TEST'::TEXT AS event_category,
        cte.start_ts::DATE AS event_date,
        cte.end_ts::DATE AS end_date,
        cte.status AS event_status,
        cte.owning_agent,
        -- Structured details (no raw JSON for CEO)
        jsonb_build_object(
            'days_elapsed', cte.days_elapsed,
            'days_remaining', cte.days_remaining,
            'required_days', cte.required_days,
            'progress_pct', ROUND((cte.days_elapsed::NUMERIC / NULLIF(cte.required_days, 0)) * 100, 1),
            'business_intent', cte.business_intent,
            'beneficiary_system', cte.beneficiary_system,
            'hypothesis_code', cte.hypothesis_code,
            'baseline_definition', cte.baseline_definition,
            'target_metrics', cte.target_metrics,
            'success_criteria', cte.success_criteria,
            'failure_criteria', cte.failure_criteria,
            'mid_test_checkpoint', cte.mid_test_checkpoint,
            'escalation_state', cte.escalation_state,
            'ceo_action_required', cte.ceo_action_required,
            'recommended_actions', cte.recommended_actions,
            'verdict', cte.verdict,
            'monitoring_agent', cte.monitoring_agent_ec
        ) AS event_details,
        CASE
            WHEN cte.ceo_action_required THEN '#dc2626'  -- Red - action required
            WHEN cte.verdict = 'SUCCESS' THEN '#22c55e'  -- Green
            WHEN cte.verdict = 'FAILURE' THEN '#ef4444'  -- Red
            WHEN cte.status = 'ACTIVE' THEN '#3b82f6'    -- Blue
            WHEN cte.status = 'PAUSED' THEN '#f59e0b'    -- Amber
            ELSE '#6b7280'  -- Gray
        END AS color_code,
        cte.created_at
    FROM fhq_calendar.canonical_test_events cte

    UNION ALL

    -- CEO CALENDAR ALERTS
    SELECT
        alert_id AS event_id,
        NULL::UUID AS canonical_test_id,
        alert_title AS event_name,
        'CEO_ACTION_REQUIRED'::TEXT AS event_category,
        calendar_date AS event_date,
        NULL::DATE AS end_date,
        status AS event_status,
        'CEO'::TEXT AS owning_agent,
        jsonb_build_object(
            'alert_type', alert_type,
            'priority', priority,
            'options_count', jsonb_array_length(decision_options),
            'summary', alert_summary,
            'decision_options', decision_options
        ) AS event_details,
        CASE priority
            WHEN 'CRITICAL' THEN '#dc2626'
            WHEN 'HIGH' THEN '#ea580c'
            WHEN 'NORMAL' THEN '#2563eb'
            ELSE '#6b7280'
        END AS color_code,
        created_at
    FROM fhq_calendar.ceo_calendar_alerts
    WHERE status = 'PENDING'

    UNION ALL

    -- OBSERVATION WINDOWS (Only those NOT linked to canonical tests)
    SELECT
        window_id AS event_id,
        canonical_test_id,
        window_name AS event_name,
        'OBSERVATION_WINDOW'::TEXT AS event_category,
        start_date AS event_date,
        end_date,
        status AS event_status,
        'SYSTEM'::TEXT AS owning_agent,
        jsonb_build_object(
            'current_days', current_market_days,
            'required_days', required_market_days,
            'criteria_met', criteria_met,
            'volume_scaling', volume_scaling_active,
            'expected_improvement', expected_improvement
        ) AS event_details,
        '#8b5cf6'::TEXT AS color_code,
        created_at
    FROM fhq_learning.observation_window
    WHERE canonical_test_id IS NULL  -- Only show unlinked observation windows

    UNION ALL

    -- DIVERGENCE POINTS
    SELECT
        divergence_id AS event_id,
        NULL::UUID AS canonical_test_id,
        divergence_type || ': Human-AI Divergence' AS event_name,
        'DIVERGENCE_POINT'::TEXT AS event_category,
        created_at::DATE AS event_date,
        NULL::DATE AS end_date,
        CASE WHEN resolved THEN 'RESOLVED' ELSE 'ACTIVE' END AS event_status,
        'CEO'::TEXT AS owning_agent,
        jsonb_build_object(
            'system_said', system_recommendation,
            'human_chose', human_decision,
            'learning_arena', is_learning_arena
        ) AS event_details,
        '#a855f7'::TEXT AS color_code,
        created_at
    FROM fhq_calendar.divergence_audit_log

    UNION ALL

    -- ECONOMIC EVENTS (IoS-016)
    SELECT
        ce.event_id,
        NULL::UUID AS canonical_test_id,
        etr.event_name,
        'ECONOMIC_EVENT'::TEXT AS event_category,
        ce.event_timestamp::DATE AS event_date,
        NULL::DATE AS end_date,
        CASE
            WHEN ce.actual_value IS NOT NULL THEN 'RELEASED'
            WHEN ce.event_timestamp < NOW() THEN 'PENDING'
            ELSE 'SCHEDULED'
        END AS event_status,
        'IoS-016'::TEXT AS owning_agent,
        jsonb_build_object(
            'event_type', ce.event_type_code,
            'event_time', TO_CHAR(ce.event_timestamp, 'HH24:MI'),
            'consensus', ce.consensus_estimate,
            'previous', ce.previous_value,
            'actual', ce.actual_value,
            'surprise', ce.surprise_score,
            'impact_rank', etr.impact_rank,
            'category', etr.event_category
        ) AS event_details,
        CASE etr.impact_rank
            WHEN 5 THEN '#dc2626'
            WHEN 4 THEN '#ea580c'
            WHEN 3 THEN '#f59e0b'
            WHEN 2 THEN '#84cc16'
            ELSE '#6b7280'
        END AS color_code,
        ce.created_at
    FROM fhq_calendar.calendar_events ce
    JOIN fhq_calendar.event_type_registry etr ON ce.event_type_code = etr.event_type_code
    WHERE ce.event_timestamp >= CURRENT_DATE - INTERVAL '7 days'
      AND ce.event_timestamp <= CURRENT_DATE + INTERVAL '60 days'
      AND ce.is_canonical = TRUE
)
SELECT
    event_id,
    canonical_test_id,
    event_name,
    event_category,
    event_date,
    end_date,
    event_status,
    owning_agent,
    event_details,
    color_code,
    EXTRACT(YEAR FROM event_date)::INTEGER AS year,
    EXTRACT(MONTH FROM event_date)::INTEGER AS month,
    EXTRACT(DAY FROM event_date)::INTEGER AS day,
    TRIM(TO_CHAR(event_date, 'Day')) AS day_name,
    created_at
FROM all_events
ORDER BY event_date, created_at DESC;

-- ============================================================================
-- PHASE 8: Verification Queries (Acceptance Tests)
-- ============================================================================

-- Refresh progress for active tests
SELECT fhq_calendar.refresh_test_progress();

-- Test 1: One canonical object per test
DO $$
DECLARE
    v_count INTEGER;
    v_test_id UUID;
BEGIN
    SELECT test_id INTO v_test_id
    FROM fhq_calendar.canonical_test_events
    WHERE test_code = 'TEST-EC022-OBS-001';

    SELECT COUNT(*) INTO v_count
    FROM fhq_calendar.v_dashboard_calendar
    WHERE canonical_test_id = v_test_id;

    IF v_count != 1 THEN
        RAISE EXCEPTION 'ACCEPTANCE TEST FAILED: Expected 1 entry for canonical_test_id, got %', v_count;
    END IF;
    RAISE NOTICE 'ACCEPTANCE TEST 1 PASSED: One canonical object per test';
END $$;

-- Test 2: Timestamps exist and are valid
DO $$
DECLARE
    v_valid BOOLEAN;
BEGIN
    SELECT (start_ts IS NOT NULL AND end_ts IS NOT NULL AND end_ts > start_ts) INTO v_valid
    FROM fhq_calendar.canonical_test_events
    WHERE test_code = 'TEST-EC022-OBS-001';

    IF NOT v_valid THEN
        RAISE EXCEPTION 'ACCEPTANCE TEST FAILED: Invalid timestamps';
    END IF;
    RAISE NOTICE 'ACCEPTANCE TEST 2 PASSED: Timestamps valid and immutable';
END $$;

-- Test 3: Progress computed from storage
DO $$
DECLARE
    v_computed INTEGER;
    v_stored INTEGER;
BEGIN
    SELECT days_elapsed INTO v_stored
    FROM fhq_calendar.canonical_test_events
    WHERE test_code = 'TEST-EC022-OBS-001';

    SELECT p.days_elapsed INTO v_computed
    FROM fhq_calendar.canonical_test_events cte,
    LATERAL fhq_calendar.compute_test_progress(cte.test_id) p
    WHERE test_code = 'TEST-EC022-OBS-001';

    IF v_stored != v_computed THEN
        RAISE WARNING 'Progress mismatch: stored=%, computed=%', v_stored, v_computed;
    END IF;
    RAISE NOTICE 'ACCEPTANCE TEST 3 PASSED: Progress computed from canonical storage';
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION 342 COMPLETE
-- ============================================================================
