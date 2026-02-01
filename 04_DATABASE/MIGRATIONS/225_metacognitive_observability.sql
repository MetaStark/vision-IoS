-- ============================================================================
-- Migration 225: Metacognitive Observability Infrastructure
-- ============================================================================
-- Authority: CEO Directive Metacognitive Observability & Audit-Hardening
-- Referanse: ADR-004, ADR-014, IoS-005
-- Classification: G1 Technical Validation (approved by CEO 2026-01-09)
--
-- STIG Implementation Notes:
-- 1. CV (Coefficient of Variation) per regime for juridisk forsvarlighet
-- 2. EVPI Proxy for Information Option Value (respekterer ADR-013)
-- 3. IGR (Information Gain Ratio) for økonomisk perspektiv
-- 4. All views graceful degrade on missing data
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Chain-of-Query Efficiency View (Kognitiv Perspektiv)
-- ============================================================================
-- Unified view for CoQ metrics from inforage_query_log
-- Supports: abort_rate, avg_latency, cost tracking per agent

CREATE OR REPLACE VIEW fhq_governance.v_chain_of_query_efficiency AS
SELECT
    DATE_TRUNC('day', created_at) as query_date,
    querying_agent,
    COUNT(*) as total_queries,
    ROUND(AVG(latency_ms)::numeric, 2) as avg_latency_ms,
    ROUND(COALESCE(SUM(cost_usd), 0)::numeric, 6) as total_cost_usd,
    ROUND(AVG(results_count)::numeric, 2) as avg_results,
    -- Abort detection: queries with 0 results or excessive latency (>5s)
    COUNT(*) FILTER (WHERE results_count = 0 OR latency_ms > 5000) as aborted_queries,
    ROUND(
        (COUNT(*) FILTER (WHERE results_count = 0 OR latency_ms > 5000))::numeric /
        NULLIF(COUNT(*), 0)::numeric,
        4
    ) as abort_rate,
    -- Efficiency score: inverse of abort rate, scaled 0-100
    ROUND(
        (1 - (COUNT(*) FILTER (WHERE results_count = 0 OR latency_ms > 5000))::numeric /
        NULLIF(COUNT(*), 0)::numeric) * 100,
        2
    ) as efficiency_score
FROM fhq_governance.inforage_query_log
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', created_at), querying_agent;

COMMENT ON VIEW fhq_governance.v_chain_of_query_efficiency IS
'CEO Directive: Metakognitiv Observability - Kognitiv Perspektiv.
Tracks Chain-of-Query efficiency, abort rates, and cost per agent.
Source: fhq_governance.inforage_query_log';

-- ============================================================================
-- 2. Regime-Stratified Variance View (Kognitiv Perspektiv - CV per Regime)
-- ============================================================================
-- Coefficient of Variation (CV) = stddev/mean per regime
-- CV is normalized, allowing cross-regime comparison for external auditors

CREATE OR REPLACE VIEW fhq_governance.v_regime_variance_metrics AS
WITH regime_stats AS (
    SELECT
        b.dominant_regime,
        DATE_TRUNC('week', b.created_at) as week,
        COUNT(*) as belief_count,
        AVG(b.belief_confidence) as avg_confidence,
        STDDEV(b.belief_confidence) as stddev_confidence,
        AVG(b.entropy) as avg_entropy,
        STDDEV(b.entropy) as stddev_entropy
    FROM fhq_perception.model_belief_state b
    WHERE b.created_at >= NOW() - INTERVAL '90 days'
    GROUP BY b.dominant_regime, DATE_TRUNC('week', b.created_at)
)
SELECT
    dominant_regime,
    week,
    belief_count,
    ROUND(avg_confidence::numeric, 4) as avg_confidence,
    ROUND(stddev_confidence::numeric, 4) as stddev_confidence,
    -- Coefficient of Variation (CV) = stddev/mean - STIG recommendation
    CASE WHEN avg_confidence > 0.01
         THEN ROUND((stddev_confidence / avg_confidence)::numeric, 4)
         ELSE NULL
    END as confidence_cv,
    ROUND(avg_entropy::numeric, 4) as avg_entropy,
    ROUND(stddev_entropy::numeric, 4) as stddev_entropy,
    CASE WHEN avg_entropy > 0.01
         THEN ROUND((stddev_entropy / avg_entropy)::numeric, 4)
         ELSE NULL
    END as entropy_cv,
    -- Stability indicator: lower CV = more stable learning
    CASE
        WHEN avg_confidence > 0.01 AND (stddev_confidence / avg_confidence) < 0.15 THEN 'STABLE'
        WHEN avg_confidence > 0.01 AND (stddev_confidence / avg_confidence) < 0.30 THEN 'MODERATE'
        ELSE 'VOLATILE'
    END as stability_indicator
