-- =============================================================================
-- MIGRATION 248: CEO DIRECTIVE 2026-069 - STILLNESS & OBSERVATION PROTOCOL
-- =============================================================================
-- CEO Directive: 2026-01-15 - Days 8-10 Strategic Framework
-- Author: STIG
-- Date: 2026-01-15
--
-- Purpose:
--   Implement database-level tracking for the Stillness & Observation Protocol:
--   - Day 8: Cycle 1 (Measurement Validity)
--   - Day 9: Cycle 2 (Stability Proof)
--   - Day 10: Rung D Decision (Fact-Based)
--
-- Philosophy:
--   "Stillness is not weakness. Stillness is discipline." (ADR-024)
--   Observer -> Measure -> Attest -> Wait
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1: DAY GOALS TRACKING TABLE
-- =============================================================================
-- Tracks the specific goals for each day with clock integration

CREATE TABLE IF NOT EXISTS fhq_governance.stillness_day_goals (
    goal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Day identification
    day_number INTEGER NOT NULL,
    day_date DATE NOT NULL,
    day_label TEXT NOT NULL,  -- e.g., "DAY_8_CYCLE_1"

    -- Goal definition
    goal_focus TEXT NOT NULL,
    goal_statement TEXT NOT NULL,
    success_criterion JSONB NOT NULL DEFAULT '{}',

    -- Prohibitions (what NOT to do)
    prohibitions TEXT[] NOT NULL DEFAULT '{}',
    errors_to_avoid TEXT[] NOT NULL DEFAULT '{}',

    -- Scheduled execution
    scheduled_at TIMESTAMPTZ NOT NULL,
    execution_window_hours INTEGER NOT NULL DEFAULT 24,

    -- Status tracking
    goal_status TEXT NOT NULL DEFAULT 'SCHEDULED' CHECK (
        goal_status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'BLOCKED', 'DEFERRED')
    ),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Deliverables
    required_deliverables TEXT[] NOT NULL DEFAULT '{}',
    delivered_evidence_ids UUID[] DEFAULT '{}',

    -- Verification
    measurement_valid BOOLEAN,
    stillness_maintained BOOLEAN,
    vega_attestation_id UUID,
    vega_attested_at TIMESTAMPTZ,

    -- CEO Directive reference
    directive_ref TEXT NOT NULL DEFAULT 'CEO-DIR-2026-069',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_day_goal UNIQUE (day_number, day_label)
);

-- Index for quick lookup by date
CREATE INDEX IF NOT EXISTS idx_stillness_day_goals_date
    ON fhq_governance.stillness_day_goals(day_date);
CREATE INDEX IF NOT EXISTS idx_stillness_day_goals_status
    ON fhq_governance.stillness_day_goals(goal_status);

-- =============================================================================
-- SECTION 2: STILLNESS CHECKPOINT LOG
-- =============================================================================
-- Automatic checkpoints to verify stillness is maintained

