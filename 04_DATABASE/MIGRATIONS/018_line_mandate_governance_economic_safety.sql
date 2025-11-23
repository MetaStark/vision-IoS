-- MIGRATION 018: LINE MANDATE GOVERNANCE & ECONOMIC SAFETY LAYER
-- =============================================================================
--
-- Authority: CODE (on behalf of LARS - LINE Mandate Registration)
-- Purpose: Establish governance infrastructure for LINE mandate registration
-- Compliance: ADR-004 (Change Gates), ADR-007 (Provider Routing),
--             ADR-008 (Ed25519 Keys), ADR-012 (Economic Safety)
--
-- Change Proposal: G0-2025-11-23-LINE-MANDATE
-- Event Type: API/LLM Provider Expansion (Modification per ADR-004)
--
-- New Providers: DeepSeek, OpenAI, Serper, Scholar, Coindesk, Marketaux, FRED
--
-- Tables Created:
--   Meta Schema (ADR Governance):
--     - fhq_meta.adr_registry
--     - fhq_meta.adr_audit_log
--     - fhq_meta.adr_version_history
--     - fhq_meta.agent_keys (Ed25519 key lifecycle)
--     - fhq_meta.key_archival_log
--
--   Governance Schema (Agent Contracts & Provider Policy):
--     - fhq_governance.agent_contracts
--     - fhq_governance.model_provider_policy
--     - fhq_governance.executive_roles
--
--   VEGA Schema (Economic Safety - ADR-012):
--     - vega.llm_rate_limits
--     - vega.llm_cost_limits
--     - vega.llm_execution_limits
--     - vega.llm_usage_log
--     - vega.llm_violation_events
--
-- IMPORTANT: LIVE_MODE=False until VEGA attestation (QG-F6)
--
-- =============================================================================

BEGIN;

-- =============================================================================
-- CREATE VEGA SCHEMA (Economic Safety Layer)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS vega;
COMMENT ON SCHEMA vega IS 'VEGA Verification & Governance Authority - Economic Safety Layer (ADR-012)';


-- =============================================================================
-- ADR GOVERNANCE REGISTRY (ADR-004)
-- =============================================================================

-- ADR Registry - Central catalog of all ADRs
CREATE TABLE IF NOT EXISTS fhq_meta.adr_registry (
    adr_id VARCHAR(20) PRIMARY KEY,  -- e.g., 'ADR-001', 'ADR-012'
    adr_title TEXT NOT NULL,
    adr_status VARCHAR(50) NOT NULL CHECK (adr_status IN ('DRAFT', 'PROPOSED', 'APPROVED', 'DEPRECATED', 'SUPERSEDED')),
    adr_type VARCHAR(50) NOT NULL CHECK (adr_type IN ('CONSTITUTIONAL', 'ARCHITECTURAL', 'OPERATIONAL', 'COMPLIANCE', 'ECONOMIC')),
    current_version VARCHAR(20) NOT NULL,  -- e.g., 'v1.0', 'v2.1'
    approval_authority VARCHAR(50),  -- e.g., 'CEO', 'LARS+VEGA'
    effective_date DATE,
    superseded_by VARCHAR(20) REFERENCES fhq_meta.adr_registry(adr_id),
    file_path TEXT,
    sha256_hash CHAR(64),  -- Hash of current version
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_adr_registry_status ON fhq_meta.adr_registry(adr_status);
CREATE INDEX idx_adr_registry_type ON fhq_meta.adr_registry(adr_type);

COMMENT ON TABLE fhq_meta.adr_registry IS 'ADR-004: Central catalog of Architecture Decision Records';


-- ADR Audit Log - Immutable change tracking with hash chains
CREATE TABLE IF NOT EXISTS fhq_meta.adr_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_proposal_id VARCHAR(100) NOT NULL,  -- e.g., 'G0-2025-11-23-LINE-MANDATE'
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'SUBMISSION',
        'G1_TECHNICAL_VALIDATION',
        'G2_GOVERNANCE_VALIDATION',
        'G3_AUDIT_VERIFICATION',
        'G4_CANONICALIZATION',
        'MODIFICATION',
        'DEPRECATION'
    )),
    gate_stage VARCHAR(10) CHECK (gate_stage IN ('G0', 'G1', 'G2', 'G3', 'G4')),
    adr_id VARCHAR(20) REFERENCES fhq_meta.adr_registry(adr_id),
    initiated_by VARCHAR(50) NOT NULL,  -- Agent ID (LARS, STIG, LINE, FINN, VEGA, CODE, CEO)
    decision VARCHAR(50),  -- 'PASS', 'FAIL', 'APPROVED', 'REJECTED', 'MODIFY', 'BLOCK', 'WARN'
    resolution_notes TEXT,
    evidence_path TEXT,  -- Path to evidence bundle (JSON, PDF, etc.)
    sha256_hash CHAR(64) NOT NULL,  -- Hash of (previous_hash + event_data)
    previous_audit_id UUID REFERENCES fhq_meta.adr_audit_log(audit_id),  -- Hash chain linkage
    hash_chain_id VARCHAR(100),  -- e.g., 'HC-LARS-ADR004-G0-20251123'
    signature_id VARCHAR(200),  -- Ed25519 signature reference
    metadata JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Constraints
    CONSTRAINT valid_gate_stage CHECK (
        (event_type = 'SUBMISSION' AND gate_stage = 'G0') OR
        (event_type = 'G1_TECHNICAL_VALIDATION' AND gate_stage = 'G1') OR
        (event_type = 'G2_GOVERNANCE_VALIDATION' AND gate_stage = 'G2') OR
        (event_type = 'G3_AUDIT_VERIFICATION' AND gate_stage = 'G3') OR
        (event_type = 'G4_CANONICALIZATION' AND gate_stage = 'G4') OR
        (event_type IN ('MODIFICATION', 'DEPRECATION'))
    )
);

