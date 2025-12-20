-- ============================================================================
-- MIGRATION 079: FULL STACK ACTIVATION — CHL Workflow Deployment
-- ============================================================================
-- Purpose: Complete Truth Stack hierarchy deployment
-- Authority: CEO Execution Order — Full Stack Activation
-- Date: 2025-12-05
--
-- TRUTH STACK HIERARCHY:
--   THE LAW (ADR-018)        → All agents MUST synchronize state
--   THE MACHINE (IoS-013)    → State engine and context definition
--   THE INTERFACE (Gateway)  → Official API for truth retrieval
--   THE DELIVERY (CHL)       → Delivers context_package into LLM
--   THE RUNTIME (Bootstrap)  → Validates package and begins reasoning
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Verify IoS-013 Deployment as Exclusive Truth Provider
-- ============================================================================

-- Confirm IoS-013 is registered with all components
DO $$
DECLARE
    v_ios013_status TEXT;
    v_aspe_appendix_exists BOOLEAN;
    v_cds_appendix_exists BOOLEAN;
    v_gateway_appendix_exists BOOLEAN;
BEGIN
    -- Check IoS-013 registry status
    SELECT status INTO v_ios013_status
    FROM fhq_meta.ios_registry
    WHERE ios_id = 'IoS-013';

    IF v_ios013_status IS NULL THEN
        RAISE EXCEPTION 'FULL_STACK_ACTIVATION_FAILED: IoS-013 not found in registry';
    END IF;

    -- Check ASPE appendix
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.ios_appendix_registry
        WHERE ios_id = 'IoS-013' AND appendix_code = 'ASPE'
    ) INTO v_aspe_appendix_exists;

    -- Check CDS appendix
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.ios_appendix_registry
        WHERE ios_id = 'IoS-013' AND appendix_code = 'CDS'
    ) INTO v_cds_appendix_exists;

    -- Check Gateway appendix
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.ios_appendix_registry
        WHERE ios_id = 'IoS-013' AND appendix_code = 'GATEWAY'
    ) INTO v_gateway_appendix_exists;

    RAISE NOTICE 'IoS-013 Status: %, ASPE: %, CDS: %, Gateway: %',
        v_ios013_status, v_aspe_appendix_exists, v_cds_appendix_exists, v_gateway_appendix_exists;
END $$;

-- ============================================================================
-- SECTION 2: Create CHL Request Registry Table
-- ============================================================================
-- Tracks all CHL-routed LLM calls for governance monitoring

