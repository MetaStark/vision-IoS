# CEO-DIR-2026-HYPOTHESIS-ECONOMY-001
# Implementation Plan: Autonomous, Error-Driven Hypothesis Economy

**Directive:** CEO-DIR-2026-HYPOTHESIS-ECONOMY-001
**Author:** STIG (EC-003)
**Date:** 2026-01-23
**Status:** PLAN AWAITING CEO APPROVAL

---

## Executive Summary

This plan implements a 6-phase Autonomous, Error-Driven Hypothesis Economy based on:
- MBB-grade research (Bridgewater, AQR, Two Sigma methodologies)
- Existing FjordHQ learning infrastructure (migrations 332, 333)
- ASRP/ADR-018 compliance requirements
- EC-020 (SitC), EC-021 (InForage), EC-022 (IKEA) integration

**Current State Assessment:**
| Component | Status | Rows | Gap |
|-----------|--------|------|-----|
| `outcome_ledger` | POPULATED | 31,289 | None - ready for learning |
| `hypothesis_ledger` | SPARSE | 8 | Needs automation |
| `decision_experiment_ledger` | EMPTY | 0 | Requires hypothesis flow |
| `expectation_outcome_ledger` | EMPTY | 0 | Requires hypothesis flow |
| ASRP compliance | IN PLACE | - | State binding active |

---

## Phase I: Error-First Learning Foundation

**Objective:** Ensure every prediction error becomes a learning opportunity

### I.1 Deliverables

| # | Deliverable | Owner | Schema/Table |
|---|-------------|-------|--------------|
| I.1.1 | `error_classification_taxonomy` table | STIG | `fhq_learning` |
| I.1.2 | `error_detector_daemon.py` | STIG | Daemon |
| I.1.3 | Error-to-Hypothesis linkage function | STIG | `fhq_learning` |
| I.1.4 | Migration 334: Error Learning Foundation | STIG | Database |

### I.2 Error Classification Taxonomy

```sql
CREATE TABLE fhq_learning.error_classification_taxonomy (
    error_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_code TEXT UNIQUE NOT NULL,           -- 'ERR-DIR-2026-0001'
    error_type TEXT NOT NULL,                  -- 'DIRECTION', 'MAGNITUDE', 'TIMING', 'REGIME'

    -- Source identification
    source_signal_id UUID,                     -- FK to unified_signal_log
    source_prediction_id UUID,                 -- FK to outcome_ledger
    source_hypothesis_id UUID,                 -- FK to hypothesis_ledger (if exists)

    -- Error characteristics
    predicted_direction TEXT,                  -- BULLISH/BEARISH/NEUTRAL
    actual_direction TEXT,                     -- BULLISH/BEARISH/NEUTRAL
    direction_error BOOLEAN GENERATED ALWAYS AS (predicted_direction != actual_direction) STORED,

    predicted_magnitude NUMERIC,
    actual_magnitude NUMERIC,
    magnitude_error_pct NUMERIC,

    predicted_timeframe_hours NUMERIC,
    actual_timeframe_hours NUMERIC,
    timing_error_hours NUMERIC,

    -- Context at time of error
    regime_at_prediction TEXT,                 -- RISK_ON/RISK_OFF/TRANSITION
    regime_at_outcome TEXT,
    regime_mismatch BOOLEAN GENERATED ALWAYS AS (regime_at_prediction != regime_at_outcome) STORED,

    -- Causal attribution (Phase IV integration)
    causal_attribution JSONB,                  -- Which factors contributed?
    confidence_at_prediction NUMERIC,

    -- Learning potential
    learning_priority TEXT DEFAULT 'MEDIUM',   -- HIGH/MEDIUM/LOW
    hypothesis_generated BOOLEAN DEFAULT FALSE,
    hypothesis_id UUID,                        -- FK to hypothesis_canon when generated

    -- Timestamps
    error_detected_at TIMESTAMPTZ DEFAULT NOW(),
    prediction_timestamp TIMESTAMPTZ,
    outcome_timestamp TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'SYSTEM'
);

-- Index for high-priority error detection
CREATE INDEX idx_error_learning_priority ON fhq_learning.error_classification_taxonomy(learning_priority, hypothesis_generated);
CREATE INDEX idx_error_type ON fhq_learning.error_classification_taxonomy(error_type);
```

