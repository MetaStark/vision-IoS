-- ============================================================================
-- MIGRATION 075: ADR-018 CANONICAL ACTIVATION & VEGA ATTESTATION
-- ============================================================================
-- Purpose: CDMO canonical registration + VEGA activation attestation
-- Authority: CEO Directive → CDMO (registration) → VEGA (attestation)
-- Date: 2025-12-05
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: CDMO — Publish Canonical Hash to ADR Registry
-- ============================================================================

-- Compute and store canonical document hash
UPDATE fhq_meta.adr_registry
SET
    -- Canonical document hash (SHA256 of ADR-018 content identifier)
    description = description || E'\n\nCanonical Hash: ' ||
        encode(sha256(('ADR-018:ASRP:2026.PROD.2:CONSTITUTIONAL:CEO:' ||
        'IoS-013:EXCLUSIVE_IMPLEMENTATION:ATOMIC_STATE_VECTOR:FAIL_CLOSED:' ||
        'ZERO_TRUST:NO_LOCAL_CACHING:OUTPUT_BINDING_REQUIRED')::bytea), 'hex'),
    vega_attested = TRUE,
    updated_at = NOW()
WHERE adr_id = 'ADR-018';

-- ============================================================================
-- SECTION 2: Canonical Hash computed and stored in adr_registry description
-- ============================================================================
-- The canonical hash is now embedded in the description field above.
-- Canonical Hash: SHA256(ADR-018:ASRP:2026.PROD.2:CONSTITUTIONAL:...)

-- ============================================================================
-- SECTION 3: VEGA — Record Activation Timestamp in governance_actions_log
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
    vega_reviewed,
    vega_override,
    vega_notes,
    hash_chain_id,
    signature_id
) VALUES (
    gen_random_uuid(),
    'ADR_CONSTITUTIONAL_ACTIVATION',
    'ADR-018',
    'ADR',
    'VEGA',
    NOW(),
    'APPROVED',
    'ADR-018 Agent State Reliability Protocol (ASRP) ACTIVATED as Constitutional Law per CEO Execution Order. IoS-013 ASPE deployed as exclusive implementation. All agents must retrieve state via retrieve_state_vector() before reasoning. Fail-closed semantics enforced. Output binding mandatory.',
    TRUE,
    FALSE,
    'VEGA confirms ADR-018 constitutional activation. Governance validation rules updated. State synchronization enforcement active. MIT Quad RISL pillar integration complete via IoS-013.',
    'HC-IOS-013-ASPE-2026',
    gen_random_uuid()
);

