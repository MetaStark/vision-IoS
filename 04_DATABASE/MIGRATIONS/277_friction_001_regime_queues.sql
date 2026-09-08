-- Migration 277: FRICTION-001 Regime-Specific Calibration Queues
-- CEO Post-G3 Directive 1.2: Measured Delta Execution
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Queue regime-specific confidence ceiling changes

-- BULL regime calibration
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
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
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    '{"regime": "BULL", "forecast_type": "PRICE_DIRECTION"}'::jsonb,
    0.92,
    0.35,
    'FRICTION-001: BULL regime overconfidence correction. Current: 92% avg confidence, 25% hit rate (67% overconfidence delta). Proposed: 35% ceiling.',
    'G3_FULLY_LOCKED',
    true,
    NOW(),
    'QUEUED',
    'UPDATE fhq_governance.confidence_calibration_gates SET confidence_ceiling = 0.92 WHERE regime = ''BULL'''
);

-- STRESS regime calibration (CRITICAL)
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
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
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    '{"regime": "STRESS"}'::jsonb,
    0.91,
    0.10,
    'FRICTION-001: STRESS regime CRITICAL fix. Current: 91% avg confidence, 0% hit rate (model anti-predictive). Proposed: 10% ceiling.',
    'G3_FULLY_LOCKED',
    true,
    NOW(),
    'QUEUED',
    'UPDATE fhq_governance.confidence_calibration_gates SET confidence_ceiling = 0.91 WHERE regime = ''STRESS'''
);

-- NEUTRAL regime calibration
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
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
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    '{"regime": "NEUTRAL", "forecast_type": "PRICE_DIRECTION"}'::jsonb,
    0.85,
    0.39,
    'FRICTION-001: NEUTRAL regime overconfidence correction. Current: 85% avg confidence, 29% hit rate (57% overconfidence delta).',
    'G3_FULLY_LOCKED',
    true,
    NOW(),
    'QUEUED',
    'UPDATE fhq_governance.confidence_calibration_gates SET confidence_ceiling = 0.85 WHERE regime = ''NEUTRAL'''
);

-- BEAR regime calibration
INSERT INTO fhq_governance.calibration_change_queue (
    okr_code,
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
    'fhq_governance.confidence_calibration_gates',
    'confidence_ceiling',
    '{"regime": "BEAR", "forecast_type": "PRICE_DIRECTION"}'::jsonb,
    0.86,
    0.43,
    'FRICTION-001: BEAR regime overconfidence correction. Current: 86% avg confidence, 33% hit rate (53% overconfidence delta).',
    'G3_FULLY_LOCKED',
    true,
    NOW(),
    'QUEUED',
    'UPDATE fhq_governance.confidence_calibration_gates SET confidence_ceiling = 0.86 WHERE regime = ''BEAR'''
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

    RAISE NOTICE 'FRICTION-001 Calibration Queue: % regime-specific changes queued for CEO approval', queued_count;
END $$;
