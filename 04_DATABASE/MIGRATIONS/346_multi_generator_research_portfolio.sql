-- ============================================================================
-- MIGRATION 346: Multi-Generator Research Portfolio Infrastructure
-- CEO-DIR-2026-POR-001: Transition to Multi-Generator Research Portfolio
-- ============================================================================
-- Governing Authority: ADR-014, ADR-018 (ASRP), ADR-004, ADR-013, IoS-016
-- Executor: STIG (EC-003)
-- Classification: STRATEGIC-CRITICAL / GOVERNANCE-MANDATED
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 4.1: LEARNING PROVENANCE WIRING (P0)
-- ============================================================================

-- Generator Registry: defines the Research Trinity
CREATE TABLE IF NOT EXISTS fhq_learning.generator_registry (
    generator_id TEXT PRIMARY KEY,
    generator_name TEXT NOT NULL,
    generator_type TEXT NOT NULL CHECK (generator_type IN ('ERROR_REPAIR', 'WORLD_MODEL', 'SHADOW_DISCOVERY')),
    description TEXT NOT NULL,
    owner_ec TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PAUSED', 'RETIRED')),
    constraints JSONB NOT NULL DEFAULT '{}',
    target_causal_depth INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG'
);

COMMENT ON TABLE fhq_learning.generator_registry IS
'CEO-DIR-2026-POR-001 Section 3: FjordHQ Research Trinity generator definitions.
FINN-E (Error Repair), FINN-T (World-Model), GN-S (Shadow Discovery)';

-- Insert the Research Trinity generators
INSERT INTO fhq_learning.generator_registry (generator_id, generator_name, generator_type, description, owner_ec, target_causal_depth, constraints)
VALUES
    ('FINN-E', 'FINN Error Repair', 'ERROR_REPAIR',
     'Convert classified HIGH errors into falsification sweeps. Cannot be sole generator.',
     'EC-004', 1,
     '{"sole_generator_allowed": false, "input_source": "forecast_error_classification"}'::jsonb),
    ('FINN-T', 'FINN Theory/World-Model', 'WORLD_MODEL',
     'Generate hypotheses from validated macro/credit/liquidity/factor drivers (G3 Golden Features). Must include N-tier mechanism chains.',
     'EC-004', 2,
     '{"min_causal_depth": 2, "input_source": "g3_golden_features", "requires_mechanism_chain": true}'::jsonb),
    ('GN-S', 'Golden Needles Shadow', 'SHADOW_DISCOVERY',
     'Orthogonal discovery and Symmetry Watch benchmark. Shadow-tier only, no reward, no execution eligibility.',
     'EC-003', 2,
     '{"shadow_tier_only": true, "reward_coupling": false, "execution_eligibility": false, "purpose": "contrast_analysis"}'::jsonb)
ON CONFLICT (generator_id) DO NOTHING;

-- ============================================================================
-- SECTION 4.2: N-TIER CAUSAL GRAPH SUPPORT (P0)
-- ============================================================================

-- Add mechanism_graph column for N-tier causal chains
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS mechanism_graph JSONB DEFAULT NULL;

-- Add generator_id for provenance tracking
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS generator_id TEXT REFERENCES fhq_learning.generator_registry(generator_id);

-- Add input_artifacts_hash for provenance verification
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS input_artifacts_hash TEXT;

-- Add overfitting risk metrics columns
ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS trial_count INTEGER DEFAULT 0;

ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS parameter_search_breadth INTEGER DEFAULT 0;

ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS family_inflation_risk NUMERIC(5,4) DEFAULT NULL;

ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS deflated_sharpe_computed BOOLEAN DEFAULT FALSE;

ALTER TABLE fhq_learning.hypothesis_canon
ADD COLUMN IF NOT EXISTS pbo_probability NUMERIC(5,4) DEFAULT NULL;

COMMENT ON COLUMN fhq_learning.hypothesis_canon.mechanism_graph IS
'N-tier causal mechanism graph. FINN-T and GN-S must have depth >= 2';

COMMENT ON COLUMN fhq_learning.hypothesis_canon.generator_id IS
'FK to generator_registry. Required for provenance tracking (fail-closed on NULL for new writes)';

