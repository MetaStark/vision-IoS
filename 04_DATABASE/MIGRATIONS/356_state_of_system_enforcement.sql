-- ============================================================================
-- MIGRATION 356: STATE OF THE SYSTEM ENFORCEMENT
-- ============================================================================
-- Authority: CEO State of the System Memo 2026-02-07 21:35 CET
-- Reference: ADR-016 (DEFCON Protocol), EC-022 Reward Logic
-- Executor: STIG (EC-003)
-- Date: 2026-02-08
--
-- Purpose:
--   1. Escalate DEFCON from GREEN to ORANGE per ADR-016
--   2. Update EC-022 test status to PRECONDITION_UNMET
--   3. Document constitutional non-compliance state
--
-- Evidence:
--   - FSS = -1.24 (worse than climatological baseline)
--   - Learning loop broken (hypothesis_death_daemon dormant)
--   - LVI not computed since 2026-01-24
--   - learning_updates_count = 0
--   - context_lift_computable = false
--   - ios010_bridge_operational = false
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. DEFCON STATE CHANGE: GREEN → ORANGE
-- ============================================================================
-- Per ADR-016: ORANGE = "Epistemic breach, paper-only execution,
-- model development freeze, stricter validation gates"

-- Mark current state as not current
UPDATE fhq_governance.defcon_state
SET is_current = false
WHERE is_current = true;

-- Insert new ORANGE state
INSERT INTO fhq_governance.defcon_state (
    state_id,
    defcon_level,
    triggered_at,
    triggered_by,
    trigger_reason,
    auto_expire_at,
    is_current,
    created_at
) VALUES (
    gen_random_uuid(),
    'ORANGE',
    NOW(),
    'STIG',
    'CEO State of System Memo 2026-02-07: Constitutional non-compliance verified. '
    || 'FSS = -1.24 (worse than random). Learning loop broken: '
    || 'hypothesis_death_daemon DORMANT, 0 hypotheses killed in 7 days, '
    || 'LVI not computed since 2026-01-24. Epistemic risk cannot be eliminated. '
    || 'System has no constitutional right to act.',
    NULL,  -- No auto-expire; requires explicit CEO directive to lift
    true,
    NOW()
);

-- Log transition in defcon_transitions
-- transition_type must be: DOWNGRADE, UPGRADE, or RESET
-- authorization_method must be: AUTOMATIC, STIG, VEGA, CEO, or SYSTEM
-- GREEN→ORANGE is an UPGRADE (higher threat level)
INSERT INTO fhq_governance.defcon_transitions (
    transition_id,
    from_level,
    to_level,
    transition_type,
    reason,
    authorized_by,
    authorization_method,
    evidence_bundle,
    transition_timestamp,
    created_at
) VALUES (
    gen_random_uuid(),
    'GREEN'::defcon_level,
    'ORANGE'::defcon_level,
    'UPGRADE',  -- GREEN→ORANGE is escalation (UPGRADE in DEFCON terms)
    'CEO State of System Memo 2026-02-07: Epistemic breach verified. '
    || 'FSS = -1.24, learning loop broken, LVI stale 14 days.',
    'STIG',
    'CEO',  -- Authorized by CEO memo
    jsonb_build_object(
        'memo_timestamp', '2026-02-07T21:35:00+01:00',
        'fss_value', -1.24,
        'learning_loop_status', 'BROKEN',
        'hypotheses_killed_7d', 0,
        'lvi_last_computed', '2026-01-24',
        'constitutional_status', 'NON-COMPLIANT'
    ),
    NOW(),
    NOW()
);

-- ============================================================================
-- 2. EC-022 TEST STATUS: Extend constraint and set PRECONDITION_UNMET
-- ============================================================================
-- The test cannot measure "Context Lift" because preconditions are not met:
--   - learning_updates_count = 0
--   - context_lift_computable = false
--   - ios010_bridge_operational = false

-- First, extend the escalation_state constraint to include PRECONDITION_UNMET
ALTER TABLE fhq_calendar.canonical_test_events
DROP CONSTRAINT IF EXISTS canonical_test_events_escalation_state_check;

ALTER TABLE fhq_calendar.canonical_test_events
ADD CONSTRAINT canonical_test_events_escalation_state_check
CHECK (escalation_state = ANY (ARRAY['NONE'::text, 'WARNING'::text, 'ACTION_REQUIRED'::text, 'RESOLVED'::text, 'PRECONDITION_UNMET'::text]));

-- Now update EC-022 test status
UPDATE fhq_calendar.canonical_test_events
SET
    escalation_state = 'PRECONDITION_UNMET',
    ceo_action_required = false,  -- Not an action issue; it's a precondition issue
    recommended_actions = '["Restore learning loop (activate hypothesis_death_daemon)", "Activate lvi_calculator daemon", "Make IoS-010 Bridge operational", "Verify context_lift_computable = true before resuming test"]'::jsonb,
    measured_vs_expected = jsonb_set(
        measured_vs_expected,
        '{status}',
        '"PRECONDITION_UNMET"'
    ),
    outcome_summary = 'EC-022 test FROZEN due to precondition failures. '
        || 'Cannot measure Context Lift without: '
        || '(1) operational learning loop, '
        || '(2) LVI computation, '
        || '(3) IoS-010 Bridge. '
        || 'Test will resume when preconditions are satisfied. '
        || 'Per CEO State of System Memo 2026-02-07.',
    updated_at = NOW()
WHERE test_code = 'TEST-EC022-OBS-001';

-- ============================================================================
-- 3. LOG ENFORCEMENT IN CEO DIRECTIVES (if table exists)
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'fhq_governance'
               AND table_name = 'ceo_directives') THEN
        INSERT INTO fhq_governance.ceo_directives (
            directive_id,
            directive_code,
            title,
            status,
            issued_at,
            issued_by,
            content,
            metadata
        ) VALUES (
            gen_random_uuid(),
            'CEO-DIR-2026-MEMO-SOT-001',
            'State of the System Enforcement',
            'EXECUTED',
            NOW(),
            'LARS',
            'Enforcement of CEO State of System Memo 2026-02-07: '
            || 'DEFCON escalated to ORANGE. EC-022 frozen at PRECONDITION_UNMET. '
            || 'Constitutional non-compliance verified.',
            jsonb_build_object(
                'defcon_change', jsonb_build_object('from', 'GREEN', 'to', 'ORANGE'),
                'ec022_change', jsonb_build_object('from', 'ACTION_REQUIRED', 'to', 'PRECONDITION_UNMET'),
                'constitutional_status', 'NON-COMPLIANT',
                'fss_value', -1.24,
                'executor', 'STIG'
            )
        );
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================
--
-- SELECT defcon_level, triggered_by, trigger_reason, is_current
-- FROM fhq_governance.defcon_state
-- WHERE is_current = true;
--
-- SELECT test_code, escalation_state, outcome_summary
-- FROM fhq_calendar.canonical_test_events
-- WHERE test_code = 'TEST-EC022-OBS-001';
-- ============================================================================
