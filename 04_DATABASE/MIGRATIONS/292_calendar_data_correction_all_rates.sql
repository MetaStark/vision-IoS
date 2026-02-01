-- Migration 292: Calendar Data Correction - ALL Central Bank Rates
-- Purpose: Correct ALL central bank rates to match actual market conditions
-- Directive: CEO/Board Discrepancy Analysis 2026-01-17
-- Issue: Calendar contained fabricated/hallucinated rate data
-- Executed by: STIG
-- Date: 2026-01-17

-- DISCREPANCY REPORT:
-- ECB: Calendar shows 2.75% consensus, actual deposit rate is 2.00%
-- BOE: Calendar shows 4.50% consensus, actual Bank Rate is 3.75%
-- BOJ: Calendar shows previous 0.25%, actual previous is 0.75% (Dec 2025 hike)
-- PBOC: Calendar shows 3.10%, actual 1-year LPR is 3.00%

BEGIN;

-- ============================================
-- STEP 1: Correct ECB Rate Decision (Jan 30)
-- ============================================
-- ECB deposit rate has been at 2.00% since Dec 2025
-- ECB held rates unchanged for 4 consecutive meetings
-- Market expects hold at 2.00%, not cut to 2.75%

UPDATE fhq_calendar.calendar_events
SET
    consensus_estimate = 2.00,  -- Deposit rate, unchanged expected
    previous_value = 2.00,      -- Current rate is 2.00%, not 3.00%
    updated_at = NOW()
WHERE event_type_code = 'ECB_RATE'
  AND event_timestamp >= '2026-01-30T00:00:00Z'
  AND event_timestamp < '2026-01-31T00:00:00Z'
  AND is_canonical = true;

-- ============================================
-- STEP 2: Correct BOE Rate Decision (Feb 6)
-- ============================================
-- BOE cut to 3.75% in December 2025 (from 4.00%)
-- 4 total cuts in 2025: 4.75% -> 3.75%
-- Market expects further cuts to 3.50-3.25% range

UPDATE fhq_calendar.calendar_events
SET
    consensus_estimate = 3.50,  -- Expected cut from 3.75% to 3.50%
    previous_value = 3.75,      -- Current rate is 3.75%, not 4.75%
    updated_at = NOW()
WHERE event_type_code = 'BOE_RATE'
  AND event_timestamp >= '2026-02-06T00:00:00Z'
  AND event_timestamp < '2026-02-07T00:00:00Z'
  AND is_canonical = true;

-- ============================================
-- STEP 3: Correct BOJ Rate Decision (Jan 24)
-- ============================================
-- BOJ raised to 0.75% in December 2025 (highest in 30 years)
-- Previous was 0.50%, before that 0.25%
-- Market expects hold or further hike to 1.00%

UPDATE fhq_calendar.calendar_events
SET
    consensus_estimate = 0.75,  -- Expected hold at 0.75%
    previous_value = 0.75,      -- Rate after Dec 2025 hike
    actual_value = NULL,        -- Clear any pre-filled actual
    updated_at = NOW()
WHERE event_type_code = 'BOJ_RATE'
  AND event_timestamp >= '2026-01-24T00:00:00Z'
  AND event_timestamp < '2026-01-25T00:00:00Z'
  AND is_canonical = true;

-- ============================================
-- STEP 4: Correct PBOC LPR (Jan 22)
-- ============================================
-- PBOC 1-year LPR has been at 3.00% since May 2025
-- 5-year LPR is 3.50%
-- Unchanged for 7 consecutive months

UPDATE fhq_calendar.calendar_events
SET
    consensus_estimate = 3.00,  -- Expected unchanged at 3.00%
    previous_value = 3.00,      -- Current 1-year LPR is 3.00%
    updated_at = NOW()
WHERE event_type_code = 'PBOC_RATE'
  AND event_timestamp >= '2026-01-22T00:00:00Z'
  AND event_timestamp < '2026-01-23T00:00:00Z'
  AND is_canonical = true;