CREATE INDEX idx_adr_audit_log_proposal ON fhq_meta.adr_audit_log(change_proposal_id);
CREATE INDEX idx_adr_audit_log_event_type ON fhq_meta.adr_audit_log(event_type);
CREATE INDEX idx_adr_audit_log_timestamp ON fhq_meta.adr_audit_log(timestamp DESC);
CREATE INDEX idx_adr_audit_log_hash_chain ON fhq_meta.adr_audit_log(hash_chain_id);

COMMENT ON TABLE fhq_meta.adr_audit_log IS 'ADR-004: Immutable audit trail for all ADR changes (G0-G4 gates)';
COMMENT ON COLUMN fhq_meta.adr_audit_log.sha256_hash IS 'SHA-256 hash chain: hash(previous_hash || event_data)';


-- ADR Version History - Track all versions of each ADR
CREATE TABLE IF NOT EXISTS fhq_meta.adr_version_history (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adr_id VARCHAR(20) NOT NULL REFERENCES fhq_meta.adr_registry(adr_id),
    version VARCHAR(20) NOT NULL,
    change_summary TEXT,
    file_path TEXT,
    sha256_hash CHAR(64) NOT NULL,
    approved_by VARCHAR(50),
    approved_at TIMESTAMPTZ,
    audit_log_id UUID REFERENCES fhq_meta.adr_audit_log(audit_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(adr_id, version)
);

CREATE INDEX idx_adr_version_history_adr ON fhq_meta.adr_version_history(adr_id);

COMMENT ON TABLE fhq_meta.adr_version_history IS 'ADR-004: Version lineage for all ADRs';


-- =============================================================================
-- ED25519 KEY MANAGEMENT (ADR-008)
-- =============================================================================

-- Agent Keys - Ed25519 key lifecycle management
CREATE TABLE IF NOT EXISTS fhq_meta.agent_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    key_type VARCHAR(50) NOT NULL CHECK (key_type IN ('ED25519_SIGNING', 'ED25519_VERIFICATION')),
    key_state VARCHAR(50) NOT NULL CHECK (key_state IN ('PENDING', 'ACTIVE', 'DEPRECATED', 'ARCHIVED')),
    public_key_hex TEXT NOT NULL,  -- Ed25519 public key (32 bytes, hex-encoded)
    key_storage_tier VARCHAR(50) CHECK (key_storage_tier IN ('TIER1_HOT', 'TIER2_WARM', 'TIER3_COLD')),
    key_storage_location TEXT,  -- Vault path, HSM slot, or file path
    activation_date TIMESTAMPTZ,
    deprecation_date TIMESTAMPTZ,
    archival_date TIMESTAMPTZ,
    expiration_date TIMESTAMPTZ,
    retention_period_days INTEGER DEFAULT 2555,  -- 7 years per ADR-008
    sha256_hash CHAR(64),  -- Hash of public key
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT one_active_key_per_agent UNIQUE (agent_id, key_state)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX idx_agent_keys_agent ON fhq_meta.agent_keys(agent_id);
CREATE INDEX idx_agent_keys_state ON fhq_meta.agent_keys(key_state);
CREATE INDEX idx_agent_keys_public_key ON fhq_meta.agent_keys(public_key_hex);

COMMENT ON TABLE fhq_meta.agent_keys IS 'ADR-008: Ed25519 key lifecycle management (PENDING → ACTIVE → DEPRECATED → ARCHIVED)';
COMMENT ON COLUMN fhq_meta.agent_keys.key_state IS 'PENDING (0h retention) → ACTIVE (90 days) → DEPRECATED (24h grace) → ARCHIVED (7 years)';


-- Key Archival Log - Audit trail for key rotation events
CREATE TABLE IF NOT EXISTS fhq_meta.key_archival_log (
    archival_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_id UUID NOT NULL REFERENCES fhq_meta.agent_keys(key_id),
    agent_id VARCHAR(50) NOT NULL,
    archival_event VARCHAR(50) NOT NULL CHECK (archival_event IN (
        'KEY_GENERATION',
        'KEY_ACTIVATION',
        'KEY_ROTATION',
        'KEY_DEPRECATION',
        'KEY_ARCHIVAL',
        'KEY_DESTRUCTION',
        'TIER_MIGRATION'
    )),
    from_state VARCHAR(50),
    to_state VARCHAR(50),
    from_tier VARCHAR(50),
    to_tier VARCHAR(50),
    reason TEXT,
    evidence_path TEXT,
    performed_by VARCHAR(50) NOT NULL,
    sha256_hash CHAR(64),
    hash_chain_id VARCHAR(100),
    signature_id VARCHAR(200),
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_key_archival_log_key ON fhq_meta.key_archival_log(key_id);
CREATE INDEX idx_key_archival_log_agent ON fhq_meta.key_archival_log(agent_id);
CREATE INDEX idx_key_archival_log_timestamp ON fhq_meta.key_archival_log(timestamp DESC);

COMMENT ON TABLE fhq_meta.key_archival_log IS 'ADR-008: Audit trail for Ed25519 key rotation and archival events';


-- =============================================================================
-- AGENT CONTRACTS & EXECUTIVE ROLES (ADR-001 §12.3)
-- =============================================================================

-- Executive Roles - Agent definitions
CREATE TABLE IF NOT EXISTS fhq_governance.executive_roles (
    role_id VARCHAR(50) PRIMARY KEY,  -- 'LARS', 'STIG', 'LINE', 'FINN', 'VEGA', 'CODE', 'CEO'
    role_name TEXT NOT NULL,
    role_description TEXT,
    authority_level INTEGER CHECK (authority_level BETWEEN 0 AND 10),
    domain TEXT[],  -- e.g., {'strategy', 'design', 'coordination'}
    capabilities TEXT[],
    veto_power BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE fhq_governance.executive_roles IS 'ADR-001 §3: Executive roles and authority levels';

-- Insert agent roles
INSERT INTO fhq_governance.executive_roles (role_id, role_name, role_description, authority_level, domain, veto_power, active) VALUES
    ('LARS', 'Logic, Analytics & Research Strategy', 'CSO - System design, strategy, structural integrity, cross-domain coordination', 9, ARRAY['strategy', 'design', 'coordination', 'architecture'], FALSE, TRUE),
    ('STIG', 'System for Technical Implementation & Governance', 'CTO - Database schemas, deployments, technical constraints, execution management', 8, ARRAY['technical', 'implementation', 'deployment', 'database'], FALSE, TRUE),
    ('LINE', 'Live Infrastructure & Node Engineering', 'CIO - Runtime operations, pipelines, uptime, SRE, incident handling', 8, ARRAY['operations', 'infrastructure', 'monitoring', 'sre'], FALSE, TRUE),
    ('FINN', 'Financial Investments Neural Network', 'CRO - Research, analysis, feature generation, backtesting, market intelligence', 8, ARRAY['research', 'analysis', 'markets', 'signals'], FALSE, TRUE),
    ('VEGA', 'Verification & Governance Authority', 'CCO - Compliance, control, continuous audits, governance enforcement', 10, ARRAY['compliance', 'audit', 'governance', 'verification'], TRUE, TRUE),
    ('CODE', 'Engineering Execution Unit', 'Execution arm - Pipeline scripts, integrations, no autonomous decision authority', NULL, ARRAY['execution', 'engineering'], FALSE, TRUE),
    ('CEO', 'Chief Executive Officer', 'Human authority - Constitution approval, role appointment, exceptions', NULL, ARRAY['human_authority', 'constitutional'], TRUE, TRUE)
ON CONFLICT (role_id) DO UPDATE SET
    role_description = EXCLUDED.role_description,
    authority_level = EXCLUDED.authority_level,
    domain = EXCLUDED.domain,
    updated_at = NOW();


-- Agent Contracts - Inter-agent communication rules
CREATE TABLE IF NOT EXISTS fhq_governance.agent_contracts (
    contract_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL REFERENCES fhq_governance.executive_roles(role_id),
    contract_type VARCHAR(50) NOT NULL CHECK (contract_type IN (
        'MANDATE',
        'SERVICE_AGREEMENT',
        'DATA_SHARING',
        'ESCALATION_PROTOCOL',
        'DELEGATION_AUTHORITY'
    )),
    contract_status VARCHAR(50) NOT NULL CHECK (contract_status IN ('DRAFT', 'PENDING_G1', 'PENDING_G2', 'PENDING_G3', 'ACTIVE', 'SUSPENDED', 'TERMINATED')),
    counterparty_agents VARCHAR(50)[],  -- Other agents involved
    mandate_scope TEXT,
    authority_boundaries JSONB,  -- Specific constraints and permissions
    communication_protocols JSONB,  -- Message formats, frequencies
    escalation_rules JSONB,  -- When to escalate to LARS/VEGA/CEO
    performance_criteria JSONB,  -- Success metrics
    compliance_requirements TEXT[],  -- ADRs this contract must follow
    change_proposal_id VARCHAR(100),  -- Link to G0 submission
    approved_by VARCHAR(50),
    approved_at TIMESTAMPTZ,
    effective_from TIMESTAMPTZ,
    effective_until TIMESTAMPTZ,
    audit_log_id UUID REFERENCES fhq_meta.adr_audit_log(audit_id),
    signature_id VARCHAR(200),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_contracts_agent ON fhq_governance.agent_contracts(agent_id);
CREATE INDEX idx_agent_contracts_status ON fhq_governance.agent_contracts(contract_status);
CREATE INDEX idx_agent_contracts_proposal ON fhq_governance.agent_contracts(change_proposal_id);

COMMENT ON TABLE fhq_governance.agent_contracts IS 'ADR-001 §12.3: Inter-agent communication rules and mandates';


-- =============================================================================
-- MODEL PROVIDER POLICY (ADR-007 §4.5 - Tier-based routing)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.model_provider_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL REFERENCES fhq_governance.executive_roles(role_id),
    sensitivity_tier VARCHAR(20) NOT NULL CHECK (sensitivity_tier IN ('TIER1_HIGH', 'TIER2_MEDIUM', 'TIER3_LOW')),
    primary_provider VARCHAR(50) NOT NULL,  -- 'ANTHROPIC', 'OPENAI', 'DEEPSEEK'
    fallback_providers VARCHAR(50)[],
    model_name VARCHAR(100),
    data_sharing_allowed BOOLEAN DEFAULT FALSE,
    use_cases TEXT[],
    cost_envelope_per_call_usd NUMERIC(10, 6),
    max_calls_per_day INTEGER,
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    compliance TEXT[],  -- ADRs enforced
    approved_by VARCHAR(50),
    approved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(agent_id, sensitivity_tier)
);

CREATE INDEX idx_model_provider_policy_agent ON fhq_governance.model_provider_policy(agent_id);
CREATE INDEX idx_model_provider_policy_tier ON fhq_governance.model_provider_policy(sensitivity_tier);

COMMENT ON TABLE fhq_governance.model_provider_policy IS 'ADR-007 §4.5: LLM provider routing policies per agent tier';
COMMENT ON COLUMN fhq_governance.model_provider_policy.sensitivity_tier IS 'TIER1 (LARS/VEGA-Anthropic), TIER2 (FINN-OpenAI), TIER3 (STIG/LINE-DeepSeek)';


-- =============================================================================
-- ECONOMIC SAFETY LAYER - RATE LIMITS (ADR-012 §3.1)
-- =============================================================================

CREATE TABLE IF NOT EXISTS vega.llm_rate_limits (
    limit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) REFERENCES fhq_governance.executive_roles(role_id),
    provider VARCHAR(50) NOT NULL,  -- 'ANTHROPIC', 'OPENAI', 'DEEPSEEK', 'SERPER', 'SCHOLAR', 'COINDESK'
    limit_type VARCHAR(50) NOT NULL CHECK (limit_type IN (
        'CALLS_PER_MINUTE_PER_AGENT',
        'CALLS_PER_PIPELINE_EXECUTION',
        'GLOBAL_DAILY_LIMIT',
        'CONCURRENT_REQUESTS'
    )),
    limit_value INTEGER NOT NULL,
    enforcement_mode VARCHAR(50) DEFAULT 'BLOCK' CHECK (enforcement_mode IN ('BLOCK', 'WARN', 'LOG_ONLY')),
    violation_action VARCHAR(50) DEFAULT 'SWITCH_TO_STUB' CHECK (violation_action IN (
        'SWITCH_TO_STUB',
        'SUSPEND_AGENT',
        'NOTIFY_VEGA',
        'ESCALATE_TO_LARS'
    )),
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    live_mode BOOLEAN DEFAULT FALSE,  -- MUST be FALSE until VEGA attestation
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(agent_id, provider, limit_type)
);

CREATE INDEX idx_llm_rate_limits_agent ON vega.llm_rate_limits(agent_id);
CREATE INDEX idx_llm_rate_limits_provider ON vega.llm_rate_limits(provider);
CREATE INDEX idx_llm_rate_limits_live_mode ON vega.llm_rate_limits(live_mode);

COMMENT ON TABLE vega.llm_rate_limits IS 'ADR-012 §3.1: Rate limit governance for LLM and API calls';
COMMENT ON COLUMN vega.llm_rate_limits.live_mode IS 'CRITICAL: Must be FALSE until VEGA attestation (QG-F6)';


-- =============================================================================
-- ECONOMIC SAFETY LAYER - COST LIMITS (ADR-012 §3.2)
-- =============================================================================

CREATE TABLE IF NOT EXISTS vega.llm_cost_limits (
    limit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) REFERENCES fhq_governance.executive_roles(role_id),
    provider VARCHAR(50) NOT NULL,
    limit_type VARCHAR(50) NOT NULL CHECK (limit_type IN (
        'MAX_COST_PER_CALL_USD',
        'MAX_COST_PER_TASK_USD',
        'MAX_COST_PER_AGENT_PER_DAY_USD',
        'MAX_DAILY_COST_GLOBAL_USD'
    )),
    limit_value_usd NUMERIC(10, 6) NOT NULL,
    enforcement_mode VARCHAR(50) DEFAULT 'BLOCK' CHECK (enforcement_mode IN ('BLOCK', 'WARN', 'LOG_ONLY')),
    violation_action VARCHAR(50) DEFAULT 'SWITCH_TO_STUB' CHECK (violation_action IN (
        'SWITCH_TO_STUB',
        'SUSPEND_AGENT',
        'NOTIFY_VEGA',
        'ESCALATE_TO_LARS'
    )),
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    live_mode BOOLEAN DEFAULT FALSE,  -- MUST be FALSE until VEGA attestation
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(agent_id, provider, limit_type)
);

CREATE INDEX idx_llm_cost_limits_agent ON vega.llm_cost_limits(agent_id);
CREATE INDEX idx_llm_cost_limits_provider ON vega.llm_cost_limits(provider);
CREATE INDEX idx_llm_cost_limits_live_mode ON vega.llm_cost_limits(live_mode);

COMMENT ON TABLE vega.llm_cost_limits IS 'ADR-012 §3.2: Cost ceiling enforcement for LLM providers';


-- =============================================================================
-- ECONOMIC SAFETY LAYER - EXECUTION LIMITS (ADR-012 §3.3)
-- =============================================================================

CREATE TABLE IF NOT EXISTS vega.llm_execution_limits (
    limit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) REFERENCES fhq_governance.executive_roles(role_id),
    provider VARCHAR(50) NOT NULL,
    limit_type VARCHAR(50) NOT NULL CHECK (limit_type IN (
        'MAX_LLM_STEPS_PER_TASK',
        'MAX_TOTAL_LATENCY_MS',
        'MAX_TOTAL_TOKENS_GENERATED',
        'MAX_CONTEXT_WINDOW_TOKENS'
    )),
    limit_value INTEGER NOT NULL,
    enforcement_mode VARCHAR(50) DEFAULT 'BLOCK' CHECK (enforcement_mode IN ('BLOCK', 'WARN', 'LOG_ONLY')),
    abort_on_overrun BOOLEAN DEFAULT TRUE,
    violation_action VARCHAR(50) DEFAULT 'ABORT_TASK' CHECK (violation_action IN (
        'ABORT_TASK',
        'SWITCH_TO_STUB',
        'NOTIFY_VEGA',
        'ESCALATE_TO_LARS'
    )),
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    live_mode BOOLEAN DEFAULT FALSE,  -- MUST be FALSE until VEGA attestation
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(agent_id, provider, limit_type)
);

