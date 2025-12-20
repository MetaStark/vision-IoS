-- ============================================================================
-- DIRECTIVE: IOS-001_CANONICAL_REGISTRY_ACTIVATION_20251129
-- ============================================================================
-- Authority Chain: CEO → LARS → STIG → CODE
-- Oversight: VEGA (Governance & TRiSM)
-- Classification: IoS MODULE ACTIVATION
-- ============================================================================
-- PHASE 1.2: Non-destructive schema migrations
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. EXCHANGES TABLE - Add missing canonical columns
-- ============================================================================

-- Add region (maps from country_code conceptually, but explicit field)
ALTER TABLE fhq_meta.exchanges
ADD COLUMN IF NOT EXISTS region TEXT;

-- Add settlement_convention
ALTER TABLE fhq_meta.exchanges
ADD COLUMN IF NOT EXISTS settlement_convention TEXT;

-- Add vega_signature_id for governance linkage
ALTER TABLE fhq_meta.exchanges
ADD COLUMN IF NOT EXISTS vega_signature_id UUID;

-- Add open_time and close_time (separate from trading_hours JSONB for direct queries)
ALTER TABLE fhq_meta.exchanges
ADD COLUMN IF NOT EXISTS open_time TIME;

ALTER TABLE fhq_meta.exchanges
ADD COLUMN IF NOT EXISTS close_time TIME;

-- Ensure mic has a primary key constraint if not already
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'fhq_meta.exchanges'::regclass
        AND contype = 'p'
    ) THEN
        ALTER TABLE fhq_meta.exchanges ADD PRIMARY KEY (mic);
    END IF;
END $$;

-- ============================================================================
-- 2. ASSETS TABLE - Create canonical table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.assets (
    canonical_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    exchange_mic TEXT NOT NULL,  -- References exchanges.mic
    asset_class TEXT,
    currency TEXT,
    lot_size NUMERIC,
    tick_size NUMERIC,
    sector TEXT,
    risk_profile TEXT,
    active_flag BOOLEAN DEFAULT TRUE,
    vega_signature_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_assets_exchange FOREIGN KEY (exchange_mic)
        REFERENCES fhq_meta.exchanges(mic) ON UPDATE CASCADE
);

-- Create index for exchange lookups
CREATE INDEX IF NOT EXISTS idx_assets_exchange_mic ON fhq_meta.assets(exchange_mic);
CREATE INDEX IF NOT EXISTS idx_assets_ticker ON fhq_meta.assets(ticker);
CREATE INDEX IF NOT EXISTS idx_assets_active ON fhq_meta.assets(active_flag) WHERE active_flag = TRUE;

-- Updated_at trigger for assets
CREATE OR REPLACE FUNCTION fhq_meta.assets_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_assets_updated_at ON fhq_meta.assets;

CREATE TRIGGER trg_assets_updated_at
BEFORE UPDATE ON fhq_meta.assets
FOR EACH ROW
EXECUTE FUNCTION fhq_meta.assets_set_updated_at();

COMMENT ON TABLE fhq_meta.assets IS 'IoS-001 Canonical Asset Registry. Single source of truth for all tradable instruments in the FjordHQ universe.';

-- ============================================================================
-- 3. MODEL_CONTEXT_REGISTRY TABLE - Create canonical table
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.model_context_registry (
    context_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id TEXT NOT NULL,
    feature_set TEXT[] DEFAULT '{}',
    regime_model_ref TEXT,
    forecast_model_ref TEXT,
    perception_model_ref TEXT,
    embedding_profile TEXT,
    training_schema_hash TEXT,
    data_vendor_source TEXT,
    vega_signature_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_model_context_asset FOREIGN KEY (canonical_id)
        REFERENCES fhq_meta.assets(canonical_id) ON UPDATE CASCADE
);

-- Indexes for model_context_registry
CREATE INDEX IF NOT EXISTS idx_model_context_canonical_id ON fhq_meta.model_context_registry(canonical_id);
CREATE INDEX IF NOT EXISTS idx_model_context_regime ON fhq_meta.model_context_registry(regime_model_ref);

-- Updated_at trigger for model_context_registry
CREATE OR REPLACE FUNCTION fhq_meta.model_context_registry_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_model_context_registry_updated_at ON fhq_meta.model_context_registry;

CREATE TRIGGER trg_model_context_registry_updated_at
BEFORE UPDATE ON fhq_meta.model_context_registry
FOR EACH ROW
EXECUTE FUNCTION fhq_meta.model_context_registry_set_updated_at();

