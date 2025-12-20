-- ============================================================================
-- MIGRATION 092: Canonical Price Data Consolidation
-- ============================================================================
-- Authority: CEO Directive - CANONICAL CONSOLIDATION
-- Reference: ADR-013 (One-True-Source / Truth Architecture)
-- Generated: 2025-12-08
--
-- PURPOSE:
--   Consolidate price data to single canonical source per ADR-013:
--   - fhq_market.prices becomes the ONE-TRUE-SOURCE for all price data
--   - fhq_data.price_series reclassified as ARCHIVE (read-only legacy)
--   - IoS-003 → IoS-004 → IoS-005 all read from fhq_market.prices
--
-- RATIONALE:
--   Previous architecture had TWO price tables causing sync gaps:
--   - fhq_data.price_series (Foundation - outdated 2025-12-03)
--   - fhq_market.prices (Vision - current 2025-12-07)
--   This violated ADR-013 One-True-Source principle and caused IoS-003
--   to operate on stale data (4-day gap discovered 2025-12-08).
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: Add Archive Metadata to price_series
-- ============================================================================

-- Add archive classification column
ALTER TABLE fhq_data.price_series
ADD COLUMN IF NOT EXISTS archive_status VARCHAR(20) DEFAULT 'ACTIVE';

ALTER TABLE fhq_data.price_series
ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

ALTER TABLE fhq_data.price_series
ADD COLUMN IF NOT EXISTS archive_reason TEXT;

-- Update to ARCHIVE status
UPDATE fhq_data.price_series
SET archive_status = 'ARCHIVE',
    archived_at = NOW(),
    archive_reason = 'CEO Directive - Canonical Consolidation. Superseded by fhq_market.prices per ADR-013.'
WHERE archive_status = 'ACTIVE';

-- Add comment for future reference
COMMENT ON TABLE fhq_data.price_series IS
'[ARCHIVE] Legacy price data table. Superseded by fhq_market.prices per CEO Directive 2025-12-08.
ADR-013 One-True-Source: All IoS pipelines now read from fhq_market.prices.
DO NOT use for new development. Retained for historical audit trail only.';


-- ============================================================================
-- SECTION 2: Mark fhq_market.prices as Canonical
-- ============================================================================

COMMENT ON TABLE fhq_market.prices IS
'[CANONICAL] One-True-Source for all price data per ADR-013 Truth Architecture.
Used by: IoS-003 (Perception), IoS-004 (Allocation), IoS-005 (Forecast Calibration)
Ingest Pipeline: staging_prices → prices (daily promotion)
CEO Directive: 2025-12-08 Canonical Consolidation';


-- ============================================================================
-- SECTION 3: Log Migration to Governance
-- ============================================================================

INSERT INTO fhq_meta.ios_audit_log (
    audit_id,
    ios_id,
    event_type,
    event_timestamp,
    actor,
    gate_level,
    event_data,
    evidence_hash
) VALUES (
    gen_random_uuid(),
    'SYSTEM',
    'CANONICAL_CONSOLIDATION',
    NOW(),
    'STIG',
    'G2',
    jsonb_build_object(
        'migration', '092_canonical_price_consolidation',
        'authority', 'CEO Directive - Canonical Consolidation',
        'adr_reference', 'ADR-013 One-True-Source',
        'deprecated_table', 'fhq_data.price_series',
        'canonical_table', 'fhq_market.prices',
        'affected_ios', ARRAY['IoS-003', 'IoS-004', 'IoS-005'],
        'rationale', 'Eliminate dual price tables causing sync gaps',
        'timestamp', NOW()
    ),
    encode(sha256('092_canonical_price_consolidation'::bytea), 'hex')::VARCHAR(16)
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    price_count INTEGER;
BEGIN
    -- Verify canonical table has data
    SELECT COUNT(*) INTO price_count FROM fhq_market.prices;

    IF price_count = 0 THEN
        RAISE EXCEPTION 'fhq_market.prices has no data - cannot be canonical';
    END IF;

    RAISE NOTICE 'Migration 092 completed successfully';
    RAISE NOTICE 'fhq_market.prices is now the ONE-TRUE-SOURCE (% rows)', price_count;
    RAISE NOTICE 'fhq_data.price_series reclassified as ARCHIVE';
END $$;
