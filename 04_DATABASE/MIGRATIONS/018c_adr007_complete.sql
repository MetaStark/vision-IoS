-- =====================================================
-- MIGRATION 018c: COMPLETE ADR-007 VERIFICATION INFRASTRUCTURE
-- =====================================================
-- Standalone migration - no dependencies
-- =====================================================

-- Create schemas
CREATE SCHEMA IF NOT EXISTS fhq_org;
CREATE SCHEMA IF NOT EXISTS fhq_governance;
CREATE SCHEMA IF NOT EXISTS fhq_meta;
CREATE SCHEMA IF NOT EXISTS fhq_monitoring;

-- =====================================================
-- 1. HASH REGISTRY (no dependencies)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_monitoring.hash_registry (
    hash_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    hash_algorithm TEXT NOT NULL DEFAULT 'SHA-256',
    hash_value TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    computed_by TEXT NOT NULL,
    hash_scope TEXT NOT NULL DEFAULT 'FULL_TABLE',
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    last_verified_at TIMESTAMPTZ,
    verification_notes TEXT,
    adr_reference TEXT NOT NULL DEFAULT 'ADR-007',
    CONSTRAINT hash_registry_unique_table_time UNIQUE (schema_name, table_name, computed_at)
);

-- =====================================================
-- 2. ORG_AGENTS (no dependencies)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_org.org_agents (
    agent_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    authority_level INTEGER NOT NULL CHECK (authority_level BETWEEN 1 AND 10),
    public_key TEXT NOT NULL,
    signing_algorithm TEXT NOT NULL DEFAULT 'Ed25519',
    key_registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    key_expires_at TIMESTAMPTZ,
    llm_tier INTEGER NOT NULL CHECK (llm_tier BETWEEN 1 AND 4),
    llm_provider TEXT,
    data_sharing_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_suspended BOOLEAN NOT NULL DEFAULT FALSE,
    suspension_reason TEXT,
    suspended_at TIMESTAMPTZ,
    constitutional_authority TEXT NOT NULL,
    responsibilities TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert agents
INSERT INTO fhq_org.org_agents (
    agent_id, agent_name, agent_role, authority_level,
    public_key, signing_algorithm, llm_tier, llm_provider, data_sharing_allowed,
    constitutional_authority, responsibilities
) VALUES
    ('LARS', 'LARS', 'Strategy', 9, 'GENESIS_KEY_LARS_PENDING_PRODUCTION', 'Ed25519', 1, 'Anthropic Claude', FALSE, 'ADR-001 → ADR-007', ARRAY['Reasoning', 'Structural logic', 'Cross-domain integrity']),
    ('STIG', 'STIG', 'Implementation', 8, 'GENESIS_KEY_STIG_PENDING_PRODUCTION', 'Ed25519', 3, 'DeepSeek + OpenAI', TRUE, 'ADR-001 → ADR-007', ARRAY['SQL', 'Pipelines', 'API integrations', 'Lineage enforcement']),
    ('LINE', 'LINE', 'SRE', 8, 'GENESIS_KEY_LINE_PENDING_PRODUCTION', 'Ed25519', 3, 'DeepSeek + OpenAI', TRUE, 'ADR-001 → ADR-007', ARRAY['Uptime', 'Monitoring', 'Container ops', 'Alerting']),
    ('FINN', 'FINN', 'Research', 8, 'GENESIS_KEY_FINN_PENDING_PRODUCTION', 'Ed25519', 2, 'OpenAI (no sharing)', FALSE, 'ADR-001 → ADR-007', ARRAY['Market analysis', 'Strategy evaluation', 'Research loops 24/7']),
    ('VEGA', 'VEGA', 'Auditor', 10, 'GENESIS_KEY_VEGA_PENDING_PRODUCTION', 'Ed25519', 1, 'Anthropic Claude', FALSE, 'ADR-006 → EC-001', ARRAY['Compliance enforcement', 'Veto', 'Attestation', 'Anti-hallucination'])
ON CONFLICT (agent_id) DO UPDATE SET
    llm_tier = EXCLUDED.llm_tier,
    llm_provider = EXCLUDED.llm_provider,
    updated_at = NOW();

-- =====================================================
-- 3. ORG_ACTIVITY_LOG (depends on org_agents)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_org.org_activity_log (
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    activity_type TEXT NOT NULL,
    activity_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    input_data JSONB,
    output_data JSONB,
    execution_duration_ms INTEGER,
    signature TEXT NOT NULL,
    signature_verified BOOLEAN DEFAULT FALSE,
    signature_verified_at TIMESTAMPTZ,
    signature_verified_by TEXT,
    hash_chain_id TEXT NOT NULL,
    previous_activity_id UUID REFERENCES fhq_org.org_activity_log(activity_id),
    reconciliation_score NUMERIC(5, 4),
    discrepancy_detected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- 4. ORG_TASKS (depends on org_agents)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_org.org_tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    task_description TEXT,
    assigned_agent_id TEXT REFERENCES fhq_org.org_agents(agent_id),
    task_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_executed_at TIMESTAMPTZ,
    execution_count INTEGER NOT NULL DEFAULT 0,
    last_execution_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- 5. FUNCTION_REGISTRY (depends on org_agents)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_org.function_registry (
    function_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    function_name TEXT NOT NULL UNIQUE,
    function_type TEXT NOT NULL,
    function_path TEXT,
    owner_agent_id TEXT REFERENCES fhq_org.org_agents(agent_id),
    function_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    max_execution_time_ms INTEGER DEFAULT 300000,
    cost_ceiling_usd NUMERIC(10, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- 6. MODEL_PROVIDER_POLICY (depends on org_agents)
-- =====================================================
DROP TABLE IF EXISTS fhq_governance.model_provider_policy CASCADE;
CREATE TABLE fhq_governance.model_provider_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    allowed_tier INTEGER NOT NULL CHECK (allowed_tier BETWEEN 1 AND 4),
    allowed_providers TEXT[] NOT NULL,
    data_sharing_policy TEXT NOT NULL CHECK (data_sharing_policy IN ('PROHIBITED', 'ALLOWED', 'CONDITIONAL')),
    enforce_strict BOOLEAN NOT NULL DEFAULT TRUE,
    violation_action TEXT NOT NULL DEFAULT 'BLOCK',
    policy_rationale TEXT,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    adr_reference TEXT NOT NULL DEFAULT 'ADR-007',
    created_by TEXT NOT NULL DEFAULT 'LARS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT model_provider_policy_unique_agent UNIQUE (agent_id, effective_from)
);

INSERT INTO fhq_governance.model_provider_policy (agent_id, allowed_tier, allowed_providers, data_sharing_policy, policy_rationale)
VALUES
    ('LARS', 1, ARRAY['Anthropic Claude'], 'PROHIBITED', 'Tier 1 - High sensitivity'),
    ('VEGA', 1, ARRAY['Anthropic Claude'], 'PROHIBITED', 'Tier 1 - High sensitivity'),
    ('FINN', 2, ARRAY['OpenAI'], 'PROHIBITED', 'Tier 2 - Medium sensitivity'),
    ('STIG', 3, ARRAY['DeepSeek', 'OpenAI'], 'ALLOWED', 'Tier 3 - Low sensitivity'),
    ('LINE', 3, ARRAY['DeepSeek', 'OpenAI'], 'ALLOWED', 'Tier 3 - Low sensitivity');

-- =====================================================
-- 7. LLM_ROUTING_LOG (depends on org_agents, model_provider_policy)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_governance.llm_routing_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    request_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    requested_provider TEXT NOT NULL,
    requested_tier INTEGER NOT NULL,
    routed_provider TEXT NOT NULL,
    routed_tier INTEGER NOT NULL,
    policy_id UUID REFERENCES fhq_governance.model_provider_policy(policy_id),
    policy_satisfied BOOLEAN NOT NULL,
    violation_detected BOOLEAN NOT NULL DEFAULT FALSE,
    violation_action_taken TEXT,
    request_context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- 8. RECONCILIATION_SNAPSHOTS (no dependencies)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_meta.reconciliation_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_name TEXT NOT NULL,
    snapshot_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_type TEXT NOT NULL DEFAULT 'SCHEDULED',
    agent_state JSONB NOT NULL,
    canonical_state JSONB NOT NULL,
    discrepancy_score NUMERIC(7, 6) NOT NULL DEFAULT 0.0,
    discrepancy_threshold NUMERIC(7, 6) NOT NULL DEFAULT 0.10,
    threshold_exceeded BOOLEAN NOT NULL DEFAULT FALSE,
    field_discrepancies JSONB,
    discrepancy_count INTEGER NOT NULL DEFAULT 0,
    reconciliation_status TEXT NOT NULL DEFAULT 'PENDING',
    reconciliation_action TEXT,
    vega_suspension_requested BOOLEAN NOT NULL DEFAULT FALSE,
    vega_suspension_request_id UUID,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- 9. RECONCILIATION_EVIDENCE (depends on reconciliation_snapshots)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_meta.reconciliation_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES fhq_meta.reconciliation_snapshots(snapshot_id),
    evidence_type TEXT NOT NULL,
    evidence_category TEXT NOT NULL,
    evidence_data JSONB NOT NULL,
    evidence_hash TEXT NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================
-- 10. GOVERNANCE_STATE (no dependencies)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_governance.governance_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_type TEXT NOT NULL,
    component_name TEXT NOT NULL,
    component_version TEXT NOT NULL,
    registration_status TEXT NOT NULL DEFAULT 'REGISTERED',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_by TEXT NOT NULL,
    authority_chain TEXT[] NOT NULL,
    adr_compliance TEXT[] NOT NULL,
    vega_attested BOOLEAN NOT NULL DEFAULT FALSE,
    vega_attestation_id UUID,
    vega_attestation_timestamp TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deployment_environment TEXT NOT NULL DEFAULT 'PRODUCTION',
    configuration JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT governance_state_unique_component UNIQUE (component_type, component_name, component_version)
);

INSERT INTO fhq_governance.governance_state (
    component_type, component_name, component_version, registered_by,
    authority_chain, adr_compliance, configuration
) VALUES (
    'ORCHESTRATOR', 'FHQ_INTELLIGENCE_ORCHESTRATOR', '1.1.1', 'LARS',
    ARRAY['ADR-001', 'ADR-002', 'ADR-006', 'ADR-007', 'EC-001'],
    ARRAY['ADR-001', 'ADR-002', 'ADR-006', 'ADR-007', 'ADR-008', 'ADR-010', 'ADR-013'],
    '{"version": "1.1.1", "validation_status": "5/5 PASS"}'::jsonb
) ON CONFLICT DO NOTHING;

-- =====================================================
-- 11. VEGA_ATTESTATIONS (no dependencies)
-- =====================================================
CREATE TABLE IF NOT EXISTS fhq_governance.vega_attestations (
    attestation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_version TEXT,
    attestation_type TEXT NOT NULL,
    attestation_status TEXT NOT NULL DEFAULT 'PENDING',
    attestation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    vega_signature TEXT NOT NULL,
    vega_public_key TEXT NOT NULL,
    signature_verified BOOLEAN NOT NULL DEFAULT FALSE,
    attestation_data JSONB NOT NULL,
    evidence_bundle_id UUID,
    adr_reference TEXT NOT NULL DEFAULT 'ADR-006',
    constitutional_basis TEXT NOT NULL DEFAULT 'EC-001',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO fhq_governance.vega_attestations (
    target_type, target_id, target_version, attestation_type, attestation_status,
    vega_signature, vega_public_key, attestation_data
) VALUES (
    'ORCHESTRATOR', 'FHQ_INTELLIGENCE_ORCHESTRATOR', '1.1.1', 'DEPLOYMENT', 'APPROVED',
    'GENESIS_ATTESTATION_VEGA', 'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    '{"deployment_verified": true, "validation_result": "5/5 PASS"}'::jsonb
) ON CONFLICT DO NOTHING;

-- =====================================================
-- VERIFICATION
-- =====================================================
SELECT 'MIGRATION 018c COMPLETE' AS status,
       (SELECT COUNT(*) FROM fhq_org.org_agents) AS agents,
       (SELECT COUNT(*) FROM fhq_governance.model_provider_policy) AS policies;
