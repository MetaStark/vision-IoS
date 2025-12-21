-- Migration 167: EQS 2.0 Shadow Evaluation Infrastructure
-- CEO Directive: CEO-EQS-2-2025-12-21
-- Purpose: Parallel shadow evaluation pipeline for EQS 2.0
-- Mode: SHADOW / READ-ONLY / NO EXECUTION INFLUENCE
-- Classification: GOVERNANCE-CRITICAL · RESEARCH-ONLY

-- ============================================================================
-- GOVERNING PRINCIPLE
-- ============================================================================
-- "We evaluate the evaluator before we trust the evaluator."
--
-- EQS 2.0 runs in shadow mode alongside EQS 1.0. All hypotheses evaluated by
-- both systems. Results logged but NOT used for promotion decisions until
-- G4 CEO directive authorizes EQS 2.0 activation.
--
-- CONSTRAINTS (NON-NEGOTIABLE):
-- 1. Shadow mode only - no execution influence
-- 2. EQS 1.0 remains decision authority
-- 3. All EQS 2.0 scores logged with full breakdown
-- 4. Shadow Ledger count (N) used for Phase B overfitting penalty
-- ============================================================================

-- SCHEMA: fhq_research
-- TABLE: eqs2_shadow_evaluations
-- PURPOSE: Shadow log of all EQS 2.0 evaluations

