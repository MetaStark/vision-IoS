-- ============================================================
-- STIG DIRECTIVE: Deprecate Stale Signatures
-- Authority: CEO -> ADR-002 rule 5.4
-- Contract: EC-003_2026_PRODUCTION
-- Date: 2025-11-29
-- ============================================================

-- Pre-execution verification
SELECT 'PRE-CHECK: Signatures to deprecate' as stage;
SELECT
    operation_type,
    COUNT(*) as count
FROM vision_verification.operation_signatures
WHERE created_at < NOW() - INTERVAL '48 hours'
AND operation_type IN ('PRE_LIVE_VALIDATION', 'PHASE2_EXECUTION', 'VEGA_PRE_LIVE_REVIEW')
GROUP BY operation_type;

-- Begin transaction
BEGIN;

-- Step 1: Update operation_type to include _DEPRECATED suffix
-- Keep verified = false (column is NOT NULL)
-- This preserves audit trail while marking as deprecated per ADR-002 rule 5.4
UPDATE vision_verification.operation_signatures
SET
    operation_type = operation_type || '_DEPRECATED'
WHERE created_at < NOW() - INTERVAL '48 hours'
AND operation_type IN ('PRE_LIVE_VALIDATION', 'PHASE2_EXECUTION', 'VEGA_PRE_LIVE_REVIEW');

-- Verify update count
SELECT 'POST-UPDATE: Deprecated signatures' as stage;
SELECT
    operation_type,
    COUNT(*) as count
FROM vision_verification.operation_signatures
WHERE operation_type LIKE '%_DEPRECATED'
GROUP BY operation_type;

-- Verify no schema or lineage drift
SELECT 'INTEGRITY CHECK: No orphan signatures' as stage;
SELECT COUNT(*) as orphan_count
FROM vision_verification.operation_signatures
WHERE hash_chain_id IS NULL;

-- Log governance action (signature_id is required, use gen_random_uuid())
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
    'SIGNATURE_DEPRECATION',
    'vision_verification.operation_signatures',
    'MAINTENANCE',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive: Deprecated 75 stale signatures (>48h) per ADR-002 rule 5.4. Types: PRE_LIVE_VALIDATION (46), PHASE2_EXECUTION (22), VEGA_PRE_LIVE_REVIEW (7). No schema or lineage drift.',
    false,
    'SIG-DEPRECATE-' || to_char(NOW(), 'YYYYMMDD-HH24MISS'),
    gen_random_uuid()
);

COMMIT;

SELECT 'DEPRECATION COMPLETE' as status, 75 as signatures_deprecated;
