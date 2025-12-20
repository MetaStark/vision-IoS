-- =====================================================
-- MIGRATION 022: GENESIS INGESTION INFRASTRUCTURE
-- =====================================================
-- Authority: ADR-013 (One-True-Source Architecture)
--            ADR-007 (Orchestrator Fetch Stage)
--            ADR-002 (Audit & Lineage)
--            IoS-001 (Canonical Asset Registry)
--
-- Purpose: Create infrastructure for OPERATION DATA FIRST
-- Owner: STIG (CTO)
-- Executor: CODE
-- Date: 2025-11-29
-- =====================================================

BEGIN;

-- =====================================================
-- STEP 1: Create fhq_market schema (staging area)
-- =====================================================

CREATE SCHEMA IF NOT EXISTS fhq_market;

COMMENT ON SCHEMA fhq_market IS 'Market data staging and canonical storage (ADR-013). Staging tables hold raw ingested data before STIG canonicalization.';

-- =====================================================
-- STEP 2: Create staging_prices table
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_market.staging_prices (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Asset reference (from IoS-001)
    asset_id UUID NOT NULL,
    canonical_id TEXT NOT NULL,

    -- OHLCV data
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,  -- UTC ISO8601
    open FLOAT8 NOT NULL,
    high FLOAT8 NOT NULL,
    low FLOAT8 NOT NULL,
    close FLOAT8 NOT NULL,
    volume FLOAT8 NOT NULL,

    -- Source and lineage (ADR-002)
    source TEXT NOT NULL DEFAULT 'yfinance',
    data_hash TEXT NOT NULL,  -- SHA-256 of row
    batch_id UUID NOT NULL,   -- UUID for ingest run

    -- Data quality flags
    gap_filled BOOLEAN DEFAULT FALSE,
    quality_flags JSONB DEFAULT '{}',

    -- Audit trail
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ingested_by TEXT NOT NULL DEFAULT 'CODE',

    -- Constraints
    CONSTRAINT staging_prices_ohlc_valid CHECK (
        high >= low AND
        high >= open AND
        high >= close AND
        low <= open AND
        low <= close
    ),
    CONSTRAINT staging_prices_positive CHECK (
        open > 0 AND high > 0 AND low > 0 AND close > 0
    ),

    -- Unique constraint for idempotent ingestion
    CONSTRAINT staging_prices_unique_asset_timestamp UNIQUE (canonical_id, timestamp)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_staging_prices_canonical_id ON fhq_market.staging_prices(canonical_id);
CREATE INDEX IF NOT EXISTS idx_staging_prices_timestamp ON fhq_market.staging_prices(timestamp);
CREATE INDEX IF NOT EXISTS idx_staging_prices_batch_id ON fhq_market.staging_prices(batch_id);
CREATE INDEX IF NOT EXISTS idx_staging_prices_asset_time ON fhq_market.staging_prices(canonical_id, timestamp DESC);

COMMENT ON TABLE fhq_market.staging_prices IS 'Staging table for raw OHLCV data before canonicalization. No writes to fhq_market.prices until STIG validates.';

-- =====================================================
-- STEP 3: Create ingestion_batches table for lineage
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_market.ingestion_batches (
    batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Operation metadata
    operation TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS',

    -- Scope
    assets_requested TEXT[] NOT NULL,
    assets_ingested TEXT[],

    -- Time window
    start_date DATE,
    end_date DATE,

    -- Statistics
    rows_count INTEGER DEFAULT 0,
    rows_failed INTEGER DEFAULT 0,

    -- Lineage (ADR-002)
    dataset_hash TEXT,  -- SHA-256 of entire dataset
    source TEXT NOT NULL DEFAULT 'yfinance',

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_by TEXT NOT NULL DEFAULT 'CODE',

    -- Evidence reference
    evidence_path TEXT
);

COMMENT ON TABLE fhq_market.ingestion_batches IS 'Tracks all data ingestion operations for audit and lineage (ADR-002).';

-- =====================================================
-- STEP 4: Register IoS-001 Canonical Assets
-- =====================================================

-- First, ensure exchanges exist
INSERT INTO fhq_meta.exchanges (mic, exchange_name, country_code, timezone, region)
VALUES
    ('XCRY', 'Cryptocurrency Global', 'XX', 'UTC', 'GLOBAL'),
    ('XFOR', 'Forex Global', 'XX', 'UTC', 'GLOBAL')
ON CONFLICT (mic) DO NOTHING;

-- Register IoS-001 canonical assets
INSERT INTO fhq_meta.assets (
    canonical_id,
    ticker,
    exchange_mic,
    asset_class,
    currency,
    lot_size,
    tick_size,
    sector,
    risk_profile,
    active_flag
)
VALUES
    ('BTC-USD', 'BTC-USD', 'XCRY', 'CRYPTO', 'USD', 0.00001, 0.01, 'DIGITAL_ASSETS', 'HIGH', TRUE),
    ('ETH-USD', 'ETH-USD', 'XCRY', 'CRYPTO', 'USD', 0.0001, 0.01, 'DIGITAL_ASSETS', 'HIGH', TRUE),
    ('SOL-USD', 'SOL-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'DIGITAL_ASSETS', 'HIGH', TRUE),
    ('EURUSD', 'EURUSD=X', 'XFOR', 'FX', 'USD', 1000, 0.00001, 'CURRENCY', 'MEDIUM', TRUE)
ON CONFLICT (canonical_id) DO UPDATE SET
    active_flag = TRUE,
    updated_at = NOW();

-- =====================================================
-- STEP 5: Register pipeline task in orchestrator (ADR-007)
-- =====================================================

INSERT INTO fhq_governance.task_registry (
    task_id,
    task_name,
    task_type,
    task_scope,
    owned_by_agent,
    executed_by_agent,
    reads_from_schemas,
    writes_to_schemas,
    gate_level,
    description,
    task_status,
    created_by
)
VALUES (
    gen_random_uuid(),
    'GENESIS_INGESTION',
    'DATA_PIPELINE',
    'FETCH_PRICES',
    'LINE',
    'CODE',
    ARRAY['fhq_meta'],
    ARRAY['fhq_market'],
    'G1',
    'OPERATION DATA FIRST: Ingest 10-year historical OHLCV for IoS-001 universe (BTC-USD, ETH-USD, SOL-USD, EURUSD)',
    'REGISTERED',
    'STIG'
)
ON CONFLICT DO NOTHING;

-- =====================================================
-- STEP 6: Log governance action (ADR-002)
-- =====================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    hash_chain_id,
    signature_id
)
VALUES (
    gen_random_uuid(),
    'SCHEMA_CREATION',
    'fhq_market.staging_prices',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'GENESIS_INGESTION_INFRASTRUCTURE: Created fhq_market schema with staging_prices and ingestion_batches tables. Registered IoS-001 assets (BTC-USD, ETH-USD, SOL-USD, EURUSD). Authority: ADR-013, ADR-007, ADR-002, IoS-001.',
    'GENESIS-INGEST-' || to_char(NOW(), 'YYYYMMDD-HH24MISS'),
    gen_random_uuid()
);

COMMIT;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify schema created
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'fhq_market';

-- Verify tables created
SELECT table_name FROM information_schema.tables WHERE table_schema = 'fhq_market';

-- Verify assets registered
SELECT canonical_id, ticker, asset_class, active_flag FROM fhq_meta.assets WHERE active_flag = TRUE;

-- =====================================================
-- END OF MIGRATION 022
-- =====================================================
