-- Migration 281: G4 FRICTION-001 Calibration Execution
-- CEO Execution Order: Kill Overconfidence
-- Date: 2026-01-17
-- Author: STIG
-- Authority: CEO Direct Order — "Calibration is not optimization. Calibration is RISK REMOVAL."

-- ============================================================================
-- G4 OPERATIONAL CALIBRATION — FRICTION-001 EXECUTION
-- ============================================================================
-- Baseline Reference: G3_BASELINE_DAY17
--   Brier: 0.5358
--   Hit Rate: 0.3265
--
-- CEO Approved Deltas (Non-Negotiable):
--   STRESS: 0.91 → 0.10 (91% gap → forced humility)
--   BULL:   0.92 → 0.35 (67% gap → aligned)
--   NEUTRAL:0.85 → 0.39 (57% gap → aligned)
--   BEAR:   0.86 → 0.43 (53% gap → aligned)
-- ============================================================================

-- Step 1: Record pre-execution state for rollback capability
CREATE TABLE IF NOT EXISTS fhq_governance.calibration_execution_log (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_batch TEXT NOT NULL,
    change_id UUID,
    target_table TEXT,
    target_column TEXT,
    target_filter JSONB,
    value_before NUMERIC,
    value_after NUMERIC,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    executed_by TEXT,
    rollback_executed BOOLEAN DEFAULT FALSE,
    measurement_at TIMESTAMPTZ,
    brier_before NUMERIC,
    brier_after NUMERIC,
    verdict TEXT
);

-- Step 2: Execute STRESS regime calibration (PRIORITY — 0% hit rate)
DO $$
DECLARE
    v_batch TEXT := 'FRICTION-001-G4-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MI');
BEGIN
    -- Log pre-execution state
    INSERT INTO fhq_governance.calibration_execution_log (
        execution_batch, change_id, target_table, target_column,
        target_filter, value_before, value_after, executed_by
    )
    SELECT
        v_batch,
        change_id,
        target_table,
        target_column,
        target_filter,
        current_value,
        proposed_value,
        'STIG'
    FROM fhq_governance.calibration_change_queue
    WHERE okr_code LIKE 'FRICTION-001%'
    AND status = 'QUEUED';

    RAISE NOTICE 'Execution batch: %', v_batch;
END $$;

-- Step 3: Create or update regime-specific confidence gates
-- STRESS regime: Force extreme humility (0% hit rate = no confidence warranted)
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type,
    regime,
    confidence_band_min,
    confidence_band_max,
    historical_accuracy,
    sample_size,
    confidence_ceiling,
    safety_margin,
    calculation_window_days,
    effective_from,
    approved_by,
    approval_timestamp
) VALUES (
    'PRICE_DIRECTION',
    'STRESS',
    0.0,
    1.0,
    0.0,  -- 0% hit rate observed
    101,  -- Sample size from analysis
    0.10, -- CEO approved ceiling
    0.10, -- Maximum safety margin
    30,
    NOW(),
    'CEO',
    NOW()
)
ON CONFLICT (forecast_type, regime, confidence_band_min, confidence_band_max)
    WHERE regime IS NOT NULL
DO UPDATE SET
    confidence_ceiling = 0.10,
    historical_accuracy = 0.0,
    approved_by = 'CEO',
    approval_timestamp = NOW();

-- BULL regime: Align with 25% hit rate
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type,
    regime,
    confidence_band_min,
    confidence_band_max,
    historical_accuracy,
    sample_size,
    confidence_ceiling,
    safety_margin,
    calculation_window_days,
    effective_from,
    approved_by,
    approval_timestamp
) VALUES (
    'PRICE_DIRECTION',
    'BULL',
    0.0,
    1.0,
    0.2528,
    1495,
    0.35, -- CEO approved ceiling
    0.10,
    30,
    NOW(),
    'CEO',
    NOW()
)
ON CONFLICT (forecast_type, regime, confidence_band_min, confidence_band_max)
    WHERE regime IS NOT NULL
DO UPDATE SET
    confidence_ceiling = 0.35,
    historical_accuracy = 0.2528,
    approved_by = 'CEO',
    approval_timestamp = NOW();

-- NEUTRAL regime: Align with 29% hit rate
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type,
    regime,
    confidence_band_min,
    confidence_band_max,
    historical_accuracy,
    sample_size,
    confidence_ceiling,
    safety_margin,
    calculation_window_days,
    effective_from,
    approved_by,
    approval_timestamp
) VALUES (
    'PRICE_DIRECTION',
    'NEUTRAL',
    0.0,
    1.0,
    0.2886,
    1275,
    0.39, -- CEO approved ceiling
    0.10,
    30,
    NOW(),
    'CEO',
    NOW()
)
ON CONFLICT (forecast_type, regime, confidence_band_min, confidence_band_max)
    WHERE regime IS NOT NULL
DO UPDATE SET
    confidence_ceiling = 0.39,
    historical_accuracy = 0.2886,
    approved_by = 'CEO',
    approval_timestamp = NOW();

