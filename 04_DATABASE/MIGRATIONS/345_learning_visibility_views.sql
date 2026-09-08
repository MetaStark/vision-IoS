-- Migration 345: Learning Visibility Views
-- CEO-DIR-2026-DAY25: Learning Must Be Visually Verifiable
-- Creates canonical views for dashboard learning graphs

BEGIN;

-- View 1: Daily Learning Metrics (for time-series graphs)
CREATE OR REPLACE VIEW fhq_learning.v_daily_learning_metrics AS
SELECT
    DATE(created_at) as metric_date,
    -- Hypothesis counts
    COUNT(*) as hypotheses_total,
    COUNT(*) FILTER (WHERE status = 'FALSIFIED') as hypotheses_falsified,
    COUNT(*) FILTER (WHERE status NOT IN ('FALSIFIED', 'DRAFT')) as hypotheses_active,
    COUNT(*) FILTER (WHERE status = 'DRAFT') as hypotheses_draft,
    -- Death rate (Tier-1 target: 60-90%)
    ROUND(
        COUNT(*) FILTER (WHERE status = 'FALSIFIED')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE status != 'DRAFT'), 0) * 100,
        1
    ) as death_rate_pct,
    -- Error conversion (target: >25%)
    COUNT(*) FILTER (WHERE origin_error_id IS NOT NULL) as from_errors,
    -- Causal depth
    ROUND(AVG(causal_graph_depth)::numeric, 2) as avg_causal_depth,
    MAX(causal_graph_depth) as max_causal_depth,
    -- Generator distribution
    COUNT(*) FILTER (WHERE generator_id = 'FINN-E') as gen_finn_e,
    COUNT(*) FILTER (WHERE generator_id = 'FINN-T') as gen_finn_t,
    COUNT(*) FILTER (WHERE generator_id = 'GN-S') as gen_gn_s,
    COUNT(*) FILTER (WHERE generator_id IS NULL OR generator_id NOT IN ('FINN-E', 'FINN-T', 'GN-S')) as gen_other
FROM fhq_learning.hypothesis_canon
GROUP BY DATE(created_at)
ORDER BY DATE(created_at) DESC;

-- View 2: Learning Status Summary (for dashboard header)
CREATE OR REPLACE VIEW fhq_learning.v_learning_status_summary AS
SELECT
    -- Cumulative totals
    COUNT(*) as total_hypotheses,
    COUNT(*) FILTER (WHERE status = 'FALSIFIED') as total_falsified,
    COUNT(*) FILTER (WHERE status NOT IN ('FALSIFIED', 'DRAFT')) as total_active,
    -- Current death rate
    ROUND(
        COUNT(*) FILTER (WHERE status = 'FALSIFIED')::numeric /
        NULLIF(COUNT(*) FILTER (WHERE status != 'DRAFT'), 0) * 100,
        1
    ) as death_rate_pct,
    -- Target compliance
    CASE
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'FALSIFIED')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status != 'DRAFT'), 0) * 100, 1
        ) BETWEEN 60 AND 90 THEN 'ON_TRACK'
        WHEN ROUND(
            COUNT(*) FILTER (WHERE status = 'FALSIFIED')::numeric /
            NULLIF(COUNT(*) FILTER (WHERE status != 'DRAFT'), 0) * 100, 1
        ) > 90 THEN 'TOO_BRUTAL'
        ELSE 'TOO_LENIENT'
    END as death_rate_status,
    -- Causal depth
    ROUND(AVG(causal_graph_depth)::numeric, 2) as avg_causal_depth,
    -- Generator counts
    COUNT(*) FILTER (WHERE generator_id = 'FINN-E') as finn_e_count,
    COUNT(*) FILTER (WHERE generator_id = 'FINN-T') as finn_t_count,
    COUNT(*) FILTER (WHERE generator_id = 'GN-S') as gn_s_count,
    -- Activity
    MAX(created_at) as last_hypothesis_time,
    COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) as today_count
FROM fhq_learning.hypothesis_canon;

-- View 3: Generator Performance (for pie chart)
CREATE OR REPLACE VIEW fhq_learning.v_generator_performance AS
SELECT
    COALESCE(generator_id, 'UNKNOWN') as generator_name,
    COUNT(*) as total_generated,
    COUNT(*) FILTER (WHERE status = 'FALSIFIED') as falsified,
    COUNT(*) FILTER (WHERE status NOT IN ('FALSIFIED', 'DRAFT')) as surviving,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'FALSIFIED')::numeric /
        NULLIF(COUNT(*), 0) * 100,
        1
    ) as death_rate_pct,
    ROUND(AVG(causal_graph_depth)::numeric, 2) as avg_depth
FROM fhq_learning.hypothesis_canon
WHERE status != 'DRAFT'
GROUP BY generator_id
ORDER BY total_generated DESC;

COMMIT;

-- Verify views
SELECT 'v_daily_learning_metrics' as view_name, COUNT(*) as rows FROM fhq_learning.v_daily_learning_metrics
UNION ALL
SELECT 'v_learning_status_summary', 1 FROM fhq_learning.v_learning_status_summary
UNION ALL
SELECT 'v_generator_performance', COUNT(*) FROM fhq_learning.v_generator_performance;
