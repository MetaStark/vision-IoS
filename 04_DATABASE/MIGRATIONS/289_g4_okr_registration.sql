-- Migration 289: G4 OKR Registration
-- CEO Directive: G4 Activation with OKRs
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Register formal OKRs for calibration, risk suppression, and ROI conversion

-- ============================================================================
-- G4 OKR REGISTRATION
-- ============================================================================
-- CEO: "This is not a suggestion. This is execution."
-- Baseline: Brier 0.5358, Hit Rate 32.65%
-- Constitutional zero-point established.
-- ============================================================================

-- Step 1: Create OKR tracking table
CREATE TABLE IF NOT EXISTS fhq_governance.g4_okr_registry (
    okr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    objective_number INTEGER NOT NULL,
    objective_name TEXT NOT NULL,
    key_result_number INTEGER NOT NULL,
    key_result_description TEXT NOT NULL,

    -- Targets
    target_metric TEXT NOT NULL,
    target_value NUMERIC,
    target_condition TEXT, -- 'LT', 'GT', 'EQ', 'WITHIN'
    target_tolerance NUMERIC,

    -- Current measurement
    current_value NUMERIC,
    current_status TEXT CHECK (current_status IN ('NOT_STARTED', 'IN_PROGRESS', 'ON_TRACK', 'AT_RISK', 'ACHIEVED', 'FAILED')),
    last_measured_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deadline TIMESTAMPTZ,
    owner_agent TEXT DEFAULT 'UMA',

    UNIQUE(objective_number, key_result_number)
);

-- Step 2: Register Objective 1 - Kill Catastrophic Overconfidence
INSERT INTO fhq_governance.g4_okr_registry (
    objective_number, objective_name, key_result_number, key_result_description,
    target_metric, target_value, target_condition, current_value, current_status, deadline
) VALUES
-- KR1.1: STRESS confidence < 15% with non-zero hit rate
(1, 'Kill Catastrophic Overconfidence', 1,
 'STRESS regime confidence below 15% with non-zero hit rate',
 'stress_confidence', 0.15, 'LT', 0.9103, 'IN_PROGRESS', NOW() + INTERVAL '48 hours'),

-- KR1.2: Every regime belief no more than 10 points above truth
(1, 'Kill Catastrophic Overconfidence', 2,
 'Every regime calibration gap ≤ 0.10 (10 percentage points)',
 'max_calibration_gap', 0.10, 'LT', 0.9103, 'IN_PROGRESS', NOW() + INTERVAL '48 hours'),

-- KR1.3: Calibration error reduced
(1, 'Kill Catastrophic Overconfidence', 3,
 'Overall calibration error reduced from baseline',
 'calibration_error', 0.5358, 'LT', 0.5567, 'IN_PROGRESS', NOW() + INTERVAL '48 hours');

-- Step 3: Register Objective 2 - Improve Learning Quality
INSERT INTO fhq_governance.g4_okr_registry (
    objective_number, objective_name, key_result_number, key_result_description,
    target_metric, target_value, target_condition, current_value, current_status, deadline
) VALUES
-- KR2.1: Adjusted LVI 10% above raw LVI
(2, 'Improve Learning Quality', 1,
 'Adjusted LVI at least 10% above raw LVI',
 'lvi_improvement_pct', 10.0, 'GT', 1.38, 'IN_PROGRESS', NOW() + INTERVAL '48 hours'),

-- KR2.2: EVENT_ADJACENT exclusion 100% enforced
(2, 'Improve Learning Quality', 2,
 'EVENT_ADJACENT forecasts 100% excluded from punitive learning',
 'event_adjacent_exclusion_pct', 100.0, 'EQ', 100.0, 'ACHIEVED', NOW() + INTERVAL '48 hours'),

-- KR2.3: Surprise classification in every degradation report
(2, 'Improve Learning Quality', 3,
 'Surprise classification (MODEL_DRIFT vs INFORMATION_SHOCK) in all degradation reports',
 'surprise_classification_coverage', 100.0, 'EQ', 0.0, 'IN_PROGRESS', NOW() + INTERVAL '48 hours');

-- Step 4: Register Objective 3 - Reduce Capital Risk
INSERT INTO fhq_governance.g4_okr_registry (
    objective_number, objective_name, key_result_number, key_result_description,
    target_metric, target_value, target_condition, current_value, current_status, deadline
) VALUES
-- KR3.1: Brier improves within 48 hours
(3, 'Reduce Capital Risk', 1,
 'Brier score improves vs baseline 0.5358 within 48 hours',
 'brier_score', 0.5358, 'LT', 0.5567, 'IN_PROGRESS', NOW() + INTERVAL '48 hours'),

-- KR3.2: No drift introduced
(3, 'Reduce Capital Risk', 2,
 'No regression drift - Brier does not exceed stop-loss 0.5658',
 'brier_stop_loss', 0.5658, 'LT', 0.5567, 'ON_TRACK', NOW() + INTERVAL '48 hours'),

