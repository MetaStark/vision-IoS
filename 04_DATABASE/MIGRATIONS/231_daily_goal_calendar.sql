-- =====================================================
-- Migration 231: Daily Goal Calendar (Track 1)
-- =====================================================
-- Directive: CEO-DIR-2026-0ZD (CORRECTED)
-- Baseline: CEO-DIR-2026-0ZC (Day 3 Truth Freeze)
-- Purpose: Operational discipline via daily goals with evidence
-- Authority: STIG (Infrastructure Sovereignty ADR-013)
-- Classification: G2 (Governance Enhancement)
--
-- SCOPE: Track 1 only (Operational Discipline)
-- NOT IN SCOPE: Track 2 (Revenue Targeting - separate directive)
-- =====================================================

BEGIN;

-- ============================================================================
-- TABLE 1: Daily Goal Calendar
-- ============================================================================
-- CEO owns goal definition, STIG owns verification (Hybrid process)

CREATE TABLE IF NOT EXISTS fhq_governance.daily_goal_calendar (
    goal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Temporal positioning
    phase_name TEXT NOT NULL,           -- 'WEEK_1_FOUNDATION', 'WEEK_2_CONSOLIDATION', etc.
    day_number INTEGER NOT NULL,        -- Day 1-10 within phase
    calendar_date DATE NOT NULL,        -- Actual calendar date
    iso_year INTEGER NOT NULL,
    iso_week INTEGER NOT NULL,

    -- Goal definition (CEO-owned)
    goal_title TEXT NOT NULL,
    goal_description TEXT NOT NULL,
    goal_type TEXT NOT NULL CHECK (
        goal_type IN ('INFRASTRUCTURE', 'CALIBRATION', 'GOVERNANCE')
    ),
    priority TEXT NOT NULL CHECK (priority IN ('P0', 'P1', 'P2')),

    -- Success criteria (machine-verifiable)
    success_criteria JSONB NOT NULL,    -- Machine-verifiable conditions
    verification_query TEXT,            -- SQL query to verify completion
    expected_threshold NUMERIC,         -- Numeric threshold for verification

    -- Completion tracking (STIG-owned verification)
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (
        status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'BLOCKED', 'DEFERRED')
    ),
    completion_percentage NUMERIC(5,2) DEFAULT 0 CHECK (
        completion_percentage >= 0 AND completion_percentage <= 100
    ),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Evidence linkage (court-proof per CEO directive)
    evidence_id UUID,                   -- Links to goal_completion_evidence
    evidence_hash TEXT,                 -- SHA-256 of completion evidence

    -- Dependencies
    depends_on UUID[],                  -- Goal IDs this goal depends on
    blocks UUID[],                      -- Goal IDs blocked by this goal

    -- Attribution
    assigned_agent TEXT NOT NULL CHECK (
        assigned_agent IN ('LARS', 'STIG', 'FINN', 'LINE', 'VEGA', 'CEO')
    ),
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Governance
    vega_attestation_id UUID,
    ceo_defined BOOLEAN DEFAULT TRUE,   -- CEO-defined goals (Hybrid process)

    CONSTRAINT unique_phase_day_goal UNIQUE (phase_name, day_number, calendar_date, goal_title),
    CONSTRAINT valid_completion CHECK (
        (status = 'COMPLETED' AND completed_at IS NOT NULL AND evidence_id IS NOT NULL) OR
        (status != 'COMPLETED')
    )
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_goal_calendar_date ON fhq_governance.daily_goal_calendar(calendar_date);
CREATE INDEX IF NOT EXISTS idx_goal_calendar_status ON fhq_governance.daily_goal_calendar(status, calendar_date);
CREATE INDEX IF NOT EXISTS idx_goal_calendar_phase ON fhq_governance.daily_goal_calendar(phase_name, day_number);

