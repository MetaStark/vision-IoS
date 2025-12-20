-- ============================================================================
-- Migration 111: IoS-001 Exchange Registration
-- Full §2.1 Compliance - Global Exchange Infrastructure
-- ============================================================================
-- Authority: STIG (CTO) per EC-003
-- ADR References: ADR-013 (Canonical Architecture), ADR-002 (Audit)
-- IoS Reference: IoS-001 §3.1
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART A: Register Major Global Exchanges
-- ============================================================================
-- Extends existing XCRY and XFOR with equity exchanges

-- New York Stock Exchange (NYSE)
INSERT INTO fhq_meta.exchanges (
    mic, operating_mic, exchange_name, country_code, timezone, region,
    settlement_convention, open_time, close_time, calendar_id, yahoo_suffix,
    trading_hours, is_active, created_at
) VALUES (
    'XNYS', 'XNYS', 'New York Stock Exchange', 'US', 'America/New_York', 'NORTH_AMERICA',
    'T+2', '09:30:00', '16:00:00', 'NYSE', '',
    '{"regular": {"open": "09:30", "close": "16:00"}, "pre": {"open": "04:00", "close": "09:30"}, "post": {"open": "16:00", "close": "20:00"}}'::jsonb,
    true, NOW()
) ON CONFLICT (mic) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    timezone = EXCLUDED.timezone,
    trading_hours = EXCLUDED.trading_hours,
    updated_at = NOW();

-- NASDAQ
INSERT INTO fhq_meta.exchanges (
    mic, operating_mic, exchange_name, country_code, timezone, region,
    settlement_convention, open_time, close_time, calendar_id, yahoo_suffix,
    trading_hours, is_active, created_at
) VALUES (
    'XNAS', 'XNAS', 'NASDAQ Stock Market', 'US', 'America/New_York', 'NORTH_AMERICA',
    'T+2', '09:30:00', '16:00:00', 'NASDAQ', '',
    '{"regular": {"open": "09:30", "close": "16:00"}, "pre": {"open": "04:00", "close": "09:30"}, "post": {"open": "16:00", "close": "20:00"}}'::jsonb,
    true, NOW()
) ON CONFLICT (mic) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    timezone = EXCLUDED.timezone,
    trading_hours = EXCLUDED.trading_hours,
    updated_at = NOW();

-- Oslo Børs (Euronext Oslo)
INSERT INTO fhq_meta.exchanges (
    mic, operating_mic, exchange_name, country_code, timezone, region,
    settlement_convention, open_time, close_time, calendar_id, yahoo_suffix,
    trading_hours, is_active, created_at
) VALUES (
    'XOSL', 'XOSL', 'Oslo Børs (Euronext Oslo)', 'NO', 'Europe/Oslo', 'EUROPE',
    'T+2', '09:00:00', '16:20:00', 'OSE', '.OL',
    '{"regular": {"open": "09:00", "close": "16:20"}, "pre": {"open": "08:15", "close": "09:00"}, "auction": {"open": "16:20", "close": "16:25"}}'::jsonb,
    true, NOW()
) ON CONFLICT (mic) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    timezone = EXCLUDED.timezone,
    trading_hours = EXCLUDED.trading_hours,
    yahoo_suffix = EXCLUDED.yahoo_suffix,
    updated_at = NOW();

-- Deutsche Börse (XETRA)
INSERT INTO fhq_meta.exchanges (
    mic, operating_mic, exchange_name, country_code, timezone, region,
    settlement_convention, open_time, close_time, calendar_id, yahoo_suffix,
    trading_hours, is_active, created_at
) VALUES (
    'XETR', 'XETR', 'Deutsche Börse XETRA', 'DE', 'Europe/Berlin', 'EUROPE',
    'T+2', '09:00:00', '17:30:00', 'XETRA', '.DE',
    '{"regular": {"open": "09:00", "close": "17:30"}, "pre": {"open": "08:00", "close": "09:00"}, "auction": {"open": "17:30", "close": "17:35"}}'::jsonb,
    true, NOW()
) ON CONFLICT (mic) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    timezone = EXCLUDED.timezone,
    trading_hours = EXCLUDED.trading_hours,
    yahoo_suffix = EXCLUDED.yahoo_suffix,
    updated_at = NOW();