COMMENT ON TABLE fhq_meta.model_context_registry IS 'IoS-001 Model Context Registry. Maps assets to their modeling contexts including feature sets, regime models, and training schemas.';

COMMIT;

-- ============================================================================
-- PHASE 2: MINIMAL SEEDING
-- ============================================================================

BEGIN;

-- 2.1 Seed canonical exchanges
INSERT INTO fhq_meta.exchanges (mic, exchange_name, country_code, timezone, region, open_time, close_time, settlement_convention, is_active)
VALUES
    ('BINANCE', 'Binance Spot Exchange', 'MT', 'UTC', 'GLOBAL', '00:00:00', '23:59:59', 'T+0', TRUE),
    ('XNAS', 'NASDAQ Stock Exchange', 'US', 'America/New_York', 'NORTH_AMERICA', '09:30:00', '16:00:00', 'T+2', TRUE),
    ('XNYS', 'New York Stock Exchange', 'US', 'America/New_York', 'NORTH_AMERICA', '09:30:00', '16:00:00', 'T+2', TRUE),
    ('XOSL', 'Oslo Børs', 'NO', 'Europe/Oslo', 'EUROPE', '09:00:00', '16:20:00', 'T+2', TRUE)
ON CONFLICT (mic) DO UPDATE SET
    region = EXCLUDED.region,
    open_time = EXCLUDED.open_time,
    close_time = EXCLUDED.close_time,
    settlement_convention = EXCLUDED.settlement_convention,
    updated_at = NOW();

-- 2.2 Seed canonical assets
INSERT INTO fhq_meta.assets (canonical_id, ticker, exchange_mic, asset_class, currency, lot_size, tick_size, sector, risk_profile, active_flag)
VALUES
    ('BTCUSD.BINANCE', 'BTCUSD', 'BINANCE', 'CRYPTO', 'USD', 0.00001, 0.01, 'CRYPTOCURRENCY', 'HIGH_VOLATILITY', TRUE),
    ('ETHUSD.BINANCE', 'ETHUSD', 'BINANCE', 'CRYPTO', 'USD', 0.0001, 0.01, 'CRYPTOCURRENCY', 'HIGH_VOLATILITY', TRUE),
    ('EQNR.XOSL', 'EQNR', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'MEDIUM_VOLATILITY', TRUE)
ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    asset_class = EXCLUDED.asset_class,
    currency = EXCLUDED.currency,
    sector = EXCLUDED.sector,
    updated_at = NOW();

-- 2.3 Seed model_context for BTCUSD demo
INSERT INTO fhq_meta.model_context_registry (
    context_id,
    canonical_id,
    feature_set,
    regime_model_ref,
    forecast_model_ref,
    perception_model_ref,
    embedding_profile,
    training_schema_hash,
    data_vendor_source
)
VALUES (
    'e0000001-0001-0001-0001-000000000001'::uuid,
    'BTCUSD.BINANCE',
    ARRAY['RSI', 'ICHIMOKU', 'ATR'],
    'REGIME_V1',
    'BASELINE_FORECAST_V1',
    'PERCEPTION_V1',
    'EMBEDDING_CRYPTO_V1',
    encode(sha256('BTCUSD.BINANCE:REGIME_V1:BASELINE_FORECAST_V1:PERCEPTION_V1'::bytea), 'hex'),
    'BINANCE_SPOT'
)
ON CONFLICT (context_id) DO UPDATE SET
    feature_set = EXCLUDED.feature_set,
    regime_model_ref = EXCLUDED.regime_model_ref,
    forecast_model_ref = EXCLUDED.forecast_model_ref,
    updated_at = NOW();

COMMIT;

-- ============================================================================
-- VERIFICATION: Schema Snapshot for VEGA
-- ============================================================================

SELECT 'EXCHANGES' as table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'fhq_meta' AND table_name = 'exchanges'
ORDER BY ordinal_position;

SELECT 'ASSETS' as table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'fhq_meta' AND table_name = 'assets'
ORDER BY ordinal_position;

SELECT 'MODEL_CONTEXT_REGISTRY' as table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'fhq_meta' AND table_name = 'model_context_registry'
ORDER BY ordinal_position;

-- Data counts
SELECT 'exchanges' as entity, COUNT(*) as count FROM fhq_meta.exchanges
UNION ALL
SELECT 'assets' as entity, COUNT(*) as count FROM fhq_meta.assets
UNION ALL
SELECT 'model_context_registry' as entity, COUNT(*) as count FROM fhq_meta.model_context_registry;
