-- Migration 278: IoS-016 EVENT_ADJACENT Tagging Activation
-- CEO Post-G3 Directive 2.1: Implement event proximity tagging
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Add event proximity tagging to brier_score_ledger for Brier stratification

-- ============================================================================
-- IoS-016 EVENT_ADJACENT TAGGING
-- ============================================================================
-- This enables stratified Brier analysis by separating:
-- - EVENT_ADJACENT: Forecasts within pre-event window (noise expected)
-- - POST_EVENT: Forecasts within post-event window (transition period)
-- - EVENT_NEUTRAL: Forecasts outside event windows (clean signal)

-- Step 1: Add event proximity columns to brier_score_ledger
ALTER TABLE fhq_governance.brier_score_ledger
ADD COLUMN IF NOT EXISTS event_proximity_tag TEXT DEFAULT 'UNTAGGED',
ADD COLUMN IF NOT EXISTS adjacent_event_id UUID,
ADD COLUMN IF NOT EXISTS adjacent_event_type TEXT,
ADD COLUMN IF NOT EXISTS adjacent_event_impact INTEGER,
ADD COLUMN IF NOT EXISTS hours_from_event NUMERIC,
ADD COLUMN IF NOT EXISTS event_tagged_at TIMESTAMPTZ;

-- Step 2: Create index for stratified queries
CREATE INDEX IF NOT EXISTS idx_brier_event_proximity
ON fhq_governance.brier_score_ledger(event_proximity_tag, created_at);

CREATE INDEX IF NOT EXISTS idx_brier_regime_proximity
ON fhq_governance.brier_score_ledger(regime, event_proximity_tag);

-- Step 3: Create function to tag existing forecasts
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

        IF v_tag IS NOT NULL THEN
            UPDATE fhq_governance.brier_score_ledger
            SET
                event_proximity_tag = v_tag.proximity_tag,
                adjacent_event_id = v_tag.event_id,
                adjacent_event_type = v_tag.event_type,
                adjacent_event_impact = v_tag.impact_rank,
                hours_from_event = v_tag.hours_diff,
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

-- Step 4: Create trigger for automatic tagging of new forecasts
CREATE OR REPLACE FUNCTION fhq_governance.auto_tag_event_proximity()
RETURNS TRIGGER AS $$
DECLARE
    v_tag RECORD;
BEGIN
    -- Get proximity tag for new forecast
    SELECT * INTO v_tag
    FROM fhq_calendar.tag_event_proximity(NEW.forecast_timestamp, NEW.asset_id);

    IF v_tag IS NOT NULL THEN
        NEW.event_proximity_tag := v_tag.proximity_tag;
        NEW.adjacent_event_id := v_tag.event_id;
        NEW.adjacent_event_type := v_tag.event_type;
        NEW.adjacent_event_impact := v_tag.impact_rank;
        NEW.hours_from_event := v_tag.hours_diff;
        NEW.event_tagged_at := NOW();
    ELSE
        NEW.event_proximity_tag := 'EVENT_NEUTRAL';
        NEW.event_tagged_at := NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (disabled by default for shadow mode)
DROP TRIGGER IF EXISTS trg_auto_tag_event_proximity ON fhq_governance.brier_score_ledger;
CREATE TRIGGER trg_auto_tag_event_proximity
    BEFORE INSERT ON fhq_governance.brier_score_ledger
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.auto_tag_event_proximity();

-- Disable trigger initially (shadow mode)
ALTER TABLE fhq_governance.brier_score_ledger DISABLE TRIGGER trg_auto_tag_event_proximity;

-- Step 5: Create view for stratified Brier analysis
CREATE OR REPLACE VIEW fhq_governance.v_brier_by_event_proximity AS
SELECT
    event_proximity_tag,
    regime,
    COUNT(*) as forecast_count,
    ROUND(AVG(squared_error)::numeric, 4) as avg_brier,
    ROUND(AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END)::numeric, 4) as hit_rate,
    ROUND(AVG(forecast_probability)::numeric, 4) as avg_confidence,
    ROUND((AVG(forecast_probability) - AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END))::numeric, 4) as overconfidence_delta
FROM fhq_governance.brier_score_ledger
WHERE created_at >= NOW() - INTERVAL '30 days'
AND eligible_for_calibration = true
GROUP BY event_proximity_tag, regime
ORDER BY event_proximity_tag, regime;

-- Step 6: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'IOS016_EVENT_TAGGING_ACTIVATED',
    'brier_score_ledger',
    'SCHEMA_EXTENSION',
    'STIG',
    'DEPLOYED_SHADOW_MODE',
    'IoS-016 EVENT_ADJACENT tagging infrastructure deployed. Trigger disabled for shadow mode verification.',
    jsonb_build_object(
        'columns_added', ARRAY['event_proximity_tag', 'adjacent_event_id', 'adjacent_event_type', 'adjacent_event_impact', 'hours_from_event', 'event_tagged_at'],
        'trigger_status', 'DISABLED',
        'backfill_function', 'fhq_calendar.backfill_event_proximity_tags()',
        'view_created', 'fhq_governance.v_brier_by_event_proximity',
        'directive', 'CEO Post-G3 Directive 2.1'
    )
);

-- Verification
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_schema = 'fhq_governance'
    AND table_name = 'brier_score_ledger'
    AND column_name = 'event_proximity_tag';

    IF col_count = 1 THEN
        RAISE NOTICE 'IoS-016 EVENT_ADJACENT tagging: DEPLOYED (shadow mode)';
    ELSE
        RAISE WARNING 'IoS-016 EVENT_ADJACENT tagging: FAILED';
    END IF;
END $$;