### I.3 Error Detector Daemon Logic

```
PSEUDOCODE: error_detector_daemon.py

EVERY 15 MINUTES:
    1. Query outcome_ledger for resolved predictions (T+24h, T+48h, T+7d)
    2. Compare predicted_direction vs actual_direction
    3. For each mismatch:
        a. Classify error type (DIRECTION, MAGNITUDE, TIMING, REGIME)
        b. Calculate magnitude_error_pct
        c. Check regime_mismatch
        d. Assign learning_priority:
           - HIGH: Direction error with confidence > 0.6
           - HIGH: Regime mismatch errors
           - MEDIUM: Magnitude errors > 50%
           - LOW: Timing errors < 24h
        e. Insert into error_classification_taxonomy
    4. Log evidence file with error summary
```

### I.4 Acceptance Tests (Phase I)

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| I.T1 | Error detection runs | Daemon executes without error |
| I.T2 | Errors classified | >= 1 error in taxonomy table |
| I.T3 | Priority assignment | HIGH/MEDIUM/LOW distributed |
| I.T4 | Regime mismatch detected | regime_mismatch = TRUE for applicable |

---

## Phase II: Hypothesis Canon v1 (Logic, Not Trades)

**Objective:** Implement the full Hypothesis Canon schema with pre-validation gates

### II.1 Deliverables

| # | Deliverable | Owner | Schema/Table |
|---|-------------|-------|--------------|
| II.1.1 | `hypothesis_canon` table (full schema) | STIG | `fhq_learning` |
| II.1.2 | `hypothesis_pre_validation_gate()` function | STIG | `fhq_learning` |
| II.1.3 | `hypothesis_confidence_decay()` function | STIG | `fhq_learning` |
| II.1.4 | `hypothesis_generation_daemon.py` | FINN | Daemon |
| II.1.5 | FINN write_mandate extension | STIG (CEO approval) | `fhq_governance` |
| II.1.6 | Migration 335: Hypothesis Canon v1 | STIG | Database |

### II.2 Hypothesis Canon Schema (From Research)

```sql
CREATE TABLE fhq_learning.hypothesis_canon (
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
    CONSTRAINT chk_origin_type CHECK (origin_type IN ('ERROR_DRIVEN', 'ECONOMIC_THEORY', 'REGIME_CHANGE')),
    CONSTRAINT chk_expected_direction CHECK (expected_direction IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
    CONSTRAINT chk_status CHECK (status IN ('DRAFT', 'PRE_VALIDATED', 'ACTIVE', 'WEAKENED', 'FALSIFIED', 'RETIRED')),
    CONSTRAINT chk_confidence_range CHECK (initial_confidence BETWEEN 0.0 AND 1.0),
    CONSTRAINT chk_decay_rate CHECK (confidence_decay_rate BETWEEN 0.0 AND 0.5)
);

-- Immutability after pre-registration
CREATE OR REPLACE FUNCTION fhq_learning.enforce_hypothesis_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.pre_registration_timestamp IS NOT NULL
       AND OLD.status NOT IN ('DRAFT', 'PRE_VALIDATED') THEN
        -- Only allow updates to: current_confidence, falsification_count, status
        IF NEW.economic_rationale != OLD.economic_rationale
           OR NEW.causal_mechanism != OLD.causal_mechanism
           OR NEW.expected_direction != OLD.expected_direction
           OR NEW.falsification_criteria != OLD.falsification_criteria THEN
            RAISE EXCEPTION 'Cannot modify hypothesis after pre-registration. Only confidence and status updates allowed.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_hypothesis_immutability
BEFORE UPDATE ON fhq_learning.hypothesis_canon
FOR EACH ROW EXECUTE FUNCTION fhq_learning.enforce_hypothesis_immutability();
```

### II.3 Pre-Validation Gate Function

