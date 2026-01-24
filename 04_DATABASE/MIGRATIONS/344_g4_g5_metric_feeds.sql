-- Migration 344: G4/G5 Metric Feeds for EC-022 Governed Test
-- Date: 2026-01-24
-- Author: STIG (EC-003)
-- Directive: CEO-DIR-2026 - EC-022 End-to-End Wiring Completion

BEGIN;

-- ============================================================================
-- G4: LEARNING VELOCITY METRICS FEED
-- Wire LVG/LVI computation to persist daily rows
-- ============================================================================

-- Function to compute and persist daily LVG metrics
CREATE OR REPLACE FUNCTION fhq_learning.compute_daily_lvg_metrics()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_metric_date DATE := CURRENT_DATE;
    v_hypotheses_born INTEGER;
    v_hypotheses_killed INTEGER;
    v_hypotheses_weakened INTEGER;
    v_hypotheses_promoted INTEGER;
    v_experiments_run INTEGER;
    v_tier1_experiments INTEGER;
    v_tier1_deaths INTEGER;
    v_death_rate NUMERIC(5,2);
    v_result JSONB;
BEGIN
    -- Count hypothesis changes in last 24h
    SELECT
        COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE),
        COUNT(*) FILTER (WHERE status = 'KILLED' AND last_updated_at >= CURRENT_DATE),
        COUNT(*) FILTER (WHERE status = 'WEAKENED' AND last_updated_at >= CURRENT_DATE),
        COUNT(*) FILTER (WHERE status = 'PROMOTED' AND last_updated_at >= CURRENT_DATE)
    INTO v_hypotheses_born, v_hypotheses_killed, v_hypotheses_weakened, v_hypotheses_promoted
    FROM fhq_learning.hypothesis_canon;

    -- Count experiments
    SELECT COUNT(*) INTO v_experiments_run
    FROM fhq_learning.experiment_registry
    WHERE created_at >= CURRENT_DATE;

    -- Tier-1 specific metrics
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE result = 'REJECTED' OR result = 'FAILED')
    INTO v_tier1_experiments, v_tier1_deaths
    FROM fhq_learning.experiment_registry
    WHERE experiment_tier = 1 AND created_at >= CURRENT_DATE;

    -- Calculate death rate
    v_death_rate := CASE
        WHEN v_tier1_experiments > 0 THEN
            ROUND((v_tier1_deaths::NUMERIC / v_tier1_experiments) * 100, 2)
        ELSE 0
    END;

    -- Insert or update daily metrics (net_hypothesis_change is generated)
    INSERT INTO fhq_learning.learning_velocity_metrics (
        metric_date,
        hypotheses_born,
        hypotheses_killed,
        hypotheses_weakened,
        hypotheses_promoted,
        experiments_run,
        tier1_experiments,
        tier1_deaths,
        death_rate_pct,
        velocity_status,
        brake_triggered,
        computed_at
    ) VALUES (
        v_metric_date,
        COALESCE(v_hypotheses_born, 0),
        COALESCE(v_hypotheses_killed, 0),
        COALESCE(v_hypotheses_weakened, 0),
        COALESCE(v_hypotheses_promoted, 0),
        COALESCE(v_experiments_run, 0),
        COALESCE(v_tier1_experiments, 0),
        COALESCE(v_tier1_deaths, 0),
        COALESCE(v_death_rate, 0),
        CASE
            WHEN v_hypotheses_born > 10 THEN 'SPIKE'
            WHEN v_hypotheses_killed > v_hypotheses_born * 2 THEN 'CONTRACTION'
            ELSE 'NORMAL'
        END,
        FALSE,
        NOW()
    )
    ON CONFLICT (metric_date) DO UPDATE SET
        hypotheses_born = EXCLUDED.hypotheses_born,
        hypotheses_killed = EXCLUDED.hypotheses_killed,
        hypotheses_weakened = EXCLUDED.hypotheses_weakened,
        hypotheses_promoted = EXCLUDED.hypotheses_promoted,
        experiments_run = EXCLUDED.experiments_run,
        tier1_experiments = EXCLUDED.tier1_experiments,
        tier1_deaths = EXCLUDED.tier1_deaths,
        death_rate_pct = EXCLUDED.death_rate_pct,
        velocity_status = EXCLUDED.velocity_status,
        computed_at = NOW();

    v_result := jsonb_build_object(
        'metric_date', v_metric_date,
        'hypotheses_born', v_hypotheses_born,
        'hypotheses_killed', v_hypotheses_killed,
        'death_rate_pct', v_death_rate,
        'status', 'COMPUTED'
    );

    RETURN v_result;
END;
$$;

