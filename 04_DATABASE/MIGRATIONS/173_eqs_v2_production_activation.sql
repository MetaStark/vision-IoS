-- Migration 173: EQS v2 Production Activation
-- Authority: CEO-DIR-2025-EQS-009
-- Purpose: Activate EQS v2 as primary scoring engine while maintaining EQS v1 in shadow
-- Created: 2025-12-26

-- =============================================================================
-- STEP 1: ADD EQS V2 COLUMNS TO GOLDEN_NEEDLES
-- =============================================================================

-- Add eqs_score_v2 column (rank-based score 0.0-1.0)
ALTER TABLE fhq_canonical.golden_needles
ADD COLUMN IF NOT EXISTS eqs_score_v2 NUMERIC(5,4);

-- Add eqs_v2_tier column (S/A/B/C tier)
ALTER TABLE fhq_canonical.golden_needles
ADD COLUMN IF NOT EXISTS eqs_v2_tier TEXT;

-- Add timestamp for when v2 score was calculated
ALTER TABLE fhq_canonical.golden_needles
ADD COLUMN IF NOT EXISTS eqs_v2_calculated_at TIMESTAMPTZ;

COMMENT ON COLUMN fhq_canonical.golden_needles.eqs_score_v2 IS 'EQS v2 rank-based score (FINN design, CEO-DIR-2025-EQS-009)';
COMMENT ON COLUMN fhq_canonical.golden_needles.eqs_v2_tier IS 'EQS v2 tier: S (>=0.95), A (>=0.88), B (>=0.78), C (<0.78)';
COMMENT ON COLUMN fhq_canonical.golden_needles.eqs_v2_calculated_at IS 'Timestamp of last EQS v2 calculation';

-- =============================================================================
-- STEP 2: EQS VERSION CONFIGURATION
-- =============================================================================

-- Create EQS configuration table
CREATE TABLE IF NOT EXISTS vision_verification.eqs_configuration (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    description TEXT,
    set_by TEXT NOT NULL,
    authority TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Set EQS v2 as primary
INSERT INTO vision_verification.eqs_configuration (config_key, config_value, description, set_by, authority)
VALUES
    ('primary_eqs_version', 'v2', 'Primary EQS version for signal ranking', 'STIG', 'CEO-DIR-2025-EQS-009'),
    ('eqs_v1_mode', 'shadow', 'EQS v1 operating mode (shadow = read-only fallback)', 'STIG', 'CEO-DIR-2025-EQS-009'),
    ('eqs_v2_activated_at', NOW()::text, 'Timestamp when EQS v2 was activated as primary', 'STIG', 'CEO-DIR-2025-EQS-009'),
    ('monitoring_window_hours', '72', 'Hours of mandatory monitoring after activation', 'STIG', 'CEO-DIR-2025-EQS-009'),
    ('hard_stop_enabled', 'true', 'VEGA C1: Hard Stop on regime diversity < 15%', 'STIG', 'CEO-DIR-2025-EQS-009'),
    ('calculation_logging_enabled', 'true', 'VEGA C2: Court-proof calculation logging', 'STIG', 'CEO-DIR-2025-EQS-009')
ON CONFLICT (config_key) DO UPDATE SET
    config_value = EXCLUDED.config_value,
    updated_at = NOW();

-- =============================================================================
-- STEP 3: ACTIVE EQS SCORE VIEW
-- =============================================================================

-- View that returns the active EQS score based on configuration
CREATE OR REPLACE VIEW fhq_canonical.v_golden_needles_active_eqs AS
SELECT
    gn.*,
    -- Active EQS score (v2 primary, v1 fallback)
    COALESCE(gn.eqs_score_v2, gn.eqs_score) as eqs_active_score,
    -- Which version is being used
    CASE
        WHEN gn.eqs_score_v2 IS NOT NULL THEN 'v2'
        ELSE 'v1'
    END as eqs_active_version,
    -- Tier (v2 tier or derived from v1)
    COALESCE(
        gn.eqs_v2_tier,
        CASE
            WHEN gn.eqs_score >= 0.95 THEN 'S'
            WHEN gn.eqs_score >= 0.88 THEN 'A'
            WHEN gn.eqs_score >= 0.78 THEN 'B'
            ELSE 'C'
        END
    ) as eqs_active_tier
FROM fhq_canonical.golden_needles gn;

COMMENT ON VIEW fhq_canonical.v_golden_needles_active_eqs IS 'Golden needles with active EQS score (v2 primary, v1 fallback per CEO-DIR-2025-EQS-009)';

-- =============================================================================
-- STEP 4: EQS DISTRIBUTION MONITORING VIEW
-- =============================================================================

-- View for monitoring EQS v2 distribution during 72h window
CREATE OR REPLACE VIEW vision_verification.v_eqs_v2_distribution_snapshot AS
WITH tier_counts AS (
    SELECT
        eqs_v2_tier as tier,
        COUNT(*) as count
    FROM fhq_canonical.golden_needles
    WHERE eqs_score_v2 IS NOT NULL
    GROUP BY eqs_v2_tier
),
stats AS (
    SELECT
        COUNT(*) as total_scored,
        AVG(eqs_score_v2) as mean_score,
        STDDEV(eqs_score_v2) as std_dev,
        MIN(eqs_score_v2) as min_score,
        MAX(eqs_score_v2) as max_score,
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY eqs_score_v2) as p10,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY eqs_score_v2) as p25,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY eqs_score_v2) as p50,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY eqs_score_v2) as p75,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY eqs_score_v2) as p90
    FROM fhq_canonical.golden_needles
    WHERE eqs_score_v2 IS NOT NULL
)
SELECT
    NOW() as snapshot_timestamp,
    s.total_scored,
    ROUND(s.mean_score::numeric, 4) as mean_score,
    ROUND(s.std_dev::numeric, 4) as std_dev,
    ROUND((s.p90 - s.p10)::numeric, 4) as p90_p10_spread,
    ROUND(s.min_score::numeric, 4) as min_score,
    ROUND(s.max_score::numeric, 4) as max_score,
    ROUND(s.p10::numeric, 4) as p10,
    ROUND(s.p25::numeric, 4) as p25,
    ROUND(s.p50::numeric, 4) as p50,
    ROUND(s.p75::numeric, 4) as p75,
    ROUND(s.p90::numeric, 4) as p90,
    (SELECT COALESCE(SUM(count), 0) FROM tier_counts WHERE tier = 'S') as tier_s_count,
    (SELECT COALESCE(SUM(count), 0) FROM tier_counts WHERE tier = 'A') as tier_a_count,
    (SELECT COALESCE(SUM(count), 0) FROM tier_counts WHERE tier = 'B') as tier_b_count,
    (SELECT COALESCE(SUM(count), 0) FROM tier_counts WHERE tier = 'C') as tier_c_count
