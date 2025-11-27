-- ============================================================================
-- MIGRATION 019 v2: ADR-014 SUB-EXECUTIVE GOVERNANCE CHARTER
-- ============================================================================
-- Fixed version that works with existing schema
-- Authority: ADR-014 – Executive Activation & Sub-Executive Governance Charter
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. UPDATE CHECK CONSTRAINT TO ALLOW NEW AGENTS
-- ============================================================================

-- Drop existing constraint
ALTER TABLE fhq_org.org_agents DROP CONSTRAINT IF EXISTS org_agents_agent_name_check;

-- Add new constraint with sub-executives
ALTER TABLE fhq_org.org_agents ADD CONSTRAINT org_agents_agent_name_check
    CHECK (agent_name = ANY (ARRAY[
        'LARS'::text, 'STIG'::text, 'LINE'::text, 'FINN'::text, 'VEGA'::text,
        'CSEO'::text, 'CDMO'::text, 'CRIO'::text, 'CEIO'::text, 'CFAO'::text
    ]));

-- ============================================================================
-- 2. CREATE AGENT MANDATES TABLE (for contract details)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.agent_mandates (
    mandate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    mandate_version TEXT NOT NULL DEFAULT 'v1.0',
    mandate_type TEXT NOT NULL,
    mandate_status TEXT NOT NULL DEFAULT 'ACTIVE',
    authority_level INTEGER NOT NULL DEFAULT 2,
    authority_type TEXT NOT NULL,
    parent_agent TEXT,
    llm_tier INTEGER NOT NULL DEFAULT 2,
    approval_gate TEXT NOT NULL DEFAULT 'G4-ceo-approved',
    cost_ceiling_usd NUMERIC(10,2) DEFAULT 0.10,
    mandate_document JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CEO',
    UNIQUE(agent_name, mandate_version)
);

CREATE INDEX IF NOT EXISTS idx_agent_mandates_name ON fhq_governance.agent_mandates(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_mandates_status ON fhq_governance.agent_mandates(mandate_status);

-- ============================================================================
-- 3. CREATE AUTHORITY MATRIX TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.authority_matrix (
    matrix_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL UNIQUE,
    authority_level INTEGER NOT NULL DEFAULT 2,
    can_read_canonical BOOLEAN NOT NULL DEFAULT TRUE,
    can_write_canonical BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g0 BOOLEAN NOT NULL DEFAULT TRUE,
    can_trigger_g1 BOOLEAN NOT NULL DEFAULT TRUE,
    can_trigger_g2 BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g3 BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g4 BOOLEAN NOT NULL DEFAULT FALSE,
    can_execute_operational_tasks BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CEO'
);

-- ============================================================================
-- 4. CREATE MODEL PROVIDER POLICY TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.model_provider_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL UNIQUE,
    llm_tier INTEGER NOT NULL,
    allowed_providers TEXT[] NOT NULL,
    forbidden_providers TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    data_sharing_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    tier_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CEO'
);

-- ============================================================================
-- 5. INSERT CSEO – Chief Strategy & Experimentation Officer
-- ============================================================================

INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES (
    'CSEO',
    'Chief Strategy & Experimentation Officer',
    'gpt-4o',
    'openai',
    encode(sha256('CSEO_ED25519_PUBLIC_KEY_ADR014'::bytea), 'hex'),
    'ACTIVE',
    jsonb_build_object(
        'tier', 2,
        'parent_agent', 'LARS',
        'authority_type', 'OPERATIONAL',
        'adr_authority', 'ADR-014',
        'activation_date', NOW()
    )
) ON CONFLICT (agent_name) DO UPDATE SET
    metadata = EXCLUDED.metadata,
    status = EXCLUDED.status;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document, created_by)
VALUES (
    'CSEO',
    'subexecutive_operational_mandate',
    'OPERATIONAL',
    'LARS',
    jsonb_build_object(
        'title', 'CSEO Sub-Executive Mandate',
        'domain', 'Strategy formulation, experimentation, reasoning chains',
        'allowed_actions', ARRAY['Run reasoning models', 'Generate Strategy Drafts', 'Experiment design'],
        'forbidden_actions', ARRAY['Change system parameters', 'Write to canonical stores', 'Produce final strategy']
    ),
    'CEO'
) ON CONFLICT (agent_name, mandate_version) DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4)
VALUES ('CSEO', 2, FALSE, FALSE, FALSE, FALSE)
ON CONFLICT (agent_name) DO NOTHING;

INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers, tier_description)
VALUES ('CSEO', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], 'Tier-2 Sub-Executive: No Tier-1 Claude access')
ON CONFLICT (agent_name) DO NOTHING;