-- Add unique constraint on metric_date if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'learning_velocity_metrics_metric_date_key'
    ) THEN
        ALTER TABLE fhq_learning.learning_velocity_metrics
        ADD CONSTRAINT learning_velocity_metrics_metric_date_key UNIQUE (metric_date);
    END IF;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- ============================================================================
-- G5: CONTEXT LIFT MEASUREMENT FEED
-- Implement v_context_brier_impact with real lift computation
-- ============================================================================

-- Drop existing view with incompatible columns
DROP VIEW IF EXISTS fhq_learning.v_context_brier_impact CASCADE;

-- Create the context lift view with proper schema
CREATE VIEW fhq_learning.v_context_brier_impact AS
WITH baseline_brier AS (
    -- Get baseline Brier from the test's baseline_definition
    SELECT
        cte.test_id,
        cte.test_code,
        (cte.baseline_definition->>'brier_score')::TEXT as baseline_brier_text,
        COALESCE(
            (cte.baseline_definition->>'brier_score_numeric')::NUMERIC,
            0.35  -- Default baseline if not specified
        ) as baseline_brier
    FROM fhq_calendar.canonical_test_events cte
    WHERE cte.status = 'ACTIVE'
),
current_brier AS (
    -- Get current Brier score from forecast skill metrics
    SELECT
        brier_score_mean as current_brier,
        resolved_count as sample_count,
        computed_at
    FROM fhq_research.forecast_skill_metrics
    ORDER BY computed_at DESC
    LIMIT 1
),
context_annotations AS (
    -- Count context annotations if they exist
    SELECT COUNT(*) as annotation_count
    FROM fhq_learning.context_annotations
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
)
SELECT
    bb.test_id,
    bb.test_code,
    bb.baseline_brier,
    cb.current_brier,
    cb.sample_count,
    CASE
        WHEN cb.current_brier IS NOT NULL AND bb.baseline_brier > 0 THEN
            ROUND((bb.baseline_brier - cb.current_brier) / bb.baseline_brier * 100, 2)
        ELSE NULL
    END as lift_pct,
    CASE
        WHEN cb.current_brier IS NOT NULL THEN
            bb.baseline_brier - cb.current_brier
        ELSE NULL
    END as brier_delta,
    ca.annotation_count,
    cb.computed_at as asof_ts,
    CASE
        WHEN cb.current_brier IS NULL THEN 'NO_DATA'
        WHEN cb.current_brier < bb.baseline_brier THEN 'POSITIVE_LIFT'
        WHEN cb.current_brier > bb.baseline_brier THEN 'NEGATIVE_LIFT'
        ELSE 'NEUTRAL'
    END as lift_status
FROM baseline_brier bb
CROSS JOIN current_brier cb
CROSS JOIN context_annotations ca;

-- ============================================================================
-- ENHANCED ORCHESTRATOR SUPPORT
-- ============================================================================

-- Add columns to canonical_test_events for enhanced tracking
DO $$
BEGIN
    -- Baseline captured flag
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_calendar'
        AND table_name = 'canonical_test_events'
        AND column_name = 'baseline_captured'
    ) THEN
        ALTER TABLE fhq_calendar.canonical_test_events
        ADD COLUMN baseline_captured BOOLEAN DEFAULT FALSE;
    END IF;

    -- Baseline captured timestamp
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_calendar'
        AND table_name = 'canonical_test_events'
        AND column_name = 'baseline_captured_at'
    ) THEN
        ALTER TABLE fhq_calendar.canonical_test_events
        ADD COLUMN baseline_captured_at TIMESTAMPTZ;
    END IF;

    -- Baseline hash for verification
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_calendar'
        AND table_name = 'canonical_test_events'
        AND column_name = 'baseline_hash'
    ) THEN
        ALTER TABLE fhq_calendar.canonical_test_events
        ADD COLUMN baseline_hash TEXT;
    END IF;

    -- Expected sample size by day (JSONB map)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_calendar'
        AND table_name = 'canonical_test_events'
        AND column_name = 'expected_sample_by_day'
    ) THEN
        ALTER TABLE fhq_calendar.canonical_test_events
        ADD COLUMN expected_sample_by_day JSONB;
    END IF;

    -- Current sample size
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_calendar'
        AND table_name = 'canonical_test_events'
        AND column_name = 'current_sample_size'
    ) THEN
        ALTER TABLE fhq_calendar.canonical_test_events
        ADD COLUMN current_sample_size INTEGER DEFAULT 0;
    END IF;

    -- Track status (on_track, behind, ahead)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_calendar'
        AND table_name = 'canonical_test_events'
        AND column_name = 'track_status'
    ) THEN
        ALTER TABLE fhq_calendar.canonical_test_events
        ADD COLUMN track_status TEXT DEFAULT 'PENDING'
            CHECK (track_status IN ('PENDING', 'ON_TRACK', 'BEHIND', 'AHEAD'));
    END IF;
