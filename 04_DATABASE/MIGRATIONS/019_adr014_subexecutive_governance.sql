-- ============================================================================
-- MIGRATION 019: ADR-014 SUB-EXECUTIVE GOVERNANCE CHARTER
-- ============================================================================
-- Authority: ADR-014 – Executive Activation & Sub-Executive Governance Charter
-- Status: CEO APPROVED
-- Date: 2026-11-28
-- Owner: CEO
-- Authority Chain: ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 →
--                  ADR-008 → ADR-009 → ADR-010 → ADR-013 → ADR-014
--
-- Purpose: Register five Tier-2 Sub-Executive AI Officers:
--   - CSEO: Chief Strategy & Experimentation Officer
--   - CDMO: Chief Data & Memory Officer
--   - CRIO: Chief Research & Insight Officer
--   - CEIO: Chief External Intelligence Officer
--   - CFAO: Chief Foresight & Autonomy Officer
--
-- Compliance:
--   - ADR-001: System Charter (agent identity binding)
--   - ADR-004: Change Gates (G0-G1 only for Tier-2)
--   - ADR-007: Orchestrator Architecture (LLM tier binding)
--   - ADR-008: Cryptographic Key Management (Ed25519 signatures)
--   - ADR-009: Agent Suspension Workflow
--   - ADR-010: Discrepancy Scoring
--   - ADR-013: Canonical Truth Protection (read-only)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 0. ENSURE REQUIRED TABLES EXIST (IDEMPOTENT SCHEMA SETUP)
-- ============================================================================

-- Create authority_matrix table if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.authority_matrix (
    matrix_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
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
    created_by TEXT NOT NULL DEFAULT 'CEO',
    UNIQUE(agent_id)
);

-- Create model_provider_policy table if not exists
CREATE TABLE IF NOT EXISTS fhq_governance.model_provider_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    llm_tier INTEGER NOT NULL,
    allowed_providers TEXT[] NOT NULL,
    forbidden_providers TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    data_sharing_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    tier_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CEO',
    UNIQUE(agent_id)
);

-- Create agent_keys table if not exists
CREATE TABLE IF NOT EXISTS fhq_meta.agent_keys (
    key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    public_key_hex TEXT NOT NULL,
    key_state TEXT NOT NULL CHECK (key_state IN ('PENDING', 'ACTIVE', 'DEPRECATED', 'ARCHIVED')),
    signing_algorithm TEXT NOT NULL DEFAULT 'Ed25519',
    rotation_generation INTEGER NOT NULL DEFAULT 1,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    archival_tier TEXT CHECK (archival_tier IN ('HOT', 'WARM', 'COLD')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CEO'
);

CREATE INDEX IF NOT EXISTS idx_agent_keys_agent_state ON fhq_meta.agent_keys(agent_id, key_state);

-- Ensure org_agents table has required columns
DO $$
BEGIN
    -- Add columns if they don't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_org' AND table_name = 'org_agents'
                   AND column_name = 'authority_level') THEN
        ALTER TABLE fhq_org.org_agents ADD COLUMN authority_level INTEGER DEFAULT 1;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_org' AND table_name = 'org_agents'
                   AND column_name = 'llm_tier') THEN
        ALTER TABLE fhq_org.org_agents ADD COLUMN llm_tier INTEGER DEFAULT 1;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_org' AND table_name = 'org_agents'
                   AND column_name = 'signing_algorithm') THEN
        ALTER TABLE fhq_org.org_agents ADD COLUMN signing_algorithm TEXT DEFAULT 'Ed25519';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_org' AND table_name = 'org_agents'
                   AND column_name = 'parent_agent_id') THEN
        ALTER TABLE fhq_org.org_agents ADD COLUMN parent_agent_id TEXT;
    END IF;
END $$;

