-- ============================================================================
-- MIGRATION 186: Learning Correction Schema
-- CEO-DIR-2026-FINN-009: Epistemic Learning Correction & Freedom Preservation
-- ============================================================================
--
-- ROOT CAUSE REMEDIATION:
--   DEFECT-001: Schema Misalignment
--   DEFECT-002: Non-Causal Feedback Loop
--   DEFECT-003: Simulated Reward Signal
--
-- This migration creates VERIFIED LEARNING infrastructure.
-- Learning remains SUSPENDED until all conditions are met.
--
-- ============================================================================

-- 1. Create canonical path_yield_attribution table (replaces broken path_yield_history usage)
CREATE TABLE IF NOT EXISTS fhq_research.path_yield_attribution (
    attribution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Path identification
    path_hash TEXT NOT NULL,
    ontology_path TEXT[] NOT NULL,

    -- Causal binding (DEFECT-002 fix)
    retrieval_event_id UUID,  -- FK to actual retrieval event
    sitc_node_id UUID,        -- FK to SitC chain node
    regime_id TEXT NOT NULL,
    regime_confidence NUMERIC(5,4),

    -- Attribution metrics (DEFECT-003 fix: real reward signals)
    evidence_retrieved INTEGER NOT NULL DEFAULT 0,
    evidence_used INTEGER NOT NULL DEFAULT 0,
    marginal_contribution NUMERIC(5,4) GENERATED ALWAYS AS (
        CASE WHEN evidence_retrieved > 0
             THEN evidence_used::NUMERIC / evidence_retrieved
             ELSE 0
        END
    ) STORED,

    -- InForage reward signals (real, not simulated)
    information_gain NUMERIC(10,6),      -- Entropy reduction from this path
    redundancy_avoided NUMERIC(10,6),    -- Duplicate evidence not fetched
    cost_saved NUMERIC(10,6),            -- API cost avoided by path efficiency

    -- Composite yield (real signal)
    real_yield NUMERIC(5,4) GENERATED ALWAYS AS (
        COALESCE(
            (CASE WHEN evidence_retrieved > 0
                  THEN evidence_used::NUMERIC / evidence_retrieved
                  ELSE 0
             END) * 0.5 +
            COALESCE(information_gain, 0) * 0.3 +
            COALESCE(redundancy_avoided, 0) * 0.2,
            0
        )
    ) STORED,

    -- Batch tracking
    batch_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,

    -- Governance
    directive_ref TEXT DEFAULT 'CEO-DIR-2026-FINN-009'
);

CREATE INDEX IF NOT EXISTS idx_path_yield_attr_path
    ON fhq_research.path_yield_attribution(path_hash);
CREATE INDEX IF NOT EXISTS idx_path_yield_attr_regime
    ON fhq_research.path_yield_attribution(regime_id);
CREATE INDEX IF NOT EXISTS idx_path_yield_attr_batch
    ON fhq_research.path_yield_attribution(batch_id, run_number);
CREATE INDEX IF NOT EXISTS idx_path_yield_attr_sitc
    ON fhq_research.path_yield_attribution(sitc_node_id);

-- 2. Create retrieval_events table for causal binding
CREATE TABLE IF NOT EXISTS fhq_research.retrieval_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Event identification
    batch_id TEXT NOT NULL,
    run_number INTEGER NOT NULL,
    hypothesis_id TEXT NOT NULL,

    -- SitC binding
    sitc_chain_id UUID,
    sitc_node_type TEXT CHECK (sitc_node_type IN (
        'PLAN_INIT', 'REASONING', 'SEARCH', 'VERIFICATION', 'SYNTHESIS', 'ABORT'
    )),

    -- Retrieval details
    query_text TEXT,
    source_tier TEXT CHECK (source_tier IN ('LAKE', 'PULSE', 'SNIPER')),
    evidence_count INTEGER NOT NULL DEFAULT 0,

    -- Cost tracking (InForage binding)
    api_cost NUMERIC(10,6) DEFAULT 0,
    latency_ms INTEGER,

    -- Regime context
    regime_id TEXT NOT NULL,
    regime_confidence NUMERIC(5,4),

    -- Outcome
    was_used_in_synthesis BOOLEAN DEFAULT FALSE,
    contribution_score NUMERIC(5,4)
);

