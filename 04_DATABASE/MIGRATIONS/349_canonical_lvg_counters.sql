-- Migration 349: CEO-DIR-2026-CRYPTO-LEARNING-VERIFICATION-001
-- Canonical LVG Counters - Direct from hypothesis_canon
--
-- Problem: v_lvg_daily_status queries learning_velocity_metrics (derived/cached)
--          which shows 0 when hypothesis_canon has 2 hypotheses today
--
-- Solution: Replace view to query directly from hypothesis_canon (canonical truth)
--
-- Authority: CEO Directive - "All CEO-visible learning counters MUST derive from hypothesis_canon"

-- Drop and recreate v_lvg_daily_status to use canonical source
DROP VIEW IF EXISTS fhq_calendar.v_lvg_daily_status CASCADE;

CREATE OR REPLACE VIEW fhq_calendar.v_lvg_daily_status AS
SELECT
    CURRENT_DATE AS report_date,

    -- Born Today: COUNT hypotheses created today (CANONICAL)
    COALESCE((
        SELECT COUNT(*)::integer
        FROM fhq_learning.hypothesis_canon
        WHERE created_at::date = CURRENT_DATE
    ), 0) AS hypotheses_born_today,

    -- Killed Today: COUNT hypotheses falsified today (CANONICAL)
    COALESCE((
        SELECT COUNT(*)::integer
        FROM fhq_learning.hypothesis_canon
        WHERE status = 'FALSIFIED'
          AND falsified_at::date = CURRENT_DATE
    ), 0) AS hypotheses_killed_today,

    -- Mean time to falsification (from velocity metrics if available)
    COALESCE((
        SELECT mean_time_to_falsification_hours
        FROM fhq_learning.learning_velocity_metrics
        WHERE metric_date = CURRENT_DATE
        ORDER BY computed_at DESC LIMIT 1
    ), NULL::numeric) AS mean_time_to_falsification_hours,

    -- Entropy score (from velocity metrics if available)
    COALESCE((
        SELECT entropy_score
        FROM fhq_learning.learning_velocity_metrics
        WHERE metric_date = CURRENT_DATE
        ORDER BY computed_at DESC LIMIT 1
    ), NULL::numeric) AS entropy_score,

    -- Thrashing index (from velocity metrics if available)
    COALESCE((
        SELECT thrashing_index
        FROM fhq_learning.learning_velocity_metrics
        WHERE metric_date = CURRENT_DATE
        ORDER BY computed_at DESC LIMIT 1
    ), NULL::numeric) AS thrashing_index,

    -- Governor action (from velocity metrics if available)
    COALESCE((
        SELECT governor_action
        FROM fhq_learning.learning_velocity_metrics
        WHERE metric_date = CURRENT_DATE
        ORDER BY computed_at DESC LIMIT 1
    ), 'NORMAL'::text) AS governor_action,

    -- Velocity brake (from velocity metrics if available)
    COALESCE((
        SELECT brake_triggered
        FROM fhq_learning.learning_velocity_metrics
        WHERE metric_date = CURRENT_DATE
        ORDER BY computed_at DESC LIMIT 1
    ), false) AS velocity_brake_active;

COMMENT ON VIEW fhq_calendar.v_lvg_daily_status IS
'CEO-DIR-2026-CRYPTO-LEARNING-VERIFICATION-001: LVG counters derived directly from hypothesis_canon (canonical truth). Born/Killed Today queries hypothesis_canon, NOT derived tables.';

-- Create reconciliation view for CEO verification
CREATE OR REPLACE VIEW fhq_calendar.v_lvg_reconciliation AS
SELECT
    CURRENT_DATE AS check_date,

    -- Canonical counts from hypothesis_canon
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE created_at::date = CURRENT_DATE) AS canonical_born_today,

    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE status = 'FALSIFIED'
       AND falsified_at::date = CURRENT_DATE) AS canonical_killed_today,

    -- Counts by generator for today
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE created_at::date = CURRENT_DATE AND generator_id = 'FINN-E') AS finn_e_born_today,

    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE created_at::date = CURRENT_DATE AND generator_id = 'FINN-T') AS finn_t_born_today,

    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE created_at::date = CURRENT_DATE AND generator_id = 'GN-S') AS gn_s_born_today,

    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE created_at::date = CURRENT_DATE AND generator_id = 'finn_crypto_scheduler') AS crypto_born_today,

    -- Counts by asset class for today
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE created_at::date = CURRENT_DATE AND asset_class = 'EQUITY') AS equity_born_today,

    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon
     WHERE created_at::date = CURRENT_DATE AND asset_class = 'CRYPTO') AS crypto_class_born_today,

    -- Dashboard view count (for reconciliation check)
    (SELECT hypotheses_born_today FROM fhq_calendar.v_lvg_daily_status) AS dashboard_born_today,

    -- Reconciliation status
    CASE
        WHEN (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon WHERE created_at::date = CURRENT_DATE) =
             (SELECT hypotheses_born_today FROM fhq_calendar.v_lvg_daily_status)
        THEN 'RECONCILED'
        ELSE 'MISMATCH'
    END AS born_today_status;

COMMENT ON VIEW fhq_calendar.v_lvg_reconciliation IS
'CEO-DIR-2026-CRYPTO-LEARNING-VERIFICATION-001: Reconciliation view proving counters match. SUM(generators) = canonical_born_today = dashboard_born_today.';

-- Grant permissions
GRANT SELECT ON fhq_calendar.v_lvg_daily_status TO postgres;
GRANT SELECT ON fhq_calendar.v_lvg_reconciliation TO postgres;

-- Verification query (run after migration)
-- SELECT * FROM fhq_calendar.v_lvg_reconciliation;
