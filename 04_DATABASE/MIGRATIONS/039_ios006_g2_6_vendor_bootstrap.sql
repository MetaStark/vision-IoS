-- ============================================================================
-- MIGRATION: 039_ios006_g2_6_vendor_bootstrap.sql
-- PURPOSE: IoS-006 G2.6 — Vendor Key Activation & Provider Bootstrap
-- AUTHORITY: LARS (Strategy & Governance)
-- EXECUTION: STIG (Technical) + CODE (EC-011)
-- GOVERNANCE: VEGA (Compliance)
-- ADR COMPLIANCE: ADR-001, ADR-011, ADR-012, ADR-013
-- STATUS: G2.6 VENDOR ACTIVATION
-- DATE: 2025-11-30
-- ============================================================================
--
-- STRATEGIC PURPOSE:
-- G2.5 etablerte Multi-Provider Canonical Router som arkitektur.
-- G2.6 gjør den operasjonell.
--
-- SCOPE:
-- - Market & Macro Vendors (Binance, TwelveData, Finnhub, etc.)
-- - News & Narrative Vendors (MarketAux, NewsAPI, etc.)
-- - Crypto Connectivity (Changelly)
-- - LLM Providers (registered for later IoS modules)
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: EXTEND PROVIDER_QUOTA_STATE SCHEMA
-- ============================================================================
-- Add fields for enhanced provider management

ALTER TABLE fhq_macro.provider_quota_state
ADD COLUMN IF NOT EXISTS reset_time_utc TIME,
ADD COLUMN IF NOT EXISTS provider_category TEXT CHECK (provider_category IN (
    'MARKET_DATA', 'NEWS_NARRATIVE', 'CRYPTO_EXCHANGE', 'LLM_PROVIDER', 'CALCULATED'
)),
ADD COLUMN IF NOT EXISTS latency_ms_avg INTEGER,
ADD COLUMN IF NOT EXISTS last_health_check TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS health_status TEXT DEFAULT 'UNKNOWN' CHECK (health_status IN (
    'ACTIVE', 'THROTTLED', 'ERROR', 'DISABLED', 'UNKNOWN'
)),
ADD COLUMN IF NOT EXISTS rate_limit_remaining INTEGER,
ADD COLUMN IF NOT EXISTS error_message TEXT;

-- ============================================================================
-- SECTION 2: REGISTER ALL G2.6 VENDORS
-- ============================================================================

-- ----- MARKET DATA & MACRO VENDORS -----

-- Binance (Crypto Exchange - Direct Feed)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'binance',
    'Binance Exchange',
    'EXCHANGE',
    'CRYPTO_EXCHANGE',
    1200, NULL, 1200,  -- 1200 requests/min on free tier
    '00:00:00',
    2, TRUE, 'UNKNOWN',
    'BINANCE_API_KEY', 'https://api.binance.com', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'CRYPTO_EXCHANGE',
    daily_limit = 1200,
    rate_limit_per_minute = 1200,
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- TwelveData (Exchange-Grade Market Data)
UPDATE fhq_macro.provider_quota_state
SET provider_category = 'MARKET_DATA',
    reset_time_utc = '00:00:00',
    health_status = 'UNKNOWN',
    updated_at = NOW()
WHERE provider_id = 'twelvedata';

-- Finnhub (Aggregator)
UPDATE fhq_macro.provider_quota_state
SET provider_category = 'MARKET_DATA',
    reset_time_utc = '00:00:00',
    health_status = 'UNKNOWN',
    updated_at = NOW()
WHERE provider_id = 'finnhub';

-- FMP (Aggregator)
UPDATE fhq_macro.provider_quota_state
SET provider_category = 'MARKET_DATA',
    reset_time_utc = '00:00:00',
    health_status = 'UNKNOWN',
    updated_at = NOW()
WHERE provider_id = 'fmp';

-- Alpha Vantage (Aggregator)
UPDATE fhq_macro.provider_quota_state
SET provider_category = 'MARKET_DATA',
    reset_time_utc = '00:00:00',
    health_status = 'UNKNOWN',
    updated_at = NOW()
WHERE provider_id = 'alphavantage';

-- FRED (Regulatory)
UPDATE fhq_macro.provider_quota_state
SET provider_category = 'MARKET_DATA',
    reset_time_utc = '00:00:00',
    health_status = 'UNKNOWN',
    updated_at = NOW()
WHERE provider_id = 'fred';

-- Yahoo (Scraper)
UPDATE fhq_macro.provider_quota_state
SET provider_category = 'MARKET_DATA',
    reset_time_utc = '00:00:00',
    health_status = 'UNKNOWN',
    updated_at = NOW()
WHERE provider_id = 'yahoo';

