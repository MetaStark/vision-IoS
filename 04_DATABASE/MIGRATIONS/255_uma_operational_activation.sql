-- Migration 255: UMA Operational Activation
-- CEO Directive 2026-01-16B: Automated Activation of UMA
-- Status: ACTIVE | Binding | System-wide

BEGIN;

-- ============================================================================
-- UMA Daily Operating Loop Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.uma_daily_loop (
    loop_id SERIAL PRIMARY KEY,
    loop_date DATE NOT NULL UNIQUE,
    cycle_number INTEGER NOT NULL,

    -- T+00h: Ingest Phase
    ingest_started_at TIMESTAMPTZ,
    daily_reports_ingested INTEGER DEFAULT 0,
    cfao_synthetic_outputs_ingested INTEGER DEFAULT 0,
    defcon_state_at_ingest TEXT,
    ingest_completed_at TIMESTAMPTZ,

    -- T+01h: Bottleneck Mapping Phase
    mapping_started_at TIMESTAMPTZ,
    hypothesis_quality_frictions JSONB,
    falsification_failure_frictions JSONB,
    governance_latency_frictions JSONB,
    validation_bottleneck_frictions JSONB,
    total_frictions_identified INTEGER DEFAULT 0,
    mapping_completed_at TIMESTAMPTZ,

    -- T+02h: Learning ROI Ranking Phase
    ranking_started_at TIMESTAMPTZ,
    frictions_ranked JSONB,  -- Ordered by expected marginal LVI uplift
    exclusions_applied JSONB,  -- What was explicitly excluded per directive
    ranking_completed_at TIMESTAMPTZ,

    -- T+03h: Action Signaling Phase
    signaling_started_at TIMESTAMPTZ,
    recommendation_1 JSONB,
    recommendation_2 JSONB,
    recommendations_issued INTEGER DEFAULT 0,  -- Max 2 per directive
    signaling_completed_at TIMESTAMPTZ,

    -- T+04h: Signature & Audit Phase
    signature_started_at TIMESTAMPTZ,
    uma_signature TEXT,
    vega_audit_submitted BOOLEAN DEFAULT FALSE,
    vega_audit_id TEXT,
    signature_completed_at TIMESTAMPTZ,

    -- Stop Conditions
    stop_condition_triggered BOOLEAN DEFAULT FALSE,
    stop_condition_reason TEXT,

    -- Loop Status
    loop_status TEXT DEFAULT 'PENDING',  -- 'PENDING', 'RUNNING', 'COMPLETED', 'STOPPED', 'FAILED'
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_loop_status CHECK (loop_status IN ('PENDING', 'RUNNING', 'COMPLETED', 'STOPPED', 'FAILED')),
    CONSTRAINT max_two_recommendations CHECK (recommendations_issued <= 2)
);

COMMENT ON TABLE fhq_governance.uma_daily_loop IS
    'UMA daily 24h operating loop per CEO Directive 2026-01-16B. Immutable loop structure.';