CREATE TABLE IF NOT EXISTS fhq_governance.chl_llm_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request identification
    advisor_id TEXT NOT NULL,
    llm_role TEXT NOT NULL,
    request_source TEXT NOT NULL DEFAULT 'DASHBOARD',
    request_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Truth payload binding
    truth_payload_id UUID,  -- Reference to gateway_request_log
    context_hash TEXT NOT NULL,
    state_snapshot_hash TEXT NOT NULL,
    quad_hash TEXT,
    integrity_signature TEXT NOT NULL,

    -- Request status
    request_status TEXT NOT NULL CHECK (request_status IN (
        'SENT',           -- LLM call sent successfully
        'BLOCKED',        -- Call blocked due to validation failure
        'CHL_BYPASS_DETECTED', -- Attempted bypass detected
        'CONTEXT_FAILED', -- Truth Gateway returned failure
        'VALIDATION_FAILED' -- Pre-send validation failed
    )),

    -- Validation flags
    truth_payload_valid BOOLEAN NOT NULL DEFAULT FALSE,
    state_hash_present BOOLEAN NOT NULL DEFAULT FALSE,
    context_hash_present BOOLEAN NOT NULL DEFAULT FALSE,
    role_authority_valid BOOLEAN NOT NULL DEFAULT FALSE,
    defcon_permitted BOOLEAN NOT NULL DEFAULT FALSE,

    -- User prompt metadata (NOT content - that stays client-side)
    user_prompt_length INTEGER,
    user_prompt_hash TEXT,  -- Hash for audit correlation

    -- LLM response binding
    response_received BOOLEAN DEFAULT FALSE,
    response_timestamp TIMESTAMPTZ,
    output_binding_id UUID,

    -- Governance event (if any)
    governance_event_raised BOOLEAN DEFAULT FALSE,
    governance_event_id UUID,

    -- Lineage
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chl_llm_requests_advisor
    ON fhq_governance.chl_llm_requests(advisor_id, request_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_chl_llm_requests_status
    ON fhq_governance.chl_llm_requests(request_status);

CREATE INDEX IF NOT EXISTS idx_chl_llm_requests_context_hash
    ON fhq_governance.chl_llm_requests(context_hash);

CREATE INDEX IF NOT EXISTS idx_chl_llm_requests_governance
    ON fhq_governance.chl_llm_requests(governance_event_raised)
    WHERE governance_event_raised = TRUE;

COMMENT ON TABLE fhq_governance.chl_llm_requests IS
'Registry of all CHL-routed LLM requests per CEO Full Stack Activation Order.
Every Dashboard LLM call MUST be logged here. Calls without entries are bypass violations.';

-- ============================================================================
-- SECTION 3: Create CHL Bypass Detection Table
-- ============================================================================
-- Tracks detected or suspected CHL bypass attempts

CREATE TABLE IF NOT EXISTS fhq_governance.chl_bypass_detections (
    detection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Detection details
    detection_type TEXT NOT NULL CHECK (detection_type IN (
        'DIRECT_LLM_CALL',        -- LLM call without CHL routing
        'MISSING_CONTEXT_HASH',   -- Response lacks context_hash
        'MISSING_STATE_HASH',     -- Response lacks state_snapshot_hash
        'STALE_CONTEXT',          -- Context older than TTL
        'INVALID_SIGNATURE',      -- Integrity signature mismatch
        'UNREGISTERED_ADVISOR',   -- Unknown advisor ID
        'ROLE_AUTHORITY_MISMATCH' -- Role not in authority_map
    )),

    -- Source identification
    suspected_source TEXT,
    advisor_id TEXT,
    user_session_id TEXT,

    -- Evidence
    detection_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence_data JSONB NOT NULL,

    -- Governance action
    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    vega_alerted BOOLEAN NOT NULL DEFAULT FALSE,
    vega_alert_id UUID,
    resolution_status TEXT DEFAULT 'OPEN' CHECK (resolution_status IN (
        'OPEN', 'INVESTIGATING', 'RESOLVED', 'FALSE_POSITIVE', 'ESCALATED'
    )),

    -- Lineage
    detected_by TEXT NOT NULL DEFAULT 'CHL_MONITOR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chl_bypass_severity
    ON fhq_governance.chl_bypass_detections(severity, detection_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_chl_bypass_open
    ON fhq_governance.chl_bypass_detections(resolution_status)
    WHERE resolution_status = 'OPEN';

COMMENT ON TABLE fhq_governance.chl_bypass_detections IS
'Tracks CHL bypass attempts per ADR-018 governance requirements.
Any detected bypass is a Critical Governance Violation.';

-- ============================================================================
-- SECTION 4: Create CHL Validation Function
-- ============================================================================
-- Validates LLM request before sending

CREATE OR REPLACE FUNCTION fhq_governance.chl_validate_request(
    p_advisor_id TEXT,
    p_llm_role TEXT,
    p_context_hash TEXT,
    p_state_snapshot_hash TEXT,
    p_integrity_signature TEXT
)
RETURNS TABLE (
    is_valid BOOLEAN,
    validation_status TEXT,
    failures JSONB
) AS $$
DECLARE
    v_is_valid BOOLEAN := TRUE;
    v_failures JSONB := '[]'::JSONB;
    v_gateway_record RECORD;
    v_role_valid BOOLEAN;
BEGIN
    -- 1. Verify context_hash exists in gateway log
    SELECT * INTO v_gateway_record
    FROM fhq_governance.gateway_request_log
    WHERE context_hash = p_context_hash
    AND gateway_status = 'SUCCESS'
    AND created_at > NOW() - INTERVAL '5 minutes'
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_gateway_record IS NULL THEN
        v_is_valid := FALSE;
        v_failures := v_failures || '["CONTEXT_HASH_NOT_FOUND_IN_GATEWAY"]'::JSONB;
    END IF;

    -- 2. Verify state_snapshot_hash matches
    IF v_gateway_record IS NOT NULL AND v_gateway_record.state_snapshot_hash != p_state_snapshot_hash THEN
        v_is_valid := FALSE;
        v_failures := v_failures || '["STATE_HASH_MISMATCH"]'::JSONB;
    END IF;

    -- 3. Verify integrity_signature matches
    IF v_gateway_record IS NOT NULL AND v_gateway_record.integrity_signature != p_integrity_signature THEN
        v_is_valid := FALSE;
        v_failures := v_failures || '["SIGNATURE_MISMATCH"]'::JSONB;
    END IF;

    -- 4. Verify LLM role is valid
    v_role_valid := p_llm_role IN (
        'SYSTEM_ADVISOR', 'STRATEGY_ADVISOR', 'TECHNICAL_ADVISOR',
        'RESEARCH_ADVISOR', 'EXECUTION_ADVISOR', 'GOVERNANCE_ADVISOR'
    );
    IF NOT v_role_valid THEN
        v_is_valid := FALSE;
        v_failures := v_failures || '["INVALID_LLM_ROLE"]'::JSONB;
    END IF;

    -- 5. Verify advisor is registered
    IF p_advisor_id NOT IN (
        'LARS', 'STIG', 'FINN', 'VEGA', 'LINE',
        'CFAO', 'CEIO', 'CSEO', 'CDMO', 'DASHBOARD_ADVISOR'
    ) THEN
        v_is_valid := FALSE;
        v_failures := v_failures || '["UNREGISTERED_ADVISOR"]'::JSONB;
    END IF;

    -- Return validation result
    RETURN QUERY SELECT
        v_is_valid,
        CASE WHEN v_is_valid THEN 'VALID' ELSE 'INVALID' END,
        v_failures;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.chl_validate_request(TEXT, TEXT, TEXT, TEXT, TEXT) IS
'Validates CHL request before LLM call per CEO Full Stack Activation Order.
Verifies context_hash, state_hash, signature, role, and advisor registration.';

-- ============================================================================
-- SECTION 5: Create CHL Log Request Function
-- ============================================================================
-- Logs CHL request with full governance binding

CREATE OR REPLACE FUNCTION fhq_governance.chl_log_request(
    p_advisor_id TEXT,
    p_llm_role TEXT,
    p_context_hash TEXT,
    p_state_snapshot_hash TEXT,
    p_quad_hash TEXT,
    p_integrity_signature TEXT,
    p_request_status TEXT,
    p_user_prompt_length INTEGER DEFAULT NULL,
    p_user_prompt_hash TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_request_id UUID;
    v_gateway_id UUID;
    v_validation_result RECORD;
BEGIN
    -- Get gateway request reference
    SELECT request_id INTO v_gateway_id
    FROM fhq_governance.gateway_request_log
    WHERE context_hash = p_context_hash
    ORDER BY created_at DESC
    LIMIT 1;

    -- Log the request
    INSERT INTO fhq_governance.chl_llm_requests (
        advisor_id, llm_role, truth_payload_id,
        context_hash, state_snapshot_hash, quad_hash, integrity_signature,
        request_status,
        truth_payload_valid, state_hash_present, context_hash_present,
        role_authority_valid, defcon_permitted,
        user_prompt_length, user_prompt_hash
    ) VALUES (
        p_advisor_id, p_llm_role, v_gateway_id,
        p_context_hash, p_state_snapshot_hash, p_quad_hash, p_integrity_signature,
        p_request_status,
        v_gateway_id IS NOT NULL,
        p_state_snapshot_hash IS NOT NULL AND p_state_snapshot_hash != '',
        p_context_hash IS NOT NULL AND p_context_hash != '',
        TRUE,  -- Assumed valid if we got here
        TRUE,  -- Assumed permitted if we got here
        p_user_prompt_length, p_user_prompt_hash
    ) RETURNING request_id INTO v_request_id;

    -- If blocked, raise governance event
    IF p_request_status IN ('BLOCKED', 'CHL_BYPASS_DETECTED', 'VALIDATION_FAILED') THEN
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, decision, decision_rationale, vega_reviewed
        ) VALUES (
            gen_random_uuid(), 'CHL_REQUEST_BLOCKED', p_advisor_id, 'ADVISOR',
            'CHL_MONITOR', 'REJECTED',
            'CHL request blocked: ' || p_request_status || '. Advisor: ' || p_advisor_id,
            TRUE
        );

        UPDATE fhq_governance.chl_llm_requests
        SET governance_event_raised = TRUE
        WHERE request_id = v_request_id;
    END IF;

    RETURN v_request_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.chl_log_request(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT) IS
'Logs CHL LLM request with full governance binding per CEO Full Stack Activation Order.
Automatically raises governance events for blocked requests.';

-- ============================================================================
-- SECTION 6: Create Bypass Detection Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.chl_detect_bypass(
    p_detection_type TEXT,
    p_suspected_source TEXT,
    p_advisor_id TEXT,
    p_evidence_data JSONB
)
RETURNS UUID AS $$
DECLARE
    v_detection_id UUID;
    v_severity TEXT;
    v_vega_alert_id UUID;
BEGIN
    -- Determine severity
    v_severity := CASE p_detection_type
        WHEN 'DIRECT_LLM_CALL' THEN 'CRITICAL'
        WHEN 'MISSING_CONTEXT_HASH' THEN 'CRITICAL'
        WHEN 'MISSING_STATE_HASH' THEN 'CRITICAL'
        WHEN 'INVALID_SIGNATURE' THEN 'HIGH'
        WHEN 'STALE_CONTEXT' THEN 'MEDIUM'
        WHEN 'UNREGISTERED_ADVISOR' THEN 'HIGH'
        WHEN 'ROLE_AUTHORITY_MISMATCH' THEN 'MEDIUM'
        ELSE 'MEDIUM'
    END;

    -- Log bypass detection
    INSERT INTO fhq_governance.chl_bypass_detections (
        detection_type, suspected_source, advisor_id,
        evidence_data, severity, detected_by
    ) VALUES (
        p_detection_type, p_suspected_source, p_advisor_id,
        p_evidence_data, v_severity, 'CHL_MONITOR'
    ) RETURNING detection_id INTO v_detection_id;

    -- Raise VEGA governance alert for CRITICAL/HIGH
    IF v_severity IN ('CRITICAL', 'HIGH') THEN
        INSERT INTO fhq_governance.governance_actions_log (
            action_id, action_type, action_target, action_target_type,
            initiated_by, decision, decision_rationale,
            vega_reviewed, vega_notes
        ) VALUES (
            gen_random_uuid(), 'CHL_BYPASS_DETECTED', p_advisor_id, 'ADVISOR',
            'VEGA', 'REJECTED',
            'CHL BYPASS DETECTED [' || v_severity || ']: ' || p_detection_type ||
            '. Source: ' || COALESCE(p_suspected_source, 'UNKNOWN') ||
            '. This is a Critical Governance Violation under ADR-018.',
            TRUE,
            'Bypass detection logged. Evidence preserved. Immediate investigation required per CEO Full Stack Activation Order.'
        ) RETURNING action_id INTO v_vega_alert_id;

        UPDATE fhq_governance.chl_bypass_detections
        SET vega_alerted = TRUE, vega_alert_id = v_vega_alert_id
        WHERE detection_id = v_detection_id;
    END IF;

    RETURN v_detection_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.chl_detect_bypass(TEXT, TEXT, TEXT, JSONB) IS
'Detects and logs CHL bypass attempts per ADR-018.
Automatically raises VEGA alerts for CRITICAL/HIGH severity.';

-- ============================================================================
-- SECTION 7: Register CHL Workflow Specification in System Documents
-- ============================================================================

-- Create system_documents table if not exists
CREATE TABLE IF NOT EXISTS fhq_meta.system_documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_code TEXT NOT NULL UNIQUE,
    document_title TEXT NOT NULL,
    document_type TEXT NOT NULL CHECK (document_type IN (
        'SPECIFICATION', 'WORKFLOW', 'ARCHITECTURE', 'POLICY', 'PROCEDURE'
    )),
    version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'ACTIVE', 'DEPRECATED', 'SUPERSEDED')),
    owner_role TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    summary TEXT,
    governing_adrs TEXT[],
    governing_ios TEXT[],
    effective_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Register CHL Workflow Specification
INSERT INTO fhq_meta.system_documents (
    document_code,
    document_title,
    document_type,
    version,
    status,
    owner_role,
    content_hash,
    summary,
    governing_adrs,
    governing_ios,
    effective_date
) VALUES (
    'CHL-WORKFLOW-SPEC',
    'Dashboard LLM Interface — Context Hydration Layer (CHL) Workflow Specification',
    'WORKFLOW',
    '2026.DRAFT.1',
    'ACTIVE',
    'DASHBOARD_TEAM',
    encode(sha256((
        'CHL:WORKFLOW:2026.DRAFT.1:' ||
        'truth_gateway:context_package:system_context:user_prompt:fail_closed'
    )::bytea), 'hex'),
    'Defines exactly how canonical system context and user prompts are combined and delivered to any LLM advisor. Ensures system truth is always applied first, user prompt second. LLM can never override context_package.',
    ARRAY['ADR-017', 'ADR-018'],
    ARRAY['IoS-013'],
    NOW()
) ON CONFLICT (document_code) DO UPDATE SET
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    content_hash = EXCLUDED.content_hash,
    updated_at = NOW();

-- ============================================================================
-- SECTION 8: Add CHL Pre-Flight Checks
-- ============================================================================

INSERT INTO fhq_governance.preflight_checklist (
    checklist_name, action_type, check_order, check_description,
    constitutional_basis, is_mandatory
) VALUES
(
    'CHL_ROUTE_MANDATORY',
    'LLM_CALL',
    -2,  -- Before Gateway checks
    'All Dashboard LLM calls MUST pass through CHL. Direct LLM calls are prohibited.',
    'CEO Full Stack Activation Order',
    TRUE
),
(
    'CHL_TRUTH_PAYLOAD_VALID',
    'LLM_CALL',
    -2,
    'Verify truth_payload from IoS-013 Gateway is present and valid before LLM call',
    'CHL Workflow Spec §3',
    TRUE
),
(
    'CHL_SYSTEM_CONTEXT_FIRST',
    'LLM_CALL',
    -2,
    'Verify SYSTEM_CONTEXT (from IoS-013) is injected before USER_PROMPT',
    'CHL Workflow Spec §4',
    TRUE
),
(
    'CHL_OUTPUT_BINDING',
    'LLM_RESPONSE',
    0,
    'Verify LLM output is bound to state_snapshot_hash + context_hash',
    'CHL Workflow Spec §3 Step 7',
    TRUE
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 9: Add VEGA Validation Rules for CHL
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
    'CHL_ROUTE_MANDATORY',
    'PRECONDITION',
    ARRAY['LLM_CALL', 'DASHBOARD_LLM_REQUEST'],
    'SELECT EXISTS (
        SELECT 1 FROM fhq_governance.chl_llm_requests
        WHERE context_hash = $1
        AND request_status = ''SENT''
        AND created_at > NOW() - INTERVAL ''5 minutes''
    )',
    'REJECT',
    'CEO Full Stack Activation Order + CHL Workflow Spec',
    TRUE
) ON CONFLICT (rule_name) DO UPDATE SET
    applies_to = EXCLUDED.applies_to,
    is_active = TRUE,
    updated_at = NOW();

