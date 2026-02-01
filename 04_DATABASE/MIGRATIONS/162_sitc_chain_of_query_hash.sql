-- ============================================================================
-- Migration 162: Add chain_of_query_hash to persist_golden_needle function
-- ============================================================================
-- CEO Directive: CEO-ACI-TRIANGLE-2025-12-21
-- Purpose: Enable EC-020 SitC chain validation by populating chain_of_query_hash
-- ============================================================================

BEGIN;

-- Update persist_golden_needle function to include chain_of_query_hash
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
    p_chain_of_query_hash text DEFAULT NULL  -- NEW: SitC chain hash for EC-020
)
RETURNS uuid
LANGUAGE plpgsql
AS $function$
DECLARE
    v_needle_id UUID;
BEGIN
    -- Validate EQS threshold (constitutional constraint)
    IF p_eqs_score < 0.85 THEN
        RAISE EXCEPTION 'G3 VIOLATION: Cannot persist hypothesis with EQS < 0.85. EQS=% is below threshold.', p_eqs_score;
    END IF;

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
        chain_of_query_hash,
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
        g2_exam_session_id
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
        p_chain_of_query_hash,
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
        p_g2_exam_session_id
    ) RETURNING needle_id INTO v_needle_id;

    RETURN v_needle_id;
END;
$function$;

-- Also create a helper function to populate chain_of_query_hash for existing needles
CREATE OR REPLACE FUNCTION fhq_canonical.populate_sitc_chain_hash(
    p_needle_id uuid,
    p_chain_hash text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
BEGIN
    UPDATE fhq_canonical.golden_needles
    SET chain_of_query_hash = p_chain_hash
    WHERE needle_id = p_needle_id;
END;
$function$;

COMMIT;
