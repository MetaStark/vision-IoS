-- Patch: Fix ambiguous column reference in Gateway function
-- Issue: RETURNS TABLE column names conflict with internal variables
-- Solution: Rename return columns to avoid ambiguity
DROP FUNCTION IF EXISTS fhq_governance.truth_gateway_retrieve(TEXT, TEXT, TEXT);

CREATE OR REPLACE FUNCTION fhq_governance.truth_gateway_retrieve(
    p_requesting_agent TEXT,
    p_agent_tier TEXT DEFAULT 'TIER-2',
    p_request_source TEXT DEFAULT 'DASHBOARD'
)
RETURNS TABLE (
    out_context_package JSONB,
    out_context_hash TEXT,
    out_issued_at TIMESTAMPTZ,
    out_integrity_signature TEXT,
    out_gateway_status TEXT,
    out_validations_passed JSONB
) AS $$
DECLARE
    v_context_pkg RECORD;
    v_computed_context_hash TEXT;
    v_integrity_sig TEXT;
    v_gateway_status TEXT := 'SUCCESS';
    v_latency_start TIMESTAMPTZ;
    v_validation_failures JSONB := '[]'::JSONB;
    v_validations JSONB;
    v_adr018_valid BOOLEAN := TRUE;
    v_adr017_valid BOOLEAN := TRUE;
    v_ec_role_valid BOOLEAN := TRUE;
    v_risl_valid BOOLEAN := TRUE;
    v_defcon_valid BOOLEAN := TRUE;
    v_all_valid BOOLEAN := TRUE;
    v_current_defcon TEXT;
    v_risl_status TEXT;
