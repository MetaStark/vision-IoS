-- ============================================================
-- CEO-DIR-2026-052 — FAILURE MODE CLOSURE PROTOCOL (FMCP)
-- ============================================================
-- Migration: 236_ceo_dir_2026_052_failure_mode_closure_protocol.sql
-- Authority: CEO (Constitutional Directive)
-- Technical Lead: STIG (CTO)
-- Governance: VEGA
-- ADR Compliance: ADR-002, ADR-012, ADR-020, ADR-021
-- ============================================================
-- PURPOSE: Convert failure detection into verified cognitive improvement
--          Implement 5-stage Failure Mode Closure Lifecycle (FMCL)
--          Enforce closure targets: ≥5 closures/day, ≥20% ratio
-- ============================================================
-- CORE PRINCIPLE: "Identifying a failure mode without closing it
--                  is not learning — it is accumulating debt."
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: FAILURE MODE REGISTRY
-- Central registry with 5-stage FMCL lifecycle
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.failure_mode_registry (
    failure_mode_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity & Classification
    failure_code TEXT NOT NULL,  -- e.g., FM-2026-001
    failure_category TEXT NOT NULL,  -- CALIBRATION_ERROR, REGIME_MISCLASSIFICATION, SUPPRESSION_REGRET, etc.
    failure_severity TEXT NOT NULL,  -- CRITICAL, HIGH, MEDIUM, LOW
    failure_title TEXT NOT NULL,
    failure_description TEXT,

    -- Source Linking
    source_lesson_id UUID,  -- Link to epistemic_lessons if migrated
    source_signal_id UUID,  -- Link to triggering signal
    source_asset TEXT,  -- Asset involved (if any)
    source_date DATE,  -- Date failure was observed

    -- FMCL Lifecycle Stage (5 stages)
    fmcl_stage TEXT NOT NULL DEFAULT 'CAPTURE',
    fmcl_stage_entered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Stage 1: CAPTURE
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    captured_by TEXT NOT NULL DEFAULT 'SYSTEM',
    capture_evidence JSONB NOT NULL DEFAULT '{}',

    -- Stage 2: DIAGNOSIS
    diagnosis_started_at TIMESTAMPTZ,
    diagnosis_completed_at TIMESTAMPTZ,
    diagnosis_agent TEXT,  -- Which agent performed diagnosis
    diagnosis_model TEXT,  -- LLM used (Claude 3.5 Sonnet / OpenAI o1)
    diagnosis_result JSONB,  -- Root cause analysis
    diagnosis_cost_usd NUMERIC(10,4),

    -- Stage 3: ACTION DEFINITION
    action_defined_at TIMESTAMPTZ,
    action_type TEXT,  -- CODE_FIX, THRESHOLD_ADJUSTMENT, RULE_UPDATE, ARCHITECTURE_CHANGE
    action_description TEXT,
    action_owner TEXT,  -- Agent responsible for implementation
    action_evidence JSONB,

    -- Stage 4: RE-TEST
    retest_started_at TIMESTAMPTZ,
    retest_completed_at TIMESTAMPTZ,
    retest_result TEXT,  -- PASS, FAIL, PARTIAL
    retest_evidence JSONB,
    retest_iterations INTEGER DEFAULT 0,

    -- Stage 5: CLOSURE
    closed_at TIMESTAMPTZ,
    closure_type TEXT,  -- RESOLVED, MITIGATED, ACCEPTED_RISK, OBSOLETE
    closure_evidence JSONB,
    closure_attestation_by TEXT,

    -- Metrics
    time_in_capture_hours NUMERIC(10,2),
    time_in_diagnosis_hours NUMERIC(10,2),
    time_in_action_hours NUMERIC(10,2),
    time_in_retest_hours NUMERIC(10,2),
    total_resolution_hours NUMERIC(10,2),

    -- Learning Link
    invariant_created BOOLEAN DEFAULT FALSE,
    invariant_id UUID,  -- Link to new invariant if created

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive TEXT DEFAULT 'CEO-DIR-2026-052',

    -- Constraints
    CONSTRAINT chk_fmcl_stage CHECK (
        fmcl_stage IN ('CAPTURE', 'DIAGNOSIS', 'ACTION_DEFINITION', 'RETEST', 'CLOSED')
    ),
    CONSTRAINT chk_failure_severity CHECK (
        failure_severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
    ),
    CONSTRAINT chk_closure_type CHECK (
        closure_type IS NULL OR closure_type IN ('RESOLVED', 'MITIGATED', 'ACCEPTED_RISK', 'OBSOLETE')
    ),
    CONSTRAINT chk_retest_result CHECK (
        retest_result IS NULL OR retest_result IN ('PASS', 'FAIL', 'PARTIAL')
    )
);

