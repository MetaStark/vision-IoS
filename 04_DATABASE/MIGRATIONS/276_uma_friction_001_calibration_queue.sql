-- Migration 276: UMA FRICTION-001 Calibration Queue
-- CEO Post-G3 Directive 1.2: Measured Delta Execution
-- Date: 2026-01-17
-- Author: STIG (executing UMA recommendation)
-- Purpose: Queue confidence damper calibration through governance infrastructure

-- ============================================================================
-- FRICTION-001: BULL REGIME OVERCONFIDENCE CALIBRATION
-- ============================================================================
-- CEO Hypothesis: BULL regime shows massive overconfidence
-- Analysis Result: CONFIRMED - 92% avg confidence vs 25% hit rate (66.79% delta)
-- Execution Gate: G3_FULLY_LOCKED (SATISFIED 2026-01-17T00:05:18Z)

-- Step 1: Create UMA recommendation record
INSERT INTO fhq_governance.uma_recommendations (
    loop_id,
    recommendation_number,
    recommendation_type,
    target_parameter,
    expected_lvi_uplift,
    evidence_references,
    exclusion_checks_passed,
    stop_condition_checks_passed,
    uma_signature,
    vega_reviewed,
    vega_outcome
) VALUES (
    (SELECT loop_id FROM fhq_governance.uma_daily_loops ORDER BY created_at DESC LIMIT 1),
    1,
    'CONFIDENCE_CALIBRATION',
    'confidence_damper_beta',
    0.05,  -- Expected 5% improvement in calibrated confidence
    ARRAY[
        '03_FUNCTIONS/evidence/UMA_FRICTION_001_ANALYSIS_20260117.json',
        '03_FUNCTIONS/evidence/VEGA_G3_SIGNATURE_CEREMONY_20260117_010456.json'
    ],
    true,
    true,
    '7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6',  -- UMA public key
    false,
    NULL
)
ON CONFLICT DO NOTHING;

-- Step 2: Update existing queued calibration change with proposed value
UPDATE fhq_governance.calibration_change_queue
SET
    proposed_value = 0.35,  -- Target ceiling for BULL regime
    gate_met = true,
    change_rationale = 'FRICTION-001: BULL regime confidence ceiling. Analysis shows 92% avg confidence vs 25% hit rate. Proposed ceiling = hit_rate + 10% safety margin.',
    uma_proposed_at = NOW()
WHERE target_column = 'confidence_ceiling'
AND status = 'QUEUED'
AND execution_gate = 'G3_FULLY_LOCKED';

-- Step 3: Queue regime-specific confidence ceiling changes
-- BULL regime
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
    uma_recommendation_id,
    target_table,
    target_column,
    target_filter,
    current_value,
    proposed_value,
    change_rationale,
    execution_gate,
    gate_met,
    uma_proposed_at,
    status,
    rollback_sql
) VALUES (
    'FRICTION-001-BULL',
    (SELECT recommendation_id FROM fhq_governance.uma_recommendations WHERE target_parameter = 'confidence_damper_beta' ORDER BY created_at DESC LIMIT 1),
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    'regime = ''BULL'' AND forecast_type = ''PRICE_DIRECTION''',
    0.92,  -- Current avg confidence in BULL
    0.35,  -- Proposed ceiling: hit_rate (0.25) + 0.10 margin
    'FRICTION-001: BULL regime overconfidence correction. Current: 92% avg confidence, 25% hit rate (67% overconfidence delta). Proposed: 35% ceiling.',
    'G3_FULLY_LOCKED',
    true,
    NOW(),
    'QUEUED',
    'UPDATE fhq_governance.confidence_calibration_gates SET confidence_ceiling = 0.92 WHERE regime = ''BULL'''
) ON CONFLICT DO NOTHING;