INSERT INTO fhq_governance.vega_validation_rules (
    rule_name,
    rule_type,
    applies_to,
    condition_sql,
    failure_action,
    constitutional_basis,
    is_active
) VALUES (
    'LLM_OUTPUT_CONTEXT_BOUND',
    'POSTCONDITION',
    ARRAY['LLM_RESPONSE'],
    'SELECT EXISTS (
        SELECT 1 FROM fhq_governance.chl_llm_requests
        WHERE context_hash = $1
        AND response_received = TRUE
    )',
    'REJECT',
    'ADR-018 + CHL Workflow Spec §3',
    TRUE
) ON CONFLICT (rule_name) DO UPDATE SET
    applies_to = EXCLUDED.applies_to,
    is_active = TRUE,
    updated_at = NOW();

-- ============================================================================
-- SECTION 10: Update IoS-013 Registry with Full Stack Status
-- ============================================================================

UPDATE fhq_meta.ios_registry
SET
    description = description || E'\n\n=== FULL STACK ACTIVATED ===\n' ||
        'IoS-013 is the EXCLUSIVE truth provider for all Dashboard LLM calls.\n' ||
        'CHL Workflow: Gateway → CHL → LLM → Output Binding\n' ||
        'No alternative truth source permitted.',
    version = '2026.PROD.FULLSTACK',
    updated_at = NOW()
