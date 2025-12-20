-- =============================================================================
-- Migration 121: IoS-001 S&P 500 Universe Expansion
-- =============================================================================
-- Authority: CEO Directive - 500+ Canonical Assets
-- Date: 2025-12-11
-- Executor: STIG (CTO)
--
-- Purpose: Add remaining S&P 500 components to reach 500+ asset target
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. Add remaining S&P 500 Large Cap
-- =============================================================================

INSERT INTO fhq_meta.assets (
    canonical_id, ticker, exchange_mic, asset_class, currency, sector,
    active_flag, quarantine_threshold, full_history_threshold, price_source_field
)
SELECT
    v.canonical_id, v.ticker, v.exchange_mic, v.asset_class::text, v.currency, v.sector,
    v.active_flag, v.quarantine_threshold, v.full_history_threshold, v.price_source_field
FROM (VALUES
    -- Healthcare (17)
    ('ISRG', 'ISRG', 'XNAS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('MDT', 'MDT', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('BMY', 'BMY', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('GILD', 'GILD', 'XNAS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('AMGN', 'AMGN', 'XNAS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('CVS', 'CVS', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('CI', 'CI', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('ELV', 'ELV', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('HUM', 'HUM', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('REGN', 'REGN', 'XNAS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('VRTX', 'VRTX', 'XNAS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('ZTS', 'ZTS', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('SYK', 'SYK', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('BSX', 'BSX', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('MCK', 'MCK', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('EW', 'EW', 'XNYS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),
    ('DXCM', 'DXCM', 'XNAS', 'EQUITY', 'USD', 'Healthcare', true, 252, 1260, 'adj_close'),

    -- Financials (20)
    ('SCHW', 'SCHW', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('CB', 'CB', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('PGR', 'PGR', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('AXP', 'AXP', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('CME', 'CME', 'XNAS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('ICE', 'ICE', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('AON', 'AON', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('MMC', 'MMC', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('USB', 'USB', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('PNC', 'PNC', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('TFC', 'TFC', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('AIG', 'AIG', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('MET', 'MET', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('COF', 'COF', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('AFL', 'AFL', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('ALL', 'ALL', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('TRV', 'TRV', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('SPGI', 'SPGI', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('MCO', 'MCO', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),
    ('MSCI', 'MSCI', 'XNYS', 'EQUITY', 'USD', 'Financials', true, 252, 1260, 'adj_close'),

    -- Industrials (20)
    ('UPS', 'UPS', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('FDX', 'FDX', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('NOC', 'NOC', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('GD', 'GD', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('LHX', 'LHX', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('ITW', 'ITW', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('EMR', 'EMR', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('ROK', 'ROK', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('ETN', 'ETN', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('PH', 'PH', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('WM', 'WM', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('RSG', 'RSG', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('CTAS', 'CTAS', 'XNAS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('CARR', 'CARR', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('OTIS', 'OTIS', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('CSX', 'CSX', 'XNAS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('NSC', 'NSC', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('DAL', 'DAL', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('UAL', 'UAL', 'XNAS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),
    ('LUV', 'LUV', 'XNYS', 'EQUITY', 'USD', 'Industrials', true, 252, 1260, 'adj_close'),

    -- Consumer Discretionary (18)
    ('CMG', 'CMG', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('YUM', 'YUM', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('MAR', 'MAR', 'XNAS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('HLT', 'HLT', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('TGT', 'TGT', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('ROST', 'ROST', 'XNAS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('ORLY', 'ORLY', 'XNAS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('AZO', 'AZO', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('NVR', 'NVR', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('LEN', 'LEN', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('DHI', 'DHI', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('PHM', 'PHM', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('EBAY', 'EBAY', 'XNAS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('ETSY', 'ETSY', 'XNAS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('DECK', 'DECK', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('LULU', 'LULU', 'XNAS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('DPZ', 'DPZ', 'XNYS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),
    ('POOL', 'POOL', 'XNAS', 'EQUITY', 'USD', 'Consumer', true, 252, 1260, 'adj_close'),

    -- Consumer Staples (15)
    ('PM', 'PM', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('MO', 'MO', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('CL', 'CL', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('EL', 'EL', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('KMB', 'KMB', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('GIS', 'GIS', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('KHC', 'KHC', 'XNAS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('HSY', 'HSY', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('MDLZ', 'MDLZ', 'XNAS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('SYY', 'SYY', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('KR', 'KR', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('CAG', 'CAG', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('CHD', 'CHD', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('CLX', 'CLX', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),
    ('STZ', 'STZ', 'XNYS', 'EQUITY', 'USD', 'Staples', true, 252, 1260, 'adj_close'),

    -- Technology (19)
    ('ADI', 'ADI', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('CDNS', 'CDNS', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('SNPS', 'SNPS', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('NXPI', 'NXPI', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('MCHP', 'MCHP', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('FTNT', 'FTNT', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('ZS', 'ZS', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('OKTA', 'OKTA', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('WDAY', 'WDAY', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('ANSS', 'ANSS', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('INTU', 'INTU', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('ADSK', 'ADSK', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('TEAM', 'TEAM', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('HUBS', 'HUBS', 'XNYS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('DOCU', 'DOCU', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('MDB', 'MDB', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('SPLK', 'SPLK', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('FIVN', 'FIVN', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),
    ('AKAM', 'AKAM', 'XNAS', 'EQUITY', 'USD', 'Technology', true, 252, 1260, 'adj_close'),

    -- Energy (11)
    ('PSX', 'PSX', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('VLO', 'VLO', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('MPC', 'MPC', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('HES', 'HES', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('DVN', 'DVN', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('FANG', 'FANG', 'XNAS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('HAL', 'HAL', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('BKR', 'BKR', 'XNAS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('KMI', 'KMI', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('WMB', 'WMB', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),
    ('OKE', 'OKE', 'XNYS', 'EQUITY', 'USD', 'Energy', true, 252, 1260, 'adj_close'),

    -- Utilities (11)
    ('AEP', 'AEP', 'XNAS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('D', 'D', 'XNYS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('XEL', 'XEL', 'XNAS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('EXC', 'EXC', 'XNAS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('SRE', 'SRE', 'XNYS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('PCG', 'PCG', 'XNYS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('WEC', 'WEC', 'XNYS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('ES', 'ES', 'XNYS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('ED', 'ED', 'XNYS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('EIX', 'EIX', 'XNYS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),
    ('AWK', 'AWK', 'XNYS', 'EQUITY', 'USD', 'Utilities', true, 252, 1260, 'adj_close'),

    -- Materials (12)
    ('ECL', 'ECL', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('DD', 'DD', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('DOW', 'DOW', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('PPG', 'PPG', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('NUE', 'NUE', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('STLD', 'STLD', 'XNAS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('VMC', 'VMC', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('MLM', 'MLM', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('ALB', 'ALB', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('IFF', 'IFF', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('CTVA', 'CTVA', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),
    ('CF', 'CF', 'XNYS', 'EQUITY', 'USD', 'Materials', true, 252, 1260, 'adj_close'),

    -- REITs (12)
    ('AMT', 'AMT', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('CCI', 'CCI', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('EQIX', 'EQIX', 'XNAS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('DLR', 'DLR', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('PLD', 'PLD', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('SPG', 'SPG', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('WELL', 'WELL', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('AVB', 'AVB', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('EQR', 'EQR', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('PSA', 'PSA', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('SBAC', 'SBAC', 'XNAS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),
    ('VICI', 'VICI', 'XNYS', 'EQUITY', 'USD', 'Real Estate', true, 252, 1260, 'adj_close'),

    -- Communications (8)
    ('CHTR', 'CHTR', 'XNAS', 'EQUITY', 'USD', 'Communications', true, 252, 1260, 'adj_close'),
    ('WBD', 'WBD', 'XNAS', 'EQUITY', 'USD', 'Communications', true, 252, 1260, 'adj_close'),
    ('PARA', 'PARA', 'XNAS', 'EQUITY', 'USD', 'Communications', true, 252, 1260, 'adj_close'),
    ('FOX', 'FOX', 'XNAS', 'EQUITY', 'USD', 'Communications', true, 252, 1260, 'adj_close'),
    ('EA', 'EA', 'XNAS', 'EQUITY', 'USD', 'Communications', true, 252, 1260, 'adj_close'),
    ('TTWO', 'TTWO', 'XNAS', 'EQUITY', 'USD', 'Communications', true, 252, 1260, 'adj_close'),
    ('LYV', 'LYV', 'XNYS', 'EQUITY', 'USD', 'Communications', true, 252, 1260, 'adj_close'),
    ('MTCH', 'MTCH', 'XNAS', 'EQUITY', 'USD', 'Communications', true, 252, 1260, 'adj_close')

) AS v(canonical_id, ticker, exchange_mic, asset_class, currency, sector, active_flag, quarantine_threshold, full_history_threshold, price_source_field)
WHERE NOT EXISTS (SELECT 1 FROM fhq_meta.assets WHERE canonical_id = v.canonical_id);

-- =============================================================================
-- 2. Governance logging
-- =============================================================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id,
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    initiated_at,
    decision,
    decision_rationale,
    hash_chain_id
) VALUES (
    gen_random_uuid(),
    'SCHEMA_MIGRATION',
    'IOS001_SP500_EXPANSION',
    'DATA_POPULATION',
    'STIG',
    NOW(),
    'COMPLETED',
    'Added 163 S&P 500 component stocks to reach 500+ asset target per IoS-001 directive',
    encode(sha256('121_ios001_sp500_expansion'::bytea), 'hex')
);

COMMIT;

-- =============================================================================
-- Verification
-- =============================================================================

DO $$
DECLARE
    asset_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO asset_count FROM fhq_meta.assets WHERE active_flag = TRUE;
    RAISE NOTICE 'Total active assets: %', asset_count;

    IF asset_count < 500 THEN
        RAISE NOTICE 'Warning: Asset count (%) is below 500 target', asset_count;
    ELSE
        RAISE NOTICE 'SUCCESS: Asset count meets 500+ target';
    END IF;
END $$;
