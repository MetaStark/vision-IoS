-- Migration 335: Hypothesis Canon v1
-- CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase II
-- Author: STIG (EC-003)
-- Date: 2026-01-23

-- ============================================
-- PHASE II: Hypothesis Canon v1 (Logic, Not Trades)
-- ============================================

-- 1. Hypothesis Canon Table (Full Schema from Research)
CREATE TABLE IF NOT EXISTS fhq_learning.hypothesis_canon (
    -- Identity
    canon_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_code TEXT UNIQUE NOT NULL,      -- 'HYP-2026-0001'

    -- Origin (Error-First)
    origin_type TEXT NOT NULL,                 -- 'ERROR_DRIVEN', 'ECONOMIC_THEORY', 'REGIME_CHANGE'
    origin_error_id UUID,                      -- FK to error_classification_taxonomy
    origin_rationale TEXT NOT NULL,            -- Why was this hypothesis born?

    -- Economic Foundation (REQUIRED - prevents data mining)
    economic_rationale TEXT NOT NULL,
    causal_mechanism TEXT NOT NULL,
    behavioral_basis TEXT,
    counterfactual_scenario TEXT NOT NULL,

    -- Event Binding
    event_type_codes TEXT[],                   -- ['US_FOMC', 'BOJ_RATE', 'CPI_RELEASE']
    asset_universe TEXT[],                     -- ['SPY', 'QQQ', 'TLT']

    -- Prediction
    expected_direction TEXT NOT NULL,          -- BULLISH/BEARISH/NEUTRAL
    expected_magnitude TEXT,                   -- HIGH/MEDIUM/LOW
    expected_timeframe_hours NUMERIC NOT NULL,

    -- Regime Dependency (REQUIRED)
    regime_validity TEXT[] NOT NULL,           -- ['RISK_ON', 'RISK_OFF']
    regime_conditional_confidence JSONB NOT NULL, -- {"RISK_ON": 0.7, "RISK_OFF": 0.3}

    -- Falsifiability (Popper)
    falsification_criteria JSONB NOT NULL,     -- When is this hypothesis wrong?
    falsification_count INT DEFAULT 0,
    confidence_decay_rate NUMERIC DEFAULT 0.1,
    max_falsifications INT DEFAULT 3,

    -- Pre-Validation Gate
    pre_validation_passed BOOLEAN DEFAULT FALSE,
    sample_size_historical INT,
    prior_hypotheses_count INT,
    deflated_sharpe_estimate NUMERIC,
    pre_registration_timestamp TIMESTAMPTZ,

    -- Confidence Tracking
    initial_confidence NUMERIC NOT NULL,
    current_confidence NUMERIC,

    -- Lifecycle
    status TEXT DEFAULT 'DRAFT',               -- DRAFT/PRE_VALIDATED/ACTIVE/WEAKENED/FALSIFIED/RETIRED
    activated_at TIMESTAMPTZ,
    falsified_at TIMESTAMPTZ,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT NOT NULL,
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated_by TEXT,

    -- Constraints
    CONSTRAINT chk_hc_origin_type CHECK (origin_type IN ('ERROR_DRIVEN', 'ECONOMIC_THEORY', 'REGIME_CHANGE')),
    CONSTRAINT chk_hc_expected_direction CHECK (expected_direction IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    CONSTRAINT chk_hc_status CHECK (status IN ('DRAFT', 'PRE_VALIDATED', 'ACTIVE', 'WEAKENED', 'FALSIFIED', 'RETIRED')),
    CONSTRAINT chk_hc_confidence_range CHECK (initial_confidence BETWEEN 0.0 AND 1.0),
    CONSTRAINT chk_hc_decay_rate CHECK (confidence_decay_rate BETWEEN 0.0 AND 0.5)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_hc_status ON fhq_learning.hypothesis_canon(status);
CREATE INDEX IF NOT EXISTS idx_hc_origin_error ON fhq_learning.hypothesis_canon(origin_error_id);
CREATE INDEX IF NOT EXISTS idx_hc_created_at ON fhq_learning.hypothesis_canon(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hc_pre_validated ON fhq_learning.hypothesis_canon(pre_validation_passed, status);
CREATE INDEX IF NOT EXISTS idx_hc_event_codes ON fhq_learning.hypothesis_canon USING GIN(event_type_codes);

-- 2. Hypothesis Code Sequence
CREATE SEQUENCE IF NOT EXISTS fhq_learning.hypothesis_code_seq START WITH 1;

-- 3. Generate hypothesis code function
CREATE OR REPLACE FUNCTION fhq_learning.generate_hypothesis_code()
RETURNS TEXT AS $$
DECLARE
    v_year TEXT;
    v_seq INT;
BEGIN
    v_year := TO_CHAR(NOW(), 'YYYY');
    v_seq := NEXTVAL('fhq_learning.hypothesis_code_seq');
    RETURN 'HYP-' || v_year || '-' || LPAD(v_seq::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;

-- 4. Immutability trigger (after pre-registration)
CREATE OR REPLACE FUNCTION fhq_learning.enforce_hypothesis_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.pre_registration_timestamp IS NOT NULL
       AND OLD.status NOT IN ('DRAFT', 'PRE_VALIDATED') THEN
        -- Only allow updates to: current_confidence, falsification_count, status, last_updated fields
        IF NEW.economic_rationale IS DISTINCT FROM OLD.economic_rationale
           OR NEW.causal_mechanism IS DISTINCT FROM OLD.causal_mechanism
           OR NEW.expected_direction IS DISTINCT FROM OLD.expected_direction
           OR NEW.falsification_criteria IS DISTINCT FROM OLD.falsification_criteria
           OR NEW.initial_confidence IS DISTINCT FROM OLD.initial_confidence
           OR NEW.counterfactual_scenario IS DISTINCT FROM OLD.counterfactual_scenario THEN
            RAISE EXCEPTION 'Cannot modify hypothesis after pre-registration. Only confidence, status, and falsification_count updates allowed.';
        END IF;
    END IF;
    NEW.last_updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hypothesis_immutability ON fhq_learning.hypothesis_canon;
CREATE TRIGGER trg_hypothesis_immutability
BEFORE UPDATE ON fhq_learning.hypothesis_canon
FOR EACH ROW EXECUTE FUNCTION fhq_learning.enforce_hypothesis_immutability();

-- 5. Pre-Validation Gate Function
CREATE OR REPLACE FUNCTION fhq_learning.hypothesis_pre_validation_gate(
    p_hypothesis_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_hypothesis RECORD;
    v_result JSONB;
    v_passed BOOLEAN := TRUE;
    v_failures TEXT[] := '{}';
BEGIN
    SELECT * INTO v_hypothesis FROM fhq_learning.hypothesis_canon WHERE canon_id = p_hypothesis_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Hypothesis not found', 'hypothesis_id', p_hypothesis_id);
    END IF;

    -- Check 1: Economic rationale exists and is non-trivial (>50 chars)
    IF v_hypothesis.economic_rationale IS NULL OR LENGTH(v_hypothesis.economic_rationale) < 50 THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'economic_rationale_insufficient');
    END IF;

    -- Check 2: Causal mechanism exists (>30 chars)
    IF v_hypothesis.causal_mechanism IS NULL OR LENGTH(v_hypothesis.causal_mechanism) < 30 THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'causal_mechanism_missing');
    END IF;

    -- Check 3: Falsification criteria defined
    IF v_hypothesis.falsification_criteria IS NULL OR v_hypothesis.falsification_criteria = '{}' THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'falsification_criteria_missing');
    END IF;

    -- Check 4: Regime validity specified
    IF v_hypothesis.regime_validity IS NULL OR array_length(v_hypothesis.regime_validity, 1) IS NULL THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'regime_validity_missing');
    END IF;

    -- Check 5: Sample size >= 30 (prevents overfitting)
    IF v_hypothesis.sample_size_historical IS NULL OR v_hypothesis.sample_size_historical < 30 THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'sample_size_insufficient');
    END IF;

    -- Check 6: Deflated Sharpe <= 1.5 (realism check)
    IF v_hypothesis.deflated_sharpe_estimate IS NOT NULL AND v_hypothesis.deflated_sharpe_estimate > 1.5 THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'deflated_sharpe_unrealistic');
    END IF;

    -- Check 7: Counterfactual scenario defined (>20 chars)
    IF v_hypothesis.counterfactual_scenario IS NULL OR LENGTH(v_hypothesis.counterfactual_scenario) < 20 THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'counterfactual_missing');
    END IF;

    -- Check 8: Origin rationale exists
    IF v_hypothesis.origin_rationale IS NULL OR LENGTH(v_hypothesis.origin_rationale) < 10 THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'origin_rationale_missing');
    END IF;

    -- Update hypothesis status if passed
    IF v_passed THEN
        UPDATE fhq_learning.hypothesis_canon
        SET pre_validation_passed = TRUE,
            status = 'PRE_VALIDATED',
            pre_registration_timestamp = NOW(),
            current_confidence = initial_confidence
        WHERE canon_id = p_hypothesis_id;
    END IF;

    v_result := jsonb_build_object(
        'hypothesis_id', p_hypothesis_id,
        'hypothesis_code', v_hypothesis.hypothesis_code,
        'passed', v_passed,
        'failures', v_failures,
        'total_checks', 8,
        'passed_checks', 8 - array_length(v_failures, 1),
        'checked_at', NOW()
    );

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