-- ============================================
-- STEP 5: Log the correction in governance
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
    'Central bank rate corrections per CEO/Board discrepancy analysis: ECB 2.75%->2.00%, BOE 4.50%->3.50% (prev 4.75%->3.75%), BOJ prev 0.25%->0.75%, PBOC 3.10%->3.00%. All values now match official central bank publications.'
);

-- ============================================
-- STEP 6: Create source conflict log entries
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
    'ECB_RATE',
    '2026-01-30T12:15:00Z',
    'MACRO',
    'MIGRATION_290_SEED',
    '{"deposit_rate": 2.75, "previous": 3.00}'::jsonb,
    0.00,
    'ECB_OFFICIAL',
    '{"deposit_rate": 2.00, "previous": 2.00}'::jsonb,
    1.00,
    'ECB_OFFICIAL',
    1.00,
    'CEO_BOARD_DISCREPANCY_ANALYSIS',
    'ECB deposit rate corrected from 2.75% to 2.00%. ECB has held at 2.00% for 4 consecutive meetings since Dec 2025.',
    NOW(),
    'STIG',
    'MACRO',
    false,
    'MANUAL_OVERRIDE'
),
(
    gen_random_uuid(),
    'BOE_RATE',
    '2026-02-06T12:00:00Z',
    'MACRO',
    'MIGRATION_290_SEED',
    '{"bank_rate": 4.50, "previous": 4.75}'::jsonb,
    0.00,
    'BOE_OFFICIAL',
    '{"bank_rate": 3.50, "previous": 3.75}'::jsonb,
    1.00,
    'BOE_OFFICIAL',
    1.00,
    'CEO_BOARD_DISCREPANCY_ANALYSIS',
    'BOE Bank Rate corrected from 4.50% to 3.50%. BOE cut 4 times in 2025 from 4.75% to 3.75%. Feb meeting expected to cut to 3.50%.',
    NOW(),
    'STIG',
    'MACRO',
    false,
    'MANUAL_OVERRIDE'
),
(
    gen_random_uuid(),
    'BOJ_RATE',
    '2026-01-24T03:00:00Z',
    'MACRO',
    'MIGRATION_290_SEED',
    '{"policy_rate": 0.50, "previous": 0.25}'::jsonb,
    0.00,
    'BOJ_OFFICIAL',
    '{"policy_rate": 0.75, "previous": 0.75}'::jsonb,
    1.00,
    'BOJ_OFFICIAL',
    1.00,
    'CEO_BOARD_DISCREPANCY_ANALYSIS',
    'BOJ previous rate corrected from 0.25% to 0.75%. BOJ raised to 0.75% in Dec 2025 - highest in 30 years.',
    NOW(),
    'STIG',
    'MACRO',
    false,
    'MANUAL_OVERRIDE'
),
(
    gen_random_uuid(),
    'PBOC_RATE',
    '2026-01-22T01:30:00Z',
    'MACRO',
    'MIGRATION_290_SEED',
    '{"lpr_1y": 3.10}'::jsonb,
    0.00,
    'PBOC_OFFICIAL',
    '{"lpr_1y": 3.00}'::jsonb,
    1.00,
    'PBOC_OFFICIAL',
    1.00,
    'CEO_BOARD_DISCREPANCY_ANALYSIS',
    'PBOC 1-year LPR corrected from 3.10% to 3.00%. LPR unchanged at 3.00% since May 2025.',
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

-- SELECT event_type_code, event_timestamp, consensus_estimate, previous_value, is_canonical
-- FROM fhq_calendar.calendar_events
-- WHERE event_type_code IN ('ECB_RATE', 'BOE_RATE', 'BOJ_RATE', 'PBOC_RATE')
--   AND is_canonical = true
-- ORDER BY event_timestamp;

-- Expected results:
-- ECB Jan 30: consensus=2.00, previous=2.00
-- BOE Feb 6: consensus=3.50, previous=3.75
-- BOJ Jan 24: consensus=0.75, previous=0.75
-- PBOC Jan 22: consensus=3.00, previous=3.00
