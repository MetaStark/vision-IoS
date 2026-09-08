-- ============================================================================
-- CEO-DIR-2026-021 AUDIT CORRECTION #3
-- Opportunity Cost v1: Binary Classification Only
-- ============================================================================
-- Date: 2026-01-08
-- Authority: CEO Directive CEO-DIR-2026-021
-- Classification: P0 - Blocking All Learning
-- Purpose: Remove monetary placeholders, implement court-proof binary classification
--
-- Audit Correction #3: Lock opportunity cost formula (v1 definition)
--   - v1 = classification only (REGRET vs WISDOM)
--   - Magnitude = dimensionless confidence_gap, NOT money
--   - Monetary/alpha computation deferred to v2 (post paper-trading baseline)
--
-- Matching Window Extension: [-24h, +72h] to account for batch write lag
-- ============================================================================

-- Remove monetary placeholders from epistemic_suppression_ledger
-- Drop dependent view first
DROP VIEW IF EXISTS fhq_governance.v_suppression_summary CASCADE;

ALTER TABLE fhq_governance.epistemic_suppression_ledger
DROP COLUMN IF EXISTS opportunity_cost_estimated,
DROP COLUMN IF EXISTS opportunity_cost_realized;

-- Add v1 binary classification fields
ALTER TABLE fhq_governance.epistemic_suppression_ledger
ADD COLUMN IF NOT EXISTS regret_classification TEXT
    CHECK (regret_classification IN ('REGRET', 'WISDOM', 'UNRESOLVED')),
ADD COLUMN IF NOT EXISTS regret_magnitude NUMERIC CHECK (regret_magnitude BETWEEN 0 AND 1),
ADD COLUMN IF NOT EXISTS regret_computed_at TIMESTAMPTZ;

COMMENT ON COLUMN fhq_governance.epistemic_suppression_ledger.regret_classification IS
'CEO-DIR-2026-021 Audit Correction #3: v1 binary classification only.
REGRET = belief was correct (suppression was a mistake - missed alpha)
WISDOM = belief was wrong (suppression was wise - avoided loss)
UNRESOLVED = no outcome available for classification
NO MONETARY VALUES in v1. Monetary alpha deferred to v2 post paper-trading baseline.';

COMMENT ON COLUMN fhq_governance.epistemic_suppression_ledger.regret_magnitude IS
'v1: Dimensionless confidence gap (suppressed_confidence - chosen_confidence).
Represents strength of belief disagreement, NOT dollar value or alpha percentage.
Range: 0.0 to 1.0. Higher = stronger disagreement.';

COMMENT ON COLUMN fhq_governance.epistemic_suppression_ledger.regret_computed_at IS
'Timestamp of regret classification computation';

-- ============================================================================
-- Classification Function with Extended Window
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.classify_suppression_regret()
RETURNS TABLE(
    updated_count INTEGER,
    regret_count INTEGER,
    wisdom_count INTEGER,
    unresolved_count INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INTEGER := 0;
    v_regret INTEGER := 0;
    v_wisdom INTEGER := 0;
    v_unresolved INTEGER := 0;
BEGIN
    -- Classify suppressions with extended window [-24h, +72h]
    WITH outcome_matches AS (
        SELECT
            esl.suppression_id,
            mbs.dominant_regime,
            esl.suppressed_confidence,
            esl.chosen_confidence,
            (
                SELECT ol.outcome_value
                FROM fhq_research.outcome_ledger ol
                WHERE ol.outcome_domain = esl.asset_id
                  AND ol.outcome_type = 'REGIME'
                  AND ol.outcome_timestamp BETWEEN
                      mbs.belief_timestamp - INTERVAL '24 hours'
                      AND mbs.belief_timestamp + INTERVAL '72 hours'
                ORDER BY ABS(EXTRACT(EPOCH FROM (ol.outcome_timestamp - mbs.belief_timestamp))) ASC
                LIMIT 1
            ) as outcome_value
        FROM fhq_governance.epistemic_suppression_ledger esl
        JOIN fhq_perception.model_belief_state mbs ON esl.belief_id = mbs.belief_id
        WHERE esl.regret_classification IS NULL
    ),
    classification AS (
        UPDATE fhq_governance.epistemic_suppression_ledger esl
        SET
            regret_classification = (
                CASE
                    WHEN om.outcome_value IS NULL THEN 'UNRESOLVED'
                    WHEN om.dominant_regime = om.outcome_value THEN 'REGRET'
                    ELSE 'WISDOM'
                END
            ),
            regret_magnitude = ABS(om.suppressed_confidence - om.chosen_confidence),
            regret_computed_at = NOW()
        FROM outcome_matches om
        WHERE esl.suppression_id = om.suppression_id
        RETURNING esl.regret_classification
    )
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE regret_classification = 'REGRET'),
        COUNT(*) FILTER (WHERE regret_classification = 'WISDOM'),
        COUNT(*) FILTER (WHERE regret_classification = 'UNRESOLVED')
    INTO v_updated, v_regret, v_wisdom, v_unresolved
    FROM classification;

    -- Emit evidence to governance log
    INSERT INTO fhq_governance.governance_actions_log (
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        decision,
        decision_rationale,
        metadata
    ) VALUES (
        'REGRET_CLASSIFICATION',
        'epistemic_suppression_ledger',
        'LEARNING_PIPELINE',
        'STIG',
        'CLASSIFIED',
        'CEO-DIR-2026-021 Audit Correction #3: Binary classification complete',
        jsonb_build_object(
            'updated_count', v_updated,
            'regret_count', v_regret,
            'wisdom_count', v_wisdom,
            'unresolved_count', v_unresolved,
            'matching_window', '[-24h, +72h]',
            'v1_definition', 'binary_classification_only',
            'timestamp', NOW()
        )
    );

    RETURN QUERY SELECT v_updated, v_regret, v_wisdom, v_unresolved;
