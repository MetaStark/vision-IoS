-- =====================================================
-- MIGRATION 020: REGISTER ADR-009 IN ADR REGISTRY
-- =====================================================
--
-- Authority: LARS
-- Purpose: Register ADR-009 in the central ADR registry
-- Issue: Migration 019 created ADR-009 infrastructure but forgot
--        to register ADR-009 itself in the registry
--
-- =====================================================

BEGIN;

-- =====================================================
-- REGISTER ADR-009 IN ADR REGISTRY
-- =====================================================

-- Insert ADR-009 into fhq_meta.adr_registry
INSERT INTO fhq_meta.adr_registry (
    adr_id,
    adr_title,
    adr_status,
    adr_type,
    current_version,
    governance_tier,
    owner,
    created_by,
    constitutional_authority,
    description,
    affects
) VALUES (
    'ADR-009',
    'Governance Approval Workflow for Agent Suspension',
    'APPROVED',
    'ARCHITECTURAL',
    '1.0.0',
    'Tier-2',
    'LARS',
    'LARS',
    'ADR-001 → ADR-002 → ADR-006 → ADR-007 → ADR-008 → EC-001',
    'Tier-2 governance workflow requiring dual-approval (VEGA recommendation + CEO approval) for agent suspension. Implements anti-hallucination enforcement via ADR-010 discrepancy scoring.',
    ARRAY['FINN', 'STIG', 'LINE', 'LARS', 'VEGA']
)
ON CONFLICT (adr_id) DO UPDATE SET
    adr_title = EXCLUDED.adr_title,
    adr_status = EXCLUDED.adr_status,
    governance_tier = EXCLUDED.governance_tier,
    description = EXCLUDED.description,
    updated_at = NOW();

-- Verify registration
DO $$
DECLARE
    adr_registered BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.adr_registry
        WHERE adr_id = 'ADR-009'
        AND adr_status = 'APPROVED'
    ) INTO adr_registered;

    IF NOT adr_registered THEN
        RAISE EXCEPTION 'ADR-009 was not registered in adr_registry';
    END IF;

    RAISE NOTICE 'ADR-009 successfully registered in ADR Registry';
END $$;

COMMIT;

-- =====================================================
-- VERIFICATION
-- =====================================================

SELECT
    'MIGRATION 020 COMPLETE' AS status,
    'ADR-009 registered in ADR Registry' AS description,
    NOW() AS completed_at;

\echo ''
\echo '=========================================='
\echo 'MIGRATION 020: ADR-009 REGISTRY REGISTRATION'
\echo '=========================================='
\echo 'ADR-009 is now registered in fhq_meta.adr_registry'
\echo '=========================================='
\echo ''
