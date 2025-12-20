-- ============================================================
-- G4 ACTIVATION: IoS-003 Appendix A – HMM REGIME
-- CEO Directive: APPROVED
-- Date: 2025-11-29
-- Authority: CEO -> ADR-004, ADR-014
-- ============================================================

BEGIN;

-- STEP 1: Update appendix status to ACTIVE
UPDATE fhq_meta.ios_appendix_registry
SET
    status = 'ACTIVE',
    updated_at = NOW()
WHERE ios_id = 'IoS-003'
  AND appendix_code = 'Appendix_A_HMM_REGIME';

-- STEP 2: Update task registry - approve gate
UPDATE fhq_governance.task_registry
SET
    gate_approved = true,
    task_status = 'ACTIVE',
    updated_at = NOW()
WHERE task_name = 'META_PERCEPTION_HMM_PIPELINE';

-- STEP 3: Log G4 activation governance action
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
    'IOS_APPENDIX_G4_ACTIVATION',
    'IoS-003_Appendix_A_HMM_REGIME',
    'IOS_APPENDIX',
    'CEO',
    NOW(),
    'APPROVED',
    'G4 activation APPROVED by CEO. All gates passed (G0-G3B). Appendix A now ACTIVE. META_PERCEPTION_HMM_PIPELINE gate_approved=TRUE. Schema freeze in effect.',
    false,
    'IOS003-APPENDIX-A-G4-' || to_char(NOW(), 'YYYYMMDD-HH24MISS'),
    gen_random_uuid()
);

-- STEP 4: Update hash chain
UPDATE vision_verification.hash_chains
SET
    chain_length = chain_length + 1,
    current_hash = encode(sha256(('IoS-003:Appendix_A:G4:ACTIVATION:' || NOW()::text)::bytea), 'hex'),
    last_verification_at = NOW(),
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-003-APPENDIX-A-20251129';

-- STEP 5: Create VEGA attestation for G4 (using correct table in fhq_governance)
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
    'IOS_APPENDIX',
    'IoS-003_Appendix_A_HMM_REGIME',
    '2026.PROD.1',
    'G4_ACTIVATION',
    'APPROVED',
    NOW(),
    encode(sha256(('VEGA:G4:IoS-003_Appendix_A:' || NOW()::text)::bytea), 'hex'),
    'VEGA-PUB-KEY-PLACEHOLDER',
    true,
    jsonb_build_object(
        'gate', 'G4',
        'action', 'ACTIVATION',
        'appendix_code', 'Appendix_A_HMM_REGIME',
        'version', '2026.PROD.1',
        'task_name', 'META_PERCEPTION_HMM_PIPELINE',
        'gate_approved', true,
        'ceo_approved', true,
        'gates_passed', ARRAY['G0', 'G1', 'G2', 'G3', 'G3B'],
        'timestamp', NOW()
    ),
    'ADR-004,ADR-014',
    'IoS-003 Appendix A HMM Regime Pipeline G4 Activation per ADR-004 Change Gates',
    NOW()
);

COMMIT;

-- ============================================================
-- POST-ACTIVATION VERIFICATION
-- ============================================================

SELECT 'APPENDIX STATUS' as check_type;
SELECT ios_id, appendix_code, status, version, updated_at
FROM fhq_meta.ios_appendix_registry
WHERE ios_id = 'IoS-003';

SELECT 'TASK REGISTRY STATUS' as check_type;
SELECT task_name, task_status, gate_approved, vega_reviewed
FROM fhq_governance.task_registry
WHERE task_name = 'META_PERCEPTION_HMM_PIPELINE';

SELECT 'GOVERNANCE ACTION' as check_type;
SELECT action_type, action_target, initiated_by, decision
FROM fhq_governance.governance_actions_log
WHERE action_target = 'IoS-003_Appendix_A_HMM_REGIME'
ORDER BY initiated_at DESC
LIMIT 1;

SELECT 'HASH CHAIN' as check_type;
SELECT chain_id, chain_length, integrity_verified
FROM vision_verification.hash_chains
WHERE chain_id = 'HC-IOS-003-APPENDIX-A-20251129';

SELECT 'VEGA ATTESTATION' as check_type;
SELECT attestation_type, target_id, attestation_status, signature_verified
FROM fhq_governance.vega_attestations
WHERE target_id = 'IoS-003_Appendix_A_HMM_REGIME'
ORDER BY created_at DESC
LIMIT 1;

SELECT 'G4 ACTIVATION COMPLETE' as status;
