-- Migration 184: Regime-Aware Path Weighting Infrastructure
-- CEO-DIR-2026-FINN-007: Operation Freedom 2026 - Batch 2
-- Section 3.1: Regime-Aware Path Weighting Protocol
--
-- Purpose: Implement dynamic ontology path weighting based on historical
-- performance within each regime. Down-weight low-yield paths, up-weight
-- high-yield paths, within Safe-Bounds.
--
-- Research Basis: MetaAgent (2025) - Meta-tool learning
-- "Self-reflection and meta-tool learning driven by metacognitive theory;
-- agent evaluates performance of each tool and integrates lessons"
--
-- Authority: CEO-DIR-2026-FINN-007
-- Owner: EC-020 (SitC)
-- Classification: LEARNING_INFRASTRUCTURE
-- Safe-Bounds: Down-weight up to 40%, Up-weight up to 20%

BEGIN;

-- ============================================================================
-- TABLE: ontology_path_weights
-- Tracks current weight for each ontology path per regime
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.ontology_path_weights (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Path identification
    ontology_path           TEXT[] NOT NULL,       -- Array representing path hierarchy
    path_hash               TEXT NOT NULL,         -- Computed on insert via trigger
    domain                  TEXT,                  -- e.g., MACRO, CRYPTO, EQUITY
    concept_id              UUID,

    -- Regime binding
    regime_id               TEXT NOT NULL,

    -- Weights
    base_weight             NUMERIC(5,4) DEFAULT 0.50,  -- Starting weight
    current_weight          NUMERIC(5,4) DEFAULT 0.50,  -- Active weight

    -- Safe-Bounds enforcement
    min_weight              NUMERIC(5,4) DEFAULT 0.10,  -- Cannot go below
    max_weight              NUMERIC(5,4) DEFAULT 0.70,  -- Cannot go above

    -- Performance metrics (rolling 50-run window)
    total_retrievals        INTEGER DEFAULT 0,
    total_used              INTEGER DEFAULT 0,
    yield_trend             TEXT CHECK (yield_trend IN (
                                'IMPROVING', 'STABLE', 'DECLINING', 'UNKNOWN'
                            )) DEFAULT 'UNKNOWN',

    -- Last adjustment
    last_adjusted_run       INTEGER,
    last_adjusted_at        TIMESTAMPTZ,
    adjustment_count        INTEGER DEFAULT 0,

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ,

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007',

    -- Unique constraint per path/regime
    CONSTRAINT uq_path_regime UNIQUE (path_hash, regime_id)
);

-- ============================================================================
-- FUNCTION: Compute path_hash on insert
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.compute_path_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.path_hash := MD5(ARRAY_TO_STRING(NEW.ontology_path, '::'));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_compute_path_hash ON fhq_research.ontology_path_weights;
CREATE TRIGGER trg_compute_path_hash
    BEFORE INSERT OR UPDATE OF ontology_path ON fhq_research.ontology_path_weights
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.compute_path_hash();

-- ============================================================================
-- TABLE: path_weight_adjustments
-- Audit log of all weight adjustments (append-only)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.path_weight_adjustments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Adjustment identification
    weight_id               UUID NOT NULL REFERENCES fhq_research.ontology_path_weights(id),
    run_number              INTEGER NOT NULL,      -- Run that triggered adjustment
    batch_id                TEXT,
    adjustment_window       INTEGER DEFAULT 50,    -- Runs analyzed

    -- Weight change
    previous_weight         NUMERIC(5,4) NOT NULL,
    new_weight              NUMERIC(5,4) NOT NULL,
    adjustment_type         TEXT CHECK (adjustment_type IN (
                                'DOWN_WEIGHT',     -- Reduced due to low yield
                                'UP_WEIGHT',       -- Increased due to high yield
                                'RESET',           -- Reset to base
                                'VEGA_OVERRIDE'    -- Manual VEGA intervention
                            )),

    -- Safe-Bounds check
    requested_amount        NUMERIC(5,4),          -- What was requested
    capped                  BOOLEAN DEFAULT FALSE, -- Was request capped?
    cap_reason              TEXT,                  -- Why capped (if applicable)

    -- Performance data supporting adjustment
    window_retrievals       INTEGER,               -- Total retrievals in window
    window_used             INTEGER,               -- Items actually used
    window_yield            NUMERIC(5,4),          -- Yield ratio in window
    yield_threshold_low     NUMERIC(5,4) DEFAULT 0.30,  -- Below this = down-weight
    yield_threshold_high    NUMERIC(5,4) DEFAULT 0.60,  -- Above this = up-weight

    -- Regime context
    regime_id               TEXT NOT NULL,
    regime_confidence       NUMERIC(5,4),

    -- Approval status
    status                  TEXT DEFAULT 'APPLIED' CHECK (status IN (
                                'APPLIED',              -- Within Safe-Bounds, auto-applied
                                'ADVISORY_PENDING_VEGA', -- Exceeded Safe-Bounds
                                'VEGA_APPROVED',        -- VEGA approved override
                                'REJECTED'              -- VEGA rejected
                            )),

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007'
);

