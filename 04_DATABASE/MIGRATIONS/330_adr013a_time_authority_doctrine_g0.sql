-- ============================================================================
-- MIGRATION 330: ADR-013A TIME AUTHORITY DOCTRINE (G0 SUBMISSION)
-- ============================================================================
-- CEO Directive: CEO-DIR-20260120-DAY20 (Full-Stack Database Verification)
-- Authority: ADR-004 (Change Control), CEO-DIR-2026-091
-- Gate: G0_SUBMISSION
-- Executor: STIG (EC-003_2026_PRODUCTION)
-- Date: 2026-01-20
--
-- PURPOSE: Register ADR-013A (Time Authority Doctrine) for G0 approval.
--          This ADR establishes that all temporal reasoning must originate
--          from canonical calendar truth - no local clocks, no assumptions.
--
-- FINDING: CEO-DIR-20260120-DAY20 database verification identified ADR-013A
--          as MISSING from fhq_meta.adr_registry (24/25 ADRs registered).
--
-- PARENT: ADR-013 (Infrastructure Sovereignty / Kernel Specification)
-- CLASSIFICATION: CONSTITUTIONAL / GOVERNANCE-CRITICAL
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: REGISTER ADR-013A IN ADR REGISTRY
-- ============================================================================

INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_status,
    adr_type,
    current_version,
    approval_authority,
    effective_date,
    file_path,
    metadata,
    title,
    status,
    version,
    created_by,
    governance_tier,
    owner,
    constitutional_authority,
    description,
    rationale,
    vega_attested,
    created_at,
    updated_at
) VALUES (
    'ADR-013A',
    'Time Authority Doctrine',
    'G0_SUBMITTED',
    'CONSTITUTIONAL',
    '2026.PRODUCTION',
    'CEO-DIR-2026-091',
    '2026-01-18',
    'C:\fhq-market-system\vision-ios\00_CONSTITUTION\ADR-013A_TIME_AUTHORITY_DOCTRINE.md',
    jsonb_build_object(
        'parent_adr', 'ADR-013',
        'classification', 'GOVERNANCE-CRITICAL',
        'g0_submission_date', '2026-01-20',
        'submitted_by', 'STIG',
        'ceo_directive', 'CEO-DIR-20260120-DAY20',
        'doctrine_statement', 'All temporal reasoning must originate from canonical calendar truth (or epoch boundary for crypto). No local clocks, no assumptions.',
        'scope', ARRAY['All agent operations', 'Automated processes', 'Signal generation', 'Forecast evaluation', 'Horizon calculations', 'Learning attribution'],
        'canonical_time_sources', jsonb_build_object(
            'US_EQUITY', 'fhq_meta.calendar_days (US_EQUITY)',
            'CRYPTO', 'fhq_meta.crypto_epoch_boundary()'
        ),
        'prohibited_patterns', ARRAY[
            'CURRENT_DATE + N for equity horizons',
            'Local clock for timestamp generation',
            'Hardcoded day counts for horizon',
            'Assuming tomorrow is a trading day',
            'Using NOW() without timezone'
        ],
        'enforcement', 'Class B violations under ADR-013'
    ),
    'Time Authority Doctrine',
    'G0_SUBMITTED',
    '2026.PRODUCTION',
    'STIG',
    'Tier-1',
    'STIG',
    'CEO-DIR-2026-091',
    'All temporal reasoning must originate from canonical calendar truth (or epoch boundary for crypto). No local clocks, no assumptions.',
    'Time-as-infrastructure prevents silent horizon drift, weekend/holiday execution attempts, timezone confusion, non-deterministic outcome capture, and audit-failing temporal claims.',
    false,
    NOW(),
    NOW()
) ON CONFLICT (adr_id) DO UPDATE SET
    adr_status = EXCLUDED.adr_status,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- ============================================================================
-- SECTION 2: CREATE HASH CHAIN (ADR-011 Fortress Standard)
-- ============================================================================

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
    'HC-ADR-013A-CONSTITUTIONAL-20260120',
    'ADR_CONSTITUTIONAL',
    'ADR-013A',
    encode(sha256(('ADR-013A:TIME-AUTHORITY-DOCTRINE:GENESIS:CONSTITUTIONAL:2026-01-20')::bytea), 'hex'),
    encode(sha256(('ADR-013A:TIME-AUTHORITY-DOCTRINE:G0_SUBMITTED:2026-01-20')::bytea), 'hex'),
    1,
    TRUE,
    NOW(),
    'STIG',
    NOW(),
    NOW()
) ON CONFLICT (chain_id) DO NOTHING;

-- ============================================================================
-- SECTION 3: LOG G4 ARTIFACT HASH
-- ============================================================================

INSERT INTO fhq_governance.g4_artifact_hashes (
    hash_id,
    ios_id,
    gate_level,
    artifact_path,
    sha256_hash,
    validated_at,
    validated_by,
    drift_detected,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'ADR-013A',
    'G0',
    '00_CONSTITUTION/ADR-013A_TIME_AUTHORITY_DOCTRINE.md',
    encode(sha256(('ADR-013A:TIME-AUTHORITY-DOCTRINE:G0_SUBMITTED:2026-01-20')::bytea), 'hex'),
    NOW(),
    'STIG',
    false,
    'HC-ADR-013A-CONSTITUTIONAL-20260120'
);

