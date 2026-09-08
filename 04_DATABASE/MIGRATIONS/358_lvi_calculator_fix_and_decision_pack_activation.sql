-- ============================================================================
-- MIGRATION 358: LVI CALCULATOR FIX & DECISION PACK GENERATOR ACTIVATION
-- ============================================================================
-- Authority: CEO directive (LVI investigation outcome)
-- Reference: DAY39 Session 4 — LVI calculator investigation
-- Executor: STIG (EC-003)
-- Date: 2026-02-08
--
-- Root Cause Analysis:
--   1. lvi_calculator writes to fhq_ops.control_room_lvi but constitutional
--      freshness checks read from fhq_governance.lvi_canonical — write target
--      mismatch causes perpetual "19 days stale" despite active daemon.
--      FIX: Python daemon patched to write to both tables (see lvi_calculator.py).
--
--   2. decision_pack_generator is DORMANT_EXPECTED, producing no new decision
--      packs. LVI formula requires completed experiments from decision_packs
--      within a 7-day window. Last pack: 2026-01-30 (9 days ago, outside window).
--      LVI = 0.0000 because completed_experiments = 0.
--      FIX: Activate decision_pack_generator daemon.
--
-- Scope:
--   - Activate decision_pack_generator daemon
--   - No capital movement enabled
--   - Learning infrastructure repair only
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ACTIVATE decision_pack_generator
-- ============================================================================
-- This daemon generates decision packs from hypothesis evaluations.
-- Without it, the LVI calculator has zero input and computes LVI = 0.0000.

UPDATE fhq_monitoring.daemon_health
SET
    lifecycle_status = 'ACTIVE',
    lifecycle_reason = 'LVI input starvation fix: decision packs required for LVI computation. '
        || 'Previous: DORMANT_EXPECTED per CEO-DIR-2026-124. '
        || 'Root cause: LVI = 0.0000 because completed_experiments = 0 in 7d window.',
    lifecycle_updated_at = NOW(),
    ceo_directive_ref = 'CEO-LVI-FIX-20260208'
WHERE daemon_name = 'decision_pack_generator';

-- ============================================================================
-- 2. LOG FIX IN DEFCON TRANSITIONS
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
    'ORANGE'::defcon_level,
    'RESET',
    'LVI calculator fix: decision_pack_generator activated to resolve LVI input starvation. '
    || 'LVI daemon write target also patched to include fhq_governance.lvi_canonical.',
    'STIG',
    'CEO',
    jsonb_build_object(
        'action', 'LVI_CALCULATOR_FIX',
        'daemon_activated', 'decision_pack_generator',
        'code_fix', 'lvi_calculator.py store_lvi() now writes to lvi_canonical + control_room_lvi',
        'root_cause_1', 'Write target mismatch: daemon wrote to fhq_ops.control_room_lvi, governance reads fhq_governance.lvi_canonical',
        'root_cause_2', 'Input starvation: decision_pack_generator DORMANT, no packs in 7d window, LVI = 0.0000',
        'defcon_status', 'ORANGE (unchanged)'
    ),
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================
--
-- SELECT daemon_name, lifecycle_status, lifecycle_reason, ceo_directive_ref
-- FROM fhq_monitoring.daemon_health
-- WHERE daemon_name = 'decision_pack_generator';
--
-- Expected: lifecycle_status = 'ACTIVE', ceo_directive_ref = 'CEO-LVI-FIX-20260208'
-- ============================================================================
