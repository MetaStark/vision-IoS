-- =============================================================================
-- MIGRATION 156: IoS-001 Canonical Price Architecture & Orchestrator Governance
-- =============================================================================
-- CEO Directive: CD-IOS-001-PRICE-ARCH-001
-- Date: 2025-12-18
-- Purpose: Register multi-tier price ontology, vendor roles, orchestrator authority
-- =============================================================================

BEGIN;

-- =============================================================================
-- SECTION 0: REGISTER IoS-001 IF NOT EXISTS
-- =============================================================================

INSERT INTO fhq_meta.ios_registry (
    ios_id, title, description, version, status, owner_role,
    governing_adrs, dependencies, content_hash, created_at, updated_at
) VALUES (
    'IoS-001',
    'Price Data Ingestion & Canonical Storage',
    'Foundation module for price data acquisition, validation, and canonical storage. '
    'Defines multi-tier price ontology (P1/P2/P3), vendor role classification, '
    'and orchestrator authority bindings per CEO Directive CD-IOS-001-PRICE-ARCH-001.',
    '3.5.0',
    'ACTIVE',
    'STIG',
    ARRAY['ADR-004', 'ADR-012', 'ADR-013'],
    ARRAY[]::TEXT[],
    encode(sha256('IoS-001-v3.5.0-2025-12-18'::bytea), 'hex'),
    NOW(),
    NOW()
) ON CONFLICT (ios_id) DO UPDATE SET
    version = '3.5.0',
    description = EXCLUDED.description,
    content_hash = encode(sha256('IoS-001-v3.5.0-2025-12-18'::bytea), 'hex'),
    updated_at = NOW();

-- =============================================================================
-- SECTION 1: CEO DIRECTIVE REGISTRATION
-- =============================================================================

INSERT INTO fhq_governance.governance_documents (
    document_id,
    document_name,
    document_type,
    tier,
    version,
    content,
    created_at,
    approved_by,
    status
) VALUES (
    gen_random_uuid(),
    'CD-IOS-001-PRICE-ARCH-001',
    'CEO_DIRECTIVE',
    1,
    '1.0.0',
    E'Executive Order – Canonical Price Architecture & Orchestrator Activation.\n\n'
    'STIG,\n\n'
    'Effective immediately, FjordHQ formalizes its price ingestion and storage architecture '
    'as a multi-tier, audit-safe system, in accordance with IoS-001 §3.5 (added 2025-12-18), '
    'ADR-004 and ADR-013.\n\n'
    '1. CANONICAL AUTHORITY\n'
    'fhq_market.prices is reaffirmed as the sole canonical daily price store.\n\n'
    '2. VENDOR ROLE ENFORCEMENT\n'
    'All price vendors must be registered with explicit Vendor Roles.\n\n'
    '3. ORCHESTRATOR ACTIVATION\n'
    'FHQ-IoS001-Bulletproof-CRYPTO, FHQ-IoS001-Bulletproof-EQUITY, FHQ-IoS001-Bulletproof-FX '
    'are hereby constitutionally authorized.\n\n'
    '4. DECOUPLING MANDATE\n'
    'Regime engines never depend on intraday freshness. '
    'Execution engines never depend on canonical daily completeness.\n\n'
    'Signed, CEO – FjordHQ',
    NOW(),
    'CEO',
    'ACTIVE'
);

