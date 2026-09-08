-- ============================================================
-- MIGRATION 208: CEO-DIR-2026-001 EPISTEMIC SEPARATION
-- ============================================================
--
-- DIRECTIVE: CEO-DIR-2026-001
-- CLASSIFICATION: GOVERNANCE-CRITICAL (CLASS A)
-- CONSTITUTIONAL BASIS: ADR-017, ADR-014, ADR-020, ADR-023
--
-- PURPOSE:
-- Enforce strict separation between:
--   1. MODEL BELIEF STATE (what the system observes and infers)
--   2. SOVEREIGN POLICY STATE (what the system decides to execute)
--
-- INVARIANTS ENFORCED:
--   - Belief and Action SHALL NOT share the same canonical variable
--   - Learning SHALL reference belief, not action
--   - Policy-induced delay SHALL be explicit, not implicit
--   - Suppressed belief SHALL be observable and auditable
--   - Opportunity cost of suppression SHALL be measurable
--
-- EXECUTED BY: STIG (Chief Architecture Officer)
-- DATE: 2026-01-06
-- ============================================================

BEGIN;

-- ============================================================
-- SECTION 1: MODEL BELIEF STATE (EPISTEMIC TRUTH)
-- ============================================================

-- Primary table for unfiltered model perception
CREATE TABLE IF NOT EXISTS fhq_perception.model_belief_state (
    belief_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    asset_id TEXT NOT NULL,
    belief_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Raw Model Output (NEVER filtered by policy)
    technical_regime TEXT NOT NULL,
    belief_distribution JSONB NOT NULL,  -- Full probability distribution
    belief_confidence NUMERIC(6,4) NOT NULL,  -- max(belief_distribution)
    dominant_regime TEXT NOT NULL,  -- argmax(belief_distribution)

    -- Model Metadata
    model_version TEXT NOT NULL,
    inference_engine TEXT NOT NULL,
    feature_hash TEXT,

    -- Changepoint Detection
    is_changepoint BOOLEAN DEFAULT FALSE,
    changepoint_probability NUMERIC(6,4),
    run_length INTEGER,

    -- Epistemic Quality
    entropy NUMERIC(6,4),  -- Uncertainty measure
    regime_stability_score NUMERIC(6,4),

    -- Lineage
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lineage_hash TEXT NOT NULL,

    -- Constraints
    CONSTRAINT belief_confidence_range CHECK (belief_confidence >= 0 AND belief_confidence <= 1),
    CONSTRAINT belief_distribution_valid CHECK (jsonb_typeof(belief_distribution) = 'object')
);