```sql
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

    -- Check 1: Economic rationale exists and is non-trivial (>50 chars)
    IF v_hypothesis.economic_rationale IS NULL OR LENGTH(v_hypothesis.economic_rationale) < 50 THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'economic_rationale_insufficient');
    END IF;

    -- Check 2: Causal mechanism exists
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
    IF v_hypothesis.regime_validity IS NULL OR array_length(v_hypothesis.regime_validity, 1) = 0 THEN
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

    -- Check 7: Counterfactual scenario defined
    IF v_hypothesis.counterfactual_scenario IS NULL OR LENGTH(v_hypothesis.counterfactual_scenario) < 20 THEN
        v_passed := FALSE;
        v_failures := array_append(v_failures, 'counterfactual_missing');
    END IF;

    -- Update hypothesis status if passed
    IF v_passed THEN
        UPDATE fhq_learning.hypothesis_canon
        SET pre_validation_passed = TRUE,
            status = 'PRE_VALIDATED',
            pre_registration_timestamp = NOW()
        WHERE canon_id = p_hypothesis_id;
    END IF;

    v_result := jsonb_build_object(
        'hypothesis_id', p_hypothesis_id,
        'passed', v_passed,
        'failures', v_failures,
        'checked_at', NOW()
    );

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;
```

### II.4 Confidence Decay Function

```sql
CREATE OR REPLACE FUNCTION fhq_learning.hypothesis_confidence_decay(
    p_hypothesis_id UUID,
    p_outcome TEXT  -- 'VALIDATED', 'WEAKENED', 'FALSIFIED'
) RETURNS JSONB AS $$
DECLARE
    v_hypothesis RECORD;
    v_new_confidence NUMERIC;
    v_new_status TEXT;
BEGIN
    SELECT * INTO v_hypothesis FROM fhq_learning.hypothesis_canon WHERE canon_id = p_hypothesis_id;

    CASE p_outcome
        WHEN 'VALIDATED' THEN
            -- Confidence maintained or slightly boosted (max 1.0)
            v_new_confidence := LEAST(1.0, v_hypothesis.current_confidence * 1.05);
            v_new_status := 'ACTIVE';

        WHEN 'WEAKENED' THEN
            -- Apply decay rate
            v_new_confidence := v_hypothesis.current_confidence * (1 - v_hypothesis.confidence_decay_rate);

            -- Update falsification count
            UPDATE fhq_learning.hypothesis_canon
            SET falsification_count = falsification_count + 1
            WHERE canon_id = p_hypothesis_id;

            -- Check if should be falsified
            IF v_hypothesis.falsification_count + 1 >= v_hypothesis.max_falsifications THEN
                v_new_status := 'FALSIFIED';
            ELSE
                v_new_status := 'WEAKENED';
            END IF;

        WHEN 'FALSIFIED' THEN
            -- Immediate falsification
            v_new_confidence := 0.0;
            v_new_status := 'FALSIFIED';
    END CASE;

    -- Update hypothesis
    UPDATE fhq_learning.hypothesis_canon
    SET current_confidence = v_new_confidence,
        status = v_new_status,
        falsified_at = CASE WHEN v_new_status = 'FALSIFIED' THEN NOW() ELSE NULL END,
        last_updated_at = NOW(),
        last_updated_by = 'SYSTEM'
    WHERE canon_id = p_hypothesis_id;

    RETURN jsonb_build_object(
        'hypothesis_id', p_hypothesis_id,
        'outcome', p_outcome,
        'old_confidence', v_hypothesis.current_confidence,
        'new_confidence', v_new_confidence,
        'new_status', v_new_status,
        'updated_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;
```

### II.5 Acceptance Tests (Phase II)

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| II.T1 | Schema created | `hypothesis_canon` table exists |
| II.T2 | Pre-validation gate rejects incomplete | Returns `passed: false` for missing fields |
| II.T3 | Pre-validation gate accepts complete | Returns `passed: true` for valid hypothesis |
| II.T4 | Immutability enforced | UPDATE fails on locked hypothesis |
| II.T5 | Confidence decay works | Decay formula applied correctly |
| II.T6 | FINN write_mandate active | FINN can insert into hypothesis_canon |

---

## Phase III: High-Throughput Experimentation

**Objective:** Enable rapid hypothesis testing with statistical rigor

### III.1 Deliverables

| # | Deliverable | Owner | Schema/Table |
|---|-------------|-------|--------------|
| III.1.1 | `experiment_runner_daemon.py` | STIG | Daemon |
| III.1.2 | `experiment_result_recorder()` function | STIG | `fhq_learning` |
| III.1.3 | `v_hypothesis_performance` view | STIG | `fhq_learning` |
| III.1.4 | Backfill existing signals as experiments | STIG | Migration |
| III.1.5 | Migration 336: Experiment Infrastructure | STIG | Database |

