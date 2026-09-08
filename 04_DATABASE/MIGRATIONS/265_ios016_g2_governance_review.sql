-- Migration 265: IoS-016 G2 Governance Review
-- CEO Directive: G2 Governance Review for IoS-016 Economic Calendar
-- Classification: GOVERNANCE-CRITICAL
-- Executed by: STIG (EC-003_2026_PRODUCTION)

BEGIN;

-- ============================================================================
-- G2-A: VEGA Lineage Model Review
-- ============================================================================
-- Verified: 13 tables in fhq_calendar schema
-- Verified: 7 FK relationships creating proper data lineage chain:
--   1. calendar_events.event_type_code -> event_type_registry.event_type_code
--   2. event_asset_mapping.event_type_code -> event_type_registry.event_type_code
--   3. ingestion_batches.provider_id -> calendar_provider_state.provider_id
--   4. provider_tos_archive.provider_id -> calendar_provider_state.provider_id
--   5. source_conflict_log.canonical_event_id -> calendar_events.event_id
--   6. staging_events.canonical_event_id -> calendar_events.event_id
--   7. unexplained_volatility_flags.resolution_event_id -> calendar_events.event_id
--
-- Data Flow Lineage:
--   External Providers -> staging_events -> calendar_events (canonical)
--                                        -> source_conflict_log (ADR-013)
--                                        -> unexplained_volatility_flags (ghost detection)

-- ============================================================================
-- G2-B: ADR Compliance Verification
-- ============================================================================
-- All 8 governing ADRs verified as ACTIVE:
--   ADR-001: System Charter - ACTIVE
--   ADR-002: Audit and Error Reconciliation Charter - ACTIVE
--   ADR-004: Change Gates Architecture (G0-G4) - ACTIVE
--   ADR-008: Cryptographic Key Management and Rotation - ACTIVE
--   ADR-012: Economic Safety Architecture - ACTIVE
--   ADR-013: Canonical ADR Governance and One-True-Source - ACTIVE
--   ADR-016: DEFCON Circuit Breaker Protocol - ACTIVE
--   ADR-020: Autonomous Cognitive Intelligence - ACTIVE

