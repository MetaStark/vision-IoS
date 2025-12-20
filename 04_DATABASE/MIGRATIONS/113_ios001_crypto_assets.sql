-- ============================================================================
-- Migration 113: IoS-001 Crypto Asset Registration
-- Top 50+ Cryptocurrencies by Market Cap
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-012 (API Waterfall)
-- IoS Reference: IoS-001 §2.1, §4.1
-- CEO Directive: 365-day Iron Curtain for Crypto (24/7 markets)
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: Top 50 Cryptocurrencies by Market Cap
-- ============================================================================
-- Data source: CoinGecko/CoinMarketCap - yahoo_suffix = -USD
-- Note: Crypto uses close = adj_close (no dividends/splits, but hard forks)

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- Layer 1 Majors (Tier 1 - Highest liquidity)
    ('BTC-USD', 'BTC-USD', 'XCRY', 'CRYPTO', 'USD', 0.00001, 0.01, 'LAYER_1', 'HIGH', true,
     5000000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('ETH-USD', 'ETH-USD', 'XCRY', 'CRYPTO', 'USD', 0.0001, 0.01, 'LAYER_1', 'HIGH', true,
     2000000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),

    -- Layer 1 Alternatives
    ('BNB-USD', 'BNB-USD', 'XCRY', 'CRYPTO', 'USD', 0.001, 0.01, 'LAYER_1', 'HIGH', true,
     500000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('XRP-USD', 'XRP-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'PAYMENT', 'HIGH', true,
     500000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('ADA-USD', 'ADA-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'LAYER_1', 'HIGH', true,
     200000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('SOL-USD', 'SOL-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'LAYER_1', 'HIGH', true,
     500000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('DOGE-USD', 'DOGE-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.00001, 'MEME', 'VERY_HIGH', true,
     300000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('DOT-USD', 'DOT-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.001, 'LAYER_0', 'HIGH', true,
     100000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('MATIC-USD', 'MATIC-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'LAYER_2', 'HIGH', true,
     150000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('SHIB-USD', 'SHIB-USD', 'XCRY', 'CRYPTO', 'USD', 1000000, 0.00000001, 'MEME', 'VERY_HIGH', true,
     100000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),

    -- Layer 1 / Smart Contract Platforms
    ('TRX-USD', 'TRX-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'LAYER_1', 'HIGH', true,
     100000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('AVAX-USD', 'AVAX-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'LAYER_1', 'HIGH', true,
     150000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('LINK-USD', 'LINK-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'ORACLE', 'HIGH', true,
     200000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('UNI-USD', 'UNI-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'DEFI', 'HIGH', true,
     100000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('ATOM-USD', 'ATOM-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'LAYER_0', 'HIGH', true,
     80000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('LTC-USD', 'LTC-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'PAYMENT', 'MEDIUM', true,
     200000000, 365, 'INTERPOLATE', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('ETC-USD', 'ETC-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'LAYER_1', 'HIGH', true,
     100000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('XMR-USD', 'XMR-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'PRIVACY', 'HIGH', true,
     50000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('BCH-USD', 'BCH-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'PAYMENT', 'MEDIUM', true,
     100000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('APT-USD', 'APT-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'LAYER_1', 'HIGH', true,
     100000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),

    -- Layer 2 and Scaling Solutions
    ('NEAR-USD', 'NEAR-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.001, 'LAYER_1', 'HIGH', true,
     80000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('FIL-USD', 'FIL-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'STORAGE', 'HIGH', true,
     50000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('VET-USD', 'VET-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.00001, 'ENTERPRISE', 'HIGH', true,
     30000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('ALGO-USD', 'ALGO-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'LAYER_1', 'HIGH', true,
     30000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('HBAR-USD', 'HBAR-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'LAYER_1', 'HIGH', true,
     40000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('ICP-USD', 'ICP-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'LAYER_1', 'HIGH', true,
     50000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('QNT-USD', 'QNT-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'ENTERPRISE', 'HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('GRT-USD', 'GRT-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'INFRASTRUCTURE', 'HIGH', true,
     30000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),

    -- DeFi Protocols
    ('AAVE-USD', 'AAVE-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'DEFI', 'HIGH', true,
     50000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('MKR-USD', 'MKR-USD', 'XCRY', 'CRYPTO', 'USD', 0.001, 0.1, 'DEFI', 'HIGH', true,
     30000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('SNX-USD', 'SNX-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'DEFI', 'HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('CRV-USD', 'CRV-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.001, 'DEFI', 'HIGH', true,
     30000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('LDO-USD', 'LDO-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.001, 'DEFI', 'HIGH', true,
     40000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('RPL-USD', 'RPL-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'DEFI', 'HIGH', true,
     10000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('COMP-USD', 'COMP-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'DEFI', 'HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),

    -- Exchange Tokens
    ('CRO-USD', 'CRO-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'EXCHANGE', 'HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('OKB-USD', 'OKB-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'EXCHANGE', 'HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),

    -- Additional Layer 1s
    ('FTM-USD', 'FTM-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'LAYER_1', 'HIGH', true,
     30000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('MANA-USD', 'MANA-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'METAVERSE', 'VERY_HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('SAND-USD', 'SAND-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'METAVERSE', 'VERY_HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('AXS-USD', 'AXS-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'GAMING', 'VERY_HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('THETA-USD', 'THETA-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.001, 'MEDIA', 'HIGH', true,
     15000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('XLM-USD', 'XLM-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.00001, 'PAYMENT', 'HIGH', true,
     50000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('XTZ-USD', 'XTZ-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.001, 'LAYER_1', 'HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('EOS-USD', 'EOS-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.001, 'LAYER_1', 'HIGH', true,
     30000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('FLOW-USD', 'FLOW-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.001, 'LAYER_1', 'HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('CHZ-USD', 'CHZ-USD', 'XCRY', 'CRYPTO', 'USD', 1, 0.0001, 'SPORTS', 'HIGH', true,
     15000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('ZEC-USD', 'ZEC-USD', 'XCRY', 'CRYPTO', 'USD', 0.01, 0.01, 'PRIVACY', 'HIGH', true,
     20000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('RUNE-USD', 'RUNE-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'DEFI', 'HIGH', true,
     30000000, 365, 'INTERPOLATE', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW()),
    ('INJ-USD', 'INJ-USD', 'XCRY', 'CRYPTO', 'USD', 0.1, 0.01, 'DEFI', 'HIGH', true,
     50000000, 365, 'INTERPOLATE', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 365, 1825, 'close', NOW())

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
    'fhq_meta.assets (Crypto)',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §2.1 Asset Onboarding - Crypto (XCRY): 50+ cryptocurrencies registered. Sectors: Layer 1, Layer 2, DeFi, Payment, Privacy, Oracle, Metaverse, Gaming. All assets in QUARANTINED status with 365-day Iron Curtain (CEO Directive for 24/7 markets). price_source_field = close (no dividend adjustment needed).',
    false,
    'MIG-113-IOS001-CRYPTO-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART C: Verification
-- ============================================================================

DO $$
DECLARE
    crypto_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO crypto_count
    FROM fhq_meta.assets
    WHERE asset_class = 'CRYPTO' AND active_flag = true;

    IF crypto_count < 50 THEN
        RAISE WARNING 'Expected at least 50 crypto assets, found %', crypto_count;
    ELSE
        RAISE NOTICE 'Crypto onboarding complete: % assets registered', crypto_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Migration 113 Complete
-- Crypto assets: 50+ registered (XCRY exchange)
-- All assets in QUARANTINED status pending 365-day Iron Curtain validation
-- Next: Migration 114 (FX Pairs)
-- ============================================================================