COMMENT ON COLUMN fhq_learning.hypothesis_canon.family_inflation_risk IS
'Multiple-testing inflation risk indicator. Required for promotion beyond Tier-1';

-- ============================================================================
-- HYPOTHESIS PROVENANCE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_learning.hypothesis_provenance (
    provenance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES fhq_learning.hypothesis_canon(canon_id),
    generator_id TEXT NOT NULL REFERENCES fhq_learning.generator_registry(generator_id),
    origin_type TEXT NOT NULL,
    input_artifacts JSONB NOT NULL,
    input_hash TEXT NOT NULL,
    causal_depth INTEGER NOT NULL DEFAULT 1,
    mechanism_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(hypothesis_id)
);

COMMENT ON TABLE fhq_learning.hypothesis_provenance IS
'CEO-DIR-2026-POR-001 Section 4.1: 100% provenance tracking. Every hypothesis must have generator_id + origin_type + input_hash';

-- ============================================================================
-- EXPERIMENT PROVENANCE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_learning.experiment_provenance (
    provenance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES fhq_learning.experiment_registry(experiment_id),
    source_hypothesis_id UUID REFERENCES fhq_learning.hypothesis_canon(canon_id),
    generator_id TEXT NOT NULL REFERENCES fhq_learning.generator_registry(generator_id),
    origin_type TEXT NOT NULL,
    input_artifacts JSONB NOT NULL,
    input_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(experiment_id)
);

COMMENT ON TABLE fhq_learning.experiment_provenance IS
'CEO-DIR-2026-POR-001 Section 4.1: Experiment provenance tracking';

-- ============================================================================
-- SECTION 4.3: ANTI-OVERFITTING GUARDRAIL PACK (P0)
-- ============================================================================

-- Promotion gate table for tracking advancement eligibility
CREATE TABLE IF NOT EXISTS fhq_learning.promotion_gate_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hypothesis_id UUID NOT NULL REFERENCES fhq_learning.hypothesis_canon(canon_id),
    gate_name TEXT NOT NULL,
    gate_result TEXT NOT NULL CHECK (gate_result IN ('PASS', 'FAIL', 'BLOCKED')),
    failure_reason TEXT,
    metrics_snapshot JSONB NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evaluated_by TEXT NOT NULL DEFAULT 'SYSTEM'
);

COMMENT ON TABLE fhq_learning.promotion_gate_audit IS
'CEO-DIR-2026-POR-001 Section 4.3: Anti-overfitting promotion gate audit trail';

-- Function to compute Deflated Sharpe Ratio style correction
CREATE OR REPLACE FUNCTION fhq_learning.compute_deflated_sharpe(
    p_hypothesis_id UUID
) RETURNS NUMERIC AS $$
DECLARE
    v_trial_count INTEGER;
    v_sharpe_estimate NUMERIC;
    v_deflation_factor NUMERIC;
    v_deflated_sharpe NUMERIC;
BEGIN
    SELECT trial_count, deflated_sharpe_estimate
    INTO v_trial_count, v_sharpe_estimate
    FROM fhq_learning.hypothesis_canon
    WHERE canon_id = p_hypothesis_id;

    IF v_trial_count IS NULL OR v_trial_count = 0 THEN
        v_trial_count := 1;
    END IF;

    -- Haircut formula: penalize for multiple trials
    -- Deflation increases with sqrt of trial count (Harvey et al. style)
    v_deflation_factor := 1.0 - (0.1 * sqrt(v_trial_count::NUMERIC));
    IF v_deflation_factor < 0.5 THEN
        v_deflation_factor := 0.5; -- Floor at 50% deflation
    END IF;

    v_deflated_sharpe := COALESCE(v_sharpe_estimate, 0) * v_deflation_factor;

    -- Update the hypothesis with computed value
    UPDATE fhq_learning.hypothesis_canon
    SET deflated_sharpe_computed = TRUE,
        deflated_sharpe_estimate = v_deflated_sharpe
    WHERE canon_id = p_hypothesis_id;

    RETURN v_deflated_sharpe;
END;
$$ LANGUAGE plpgsql;

