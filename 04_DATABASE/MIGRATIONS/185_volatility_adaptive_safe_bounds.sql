-- ============================================================================
-- MIGRATION 185: Volatility-Adaptive Safe Bounds
-- CEO-DIR-2026-FINN-008: Operation Freedom 2026 - Phase 2: Adaptivity
-- ============================================================================
--
-- PURPOSE:
--   Implement dynamic safe-bounds that adjust based on regime volatility.
--   Enable autonomous learning within governance-controlled limits.
--
-- VOLATILITY QUARTILES:
--   Q1 (Low):      max_down=20%, max_up=10%  (conservative)
--   Q2-Q3 (Medium): max_down=40%, max_up=20%  (standard)
--   Q4 (High):     max_down=50%, max_up=30%  (aggressive)
--   EXTREME:       FREEZE all adjustments (DEFCON ORANGE/RED)
--
-- DEPENDENCIES:
--   - Migration 184 (ontology_path_weights)
--   - IoS-003 (regime detection)
--   - ADR-016 (DEFCON protocol)
--
-- ============================================================================

-- 1. Volatility quartile configuration table
CREATE TABLE IF NOT EXISTS fhq_research.volatility_safe_bounds (
    quartile_id TEXT PRIMARY KEY,
    percentile_min NUMERIC(5,2) NOT NULL,
    percentile_max NUMERIC(5,2) NOT NULL,
    max_down_weight NUMERIC(3,2) NOT NULL,
    max_up_weight NUMERIC(3,2) NOT NULL,
    learning_rate_multiplier NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
    human_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert the CEO-DIR-008 defined quartiles
INSERT INTO fhq_research.volatility_safe_bounds
    (quartile_id, percentile_min, percentile_max, max_down_weight, max_up_weight,
     learning_rate_multiplier, is_frozen, human_review_required, description)
VALUES
    ('Q1_LOW', 0, 25, 0.20, 0.10, 0.5, FALSE, FALSE,
     'Low volatility: Conservative. Overfitting risk high.'),
    ('Q2_Q3_MEDIUM', 25, 75, 0.40, 0.20, 1.0, FALSE, FALSE,
     'Medium volatility: Standard CEO-DIR-007 bounds.'),
    ('Q4_HIGH', 75, 95, 0.50, 0.30, 1.5, FALSE, FALSE,
     'High volatility: Aggressive adaptation permitted.'),
    ('EXTREME_DEFCON', 95, 100, 0.00, 0.00, 0.0, TRUE, TRUE,
     'DEFCON ORANGE/RED: All adjustments frozen.')
ON CONFLICT (quartile_id) DO UPDATE SET
    max_down_weight = EXCLUDED.max_down_weight,
    max_up_weight = EXCLUDED.max_up_weight,
    learning_rate_multiplier = EXCLUDED.learning_rate_multiplier,
    updated_at = NOW();

-- 2. Volatility assessment log (append-only)
CREATE TABLE IF NOT EXISTS fhq_research.volatility_assessment_log (
    assessment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    batch_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,

    -- Volatility metrics
    current_volatility NUMERIC(10,6),
    volatility_percentile NUMERIC(5,2),
    assigned_quartile TEXT REFERENCES fhq_research.volatility_safe_bounds(quartile_id),

    -- Effective bounds for this assessment
    effective_max_down NUMERIC(3,2) NOT NULL,
    effective_max_up NUMERIC(3,2) NOT NULL,
    effective_learning_rate NUMERIC(3,2) NOT NULL,

    -- Source data
    regime_id TEXT,
    regime_confidence NUMERIC(5,4),
    vix_proxy NUMERIC(10,4),
    defcon_level TEXT,

    -- Audit
    is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
    freeze_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_vol_assessment_batch
    ON fhq_research.volatility_assessment_log(batch_id, run_number);
CREATE INDEX IF NOT EXISTS idx_vol_assessment_quartile
    ON fhq_research.volatility_assessment_log(assigned_quartile);

-- 3. Path euthanasia tracking table
CREATE TABLE IF NOT EXISTS fhq_research.path_euthanasia_tracking (
    tracking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path_hash TEXT NOT NULL,
    ontology_path TEXT[] NOT NULL,

    -- Yield tracking
    checkpoint_1_yield NUMERIC(5,4),
    checkpoint_1_date TIMESTAMPTZ,
    checkpoint_2_yield NUMERIC(5,4),
    checkpoint_2_date TIMESTAMPTZ,
    checkpoint_3_yield NUMERIC(5,4),
    checkpoint_3_date TIMESTAMPTZ,

    -- Status
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'WARNING', 'QUARANTINE', 'EUTHANIZED')),
    consecutive_low_yield_count INTEGER NOT NULL DEFAULT 0,

    -- Lifecycle
    quarantined_at TIMESTAMPTZ,
    quarantined_by TEXT,
    euthanized_at TIMESTAMPTZ,
    euthanized_by TEXT,
    reactivated_at TIMESTAMPTZ,
    reactivated_by TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_path_euthanasia_hash
    ON fhq_research.path_euthanasia_tracking(path_hash);

-- 4. Stop-loss checkpoint log
CREATE TABLE IF NOT EXISTS fhq_research.learning_stop_loss_log (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checkpoint_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    batch_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,

    -- Metrics at checkpoint
    retrieval_discipline NUMERIC(5,4) NOT NULL,
    threshold NUMERIC(5,4) NOT NULL,
    passed BOOLEAN NOT NULL,

    -- Action taken
    action TEXT NOT NULL CHECK (action IN (
        'CONTINUE', 'PAUSE_AND_REVIEW', 'RECALIBRATE_HEURISTICS', 'CEO_ESCALATION'
    )),
    escalation_to TEXT,

    -- Resolution
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT
);

-- 5. Function to get current volatility quartile
CREATE OR REPLACE FUNCTION fhq_research.get_current_volatility_quartile(
    p_volatility_percentile NUMERIC DEFAULT NULL
)
RETURNS TABLE (
    quartile_id TEXT,
    max_down_weight NUMERIC,
    max_up_weight NUMERIC,
    learning_rate_multiplier NUMERIC,
    is_frozen BOOLEAN
) AS $$
DECLARE
    v_percentile NUMERIC;
    v_defcon TEXT;
BEGIN
    -- Check DEFCON status first
    SELECT current_level INTO v_defcon
    FROM fhq_monitoring.defcon_status
    WHERE is_active = TRUE
    ORDER BY activated_at DESC
    LIMIT 1;

    -- If DEFCON ORANGE or RED, return frozen bounds
    IF v_defcon IN ('ORANGE', 'RED', 'BLACK') THEN
        RETURN QUERY
        SELECT vsb.quartile_id, vsb.max_down_weight, vsb.max_up_weight,
               vsb.learning_rate_multiplier, vsb.is_frozen
        FROM fhq_research.volatility_safe_bounds vsb
        WHERE vsb.quartile_id = 'EXTREME_DEFCON';
        RETURN;
    END IF;

    -- Use provided percentile or calculate from recent data
    IF p_volatility_percentile IS NOT NULL THEN
        v_percentile := p_volatility_percentile;
    ELSE
        -- Default to medium if no data available
        v_percentile := 50;
    END IF;

    -- Return matching quartile bounds
    RETURN QUERY
    SELECT vsb.quartile_id, vsb.max_down_weight, vsb.max_up_weight,
           vsb.learning_rate_multiplier, vsb.is_frozen
    FROM fhq_research.volatility_safe_bounds vsb
    WHERE v_percentile >= vsb.percentile_min
      AND v_percentile < vsb.percentile_max
    LIMIT 1;

    -- Fallback to medium if no match
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT vsb.quartile_id, vsb.max_down_weight, vsb.max_up_weight,
               vsb.learning_rate_multiplier, vsb.is_frozen
        FROM fhq_research.volatility_safe_bounds vsb
        WHERE vsb.quartile_id = 'Q2_Q3_MEDIUM';
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

-- 6. Function to check path euthanasia eligibility
CREATE OR REPLACE FUNCTION fhq_research.check_path_euthanasia(
    p_path_hash TEXT,
    p_current_yield NUMERIC
)
RETURNS TABLE (
    should_quarantine BOOLEAN,
    current_status TEXT,
    consecutive_failures INTEGER
) AS $$
DECLARE
    v_tracking RECORD;
    v_yield_threshold NUMERIC := 0.05;
    v_checkpoint_window INTEGER := 3;
BEGIN
    -- Get or create tracking record
    SELECT * INTO v_tracking
    FROM fhq_research.path_euthanasia_tracking pet
    WHERE pet.path_hash = p_path_hash;

    IF NOT FOUND THEN
        -- New path, create tracking
        INSERT INTO fhq_research.path_euthanasia_tracking (path_hash, ontology_path)
        VALUES (p_path_hash, ARRAY[p_path_hash])
        RETURNING * INTO v_tracking;
    END IF;

    -- Update yield history
    IF p_current_yield < v_yield_threshold THEN
        UPDATE fhq_research.path_euthanasia_tracking
        SET consecutive_low_yield_count = consecutive_low_yield_count + 1,
            checkpoint_3_yield = checkpoint_2_yield,
            checkpoint_3_date = checkpoint_2_date,
            checkpoint_2_yield = checkpoint_1_yield,
            checkpoint_2_date = checkpoint_1_date,
            checkpoint_1_yield = p_current_yield,
            checkpoint_1_date = NOW(),
            status = CASE
                WHEN consecutive_low_yield_count + 1 >= v_checkpoint_window THEN 'QUARANTINE'
                WHEN consecutive_low_yield_count + 1 >= 2 THEN 'WARNING'
                ELSE 'ACTIVE'
            END,
            quarantined_at = CASE
                WHEN consecutive_low_yield_count + 1 >= v_checkpoint_window THEN NOW()
                ELSE quarantined_at
            END,
            updated_at = NOW()
        WHERE path_hash = p_path_hash
        RETURNING * INTO v_tracking;
    ELSE
        -- Reset on good yield
        UPDATE fhq_research.path_euthanasia_tracking
        SET consecutive_low_yield_count = 0,
            status = 'ACTIVE',
            checkpoint_1_yield = p_current_yield,
            checkpoint_1_date = NOW(),
            updated_at = NOW()
        WHERE path_hash = p_path_hash
        RETURNING * INTO v_tracking;
    END IF;

    RETURN QUERY
    SELECT
        v_tracking.status = 'QUARANTINE',
        v_tracking.status,
        v_tracking.consecutive_low_yield_count;
END;
$$ LANGUAGE plpgsql;

-- 7. Function to evaluate stop-loss at checkpoint
CREATE OR REPLACE FUNCTION fhq_research.evaluate_stop_loss(
    p_batch_id TEXT,
    p_run_number INTEGER,
    p_retrieval_discipline NUMERIC
)
RETURNS TEXT AS $$
DECLARE
    v_threshold NUMERIC;
    v_action TEXT;
    v_escalation TEXT;
BEGIN
    -- Determine threshold based on run number
    v_threshold := CASE
        WHEN p_run_number >= 300 THEN 0.60
        WHEN p_run_number >= 250 THEN 0.55
        ELSE 0.45  -- No stop-loss before 250
    END;

    -- Determine action
    IF p_run_number < 250 THEN
        v_action := 'CONTINUE';
        v_escalation := NULL;
    ELSIF p_retrieval_discipline >= v_threshold THEN
        v_action := 'CONTINUE';
        v_escalation := NULL;
    ELSIF p_run_number >= 300 THEN
        v_action := 'CEO_ESCALATION';
        v_escalation := 'CEO';
    ELSE
        v_action := 'PAUSE_AND_REVIEW';
        v_escalation := 'CSEO + VEGA';
    END IF;

    -- Log the checkpoint
    INSERT INTO fhq_research.learning_stop_loss_log (
        batch_id, run_number, retrieval_discipline,
        threshold, passed, action, escalation_to
    ) VALUES (
        p_batch_id, p_run_number, p_retrieval_discipline,
        v_threshold, p_retrieval_discipline >= v_threshold,
        v_action, v_escalation
    );

    RETURN v_action;
END;
$$ LANGUAGE plpgsql;

-- 8. View: Current learning status dashboard
CREATE OR REPLACE VIEW fhq_research.learning_status_dashboard AS
SELECT
    -- Latest volatility assessment
    (SELECT assigned_quartile FROM fhq_research.volatility_assessment_log
     ORDER BY assessed_at DESC LIMIT 1) AS current_quartile,
    (SELECT effective_max_down FROM fhq_research.volatility_assessment_log
     ORDER BY assessed_at DESC LIMIT 1) AS current_max_down,
    (SELECT effective_max_up FROM fhq_research.volatility_assessment_log
     ORDER BY assessed_at DESC LIMIT 1) AS current_max_up,
    (SELECT is_frozen FROM fhq_research.volatility_assessment_log
     ORDER BY assessed_at DESC LIMIT 1) AS is_frozen,

    -- Path euthanasia stats
    (SELECT COUNT(*) FROM fhq_research.path_euthanasia_tracking
     WHERE status = 'ACTIVE') AS active_paths,
    (SELECT COUNT(*) FROM fhq_research.path_euthanasia_tracking
     WHERE status = 'WARNING') AS warning_paths,
    (SELECT COUNT(*) FROM fhq_research.path_euthanasia_tracking
     WHERE status = 'QUARANTINE') AS quarantined_paths,
    (SELECT COUNT(*) FROM fhq_research.path_euthanasia_tracking
     WHERE status = 'EUTHANIZED') AS euthanized_paths,

    -- Latest stop-loss status
    (SELECT action FROM fhq_research.learning_stop_loss_log
     ORDER BY checkpoint_at DESC LIMIT 1) AS last_stop_loss_action,
    (SELECT retrieval_discipline FROM fhq_research.learning_stop_loss_log
     ORDER BY checkpoint_at DESC LIMIT 1) AS last_retrieval_discipline;

-- 9. Grant permissions
GRANT SELECT ON fhq_research.volatility_safe_bounds TO PUBLIC;
GRANT SELECT, INSERT ON fhq_research.volatility_assessment_log TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_research.path_euthanasia_tracking TO PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fhq_research.learning_stop_loss_log TO PUBLIC;
GRANT SELECT ON fhq_research.learning_status_dashboard TO PUBLIC;

-- 10. Migration metadata
COMMENT ON TABLE fhq_research.volatility_safe_bounds IS
    'CEO-DIR-2026-FINN-008: Volatility-adjusted safe bounds for autonomous learning';
COMMENT ON TABLE fhq_research.path_euthanasia_tracking IS
    'CEO-DIR-2026-FINN-008: Tracking for path quarantine and euthanasia protocol';
COMMENT ON TABLE fhq_research.learning_stop_loss_log IS
    'CEO-DIR-2026-FINN-008: Stop-loss checkpoints for learning loop';

-- ============================================================================
-- MIGRATION COMPLETE
-- Next: Execute Batch 3 with ACTIVE learning mode
-- ============================================================================
