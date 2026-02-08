-- ============================================================================
-- MIGRATION 361: EXPERIMENT AUTO-SPAWN TRIGGER
-- ============================================================================
-- Authority: CEO-DIR-2026-128 DAY42 (WEEKLY RESET & LEARNING ACTIVATION)
-- Purpose: Auto-spawn experiments when hypotheses are inserted
-- Executor: STIG (EC-003)
-- Date: 2026-02-08
--
-- Root Cause:
--   Hypotheses are born without experiments, creating orphans that never
--   contribute to learning. The hypothesis → experiment → outcome chain is
--   broken at the first link.
--
-- Solution:
--   Create trigger that auto-spawns Tier 1 (FALSIFICATION_SWEEP) experiments
--   for hypotheses from specific generators (FINN-T, finn_crypto_scheduler).
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CREATE AUTO-SPAWN EXPERIMENT FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_learning.auto_spawn_experiment()
RETURNS TRIGGER AS $$
DECLARE
    v_experiment_id UUID;
    v_experiment_code TEXT;
BEGIN
    -- Only auto-spawn for active learning generators
    IF NEW.generator_id IN ('FINN-T', 'finn_crypto_scheduler', 'FINN-E', 'GN-S') THEN

        -- Generate experiment code
        v_experiment_code := 'EXP_AUTO_' || NEW.hypothesis_code;

        -- Check if experiment already exists for this hypothesis
        SELECT experiment_id INTO v_experiment_id
        FROM fhq_learning.experiment_registry
        WHERE hypothesis_id = NEW.canon_id
        LIMIT 1;

        IF v_experiment_id IS NULL THEN
            -- Note: tier_name is a generated column, don't include it
            INSERT INTO fhq_learning.experiment_registry (
                experiment_id,
                experiment_code,
                hypothesis_id,
                experiment_tier,
                status,
                execution_mode,
                parameters,
                prior_experiments_on_hypothesis,
                created_at,
                created_by,
                metadata
            ) VALUES (
                gen_random_uuid(),
                v_experiment_code,
                NEW.canon_id,
                1,  -- Tier 1: FALSIFICATION_SWEEP
                'PENDING',
                'AUTO',
                jsonb_build_object(
                    'auto_spawned', true,
                    'hypothesis_code', NEW.hypothesis_code,
                    'generator_id', NEW.generator_id,
                    'asset_universe', NEW.asset_universe,
                    'expected_timeframe_hours', NEW.expected_timeframe_hours
                ),
                0,  -- First experiment on this hypothesis
                NOW(),
                'AUTO_SPAWN_TRIGGER',
                jsonb_build_object(
                    'directive', 'CEO-DIR-2026-128',
                    'spawned_at', NOW(),
                    'reason', 'No orphan hypotheses rule'
                )
            );

            RAISE NOTICE 'AUTO_SPAWN: Created experiment % for hypothesis %',
                v_experiment_code, NEW.hypothesis_code;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_learning.auto_spawn_experiment IS
'CEO-DIR-2026-128: Auto-spawn Tier 1 experiment when hypothesis is inserted. No orphan hypotheses rule.';

-- ============================================================================
-- 2. CREATE TRIGGER
-- ============================================================================

DROP TRIGGER IF EXISTS trg_auto_spawn_experiment ON fhq_learning.hypothesis_canon;

CREATE TRIGGER trg_auto_spawn_experiment
AFTER INSERT ON fhq_learning.hypothesis_canon
FOR EACH ROW
EXECUTE FUNCTION fhq_learning.auto_spawn_experiment();

COMMENT ON TRIGGER trg_auto_spawn_experiment ON fhq_learning.hypothesis_canon IS
'CEO-DIR-2026-128: Auto-spawn experiment on hypothesis birth. Prevents orphan hypotheses.';

-- ============================================================================
-- 3. BACKFILL: Create experiments for recent orphan hypotheses
-- ============================================================================
-- Create experiments for hypotheses born in last 7 days without experiments

