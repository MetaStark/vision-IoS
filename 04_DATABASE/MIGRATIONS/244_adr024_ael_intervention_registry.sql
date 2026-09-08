-- =============================================================================
-- MIGRATION 244: ADR-024 AEL INTERVENTION REGISTRY
-- =============================================================================
-- CEO Directive: ADR-024 Rung C - Intervention Registry & Causal Isolation
-- Author: STIG
-- Date: 2026-01-14
--
-- Purpose:
--   Creates the ael_intervention_registry table to track all interventions
--   per ADR-024 requirements:
--   - Uniquely identified (hash + version)
--   - Explicitly scoped (what it may touch)
--   - Executed in isolation windows (e.g. LDOW)
--   - Attribution must be unambiguous
--
-- Prevents:
--   - Cross-contamination
--   - Post-hoc rationalization
--   - Narrative overfitting
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 1: AEL INTERVENTION REGISTRY TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.ael_intervention_registry (
    intervention_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity & Version (ADR-024: Uniquely identified)
    intervention_hash TEXT NOT NULL,
    intervention_version TEXT NOT NULL DEFAULT '1.0',
    intervention_name TEXT NOT NULL,
    intervention_category TEXT NOT NULL CHECK (intervention_category IN (
        'CALIBRATION_TUNING',           -- Pre-signable: within fixed bounds
        'THRESHOLD_ADJUSTMENT',          -- Pre-signable: no topology change
        'WEIGHT_RENORMALIZATION',        -- Pre-signable: invariant schemas
        'FEATURE_CREATION',              -- EXCLUDED from pre-approval
        'FEATURE_REMOVAL',               -- EXCLUDED from pre-approval
        'REGIME_LOGIC_CHANGE',           -- EXCLUDED from pre-approval
        'OBJECTIVE_REDEFINITION',        -- EXCLUDED from pre-approval
        'CAPITAL_EXECUTION_LOGIC',       -- EXCLUDED from pre-approval
        'OBSERVATION_ONLY'               -- Phase 0: No intervention
    )),

    -- Scope Definition (ADR-024: Explicitly scoped)
    scope_target_schema TEXT NOT NULL,
    scope_target_tables TEXT[] NOT NULL DEFAULT '{}',
    scope_target_columns TEXT[] DEFAULT NULL,
    scope_parameter_bounds JSONB DEFAULT '{}',
    scope_blast_radius TEXT NOT NULL CHECK (scope_blast_radius IN (
        'ISOLATED',      -- Single parameter, no side effects
        'CONTAINED',     -- Multiple parameters, known bounds
        'SYSTEMIC'       -- Affects multiple components
    )),

    -- Hypothesis (ADR-024: Stated hypothesis, expected direction)
    hypothesis_statement TEXT NOT NULL,
    expected_direction TEXT NOT NULL CHECK (expected_direction IN (
        'IMPROVE_CALIBRATION',
        'IMPROVE_SKILL',
        'IMPROVE_GENERALIZATION',
        'REDUCE_VARIANCE',
        'NEUTRAL_REFACTOR'
    )),
    expected_magnitude TEXT NOT NULL CHECK (expected_magnitude IN (
        'MINOR',        -- <1% impact
        'MODERATE',     -- 1-5% impact
        'SIGNIFICANT'   -- >5% impact
    )),

    -- Isolation Window (ADR-024: Executed in isolation)
    isolation_window_type TEXT NOT NULL CHECK (isolation_window_type IN (
        'LDOW',          -- Learning Delta Observation Window
        'HOLDOUT',       -- Holdout evaluation period
        'IMMEDIATE',     -- Immediate (requires G4 approval)
        'SCHEDULED'      -- Scheduled batch window
    )),
    isolation_start_at TIMESTAMPTZ,
    isolation_end_at TIMESTAMPTZ,

    -- Rollback Path (ADR-024: Deterministic Rollback)
    rollback_strategy TEXT NOT NULL CHECK (rollback_strategy IN (
        'VERSION_REVERT',    -- Exact version recovery
        'PARAMETER_RESET',   -- Reset to baseline
        'SCHEMA_RESTORE',    -- Full schema restore
        'NOT_APPLICABLE'     -- Observation only
    )),
    rollback_target_version TEXT,
    rollback_sql TEXT,
    rollback_verified BOOLEAN DEFAULT FALSE,

    -- Attribution (ADR-024: Full Attribution)
    proposed_by TEXT NOT NULL,
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    executed_by TEXT,
    executed_at TIMESTAMPTZ,

    -- Evidence Chain
    evidence_id UUID,
    evidence_hash TEXT,
    parent_intervention_id UUID REFERENCES fhq_governance.ael_intervention_registry(intervention_id),

    -- State Tracking
    intervention_status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (intervention_status IN (
        'PROPOSED',      -- Rung D: Awaiting human authorization
        'APPROVED',      -- Authorized for execution
        'EXECUTING',     -- Currently running
        'COMPLETED',     -- Successfully completed
        'ROLLED_BACK',   -- Reverted due to issue
        'REJECTED',      -- Not approved
        'EXPIRED'        -- Window passed without execution
    )),

    -- Evaluation Results (Post-execution)
    evaluation_horizon_hours INTEGER,
    evaluation_metric_before JSONB,
    evaluation_metric_after JSONB,
    evaluation_delta JSONB,
    improvement_verified BOOLEAN,
    replicable_improvement BOOLEAN,

    -- Phase Gate (ADR-024)
    ael_phase INTEGER NOT NULL DEFAULT 0 CHECK (ael_phase BETWEEN 0 AND 4),
    rung_qualification TEXT CHECK (rung_qualification IN (
        'RUNG_A',  -- Measurement Completeness
        'RUNG_B',  -- Canonical Evaluation Contract
        'RUNG_C',  -- Intervention Registry (this table)
        'RUNG_D',  -- Human-Authorized Execution
        'RUNG_E'   -- Pre-Signed Policy
    )),

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- SECTION 2: INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_ael_intervention_hash
    ON fhq_governance.ael_intervention_registry(intervention_hash);

CREATE INDEX IF NOT EXISTS idx_ael_intervention_status
    ON fhq_governance.ael_intervention_registry(intervention_status);

CREATE INDEX IF NOT EXISTS idx_ael_intervention_category
    ON fhq_governance.ael_intervention_registry(intervention_category);

CREATE INDEX IF NOT EXISTS idx_ael_intervention_proposed_at
    ON fhq_governance.ael_intervention_registry(proposed_at DESC);

CREATE INDEX IF NOT EXISTS idx_ael_intervention_phase
    ON fhq_governance.ael_intervention_registry(ael_phase);

-- =============================================================================
-- SECTION 3: TRIGGER FOR UPDATED_AT
-- =============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.update_ael_intervention_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ael_intervention_updated ON fhq_governance.ael_intervention_registry;
CREATE TRIGGER trg_ael_intervention_updated
    BEFORE UPDATE ON fhq_governance.ael_intervention_registry
    FOR EACH ROW
    EXECUTE FUNCTION fhq_governance.update_ael_intervention_timestamp();

-- =============================================================================
-- SECTION 4: STILLNESS PROTOCOL ENFORCEMENT VIEW
-- =============================================================================
-- ADR-024: "Stillness is not weakness. Stillness is discipline."
-- This view identifies interventions missing required elements

CREATE OR REPLACE VIEW fhq_governance.v_ael_stillness_violations AS
SELECT
    intervention_id,
    intervention_name,
    intervention_category,
    intervention_status,
    proposed_by,
    proposed_at,
    CASE
        WHEN intervention_hash IS NULL OR intervention_hash = '' THEN 'MISSING_HASH'
        WHEN evidence_id IS NULL THEN 'MISSING_EVIDENCE'
        WHEN rollback_strategy IS NULL THEN 'MISSING_ROLLBACK'
        WHEN rollback_strategy != 'NOT_APPLICABLE' AND rollback_verified = FALSE THEN 'UNVERIFIED_ROLLBACK'
        WHEN hypothesis_statement IS NULL OR hypothesis_statement = '' THEN 'MISSING_HYPOTHESIS'
        WHEN scope_target_tables = '{}' AND intervention_category != 'OBSERVATION_ONLY' THEN 'MISSING_SCOPE'
        ELSE 'COMPLIANT'
    END AS violation_type,
    'ADR-024' AS adr_reference
FROM fhq_governance.ael_intervention_registry
WHERE intervention_status NOT IN ('REJECTED', 'EXPIRED');

-- =============================================================================
-- SECTION 5: PRE-SIGNABLE CATEGORIES VIEW
-- =============================================================================
-- ADR-024 Section 5: Only these categories may be pre-approved for autonomous execution

CREATE OR REPLACE VIEW fhq_governance.v_ael_presignable_interventions AS
SELECT
    intervention_id,
    intervention_name,
    intervention_category,
    intervention_status,
    scope_blast_radius,
    rollback_verified,
    CASE
        WHEN intervention_category IN ('CALIBRATION_TUNING', 'THRESHOLD_ADJUSTMENT', 'WEIGHT_RENORMALIZATION')
             AND scope_blast_radius IN ('ISOLATED', 'CONTAINED')
             AND rollback_verified = TRUE
        THEN TRUE
        ELSE FALSE
    END AS eligible_for_presign,
    ael_phase,
    rung_qualification
FROM fhq_governance.ael_intervention_registry
WHERE intervention_status IN ('PROPOSED', 'APPROVED');

-- =============================================================================
-- SECTION 6: BASELINE OBSERVATION RECORD (Phase 0)
-- =============================================================================
-- ADR-024: "Phase 0 - Observation only - Current state"

INSERT INTO fhq_governance.ael_intervention_registry (
    intervention_hash,
    intervention_version,
    intervention_name,
    intervention_category,
    scope_target_schema,
    scope_target_tables,
    scope_blast_radius,
    hypothesis_statement,
    expected_direction,
    expected_magnitude,
    isolation_window_type,
    rollback_strategy,
    proposed_by,
    approved_by,
    approved_at,
    executed_by,
    executed_at,
    intervention_status,
    ael_phase,
    rung_qualification
) VALUES (
    'ADR024-BASELINE-OBSERVATION-' || md5(NOW()::TEXT),
    '1.0',
    'ADR-024 Baseline Observation Record',
    'OBSERVATION_ONLY',
    'fhq_governance',
    ARRAY['ael_intervention_registry'],
    'ISOLATED',
    'Establish Phase 0 baseline for AEL tracking. No interventions - observation only.',
    'NEUTRAL_REFACTOR',
    'MINOR',
    'IMMEDIATE',
    'NOT_APPLICABLE',
    'STIG',
    'CEO',
    NOW(),
    'STIG',
    NOW(),
    'COMPLETED',
    0,
    'RUNG_C'
) ON CONFLICT DO NOTHING;

-- =============================================================================
-- SECTION 7: GOVERNANCE LOG
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'SCHEMA_CREATION',
    'fhq_governance.ael_intervention_registry',
    'TABLE',
    'STIG',
    'EXECUTED',
    'ADR-024 Rung C: Intervention Registry & Causal Isolation',
    jsonb_build_object(
        'migration', '244_adr024_ael_intervention_registry.sql',
        'adr_reference', 'ADR-024',
        'rung', 'C',
        'directive', 'CEO-DIR-2026-ADR024-EXEC',
        'timestamp', NOW()
    )
);

COMMIT;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT 'Migration 244 Complete: AEL Intervention Registry Created' AS status;
SELECT COUNT(*) AS baseline_records FROM fhq_governance.ael_intervention_registry;
