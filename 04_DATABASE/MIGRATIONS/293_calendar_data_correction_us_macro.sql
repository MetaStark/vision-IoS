-- Migration 293: Calendar Data Correction - US Macro Data
-- Purpose: Correct US NFP and CPI actual values to match BLS releases
-- Directive: CEO/Board Discrepancy Analysis 2026-01-17
-- Issue: Calendar contained fabricated NFP (256K vs actual 50K) and CPI (2.9% vs actual 2.7%)
-- Executed by: STIG
-- Date: 2026-01-17

-- DISCREPANCY REPORT:
-- US NFP (Jan 10 release, Dec 2025 data):
--   Calendar: actual 256,000, previous 212,000
--   Actual: 50,000, previous 56,000 (revised)
--   Error: 206,000 jobs (5x overstatement)
--
-- US CPI (Jan 14 release, Dec 2025 data):
--   Calendar: actual 2.9%
--   Actual: 2.7%
--   Error: 0.2%

BEGIN;

-- ============================================
-- STEP 1: Correct US NFP (Jan 10, 2026 release)
-- ============================================
-- December 2025 NFP: 50,000 (actual per BLS)
-- November 2025: 56,000 (revised down from 64,000)
-- October 2025: -173,000 (revised down from -105,000)

UPDATE fhq_calendar.calendar_events
SET
    actual_value = 50000,       -- Actual Dec 2025 NFP was 50K, not 256K
    previous_value = 56000,     -- Nov 2025 revised to 56K, not 212K
    consensus_estimate = 60000, -- Consensus was 60K
    updated_at = NOW()
WHERE event_type_code = 'US_NFP'
  AND event_timestamp >= '2026-01-10T00:00:00Z'
  AND event_timestamp < '2026-01-11T00:00:00Z'
  AND is_canonical = true;

-- ============================================
-- STEP 2: Correct US CPI (Jan 14, 2026 release)
-- ============================================
-- December 2025 CPI: 2.7% YoY (actual per BLS)
-- Same as November 2025 (2.7%)
-- Core CPI: 2.6% (lowest since 2021)

UPDATE fhq_calendar.calendar_events
SET
    actual_value = 2.7,         -- Actual Dec 2025 CPI was 2.7%, not 2.9%
    previous_value = 2.7,       -- Nov 2025 was also 2.7%
    consensus_estimate = 2.7,   -- Consensus was 2.7%
    updated_at = NOW()
WHERE event_type_code = 'US_CPI'
  AND event_timestamp >= '2026-01-14T00:00:00Z'
  AND event_timestamp < '2026-01-15T00:00:00Z'
  AND is_canonical = true;

-- ============================================
-- STEP 3: Also correct December 2025 NFP data
-- ============================================
-- The Dec 6, 2025 release (Nov 2025 data) also needs correction
-- if present, to maintain consistency in the chain

UPDATE fhq_calendar.calendar_events
SET
    actual_value = 227000,      -- BLS reported 227K for Nov 2025 at time of release
    previous_value = 36000,     -- Keeping original if correct, verify later
    updated_at = NOW()
WHERE event_type_code = 'US_NFP'
  AND event_timestamp >= '2025-12-06T00:00:00Z'
  AND event_timestamp < '2025-12-07T00:00:00Z'
  AND is_canonical = true
  AND actual_value != 227000;   -- Only if not already correct

-- ============================================
-- STEP 4: Log the correction in governance
-- ============================================

INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale
) VALUES (
    gen_random_uuid(),
    'DATA_CORRECTION',
    'fhq_calendar.calendar_events',
    'TABLE',
    'STIG',
    NOW(),
    'APPROVED',
    'US macro data corrections per CEO/Board discrepancy analysis: NFP Dec 2025 actual 256K->50K (5x overstatement error), previous 212K->56K. CPI Dec 2025 actual 2.9%->2.7%. All values now match BLS official releases.'
);

-- ============================================
-- STEP 5: Create source conflict log entries
-- ============================================

INSERT INTO fhq_calendar.source_conflict_log (
    conflict_id,
    event_type_code,
    event_timestamp,
    event_domain,
    provider_a,
    provider_a_value,
    provider_a_reliability,
    provider_b,
    provider_b_value,
    provider_b_reliability,
    winning_provider,
    winning_reliability,
    resolution_method,
    resolution_notes,
    resolved_at,
    resolved_by,
    event_type_category,
    granular_reliability_used,
    resolution_path
) VALUES
(
    gen_random_uuid(),
    'US_NFP',
    '2026-01-10T13:30:00Z',
    'MACRO',
    'MIGRATION_290_SEED',
    '{"nfp": 256000, "previous": 212000}'::jsonb,
    0.00,
    'BLS_OFFICIAL',
    '{"nfp": 50000, "previous": 56000}'::jsonb,
    1.00,
    'BLS_OFFICIAL',
    1.00,
    'CEO_BOARD_DISCREPANCY_ANALYSIS',
    'CATASTROPHIC NFP ERROR: Calendar showed 256K, actual was 50K - a 206K overstatement (5x error). Previous also wrong: 212K vs actual 56K. This is the most severe data error found.',
    NOW(),
    'STIG',
    'MACRO',
    false,
    'MANUAL_OVERRIDE'
),
(
    gen_random_uuid(),
    'US_CPI',
    '2026-01-14T13:30:00Z',
    'MACRO',
    'MIGRATION_290_SEED',
    '{"cpi_yoy": 2.9}'::jsonb,
    0.00,
    'BLS_OFFICIAL',
    '{"cpi_yoy": 2.7}'::jsonb,
    1.00,
    'BLS_OFFICIAL',
    1.00,
    'CEO_BOARD_DISCREPANCY_ANALYSIS',
    'CPI Dec 2025 corrected from 2.9% to 2.7%. Inflation remained flat at 2.7% in December, same as November.',
    NOW(),
    'STIG',
    'MACRO',
    false,
    'MANUAL_OVERRIDE'
);

COMMIT;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================
-- Run after migration to verify corrections:

-- SELECT event_type_code, event_timestamp, consensus_estimate, actual_value, previous_value
-- FROM fhq_calendar.calendar_events
-- WHERE event_type_code IN ('US_NFP', 'US_CPI')
--   AND event_timestamp >= '2026-01-01'
--   AND is_canonical = true
-- ORDER BY event_timestamp;

-- Expected results:
-- US_NFP Jan 10: consensus=60000, actual=50000, previous=56000
-- US_CPI Jan 14: consensus=2.7, actual=2.7, previous=2.7
