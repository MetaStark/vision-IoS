-- ============================================================================
-- MIGRATION 020: PHASE D - IDENTITY SOVEREIGNTY
-- ============================================================================
-- Authority: EXEC-DIR-004-KEYS (Boardroom Directive)
-- Reference: ADR-008 (Cryptographic Key Management)
-- Auditor: VEGA (Constitutional Guardrail)
-- Executor: CODE (Clearance Level 3)
--
-- Purpose: Establish cryptographic identity infrastructure for all 11 agents
--   Tier-1 Executive: VEGA, LARS
--   Tier-2 Executive: STIG, FINN, LINE
--   Tier-2 Sub-Executive: CSEO, CDMO, CRIO, CEIO, CFAO
--   Tier-3 Engineering: CODE
--
-- Zero Trust Rule: No agent operates without a verified Ed25519 identity keypair
--                  anchored in fhq_meta.agent_keys and attested by VEGA.
--
-- Compliance Chain:
--   ADR-001 -> ADR-006 -> ADR-007 -> ADR-008 -> ADR-014 -> EXEC-DIR-004
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: SCHEMA VERIFICATION & ENHANCEMENT
-- ============================================================================

-- Ensure fhq_meta.agent_keys has required columns
ALTER TABLE fhq_meta.agent_keys
    ADD COLUMN IF NOT EXISTS key_type TEXT DEFAULT 'ED25519',
    ADD COLUMN IF NOT EXISTS status TEXT GENERATED ALWAYS AS (key_state) STORED,
    ADD COLUMN IF NOT EXISTS vega_attested BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS vega_attestation_id UUID,
    ADD COLUMN IF NOT EXISTS vega_attestation_timestamp TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS key_fingerprint TEXT,
    ADD COLUMN IF NOT EXISTS ceremony_id TEXT;

-- Create index for key ceremony tracking
CREATE INDEX IF NOT EXISTS idx_agent_keys_ceremony ON fhq_meta.agent_keys(ceremony_id);
CREATE INDEX IF NOT EXISTS idx_agent_keys_attested ON fhq_meta.agent_keys(vega_attested);

-- ============================================================================
-- SECTION 1B: ENSURE GOVERNANCE TABLES EXIST
-- ============================================================================

-- Create authority_matrix table if not exists (from ADR-014)
CREATE TABLE IF NOT EXISTS fhq_governance.authority_matrix (
    matrix_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL UNIQUE,
    authority_level INTEGER NOT NULL DEFAULT 2,
    can_read_canonical BOOLEAN NOT NULL DEFAULT TRUE,
    can_write_canonical BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g0 BOOLEAN NOT NULL DEFAULT TRUE,
    can_trigger_g1 BOOLEAN NOT NULL DEFAULT TRUE,
    can_trigger_g2 BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g3 BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g4 BOOLEAN NOT NULL DEFAULT FALSE,
    can_execute_operational_tasks BOOLEAN NOT NULL DEFAULT TRUE,
    can_submit_g0 BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CEO'
);

-- Create model_provider_policy table if not exists (from ADR-007/ADR-014)
CREATE TABLE IF NOT EXISTS fhq_governance.model_provider_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL UNIQUE,
    llm_tier INTEGER NOT NULL,
    allowed_providers TEXT[] NOT NULL,
    forbidden_providers TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    data_sharing_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    tier_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CEO'
);

-- Create change_log table if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.change_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_type TEXT NOT NULL,
    change_scope TEXT NOT NULL,
    change_description TEXT NOT NULL,
    authority TEXT NOT NULL,
    approval_gate TEXT,
    hash_chain_id TEXT,
    agent_signatures JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL
);

-- ============================================================================
-- SECTION 2: CODE AGENT REGISTRATION
-- ============================================================================
-- CODE is the Engineering Execution Unit (Tier-3)
-- CODE executes engineering tasks under governance oversight

-- Register CODE in org_agents
INSERT INTO fhq_org.org_agents (
    agent_id, agent_name, agent_role, authority_level,
    public_key, signing_algorithm, llm_tier, llm_provider, data_sharing_allowed,
    constitutional_authority, responsibilities, is_active
) VALUES (
    'CODE', 'CODE', 'Engineering', 3,
    'GENESIS_KEY_CODE_PENDING_PRODUCTION', 'Ed25519', 3, 'Anthropic Claude', FALSE,
    'ADR-001 -> ADR-008 -> EXEC-DIR-004',
    ARRAY['Code execution', 'Key ceremonies', 'Security tooling', 'Infrastructure automation'],
    TRUE
) ON CONFLICT (agent_id) DO UPDATE SET
    agent_role = EXCLUDED.agent_role,
    authority_level = EXCLUDED.authority_level,
    llm_tier = EXCLUDED.llm_tier,
    responsibilities = EXCLUDED.responsibilities,
    updated_at = NOW();

