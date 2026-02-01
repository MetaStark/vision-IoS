-- =====================================================
-- Migration 219: Regret Attribution Schema
-- =====================================================
-- Directive: CEO-DIR-2026-021 Optimization Phase
-- Purpose: Enable Type A/B/C regret classification
-- Authority: STIG (Observability Enhancement)
-- Classification: G1 (Schema Enhancement, No Policy Change)
--
-- Enables surgical optimization of the 16.1% regret rate:
-- - Type A: Hysteresis Lag (confirms_required too high)
-- - Type B: Confidence Floor (just below threshold)
-- - Type C: Data Blindness (missing macro signals)
-- =====================================================

BEGIN;

-- Add attribution columns to suppression ledger
ALTER TABLE fhq_governance.epistemic_suppression_ledger
ADD COLUMN IF NOT EXISTS regret_attribution_type TEXT,
ADD COLUMN IF NOT EXISTS regret_root_cause JSONB,
ADD COLUMN IF NOT EXISTS regret_magnitude_category TEXT;

-- Add constraint after data is populated
ALTER TABLE fhq_governance.epistemic_suppression_ledger
DROP CONSTRAINT IF EXISTS check_regret_attribution_type;

ALTER TABLE fhq_governance.epistemic_suppression_ledger
ADD CONSTRAINT check_regret_attribution_type CHECK (
  regret_attribution_type IS NULL OR
  regret_attribution_type IN (
    'TYPE_A_HYSTERESIS_LAG',
    'TYPE_B_CONFIDENCE_FLOOR',
    'TYPE_C_DATA_BLINDNESS',
    'TYPE_X_UNKNOWN'
  )
);

ALTER TABLE fhq_governance.epistemic_suppression_ledger
DROP CONSTRAINT IF EXISTS check_regret_magnitude_category;

ALTER TABLE fhq_governance.epistemic_suppression_ledger
ADD CONSTRAINT check_regret_magnitude_category CHECK (
  regret_magnitude_category IS NULL OR
  regret_magnitude_category IN ('LOW', 'MEDIUM', 'HIGH', 'EXTREME')
);

-- Index for attribution queries
CREATE INDEX IF NOT EXISTS idx_regret_attribution
ON fhq_governance.epistemic_suppression_ledger(regret_attribution_type)
WHERE regret_classification = 'REGRET';

CREATE INDEX IF NOT EXISTS idx_regret_magnitude_category
ON fhq_governance.epistemic_suppression_ledger(regret_magnitude_category)
WHERE regret_classification = 'REGRET';

-- Materialized view for attribution dashboard
CREATE MATERIALIZED VIEW IF NOT EXISTS fhq_governance.regret_attribution_summary AS
SELECT
  regret_attribution_type,
  regret_magnitude_category,
  COUNT(*) as occurrence_count,
  AVG(regret_magnitude) as avg_regret_magnitude,
  ARRAY_AGG(DISTINCT asset_id) as affected_assets,
  MIN(suppression_timestamp) as first_occurrence,
  MAX(suppression_timestamp) as latest_occurrence
FROM fhq_governance.epistemic_suppression_ledger
WHERE regret_classification = 'REGRET'
  AND regret_attribution_type IS NOT NULL
GROUP BY regret_attribution_type, regret_magnitude_category
ORDER BY occurrence_count DESC;

-- Function to refresh attribution summary
CREATE OR REPLACE FUNCTION fhq_governance.refresh_regret_attribution_summary()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW fhq_governance.regret_attribution_summary;

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
    'regret_attribution_summary',
    'MATERIALIZED_VIEW',
    'SYSTEM',
    'REFRESHED',
    'Weekly regret attribution metrics updated'
  );
END;
$$;

-- Function to categorize regret magnitude
CREATE OR REPLACE FUNCTION fhq_governance.categorize_regret_magnitude(
  p_regret_magnitude NUMERIC
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
  CASE
    WHEN p_regret_magnitude < 0.02 THEN RETURN 'LOW';
    WHEN p_regret_magnitude < 0.05 THEN RETURN 'MEDIUM';
    WHEN p_regret_magnitude < 0.10 THEN RETURN 'HIGH';
    ELSE RETURN 'EXTREME';
  END CASE;
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
  'epistemic_suppression_ledger',
  'DATABASE_TABLE',
  'STIG',
  'MIGRATION_EXECUTED',
  'Migration 219: Regret Attribution Schema - Enables Type A/B/C classification for surgical optimization',
  jsonb_build_object(
    'migration_id', 219,
    'migration_name', 'regret_attribution_schema',
    'directive', 'CEO-DIR-2026-021-OPTIMIZATION',
    'classification', 'G1_OBSERVABILITY_ENHANCEMENT',
    'policy_change', false,
    'tables_modified', ARRAY['epistemic_suppression_ledger'],
    'views_created', ARRAY['regret_attribution_summary'],
    'functions_created', ARRAY['refresh_regret_attribution_summary', 'categorize_regret_magnitude']
  )
);

COMMIT;

-- Verification
DO $$
DECLARE
  v_columns_added INTEGER;
  v_indexes_created INTEGER;
BEGIN
  -- Verify columns exist
  SELECT COUNT(*) INTO v_columns_added
  FROM information_schema.columns
  WHERE table_schema = 'fhq_governance'
    AND table_name = 'epistemic_suppression_ledger'
    AND column_name IN ('regret_attribution_type', 'regret_root_cause', 'regret_magnitude_category');

  -- Verify indexes exist
  SELECT COUNT(*) INTO v_indexes_created
  FROM pg_indexes
  WHERE schemaname = 'fhq_governance'
    AND tablename = 'epistemic_suppression_ledger'
    AND indexname IN ('idx_regret_attribution', 'idx_regret_magnitude_category');

  IF v_columns_added = 3 AND v_indexes_created = 2 THEN
    RAISE NOTICE '[OK] Migration 219 verified: % columns added, % indexes created', v_columns_added, v_indexes_created;
  ELSE
    RAISE EXCEPTION '[FAIL] Migration 219 verification failed: columns=%, indexes=%', v_columns_added, v_indexes_created;
  END IF;
END;
$$;
