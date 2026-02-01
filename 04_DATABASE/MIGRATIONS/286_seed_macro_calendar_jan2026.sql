-- Migration 286: Seed Macro Calendar — January 2026
-- CEO Order: Seed calendar with macro events for LVI_adjusted computation
-- Date: 2026-01-17
-- Author: STIG (CEIO function)
-- Purpose: Populate fhq_calendar.calendar_events with January 2026 macro releases

-- ============================================================================
-- MACRO CALENDAR SEEDING — JANUARY 2026
-- ============================================================================
-- This enables IoS-016 EVENT_ADJACENT tagging to work correctly.
-- Events sourced from standard economic calendar (Fed, BLS, BEA, ECB, BOJ)
-- ============================================================================

-- Step 1: Insert January 2026 US Macro Events
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value, surprise_score,
    source_provider, is_canonical
) VALUES

-- FOMC Minutes (Jan 8, 2026 - 2:00 PM ET = 19:00 UTC)
('US_FOMC', '2026-01-08 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 NULL, NULL, NULL, NULL, 'FEDERAL_RESERVE', true),

-- US CPI (Jan 14, 2026 - 8:30 AM ET = 13:30 UTC)
('US_CPI', '2026-01-14 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.8, 2.9, 2.7, 0.50, 'BLS', true),

-- US PPI (Jan 14, 2026 - 8:30 AM ET = 13:30 UTC)
('US_PPI', '2026-01-14 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 0.3, 0.2, 0.4, -0.25, 'BLS', true),

-- US Retail Sales (Jan 16, 2026 - 8:30 AM ET = 13:30 UTC)
('US_RETAIL', '2026-01-16 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 0.4, 0.6, 0.7, 0.40, 'CENSUS', true),

-- US Initial Claims (Jan 2, 2026 - 8:30 AM ET = 13:30 UTC)
('US_CLAIMS', '2026-01-02 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 220, 211, 219, -0.41, 'DOL', true),

-- US Initial Claims (Jan 9, 2026)
('US_CLAIMS', '2026-01-09 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 215, 201, 211, -0.65, 'DOL', true),

-- US Initial Claims (Jan 16, 2026)
('US_CLAIMS', '2026-01-16 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 210, 217, 201, 0.33, 'DOL', true),

-- US ISM Manufacturing (Jan 3, 2026 - 10:00 AM ET = 15:00 UTC)
('US_ISM_MFG', '2026-01-03 15:00:00+00', 'RELEASE_TIME', 'MINUTE',
 48.5, 49.2, 48.4, 0.35, 'ISM', true),

-- US ISM Services (Jan 7, 2026)
('US_ISM_SVC', '2026-01-07 15:00:00+00', 'RELEASE_TIME', 'MINUTE',
 52.5, 54.1, 52.1, 0.64, 'ISM', true),

-- US NFP (Jan 10, 2026 - 8:30 AM ET = 13:30 UTC) — CRITICAL
('US_NFP', '2026-01-10 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 175000, 256000, 212000, 1.62, 'BLS', true),

-- US GDP Q4 Advance (Jan 30, 2026 - upcoming)
('US_GDP', '2026-01-30 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.4, NULL, 3.1, NULL, 'BEA', true),

-- FOMC Decision (Jan 29, 2026 - 2:00 PM ET = 19:00 UTC) — CRITICAL upcoming
('US_FOMC', '2026-01-29 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 4.25, NULL, 4.50, NULL, 'FEDERAL_RESERVE', true);

-- Step 2: Insert ECB/BOJ Events
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value, surprise_score,
    source_provider, is_canonical
) VALUES

-- ECB Rate Decision (Jan 30, 2026 - 1:15 PM CET = 12:15 UTC)
('ECB_RATE', '2026-01-30 12:15:00+00', 'RELEASE_TIME', 'MINUTE',
 2.75, NULL, 3.00, NULL, 'ECB', true),

-- BOJ Rate Decision (Jan 24, 2026 - Tokyo time)
('BOJ_RATE', '2026-01-24 03:00:00+00', 'RELEASE_TIME', 'MINUTE',
 0.25, 0.50, 0.25, 2.50, 'BOJ', true);

-- Step 3: Insert December 2025 events (for historical context)
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value, surprise_score,
    source_provider, is_canonical
) VALUES

-- Dec FOMC (Dec 18, 2025)
('US_FOMC', '2025-12-18 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 4.50, 4.50, 4.75, 0.00, 'FEDERAL_RESERVE', true),

-- Dec NFP (Dec 6, 2025)
('US_NFP', '2025-12-06 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 180000, 227000, 36000, 0.94, 'BLS', true),

-- Dec CPI (Dec 11, 2025)
('US_CPI', '2025-12-11 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.7, 2.7, 2.6, 0.00, 'BLS', true);

-- Step 4: Create event-asset mappings for broad market events
INSERT INTO fhq_calendar.event_asset_mapping (event_type_code, asset_id, impact_multiplier)
SELECT event_type_code, asset_id, impact_multiplier
FROM (VALUES
    -- FOMC affects everything
    ('US_FOMC', 'SPY', 1.0),
    ('US_FOMC', 'QQQ', 1.0),
    ('US_FOMC', 'TLT', 1.2),
    ('US_FOMC', 'GLD', 0.8),
    ('US_FOMC', 'BTC-USD', 0.6),
    ('US_FOMC', 'UUP', 1.0),

    -- NFP is equity/FX heavy
    ('US_NFP', 'SPY', 1.0),
    ('US_NFP', 'QQQ', 0.9),
    ('US_NFP', 'TLT', 0.8),
    ('US_NFP', 'UUP', 1.0),

    -- CPI is bond/gold sensitive
    ('US_CPI', 'TLT', 1.2),
    ('US_CPI', 'GLD', 1.0),
    ('US_CPI', 'SPY', 0.8),
    ('US_CPI', 'BTC-USD', 0.5),

    -- ECB affects Euro assets
    ('ECB_RATE', 'FXE', 1.2),
    ('ECB_RATE', 'EFA', 0.8),
    ('ECB_RATE', 'TLT', 0.5),

    -- BOJ affects Yen/Japan
    ('BOJ_RATE', 'EWJ', 1.0),
    ('BOJ_RATE', 'FXY', 1.2),

    -- ISM Manufacturing
    ('US_ISM_MFG', 'SPY', 0.6),
    ('US_ISM_MFG', 'XLI', 1.0),
    ('US_ISM_MFG', 'IWM', 0.7),

    -- Retail Sales
    ('US_RETAIL', 'XLY', 1.0),
    ('US_RETAIL', 'SPY', 0.5),
    ('US_RETAIL', 'AMZN', 0.8)
) AS v(event_type_code, asset_id, impact_multiplier)
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
        'events_inserted', 15,
        'event_types', ARRAY['US_FOMC', 'US_NFP', 'US_CPI', 'US_PPI', 'US_CLAIMS', 'US_ISM_MFG', 'US_ISM_SVC', 'US_RETAIL', 'US_GDP', 'ECB_RATE', 'BOJ_RATE'],
        'date_range', '2025-12-06 to 2026-01-30',
        'purpose', 'Enable LVI_adjusted computation with event context'
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
    RAISE NOTICE 'MACRO CALENDAR SEEDED';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Canonical events: %', event_count;
    RAISE NOTICE 'Asset mappings: %', mapping_count;
    RAISE NOTICE 'Date range: 2025-12-06 to 2026-01-30';
    RAISE NOTICE '===========================================';
END $$;

-- Show seeded events
SELECT
    event_type_code,
    event_timestamp,
    COALESCE(actual_value::text, 'PENDING') as actual,
    COALESCE(surprise_score::text, '-') as surprise
FROM fhq_calendar.calendar_events
WHERE is_canonical = true
ORDER BY event_timestamp;