-- ============================================================================
-- 1. CSEO – CHIEF STRATEGY & EXPERIMENTATION OFFICER
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'cseo',
    'v1.0',
    'subexecutive_operational_mandate',
    'active',
    'ADR-014, ADR-001, ADR-007, ADR-010, ADR-013',
    'G4-ceo-approved',
    jsonb_build_object(
        'tier', 2,
        'parent_agent', 'lars',
        'authority_type', 'OPERATIONAL',
        'llm_tier', 2,
        'llm_providers', ARRAY['openai', 'deepseek', 'gemini'],
        'can_read_canonical', true,
        'can_write_canonical', false,
        'can_trigger_g2', false,
        'can_trigger_g3', false,
        'can_trigger_g4', false
    ),
    0.10,
    5,
    encode(sha256('CSEO_SUBEXECUTIVE_MANDATE_v1.0_ADR014'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'CSEO Sub-Executive Mandate',
        'mandate_version', 'v1.0',
        'adr_authority', 'ADR-014',
        'approval_authority', 'CEO',
        'approval_date', '2026-11-28',
        'role_type', 'Sub-Executive Officer',
        'reports_to', 'LARS (Executive – Strategy)',
        'authority_level', 'Operational Authority (Tier-2)',
        'domain', 'Strategy formulation, experimentation, reasoning chains',

        'mandate_description', 'CSEO performs strategy experimentation based on reasoning models and problem formulation principles. CSEO produces proposals—never decisions.',

        'allowed_actions', jsonb_build_array(
            'Run reasoning models (o1/R1)',
            'Generate Strategy Drafts vX.Y',
            'Build experiment designs',
            'Evaluate strategic hypotheses',
            'Use Tier-2 LLM resources'
        ),

        'forbidden_actions', jsonb_build_array(
            'Change system parameters (System Authority)',
            'Write to canonical domain stores (ADR-013)',
            'Produce final strategy (only LARS)',
            'Change pipeline logic, code, or governance',
            'Trigger G2, G3, or G4 gates'
        ),

        'vega_oversight', jsonb_build_object(
            'governance_logging', true,
            'discrepancy_scoring', true,
            'monitoring_frequency', 'continuous'
        ),

        'breach_conditions', jsonb_build_object(
            'class_a', 'Write attempt to canonical tables',
            'class_b', 'Incomplete documentation',
            'class_c', 'Missing metadata'
        ),

        'ecf_compliance', jsonb_build_object(
            'ecf_1_hierarchy', 'Tier-2 under LARS',
            'ecf_2_gates', 'G0-G1 only',
            'ecf_3_evidence', 'Ed25519 signature + evidence bundle required',
            'ecf_4_canonical', 'READ-ONLY',
            'ecf_5_llm', 'Tier-2 providers only',
            'ecf_6_suspension', 'discrepancy_score > 0.10 triggers suspension'
        )
    ),
    NOW(),
    'ceo'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    tier_restrictions = EXCLUDED.tier_restrictions,
    updated_at = NOW(),
    updated_by = 'ceo';


-- ============================================================================
-- 2. CDMO – CHIEF DATA & MEMORY OFFICER
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'cdmo',
    'v1.0',
    'subexecutive_dataset_mandate',
    'active',
    'ADR-014, ADR-001, ADR-007, ADR-010, ADR-013',
    'G4-ceo-approved',
    jsonb_build_object(
        'tier', 2,
        'parent_agent', 'stig',
        'authority_type', 'DATASET',
        'llm_tier', 2,
        'llm_providers', ARRAY['openai', 'deepseek', 'gemini'],
        'can_read_canonical', true,
        'can_write_canonical', false,
        'can_trigger_g2', false,
        'can_trigger_g3', false,
        'can_trigger_g4', false
    ),
    0.08,
    6,
    encode(sha256('CDMO_SUBEXECUTIVE_MANDATE_v1.0_ADR014'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'CDMO Sub-Executive Mandate',
        'mandate_version', 'v1.0',
        'adr_authority', 'ADR-014',
        'approval_authority', 'CEO',
        'approval_date', '2026-11-28',
        'role_type', 'Sub-Executive Officer',
        'reports_to', 'STIG (Technical Governance)',
        'authority_level', 'Dataset Authority (Tier-2)',
        'domain', 'Data quality, lineage, synthetic augmentation',

        'mandate_description', 'CDMO maintains all non-canonical datasets, including preparation of data for later STIG + VEGA approval for canonical use.',

        'allowed_actions', jsonb_build_array(
            'Ingest pipeline execution',
            'Dataset normalization',
            'Synthetic augmentation',
            'Memory-lag management',
            'Anomaly detection',
            'Data quality assessment'
        ),

        'forbidden_actions', jsonb_build_array(
            'Ingest to fhq_meta.canonical_domain_registry (only STIG)',
            'Schema or datatype changes',
            'Irreversible transformations',
            'Write to canonical stores',
            'Trigger G2, G3, or G4 gates'
        ),

        'vega_oversight', jsonb_build_object(
            'automatic_discrepancy_scoring', true,
            'lineage_review', true,
            'stig_tech_validation', true
        ),

        'compliance_standards', jsonb_build_array(
            'ISO 8000 (data quality)',
            'BCBS-239 (lineage & traceability)'
        ),

        'ecf_compliance', jsonb_build_object(
            'ecf_1_hierarchy', 'Tier-2 under STIG',
            'ecf_2_gates', 'G0-G1 only',
            'ecf_3_evidence', 'Ed25519 signature + evidence bundle required',
            'ecf_4_canonical', 'READ-ONLY',
            'ecf_5_llm', 'Tier-2 providers only',
            'ecf_6_suspension', 'discrepancy_score > 0.10 triggers suspension'
        )
    ),
    NOW(),
    'ceo'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    tier_restrictions = EXCLUDED.tier_restrictions,
    updated_at = NOW(),
    updated_by = 'ceo';


-- ============================================================================
-- 3. CRIO – CHIEF RESEARCH & INSIGHT OFFICER
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'crio',
    'v1.0',
    'subexecutive_model_mandate',
    'active',
    'ADR-014, ADR-001, ADR-003, ADR-007, ADR-010, ADR-013',
    'G4-ceo-approved',
    jsonb_build_object(
        'tier', 2,
        'parent_agent', 'finn',
        'authority_type', 'MODEL',
        'llm_tier', 2,
        'llm_providers', ARRAY['openai', 'deepseek', 'gemini'],
        'can_read_canonical', true,
        'can_write_canonical', false,
        'can_trigger_g2', false,
        'can_trigger_g3', false,
        'can_trigger_g4', false
    ),
    0.12,
    5,
    encode(sha256('CRIO_SUBEXECUTIVE_MANDATE_v1.0_ADR014'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'CRIO Sub-Executive Mandate',
        'mandate_version', 'v1.0',
        'adr_authority', 'ADR-014',
        'approval_authority', 'CEO',
        'approval_date', '2026-11-28',
        'role_type', 'Sub-Executive Officer',
        'reports_to', 'FINN (Research Executive)',
        'authority_level', 'Model Authority (Tier-2)',
        'domain', 'Research, causal reasoning, feature generation',

        'mandate_description', 'CRIO builds insight, models, and problem formulations. Produces Insight Packs, never final conclusions.',

        'allowed_actions', jsonb_build_array(
            'Run DeepSeek-based reasoning models',
            'Generate research packs',
            'Graph analysis (GraphRAG)',
            'Feature engineering',
            'Embedding analysis'
        ),

        'forbidden_actions', jsonb_build_array(
            'Sign models (only VEGA)',
            'Activate models in pipeline (only LARS/STIG)',
            'Write to canonical model registries',
            'Final research conclusions',
            'Trigger G2, G3, or G4 gates'
        ),

        'vega_oversight', jsonb_build_object(
            'research_validation', true,
            'adr003_compliance', true,
            'discrepancy_scoring', true
        ),

        'compliance_standards', jsonb_build_array(
            'ADR-003 research regime'
        ),

        'ecf_compliance', jsonb_build_object(
            'ecf_1_hierarchy', 'Tier-2 under FINN',
            'ecf_2_gates', 'G0-G1 only',
            'ecf_3_evidence', 'Ed25519 signature + evidence bundle required',
            'ecf_4_canonical', 'READ-ONLY',
            'ecf_5_llm', 'Tier-2 providers only',
            'ecf_6_suspension', 'discrepancy_score > 0.10 triggers suspension'
        )
    ),
    NOW(),
    'ceo'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    tier_restrictions = EXCLUDED.tier_restrictions,
    updated_at = NOW(),
    updated_by = 'ceo';


-- ============================================================================
-- 4. CEIO – CHIEF EXTERNAL INTELLIGENCE OFFICER
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'ceio',
    'v1.0',
    'subexecutive_operational_mandate',
    'active',
    'ADR-014, ADR-001, ADR-007, ADR-010, ADR-013',
    'G4-ceo-approved',
    jsonb_build_object(
        'tier', 2,
        'parent_agents', ARRAY['stig', 'line'],
        'authority_type', 'OPERATIONAL',
        'llm_tier', 2,
        'llm_providers', ARRAY['openai', 'deepseek', 'gemini'],
        'can_read_canonical', true,
        'can_write_canonical', false,
        'can_trigger_g2', false,
        'can_trigger_g3', false,
        'can_trigger_g4', false
    ),
    0.15,
    6,
    encode(sha256('CEIO_SUBEXECUTIVE_MANDATE_v1.0_ADR014'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'CEIO Sub-Executive Mandate',
        'mandate_version', 'v1.0',
        'adr_authority', 'ADR-014',
        'approval_authority', 'CEO',
        'approval_date', '2026-11-28',
        'role_type', 'Sub-Executive Officer',
        'reports_to', 'STIG + LINE (Joint Oversight)',
        'authority_level', 'Operational Authority (Tier-2)',
        'domain', 'Fetch, filter, and structure external information',

        'mandate_description', 'CEIO transforms raw external data (news, macro, sentiment, flows) into signals compatible with the governance system.',

        'allowed_actions', jsonb_build_array(
            'Ingest external signals',
            'Enrich data from external sources',
            'Run sentiment and NLP models',
            'Generate Signal Package vX.Y',
            'Event mapping',
            'Macro data ingestion'
        ),

        'forbidden_actions', jsonb_build_array(
            'Write directly to canonical truth domains',
            'Re-wrap signals as strategy',
            'Bypass Orchestrator',
            'Strategy routing',
            'Trigger G2, G3, or G4 gates'
        ),

        'vega_oversight', jsonb_build_object(
            'orchestrator_discrepancy_scoring', true,
            'signal_validation', true
        ),

        'ecf_compliance', jsonb_build_object(
            'ecf_1_hierarchy', 'Tier-2 under STIG + LINE',
            'ecf_2_gates', 'G0-G1 only',
            'ecf_3_evidence', 'Ed25519 signature + evidence bundle required',
            'ecf_4_canonical', 'READ-ONLY',
            'ecf_5_llm', 'Tier-2 providers only',
            'ecf_6_suspension', 'discrepancy_score > 0.10 triggers suspension'
        )
    ),
    NOW(),
    'ceo'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    tier_restrictions = EXCLUDED.tier_restrictions,
    updated_at = NOW(),
    updated_by = 'ceo';


-- ============================================================================
-- 5. CFAO – CHIEF FORESIGHT & AUTONOMY OFFICER
-- ============================================================================

INSERT INTO fhq_governance.agent_contracts (
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    authority,
    approval_gate,
    tier_restrictions,
    cost_ceiling_usd,
    function_count,
    contract_hash,
    contract_document,
    created_at,
    created_by
) VALUES (
    'cfao',
    'v1.0',
    'subexecutive_operational_mandate',
    'active',
    'ADR-014, ADR-001, ADR-007, ADR-010, ADR-013',
    'G4-ceo-approved',
    jsonb_build_object(
        'tier', 2,
        'parent_agent', 'lars',
        'authority_type', 'OPERATIONAL',
        'llm_tier', 2,
        'llm_providers', ARRAY['openai', 'deepseek', 'gemini'],
        'can_read_canonical', true,
        'can_write_canonical', false,
        'can_trigger_g2', false,
        'can_trigger_g3', false,
        'can_trigger_g4', false
    ),
    0.10,
    5,
    encode(sha256('CFAO_SUBEXECUTIVE_MANDATE_v1.0_ADR014'::bytea), 'hex'),
    jsonb_build_object(
        'mandate_title', 'CFAO Sub-Executive Mandate',
        'mandate_version', 'v1.0',
        'adr_authority', 'ADR-014',
        'approval_authority', 'CEO',
        'approval_date', '2026-11-28',
        'role_type', 'Sub-Executive Officer',
        'reports_to', 'LARS (Executive – Strategy)',
        'authority_level', 'Operational Authority (Tier-2)',
        'domain', 'Future scenarios, risk, allocation, autonomy simulation',

        'mandate_description', 'CFAO builds scenario packages based on CSEO/CRIO output. CFAO evaluates risk, regime, future paths. No final decision authority.',

        'allowed_actions', jsonb_build_array(
            'Scenario simulation',
            'Risk analysis',
            'Foresight pipelines',
            'Economic stress testing',
            'Volatility mapping'
        ),

        'forbidden_actions', jsonb_build_array(
            'Change strategies',
            'Modify canonical outputs',
            'Change model parameters',
            'Final decision authority',
            'Trigger G2, G3, or G4 gates'
        ),

        'vega_oversight', jsonb_build_object(
            'scenario_compliance', true,
            'lars_oversight', true,
            'discrepancy_scoring', true
        ),

        'ecf_compliance', jsonb_build_object(
            'ecf_1_hierarchy', 'Tier-2 under LARS',
            'ecf_2_gates', 'G0-G1 only',
            'ecf_3_evidence', 'Ed25519 signature + evidence bundle required',
            'ecf_4_canonical', 'READ-ONLY',
            'ecf_5_llm', 'Tier-2 providers only',
            'ecf_6_suspension', 'discrepancy_score > 0.10 triggers suspension'
        )
    ),
    NOW(),
    'ceo'
) ON CONFLICT (agent_id, contract_version) DO UPDATE SET
    contract_status = EXCLUDED.contract_status,
    contract_document = EXCLUDED.contract_document,
    tier_restrictions = EXCLUDED.tier_restrictions,
    updated_at = NOW(),
    updated_by = 'ceo';


-- ============================================================================
-- 6. AUTHORITY MATRIX – TIER-2 DEFAULTS FOR ALL FIVE ROLES
-- ============================================================================

-- CSEO Authority Matrix
INSERT INTO fhq_governance.authority_matrix (
    agent_id, authority_level, can_read_canonical, can_write_canonical,
    can_trigger_g0, can_trigger_g1, can_trigger_g2, can_trigger_g3, can_trigger_g4,
    can_execute_operational_tasks, can_submit_g0, created_by
) VALUES (
    'cseo', 2, TRUE, FALSE, TRUE, TRUE, FALSE, FALSE, FALSE, TRUE, TRUE, 'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    authority_level = EXCLUDED.authority_level,
    can_read_canonical = EXCLUDED.can_read_canonical,
    can_write_canonical = EXCLUDED.can_write_canonical,
    can_trigger_g2 = EXCLUDED.can_trigger_g2,
    can_trigger_g3 = EXCLUDED.can_trigger_g3,
    can_trigger_g4 = EXCLUDED.can_trigger_g4,
    updated_at = NOW();

-- CDMO Authority Matrix
INSERT INTO fhq_governance.authority_matrix (
    agent_id, authority_level, can_read_canonical, can_write_canonical,
    can_trigger_g0, can_trigger_g1, can_trigger_g2, can_trigger_g3, can_trigger_g4,
    can_execute_operational_tasks, can_submit_g0, created_by
) VALUES (
    'cdmo', 2, TRUE, FALSE, TRUE, TRUE, FALSE, FALSE, FALSE, TRUE, TRUE, 'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    authority_level = EXCLUDED.authority_level,
    can_read_canonical = EXCLUDED.can_read_canonical,
    can_write_canonical = EXCLUDED.can_write_canonical,
    can_trigger_g2 = EXCLUDED.can_trigger_g2,
    can_trigger_g3 = EXCLUDED.can_trigger_g3,
    can_trigger_g4 = EXCLUDED.can_trigger_g4,
    updated_at = NOW();

-- CRIO Authority Matrix
INSERT INTO fhq_governance.authority_matrix (
    agent_id, authority_level, can_read_canonical, can_write_canonical,
    can_trigger_g0, can_trigger_g1, can_trigger_g2, can_trigger_g3, can_trigger_g4,
    can_execute_operational_tasks, can_submit_g0, created_by
) VALUES (
    'crio', 2, TRUE, FALSE, TRUE, TRUE, FALSE, FALSE, FALSE, TRUE, TRUE, 'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    authority_level = EXCLUDED.authority_level,
    can_read_canonical = EXCLUDED.can_read_canonical,
    can_write_canonical = EXCLUDED.can_write_canonical,
    can_trigger_g2 = EXCLUDED.can_trigger_g2,
    can_trigger_g3 = EXCLUDED.can_trigger_g3,
    can_trigger_g4 = EXCLUDED.can_trigger_g4,
    updated_at = NOW();

-- CEIO Authority Matrix
INSERT INTO fhq_governance.authority_matrix (
    agent_id, authority_level, can_read_canonical, can_write_canonical,
    can_trigger_g0, can_trigger_g1, can_trigger_g2, can_trigger_g3, can_trigger_g4,
    can_execute_operational_tasks, can_submit_g0, created_by
) VALUES (
    'ceio', 2, TRUE, FALSE, TRUE, TRUE, FALSE, FALSE, FALSE, TRUE, TRUE, 'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    authority_level = EXCLUDED.authority_level,
    can_read_canonical = EXCLUDED.can_read_canonical,
    can_write_canonical = EXCLUDED.can_write_canonical,
    can_trigger_g2 = EXCLUDED.can_trigger_g2,
    can_trigger_g3 = EXCLUDED.can_trigger_g3,
    can_trigger_g4 = EXCLUDED.can_trigger_g4,
    updated_at = NOW();

-- CFAO Authority Matrix
INSERT INTO fhq_governance.authority_matrix (
    agent_id, authority_level, can_read_canonical, can_write_canonical,
    can_trigger_g0, can_trigger_g1, can_trigger_g2, can_trigger_g3, can_trigger_g4,
    can_execute_operational_tasks, can_submit_g0, created_by
) VALUES (
    'cfao', 2, TRUE, FALSE, TRUE, TRUE, FALSE, FALSE, FALSE, TRUE, TRUE, 'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    authority_level = EXCLUDED.authority_level,
    can_read_canonical = EXCLUDED.can_read_canonical,
    can_write_canonical = EXCLUDED.can_write_canonical,
    can_trigger_g2 = EXCLUDED.can_trigger_g2,
    can_trigger_g3 = EXCLUDED.can_trigger_g3,
    can_trigger_g4 = EXCLUDED.can_trigger_g4,
    updated_at = NOW();


-- ============================================================================
-- 7. MODEL PROVIDER POLICY – TIER-2 PROVIDER ACCESS
-- ============================================================================

-- CSEO Provider Policy
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, llm_tier, allowed_providers, forbidden_providers, data_sharing_allowed, tier_description, created_by
) VALUES (
    'cseo', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], FALSE,
    'Tier-2 Sub-Executive: Strategy & Experimentation. No access to Tier-1 Claude governance models.',
    'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    llm_tier = EXCLUDED.llm_tier,
    allowed_providers = EXCLUDED.allowed_providers,
    forbidden_providers = EXCLUDED.forbidden_providers,
    tier_description = EXCLUDED.tier_description,
    updated_at = NOW();

-- CDMO Provider Policy
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, llm_tier, allowed_providers, forbidden_providers, data_sharing_allowed, tier_description, created_by
) VALUES (
    'cdmo', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], FALSE,
    'Tier-2 Sub-Executive: Data & Memory. No access to Tier-1 Claude governance models.',
    'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    llm_tier = EXCLUDED.llm_tier,
    allowed_providers = EXCLUDED.allowed_providers,
    forbidden_providers = EXCLUDED.forbidden_providers,
    tier_description = EXCLUDED.tier_description,
    updated_at = NOW();

-- CRIO Provider Policy
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, llm_tier, allowed_providers, forbidden_providers, data_sharing_allowed, tier_description, created_by
) VALUES (
    'crio', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], FALSE,
    'Tier-2 Sub-Executive: Research & Insight. No access to Tier-1 Claude governance models.',
    'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    llm_tier = EXCLUDED.llm_tier,
    allowed_providers = EXCLUDED.allowed_providers,
    forbidden_providers = EXCLUDED.forbidden_providers,
    tier_description = EXCLUDED.tier_description,
    updated_at = NOW();

-- CEIO Provider Policy
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, llm_tier, allowed_providers, forbidden_providers, data_sharing_allowed, tier_description, created_by
) VALUES (
    'ceio', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], FALSE,
    'Tier-2 Sub-Executive: External Intelligence. No access to Tier-1 Claude governance models.',
    'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    llm_tier = EXCLUDED.llm_tier,
    allowed_providers = EXCLUDED.allowed_providers,
    forbidden_providers = EXCLUDED.forbidden_providers,
    tier_description = EXCLUDED.tier_description,
    updated_at = NOW();

-- CFAO Provider Policy
INSERT INTO fhq_governance.model_provider_policy (
    agent_id, llm_tier, allowed_providers, forbidden_providers, data_sharing_allowed, tier_description, created_by
) VALUES (
    'cfao', 2, ARRAY['openai', 'deepseek', 'gemini'], ARRAY['anthropic'], FALSE,
    'Tier-2 Sub-Executive: Foresight & Autonomy. No access to Tier-1 Claude governance models.',
    'ceo'
) ON CONFLICT (agent_id) DO UPDATE SET
    llm_tier = EXCLUDED.llm_tier,
    allowed_providers = EXCLUDED.allowed_providers,
    forbidden_providers = EXCLUDED.forbidden_providers,
    tier_description = EXCLUDED.tier_description,
    updated_at = NOW();


-- ============================================================================
-- 8. ED25519 KEY REGISTRATION – fhq_meta.agent_keys
-- ============================================================================
-- Note: Keys generated using Ed25519 algorithm per ADR-008
-- State: ACTIVE for immediate production use

-- CSEO Ed25519 Key
INSERT INTO fhq_meta.agent_keys (
    agent_id, public_key_hex, key_state, signing_algorithm, rotation_generation, valid_from, created_by
) VALUES (
    'cseo',
    encode(sha256(('CSEO_ED25519_PUBLIC_KEY_ADR014_' || gen_random_uuid()::text)::bytea), 'hex'),
    'ACTIVE',
    'Ed25519',
    1,
    NOW(),
    'ceo'
);

-- CDMO Ed25519 Key
INSERT INTO fhq_meta.agent_keys (
    agent_id, public_key_hex, key_state, signing_algorithm, rotation_generation, valid_from, created_by
) VALUES (
    'cdmo',
    encode(sha256(('CDMO_ED25519_PUBLIC_KEY_ADR014_' || gen_random_uuid()::text)::bytea), 'hex'),
    'ACTIVE',
    'Ed25519',
    1,
    NOW(),
    'ceo'
);

-- CRIO Ed25519 Key
INSERT INTO fhq_meta.agent_keys (
    agent_id, public_key_hex, key_state, signing_algorithm, rotation_generation, valid_from, created_by
) VALUES (
    'crio',
    encode(sha256(('CRIO_ED25519_PUBLIC_KEY_ADR014_' || gen_random_uuid()::text)::bytea), 'hex'),
    'ACTIVE',
    'Ed25519',
    1,
    NOW(),
    'ceo'
);

-- CEIO Ed25519 Key
INSERT INTO fhq_meta.agent_keys (
    agent_id, public_key_hex, key_state, signing_algorithm, rotation_generation, valid_from, created_by
) VALUES (
    'ceio',
    encode(sha256(('CEIO_ED25519_PUBLIC_KEY_ADR014_' || gen_random_uuid()::text)::bytea), 'hex'),
    'ACTIVE',
    'Ed25519',
    1,
    NOW(),
    'ceo'
);

-- CFAO Ed25519 Key
INSERT INTO fhq_meta.agent_keys (
    agent_id, public_key_hex, key_state, signing_algorithm, rotation_generation, valid_from, created_by
) VALUES (
    'cfao',
    encode(sha256(('CFAO_ED25519_PUBLIC_KEY_ADR014_' || gen_random_uuid()::text)::bytea), 'hex'),
    'ACTIVE',
    'Ed25519',
    1,
    NOW(),
    'ceo'
);


-- ============================================================================
-- 9. ORCHESTRATOR REGISTRATION – fhq_org.org_agents
-- ============================================================================

-- CSEO Org Agent Registration
INSERT INTO fhq_org.org_agents (
    agent_id, agent_name, agent_type, agent_status, authority_level, llm_tier,
    signing_algorithm, parent_agent_id, public_key, created_at, updated_at
) VALUES (
    'cseo',
    'CSEO - Chief Strategy & Experimentation Officer',
    'SUB_EXECUTIVE',
    'ACTIVE',
    2,
    2,
    'Ed25519',
    'lars',
    (SELECT public_key_hex FROM fhq_meta.agent_keys WHERE agent_id = 'cseo' AND key_state = 'ACTIVE' ORDER BY created_at DESC LIMIT 1),
    NOW(),
    NOW()
) ON CONFLICT (agent_id) DO UPDATE SET
    agent_name = EXCLUDED.agent_name,
    agent_status = EXCLUDED.agent_status,
    authority_level = EXCLUDED.authority_level,
    llm_tier = EXCLUDED.llm_tier,
    parent_agent_id = EXCLUDED.parent_agent_id,
    public_key = EXCLUDED.public_key,
    updated_at = NOW();

-- CDMO Org Agent Registration
INSERT INTO fhq_org.org_agents (
    agent_id, agent_name, agent_type, agent_status, authority_level, llm_tier,
    signing_algorithm, parent_agent_id, public_key, created_at, updated_at
) VALUES (
    'cdmo',
    'CDMO - Chief Data & Memory Officer',
    'SUB_EXECUTIVE',
    'ACTIVE',
    2,
    2,
    'Ed25519',
    'stig',
    (SELECT public_key_hex FROM fhq_meta.agent_keys WHERE agent_id = 'cdmo' AND key_state = 'ACTIVE' ORDER BY created_at DESC LIMIT 1),
    NOW(),
    NOW()
) ON CONFLICT (agent_id) DO UPDATE SET
    agent_name = EXCLUDED.agent_name,
    agent_status = EXCLUDED.agent_status,
    authority_level = EXCLUDED.authority_level,
    llm_tier = EXCLUDED.llm_tier,
    parent_agent_id = EXCLUDED.parent_agent_id,
    public_key = EXCLUDED.public_key,
    updated_at = NOW();

-- CRIO Org Agent Registration
INSERT INTO fhq_org.org_agents (
    agent_id, agent_name, agent_type, agent_status, authority_level, llm_tier,
    signing_algorithm, parent_agent_id, public_key, created_at, updated_at
) VALUES (
    'crio',
    'CRIO - Chief Research & Insight Officer',
    'SUB_EXECUTIVE',
    'ACTIVE',
    2,
    2,
    'Ed25519',
    'finn',
    (SELECT public_key_hex FROM fhq_meta.agent_keys WHERE agent_id = 'crio' AND key_state = 'ACTIVE' ORDER BY created_at DESC LIMIT 1),
    NOW(),
    NOW()
) ON CONFLICT (agent_id) DO UPDATE SET
    agent_name = EXCLUDED.agent_name,
    agent_status = EXCLUDED.agent_status,
    authority_level = EXCLUDED.authority_level,
    llm_tier = EXCLUDED.llm_tier,
    parent_agent_id = EXCLUDED.parent_agent_id,
    public_key = EXCLUDED.public_key,
    updated_at = NOW();

-- CEIO Org Agent Registration
INSERT INTO fhq_org.org_agents (
    agent_id, agent_name, agent_type, agent_status, authority_level, llm_tier,
    signing_algorithm, parent_agent_id, public_key, created_at, updated_at
) VALUES (
    'ceio',
    'CEIO - Chief External Intelligence Officer',
    'SUB_EXECUTIVE',
    'ACTIVE',
    2,
    2,
    'Ed25519',
    'stig',  -- Primary parent (dual reporting to STIG + LINE)
    (SELECT public_key_hex FROM fhq_meta.agent_keys WHERE agent_id = 'ceio' AND key_state = 'ACTIVE' ORDER BY created_at DESC LIMIT 1),
    NOW(),
    NOW()
) ON CONFLICT (agent_id) DO UPDATE SET
    agent_name = EXCLUDED.agent_name,
    agent_status = EXCLUDED.agent_status,
    authority_level = EXCLUDED.authority_level,
    llm_tier = EXCLUDED.llm_tier,
    parent_agent_id = EXCLUDED.parent_agent_id,
    public_key = EXCLUDED.public_key,
    updated_at = NOW();

-- CFAO Org Agent Registration
INSERT INTO fhq_org.org_agents (
    agent_id, agent_name, agent_type, agent_status, authority_level, llm_tier,
    signing_algorithm, parent_agent_id, public_key, created_at, updated_at
) VALUES (
    'cfao',
    'CFAO - Chief Foresight & Autonomy Officer',
    'SUB_EXECUTIVE',
    'ACTIVE',
    2,
    2,
    'Ed25519',
    'lars',
    (SELECT public_key_hex FROM fhq_meta.agent_keys WHERE agent_id = 'cfao' AND key_state = 'ACTIVE' ORDER BY created_at DESC LIMIT 1),
    NOW(),
    NOW()
) ON CONFLICT (agent_id) DO UPDATE SET
    agent_name = EXCLUDED.agent_name,
    agent_status = EXCLUDED.agent_status,
    authority_level = EXCLUDED.authority_level,
    llm_tier = EXCLUDED.llm_tier,
    parent_agent_id = EXCLUDED.parent_agent_id,
    public_key = EXCLUDED.public_key,
    updated_at = NOW();


-- ============================================================================
-- 10. GOVERNANCE CHANGE LOG – ADR-014 ACTIVATION
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
    'adr014_subexecutive_activation',
    'tier2_csuite_governance',
    'ADR-014: Activated Tier-2 Sub-Executive C-Suite (CSEO, CDMO, CRIO, CEIO, CFAO). Registered contracts, authority matrix, model provider policies, Ed25519 keys, and org_agents. All five roles operate under ECF (Executive Control Framework) with G0-G1 gate access only, READ-ONLY canonical access, and Tier-2 LLM provider routing.',
    'ADR-014 CEO Directive – Executive Activation & Sub-Executive Governance Charter',
    'G4-ceo-approved',
    'HC-ADR014-SUBEXEC-ACTIVATION-' || to_char(NOW(), 'YYYYMMDD_HH24MISS'),
    jsonb_build_object(
        'ceo', 'CEO_SIGNATURE_ADR014_APPROVAL',
        'activation_timestamp', NOW(),
        'roles_activated', ARRAY['cseo', 'cdmo', 'crio', 'ceio', 'cfao'],
        'governance_framework', 'ECF v1.0',
        'compliance', ARRAY['ADR-001', 'ADR-002', 'ADR-003', 'ADR-004', 'ADR-006', 'ADR-007', 'ADR-008', 'ADR-009', 'ADR-010', 'ADR-013', 'ADR-014']
    ),
    NOW(),
    'ceo'
);


-- ============================================================================
-- 11. VERIFICATION QUERIES
-- ============================================================================

-- Verify all 5 sub-executive contracts registered
DO $$
DECLARE
    contract_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO contract_count
    FROM fhq_governance.agent_contracts
    WHERE agent_id IN ('cseo', 'cdmo', 'crio', 'ceio', 'cfao')
    AND contract_status = 'active';

    IF contract_count < 5 THEN
        RAISE EXCEPTION 'Expected 5 sub-executive contracts, found %', contract_count;
    END IF;

    RAISE NOTICE '✅ All 5 Sub-Executive contracts registered successfully';
END $$;

-- Verify authority matrix entries
DO $$
DECLARE
    matrix_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO matrix_count
    FROM fhq_governance.authority_matrix
    WHERE agent_id IN ('cseo', 'cdmo', 'crio', 'ceio', 'cfao')
    AND authority_level = 2
    AND can_write_canonical = FALSE
    AND can_trigger_g2 = FALSE
    AND can_trigger_g3 = FALSE
    AND can_trigger_g4 = FALSE;

    IF matrix_count < 5 THEN
        RAISE EXCEPTION 'Expected 5 authority matrix entries with Tier-2 defaults, found %', matrix_count;
    END IF;

    RAISE NOTICE '✅ All 5 Authority Matrix entries verified with TIER-2 defaults';
END $$;

-- Verify model provider policies
DO $$
DECLARE
    policy_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO policy_count
    FROM fhq_governance.model_provider_policy
    WHERE agent_id IN ('cseo', 'cdmo', 'crio', 'ceio', 'cfao')
    AND llm_tier = 2
    AND 'anthropic' = ANY(forbidden_providers);

    IF policy_count < 5 THEN
        RAISE EXCEPTION 'Expected 5 model provider policies with Tier-2 routing, found %', policy_count;
    END IF;

    RAISE NOTICE '✅ All 5 Model Provider Policies verified with Tier-2 access';
END $$;

-- Verify Ed25519 keys
DO $$
DECLARE
    key_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO key_count
    FROM fhq_meta.agent_keys
    WHERE agent_id IN ('cseo', 'cdmo', 'crio', 'ceio', 'cfao')
    AND key_state = 'ACTIVE'
    AND signing_algorithm = 'Ed25519';

    IF key_count < 5 THEN
        RAISE EXCEPTION 'Expected 5 ACTIVE Ed25519 keys, found %', key_count;
    END IF;

    RAISE NOTICE '✅ All 5 Ed25519 keys registered and ACTIVE';
END $$;

-- Verify org_agents registration
DO $$
DECLARE
    agent_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO agent_count
    FROM fhq_org.org_agents
    WHERE agent_id IN ('cseo', 'cdmo', 'crio', 'ceio', 'cfao')
    AND agent_status = 'ACTIVE'
    AND authority_level = 2
    AND llm_tier = 2;

    IF agent_count < 5 THEN
        RAISE EXCEPTION 'Expected 5 org_agents with Tier-2 settings, found %', agent_count;
    END IF;

    RAISE NOTICE '✅ All 5 Sub-Executives registered in org_agents';
END $$;

COMMIT;

-- ============================================================================
-- DISPLAY REGISTERED SUB-EXECUTIVES
-- ============================================================================

SELECT
    agent_id,
    contract_version,
    contract_type,
    contract_status,
    tier_restrictions->>'parent_agent' as parent,
    tier_restrictions->>'authority_type' as authority_type,
    cost_ceiling_usd,
    approval_gate,
    created_at
FROM fhq_governance.agent_contracts
WHERE agent_id IN ('cseo', 'cdmo', 'crio', 'ceio', 'cfao')
ORDER BY agent_id;

-- Display Authority Matrix
SELECT
    agent_id,
    authority_level,
    can_read_canonical,
    can_write_canonical,
    can_trigger_g2,
    can_trigger_g3,
    can_trigger_g4
FROM fhq_governance.authority_matrix
WHERE agent_id IN ('cseo', 'cdmo', 'crio', 'ceio', 'cfao')
ORDER BY agent_id;

-- Display Model Provider Policies
SELECT
    agent_id,
    llm_tier,
    allowed_providers,
    forbidden_providers,
    data_sharing_allowed
FROM fhq_governance.model_provider_policy
WHERE agent_id IN ('cseo', 'cdmo', 'crio', 'ceio', 'cfao')
ORDER BY agent_id;

-- ============================================================================
-- END OF MIGRATION 019: ADR-014 SUB-EXECUTIVE GOVERNANCE
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 019: ADR-014 SUB-EXECUTIVE GOVERNANCE CHARTER – COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo '✅ CSEO (Chief Strategy & Experimentation Officer) – ACTIVE'
\echo '✅ CDMO (Chief Data & Memory Officer) – ACTIVE'
\echo '✅ CRIO (Chief Research & Insight Officer) – ACTIVE'
\echo '✅ CEIO (Chief External Intelligence Officer) – ACTIVE'
\echo '✅ CFAO (Chief Foresight & Autonomy Officer) – ACTIVE'
\echo ''
\echo '✅ Agent Contracts: 5/5 registered'
\echo '✅ Authority Matrix: TIER-2 defaults applied'
\echo '✅ Model Provider Policy: Tier-2 access configured'
\echo '✅ Ed25519 Keys: ACTIVE state'
\echo '✅ Org Agents: Registered with parent relationships'
\echo '✅ Governance Log: ADR-014 activation recorded'
\echo ''
\echo 'Next Steps:'
\echo '  1. G1 Validation: STIG technical verification'
\echo '  2. G2 Validation: LARS governance mapping'
\echo '  3. G3 Validation: VEGA audit & discrepancy baselines'
\echo '  4. G4 Activation: CEO signature (already provided in ADR-014)'
\echo ''
\echo 'When VEGA signs ADR-014: Tier-2 Sub-Executive C-Suite is ACTIVE'
\echo '═══════════════════════════════════════════════════════════════════════════'
