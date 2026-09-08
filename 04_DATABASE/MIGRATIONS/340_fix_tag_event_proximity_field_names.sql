-- Migration 340: Fix tag_event_proximity Field Name Mismatch
-- CEO Directive: Meta-Analysis Phase 1 - Learning Loop Recovery
-- Date: 2026-01-23
-- Author: STIG (EC-003)
-- Purpose: Fix field name mismatch between tag_event_proximity() return and auto_tag_event_proximity() trigger
--
-- Root Cause:
--   fhq_calendar.tag_event_proximity() returns: nearest_event_id, nearest_event_type, event_impact_rank, hours_to_event
--   fhq_governance.auto_tag_event_proximity() expects: event_id, event_type, impact_rank, hours_diff
--
-- Error since 2026-01-18:
--   "record 'v_tag' has no field 'event_id'"
--
-- Fix: Update trigger function to use correct field names from tag_event_proximity()

-- ============================================================================
-- FIX: Update auto_tag_event_proximity trigger function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.auto_tag_event_proximity()
RETURNS TRIGGER AS $$
DECLARE
    v_tag RECORD;
BEGIN
    -- Get proximity tag for new forecast
    SELECT * INTO v_tag
    FROM fhq_calendar.tag_event_proximity(NEW.forecast_timestamp, NEW.asset_id);

    IF v_tag IS NOT NULL AND v_tag.proximity_tag IS NOT NULL THEN
        -- Use correct field names from tag_event_proximity() return type:
        -- nearest_event_id, nearest_event_type, event_impact_rank, hours_to_event
        NEW.event_proximity_tag := v_tag.proximity_tag;
        NEW.adjacent_event_id := v_tag.nearest_event_id;      -- Fixed: was event_id
        NEW.adjacent_event_type := v_tag.nearest_event_type;  -- Fixed: was event_type
        NEW.adjacent_event_impact := v_tag.event_impact_rank; -- Fixed: was impact_rank
        NEW.hours_from_event := v_tag.hours_to_event;         -- Fixed: was hours_diff
        NEW.event_tagged_at := NOW();
    ELSE
        NEW.event_proximity_tag := 'EVENT_NEUTRAL';
        NEW.event_tagged_at := NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FIX: Update backfill_event_proximity_tags function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.backfill_event_proximity_tags()
RETURNS TABLE (
    tagged_count INTEGER,
    event_adjacent_count INTEGER,
    post_event_count INTEGER,
    event_neutral_count INTEGER
) AS $$
DECLARE
    v_tagged INTEGER := 0;
    v_adjacent INTEGER := 0;
    v_post INTEGER := 0;
    v_neutral INTEGER := 0;
    v_forecast RECORD;
    v_tag RECORD;
BEGIN
    FOR v_forecast IN
        SELECT score_id, asset_id, forecast_timestamp
        FROM fhq_governance.brier_score_ledger
        WHERE event_proximity_tag = 'UNTAGGED' OR event_proximity_tag IS NULL
        LIMIT 5000  -- Process in batches
    LOOP
        -- Get proximity tag for this forecast
        SELECT * INTO v_tag
        FROM fhq_calendar.tag_event_proximity(v_forecast.forecast_timestamp, v_forecast.asset_id);

        IF v_tag IS NOT NULL AND v_tag.proximity_tag IS NOT NULL THEN
            UPDATE fhq_governance.brier_score_ledger
            SET
                event_proximity_tag = v_tag.proximity_tag,
                adjacent_event_id = v_tag.nearest_event_id,      -- Fixed: was event_id
                adjacent_event_type = v_tag.nearest_event_type,  -- Fixed: was event_type
                adjacent_event_impact = v_tag.event_impact_rank, -- Fixed: was impact_rank
                hours_from_event = v_tag.hours_to_event,         -- Fixed: was hours_diff
                event_tagged_at = NOW()
            WHERE score_id = v_forecast.score_id;

            v_tagged := v_tagged + 1;

            IF v_tag.proximity_tag = 'EVENT_ADJACENT' THEN
                v_adjacent := v_adjacent + 1;
            ELSIF v_tag.proximity_tag = 'POST_EVENT' THEN
                v_post := v_post + 1;
            ELSE
                v_neutral := v_neutral + 1;
            END IF;
        END IF;
    END LOOP;

    RETURN QUERY SELECT v_tagged, v_adjacent, v_post, v_neutral;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_test RECORD;
BEGIN
    -- Test tag_event_proximity function
    SELECT * INTO v_test
    FROM fhq_calendar.tag_event_proximity(NOW(), NULL);

    IF v_test.proximity_tag IS NOT NULL THEN
        RAISE NOTICE 'Migration 340: tag_event_proximity() WORKING';
        RAISE NOTICE '  proximity_tag: %', v_test.proximity_tag;
        RAISE NOTICE '  nearest_event_id: %', v_test.nearest_event_id;
        RAISE NOTICE '  nearest_event_type: %', v_test.nearest_event_type;
    ELSE
        RAISE NOTICE 'Migration 340: tag_event_proximity() returned NULL (no events found)';
    END IF;
END $$;

-- ============================================================================
-- GOVERNANCE LOG
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MIGRATION_340_TAG_EVENT_PROXIMITY_FIX',
    'auto_tag_event_proximity',
    'FUNCTION_FIX',
    'STIG',
    'DEPLOYED',
    'Fixed field name mismatch between tag_event_proximity() return type and auto_tag_event_proximity() trigger. Error active since 2026-01-18.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-META-ANALYSIS',
        'phase', 'Phase 1: Learning Loop Recovery',
        'error_fixed', 'record "v_tag" has no field "event_id"',
        'field_mapping', jsonb_build_object(
            'nearest_event_id', 'adjacent_event_id',
            'nearest_event_type', 'adjacent_event_type',
            'event_impact_rank', 'adjacent_event_impact',
            'hours_to_event', 'hours_from_event'
        ),
        'functions_updated', ARRAY['fhq_governance.auto_tag_event_proximity', 'fhq_calendar.backfill_event_proximity_tags']
    )
);

RAISE NOTICE 'Migration 340: COMPLETE - tag_event_proximity field names fixed';
