-- ============================================================================
-- MIGRATION 363: PHASE-2 READINESS VIEW
-- ============================================================================
-- Authority: CEO-DIR-2026-128 DAY44 (WEEKLY RESET & LEARNING ACTIVATION)
-- Purpose: Provide Phase-2 readiness assessment for CEO decision point
-- Executor: STIG (EC-003)
-- Date: 2026-02-08
--
-- Phase-2 Criteria:
--   1. LVI > 0 (non-zero learning velocity)
--   2. Decision packs flowing (at least 1 in 7 days)
--   3. FSS improving (avg > -0.50)
--   4. Memory citations active (at least 1 hypothesis with prior_hypotheses_count > 0)
--
-- Phase-2 Activation:
--   - 3/4 criteria met
--   - DEFCON not RED or BLACK
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CREATE PHASE-2 READINESS VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.phase2_readiness AS
WITH lvi_check AS (
    SELECT lvi_value > 0 as lvi_nonzero, lvi_value
    FROM fhq_governance.lvi_canonical
    ORDER BY computed_at DESC LIMIT 1
),
decision_pack_check AS (
    SELECT COUNT(*) > 0 as packs_flowing, COUNT(*) as pack_count
    FROM fhq_learning.decision_packs
    WHERE created_at > NOW() - INTERVAL '7 days'
),
fss_check AS (
    SELECT
        AVG(fss_value) > -0.50 as fss_acceptable,
        ROUND(AVG(fss_value)::numeric, 3) as fss_avg
    FROM fhq_research.fss_computation_log
    WHERE computation_timestamp > NOW() - INTERVAL '7 days'
),
memory_check AS (
    SELECT
        COUNT(*) > 0 as memory_active,
        COUNT(*) as memory_count
    FROM fhq_learning.hypothesis_canon
    WHERE prior_hypotheses_count IS NOT NULL
      AND prior_hypotheses_count > 0
),
defcon_check AS (
    SELECT defcon_level
    FROM fhq_governance.defcon_state
    WHERE is_current = true
)
SELECT
    COALESCE(l.lvi_nonzero, false) as lvi_nonzero,
    COALESCE(l.lvi_value, 0) as lvi_value,
    COALESCE(d.packs_flowing, false) as decision_packs_flowing,
    COALESCE(d.pack_count, 0) as decision_pack_count,
    COALESCE(f.fss_acceptable, false) as fss_acceptable,
    COALESCE(f.fss_avg, 0) as fss_average,
    COALESCE(m.memory_active, false) as memory_active,
    COALESCE(m.memory_count, 0) as memory_citation_count,
    COALESCE(c.defcon_level, 'UNKNOWN') as defcon_level,
    (
        CASE WHEN l.lvi_nonzero THEN 1 ELSE 0 END +
        CASE WHEN d.packs_flowing THEN 1 ELSE 0 END +
        CASE WHEN f.fss_acceptable THEN 1 ELSE 0 END +
        CASE WHEN m.memory_active THEN 1 ELSE 0 END
    ) as criteria_met,
    4 as criteria_total,
    (
        (
            CASE WHEN l.lvi_nonzero THEN 1 ELSE 0 END +
            CASE WHEN d.packs_flowing THEN 1 ELSE 0 END +
            CASE WHEN f.fss_acceptable THEN 1 ELSE 0 END +
            CASE WHEN m.memory_active THEN 1 ELSE 0 END
        ) >= 3
        AND COALESCE(c.defcon_level, 'UNKNOWN') NOT IN ('RED', 'BLACK')
    ) as phase2_ready,
    NOW() as assessed_at
FROM lvi_check l
CROSS JOIN decision_pack_check d
CROSS JOIN fss_check f
CROSS JOIN memory_check m
CROSS JOIN defcon_check c;

COMMENT ON VIEW fhq_governance.phase2_readiness IS
'CEO-DIR-2026-128: Phase-2 readiness assessment. 3/4 criteria required for activation.';

-- ============================================================================
-- 2. CREATE WEEKLY METRICS VIEW (or update existing materialized view)
-- ============================================================================
-- Note: weekly_learning_metrics may already exist as a materialized view.
-- We drop and recreate as a regular view for simpler updates.

DROP MATERIALIZED VIEW IF EXISTS fhq_governance.weekly_learning_metrics;

CREATE OR REPLACE VIEW fhq_governance.weekly_learning_metrics AS
SELECT
    -- Hypothesis metrics
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE created_at > NOW() - INTERVAL '7 days') as hypotheses_born_7d,
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE death_timestamp > NOW() - INTERVAL '7 days') as hypotheses_killed_7d,
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE status IN ('ACTIVE', 'DRAFT', 'WEAKENED')) as hypotheses_active,

    -- Decision pack metrics
    (SELECT COUNT(*) FROM fhq_learning.decision_packs
     WHERE created_at > NOW() - INTERVAL '7 days') as decision_packs_7d,
    (SELECT COUNT(*) FROM fhq_learning.decision_packs
     WHERE created_at > NOW() - INTERVAL '7 days' AND execution_status = 'EXECUTED') as packs_executed_7d,

    -- LVI metrics
    (SELECT lvi_value FROM fhq_governance.lvi_canonical
     ORDER BY computed_at DESC LIMIT 1) as current_lvi,

    -- Memory metrics
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE prior_hypotheses_count IS NOT NULL AND prior_hypotheses_count > 0
       AND created_at > NOW() - INTERVAL '7 days') as memory_citations_7d,
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_birth_blocks
     WHERE blocked_at > NOW() - INTERVAL '7 days') as birth_blocks_7d,

    -- FSS metrics
    (SELECT ROUND(AVG(fss_value)::numeric, 3) FROM fhq_research.fss_computation_log
     WHERE computation_timestamp > NOW() - INTERVAL '7 days') as fss_avg_7d,

    -- Timestamp
    NOW() as computed_at;

COMMENT ON VIEW fhq_governance.weekly_learning_metrics IS
'CEO-DIR-2026-128: Weekly learning metrics summary for Phase-2 assessment.';

-- ============================================================================
-- 3. LOG MIGRATION IN DEFCON TRANSITIONS
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
    'CEO-DIR-2026-128 DAY44: Phase-2 readiness view and weekly metrics installed. '
    || 'CEO decision point infrastructure ready.',
    'STIG',
    'CEO',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-128',
        'day', 'DAY44',
        'action', 'PHASE2_READINESS_INFRASTRUCTURE',
        'views_created', ARRAY['fhq_governance.phase2_readiness', 'fhq_governance.weekly_learning_metrics'],
        'criteria', ARRAY['LVI > 0', 'Decision packs flowing', 'FSS > -0.50', 'Memory active']
    ),
    NOW(),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================
--
-- 1. Check Phase-2 readiness:
-- SELECT * FROM fhq_governance.phase2_readiness;
--
-- 2. Check weekly metrics:
-- SELECT * FROM fhq_governance.weekly_learning_metrics;
-- ============================================================================