-- =============================================================================
-- SECTION 2: PRICE CLASS ONTOLOGY (P1, P2, P3)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_meta.price_class_ontology (
    price_class_id TEXT PRIMARY KEY,
    price_class_name TEXT NOT NULL,
    description TEXT NOT NULL,
    storage_policy TEXT NOT NULL,
    permitted_use TEXT[] NOT NULL,
    ttl_hours INTEGER,
    immutable BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO fhq_meta.price_class_ontology (price_class_id, price_class_name, description, storage_policy, permitted_use, ttl_hours, immutable)
VALUES
    ('P1', 'CANONICAL_DAILY_PRICE', 'Official end-of-session OHLCV', 'IMMUTABLE', ARRAY['regime', 'risk', 'backtest', 'indicators'], NULL, TRUE),
    ('P2', 'OPERATIONAL_INTRADAY_PRICE', 'Live or near-real-time prices', 'EPHEMERAL', ARRAY['execution', 'freshness_gates', 'paper_trading'], 48, FALSE),
    ('P3', 'HISTORICAL_BACKFILL_PRICE', 'One-time historical imports', 'WRITE_ONCE', ARRAY['gap_repair', 'bootstrap', 'backfill'], NULL, TRUE)
ON CONFLICT (price_class_id) DO UPDATE SET
    description = EXCLUDED.description,
    storage_policy = EXCLUDED.storage_policy,
    permitted_use = EXCLUDED.permitted_use;

-- =============================================================================
-- SECTION 3: VENDOR ROLE EXTENSION
-- =============================================================================

-- Add vendor_role column to existing vendors table if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_meta'
                   AND table_name = 'vendors'
                   AND column_name = 'vendor_role') THEN
        ALTER TABLE fhq_meta.vendors ADD COLUMN vendor_role TEXT[];
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_meta'
                   AND table_name = 'vendors'
                   AND column_name = 'price_class_authority') THEN
        ALTER TABLE fhq_meta.vendors ADD COLUMN price_class_authority TEXT[];
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_meta'
                   AND table_name = 'vendors'
                   AND column_name = 'asset_classes') THEN
        ALTER TABLE fhq_meta.vendors ADD COLUMN asset_classes TEXT[];
    END IF;
END $$;

