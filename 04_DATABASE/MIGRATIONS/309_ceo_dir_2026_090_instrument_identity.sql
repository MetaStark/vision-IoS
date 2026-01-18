-- =============================================================================
-- CEO-DIR-2026-090: IoS-001 CANONICAL SCHEMA EXPANSION - INSTRUMENT IDENTITY
-- =============================================================================
--
-- Authority: CEO
-- Gate: G0 → G4 per ADR-004
-- Scope: fhq_meta.assets (canonical layer)
-- Domain: Universal (all asset classes)
--
-- This migration adds two mandatory columns to fhq_meta.assets:
--   1. instrument_type: SPOT, PERP, FUTURE, OPTION
--   2. data_granularity: AGGREGATED, EXCHANGE_RAW
--
-- CRITICAL: No NULL values allowed in canonical layer
-- =============================================================================

BEGIN;

-- =============================================================================
-- STEP 1: CREATE ENUM TYPES
-- =============================================================================

-- Create instrument_type enum if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'instrument_type_enum') THEN
        CREATE TYPE instrument_type_enum AS ENUM ('SPOT', 'PERP', 'FUTURE', 'OPTION');
    END IF;
END$$;

-- Create data_granularity enum if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'data_granularity_enum') THEN
        CREATE TYPE data_granularity_enum AS ENUM ('AGGREGATED', 'EXCHANGE_RAW');
    END IF;
END$$;

-- =============================================================================
-- STEP 2: ADD COLUMNS TO fhq_meta.assets
-- =============================================================================

-- Add instrument_type column (nullable first for migration)
ALTER TABLE fhq_meta.assets
ADD COLUMN IF NOT EXISTS instrument_type VARCHAR(20);

-- Add data_granularity column (nullable first for migration)
ALTER TABLE fhq_meta.assets
ADD COLUMN IF NOT EXISTS data_granularity VARCHAR(20);

-- =============================================================================
-- STEP 3: SET DEFAULT VALUES FOR EXISTING RECORDS
-- =============================================================================

-- All existing assets default to SPOT (most common case)
UPDATE fhq_meta.assets
SET instrument_type = 'SPOT'
WHERE instrument_type IS NULL;

-- All existing assets default to AGGREGATED (historical data sources)
UPDATE fhq_meta.assets
SET data_granularity = 'AGGREGATED'
WHERE data_granularity IS NULL;

-- =============================================================================
-- STEP 4: ADD NOT NULL CONSTRAINTS
-- =============================================================================

ALTER TABLE fhq_meta.assets
ALTER COLUMN instrument_type SET NOT NULL;

ALTER TABLE fhq_meta.assets
ALTER COLUMN data_granularity SET NOT NULL;

-- =============================================================================
-- STEP 5: ADD CHECK CONSTRAINTS
-- =============================================================================

ALTER TABLE fhq_meta.assets
ADD CONSTRAINT chk_instrument_type
CHECK (instrument_type IN ('SPOT', 'PERP', 'FUTURE', 'OPTION'));

ALTER TABLE fhq_meta.assets
ADD CONSTRAINT chk_data_granularity
CHECK (data_granularity IN ('AGGREGATED', 'EXCHANGE_RAW'));

-- =============================================================================
-- STEP 6: CREATE EXCHANGE MIC REGISTRY TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.exchange_mic_registry (
    mic_code VARCHAR(10) PRIMARY KEY,
    exchange_name VARCHAR(100) NOT NULL,
    exchange_type VARCHAR(50) NOT NULL,
    asset_classes TEXT[] NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_exchange_type CHECK (exchange_type IN ('CEX', 'DEX', 'AGGREGATOR', 'TRADITIONAL'))
);

-- Seed exchange MIC registry with initial values
INSERT INTO fhq_meta.exchange_mic_registry (mic_code, exchange_name, exchange_type, asset_classes) VALUES
    ('XNYS', 'New York Stock Exchange', 'TRADITIONAL', ARRAY['EQUITY_US']),
    ('XNAS', 'NASDAQ', 'TRADITIONAL', ARRAY['EQUITY_US']),
    ('XBIN', 'Binance', 'CEX', ARRAY['CRYPTO']),
    ('XBYB', 'Bybit', 'CEX', ARRAY['CRYPTO']),
    ('XOKX', 'OKX', 'CEX', ARRAY['CRYPTO']),
    ('XDRB', 'Deribit', 'CEX', ARRAY['CRYPTO']),
    ('XCBS', 'Coinbase', 'CEX', ARRAY['CRYPTO']),
    ('XCRY', 'Crypto Aggregated', 'AGGREGATOR', ARRAY['CRYPTO'])
ON CONFLICT (mic_code) DO NOTHING;

-- =============================================================================
-- STEP 7: CREATE INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_assets_instrument_type
ON fhq_meta.assets (instrument_type);

CREATE INDEX IF NOT EXISTS idx_assets_data_granularity
ON fhq_meta.assets (data_granularity);

CREATE INDEX IF NOT EXISTS idx_assets_instrument_asset_class
ON fhq_meta.assets (instrument_type, asset_class);

-- =============================================================================
-- STEP 8: GOVERNANCE LOGGING
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log
    (action_type, action_target, action_target_type, initiated_by, decision, decision_rationale, metadata)
VALUES
    ('SCHEMA_MIGRATION_EXECUTED', 'MIGRATION_309_INSTRUMENT_IDENTITY', 'MIGRATION', 'STIG', 'EXECUTED',
     'CEO-DIR-2026-090: Added instrument_type and data_granularity columns to fhq_meta.assets. Created exchange_mic_registry table.',
     jsonb_build_object(
         'directive', 'CEO-DIR-2026-090',
         'migration', '309_ceo_dir_2026_090_instrument_identity.sql',
         'columns_added', ARRAY['instrument_type', 'data_granularity'],
         'table_created', 'fhq_meta.exchange_mic_registry',
         'executed_at', NOW()
     ));

-- =============================================================================
-- STEP 9: VERIFICATION QUERIES
-- =============================================================================

-- Verify no NULL values exist
DO $$
DECLARE
    null_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO null_count
    FROM fhq_meta.assets
    WHERE instrument_type IS NULL OR data_granularity IS NULL;

    IF null_count > 0 THEN
        RAISE EXCEPTION 'Migration failed: % assets have NULL values in canonical columns', null_count;
    END IF;
END$$;

-- Log verification
DO $$
DECLARE
    total_assets INTEGER;
    spot_count INTEGER;
    crypto_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_assets FROM fhq_meta.assets;
    SELECT COUNT(*) INTO spot_count FROM fhq_meta.assets WHERE instrument_type = 'SPOT';
    SELECT COUNT(*) INTO crypto_count FROM fhq_meta.assets WHERE asset_class = 'CRYPTO';

    RAISE NOTICE 'Migration 309 complete: % total assets, % SPOT, % CRYPTO',
        total_assets, spot_count, crypto_count;
END$$;

COMMIT;

-- =============================================================================
-- VERIFICATION QUERY (run manually after migration)
-- =============================================================================
-- SELECT
--     asset_class,
--     instrument_type,
--     data_granularity,
--     COUNT(*) as count
-- FROM fhq_meta.assets
-- GROUP BY asset_class, instrument_type, data_granularity
-- ORDER BY asset_class, instrument_type;
