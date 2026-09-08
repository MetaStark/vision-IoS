-- Migration 279: Surprise-Based Diagnostics Activation
-- CEO Post-G3 Directive 2.2: Activate surprise-based diagnostics
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Activate surprise score computation and ghost event detection

-- ============================================================================
-- SURPRISE-BASED DIAGNOSTICS
-- ============================================================================
-- Surprise score = (actual - consensus) / historical_std
-- Ghost events = unexplained volatility without matching calendar events

-- Step 1: Create function to compute normalized surprise scores
CREATE OR REPLACE FUNCTION fhq_calendar.compute_surprise_score(
    p_actual NUMERIC,
    p_consensus NUMERIC,
    p_event_type_code TEXT
)
RETURNS NUMERIC AS $$
DECLARE
    v_historical_std NUMERIC;
    v_normalization_unit TEXT;
BEGIN
    -- Get historical std for this event type
    SELECT historical_std, surprise_normalization_unit
    INTO v_historical_std, v_normalization_unit
    FROM fhq_calendar.event_type_registry
    WHERE event_type_code = p_event_type_code;

    IF v_historical_std IS NULL OR v_historical_std = 0 THEN
        -- Default to percentage difference if no historical data
        IF p_consensus = 0 THEN
            RETURN NULL;
        END IF;
        RETURN (p_actual - p_consensus) / ABS(p_consensus);
    END IF;

    -- Normalized surprise score
    RETURN (p_actual - p_consensus) / v_historical_std;
END;
$$ LANGUAGE plpgsql;

-- Step 2: Add historical_std column to event_type_registry if not exists
ALTER TABLE fhq_calendar.event_type_registry
ADD COLUMN IF NOT EXISTS historical_std NUMERIC DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS surprise_normalization_unit TEXT DEFAULT 'PCT';

-- Step 3: Update event types with approximate historical std values
UPDATE fhq_calendar.event_type_registry SET
    historical_std = 0.25,  -- 25bps typical surprise
    surprise_normalization_unit = 'BPS'
WHERE event_type_code IN ('US_FOMC', 'ECB_RATE', 'BOJ_RATE', 'BOE_RATE');

UPDATE fhq_calendar.event_type_registry SET
    historical_std = 0.20,  -- 0.2% typical CPI surprise
    surprise_normalization_unit = 'PCT'
WHERE event_type_code IN ('US_CPI', 'EU_CPI', 'UK_CPI');

UPDATE fhq_calendar.event_type_registry SET
    historical_std = 50000,  -- 50K jobs typical NFP surprise
    surprise_normalization_unit = 'ABSOLUTE'
WHERE event_type_code IN ('US_NFP', 'US_CLAIMS');

UPDATE fhq_calendar.event_type_registry SET
    historical_std = 0.10,  -- 10% typical earnings surprise
    surprise_normalization_unit = 'PCT'
WHERE event_type_code IN ('EARNINGS_Q', 'EARNINGS_A');