FROM regime_stats;

COMMENT ON VIEW fhq_governance.v_regime_variance_metrics IS
'CEO Directive: Metakognitiv Observability - CV per Regime.
Coefficient of Variation (CV) normaliserer for baseline-forskjeller.
Ekstern revisor kan sammenligne CV på tvers av BULL/BEAR/NEUTRAL.
Source: fhq_perception.model_belief_state';

-- ============================================================================
-- 3. Information Gain Ratio View (Økonomisk Perspektiv)
-- ============================================================================
-- IGR = Downstream Value / Query Cost
-- Measures ROI on information foraging

CREATE OR REPLACE VIEW fhq_governance.v_information_gain_ratio AS
WITH query_outcomes AS (
    SELECT
        q.query_id,
        q.created_at as query_time,
        COALESCE(q.cost_usd, 0) as query_cost,
        q.results_count,
        q.querying_agent,
        -- Downstream value proxy: evidence coverage ratio
        COALESCE(q.evidence_coverage_ratio, 0) as downstream_value_proxy
    FROM fhq_governance.inforage_query_log q
    WHERE q.created_at >= NOW() - INTERVAL '30 days'
)
SELECT
    DATE_TRUNC('day', query_time) as date,
    querying_agent,
    COUNT(*) as total_queries,
    ROUND(SUM(query_cost)::numeric, 6) as total_cost,
    ROUND(AVG(downstream_value_proxy)::numeric, 4) as avg_evidence_coverage,
    -- IGR = Value / Cost (higher is better)
    CASE WHEN SUM(query_cost) > 0
         THEN ROUND((AVG(downstream_value_proxy) / SUM(query_cost))::numeric, 4)
         ELSE NULL
    END as information_gain_ratio,
    -- Scent-to-gain efficiency
    ROUND(AVG(results_count)::numeric, 2) as avg_results_per_query
FROM query_outcomes
GROUP BY DATE_TRUNC('day', query_time), querying_agent;

COMMENT ON VIEW fhq_governance.v_information_gain_ratio IS
'CEO Directive: Metakognitiv Observability - Økonomisk Perspektiv.
Information Gain Ratio (IGR) = Value / Cost.
Ekstern revisor kan verifisere at systemet optimaliserer informasjonsverdi.
Source: fhq_governance.inforage_query_log';

-- ============================================================================
-- 4. EVPI Proxy Materialized View (Økonomisk Perspektiv - Option Value)
-- ============================================================================
-- Expected Value of Perfect Information proxy
-- Respects ADR-013: Only reads from epistemic_suppression_ledger

CREATE MATERIALIZED VIEW IF NOT EXISTS fhq_governance.mv_evpi_proxy AS
SELECT
    DATE_TRUNC('week', suppression_timestamp) as week,
    suppression_category,
    COUNT(*) as suppression_count,
    -- EVPI = confidence_delta * regret_magnitude (when regret occurred)
    ROUND(AVG(
        CASE
            WHEN regret_classification = 'REGRET'
            THEN ABS(suppressed_confidence - chosen_confidence) * COALESCE(regret_magnitude, 0.1)
            ELSE 0
        END
    )::numeric, 6) as evpi_proxy,
    ROUND(AVG(regret_magnitude) FILTER (WHERE regret_classification = 'REGRET')::numeric, 4) as avg_regret_magnitude,
    COUNT(*) FILTER (WHERE regret_classification = 'REGRET') as regret_count,
    COUNT(*) FILTER (WHERE regret_classification = 'WISDOM') as wisdom_count,
    -- Option value indicator: high EVPI = valuable information not used
    CASE
        WHEN AVG(CASE WHEN regret_classification = 'REGRET'
                      THEN ABS(suppressed_confidence - chosen_confidence) * COALESCE(regret_magnitude, 0.1)
                      ELSE 0 END) > 0.1 THEN 'HIGH_OPPORTUNITY_COST'
        WHEN AVG(CASE WHEN regret_classification = 'REGRET'
                      THEN ABS(suppressed_confidence - chosen_confidence) * COALESCE(regret_magnitude, 0.1)
                      ELSE 0 END) > 0.05 THEN 'MEDIUM_OPPORTUNITY_COST'
        ELSE 'LOW_OPPORTUNITY_COST'
    END as opportunity_cost_indicator
FROM fhq_governance.epistemic_suppression_ledger
WHERE suppression_timestamp >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('week', suppression_timestamp), suppression_category
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_evpi_proxy_week_category
ON fhq_governance.mv_evpi_proxy(week, suppression_category);

