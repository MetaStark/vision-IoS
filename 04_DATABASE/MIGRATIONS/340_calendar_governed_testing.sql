-- ============================================================================
-- MIGRATION 340: Calendar-Governed Testing Framework
-- CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
-- ============================================================================
-- Classification: GOVERNANCE-CRITICAL / EXECUTION-BOUND
-- Governing ADRs: ADR-004, ADR-010, ADR-013, ADR-018 (ASRP), ADR-014
-- Executor: STIG (EC-003)
-- Date: 2026-01-24
-- ============================================================================

-- Executive Intent: Calendar-as-Law Doctrine
-- If something matters, it exists as a canonical calendar event.
-- If it exists as a calendar event, it must execute automatically.

BEGIN;

-- ============================================================================
-- SECTION 3: CANONICAL TEST EVENT SCHEMA
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.canonical_test_events (
    test_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Human-readable identification (IDs never dominate CEO surfaces)
    test_name TEXT NOT NULL,
    test_code TEXT UNIQUE NOT NULL,  -- Internal reference

    -- Ownership (explicit responsibility)
    owning_agent TEXT NOT NULL,  -- EC-xxx format
    monitoring_agent TEXT,  -- Agent that evaluates continuously

    -- Hypothesis linkage
    hypothesis_id UUID REFERENCES fhq_learning.hypothesis_canon(canon_id),
    hypothesis_code TEXT,  -- Denormalized for readability

    -- Business Intent (Section 3 - Required Fields)
    business_intent TEXT NOT NULL,  -- Why are we doing this
    beneficiary_system TEXT NOT NULL,  -- Which agent/system benefits if successful

    -- Baseline & Targets
    baseline_definition JSONB NOT NULL,  -- What "normal" means
    target_metrics JSONB NOT NULL,  -- Expected values
    expected_trajectory JSONB,  -- Day-by-day expected path

    -- Sample Size Governance (Section 4)
    minimum_sample_size INTEGER,
    target_sample_size INTEGER NOT NULL,
    current_sample_size INTEGER DEFAULT 0,
    sample_trajectory_status TEXT DEFAULT 'ON_TRACK',  -- ON_TRACK, BEHIND, AHEAD

    -- Timing
    start_date DATE NOT NULL,
    end_date DATE,
    duration_days INTEGER,
    days_elapsed INTEGER DEFAULT 0,
    days_remaining INTEGER,

    -- Review Checkpoints (Section 3)
    mid_test_checkpoint DATE,
    mid_test_reviewed BOOLEAN DEFAULT FALSE,
    end_test_checkpoint DATE,

    -- Success/Failure Criteria (Immutable once test starts)
    success_criteria JSONB NOT NULL,
    failure_criteria JSONB NOT NULL,

    -- Escalation Rules
    escalation_rules JSONB NOT NULL DEFAULT '{
        "sample_behind_threshold": 0.8,
        "metric_drift_days": 7,
        "auto_escalate_on_failure": true
    }'::jsonb,

    -- Status & Outcome
    status TEXT NOT NULL DEFAULT 'SCHEDULED',
    CHECK (status IN ('SCHEDULED', 'ACTIVE', 'PAUSED', 'COMPLETED', 'TERMINATED')),

    outcome TEXT,
    CHECK (outcome IS NULL OR outcome IN ('SUCCESS', 'FAILURE', 'INCONCLUSIVE')),

    -- Outcome Details (Section 6.2 - Forced Outcome Declaration)
    outcome_summary TEXT,
    outcome_evidence JSONB,
    ceo_decision_logged BOOLEAN DEFAULT FALSE,

    -- Success Path (Section 7)
    success_sop JSONB,  -- What happens if SUCCESS
    promotion_triggered BOOLEAN DEFAULT FALSE,

    -- Calendar Category (Section 2.2)
    calendar_category TEXT NOT NULL DEFAULT 'ACTIVE_TEST',
    CHECK (calendar_category IN (
        'ECONOMIC_EVENT', 'ACTIVE_TEST', 'DECISION_DEADLINE',
        'CEO_ACTION_REQUIRED', 'COMPLETED', 'ARCHIVED'
    )),

    -- Context Dominance Verification (Section 3.3 Correction)
    temporal_veto_checked BOOLEAN DEFAULT FALSE,
    narrative_seduction_flagged BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraint: Tests must have clear ownership
    CONSTRAINT chk_owning_agent_format CHECK (owning_agent ~ '^EC-[0-9]{3}$')
);

