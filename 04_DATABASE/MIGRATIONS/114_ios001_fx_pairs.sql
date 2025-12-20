-- ============================================================================
-- Migration 114: IoS-001 FX Currency Pair Registration
-- 20 Most Liquid FX Pairs (G10 + Emerging)
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-012 (API Waterfall)
-- IoS Reference: IoS-001 §2.1, §4.1
-- CEO Directive: 252-day Iron Curtain for FX
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: G10 Major Currency Pairs (7 majors)
-- ============================================================================
-- Data source: Refinitiv/AlphaVantage - yahoo_suffix = =X

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- G10 Majors (vs USD)
    ('EURUSD=X', 'EURUSD=X', 'XFOR', 'FX', 'USD', 1000, 0.00001, 'G10_MAJOR', 'LOW', true,
     500000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('GBPUSD=X', 'GBPUSD=X', 'XFOR', 'FX', 'USD', 1000, 0.00001, 'G10_MAJOR', 'LOW', true,
     300000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('USDJPY=X', 'USDJPY=X', 'XFOR', 'FX', 'JPY', 1000, 0.001, 'G10_MAJOR', 'LOW', true,
     400000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('USDCHF=X', 'USDCHF=X', 'XFOR', 'FX', 'CHF', 1000, 0.00001, 'G10_MAJOR', 'LOW', true,
     100000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('AUDUSD=X', 'AUDUSD=X', 'XFOR', 'FX', 'USD', 1000, 0.00001, 'G10_MAJOR', 'LOW', true,
     200000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('USDCAD=X', 'USDCAD=X', 'XFOR', 'FX', 'CAD', 1000, 0.00001, 'G10_MAJOR', 'LOW', true,
     150000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('NZDUSD=X', 'NZDUSD=X', 'XFOR', 'FX', 'USD', 1000, 0.00001, 'G10_MAJOR', 'LOW', true,
     50000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),

    -- G10 Crosses
    ('EURGBP=X', 'EURGBP=X', 'XFOR', 'FX', 'GBP', 1000, 0.00001, 'G10_CROSS', 'LOW', true,
     80000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('EURJPY=X', 'EURJPY=X', 'XFOR', 'FX', 'JPY', 1000, 0.001, 'G10_CROSS', 'LOW', true,
     100000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('GBPJPY=X', 'GBPJPY=X', 'XFOR', 'FX', 'JPY', 1000, 0.001, 'G10_CROSS', 'MEDIUM', true,
     80000000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('AUDJPY=X', 'AUDJPY=X', 'XFOR', 'FX', 'JPY', 1000, 0.001, 'G10_CROSS', 'MEDIUM', true,
     40000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('CADJPY=X', 'CADJPY=X', 'XFOR', 'FX', 'JPY', 1000, 0.001, 'G10_CROSS', 'MEDIUM', true,
     30000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('CHFJPY=X', 'CHFJPY=X', 'XFOR', 'FX', 'JPY', 1000, 0.001, 'G10_CROSS', 'MEDIUM', true,
     30000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('EURCHF=X', 'EURCHF=X', 'XFOR', 'FX', 'CHF', 1000, 0.00001, 'G10_CROSS', 'LOW', true,
     50000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('EURAUD=X', 'EURAUD=X', 'XFOR', 'FX', 'AUD', 1000, 0.00001, 'G10_CROSS', 'MEDIUM', true,
     30000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),

    -- Nordic & Scandinavian Currencies (Important for Oslo Børs FX exposure)
    ('USDNOK=X', 'USDNOK=X', 'XFOR', 'FX', 'NOK', 1000, 0.0001, 'NORDIC', 'MEDIUM', true,
     20000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('USDSEK=X', 'USDSEK=X', 'XFOR', 'FX', 'SEK', 1000, 0.0001, 'NORDIC', 'MEDIUM', true,
     25000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('EURNOK=X', 'EURNOK=X', 'XFOR', 'FX', 'NOK', 1000, 0.0001, 'NORDIC', 'MEDIUM', true,
     15000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('EURSEK=X', 'EURSEK=X', 'XFOR', 'FX', 'SEK', 1000, 0.0001, 'NORDIC', 'MEDIUM', true,
     18000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),

    -- Emerging Market FX
    ('USDMXN=X', 'USDMXN=X', 'XFOR', 'FX', 'MXN', 1000, 0.0001, 'EMERGING', 'HIGH', true,
     50000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('USDZAR=X', 'USDZAR=X', 'XFOR', 'FX', 'ZAR', 1000, 0.0001, 'EMERGING', 'HIGH', true,
     30000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('USDTRY=X', 'USDTRY=X', 'XFOR', 'FX', 'TRY', 1000, 0.0001, 'EMERGING', 'VERY_HIGH', true,
     20000000000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('USDHKD=X', 'USDHKD=X', 'XFOR', 'FX', 'HKD', 1000, 0.00001, 'ASIA', 'LOW', true,
     30000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW()),
    ('USDSGD=X', 'USDSGD=X', 'XFOR', 'FX', 'SGD', 1000, 0.00001, 'ASIA', 'LOW', true,
     25000000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    exchange_mic = EXCLUDED.exchange_mic,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    quarantine_threshold = EXCLUDED.quarantine_threshold,
    full_history_threshold = EXCLUDED.full_history_threshold,
    price_source_field = EXCLUDED.price_source_field,
    updated_at = NOW();

-- ============================================================================
-- PART B: Governance Logging (ADR-002)
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
    'ASSET_ONBOARDING',
    'fhq_meta.assets (FX)',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §2.1 Asset Onboarding - FX (XFOR): 24 currency pairs registered. Coverage: G10 Majors (7), G10 Crosses (8), Nordic (4), Emerging (5). All assets in QUARANTINED status with 252-day Iron Curtain. price_source_field = close. Nordic pairs (NOK, SEK) critical for Oslo Børs FX exposure analysis.',
    false,
    'MIG-114-IOS001-FX-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART C: Verification
-- ============================================================================

DO $$
DECLARE
    fx_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO fx_count
    FROM fhq_meta.assets
    WHERE asset_class = 'FX' AND active_flag = true;

    IF fx_count < 20 THEN
        RAISE WARNING 'Expected at least 20 FX pairs, found %', fx_count;
    ELSE
        RAISE NOTICE 'FX onboarding complete: % currency pairs registered', fx_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Migration 114 Complete
-- FX pairs: 24 registered (XFOR exchange)
-- All assets in QUARANTINED status pending 252-day Iron Curtain validation
-- Next: Migration 115 (US Equities)
-- ============================================================================
