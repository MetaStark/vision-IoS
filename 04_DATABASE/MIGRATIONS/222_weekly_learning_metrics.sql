-- =====================================================
-- Migration 222: Weekly Learning Metrics Dashboard
-- =====================================================
-- Directive: CEO-DIR-2026-022 (Gap Closure)
-- Purpose: Weekly aggregated metrics for observation window
-- Authority: STIG (Observability Enhancement)
-- Classification: G1 (Schema Enhancement, No Policy Change)
--
-- Provides CEO/VEGA with weekly pulse on learning health:
-- - Regret/Wisdom rates by week
-- - Attribution trends
-- - Magnitude analysis
-- - Match rate stability
-- =====================================================

BEGIN;

-- Materialized view for weekly metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS fhq_governance.weekly_learning_metrics AS
WITH weekly_data AS (
  SELECT
    EXTRACT(ISOYEAR FROM suppression_timestamp)::INTEGER as iso_year,
    EXTRACT(WEEK FROM suppression_timestamp)::INTEGER as iso_week,
    regret_classification,
    regret_attribution_type,
    regret_magnitude_category,
    regret_magnitude,
    suppressed_confidence,
    chosen_confidence
  FROM fhq_governance.epistemic_suppression_ledger
  WHERE suppression_timestamp >= '2026-01-08'  -- Deployment date
)
SELECT
  iso_year,
  iso_week,

  -- Overall counts
  COUNT(*) as total_suppressions,
  COUNT(*) FILTER (WHERE regret_classification = 'REGRET') as regret_count,
  COUNT(*) FILTER (WHERE regret_classification = 'WISDOM') as wisdom_count,
  COUNT(*) FILTER (WHERE regret_classification = 'UNRESOLVED') as unresolved_count,

  -- Rates
  ROUND(
    COUNT(*) FILTER (WHERE regret_classification = 'REGRET')::NUMERIC / NULLIF(COUNT(*), 0),
    4
  ) as regret_rate,
  ROUND(
    COUNT(*) FILTER (WHERE regret_classification = 'WISDOM')::NUMERIC / NULLIF(COUNT(*), 0),
    4
  ) as wisdom_rate,

  -- Attribution breakdown
  COUNT(*) FILTER (WHERE regret_attribution_type = 'TYPE_A_HYSTERESIS_LAG') as type_a_count,
  COUNT(*) FILTER (WHERE regret_attribution_type = 'TYPE_B_CONFIDENCE_FLOOR') as type_b_count,
  COUNT(*) FILTER (WHERE regret_attribution_type = 'TYPE_C_DATA_BLINDNESS') as type_c_count,
  COUNT(*) FILTER (WHERE regret_attribution_type = 'TYPE_X_UNKNOWN') as type_x_count,

  -- Magnitude analysis
  AVG(regret_magnitude) FILTER (WHERE regret_classification = 'REGRET') as avg_regret_magnitude,
  AVG(regret_magnitude) FILTER (WHERE regret_classification = 'WISDOM') as avg_wisdom_magnitude,
  STDDEV(regret_magnitude) FILTER (WHERE regret_classification = 'REGRET') as regret_magnitude_stddev,

  -- Magnitude categories
  COUNT(*) FILTER (WHERE regret_magnitude_category = 'LOW') as low_magnitude_count,
  COUNT(*) FILTER (WHERE regret_magnitude_category = 'MEDIUM') as medium_magnitude_count,
  COUNT(*) FILTER (WHERE regret_magnitude_category = 'HIGH') as high_magnitude_count,
  COUNT(*) FILTER (WHERE regret_magnitude_category = 'EXTREME') as extreme_magnitude_count,

  -- Confidence analysis
  AVG(suppressed_confidence) FILTER (WHERE regret_classification = 'REGRET') as avg_regret_suppressed_confidence,
  AVG(chosen_confidence) FILTER (WHERE regret_classification = 'REGRET') as avg_regret_chosen_confidence,
  AVG(chosen_confidence - suppressed_confidence) FILTER (WHERE regret_classification = 'REGRET') as avg_confidence_delta,

  -- Temporal
  MIN(iso_year || '-W' || LPAD(iso_week::TEXT, 2, '0')) as week_label

FROM weekly_data
GROUP BY iso_year, iso_week
ORDER BY iso_year DESC, iso_week DESC;

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_weekly_metrics_week
ON fhq_governance.weekly_learning_metrics(iso_year, iso_week);

-- Function to refresh weekly metrics
CREATE OR REPLACE FUNCTION fhq_governance.refresh_weekly_learning_metrics()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW fhq_governance.weekly_learning_metrics;

  -- Log refresh
  INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale
  ) VALUES (
    'METRICS_REFRESH',
    'weekly_learning_metrics',
    'MATERIALIZED_VIEW',
    'SYSTEM',
    'REFRESHED',
    'Weekly learning metrics dashboard updated'
  );
END;
$$;

