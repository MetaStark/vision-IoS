-- ============================================================================
-- Migration 110: IoS-001 Schema Alignment
-- CEO Directive: Data Backfill & Price Semantics Enforcement
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-002 (Audit)
-- IoS Reference: IoS-001 §2.1, §3.4, §4.1, §4.5
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: Create data_quality_status ENUM (CEO Directive)
-- ============================================================================
-- Defines the "Iron Curtain" quarantine states for asset data maturity

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'data_quality_status') THEN
        CREATE TYPE data_quality_status AS ENUM (
            'QUARANTINED',       -- < 252/365 rows, NO signals allowed (Iron Curtain)
            'SHORT_HISTORY',     -- 252-1260 / 365-1825 rows, flagged in IoS-003
            'FULL_HISTORY',      -- > 1260/1825 rows (5 years), full Alpha member
            'DELISTED_RETAINED'  -- Inactive but preserved for backtest (survivorship)
        );
        COMMENT ON TYPE data_quality_status IS 'IoS-001 §4.1 Data Quality Status - CEO Directive for Iron Curtain enforcement';
    END IF;
END $$;

-- ============================================================================
-- PART B: Extend fhq_meta.assets table (§4.1 Onboarding Criteria)
-- ============================================================================

-- Add data quality and onboarding columns
ALTER TABLE fhq_meta.assets
    ADD COLUMN IF NOT EXISTS min_daily_volume_usd NUMERIC,
    ADD COLUMN IF NOT EXISTS required_history_days INTEGER DEFAULT 252,
    ADD COLUMN IF NOT EXISTS gap_policy TEXT,
    ADD COLUMN IF NOT EXISTS liquidity_tier TEXT,
    ADD COLUMN IF NOT EXISTS onboarding_date DATE,
    ADD COLUMN IF NOT EXISTS data_quality_score NUMERIC(5,2);

-- Add CEO Directive columns for data quality enforcement
ALTER TABLE fhq_meta.assets
    ADD COLUMN IF NOT EXISTS valid_row_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS quarantine_threshold INTEGER DEFAULT 252,
    ADD COLUMN IF NOT EXISTS full_history_threshold INTEGER DEFAULT 1260,
    ADD COLUMN IF NOT EXISTS price_source_field TEXT DEFAULT 'adj_close';

-- Add data_quality_status column (using the ENUM)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'fhq_meta'
        AND table_name = 'assets'
        AND column_name = 'data_quality_status'
    ) THEN
        ALTER TABLE fhq_meta.assets
        ADD COLUMN data_quality_status data_quality_status DEFAULT 'QUARANTINED';
    END IF;
END $$;

-- Add constraints for gap_policy (§4.1)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_gap_policy'
        AND table_schema = 'fhq_meta'
    ) THEN
        ALTER TABLE fhq_meta.assets
        ADD CONSTRAINT chk_gap_policy
        CHECK (gap_policy IS NULL OR gap_policy IN ('INTERPOLATE', 'FORWARD_FILL', 'SKIP_IF_GAP', 'FX_ADJUST'));
    END IF;
END $$;

-- Add constraint for price_source_field (Dual Price Ontology - GIPS Alignment)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_price_source'
        AND table_schema = 'fhq_meta'
    ) THEN
        ALTER TABLE fhq_meta.assets
        ADD CONSTRAINT chk_price_source
        CHECK (price_source_field IS NULL OR price_source_field IN ('adj_close', 'close'));
    END IF;
END $$;

-- Add constraint for liquidity_tier
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_liquidity_tier'
        AND table_schema = 'fhq_meta'
    ) THEN
        ALTER TABLE fhq_meta.assets
        ADD CONSTRAINT chk_liquidity_tier
        CHECK (liquidity_tier IS NULL OR liquidity_tier IN ('TIER_1', 'TIER_2', 'TIER_3', 'ILLIQUID'));
    END IF;
END $$;

-- ============================================================================
-- PART C: Extend fhq_meta.canonical_indicator_registry (§3.4)
-- ============================================================================

-- Add missing columns per IoS-001 §3.4 specification
ALTER TABLE fhq_meta.canonical_indicator_registry
    ADD COLUMN IF NOT EXISTS category TEXT,
    ADD COLUMN IF NOT EXISTS source_standard TEXT,
    ADD COLUMN IF NOT EXISTS ios_module TEXT DEFAULT 'IoS-002',
    ADD COLUMN IF NOT EXISTS formula_hash TEXT,
    ADD COLUMN IF NOT EXISTS vega_signature_id UUID,
    ADD COLUMN IF NOT EXISTS price_input_field TEXT DEFAULT 'adj_close';

-- Add constraint for category (GIPS-aligned indicator taxonomy)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_indicator_category'
        AND table_schema = 'fhq_meta'
    ) THEN
        ALTER TABLE fhq_meta.canonical_indicator_registry
        ADD CONSTRAINT chk_indicator_category
        CHECK (category IS NULL OR category IN ('MOMENTUM', 'TREND', 'VOLATILITY', 'ICHIMOKU', 'VOLUME', 'BREADTH'));
    END IF;
