-- ============================================================================
-- CEO-DIR-2026-019: CRITICAL FIX - Independent Regime Outcome Source
-- Migration 213: Eliminate circular validation in Brier/hit-rate metrics
-- ============================================================================
-- STIG Implementation | P0-1 Audit Finding
-- Generated: 2026-01-07
--
-- PROBLEM DISCOVERED:
--   outcome_ledger.evidence_source = 'sovereign_regime_state_v4'
--   Outcomes derived FROM predictions → 100% hit rate is SELF-REFERENTIAL
--   All Brier scores and calibration metrics are MEANINGLESS
--
-- SOLUTION:
--   Create independent regime classification from actual price returns
--   Evidence source: fhq_market.prices (canonical price data)
--   Method: 5-day rolling return on SPY determines market regime
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART 1: PRICE-BASED REGIME CLASSIFICATION FUNCTION
-- ============================================================================
-- Independent regime derivation based on actual market movements
-- NOT derived from model predictions - this is the key fix

CREATE OR REPLACE FUNCTION fhq_research.compute_price_based_regime(
    p_asset_id TEXT,
    p_as_of_date DATE,
    p_lookback_days INTEGER DEFAULT 5
)
RETURNS TABLE (
    regime TEXT,
    return_pct NUMERIC,
    evidence_hash TEXT,
    computation_method TEXT
)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_current_price NUMERIC;
    v_prior_price NUMERIC;
    v_return_pct NUMERIC;
    v_regime TEXT;
    v_evidence_hash TEXT;
BEGIN
    -- Get current price (most recent before as_of_date)
    SELECT close INTO v_current_price
    FROM fhq_market.prices
    WHERE canonical_id = p_asset_id
      AND timestamp::date <= p_as_of_date
    ORDER BY timestamp DESC
    LIMIT 1;

    -- Get prior price (lookback_days before)
    SELECT close INTO v_prior_price
    FROM fhq_market.prices
    WHERE canonical_id = p_asset_id
      AND timestamp::date <= (p_as_of_date - p_lookback_days)
    ORDER BY timestamp DESC
    LIMIT 1;

    -- Compute return
    IF v_current_price IS NOT NULL AND v_prior_price IS NOT NULL AND v_prior_price > 0 THEN
        v_return_pct := (v_current_price - v_prior_price) / v_prior_price * 100;
    ELSE
        v_return_pct := NULL;
    END IF;

    -- Classify regime based on returns
    -- These thresholds are FIXED and DOCUMENTED - not derived from predictions
    IF v_return_pct IS NULL THEN
        v_regime := NULL;
    ELSIF v_return_pct > 1.0 THEN
        v_regime := 'BULL';      -- >1% 5-day return = bullish
    ELSIF v_return_pct < -1.0 THEN
        v_regime := 'BEAR';      -- <-1% 5-day return = bearish
    ELSE
        v_regime := 'NEUTRAL';   -- Between -1% and +1% = neutral
    END IF;

    -- Compute evidence hash for court-proof verification
    v_evidence_hash := encode(sha256(
        (p_asset_id || p_as_of_date::text || p_lookback_days::text ||
         COALESCE(v_current_price::text, 'NULL') ||
         COALESCE(v_prior_price::text, 'NULL'))::bytea
    ), 'hex');

    RETURN QUERY SELECT
        v_regime,
        v_return_pct,
        v_evidence_hash,
        'PRICE_RETURN_5D_SPY_THRESHOLD'::TEXT;
END;
$function$;

COMMENT ON FUNCTION fhq_research.compute_price_based_regime IS
'CEO-DIR-2026-019 P0-1 FIX: Independent regime classification from price returns.
CRITICAL: This function does NOT reference sovereign_regime_state or any predictions.
Evidence source is fhq_market.prices (canonical, auditable).
Thresholds: BULL (>+1%), NEUTRAL (-1% to +1%), BEAR (<-1%)';

