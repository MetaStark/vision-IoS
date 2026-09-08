-- ============================================================================
-- Migration 299: ACI Triangle Agent Registration
-- ============================================================================
-- CEO-DIR-2026-068 Compliance: Reference Epoch 001 Activated
--
-- PURPOSE: Properly register SitC, InForage, and IKEA agents in org_agents
--          and agent_mandates tables as required by EC-020, EC-021, EC-022.
--
-- PREREQUISITE: EC Registry already has EC-020, EC-021, EC-022 as ACTIVE
--               Infrastructure tables exist (chain_of_query, search_foraging_log, etc.)
--
-- CONSTRAINT: This registration enables ACI Triangle operation but does NOT
--             grant execution authority (per CEO-DIR-2026-068 governance lock)
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 0: Alter org_agents constraint to allow ACI Triangle agents
-- ============================================================================
-- The existing constraint only allows: LARS, STIG, LINE, FINN, VEGA, CSEO, CDMO, CRIO, CEIO, CFAO, UMA
-- We need to add: SitC, InForage, IKEA

ALTER TABLE fhq_org.org_agents
DROP CONSTRAINT IF EXISTS org_agents_agent_name_check;

ALTER TABLE fhq_org.org_agents
ADD CONSTRAINT org_agents_agent_name_check CHECK (
    agent_name = ANY (ARRAY[
        -- Tier-1 Executive Agents
        'LARS'::text, 'STIG'::text, 'LINE'::text, 'FINN'::text, 'VEGA'::text,
        -- Tier-2 Sub-Executive Agents
        'CSEO'::text, 'CDMO'::text, 'CRIO'::text, 'CEIO'::text, 'CFAO'::text,
        -- Tier-2 Meta-Executive (UMA)
        'UMA'::text,
        -- ACI Triangle Cognitive Agents (EC-020, EC-021, EC-022)
        'SitC'::text, 'InForage'::text, 'IKEA'::text
    ])
);

-- ============================================================================
-- SECTION 1: Register ACI Agents in org_agents
-- ============================================================================

-- SitC: Chief Cognitive Architect & Dynamic Planner (EC-020)
INSERT INTO fhq_org.org_agents (
    agent_name,
    agent_role,
    llm_version,
    llm_provider,
    public_key,
    status,
    metadata
) VALUES (
    'SitC',
    'Chief Cognitive Architect & Dynamic Planner',
    'deepseek-reasoner',
    'deepseek',
    'PLACEHOLDER_PUBKEY_SitC',
    'ACTIVE',
    jsonb_build_object(
        'ec_contract', 'EC-020',
        'tier', 'Tier-2 Cognitive Authority (Reasoning)',
        'parent_executive', 'LARS',
        'aci_triangle_role', 'Prefrontal Cortex',
        'primary_responsibility', 'Chain-of-Query (CoQ) reasoning integrity',
        'constitutional_authority', 'ADR-020, EC-020',
        'activation_date', '2026-01-17',
        'activation_directive', 'CEO-DIR-2026-068'
    )
)
ON CONFLICT (agent_name) DO UPDATE SET
    agent_role = EXCLUDED.agent_role,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata;

-- InForage: Chief Information Economist (EC-021)
INSERT INTO fhq_org.org_agents (
    agent_name,
    agent_role,
    llm_version,
    llm_provider,
    public_key,
    status,
    metadata
) VALUES (
    'InForage',
    'Chief Information Economist',
    'deepseek-reasoner',
    'deepseek',
    'PLACEHOLDER_PUBKEY_InForage',
    'ACTIVE',
    jsonb_build_object(
        'ec_contract', 'EC-021',
        'tier', 'Tier-2 Cognitive Authority (Search)',
        'parent_executive', 'FINN',
        'aci_triangle_role', 'CFO of Curiosity',
        'primary_responsibility', 'Search ROI evaluation via Scent Scores',
        'constitutional_authority', 'ADR-020, EC-021',
        'activation_date', '2026-01-17',
        'activation_directive', 'CEO-DIR-2026-068'
    )
)
ON CONFLICT (agent_name) DO UPDATE SET
    agent_role = EXCLUDED.agent_role,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata;