-- CBOE (Exchange)
UPDATE fhq_macro.provider_quota_state
SET provider_category = 'MARKET_DATA',
    reset_time_utc = '00:00:00',
    health_status = 'UNKNOWN',
    updated_at = NOW()
WHERE provider_id = 'cboe';

-- CoinDesk Data API (Crypto Market Data)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'coindesk',
    'CoinDesk Data API',
    'AGGREGATOR',
    'MARKET_DATA',
    1000, NULL, 30,
    '00:00:00',
    3, TRUE, 'UNKNOWN',
    'COINDESK_API_KEY', 'https://data-api.coindesk.com', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'MARKET_DATA',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- ----- NEWS & NARRATIVE VENDORS -----

-- MarketAux (Financial News - ADR-012 Tier 2 Pulse)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'marketaux',
    'MarketAux Financial News',
    'AGGREGATOR',
    'NEWS_NARRATIVE',
    100, NULL, 10,  -- 100 requests/day free tier
    '00:00:00',
    2, TRUE, 'UNKNOWN',
    'MARKETAUX_API_KEY', 'https://api.marketaux.com/v1', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'NEWS_NARRATIVE',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- NewsAPI (General News)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'newsapi',
    'NewsAPI',
    'AGGREGATOR',
    'NEWS_NARRATIVE',
    100, NULL, 10,  -- 100 requests/day free tier (dev)
    '00:00:00',
    3, TRUE, 'UNKNOWN',
    'NEWSAPI_KEY', 'https://newsapi.org/v2', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'NEWS_NARRATIVE',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- TheNewsAPI
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'thenewsapi',
    'TheNewsAPI',
    'AGGREGATOR',
    'NEWS_NARRATIVE',
    100, 3000, 10,  -- 3 requests/day free, 3000/month paid
    '00:00:00',
    3, TRUE, 'UNKNOWN',
    'THENEWSAPI_KEY', 'https://api.thenewsapi.com/v1', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'NEWS_NARRATIVE',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- Massive (AI News Analysis)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'massive',
    'Massive AI News',
    'AGGREGATOR',
    'NEWS_NARRATIVE',
    500, NULL, 30,
    '00:00:00',
    3, TRUE, 'UNKNOWN',
    'MASSIVE_API_KEY', 'https://api.massive.io', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'NEWS_NARRATIVE',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- ----- CRYPTO / EXECUTION CONNECTIVITY -----

-- Changelly (Crypto Swap/Routing)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'changelly',
    'Changelly Exchange',
    'EXCHANGE',
    'CRYPTO_EXCHANGE',
    1000, NULL, 60,
    '00:00:00',
    3, TRUE, 'UNKNOWN',
    'CHANGELLY_API_KEY', 'https://api.changelly.com', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'CRYPTO_EXCHANGE',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- ----- LLM PROVIDERS (For later IoS modules) -----

-- OpenAI (LARS primary)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'openai',
    'OpenAI GPT',
    'REGULATORY',
    'LLM_PROVIDER',
    10000, NULL, 60,
    '00:00:00',
    1, TRUE, 'UNKNOWN',
    'OPENAI_API_KEY', 'https://api.openai.com/v1', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'LLM_PROVIDER',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- Anthropic (STIG, VEGA primary)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'anthropic',
    'Anthropic Claude',
    'REGULATORY',
    'LLM_PROVIDER',
    10000, NULL, 60,
    '00:00:00',
    1, TRUE, 'UNKNOWN',
    'ANTHROPIC_API_KEY', 'https://api.anthropic.com/v1', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'LLM_PROVIDER',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- Gemini (LINE primary)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'gemini',
    'Google Gemini',
    'REGULATORY',
    'LLM_PROVIDER',
    10000, NULL, 60,
    '00:00:00',
    1, TRUE, 'UNKNOWN',
    'GEMINI_API_KEY', 'https://generativelanguage.googleapis.com', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'LLM_PROVIDER',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- DeepSeek (FINN primary)
INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type, provider_category,
    daily_limit, monthly_limit, rate_limit_per_minute, reset_time_utc,
    canonical_source_preference, is_active, health_status,
    api_key_env_var, base_url, requires_api_key
) VALUES (
    'deepseek',
    'DeepSeek AI',
    'AGGREGATOR',
    'LLM_PROVIDER',
    10000, NULL, 60,
    '00:00:00',
    2, TRUE, 'UNKNOWN',
    'DEEPSEEK_API_KEY', 'https://api.deepseek.com/v1', TRUE
)
ON CONFLICT (provider_id) DO UPDATE SET
    provider_category = 'LLM_PROVIDER',
    health_status = 'UNKNOWN',
    updated_at = NOW();

-- ============================================================================
-- SECTION 3: EXTEND PROVIDER_CAPABILITY FOR NEW PROVIDERS
-- ============================================================================