-- ============================================================================
-- TABLE 2: Goal Completion Evidence (Court-Proof)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.goal_completion_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    goal_id UUID NOT NULL REFERENCES fhq_governance.daily_goal_calendar(goal_id),

    -- Verification execution (STIG-owned)
    verification_query TEXT NOT NULL,
    verification_result JSONB NOT NULL,
    verification_timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Court-proof chain (CEO directive)
    query_result_hash TEXT NOT NULL,    -- SHA-256 of verification_result
    previous_hash TEXT,                 -- Chain linkage for integrity

    -- Success determination
    threshold_met BOOLEAN NOT NULL,
    threshold_value NUMERIC,
    actual_value NUMERIC,

    -- Attribution
    verified_by TEXT NOT NULL DEFAULT 'STIG',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for chain traversal
CREATE INDEX IF NOT EXISTS idx_goal_evidence_goal ON fhq_governance.goal_completion_evidence(goal_id);
CREATE INDEX IF NOT EXISTS idx_goal_evidence_chain ON fhq_governance.goal_completion_evidence(previous_hash);

-- ============================================================================
-- FUNCTION: Record Goal Completion (Evidence-Bound)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.record_goal_completion(
    p_goal_id UUID,
    p_verification_query TEXT,
    p_verification_result JSONB,
    p_threshold_met BOOLEAN,
    p_threshold_value NUMERIC,
    p_actual_value NUMERIC,
    p_verified_by TEXT DEFAULT 'STIG'
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_evidence_id UUID;
    v_query_hash TEXT;
    v_previous_hash TEXT;
BEGIN
    -- Compute SHA-256 hash of verification result
    v_query_hash := encode(sha256((p_verification_result::text)::bytea), 'hex');

    -- Get previous hash for chain integrity
    SELECT query_result_hash INTO v_previous_hash
    FROM fhq_governance.goal_completion_evidence
    ORDER BY created_at DESC
    LIMIT 1;

    -- Insert evidence record
    INSERT INTO fhq_governance.goal_completion_evidence (
        goal_id,
        verification_query,
        verification_result,
        query_result_hash,
        previous_hash,
        threshold_met,
        threshold_value,
        actual_value,
        verified_by
    ) VALUES (
        p_goal_id,
        p_verification_query,
        p_verification_result,
        v_query_hash,
        v_previous_hash,
        p_threshold_met,
        p_threshold_value,
        p_actual_value,
        p_verified_by
    )
    RETURNING evidence_id INTO v_evidence_id;

    -- Update goal status if threshold met
    IF p_threshold_met THEN
        UPDATE fhq_governance.daily_goal_calendar
        SET status = 'COMPLETED',
            completed_at = NOW(),
            evidence_id = v_evidence_id,
            evidence_hash = v_query_hash,
            completion_percentage = 100,
            updated_at = NOW()
        WHERE goal_id = p_goal_id;
    ELSE
        UPDATE fhq_governance.daily_goal_calendar
        SET completion_percentage = LEAST(100, (p_actual_value / NULLIF(p_threshold_value, 0)) * 100),
            updated_at = NOW()
        WHERE goal_id = p_goal_id;
    END IF;

    -- Log to governance (ADR-002)
    INSERT INTO fhq_governance.governance_actions_log (
        action_type,
        action_target,
        action_target_type,
        initiated_by,
        decision,
        decision_rationale,
        metadata
    ) VALUES (
        'GOAL_VERIFICATION',
        p_goal_id::TEXT,
        'DAILY_GOAL',
        p_verified_by,
        CASE WHEN p_threshold_met THEN 'COMPLETED' ELSE 'PROGRESS_RECORDED' END,
        format('Goal verification: threshold=%s, actual=%s, met=%s',
               p_threshold_value, p_actual_value, p_threshold_met),
        jsonb_build_object(
            'evidence_id', v_evidence_id,
            'query_hash', v_query_hash,
            'threshold_met', p_threshold_met,
            'directive', 'CEO-DIR-2026-0ZD'
        )
    );

    RETURN v_evidence_id;
END;
$$;

-- ============================================================================
-- SEED: Week 1 Foundation Phase Goals (Day 4-10)
-- Reset to HYGIENE (not superforecaster targets)
-- ============================================================================

INSERT INTO fhq_governance.daily_goal_calendar (
    phase_name, day_number, calendar_date, iso_year, iso_week,
    goal_title, goal_description, goal_type, priority,
    success_criteria, verification_query, expected_threshold,
    assigned_agent, created_by
) VALUES
-- Day 4: January 11, 2026 (Sunday)
('WEEK_1_FOUNDATION', 4, '2026-01-11', 2026, 2,
 'Confirm Day 3 baseline frozen',
 'Verify 0ZC evidence file exists and baseline is frozen',
 'GOVERNANCE', 'P0',
 '{"condition": "0ZC_evidence_exists"}',
 NULL,
 NULL,
 'STIG', 'STIG'),

('WEEK_1_FOUNDATION', 4, '2026-01-11', 2026, 2,
 'Heartbeat thresholds verified',
 'Confirm new heartbeat thresholds prevent false Sunday alerts',
 'INFRASTRUCTURE', 'P1',
 '{"condition": "no_false_alerts"}',
 NULL,
 NULL,
 'STIG', 'STIG'),

-- Day 5: January 12, 2026 (Monday)
('WEEK_1_FOUNDATION', 5, '2026-01-12', 2026, 2,
 'ios001 split tasks execute',
 'Verify 3 split tasks (crypto/fx/equity) run on schedule',
 'INFRASTRUCTURE', 'P0',
 '{"condition": "3_tasks_executed"}',
 'SELECT COUNT(DISTINCT task_name) FROM fhq_governance.governance_actions_log WHERE action_type = ''TASK_EXECUTION'' AND metadata->>''task_name'' LIKE ''ios001_%'' AND created_at::date = ''2026-01-12''',
 3,
 'STIG', 'STIG'),

('WEEK_1_FOUNDATION', 5, '2026-01-12', 2026, 2,
 'Regime sync verified',
 'Confirm ios003 -> fhq_meta.regime_state sync latency < 1h',
 'CALIBRATION', 'P1',
 '{"condition": "sync_latency_hours < 1"}',
 'SELECT EXTRACT(EPOCH FROM (NOW() - last_updated_at))/3600 FROM fhq_meta.regime_state',
 1,
 'STIG', 'STIG'),

-- Day 6: January 13, 2026 (Tuesday)
('WEEK_1_FOUNDATION', 6, '2026-01-13', 2026, 2,
 'Forecast volume stable',
 'Verify forecasts > 1000 for day (stability check)',
 'CALIBRATION', 'P0',
 '{"condition": "forecast_count >= 1000"}',
 'SELECT COUNT(*) FROM fhq_research.forecast_ledger WHERE forecast_made_at::date = ''2026-01-13''',
 1000,
 'FINN', 'STIG'),

('WEEK_1_FOUNDATION', 6, '2026-01-13', 2026, 2,
 'Resolution rate > 75%',
 'Verify forecast-outcome resolution rate exceeds 75%',
 'CALIBRATION', 'P1',
 '{"condition": "resolution_rate >= 0.75"}',
 'SELECT AVG(CASE WHEN is_resolved THEN 1.0 ELSE 0.0 END) FROM fhq_research.forecast_ledger WHERE forecast_made_at >= NOW() - INTERVAL ''7 days''',
 0.75,
 'FINN', 'STIG'),

-- Day 7: January 14, 2026 (Wednesday)
('WEEK_1_FOUNDATION', 7, '2026-01-14', 2026, 2,
 'Brier tracking operational',
 'Verify PRICE_DIRECTION and REGIME Brier scores logged separately',
 'CALIBRATION', 'P0',
 '{"condition": "both_event_types_tracked"}',
 'SELECT COUNT(DISTINCT forecast_type) FROM fhq_governance.brier_score_ledger WHERE created_at >= NOW() - INTERVAL ''7 days''',
 2,
 'STIG', 'STIG'),

('WEEK_1_FOUNDATION', 7, '2026-01-14', 2026, 2,
 'Calibration gates reviewed',
 'Verify all 9 calibration gates examined and documented',
 'GOVERNANCE', 'P1',
 '{"condition": "9_gates_reviewed"}',
 'SELECT COUNT(*) FROM fhq_governance.confidence_calibration_gates WHERE effective_from <= NOW() AND (effective_until IS NULL OR effective_until > NOW())',
 9,
 'STIG', 'STIG'),

-- Day 8: January 15, 2026 (Thursday)
('WEEK_1_FOUNDATION', 8, '2026-01-15', 2026, 2,
 'Regret/wisdom metrics stable',
 'Verify weekly_learning_metrics materialized view populated',
 'CALIBRATION', 'P0',
 '{"condition": "metrics_populated"}',
 'SELECT COUNT(*) FROM fhq_governance.weekly_learning_metrics WHERE iso_year = 2026',
 1,
 'STIG', 'STIG'),

('WEEK_1_FOUNDATION', 8, '2026-01-15', 2026, 2,
 'No DORMANT activation',
 'Confirm no premature activation of DORMANT components',
 'GOVERNANCE', 'P1',
 '{"condition": "no_new_activations"}',
 NULL,
 NULL,
 'VEGA', 'STIG'),

-- Day 9: January 16, 2026 (Friday)
('WEEK_1_FOUNDATION', 9, '2026-01-16', 2026, 3,
 'Week 1 learning summary',
 'Generate skill metrics aggregation for Week 1',
 'GOVERNANCE', 'P0',
 '{"condition": "skill_metrics_aggregated"}',
 'SELECT COUNT(*) FROM fhq_research.forecast_skill_metrics WHERE period_end >= ''2026-01-11''',
 1,
 'STIG', 'STIG'),

('WEEK_1_FOUNDATION', 9, '2026-01-16', 2026, 3,
 'Phase 0 stability confirmed',
 'Confirm all 4 ACTIVE IoS (001,003,006,010) healthy',
 'GOVERNANCE', 'P1',
 '{"condition": "4_ios_healthy"}',
 NULL,
 NULL,
 'STIG', 'STIG'),

-- Day 10: January 17, 2026 (Saturday)
('WEEK_1_FOUNDATION', 10, '2026-01-17', 2026, 3,
 'Week 1 evidence bundle',
 'Generate 8+ evidence files documenting Week 1 completion',
 'GOVERNANCE', 'P0',
 '{"condition": "evidence_files >= 8"}',
 NULL,
 8,
 'STIG', 'STIG'),

('WEEK_1_FOUNDATION', 10, '2026-01-17', 2026, 3,
 'Phase 1 activation readiness',
 'Complete IOS-003-B review for potential Phase 1 activation',
 'GOVERNANCE', 'P1',
 '{"condition": "ios003b_reviewed"}',
 NULL,
 NULL,
 'VEGA', 'STIG')

ON CONFLICT (phase_name, day_number, calendar_date, goal_title) DO NOTHING;

-- ============================================================================
-- GOVERNANCE LOGGING (ADR-002)
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'SCHEMA_MIGRATION',
    '231_daily_goal_calendar',
    'DATABASE_TABLES',
    'STIG',
    'MIGRATION_EXECUTED',
    'Migration 231: Daily Goal Calendar (Track 1) - CEO-DIR-2026-0ZD (CORRECTED)',
    jsonb_build_object(
        'migration_id', 231,
        'directive', 'CEO-DIR-2026-0ZD',
        'baseline_reference', 'CEO-DIR-2026-0ZC',
        'track', 'Track 1 (Operational Discipline)',
        'tables_created', ARRAY['daily_goal_calendar', 'goal_completion_evidence'],
        'functions_created', ARRAY['record_goal_completion'],
        'goals_seeded', 14,
        'week', 'WEEK_1_FOUNDATION',
        'focus', 'plumbing + calibration hygiene',
        'excludes', ARRAY['revenue_targeting', 'learning_tempo_tables']
    )
);

COMMIT;