-- Create G2 compliance verification record
CREATE TABLE IF NOT EXISTS fhq_calendar.g2_adr_compliance (
    compliance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adr_id TEXT NOT NULL,
    ios_id TEXT NOT NULL,
    compliance_status TEXT NOT NULL CHECK (compliance_status IN ('COMPLIANT', 'PARTIAL', 'NON_COMPLIANT', 'DEFERRED')),
    verification_method TEXT NOT NULL,
    verification_notes TEXT,
    verified_by TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO fhq_calendar.g2_adr_compliance (adr_id, ios_id, compliance_status, verification_method, verification_notes, verified_by) VALUES
('ADR-001', 'IoS-016', 'COMPLIANT', 'REGISTRY_CHECK', 'System Charter verified. LINE owns temporal governance, CEIO operates ingestion.', 'STIG'),
('ADR-002', 'IoS-016', 'COMPLIANT', 'SCHEMA_AUDIT', 'Audit tables present: ingestion_batches with hash chain, source_conflict_log for decisions.', 'STIG'),
('ADR-004', 'IoS-016', 'COMPLIANT', 'GOVERNANCE_LOG', 'G0 SUBMITTED, G1 VALIDATED, G2 IN_PROGRESS. Full gate cycle followed.', 'STIG'),
('ADR-008', 'IoS-016', 'PARTIAL', 'KEY_REGISTRY', 'ceio_signature field exists but nullable. CEIO key registration deferred to G3.', 'STIG'),
('ADR-012', 'IoS-016', 'COMPLIANT', 'PROVIDER_CONFIG', 'API waterfall respected: FRED/yfinance (Tier-1), CEIO calendars (Tier-2), premium APIs (Tier-3).', 'STIG'),
('ADR-013', 'IoS-016', 'COMPLIANT', 'CONFLICT_LOG', 'One-True-Source enforced via calendar_events.is_canonical. resolve_source_conflict() tested.', 'STIG'),
('ADR-016', 'IoS-016', 'COMPLIANT', 'SCHEMA_DESIGN', 'Schema respects DEFCON states. No execution authority in calendar tables.', 'STIG'),
('ADR-020', 'IoS-016', 'COMPLIANT', 'INTEGRATION_DESIGN', 'Calendar feeds UMA learning via event tagging and LVI_adjusted computation.', 'STIG');

-- ============================================================================
-- G2-C: EC Authority Boundaries Confirmation
-- ============================================================================
-- Verified authority boundaries per agent_mandates:
--   LINE: executive, EXECUTION authority (parent: LARS) - owns temporal governance
--   CEIO: subexecutive, OPERATIONAL authority (parent: STIG) - operates calendar ingestion
--   CDMO: subexecutive, DATASET authority (parent: STIG) - data steward for metadata
--   STIG: executive, INFRASTRUCTURE authority (parent: LARS) - schema enforcement
--   VEGA: constitutional, GOVERNANCE authority (parent: CEO) - auditor

CREATE TABLE IF NOT EXISTS fhq_calendar.g2_ec_authority_map (
    authority_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ios_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    calendar_role TEXT NOT NULL,
    authority_type TEXT NOT NULL,
    mandate_verified BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO fhq_calendar.g2_ec_authority_map (ios_id, agent_name, calendar_role, authority_type, mandate_verified, notes) VALUES
('IoS-016', 'LINE', 'TEMPORAL_GOVERNANCE_OWNER', 'EXECUTION', true, 'EC-005: Owns system clock, event scheduling, temporal integrity'),
('IoS-016', 'CEIO', 'CALENDAR_OPERATOR', 'OPERATIONAL', true, 'EC-009: External calendar data ingestion via API waterfall'),
('IoS-016', 'CDMO', 'DATA_STEWARD', 'DATASET', true, 'EC-007: Metadata definitions, quality standards enforcement'),
('IoS-016', 'STIG', 'INFRASTRUCTURE', 'INFRASTRUCTURE', true, 'EC-003: Schema creation, migration execution, security'),
('IoS-016', 'VEGA', 'AUDITOR', 'GOVERNANCE', true, 'EC-001: Lineage verification, attestation, compliance audit');

-- ============================================================================
-- G2-D: TOS Archive Verification
-- ============================================================================
-- Structure verified:
--   - provider_tos_archive table exists with proper schema
--   - calendar_provider_state has TOS fields (tos_snapshot_hash, tos_permitted_use, etc.)
--   - 5 providers configured: FRED, YAHOO_FINANCE, INVESTING_COM, TRADINGECONOMICS, ALPHA_VANTAGE
--
-- Status: TOS fields currently NULL (expected)
-- Rationale: TOS capture happens during provider integration (G3/G4)
-- Mitigation: verify_provider_tos() function blocks ingestion without valid TOS

CREATE TABLE IF NOT EXISTS fhq_calendar.g2_tos_verification (
    verification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name TEXT NOT NULL,
    tos_structure_exists BOOLEAN NOT NULL,
    tos_populated BOOLEAN NOT NULL,
    tos_capture_phase TEXT NOT NULL,
    verification_notes TEXT,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO fhq_calendar.g2_tos_verification (provider_name, tos_structure_exists, tos_populated, tos_capture_phase, verification_notes) VALUES
('FRED', true, false, 'G3_INTEGRATION', 'Public domain data, TOS documentation for audit trail'),
('YAHOO_FINANCE', true, false, 'G3_INTEGRATION', 'API TOS capture required before production ingestion'),
('INVESTING_COM', true, false, 'G3_INTEGRATION', 'Web scraping TOS review required'),
('TRADINGECONOMICS', true, false, 'G3_INTEGRATION', 'API TOS capture required'),
('ALPHA_VANTAGE', true, false, 'G3_INTEGRATION', 'Premium API TOS documentation required');

-- ============================================================================
-- G2-E: Update IoS-016 Registry Status
-- ============================================================================

UPDATE fhq_meta.ios_registry
SET
    status = 'G2_VALIDATED',
    governance_state = 'G2_COMPLETE',
    version = '2026.G2.MBB++',
    updated_at = NOW()
WHERE ios_id = 'IoS-016';

-- ============================================================================
-- G2-F: Audit Log Entry
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
    'G2_GOVERNANCE_REVIEW',
    NOW(),
    'STIG',
    'G2',
    jsonb_build_object(
        'g2a_lineage_review', 'PASS - 7 FK relationships verified',
        'g2b_adr_compliance', 'PASS - 8/8 ADRs verified (1 PARTIAL: ADR-008)',
        'g2c_ec_boundaries', 'PASS - 5 agents with verified mandates',
        'g2d_tos_verification', 'STRUCTURE_VERIFIED - Population deferred to G3',
        'overall_status', 'G2_VALIDATED',
        'technical_debt', ARRAY['ADR-008 CEIO signature deferred to G3', 'TOS capture deferred to G3'],
        'vega_attestation', 'PENDING_G3'
    ),
    'd8674368ae96e7f16ccd73b0cc047f49272dc309ded1ec518da08dc767ec2fd6'
);

-- ============================================================================
-- G2-G: Governance Actions Log
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
    'G2_GOVERNANCE_REVIEW',
    'IoS-016',
    'INSTITUTIONAL_OPERATING_STANDARD',
    'STIG',
    NOW(),
    'VALIDATED',
    'G2 Governance Review PASSED. Lineage model verified (7 FKs). ADR compliance verified (8/8, 1 partial). EC authority boundaries confirmed (5 agents). TOS structure verified (population deferred to G3).',
    jsonb_build_object(
        'migration', '265_ios016_g2_governance_review.sql',
        'adr_compliance_count', '8/8',
        'adr_partial', 'ADR-008 (CEIO signature)',
        'ec_agents_verified', 5,
        'fk_relationships', 7,
        'providers_configured', 5,
        'tos_status', 'STRUCTURE_VERIFIED',
        'next_gate', 'G3 Audit Verification',
        'vega_attestation_pending', true
    ),
    'STIG',
    NOW()
);

-- ============================================================================
-- G2-H: Version History
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
    '2026.G2.MBB++',
    '2026.G1.MBB++',
    'GOVERNANCE_GATE',
    'G2 Governance Review completed. Lineage model verified. ADR compliance confirmed (8 ADRs, 1 partial). EC authority boundaries mapped. TOS structure verified, population deferred to G3. Ready for G3 Audit Verification.',
    'STIG',
    NOW(),
    'd8674368ae96e7f16ccd73b0cc047f49272dc309ded1ec518da08dc767ec2fd6'
);

COMMIT;

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- SELECT * FROM fhq_calendar.g2_adr_compliance WHERE ios_id = 'IoS-016';
-- SELECT * FROM fhq_calendar.g2_ec_authority_map WHERE ios_id = 'IoS-016';
-- SELECT * FROM fhq_calendar.g2_tos_verification;
-- SELECT ios_id, status, governance_state, version FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-016';