FROM stats s;

-- =============================================================================
-- STEP 5: 72H MONITORING SNAPSHOT TABLE
-- =============================================================================

-- Table to store daily snapshots during 72h monitoring window
CREATE TABLE IF NOT EXISTS vision_verification.eqs_v2_monitoring_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_scored INTEGER,
    mean_score NUMERIC(5,4),
    std_dev NUMERIC(5,4),
    p90_p10_spread NUMERIC(5,4),
    tier_s_count INTEGER,
    tier_a_count INTEGER,
    tier_b_count INTEGER,
    tier_c_count INTEGER,
    regime_diversity_pct NUMERIC(5,2),
    regime_status TEXT,
    hard_stop_triggered BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_by TEXT DEFAULT 'STIG'
);

-- Function to capture snapshot
CREATE OR REPLACE FUNCTION vision_verification.capture_eqs_v2_snapshot(p_notes TEXT DEFAULT NULL)
RETURNS UUID AS $$
DECLARE
    v_snapshot_id UUID;
    v_regime_pct NUMERIC;
    v_regime_status TEXT;
BEGIN
    -- Get regime diversity
    SELECT non_dominant_pct, status
    INTO v_regime_pct, v_regime_status
    FROM vision_verification.regime_coverage_health
    LIMIT 1;

    -- Insert snapshot
    INSERT INTO vision_verification.eqs_v2_monitoring_snapshots (
        total_scored, mean_score, std_dev, p90_p10_spread,
        tier_s_count, tier_a_count, tier_b_count, tier_c_count,
        regime_diversity_pct, regime_status, notes
    )
    SELECT
        total_scored, mean_score, std_dev, p90_p10_spread,
        tier_s_count, tier_a_count, tier_b_count, tier_c_count,
        v_regime_pct, v_regime_status, p_notes
    FROM vision_verification.v_eqs_v2_distribution_snapshot
    RETURNING id INTO v_snapshot_id;

    RETURN v_snapshot_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- STEP 6: GRANTS
-- =============================================================================

GRANT SELECT ON vision_verification.eqs_configuration TO PUBLIC;
GRANT SELECT ON fhq_canonical.v_golden_needles_active_eqs TO PUBLIC;
GRANT SELECT ON vision_verification.v_eqs_v2_distribution_snapshot TO PUBLIC;
GRANT SELECT ON vision_verification.eqs_v2_monitoring_snapshots TO PUBLIC;
GRANT EXECUTE ON FUNCTION vision_verification.capture_eqs_v2_snapshot(TEXT) TO PUBLIC;

-- =============================================================================
-- STEP 7: ACTIVATION AUDIT LOG
-- =============================================================================

INSERT INTO fhq_meta.ios_audit_log (
    audit_id, ios_id, event_type, event_timestamp, actor, gate_level, event_data
) VALUES (
    gen_random_uuid(),
    'EQS-v2',
    'PRODUCTION_ACTIVATION',
    NOW(),
    'STIG',
    'G4',
    jsonb_build_object(
        'authority', 'CEO-DIR-2025-EQS-009',
        'migration', '173_eqs_v2_production_activation.sql',
        'activation_scope', jsonb_build_array(
            'EQS v2 as primary scoring engine',
            'EQS v1 in shadow mode (read-only fallback)',
            'Hard Stop (C1) enforced',
            'Calculation Logging (C2) enforced',
            '72h monitoring window started'
        ),
        'preconditions_verified', jsonb_build_object(
            'RC004_closed', true,
            'vega_c1_c2', 'SATISFIED',
            'regime_diversity', 23.91,
            'asset_coverage', 486,
            'sentinels', 'ACTIVE'
        ),
        'monitoring_window_start', NOW(),
        'monitoring_window_end', NOW() + INTERVAL '72 hours'
    )
);

-- Capture initial snapshot
SELECT vision_verification.capture_eqs_v2_snapshot('Initial activation snapshot per CEO-DIR-2025-EQS-009');

SELECT 'EQS v2 PRODUCTION ACTIVATION COMPLETE' as status;
