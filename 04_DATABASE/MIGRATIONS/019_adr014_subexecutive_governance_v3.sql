-- ============================================================================
-- MIGRATION 019 v3: ADR-014 SUB-EXECUTIVE GOVERNANCE CHARTER
-- ============================================================================
-- Fixed version - removed dependency on governance_actions_log
-- ============================================================================

BEGIN;

-- 1. UPDATE CHECK CONSTRAINT
ALTER TABLE fhq_org.org_agents DROP CONSTRAINT IF EXISTS org_agents_agent_name_check;
ALTER TABLE fhq_org.org_agents ADD CONSTRAINT org_agents_agent_name_check
    CHECK (agent_name = ANY (ARRAY[
        'LARS'::text, 'STIG'::text, 'LINE'::text, 'FINN'::text, 'VEGA'::text,
        'CSEO'::text, 'CDMO'::text, 'CRIO'::text, 'CEIO'::text, 'CFAO'::text
    ]));

-- 2. CREATE TABLES
CREATE TABLE IF NOT EXISTS fhq_governance.agent_mandates (
    mandate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    mandate_version TEXT NOT NULL DEFAULT 'v1.0',
    mandate_type TEXT NOT NULL,
    authority_type TEXT NOT NULL,
    parent_agent TEXT,
    mandate_document JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(agent_name, mandate_version)
);

CREATE TABLE IF NOT EXISTS fhq_governance.authority_matrix (
    matrix_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL UNIQUE,
    authority_level INTEGER NOT NULL DEFAULT 2,
    can_write_canonical BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g2 BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g3 BOOLEAN NOT NULL DEFAULT FALSE,
    can_trigger_g4 BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fhq_governance.model_provider_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL UNIQUE,
    llm_tier INTEGER NOT NULL,
    allowed_providers TEXT[] NOT NULL,
    forbidden_providers TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. INSERT CSEO
INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES ('CSEO', 'Chief Strategy & Experimentation Officer', 'gpt-4o', 'openai',
        encode(sha256('CSEO_KEY'::bytea), 'hex'), 'ACTIVE',
        '{"tier": 2, "parent_agent": "LARS", "authority_type": "OPERATIONAL"}'::jsonb)
ON CONFLICT (agent_name) DO UPDATE SET metadata = EXCLUDED.metadata;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document)
VALUES ('CSEO', 'subexecutive', 'OPERATIONAL', 'LARS', '{"domain": "Strategy & Experimentation"}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name) VALUES ('CSEO') ON CONFLICT DO NOTHING;
INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers)
VALUES ('CSEO', 2, ARRAY['openai','deepseek','gemini'], ARRAY['anthropic']) ON CONFLICT DO NOTHING;

-- 4. INSERT CDMO
INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES ('CDMO', 'Chief Data & Memory Officer', 'gpt-4o', 'openai',
        encode(sha256('CDMO_KEY'::bytea), 'hex'), 'ACTIVE',
        '{"tier": 2, "parent_agent": "STIG", "authority_type": "DATASET"}'::jsonb)
ON CONFLICT (agent_name) DO UPDATE SET metadata = EXCLUDED.metadata;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document)
VALUES ('CDMO', 'subexecutive', 'DATASET', 'STIG', '{"domain": "Data & Memory"}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name) VALUES ('CDMO') ON CONFLICT DO NOTHING;
INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers)
VALUES ('CDMO', 2, ARRAY['openai','deepseek','gemini'], ARRAY['anthropic']) ON CONFLICT DO NOTHING;

-- 5. INSERT CRIO
INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES ('CRIO', 'Chief Research & Insight Officer', 'deepseek-r1', 'deepseek',
        encode(sha256('CRIO_KEY'::bytea), 'hex'), 'ACTIVE',
        '{"tier": 2, "parent_agent": "FINN", "authority_type": "MODEL"}'::jsonb)
ON CONFLICT (agent_name) DO UPDATE SET metadata = EXCLUDED.metadata;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document)
VALUES ('CRIO', 'subexecutive', 'MODEL', 'FINN', '{"domain": "Research & Insight"}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name) VALUES ('CRIO') ON CONFLICT DO NOTHING;
INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers)
VALUES ('CRIO', 2, ARRAY['openai','deepseek','gemini'], ARRAY['anthropic']) ON CONFLICT DO NOTHING;

-- 6. INSERT CEIO
INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES ('CEIO', 'Chief External Intelligence Officer', 'gpt-4o', 'openai',
        encode(sha256('CEIO_KEY'::bytea), 'hex'), 'ACTIVE',
        '{"tier": 2, "parent_agents": ["STIG","LINE"], "authority_type": "OPERATIONAL"}'::jsonb)
ON CONFLICT (agent_name) DO UPDATE SET metadata = EXCLUDED.metadata;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document)
VALUES ('CEIO', 'subexecutive', 'OPERATIONAL', 'STIG', '{"domain": "External Intelligence"}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name) VALUES ('CEIO') ON CONFLICT DO NOTHING;
INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers)
VALUES ('CEIO', 2, ARRAY['openai','deepseek','gemini'], ARRAY['anthropic']) ON CONFLICT DO NOTHING;

-- 7. INSERT CFAO
INSERT INTO fhq_org.org_agents (agent_name, agent_role, llm_version, llm_provider, public_key, status, metadata)
VALUES ('CFAO', 'Chief Foresight & Autonomy Officer', 'gpt-4o', 'openai',
        encode(sha256('CFAO_KEY'::bytea), 'hex'), 'ACTIVE',
        '{"tier": 2, "parent_agent": "LARS", "authority_type": "OPERATIONAL"}'::jsonb)
ON CONFLICT (agent_name) DO UPDATE SET metadata = EXCLUDED.metadata;

INSERT INTO fhq_governance.agent_mandates (agent_name, mandate_type, authority_type, parent_agent, mandate_document)
VALUES ('CFAO', 'subexecutive', 'OPERATIONAL', 'LARS', '{"domain": "Foresight & Autonomy"}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO fhq_governance.authority_matrix (agent_name) VALUES ('CFAO') ON CONFLICT DO NOTHING;
INSERT INTO fhq_governance.model_provider_policy (agent_name, llm_tier, allowed_providers, forbidden_providers)
VALUES ('CFAO', 2, ARRAY['openai','deepseek','gemini'], ARRAY['anthropic']) ON CONFLICT DO NOTHING;

COMMIT;

-- VERIFICATION
SELECT 'SUB-EXECUTIVES:' as info;
SELECT agent_name, agent_role, status, metadata->>'parent_agent' as parent
FROM fhq_org.org_agents WHERE agent_name IN ('CSEO','CDMO','CRIO','CEIO','CFAO');

SELECT 'AUTHORITY MATRIX:' as info;
SELECT * FROM fhq_governance.authority_matrix;

SELECT 'MODEL POLICIES:' as info;
SELECT * FROM fhq_governance.model_provider_policy;

\echo ''
\echo '✅ ADR-014 COMPLETE: 5 Sub-Executives activated'
