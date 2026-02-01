-- ============================================================================
-- CEO-DIR-2026-019: ACI 1.0 LEARNING ACTIVATION
-- Migration 212: Fix regret computation + Cognitive Fasting state
-- ============================================================================
-- STIG Implementation | P0-1.1 and P0-2.3 Requirements
-- Generated: 2026-01-07
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART 1: FIX compute_suppression_regret() to use 'REGIME' not 'REGIME_CLASSIFICATION'
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.compute_suppression_regret(
    p_period_start timestamp with time zone,
    p_period_end timestamp with time zone
)
RETURNS uuid
LANGUAGE plpgsql
AS $function$
DECLARE
    v_regret_id UUID;
    v_total INTEGER;
    v_correct INTEGER;
    v_regrettable INTEGER;
    v_regret_rate NUMERIC;
    v_wisdom_rate NUMERIC;
    v_regret_by_regime JSONB;
    v_regret_by_asset JSONB;
    v_hash TEXT;
BEGIN
    -- Count suppressions with reconciled outcomes
    -- CEO-DIR-2026-019: Fixed outcome_type from 'REGIME_CLASSIFICATION' to 'REGIME'
    WITH suppression_outcomes AS (
        SELECT
            esl.suppression_id,
            esl.asset_id,
            mbs.dominant_regime AS believed_regime,
            sps.chosen_regime AS policy_regime,
            o.outcome_value AS realized_regime,
            CASE
                WHEN mbs.dominant_regime = o.outcome_value THEN 'REGRET'  -- belief was correct, should not have suppressed
                ELSE 'WISDOM'  -- belief was wrong, suppression was wise
            END AS regret_classification
        FROM fhq_governance.epistemic_suppression_ledger esl
        JOIN fhq_perception.model_belief_state mbs ON esl.belief_id = mbs.belief_id
        JOIN fhq_perception.sovereign_policy_state sps ON esl.policy_id = sps.policy_id
        LEFT JOIN LATERAL (
            SELECT ol.outcome_value
            FROM fhq_research.outcome_ledger ol
            WHERE ol.outcome_domain = esl.asset_id
              AND ol.outcome_type = 'REGIME'  -- FIXED: was 'REGIME_CLASSIFICATION'
              AND ol.outcome_timestamp BETWEEN mbs.belief_timestamp AND mbs.belief_timestamp + INTERVAL '48 hours'
            ORDER BY ol.outcome_timestamp ASC
            LIMIT 1
        ) o ON TRUE
        WHERE esl.suppression_timestamp BETWEEN p_period_start AND p_period_end
          AND o.outcome_value IS NOT NULL
    )
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE regret_classification = 'WISDOM'),
        COUNT(*) FILTER (WHERE regret_classification = 'REGRET')
    INTO v_total, v_correct, v_regrettable
    FROM suppression_outcomes;

    IF v_total = 0 THEN
        v_regret_rate := 0;
        v_wisdom_rate := 0;
    ELSE
        v_regret_rate := v_regrettable::numeric / v_total;
        v_wisdom_rate := v_correct::numeric / v_total;
    END IF;

    -- Compute breakdown by regime
    WITH regime_breakdown AS (
        SELECT
            mbs.dominant_regime,
            COUNT(*) FILTER (WHERE mbs.dominant_regime = o.outcome_value) AS regret_count,
            COUNT(*) AS total_count
        FROM fhq_governance.epistemic_suppression_ledger esl
        JOIN fhq_perception.model_belief_state mbs ON esl.belief_id = mbs.belief_id
        LEFT JOIN LATERAL (
            SELECT ol.outcome_value
            FROM fhq_research.outcome_ledger ol
            WHERE ol.outcome_domain = esl.asset_id
              AND ol.outcome_type = 'REGIME'
              AND ol.outcome_timestamp BETWEEN mbs.belief_timestamp AND mbs.belief_timestamp + INTERVAL '48 hours'
            LIMIT 1
        ) o ON TRUE
        WHERE esl.suppression_timestamp BETWEEN p_period_start AND p_period_end
        GROUP BY mbs.dominant_regime
    )
    SELECT jsonb_object_agg(dominant_regime, jsonb_build_object('regret', regret_count, 'total', total_count))
    INTO v_regret_by_regime
    FROM regime_breakdown;

    -- Compute breakdown by asset
    WITH asset_breakdown AS (
        SELECT
            esl.asset_id,
            COUNT(*) FILTER (WHERE mbs.dominant_regime = o.outcome_value) AS regret_count,
            COUNT(*) AS total_count
        FROM fhq_governance.epistemic_suppression_ledger esl
        JOIN fhq_perception.model_belief_state mbs ON esl.belief_id = mbs.belief_id
        LEFT JOIN LATERAL (
            SELECT ol.outcome_value
            FROM fhq_research.outcome_ledger ol
            WHERE ol.outcome_domain = esl.asset_id
              AND ol.outcome_type = 'REGIME'
            LIMIT 1
        ) o ON TRUE
        WHERE esl.suppression_timestamp BETWEEN p_period_start AND p_period_end
        GROUP BY esl.asset_id
        ORDER BY regret_count DESC
        LIMIT 20
    )
    SELECT jsonb_object_agg(asset_id, jsonb_build_object('regret', regret_count, 'total', total_count))
    INTO v_regret_by_asset
    FROM asset_breakdown;

    -- Compute court-proof hash
    v_hash := encode(sha256(
        (p_period_start::text || p_period_end::text || v_total::text ||
         v_regret_rate::text || v_wisdom_rate::text)::bytea
    ), 'hex');

    -- Insert record
    INSERT INTO fhq_governance.suppression_regret_index (
        period_start, period_end,
        total_suppressions, correct_suppressions, regrettable_suppressions,
        suppression_regret_rate, suppression_wisdom_rate,
        regret_by_regime, regret_by_asset,
        computation_hash
    ) VALUES (
        p_period_start, p_period_end,
        v_total, v_correct, v_regrettable,
        v_regret_rate, v_wisdom_rate,
        COALESCE(v_regret_by_regime, '{}'::jsonb),
        COALESCE(v_regret_by_asset, '{}'::jsonb),
        v_hash
    )
    RETURNING regret_id INTO v_regret_id;

    RETURN v_regret_id;
