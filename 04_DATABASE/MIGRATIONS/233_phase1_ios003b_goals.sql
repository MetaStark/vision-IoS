-- =====================================================
-- Migration 233: Phase 1 IOS-003-B Observability Goals
-- =====================================================
-- Directive: CEO-DIR-2026-0ZE-A v2
-- Purpose: Insert Phase 1 verification goals for IOS-003-B
-- Authority: STIG (Infrastructure Sovereignty ADR-013)
-- Classification: G1 (Non-breaking governance enhancement)
--
-- This migration adds Phase 1 goals (Day 4-11) for:
-- - IOS-003-B activation verification
-- - 72h verification checkpoints
-- - Phase 1 success/null determination
-- =====================================================

BEGIN;

-- ============================================================================
-- Phase 1 Goals: IOS-003-B Observability Window (Day 4-11)
-- ============================================================================
-- Per CEO-DIR-2026-0ZE-A v2: 7-day verification window
-- Success Criterion: Divergence OR Null hypothesis - both valid outcomes

INSERT INTO fhq_governance.daily_goal_calendar (
    phase_name, day_number, calendar_date, iso_year, iso_week,
    goal_title, goal_description, goal_type, priority,
    success_criteria, verification_query, expected_threshold,
    assigned_agent, created_by
) VALUES

-- Day 4: January 11, 2026 (Sunday) - Activation
('WEEK_1_FOUNDATION', 4, '2026-01-11', 2026, 2,
 'IOS-003-B observability mode activated',
 'Verify IOS-003-B gate entry exists in ios_execution_gates with BLOCKED status',
 'INFRASTRUCTURE', 'P0',
 '{"condition": "gate_entry_exists", "gate_status": "BLOCKED"}',
 'SELECT COUNT(*) FROM fhq_governance.ios_execution_gates WHERE ios_id = ''IOS-003-B'' AND gate_type = ''FLASH_CONTEXT_EMISSION'' AND gate_status = ''BLOCKED''',
 1,
 'STIG', 'STIG'),

-- Day 5: January 12, 2026 (Monday) - First Production
('WEEK_1_FOUNDATION', 5, '2026-01-12', 2026, 2,
 'First 24h of delta production verified',
 'Verify IOS-003-B delta_log entries exist after activation',
 'CALIBRATION', 'P0',
 '{"condition": "delta_log_count > 0"}',
 'SELECT COUNT(*) FROM fhq_operational.delta_log WHERE created_at >= ''2026-01-11T20:00:00Z''',
 1,
 'STIG', 'STIG'),

-- Day 6: January 13, 2026 (Tuesday) - Schema Audit
('WEEK_1_FOUNDATION', 6, '2026-01-13', 2026, 2,
 'No forbidden writes detected',
 'Verify IOS-003-B has not written to fhq_governance or other forbidden schemas',
 'GOVERNANCE', 'P0',
 '{"condition": "no_forbidden_writes"}',
 NULL,
 NULL,
 'VEGA', 'STIG'),

-- Day 7: January 14, 2026 (Wednesday) - Distribution Check
('WEEK_1_FOUNDATION', 7, '2026-01-14', 2026, 2,
 'Delta distribution non-degenerate',
 'Verify delta_log has variance > 0 (not all same value)',
 'CALIBRATION', 'P0',
 '{"condition": "variance > 0"}',
 'SELECT VARIANCE(CAST(details->>''intensity'' AS FLOAT)) FROM fhq_operational.delta_log WHERE created_at >= ''2026-01-11T20:00:00Z'' AND details->>''intensity'' IS NOT NULL',
 0.001,
 'STIG', 'STIG'),

-- Day 8: January 15, 2026 (Thursday) - 72h Checkpoint
('WEEK_1_FOUNDATION', 8, '2026-01-15', 2026, 2,
 '72h verification complete',
 'Generate 72h verification evidence file with all checkpoint results',
 'GOVERNANCE', 'P0',
 '{"condition": "evidence_file_generated"}',
 NULL,
 NULL,
 'STIG', 'STIG'),

-- Day 9: January 16, 2026 (Friday) - Correlation Analysis
('WEEK_1_FOUNDATION', 9, '2026-01-16', 2026, 3,
 'Intraday vs daily correlation analyzed',
 'Compute correlation between intraday_delta and daily_regime_change',
 'CALIBRATION', 'P0',
 '{"condition": "correlation_computed", "target": "CORR < 0.7 OR CORR >= 0.9"}',
 NULL,
 NULL,
 'FINN', 'STIG'),

-- Day 10: January 17, 2026 (Saturday) - Phase 1 Verdict
('WEEK_1_FOUNDATION', 10, '2026-01-17', 2026, 3,
 'Phase 1 success/null determined',
 'VEGA reviews evidence and documents Phase 1 outcome (Divergence, Null, or Inconclusive)',
 'GOVERNANCE', 'P0',
 '{"condition": "verdict_documented", "valid_outcomes": ["DIVERGENCE", "NULL", "INCONCLUSIVE"]}',
 NULL,
 NULL,
 'VEGA', 'STIG'),

-- Day 11: January 18, 2026 (Sunday) - Evidence Bundle
('WEEK_1_FOUNDATION', 11, '2026-01-18', 2026, 3,
 'Phase 1 evidence bundle complete',
 'Generate 5+ evidence files documenting Phase 1 completion',
 'GOVERNANCE', 'P0',
 '{"condition": "evidence_files >= 5"}',
 NULL,
 5,
 'STIG', 'STIG')

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
    'GOAL_CALENDAR_UPDATE',
    'PHASE_1_IOS003B_GOALS',
    'DAILY_GOALS',
    'STIG',
    'GOALS_INSERTED',
    'CEO-DIR-2026-0ZE-A v2: Phase 1 IOS-003-B observability goals (Day 4-11) inserted into daily_goal_calendar',
    jsonb_build_object(
        'migration_id', 233,
        'directive', 'CEO-DIR-2026-0ZE-A-v2',
        'goals_inserted', 8,
        'phase', 'PHASE_1_IOS003B_OBSERVABILITY',
        'day_range', 'Day 4 (2026-01-11) to Day 11 (2026-01-18)',
        'verification_window', '7 days',
        'success_criteria', 'Divergence OR Null hypothesis - both valid outcomes'
    )
);

COMMIT;
