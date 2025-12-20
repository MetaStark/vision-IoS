-- =====================================================
-- MIGRATION 023: DAILY INGESTION INFRASTRUCTURE
-- =====================================================
-- Authority: ADR-013, ADR-007, ADR-002, IoS-001
-- Purpose: Create canonical prices table and reconciliation infrastructure
-- Owner: STIG (CTO)
-- Date: 2025-11-29
-- =====================================================

BEGIN;

-- =====================================================
-- STEP 1: Create canonical prices table (fhq_market.prices)
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_market.prices (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Asset reference
    asset_id UUID NOT NULL,
    canonical_id TEXT NOT NULL,

    -- OHLCV data (canonical, validated)
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    open FLOAT8 NOT NULL,
    high FLOAT8 NOT NULL,
    low FLOAT8 NOT NULL,
    close FLOAT8 NOT NULL,
    volume FLOAT8 NOT NULL,

    -- Canonicalization metadata
    source TEXT NOT NULL DEFAULT 'yfinance',
    staging_id UUID,  -- Reference to staging_prices.id
    data_hash TEXT NOT NULL,

    -- Quality flags
    gap_filled BOOLEAN DEFAULT FALSE,
    interpolated BOOLEAN DEFAULT FALSE,
    quality_score FLOAT8 DEFAULT 1.0,

    -- Lineage (ADR-002)
    batch_id UUID NOT NULL,
    canonicalized_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    canonicalized_by TEXT NOT NULL DEFAULT 'STIG',

    -- VEGA attestation
    vega_reconciled BOOLEAN DEFAULT FALSE,
    vega_reconciled_at TIMESTAMP WITH TIME ZONE,
    vega_attestation_id UUID,

    -- Constraints
    CONSTRAINT prices_ohlc_valid CHECK (
        high >= low AND
        high >= open AND
        high >= close AND
        low <= open AND
        low <= close
    ),
    CONSTRAINT prices_positive CHECK (
        open > 0 AND high > 0 AND low > 0 AND close > 0
    ),

    -- Unique constraint
    CONSTRAINT prices_unique_asset_timestamp UNIQUE (canonical_id, timestamp)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prices_canonical_id ON fhq_market.prices(canonical_id);
CREATE INDEX IF NOT EXISTS idx_prices_timestamp ON fhq_market.prices(timestamp);
CREATE INDEX IF NOT EXISTS idx_prices_asset_time ON fhq_market.prices(canonical_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_prices_batch_id ON fhq_market.prices(batch_id);
CREATE INDEX IF NOT EXISTS idx_prices_vega_reconciled ON fhq_market.prices(vega_reconciled);

COMMENT ON TABLE fhq_market.prices IS 'Canonical OHLCV price data. Only STIG may write here after VEGA reconciliation.';

-- =====================================================
-- STEP 2: Create gap tracking table
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_market.data_gaps (
    gap_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Asset and time range
    canonical_id TEXT NOT NULL,
    gap_start DATE NOT NULL,
    gap_end DATE NOT NULL,
    gap_days INTEGER NOT NULL,

    -- Status
    status TEXT NOT NULL DEFAULT 'DETECTED',  -- DETECTED, BACKFILLING, FILLED, IGNORED

    -- Resolution
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by TEXT,
    resolution_batch_id UUID,

    -- Metadata
    expected_rows INTEGER,
    actual_rows INTEGER,
    notes TEXT,

    CONSTRAINT data_gaps_status_check CHECK (
        status IN ('DETECTED', 'BACKFILLING', 'FILLED', 'IGNORED')
    )
);

CREATE INDEX IF NOT EXISTS idx_data_gaps_status ON fhq_market.data_gaps(status);
CREATE INDEX IF NOT EXISTS idx_data_gaps_canonical ON fhq_market.data_gaps(canonical_id);

COMMENT ON TABLE fhq_market.data_gaps IS 'Tracks detected data gaps and backfill status for each asset.';

-- =====================================================
-- STEP 3: Create daily ingest schedule table
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_market.ingest_schedule (
    schedule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Schedule config
    schedule_name TEXT NOT NULL UNIQUE,
    cron_expression TEXT NOT NULL,  -- e.g., "5 0 * * *" for 00:05 UTC daily
    timezone TEXT NOT NULL DEFAULT 'UTC',

    -- Scope
    assets TEXT[] NOT NULL,
    pipeline_stage TEXT NOT NULL,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_run_status TEXT,
    last_run_batch_id UUID,
    next_run_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG',

    CONSTRAINT ingest_schedule_status_check CHECK (
        last_run_status IS NULL OR last_run_status IN ('SUCCESS', 'PARTIAL', 'FAILED', 'RUNNING')
    )
);

-- Insert daily schedule
INSERT INTO fhq_market.ingest_schedule (
    schedule_name,
    cron_expression,
    timezone,
    assets,
    pipeline_stage,
    is_active,
    next_run_at
) VALUES (
    'DAILY_OHLCV_INGEST',
    '5 0 * * *',
    'UTC',
    ARRAY['BTC-USD', 'ETH-USD', 'SOL-USD', 'EURUSD'],
    'FETCH_PRICES',
    TRUE,
    (CURRENT_DATE + INTERVAL '1 day' + INTERVAL '5 minutes')::TIMESTAMP WITH TIME ZONE
) ON CONFLICT (schedule_name) DO UPDATE SET
    assets = EXCLUDED.assets,
    is_active = TRUE;

-- =====================================================
-- STEP 4: Create reconciliation log table
-- =====================================================

CREATE TABLE IF NOT EXISTS fhq_market.reconciliation_log (
    reconciliation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Scope
    batch_id UUID NOT NULL,
    canonical_id TEXT,  -- NULL means all assets in batch

    -- Reconciliation results
    staging_rows INTEGER NOT NULL,
    canonical_rows INTEGER NOT NULL,
    rows_added INTEGER DEFAULT 0,
    rows_updated INTEGER DEFAULT 0,
    rows_rejected INTEGER DEFAULT 0,

    -- Hashes
    staging_hash TEXT,
    canonical_hash TEXT,
    hashes_match BOOLEAN,

    -- VEGA decision
    vega_decision TEXT NOT NULL,  -- APPROVED, REJECTED, PENDING
    vega_notes TEXT,
    vega_attestation_id UUID,

    -- Timestamps
    reconciled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reconciled_by TEXT NOT NULL DEFAULT 'VEGA',

    CONSTRAINT reconciliation_decision_check CHECK (
        vega_decision IN ('APPROVED', 'REJECTED', 'PENDING')
    )
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_batch ON fhq_market.reconciliation_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_reconciliation_decision ON fhq_market.reconciliation_log(vega_decision);

COMMENT ON TABLE fhq_market.reconciliation_log IS 'VEGA reconciliation decisions for staging → canonical promotion.';

-- =====================================================
-- STEP 5: Log governance action
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
    'SCHEMA_EXTENSION',
    'fhq_market',
    'TABLES',
    'STIG',
    NOW(),
    'APPROVED',
    'DAILY_INGESTION_INFRASTRUCTURE: Created prices (canonical), data_gaps, ingest_schedule, reconciliation_log tables. Authority: ADR-013, ADR-007, ADR-002.',
    'DAILY-INGEST-INFRA-' || to_char(NOW(), 'YYYYMMDD-HH24MISS'),
    gen_random_uuid()
);

COMMIT;

-- =====================================================
-- VERIFICATION
-- =====================================================

SELECT table_name FROM information_schema.tables
WHERE table_schema = 'fhq_market'
ORDER BY table_name;

SELECT * FROM fhq_market.ingest_schedule;
