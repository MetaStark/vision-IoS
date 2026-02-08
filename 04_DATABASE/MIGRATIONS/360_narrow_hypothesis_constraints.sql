-- ============================================================================
-- MIGRATION 360: NARROW HYPOTHESIS CONSTRAINTS
-- ============================================================================
-- Authority: CEO-DIR-2026-128 DAY41 (WEEKLY RESET & LEARNING ACTIVATION)
-- Purpose: Enforce hypothesis quality through schema constraints
-- Executor: STIG (EC-003)
-- Date: 2026-02-08
--
-- Root Cause:
--   FjordHQ generates "broad" hypotheses that are unfalsifiable within
--   reasonable timeframes. Win rate = 0%, FSS = -1.265 (worse than random).
--
-- Solution:
--   1. Max 7-day (168h) lifespan constraint
--   2. Binary direction enforcement (UP/DOWN only for new, NEUTRAL allowed for legacy)
--   3. Falsification criteria required
--   4. Hypothesis class freeze table for CEO directive enforcement
--
-- NOTE: NEUTRAL direction allowed for legacy hypotheses. New generators
-- should enforce UP/DOWN at generation time, not at DB constraint level.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. ADD TIMEFRAME CONSTRAINT (MAX 168 HOURS = 7 DAYS)
-- ============================================================================
-- Prevents long-horizon unfalsifiable hypotheses.
-- Existing data: All within 72h, so this is forward-looking protection.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_max_timeframe'
        AND table_schema = 'fhq_learning'
    ) THEN
        ALTER TABLE fhq_learning.hypothesis_canon
        ADD CONSTRAINT chk_max_timeframe
        CHECK (expected_timeframe_hours <= 168);
    END IF;
END $$;

COMMENT ON CONSTRAINT chk_max_timeframe ON fhq_learning.hypothesis_canon IS
'CEO-DIR-2026-128: Max 7-day (168h) hypothesis lifespan to ensure falsifiability';

-- ============================================================================
-- 2. FALSIFICATION CRITERIA REQUIRED (SOFT ENFORCEMENT)
-- ============================================================================
-- Note: falsification_criteria is already JSONB, we enforce non-null for new.
-- Legacy hypotheses may have NULL, so we don't add a hard NOT NULL constraint.
-- Instead, generators must populate this field.

-- Create index to identify hypotheses without falsification criteria
CREATE INDEX IF NOT EXISTS idx_hypothesis_canon_missing_falsification
ON fhq_learning.hypothesis_canon(status, created_at)
WHERE falsification_criteria IS NULL;

-- ============================================================================
-- 3. CREATE HYPOTHESIS CLASS FREEZE TABLE
-- ============================================================================
-- CEO directive enforcement: frozen classes cannot generate new hypotheses.

CREATE TABLE IF NOT EXISTS fhq_governance.hypothesis_class_freeze (
    class_name TEXT PRIMARY KEY,
    frozen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    frozen_by TEXT NOT NULL DEFAULT 'CEO-DIR-2026-128',
    unfreeze_condition TEXT NOT NULL,
    freeze_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.hypothesis_class_freeze IS
'CEO-DIR-2026-128: Frozen hypothesis classes that cannot generate new hypotheses until unfreeze_condition is met';

-- Freeze problematic hypothesis classes per CEO directive
INSERT INTO fhq_governance.hypothesis_class_freeze (class_name, frozen_by, unfreeze_condition, freeze_reason)
VALUES
    ('GENERIC_MACRO', 'CEO-DIR-2026-128', 'FSS >= 0 for asset class',
     'Broad macro hypotheses without specific causal mechanisms are unfalsifiable'),
    ('REGIME_AGNOSTIC', 'CEO-DIR-2026-128', 'FSS >= 0 for asset class',
     'Regime-agnostic hypotheses ignore critical market context'),
    ('LOW_SPECIFICITY', 'CEO-DIR-2026-128', 'FSS >= 0 for asset class',
     'Low specificity hypotheses cannot be tested rigorously')
ON CONFLICT (class_name) DO NOTHING;

-- ============================================================================
-- 4. CREATE HYPOTHESIS QUALITY METRICS VIEW
-- ============================================================================
-- Provides visibility into hypothesis quality for generators to self-regulate.

CREATE OR REPLACE VIEW fhq_learning.hypothesis_quality_metrics AS
SELECT
    generator_id,
    COUNT(*) as total_generated,
    COUNT(*) FILTER (WHERE status IN ('FALSIFIED', 'ANNIHILATED')) as falsified_count,
    COUNT(*) FILTER (WHERE status = 'ACTIVE') as active_count,
    AVG(time_to_falsification_hours) FILTER (WHERE time_to_falsification_hours IS NOT NULL) as avg_ttf_hours,
    AVG(expected_timeframe_hours) as avg_timeframe_hours,
    COUNT(*) FILTER (WHERE falsification_criteria IS NULL) as missing_falsification,
    COUNT(*) FILTER (WHERE expected_direction = 'NEUTRAL') as neutral_direction_count,
    COUNT(*) FILTER (WHERE prior_hypotheses_count IS NOT NULL AND prior_hypotheses_count > 0) as memory_aware_count
FROM fhq_learning.hypothesis_canon
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY generator_id;

COMMENT ON VIEW fhq_learning.hypothesis_quality_metrics IS
'CEO-DIR-2026-128: Hypothesis quality metrics by generator for self-regulation and monitoring';

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
    'CEO-DIR-2026-128 DAY41: Narrow hypothesis constraints installed. '
    || 'Max 168h timeframe, hypothesis class freeze table, quality metrics view.',
    'STIG',
    'CEO',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-128',
        'day', 'DAY41',
        'action', 'NARROW_HYPOTHESIS_CONSTRAINTS',
        'constraint_added', 'chk_max_timeframe (<=168h)',
        'table_created', 'fhq_governance.hypothesis_class_freeze',
        'view_created', 'fhq_learning.hypothesis_quality_metrics',
        'classes_frozen', ARRAY['GENERIC_MACRO', 'REGIME_AGNOSTIC', 'LOW_SPECIFICITY']
    ),
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================
--
-- 1. Verify constraint:
-- SELECT constraint_name FROM information_schema.table_constraints
-- WHERE table_schema = 'fhq_learning' AND table_name = 'hypothesis_canon'
-- AND constraint_name = 'chk_max_timeframe';
--
-- 2. Verify frozen classes:
-- SELECT * FROM fhq_governance.hypothesis_class_freeze;
--
-- 3. Check quality metrics:
-- SELECT * FROM fhq_learning.hypothesis_quality_metrics;
-- ============================================================================