-- Step 4: Create function to detect ghost events (unexplained volatility)
CREATE OR REPLACE FUNCTION fhq_calendar.detect_ghost_events(
    p_lookback_hours INTEGER DEFAULT 24
)
RETURNS TABLE (
    asset_id TEXT,
    detection_timestamp TIMESTAMPTZ,
    volatility_magnitude NUMERIC,
    expected_volatility NUMERIC,
    volatility_ratio NUMERIC,
    nearest_event_id UUID,
    nearest_event_type TEXT,
    is_ghost BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH recent_volatility AS (
        -- Get recent high volatility moves (simplified detection)
        SELECT
            b.asset_id,
            b.forecast_timestamp as detection_ts,
            ABS(b.forecast_probability - 0.5) * 2 as vol_magnitude,  -- Proxy for volatility
            0.3 as expected_vol  -- Baseline expected volatility
        FROM fhq_governance.brier_score_ledger b
        WHERE b.created_at >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
        AND b.squared_error > 0.5  -- High error = high surprise
    ),
    with_events AS (
        SELECT
            rv.*,
            ce.event_id,
            ce.event_type_code,
            ABS(EXTRACT(EPOCH FROM (ce.event_timestamp - rv.detection_ts)) / 3600.0) as hours_from_event
        FROM recent_volatility rv
        LEFT JOIN fhq_calendar.calendar_events ce ON
            ce.event_timestamp BETWEEN rv.detection_ts - INTERVAL '6 hours'
            AND rv.detection_ts + INTERVAL '6 hours'
            AND ce.is_canonical = TRUE
    )
    SELECT
        we.asset_id,
        we.detection_ts,
        we.vol_magnitude,
        we.expected_vol,
        we.vol_magnitude / NULLIF(we.expected_vol, 0) as vol_ratio,
        we.event_id,
        we.event_type_code,
        (we.event_id IS NULL) as is_ghost
    FROM with_events we
    WHERE we.vol_magnitude > we.expected_vol * 1.5;  -- Threshold: 50% above expected
END;
$$ LANGUAGE plpgsql;

-- Step 5: Create view for surprise-based Brier analysis
CREATE OR REPLACE VIEW fhq_calendar.v_surprise_impact_analysis AS
SELECT
    ce.event_type_code,
    etr.impact_rank,
    COUNT(*) as event_count,
    ROUND(AVG(ce.surprise_score)::numeric, 4) as avg_surprise,
    ROUND(STDDEV(ce.surprise_score)::numeric, 4) as surprise_stddev,
    ROUND(MAX(ABS(ce.surprise_score))::numeric, 4) as max_abs_surprise
FROM fhq_calendar.calendar_events ce
JOIN fhq_calendar.event_type_registry etr ON ce.event_type_code = etr.event_type_code
WHERE ce.surprise_score IS NOT NULL
GROUP BY ce.event_type_code, etr.impact_rank
ORDER BY etr.impact_rank DESC, avg_surprise DESC;

-- Step 6: Create diagnostic summary function
CREATE OR REPLACE FUNCTION fhq_calendar.get_surprise_diagnostics(
    p_since DATE DEFAULT CURRENT_DATE - 7
)
RETURNS TABLE (
    metric TEXT,
    value NUMERIC,
    interpretation TEXT
) AS $$
BEGIN
    -- Events with surprise scores
    RETURN QUERY
    SELECT
        'events_with_surprise'::TEXT,
        COUNT(*)::NUMERIC,
        'Total events with computed surprise scores'::TEXT
    FROM fhq_calendar.calendar_events
    WHERE surprise_score IS NOT NULL
    AND created_at >= p_since;

    -- Average absolute surprise
    RETURN QUERY
    SELECT
        'avg_abs_surprise'::TEXT,
        ROUND(AVG(ABS(surprise_score))::NUMERIC, 4),
        'Mean absolute surprise (|actual - consensus| / std)'::TEXT
    FROM fhq_calendar.calendar_events
    WHERE surprise_score IS NOT NULL
    AND created_at >= p_since;

    -- Ghost events detected
    RETURN QUERY
    SELECT
        'ghost_events_open'::TEXT,
        COUNT(*)::NUMERIC,
        'Unexplained volatility without calendar events'::TEXT
    FROM fhq_calendar.unexplained_volatility_flags
    WHERE flag_status = 'OPEN'
    AND created_at >= p_since;

    -- High surprise events (|score| > 2)
    RETURN QUERY
    SELECT
        'high_surprise_events'::TEXT,
        COUNT(*)::NUMERIC,
        'Events with |surprise| > 2 std (significant)'::TEXT
    FROM fhq_calendar.calendar_events
    WHERE ABS(surprise_score) > 2
    AND created_at >= p_since;
END;
$$ LANGUAGE plpgsql;

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
    'SURPRISE_DIAGNOSTICS_ACTIVATED',
    'fhq_calendar',
    'DIAGNOSTIC_SYSTEM',
    'STIG',
    'DEPLOYED',
    'Surprise-based diagnostics activated. Functions: compute_surprise_score(), detect_ghost_events(), get_surprise_diagnostics(). View: v_surprise_impact_analysis.',
    jsonb_build_object(
        'functions_created', ARRAY['compute_surprise_score', 'detect_ghost_events', 'get_surprise_diagnostics'],
        'views_created', ARRAY['v_surprise_impact_analysis'],
        'directive', 'CEO Post-G3 Directive 2.2'
    )
);

-- Verification
DO $$
DECLARE
    func_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO func_count
    FROM information_schema.routines
    WHERE routine_schema = 'fhq_calendar'
    AND routine_name IN ('compute_surprise_score', 'detect_ghost_events', 'get_surprise_diagnostics');

    IF func_count >= 3 THEN
        RAISE NOTICE 'Surprise-based diagnostics: DEPLOYED (% functions)', func_count;
    ELSE
        RAISE WARNING 'Surprise-based diagnostics: INCOMPLETE';
    END IF;
END $$;
