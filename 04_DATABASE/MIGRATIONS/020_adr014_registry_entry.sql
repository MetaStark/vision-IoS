-- ============================================================================
-- MIGRATION 020: Register ADR-014 in fhq_meta.adr_registry
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_status,
    adr_type,
    current_version,
    approval_authority,
    effective_date,
    created_by,
    owner,
    governance_tier,
    description,
    affects,
    metadata
) VALUES (
    'ADR-014',
    'Executive Activation & Sub-Executive Governance Charter',
    'APPROVED',
    'CONSTITUTIONAL',
    '2026.PRODUCTION',
    'CEO',
    '2025-11-28',
    'CEO',
    'CEO',
    'Tier-1',
    'Establishes Tier-2 Sub-Executive C-Suite (CSEO, CDMO, CRIO, CEIO, CFAO) with Executive Control Framework (ECF). Defines authority hierarchy, change gate boundaries, canonical protection, LLM-tier binding, and suspension mechanisms for operational AI officers.',
    ARRAY['fhq_governance', 'fhq_org', 'fhq_meta', 'All Tier-2 Agents'],
    jsonb_build_object(
        'authority_chain', 'ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 → ADR-008 → ADR-009 → ADR-010 → ADR-013 → ADR-014',
        'governing_agents', ARRAY['VEGA', 'LARS'],
        'classification', 'GOVERNANCE-CRITICAL',
        'sub_executives', jsonb_build_object(
            'CSEO', jsonb_build_object('parent', 'LARS', 'authority', 'OPERATIONAL'),
            'CDMO', jsonb_build_object('parent', 'STIG', 'authority', 'DATASET'),
            'CRIO', jsonb_build_object('parent', 'FINN', 'authority', 'MODEL'),
            'CEIO', jsonb_build_object('parent', 'STIG+LINE', 'authority', 'OPERATIONAL'),
            'CFAO', jsonb_build_object('parent', 'LARS', 'authority', 'OPERATIONAL')
        ),
        'ecf_version', '1.0',
        'g4_activation_date', '2025-11-28'
    )
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    current_version = EXCLUDED.current_version,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Verify
SELECT adr_id, adr_title, adr_status, adr_type, governance_tier, effective_date
FROM fhq_meta.adr_registry
WHERE adr_id = 'ADR-014';

\echo '✅ ADR-014 registered in fhq_meta.adr_registry'
