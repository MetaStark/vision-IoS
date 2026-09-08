-- Migration 180: FINN-006 Adaptive Learning Functions
-- CEO-DIR-2026-FINN-006: Adaptive Epistemic Learning Loop
--
-- Purpose: Core learning functions that enable the system to adapt
-- during the first 1,000 cognitive runs.
--
-- Functions:
--   1. calculate_regime_aware_weights() - Section 3.1, EC-020
--   2. apply_surprise_resampling() - Section 3.2, EC-021
--   3. detect_efficiency_anomaly() - Section 5, VEGA
--
-- Authority: CEO APPROVED (2025-12-30T23:30:00Z)
-- Owners: EC-020, EC-021, VEGA

BEGIN;

-- ============================================================================
-- FUNCTION 1: calculate_regime_aware_weights
-- Owner: EC-020 (SitC)
-- Purpose: Calculate evidence path weights based on historical efficiency
-- per regime (noise in BULL may be signal in BROKEN)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.calculate_regime_aware_weights(
    p_ontology_path TEXT[],
    p_regime_id TEXT,
    p_lookback_runs INTEGER DEFAULT 100
)
RETURNS TABLE (
    ontology_node TEXT,
    base_weight NUMERIC,
    regime_adjustment NUMERIC,
    final_weight NUMERIC,
    sample_size INTEGER,
    confidence TEXT
) AS $$
DECLARE
    v_default_weight NUMERIC := 0.5;
