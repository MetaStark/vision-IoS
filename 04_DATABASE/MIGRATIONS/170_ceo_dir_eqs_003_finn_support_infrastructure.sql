-- ============================================================================
-- Migration 170: CEO-DIR-2025-EQS-003 - FINN Support Infrastructure
-- ============================================================================
-- Directive: CEO-DIR-2025-EQS-003
-- Status: CEO APPROVED
-- Scope: Read-only support infrastructure for EQS redesign
--
-- APPROVED ACTIONS:
--   1. FINN EQS Sandbox (read-only formula testing)
--   2. Cross-Sectional Ranking View (asset × regime percentiles)
--   3. Automated EQS Collapse Detection (VEGA alert trigger)
--
-- NOT APPROVED:
--   - Regime classifier changes
--   - EQS activation
--   - Temporary threshold overrides
--
-- Principle: "Fix the truth first. Speed comes after."
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Cross-Sectional Ranking View
-- ============================================================================
-- Provides FINN with current percentile rank structure for analysis
-- Read-only view, no production impact

CREATE OR REPLACE VIEW fhq_canonical.v_eqs_cross_sectional_rank AS
SELECT
    gn.needle_id,
    gn.target_asset,
    gn.regime_technical,
    gn.eqs_score,
    gn.hypothesis_title,
    gn.created_at,
    ss.current_state,
    -- Percentile rank within asset × regime partition
    ROUND(
        PERCENT_RANK() OVER (
            PARTITION BY gn.target_asset, gn.regime_technical
            ORDER BY gn.eqs_score DESC
        )::numeric, 4
    ) as percentile_rank,
    -- Dense rank for tie-handling
    DENSE_RANK() OVER (
        PARTITION BY gn.target_asset, gn.regime_technical
        ORDER BY gn.eqs_score DESC
    ) as dense_rank,
    -- Count within partition
    COUNT(*) OVER (
        PARTITION BY gn.target_asset, gn.regime_technical
    ) as partition_size
FROM fhq_canonical.golden_needles gn
JOIN fhq_canonical.g5_signal_state ss ON gn.needle_id = ss.needle_id
WHERE ss.current_state = 'DORMANT';

COMMENT ON VIEW fhq_canonical.v_eqs_cross_sectional_rank IS
'CEO-DIR-2025-EQS-003: Cross-sectional ranking view for FINN EQS analysis. Read-only.';

-- ============================================================================
-- STEP 2: Regime Baseline Table (for future z-score calculations)
-- ============================================================================
-- Stores rolling regime baselines for deviation-based scoring