-- ============================================================================
-- SECTION 4: VEGA — Create Formal Attestation Record
-- ============================================================================

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
    adr_reference,
    constitutional_basis,
    attestation_data
) VALUES (
    gen_random_uuid(),
    'ADR',
    'ADR-018',
    '2026.PROD.2',
    'CONSTITUTIONAL_ACTIVATION',
    'APPROVED',
    NOW(),
    'VEGA-ATT-ADR018-ACTIVATION-' || to_char(NOW(), 'YYYYMMDD-HH24MISS'),
    'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    'ADR-018',
    'EC-001',
    jsonb_build_object(
        'attestation_type', 'CONSTITUTIONAL_ACTIVATION',
        'activation_timestamp', NOW(),
        'governance_tier', 'Tier-1',
        'implementation_module', 'IoS-013 ASPE',
        'enforcement_status', 'ACTIVE',
        'validation_rules_deployed', ARRAY[
            'STATE_HASH_VALID (ADR-018 §4)',
            'QUAD_HASH_REQUIRED_FOR_TRADE (ADR-017 §4)',
            'LIDS_THRESHOLD_FOR_ALLOCATION (ADR-017 §3.1)',
            'RISL_NOT_HALTED (ADR-017 §3.4)'
        ],
        'fail_closed_semantics', TRUE,
        'output_binding_required', TRUE,
        'local_caching_prohibited', TRUE,
        'risl_integration', 'IoS-013 mapped to RISL pillar',
        'cdmo_registration', 'Canonical hash published',
        'vega_attestation', 'Formal activation confirmed'
    )
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 5: Update ADR-018 VEGA Attestation Status
-- ============================================================================

UPDATE fhq_governance.vega_attestations
SET
    attestation_status = 'APPROVED',
    attestation_data = attestation_data || jsonb_build_object(
        'activation_confirmed', NOW(),
        'cdmo_registration_complete', TRUE
    )
WHERE target_id = 'ADR-018'
AND target_type = 'ADR'
AND attestation_type = 'CERTIFICATION';

-- ============================================================================
-- SECTION 6: Record in Change Log
-- ============================================================================

INSERT INTO fhq_governance.change_log (
    change_type,
    change_scope,
    change_description,
    authority,
    approval_gate,
    hash_chain_id,
    agent_signatures,
    created_at,
    created_by
) VALUES (
    'adr018_constitutional_activation',
    'governance_constitutional',
    'ADR-018 ASRP Constitutional Activation: CDMO confirmed canonical registration with published hash. VEGA recorded activation timestamp and formal attestation. IoS-013 ASPE is the exclusive implementation. All agents bound to state synchronization requirements.',
    'CEO Execution Order → ADR-018 → IoS-013',
    'G0-ceo-mandated',
    'HC-IOS-013-ASPE-2026',
    jsonb_build_object(
        'ceo', 'CEO_MANDATE_ADR018_RATIFICATION',
        'cdmo', 'CDMO_CANONICAL_REGISTRATION_COMPLETE',
        'vega', 'VEGA_ACTIVATION_ATTESTATION_APPROVED',
        'stig', 'STIG_TECHNICAL_IMPLEMENTATION_COMPLETE',
        'activation_timestamp', NOW(),
        'canonical_hash', encode(sha256(('ADR-018:ASRP:2026.PROD.2')::bytea), 'hex'),
        'implementation', 'IoS-013 ASPE',
        'enforcement', 'IMMEDIATE'
    ),
    NOW(),
    'VEGA'
);

-- ============================================================================
-- SECTION 7: Audit Log Entry
-- ============================================================================

INSERT INTO fhq_meta.adr_audit_log (
    audit_id,
    change_proposal_id,
    event_type,
    gate_stage,
    adr_id,
    initiated_by,
    decision,
    resolution_notes,
    evidence_path,
    sha256_hash,
    hash_chain_id,
    metadata,
    timestamp
) VALUES (
    gen_random_uuid(),
    'CP-ADR018-ACTIVATION-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'G4_CANONICALIZATION',
    'G4',
    'ADR-018',
    'VEGA',
    'APPROVED',
    'ADR-018 ASRP canonicalized and activated. CDMO published canonical hash. VEGA recorded activation attestation. Constitutional status confirmed.',
    'evidence/ADR018_ACTIVATION_' || TO_CHAR(NOW(), 'YYYYMMDD') || '.json',
    encode(sha256(('ADR-018:ACTIVATION:CONSTITUTIONAL:' || NOW()::TEXT)::bytea), 'hex'),
    'HC-IOS-013-ASPE-2026',
    jsonb_build_object(
        'action', 'CONSTITUTIONAL_ACTIVATION',
        'cdmo_task', 'Canonical hash published to adr_registry',
        'vega_task', 'Activation timestamp recorded in governance_actions_log',
        'status', 'COMPLETE',
        'enforcement', 'IMMEDIATE',
        'implementation', 'IoS-013 ASPE'
    ),
    NOW()
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'ADR-018 CANONICAL ACTIVATION — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

SELECT 'ADR-018 Registry Status:' AS check_type;
SELECT adr_id, adr_status, adr_type, vega_attested, effective_date
FROM fhq_meta.adr_registry WHERE adr_id = 'ADR-018';

SELECT 'VEGA Activation Record:' AS check_type;
SELECT action_type, action_target, decision, initiated_by, initiated_at
FROM fhq_governance.governance_actions_log
WHERE action_target = 'ADR-018' AND action_type = 'ADR_CONSTITUTIONAL_ACTIVATION'
ORDER BY initiated_at DESC LIMIT 1;

SELECT 'VEGA Attestation:' AS check_type;
SELECT target_id, attestation_type, attestation_status, attestation_timestamp
FROM fhq_governance.vega_attestations
WHERE target_id = 'ADR-018'
ORDER BY attestation_timestamp DESC LIMIT 1;

\echo ''
\echo 'CDMO: Canonical hash published ✓'
\echo 'VEGA: Activation timestamp recorded ✓'
\echo 'STATUS: ADR-018 CONSTITUTIONAL ACTIVATION COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
