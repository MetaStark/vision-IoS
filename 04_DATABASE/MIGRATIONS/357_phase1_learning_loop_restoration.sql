-- ============================================================================
-- MIGRATION 357: PHASE 1 LEARNING LOOP RESTORATION
-- ============================================================================
-- Authority: CEO State of the System Memo 2026-02-07 — Phase 1 Restoration
-- Reference: ADR-016 (DEFCON ORANGE active), CEO-DIR-2026-124 (superseded)
-- Executor: STIG (EC-003)
-- Date: 2026-02-08
--
-- Purpose:
--   Restore learning loop by activating dormant daemons:
--   1. hypothesis_death_daemon - Enables hypothesis falsification
--   2. lvi_calculator - Computes Learning Velocity Index
--   3. hypothesis_experiment_bridge_daemon - Connects experiments to hypotheses
--
-- Precondition: DEFCON ORANGE active (per migration 356)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ACTIVATE hypothesis_death_daemon
-- ============================================================================
-- This daemon is responsible for falsifying hypotheses based on outcome data.
-- Without it, hypotheses are born but never killed, breaking the learning loop.

UPDATE fhq_monitoring.daemon_health
SET
    lifecycle_status = 'ACTIVE',
    lifecycle_reason = 'CEO Phase 1 Restoration 2026-02-08: Learning loop restoration. '
        || 'Previous: DORMANT_EXPECTED per CEO-DIR-2026-124.',
    lifecycle_updated_at = NOW(),
    ceo_directive_ref = 'CEO-PHASE1-RESTORE-20260208'
WHERE daemon_name = 'hypothesis_death_daemon';

-- ============================================================================
-- 2. ACTIVATE lvi_calculator
-- ============================================================================
-- Computes Learning Velocity Index (LVI) - the system's self-attestation
-- of learning capability. Last computed: 2026-01-24 (14 days stale).

UPDATE fhq_monitoring.daemon_health
SET
    lifecycle_status = 'ACTIVE',
    lifecycle_reason = 'CEO Phase 1 Restoration 2026-02-08: LVI computation restored. '
        || 'Previous: DORMANT_EXPECTED per CEO-DIR-2026-124.',
    lifecycle_updated_at = NOW(),
    ceo_directive_ref = 'CEO-PHASE1-RESTORE-20260208'
WHERE daemon_name = 'lvi_calculator';

-- ============================================================================
-- 3. ACTIVATE hypothesis_experiment_bridge_daemon
-- ============================================================================
-- Connects experiments to hypotheses, enabling the feedback loop from
-- experiment outcomes back to hypothesis validation.

UPDATE fhq_monitoring.daemon_health
SET
    lifecycle_status = 'ACTIVE',
    lifecycle_reason = 'CEO Phase 1 Restoration 2026-02-08: Experiment bridge restored. '
        || 'Previous: DORMANT_EXPECTED per CEO-DIR-2026-124.',
    lifecycle_updated_at = NOW(),
    ceo_directive_ref = 'CEO-PHASE1-RESTORE-20260208'
WHERE daemon_name = 'hypothesis_experiment_bridge_daemon';

-- ============================================================================
-- 4. LOG PHASE 1 RESTORATION IN DEFCON TRANSITIONS
-- ============================================================================

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
    'ORANGE'::defcon_level,
    'ORANGE'::defcon_level,  -- Staying ORANGE, but logging restoration action
    'RESET',  -- Using RESET to indicate state change within same level
    'Phase 1 Restoration: Learning loop daemons activated. '
    || 'DEFCON remains ORANGE until FSS >= 0.60.',
    'STIG',
    'CEO',
    jsonb_build_object(
        'phase', 'PHASE_1_RESTORATION',
        'daemons_activated', ARRAY[
            'hypothesis_death_daemon',
            'lvi_calculator',
            'hypothesis_experiment_bridge_daemon'
        ],
        'previous_directive', 'CEO-DIR-2026-124',
        'new_directive', 'CEO-PHASE1-RESTORE-20260208',
        'defcon_status', 'ORANGE (unchanged)',
        'next_phase', 'PHASE_2_SKILL_RESTORATION'
    ),
    NOW(),
    NOW()
);

-- ============================================================================
-- 5. UPDATE EC-022 measured_vs_expected
-- ============================================================================
-- Update the learning_updates_count expectation now that daemons are active

UPDATE fhq_calendar.canonical_test_events
SET
    measured_vs_expected = jsonb_set(
        measured_vs_expected,
        '{phase1_restoration}',
        jsonb_build_object(
            'activated_at', NOW(),
            'daemons_activated', ARRAY[
                'hypothesis_death_daemon',
                'lvi_calculator',
                'hypothesis_experiment_bridge_daemon'
            ],
            'next_check', 'Verify hypotheses being killed within 24h'
        )
    ),
    outcome_summary = 'EC-022 test FROZEN (PRECONDITION_UNMET). '
        || 'Phase 1 Restoration initiated 2026-02-08. '
        || 'Learning loop daemons activated. '
        || 'Waiting for: hypothesis deaths, LVI computation, IoS-010 bridge verification.',
    updated_at = NOW()
WHERE test_code = 'TEST-EC022-OBS-001';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================
--
-- SELECT daemon_name, lifecycle_status, lifecycle_reason
-- FROM fhq_monitoring.daemon_health
-- WHERE daemon_name IN ('hypothesis_death_daemon', 'lvi_calculator',
--                       'hypothesis_experiment_bridge_daemon');
--
-- Expected: All three should show lifecycle_status = 'ACTIVE'
-- ============================================================================