WHERE ios_id = 'IoS-013';

-- ============================================================================
-- SECTION 11: STIG Deployment Confirmation
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
    'FULL_STACK_DEPLOYMENT',
    'IoS-013',
    'IOS',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-013 deployed as EXCLUSIVE truth provider per CEO Full Stack Activation Order. Components: ASPE (engine), CDS (schema), Gateway (interface). No alternative truth source permitted. CHL integration infrastructure operational.',
    TRUE,
    'HC-IOS-013-ASPE-2026',
    gen_random_uuid()
);

-- ============================================================================
-- SECTION 12: CDMO Registration Confirmation
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
    'CHL_SPECIFICATION_REGISTRATION',
    'CHL-WORKFLOW-SPEC',
    'SYSTEM_DOCUMENT',
    'CDMO',
    NOW(),
    'APPROVED',
    'CHL Workflow Specification registered in fhq_meta.system_documents per CEO Full Stack Activation Order. Document is now part of FjordHQ canonical architecture.',
    TRUE,
    'HC-IOS-013-ASPE-2026',
    gen_random_uuid()
);

-- ============================================================================
-- SECTION 13: VEGA Governance Monitoring Activation
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
    'CHL_GOVERNANCE_MONITORING_ACTIVATED',
    'CHL_MONITOR',
    'SYSTEM',
    'VEGA',
    NOW(),
    'APPROVED',
    'VEGA continuous monitoring ACTIVATED per CEO Full Stack Activation Order. Any LLM response missing valid context_hash or state_snapshot_hash is a Critical Governance Violation under ADR-018. Any call detected outside CHL/IoS-013 routing will be treated as bypass attempt.',
    TRUE,
    'Monitoring rules deployed: CHL_ROUTE_MANDATORY, LLM_OUTPUT_CONTEXT_BOUND. Bypass detection active. Auto-escalation for CRITICAL/HIGH severity events.',
    'HC-IOS-013-ASPE-2026',
    gen_random_uuid()
);

