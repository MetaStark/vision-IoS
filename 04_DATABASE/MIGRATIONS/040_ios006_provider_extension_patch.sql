-- =============================================================================
-- IoS-006 PROVIDER EXTENSION PATCH
-- Migration: 040_ios006_provider_extension_patch.sql
-- =============================================================================
-- Authority: LARS (Strategy & Governance)
-- Executor: STIG (CTO) + CODE (EC-011)
-- ADR Compliance: ADR-011, ADR-012, ADR-013
-- Hash Chain: HC-IOS-006-2026
-- =============================================================================
-- Purpose:
--   Extend the Multi-Provider Canonical Router with:
--   - Changelly (crypto swap/execution intelligence)
--   - Bitquery (blockchain/on-chain intelligence)
--   - Ensure Binance is fully integrated
--
-- Design Constraints:
--   - Changelly/Bitquery are NOT macro providers (IoS-006)
--   - They ARE canonical providers for future IoS-008, IoS-009, IoS-010
--   - Registration now ensures lineage continuity and health check coverage
-- =============================================================================

BEGIN;

-- =============================================================================
-- STEP 0: ADD 'BLOCKCHAIN_INTELLIGENCE' TO PROVIDER CATEGORY CHECK
-- =============================================================================

ALTER TABLE fhq_macro.provider_quota_state
DROP CONSTRAINT IF EXISTS provider_quota_state_provider_category_check;

ALTER TABLE fhq_macro.provider_quota_state
ADD CONSTRAINT provider_quota_state_provider_category_check
CHECK (provider_category = ANY (ARRAY[
    'MARKET_DATA'::text,
    'NEWS_NARRATIVE'::text,
    'CRYPTO_EXCHANGE'::text,
    'LLM_PROVIDER'::text,
    'CALCULATED'::text,
    'BLOCKCHAIN_INTELLIGENCE'::text
]));

-- =============================================================================
-- STEP 1: PROVIDER REGISTRY EXTENSION
-- =============================================================================
-- Add Changelly and Bitquery to provider_quota_state
-- Binance already exists from migration 039

-- Insert/Update Changelly (crypto swap/routing - future IoS-010)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id,
    provider_name,
    provider_type,
    daily_limit,
    used_today,
    canonical_source_preference,
    requires_api_key,
    api_key_env_var,
    health_status,
    provider_category,
    reset_time_utc,
    is_active,
    created_at,
    updated_at,
    created_by
) VALUES (
    'changelly',
    'Changelly Exchange',
    'EXCHANGE',
    10000,
    0,
    2,  -- Exchange-grade
    TRUE,
    'CHANGELLY_API_KEY',
    'UNKNOWN',
    'CRYPTO_EXCHANGE',
    '00:00:00',
    TRUE,
    NOW(),
    NOW(),
    'STIG'
) ON CONFLICT (provider_id) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    daily_limit = EXCLUDED.daily_limit,
    canonical_source_preference = EXCLUDED.canonical_source_preference,
    provider_category = EXCLUDED.provider_category,
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- Insert Bitquery (blockchain intelligence - future IoS-008, IoS-009)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id,
    provider_name,
    provider_type,
    daily_limit,
    used_today,
    canonical_source_preference,
    requires_api_key,
    api_key_env_var,
    health_status,
    provider_category,
    reset_time_utc,
    is_active,
    created_at,
    updated_at,
    created_by
) VALUES (
    'bitquery',
    'Bitquery GraphQL',
    'AGGREGATOR',
    50000,
    0,
    2,  -- Exchange-grade (on-chain data is authoritative)
    TRUE,
    'BITQUERY_API_KEY',
    'UNKNOWN',
    'BLOCKCHAIN_INTELLIGENCE',
    '00:00:00',
    TRUE,
    NOW(),
    NOW(),
    'STIG'
) ON CONFLICT (provider_id) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    daily_limit = EXCLUDED.daily_limit,
    canonical_source_preference = EXCLUDED.canonical_source_preference,
    provider_category = EXCLUDED.provider_category,
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- =============================================================================
-- STEP 2: FEATURE REGISTRY EXTENSION (On-Chain Features)
-- =============================================================================
-- Register future IoS-008/009/010 features in the macro registry
-- These will NOT be ingested by IoS-006 but must exist for router capability mapping