END;
$$;

COMMENT ON FUNCTION fhq_governance.classify_suppression_regret IS
'CEO-DIR-2026-021 Audit Correction #3: v1 binary classification (no monetary value).
Extended matching window: [-24h, +72h] to account for outcome batch write lag.
Closest outcome match within window is selected by minimum absolute time delta.
v2 will add price-based realized alpha after paper trading baseline established.';

-- ============================================================================
-- Execute Classification on Existing Suppressions
-- ============================================================================

DO $$
DECLARE
    v_result RECORD;
BEGIN
    RAISE NOTICE 'Classifying existing suppressions with extended window...';

    SELECT * INTO v_result
    FROM fhq_governance.classify_suppression_regret();

    RAISE NOTICE 'Classification complete:';
    RAISE NOTICE '  Updated: % suppressions', v_result.updated_count;
    RAISE NOTICE '  REGRET: % (belief was correct, suppression was mistake)', v_result.regret_count;
    RAISE NOTICE '  WISDOM: % (belief was wrong, suppression was wise)', v_result.wisdom_count;
    RAISE NOTICE '  UNRESOLVED: % (no outcome data)', v_result.unresolved_count;
END $$;

-- ============================================================================
-- Validation
-- ============================================================================

DO $$
DECLARE
    v_unclassified INTEGER;
    v_invalid_magnitude INTEGER;
BEGIN
    -- Check all suppressions with outcomes are classified
    SELECT COUNT(*) INTO v_unclassified
    FROM fhq_governance.epistemic_suppression_ledger esl
    JOIN fhq_perception.model_belief_state mbs ON esl.belief_id = mbs.belief_id
    WHERE EXISTS (
        SELECT 1 FROM fhq_research.outcome_ledger ol
        WHERE ol.outcome_domain = esl.asset_id
          AND ol.outcome_type = 'REGIME'
          AND ol.outcome_timestamp BETWEEN
              mbs.belief_timestamp - INTERVAL '24 hours'
              AND mbs.belief_timestamp + INTERVAL '72 hours'
    )
    AND esl.regret_classification IS NULL;

    IF v_unclassified > 0 THEN
        RAISE EXCEPTION 'Validation failed: % suppressions with outcomes remain unclassified', v_unclassified;
    END IF;

    -- Check magnitude is in valid range
    SELECT COUNT(*) INTO v_invalid_magnitude
    FROM fhq_governance.epistemic_suppression_ledger
    WHERE regret_magnitude IS NOT NULL
      AND (regret_magnitude < 0 OR regret_magnitude > 1);

    IF v_invalid_magnitude > 0 THEN
        RAISE EXCEPTION 'Validation failed: % suppressions have invalid magnitude (outside 0-1)', v_invalid_magnitude;
    END IF;

    RAISE NOTICE 'Validation passed:';
    RAISE NOTICE '  All suppressions with outcomes classified';
    RAISE NOTICE '  All magnitudes within valid range [0, 1]';
END $$;

-- Log migration completion
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MIGRATION_EXECUTION',
    '214_ceo_dir_2026_021_audit_correction_3',
    'DATABASE_SCHEMA',
    'STIG',
    'COMPLETED',
    'CEO-DIR-2026-021 Audit Correction #3: Binary regret classification (v1)',
    jsonb_build_object(
        'migration_file', '214_ceo_dir_2026_021_audit_correction_3.sql',
        'correction', 'AUDIT_CORRECTION_3',
        'tables_modified', ARRAY['epistemic_suppression_ledger'],
        'columns_dropped', ARRAY['opportunity_cost_estimated', 'opportunity_cost_realized'],
        'columns_added', ARRAY['regret_classification', 'regret_magnitude', 'regret_computed_at'],
        'matching_window', '[-24h, +72h]',
        'v1_definition', 'binary_classification_only',
        'v2_deferred_to', 'post_paper_trading_baseline',
        'validation_status', 'PASS'
    )
);

-- Court-proof: Record schema change hash
SELECT
    'MIGRATION_214' as migration_id,
    encode(sha256(
        ('214_ceo_dir_2026_021_audit_correction_3.sql' ||
         NOW()::text)::bytea
    ), 'hex') as execution_hash,
    NOW() as executed_at;
