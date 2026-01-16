-- Migration 264: IoS-016 Economic Calendar Registry Registration
-- CEO Directive: Register IoS-016 per FjordHQ Constitutional Standards
-- Classification: GOVERNANCE-CRITICAL
-- Executed by: STIG (EC-003_2026_PRODUCTION)

BEGIN;

-- ============================================================================
-- 264.1: Register IoS-016 in ios_registry
-- ============================================================================

INSERT INTO fhq_meta.ios_registry (
    ios_id,
    title,
    description,
    version,
    status,
    owner_role,
    governing_adrs,
    dependencies,
    content_hash,
    created_at,
    updated_at,
    experimental_classification,
    risk_multiplier,
    immutability_level,
    canonical,
    modification_requires,
    governance_state
) VALUES (
    'IoS-016',
    'IoS-016 Economic Calendar & Temporal Governance',
    'FjordHQ canonical economic calendar and temporal governance system. Provides single source of truth for market-moving events across all asset classes. Enables event-aware learning by tagging forecasts with event proximity context. Separates model error from event-driven volatility in Brier score analysis. Supports UMA Learning Velocity Index (LVI) with clean learning windows. MBB++ Investor-Grade Standard with 9 CEO refinements.',
    '2026.G1.MBB++',
    'G1_TECHNICAL',
    'LINE',
    ARRAY['ADR-001', 'ADR-002', 'ADR-004', 'ADR-008', 'ADR-012', 'ADR-013', 'ADR-016', 'ADR-020'],
    ARRAY['IoS-001', 'IoS-003', 'IoS-005', 'IoS-010'],
    'd8674368ae96e7f16ccd73b0cc047f49272dc309ded1ec518da08dc767ec2fd6',
    NOW(),
    NOW(),
    'PRODUCTION_CANDIDATE',
    1.0,
    'GOVERNANCE_CONTROLLED',
    true,
    'CEO_OR_VEGA',
    'G1_COMPLETE'
)
ON CONFLICT (ios_id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    status = EXCLUDED.status,
    owner_role = EXCLUDED.owner_role,
    governing_adrs = EXCLUDED.governing_adrs,
    dependencies = EXCLUDED.dependencies,
    content_hash = EXCLUDED.content_hash,
    updated_at = NOW(),
    experimental_classification = EXCLUDED.experimental_classification,
    risk_multiplier = EXCLUDED.risk_multiplier,
    immutability_level = EXCLUDED.immutability_level,
    canonical = EXCLUDED.canonical,
    modification_requires = EXCLUDED.modification_requires,
    governance_state = EXCLUDED.governance_state;

-- ============================================================================
-- 264.2: Log to ios_audit_log
-- ============================================================================

INSERT INTO fhq_meta.ios_audit_log (
    audit_id,
    ios_id,
    event_type,
    event_timestamp,
    actor,
    gate_level,
    event_data,
    evidence_hash
) VALUES (
    gen_random_uuid(),
    'IoS-016',
    'IOS_REGISTERED',
    NOW(),
    'STIG',
    'G1',
    jsonb_build_object(
        'registration_type', 'NEW_IOS',
        'governance_gate', 'G1',
        'g1_status', 'VALIDATED',
        'schema_created', 'fhq_calendar',
        'tables_created', 11,
        'test_coverage', '100% on QG-F1 through QG-F4',
        'owner', 'LINE (EC-005)',
        'operator', 'CEIO (EC-009)',
        'infrastructure', 'STIG (EC-003)',
        'data_steward', 'CDMO (EC-007)',
        'ceo_approval', 'Phase 1 Foundation APPROVED (2026-01-16)',
        'mbb_version', 'MBB++ v3.0 with 9 CEO refinements',
        'document_path', '02_IOS/IoS-016_Economic_Calendar_and_Temporal_Governance.md',
        'evidence_path', '03_FUNCTIONS/evidence/CEO_DIR_2026_IOS016_G1_TECHNICAL_VALIDATION.json'
    ),
    'd8674368ae96e7f16ccd73b0cc047f49272dc309ded1ec518da08dc767ec2fd6'
);

-- ============================================================================
-- 264.3: Log to governance_actions_log
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
    'IOS_REGISTRATION',
    'IoS-016',
    'INSTITUTIONAL_OPERATING_STANDARD',
    'STIG',
    NOW(),
    'REGISTERED',
    'IoS-016 Economic Calendar & Temporal Governance registered in fhq_meta.ios_registry per FjordHQ Constitutional standards. G1 Technical Validation PASSED. Canonical status granted. LINE owns temporal governance, CEIO operates ingestion.',
    jsonb_build_object(
        'migration', '264_ios016_registry_registration.sql',
        'ios_version', '2026.G1.MBB++',
        'canonical', true,
        'governing_adrs', ARRAY['ADR-001', 'ADR-002', 'ADR-004', 'ADR-008', 'ADR-012', 'ADR-013', 'ADR-016', 'ADR-020'],
        'dependencies', ARRAY['IoS-001', 'IoS-003', 'IoS-005', 'IoS-010'],
        'schema', 'fhq_calendar',
        'immutability_level', 'GOVERNANCE_CONTROLLED',
        'modification_requires', 'CEO_OR_VEGA'
    ),
    'STIG',
    NOW()
);

-- ============================================================================
-- 264.4: Add to ios_version_history
-- ============================================================================

INSERT INTO fhq_meta.ios_version_history (
    history_id,
    ios_id,
    version,
    previous_version,
    change_type,
    change_summary,
    changed_by,
    changed_at,
    content_hash
) VALUES (
    gen_random_uuid(),
    'IoS-016',
    '2026.G1.MBB++',
    NULL,
    'INITIAL_REGISTRATION',
    'Initial registration after G1 Technical Validation. MBB++ Investor-Grade Standard v3.0 with 9 CEO refinements. Schema fhq_calendar created with 11 tables. Full test coverage on QG-F1 through QG-F4. Pending: G2 Governance Review, G3 Audit Verification, G3.5 Shadow Mode, G4 CEO Activation.',
    'STIG',
    NOW(),
    'd8674368ae96e7f16ccd73b0cc047f49272dc309ded1ec518da08dc767ec2fd6'
);

COMMIT;

-- ============================================================================
-- Verification
-- ============================================================================
-- SELECT ios_id, title, version, status, canonical, governance_state
-- FROM fhq_meta.ios_registry
-- WHERE ios_id = 'IoS-016';