-- KR3.3: Every delta reversible and attributable
(3, 'Reduce Capital Risk', 3,
 'All calibration changes logged with rollback capability',
 'changes_logged_pct', 100.0, 'EQ', 100.0, 'ACHIEVED', NOW() + INTERVAL '48 hours');

-- Step 5: Register Objective 4 - Preserve Defensibility
INSERT INTO fhq_governance.g4_okr_registry (
    objective_number, objective_name, key_result_number, key_result_description,
    target_metric, target_value, target_condition, current_value, current_status, deadline
) VALUES
-- KR4.1: All learning signed
(4, 'Preserve Defensibility', 1,
 'All UMA learning records signed with Ed25519 key',
 'signed_learning_pct', 100.0, 'EQ', 100.0, 'ACHIEVED', NOW() + INTERVAL '48 hours'),

-- KR4.2: Every G4 report VEGA-clean
(4, 'Preserve Defensibility', 2,
 'All G4 evidence files pass VEGA attestation',
 'vega_attestation_pct', 100.0, 'EQ', 100.0, 'ON_TRACK', NOW() + INTERVAL '48 hours'),

-- KR4.3: Stillness violations zero
(4, 'Preserve Defensibility', 3,
 'Zero stillness protocol violations during G4 period',
 'stillness_violations', 0, 'EQ', 0, 'ON_TRACK', NOW() + INTERVAL '48 hours');

-- Step 6: Create OKR measurement function
CREATE OR REPLACE FUNCTION fhq_governance.measure_g4_okrs()
RETURNS TABLE (
    objective TEXT,
    key_result TEXT,
    target TEXT,
    current TEXT,
    status TEXT,
    delta TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'O' || objective_number || ': ' || objective_name,
        'KR' || objective_number || '.' || key_result_number || ': ' || LEFT(key_result_description, 50) || '...',
        target_condition || ' ' || ROUND(target_value::numeric, 4)::text,
        ROUND(current_value::numeric, 4)::text,
        current_status,
        CASE
            WHEN target_condition = 'LT' THEN
                CASE WHEN current_value < target_value THEN '✓' ELSE ROUND((current_value - target_value)::numeric, 4)::text || ' gap' END
            WHEN target_condition = 'GT' THEN
                CASE WHEN current_value > target_value THEN '✓' ELSE ROUND((target_value - current_value)::numeric, 4)::text || ' gap' END
            WHEN target_condition = 'EQ' THEN
                CASE WHEN current_value = target_value THEN '✓' ELSE ROUND(ABS(current_value - target_value)::numeric, 4)::text || ' gap' END
            ELSE 'N/A'
        END
    FROM fhq_governance.g4_okr_registry
    ORDER BY objective_number, key_result_number;
END;
$$ LANGUAGE plpgsql;

-- Step 7: Create OKR summary view
CREATE OR REPLACE VIEW fhq_governance.v_g4_okr_summary AS
SELECT
    objective_number,
    objective_name,
    COUNT(*) as total_krs,
    COUNT(*) FILTER (WHERE current_status = 'ACHIEVED') as achieved,
    COUNT(*) FILTER (WHERE current_status IN ('ON_TRACK', 'IN_PROGRESS')) as in_progress,
    COUNT(*) FILTER (WHERE current_status IN ('AT_RISK', 'FAILED')) as at_risk,
    ROUND(
        (COUNT(*) FILTER (WHERE current_status = 'ACHIEVED')::numeric / COUNT(*)::numeric) * 100,
        1
    ) as completion_pct
FROM fhq_governance.g4_okr_registry
GROUP BY objective_number, objective_name
ORDER BY objective_number;

-- Step 8: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'G4_OKR_REGISTRATION',
    'g4_okr_registry',
    'GOVERNANCE',
    'CEO',
    'REGISTERED',
    'CEO Directive: G4 Activation with OKRs. Four objectives, twelve key results. 48-hour measurement deadline.',
    jsonb_build_object(
        'objectives', 4,
        'key_results', 12,
        'baseline_brier', 0.5358,
        'baseline_hit_rate', 0.3265,
        'deadline', NOW() + INTERVAL '48 hours',
        'ceo_principle', 'ROI will not come from brilliance. It will come from not being wrong with confidence.'
    )
);

-- Verification
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM fhq_governance.g4_okr_registry;

    RAISE NOTICE '===========================================';
    RAISE NOTICE 'G4 OKR REGISTRATION COMPLETE';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Objectives registered: 4';
    RAISE NOTICE 'Key Results registered: %', v_count;
    RAISE NOTICE 'Deadline: 48 hours from activation';
    RAISE NOTICE 'Baseline Brier: 0.5358';
    RAISE NOTICE 'Stop-loss: 0.5658';
    RAISE NOTICE '===========================================';
END $$;

-- Show OKR summary
SELECT * FROM fhq_governance.v_g4_okr_summary;