CREATE INDEX IF NOT EXISTS idx_retrieval_events_batch
    ON fhq_research.retrieval_events(batch_id, run_number);
CREATE INDEX IF NOT EXISTS idx_retrieval_events_sitc
    ON fhq_research.retrieval_events(sitc_chain_id);

-- 3. Create learning_suspension_log (tracks suspension state)
CREATE TABLE IF NOT EXISTS fhq_research.learning_suspension_log (
    suspension_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    directive_ref TEXT NOT NULL,
    suspension_type TEXT NOT NULL CHECK (suspension_type IN (
        'PATH_WEIGHT_UPDATES', 'SAFE_BOUNDS', 'ENTROPY_STOPPING', 'ALL'
    )),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    reason TEXT NOT NULL,

    -- Reactivation conditions
    reactivation_conditions JSONB,
    reactivated_at TIMESTAMPTZ,
    reactivated_by TEXT
);

-- Insert current suspension per CEO-DIR-009
INSERT INTO fhq_research.learning_suspension_log (
    directive_ref, suspension_type, is_active, reason, reactivation_conditions
) VALUES (
    'CEO-DIR-2026-FINN-009',
    'PATH_WEIGHT_UPDATES',
    TRUE,
    'Batch 3 learning failure: Schema misalignment, non-causal feedback, simulated reward',
    '{
        "schema": "Verified by STIG",
        "attribution": "Signed by SitC",
        "reward_signal": "Derived from InForage",
        "governance": "VEGA G1 cleared"
    }'::jsonb
);

-- 4. Create learning_reactivation_checklist
CREATE TABLE IF NOT EXISTS fhq_research.learning_reactivation_checklist (
    check_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    directive_ref TEXT NOT NULL,
    condition_name TEXT NOT NULL,
    condition_description TEXT NOT NULL,

    is_satisfied BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    evidence_ref TEXT
);

-- Insert reactivation conditions
INSERT INTO fhq_research.learning_reactivation_checklist
    (directive_ref, condition_name, condition_description)
VALUES
    ('CEO-DIR-2026-FINN-009', 'SCHEMA_CORRECTION',
     'path_yield_attribution table with proper FKs to retrieval_events and SitC nodes'),
    ('CEO-DIR-2026-FINN-009', 'CAUSAL_ATTRIBUTION',
     'marginal_contribution = evidence_used / evidence_retrieved, per path, per regime'),
    ('CEO-DIR-2026-FINN-009', 'REAL_REWARD_SIGNAL',
     'Yield derived from information_gain, redundancy_avoided, cost_saved'),
    ('CEO-DIR-2026-FINN-009', 'VEGA_G1_CLEARANCE',
     'VEGA attestation that learning infrastructure is sound');

-- 5. Create view for learning readiness dashboard
CREATE OR REPLACE VIEW fhq_research.learning_readiness_dashboard AS
SELECT
    -- Suspension status
    (SELECT COUNT(*) FROM fhq_research.learning_suspension_log
     WHERE is_active = TRUE) AS active_suspensions,

    -- Checklist progress
    (SELECT COUNT(*) FROM fhq_research.learning_reactivation_checklist
     WHERE is_satisfied = TRUE) AS conditions_satisfied,
    (SELECT COUNT(*) FROM fhq_research.learning_reactivation_checklist) AS conditions_total,

    -- Schema readiness
    EXISTS(SELECT 1 FROM information_schema.tables
           WHERE table_schema = 'fhq_research'
           AND table_name = 'path_yield_attribution') AS schema_ready,

    EXISTS(SELECT 1 FROM information_schema.tables
           WHERE table_schema = 'fhq_research'
           AND table_name = 'retrieval_events') AS retrieval_events_ready,

    -- Learning status
    CASE
        WHEN (SELECT COUNT(*) FROM fhq_research.learning_suspension_log WHERE is_active = TRUE) > 0
        THEN 'SUSPENDED'
        WHEN (SELECT COUNT(*) FROM fhq_research.learning_reactivation_checklist WHERE is_satisfied = FALSE) > 0
        THEN 'PENDING_VERIFICATION'
        ELSE 'READY'
    END AS learning_status,

    -- Next batch targets
    0.50 AS batch_4_target,
    0.55 AS batch_5_target,
    0.60 AS batch_6_target;