-- ============================================================================
-- 6. INSERT CDMO – Chief Data & Memory Officer
-- ============================================================================

INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES (
    'CDMO',
    'Chief Data & Memory Officer',
    'gpt-4o',
    'openai',
    encode(sha256('CDMO_ED25519_PUBLIC_KEY_ADR014'::bytea), 'hex'),
    'ACTIVE',
    jsonb_build_object(
        'tier', 2,
        'parent_agent', 'STIG',
        'authority_type', 'DATASET',
        'adr_authority', 'ADR-014',
        'activation_date', NOW()
    )
) ON CONFLICT (agent_name) DO UPDATE SET
    metadata = EXCLUDED.metadata,
    status = EXCLUDED.status;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document, created_by)
VALUES (
    'CDMO',
    'subexecutive_dataset_mandate',
    'DATASET',
    'STIG',
    jsonb_build_object(
        'title', 'CDMO Sub-Executive Mandate',
        'domain', 'Data quality, lineage, synthetic augmentation',
        'allowed_actions', ARRAY['Ingest pipeline execution', 'Dataset normalization', 'Anomaly detection'],
        'forbidden_actions', ARRAY['Ingest to canonical registry', 'Schema changes', 'Irreversible transformations']
    ),
    'CEO'
) ON CONFLICT (agent_name, mandate_version) DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4)
VALUES ('CDMO', 2, FALSE, FALSE, FALSE, FALSE)
ON CONFLICT (agent_name) DO NOTHING;

INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers, tier_description)
VALUES ('CDMO', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], 'Tier-2 Sub-Executive: No Tier-1 Claude access')
ON CONFLICT (agent_name) DO NOTHING;

-- ============================================================================
-- 7. INSERT CRIO – Chief Research & Insight Officer
-- ============================================================================

INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES (
    'CRIO',
    'Chief Research & Insight Officer',
    'deepseek-r1',
    'deepseek',
    encode(sha256('CRIO_ED25519_PUBLIC_KEY_ADR014'::bytea), 'hex'),
    'ACTIVE',
    jsonb_build_object(
        'tier', 2,
        'parent_agent', 'FINN',
        'authority_type', 'MODEL',
        'adr_authority', 'ADR-014',
        'activation_date', NOW()
    )
) ON CONFLICT (agent_name) DO UPDATE SET
    metadata = EXCLUDED.metadata,
    status = EXCLUDED.status;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document, created_by)
VALUES (
    'CRIO',
    'subexecutive_model_mandate',
    'MODEL',
    'FINN',
    jsonb_build_object(
        'title', 'CRIO Sub-Executive Mandate',
        'domain', 'Research, causal reasoning, feature generation',
        'allowed_actions', ARRAY['Run reasoning models', 'Generate research packs', 'Graph analysis'],
        'forbidden_actions', ARRAY['Sign models', 'Activate models in pipeline', 'Write to model registries']
    ),
    'CEO'
) ON CONFLICT (agent_name, mandate_version) DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4)
VALUES ('CRIO', 2, FALSE, FALSE, FALSE, FALSE)
ON CONFLICT (agent_name) DO NOTHING;

INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers, tier_description)
VALUES ('CRIO', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], 'Tier-2 Sub-Executive: No Tier-1 Claude access')
ON CONFLICT (agent_name) DO NOTHING;

-- ============================================================================
-- 8. INSERT CEIO – Chief External Intelligence Officer
-- ============================================================================

INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES (
    'CEIO',
    'Chief External Intelligence Officer',
    'gpt-4o',
    'openai',
    encode(sha256('CEIO_ED25519_PUBLIC_KEY_ADR014'::bytea), 'hex'),
    'ACTIVE',
    jsonb_build_object(
        'tier', 2,
        'parent_agents', ARRAY['STIG', 'LINE'],
        'authority_type', 'OPERATIONAL',
        'adr_authority', 'ADR-014',
        'activation_date', NOW()
    )
) ON CONFLICT (agent_name) DO UPDATE SET
    metadata = EXCLUDED.metadata,
    status = EXCLUDED.status;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document, created_by)
VALUES (
    'CEIO',
    'subexecutive_operational_mandate',
    'OPERATIONAL',
    'STIG',
    jsonb_build_object(
        'title', 'CEIO Sub-Executive Mandate',
        'domain', 'External intelligence, signal transformation',
        'allowed_actions', ARRAY['Ingest signals', 'Enrich data', 'Run sentiment models', 'Generate Signal Packages'],
        'forbidden_actions', ARRAY['Write to canonical truth', 'Re-wrap signals as strategy', 'Bypass Orchestrator']
    ),
    'CEO'
) ON CONFLICT (agent_name, mandate_version) DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4)
VALUES ('CEIO', 2, FALSE, FALSE, FALSE, FALSE)
ON CONFLICT (agent_name) DO NOTHING;

INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers, tier_description)
VALUES ('CEIO', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], 'Tier-2 Sub-Executive: No Tier-1 Claude access')
ON CONFLICT (agent_name) DO NOTHING;

-- ============================================================================
-- 9. INSERT CFAO – Chief Foresight & Autonomy Officer
-- ============================================================================

INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES (
    'CFAO',
    'Chief Foresight & Autonomy Officer',
    'gpt-4o',
    'openai',
    encode(sha256('CFAO_ED25519_PUBLIC_KEY_ADR014'::bytea), 'hex'),
    'ACTIVE',
    jsonb_build_object(
        'tier', 2,
        'parent_agent', 'LARS',
        'authority_type', 'OPERATIONAL',
        'adr_authority', 'ADR-014',
        'activation_date', NOW()
    )
) ON CONFLICT (agent_name) DO UPDATE SET
    metadata = EXCLUDED.metadata,
    status = EXCLUDED.status;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document, created_by)
VALUES (
    'CFAO',
    'subexecutive_operational_mandate',
    'OPERATIONAL',
    'LARS',
    jsonb_build_object(
        'title', 'CFAO Sub-Executive Mandate',
        'domain', 'Future scenarios, risk, allocation, autonomy simulation',
        'allowed_actions', ARRAY['Scenario simulation', 'Risk analysis', 'Foresight pipelines', 'Stress testing'],
        'forbidden_actions', ARRAY['Change strategies', 'Modify canonical outputs', 'Change model parameters']
    ),
    'CEO'
) ON CONFLICT (agent_name, mandate_version) DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4)
VALUES ('CFAO', 2, FALSE, FALSE, FALSE, FALSE)
ON CONFLICT (agent_name) DO NOTHING;

INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers, tier_description)
VALUES ('CFAO', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], 'Tier-2 Sub-Executive: No Tier-1 Claude access')
ON CONFLICT (agent_name) DO NOTHING;

-- ============================================================================
-- 10. LOG GOVERNANCE ACTIVATION
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    agent_id,
    decision,
    metadata,
    hash_chain_id,
    signature,
    timestamp
) VALUES (
    'ADR014_SUBEXECUTIVE_ACTIVATION',
    (SELECT agent_id FROM fhq_org.org_agents WHERE agent_name = 'LARS' LIMIT 1),
    'APPROVED',
    jsonb_build_object(
        'adr', 'ADR-014',
        'title', 'Executive Activation & Sub-Executive Governance Charter',
        'activated_roles', ARRAY['CSEO', 'CDMO', 'CRIO', 'CEIO', 'CFAO'],
        'authority_level', 2,
        'ecf_version', '1.0',
        'g4_ceo_approved', true,
        'activation_timestamp', NOW()
    ),
    'HC-ADR014-ACTIVATION-' || to_char(NOW(), 'YYYYMMDD_HH24MISS'),
    'CEO_SIGNATURE_ADR014_G4_ACTIVATION',
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT '=== SUB-EXECUTIVES REGISTERED ===' as status;

SELECT agent_name, agent_role, llm_provider, status,
       metadata->>'tier' as tier,
       metadata->>'parent_agent' as parent
FROM fhq_org.org_agents
WHERE agent_name IN ('CSEO', 'CDMO', 'CRIO', 'CEIO', 'CFAO')
ORDER BY agent_name;

SELECT '=== AUTHORITY MATRIX ===' as status;

SELECT agent_name, authority_level, can_write_canonical, can_trigger_g2, can_trigger_g3, can_trigger_g4
FROM fhq_governance.authority_matrix
WHERE agent_name IN ('CSEO', 'CDMO', 'CRIO', 'CEIO', 'CFAO')
ORDER BY agent_name;

SELECT '=== MODEL PROVIDER POLICIES ===' as status;

SELECT agent_name, llm_tier, allowed_providers, forbidden_providers
FROM fhq_governance.model_provider_policy
WHERE agent_name IN ('CSEO', 'CDMO', 'CRIO', 'CEIO', 'CFAO')
ORDER BY agent_name;

\echo ''
\echo '✅ ADR-014 SUB-EXECUTIVE ACTIVATION COMPLETE'
\echo '✅ 5 Tier-2 roles registered: CSEO, CDMO, CRIO, CEIO, CFAO'
\echo '✅ Authority matrix configured with TIER-2 defaults'
\echo '✅ Model provider policies set (no Anthropic access)'
\echo ''
