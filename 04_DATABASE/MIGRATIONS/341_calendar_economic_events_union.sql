-- ============================================================================
-- MIGRATION 341: Add Economic Events to Dashboard Calendar View
-- CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001 Gap Remediation
-- ============================================================================
-- Section 2: Dashboard Authority Layer must include IoS-016 economic events
-- Gap identified: 45 events in DB, 0 displayed in UI
-- ============================================================================

BEGIN;

-- ============================================================================
-- RECREATE v_dashboard_calendar WITH ECONOMIC EVENTS
-- ============================================================================

DROP VIEW IF EXISTS fhq_calendar.v_dashboard_calendar;

CREATE OR REPLACE VIEW fhq_calendar.v_dashboard_calendar AS
WITH all_events AS (
    -- ========================================================================
    -- ACTIVE TESTS (canonical_test_events)
    -- ========================================================================
    SELECT
        test_id as event_id,
        test_name as event_name,
        'ACTIVE_TEST' as event_category,
        start_date as event_date,
        end_date,
        status as event_status,
        owning_agent,
        jsonb_build_object(
            'days_elapsed', days_elapsed,
            'days_remaining', days_remaining,
            'sample_status', sample_trajectory_status,
            'hypothesis', hypothesis_code,
            'business_intent', business_intent,
            'beneficiary_system', beneficiary_system
        ) as event_details,
        CASE
            WHEN outcome = 'SUCCESS' THEN '#22c55e'  -- Green
            WHEN outcome = 'FAILURE' THEN '#ef4444'  -- Red
            WHEN status = 'ACTIVE' THEN '#3b82f6'    -- Blue
            WHEN status = 'PAUSED' THEN '#f59e0b'    -- Amber
            ELSE '#6b7280'  -- Gray
        END as color_code,
        created_at
    FROM fhq_calendar.canonical_test_events

    UNION ALL

    -- ========================================================================
    -- CEO ALERTS (ceo_calendar_alerts)
    -- ========================================================================
    SELECT
        alert_id as event_id,
        alert_title as event_name,
        'CEO_ACTION_REQUIRED' as event_category,
        calendar_date as event_date,
        NULL as end_date,
        status as event_status,
        'CEO' as owning_agent,
        jsonb_build_object(
            'alert_type', alert_type,
            'priority', priority,
            'options_count', jsonb_array_length(decision_options),
            'summary', alert_summary
        ) as event_details,
        CASE priority
            WHEN 'CRITICAL' THEN '#dc2626'  -- Red
            WHEN 'HIGH' THEN '#ea580c'      -- Orange
            WHEN 'NORMAL' THEN '#2563eb'    -- Blue
            ELSE '#6b7280'  -- Gray
        END as color_code,
        created_at
    FROM fhq_calendar.ceo_calendar_alerts
    WHERE status = 'PENDING'

    UNION ALL

    -- ========================================================================
    -- OBSERVATION WINDOWS
    -- ========================================================================
    SELECT
        window_id as event_id,
        window_name as event_name,
        'OBSERVATION_WINDOW' as event_category,
        start_date as event_date,
        end_date,
        status as event_status,
        'SYSTEM' as owning_agent,
        jsonb_build_object(
            'current_days', current_market_days,
            'required_days', required_market_days,
            'criteria_met', criteria_met,
            'volume_scaling', volume_scaling_active,
            'expected_improvement', expected_improvement
        ) as event_details,
        '#8b5cf6' as color_code,  -- Purple
        created_at
    FROM fhq_learning.observation_window

    UNION ALL

    -- ========================================================================
    -- DIVERGENCE POINTS (Section 11 - Shadow Veto)
    -- ========================================================================
    SELECT
        divergence_id as event_id,
        divergence_type || ': Human-AI Divergence' as event_name,
        'DIVERGENCE_POINT' as event_category,
        created_at::date as event_date,
        NULL as end_date,
        CASE WHEN resolved THEN 'RESOLVED' ELSE 'ACTIVE' END as event_status,
        'CEO' as owning_agent,
        jsonb_build_object(
            'system_said', system_recommendation,
            'human_chose', human_decision,
            'learning_arena', is_learning_arena
        ) as event_details,
        '#a855f7' as color_code,  -- Purple (divergence)
        created_at
    FROM fhq_calendar.divergence_audit_log

    UNION ALL

    -- ========================================================================
    -- ECONOMIC EVENTS (IoS-016) - NEW
    -- ========================================================================
    SELECT
        ce.event_id,
        etr.event_name,
        'ECONOMIC_EVENT' as event_category,
        ce.event_timestamp::date as event_date,
        NULL as end_date,
        CASE
            WHEN ce.actual_value IS NOT NULL THEN 'RELEASED'
            WHEN ce.event_timestamp < NOW() THEN 'PENDING'
            ELSE 'SCHEDULED'
        END as event_status,
        'IoS-016' as owning_agent,
        jsonb_build_object(
            'event_type', ce.event_type_code,
            'event_time', to_char(ce.event_timestamp, 'HH24:MI'),
            'consensus', ce.consensus_estimate,
            'previous', ce.previous_value,
            'actual', ce.actual_value,
            'surprise', ce.surprise_score,
            'impact_rank', etr.impact_rank,
            'category', etr.event_category
        ) as event_details,
        CASE etr.impact_rank
            WHEN 5 THEN '#dc2626'  -- Red (highest impact)
            WHEN 4 THEN '#ea580c'  -- Orange
            WHEN 3 THEN '#f59e0b'  -- Amber
            WHEN 2 THEN '#84cc16'  -- Lime
            ELSE '#6b7280'         -- Gray (lowest impact)
        END as color_code,
        ce.created_at
    FROM fhq_calendar.calendar_events ce
    JOIN fhq_calendar.event_type_registry etr
        ON ce.event_type_code = etr.event_type_code
    WHERE ce.event_timestamp >= CURRENT_DATE - INTERVAL '7 days'
      AND ce.event_timestamp <= CURRENT_DATE + INTERVAL '60 days'
      AND ce.is_canonical = TRUE
)
SELECT
    event_id,
    event_name,
    event_category,
    event_date,
    end_date,
    event_status,
    owning_agent,
    event_details,
    color_code,
    -- Calendar grid helpers
    EXTRACT(YEAR FROM event_date) as year,
    EXTRACT(MONTH FROM event_date) as month,
    EXTRACT(DAY FROM event_date) as day,
    TO_CHAR(event_date, 'Day') as day_name,
    created_at
FROM all_events
ORDER BY event_date ASC, created_at DESC;

COMMENT ON VIEW fhq_calendar.v_dashboard_calendar IS
'CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001 Section 2: Dashboard Calendar View.
Now includes economic events from IoS-016. CEO must understand system state in <30 seconds.
Color coding: Red=High Impact/Critical, Orange=Medium, Blue=Active, Purple=Observation/Divergence, Gray=Low';

-- ============================================================================
-- VERIFY ECONOMIC EVENTS INCLUDED
-- ============================================================================

DO $$
DECLARE
    v_economic_count INTEGER;
    v_total_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_economic_count
    FROM fhq_calendar.v_dashboard_calendar
    WHERE event_category = 'ECONOMIC_EVENT';

    SELECT COUNT(*) INTO v_total_count
    FROM fhq_calendar.v_dashboard_calendar;

    RAISE NOTICE 'Migration 341 VERIFIED: % economic events, % total events in view',
        v_economic_count, v_total_count;

    IF v_economic_count = 0 THEN
        RAISE WARNING 'No economic events found - check calendar_events table';
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION 341 COMPLETE
-- Economic events from IoS-016 now visible in dashboard calendar
-- ============================================================================
