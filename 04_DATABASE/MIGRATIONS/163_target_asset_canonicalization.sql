-- Migration 163: Target Asset Canonicalization
-- CEO Directive: CEO-ACI-FINN-TA-2025-12-21
-- Purpose: Add p_target_asset parameter to persist_golden_needle function
-- Scope: FINN -> Golden Needles -> ACI Triangle (EC-022 IKEA filtering)

-- ============================================================================
-- STEP 1: Update persist_golden_needle function to include target_asset
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_canonical.persist_golden_needle(
    p_hypothesis_id text,
    p_hunt_session_id uuid,
    p_cycle_id text,
    p_eqs_score numeric,
    p_confluence_factors text[],
    p_eqs_components jsonb,
    p_hypothesis_title text,
    p_hypothesis_statement text,
    p_hypothesis_category text,
    p_executive_summary text,
    p_sitc_plan_id uuid,
    p_sitc_confidence text,
    p_sitc_nodes_completed integer,
    p_sitc_nodes_total integer,
    p_asrp_hash text,
    p_asrp_timestamp timestamp with time zone,
    p_state_vector_id uuid,
    p_state_hash text,
    p_price_witness_id text,
    p_price_witness_symbol text,
    p_price_witness_value numeric,
    p_price_witness_source text,
    p_price_witness_timestamp timestamp with time zone,
    p_regime_asset_id text,
    p_regime_technical text,
    p_regime_sovereign text,
    p_regime_confidence numeric,
    p_regime_crio_driver text,
    p_regime_snapshot_timestamp timestamp with time zone,
    p_defcon_level integer,
    p_falsification_criteria jsonb,
    p_backtest_requirements jsonb,
    p_g2_exam_session_id text DEFAULT NULL,
    p_chain_of_query_hash text DEFAULT NULL,
    p_target_asset text DEFAULT NULL  -- NEW: Canonical target asset (e.g., BTC-USD, ETH-USD)
)
RETURNS uuid
LANGUAGE plpgsql
AS $function$
DECLARE
    v_needle_id UUID;
    v_target_asset TEXT;