### III.2 Experiment Flow

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Hypothesis Activation                               │
│  hypothesis_canon.status = 'ACTIVE'                          │
│  pre_registration_timestamp locked                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Event Detection (calendar_integrity_daemon)         │
│  Upcoming event matches hypothesis.event_type_codes          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Experiment Creation                                 │
│  INSERT INTO decision_experiment_ledger (                    │
│    hypothesis_id,                                            │
│    event_id,                                                 │
│    regime_at_creation,                                       │
│    expected_direction,                                       │
│    expected_timeframe_hours                                  │
│  )                                                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Event Occurs                                        │
│  actual_outcome captured in outcome_ledger                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Experiment Resolution (T + timeframe)               │
│  UPDATE decision_experiment_ledger SET                       │
│    actual_direction = ...,                                   │
│    actual_magnitude = ...,                                   │
│    verdict = 'VALIDATED' | 'WEAKENED' | 'FALSIFIED'          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 6: Hypothesis Update                                   │
│  CALL hypothesis_confidence_decay(hypothesis_id, verdict)    │
└─────────────────────────────────────────────────────────────┘
```

### III.3 Performance View

```sql
CREATE OR REPLACE VIEW fhq_learning.v_hypothesis_performance AS
SELECT
    hc.canon_id,
    hc.hypothesis_code,
    hc.status,
    hc.initial_confidence,
    hc.current_confidence,
    hc.falsification_count,
    hc.max_falsifications,
    COUNT(del.experiment_id) AS total_experiments,
    COUNT(CASE WHEN del.verdict = 'VALIDATED' THEN 1 END) AS validated_count,
    COUNT(CASE WHEN del.verdict = 'WEAKENED' THEN 1 END) AS weakened_count,
    COUNT(CASE WHEN del.verdict = 'FALSIFIED' THEN 1 END) AS falsified_count,
    CASE
        WHEN COUNT(del.experiment_id) > 0
        THEN ROUND(
            COUNT(CASE WHEN del.verdict = 'VALIDATED' THEN 1 END)::NUMERIC
            / COUNT(del.experiment_id) * 100, 2
        )
        ELSE 0
    END AS hit_rate_pct,
    hc.created_at,
    hc.activated_at,
    hc.falsified_at
FROM fhq_learning.hypothesis_canon hc
LEFT JOIN fhq_learning.decision_experiment_ledger del ON del.hypothesis_id = hc.canon_id
GROUP BY hc.canon_id, hc.hypothesis_code, hc.status, hc.initial_confidence,
         hc.current_confidence, hc.falsification_count, hc.max_falsifications,
         hc.created_at, hc.activated_at, hc.falsified_at;
