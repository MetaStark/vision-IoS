-- ============================================================================
-- MIGRATION: 038_ios006_g2_5_multi_provider_router.sql
-- PURPOSE: IoS-006 G2.5 — Multi-Provider Canonical Router Architecture
-- AUTHORITY: LARS (Strategy) + STIG (Technical)
-- ADR COMPLIANCE: ADR-011 (Lineage), ADR-012 (API Waterfall), ADR-013 (One-True-Source)
-- STATUS: G2.5 ARCHITECTURE UPGRADE
-- DATE: 2025-11-30
-- ============================================================================
--
-- STRATEGIC MISSION:
-- Eliminate single-point-of-failure risks in data ingestion by establishing
-- a Multi-Provider Canonical Router with deterministic failover logic.
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- SECTION 1: PROVIDER QUOTA STATE (The Preference Engine)
-- ============================================================================
-- Manages capacity and trust hierarchy for data providers.
-- canonical_source_preference determines priority:
--   1: Regulatory Grade (FRED, Treasury)
--   2: Exchange Grade (CBOE, TwelveData)
--   3: Aggregator Grade (Finnhub, FMP)
--   4: Scraper Grade (Yahoo, AlphaVantage)

CREATE TABLE IF NOT EXISTS fhq_macro.provider_quota_state (
    provider_id TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    provider_type TEXT NOT NULL CHECK (provider_type IN (
        'REGULATORY', 'EXCHANGE', 'AGGREGATOR', 'SCRAPER'
    )),

    -- API Limits
    daily_limit INTEGER NOT NULL,
    used_today INTEGER NOT NULL DEFAULT 0,
    monthly_limit INTEGER,
    used_this_month INTEGER DEFAULT 0,
    rate_limit_per_minute INTEGER,

    -- Trust Hierarchy (ADR-013 Compliance)
    canonical_source_preference INTEGER NOT NULL CHECK (canonical_source_preference BETWEEN 1 AND 4),
    -- 1: Regulatory Grade (FRED, Treasury Direct)
    -- 2: Exchange Grade (CBOE, TwelveData direct feeds)
    -- 3: Aggregator Grade (Finnhub, FMP)
    -- 4: Scraper Grade (Yahoo, AlphaVantage)

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_successful_call TIMESTAMPTZ,
    last_failed_call TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,
    cooldown_until TIMESTAMPTZ,

    -- API Configuration
    api_key_env_var TEXT,                    -- Environment variable name for API key
    base_url TEXT,
    requires_api_key BOOLEAN DEFAULT TRUE,

    -- Lineage (ADR-011)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG'
);

CREATE INDEX IF NOT EXISTS idx_provider_preference ON fhq_macro.provider_quota_state(canonical_source_preference);
CREATE INDEX IF NOT EXISTS idx_provider_active ON fhq_macro.provider_quota_state(is_active);

COMMENT ON TABLE fhq_macro.provider_quota_state IS
'Provider Quota State (The Preference Engine). Manages capacity and trust hierarchy for data providers.
canonical_source_preference: 1=Regulatory, 2=Exchange, 3=Aggregator, 4=Scraper.
Supports ADR-012 API Waterfall and ADR-013 One-True-Source compliance.';

-- ============================================================================
-- SECTION 2: PROVIDER CAPABILITY MATRIX
-- ============================================================================
-- Maps features to valid providers with provider-specific ticker symbols.
-- Prevents "blind guessing" by explicitly defining which providers can serve which features.

CREATE TABLE IF NOT EXISTS fhq_macro.provider_capability (
    capability_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id TEXT NOT NULL REFERENCES fhq_macro.provider_quota_state(provider_id),
    feature_id TEXT NOT NULL REFERENCES fhq_macro.feature_registry(feature_id),

    -- Provider-Specific Configuration
    ticker_symbol TEXT NOT NULL,             -- Provider-specific symbol (e.g., '^VIX' vs 'VIX')
    endpoint_path TEXT,                      -- API endpoint path for this feature
    response_field TEXT,                     -- JSON path to extract value

    -- Quality Metrics
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    data_quality_score NUMERIC(3,2) DEFAULT 1.00,  -- 0.00 to 1.00
    latency_ms_avg INTEGER,                  -- Average response time
    last_verified TIMESTAMPTZ,

    -- Lineage
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_provider_feature UNIQUE (provider_id, feature_id)
);

