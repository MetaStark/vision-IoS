-- Migration 239: CEO-DIR-2026-064R Lineage Schema Enforcement
-- Section 3.3: Lineage Schema Enforcement (IoS-010)
--
-- Purpose: Add required audit lineage columns to forecast_outcome_pairs
-- for deterministic A/B analysis and provable learning effect tracking.
--
-- Authority: CEO-DIR-2026-064R
-- Owner: STIG
-- Classification: MISSION_CRITICAL
-- Prerequisite: Must be executed BEFORE FINN commits damper code integration

BEGIN;

-- ============================================================================
-- TABLE EXTENSION: forecast_outcome_pairs
-- Add lineage columns for damper tracking (IoS-010 compliance)
-- ============================================================================

-- Add parent_forecast_id column (tracks original undamped forecast)
ALTER TABLE fhq_research.forecast_outcome_pairs
ADD COLUMN IF NOT EXISTS parent_forecast_id UUID;

-- Add damper_version_hash column (cryptographic proof of damper version used)
ALTER TABLE fhq_research.forecast_outcome_pairs
ADD COLUMN IF NOT EXISTS damper_version_hash TEXT;

-- Add damped_at timestamp (when dampening was applied)
ALTER TABLE fhq_research.forecast_outcome_pairs
ADD COLUMN IF NOT EXISTS damped_at TIMESTAMPTZ;

-- Add raw_confidence (original model confidence before dampening)
ALTER TABLE fhq_research.forecast_outcome_pairs
ADD COLUMN IF NOT EXISTS raw_confidence NUMERIC(5,4);

-- Add damped_confidence (confidence after dampening applied)
ALTER TABLE fhq_research.forecast_outcome_pairs
ADD COLUMN IF NOT EXISTS damped_confidence NUMERIC(5,4);

-- Add dampening_delta (amount of confidence reduction)
ALTER TABLE fhq_research.forecast_outcome_pairs
ADD COLUMN IF NOT EXISTS dampening_delta NUMERIC(5,4);

-- Add ceiling_applied (what ceiling was used)
ALTER TABLE fhq_research.forecast_outcome_pairs
ADD COLUMN IF NOT EXISTS ceiling_applied NUMERIC(5,4);

-- Add directive_ref (which CEO directive authorized the dampening)
ALTER TABLE fhq_research.forecast_outcome_pairs
ADD COLUMN IF NOT EXISTS directive_ref TEXT DEFAULT 'CEO-DIR-2026-063R';

-- ============================================================================
-- INDEX: Optimize queries for dampening analysis
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_fop_damper_version
ON fhq_research.forecast_outcome_pairs(damper_version_hash)
WHERE damper_version_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fop_parent_forecast
ON fhq_research.forecast_outcome_pairs(parent_forecast_id)
WHERE parent_forecast_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fop_dampening_delta
ON fhq_research.forecast_outcome_pairs(dampening_delta)
WHERE dampening_delta > 0;

-- ============================================================================
-- VIEW: Dampening effectiveness analysis
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_dampening_effectiveness AS
SELECT
    DATE(damped_at) as date,
    COUNT(*) as total_forecasts,
    COUNT(*) FILTER (WHERE dampening_delta > 0) as damped_count,
    ROUND(AVG(raw_confidence)::numeric, 4) as avg_raw_confidence,
    ROUND(AVG(damped_confidence)::numeric, 4) as avg_damped_confidence,
    ROUND(AVG(dampening_delta)::numeric, 4) as avg_dampening_delta,
    ROUND(MAX(dampening_delta)::numeric, 4) as max_dampening_delta,
    ROUND(AVG(ceiling_applied)::numeric, 4) as avg_ceiling_applied,
    COUNT(DISTINCT damper_version_hash) as damper_versions_used
FROM fhq_research.forecast_outcome_pairs
WHERE damped_at IS NOT NULL
GROUP BY DATE(damped_at)
ORDER BY date DESC;

-- ============================================================================
-- AUDIT: Log migration
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MIGRATION_EXECUTE',
    '239_ceo_dir_2026_064r_lineage_enforcement',
    'DATABASE_MIGRATION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-064R Section 3.3: Lineage Schema Enforcement (IoS-010)',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-064R',
        'section', '3.3 Lineage Schema Enforcement',
        'table', 'fhq_research.forecast_outcome_pairs',
        'columns_added', ARRAY[
            'parent_forecast_id',
            'damper_version_hash',
            'damped_at',
            'raw_confidence',
            'damped_confidence',
            'dampening_delta',
            'ceiling_applied',
            'directive_ref'
        ],
        'ios_ref', 'IoS-010',
        'purpose', 'Deterministic A/B analysis and provable learning effect'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_col_count
    FROM information_schema.columns
    WHERE table_schema = 'fhq_research'
    AND table_name = 'forecast_outcome_pairs'
    AND column_name IN ('parent_forecast_id', 'damper_version_hash');

    IF v_col_count < 2 THEN
        RAISE EXCEPTION 'Migration 239 FAILED: Required lineage columns not created';
    END IF;

    RAISE NOTICE 'Migration 239 SUCCESS: Lineage columns added to forecast_outcome_pairs';
    RAISE NOTICE 'CEO-DIR-2026-064R Section 3.3: Schema enforcement COMPLETE';
END $$;