-- Bitquery on-chain features (IoS-008: On-Chain Factor Engine)
-- Note: feature_registry uses 'cluster' not 'cluster_id', 'provenance' not 'provenance_source'
INSERT INTO fhq_macro.feature_registry (
    feature_id, feature_name, description, provenance, source_ticker,
    frequency, lag_period_days, cluster, hypothesis, status,
    created_by, created_at, updated_at
) VALUES
    ('BTC_ONCHAIN_SUPPLY', 'Bitcoin On-Chain Supply',
     'Total BTC supply visible on-chain', 'BITQUERY', 'BTC',
     'DAILY', 0, 'ONCHAIN', 'On-chain supply dynamics precede price movements', 'CANDIDATE',
     'STIG', NOW(), NOW()),
    ('BTC_EXCHANGE_FLOW', 'Bitcoin Exchange Flow',
     'Net BTC flow into/out of exchanges', 'BITQUERY', 'BTC_FLOW',
     'DAILY', 0, 'ONCHAIN', 'Exchange inflows/outflows signal accumulation vs distribution', 'CANDIDATE',
     'STIG', NOW(), NOW()),
    ('BTC_MINER_RESERVES', 'Bitcoin Miner Reserves',
     'BTC held by mining pools', 'BITQUERY', 'BTC_MINER',
     'DAILY', 0, 'ONCHAIN', 'Miner reserve changes indicate selling pressure', 'CANDIDATE',
     'STIG', NOW(), NOW()),
    ('ETH_ONCHAIN_SUPPLY', 'Ethereum On-Chain Supply',
     'Total ETH supply post-merge', 'BITQUERY', 'ETH',
     'DAILY', 0, 'ONCHAIN', 'ETH supply dynamics after merge affect macro conditions', 'CANDIDATE',
     'STIG', NOW(), NOW()),
    ('ETH_EXCHANGE_FLOW', 'Ethereum Exchange Flow',
     'Net ETH flow into/out of exchanges', 'BITQUERY', 'ETH_FLOW',
     'DAILY', 0, 'ONCHAIN', 'ETH exchange flows signal institutional positioning', 'CANDIDATE',
     'STIG', NOW(), NOW())
ON CONFLICT (feature_id) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = NOW();

-- Changelly swap features (IoS-010: Execution Intelligence)
-- Note: 'SWAP' cluster doesn't exist, use 'OTHER' instead
INSERT INTO fhq_macro.feature_registry (
    feature_id, feature_name, description, provenance, source_ticker,
    frequency, lag_period_days, cluster, hypothesis, status,
    created_by, created_at, updated_at
) VALUES
    ('BTC_SWAP_LIQUIDITY', 'Bitcoin Swap Liquidity',
     'Cross-exchange BTC swap liquidity depth', 'CHANGELLY', 'BTC_SWAP',
     'HOURLY', 0, 'OTHER', 'Cross-exchange swap liquidity indicates arbitrage capacity', 'CANDIDATE',
     'STIG', NOW(), NOW()),
    ('ETH_SWAP_LIQUIDITY', 'Ethereum Swap Liquidity',
     'Cross-exchange ETH swap liquidity depth', 'CHANGELLY', 'ETH_SWAP',
     'HOURLY', 0, 'OTHER', 'ETH swap liquidity affects execution slippage', 'CANDIDATE',
     'STIG', NOW(), NOW())
ON CONFLICT (feature_id) DO UPDATE SET
    description = EXCLUDED.description,
    updated_at = NOW();