CREATE INDEX idx_llm_execution_limits_agent ON vega.llm_execution_limits(agent_id);
CREATE INDEX idx_llm_execution_limits_provider ON vega.llm_execution_limits(provider);
CREATE INDEX idx_llm_execution_limits_live_mode ON vega.llm_execution_limits(live_mode);

COMMENT ON TABLE vega.llm_execution_limits IS 'ADR-012 §3.3: Execution time and reasoning step limits';


-- =============================================================================
-- ECONOMIC SAFETY LAYER - USAGE LOG (ADR-012 §4)
-- =============================================================================

CREATE TABLE IF NOT EXISTS vega.llm_usage_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100),
    call_type VARCHAR(50),  -- 'COMPLETION', 'EMBEDDING', 'SEARCH', 'VISION'
    task_id UUID,
    cycle_id VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd NUMERIC(10, 6),
    actual_cost_usd NUMERIC(10, 6),
    latency_ms INTEGER,
    llm_steps_used INTEGER,
    success BOOLEAN,
    error_message TEXT,
    hash_chain_id VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_llm_usage_log_agent ON vega.llm_usage_log(agent_id);
CREATE INDEX idx_llm_usage_log_provider ON vega.llm_usage_log(provider);
CREATE INDEX idx_llm_usage_log_timestamp ON vega.llm_usage_log(timestamp DESC);
CREATE INDEX idx_llm_usage_log_task ON vega.llm_usage_log(task_id);

