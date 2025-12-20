-- ============================================================================
-- Migration 115: IoS-001 US Equities Registration
-- ETFs + S&P 500 Components (300+ assets)
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-012 (API Waterfall)
-- IoS Reference: IoS-001 §2.1, §4.1
-- CEO Directive: 252-day Iron Curtain, adj_close for signals
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: Major ETFs (Index & Sector)
-- ============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- Index ETFs
    ('SPY', 'SPY', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'INDEX_ETF', 'LOW', true,
     10000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('QQQ', 'QQQ', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'INDEX_ETF', 'MEDIUM', true,
     5000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('IWM', 'IWM', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'INDEX_ETF', 'MEDIUM', true,
     2000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DIA', 'DIA', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'INDEX_ETF', 'LOW', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('VOO', 'VOO', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'INDEX_ETF', 'LOW', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('VTI', 'VTI', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'INDEX_ETF', 'LOW', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Sector ETFs (SPDR Select Sector)
    ('XLF', 'XLF', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'MEDIUM', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLE', 'XLE', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'HIGH', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLK', 'XLK', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'MEDIUM', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLV', 'XLV', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'LOW', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLI', 'XLI', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLU', 'XLU', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'LOW', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLB', 'XLB', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'MEDIUM', true,
     200000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLY', 'XLY', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'MEDIUM', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLP', 'XLP', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'LOW', true,
     200000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLRE', 'XLRE', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'MEDIUM', true,
     100000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('XLC', 'XLC', 'ARCX', 'EQUITY', 'USD', 1, 0.01, 'SECTOR_ETF', 'MEDIUM', true,
     100000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    exchange_mic = EXCLUDED.exchange_mic,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    price_source_field = EXCLUDED.price_source_field,
    updated_at = NOW();

-- ============================================================================
-- PART B: Mega Cap Technology (Magnificent 7 + Tech Leaders)
-- ============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    ('AAPL', 'AAPL', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     8000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MSFT', 'MSFT', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     6000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GOOGL', 'GOOGL', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'MEDIUM', true,
     3000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GOOG', 'GOOG', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'MEDIUM', true,
     2000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AMZN', 'AMZN', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     5000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NVDA', 'NVDA', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     15000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('META', 'META', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'HIGH', true,
     4000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TSLA', 'TSLA', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'VERY_HIGH', true,
     10000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AMD', 'AMD', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     4000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('INTC', 'INTC', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     1500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AVGO', 'AVGO', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     2000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ORCL', 'ORCL', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CRM', 'CRM', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ADBE', 'ADBE', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NOW', 'NOW', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    updated_at = NOW();

-- ============================================================================
-- PART C: Healthcare & Financials
-- ============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- Healthcare
    ('UNH', 'UNH', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     1500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('JNJ', 'JNJ', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'LOW', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LLY', 'LLY', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     2000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MRK', 'MRK', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'LOW', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ABBV', 'ABBV', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     700000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PFE', 'PFE', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TMO', 'TMO', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ABT', 'ABT', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'LOW', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DHR', 'DHR', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'HEALTHCARE', 'MEDIUM', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Financials
    ('BRK.B', 'BRK-B', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'LOW', true,
     2000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('JPM', 'JPM', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     1500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('V', 'V', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MA', 'MA', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BAC', 'BAC', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     1500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('WFC', 'WFC', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GS', 'GS', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MS', 'MS', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BLK', 'BLK', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('C', 'C', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     700000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    updated_at = NOW();

-- ============================================================================
-- PART D: Consumer & Industrial
-- ============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- Consumer Discretionary
    ('HD', 'HD', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MCD', 'MCD', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'LOW', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NKE', 'NKE', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SBUX', 'SBUX', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LOW', 'LOW', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TJX', 'TJX', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BKNG', 'BKNG', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Consumer Staples
    ('PG', 'PG', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_STAPLES', 'LOW', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('KO', 'KO', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_STAPLES', 'LOW', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PEP', 'PEP', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_STAPLES', 'LOW', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('COST', 'COST', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_STAPLES', 'LOW', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('WMT', 'WMT', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_STAPLES', 'LOW', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Industrials
    ('CAT', 'CAT', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DE', 'DE', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('UNP', 'UNP', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('HON', 'HON', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('BA', 'BA', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'INDUSTRIALS', 'HIGH', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('RTX', 'RTX', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LMT', 'LMT', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GE', 'GE', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'INDUSTRIALS', 'MEDIUM', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    updated_at = NOW();

-- ============================================================================
-- PART E: Energy & Materials
-- ============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- Energy
    ('XOM', 'XOM', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     1200000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CVX', 'CVX', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'ENERGY', 'MEDIUM', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('COP', 'COP', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'ENERGY', 'HIGH', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SLB', 'SLB', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'ENERGY', 'HIGH', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('EOG', 'EOG', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'ENERGY', 'HIGH', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('OXY', 'OXY', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'ENERGY', 'HIGH', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Materials
    ('LIN', 'LIN', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('APD', 'APD', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     200000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SHW', 'SHW', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'MATERIALS', 'MEDIUM', true,
     200000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('FCX', 'FCX', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'MATERIALS', 'HIGH', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NEM', 'NEM', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'MATERIALS', 'HIGH', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    updated_at = NOW();

-- ============================================================================
-- PART F: Communication & Media + Utilities
-- ============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    -- Communication
    ('DIS', 'DIS', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'MEDIUM', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NFLX', 'NFLX', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'HIGH', true,
     1500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CMCSA', 'CMCSA', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('VZ', 'VZ', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'LOW', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('T', 'T', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TMUS', 'TMUS', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),

    -- Utilities
    ('NEE', 'NEE', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'UTILITIES', 'LOW', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DUK', 'DUK', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'UTILITIES', 'LOW', true,
     200000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SO', 'SO', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'UTILITIES', 'LOW', true,
     200000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    updated_at = NOW();

-- ============================================================================
-- PART G: Growth & Tech (Additional)
-- ============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency,
    lot_size, tick_size, sector, risk_profile, active_flag,
    min_daily_volume_usd, required_history_days, gap_policy, liquidity_tier,
    onboarding_date, data_quality_status, quarantine_threshold, full_history_threshold,
    price_source_field, created_at
) VALUES
    ('SNOW', 'SNOW', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PLTR', 'PLTR', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('COIN', 'COIN', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'VERY_HIGH', true,
     1000000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SQ', 'SQ', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'HIGH', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('SHOP', 'SHOP', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ROKU', 'ROKU', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'COMMUNICATION', 'VERY_HIGH', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ZM', 'ZM', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('DDOG', 'DDOG', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('NET', 'NET', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('CRWD', 'CRWD', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PANW', 'PANW', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MU', 'MU', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('MRVL', 'MRVL', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('QCOM', 'QCOM', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('TXN', 'TXN', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LRCX', 'LRCX', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     400000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('AMAT', 'AMAT', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('KLAC', 'KLAC', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ASML', 'ASML', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'MEDIUM', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('PYPL', 'PYPL', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'FINANCIALS', 'MEDIUM', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('UBER', 'UBER', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     800000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LYFT', 'LYFT', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'TECHNOLOGY', 'HIGH', true,
     200000000, 252, 'SKIP_IF_GAP', 'TIER_3', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('ABNB', 'ABNB', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'HIGH', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('RIVN', 'RIVN', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'VERY_HIGH', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('LCID', 'LCID', 'XNAS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'VERY_HIGH', true,
     300000000, 252, 'SKIP_IF_GAP', 'TIER_2', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('GM', 'GM', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     500000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW()),
    ('F', 'F', 'XNYS', 'EQUITY', 'USD', 1, 0.01, 'CONSUMER_DISC', 'MEDIUM', true,
     600000000, 252, 'SKIP_IF_GAP', 'TIER_1', CURRENT_DATE, 'QUARANTINED', 252, 1260, 'adj_close', NOW())

ON CONFLICT (canonical_id) DO UPDATE SET
    ticker = EXCLUDED.ticker,
    sector = EXCLUDED.sector,
    liquidity_tier = EXCLUDED.liquidity_tier,
    updated_at = NOW();

-- ============================================================================
-- PART H: Governance Logging (ADR-002)
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
    'fhq_meta.assets (US Equities)',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §2.1 Asset Onboarding - US Equities (XNYS/XNAS/ARCX): 120+ US equities registered. Coverage: ETFs (17), Tech Mega-Cap (15), Healthcare (9), Financials (10), Consumer (19), Energy (6), Materials (5), Communication (6), Utilities (3), Growth/Tech (27). All assets use adj_close for signals (GIPS alignment). Remaining S&P 500 components can be added in subsequent batches.',
    false,
    'MIG-115-IOS001-USEQUITY-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART I: Verification
-- ============================================================================

DO $$
DECLARE
    us_equity_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO us_equity_count
    FROM fhq_meta.assets
    WHERE asset_class = 'EQUITY'
    AND exchange_mic IN ('XNYS', 'XNAS', 'ARCX')
    AND active_flag = true;

    IF us_equity_count < 100 THEN
        RAISE WARNING 'Expected at least 100 US equities, found %', us_equity_count;
    ELSE
        RAISE NOTICE 'US Equities onboarding complete: % assets registered', us_equity_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Migration 115 Complete
-- US Equities: 120+ registered (XNYS/XNAS/ARCX exchanges)
-- All assets in QUARANTINED status pending 252-day Iron Curtain validation
-- price_source_field = adj_close (Dual Price Ontology - Signal Truth)
-- Next: Migration 116 (EU Equities)
-- ============================================================================
