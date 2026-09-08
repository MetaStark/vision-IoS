-- Migration 240: CEO-DIR-2026-067 Continuous LDOW Capture & Rolling Learning Metrics
-- Create infrastructure for continuous observation under LDOW
--
-- Authority: CEO-DIR-2026-067
-- Owner: STIG
-- Classification: OBSERVATION_ONLY (not intervention)

BEGIN;

-- =============================================================================
-- 1. LDOW CYCLE METRICS TABLE (Section 3.2)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.ldow_cycle_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ldow_id UUID NOT NULL REFERENCES fhq_governance.learning_delta_observation_window(ldow_id),
    cycle_number INTEGER NOT NULL,

    -- Core metrics
    forecast_count INTEGER NOT NULL DEFAULT 0,
    damped_count INTEGER NOT NULL DEFAULT 0,

    -- Calibration metrics (Section 3.2)
    calibration_error NUMERIC(6,4),
    brier_score NUMERIC(6,4),
    delta_fss NUMERIC(6,4),

    -- Latency metrics (IoS-008)
    p95_latency_ms INTEGER,
    avg_latency_ms INTEGER,

    -- Confidence metrics
    avg_raw_confidence NUMERIC(5,4),
    avg_damped_confidence NUMERIC(5,4),
    avg_dampening_delta NUMERIC(5,4),

    -- Comparison to previous cycle
    calibration_error_delta NUMERIC(6,4),
    brier_score_delta NUMERIC(6,4),

    -- Damper integrity
    damper_version_hash TEXT NOT NULL,
    damper_hash_verified BOOLEAN DEFAULT true,

    -- Timestamps
    cycle_started_at TIMESTAMPTZ NOT NULL,
    cycle_completed_at TIMESTAMPTZ,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(ldow_id, cycle_number)
);

-- =============================================================================
-- 2. LDOW REGIME METRICS (Aggregation per regime)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.ldow_regime_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ldow_id UUID NOT NULL,
    cycle_number INTEGER NOT NULL,
    regime TEXT NOT NULL,

    -- Metrics per regime
    forecast_count INTEGER NOT NULL DEFAULT 0,
    avg_raw_confidence NUMERIC(5,4),
    avg_damped_confidence NUMERIC(5,4),
    avg_dampening_delta NUMERIC(5,4),
    calibration_error NUMERIC(6,4),
    brier_score NUMERIC(6,4),

    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(ldow_id, cycle_number, regime)
);

-- =============================================================================
-- 3. LDOW STRATEGY METRICS (Aggregation per strategy)
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.ldow_strategy_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ldow_id UUID NOT NULL,
    cycle_number INTEGER NOT NULL,
    strategy_id TEXT NOT NULL,

    -- Metrics per strategy
    forecast_count INTEGER NOT NULL DEFAULT 0,
    avg_raw_confidence NUMERIC(5,4),
    avg_damped_confidence NUMERIC(5,4),
    avg_dampening_delta NUMERIC(5,4),

    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(ldow_id, cycle_number, strategy_id)
);

-- =============================================================================
-- 4. INDEXES FOR PERFORMANCE
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_ldow_cycle_metrics_ldow
ON fhq_governance.ldow_cycle_metrics(ldow_id, cycle_number);

CREATE INDEX IF NOT EXISTS idx_ldow_regime_metrics_ldow
ON fhq_governance.ldow_regime_metrics(ldow_id, cycle_number);

CREATE INDEX IF NOT EXISTS idx_ldow_strategy_metrics_ldow
ON fhq_governance.ldow_strategy_metrics(ldow_id, cycle_number);

COMMIT;

-- =============================================================================
-- 5. ROLLING LDOW DASHBOARD VIEW (Section 6)
-- =============================================================================
CREATE OR REPLACE VIEW fhq_governance.v_ldow_rolling_dashboard AS
WITH current_ldow AS (
    SELECT
        ldow_id,
        holdout_id,
        status,
        cycles_completed,
        minimum_cycles,
        baseline_calibration_error,
        baseline_brier_score,
        damper_version_hash as locked_damper_hash,
        started_at
    FROM fhq_governance.learning_delta_observation_window
    WHERE status = 'ACTIVE'
    LIMIT 1
),
cycle_metrics AS (
    SELECT
        cm.*,
        LAG(cm.calibration_error) OVER (ORDER BY cm.cycle_number) as prev_calibration_error,
        LAG(cm.brier_score) OVER (ORDER BY cm.cycle_number) as prev_brier_score
    FROM fhq_governance.ldow_cycle_metrics cm
    JOIN current_ldow cl ON cm.ldow_id = cl.ldow_id
),
capture_stats AS (
    SELECT
        ldow_id,
        cycle_number,
        COUNT(*) as capture_count,
        COUNT(*) FILTER (WHERE raw_confidence IS NOT NULL
                         AND damped_confidence IS NOT NULL
                         AND damper_version_hash IS NOT NULL) as lineage_complete_count
    FROM fhq_governance.ldow_forecast_captures
    GROUP BY ldow_id, cycle_number
)
SELECT
    cl.ldow_id,
    cl.status as ldow_status,
    cl.cycles_completed,
    cl.minimum_cycles,
    cl.baseline_calibration_error,
    cl.baseline_brier_score,
    cl.locked_damper_hash,
    cl.started_at as ldow_started,

    -- Latest cycle info
    cm.cycle_number as current_cycle,
    cm.forecast_count,
    cm.calibration_error as current_calibration_error,
    cm.brier_score as current_brier_score,
    cm.delta_fss,
    cm.p95_latency_ms,

    -- Trends
    cm.calibration_error - cm.prev_calibration_error as calibration_trend,
    cm.brier_score - cm.prev_brier_score as brier_trend,

    -- vs Baseline
    cm.calibration_error - cl.baseline_calibration_error as calibration_vs_baseline,
    cm.brier_score - cl.baseline_brier_score as brier_vs_baseline,

    -- Confidence metrics
    cm.avg_raw_confidence,
    cm.avg_damped_confidence,
    cm.avg_dampening_delta,

    -- Integrity
    cm.damper_hash_verified,

    -- Capture stats
    cs.capture_count,
    cs.lineage_complete_count,
    ROUND((cs.lineage_complete_count::numeric / NULLIF(cs.capture_count, 0) * 100), 1) as lineage_coverage_pct

FROM current_ldow cl
LEFT JOIN cycle_metrics cm ON cm.ldow_id = cl.ldow_id
    AND cm.cycle_number = (SELECT MAX(cycle_number) FROM cycle_metrics)
LEFT JOIN capture_stats cs ON cs.ldow_id = cl.ldow_id
    AND cs.cycle_number = cm.cycle_number;

-- Verification
DO $$
BEGIN
    RAISE NOTICE 'Migration 240 SUCCESS: CEO-DIR-2026-067 infrastructure created';
    RAISE NOTICE 'Tables: ldow_cycle_metrics, ldow_regime_metrics, ldow_strategy_metrics';
    RAISE NOTICE 'View: v_ldow_rolling_dashboard';
END $$;
