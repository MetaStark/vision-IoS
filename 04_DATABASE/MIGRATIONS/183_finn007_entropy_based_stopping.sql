-- Migration 183: Entropy-Based Stopping Infrastructure
-- CEO-DIR-2026-FINN-007: Operation Freedom 2026 - Batch 2
-- Section 3.2: Entropy-Based Stopping Protocol
--
-- Purpose: Implement UCB-style Pandora's Box algorithm to stop retrieval
-- when expected information gain falls below threshold.
--
-- Research Basis: UCB Pandora's Box (2025)
-- "Viewing each generation as a costly box and using UCB-style algorithm
-- can stop retrieval when expected gain falls below threshold, matching
-- Best-of-N performance with 15-35% fewer samples"
--
-- Authority: CEO-DIR-2026-FINN-007
-- Owner: EC-021 (InForage)
-- Classification: LEARNING_INFRASTRUCTURE

BEGIN;

-- ============================================================================
-- TABLE: entropy_stopping_log
-- Tracks entropy calculations and stopping decisions per retrieval step
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.entropy_stopping_log (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run identification
    run_id                  UUID NOT NULL,
    run_number              INTEGER NOT NULL,
    batch_id                TEXT,
    retrieval_step          INTEGER NOT NULL,     -- Step number within run

    -- Entropy calculations (Shannon entropy)
    candidate_count         INTEGER NOT NULL,      -- Number of candidate answers
    candidate_distribution  JSONB NOT NULL,        -- Probability distribution over candidates
    current_entropy         NUMERIC(8,6) NOT NULL, -- H(candidates)
    previous_entropy        NUMERIC(8,6),          -- H(candidates) from previous step
    entropy_delta           NUMERIC(8,6) GENERATED ALWAYS AS (
                                CASE WHEN previous_entropy IS NOT NULL
                                     THEN current_entropy - previous_entropy
                                     ELSE NULL
                                END
                            ) STORED,

    -- Information gain estimation
    expected_gain           NUMERIC(8,6),          -- Estimated ΔH from another retrieval
    retrieval_cost          NUMERIC(10,6),         -- Cost of another retrieval
    gain_cost_ratio         NUMERIC(8,6) GENERATED ALWAYS AS (
                                CASE WHEN retrieval_cost > 0
                                     THEN expected_gain / retrieval_cost
                                     ELSE 0
                                END
                            ) STORED,

    -- Stopping decision
    stop_threshold          NUMERIC(5,4) DEFAULT 0.10,  -- ΔH threshold
    should_stop             BOOLEAN GENERATED ALWAYS AS (
                                (CASE WHEN previous_entropy IS NOT NULL
                                      THEN current_entropy - previous_entropy
                                      ELSE 1.0  -- First step, don't stop
                                 END) < 0.10
                                OR
                                (CASE WHEN retrieval_cost > 0
                                      THEN expected_gain / retrieval_cost
                                      ELSE 0
                                 END) < 1.0  -- Cost exceeds expected gain
                            ) STORED,
    actual_stopped          BOOLEAN DEFAULT FALSE,
    stop_reason             TEXT CHECK (stop_reason IN (
                                'ENTROPY_CONVERGED',      -- ΔH < threshold
                                'COST_EXCEEDED',          -- Cost > expected gain
                                'MAX_STEPS_REACHED',      -- Hit retrieval limit
                                'CONFIDENCE_ACHIEVED',    -- DINCO score high enough
                                'CONTINUED'               -- Did not stop
                            )),

    -- UCB exploration bonus
    ucb_exploration_bonus   NUMERIC(8,6),         -- Bonus for exploring new sources
    ucb_total_score         NUMERIC(8,6),         -- expected_gain + exploration_bonus

    -- Regime context
    regime_id               TEXT NOT NULL,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007'
);

