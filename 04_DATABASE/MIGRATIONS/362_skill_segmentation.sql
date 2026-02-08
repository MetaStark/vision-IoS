-- ============================================================================
-- MIGRATION 362: SKILL SEGMENTATION VIEW & PREDICTION BLACKLIST
-- ============================================================================
-- Authority: CEO-DIR-2026-128 DAY43 (WEEKLY RESET & LEARNING ACTIVATION)
-- Purpose: Accept and segment current skill state, create prediction blacklist
-- Executor: STIG (EC-003)
-- Date: 2026-02-08
--
-- Current State:
--   FSS = -1.265 (worse than random). We must be honest about where we
--   have skill and where we are anti-predictive. This migration creates:
--   1. Skill segmentation by asset
--   2. Prediction blacklist for anti-predictive assets
--   3. Blacklist enforcement view for generators
--
-- Skill Tiers:
--   - SKILLED: FSS >= 0.60 (demonstrable edge)
--   - WEAK_POSITIVE: FSS >= 0 (slight edge, needs more data)
--   - WEAK_NEGATIVE: FSS >= -0.50 (slight anti-skill, concerning)
--   - ANTI_PREDICTIVE: FSS < -0.50 (strong anti-skill, BLACKLIST)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CREATE SKILL SEGMENTATION MATERIALIZED VIEW
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS fhq_research.skill_segmentation;

CREATE MATERIALIZED VIEW fhq_research.skill_segmentation AS
SELECT
    asset_id,
    ROUND(AVG(fss_value)::numeric, 3) as avg_fss,
    ROUND(STDDEV(fss_value)::numeric, 3) as fss_stddev,
    COUNT(*) as sample_size,
    MIN(computation_timestamp) as first_computed,
    MAX(computation_timestamp) as last_computed,
    CASE
        WHEN AVG(fss_value) >= 0.60 THEN 'SKILLED'
        WHEN AVG(fss_value) >= 0 THEN 'WEAK_POSITIVE'
        WHEN AVG(fss_value) >= -0.50 THEN 'WEAK_NEGATIVE'
        ELSE 'ANTI_PREDICTIVE'
    END as skill_tier
FROM fhq_research.fss_computation_log
WHERE computation_timestamp > NOW() - INTERVAL '30 days'
GROUP BY asset_id;

-- Create index for hypothesis generators to query
CREATE INDEX idx_skill_segmentation_tier
ON fhq_research.skill_segmentation(skill_tier);

CREATE INDEX idx_skill_segmentation_asset
ON fhq_research.skill_segmentation(asset_id);

COMMENT ON MATERIALIZED VIEW fhq_research.skill_segmentation IS
'CEO-DIR-2026-128: Skill segmentation by asset. Refresh daily. SKILLED/WEAK_POSITIVE/WEAK_NEGATIVE/ANTI_PREDICTIVE tiers.';

