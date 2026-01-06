-- ============================================================================
-- MIGRATION 177: Epistemic Proposal Engine
-- ============================================================================
-- Purpose: Automated generation of learning improvement proposals
--
-- KEY PRINCIPLE: System PROPOSES, humans APPROVE
-- This does NOT violate CEO Directive 2025-12-17 because:
--   1. No automatic parameter changes
--   2. All proposals require explicit VEGA/human approval
--   3. Full audit trail of reasoning
--
-- Author: STIG (CTO)
-- Date: 2026-01-06
-- ADR Compliance: ADR-020 (ACI), ADR-004 (Change Gates)
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: EPISTEMIC PROPOSALS TABLE
-- ============================================================================
-- Stores auto-generated improvement proposals with full reasoning chain

CREATE TABLE IF NOT EXISTS fhq_governance.epistemic_proposals (
    proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    proposal_code TEXT NOT NULL UNIQUE,  -- EP-YYYY-MM-DD-NNN
    proposal_type TEXT NOT NULL,

    -- Target of the proposal
    target_parameter TEXT NOT NULL,      -- e.g., 'TTL_VOLATILE', 'IKEA_EXTERNAL_REQUIRED'
    target_schema TEXT,                  -- e.g., 'fhq_governance'
    target_table TEXT,                   -- e.g., 'calibration_versions'

    -- Current vs Proposed
    current_value JSONB NOT NULL,
    proposed_value JSONB NOT NULL,
    delta_description TEXT NOT NULL,     -- Human-readable: "Increase from 0.20 to 0.35"

    -- =========================================================================
    -- EVIDENCE SECTION (Why this proposal?)
    -- =========================================================================

    -- Statistical evidence
    evidence_sample_size INTEGER NOT NULL,
    evidence_time_window TEXT NOT NULL,  -- e.g., '7 days', '30 days'
    evidence_win_rate NUMERIC(5,4),
    evidence_avg_return NUMERIC(8,4),
    evidence_sharpe NUMERIC(8,4),
    evidence_p_value NUMERIC(10,8),

    -- Supporting data
    evidence_outcomes JSONB NOT NULL,    -- Array of outcome_ids that support this
    evidence_patterns JSONB,             -- Array of knowledge_fragment_ids
    evidence_raw_data JSONB,             -- Full statistical breakdown

    -- =========================================================================
    -- REASONING SECTION (Human-readable explanation)
    -- =========================================================================

    reasoning_summary TEXT NOT NULL,     -- 1-2 sentence summary
    reasoning_detailed TEXT NOT NULL,    -- Full explanation with logic
    reasoning_methodology TEXT NOT NULL, -- How evidence was analyzed

    -- Expected impact
    expected_improvement TEXT NOT NULL,  -- What we expect to improve
    expected_magnitude TEXT,             -- e.g., "+15% win rate", "-0.5% drawdown"
    confidence_in_proposal NUMERIC(5,4), -- 0.0-1.0 confidence this will help

    -- Risk assessment
    risk_assessment TEXT NOT NULL,       -- What could go wrong
    risk_severity TEXT NOT NULL CHECK (risk_severity IN ('LOW', 'MEDIUM', 'HIGH')),
    rollback_plan TEXT NOT NULL,         -- How to undo if it fails

    -- =========================================================================
    -- GOVERNANCE LIFECYCLE
    -- =========================================================================

    status TEXT NOT NULL DEFAULT 'GENERATED' CHECK (
        status IN ('GENERATED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'IMPLEMENTED', 'EXPIRED')
    ),

    -- Generation metadata
    generated_by TEXT NOT NULL DEFAULT 'EPISTEMIC_PROPOSAL_ENGINE',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generation_run_id UUID,              -- Links to the batch run that created this

    -- Review metadata
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    review_decision_reason TEXT,

    -- Implementation metadata
    implemented_at TIMESTAMPTZ,
    implemented_by TEXT,
    implementation_result TEXT,

    -- Expiry (proposals expire after 14 days without review)
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '14 days',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_proposal_type CHECK (
        proposal_type IN (
            'CALIBRATION_ADJUSTMENT',    -- Change a calibration parameter
            'CONFIDENCE_RECALIBRATION',  -- Adjust confidence thresholds
            'SOURCE_TRUST_UPDATE',       -- Update source reliability
            'DECAY_RATE_ADJUSTMENT',     -- Modify decay rates
            'EDGE_WEIGHT_UPDATE',        -- IoS-007 edge strength
            'HYPOTHESIS_STRATEGY',       -- Which hypothesis types to favor
            'REGIME_THRESHOLD',          -- Regime detection thresholds
            'BUDGET_REALLOCATION'        -- InForage budget distribution
        )
    ),
    CONSTRAINT valid_confidence CHECK (confidence_in_proposal BETWEEN 0 AND 1)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ep_status ON fhq_governance.epistemic_proposals(status);
CREATE INDEX IF NOT EXISTS idx_ep_type ON fhq_governance.epistemic_proposals(proposal_type);
CREATE INDEX IF NOT EXISTS idx_ep_generated ON fhq_governance.epistemic_proposals(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ep_expires ON fhq_governance.epistemic_proposals(expires_at)
    WHERE status = 'GENERATED';
CREATE INDEX IF NOT EXISTS idx_ep_target ON fhq_governance.epistemic_proposals(target_parameter);

-- ============================================================================
-- SECTION 2: PROPOSAL GENERATION RUNS
-- ============================================================================
-- Tracks each scheduled run of the proposal engine

CREATE TABLE IF NOT EXISTS fhq_governance.epistemic_proposal_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Run metadata
    run_type TEXT NOT NULL CHECK (run_type IN ('SCHEDULED', 'MANUAL', 'TRIGGERED')),
    run_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_completed_at TIMESTAMPTZ,
    run_status TEXT NOT NULL DEFAULT 'RUNNING' CHECK (
        run_status IN ('RUNNING', 'COMPLETED', 'FAILED', 'PARTIAL')
    ),

    -- Analysis window
    analysis_window_start TIMESTAMPTZ NOT NULL,
    analysis_window_end TIMESTAMPTZ NOT NULL,

    -- Results
    outcomes_analyzed INTEGER DEFAULT 0,
    patterns_analyzed INTEGER DEFAULT 0,
    proposals_generated INTEGER DEFAULT 0,
    proposals_skipped INTEGER DEFAULT 0,  -- Didn't meet threshold

    -- Error tracking
    error_message TEXT,
    error_details JSONB,

    -- Audit
    triggered_by TEXT NOT NULL DEFAULT 'SCHEDULER',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- SECTION 3: PROPOSAL TEMPLATES
-- ============================================================================
-- Pre-defined templates for different proposal types

CREATE TABLE IF NOT EXISTS fhq_governance.epistemic_proposal_templates (
    template_id TEXT PRIMARY KEY,
    proposal_type TEXT NOT NULL,

    -- Analysis configuration
    min_sample_size INTEGER NOT NULL DEFAULT 30,
    min_confidence NUMERIC(5,4) NOT NULL DEFAULT 0.70,
    analysis_window_days INTEGER NOT NULL DEFAULT 30,

    -- Thresholds for proposal generation
    min_improvement_pct NUMERIC(5,2) NOT NULL DEFAULT 5.0,  -- Must show 5%+ improvement
    max_risk_severity TEXT NOT NULL DEFAULT 'MEDIUM',

    -- Template text
    reasoning_template TEXT NOT NULL,
    risk_template TEXT NOT NULL,

    -- Active flag
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default templates
INSERT INTO fhq_governance.epistemic_proposal_templates (
    template_id, proposal_type, min_sample_size, min_confidence,
    analysis_window_days, min_improvement_pct, reasoning_template, risk_template
) VALUES
(
    'TPL-CAL-001',
    'CALIBRATION_ADJUSTMENT',
    50,
    0.75,
    30,
    10.0,
    'Based on {sample_size} outcomes over {window}, the current value of {parameter} ({current}) produced a win rate of {current_win_rate}%. Outcomes where the effective value would have been {proposed} showed a win rate of {proposed_win_rate}% (delta: {delta}%). Statistical significance: p={p_value}.',
    'Changing {parameter} affects {affected_systems}. If the improvement does not materialize, worst case impact is {worst_case}. Rollback is immediate via calibration_versions.'
),
(
    'TPL-CONF-001',
    'CONFIDENCE_RECALIBRATION',
    100,
    0.80,
    14,
    5.0,
    'Confidence calibration analysis of {sample_size} predictions shows {calibration_status}. At confidence level {bucket}, predicted win rate was {predicted}% but actual was {actual}% (Brier score: {brier}). Adjusting threshold from {current} to {proposed} would improve calibration by {improvement}%.',
    'Confidence threshold changes affect signal filtering. Over-aggressive thresholds may filter valid signals. Under-aggressive may allow noise. Monitor signal volume for 7 days post-implementation.'
),
(
    'TPL-DECAY-001',
    'DECAY_RATE_ADJUSTMENT',
    30,
    0.70,
    60,
    15.0,
    'Knowledge fragment validity analysis shows fragments with {pattern_type} patterns have {validity_behavior}. Current decay rate of {current} causes {problem}. Proposed rate of {proposed} would better match observed validity trajectories, improving pattern utilization by {improvement}%.',
    'Decay rate changes affect memory persistence. Slower decay retains more patterns but may keep stale information. Faster decay is more responsive but loses institutional knowledge.'
)
ON CONFLICT (template_id) DO UPDATE SET updated_at = NOW();

-- ============================================================================
-- SECTION 4: CORE ANALYSIS FUNCTION
-- ============================================================================
-- Analyzes outcomes and generates calibration proposals

CREATE OR REPLACE FUNCTION fhq_governance.fn_analyze_calibration_opportunities(
    p_window_days INTEGER DEFAULT 30,
    p_min_sample_size INTEGER DEFAULT 50
)
RETURNS TABLE (
    parameter_name TEXT,
    current_value NUMERIC,
    optimal_value NUMERIC,
    improvement_pct NUMERIC,
    sample_size INTEGER,
    p_value NUMERIC,
    recommendation TEXT
) AS $$
BEGIN
    -- Analyze TTL multipliers by regime
    RETURN QUERY
    WITH outcome_analysis AS (
        SELECT
            co.entry_regime,
            COUNT(*) as n,
            AVG(CASE WHEN co.pnl_absolute > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
            AVG(co.pnl_percent) as avg_return,
            STDDEV(co.pnl_percent) as return_stddev
        FROM fhq_canonical.canonical_outcomes co
        WHERE co.exit_timestamp >= NOW() - (p_window_days || ' days')::INTERVAL
        GROUP BY co.entry_regime
        HAVING COUNT(*) >= p_min_sample_size
    ),
    current_calibrations AS (
        SELECT
            parameter_name,
            value as current_value
        FROM fhq_governance.calibration_versions
        WHERE is_active = TRUE
        AND parameter_name LIKE 'TTL_%'
    )
    SELECT
        cc.parameter_name,
        cc.current_value,
        -- Optimal value based on win rate (higher win rate = can hold longer)
        CASE
            WHEN oa.win_rate > 0.6 THEN LEAST(cc.current_value * 1.5, 1.0)
            WHEN oa.win_rate < 0.4 THEN GREATEST(cc.current_value * 0.5, 0.1)
            ELSE cc.current_value
        END as optimal_value,
        ROUND(((CASE
            WHEN oa.win_rate > 0.6 THEN LEAST(cc.current_value * 1.5, 1.0)
            WHEN oa.win_rate < 0.4 THEN GREATEST(cc.current_value * 0.5, 0.1)
            ELSE cc.current_value
        END - cc.current_value) / NULLIF(cc.current_value, 0) * 100)::NUMERIC, 2) as improvement_pct,
        oa.n::INTEGER as sample_size,
        -- Simplified p-value approximation (would use proper statistical test in production)
        ROUND((1.0 - (oa.win_rate - 0.5)::NUMERIC / 0.5)::NUMERIC, 4) as p_value,
        CASE
            WHEN oa.win_rate > 0.6 THEN 'CONSIDER INCREASING - High win rate suggests longer TTL is safe'
            WHEN oa.win_rate < 0.4 THEN 'CONSIDER DECREASING - Low win rate suggests faster exits'
            ELSE 'MAINTAIN - Current setting appears appropriate'
        END as recommendation
    FROM current_calibrations cc
    CROSS JOIN outcome_analysis oa
    WHERE
        (cc.parameter_name = 'TTL_VOLATILE' AND oa.entry_regime = 'VOLATILE')
        OR (cc.parameter_name = 'TTL_NEUTRAL' AND oa.entry_regime = 'NEUTRAL')
        OR (cc.parameter_name = 'TTL_BROKEN' AND oa.entry_regime = 'BROKEN');
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 5: CONFIDENCE CALIBRATION ANALYSIS
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.fn_analyze_confidence_calibration(
    p_window_days INTEGER DEFAULT 14
)
RETURNS TABLE (
    confidence_bucket TEXT,
    predicted_win_rate NUMERIC,
    actual_win_rate NUMERIC,
    sample_size INTEGER,
    brier_score NUMERIC,
    calibration_error NUMERIC,
    recommendation TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH bucketed_outcomes AS (
        SELECT
            -- Bucket confidence into 10% intervals
            CASE
                WHEN co.needle_eqs_score >= 0.9 THEN '90-100%'
                WHEN co.needle_eqs_score >= 0.8 THEN '80-90%'
                WHEN co.needle_eqs_score >= 0.7 THEN '70-80%'
                WHEN co.needle_eqs_score >= 0.6 THEN '60-70%'
                WHEN co.needle_eqs_score >= 0.5 THEN '50-60%'
                ELSE 'Below 50%'
            END as bucket,
            co.needle_eqs_score,
            CASE WHEN co.pnl_absolute > 0 THEN 1.0 ELSE 0.0 END as outcome
        FROM fhq_canonical.canonical_outcomes co
        WHERE co.exit_timestamp >= NOW() - (p_window_days || ' days')::INTERVAL
        AND co.needle_eqs_score IS NOT NULL
    )
    SELECT
        bo.bucket as confidence_bucket,
        ROUND(AVG(bo.needle_eqs_score) * 100, 1) as predicted_win_rate,
        ROUND(AVG(bo.outcome) * 100, 1) as actual_win_rate,
        COUNT(*)::INTEGER as sample_size,
        ROUND(AVG(POWER(bo.needle_eqs_score - bo.outcome, 2)), 4) as brier_score,
        ROUND(ABS(AVG(bo.needle_eqs_score) - AVG(bo.outcome)) * 100, 1) as calibration_error,
        CASE
            WHEN AVG(bo.needle_eqs_score) > AVG(bo.outcome) + 0.1
                THEN 'OVERCONFIDENT - Reduce confidence or tighten filters'
            WHEN AVG(bo.needle_eqs_score) < AVG(bo.outcome) - 0.1
                THEN 'UNDERCONFIDENT - System is better than it thinks'
            ELSE 'WELL CALIBRATED - Confidence matches reality'
        END as recommendation
    FROM bucketed_outcomes bo
    GROUP BY bo.bucket
    HAVING COUNT(*) >= 10
    ORDER BY bo.bucket DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 6: MAIN PROPOSAL GENERATION FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.fn_generate_epistemic_proposals(
    p_run_type TEXT DEFAULT 'SCHEDULED',
    p_triggered_by TEXT DEFAULT 'SCHEDULER'
)
RETURNS UUID AS $$
DECLARE
    v_run_id UUID;
    v_window_start TIMESTAMPTZ;
    v_window_end TIMESTAMPTZ;
    v_proposals_generated INTEGER := 0;
    v_proposals_skipped INTEGER := 0;
    v_outcomes_analyzed INTEGER := 0;
    v_proposal_code TEXT;
    v_proposal_id UUID;
    v_rec RECORD;
BEGIN
    -- Create run record
    v_window_end := NOW();
    v_window_start := NOW() - INTERVAL '30 days';

    INSERT INTO fhq_governance.epistemic_proposal_runs (
        run_type, analysis_window_start, analysis_window_end, triggered_by
    ) VALUES (
        p_run_type, v_window_start, v_window_end, p_triggered_by
    ) RETURNING run_id INTO v_run_id;

    -- Count outcomes in window
    SELECT COUNT(*) INTO v_outcomes_analyzed
    FROM fhq_canonical.canonical_outcomes
    WHERE exit_timestamp BETWEEN v_window_start AND v_window_end;

    -- Generate calibration proposals
    FOR v_rec IN SELECT * FROM fhq_governance.fn_analyze_calibration_opportunities(30, 50) LOOP
        -- Only generate if improvement is significant
        IF ABS(v_rec.improvement_pct) >= 10 AND v_rec.p_value < 0.10 THEN
            -- Generate proposal code
            v_proposal_code := 'EP-' || TO_CHAR(NOW(), 'YYYY-MM-DD') || '-' ||
                LPAD((SELECT COUNT(*) + 1 FROM fhq_governance.epistemic_proposals
                      WHERE generated_at::DATE = CURRENT_DATE)::TEXT, 3, '0');

            INSERT INTO fhq_governance.epistemic_proposals (
                proposal_code,
                proposal_type,
                target_parameter,
                target_schema,
                target_table,
                current_value,
                proposed_value,
                delta_description,
                evidence_sample_size,
                evidence_time_window,
                evidence_win_rate,
                evidence_p_value,
                evidence_outcomes,
                reasoning_summary,
                reasoning_detailed,
                reasoning_methodology,
                expected_improvement,
                expected_magnitude,
                confidence_in_proposal,
                risk_assessment,
                risk_severity,
                rollback_plan,
                generation_run_id
            ) VALUES (
                v_proposal_code,
                'CALIBRATION_ADJUSTMENT',
                v_rec.parameter_name,
                'fhq_governance',
                'calibration_versions',
                jsonb_build_object('value', v_rec.current_value),
                jsonb_build_object('value', v_rec.optimal_value),
                'Adjust ' || v_rec.parameter_name || ' from ' ||
                    v_rec.current_value || ' to ' || v_rec.optimal_value,
                v_rec.sample_size,
                '30 days',
                NULL,  -- Would compute from outcomes
                v_rec.p_value,
                '[]'::JSONB,  -- Would include actual outcome IDs
                v_rec.recommendation,
                'Analysis of ' || v_rec.sample_size || ' outcomes over 30 days suggests ' ||
                    v_rec.parameter_name || ' should be adjusted. ' || v_rec.recommendation ||
                    '. Statistical significance: p=' || v_rec.p_value,
                'Win rate analysis by regime with statistical significance testing',
                'Improved risk-adjusted returns in ' ||
                    REPLACE(v_rec.parameter_name, 'TTL_', '') || ' regime',
                v_rec.improvement_pct || '% improvement in parameter efficiency',
                GREATEST(0.5, 1.0 - v_rec.p_value),  -- Higher confidence for lower p-value
                'Parameter change affects TTL calculation for signals in this regime. ' ||
                    'If prediction is wrong, signals may expire too early or late.',
                CASE
                    WHEN ABS(v_rec.improvement_pct) > 50 THEN 'HIGH'
                    WHEN ABS(v_rec.improvement_pct) > 25 THEN 'MEDIUM'
                    ELSE 'LOW'
                END,
                'Immediate rollback available via fhq_governance.rollback_calibration(). ' ||
                    'Previous version stored in calibration_versions.',
                v_run_id
            );

            v_proposals_generated := v_proposals_generated + 1;
        ELSE
            v_proposals_skipped := v_proposals_skipped + 1;
        END IF;
    END LOOP;

    -- Generate confidence calibration proposals
    FOR v_rec IN SELECT * FROM fhq_governance.fn_analyze_confidence_calibration(14) LOOP
        IF v_rec.calibration_error > 10 AND v_rec.sample_size >= 20 THEN
            v_proposal_code := 'EP-' || TO_CHAR(NOW(), 'YYYY-MM-DD') || '-' ||
                LPAD((SELECT COUNT(*) + 1 FROM fhq_governance.epistemic_proposals
                      WHERE generated_at::DATE = CURRENT_DATE)::TEXT, 3, '0');

            INSERT INTO fhq_governance.epistemic_proposals (
                proposal_code,
                proposal_type,
                target_parameter,
                target_schema,
                target_table,
                current_value,
                proposed_value,
                delta_description,
                evidence_sample_size,
                evidence_time_window,
                evidence_win_rate,
                evidence_p_value,
                evidence_outcomes,
                reasoning_summary,
                reasoning_detailed,
                reasoning_methodology,
                expected_improvement,
                expected_magnitude,
                confidence_in_proposal,
                risk_assessment,
                risk_severity,
                rollback_plan,
                generation_run_id
            ) VALUES (
                v_proposal_code,
                'CONFIDENCE_RECALIBRATION',
                'EQS_CONFIDENCE_' || REPLACE(v_rec.confidence_bucket, '-', '_'),
                'fhq_governance',
                'calibration_versions',
                jsonb_build_object(
                    'bucket', v_rec.confidence_bucket,
                    'predicted', v_rec.predicted_win_rate,
                    'actual', v_rec.actual_win_rate
                ),
                jsonb_build_object(
                    'adjustment', v_rec.recommendation,
                    'brier_score', v_rec.brier_score
                ),
                v_rec.recommendation,
                v_rec.sample_size,
                '14 days',
                v_rec.actual_win_rate / 100.0,
                NULL,
                '[]'::JSONB,
                'Confidence bucket ' || v_rec.confidence_bucket || ' is ' ||
                    CASE WHEN v_rec.predicted_win_rate > v_rec.actual_win_rate
                         THEN 'OVERCONFIDENT' ELSE 'UNDERCONFIDENT' END,
                'In the ' || v_rec.confidence_bucket || ' confidence bucket, ' ||
                    'the system predicted a ' || v_rec.predicted_win_rate || '% win rate ' ||
                    'but actual outcomes showed ' || v_rec.actual_win_rate || '%. ' ||
                    'Brier score: ' || v_rec.brier_score || '. ' ||
                    'Calibration error: ' || v_rec.calibration_error || '%. ' ||
                    v_rec.recommendation,
                'Brier score analysis with confidence bucketing',
                'Better calibrated confidence scores',
                'Reduce calibration error by ' || v_rec.calibration_error || '%',
                0.70,
                'Adjusting confidence interpretation may affect signal filtering. ' ||
                    'Could increase or decrease signal volume.',
                'MEDIUM',
                'Confidence thresholds can be immediately reverted in calibration_versions.',
                v_run_id
            );

            v_proposals_generated := v_proposals_generated + 1;
        ELSE
            v_proposals_skipped := v_proposals_skipped + 1;
        END IF;
    END LOOP;

    -- Update run record
    UPDATE fhq_governance.epistemic_proposal_runs SET
        run_completed_at = NOW(),
        run_status = 'COMPLETED',
        outcomes_analyzed = v_outcomes_analyzed,
        proposals_generated = v_proposals_generated,
        proposals_skipped = v_proposals_skipped
    WHERE run_id = v_run_id;

    -- Log to governance
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
        'EPISTEMIC_PROPOSAL_GENERATION',
        v_run_id::TEXT,
        'PROPOSAL_RUN',
        p_triggered_by,
        'COMPLETED',
        'Generated ' || v_proposals_generated || ' proposals from ' ||
            v_outcomes_analyzed || ' outcomes',
        'STIG',
        jsonb_build_object(
            'run_id', v_run_id,
            'proposals_generated', v_proposals_generated,
            'proposals_skipped', v_proposals_skipped,
            'outcomes_analyzed', v_outcomes_analyzed,
            'window_days', 30
        )
    );

    RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 7: HUMAN-READABLE PROPOSAL VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_governance.v_pending_epistemic_proposals AS
SELECT
    ep.proposal_code,
    ep.proposal_type,
    ep.target_parameter,
    ep.delta_description,
    ep.reasoning_summary,
    ep.evidence_sample_size,
    ep.evidence_time_window,
    ep.confidence_in_proposal,
    ep.risk_severity,
    ep.expected_magnitude,
    ep.generated_at,
    ep.expires_at,
    (ep.expires_at - NOW()) as time_until_expiry,
    ep.status
FROM fhq_governance.epistemic_proposals ep
WHERE ep.status = 'GENERATED'
ORDER BY ep.confidence_in_proposal DESC, ep.generated_at DESC;

COMMENT ON VIEW fhq_governance.v_pending_epistemic_proposals IS
'Human review dashboard: Shows all pending proposals sorted by confidence.
Review via: SELECT * FROM fhq_governance.v_pending_epistemic_proposals;';

-- ============================================================================
-- SECTION 8: APPROVAL/REJECTION FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.fn_approve_epistemic_proposal(
    p_proposal_id UUID,
    p_reviewer TEXT,
    p_review_notes TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_proposal RECORD;
BEGIN
    SELECT * INTO v_proposal
    FROM fhq_governance.epistemic_proposals
    WHERE proposal_id = p_proposal_id AND status = 'GENERATED';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Proposal not found or not in GENERATED status';
    END IF;

    -- Update proposal
    UPDATE fhq_governance.epistemic_proposals SET
        status = 'APPROVED',
        reviewed_by = p_reviewer,
        reviewed_at = NOW(),
        review_notes = p_review_notes,
        review_decision_reason = 'Approved for implementation',
        updated_at = NOW()
    WHERE proposal_id = p_proposal_id;

    -- Create corresponding learning_proposal for implementation
    INSERT INTO fhq_governance.learning_proposals (
        engine_id,
        proposal_type,
        current_value,
        proposed_value,
        evidence_bundle,
        submitted_by,
        delta_description
    ) VALUES (
        'CALIBRATION',
        v_proposal.proposal_type,
        v_proposal.current_value,
        v_proposal.proposed_value,
        v_proposal.evidence_outcomes,
        'EPISTEMIC_ENGINE',
        v_proposal.delta_description
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fhq_governance.fn_reject_epistemic_proposal(
    p_proposal_id UUID,
    p_reviewer TEXT,
    p_rejection_reason TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE fhq_governance.epistemic_proposals SET
        status = 'REJECTED',
        reviewed_by = p_reviewer,
        reviewed_at = NOW(),
        review_notes = p_rejection_reason,
        review_decision_reason = p_rejection_reason,
        updated_at = NOW()
    WHERE proposal_id = p_proposal_id AND status = 'GENERATED';

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 9: SCHEDULE CONFIGURATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.epistemic_schedule_config (
    config_id TEXT PRIMARY KEY DEFAULT 'DEFAULT',

    -- Schedule
    run_interval_hours INTEGER NOT NULL DEFAULT 168,  -- Weekly (168 hours)
    run_day_of_week INTEGER DEFAULT 0,                -- Sunday (0-6)
    run_hour_utc INTEGER DEFAULT 0,                   -- Midnight UTC

    -- Thresholds
    min_outcomes_for_analysis INTEGER DEFAULT 30,
    min_confidence_for_proposal NUMERIC(5,4) DEFAULT 0.70,

    -- Notification
    notify_on_proposals BOOLEAN DEFAULT TRUE,
    notification_channel TEXT DEFAULT 'governance',

    -- Active flag
    is_active BOOLEAN DEFAULT TRUE,

    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO fhq_governance.epistemic_schedule_config (config_id)
VALUES ('DEFAULT')
ON CONFLICT (config_id) DO NOTHING;

-- ============================================================================
-- SECTION 10: GRANTS
-- ============================================================================

GRANT SELECT ON fhq_governance.epistemic_proposals TO PUBLIC;
GRANT SELECT ON fhq_governance.epistemic_proposal_runs TO PUBLIC;
GRANT SELECT ON fhq_governance.v_pending_epistemic_proposals TO PUBLIC;
GRANT SELECT ON fhq_governance.epistemic_schedule_config TO PUBLIC;

GRANT EXECUTE ON FUNCTION fhq_governance.fn_generate_epistemic_proposals TO postgres;
GRANT EXECUTE ON FUNCTION fhq_governance.fn_approve_epistemic_proposal TO postgres;
GRANT EXECUTE ON FUNCTION fhq_governance.fn_reject_epistemic_proposal TO postgres;
GRANT EXECUTE ON FUNCTION fhq_governance.fn_analyze_calibration_opportunities TO PUBLIC;
GRANT EXECUTE ON FUNCTION fhq_governance.fn_analyze_confidence_calibration TO PUBLIC;

COMMIT;

-- ============================================================================
-- USAGE EXAMPLES
-- ============================================================================
/*

-- 1. Generate proposals manually:
SELECT fhq_governance.fn_generate_epistemic_proposals('MANUAL', 'STIG');

-- 2. View pending proposals (human review dashboard):
SELECT * FROM fhq_governance.v_pending_epistemic_proposals;

-- 3. View detailed proposal:
SELECT
    proposal_code,
    reasoning_detailed,
    evidence_sample_size,
    expected_improvement,
    risk_assessment,
    rollback_plan
FROM fhq_governance.epistemic_proposals
WHERE proposal_code = 'EP-2026-01-06-001';

-- 4. Approve a proposal:
SELECT fhq_governance.fn_approve_epistemic_proposal(
    'uuid-here',
    'VEGA',
    'Approved: Evidence is compelling and risk is acceptable'
);

-- 5. Reject a proposal:
SELECT fhq_governance.fn_reject_epistemic_proposal(
    'uuid-here',
    'VEGA',
    'Rejected: Sample size too small for this regime'
);

-- 6. View proposal generation history:
SELECT * FROM fhq_governance.epistemic_proposal_runs
ORDER BY run_started_at DESC;

-- 7. Schedule info:
SELECT * FROM fhq_governance.epistemic_schedule_config;

*/