-- Function to check promotion eligibility (fail-closed)
CREATE OR REPLACE FUNCTION fhq_learning.check_promotion_eligibility(
    p_hypothesis_id UUID
) RETURNS TABLE (
    eligible BOOLEAN,
    blocking_reasons TEXT[],
    metrics JSONB
) AS $$
DECLARE
    v_hypo RECORD;
    v_reasons TEXT[] := ARRAY[]::TEXT[];
    v_eligible BOOLEAN := TRUE;
    v_metrics JSONB;
BEGIN
    SELECT * INTO v_hypo
    FROM fhq_learning.hypothesis_canon
    WHERE canon_id = p_hypothesis_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, ARRAY['Hypothesis not found'], '{}'::JSONB;
        RETURN;
    END IF;

    -- Gate 1: Provenance must be known
    IF v_hypo.generator_id IS NULL THEN
        v_reasons := array_append(v_reasons, 'PROVENANCE_MISSING: generator_id is NULL');
        v_eligible := FALSE;
    END IF;

    -- Gate 2: Falsification criteria must exist and be reachable
    IF v_hypo.falsification_criteria IS NULL OR v_hypo.falsification_criteria = '{}'::JSONB THEN
        v_reasons := array_append(v_reasons, 'FALSIFICATION_MISSING: No falsification criteria defined');
        v_eligible := FALSE;
    END IF;

    -- Gate 3: Overfitting risk metrics must be computed
    IF v_hypo.family_inflation_risk IS NULL AND v_hypo.pbo_probability IS NULL THEN
        v_reasons := array_append(v_reasons, 'OVERFITTING_METRICS_MISSING: No inflation risk or PBO computed');
        v_eligible := FALSE;
    END IF;

    -- Gate 4: If inflation risk is too high, block
    IF v_hypo.family_inflation_risk IS NOT NULL AND v_hypo.family_inflation_risk > 0.30 THEN
        v_reasons := array_append(v_reasons, 'INFLATION_RISK_HIGH: family_inflation_risk > 0.30');
        v_eligible := FALSE;
    END IF;

    -- Gate 5: PBO probability check (if computed)
    IF v_hypo.pbo_probability IS NOT NULL AND v_hypo.pbo_probability > 0.50 THEN
        v_reasons := array_append(v_reasons, 'PBO_TOO_HIGH: Probability of backtest overfitting > 50%');
        v_eligible := FALSE;
    END IF;

    v_metrics := jsonb_build_object(
        'generator_id', v_hypo.generator_id,
        'causal_graph_depth', v_hypo.causal_graph_depth,
        'trial_count', v_hypo.trial_count,
        'family_inflation_risk', v_hypo.family_inflation_risk,
        'pbo_probability', v_hypo.pbo_probability,
        'deflated_sharpe_computed', v_hypo.deflated_sharpe_computed,
        'falsification_criteria_present', (v_hypo.falsification_criteria IS NOT NULL)
    );

    -- Log the audit
    INSERT INTO fhq_learning.promotion_gate_audit (
        hypothesis_id, gate_name, gate_result, failure_reason, metrics_snapshot
    ) VALUES (
        p_hypothesis_id,
        'PROMOTION_ELIGIBILITY_CHECK',
        CASE WHEN v_eligible THEN 'PASS' ELSE 'BLOCKED' END,
        CASE WHEN array_length(v_reasons, 1) > 0 THEN array_to_string(v_reasons, '; ') ELSE NULL END,
        v_metrics
    );

    RETURN QUERY SELECT v_eligible, v_reasons, v_metrics;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FAIL-CLOSED TRIGGER: Reject writes with NULL provenance (for new hypotheses)
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_learning.enforce_provenance_on_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Only enforce for hypotheses created after directive timestamp
    IF NEW.created_at > '2026-01-24 22:00:00+01'::TIMESTAMPTZ THEN
        IF NEW.generator_id IS NULL THEN
            -- Raise escalation event
            INSERT INTO fhq_learning.learning_escalation_log (
                trigger_type, trigger_value, threshold_value,
                escalation_action, details
            ) VALUES (
                'PROVENANCE_VIOLATION',
                'NULL',
                'NOT_NULL_REQUIRED',
                'WRITE_REJECTED',
                jsonb_build_object(
                    'hypothesis_code', NEW.hypothesis_code,
                    'origin_type', NEW.origin_type,
                    'violation', 'generator_id is NULL (fail-closed under ASRP)'
                )
            );

            RAISE EXCEPTION 'PROVENANCE_VIOLATION: generator_id cannot be NULL for new hypotheses (CEO-DIR-2026-POR-001 fail-closed)';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_provenance ON fhq_learning.hypothesis_canon;
