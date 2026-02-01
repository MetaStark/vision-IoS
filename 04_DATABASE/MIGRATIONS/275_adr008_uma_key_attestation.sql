-- Migration 275: ADR-008 UMA Key Attestation Completion
-- CEO Post-G3 Directive 3.1 Verification
-- Date: 2026-01-17
-- Author: STIG
-- Purpose: Formally attest UMA Ed25519 key registration for calibration operations

-- ============================================================================
-- ADR-008 COMPLIANCE VERIFICATION
-- ============================================================================
-- UMA key was registered on 2026-01-16T18:41:14Z
-- Public Key: 7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6
-- Fingerprint: 2fd377f9be70cea9
-- This migration creates the formal VEGA attestation for court-proof compliance

-- Step 1: Create VEGA attestation for UMA key
INSERT INTO fhq_governance.vega_attestations (
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
    constitutional_basis
) VALUES (
    'AGENT_KEY',
    '7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6',
    'v1',
    'ADR_008_KEY_REGISTRATION',
    'ATTESTED',
    NOW(),
    '57abb8de688fc2405cb48573eb0aae5ac4d1780c04e2a1bd264901b837142979ebc050395f973452f8364260cd2ce8644a626f8fb83c596c6b70dd881e585203',
    '7c71b6356827f270200cc3b870b8c8d33b72eca77d5b87145c377812705515c9',
    true,
    jsonb_build_object(
        'agent_id', 'UMA',
        'key_fingerprint', '2fd377f9be70cea9',
        'key_type', 'ED25519_SIGNING',
        'original_registration', '2026-01-16T18:41:14Z',
        'compliance_verification', 'Day 17 Post-G3 audit',
        'ceo_directive', 'CEO Post-G3 Directive 3.1',
        'placeholder_replaced', 'PLACEHOLDER_PUBKEY_UMA',
        'key_purposes', ARRAY['Governance Attestation', 'Inter-Agent Authentication', 'Learning Artifact Signing']
    ),
    'ADR-008',
    'ADR-008 Agent Key Management. UMA key verified active and ready for calibration signing.'
)
ON CONFLICT DO NOTHING;

-- Step 2: Update agent_keys to link attestation
UPDATE fhq_meta.agent_keys
SET vega_attestation_id = (
    SELECT attestation_id FROM fhq_governance.vega_attestations
    WHERE target_type = 'AGENT_KEY'
    AND target_id = '7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6'
    ORDER BY attestation_timestamp DESC LIMIT 1
),
vega_attestation_timestamp = NOW()
WHERE agent_id = 'UMA';

-- Step 3: Log governance action for verification
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'ADR_008_VERIFICATION',
    'UMA',
    'AGENT_KEY',
    'STIG',
    'VERIFIED',
    'CEO Post-G3 Directive 3.1 compliance verification. UMA Ed25519 key confirmed active and VEGA-attested.',
    jsonb_build_object(
        'public_key_hex', '7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6',
        'key_fingerprint', '2fd377f9be70cea9',
        'original_registration', '2026-01-16T18:41:14Z',
        'verification_date', '2026-01-17',
        'directive', 'CEO Post-G3 Directive 3.1',
        'status', 'CALIBRATION_READY'
    )
);

-- Verification query
DO $$
DECLARE
    key_count INTEGER;
    attestation_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO key_count
    FROM fhq_meta.agent_keys
    WHERE agent_id = 'UMA' AND key_state = 'ACTIVE';

    SELECT COUNT(*) INTO attestation_count
    FROM fhq_governance.vega_attestations
    WHERE target_type = 'AGENT_KEY'
    AND attestation_data->>'agent_id' = 'UMA';

    IF key_count = 1 AND attestation_count >= 1 THEN
        RAISE NOTICE 'ADR-008 UMA Key Verification: PASSED';
        RAISE NOTICE 'Active keys: %, Attestations: %', key_count, attestation_count;
    ELSE
        RAISE WARNING 'ADR-008 UMA Key Verification: CHECK REQUIRED';
    END IF;
END $$;