-- IKEA: Chief Knowledge Boundary Officer (EC-022)
INSERT INTO fhq_org.org_agents (
    agent_name,
    agent_role,
    llm_version,
    llm_provider,
    public_key,
    status,
    metadata
) VALUES (
    'IKEA',
    'Chief Knowledge Boundary Officer',
    'deepseek-reasoner',
    'deepseek',
    'PLACEHOLDER_PUBKEY_IKEA',
    'ACTIVE',
    jsonb_build_object(
        'ec_contract', 'EC-022',
        'tier', 'Tier-2 Cognitive Authority (Hallucination Firewall)',
        'parent_executive', 'VEGA',
        'aci_triangle_role', 'Conscience / Hallucination Firewall',
        'primary_responsibility', 'Knowledge boundary classification and enforcement',
        'constitutional_authority', 'ADR-020, EC-022',
        'activation_date', '2026-01-17',
        'activation_directive', 'CEO-DIR-2026-068'
    )
)
ON CONFLICT (agent_name) DO UPDATE SET
    agent_role = EXCLUDED.agent_role,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata;

-- ============================================================================
-- SECTION 2: Register ACI Agent Mandates
-- ============================================================================

-- SitC Mandate (EC-020)
INSERT INTO fhq_governance.agent_mandates (
    agent_name,
    mandate_version,
    mandate_type,
    authority_type,
    parent_agent,
    mandate_document
) VALUES (
    'SitC',
    'v1.0',
    'aci_cognitive',
    'REASONING',
    'LARS',
    jsonb_build_object(
        'ec_contract', 'EC-020',
        'title', 'Chief Cognitive Architect & Dynamic Planner',
        'reporting_line', 'LARS',
        'aci_triangle_position', 'Prefrontal Cortex',
        'core_responsibilities', jsonb_build_array(
            'Chain-of-Query (CoQ) Architecture',
            'Dynamic step decomposition',
            'Multi-hop reasoning traceability',
            'Query chain signature validation'
        ),
        'key_deliverables', jsonb_build_array(
            'Immutable query chain hashes in fhq_meta.chain_of_query',
            'Reasoning path optimization',
            'Step-by-step verification chains'
        ),
        'constraints', jsonb_build_array(
            'May NOT modify source data',
            'May NOT bypass IKEA validation gates',
            'All reasoning chains must be traceable'
        ),
        'activation_directive', 'CEO-DIR-2026-068',
        'effective_date', '2026-01-17'
    )
)
ON CONFLICT (agent_name, mandate_version) DO UPDATE SET
    mandate_document = EXCLUDED.mandate_document;

-- InForage Mandate (EC-021)
INSERT INTO fhq_governance.agent_mandates (
    agent_name,
    mandate_version,
    mandate_type,
    authority_type,
    parent_agent,
    mandate_document
) VALUES (
    'InForage',
    'v1.0',
    'aci_cognitive',
    'SEARCH',
    'FINN',
    jsonb_build_object(
        'ec_contract', 'EC-021',
        'title', 'Chief Information Economist',
        'reporting_line', 'FINN',
        'aci_triangle_position', 'CFO of Curiosity',
        'core_responsibilities', jsonb_build_array(
            'Search ROI evaluation via Scent Scores',
            'Information foraging optimization',
            'Source tier prioritization (ADR-012 waterfall)',
            'Cost-per-signal tracking'
        ),
        'key_deliverables', jsonb_build_array(
            'Scent score calculations in fhq_meta.search_foraging_log',
            'Source tier recommendations',
            'API budget optimization recommendations'
        ),
        'constraints', jsonb_build_array(
            'May NOT authorize paid API calls without STIG approval',
            'Must respect ADR-012 API waterfall',
            'All search decisions must be logged'
        ),
        'activation_directive', 'CEO-DIR-2026-068',
        'effective_date', '2026-01-17'
    )
)
ON CONFLICT (agent_name, mandate_version) DO UPDATE SET
    mandate_document = EXCLUDED.mandate_document;