-- ============================================================================
-- 2. CREATE PREDICTION BLACKLIST TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.prediction_blacklist (
    blacklist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id TEXT NOT NULL,
    blacklist_reason TEXT NOT NULL,
    fss_evidence NUMERIC,
    sample_size INTEGER,
    blacklisted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    blacklisted_by TEXT NOT NULL DEFAULT 'CEO-DIR-2026-128',
    review_after TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days',
    reviewed_at TIMESTAMPTZ,
    review_status TEXT,  -- 'LIFTED', 'EXTENDED', NULL
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prediction_blacklist_asset
ON fhq_governance.prediction_blacklist(asset_id);

CREATE INDEX IF NOT EXISTS idx_prediction_blacklist_active
ON fhq_governance.prediction_blacklist(review_after)
WHERE reviewed_at IS NULL;

COMMENT ON TABLE fhq_governance.prediction_blacklist IS
'CEO-DIR-2026-128: Assets we cannot predict. Generators must check before hypothesis birth.';

-- ============================================================================
-- 3. POPULATE BLACKLIST FROM ANTI-PREDICTIVE ASSETS
-- ============================================================================

INSERT INTO fhq_governance.prediction_blacklist (asset_id, blacklist_reason, fss_evidence, sample_size, blacklisted_by)
SELECT
    asset_id,
    'FSS < -0.50 (anti-predictive): We are worse than random on this asset',
    avg_fss,
    sample_size,
    'CEO-DIR-2026-128'
FROM fhq_research.skill_segmentation
WHERE skill_tier = 'ANTI_PREDICTIVE'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 4. CREATE BLACKLIST CHECK FUNCTION (for generators)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.is_asset_blacklisted(p_asset_id TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM fhq_governance.prediction_blacklist
        WHERE asset_id = p_asset_id
          AND review_after > NOW()
          AND reviewed_at IS NULL
    );
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION fhq_governance.is_asset_blacklisted IS
'CEO-DIR-2026-128: Returns TRUE if asset is on prediction blacklist. Generators must call before hypothesis birth.';

-- ============================================================================
-- 5. CREATE SKILL SUMMARY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.skill_summary AS
SELECT
    skill_tier,
    COUNT(*) as asset_count,
    ROUND(AVG(avg_fss)::numeric, 3) as tier_avg_fss,
    SUM(sample_size) as total_samples,
    ARRAY_AGG(asset_id ORDER BY avg_fss DESC) as assets
FROM fhq_research.skill_segmentation
GROUP BY skill_tier
ORDER BY
    CASE skill_tier
        WHEN 'SKILLED' THEN 1
        WHEN 'WEAK_POSITIVE' THEN 2
        WHEN 'WEAK_NEGATIVE' THEN 3
        WHEN 'ANTI_PREDICTIVE' THEN 4
    END;

COMMENT ON VIEW fhq_research.skill_summary IS
'CEO-DIR-2026-128: Summary of skill tiers across all assets. Honest skill assessment.';

-- ============================================================================
-- 6. CREATE REFRESH FUNCTION FOR MATERIALIZED VIEW
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.refresh_skill_segmentation()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY fhq_research.skill_segmentation;

    -- Auto-update blacklist based on new segmentation
    INSERT INTO fhq_governance.prediction_blacklist (asset_id, blacklist_reason, fss_evidence, sample_size, blacklisted_by)
    SELECT
        asset_id,
        'FSS < -0.50 (anti-predictive): Auto-blacklisted on refresh',
        avg_fss,
        sample_size,
        'AUTO_REFRESH'
    FROM fhq_research.skill_segmentation
    WHERE skill_tier = 'ANTI_PREDICTIVE'
      AND asset_id NOT IN (
          SELECT asset_id FROM fhq_governance.prediction_blacklist
          WHERE review_after > NOW() AND reviewed_at IS NULL
      );

    RAISE NOTICE 'Skill segmentation refreshed at %', NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_research.refresh_skill_segmentation IS
'CEO-DIR-2026-128: Refresh skill segmentation and auto-update blacklist. Call daily.';

-- ============================================================================
-- 7. LOG MIGRATION IN DEFCON TRANSITIONS
-- ============================================================================

INSERT INTO fhq_governance.defcon_transitions (
    transition_id,
    from_level,
    to_level,
    transition_type,
    reason,
    authorized_by,
    authorization_method,
    evidence_bundle,
    transition_timestamp,
    created_at
) VALUES (
    gen_random_uuid(),
    'ORANGE'::defcon_level,
    'ORANGE'::defcon_level,
    'RESET',
    'CEO-DIR-2026-128 DAY43: Skill segmentation and prediction blacklist installed. '
    || 'Honest skill assessment: SKILLED/WEAK_POSITIVE/WEAK_NEGATIVE/ANTI_PREDICTIVE tiers.',
    'STIG',
    'CEO',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-128',
        'day', 'DAY43',
        'action', 'SKILL_SEGMENTATION_AND_BLACKLIST',
        'materialized_view_created', 'fhq_research.skill_segmentation',
        'table_created', 'fhq_governance.prediction_blacklist',
        'function_created', 'fhq_governance.is_asset_blacklisted',
        'view_created', 'fhq_research.skill_summary'
    ),
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================
--
-- 1. Check skill segmentation:
-- SELECT * FROM fhq_research.skill_segmentation ORDER BY avg_fss;
--
-- 2. Check skill summary:
-- SELECT * FROM fhq_research.skill_summary;
--
-- 3. Check blacklist:
-- SELECT * FROM fhq_governance.prediction_blacklist;
--
-- 4. Test blacklist function:
-- SELECT fhq_governance.is_asset_blacklisted('BTC-USD');
-- ============================================================================