-- Index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_model_belief_state_asset_time
ON fhq_perception.model_belief_state(asset_id, belief_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_model_belief_state_dominant
ON fhq_perception.model_belief_state(dominant_regime, belief_timestamp DESC);

-- Comment
COMMENT ON TABLE fhq_perception.model_belief_state IS
'CEO-DIR-2026-001: Unfiltered model perception. NEVER modified by policy. Source of epistemic truth for all learning.';

-- ============================================================
-- SECTION 2: SOVEREIGN POLICY STATE (ACTION UNDER CONSTRAINT)
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_perception.sovereign_policy_state (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to belief (MANDATORY - policy must reference belief)
    belief_id UUID NOT NULL REFERENCES fhq_perception.model_belief_state(belief_id),

    -- Identity
    asset_id TEXT NOT NULL,
    policy_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Policy Decision
    policy_regime TEXT NOT NULL,  -- What we decided to act on
    policy_confidence NUMERIC(6,4) NOT NULL,

    -- Belief vs Policy Divergence (EXPLICIT)
    belief_regime TEXT NOT NULL,  -- Copy from belief for audit
    belief_confidence NUMERIC(6,4) NOT NULL,
    is_suppressed BOOLEAN NOT NULL DEFAULT FALSE,
    suppression_reason TEXT,  -- Why belief was overridden

    -- Policy Constraints Applied
    hysteresis_active BOOLEAN DEFAULT FALSE,
    hysteresis_days_remaining INTEGER,
    defcon_level TEXT,
    risk_scalar_applied NUMERIC(6,4),

    -- Transition State (EXPLICIT - per CEO directive point 6)
    transition_state TEXT,  -- 'STABLE', 'PENDING_CONFIRMATION', 'TRANSITIONING'
    pending_regime TEXT,  -- What we're waiting to confirm
    consecutive_confirms INTEGER DEFAULT 0,
    confirms_required INTEGER,

    -- Governance
    policy_version TEXT NOT NULL,
    policy_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT policy_confidence_range CHECK (policy_confidence >= 0 AND policy_confidence <= 1)
);

-- Index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_sovereign_policy_state_asset_time
ON fhq_perception.sovereign_policy_state(asset_id, policy_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_sovereign_policy_state_suppressed
ON fhq_perception.sovereign_policy_state(is_suppressed, policy_timestamp DESC)
WHERE is_suppressed = TRUE;

-- Comment
COMMENT ON TABLE fhq_perception.sovereign_policy_state IS
'CEO-DIR-2026-001: Policy decisions with explicit belief reference. Divergence is auditable.';

-- ============================================================
-- SECTION 3: EPISTEMIC SUPPRESSION LEDGER
-- ============================================================

CREATE TABLE IF NOT EXISTS fhq_governance.epistemic_suppression_ledger (
    suppression_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- References
    belief_id UUID NOT NULL REFERENCES fhq_perception.model_belief_state(belief_id),
    policy_id UUID NOT NULL REFERENCES fhq_perception.sovereign_policy_state(policy_id),

    -- Suppression Details
    asset_id TEXT NOT NULL,
    suppression_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- What was suppressed
    suppressed_regime TEXT NOT NULL,
    suppressed_confidence NUMERIC(6,4) NOT NULL,

    -- What was chosen instead
    chosen_regime TEXT NOT NULL,
    chosen_confidence NUMERIC(6,4) NOT NULL,

    -- Why (EXPLICIT per CEO directive)
    suppression_reason TEXT NOT NULL,
    suppression_category TEXT NOT NULL,  -- 'HYSTERESIS', 'DEFCON', 'RISK_LIMIT', 'LIQUIDITY'

    -- Governance constraint that caused suppression
    constraint_type TEXT NOT NULL,
    constraint_value TEXT,
    constraint_threshold TEXT,

    -- Opportunity Cost Tracking (CEO directive point 8)
    opportunity_cost_estimated NUMERIC(12,4),  -- Estimated $ impact
    market_outcome TEXT,  -- Filled post-facto: what actually happened
    opportunity_cost_realized NUMERIC(12,4),  -- Actual $ impact (filled later)
    lesson_extracted TEXT,  -- Learning from this suppression

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,

    -- Constraints
    CONSTRAINT valid_suppression_category CHECK (
        suppression_category IN ('HYSTERESIS', 'DEFCON', 'RISK_LIMIT', 'LIQUIDITY', 'MANUAL_OVERRIDE', 'OTHER')
    )
);

-- Index for governance review
CREATE INDEX IF NOT EXISTS idx_epistemic_suppression_unreviewed
ON fhq_governance.epistemic_suppression_ledger(created_at DESC)
WHERE reviewed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_epistemic_suppression_by_category
ON fhq_governance.epistemic_suppression_ledger(suppression_category, created_at DESC);

-- Comment
COMMENT ON TABLE fhq_governance.epistemic_suppression_ledger IS
'CEO-DIR-2026-001: Audit trail of every belief suppression. Enables opportunity cost measurement and learning.';

-- ============================================================
-- SECTION 4: CANONICAL BELIEF STATE VIEW
-- ============================================================

-- This view provides the latest belief for each asset (for learning systems)
CREATE OR REPLACE VIEW fhq_perception.v_canonical_belief AS
SELECT DISTINCT ON (asset_id)
    belief_id,
    asset_id,
    belief_timestamp,
    technical_regime,
    dominant_regime,
    belief_distribution,
    belief_confidence,
    entropy,
    is_changepoint,
    model_version
FROM fhq_perception.model_belief_state
ORDER BY asset_id, belief_timestamp DESC;

COMMENT ON VIEW fhq_perception.v_canonical_belief IS
'CEO-DIR-2026-001: Latest unfiltered belief per asset. USE THIS FOR LEARNING, NOT sovereign_policy_state.';

-- ============================================================
-- SECTION 5: CANONICAL POLICY STATE VIEW
-- ============================================================

-- This view provides the latest policy for each asset (for execution systems)
CREATE OR REPLACE VIEW fhq_perception.v_canonical_policy AS
SELECT DISTINCT ON (sps.asset_id)
    sps.policy_id,
    sps.belief_id,
    sps.asset_id,
    sps.policy_timestamp,
    sps.policy_regime,
    sps.policy_confidence,
    sps.belief_regime,
    sps.belief_confidence AS belief_conf,
    sps.is_suppressed,
    sps.suppression_reason,
    sps.transition_state,
    sps.pending_regime,
    sps.consecutive_confirms,
    sps.confirms_required,
    sps.hysteresis_active,
    sps.defcon_level
FROM fhq_perception.sovereign_policy_state sps
ORDER BY sps.asset_id, sps.policy_timestamp DESC;

COMMENT ON VIEW fhq_perception.v_canonical_policy IS
'CEO-DIR-2026-001: Latest policy decision per asset. USE THIS FOR EXECUTION, includes explicit divergence from belief.';

-- ============================================================
-- SECTION 6: SUPPRESSION SUMMARY VIEW (for CEO/VEGA)
-- ============================================================

CREATE OR REPLACE VIEW fhq_governance.v_suppression_summary AS
SELECT
    DATE(suppression_timestamp) as suppression_date,
    suppression_category,
    COUNT(*) as suppression_count,
    AVG(suppressed_confidence) as avg_suppressed_confidence,
    SUM(COALESCE(opportunity_cost_realized, 0)) as total_realized_cost,
    COUNT(*) FILTER (WHERE reviewed_at IS NULL) as unreviewed_count
FROM fhq_governance.epistemic_suppression_ledger
GROUP BY DATE(suppression_timestamp), suppression_category
ORDER BY suppression_date DESC, suppression_count DESC;

COMMENT ON VIEW fhq_governance.v_suppression_summary IS
'CEO-DIR-2026-001: Daily suppression summary for governance review.';

-- ============================================================
-- SECTION 7: UPDATE FHQ_META.REGIME_STATE SEMANTICS
-- ============================================================

-- Add columns to make belief vs policy explicit
ALTER TABLE fhq_meta.regime_state
ADD COLUMN IF NOT EXISTS belief_regime TEXT,
ADD COLUMN IF NOT EXISTS belief_confidence NUMERIC(6,4),
ADD COLUMN IF NOT EXISTS is_policy_divergent BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS divergence_reason TEXT,
ADD COLUMN IF NOT EXISTS transition_state TEXT DEFAULT 'STABLE';

-- Update current row to reflect the architectural correction
UPDATE fhq_meta.regime_state
SET
    belief_regime = 'STRESS',  -- What the model actually believes (from today's analysis)
    belief_confidence = 0.8499,
    is_policy_divergent = TRUE,
    divergence_reason = 'HYSTERESIS: 1/5 confirms (CEO-DIR-2026-001 identified)',
    transition_state = 'PENDING_CONFIRMATION',
    updated_by = 'STIG.DIR_2026_001'
WHERE state_id IS NOT NULL;

COMMENT ON COLUMN fhq_meta.regime_state.belief_regime IS
'CEO-DIR-2026-001: What the model believes (unfiltered)';
COMMENT ON COLUMN fhq_meta.regime_state.belief_confidence IS
'CEO-DIR-2026-001: Model confidence in belief_regime';
COMMENT ON COLUMN fhq_meta.regime_state.is_policy_divergent IS
'CEO-DIR-2026-001: TRUE when policy_regime != belief_regime';
COMMENT ON COLUMN fhq_meta.regime_state.transition_state IS
'CEO-DIR-2026-001: STABLE, PENDING_CONFIRMATION, TRANSITIONING';

-- ============================================================
-- SECTION 8: GOVERNANCE LOG
-- ============================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'CONSTITUTIONAL_CORRECTION',
    'CEO-DIR-2026-001',
    'DIRECTIVE',
    'CEO',
    'EXECUTED',
    'Mandatory Epistemic Separation: Belief vs Action. Constitutional architectural correction enforcing ADR-017, ADR-020, ADR-023.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-001',
        'classification', 'GOVERNANCE-CRITICAL (CLASS A)',
        'tables_created', ARRAY[
            'fhq_perception.model_belief_state',
            'fhq_perception.sovereign_policy_state',
            'fhq_governance.epistemic_suppression_ledger'
        ],
        'views_created', ARRAY[
            'fhq_perception.v_canonical_belief',
            'fhq_perception.v_canonical_policy',
            'fhq_governance.v_suppression_summary'
        ],
        'invariants_enforced', ARRAY[
            'Belief and Action separate canonical variables',
            'Learning references belief not action',
            'Policy delay explicit not implicit',
            'Suppressed belief auditable',
            'Opportunity cost measurable'
        ],
        'executed_by', 'STIG',
        'timestamp', NOW()
    )
);

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================

-- Verify tables created
SELECT 'model_belief_state' as table_name, COUNT(*) as exists FROM information_schema.tables
WHERE table_schema = 'fhq_perception' AND table_name = 'model_belief_state'
UNION ALL
SELECT 'sovereign_policy_state', COUNT(*) FROM information_schema.tables
WHERE table_schema = 'fhq_perception' AND table_name = 'sovereign_policy_state'
UNION ALL
SELECT 'epistemic_suppression_ledger', COUNT(*) FROM information_schema.tables
WHERE table_schema = 'fhq_governance' AND table_name = 'epistemic_suppression_ledger';

-- Verify fhq_meta.regime_state updated
SELECT current_regime, regime_confidence, belief_regime, belief_confidence,
       is_policy_divergent, divergence_reason, transition_state
FROM fhq_meta.regime_state;