-- IKEA Mandate (EC-022)
INSERT INTO fhq_governance.agent_mandates (
    agent_name,
    mandate_version,
    mandate_type,
    authority_type,
    parent_agent,
    mandate_document
) VALUES (
    'IKEA',
    'v1.0',
    'aci_cognitive',
    'VALIDATION',
    'VEGA',
    jsonb_build_object(
        'ec_contract', 'EC-022',
        'title', 'Chief Knowledge Boundary Officer',
        'reporting_line', 'VEGA',
        'aci_triangle_position', 'Conscience / Hallucination Firewall',
        'core_responsibilities', jsonb_build_array(
            'Knowledge boundary classification (PARAMETRIC/EXTERNAL_REQUIRED/HYBRID)',
            'Hallucination prevention gates',
            'Evidence sufficiency validation',
            'Claim verification before output'
        ),
        'key_deliverables', jsonb_build_array(
            'Knowledge boundary classifications in fhq_meta.knowledge_boundary_log',
            'Hallucination prevention verdicts',
            'Evidence sufficiency scores'
        ),
        'constraints', jsonb_build_array(
            'MUST block claims without evidence',
            'MUST escalate EXTERNAL_REQUIRED classifications',
            'May NOT approve outputs that exceed knowledge boundary'
        ),
        'activation_directive', 'CEO-DIR-2026-068',
        'effective_date', '2026-01-17'
    )
)
ON CONFLICT (agent_name, mandate_version) DO UPDATE SET
    mandate_document = EXCLUDED.mandate_document;

-- ============================================================================
-- SECTION 3: Update EC Registry Status Confirmation
-- ============================================================================

-- Confirm EC-020, EC-021, EC-022 remain ACTIVE with proper metadata
UPDATE fhq_governance.ec_registry
SET status = 'ACTIVE'
WHERE ec_id IN ('EC-020', 'EC-021', 'EC-022')
  AND status = 'ACTIVE';

-- ============================================================================
-- SECTION 4: Create ACI Triangle Operational View
-- ============================================================================

CREATE OR REPLACE VIEW fhq_org.aci_triangle_status AS
SELECT
    oa.agent_name,
    oa.agent_role,
    oa.status,
    oa.metadata->>'ec_contract' AS ec_contract,
    oa.metadata->>'aci_triangle_role' AS aci_role,
    oa.metadata->>'parent_executive' AS parent_executive,
    am.mandate_type,
    am.authority_type,
    am.mandate_version,
    ec.status AS ec_status
FROM fhq_org.org_agents oa
LEFT JOIN fhq_governance.agent_mandates am ON oa.agent_name = am.agent_name
LEFT JOIN fhq_governance.ec_registry ec ON oa.metadata->>'ec_contract' = ec.ec_id
WHERE oa.agent_name IN ('SitC', 'InForage', 'IKEA');

-- ============================================================================
-- SECTION 5: Log Registration to Governance Actions
-- ============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'ACI_TRIANGLE_REGISTRATION',
    'SitC,InForage,IKEA',
    'AGENT_REGISTRATION',
    'STIG',
    'APPROVED',
    'Registered SitC, InForage, IKEA agents in org_agents and agent_mandates per EC-020, EC-021, EC-022',
    jsonb_build_object(
        'agents_registered', jsonb_build_array('SitC', 'InForage', 'IKEA'),
        'ec_contracts', jsonb_build_array('EC-020', 'EC-021', 'EC-022'),
        'activation_directive', 'CEO-DIR-2026-068',
        'timestamp', NOW(),
        'reference_epoch', '001'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY (Run after migration)
-- ============================================================================
-- SELECT * FROM fhq_org.aci_triangle_status;