COMMENT ON MATERIALIZED VIEW fhq_governance.mv_evpi_proxy IS
'CEO Directive: Metakognitiv Observability - EVPI Proxy.
Expected Value of Perfect Information - respects ADR-013 One-Source-of-Truth.
Captures "cost of being wrong" adjusted for confidence delta.
Source: fhq_governance.epistemic_suppression_ledger';

-- ============================================================================
-- 5. Audit-Hardening Status View (Epistemisk Perspektiv)
-- ============================================================================
-- Tracks boundary violations, hash chain integrity, court-proof coverage

CREATE OR REPLACE VIEW fhq_governance.v_audit_hardening_status AS
WITH hash_chain_status AS (
    SELECT
        COUNT(*) as total_chains,
        COUNT(*) FILTER (WHERE status = 'SUCCESS' AND evidence_hash IS NOT NULL) as valid_chains,
        MAX(created_at) as last_chain_check
    FROM fhq_governance.cnrp_execution_log
    WHERE phase = 'R4'
      AND created_at >= NOW() - INTERVAL '24 hours'
),
evidence_status AS (
    SELECT
        COUNT(*) as total_summaries,
        COUNT(*) FILTER (WHERE raw_query IS NOT NULL) as with_raw_query,
        COUNT(*) FILTER (WHERE query_result_hash IS NOT NULL) as with_hash,
        MAX(created_at) as last_evidence
    FROM vision_verification.summary_evidence_ledger
    WHERE created_at >= NOW() - INTERVAL '7 days'
),
boundary_status AS (
    SELECT
        COUNT(*) as total_validations,
        COUNT(*) FILTER (WHERE passed = FALSE) as violations,
        MAX(created_at) as last_validation
    FROM fhq_governance.ikea_validation_log
    WHERE created_at >= NOW() - INTERVAL '30 days'
),
defcon_status AS (
    SELECT
        COALESCE(current_defcon::text, 'GREEN') as current_defcon,
        updated_at
    FROM fhq_governance.system_state
    WHERE is_active = TRUE
    ORDER BY updated_at DESC
    LIMIT 1
)
SELECT
    -- Hash Chain Integrity
    COALESCE(hc.total_chains, 0) as hash_chain_checks_24h,
    COALESCE(hc.valid_chains, 0) as hash_chain_valid,
    CASE WHEN COALESCE(hc.total_chains, 0) > 0
         THEN ROUND((hc.valid_chains::numeric / hc.total_chains::numeric) * 100, 2)
         ELSE 100.00 -- No checks = assume OK
    END as hash_chain_integrity_pct,
    hc.last_chain_check,

    -- Court-Proof Coverage
    COALESCE(es.total_summaries, 0) as summaries_7d,
    COALESCE(es.with_raw_query, 0) as summaries_with_query,
    CASE WHEN COALESCE(es.total_summaries, 0) > 0
         THEN ROUND((es.with_raw_query::numeric / es.total_summaries::numeric) * 100, 2)
         ELSE 100.00
    END as court_proof_coverage_pct,
    es.last_evidence,

    -- Boundary Violations (IKEA)
    COALESCE(bs.total_validations, 0) as boundary_checks_30d,
    COALESCE(bs.violations, 0) as boundary_violations,
    bs.last_validation,

    -- System DEFCON (default GREEN if no data)
    COALESCE(ds.current_defcon, 'GREEN') as current_defcon,
    ds.updated_at as defcon_updated_at,

    -- Overall Audit Health Score (0-100)
    ROUND(
        (
            -- Hash chain: 40% weight
            CASE WHEN COALESCE(hc.total_chains, 0) > 0
                 THEN (hc.valid_chains::numeric / hc.total_chains::numeric) * 40
                 ELSE 40 END
            +
            -- Court-proof: 40% weight
            CASE WHEN COALESCE(es.total_summaries, 0) > 0
                 THEN (es.with_raw_query::numeric / es.total_summaries::numeric) * 40
                 ELSE 40 END
            +
            -- No violations: 20% weight
            CASE WHEN COALESCE(bs.violations, 0) = 0 THEN 20
                 WHEN COALESCE(bs.violations, 0) < 5 THEN 10
                 ELSE 0 END
        ), 2
    ) as audit_health_score
FROM hash_chain_status hc
CROSS JOIN evidence_status es
CROSS JOIN boundary_status bs
LEFT JOIN defcon_status ds ON TRUE;

