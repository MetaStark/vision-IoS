-- ============================================================================
-- IOS-TRUTH-LOOP v2 - Delta Bundle (Read-Only)
-- Authority: CEO-DIR-2026-039B
-- Purpose: Day-over-day comparison for learning velocity calculation
-- Mode: READ-ONLY - No INSERT/UPDATE/DDL
-- ============================================================================

-- ===========================================
-- DELTA CALCULATION: Last 24h vs Previous 24h
-- ===========================================

-- D1: Forecasts Delta
WITH last_24h AS (
    SELECT COUNT(*) as count
    FROM fhq_research.forecast_ledger
    WHERE forecast_made_at >= NOW() - INTERVAL '24 hours'
),
previous_24h AS (
    SELECT COUNT(*) as count
    FROM fhq_research.forecast_ledger
    WHERE forecast_made_at >= NOW() - INTERVAL '48 hours'
    AND forecast_made_at < NOW() - INTERVAL '24 hours'
)
SELECT
    last_24h.count as forecasts_last_24h,
    previous_24h.count as forecasts_previous_24h,
    last_24h.count - previous_24h.count as forecasts_delta
FROM last_24h, previous_24h;

-- D2: Outcomes Delta (0h + 1h combined)
WITH last_24h AS (
    SELECT COUNT(*) as count
    FROM fhq_research.forecast_outcome_pairs fop
    JOIN fhq_research.forecast_ledger fl ON fl.forecast_id = fop.forecast_id
    WHERE fop.reconciled_at >= NOW() - INTERVAL '24 hours'
    AND fl.forecast_horizon_hours IN (0, 1)
),
previous_24h AS (
    SELECT COUNT(*) as count
    FROM fhq_research.forecast_outcome_pairs fop
    JOIN fhq_research.forecast_ledger fl ON fl.forecast_id = fop.forecast_id
    WHERE fop.reconciled_at >= NOW() - INTERVAL '48 hours'
    AND fop.reconciled_at < NOW() - INTERVAL '24 hours'
    AND fl.forecast_horizon_hours IN (0, 1)
)
SELECT
    last_24h.count as outcomes_0h_1h_last_24h,
    previous_24h.count as outcomes_0h_1h_previous_24h,
    last_24h.count - previous_24h.count as outcomes_0h_1h_delta
FROM last_24h, previous_24h;

-- D3: Brier Delta (all horizons combined)
WITH last_24h AS (
    SELECT AVG(brier_score)::numeric(6,4) as brier
    FROM fhq_research.forecast_outcome_pairs
    WHERE reconciled_at >= NOW() - INTERVAL '24 hours'
),
previous_24h AS (
    SELECT AVG(brier_score)::numeric(6,4) as brier
    FROM fhq_research.forecast_outcome_pairs
    WHERE reconciled_at >= NOW() - INTERVAL '48 hours'
    AND reconciled_at < NOW() - INTERVAL '24 hours'
)
SELECT
    last_24h.brier as brier_last_24h,
    previous_24h.brier as brier_previous_24h,
    CASE
        WHEN last_24h.brier IS NOT NULL AND previous_24h.brier IS NOT NULL
        THEN (last_24h.brier - previous_24h.brier)::numeric(6,4)
        ELSE NULL
    END as brier_delta
FROM last_24h, previous_24h;

-- D4: Type X Share Delta
WITH last_24h AS (
    SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE regret_attribution_type IS NULL) as type_x
    FROM fhq_governance.epistemic_suppression_ledger
    WHERE suppression_timestamp >= NOW() - INTERVAL '24 hours'
),
previous_24h AS (
    SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE regret_attribution_type IS NULL) as type_x
    FROM fhq_governance.epistemic_suppression_ledger
    WHERE suppression_timestamp >= NOW() - INTERVAL '48 hours'
    AND suppression_timestamp < NOW() - INTERVAL '24 hours'
)
SELECT
    CASE WHEN last_24h.total > 0 THEN (last_24h.type_x::float / last_24h.total * 100)::numeric(5,2) ELSE 0 END as type_x_share_last_24h,
    CASE WHEN previous_24h.total > 0 THEN (previous_24h.type_x::float / previous_24h.total * 100)::numeric(5,2) ELSE 0 END as type_x_share_previous_24h,
    CASE
        WHEN last_24h.total > 0 AND previous_24h.total > 0
        THEN ((last_24h.type_x::float / last_24h.total) - (previous_24h.type_x::float / previous_24h.total)) * 100
        ELSE NULL
    END::numeric(5,2) as type_x_share_delta
FROM last_24h, previous_24h;

-- D5: Suppressions Delta
WITH last_24h AS (
    SELECT COUNT(*) as count
    FROM fhq_governance.epistemic_suppression_ledger
    WHERE suppression_timestamp >= NOW() - INTERVAL '24 hours'
),
previous_24h AS (
    SELECT COUNT(*) as count
    FROM fhq_governance.epistemic_suppression_ledger
    WHERE suppression_timestamp >= NOW() - INTERVAL '48 hours'
    AND suppression_timestamp < NOW() - INTERVAL '24 hours'
)
SELECT
    last_24h.count as suppressions_last_24h,
    previous_24h.count as suppressions_previous_24h,
    last_24h.count - previous_24h.count as suppressions_delta
