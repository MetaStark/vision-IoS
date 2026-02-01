-- Migration 283: IoS-016 Shadow to Active Promotion
-- CEO Directive 3.1: EVENT_ADJACENT tagging is now authoritative
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Promote IoS-016 from shadow mode to active learning context

-- ============================================================================
-- IoS-016 PROMOTION: SHADOW → ACTIVE
-- ============================================================================
-- CEO Order: "EVENT_ADJACENT tagging is now authoritative.
--            Event-adjacent forecasts are excluded from punitive learning.
--            Learning must occur in CLEAN WINDOWS ONLY."
-- ============================================================================

-- Step 1: Enable the automatic event tagging trigger
ALTER TABLE fhq_governance.brier_score_ledger
ENABLE TRIGGER trg_auto_tag_event_proximity;

-- Step 2: Create learning exclusion view (EVENT_ADJACENT excluded from punitive learning)
CREATE OR REPLACE VIEW fhq_governance.v_clean_learning_window AS
SELECT
    score_id,
    belief_id,
    forecast_type,
    asset_id,
    regime,
    forecast_probability,
    actual_outcome,
    squared_error,
    forecast_timestamp,
    event_proximity_tag,
    adjacent_event_type,
    hours_from_event
FROM fhq_governance.brier_score_ledger
WHERE event_proximity_tag = 'EVENT_NEUTRAL'  -- Clean windows only
AND eligible_for_calibration = true
AND created_at >= NOW() - INTERVAL '30 days';

-- Step 3: Create punitive learning exclusion table for audit
CREATE TABLE IF NOT EXISTS fhq_governance.learning_exclusions (
    exclusion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    score_id UUID NOT NULL,
    exclusion_reason TEXT NOT NULL,
    event_proximity_tag TEXT,
    adjacent_event_id UUID,
    adjacent_event_type TEXT,
    hours_from_event NUMERIC,
    excluded_at TIMESTAMPTZ DEFAULT NOW(),
    excluded_by TEXT DEFAULT 'IoS-016'
);

CREATE INDEX IF NOT EXISTS idx_learning_exclusions_reason
ON fhq_governance.learning_exclusions(exclusion_reason, excluded_at);

-- Step 4: Create function to classify learning eligibility
CREATE OR REPLACE FUNCTION fhq_governance.classify_learning_eligibility(
    p_score_id UUID
)
RETURNS TABLE (
    is_eligible BOOLEAN,
    exclusion_reason TEXT,
    learning_context TEXT
) AS $$
DECLARE
    v_record RECORD;
BEGIN
    SELECT * INTO v_record
    FROM fhq_governance.brier_score_ledger
    WHERE score_id = p_score_id;

    IF v_record IS NULL THEN
        RETURN QUERY SELECT FALSE, 'SCORE_NOT_FOUND'::TEXT, 'N/A'::TEXT;
        RETURN;
    END IF;

    -- EVENT_ADJACENT: Exclude from punitive learning
    IF v_record.event_proximity_tag = 'EVENT_ADJACENT' THEN
        RETURN QUERY SELECT
            FALSE,
            'EVENT_ADJACENT_EXCLUSION'::TEXT,
            'Forecast made within pre-event window. Noise expected.'::TEXT;
        RETURN;
    END IF;

    -- POST_EVENT: Reduced learning weight
    IF v_record.event_proximity_tag = 'POST_EVENT' THEN
        RETURN QUERY SELECT
            TRUE,
            'REDUCED_WEIGHT'::TEXT,
            'Forecast in post-event transition. Learning at 50% weight.'::TEXT;
        RETURN;
    END IF;

    -- EVENT_NEUTRAL: Full learning
    RETURN QUERY SELECT
        TRUE,
        'FULL_LEARNING'::TEXT,
        'Clean window. Full learning weight applied.'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Step 5: Create LVI_adjusted computation function (CEO-visible metric)
CREATE OR REPLACE FUNCTION fhq_governance.compute_lvi_adjusted(
    p_start_date DATE,
    p_end_date DATE
)
RETURNS TABLE (
    learning_window TEXT,
    total_forecasts BIGINT,
    clean_forecasts BIGINT,
    event_adjacent_excluded BIGINT,
    raw_lvi NUMERIC,
    adjusted_lvi NUMERIC,
    false_error_removed_pct NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH stats AS (
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE event_proximity_tag = 'EVENT_NEUTRAL') as clean,
            COUNT(*) FILTER (WHERE event_proximity_tag = 'EVENT_ADJACENT') as adjacent,
            AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END) as overall_hit,
            AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END)
                FILTER (WHERE event_proximity_tag = 'EVENT_NEUTRAL') as clean_hit
        FROM fhq_governance.brier_score_ledger
        WHERE created_at::date BETWEEN p_start_date AND p_end_date
        AND eligible_for_calibration = true
    )
    SELECT
        p_start_date || ' to ' || p_end_date,
        total,
        clean,
        adjacent,
        ROUND(overall_hit::numeric, 4),
        ROUND(COALESCE(clean_hit, 0)::numeric, 4),
        ROUND(((adjacent::numeric / NULLIF(total, 0)) * 100)::numeric, 2)
    FROM stats;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Backfill existing untagged forecasts
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    -- Tag any remaining untagged forecasts as EVENT_NEUTRAL (conservative default)
    UPDATE fhq_governance.brier_score_ledger
    SET event_proximity_tag = 'EVENT_NEUTRAL',
        event_tagged_at = NOW()
    WHERE event_proximity_tag IS NULL OR event_proximity_tag = 'UNTAGGED';

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Backfilled % forecasts with EVENT_NEUTRAL tag', v_count;
END $$;

-- Step 7: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'IOS016_PROMOTED_TO_ACTIVE',
    'brier_score_ledger',
    'LEARNING_CONTEXT',
    'CEO',
    'PROMOTED',
    'CEO Directive 3.1: IoS-016 promoted from shadow to active. EVENT_ADJACENT tagging now authoritative. Event-adjacent forecasts excluded from punitive learning.',
    jsonb_build_object(
        'trigger_status', 'ENABLED',
        'learning_rule', 'CLEAN_WINDOWS_ONLY',
        'event_adjacent_treatment', 'EXCLUDED_FROM_PUNITIVE_LEARNING',
        'post_event_treatment', 'REDUCED_WEIGHT_50PCT',
        'event_neutral_treatment', 'FULL_LEARNING',
        'expected_false_error_reduction', '15-25%',
        'ceo_principle', 'This alone is expected to remove 15-25% of false error attribution.'
    )
);

-- Verification
DO $$
DECLARE
    trigger_enabled BOOLEAN;
BEGIN
    SELECT tgenabled = 'O' INTO trigger_enabled
    FROM pg_trigger
    WHERE tgname = 'trg_auto_tag_event_proximity';

    IF trigger_enabled THEN
        RAISE NOTICE '===========================================';
        RAISE NOTICE 'IoS-016 PROMOTED TO ACTIVE';
        RAISE NOTICE '===========================================';
        RAISE NOTICE 'Event tagging trigger: ENABLED';
        RAISE NOTICE 'Learning context: CLEAN_WINDOWS_ONLY';
        RAISE NOTICE 'Expected improvement: 15-25%% false error removed';
        RAISE NOTICE '===========================================';
    ELSE
        RAISE WARNING 'IoS-016 promotion FAILED - trigger not enabled';
    END IF;
END $$;