BEGIN
    -- Validate EQS threshold (constitutional constraint)
    IF p_eqs_score < 0.85 THEN
        RAISE EXCEPTION 'G3 VIOLATION: Cannot persist hypothesis with EQS < 0.85. EQS=% is below threshold.', p_eqs_score;
    END IF;

    -- Derive target_asset from p_target_asset or fallback to p_regime_asset_id or p_price_witness_symbol
    v_target_asset := COALESCE(
        p_target_asset,
        p_regime_asset_id,
        CASE
            WHEN p_price_witness_symbol ILIKE '%BTC%' THEN 'BTC-USD'
            WHEN p_price_witness_symbol ILIKE '%ETH%' THEN 'ETH-USD'
            WHEN p_price_witness_symbol ILIKE '%SOL%' THEN 'SOL-USD'
            WHEN p_price_witness_symbol ILIKE '%XRP%' THEN 'XRP-USD'
            ELSE p_price_witness_symbol
        END
    );

    INSERT INTO fhq_canonical.golden_needles (
        hypothesis_id,
        hunt_session_id,
        cycle_id,
        eqs_score,
        -- Confluence factors
        factor_price_technical,
        factor_volume_confirmation,
        factor_regime_alignment,
        factor_temporal_coherence,
        factor_catalyst_present,
        factor_specific_testable,
        factor_testable_criteria,
        -- EQS weights
        weight_price_technical,
        weight_volume_confirmation,
        weight_regime_alignment,
        weight_temporal_coherence,
        weight_catalyst_present,
        weight_specificity_bonus,
        weight_testability_bonus,
        stress_modifier,
        -- Hypothesis
        hypothesis_title,
        hypothesis_statement,
        hypothesis_category,
        executive_summary,
        -- SitC
        sitc_plan_id,
        sitc_confidence_level,
        sitc_nodes_completed,
        sitc_nodes_total,
        -- ASRP
        asrp_hash,
        asrp_timestamp,
        state_vector_id,
        state_hash_at_creation,
        -- Price Witness
        price_witness_id,
        price_witness_symbol,
        price_witness_value,
        price_witness_source,
        price_witness_timestamp,
        -- Regime
        regime_asset_id,
        regime_technical,
        regime_sovereign,
        regime_confidence,
        regime_crio_driver,
        regime_snapshot_timestamp,
        defcon_level,
        -- Backtest hooks
        falsification_criteria,
        backtest_requirements,
        -- Governance
        g2_exam_session_id,
        chain_of_query_hash,
        target_asset  -- NEW: Canonical target asset
    ) VALUES (
        p_hypothesis_id,
        p_hunt_session_id,
        p_cycle_id,
        p_eqs_score,
        -- Parse confluence factors array
        'PRICE_TECHNICAL' = ANY(p_confluence_factors),
        'VOLUME_CONFIRMATION' = ANY(p_confluence_factors),
        'REGIME_ALIGNMENT' = ANY(p_confluence_factors),
        'TEMPORAL_COHERENCE' = ANY(p_confluence_factors),
        'CATALYST_PRESENT' = ANY(p_confluence_factors),
        'SPECIFIC_TESTABLE' = ANY(p_confluence_factors),
        'TESTABLE_CRITERIA' = ANY(p_confluence_factors),
        -- Extract weights from JSONB
        (p_eqs_components->>'price_technical')::NUMERIC,
        (p_eqs_components->>'volume_confirmation')::NUMERIC,
        (p_eqs_components->>'regime_alignment')::NUMERIC,
        (p_eqs_components->>'temporal_coherence')::NUMERIC,
        (p_eqs_components->>'catalyst_present')::NUMERIC,
        (p_eqs_components->>'specificity_bonus')::NUMERIC,
        (p_eqs_components->>'testability_bonus')::NUMERIC,
        COALESCE((p_eqs_components->>'stress_modifier')::NUMERIC, 1.0),
        p_hypothesis_title,
        p_hypothesis_statement,
        p_hypothesis_category,
        p_executive_summary,
        p_sitc_plan_id,
        p_sitc_confidence,
        p_sitc_nodes_completed,
        p_sitc_nodes_total,
        p_asrp_hash,
        p_asrp_timestamp,
        p_state_vector_id,
        p_state_hash,
        p_price_witness_id,
        p_price_witness_symbol,
        p_price_witness_value,
        p_price_witness_source,
        p_price_witness_timestamp,
        p_regime_asset_id,
        p_regime_technical,
        p_regime_sovereign,
        p_regime_confidence,
        p_regime_crio_driver,
        p_regime_snapshot_timestamp,
        p_defcon_level,
        p_falsification_criteria,
        p_backtest_requirements,
        p_g2_exam_session_id,
        p_chain_of_query_hash,
        v_target_asset  -- Derived or explicit target asset
    ) RETURNING needle_id INTO v_needle_id;

    RETURN v_needle_id;
END;
$function$;

-- ============================================================================
-- STEP 2: Backfill existing 740 needles with canonical target_asset
-- Source of truth: regime_asset_id (already 'BTC-USD' for all)
-- ============================================================================

UPDATE fhq_canonical.golden_needles
SET target_asset = COALESCE(
    regime_asset_id,
    CASE
        WHEN price_witness_symbol ILIKE '%BTC%' THEN 'BTC-USD'
        WHEN price_witness_symbol ILIKE '%ETH%' THEN 'ETH-USD'
        WHEN price_witness_symbol ILIKE '%SOL%' THEN 'SOL-USD'
        WHEN price_witness_symbol ILIKE '%XRP%' THEN 'XRP-USD'
        ELSE 'BTC-USD'  -- Default to BTC-USD for crypto needles
    END
)
WHERE target_asset IS NULL
  AND is_current = TRUE;

-- ============================================================================
-- STEP 3: Add constraint to prevent future NULL target_asset (optional warning)
-- Note: Not enforced as hard constraint per CEO directive (SHADOW mode)
-- ============================================================================

COMMENT ON COLUMN fhq_canonical.golden_needles.target_asset IS
'Canonical target asset identifier (e.g., BTC-USD, ETH-USD).
Required for EC-022 IKEA asset-class filtering.
CEO Directive: CEO-ACI-FINN-TA-2025-12-21';

-- ============================================================================
-- VERIFICATION QUERY (run after migration)
-- ============================================================================
-- SELECT
--     COUNT(*) as total,
--     COUNT(*) FILTER (WHERE target_asset IS NULL) as null_target,
--     COUNT(*) FILTER (WHERE target_asset IS NOT NULL) as with_target
-- FROM fhq_canonical.golden_needles
-- WHERE is_current = TRUE;