-- ============================================================================
-- PART 2: BULK BACKFILL FUNCTION FOR INDEPENDENT OUTCOMES
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.backfill_independent_regime_outcomes(
    p_start_date DATE,
    p_end_date DATE,
    p_reference_asset TEXT DEFAULT 'SPY'
)
RETURNS TABLE (
    backfilled_count INTEGER,
    success BOOLEAN,
    error_message TEXT
)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_count INTEGER := 0;
    v_date DATE;
    v_regime TEXT;
    v_return_pct NUMERIC;
    v_evidence_hash TEXT;
    v_computation_method TEXT;
BEGIN
    -- Loop through each date
    FOR v_date IN SELECT generate_series(p_start_date, p_end_date, '1 day'::interval)::date
    LOOP
        -- Compute independent regime for this date
        SELECT regime, return_pct, evidence_hash, computation_method
        INTO v_regime, v_return_pct, v_evidence_hash, v_computation_method
        FROM fhq_research.compute_price_based_regime(p_reference_asset, v_date, 5);

        -- Only insert if we got a valid regime
        IF v_regime IS NOT NULL THEN
            -- Insert into outcome_ledger with INDEPENDENT evidence source
            INSERT INTO fhq_research.outcome_ledger (
                outcome_type,
                outcome_domain,
                outcome_value,
                outcome_timestamp,
                evidence_source,
                evidence_data,  -- FIXED: correct column name
                created_by
            ) VALUES (
                'REGIME_INDEPENDENT',  -- New type to distinguish from contaminated
                p_reference_asset,
                v_regime,
                v_date::timestamptz + INTERVAL '16 hours',  -- Market close time
                'fhq_market.prices',   -- INDEPENDENT source - NOT sovereign_regime_state_v4
                jsonb_build_object(
                    'computation_method', v_computation_method,
                    'return_pct', v_return_pct,
                    'evidence_hash', v_evidence_hash,
                    'reference_asset', p_reference_asset,
                    'lookback_days', 5,
                    'threshold_bull', 1.0,
                    'threshold_bear', -1.0,
                    'lineage', 'CEO-DIR-2026-019-M213'
                ),
                'STIG-M213'
            )
            ON CONFLICT DO NOTHING;  -- Idempotent

            v_count := v_count + 1;
        END IF;
    END LOOP;

    RETURN QUERY SELECT v_count, TRUE, NULL::TEXT;
EXCEPTION
    WHEN OTHERS THEN
        RETURN QUERY SELECT 0, FALSE, SQLERRM;
END;
$function$;

COMMENT ON FUNCTION fhq_research.backfill_independent_regime_outcomes IS
'CEO-DIR-2026-019 P0-1 FIX: Backfill outcome_ledger with INDEPENDENT regime outcomes.
Evidence source: fhq_market.prices (NOT sovereign_regime_state_v4).
This eliminates circular validation in Brier score computation.';