CREATE TABLE IF NOT EXISTS fhq_research.eqs2_shadow_evaluations (
    evaluation_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Hypothesis Identity
    hypothesis_hash         TEXT NOT NULL,  -- SHA-256 for linking
    target_asset            TEXT NOT NULL,
    hypothesis_title        TEXT NOT NULL,
    hypothesis_statement    TEXT NOT NULL,

    -- EQS 1.0 Baseline (for comparison)
    eqs1_score              NUMERIC(5,4) NOT NULL,
    eqs1_decision           TEXT NOT NULL,  -- ACCEPT, LOG_ONLY, REJECT

    -- EQS 2.0 Phase A: Semantic & Logical Consistency
    phase_a_score           NUMERIC(5,4),
    phase_a_passed          BOOLEAN,
    phase_a_breakdown       JSONB,
    -- Example: {"semantic_coherence": 0.90, "logical_consistency": 0.85, "adversarial_probe": 0.80}

    -- EQS 2.0 Phase B: Regime-Conditioned Statistical Robustness
    phase_b_score           NUMERIC(5,4),
    phase_b_passed          BOOLEAN,
    phase_b_breakdown       JSONB,
    -- Example: {"regime_prior": 0.85, "shadow_ledger_penalty": -0.10, "statistical_significance": 0.75}
    shadow_ledger_n         INTEGER,  -- Count of similar rejections in shadow ledger
    overfitting_penalty     NUMERIC(5,4),

    -- EQS 2.0 Phase C: Economic & Microstructure Coherence
    phase_c_score           NUMERIC(5,4),
    phase_c_passed          BOOLEAN,
    phase_c_breakdown       JSONB,
    -- Example: {"bid_ask_feasibility": 0.90, "latency_assumption": 0.85, "slippage_estimate": 0.80}

    -- EQS 2.0 Final Score
    eqs2_final_score        NUMERIC(5,4),
    eqs2_decision           TEXT,  -- WOULD_ACCEPT, WOULD_LOG, WOULD_REJECT
    eqs2_confidence         TEXT,  -- HIGH, MEDIUM, LOW

    -- Divergence Analysis
    eqs_divergence          NUMERIC(5,4),  -- ABS(eqs2 - eqs1)
    divergence_category     TEXT,  -- AGREEMENT, MILD_DIVERGENCE, SIGNIFICANT_DIVERGENCE

    -- Market Context at Evaluation
    market_context          JSONB NOT NULL,

    -- Lineage
    model_version           TEXT NOT NULL DEFAULT 'EQS2-SHADOW-2025-12',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- INDEXING FOR SHADOW ANALYSIS
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_eqs2_asset
    ON fhq_research.eqs2_shadow_evaluations(target_asset);

CREATE INDEX IF NOT EXISTS idx_eqs2_divergence
    ON fhq_research.eqs2_shadow_evaluations(eqs_divergence DESC);

CREATE INDEX IF NOT EXISTS idx_eqs2_timestamp
    ON fhq_research.eqs2_shadow_evaluations(evaluation_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_eqs2_decision
    ON fhq_research.eqs2_shadow_evaluations(eqs1_decision, eqs2_decision);

-- GIN index for phase breakdowns
CREATE INDEX IF NOT EXISTS idx_eqs2_phase_a
    ON fhq_research.eqs2_shadow_evaluations USING GIN (phase_a_breakdown);

CREATE INDEX IF NOT EXISTS idx_eqs2_phase_b
    ON fhq_research.eqs2_shadow_evaluations USING GIN (phase_b_breakdown);

CREATE INDEX IF NOT EXISTS idx_eqs2_phase_c
    ON fhq_research.eqs2_shadow_evaluations USING GIN (phase_c_breakdown);

-- ============================================================================
-- COMMENTS (Governance Documentation)
-- ============================================================================

COMMENT ON TABLE fhq_research.eqs2_shadow_evaluations IS
'Shadow evaluation log for EQS 2.0 parallel pipeline.
CEO Directive: CEO-EQS-2-2025-12-21

MODE: Shadow / Read-Only / No Execution Influence

EQS 2.0 PHASES:
- Phase A: Semantic & Logical Consistency (gatekeeper)
- Phase B: Regime-Conditioned Statistical Robustness (overfitting penalty)
- Phase C: Economic & Microstructure Coherence (execution feasibility)

PURPOSE: Evaluate EQS 2.0 against EQS 1.0 without affecting promotion decisions.
Divergence analysis enables future calibration.';

COMMENT ON COLUMN fhq_research.eqs2_shadow_evaluations.shadow_ledger_n IS
'Count of similar hypotheses in rejected_hypotheses shadow ledger.
High N suggests pattern has been seen and rejected before -> overfitting risk.';

COMMENT ON COLUMN fhq_research.eqs2_shadow_evaluations.overfitting_penalty IS
'Penalty applied based on shadow_ledger_n.
Formula: penalty = min(0.15, 0.02 * log2(N+1))
Reflects thesis: frequently rejected patterns may be overfitted.';

COMMENT ON COLUMN fhq_research.eqs2_shadow_evaluations.divergence_category IS
'Classification of EQS1 vs EQS2 disagreement.
AGREEMENT: |divergence| < 0.10
MILD_DIVERGENCE: 0.10 <= |divergence| < 0.20
SIGNIFICANT_DIVERGENCE: |divergence| >= 0.20';

-- ============================================================================
-- HELPER FUNCTION: Log EQS 2.0 Shadow Evaluation
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.log_eqs2_shadow_evaluation(
    p_hypothesis_hash TEXT,
    p_target_asset TEXT,
    p_hypothesis_title TEXT,
    p_hypothesis_statement TEXT,
    p_eqs1_score NUMERIC,
    p_eqs1_decision TEXT,
    p_phase_a_score NUMERIC,
    p_phase_a_passed BOOLEAN,
    p_phase_a_breakdown JSONB,
    p_phase_b_score NUMERIC,
    p_phase_b_passed BOOLEAN,
    p_phase_b_breakdown JSONB,
    p_shadow_ledger_n INTEGER,
    p_overfitting_penalty NUMERIC,
    p_phase_c_score NUMERIC,
    p_phase_c_passed BOOLEAN,
    p_phase_c_breakdown JSONB,
    p_eqs2_final_score NUMERIC,
    p_eqs2_decision TEXT,
    p_eqs2_confidence TEXT,
    p_market_context JSONB
)
RETURNS UUID
LANGUAGE plpgsql
AS $function$
DECLARE
    v_evaluation_id UUID;
    v_divergence NUMERIC;
    v_divergence_category TEXT;
BEGIN
    -- Calculate divergence
    v_divergence := ABS(p_eqs2_final_score - p_eqs1_score);

    -- Classify divergence
    IF v_divergence < 0.10 THEN
        v_divergence_category := 'AGREEMENT';
    ELSIF v_divergence < 0.20 THEN
        v_divergence_category := 'MILD_DIVERGENCE';
    ELSE
        v_divergence_category := 'SIGNIFICANT_DIVERGENCE';
    END IF;

    INSERT INTO fhq_research.eqs2_shadow_evaluations (
        hypothesis_hash,
        target_asset,
        hypothesis_title,
        hypothesis_statement,
        eqs1_score,
        eqs1_decision,
        phase_a_score,
        phase_a_passed,
        phase_a_breakdown,
        phase_b_score,
        phase_b_passed,
        phase_b_breakdown,
        shadow_ledger_n,
        overfitting_penalty,
        phase_c_score,
        phase_c_passed,
        phase_c_breakdown,
        eqs2_final_score,
        eqs2_decision,
        eqs2_confidence,
        eqs_divergence,
        divergence_category,
        market_context
    ) VALUES (
        p_hypothesis_hash,
        p_target_asset,
        p_hypothesis_title,
        p_hypothesis_statement,
        p_eqs1_score,
        p_eqs1_decision,
        p_phase_a_score,
        p_phase_a_passed,
        p_phase_a_breakdown,
        p_phase_b_score,
        p_phase_b_passed,
        p_phase_b_breakdown,
        p_shadow_ledger_n,
        p_overfitting_penalty,
        p_phase_c_score,
        p_phase_c_passed,
        p_phase_c_breakdown,
        p_eqs2_final_score,
        p_eqs2_decision,
        p_eqs2_confidence,
        v_divergence,
        v_divergence_category,
        p_market_context
    ) RETURNING evaluation_id INTO v_evaluation_id;

    RETURN v_evaluation_id;
END;
$function$;

COMMENT ON FUNCTION fhq_research.log_eqs2_shadow_evaluation IS
'FINN-only function to log EQS 2.0 shadow evaluations.
CEO Directive: CEO-EQS-2-2025-12-21
Mode: Shadow / Read-Only / No Execution Influence';

-- ============================================================================
-- HELPER FUNCTION: Get Shadow Ledger Count for Asset
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_research.get_shadow_ledger_count(
    p_target_asset TEXT,
    p_lookback_days INTEGER DEFAULT 30
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $function$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM fhq_research.rejected_hypotheses
    WHERE target_asset = p_target_asset
      AND rejection_timestamp > NOW() - (p_lookback_days || ' days')::INTERVAL;

    RETURN COALESCE(v_count, 0);
END;
$function$;

COMMENT ON FUNCTION fhq_research.get_shadow_ledger_count IS
'Returns count of rejected hypotheses for an asset in shadow ledger.
Used by EQS 2.0 Phase B for overfitting penalty calculation.';

-- ============================================================================
-- VIEW: EQS Divergence Analysis
-- ============================================================================

CREATE OR REPLACE VIEW fhq_research.v_eqs_divergence_analysis AS
SELECT
    evaluation_timestamp::DATE AS eval_date,
    target_asset,
    COUNT(*) AS evaluations,
    AVG(eqs1_score) AS avg_eqs1,
    AVG(eqs2_final_score) AS avg_eqs2,
    AVG(eqs_divergence) AS avg_divergence,
    SUM(CASE WHEN divergence_category = 'AGREEMENT' THEN 1 ELSE 0 END) AS agreements,
    SUM(CASE WHEN divergence_category = 'MILD_DIVERGENCE' THEN 1 ELSE 0 END) AS mild_divergences,
    SUM(CASE WHEN divergence_category = 'SIGNIFICANT_DIVERGENCE' THEN 1 ELSE 0 END) AS significant_divergences,
    SUM(CASE WHEN eqs1_decision = 'ACCEPT' AND eqs2_decision = 'WOULD_REJECT' THEN 1 ELSE 0 END) AS eqs1_accept_eqs2_reject,
    SUM(CASE WHEN eqs1_decision = 'REJECT' AND eqs2_decision = 'WOULD_ACCEPT' THEN 1 ELSE 0 END) AS eqs1_reject_eqs2_accept
FROM fhq_research.eqs2_shadow_evaluations
GROUP BY eval_date, target_asset
ORDER BY eval_date DESC, target_asset;

COMMENT ON VIEW fhq_research.v_eqs_divergence_analysis IS
'Divergence analysis between EQS 1.0 and EQS 2.0 shadow evaluations.
Key metric: eqs1_accept_eqs2_reject shows hypotheses that EQS 2.0 would have filtered.';

-- ============================================================================
-- GOVERNANCE LOG
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'MIGRATION_EXECUTED',
    'fhq_research.eqs2_shadow_evaluations',
    'SCHEMA_CREATION',
    'CEO_DIRECTIVE',
    'APPROVED',
    'CEO-EQS-2-2025-12-21: EQS 2.0 Shadow Evaluation Pipeline',
    'STIG',
    jsonb_build_object(
        'migration_id', '167_eqs2_shadow_evaluation',
        'directive', 'CEO-EQS-2-2025-12-21',
        'mode', 'SHADOW_READ_ONLY',
        'phases', jsonb_build_array(
            'Phase A: Semantic & Logical Consistency',
            'Phase B: Regime-Conditioned Statistical Robustness',
            'Phase C: Economic & Microstructure Coherence'
        ),
        'constraints', jsonb_build_array(
            'Shadow mode only',
            'EQS 1.0 remains decision authority',
            'No execution influence',
            'Divergence logging for calibration'
        ),
        'executed_at', NOW()
    )
);