-- BEAR regime: Align with 33% hit rate
INSERT INTO fhq_governance.confidence_calibration_gates (
    forecast_type,
    regime,
    confidence_band_min,
    confidence_band_max,
    historical_accuracy,
    sample_size,
    confidence_ceiling,
    safety_margin,
    calculation_window_days,
    effective_from,
    approved_by,
    approval_timestamp
) VALUES (
    'PRICE_DIRECTION',
    'BEAR',
    0.0,
    1.0,
    0.3260,
    730,
    0.43, -- CEO approved ceiling
    0.10,
    30,
    NOW(),
    'CEO',
    NOW()
)
ON CONFLICT (forecast_type, regime, confidence_band_min, confidence_band_max)
    WHERE regime IS NOT NULL
DO UPDATE SET
    confidence_ceiling = 0.43,
    historical_accuracy = 0.3260,
    approved_by = 'CEO',
    approval_timestamp = NOW();

-- Step 4: Update queue status to EXECUTED
UPDATE fhq_governance.calibration_change_queue
SET
    status = 'EXECUTED',
    ceo_approved_at = NOW(),
    executed_at = NOW()
WHERE okr_code LIKE 'FRICTION-001%'
AND status = 'QUEUED';

-- Step 5: Create confidence damping function for real-time enforcement
CREATE OR REPLACE FUNCTION fhq_governance.apply_regime_confidence_ceiling(
    p_raw_confidence NUMERIC,
    p_regime TEXT
)
RETURNS NUMERIC AS $$
DECLARE
    v_ceiling NUMERIC;
BEGIN
    -- Get the CEO-approved ceiling for this regime
    SELECT confidence_ceiling INTO v_ceiling
    FROM fhq_governance.confidence_calibration_gates
    WHERE forecast_type = 'PRICE_DIRECTION'
    AND regime = p_regime
    AND effective_until IS NULL
    ORDER BY effective_from DESC
    LIMIT 1;

    -- If no ceiling found, use conservative default
    IF v_ceiling IS NULL THEN
        v_ceiling := 0.35;
    END IF;

    -- Return the minimum of raw confidence and ceiling
    RETURN LEAST(p_raw_confidence, v_ceiling);
END;
$$ LANGUAGE plpgsql;

-- Step 6: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'G4_FRICTION_001_EXECUTION',
    'confidence_calibration_gates',
    'REGIME_CALIBRATION',
    'CEO',
    'EXECUTED',
    'CEO Direct Order: Kill Overconfidence. Calibration is RISK REMOVAL. All regime confidence ceilings aligned with observed hit rates.',
    jsonb_build_object(
        'baseline_brier', 0.5358,
        'baseline_hit_rate', 0.3265,
        'changes_executed', 4,
        'stress_ceiling', 0.10,
        'bull_ceiling', 0.35,
        'neutral_ceiling', 0.39,
        'bear_ceiling', 0.43,
        'ceo_principle', 'ROI will not come from brilliance. It will come from not being wrong with confidence.',
        'measurement_deadline', NOW() + INTERVAL '24 hours'
    )
);

-- Step 7: Create measurement view for 24h verification
CREATE OR REPLACE VIEW fhq_governance.v_friction_001_measurement AS
SELECT
    regime,
    COUNT(*) as forecast_count,
    ROUND(AVG(squared_error)::numeric, 4) as current_brier,
    0.5358 as baseline_brier,
    ROUND((0.5358 - AVG(squared_error))::numeric, 4) as brier_improvement,
    ROUND(AVG(CASE WHEN actual_outcome THEN 1.0 ELSE 0.0 END)::numeric, 4) as current_hit_rate,
    0.3265 as baseline_hit_rate,
    ROUND(AVG(forecast_probability)::numeric, 4) as avg_confidence,
    CASE
        WHEN regime = 'STRESS' THEN 0.10
        WHEN regime = 'BULL' THEN 0.35
        WHEN regime = 'NEUTRAL' THEN 0.39
        WHEN regime = 'BEAR' THEN 0.43
    END as new_ceiling,
    CASE
        WHEN AVG(squared_error) < 0.5358 THEN 'IMPROVING'
        WHEN AVG(squared_error) = 0.5358 THEN 'STABLE'
        ELSE 'REGRESSING'
    END as verdict
FROM fhq_governance.brier_score_ledger
WHERE created_at >= NOW() - INTERVAL '24 hours'
AND eligible_for_calibration = true
GROUP BY regime
ORDER BY regime;

-- Verification
DO $$
DECLARE
    executed_count INTEGER;
    ceiling_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO executed_count
    FROM fhq_governance.calibration_change_queue
    WHERE okr_code LIKE 'FRICTION-001%'
    AND status = 'EXECUTED';

    SELECT COUNT(*) INTO ceiling_count
    FROM fhq_governance.confidence_calibration_gates
    WHERE approved_by = 'CEO'
    AND regime IN ('STRESS', 'BULL', 'NEUTRAL', 'BEAR');

    RAISE NOTICE '===========================================';
    RAISE NOTICE 'G4 FRICTION-001 EXECUTION COMPLETE';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Queue entries executed: %', executed_count;
    RAISE NOTICE 'Regime ceilings set: %', ceiling_count;
    RAISE NOTICE 'Baseline Brier: 0.5358';
    RAISE NOTICE 'Measurement deadline: 24 hours';
    RAISE NOTICE '===========================================';
END $$;
