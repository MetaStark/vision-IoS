-- ============================================================================
-- Migration 088: IoS-014 Vendor Limits Foundation
-- Authority: CEO DIRECTIVE — IoS-014 BUILD & AUTONOMOUS AGENT ACTIVATION
--
-- Creates vendor_limits and vendor_usage_counters tables for economic safety
-- enforcement as mandated by ADR-012 and IoS-014 Section 4.3
-- ============================================================================

-- Ensure meta schema exists
CREATE SCHEMA IF NOT EXISTS fhq_meta;

-- =============================================================================
-- Table: fhq_meta.vendor_limits
-- Purpose: Configuration of vendor quotas, soft ceilings, and fallback routing
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_meta.vendor_limits (
    vendor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_name TEXT NOT NULL UNIQUE,

    -- Tier classification per ADR-012
    tier TEXT NOT NULL DEFAULT 'LAKE',
    CONSTRAINT valid_tier CHECK (tier IN ('LAKE', 'PULSE', 'SNIPER')),

    -- Quota configuration
    free_tier_limit INTEGER NOT NULL DEFAULT 0,
    interval_type TEXT NOT NULL DEFAULT 'DAY',
    CONSTRAINT valid_interval CHECK (interval_type IN ('MINUTE', 'HOUR', 'DAY', 'MONTH')),

    -- Soft ceiling (default 90% per CEO Directive)
    soft_ceiling_pct NUMERIC(3,2) NOT NULL DEFAULT 0.90,
    CONSTRAINT valid_ceiling CHECK (soft_ceiling_pct > 0 AND soft_ceiling_pct <= 1.0),

    -- Hard limit (absolute maximum, never exceed)
    hard_limit INTEGER,

    -- Priority routing
    priority_rank INTEGER NOT NULL DEFAULT 100,
    fallback_vendor_id UUID REFERENCES fhq_meta.vendor_limits(vendor_id),

    -- Data domains this vendor serves
    data_domains TEXT[] NOT NULL DEFAULT '{}',

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_free_tier BOOLEAN NOT NULL DEFAULT TRUE,

    -- API configuration
    api_key_env_var TEXT,
    base_url TEXT,
    rate_limit_per_second NUMERIC(5,2),

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'STIG'
);

-- =============================================================================
-- Table: fhq_meta.vendor_usage_counters
-- Purpose: Live tracking of vendor API usage per interval
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_meta.vendor_usage_counters (
    counter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES fhq_meta.vendor_limits(vendor_id),

    -- Interval tracking
    interval_start TIMESTAMPTZ NOT NULL,
    interval_type TEXT NOT NULL,

    -- Usage metrics
    current_usage INTEGER NOT NULL DEFAULT 0,
    peak_usage INTEGER NOT NULL DEFAULT 0,

    -- Soft ceiling tracking
    soft_ceiling_reached_at TIMESTAMPTZ,
    hard_limit_reached_at TIMESTAMPTZ,

    -- Metadata
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint per vendor per interval
    CONSTRAINT unique_vendor_interval UNIQUE (vendor_id, interval_start, interval_type)
);

-- =============================================================================
-- Table: fhq_governance.vendor_quota_events
-- Purpose: Audit log for quota-related decisions
-- =============================================================================
CREATE TABLE IF NOT EXISTS fhq_governance.vendor_quota_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES fhq_meta.vendor_limits(vendor_id),

    -- Event details
    event_type TEXT NOT NULL,
    CONSTRAINT valid_event_type CHECK (event_type IN (
        'USAGE_INCREMENT',
        'SOFT_CEILING_WARNING',
        'SOFT_CEILING_REACHED',
        'HARD_LIMIT_REACHED',
        'FALLBACK_TRIGGERED',
        'TASK_SKIPPED',
        'INTERVAL_RESET'
    )),

    -- Context
    task_name TEXT,
    previous_usage INTEGER,
    new_usage INTEGER,
    ceiling_value INTEGER,

    -- Decision
    decision TEXT,
    decision_rationale TEXT,
    fallback_vendor_id UUID,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT NOT NULL DEFAULT 'IOS014'
);

-- =============================================================================
-- Indexes
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_vendor_limits_tier ON fhq_meta.vendor_limits(tier);
CREATE INDEX IF NOT EXISTS idx_vendor_limits_active ON fhq_meta.vendor_limits(is_active);
CREATE INDEX IF NOT EXISTS idx_vendor_limits_domains ON fhq_meta.vendor_limits USING GIN(data_domains);
CREATE INDEX IF NOT EXISTS idx_vendor_usage_vendor ON fhq_meta.vendor_usage_counters(vendor_id);
CREATE INDEX IF NOT EXISTS idx_vendor_usage_interval ON fhq_meta.vendor_usage_counters(interval_start);
CREATE INDEX IF NOT EXISTS idx_quota_events_vendor ON fhq_governance.vendor_quota_events(vendor_id);
CREATE INDEX IF NOT EXISTS idx_quota_events_type ON fhq_governance.vendor_quota_events(event_type);

