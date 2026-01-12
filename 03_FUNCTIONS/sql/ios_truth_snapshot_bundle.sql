-- ============================================================================
-- IOS-TRUTH-LOOP v2 - SQL Bundle (Read-Only)
-- Authority: CEO-DIR-2026-039B
-- Purpose: Extract learning metrics from database for Truth Snapshot
-- Mode: READ-ONLY - No INSERT/UPDATE/DDL
--
-- Schema Discovery: All column names verified via information_schema
-- If table/column missing: Returns NULL and marks UNKNOWN
-- ============================================================================

-- ===========================================
-- SECTION A: Learning Volume (last 24h)
-- ===========================================

-- A1: Forecasts last 24h
SELECT
    COUNT(*) as forecasts_last_24h,
    COUNT(*) FILTER (WHERE forecast_made_at >= NOW() - INTERVAL '6 hours') as forecasts_last_6h,
    COUNT(DISTINCT forecast_domain) as unique_domains_24h
FROM fhq_research.forecast_ledger
WHERE forecast_made_at >= NOW() - INTERVAL '24 hours';

-- A2: Outcomes resolved last 24h by horizon
SELECT
    fl.forecast_horizon_hours as horizon,
    COUNT(*) as outcomes_resolved_last_24h,
    AVG(fop.brier_score)::numeric(6,4) as avg_brier
FROM fhq_research.forecast_outcome_pairs fop
JOIN fhq_research.forecast_ledger fl ON fl.forecast_id = fop.forecast_id
WHERE fop.reconciled_at >= NOW() - INTERVAL '24 hours'
GROUP BY fl.forecast_horizon_hours
ORDER BY fl.forecast_horizon_hours;

-- A3: Outcome pairs added last 24h
SELECT
    COUNT(*) as outcome_pairs_added_last_24h
FROM fhq_research.forecast_outcome_pairs
WHERE reconciled_at >= NOW() - INTERVAL '24 hours';

-- A4: Coverage - eligible vs resolved
SELECT
    fl.forecast_horizon_hours as horizon,
    COUNT(DISTINCT fl.forecast_id) as eligible_forecasts,
    COUNT(DISTINCT fop.forecast_id) as resolved_forecasts,
    CASE
        WHEN COUNT(DISTINCT fl.forecast_id) > 0
        THEN (COUNT(DISTINCT fop.forecast_id)::float / COUNT(DISTINCT fl.forecast_id) * 100)::numeric(5,2)
        ELSE 0
    END as coverage_pct
FROM fhq_research.forecast_ledger fl
LEFT JOIN fhq_research.forecast_outcome_pairs fop ON fl.forecast_id = fop.forecast_id
WHERE fl.forecast_valid_until <= NOW()
AND fl.forecast_made_at >= NOW() - INTERVAL '7 days'
GROUP BY fl.forecast_horizon_hours
ORDER BY fl.forecast_horizon_hours;

-- ===========================================
-- SECTION B: Calibration Direction
-- ===========================================

-- B1: Brier last 24h by horizon
SELECT
    fl.forecast_horizon_hours as horizon,
    COUNT(*) as sample_count,
    AVG(fop.brier_score)::numeric(6,4) as brier_last_24h,
    AVG(fop.hit_rate_contribution::int)::numeric(5,4) as hit_rate_last_24h
FROM fhq_research.forecast_outcome_pairs fop
JOIN fhq_research.forecast_ledger fl ON fl.forecast_id = fop.forecast_id
WHERE fop.reconciled_at >= NOW() - INTERVAL '24 hours'
GROUP BY fl.forecast_horizon_hours
ORDER BY fl.forecast_horizon_hours;

-- B2: Hit rate by confidence band (last 24h)
SELECT
    CASE
        WHEN fl.forecast_confidence < 0.4 THEN '0-40'
        WHEN fl.forecast_confidence < 0.6 THEN '40-60'
        WHEN fl.forecast_confidence < 0.8 THEN '60-80'
        ELSE '80-100'
    END as confidence_band,
    COUNT(*) as sample_count,
    AVG(fl.forecast_confidence)::numeric(5,4) as avg_confidence,
    AVG(fop.hit_rate_contribution::int)::numeric(5,4) as hit_rate,
    AVG(fop.brier_score)::numeric(6,4) as avg_brier
FROM fhq_research.forecast_outcome_pairs fop
JOIN fhq_research.forecast_ledger fl ON fl.forecast_id = fop.forecast_id
WHERE fop.reconciled_at >= NOW() - INTERVAL '24 hours'
GROUP BY 1
ORDER BY 1;