-- ============================================================================
-- TABLE: path_yield_history
-- Tracks yield per path over time for trend analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_research.path_yield_history (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Path identification
    weight_id               UUID NOT NULL REFERENCES fhq_research.ontology_path_weights(id),
    ontology_path           TEXT[] NOT NULL,
    regime_id               TEXT NOT NULL,

    -- Window metrics
    window_start_run        INTEGER NOT NULL,
    window_end_run          INTEGER NOT NULL,
    retrievals_in_window    INTEGER NOT NULL,
    used_in_window          INTEGER NOT NULL,
    yield_ratio             NUMERIC(5,4) NOT NULL,

    -- Comparison
    previous_yield          NUMERIC(5,4),
    yield_delta             NUMERIC(5,4),

    -- Timestamps
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Governance
    directive_ref           TEXT DEFAULT 'CEO-DIR-2026-FINN-007'
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Path weights
CREATE INDEX IF NOT EXISTS idx_path_weights_regime ON fhq_research.ontology_path_weights(regime_id);
CREATE INDEX IF NOT EXISTS idx_path_weights_hash ON fhq_research.ontology_path_weights(path_hash);

-- Weight adjustments
CREATE INDEX IF NOT EXISTS idx_adjustments_weight ON fhq_research.path_weight_adjustments(weight_id);
CREATE INDEX IF NOT EXISTS idx_adjustments_batch ON fhq_research.path_weight_adjustments(batch_id);
CREATE INDEX IF NOT EXISTS idx_adjustments_pending ON fhq_research.path_weight_adjustments(status)
    WHERE status = 'ADVISORY_PENDING_VEGA';

-- Yield history
CREATE INDEX IF NOT EXISTS idx_yield_history_weight ON fhq_research.path_yield_history(weight_id);

-- ============================================================================
-- FUNCTION: Get current path weight
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.get_path_weight(
    p_ontology_path TEXT[],
    p_regime_id TEXT
)
RETURNS NUMERIC AS $$
DECLARE
    v_weight NUMERIC;
BEGIN
    SELECT current_weight INTO v_weight
    FROM fhq_research.ontology_path_weights
    WHERE path_hash = MD5(ARRAY_TO_STRING(p_ontology_path, '::'))
      AND regime_id = p_regime_id;

    -- Return default if not found
    RETURN COALESCE(v_weight, 0.50);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Calculate weight adjustment within Safe-Bounds
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.calculate_weight_adjustment(
    p_current_weight NUMERIC,
    p_yield_ratio NUMERIC,
    p_yield_threshold_low NUMERIC DEFAULT 0.30,
    p_yield_threshold_high NUMERIC DEFAULT 0.60,
    p_max_down_weight NUMERIC DEFAULT 0.40,  -- Maximum 40% reduction
    p_max_up_weight NUMERIC DEFAULT 0.20     -- Maximum 20% increase
)
RETURNS JSONB AS $$
DECLARE
    v_adjustment NUMERIC := 0;
    v_adjustment_type TEXT := 'NONE';
    v_new_weight NUMERIC;
    v_capped BOOLEAN := FALSE;
    v_cap_reason TEXT;
BEGIN
    -- Determine adjustment based on yield
    IF p_yield_ratio < p_yield_threshold_low THEN
        -- Low yield: down-weight proportionally
        v_adjustment := -1 * (p_yield_threshold_low - p_yield_ratio) * 0.5;
        v_adjustment_type := 'DOWN_WEIGHT';
    ELSIF p_yield_ratio > p_yield_threshold_high THEN
        -- High yield: up-weight proportionally
        v_adjustment := (p_yield_ratio - p_yield_threshold_high) * 0.3;
        v_adjustment_type := 'UP_WEIGHT';
    END IF;

    -- Calculate proposed new weight
    v_new_weight := p_current_weight + v_adjustment;

    -- Apply Safe-Bounds
    IF v_adjustment_type = 'DOWN_WEIGHT' THEN
        -- Cannot reduce more than 40% from base (0.50)
        IF v_new_weight < 0.10 THEN
            v_new_weight := 0.10;
            v_capped := TRUE;
            v_cap_reason := 'MIN_WEIGHT_FLOOR (Safe-Bounds 40% reduction limit)';
        END IF;
    ELSIF v_adjustment_type = 'UP_WEIGHT' THEN
        -- Cannot increase more than 20% from base (0.50)
        IF v_new_weight > 0.70 THEN
            v_new_weight := 0.70;
            v_capped := TRUE;
            v_cap_reason := 'MAX_WEIGHT_CEILING (Safe-Bounds 20% increase limit)';
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'adjustment_type', v_adjustment_type,
        'requested_adjustment', v_adjustment,
        'new_weight', ROUND(v_new_weight, 4),
        'capped', v_capped,
        'cap_reason', v_cap_reason
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Apply path weight adjustment
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.apply_path_weight_adjustment(
    p_ontology_path TEXT[],
    p_regime_id TEXT,
    p_run_number INTEGER,
    p_batch_id TEXT,
    p_window_retrievals INTEGER,
    p_window_used INTEGER
)
RETURNS JSONB AS $$
DECLARE
    v_weight_id UUID;
    v_current_weight NUMERIC;
    v_yield_ratio NUMERIC;
    v_adjustment JSONB;
    v_status TEXT;
    v_path_hash TEXT;
BEGIN
    -- Calculate yield ratio
    IF p_window_retrievals > 0 THEN
        v_yield_ratio := p_window_used::NUMERIC / p_window_retrievals;
    ELSE
        v_yield_ratio := 0.50;
    END IF;

    -- Compute path hash
    v_path_hash := MD5(ARRAY_TO_STRING(p_ontology_path, '::'));

    -- Get or create weight record
    INSERT INTO fhq_research.ontology_path_weights (
        ontology_path, path_hash, regime_id, total_retrievals, total_used
    ) VALUES (
        p_ontology_path, v_path_hash, p_regime_id, p_window_retrievals, p_window_used
    )
    ON CONFLICT (path_hash, regime_id) DO UPDATE SET
        total_retrievals = fhq_research.ontology_path_weights.total_retrievals + p_window_retrievals,
        total_used = fhq_research.ontology_path_weights.total_used + p_window_used,
        updated_at = NOW()
    RETURNING id, current_weight INTO v_weight_id, v_current_weight;

    -- Calculate adjustment
    v_adjustment := fhq_research.calculate_weight_adjustment(
        v_current_weight, v_yield_ratio
    );

    -- Determine status
    IF (v_adjustment->>'capped')::BOOLEAN THEN
        v_status := 'ADVISORY_PENDING_VEGA';
    ELSE
        v_status := 'APPLIED';
    END IF;

    -- Apply adjustment (if within bounds)
    IF v_status = 'APPLIED' AND (v_adjustment->>'adjustment_type') != 'NONE' THEN
        UPDATE fhq_research.ontology_path_weights
        SET current_weight = (v_adjustment->>'new_weight')::NUMERIC,
            last_adjusted_run = p_run_number,
            last_adjusted_at = NOW(),
            adjustment_count = adjustment_count + 1,
            updated_at = NOW()
        WHERE id = v_weight_id;
    END IF;

    -- Log adjustment
    INSERT INTO fhq_research.path_weight_adjustments (
        weight_id, run_number, batch_id,
        previous_weight, new_weight, adjustment_type,
        requested_amount, capped, cap_reason,
        window_retrievals, window_used, window_yield,
        regime_id, status
    ) VALUES (
        v_weight_id, p_run_number, p_batch_id,
        v_current_weight, (v_adjustment->>'new_weight')::NUMERIC,
        v_adjustment->>'adjustment_type',
        (v_adjustment->>'requested_adjustment')::NUMERIC,
        (v_adjustment->>'capped')::BOOLEAN,
        v_adjustment->>'cap_reason',
        p_window_retrievals, p_window_used, v_yield_ratio,
        p_regime_id, v_status
    );

    RETURN jsonb_build_object(
        'weight_id', v_weight_id,
        'previous_weight', v_current_weight,
        'new_weight', v_adjustment->>'new_weight',
        'adjustment_type', v_adjustment->>'adjustment_type',
        'yield_ratio', v_yield_ratio,
        'status', v_status,
        'capped', v_adjustment->>'capped'
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: Batch weight recalculation (every 50 runs)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.recalculate_batch_weights(
    p_batch_id TEXT,
    p_run_number INTEGER
)
RETURNS TABLE (
    ontology_path TEXT[],
    regime_id TEXT,
    previous_weight NUMERIC,
    new_weight NUMERIC,
    adjustment_type TEXT,
    status TEXT
) AS $$
DECLARE
    v_path_regime RECORD;
    v_result JSONB;
BEGIN
    -- Get all paths with activity in the last 50 runs
    FOR v_path_regime IN
        SELECT DISTINCT
            rel.ontology_path,
            rel.regime_id,
            SUM(rel.total_items_retrieved) as window_retrievals,
            SUM(rel.verified_items_used) as window_used
        FROM fhq_research.retrieval_efficiency_log rel
        WHERE rel.run_number > p_run_number - 50
          AND rel.run_number <= p_run_number
        GROUP BY rel.ontology_path, rel.regime_id
    LOOP
        -- Apply adjustment for each path/regime
        v_result := fhq_research.apply_path_weight_adjustment(
            v_path_regime.ontology_path,
            v_path_regime.regime_id,
            p_run_number,
            p_batch_id,
            v_path_regime.window_retrievals,
            v_path_regime.window_used
        );

        -- Return result
        ontology_path := v_path_regime.ontology_path;
        regime_id := v_path_regime.regime_id;
        previous_weight := (v_result->>'previous_weight')::NUMERIC;
        new_weight := (v_result->>'new_weight')::NUMERIC;
        adjustment_type := v_result->>'adjustment_type';
        status := v_result->>'status';
        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEW: Path Weight Summary
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_path_weight_summary AS
SELECT
    opw.regime_id,
    opw.ontology_path,
    opw.domain,
    opw.base_weight,
    opw.current_weight,
    opw.current_weight - opw.base_weight as weight_delta,
    CASE WHEN opw.total_retrievals > 0
         THEN ROUND(opw.total_used::NUMERIC / opw.total_retrievals, 4)
         ELSE 0.50
    END as yield_ratio,
    opw.yield_trend,
    opw.total_retrievals,
    opw.total_used,
    opw.adjustment_count,
    opw.last_adjusted_run,
    CASE
        WHEN opw.total_retrievals > 0 AND (opw.total_used::NUMERIC / opw.total_retrievals) < 0.30 THEN 'LOW_YIELD'
        WHEN opw.total_retrievals > 0 AND (opw.total_used::NUMERIC / opw.total_retrievals) > 0.60 THEN 'HIGH_YIELD'
        ELSE 'NORMAL'
    END as yield_status,
    opw.current_weight <= 0.10 OR opw.current_weight >= 0.70 as weight_capped
FROM fhq_research.ontology_path_weights opw
ORDER BY
    CASE WHEN opw.total_retrievals > 0
         THEN opw.total_used::NUMERIC / opw.total_retrievals
         ELSE 0.50
    END ASC;

-- ============================================================================
-- VIEW: Pending VEGA Approvals
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_pending_vega_approvals AS
SELECT
    pwa.id,
    pwa.batch_id,
    pwa.run_number,
    opw.ontology_path,
    pwa.regime_id,
    pwa.previous_weight,
    pwa.new_weight,
    pwa.adjustment_type,
    pwa.requested_amount,
    pwa.cap_reason,
    pwa.window_yield,
    pwa.created_at
FROM fhq_research.path_weight_adjustments pwa
JOIN fhq_research.ontology_path_weights opw ON pwa.weight_id = opw.id
WHERE pwa.status = 'ADVISORY_PENDING_VEGA'
ORDER BY pwa.created_at DESC;

-- ============================================================================
-- VIEW: Low-Yield Path Hotspots
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_low_yield_hotspots AS
SELECT
    regime_id,
    ontology_path,
    domain,
    current_weight,
    CASE WHEN total_retrievals > 0
         THEN ROUND(total_used::NUMERIC / total_retrievals, 4)
         ELSE 0
    END as yield_ratio,
    total_retrievals,
    total_used,
    total_retrievals - total_used as wasted_retrievals,
    adjustment_count
FROM fhq_research.ontology_path_weights
WHERE total_retrievals > 0
  AND (total_used::NUMERIC / total_retrievals) < 0.30
  AND total_retrievals >= 5  -- Minimum sample size
ORDER BY (total_used::NUMERIC / total_retrievals) ASC, (total_retrievals - total_used) DESC;

-- ============================================================================
-- APPEND-ONLY ENFORCEMENT (Per CEO-DIR-2026-FINN-006)
-- NOTE: ontology_path_weights allows UPDATE for weight adjustments
-- path_weight_adjustments and path_yield_history are append-only
-- ============================================================================

-- Path weight adjustments - append only
DROP TRIGGER IF EXISTS trg_append_only_path_adj ON fhq_research.path_weight_adjustments;
CREATE TRIGGER trg_append_only_path_adj
    BEFORE UPDATE OR DELETE ON fhq_research.path_weight_adjustments
    FOR EACH ROW
    EXECUTE FUNCTION fhq_research.enforce_append_only();

-- Yield history - append only
DROP TRIGGER IF EXISTS trg_append_only_yield_hist ON fhq_research.path_yield_history;
CREATE TRIGGER trg_append_only_yield_hist
    BEFORE UPDATE OR DELETE ON fhq_research.path_yield_history
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
    '184_finn007_regime_aware_path_weighting',
    'DATABASE_MIGRATION',
    'STIG',
    'APPROVED',
    'CEO-DIR-2026-FINN-007 Section 3.1: Regime-Aware Path Weighting Protocol',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-FINN-007',
        'section', '3.1 Regime-Aware Path Weighting',
        'tables', ARRAY['ontology_path_weights', 'path_weight_adjustments', 'path_yield_history'],
        'research_basis', 'MetaAgent (2025) - Meta-tool learning',
        'safe_bounds', jsonb_build_object(
            'max_down_weight', '40%',
            'max_up_weight', '20%',
            'min_weight', 0.10,
            'max_weight', 0.70
        ),
        'cadence', 'Every 50 runs'
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
        AND table_name = 'ontology_path_weights'
    ) THEN
        RAISE EXCEPTION 'Migration 184 FAILED: ontology_path_weights not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'fhq_research'
        AND table_name = 'path_weight_adjustments'
    ) THEN
        RAISE EXCEPTION 'Migration 184 FAILED: path_weight_adjustments not created';
    END IF;

    RAISE NOTICE 'Migration 184 SUCCESS: Regime-aware path weighting infrastructure created';
    RAISE NOTICE 'CEO-DIR-2026-FINN-007: Safe-Bounds = Down 40%% / Up 20%% per regime';
END $$;
