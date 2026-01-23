-- Migration 338: Addendum A - Epistemic Hardening, Incentive Safety & Context Integrity
-- CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Addendum A
-- Author: STIG (EC-003)
-- Date: 2026-01-23
--
-- MANDATORY IMPLEMENTATION per CEO directive
-- Governing Frameworks: ADR-018 (ASRP), ADR-014, ADR-004, IoS-010, EC-020/021/022
--
-- Addresses four failure modes:
--   1. Over-hard Tier-1 falsification (Type I error dominance)
--   2. Narrative seduction via unconstrained context vectors
--   3. Antithesis leakage destabilizing learning economics
--   4. Reward hacking ("Cobra Effect") in EC-022

-- ============================================
-- DIRECTIVE 1: TIER-1 SYMMETRY WATCH & DISCARDED HYPOTHESIS AUDIT
-- "Detect systematic over-hardening"
-- ============================================

-- 1.1 Shadow Tier Registry (for discarded hypothesis audit)
CREATE TABLE IF NOT EXISTS fhq_learning.shadow_tier_registry (
    shadow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source (5% random sample of Tier-1 FALSIFIED)
    source_hypothesis_id UUID NOT NULL REFERENCES fhq_learning.hypothesis_canon(canon_id),
    source_experiment_id UUID REFERENCES fhq_learning.experiment_registry(experiment_id),

    -- Shadow execution (LARS, read-only, isolated)
    executor TEXT DEFAULT 'LARS',
    execution_environment TEXT DEFAULT 'NON_CANONICAL',

    -- Shadow results
    shadow_result TEXT,  -- 'SURVIVED', 'CONFIRMED_DEAD', 'INCONCLUSIVE'
    shadow_confidence NUMERIC(4,3),
    shadow_metrics JSONB,

    -- Isolation enforcement
    feedback_to_active_tiers BOOLEAN DEFAULT FALSE,  -- MUST always be FALSE
    cross_contamination_detected BOOLEAN DEFAULT FALSE,

    -- Timestamps
    sampled_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    created_by TEXT DEFAULT 'STIG',

    -- HARD CONSTRAINT: Shadow Tier must NEVER re-promote hypotheses
    CONSTRAINT chk_no_feedback CHECK (feedback_to_active_tiers = FALSE),
    CONSTRAINT chk_shadow_result CHECK (shadow_result IS NULL OR shadow_result IN ('SURVIVED', 'CONFIRMED_DEAD', 'INCONCLUSIVE'))
);

-- 1.2 Shadow Tier Sampling Function
CREATE OR REPLACE FUNCTION fhq_learning.sample_for_shadow_tier(
    p_sample_rate NUMERIC DEFAULT 0.05  -- 5% default
) RETURNS JSONB AS $$
DECLARE
    v_sampled_count INT := 0;
    v_hypothesis RECORD;
