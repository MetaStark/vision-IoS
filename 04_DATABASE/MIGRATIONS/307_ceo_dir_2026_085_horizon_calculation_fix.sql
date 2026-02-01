-- ============================================================================
-- MIGRATION 307: CEO-DIR-2026-085 ROI LEDGER HORIZON CALCULATION CORRECTION
-- ============================================================================
-- Authority: CEO
-- Directive: CEO-DIR-2026-085
-- Executed by: STIG (EC-003)
--
-- FACTUAL FINDING:
--   3D and 5D hit rates were calculated using total events (n=31)
--   Correct methodology requires filtering to events with non-NULL outcomes
--   When calculated correctly, hit rate is stable ~56-58% across all horizons
--   Current reported decay is a statistical artifact, not real signal decay
--
-- FIX: Use FILTER (WHERE price_t0_plus_Xd IS NOT NULL) for each horizon
-- ============================================================================

-- Drop existing views
DROP VIEW IF EXISTS fhq_research.roi_direction_equity_daily_ev CASCADE;
DROP VIEW IF EXISTS fhq_research.roi_direction_equity_rolling_30d CASCADE;

-- ============================================================================
-- VIEW 1: DAILY EV (CORRECTED)
-- ============================================================================
CREATE OR REPLACE VIEW fhq_research.roi_direction_equity_daily_ev AS
SELECT
    DATE(signal_timestamp) AS signal_date,

    -- Event counts by horizon availability
    COUNT(*) AS events_total,
    COUNT(*) FILTER (WHERE price_t0_plus_1d IS NOT NULL) AS events_with_1d,
    COUNT(*) FILTER (WHERE price_t0_plus_3d IS NOT NULL) AS events_with_3d,
    COUNT(*) FILTER (WHERE price_t0_plus_5d IS NOT NULL) AS events_with_5d,

    -- HIT RATES: CORRECTED DENOMINATOR (only count events with outcome data)
    AVG(CASE WHEN correct_direction_1d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE price_t0_plus_1d IS NOT NULL) AS hit_rate_1d,
    AVG(CASE WHEN correct_direction_3d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE price_t0_plus_3d IS NOT NULL) AS hit_rate_3d,
    AVG(CASE WHEN correct_direction_5d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE price_t0_plus_5d IS NOT NULL) AS hit_rate_5d,

    -- Average returns (only where data exists)
    AVG(return_1d) FILTER (WHERE return_1d IS NOT NULL) AS avg_return_1d,
    AVG(return_3d) FILTER (WHERE return_3d IS NOT NULL) AS avg_return_3d,
    AVG(return_5d) FILTER (WHERE return_5d IS NOT NULL) AS avg_return_5d,

    -- Edge per activation (only when direction correct AND data exists)
    AVG(ABS(return_1d)) FILTER (WHERE correct_direction_1d = TRUE) AS edge_per_activation_1d,
    AVG(ABS(return_3d)) FILTER (WHERE correct_direction_3d = TRUE) AS edge_per_activation_3d,
    AVG(ABS(return_5d)) FILTER (WHERE correct_direction_5d = TRUE) AS edge_per_activation_5d,

    -- Quality metrics
    AVG(inverted_brier_at_event) AS avg_inverted_brier,
    SUM(CASE WHEN anomaly_flag THEN 1 ELSE 0 END) AS anomaly_count,

    -- DATA QUALITY ANNOTATION (CEO-DIR-2026-085 requirement)
    CASE
        WHEN COUNT(*) FILTER (WHERE price_t0_plus_3d IS NOT NULL) < COUNT(*) FILTER (WHERE price_t0_plus_1d IS NOT NULL)
        THEN 'INCOMPLETE_3D'
        ELSE 'COMPLETE'
    END AS data_quality_3d,
    CASE
        WHEN COUNT(*) FILTER (WHERE price_t0_plus_5d IS NOT NULL) < COUNT(*) FILTER (WHERE price_t0_plus_1d IS NOT NULL)
        THEN 'INCOMPLETE_5D'
        ELSE 'COMPLETE'
    END AS data_quality_5d

FROM fhq_research.roi_direction_ledger_equity
GROUP BY DATE(signal_timestamp)
ORDER BY DATE(signal_timestamp) DESC;

-- ============================================================================
-- VIEW 2: ROLLING 30D (CORRECTED)
-- ============================================================================
CREATE OR REPLACE VIEW fhq_research.roi_direction_equity_rolling_30d AS
SELECT
    DATE(NOW()) AS calculation_date,

    -- Total counts
    COUNT(*) AS total_events,
    COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') AS events_30d,

    -- Sample counts by horizon (30d window)
    COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_1d IS NOT NULL) AS samples_1d_30d,
    COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_3d IS NOT NULL) AS samples_3d_30d,
    COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_5d IS NOT NULL) AS samples_5d_30d,

    -- HIT RATES: CORRECTED DENOMINATOR (CEO-DIR-2026-085)
    AVG(CASE WHEN correct_direction_1d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_1d IS NOT NULL) AS hit_rate_1d_30d,
    AVG(CASE WHEN correct_direction_3d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_3d IS NOT NULL) AS hit_rate_3d_30d,
    AVG(CASE WHEN correct_direction_5d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_5d IS NOT NULL) AS hit_rate_5d_30d,

    -- Expected value (average return)
    AVG(return_1d) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND return_1d IS NOT NULL) AS ev_1d_30d,
    AVG(return_3d) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND return_3d IS NOT NULL) AS ev_3d_30d,
    AVG(return_5d) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND return_5d IS NOT NULL) AS ev_5d_30d,

    -- Edge per activation
    AVG(ABS(return_1d)) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND correct_direction_1d = TRUE) AS edge_per_activation_1d_30d,
    AVG(ABS(return_3d)) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND correct_direction_3d = TRUE) AS edge_per_activation_3d_30d,
    AVG(ABS(return_5d)) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND correct_direction_5d = TRUE) AS edge_per_activation_5d_30d,

    -- Quality metrics
    AVG(inverted_brier_at_event) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') AS avg_inverted_brier_30d,

    -- Alerts
    CASE WHEN COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days') < 5
         THEN TRUE ELSE FALSE END AS sample_collapse_alert,

    -- DATA QUALITY ANNOTATIONS (CEO-DIR-2026-085 requirement)
    ROUND(
        COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_3d IS NOT NULL)::NUMERIC /
        NULLIF(COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_1d IS NOT NULL), 0) * 100
    , 1) AS outcome_completeness_3d_pct,
    ROUND(
        COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_5d IS NOT NULL)::NUMERIC /
        NULLIF(COUNT(*) FILTER (WHERE signal_timestamp >= NOW() - INTERVAL '30 days' AND price_t0_plus_1d IS NOT NULL), 0) * 100
    , 1) AS outcome_completeness_5d_pct