FROM last_24h, previous_24h;

-- ===========================================
-- LEARNING VELOCITY INDEX (LVI) COMPONENTS
-- ===========================================

-- LVI requires:
-- 1. outcomes_acceleration = outcomes_today / outcomes_yesterday (weight: 40%)
-- 2. type_x_improvement = (1 - type_x_today) / (1 - type_x_yesterday) (weight: 30%)
-- 3. brier_improvement = brier_yesterday / brier_today (weight: 30%)
-- LVI > 1.0 = ACCELERATING, = 1.0 = STABLE, < 1.0 = DECELERATING

WITH outcomes AS (
    SELECT
        COUNT(*) FILTER (WHERE reconciled_at >= NOW() - INTERVAL '24 hours') as today,
        COUNT(*) FILTER (WHERE reconciled_at >= NOW() - INTERVAL '48 hours' AND reconciled_at < NOW() - INTERVAL '24 hours') as yesterday
    FROM fhq_research.forecast_outcome_pairs
),
type_x AS (
    SELECT
        CASE WHEN COUNT(*) FILTER (WHERE suppression_timestamp >= NOW() - INTERVAL '24 hours') > 0
             THEN COUNT(*) FILTER (WHERE suppression_timestamp >= NOW() - INTERVAL '24 hours' AND regret_attribution_type IS NULL)::float
                  / COUNT(*) FILTER (WHERE suppression_timestamp >= NOW() - INTERVAL '24 hours')
             ELSE 0 END as share_today,
        CASE WHEN COUNT(*) FILTER (WHERE suppression_timestamp >= NOW() - INTERVAL '48 hours' AND suppression_timestamp < NOW() - INTERVAL '24 hours') > 0
             THEN COUNT(*) FILTER (WHERE suppression_timestamp >= NOW() - INTERVAL '48 hours' AND suppression_timestamp < NOW() - INTERVAL '24 hours' AND regret_attribution_type IS NULL)::float
                  / COUNT(*) FILTER (WHERE suppression_timestamp >= NOW() - INTERVAL '48 hours' AND suppression_timestamp < NOW() - INTERVAL '24 hours')
             ELSE 0 END as share_yesterday
    FROM fhq_governance.epistemic_suppression_ledger
),
brier AS (
    SELECT
        AVG(CASE WHEN reconciled_at >= NOW() - INTERVAL '24 hours' THEN brier_score END) as today,
        AVG(CASE WHEN reconciled_at >= NOW() - INTERVAL '48 hours' AND reconciled_at < NOW() - INTERVAL '24 hours' THEN brier_score END) as yesterday
    FROM fhq_research.forecast_outcome_pairs
)
SELECT
    -- Raw components
    outcomes.today as outcomes_today,
    outcomes.yesterday as outcomes_yesterday,
    type_x.share_today as type_x_share_today,
    type_x.share_yesterday as type_x_share_yesterday,
    brier.today::numeric(6,4) as brier_today,
    brier.yesterday::numeric(6,4) as brier_yesterday,
    -- Component ratios
    CASE WHEN outcomes.yesterday > 0 THEN outcomes.today::float / outcomes.yesterday ELSE NULL END as outcomes_ratio,
    CASE WHEN type_x.share_yesterday < 1 AND type_x.share_today < 1
         THEN (1 - type_x.share_today) / NULLIF(1 - type_x.share_yesterday, 0)
         ELSE NULL END as type_x_ratio,
    CASE WHEN brier.today > 0 THEN brier.yesterday / brier.today ELSE NULL END as brier_ratio,
    -- LVI calculation
    CASE
        WHEN outcomes.yesterday > 0 AND brier.today > 0 AND brier.yesterday > 0
             AND type_x.share_yesterday < 1 AND (1 - type_x.share_yesterday) > 0
        THEN (
            (outcomes.today::float / outcomes.yesterday) * 0.4 +
            ((1 - type_x.share_today) / (1 - type_x.share_yesterday)) * 0.3 +
            (brier.yesterday / brier.today) * 0.3
        )::numeric(5,3)
        ELSE NULL
    END as learning_velocity_index,
    -- Interpretation
    CASE
        WHEN outcomes.yesterday = 0 OR brier.today IS NULL OR brier.yesterday IS NULL THEN 'INSUFFICIENT_DATA'
        WHEN (
            (outcomes.today::float / NULLIF(outcomes.yesterday, 0)) * 0.4 +
            COALESCE((1 - type_x.share_today) / NULLIF(1 - type_x.share_yesterday, 0), 1) * 0.3 +
            COALESCE(brier.yesterday / NULLIF(brier.today, 0), 1) * 0.3
        ) > 1.05 THEN 'ACCELERATING'
        WHEN (
            (outcomes.today::float / NULLIF(outcomes.yesterday, 0)) * 0.4 +
            COALESCE((1 - type_x.share_today) / NULLIF(1 - type_x.share_yesterday, 0), 1) * 0.3 +
            COALESCE(brier.yesterday / NULLIF(brier.today, 0), 1) * 0.3
        ) < 0.95 THEN 'DECELERATING'
        ELSE 'STABLE'
    END as lvi_interpretation
FROM outcomes, type_x, brier;
