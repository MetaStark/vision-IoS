-- =====================================================
-- Migration 221: Brier Score Tracking
-- =====================================================
-- Directive: CEO-DIR-2026-021 Optimization Phase
-- Purpose: Track forecast calibration for Phase 5 unlock gate
-- Authority: STIG (Observability Enhancement)
-- Classification: G1 (Schema Enhancement, No Policy Change)
--
-- Phase 5 Unlock Gate: Brier Score < 0.15 across all active regimes
-- Brier Score = Average of (forecast_probability - actual_outcome)^2
-- Perfect calibration = 0.0, Random guessing = 0.25, Worse than random > 0.25
-- =====================================================

BEGIN;

-- Brier score ledger table
CREATE TABLE IF NOT EXISTS fhq_governance.brier_score_ledger (
  score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Forecast identity
  belief_id UUID, -- Links to model_belief_state if available
  forecast_type TEXT NOT NULL CHECK (
    forecast_type IN ('REGIME_CLASSIFICATION', 'FORECAST_BELIEF', 'SIGNAL_CONFIDENCE')
  ),

  -- Forecast details
  asset_id TEXT,
  regime TEXT NOT NULL,
  asset_class TEXT,

  -- Brier components
  forecast_probability NUMERIC(6,4) NOT NULL CHECK (
    forecast_probability >= 0 AND forecast_probability <= 1
  ),
  actual_outcome BOOLEAN NOT NULL,
  squared_error NUMERIC(6,4) NOT NULL CHECK (
    squared_error >= 0 AND squared_error <= 1
  ),

  -- Temporal context
  forecast_timestamp TIMESTAMPTZ NOT NULL,
  outcome_timestamp TIMESTAMPTZ NOT NULL,
  forecast_horizon_hours INTEGER NOT NULL,

  -- Attribution
  generated_by TEXT NOT NULL, -- 'FINN', 'STIG', 'LARS'
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for aggregation
CREATE INDEX IF NOT EXISTS idx_brier_by_regime
ON fhq_governance.brier_score_ledger(regime, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_brier_by_forecast_type
ON fhq_governance.brier_score_ledger(forecast_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_brier_by_asset_class
ON fhq_governance.brier_score_ledger(asset_class, created_at DESC)
WHERE asset_class IS NOT NULL;

-- Function: Compute Brier score for regime over window
CREATE OR REPLACE FUNCTION fhq_governance.compute_brier_score_for_regime(
  p_regime TEXT,
  p_window_days INTEGER DEFAULT 30
)
RETURNS NUMERIC(6,4)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_brier_score NUMERIC(6,4);
  v_sample_count INTEGER;
BEGIN
  -- Compute average squared error over window
  SELECT
    AVG(squared_error),
    COUNT(*)
  INTO v_brier_score, v_sample_count
  FROM fhq_governance.brier_score_ledger
  WHERE regime = p_regime
    AND created_at >= NOW() - (p_window_days || ' days')::INTERVAL;

  -- Require minimum 10 samples for valid score
  IF v_sample_count < 10 THEN
    RETURN 1.0; -- Worst case (no calibration data)
  END IF;

  RETURN COALESCE(v_brier_score, 1.0);
END;
$$;

-- Function: Check if all active regimes meet calibration threshold
CREATE OR REPLACE FUNCTION fhq_governance.check_calibration_gate(
  p_threshold NUMERIC DEFAULT 0.15,
  p_window_days INTEGER DEFAULT 30
)
RETURNS TABLE(
  gate_passed BOOLEAN,
  regime TEXT,
  brier_score NUMERIC,
  sample_count INTEGER,
  passes_threshold BOOLEAN
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    (MIN(CASE WHEN bs.avg_squared_error < p_threshold THEN 1 ELSE 0 END) = 1) as gate_passed,
    bs.regime,
    bs.avg_squared_error as brier_score,
    bs.sample_count,
    (bs.avg_squared_error < p_threshold) as passes_threshold
  FROM (
    SELECT
      regime,
      AVG(squared_error) as avg_squared_error,
      COUNT(*) as sample_count
    FROM fhq_governance.brier_score_ledger
    WHERE created_at >= NOW() - (p_window_days || ' days')::INTERVAL
    GROUP BY regime
    HAVING COUNT(*) >= 10  -- Minimum sample requirement
  ) bs
  GROUP BY bs.regime, bs.avg_squared_error, bs.sample_count;
END;
$$;

-- Materialized view: Calibration dashboard
CREATE MATERIALIZED VIEW IF NOT EXISTS fhq_governance.calibration_dashboard AS
SELECT
  regime,
  forecast_type,
  asset_class,
  COUNT(*) as total_forecasts,
  AVG(squared_error) as brier_score,
  STDDEV(squared_error) as brier_std_dev,
  MIN(forecast_timestamp) as first_forecast,
  MAX(forecast_timestamp) as latest_forecast,
  AVG(forecast_horizon_hours) as avg_horizon_hours
FROM fhq_governance.brier_score_ledger
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY regime, forecast_type, asset_class
ORDER BY regime, forecast_type, asset_class;

-- Function to refresh calibration dashboard
CREATE OR REPLACE FUNCTION fhq_governance.refresh_calibration_dashboard()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW fhq_governance.calibration_dashboard;

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
    'calibration_dashboard',
    'MATERIALIZED_VIEW',
    'SYSTEM',
    'REFRESHED',
    'Weekly calibration metrics updated'
  );
END;
$$;

-- Function: Record Brier score from belief/outcome pair
CREATE OR REPLACE FUNCTION fhq_governance.record_brier_score(
  p_belief_id UUID,
  p_forecast_type TEXT,
  p_asset_id TEXT,
  p_regime TEXT,
  p_asset_class TEXT,
  p_forecast_probability NUMERIC,
  p_actual_outcome BOOLEAN,
  p_forecast_timestamp TIMESTAMPTZ,
  p_outcome_timestamp TIMESTAMPTZ,
  p_generated_by TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  v_squared_error NUMERIC(6,4);
  v_score_id UUID;
  v_forecast_horizon_hours INTEGER;
BEGIN
  -- Compute squared error
  v_squared_error := POWER(p_forecast_probability - CASE WHEN p_actual_outcome THEN 1.0 ELSE 0.0 END, 2);

  -- Compute forecast horizon
  v_forecast_horizon_hours := EXTRACT(EPOCH FROM (p_outcome_timestamp - p_forecast_timestamp)) / 3600;

  -- Insert score
  INSERT INTO fhq_governance.brier_score_ledger (
    belief_id,
    forecast_type,
    asset_id,
    regime,
    asset_class,
    forecast_probability,
    actual_outcome,
    squared_error,
    forecast_timestamp,
    outcome_timestamp,
    forecast_horizon_hours,
    generated_by
  ) VALUES (
    p_belief_id,
    p_forecast_type,
    p_asset_id,
    p_regime,
    p_asset_class,
    p_forecast_probability,
    p_actual_outcome,
    v_squared_error,
    p_forecast_timestamp,
    p_outcome_timestamp,
    v_forecast_horizon_hours,
    p_generated_by
  )
  RETURNING score_id INTO v_score_id;

  RETURN v_score_id;
END;
$$;

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
  'brier_score_ledger',
  'DATABASE_TABLE',
  'STIG',
  'MIGRATION_EXECUTED',
  'Migration 221: Brier Score Tracking - Phase 5 calibration gate infrastructure',
  jsonb_build_object(
    'migration_id', 221,
    'migration_name', 'brier_score_tracking',
    'directive', 'CEO-DIR-2026-021-OPTIMIZATION',
    'classification', 'G1_OBSERVABILITY_ENHANCEMENT',
    'policy_change', false,
    'phase_5_unlock_gate', true,
    'calibration_threshold', 0.15,
    'tables_created', ARRAY['brier_score_ledger'],
    'views_created', ARRAY['calibration_dashboard'],
    'functions_created', ARRAY['compute_brier_score_for_regime', 'check_calibration_gate', 'record_brier_score', 'refresh_calibration_dashboard']
  )
);

COMMIT;

-- Verification
DO $$
DECLARE
  v_table_exists BOOLEAN;
  v_functions_created INTEGER;
BEGIN
  -- Verify table exists
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'fhq_governance'
      AND table_name = 'brier_score_ledger'
  ) INTO v_table_exists;

  -- Verify functions exist
  SELECT COUNT(*) INTO v_functions_created
  FROM pg_proc p
  JOIN pg_namespace n ON p.pronamespace = n.oid
  WHERE n.nspname = 'fhq_governance'
    AND p.proname IN (
      'compute_brier_score_for_regime',
      'check_calibration_gate',
      'record_brier_score',
      'refresh_calibration_dashboard'
    );

  IF v_table_exists AND v_functions_created = 4 THEN
    RAISE NOTICE '[OK] Migration 221 verified: table created, % functions created', v_functions_created;
  ELSE
    RAISE EXCEPTION '[FAIL] Migration 221 verification failed: table_exists=%, functions=%', v_table_exists, v_functions_created;
  END IF;
END;
$$;