-- STRESS regime (critical)
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
    uma_recommendation_id,
    target_table,
    target_column,
    target_filter,
    current_value,
    proposed_value,
    change_rationale,
    execution_gate,
    gate_met,
    uma_proposed_at,
    status,
    rollback_sql
) VALUES (
    'FRICTION-001-STRESS',
    (SELECT recommendation_id FROM fhq_governance.uma_recommendations WHERE target_parameter = 'confidence_damper_beta' ORDER BY created_at DESC LIMIT 1),
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    'regime = ''STRESS''',
    0.91,  -- Current avg confidence in STRESS
    0.10,  -- Proposed ceiling: near-zero + margin (0% hit rate!)
    'FRICTION-001: STRESS regime CRITICAL fix. Current: 91% avg confidence, 0% hit rate (model anti-predictive). Proposed: 10% ceiling.',
    'G3_FULLY_LOCKED',
    true,
    NOW(),
    'QUEUED',
    'UPDATE fhq_governance.confidence_calibration_gates SET confidence_ceiling = 0.91 WHERE regime = ''STRESS'''
) ON CONFLICT DO NOTHING;

-- NEUTRAL regime
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
    uma_recommendation_id,
    target_table,
    target_column,
    target_filter,
    current_value,
    proposed_value,
    change_rationale,
    execution_gate,
    gate_met,
    uma_proposed_at,
    status,
    rollback_sql
) VALUES (
    'FRICTION-001-NEUTRAL',
    (SELECT recommendation_id FROM fhq_governance.uma_recommendations WHERE target_parameter = 'confidence_damper_beta' ORDER BY created_at DESC LIMIT 1),
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    'regime = ''NEUTRAL'' AND forecast_type = ''PRICE_DIRECTION''',
    0.85,  -- Current avg confidence in NEUTRAL
    0.39,  -- Proposed ceiling: hit_rate (0.29) + 0.10 margin
    'FRICTION-001: NEUTRAL regime overconfidence correction. Current: 85% avg confidence, 29% hit rate (57% overconfidence delta).',
    'G3_FULLY_LOCKED',
    true,
    NOW(),
    'QUEUED',
    'UPDATE fhq_governance.confidence_calibration_gates SET confidence_ceiling = 0.85 WHERE regime = ''NEUTRAL'''
) ON CONFLICT DO NOTHING;

-- BEAR regime
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
    uma_recommendation_id,
    target_table,
    target_column,
    target_filter,
    current_value,
    proposed_value,
    change_rationale,
    execution_gate,
    gate_met,
    uma_proposed_at,
    status,
    rollback_sql
) VALUES (
    'FRICTION-001-BEAR',
    (SELECT recommendation_id FROM fhq_governance.uma_recommendations WHERE target_parameter = 'confidence_damper_beta' ORDER BY created_at DESC LIMIT 1),
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    'regime = ''BEAR'' AND forecast_type = ''PRICE_DIRECTION''',
    0.86,  -- Current avg confidence in BEAR
    0.43,  -- Proposed ceiling: hit_rate (0.33) + 0.10 margin
    'FRICTION-001: BEAR regime overconfidence correction. Current: 86% avg confidence, 33% hit rate (53% overconfidence delta).',
    'G3_FULLY_LOCKED',
    true,
    NOW(),
    'QUEUED',
    'UPDATE fhq_governance.confidence_calibration_gates SET confidence_ceiling = 0.86 WHERE regime = ''BEAR'''
) ON CONFLICT DO NOTHING;

-- Step 4: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'FRICTION_001_CALIBRATION_QUEUED',
    'confidence_damper_beta',
    'CALIBRATION_QUEUE',
    'UMA',
    'QUEUED_FOR_CEO_APPROVAL',
    'FRICTION-001: Regime-specific confidence ceiling calibration queued. All 4 regimes show SEVERE overconfidence. Execution requires CEO approval.',
    jsonb_build_object(
        'regimes_queued', 4,
        'bull_delta', 0.6679,
        'stress_delta', 0.9103,
        'neutral_delta', 0.5660,
        'bear_delta', 0.5297,
        'execution_gate', 'G3_FULLY_LOCKED',
        'gate_satisfied', true,
        'baseline_reference', 'G3_BASELINE_DAY17'
    )
);

-- Verification
DO $$
DECLARE
    queued_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO queued_count
    FROM fhq_governance.calibration_change_queue
    WHERE okr_code LIKE 'FRICTION-001%'
    AND status = 'QUEUED';

    RAISE NOTICE 'FRICTION-001 Calibration Queue: % changes queued for CEO approval', queued_count;
END $$;