-- Create vendor role reference table
CREATE TABLE IF NOT EXISTS fhq_meta.vendor_role_definitions (
    role_id TEXT PRIMARY KEY,
    role_name TEXT NOT NULL,
    description TEXT NOT NULL,
    can_write_canonical BOOLEAN DEFAULT FALSE,
    can_write_operational BOOLEAN DEFAULT FALSE,
    can_write_backfill BOOLEAN DEFAULT FALSE,
    priority_order INTEGER DEFAULT 99,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO fhq_meta.vendor_role_definitions (role_id, role_name, description, can_write_canonical, can_write_operational, can_write_backfill, priority_order)
VALUES
    ('CANONICAL_PRIMARY', 'Canonical Primary', 'Authoritative daily price source', TRUE, FALSE, FALSE, 1),
    ('OPERATIONAL_FEED', 'Operational Feed', 'Live / intraday operational prices', FALSE, TRUE, FALSE, 2),
    ('BACKUP_ONLY', 'Backup Only', 'Secondary fallback source', FALSE, FALSE, FALSE, 3),
    ('BACKFILL_ONLY', 'Backfill Only', 'Historical one-time ingestion', FALSE, FALSE, TRUE, 4)
ON CONFLICT (role_id) DO NOTHING;

-- =============================================================================
-- SECTION 4: POPULATE VENDOR REGISTRY
-- =============================================================================

-- Clear and repopulate vendors with roles
DELETE FROM fhq_meta.vendors WHERE vendor_id IN ('binance', 'alpaca', 'coingecko', 'cryptodatadownload', 'yahoo_finance');

INSERT INTO fhq_meta.vendors (vendor_id, vendor_name, base_url, rate_limit_per_minute, requires_auth, vendor_role, price_class_authority, asset_classes)
VALUES
    ('binance', 'Binance', 'https://api.binance.com', 1200, FALSE,
     ARRAY['CANONICAL_PRIMARY', 'OPERATIONAL_FEED'],
     ARRAY['P1', 'P2'],
     ARRAY['crypto']),

    ('alpaca', 'Alpaca Markets', 'https://paper-api.alpaca.markets', 200, TRUE,
     ARRAY['CANONICAL_PRIMARY', 'OPERATIONAL_FEED'],
     ARRAY['P1', 'P2'],
     ARRAY['equity', 'etf']),

    ('coingecko', 'CoinGecko', 'https://api.coingecko.com', 30, FALSE,
     ARRAY['BACKUP_ONLY'],
     ARRAY[]::TEXT[],
     ARRAY['crypto']),

    ('cryptodatadownload', 'CryptoDataDownload', 'https://www.cryptodatadownload.com', 10, FALSE,
     ARRAY['BACKFILL_ONLY'],
     ARRAY['P3'],
     ARRAY['crypto']),

    ('yahoo_finance', 'Yahoo Finance', 'https://query1.finance.yahoo.com', 60, FALSE,
     ARRAY['BACKUP_ONLY', 'BACKFILL_ONLY'],
     ARRAY['P3'],
     ARRAY['equity', 'etf', 'fx', 'crypto'])
ON CONFLICT (vendor_id) DO UPDATE SET
    vendor_role = EXCLUDED.vendor_role,
    price_class_authority = EXCLUDED.price_class_authority,
    asset_classes = EXCLUDED.asset_classes;

-- =============================================================================
-- SECTION 5: ORCHESTRATOR AUTHORITY REGISTRY
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.orchestrator_authority (
    orchestrator_id TEXT PRIMARY KEY,
    orchestrator_name TEXT NOT NULL,
    scope TEXT NOT NULL,
    asset_classes TEXT[] NOT NULL,
    primary_vendor TEXT NOT NULL,
    fallback_vendors TEXT[],
    constitutional_authority BOOLEAN DEFAULT TRUE,
    enabled BOOLEAN DEFAULT TRUE,
    stop_conditions JSONB DEFAULT '{}',
    freshness_metrics_enabled BOOLEAN DEFAULT TRUE,
    fail_closed BOOLEAN DEFAULT TRUE,
    activated_by TEXT DEFAULT 'CEO',
    activated_at TIMESTAMPTZ DEFAULT NOW(),
    directive_reference TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO fhq_governance.orchestrator_authority (
    orchestrator_id, orchestrator_name, scope, asset_classes,
    primary_vendor, fallback_vendors, constitutional_authority,
    stop_conditions, directive_reference
)
VALUES
    ('FHQ-IoS001-Bulletproof-CRYPTO', 'Bulletproof Crypto Ingest',
     'Crypto daily OHLCV prices', ARRAY['crypto'],
     'binance', ARRAY['coingecko', 'yahoo_finance'], TRUE,
     '{"max_consecutive_failures": 3, "circuit_breaker_threshold": 5}',
     'CD-IOS-001-PRICE-ARCH-001'),

    ('FHQ-IoS001-Bulletproof-EQUITY', 'Bulletproof Equity Ingest',
     'Equity daily OHLCV prices', ARRAY['equity', 'etf'],
     'alpaca', ARRAY['yahoo_finance'], TRUE,
     '{"max_consecutive_failures": 3, "circuit_breaker_threshold": 5}',
     'CD-IOS-001-PRICE-ARCH-001'),

    ('FHQ-IoS001-Bulletproof-FX', 'Bulletproof FX Ingest',
     'FX daily rates', ARRAY['fx'],
     'yahoo_finance', ARRAY[]::TEXT[], TRUE,
     '{"max_consecutive_failures": 5, "circuit_breaker_threshold": 10}',
     'CD-IOS-001-PRICE-ARCH-001')
ON CONFLICT (orchestrator_id) DO UPDATE SET
    primary_vendor = EXCLUDED.primary_vendor,
    fallback_vendors = EXCLUDED.fallback_vendors,
    constitutional_authority = TRUE,
    activated_at = NOW();

-- =============================================================================
-- SECTION 6: IoS-001 §3.5 AMENDMENT REGISTRATION
-- =============================================================================

INSERT INTO fhq_governance.governance_instruments (
    instrument_id,
    instrument_name,
    instrument_type,
    ios_reference,
    status,
    constitutional,
    binding_scope,
    activation_gate,
    activated_by,
    activated_at,
    created_at
) VALUES (
    gen_random_uuid(),
    'IoS-001 §3.5 - Canonical Price Storage & Vendor Role Architecture',
    'IOS_AMENDMENT',
    'IoS-001',
    'ACTIVE',
    TRUE,
    ARRAY['STIG', 'LINE', 'CEIO', 'CDMO'],
    'G4',
    'CEO',
    NOW(),
    NOW()
);

-- =============================================================================
-- SECTION 7: FRESHNESS DECOUPLING ENFORCEMENT RULE
-- =============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.freshness_decoupling_rules (
    rule_id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    source_layer TEXT NOT NULL,
    target_layer TEXT NOT NULL,
    dependency_allowed BOOLEAN NOT NULL,
    violation_class TEXT NOT NULL,
    enforcement_mode TEXT DEFAULT 'HARD',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO fhq_governance.freshness_decoupling_rules (rule_id, rule_name, source_layer, target_layer, dependency_allowed, violation_class)
VALUES
    ('FDR-001', 'Regime Independence from Intraday', 'REGIME_ENGINE', 'OPERATIONAL_INTRADAY_PRICE', FALSE, 'CLASS_A'),
    ('FDR-002', 'Execution Independence from Canonical Completeness', 'EXECUTION_ENGINE', 'CANONICAL_DAILY_PRICE', FALSE, 'CLASS_A'),
    ('FDR-003', 'Backtest Uses Canonical Only', 'BACKTEST_ENGINE', 'OPERATIONAL_INTRADAY_PRICE', FALSE, 'CLASS_A'),
    ('FDR-004', 'Paper Trading Uses Operational', 'PAPER_TRADING', 'CANONICAL_DAILY_PRICE', FALSE, 'ADVISORY')
ON CONFLICT (rule_id) DO NOTHING;

-- =============================================================================
-- SECTION 8: CANONICAL PRICE TABLE CONSTRAINT ENFORCEMENT
-- =============================================================================

-- Add source tracking columns if not exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_market'
                   AND table_name = 'prices'
                   AND column_name = 'vendor_id') THEN
        ALTER TABLE fhq_market.prices ADD COLUMN vendor_id TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_market'
                   AND table_name = 'prices'
                   AND column_name = 'vendor_role') THEN
        ALTER TABLE fhq_market.prices ADD COLUMN vendor_role TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'fhq_market'
                   AND table_name = 'prices'
                   AND column_name = 'price_class') THEN
        ALTER TABLE fhq_market.prices ADD COLUMN price_class TEXT DEFAULT 'P1';
    END IF;
