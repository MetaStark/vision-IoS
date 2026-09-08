-- Migration 252: Fast-Track G1 Infrastructure
-- Directive A: Fast-Track G1 Validation for Low-Risk Learning Parameters
-- Binding: ADR-004 (Change Gates) + ADR-016 (DEFCON)

BEGIN;

-- ============================================================================
-- Fast-Track Eligibility Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.fast_track_eligible_parameters (
    parameter_id SERIAL PRIMARY KEY,
    parameter_name TEXT NOT NULL UNIQUE,
    parameter_scope TEXT NOT NULL,  -- 'damper', 'threshold', 'window', 'scalar'
    risk_classification TEXT DEFAULT 'LOW',
    auto_g1_eligible BOOLEAN DEFAULT FALSE,
    max_delta_percent DECIMAL(5,2),  -- Maximum allowed change percentage
    cooldown_hours INTEGER DEFAULT 24,
    requires_stillness BOOLEAN DEFAULT TRUE,
    defcon_eligible TEXT[] DEFAULT ARRAY['GREEN', 'YELLOW'],
    last_adjustment TIMESTAMPTZ,
    adjustment_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'UMA',
    CONSTRAINT valid_risk CHECK (risk_classification IN ('LOW', 'MEDIUM', 'HIGH')),
    CONSTRAINT valid_scope CHECK (parameter_scope IN ('damper', 'threshold', 'window', 'scalar', 'multiplier'))
);

COMMENT ON TABLE fhq_governance.fast_track_eligible_parameters IS
    'Fast-Track G1 eligible parameters per EC-014 Section 5.3. DEFCON-gated: only GREEN/YELLOW.';

-- ============================================================================
-- Fast-Track DEFCON Gate Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.fast_track_defcon_gate()
RETURNS BOOLEAN AS $$
DECLARE
    current_defcon TEXT;
BEGIN
    -- Get current DEFCON level from fhq_monitoring.defcon_status
    SELECT current_level INTO current_defcon
    FROM fhq_monitoring.defcon_status
    WHERE deactivated_at IS NULL
    ORDER BY activated_at DESC
    LIMIT 1;

    -- Default to GREEN if no active DEFCON status
    IF current_defcon IS NULL THEN
        current_defcon := 'GREEN';
    END IF;

    -- Fast-Track ONLY valid in GREEN/YELLOW per ADR-016 binding
    RETURN current_defcon IN ('GREEN', 'YELLOW');
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.fast_track_defcon_gate() IS
    'ADR-016 binding: Fast-Track auto-G1 suspended in ORANGE/RED/BLACK. Violation is Class A breach.';

-- ============================================================================
-- Fast-Track Eligibility Check Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_fast_track_eligibility(
    p_parameter_name TEXT,
    p_proposed_delta_percent DECIMAL
)
RETURNS JSONB AS $$
DECLARE
    v_param RECORD;
    v_defcon_ok BOOLEAN;
    v_result JSONB;