END $$;

-- Add constraint for price_input_field (Dual Price Ontology enforcement)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chk_indicator_price_input'
        AND table_schema = 'fhq_meta'
    ) THEN
        ALTER TABLE fhq_meta.canonical_indicator_registry
        ADD CONSTRAINT chk_indicator_price_input
        CHECK (price_input_field IS NULL OR price_input_field IN ('adj_close', 'close'));
    END IF;
END $$;

-- ============================================================================
-- PART D: Update existing assets with correct thresholds
-- ============================================================================

-- Set thresholds for Crypto assets (365/1825 for 24/7 markets)
UPDATE fhq_meta.assets
SET
    quarantine_threshold = 365,
    full_history_threshold = 1825,
    price_source_field = 'close',
    gap_policy = 'INTERPOLATE'
WHERE asset_class = 'CRYPTO';

-- Set thresholds for FX assets (252/1260 standard)
UPDATE fhq_meta.assets
SET
    quarantine_threshold = 252,
    full_history_threshold = 1260,
    price_source_field = 'close',
    gap_policy = 'FORWARD_FILL'
WHERE asset_class = 'FX';

-- Set thresholds for Equities (252/1260 standard, adj_close for signals)
UPDATE fhq_meta.assets
SET
    quarantine_threshold = 252,
    full_history_threshold = 1260,
    price_source_field = 'adj_close',
    gap_policy = 'SKIP_IF_GAP'
WHERE asset_class = 'EQUITY';

-- ============================================================================
-- PART E: Add comments for documentation
-- ============================================================================

COMMENT ON COLUMN fhq_meta.assets.data_quality_status IS
    'CEO Directive: Iron Curtain status - QUARANTINED blocks IoS-002/003 access';
COMMENT ON COLUMN fhq_meta.assets.valid_row_count IS
    'Actual row count with valid price data, not calendar days';
COMMENT ON COLUMN fhq_meta.assets.quarantine_threshold IS
    'Minimum rows before asset exits QUARANTINED (252 Equity/FX, 365 Crypto)';
COMMENT ON COLUMN fhq_meta.assets.full_history_threshold IS
    '5-year threshold for FULL_HISTORY status (1260 Equity/FX, 1825 Crypto)';
COMMENT ON COLUMN fhq_meta.assets.price_source_field IS
    'Dual Price Ontology: adj_close for signals (Equity), close for Crypto/FX';
COMMENT ON COLUMN fhq_meta.assets.gap_policy IS
    'Data gap handling: INTERPOLATE, FORWARD_FILL, SKIP_IF_GAP, FX_ADJUST';

COMMENT ON COLUMN fhq_meta.canonical_indicator_registry.category IS
    'GIPS-aligned indicator taxonomy: MOMENTUM, TREND, VOLATILITY, ICHIMOKU, VOLUME';
COMMENT ON COLUMN fhq_meta.canonical_indicator_registry.source_standard IS
    'Academic reference (e.g., Wilder 1978, Appel 1979)';
COMMENT ON COLUMN fhq_meta.canonical_indicator_registry.formula_hash IS
    'SHA-256 hash of calculation logic for reproducibility';
COMMENT ON COLUMN fhq_meta.canonical_indicator_registry.price_input_field IS
    'Dual Price Ontology: which price field indicators use';

-- ============================================================================
-- PART F: Governance Logging (ADR-002)
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
    'SCHEMA_MIGRATION',
    'fhq_meta.assets, fhq_meta.canonical_indicator_registry',
    'SCHEMA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §2.1/§3.4/§4.1 Schema Alignment - CEO Directive for Price Semantics & Data Quality Enforcement. Added data_quality_status ENUM, extended assets with onboarding criteria, extended canonical_indicator_registry with GIPS-aligned taxonomy.',
    false,
    'MIG-110-IOS001-SCHEMA-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART G: Hash Chain Registration (ADR-011)
-- ============================================================================

INSERT INTO vision_verification.hash_chains (
    chain_id,
    chain_type,
    chain_scope,
    genesis_hash,
    current_hash,
    chain_length,
    integrity_verified,
    created_by,
    created_at
) VALUES (
    'HC-IOS001-MIG110-' || TO_CHAR(NOW(), 'YYYYMMDD'),
    'MIGRATION',
    'IoS-001 Schema Alignment',
    encode(sha256('MIG-110-IOS001-SCHEMA-ALIGNMENT'::bytea), 'hex'),
    encode(sha256(('MIG-110-IOS001-' || NOW()::text)::bytea), 'hex'),
    1,
    true,
    'STIG',
    NOW()
) ON CONFLICT (chain_id) DO UPDATE SET
    current_hash = EXCLUDED.current_hash,
    chain_length = vision_verification.hash_chains.chain_length + 1,
    updated_at = NOW();

COMMIT;

-- ============================================================================
-- Migration 110 Complete
-- Next: Migration 111 (Exchange Registration)
-- ============================================================================