-- ============================================================================
-- SECTION 4: LOG GOVERNANCE ACTION
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
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'ADR_G0_SUBMISSION',
    'ADR-013A',
    'ADR',
    'STIG',
    NOW(),
    'G0_SUBMITTED',
    'CEO-DIR-20260120-DAY20: ADR-013A (Time Authority Doctrine) submitted for G0 approval. Identified as MISSING during database verification (24/25 ADRs registered). Parent: ADR-013 (Infrastructure Sovereignty). Establishes canonical time sources for all temporal reasoning.',
    false,
    'HC-ADR-013A-CONSTITUTIONAL-20260120'
);

-- ============================================================================
-- SECTION 5: CREATE VEGA ATTESTATION (PENDING)
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
    'ADR-013A',
    '2026.PRODUCTION',
    'CERTIFICATION',
    'PENDING',
    NOW(),
    'VEGA-ATT-ADR013A-' || md5(random()::text),
    'GENESIS_KEY_VEGA_PENDING_PRODUCTION',
    'ADR-013A',
    'EC-001',
    jsonb_build_object(
        'attestation_id', 'ATT-VEGA-ADR013A-' || to_char(NOW(), 'YYYYMMDD'),
        'governance_tier', 'Tier-1',
        'verification_status', 'PENDING - Awaiting VEGA formal attestation',
        'parent_adr', 'ADR-013',
        'constitutional_mandate', 'Time Authority Doctrine - all temporal reasoning from canonical sources',
        'gate_status', 'G0_SUBMITTED',
        'ceo_directive', 'CEO-DIR-20260120-DAY20'
    )
) ON CONFLICT DO NOTHING;

-- ============================================================================
-- SECTION 6: AUDIT LOG ENTRY (ADR-002 Compliance)
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
    'CP-ADR013A-REG-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'SUBMISSION',
    'G0',
    'ADR-013A',
    'STIG',
    'G0_SUBMITTED',
    'CEO-DIR-20260120-DAY20: ADR-013A Time Authority Doctrine submitted for G0 approval. Identified as MISSING during database verification. Parent: ADR-013 (Infrastructure Sovereignty). Doctrine: All temporal reasoning must originate from canonical calendar truth.',
    '12_DAILY_REPORTS/FjordHQ_DB_DAY20.json',
    encode(sha256(('ADR-013A:TIME-AUTHORITY-DOCTRINE:G0_SUBMITTED:2026-01-20')::bytea), 'hex'),
    'HC-ADR-013A-CONSTITUTIONAL-20260120',
    jsonb_build_object(
        'adr_id', 'ADR-013A',
        'version', '2026.PRODUCTION',
        'type', 'CONSTITUTIONAL',
        'parent', 'ADR-013',
        'owner', 'STIG',
        'ceo_directive', 'CEO-DIR-20260120-DAY20',
        'finding', 'MISSING from registry during Day 20 verification',
        'canonical_time_sources', jsonb_build_object(
            'US_EQUITY', 'fhq_meta.calendar_days',
            'CRYPTO', 'fhq_meta.crypto_epoch_boundary()'
        )
    ),
    NOW()
);

COMMIT;

-- ============================================================================
-- POST-MIGRATION VERIFICATION
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 330: ADR-013A TIME AUTHORITY DOCTRINE — VERIFICATION'
\echo '═══════════════════════════════════════════════════════════════════════════'

-- Verify ADR-013A registration
SELECT 'Registry Entry:' AS check_type;
SELECT adr_id, adr_title, adr_status, adr_type, governance_tier, vega_attested
FROM fhq_meta.adr_registry
WHERE adr_id = 'ADR-013A';

-- Verify Hash Chain
SELECT 'Hash Chain:' AS check_type;
SELECT chain_id, chain_type, chain_scope, integrity_verified
FROM vision_verification.hash_chains
WHERE chain_id = 'HC-ADR-013A-CONSTITUTIONAL-20260120';

-- Verify Governance Action
SELECT 'Governance Action:' AS check_type;
SELECT action_type, action_target, decision, initiated_by
FROM fhq_governance.governance_actions_log
WHERE action_target = 'ADR-013A'
ORDER BY initiated_at DESC
LIMIT 1;

-- Verify VEGA Attestation
SELECT 'VEGA Attestation:' AS check_type;
SELECT target_id, target_type, attestation_status
FROM fhq_governance.vega_attestations
WHERE target_id = 'ADR-013A';

-- Verify ADR count (should now be 25)
SELECT 'ADR Registry Count:' AS check_type;
SELECT COUNT(*) as total_adrs,
       SUM(CASE WHEN adr_id LIKE 'ADR-%' THEN 1 ELSE 0 END) as adr_count
FROM fhq_meta.adr_registry
WHERE adr_id LIKE 'ADR-%';

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'ADR-013A TIME AUTHORITY DOCTRINE — REGISTRATION COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo 'Document Registered:'
\echo '  ADR-013A — Time Authority Doctrine (CONSTITUTIONAL)'
\echo ''
\echo 'Parent: ADR-013 (Infrastructure Sovereignty)'
\echo 'Authority: CEO-DIR-2026-091'
\echo ''
\echo 'Doctrine Statement:'
\echo '  All temporal reasoning must originate from canonical calendar truth'
\echo '  (or epoch boundary for crypto). No local clocks, no assumptions.'
\echo ''
\echo 'Gate Status: G0_SUBMITTED'
\echo 'VEGA Attestation: PENDING'
\echo ''
\echo 'Next Step: VEGA attestation required for G0 → ACTIVE transition'
\echo '═══════════════════════════════════════════════════════════════════════════'
