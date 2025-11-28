-- ============================================================================
-- MIGRATION 021: API SCARCITY & WATERFALL ARCHITECTURE
-- ============================================================================
-- Authority: CEO MBB C-LEVEL DIRECTIVE
-- Status: CEO APPROVED
-- Date: 2026-11-28
-- Owner: CEO
-- Governing Framework: ADR-014 (Roles), ADR-008 (Keys), ADR-003 (Standards)
-- Attestation Required: VEGA
--
-- Purpose: Implement "Economic Intelligence" - The Data Waterfall Protocol
--   Tier 1 (LAKE): Unlimited - yfinance, FRED
--   Tier 2 (PULSE): Generous - Twelve Data, Finnhub, MarketAux
--   Tier 3 (SNIPER): Scarce - Alpha Vantage, FMP (Critical only)
--
-- Compliance:
--   - ADR-002: Audit & Error Reconciliation (budget logging)
--   - ADR-003: Institutional Standards & Compliance
--   - ADR-008: Cryptographic Key Management (API keys)
--   - ADR-012: Economic Safety Architecture
--   - ADR-014: Executive Activation & Sub-Executive Governance
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CREATE DATA PROVIDER POLICY TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.data_provider_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    authorized_providers TEXT[] NOT NULL,
    usage_tier TEXT NOT NULL DEFAULT 'SNIPER' CHECK (usage_tier IN ('LAKE', 'PULSE', 'SNIPER')),
    daily_quota INTEGER NOT NULL DEFAULT 0,
    cost_weight INTEGER NOT NULL DEFAULT 10 CHECK (cost_weight >= 1 AND cost_weight <= 10),
    priority_required TEXT DEFAULT 'NORMAL' CHECK (priority_required IN ('NORMAL', 'HIGH', 'CRITICAL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'CEO',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(agent_id, usage_tier)
);

CREATE INDEX IF NOT EXISTS idx_data_provider_policy_agent ON fhq_governance.data_provider_policy(agent_id);
CREATE INDEX IF NOT EXISTS idx_data_provider_policy_tier ON fhq_governance.data_provider_policy(usage_tier);

-- ============================================================================
-- 2. CREATE API BUDGET LOG TABLE (ADR-002 Compliance)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_monitoring.api_budget_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL REFERENCES fhq_org.org_agents(agent_id),
    provider TEXT NOT NULL,
    usage_tier TEXT NOT NULL CHECK (usage_tier IN ('LAKE', 'PULSE', 'SNIPER')),
    credits_used INTEGER NOT NULL DEFAULT 1,
    priority_level TEXT DEFAULT 'NORMAL',
    justification TEXT,  -- Required for SNIPER tier
    request_hash TEXT,   -- For deduplication
    response_status TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_budget_log_agent ON fhq_monitoring.api_budget_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_api_budget_log_provider ON fhq_monitoring.api_budget_log(provider);
CREATE INDEX IF NOT EXISTS idx_api_budget_log_tier ON fhq_monitoring.api_budget_log(usage_tier);
CREATE INDEX IF NOT EXISTS idx_api_budget_log_created ON fhq_monitoring.api_budget_log(created_at);

-- ============================================================================
-- 3. CREATE API PROVIDER REGISTRY
-- ============================================================================

CREATE TABLE IF NOT EXISTS fhq_governance.api_provider_registry (
    provider_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name TEXT NOT NULL UNIQUE,
    provider_type TEXT NOT NULL CHECK (provider_type IN ('MARKET_DATA', 'NEWS', 'MACRO', 'SEARCH', 'ANALYTICS')),
    usage_tier TEXT NOT NULL CHECK (usage_tier IN ('LAKE', 'PULSE', 'SNIPER')),
    base_url TEXT,
    daily_limit INTEGER NOT NULL DEFAULT 0,  -- 0 = unlimited
    rate_limit_per_minute INTEGER DEFAULT 60,
    cost_per_call NUMERIC(10,6) DEFAULT 0,
    requires_api_key BOOLEAN NOT NULL DEFAULT TRUE,
    key_env_variable TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 4. CONFIGURE PROVIDERS (The Hard Limits)
-- ============================================================================

-- TIER 1: LAKE (Free/Unlimited - Low Governance Friction)
INSERT INTO fhq_governance.api_provider_registry (provider_name, provider_type, usage_tier, daily_limit, rate_limit_per_minute, cost_per_call, requires_api_key, key_env_variable, metadata)
VALUES
    ('YFINANCE', 'MARKET_DATA', 'LAKE', 0, 999, 0, FALSE, NULL,
     '{"description": "Yahoo Finance Python library", "data_types": ["OHLCV", "fundamentals", "options"], "latency": "medium"}'::jsonb),
    ('FRED', 'MACRO', 'LAKE', 0, 120, 0, TRUE, 'FRED_API_KEY',
     '{"description": "Federal Reserve Economic Data", "data_types": ["macro", "rates", "economic_indicators"], "latency": "low"}'::jsonb)
ON CONFLICT (provider_name) DO UPDATE SET
    usage_tier = EXCLUDED.usage_tier,
    daily_limit = EXCLUDED.daily_limit;

-- TIER 2: PULSE (Monitoring - Generous but Tracked)
INSERT INTO fhq_governance.api_provider_registry (provider_name, provider_type, usage_tier, daily_limit, rate_limit_per_minute, cost_per_call, requires_api_key, key_env_variable, metadata)
VALUES
    ('TWELVEDATA', 'MARKET_DATA', 'PULSE', 800, 8, 0.001, TRUE, 'TWELVEDATA_API_KEY',
     '{"description": "Real-time and historical market data", "data_types": ["realtime", "OHLCV", "technicals"], "latency": "low"}'::jsonb),
    ('FINNHUB', 'MARKET_DATA', 'PULSE', 3600, 60, 0, TRUE, 'FINNHUB_API_KEY',
     '{"description": "Real-time stock API", "data_types": ["quotes", "news", "fundamentals"], "latency": "very_low"}'::jsonb),
    ('MARKETAUX', 'NEWS', 'PULSE', 50, 5, 0.02, TRUE, 'MARKETAUX_API_KEY',
     '{"description": "Financial news sentiment", "data_types": ["news", "sentiment"], "latency": "medium"}'::jsonb)
ON CONFLICT (provider_name) DO UPDATE SET
    usage_tier = EXCLUDED.usage_tier,
    daily_limit = EXCLUDED.daily_limit;

-- TIER 3: SNIPER (Alpha Confirmation Only - Scarce)
INSERT INTO fhq_governance.api_provider_registry (provider_name, provider_type, usage_tier, daily_limit, rate_limit_per_minute, cost_per_call, requires_api_key, key_env_variable, metadata)
VALUES
    ('ALPHAVANTAGE', 'MARKET_DATA', 'SNIPER', 25, 5, 0.04, TRUE, 'ALPHAVANTAGE_API_KEY',
     '{"description": "Premium technical analysis", "data_types": ["technicals", "fundamentals", "forex"], "latency": "medium", "priority_required": "CRITICAL"}'::jsonb),
    ('FMP', 'MARKET_DATA', 'SNIPER', 250, 10, 0.004, TRUE, 'FMP_API_KEY',
     '{"description": "Financial Modeling Prep", "data_types": ["financials", "SEC", "estimates"], "latency": "low", "priority_required": "CRITICAL"}'::jsonb),
    ('SERPER', 'SEARCH', 'SNIPER', 50, 10, 0.002, TRUE, 'SERPER_API_KEY',
     '{"description": "Google Search API for fact-checking", "data_types": ["search", "verification"], "latency": "low", "owner": "CEIO"}'::jsonb)
ON CONFLICT (provider_name) DO UPDATE SET
    usage_tier = EXCLUDED.usage_tier,
    daily_limit = EXCLUDED.daily_limit;

-- ============================================================================
-- 5. CONFIGURE AGENT ACCESS POLICIES (Role-Based)
-- ============================================================================

-- CDMO: Chief Data & Memory Officer - Full LAKE access, limited PULSE
INSERT INTO fhq_governance.data_provider_policy (agent_id, authorized_providers, usage_tier, daily_quota, cost_weight, priority_required, created_by)
VALUES
    ('cdmo', ARRAY['YFINANCE', 'FRED'], 'LAKE', 999999, 1, 'NORMAL', 'CEO'),
    ('cdmo', ARRAY['TWELVEDATA', 'FINNHUB'], 'PULSE', 200, 3, 'NORMAL', 'CEO')
ON CONFLICT (agent_id, usage_tier) DO UPDATE SET
    authorized_providers = EXCLUDED.authorized_providers,
    daily_quota = EXCLUDED.daily_quota;

-- CRIO: Chief Research & Intelligence Officer - GraphRAG builder
INSERT INTO fhq_governance.data_provider_policy (agent_id, authorized_providers, usage_tier, daily_quota, cost_weight, priority_required, created_by)
VALUES
    ('crio', ARRAY['YFINANCE', 'FRED'], 'LAKE', 999999, 1, 'NORMAL', 'CEO'),
    ('crio', ARRAY['FINNHUB', 'MARKETAUX'], 'PULSE', 150, 4, 'NORMAL', 'CEO')
ON CONFLICT (agent_id, usage_tier) DO UPDATE SET
    authorized_providers = EXCLUDED.authorized_providers,
    daily_quota = EXCLUDED.daily_quota;

-- CFAO: Chief Foresight & Analytics Officer - Simulation focus
INSERT INTO fhq_governance.data_provider_policy (agent_id, authorized_providers, usage_tier, daily_quota, cost_weight, priority_required, created_by)
VALUES
    ('cfao', ARRAY['FRED'], 'LAKE', 999999, 1, 'NORMAL', 'CEO'),
    ('cfao', ARRAY['TWELVEDATA'], 'PULSE', 100, 3, 'NORMAL', 'CEO')
ON CONFLICT (agent_id, usage_tier) DO UPDATE SET
    authorized_providers = EXCLUDED.authorized_providers,
    daily_quota = EXCLUDED.daily_quota;

-- CEIO: Chief External Intelligence Officer - News & Verification
INSERT INTO fhq_governance.data_provider_policy (agent_id, authorized_providers, usage_tier, daily_quota, cost_weight, priority_required, created_by)
VALUES
    ('ceio', ARRAY['FRED'], 'LAKE', 999999, 1, 'NORMAL', 'CEO'),
    ('ceio', ARRAY['MARKETAUX', 'FINNHUB'], 'PULSE', 100, 5, 'NORMAL', 'CEO'),
    ('ceio', ARRAY['SERPER'], 'SNIPER', 50, 8, 'HIGH', 'CEO')
ON CONFLICT (agent_id, usage_tier) DO UPDATE SET
    authorized_providers = EXCLUDED.authorized_providers,
    daily_quota = EXCLUDED.daily_quota;

-- FINN: Financial Intelligence - Analysis focus
INSERT INTO fhq_governance.data_provider_policy (agent_id, authorized_providers, usage_tier, daily_quota, cost_weight, priority_required, created_by)
VALUES
    ('finn', ARRAY['YFINANCE', 'FRED'], 'LAKE', 999999, 1, 'NORMAL', 'CEO'),
    ('finn', ARRAY['TWELVEDATA', 'FINNHUB'], 'PULSE', 300, 3, 'NORMAL', 'CEO'),
    ('finn', ARRAY['ALPHAVANTAGE', 'FMP'], 'SNIPER', 25, 10, 'CRITICAL', 'CEO')
ON CONFLICT (agent_id, usage_tier) DO UPDATE SET
    authorized_providers = EXCLUDED.authorized_providers,
    daily_quota = EXCLUDED.daily_quota;

-- LARS: Strategy - Final confirmation only
INSERT INTO fhq_governance.data_provider_policy (agent_id, authorized_providers, usage_tier, daily_quota, cost_weight, priority_required, created_by)
VALUES
    ('lars', ARRAY['FRED'], 'LAKE', 999999, 1, 'NORMAL', 'CEO'),
    ('lars', ARRAY['ALPHAVANTAGE', 'FMP'], 'SNIPER', 10, 10, 'CRITICAL', 'CEO')
ON CONFLICT (agent_id, usage_tier) DO UPDATE SET
    authorized_providers = EXCLUDED.authorized_providers,
    daily_quota = EXCLUDED.daily_quota;

-- ============================================================================
-- 6. CREATE WATERFALL ENFORCEMENT FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.check_api_budget(
    p_agent_id TEXT,
    p_provider TEXT,
    p_priority TEXT DEFAULT 'NORMAL'
)
RETURNS TABLE (
    allowed BOOLEAN,
    remaining_quota INTEGER,
    usage_tier TEXT,
    reason TEXT
) AS $$
DECLARE
    v_policy RECORD;
    v_provider_info RECORD;
    v_used_today INTEGER;
    v_tier TEXT;
BEGIN
    -- Get provider info
    SELECT * INTO v_provider_info
    FROM fhq_governance.api_provider_registry
    WHERE provider_name = UPPER(p_provider) AND is_active = TRUE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 0, 'UNKNOWN'::TEXT, 'Provider not registered or inactive';
        RETURN;
    END IF;

    v_tier := v_provider_info.usage_tier;

    -- Get agent policy for this tier
    SELECT * INTO v_policy
    FROM fhq_governance.data_provider_policy
    WHERE agent_id = p_agent_id
      AND usage_tier = v_tier
      AND UPPER(p_provider) = ANY(authorized_providers);

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 0, v_tier, 'Agent not authorized for this provider';
        RETURN;
    END IF;

    -- Check priority requirements for SNIPER tier
    IF v_tier = 'SNIPER' AND p_priority != 'CRITICAL' THEN
        RETURN QUERY SELECT FALSE, v_policy.daily_quota, v_tier,
            'SNIPER tier requires CRITICAL priority (VEGA Guardrail)';
        RETURN;
    END IF;

    -- Calculate usage today
    SELECT COALESCE(SUM(credits_used), 0) INTO v_used_today
    FROM fhq_monitoring.api_budget_log
    WHERE agent_id = p_agent_id
      AND provider = UPPER(p_provider)
      AND created_at >= CURRENT_DATE;

    -- Check quota
    IF v_used_today >= v_policy.daily_quota THEN
        RETURN QUERY SELECT FALSE, 0, v_tier, 'Daily quota exhausted';
        RETURN;
    END IF;

    RETURN QUERY SELECT TRUE, (v_policy.daily_quota - v_used_today)::INTEGER, v_tier, 'OK';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. CREATE USAGE LOGGING FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION fhq_governance.log_api_usage(
    p_agent_id TEXT,
    p_provider TEXT,
    p_priority TEXT DEFAULT 'NORMAL',
    p_justification TEXT DEFAULT NULL,
    p_credits INTEGER DEFAULT 1
)
RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
    v_tier TEXT;
    v_check RECORD;
BEGIN
    -- Check budget first
    SELECT * INTO v_check FROM fhq_governance.check_api_budget(p_agent_id, p_provider, p_priority);

    IF NOT v_check.allowed THEN
        RAISE EXCEPTION 'API call blocked: %', v_check.reason;
    END IF;

    v_tier := v_check.usage_tier;

    -- SNIPER tier requires justification
    IF v_tier = 'SNIPER' AND p_justification IS NULL THEN
        RAISE EXCEPTION 'SNIPER tier requires justification (ADR-002 compliance)';
    END IF;

    -- Log the usage
    INSERT INTO fhq_monitoring.api_budget_log (
        agent_id, provider, usage_tier, credits_used, priority_level, justification
    ) VALUES (
        p_agent_id, UPPER(p_provider), v_tier, p_credits, p_priority, p_justification
    ) RETURNING log_id INTO v_log_id;

    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. CREATE DAILY BUDGET SUMMARY VIEW
-- ============================================================================

CREATE OR REPLACE VIEW fhq_monitoring.api_budget_summary AS
SELECT
    abl.agent_id,
    abl.provider,
    abl.usage_tier,
    apr.daily_limit AS provider_limit,
    dpp.daily_quota AS agent_quota,
    SUM(abl.credits_used) AS used_today,
    LEAST(apr.daily_limit, dpp.daily_quota) - SUM(abl.credits_used) AS remaining,
    COUNT(*) AS call_count
FROM fhq_monitoring.api_budget_log abl
JOIN fhq_governance.api_provider_registry apr ON apr.provider_name = abl.provider
LEFT JOIN fhq_governance.data_provider_policy dpp
    ON dpp.agent_id = abl.agent_id AND dpp.usage_tier = abl.usage_tier
WHERE abl.created_at >= CURRENT_DATE
GROUP BY abl.agent_id, abl.provider, abl.usage_tier, apr.daily_limit, dpp.daily_quota;

-- ============================================================================
-- 9. GOVERNANCE CHANGE LOG
-- ============================================================================

INSERT INTO fhq_governance.change_log (
    change_type,
    change_scope,
    change_description,
    authority,
    approval_gate,
    hash_chain_id,
    agent_signatures,
    created_at,
    created_by
) VALUES (
    'api_scarcity_waterfall',
    'data_governance',
    'MBB C-LEVEL DIRECTIVE: API Scarcity & Waterfall Architecture - Tier 1 (LAKE): yfinance/FRED unlimited, Tier 2 (PULSE): Twelve Data/Finnhub/MarketAux monitored, Tier 3 (SNIPER): Alpha Vantage/FMP/Serper critical-only. VEGA guardrails enforce CRITICAL priority for SNIPER tier.',
    'CEO MBB C-LEVEL DIRECTIVE',
    'G4-ceo-approved',
    'HC-API-SCARCITY-WATERFALL-' || to_char(NOW(), 'YYYYMMDD_HH24MISS'),
    jsonb_build_object(
        'ceo', 'CEO_SIGNATURE_API_SCARCITY',
        'activation_timestamp', NOW(),
        'waterfall_tiers', ARRAY['LAKE', 'PULSE', 'SNIPER'],
        'compliance', ARRAY['ADR-002', 'ADR-003', 'ADR-008', 'ADR-012', 'ADR-014']
    ),
    NOW(),
    'ceo'
);

-- ============================================================================
-- 10. VERIFICATION
-- ============================================================================

DO $$
DECLARE
    v_provider_count INTEGER;
    v_policy_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_provider_count FROM fhq_governance.api_provider_registry;
    SELECT COUNT(*) INTO v_policy_count FROM fhq_governance.data_provider_policy;

    IF v_provider_count < 7 THEN
        RAISE EXCEPTION 'API provider registry incomplete: % providers', v_provider_count;
    END IF;

    IF v_policy_count < 10 THEN
        RAISE EXCEPTION 'Data provider policies incomplete: % policies', v_policy_count;
    END IF;

    RAISE NOTICE '✅ API Scarcity & Waterfall verified (% providers, % policies)', v_provider_count, v_policy_count;
END $$;

-- Test the waterfall function
DO $$
DECLARE
    v_result RECORD;
BEGIN
    -- Test LAKE access (should always work)
    SELECT * INTO v_result FROM fhq_governance.check_api_budget('cdmo', 'YFINANCE', 'NORMAL');
    IF NOT v_result.allowed THEN
        RAISE EXCEPTION 'LAKE access failed for CDMO';
    END IF;

    -- Test SNIPER without CRITICAL (should fail)
    SELECT * INTO v_result FROM fhq_governance.check_api_budget('finn', 'ALPHAVANTAGE', 'NORMAL');
    IF v_result.allowed THEN
        RAISE EXCEPTION 'SNIPER should require CRITICAL priority';
    END IF;

    -- Test SNIPER with CRITICAL (should work)
    SELECT * INTO v_result FROM fhq_governance.check_api_budget('finn', 'ALPHAVANTAGE', 'CRITICAL');
    IF NOT v_result.allowed THEN
        RAISE EXCEPTION 'SNIPER with CRITICAL should be allowed';
    END IF;

    RAISE NOTICE '✅ Waterfall enforcement verified (LAKE open, SNIPER requires CRITICAL)';
END $$;

COMMIT;

-- ============================================================================
-- DISPLAY SUMMARY
-- ============================================================================

\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo 'MIGRATION 021: API SCARCITY & WATERFALL ARCHITECTURE – COMPLETE'
\echo '═══════════════════════════════════════════════════════════════════════════'
\echo ''
\echo 'DATA WATERFALL PROTOCOL:'
\echo '  ✅ Tier 1 (LAKE): yfinance, FRED – Unlimited'
\echo '  ✅ Tier 2 (PULSE): Twelve Data (800), Finnhub (3600), MarketAux (50)'
\echo '  ✅ Tier 3 (SNIPER): Alpha Vantage (25), FMP (250), Serper (50)'
\echo ''
\echo 'AGENT ACCESS POLICIES:'
\echo '  ✅ CDMO: LAKE + PULSE access for synthetic data'
\echo '  ✅ CRIO: LAKE + PULSE access for GraphRAG'
\echo '  ✅ CFAO: LAKE + PULSE for foresight simulation'
\echo '  ✅ CEIO: PULSE + SNIPER (Serper) for fact-checking'
\echo '  ✅ FINN: Full stack access for alpha generation'
\echo '  ✅ LARS: LAKE + SNIPER for final confirmation'
\echo ''
\echo 'GOVERNANCE FUNCTIONS:'
\echo '  ✅ fhq_governance.check_api_budget() – Pre-flight check'
\echo '  ✅ fhq_governance.log_api_usage() – ADR-002 compliant logging'
\echo '  ✅ fhq_monitoring.api_budget_summary – Daily usage view'
\echo ''
\echo 'VEGA GUARDRAILS:'
\echo '  ✅ SNIPER tier requires CRITICAL priority'
\echo '  ✅ SNIPER tier requires justification'
\echo '  ✅ Budget exhaustion blocks API calls'
\echo ''
\echo '═══════════════════════════════════════════════════════════════════════════'