-- Register CODE authority matrix
INSERT INTO fhq_governance.authority_matrix (
    agent_id, authority_level, can_read_canonical, can_write_canonical,
    can_trigger_g0, can_trigger_g1, can_trigger_g2, can_trigger_g3, can_trigger_g4,
    can_execute_operational_tasks, can_submit_g0, created_by
) VALUES (
    'CODE', 3, TRUE, FALSE, TRUE, TRUE, FALSE, FALSE, FALSE, TRUE, TRUE, 'CEO'
) ON CONFLICT (agent_id) DO UPDATE SET
    authority_level = EXCLUDED.authority_level,
    updated_at = NOW();

-- Register CODE model provider policy
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, llm_tier, allowed_providers, forbidden_providers,
    data_sharing_allowed, tier_description, created_by
) VALUES (
    'CODE', 3, ARRAY['anthropic', 'openai', 'deepseek'], ARRAY[]::TEXT[], FALSE,
    'Tier-3 Engineering: Code execution and security infrastructure. Full provider access for tooling.',
    'CEO'
) ON CONFLICT (agent_id) DO UPDATE SET
    llm_tier = EXCLUDED.llm_tier,
    allowed_providers = EXCLUDED.allowed_providers,
    tier_description = EXCLUDED.tier_description,
    updated_at = NOW();

-- ============================================================================
-- SECTION 3: KEY CEREMONY INFRASTRUCTURE
-- ============================================================================

-- Create key ceremony audit table
CREATE TABLE IF NOT EXISTS fhq_meta.key_ceremonies (
    ceremony_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ceremony_type TEXT NOT NULL CHECK (ceremony_type IN ('IGNITION', 'ROTATION', 'RECOVERY', 'REVOCATION')),
    ceremony_name TEXT NOT NULL,
    ceremony_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ceremony scope
    agents_included TEXT[] NOT NULL,
    keys_generated INTEGER NOT NULL DEFAULT 0,
    keys_registered INTEGER NOT NULL DEFAULT 0,

    -- Security context
    executed_by TEXT NOT NULL,
    execution_environment TEXT NOT NULL DEFAULT 'LOCAL_SECURE_TERMINAL',

    -- Verification state
    vega_attested BOOLEAN NOT NULL DEFAULT FALSE,
    vega_attestation_id UUID,
    vega_attestation_timestamp TIMESTAMPTZ,

    -- Ceremony outcome
    ceremony_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (
        ceremony_status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'ATTESTED', 'FAILED', 'REVOKED')
    ),
    ceremony_hash TEXT NOT NULL,
    ceremony_signature TEXT,

    -- Metadata
    ceremony_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_key_ceremonies_status ON fhq_meta.key_ceremonies(ceremony_status);
CREATE INDEX IF NOT EXISTS idx_key_ceremonies_type ON fhq_meta.key_ceremonies(ceremony_type);

COMMENT ON TABLE fhq_meta.key_ceremonies IS 'ADR-008 / EXEC-DIR-004: Key ceremony audit trail for identity sovereignty operations';

-- ============================================================================
-- SECTION 4: VEGA ATTESTATION INFRASTRUCTURE
-- ============================================================================

-- Create identity state attestation table
CREATE TABLE IF NOT EXISTS fhq_meta.identity_state_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- State capture
    agent_count INTEGER NOT NULL,
    active_key_count INTEGER NOT NULL,
    identity_state_hash TEXT NOT NULL,

    -- Detailed agent states
    agent_states JSONB NOT NULL,

    -- Verification
    vega_attested BOOLEAN NOT NULL DEFAULT FALSE,
    vega_signature TEXT,
    vega_public_key TEXT,
    attestation_timestamp TIMESTAMPTZ,

    -- Ceremony reference
    ceremony_id UUID REFERENCES fhq_meta.key_ceremonies(ceremony_id),

    -- Metadata
    reason TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'VEGA',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_identity_snapshots_attested ON fhq_meta.identity_state_snapshots(vega_attested);
CREATE INDEX IF NOT EXISTS idx_identity_snapshots_ceremony ON fhq_meta.identity_state_snapshots(ceremony_id);

COMMENT ON TABLE fhq_meta.identity_state_snapshots IS 'ADR-008: Identity state snapshots with VEGA attestation for canonical verification';

-- ============================================================================
-- SECTION 5: DEPRECATE PLACEHOLDER KEYS
-- ============================================================================

-- Mark all GENESIS placeholder keys as PENDING (awaiting real keys)
UPDATE fhq_meta.agent_keys
SET key_state = 'PENDING',
    ceremony_id = NULL
WHERE public_key_hex LIKE '%GENESIS%'
   OR public_key_hex LIKE '%PENDING%';

-- Also update org_agents placeholder keys
UPDATE fhq_org.org_agents
SET public_key = 'PENDING_CEREMONY_KEY'
WHERE public_key LIKE '%GENESIS%'
   OR public_key LIKE '%PENDING%';

-- ============================================================================
-- SECTION 6: VERIFICATION QUERIES
-- ============================================================================

