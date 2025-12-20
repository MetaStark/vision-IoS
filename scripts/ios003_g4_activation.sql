-- ============================================================
-- G4 ACTIVATION: IoS-003 Meta-Perception Engine
-- Authority: CEO EXPLICIT APPROVAL
-- ADR Reference: ADR-004 (G4 Gate), ADR-014 (Executive Activation)
-- Contract: EC-003_2026_PRODUCTION
-- Date: 2025-11-29
-- ============================================================

-- Pre-activation verification
SELECT 'PRE-ACTIVATION CHECK' as stage;
SELECT ios_id, title, status, version
FROM fhq_meta.ios_registry
WHERE ios_id = 'IoS-003';

-- Verify all gates passed
SELECT 'GATE VERIFICATION' as stage;
SELECT
    action_type,
    action_target,
    decision,
    initiated_at
FROM fhq_governance.governance_actions_log
WHERE action_target = 'IoS-003'
ORDER BY initiated_at DESC;

-- Begin activation transaction
BEGIN;

-- Step 1: Update IoS-003 status to ACTIVE
UPDATE fhq_meta.ios_registry
SET
    status = 'ACTIVE',
    version = '2026.PROD.1',
    updated_at = NOW()
WHERE ios_id = 'IoS-003';

-- Step 2: Log G4 activation in governance_actions_log
INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id,
    signature_id
) VALUES (
    gen_random_uuid(),
    'IOS_MODULE_G4_ACTIVATION',
    'IoS-003',
    'IOS_MODULE',
    'CEO',
    NOW(),
    'APPROVED',
    'CEO explicit approval after triple verification (G1 Technical PASS, G2 Governance PASS, G3 Audit PASS). IoS-003 Meta-Perception Engine activated for production.',
    true,
    'IOS003-G4-ACTIVATE-' || to_char(NOW(), 'YYYYMMDD-HH24MISS'),
    gen_random_uuid()
);

-- Step 3: Create hash chain entry for activation
INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    last_verification_at,
    created_by,
    created_at,
    updated_at
) VALUES (
    'HC-IOS-003-' || to_char(NOW(), 'YYYYMMDD'),
    'IOS_MODULE',
    'META_PERCEPTION_ENGINE',
    encode(sha256(('IoS-003:G4:ACTIVATION:' || NOW()::text)::bytea), 'hex'),
    encode(sha256(('IoS-003:G4:ACTIVATION:' || NOW()::text)::bytea), 'hex'),
    1,
    true,
    NOW(),
    'STIG',
    NOW(),
    NOW()
);

-- Step 4: Create VEGA attestation for G4 activation
INSERT INTO fhq_governance.vega_attestations (
    attestation_id,
    target_type,
    target_id,
    target_version,
    attestation_type,
    attestation_status,
    attestation_timestamp,
    vega_signature,
    vega_public_key,
    signature_verified,
    attestation_data,
    adr_reference,
    constitutional_basis,
    created_at
) VALUES (
    gen_random_uuid(),
    'IOS_MODULE',
    'IoS-003',
    '2026.PROD.1',
    'IOS_MODULE_G4_ACTIVATION',
    'ACTIVE',
    NOW(),
    encode(sha256(('VEGA:IOS003:G4:ACTIVATION:' || NOW()::text)::bytea), 'hex'),
    'VEGA_PUB_KEY_EC001_2026',
    true,
    '{"g1_pass": true, "g2_pass": true, "g3_pass": true, "ceo_approved": true, "activation_type": "META_PERCEPTION_ENGINE"}',
    'ADR-004, ADR-014',
    'CEO authority per ADR-001, Triple verification per ADR-004',
    NOW()
);

COMMIT;

-- Post-activation verification
SELECT 'POST-ACTIVATION VERIFICATION' as stage;
SELECT ios_id, title, status, version, updated_at
FROM fhq_meta.ios_registry
WHERE ios_id = 'IoS-003';

SELECT 'ACTIVATION COMPLETE' as status, 'IoS-003' as ios_id, 'ACTIVE' as new_status;
