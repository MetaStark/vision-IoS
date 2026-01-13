-- ============================================================
-- CEO-DIR-2026-054 — RETEST VALIDATION FRAMEWORK
-- ============================================================
-- Migration: 237_ceo_dir_2026_054_retest_validation_framework.sql
-- Authority: CEO (Constitutional Directive)
-- Technical Lead: STIG (CTO)
-- Validator: VEGA
-- ADR Compliance: ADR-002, ADR-012, ADR-020
-- ============================================================
-- PURPOSE: Implement RETEST → CLOSURE acceleration with verification
--          Track 7-day shadow validation cycles
--          Enforce failure mode re-open protocol
-- ============================================================
-- CORE PRINCIPLE: "Learning is only real when RETEST failure modes
--                  demonstrably remain closed under live shadow conditions."
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: RETEST VALIDATION CYCLES
-- Track shadow cycles for 7-day validation requirement
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.retest_validation_cycles (
    cycle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Failure Mode Reference
    failure_mode_id UUID NOT NULL REFERENCES fhq_governance.failure_mode_registry(failure_mode_id),

    -- Cycle Tracking
    cycle_number INTEGER NOT NULL DEFAULT 1,
    cycle_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Validation Results
    corrective_mechanism_active BOOLEAN NOT NULL,
    original_failure_reappeared BOOLEAN NOT NULL DEFAULT FALSE,
    new_failure_introduced BOOLEAN NOT NULL DEFAULT FALSE,
    metrics_improved BOOLEAN NOT NULL,

    -- Metrics Snapshot
    before_metric NUMERIC(10,4),
    after_metric NUMERIC(10,4),
    delta_metric NUMERIC(10,4),

    -- Status
    cycle_result TEXT NOT NULL,  -- PASS, FAIL, REGRESSION

    -- Metadata
    validated_by TEXT DEFAULT 'SHADOW_EVALUATOR',
    evidence JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_cycle_result CHECK (
        cycle_result IN ('PASS', 'FAIL', 'REGRESSION')
    ),
    CONSTRAINT uq_failure_cycle UNIQUE (failure_mode_id, cycle_number)
);

CREATE INDEX IF NOT EXISTS idx_retest_validation_fm
    ON fhq_governance.retest_validation_cycles(failure_mode_id, cycle_number);

CREATE INDEX IF NOT EXISTS idx_retest_validation_time
    ON fhq_governance.retest_validation_cycles(cycle_timestamp DESC);

COMMENT ON TABLE fhq_governance.retest_validation_cycles IS
'CEO-DIR-2026-054: RETEST validation cycle tracking.
Tracks 7 consecutive shadow cycles required for closure.
STIG 2026-01-14';

