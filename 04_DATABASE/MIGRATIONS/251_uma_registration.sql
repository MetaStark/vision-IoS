-- Migration 251: UMA Registration
-- CEO Directive 2026-01-16: Register Universal Meta-Analyst (UMA)
-- Contract: EC-014_2026_PRODUCTION
-- Classification: Tier-2 Meta-Executive (Learning Acceleration & ROI Compression)

BEGIN;

-- ============================================================================
-- Phase 1.1: Agent Registry Entry (fhq_governance.agent_mandates)
-- ============================================================================

INSERT INTO fhq_governance.agent_mandates (
    mandate_id,
    agent_name,
    mandate_version,
    mandate_type,
    authority_type,
    parent_agent,
    mandate_document,
    created_at
) VALUES (
    gen_random_uuid(),
    'UMA',
    '2026.PRODUCTION',
    'Learning Velocity & ROI Acceleration Charter',
    'Tier-2 Meta-Executive',
    'CEO',  -- Primary parent (also reports to STIG, LARS per EC-014)
    jsonb_build_object(
        'core_mandate', 'Compress time from Hypothesis → Validated Signal → Executable ROI',
        'authority_chain', 'ADR-001 → ADR-003 → ADR-004 → ADR-012 → ADR-016 → ADR-020 → ADR-021 → ADR-024 → EC-014',
        'parent_agents', ARRAY['CEO', 'STIG', 'LARS'],
        'primary_metric', 'Learning Velocity Index (LVI)',
        'lvi_formula', 'Validated Executable Signals / Time from Hypothesis → Validation',
        'constraints', jsonb_build_object(
            'cannot_generate_trading_signals', true,
            'cannot_modify_models', true,
            'cannot_override_vega', true,
            'cannot_access_execution_systems', true,
            'cannot_reclassify_canonical_truth', true,
            'cannot_approve_fast_track', true
        ),
        'defcon_behavior', jsonb_build_object(
            'GREEN', 'Full operation',
            'YELLOW', 'Full operation',
            'ORANGE', 'Latency reduction only',
            'RED', 'Analysis-only, no recommendations',
            'BLACK', 'Suspended'
        ),
        'contract_reference', 'EC-014_2026_PRODUCTION',
        'effective_date', '2026-01-16'
    ),
    NOW()
);

-- ============================================================================
-- Phase 1.2: Organization Registry (fhq_org.org_agents)
-- ============================================================================

-- First, extend the agent_name constraint to include UMA
ALTER TABLE fhq_org.org_agents DROP CONSTRAINT IF EXISTS org_agents_agent_name_check;
ALTER TABLE fhq_org.org_agents ADD CONSTRAINT org_agents_agent_name_check
    CHECK (agent_name IN ('LARS', 'STIG', 'LINE', 'FINN', 'VEGA', 'CSEO', 'CDMO', 'CRIO', 'CEIO', 'CFAO', 'UMA'));

INSERT INTO fhq_org.org_agents (
    agent_id,
    agent_name,
    agent_role,
    llm_provider,
    llm_version,
    public_key,
    status,
    metadata,
    created_at
) VALUES (
    gen_random_uuid(),
    'UMA',
    'Universal Meta-Analyst',
    'Anthropic',  -- Tier-2 Reasoning / Meta-Analysis Models
    'Tier-2',
    'PLACEHOLDER_PUBKEY_UMA',  -- Ed25519 key to be attested by VEGA
    'ACTIVE',
    jsonb_build_object(
        'classification', 'Tier-2 Meta-Executive',
        'identity_type', 'Ed25519 (VEGA-attested)',
        'reports_to', ARRAY['CEO', 'STIG', 'LARS'],
        'core_mandate', 'Learn faster than markets change',
        'contract', 'EC-014_2026_PRODUCTION'
    ),
    NOW()
);

-- ============================================================================
-- Phase 1.3: Employment Contract Registry (fhq_governance.ec_registry)
-- ============================================================================

INSERT INTO fhq_governance.ec_registry (
    ec_id,
    title,
    role_type,
    parent_executive,
    effective_date,
    status,
    authority_chain,
    dependencies,
    breach_classes,
    created_at
) VALUES (
    'EC-014',
    'Learning Velocity & ROI Acceleration Charter',
    'Tier-2 Meta-Executive',
    'CEO',
    '2026-01-16',
    'ACTIVE',
    ARRAY['ADR-001', 'ADR-003', 'ADR-004', 'ADR-012', 'ADR-016', 'ADR-020', 'ADR-021', 'ADR-024'],
    ARRAY['EC-003', 'EC-004'],  -- Dependencies: STIG (EC-003), LARS (EC-004)
    jsonb_build_object(
        'Class_A', ARRAY[
            'LVI calculations inconsistent or unverifiable',
            'Synthetic data treated as canonical',
            'Recommendations violating ADR-004 or ADR-012'
        ],
        'Class_B', ARRAY[
            'VEGA discrepancy score exceeds tolerance',
            'Missing evidence references',
            'Unsigned learning recommendations'
        ]
    ),
    NOW()
);

-- ============================================================================
-- Migration Audit Log
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
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'AGENT_REGISTRATION',
    'UMA',
    'TIER_2_EXECUTIVE',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive 2026-01-16: Register UMA (Universal Meta-Analyst) per EC-014_2026_PRODUCTION',
    jsonb_build_object(
        'migration', '251_uma_registration.sql',
        'directive', 'CEO Directive 2026-01-16',
        'contract', 'EC-014_2026_PRODUCTION',
        'tables_modified', ARRAY['agent_mandates', 'org_agents', 'ec_registry'],
        'registration_complete', true
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- SELECT * FROM fhq_governance.agent_mandates WHERE agent_name = 'UMA';
-- SELECT * FROM fhq_org.org_agents WHERE agent_name = 'UMA';
-- SELECT * FROM fhq_governance.ec_registry WHERE ec_id = 'EC-014';
