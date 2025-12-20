-- ============================================================================
-- MIGRATION 103: IoS-001 Vendor Compliance Registration
-- ============================================================================
-- Authority: CEO Directive - IoS-001 Compliance Audit 2025-12-09
-- Executed By: STIG (CTO)
-- Classification: Tier-2 Technical Executive
-- ADR Reference: ADR-012 (API Waterfall), IoS-001 (Canonical Registry)
-- ============================================================================

BEGIN;

-- ============================================================================
-- 0. EXTEND CONSTRAINTS TO SUPPORT EXECUTION BROKER TYPE
-- ============================================================================
-- Add EXECUTION to provider_type constraint (required for Alpaca broker)
-- Add EXECUTION to usage_tier constraint (special tier for brokers)

ALTER TABLE fhq_governance.api_provider_registry
    DROP CONSTRAINT IF EXISTS api_provider_registry_provider_type_check;

ALTER TABLE fhq_governance.api_provider_registry
    ADD CONSTRAINT api_provider_registry_provider_type_check
    CHECK (provider_type = ANY (ARRAY[
        'MARKET_DATA'::text,
        'NEWS'::text,
        'MACRO'::text,
        'SEARCH'::text,
        'ANALYTICS'::text,
        'LLM'::text,
        'EXECUTION'::text  -- NEW: Broker/execution providers
    ]));

ALTER TABLE fhq_governance.api_provider_registry
    DROP CONSTRAINT IF EXISTS api_provider_registry_usage_tier_check;

ALTER TABLE fhq_governance.api_provider_registry
    ADD CONSTRAINT api_provider_registry_usage_tier_check
    CHECK (usage_tier = ANY (ARRAY[
        'LAKE'::text,
        'PULSE'::text,
        'SNIPER'::text,
        'TIER_1'::text,
        'TIER_2'::text,
        'TIER_3'::text,
        'EXECUTION'::text  -- NEW: Broker tier
    ]));

-- ============================================================================
-- 1. REGISTER BINANCE API (LAKE Tier - Free Public Endpoints)
-- ============================================================================
-- Binance provides free public market data for crypto assets
-- Rate limit: 1200 requests/minute for public endpoints
-- No API key required for public data (klines, ticker, depth)

INSERT INTO fhq_governance.api_provider_registry (
    provider_id,
    provider_name,
    provider_type,
    usage_tier,
    base_url,
    daily_limit,
    rate_limit_per_minute,
    cost_per_call,
    requires_api_key,
    key_env_variable,
    is_active,
    metadata,
    created_at
) VALUES (
    gen_random_uuid(),
    'BINANCE',
    'MARKET_DATA',
    'LAKE',
    'https://api.binance.com',
    0,  -- Unlimited for public endpoints
    1200,  -- Binance rate limit: 1200 requests/minute
    0.00,
    false,  -- Public endpoints don't require API key
    'BINANCE_API_KEY',  -- Optional for authenticated endpoints
    true,
    jsonb_build_object(
        'ios001_registered', true,
        'registered_by', 'STIG',
        'registration_date', '2025-12-09',
        'registration_reason', 'CEO Directive IoS-001 Compliance Audit',
        'supported_assets', ARRAY['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD'],
        'data_types', ARRAY['spot', 'futures', 'klines', 'ticker', 'depth'],
        'api_version', 'v3',
        'documentation', 'https://binance-docs.github.io/apidocs/'
    ),
    NOW()
)
ON CONFLICT (provider_name) DO UPDATE SET
    is_active = true,
    metadata = fhq_governance.api_provider_registry.metadata ||
               jsonb_build_object('ios001_revalidated', NOW()::text);


-- ============================================================================
-- 2. REGISTER ALPACA API (EXECUTION Tier - Paper & Live Trading)
-- ============================================================================
-- Alpaca is the execution broker for IoS-012
-- Critical: Must be registered for governance compliance
-- Supports both Paper and Live trading environments

INSERT INTO fhq_governance.api_provider_registry (
    provider_id,
    provider_name,
    provider_type,
    usage_tier,
    base_url,
    daily_limit,
    rate_limit_per_minute,
    cost_per_call,
    requires_api_key,
    key_env_variable,
    is_active,
    metadata,
    created_at
) VALUES (
    gen_random_uuid(),
    'ALPACA',
    'EXECUTION',
    'EXECUTION',  -- Special tier for brokers
    'https://paper-api.alpaca.markets',  -- Paper trading endpoint
    0,  -- No daily call limit
    200,  -- 200 API calls per minute
    0.00,  -- No per-call cost (commission-free trading)
    true,
    'ALPACA_API_KEY',
    true,
    jsonb_build_object(
        'ios001_registered', true,
        'registered_by', 'STIG',
        'registration_date', '2025-12-09',
        'registration_reason', 'CEO Directive IoS-001 Compliance Audit - Execution Broker',
        'environments', jsonb_build_object(
            'paper', 'https://paper-api.alpaca.markets',
            'live', 'https://api.alpaca.markets'
        ),
        'current_environment', 'PAPER',
        'supported_assets', ARRAY['equities', 'crypto'],
        'order_types', ARRAY['market', 'limit', 'stop', 'stop_limit', 'trailing_stop'],
        'time_in_force', ARRAY['day', 'gtc', 'opg', 'cls', 'ioc', 'fok'],
        'ios012_integration', true,
        'secret_env_variable', 'ALPACA_SECRET_KEY',
        'documentation', 'https://docs.alpaca.markets/'
    ),
    NOW()
)
ON CONFLICT (provider_name) DO UPDATE SET
    is_active = true,
    metadata = fhq_governance.api_provider_registry.metadata ||
               jsonb_build_object('ios001_revalidated', NOW()::text);


-- ============================================================================
-- 3. LOG GOVERNANCE ACTION
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
    vega_override,
    vega_notes,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'IOS001_VENDOR_REGISTRATION',
    'api_provider_registry',
    'COMPLIANCE_REMEDIATION',
    'STIG',
    NOW(),
    'APPROVED',
    'CEO Directive IoS-001 Compliance Audit 2025-12-09: Registered BINANCE (LAKE tier) and ALPACA (EXECUTION tier) to bring all API vendors into IoS-001 compliance.',
    false,  -- Pending VEGA review
    false,
    'Vendors registered: BINANCE, ALPACA. ADR references: ADR-012, IoS-001.',
    'IOS001_VENDOR_REG_' || to_char(NOW(), 'YYYYMMDD_HH24MISS')
);


-- ============================================================================
-- 4. VERIFICATION QUERY (Run after migration)
-- ============================================================================
-- SELECT provider_name, provider_type, usage_tier, is_active,
--        metadata->>'ios001_registered' as ios001_compliant
-- FROM fhq_governance.api_provider_registry
-- WHERE provider_name IN ('BINANCE', 'ALPACA')
-- ORDER BY provider_name;


COMMIT;

-- ============================================================================
-- EXECUTION INSTRUCTIONS
-- ============================================================================
-- Run this migration with:
-- psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -f 04_DATABASE/MIGRATIONS/103_ios001_vendor_compliance_registration.sql
-- ============================================================================
