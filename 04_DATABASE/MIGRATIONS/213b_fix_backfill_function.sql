-- Fix backfill function with content_hash
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
    v_content_hash TEXT;
    v_evidence_data JSONB;
BEGIN
    FOR v_date IN SELECT generate_series(p_start_date, p_end_date, '1 day'::interval)::date
    LOOP
        SELECT regime, return_pct, evidence_hash, computation_method
        INTO v_regime, v_return_pct, v_evidence_hash, v_computation_method
        FROM fhq_research.compute_price_based_regime(p_reference_asset, v_date, 5);

        IF v_regime IS NOT NULL THEN
            -- Build evidence data
            v_evidence_data := jsonb_build_object(
                'computation_method', v_computation_method,
                'return_pct', v_return_pct,
                'evidence_hash', v_evidence_hash,
                'reference_asset', p_reference_asset,
                'lookback_days', 5,
                'threshold_bull', 1.0,
                'threshold_bear', -1.0,
                'lineage', 'CEO-DIR-2026-019-M213'
            );

            -- Compute content_hash (SHA-256 of canonical content)
            v_content_hash := encode(sha256(
                ('REGIME_INDEPENDENT' || p_reference_asset || v_regime ||
                 (v_date::timestamptz + INTERVAL '16 hours')::text ||
                 'fhq_market.prices' || v_evidence_data::text)::bytea
            ), 'hex');

            INSERT INTO fhq_research.outcome_ledger (
                outcome_type,
                outcome_domain,
                outcome_value,
                outcome_timestamp,
                evidence_source,
                evidence_data,
                content_hash,
                hash_chain_id,
                created_by
            ) VALUES (
                'REGIME',  -- Use standard type, distinguish by evidence_source
                p_reference_asset,
                v_regime,
                v_date::timestamptz + INTERVAL '16 hours',
                'fhq_market.prices',  -- INDEPENDENT: NOT sovereign_regime_state_v4
                v_evidence_data,
                v_content_hash,
                'HC-REGIME-INDEPENDENT-' || to_char(v_date, 'YYYYMMDD'),
                'STIG-M213'
            )
            ON CONFLICT DO NOTHING;
            v_count := v_count + 1;
        END IF;
    END LOOP;
    RETURN QUERY SELECT v_count, TRUE, NULL::TEXT;
EXCEPTION
    WHEN OTHERS THEN
        RETURN QUERY SELECT 0, FALSE, SQLERRM;
END;
$function$;

-- Now execute the backfill
SELECT * FROM fhq_research.backfill_independent_regime_outcomes('2025-12-08'::date, '2026-01-07'::date, 'SPY');
