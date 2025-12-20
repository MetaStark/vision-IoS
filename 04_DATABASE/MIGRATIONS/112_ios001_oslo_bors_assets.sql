-- ============================================================================
-- Migration 112: IoS-001 Oslo Børs Asset Registration
-- Full OBX Index + Mid-Cap Norwegian Equities (50+ assets)
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-012 (API Waterfall)
-- IoS Reference: IoS-001 §2.1, §4.1
-- CEO Directive: Rate-limit protection, batch processing
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: OBX Index Components (25 largest Norwegian stocks)
-- ============================================================================
-- Data source: Oslo Børs / Euronext - yahoo_suffix = .OL

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- Energy (Largest sector on Oslo Børs)
    ('EQNR.OL', 'EQNR.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AKRBP.OL', 'AKRBP.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     10000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('VAR.OL', 'VAR.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'HIGH', true,
     5000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SUBC.OL', 'SUBC.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     5000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Financial Services
    ('DNB.OL', 'DNB.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('STB.OL', 'STB.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     5000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GJFAH.OL', 'GJFAH.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Seafood (Major Norwegian export)
    ('MOWI.OL', 'MOWI.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_STAPLES', 'MEDIUM', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SALM.OL', 'SALM.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_STAPLES', 'MEDIUM', true,
     10000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BAKKA.OL', 'BAKKA.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_STAPLES', 'MEDIUM', true,
     5000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LSG.OL', 'LSG.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_STAPLES', 'MEDIUM', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AUSS.OL', 'AUSS.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_STAPLES', 'MEDIUM', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Telecom
    ('TEL.OL', 'TEL.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'COMMUNICATION', 'LOW', true,
     15000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Industrials
    ('YAR.OL', 'YAR.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     15000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ORK.OL', 'ORK.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_STAPLES', 'LOW', true,
     10000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NHY.OL', 'NHY.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     10000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AKER.OL', 'AKER.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     5000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('KOG.OL', 'KOG.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SCHB.OL', 'SCHB.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TOM.OL', 'TOM.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Technology & Software
    ('KAHOT.OL', 'KAHOT.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CRAYN.OL', 'CRAYN.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Shipping
    ('FLNG.OL', 'FLNG.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'HIGH', true,
     5000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('FRO.OL', 'FRO.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     5000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('HAFNI.OL', 'HAFNI.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    exchange_mic = EXCLUDED.exchange_mic,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    updated_at = NOW();

-- ============================================================================
-- PART B: Additional Oslo Børs Mid-Cap Stocks (25+ more)
-- ============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- More Energy/Oil Services
    ('BWO.OL', 'BWO.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'HIGH', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AKSO.OL', 'AKSO.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'HIGH', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PGS.OL', 'PGS.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'HIGH', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TGS.OL', 'TGS.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AKVA.OL', 'AKVA.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     1000000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Consumer & Retail
    ('XXL.OL', 'XXL.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_DISC', 'HIGH', true,
     1000000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('KID.OL', 'KID.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SCHA.OL', 'SCHA.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'CONSUMER_STAPLES', 'LOW', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Healthcare & Biotech
    ('PHO.OL', 'PHO.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'HEALTHCARE', 'HIGH', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Real Estate
    ('ENTRA.OL', 'ENTRA.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'REAL_ESTATE', 'MEDIUM', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('OLT.OL', 'OLT.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'REAL_ESTATE', 'MEDIUM', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Media & Entertainment
    ('SCATC.OL', 'SCATC.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'UTILITIES', 'MEDIUM', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- More Industrials
    ('WAWI.OL', 'WAWI.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NOD.OL', 'NOD.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     1000000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GJF.OL', 'GJF.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Renewable Energy
    ('NEL.OL', 'NEL.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'UTILITIES', 'HIGH', true,
     5000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('REC.OL', 'REC.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AKER.OL', 'AKER.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- More Shipping
    ('GOGL.OL', 'GOGL.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     3000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('STRO.OL', 'STRO.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BELCO.OL', 'BELCO.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Banking & Finance
    ('SRBNK.OL', 'SRBNK.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MORG.OL', 'MORG.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PROTCT.OL', 'PROTCT.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Additional companies
    ('AUTO.OL', 'AUTO.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     2000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BEWI.OL', 'BEWI.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ELMRA.OL', 'ELMRA.OL', 'XOSL', 'EQUITY', 'NOK', 1, 0.01, 'UTILITIES', 'MEDIUM', true,
     1500000, 252, 'FORWARD_FILL', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    exchange_mic = EXCLUDED.exchange_mic,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    updated_at = NOW();

-- ============================================================================
-- PART C: Governance Logging (ADR-002)
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
    'fhq_meta.assets (Oslo Børs)',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §2.1 Asset Onboarding - Oslo Børs (XOSL): 50+ Norwegian equities registered. OBX Index + Mid-cap coverage. All assets start in QUARANTINED status pending 252-day Iron Curtain validation. Sectors: Energy, Financials, Seafood, Telecom, Industrials, Technology, Shipping, Healthcare, Real Estate.',
    false,
    'MIG-112-IOS001-OSLO-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART D: Verification
-- ============================================================================

DO $$
DECLARE
    oslo_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO oslo_count
    FROM fhq_meta.assets
    WHERE exchange_mic = 'XOSL' AND active_flag = true;

    IF oslo_count < 50 THEN
        RAISE WARNING 'Expected at least 50 Oslo Børs assets, found %', oslo_count;
    ELSE
        RAISE NOTICE 'Oslo Børs onboarding complete: % assets registered', oslo_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Migration 112 Complete
-- Oslo Børs assets: 50+ registered (XOSL exchange)
-- All assets in QUARANTINED status pending price data backfill
-- Next: Migration 113 (Crypto Assets)
-- ============================================================================
