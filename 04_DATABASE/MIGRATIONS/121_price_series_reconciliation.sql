-- ============================================================================
-- Migration 121: Price Series Reconciliation
-- Normalize existing price data listing_ids to canonical_id format
-- Update valid_row_count and data_quality_status for assets with data
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), IoS-001 §4.1 (Iron Curtain)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: Normalize listing_id to canonical_id format
-- ============================================================================
-- Update BTCUSD -> BTC-USD, ETHUSD -> ETH-USD, SOLUSD -> SOL-USD

UPDATE fhq_data.price_series
SET listing_id = 'BTC-USD'
WHERE listing_id = 'BTCUSD';

UPDATE fhq_data.price_series
SET listing_id = 'ETH-USD'
WHERE listing_id = 'ETHUSD';

UPDATE fhq_data.price_series
SET listing_id = 'SOL-USD'
WHERE listing_id = 'SOLUSD';

-- GLD doesn't have a canonical asset yet, leave as-is or skip
-- (It was legacy test data)

-- ============================================================================
-- PART B: Update valid_row_count for all assets with price data
-- ============================================================================

UPDATE fhq_meta.assets a
SET valid_row_count = ps.row_count,
    updated_at = NOW()
FROM (
    SELECT listing_id, COUNT(*) as row_count
    FROM fhq_data.price_series
    WHERE close IS NOT NULL
    GROUP BY listing_id
) ps
WHERE a.canonical_id = ps.listing_id;

-- ============================================================================
-- PART C: Update data_quality_status based on Iron Curtain thresholds
-- ============================================================================
-- Equities/FX: 252 = quarantine, 1260 = full history
-- Crypto: 365 = quarantine, 1825 = full history

-- Update CRYPTO assets
UPDATE fhq_meta.assets
SET data_quality_status = CASE
    WHEN valid_row_count >= 1825 THEN 'FULL_HISTORY'::data_quality_status
    WHEN valid_row_count >= 365 THEN 'SHORT_HISTORY'::data_quality_status
    ELSE 'QUARANTINED'::data_quality_status
END,
updated_at = NOW()
WHERE asset_class = 'CRYPTO' AND valid_row_count > 0;

-- Update EQUITY assets
UPDATE fhq_meta.assets
SET data_quality_status = CASE
    WHEN valid_row_count >= 1260 THEN 'FULL_HISTORY'::data_quality_status
    WHEN valid_row_count >= 252 THEN 'SHORT_HISTORY'::data_quality_status
    ELSE 'QUARANTINED'::data_quality_status
END,
updated_at = NOW()
WHERE asset_class = 'EQUITY' AND valid_row_count > 0;

-- Update FX assets
UPDATE fhq_meta.assets
SET data_quality_status = CASE
    WHEN valid_row_count >= 1260 THEN 'FULL_HISTORY'::data_quality_status
    WHEN valid_row_count >= 252 THEN 'SHORT_HISTORY'::data_quality_status
    ELSE 'QUARANTINED'::data_quality_status
END,
updated_at = NOW()
WHERE asset_class = 'FX' AND valid_row_count > 0;

-- ============================================================================
-- PART D: Verification
-- ============================================================================

DO $$
DECLARE
    total_with_data INTEGER;
    quarantined INTEGER;
    short_history INTEGER;
    full_history INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_with_data
    FROM fhq_meta.assets WHERE valid_row_count > 0;

    SELECT COUNT(*) INTO quarantined
    FROM fhq_meta.assets WHERE data_quality_status = 'QUARANTINED' AND valid_row_count > 0;

    SELECT COUNT(*) INTO short_history
    FROM fhq_meta.assets WHERE data_quality_status = 'SHORT_HISTORY';

    SELECT COUNT(*) INTO full_history
    FROM fhq_meta.assets WHERE data_quality_status = 'FULL_HISTORY';

    RAISE NOTICE '========================================';
    RAISE NOTICE 'PRICE SERIES RECONCILIATION COMPLETE';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Assets with price data: %', total_with_data;
    RAISE NOTICE '  - QUARANTINED (with data): %', quarantined;
    RAISE NOTICE '  - SHORT_HISTORY: %', short_history;
    RAISE NOTICE '  - FULL_HISTORY: %', full_history;
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- PART E: Governance Logging
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
    'DATA_RECONCILIATION',
    'fhq_data.price_series',
    'TABLE',
    'STIG',
    NOW(),
    'APPROVED',
    E'Migration 121: Price Series Reconciliation\n\n' ||
    E'Actions performed:\n' ||
    E'1. Normalized listing_id to canonical_id format (BTCUSD->BTC-USD, etc.)\n' ||
    E'2. Updated valid_row_count for all assets with price data\n' ||
    E'3. Updated data_quality_status based on Iron Curtain thresholds:\n' ||
    E'   - Crypto: 365 rows = SHORT_HISTORY, 1825 = FULL_HISTORY\n' ||
    E'   - Equity/FX: 252 rows = SHORT_HISTORY, 1260 = FULL_HISTORY\n\n' ||
    E'This enables IoS-003 regime processing for assets meeting Iron Curtain requirements.',
    false,
    'MIG-121-PRICE-RECONCILE-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

COMMIT;

-- ============================================================================
-- Migration 121 Complete
-- ============================================================================