-- =============================================================================
-- STEP 3: CAPABILITY MATRIX EXTENSION
-- =============================================================================
-- Map Bitquery to on-chain features
INSERT INTO fhq_macro.provider_capability (
    provider_id, feature_id, ticker_symbol, endpoint_path,
    is_active, created_at, updated_at
) VALUES
    -- Bitquery on-chain capabilities
    ('bitquery', 'BTC_ONCHAIN_SUPPLY', 'BTC', 'graphql.bitquery.io',
     TRUE, NOW(), NOW()),
    ('bitquery', 'BTC_EXCHANGE_FLOW', 'BTC_FLOW', 'graphql.bitquery.io',
     TRUE, NOW(), NOW()),
    ('bitquery', 'BTC_MINER_RESERVES', 'BTC_MINER', 'graphql.bitquery.io',
     TRUE, NOW(), NOW()),
    ('bitquery', 'ETH_ONCHAIN_SUPPLY', 'ETH', 'graphql.bitquery.io',
     TRUE, NOW(), NOW()),
    ('bitquery', 'ETH_EXCHANGE_FLOW', 'ETH_FLOW', 'graphql.bitquery.io',
     TRUE, NOW(), NOW())
ON CONFLICT (provider_id, feature_id) DO NOTHING;

-- Map Changelly to swap features
INSERT INTO fhq_macro.provider_capability (
    provider_id, feature_id, ticker_symbol, endpoint_path,
    is_active, created_at, updated_at
) VALUES
    ('changelly', 'BTC_SWAP_LIQUIDITY', 'BTC_SWAP', 'api.changelly.com',
     TRUE, NOW(), NOW()),
    ('changelly', 'ETH_SWAP_LIQUIDITY', 'ETH_SWAP', 'api.changelly.com',
     TRUE, NOW(), NOW())
ON CONFLICT (provider_id, feature_id) DO NOTHING;

-- =============================================================================
-- STEP 4: ENSURE BINANCE IS NOT MAPPED TO MACRO FEATURES
-- =============================================================================
-- Binance provides crypto prices, not macro indicators
-- Explicitly mark any accidental macro mappings as inactive

UPDATE fhq_macro.provider_capability
SET is_active = FALSE
WHERE provider_id = 'binance'
  AND feature_id IN (
      SELECT feature_id FROM fhq_macro.feature_registry
      WHERE cluster IN ('LIQUIDITY', 'CREDIT', 'VOLATILITY', 'FACTOR')
  );

-- =============================================================================
-- STEP 5: GOVERNANCE LOGGING
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    vega_reviewed,
    hash_chain_id,
    signature_id
) VALUES (
    'IOS_MODULE_PROVIDER_EXTENSION',
    'IoS-006',
    'IOS_MODULE',
    'LARS',
    NOW(),
    'APPROVED',
    'Extended Multi-Provider Router with Changelly (crypto swap), Bitquery (blockchain intelligence). ' ||
    'These providers are registered for lineage continuity and future IoS-008/009/010 integration. ' ||
    'They are NOT active for IoS-006 macro features. ADR Compliance: ADR-011, ADR-012, ADR-013.',
    FALSE,
    'HC-IOS-006-2026',
    gen_random_uuid()
);

-- =============================================================================
-- STEP 6: UPDATE IoS REGISTRY
-- =============================================================================

UPDATE fhq_meta.ios_registry
SET
    description = description || ' [G2.6.1: Provider Extension Patch - Added Changelly, Bitquery]',
    updated_at = NOW()
WHERE ios_id = 'IOS-006';

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Check new providers
SELECT provider_id, provider_name, daily_limit, canonical_source_preference, health_status, provider_category
FROM fhq_macro.provider_quota_state
WHERE provider_id IN ('changelly', 'bitquery', 'binance')
ORDER BY provider_id;

-- Check new features
SELECT feature_id, cluster, provenance, status
FROM fhq_macro.feature_registry
WHERE cluster IN ('ONCHAIN', 'OTHER')
  AND feature_id LIKE '%SWAP%' OR feature_id LIKE '%ONCHAIN%' OR feature_id LIKE '%EXCHANGE_FLOW%' OR feature_id LIKE '%MINER%'
ORDER BY feature_id;

-- Check capability mappings
SELECT pc.provider_id, pc.feature_id, pc.is_active, fr.cluster
FROM fhq_macro.provider_capability pc
JOIN fhq_macro.feature_registry fr ON pc.feature_id = fr.feature_id
WHERE pc.provider_id IN ('changelly', 'bitquery')
ORDER BY pc.provider_id, pc.feature_id;