-- ============================================================================
-- PART 3: CORRECTED BRIER SCORE FUNCTION USING INDEPENDENT OUTCOMES
-- ============================================================================

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
    -- Count forecasts with INDEPENDENT outcomes only
    WITH matched_forecasts AS (
        SELECT
            sps.policy_id,
            sps.policy_regime AS predicted_regime,
            sps.confidence,
            o.outcome_value AS actual_regime,
            CASE WHEN sps.policy_regime = o.outcome_value THEN 1 ELSE 0 END AS correct,
            POWER(
                CASE WHEN sps.policy_regime = o.outcome_value
                     THEN 1 - sps.confidence
                     ELSE sps.confidence
                END, 2
            ) AS brier_score
        FROM fhq_perception.sovereign_policy_state sps
        JOIN fhq_research.outcome_ledger o
            ON o.outcome_domain = 'SPY'
            AND o.outcome_type = 'REGIME_INDEPENDENT'  -- ONLY independent outcomes
            AND o.evidence_source = 'fhq_market.prices'  -- Verify source
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

    -- Generate metric ID
    v_metric_id := gen_random_uuid();

    -- Store in forecast_skill_metrics
    INSERT INTO fhq_research.forecast_skill_metrics (
        metric_id,
        metric_type,
        period_start,
        period_end,
        value,
        metadata
    ) VALUES (
        v_metric_id,
        'BRIER_SCORE_INDEPENDENT',
        p_period_start,
        p_period_end,
        v_brier_mean,
        jsonb_build_object(
            'forecast_count', v_forecast_count,
            'resolved_count', v_resolved_count,
            'hit_rate', v_hit_rate,
            'evidence_source', 'fhq_market.prices',
            'outcome_type_used', 'REGIME_INDEPENDENT',
            'lineage', 'CEO-DIR-2026-019-M213',
            'circular_validation', FALSE
        )
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

COMMENT ON FUNCTION fhq_research.compute_brier_score_independent IS
'CEO-DIR-2026-019 P0-1 FIX: Brier score using ONLY independent outcomes.
CRITICAL: Only matches against REGIME_INDEPENDENT outcomes with evidence_source = fhq_market.prices.
This produces MEANINGFUL calibration metrics (not 100% due to circular validation).';

-- ============================================================================
-- PART 4: CONTAMINATION STATUS (Computed, not stored - respects immutability)
-- ============================================================================
-- outcome_ledger has immutability trigger, so we use a computed view instead

-- No column added - contamination is DERIVED from evidence_source, not stored
-- This respects the immutability contract on outcome_ledger

-- ============================================================================
-- PART 5: VIEW FOR AUDIT - SHOW CONTAMINATION STATUS
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_outcome_integrity_audit AS
SELECT
    outcome_type,
    evidence_source,
    -- Computed contamination status (not stored, respects immutability)
    CASE
        WHEN evidence_source = 'sovereign_regime_state_v4' THEN TRUE
        ELSE FALSE
    END AS circular_contamination,
    COUNT(*) as count,
    MIN(outcome_timestamp) as first_outcome,
    MAX(outcome_timestamp) as last_outcome,
    CASE
        WHEN evidence_source = 'sovereign_regime_state_v4' THEN 'INVALID - circular validation'
        WHEN evidence_source = 'fhq_market.prices' THEN 'VALID - independent source'
        ELSE 'UNKNOWN - requires audit'
    END AS integrity_status
FROM fhq_research.outcome_ledger
GROUP BY outcome_type, evidence_source
ORDER BY count DESC;

COMMENT ON VIEW fhq_research.v_outcome_integrity_audit IS
'CEO-DIR-2026-019 P0-1: Audit view showing outcome source integrity.
VALID outcomes must have evidence_source = fhq_market.prices.
circular_contamination is COMPUTED from evidence_source (respects ledger immutability).';

-- ============================================================================
-- PART 6: GOVERNANCE LOG ENTRY
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MIGRATION',
    '213_independent_regime_outcome_source',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-019 P0-1: Fix circular validation - create independent outcome source',
    jsonb_build_object(
        'migration', '213_independent_regime_outcome_source',
        'directive', 'CEO-DIR-2026-019',
        'audit_finding', 'CIRCULAR_VALIDATION_DETECTED',
        'problem', 'outcome_ledger.evidence_source = sovereign_regime_state_v4 means 100% hit rate is self-referential',
        'solution', 'Create REGIME_INDEPENDENT outcomes from fhq_market.prices',
        'functions_added', ARRAY[
            'compute_price_based_regime',
            'backfill_independent_regime_outcomes',
            'compute_brier_score_independent'
        ],
        'columns_added', ARRAY[]::TEXT[],  -- No columns added (respects outcome_ledger immutability)
        'views_added', ARRAY['v_outcome_integrity_audit']
    )
);

COMMIT;

-- ============================================================================
-- POST-COMMIT: BACKFILL INDEPENDENT OUTCOMES
-- ============================================================================
-- Execute after migration:
-- SELECT * FROM fhq_research.backfill_independent_regime_outcomes('2025-12-08', '2026-01-07', 'SPY');
-- SELECT * FROM fhq_research.compute_brier_score_independent('2025-12-08'::timestamptz, '2026-01-07'::timestamptz);