END;
$function$;

COMMENT ON FUNCTION fhq_governance.compute_suppression_regret IS
'CEO-DIR-2026-019 P0-1: Compute regret metrics for suppressions in a time period.
REGRET = belief was correct (suppression was a mistake)
WISDOM = belief was wrong (suppression was wise)
Fixed 2026-01-07: outcome_type REGIME_CLASSIFICATION -> REGIME';

-- ============================================================================
-- PART 2: COGNITIVE FASTING STATE (P0-2.3)
-- ============================================================================

-- Add cognitive fasting columns to execution_state
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_governance'
        AND table_name = 'execution_state'
        AND column_name = 'cognitive_fasting'
    ) THEN
        ALTER TABLE fhq_governance.execution_state
        ADD COLUMN cognitive_fasting BOOLEAN DEFAULT FALSE,
        ADD COLUMN fasting_reason TEXT,
        ADD COLUMN fasting_started_at TIMESTAMPTZ,
        ADD COLUMN fasting_max_duration_hours INTEGER DEFAULT 24,
        ADD COLUMN revalidation_required BOOLEAN DEFAULT FALSE,
        ADD COLUMN last_cnrp_completion TIMESTAMPTZ,
        ADD COLUMN fasting_requires_ceo_override BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

COMMENT ON COLUMN fhq_governance.execution_state.cognitive_fasting IS
'CEO-DIR-2026-019 P0-2: TRUE when LIDS gates block execution pending revalidation';

COMMENT ON COLUMN fhq_governance.execution_state.fasting_reason IS
'Why the system entered cognitive fasting (e.g., confidence < 0.70, freshness > 12h)';

COMMENT ON COLUMN fhq_governance.execution_state.fasting_started_at IS
'When cognitive fasting began';

COMMENT ON COLUMN fhq_governance.execution_state.fasting_max_duration_hours IS
'Maximum fasting duration before requiring CEO override (default 24h)';

COMMENT ON COLUMN fhq_governance.execution_state.revalidation_required IS
'TRUE if CNRP must complete before exiting fasting';