END $$;

-- Function to capture and hash baseline
CREATE OR REPLACE FUNCTION fhq_calendar.capture_test_baseline(p_test_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_test RECORD;
    v_baseline JSONB;
    v_hash TEXT;
BEGIN
    SELECT * INTO v_test
    FROM fhq_calendar.canonical_test_events
    WHERE test_id = p_test_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Test not found');
    END IF;

    IF v_test.baseline_captured THEN
        RETURN jsonb_build_object('status', 'ALREADY_CAPTURED', 'captured_at', v_test.baseline_captured_at);
    END IF;

    -- Build baseline snapshot
    v_baseline := jsonb_build_object(
        'captured_at', NOW(),
        'lvi', (SELECT death_rate_pct FROM fhq_learning.learning_velocity_metrics ORDER BY metric_date DESC LIMIT 1),
        'brier_score', (SELECT brier_score_mean FROM fhq_research.forecast_skill_metrics ORDER BY computed_at DESC LIMIT 1),
        'tier1_death_rate', (SELECT death_rate_pct FROM fhq_learning.v_tier1_calibration_status LIMIT 1),
        'sample_count', (SELECT resolved_count FROM fhq_research.forecast_skill_metrics ORDER BY computed_at DESC LIMIT 1)
    );

    -- Generate hash
    v_hash := md5(v_baseline::TEXT);

    -- Update test
    UPDATE fhq_calendar.canonical_test_events
    SET
        baseline_captured = TRUE,
        baseline_captured_at = NOW(),
        baseline_hash = v_hash,
        baseline_definition = COALESCE(baseline_definition, '{}'::JSONB) || v_baseline
    WHERE test_id = p_test_id;

    RETURN jsonb_build_object(
        'status', 'CAPTURED',
        'baseline', v_baseline,
        'hash', v_hash
    );
END;
$$;

-- Function to evaluate track status based on sample size
CREATE OR REPLACE FUNCTION fhq_calendar.evaluate_track_status(p_test_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_test RECORD;
    v_progress RECORD;
    v_expected_sample INTEGER;
    v_current_sample INTEGER;
    v_track_status TEXT;
    v_deficit INTEGER;
    v_power_impact NUMERIC;
BEGIN
    SELECT * INTO v_test
    FROM fhq_calendar.canonical_test_events
    WHERE test_id = p_test_id;

    SELECT * INTO v_progress
    FROM fhq_calendar.compute_test_progress(p_test_id);

    -- Get current sample from forecast metrics
    SELECT COALESCE(resolved_count, 0) INTO v_current_sample
    FROM fhq_research.forecast_skill_metrics
    ORDER BY computed_at DESC LIMIT 1;

    -- Calculate expected sample (linear interpolation)
    -- Assume target is 100 samples over 30 days
    v_expected_sample := CEIL((v_progress.days_elapsed + 1) * (100.0 / 30));

    -- Determine track status
    IF v_current_sample >= v_expected_sample THEN
        IF v_current_sample > v_expected_sample * 1.2 THEN
            v_track_status := 'AHEAD';
        ELSE
            v_track_status := 'ON_TRACK';
        END IF;
    ELSE
        v_track_status := 'BEHIND';
    END IF;

    -- Calculate deficit and power impact
    v_deficit := GREATEST(0, v_expected_sample - v_current_sample);
    v_power_impact := CASE
        WHEN v_deficit > 0 THEN ROUND((v_deficit::NUMERIC / v_expected_sample) * 100, 1)
        ELSE 0
    END;

    -- Update test
    UPDATE fhq_calendar.canonical_test_events
    SET
        track_status = v_track_status,
        current_sample_size = v_current_sample
    WHERE test_id = p_test_id;

    RETURN jsonb_build_object(
        'track_status', v_track_status,
        'current_sample', v_current_sample,
        'expected_sample', v_expected_sample,
        'deficit', v_deficit,
        'power_impact_pct', v_power_impact,
        'days_elapsed', v_progress.days_elapsed
    );
END;
$$;

-- ============================================================================
-- UPDATE SIGNAL REGISTRY WITH NEW SOURCES
-- ============================================================================

-- Update context_lift signal to use new view
UPDATE fhq_calendar.test_signal_registry
SET source_column = 'lift_pct'
WHERE signal_key = 'context_lift';

-- Add new signals
INSERT INTO fhq_calendar.test_signal_registry (signal_key, signal_name, source_schema, source_table, source_column, aggregation)
VALUES
    ('brier_delta', 'Brier Score Delta', 'fhq_learning', 'v_context_brier_impact', 'brier_delta', 'LATEST'),
    ('lift_status', 'Context Lift Status', 'fhq_learning', 'v_context_brier_impact', 'lift_status', 'LATEST'),
    ('sample_count', 'Resolved Sample Count', 'fhq_learning', 'v_context_brier_impact', 'sample_count', 'LATEST')
ON CONFLICT (signal_key) DO UPDATE SET
    source_schema = EXCLUDED.source_schema,
    source_table = EXCLUDED.source_table,
    source_column = EXCLUDED.source_column;

-- ============================================================================
-- ENHANCED CHECK_ESCALATION_CONDITIONS
-- Now includes sample size and metric feed checks
-- ============================================================================

-- Drop existing function with different return type
DROP FUNCTION IF EXISTS fhq_calendar.check_escalation_conditions(UUID);

CREATE OR REPLACE FUNCTION fhq_calendar.check_escalation_conditions(p_test_id UUID)
RETURNS TABLE(should_escalate BOOLEAN, escalation_reason TEXT, recommended_actions JSONB, escalation_level TEXT)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_test RECORD;
    v_progress RECORD;
    v_track JSONB;
    v_lvg_latest DATE;
    v_reasons TEXT[] := ARRAY[]::TEXT[];
    v_actions JSONB := '[]'::JSONB;
    v_level TEXT := 'NONE';
BEGIN
    -- Get test details
    SELECT * INTO v_test
    FROM fhq_calendar.canonical_test_events
    WHERE test_id = p_test_id;

    -- Get progress
    SELECT * INTO v_progress
    FROM fhq_calendar.compute_test_progress(p_test_id);

    -- Get track status
    v_track := fhq_calendar.evaluate_track_status(p_test_id);

    -- Check LVG feed (G4 fail-closed)
    SELECT MAX(metric_date) INTO v_lvg_latest
    FROM fhq_learning.learning_velocity_metrics;

    IF v_lvg_latest IS NULL OR v_lvg_latest < CURRENT_DATE - INTERVAL '1 day' THEN
        v_reasons := array_append(v_reasons, 'LVG metric feed missing for >24h');
        v_actions := v_actions || '["Run LVG computation", "Check learning_velocity_metrics table"]'::JSONB;
        v_level := 'WARNING';
    END IF;

    -- Check sample size (do NOT auto-invalidate, escalate with options)
    IF (v_track->>'track_status')::TEXT = 'BEHIND' THEN
        v_reasons := array_append(v_reasons,
            format('Sample size behind: current %s, expected %s (deficit: %s, power impact: %s%%)',
                v_track->>'current_sample',
                v_track->>'expected_sample',
                v_track->>'deficit',
                v_track->>'power_impact_pct'
            ));
        v_actions := v_actions || jsonb_build_array(
            'Increase forecast volume',
            'Broaden universe/horizons',
            'Extend observation window',
            'Accept reduced statistical power'
        );
        IF v_level = 'NONE' THEN v_level := 'WARNING'; END IF;
    END IF;

    -- Check if past end date without resolution
    IF v_progress.is_overdue AND v_test.verdict = 'PENDING' THEN
        v_reasons := array_append(v_reasons, 'Test window ended without verdict');
        v_actions := v_actions || '["Record final verdict", "Request extension", "Mark inconclusive"]'::JSONB;
        v_level := 'ACTION_REQUIRED';
    END IF;

    -- Check if baseline not captured
    IF NOT COALESCE(v_test.baseline_captured, FALSE) THEN
        v_reasons := array_append(v_reasons, 'Baseline not yet captured');
        v_actions := v_actions || '["Capture baseline snapshot", "Verify metric sources"]'::JSONB;
        IF v_level = 'NONE' THEN v_level := 'WARNING'; END IF;
    END IF;

    should_escalate := (array_length(v_reasons, 1) > 0);
    escalation_reason := array_to_string(v_reasons, '; ');
    recommended_actions := v_actions;
    escalation_level := v_level;

    RETURN QUERY SELECT should_escalate, escalation_reason, recommended_actions, escalation_level;
END;
$$;

-- ============================================================================
-- SEED INITIAL LVG DATA FOR TODAY
-- ============================================================================

SELECT fhq_learning.compute_daily_lvg_metrics();

-- ============================================================================
-- CAPTURE BASELINE FOR EC-022
-- ============================================================================

SELECT fhq_calendar.capture_test_baseline('fadbbc8d-c5c4-4da7-a379-4fbe890a8010'::UUID);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

SELECT 'LVG Metrics' as component, COUNT(*) as count FROM fhq_learning.learning_velocity_metrics
UNION ALL
SELECT 'Context Lift View', COUNT(*) FROM fhq_learning.v_context_brier_impact
UNION ALL
SELECT 'Signal Registry', COUNT(*) FROM fhq_calendar.test_signal_registry;