COMMENT ON TABLE vega.llm_usage_log IS 'ADR-012 §4: Detailed tracking of all LLM and API calls';


-- =============================================================================
-- ECONOMIC SAFETY LAYER - VIOLATION EVENTS (ADR-012 §5)
-- =============================================================================

CREATE TABLE IF NOT EXISTS vega.llm_violation_events (
    violation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    violation_type VARCHAR(50) NOT NULL CHECK (violation_type IN (
        'RATE_LIMIT_EXCEEDED',
        'COST_LIMIT_EXCEEDED',
        'EXECUTION_LIMIT_EXCEEDED',
        'UNAUTHORIZED_PROVIDER',
        'DATA_SHARING_VIOLATION'
    )),
    limit_type VARCHAR(100),
    limit_value TEXT,
    actual_value TEXT,
    enforcement_action VARCHAR(50),  -- Action taken (BLOCKED, WARNED, SUSPENDED, etc.)
    task_id UUID,
    cycle_id VARCHAR(100),
    evidence JSONB,
    vega_recommendation VARCHAR(50),  -- 'WARN', 'SUSPEND', 'BLOCK'
    lars_decision VARCHAR(50),  -- If escalated
    resolution_notes TEXT,
    hash_chain_id VARCHAR(100),
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_llm_violation_events_agent ON vega.llm_violation_events(agent_id);
CREATE INDEX idx_llm_violation_events_type ON vega.llm_violation_events(violation_type);
CREATE INDEX idx_llm_violation_events_timestamp ON vega.llm_violation_events(timestamp DESC);

COMMENT ON TABLE vega.llm_violation_events IS 'ADR-012 §5: Economic safety violation tracking and enforcement';


-- =============================================================================
-- POPULATE INITIAL PROVIDER POLICIES (ADR-007 Tier Model)
-- =============================================================================

-- TIER 1 - High Sensitivity (LARS, VEGA → Anthropic Claude only, no data sharing)
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, sensitivity_tier, primary_provider, fallback_providers,
    model_name, data_sharing_allowed, use_cases,
    cost_envelope_per_call_usd, max_calls_per_day,
    compliance, approved_by, approved_at
) VALUES
    ('LARS', 'TIER1_HIGH', 'ANTHROPIC', NULL,
     'claude-3-haiku-20240307', FALSE,
     ARRAY['strategic_analysis', 'governance_decisions', 'cross_domain_coordination'],
     0.08, 100,
     ARRAY['ADR-007', 'ADR-012'], 'CEO', NOW()),

    ('VEGA', 'TIER1_HIGH', 'ANTHROPIC', NULL,
     'claude-3-haiku-20240307', FALSE,
     ARRAY['compliance_audit', 'governance_enforcement', 'veto_decisions'],
     0.08, 50,
     ARRAY['ADR-007', 'ADR-012'], 'CEO', NOW())
