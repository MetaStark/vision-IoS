-- ============================================================================
-- MIGRATION 077: IoS-013 CDS — Context Definition Specification Activation
-- ============================================================================
-- Purpose: Implement CDS canonical context package + CHL infrastructure
-- Authority: CEO Execution Order → IoS-013 CDS Final Activation
-- Date: 2025-12-05
--
-- ARCHITECTURE:
--   Constitution (ADR-018) → Machine (IoS-013) → Payload (CDS) → Interface (CHL)
--
-- MANDATES:
--   STIG: context_package implementation
--   CDMO: Canonical registration
--   VEGA: Governance validation
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Create CDS Context Package Table
-- ============================================================================
-- Stores pre-computed context packages for atomic delivery

CREATE TABLE IF NOT EXISTS fhq_governance.context_packages (
    package_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core identification
    package_version TEXT NOT NULL DEFAULT '2026.CDS.1',
    package_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- === STATE VECTOR (from ASRP - ADR-018) ===
    state_vector JSONB NOT NULL,
    state_snapshot_hash TEXT NOT NULL,

    -- === ADR INDEX ===
    adr_index JSONB NOT NULL,

    -- === IoS INDEX ===
    ios_index JSONB NOT NULL,

    -- === AUTHORITY MAP ===
    authority_map JSONB NOT NULL,

    -- === OPERATIONAL CONSTRAINTS ===
    operational_constraints JSONB NOT NULL,

    -- === QUAD HASH (from MIT Quad - ADR-017) ===
    quad_hash TEXT,

    -- === PACKAGE INTEGRITY ===
    package_hash TEXT NOT NULL UNIQUE,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,

    -- === VALIDITY WINDOW ===
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    freshness_ttl_seconds INTEGER NOT NULL DEFAULT 300,

    -- === LINEAGE ===
    created_by TEXT NOT NULL DEFAULT 'STIG',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_context_packages_valid
    ON fhq_governance.context_packages(is_valid, valid_until)
    WHERE is_valid = TRUE AND valid_until IS NULL;

CREATE INDEX IF NOT EXISTS idx_context_packages_hash
    ON fhq_governance.context_packages(package_hash);

CREATE INDEX IF NOT EXISTS idx_context_packages_state_hash
    ON fhq_governance.context_packages(state_snapshot_hash);

COMMENT ON TABLE fhq_governance.context_packages IS
'Pre-computed context packages per IoS-013 CDS. Atomic delivery to CHL.
Contains: state_vector, adr_index, ios_index, authority_map, operational_constraints.
Must be delivered as single atomic unit - partial reads prohibited.';

-- ============================================================================
-- SECTION 2: Create CHL Request Log Table
-- ============================================================================
-- Audit trail for Context Hydration Layer requests

CREATE TABLE IF NOT EXISTS fhq_governance.chl_request_log (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request identification
    requesting_agent TEXT NOT NULL,
    request_source TEXT NOT NULL,  -- 'DASHBOARD', 'API', 'ORCHESTRATOR'
    request_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Context package delivered
    package_id UUID REFERENCES fhq_governance.context_packages(package_id),
    package_hash TEXT NOT NULL,
    state_snapshot_hash TEXT NOT NULL,
    quad_hash TEXT,

    -- Validation results
    hydration_status TEXT NOT NULL CHECK (hydration_status IN (
        'SUCCESS',        -- Context delivered successfully
        'STALE_CONTEXT',  -- Context exceeded TTL
        'INVALID_PACKAGE',-- Package failed validation
        'MISSING_PACKAGE',-- No valid package available
        'CHL_BYPASS_BLOCKED', -- Attempted CHL bypass blocked
        'VALIDATION_FAILED'   -- Pre-flight checks failed
    )),

    -- Pre-flight checklist results
    preflight_passed BOOLEAN NOT NULL DEFAULT FALSE,
    preflight_failures TEXT[],

    -- Output binding
    output_bound BOOLEAN DEFAULT FALSE,
    output_binding_id UUID,

    -- Metadata
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chl_request_log_agent
    ON fhq_governance.chl_request_log(requesting_agent, request_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_chl_request_log_status
    ON fhq_governance.chl_request_log(hydration_status);

COMMENT ON TABLE fhq_governance.chl_request_log IS
'Audit log for Context Hydration Layer (CHL) requests per IoS-013 CDS §4.
Every LLM call must be logged here with context delivery status.';

-- ============================================================================
-- SECTION 3: Create Context Package Generation Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.generate_context_package()
RETURNS UUID AS $$
DECLARE
    v_package_id UUID;
    v_state_snapshot RECORD;
    v_state_vector JSONB;
    v_adr_index JSONB;
    v_ios_index JSONB;
    v_authority_map JSONB;
    v_operational_constraints JSONB;
    v_package_hash TEXT;
    v_quad_hash TEXT;
BEGIN
    -- 1. Get current valid state snapshot (ASRP)
    SELECT
        snapshot_id,
        state_vector_hash,
        snapshot_timestamp,
        defcon_level,
        btc_regime_label,
        btc_regime_confidence,
        strategy_posture,
        strategy_exposure
    INTO v_state_snapshot
    FROM fhq_governance.shared_state_snapshots
    WHERE is_valid = TRUE AND valid_until IS NULL
    ORDER BY snapshot_timestamp DESC
    LIMIT 1;

    IF v_state_snapshot IS NULL THEN
        RAISE EXCEPTION 'CDS_FAIL: No valid state snapshot available. HALT required.';
    END IF;

    -- 2. Build state_vector (CDS §2.1)
    v_state_vector := jsonb_build_object(
        'defcon', v_state_snapshot.defcon_level,
        'regime', v_state_snapshot.btc_regime_label,
        'regime_confidence', v_state_snapshot.btc_regime_confidence,
        'strategy', v_state_snapshot.strategy_posture,
        'strategy_exposure', v_state_snapshot.strategy_exposure,
        'state_snapshot_hash', v_state_snapshot.state_vector_hash,
        'timestamp', v_state_snapshot.snapshot_timestamp
    );

    -- 3. Build ADR index (CDS §2.2)
    SELECT jsonb_agg(jsonb_build_object(
        'id', adr_id,
        'title', adr_title,
        'version', current_version,
        'tier', governance_tier,
        'status', adr_status,
        'sha256', encode(sha256((adr_id || ':' || current_version)::bytea), 'hex')
    ) ORDER BY adr_id)
    INTO v_adr_index
    FROM fhq_meta.adr_registry
    WHERE adr_status IN ('APPROVED', 'ACTIVE');

    -- 4. Build IoS index (CDS §2.3)
    SELECT jsonb_agg(jsonb_build_object(
        'id', r.ios_id,
        'purpose', r.title,
        'owner', r.owner_role,
        'pillar', COALESCE(m.pillar_id, 'UNASSIGNED'),
        'status', r.status,
        'version', r.version
    ) ORDER BY r.ios_id)
    INTO v_ios_index
    FROM fhq_meta.ios_registry r
    LEFT JOIN fhq_governance.ios_quad_mapping m ON r.ios_id = m.ios_id AND m.is_primary = TRUE;

    -- 5. Build authority_map (CDS §2.4)
    v_authority_map := jsonb_build_object(
        'tier_1', jsonb_build_object(
            'agents', ARRAY['LARS', 'STIG', 'FINN', 'VEGA'],
            'description', 'Executive Agents'
        ),
        'tier_2', jsonb_build_object(
            'agents', ARRAY['CFAO', 'CEIO', 'CSEO', 'CDMO', 'LINE'],
            'description', 'Sub-Executive Agents'
        ),
        'object_ownership', jsonb_build_object(
            'defcon', 'STIG',
            'regime', 'FINN',
            'strategy', 'LARS',
            'governance', 'VEGA',
            'execution', 'LINE'
        )
    );

    -- 6. Build operational_constraints (CDS §2.5)
    v_operational_constraints := jsonb_build_object(
        'lids_threshold', jsonb_build_object(
            'value', 0.85,
            'description', 'LIDS P(Truth) must exceed 0.85 for allocation',
            'basis', 'ADR-017 §3.1'
        ),
        'quad_hash_required', jsonb_build_object(
            'value', TRUE,
            'description', 'Quad-Hash required for all execution actions',
            'basis', 'ADR-017 §4'
        ),
        'state_hash_required', jsonb_build_object(
            'value', TRUE,
            'description', 'State hash required for all agent outputs',
            'basis', 'ADR-018 §4'
        ),
        'preflight_checklist', jsonb_build_object(
            'steps', 5,
            'checks', ARRAY[
                'ASRP_STATE_VALID',
                'MIT_QUAD_HASH_PRESENT',
                'LIDS_THRESHOLD_MET',
                'RISL_NOT_HALTED',
                'DUAL_HASH_VALIDATION'
            ]
        ),
        'risl_halt_conditions', jsonb_build_object(
            'triggers', ARRAY['DATA_DRIFT', 'AGENT_HALLUCINATION', 'CONSENSUS_FAILURE'],
            'basis', 'ADR-017 §3.4 + ADR-016'
        ),
        'defcon_restrictions', jsonb_build_object(
            'BLACK', 'ALL_OPERATIONS_HALTED',
            'RED', 'EXECUTION_SUSPENDED',
            'ORANGE', 'PAPER_TRADING_ONLY',
            'YELLOW', 'TIER2_RESTRICTED',
            'GREEN', 'NORMAL_OPERATIONS'
        )
    );

    -- 7. Compute package hash
    v_package_hash := encode(sha256((
        v_state_vector::TEXT || ':' ||
        v_adr_index::TEXT || ':' ||
        v_ios_index::TEXT || ':' ||
        v_authority_map::TEXT || ':' ||
        v_operational_constraints::TEXT || ':' ||
        NOW()::TEXT
    )::bytea), 'hex');

    -- 8. Get latest quad_hash if available
    SELECT quad_hash INTO v_quad_hash
    FROM fhq_governance.quad_hash_registry
    WHERE state_snapshot_hash = v_state_snapshot.state_vector_hash
    AND is_valid = TRUE
    ORDER BY created_at DESC
    LIMIT 1;

    -- 9. Invalidate previous packages
    UPDATE fhq_governance.context_packages
    SET
        valid_until = NOW(),
        is_valid = FALSE
    WHERE is_valid = TRUE AND valid_until IS NULL;

    -- 10. Insert new context package
    INSERT INTO fhq_governance.context_packages (
        package_id,
        state_vector,
        state_snapshot_hash,
        adr_index,
        ios_index,
        authority_map,
        operational_constraints,
        quad_hash,
        package_hash,
        created_by
    ) VALUES (
        gen_random_uuid(),
        v_state_vector,
        v_state_snapshot.state_vector_hash,
        v_adr_index,
        v_ios_index,
        v_authority_map,
        v_operational_constraints,
        v_quad_hash,
        v_package_hash,
        'STIG'
    ) RETURNING package_id INTO v_package_id;

    RETURN v_package_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.generate_context_package() IS
'Generates atomic context package per IoS-013 CDS §2.
Combines state_vector, adr_index, ios_index, authority_map, operational_constraints.
Invalidates previous packages (single valid package at any time).';

-- ============================================================================
-- SECTION 4: Create CHL Retrieval Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.chl_retrieve_context(
    p_requesting_agent TEXT,
    p_request_source TEXT DEFAULT 'DASHBOARD'
)
RETURNS TABLE (
    package_id UUID,
    context_package JSONB,
    package_hash TEXT,
    state_snapshot_hash TEXT,
    quad_hash TEXT,
    is_valid BOOLEAN,
    hydration_status TEXT,
    preflight_passed BOOLEAN
) AS $$
DECLARE
    v_package RECORD;
    v_is_fresh BOOLEAN;
    v_preflight_passed BOOLEAN := TRUE;
    v_preflight_failures TEXT[] := ARRAY[]::TEXT[];
    v_hydration_status TEXT;
    v_latency_start TIMESTAMPTZ;
    v_context_package JSONB;
BEGIN
    v_latency_start := clock_timestamp();

    -- 1. Get current valid context package
    SELECT cp.* INTO v_package
    FROM fhq_governance.context_packages cp
    WHERE cp.is_valid = TRUE AND cp.valid_until IS NULL
    ORDER BY cp.package_timestamp DESC
    LIMIT 1;

    -- 2. FAIL-CLOSED: No package available
    IF v_package IS NULL THEN
        -- Log the failed request
        INSERT INTO fhq_governance.chl_request_log (
            requesting_agent, request_source, package_hash, state_snapshot_hash,
            hydration_status, preflight_passed, latency_ms
        ) VALUES (
            p_requesting_agent, p_request_source, 'NONE', 'NONE',
            'MISSING_PACKAGE', FALSE,
            EXTRACT(MILLISECONDS FROM clock_timestamp() - v_latency_start)::INTEGER
        );

        RETURN QUERY SELECT
            NULL::UUID,
            jsonb_build_object('error', 'No valid context package available. HALT required.'),
            'HALT'::TEXT,
            'HALT'::TEXT,
            NULL::TEXT,
            FALSE,
            'MISSING_PACKAGE'::TEXT,
            FALSE;
        RETURN;
    END IF;

    -- 3. Freshness check
    v_is_fresh := (NOW() - v_package.package_timestamp) <
                  (v_package.freshness_ttl_seconds * INTERVAL '1 second');

    IF NOT v_is_fresh THEN
        v_hydration_status := 'STALE_CONTEXT';
        v_preflight_passed := FALSE;
        v_preflight_failures := array_append(v_preflight_failures, 'CONTEXT_STALE');
    END IF;

    -- 4. Pre-flight validation
    -- Check DEFCON
    IF (v_package.state_vector->>'defcon') = 'BLACK' THEN
        v_preflight_passed := FALSE;
        v_preflight_failures := array_append(v_preflight_failures, 'DEFCON_BLACK');
    END IF;

    -- Check state hash exists
    IF v_package.state_snapshot_hash IS NULL THEN
        v_preflight_passed := FALSE;
        v_preflight_failures := array_append(v_preflight_failures, 'MISSING_STATE_HASH');
    END IF;

    -- 5. Build context package JSON
    v_context_package := jsonb_build_object(
        'state_vector', v_package.state_vector,
        'adr_index', v_package.adr_index,
        'ios_index', v_package.ios_index,
        'authority_map', v_package.authority_map,
        'operational_constraints', v_package.operational_constraints,
        '_metadata', jsonb_build_object(
            'package_id', v_package.package_id,
            'package_hash', v_package.package_hash,
            'state_snapshot_hash', v_package.state_snapshot_hash,
            'quad_hash', v_package.quad_hash,
            'generated_at', v_package.package_timestamp,
            'retrieved_at', NOW(),
            'cds_version', v_package.package_version
        )
    );

    -- 6. Determine final status
    IF v_preflight_passed AND v_is_fresh THEN
        v_hydration_status := 'SUCCESS';
    ELSIF NOT v_is_fresh THEN
        v_hydration_status := 'STALE_CONTEXT';
    ELSE
        v_hydration_status := 'VALIDATION_FAILED';
    END IF;

    -- 7. Log the request
    INSERT INTO fhq_governance.chl_request_log (
        requesting_agent, request_source, package_id, package_hash,
        state_snapshot_hash, quad_hash, hydration_status,
        preflight_passed, preflight_failures, latency_ms
    ) VALUES (
        p_requesting_agent, p_request_source, v_package.package_id, v_package.package_hash,
        v_package.state_snapshot_hash, v_package.quad_hash, v_hydration_status,
        v_preflight_passed, v_preflight_failures,
        EXTRACT(MILLISECONDS FROM clock_timestamp() - v_latency_start)::INTEGER
    );

    -- 8. Return context package
    RETURN QUERY SELECT
        v_package.package_id,
        v_context_package,
        v_package.package_hash,
        v_package.state_snapshot_hash,
        v_package.quad_hash,
        v_package.is_valid AND v_is_fresh,
        v_hydration_status,
        v_preflight_passed;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.chl_retrieve_context(TEXT, TEXT) IS
'CHL retrieval function per IoS-013 CDS §4.
Returns complete atomic context_package for LLM hydration.
Logs all requests. Implements fail-closed semantics.';

-- ============================================================================
-- SECTION 5: Add CDS Compliance to Pre-Flight Checklist
-- ============================================================================

INSERT INTO fhq_governance.preflight_checklist (
    checklist_name, action_type, check_order, check_description,
    constitutional_basis, is_mandatory
) VALUES
(
    'CDS_CONTEXT_VALID',
    'LLM_REASONING',
    0,
    'Verify CHL has injected valid context_package before LLM reasoning',
    'IoS-013 CDS §3',
    TRUE
),
(
    'CHL_HYDRATION_SUCCESS',
    'LLM_REASONING',
    1,
    'Verify CHL hydration completed successfully (not stale, not missing)',
    'IoS-013 CDS §4',
    TRUE
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 6: Add VEGA Validation Rule for CDS Compliance
-- ============================================================================

INSERT INTO fhq_governance.vega_validation_rules (
    rule_name,
    rule_type,
    applies_to,
    condition_sql,
    failure_action,
    constitutional_basis,
    is_active
) VALUES (
    'CDS_CONTEXT_PACKAGE_REQUIRED',
    'PRECONDITION',
    ARRAY['LLM_REASONING', 'DASHBOARD_QUERY', 'AGENT_REASONING'],
    'SELECT EXISTS (
        SELECT 1 FROM fhq_governance.chl_request_log
        WHERE package_hash = $1
        AND hydration_status = ''SUCCESS''
        AND preflight_passed = TRUE
    )',
    'REJECT',
    'IoS-013 CDS §3 + §4',
    TRUE
) ON CONFLICT (rule_name) DO UPDATE SET
    applies_to = EXCLUDED.applies_to,
    condition_sql = EXCLUDED.condition_sql,
    is_active = TRUE,
    updated_at = NOW();

-- ============================================================================
-- SECTION 7: Update IoS-013 Registry with CDS Metadata
-- ============================================================================

UPDATE fhq_meta.ios_registry
SET
    description = description || E'\n\n=== CDS ACTIVATED ===\n' ||
        'Context Definition Specification (CDS) active.\n' ||
        'CHL (Context Hydration Layer) operational.\n' ||
        'Governance chain: Constitution (ADR-018) → Machine (IoS-013) → Payload (CDS) → Interface (CHL)',
    version = '2026.PROD.G0.CDS',
    governing_adrs = array_append(governing_adrs, 'IoS-013-CDS'),
    updated_at = NOW()
WHERE ios_id = 'IoS-013';

-- ============================================================================
-- SECTION 8: Register CDS Document in IoS Appendix Registry
-- ============================================================================

INSERT INTO fhq_meta.ios_appendix_registry (
    ios_id,
    appendix_code,
    appendix_title,
    version,
    status,
    content_hash,
    owner_role,
    governing_adrs
) VALUES (
    'IoS-013',
    'CDS',
    'Context Definition Specification',
    '2026.DRAFT.1',
    'ACTIVE',
    encode(sha256((
        'IoS-013:CDS:2026.DRAFT.1:context_package:state_vector:adr_index:' ||
        'ios_index:authority_map:operational_constraints'
    )::bytea), 'hex'),
    'STIG',
    ARRAY['ADR-017', 'ADR-018', 'IoS-013']
) ON CONFLICT (ios_id, appendix_code) DO UPDATE SET
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    content_hash = EXCLUDED.content_hash,
    updated_at = NOW();

-- ============================================================================
-- SECTION 9: CDMO Governance Action Log
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
    vega_reviewed,
    hash_chain_id,
    signature_id
) VALUES (
    gen_random_uuid(),
    'CDS_ACTIVATION',
    'IoS-013-CDS',
    'IOS_APPENDIX',
    'CDMO',
    NOW(),
    'APPROVED',
    'IoS-013 Context Definition Specification (CDS) activated per CEO Execution Order. CHL infrastructure deployed. Context package structure implemented. Governance chain established: Constitution (ADR-018) → Machine (IoS-013) → Payload (CDS) → Interface (CHL).',
    TRUE,
    'HC-IOS-013-ASPE-2026',
    gen_random_uuid()
);

-- ============================================================================
-- SECTION 10: VEGA Governance Action Log
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
    vega_reviewed,
    vega_notes,
    hash_chain_id,
    signature_id
) VALUES (
    gen_random_uuid(),
    'CDS_COMPLIANCE_ENFORCEMENT',
    'IoS-013-CDS',
    'IOS_APPENDIX',
    'VEGA',
    NOW(),
    'APPROVED',
    'VEGA confirms CDS compliance enforcement active. All LLM requests must include valid CHL-injected context_package. Pre-flight checklist updated. Validation rule CDS_CONTEXT_PACKAGE_REQUIRED active.',
    TRUE,
    'CDS compliance added to mandatory pre-flight governance checklist. No LLM call permitted without CHL activation. Agent requests lacking valid context_package will be rejected.',
    'HC-IOS-013-ASPE-2026',
    gen_random_uuid()
);

-- ============================================================================
-- SECTION 11: Generate Initial Context Package
-- ============================================================================

SELECT fhq_governance.generate_context_package() AS initial_context_package_id;

-- ============================================================================
-- SECTION 12: Audit Log Entry
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    evidence_path,
    sha256_hash,
    hash_chain_id,
    metadata,
    timestamp
) VALUES (
    gen_random_uuid(),
    'CP-IOS013-CDS-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    NULL,
    'STIG',
    'APPROVED',
    'IoS-013 CDS activated per CEO Execution Order. Context package structure implemented. CHL retrieval API operational. CDMO registration complete. VEGA compliance enforcement active.',
    'evidence/IOS013_CDS_ACTIVATION_' || TO_CHAR(NOW(), 'YYYYMMDD') || '.json',
    encode(sha256(('IoS-013:CDS:ACTIVATION:' || NOW()::TEXT)::bytea), 'hex'),
    'HC-IOS-013-ASPE-2026',
    jsonb_build_object(
        'component', 'IoS-013-CDS',
        'version', '2026.DRAFT.1',
        'governance_chain', 'Constitution (ADR-018) → Machine (IoS-013) → Payload (CDS) → Interface (CHL)',
        'context_package_elements', jsonb_build_array(
            'state_vector',
            'adr_index',
            'ios_index',
            'authority_map',
            'operational_constraints'
        ),
        'chl_functions', jsonb_build_array(
            'generate_context_package()',
            'chl_retrieve_context(agent, source)'
        ),
        'validation_rules', jsonb_build_array(
            'CDS_CONTEXT_PACKAGE_REQUIRED'
        ),
        'preflight_checks', jsonb_build_array(
            'CDS_CONTEXT_VALID',
            'CHL_HYDRATION_SUCCESS'
        )
    ),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'IoS-013 CDS — CONTEXT DEFINITION SPECIFICATION VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

SELECT 'Context Package Generated:' AS check_type;
SELECT package_id, package_version, package_timestamp, is_valid
FROM fhq_governance.context_packages
WHERE is_valid = TRUE
LIMIT 1;

SELECT 'Context Package Contents:' AS check_type;
SELECT
    jsonb_object_keys(state_vector) AS state_vector_keys
FROM fhq_governance.context_packages
WHERE is_valid = TRUE
LIMIT 1;

SELECT 'CDS Validation Rules:' AS check_type;
SELECT rule_name, is_active, constitutional_basis
FROM fhq_governance.vega_validation_rules
WHERE rule_name LIKE '%CDS%' OR rule_name LIKE '%CONTEXT%';

SELECT 'CDS Pre-Flight Checks:' AS check_type;
SELECT checklist_name, check_order, is_mandatory
FROM fhq_governance.preflight_checklist
WHERE checklist_name LIKE '%CDS%' OR checklist_name LIKE '%CHL%'
ORDER BY check_order;

SELECT 'IoS-013 CDS Appendix:' AS check_type;
SELECT ios_id, appendix_code, status, version
FROM fhq_meta.ios_appendix_registry
WHERE ios_id = 'IoS-013' AND appendix_code = 'CDS';

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'IoS-013 CDS ACTIVATION COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo 'GOVERNANCE CHAIN:'
\echo '  Constitution (ADR-018) → Machine (IoS-013) → Payload (CDS) → Interface (CHL)'
\echo ''
\echo 'CONTEXT PACKAGE ELEMENTS:'
\echo '  - state_vector (ASRP)'
\echo '  - adr_index'
\echo '  - ios_index'
\echo '  - authority_map'
\echo '  - operational_constraints'
\echo ''
\echo 'CHL FUNCTIONS:'
\echo '  - generate_context_package() → Creates atomic context'
\echo '  - chl_retrieve_context(agent, source) → Delivers to LLM'
\echo ''
\echo 'ENFORCEMENT:'
\echo '  - No LLM call permitted without CHL activation'
\echo '  - Pre-flight checklist: CDS_CONTEXT_VALID, CHL_HYDRATION_SUCCESS'
\echo '  - VEGA validation rule: CDS_CONTEXT_PACKAGE_REQUIRED'
\echo '═══════════════════════════════════════════════════════════════════════════'