BEGIN
    -- Sample random 5% of recently FALSIFIED hypotheses not yet in shadow
    FOR v_hypothesis IN
        SELECT hc.canon_id, er.experiment_id
        FROM fhq_learning.hypothesis_canon hc
        JOIN fhq_learning.experiment_registry er ON er.hypothesis_id = hc.canon_id
        WHERE hc.status = 'FALSIFIED'
          AND er.experiment_tier = 1
          AND er.result = 'FALSIFIED'
          AND NOT EXISTS (
              SELECT 1 FROM fhq_learning.shadow_tier_registry str
              WHERE str.source_hypothesis_id = hc.canon_id
          )
          AND RANDOM() < p_sample_rate
        LIMIT 10  -- Max 10 per batch
    LOOP
        INSERT INTO fhq_learning.shadow_tier_registry (
            source_hypothesis_id,
            source_experiment_id,
            executor,
            execution_environment
        ) VALUES (
            v_hypothesis.canon_id,
            v_hypothesis.experiment_id,
            'LARS',
            'NON_CANONICAL'
        );
        v_sampled_count := v_sampled_count + 1;
    END LOOP;

    RETURN jsonb_build_object(
        'sampled', v_sampled_count,
        'sample_rate', p_sample_rate,
        'timestamp', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- 1.3 Extended Tier-1 Calibration Status with Symmetry Watch
DROP VIEW IF EXISTS fhq_learning.v_tier1_calibration_status;
CREATE OR REPLACE VIEW fhq_learning.v_tier1_calibration_status AS
WITH tier1_stats AS (
    SELECT
        COUNT(*) as total_experiments,
        COUNT(CASE WHEN result = 'FALSIFIED' THEN 1 END) as falsified,
        COUNT(CASE WHEN result = 'WEAKENED' THEN 1 END) as weakened,
        COUNT(CASE WHEN result IN ('STABLE', 'PROMOTED') THEN 1 END) as survived
    FROM fhq_learning.experiment_registry
    WHERE experiment_tier = 1 AND status = 'COMPLETED'
),
shadow_stats AS (
    SELECT
        COUNT(*) as shadow_total,
        COUNT(CASE WHEN shadow_result = 'SURVIVED' THEN 1 END) as shadow_survived,
        COUNT(CASE WHEN cross_contamination_detected THEN 1 END) as contamination_count
    FROM fhq_learning.shadow_tier_registry
    WHERE shadow_result IS NOT NULL
)
SELECT
    t.total_experiments,
    t.falsified,
    t.weakened,
    t.survived,
    ROUND(t.falsified::NUMERIC / NULLIF(t.total_experiments, 0) * 100, 2) as death_rate_pct,

    -- Symmetry Watch Metrics (NEW per Addendum A)
    s.shadow_total,
    s.shadow_survived,
    ROUND(s.shadow_survived::NUMERIC / NULLIF(s.shadow_total, 0) * 100, 2) as shadow_survival_rate,

    -- False Negative Indicator
    CASE
        WHEN s.shadow_total >= 10 AND s.shadow_survived::NUMERIC / NULLIF(s.shadow_total, 0) > 0.30
        THEN TRUE
        ELSE FALSE
    END as false_negative_indicator,

    -- Hardening Bias Flag
    CASE
        WHEN s.shadow_total >= 10 AND s.shadow_survived::NUMERIC / NULLIF(s.shadow_total, 0) > 0.20
        THEN 'WARNING: Potential over-hardening detected'
        WHEN s.shadow_total >= 10 AND s.shadow_survived::NUMERIC / NULLIF(s.shadow_total, 0) > 0.30
        THEN 'ALERT: Systematic over-hardening - review Tier-1 criteria'
        ELSE 'OK'
    END as hardening_bias_flag,

    -- Contamination check
    s.contamination_count > 0 as contamination_detected,

    -- Calibration status
    CASE
        WHEN t.total_experiments < 30 THEN 'INSUFFICIENT_DATA'
        WHEN t.falsified::NUMERIC / NULLIF(t.total_experiments, 0) >= 0.80 THEN 'CALIBRATED_OK'
        WHEN t.falsified::NUMERIC / NULLIF(t.total_experiments, 0) >= 0.70 THEN 'ACCEPTABLE'
        ELSE 'NEEDS_TIGHTENING'
    END as calibration_status,
    70.0 as target_min_death_rate,
    90.0 as target_max_death_rate,
    30 as min_experiments_for_assessment,
    0.30 as shadow_survival_alert_threshold
FROM tier1_stats t, shadow_stats s;

-- ============================================
-- DIRECTIVE 2: CONTEXT VECTOR DOMINANCE HIERARCHY
-- "Temporal Alignment is VETO - no weighted averaging"
-- ============================================

-- 2.1 Add temporal_veto column to context_annotations
ALTER TABLE fhq_learning.context_annotations
ADD COLUMN IF NOT EXISTS temporal_veto BOOLEAN GENERATED ALWAYS AS (
    -- If temporal_alignment = 'AFTER', context is auto-vetoed
    temporal_alignment = 'AFTER'
) STORED;

-- 2.2 Add effective_confidence that respects dominance hierarchy
ALTER TABLE fhq_learning.context_annotations
ADD COLUMN IF NOT EXISTS effective_confidence NUMERIC(4,3) GENERATED ALWAYS AS (
    CASE
        -- VETO: If context came AFTER outcome, confidence = 0 regardless of other scores
        WHEN temporal_alignment = 'AFTER' THEN 0.000
        WHEN confidence_temporal_alignment IS NULL OR confidence_temporal_alignment < 0.5 THEN 0.000
        -- Dominance hierarchy: Temporal → Statistical Lift → Cross-Event (no averaging)
        ELSE LEAST(
            COALESCE(confidence_temporal_alignment, 0),
            COALESCE(confidence_statistical_lift, 1),
            COALESCE(confidence_cross_event_recurrence, 1)
        )
    END
) STORED;

-- 2.3 Context Dominance Validation Trigger
CREATE OR REPLACE FUNCTION fhq_learning.validate_context_dominance()
RETURNS TRIGGER AS $$
BEGIN
    -- VETO RULE: Context timestamp > outcome timestamp → reject or nullify
    IF NEW.temporal_alignment = 'AFTER' THEN
        -- Auto-nullify confidence scores (fail-closed)
        NEW.confidence_temporal_alignment := 0;
        NEW.confidence_statistical_lift := 0;
        NEW.confidence_cross_event_recurrence := 0;
        NEW.confidence_out_of_sample := 0;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_context_dominance ON fhq_learning.context_annotations;
CREATE TRIGGER trg_context_dominance
    BEFORE INSERT OR UPDATE ON fhq_learning.context_annotations
    FOR EACH ROW
    EXECUTE FUNCTION fhq_learning.validate_context_dominance();

-- 2.4 View to answer "Why was this context ignored?"
CREATE OR REPLACE VIEW fhq_learning.v_context_rejection_audit AS
SELECT
    annotation_id,
    target_type,
    target_id,
    context_theme,
    temporal_alignment,
    confidence_temporal_alignment,
    confidence_statistical_lift,
    confidence_cross_event_recurrence,
    effective_confidence,
    temporal_veto,
    CASE
        WHEN temporal_alignment = 'AFTER' THEN 'TEMPORAL_VETO: Context came after outcome'
        WHEN confidence_temporal_alignment IS NULL OR confidence_temporal_alignment < 0.5
            THEN 'TEMPORAL_ALIGNMENT_INSUFFICIENT: Score < 0.5'
        WHEN effective_confidence < 0.3 THEN 'LOW_EFFECTIVE_CONFIDENCE: Dominance hierarchy result < 0.3'
        ELSE 'ACCEPTED'
    END as rejection_reason,
    created_at
FROM fhq_learning.context_annotations
ORDER BY created_at DESC;

-- ============================================
-- DIRECTIVE 3: CSEO ANTITHESIS BOUNDARY (ADR-014)
-- "Antithesis is destructive testing only, not generative"
-- ============================================

-- 3.1 Add boundary constraint to antithesis_experiments
ALTER TABLE fhq_learning.antithesis_experiments
ADD COLUMN IF NOT EXISTS boundary_validated BOOLEAN DEFAULT FALSE;

-- 3.2 Antithesis Boundary Validation Function
CREATE OR REPLACE FUNCTION fhq_learning.validate_antithesis_boundary()
RETURNS TRIGGER AS $$
DECLARE
    v_hypothesis_status TEXT;
BEGIN
    -- Get target hypothesis status
    SELECT status INTO v_hypothesis_status
    FROM fhq_learning.hypothesis_canon
    WHERE canon_id = NEW.target_hypothesis_id;

    -- BOUNDARY RULE: Can only attack WEAKENED or CANDIDATE hypotheses
    IF v_hypothesis_status NOT IN ('WEAKENED', 'CANDIDATE') THEN
        RAISE EXCEPTION 'ANTITHESIS_BOUNDARY_VIOLATION: Cannot attack hypothesis with status %. Only WEAKENED or CANDIDATE allowed. (ADR-014)', v_hypothesis_status;
    END IF;

    -- Mark as boundary validated
    NEW.boundary_validated := TRUE;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_antithesis_boundary ON fhq_learning.antithesis_experiments;
CREATE TRIGGER trg_antithesis_boundary
    BEFORE INSERT ON fhq_learning.antithesis_experiments
    FOR EACH ROW
    EXECUTE FUNCTION fhq_learning.validate_antithesis_boundary();

-- 3.3 Antithesis Boundary Audit View
CREATE OR REPLACE VIEW fhq_learning.v_antithesis_boundary_audit AS
SELECT
    ae.antithesis_id,
    ae.antithesis_code,
    ae.target_hypothesis_id,
    hc.hypothesis_code,
    hc.status as hypothesis_status,
    ae.antithesis_class,
    ae.boundary_validated,
    ae.status as antithesis_status,
    ae.created_at,
    CASE
        WHEN hc.status IN ('WEAKENED', 'CANDIDATE') THEN 'VALID_TARGET'
        ELSE 'BOUNDARY_VIOLATION'
    END as boundary_check
FROM fhq_learning.antithesis_experiments ae
JOIN fhq_learning.hypothesis_canon hc ON ae.target_hypothesis_id = hc.canon_id;

-- ============================================
-- DIRECTIVE 4: EC-022 COMPLEXITY-ADJUSTED INCENTIVES
-- "Prevent Cobra Effect - no reward for killing trivial hypotheses"
-- ============================================

-- 4.1 Add complexity scoring to hypothesis_canon
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS complexity_score NUMERIC(4,2) DEFAULT 1.0;

ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS causal_graph_depth INT DEFAULT 1;

-- 4.2 Complexity Score Calculator
CREATE OR REPLACE FUNCTION fhq_learning.calculate_hypothesis_complexity(
    p_hypothesis_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_hypothesis RECORD;
    v_dof INT;
    v_causal_depth INT;
    v_regime_count INT;
    v_complexity NUMERIC;
BEGIN
    -- Get hypothesis details
    SELECT * INTO v_hypothesis
    FROM fhq_learning.hypothesis_canon
    WHERE canon_id = p_hypothesis_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Hypothesis not found');
    END IF;

    -- Calculate degrees of freedom from experiments
    SELECT COALESCE(SUM(dof_count), 0) INTO v_dof
    FROM fhq_learning.experiment_registry
    WHERE hypothesis_id = p_hypothesis_id;

    -- Get causal graph depth (from hypothesis definition)
    v_causal_depth := COALESCE(v_hypothesis.causal_graph_depth, 1);

    -- Count regime validity scope
    v_regime_count := COALESCE(jsonb_array_length(v_hypothesis.regime_validity), 1);

    -- Complexity formula: Higher = more complex = more valuable to falsify
    -- Trivial hypothesis = low complexity = low reward for killing
    v_complexity := (
        (v_causal_depth * 0.4) +
        (LEAST(v_dof, 10) * 0.3) +
        (v_regime_count * 0.3)
    );

    -- Update hypothesis
    UPDATE fhq_learning.hypothesis_canon
    SET complexity_score = v_complexity,
        causal_graph_depth = v_causal_depth
    WHERE canon_id = p_hypothesis_id;

    RETURN jsonb_build_object(
        'hypothesis_id', p_hypothesis_id,
        'causal_depth', v_causal_depth,
        'degrees_of_freedom', v_dof,
        'regime_count', v_regime_count,
        'complexity_score', ROUND(v_complexity, 2),
        'trivial_threshold', 1.5,
        'is_trivial', v_complexity < 1.5
    );
END;
$$ LANGUAGE plpgsql;

-- 4.3 Complexity-Adjusted Reward Calculator for EC-022
CREATE OR REPLACE FUNCTION fhq_learning.calculate_complexity_adjusted_reward(
    p_hypothesis_id UUID,
    p_base_reward NUMERIC,
    p_reward_type TEXT
) RETURNS JSONB AS $$
DECLARE
    v_complexity NUMERIC;
    v_adjusted_reward NUMERIC;
    v_cobra_flag BOOLEAN := FALSE;
BEGIN
    -- Get complexity score
    SELECT complexity_score INTO v_complexity
    FROM fhq_learning.hypothesis_canon
    WHERE canon_id = p_hypothesis_id;

    v_complexity := COALESCE(v_complexity, 1.0);

    -- Cobra Effect Prevention:
    -- If hypothesis is trivial (complexity < 1.5), reward is severely reduced
    IF v_complexity < 1.5 THEN
        v_adjusted_reward := p_base_reward * 0.1;  -- 90% reduction for trivial
        v_cobra_flag := TRUE;
    ELSIF v_complexity < 2.5 THEN
        v_adjusted_reward := p_base_reward * 0.5;  -- 50% reduction for simple
    ELSE
        v_adjusted_reward := p_base_reward * (v_complexity / 3.0);  -- Scale with complexity
    END IF;

    -- Cap reward
    v_adjusted_reward := LEAST(v_adjusted_reward, p_base_reward * 1.5);

    RETURN jsonb_build_object(
        'hypothesis_id', p_hypothesis_id,
        'reward_type', p_reward_type,
        'base_reward', p_base_reward,
        'complexity_score', v_complexity,
        'adjusted_reward', ROUND(v_adjusted_reward, 4),
        'cobra_flag', v_cobra_flag,
        'cobra_message', CASE WHEN v_cobra_flag
            THEN 'Trivial hypothesis - reward severely reduced to prevent Cobra Effect'
            ELSE NULL
        END
    );
END;
$$ LANGUAGE plpgsql;

-- 4.4 Update G1 Gate to include Cobra Effect simulation
ALTER TABLE fhq_learning.reward_logic_registry
ADD COLUMN IF NOT EXISTS cobra_effect_test BOOLEAN DEFAULT FALSE;

ALTER TABLE fhq_learning.reward_logic_registry
ADD COLUMN IF NOT EXISTS trivial_kill_net_reward NUMERIC(6,4);

-- 4.5 Enhanced G1 Gate Validation (now requires Cobra test)
CREATE OR REPLACE FUNCTION fhq_learning.validate_ec022_g1_gate_v2(
    p_reward_id UUID,
    p_validator TEXT,
    p_incentive_alignment_result BOOLEAN,
    p_asymmetry_result BOOLEAN,
    p_delayed_reward_result BOOLEAN,
    p_cobra_effect_result BOOLEAN,
    p_trivial_kill_net_reward NUMERIC,
    p_evidence JSONB
) RETURNS JSONB AS $$
DECLARE
    v_all_pass BOOLEAN;
BEGIN
    -- Validator must be STIG
    IF p_validator != 'STIG' THEN
        RETURN jsonb_build_object(
            'error', 'G1_VALIDATOR_UNAUTHORIZED',
            'message', 'Only STIG (EC-003) can validate EC-022 reward logic'
        );
    END IF;

    -- COBRA EFFECT CHECK: If trivial-kill yields positive reward, FAIL
    IF p_trivial_kill_net_reward > 0 THEN
        RETURN jsonb_build_object(
            'status', 'G1_FAILED_COBRA_EFFECT',
            'message', 'Trivial-kill strategy yields positive reward - EC-022 remains disabled',
            'trivial_kill_net_reward', p_trivial_kill_net_reward
        );
    END IF;

    -- All four tests must pass
    v_all_pass := p_incentive_alignment_result
        AND p_asymmetry_result
        AND p_delayed_reward_result
        AND p_cobra_effect_result;

    IF v_all_pass THEN
        UPDATE fhq_learning.reward_logic_registry
        SET g1_validated = TRUE,
            g1_validated_at = NOW(),
            g1_validator = p_validator,
            g1_validation_evidence = p_evidence,
            incentive_alignment_test = p_incentive_alignment_result,
            asymmetry_test = p_asymmetry_result,
            delayed_reward_test = p_delayed_reward_result,
            cobra_effect_test = p_cobra_effect_result,
            trivial_kill_net_reward = p_trivial_kill_net_reward,
            is_active = TRUE
        WHERE reward_id = p_reward_id;

        RETURN jsonb_build_object(
            'status', 'G1_VALIDATED_V2',
            'reward_id', p_reward_id,
            'cobra_effect_neutralized', TRUE,
            'activated', TRUE
        );
    ELSE
        RETURN jsonb_build_object(
            'status', 'G1_FAILED',
            'failures', jsonb_build_object(
                'incentive_alignment', p_incentive_alignment_result,
                'asymmetry', p_asymmetry_result,
                'delayed_reward', p_delayed_reward_result,
                'cobra_effect', p_cobra_effect_result
            )
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- DIRECTIVE 5: IoS-010 STRUCTURAL INTEGRATION
-- "Context → Evaluation linkage for Brier Score attribution"
-- ============================================

-- 5.1 Add evaluation_id to context_annotations
ALTER TABLE fhq_learning.context_annotations
ADD COLUMN IF NOT EXISTS evaluation_id UUID;

-- 5.2 Check if evaluations table exists and create FK if possible
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research' AND table_name = 'evaluations'
    ) THEN
        -- Add foreign key if evaluations table exists
        ALTER TABLE fhq_learning.context_annotations
        ADD CONSTRAINT fk_context_evaluation
        FOREIGN KEY (evaluation_id) REFERENCES fhq_research.evaluations(evaluation_id)
        ON DELETE SET NULL;
    END IF;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 5.3 Context annotation insert validation (fail-closed for IoS-010)
CREATE OR REPLACE FUNCTION fhq_learning.validate_context_evaluation_link()
RETURNS TRIGGER AS $$
BEGIN
    -- For hypothesis-linked contexts, evaluation_id is recommended but not required
    -- For evaluation-linked contexts, it must be valid
    IF NEW.target_type = 'EVALUATION' AND NEW.evaluation_id IS NULL THEN
        RAISE EXCEPTION 'CONTEXT_EVALUATION_LINK_REQUIRED: Evaluation-type context must have evaluation_id (IoS-010)';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_context_evaluation_link ON fhq_learning.context_annotations;
CREATE TRIGGER trg_context_evaluation_link
    BEFORE INSERT ON fhq_learning.context_annotations
    FOR EACH ROW
    EXECUTE FUNCTION fhq_learning.validate_context_evaluation_link();

-- 5.4 Context Impact Attribution View
CREATE OR REPLACE VIEW fhq_learning.v_context_brier_impact AS
SELECT
    ca.context_theme,
    ca.evaluation_id,
    ca.target_type,
    ca.effective_confidence as context_confidence,
    ca.temporal_alignment,
    ca.temporal_veto,
    ca.created_at as context_created_at,
    -- This view is ready for JOIN with fhq_research.evaluations when available
    'Ready for Brier Score delta attribution' as integration_status
FROM fhq_learning.context_annotations ca
WHERE ca.evaluation_id IS NOT NULL
   OR ca.target_type = 'HYPOTHESIS'
ORDER BY ca.created_at DESC;

-- ============================================
-- READINESS CHECKLIST VIEW
-- ============================================

CREATE OR REPLACE VIEW fhq_learning.v_addendum_a_readiness AS
SELECT
    -- Tier-1 Death Rate
    (SELECT death_rate_pct FROM fhq_learning.v_tier1_calibration_status) as tier1_death_rate,
    (SELECT death_rate_pct >= 70 FROM fhq_learning.v_tier1_calibration_status) as tier1_target_met,

    -- Symmetry Watch
    (SELECT shadow_total FROM fhq_learning.v_tier1_calibration_status) as shadow_tier_samples,
    (SELECT shadow_survival_rate FROM fhq_learning.v_tier1_calibration_status) as shadow_survival_rate,
    (SELECT hardening_bias_flag FROM fhq_learning.v_tier1_calibration_status) as hardening_bias_status,

    -- Context Dominance
    EXISTS(SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'fhq_learning' AND table_name = 'context_annotations'
           AND column_name = 'temporal_veto') as temporal_veto_enforced,

    -- CSEO Boundary
    EXISTS(SELECT 1 FROM information_schema.triggers
           WHERE trigger_name = 'trg_antithesis_boundary') as cseo_boundary_enforced,

    -- EC-022 G1
    (SELECT COUNT(*) FROM fhq_learning.reward_logic_registry WHERE g1_validated AND cobra_effect_test) as ec022_cobra_validated_count,

    -- IoS-010 Bridge
    EXISTS(SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'fhq_learning' AND table_name = 'context_annotations'
           AND column_name = 'evaluation_id') as ios010_bridge_ready,

    NOW() as checked_at;

-- ============================================
-- PERMISSIONS
-- ============================================

GRANT SELECT, INSERT, UPDATE ON fhq_learning.shadow_tier_registry TO PUBLIC;
GRANT SELECT ON fhq_learning.v_tier1_calibration_status TO PUBLIC;
GRANT SELECT ON fhq_learning.v_context_rejection_audit TO PUBLIC;
GRANT SELECT ON fhq_learning.v_antithesis_boundary_audit TO PUBLIC;
GRANT SELECT ON fhq_learning.v_context_brier_impact TO PUBLIC;
GRANT SELECT ON fhq_learning.v_addendum_a_readiness TO PUBLIC;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE fhq_learning.shadow_tier_registry IS 'Addendum A Directive 1: Shadow Tier for detecting systematic over-hardening. LARS executes in non-canonical isolation. Cross-contamination = halt Phase III.';

COMMENT ON VIEW fhq_learning.v_context_rejection_audit IS 'Addendum A Directive 2: Answers "Why was this context ignored despite high narrative plausibility?" via Temporal VETO dominance.';

COMMENT ON FUNCTION fhq_learning.validate_antithesis_boundary IS 'Addendum A Directive 3: CSEO can only attack WEAKENED or CANDIDATE hypotheses. Boundary violation raises exception.';

COMMENT ON FUNCTION fhq_learning.calculate_complexity_adjusted_reward IS 'Addendum A Directive 4: Cobra Effect prevention. Trivial hypothesis kills yield severely reduced rewards.';

COMMENT ON VIEW fhq_learning.v_addendum_a_readiness IS 'CEO-level readiness checklist for Addendum A implementation status.';
