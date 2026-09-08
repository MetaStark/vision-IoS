-- =============================================================================
-- Migration 250: P1 Regime Ontology Alignment
-- =============================================================================
-- CEO Directive: Regime Ontology Integrity Remediation
-- Priority: P1 (Important - Structural Repair)
-- Depends On: Migration 249 (P0 STRESS Freeze)
--
-- PURPOSE: Establish canonical regime ontology with explicit equivalence status
--          and downstream contracts for all regime types.
--
-- APPROACH:
--   1. Extend regime_v2_to_v4_mapping with definition columns
--   2. Update BROKEN and VOLATILE_NON_DIRECTIONAL to identity mappings
--   3. Populate definitions and downstream contracts for all regimes
--   4. Add VOLATILE_NON_DIRECTIONAL to regime_scalar_config
--
-- CONSTRAINTS:
--   - No new tables
--   - No new models
--   - Database-first, governance-first
--
-- AUTHOR: STIG (System for Technical Implementation & Governance)
-- APPROVED BY: CEO via Plan Mode v3
-- DATE: 2026-01-15
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- STEP 1: Extend regime_v2_to_v4_mapping with ontology columns
-- -----------------------------------------------------------------------------

ALTER TABLE fhq_perception.regime_v2_to_v4_mapping
ADD COLUMN IF NOT EXISTS forecast_definition TEXT,
ADD COLUMN IF NOT EXISTS outcome_definition TEXT,
ADD COLUMN IF NOT EXISTS definition_equivalent BOOLEAN DEFAULT NULL,
ADD COLUMN IF NOT EXISTS equivalence_proof TEXT,
ADD COLUMN IF NOT EXISTS effective_date DATE DEFAULT CURRENT_DATE,
ADD COLUMN IF NOT EXISTS migration_notes TEXT,
ADD COLUMN IF NOT EXISTS downstream_contract TEXT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN fhq_perception.regime_v2_to_v4_mapping.definition_equivalent IS
'NULL = unproven, TRUE = proven equivalent, FALSE = proven non-equivalent. Only STIG may set TRUE after formal verification. Added per CEO-DIR Regime Ontology Remediation 2026-01-15.';

COMMENT ON COLUMN fhq_perception.regime_v2_to_v4_mapping.downstream_contract IS
'Specifies how downstream systems (execution, sizing, needles) should handle this regime.';

-- -----------------------------------------------------------------------------
-- STEP 2: Update BROKEN and VOLATILE_NON_DIRECTIONAL to identity mappings
-- -----------------------------------------------------------------------------
-- These were incorrectly mapped to STRESS, causing definition mismatch

UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    v4_regime = 'BROKEN',
    mapping_confidence = 1.0,
    forecast_definition = 'Data quality regime: Insufficient/corrupted data to classify.',
    outcome_definition = 'Same as forecast (identity mapping)',
    definition_equivalent = TRUE,
    equivalence_proof = 'Identity mapping: V2 and V4 are same label.',
    downstream_contract = 'EXISTING: scalar_value=0.0 (full cash) in regime_scalar_config. No change needed.',
    migration_notes = 'P1 RESOLVED: No longer mapped to STRESS. Existing scalar=0.0 provides correct handling.',
    updated_at = NOW()
WHERE v2_regime = 'BROKEN';

UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    v4_regime = 'VOLATILE_NON_DIRECTIONAL',
    mapping_confidence = 1.0,
    forecast_definition = 'Outcome-only regime: vol_ratio > 2.0 AND |return| < vol. NOT predicted by HMM.',
    outcome_definition = 'Same as forecast (identity mapping)',
    definition_equivalent = TRUE,
    equivalence_proof = 'Identity mapping: V2 and V4 are same label.',
    downstream_contract = 'MAP TO NEUTRAL in execution layer. Reason: No scalar defined. Treatment: regime_scalar_config fallback to NEUTRAL (0.5)',
    migration_notes = 'P1 RESOLVED: No longer mapped to STRESS. Downstream uses NEUTRAL scalar.',
    updated_at = NOW()
WHERE v2_regime = 'VOLATILE_NON_DIRECTIONAL';

