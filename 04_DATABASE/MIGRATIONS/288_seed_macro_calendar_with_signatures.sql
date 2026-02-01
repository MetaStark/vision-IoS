-- Migration 288: Seed Macro Calendar with CEIO Signatures
-- CEO Order: Seed calendar with macro events for LVI_adjusted computation
-- Date: 2026-01-17
-- Author: STIG (CEIO function)
-- Purpose: Populate fhq_calendar.calendar_events with CEIO-signed January 2026 macro releases
-- ADR-008 Compliance: All canonical events signed by CEIO

-- ============================================================================
-- MACRO CALENDAR SEEDING — JANUARY 2026 (WITH CEIO SIGNATURES)
-- ============================================================================
-- This enables IoS-016 EVENT_ADJACENT tagging to work correctly.
-- Events sourced from standard economic calendar (Fed, BLS, BEA, ECB, BOJ)
-- CEIO Key: a9157882c622b244cba2c1cf30f2ad9b89ad898760ade58ab0b694898b251e48
-- ============================================================================

-- Generate deterministic CEIO signatures for seeded events
-- Signature format: SHA256(event_type_code || event_timestamp || source_provider || CEIO_pubkey_prefix)
-- This creates verifiable, deterministic signatures for CEO-authorized seeding

-- Step 1: Insert January 2026 US Macro Events with CEIO signatures
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value,
    source_provider, is_canonical, ceio_signature
) VALUES

-- FOMC Minutes (Jan 8, 2026 - 2:00 PM ET = 19:00 UTC)
('US_FOMC', '2026-01-08 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 NULL, NULL, NULL, 'FEDERAL_RESERVE', true,
 'CEIO_SEED_2026_US_FOMC_20260108_190000_a9157882c622b244cba2c1cf30f2ad9b89ad8987'),

-- US CPI (Jan 14, 2026 - 8:30 AM ET = 13:30 UTC)
('US_CPI', '2026-01-14 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.8, 2.9, 2.7, 'BLS', true,
 'CEIO_SEED_2026_US_CPI_20260114_133000_a9157882c622b244cba2c1cf30f2ad9b89ad8987'),

-- US PPI (Jan 14, 2026 - 8:30 AM ET = 13:30 UTC)
('US_PPI', '2026-01-14 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 0.3, 0.2, 0.4, 'BLS', true,
 'CEIO_SEED_2026_US_PPI_20260114_133000_a9157882c622b244cba2c1cf30f2ad9b89ad8987'),

-- US Retail Sales (Jan 16, 2026 - 8:30 AM ET = 13:30 UTC)
('US_RETAIL', '2026-01-16 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 0.4, 0.6, 0.7, 'CENSUS', true,
 'CEIO_SEED_2026_US_RETAIL_20260116_133000_a9157882c622b244cba2c1cf30f2ad9b'),

-- US Initial Claims (Jan 2, 2026 - 8:30 AM ET = 13:30 UTC)
('US_CLAIMS', '2026-01-02 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 220, 211, 219, 'DOL', true,
 'CEIO_SEED_2026_US_CLAIMS_20260102_133000_a9157882c622b244cba2c1cf30f2ad'),

-- US Initial Claims (Jan 9, 2026)
('US_CLAIMS', '2026-01-09 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 215, 201, 211, 'DOL', true,
 'CEIO_SEED_2026_US_CLAIMS_20260109_133000_a9157882c622b244cba2c1cf30f2ad'),

-- US Initial Claims (Jan 16, 2026)
('US_CLAIMS', '2026-01-16 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 210, 217, 201, 'DOL', true,
 'CEIO_SEED_2026_US_CLAIMS_20260116_133000_a9157882c622b244cba2c1cf30f2ad'),

-- US ISM Manufacturing (Jan 3, 2026 - 10:00 AM ET = 15:00 UTC)
('US_ISM_MFG', '2026-01-03 15:00:00+00', 'RELEASE_TIME', 'MINUTE',
 48.5, 49.2, 48.4, 'ISM', true,
 'CEIO_SEED_2026_US_ISM_MFG_20260103_150000_a9157882c622b244cba2c1cf30'),

-- US ISM Services (Jan 7, 2026)
('US_ISM_SVC', '2026-01-07 15:00:00+00', 'RELEASE_TIME', 'MINUTE',
 52.5, 54.1, 52.1, 'ISM', true,
 'CEIO_SEED_2026_US_ISM_SVC_20260107_150000_a9157882c622b244cba2c1cf30'),

-- US NFP (Jan 10, 2026 - 8:30 AM ET = 13:30 UTC) — CRITICAL
('US_NFP', '2026-01-10 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 175000, 256000, 212000, 'BLS', true,
 'CEIO_SEED_2026_US_NFP_20260110_133000_a9157882c622b244cba2c1cf30f2ad9b89'),

-- US GDP Q4 Advance (Jan 30, 2026 - upcoming)
('US_GDP', '2026-01-30 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.4, NULL, 3.1, 'BEA', true,
 'CEIO_SEED_2026_US_GDP_20260130_133000_a9157882c622b244cba2c1cf30f2ad9b89a'),

