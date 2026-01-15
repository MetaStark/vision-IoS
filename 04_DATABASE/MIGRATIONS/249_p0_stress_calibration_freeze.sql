-- =============================================================================
-- Migration 249: P0 STRESS Regime Calibration Freeze
-- =============================================================================
-- CEO Directive: Regime Ontology Integrity Remediation
-- Priority: P0 (Critical - Immediate Containment)
--
-- PURPOSE: Eliminate systematic over-confidence in STRESS regime predictions
--          by enforcing hard confidence ceiling.
--
-- ROOT CAUSE (PROVEN):
--   - STRESS forecast uses: fragility_score > 0.80 OR VIX_SPIKE (macro signal)
--   - STRESS outcome uses: vol_ratio > 2.0 AND |return| < vol (price signal)
--   - Result: 0% hit rate on 75 predictions (definition mismatch)
--
-- APPROACH:
--   1. Insert STRESS calibration gates (idempotent)
--   2. Add eligible_for_calibration flag to brier_score_ledger
--   3. Mark existing STRESS entries as ineligible for calibration aggregates
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
-- STEP 1: Insert STRESS calibration gates (IDEMPOTENT)
-- -----------------------------------------------------------------------------
-- brier_score_ledger uses forecast_type = 'REGIME_CLASSIFICATION'
-- forecast_confidence_damper may use forecast_type = 'REGIME'
-- Insert gates for BOTH to ensure coverage

-- Gate for REGIME_CLASSIFICATION (matches brier_score_ledger)
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type,
    regime,
    confidence_band_min,
    confidence_band_max,
    historical_accuracy,
    sample_size,
    confidence_ceiling,
    safety_margin,
    approved_by
)
SELECT
    'REGIME_CLASSIFICATION',
    'STRESS',
    0.00,
    1.00,
    0.00,    -- 0% hit rate (proven)
    75,      -- Sample size from brier_score_ledger
    0.50,    -- Hard ceiling
    0.50,    -- Full margin due to definition mismatch
    'STIG'
WHERE NOT EXISTS (
    SELECT 1 FROM fhq_governance.confidence_calibration_gates
    WHERE forecast_type = 'REGIME_CLASSIFICATION' AND regime = 'STRESS'
);

-- Gate for REGIME (in case damper uses this forecast_type)
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type,
    regime,
    confidence_band_min,
    confidence_band_max,
    historical_accuracy,
    sample_size,
    confidence_ceiling,
    safety_margin,
    approved_by
)
SELECT
    'REGIME',
    'STRESS',
    0.00,
    1.00,
    0.00,    -- 0% hit rate
    75,      -- Sample size
    0.50,    -- Hard ceiling
    0.50,    -- Full margin
    'STIG'
WHERE NOT EXISTS (
    SELECT 1 FROM fhq_governance.confidence_calibration_gates
    WHERE forecast_type = 'REGIME' AND regime = 'STRESS'
);

-- Verification: Ensure both gates exist
DO $$
DECLARE
    gate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO gate_count
    FROM fhq_governance.confidence_calibration_gates
    WHERE regime = 'STRESS';

    IF gate_count < 2 THEN
        RAISE WARNING 'P0 STRESS gate insert incomplete: only % gates found (expected 2)', gate_count;
    ELSE
        RAISE NOTICE 'P0 STRESS gates verified: % gates active', gate_count;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- STEP 2: Add eligible_for_calibration flag to brier_score_ledger
-- -----------------------------------------------------------------------------
-- This flag excludes entries from calibration aggregates without deleting data
-- Semantics: FALSE = forecast/outcome definition mismatch, excluded from stats

ALTER TABLE fhq_governance.brier_score_ledger
ADD COLUMN IF NOT EXISTS eligible_for_calibration BOOLEAN DEFAULT true;

COMMENT ON COLUMN fhq_governance.brier_score_ledger.eligible_for_calibration IS
'P0: FALSE = forecast/outcome definition mismatch, excluded from calibration aggregates. Does not invalidate measurement, only excludes from calibration statistics. Added per CEO-DIR Regime Ontology Remediation 2026-01-15.';

-- -----------------------------------------------------------------------------
-- STEP 3: Mark existing STRESS entries as ineligible for calibration
-- -----------------------------------------------------------------------------
-- This is scope exclusion, not data massage

UPDATE fhq_governance.brier_score_ledger
SET eligible_for_calibration = false
WHERE regime = 'STRESS'
  AND eligible_for_calibration IS DISTINCT FROM false;

-- Log how many rows were affected
DO $$
DECLARE
    affected_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO affected_count
    FROM fhq_governance.brier_score_ledger
    WHERE regime = 'STRESS' AND eligible_for_calibration = false;

    RAISE NOTICE 'P0: Marked % STRESS entries as ineligible for calibration', affected_count;
END $$;

-- -----------------------------------------------------------------------------
-- VERIFICATION QUERIES (for manual review)
-- -----------------------------------------------------------------------------
-- Run these after migration to confirm success:
--
-- 1. Confirm BOTH calibration gates exist:
--    SELECT forecast_type, regime, confidence_ceiling
--    FROM fhq_governance.confidence_calibration_gates
--    WHERE regime = 'STRESS';
--    -- Expected: 2 rows (REGIME_CLASSIFICATION + REGIME)
--
-- 2. Confirm eligible_for_calibration column exists and STRESS marked:
--    SELECT regime, eligible_for_calibration, COUNT(*)
--    FROM fhq_governance.brier_score_ledger
--    WHERE regime = 'STRESS'
--    GROUP BY regime, eligible_for_calibration;
--    -- Expected: eligible_for_calibration = false for all STRESS
-- -----------------------------------------------------------------------------

COMMIT;