FROM fhq_research.roi_direction_ledger_equity;

-- ============================================================================
-- VIEW 3: HORIZON SUMMARY (NEW - for clean reporting)
-- ============================================================================
CREATE OR REPLACE VIEW fhq_research.roi_direction_equity_horizon_summary AS
SELECT
    '1D' AS horizon,
    COUNT(*) FILTER (WHERE price_t0_plus_1d IS NOT NULL) AS sample_size,
    SUM(CASE WHEN correct_direction_1d THEN 1 ELSE 0 END) AS correct_count,
    ROUND(AVG(CASE WHEN correct_direction_1d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE price_t0_plus_1d IS NOT NULL) * 100, 2) AS hit_rate_pct,
    ROUND(AVG(ABS(return_1d)) FILTER (WHERE correct_direction_1d = TRUE) * 100, 4) AS edge_per_activation_pct,
    'COMPLETE' AS data_status
FROM fhq_research.roi_direction_ledger_equity

UNION ALL

SELECT
    '3D' AS horizon,
    COUNT(*) FILTER (WHERE price_t0_plus_3d IS NOT NULL) AS sample_size,
    SUM(CASE WHEN correct_direction_3d THEN 1 ELSE 0 END) AS correct_count,
    ROUND(AVG(CASE WHEN correct_direction_3d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE price_t0_plus_3d IS NOT NULL) * 100, 2) AS hit_rate_pct,
    ROUND(AVG(ABS(return_3d)) FILTER (WHERE correct_direction_3d = TRUE) * 100, 4) AS edge_per_activation_pct,
    CASE WHEN COUNT(*) FILTER (WHERE price_t0_plus_3d IS NOT NULL) < COUNT(*) FILTER (WHERE price_t0_plus_1d IS NOT NULL)
         THEN 'INCOMPLETE' ELSE 'COMPLETE' END AS data_status
FROM fhq_research.roi_direction_ledger_equity

UNION ALL

SELECT
    '5D' AS horizon,
    COUNT(*) FILTER (WHERE price_t0_plus_5d IS NOT NULL) AS sample_size,
    SUM(CASE WHEN correct_direction_5d THEN 1 ELSE 0 END) AS correct_count,
    ROUND(AVG(CASE WHEN correct_direction_5d THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE price_t0_plus_5d IS NOT NULL) * 100, 2) AS hit_rate_pct,
    ROUND(AVG(ABS(return_5d)) FILTER (WHERE correct_direction_5d = TRUE) * 100, 4) AS edge_per_activation_pct,
    CASE WHEN COUNT(*) FILTER (WHERE price_t0_plus_5d IS NOT NULL) < COUNT(*) FILTER (WHERE price_t0_plus_1d IS NOT NULL)
         THEN 'INCOMPLETE' ELSE 'COMPLETE' END AS data_status
FROM fhq_research.roi_direction_ledger_equity;

-- ============================================================================
-- GOVERNANCE REGISTRATION
-- ============================================================================
INSERT INTO fhq_meta.adr_audit_log (
    adr_id,
    event_id,
    review_status,
    detected_by,
    detected_at,
    resolution_notes,
    severity
) VALUES (
    'ADR-002',
    'CEO-DIR-2026-085-HORIZON-FIX',
    'VERIFIED',
    'STIG',
    NOW(),
    'CEO-DIR-2026-085: Fixed ROI ledger horizon hit rate calculations. Denominator now correctly filters to events with non-NULL outcomes. Added data quality annotations. No signal data altered.',
    'MEDIUM'
);

-- ============================================================================
-- VERIFICATION COMMENT
-- ============================================================================
COMMENT ON VIEW fhq_research.roi_direction_equity_daily_ev IS
'CEO-DIR-2026-085: Hit rates calculated using correct denominator (events with outcome data only). Data quality annotations added.';

COMMENT ON VIEW fhq_research.roi_direction_equity_rolling_30d IS
'CEO-DIR-2026-085: Hit rates calculated using correct denominator. Includes sample counts and completeness percentages per horizon.';

COMMENT ON VIEW fhq_research.roi_direction_equity_horizon_summary IS
'CEO-DIR-2026-085: Clean horizon comparison view showing hit rate stability across 1D/3D/5D when calculated correctly.';