-- =============================================================================
-- Seed data: Initial vendor configuration
-- =============================================================================

-- Tier 1: LAKE (Free sources)
INSERT INTO fhq_meta.vendor_limits (vendor_name, tier, free_tier_limit, interval_type, soft_ceiling_pct, priority_rank, data_domains, api_key_env_var, is_free_tier)
VALUES
    ('YFINANCE', 'LAKE', 2000, 'HOUR', 0.90, 10, ARRAY['OHLCV', 'CRYPTO', 'FX', 'EQUITY'], NULL, TRUE),
    ('BINANCE_PUBLIC', 'LAKE', 1200, 'MINUTE', 0.90, 5, ARRAY['CRYPTO', 'OHLCV'], NULL, TRUE),
    ('FRED', 'LAKE', 500, 'DAY', 0.90, 10, ARRAY['MACRO', 'RATES'], 'FRED_API_KEY', TRUE)
ON CONFLICT (vendor_name) DO NOTHING;

-- Tier 2: PULSE (Limited paid)
INSERT INTO fhq_meta.vendor_limits (vendor_name, tier, free_tier_limit, interval_type, soft_ceiling_pct, priority_rank, data_domains, api_key_env_var, is_free_tier)
VALUES
    ('MARKETAUX', 'PULSE', 100, 'DAY', 0.90, 50, ARRAY['NEWS', 'SENTIMENT'], 'MARKETAUX_API_KEY', TRUE),
    ('TWELVEDATA', 'PULSE', 800, 'DAY', 0.90, 40, ARRAY['OHLCV', 'FX', 'CRYPTO'], 'TWELVEDATA_API_KEY', TRUE),
    ('FINNHUB', 'PULSE', 60, 'MINUTE', 0.90, 45, ARRAY['NEWS', 'OHLCV', 'FUNDAMENTALS'], 'FINNHUB_API_KEY', TRUE)
ON CONFLICT (vendor_name) DO NOTHING;

-- Tier 3: SNIPER (Paid, use sparingly)
INSERT INTO fhq_meta.vendor_limits (vendor_name, tier, free_tier_limit, interval_type, soft_ceiling_pct, priority_rank, data_domains, api_key_env_var, is_free_tier)
VALUES
    ('ALPHAVANTAGE', 'SNIPER', 25, 'DAY', 0.90, 80, ARRAY['OHLCV', 'FX', 'CRYPTO', 'FUNDAMENTALS'], 'ALPHAVANTAGE_API_KEY', TRUE),
    ('FMP', 'SNIPER', 250, 'DAY', 0.90, 85, ARRAY['OHLCV', 'FUNDAMENTALS', 'NEWS'], 'FMP_API_KEY', TRUE)
ON CONFLICT (vendor_name) DO NOTHING;

-- Set fallback routing (SNIPER falls back to PULSE, PULSE falls back to LAKE)
UPDATE fhq_meta.vendor_limits SET fallback_vendor_id = (SELECT vendor_id FROM fhq_meta.vendor_limits WHERE vendor_name = 'TWELVEDATA')
WHERE vendor_name = 'ALPHAVANTAGE';

UPDATE fhq_meta.vendor_limits SET fallback_vendor_id = (SELECT vendor_id FROM fhq_meta.vendor_limits WHERE vendor_name = 'YFINANCE')
WHERE vendor_name = 'TWELVEDATA';

-- =============================================================================
-- Function: Check if vendor usage is within soft ceiling
-- =============================================================================
CREATE OR REPLACE FUNCTION fhq_meta.check_vendor_quota(
    p_vendor_name TEXT,
    p_calls_needed INTEGER DEFAULT 1
)
RETURNS TABLE (
    can_proceed BOOLEAN,
    current_usage INTEGER,
    soft_ceiling INTEGER,
    hard_limit INTEGER,
    fallback_vendor TEXT,
    decision TEXT
) AS $$
DECLARE
    v_vendor RECORD;
    v_counter RECORD;
    v_soft_ceiling INTEGER;
    v_interval_start TIMESTAMPTZ;