-- Indexes for FMCL queries
CREATE INDEX IF NOT EXISTS idx_fm_registry_stage
    ON fhq_governance.failure_mode_registry(fmcl_stage, failure_severity);

CREATE INDEX IF NOT EXISTS idx_fm_registry_category
    ON fhq_governance.failure_mode_registry(failure_category, fmcl_stage);

CREATE INDEX IF NOT EXISTS idx_fm_registry_source_date
    ON fhq_governance.failure_mode_registry(source_date DESC);

CREATE INDEX IF NOT EXISTS idx_fm_registry_created
    ON fhq_governance.failure_mode_registry(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fm_registry_closed
    ON fhq_governance.failure_mode_registry(closed_at DESC)
    WHERE fmcl_stage = 'CLOSED';

COMMENT ON TABLE fhq_governance.failure_mode_registry IS
'CEO-DIR-2026-052: Failure Mode Registry with 5-stage FMCL lifecycle.
Stages: CAPTURE → DIAGNOSIS → ACTION_DEFINITION → RETEST → CLOSED.
Target: ≥5 closures/day, ≥20% closure ratio, net open must decrease.
STIG 2026-01-14';

-- ============================================================
-- SECTION 2: GOLDEN SCENARIO REGISTRY
-- Canonical stress events for judgment quality validation
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.golden_scenario_registry (
    scenario_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scenario Identity
    scenario_code TEXT NOT NULL UNIQUE,  -- e.g., GS-001
    scenario_name TEXT NOT NULL,
    scenario_type TEXT NOT NULL,  -- STRESS, REGIME_SHIFT, LIQUIDITY_CRISIS, VOLATILITY_SPIKE

    -- Event Details
    event_date DATE NOT NULL,
    event_asset TEXT NOT NULL,
    event_description TEXT,

    -- Expected Behavior
    expected_regime TEXT,  -- What regime should have been detected
    expected_action TEXT,  -- What action should have been taken
    expected_confidence_min NUMERIC(8,4),

    -- Actual Outcome (historical)
    actual_regime TEXT,
    actual_action TEXT,
    actual_confidence NUMERIC(8,4),
    actual_outcome TEXT,  -- CORRECT, INCORRECT, PARTIAL

    -- Stress Metrics
    stress_probability NUMERIC(10,6),
    volatility_zscore NUMERIC(10,4),
    drawdown_pct NUMERIC(10,4),

    -- Validation
    last_validation_at TIMESTAMPTZ,
    validation_result TEXT,  -- PASS, FAIL, DEGRADED
    validation_evidence JSONB,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'FINN',
    canonical BOOLEAN DEFAULT TRUE,
    directive TEXT DEFAULT 'CEO-DIR-2026-052',

    CONSTRAINT chk_scenario_type CHECK (
        scenario_type IN ('STRESS', 'REGIME_SHIFT', 'LIQUIDITY_CRISIS', 'VOLATILITY_SPIKE', 'FLASH_CRASH', 'CORRELATION_BREAKDOWN')
    ),
    CONSTRAINT chk_validation_result CHECK (
        validation_result IS NULL OR validation_result IN ('PASS', 'FAIL', 'DEGRADED')
    )
);

COMMENT ON TABLE fhq_governance.golden_scenario_registry IS
'CEO-DIR-2026-052: Golden Scenario Registry for judgment quality validation.
Canonical stress events that the system must handle correctly.
Target: ≥3 scenarios defined, weekly validation.
STIG 2026-01-14';

-- ============================================================
-- SECTION 3: MARKET-AWARE TEMPORAL WINDOWS
-- Replace hard-coded staleness thresholds with context-aware logic
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.market_temporal_windows (
    window_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Window Definition
    asset_class TEXT NOT NULL,  -- crypto, equity_us, equity_intl, fx, commodity
    market_condition TEXT NOT NULL,  -- NORMAL, WEEKEND, HOLIDAY, EXTENDED_HOURS, CLOSED

    -- Staleness Thresholds (hours)
    freshness_threshold_hours NUMERIC(10,2) NOT NULL,
    freshness_warning_hours NUMERIC(10,2),
    freshness_critical_hours NUMERIC(10,2),

    -- Time Windows
    applies_from TIME,  -- e.g., 09:30 for market open
    applies_to TIME,  -- e.g., 16:00 for market close
    timezone TEXT DEFAULT 'America/New_York',

    -- Day-of-Week Rules
    applies_on_days INTEGER[],  -- 0=Sunday, 1=Monday, ..., 6=Saturday

    -- Holiday Handling
    holiday_multiplier NUMERIC(4,2) DEFAULT 1.0,  -- e.g., 3.0 for 3-day weekend

    -- Validation
    enabled BOOLEAN DEFAULT TRUE,
    effective_from DATE DEFAULT CURRENT_DATE,
    effective_to DATE,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT DEFAULT 'CDMO',
    directive TEXT DEFAULT 'CEO-DIR-2026-052',

    CONSTRAINT chk_asset_class CHECK (
        asset_class IN ('crypto', 'equity_us', 'equity_intl', 'fx', 'commodity', 'all')
    ),
    CONSTRAINT chk_market_condition CHECK (
        market_condition IN ('NORMAL', 'WEEKEND', 'HOLIDAY', 'EXTENDED_HOURS', 'CLOSED', 'ALL')
    )
);

-- Insert default temporal windows
INSERT INTO fhq_governance.market_temporal_windows
    (asset_class, market_condition, freshness_threshold_hours, freshness_warning_hours, freshness_critical_hours, applies_on_days)
VALUES
    -- Crypto: 24/7, tight staleness
    ('crypto', 'ALL', 12.0, 8.0, 24.0, ARRAY[0,1,2,3,4,5,6]),

    -- US Equity: Normal trading hours
    ('equity_us', 'NORMAL', 12.0, 8.0, 24.0, ARRAY[1,2,3,4,5]),

    -- US Equity: Weekend (relax threshold)
    ('equity_us', 'WEEKEND', 72.0, 48.0, 96.0, ARRAY[0,6]),

    -- US Equity: Holiday (relax threshold)
    ('equity_us', 'HOLIDAY', 96.0, 72.0, 120.0, ARRAY[0,1,2,3,4,5,6]),

    -- FX: 24/5, weekend relaxation
    ('fx', 'NORMAL', 12.0, 8.0, 24.0, ARRAY[1,2,3,4,5]),
    ('fx', 'WEEKEND', 60.0, 48.0, 72.0, ARRAY[0,6])
ON CONFLICT DO NOTHING;

COMMENT ON TABLE fhq_governance.market_temporal_windows IS
'CEO-DIR-2026-052: Market-aware temporal windows for contextual staleness.
Replaces hard-coded 118.8h threshold with context-aware logic.
CDMO mandate: weekend equity data is NOT stale, just closed.
STIG 2026-01-14';

-- ============================================================
-- SECTION 4: FMCL LIFECYCLE FUNCTIONS
-- ============================================================

-- Function to advance failure mode through lifecycle stages
CREATE OR REPLACE FUNCTION fhq_governance.advance_fmcl_stage(
    p_failure_mode_id UUID,
    p_new_stage TEXT,
    p_evidence JSONB DEFAULT '{}'
) RETURNS JSONB AS $$
DECLARE
    v_current_stage TEXT;
    v_current_entered TIMESTAMPTZ;
    v_hours_in_stage NUMERIC;
    v_result JSONB;
BEGIN
    -- Get current stage
    SELECT fmcl_stage, fmcl_stage_entered_at
    INTO v_current_stage, v_current_entered
    FROM fhq_governance.failure_mode_registry
    WHERE failure_mode_id = p_failure_mode_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error', 'Failure mode not found');
    END IF;

    -- Calculate time in current stage
    v_hours_in_stage := EXTRACT(EPOCH FROM (NOW() - v_current_entered)) / 3600;

    -- Validate stage transition (must be sequential)
    IF NOT (
        (v_current_stage = 'CAPTURE' AND p_new_stage = 'DIAGNOSIS') OR
        (v_current_stage = 'DIAGNOSIS' AND p_new_stage = 'ACTION_DEFINITION') OR
        (v_current_stage = 'ACTION_DEFINITION' AND p_new_stage = 'RETEST') OR
        (v_current_stage = 'RETEST' AND p_new_stage = 'CLOSED') OR
        (v_current_stage = 'RETEST' AND p_new_stage = 'ACTION_DEFINITION')  -- Allow regression for failed retest
    ) THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', format('Invalid transition: %s → %s', v_current_stage, p_new_stage)
        );
    END IF;

    -- Update stage and timing
    UPDATE fhq_governance.failure_mode_registry
    SET
        fmcl_stage = p_new_stage,
        fmcl_stage_entered_at = NOW(),
        updated_at = NOW(),
        -- Update stage-specific timestamps
        diagnosis_started_at = CASE WHEN p_new_stage = 'DIAGNOSIS' THEN NOW() ELSE diagnosis_started_at END,
        diagnosis_completed_at = CASE WHEN v_current_stage = 'DIAGNOSIS' AND p_new_stage = 'ACTION_DEFINITION' THEN NOW() ELSE diagnosis_completed_at END,
        action_defined_at = CASE WHEN p_new_stage = 'ACTION_DEFINITION' THEN NOW() ELSE action_defined_at END,
        retest_started_at = CASE WHEN p_new_stage = 'RETEST' THEN NOW() ELSE retest_started_at END,
        retest_completed_at = CASE WHEN v_current_stage = 'RETEST' AND p_new_stage = 'CLOSED' THEN NOW() ELSE retest_completed_at END,
        closed_at = CASE WHEN p_new_stage = 'CLOSED' THEN NOW() ELSE closed_at END,
        -- Update time tracking
        time_in_capture_hours = CASE WHEN v_current_stage = 'CAPTURE' THEN v_hours_in_stage ELSE time_in_capture_hours END,
        time_in_diagnosis_hours = CASE WHEN v_current_stage = 'DIAGNOSIS' THEN v_hours_in_stage ELSE time_in_diagnosis_hours END,
        time_in_action_hours = CASE WHEN v_current_stage = 'ACTION_DEFINITION' THEN v_hours_in_stage ELSE time_in_action_hours END,
        time_in_retest_hours = CASE WHEN v_current_stage = 'RETEST' THEN v_hours_in_stage ELSE time_in_retest_hours END,
        -- Update evidence
        diagnosis_result = CASE WHEN p_new_stage = 'ACTION_DEFINITION' THEN COALESCE(p_evidence, diagnosis_result) ELSE diagnosis_result END,
        action_evidence = CASE WHEN p_new_stage = 'RETEST' THEN COALESCE(p_evidence, action_evidence) ELSE action_evidence END,
        retest_evidence = CASE WHEN p_new_stage = 'CLOSED' OR (v_current_stage = 'RETEST' AND p_new_stage = 'ACTION_DEFINITION') THEN COALESCE(p_evidence, retest_evidence) ELSE retest_evidence END,
        closure_evidence = CASE WHEN p_new_stage = 'CLOSED' THEN p_evidence ELSE closure_evidence END
    WHERE failure_mode_id = p_failure_mode_id;

    -- Calculate total resolution time if closed
    IF p_new_stage = 'CLOSED' THEN
        UPDATE fhq_governance.failure_mode_registry
        SET total_resolution_hours = COALESCE(time_in_capture_hours, 0) +
                                     COALESCE(time_in_diagnosis_hours, 0) +
                                     COALESCE(time_in_action_hours, 0) +
                                     COALESCE(time_in_retest_hours, 0)
        WHERE failure_mode_id = p_failure_mode_id;
    END IF;

    RETURN jsonb_build_object(
        'success', true,
        'failure_mode_id', p_failure_mode_id,
        'previous_stage', v_current_stage,
        'new_stage', p_new_stage,
        'hours_in_previous_stage', ROUND(v_hours_in_stage, 2)
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.advance_fmcl_stage IS
'CEO-DIR-2026-052: Advance failure mode through FMCL lifecycle.
Validates sequential transitions and tracks timing metrics.';

-- ============================================================
-- SECTION 5: CLOSURE METRICS VIEW
-- Daily tracking of closure rate and targets
-- ============================================================

CREATE OR REPLACE VIEW fhq_governance.v_fmcl_daily_metrics AS
WITH daily_stats AS (
    SELECT
        DATE(created_at) AS report_date,
        COUNT(*) FILTER (WHERE fmcl_stage = 'CAPTURE') AS captured_today,
        COUNT(*) FILTER (WHERE DATE(closed_at) = DATE(created_at)) AS closed_same_day,
        COUNT(*) FILTER (WHERE fmcl_stage = 'CLOSED') AS total_closed,
        COUNT(*) FILTER (WHERE fmcl_stage != 'CLOSED') AS total_open,
        COUNT(*) AS total_all
    FROM fhq_governance.failure_mode_registry
    GROUP BY DATE(created_at)
),
closure_by_day AS (
    SELECT
        DATE(closed_at) AS closure_date,
        COUNT(*) AS closures_on_day
    FROM fhq_governance.failure_mode_registry
    WHERE closed_at IS NOT NULL
    GROUP BY DATE(closed_at)
),
running_totals AS (
    SELECT
        CURRENT_DATE AS report_date,
        COUNT(*) FILTER (WHERE fmcl_stage = 'CAPTURE') AS in_capture,
        COUNT(*) FILTER (WHERE fmcl_stage = 'DIAGNOSIS') AS in_diagnosis,
        COUNT(*) FILTER (WHERE fmcl_stage = 'ACTION_DEFINITION') AS in_action,
        COUNT(*) FILTER (WHERE fmcl_stage = 'RETEST') AS in_retest,
        COUNT(*) FILTER (WHERE fmcl_stage = 'CLOSED') AS closed,
        COUNT(*) FILTER (WHERE fmcl_stage != 'CLOSED') AS total_open,
        COUNT(*) AS total_all
    FROM fhq_governance.failure_mode_registry
)
SELECT
    r.report_date,
    r.in_capture,
    r.in_diagnosis,
    r.in_action,
    r.in_retest,
    r.closed,
    r.total_open,
    r.total_all,
    COALESCE(c.closures_on_day, 0) AS closures_today,
    ROUND(100.0 * r.closed / NULLIF(r.total_all, 0), 1) AS closure_ratio_pct,
    -- Target checks
    CASE WHEN COALESCE(c.closures_on_day, 0) >= 5 THEN 'MET' ELSE 'NOT_MET' END AS daily_closure_target,
    CASE WHEN (100.0 * r.closed / NULLIF(r.total_all, 0)) >= 20 THEN 'MET' ELSE 'NOT_MET' END AS ratio_target
FROM running_totals r
LEFT JOIN closure_by_day c ON c.closure_date = CURRENT_DATE;

COMMENT ON VIEW fhq_governance.v_fmcl_daily_metrics IS
'CEO-DIR-2026-052: Daily FMCL metrics with target tracking.
Targets: ≥5 closures/day, ≥20% closure ratio.';

-- ============================================================
-- SECTION 6: STAGE DISTRIBUTION VIEW
-- Current state of all failure modes by stage and severity
-- ============================================================

CREATE OR REPLACE VIEW fhq_governance.v_fmcl_stage_distribution AS
SELECT
    fmcl_stage,
    failure_severity,
    failure_category,
    COUNT(*) AS count,
    ROUND(AVG(EXTRACT(EPOCH FROM (NOW() - fmcl_stage_entered_at)) / 3600), 1) AS avg_hours_in_stage,
    MIN(fmcl_stage_entered_at) AS oldest_entry,
    MAX(fmcl_stage_entered_at) AS newest_entry
FROM fhq_governance.failure_mode_registry
WHERE fmcl_stage != 'CLOSED'
GROUP BY fmcl_stage, failure_severity, failure_category
ORDER BY
    CASE fmcl_stage
        WHEN 'CAPTURE' THEN 1
        WHEN 'DIAGNOSIS' THEN 2
        WHEN 'ACTION_DEFINITION' THEN 3
        WHEN 'RETEST' THEN 4
    END,
    CASE failure_severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;

COMMENT ON VIEW fhq_governance.v_fmcl_stage_distribution IS
'CEO-DIR-2026-052: Current distribution of open failure modes by stage and severity.';

-- ============================================================
-- SECTION 7: MIGRATE EXISTING EPISTEMIC LESSONS
-- ============================================================

-- Insert existing epistemic lessons into failure_mode_registry
INSERT INTO fhq_governance.failure_mode_registry (
    failure_code,
    failure_category,
    failure_severity,
    failure_title,
    failure_description,
    source_lesson_id,
    source_asset,
    source_date,
    fmcl_stage,
    captured_at,
    captured_by,
    capture_evidence
)
SELECT
    'FM-MIG-' || ROW_NUMBER() OVER (ORDER BY created_at) AS failure_code,
    lesson_category AS failure_category,
    COALESCE(lesson_severity, 'MEDIUM') AS failure_severity,
    COALESCE(LEFT(lesson_description, 100), 'Migrated from epistemic_lessons') AS failure_title,
    lesson_description AS failure_description,
    lesson_id AS source_lesson_id,
    affected_asset_id AS source_asset,
    DATE(lesson_timestamp) AS source_date,
    'CAPTURE' AS fmcl_stage,
    created_at AS captured_at,
    COALESCE(created_by, 'FINN') AS captured_by,
    jsonb_build_object(
        'migrated_from', 'epistemic_lessons',
        'original_lesson_id', lesson_id,
        'migration_date', NOW(),
        'directive', 'CEO-DIR-2026-052'
    ) AS capture_evidence
FROM fhq_governance.epistemic_lessons
WHERE action_taken IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM fhq_governance.failure_mode_registry fm
      WHERE fm.source_lesson_id = epistemic_lessons.lesson_id
  );