-- ============================================================================
-- TABLE: retrieval_efficiency_batch_summary
-- Aggregated retrieval efficiency metrics per batch
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.retrieval_efficiency_batch_summary (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Batch identification
    batch_id                TEXT NOT NULL UNIQUE,
    batch_start_run         INTEGER NOT NULL,
    batch_end_run           INTEGER NOT NULL,

    -- Retrieval count metrics
    total_runs              INTEGER NOT NULL DEFAULT 0,
    total_retrieval_steps   INTEGER NOT NULL DEFAULT 0,
    avg_steps_per_run       NUMERIC(5,2) GENERATED ALWAYS AS (
                                CASE WHEN total_runs > 0
                                     THEN total_retrieval_steps::NUMERIC / total_runs
                                     ELSE 0
                                END
                            ) STORED,

    -- Early stopping metrics
    early_stopped_runs      INTEGER NOT NULL DEFAULT 0,
    avg_steps_saved         NUMERIC(5,2),         -- vs max allowed steps
    early_stop_rate         NUMERIC(5,4) GENERATED ALWAYS AS (
                                CASE WHEN total_runs > 0
                                     THEN early_stopped_runs::NUMERIC / total_runs
                                     ELSE 0
                                END
                            ) STORED,

    -- Batch 1 baseline comparison
    batch1_avg_steps        NUMERIC(5,2) DEFAULT NULL,
    step_reduction_pct      NUMERIC(5,4),         -- Target: 20% reduction

    -- Entropy convergence metrics
    avg_final_entropy       NUMERIC(8,6),
    avg_entropy_delta       NUMERIC(8,6),

    -- Stop reason distribution
    entropy_converged_count INTEGER DEFAULT 0,
    cost_exceeded_count     INTEGER DEFAULT 0,
    max_steps_count         INTEGER DEFAULT 0,
    confidence_achieved_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ,

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007'
);

