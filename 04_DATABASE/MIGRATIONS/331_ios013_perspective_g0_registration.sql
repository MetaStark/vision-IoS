-- ============================================================================
-- MIGRATION 331: IoS-013-Perspective G0 Registration
-- ============================================================================
-- Directive: ADR-004 G0 Protocol
-- Classification: GOVERNANCE-CRITICAL
-- Date: 2026-01-20
-- Executed by: STIG (EC-003_2026_PRODUCTION)
--
-- Purpose: Register IoS-013-Perspective (Cognitive Signal Weighting & Decision
--          Context Engine) as the canonical successor to IoS-013.HCP-LAB
--
-- ADR-004 G0 Protocol:
--   G0 = Draft submission for governance review
--   Requires: Document exists, hash verified, dependencies declared
--   Next: G1 (Technical Validation), G2 (LARS+VEGA Signing)
-- ============================================================================

BEGIN;

-- Step 1: Update existing IoS-013 record with canonical data
UPDATE fhq_meta.ios_registry
SET
    title = 'Cognitive Signal Weighting & Decision Context Engine',
    description = 'IoS-013-Perspective er FjordHQs offisielle komponent for å konvertere signaler til beslutningskraft. Den samler, vekter og forklarer sanntidsdata fra hele signalsystemet og skaper et kognitivt tolkningsgrunnlag som kan brukes av både autonome agenter og mennesker. Dette er perspektivet som avgjør hvilken strategi som skal få tillit. Supersedes IoS-013.HCP-LAB.',
    version = 'G0',
    status = 'G0_PENDING',
    owner_role = 'STIG',
    governing_adrs = ARRAY['ADR-001', 'ADR-003', 'ADR-004', 'ADR-005', 'ADR-007', 'ADR-013', 'ADR-014', 'ADR-016', 'ADR-018'],
    dependencies = ARRAY['IoS-002', 'IoS-003', 'IoS-005', 'IoS-006', 'IoS-007', 'IoS-010', 'IoS-016'],
    content_hash = '1afa5eed6f0234c1b2c9207e472c4051fec69abc9fd7044b10794487516708fb',
    updated_at = NOW(),
    governance_state = 'G0_REGISTERED',
    experimental_classification = 'PERSPECTIVE_ENGINE',
    modification_requires = 'G2_VEGA_LARS',
    immutability_level = 'G0_MUTABLE',
    canonical = true
WHERE ios_id = 'IoS-013';

-- Step 2: Log the G0 registration event
INSERT INTO fhq_meta.ios_audit_log (
    ios_id,
    event_type,
    event_description,
    actor,
    directive_ref,
    evidence_hash,
    created_at
) VALUES (
    'IoS-013',
    'G0_REGISTRATION',
    'IoS-013-Perspective registered per ADR-004 G0 protocol. Supersedes IoS-013.HCP-LAB (deprecated). Cognitive Signal Weighting & Decision Context Engine ready for G1 technical validation.',
    'STIG (EC-003_2026_PRODUCTION)',
    'ADR-004',
    '1afa5eed6f0234c1b2c9207e472c4051fec69abc9fd7044b10794487516708fb',
    NOW()
);

-- Step 3: Create evidence record
INSERT INTO fhq_meta.cognitive_engine_evidence (
    evidence_id,
    engine_id,
    engine_name,
    invocation_type,
    decision_rationale,
    cost_usd,
    created_at
) VALUES (
    gen_random_uuid(),
    'EC-003',
    'STIG',
    'IOS_G0_REGISTRATION',
    'IoS-013-Perspective G0 registration completed per ADR-004. Document hash: 1afa5eed6f0234c1b2c9207e472c4051fec69abc9fd7044b10794487516708fb. File: 02_IOS/IoS-013-Perspective_2026.md. Dependencies: IoS-002, IoS-003, IoS-005, IoS-006, IoS-007, IoS-010, IoS-016. Next gate: G1 Technical Validation by STIG.',
    0.00,
    NOW()
);

COMMIT;

-- Verification query (run after migration)
-- SELECT ios_id, title, version, status, governance_state, owner_role, governing_adrs
-- FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-013';