-- Verify all 11 agents exist in org_agents
DO $$
DECLARE
    agent_count INTEGER;
    expected_agents TEXT[] := ARRAY['LARS', 'STIG', 'FINN', 'LINE', 'VEGA', 'CODE', 'cseo', 'cdmo', 'crio', 'ceio', 'cfao'];
    missing_agents TEXT[];
BEGIN
    SELECT COUNT(*) INTO agent_count
    FROM fhq_org.org_agents
    WHERE UPPER(agent_id) = ANY(
        SELECT UPPER(unnest) FROM unnest(expected_agents)
    );

    IF agent_count < 11 THEN
        SELECT ARRAY_AGG(expected) INTO missing_agents
        FROM unnest(expected_agents) AS expected
        WHERE NOT EXISTS (
            SELECT 1 FROM fhq_org.org_agents
            WHERE UPPER(agent_id) = UPPER(expected)
        );

        RAISE WARNING 'Missing agents: %. Found %/11.', missing_agents, agent_count;
    ELSE
        RAISE NOTICE 'PRE-FLIGHT CHECK PASSED: All 11 agents registered in org_agents';
    END IF;
END $$;

-- Verify CODE is registered
DO $$
DECLARE
    code_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM fhq_org.org_agents WHERE UPPER(agent_id) = 'CODE'
    ) INTO code_exists;

    IF NOT code_exists THEN
        RAISE EXCEPTION 'CODE agent not registered. ABORT.';
    ELSE
        RAISE NOTICE 'CODE agent registered successfully';
    END IF;
END $$;

-- ============================================================================
-- SECTION 7: GOVERNANCE AUDIT LOG
-- ============================================================================

INSERT INTO fhq_governance.change_log (
    change_type,
    change_scope,
    change_description,
    authority,
    approval_gate,
    hash_chain_id,
    agent_signatures,
    created_at,
    created_by
) VALUES (
    'phase_d_identity_sovereignty_infrastructure',
    'cryptographic_identity_system',
    'EXEC-DIR-004-KEYS: Phase D Identity Sovereignty infrastructure deployed. ' ||
    'Registered CODE agent (Tier-3 Engineering). Created key ceremony tracking infrastructure. ' ||
    'Created identity state snapshot table for VEGA attestation. ' ||
    'Deprecated all GENESIS placeholder keys. System ready for Key Ceremony (SOP-008).',
    'EXEC-DIR-004-KEYS -> ADR-008 -> ADR-001',
    'G0-infrastructure',
    'HC-PHASYD-IDENTITY-' || to_char(NOW(), 'YYYYMMDD_HH24MISS'),
    jsonb_build_object(
        'executor', 'CODE',
        'auditor', 'VEGA',
        'directive', 'EXEC-DIR-004-KEYS',
        'timestamp', NOW(),
        'agents_registered', 11,
        'infrastructure_tables', ARRAY['fhq_meta.key_ceremonies', 'fhq_meta.identity_state_snapshots'],
        'next_step', 'Execute Key Ceremony (SOP-008)'
    ),
    NOW(),
    'CODE'
);

COMMIT;

-- ============================================================================
-- FINAL STATUS REPORT
-- ============================================================================

SELECT
    '020_phase_d_identity_sovereignty' AS migration,
    'COMPLETE' AS status,
    'EXEC-DIR-004-KEYS' AS authority,
    NOW() AS completed_at;

\echo ''
\echo '============================================================================='
\echo 'MIGRATION 020: PHASE D - IDENTITY SOVEREIGNTY INFRASTRUCTURE'
\echo '============================================================================='
\echo ''
\echo 'Infrastructure Deployed:'
\echo '  [x] CODE agent registered (Tier-3 Engineering)'
\echo '  [x] fhq_meta.key_ceremonies table created'
\echo '  [x] fhq_meta.identity_state_snapshots table created'
\echo '  [x] GENESIS placeholder keys deprecated'
\echo '  [x] Authority matrix and model provider policy for CODE'
\echo ''
\echo 'Agent Fleet Status (Pre-Ceremony):'
\echo '  Tier-1: VEGA (Authority 10), LARS (Authority 9)'
\echo '  Tier-2 Exec: STIG, FINN, LINE (Authority 8)'
\echo '  Tier-2 Sub-Exec: CSEO, CDMO, CRIO, CEIO, CFAO (Authority 2)'
\echo '  Tier-3: CODE (Authority 3)'
\echo ''
\echo 'NEXT STEP: Execute Key Ceremony (SOP-008)'
\echo '  python tools/security/generate_fleet_keys_hardened.py'
\echo ''
\echo 'After key generation:'
\echo '  1. Execute SQL (public keys -> fhq_meta.agent_keys)'
\echo '  2. Update .env (private keys -> local vault)'
\echo '  3. Run VEGA attestation: python tools/security/vega_core.py attest identity_state'
\echo '============================================================================='