-- ============================================================================
-- TABLE: active_inference_loop_log
-- Tracks fast/slow dual-process architecture decisions
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.active_inference_loop_log (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run identification
    run_id                  UUID NOT NULL,
    run_number              INTEGER NOT NULL,
    batch_id                TEXT,
    hypothesis_id           TEXT NOT NULL,

    -- Loop type
    loop_type               TEXT NOT NULL CHECK (loop_type IN (
                                'FAST',   -- Verify claims using cached knowledge (LAKE)
                                'SLOW'    -- Hypothesis generation, counterfactual simulation
                            )),

    -- Fast loop metrics
    fast_loop_duration_ms   INTEGER,
    fast_loop_cache_hits    INTEGER DEFAULT 0,
    fast_loop_confidence    NUMERIC(5,4),
    fast_loop_sufficient    BOOLEAN,              -- Did fast loop answer the question?

    -- Slow loop metrics (only if fast loop insufficient)
    slow_loop_activated     BOOLEAN DEFAULT FALSE,
    slow_loop_duration_ms   INTEGER,
    slow_loop_simulations   INTEGER DEFAULT 0,    -- Counterfactual simulations run
    slow_loop_retrievals    INTEGER DEFAULT 0,    -- External retrievals made
    slow_loop_confidence    NUMERIC(5,4),

    -- Decision rationale
    activation_reason       TEXT,                 -- Why slow loop was/wasn't activated
    uncertainty_threshold   NUMERIC(5,4) DEFAULT 0.70,
    internal_model_entropy  NUMERIC(8,6),         -- Uncertainty of internal model

    -- Outcome
    final_loop_used         TEXT CHECK (final_loop_used IN ('FAST', 'SLOW')),
    external_data_requested BOOLEAN DEFAULT FALSE,

    -- Regime context
    regime_id               TEXT NOT NULL,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007'
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Entropy stopping queries
CREATE INDEX idx_entropy_run ON fhq_research.entropy_stopping_log(run_id);
CREATE INDEX idx_entropy_batch ON fhq_research.entropy_stopping_log(batch_id);
CREATE INDEX idx_entropy_stopped ON fhq_research.entropy_stopping_log(actual_stopped)
    WHERE actual_stopped = TRUE;
CREATE INDEX idx_entropy_reason ON fhq_research.entropy_stopping_log(stop_reason);

-- Batch summary
CREATE INDEX idx_retrieval_batch ON fhq_research.retrieval_efficiency_batch_summary(batch_id);

-- Active inference queries
CREATE INDEX idx_inference_run ON fhq_research.active_inference_loop_log(run_id);
CREATE INDEX idx_inference_slow ON fhq_research.active_inference_loop_log(slow_loop_activated)
    WHERE slow_loop_activated = TRUE;

-- ============================================================================
-- FUNCTION: Calculate Shannon entropy
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.calculate_shannon_entropy(
    p_distribution JSONB
)
RETURNS NUMERIC AS $$
DECLARE
    v_entropy NUMERIC := 0;
    v_prob NUMERIC;
BEGIN
    FOR v_prob IN SELECT (value::NUMERIC) FROM jsonb_array_elements_text(p_distribution)
    LOOP
        IF v_prob > 0 THEN
            v_entropy := v_entropy - (v_prob * LOG(2, v_prob));
        END IF;
    END LOOP;

    RETURN ROUND(v_entropy, 6);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Determine if retrieval should stop
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.should_stop_retrieval(
    p_current_entropy NUMERIC,
    p_previous_entropy NUMERIC,
    p_expected_gain NUMERIC,
    p_retrieval_cost NUMERIC,
    p_entropy_threshold NUMERIC DEFAULT 0.10,
    p_gain_cost_threshold NUMERIC DEFAULT 1.0
)
RETURNS JSONB AS $$
DECLARE
    v_entropy_delta NUMERIC;
    v_gain_cost_ratio NUMERIC;
    v_should_stop BOOLEAN := FALSE;
    v_reason TEXT := 'CONTINUED';
BEGIN
    -- Calculate entropy delta
    IF p_previous_entropy IS NOT NULL THEN
        v_entropy_delta := p_current_entropy - p_previous_entropy;
    ELSE
        v_entropy_delta := 1.0;  -- First step, don't stop
    END IF;

    -- Calculate gain/cost ratio
    IF p_retrieval_cost > 0 THEN
        v_gain_cost_ratio := p_expected_gain / p_retrieval_cost;
    ELSE
        v_gain_cost_ratio := 0;
    END IF;

    -- Check stopping conditions
    IF ABS(v_entropy_delta) < p_entropy_threshold THEN
        v_should_stop := TRUE;
        v_reason := 'ENTROPY_CONVERGED';
    ELSIF v_gain_cost_ratio < p_gain_cost_threshold THEN
        v_should_stop := TRUE;
        v_reason := 'COST_EXCEEDED';
    END IF;

    RETURN jsonb_build_object(
        'should_stop', v_should_stop,
        'reason', v_reason,
        'entropy_delta', v_entropy_delta,
        'gain_cost_ratio', v_gain_cost_ratio
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Calculate UCB exploration bonus
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.calculate_ucb_bonus(
    p_source_name TEXT,
    p_regime_id TEXT,
    p_total_retrievals INTEGER,
    p_exploration_weight NUMERIC DEFAULT 2.0
)
RETURNS NUMERIC AS $$
DECLARE
    v_source_count INTEGER;
    v_ucb_bonus NUMERIC;
BEGIN
    -- Count how many times this source has been used in this regime
    SELECT COUNT(*)
    INTO v_source_count
    FROM fhq_research.signal_yield_tracking
    WHERE source_name = p_source_name
      AND regime_id = p_regime_id
      AND created_at > NOW() - INTERVAL '7 days';

    -- UCB formula: sqrt(2 * ln(total) / source_count)
    IF v_source_count = 0 THEN
        -- Never used, high exploration bonus
        RETURN 1.0;
    ELSIF p_total_retrievals > 0 THEN
        v_ucb_bonus := p_exploration_weight * SQRT(
            2.0 * LN(p_total_retrievals::NUMERIC) / v_source_count
        );
        RETURN LEAST(1.0, v_ucb_bonus);  -- Cap at 1.0
    ELSE
        RETURN 0.5;  -- Default moderate bonus
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Update batch retrieval efficiency summary
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.update_retrieval_efficiency_summary(
    p_batch_id TEXT
)
RETURNS VOID AS $$
DECLARE
    v_metrics RECORD;
BEGIN
    -- Calculate aggregated metrics
    SELECT
        COUNT(DISTINCT run_id) as total_runs,
        COUNT(*) as total_steps,
        COUNT(*) FILTER (WHERE actual_stopped) as early_stopped,
        AVG(current_entropy) as avg_entropy,
        AVG(ABS(entropy_delta)) FILTER (WHERE entropy_delta IS NOT NULL) as avg_delta,
        COUNT(*) FILTER (WHERE stop_reason = 'ENTROPY_CONVERGED') as entropy_converged,
        COUNT(*) FILTER (WHERE stop_reason = 'COST_EXCEEDED') as cost_exceeded,
        COUNT(*) FILTER (WHERE stop_reason = 'MAX_STEPS_REACHED') as max_steps,
        COUNT(*) FILTER (WHERE stop_reason = 'CONFIDENCE_ACHIEVED') as confidence_achieved
    INTO v_metrics
    FROM fhq_research.entropy_stopping_log
    WHERE batch_id = p_batch_id;

    -- Upsert summary record
    INSERT INTO fhq_research.retrieval_efficiency_batch_summary (
        batch_id,
        batch_start_run,
        batch_end_run,
        total_runs,
        total_retrieval_steps,
        early_stopped_runs,
        avg_final_entropy,
        avg_entropy_delta,
        entropy_converged_count,
        cost_exceeded_count,
        max_steps_count,
        confidence_achieved_count,
        updated_at
    ) VALUES (
        p_batch_id,
        101,
        200,
        v_metrics.total_runs,
        v_metrics.total_steps,
        v_metrics.early_stopped,
        v_metrics.avg_entropy,
        v_metrics.avg_delta,
        v_metrics.entropy_converged,
        v_metrics.cost_exceeded,
        v_metrics.max_steps,
        v_metrics.confidence_achieved,
        NOW()
    )
    ON CONFLICT (batch_id) DO UPDATE SET
        total_runs = EXCLUDED.total_runs,
        total_retrieval_steps = EXCLUDED.total_retrieval_steps,
        early_stopped_runs = EXCLUDED.early_stopped_runs,
        avg_final_entropy = EXCLUDED.avg_final_entropy,
        avg_entropy_delta = EXCLUDED.avg_entropy_delta,
        entropy_converged_count = EXCLUDED.entropy_converged_count,
        cost_exceeded_count = EXCLUDED.cost_exceeded_count,
        max_steps_count = EXCLUDED.max_steps_count,
        confidence_achieved_count = EXCLUDED.confidence_achieved_count,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEW: Entropy Stopping Effectiveness
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_entropy_stopping_effectiveness AS
SELECT
    batch_id,
    COUNT(DISTINCT run_id) as total_runs,
    COUNT(*) as total_steps,
    ROUND(COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT run_id), 0), 2) as avg_steps_per_run,
    COUNT(*) FILTER (WHERE actual_stopped) as early_stopped,
    ROUND(
        COUNT(*) FILTER (WHERE actual_stopped)::NUMERIC /
        NULLIF(COUNT(DISTINCT run_id), 0),
        4
    ) as early_stop_rate,
    ROUND(AVG(current_entropy), 4) as avg_final_entropy,
    ROUND(AVG(ABS(entropy_delta)) FILTER (WHERE entropy_delta IS NOT NULL), 4) as avg_entropy_delta
