-- Migration 282: G4 Regime Confidence Ceilings (Direct Insert)
-- CEO Execution Order: Kill Overconfidence
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Direct insert of CEO-approved regime confidence ceilings

-- ============================================================================
-- DIRECT INSERT OF REGIME CONFIDENCE CEILINGS
-- ============================================================================

-- STRESS regime: 0.10 ceiling (0% hit rate = no confidence warranted)
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type, regime, confidence_band_min, confidence_band_max,
    historical_accuracy, sample_size, confidence_ceiling, safety_margin,
    calculation_window_days, effective_from, approved_by, approval_timestamp
) VALUES (
    'PRICE_DIRECTION', 'STRESS', 0.0, 1.0,
    0.0000, 101, 0.10, 0.10,
    30, NOW(), 'CEO', NOW()
);

-- BULL regime: 0.35 ceiling (25% hit rate)
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type, regime, confidence_band_min, confidence_band_max,
    historical_accuracy, sample_size, confidence_ceiling, safety_margin,
    calculation_window_days, effective_from, approved_by, approval_timestamp
) VALUES (
    'PRICE_DIRECTION', 'BULL', 0.0, 1.0,
    0.2528, 1495, 0.35, 0.10,
    30, NOW(), 'CEO', NOW()
);

-- NEUTRAL regime: 0.39 ceiling (29% hit rate)
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type, regime, confidence_band_min, confidence_band_max,
    historical_accuracy, sample_size, confidence_ceiling, safety_margin,
    calculation_window_days, effective_from, approved_by, approval_timestamp
) VALUES (
    'PRICE_DIRECTION', 'NEUTRAL', 0.0, 1.0,
    0.2886, 1275, 0.39, 0.10,
    30, NOW(), 'CEO', NOW()
);

-- BEAR regime: 0.43 ceiling (33% hit rate)
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type, regime, confidence_band_min, confidence_band_max,
    historical_accuracy, sample_size, confidence_ceiling, safety_margin,
    calculation_window_days, effective_from, approved_by, approval_timestamp
) VALUES (
    'PRICE_DIRECTION', 'BEAR', 0.0, 1.0,
    0.3260, 730, 0.43, 0.10,
    30, NOW(), 'CEO', NOW()
);

-- Update existing STRESS gates to match
UPDATE fhq_governance.confidence_calibration_gates
SET confidence_ceiling = 0.10,
    approved_by = 'CEO',
    approval_timestamp = NOW()
WHERE regime = 'STRESS';

-- Verification
DO $$
DECLARE
    ceiling_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO ceiling_count
    FROM fhq_governance.confidence_calibration_gates
    WHERE approved_by = 'CEO'
    AND regime IN ('STRESS', 'BULL', 'NEUTRAL', 'BEAR');

    RAISE NOTICE 'CEO-approved regime ceilings: %', ceiling_count;
END $$;

-- Display new ceilings
SELECT regime, forecast_type, confidence_ceiling, historical_accuracy, approved_by
FROM fhq_governance.confidence_calibration_gates
WHERE regime IN ('STRESS', 'BULL', 'NEUTRAL', 'BEAR')
ORDER BY regime;