BEGIN
    RETURN QUERY
    WITH path_stats AS (
        SELECT
            unnest(rel.ontology_path) as node,
            rel.regime_id,
            COUNT(*) as retrieval_count,
            COUNT(*) FILTER (WHERE rel.was_used_in_chain = TRUE) as used_count,
            AVG(rel.noise_score) as avg_noise
        FROM fhq_research.retrieval_efficiency_log rel
        WHERE rel.regime_id = p_regime_id
          AND rel.created_at > NOW() - INTERVAL '7 days'
          AND rel.run_number >= (
              SELECT COALESCE(MAX(run_number), 0) - p_lookback_runs
              FROM fhq_research.retrieval_efficiency_log
          )
        GROUP BY unnest(rel.ontology_path), rel.regime_id
    ),
    weighted_stats AS (
        SELECT
            ps.node,
            v_default_weight as base_wt,
            -- Regime adjustment based on utilization rate
            CASE
                WHEN ps.retrieval_count >= 10 THEN
                    (ps.used_count::NUMERIC / ps.retrieval_count - 0.5) * 0.6
                ELSE
                    0  -- Not enough data, no adjustment
            END as regime_adj,
            -- Noise penalty
            COALESCE(-ps.avg_noise * 0.3, 0) as noise_penalty,
            ps.retrieval_count as samples
        FROM path_stats ps
    )
    SELECT
        ws.node,
        ws.base_wt,
        ws.regime_adj + ws.noise_penalty,
        GREATEST(0.1, LEAST(0.95,
            ws.base_wt + ws.regime_adj + ws.noise_penalty
        )),
        ws.samples,
        CASE
            WHEN ws.samples >= 20 THEN 'HIGH'
            WHEN ws.samples >= 10 THEN 'MEDIUM'
            WHEN ws.samples >= 5 THEN 'LOW'
            ELSE 'INSUFFICIENT'
        END
    FROM weighted_stats ws
    WHERE ws.node = ANY(p_ontology_path)

    UNION ALL

    -- Include paths with no history (default weight)
    SELECT
        path_node,
        v_default_weight,
        0,
        v_default_weight,
        0,
        'NO_HISTORY'
    FROM unnest(p_ontology_path) as path_node
    WHERE path_node NOT IN (
        SELECT node FROM path_stats
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION 2: apply_surprise_resampling
-- Owner: EC-021 (InForage)
-- Purpose: Implement the 5% anti-confirmation bias exploration quota
-- Returns nodes that should be re-tested despite being flagged as noise
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.apply_surprise_resampling(
    p_batch_id TEXT,
    p_current_retrievals INTEGER
)
RETURNS TABLE (
    evidence_node_id UUID,
    ontology_path TEXT[],
    noise_score NUMERIC,
    last_regime_id TEXT,
    reason TEXT
) AS $$
DECLARE
    v_quota_id UUID;
    v_quota_count INTEGER;
    v_used_count INTEGER;
    v_remaining INTEGER;
BEGIN
    -- Get or create quota for this batch
    SELECT id, surprise_samples_used
    INTO v_quota_id, v_used_count
    FROM fhq_research.surprise_resampling_quota
    WHERE batch_id = p_batch_id;

    IF v_quota_id IS NULL THEN
        -- Create new quota
        INSERT INTO fhq_research.surprise_resampling_quota (
            batch_id,
            batch_start_run,
            batch_end_run,
            total_retrievals
        ) VALUES (
            p_batch_id,
            1,
            100,
            p_current_retrievals
        )
        RETURNING id INTO v_quota_id;
        v_used_count := 0;
    ELSE
        -- Update total retrievals
        UPDATE fhq_research.surprise_resampling_quota
        SET total_retrievals = total_retrievals + p_current_retrievals
        WHERE id = v_quota_id;
    END IF;

    -- Calculate quota (5% of total)
    v_quota_count := GREATEST(1, FLOOR(p_current_retrievals * 0.05));
    v_remaining := v_quota_count - v_used_count;

    IF v_remaining <= 0 THEN
        -- Quota exhausted, return empty
        RETURN;
    END IF;

    -- Select candidates from flagged noise that deserve re-testing
    RETURN QUERY
    SELECT DISTINCT ON (rel.evidence_node_id)
        rel.evidence_node_id,
        rel.ontology_path,
        rel.noise_score,
        rel.regime_id,
        CASE
            WHEN rel.noise_score < 0.7 THEN 'BORDERLINE_NOISE'
            WHEN rel.regime_id != (
                SELECT regime_id FROM fhq_research.retrieval_efficiency_log
                ORDER BY created_at DESC LIMIT 1
            ) THEN 'REGIME_SHIFTED'
            ELSE 'RANDOM_EXPLORATION'
        END as reason
    FROM fhq_research.retrieval_efficiency_log rel
    WHERE rel.is_noise_candidate = TRUE
      AND rel.noise_score < 0.9  -- Don't re-test pure noise
      AND rel.created_at > NOW() - INTERVAL '7 days'
      -- Prioritize borderline cases and regime-shifted contexts
    ORDER BY
        rel.evidence_node_id,
        CASE
            WHEN rel.noise_score < 0.6 THEN 1  -- Borderline first
            WHEN rel.regime_id != (
                SELECT regime_id FROM fhq_research.retrieval_efficiency_log
                ORDER BY created_at DESC LIMIT 1
            ) THEN 2  -- Regime shift second
            ELSE 3
        END,
        RANDOM()  -- Randomize within priority
    LIMIT v_remaining;

    -- Update used count
    UPDATE fhq_research.surprise_resampling_quota
    SET surprise_samples_used = surprise_samples_used + v_remaining
    WHERE id = v_quota_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION 3: detect_efficiency_anomaly
-- Owner: VEGA (Audit)
-- Purpose: Flag batches where SitC-Discipline rises too quickly (>0.90)
-- This is a RISK SIGNAL per FINN-006 Section 5
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.detect_efficiency_anomaly(
    p_batch_id TEXT DEFAULT NULL
)
RETURNS TABLE (
    batch_id TEXT,
    run_range TEXT,
    avg_discipline NUMERIC,
    discipline_trend NUMERIC,
    anomaly_type TEXT,
    risk_level TEXT,
    recommended_action TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH batch_metrics AS (
        SELECT
            rel.batch_id,
            MIN(rel.run_number) as first_run,
            MAX(rel.run_number) as last_run,
            AVG(rel.sitc_discipline_after) as avg_disc,
            -- Calculate trend using linear regression slope
            REGR_SLOPE(rel.sitc_discipline_after, rel.run_number) as trend_slope,
            COUNT(DISTINCT rel.run_id) as run_count
        FROM fhq_research.retrieval_efficiency_log rel
        WHERE (p_batch_id IS NULL OR rel.batch_id = p_batch_id)
          AND rel.sitc_discipline_after IS NOT NULL
        GROUP BY rel.batch_id
        HAVING COUNT(DISTINCT rel.run_id) >= 10  -- Minimum sample
    )
    SELECT
        bm.batch_id,
        bm.first_run || '-' || bm.last_run,
        ROUND(bm.avg_disc, 4),
        ROUND(bm.trend_slope, 6),
        CASE
            -- Over-efficiency: Too good too fast
            WHEN bm.avg_disc > 0.90 THEN 'OVER_EFFICIENCY'
            -- Rapid improvement: Suspiciously fast learning
            WHEN bm.trend_slope > 0.01 THEN 'RAPID_IMPROVEMENT'
            -- Stagnation: No learning happening
            WHEN bm.trend_slope < 0.0001 AND bm.avg_disc < 0.50 THEN 'STAGNATION'
            -- Regression: Getting worse
            WHEN bm.trend_slope < -0.005 THEN 'REGRESSION'
            ELSE 'NORMAL'
        END,
        CASE
            WHEN bm.avg_disc > 0.90 THEN 'HIGH'
            WHEN bm.trend_slope > 0.01 THEN 'MEDIUM'
            WHEN bm.trend_slope < -0.005 THEN 'MEDIUM'
            WHEN bm.trend_slope < 0.0001 AND bm.avg_disc < 0.50 THEN 'LOW'
            ELSE 'NONE'
        END,
        CASE
            WHEN bm.avg_disc > 0.90 THEN 'HUMAN_REVIEW_REQUIRED: Potential over-pruning or semantic tunnel vision'
            WHEN bm.trend_slope > 0.01 THEN 'HUMAN_REVIEW_REQUIRED: Verify ontology re-anchoring'
            WHEN bm.trend_slope < -0.005 THEN 'INVESTIGATE: System may be degrading'
            WHEN bm.trend_slope < 0.0001 AND bm.avg_disc < 0.50 THEN 'MONITOR: Learning may be stuck'
            ELSE 'CONTINUE: Normal learning trajectory'
        END
    FROM batch_metrics bm
    WHERE bm.avg_disc > 0.90
       OR bm.trend_slope > 0.01
       OR bm.trend_slope < -0.005
       OR (bm.trend_slope < 0.0001 AND bm.avg_disc < 0.50)
       OR p_batch_id IS NOT NULL  -- Always return if specific batch requested
    ORDER BY
        CASE
            WHEN bm.avg_disc > 0.90 THEN 1
            WHEN bm.trend_slope > 0.01 THEN 2
            WHEN bm.trend_slope < -0.005 THEN 3
            ELSE 4
        END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION 4: get_learning_progress
-- Owner: VEGA (Audit)
-- Purpose: Track progress toward FINN-006 learning targets
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.get_learning_progress()
RETURNS TABLE (
    metric_name TEXT,
    current_value NUMERIC,
    target_value NUMERIC,
    baseline_value NUMERIC,
    progress_pct NUMERIC,
    status TEXT,
    runs_analyzed INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH run_metrics AS (
        SELECT
            COUNT(DISTINCT run_id) as total_runs,
            -- Chain Integrity (HARD_REQUIREMENT = 1.00)
            AVG(CASE WHEN was_used_in_chain = TRUE THEN 1.0 ELSE 0.0 END) as avg_chain_integrity,
            -- Retrieval Discipline (target = 0.70, baseline = 0.45)
            AVG(sitc_discipline_after) as avg_discipline
        FROM fhq_research.retrieval_efficiency_log
        WHERE created_at > NOW() - INTERVAL '7 days'
    )
    SELECT
        'SitC-Chain Integrity'::TEXT,
        ROUND(COALESCE(rm.avg_chain_integrity, 1.0), 4),
        1.00::NUMERIC,
        1.00::NUMERIC,  -- Baseline is also 1.00 (always required)
        100.0::NUMERIC,  -- Must be 100%
        CASE
            WHEN COALESCE(rm.avg_chain_integrity, 1.0) >= 1.00 THEN 'PASS'
            ELSE 'FAIL'
        END,
        rm.total_runs::INTEGER
    FROM run_metrics rm

    UNION ALL

    SELECT
        'SitC-Retrieval Discipline'::TEXT,
        ROUND(COALESCE(rm.avg_discipline, 0.45), 4),
        0.70::NUMERIC,
        0.45::NUMERIC,
        ROUND(
            LEAST(100, GREATEST(0,
                (COALESCE(rm.avg_discipline, 0.45) - 0.45) / (0.70 - 0.45) * 100
            )), 2
        ),
        CASE
            WHEN COALESCE(rm.avg_discipline, 0.45) >= 0.70 THEN 'TARGET_REACHED'
            WHEN COALESCE(rm.avg_discipline, 0.45) >= 0.60 THEN 'GOOD_PROGRESS'
            WHEN COALESCE(rm.avg_discipline, 0.45) >= 0.50 THEN 'LEARNING'
            ELSE 'BASELINE'
        END,
        rm.total_runs::INTEGER
    FROM run_metrics rm;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION 5: log_learning_checkpoint
-- Purpose: Create periodic checkpoint of learning state
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.log_learning_checkpoint(
    p_batch_id TEXT,
    p_checkpoint_run INTEGER
)
RETURNS UUID AS $$
DECLARE
    v_checkpoint_id UUID := gen_random_uuid();
BEGIN
    -- Get current learning metrics
    INSERT INTO fhq_research.retrieval_efficiency_log (
        id,
        run_id,
        batch_id,
        run_number,
        evidence_node_id,
        was_used_in_chain,
        usage_type,
        regime_id,
        sitc_discipline_after,
        directive_ref
    )
    SELECT
        v_checkpoint_id,
        gen_random_uuid(),
        p_batch_id,
        p_checkpoint_run,
        gen_random_uuid(),
        TRUE,
        'SYNTHESIS',
        'CHECKPOINT',
        (SELECT current_value FROM fhq_research.get_learning_progress() WHERE metric_name = 'SitC-Retrieval Discipline'),
        'CEO-DIR-2026-FINN-006'
    ;

    -- Log to audit
    INSERT INTO fhq_meta.adr_audit_log (
        action_type,
        entity_type,
        entity_id,
        new_values,
        performed_by,
        governance_gate
    ) VALUES (
        'CHECKPOINT',
        'LEARNING_STATE',
        v_checkpoint_id::TEXT,
        (SELECT jsonb_agg(row_to_json(lp)) FROM fhq_research.get_learning_progress() lp),
        'VEGA',
        'G1'
    );

    RETURN v_checkpoint_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEW: Learning Dashboard Summary
-- For Vision-IoS dashboard integration
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_learning_dashboard AS
SELECT
    lp.metric_name,
    lp.current_value,
    lp.target_value,
    lp.baseline_value,
    lp.progress_pct,
    lp.status,
    lp.runs_analyzed,
    CASE
        WHEN lp.status = 'PASS' OR lp.status = 'TARGET_REACHED' THEN 'green'
        WHEN lp.status = 'GOOD_PROGRESS' OR lp.status = 'LEARNING' THEN 'yellow'
        ELSE 'red'
    END as status_color,
    NOW() as snapshot_time
FROM fhq_research.get_learning_progress() lp;

-- ============================================================================
-- AUDIT: Log migration
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
    'MIGRATION_EXECUTE',
    '180_finn006_adaptive_learning_functions',
    'DATABASE_MIGRATION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-FINN-006: Core Adaptive Learning Functions',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-FINN-006',
        'functions', ARRAY[
            'calculate_regime_aware_weights',
            'apply_surprise_resampling',
            'detect_efficiency_anomaly',
            'get_learning_progress',
            'log_learning_checkpoint'
        ],
        'purpose', 'Core adaptive learning functions for 1,000-run program'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_func_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_func_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'fhq_research'
      AND p.proname IN (
          'calculate_regime_aware_weights',
          'apply_surprise_resampling',
          'detect_efficiency_anomaly',
          'get_learning_progress',
          'log_learning_checkpoint'
      );

    IF v_func_count < 5 THEN
        RAISE EXCEPTION 'Migration 180 FAILED: Only % of 5 functions created', v_func_count;
    END IF;

    RAISE NOTICE 'Migration 180 SUCCESS: All 5 adaptive learning functions created';
END $$;