CREATE TRIGGER trg_enforce_provenance
BEFORE INSERT ON fhq_learning.hypothesis_canon
FOR EACH ROW EXECUTE FUNCTION fhq_learning.enforce_provenance_on_insert();

-- ============================================================================
-- SECTION 4.5: LVG THROTTLE SUPPORT
-- ============================================================================

-- Add similarity/entropy tracking for mode collapse detection
ALTER TABLE fhq_learning.learning_velocity_metrics
ADD COLUMN IF NOT EXISTS generator_distribution JSONB DEFAULT '{}';

ALTER TABLE fhq_learning.learning_velocity_metrics
ADD COLUMN IF NOT EXISTS similarity_score NUMERIC(5,4) DEFAULT NULL;

ALTER TABLE fhq_learning.learning_velocity_metrics
ADD COLUMN IF NOT EXISTS throttle_active BOOLEAN DEFAULT FALSE;

ALTER TABLE fhq_learning.learning_velocity_metrics
ADD COLUMN IF NOT EXISTS throttle_reason TEXT DEFAULT NULL;

-- Function to check generator diversity (no single generator > 60%)
CREATE OR REPLACE FUNCTION fhq_learning.check_generator_diversity()
RETURNS TABLE (
    diverse BOOLEAN,
    dominant_generator TEXT,
    dominant_pct NUMERIC,
    distribution JSONB
) AS $$
DECLARE
    v_dist JSONB;
    v_total INTEGER;
    v_max_pct NUMERIC := 0;
    v_dominant TEXT := NULL;
    v_diverse BOOLEAN := TRUE;
    v_key TEXT;
    v_count INTEGER;
BEGIN
    -- Get distribution of generators for last 7 days
    SELECT jsonb_object_agg(generator_id, cnt), SUM(cnt)
    INTO v_dist, v_total
    FROM (
        SELECT COALESCE(generator_id, 'UNKNOWN') as generator_id, COUNT(*) as cnt
        FROM fhq_learning.hypothesis_canon
        WHERE created_at >= NOW() - INTERVAL '7 days'
        GROUP BY COALESCE(generator_id, 'UNKNOWN')
    ) t;

    IF v_total IS NULL OR v_total = 0 THEN
        RETURN QUERY SELECT TRUE, NULL::TEXT, 0::NUMERIC, '{}'::JSONB;
        RETURN;
    END IF;

    -- Check each generator's percentage
    FOR v_key, v_count IN SELECT * FROM jsonb_each_text(v_dist)
    LOOP
        IF (v_count::NUMERIC / v_total * 100) > v_max_pct THEN
            v_max_pct := v_count::NUMERIC / v_total * 100;
            v_dominant := v_key;
        END IF;
    END LOOP;

    -- Fail if any generator > 60%
    IF v_max_pct > 60 THEN
        v_diverse := FALSE;
    END IF;

    RETURN QUERY SELECT v_diverse, v_dominant, ROUND(v_max_pct, 1), v_dist;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS FOR CEO REPORTING
-- ============================================================================

-- Generator diversity view
CREATE OR REPLACE VIEW fhq_learning.v_generator_diversity AS
SELECT
    (fhq_learning.check_generator_diversity()).*,
    (SELECT COUNT(*) FROM fhq_learning.hypothesis_canon WHERE created_at >= NOW() - INTERVAL '7 days') as total_hypotheses_7d,
    (SELECT AVG(causal_graph_depth) FROM fhq_learning.hypothesis_canon WHERE created_at >= NOW() - INTERVAL '7 days') as avg_causal_depth_7d,
    (SELECT STDDEV(causal_graph_depth) FROM fhq_learning.hypothesis_canon WHERE created_at >= NOW() - INTERVAL '7 days') as causal_depth_variance;