-- -----------------------------------------------------------------------------
-- STEP 3: Populate definitions for core regimes (NULL equivalence = unproven)
-- -----------------------------------------------------------------------------

-- BULL: UNPROVEN
UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    forecast_definition = 'HMM posterior probability for BULL state. Uses return, volatility, volume features. May be modified by CRIO rules.',
    outcome_definition = 'Independent regime: return_20d > 0.5*vol AND return > 0. Source: ios003_independent_regime_outcome.py:229-233',
    definition_equivalent = NULL,
    equivalence_proof = 'PENDING: STIG must verify that HMM BULL definition aligns with outcome definition. Current hit rate = 27.6% suggests partial alignment.',
    downstream_contract = 'ACTIVE: scalar_value via regime_scalar_config',
    updated_at = NOW()
WHERE v2_regime = 'BULL' AND forecast_definition IS NULL;

-- STRONG_BULL
UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    forecast_definition = 'HMM BULL state with high posterior probability (>0.85). Strong directional conviction.',
    outcome_definition = 'Maps to BULL outcome. Source: ios003_independent_regime_outcome.py',
    definition_equivalent = NULL,
    equivalence_proof = 'PENDING: Verification through BULL outcome.',
    downstream_contract = 'ACTIVE: scalar_value=1.0 via regime_scalar_config',
    updated_at = NOW()
WHERE v2_regime = 'STRONG_BULL' AND forecast_definition IS NULL;

-- BEAR: UNPROVEN
UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    forecast_definition = 'HMM posterior probability for BEAR state. Uses return, volatility, volume features. May be modified by CRIO rules.',
    outcome_definition = 'Independent regime: return_20d < -0.5*vol AND return < 0. Source: ios003_independent_regime_outcome.py:241-245',
    definition_equivalent = NULL,
    equivalence_proof = 'PENDING: STIG must verify. Current hit rate = 33.8% (best performer) suggests reasonable alignment.',
    downstream_contract = 'ACTIVE: scalar_value=0.0 (full cash) via regime_scalar_config',
    updated_at = NOW()
WHERE v2_regime = 'BEAR' AND forecast_definition IS NULL;

-- STRONG_BEAR
UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    forecast_definition = 'HMM BEAR state with high posterior probability (>0.85). Strong directional conviction.',
    outcome_definition = 'Maps to BEAR outcome. Source: ios003_independent_regime_outcome.py',
    definition_equivalent = NULL,
    equivalence_proof = 'PENDING: Verification through BEAR outcome.',
    downstream_contract = 'ACTIVE: scalar_value=0.0 via regime_scalar_config',
    updated_at = NOW()
WHERE v2_regime = 'STRONG_BEAR' AND forecast_definition IS NULL;

-- NEUTRAL: UNPROVEN
UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    forecast_definition = 'HMM posterior probability for NEUTRAL state. Low directional conviction.',
    outcome_definition = 'Independent regime: |return_20d| < 0.5*vol. Source: ios003_independent_regime_outcome.py:248-251',
    definition_equivalent = NULL,
    equivalence_proof = 'PENDING: STIG must verify. Current hit rate = 28.4%.',
    downstream_contract = 'ACTIVE: scalar_value=0.5 via regime_scalar_config',
    updated_at = NOW()
WHERE v2_regime = 'NEUTRAL' AND forecast_definition IS NULL;

-- COMPRESSION (maps to NEUTRAL)
UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    forecast_definition = 'Low volatility consolidation regime. Mapped to NEUTRAL for execution.',
    outcome_definition = 'Uses NEUTRAL outcome definition',
    definition_equivalent = NULL,
    equivalence_proof = 'PENDING: Compression may precede breakout, verify NEUTRAL alignment.',
    downstream_contract = 'ACTIVE: Uses NEUTRAL scalar_value=0.5',
    updated_at = NOW()
WHERE v2_regime = 'COMPRESSION' AND forecast_definition IS NULL;