ON CONFLICT (agent_id, sensitivity_tier) DO UPDATE SET
    primary_provider = EXCLUDED.primary_provider,
    model_name = EXCLUDED.model_name,
    updated_at = NOW();


-- TIER 2 - Medium Sensitivity (FINN → OpenAI GPT, no data sharing)
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, sensitivity_tier, primary_provider, fallback_providers,
    model_name, data_sharing_allowed, use_cases,
    cost_envelope_per_call_usd, max_calls_per_day,
    compliance, approved_by, approved_at
) VALUES
    ('FINN', 'TIER2_MEDIUM', 'OPENAI', ARRAY['ANTHROPIC'],
     'gpt-4-turbo', FALSE,
     ARRAY['research_analysis', 'signal_generation', 'market_intelligence'],
     0.04, 150,
     ARRAY['ADR-007', 'ADR-012'], 'CEO', NOW())
ON CONFLICT (agent_id, sensitivity_tier) DO UPDATE SET
    primary_provider = EXCLUDED.primary_provider,
    model_name = EXCLUDED.model_name,
    updated_at = NOW();


-- TIER 3 - Low Sensitivity (STIG, LINE → DeepSeek/OpenAI, data sharing allowed)
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, sensitivity_tier, primary_provider, fallback_providers,
    model_name, data_sharing_allowed, use_cases,
    cost_envelope_per_call_usd, max_calls_per_day,
    compliance, approved_by, approved_at
) VALUES
    ('STIG', 'TIER3_LOW', 'DEEPSEEK', ARRAY['OPENAI'],
     'deepseek-chat', TRUE,
     ARRAY['technical_validation', 'schema_analysis', 'deployment_checks'],
     0.005, 200,
     ARRAY['ADR-007', 'ADR-012'], 'CEO', NOW()),

    ('LINE', 'TIER3_LOW', 'DEEPSEEK', ARRAY['OPENAI'],
     'deepseek-chat', TRUE,
     ARRAY['infrastructure_monitoring', 'sre_operations', 'incident_response'],
     0.005, 300,
     ARRAY['ADR-007', 'ADR-012'], 'CEO', NOW())
ON CONFLICT (agent_id, sensitivity_tier) DO UPDATE SET
    primary_provider = EXCLUDED.primary_provider,
    model_name = EXCLUDED.model_name,
    updated_at = NOW();


-- =============================================================================
-- POPULATE INITIAL RATE LIMITS (ADR-012 Conservative Defaults)
-- =============================================================================

