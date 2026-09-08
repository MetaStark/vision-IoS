-- Migration 334b: Fix error detection function for actual schema
-- CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase I (cont.)

-- Drop existing function
DROP FUNCTION IF EXISTS fhq_learning.detect_prediction_errors(INT);

-- Recreate with correct schema references
CREATE OR REPLACE FUNCTION fhq_learning.detect_prediction_errors(
    p_lookback_hours INT DEFAULT 24
) RETURNS TABLE (
    new_error_id UUID,
    error_code TEXT,
    error_type TEXT,
    source_prediction_id UUID,
    predicted_direction TEXT,
    actual_direction TEXT,
    learning_priority TEXT
) AS $$
DECLARE
    v_pair RECORD;
    v_new_error_id UUID;
    v_error_code TEXT;
    v_error_type TEXT;
    v_learning_priority TEXT;
    v_predicted_dir TEXT;
    v_actual_dir TEXT;
BEGIN
    -- Find forecast-outcome pairs with errors (hit_rate_contribution = FALSE)
    FOR v_pair IN
        SELECT
            fop.pair_id,
            fop.forecast_id,
            fop.outcome_id,
            fop.hit_rate_contribution,
            fop.brier_score,
            fop.reconciled_at,
            fl.forecast_value,
            fl.forecast_confidence,
            fl.forecast_domain,
            fl.forecast_made_at,
            ol.outcome_value,
            ol.outcome_timestamp
        FROM fhq_research.forecast_outcome_pairs fop
        JOIN fhq_research.forecast_ledger fl ON fop.forecast_id = fl.forecast_id
        JOIN fhq_research.outcome_ledger ol ON fop.outcome_id = ol.outcome_id
        WHERE fop.reconciled_at >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
          AND fop.hit_rate_contribution = FALSE
          AND NOT EXISTS (
              SELECT 1 FROM fhq_learning.error_classification_taxonomy ect
              WHERE ect.source_prediction_id = fop.forecast_id
          )
        ORDER BY fop.brier_score DESC
        LIMIT 100  -- Process top 100 worst errors per run
    LOOP
        -- Determine directions from values
        v_predicted_dir := CASE
            WHEN v_pair.forecast_value ILIKE '%up%' OR v_pair.forecast_value ILIKE '%bull%' OR v_pair.forecast_value ILIKE '%higher%' THEN 'BULLISH'
            WHEN v_pair.forecast_value ILIKE '%down%' OR v_pair.forecast_value ILIKE '%bear%' OR v_pair.forecast_value ILIKE '%lower%' THEN 'BEARISH'
            ELSE 'NEUTRAL'
        END;

        v_actual_dir := CASE
            WHEN v_pair.outcome_value ILIKE '%up%' OR v_pair.outcome_value ILIKE '%bull%' OR v_pair.outcome_value ILIKE '%higher%' THEN 'BULLISH'
            WHEN v_pair.outcome_value ILIKE '%down%' OR v_pair.outcome_value ILIKE '%bear%' OR v_pair.outcome_value ILIKE '%lower%' THEN 'BEARISH'
            ELSE 'NEUTRAL'
        END;

        -- Determine error type based on brier score and direction
        IF v_predicted_dir IS DISTINCT FROM v_actual_dir THEN
            v_error_type := 'DIRECTION';
        ELSIF v_pair.brier_score > 0.5 THEN
            v_error_type := 'MAGNITUDE';
        ELSE
            v_error_type := 'TIMING';
        END IF;

        -- Determine learning priority based on Brier score (severity)
        IF v_pair.brier_score > 0.7 THEN
            v_learning_priority := 'HIGH';
        ELSIF v_pair.brier_score > 0.4 THEN
            v_learning_priority := 'MEDIUM';
        ELSE
            v_learning_priority := 'LOW';
        END IF;

        -- Boost priority for high confidence errors (confident but wrong = important to learn)
        IF COALESCE(v_pair.forecast_confidence, 0) > 0.6 AND v_error_type = 'DIRECTION' THEN
            v_learning_priority := 'HIGH';
        END IF;

        -- Generate error code
        v_error_code := fhq_learning.generate_error_code();
        v_new_error_id := gen_random_uuid();

        -- Insert error record
        INSERT INTO fhq_learning.error_classification_taxonomy (
            error_id,
            error_code,
            error_type,
            source_prediction_id,
            predicted_direction,
            actual_direction,
            confidence_at_prediction,
            learning_priority,
            prediction_timestamp,
            outcome_timestamp
        ) VALUES (
            v_new_error_id,
            v_error_code,
            v_error_type,
            v_pair.forecast_id,
            v_predicted_dir,
            v_actual_dir,
            v_pair.forecast_confidence,
            v_learning_priority,
            v_pair.forecast_made_at,
            v_pair.outcome_timestamp
        );

        -- Return the new error
        new_error_id := v_new_error_id;
        error_code := v_error_code;
        error_type := v_error_type;
        source_prediction_id := v_pair.forecast_id;
        predicted_direction := v_predicted_dir;
        actual_direction := v_actual_dir;
        learning_priority := v_learning_priority;

        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Also add helper function for linking errors to hypotheses
CREATE OR REPLACE FUNCTION fhq_learning.link_error_to_hypothesis(
    p_error_id UUID,
    p_hypothesis_id UUID
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE fhq_learning.error_classification_taxonomy
    SET hypothesis_generated = TRUE,
        generated_hypothesis_id = p_hypothesis_id
    WHERE error_id = p_error_id
      AND hypothesis_generated = FALSE;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_learning.detect_prediction_errors IS 'Detects prediction errors from forecast_outcome_pairs for learning. Returns top 100 worst errors (by Brier score) not yet processed.';