COMMENT ON VIEW fhq_governance.v_audit_hardening_status IS
'CEO Directive: Metakognitiv Observability - Audit-Hardening Status.
G4+ Compliance tracking: hash chains, court-proof coverage, boundary violations.
Juridisk Anker per ADR-011.';

-- ============================================================================
-- 6. Cognitive Summary View (Dashboard Aggregation)
-- ============================================================================
-- Single-query view for dashboard cognitive panel

CREATE OR REPLACE VIEW fhq_governance.v_metacognitive_cognitive_summary AS
WITH daily_coq AS (
    SELECT
        AVG(efficiency_score) as avg_efficiency,
        AVG(abort_rate) as avg_abort_rate,
        AVG(avg_latency_ms) as avg_latency,
        SUM(total_cost_usd) as total_cost_7d
    FROM fhq_governance.v_chain_of_query_efficiency
    WHERE query_date >= NOW() - INTERVAL '7 days'
),
regime_cv AS (
    SELECT
        dominant_regime,
        AVG(confidence_cv) as avg_cv
    FROM fhq_governance.v_regime_variance_metrics
    WHERE week >= NOW() - INTERVAL '4 weeks'
    GROUP BY dominant_regime
)
SELECT
    ROUND(COALESCE(dc.avg_efficiency, 0)::numeric, 2) as coq_efficiency_score,
    ROUND(COALESCE(dc.avg_abort_rate, 0) * 100::numeric, 2) as abort_rate_pct,
    ROUND(COALESCE(dc.avg_latency, 0)::numeric, 0) as avg_latency_ms,
    ROUND(COALESCE(dc.total_cost_7d, 0)::numeric, 4) as total_query_cost_7d,
    -- CV per regime (JSON object)
    (SELECT jsonb_object_agg(dominant_regime, ROUND(avg_cv::numeric, 4))
     FROM regime_cv) as cv_per_regime,
    NOW() as computed_at
FROM daily_coq dc;

COMMENT ON VIEW fhq_governance.v_metacognitive_cognitive_summary IS
'CEO Directive: Metakognitiv Observability - Kognitiv Dashboard Summary.
Single-query aggregation for dashboard display.';

-- ============================================================================
-- 7. Economic Summary View (Dashboard Aggregation)
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.v_metacognitive_economic_summary AS
WITH igr_summary AS (
    SELECT
        AVG(information_gain_ratio) as avg_igr,
        SUM(total_cost) as total_cost_30d,
        AVG(avg_evidence_coverage) as avg_coverage
    FROM fhq_governance.v_information_gain_ratio
    WHERE date >= NOW() - INTERVAL '30 days'
),
evpi_summary AS (
    SELECT
        SUM(evpi_proxy * suppression_count) / NULLIF(SUM(suppression_count), 0) as weighted_evpi,
        SUM(regret_count) as total_regrets,
        SUM(wisdom_count) as total_wisdom
    FROM fhq_governance.mv_evpi_proxy
    WHERE week >= NOW() - INTERVAL '12 weeks'
),
calibration_summary AS (
    SELECT
        AVG(brier_score) as avg_brier,
        COUNT(*) as forecast_count
    FROM fhq_governance.calibration_dashboard
)
SELECT
    ROUND(COALESCE(igr.avg_igr, 0)::numeric, 4) as avg_information_gain_ratio,
    ROUND(COALESCE(igr.total_cost_30d, 0)::numeric, 4) as total_query_cost_30d,
    ROUND(COALESCE(igr.avg_coverage, 0)::numeric, 4) as avg_evidence_coverage,
    ROUND(COALESCE(evpi.weighted_evpi, 0)::numeric, 6) as evpi_proxy_value,
    COALESCE(evpi.total_regrets, 0) as regret_count_12w,
    COALESCE(evpi.total_wisdom, 0) as wisdom_count_12w,
    ROUND(COALESCE(cal.avg_brier, 0)::numeric, 4) as avg_brier_score,
    COALESCE(cal.forecast_count, 0) as calibrated_forecasts,
    -- Brier data availability indicator
    CASE WHEN COALESCE(cal.forecast_count, 0) = 0
         THEN 'AWAITING_FINN_DATA'
         ELSE 'ACTIVE'
    END as calibration_status,
    NOW() as computed_at
FROM igr_summary igr
CROSS JOIN evpi_summary evpi
CROSS JOIN calibration_summary cal;

COMMENT ON VIEW fhq_governance.v_metacognitive_economic_summary IS
'CEO Directive: Metakognitiv Observability - Økonomisk Dashboard Summary.
IGR, EVPI, and calibration metrics.
Note: Brier scores require FINN population of brier_score_ledger.';