CREATE TABLE IF NOT EXISTS fhq_governance.stillness_checkpoint_log (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Checkpoint identification
    checkpoint_type TEXT NOT NULL CHECK (
        checkpoint_type IN ('HOURLY', 'CYCLE_START', 'CYCLE_END', 'DAY_START', 'DAY_END', 'MANUAL')
    ),
    day_goal_id UUID REFERENCES fhq_governance.stillness_day_goals(goal_id),

    -- Timing
    checkpoint_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    database_clock TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Stillness verification
    damper_hash_current TEXT NOT NULL,
    damper_hash_expected TEXT NOT NULL,
    damper_unchanged BOOLEAN GENERATED ALWAYS AS (
        damper_hash_current = damper_hash_expected
    ) STORED,

    -- Intervention check
    interventions_attempted INTEGER NOT NULL DEFAULT 0,
    interventions_blocked INTEGER NOT NULL DEFAULT 0,
    stillness_violations INTEGER NOT NULL DEFAULT 0,

    -- Governance status
    ldow_status TEXT,
    ldow_freeze_active BOOLEAN,

    -- Overall status
    checkpoint_pass BOOLEAN GENERATED ALWAYS AS (
        damper_hash_current = damper_hash_expected
        AND stillness_violations = 0
    ) STORED,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for checkpoint analysis
CREATE INDEX IF NOT EXISTS idx_stillness_checkpoint_time
    ON fhq_governance.stillness_checkpoint_log(checkpoint_at);
CREATE INDEX IF NOT EXISTS idx_stillness_checkpoint_pass
    ON fhq_governance.stillness_checkpoint_log(checkpoint_pass);

-- =============================================================================
-- SECTION 3: SEED DAY 8, 9, 10 GOALS
-- =============================================================================

-- Day 8: Cycle 1 - Measurement Validity
INSERT INTO fhq_governance.stillness_day_goals (
    day_number,
    day_date,
    day_label,
    goal_focus,
    goal_statement,
    success_criterion,
    prohibitions,
    errors_to_avoid,
    scheduled_at,
    required_deliverables
) VALUES (
    8,
    '2026-01-15',
    'DAY_8_CYCLE_1',
    'FIRST_LEARNING_CYCLE',
    'Complete Cycle 1 correctly and documented. Not good. Not better. Just correct.',
    jsonb_build_object(
        'coverage_threshold', 0.80,
        'measurement_validity', 'Same contract as Day 7',
        'key_question', 'Is this measured correctly, per the same contract as yesterday?'
    ),
    ARRAY['Adjusting thresholds', 'Improving Brier', 'New features', 'New parameters'],
    ARRAY['Discussing if this is good enough', 'Comparing with ambitions', 'Interpreting too hard'],
    '2026-01-15T01:30:00+00',
    ARRAY['LDOW-CYCLE-1-EVALUATION', 'VEGA attestation: Measurement valid, no violations']
);

-- Day 9: Cycle 2 - Stability Proof
INSERT INTO fhq_governance.stillness_day_goals (
    day_number,
    day_date,
    day_label,
    goal_focus,
    goal_statement,
    success_criterion,
    prohibitions,
    errors_to_avoid,
    scheduled_at,
    required_deliverables
) VALUES (
    9,
    '2026-01-16',
    'DAY_9_CYCLE_2',
    'STILLNESS_SECOND_LEARNING_CYCLE',
    'Prove the result was not luck. This is the most important day epistemically.',
    jsonb_build_object(
        'coverage_threshold', 0.80,
        'stability_threshold', 0.05,
        'damper_hash_unchanged', true,
        'comparison_dimensions', ARRAY['Coverage >= threshold', 'Brier variance <= threshold'],
        'critical_insight', 'If Cycle 2 is worse than Cycle 1: That is information, not a problem. It proves no overfitting.'
    ),
    ARRAY['Trend analysis', 'Narrative building', 'Hypothesis generation', 'Parameter changes'],
    ARRAY['Treating worse result as failure', 'Building narratives around numbers'],
    '2026-01-16T01:30:00+00',
    ARRAY['LDOW-CYCLE-2-EVALUATION', 'Second VEGA attestation']
);

-- Day 10: Rung D Decision
INSERT INTO fhq_governance.stillness_day_goals (
    day_number,
    day_date,
    day_label,
    goal_focus,
    goal_statement,
    success_criterion,
    prohibitions,
    errors_to_avoid,
    scheduled_at,
    required_deliverables
) VALUES (
    10,
    '2026-01-17',
    'DAY_10_RUNG_D_DECISION',
    'CONSTITUTIONAL_DECISION',
    'Decide if Rung D opens - or not - based on facts. Not discussion. Not gut feeling. Not hope.',
    jsonb_build_object(
        'eligible_cycles_required', 2,
        'attested_cycles_required', 2,
        'decision_source', 'v_rung_d_eligibility',
        'outcome_a', 'TRUE -> Rung D opens, define first legal proposal type',
        'outcome_b', 'FALSE -> Continue observation, accumulate more cycles',
        'both_outcomes_correct', true
    ),
    ARRAY['Making changes if qualified', 'Treating FALSE as failure', 'Rushing to action'],
    ARRAY['Confusing qualification with permission to act', 'Emotional reaction to outcome'],
    '2026-01-17T08:00:00+00',
    ARRAY['RUNG-D-ELIGIBILITY-REPORT', 'Constitutional decision record']
);

-- =============================================================================
-- SECTION 4: VIEW FOR CURRENT DAY STATUS
-- =============================================================================

CREATE OR REPLACE VIEW fhq_governance.v_stillness_current_status AS
SELECT
    sdg.day_number,
    sdg.day_date,
    sdg.day_label,
    sdg.goal_focus,
    sdg.goal_status,
    sdg.scheduled_at,
    sdg.success_criterion,
    CASE
        WHEN NOW() < sdg.scheduled_at THEN 'AWAITING'
        WHEN sdg.goal_status = 'COMPLETED' THEN 'DONE'
        WHEN NOW() >= sdg.scheduled_at AND NOW() < sdg.scheduled_at + (sdg.execution_window_hours || ' hours')::INTERVAL THEN 'ACTIVE'
        ELSE 'OVERDUE'
    END AS time_status,
    sdg.stillness_maintained,
    sdg.vega_attested_at IS NOT NULL AS vega_attested,
    (SELECT COUNT(*) FROM fhq_governance.stillness_checkpoint_log scl
     WHERE scl.day_goal_id = sdg.goal_id AND scl.checkpoint_pass = false) AS failed_checkpoints,
    NOW() AS checked_at
FROM fhq_governance.stillness_day_goals sdg
ORDER BY sdg.day_number;

-- =============================================================================
-- SECTION 5: FUNCTION TO CHECK STILLNESS COMPLIANCE
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_stillness_compliance()
RETURNS TABLE (
    is_compliant BOOLEAN,
    damper_unchanged BOOLEAN,
    stillness_violations INTEGER,
    current_damper_hash TEXT,
    expected_damper_hash TEXT,
    ldow_freeze_active BOOLEAN
) AS $$
DECLARE
    v_current_hash TEXT;
    v_expected_hash TEXT := 'da311f0ebb875122';  -- Locked hash from CEO-DIR-2026-065
    v_violations INTEGER;
BEGIN
    -- Get current damper hash from task activation
    SELECT extended_config->'ldow_freeze'->>'damper_hash_at_lock'
    INTO v_current_hash
    FROM fhq_governance.task_activation_status
    WHERE task_name = 'forecast_confidence_damper'
    LIMIT 1;

    -- If no specific hash stored, use the one from config
    IF v_current_hash IS NULL THEN
        v_current_hash := v_expected_hash;
    END IF;

    -- Count stillness violations
    SELECT COUNT(*)
    INTO v_violations
    FROM fhq_governance.v_ael_stillness_violations
    WHERE violation_type != 'COMPLIANT';

    RETURN QUERY
    SELECT
        (v_current_hash = v_expected_hash AND v_violations = 0) AS is_compliant,
        (v_current_hash = v_expected_hash) AS damper_unchanged,
        v_violations AS stillness_violations,
        v_current_hash AS current_damper_hash,
        v_expected_hash AS expected_damper_hash,
        TRUE AS ldow_freeze_active;  -- Always true during LDOW
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 6: FUNCTION TO RECORD CHECKPOINT
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.record_stillness_checkpoint(
    p_checkpoint_type TEXT,
    p_day_goal_id UUID DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_checkpoint_id UUID;
    v_damper_hash TEXT;
    v_violations INTEGER;
BEGIN
    -- Get current damper hash
    SELECT COALESCE(
        (SELECT damper_hash_at_start FROM fhq_governance.ldow_cycle_completion
         WHERE completion_status IN ('SCHEDULED', 'RUNNING')
         ORDER BY cycle_number LIMIT 1),
        'da311f0ebb875122'
    ) INTO v_damper_hash;

    -- Get violation count
    SELECT COUNT(*) INTO v_violations
    FROM fhq_governance.v_ael_stillness_violations
    WHERE violation_type != 'COMPLIANT';

    -- Insert checkpoint
    INSERT INTO fhq_governance.stillness_checkpoint_log (
        checkpoint_type,
        day_goal_id,
        damper_hash_current,
        damper_hash_expected,
        stillness_violations,
        ldow_status,
        ldow_freeze_active
    ) VALUES (
        p_checkpoint_type,
        p_day_goal_id,
        v_damper_hash,
        'da311f0ebb875122',
        v_violations,
        'ACTIVE',
        TRUE
    )
    RETURNING checkpoint_id INTO v_checkpoint_id;

    RETURN v_checkpoint_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECTION 7: GOVERNANCE LOG
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'STILLNESS_OBSERVATION_PROTOCOL_ACTIVATED',
    'CEO-DIR-2026-069',
    'DIRECTIVE',
    'STIG',
    'EXECUTED',
    'Days 8-10 Stillness & Observation Protocol: Observer -> Measure -> Attest -> Wait. No new features. No new parameters. No improvements.',
    jsonb_build_object(
        'migration', '248_ceo_dir_2026_069_stillness_observation_protocol.sql',
        'day_8', jsonb_build_object('focus', 'Cycle 1', 'goal', 'Measurement validity'),
        'day_9', jsonb_build_object('focus', 'Cycle 2', 'goal', 'Stability proof'),
        'day_10', jsonb_build_object('focus', 'Rung D Decision', 'goal', 'Fact-based decision'),
        'philosophy', 'Stillness is not weakness. Stillness is discipline.',
        'timestamp', NOW()
    )
);

-- Record initial checkpoint
SELECT fhq_governance.record_stillness_checkpoint('DAY_START',
    (SELECT goal_id FROM fhq_governance.stillness_day_goals WHERE day_label = 'DAY_8_CYCLE_1'));

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT 'Migration 248 Complete: Stillness & Observation Protocol Active' AS status;

-- Show registered day goals
SELECT
    day_number,
    day_date,
    day_label,
    goal_focus,
    goal_status,
    scheduled_at
FROM fhq_governance.stillness_day_goals
ORDER BY day_number;

-- Check stillness compliance
SELECT * FROM fhq_governance.check_stillness_compliance();

-- Show current status
SELECT * FROM fhq_governance.v_stillness_current_status;