END $$;

-- =============================================================================
-- SECTION 9: AUDIT LOG ENTRY
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    metadata,
    agent_id,
    timestamp
) VALUES (
    gen_random_uuid(),
    'DIRECTIVE_ACTIVATION',
    'CD-IOS-001-PRICE-ARCH-001',
    'CEO_DIRECTIVE',
    'CEO',
    NOW(),
    'APPROVED',
    'Activated Canonical Price Architecture & Orchestrator Governance per CEO Directive CD-IOS-001-PRICE-ARCH-001',
    jsonb_build_object(
        'orchestrators_activated', ARRAY['FHQ-IoS001-Bulletproof-CRYPTO', 'FHQ-IoS001-Bulletproof-EQUITY', 'FHQ-IoS001-Bulletproof-FX'],
        'vendors_registered', ARRAY['binance', 'alpaca', 'coingecko', 'cryptodatadownload', 'yahoo_finance'],
        'price_classes_defined', ARRAY['P1', 'P2', 'P3'],
        'ios_amendment', 'IoS-001 §3.5'
    ),
    'STIG',
    NOW()
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES (run after commit)
-- =============================================================================

SELECT '=== PRICE CLASS ONTOLOGY ===' as section;
SELECT price_class_id, price_class_name, storage_policy, permitted_use FROM fhq_meta.price_class_ontology;

SELECT '=== VENDOR REGISTRY ===' as section;
SELECT vendor_id, vendor_name, vendor_role, price_class_authority, asset_classes
FROM fhq_meta.vendors WHERE vendor_role IS NOT NULL;

SELECT '=== ORCHESTRATOR AUTHORITY ===' as section;
SELECT orchestrator_id, scope, primary_vendor, constitutional_authority
FROM fhq_governance.orchestrator_authority;

SELECT '=== FRESHNESS DECOUPLING RULES ===' as section;
SELECT rule_id, rule_name, violation_class FROM fhq_governance.freshness_decoupling_rules;

SELECT '=== IoS-001 REGISTRY ===' as section;
SELECT ios_id, title, version, status FROM fhq_meta.ios_registry WHERE ios_id = 'IoS-001';
