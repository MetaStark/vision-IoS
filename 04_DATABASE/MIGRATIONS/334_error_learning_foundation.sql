-- Migration 334: Error Learning Foundation
-- CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase I
-- Author: STIG (EC-003)
-- Date: 2026-01-23

-- ============================================
-- PHASE I: Error-First Learning Foundation
-- ============================================

-- 1. Error Classification Taxonomy
CREATE TABLE IF NOT EXISTS fhq_learning.error_classification_taxonomy (
    error_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_code TEXT UNIQUE NOT NULL,           -- 'ERR-DIR-2026-0001'
    error_type TEXT NOT NULL,                  -- 'DIRECTION', 'MAGNITUDE', 'TIMING', 'REGIME'

    -- Source identification
    source_signal_id UUID,                     -- FK to unified_signal_log
    source_prediction_id UUID,                 -- FK to outcome_ledger
    source_hypothesis_id UUID,                 -- FK to hypothesis_ledger (if exists)

    -- Error characteristics
    predicted_direction TEXT,                  -- BULLISH/BEARISH/NEUTRAL
    actual_direction TEXT,                     -- BULLISH/BEARISH/NEUTRAL
    direction_error BOOLEAN GENERATED ALWAYS AS (predicted_direction IS DISTINCT FROM actual_direction) STORED,

    predicted_magnitude NUMERIC,
    actual_magnitude NUMERIC,
    magnitude_error_pct NUMERIC,

    predicted_timeframe_hours NUMERIC,
    actual_timeframe_hours NUMERIC,
    timing_error_hours NUMERIC,

    -- Context at time of error
    regime_at_prediction TEXT,                 -- RISK_ON/RISK_OFF/TRANSITION
    regime_at_outcome TEXT,
    regime_mismatch BOOLEAN GENERATED ALWAYS AS (regime_at_prediction IS DISTINCT FROM regime_at_outcome) STORED,

    -- Causal attribution (Phase IV integration)
    causal_attribution JSONB,                  -- Which factors contributed?
    confidence_at_prediction NUMERIC,

    -- Learning potential
    learning_priority TEXT DEFAULT 'MEDIUM',   -- HIGH/MEDIUM/LOW
    hypothesis_generated BOOLEAN DEFAULT FALSE,
    generated_hypothesis_id UUID,              -- FK to hypothesis_canon when generated

    -- Timestamps
    error_detected_at TIMESTAMPTZ DEFAULT NOW(),
    prediction_timestamp TIMESTAMPTZ,
    outcome_timestamp TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'SYSTEM',

    -- Constraints
    CONSTRAINT chk_error_type CHECK (error_type IN ('DIRECTION', 'MAGNITUDE', 'TIMING', 'REGIME', 'COMPOSITE')),
    CONSTRAINT chk_learning_priority CHECK (learning_priority IN ('HIGH', 'MEDIUM', 'LOW')),
    CONSTRAINT chk_predicted_direction CHECK (predicted_direction IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    CONSTRAINT chk_actual_direction CHECK (actual_direction IN ('BULLISH', 'BEARISH', 'NEUTRAL'))
);

-- Indexes for efficient error detection and learning
CREATE INDEX IF NOT EXISTS idx_error_learning_priority
    ON fhq_learning.error_classification_taxonomy(learning_priority, hypothesis_generated);
CREATE INDEX IF NOT EXISTS idx_error_type
    ON fhq_learning.error_classification_taxonomy(error_type);
CREATE INDEX IF NOT EXISTS idx_error_detected_at
    ON fhq_learning.error_classification_taxonomy(error_detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_direction_mismatch
    ON fhq_learning.error_classification_taxonomy(direction_error) WHERE direction_error = TRUE;
CREATE INDEX IF NOT EXISTS idx_error_regime_mismatch
    ON fhq_learning.error_classification_taxonomy(regime_mismatch) WHERE regime_mismatch = TRUE;

-- 2. Error Code Sequence
CREATE SEQUENCE IF NOT EXISTS fhq_learning.error_code_seq START WITH 1;

-- 3. Function to generate error codes
CREATE OR REPLACE FUNCTION fhq_learning.generate_error_code()
RETURNS TEXT AS $$
DECLARE
    v_year TEXT;
    v_seq INT;
BEGIN
    v_year := TO_CHAR(NOW(), 'YYYY');
    v_seq := NEXTVAL('fhq_learning.error_code_seq');
    RETURN 'ERR-DIR-' || v_year || '-' || LPAD(v_seq::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;

-- 4. Function to detect and classify errors from outcome_ledger
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
    v_prediction RECORD;
    v_new_error_id UUID;
    v_error_code TEXT;
    v_error_type TEXT;
    v_learning_priority TEXT;
    v_direction_error BOOLEAN;
    v_magnitude_error_pct NUMERIC;
BEGIN
    -- Find resolved predictions with errors
    FOR v_prediction IN
        SELECT
            ol.outcome_id,
            ol.symbol,
            ol.prediction_timestamp,
            ol.outcome_timestamp,
            ol.predicted_direction,
            ol.actual_direction,
            ol.predicted_magnitude,
            ol.actual_magnitude,
            ol.confidence_at_prediction,
            ol.regime_at_prediction,
            ol.regime_at_outcome
        FROM fhq_research.outcome_ledger ol
        WHERE ol.outcome_timestamp >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
          AND ol.outcome_timestamp IS NOT NULL
          AND (
              ol.predicted_direction IS DISTINCT FROM ol.actual_direction
              OR ABS(COALESCE(ol.predicted_magnitude, 0) - COALESCE(ol.actual_magnitude, 0)) > 0.02
              OR ol.regime_at_prediction IS DISTINCT FROM ol.regime_at_outcome
          )
          AND NOT EXISTS (
              SELECT 1 FROM fhq_learning.error_classification_taxonomy ect
              WHERE ect.source_prediction_id = ol.outcome_id
          )
    LOOP
        -- Classify error type
        v_direction_error := v_prediction.predicted_direction IS DISTINCT FROM v_prediction.actual_direction;

        IF v_prediction.predicted_magnitude IS NOT NULL AND v_prediction.actual_magnitude IS NOT NULL THEN
            v_magnitude_error_pct := ABS(v_prediction.predicted_magnitude - v_prediction.actual_magnitude)
                                     / GREATEST(0.01, ABS(v_prediction.predicted_magnitude)) * 100;
        ELSE
            v_magnitude_error_pct := NULL;
        END IF;

        -- Determine primary error type
        IF v_direction_error THEN
            v_error_type := 'DIRECTION';
        ELSIF v_prediction.regime_at_prediction IS DISTINCT FROM v_prediction.regime_at_outcome THEN
            v_error_type := 'REGIME';
        ELSIF v_magnitude_error_pct > 50 THEN
            v_error_type := 'MAGNITUDE';
        ELSE
            v_error_type := 'TIMING';
        END IF;

        -- Determine learning priority
        IF v_direction_error AND COALESCE(v_prediction.confidence_at_prediction, 0) > 0.6 THEN
            v_learning_priority := 'HIGH';
        ELSIF v_prediction.regime_at_prediction IS DISTINCT FROM v_prediction.regime_at_outcome THEN
            v_learning_priority := 'HIGH';
        ELSIF v_magnitude_error_pct > 50 THEN
            v_learning_priority := 'MEDIUM';
        ELSE
            v_learning_priority := 'LOW';
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
            predicted_magnitude,
            actual_magnitude,
            magnitude_error_pct,
            regime_at_prediction,
            regime_at_outcome,
            confidence_at_prediction,
            learning_priority,
            prediction_timestamp,
            outcome_timestamp
        ) VALUES (
            v_new_error_id,
            v_error_code,
            v_error_type,
            v_prediction.outcome_id,
            v_prediction.predicted_direction,
            v_prediction.actual_direction,
            v_prediction.predicted_magnitude,
            v_prediction.actual_magnitude,
            v_magnitude_error_pct,
            v_prediction.regime_at_prediction,
            v_prediction.regime_at_outcome,
            v_prediction.confidence_at_prediction,
            v_learning_priority,
            v_prediction.prediction_timestamp,
            v_prediction.outcome_timestamp
        );

        -- Return the new error
        new_error_id := v_new_error_id;
        error_code := v_error_code;
        error_type := v_error_type;
        source_prediction_id := v_prediction.outcome_id;
        predicted_direction := v_prediction.predicted_direction;
        actual_direction := v_prediction.actual_direction;
        learning_priority := v_learning_priority;

        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 5. View for high-priority learning errors
CREATE OR REPLACE VIEW fhq_learning.v_high_priority_errors AS
SELECT
    ect.error_id,
    ect.error_code,
    ect.error_type,
    ect.predicted_direction,
    ect.actual_direction,
    ect.direction_error,
    ect.regime_at_prediction,
    ect.regime_at_outcome,
    ect.regime_mismatch,
    ect.confidence_at_prediction,
    ect.learning_priority,
    ect.hypothesis_generated,
    ect.error_detected_at,
    ect.prediction_timestamp,
    ect.outcome_timestamp
FROM fhq_learning.error_classification_taxonomy ect
WHERE ect.learning_priority = 'HIGH'
  AND ect.hypothesis_generated = FALSE
ORDER BY ect.error_detected_at DESC;

-- 6. Summary statistics view
CREATE OR REPLACE VIEW fhq_learning.v_error_learning_summary AS
SELECT
    DATE_TRUNC('day', error_detected_at) AS error_date,
    COUNT(*) AS total_errors,
    COUNT(CASE WHEN error_type = 'DIRECTION' THEN 1 END) AS direction_errors,
    COUNT(CASE WHEN error_type = 'MAGNITUDE' THEN 1 END) AS magnitude_errors,
    COUNT(CASE WHEN error_type = 'TIMING' THEN 1 END) AS timing_errors,
    COUNT(CASE WHEN error_type = 'REGIME' THEN 1 END) AS regime_errors,
    COUNT(CASE WHEN learning_priority = 'HIGH' THEN 1 END) AS high_priority,
    COUNT(CASE WHEN learning_priority = 'MEDIUM' THEN 1 END) AS medium_priority,
    COUNT(CASE WHEN learning_priority = 'LOW' THEN 1 END) AS low_priority,
    COUNT(CASE WHEN hypothesis_generated THEN 1 END) AS hypotheses_generated,
    ROUND(
        COUNT(CASE WHEN hypothesis_generated THEN 1 END)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2
    ) AS error_to_hypothesis_rate
FROM fhq_learning.error_classification_taxonomy
GROUP BY DATE_TRUNC('day', error_detected_at)
ORDER BY error_date DESC;

-- 7. Grant permissions
GRANT SELECT, INSERT, UPDATE ON fhq_learning.error_classification_taxonomy TO PUBLIC;
GRANT USAGE ON SEQUENCE fhq_learning.error_code_seq TO PUBLIC;
GRANT SELECT ON fhq_learning.v_high_priority_errors TO PUBLIC;
GRANT SELECT ON fhq_learning.v_error_learning_summary TO PUBLIC;

-- 8. Record migration
INSERT INTO fhq_meta.migration_log (migration_id, migration_name, executed_by)
VALUES (334, 'error_learning_foundation', 'STIG')
ON CONFLICT (migration_id) DO NOTHING;

COMMENT ON TABLE fhq_learning.error_classification_taxonomy IS 'CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase I: Error-First Learning Foundation. Every prediction error becomes a learning opportunity.';