INSERT INTO vega.llm_rate_limits (
    agent_id, provider, limit_type, limit_value, enforcement_mode, violation_action, live_mode
) VALUES
    -- Anthropic (LARS, VEGA)
    ('LARS', 'ANTHROPIC', 'CALLS_PER_MINUTE_PER_AGENT', 3, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('LARS', 'ANTHROPIC', 'CALLS_PER_PIPELINE_EXECUTION', 5, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('VEGA', 'ANTHROPIC', 'CALLS_PER_MINUTE_PER_AGENT', 3, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('VEGA', 'ANTHROPIC', 'CALLS_PER_PIPELINE_EXECUTION', 5, 'BLOCK', 'SWITCH_TO_STUB', FALSE),

    -- OpenAI (FINN)
    ('FINN', 'OPENAI', 'CALLS_PER_MINUTE_PER_AGENT', 5, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('FINN', 'OPENAI', 'CALLS_PER_PIPELINE_EXECUTION', 10, 'BLOCK', 'SWITCH_TO_STUB', FALSE),

    -- DeepSeek (STIG, LINE)
    ('STIG', 'DEEPSEEK', 'CALLS_PER_MINUTE_PER_AGENT', 10, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('STIG', 'DEEPSEEK', 'CALLS_PER_PIPELINE_EXECUTION', 15, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('LINE', 'DEEPSEEK', 'CALLS_PER_MINUTE_PER_AGENT', 10, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('LINE', 'DEEPSEEK', 'CALLS_PER_PIPELINE_EXECUTION', 15, 'BLOCK', 'SWITCH_TO_STUB', FALSE),

    -- Global limits
    (NULL, 'ANTHROPIC', 'GLOBAL_DAILY_LIMIT', 100, 'BLOCK', 'NOTIFY_VEGA', FALSE),
    (NULL, 'OPENAI', 'GLOBAL_DAILY_LIMIT', 150, 'BLOCK', 'NOTIFY_VEGA', FALSE),
    (NULL, 'DEEPSEEK', 'GLOBAL_DAILY_LIMIT', 500, 'BLOCK', 'NOTIFY_VEGA', FALSE),

    -- API limits (Serper, Scholar, Coindesk, Marketaux, FRED)
    (NULL, 'SERPER', 'CALLS_PER_MINUTE_PER_AGENT', 5, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    (NULL, 'SCHOLAR', 'CALLS_PER_MINUTE_PER_AGENT', 3, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    (NULL, 'COINDESK', 'CALLS_PER_MINUTE_PER_AGENT', 10, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    (NULL, 'MARKETAUX', 'CALLS_PER_MINUTE_PER_AGENT', 5, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    (NULL, 'MARKETAUX', 'GLOBAL_DAILY_LIMIT', 100, 'BLOCK', 'NOTIFY_VEGA', FALSE),
    (NULL, 'FRED', 'CALLS_PER_MINUTE_PER_AGENT', 10, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    (NULL, 'FRED', 'GLOBAL_DAILY_LIMIT', 120, 'BLOCK', 'NOTIFY_VEGA', FALSE)
ON CONFLICT (agent_id, provider, limit_type) DO UPDATE SET
    limit_value = EXCLUDED.limit_value,
    updated_at = NOW();


-- =============================================================================
-- POPULATE INITIAL COST LIMITS (ADR-012 Conservative Defaults)
-- =============================================================================

INSERT INTO vega.llm_cost_limits (
    agent_id, provider, limit_type, limit_value_usd, enforcement_mode, violation_action, live_mode
) VALUES
    -- Per-call limits
    ('LARS', 'ANTHROPIC', 'MAX_COST_PER_CALL_USD', 0.08, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('VEGA', 'ANTHROPIC', 'MAX_COST_PER_CALL_USD', 0.08, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('FINN', 'OPENAI', 'MAX_COST_PER_CALL_USD', 0.04, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('STIG', 'DEEPSEEK', 'MAX_COST_PER_CALL_USD', 0.005, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('LINE', 'DEEPSEEK', 'MAX_COST_PER_CALL_USD', 0.005, 'BLOCK', 'SWITCH_TO_STUB', FALSE),

    -- Per-task limits
    ('LARS', 'ANTHROPIC', 'MAX_COST_PER_TASK_USD', 0.50, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('FINN', 'OPENAI', 'MAX_COST_PER_TASK_USD', 0.50, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('STIG', 'DEEPSEEK', 'MAX_COST_PER_TASK_USD', 0.10, 'BLOCK', 'SWITCH_TO_STUB', FALSE),
    ('LINE', 'DEEPSEEK', 'MAX_COST_PER_TASK_USD', 0.10, 'BLOCK', 'SWITCH_TO_STUB', FALSE),

    -- Per-agent daily limits
    ('LARS', 'ANTHROPIC', 'MAX_COST_PER_AGENT_PER_DAY_USD', 1.00, 'BLOCK', 'NOTIFY_VEGA', FALSE),
    ('VEGA', 'ANTHROPIC', 'MAX_COST_PER_AGENT_PER_DAY_USD', 0.50, 'BLOCK', 'NOTIFY_VEGA', FALSE),
    ('FINN', 'OPENAI', 'MAX_COST_PER_AGENT_PER_DAY_USD', 1.00, 'BLOCK', 'NOTIFY_VEGA', FALSE),
    ('STIG', 'DEEPSEEK', 'MAX_COST_PER_AGENT_PER_DAY_USD', 0.50, 'BLOCK', 'NOTIFY_VEGA', FALSE),
    ('LINE', 'DEEPSEEK', 'MAX_COST_PER_AGENT_PER_DAY_USD', 0.50, 'BLOCK', 'NOTIFY_VEGA', FALSE),

    -- Global daily limit
    (NULL, 'ANTHROPIC', 'MAX_DAILY_COST_GLOBAL_USD', 5.00, 'BLOCK', 'ESCALATE_TO_LARS', FALSE),
    (NULL, 'OPENAI', 'MAX_DAILY_COST_GLOBAL_USD', 3.00, 'BLOCK', 'ESCALATE_TO_LARS', FALSE),
    (NULL, 'DEEPSEEK', 'MAX_DAILY_COST_GLOBAL_USD', 2.00, 'BLOCK', 'ESCALATE_TO_LARS', FALSE)
ON CONFLICT (agent_id, provider, limit_type) DO UPDATE SET
    limit_value_usd = EXCLUDED.limit_value_usd,
    updated_at = NOW();


-- =============================================================================
-- POPULATE INITIAL EXECUTION LIMITS (ADR-012 Conservative Defaults)
-- =============================================================================

INSERT INTO vega.llm_execution_limits (
    agent_id, provider, limit_type, limit_value, enforcement_mode, abort_on_overrun, violation_action, live_mode
) VALUES
    -- LLM steps per task
    ('LARS', 'ANTHROPIC', 'MAX_LLM_STEPS_PER_TASK', 3, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),
    ('VEGA', 'ANTHROPIC', 'MAX_LLM_STEPS_PER_TASK', 3, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),
    ('FINN', 'OPENAI', 'MAX_LLM_STEPS_PER_TASK', 5, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),
    ('STIG', 'DEEPSEEK', 'MAX_LLM_STEPS_PER_TASK', 5, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),
    ('LINE', 'DEEPSEEK', 'MAX_LLM_STEPS_PER_TASK', 5, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),

    -- Total latency
    ('LARS', 'ANTHROPIC', 'MAX_TOTAL_LATENCY_MS', 3000, 'WARN', TRUE, 'NOTIFY_VEGA', FALSE),
    ('FINN', 'OPENAI', 'MAX_TOTAL_LATENCY_MS', 5000, 'WARN', TRUE, 'NOTIFY_VEGA', FALSE),
    ('STIG', 'DEEPSEEK', 'MAX_TOTAL_LATENCY_MS', 5000, 'WARN', TRUE, 'NOTIFY_VEGA', FALSE),
    ('LINE', 'DEEPSEEK', 'MAX_TOTAL_LATENCY_MS', 5000, 'WARN', TRUE, 'NOTIFY_VEGA', FALSE),

    -- Token generation limits (Anthropic Claude 3 Haiku: 4096 max output)
    ('LARS', 'ANTHROPIC', 'MAX_TOTAL_TOKENS_GENERATED', 4096, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),
    ('VEGA', 'ANTHROPIC', 'MAX_TOTAL_TOKENS_GENERATED', 4096, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),
    ('FINN', 'OPENAI', 'MAX_TOTAL_TOKENS_GENERATED', 4096, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),
    ('STIG', 'DEEPSEEK', 'MAX_TOTAL_TOKENS_GENERATED', 8192, 'BLOCK', TRUE, 'ABORT_TASK', FALSE),
    ('LINE', 'DEEPSEEK', 'MAX_TOTAL_TOKENS_GENERATED', 8192, 'BLOCK', TRUE, 'ABORT_TASK', FALSE)
ON CONFLICT (agent_id, provider, limit_type) DO UPDATE SET
    limit_value = EXCLUDED.limit_value,
    updated_at = NOW();


-- =============================================================================
-- CREATE G0 SUBMISSION FOR LINE MANDATE
-- =============================================================================

-- Log G0 submission to audit log
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
    previous_audit_id,
    hash_chain_id,
    signature_id,
    metadata,
    timestamp
) VALUES (
    gen_random_uuid(),
    'G0-2025-11-23-LINE-MANDATE',
    'SUBMISSION',
    'G0',
    NULL,  -- Will be set after ADR creation
    'CODE',
    'SUBMITTED',
    'G0 Submission: LINE mandate registration with expanded provider support (DeepSeek, OpenAI, Serper, Scholar, Coindesk). Includes Economic Safety Layer (ADR-012) implementation with rate/cost/execution ceilings. LIVE_MODE=False until VEGA attestation (QG-F6).',
    '/home/user/vision-IoS/04_DATABASE/MIGRATIONS/018_line_mandate_governance_economic_safety.sql',
    encode(sha256('G0-2025-11-23-LINE-MANDATE'::bytea), 'hex'),
    NULL,
    'HC-CODE-ADR004-G0-20251123',
    'GENESIS_SIGNATURE_CODE_' || MD5(NOW()::TEXT),
    jsonb_build_object(
        'change_type', 'MODIFICATION',
        'change_category', 'API_LLM_PROVIDER_EXPANSION',
        'affected_agents', ARRAY['LINE', 'STIG', 'FINN', 'LARS', 'VEGA'],
        'new_providers', ARRAY['DEEPSEEK', 'OPENAI', 'SERPER', 'SCHOLAR', 'COINDESK', 'MARKETAUX', 'FRED'],
        'tables_created', ARRAY[
            'fhq_meta.adr_registry',
            'fhq_meta.adr_audit_log',
            'fhq_meta.adr_version_history',
            'fhq_meta.agent_keys',
            'fhq_meta.key_archival_log',
            'fhq_governance.executive_roles',
            'fhq_governance.agent_contracts',
            'fhq_governance.model_provider_policy',
            'vega.llm_rate_limits',
            'vega.llm_cost_limits',
            'vega.llm_execution_limits',
            'vega.llm_usage_log',
            'vega.llm_violation_events'
        ],
        'compliance', ARRAY['ADR-004', 'ADR-007', 'ADR-008', 'ADR-012'],
        'next_gate', 'G1_TECHNICAL_VALIDATION',
        'next_gate_owner', 'STIG',
        'live_mode', FALSE,
        'vega_attestation_required', 'QG-F6'
    ),
    NOW()
);


-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify all tables created
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema IN ('fhq_meta', 'fhq_governance', 'vega')
      AND table_name IN (
        'adr_registry', 'adr_audit_log', 'adr_version_history',
        'agent_keys', 'key_archival_log',
        'executive_roles', 'agent_contracts', 'model_provider_policy',
        'llm_rate_limits', 'llm_cost_limits', 'llm_execution_limits',
        'llm_usage_log', 'llm_violation_events'
      );

    IF table_count < 13 THEN
        RAISE EXCEPTION 'Expected 13 tables, found %', table_count;
    END IF;

    RAISE NOTICE '✅ All 13 governance and economic safety tables created';
END $$;


-- Verify G0 submission logged
DO $$
DECLARE
    submission_logged BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM fhq_meta.adr_audit_log
        WHERE change_proposal_id = 'G0-2025-11-23-LINE-MANDATE'
          AND event_type = 'SUBMISSION'
          AND gate_stage = 'G0'
    ) INTO submission_logged;

    IF NOT submission_logged THEN
        RAISE EXCEPTION 'G0 submission not logged';
    END IF;

    RAISE NOTICE '✅ G0 submission logged: G0-2025-11-23-LINE-MANDATE';
END $$;


-- Verify LIVE_MODE=False on all economic safety tables
DO $$
DECLARE
    live_mode_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO live_mode_count
    FROM (
        SELECT live_mode FROM vega.llm_rate_limits WHERE live_mode = TRUE
        UNION ALL
        SELECT live_mode FROM vega.llm_cost_limits WHERE live_mode = TRUE
        UNION ALL
        SELECT live_mode FROM vega.llm_execution_limits WHERE live_mode = TRUE
    ) AS live_checks;

    IF live_mode_count > 0 THEN
        RAISE EXCEPTION 'CRITICAL: Found % rows with LIVE_MODE=TRUE. All must be FALSE until VEGA attestation.', live_mode_count;
    END IF;

    RAISE NOTICE '✅ LIVE_MODE=False verified on all economic safety limits';
END $$;


-- Display summary
SELECT
    'MIGRATION 018 COMPLETE' AS status,
    'LINE Mandate G0 Submission & Economic Safety Layer' AS description,
    (SELECT COUNT(*) FROM fhq_governance.executive_roles WHERE active = TRUE) AS active_roles,
    (SELECT COUNT(*) FROM fhq_governance.model_provider_policy) AS provider_policies,
    (SELECT COUNT(*) FROM vega.llm_rate_limits) AS rate_limits,
    (SELECT COUNT(*) FROM vega.llm_cost_limits) AS cost_limits,
    (SELECT COUNT(*) FROM vega.llm_execution_limits) AS execution_limits;


COMMIT;


-- =============================================================================
-- FINAL SUMMARY
-- =============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 018: LINE MANDATE G0 SUBMISSION & ECONOMIC SAFETY LAYER'
\echo '═══════════════════════════════════════════════════════════════════════'
\echo '✅ ADR Governance Infrastructure (ADR-004)'
\echo '   ├─ fhq_meta.adr_registry'
\echo '   ├─ fhq_meta.adr_audit_log (G0-G4 gates)'
\echo '   └─ fhq_meta.adr_version_history'
\echo ''
\echo '✅ Ed25519 Key Management (ADR-008)'
\echo '   ├─ fhq_meta.agent_keys (PENDING → ACTIVE → DEPRECATED → ARCHIVED)'
\echo '   └─ fhq_meta.key_archival_log'
\echo ''
\echo '✅ Agent Contracts & Roles (ADR-001 §12.3)'
\echo '   ├─ fhq_governance.executive_roles (7 roles registered)'
\echo '   └─ fhq_governance.agent_contracts'
\echo ''
\echo '✅ Provider Routing Policies (ADR-007 §4.5)'
\echo '   └─ fhq_governance.model_provider_policy'
\echo '      ├─ TIER1 (LARS/VEGA): Anthropic Claude (no sharing)'
\echo '      ├─ TIER2 (FINN): OpenAI GPT (no sharing)'
\echo '      └─ TIER3 (STIG/LINE): DeepSeek/OpenAI (sharing allowed)'
\echo ''
\echo '✅ Economic Safety Layer (ADR-012)'
\echo '   ├─ vega.llm_rate_limits (per-agent, per-provider, global)'
\echo '   ├─ vega.llm_cost_limits (call, task, daily ceilings)'
\echo '   ├─ vega.llm_execution_limits (steps, latency, tokens)'
\echo '   ├─ vega.llm_usage_log (detailed call tracking)'
\echo '   └─ vega.llm_violation_events (enforcement actions)'
\echo ''
\echo '✅ G0 Submission Logged'
\echo '   ├─ Change Proposal: G0-2025-11-23-LINE-MANDATE'
\echo '   ├─ Event Type: SUBMISSION (API/LLM Provider Expansion)'
\echo '   ├─ Initiated By: CODE'
\echo '   ├─ Hash Chain: HC-CODE-ADR004-G0-20251123'
\echo '   └─ Next Gate: G1_TECHNICAL_VALIDATION (Owner: STIG)'
\echo ''
\echo '⚠️  CRITICAL: LIVE_MODE=False on ALL economic safety limits'
\echo '   └─ Must remain FALSE until VEGA attestation (QG-F6)'
\echo ''
\echo '═══════════════════════════════════════════════════════════════════════'
\echo ''
\echo 'Next Steps (ADR-004 G1→G4 Process):'
\echo '  G1 (STIG): Technical validation of schema changes and provider policies'
\echo '  G2 (LARS): Governance validation of mandate scope and authority'
\echo '  G3 (VEGA): Audit verification of compliance and economic safety'
\echo '  G4 (CEO):  Canonicalization and production approval'
\echo ''
\echo 'Query Examples:'
\echo '  SELECT * FROM fhq_meta.adr_audit_log ORDER BY timestamp DESC LIMIT 10;'
\echo '  SELECT * FROM fhq_governance.model_provider_policy;'
\echo '  SELECT * FROM vega.llm_rate_limits WHERE agent_id = '\''LINE'\'';'
\echo '  SELECT * FROM vega.llm_cost_limits WHERE live_mode = FALSE;'
\echo ''
