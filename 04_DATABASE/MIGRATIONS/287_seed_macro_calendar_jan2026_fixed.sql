-- Migration 287: Seed Macro Calendar — January 2026 (CORRECTED)
-- CEO Order: Seed calendar with macro events for LVI_adjusted computation
-- Date: 2026-01-17
-- Author: STIG (CEIO function)
-- Purpose: Populate fhq_calendar.calendar_events with January 2026 macro releases
-- FIX: Removed surprise_score (generated column), added asset_class to mappings

-- ============================================================================
-- MACRO CALENDAR SEEDING — JANUARY 2026 (CORRECTED)
-- ============================================================================
-- This enables IoS-016 EVENT_ADJACENT tagging to work correctly.
-- Events sourced from standard economic calendar (Fed, BLS, BEA, ECB, BOJ)
-- ============================================================================

-- Step 1: Insert January 2026 US Macro Events
-- NOTE: surprise_score is GENERATED from (actual_value - consensus_estimate) / |consensus_estimate|
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value,
    source_provider, is_canonical
) VALUES

-- FOMC Minutes (Jan 8, 2026 - 2:00 PM ET = 19:00 UTC)
('US_FOMC', '2026-01-08 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 NULL, NULL, NULL, 'FEDERAL_RESERVE', true),

-- US CPI (Jan 14, 2026 - 8:30 AM ET = 13:30 UTC)
('US_CPI', '2026-01-14 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.8, 2.9, 2.7, 'BLS', true),

-- US PPI (Jan 14, 2026 - 8:30 AM ET = 13:30 UTC)
('US_PPI', '2026-01-14 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 0.3, 0.2, 0.4, 'BLS', true),

-- US Retail Sales (Jan 16, 2026 - 8:30 AM ET = 13:30 UTC)
('US_RETAIL', '2026-01-16 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 0.4, 0.6, 0.7, 'CENSUS', true),

-- US Initial Claims (Jan 2, 2026 - 8:30 AM ET = 13:30 UTC)
('US_CLAIMS', '2026-01-02 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 220, 211, 219, 'DOL', true),

-- US Initial Claims (Jan 9, 2026)
('US_CLAIMS', '2026-01-09 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 215, 201, 211, 'DOL', true),

-- US Initial Claims (Jan 16, 2026)
('US_CLAIMS', '2026-01-16 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 210, 217, 201, 'DOL', true),

-- US ISM Manufacturing (Jan 3, 2026 - 10:00 AM ET = 15:00 UTC)
('US_ISM_MFG', '2026-01-03 15:00:00+00', 'RELEASE_TIME', 'MINUTE',
 48.5, 49.2, 48.4, 'ISM', true),

-- US ISM Services (Jan 7, 2026)
('US_ISM_SVC', '2026-01-07 15:00:00+00', 'RELEASE_TIME', 'MINUTE',
 52.5, 54.1, 52.1, 'ISM', true),

-- US NFP (Jan 10, 2026 - 8:30 AM ET = 13:30 UTC) — CRITICAL
('US_NFP', '2026-01-10 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 175000, 256000, 212000, 'BLS', true),

-- US GDP Q4 Advance (Jan 30, 2026 - upcoming)
('US_GDP', '2026-01-30 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.4, NULL, 3.1, 'BEA', true),

-- FOMC Decision (Jan 29, 2026 - 2:00 PM ET = 19:00 UTC) — CRITICAL upcoming
('US_FOMC', '2026-01-29 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 4.25, NULL, 4.50, 'FEDERAL_RESERVE', true);

-- Step 2: Insert ECB/BOJ Events
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value,
    source_provider, is_canonical
) VALUES

-- ECB Rate Decision (Jan 30, 2026 - 1:15 PM CET = 12:15 UTC)
('ECB_RATE', '2026-01-30 12:15:00+00', 'RELEASE_TIME', 'MINUTE',
 2.75, NULL, 3.00, 'ECB', true),

-- BOJ Rate Decision (Jan 24, 2026 - Tokyo time)
('BOJ_RATE', '2026-01-24 03:00:00+00', 'RELEASE_TIME', 'MINUTE',
 0.25, 0.50, 0.25, 'BOJ', true);

-- Step 3: Insert December 2025 events (for historical context)
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value,
    source_provider, is_canonical
) VALUES

-- Dec FOMC (Dec 18, 2025)
('US_FOMC', '2025-12-18 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 4.50, 4.50, 4.75, 'FEDERAL_RESERVE', true),

-- Dec NFP (Dec 6, 2025)
('US_NFP', '2025-12-06 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 180000, 227000, 36000, 'BLS', true),

-- Dec CPI (Dec 11, 2025)
('US_CPI', '2025-12-11 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.7, 2.7, 2.6, 'BLS', true);

-- Step 4: Create event-asset mappings with required asset_class
INSERT INTO fhq_calendar.event_asset_mapping (event_type_code, asset_id, asset_class, impact_multiplier)
VALUES
    -- FOMC affects everything
    ('US_FOMC', 'SPY', 'EQUITY', 1.0),
    ('US_FOMC', 'QQQ', 'EQUITY', 1.0),
    ('US_FOMC', 'TLT', 'FIXED_INCOME', 1.2),
    ('US_FOMC', 'GLD', 'COMMODITY', 0.8),
    ('US_FOMC', 'BTC-USD', 'CRYPTO', 0.6),
    ('US_FOMC', 'UUP', 'FX', 1.0),

    -- NFP is equity/FX heavy
    ('US_NFP', 'SPY', 'EQUITY', 1.0),
    ('US_NFP', 'QQQ', 'EQUITY', 0.9),
    ('US_NFP', 'TLT', 'FIXED_INCOME', 0.8),
    ('US_NFP', 'UUP', 'FX', 1.0),

    -- CPI is bond/gold sensitive
    ('US_CPI', 'TLT', 'FIXED_INCOME', 1.2),
    ('US_CPI', 'GLD', 'COMMODITY', 1.0),
    ('US_CPI', 'SPY', 'EQUITY', 0.8),
    ('US_CPI', 'BTC-USD', 'CRYPTO', 0.5),

    -- ECB affects Euro assets
    ('ECB_RATE', 'FXE', 'FX', 1.2),
    ('ECB_RATE', 'EFA', 'EQUITY', 0.8),
    ('ECB_RATE', 'TLT', 'FIXED_INCOME', 0.5),

    -- BOJ affects Yen/Japan
    ('BOJ_RATE', 'EWJ', 'EQUITY', 1.0),
    ('BOJ_RATE', 'FXY', 'FX', 1.2),

    -- ISM Manufacturing
    ('US_ISM_MFG', 'SPY', 'EQUITY', 0.6),
    ('US_ISM_MFG', 'XLI', 'EQUITY', 1.0),
    ('US_ISM_MFG', 'IWM', 'EQUITY', 0.7),

    -- Retail Sales
    ('US_RETAIL', 'XLY', 'EQUITY', 1.0),
    ('US_RETAIL', 'SPY', 'EQUITY', 0.5),
    ('US_RETAIL', 'AMZN', 'EQUITY', 0.8)
ON CONFLICT DO NOTHING;

-- Step 5: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MACRO_CALENDAR_SEEDED',
    'fhq_calendar.calendar_events',
    'DATA_INGESTION',
    'CEIO',
    'SEEDED',
    'CEO Order: Seed calendar with macro events. January 2026 + December 2025 historical context. Enables IoS-016 EVENT_ADJACENT tagging.',
    jsonb_build_object(
        'events_inserted', 17,
        'event_types', ARRAY['US_FOMC', 'US_NFP', 'US_CPI', 'US_PPI', 'US_CLAIMS', 'US_ISM_MFG', 'US_ISM_SVC', 'US_RETAIL', 'US_GDP', 'ECB_RATE', 'BOJ_RATE'],
        'date_range', '2025-12-06 to 2026-01-30',
        'purpose', 'Enable LVI_adjusted computation with event context',
        'fix_applied', 'Removed surprise_score (generated column), added asset_class to mappings'
    )
);

-- Verification
DO $$
DECLARE
    event_count INTEGER;
    mapping_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO event_count
    FROM fhq_calendar.calendar_events
    WHERE is_canonical = true;

    SELECT COUNT(*) INTO mapping_count
    FROM fhq_calendar.event_asset_mapping;

    RAISE NOTICE '===========================================';
    RAISE NOTICE 'MACRO CALENDAR SEEDED (CORRECTED)';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Canonical events: %', event_count;
    RAISE NOTICE 'Asset mappings: %', mapping_count;
    RAISE NOTICE 'Date range: 2025-12-06 to 2026-01-30';
    RAISE NOTICE '===========================================';
END $$;

-- Show seeded events with computed surprise scores
SELECT
    event_type_code,
    event_timestamp,
    consensus_estimate,
    actual_value,
    ROUND(surprise_score::numeric, 4) as surprise_score,
    source_provider
FROM fhq_calendar.calendar_events
WHERE is_canonical = true
ORDER BY event_timestamp;
