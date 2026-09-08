-- Migration 284: UMA Surprise-Based Degradation Classification
-- CEO Directive 3.2: Classify every degradation as Model Drift or Information Shock
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Only Model Drift justifies structural change. Information Shock does not.

-- ============================================================================
-- SURPRISE-BASED DEGRADATION CLASSIFICATION
-- ============================================================================
-- CEO Order: "UMA is instructed to classify every degradation as:
--   - MODEL DRIFT (low surprise, poor outcome) → justifies structural change
--   - INFORMATION SHOCK (high surprise, poor outcome) → does NOT justify change
-- This distinction governs future risk scaling."
-- ============================================================================

-- Step 1: Create degradation classification table
CREATE TABLE IF NOT EXISTS fhq_governance.uma_degradation_classifications (
    classification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    score_id UUID REFERENCES fhq_governance.brier_score_ledger(score_id),
    asset_id TEXT NOT NULL,
    regime TEXT,

    -- Classification
    degradation_type TEXT NOT NULL CHECK (degradation_type IN ('MODEL_DRIFT', 'INFORMATION_SHOCK', 'UNCLASSIFIED')),

    -- Evidence
    surprise_score NUMERIC,
    brier_delta NUMERIC,
    hours_from_event NUMERIC,
    adjacent_event_type TEXT,

    -- Decision
    structural_change_warranted BOOLEAN NOT NULL DEFAULT FALSE,
    classification_confidence NUMERIC,
    classification_rationale TEXT,

    -- Metadata
    classified_at TIMESTAMPTZ DEFAULT NOW(),
    classified_by TEXT DEFAULT 'UMA'
);

CREATE INDEX IF NOT EXISTS idx_degradation_type
ON fhq_governance.uma_degradation_classifications(degradation_type, classified_at);

-- Step 2: Create classification function
CREATE OR REPLACE FUNCTION fhq_governance.classify_degradation(
    p_score_id UUID
)
RETURNS TABLE (
    degradation_type TEXT,
    structural_change_warranted BOOLEAN,
    classification_rationale TEXT
) AS $$
DECLARE
    v_record RECORD;
    v_surprise NUMERIC;
    v_brier_delta NUMERIC;
    v_baseline_brier NUMERIC := 0.5358;  -- G3 frozen baseline
    v_type TEXT;
    v_warranted BOOLEAN;
    v_rationale TEXT;
BEGIN
    -- Get the forecast record
    SELECT * INTO v_record
    FROM fhq_governance.brier_score_ledger
    WHERE score_id = p_score_id;

    IF v_record IS NULL THEN
        RETURN QUERY SELECT 'UNCLASSIFIED'::TEXT, FALSE, 'Score not found'::TEXT;
        RETURN;
    END IF;

    -- Calculate Brier delta from baseline
    v_brier_delta := v_record.squared_error - v_baseline_brier;

    -- Get surprise score from adjacent event if available
    SELECT ce.surprise_score INTO v_surprise
    FROM fhq_calendar.calendar_events ce
    WHERE ce.event_id = v_record.adjacent_event_id;

    -- Classification logic
    IF v_record.event_proximity_tag = 'EVENT_ADJACENT' AND v_surprise IS NOT NULL AND ABS(v_surprise) > 1.5 THEN
        -- High surprise + event adjacent = Information Shock
        v_type := 'INFORMATION_SHOCK';
        v_warranted := FALSE;
        v_rationale := 'High surprise event (' || ROUND(v_surprise, 2) || ' std). Poor outcome driven by external shock, not model failure.';
    ELSIF v_record.event_proximity_tag = 'EVENT_NEUTRAL' AND v_brier_delta > 0.10 THEN
        -- No event context + significant underperformance = Model Drift
        v_type := 'MODEL_DRIFT';
        v_warranted := TRUE;
        v_rationale := 'Clean window, significant Brier delta (' || ROUND(v_brier_delta, 4) || '). Model structural issue detected.';
    ELSIF v_brier_delta <= 0 THEN
        -- Outperforming baseline
        v_type := 'UNCLASSIFIED';
        v_warranted := FALSE;
        v_rationale := 'Performance at or above baseline. No degradation to classify.';
    ELSE
        -- Marginal underperformance in ambiguous context
        v_type := 'UNCLASSIFIED';
        v_warranted := FALSE;
        v_rationale := 'Marginal degradation (' || ROUND(v_brier_delta, 4) || '). Insufficient evidence for classification.';
    END IF;

    -- Record classification
    INSERT INTO fhq_governance.uma_degradation_classifications (
        score_id, asset_id, regime, degradation_type,
        surprise_score, brier_delta, hours_from_event, adjacent_event_type,
        structural_change_warranted, classification_confidence, classification_rationale
    ) VALUES (
        p_score_id, v_record.asset_id, v_record.regime, v_type,
        v_surprise, v_brier_delta, v_record.hours_from_event, v_record.adjacent_event_type,
        v_warranted,
        CASE
            WHEN v_type = 'UNCLASSIFIED' THEN 0.5
            ELSE 0.85
        END,
        v_rationale
    )
    ON CONFLICT DO NOTHING;

    RETURN QUERY SELECT v_type, v_warranted, v_rationale;
