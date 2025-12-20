-- ============================================================================
-- DIRECTIVE: IOS-001_CORRECTION_20251128
-- ============================================================================
-- Authority Chain: CEO → LARS → STIG → CODE
-- Oversight: VEGA
-- Classification: IoS Module Correction (Tier-1 Critical)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PHASE 1: PURGE ALL UNAPPROVED SEED DATA
-- ============================================================================

-- Remove model contexts first (FK dependency)
DELETE FROM fhq_meta.model_context_registry;

-- Remove assets (FK dependency on exchanges)
DELETE FROM fhq_meta.assets;

-- Remove exchanges
DELETE FROM fhq_meta.exchanges;

-- ============================================================================
-- PHASE 2: CORRECT IOS-001 REGISTRY ENTRY
-- ============================================================================

UPDATE fhq_meta.ios_registry
SET
    version = '2026.PROD.2',
    governing_adrs = ARRAY['ADR-001','ADR-006','ADR-012','ADR-013','ADR-016'],
    description = 'Application Layer Registry [CORRECTED 2025-11-28: Removed invalid ADR references and purged unapproved seed data]',
    updated_at = NOW()
WHERE ios_id = 'IoS-001';

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'model_context_registry' as table_name, COUNT(*) as count FROM fhq_meta.model_context_registry
UNION ALL
SELECT 'assets' as table_name, COUNT(*) as count FROM fhq_meta.assets
UNION ALL
SELECT 'exchanges' as table_name, COUNT(*) as count FROM fhq_meta.exchanges;

SELECT ios_id, version, governing_adrs, description
FROM fhq_meta.ios_registry
WHERE ios_id = 'IoS-001';