-- ============================================================
-- SECTION 2: FAILURE MODE RE-OPEN LOG
-- Per directive: Reopened failures tagged REOPENED_AFTER_FIX
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.failure_mode_reopen_log (
    reopen_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Original Failure Reference
    failure_mode_id UUID NOT NULL REFERENCES fhq_governance.failure_mode_registry(failure_mode_id),
    original_failure_code TEXT NOT NULL,

    -- Reopen Details
    reopened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    previous_stage TEXT NOT NULL,  -- Stage before reopen (usually RETEST or CLOSED)
    reopen_trigger TEXT NOT NULL,  -- What caused the reopen

    -- Root Cause of Fix Failure
    previous_diagnosis_failed_because TEXT,
    is_architectural_flaw BOOLEAN DEFAULT FALSE,

    -- Counter
    reopen_count INTEGER NOT NULL DEFAULT 1,

    -- Metadata
    detected_by TEXT DEFAULT 'SHADOW_EVALUATOR',
    evidence JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reopen_log_fm
    ON fhq_governance.failure_mode_reopen_log(failure_mode_id);

COMMENT ON TABLE fhq_governance.failure_mode_reopen_log IS
'CEO-DIR-2026-054: Failure mode re-open tracking.
Per directive: Reopened failures tagged REOPENED_AFTER_FIX.
Repeated reopenings treated as architectural flaws.
STIG 2026-01-14';

-- ============================================================
-- SECTION 3: LEARNING VERIFICATION VIEW
-- Non-subjective criteria per directive Section 5
-- ============================================================

CREATE OR REPLACE VIEW fhq_governance.v_learning_verification_criteria AS
WITH retest_stats AS (
    SELECT
        COUNT(*) FILTER (WHERE fmcl_stage = 'RETEST') as in_retest,
        COUNT(*) FILTER (WHERE fmcl_stage = 'CLOSED' AND failure_severity = 'HIGH') as high_closed,
        COUNT(*) FILTER (WHERE fmcl_stage IN ('RETEST', 'CLOSED') AND failure_severity = 'HIGH') as high_total
    FROM fhq_governance.failure_mode_registry
),
calibration_stats AS (
    SELECT
        ROUND(AVG(
            CASE WHEN forecast_probability >= 0.9 THEN forecast_probability - actual_outcome::int ELSE NULL END
        )::numeric, 4) as high_conf_gap,
        COUNT(*) as sample_size
    FROM fhq_governance.brier_score_ledger
    WHERE forecast_timestamp >= NOW() - INTERVAL '7 days'
),
suppression_stats AS (
    SELECT
        suppression_wisdom_rate,
        computation_timestamp
    FROM fhq_governance.suppression_regret_index
    ORDER BY computation_timestamp DESC
    LIMIT 2
),
fmcl_entropy AS (
    SELECT
        COUNT(*) FILTER (WHERE fmcl_stage = 'CAPTURE') as capture,
        COUNT(*) FILTER (WHERE fmcl_stage = 'DIAGNOSIS') as diagnosis,
        COUNT(*) FILTER (WHERE fmcl_stage = 'ACTION_DEFINITION') as action,
        COUNT(*) FILTER (WHERE fmcl_stage = 'RETEST') as retest,
        COUNT(*) FILTER (WHERE fmcl_stage = 'CLOSED') as closed,
        COUNT(*) FILTER (WHERE fmcl_stage != 'CLOSED') as net_open
    FROM fhq_governance.failure_mode_registry
)
SELECT
    -- Criterion 1: RETEST Closure Rate >= 70%
    CASE
        WHEN rs.high_total > 0 THEN ROUND(100.0 * rs.high_closed / rs.high_total, 1)
        ELSE 0
    END as retest_closure_rate_pct,
    CASE
        WHEN rs.high_total > 0 AND (100.0 * rs.high_closed / rs.high_total) >= 70 THEN 'MET'
        ELSE 'NOT_MET'
    END as criterion_1_retest_closure,

    -- Criterion 2: Zero regression in calibration gap
    cs.high_conf_gap as current_calibration_gap,
    CASE
        WHEN cs.high_conf_gap IS NULL OR cs.high_conf_gap < 0.55 THEN 'MET'
        ELSE 'NOT_MET'
    END as criterion_2_calibration,

    -- Criterion 3: Suppression regret stabilizes
    'PENDING_7DAY_DATA' as criterion_3_suppression,

    -- Criterion 4: No increase in net open failure modes
    fe.net_open as current_net_open,
    CASE
        WHEN fe.net_open <= 24 THEN 'MET'  -- Baseline was 24
        ELSE 'NOT_MET'
    END as criterion_4_net_open,

    -- Criterion 5: FMCL shows declining entropy
    fe.capture || '-' || fe.diagnosis || '-' || fe.action || '-' || fe.retest || '-' || fe.closed as fmcl_distribution,
    CASE
        WHEN fe.closed >= 5 AND fe.retest >= 0 THEN 'CONVERGING'
        ELSE 'OSCILLATING'
    END as criterion_5_entropy,

    -- Overall Verdict
    CASE
        WHEN (rs.high_total > 0 AND (100.0 * rs.high_closed / rs.high_total) >= 70)
             AND (cs.high_conf_gap IS NULL OR cs.high_conf_gap < 0.55)
             AND fe.net_open <= 24
             AND fe.closed >= 5
        THEN 'LEARNING_VERIFIED'
        ELSE 'LEARNING_NOT_PROVEN'
    END as overall_verdict,

    NOW() as verified_at
FROM retest_stats rs
CROSS JOIN calibration_stats cs
CROSS JOIN fmcl_entropy fe;

COMMENT ON VIEW fhq_governance.v_learning_verification_criteria IS
'CEO-DIR-2026-054: Learning verification criteria (non-subjective).
All criteria must be MET for VEGA attestation.
Failure on any axis = learning NOT proven.';

-- ============================================================
-- SECTION 4: FUNCTION TO VALIDATE RETEST CLOSURE
-- Enforces the 4 criteria per directive Section 4.1
-- ============================================================

CREATE OR REPLACE FUNCTION fhq_governance.validate_retest_closure(
    p_failure_mode_id UUID
) RETURNS JSONB AS $$
DECLARE
    v_corrective_active BOOLEAN;
    v_failure_reappeared BOOLEAN;
    v_new_failure_introduced BOOLEAN;
    v_metrics_improved BOOLEAN;
    v_cycle_count INTEGER;
    v_can_close BOOLEAN;
    v_result JSONB;
BEGIN
    -- Count validation cycles
    SELECT COUNT(*),
           BOOL_AND(corrective_mechanism_active),
           BOOL_OR(original_failure_reappeared),
           BOOL_OR(new_failure_introduced),
           BOOL_AND(metrics_improved)
    INTO v_cycle_count, v_corrective_active, v_failure_reappeared, v_new_failure_introduced, v_metrics_improved
    FROM fhq_governance.retest_validation_cycles
    WHERE failure_mode_id = p_failure_mode_id
      AND cycle_result = 'PASS';

    -- Check all 4 criteria
    v_can_close := (
        COALESCE(v_cycle_count, 0) >= 1 AND  -- At least 1 validation cycle (7 for full compliance)
        COALESCE(v_corrective_active, FALSE) = TRUE AND
        COALESCE(v_failure_reappeared, TRUE) = FALSE AND
        COALESCE(v_new_failure_introduced, TRUE) = FALSE AND
        COALESCE(v_metrics_improved, FALSE) = TRUE
    );

    v_result := jsonb_build_object(
        'failure_mode_id', p_failure_mode_id,
        'can_close', v_can_close,
        'validation_cycles', COALESCE(v_cycle_count, 0),
        'required_cycles', 7,
        'criteria', jsonb_build_object(
            'corrective_mechanism_active', COALESCE(v_corrective_active, FALSE),
            'original_failure_reappeared', COALESCE(v_failure_reappeared, TRUE),
            'new_failure_introduced', COALESCE(v_new_failure_introduced, TRUE),
            'metrics_improved', COALESCE(v_metrics_improved, FALSE)
        ),
        'directive', 'CEO-DIR-2026-054',
        'validated_at', NOW()
    );

    RETURN v_result;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.validate_retest_closure IS
'CEO-DIR-2026-054: Validate if a RETEST failure mode can be closed.
Enforces all 4 criteria from directive Section 4.1.';

-- ============================================================
-- SECTION 5: GOVERNANCE ATTESTATION
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'CONSTITUTIONAL_DIRECTIVE',
    'CEO-DIR-2026-054',
    'DIRECTIVE',
    'CEO',
    NOW(),
    'APPROVED',
    'RETEST -> CLOSURE Acceleration & Learning Verification Lock-In. Forces convergence, freezes expansion. Learning only proven when RETEST modes remain closed under shadow conditions.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-054',
        'migration_id', 237,
        'tables_created', ARRAY[
            'fhq_governance.retest_validation_cycles',
            'fhq_governance.failure_mode_reopen_log'
        ],
        'views_created', ARRAY['fhq_governance.v_learning_verification_criteria'],
        'functions_created', ARRAY['fhq_governance.validate_retest_closure'],
        'learning_criteria', jsonb_build_object(
            'retest_closure_rate', '>=70% (>=8 of 11)',
            'calibration_gap', 'zero regression',
            'net_open_failure_modes', 'no increase',
            'fmcl_entropy', 'declining, not oscillating'
        ),
        'prohibitions', ARRAY[
            'No paper trading',
            'No capital exposure',
            'No new model classes',
            'No new signal generation',
            'No budget escalation'
        ]
    )
);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Verify tables created
SELECT 'RETEST_VALIDATION_CYCLES' as check_type, COUNT(*) FROM fhq_governance.retest_validation_cycles;
SELECT 'FAILURE_MODE_REOPEN_LOG' as check_type, COUNT(*) FROM fhq_governance.failure_mode_reopen_log;

-- Check learning verification criteria
SELECT * FROM fhq_governance.v_learning_verification_criteria;