BEGIN
    -- Get vendor config
    SELECT * INTO v_vendor FROM fhq_meta.vendor_limits WHERE vendor_name = p_vendor_name AND is_active = TRUE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 0, 0, 0, NULL::TEXT, 'VENDOR_NOT_FOUND'::TEXT;
        RETURN;
    END IF;

    -- Calculate interval start
    v_interval_start := CASE v_vendor.interval_type
        WHEN 'MINUTE' THEN date_trunc('minute', NOW())
        WHEN 'HOUR' THEN date_trunc('hour', NOW())
        WHEN 'DAY' THEN date_trunc('day', NOW())
        WHEN 'MONTH' THEN date_trunc('month', NOW())
    END;

    -- Get or create counter
    SELECT * INTO v_counter FROM fhq_meta.vendor_usage_counters
    WHERE vendor_id = v_vendor.vendor_id AND interval_start = v_interval_start;

    IF NOT FOUND THEN
        INSERT INTO fhq_meta.vendor_usage_counters (vendor_id, interval_start, interval_type, current_usage)
        VALUES (v_vendor.vendor_id, v_interval_start, v_vendor.interval_type, 0)
        RETURNING * INTO v_counter;
    END IF;

    -- Calculate soft ceiling
    v_soft_ceiling := FLOOR(v_vendor.free_tier_limit * v_vendor.soft_ceiling_pct);

    -- Check if we can proceed
    IF v_counter.current_usage + p_calls_needed <= v_soft_ceiling THEN
        RETURN QUERY SELECT
            TRUE,
            v_counter.current_usage,
            v_soft_ceiling,
            v_vendor.hard_limit,
            NULL::TEXT,
            'PROCEED'::TEXT;
    ELSIF v_vendor.fallback_vendor_id IS NOT NULL THEN
        RETURN QUERY SELECT
            FALSE,
            v_counter.current_usage,
            v_soft_ceiling,
            v_vendor.hard_limit,
            (SELECT vendor_name FROM fhq_meta.vendor_limits WHERE vendor_id = v_vendor.fallback_vendor_id),
            'USE_FALLBACK'::TEXT;
    ELSE
        RETURN QUERY SELECT
            FALSE,
            v_counter.current_usage,
            v_soft_ceiling,
            v_vendor.hard_limit,
            NULL::TEXT,
            'SKIP_QUOTA_PROTECTION'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Function: Increment vendor usage
-- =============================================================================
CREATE OR REPLACE FUNCTION fhq_meta.increment_vendor_usage(
    p_vendor_name TEXT,
    p_calls INTEGER DEFAULT 1,
    p_task_name TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_vendor RECORD;
    v_interval_start TIMESTAMPTZ;
    v_new_usage INTEGER;
BEGIN
    SELECT * INTO v_vendor FROM fhq_meta.vendor_limits WHERE vendor_name = p_vendor_name;
    IF NOT FOUND THEN RETURN FALSE; END IF;

    v_interval_start := CASE v_vendor.interval_type
        WHEN 'MINUTE' THEN date_trunc('minute', NOW())
        WHEN 'HOUR' THEN date_trunc('hour', NOW())
        WHEN 'DAY' THEN date_trunc('day', NOW())
        WHEN 'MONTH' THEN date_trunc('month', NOW())
    END;

    INSERT INTO fhq_meta.vendor_usage_counters (vendor_id, interval_start, interval_type, current_usage)
    VALUES (v_vendor.vendor_id, v_interval_start, v_vendor.interval_type, p_calls)
    ON CONFLICT (vendor_id, interval_start, interval_type)
    DO UPDATE SET
        current_usage = fhq_meta.vendor_usage_counters.current_usage + p_calls,
        peak_usage = GREATEST(fhq_meta.vendor_usage_counters.peak_usage, fhq_meta.vendor_usage_counters.current_usage + p_calls),
        last_updated = NOW()
    RETURNING current_usage INTO v_new_usage;

    -- Log the usage
    INSERT INTO fhq_governance.vendor_quota_events (vendor_id, event_type, task_name, previous_usage, new_usage)
    VALUES (v_vendor.vendor_id, 'USAGE_INCREMENT', p_task_name, v_new_usage - p_calls, v_new_usage);

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Log migration
-- =============================================================================
INSERT INTO fhq_governance.governance_actions_log (
    action_type, action_target, action_target_type, initiated_by,
    decision, decision_rationale, hash_chain_id
) VALUES (
    'MIGRATION',
    'ios014_vendor_limits_foundation',
    'DATABASE_SCHEMA',
    'STIG',
    'COMPLETED',
    'Created vendor_limits, vendor_usage_counters, and vendor_quota_events tables per CEO DIRECTIVE IoS-014',
    'HC-MIGRATION-088-2025-12-07'
);

COMMENT ON TABLE fhq_meta.vendor_limits IS 'Vendor quota configuration for ADR-012 economic safety. 90% soft ceiling enforced by IoS-014.';
COMMENT ON TABLE fhq_meta.vendor_usage_counters IS 'Live vendor API usage tracking per interval.';
COMMENT ON TABLE fhq_governance.vendor_quota_events IS 'Audit log for vendor quota decisions and events.';
