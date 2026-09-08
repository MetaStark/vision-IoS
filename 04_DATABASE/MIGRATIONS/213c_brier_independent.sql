-- Compute REAL Brier scores using independent outcomes only
CREATE OR REPLACE FUNCTION fhq_research.compute_brier_score_independent(
    p_period_start TIMESTAMPTZ,
    p_period_end TIMESTAMPTZ
)
RETURNS TABLE (
    metric_id UUID,
    forecast_count INTEGER,
    resolved_count INTEGER,
    brier_score_mean NUMERIC,
    hit_rate NUMERIC,
    evidence_integrity TEXT
)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_metric_id UUID;
    v_forecast_count INTEGER;
    v_resolved_count INTEGER;
    v_brier_mean NUMERIC;
    v_hit_rate NUMERIC;
BEGIN
    WITH matched_forecasts AS (
        SELECT
            sps.policy_id,
            sps.policy_regime AS predicted_regime,
            sps.policy_confidence,
            o.outcome_value AS actual_regime,
            CASE WHEN sps.policy_regime = o.outcome_value THEN 1 ELSE 0 END AS correct,
            POWER(
                CASE WHEN sps.policy_regime = o.outcome_value
                     THEN 1 - sps.policy_confidence
                     ELSE sps.policy_confidence
                END, 2
            ) AS brier_score
        FROM fhq_perception.sovereign_policy_state sps
        JOIN fhq_research.outcome_ledger o
            ON o.outcome_domain = 'SPY'
            AND o.outcome_type = 'REGIME'
            AND o.evidence_source = 'fhq_market.prices'  -- ONLY independent!
            AND o.outcome_timestamp BETWEEN sps.policy_timestamp AND sps.policy_timestamp + INTERVAL '48 hours'
        WHERE sps.policy_timestamp BETWEEN p_period_start AND p_period_end
    )
    SELECT
        COUNT(*)::INTEGER,
        COUNT(actual_regime)::INTEGER,
        AVG(brier_score),
        AVG(correct)
    INTO v_forecast_count, v_resolved_count, v_brier_mean, v_hit_rate
    FROM matched_forecasts;

    v_metric_id := gen_random_uuid();

    INSERT INTO fhq_research.forecast_skill_metrics (
        metric_id,
        metric_scope,
        scope_value,
        period_start,
        period_end,
        forecast_count,
        resolved_count,
        brier_score_mean,
        hit_rate,
        computed_by,
        hash_chain_id
    ) VALUES (
        v_metric_id,
        'INDEPENDENT_REGIME',
        'SPY',
        p_period_start,
        p_period_end,
        v_forecast_count,
        v_resolved_count,
        v_brier_mean,
        v_hit_rate,
        'STIG-M213',
        'HC-BRIER-INDEPENDENT-' || to_char(NOW(), 'YYYYMMDD')
    );

    RETURN QUERY SELECT
        v_metric_id,
        v_forecast_count,
        v_resolved_count,
        v_brier_mean,
        v_hit_rate,
        'INDEPENDENT - fhq_market.prices'::TEXT;
END;
$function$;

-- Execute it
SELECT * FROM fhq_research.compute_brier_score_independent('2025-12-08'::timestamptz, '2026-01-07'::timestamptz);