CREATE TABLE IF NOT EXISTS fhq_canonical.eqs_regime_baseline (
    baseline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Segmentation
    target_asset TEXT NOT NULL,
    regime TEXT NOT NULL,

    -- Baseline statistics
    baseline_mean NUMERIC(5,4) NOT NULL,
    baseline_std NUMERIC(5,4) NOT NULL,
    baseline_median NUMERIC(5,4),
    sample_size INTEGER NOT NULL,

    -- Validity period
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ,

    -- Governance
    computed_by TEXT NOT NULL DEFAULT 'STIG',
    is_active BOOLEAN DEFAULT TRUE,

    CONSTRAINT eqs_regime_baseline_unique UNIQUE (target_asset, regime, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_eqs_regime_baseline_active
ON fhq_canonical.eqs_regime_baseline(target_asset, regime) WHERE is_active = TRUE;

COMMENT ON TABLE fhq_canonical.eqs_regime_baseline IS
'CEO-DIR-2025-EQS-003: Regime baselines for z-score/deviation-based EQS calculations.';

-- ============================================================================
-- STEP 3: FINN EQS Sandbox Function
-- ============================================================================
-- Allows FINN to test EQS formulas against live data without production impact
-- Returns distribution statistics for proposed formula

CREATE OR REPLACE FUNCTION fhq_canonical.finn_eqs_sandbox(
    p_formula_description TEXT,
    p_sample_limit INTEGER DEFAULT 500
)
RETURNS TABLE (
    formula_description TEXT,
    sample_size INTEGER,
    current_min_eqs NUMERIC,
    current_max_eqs NUMERIC,
    current_mean_eqs NUMERIC,
    current_median_eqs NUMERIC,
    current_std NUMERIC,
    current_p05 NUMERIC,
    current_p10 NUMERIC,
    current_p25 NUMERIC,
    current_p50 NUMERIC,
    current_p75 NUMERIC,
    current_p90 NUMERIC,
    current_p95 NUMERIC,
    pct_above_085 NUMERIC,
    pct_above_090 NUMERIC,
    pct_above_095 NUMERIC,
    regime_distribution JSONB,
    asset_distribution JSONB,
    sandbox_timestamp TIMESTAMPTZ
) AS $$
BEGIN
    -- Log sandbox usage for audit
    INSERT INTO fhq_governance.governance_actions_log (
        action_id,
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        initiated_at,
        decision,
        decision_rationale,
        metadata,
        agent_id,
        timestamp
    ) VALUES (
        gen_random_uuid(),
        'FINN_EQS_SANDBOX_INVOKED',
        p_formula_description,
        'EQS_FORMULA_TEST',
        'FINN',
        NOW(),
        'SANDBOX_RUN',
        'FINN testing EQS formula per CEO-DIR-2025-EQS-003',
        jsonb_build_object(
            'formula_description', p_formula_description,
            'sample_limit', p_sample_limit,
            'directive', 'CEO-DIR-2025-EQS-003'
        ),
        'FINN',
        NOW()
    );

    -- Return current distribution statistics
    RETURN QUERY
    WITH sample AS (
        SELECT
            gn.needle_id,
            gn.target_asset,
            gn.regime_technical,
            gn.eqs_score
        FROM fhq_canonical.golden_needles gn
        JOIN fhq_canonical.g5_signal_state ss ON gn.needle_id = ss.needle_id
        WHERE ss.current_state = 'DORMANT'
        ORDER BY gn.created_at DESC
        LIMIT p_sample_limit
    ),
    stats AS (
        SELECT
            COUNT(*)::INTEGER as cnt,
            MIN(eqs_score) as min_eqs,
            MAX(eqs_score) as max_eqs,
            AVG(eqs_score) as mean_eqs,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY eqs_score) as median_eqs,
            STDDEV(eqs_score) as std_dev,
            PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY eqs_score) as p05,
            PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY eqs_score) as p10,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY eqs_score) as p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY eqs_score) as p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY eqs_score) as p75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY eqs_score) as p90,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY eqs_score) as p95,
            ROUND(100.0 * SUM(CASE WHEN eqs_score >= 0.85 THEN 1 ELSE 0 END) / COUNT(*), 2) as above_085,
            ROUND(100.0 * SUM(CASE WHEN eqs_score >= 0.90 THEN 1 ELSE 0 END) / COUNT(*), 2) as above_090,
            ROUND(100.0 * SUM(CASE WHEN eqs_score >= 0.95 THEN 1 ELSE 0 END) / COUNT(*), 2) as above_095
        FROM sample
    ),
    regime_dist AS (
        SELECT jsonb_object_agg(
            COALESCE(regime_technical, 'NULL'),
            cnt
        ) as dist
        FROM (
            SELECT regime_technical, COUNT(*) as cnt
            FROM sample
            GROUP BY regime_technical
        ) r
    ),
    asset_dist AS (
        SELECT jsonb_object_agg(target_asset, cnt) as dist
        FROM (
            SELECT target_asset, COUNT(*) as cnt
            FROM sample
            GROUP BY target_asset
        ) a
    )
    SELECT
        p_formula_description,
        stats.cnt,
        ROUND(stats.min_eqs::numeric, 4),
        ROUND(stats.max_eqs::numeric, 4),
        ROUND(stats.mean_eqs::numeric, 4),
        ROUND(stats.median_eqs::numeric, 4),
        ROUND(stats.std_dev::numeric, 6),
        ROUND(stats.p05::numeric, 4),
        ROUND(stats.p10::numeric, 4),
        ROUND(stats.p25::numeric, 4),
        ROUND(stats.p50::numeric, 4),
        ROUND(stats.p75::numeric, 4),
        ROUND(stats.p90::numeric, 4),
        ROUND(stats.p95::numeric, 4),
        stats.above_085,
        stats.above_090,
        stats.above_095,
        regime_dist.dist,
        asset_dist.dist,
        NOW()
    FROM stats, regime_dist, asset_dist;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_canonical.finn_eqs_sandbox IS
'CEO-DIR-2025-EQS-003: Read-only sandbox for FINN to test EQS formula concepts. Returns current distribution statistics.';

-- ============================================================================
-- STEP 4: Automated EQS Collapse Detection
-- ============================================================================
-- Trigger VEGA alert when distribution collapses (>50% above threshold)

CREATE OR REPLACE FUNCTION fhq_canonical.detect_eqs_collapse()
RETURNS TRIGGER AS $$
BEGIN
    -- Check for collapse conditions
    IF NEW.pct_above_threshold > 50.0 THEN
        -- Log VEGA alert
        INSERT INTO fhq_governance.governance_actions_log (
            action_id,
            action_type,
            action_target,
            action_target_type,
            initiated_by,
            initiated_at,
            decision,
            decision_rationale,
            metadata,
            agent_id,
            timestamp
        ) VALUES (
            gen_random_uuid(),
            'EQS_COLLAPSE_DETECTED',
            NEW.snapshot_id::TEXT,
            'EQS_DISTRIBUTION',
            'STIG',
            NOW(),
            'VEGA_ALERT_TRIGGERED',
            'EQS distribution collapsed: ' || NEW.pct_above_threshold || '% above threshold (max 50%)',
            jsonb_build_object(
                'snapshot_id', NEW.snapshot_id,
                'snapshot_date', NEW.snapshot_date,
                'asset', NEW.asset,
                'regime', NEW.regime,
                'signal_count', NEW.signal_count,
                'pct_above_threshold', NEW.pct_above_threshold,
                'active_threshold', NEW.active_threshold,
                'alert_level', CASE
                    WHEN NEW.pct_above_threshold > 90 THEN 'CRITICAL'
                    WHEN NEW.pct_above_threshold > 75 THEN 'HIGH'
                    ELSE 'MEDIUM'
                END,
                'directive', 'CEO-DIR-2025-EQS-003'
            ),
            'STIG',
            NOW()
        );

        -- Mark snapshot as collapsed
        NEW.distribution_collapsed := TRUE;
        NEW.collapse_reason := 'AUTO-DETECTED: ' ||
            ROUND(NEW.pct_above_threshold, 1) || '% above threshold (max 50%)';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on snapshot insert/update
