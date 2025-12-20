-- ============================================================================
-- MIGRATION 074: ADR-017 MIT QUAD PROTOCOL REGISTRATION
-- ============================================================================
-- ADR: ADR-017 — The MIT Quad Protocol for Alpha Sovereignty
-- Gate: G0_SUBMISSION (CEO Mandated)
-- Owner: CEO
-- Technical Authority: STIG
-- Date: 2025-12-05
--
-- PURPOSE: Register ADR-017 as Constitutional Law and implement MIT Quad
--          infrastructure for LIDS-ACL-DSL-RISL governance.
--
-- SCOPE:
--   1. Register ADR-017 in adr_registry (CONSTITUTIONAL)
--   2. Create MIT Quad pillar mapping table
--   3. Create Quad-Hash tracking infrastructure
--   4. Map IoS modules to MIT Quad pillars
--   5. Create governance validation rules
--   6. Log governance action
--
-- CONSTITUTIONAL MANDATE:
--   - MIT Quad compliance as mandatory precondition for strategy activation
--   - Quad-Hash required for every trade and strategy output
--   - RISL immunity logic as escalation path under ADR-016
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Register ADR-017 in ADR Registry
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_status,
    adr_type,
    current_version,
    approval_authority,
    effective_date,
    governance_tier,
    created_by,
    owner,
    description,
    vega_attested
) VALUES (
    'ADR-017',
    'The MIT Quad Protocol for Alpha Sovereignty',
    'APPROVED',
    'CONSTITUTIONAL',
    '2026.PROD.1',
    'CEO',
    CURRENT_DATE,
    'Tier-1',
    'CEO',
    'CEO',
    'Establishes the MIT Quad (LIDS-ACL-DSL-RISL) as the methodological engine of FjordHQ. Upgrades the system from Automated to Autonomous via: Sense (LIDS) → Coordinate (ACL) → Act (DSL) → Survive (RISL). Implements the Freedom Formula and enforces Quad-Hash traceability for every transaction.',
    false
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_title = EXCLUDED.adr_title,
    adr_status = EXCLUDED.adr_status,
    adr_type = EXCLUDED.adr_type,
    current_version = EXCLUDED.current_version,
    description = EXCLUDED.description,
    effective_date = EXCLUDED.effective_date;

-- Register ADR-017 dependencies
INSERT INTO fhq_meta.adr_dependencies (
    adr_id,
    version,
    depends_on,
    dependency_type,
    criticality
) VALUES (
    'ADR-017',
    '2026.PROD.1',
    ARRAY['ADR-001', 'ADR-013', 'IoS-005', 'IoS-010'],
    'CONSTITUTIONAL',
    'CRITICAL'
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 2: Create MIT Quad Pillar Registry
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.mit_quad_pillars (
    pillar_id TEXT PRIMARY KEY,
    pillar_name TEXT NOT NULL,
    lab_name TEXT NOT NULL,
    core_function TEXT NOT NULL,
    mit_methodology TEXT NOT NULL,
    fhq_implementation TEXT NOT NULL,
    primary_ios TEXT[],
    primary_agents TEXT[],
    constitutional_basis TEXT NOT NULL DEFAULT 'ADR-017',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.mit_quad_pillars IS
'Registry of MIT Quad pillars per ADR-017. Maps MIT research domains to FjordHQ functional requirements.';

-- Insert the four pillars
INSERT INTO fhq_governance.mit_quad_pillars (
    pillar_id, pillar_name, lab_name, core_function, mit_methodology,
    fhq_implementation, primary_ios, primary_agents
) VALUES
(
    'LIDS',
    'THE BRAIN',
    'Lab for Information & Decision Systems',
    'Inference & Truth',
    'Inference over Networks, ADEV Framework',
    'STIG Gateway (Control Plane): Calculates probability of signal truth. Enforces No-Math protocol.',
    ARRAY['IoS-003', 'IoS-005', 'IoS-007'],
    ARRAY['FINN', 'STIG']
),
(
    'ACL',
    'THE MANAGER',
    'Aerospace Controls Lab',
    'Coordination',
    'CBBA (Consensus-Based Bundle Algorithm), Robust Planning',
    'ADR-007 Orchestrator: Agents bid on tasks. Decentralized task assignment without human PM.',
    ARRAY['IoS-008'],
    ARRAY['LARS', 'LINE']
),
(
    'DSL',
    'THE ENGINE',
    'Data Science Lab',
    'Optimization',
    'Stochastic Optimization, Simchi-Levi Algorithms',
    'IoS-004 Allocation Engine: Optimizes bet sizing under uncertainty constraints.',
    ARRAY['IoS-004', 'IoS-012'],
    ARRAY['LARS', 'LINE']
),
(
    'RISL',
    'THE SHIELD',
    'Resilient Infrastructure Lab',
    'Immunity',
    'Adversarial Robustness, Failure Detection',
    'IoS-010 Circuit Breakers: Detects hallucination loops & data attacks. Cuts connectivity automatically.',
    ARRAY['IoS-010', 'IoS-013'],
    ARRAY['VEGA', 'STIG']
)
ON CONFLICT (pillar_id) DO UPDATE SET
    pillar_name = EXCLUDED.pillar_name,
    lab_name = EXCLUDED.lab_name,
    core_function = EXCLUDED.core_function,
    mit_methodology = EXCLUDED.mit_methodology,
    fhq_implementation = EXCLUDED.fhq_implementation,
    primary_ios = EXCLUDED.primary_ios,
    primary_agents = EXCLUDED.primary_agents,
    updated_at = NOW();

-- ============================================================================
-- SECTION 3: Create Quad-Hash Tracking Table
-- ============================================================================
-- Per ADR-017 §4: Every trade must reference the Quad-Hash

CREATE TABLE IF NOT EXISTS fhq_governance.quad_hash_registry (
    quad_hash_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The Quad-Hash components
    lids_score NUMERIC NOT NULL CHECK (lids_score >= 0 AND lids_score <= 1),
    acl_agent TEXT NOT NULL,
    dsl_model TEXT NOT NULL,
    risl_status TEXT NOT NULL CHECK (risl_status IN ('HEALTHY', 'DEGRADED', 'ISOLATED', 'HALTED')),

    -- Computed Quad-Hash: {LIDS_Score}_{ACL_Agent}_{DSL_Model}_{RISL_Status}
    quad_hash TEXT NOT NULL UNIQUE,

    -- State context (from IoS-013 ASPE)
    state_snapshot_hash TEXT NOT NULL,
    state_timestamp TIMESTAMPTZ NOT NULL,

    -- Validation
    lids_threshold_met BOOLEAN NOT NULL DEFAULT FALSE,  -- P(Truth) > 0.85
    is_valid BOOLEAN NOT NULL DEFAULT FALSE,

    -- Lineage
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL,
    hash_self TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quad_hash_registry_hash
    ON fhq_governance.quad_hash_registry(quad_hash);

CREATE INDEX IF NOT EXISTS idx_quad_hash_registry_state
    ON fhq_governance.quad_hash_registry(state_snapshot_hash);

CREATE INDEX IF NOT EXISTS idx_quad_hash_registry_valid
    ON fhq_governance.quad_hash_registry(is_valid) WHERE is_valid = TRUE;

COMMENT ON TABLE fhq_governance.quad_hash_registry IS
'Registry of Quad-Hashes per ADR-017 §4. Every trade/strategy output must reference a valid Quad-Hash.
Format: {LIDS_Score}_{ACL_Agent}_{DSL_Model}_{RISL_Status}';

-- ============================================================================
-- SECTION 4: Create Quad-Hash Generation Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.generate_quad_hash(
    p_lids_score NUMERIC,
    p_acl_agent TEXT,
    p_dsl_model TEXT,
    p_risl_status TEXT,
    p_state_hash TEXT,
    p_state_timestamp TIMESTAMPTZ,
    p_created_by TEXT
)
RETURNS TEXT AS $$
DECLARE
    v_quad_hash TEXT;
    v_lids_threshold_met BOOLEAN;
    v_is_valid BOOLEAN;
    v_hash_self TEXT;
BEGIN
    -- Generate the Quad-Hash string
    v_quad_hash := ROUND(p_lids_score, 4)::TEXT || '_' ||
                   p_acl_agent || '_' ||
                   p_dsl_model || '_' ||
                   p_risl_status;

    -- Check LIDS threshold (P(Truth) > 0.85 per ADR-017 §3.1)
    v_lids_threshold_met := p_lids_score > 0.85;

    -- Quad-Hash is valid if LIDS threshold met and RISL not halted
    v_is_valid := v_lids_threshold_met AND p_risl_status != 'HALTED';

    -- Compute hash_self
    v_hash_self := encode(sha256((v_quad_hash || ':' || p_state_hash || ':' || NOW()::TEXT)::bytea), 'hex');

    -- Insert into registry
    INSERT INTO fhq_governance.quad_hash_registry (
        lids_score, acl_agent, dsl_model, risl_status,
        quad_hash, state_snapshot_hash, state_timestamp,
        lids_threshold_met, is_valid, created_by, hash_self
    ) VALUES (
        p_lids_score, p_acl_agent, p_dsl_model, p_risl_status,
        v_quad_hash, p_state_hash, p_state_timestamp,
        v_lids_threshold_met, v_is_valid, p_created_by, v_hash_self
    )
    ON CONFLICT (quad_hash) DO UPDATE SET
        state_snapshot_hash = p_state_hash,
        state_timestamp = p_state_timestamp;

    RETURN v_quad_hash;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.generate_quad_hash IS
'Generates and registers a Quad-Hash per ADR-017 §4.
Validates LIDS threshold (>0.85) and RISL status.
Returns the Quad-Hash string for audit trail binding.';

-- ============================================================================
-- SECTION 5: Create IoS Module to MIT Quad Mapping Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.ios_quad_mapping (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    pillar_id TEXT NOT NULL REFERENCES fhq_governance.mit_quad_pillars(pillar_id),
    role_description TEXT NOT NULL,
    implements_function TEXT NOT NULL,
    constitutional_basis TEXT NOT NULL DEFAULT 'ADR-017',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ios_quad_mapping_unique UNIQUE (ios_id, pillar_id)
);

COMMENT ON TABLE fhq_governance.ios_quad_mapping IS
'Maps IoS modules to MIT Quad pillars per ADR-017. Ensures all modules are aligned with constitutional roles.';

-- Insert IoS to Quad mappings
INSERT INTO fhq_governance.ios_quad_mapping (ios_id, pillar_id, role_description, implements_function, is_primary) VALUES
-- LIDS (The Brain) - Inference & Truth
('IoS-003', 'LIDS', 'Meta-Perception Engine - Market regime detection', 'Calculates P(Regime) for signal truth assessment', TRUE),
('IoS-005', 'LIDS', 'Forecast Calibration & Skill Engine - Prediction accuracy', 'Measures signal precision and calibration', TRUE),
('IoS-007', 'LIDS', 'Alpha Graph Engine - Causal reasoning', 'Provides causal inference for truth validation', TRUE),
('IoS-009', 'LIDS', 'Meta-Perception Layer - Intent & stress detection', 'Detects market intent for inference', FALSE),

-- ACL (The Manager) - Coordination
('IoS-008', 'ACL', 'Runtime Decision Engine - Task orchestration', 'Implements CBBA-style task assignment', TRUE),
('IoS-012', 'ACL', 'Execution Engine - Trade coordination', 'Coordinates execution across agents', FALSE),

-- DSL (The Engine) - Optimization
('IoS-004', 'DSL', 'Regime-Driven Allocation Engine - Position sizing', 'Stochastic optimization under uncertainty', TRUE),
('IoS-012', 'DSL', 'Execution Engine - Order optimization', 'Optimizes order execution and slippage', FALSE),

-- RISL (The Shield) - Immunity
('IoS-010', 'RISL', 'Prediction Ledger Engine - Failure detection', 'Detects prediction failures and hallucination', TRUE),
('IoS-013', 'RISL', 'Agent State Protocol Engine - State integrity', 'Enforces fail-closed semantics and isolation', TRUE)
ON CONFLICT (ios_id, pillar_id) DO UPDATE SET
    role_description = EXCLUDED.role_description,
    implements_function = EXCLUDED.implements_function,
    is_primary = EXCLUDED.is_primary,
    updated_at = NOW();

-- ============================================================================
-- SECTION 6: Create Quad Compliance Validation Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.validate_quad_compliance(
    p_agent_id TEXT,
    p_action_type TEXT,
    p_quad_hash TEXT DEFAULT NULL
)
RETURNS TABLE (
    is_compliant BOOLEAN,
    lids_status TEXT,
    acl_status TEXT,
    dsl_status TEXT,
    risl_status TEXT,
    rejection_reason TEXT
) AS $$
DECLARE
    v_quad RECORD;
    v_defcon TEXT;
BEGIN
    -- Get current DEFCON
    SELECT current_defcon::TEXT INTO v_defcon
    FROM fhq_governance.system_state
    WHERE is_active = TRUE
    LIMIT 1;

    -- If Quad-Hash provided, validate it
    IF p_quad_hash IS NOT NULL THEN
        SELECT * INTO v_quad
        FROM fhq_governance.quad_hash_registry
        WHERE quad_hash = p_quad_hash;

        IF v_quad IS NULL THEN
            RETURN QUERY SELECT
                FALSE,
                'UNKNOWN'::TEXT,
                'UNKNOWN'::TEXT,
                'UNKNOWN'::TEXT,
                'UNKNOWN'::TEXT,
                'Quad-Hash not found in registry'::TEXT;
            RETURN;
        END IF;

        IF NOT v_quad.is_valid THEN
            RETURN QUERY SELECT
                FALSE,
                CASE WHEN v_quad.lids_threshold_met THEN 'PASS' ELSE 'FAIL' END,
                'UNKNOWN'::TEXT,
                'UNKNOWN'::TEXT,
                v_quad.risl_status,
                'Quad-Hash invalid: LIDS threshold not met or RISL halted'::TEXT;
            RETURN;
        END IF;

        -- Valid Quad-Hash
        RETURN QUERY SELECT
            TRUE,
            'PASS'::TEXT,
            v_quad.acl_agent,
            v_quad.dsl_model,
            v_quad.risl_status,
            NULL::TEXT;
        RETURN;
    END IF;

    -- No Quad-Hash provided - check if action requires one
    IF p_action_type IN ('TRADE', 'EXECUTION_PLAN', 'ALLOCATION', 'STRATEGY_PROPOSAL') THEN
        RETURN QUERY SELECT
            FALSE,
            'UNKNOWN'::TEXT,
            'UNKNOWN'::TEXT,
            'UNKNOWN'::TEXT,
            'UNKNOWN'::TEXT,
            'Quad-Hash required for action type: ' || p_action_type;
        RETURN;
    END IF;

    -- Action doesn't require Quad-Hash
    RETURN QUERY SELECT
        TRUE,
        'N/A'::TEXT,
        'N/A'::TEXT,
        'N/A'::TEXT,
        COALESCE(v_defcon, 'GREEN'),
        NULL::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.validate_quad_compliance IS
'Validates MIT Quad compliance per ADR-017 §4.
Checks Quad-Hash validity for trades and strategy outputs.
Returns compliance status for each pillar.';

-- ============================================================================
-- SECTION 7: Create RISL Immunity Escalation Function
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.risl_escalate_immunity(
    p_trigger_type TEXT,
    p_agent_id TEXT,
    p_evidence JSONB
)
RETURNS TEXT AS $$
DECLARE
    v_current_defcon TEXT;
    v_new_defcon TEXT;
    v_action TEXT;
BEGIN
    -- Get current DEFCON
    SELECT current_defcon::TEXT INTO v_current_defcon
    FROM fhq_governance.system_state
    WHERE is_active = TRUE;

    -- Determine escalation based on trigger type
    CASE p_trigger_type
        WHEN 'DATA_DRIFT' THEN
            v_new_defcon := CASE
                WHEN v_current_defcon = 'GREEN' THEN 'YELLOW'
                WHEN v_current_defcon = 'YELLOW' THEN 'ORANGE'
                ELSE v_current_defcon
            END;
            v_action := 'MONITOR';

        WHEN 'AGENT_HALLUCINATION' THEN
            v_new_defcon := CASE
                WHEN v_current_defcon IN ('GREEN', 'YELLOW') THEN 'ORANGE'
                WHEN v_current_defcon = 'ORANGE' THEN 'RED'
                ELSE v_current_defcon
            END;
            v_action := 'ISOLATE';

        WHEN 'PREDICTION_FAILURE' THEN
            v_new_defcon := 'YELLOW';
            v_action := 'REVIEW';

        WHEN 'LIDS_THRESHOLD_BREACH' THEN
            v_new_defcon := 'YELLOW';
            v_action := 'PAUSE_ALLOCATION';

        WHEN 'CONSENSUS_FAILURE' THEN
            v_new_defcon := 'ORANGE';
            v_action := 'HALT_EXECUTION';

        ELSE
            v_new_defcon := v_current_defcon;
            v_action := 'LOG';
    END CASE;

    -- Log the RISL escalation
    INSERT INTO fhq_governance.asrp_violations (
        violation_type,
        agent_id,
        attempted_action,
        enforcement_action,
        evidence_bundle
    ) VALUES (
        'BYPASS_ATTEMPT',
        p_agent_id,
        'RISL_ESCALATION: ' || p_trigger_type,
        v_action,
        p_evidence || jsonb_build_object(
            'current_defcon', v_current_defcon,
            'recommended_defcon', v_new_defcon,
            'risl_trigger', p_trigger_type,
            'timestamp', NOW()
        )
    );

    -- Return the recommended action
    RETURN v_action || ':' || v_new_defcon;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fhq_governance.risl_escalate_immunity IS
'RISL immunity escalation per ADR-017 §3.4 and ADR-016.
Triggers DEFCON escalation based on threat type.
Implements fail-safe over fail-open principle.';

-- ============================================================================
-- SECTION 8: Update IoS-013 ASPE to Include Quad-Hash Validation
-- ============================================================================

-- Add Quad-Hash column to output_bindings if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_governance'
        AND table_name = 'output_bindings'
        AND column_name = 'quad_hash'
    ) THEN
        ALTER TABLE fhq_governance.output_bindings
        ADD COLUMN quad_hash TEXT;
    END IF;
END $$;

-- ============================================================================
-- SECTION 9: Create VEGA Governance Validation Rule
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.vega_validation_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name TEXT NOT NULL UNIQUE,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('PRECONDITION', 'POSTCONDITION', 'INVARIANT')),
    applies_to TEXT[] NOT NULL,
    condition_sql TEXT NOT NULL,
    failure_action TEXT NOT NULL,
    constitutional_basis TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.vega_validation_rules IS
'VEGA governance validation rules per ADR-017. Enforces MIT Quad compliance as mandatory preconditions.';

-- Insert MIT Quad validation rules
INSERT INTO fhq_governance.vega_validation_rules (
    rule_name, rule_type, applies_to, condition_sql, failure_action, constitutional_basis
) VALUES
(
    'QUAD_HASH_REQUIRED_FOR_TRADE',
    'PRECONDITION',
    ARRAY['TRADE', 'EXECUTION_PLAN', 'ALLOCATION'],
    'SELECT EXISTS (SELECT 1 FROM fhq_governance.quad_hash_registry WHERE quad_hash = $1 AND is_valid = TRUE)',
    'REJECT',
    'ADR-017 §4'
),
(
    'LIDS_THRESHOLD_FOR_ALLOCATION',
    'PRECONDITION',
    ARRAY['ALLOCATION', 'STRATEGY_PROPOSAL'],
    'SELECT lids_score > 0.85 FROM fhq_governance.quad_hash_registry WHERE quad_hash = $1',
    'REJECT',
    'ADR-017 §3.1'
),
(
    'RISL_NOT_HALTED',
    'PRECONDITION',
    ARRAY['TRADE', 'EXECUTION_PLAN', 'ALLOCATION', 'STRATEGY_PROPOSAL'],
    'SELECT risl_status != ''HALTED'' FROM fhq_governance.quad_hash_registry WHERE quad_hash = $1',
    'REJECT',
    'ADR-017 §3.4'
),
(
    'STATE_HASH_VALID',
    'PRECONDITION',
    ARRAY['REASONING', 'TRADE', 'EXECUTION_PLAN', 'ALLOCATION', 'STRATEGY_PROPOSAL'],
    'SELECT EXISTS (SELECT 1 FROM fhq_governance.shared_state_snapshots WHERE state_vector_hash = $1 AND is_valid = TRUE)',
    'REJECT',
    'ADR-018 §4'
)
ON CONFLICT (rule_name) DO UPDATE SET
    condition_sql = EXCLUDED.condition_sql,
    failure_action = EXCLUDED.failure_action,
    updated_at = NOW();

-- ============================================================================
-- SECTION 10: Create Hash Chain for ADR-017
-- ============================================================================

INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    last_verification_at,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-ADR-017-MIT-QUAD-2026',
    'ADR_CONSTITUTIONAL',
    'ADR-017',
    encode(sha256(('ADR-017:MIT-QUAD:GENESIS:CONSTITUTIONAL:' || NOW()::TEXT)::bytea), 'hex'),
    encode(sha256(('ADR-017:MIT-QUAD:GENESIS:CONSTITUTIONAL:' || NOW()::TEXT)::bytea), 'hex'),
    1,
    TRUE,
    NOW(),
    'CEO',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO NOTHING;

-- ============================================================================
-- SECTION 11: Log Governance Action
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
    'ADR_CONSTITUTIONAL_REGISTRATION',
    'ADR-017',
    'ADR',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO Execution Order: ADR-017 MIT Quad Protocol registered as Constitutional Law. LIDS-ACL-DSL-RISL governance structure activated. Quad-Hash infrastructure deployed. All agents must comply with MIT Quad validation rules.',
    FALSE,
    'HC-ADR-017-MIT-QUAD-2026',
    gen_random_uuid()
);

-- ============================================================================
-- SECTION 12: Create VEGA Attestation for ADR-017
-- ============================================================================

INSERT INTO fhq_governance.vega_attestations (
    attestation_id,
    target_type,
    target_id,
    target_version,
    attestation_type,
    attestation_status,
    attestation_timestamp,
    vega_signature,
    vega_public_key,
    adr_reference,
    constitutional_basis,
    attestation_data
) VALUES (
    gen_random_uuid(),
    'ADR',
    'ADR-017',
    '2026.PROD.1',
    'CERTIFICATION',
    'PENDING',  -- Requires VEGA formal attestation
    NOW(),
    'VEGA-ATT-ADR017-' || md5(random()::text),
    'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    'ADR-017',
    'EC-001',
    jsonb_build_object(
        'attestation_id', 'ATT-VEGA-ADR017-' || to_char(NOW(), 'YYYYMMDD'),
        'governance_tier', 'Tier-1',
        'verification_status', 'PENDING - Awaiting VEGA formal attestation',
        'mit_quad_pillars', ARRAY['LIDS', 'ACL', 'DSL', 'RISL'],
        'constitutional_mandate', 'MIT Quad compliance mandatory for all strategy activation',
        'quad_hash_required', TRUE,
        'risl_immunity_active', TRUE
    )
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 13: Audit Log Entry
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
    'CP-ADR017-REG-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    'ADR-017',
    'CEO',
    'APPROVED',
    'ADR-017 MIT Quad Protocol registered as Constitutional Law per CEO Execution Order. Quad-Hash infrastructure deployed. IoS modules mapped to pillars. VEGA validation rules created.',
    'evidence/ADR017_REGISTRATION_' || TO_CHAR(NOW(), 'YYYYMMDD') || '.json',
    encode(sha256(('ADR-017:MIT-QUAD:REGISTRATION:' || NOW()::TEXT)::bytea), 'hex'),
    'HC-ADR-017-MIT-QUAD-2026',
    jsonb_build_object(
        'adr_id', 'ADR-017',
        'version', '2026.PROD.1',
        'type', 'CONSTITUTIONAL',
        'owner', 'CEO',
        'mit_quad_pillars', jsonb_build_object(
            'LIDS', 'Inference & Truth (IoS-003, IoS-005, IoS-007)',
            'ACL', 'Coordination (IoS-008)',
            'DSL', 'Optimization (IoS-004, IoS-012)',
            'RISL', 'Immunity (IoS-010, IoS-013)'
        ),
        'infrastructure_deployed', jsonb_build_array(
            'fhq_governance.mit_quad_pillars',
            'fhq_governance.quad_hash_registry',
            'fhq_governance.ios_quad_mapping',
            'fhq_governance.vega_validation_rules'
        ),
        'functions_created', jsonb_build_array(
            'generate_quad_hash()',
            'validate_quad_compliance()',
            'risl_escalate_immunity()'
        ),
        'freedom_formula', 'Alpha Signal Precision (LIDS + DSL) / Time to Autonomy (ACL + RISL)'
    ),
    NOW()
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 074: ADR-017 MIT QUAD PROTOCOL — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

-- Verify ADR-017 registered
SELECT 'ADR-017 Registration:' AS check_type;
SELECT adr_id, adr_title, adr_status, adr_type, governance_tier
FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-017';

-- Verify MIT Quad pillars
SELECT 'MIT Quad Pillars:' AS check_type;
SELECT pillar_id, pillar_name, core_function
FROM fhq_governance.mit_quad_pillars
ORDER BY pillar_id;

-- Verify IoS mappings
SELECT 'IoS to Quad Mappings:' AS check_type;
SELECT ios_id, pillar_id, is_primary
FROM fhq_governance.ios_quad_mapping
WHERE is_primary = TRUE
ORDER BY pillar_id, ios_id;

-- Verify VEGA validation rules
SELECT 'VEGA Validation Rules:' AS check_type;
SELECT rule_name, rule_type, constitutional_basis
FROM fhq_governance.vega_validation_rules
WHERE is_active = TRUE;

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'ADR-017 MIT QUAD PROTOCOL — REGISTRATION COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo 'MIT Quad Pillars Active:'
\echo '  LIDS (The Brain)   — Inference & Truth    → IoS-003, IoS-005, IoS-007'
\echo '  ACL  (The Manager) — Coordination         → IoS-008'
\echo '  DSL  (The Engine)  — Optimization         → IoS-004, IoS-012'
\echo '  RISL (The Shield)  — Immunity             → IoS-010, IoS-013'
\echo ''
\echo 'Quad-Hash Format: {LIDS_Score}_{ACL_Agent}_{DSL_Model}_{RISL_Status}'
\echo ''
\echo 'Constitutional Requirements:'
\echo '  - MIT Quad compliance mandatory for strategy activation'
\echo '  - Quad-Hash required for every trade/strategy output'
\echo '  - RISL immunity logic integrated with ADR-016 DEFCON'
\echo '  - LIDS threshold: P(Truth) > 0.85 required for allocation'
\echo ''
\echo 'Freedom Formula:'
\echo '  Freedom = Alpha Signal Precision (LIDS + DSL) / Time to Autonomy (ACL + RISL)'
\echo '═══════════════════════════════════════════════════════════════════════════'