```

### III.4 Acceptance Tests (Phase III)

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| III.T1 | Experiment creation works | >= 1 row in decision_experiment_ledger |
| III.T2 | Verdict assignment works | verdict column populated |
| III.T3 | Performance view accurate | hit_rate_pct calculates correctly |
| III.T4 | Confidence decay triggers | current_confidence decreases on WEAKENED |

---

## Phase IV: Context Integration (EC-020/021/022)

**Objective:** Integrate SitC, InForage, and IKEA for rich hypothesis context

### IV.1 EC-020 (SitC) Integration - Reasoning Chains

| Requirement | Implementation |
|-------------|----------------|
| Chain reasoning before hypothesis | `hypothesis_canon.sitc_chain_id` FK |
| Audit trail of decision logic | `reasoning_chain_ledger` linked |
| Prevent hallucinated rationale | IKEA validation before insert |

### IV.2 EC-021 (InForage) Integration - Information Efficiency

| Requirement | Implementation |
|-------------|----------------|
| Track information cost | `hypothesis_canon.inforage_cost` |
| Optimize search patterns | InForage suggests data sources |
| Avoid redundant queries | Query deduplication layer |

### IV.3 EC-022 (IKEA) Integration - Hallucination Firewall

| Requirement | Implementation |
|-------------|----------------|
| Validate economic_rationale | IKEA check before pre-validation |
| Verify causal_mechanism | Cross-reference with known models |
| Flag speculative claims | `hallucination_risk_score` field |

### IV.4 Deliverables

| # | Deliverable | Owner | Schema/Table |
|---|-------------|-------|--------------|
| IV.1.1 | Add `sitc_chain_id` to hypothesis_canon | STIG | Migration |
| IV.1.2 | Add `inforage_cost` tracking | STIG | Migration |
| IV.1.3 | Add `hallucination_risk_score` | STIG | Migration |
| IV.1.4 | IKEA validation function | STIG | `fhq_learning` |
| IV.1.5 | Migration 337: Context Integration | STIG | Database |

### IV.5 Acceptance Tests (Phase IV)

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| IV.T1 | SitC chain linkage works | sitc_chain_id references valid chain |
| IV.T2 | InForage cost tracked | inforage_cost > 0 for hypotheses |
| IV.T3 | IKEA validation runs | hallucination_risk_score assigned |
| IV.T4 | High-risk flagged | Hypotheses with score > 0.7 blocked |

---

## Phase V: Autonomous Execution Eligibility

**Objective:** Define criteria for hypotheses to graduate to live trading

### V.1 Eligibility Criteria

```sql
CREATE OR REPLACE FUNCTION fhq_learning.check_execution_eligibility(
    p_hypothesis_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_hypothesis RECORD;
    v_perf RECORD;
    v_eligible BOOLEAN := TRUE;
    v_blockers TEXT[] := '{}';
BEGIN
    SELECT * INTO v_hypothesis FROM fhq_learning.hypothesis_canon WHERE canon_id = p_hypothesis_id;
    SELECT * INTO v_perf FROM fhq_learning.v_hypothesis_performance WHERE canon_id = p_hypothesis_id;

    -- Criterion 1: Status must be ACTIVE
    IF v_hypothesis.status != 'ACTIVE' THEN
        v_eligible := FALSE;
        v_blockers := array_append(v_blockers, 'status_not_active');
    END IF;

    -- Criterion 2: Minimum 10 experiments
    IF v_perf.total_experiments < 10 THEN
        v_eligible := FALSE;
        v_blockers := array_append(v_blockers, 'insufficient_experiments');
    END IF;

    -- Criterion 3: Hit rate >= 60%
    IF v_perf.hit_rate_pct < 60 THEN
        v_eligible := FALSE;
        v_blockers := array_append(v_blockers, 'hit_rate_below_threshold');
    END IF;

    -- Criterion 4: Current confidence >= 0.5
    IF v_hypothesis.current_confidence < 0.5 THEN
        v_eligible := FALSE;
        v_blockers := array_append(v_blockers, 'confidence_below_threshold');
    END IF;

    -- Criterion 5: Falsification count < max - 1 (safety margin)
    IF v_hypothesis.falsification_count >= v_hypothesis.max_falsifications - 1 THEN
        v_eligible := FALSE;
        v_blockers := array_append(v_blockers, 'near_falsification_limit');
    END IF;

    -- Criterion 6: ASRP compliance (fail-closed)
    IF v_hypothesis.pre_validation_passed = FALSE THEN
        v_eligible := FALSE;
        v_blockers := array_append(v_blockers, 'pre_validation_failed');
    END IF;

    RETURN jsonb_build_object(
        'hypothesis_id', p_hypothesis_id,
        'eligible', v_eligible,
        'blockers', v_blockers,
        'total_experiments', v_perf.total_experiments,
        'hit_rate_pct', v_perf.hit_rate_pct,
        'current_confidence', v_hypothesis.current_confidence,
        'checked_at', NOW()
    );
END;
$$ LANGUAGE plpgsql;
```

### V.2 Deliverables

| # | Deliverable | Owner | Schema/Table |
|---|-------------|-------|--------------|
| V.1.1 | `check_execution_eligibility()` function | STIG | `fhq_learning` |
| V.1.2 | `execution_eligibility_daemon.py` | STIG | Daemon |
| V.1.3 | `eligible_hypotheses` view | STIG | `fhq_learning` |
| V.1.4 | Integration with unified_execution_gateway | LINE | Daemon |
| V.1.5 | Migration 338: Execution Eligibility | STIG | Database |

### V.3 Acceptance Tests (Phase V)

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| V.T1 | Eligibility check runs | Function returns JSONB |
| V.T2 | Blockers identified | Blockers array populated |
| V.T3 | Eligible hypothesis found | >= 1 hypothesis passes all criteria |
| V.T4 | Integration with LINE | Eligible hypothesis triggers signal |

---

## Phase VI: Continuous Meta-Learning

**Objective:** System learns from its own learning process

### VI.1 Meta-Learning Metrics

```sql
CREATE TABLE fhq_learning.meta_learning_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    measurement_date DATE NOT NULL,

    -- Hypothesis Generation Quality
    total_hypotheses_generated INT,
    hypotheses_passed_pre_validation INT,
    pre_validation_pass_rate NUMERIC,

    -- Experiment Quality
    total_experiments INT,
    validated_experiments INT,
    weakened_experiments INT,
    falsified_experiments INT,
    overall_hit_rate NUMERIC,

    -- Error Learning Efficiency
    errors_detected INT,
    errors_with_hypothesis INT,
    error_to_hypothesis_rate NUMERIC,

    -- Execution Performance
    hypotheses_eligible INT,
    hypotheses_executed INT,
    execution_hit_rate NUMERIC,

    -- Learning Velocity
    lvi_score NUMERIC,
    coverage_rate NUMERIC,
    accuracy_rate NUMERIC,

    -- Confidence Calibration
    avg_predicted_confidence NUMERIC,
    avg_actual_hit_rate NUMERIC,
    calibration_error NUMERIC,  -- Brier-style

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_meta_learning_date ON fhq_learning.meta_learning_metrics(measurement_date);
```

### VI.2 Meta-Learning Daemon

```
PSEUDOCODE: meta_learning_daemon.py

DAILY at 00:00 UTC:
    1. Calculate all metrics for previous day
    2. Insert into meta_learning_metrics
    3. Compare against trailing 7-day average
    4. Identify degradation signals:
       - pre_validation_pass_rate declining
       - overall_hit_rate below 55%
       - calibration_error increasing
    5. Generate meta-learning proposals:
       - "Tighten pre-validation gate"
       - "Increase sample_size requirement"
       - "Adjust confidence_decay_rate"
    6. Log evidence file with recommendations
```

### VI.3 Deliverables

| # | Deliverable | Owner | Schema/Table |
|---|-------------|-------|--------------|
| VI.1.1 | `meta_learning_metrics` table | STIG | `fhq_learning` |
| VI.1.2 | `meta_learning_daemon.py` | STIG | Daemon |
| VI.1.3 | `v_meta_learning_trend` view | STIG | `fhq_learning` |
| VI.1.4 | Dashboard integration | STIG | Dashboard |
| VI.1.5 | Migration 339: Meta-Learning | STIG | Database |

### VI.4 Acceptance Tests (Phase VI)

| Test ID | Description | Pass Criteria |
|---------|-------------|---------------|
| VI.T1 | Metrics calculated | Daily row in meta_learning_metrics |
| VI.T2 | Trend view works | 7-day average calculated |
| VI.T3 | Degradation detected | Alerts triggered on decline |
| VI.T4 | Recommendations generated | >= 1 meta-learning proposal |

---

## Implementation Schedule

| Phase | Migrations | Estimated Complexity | Dependencies |
|-------|------------|---------------------|--------------|
| **I** | 334 | MEDIUM | None |
| **II** | 335 | HIGH | Phase I |
| **III** | 336 | MEDIUM | Phase II |
| **IV** | 337 | HIGH | Phase III |
| **V** | 338 | MEDIUM | Phase IV |
| **VI** | 339 | MEDIUM | Phase V |

**Execution Order:** Strictly sequential per CEO directive.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Multiple testing bias | Deflated Sharpe Ratio, pre-registration |
| Overfitting | Minimum 30 sample size, CPCV validation |
| Hallucination | IKEA firewall, ASRP fail-closed |
| Regime mismatch | Regime-conditional confidence |
| Data snooping | Immutability after pre-registration |

---

## CEO Decisions Required

1. **FINN Write Mandate:** Approve FINN write access to `hypothesis_canon`
2. **Phase Execution:** Approve sequential execution starting with Phase I
3. **Daemon Scheduling:** Confirm cron schedules for new daemons

---

**Signed:** STIG (EC-003)
**Timestamp:** 2026-01-23T22:15:00.000Z
**Plan Status:** AWAITING CEO APPROVAL