-- ============================================================================
-- UMA Stop Conditions Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.uma_stop_conditions (
    condition_id SERIAL PRIMARY KEY,
    condition_code TEXT NOT NULL UNIQUE,
    condition_description TEXT NOT NULL,
    check_function TEXT,  -- SQL function to evaluate condition
    is_active BOOLEAN DEFAULT TRUE,
    severity TEXT DEFAULT 'HARD',  -- All conditions are HARD per directive
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.uma_stop_conditions IS
    'Mandatory stop conditions for UMA. All are HARD rules per CEO Directive 2026-01-16B.';

-- Insert the 5 mandatory stop conditions from the directive
INSERT INTO fhq_governance.uma_stop_conditions (condition_code, condition_description, check_function) VALUES
    ('DEFCON_ELEVATED',
     'DEFCON >= ORANGE - UMA must recommend no action',
     'SELECT current_level NOT IN (''GREEN'', ''YELLOW'') FROM fhq_monitoring.defcon_status WHERE deactivated_at IS NULL ORDER BY activated_at DESC LIMIT 1'),

    ('SINGLE_HYPOTHESIS_DRIVEN',
     'LVI improvement is driven by a single hypothesis class',
     NULL),  -- Requires UMA analysis to determine

    ('SYNTHETIC_DIVERGENCE',
     'Synthetic performance diverges materially from canonical validation',
     NULL),  -- Requires UMA analysis to determine

    ('EXECUTION_AUTHORITY_EXPANSION',
     'Governance friction removal would expand execution authority',
     NULL),  -- Requires UMA analysis to determine

    ('VEGA_METRIC_INTEGRITY_RISK',
     'VEGA flags metric integrity risk',
     'SELECT EXISTS(SELECT 1 FROM fhq_governance.vega_feedback_loop WHERE vega_ruling = ''REJECTED'' AND created_at > NOW() - INTERVAL ''24 hours'')');

-- ============================================================================
-- UMA Stop Condition Check Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_uma_stop_conditions()
RETURNS JSONB AS $$
DECLARE
    v_defcon TEXT;
    v_result JSONB;
    v_stop_triggered BOOLEAN := FALSE;
    v_stop_reasons TEXT[] := ARRAY[]::TEXT[];
BEGIN
    -- Check DEFCON state (most critical)
    SELECT current_level INTO v_defcon
    FROM fhq_monitoring.defcon_status
    WHERE deactivated_at IS NULL
    ORDER BY activated_at DESC
    LIMIT 1;

    IF v_defcon IS NULL THEN
        v_defcon := 'GREEN';
    END IF;

    IF v_defcon NOT IN ('GREEN', 'YELLOW') THEN
        v_stop_triggered := TRUE;
        v_stop_reasons := array_append(v_stop_reasons, 'DEFCON_ELEVATED: ' || v_defcon);
    END IF;

    -- Return result
    RETURN jsonb_build_object(
        'stop_triggered', v_stop_triggered,
        'stop_reasons', v_stop_reasons,
        'defcon_state', v_defcon,
        'checked_at', NOW(),
        'note', 'Additional stop conditions (single_hypothesis, synthetic_divergence, execution_authority, vega_integrity) require UMA runtime analysis'
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- UMA Exclusions Registry (What UMA May NOT Recommend)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.uma_exclusions (
    exclusion_id SERIAL PRIMARY KEY,
    exclusion_type TEXT NOT NULL,
    exclusion_description TEXT NOT NULL,
    directive_reference TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO fhq_governance.uma_exclusions (exclusion_type, exclusion_description, directive_reference) VALUES
    ('EXECUTION_OPTIMIZATION', 'UMA may not recommend execution optimization', 'CEO-DIR-2026-01-16B Section 3.T+02h'),
    ('PNL_CHASING', 'UMA may not recommend PnL chasing activities', 'CEO-DIR-2026-01-16B Section 3.T+02h'),
    ('MODEL_MICRO_TUNING', 'UMA may not recommend model micro-tuning outside Fast-Track scope', 'CEO-DIR-2026-01-16B Section 3.T+02h'),
    ('STRATEGY_CHANGES', 'UMA may not recommend strategy changes', 'CEO-DIR-2026-01-16B Section 3.T+03h'),
    ('PARAMETER_ENFORCEMENT', 'UMA may not enforce parameters (advisory only)', 'CEO-DIR-2026-01-16B Section 3.T+03h'),
    ('CAPITAL_ALLOCATION', 'UMA may not suggest capital allocation', 'CEO-DIR-2026-01-16B Section 3.T+03h'),
    ('INCREASED_RISK', 'LVI may not justify increased risk', 'CEO-DIR-2026-01-16B Section 5'),
    ('RELAXED_CAPITAL_CONSTRAINTS', 'LVI may not justify relaxed capital constraints', 'CEO-DIR-2026-01-16B Section 5'),
    ('EXECUTION_AUTONOMY', 'LVI may not justify execution autonomy', 'CEO-DIR-2026-01-16B Section 5');

COMMENT ON TABLE fhq_governance.uma_exclusions IS
    'Explicit exclusions for UMA recommendations per CEO Directive 2026-01-16B.';

-- ============================================================================
-- UMA Recommendations Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.uma_recommendations (
    recommendation_id SERIAL PRIMARY KEY,
    loop_id INTEGER REFERENCES fhq_governance.uma_daily_loop(loop_id),
    recommendation_number INTEGER CHECK (recommendation_number IN (1, 2)),
    recommendation_type TEXT NOT NULL,  -- 'FAST_TRACK_G1_FLAG', 'GOVERNANCE_FEEDBACK'
    target_parameter TEXT,
    expected_lvi_uplift DECIMAL(5,4),
    evidence_references TEXT[],
    exclusion_checks_passed BOOLEAN DEFAULT FALSE,
    stop_condition_checks_passed BOOLEAN DEFAULT FALSE,
    uma_signature TEXT,
    vega_reviewed BOOLEAN DEFAULT FALSE,
    vega_outcome TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_recommendation_type CHECK (recommendation_type IN ('FAST_TRACK_G1_FLAG', 'GOVERNANCE_FEEDBACK'))
);

COMMENT ON TABLE fhq_governance.uma_recommendations IS
    'UMA recommendations (max 2 per cycle). Must pass exclusion and stop-condition checks.';

-- ============================================================================
-- CEO Override Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.ceo_uma_overrides (
    override_id SERIAL PRIMARY KEY,
    override_type TEXT NOT NULL,  -- 'PAUSE', 'RESET_LVI_BASELINE', 'RESTRICT_FAST_TRACK', 'FREEZE_LEARNING'
    override_reason TEXT NOT NULL,
    override_duration_hours INTEGER,
    activated_at TIMESTAMPTZ DEFAULT NOW(),
    deactivated_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    ceo_signature TEXT,

    CONSTRAINT valid_override_type CHECK (override_type IN (
        'PAUSE_RECOMMENDATIONS',
        'RESET_LVI_BASELINE',
        'RESTRICT_FAST_TRACK_SCOPE',
        'FREEZE_LEARNING'
    ))
);

COMMENT ON TABLE fhq_governance.ceo_uma_overrides IS
    'CEO override authority per Section 6. Human capital sovereignty is absolute.';

-- ============================================================================
-- Migration Audit Log
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'UMA_OPERATIONAL_ACTIVATION',
    'UMA',
    'CEO_DIRECTIVE',
    'CEO',
    NOW(),
    'ACTIVATED',
    'CEO Directive 2026-01-16B: Automated Activation of UMA (Universal Meta-Analyst)',
    jsonb_build_object(
        'migration', '255_uma_operational_activation.sql',
        'directive', 'CEO-DIR-2026-01-16B',
        'tables_created', ARRAY[
            'uma_daily_loop',
            'uma_stop_conditions',
            'uma_exclusions',
            'uma_recommendations',
            'ceo_uma_overrides'
        ],
        'stop_conditions', 5,
        'exclusions', 9,
        'max_recommendations_per_cycle', 2,
        'strategic_closure', 'Learning is no longer accidental. Speed is no longer chaotic. Intelligence compounds under control.'
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- SELECT * FROM fhq_governance.uma_stop_conditions;
-- SELECT * FROM fhq_governance.uma_exclusions;
-- SELECT fhq_governance.check_uma_stop_conditions();