-- ============================================================
-- SECTION 8: INSERT GOLDEN SCENARIOS FROM AVAILABLE DATA
-- ============================================================

-- Insert golden scenarios from identified stress events
INSERT INTO fhq_governance.golden_scenario_registry (
    scenario_code,
    scenario_name,
    scenario_type,
    event_date,
    event_asset,
    event_description,
    expected_regime,
    stress_probability,
    created_by
) VALUES
    ('GS-001', 'AIG High Stress 2026-01-11', 'STRESS', '2026-01-11', 'AIG',
     'AIG exhibited stress probability 0.9997 - canonical stress detection scenario',
     'STRESS', 0.9997, 'FINN'),
    ('GS-002', 'GIS High Stress 2026-01-11', 'STRESS', '2026-01-11', 'GIS',
     'GIS exhibited stress probability 0.9998 - canonical stress detection scenario',
     'STRESS', 0.9998, 'FINN'),
    ('GS-003', 'NOW High Stress 2026-01-11', 'STRESS', '2026-01-11', 'NOW',
     'NOW exhibited stress probability 0.9988 - canonical stress detection scenario',
     'STRESS', 0.9988, 'FINN'),
    ('GS-004', 'FLOW-USD Crypto Stress 2026-01-10', 'STRESS', '2026-01-10', 'FLOW-USD',
     'FLOW-USD crypto exhibited stress probability 0.9907 - cross-asset stress scenario',
     'STRESS', 0.9907, 'FINN')