BEGIN
    -- Get parameter configuration
    SELECT * INTO v_param
    FROM fhq_governance.fast_track_eligible_parameters
    WHERE parameter_name = p_parameter_name;

    IF v_param IS NULL THEN
        RETURN jsonb_build_object(
            'eligible', false,
            'reason', 'Parameter not in fast-track registry',
            'parameter', p_parameter_name
        );
    END IF;

    -- Check DEFCON gate
    v_defcon_ok := fhq_governance.fast_track_defcon_gate();

    IF NOT v_defcon_ok THEN
        RETURN jsonb_build_object(
            'eligible', false,
            'reason', 'DEFCON state not GREEN/YELLOW - Fast-Track suspended',
            'parameter', p_parameter_name,
            'adr_reference', 'ADR-016'
        );
    END IF;

    -- Check if auto-G1 eligible
    IF NOT v_param.auto_g1_eligible THEN
        RETURN jsonb_build_object(
            'eligible', false,
            'reason', 'Parameter not marked for auto-G1',
            'parameter', p_parameter_name
        );
    END IF;

    -- Check cooldown
    IF v_param.last_adjustment IS NOT NULL AND
       v_param.last_adjustment + (v_param.cooldown_hours || ' hours')::INTERVAL > NOW() THEN
        RETURN jsonb_build_object(
            'eligible', false,
            'reason', 'Cooldown period not elapsed',
            'parameter', p_parameter_name,
            'cooldown_hours', v_param.cooldown_hours,
            'last_adjustment', v_param.last_adjustment,
            'available_at', v_param.last_adjustment + (v_param.cooldown_hours || ' hours')::INTERVAL
        );
    END IF;

    -- Check delta limit
    IF ABS(p_proposed_delta_percent) > v_param.max_delta_percent THEN
        RETURN jsonb_build_object(
            'eligible', false,
            'reason', 'Proposed delta exceeds max allowed',
            'parameter', p_parameter_name,
            'proposed_delta', p_proposed_delta_percent,
            'max_delta', v_param.max_delta_percent
        );
    END IF;

    -- All checks passed
    RETURN jsonb_build_object(
        'eligible', true,
        'parameter', p_parameter_name,
        'risk_classification', v_param.risk_classification,
        'proposed_delta', p_proposed_delta_percent,
        'max_delta', v_param.max_delta_percent,
        'requires_stillness', v_param.requires_stillness,
        'note', 'VEGA audit still mandatory'
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Fast-Track Adjustment Log
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.fast_track_adjustment_log (
    log_id SERIAL PRIMARY KEY,
    parameter_name TEXT NOT NULL REFERENCES fhq_governance.fast_track_eligible_parameters(parameter_name),
    previous_value DECIMAL,
    new_value DECIMAL,
    delta_percent DECIMAL(5,2),
    requested_by TEXT NOT NULL,  -- Usually 'UMA'
    approved_by TEXT NOT NULL,   -- 'STIG' for feasibility
    vega_audit_id TEXT,          -- VEGA audit reference (mandatory)
    defcon_at_approval TEXT NOT NULL,
    stillness_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.fast_track_adjustment_log IS
    'Audit trail for all Fast-Track parameter adjustments. Court-proof evidence.';

-- ============================================================================
-- Initial Fast-Track Parameters (Per Plan)
-- ============================================================================

INSERT INTO fhq_governance.fast_track_eligible_parameters
    (parameter_name, parameter_scope, risk_classification, auto_g1_eligible, max_delta_percent, cooldown_hours, requires_stillness)
VALUES
    ('confidence_damper_alpha', 'damper', 'LOW', TRUE, 10.00, 24, TRUE),
    ('confidence_damper_beta', 'damper', 'LOW', TRUE, 10.00, 24, TRUE),
    ('ldow_coverage_threshold', 'threshold', 'LOW', TRUE, 5.00, 48, TRUE),
    ('ldow_stability_threshold', 'threshold', 'LOW', TRUE, 2.00, 48, TRUE)
ON CONFLICT (parameter_name) DO NOTHING;

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
    'INFRASTRUCTURE_CREATE',
    'FAST_TRACK_G1',
    'DIRECTIVE_A',
    'STIG',
    NOW(),
    'DEPLOYED',
    'CEO Directive 2026-01-16 - Directive A: Fast-Track G1 for Low-Risk Learning Parameters',
    jsonb_build_object(
        'migration', '252_fast_track_g1_infrastructure.sql',
        'directive', 'CEO Directive 2026-01-16 - Directive A',
        'tables_created', ARRAY['fast_track_eligible_parameters', 'fast_track_adjustment_log'],
        'functions_created', ARRAY['fast_track_defcon_gate', 'check_fast_track_eligibility'],
        'initial_parameters', 4,
        'defcon_binding', 'ADR-016 - GREEN/YELLOW only',
        'vega_audit_mandatory', true
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- SELECT * FROM fhq_governance.fast_track_eligible_parameters;
-- SELECT fhq_governance.fast_track_defcon_gate();
-- SELECT fhq_governance.check_fast_track_eligibility('confidence_damper_alpha', 5.0);
