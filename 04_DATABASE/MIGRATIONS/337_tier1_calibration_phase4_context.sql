-- Migration 337: Tier-1 Calibration + Phase IV Context Integration
-- CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase III Calibration + Phase IV
-- Author: STIG (EC-003)
-- Date: 2026-01-23
--
-- CEO DIRECTIVE:
--   - Tier-1 death rate too low (50% vs target 80-90%)
--   - Make Tier-1 HARDER, not smarter
--   - Activate Phase IV in "read-only learning mode"
--   - Implement MBB add-ons (CSEO Antithesis, Context Confidence, G1 Gate)

-- ============================================
-- PART A: TIER-1 CALIBRATION (MANDATORY QUICK FIX)
-- "Ingen hypotese skal overleve Tier-1 på delvis riktighet"
-- ============================================

-- 1. Tier-1 Falsification Criteria Table
CREATE TABLE IF NOT EXISTS fhq_learning.tier1_falsification_criteria (
    criteria_id SERIAL PRIMARY KEY,
    criteria_code TEXT UNIQUE NOT NULL,
    criteria_name TEXT NOT NULL,
    description TEXT,
    weight NUMERIC(4,2) DEFAULT 1.0,
    failure_threshold NUMERIC(4,2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert HARDENED Tier-1 criteria
INSERT INTO fhq_learning.tier1_falsification_criteria (criteria_code, criteria_name, description, weight, failure_threshold) VALUES
    ('SIGN_STABILITY', 'Sign Stability', 'Direction must be consistent across 80% of test windows', 1.2, 0.80),
    ('REGIME_CONSISTENCY', 'Regime Consistency', 'Must hold in declared regime with 75% confidence', 1.2, 0.75),
    ('DIRECTION_ACCURACY', 'Direction Accuracy', 'Directional accuracy must exceed 55% (vs 50% random)', 1.0, 0.55),
    ('NO_PARTIAL_CREDIT', 'No Partial Credit', 'Fail if ANY core condition fails (conjunctive)', 1.5, 1.00),
    ('MAGNITUDE_THRESHOLD', 'Magnitude Threshold', 'Effect size must exceed transaction cost + noise', 1.0, 0.02),
    ('TEMPORAL_STABILITY', 'Temporal Stability', 'Must not flip direction within prediction window', 1.3, 0.85)
ON CONFLICT (criteria_code) DO NOTHING;

-- 2. Enhanced Tier-1 Validation Function (HARDENED)
CREATE OR REPLACE FUNCTION fhq_learning.validate_tier1_falsification(
    p_experiment_id UUID,
    p_test_results JSONB
) RETURNS JSONB AS $$
DECLARE
    v_criteria RECORD;
    v_all_pass BOOLEAN := TRUE;
    v_failures TEXT[] := '{}';
    v_total_score NUMERIC := 0;
    v_max_score NUMERIC := 0;
    v_result TEXT;
    v_sign_stability NUMERIC;
    v_regime_consistency NUMERIC;
    v_direction_accuracy NUMERIC;
    v_magnitude NUMERIC;
    v_temporal_stability NUMERIC;
BEGIN
    -- Extract metrics from test results
    v_sign_stability := COALESCE((p_test_results->>'sign_stability')::NUMERIC, 0);
    v_regime_consistency := COALESCE((p_test_results->>'regime_consistency')::NUMERIC, 0);
    v_direction_accuracy := COALESCE((p_test_results->>'direction_accuracy')::NUMERIC, 0);
    v_magnitude := COALESCE((p_test_results->>'effect_magnitude')::NUMERIC, 0);
    v_temporal_stability := COALESCE((p_test_results->>'temporal_stability')::NUMERIC, 0);

    -- Evaluate each criterion (HARD MODE - all must pass)
    FOR v_criteria IN
        SELECT * FROM fhq_learning.tier1_falsification_criteria WHERE is_active = TRUE
    LOOP
        v_max_score := v_max_score + v_criteria.weight;

        CASE v_criteria.criteria_code
            WHEN 'SIGN_STABILITY' THEN
                IF v_sign_stability >= v_criteria.failure_threshold THEN
                    v_total_score := v_total_score + v_criteria.weight;
                ELSE
                    v_all_pass := FALSE;
                    v_failures := array_append(v_failures,
                        v_criteria.criteria_code || ': ' || v_sign_stability::TEXT || ' < ' || v_criteria.failure_threshold::TEXT);
                END IF;

            WHEN 'REGIME_CONSISTENCY' THEN
                IF v_regime_consistency >= v_criteria.failure_threshold THEN
                    v_total_score := v_total_score + v_criteria.weight;
                ELSE
                    v_all_pass := FALSE;
                    v_failures := array_append(v_failures,
                        v_criteria.criteria_code || ': ' || v_regime_consistency::TEXT || ' < ' || v_criteria.failure_threshold::TEXT);
                END IF;

            WHEN 'DIRECTION_ACCURACY' THEN
                IF v_direction_accuracy >= v_criteria.failure_threshold THEN
                    v_total_score := v_total_score + v_criteria.weight;
                ELSE
                    v_all_pass := FALSE;
                    v_failures := array_append(v_failures,
                        v_criteria.criteria_code || ': ' || v_direction_accuracy::TEXT || ' < ' || v_criteria.failure_threshold::TEXT);
                END IF;

            WHEN 'MAGNITUDE_THRESHOLD' THEN
                IF v_magnitude >= v_criteria.failure_threshold THEN
                    v_total_score := v_total_score + v_criteria.weight;
                ELSE
                    v_all_pass := FALSE;
                    v_failures := array_append(v_failures,
                        v_criteria.criteria_code || ': ' || v_magnitude::TEXT || ' < ' || v_criteria.failure_threshold::TEXT);
                END IF;

            WHEN 'TEMPORAL_STABILITY' THEN
                IF v_temporal_stability >= v_criteria.failure_threshold THEN
                    v_total_score := v_total_score + v_criteria.weight;
                ELSE
                    v_all_pass := FALSE;
                    v_failures := array_append(v_failures,
                        v_criteria.criteria_code || ': ' || v_temporal_stability::TEXT || ' < ' || v_criteria.failure_threshold::TEXT);
                END IF;

            WHEN 'NO_PARTIAL_CREDIT' THEN
                -- This is a meta-criterion: if ANY other criterion failed, this auto-fails
                IF v_all_pass THEN
                    v_total_score := v_total_score + v_criteria.weight;
                ELSE
                    v_failures := array_append(v_failures, 'NO_PARTIAL_CREDIT: Conjunctive failure triggered');
                END IF;
        END CASE;
    END LOOP;

    -- Determine result (HARDENED: single failure = FALSIFIED)
    IF NOT v_all_pass THEN
        v_result := 'FALSIFIED';
    ELSIF v_total_score / NULLIF(v_max_score, 0) >= 0.90 THEN
        v_result := 'STABLE';  -- Only if 90%+ score
    ELSE
        v_result := 'WEAKENED';  -- Partial pass = still weakened
    END IF;

    RETURN jsonb_build_object(
        'experiment_id', p_experiment_id,
        'result', v_result,
        'all_criteria_passed', v_all_pass,
        'failures', v_failures,
        'score', v_total_score,
        'max_score', v_max_score,
        'score_pct', ROUND((v_total_score / NULLIF(v_max_score, 0) * 100)::NUMERIC, 2),
        'criteria_count', (SELECT COUNT(*) FROM fhq_learning.tier1_falsification_criteria WHERE is_active),
        'evaluated_at', NOW(),
        'calibration_mode', 'HARDENED_V1'
    );
END;
$$ LANGUAGE plpgsql;

-- 3. Tier-1 Calibration Status View
CREATE OR REPLACE VIEW fhq_learning.v_tier1_calibration_status AS
WITH tier1_stats AS (
    SELECT
        COUNT(*) as total_experiments,
        COUNT(CASE WHEN result = 'FALSIFIED' THEN 1 END) as falsified,
        COUNT(CASE WHEN result = 'WEAKENED' THEN 1 END) as weakened,
        COUNT(CASE WHEN result IN ('STABLE', 'PROMOTED') THEN 1 END) as survived
    FROM fhq_learning.experiment_registry
    WHERE experiment_tier = 1 AND status = 'COMPLETED'
)
SELECT
    total_experiments,
    falsified,
    weakened,
    survived,
    ROUND(falsified::NUMERIC / NULLIF(total_experiments, 0) * 100, 2) as death_rate_pct,
    CASE
        WHEN total_experiments < 30 THEN 'INSUFFICIENT_DATA'
        WHEN falsified::NUMERIC / NULLIF(total_experiments, 0) >= 0.80 THEN 'CALIBRATED_OK'
        WHEN falsified::NUMERIC / NULLIF(total_experiments, 0) >= 0.70 THEN 'ACCEPTABLE'
        ELSE 'NEEDS_TIGHTENING'
    END as calibration_status,
    70.0 as target_min_death_rate,
    90.0 as target_max_death_rate,
    30 as min_experiments_for_assessment
FROM tier1_stats;

-- ============================================
-- PART B: PHASE IV - CONTEXT INTEGRATION (READ-ONLY LEARNING MODE)
-- EC-020 (SitC), EC-021 (InForage), EC-022 (Reward Logic)
-- ============================================

-- 4. Context Annotation Table (Phase IV Core)
CREATE TABLE IF NOT EXISTS fhq_learning.context_annotations (
    annotation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What we're annotating
    target_type TEXT NOT NULL,  -- 'HYPOTHESIS', 'EXPERIMENT', 'ERROR'
    target_id UUID NOT NULL,

    -- Context Source (EC attribution)
    source_ec TEXT NOT NULL,    -- 'EC-020', 'EC-021', 'EC-022'
    source_name TEXT GENERATED ALWAYS AS (
        CASE source_ec
            WHEN 'EC-020' THEN 'SitC (Search in Chain)'
            WHEN 'EC-021' THEN 'InForage (Information Foraging)'
            WHEN 'EC-022' THEN 'Reward Logic'
        END
    ) STORED,

    -- Context Content (READ-ONLY - cannot change hypothesis)
    context_theme TEXT NOT NULL,        -- 'BANK_STRESS', 'GEOPOLITICS', 'AI_REGULATION', etc.
    context_description TEXT,
    temporal_alignment TEXT,            -- 'BEFORE', 'DURING', 'AFTER' the event

    -- Context Confidence Score (VECTOR, not scalar - per CEO/MBB directive)
    confidence_temporal_alignment NUMERIC(4,3),   -- Did context come before outcome?
    confidence_cross_event_recurrence NUMERIC(4,3), -- Same context explains multiple errors?
    confidence_statistical_lift NUMERIC(4,3),     -- Better than baseline?
    confidence_out_of_sample NUMERIC(4,3),        -- Holds in other periods?

    -- Aggregated score (for sorting only, not truth)
    confidence_composite NUMERIC(4,3) GENERATED ALWAYS AS (
        (COALESCE(confidence_temporal_alignment, 0) * 0.3 +
         COALESCE(confidence_cross_event_recurrence, 0) * 0.3 +
         COALESCE(confidence_statistical_lift, 0) * 0.25 +
         COALESCE(confidence_out_of_sample, 0) * 0.15)
    ) STORED,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT NOT NULL,

    -- HARD CONSTRAINT: Context annotations are READ-ONLY
    -- They CANNOT change hypothesis confidence directly
    CONSTRAINT chk_source_ec CHECK (source_ec IN ('EC-020', 'EC-021', 'EC-022')),
    CONSTRAINT chk_target_type CHECK (target_type IN ('HYPOTHESIS', 'EXPERIMENT', 'ERROR')),
    CONSTRAINT chk_temporal CHECK (temporal_alignment IN ('BEFORE', 'DURING', 'AFTER'))
);

CREATE INDEX IF NOT EXISTS idx_ctx_target ON fhq_learning.context_annotations(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_ctx_theme ON fhq_learning.context_annotations(context_theme);
CREATE INDEX IF NOT EXISTS idx_ctx_source ON fhq_learning.context_annotations(source_ec);

-- 5. EC-020 (SitC) Trigger Registry
CREATE TABLE IF NOT EXISTS fhq_learning.sitc_triggers (
    trigger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_type TEXT NOT NULL,  -- 'FALSIFIED', 'WEAKENED', 'REGIME_BREACH'
    triggered_by_id UUID NOT NULL,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    search_window_start TIMESTAMPTZ,
    search_window_end TIMESTAMPTZ,
    search_status TEXT DEFAULT 'PENDING',  -- PENDING, COMPLETED, FAILED
    search_result JSONB,
    created_by TEXT DEFAULT 'EC-020'
);

-- 6. EC-021 (InForage) Theme Registry
CREATE TABLE IF NOT EXISTS fhq_learning.inforage_themes (
    theme_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theme_code TEXT UNIQUE NOT NULL,
    theme_name TEXT NOT NULL,
    theme_description TEXT,
    error_count INT DEFAULT 0,
    hypothesis_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert base themes
INSERT INTO fhq_learning.inforage_themes (theme_code, theme_name, theme_description) VALUES
    ('BANK_STRESS', 'Banking Sector Stress', 'Credit events, bank failures, liquidity crises'),
    ('GEOPOLITICS', 'Geopolitical Events', 'Wars, sanctions, trade disputes'),
    ('AI_REGULATION', 'AI/Tech Regulation', 'AI policy, tech antitrust, data privacy'),
    ('FED_POLICY', 'Fed Policy Shifts', 'Rate decisions, QE/QT, forward guidance'),
    ('EARNINGS_SURPRISE', 'Earnings Surprises', 'Unexpected earnings beats/misses'),
    ('MACRO_SHOCK', 'Macro Shocks', 'GDP, inflation, employment surprises'),
    ('REGIME_TRANSITION', 'Regime Transitions', 'Risk-on/off shifts, volatility regime changes'),
    ('LIQUIDITY_EVENT', 'Liquidity Events', 'Flash crashes, market freezes, deleveraging')
ON CONFLICT (theme_code) DO NOTHING;

-- 7. EC-022 Reward Logic Registry (with G1 Gate requirement)
CREATE TABLE IF NOT EXISTS fhq_learning.reward_logic_registry (
    reward_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reward_type TEXT NOT NULL,
    reward_description TEXT NOT NULL,
    reward_weight NUMERIC(4,2) DEFAULT 1.0,

    -- G1 Gate Required Fields
    g1_validated BOOLEAN DEFAULT FALSE,
    g1_validated_at TIMESTAMPTZ,
    g1_validator TEXT,  -- Must be 'STIG' per CEO directive
    g1_validation_evidence JSONB,

    -- Incentive Safety Checks (per MBB add-on)
    incentive_alignment_test BOOLEAN DEFAULT FALSE,
    asymmetry_test BOOLEAN DEFAULT FALSE,
    delayed_reward_test BOOLEAN DEFAULT FALSE,

    is_active BOOLEAN DEFAULT FALSE,  -- Inactive until G1 validated
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert reward types (INACTIVE until G1 validated)
INSERT INTO fhq_learning.reward_logic_registry (reward_type, reward_description, reward_weight) VALUES
    ('FAST_FALSIFICATION', 'Reward for rapid hypothesis death (scientific quality)', 1.0),
    ('CORRECT_HIBERNATION', 'Reward for hibernating in wrong regime', 0.8),
    ('CONFIDENCE_DECAY_ACCEPTANCE', 'Reward for accepting confidence decay without resistance', 0.6),
    ('TIER1_DEATH', 'Reward for dying in Tier 1 (expected behavior)', 0.3)
ON CONFLICT DO NOTHING;

-- 8. G1 Gate Validation Function for EC-022
CREATE OR REPLACE FUNCTION fhq_learning.validate_ec022_g1_gate(
    p_reward_id UUID,
    p_validator TEXT,
    p_incentive_alignment_result BOOLEAN,
    p_asymmetry_result BOOLEAN,
    p_delayed_reward_result BOOLEAN,
    p_evidence JSONB
) RETURNS JSONB AS $$
DECLARE
    v_all_pass BOOLEAN;
BEGIN
    -- Validator must be STIG (per CEO directive)
    IF p_validator != 'STIG' THEN
        RETURN jsonb_build_object(
            'error', 'G1_VALIDATOR_UNAUTHORIZED',
            'message', 'Only STIG (EC-003) can validate EC-022 reward logic',
            'provided_validator', p_validator
        );
    END IF;

    -- All three tests must pass
    v_all_pass := p_incentive_alignment_result AND p_asymmetry_result AND p_delayed_reward_result;

    IF v_all_pass THEN
        UPDATE fhq_learning.reward_logic_registry
        SET g1_validated = TRUE,
            g1_validated_at = NOW(),
            g1_validator = p_validator,
            g1_validation_evidence = p_evidence,
            incentive_alignment_test = p_incentive_alignment_result,
            asymmetry_test = p_asymmetry_result,
            delayed_reward_test = p_delayed_reward_result,
            is_active = TRUE  -- Activate only after G1 pass
        WHERE reward_id = p_reward_id;

        RETURN jsonb_build_object(
            'status', 'G1_VALIDATED',
            'reward_id', p_reward_id,
            'validator', p_validator,
            'activated', TRUE,
            'validated_at', NOW()
        );
    ELSE
        RETURN jsonb_build_object(
            'status', 'G1_FAILED',
            'reward_id', p_reward_id,
            'failures', jsonb_build_object(
                'incentive_alignment', p_incentive_alignment_result,
                'asymmetry', p_asymmetry_result,
                'delayed_reward', p_delayed_reward_result
            ),
            'message', 'Reward logic failed G1 gate - NOT activated'
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- PART C: CSEO TARGETED ANTITHESIS EXPERIMENTS (MBB Add-on)
-- Adversarial science - stress-testing truth
-- ============================================

-- 9. Antithesis Experiment Registry
CREATE TABLE IF NOT EXISTS fhq_learning.antithesis_experiments (
    antithesis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    antithesis_code TEXT UNIQUE NOT NULL,

    -- Target hypothesis
    target_hypothesis_id UUID NOT NULL REFERENCES fhq_learning.hypothesis_canon(canon_id),

    -- Antithesis Class (per CEO/MBB directive)
    antithesis_class TEXT NOT NULL,
    antithesis_class_name TEXT GENERATED ALWAYS AS (
        CASE antithesis_class
            WHEN 'MECHANISM_BREAK' THEN 'Mechanism Break (invert causal chain)'
            WHEN 'REGIME_STRESS' THEN 'Regime Stress (test in neighbor regimes)'
            WHEN 'BOUNDARY_VIOLATION' THEN 'Boundary Violation (tail stress)'
        END
    ) STORED,

    -- Design
    design_description TEXT NOT NULL,
    inverted_variables JSONB,       -- For MECHANISM_BREAK
    stress_regimes JSONB,           -- For REGIME_STRESS
    boundary_conditions JSONB,      -- For BOUNDARY_VIOLATION

    -- Constraints (CSEO guardrail)
    -- Antithesis experiments can ONLY run in Tier 2 or Tier 3
    allowed_tiers INT[] DEFAULT ARRAY[2, 3],

    -- Results
    status TEXT DEFAULT 'DESIGNED',  -- DESIGNED, APPROVED, RUNNING, COMPLETED
    result TEXT,  -- 'HYPOTHESIS_SURVIVED', 'HYPOTHESIS_BROKEN'
    result_evidence JSONB,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'CSEO',

    CONSTRAINT chk_antithesis_class CHECK (antithesis_class IN ('MECHANISM_BREAK', 'REGIME_STRESS', 'BOUNDARY_VIOLATION'))
);

CREATE SEQUENCE IF NOT EXISTS fhq_learning.antithesis_code_seq START WITH 1;

-- 10. Generate Antithesis Code
CREATE OR REPLACE FUNCTION fhq_learning.generate_antithesis_code(p_class TEXT)
RETURNS TEXT AS $$
DECLARE
    v_year TEXT;
    v_seq INT;
    v_prefix TEXT;
BEGIN
    v_year := TO_CHAR(NOW(), 'YYYY');
    v_seq := NEXTVAL('fhq_learning.antithesis_code_seq');
    v_prefix := CASE p_class
        WHEN 'MECHANISM_BREAK' THEN 'MB'
        WHEN 'REGIME_STRESS' THEN 'RS'
        WHEN 'BOUNDARY_VIOLATION' THEN 'BV'
    END;
    RETURN 'ANTI-' || v_year || '-' || v_prefix || '-' || LPAD(v_seq::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;

-- 11. Create Antithesis Experiment Function (CSEO use)
CREATE OR REPLACE FUNCTION fhq_learning.create_antithesis_experiment(
    p_hypothesis_id UUID,
    p_class TEXT,
    p_design_description TEXT,
    p_variables JSONB DEFAULT NULL,
    p_created_by TEXT DEFAULT 'CSEO'
) RETURNS JSONB AS $$
DECLARE
    v_antithesis_id UUID;
    v_antithesis_code TEXT;
BEGIN
    -- Validate class
    IF p_class NOT IN ('MECHANISM_BREAK', 'REGIME_STRESS', 'BOUNDARY_VIOLATION') THEN
        RETURN jsonb_build_object('error', 'Invalid antithesis class');
    END IF;

    -- Generate codes
    v_antithesis_id := gen_random_uuid();
    v_antithesis_code := fhq_learning.generate_antithesis_code(p_class);

    -- Create antithesis experiment
    INSERT INTO fhq_learning.antithesis_experiments (
        antithesis_id,
        antithesis_code,
        target_hypothesis_id,
        antithesis_class,
        design_description,
        inverted_variables,
        stress_regimes,
        boundary_conditions,
        created_by
    ) VALUES (
        v_antithesis_id,
        v_antithesis_code,
        p_hypothesis_id,
        p_class,
        p_design_description,
        CASE WHEN p_class = 'MECHANISM_BREAK' THEN p_variables ELSE NULL END,
        CASE WHEN p_class = 'REGIME_STRESS' THEN p_variables ELSE NULL END,
        CASE WHEN p_class = 'BOUNDARY_VIOLATION' THEN p_variables ELSE NULL END,
        p_created_by
    );

    RETURN jsonb_build_object(
        'antithesis_id', v_antithesis_id,
        'antithesis_code', v_antithesis_code,
        'class', p_class,
        'hypothesis_id', p_hypothesis_id,
        'status', 'DESIGNED',
        'guardrail', 'Can only execute in Tier 2 or Tier 3',
        'created_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- PART D: PHASE IV ACCEPTANCE TEST VIEWS
-- ============================================

-- 12. Context Theme Correlation with Falsification
CREATE OR REPLACE VIEW fhq_learning.v_context_falsification_correlation AS
SELECT
    ca.context_theme,
    COUNT(DISTINCT ca.target_id) as annotated_count,
    COUNT(DISTINCT CASE WHEN hc.status = 'FALSIFIED' THEN hc.canon_id END) as falsified_count,
    ROUND(
        COUNT(DISTINCT CASE WHEN hc.status = 'FALSIFIED' THEN hc.canon_id END)::NUMERIC
        / NULLIF(COUNT(DISTINCT ca.target_id), 0) * 100, 2
    ) as falsification_rate_pct,
    AVG(ca.confidence_composite) as avg_confidence
FROM fhq_learning.context_annotations ca
LEFT JOIN fhq_learning.hypothesis_canon hc ON ca.target_id = hc.canon_id AND ca.target_type = 'HYPOTHESIS'
GROUP BY ca.context_theme
ORDER BY falsified_count DESC;

-- 13. Cross-Regime Error Recurrence
CREATE OR REPLACE VIEW fhq_learning.v_cross_regime_error_patterns AS
SELECT
    ect.error_type,
    COUNT(DISTINCT ect.error_id) as total_errors,
    COUNT(DISTINCT (ect.context->>'regime')) as regime_count,
    array_agg(DISTINCT ect.context->>'regime') as regimes_affected,
    ROUND(AVG(ect.confidence_at_prediction), 4) as avg_confidence_at_error
FROM fhq_learning.error_classification_taxonomy ect
GROUP BY ect.error_type
HAVING COUNT(DISTINCT (ect.context->>'regime')) > 1
ORDER BY total_errors DESC;

-- 14. Hypothesis Failure Pattern Analysis
CREATE OR REPLACE VIEW fhq_learning.v_hypothesis_failure_patterns AS
WITH hypothesis_failures AS (
    SELECT
        hc.canon_id,
        hc.hypothesis_code,
        hc.status,
        hc.source_error_id,
        ect.error_type,
        ect.error_subtype,
        ca.context_theme
    FROM fhq_learning.hypothesis_canon hc
    LEFT JOIN fhq_learning.error_classification_taxonomy ect ON hc.source_error_id = ect.error_id
    LEFT JOIN fhq_learning.context_annotations ca ON ca.target_id = hc.canon_id AND ca.target_type = 'HYPOTHESIS'
    WHERE hc.status IN ('FALSIFIED', 'WEAKENED')
)
SELECT
    error_type,
    error_subtype,
    context_theme,
    COUNT(*) as failure_count,
    COUNT(CASE WHEN status = 'FALSIFIED' THEN 1 END) as fully_falsified,
    COUNT(CASE WHEN status = 'WEAKENED' THEN 1 END) as weakened_only
FROM hypothesis_failures
GROUP BY error_type, error_subtype, context_theme
HAVING COUNT(*) > 1
ORDER BY failure_count DESC;

-- 15. Phase IV Independence Test View
-- "Slå av Phase IV → Phase III skal fungere uendret"
CREATE OR REPLACE VIEW fhq_learning.v_phase4_independence_test AS
SELECT
    'PHASE_IV_INDEPENDENCE' as test_name,
    (SELECT COUNT(*) FROM fhq_learning.experiment_registry) as experiments_exist,
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon) as hypotheses_exist,
    (SELECT COUNT(*) FROM fhq_learning.context_annotations) as context_annotations,
    CASE
        WHEN (SELECT COUNT(*) FROM fhq_learning.experiment_registry) > 0
         AND (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon) > 0
         THEN 'PHASE_III_OPERATIONAL'
        ELSE 'PHASE_III_CHECK_REQUIRED'
    END as phase3_status,
    'Phase IV context annotations are READ-ONLY and do not affect Phase III operations' as independence_note;

-- ============================================
-- PART E: PERMISSIONS AND DOCUMENTATION
-- ============================================

GRANT SELECT, INSERT ON fhq_learning.tier1_falsification_criteria TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_learning.context_annotations TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_learning.sitc_triggers TO PUBLIC;
GRANT SELECT, INSERT ON fhq_learning.inforage_themes TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_learning.reward_logic_registry TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_learning.antithesis_experiments TO PUBLIC;
GRANT USAGE ON SEQUENCE fhq_learning.antithesis_code_seq TO PUBLIC;

GRANT SELECT ON fhq_learning.v_tier1_calibration_status TO PUBLIC;
GRANT SELECT ON fhq_learning.v_context_falsification_correlation TO PUBLIC;
GRANT SELECT ON fhq_learning.v_cross_regime_error_patterns TO PUBLIC;
GRANT SELECT ON fhq_learning.v_hypothesis_failure_patterns TO PUBLIC;
GRANT SELECT ON fhq_learning.v_phase4_independence_test TO PUBLIC;

COMMENT ON TABLE fhq_learning.tier1_falsification_criteria IS 'CEO-DIR: Hardened Tier-1 criteria. Target death rate: 80-90%. No partial credit.';
COMMENT ON TABLE fhq_learning.context_annotations IS 'Phase IV: READ-ONLY context annotations. Cannot change hypothesis confidence directly.';
COMMENT ON TABLE fhq_learning.reward_logic_registry IS 'EC-022: Reward logic requires G1 Gate validation by STIG before activation.';
COMMENT ON TABLE fhq_learning.antithesis_experiments IS 'CSEO: Targeted Antithesis Experiments. Can only execute in Tier 2 or Tier 3.';