-- Note: tier_name is a generated column, don't include it
INSERT INTO fhq_learning.experiment_registry (
    experiment_id,
    experiment_code,
    hypothesis_id,
    experiment_tier,
    status,
    execution_mode,
    parameters,
    prior_experiments_on_hypothesis,
    created_at,
    created_by,
    metadata
)
SELECT
    gen_random_uuid(),
    'EXP_BACKFILL_' || hc.hypothesis_code,
    hc.canon_id,
    1,
    'PENDING',
    'BACKFILL',
    jsonb_build_object(
        'backfilled', true,
        'hypothesis_code', hc.hypothesis_code,
        'generator_id', hc.generator_id,
        'asset_universe', hc.asset_universe,
        'expected_timeframe_hours', hc.expected_timeframe_hours
    ),
    0,
    NOW(),
    'BACKFILL_CEO_DIR_128',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-128',
        'backfilled_at', NOW(),
        'reason', 'Orphan hypothesis remediation'
    )
FROM fhq_learning.hypothesis_canon hc
LEFT JOIN fhq_learning.experiment_registry er ON hc.canon_id = er.hypothesis_id
WHERE hc.created_at > NOW() - INTERVAL '7 days'
  AND hc.status IN ('DRAFT', 'ACTIVE', 'WEAKENED')
  AND hc.generator_id IN ('FINN-T', 'finn_crypto_scheduler', 'FINN-E', 'GN-S')
  AND er.experiment_id IS NULL;

-- ============================================================================
-- 4. CREATE ORPHAN HYPOTHESIS MONITORING VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_learning.orphan_hypotheses AS
SELECT
    hc.hypothesis_code,
    hc.generator_id,
    hc.status,
    hc.created_at,
    hc.asset_universe,
    EXTRACT(EPOCH FROM (NOW() - hc.created_at)) / 3600 as age_hours,
    CASE WHEN er.experiment_id IS NOT NULL THEN 'HAS_EXPERIMENT' ELSE 'ORPHAN' END as experiment_status
FROM fhq_learning.hypothesis_canon hc
LEFT JOIN fhq_learning.experiment_registry er ON hc.canon_id = er.hypothesis_id
WHERE hc.status IN ('DRAFT', 'ACTIVE', 'WEAKENED')
  AND hc.created_at > NOW() - INTERVAL '30 days';

COMMENT ON VIEW fhq_learning.orphan_hypotheses IS
'CEO-DIR-2026-128: Identifies hypotheses without experiments. Goal: zero orphans.';

-- ============================================================================
-- 5. LOG MIGRATION IN DEFCON TRANSITIONS
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
    'CEO-DIR-2026-128 DAY42: Experiment auto-spawn trigger installed. '
    || 'All new hypotheses from FINN-T, finn_crypto_scheduler, FINN-E, GN-S now auto-spawn Tier 1 experiments.',
    'STIG',
    'CEO',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-128',
        'day', 'DAY42',
        'action', 'EXPERIMENT_AUTO_SPAWN_TRIGGER',
        'trigger_created', 'trg_auto_spawn_experiment',
        'function_created', 'fhq_learning.auto_spawn_experiment',
        'view_created', 'fhq_learning.orphan_hypotheses',
        'backfill_performed', true
    ),
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================
--
-- 1. Verify trigger exists:
-- SELECT tgname FROM pg_trigger WHERE tgname = 'trg_auto_spawn_experiment';
--
-- 2. Check orphan hypotheses (should be zero or near-zero):
-- SELECT experiment_status, COUNT(*) FROM fhq_learning.orphan_hypotheses GROUP BY 1;
--
-- 3. Verify backfill:
-- SELECT COUNT(*) FROM fhq_learning.experiment_registry
-- WHERE created_by = 'BACKFILL_CEO_DIR_128';
-- ============================================================================
