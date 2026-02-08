-- ============================================================================
-- MIGRATION 364: CEO-DIR-2026-129 CONTROLLED GENERATOR REACTIVATION
-- ============================================================================
-- Authority: CEO-DIR-2026-129 (2026-02-08, DAY39)
-- Purpose: Activate finn_crypto_scheduler ONLY for memory gate validation
-- Executor: STIG (EC-003)
-- DEFCON: ORANGE (unchanged)
--
-- SCOPE:
--   - ACTIVATE: finn_crypto_scheduler
--   - REMAIN DORMANT: finn_t_scheduler, finn_e_scheduler, gn_s_shadow_generator
--
-- CONSTRAINTS (Non-Negotiable):
--   - Memory-first enforcement (check_prior_failures must be called)
--   - Shadow/learning-only execution
--   - No Tier-1 or live execution
--   - 72-hour validation window
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ACTIVATE finn_crypto_scheduler
-- ============================================================================

UPDATE fhq_monitoring.daemon_health
SET lifecycle_status = 'ACTIVE',
    lifecycle_reason = 'CEO-DIR-2026-129: Controlled reactivation for memory gate validation. Memory-first enforcement required. 72h validation window.',
    ceo_directive_ref = 'CEO-DIR-2026-129',
    updated_at = NOW()
WHERE daemon_name = 'finn_crypto_scheduler';

-- ============================================================================
-- 2. EXPLICITLY CONFIRM OTHER GENERATORS REMAIN DORMANT
-- ============================================================================

UPDATE fhq_monitoring.daemon_health
SET lifecycle_reason = 'CEO-DIR-2026-124: DORMANT. CEO-DIR-2026-129 explicitly excludes this generator from reactivation.',
    updated_at = NOW()
WHERE daemon_name IN ('finn_t_scheduler', 'finn_e_scheduler', 'gn_s_shadow_generator')
  AND lifecycle_status = 'DORMANT_EXPECTED';

-- ============================================================================
-- 3. LOG TRANSITION IN DEFCON TRANSITIONS
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
    'CEO-DIR-2026-129: Controlled generator reactivation for memory gate validation. '
    || 'finn_crypto_scheduler ACTIVE. All other generators remain DORMANT_EXPECTED.',
    'STIG',
    'CEO',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-129',
        'day', 'DAY39',
        'action', 'CONTROLLED_GENERATOR_REACTIVATION',
        'activated', ARRAY['finn_crypto_scheduler'],
        'remain_dormant', ARRAY['finn_t_scheduler', 'finn_e_scheduler', 'gn_s_shadow_generator'],
        'constraints', jsonb_build_object(
            'memory_first_enforcement', true,
            'shadow_only_execution', true,
            'no_tier1_execution', true,
            'no_capital_exposure', true,
            'success_window_hours', 72,
            'rollback_on_failure', true
        ),
        'success_criteria', jsonb_build_array(
            'At least 1 hypothesis birth with memory citation',
            'At least 1 hypothesis birth blocked by memory',
            'Measurable reduction in duplicate hypotheses',
            'Promotion gate continues rejecting low-skill output',
            'LVI stable or increases from zero'
        )
    ),
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
--
-- 1. Check generator status:
-- SELECT daemon_name, lifecycle_status, ceo_directive_ref
-- FROM fhq_monitoring.daemon_health
-- WHERE daemon_name LIKE 'finn%' OR daemon_name = 'gn_s_shadow_generator';
--
-- 2. Monitor memory blocks (run after generator executes):
-- SELECT * FROM fhq_learning.hypothesis_birth_blocks
-- WHERE blocked_at > NOW() - INTERVAL '24 hours';
--
-- 3. Check new hypotheses with memory citations:
-- SELECT hypothesis_code, prior_hypotheses_count, created_at
-- FROM fhq_learning.hypothesis_canon
-- WHERE created_at > NOW() - INTERVAL '24 hours'
-- ORDER BY created_at DESC;
-- ============================================================================