FROM fhq_research.entropy_stopping_log
GROUP BY batch_id
ORDER BY batch_id;

-- ============================================================================
-- VIEW: Active Inference Loop Summary
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_active_inference_summary AS
SELECT
    batch_id,
    COUNT(*) as total_inferences,
    COUNT(*) FILTER (WHERE final_loop_used = 'FAST') as fast_only,
    COUNT(*) FILTER (WHERE slow_loop_activated) as slow_activated,
    ROUND(
        COUNT(*) FILTER (WHERE final_loop_used = 'FAST')::NUMERIC /
        NULLIF(COUNT(*), 0),
        4
    ) as fast_resolution_rate,
    ROUND(AVG(fast_loop_duration_ms), 0) as avg_fast_duration_ms,
    ROUND(AVG(slow_loop_duration_ms) FILTER (WHERE slow_loop_activated), 0) as avg_slow_duration_ms,
    ROUND(AVG(fast_loop_cache_hits), 2) as avg_cache_hits,
    COUNT(*) FILTER (WHERE external_data_requested) as external_requests
FROM fhq_research.active_inference_loop_log
GROUP BY batch_id
ORDER BY batch_id;

-- ============================================================================
-- APPEND-ONLY ENFORCEMENT (Per CEO-DIR-2026-FINN-006)
-- ============================================================================

-- Entropy stopping log - append only
DROP TRIGGER IF EXISTS trg_append_only_entropy ON fhq_research.entropy_stopping_log;
CREATE TRIGGER trg_append_only_entropy
    BEFORE UPDATE OR DELETE ON fhq_research.entropy_stopping_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only();

-- Active inference loop log - append only
DROP TRIGGER IF EXISTS trg_append_only_inference ON fhq_research.active_inference_loop_log;
CREATE TRIGGER trg_append_only_inference
    BEFORE UPDATE OR DELETE ON fhq_research.active_inference_loop_log
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only();

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
    '183_finn007_entropy_based_stopping',
    'DATABASE_MIGRATION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-FINN-007 Section 3.2: Entropy-Based Stopping Protocol',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-FINN-007',
        'section', '3.2 Entropy-Based Stopping',
        'tables', ARRAY['entropy_stopping_log', 'retrieval_efficiency_batch_summary', 'active_inference_loop_log'],
        'research_basis', 'UCB Pandora Box (2025), Active Inference AI Systems (2025)',
        'purpose', 'Stop retrieval when expected gain falls below threshold, implement dual-process architecture',
        'target', '20% retrieval reduction vs Batch 1'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'entropy_stopping_log'
    ) THEN
        RAISE EXCEPTION 'Migration 183 FAILED: entropy_stopping_log not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'active_inference_loop_log'
    ) THEN
        RAISE EXCEPTION 'Migration 183 FAILED: active_inference_loop_log not created';
    END IF;

    RAISE NOTICE 'Migration 183 SUCCESS: Entropy-based stopping infrastructure created';
    RAISE NOTICE 'CEO-DIR-2026-FINN-007: Target 20%% retrieval reduction vs Batch 1';
END $$;