END;
$$ LANGUAGE plpgsql;

-- Step 3: Create batch classification function for UMA
CREATE OR REPLACE FUNCTION fhq_governance.uma_classify_recent_degradations(
    p_hours INTEGER DEFAULT 24
)
RETURNS TABLE (
    total_classified BIGINT,
    model_drift_count BIGINT,
    information_shock_count BIGINT,
    structural_changes_warranted BIGINT
) AS $$
DECLARE
    v_score RECORD;
    v_result RECORD;
    v_total INTEGER := 0;
    v_drift INTEGER := 0;
    v_shock INTEGER := 0;
    v_warranted INTEGER := 0;
BEGIN
    FOR v_score IN
        SELECT score_id
        FROM fhq_governance.brier_score_ledger
        WHERE created_at >= NOW() - (p_hours || ' hours')::INTERVAL
        AND squared_error > 0.5358  -- Above baseline = potential degradation
        AND score_id NOT IN (
            SELECT score_id FROM fhq_governance.uma_degradation_classifications
        )
        LIMIT 1000
    LOOP
        SELECT * INTO v_result FROM fhq_governance.classify_degradation(v_score.score_id);

        v_total := v_total + 1;

        IF v_result.degradation_type = 'MODEL_DRIFT' THEN
            v_drift := v_drift + 1;
        ELSIF v_result.degradation_type = 'INFORMATION_SHOCK' THEN
            v_shock := v_shock + 1;
        END IF;

        IF v_result.structural_change_warranted THEN
            v_warranted := v_warranted + 1;
        END IF;
    END LOOP;

    RETURN QUERY SELECT v_total::BIGINT, v_drift::BIGINT, v_shock::BIGINT, v_warranted::BIGINT;
END;
$$ LANGUAGE plpgsql;

-- Step 4: Create governance view for CEO
CREATE OR REPLACE VIEW fhq_governance.v_degradation_summary AS
SELECT
    degradation_type,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE structural_change_warranted) as changes_warranted,
    ROUND(AVG(brier_delta)::numeric, 4) as avg_brier_delta,
    ROUND(AVG(surprise_score)::numeric, 4) as avg_surprise,
    MIN(classified_at) as first_classified,
    MAX(classified_at) as last_classified
FROM fhq_governance.uma_degradation_classifications
WHERE classified_at >= NOW() - INTERVAL '7 days'
GROUP BY degradation_type
ORDER BY count DESC;

-- Step 5: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'UMA_SURPRISE_CLASSIFICATION_ENFORCED',
    'uma_degradation_classifications',
    'LEARNING_GOVERNANCE',
    'CEO',
    'DEPLOYED',
    'CEO Directive 3.2: UMA surprise-based classification enforced. Only MODEL_DRIFT justifies structural change. INFORMATION_SHOCK does not.',
    jsonb_build_object(
        'classification_types', ARRAY['MODEL_DRIFT', 'INFORMATION_SHOCK', 'UNCLASSIFIED'],
        'model_drift_action', 'STRUCTURAL_CHANGE_WARRANTED',
        'information_shock_action', 'NO_STRUCTURAL_CHANGE',
        'surprise_threshold', 1.5,
        'brier_delta_threshold', 0.10,
        'ceo_principle', 'Only Model Drift justifies structural change. This distinction governs future risk scaling.'
    )
);

-- Verification
DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'UMA SURPRISE CLASSIFICATION ENFORCED';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'MODEL_DRIFT: Low surprise + poor outcome → structural change warranted';
    RAISE NOTICE 'INFORMATION_SHOCK: High surprise + poor outcome → NO structural change';
    RAISE NOTICE 'Classification function: fhq_governance.classify_degradation()';
    RAISE NOTICE 'Batch function: fhq_governance.uma_classify_recent_degradations()';
    RAISE NOTICE '===========================================';
END $$;
