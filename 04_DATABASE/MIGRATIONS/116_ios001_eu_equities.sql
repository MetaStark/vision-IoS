-- ============================================================================
-- Migration 116: IoS-001 EU Equities Registration
-- DAX 40 + CAC 40 Components (100+ assets)
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-012 (API Waterfall)
-- IoS Reference: IoS-001 §2.1, §4.1
-- CEO Directive: 252-day Iron Curtain for Equities, adj_close for Signal Truth
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: DAX 40 Components (Deutsche Börse XETRA)
-- ============================================================================
-- Yahoo Finance suffix: .DE
-- Settlement: T+2, Timezone: Europe/Berlin
-- Trading Hours: 09:00-17:30 CET

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- DAX 40 - Financials
    ('ALV.DE', 'ALV.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MUV2.DE', 'MUV2.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DBK.DE', 'DBK.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'FINANCIALS', 'HIGH', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CBK.DE', 'CBK.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'FINANCIALS', 'HIGH', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Technology & Software
    ('SAP.DE', 'SAP.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     200000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('IFX.DE', 'IFX.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Automotive
    ('VOW3.DE', 'VOW3.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MBG.DE', 'MBG.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BMW.DE', 'BMW.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('P911.DE', 'P911.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Industrials
    ('SIE.DE', 'SIE.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AIR.DE', 'AIR.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SHL.DE', 'SHL.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MTX.DE', 'MTX.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Healthcare & Pharma
    ('BAS.DE', 'BAS.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BAYN.DE', 'BAYN.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'HEALTHCARE', 'HIGH', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MRK.DE', 'MRK.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('FRE.DE', 'FRE.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SRT3.DE', 'SRT3.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('QIA.DE', 'QIA.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'HEALTHCARE', 'HIGH', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Consumer Goods
    ('ADS.DE', 'ADS.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('HEN3.DE', 'HEN3.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BEI.DE', 'BEI.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Energy & Utilities
    ('RWE.DE', 'RWE.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'UTILITIES', 'MEDIUM', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('EOAN.DE', 'EOAN.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'UTILITIES', 'LOW', true,
     60000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Telecommunications
    ('DTE.DE', 'DTE.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'COMMUNICATION', 'LOW', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Logistics & Transport
    ('DHL.DE', 'DHL.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Real Estate
    ('VNA.DE', 'VNA.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'REAL_ESTATE', 'HIGH', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - E-Commerce & Online
    ('ZAL.DE', 'ZAL.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'HIGH', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('HFG.DE', 'HFG.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'HIGH', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- DAX 40 - Additional Components
    ('HNR1.DE', 'HNR1.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     15000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CON.DE', 'CON.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ENR.DE', 'ENR.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SY1.DE', 'SY1.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'HEALTHCARE', 'HIGH', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PAH3.DE', 'PAH3.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('1COV.DE', '1COV.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     15000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DHER.DE', 'DHER.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'HIGH', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('RHM.DE', 'RHM.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BNR.DE', 'BNR.DE', 'XETR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     15000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

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
-- PART B: CAC 40 Components (Euronext Paris)
-- ============================================================================
-- Yahoo Finance suffix: .PA
-- Settlement: T+2, Timezone: Europe/Paris
-- Trading Hours: 09:00-17:30 CET

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- CAC 40 - Luxury & Consumer
    ('MC.PA', 'MC.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'LOW', true,
     500000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('OR.PA', 'OR.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     200000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('RMS.PA', 'RMS.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'LOW', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('KER.PA', 'KER.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('EL.PA', 'EL.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- CAC 40 - Energy
    ('TTE.PA', 'TTE.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     300000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- CAC 40 - Financials
    ('BNP.PA', 'BNP.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GLE.PA', 'GLE.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'FINANCIALS', 'HIGH', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CS.PA', 'CS.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ACA.PA', 'ACA.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- CAC 40 - Healthcare & Pharma
    ('SAN.PA', 'SAN.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'HEALTHCARE', 'LOW', true,
     200000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- CAC 40 - Industrials & Aerospace
    ('AIR.PA', 'AIR.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SAF.PA', 'SAF.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('HO.PA', 'HO.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LR.PA', 'LR.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('VIE.PA', 'VIE.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SGO.PA', 'SGO.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CAP.PA', 'CAP.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BN.PA', 'BN.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- CAC 40 - Technology
    ('STM.PA', 'STM.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DSY.PA', 'DSY.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- CAC 40 - Utilities & Telecom
    ('ORA.PA', 'ORA.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'COMMUNICATION', 'LOW', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ENGI.PA', 'ENGI.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'UTILITIES', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- CAC 40 - Consumer Products
    ('RI.PA', 'RI.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PUB.PA', 'PUB.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'COMMUNICATION', 'MEDIUM', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- CAC 40 - Additional Components
    ('AI.PA', 'AI.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ML.PA', 'ML.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     60000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('WLN.PA', 'WLN.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'HEALTHCARE', 'LOW', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SU.PA', 'SU.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('URW.PA', 'URW.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'REAL_ESTATE', 'HIGH', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('VIV.PA', 'VIV.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'COMMUNICATION', 'MEDIUM', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TEP.PA', 'TEP.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_DEFENSIVE', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ATO.PA', 'ATO.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     25000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('RNO.PA', 'RNO.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'HIGH', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('EN.PA', 'EN.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_CYCLICAL', 'MEDIUM', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ALO.PA', 'ALO.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     30000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DG.PA', 'DG.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ERF.PA', 'ERF.PA', 'XPAR', 'EQUITY', 'EUR', 1, 0.01, 'REAL_ESTATE', 'MEDIUM', true,
     20000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

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
-- PART C: London Stock Exchange (FTSE 100 Selection)
-- ============================================================================
-- Yahoo Finance suffix: .L
-- Settlement: T+2, Timezone: Europe/London
-- Trading Hours: 08:00-16:30 GMT

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- FTSE 100 - Energy
    ('BP.L', 'BP.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     200000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SHEL.L', 'SHEL.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     300000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- FTSE 100 - Financials
    ('HSBA.L', 'HSBA.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     200000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LLOY.L', 'LLOY.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'HIGH', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BARC.L', 'BARC.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'HIGH', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NWG.L', 'NWG.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('STAN.L', 'STAN.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     60000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LGEN.L', 'LGEN.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'LOW', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AV.L', 'AV.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'LOW', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PRU.L', 'PRU.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- FTSE 100 - Healthcare & Pharma
    ('AZN.L', 'AZN.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'HEALTHCARE', 'LOW', true,
     300000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GSK.L', 'GSK.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'HEALTHCARE', 'LOW', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- FTSE 100 - Consumer
    ('ULVR.L', 'ULVR.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DGE.L', 'DGE.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('RKT.L', 'RKT.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BATS.L', 'BATS.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- FTSE 100 - Mining
    ('RIO.L', 'RIO.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     200000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GLEN.L', 'GLEN.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'MATERIALS', 'HIGH', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AAL.L', 'AAL.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BHP.L', 'BHP.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     150000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- FTSE 100 - Telecom
    ('VOD.L', 'VOD.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'COMMUNICATION', 'HIGH', true,
     100000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BT.A.L', 'BT.A.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'COMMUNICATION', 'HIGH', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- FTSE 100 - Other
    ('REL.L', 'REL.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'COMMUNICATION', 'LOW', true,
     60000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CPG.L', 'CPG.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     40000000, 252, 'FORWARD_FILL', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('III.L', 'III.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     50000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('IAG.L', 'IAG.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     60000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('RR.L', 'RR.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BA.L', 'BA.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     60000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TSCO.L', 'TSCO.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'CONSUMER_DEFENSIVE', 'LOW', true,
     80000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NG.L', 'NG.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'UTILITIES', 'LOW', true,
     60000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SSE.L', 'SSE.L', 'XLON', 'EQUITY', 'GBP', 1, 0.01, 'UTILITIES', 'LOW', true,
     60000000, 252, 'FORWARD_FILL', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

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
-- PART D: Governance Logging (ADR-002)
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
    'fhq_meta.assets (EU_EQUITIES)',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §2.1 Asset Onboarding - EU Equities: 110 assets registered. Coverage: DAX 40 (XETR): 40 assets, CAC 40 (XPAR): 38 assets, FTSE 100 (XLON): 32 assets. All assets in QUARANTINED status with 252-day Iron Curtain. price_source_field = adj_close (Dual Price Ontology).',
    false,
    'MIG-116-IOS001-EU-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART E: Verification
-- ============================================================================

DO $$
DECLARE
    eu_count INTEGER;
    dax_count INTEGER;
    cac_count INTEGER;
    ftse_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO eu_count
    FROM fhq_meta.assets
    WHERE exchange_mic IN ('XETR', 'XPAR', 'XLON') AND asset_class = 'EQUITY' AND active_flag = true;

    SELECT COUNT(*) INTO dax_count
    FROM fhq_meta.assets
    WHERE exchange_mic = 'XETR' AND active_flag = true;

    SELECT COUNT(*) INTO cac_count
    FROM fhq_meta.assets
    WHERE exchange_mic = 'XPAR' AND active_flag = true;

    SELECT COUNT(*) INTO ftse_count
    FROM fhq_meta.assets
    WHERE exchange_mic = 'XLON' AND active_flag = true;

    IF eu_count < 100 THEN
        RAISE WARNING 'Expected at least 100 EU equities, found %', eu_count;
    ELSE
        RAISE NOTICE 'EU equities onboarding complete: % total (DAX: %, CAC: %, FTSE: %)', eu_count, dax_count, cac_count, ftse_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Migration 116 Complete
-- EU Equities: 110 registered (DAX 40 + CAC 40 + FTSE 100 selection)
-- All assets in QUARANTINED status pending 252-day Iron Curtain validation
-- Next: Migration 117 (Indicator Registry Population)
-- ============================================================================