DROP TRIGGER IF EXISTS trg_eqs_collapse_detection ON fhq_canonical.eqs_distribution_snapshots;
CREATE TRIGGER trg_eqs_collapse_detection
    BEFORE INSERT OR UPDATE ON fhq_canonical.eqs_distribution_snapshots
    FOR EACH ROW
    EXECUTE FUNCTION fhq_canonical.detect_eqs_collapse();

COMMENT ON FUNCTION fhq_canonical.detect_eqs_collapse IS
'CEO-DIR-2025-EQS-003: Automated collapse detection trigger. Alerts VEGA when distribution degrades.';

-- ============================================================================
-- STEP 5: Regime Diversity Check View
-- ============================================================================
-- Surfaces the regime classifier dependency issue for FINN

CREATE OR REPLACE VIEW fhq_canonical.v_regime_diversity_status AS
WITH regime_counts AS (
    SELECT
        COALESCE(gn.regime_technical, 'NULL') as regime,
        COUNT(*) as signal_count,
        MIN(gn.created_at) as earliest_signal,
        MAX(gn.created_at) as latest_signal
    FROM fhq_canonical.golden_needles gn
    JOIN fhq_canonical.g5_signal_state ss ON gn.needle_id = ss.needle_id
    WHERE ss.current_state = 'DORMANT'
    GROUP BY gn.regime_technical
),
total AS (
    SELECT SUM(signal_count) as total_count FROM regime_counts
)
SELECT
    rc.regime,
    rc.signal_count,
    ROUND(100.0 * rc.signal_count / t.total_count, 2) as pct_of_total,
    rc.earliest_signal,
    rc.latest_signal,
    CASE
        WHEN (SELECT COUNT(DISTINCT regime) FROM regime_counts) < 3
        THEN 'COLLAPSED'
        WHEN (SELECT MAX(100.0 * signal_count / t.total_count) FROM regime_counts, total t) > 80
        THEN 'SKEWED'
        ELSE 'HEALTHY'
    END as diversity_status,
    CASE
        WHEN (SELECT COUNT(DISTINCT regime) FROM regime_counts) < 3
        THEN 'EQS regime-sensitivity BLOCKED until classifier produces BULL/BEAR/NEUTRAL variance'
        ELSE 'Regime diversity sufficient for EQS validation'
    END as finn_guidance
FROM regime_counts rc, total t
ORDER BY rc.signal_count DESC;

COMMENT ON VIEW fhq_canonical.v_regime_diversity_status IS
'CEO-DIR-2025-EQS-003: Surfaces regime classifier dependency for FINN. Shows diversity status.';

-- ============================================================================
-- STEP 6: Compute Initial Regime Baseline (for z-score reference)
-- ============================================================================

INSERT INTO fhq_canonical.eqs_regime_baseline (
    target_asset,
    regime,
    baseline_mean,
    baseline_std,
    baseline_median,
    sample_size,
    computed_by
)
SELECT
    gn.target_asset,
    COALESCE(gn.regime_technical, 'UNKNOWN'),
    ROUND(AVG(gn.eqs_score)::numeric, 4),
    ROUND(COALESCE(STDDEV(gn.eqs_score), 0)::numeric, 4),
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gn.eqs_score)::numeric, 4),
    COUNT(*)::INTEGER,
    'STIG'
FROM fhq_canonical.golden_needles gn
JOIN fhq_canonical.g5_signal_state ss ON gn.needle_id = ss.needle_id
WHERE ss.current_state = 'DORMANT'
GROUP BY gn.target_asset, gn.regime_technical
ON CONFLICT (target_asset, regime, valid_from) DO NOTHING;

-- ============================================================================
-- STEP 7: Log Migration Completion
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'MIGRATION_DEPLOYED',
    '170_ceo_dir_eqs_003_finn_support_infrastructure',
    'MIGRATION',
    'STIG',
    NOW(),
    'COMPLETED',
    'CEO-DIR-2025-EQS-003: FINN Support Infrastructure deployed',
    jsonb_build_object(
        'directive_id', 'CEO-DIR-2025-EQS-003',
        'approved_items', jsonb_build_array(
            'FINN EQS Sandbox Function',
            'Cross-Sectional Ranking View',
            'Automated EQS Collapse Detection',
            'Regime Diversity Status View',
            'Regime Baseline Table'
        ),
        'not_approved', jsonb_build_array(
            'Regime classifier changes',
            'EQS activation',
            'Temporary threshold overrides'
        ),
        'principle', 'Fix the truth first. Speed comes after.'
    ),
    'STIG',
    NOW()
);

COMMIT;