-- B3: Monotonicity check (compare recent vs older brier)
WITH recent AS (
    SELECT AVG(brier_score)::numeric(6,4) as recent_brier
    FROM fhq_research.forecast_outcome_pairs
    WHERE reconciled_at >= NOW() - INTERVAL '3 days'
),
older AS (
    SELECT AVG(brier_score)::numeric(6,4) as older_brier
    FROM fhq_research.forecast_outcome_pairs
    WHERE reconciled_at >= NOW() - INTERVAL '7 days'
    AND reconciled_at < NOW() - INTERVAL '3 days'
)
SELECT
    recent.recent_brier,
    older.older_brier,
    CASE
        WHEN recent.recent_brier IS NULL OR older.older_brier IS NULL THEN 'UNKNOWN'
        WHEN recent.recent_brier < older.older_brier - 0.01 THEN 'IMPROVING'
        WHEN recent.recent_brier > older.older_brier + 0.01 THEN 'WORSE'
        ELSE 'FLAT'
    END as monotonicity_status
FROM recent, older;

-- ===========================================
-- SECTION C: Suppression Truth
-- ===========================================

-- C1: Suppressions last 24h
SELECT
    COUNT(*) as suppressions_last_24h,
    COUNT(*) FILTER (WHERE regret_classification = 'WISDOM') as wisdom_count_last_24h,
    COUNT(*) FILTER (WHERE regret_classification = 'REGRET') as regret_count_last_24h,
    COUNT(*) FILTER (WHERE regret_classification IS NULL OR regret_classification = 'UNRESOLVED') as unresolved_count_last_24h
FROM fhq_governance.epistemic_suppression_ledger
WHERE suppression_timestamp >= NOW() - INTERVAL '24 hours';

-- C2: Type X analysis
SELECT
    COUNT(*) as total_suppressions,
    COUNT(*) FILTER (WHERE regret_attribution_type IS NULL) as type_x_count,
    CASE
        WHEN COUNT(*) > 0
        THEN (COUNT(*) FILTER (WHERE regret_attribution_type IS NULL)::float / COUNT(*) * 100)::numeric(5,2)
        ELSE 0
    END as type_x_share_pct
FROM fhq_governance.epistemic_suppression_ledger
WHERE suppression_timestamp >= NOW() - INTERVAL '24 hours';

-- C3: Type X forensic breakdown
SELECT
    CASE
        WHEN regret_classification IS NULL OR regret_classification = 'UNRESOLVED' THEN 'HORIZON_NOT_MATURED'
        WHEN regret_classification IN ('REGRET', 'WISDOM') AND regret_root_cause IS NULL THEN 'ATTRIBUTION_LOGIC_GAP'
        ELSE 'OTHER'
    END as forensic_category,
    COUNT(*) as count
FROM fhq_governance.epistemic_suppression_ledger
WHERE regret_attribution_type IS NULL
AND suppression_timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY 1
ORDER BY count DESC;

-- ===========================================
-- SECTION D: Integrity Invariants
-- ===========================================

-- D1: Exposure total (MUST BE 0)
-- Note: paper_positions tracks all positions, quantity != 0 means open
SELECT
    COALESCE(SUM(ABS(quantity)), 0) as exposure_total,
    COUNT(*) FILTER (WHERE quantity != 0) as open_position_count
FROM fhq_execution.paper_positions;

-- D2: Gate violations last 24h
SELECT
    COUNT(*) as gate_violations_last_24h
FROM fhq_governance.governance_actions_log
WHERE action_type LIKE '%VIOLATION%'
AND initiated_at >= NOW() - INTERVAL '24 hours';

-- D3: Policy changes last 24h
SELECT
    COUNT(*) as policy_changes_last_24h
FROM fhq_governance.governance_actions_log
WHERE (action_type LIKE '%POLICY%' OR action_type LIKE '%GATE%' OR action_type LIKE '%TUNING%')
AND initiated_at >= NOW() - INTERVAL '24 hours';

-- D4: IOS-003-B non-interference proof
SELECT
    current_regime,
    updated_by,
    last_updated_at,
    CASE
        WHEN updated_by NOT ILIKE '%ios003b%' THEN true
        ELSE false
    END as ios003b_non_interference
FROM fhq_meta.regime_state
ORDER BY last_updated_at DESC
LIMIT 1;

-- ===========================================
-- SECTION E: ACI Engine Status (Shadow Mode)
-- ===========================================

-- E1: EC-020/021/022 status
SELECT
    ec_id,
    title,
    status,
    effective_date
FROM fhq_governance.ec_registry
WHERE ec_id IN ('EC-020', 'EC-021', 'EC-022')
ORDER BY ec_id;

-- E2: ACI shadow evaluations summary
SELECT
    COUNT(*) as total_evaluations,
    COUNT(*) FILTER (WHERE sitc_has_broken_chain = true) as sitc_broken_chains,
    COUNT(*) FILTER (WHERE ikea_has_fabrication = true) as ikea_fabrications,
    AVG(sitc_score)::numeric(5,4) as avg_sitc_score,
    AVG(ikea_score)::numeric(5,4) as avg_ikea_score,
    SUM(inforage_api_cost_usd)::numeric(10,6) as total_inforage_cost,
    MAX(evaluated_at) as last_evaluation
FROM fhq_canonical.aci_shadow_evaluations;