BEGIN
    v_latency_start := clock_timestamp();

    -- Get current context package
    SELECT cp.* INTO v_context_pkg
    FROM fhq_governance.context_packages cp
    WHERE cp.is_valid = TRUE AND cp.valid_until IS NULL
    ORDER BY cp.package_timestamp DESC LIMIT 1;

    -- FAIL-CLOSED: No context available
    IF v_context_pkg IS NULL THEN
        v_gateway_status := 'MISSING_CONTEXT';
        INSERT INTO fhq_governance.gateway_request_log (
            requesting_agent, agent_tier, request_source, gateway_status,
            adr018_validated, adr017_validated, ec_role_validated,
            risl_validated, defcon_validated, validation_failures, latency_ms
        ) VALUES (
            p_requesting_agent, p_agent_tier, p_request_source, v_gateway_status,
            FALSE, FALSE, FALSE, FALSE, FALSE, '["NO_VALID_CONTEXT_PACKAGE"]'::JSONB,
            EXTRACT(MILLISECONDS FROM clock_timestamp() - v_latency_start)::INTEGER
        );
        RETURN QUERY SELECT
            jsonb_build_object('error', 'GATEWAY_HALT: No valid context package available'),
            'HALT'::TEXT, NOW(), 'NONE'::TEXT, v_gateway_status,
            jsonb_build_object('all_passed', FALSE, 'reason', 'MISSING_CONTEXT');
        RETURN;
    END IF;

    -- Validate ADR-018 state integrity
    IF v_context_pkg.state_snapshot_hash IS NULL THEN
        v_adr018_valid := FALSE; v_all_valid := FALSE;
        v_validation_failures := v_validation_failures || '["ADR018_MISSING_STATE_HASH"]'::JSONB;
    END IF;

    IF (NOW() - v_context_pkg.package_timestamp) > (v_context_pkg.freshness_ttl_seconds * INTERVAL '1 second') THEN
        v_adr018_valid := FALSE; v_all_valid := FALSE;
        v_gateway_status := 'STALE_CONTEXT';
        v_validation_failures := v_validation_failures || '["ADR018_CONTEXT_STALE"]'::JSONB;
    END IF;

    -- Validate ADR-017 quad_hash for execution contexts
    IF p_request_source IN ('ORCHESTRATOR', 'AGENT_DIRECT') AND v_context_pkg.quad_hash IS NULL THEN
        v_adr017_valid := FALSE; v_all_valid := FALSE;
        v_validation_failures := v_validation_failures || '["ADR017_MISSING_QUAD_HASH"]'::JSONB;
    END IF;

    -- Validate EC role boundaries
    IF p_agent_tier = 'TIER-1' AND p_requesting_agent NOT IN ('LARS', 'STIG', 'FINN', 'VEGA') THEN
        v_ec_role_valid := FALSE; v_all_valid := FALSE;
        v_validation_failures := v_validation_failures || '["EC_INVALID_TIER1_AGENT"]'::JSONB;
    END IF;

    -- Validate RISL status
    SELECT risl_status INTO v_risl_status FROM fhq_governance.mit_quad_pillars WHERE pillar_id = 'RISL';
    IF v_risl_status = 'HALTED' THEN
        v_risl_valid := FALSE; v_all_valid := FALSE;
        v_gateway_status := 'RISL_BLOCKED';
        v_validation_failures := v_validation_failures || '["RISL_HALTED"]'::JSONB;
    END IF;

    -- Validate DEFCON gating
    v_current_defcon := v_context_pkg.state_vector->>'defcon';
    IF v_current_defcon = 'BLACK' THEN
        v_defcon_valid := FALSE; v_all_valid := FALSE;
        v_gateway_status := 'DEFCON_BLOCKED';
        v_validation_failures := v_validation_failures || '["DEFCON_BLACK_HALT"]'::JSONB;
    ELSIF v_current_defcon = 'RED' AND p_request_source = 'ORCHESTRATOR' THEN
        v_defcon_valid := FALSE; v_all_valid := FALSE;
        v_gateway_status := 'DEFCON_BLOCKED';
        v_validation_failures := v_validation_failures || '["DEFCON_RED_EXECUTION_BLOCKED"]'::JSONB;
    END IF;

    -- FAIL-CLOSED on validation failure
    IF NOT v_all_valid THEN
        IF v_gateway_status = 'SUCCESS' THEN v_gateway_status := 'VALIDATION_FAILED'; END IF;
        INSERT INTO fhq_governance.gateway_request_log (
            requesting_agent, agent_tier, request_source, gateway_status,
            state_snapshot_hash, quad_hash,
            adr018_validated, adr017_validated, ec_role_validated,
            risl_validated, defcon_validated, validation_failures, latency_ms
        ) VALUES (
            p_requesting_agent, p_agent_tier, p_request_source, v_gateway_status,
            v_context_pkg.state_snapshot_hash, v_context_pkg.quad_hash,
            v_adr018_valid, v_adr017_valid, v_ec_role_valid,
            v_risl_valid, v_defcon_valid, v_validation_failures,
            EXTRACT(MILLISECONDS FROM clock_timestamp() - v_latency_start)::INTEGER
        );
        RETURN QUERY SELECT
            jsonb_build_object('error', 'GATEWAY_REJECT', 'status', v_gateway_status, 'failures', v_validation_failures),
            'REJECTED'::TEXT, NOW(), 'NONE'::TEXT, v_gateway_status,
            jsonb_build_object('all_passed', FALSE, 'adr018', v_adr018_valid, 'adr017', v_adr017_valid,
                'ec_role', v_ec_role_valid, 'risl', v_risl_valid, 'defcon', v_defcon_valid);
        RETURN;
    END IF;

    -- Compute cryptographic lineage
    v_computed_context_hash := encode(sha256((
        v_context_pkg.state_vector::TEXT || ':' || v_context_pkg.adr_index::TEXT || ':' ||
        v_context_pkg.ios_index::TEXT || ':' || v_context_pkg.authority_map::TEXT || ':' ||
        v_context_pkg.operational_constraints::TEXT || ':' || NOW()::TEXT
    )::bytea), 'hex');

    v_integrity_sig := 'STIG-GW-' || encode(sha256((
        v_computed_context_hash || ':' || v_context_pkg.state_snapshot_hash || ':' ||
        COALESCE(v_context_pkg.quad_hash, 'NULL') || ':' || p_requesting_agent || ':' || NOW()::TEXT
    )::bytea), 'hex');

    -- Store integrity signature
    INSERT INTO fhq_governance.gateway_integrity_signatures (
        context_hash, state_snapshot_hash, quad_hash,
        signature_value, package_version, issued_at
    ) VALUES (
        v_computed_context_hash, v_context_pkg.state_snapshot_hash, v_context_pkg.quad_hash,
        v_integrity_sig, v_context_pkg.package_version, NOW()
    ) ON CONFLICT (context_hash) DO UPDATE SET
        is_valid = TRUE,
        issued_at = NOW();

    v_validations := jsonb_build_object(
        'all_passed', TRUE, 'adr018_asrp', TRUE, 'adr017_quad', TRUE,
        'ec_role_boundary', TRUE, 'risl_safety', TRUE, 'defcon_gating', TRUE
    );

    -- Log successful request
    INSERT INTO fhq_governance.gateway_request_log (
        requesting_agent, agent_tier, request_source, gateway_status,
        context_hash, state_snapshot_hash, quad_hash, integrity_signature,
        adr018_validated, adr017_validated, ec_role_validated,
        risl_validated, defcon_validated, latency_ms
    ) VALUES (
        p_requesting_agent, p_agent_tier, p_request_source, 'SUCCESS',
        v_computed_context_hash, v_context_pkg.state_snapshot_hash, v_context_pkg.quad_hash,
        v_integrity_sig, TRUE, TRUE, TRUE, TRUE, TRUE,
        EXTRACT(MILLISECONDS FROM clock_timestamp() - v_latency_start)::INTEGER
    );

    -- Return atomic response
    RETURN QUERY SELECT
        jsonb_build_object(
            'state_vector', v_context_pkg.state_vector,
            'adr_index', v_context_pkg.adr_index,
            'ios_index', v_context_pkg.ios_index,
            'authority_map', v_context_pkg.authority_map,
            'operational_constraints', v_context_pkg.operational_constraints,
            '_metadata', jsonb_build_object(
                'package_id', v_context_pkg.package_id,
                'package_hash', v_context_pkg.package_hash,
                'state_snapshot_hash', v_context_pkg.state_snapshot_hash,
                'quad_hash', v_context_pkg.quad_hash,
                'gateway_version', '2026.DRAFT.2'
            )
        ),
        v_computed_context_hash,
        NOW(),
        v_integrity_sig,
        'SUCCESS'::TEXT,
        v_validations;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.truth_gateway_retrieve(TEXT, TEXT, TEXT) IS
'IoS-013 Truth Gateway Interface — The official truth surface for all LLM agents.
Returns atomic: {context_package, context_hash, issued_at, integrity_signature}
Enforces: ADR-018 (ASRP), ADR-017 (MIT Quad), EC boundaries, RISL, DEFCON.
FAIL-CLOSED: Any validation failure → REJECT.';