-- UNTRUSTED (maps to NEUTRAL)
UPDATE fhq_perception.regime_v2_to_v4_mapping
SET
    forecast_definition = 'Data quality concern: Insufficient confidence to classify. Defensive mapping to NEUTRAL.',
    outcome_definition = 'Uses NEUTRAL outcome definition',
    definition_equivalent = NULL,
    equivalence_proof = 'N/A: Defensive mapping, not semantic equivalence.',
    downstream_contract = 'ACTIVE: Uses NEUTRAL scalar_value=0.5 (defensive)',
    updated_at = NOW()
WHERE v2_regime = 'UNTRUSTED' AND forecast_definition IS NULL;

-- -----------------------------------------------------------------------------
-- STEP 4: Add VOLATILE_NON_DIRECTIONAL to regime_scalar_config
-- -----------------------------------------------------------------------------

INSERT INTO fhq_governance.regime_scalar_config (
    regime_label,
    scalar_value,
    mode,
    description,
    is_active,
    created_by
) VALUES (
    'VOLATILE_NON_DIRECTIONAL',
    0.25,
    'LONG_ONLY',
    'P1: High volatility non-directional regime. Reduce exposure. Added per CEO-DIR Regime Ontology Remediation 2026-01-15.',
    true,
    'STIG'
) ON CONFLICT (regime_label) DO NOTHING;

-- -----------------------------------------------------------------------------
-- STEP 5: CRITICAL - Verify no remaining STRESS mappings
-- -----------------------------------------------------------------------------

DO $$
DECLARE
    stress_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO stress_count
    FROM fhq_perception.regime_v2_to_v4_mapping
    WHERE v4_regime = 'STRESS';

    IF stress_count > 0 THEN
        RAISE EXCEPTION 'P1 INCOMPLETE: % rows still map to STRESS. Must remap or remove.', stress_count;
    ELSE
        RAISE NOTICE 'P1 VERIFIED: No remaining STRESS mappings';
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- STEP 6: Verification summary
-- -----------------------------------------------------------------------------

DO $$
DECLARE
    mapping_count INTEGER;
    defined_count INTEGER;
    vnd_scalar NUMERIC;
BEGIN
    SELECT COUNT(*), COUNT(forecast_definition)
    INTO mapping_count, defined_count
    FROM fhq_perception.regime_v2_to_v4_mapping;

    SELECT scalar_value INTO vnd_scalar
    FROM fhq_governance.regime_scalar_config
    WHERE regime_label = 'VOLATILE_NON_DIRECTIONAL';

    RAISE NOTICE 'P1 Summary: % mappings, % with definitions, VND scalar=%',
        mapping_count, defined_count, COALESCE(vnd_scalar::TEXT, 'MISSING');
END $$;

-- -----------------------------------------------------------------------------
-- VERIFICATION QUERIES (for manual review)
-- -----------------------------------------------------------------------------
-- 1. Confirm all definitions populated:
--    SELECT v2_regime, v4_regime, definition_equivalent,
--           CASE WHEN forecast_definition IS NULL THEN 'MISSING' ELSE 'OK' END as forecast_def,
--           CASE WHEN downstream_contract IS NULL THEN 'MISSING' ELSE 'OK' END as downstream
--    FROM fhq_perception.regime_v2_to_v4_mapping;
--
-- 2. Confirm NULL equivalence for unproven regimes:
--    SELECT v4_regime, definition_equivalent
--    FROM fhq_perception.regime_v2_to_v4_mapping
--    WHERE v4_regime IN ('BULL', 'BEAR', 'NEUTRAL');
--    -- Expected: definition_equivalent = NULL
--
-- 3. Confirm STRESS removed from mapping:
--    SELECT * FROM fhq_perception.regime_v2_to_v4_mapping
--    WHERE v4_regime = 'STRESS';
--    -- Expected: 0 rows
--
-- 4. Confirm VOLATILE_NON_DIRECTIONAL has scalar:
--    SELECT regime_label, scalar_value
--    FROM fhq_governance.regime_scalar_config
--    WHERE regime_label = 'VOLATILE_NON_DIRECTIONAL';
--    -- Expected: 1 row with scalar_value = 0.25
-- -----------------------------------------------------------------------------

COMMIT;
