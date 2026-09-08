-- Migration 336: Phase III - Tiered Experimentation Engine
-- CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase III
-- Author: STIG (EC-003)
-- Date: 2026-01-23
-- CEO Authorization: Phase III approved with mandatory tiered architecture

-- ============================================
-- PHASE III: High-Throughput Experimentation
-- "Phase III er der vi beviser at systemet ikke lyver for seg selv"
-- ============================================

-- 1. Experiment Registry with Tiered Architecture
CREATE TABLE IF NOT EXISTS fhq_learning.experiment_registry (
    experiment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_code TEXT UNIQUE NOT NULL,          -- 'EXP-2026-T1-0001'

    -- Hypothesis Link (REQUIRED - no experiment without hypothesis)
    hypothesis_id UUID NOT NULL REFERENCES fhq_learning.hypothesis_canon(canon_id),
    origin_error_id UUID,                          -- Link back to original error

    -- Tier Classification (MANDATORY)
    experiment_tier INT NOT NULL,                  -- 1, 2, or 3
    tier_name TEXT GENERATED ALWAYS AS (
        CASE experiment_tier
            WHEN 1 THEN 'FALSIFICATION_SWEEP'
            WHEN 2 THEN 'ROBUSTNESS_VALIDATION'
            WHEN 3 THEN 'PROMOTION_CANDIDATE'
        END
    ) STORED,

    -- ASRP Required Fields (fail-closed)
    error_id UUID NOT NULL,                        -- Must link to error
    system_state_hash TEXT NOT NULL,               -- Required for ASRP
    regime_snapshot JSONB NOT NULL,                -- Required for ASRP

    -- Dataset Signature Enforcement
    dataset_signature TEXT NOT NULL,               -- Unique signature for dataset used
    dataset_start_date DATE NOT NULL,
    dataset_end_date DATE NOT NULL,
    dataset_row_count INT NOT NULL,

    -- Experiment Parameters (Tier-specific limits)
    parameters JSONB NOT NULL,                     -- Parameters being tested
    parameter_count INT GENERATED ALWAYS AS (
        jsonb_array_length(COALESCE(parameters->'params', '[]'::jsonb))
    ) STORED,

    -- Degree of Freedom Tracking
    dof_count INT DEFAULT 1,                       -- Degrees of freedom consumed
    prior_experiments_on_hypothesis INT DEFAULT 0, -- How many experiments already run

    -- Execution Mode (MUST be EXPERIMENT)
    execution_mode TEXT NOT NULL DEFAULT 'EXPERIMENT',

    -- Results
    status TEXT DEFAULT 'PENDING',                 -- PENDING/RUNNING/COMPLETED/FAILED
    result TEXT,                                   -- FALSIFIED/WEAKENED/STABLE/PROMOTED
    result_metrics JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by TEXT NOT NULL,

    -- Constraints
    CONSTRAINT chk_tier_valid CHECK (experiment_tier IN (1, 2, 3)),
    CONSTRAINT chk_execution_mode CHECK (execution_mode = 'EXPERIMENT'),
    CONSTRAINT chk_status CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    CONSTRAINT chk_result CHECK (result IS NULL OR result IN ('FALSIFIED', 'WEAKENED', 'STABLE', 'PROMOTED', 'ELIGIBLE_FOR_PAPER')),
    CONSTRAINT chk_tier1_params CHECK (experiment_tier != 1 OR parameter_count <= 3),
    CONSTRAINT chk_asrp_required CHECK (error_id IS NOT NULL AND system_state_hash IS NOT NULL AND regime_snapshot IS NOT NULL)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_exp_hypothesis ON fhq_learning.experiment_registry(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_exp_tier ON fhq_learning.experiment_registry(experiment_tier, status);
CREATE INDEX IF NOT EXISTS idx_exp_dataset_sig ON fhq_learning.experiment_registry(dataset_signature);
CREATE INDEX IF NOT EXISTS idx_exp_created ON fhq_learning.experiment_registry(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_exp_result ON fhq_learning.experiment_registry(result) WHERE result IS NOT NULL;

-- 2. Experiment Code Sequence
CREATE SEQUENCE IF NOT EXISTS fhq_learning.experiment_code_seq START WITH 1;

-- 3. Generate experiment code with tier
CREATE OR REPLACE FUNCTION fhq_learning.generate_experiment_code(p_tier INT)
RETURNS TEXT AS $$
DECLARE
    v_year TEXT;
    v_seq INT;
BEGIN
    v_year := TO_CHAR(NOW(), 'YYYY');
    v_seq := NEXTVAL('fhq_learning.experiment_code_seq');
    RETURN 'EXP-' || v_year || '-T' || p_tier || '-' || LPAD(v_seq::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;

-- 4. ASRP Validation Function (fail-closed)
CREATE OR REPLACE FUNCTION fhq_learning.validate_experiment_asrp(
    p_error_id UUID,
    p_system_state_hash TEXT,
    p_regime_snapshot JSONB
) RETURNS JSONB AS $$
DECLARE
    v_valid BOOLEAN := TRUE;
    v_failures TEXT[] := '{}';
BEGIN
    -- Check 1: error_id exists
    IF p_error_id IS NULL THEN
        v_valid := FALSE;
        v_failures := array_append(v_failures, 'error_id_missing');
    ELSIF NOT EXISTS (SELECT 1 FROM fhq_learning.error_classification_taxonomy WHERE error_id = p_error_id) THEN
        v_valid := FALSE;
        v_failures := array_append(v_failures, 'error_id_invalid');
    END IF;

    -- Check 2: system_state_hash exists
    IF p_system_state_hash IS NULL OR LENGTH(p_system_state_hash) < 8 THEN
        v_valid := FALSE;
        v_failures := array_append(v_failures, 'system_state_hash_missing');
    END IF;

    -- Check 3: regime_snapshot exists and has required fields
    IF p_regime_snapshot IS NULL THEN
        v_valid := FALSE;
        v_failures := array_append(v_failures, 'regime_snapshot_missing');
    ELSIF NOT (p_regime_snapshot ? 'regime' AND p_regime_snapshot ? 'timestamp') THEN
        v_valid := FALSE;
        v_failures := array_append(v_failures, 'regime_snapshot_incomplete');
    END IF;

    RETURN jsonb_build_object(
        'valid', v_valid,
        'failures', v_failures,
        'checked_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- 5. Dataset Signature Enforcement
CREATE OR REPLACE FUNCTION fhq_learning.check_dataset_reuse(
    p_dataset_signature TEXT,
    p_hypothesis_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_existing_count INT;
    v_allowed BOOLEAN;
BEGIN
    -- Check if this exact dataset has been used for this hypothesis
    SELECT COUNT(*) INTO v_existing_count
    FROM fhq_learning.experiment_registry
    WHERE hypothesis_id = p_hypothesis_id
      AND dataset_signature = p_dataset_signature;

    v_allowed := (v_existing_count = 0);

    RETURN jsonb_build_object(
        'allowed', v_allowed,
        'existing_uses', v_existing_count,
        'warning', CASE WHEN NOT v_allowed THEN 'Dataset already used for this hypothesis - requires explicit approval' ELSE NULL END
    );
END;
$$ LANGUAGE plpgsql;

-- 6. Degree of Freedom Penalty Calculator
CREATE OR REPLACE FUNCTION fhq_learning.calculate_dof_penalty(
    p_hypothesis_id UUID,
    p_new_dof INT DEFAULT 1
) RETURNS JSONB AS $$
DECLARE
    v_total_experiments INT;
    v_total_dof INT;
    v_penalty_factor NUMERIC;
    v_recommended_confidence_multiplier NUMERIC;
BEGIN
    -- Count total experiments and DOF for this hypothesis
    SELECT
        COUNT(*),
        COALESCE(SUM(dof_count), 0)
    INTO v_total_experiments, v_total_dof
    FROM fhq_learning.experiment_registry
    WHERE hypothesis_id = p_hypothesis_id;

    -- Add new DOF
    v_total_dof := v_total_dof + p_new_dof;

    -- Calculate penalty (logarithmic decay)
    -- More experiments = lower confidence multiplier
    v_penalty_factor := LN(v_total_dof + 1) / 10.0;
    v_recommended_confidence_multiplier := GREATEST(0.5, 1.0 - v_penalty_factor);

    RETURN jsonb_build_object(
        'total_experiments', v_total_experiments + 1,
        'total_dof', v_total_dof,
        'penalty_factor', ROUND(v_penalty_factor::NUMERIC, 4),
        'confidence_multiplier', ROUND(v_recommended_confidence_multiplier, 4),
        'warning', CASE
            WHEN v_total_dof > 20 THEN 'HIGH DOF WARNING: Risk of overfitting'
            WHEN v_total_dof > 10 THEN 'MEDIUM DOF WARNING: Monitor closely'
            ELSE NULL
        END
    );
END;
$$ LANGUAGE plpgsql;

-- 7. Create Experiment Function (with all guardrails)
CREATE OR REPLACE FUNCTION fhq_learning.create_experiment(
    p_hypothesis_id UUID,
    p_tier INT,
    p_error_id UUID,
    p_system_state_hash TEXT,
    p_regime_snapshot JSONB,
    p_dataset_signature TEXT,
    p_dataset_start DATE,
    p_dataset_end DATE,
    p_dataset_rows INT,
    p_parameters JSONB,
    p_created_by TEXT DEFAULT 'STIG'
) RETURNS JSONB AS $$
DECLARE
    v_asrp_check JSONB;
    v_dataset_check JSONB;
    v_dof_check JSONB;
    v_experiment_id UUID;
    v_experiment_code TEXT;
    v_prior_experiments INT;
    v_param_count INT;
BEGIN
    -- ASRP Validation (fail-closed)
    v_asrp_check := fhq_learning.validate_experiment_asrp(p_error_id, p_system_state_hash, p_regime_snapshot);
    IF NOT (v_asrp_check->>'valid')::BOOLEAN THEN
        RETURN jsonb_build_object(
            'error', 'ASRP_VALIDATION_FAILED',
            'details', v_asrp_check,
            'action', 'REJECT + ASRP escalation'
        );
    END IF;

    -- Dataset Reuse Check
    v_dataset_check := fhq_learning.check_dataset_reuse(p_dataset_signature, p_hypothesis_id);
    IF NOT (v_dataset_check->>'allowed')::BOOLEAN THEN
        RETURN jsonb_build_object(
            'error', 'DATASET_REUSE_BLOCKED',
            'details', v_dataset_check,
            'action', 'Requires explicit CEO approval for dataset reuse'
        );
    END IF;

    -- Tier 1 Parameter Limit Check
    v_param_count := jsonb_array_length(COALESCE(p_parameters->'params', '[]'::jsonb));
    IF p_tier = 1 AND v_param_count > 3 THEN
        RETURN jsonb_build_object(
            'error', 'TIER1_PARAM_LIMIT_EXCEEDED',
            'param_count', v_param_count,
            'max_allowed', 3,
            'action', 'Reduce parameters or move to Tier 2'
        );
    END IF;

    -- DOF Penalty Calculation
    v_dof_check := fhq_learning.calculate_dof_penalty(p_hypothesis_id, v_param_count);

    -- Get prior experiment count
    SELECT COUNT(*) INTO v_prior_experiments
    FROM fhq_learning.experiment_registry
    WHERE hypothesis_id = p_hypothesis_id;

    -- Generate codes
    v_experiment_id := gen_random_uuid();
    v_experiment_code := fhq_learning.generate_experiment_code(p_tier);

    -- Create experiment
    INSERT INTO fhq_learning.experiment_registry (
        experiment_id,
        experiment_code,
        hypothesis_id,
        origin_error_id,
        experiment_tier,
        error_id,
        system_state_hash,
        regime_snapshot,
        dataset_signature,
        dataset_start_date,
        dataset_end_date,
        dataset_row_count,
        parameters,
        dof_count,
        prior_experiments_on_hypothesis,
        execution_mode,
        created_by
    ) VALUES (
        v_experiment_id,
        v_experiment_code,
        p_hypothesis_id,
        p_error_id,
        p_tier,
        p_error_id,
        p_system_state_hash,
        p_regime_snapshot,
        p_dataset_signature,
        p_dataset_start,
        p_dataset_end,
        p_dataset_rows,
        p_parameters,
        v_param_count,
        v_prior_experiments,
        'EXPERIMENT',
        p_created_by
    );

    RETURN jsonb_build_object(
        'experiment_id', v_experiment_id,
        'experiment_code', v_experiment_code,
        'tier', p_tier,
        'tier_name', CASE p_tier WHEN 1 THEN 'FALSIFICATION_SWEEP' WHEN 2 THEN 'ROBUSTNESS_VALIDATION' WHEN 3 THEN 'PROMOTION_CANDIDATE' END,
        'dof_penalty', v_dof_check,
        'status', 'PENDING',
        'created_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- 8. Record Experiment Result Function
CREATE OR REPLACE FUNCTION fhq_learning.record_experiment_result(
    p_experiment_id UUID,
    p_result TEXT,
    p_metrics JSONB
) RETURNS JSONB AS $$
DECLARE
    v_experiment RECORD;
    v_hypothesis_update JSONB;
BEGIN
    -- Get experiment
    SELECT * INTO v_experiment
    FROM fhq_learning.experiment_registry
    WHERE experiment_id = p_experiment_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Experiment not found');
    END IF;

    -- Update experiment
    UPDATE fhq_learning.experiment_registry
    SET status = 'COMPLETED',
        result = p_result,
        result_metrics = p_metrics,
        completed_at = NOW()
    WHERE experiment_id = p_experiment_id;

    -- Update hypothesis based on result
    IF p_result = 'FALSIFIED' THEN
        v_hypothesis_update := fhq_learning.hypothesis_confidence_decay(v_experiment.hypothesis_id, 'FALSIFIED');
    ELSIF p_result = 'WEAKENED' THEN
        v_hypothesis_update := fhq_learning.hypothesis_confidence_decay(v_experiment.hypothesis_id, 'WEAKENED');
    ELSIF p_result IN ('STABLE', 'PROMOTED', 'ELIGIBLE_FOR_PAPER') THEN
        v_hypothesis_update := fhq_learning.hypothesis_confidence_decay(v_experiment.hypothesis_id, 'VALIDATED');
    END IF;

    RETURN jsonb_build_object(
        'experiment_id', p_experiment_id,
        'result', p_result,
        'hypothesis_update', v_hypothesis_update,
        'completed_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- 9. Tier Statistics View (for acceptance tests)
CREATE OR REPLACE VIEW fhq_learning.v_tier_statistics AS
SELECT
    experiment_tier,
    tier_name,
    COUNT(*) as total_experiments,
    COUNT(CASE WHEN result = 'FALSIFIED' THEN 1 END) as falsified_count,
    COUNT(CASE WHEN result = 'WEAKENED' THEN 1 END) as weakened_count,
    COUNT(CASE WHEN result IN ('STABLE', 'PROMOTED', 'ELIGIBLE_FOR_PAPER') THEN 1 END) as survived_count,
    ROUND(
        COUNT(CASE WHEN result = 'FALSIFIED' THEN 1 END)::NUMERIC
        / NULLIF(COUNT(CASE WHEN result IS NOT NULL THEN 1 END), 0) * 100, 2
    ) as death_rate_pct,
    AVG(dof_count) as avg_dof
FROM fhq_learning.experiment_registry
GROUP BY experiment_tier, tier_name
ORDER BY experiment_tier;

-- 10. Daily Experiment Summary View
CREATE OR REPLACE VIEW fhq_learning.v_daily_experiment_summary AS
SELECT
    DATE_TRUNC('day', created_at) as experiment_date,
    experiment_tier,
    COUNT(*) as experiments_run,
    COUNT(CASE WHEN result = 'FALSIFIED' THEN 1 END) as died,
    COUNT(CASE WHEN result IN ('STABLE', 'PROMOTED') THEN 1 END) as survived,
    ROUND(
        COUNT(CASE WHEN result = 'FALSIFIED' THEN 1 END)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2
    ) as death_rate_pct
FROM fhq_learning.experiment_registry
WHERE result IS NOT NULL
GROUP BY DATE_TRUNC('day', created_at), experiment_tier
ORDER BY experiment_date DESC, experiment_tier;

-- 11. Hypothesis Experiment Count View (DOF tracking)
CREATE OR REPLACE VIEW fhq_learning.v_hypothesis_dof_summary AS
SELECT
    hc.canon_id,
    hc.hypothesis_code,
    hc.status as hypothesis_status,
    hc.current_confidence,
    COUNT(er.experiment_id) as total_experiments,
    SUM(er.dof_count) as total_dof,
    COUNT(CASE WHEN er.result = 'FALSIFIED' THEN 1 END) as falsified_experiments,
    COUNT(CASE WHEN er.experiment_tier = 1 THEN 1 END) as tier1_experiments,
    COUNT(CASE WHEN er.experiment_tier = 2 THEN 1 END) as tier2_experiments,
    COUNT(CASE WHEN er.experiment_tier = 3 THEN 1 END) as tier3_experiments
FROM fhq_learning.hypothesis_canon hc
LEFT JOIN fhq_learning.experiment_registry er ON er.hypothesis_id = hc.canon_id
GROUP BY hc.canon_id, hc.hypothesis_code, hc.status, hc.current_confidence;

-- 12. P-Hacking Drift Detection View (STOP CONDITIONS)
CREATE OR REPLACE VIEW fhq_learning.v_phacking_drift_monitor AS
WITH daily_stats AS (
    SELECT
        DATE_TRUNC('day', created_at) as day,
        COUNT(*) as experiments,
        COUNT(CASE WHEN result = 'FALSIFIED' THEN 1 END) as deaths,
        AVG(dof_count) as avg_dof
    FROM fhq_learning.experiment_registry
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY DATE_TRUNC('day', created_at)
)
SELECT
    day,
    experiments,
    deaths,
    ROUND(deaths::NUMERIC / NULLIF(experiments, 0) * 100, 2) as death_rate_pct,
    avg_dof,
    CASE
        WHEN deaths::NUMERIC / NULLIF(experiments, 0) < 0.5 THEN 'WARNING: Low death rate - possible p-hacking'
        WHEN experiments > LAG(experiments) OVER (ORDER BY day) * 1.5
             AND deaths::NUMERIC / NULLIF(experiments, 0) < LAG(deaths::NUMERIC / NULLIF(experiments, 0)) OVER (ORDER BY day)
             THEN 'ALERT: Volume increasing but death rate dropping'
        ELSE 'OK'
    END as drift_status
FROM daily_stats
ORDER BY day DESC;

-- 13. Grant permissions
GRANT SELECT, INSERT, UPDATE ON fhq_learning.experiment_registry TO PUBLIC;
GRANT USAGE ON SEQUENCE fhq_learning.experiment_code_seq TO PUBLIC;
GRANT SELECT ON fhq_learning.v_tier_statistics TO PUBLIC;
GRANT SELECT ON fhq_learning.v_daily_experiment_summary TO PUBLIC;
GRANT SELECT ON fhq_learning.v_hypothesis_dof_summary TO PUBLIC;
GRANT SELECT ON fhq_learning.v_phacking_drift_monitor TO PUBLIC;

COMMENT ON TABLE fhq_learning.experiment_registry IS 'CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase III: Tiered Experimentation Engine. Tier 1 = Falsification Sweep (80-90% should die). Tier 2 = Robustness Validation. Tier 3 = Promotion Candidate. All experiments require ASRP compliance.';