COMMENT ON COLUMN fhq_governance.execution_state.last_cnrp_completion IS
'Timestamp of last successful CNRP completion';

COMMENT ON COLUMN fhq_governance.execution_state.fasting_requires_ceo_override IS
'TRUE if fasting exceeded max duration and requires CEO intervention';

-- ============================================================================
-- PART 3: COGNITIVE FASTING EXIT FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.can_exit_cognitive_fasting(
    p_data_freshness_hours NUMERIC,
    p_belief_confidence NUMERIC,
    p_evidence_attachment_ok BOOLEAN,
    p_cnrp_completed BOOLEAN
)
RETURNS TABLE (
    can_exit BOOLEAN,
    exit_reason TEXT,
    blocking_conditions JSONB
)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_conditions JSONB;
BEGIN
    -- Build conditions object
    v_conditions := jsonb_build_object(
        'data_freshness_ok', p_data_freshness_hours <= 12,
        'confidence_ok', p_belief_confidence >= 0.70,
        'evidence_ok', p_evidence_attachment_ok,
        'cnrp_ok', p_cnrp_completed,
        'data_freshness_hours', p_data_freshness_hours,
        'belief_confidence', p_belief_confidence
    );

    -- CEO Presisering 4: ALL conditions must be TRUE to exit
    IF p_data_freshness_hours <= 12
       AND p_belief_confidence >= 0.70
       AND p_evidence_attachment_ok = TRUE
       AND p_cnrp_completed = TRUE
    THEN
        RETURN QUERY SELECT
            TRUE,
            'All exit conditions met - can resume execution'::TEXT,
            v_conditions;
    ELSE
        RETURN QUERY SELECT
            FALSE,
            CASE
                WHEN p_data_freshness_hours > 12 THEN 'Data freshness exceeds 12h threshold'
                WHEN p_belief_confidence < 0.70 THEN 'Confidence below 0.70 threshold'
                WHEN NOT p_evidence_attachment_ok THEN 'Evidence attachment failed'
                WHEN NOT p_cnrp_completed THEN 'CNRP not completed'
                ELSE 'Unknown blocking condition'
            END::TEXT,
            v_conditions;
    END IF;
END;
$function$;

COMMENT ON FUNCTION fhq_governance.can_exit_cognitive_fasting IS
'CEO-DIR-2026-019 Presisering 4: Mekanisk presis exit condition for cognitive fasting.
ALL conditions must be TRUE: freshness<=12h, confidence>=0.70, evidence_ok, cnrp_completed';

-- ============================================================================
-- PART 4: EVIDENCE BUNDLE TYPE TRACKING (CEO Presisering 5)
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_governance'
        AND table_name = 'epistemic_proposals'
        AND column_name = 'evidence_bundle_type'
    ) THEN
        ALTER TABLE fhq_governance.epistemic_proposals
        ADD COLUMN evidence_bundle_type VARCHAR(30)
        CHECK (evidence_bundle_type IN ('BACKFILL', 'LIVE', 'PROMOTION'));
    END IF;
END $$;

COMMENT ON COLUMN fhq_governance.epistemic_proposals.evidence_bundle_type IS
'CEO-DIR-2026-019 Presisering 5: Tre distinkte moduser - BACKFILL (historical), LIVE (ongoing), PROMOTION (activation)';

-- ============================================================================
-- PART 5: GOVERNANCE LOG ENTRY
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
    '212_ceo_dir_2026_019_learning_activation',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-019 P0-1.1 and P0-2.3 implementation',
    jsonb_build_object(
        'migration', '212_ceo_dir_2026_019_learning_activation',
        'directive', 'CEO-DIR-2026-019',
        'components', ARRAY['compute_suppression_regret fix', 'cognitive_fasting state', 'can_exit_cognitive_fasting', 'evidence_bundle_type'],
        'p0_blockers', ARRAY['P0-1.1', 'P0-2.3']
    )
);

COMMIT;

-- ============================================================================
-- POST-COMMIT: Run historical regret backfill for CEO-DIR-2026-019
-- ============================================================================
-- This will be executed after migration completes:
-- SELECT fhq_governance.compute_suppression_regret(
--     '2025-12-08'::timestamptz,
--     '2026-01-07'::timestamptz
-- );
