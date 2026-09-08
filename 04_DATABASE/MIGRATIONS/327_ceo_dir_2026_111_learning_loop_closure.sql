-- CEO-DIR-2026-111 Phase 5: Learning Loop Closure
-- Classification: MANDATORY – IMMEDIATE EXECUTION
-- Every CPTO-evaluated signal recorded in fhq_research.evaluations
-- Implementor: STIG
-- Date: 2026-01-20

-- =============================================================================
-- PHASE 5: LEARNING LOOP CLOSURE
-- Requirement: Every CPTO-evaluated signal must be recorded including:
-- - Decision rationale
-- - Slippage saved
-- - Refusal reason (TTL / Liquidity / DEFCON)
-- - Regime snapshot
-- - Parameter version hash
--
-- Purpose: Feed Brier decomposition and Learning Velocity Index (LVI) with
-- live-regime data.
-- =============================================================================

BEGIN;

-- Step 1: Create evaluations table for CPTO signal learning
CREATE TABLE IF NOT EXISTS fhq_research.evaluations (
    evaluation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal identification
    source_signal_id UUID NOT NULL,
    source_plan_id UUID,
    source_module TEXT NOT NULL,
    signal_class TEXT NOT NULL,

    -- Instrument
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence NUMERIC NOT NULL,

    -- CPTO Decision
    cpto_decision TEXT NOT NULL,  -- 'ACCEPTED', 'BLOCKED_TTL', 'BLOCKED_DEFCON', 'BLOCKED_LIQUIDITY', 'BLOCKED_INVERSION_UNVERIFIED'
    decision_rationale TEXT NOT NULL,

    -- Refusal reason (if blocked)
    refusal_reason TEXT,
    refusal_category TEXT,  -- 'TTL', 'DEFCON', 'LIQUIDITY', 'INVERSION', 'OTHER'

    -- Slippage saved (CEO Amendment B)
    mid_market_price NUMERIC,
    calculated_entry_price NUMERIC,
    slippage_saved_bps NUMERIC,

    -- Regime snapshot
    regime_at_evaluation TEXT NOT NULL,
    regime_confidence NUMERIC,
    regime_snapshot_hash TEXT NOT NULL,

    -- Parameter version (Fix #5)
    parameter_set_version TEXT NOT NULL,
    parameter_set_hash TEXT NOT NULL,

    -- DEFCON state
    defcon_at_evaluation TEXT NOT NULL,
    defcon_behavior TEXT NOT NULL,

    -- TTL state
    signal_valid_until TIMESTAMPTZ NOT NULL,
    ttl_remaining_seconds NUMERIC NOT NULL,
    ttl_check_passed BOOLEAN NOT NULL,

    -- Inversion metadata (if applicable)
    is_inversion_candidate BOOLEAN NOT NULL DEFAULT false,
    inversion_verified BOOLEAN,
    inversion_verification_source TEXT,

    -- Friction tracking
    friction_recorded BOOLEAN NOT NULL DEFAULT false,
    friction_escalation_triggered BOOLEAN NOT NULL DEFAULT false,
    friction_escalation_target TEXT,

    -- Learning loop metadata
    ios010_linked BOOLEAN NOT NULL DEFAULT false,
    brier_contribution_logged BOOLEAN NOT NULL DEFAULT false,
    lvi_contribution_logged BOOLEAN NOT NULL DEFAULT false,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    directive_reference TEXT NOT NULL DEFAULT 'CEO-DIR-2026-111'
);

CREATE INDEX IF NOT EXISTS idx_evaluations_signal
ON fhq_research.evaluations(source_signal_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evaluations_decision
ON fhq_research.evaluations(cpto_decision, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evaluations_regime
ON fhq_research.evaluations(regime_at_evaluation, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_evaluations_refusal
ON fhq_research.evaluations(refusal_category, created_at DESC)
WHERE refusal_category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_evaluations_inversion
ON fhq_research.evaluations(is_inversion_candidate, inversion_verified);

-- Step 2: Create function to log CPTO evaluation
CREATE OR REPLACE FUNCTION fhq_research.log_cpto_evaluation(
    p_source_signal_id UUID,
    p_source_plan_id UUID,
    p_source_module TEXT,
    p_signal_class TEXT,
    p_instrument TEXT,
    p_direction TEXT,
    p_confidence NUMERIC,
    p_cpto_decision TEXT,
    p_decision_rationale TEXT,
    p_refusal_reason TEXT,
    p_refusal_category TEXT,
    p_mid_market_price NUMERIC,
    p_calculated_entry_price NUMERIC,
    p_slippage_saved_bps NUMERIC,
    p_regime TEXT,
    p_regime_confidence NUMERIC,
    p_regime_snapshot_hash TEXT,
    p_parameter_version TEXT,
    p_parameter_hash TEXT,
    p_defcon TEXT,
    p_defcon_behavior TEXT,
    p_valid_until TIMESTAMPTZ,
    p_ttl_remaining NUMERIC,
    p_ttl_passed BOOLEAN,
    p_is_inversion BOOLEAN,
    p_inversion_verified BOOLEAN,
    p_inversion_source TEXT
) RETURNS UUID AS $$
DECLARE
    v_eval_id UUID;
BEGIN
    INSERT INTO fhq_research.evaluations (
        source_signal_id,
        source_plan_id,
        source_module,
        signal_class,
        instrument,
        direction,
        confidence,
        cpto_decision,
        decision_rationale,
        refusal_reason,
        refusal_category,
        mid_market_price,
        calculated_entry_price,
        slippage_saved_bps,
        regime_at_evaluation,
        regime_confidence,
        regime_snapshot_hash,
        parameter_set_version,
        parameter_set_hash,
        defcon_at_evaluation,
        defcon_behavior,
        signal_valid_until,
        ttl_remaining_seconds,
        ttl_check_passed,
        is_inversion_candidate,
        inversion_verified,
        inversion_verification_source
    ) VALUES (
        p_source_signal_id,
        p_source_plan_id,
        p_source_module,
        p_signal_class,
        p_instrument,
        p_direction,
        p_confidence,
        p_cpto_decision,
        p_decision_rationale,
        p_refusal_reason,
        p_refusal_category,
        p_mid_market_price,
        p_calculated_entry_price,
        p_slippage_saved_bps,
        p_regime,
        p_regime_confidence,
        p_regime_snapshot_hash,
        p_parameter_version,
        p_parameter_hash,
        p_defcon,
        p_defcon_behavior,
        p_valid_until,
        p_ttl_remaining,
        p_ttl_passed,
        p_is_inversion,
        p_inversion_verified,
        p_inversion_source
    ) RETURNING evaluation_id INTO v_eval_id;

    RETURN v_eval_id;
END;
$$ LANGUAGE plpgsql;

-- Step 3: Create view for learning metrics
CREATE OR REPLACE VIEW fhq_research.v_cpto_learning_metrics AS
SELECT
    date_trunc('hour', created_at) as hour,
    regime_at_evaluation as regime,
    cpto_decision,
    refusal_category,
    COUNT(*) as signal_count,
    AVG(slippage_saved_bps) as avg_slippage_saved_bps,
    AVG(confidence) as avg_confidence,
    SUM(CASE WHEN ttl_check_passed THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0) as ttl_pass_rate,
    SUM(CASE WHEN is_inversion_candidate THEN 1 ELSE 0 END) as inversion_candidates,
    SUM(CASE WHEN is_inversion_candidate AND inversion_verified THEN 1 ELSE 0 END) as inversions_verified
FROM fhq_research.evaluations
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, signal_count DESC;

-- Step 4: Create view for LVI (Learning Velocity Index) contribution
CREATE OR REPLACE VIEW fhq_research.v_lvi_contribution AS
SELECT
    date_trunc('day', created_at) as day,
    COUNT(*) as total_evaluations,
    SUM(CASE WHEN cpto_decision = 'ACCEPTED' THEN 1 ELSE 0 END) as accepted,
    SUM(CASE WHEN cpto_decision LIKE 'BLOCKED%' THEN 1 ELSE 0 END) as blocked,
    -- LVI components
    AVG(slippage_saved_bps) as avg_slippage_saved,
    COUNT(DISTINCT regime_at_evaluation) as regime_diversity,
    COUNT(DISTINCT instrument) as instrument_diversity,
    -- Quality metrics
    AVG(CASE WHEN ttl_check_passed THEN 1.0 ELSE 0.0 END) as ttl_compliance,
    AVG(confidence) as avg_confidence
FROM fhq_research.evaluations
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY 1 DESC;

-- Step 5: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    vega_reviewed
) VALUES (
    'LEARNING_LOOP_CLOSURE',
    'CEO-DIR-2026-111-PHASE-5',
    'LEARNING_INFRASTRUCTURE',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO-DIR-2026-111 Phase 5: Learning loop closure implemented. ' ||
    'Every CPTO-evaluated signal recorded in fhq_research.evaluations. ' ||
    'Includes: decision rationale, slippage saved, refusal reason, ' ||
    'regime snapshot, parameter version hash. ' ||
    'Feeds Brier decomposition and Learning Velocity Index (LVI) with live-regime data.',
    jsonb_build_object(
        'directive', 'CEO-DIR-2026-111',
        'phase', 5,
        'table_created', 'fhq_research.evaluations',
        'learning_metrics', ARRAY[
            'Decision rationale',
            'Slippage saved (bps)',
            'Refusal reason (TTL/Liquidity/DEFCON)',
            'Regime snapshot with hash',
            'Parameter version hash',
            'LVI contribution',
            'Brier decomposition data'
        ],
        'views_created', ARRAY[
            'v_cpto_learning_metrics',
            'v_lvi_contribution'
        ]
    ),
    false
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify evaluations table exists
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'fhq_research' AND table_name = 'evaluations'
ORDER BY ordinal_position
LIMIT 10;

-- Verify function exists
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'fhq_research' AND routine_name = 'log_cpto_evaluation';