-- Function to get current week metrics (live query, not cached)
CREATE OR REPLACE FUNCTION fhq_governance.get_current_week_metrics()
RETURNS TABLE(
  iso_year INTEGER,
  iso_week INTEGER,
  total_suppressions BIGINT,
  regret_count BIGINT,
  wisdom_count BIGINT,
  regret_rate NUMERIC,
  type_a_count BIGINT,
  type_b_count BIGINT,
  type_c_count BIGINT,
  avg_regret_magnitude NUMERIC
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_current_year INTEGER;
  v_current_week INTEGER;
BEGIN
  -- Get current ISO week
  v_current_year := EXTRACT(ISOYEAR FROM CURRENT_DATE);
  v_current_week := EXTRACT(WEEK FROM CURRENT_DATE);

  RETURN QUERY
  SELECT
    v_current_year as iso_year,
    v_current_week as iso_week,
    COUNT(*) as total_suppressions,
    COUNT(*) FILTER (WHERE regret_classification = 'REGRET') as regret_count,
    COUNT(*) FILTER (WHERE regret_classification = 'WISDOM') as wisdom_count,
    ROUND(
      COUNT(*) FILTER (WHERE regret_classification = 'REGRET')::NUMERIC / NULLIF(COUNT(*), 0),
      4
    ) as regret_rate,
    COUNT(*) FILTER (WHERE regret_attribution_type = 'TYPE_A_HYSTERESIS_LAG') as type_a_count,
    COUNT(*) FILTER (WHERE regret_attribution_type = 'TYPE_B_CONFIDENCE_FLOOR') as type_b_count,
    COUNT(*) FILTER (WHERE regret_attribution_type = 'TYPE_C_DATA_BLINDNESS') as type_c_count,
    AVG(regret_magnitude) FILTER (WHERE regret_classification = 'REGRET') as avg_regret_magnitude
  FROM fhq_governance.epistemic_suppression_ledger
  WHERE EXTRACT(ISOYEAR FROM suppression_timestamp) = v_current_year
    AND EXTRACT(WEEK FROM suppression_timestamp) = v_current_week;
END;
$$;

-- Function to detect regret stability (for Phase 5 unlock)
CREATE OR REPLACE FUNCTION fhq_governance.check_regret_stability(
  p_window_weeks INTEGER DEFAULT 4,
  p_threshold NUMERIC DEFAULT 0.05
)
RETURNS TABLE(
  stable BOOLEAN,
  variance NUMERIC,
  weeks_analyzed INTEGER,
  min_regret_rate NUMERIC,
  max_regret_rate NUMERIC,
  avg_regret_rate NUMERIC
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_variance NUMERIC;
  v_weeks INTEGER;
BEGIN
  -- Calculate variance of regret rates over last N weeks
  SELECT
    VARIANCE(regret_rate),
    COUNT(*)
  INTO v_variance, v_weeks
  FROM fhq_governance.weekly_learning_metrics
  WHERE iso_year >= EXTRACT(ISOYEAR FROM CURRENT_DATE - INTERVAL '8 weeks')
  ORDER BY iso_year DESC, iso_week DESC
  LIMIT p_window_weeks;

  RETURN QUERY
  SELECT
    (COALESCE(v_variance, 1.0) < p_threshold) as stable,
    COALESCE(v_variance, 1.0) as variance,
    COALESCE(v_weeks, 0) as weeks_analyzed,
    MIN(regret_rate) as min_regret_rate,
    MAX(regret_rate) as max_regret_rate,
    AVG(regret_rate) as avg_regret_rate
  FROM fhq_governance.weekly_learning_metrics
  WHERE iso_year >= EXTRACT(ISOYEAR FROM CURRENT_DATE - INTERVAL '8 weeks')
  ORDER BY iso_year DESC, iso_week DESC
  LIMIT p_window_weeks;
END;
$$;

-- Initial population
REFRESH MATERIALIZED VIEW fhq_governance.weekly_learning_metrics;

-- Governance log
INSERT INTO fhq_governance.governance_actions_log (
  action_type,
  action_target,
  action_target_type,
  initiated_by,
  decision,
  decision_rationale,
  metadata
) VALUES (
  'SCHEMA_MIGRATION',
  'weekly_learning_metrics',
  'MATERIALIZED_VIEW',
  'STIG',
  'MIGRATION_EXECUTED',
  'Migration 222: Weekly Learning Metrics Dashboard - CEO-DIR-2026-022 gap closure',
  jsonb_build_object(
    'migration_id', 222,
    'migration_name', 'weekly_learning_metrics',
    'directive', 'CEO-DIR-2026-022',
    'classification', 'G1_OBSERVABILITY_ENHANCEMENT',
    'policy_change', false,
    'views_created', ARRAY['weekly_learning_metrics'],
    'functions_created', ARRAY['refresh_weekly_learning_metrics', 'get_current_week_metrics', 'check_regret_stability']
  )
);

COMMIT;

-- Verification
DO $$
DECLARE
  v_view_exists BOOLEAN;
  v_functions_created INTEGER;
  v_row_count BIGINT;
BEGIN
  -- Verify view exists
  SELECT EXISTS (
    SELECT 1 FROM pg_matviews
    WHERE schemaname = 'fhq_governance'
      AND matviewname = 'weekly_learning_metrics'
  ) INTO v_view_exists;

  -- Verify functions exist
  SELECT COUNT(*) INTO v_functions_created
  FROM pg_proc p
  JOIN pg_namespace n ON p.pronamespace = n.oid
  WHERE n.nspname = 'fhq_governance'
    AND p.proname IN (
      'refresh_weekly_learning_metrics',
      'get_current_week_metrics',
      'check_regret_stability'
    );

  -- Check data populated
  SELECT COUNT(*) INTO v_row_count
  FROM fhq_governance.weekly_learning_metrics;

  IF v_view_exists AND v_functions_created = 3 AND v_row_count > 0 THEN
    RAISE NOTICE '[OK] Migration 222 verified: view exists, % functions created, % rows populated', v_functions_created, v_row_count;
  ELSE
    RAISE EXCEPTION '[FAIL] Migration 222 verification failed: view_exists=%, functions=%, rows=%', v_view_exists, v_functions_created, v_row_count;
  END IF;
END;
$$;
