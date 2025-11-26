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

-- Insert ADR-009 into the approved ADRs registry
-- This makes ADR-009 visible in governance reports
INSERT INTO fhq_meta.approved_adrs (
    adr_code,
    title,
    status,
    effective_date,
    authority,
    description,
    adr_reference
) VALUES (
    'ADR-009',
    'Governance Approval Workflow for Agent Suspension',
    'APPROVED',
    NOW(),
    'LARS',
    'Tier-2 governance workflow requiring dual-approval (VEGA recommendation + CEO approval) for agent suspension. Implements anti-hallucination enforcement via ADR-010 discrepancy scoring.',
    'ADR-001 → ADR-002 → ADR-006 → ADR-007 → ADR-008 → EC-001'
)
ON CONFLICT (adr_code) DO UPDATE SET
    title = EXCLUDED.title,
    status = EXCLUDED.status,
    authority = EXCLUDED.authority,
    description = EXCLUDED.description;

-- Verify registration
DO $$
DECLARE
    adr_registered BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM fhq_meta.approved_adrs
        WHERE adr_code = 'ADR-009'
        AND status = 'APPROVED'
    ) INTO adr_registered;

    IF NOT adr_registered THEN
        RAISE EXCEPTION 'ADR-009 was not registered in approved_adrs';
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
\echo 'ADR-009 is now registered in fhq_meta.approved_adrs'
\echo '=========================================='
\echo ''