ON CONFLICT (scenario_code) DO UPDATE SET
    stress_probability = EXCLUDED.stress_probability,
    event_description = EXCLUDED.event_description;

-- ============================================================
-- SECTION 9: GOVERNANCE ATTESTATION
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
    'CEO-DIR-2026-052',
    'DIRECTIVE',
    'CEO',
    NOW(),
    'APPROVED',
    'Failure Mode Closure Protocol: Convert failure detection into verified cognitive improvement. 5-stage FMCL lifecycle. Targets: ≥5 closures/day, ≥20% closure ratio.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-052',
        'migration_id', 236,
        'tables_created', ARRAY[
            'fhq_governance.failure_mode_registry',
            'fhq_governance.golden_scenario_registry',
            'fhq_governance.market_temporal_windows'
        ],
        'views_created', ARRAY[
            'fhq_governance.v_fmcl_daily_metrics',
            'fhq_governance.v_fmcl_stage_distribution'
        ],
        'functions_created', ARRAY[
            'fhq_governance.advance_fmcl_stage'
        ],
        'adr_compliance', ARRAY['ADR-002', 'ADR-012', 'ADR-020', 'ADR-021'],
        'closure_targets', jsonb_build_object(
            'daily_closures', 5,
            'closure_ratio_pct', 20
        )
    )
);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Verify failure_mode_registry created and populated
SELECT
    'FAILURE_MODE_REGISTRY' AS check_type,
    COUNT(*) AS total_count,
    COUNT(*) FILTER (WHERE fmcl_stage = 'CAPTURE') AS in_capture,
    COUNT(*) FILTER (WHERE fmcl_stage = 'CLOSED') AS closed
FROM fhq_governance.failure_mode_registry;

-- Verify golden scenarios created
SELECT
    'GOLDEN_SCENARIOS' AS check_type,
    COUNT(*) AS scenario_count
FROM fhq_governance.golden_scenario_registry;

-- Verify temporal windows created
SELECT
    'TEMPORAL_WINDOWS' AS check_type,
    asset_class,
    market_condition,
    freshness_threshold_hours
FROM fhq_governance.market_temporal_windows
ORDER BY asset_class, market_condition;

-- Show FMCL metrics
SELECT * FROM fhq_governance.v_fmcl_daily_metrics;