-- Promotion gate status view
CREATE OR REPLACE VIEW fhq_learning.v_promotion_gate_status AS
SELECT
    h.hypothesis_code,
    h.generator_id,
    h.status,
    h.causal_graph_depth,
    h.trial_count,
    h.family_inflation_risk,
    h.pbo_probability,
    h.deflated_sharpe_computed,
    CASE
        WHEN h.generator_id IS NULL THEN 'BLOCKED: No provenance'
        WHEN h.falsification_criteria IS NULL THEN 'BLOCKED: No falsification'
        WHEN h.family_inflation_risk IS NULL AND h.pbo_probability IS NULL THEN 'BLOCKED: No overfitting metrics'
        WHEN h.family_inflation_risk > 0.30 THEN 'BLOCKED: High inflation risk'
        WHEN h.pbo_probability > 0.50 THEN 'BLOCKED: High PBO'
        ELSE 'ELIGIBLE'
    END as promotion_status
FROM fhq_learning.hypothesis_canon h
WHERE h.status NOT IN ('FALSIFIED', 'RETIRED');

-- Research Trinity status view
CREATE OR REPLACE VIEW fhq_learning.v_research_trinity_status AS
SELECT
    g.generator_id,
    g.generator_name,
    g.generator_type,
    g.status as generator_status,
    g.target_causal_depth,
    COUNT(h.canon_id) as total_hypotheses,
    COUNT(h.canon_id) FILTER (WHERE h.created_at >= NOW() - INTERVAL '24 hours') as hypotheses_24h,
    COUNT(h.canon_id) FILTER (WHERE h.created_at >= NOW() - INTERVAL '7 days') as hypotheses_7d,
    AVG(h.causal_graph_depth) as avg_causal_depth,
    COUNT(h.canon_id) FILTER (WHERE h.status = 'FALSIFIED') as falsified_count,
    COUNT(h.canon_id) FILTER (WHERE h.status = 'ACTIVE') as active_count
FROM fhq_learning.generator_registry g
LEFT JOIN fhq_learning.hypothesis_canon h ON g.generator_id = h.generator_id
GROUP BY g.generator_id, g.generator_name, g.generator_type, g.status, g.target_causal_depth;

-- ============================================================================
-- BACKFILL: Assign existing hypotheses to FINN-E (legacy error-driven)
-- ============================================================================

UPDATE fhq_learning.hypothesis_canon
SET generator_id = 'FINN-E'
WHERE generator_id IS NULL
  AND origin_type = 'ERROR_DRIVEN';

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_hypothesis_generator ON fhq_learning.hypothesis_canon(generator_id);
CREATE INDEX IF NOT EXISTS idx_hypothesis_provenance_hypothesis ON fhq_learning.hypothesis_provenance(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_experiment_provenance_experiment ON fhq_learning.experiment_provenance(experiment_id);
CREATE INDEX IF NOT EXISTS idx_promotion_gate_hypothesis ON fhq_learning.promotion_gate_audit(hypothesis_id);

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_generators INTEGER;
    v_hypotheses_with_generator INTEGER;
    v_total_hypotheses INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_generators FROM fhq_learning.generator_registry;
    SELECT COUNT(*) INTO v_hypotheses_with_generator FROM fhq_learning.hypothesis_canon WHERE generator_id IS NOT NULL;
    SELECT COUNT(*) INTO v_total_hypotheses FROM fhq_learning.hypothesis_canon;

    RAISE NOTICE 'Migration 346 VERIFIED:';
    RAISE NOTICE '  Generators registered: %', v_generators;
    RAISE NOTICE '  Hypotheses with provenance: % / %', v_hypotheses_with_generator, v_total_hypotheses;
    RAISE NOTICE '  Provenance coverage: %', ROUND(v_hypotheses_with_generator::NUMERIC / NULLIF(v_total_hypotheses, 0) * 100, 1) || '%';
END $$;

COMMIT;

-- ============================================================================
-- MIGRATION 346 COMPLETE
-- Multi-Generator Research Portfolio Infrastructure deployed
-- ============================================================================
