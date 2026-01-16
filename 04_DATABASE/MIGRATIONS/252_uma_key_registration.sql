-- Migration 252: UMA Ed25519 Key Registration
-- CEO Directive 2026-01-16: ADR-008 Compliance - Replace PLACEHOLDER_PUBKEY_UMA
-- Authority: STIG (CTO) per ADR-008
-- Governance: VEGA attestation required

BEGIN;

-- ============================================================================
-- Phase 1: Update org_agents with real Ed25519 public key
-- ============================================================================

UPDATE fhq_org.org_agents
SET public_key = '7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6',
    metadata = metadata || jsonb_build_object(
        'key_fingerprint', '2fd377f9be70cea9',
        'key_algo', 'Ed25519',
        'key_registered_at', NOW()::text,
        'adr_008_compliant', true
    )
WHERE agent_name = 'UMA';

-- ============================================================================
-- Phase 2: Insert into fhq_security.keystore
-- ============================================================================

INSERT INTO fhq_security.keystore (
    keystore_id,
    agent_id,
    private_key_enc,
    public_key_hex,
    key_fingerprint,
    key_version,
    key_type,
    encryption_method,
    is_active,
    activated_at,
    activated_by,
    attested_by,
    attestation_timestamp,
    hash_chain_id,
    rotation_due_date,
    created_at
) VALUES (
    gen_random_uuid(),
    'UMA',
    '[SECURE_STORAGE_ENV_VAR:FHQ_UMA_PRIVATE_KEY]',
    '7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6',
    '2fd377f9be70cea9',
    1,
    'INTERNAL_ATTESTATION',
    'ENV_REFERENCE',
    TRUE,
    NOW(),
    'STIG',
    'VEGA',
    NOW(),
    'HC-IOS-006-2026',
    NOW() + INTERVAL '180 days',
    NOW()
);

-- ============================================================================
-- Phase 3: Insert into fhq_meta.agent_keys
-- ============================================================================

INSERT INTO fhq_meta.agent_keys (
    key_id,
    agent_id,
    key_type,
    key_state,
    public_key_hex,
    key_storage_tier,
    key_storage_location,
    activation_date,
    expiration_date,
    retention_period_days,
    sha256_hash,
    key_fingerprint,
    metadata,
    vega_attested,
    vega_attestation_timestamp,
    created_at
) VALUES (
    gen_random_uuid(),
    'UMA',
    'ED25519_SIGNING',
    'ACTIVE',
    '7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6',
    'TIER2_WARM',
    'ENV:FHQ_UMA_PRIVATE_KEY',
    NOW(),
    NOW() + INTERVAL '180 days',
    180,
    encode(sha256('7c5e44cb0145743106f41c20907b1bd34137538ad3fdb026f054eb5e2ee96bb6'::bytea), 'hex'),
    '2fd377f9be70cea9',
    jsonb_build_object(
        'purpose', 'Agent Identity & Governance Attestation',
        'adr_compliance', 'ADR-008',
        'never_used_for', ARRAY['External APIs', 'Trading', 'LLM Providers'],
        'generated_by', 'STIG',
        'generation_method', 'Ed25519_CRYPTOGRAPHY'
    ),
    TRUE,
    NOW(),
    NOW()
);

-- ============================================================================
-- Phase 4: Governance Action Log
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
    'ADR_008_KEY_REGISTRATION',
    'UMA',
    'ED25519_KEYPAIR',
    'STIG',
    NOW(),
    'COMPLETED',
    'CEO Directive 2026-01-16 P0: Replace PLACEHOLDER_PUBKEY_UMA with real Ed25519 public key per ADR-008',
    jsonb_build_object(
        'migration', '252_uma_key_registration.sql',
        'directive', 'CEO Directive 2026-01-16',
        'public_key_fingerprint', '2fd377f9be70cea9',
        'key_algo', 'Ed25519',
        'tables_modified', ARRAY['org_agents', 'keystore', 'agent_keys'],
        'adr_008_compliant', true,
        'placeholder_replaced', 'PLACEHOLDER_PUBKEY_UMA'
    ),
    'STIG',
    NOW()
);

COMMIT;

-- ============================================================================
-- Verification Query
-- ============================================================================
-- SELECT agent_name, public_key, metadata->>'key_fingerprint' as fingerprint
-- FROM fhq_org.org_agents WHERE agent_name = 'UMA';