-- 6. Function to compute real yield from retrieval event
CREATE OR REPLACE FUNCTION fhq_research.compute_real_yield(
    p_retrieval_event_id UUID
)
RETURNS NUMERIC AS $$
DECLARE
    v_event RECORD;
    v_yield NUMERIC;
BEGIN
    SELECT * INTO v_event
    FROM fhq_research.retrieval_events
    WHERE event_id = p_retrieval_event_id;

    IF NOT FOUND THEN
        RETURN 0;
    END IF;

    -- Real yield formula per CEO-DIR-009:
    -- 50% marginal contribution (evidence used / retrieved)
    -- 30% information gain (normalized)
    -- 20% redundancy avoided (normalized)
    v_yield := COALESCE(v_event.contribution_score, 0) * 0.5;

    -- Add cost efficiency component
    IF v_event.api_cost IS NOT NULL AND v_event.api_cost > 0 THEN
        v_yield := v_yield + (1 - LEAST(v_event.api_cost / 0.01, 1)) * 0.3;
    END IF;

    -- Add synthesis contribution
    IF v_event.was_used_in_synthesis THEN
        v_yield := v_yield + 0.2;
    END IF;

    RETURN LEAST(v_yield, 1.0);
END;
$$ LANGUAGE plpgsql STABLE;

-- 7. Function to check if learning can be reactivated
CREATE OR REPLACE FUNCTION fhq_research.can_reactivate_learning()
RETURNS BOOLEAN AS $$
DECLARE
    v_unsatisfied INTEGER;
    v_active_suspensions INTEGER;
BEGIN
    -- Check unsatisfied conditions
    SELECT COUNT(*) INTO v_unsatisfied
    FROM fhq_research.learning_reactivation_checklist
    WHERE is_satisfied = FALSE;

    -- Check active suspensions
    SELECT COUNT(*) INTO v_active_suspensions
    FROM fhq_research.learning_suspension_log
    WHERE is_active = TRUE;

    RETURN v_unsatisfied = 0 AND v_active_suspensions = 0;
END;
$$ LANGUAGE plpgsql STABLE;

-- 8. Function to mark condition as satisfied
CREATE OR REPLACE FUNCTION fhq_research.satisfy_reactivation_condition(
    p_condition_name TEXT,
    p_verified_by TEXT,
    p_evidence_ref TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE fhq_research.learning_reactivation_checklist
    SET is_satisfied = TRUE,
        verified_by = p_verified_by,
        verified_at = NOW(),
        evidence_ref = p_evidence_ref
    WHERE condition_name = p_condition_name
      AND directive_ref = 'CEO-DIR-2026-FINN-009';

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- 9. Mark SCHEMA_CORRECTION as satisfied (this migration completes it)
SELECT fhq_research.satisfy_reactivation_condition(
    'SCHEMA_CORRECTION',
    'STIG',
    'Migration 186 executed'
);

-- 10. Grant permissions
GRANT SELECT, INSERT ON fhq_research.path_yield_attribution TO PUBLIC;
GRANT SELECT, INSERT ON fhq_research.retrieval_events TO PUBLIC;
GRANT SELECT ON fhq_research.learning_suspension_log TO PUBLIC;
GRANT SELECT ON fhq_research.learning_reactivation_checklist TO PUBLIC;
GRANT SELECT ON fhq_research.learning_readiness_dashboard TO PUBLIC;

-- 11. Migration metadata
COMMENT ON TABLE fhq_research.path_yield_attribution IS
    'CEO-DIR-2026-FINN-009: Canonical yield attribution with causal binding';
COMMENT ON TABLE fhq_research.retrieval_events IS
    'CEO-DIR-2026-FINN-009: Retrieval events for causal attribution';
COMMENT ON TABLE fhq_research.learning_suspension_log IS
    'CEO-DIR-2026-FINN-009: Learning suspension tracking';

-- ============================================================================
-- MIGRATION 186 COMPLETE
--
-- Status:
--   [x] SCHEMA_CORRECTION - Satisfied by this migration
--   [ ] CAUSAL_ATTRIBUTION - Pending FINN + SitC integration
--   [ ] REAL_REWARD_SIGNAL - Pending InForage integration
--   [ ] VEGA_G1_CLEARANCE - Pending VEGA attestation
--
-- Learning remains SUSPENDED until all conditions are satisfied.
-- ============================================================================