COMMENT ON TABLE fhq_calendar.canonical_test_events IS
'CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001 Section 3: Canonical Test Event Schema.
Every test must explain itself without CEO archaeology.';

-- ============================================================================
-- SECTION 4.3: CEO CALENDAR ALERTS (Dialog-Driven Governance)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.ceo_calendar_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference to test
    test_id UUID REFERENCES fhq_calendar.canonical_test_events(test_id),
    observation_window_id UUID REFERENCES fhq_learning.observation_window(window_id),

    -- Alert Details
    alert_type TEXT NOT NULL,
    CHECK (alert_type IN (
        'SAMPLE_BEHIND_PLAN', 'METRIC_DRIFT', 'REGIME_MISALIGNMENT',
        'MID_TEST_REVIEW', 'END_TEST_REVIEW', 'JUDGMENT_REQUIRED',
        'GOVERNANCE_FAILURE', 'DIVERGENCE_DETECTED', 'VELOCITY_SPIKE'
    )),

    alert_title TEXT NOT NULL,
    alert_summary TEXT NOT NULL,  -- 2-5 sentences

    -- Decision Options (Section 4.3)
    decision_options JSONB NOT NULL,
    -- Example: [{"option": "extend_duration", "description": "..."}, ...]

    -- Status
    status TEXT NOT NULL DEFAULT 'PENDING',
    CHECK (status IN ('PENDING', 'ACKNOWLEDGED', 'RESOLVED', 'ESCALATED')),

    -- CEO Response
    ceo_decision TEXT,
    ceo_decision_rationale TEXT,
    ceo_responded_at TIMESTAMPTZ,

    -- Calendar Integration
    calendar_date DATE NOT NULL DEFAULT CURRENT_DATE,
    priority TEXT NOT NULL DEFAULT 'NORMAL',
    CHECK (priority IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

COMMENT ON TABLE fhq_calendar.ceo_calendar_alerts IS
'CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001 Section 4.3: Calendar-Driven CEO Interaction.
CEO is only interrupted when judgment is required.';

-- ============================================================================
-- SECTION 6: TEST LIFECYCLE LOG (Automation Tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.test_lifecycle_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES fhq_calendar.canonical_test_events(test_id),

    -- Lifecycle Event
    event_type TEXT NOT NULL,
    CHECK (event_type IN (
        'CREATED', 'STARTED', 'DAILY_UPDATE', 'MID_TEST_CHECKPOINT',
        'SAMPLE_UPDATE', 'METRIC_UPDATE', 'ESCALATION_TRIGGERED',
        'PAUSED', 'RESUMED', 'COMPLETED', 'ARCHIVED', 'CEO_DECISION'
    )),

    -- State Capture
    previous_state JSONB,
    new_state JSONB,

    -- Daily Report Content (Section 5)
    days_elapsed INTEGER,
    days_remaining INTEGER,
    current_sample_size INTEGER,
    expected_sample_size INTEGER,
    metric_deltas JSONB,  -- vs baseline
    executive_summary TEXT,  -- 2-5 sentences

    -- LVG Status (Section 5.5 Correction)
    lvg_status JSONB,
    -- Contains: entropy_score, thrashing_index, governor_action

    -- Recommendations (Section 5)
    recommendations JSONB,  -- Labeled as recommendation, not fact
    recommendation_source TEXT,  -- Meta-analysis reference

    -- Runbook Reference
    runbook_file TEXT,
    runbook_updated BOOLEAN DEFAULT FALSE,

    -- Timestamp
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    logged_by TEXT NOT NULL DEFAULT 'SYSTEM'
);

COMMENT ON TABLE fhq_calendar.test_lifecycle_log IS
'CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001 Section 6: Automatic RUNBOOK Propagation.
Every test day creates a lifecycle entry that feeds daily reports.';

-- ============================================================================
-- SECTION 11: SHADOW VETO DIVERGENCE AUDIT (Correction 1)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_calendar.divergence_audit_log (
    divergence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source of Divergence
    divergence_type TEXT NOT NULL,
    CHECK (divergence_type IN (
        'SHADOW_VETO', 'HUMAN_AI_DIVERGENCE', 'EPISTEMICALLY_INDEFENSIBLE',
        'INTUITION_OVERRIDE', 'SYSTEM_RECOMMENDATION_REJECTED'
    )),

    -- Context
    related_test_id UUID REFERENCES fhq_calendar.canonical_test_events(test_id),
    related_hypothesis_id UUID REFERENCES fhq_learning.hypothesis_canon(canon_id),

    -- The Divergence
    system_recommendation TEXT NOT NULL,
    human_decision TEXT NOT NULL,
    divergence_rationale TEXT,  -- Why CEO chose differently

    -- Automatic Experiment Generation (Section 11.1)
    antithesis_experiment_id UUID REFERENCES fhq_learning.antithesis_experiments(antithesis_id),
    experiment_generated BOOLEAN DEFAULT FALSE,

    -- Calendar Visualization (Section 11.2 - Purple color code)
    calendar_category TEXT DEFAULT 'DIVERGENCE_POINT',
    is_learning_arena BOOLEAN DEFAULT TRUE,

    -- Resolution
    resolved BOOLEAN DEFAULT FALSE,
    resolution_outcome TEXT,
    learning_captured JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

COMMENT ON TABLE fhq_calendar.divergence_audit_log IS
'CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001 Section 11: Shadow Veto as Divergence-Trigger.
Human-AI divergence points are our most important learning arenas.';

-- ============================================================================
-- SECTION 8: EC-022 OBSERVATION WINDOW CALENDAR INTEGRATION
-- ============================================================================

-- Add calendar-native fields to observation_window
ALTER TABLE fhq_learning.observation_window
ADD COLUMN IF NOT EXISTS starting_consensus_state JSONB,
ADD COLUMN IF NOT EXISTS expected_improvement TEXT,
ADD COLUMN IF NOT EXISTS improvement_metrics JSONB,
ADD COLUMN IF NOT EXISTS volume_scaling_active BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS metric_drift_alerts INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS calendar_event_id UUID;

COMMENT ON COLUMN fhq_learning.observation_window.volume_scaling_active IS
'Section 8.1: Volume Scaling Mandate - maximize evaluations even while reward frozen';

COMMENT ON COLUMN fhq_learning.observation_window.metric_drift_alerts IS
'Section 8.2: Metric Drift Alert counter - negative Brier trend over 7 days';

-- Update existing EC-022 window with calendar fields
UPDATE fhq_learning.observation_window
SET
    starting_consensus_state = '{"brier_score": null, "lvi": 0.0389, "tier1_death_rate": 0.50}'::jsonb,
    expected_improvement = 'Context Confidence Score shows predictive lift vs baseline on 2 macro regimes + 1 drawdown phase',
    improvement_metrics = '{
        "brier_score_target": "< baseline",
        "context_lift_required": 0.05,
        "macro_regimes_tested": 2,
        "drawdown_phases_tested": 1
    }'::jsonb,
    volume_scaling_active = TRUE
WHERE window_type = 'EC022_ELIGIBILITY';

-- ============================================================================
-- SECTION 6.3: SHADOW TIER MIRRORING FOR CALENDAR
-- ============================================================================

CREATE OR REPLACE VIEW fhq_calendar.v_shadow_tier_calendar_status AS
SELECT
    'Shadow Tier Monitoring' as event_name,
    'SYMMETRY_WATCH' as event_type,
    CURRENT_DATE as calendar_date,
    COUNT(*) as total_samples,
    COUNT(*) FILTER (WHERE shadow_result = 'SURVIVED') as survived_count,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(COUNT(*) FILTER (WHERE shadow_result = 'SURVIVED')::numeric / COUNT(*) * 100, 2)
        ELSE 0
    END as shadow_survival_rate,
    CASE
        WHEN COUNT(*) FILTER (WHERE shadow_result = 'SURVIVED')::numeric / NULLIF(COUNT(*), 0) > 0.30
        THEN 'WARNING: Over-hardening detected'
        ELSE 'NORMAL'
    END as calibration_status,
    'Validates if Tier-1 filters are precise or just brutal' as purpose
FROM fhq_learning.shadow_tier_registry;

-- ============================================================================
-- DASHBOARD CALENDAR VIEW (Section 2)
-- ============================================================================

CREATE OR REPLACE VIEW fhq_calendar.v_dashboard_calendar AS
WITH all_events AS (
    -- Active Tests
    SELECT
        test_id as event_id,
        test_name as event_name,
        'ACTIVE_TEST' as event_category,
        start_date as event_date,
        end_date,
        status as event_status,
        owning_agent,
        jsonb_build_object(
            'days_elapsed', days_elapsed,
            'days_remaining', days_remaining,
            'sample_status', sample_trajectory_status,
            'hypothesis', hypothesis_code
        ) as event_details,
        CASE
            WHEN outcome = 'SUCCESS' THEN '#22c55e'  -- Green
            WHEN outcome = 'FAILURE' THEN '#ef4444'  -- Red
            WHEN status = 'ACTIVE' THEN '#3b82f6'    -- Blue
            WHEN status = 'PAUSED' THEN '#f59e0b'    -- Amber
            ELSE '#6b7280'  -- Gray
        END as color_code,
        created_at
    FROM fhq_calendar.canonical_test_events

    UNION ALL

    -- CEO Alerts
    SELECT
        alert_id as event_id,
        alert_title as event_name,
        'CEO_ACTION_REQUIRED' as event_category,
        calendar_date as event_date,
        NULL as end_date,
        status as event_status,
        'CEO' as owning_agent,
        jsonb_build_object(
            'alert_type', alert_type,
            'priority', priority,
            'options_count', jsonb_array_length(decision_options)
        ) as event_details,
        CASE priority
            WHEN 'CRITICAL' THEN '#dc2626'  -- Red
            WHEN 'HIGH' THEN '#ea580c'      -- Orange
            WHEN 'NORMAL' THEN '#2563eb'    -- Blue
            ELSE '#6b7280'  -- Gray
        END as color_code,
        created_at
    FROM fhq_calendar.ceo_calendar_alerts
    WHERE status = 'PENDING'

    UNION ALL

    -- Observation Windows
    SELECT
        window_id as event_id,
        window_name as event_name,
        'OBSERVATION_WINDOW' as event_category,
        start_date as event_date,
        end_date,
        status as event_status,
        'SYSTEM' as owning_agent,
        jsonb_build_object(
            'current_days', current_market_days,
            'required_days', required_market_days,
            'criteria_met', criteria_met,
            'volume_scaling', volume_scaling_active
        ) as event_details,
        '#8b5cf6' as color_code,  -- Purple
        created_at
    FROM fhq_learning.observation_window

    UNION ALL

    -- Divergence Points (Purple - Section 11.2)
    SELECT
        divergence_id as event_id,
        divergence_type || ': Human-AI Divergence' as event_name,
        'DIVERGENCE_POINT' as event_category,
        created_at::date as event_date,
        NULL as end_date,
        CASE WHEN resolved THEN 'RESOLVED' ELSE 'ACTIVE' END as event_status,
        'CEO' as owning_agent,
        jsonb_build_object(
            'system_said', system_recommendation,
            'human_chose', human_decision,
            'learning_arena', is_learning_arena
        ) as event_details,
        '#a855f7' as color_code,  -- Purple (divergence)
        created_at
    FROM fhq_calendar.divergence_audit_log
)
SELECT
    event_id,
    event_name,
    event_category,
    event_date,
    end_date,
    event_status,
    owning_agent,
    event_details,
    color_code,
    -- Calendar grid helpers
    EXTRACT(YEAR FROM event_date) as year,
    EXTRACT(MONTH FROM event_date) as month,
    EXTRACT(DAY FROM event_date) as day,
    TO_CHAR(event_date, 'Day') as day_name,
    created_at
FROM all_events
ORDER BY event_date DESC, created_at DESC;

COMMENT ON VIEW fhq_calendar.v_dashboard_calendar IS
'CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001 Section 2: Dashboard Calendar View.
CEO must understand system state in <30 seconds.';

-- ============================================================================
-- ADD MISSING COLUMNS TO learning_velocity_metrics (before view depends on them)
-- ============================================================================

ALTER TABLE fhq_learning.learning_velocity_metrics
ADD COLUMN IF NOT EXISTS entropy_score NUMERIC,
ADD COLUMN IF NOT EXISTS thrashing_index NUMERIC,
ADD COLUMN IF NOT EXISTS governor_action TEXT DEFAULT 'NORMAL';

COMMENT ON COLUMN fhq_learning.learning_velocity_metrics.entropy_score IS
'Section 5.5: Are hypotheses too similar? Low entropy = groupthink risk';

COMMENT ON COLUMN fhq_learning.learning_velocity_metrics.thrashing_index IS
'Section 5.5: Is system changing mind too often? High thrashing = instability';

COMMENT ON COLUMN fhq_learning.learning_velocity_metrics.governor_action IS
'Section 5.5: Current LVG state - NORMAL, THROTTLED, or COOLED_OFF';

-- ============================================================================
-- SECTION 5.5: LVG STATUS VIEW FOR DAILY REPORTS
-- ============================================================================

CREATE OR REPLACE VIEW fhq_calendar.v_lvg_daily_status AS
SELECT
    CURRENT_DATE as report_date,
    COALESCE(
        (SELECT hypotheses_born FROM fhq_learning.learning_velocity_metrics
         WHERE metric_date = CURRENT_DATE ORDER BY computed_at DESC LIMIT 1),
        0
    ) as hypotheses_born_today,
    COALESCE(
        (SELECT hypotheses_killed FROM fhq_learning.learning_velocity_metrics
         WHERE metric_date = CURRENT_DATE ORDER BY computed_at DESC LIMIT 1),
        0
    ) as hypotheses_killed_today,
    COALESCE(
        (SELECT mean_time_to_falsification_hours FROM fhq_learning.learning_velocity_metrics
         WHERE metric_date = CURRENT_DATE ORDER BY computed_at DESC LIMIT 1),
        NULL
    ) as mean_time_to_falsification_hours,
    -- Entropy Score (are hypotheses too similar?) - NEW column added by this migration
    COALESCE(
        (SELECT entropy_score FROM fhq_learning.learning_velocity_metrics
         WHERE metric_date = CURRENT_DATE ORDER BY computed_at DESC LIMIT 1),
        NULL
    ) as entropy_score,
    -- Thrashing Index (changing mind too often?) - NEW column added by this migration
    COALESCE(
        (SELECT thrashing_index FROM fhq_learning.learning_velocity_metrics
         WHERE metric_date = CURRENT_DATE ORDER BY computed_at DESC LIMIT 1),
        NULL
    ) as thrashing_index,
    -- Governor Action - NEW column added by this migration
    COALESCE(
        (SELECT governor_action FROM fhq_learning.learning_velocity_metrics
         WHERE metric_date = CURRENT_DATE ORDER BY computed_at DESC LIMIT 1),
        'NORMAL'
    ) as governor_action,
    -- Brake Status
    COALESCE(
        (SELECT brake_triggered FROM fhq_learning.learning_velocity_metrics
         WHERE metric_date = CURRENT_DATE ORDER BY computed_at DESC LIMIT 1),
        FALSE
    ) as velocity_brake_active;

-- ============================================================================
-- SECTION 9: FAIL-CLOSED GOVERNANCE FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.check_calendar_sync()
RETURNS TABLE (
    check_name TEXT,
    check_status TEXT,
    discrepancy TEXT
) AS $$
BEGIN
    -- Check 1: All active tests have calendar entries
    RETURN QUERY
    SELECT
        'Active Tests in Calendar'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        CASE WHEN COUNT(*) = 0 THEN NULL
             ELSE COUNT(*)::TEXT || ' tests missing calendar entry' END::TEXT
    FROM fhq_calendar.canonical_test_events
    WHERE status = 'ACTIVE' AND calendar_category IS NULL;

    -- Check 2: All observation windows have calendar visibility
    RETURN QUERY
    SELECT
        'Observation Windows Visible'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        CASE WHEN COUNT(*) = 0 THEN NULL
             ELSE COUNT(*)::TEXT || ' windows not visible' END::TEXT
    FROM fhq_learning.observation_window
    WHERE status = 'ACTIVE';

    -- Check 3: Pending CEO alerts not older than 24h
    RETURN QUERY
    SELECT
        'CEO Alerts Timely'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARNING' END::TEXT,
        CASE WHEN COUNT(*) = 0 THEN NULL
             ELSE COUNT(*)::TEXT || ' alerts pending > 24h' END::TEXT
    FROM fhq_calendar.ceo_calendar_alerts
    WHERE status = 'PENDING' AND created_at < NOW() - INTERVAL '24 hours';

    RETURN;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Generate CEO Alert for Sample Size Behind Plan
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.generate_sample_alert(p_test_id UUID)
RETURNS UUID AS $$
DECLARE
    v_alert_id UUID;
    v_test RECORD;
BEGIN
    SELECT * INTO v_test FROM fhq_calendar.canonical_test_events WHERE test_id = p_test_id;

    IF v_test.current_sample_size < v_test.target_sample_size * 0.8 *
       (v_test.days_elapsed::numeric / NULLIF(v_test.duration_days, 0)) THEN

        INSERT INTO fhq_calendar.ceo_calendar_alerts (
            test_id,
            alert_type,
            alert_title,
            alert_summary,
            decision_options,
            priority
        ) VALUES (
            p_test_id,
            'SAMPLE_BEHIND_PLAN',
            'Sample size behind plan: ' || v_test.test_name,
            format('Test "%s" has %s samples at day %s, expected ~%s. Statistical power may be compromised.',
                v_test.test_name,
                v_test.current_sample_size,
                v_test.days_elapsed,
                ROUND(v_test.target_sample_size * v_test.days_elapsed::numeric / NULLIF(v_test.duration_days, 0))
            ),
            '[
                {"option": "increase_sample_size", "description": "Increase target sample size"},
                {"option": "extend_duration", "description": "Extend test duration"},
                {"option": "adjust_confidence", "description": "Adjust confidence threshold"},
                {"option": "terminate_early", "description": "Terminate test early"}
            ]'::jsonb,
            'HIGH'
        ) RETURNING alert_id INTO v_alert_id;

        -- Update test status
        UPDATE fhq_calendar.canonical_test_events
        SET sample_trajectory_status = 'BEHIND',
            calendar_category = 'CEO_ACTION_REQUIRED'
        WHERE test_id = p_test_id;

    END IF;

    RETURN v_alert_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Log Divergence and Generate Antithesis Experiment
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_calendar.log_shadow_veto(
    p_system_recommendation TEXT,
    p_human_decision TEXT,
    p_rationale TEXT,
    p_related_test_id UUID DEFAULT NULL,
    p_related_hypothesis_id UUID DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_divergence_id UUID;
    v_experiment_id UUID;
BEGIN
    -- Log the divergence
    INSERT INTO fhq_calendar.divergence_audit_log (
        divergence_type,
        related_test_id,
        related_hypothesis_id,
        system_recommendation,
        human_decision,
        divergence_rationale
    ) VALUES (
        'SHADOW_VETO',
        p_related_test_id,
        p_related_hypothesis_id,
        p_system_recommendation,
        p_human_decision,
        p_rationale
    ) RETURNING divergence_id INTO v_divergence_id;

    -- Section 11.1: Automatically generate CSEO Antithesis Experiment
    IF p_related_hypothesis_id IS NOT NULL THEN
        INSERT INTO fhq_learning.antithesis_experiments (
            target_hypothesis_id,
            antithesis_code,
            antithesis_class,
            antithesis_class_name,
            design_description,
            inverted_variables,
            status,
            created_by
        ) VALUES (
            p_related_hypothesis_id,
            'CSEO-VETO-' || to_char(NOW(), 'YYYYMMDD-HH24MISS'),
            'SHADOW_VETO',
            'CEO Shadow Veto Experiment',
            'CEO Shadow Veto: ' || p_human_decision,
            jsonb_build_object(
                'source', 'SHADOW_VETO',
                'divergence_id', v_divergence_id,
                'system_said', p_system_recommendation,
                'human_chose', p_human_decision
            ),
            'PENDING',
            'CSEO'
        ) RETURNING antithesis_id INTO v_experiment_id;

        -- Link experiment to divergence
        UPDATE fhq_calendar.divergence_audit_log
        SET antithesis_experiment_id = v_experiment_id,
            experiment_generated = TRUE
        WHERE divergence_id = v_divergence_id;
    END IF;

    RETURN v_divergence_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify all tables created
DO $$
DECLARE
    v_tables_created INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_tables_created
    FROM information_schema.tables
    WHERE table_schema = 'fhq_calendar'
    AND table_name IN ('canonical_test_events', 'ceo_calendar_alerts',
                       'test_lifecycle_log', 'divergence_audit_log');

    IF v_tables_created < 4 THEN
        RAISE EXCEPTION 'Migration 340 FAILED: Only % of 4 tables created', v_tables_created;
    END IF;

    RAISE NOTICE 'Migration 340 VERIFIED: % tables created', v_tables_created;
END $$;

COMMIT;

-- ============================================================================
-- POST-MIGRATION: Insert EC-022 as Canonical Test Event
-- ============================================================================

INSERT INTO fhq_calendar.canonical_test_events (
    test_name,
    test_code,
    owning_agent,
    monitoring_agent,
    business_intent,
    beneficiary_system,
    baseline_definition,
    target_metrics,
    target_sample_size,
    start_date,
    duration_days,
    success_criteria,
    failure_criteria,
    escalation_rules,
    status,
    calendar_category
) VALUES (
    'EC-022 Reward Logic Observation Window',
    'TEST-EC022-OBS-001',
    'EC-022',
    'EC-003',
    'Validate that context integration provides predictive lift before enabling reward logic',
    'EC-022 (Reward Architect)',
    '{
        "brier_score": "baseline from Day 23",
        "lvi": 0.0389,
        "tier1_death_rate": 0.50,
        "context_lift": 0
    }'::jsonb,
    '{
        "context_lift_vs_baseline": 0.05,
        "macro_regimes_tested": 2,
        "drawdown_phases_tested": 1,
        "ios010_bridge_operational": true
    }'::jsonb,
    30,  -- 30 market days
    '2026-01-24',
    30,
    '{
        "context_confidence_shows_lift": true,
        "macro_regimes_passed": 2,
        "drawdown_phase_passed": 1,
        "no_negative_brier_drift_7d": true
    }'::jsonb,
    '{
        "context_lift_negative": true,
        "brier_drift_sustained": true,
        "ios010_bridge_failed": true
    }'::jsonb,
    '{
        "sample_behind_threshold": 0.8,
        "metric_drift_days": 7,
        "auto_escalate_on_failure": true,
        "volume_scaling_mandate": true
    }'::jsonb,
    'ACTIVE',
    'ACTIVE_TEST'
) ON CONFLICT (test_code) DO NOTHING;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