-- 6. Confidence Decay Function
CREATE OR REPLACE FUNCTION fhq_learning.hypothesis_confidence_decay(
    p_hypothesis_id UUID,
    p_outcome TEXT  -- 'VALIDATED', 'WEAKENED', 'FALSIFIED'
) RETURNS JSONB AS $$
DECLARE
    v_hypothesis RECORD;
    v_new_confidence NUMERIC;
    v_new_status TEXT;
    v_new_falsification_count INT;
BEGIN
    SELECT * INTO v_hypothesis FROM fhq_learning.hypothesis_canon WHERE canon_id = p_hypothesis_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Hypothesis not found', 'hypothesis_id', p_hypothesis_id);
    END IF;

    v_new_falsification_count := v_hypothesis.falsification_count;
    v_new_status := v_hypothesis.status;

    CASE p_outcome
        WHEN 'VALIDATED' THEN
            -- Confidence maintained or slightly boosted (max 1.0)
            v_new_confidence := LEAST(1.0, COALESCE(v_hypothesis.current_confidence, v_hypothesis.initial_confidence) * 1.05);
            v_new_status := 'ACTIVE';

        WHEN 'WEAKENED' THEN
            -- Apply decay rate
            v_new_confidence := COALESCE(v_hypothesis.current_confidence, v_hypothesis.initial_confidence) * (1 - v_hypothesis.confidence_decay_rate);
            v_new_falsification_count := v_hypothesis.falsification_count + 1;

            -- Check if should be falsified
            IF v_new_falsification_count >= v_hypothesis.max_falsifications THEN
                v_new_status := 'FALSIFIED';
            ELSE
                v_new_status := 'WEAKENED';
            END IF;

        WHEN 'FALSIFIED' THEN
            -- Immediate falsification
            v_new_confidence := 0.0;
            v_new_status := 'FALSIFIED';
            v_new_falsification_count := v_hypothesis.max_falsifications;

        ELSE
            RETURN jsonb_build_object('error', 'Invalid outcome', 'valid_outcomes', ARRAY['VALIDATED', 'WEAKENED', 'FALSIFIED']);
    END CASE;

    -- Update hypothesis
    UPDATE fhq_learning.hypothesis_canon
    SET current_confidence = v_new_confidence,
        status = v_new_status,
        falsification_count = v_new_falsification_count,
        falsified_at = CASE WHEN v_new_status = 'FALSIFIED' THEN NOW() ELSE NULL END,
        last_updated_by = 'SYSTEM'
    WHERE canon_id = p_hypothesis_id;

    RETURN jsonb_build_object(
        'hypothesis_id', p_hypothesis_id,
        'hypothesis_code', v_hypothesis.hypothesis_code,
        'outcome', p_outcome,
        'old_confidence', v_hypothesis.current_confidence,
        'new_confidence', v_new_confidence,
        'old_status', v_hypothesis.status,
        'new_status', v_new_status,
        'falsification_count', v_new_falsification_count,
        'max_falsifications', v_hypothesis.max_falsifications,
        'updated_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- 7. Activate Hypothesis Function
CREATE OR REPLACE FUNCTION fhq_learning.activate_hypothesis(
    p_hypothesis_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_hypothesis RECORD;
BEGIN
    SELECT * INTO v_hypothesis FROM fhq_learning.hypothesis_canon WHERE canon_id = p_hypothesis_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Hypothesis not found');
    END IF;

    IF NOT v_hypothesis.pre_validation_passed THEN
        RETURN jsonb_build_object('error', 'Hypothesis has not passed pre-validation gate');
    END IF;

    IF v_hypothesis.status = 'ACTIVE' THEN
        RETURN jsonb_build_object('error', 'Hypothesis is already active');
    END IF;

    UPDATE fhq_learning.hypothesis_canon
    SET status = 'ACTIVE',
        activated_at = NOW(),
        last_updated_by = 'SYSTEM'
    WHERE canon_id = p_hypothesis_id;

    RETURN jsonb_build_object(
        'hypothesis_id', p_hypothesis_id,
        'hypothesis_code', v_hypothesis.hypothesis_code,
        'status', 'ACTIVE',
        'activated_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- 8. View: Active Hypotheses
CREATE OR REPLACE VIEW fhq_learning.v_active_hypotheses AS
SELECT
    hc.canon_id,
    hc.hypothesis_code,
    hc.origin_type,
    hc.expected_direction,
    hc.expected_magnitude,
    hc.expected_timeframe_hours,
    hc.regime_validity,
    hc.current_confidence,
    hc.falsification_count,
    hc.max_falsifications,
    hc.event_type_codes,
    hc.asset_universe,
    hc.activated_at,
    hc.created_at
FROM fhq_learning.hypothesis_canon hc
WHERE hc.status = 'ACTIVE'
ORDER BY hc.current_confidence DESC;

-- 9. View: Hypothesis Summary
CREATE OR REPLACE VIEW fhq_learning.v_hypothesis_summary AS
SELECT
    status,
    origin_type,
    COUNT(*) as total_hypotheses,
    AVG(initial_confidence) as avg_initial_confidence,
    AVG(current_confidence) as avg_current_confidence,
    AVG(falsification_count) as avg_falsifications,
    COUNT(CASE WHEN pre_validation_passed THEN 1 END) as pre_validated_count
FROM fhq_learning.hypothesis_canon
GROUP BY status, origin_type
ORDER BY status, origin_type;

-- 10. Create hypothesis from error function
CREATE OR REPLACE FUNCTION fhq_learning.create_hypothesis_from_error(
    p_error_id UUID,
    p_economic_rationale TEXT,
    p_causal_mechanism TEXT,
    p_counterfactual_scenario TEXT,
    p_expected_direction TEXT,
    p_expected_timeframe_hours NUMERIC,
    p_regime_validity TEXT[],
    p_initial_confidence NUMERIC,
    p_event_type_codes TEXT[] DEFAULT NULL,
    p_asset_universe TEXT[] DEFAULT NULL,
    p_behavioral_basis TEXT DEFAULT NULL,
    p_expected_magnitude TEXT DEFAULT NULL,
    p_sample_size_historical INT DEFAULT NULL,
    p_deflated_sharpe_estimate NUMERIC DEFAULT NULL,
    p_created_by TEXT DEFAULT 'FINN'
) RETURNS JSONB AS $$
DECLARE
    v_error RECORD;
    v_hypothesis_id UUID;
    v_hypothesis_code TEXT;
    v_regime_conf JSONB;
BEGIN
    -- Validate error exists and hasn't already generated a hypothesis
    SELECT * INTO v_error FROM fhq_learning.error_classification_taxonomy WHERE error_id = p_error_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Error not found', 'error_id', p_error_id);
    END IF;

    IF v_error.hypothesis_generated THEN
        RETURN jsonb_build_object('error', 'Error has already generated a hypothesis', 'existing_hypothesis_id', v_error.generated_hypothesis_id);
    END IF;

    -- Generate hypothesis code
    v_hypothesis_code := fhq_learning.generate_hypothesis_code();
    v_hypothesis_id := gen_random_uuid();

    -- Create default regime conditional confidence
    v_regime_conf := jsonb_build_object();
    FOR i IN 1..array_length(p_regime_validity, 1) LOOP
        v_regime_conf := v_regime_conf || jsonb_build_object(p_regime_validity[i], p_initial_confidence);
    END LOOP;

    -- Create hypothesis
    INSERT INTO fhq_learning.hypothesis_canon (
        canon_id,
        hypothesis_code,
        origin_type,
        origin_error_id,
        origin_rationale,
        economic_rationale,
        causal_mechanism,
        behavioral_basis,
        counterfactual_scenario,
        event_type_codes,
        asset_universe,
        expected_direction,
        expected_magnitude,
        expected_timeframe_hours,
        regime_validity,
        regime_conditional_confidence,
        falsification_criteria,
        sample_size_historical,
        deflated_sharpe_estimate,
        initial_confidence,
        created_by
    ) VALUES (
        v_hypothesis_id,
        v_hypothesis_code,
        'ERROR_DRIVEN',
        p_error_id,
        'Generated from error ' || v_error.error_code || ': ' || v_error.error_type || ' error where predicted=' || v_error.predicted_direction || ' but actual=' || v_error.actual_direction,
        p_economic_rationale,
        p_causal_mechanism,
        p_behavioral_basis,
        p_counterfactual_scenario,
        p_event_type_codes,
        p_asset_universe,
        p_expected_direction,
        p_expected_magnitude,
        p_expected_timeframe_hours,
        p_regime_validity,
        v_regime_conf,
        jsonb_build_object(
            'metric', 'direction_accuracy',
            'condition', 'actual_direction != expected_direction',
            'threshold', 2
        ),
        p_sample_size_historical,
        p_deflated_sharpe_estimate,
        p_initial_confidence,
        p_created_by
    );

    -- Link error to hypothesis
    PERFORM fhq_learning.link_error_to_hypothesis(p_error_id, v_hypothesis_id);

    RETURN jsonb_build_object(
        'hypothesis_id', v_hypothesis_id,
        'hypothesis_code', v_hypothesis_code,
        'origin_error_code', v_error.error_code,
        'status', 'DRAFT',
        'created_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- 11. Grant permissions
GRANT SELECT, INSERT, UPDATE ON fhq_learning.hypothesis_canon TO PUBLIC;
GRANT USAGE ON SEQUENCE fhq_learning.hypothesis_code_seq TO PUBLIC;
GRANT SELECT ON fhq_learning.v_active_hypotheses TO PUBLIC;
GRANT SELECT ON fhq_learning.v_hypothesis_summary TO PUBLIC;

COMMENT ON TABLE fhq_learning.hypothesis_canon IS 'CEO-DIR-2026-HYPOTHESIS-ECONOMY-001 Phase II: Hypothesis Canon v1. MBB-grade hypothesis management with pre-validation gates, falsifiability tracking, and regime-dependent confidence.';