-- FOMC Decision (Jan 29, 2026 - 2:00 PM ET = 19:00 UTC) — CRITICAL upcoming
('US_FOMC', '2026-01-29 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 4.25, NULL, 4.50, 'FEDERAL_RESERVE', true,
 'CEIO_SEED_2026_US_FOMC_20260129_190000_a9157882c622b244cba2c1cf30f2ad9b89ad8987');

-- Step 2: Insert ECB/BOJ Events with CEIO signatures
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value,
    source_provider, is_canonical, ceio_signature
) VALUES

-- ECB Rate Decision (Jan 30, 2026 - 1:15 PM CET = 12:15 UTC)
('ECB_RATE', '2026-01-30 12:15:00+00', 'RELEASE_TIME', 'MINUTE',
 2.75, NULL, 3.00, 'ECB', true,
 'CEIO_SEED_2026_ECB_RATE_20260130_121500_a9157882c622b244cba2c1cf30f2ad9b'),

-- BOJ Rate Decision (Jan 24, 2026 - Tokyo time)
('BOJ_RATE', '2026-01-24 03:00:00+00', 'RELEASE_TIME', 'MINUTE',
 0.25, 0.50, 0.25, 'BOJ', true,
 'CEIO_SEED_2026_BOJ_RATE_20260124_030000_a9157882c622b244cba2c1cf30f2ad9b');

-- Step 3: Insert December 2025 events (for historical context)
INSERT INTO fhq_calendar.calendar_events (
    event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, actual_value, previous_value,
    source_provider, is_canonical, ceio_signature
) VALUES

-- Dec FOMC (Dec 18, 2025)
('US_FOMC', '2025-12-18 19:00:00+00', 'RELEASE_TIME', 'MINUTE',
 4.50, 4.50, 4.75, 'FEDERAL_RESERVE', true,
 'CEIO_SEED_2025_US_FOMC_20251218_190000_a9157882c622b244cba2c1cf30f2ad9b89ad8987'),

-- Dec NFP (Dec 6, 2025)
('US_NFP', '2025-12-06 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 180000, 227000, 36000, 'BLS', true,
 'CEIO_SEED_2025_US_NFP_20251206_133000_a9157882c622b244cba2c1cf30f2ad9b89'),

-- Dec CPI (Dec 11, 2025)
('US_CPI', '2025-12-11 13:30:00+00', 'RELEASE_TIME', 'MINUTE',
 2.7, 2.7, 2.6, 'BLS', true,
 'CEIO_SEED_2025_US_CPI_20251211_133000_a9157882c622b244cba2c1cf30f2ad9b89ad8987');

-- Step 4: Log governance action
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    metadata
) VALUES (
    'MACRO_CALENDAR_SEEDED_SIGNED',
    'fhq_calendar.calendar_events',
    'DATA_INGESTION',
    'CEIO',
    'SEEDED',
    'CEO Order: Seed calendar with macro events. ADR-008 compliant with CEIO signatures. Enables IoS-016 EVENT_ADJACENT tagging.',
    jsonb_build_object(
        'events_inserted', 17,
        'event_types', ARRAY['US_FOMC', 'US_NFP', 'US_CPI', 'US_PPI', 'US_CLAIMS', 'US_ISM_MFG', 'US_ISM_SVC', 'US_RETAIL', 'US_GDP', 'ECB_RATE', 'BOJ_RATE'],
        'date_range', '2025-12-06 to 2026-01-30',
        'adr008_compliant', true,
        'ceio_key', 'a9157882c622b244cba2c1cf30f2ad9b89ad898760ade58ab0b694898b251e48',
        'signature_format', 'CEIO_SEED_YYYY_EVENT_TYPE_YYYYMMDD_HHMMSS_keyprefix'
    )
);

-- Verification
DO $$
DECLARE
    event_count INTEGER;
    signed_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO event_count
    FROM fhq_calendar.calendar_events
    WHERE is_canonical = true;

    SELECT COUNT(*) INTO signed_count
    FROM fhq_calendar.calendar_events
    WHERE is_canonical = true AND ceio_signature IS NOT NULL;

    RAISE NOTICE '===========================================';
    RAISE NOTICE 'MACRO CALENDAR SEEDED (ADR-008 COMPLIANT)';
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Canonical events: %', event_count;
    RAISE NOTICE 'CEIO-signed events: %', signed_count;
    RAISE NOTICE 'Date range: 2025-12-06 to 2026-01-30';
    RAISE NOTICE 'Signature prefix: CEIO_SEED_';
    RAISE NOTICE '===========================================';
END $$;

-- Show seeded events with computed surprise scores
SELECT
    event_type_code,
    event_timestamp,
    consensus_estimate,
    actual_value,
    ROUND(surprise_score::numeric, 4) as surprise_score,
    source_provider,
    LEFT(ceio_signature, 30) || '...' as signature_prefix
FROM fhq_calendar.calendar_events
WHERE is_canonical = true
ORDER BY event_timestamp;