-- TwelveData expanded capabilities
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, is_active)
VALUES
    ('twelvedata', 'MOVE_INDEX', 'MOVE', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, is_active = TRUE;

-- Note: Binance and CoinDesk focus on crypto, not traditional macro indicators
-- They will be used for crypto-specific features in later IoS modules

-- ============================================================================
-- SECTION 4: UPDATE IOS REGISTRY
-- ============================================================================

UPDATE fhq_meta.ios_registry
SET version = '2026.PROD.G2.6',
    updated_at = NOW()
WHERE ios_id = 'IoS-006';

-- ============================================================================
-- SECTION 5: LOG GOVERNANCE ACTION
-- ============================================================================

DO $$
DECLARE
    v_signature_id UUID := gen_random_uuid();
    v_action_id UUID := gen_random_uuid();
    v_payload JSONB;
    v_signature_value TEXT;
    v_provider_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_provider_count FROM fhq_macro.provider_quota_state;

    v_payload := jsonb_build_object(
        'action_type', 'IOS_MODULE_G2_6_VENDOR_BOOTSTRAP',
        'action_target', 'IoS-006',
        'decision', 'APPROVED',
        'initiated_by', 'STIG',
        'authorized_by', 'LARS',
        'timestamp', NOW()::text,
        'chain_id', 'HC-IOS-006-2026',
        'vendors_registered', jsonb_build_object(
            'market_data', ARRAY['binance', 'twelvedata', 'finnhub', 'fmp', 'alphavantage', 'fred', 'yahoo', 'cboe', 'coindesk'],
            'news_narrative', ARRAY['marketaux', 'newsapi', 'thenewsapi', 'massive'],
            'crypto_exchange', ARRAY['binance', 'changelly'],
            'llm_providers', ARRAY['openai', 'anthropic', 'gemini', 'deepseek']
        ),
        'total_providers', v_provider_count
    );

    v_signature_value := encode(sha256(v_payload::text::bytea), 'hex');

    INSERT INTO vision_verification.operation_signatures (
        signature_id, operation_type, operation_id, operation_table, operation_schema,
        signing_agent, signing_key_id, signature_value, signed_payload,
        verified, verified_at, verified_by, created_at, hash_chain_id
    ) VALUES (
        v_signature_id, 'IOS_MODULE_G2_6_VENDOR_BOOTSTRAP', v_action_id, 'governance_actions_log',
        'fhq_governance', 'STIG', 'STIG-EC003-IOS006-G2.6', v_signature_value, v_payload,
        TRUE, NOW(), 'STIG', NOW(), 'HC-IOS-006-2026'
    );

    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type, initiated_by,
        initiated_at, decision, decision_rationale, vega_reviewed, vega_override,
        vega_notes, hash_chain_id, signature_id
    ) VALUES (
        v_action_id, 'IOS_MODULE_G2_6_VENDOR_BOOTSTRAP', 'IoS-006', 'IOS_MODULE', 'STIG', NOW(),
        'APPROVED',
        'G2.6 VENDOR BOOTSTRAP: Registered ' || v_provider_count || ' providers across 4 categories. ' ||
        'Market Data: Binance, TwelveData, Finnhub, FMP, AlphaVantage, FRED, Yahoo, CBOE, CoinDesk. ' ||
        'News/Narrative: MarketAux, NewsAPI, TheNewsAPI, Massive. ' ||
        'Crypto Exchange: Binance, Changelly. ' ||
        'LLM Providers: OpenAI (LARS), Anthropic (STIG/VEGA), Gemini (LINE), DeepSeek (FINN). ' ||
        'All providers registered with ADR-012 preference hierarchy. Awaiting API key activation.',
        TRUE, FALSE,
        'Schema extended with health_status, reset_time_utc, provider_category fields. ' ||
        'LLM providers registered for future IoS modules (IoS-007, IoS-009, IoS-010). ' ||
        'News vendors prepared for sentiment analysis pipeline.',
        'HC-IOS-006-2026', v_signature_id
    );

    RAISE NOTICE 'IoS-006 G2.6 VENDOR BOOTSTRAP: action_id=%, providers=%', v_action_id, v_provider_count;
END $$;

-- ============================================================================
-- SECTION 6: UPDATE HASH CHAIN
-- ============================================================================

UPDATE vision_verification.hash_chains
SET current_hash = encode(sha256(('IoS-006_G2.6_VENDOR_BOOTSTRAP_' || NOW()::text)::bytea), 'hex'),
    chain_length = chain_length + 1,
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-006-2026';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- SELECT provider_id, provider_name, provider_category, canonical_source_preference, health_status
--   FROM fhq_macro.provider_quota_state ORDER BY provider_category, canonical_source_preference;
-- SELECT COUNT(*) as total_providers FROM fhq_macro.provider_quota_state;