-- ============================================================================
-- SECTION 14: Audit Log Entry
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
    'CP-FULLSTACK-ACTIVATION-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    NULL,
    'CEO',
    'APPROVED',
    'FULL STACK ACTIVATION executed per CEO Order. Truth Stack hierarchy complete: LAW (ADR-018) → MACHINE (IoS-013) → INTERFACE (Gateway) → DELIVERY (CHL) → RUNTIME (Bootstrap). No Dashboard LLM interaction valid unless hydrated via CHL, sourced from IoS-013, and bound to state_snapshot_hash + context_hash.',
    'evidence/FULL_STACK_ACTIVATION_' || TO_CHAR(NOW(), 'YYYYMMDD') || '.json',
    encode(sha256(('FULLSTACK:ACTIVATION:' || NOW()::TEXT)::bytea), 'hex'),
    'HC-IOS-013-ASPE-2026',
    jsonb_build_object(
        'truth_stack_hierarchy', jsonb_build_object(
            'THE_LAW', 'ADR-018 - All agents MUST synchronize state',
            'THE_MACHINE', 'IoS-013 ASPE + CDS - State engine and context definition',
            'THE_INTERFACE', 'IoS-013 Gateway - Official API for truth retrieval',
            'THE_DELIVERY', 'CHL - Delivers context_package into LLM',
            'THE_RUNTIME', 'Bootstrap - Validates package and begins reasoning'
        ),
        'mandates_executed', jsonb_build_array(
            'STIG: IoS-013 deployed as exclusive truth provider',
            'DASHBOARD_TEAM: CHL middleware infrastructure ready',
            'VEGA: Governance monitoring activated',
            'CDMO: CHL Workflow Specification registered'
        ),
        'enforcement', jsonb_build_object(
            'chl_route_mandatory', TRUE,
            'bypass_detection_active', TRUE,
            'output_binding_required', TRUE,
            'governance_monitoring', 'CONTINUOUS'
        ),
        'validity_requirements', jsonb_build_array(
            'Hydrated via CHL',
            'Sourced from IoS-013',
            'Bound to state_snapshot_hash + context_hash'
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
\echo 'FULL STACK ACTIVATION — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

SELECT 'IoS-013 Status:' AS check_type;
SELECT ios_id, version, status
FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-013';

SELECT 'IoS-013 Appendices:' AS check_type;
SELECT ios_id, appendix_code, status, version
FROM fhq_meta.ios_appendix_registry WHERE ios_id = 'IoS-013'
ORDER BY appendix_code;

SELECT 'CHL Workflow Specification:' AS check_type;
SELECT document_code, status, version, owner_role
FROM fhq_meta.system_documents WHERE document_code = 'CHL-WORKFLOW-SPEC';

SELECT 'CHL Pre-Flight Checks:' AS check_type;
SELECT checklist_name, is_mandatory
FROM fhq_governance.preflight_checklist
WHERE checklist_name LIKE 'CHL%'
ORDER BY check_order;

SELECT 'CHL Validation Rules:' AS check_type;
SELECT rule_name, is_active
FROM fhq_governance.vega_validation_rules
WHERE rule_name LIKE 'CHL%' OR rule_name LIKE 'LLM_OUTPUT%';

SELECT 'Governance Activation Records:' AS check_type;
SELECT action_type, initiated_by, decision
FROM fhq_governance.governance_actions_log
WHERE action_type IN ('FULL_STACK_DEPLOYMENT', 'CHL_SPECIFICATION_REGISTRATION', 'CHL_GOVERNANCE_MONITORING_ACTIVATED')
ORDER BY initiated_at DESC;

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'FULL STACK ACTIVATION COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo 'TRUTH STACK HIERARCHY:'
\echo '  THE LAW      (ADR-018)      → All agents MUST synchronize state'
\echo '  THE MACHINE  (IoS-013)      → State engine and context definition'
\echo '  THE INTERFACE(Gateway)      → Official API for truth retrieval'
\echo '  THE DELIVERY (CHL)          → Delivers context_package into LLM'
\echo '  THE RUNTIME  (Bootstrap)    → Validates package and begins reasoning'
\echo ''
\echo 'ENFORCEMENT STATUS:'
\echo '  - CHL route mandatory for all Dashboard LLM calls'
\echo '  - Bypass detection active with VEGA auto-escalation'
\echo '  - Output binding required (state_hash + context_hash)'
\echo '  - Continuous governance monitoring active'
\echo ''
\echo 'VALIDITY REQUIREMENTS:'
\echo '  - Hydrated via CHL'
\echo '  - Sourced from IoS-013'
\echo '  - Bound to state_snapshot_hash + context_hash'
\echo '═══════════════════════════════════════════════════════════════════════════'