-- London Stock Exchange
INSERT INTO fhq_meta.exchanges (
    mic, operating_mic, exchange_name, country_code, timezone, region,
    settlement_convention, open_time, close_time, calendar_id, yahoo_suffix,
    trading_hours, is_active, created_at
) VALUES (
    'XLON', 'XLON', 'London Stock Exchange', 'GB', 'Europe/London', 'EUROPE',
    'T+2', '08:00:00', '16:30:00', 'LSE', '.L',
    '{"regular": {"open": "08:00", "close": "16:30"}, "auction": {"open": "07:50", "close": "08:00"}}'::jsonb,
    true, NOW()
) ON CONFLICT (mic) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    timezone = EXCLUDED.timezone,
    trading_hours = EXCLUDED.trading_hours,
    yahoo_suffix = EXCLUDED.yahoo_suffix,
    updated_at = NOW();

-- Euronext Paris (for CAC 40)
INSERT INTO fhq_meta.exchanges (
    mic, operating_mic, exchange_name, country_code, timezone, region,
    settlement_convention, open_time, close_time, calendar_id, yahoo_suffix,
    trading_hours, is_active, created_at
) VALUES (
    'XPAR', 'XPAR', 'Euronext Paris', 'FR', 'Europe/Paris', 'EUROPE',
    'T+2', '09:00:00', '17:30:00', 'EURONEXT', '.PA',
    '{"regular": {"open": "09:00", "close": "17:30"}, "pre": {"open": "07:15", "close": "09:00"}}'::jsonb,
    true, NOW()
) ON CONFLICT (mic) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    timezone = EXCLUDED.timezone,
    trading_hours = EXCLUDED.trading_hours,
    yahoo_suffix = EXCLUDED.yahoo_suffix,
    updated_at = NOW();

-- NYSE ARCA (for ETFs)
INSERT INTO fhq_meta.exchanges (
    mic, operating_mic, exchange_name, country_code, timezone, region,
    settlement_convention, open_time, close_time, calendar_id, yahoo_suffix,
    trading_hours, is_active, created_at
) VALUES (
    'ARCX', 'ARCX', 'NYSE Arca', 'US', 'America/New_York', 'NORTH_AMERICA',
    'T+2', '09:30:00', '16:00:00', 'NYSE', '',
    '{"regular": {"open": "09:30", "close": "16:00"}, "pre": {"open": "04:00", "close": "09:30"}, "post": {"open": "16:00", "close": "20:00"}}'::jsonb,
    true, NOW()
) ON CONFLICT (mic) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    timezone = EXCLUDED.timezone,
    trading_hours = EXCLUDED.trading_hours,
    updated_at = NOW();

-- ============================================================================
-- PART B: Update existing exchanges with complete metadata
-- ============================================================================

-- Update XCRY (Cryptocurrency) with proper metadata
UPDATE fhq_meta.exchanges
SET
    operating_mic = 'XCRY',
    settlement_convention = 'T+0',
    open_time = '00:00:00',
    close_time = '23:59:59',
    trading_hours = '{"regular": {"open": "00:00", "close": "23:59"}, "note": "24/7 trading"}'::jsonb,
    updated_at = NOW()
WHERE mic = 'XCRY';

-- Update XFOR (Forex) with proper metadata
UPDATE fhq_meta.exchanges
SET
    operating_mic = 'XFOR',
    settlement_convention = 'T+2',
    open_time = '00:00:00',
    close_time = '23:59:59',
    trading_hours = '{"regular": {"open": "17:00", "close": "17:00"}, "note": "Sunday 17:00 to Friday 17:00 EST"}'::jsonb,
    updated_at = NOW()
WHERE mic = 'XFOR';

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
    'EXCHANGE_REGISTRATION',
    'fhq_meta.exchanges',
    'DATA',
    'STIG',
    NOW(),
    'APPROVED',
    'IoS-001 §3.1 Exchange Registration - Added XNYS, XNAS, XOSL, XETR, XLON, XPAR, ARCX. Updated XCRY, XFOR with complete metadata. Full §2.1 infrastructure for 500+ asset onboarding.',
    false,
    'MIG-111-IOS001-EXCHANGES-' || TO_CHAR(NOW(), 'YYYYMMDD-HH24MISS')
);

-- ============================================================================
-- PART D: Verification Query
-- ============================================================================

-- Verify exchange count
DO $$
DECLARE
    exchange_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO exchange_count FROM fhq_meta.exchanges WHERE is_active = true;
    IF exchange_count < 7 THEN
        RAISE WARNING 'Expected at least 7 active exchanges, found %', exchange_count;
    ELSE
        RAISE NOTICE 'Exchange registration complete: % active exchanges', exchange_count;
    END IF;
END $$;

COMMIT;

-- ============================================================================
-- Migration 111 Complete
-- Exchanges registered: XCRY, XFOR, XNYS, XNAS, XOSL, XETR, XLON, XPAR, ARCX
-- Next: Migration 112 (Oslo Børs Assets)
-- ============================================================================