CREATE INDEX IF NOT EXISTS idx_capability_feature ON fhq_macro.provider_capability(feature_id);
CREATE INDEX IF NOT EXISTS idx_capability_provider ON fhq_macro.provider_capability(provider_id);
CREATE INDEX IF NOT EXISTS idx_capability_active ON fhq_macro.provider_capability(is_active);

COMMENT ON TABLE fhq_macro.provider_capability IS
'Provider Capability Matrix. Maps features to valid providers with provider-specific ticker symbols.
Prevents blind guessing by explicitly defining provider-feature relationships.';

-- ============================================================================
-- SECTION 3: SOURCE COMPARISON LOG (The Drift Detective)
-- ============================================================================
-- Audits consistency when sources switch. Detects drift between providers.

CREATE TABLE IF NOT EXISTS fhq_macro.source_comparison_log (
    comparison_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comparison_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Feature Being Compared
    feature_id TEXT NOT NULL REFERENCES fhq_macro.feature_registry(feature_id),
    data_timestamp TIMESTAMPTZ NOT NULL,     -- Timestamp of the data point being compared

    -- Provider Information
    primary_provider TEXT NOT NULL REFERENCES fhq_macro.provider_quota_state(provider_id),
    primary_value NUMERIC NOT NULL,
    secondary_provider TEXT NOT NULL REFERENCES fhq_macro.provider_quota_state(provider_id),
    secondary_value NUMERIC NOT NULL,

    -- Comparison Metrics
    value_diff NUMERIC NOT NULL,             -- Absolute delta
    pct_diff NUMERIC(8,5),                   -- Percentage difference
    z_score_diff NUMERIC(6,3),               -- Statistical deviation (requires historical data)

    -- Decision
    is_acceptable BOOLEAN NOT NULL,          -- Within tolerance?
    tolerance_threshold NUMERIC DEFAULT 0.01, -- Default 1% tolerance
    action_taken TEXT CHECK (action_taken IN (
        'ACCEPTED_PRIMARY', 'ACCEPTED_SECONDARY', 'FLAGGED_FOR_REVIEW', 'REJECTED_BOTH'
    )),

    -- Lineage
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comparison_feature ON fhq_macro.source_comparison_log(feature_id);
CREATE INDEX IF NOT EXISTS idx_comparison_timestamp ON fhq_macro.source_comparison_log(comparison_timestamp);
CREATE INDEX IF NOT EXISTS idx_comparison_acceptable ON fhq_macro.source_comparison_log(is_acceptable);

COMMENT ON TABLE fhq_macro.source_comparison_log IS
'Source Comparison Log (The Drift Detective). Audits consistency when sources switch.
Tracks value differences and statistical deviations between providers for the same feature.';

-- ============================================================================
-- SECTION 4: EXTEND RAW_STAGING FOR ROUTER LINEAGE
-- ============================================================================
-- Add columns to track router decisions per ADR-011

ALTER TABLE fhq_macro.raw_staging
ADD COLUMN IF NOT EXISTS provider_id TEXT,
ADD COLUMN IF NOT EXISTS router_logic_hash TEXT,
ADD COLUMN IF NOT EXISTS failover_count INTEGER DEFAULT 0;

COMMENT ON COLUMN fhq_macro.raw_staging.provider_id IS 'The specific provider used for this data point (ADR-011 lineage)';
COMMENT ON COLUMN fhq_macro.raw_staging.router_logic_hash IS 'Hash of the preference logic used at ingest time (ADR-011)';
COMMENT ON COLUMN fhq_macro.raw_staging.failover_count IS 'Number of failovers before successful fetch';

-- ============================================================================
-- SECTION 5: POPULATE PROVIDER QUOTA STATE
-- ============================================================================
-- Free tier limits for supported providers

INSERT INTO fhq_macro.provider_quota_state (
    provider_id, provider_name, provider_type,
    daily_limit, monthly_limit, rate_limit_per_minute,
    canonical_source_preference, is_active,
    api_key_env_var, base_url, requires_api_key
) VALUES
-- Tier 1: Regulatory Grade (Preference 1)
(
    'fred',
    'Federal Reserve Economic Data',
    'REGULATORY',
    500, NULL, 120,
    1, TRUE,
    'FRED_API_KEY', 'https://api.stlouisfed.org/fred', TRUE
),
-- Tier 2: Exchange Grade (Preference 2)
(
    'twelvedata',
    'Twelve Data',
    'EXCHANGE',
    800, NULL, 8,  -- 8 requests per minute on free tier
    2, TRUE,
    'TWELVEDATA_API_KEY', 'https://api.twelvedata.com', TRUE
),
(
    'cboe',
    'CBOE Global Markets',
    'EXCHANGE',
    1000, NULL, 60,
    2, TRUE,
    NULL, 'https://cdn.cboe.com', FALSE  -- Public data feeds
),
-- Tier 3: Aggregator Grade (Preference 3)
(
    'finnhub',
    'Finnhub Stock API',
    'AGGREGATOR',
    60, NULL, 30,  -- 60 calls/minute on free tier
    3, TRUE,
    'FINNHUB_API_KEY', 'https://finnhub.io/api/v1', TRUE
),
(
    'fmp',
    'Financial Modeling Prep',
    'AGGREGATOR',
    250, NULL, 5,  -- 250 requests/day on free tier
    3, TRUE,
    'FMP_API_KEY', 'https://financialmodelingprep.com/api/v3', TRUE
),
(
    'alphavantage',
    'Alpha Vantage',
    'AGGREGATOR',
    25, 500, 5,  -- 25/day, 500/month on free tier
    3, TRUE,
    'ALPHAVANTAGE_API_KEY', 'https://www.alphavantage.co/query', TRUE
),
-- Tier 4: Scraper Grade (Preference 4)
(
    'yahoo',
    'Yahoo Finance',
    'SCRAPER',
    2000, NULL, 60,  -- Unofficial limits, conservative
    4, TRUE,
    NULL, 'https://query1.finance.yahoo.com', FALSE
),
(
    'investing',
    'Investing.com',
    'SCRAPER',
    500, NULL, 30,
    4, FALSE,  -- Disabled by default
    NULL, 'https://www.investing.com', FALSE
)
ON CONFLICT (provider_id) DO UPDATE SET
    daily_limit = EXCLUDED.daily_limit,
    rate_limit_per_minute = EXCLUDED.rate_limit_per_minute,
    updated_at = NOW();

-- ============================================================================
-- SECTION 6: POPULATE PROVIDER CAPABILITY MATRIX
-- ============================================================================
-- Map pending G2 features to available providers

-- VIX_INDEX capabilities
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'VIX_INDEX', '^VIX', '/v8/finance/chart/^VIX', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('twelvedata', 'VIX_INDEX', 'VIX', '/time_series', 'values[].close', TRUE),
    ('cboe', 'VIX_INDEX', 'VIX', '/api/delayed_quotes/vix', 'data.price', TRUE),
    ('finnhub', 'VIX_INDEX', '^VIX', '/quote', 'c', TRUE),
    ('alphavantage', 'VIX_INDEX', 'VIX', 'function=TIME_SERIES_DAILY', 'Time Series (Daily)', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- VIX9D_INDEX capabilities
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'VIX9D_INDEX', '^VIX9D', '/v8/finance/chart/^VIX9D', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('cboe', 'VIX9D_INDEX', 'VIX9D', '/api/delayed_quotes/vix9d', 'data.price', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- DXY_INDEX capabilities
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'DXY_INDEX', 'DX-Y.NYB', '/v8/finance/chart/DX-Y.NYB', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('twelvedata', 'DXY_INDEX', 'DXY', '/time_series', 'values[].close', TRUE),
    ('finnhub', 'DXY_INDEX', 'DXY', '/forex/candle', 'c', TRUE),
    ('alphavantage', 'DXY_INDEX', 'DX-Y.NYB', 'function=FX_DAILY', 'Time Series FX (Daily)', TRUE),
    ('fmp', 'DXY_INDEX', 'DXUSD', '/historical-chart/1day/DXUSD', '[].close', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- NDX_INDEX capabilities
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'NDX_INDEX', '^NDX', '/v8/finance/chart/^NDX', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('twelvedata', 'NDX_INDEX', 'NDX', '/time_series', 'values[].close', TRUE),
    ('finnhub', 'NDX_INDEX', '^NDX', '/quote', 'c', TRUE),
    ('alphavantage', 'NDX_INDEX', 'NDX', 'function=TIME_SERIES_DAILY', 'Time Series (Daily)', TRUE),
    ('fmp', 'NDX_INDEX', '^NDX', '/historical-price-full/^NDX', 'historical[].close', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- MOVE_INDEX capabilities (bond volatility)
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'MOVE_INDEX', '^MOVE', '/v8/finance/chart/^MOVE', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('fred', 'MOVE_INDEX', 'BAMLMOVE', '/series/observations', 'observations[].value', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- Supporting tickers for calculated features
-- SPX (for GOLD_SPX_RATIO, SPX_RVOL_20D, VIX_RVOL_SPREAD)
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'SPX_RVOL_20D', '^GSPC', '/v8/finance/chart/^GSPC', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('twelvedata', 'SPX_RVOL_20D', 'SPX', '/time_series', 'values[].close', TRUE),
    ('finnhub', 'SPX_RVOL_20D', '^GSPC', '/quote', 'c', TRUE),
    ('fmp', 'SPX_RVOL_20D', '^GSPC', '/historical-price-full/^GSPC', 'historical[].close', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- Gold (for GOLD_SPX_RATIO, COPPER_GOLD_RATIO)
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'GOLD_SPX_RATIO', 'GC=F', '/v8/finance/chart/GC=F', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('twelvedata', 'GOLD_SPX_RATIO', 'XAU/USD', '/time_series', 'values[].close', TRUE),
    ('finnhub', 'GOLD_SPX_RATIO', 'OANDA:XAU_USD', '/forex/candle', 'c', TRUE),
    ('fmp', 'GOLD_SPX_RATIO', 'GCUSD', '/historical-chart/1day/GCUSD', '[].close', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- Copper (for COPPER_GOLD_RATIO)
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'COPPER_GOLD_RATIO', 'HG=F', '/v8/finance/chart/HG=F', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('twelvedata', 'COPPER_GOLD_RATIO', 'XCU/USD', '/time_series', 'values[].close', TRUE),
    ('fmp', 'COPPER_GOLD_RATIO', 'HGUSD', '/historical-chart/1day/HGUSD', '[].close', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- VIX3M (for VIX_TERM_STRUCTURE)
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'VIX_TERM_STRUCTURE', '^VIX3M', '/v8/finance/chart/^VIX3M', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('cboe', 'VIX_TERM_STRUCTURE', 'VIX3M', '/api/delayed_quotes/vix3m', 'data.price', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- VIX_RVOL_SPREAD (derived from VIX and SPX_RVOL)
INSERT INTO fhq_macro.provider_capability (provider_id, feature_id, ticker_symbol, endpoint_path, response_field, is_active)
VALUES
    ('yahoo', 'VIX_RVOL_SPREAD', '^VIX', '/v8/finance/chart/^VIX', 'chart.result[0].indicators.quote[0].close', TRUE),
    ('twelvedata', 'VIX_RVOL_SPREAD', 'VIX', '/time_series', 'values[].close', TRUE)
ON CONFLICT (provider_id, feature_id) DO UPDATE SET ticker_symbol = EXCLUDED.ticker_symbol, updated_at = NOW();

-- ============================================================================
-- SECTION 7: CREATE ROUTER FUNCTIONS
-- ============================================================================

-- Function to get next available provider for a feature
CREATE OR REPLACE FUNCTION fhq_macro.get_next_provider(
    p_feature_id TEXT,
    p_exclude_providers TEXT[] DEFAULT ARRAY[]::TEXT[]
) RETURNS TABLE (
    provider_id TEXT,
    ticker_symbol TEXT,
    preference_rank INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pqs.provider_id,
        pc.ticker_symbol,
        pqs.canonical_source_preference
    FROM fhq_macro.provider_quota_state pqs
    JOIN fhq_macro.provider_capability pc ON pqs.provider_id = pc.provider_id
    WHERE pc.feature_id = p_feature_id
      AND pc.is_active = TRUE
      AND pqs.is_active = TRUE
      AND pqs.used_today < (pqs.daily_limit * 0.99)  -- 99% threshold
      AND (pqs.cooldown_until IS NULL OR pqs.cooldown_until < NOW())
      AND NOT (pqs.provider_id = ANY(p_exclude_providers))
    ORDER BY pqs.canonical_source_preference ASC, pqs.consecutive_failures ASC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to record provider usage
CREATE OR REPLACE FUNCTION fhq_macro.record_provider_usage(
    p_provider_id TEXT,
    p_success BOOLEAN,
    p_response_time_ms INTEGER DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    IF p_success THEN
        UPDATE fhq_macro.provider_quota_state
        SET used_today = used_today + 1,
            used_this_month = COALESCE(used_this_month, 0) + 1,
            last_successful_call = NOW(),
            consecutive_failures = 0,
            cooldown_until = NULL,
            updated_at = NOW()
        WHERE provider_id = p_provider_id;
    ELSE
        UPDATE fhq_macro.provider_quota_state
        SET consecutive_failures = consecutive_failures + 1,
            last_failed_call = NOW(),
            -- Exponential backoff: 2^failures minutes cooldown
            cooldown_until = NOW() + (POWER(2, LEAST(consecutive_failures + 1, 6))::INTEGER || ' minutes')::INTERVAL,
            updated_at = NOW()
        WHERE provider_id = p_provider_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to reset daily quotas (should be called by scheduler at midnight UTC)
CREATE OR REPLACE FUNCTION fhq_macro.reset_daily_quotas() RETURNS VOID AS $$
BEGIN
    UPDATE fhq_macro.provider_quota_state
    SET used_today = 0,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 8: UPDATE IOS REGISTRY
-- ============================================================================

UPDATE fhq_meta.ios_registry
SET version = '2026.PROD.G2.5',
    updated_at = NOW()
WHERE ios_id = 'IoS-006';

-- ============================================================================
-- SECTION 9: LOG GOVERNANCE ACTION
-- ============================================================================

DO $$
DECLARE
    v_signature_id UUID := gen_random_uuid();
    v_action_id UUID := gen_random_uuid();
    v_payload JSONB;
    v_signature_value TEXT;
BEGIN
    v_payload := jsonb_build_object(
        'action_type', 'IOS_MODULE_G2_5_ARCHITECTURE',
        'action_target', 'IoS-006',
        'decision', 'APPROVED',
        'initiated_by', 'STIG',
        'authorized_by', 'LARS',
        'timestamp', NOW()::text,
        'chain_id', 'HC-IOS-006-2026',
        'architecture_components', jsonb_build_object(
            'provider_quota_state', 'Preference Engine - manages capacity and trust hierarchy',
            'provider_capability', 'Capability Matrix - maps features to providers',
            'source_comparison_log', 'Drift Detective - audits consistency'
        ),
        'providers_configured', ARRAY['fred', 'twelvedata', 'cboe', 'finnhub', 'fmp', 'alphavantage', 'yahoo'],
        'routing_logic', jsonb_build_object(
            'step1', 'Capability Lookup',
            'step2', 'Preference Sort (1=Regulatory, 2=Exchange, 3=Aggregator, 4=Scraper)',
            'step3', 'Quota Check (99% threshold)',
            'step4', 'Selection (highest-ranking available)',
            'step5', 'Failover (retry with next provider on error)'
        )
    );

    v_signature_value := encode(sha256(v_payload::text::bytea), 'hex');

    INSERT INTO vision_verification.operation_signatures (
        signature_id, operation_type, operation_id, operation_table, operation_schema,
        signing_agent, signing_key_id, signature_value, signed_payload,
        verified, verified_at, verified_by, created_at, hash_chain_id
    ) VALUES (
        v_signature_id, 'IOS_MODULE_G2_5_ARCHITECTURE', v_action_id, 'governance_actions_log',
        'fhq_governance', 'STIG', 'STIG-EC003-IOS006-G2.5', v_signature_value, v_payload,
        TRUE, NOW(), 'STIG', NOW(), 'HC-IOS-006-2026'
    );

    INSERT INTO fhq_governance.governance_actions_log (
        action_id, action_type, action_target, action_target_type, initiated_by,
        initiated_at, decision, decision_rationale, vega_reviewed, vega_override,
        vega_notes, hash_chain_id, signature_id
    ) VALUES (
        v_action_id, 'IOS_MODULE_G2_5_ARCHITECTURE', 'IoS-006', 'IOS_MODULE', 'STIG', NOW(),
        'APPROVED',
        'G2.5 ARCHITECTURE UPGRADE: Multi-Provider Canonical Router implemented. ' ||
        'Created 3 control tables: provider_quota_state (Preference Engine), provider_capability (Capability Matrix), ' ||
        'source_comparison_log (Drift Detective). Configured 8 providers with trust hierarchy (Regulatory > Exchange > Aggregator > Scraper). ' ||
        'Deterministic routing with 99% quota threshold and exponential backoff on failures. ' ||
        'Extended raw_staging with provider_id and router_logic_hash for ADR-011 lineage compliance.',
        TRUE, FALSE,
        'Architecture eliminates single-point-of-failure risk from Yahoo rate limiting. ' ||
        'Provider preference follows ADR-012 API Waterfall: FRED (Regulatory) > TwelveData/CBOE (Exchange) > Finnhub/FMP (Aggregator) > Yahoo (Scraper). ' ||
        'Ready for tactical recovery of blocked G2 features.',
        'HC-IOS-006-2026', v_signature_id
    );

    RAISE NOTICE 'IoS-006 G2.5 ARCHITECTURE: action_id=%, signature_id=%', v_action_id, v_signature_id;
END $$;

-- ============================================================================
-- SECTION 10: UPDATE HASH CHAIN
-- ============================================================================

UPDATE vision_verification.hash_chains
SET current_hash = encode(sha256(('IoS-006_G2.5_MULTI_PROVIDER_' || NOW()::text)::bytea), 'hex'),
    chain_length = chain_length + 1,
    updated_at = NOW()
WHERE chain_id = 'HC-IOS-006-2026';

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- SELECT * FROM fhq_macro.provider_quota_state ORDER BY canonical_source_preference;
-- SELECT pc.feature_id, pc.provider_id, pc.ticker_symbol, pqs.canonical_source_preference
--   FROM fhq_macro.provider_capability pc
--   JOIN fhq_macro.provider_quota_state pqs ON pc.provider_id = pqs.provider_id
--   ORDER BY pc.feature_id, pqs.canonical_source_preference;
-- SELECT * FROM fhq_macro.get_next_provider('VIX_INDEX');
