-- ============================================================================
-- Migration: 351_pre_tier_gradient_g1_5_freeze.sql
-- Directive: CEO-DIR-2026-PRE-TIER-GRADIENT-G1.5 (Empirical Calibration Phase)
-- Gate: G1.5 (Freeze Order)
-- Executor: STIG (EC-003)
-- Date: 2026-01-25
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: REGISTER G1.5 CALIBRATION PHASE
-- ============================================================================
INSERT INTO fhq_governance.canonical_evidence (
    evidence_type,
    evidence_category,
    agent_id,
    execution_timestamp,
    evidence_hash,
    evidence_payload,
    vega_signature,
    vega_public_key,
    registered_by,
    registered_at,
    authority,
    adr_compliance,
    audit_notes,
    immutable
) VALUES (
    'PHASE_GATE',
    'G1.5_CALIBRATION_FREEZE',
    'STIG',
    NOW(),
    encode(sha256('CEO-DIR-2026-PRE-TIER-GRADIENT-G1.5|FREEZE_ORDER|STIG|2026-01-25'::bytea), 'hex'),
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-PRE-TIER-GRADIENT-G1.5',
        'phase', 'EMPIRICAL_CALIBRATION',
        'status', 'ACTIVE',
        'freeze_order', jsonb_build_object(
            'weights_frozen', true,
            'thresholds_frozen', true,
            'agent_roles_frozen', true,
            'oxygen_criteria_frozen', true
        ),
        'calibration_target', jsonb_build_object(
            'required_deaths', 30,
            'current_deaths_with_score', 0,
            'tracked_hypotheses', 12
        ),
        'primary_metric', 'Spearman correlation: pre_tier_score_at_birth vs time_to_falsification',
        'secondary_metrics', ARRAY[
            'Pearson correlation (reported only)',
            'Survival stratified by score quartiles'
        ],
        'vega_trigger', 'Reasoning-Delta report at n=30',
        'principle', 'Observation beats intervention'
    ),
    'PENDING_VEGA_ATTESTATION',
    'PENDING_VEGA_ATTESTATION',
    'STIG',
    NOW(),
    'CEO',
    ARRAY['ADR-011', 'ADR-013'],
    'G1.5 Empirical Calibration Phase activated. Freeze order in effect until n>=30 hypothesis deaths with pre_tier_score.',
    true
);

-- ============================================================================
-- STEP 2: ADD BIRTH SCORE LOCK COLUMN (Immutable at death)
-- ============================================================================
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS pre_tier_score_at_birth NUMERIC(5,2),
ADD COLUMN IF NOT EXISTS time_to_falsification_hours NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS death_timestamp TIMESTAMPTZ;

-- ============================================================================
-- STEP 3: LOCK CURRENT SCORES AS BIRTH SCORES
-- ============================================================================
UPDATE fhq_learning.hypothesis_canon
SET pre_tier_score_at_birth = pre_tier_score
WHERE pre_tier_score IS NOT NULL
AND pre_tier_score_at_birth IS NULL;

-- ============================================================================
-- STEP 4: CREATE CALIBRATION TRACKING VIEW
-- ============================================================================
CREATE OR REPLACE VIEW fhq_learning.v_pre_tier_calibration_tracker AS
SELECT
    -- Hypothesis deaths with pre-tier scores
    COUNT(*) FILTER (
        WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')
        AND pre_tier_score_at_birth IS NOT NULL
    ) as deaths_with_score,

    -- Target
    30 as calibration_threshold,

    -- Progress
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')
            AND pre_tier_score_at_birth IS NOT NULL
        ) / 30.0, 1
    ) as progress_percent,

    -- Calibration ready flag
    COUNT(*) FILTER (
        WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')
        AND pre_tier_score_at_birth IS NOT NULL
    ) >= 30 as calibration_ready,

    -- Active tracked hypotheses
    COUNT(*) FILTER (
        WHERE status = 'DRAFT'
        AND pre_tier_score_at_birth IS NOT NULL
    ) as active_tracked,

    -- Score distribution of deaths
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY pre_tier_score_at_birth) FILTER (
        WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')
        AND pre_tier_score_at_birth IS NOT NULL
    ) as q1_score,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY pre_tier_score_at_birth) FILTER (
        WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')
        AND pre_tier_score_at_birth IS NOT NULL
    ) as q2_score,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY pre_tier_score_at_birth) FILTER (
        WHERE status IN ('FALSIFIED', 'REJECTED', 'EXPIRED')
        AND pre_tier_score_at_birth IS NOT NULL
    ) as q3_score
FROM fhq_learning.hypothesis_canon;

-- ============================================================================
-- STEP 5: CREATE VEGA TRIGGER RULE FOR N=30
-- ============================================================================
INSERT INTO fhq_governance.vega_validation_rules (
    rule_id,
    rule_name,
    rule_type,
    applies_to,
    condition_sql,
    failure_action,
    constitutional_basis,
    is_active,
    created_at
) VALUES (
    gen_random_uuid(),
    'Pre-Tier Calibration N30 Trigger',
    'POSTCONDITION',
    ARRAY['fhq_learning.hypothesis_canon'],
    'SELECT calibration_ready FROM fhq_learning.v_pre_tier_calibration_tracker WHERE calibration_ready = true',
    'ALERT',
    'CEO-DIR-2026-PRE-TIER-GRADIENT-G1.5',
    true,
    NOW()
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- STEP 6: REGISTER FREEZE ORDER IN ORCHESTRATOR
-- ============================================================================
UPDATE fhq_governance.orchestrator_authority
SET
    stop_conditions = stop_conditions || '{"g1_5_freeze": true, "calibration_required_deaths": 30}'::jsonb,
    directive_reference = 'CEO-DIR-2026-PRE-TIER-GRADIENT-G1.5'
WHERE orchestrator_id = 'FHQ-PreTier-Scoring-Orchestrator';

COMMIT;
