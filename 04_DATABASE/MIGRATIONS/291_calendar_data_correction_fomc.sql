-- Migration 291: Calendar Data Correction - FOMC Rate Alignment
-- Purpose: Correct FOMC rate data to match actual market conditions
-- Directive: CEO/Board Discrepancy Analysis 2026-01-17
-- Issue: Calendar contained stale/incorrect rate assumptions
-- Executed by: STIG
-- Date: 2026-01-17

-- DISCREPANCY REPORT:
-- 1. Fed Funds Rate as of Jan 2026: 3.50%-3.75% (after 3 cuts in 2025)
-- 2. FOMC Jan meeting: 27-28 January (not 29)
-- 3. Market expectation: 95% PAUSE probability (not 25bp cut)

BEGIN;

-- ============================================
-- STEP 1: Correct December 2025 FOMC Record
-- ============================================
-- The Dec 18, 2025 FOMC decision resulted in rate at 3.50-3.75%
-- (using midpoint 3.625% or lower bound 3.50%)

UPDATE fhq_calendar.calendar_events
SET
    consensus_estimate = 3.50,
    actual_value = 3.50,
    previous_value = 3.75,
    updated_at = NOW()
WHERE event_id = 'a85bb2cd-d81a-44e5-9842-66494f06a8f8'
  AND event_type_code = 'US_FOMC'
  AND event_timestamp = '2025-12-18T19:00:00Z';

-- ============================================
-- STEP 2: Correct January 2026 FOMC Record
-- ============================================
-- Correct date: Jan 28, 2026 (decision announced end of 2-day meeting)
-- Correct expectation: PAUSE (no change from 3.50%)
-- Previous value: 3.50% (from Dec meeting)

UPDATE fhq_calendar.calendar_events
SET
    event_timestamp = '2026-01-28T19:00:00Z',
    consensus_estimate = 3.50,  -- PAUSE expected (same as current)
    previous_value = 3.50,
    updated_at = NOW()
WHERE event_id = 'fe3cb3ba-6794-4253-ab7d-18a8b09f35a8'
  AND event_type_code = 'US_FOMC'
  AND is_canonical = true;

-- Mark the duplicate/test FOMC entries as non-canonical
UPDATE fhq_calendar.calendar_events
SET is_canonical = false,
    updated_at = NOW()
WHERE event_type_code = 'US_FOMC'
  AND event_timestamp >= '2026-01-29T00:00:00Z'
  AND event_timestamp < '2026-01-30T00:00:00Z'
  AND source_provider IN ('G1_TEST_TZ', 'G1_TEST_PRECISION');

-- ============================================
-- STEP 3: Correct the orphan Jan 8 record
-- ============================================
-- There was no FOMC meeting on Jan 8, 2026 - this is erroneous
-- Mark as non-canonical

UPDATE fhq_calendar.calendar_events
SET is_canonical = false,
    updated_at = NOW()
WHERE event_id = '9d9add8d-d052-4f5c-852c-584355fe0d96'
  AND event_type_code = 'US_FOMC'
  AND event_timestamp = '2026-01-08T19:00:00Z';

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
    'Calendar data correction per CEO/Board discrepancy analysis: FOMC rates corrected from 4.50% to 3.50%, meeting date from Jan 29 to Jan 28, expectation from CUT to PAUSE. Erroneous Jan 8 entry invalidated.'
);

-- ============================================
-- STEP 5: Create discrepancy evidence record
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
) VALUES (
    gen_random_uuid(),
    'US_FOMC',
    '2026-01-28T19:00:00Z',
    'MACRO',
    'MIGRATION_SEED',
    '{"fed_funds_rate": 4.50, "date": "2026-01-29"}'::jsonb,
    0.50,
    'BOARD_VERIFICATION',
    '{"fed_funds_rate": 3.50, "date": "2026-01-28"}'::jsonb,
    1.00,
    'BOARD_VERIFICATION',
    1.00,
    'CEO_BOARD_DISCREPANCY_ANALYSIS',
    'CEO/Board discrepancy analysis identified stale rate data. Fed Funds corrected from 4.50% to 3.50%, FOMC date from Jan 29 to Jan 28, expectation from CUT to PAUSE. Erroneous Jan 8 entry invalidated.',
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

-- SELECT event_type_code, event_timestamp, consensus_estimate, actual_value, previous_value, is_canonical
-- FROM fhq_calendar.calendar_events
-- WHERE event_type_code = 'US_FOMC'
-- ORDER BY event_timestamp;

-- Expected result:
-- Dec 18, 2025: actual=3.50, previous=3.75, canonical=true
-- Jan 28, 2026: consensus=3.50, previous=3.50 (PAUSE), canonical=true
-- Jan 8 and Jan 29 entries: canonical=false