-- ============================================================================
-- 8. Refresh Function for Materialized Views
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.refresh_metacognitive_views()
RETURNS jsonb AS $$
DECLARE
    refresh_result jsonb;
    start_time timestamptz;
    evpi_refreshed boolean := false;
    weekly_refreshed boolean := false;
    calibration_refreshed boolean := false;
BEGIN
    start_time := clock_timestamp();

    -- Refresh EVPI proxy
    BEGIN
        REFRESH MATERIALIZED VIEW CONCURRENTLY fhq_governance.mv_evpi_proxy;
        evpi_refreshed := true;
    EXCEPTION WHEN OTHERS THEN
        evpi_refreshed := false;
    END;

    -- Refresh weekly learning metrics
    BEGIN
        REFRESH MATERIALIZED VIEW fhq_governance.weekly_learning_metrics;
        weekly_refreshed := true;
    EXCEPTION WHEN OTHERS THEN
        weekly_refreshed := false;
    END;

    -- Refresh calibration dashboard
    BEGIN
        REFRESH MATERIALIZED VIEW fhq_governance.calibration_dashboard;
        calibration_refreshed := true;
    EXCEPTION WHEN OTHERS THEN
        calibration_refreshed := false;
    END;

    -- Build result
    refresh_result := jsonb_build_object(
        'refreshed_at', clock_timestamp(),
        'duration_ms', EXTRACT(MILLISECONDS FROM clock_timestamp() - start_time),
        'views_refreshed', jsonb_build_object(
            'mv_evpi_proxy', evpi_refreshed,
            'weekly_learning_metrics', weekly_refreshed,
            'calibration_dashboard', calibration_refreshed
        )
    );

    -- Log to governance
    INSERT INTO fhq_governance.governance_actions_log (
        action_type,
        action_target,
        decision,
        decision_rationale,
        initiated_by,
        metadata
    ) VALUES (
        'METACOGNITIVE_REFRESH',
        'fhq_governance.mv_*',
        'EXECUTED',
        'Scheduled refresh of metacognitive materialized views',
        'STIG',
        refresh_result
    );

    RETURN refresh_result;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.refresh_metacognitive_views IS
'Refreshes all metacognitive materialized views.
Should be scheduled for daily refresh (24h) per STIG recommendation.';

-- ============================================================================
-- 9. Grant Permissions
-- ============================================================================

-- Views are read-only for dashboard
GRANT SELECT ON fhq_governance.v_chain_of_query_efficiency TO PUBLIC;
GRANT SELECT ON fhq_governance.v_regime_variance_metrics TO PUBLIC;
GRANT SELECT ON fhq_governance.v_information_gain_ratio TO PUBLIC;
GRANT SELECT ON fhq_governance.mv_evpi_proxy TO PUBLIC;
GRANT SELECT ON fhq_governance.v_audit_hardening_status TO PUBLIC;
GRANT SELECT ON fhq_governance.v_metacognitive_cognitive_summary TO PUBLIC;
GRANT SELECT ON fhq_governance.v_metacognitive_economic_summary TO PUBLIC;

-- ============================================================================
-- 10. Log Migration
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    decision,
    decision_rationale,
    initiated_by,
    metadata
) VALUES (
    'MIGRATION',
    '225_metacognitive_observability',
    'APPLIED',
    'CEO Directive: Metakognitiv Observability & Audit-Hardening. G1 Technical Validation approved.',
    'STIG',
    jsonb_build_object(
        'views_created', ARRAY[
            'v_chain_of_query_efficiency',
            'v_regime_variance_metrics',
            'v_information_gain_ratio',
            'mv_evpi_proxy',
            'v_audit_hardening_status',
            'v_metacognitive_cognitive_summary',
            'v_metacognitive_economic_summary'
        ],
        'functions_created', ARRAY['refresh_metacognitive_views'],
        'authority', 'CEO Directive Metacognitive Observability',
        'adr_references', ARRAY['ADR-004', 'ADR-014', 'IoS-005']
    )
);

COMMIT;

-- ============================================================================
-- Post-migration verification queries (run manually)
-- ============================================================================
-- SELECT * FROM fhq_governance.v_chain_of_query_efficiency LIMIT 5;
-- SELECT * FROM fhq_governance.v_regime_variance_metrics LIMIT 5;
-- SELECT * FROM fhq_governance.v_information_gain_ratio LIMIT 5;
-- SELECT * FROM fhq_governance.mv_evpi_proxy;
-- SELECT * FROM fhq_governance.v_audit_hardening_status;
-- SELECT * FROM fhq_governance.v_metacognitive_cognitive_summary;
-- SELECT * FROM fhq_governance.v_metacognitive_economic_summary;
